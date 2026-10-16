# -*- coding: utf-8 -*-
"""
连续多目标基准（ZDT / DTLZ）：决策变量是实数向量，目标一律「越小越好」，有解析的真 Pareto 前沿，
所以能算 IGD（到真前沿的平均距离）和超体积 HV——这是多目标算法比较的标准做法。

与 domains.py 里的「多目标背包」（位编码、最大化、没有真前沿）是两回事，所以单独成域 mocont：
    变体 zdt1 zdt2 zdt3 zdt4 zdt5（位串）zdt6（双目标）、dtlz1 … dtlz7（三目标）
    算法 random（随机基线）/ wsga（加权和 GA，对照：非凸前沿会漏）/ nsga2 / moead（Tchebycheff + 差分，Li & Zhang 2009）
状态里：pop=当代种群的目标值，front=当代非支配解，igd/hv 是当代前沿的指标，best=到当前为止最好的 IGD（只降不升）。

纯标准库。浏览器里本文件与 domains.py 拼进同一名字空间（同 entryseq.py 的做法）：顶层名字不得与其它模块重名。
参考：Zitzler, Deb & Thiele (2000) Evolutionary Computation 8(2):173-195（ZDT）；
      Deb, Thiele, Laumanns & Zitzler (2005) 在 Evolutionary Multiobjective Optimization 中（DTLZ）。
"""
import math
import random

MOC_VARIANTS = ("zdt1", "zdt2", "zdt3", "zdt4", "zdt5", "zdt6", "dtlz1", "dtlz2", "dtlz3", "dtlz4", "dtlz5", "dtlz6", "dtlz7")
MOC_BITS = ("zdt5",)          # 位串编码的变体（其余都是实数向量）
MOC_SCALE = {"zdt5": [31.0, 10.0]}  # ZDT5 的两个目标量级差很大（f1 在 1..31，f2 在 0.3..10）：MOEA/D 的 Tchebycheff 要先按目标范围归一化；其余变体各目标量级相近，不缩放
MOC_NFIX = {"zdt5": 11}       # 决策变量个数固定的变体：ZDT5 的真前沿 f2 = (n-1)/f1 依赖 n，按论文取 11（第 1 变量 30 位，其余 10 个变量各 5 位）


# ------------------------------------------------------------------ 测试函数（最小化）

def _zdt_g(x):
    return 1.0 + 9.0 * sum(x[1:]) / (len(x) - 1)


def _f_zdt1(x):
    g = _zdt_g(x)
    return [x[0], g * (1.0 - math.sqrt(x[0] / g))]


def _f_zdt2(x):
    g = _zdt_g(x)
    return [x[0], g * (1.0 - (x[0] / g) ** 2)]


def _f_zdt3(x):
    g = _zdt_g(x)
    r = x[0] / g
    return [x[0], g * (1.0 - math.sqrt(r) - r * math.sin(10.0 * math.pi * x[0]))]


def _f_zdt4(x):
    g = 1.0 + 10.0 * (len(x) - 1) + sum(v * v - 10.0 * math.cos(4.0 * math.pi * v) for v in x[1:])
    return [x[0], g * (1.0 - math.sqrt(x[0] / g))]


def _f_zdt6(x):
    f1 = 1.0 - math.exp(-4.0 * x[0]) * math.sin(6.0 * math.pi * x[0]) ** 6
    g = 1.0 + 9.0 * (sum(x[1:]) / (len(x) - 1)) ** 0.25
    return [f1, g * (1.0 - (f1 / g) ** 2)]


def _f_dtlz1(x):
    k = len(x) - 2
    g = 100.0 * (k + sum((v - 0.5) ** 2 - math.cos(20.0 * math.pi * (v - 0.5)) for v in x[2:]))
    return [0.5 * x[0] * x[1] * (1.0 + g), 0.5 * x[0] * (1.0 - x[1]) * (1.0 + g), 0.5 * (1.0 - x[0]) * (1.0 + g)]


def _f_dtlz2(x):
    g = sum((v - 0.5) ** 2 for v in x[2:])
    c = math.pi / 2.0
    return [(1.0 + g) * math.cos(x[0] * c) * math.cos(x[1] * c),
            (1.0 + g) * math.cos(x[0] * c) * math.sin(x[1] * c),
            (1.0 + g) * math.sin(x[0] * c)]


def _f_zdt5(x):
    """ZDT5（位串）：x 是 30 + 5(n-1) 个 0/1。f1 = 1 + 第一段里 1 的个数，g = Σ v(其余各 5 位里 1 的个数)，
    v(u) = 2 + u（u < 5），v(5) = 1；f2 = g / f1。欺骗性：全 0 的段 v=2 很诱人，最优却是全 1（v=1）。"""
    f1 = 1.0 + sum(x[:30])
    g = 0.0
    for i in range(30, len(x), 5):
        u = sum(x[i:i + 5])
        g += 2.0 + u if u < 5 else 1.0
    return [f1, g / f1]


def _dtlz_sphere(g, a1, a2):
    return [(1.0 + g) * math.cos(a1) * math.cos(a2), (1.0 + g) * math.cos(a1) * math.sin(a2), (1.0 + g) * math.sin(a1)]


def _f_dtlz3(x):
    # g 同 DTLZ1（Rastrigin 式，3^k - 1 个局部前沿），形状同 DTLZ2（球面）
    k = len(x) - 2
    g = 100.0 * (k + sum((v - 0.5) ** 2 - math.cos(20.0 * math.pi * (v - 0.5)) for v in x[2:]))
    c = math.pi / 2.0
    return _dtlz_sphere(g, x[0] * c, x[1] * c)


def _f_dtlz4(x):
    # 同 DTLZ2，但 x 被 x^100 压缩：解在目标空间里极不均匀地挤向 f3 = 0 的面（考多样性维护）
    g = sum((v - 0.5) ** 2 for v in x[2:])
    c = math.pi / 2.0
    return _dtlz_sphere(g, (x[0] ** 100) * c, (x[1] ** 100) * c)


def _f_dtlz5(x):
    # 前沿退化成一条曲线（f1 = f2）：第二个角度由 g 控制，g = 0 时恒为 π/4
    g = sum((v - 0.5) ** 2 for v in x[2:])
    t2 = math.pi / (4.0 * (1.0 + g)) * (1.0 + 2.0 * g * x[1])
    return _dtlz_sphere(g, x[0] * math.pi / 2.0, t2)


def _f_dtlz6(x):
    # 同 DTLZ5，但 g = Σ x^0.1：g 在 0 附近极其陡，收敛很难
    g = sum(v ** 0.1 for v in x[2:])
    t2 = math.pi / (4.0 * (1.0 + g)) * (1.0 + 2.0 * g * x[1])
    return _dtlz_sphere(g, x[0] * math.pi / 2.0, t2)


def _dtlz7_f3(f1, f2, g):
    h = 3.0 - sum(f / (1.0 + g) * (1.0 + math.sin(3.0 * math.pi * f)) for f in (f1, f2))
    return (1.0 + g) * h


def _f_dtlz7(x):
    k = len(x) - 2
    g = 1.0 + 9.0 / k * sum(x[2:])
    return [x[0], x[1], _dtlz7_f3(x[0], x[1], g)]


# 变体 → (名称, 目标数, 默认维数, 最小维数, 每维取值范围函数, 目标函数, HV 参考点)
def _unit(n):
    return [(0.0, 1.0)] * n


def _zdt5_bounds(n):
    return [(0, 1)] * (30 + 5 * (n - 1))


def _zdt4_bounds(n):
    return [(0.0, 1.0)] + [(-5.0, 5.0)] * (n - 1)


MOC_SPEC = {
    "zdt1": ("ZDT1（凸前沿）", 2, 30, 2, _unit, _f_zdt1, [1.1, 1.1]),
    "zdt2": ("ZDT2（非凸前沿）", 2, 30, 2, _unit, _f_zdt2, [1.1, 1.1]),
    "zdt3": ("ZDT3（不连续前沿）", 2, 30, 2, _unit, _f_zdt3, [1.1, 1.1]),
    "zdt4": ("ZDT4（多峰：21^9 个局部前沿）", 2, 10, 2, _zdt4_bounds, _f_zdt4, [1.1, 1.1]),
    "zdt5": ("ZDT5（位串编码的欺骗问题）", 2, 11, 2, _zdt5_bounds, _f_zdt5, [32.0, 11.0]),
    "zdt6": ("ZDT6（前沿偏斜、解密度不均）", 2, 10, 2, _unit, _f_zdt6, [1.1, 1.1]),
    "dtlz1": ("DTLZ1（三目标线性前沿，多峰）", 3, 7, 3, _unit, _f_dtlz1, [0.6, 0.6, 0.6]),
    "dtlz2": ("DTLZ2（三目标球面前沿）", 3, 12, 3, _unit, _f_dtlz2, [1.1, 1.1, 1.1]),
    "dtlz3": ("DTLZ3（球面前沿 + 3^k-1 个局部前沿）", 3, 12, 3, _unit, _f_dtlz3, [1.1, 1.1, 1.1]),
    "dtlz4": ("DTLZ4（球面前沿，解密度极不均）", 3, 12, 3, _unit, _f_dtlz4, [1.1, 1.1, 1.1]),
    "dtlz5": ("DTLZ5（前沿退化成曲线）", 3, 12, 3, _unit, _f_dtlz5, [1.1, 1.1, 1.1]),
    "dtlz6": ("DTLZ6（退化曲线 + 难收敛）", 3, 12, 3, _unit, _f_dtlz6, [1.1, 1.1, 1.1]),
    "dtlz7": ("DTLZ7（4 块不连通前沿）", 3, 22, 3, _unit, _f_dtlz7, [1.1, 1.1, 7.0]),
}


def mc_make(variant="zdt1", n=None, seed=7):
    """实例 = 变体 + 决策变量个数（这些基准函数是确定的，没有随机实例；seed 只给算法用）。"""
    if variant not in MOC_SPEC:
        raise ValueError(variant)
    _name, m, n_def, n_min, _b, _f, _r = MOC_SPEC[variant]
    n = n_def if n in (None, "") else int(n)
    if variant in MOC_NFIX:
        n = MOC_NFIX[variant]
    return {"variant": variant, "n": max(n_min, min(n, 100)), "m": m}


class MOC:
    """连续多目标上下文。"""

    def __init__(self, problem):
        self.variant = problem["variant"]
        name, self.m, _nd, self.n_min, bfun, self.fn, self.ref = MOC_SPEC[self.variant]
        self.name = name
        self.n = problem["n"]
        self.bounds = bfun(self.n)
        self.bits = self.variant in MOC_BITS
        self.scale = MOC_SCALE.get(self.variant, [1.0] * self.m)

    def clamp(self, x):
        return [min(hi, max(lo, v)) for v, (lo, hi) in zip(x, self.bounds)]

    def random(self, rng):
        if self.bits:
            return [rng.randint(0, 1) for _ in self.bounds]
        return [rng.uniform(lo, hi) for (lo, hi) in self.bounds]

    def f(self, x):
        return self.fn(x if self.bits else self.clamp(x))

    # ---- 变异 / 交叉：实数编码用 SBX + 多项式变异 / 差分；位串用均匀交叉 + 逐位翻转（概率 1/长度）
    def cross(self, a, b, rng):
        if not self.bits:
            return sbx(a, b, self.bounds, rng)
        if rng.random() > 0.9:
            return list(a), list(b)
        c1, c2 = list(a), list(b)
        for i in range(len(a)):
            if rng.random() < 0.5:
                c1[i], c2[i] = c2[i], c1[i]
        return c1, c2

    def mutate(self, x, rng):
        if not self.bits:
            return poly_mutate(x, self.bounds, rng)
        pm = 1.0 / len(x)
        return [1 - v if rng.random() < pm else v for v in x]

    def vary3(self, a, b, c, rng):
        """MOEA/D 的产生子代：实数 = 差分 a + 0.5(b - c)；位串没有差分，改用 a、b 的交叉。"""
        if self.bits:
            return self.cross(a, b, rng)[0]
        return self.clamp([a[d] + 0.5 * (b[d] - c[d]) for d in range(len(a))])


# ------------------------------------------------------------------ 真前沿与指标

def das_dennis(m, h):
    pts = []

    def rec(rem, k, cur):
        if k == m - 1:
            pts.append([c / h for c in cur + [rem]])
            return
        for i in range(rem + 1):
            rec(rem - i, k + 1, cur + [i])
    rec(h, 0, [])
    return pts


_FRONT_CACHE = {}


def true_front(variant, count=200):
    """解析真前沿的采样点（用作 IGD 的参考集）。"""
    key = (variant, count)
    if key in _FRONT_CACHE:
        return _FRONT_CACHE[key]
    if variant in ("zdt1", "zdt4"):
        pts = [[i / (count - 1), 1.0 - math.sqrt(i / (count - 1))] for i in range(count)]
    elif variant == "zdt2":
        pts = [[i / (count - 1), 1.0 - (i / (count - 1)) ** 2] for i in range(count)]
    elif variant == "zdt3":
        # 曲线 f2 = 1 - sqrt(f1) - f1·sin(10π f1) 中只有一部分是非支配的（5 段）：密采样后按 f1 升序扫一遍，
        # 只保留 f2 严格低于此前所有点的那些（O(n)；论文里的 5 段端点由此得到，不手抄常数）
        dense = [[t / 20000.0, 1.0 - math.sqrt(t / 20000.0) - (t / 20000.0) * math.sin(10.0 * math.pi * t / 20000.0)]
                 for t in range(20001)]
        nd, low = [], float("inf")
        for pt in dense:
            if pt[1] < low:
                nd.append(pt)
                low = pt[1]
        step = max(1, len(nd) // count)
        pts = nd[::step]
    elif variant == "zdt6":
        lo = 0.2807753191
        pts = [[lo + (1.0 - lo) * i / (count - 1), 1.0 - (lo + (1.0 - lo) * i / (count - 1)) ** 2] for i in range(count)]
    elif variant == "zdt5":
        pts = [[float(f1), 10.0 / f1] for f1 in range(1, 32)]  # 离散前沿：g = 10 时 f2 = 10 / f1，f1 取 1..31
    elif variant == "dtlz1":
        pts = [[0.5 * w for w in v] for v in das_dennis(3, 13)]
    elif variant in ("dtlz2", "dtlz3", "dtlz4"):
        pts = []
        for v in das_dennis(3, 13):
            norm = math.sqrt(sum(w * w for w in v))
            pts.append([w / norm for w in v])
    elif variant in ("dtlz5", "dtlz6"):
        # g = 0 时 θ2 = π/4：f1 = f2 = cosθ1/√2，f3 = sinθ1，θ1 ∈ [0, π/2]
        pts = [[math.cos(t) / math.sqrt(2.0), math.cos(t) / math.sqrt(2.0), math.sin(t)]
               for t in (math.pi / 2.0 * i / (count - 1) for i in range(count))]
    elif variant == "dtlz7":
        pts = _dtlz7_front(200)
        step = max(1, len(pts) // count)
        pts = pts[::step]
    else:
        raise ValueError(variant)
    _FRONT_CACHE[key] = pts
    return pts


def _dtlz7_front(grid):
    """DTLZ7 的真前沿（g = 1）：曲面 f3 = h(f1, f2) 上的非支配部分。曲面在 (f1, f2) 网格上取点，
    网格点 (i, j) 被支配 ⇔ 存在 i' ≤ i、j' ≤ j（不同于自己）的点 f3 不比它大；用二维前缀最小值一遍算出，O(grid²)，不必做三维两两比较。"""
    key = ("dtlz7", "grid", grid)
    if key in _FRONT_CACHE:
        return _FRONT_CACHE[key]
    xs = [i / (grid - 1) for i in range(grid)]
    f3 = [[_dtlz7_f3(a, b, 1.0) for b in xs] for a in xs]
    INF = float("inf")
    pm = [[INF] * grid for _ in range(grid)]  # pm[i][j] = min f3 over i' <= i, j' <= j
    pts = []
    for i in range(grid):
        for j in range(grid):
            up = pm[i - 1][j] if i else INF
            left = pm[i][j - 1] if j else INF
            if f3[i][j] < min(up, left):
                pts.append([xs[i], xs[j], f3[i][j]])
            pm[i][j] = min(f3[i][j], up, left)
    pts.sort()
    _FRONT_CACHE[key] = pts
    return pts


def dense_front(variant, h=36):
    """三目标真前沿的密采样（只用来算参考超体积；IGD 用较稀的 true_front）。"""
    key = (variant, "dense", h)
    if key not in _FRONT_CACHE:
        pts = []
        if variant in ("dtlz5", "dtlz6"):
            pts = true_front(variant, 400)
        elif variant == "dtlz7":
            pts = _dtlz7_front(60)
        else:
            for v in das_dennis(3, h):
                if variant == "dtlz1":
                    pts.append([0.5 * w for w in v])
                else:
                    norm = math.sqrt(sum(w * w for w in v))
                    pts.append([w / norm for w in v])
        _FRONT_CACHE[key] = pts
    return _FRONT_CACHE[key]


def igd(front, ref_set):
    """IGD：参考集中每个点到「找到的前沿」最近距离的平均值（越小越好；既衡量收敛也衡量铺开）。"""
    if not front:
        return float("inf")
    return sum(min(math.dist(r, f) for f in front) for r in ref_set) / len(ref_set)


def hypervolume(points, ref):
    """被 points 支配、且在参考点 ref 以内的体积（最小化；2 / 3 目标，维度扫描法）。"""
    pts = [p for p in points if all(p[d] < ref[d] for d in range(len(ref)))]
    if not pts:
        return 0.0
    m = len(ref)
    if m == 1:
        return ref[0] - min(p[0] for p in pts)
    if m == 2:
        pts.sort()
        vol, best_y = 0.0, ref[1]
        for x, y in pts:
            if y < best_y:
                vol += (ref[0] - x) * (best_y - y)
                best_y = y
        return vol
    pts.sort(key=lambda p: p[-1])  # 按最后一维升序切片
    vol = 0.0
    for i, p in enumerate(pts):
        nxt = pts[i + 1][-1] if i + 1 < len(pts) else ref[-1]
        if nxt > p[-1]:
            vol += hypervolume([q[:-1] for q in pts[: i + 1]], ref[:-1]) * (nxt - p[-1])
    return vol


# ------------------------------------------------------------------ 非支配排序与算子（最小化）

def nd_sort(F):
    n = len(F)
    S = [[] for _ in range(n)]
    cnt = [0] * n
    fronts = [[]]
    rank = [0] * n
    for i in range(n):
        for j in range(i + 1, n):
            a, b = F[i], F[j]
            ab = all(a[d] <= b[d] for d in range(len(a))) and a != b
            ba = all(b[d] <= a[d] for d in range(len(a))) and a != b
            if ab:
                S[i].append(j)
                cnt[j] += 1
            elif ba:
                S[j].append(i)
                cnt[i] += 1
    fronts[0] = [i for i in range(n) if cnt[i] == 0]
    k = 0
    while fronts[k]:
        nxt = []
        for i in fronts[k]:
            for j in S[i]:
                cnt[j] -= 1
                if cnt[j] == 0:
                    rank[j] = k + 1
                    nxt.append(j)
        k += 1
        fronts.append(nxt)
    return rank, [f for f in fronts if f]


def crowding(F, idxs):
    if len(idxs) <= 2:
        return {i: float("inf") for i in idxs}
    dist = {i: 0.0 for i in idxs}
    for d in range(len(F[0])):
        order = sorted(idxs, key=lambda i: F[i][d])
        dist[order[0]] = dist[order[-1]] = float("inf")
        span = F[order[-1]][d] - F[order[0]][d]
        if span <= 0:
            continue
        for k in range(1, len(order) - 1):
            dist[order[k]] += (F[order[k + 1]][d] - F[order[k - 1]][d]) / span
    return dist


def sbx(p1, p2, bounds, rng, eta=15.0, pc=0.9):
    """模拟二进制交叉（Deb & Agrawal 1995）。"""
    c1, c2 = list(p1), list(p2)
    if rng.random() > pc:
        return c1, c2
    for i, (lo, hi) in enumerate(bounds):
        if rng.random() > 0.5 or abs(p1[i] - p2[i]) < 1e-14:
            continue
        a, b = min(p1[i], p2[i]), max(p1[i], p2[i])
        u = rng.random()
        beta = 1.0 + 2.0 * (a - lo) / (b - a)
        alpha = 2.0 - beta ** -(eta + 1.0)
        bq = (u * alpha) ** (1.0 / (eta + 1.0)) if u <= 1.0 / alpha else (1.0 / (2.0 - u * alpha)) ** (1.0 / (eta + 1.0))
        x1 = 0.5 * ((a + b) - bq * (b - a))
        beta = 1.0 + 2.0 * (hi - b) / (b - a)
        alpha = 2.0 - beta ** -(eta + 1.0)
        bq = (u * alpha) ** (1.0 / (eta + 1.0)) if u <= 1.0 / alpha else (1.0 / (2.0 - u * alpha)) ** (1.0 / (eta + 1.0))
        x2 = 0.5 * ((a + b) + bq * (b - a))
        x1, x2 = min(hi, max(lo, x1)), min(hi, max(lo, x2))
        if rng.random() < 0.5:
            x1, x2 = x2, x1
        c1[i], c2[i] = x1, x2
    return c1, c2


def poly_mutate(x, bounds, rng, eta=20.0, pm=None):
    """多项式变异（Deb & Goyal 1996）。"""
    n = len(x)
    pm = 1.0 / n if pm is None else pm
    y = list(x)
    for i, (lo, hi) in enumerate(bounds):
        if rng.random() >= pm:
            continue
        u = rng.random()
        d1, d2 = (y[i] - lo) / (hi - lo), (hi - y[i]) / (hi - lo)
        if u < 0.5:
            dq = (2.0 * u + (1.0 - 2.0 * u) * (1.0 - d1) ** (eta + 1.0)) ** (1.0 / (eta + 1.0)) - 1.0
        else:
            dq = 1.0 - (2.0 * (1.0 - u) + 2.0 * (u - 0.5) * (1.0 - d2) ** (eta + 1.0)) ** (1.0 / (eta + 1.0))
        y[i] = min(hi, max(lo, y[i] + dq * (hi - lo)))
    return y


# ------------------------------------------------------------------ 状态

class _Tracker:
    def __init__(self, ctx):
        self.ctx = ctx
        self.ref_set = true_front(ctx.variant)
        self.hv_true = hypervolume(true_front(ctx.variant, 1500) if ctx.m == 2 else dense_front(ctx.variant), ctx.ref)
        self.best_igd = float("inf")

    def state(self, it, pop_F, pop_X):
        ctx = self.ctx
        _r, fronts = nd_sort(pop_F)
        order = sorted(fronts[0], key=lambda i: pop_F[i])
        front = [pop_F[i] for i in order]
        cur = igd(front, self.ref_set)
        self.best_igd = min(self.best_igd, cur)
        hv = hypervolume(front, ctx.ref)
        return {"iter": it, "pop": [list(f) for f in pop_F], "front": [list(f) for f in front],
                "front_x": [list(pop_X[i]) for i in order], "nd": len(front),
                "igd": round(cur, 6), "hv": round(hv, 6), "hv_ratio": round(hv / self.hv_true, 4) if self.hv_true else 0.0,
                "best": round(self.best_igd, 6), "cur": round(cur, 6)}


# ------------------------------------------------------------------ 算法

def _mc_random(ctx, p, rng):
    """随机基线：每代抽一批随机解，只保留非支配的档案。"""
    tr = _Tracker(ctx)
    arch, arch_x = [], []
    for it in range(1, p["max_iter"] + 1):
        new_x = [ctx.random(rng) for _ in range(p["n_pop"])]
        new = [ctx.f(x) for x in new_x]
        cand, cand_x = arch + new, arch_x + new_x
        _r, fr = nd_sort(cand)
        arch, arch_x = [cand[i] for i in fr[0]], [cand_x[i] for i in fr[0]]
        if len(arch) > 2 * p["n_pop"]:
            arch, arch_x = arch[:: 2], arch_x[:: 2]
        yield tr.state(it, arch + new, arch_x + new_x)


def _mc_wsga(ctx, p, rng):
    """加权和 GA（对照）：每代随机权重把多目标压成一个数，再做单目标选择。
    经典弱点：种群被拉向权重方向上的某一点，铺不开前沿；非凸前沿段用任何权重都够不到。"""
    tr = _Tracker(ctx)
    n_pop = p["n_pop"]
    pop = [ctx.random(rng) for _ in range(n_pop)]
    F = [ctx.f(x) for x in pop]
    for it in range(1, p["max_iter"] + 1):
        w = [rng.random() for _ in range(ctx.m)]
        s = sum(w) or 1.0
        w = [v / s for v in w]
        sc = [sum(w[d] * f[d] for d in range(ctx.m)) for f in F]
        new = [list(pop[min(range(n_pop), key=sc.__getitem__)])]
        while len(new) < n_pop:
            a = min(rng.sample(range(n_pop), 2), key=sc.__getitem__)
            b = min(rng.sample(range(n_pop), 2), key=sc.__getitem__)
            c1, _c2 = ctx.cross(pop[a], pop[b], rng)
            new.append(ctx.mutate(c1, rng))
        pop = new
        F = [ctx.f(x) for x in pop]
        yield tr.state(it, F, pop)


def _mc_nsga2(ctx, p, rng):
    """NSGA-II（Deb et al. 2002）：非支配排序 + 拥挤度 + 精英保留；实数编码用 SBX + 多项式变异。"""
    tr = _Tracker(ctx)
    n_pop = p["n_pop"]
    pop = [ctx.random(rng) for _ in range(n_pop)]
    F = [ctx.f(x) for x in pop]
    rank, fronts = nd_sort(F)
    cd = {}
    for fr in fronts:
        cd.update(crowding(F, fr))

    def tour():
        a, b = rng.sample(range(n_pop), 2)
        if rank[a] != rank[b]:
            return pop[a] if rank[a] < rank[b] else pop[b]
        return pop[a] if cd[a] >= cd[b] else pop[b]

    for it in range(1, p["max_iter"] + 1):
        kids = []
        while len(kids) < n_pop:
            c1, c2 = ctx.cross(tour(), tour(), rng)
            kids += [ctx.mutate(c1, rng), ctx.mutate(c2, rng)]
        kids = kids[:n_pop]
        KF = [ctx.f(x) for x in kids]
        union, UF = pop + kids, F + KF
        _ur, ufronts = nd_sort(UF)
        sel = []
        for fr in ufronts:
            if len(sel) + len(fr) <= n_pop:
                sel += fr
            else:
                c = crowding(UF, fr)
                sel += sorted(fr, key=lambda i: c[i], reverse=True)[: n_pop - len(sel)]
                break
        pop, F = [union[i] for i in sel], [UF[i] for i in sel]
        rank, fronts = nd_sort(F)
        cd = {}
        for fr in fronts:
            cd.update(crowding(F, fr))
        yield tr.state(it, F, pop)


def _mc_moead(ctx, p, rng):
    """MOEA/D-DE（Li & Zhang 2009）：把多目标拆成 N 个 Tchebycheff 单目标子问题，每个子问题只与权重相近的邻居交配；
    变异 = 差分 + 多项式变异（位串编码的 ZDT5 没有差分，改用均匀交叉 + 逐位翻转）。"""
    tr = _Tracker(ctx)
    m = ctx.m
    if m == 2:
        n_pop = p["n_pop"]
        W = [[i / (n_pop - 1), 1.0 - i / (n_pop - 1)] for i in range(n_pop)]
    else:
        h = 1
        while len(das_dennis(m, h + 1)) <= p["n_pop"]:
            h += 1
        W = das_dennis(m, h)
        n_pop = len(W)
    W = [[max(v, 1e-6) for v in w] for w in W]
    T = max(3, n_pop // 5)
    nb = [sorted(range(n_pop), key=lambda j: math.dist(W[i], W[j]))[:T] for i in range(n_pop)]
    pop = [ctx.random(rng) for _ in range(n_pop)]
    F = [ctx.f(x) for x in pop]
    z = [min(f[d] for f in F) for d in range(m)]

    def g(f, w):
        return max(w[d] * abs(f[d] - z[d]) / ctx.scale[d] for d in range(m))

    for it in range(1, p["max_iter"] + 1):
        for i in rng.sample(range(n_pop), n_pop):
            pool = nb[i] if rng.random() < 0.9 else list(range(n_pop))
            r1, r2, r3 = rng.sample(pool, 3) if len(pool) >= 3 else (i, i, i)
            child = ctx.mutate(ctx.vary3(pop[r1], pop[r2], pop[r3], rng), rng)
            cf = ctx.f(child)
            z = [min(z[d], cf[d]) for d in range(m)]
            replaced = 0
            for j in rng.sample(pool, len(pool)):
                if g(cf, W[j]) <= g(F[j], W[j]):
                    pop[j], F[j] = child, cf
                    replaced += 1
                    if replaced >= 2:
                        break
        yield tr.state(it, F, pop)


def _pref_point(ctx):
    """偏好范式用的参考点（愿望点）：理想点向真前沿「正中」那个点方向走 85%——略好于前沿、不可达，是 R-NSGA-II 论文里常见的设法。"""
    pts = true_front(ctx.variant)
    m = ctx.m
    ideal = [min(p[d] for p in pts) for d in range(m)]
    sc = ctx.scale
    cen = [sum(p[d] for p in pts) / len(pts) for d in range(m)]
    mid = min(pts, key=lambda p: sum(((p[d] - cen[d]) / sc[d]) ** 2 for d in range(m)))
    return [ideal[d] + 0.85 * (mid[d] - ideal[d]) for d in range(m)]


def _mc_ibea(ctx, p, rng):
    """IBEA（Zitzler & Künzli 2004）：用加性 ε 指标直接当适应度——F(x) = Σ_{y≠x} −exp(−I(y,x)/(c·κ))，
    环境选择反复删掉适应度最差者并更新其余个体的适应度；不用支配排序，也不用拥挤度。"""
    tr = _Tracker(ctx)
    n, m, sc, kappa = p["n_pop"], ctx.m, ctx.scale, 0.05
    pop = [ctx.random(rng) for _ in range(n)]
    F = [ctx.f(x) for x in pop]

    def eps_matrix(Fs):
        k = len(Fs)
        return [[max((Fs[i][d] - Fs[j][d]) / sc[d] for d in range(m)) for j in range(k)] for i in range(k)]

    def fitness(I, alive):
        c = max((abs(I[i][j]) for i in alive for j in alive if i != j), default=1.0) or 1.0
        return c, {i: sum(-math.exp(-I[j][i] / (c * kappa)) for j in alive if j != i) for i in alive}

    _c, fit = fitness(eps_matrix(F), list(range(n)))

    for it in range(1, p["max_iter"] + 1):
        ids = list(range(n))

        def tour():
            a, b = rng.sample(ids, 2)
            return pop[a] if fit[a] >= fit[b] else pop[b]
        kids = []
        while len(kids) < n:
            c1, c2 = ctx.cross(tour(), tour(), rng)
            kids += [ctx.mutate(c1, rng), ctx.mutate(c2, rng)]
        kids = kids[:n]
        union, UF = pop + kids, F + [ctx.f(x) for x in kids]
        I = eps_matrix(UF)
        alive = list(range(len(union)))
        c, ufit = fitness(I, alive)
        while len(alive) > n:
            worst = min(alive, key=lambda i: ufit[i])
            alive.remove(worst)
            for i in alive:
                ufit[i] += math.exp(-I[worst][i] / (c * kappa))
        pop, F = [union[i] for i in alive], [UF[i] for i in alive]
        fit = {k: ufit[i] for k, i in enumerate(alive)}
        yield tr.state(it, F, pop)


def _mc_rnsga2(ctx, p, rng):
    """R-NSGA-II（Deb et al. 2006）简化版：NSGA-II 的骨架，但同一前沿内用「到参考点的距离」代替拥挤度，
    并用 ε-清除避免种群塌成一个点。只追求参考点附近的那一段前沿——所以 IGD（衡量整条前沿）偏大是预期的。"""
    tr = _Tracker(ctx)
    n, m, sc = p["n_pop"], ctx.m, ctx.scale
    ref = _pref_point(ctx)
    eps = 0.02

    def dist(f):
        return math.sqrt(sum(((f[d] - ref[d]) / sc[d]) ** 2 for d in range(m)))

    def clear_order(Fs, ids):
        rest = sorted(ids, key=lambda i: dist(Fs[i]))
        out, later = [], []
        while rest:
            a = rest.pop(0)
            out.append(a)
            keep = []
            for b in rest:
                if math.sqrt(sum(((Fs[a][d] - Fs[b][d]) / sc[d]) ** 2 for d in range(m))) < eps:
                    later.append(b)
                else:
                    keep.append(b)
            rest = keep
        return out + sorted(later, key=lambda i: dist(Fs[i]))

    pop = [ctx.random(rng) for _ in range(n)]
    F = [ctx.f(x) for x in pop]
    rank, _fr = nd_sort(F)

    def emit(it):
        s = tr.state(it, F, pop)
        s["pref"] = [round(v, 6) for v in ref]
        s["pref_dist"] = round(min(dist(f) for f in s["front"]), 6)
        return s

    for it in range(1, p["max_iter"] + 1):
        def tour():
            a, b = rng.sample(range(n), 2)
            if rank[a] != rank[b]:
                return pop[a] if rank[a] < rank[b] else pop[b]
            return pop[a] if dist(F[a]) <= dist(F[b]) else pop[b]
        kids = []
        while len(kids) < n:
            c1, c2 = ctx.cross(tour(), tour(), rng)
            kids += [ctx.mutate(c1, rng), ctx.mutate(c2, rng)]
        kids = kids[:n]
        union, UF = pop + kids, F + [ctx.f(x) for x in kids]
        _ur, ufronts = nd_sort(UF)
        sel = []
        for fr in ufronts:
            if len(sel) + len(fr) <= n:
                sel += fr
            else:
                sel += clear_order(UF, fr)[: n - len(sel)]
                break
        pop, F = [union[i] for i in sel], [UF[i] for i in sel]
        rank, _fr = nd_sort(F)
        yield emit(it)


MOC_ALGOS = {
    "random": {"fn": _mc_random, "name": "随机搜索", "category": "基线", "desc": "盲采样 + 非支配档案：所有算法都要显著优于它", "tune": []},
    "wsga": {"fn": _mc_wsga, "name": "加权和 GA", "category": "进化计算", "desc": "每代随机权重合成单目标（对照：铺不开前沿、漏非凸段）", "tune": []},
    "nsga2": {"fn": _mc_nsga2, "name": "NSGA-II", "category": "进化计算", "desc": "非支配排序 + 拥挤度，SBX + 多项式变异（Deb 2002）", "tune": []},
    "moead": {"fn": _mc_moead, "name": "MOEA/D", "category": "进化计算", "desc": "Tchebycheff 分解 + 邻域差分（Li & Zhang 2009）", "tune": []},
    "ibea": {"fn": _mc_ibea, "name": "IBEA", "category": "进化计算", "desc": "指标法：加性 ε 指标直接当适应度，不用支配排序（Zitzler & Künzli 2004）", "tune": []},
    "rnsga2": {"fn": _mc_rnsga2, "name": "R-NSGA-II", "category": "进化计算", "desc": "偏好法：给定参考点，同一前沿内按到参考点的距离选择（Deb 等 2006 简化版）；图上的菱形是参考点", "tune": []},
}
MOC_DEF = {"n_pop": 60, "max_iter": 300, "seed": 7}

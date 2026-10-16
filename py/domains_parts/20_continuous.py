# ============================================================
# 域二：连续函数基准（实数编码——PSO/DE/GWO/WOA/SCA 的原生域）
# ============================================================

def _fn_sphere(x):
    return sum(v * v for v in x)


def _fn_rosenbrock(x):
    return sum(100 * (x[i + 1] - x[i] * x[i]) ** 2 + (1 - x[i]) ** 2 for i in range(len(x) - 1))


def _fn_rastrigin(x):
    return 10 * len(x) + sum(v * v - 10 * math.cos(2 * math.pi * v) for v in x)


def _fn_ackley(x):
    n = len(x)
    s1 = sum(v * v for v in x) / n
    s2 = sum(math.cos(2 * math.pi * v) for v in x) / n
    return -20 * math.exp(-0.2 * math.sqrt(s1)) - math.exp(s2) + 20 + math.e


FUNCS = {"sphere": (_fn_sphere, -5.0, 5.0, 0.0),
         "rosenbrock": (_fn_rosenbrock, -2.2, 2.2, 0.0),
         "rastrigin": (_fn_rastrigin, -5.0, 5.0, 0.0),
         "ackley": (_fn_ackley, -5.0, 5.0, 0.0)}


# ============================================================
# H3 期：BBOB 基准套件（COCO, Hansen et al. 2009）子集接入 continuous 域。
# 仅追加、零修改 FUNCS 字面量——下方 FUNCS.update 注入。选入 6 个无噪可分函数：
# f1 球（同 sphere）、f2 椭球（条件数 1e6）、f3 雪茄、f4 铁饼、f5 异次幂、
# f6 尖脊。全部在原点取最优 0、定义域 [-5,5]^d，与既有连续函数口径一致。
# 编号说明：f1/f2 与 COCO 官方编号一致；f3-f6 为本站教学序，取的是 BBOB
# 套件真实函数（Bent Cigar/Discus/Different Powers/Sharp Ridge），但非 COCO
# 官方 f3-f6（separable Rastrigin/Büche-Rastrigin/Linear Slope/Attractive Sector）。
# ============================================================

def _fn_bbob_f1(x):
    return sum(v * v for v in x)


def _fn_bbob_f2(x):
    d = len(x)
    if d <= 1:
        return x[0] * x[0]
    return sum((10 ** (6.0 * i / (d - 1))) * x[i] * x[i] for i in range(d))


def _fn_bbob_f3(x):  # 雪茄
    return x[0] * x[0] + 10 ** 6 * sum(v * v for v in x[1:])


def _fn_bbob_f4(x):  # 铁饼
    return 10 ** 6 * x[0] * x[0] + sum(v * v for v in x[1:])


def _fn_bbob_f5(x):  # 异次幂
    d = len(x)
    if d <= 1:
        return x[0] * x[0]
    return sum(abs(x[i]) ** (2 + 4.0 * i / (d - 1)) for i in range(d))


def _fn_bbob_f6(x):  # 尖脊
    return x[0] * x[0] + 100.0 * math.sqrt(sum(v * v for v in x[1:]))


# ------------------------------------------------------------------
# 2026-10 补充的经典连续基准（Jamil & Yang 2013 的全局优化测试函数目录里的标准定义）。
# 都平移 / 书写成「最优值 = 0」，与既有函数同口径；搜索范围取文献里的通用范围。
#   griewank       [-600,600]  多峰，峰谷规则、维度越高越平缓
#   levy           [-10,10]    多峰，最优在 (1,…,1) 而不在原点
#   schwefel       [-500,500]  欺骗性：次优解离最优解极远（最优在 420.9687 附近，靠近边界）
#   zakharov       [-5,10]     单峰，变量之间有耦合
#   dixon_price    [-10,10]    单峰、谷形，最优点各维不同
#   styblinski_tang [-5,5]     多峰，每一维有两个谷（加常数 39.16617·d 使最优为 0）
# ------------------------------------------------------------------

def _fn_griewank(x):
    return 1.0 + sum(v * v for v in x) / 4000.0 - math.prod(math.cos(v / math.sqrt(i + 1)) for i, v in enumerate(x))


def _fn_levy(x):
    w = [1.0 + (v - 1.0) / 4.0 for v in x]
    s = math.sin(math.pi * w[0]) ** 2
    s += sum((w[i] - 1.0) ** 2 * (1.0 + 10.0 * math.sin(math.pi * w[i] + 1.0) ** 2) for i in range(len(w) - 1))
    s += (w[-1] - 1.0) ** 2 * (1.0 + math.sin(2.0 * math.pi * w[-1]) ** 2)
    return s


def _fn_schwefel(x):
    return 418.9828872724338 * len(x) - sum(v * math.sin(math.sqrt(abs(v))) for v in x)


def _fn_zakharov(x):
    s = sum(0.5 * (i + 1) * v for i, v in enumerate(x))
    return sum(v * v for v in x) + s ** 2 + s ** 4


def _fn_dixon_price(x):
    return (x[0] - 1.0) ** 2 + sum((i + 1) * (2.0 * x[i] ** 2 - x[i - 1]) ** 2 for i in range(1, len(x)))


def _fn_styblinski_tang(x):
    return 0.5 * sum(v ** 4 - 16.0 * v * v + 5.0 * v for v in x) + 39.16616570377142 * len(x)


_NEW_FUNCS = {"griewank": (_fn_griewank, -600.0, 600.0, 0.0),
              "levy": (_fn_levy, -10.0, 10.0, 0.0),
              "schwefel": (_fn_schwefel, -500.0, 500.0, 0.0),
              "zakharov": (_fn_zakharov, -5.0, 10.0, 0.0),
              "dixon_price": (_fn_dixon_price, -10.0, 10.0, 0.0),
              "styblinski_tang": (_fn_styblinski_tang, -5.0, 5.0, 0.0)}

FUNCS.update({
    "bbob_f1": (_fn_bbob_f1, -5.0, 5.0, 0.0),
    "bbob_f2": (_fn_bbob_f2, -5.0, 5.0, 0.0),
    "bbob_f3": (_fn_bbob_f3, -5.0, 5.0, 0.0),
    "bbob_f4": (_fn_bbob_f4, -5.0, 5.0, 0.0),
    "bbob_f5": (_fn_bbob_f5, -5.0, 5.0, 0.0),
    "bbob_f6": (_fn_bbob_f6, -5.0, 5.0, 0.0),
})
FUNCS.update(_NEW_FUNCS)


def cn_make(fn="rastrigin", dim=2, seed=7):
    f, lo, hi, opt = FUNCS[fn]
    return {"fn": fn, "dim": dim, "lo": lo, "hi": hi, "optimum": opt}


class _CN:
    def __init__(self, problem):
        self.f, self.lo, self.hi, _ = FUNCS[problem["fn"]]
        self.dim = problem["dim"]

    def random(self, rng):
        return [rng.uniform(self.lo, self.hi) for _ in range(self.dim)]

    def eval(self, x):
        return self.f(x)

    def clamp(self, x):
        return [min(self.hi, max(self.lo, v)) for v in x]

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(p["n_pop"])]
        return pop, [self.eval(x) for x in pop]


def _cn_state(ctx, it, best, bpos, pop, vals):
    return {"iter": it, "best": best, "gbest_pos": list(bpos[:2]), "best_sol": list(bpos),
            "particles": [list(x[:2]) for x in pop], "cur": sum(vals) / len(vals)}


def _sym_eig(A, dim, n_rot=100):
    """对称矩阵 Jacobi 特征分解：返回 (特征值列表, 特征向量阵 B)。

    B 的列是特征向量，满足 A ≈ B·diag(λ)·Bᵀ。用于 CMA-ES 协方差采样
    （C^{1/2}=B·diag(√λ)·Bᵀ、C^{-1/2}=B·diag(1/√λ)·Bᵀ）。连续域 dim≤~20，
    每代一次足够快；收敛阈值 1e-12，封顶 n_rot 次旋转保底。
    """
    a = [row[:] for row in A]
    V = [[1.0 if i == j else 0.0 for j in range(dim)] for i in range(dim)]
    for _ in range(n_rot):
        p, q, mx = 0, 1, 0.0
        for i in range(dim):
            for j in range(i + 1, dim):
                if abs(a[i][j]) > mx:
                    mx = abs(a[i][j]); p, q = i, j
        if mx < 1e-12:
            break
        app, aqq, apq = a[p][p], a[q][q], a[p][q]
        th = math.pi / 4 if app == aqq else 0.5 * math.atan2(2.0 * apq, aqq - app)
        c, s = math.cos(th), math.sin(th)
        for i in range(dim):
            if i != p and i != q:
                aip, aiq = a[i][p], a[i][q]
                a[i][p] = c * aip - s * aiq
                a[i][q] = s * aip + c * aiq
                a[p][i] = a[i][p]
                a[q][i] = a[i][q]
        a[p][p] = c * c * app - 2.0 * c * s * apq + s * s * aqq
        a[q][q] = s * s * app + 2.0 * c * s * apq + c * c * aqq
        a[p][q] = 0.0
        a[q][p] = 0.0
        for i in range(dim):
            vip, viq = V[i][p], V[i][q]
            V[i][p] = c * vip - s * viq
            V[i][q] = s * vip + c * viq
    return [a[i][i] for i in range(dim)], V


def _cn_random(ctx, p, rng):
    pop, vals = ctx.init_pop(p, rng)
    bi = argbest(vals, "min")
    best, bpos = vals[bi], list(pop[bi])
    for it in range(1, p["max_iter"] + 1):
        for i in range(p["n_pop"]):
            pop[i] = ctx.random(rng)
            vals[i] = ctx.eval(pop[i])
            best, bpos = bump(best, bpos, vals[i], pop[i], "min")
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_hc(ctx, p, rng):
    x = ctx.random(rng)
    best = ctx.eval(x)
    bpos = list(x)
    sigma = p["sigma"]
    stall = 0
    for it in range(1, p["max_iter"] + 1):
        cand = ctx.clamp([v + rng.gauss(0, sigma) for v in x])
        c = ctx.eval(cand)
        if c <= ctx.eval(x):
            x = cand
        if c < best:
            best, bpos = c, list(cand)
            stall = 0
        else:
            stall += 1
        # 多起点重启：爬山法困在局部谷时，在历史最优附近随机重撒——
        # 若原样回到 bpos，贪心下降会沿同一轨迹落回同一个谷（实测教训）
        if stall >= p["restart_at"]:
            x = ctx.clamp([b + rng.gauss(0, 0.8) for b in bpos])
            sigma = max(p["sigma"], 0.4)
            stall = 0
        sigma *= 0.995
        yield {"iter": it, "best": best, "gbest_pos": list(bpos[:2]), "best_sol": list(bpos),
               "particles": [list(x[:2])], "cur": ctx.eval(x)}


def _cn_sa(ctx, p, rng):
    x = ctx.random(rng)
    v = ctx.eval(x)
    best, bpos = v, list(x)
    t0, decay = p["t0"], p["decay"]
    span = ctx.hi - ctx.lo
    stall = 0
    boost = 0.0  # 重启时的步长加热（与接受温度解耦——教训：二者耦合会让收尾变粗糙）
    for it in range(1, p["max_iter"] + 1):
        T = t0 * (decay ** it)
        width = 0.1 * span * max(1.0 - it / p["max_iter"], 0.02) * (1.0 + boost)
        cand = ctx.clamp([b + rng.gauss(0, width) for b in x])
        v2 = ctx.eval(cand)
        d = v2 - v
        if d < 0 or (T > 1e-12 and rng.random() < math.exp(-d / T)):
            x, v = cand, v2
        if v < best:
            best, bpos = v, list(x)
            stall = 0
        else:
            stall += 1
        # 重启策略（SA 工程化标准组件）：长期无改进就回到历史最优并重新加热步长，
        # 避免单链在多峰地形（Rastrigin 类）里永久困死
        if stall >= p["restart_at"]:
            x = list(bpos)
            v = best
            boost = 1.0
            stall = 0
        boost *= 0.9
        yield {"iter": it, "best": best, "gbest_pos": list(bpos[:2]), "best_sol": list(bpos),
               "particles": [list(x[:2])], "cur": v}


def _cn_pso(ctx, p, rng):
    pop, vals = ctx.init_pop(p, rng)
    vel = [[rng.uniform(-0.5, 0.5) * (ctx.hi - ctx.lo) * 0.1 for _ in range(ctx.dim)] for _ in range(p["n_pop"])]
    pbest = [list(x) for x in pop]
    pv = list(vals)
    bi = argbest(vals, "min")
    best, bpos = vals[bi], list(pop[bi])
    for it in range(1, p["max_iter"] + 1):
        w = p["w_max"] - (p["w_max"] - p["w_min"]) * it / p["max_iter"]
        for i in range(p["n_pop"]):
            for d in range(ctx.dim):
                r1, r2 = rng.random(), rng.random()
                vel[i][d] = (w * vel[i][d] + p["c1"] * r1 * (pbest[i][d] - pop[i][d])
                             + p["c2"] * r2 * (bpos[d] - pop[i][d]))
                vel[i][d] = max(-1.0, min(1.0, vel[i][d])) * (ctx.hi - ctx.lo) * 0.2
            pop[i] = ctx.clamp([pop[i][d] + vel[i][d] for d in range(ctx.dim)])
            vals[i] = ctx.eval(pop[i])
            if vals[i] < pv[i]:
                pbest[i], pv[i] = list(pop[i]), vals[i]
                best, bpos = bump(best, bpos, vals[i], pop[i], "min")
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_de(ctx, p, rng):
    pop, vals = ctx.init_pop(p, rng)
    bi = argbest(vals, "min")
    best, bpos = vals[bi], list(pop[bi])
    for it in range(1, p["max_iter"] + 1):
        for i in range(p["n_pop"]):
            r1, r2, r3 = rng.sample([j for j in range(p["n_pop"]) if j != i], 3)
            F = p["F"] * (0.5 + rng.random())
            mutant = [pop[r1][d] + F * (pop[r2][d] - pop[r3][d]) for d in range(ctx.dim)]
            trial = [mutant[d] if rng.random() < p["CR"] else pop[i][d] for d in range(ctx.dim)]
            trial = ctx.clamp(trial)
            v = ctx.eval(trial)
            if v <= vals[i]:
                pop[i], vals[i] = trial, v
                best, bpos = bump(best, bpos, v, trial, "min")
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_gwo(ctx, p, rng):
    pop, vals = ctx.init_pop(p, rng)
    order = sorted(range(p["n_pop"]), key=lambda i: vals[i])
    al, be, de = list(pop[order[0]]), list(pop[order[1]]), list(pop[order[2]])
    best, bpos = vals[order[0]], list(pop[order[0]])
    for it in range(1, p["max_iter"] + 1):
        a = 2.0 * (1 - it / p["max_iter"])
        for i in range(p["n_pop"]):
            # 标准 GWO：Xi = Xleader - A·|C·Xleader - X|，A/C 都是随机系数向量
            def _upd(leader):
                A = a * (2 * rng.random() - 1)
                C = 2 * rng.random()
                return [leader[d] - A * abs(C * leader[d] - pop[i][d]) for d in range(ctx.dim)]
            x1, x2, x3 = _upd(al), _upd(be), _upd(de)
            pop[i] = ctx.clamp([(x1[d] + x2[d] + x3[d]) / 3 for d in range(ctx.dim)])
            vals[i] = ctx.eval(pop[i])
            best, bpos = bump(best, bpos, vals[i], pop[i], "min")
        order = sorted(range(p["n_pop"]), key=lambda i: vals[i])
        al, be, de = list(pop[order[0]]), list(pop[order[1]]), list(pop[order[2]])
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_woa(ctx, p, rng):
    pop, vals = ctx.init_pop(p, rng)
    bi = argbest(vals, "min")
    best, bpos = vals[bi], list(pop[bi])
    for it in range(1, p["max_iter"] + 1):
        a = 2.0 * (1 - it / p["max_iter"])
        for i in range(p["n_pop"]):
            r1, r2 = rng.random(), rng.random()
            A = 2 * a * r1 - a
            C = 2 * r2
            if rng.random() < 0.5:
                if abs(A) < 1:  # 包围猎物
                    cand = [bpos[d] - A * abs(C * bpos[d] - pop[i][d]) for d in range(ctx.dim)]
                else:  # 搜索猎物
                    rand = pop[rng.randrange(p["n_pop"])]
                    cand = [rand[d] - A * abs(C * rand[d] - pop[i][d]) for d in range(ctx.dim)]
            else:  # 螺旋更新
                b, l = 1.0, rng.uniform(-1, 1)
                cand = [bpos[d] + math.exp(b * l) * math.cos(2 * math.pi * l)
                        * abs(bpos[d] - pop[i][d]) for d in range(ctx.dim)]
            pop[i] = ctx.clamp(cand)
            vals[i] = ctx.eval(pop[i])
            best, bpos = bump(best, bpos, vals[i], pop[i], "min")
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_sca(ctx, p, rng):
    pop, vals = ctx.init_pop(p, rng)
    bi = argbest(vals, "min")
    best, bpos = vals[bi], list(pop[bi])
    for it in range(1, p["max_iter"] + 1):
        r1 = p["a_max"] - (p["a_max"]) * it / p["max_iter"]
        for i in range(p["n_pop"]):
            r2, r3, r4 = 2 * math.pi * rng.random(), rng.random(), rng.random()
            step = r1 * math.sin(r2) if r4 < 0.5 else r1 * math.cos(r2)
            pop[i] = ctx.clamp([pop[i][d] + step * abs(r3 * bpos[d] - pop[i][d]) for d in range(ctx.dim)])
            vals[i] = ctx.eval(pop[i])
            best, bpos = bump(best, bpos, vals[i], pop[i], "min")
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_cmaes(ctx, p, rng):
    """CMA-ES（Hansen & Ostermeier 2001）：连续域 SOTA 级演化策略——本站主场。

    全协方差矩阵自适应 + 步长 σ 自适应 + 进化路径 pc/ps 全套标准 (μ,λ)-CMA-ES：
      每代对协方差 C 做 Jacobi 特征分解 → B·diag(√λ)·Bᵀ 采样；
      选 μ 个精英更新均值、pc、ps、C、σ（秩一 + 秩μ 协方差更新）。
    与 TSP 侧 separable 版不同，这里是**全协方差**（连续域 dim 小，特征分解不重），
    正是 CMA-ES 相对 EDA / sep-CMA 的招牌能力：自动学习地形条件数。
    """
    dim = ctx.dim
    n_pop = int(p["n_pop"])
    mu = max(1, n_pop // 2)
    weights = [math.log(mu + 0.5) - math.log(i + 1) for i in range(mu)]
    wsum = sum(weights)
    weights = [w / wsum for w in weights]
    mueff = (sum(weights)) ** 2 / sum(w * w for w in weights)
    cc = 4.0 / (dim + 4.0)
    cs = (mueff + 2.0) / (dim + mueff + 3.0)
    c1 = 2.0 / ((dim + 1.3) ** 2 + mueff)
    cmu = min(1.0 - c1, 2.0 * (mueff - 2.0 + 1.0 / mueff) / ((dim + 2.0) ** 2 + mueff))
    damps = 1.0 + 2.0 * max(0.0, math.sqrt((mueff - 1.0) / (dim + 1.0)) - 1.0) + cs
    chiN = math.sqrt(dim) * (1.0 - 1.0 / (4.0 * dim) + 1.0 / (21.0 * dim ** 2))

    span = ctx.hi - ctx.lo
    m = ctx.random(rng)
    sigma = span / 3.0
    C = [[1.0 if i == j else 0.0 for j in range(dim)] for i in range(dim)]
    pc = [0.0] * dim
    ps = [0.0] * dim
    best = float("inf")
    bpos = list(m)
    eigvals, B = _sym_eig(C, dim)

    for it in range(1, p["max_iter"] + 1):
        sq = [math.sqrt(max(eigvals[i], 1e-14)) for i in range(dim)]
        invsq = [1.0 / sq[i] for i in range(dim)]
        pop, vals = [], []
        for _k in range(n_pop):
            z = [rng.gauss(0.0, 1.0) for _ in range(dim)]
            # y = B·(√λ·(Bᵀ z))
            vtz = [sum(B[p][i] * z[p] for p in range(dim)) for i in range(dim)]
            w = [sq[i] * vtz[i] for i in range(dim)]
            y = [sum(B[i][p] * w[p] for p in range(dim)) for i in range(dim)]
            x = [m[d] + sigma * y[d] for d in range(dim)]
            # 边界处理：评价与上报用投影回搜索范围的点 xe；协方差 / 均值的更新仍用未投影的 x（标准做法）。
            # 此前直接在范围外评价——Schwefel 这类范围外函数值更低的函数上，「最优」跑到了范围外（-1e13）
            xe = ctx.clamp(x)
            v = ctx.eval(xe)
            pop.append(x); vals.append(v)
            best, bpos = bump(best, bpos, v, xe, "min")
        order = sorted(range(n_pop), key=lambda i: vals[i])
        sel = order[:mu]
        old_m = m
        m = [sum(weights[i] * pop[sel[i]][d] for i in range(mu)) for d in range(dim)]
        ymean = [(m[d] - old_m[d]) / sigma for d in range(dim)]
        # 步长路径 ps 用 C^{-1/2}
        vtc = [sum(B[p][i] * ymean[p] for p in range(dim)) for i in range(dim)]
        w2 = [invsq[i] * vtc[i] for i in range(dim)]
        cinv = [sum(B[i][p] * w2[p] for p in range(dim)) for i in range(dim)]
        ps = [(1 - cs) * ps[d] + math.sqrt(cs * (2 - cs) * mueff) * cinv[d] for d in range(dim)]
        hsig = (math.sqrt(sum(pp * pp for pp in ps)) /
                math.sqrt(1 - (1 - cs) ** (2 * it)) / chiN) < (1.4 + 2.0 / (dim + 1.0))
        pc = [(1 - cc) * pc[d] + hsig * math.sqrt(cc * (2 - cc) * mueff) * ymean[d] for d in range(dim)]
        ci = cmu  # Σweights = 1
        newC = [[0.0] * dim for _ in range(dim)]
        for d1 in range(dim):
            for d2 in range(dim):
                newC[d1][d2] = (1 - c1 - ci) * C[d1][d2] + c1 * (pc[d1] * pc[d2] + hsig * (2 - hsig) * C[d1][d2])
        for i in range(mu):
            yi = [(pop[sel[i]][d] - old_m[d]) / sigma for d in range(dim)]
            wi = weights[i]
            for d1 in range(dim):
                for d2 in range(d1, dim):
                    newC[d1][d2] += cmu * wi * yi[d1] * yi[d2]
        for d1 in range(dim):
            for d2 in range(d1 + 1, dim):
                newC[d2][d1] = newC[d1][d2]
        C = newC
        sigma *= math.exp((cs / damps) * (math.sqrt(sum(pp * pp for pp in ps)) / chiN - 1.0))
        eigvals, B = _sym_eig(C, dim)
        cur = sum(vals) / n_pop
        yield _cn_state(ctx, it, best, bpos, [ctx.clamp(q) for q in pop], vals)



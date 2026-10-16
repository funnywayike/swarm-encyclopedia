# ============================================================
# 域三：双目标背包（多目标入门）
# ============================================================

def mo_make(variant="moco", n=40, seed=7):
    rng = random.Random(seed)
    items = []
    for _ in range(n):
        w = rng.randint(2, 60)
        v1 = rng.randint(10, 100)
        # ★ 两个收益必须独立（甚至部分负相关）：若 v2 由 v1 派生，前沿会退化成
        #   单点支配——教训来自首次实现，测试 test_multiobj_front_shape 看着它
        v2 = rng.randint(10, 100)
        if variant == "maop":
            # 三目标：再加一个独立收益 v3，三目标前沿需 NSGA-II 才能覆盖非凸面
            v3 = rng.randint(10, 100)
            items.append([w, v1, v2, v3])
        else:
            items.append([w, v1, v2])
    cap = int(sum(x[0] for x in items) * 0.45)
    return {"variant": variant, "n": n, "cap": cap, "items": items}


def _mo_spea2(ctx, p, rng):
    """SPEA2（Zitzler et al., 2001）：强度 Pareto + 密度截断（经典）。
    F(i)=R(i)+D(i)；R=支配者强度之和，D=1/(σ^k+2)，archive 超容量按最近邻迭代删除。"""
    n_pop, arc_cap = p["n_pop"], p["n_pop"]
    no = ctx.no
    pop = ctx.init_pop(p, rng)
    archive = []
    for it in range(1, p["max_iter"] + 1):
        union = list(pop) + list(archive)
        U = [ctx.fs(x)[:no] for x in union]
        n = len(union)
        dom = [[False] * n for _ in range(n)]
        for a in range(n):
            for b in range(n):
                if a != b and all(U[a][k] >= U[b][k] for k in range(no)) \
                        and any(U[a][k] > U[b][k] for k in range(no)):
                    dom[a][b] = True  # a 支配 b
        S = [sum(dom[a]) for a in range(n)]
        R = [sum(S[j] for j in range(n) if dom[j][i]) for i in range(n)]
        kth = int(n ** 0.5)  # 正典 k≈sqrt(n)（终审C #3 修正：原 sqrt(n+arc_cap) 偏大）
        dist = [[sum((U[a][k2] - U[b][k2]) ** 2 for k2 in range(no)) ** 0.5 for b in range(n)]
                for a in range(n)]
        Fit = []
        for i in range(n):
            dd = sorted(dist[i])[kth] if len(dist[i]) > kth else max(dist[i])
            Fit.append(R[i] + 1.0 / (dd + 2.0))
        nd_idx = [i for i in range(n) if Fit[i] < 1.0]
        if len(nd_idx) < arc_cap:
            rest = sorted((i for i in range(n) if Fit[i] >= 1.0), key=lambda i: Fit[i])
            keep = nd_idx + rest[:arc_cap - len(nd_idx)]
        else:
            keep = list(nd_idx)
            while len(keep) > arc_cap:  # 正典 σ 最近邻迭代删除
                worst = min(keep, key=lambda i2: min((dist[i2][j2] for j2 in keep if j2 != i2), default=9e9))
                keep.remove(worst)
        archive = [union[i] for i in keep]  # archive 存解本体（union 全为解，fs 每代重算）
        # 新种群：archive 二进制锦标赛（Fit 小优）+ 均匀交叉 + 位变异
        new_pop = []
        while len(new_pop) < n_pop:
            a, b = rng.sample(range(len(archive)), 2) if len(archive) >= 2 else (0, 0)
            pa = archive[a] if Fit[keep[a]] <= Fit[keep[b]] else archive[b]
            pb = archive[rng.randrange(len(archive))]
            c = bits_uniform(pa, pb, rng) if rng.random() < p["pc"] else list(pa)
            bits_mutate(c, p["pm"], rng)
            new_pop.append(ctx.repair(c))
        pop = new_pop
        # 终审C 修正：yield 必须投影回目标空间（archive 存的是解位串），nd 为真实非支配数
        AF = [ctx.fs(x)[:no] for x in archive]
        _, afronts = _mo_nd_sort(AF)
        yield {"iter": it, "pop": [list(f) for f in AF[:min(8, len(AF))]],
               "front": [list(f) for f in AF], "nd": len(afronts[0])}


def _mo_moead(ctx, p, rng):
    """MOEA-D（Zhang & Li, 2007）：Tchebycheff 分解 + 权重向量邻域 + 理想点追踪。
    最大化目标的 Tchebycheff：g(x)=max_j w_j·|z*_j − f_j(x)|，z*_j=历史最大 f_j，g 越小越好。"""
    n_pop = p["n_pop"]
    if ctx.no == 2:
        H = max(1, n_pop - 1)
        W = [[i / H, 1.0 - i / H] for i in range(H + 1)][:n_pop]  # Das-Dennis 单纯形网格（双目标）
    else:  # 3+ 目标：随机归一化权重（文献常用变体）
        W = []
        for _ in range(n_pop):
            wv = [rng.random() + 0.05 for _ in range(ctx.no)]
            sw = sum(wv)
            W.append([w / sw for w in wv])
    T = max(2, n_pop // 10)
    pop = ctx.init_pop(p, rng)
    F = [ctx.fs(x)[:ctx.no] for x in pop]
    B = []  # 邻域：权重欧氏最近的 T 个
    for i in range(n_pop):
        dists = sorted(range(n_pop), key=lambda j: sum((W[i][k] - W[j][k]) ** 2 for k in range(ctx.no)))
        B.append(dists[:T])
    z = [max(f[j] for f in F) for j in range(ctx.no)]  # 理想点（最大化）
    def _g(w, f):
        return max(w[k] * abs(z[k] - f[k]) for k in range(ctx.no))
    for it in range(1, p["max_iter"] + 1):
        i_sub = it % n_pop
        pa, pb = (pop[j] for j in rng.sample(B[i_sub], 2))
        c = bits_uniform(pa, pb, rng) if rng.random() < p["pc"] else list(pa)
        bits_mutate(c, p["pm"], rng)
        c = ctx.repair(c)
        fc = ctx.fs(c)[:ctx.no]
        for k in range(ctx.no):
            if fc[k] > z[k]:
                z[k] = fc[k]
        for j in B[i_sub]:
            if _g(W[j], fc) <= _g(W[j], F[j]):
                pop[j], F[j] = c, list(fc)
        _, fronts = _mo_nd_sort(F)
        arch = [F[i] for i in fronts[0]]
        yield {"iter": it, "pop": [list(f) for f in F], "front": [list(f) for f in arch], "nd": len(arch)}


def _mo_nd_sort(F):
    """快速非支配排序（最大化 m 目标，m 任意）。返回 ranks 列表与各层索引。"""
    n = len(F)
    m = len(F[0]) if n else 0
    S = [[] for _ in range(n)]
    ndc = [0] * n
    ranks = [0] * n
    fronts = [[]]
    for i in range(n):
        for j in range(i + 1, n):
            a, b = F[i], F[j]
            a_dom = all(a[d] >= b[d] for d in range(m)) and a != b
            b_dom = all(b[d] >= a[d] for d in range(m)) and a != b
            if a_dom:
                S[i].append(j)
                ndc[j] += 1
            elif b_dom:
                S[j].append(i)
                ndc[i] += 1
    for i in range(n):
        if ndc[i] == 0:
            ranks[i] = 0
            fronts[0].append(i)
    k = 0
    while fronts[k]:
        nxt = []
        for i in fronts[k]:
            for j in S[i]:
                ndc[j] -= 1
                if ndc[j] == 0:
                    ranks[j] = k + 1
                    nxt.append(j)
        k += 1
        fronts.append(nxt)
    return ranks, [f for f in fronts if f]


def _mo_crowding(F, idxs):
    m = len(F[0]) if F else 0
    if len(idxs) <= 2:
        return {i: float("inf") for i in idxs}
    dist = {i: 0.0 for i in idxs}
    for d in range(m):
        order = sorted(idxs, key=lambda i: F[i][d])
        dist[order[0]] = dist[order[-1]] = float("inf")
        lo, hi = F[order[0]][d], F[order[-1]][d]
        rng_ = hi - lo
        if rng_ <= 0:
            continue
        for k in range(1, len(order) - 1):
            dist[order[k]] += (F[order[k + 1]][d] - F[order[k - 1]][d]) / rng_
    return dist


class _MO:
    """多目标背包（variant=moco 双目标 / maop 三目标）：no 自适应目标数，fs 返回 [v1(,v2,v3),w]（末位为约束）。"""

    def __init__(self, problem):
        self.items = [tuple(x) for x in problem["items"]]  # (w, v1[, v2, v3])
        self.cap = problem["cap"]
        self.n = problem["n"]
        self.no = len(self.items[0]) - 1  # 目标数自适应：双目标 items 宽 3、三目标宽 4

    def fs(self, s):
        v1 = v2 = 0
        w = 0
        for i in range(self.n):
            if s[i]:
                w += self.items[i][0]
                v1 += self.items[i][1]
                v2 += self.items[i][2]
        return [v1, v2, w]

    def repair(self, s):
        s = list(s)
        f = self.fs(s)
        if f[self.no] <= self.cap:
            return s
        idx = [i for i in range(self.n) if s[i]]
        idx.sort(key=lambda i: (self.items[i][1] + self.items[i][2]) / max(1, self.items[i][0]))
        for i in idx:
            if self.fs(s)[self.no] <= self.cap:
                break
            s[i] = 0
        return s

    def random(self, rng):
        return self.repair([1 if rng.random() < 0.5 else 0 for _ in range(self.n)])

    def init_pop(self, p, rng):
        return [self.random(rng) for _ in range(p["n_pop"])]


class _MO3:
    """三目标背包（variant=maop）：目标数 no=3，fs 返回 [v1,v2,v3,w]（w 为约束）。
    与 _MO 共用全部 _mo_* 内核（已泛化到 m 目标），仅 fs/repair/no 不同。"""
    no = 3

    def __init__(self, problem):
        self.items = [tuple(x) for x in problem["items"]]  # (w, v1, v2, v3)
        self.cap = problem["cap"]
        self.n = problem["n"]

    def fs(self, s):
        v1 = v2 = v3 = 0
        w = 0
        for i in range(self.n):
            if s[i]:
                w += self.items[i][0]
                v1 += self.items[i][1]
                v2 += self.items[i][2]
                v3 += self.items[i][3]
        return [v1, v2, v3, w]

    def repair(self, s):
        s = list(s)
        f = self.fs(s)
        if f[self.no] <= self.cap:
            return s
        idx = [i for i in range(self.n) if s[i]]
        idx.sort(key=lambda i: (self.items[i][1] + self.items[i][2] + self.items[i][3]) / max(1, self.items[i][0]))
        for i in idx:
            if self.fs(s)[self.no] <= self.cap:
                break
            s[i] = 0
        return s

    def random(self, rng):
        return self.repair([1 if rng.random() < 0.5 else 0 for _ in range(self.n)])

    def init_pop(self, p, rng):
        return [self.random(rng) for _ in range(p["n_pop"])]


def _mo_states(pop, ctx):
    F = [ctx.fs(s)[:ctx.no] for s in pop]
    ranks, fronts = _mo_nd_sort(F)
    front_pts = sorted((F[i] for i in fronts[0]), key=lambda p: (-p[0], p[1]))
    return F, ranks, fronts, front_pts


def _mo_random(ctx, p, rng):
    arch = []
    for it in range(1, p["max_iter"] + 1):
        s = ctx.random(rng)
        f = ctx.fs(s)[:ctx.no]
        cand = arch + [f]
        _, fronts = _mo_nd_sort(cand)
        arch = [cand[i] for i in fronts[0]]
        if len(arch) > 60:
            arch = arch[::2]
        yield {"iter": it, "pop": [ctx.fs(x)[:ctx.no] for x in [list(s)]], "front": [list(f) for f in arch], "nd": len(arch)}


def _mo_wsga(ctx, p, rng):
    """加权单目标和 GA（对照：经典加权法会漏掉非凸前沿段）。"""
    pop = ctx.init_pop(p, rng)
    for it in range(1, p["max_iter"] + 1):
        F = [ctx.fs(s)[:ctx.no] for s in pop]
        # 加权法对任意 m 目标：随机权重归一化后线性合成（m=2 时退化为原 lam/(1-lam)）
        lams = [rng.random() for _ in range(ctx.no)]
        s_ = sum(lams) or 1.0
        lams = [x / s_ for x in lams]
        sc = [sum(lams[d] * f[d] for d in range(ctx.no)) for f in F]
        bi = max(range(len(pop)), key=lambda i: sc[i])
        new = [list(pop[bi])]
        while len(new) < p["n_pop"]:
            a, b = rng.sample(range(len(pop)), 2)
            child = bits_uniform(pop[a], pop[b], rng)
            bits_mutate(child, p["pm"], rng)
            new.append(ctx.repair(child))
        pop = new
        F, ranks, fronts, front_pts = _mo_states(pop, ctx)
        yield {"iter": it, "pop": F, "front": front_pts, "nd": len(front_pts)}


def _mo_nsga2(ctx, p, rng):
    """NSGA-II（Deb et al., 2002）：非支配排序 + 拥挤度 + 精英保留。"""
    pop = ctx.init_pop(p, rng)
    for it in range(1, p["max_iter"] + 1):
        F, ranks, fronts, front_pts = _mo_states(pop, ctx)
        # 二进制锦标赛（rank 小优先，同 rank 拥挤度大优先）
        def tour():
            a, b = rng.sample(range(len(pop)), 2)
            if ranks[a] != ranks[b]:
                return pop[a] if ranks[a] < ranks[b] else pop[b]
            da = _mo_crowding(F, fronts[ranks[a]])[a]
            db = _mo_crowding(F, fronts[ranks[b]])[b]
            return pop[a] if da >= db else pop[b]

        child = []
        while len(child) < p["n_pop"]:
            pa, pb = tour(), tour()
            c = bits_uniform(pa, pb, rng) if rng.random() < p["pc"] else list(pa)
            bits_mutate(c, p["pm"], rng)
            child.append(ctx.repair(c))
        # 精英合并
        union = pop + child
        UF = [ctx.fs(s)[:ctx.no] for s in union]
        uranks, ufronts = _mo_nd_sort(UF)
        new = []
        for fr in ufronts:
            if len(new) + len(fr) <= p["n_pop"]:
                new.extend(union[i] for i in fr)
            else:
                cd = _mo_crowding(UF, fr)
                fr_sorted = sorted(fr, key=lambda i: cd[i], reverse=True)
                new.extend(union[i] for i in fr_sorted[: p["n_pop"] - len(new)])
                break
        pop = new
        F, ranks, fronts, front_pts = _mo_states(pop, ctx)
        yield {"iter": it, "pop": F, "front": front_pts, "nd": len(front_pts)}


# ---- NSGA-III 参考点小生境（Deb & Jain 2014，complete-a-kernels 2026-09-29）----
def _das_dennis(no, H):
    """Das-Dennis 单纯形参考点生成：所有非负整数向量 (w1..w_no) 和为 H，归一化到 [0,1]。"""
    pts = []
    def rec(rem, k, cur):
        if k == no - 1:
            pts.append([c / H for c in cur + [rem]])
            return
        for i in range(rem + 1):
            rec(rem - i, k + 1, cur + [i])
    rec(H, 0, [])
    return pts


def _mo_nsga3(ctx, p, rng):
    """NSGA-III（Deb & Jain 2014）：Das-Dennis 参考点 + 垂直距离关联 + 小生境计数选择。
    复用 _mo_nd_sort / bits_uniform / bits_mutate。max 目标（复用 _MO/_MO3 ctx）。"""
    no = ctx.no
    n_pop = p["n_pop"]
    H = 12 if no == 2 else 6
    R = _das_dennis(no, H)
    pop = ctx.init_pop(p, rng)
    for it in range(1, p["max_iter"] + 1):
        F = [ctx.fs(s)[:no] for s in pop]
        ranks, fronts = _mo_nd_sort(F)
        off = []
        while len(off) < n_pop:
            a, b = rng.sample(range(len(pop)), 2)
            pa = pop[a] if ranks[a] < ranks[b] else pop[b]
            pb = pop[rng.randrange(len(pop))]
            c = bits_uniform(pa, pb, rng) if rng.random() < p["pc"] else list(pa)
            bits_mutate(c, p["pm"], rng)
            off.append(ctx.repair(c))
        union = pop + off
        UF = [ctx.fs(s)[:no] for s in union]
        uranks, ufronts = _mo_nd_sort(UF)
        zmin = [min(f[j] for f in UF) for j in range(no)]
        zmax = [max(f[j] for f in UF) for j in range(no)]
        def normf(f):
            return [(f[j] - zmin[j]) / (zmax[j] - zmin[j]) if (zmax[j] - zmin[j]) > 1e-9 else 0.0
                    for j in range(no)]
        assoc = []
        for f in UF:
            fn = normf(f)
            best_r, best_d = 0, None
            for ri, r in enumerate(R):
                dot = sum(fn[d] * r[d] for d in range(no))
                r2 = sum(x * x for x in r)
                if r2 < 1e-12:
                    d = _math.sqrt(sum(x * x for x in fn))
                else:
                    proj = dot / r2
                    d = _math.sqrt(sum((fn[d] - proj * r[d]) ** 2 for d in range(no)))
                if best_d is None or d < best_d:
                    best_d, best_r = d, ri
            assoc.append(best_r)
        pop_sel = []
        rho = [0] * len(R)
        for fr in ufronts:
            if len(pop_sel) + len(fr) <= n_pop:
                for i in fr:
                    pop_sel.append(union[i]); rho[assoc[i]] += 1
            else:
                I = [i for i in fr if rho[assoc[i]] == 0]
                P = [i for i in fr if rho[assoc[i]] > 0]
                while I and len(pop_sel) < n_pop:
                    i = I.pop(rng.randrange(len(I)))
                    if rho[assoc[i]] == 0:
                        pop_sel.append(union[i]); rho[assoc[i]] += 1
                    else:
                        P.append(i)
                while P and len(pop_sel) < n_pop:
                    i = P.pop(rng.randrange(len(P)))
                    pop_sel.append(union[i]); rho[assoc[i]] += 1
                break
        pop = pop_sel
        Fpop = [ctx.fs(s)[:no] for s in pop]
        _, ffronts = _mo_nd_sort(Fpop)
        front_pts = sorted((Fpop[i] for i in ffronts[0]), key=lambda q: (-q[0],) + tuple(q[1:]))
        yield {"iter": it, "pop": [list(f) for f in Fpop], "front": [list(f) for f in front_pts],
               "nd": len(front_pts)}



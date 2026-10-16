# ============================================================
# 域六/八/十：二进制编码三域（SCP / QUBO / UFLP）共用 _bin_* 内核
# ------------------------------------------------------------
# 同背包域范式：编码=0/1 向量，域差异全部压进 ctx（obj/repair/random）。
# SAT（域七）也是二进制编码，复用 _bin_* 内核 + 两个正典特化算法
# （WalkSAT、DPLL 精确锚点）。GAP（域九）是整数向量编码，独立小内核。
# ============================================================

def _bin_random(ctx, p, rng):
    best, bs = None, None
    for it in range(1, p["max_iter"] + 1):
        s = ctx.random(rng)
        v = ctx.obj(s)
        if bs is None or v < best:
            best, bs = v, s
        yield {"iter": it, "best": best, "cur": v, "best_sol": list(bs)}


def _bin_hc(ctx, p, rng):
    s = ctx.random(rng)
    v = ctx.obj(s)
    best, bs = v, list(s)
    for it in range(1, p["max_iter"] + 1):
        for _ in range(p["tries"]):
            cand = bits_flip(s, rng, 1)
            cand = ctx.repair(cand)
            cv = ctx.obj(cand)
            if cv <= v:  # 平台侧移：等值也接受（二进制 plateau 巨大）
                s, v = cand, cv
        if v < best:
            best, bs = v, list(s)
        yield {"iter": it, "best": best, "cur": v, "best_sol": list(bs)}


def _bin_sa(ctx, p, rng):
    s = ctx.random(rng)
    v = ctx.obj(s)
    best, bs = v, list(s)
    t0, decay = p["t0"], p["decay"]
    stall = 0
    for it in range(1, p["max_iter"] + 1):
        T = t0 * (decay ** it)
        cand = bits_flip(s, rng, 1)
        cand = ctx.repair(cand)
        cv = ctx.obj(cand)
        d = cv - v
        if d < 0 or (T > 1e-12 and rng.random() < math.exp(-d / T)):
            s, v = cand, cv
        if v < best:
            best, bs = v, list(s)
            stall = 0
        else:
            stall += 1
        if stall >= p["restart_at"]:  # 卡死重启（连续域同款组件）
            s, v = list(bs), best
            s = bits_flip(s, rng, 2)
            s = ctx.repair(s)
            v = ctx.obj(s)
            stall = 0
        yield {"iter": it, "best": best, "cur": v, "best_sol": list(bs)}


def _bin_ts(ctx, p, rng):
    s = ctx.random(rng)
    v = ctx.obj(s)
    best, bs = v, list(s)
    tabu = {}
    tenure, sample = p["tenure"], p["ts_sample"]
    n = ctx.n
    for it in range(1, p["max_iter"] + 1):
        bm, bv, bi = None, None, -1
        for _ in range(sample):
            i = rng.randrange(n)
            cand = list(s)
            cand[i] ^= 1
            cand = ctx.repair(cand)
            cv = ctx.obj(cand)
            if tabu.get(i, -1) >= it and not (bv is None or cv < best):
                continue  # 特赦准则：禁忌但破纪录则放行
            if bv is None or cv < bv:
                bm, bv, bi = cand, cv, i
        if bm is None:
            s = ctx.random(rng)
            v = ctx.obj(s)
        else:
            s, v = bm, bv
            tabu[bi] = it + tenure
        if v < best:
            best, bs = v, list(s)
        yield {"iter": it, "best": best, "cur": v, "best_sol": list(bs)}


def _bin_ga(ctx, p, rng):
    pop, vals = ctx.init_pop(p, rng)
    bi = argbest(vals, "min")
    best, bs = vals[bi], list(pop[bi])
    for it in range(1, p["max_iter"] + 1):
        new = [list(pop[bi])]  # 精英保留
        while len(new) < p["n_pop"]:
            a, b = rng.sample(range(p["n_pop"]), 2)
            child = bits_uniform(pop[a], pop[b], rng)
            bits_mutate(child, p["pm"], rng)
            child = ctx.repair(child)
            new.append(child)
        pop = new
        vals = [ctx.obj(s) for s in pop]
        bi = argbest(vals, "min")
        if vals[bi] < best:
            best, bs = vals[bi], list(pop[bi])
        yield {"iter": it, "best": best, "cur": min(vals), "best_sol": list(bs)}


_BIN_ALGOS = {
    "random": {"fn": _bin_random, "name": "随机搜索", "category": "基线",
               "desc": "盲采样基线：一切算法都要显著降低目标", "tune": []},
    "hc": {"fn": _bin_hc, "name": "爬山法 HC", "category": "局部搜索",
           "desc": "单比特翻转贪心（平台侧移版）", "tune": ["tries"]},
    "sa": {"fn": _bin_sa, "name": "模拟退火 SA", "category": "物理启发",
           "desc": "Metropolis 准则 + 卡死重启", "tune": ["t0", "decay"]},
    "ts": {"fn": _bin_ts, "name": "禁忌搜索 TS", "category": "局部搜索",
           "desc": "禁忌表 + 采样邻域 + 特赦准则", "tune": ["tenure"]},
    "ga": {"fn": _bin_ga, "name": "遗传 GA", "category": "进化计算",
           "desc": "均匀交叉 + 位翻转变异 + 精英", "tune": ["pm"]},
}


# ---- 交换邻域内核（SCP/UFLP 用）：单比特翻转在「修复式编码」下太粗糙——
# 关掉一个集合/设施造成巨幅跳变，SA/GA 全部卡死（基准实测教训）。
# swap = 「关一个 + 开一个」成对移动，Δ 平滑，经典文献邻域。 ----

def _sw_random(ctx, p, rng):
    return (yield from _bin_random(ctx, p, rng))


def _sw_hc(ctx, p, rng):
    s = ctx.random(rng)
    v = ctx.obj(s)
    best, bs = v, list(s)
    stall = 0
    for it in range(1, p["max_iter"] + 1):
        for _ in range(p["tries"]):
            cand = ctx.swap(s, rng)
            cv = ctx.obj(cand)
            if cv <= v:
                s, v = cand, cv
        if v < best:
            best, bs = v, list(s)
            stall = 0
        else:
            stall += 1
        if stall >= p["restart_at"]:  # ILS：停滞则全新重启（随机基线=200 次重启，必须同样多起点）
            s = ctx.random(rng)
            v = ctx.obj(s)
            stall = 0
        yield {"iter": it, "best": best, "cur": v, "best_sol": list(bs)}


def _sw_sa(ctx, p, rng):
    s = ctx.random(rng)
    v = ctx.obj(s)
    best, bs = v, list(s)
    t0, decay = p["t0"], p["decay"]
    stall = 0
    for it in range(1, p["max_iter"] + 1):
        T = t0 * (decay ** it)
        cand = ctx.swap(s, rng)
        cv = ctx.obj(cand)
        d = cv - v
        if d < 0 or (T > 1e-12 and rng.random() < math.exp(-d / max(T, 1e-9))):
            s, v = cand, cv
        if v < best:
            best, bs = v, list(s)
            stall = 0
        else:
            stall += 1
        if stall >= p["restart_at"]:  # ILS：从全新随机重启，而非在 best 附近小踢
            s = ctx.random(rng)
            v = ctx.obj(s)
            stall = 0
        yield {"iter": it, "best": best, "cur": v, "best_sol": list(bs)}


def _sw_ts(ctx, p, rng):
    s = ctx.random(rng)
    v = ctx.obj(s)
    best, bs = v, list(s)
    tabu = {}
    tenure, sample = p["tenure"], p["ts_sample"]
    stall = 0
    for it in range(1, p["max_iter"] + 1):
        bm, bv, bkey = None, None, None
        for _ in range(sample):
            cand = ctx.swap(s, rng)
            key = tuple(i for i, b in enumerate(cand) if b != s[i])
            cv = ctx.obj(cand)
            if tabu.get(key, -1) >= it and not (bv is None or cv < best):
                continue
            if bv is None or cv < bv:
                bm, bv, bkey = cand, cv, key
        if bm is None:
            s = ctx.random(rng)
            v = ctx.obj(s)
        else:
            s, v = bm, bv
            tabu[bkey] = it + tenure
        if v < best:
            best, bs = v, list(s)
            stall = 0
        else:
            stall += 1
        if stall >= p["restart_at"]:  # ILS：禁忌陷入循环时全新重启
            s = ctx.random(rng)
            v = ctx.obj(s)
            stall = 0
            tabu = {}
        yield {"iter": it, "best": best, "cur": v, "best_sol": list(bs)}


def _sw_ga(ctx, p, rng):
    pop, vals = ctx.init_pop(p, rng)
    bi = argbest(vals, "min")
    best, bs = vals[bi], list(pop[bi])
    for it in range(1, p["max_iter"] + 1):
        new = [list(pop[bi])]
        while len(new) < p["n_pop"]:
            a, b = rng.sample(range(p["n_pop"]), 2)
            child = bits_uniform(pop[a], pop[b], rng)
            bits_mutate(child, p["pm"], rng)
            child = ctx.repair(child)
            if rng.random() < 0.5:  # 一半个体再叠一次 swap 局部移动
                child = ctx.swap(child, rng)
            new.append(child)
        pop = new
        vals = [ctx.obj(s) for s in pop]
        bi = argbest(vals, "min")
        if vals[bi] < best:
            best, bs = vals[bi], list(pop[bi])
        yield {"iter": it, "best": best, "cur": min(vals), "best_sol": list(bs)}


def _sw_pop(ctx, p, rng):
    """自适应种群组装：ctx 有 init_pop 用之，否则 random×n_pop 组装。"""
    if hasattr(ctx, "init_pop"):
        return ctx.init_pop(p, rng)
    n_pop = p.get("n_pop", 30)
    pop = [ctx.random(rng) for _ in range(n_pop)]
    return pop, [ctx.obj(x) for x in pop]


def _sw_de(ctx, p, rng):
    """通用差分 DE（批 7 续重写）：值可重复域=标准差分；排列域=swap 组合差分。"""
    pop, vals = _sw_pop(ctx, p, rng)
    F = p.get("F", 0.7)
    perm_mode = len(set(pop[0])) == len(pop[0])
    n_dim = len(pop[0])
    for it in range(1, p["max_iter"] + 1):
        for i in range(len(pop)):
            idxs = [j for j in range(len(pop)) if j != i]
            r1, r2, r3 = rng.sample(idxs, 3)
            if perm_mode:
                cand = list(pop[i])
                for k in range(n_dim):
                    if pop[r1][k] != pop[r2][k] and rng.random() < F:
                        val = pop[r3][k]
                        if val in cand:
                            pos = cand.index(val)
                            cand[k], cand[pos] = cand[pos], cand[k]
            else:
                cand = [max(0, min(ctx.n - 1, int(round(r3v + F * (r1v - r2v)))))
                        if isinstance(r3v, int) else
                        max(-5, min(5, r3v + F * (r1v - r2v)))
                        for r3v, r1v, r2v in zip(pop[r3], pop[r1], pop[r2])]
            c = ctx.obj(cand)
            if c <= vals[i]:
                pop[i], vals[i] = cand, c
        best, bpos = min(zip(vals, pop))
        yield {"iter": it, "best": best, "best_sol": list(bpos), "cur": sum(vals) / len(vals)}


def _sw_gwo(ctx, p, rng):
    """通用灰狼 GWO（批 7 续重写）：三狼投票，排列/向量双模式。"""
    pop, vals = _sw_pop(ctx, p, rng)
    perm_mode = len(set(pop[0])) == len(pop[0])
    n_dim = len(pop[0])
    for it in range(1, p["max_iter"] + 1):
        order = sorted(range(len(pop)), key=lambda i: vals[i])
        alpha, beta, delta = pop[order[0]], pop[order[1]], pop[order[2]]
        for i in range(len(pop)):
            if perm_mode:
                cand = list(pop[i])
                for k in range(n_dim):
                    lead = rng.choice([alpha, beta, delta])
                    if lead[k] != cand[k] and rng.random() < 0.6:
                        if lead[k] in cand:
                            pos = cand.index(lead[k])
                            cand[k], cand[pos] = cand[pos], cand[k]
            else:
                cand = [max(0, min(ctx.n - 1, int(round((alpha[k] + beta[k] + delta[k]) / 3))))
                        if isinstance(alpha[k], int) else
                        max(-5, min(5, (alpha[k] + beta[k] + delta[k]) / 3 + rng.uniform(-1, 1)))
                        for k in range(n_dim)]
            c = ctx.obj(cand)
            if c <= vals[i]:
                pop[i], vals[i] = cand, c
        best, bpos = min(zip(vals, pop))
        yield {"iter": it, "best": best, "best_sol": list(bpos), "cur": sum(vals) / len(vals)}


def _sw_cs(ctx, p, rng):
    """通用布谷鸟 CS（批 7 续重写）：莱维 swap 串+弃巢，域无关。"""
    pop, vals = _sw_pop(ctx, p, rng)
    pa = p.get("pa", 0.25)
    best, bpos = min(zip(vals, pop))
    for it in range(1, p["max_iter"] + 1):
        i = rng.randrange(len(pop))
        levy = int(rng.paretovariate(1.5))
        cand = list(pop[i])
        for _ in range(min(levy + 1, 8)):
            cand = ctx.swap(cand, rng)
        c = ctx.obj(cand)
        if c <= vals[i]:
            pop[i], vals[i] = cand, c
        wi = max(range(len(pop)), key=lambda i2: vals[i2])
        if rng.random() < pa:
            pop[wi] = ctx.random(rng)
            vals[wi] = ctx.obj(pop[wi])
        best, bpos = min(zip(vals, pop))
        yield {"iter": it, "best": best, "best_sol": list(bpos), "cur": sum(vals) / len(vals)}



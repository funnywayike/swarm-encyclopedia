# ---- M3 指派适配层：实值位置 → round+clamp(0..na-1)（值可重复的指派向量）----
def _as_range(ctx, rng):
    ref = ctx.random(rng)
    na = getattr(ctx, "n_a", None)
    if na is None:
        na = (max(ref) + 1) if ref else 2
    return len(ref), na

def _as_dec(ctx, pos, na):
    return [max(0, min(na - 1, int(round(v)))) for v in pos]

def _as_pso(ctx, p, rng):
    """PSO 指派版：实值位置 + round-clamp 解码。"""
    n_dim, na = _as_range(ctx, rng)
    n_pop = p.get("n_pop", 30)
    pos = [[rng.uniform(0, na - 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vel = [[0.0] * n_dim for _ in range(n_pop)]
    vals = [ctx.obj(_as_dec(ctx, k, na)) for k in pos]
    pb, pv = [list(k) for k in pos], list(vals)
    best = min(vals)
    bk = list(pos[vals.index(best)])
    for it in range(1, p["max_iter"] + 1):
        for i in range(n_pop):
            for k in range(n_dim):
                r1, r2 = rng.random(), rng.random()
                vel[i][k] = 0.7 * vel[i][k] + 1.5 * r1 * (pb[i][k] - pos[i][k]) + 1.5 * r2 * (bk[k] - pos[i][k])
                pos[i][k] += vel[i][k]
            v = ctx.obj(_as_dec(ctx, pos[i], na))
            if v <= pv[i]:
                pb[i], pv[i] = list(pos[i]), v
                if v < best:
                    best, bk = v, list(pos[i])
        yield {"iter": it, "best": best, "best_sol": _as_dec(ctx, bk, na), "cur": sum(vals) / len(vals)}

def _as_sca(ctx, p, rng):
    """SCA 指派版：正弦余弦更新 + round-clamp。"""
    n_dim, na = _as_range(ctx, rng)
    n_pop = p.get("n_pop", 30)
    pos = [[rng.uniform(0, na - 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vals = [ctx.obj(_as_dec(ctx, k, na)) for k in pos]
    best = min(vals)
    bk = list(pos[vals.index(best)])
    for it in range(1, p["max_iter"] + 1):
        r1 = 2.0 - 2.0 * it / p["max_iter"]
        for i in range(n_pop):
            r2, r3, r4 = 6.28318 * rng.random(), 2.0 * rng.random(), rng.random()
            for k in range(n_dim):
                step = r1 * (_math.sin(r2) if r4 < 0.5 else _math.cos(r2)) * abs(r3 * bk[k] - pos[i][k])
                pos[i][k] = pos[i][k] + step
            v = ctx.obj(_as_dec(ctx, pos[i], na))
            if v <= vals[i]:
                vals[i] = v
                if v < best:
                    best, bk = v, list(pos[i])
        yield {"iter": it, "best": best, "best_sol": _as_dec(ctx, bk, na), "cur": sum(vals) / len(vals)}

def _as_mfo(ctx, p, rng):
    """MFO 指派版：蛾焰螺旋 + round-clamp。"""
    import math as _m
    n_dim, na = _as_range(ctx, rng)
    n_pop = p.get("n_pop", 30)
    pos = [[rng.uniform(0, na - 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vals = [ctx.obj(_as_dec(ctx, k, na)) for k in pos]
    for it in range(1, p["max_iter"] + 1):
        flame_num = int(round(n_pop - (n_pop - 1) * it / p["max_iter"]))  # 正典多焰递减
        order = sorted(range(n_pop), key=lambda i: vals[i])
        flames = [list(pos[oi]) for oi in order]
        t_min = -1.0 + it * (-1.0 / p["max_iter"])
        for i in range(n_pop):
            flame = flames[min(i, flame_num - 1)]
            t = rng.uniform(t_min, 1.0)
            cand = list(pos[i])  # 在副本上更新，贪心接受才写回（否则没接受时位置与值错位）
            for k in range(n_dim):
                d = abs(flame[k] - pos[i][k])
                cand[k] = d * _m.exp(t) * _m.cos(6.28318 * t) + flame[k]
            v = ctx.obj(_as_dec(ctx, cand, na))
            if v <= vals[i]:
                pos[i], vals[i] = cand, v
        best = min(vals)
        yield {"iter": it, "best": best, "best_sol": _as_dec(ctx, pos[vals.index(best)], na), "cur": sum(vals) / len(vals)}

def _as_eo(ctx, p, rng):
    """EO 指派版：均衡候选聚合 + round-clamp。"""
    n_dim, na = _as_range(ctx, rng)
    n_pop = p.get("n_pop", 30)
    pos = [[rng.uniform(0, na - 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vals = [ctx.obj(_as_dec(ctx, k, na)) for k in pos]
    for it in range(1, p["max_iter"] + 1):
        order = sorted(range(n_pop), key=lambda i: vals[i])
        # 正典平衡池：前 4 优 + 均值，等概率选一
        pool = [pos[order[j]] for j in range(min(4, n_pop))]
        if n_pop >= 4:
            pool.append([sum(pos[order[j]][k] for j in range(4)) / 4.0 for k in range(n_dim)])
        c_eq = pool[rng.randrange(len(pool))]
        F = (1 if rng.random() >= 0.5 else -1) * (_math.exp(-rng.random() * 3.0) - 1.0)
        gcp = 0.5 * rng.random() if rng.random() >= 0.5 else 0.0  # GCP 开关
        for i in range(n_pop):
            lam = rng.random() * 2.0
            cand = list(pos[i])  # 在副本上更新，贪心接受才写回（否则没接受时位置与值错位）
            for k in range(n_dim):
                cand[k] = c_eq[k] + (pos[i][k] - c_eq[k]) * F + gcp * (c_eq[k] - lam * pos[i][k]) * (1.0 - F) * 0.3
            v = ctx.obj(_as_dec(ctx, cand, na))
            if v <= vals[i]:
                pos[i], vals[i] = cand, v
        best = min(vals)
        yield {"iter": it, "best": best, "best_sol": _as_dec(ctx, pos[vals.index(best)], na), "cur": sum(vals) / len(vals)}

def _as_ao(ctx, p, rng):
    """AO 指派版：经典四阶段 + round-clamp。"""
    n_dim, na = _as_range(ctx, rng)
    n_pop = p.get("n_pop", 30)
    pos = [[rng.uniform(0, na - 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vals = [ctx.obj(_as_dec(ctx, k, na)) for k in pos]
    best, bk = min(vals), list(pos[vals.index(min(vals))])
    for it in range(1, p["max_iter"] + 1):
        t = it / p["max_iter"]
        mean = [sum(pos[i][k] for i in range(n_pop)) / n_pop for k in range(n_dim)]
        lv = _levy_vec(rng, n_dim)
        for i in range(n_pop):
            for k in range(n_dim):
                if t <= 2.0 / 3.0:
                    if rng.random() < 0.5:
                        pos[i][k] = bk[k] * (1.0 - t) + (mean[k] - bk[k]) * rng.random()
                    else:
                        pos[i][k] = bk[k] * lv[k] + pos[rng.randrange(n_pop)][k] + rng.gauss(0, 0.3)
                else:
                    if rng.random() < 0.5:
                        pos[i][k] = (bk[k] - mean[k]) * 0.1 - rng.random() + (na - 1) * rng.random() * 0.1
                    else:
                        qf = 1.0 + t
                        pos[i][k] = (qf * bk[k] - (rng.random() * pos[i][k] - rng.random() * bk[k])
                                     + rng.random() * lv[k] * 0.3)
            v = ctx.obj(_as_dec(ctx, pos[i], na))
            if v <= vals[i]:
                vals[i] = v
                if v < best:
                    best, bk = v, list(pos[i])
        yield {"iter": it, "best": best, "best_sol": _as_dec(ctx, bk, na), "cur": sum(vals) / len(vals)}

def _as_sma(ctx, p, rng):
    """SMA 指派版：经典结构 + round-clamp。"""
    n_dim, na = _as_range(ctx, rng)
    n_pop = p.get("n_pop", 30)
    pos = [[rng.uniform(0, na - 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vals = [ctx.obj(_as_dec(ctx, k, na)) for k in pos]
    best = min(vals)
    bk = list(pos[vals.index(best)])
    z = 0.03
    for it in range(1, p["max_iter"] + 1):
        t = it / p["max_iter"]
        order = sorted(range(n_pop), key=lambda i: vals[i])
        rank_of = [0] * n_pop
        for r_, idx in enumerate(order):
            rank_of[idx] = r_
        bF, wF = vals[order[0]], vals[order[-1]]
        DF = best
        a = _math.atanh(max(0.001, 1.0 - t))
        vb = rng.uniform(-a, a)
        vc = rng.uniform(-(1.0 - t), 1.0 - t)
        span = max(1e-12, bF - wF)
        for i in range(n_pop):
            lg = _math.log(abs(bF - vals[i]) / span + 1.0)
            W = (1 + rng.random() * lg) if rank_of[i] < n_pop // 2 else (1 - rng.random() * lg)
            p_i = _math.tanh(abs(vals[i] - DF))
            r = rng.random()
            if r < z:
                pos[i] = [rng.uniform(0, na - 1) for _ in range(n_dim)]
            elif r < p_i:
                ia, ib = rng.randrange(n_pop), rng.randrange(n_pop)
                for k in range(n_dim):
                    pos[i][k] = bk[k] + vb * (W * pos[ia][k] - pos[ib][k])
            else:
                for k in range(n_dim):
                    pos[i][k] = vc * pos[i][k]
            v = ctx.obj(_as_dec(ctx, pos[i], na))
            if v <= vals[i]:
                vals[i] = v
                if v < best:
                    best, bk = v, list(pos[i])
        yield {"iter": it, "best": best, "best_sol": _as_dec(ctx, bk, na), "cur": sum(vals) / len(vals)}

def _as_fa(ctx, p, rng):
    """FA 指派版：亮度吸引 + round-clamp。"""
    n_dim, na = _as_range(ctx, rng)
    n_pop = p.get("n_pop", 30)
    pos = [[rng.uniform(0, na - 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vals = [ctx.obj(_as_dec(ctx, k, na)) for k in pos]
    best = min(vals)
    bk = list(pos[vals.index(best)])
    alpha = 0.5
    for it in range(1, p["max_iter"] + 1):
        for i in range(n_pop):
            j = rng.randrange(n_pop)
            if vals[j] >= vals[i]:
                continue
            for k in range(n_dim):
                r2 = (pos[i][k] - pos[j][k]) ** 2
                pos[i][k] += 1.0 / (1.0 + r2) * (pos[j][k] - pos[i][k]) + alpha * (rng.random() - 0.5)
            v = ctx.obj(_as_dec(ctx, pos[i], na))
            if v <= vals[i]:
                vals[i] = v
                if v < best:
                    best, bk = v, list(pos[i])
        alpha *= 0.97
        yield {"iter": it, "best": best, "best_sol": _as_dec(ctx, bk, na), "cur": sum(vals) / len(vals)}

def _as_ba(ctx, p, rng):
    """BA 指派版：频率调谐 + round-clamp。"""
    n_dim, na = _as_range(ctx, rng)
    n_pop = p.get("n_pop", 30)
    pos = [[rng.uniform(0, na - 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vel = [[0.0] * n_dim for _ in range(n_pop)]
    vals = [ctx.obj(_as_dec(ctx, k, na)) for k in pos]
    best = min(vals)
    bk = list(pos[vals.index(best)])
    A = [0.9] * n_pop
    for it in range(1, p["max_iter"] + 1):
        for i in range(n_pop):
            f = 0.2 + 0.8 * rng.random()
            for k in range(n_dim):
                vel[i][k] += (bk[k] - pos[i][k]) * f
                pos[i][k] += vel[i][k]
            v = ctx.obj(_as_dec(ctx, pos[i], na))
            if v <= vals[i] and rng.random() < A[i]:
                vals[i] = v
                A[i] *= 0.9
                if v < best:
                    best, bk = v, list(pos[i])
        yield {"iter": it, "best": best, "best_sol": _as_dec(ctx, bk, na), "cur": sum(vals) / len(vals)}

def _as_jaya(ctx, p, rng):
    """Jaya 指派版：向优避劣 + round-clamp。"""
    n_dim, na = _as_range(ctx, rng)
    n_pop = p.get("n_pop", 30)
    pos = [[rng.uniform(0, na - 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vals = [ctx.obj(_as_dec(ctx, k, na)) for k in pos]
    for it in range(1, p["max_iter"] + 1):
        bi, wi = vals.index(min(vals)), vals.index(max(vals))
        for i in range(n_pop):
            cand = list(pos[i])  # 在副本上更新，贪心接受才写回（否则没接受时位置与值错位）
            for k in range(n_dim):
                cand[k] += rng.random() * (pos[bi][k] - abs(pos[i][k])) - rng.random() * (pos[wi][k] - abs(pos[i][k]))
            v = ctx.obj(_as_dec(ctx, cand, na))
            if v <= vals[i]:
                pos[i], vals[i] = cand, v
        best = min(vals)
        yield {"iter": it, "best": best, "best_sol": _as_dec(ctx, pos[vals.index(best)], na), "cur": sum(vals) / len(vals)}

def _as_tlbo(ctx, p, rng):
    """TLBO 指派版：教师/学习 + round-clamp。"""
    n_dim, na = _as_range(ctx, rng)
    n_pop = p.get("n_pop", 30)
    pos = [[rng.uniform(0, na - 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vals = [ctx.obj(_as_dec(ctx, k, na)) for k in pos]
    for it in range(1, p["max_iter"] + 1):
        bi = vals.index(min(vals))
        mean = [sum(pos[i][k] for i in range(n_pop)) / n_pop for k in range(n_dim)]
        tf = rng.randint(1, 2)
        for i in range(n_pop):
            cand = list(pos[i])  # 在副本上更新，贪心接受才写回（否则没接受时位置与值错位）
            for k in range(n_dim):
                cand[k] += rng.random() * (pos[bi][k] - tf * mean[k])
            v = ctx.obj(_as_dec(ctx, cand, na))
            if v <= vals[i]:
                pos[i], vals[i] = cand, v
        idx = list(range(n_pop))
        rng.shuffle(idx)
        for a, b in zip(idx[::2], idx[1::2]):
            better, worse = (a, b) if vals[a] < vals[b] else (b, a)
            cand = list(pos[worse])  # 在副本上更新，贪心接受才写回（否则没接受时位置与值错位）
            for k in range(n_dim):
                cand[k] += rng.random() * (pos[better][k] - pos[worse][k])
            v = ctx.obj(_as_dec(ctx, cand, na))
            if v <= vals[worse]:
                pos[worse], vals[worse] = cand, v
        best = min(vals)
        yield {"iter": it, "best": best, "best_sol": _as_dec(ctx, pos[vals.index(best)], na), "cur": sum(vals) / len(vals)}

def _as_cem(ctx, p, rng):
    """CEM 指派版：精英均值回写 + 停滞重启 + round-clamp。"""
    n_dim, na = _as_range(ctx, rng)
    n_pop = p.get("n_pop", 30)
    mu = [(na - 1) / 2.0] * n_dim
    sd = [na / 3.0] * n_dim
    best, bk = None, None
    stall = 0
    for it in range(1, p["max_iter"] + 1):
        pop = [[rng.gauss(mu[k], max(0.02, sd[k])) for k in range(n_dim)] for _ in range(n_pop)]
        dec = [_as_dec(ctx, x, na) for x in pop]
        vals = [ctx.obj(x) for x in dec]
        gb, gi = min(vals), vals.index(min(vals))
        if best is None or gb < best:
            best, bk = gb, list(dec[gi])
            stall = 0
        else:
            stall += 1
        elite = sorted(range(n_pop), key=lambda i: vals[i])[:max(2, n_pop // 2)]
        mu = [sum(pop[i][k] for i in elite) / len(elite) * 0.8 + bk[k] * 0.2 for k in range(n_dim)]
        sd = [max(0.05, (max(pop[i][k] for i in elite) - min(pop[i][k] for i in elite)) / 2) for k in range(n_dim)]
        if stall >= 25:
            sd = [na / 3.0] * n_dim
            stall = 0
        yield {"iter": it, "best": best, "best_sol": list(bk), "cur": sum(vals) / len(vals)}

def _as_cmaes(ctx, p, rng):
    """CMA-ES 指派版：对角步长自适应（诚实简化）+ round-clamp。"""
    n_dim, na = _as_range(ctx, rng)
    n_pop = p.get("n_pop", 30)
    mu = [(na - 1) / 2.0] * n_dim
    sigma = na / 4.0
    best, bk = None, None
    stall = 0
    for it in range(1, p["max_iter"] + 1):
        pop = [[mu[k] + rng.gauss(0, sigma) for k in range(n_dim)] for _ in range(n_pop)]
        dec = [_as_dec(ctx, x, na) for x in pop]
        vals = [ctx.obj(x) for x in dec]
        gb, gi = min(vals), vals.index(min(vals))
        if best is None or gb < best:
            best, bk = gb, list(dec[gi])
            stall = 0
        else:
            stall += 1
        elite = sorted(range(n_pop), key=lambda i: vals[i])[:max(2, n_pop // 4)]
        mu = [sum(pop[i][k] for i in elite) / len(elite) for k in range(n_dim)]
        sigma = max(0.05, sigma * 0.95)
        if stall >= 25:
            mu = [(na - 1) / 2.0] * n_dim
            sigma = na / 4.0
            stall = 0
        yield {"iter": it, "best": best, "best_sol": list(bk), "cur": sum(vals) / len(vals)}


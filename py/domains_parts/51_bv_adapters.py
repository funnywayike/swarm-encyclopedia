# ---- M1 sigmoid 位向量适配层（2026-09-27 全矩阵计划）----
import math as _math

def _sig(v):
    return 1.0 / (1.0 + math.exp(-max(-500, min(500, v))))

def _bin_rand_pos(rng, n_dim):
    return [rng.uniform(-4, 4) for _ in range(n_dim)]

def _bin_decode(v):
    return [1 if _sig(x) > 0.5 else 0 for x in v]

def _bin_rep(ctx, b):
    return ctx.repair(b) if hasattr(ctx, "repair") else b

def _bv_fa(ctx, p, rng):
    n_pop, n_dim = p.get("n_pop", 30), ctx.n
    pos = [_bin_rand_pos(rng, n_dim) for _ in range(n_pop)]
    bits = [_bin_rep(ctx, _bin_decode(v)) for v in pos]
    vals = [ctx.obj(b) for b in bits]
    best = min(vals)
    alpha = 0.5
    for it in range(1, p["max_iter"] + 1):
        for i in range(n_pop):
            j = rng.randrange(n_pop)
            if vals[j] >= vals[i]: continue
            for k in range(n_dim):
                r2 = (pos[i][k] - pos[j][k]) ** 2
                pos[i][k] += 1.0/(1.0+r2) * (pos[j][k] - pos[i][k]) + alpha * (rng.random()-0.5)
            b = _bin_rep(ctx, _bin_decode(pos[i]))
            v = ctx.obj(b)
            if v < vals[i]: bits[i], vals[i] = b, v
        best = min(vals)
        alpha *= 0.97
        yield {"iter": it, "best": best, "best_sol": list(bits[vals.index(best)]), "cur": sum(vals)/len(vals)}

def _bv_ba(ctx, p, rng):
    n_pop, n_dim = p.get("n_pop", 30), ctx.n
    pos = [_bin_rand_pos(rng, n_dim) for _ in range(n_pop)]
    vel = [[0.0]*n_dim for _ in range(n_pop)]
    bits = [_bin_rep(ctx, _bin_decode(v)) for v in pos]
    vals = [ctx.obj(b) for b in bits]
    best = min(vals)
    gbest = list(bits[vals.index(best)])  # 全局最优位向量（vel 向其收敛）
    A = [0.9]*n_pop
    for it in range(1, p["max_iter"] + 1):
        for i in range(n_pop):
            f = 0.2 + 0.8*rng.random()
            g_real = [4.0 if b == 1 else -4.0 for b in gbest]  # gbest 的实数代理
            for k in range(n_dim):
                vel[i][k] += (g_real[k] - pos[i][k]) * f
                pos[i][k] += vel[i][k]
            b = _bin_rep(ctx, _bin_decode(pos[i]))
            v = ctx.obj(b)
            if v <= vals[i] and rng.random() < A[i]:
                bits[i], vals[i] = b, v; A[i] *= 0.9
                if v < best: best, gbest = v, list(b)
        yield {"iter": it, "best": best, "best_sol": list(bits[vals.index(best)]), "cur": sum(vals)/len(vals)}

def _bv_jaya(ctx, p, rng):
    n_pop, n_dim = p.get("n_pop", 30), ctx.n
    pos = [_bin_rand_pos(rng, n_dim) for _ in range(n_pop)]
    bits = [_bin_rep(ctx, _bin_decode(v)) for v in pos]
    vals = [ctx.obj(b) for b in bits]
    for it in range(1, p["max_iter"] + 1):
        best = min(vals)
        worst = max(vals)
        bi = vals.index(best); wi = vals.index(worst)
        b_vec = [4.0 if b==1 else -4.0 for b in bits[bi]]
        w_vec = [4.0 if w==1 else -4.0 for w in bits[wi]]
        for i in range(n_pop):
            for k in range(n_dim):
                pos[i][k] += rng.random()*(b_vec[k]-abs(pos[i][k])) - rng.random()*(w_vec[k]-abs(pos[i][k]))
            b = _bin_rep(ctx, _bin_decode(pos[i]))
            v = ctx.obj(b)
            if v < vals[i]: bits[i], vals[i] = b, v
        best = min(vals)
        yield {"iter": it, "best": best, "best_sol": list(bits[vals.index(best)]), "cur": sum(vals)/len(vals)}

def _bv_tlbo(ctx, p, rng):
    n_pop, n_dim = p.get("n_pop", 30), ctx.n
    pos = [_bin_rand_pos(rng, n_dim) for _ in range(n_pop)]
    bits = [_bin_rep(ctx, _bin_decode(v)) for v in pos]
    vals = [ctx.obj(b) for b in bits]
    for it in range(1, p["max_iter"] + 1):
        best = min(vals)
        mean = [sum(p_[k] for p_ in pos)/n_pop for k in range(n_dim)]
        tf = rng.randint(1, 2)
        bi = vals.index(best)
        for i in range(n_pop):
            for k in range(n_dim):
                pos[i][k] += rng.random()*(bits[bi][k]*4 - tf*mean[k])*0.5
            b = _bin_rep(ctx, _bin_decode(pos[i]))
            v = ctx.obj(b)
            if v < vals[i]: bits[i], vals[i] = b, v
        idx = list(range(n_pop)); rng.shuffle(idx)
        for a, b in zip(idx[::2], idx[1::2]):
            better, worse = (a, b) if vals[a] < vals[b] else (b, a)
            for k in range(n_dim):
                pos[worse][k] += rng.random()*(pos[better][k] - pos[worse][k])
            b2 = _bin_rep(ctx, _bin_decode(pos[worse]))
            v2 = ctx.obj(b2)
            if v2 < vals[worse]: bits[worse], vals[worse] = b2, v2
        best = min(vals)
        yield {"iter": it, "best": best, "best_sol": list(bits[vals.index(best)]), "cur": sum(vals)/len(vals)}



# ---- M1 续批 C：CEM/CMA-ES 分布系二值化 ----
def _bv_cem(ctx, p, rng):
    """CEM 位向量版：伯努利分布采样→精英频率回写（Rubinstein 1997 离散原味——位编码上 CEM 天然是伯努利 CEM）。"""
    n_pop, n_dim = p.get("n_pop", 30), ctx.n
    prob = [0.5] * n_dim  # 每位=1 的伯努利概率
    best, gbest = None, None
    stall = 0
    for it in range(1, p["max_iter"] + 1):
        pop = [_bin_rep(ctx, [1 if rng.random() < prob[k] else 0 for k in range(n_dim)])
               for _ in range(n_pop)]
        vals = [ctx.obj(b) for b in pop]
        gen_best, gen_bp = min(zip(vals, pop))
        if best is None or gen_best < best:
            best, gbest = gen_best, list(gen_bp)
            stall = 0
        else:
            stall += 1
        elite = sorted(range(n_pop), key=lambda i: vals[i])[:max(2, n_pop // 2)]
        freq = [sum(pop[i][k] for i in elite) / len(elite) for k in range(n_dim)]
        prob = [0.8 * f + 0.2 * g for f, g in zip(freq, (1.0 if g == 1 else 0.0 for g in gbest))]
        prob = [min(0.95, max(0.05, x)) for x in prob]  # 防概率塌缩到 0/1
        if stall >= 25:  # 停滞重启：概率弹回 0.5
            prob = [0.5] * n_dim
            stall = 0
        yield {"iter": it, "best": best, "best_sol": list(gbest), "cur": sum(vals) / len(vals)}

def _bv_cmaes(ctx, p, rng):
    """CMA-ES 位向量版：对角协方差伯努利近似（简化诚实标注：完整 CMA 矩阵对位编码无意义，
    保留均值/步长/精英回写骨架，协方差退化为每位独立方差）。"""
    n_pop, n_dim = p.get("n_pop", 30), ctx.n
    prob = [0.5] * n_dim
    sigma = 0.3
    best, gbest = None, None
    stall = 0
    for it in range(1, p["max_iter"] + 1):
        pop = [_bin_rep(ctx, [1 if rng.random() < min(0.95, max(0.05, prob[k] + rng.gauss(0, sigma))) else 0
                              for k in range(n_dim)]) for _ in range(n_pop)]
        vals = [ctx.obj(b) for b in pop]
        gen_best, gen_bp = min(zip(vals, pop))
        if best is None or gen_best < best:
            best, gbest = gen_best, list(gen_bp)
            stall = 0
        else:
            stall += 1
        elite = sorted(range(n_pop), key=lambda i: vals[i])[:max(2, n_pop // 4)]
        freq = [sum(pop[i][k] for i in elite) / len(elite) for k in range(n_dim)]
        prob = [0.7 * f + 0.3 * (1.0 if g == 1 else 0.0) for f, g in zip(freq, gbest)]
        prob = [min(0.95, max(0.05, x)) for x in prob]
        var = sum((f - 0.5) ** 2 for f in freq) / n_dim
        sigma = max(0.05, min(0.4, sigma * (1.15 if var > 0.05 else 0.92)))  # 步长自适应
        if stall >= 25:
            prob = [0.5] * n_dim
            sigma = 0.3
            stall = 0
        yield {"iter": it, "best": best, "best_sol": list(gbest), "cur": sum(vals) / len(vals)}

# ---- M1 续批 B：HS/EO/AO/SMA 二值化 ----
def _bv_hs(ctx, p, rng):
    """HS 位向量版：和声记忆考量+音高调整（Geem 2001——HS 本是离散起源算法，位串天然适配）。"""
    n_dim = ctx.n
    hms = p.get("n_pop", 30)
    hm = [_bin_rep(ctx, [1 if rng.random() < 0.5 else 0 for _ in range(n_dim)]) for _ in range(hms)]
    hv = [ctx.obj(b) for b in hm]
    hmcr, par = 0.85, 0.3
    for it in range(1, p["max_iter"] + 1):
        cand = []
        for k in range(n_dim):
            if rng.random() < hmcr:
                cand.append(hm[rng.randrange(hms)][k])  # 记忆考量
            else:
                cand.append(1 if rng.random() < 0.5 else 0)  # 随机选音
            if rng.random() < par:
                cand[-1] ^= 1  # 音高调整=位翻转
        cand = _bin_rep(ctx, cand)
        v = ctx.obj(cand)
        wi = max(range(hms), key=lambda i: hv[i])  # 最差替换
        if v < hv[wi]:
            hm[wi], hv[wi] = cand, v
        best = min(hv)
        yield {"iter": it, "best": best, "best_sol": list(hm[hv.index(best)]), "cur": sum(hv) / len(hv)}

def _bv_eo(ctx, p, rng):
    """EO 位向量版：均衡候选（4+1 分割）加权聚合更新（Faramarzi 2020）。"""
    n_pop, n_dim = p.get("n_pop", 30), ctx.n
    bits = [_bin_rep(ctx, [1 if rng.random() < 0.5 else 0 for _ in range(n_dim)]) for _ in range(n_pop)]
    vals = [ctx.obj(b) for b in bits]
    a1, a2 = 1.0, 1.0
    for it in range(1, p["max_iter"] + 1):
        order = sorted(range(n_pop), key=lambda i: vals[i])
        # 正典平衡池（Faramarzi 2020）：前 4 优 + 均值，等概率 0.2 选一作 Ceq
        top = [bits[i] for i in order[:4]]
        c_avg = [sum(t[k] for t in top) / 4.0 for k in range(n_dim)]
        avg = [1 if c > 0.5 else 0 for c in c_avg]
        pool = top + [_bin_rep(ctx, avg)]
        c_eq = pool[rng.randrange(5)]
        g = [4.0 if b == 1 else -4.0 for b in c_eq]
        F = a1 * (1 if rng.random() >= 0.5 else -1) * (_math.exp(-rng.random() * 3.0) - 1.0)
        gcp = 0.5 * rng.random() if rng.random() >= 0.5 else 0.0  # GCP 开关（GP=0.5）
        for i in range(n_pop):
            lam = rng.random() * 2.0
            cand = list(bits[i])  # 在副本上翻转，接受才写回（原先先改 bits[i]，没接受时位向量与 vals 错位）
            for k in range(n_dim):
                posv = (4.0 if bits[i][k] == 1 else -4.0)
                # 正典更新：C = Ceq + (C−Ceq)·F + G/(λV)·(1−F)
                posv = c_eq[k] + (posv - c_eq[k]) * F + gcp * (g[k] - lam * posv) * (1.0 - F) * 0.3
                if rng.random() < min(1.0, abs(posv) / 8.0):
                    cand[k] ^= 1  # sigmoid 概率翻转
            b = _bin_rep(ctx, cand)
            v = ctx.obj(b)
            if v < vals[i]:
                bits[i], vals[i] = b, v
        best = min(vals)
        yield {"iter": it, "best": best, "best_sol": list(bits[vals.index(best)]), "cur": sum(vals) / len(vals)}
        best = min(vals)

def _levy_vec(rng, n):
    """Levy 飞行步长向量（Mantegna 简化式，β=1.5, s=0.01——AO/CSO 经典部件）。"""
    import math as _mm
    beta = 1.5
    sig = (_mm.gamma(1 + beta) * _mm.sin(_mm.pi * beta / 2) /
           (_mm.gamma((1 + beta) / 2) * beta * 2 ** ((beta - 1) / 2))) ** (1 / beta)
    u = [rng.gauss(0, sig) for _ in range(n)]
    v = [rng.gauss(0, 1) for _ in range(n)]
    return [0.01 * uu / (abs(vv) ** (1 / beta)) for uu, vv in zip(u, v)]

def _bv_ao(ctx, p, rng):
    """AO 位向量版：经典四阶段（Abualigah 2021）——实值 key 空间更新 + sigmoid 解码。
    X1=Xbest(1−t/T)+(X_M−Xbest·rand)；X2=Xbest·Levy+X_R+(y−x)·rand（螺旋简化为扰动）；
    X3=(Xbest−X_M)·α−rand+((UB−LB)·rand+LB)·δ（α=δ=0.1）；X4=QF·Xbest−(G1·X·rand−G2·Xbest)+G3·Levy。"""
    n_dim, n_pop = ctx.n, p.get("n_pop", 30)
    pos = [_bin_rand_pos(rng, n_dim) for _ in range(n_pop)]
    bits = [_bin_rep(ctx, _bin_decode(v)) for v in pos]
    vals = [ctx.obj(b) for b in bits]
    best, gk = min(vals), list(pos[vals.index(min(vals))])
    for it in range(1, p["max_iter"] + 1):
        t = it / p["max_iter"]
        mean = [sum(pos[i][k] for i in range(n_pop)) / n_pop for k in range(n_dim)]
        lv = _levy_vec(rng, n_dim)
        for i in range(n_pop):
            for k in range(n_dim):
                if t <= 2.0 / 3.0:
                    if rng.random() < 0.5:  # 阶段1 扩张探索
                        pos[i][k] = gk[k] * (1.0 - t) + (mean[k] - gk[k]) * rng.random()
                    else:  # 阶段2 收缩探索（Levy+螺旋扰动）
                        pos[i][k] = gk[k] * lv[k] + pos[rng.randrange(n_pop)][k] + rng.gauss(0, 0.3)
                else:
                    if rng.random() < 0.5:  # 阶段3 扩张开发（α=δ=0.1）
                        pos[i][k] = (gk[k] - mean[k]) * 0.1 - rng.random() + 8.0 * rng.random() * 0.1
                    else:  # 阶段4 收缩开发（QF 收缩+Levy）
                        qf = 1.0 + t * (2.0 - 1.0)
                        g3 = rng.random()
                        pos[i][k] = (qf * gk[k] - (rng.random() * pos[i][k] - rng.random() * gk[k])
                                     + g3 * lv[k] * 0.3)
                pos[i][k] = max(-6.0, min(6.0, pos[i][k]))
            b = _bin_rep(ctx, _bin_decode(pos[i]))
            v = ctx.obj(b)
            if v < vals[i]:
                bits[i], vals[i] = b, v
                if v < best:
                    best, gk = v, list(pos[i])
        yield {"iter": it, "best": best, "best_sol": list(bits[vals.index(best)]), "cur": sum(vals) / len(vals)}

def _bv_sma(ctx, p, rng):
    """SMA 位向量版：经典结构（Li 2020）——Xb+vb(W·XA−XB) 位移式 + log 权重 + p=tanh|S−DF| + z=0.03 重置。"""
    n_dim, n_pop = ctx.n, p.get("n_pop", 30)
    pos = [_bin_rand_pos(rng, n_dim) for _ in range(n_pop)]
    bits = [_bin_rep(ctx, _bin_decode(v)) for v in pos]
    vals = [ctx.obj(b) for b in bits]
    best = min(vals)
    gk = list(bits[vals.index(best)])
    z = 0.03
    for it in range(1, p["max_iter"] + 1):
        t = it / p["max_iter"]
        order = sorted(range(n_pop), key=lambda i: vals[i])
        rank_of = [0] * n_pop
        for r_, idx in enumerate(order):
            rank_of[idx] = r_
        bF, wF = vals[order[0]], vals[order[-1]]
        DF = best
        a = _math.atanh(max(0.001, 1.0 - t))  # vb ∈ [−a,a]
        vb = rng.uniform(-a, a)
        vc = rng.uniform(-(1.0 - t), 1.0 - t)
        span = max(1e-12, bF - wF)
        for i in range(n_pop):
            lg = _math.log(abs(bF - vals[i]) / span + 1.0)
            W = (1 + rng.random() * lg) if rank_of[i] < n_pop // 2 else (1 - rng.random() * lg)
            p_i = _math.tanh(abs(vals[i] - DF))
            r = rng.random()
            if r < z:  # 包裹食物：随机重置
                pos[i] = [_bin_rand_pos(rng, n_dim)[k] for k in range(n_dim)]
            elif r < p_i:  # 逼近食物：Xb + vb·(W·XA − XB)
                ia, ib = rng.randrange(n_pop), rng.randrange(n_pop)
                for k in range(n_dim):
                    pos[i][k] = max(-6.0, min(6.0,
                        pos[order[0]][k] + vb * (W * pos[ia][k] - pos[ib][k])))
            else:  # 振荡：vc·X
                for k in range(n_dim):
                    pos[i][k] = max(-6.0, min(6.0, vc * pos[i][k]))
            b = _bin_rep(ctx, _bin_decode(pos[i]))
            v = ctx.obj(b)
            if v < vals[i]:
                bits[i], vals[i] = b, v
                if v < best:
                    best, gk = v, list(b)
        yield {"iter": it, "best": best, "best_sol": list(gk), "cur": sum(vals) / len(vals)}

def _pk_decode(key):
    return sorted(range(len(key)), key=lambda k: key[k])

def _pk_sol(ctx, perm):
    """best_sol 归一化：_GC/_BP 有 solution（可视化信息），_ES 直接用排列。"""
    return ctx.solution(perm) if hasattr(ctx, "solution") else perm

def _pk_val(v):
    """cost 归一化：_GC/_BP 返回 tuple、_ES 返回标量——统一取标量分量。"""
    return v[0] if isinstance(v, tuple) else v

def _pk_tie(v):
    return v[1] if isinstance(v, tuple) and len(v) > 1 else 0

def _pk_cost(ctx, key):
    perm = _pk_decode(key)
    if hasattr(ctx, "decode"):  # _GC/_BP 协议：decode 返回 cost 元组
        return ctx.decode(perm)
    return ctx.obj(perm)  # _ES 协议：obj 直接评估排列

def _pk_pso(ctx, p, rng):
    """PSO 排列版：随机键 + 速度-位置（Bean 1994 桥接）。"""
    n_dim, n_pop = len(ctx.random(rng)), p.get("n_pop", 30)
    pos = [[rng.uniform(-1, 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vel = [[0.0] * n_dim for _ in range(n_pop)]
    vals = [_pk_cost(ctx, k) for k in pos]
    pb, pv = [list(k) for k in pos], list(vals)
    best, bk = min(vals), list(pos[vals.index(min(vals))])
    for it in range(1, p["max_iter"] + 1):
        for i in range(n_pop):
            for k in range(n_dim):
                r1, r2 = rng.random(), rng.random()
                vel[i][k] = 0.7 * vel[i][k] + 1.5 * r1 * (pb[i][k] - pos[i][k]) + 1.5 * r2 * (bk[k] - pos[i][k])
                pos[i][k] += vel[i][k]
            v = _pk_cost(ctx, pos[i])
            if v <= pv[i]:
                pb[i], pv[i] = list(pos[i]), v
                if v < best:
                    best, bk = v, list(pos[i])
        yield {"iter": it, "best": _pk_val(best), "cur": _pk_val(pv[0]), "tie": _pk_tie(best),
               "best_sol": _pk_sol(ctx, _pk_decode(bk))}

def _pk_sca(ctx, p, rng):
    """SCA 排列版：随机键 + 正弦余弦更新。"""
    n_dim, n_pop = len(ctx.random(rng)), p.get("n_pop", 30)
    pos = [[rng.uniform(-1, 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vals = [_pk_cost(ctx, k) for k in pos]
    best, bk = min(vals), list(pos[vals.index(min(vals))])
    for it in range(1, p["max_iter"] + 1):
        r1 = 2.0 - 2.0 * it / p["max_iter"]
        for i in range(n_pop):
            r2, r3, r4 = 6.28318 * rng.random(), 2.0 * rng.random(), rng.random()
            for k in range(n_dim):
                step = r1 * (_math.sin(r2) if r4 < 0.5 else _math.cos(r2)) * abs(r3 * bk[k] - pos[i][k])
                pos[i][k] = pos[i][k] + step
            v = _pk_cost(ctx, pos[i])
            if v <= vals[i]:
                vals[i] = v
                if v < best:
                    best, bk = v, list(pos[i])
        yield {"iter": it, "best": _pk_val(best), "cur": _pk_val(vals[0]), "tie": _pk_tie(best),
               "best_sol": _pk_sol(ctx, _pk_decode(bk))}

def _pk_mfo(ctx, p, rng):
    """MFO 排列版：随机键 + 蛾焰螺旋。"""
    import math as _m
    n_dim, n_pop = len(ctx.random(rng)), p.get("n_pop", 30)
    pos = [[rng.uniform(-1, 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vals = [_pk_cost(ctx, k) for k in pos]
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
            v = _pk_cost(ctx, cand)
            if v <= vals[i]:
                pos[i], vals[i] = cand, v
        best = min(vals)
        bk = pos[vals.index(best)]
        yield {"iter": it, "best": _pk_val(best), "cur": _pk_val(vals[0]), "tie": _pk_tie(best),
               "best_sol": _pk_sol(ctx, _pk_decode(bk))}

def _pk_eo(ctx, p, rng):
    """EO 排列版：随机键 + 均衡候选聚合（前 4 优均值）。"""
    n_dim, n_pop = len(ctx.random(rng)), p.get("n_pop", 30)
    pos = [[rng.uniform(-1, 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vals = [_pk_cost(ctx, k) for k in pos]
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
                # 正典更新：C = Ceq + (C−Ceq)·F + G/(λV)·(1−F)
                cand[k] = c_eq[k] + (pos[i][k] - c_eq[k]) * F + gcp * (c_eq[k] - lam * pos[i][k]) * (1.0 - F) * 0.3
            v = _pk_cost(ctx, cand)
            if v <= vals[i]:
                pos[i], vals[i] = cand, v
        best = min(vals)
        bk = pos[vals.index(best)]
        yield {"iter": it, "best": _pk_val(best), "cur": _pk_val(vals[0]), "tie": _pk_tie(best),
               "best_sol": _pk_sol(ctx, _pk_decode(bk))}

def _pk_ao(ctx, p, rng):
    """AO 排列版：随机键 + 经典四阶段（Abualigah 2021）。"""
    n_dim = len(ctx.random(rng))
    n_pop = p.get("n_pop", 30)
    pos = [[rng.uniform(-1, 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vals = [_pk_cost(ctx, k) for k in pos]
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
                        pos[i][k] = (bk[k] - mean[k]) * 0.1 - rng.random() + 2.0 * rng.random() * 0.1
                    else:
                        qf = 1.0 + t
                        pos[i][k] = (qf * bk[k] - (rng.random() * pos[i][k] - rng.random() * bk[k])
                                     + rng.random() * lv[k] * 0.3)
            v = _pk_cost(ctx, pos[i])
            if v <= vals[i]:
                vals[i] = v
                if v < best:
                    best, bk = v, list(pos[i])
        yield {"iter": it, "best": _pk_val(best), "cur": _pk_val(vals[0]), "tie": _pk_tie(best),
               "best_sol": _pk_sol(ctx, _pk_decode(bk))}

def _pk_sma(ctx, p, rng):
    """SMA 排列版：随机键 + 经典结构（Li 2020）。"""
    n_dim = len(ctx.random(rng))
    n_pop = p.get("n_pop", 30)
    pos = [[rng.uniform(-1, 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vals = [_pk_cost(ctx, k) for k in pos]
    best, bk = min(vals), list(pos[vals.index(min(vals))])
    z = 0.03
    for it in range(1, p["max_iter"] + 1):
        t = it / p["max_iter"]
        order = sorted(range(n_pop), key=lambda i: vals[i])
        rank_of = [0] * n_pop
        for r_, idx in enumerate(order):
            rank_of[idx] = r_
        bF = vals[order[0]][0] if isinstance(vals[order[0]], tuple) else vals[order[0]]
        wF = vals[order[-1]][0] if isinstance(vals[order[-1]], tuple) else vals[order[-1]]
        DF = best[0] if isinstance(best, tuple) else best
        a = _math.atanh(max(0.001, 1.0 - t))
        vb = rng.uniform(-a, a)
        vc = rng.uniform(-(1.0 - t), 1.0 - t)
        span = max(1e-12, bF - wF)
        for i in range(n_pop):
            vi = vals[i][0] if isinstance(vals[i], tuple) else vals[i]
            lg = _math.log(abs(bF - vi) / span + 1.0) if bF != wF else 0.0
            W = (1 + rng.random() * lg) if rank_of[i] < n_pop // 2 else (1 - rng.random() * lg)
            p_i = _math.tanh(abs(vi - DF))
            r = rng.random()
            if r < z:
                pos[i] = [rng.uniform(-1, 1) for _ in range(n_dim)]
            elif r < p_i:
                ia, ib = rng.randrange(n_pop), rng.randrange(n_pop)
                for k in range(n_dim):
                    pos[i][k] = bk[k] + vb * (W * pos[ia][k] - pos[ib][k])
            else:
                for k in range(n_dim):
                    pos[i][k] = vc * pos[i][k]
            v = _pk_cost(ctx, pos[i])
            if v <= vals[i]:
                vals[i] = v
                if v < best:
                    best, bk = v, list(pos[i])
        yield {"iter": it, "best": _pk_val(best), "cur": _pk_val(vals[0]), "tie": _pk_tie(best),
               "best_sol": _pk_sol(ctx, _pk_decode(bk))}

def _pk_fa(ctx, p, rng):
    """FA 排列版：随机键 + 亮度吸引（更亮=目标更优者吸引）。"""
    n_dim, n_pop = len(ctx.random(rng)), p.get("n_pop", 30)
    pos = [[rng.uniform(-1, 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vals = [_pk_cost(ctx, k) for k in pos]
    best, bk = min(vals), list(pos[vals.index(min(vals))])
    alpha = 0.5
    for it in range(1, p["max_iter"] + 1):
        for i in range(n_pop):
            j = rng.randrange(n_pop)
            if vals[j] >= vals[i]:
                continue
            for k in range(n_dim):
                r2 = (pos[i][k] - pos[j][k]) ** 2
                pos[i][k] += 1.0 / (1.0 + r2) * (pos[j][k] - pos[i][k]) + alpha * (rng.random() - 0.5)
            v = _pk_cost(ctx, pos[i])
            if v <= vals[i]:
                vals[i] = v
                if v < best:
                    best, bk = v, list(pos[i])
        alpha *= 0.97
        yield {"iter": it, "best": _pk_val(best), "cur": _pk_val(vals[0]), "tie": _pk_tie(best),
               "best_sol": _pk_sol(ctx, _pk_decode(bk))}

def _pk_ba(ctx, p, rng):
    """BA 排列版：随机键 + 频率调谐 + 响度衰减。"""
    n_dim, n_pop = len(ctx.random(rng)), p.get("n_pop", 30)
    pos = [[rng.uniform(-1, 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vel = [[0.0] * n_dim for _ in range(n_pop)]
    vals = [_pk_cost(ctx, k) for k in pos]
    best, bk = min(vals), list(pos[vals.index(min(vals))])
    A = [0.9] * n_pop
    for it in range(1, p["max_iter"] + 1):
        for i in range(n_pop):
            f = 0.2 + 0.8 * rng.random()
            for k in range(n_dim):
                vel[i][k] += (bk[k] - pos[i][k]) * f
                pos[i][k] += vel[i][k]
            v = _pk_cost(ctx, pos[i])
            if v <= vals[i] and rng.random() < A[i]:
                vals[i] = v
                A[i] *= 0.9
                if v < best:
                    best, bk = v, list(pos[i])
        yield {"iter": it, "best": _pk_val(best), "cur": _pk_val(vals[0]), "tie": _pk_tie(best),
               "best_sol": _pk_sol(ctx, _pk_decode(bk))}

def _pk_jaya(ctx, p, rng):
    """Jaya 排列版：随机键 + 向 best 靠拢、远离 worst。"""
    n_dim, n_pop = len(ctx.random(rng)), p.get("n_pop", 30)
    pos = [[rng.uniform(-1, 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vals = [_pk_cost(ctx, k) for k in pos]
    for it in range(1, p["max_iter"] + 1):
        bi = vals.index(min(vals))
        wi = vals.index(max(vals))
        for i in range(n_pop):
            cand = list(pos[i])  # 在副本上更新，贪心接受才写回（否则没接受时位置与值错位）
            for k in range(n_dim):
                cand[k] += rng.random() * (pos[bi][k] - abs(pos[i][k])) - rng.random() * (pos[wi][k] - abs(pos[i][k]))
            v = _pk_cost(ctx, cand)
            if v <= vals[i]:
                pos[i], vals[i] = cand, v
        best = min(vals)
        bk = pos[vals.index(best)]
        yield {"iter": it, "best": _pk_val(best), "cur": _pk_val(vals[0]), "tie": _pk_tie(best),
               "best_sol": _pk_sol(ctx, _pk_decode(bk))}

def _pk_tlbo(ctx, p, rng):
    """TLBO 排列版：随机键 + 教师/学习两阶段。"""
    n_dim, n_pop = len(ctx.random(rng)), p.get("n_pop", 30)
    pos = [[rng.uniform(-1, 1) for _ in range(n_dim)] for _ in range(n_pop)]
    vals = [_pk_cost(ctx, k) for k in pos]
    for it in range(1, p["max_iter"] + 1):
        bi = vals.index(min(vals))
        mean = [sum(pos[i][k] for i in range(n_pop)) / n_pop for k in range(n_dim)]
        tf = rng.randint(1, 2)
        for i in range(n_pop):
            cand = list(pos[i])  # 在副本上更新，贪心接受才写回（否则没接受时位置与值错位）
            for k in range(n_dim):
                cand[k] += rng.random() * (pos[bi][k] - tf * mean[k])
            v = _pk_cost(ctx, cand)
            if v <= vals[i]:
                pos[i], vals[i] = cand, v
        idx = list(range(n_pop))
        rng.shuffle(idx)
        for a, b in zip(idx[::2], idx[1::2]):
            better, worse = (a, b) if vals[a] < vals[b] else (b, a)
            cand = list(pos[worse])  # 在副本上更新，贪心接受才写回（否则没接受时位置与值错位）
            for k in range(n_dim):
                cand[k] += rng.random() * (pos[better][k] - pos[worse][k])
            v = _pk_cost(ctx, cand)
            if v <= vals[worse]:
                pos[worse], vals[worse] = cand, v
        best = min(vals)
        bk = pos[vals.index(best)]
        yield {"iter": it, "best": _pk_val(best), "cur": _pk_val(vals[0]), "tie": _pk_tie(best),
               "best_sol": _pk_sol(ctx, _pk_decode(bk))}

def _pk_cem(ctx, p, rng):
    """CEM 排列版：随机键 + 精英均值回写 + 停滞重启。"""
    n_dim, n_pop = len(ctx.random(rng)), p.get("n_pop", 30)
    mu = [0.0] * n_dim
    sd = [1.0] * n_dim
    best, bk = None, None
    stall = 0
    for it in range(1, p["max_iter"] + 1):
        pop = [[rng.gauss(mu[k], sd[k]) for k in range(n_dim)] for _ in range(n_pop)]
        vals = [_pk_cost(ctx, k) for k in pop]
        gb, gi = min(vals), vals.index(min(vals))
        if best is None or gb < best:
            best, bk = gb, list(pop[gi])
            stall = 0
        else:
            stall += 1
        elite = sorted(range(n_pop), key=lambda i: vals[i])[:max(2, n_pop // 2)]
        mu = [sum(pop[i][k] for i in elite) / len(elite) * 0.8 + (bk[k] * 0.2) for k in range(n_dim)]
        sd = [max(0.05, (max(pop[i][k] for i in elite) - min(pop[i][k] for i in elite)) / 2) for k in range(n_dim)]
        if stall >= 25:
            sd = [1.0] * n_dim
            stall = 0
        yield {"iter": it, "best": _pk_val(best), "cur": _pk_val(vals[0]), "tie": _pk_tie(best),
               "best_sol": _pk_sol(ctx, _pk_decode(bk))}

def _pk_cmaes(ctx, p, rng):
    """CMA-ES 排列版：随机键 + 对角步长自适应（诚实简化）。"""
    n_dim, n_pop = len(ctx.random(rng)), p.get("n_pop", 30)
    mu = [0.0] * n_dim
    sigma = 0.5
    best, bk = None, None
    stall = 0
    for it in range(1, p["max_iter"] + 1):
        pop = [[mu[k] + rng.gauss(0, sigma) for k in range(n_dim)] for _ in range(n_pop)]
        vals = [_pk_cost(ctx, k) for k in pop]
        gb, gi = min(vals), vals.index(min(vals))
        if best is None or gb < best:
            best, bk = gb, list(pop[gi])
            stall = 0
        else:
            stall += 1
        elite = sorted(range(n_pop), key=lambda i: vals[i])[:max(2, n_pop // 4)]
        mu = [sum(pop[i][k] for i in elite) / len(elite) for k in range(n_dim)]
        sigma = max(0.05, min(1.0, sigma * 0.95))
        if stall >= 25:
            mu = [0.0] * n_dim
            sigma = 0.5
            stall = 0
        yield {"iter": it, "best": _pk_val(best), "cur": _pk_val(vals[0]), "tie": _pk_tie(best),
               "best_sol": _pk_sol(ctx, _pk_decode(bk))}


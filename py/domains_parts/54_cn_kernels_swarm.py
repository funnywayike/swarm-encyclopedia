# ---- 连续域内核补全（2026-10）：此前只在 TSP 上有的算法，按原论文写成连续版 ----
# 每个内核只写一遍（连续形式、原论文公式），再经 56_generic_bridges.py 的通用适配器接到位向量 / 排列 / 指派向量问题上。
# 约定同其它 _cn_*：上下文 ctx 提供 dim / lo / hi / random / clamp / eval / init_pop；每代 yield _cn_state；
# 上报「历史最优」（只降不升），评价过的每个点都参与最优追踪。


def _lv_step(rng, n, beta=1.5):
    """Lévy 飞行步长（Mantegna 算法，β = 1.5），不带缩放系数。"""
    sig = (math.gamma(1 + beta) * math.sin(math.pi * beta / 2)
           / (math.gamma((1 + beta) / 2) * beta * 2 ** ((beta - 1) / 2))) ** (1 / beta)
    return [rng.gauss(0, sig) / (abs(rng.gauss(0, 1)) ** (1 / beta) + 1e-300) for _ in range(n)]


def _cn_best0(vals, pop):
    bi = min(range(len(vals)), key=vals.__getitem__)
    return vals[bi], list(pop[bi])


def _cn_hho(ctx, p, rng):
    """哈里斯鹰 HHO（Heidari et al. 2019）：逃逸能量 E = 2E0(1 − t/T) 在探索（|E| ≥ 1）与四种围捕之间切换——
    软围攻、硬围攻、带 Lévy 俯冲的软 / 硬围攻（俯冲只在变好时接受）。"""
    pop, vals = ctx.init_pop(p, rng)
    n, D, T = len(pop), ctx.dim, p["max_iter"]
    best, bpos = _cn_best0(vals, pop)
    for it in range(1, T + 1):
        xm = [sum(x[d] for x in pop) / n for d in range(D)]
        for i in range(n):
            x = pop[i]
            E = 2 * (2 * rng.random() - 1) * (1 - it / T)
            if abs(E) >= 1:  # 探索
                if rng.random() >= 0.5:
                    xr = pop[rng.randrange(n)]
                    cand = [xr[d] - rng.random() * abs(xr[d] - 2 * rng.random() * x[d]) for d in range(D)]
                else:
                    cand = [(bpos[d] - xm[d]) - rng.random() * (ctx.lo + rng.random() * (ctx.hi - ctx.lo)) for d in range(D)]
                pop[i] = ctx.clamp(cand)
                vals[i] = ctx.eval(pop[i])
            else:
                r, J = rng.random(), 2 * (1 - rng.random())
                if r >= 0.5:
                    if abs(E) >= 0.5:  # 软围攻
                        cand = [(bpos[d] - x[d]) - E * abs(J * bpos[d] - x[d]) for d in range(D)]
                    else:  # 硬围攻
                        cand = [bpos[d] - E * abs(bpos[d] - x[d]) for d in range(D)]
                    pop[i] = ctx.clamp(cand)
                    vals[i] = ctx.eval(pop[i])
                else:  # 带渐进快速俯冲的围攻：Y 与 Y + S·LF 里挑变好的
                    ref = x if abs(E) >= 0.5 else xm
                    y = ctx.clamp([bpos[d] - E * abs(J * bpos[d] - ref[d]) for d in range(D)])
                    fy = ctx.eval(y)
                    if fy < vals[i]:
                        pop[i], vals[i] = y, fy
                    else:
                        lf = _lv_step(rng, D)
                        z = ctx.clamp([y[d] + rng.random() * lf[d] * 0.01 for d in range(D)])
                        fz = ctx.eval(z)
                        if fz < vals[i]:
                            pop[i], vals[i] = z, fz
            if vals[i] < best:
                best, bpos = vals[i], list(pop[i])
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_ssa(ctx, p, rng):
    """麻雀搜索 SSA（Xue & Shen 2020）：发现者（20%）按 exp(−i/(αT)) 收缩或高斯扰动；加入者追随最优发现者，
    排名靠后的饿着飞向别处；警戒者（10%）遇险时向最优靠拢或向最差反方向逃。更新取贪心。"""
    pop, vals = ctx.init_pop(p, rng)
    n, D, T = len(pop), ctx.dim, p["max_iter"]
    n_prod, n_scout, ST = max(1, int(0.2 * n)), max(1, int(0.1 * n)), 0.8
    best, bpos = _cn_best0(vals, pop)
    for it in range(1, T + 1):
        order = sorted(range(n), key=vals.__getitem__)
        pop, vals = [pop[i] for i in order], [vals[i] for i in order]
        worst = list(pop[-1])
        fw = vals[-1]
        new = [None] * n
        for i in range(n_prod):  # 发现者
            if rng.random() < ST:
                a = rng.random() or 1e-12
                new[i] = [pop[i][d] * math.exp(-(i + 1) / (a * T)) for d in range(D)]
            else:
                q = rng.gauss(0, 1)
                new[i] = [pop[i][d] + q for d in range(D)]
            new[i] = ctx.clamp(new[i])
        fv = [ctx.eval(new[i]) for i in range(n_prod)]
        for i in range(n_prod):
            if fv[i] < vals[i]:
                pop[i], vals[i] = new[i], fv[i]
        xp = list(pop[min(range(n_prod), key=vals.__getitem__)])
        for i in range(n_prod, n):  # 加入者
            if i + 1 > n / 2:
                q = rng.gauss(0, 1)
                cand = [q * math.exp((worst[d] - pop[i][d]) / ((i + 1) ** 2)) for d in range(D)]
            else:
                sign = [rng.choice((-1, 1)) for _ in range(D)]
                cand = [xp[d] + abs(pop[i][d] - xp[d]) * sign[d] / D for d in range(D)]
            cand = ctx.clamp(cand)
            fc = ctx.eval(cand)
            if fc < vals[i]:
                pop[i], vals[i] = cand, fc
        gbest, fg = list(pop[0]), vals[0]
        for i in rng.sample(range(n), n_scout):  # 警戒者
            if vals[i] > fg:
                cand = [gbest[d] + rng.gauss(0, 1) * abs(pop[i][d] - gbest[d]) for d in range(D)]
            else:
                k = rng.uniform(-1, 1)
                cand = [pop[i][d] + k * abs(pop[i][d] - worst[d]) / ((vals[i] - fw) + 1e-50) for d in range(D)]
            cand = ctx.clamp(cand)
            fc = ctx.eval(cand)
            if fc < vals[i]:
                pop[i], vals[i] = cand, fc
        cb, cp = _cn_best0(vals, pop)
        if cb < best:
            best, bpos = cb, cp
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_alo(ctx, p, rng):
    """蚁狮优化 ALO（Mirjalili 2015）：蚂蚁围绕「轮盘赌选中的蚁狮」与「精英蚁狮」各做一次随机游走（游走范围随迭代收缩），
    位置取两者平均；蚂蚁比蚁狮好就取代它（蚁狮 + 蚂蚁合并后留最好的 n 只）。"""
    lions, lv = ctx.init_pop(p, rng)
    n, D, T = len(lions), ctx.dim, p["max_iter"]
    best, bpos = _cn_best0(lv, lions)
    walk_len = max(10, min(T, 100))
    for it in range(1, T + 1):
        w = 2 if it > 0.1 * T else 1
        for thr, wv in ((0.5, 3), (0.75, 4), (0.9, 5), (0.95, 6)):
            if it > thr * T:
                w = wv
        ratio = (10 ** w) * it / T
        lo_t, hi_t = ctx.lo / ratio, ctx.hi / ratio
        worst_v = max(lv)
        wts = [worst_v - v + 1e-12 for v in lv]  # 轮盘赌权重：越好越大
        tot = sum(wts)

        def walk(center, k):
            c = lo_t + center[k] if rng.random() < 0.5 else -lo_t + center[k]
            d = hi_t + center[k] if rng.random() < 0.5 else -hi_t + center[k]
            s, xs = 0.0, []
            for _ in range(walk_len):
                s += 1.0 if rng.random() > 0.5 else -1.0
                xs.append(s)
            a, b = min(xs), max(xs)
            pick = xs[min(len(xs) - 1, int(it / T * len(xs)))]
            return (pick - a) * (d - c) / (b - a) + c if b > a else c

        ants, av = [], []
        for _ in range(n):
            r, acc, sel = rng.random() * tot, 0.0, n - 1
            for j in range(n):
                acc += wts[j]
                if acc >= r:
                    sel = j
                    break
            ra = [walk(lions[sel], k) for k in range(D)]
            re = [walk(bpos, k) for k in range(D)]
            a = ctx.clamp([(ra[k] + re[k]) / 2 for k in range(D)])
            ants.append(a)
            av.append(ctx.eval(a))
        allp, allv = lions + ants, lv + av
        order = sorted(range(2 * n), key=allv.__getitem__)[:n]
        lions, lv = [allp[i] for i in order], [allv[i] for i in order]
        if lv[0] < best:
            best, bpos = lv[0], list(lions[0])
        lions[0], lv[0] = list(bpos), best  # 精英永远留在蚁狮里
        yield _cn_state(ctx, it, best, bpos, ants, av)


def _cn_boa(ctx, p, rng):
    """蝴蝶优化 BOA（Arora & Singh 2019）：香味 f = c·I^a（I 取归一化后的刺激强度，越好越大；c 随迭代增大），
    以概率 p = 0.8 全局搜索 x + (r²·g* − x)·f，否则局部搜索 x + (r²·x_j − x_k)·f。"""
    pop, vals = ctx.init_pop(p, rng)
    n, D, T = len(pop), ctx.dim, p["max_iter"]
    best, bpos = _cn_best0(vals, pop)
    c, a, switch = 0.01, 0.1, 0.8
    for it in range(1, T + 1):
        lo_v, hi_v = min(vals), max(vals)
        span = (hi_v - lo_v) or 1.0
        for i in range(n):
            inten = (hi_v - vals[i]) / span + 1e-12
            fr = c * (inten ** a)
            r = rng.random()
            if rng.random() < switch:
                cand = [pop[i][d] + (r * r * bpos[d] - pop[i][d]) * fr for d in range(D)]
            else:
                j, k = rng.randrange(n), rng.randrange(n)
                cand = [pop[i][d] + (r * r * pop[j][d] - pop[k][d]) * fr for d in range(D)]
            pop[i] = ctx.clamp(cand)
            vals[i] = ctx.eval(pop[i])
            if vals[i] < best:
                best, bpos = vals[i], list(pop[i])
        c = c + 0.025 / (c * T)
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_salp(ctx, p, rng):
    """樽海鞘群 SSA-Salp（Mirjalili et al. 2017）：前一半是领导者，围绕食物（当前最优）按 c1 = 2e^{−(4t/T)²} 步长搜索；
    其余是追随者，取与前一只位置的平均。"""
    pop, vals = ctx.init_pop(p, rng)
    n, D, T = len(pop), ctx.dim, p["max_iter"]
    best, bpos = _cn_best0(vals, pop)
    for it in range(1, T + 1):
        c1 = 2 * math.exp(-((4 * it / T) ** 2))
        for i in range(n):
            if i < n / 2:
                cand = []
                for d in range(D):
                    step = c1 * ((ctx.hi - ctx.lo) * rng.random() + ctx.lo)
                    cand.append(bpos[d] + step if rng.random() >= 0.5 else bpos[d] - step)
            else:
                cand = [(pop[i][d] + pop[i - 1][d]) / 2 for d in range(D)]
            pop[i] = ctx.clamp(cand)
            vals[i] = ctx.eval(pop[i])
            if vals[i] < best:
                best, bpos = vals[i], list(pop[i])
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_fpa(ctx, p, rng):
    """花朵授粉 FPA（Yang 2012）：以概率 0.8 做全局授粉 x + γ·L(λ)·(g* − x)（Lévy 飞行，γ = 0.1，λ = 1.5），
    否则局部授粉 x + ε(x_j − x_k)；新位置更好才替换。"""
    pop, vals = ctx.init_pop(p, rng)
    n, D, T = len(pop), ctx.dim, p["max_iter"]
    best, bpos = _cn_best0(vals, pop)
    for it in range(1, T + 1):
        for i in range(n):
            if rng.random() < 0.8:
                lv = _lv_step(rng, D)
                cand = [pop[i][d] + 0.1 * lv[d] * (bpos[d] - pop[i][d]) for d in range(D)]
            else:
                j, k = rng.randrange(n), rng.randrange(n)
                e = rng.random()
                cand = [pop[i][d] + e * (pop[j][d] - pop[k][d]) for d in range(D)]
            cand = ctx.clamp(cand)
            fc = ctx.eval(cand)
            if fc < vals[i]:
                pop[i], vals[i] = cand, fc
                if fc < best:
                    best, bpos = fc, list(cand)
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_da(ctx, p, rng):
    """蜻蜓算法 DA（Mirjalili 2016）：分离 / 对齐 / 凝聚 / 觅食 / 避敌五种行为加权，权重与邻域半径随迭代变化；
    没有邻居时做 Lévy 随机游走。"""
    pop, vals = ctx.init_pop(p, rng)
    n, D, T = len(pop), ctx.dim, p["max_iter"]
    rng_ = ctx.hi - ctx.lo
    vmax = rng_ / 10.0
    vel = [[0.0] * D for _ in range(n)]
    best, bpos = _cn_best0(vals, pop)
    for it in range(1, T + 1):
        r = rng_ / 4 + rng_ * 2 * it / T
        w = 0.9 - it * 0.5 / T
        my_c = 0.1 - it * (0.1 / (T / 2)) if it <= T / 2 else 0.0
        s, a, c, f, e = 2 * rng.random() * my_c, 2 * rng.random() * my_c, 2 * rng.random() * my_c, 2 * rng.random(), my_c
        if it > 3 * T / 4:
            e = 0.0
        wi = max(range(n), key=vals.__getitem__)
        enemy = list(pop[wi])
        for i in range(n):
            nb = [j for j in range(n) if j != i and all(abs(pop[j][d] - pop[i][d]) <= r for d in range(D))]
            if nb:
                S = [-sum(pop[i][d] - pop[j][d] for j in nb) for d in range(D)]
                A = [sum(vel[j][d] for j in nb) / len(nb) for d in range(D)]
                C = [sum(pop[j][d] for j in nb) / len(nb) - pop[i][d] for d in range(D)]
                F = [bpos[d] - pop[i][d] for d in range(D)]
                E = [enemy[d] + pop[i][d] for d in range(D)]
                for d in range(D):
                    v = s * S[d] + a * A[d] + c * C[d] + f * F[d] + e * E[d] + w * vel[i][d]
                    vel[i][d] = max(-vmax, min(vmax, v))
                cand = [pop[i][d] + vel[i][d] for d in range(D)]
            else:
                lv = _lv_step(rng, D)
                cand = [pop[i][d] + lv[d] * pop[i][d] for d in range(D)]
                vel[i] = [0.0] * D
            pop[i] = ctx.clamp(cand)
            vals[i] = ctx.eval(pop[i])
            if vals[i] < best:
                best, bpos = vals[i], list(pop[i])
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_mpa(ctx, p, rng):
    """海洋掠食者 MPA（Faramarzi et al. 2020）：按迭代三等分——高速比（猎物布朗运动）、单位速度比（一半 Lévy 一半布朗）、
    低速比（掠食者 Lévy）；精英矩阵 + 记忆保存 + FADs 效应（涡流 / 鱼聚集装置，概率 0.2）。"""
    pop, vals = ctx.init_pop(p, rng)
    n, D, T = len(pop), ctx.dim, p["max_iter"]
    best, bpos = _cn_best0(vals, pop)
    P, FADs = 0.5, 0.2
    for it in range(1, T + 1):
        CF = (1 - it / T) ** (2 * it / T)
        elite = list(bpos)
        old_pop, old_vals = [list(x) for x in pop], list(vals)
        for i in range(n):
            RB = [rng.gauss(0, 1) for _ in range(D)]
            RL = [0.05 * v for v in _lv_step(rng, D)]
            R = [rng.random() for _ in range(D)]
            x = pop[i]
            if it < T / 3:
                cand = [x[d] + P * R[d] * (RB[d] * (elite[d] - RB[d] * x[d])) for d in range(D)]
            elif it < 2 * T / 3:
                if i < n / 2:
                    cand = [x[d] + P * R[d] * (RL[d] * (elite[d] - RL[d] * x[d])) for d in range(D)]
                else:
                    cand = [elite[d] + P * CF * (RB[d] * (RB[d] * elite[d] - x[d])) for d in range(D)]
            else:
                cand = [elite[d] + P * CF * (RL[d] * (RL[d] * elite[d] - x[d])) for d in range(D)]
            pop[i] = ctx.clamp(cand)
            vals[i] = ctx.eval(pop[i])
        for i in range(n):  # 记忆保存
            if vals[i] > old_vals[i]:
                pop[i], vals[i] = old_pop[i], old_vals[i]
        cb, cp = _cn_best0(vals, pop)
        if cb < best:
            best, bpos = cb, cp
        old_pop, old_vals = [list(x) for x in pop], list(vals)
        if rng.random() < FADs:  # FADs 效应
            for i in range(n):
                cand = [pop[i][d] + CF * (ctx.lo + rng.random() * (ctx.hi - ctx.lo)) * (1.0 if rng.random() < FADs else 0.0)
                        for d in range(D)]
                pop[i] = ctx.clamp(cand)
                vals[i] = ctx.eval(pop[i])
        else:
            r = rng.random()
            for i in range(n):
                j, k = rng.randrange(n), rng.randrange(n)
                pop[i] = ctx.clamp([pop[i][d] + (FADs * (1 - r) + r) * (pop[j][d] - pop[k][d]) for d in range(D)])
                vals[i] = ctx.eval(pop[i])
        for i in range(n):
            if vals[i] > old_vals[i]:
                pop[i], vals[i] = old_pop[i], old_vals[i]
        cb, cp = _cn_best0(vals, pop)
        if cb < best:
            best, bpos = cb, cp
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_cscrow(ctx, p, rng):
    """乌鸦搜索 CSA（Askarzadeh 2016）：每只乌鸦记着自己的最好藏食点；跟踪另一只乌鸦——对方没发觉（概率 1 − AP）就飞向它的藏食点，
    否则随机飞到别处；藏食点只在变好时更新。AP = 0.1，飞行长度 fl = 2。"""
    mem, mv = ctx.init_pop(p, rng)
    n, D, T = len(mem), ctx.dim, p["max_iter"]
    pos = [list(x) for x in mem]
    best, bpos = _cn_best0(mv, mem)
    AP, fl = 0.1, 2.0
    for it in range(1, T + 1):
        for i in range(n):
            j = rng.randrange(n)
            while j == i and n > 1:
                j = rng.randrange(n)
            if rng.random() >= AP:
                r = rng.random()
                cand = [pos[i][d] + r * fl * (mem[j][d] - pos[i][d]) for d in range(D)]
            else:
                cand = ctx.random(rng)
            pos[i] = ctx.clamp(cand)
            fv = ctx.eval(pos[i])
            if fv < mv[i]:
                mem[i], mv[i] = list(pos[i]), fv
                if fv < best:
                    best, bpos = fv, list(pos[i])
        yield _cn_state(ctx, it, best, bpos, pos, mv)

# ---- 连续域内核补全（2026-10）第二批：磷虾、细菌、鱼群、烟花、帝国、蛙跳、共生、生物地理、克隆选择 ----
# 约定同 54_cn_kernels_swarm.py。


def _cn_kh(ctx, p, rng):
    """磷虾群 KH（Gandomi & Alavi 2012）：每只磷虾的速度 = 诱导运动 N（邻居吸引 + 全局最优）+ 觅食运动 F（食物中心 + 自身历史最优）
    + 随机扩散 D；位置步长 Δt = C_t·Σ(UB − LB)；再做一次与随机磷虾的交叉（概率 Cr = 0.2·K̂_{i,best}）。
    食物中心用 1/K 加权，K 取平移后的正适应度（目标可为负）。"""
    pop, vals = ctx.init_pop(p, rng)
    n, D, T = len(pop), ctx.dim, p["max_iter"]
    Nmax, Vf, Dmax, Ct = 0.01, 0.02, 0.005, 0.5
    dt = Ct * D * (ctx.hi - ctx.lo)
    N_old = [[0.0] * D for _ in range(n)]
    F_old = [[0.0] * D for _ in range(n)]
    pbest = [list(x) for x in pop]
    pbv = list(vals)
    best, bpos = _cn_best0(vals, pop)
    eps = 1e-12

    def khat(a, b, kb, kw):
        return (a - b) / ((kw - kb) or eps)

    def xhat(xi, xj):
        dist = math.sqrt(sum((xj[d] - xi[d]) ** 2 for d in range(D))) + eps
        return [(xj[d] - xi[d]) / dist for d in range(D)]

    for it in range(1, T + 1):
        kb, kw = min(vals), max(vals)
        ib = vals.index(kb)
        shift = [v - kb + 1e-9 for v in vals]
        wsum = sum(1.0 / s for s in shift)
        food = [sum(pop[i][d] / shift[i] for i in range(n)) / wsum for d in range(D)]
        food = ctx.clamp(food)
        kfood = ctx.eval(food)
        if kfood < best:
            best, bpos = kfood, list(food)
        w = 0.1 + 0.8 * (1 - it / T)
        cbest = 2 * (rng.random() + it / T)
        cfood = 2 * (1 - it / T)
        new = []
        for i in range(n):
            ds = sum(math.sqrt(sum((pop[i][d] - pop[j][d]) ** 2 for d in range(D))) for j in range(n)) / (5 * n) + eps
            a_loc = [0.0] * D
            for j in range(n):
                if j == i:
                    continue
                dij = math.sqrt(sum((pop[i][d] - pop[j][d]) ** 2 for d in range(D)))
                if dij < ds:
                    kh_, xh = khat(vals[i], vals[j], kb, kw), xhat(pop[i], pop[j])
                    for d in range(D):
                        a_loc[d] += kh_ * xh[d]
            kt, xt = khat(vals[i], kb, kb, kw), xhat(pop[i], pop[ib])
            a_tar = [cbest * kt * xt[d] for d in range(D)]
            Ni = [Nmax * (a_loc[d] + a_tar[d]) + w * N_old[i][d] for d in range(D)]
            kf, xf = khat(vals[i], kfood, kb, kw), xhat(pop[i], food)
            kp, xp = khat(vals[i], pbv[i], kb, kw), xhat(pop[i], pbest[i])
            Fi = [Vf * (cfood * kf * xf[d] + kp * xp[d]) + w * F_old[i][d] for d in range(D)]
            Di = [Dmax * (1 - it / T) * rng.uniform(-1, 1) for _ in range(D)]
            N_old[i], F_old[i] = Ni, Fi
            x = [pop[i][d] + dt * (Ni[d] + Fi[d] + Di[d]) for d in range(D)]
            cr = 0.2 * abs(khat(vals[i], kb, kb, kw))  # 越差的磷虾越爱交叉
            if rng.random() < cr:
                m = pop[rng.randrange(n)]
                x = [m[d] if rng.random() < 0.5 else x[d] for d in range(D)]
            new.append(ctx.clamp(x))
        for i in range(n):
            pop[i] = new[i]
            vals[i] = ctx.eval(pop[i])
            if vals[i] < pbv[i]:
                pbest[i], pbv[i] = list(pop[i]), vals[i]
            if vals[i] < best:
                best, bpos = vals[i], list(pop[i])
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_bfo(ctx, p, rng):
    """细菌觅食 BFO（Passino 2002）：趋化（翻转 + 沿同方向游动，只要变好就继续，至多 Ns 步）、细菌间吸引 / 排斥（J_cc）、
    每 Nc 代繁殖（健康度前一半各分裂一个，淘汰后一半）、每 Nre 次繁殖做一次消除—扩散（概率 ped 随机迁移）。
    一次「迭代」= 全部细菌各做一次趋化步。"""
    pop, J = ctx.init_pop(p, rng)
    n, D, T = len(pop), ctx.dim, p["max_iter"]
    Nc, Ns, Nre, ped = 10, 4, 4, 0.25
    C = 0.05 * (ctx.hi - ctx.lo)  # 趋化步长（原论文里是自由参数）：取搜索范围的 5%——0.1 在多峰函数上对随机搜索几乎没有优势
    d_att, w_att, h_rep, w_rep = 0.1, 0.2, 0.1, 10.0
    health = [0.0] * n
    best, bpos = _cn_best0(J, pop)

    def jcc(x):
        s = 0.0
        for y in pop:
            sq = sum((x[d] - y[d]) ** 2 for d in range(D))
            s += -d_att * math.exp(-w_att * sq) + h_rep * math.exp(-w_rep * sq)
        return s

    for it in range(1, T + 1):
        for i in range(n):
            delta = [rng.uniform(-1, 1) for _ in range(D)]
            nrm = math.sqrt(sum(v * v for v in delta)) or 1.0
            direction = [v / nrm for v in delta]
            cur = J[i] + jcc(pop[i])
            health[i] += J[i]
            for _ in range(Ns + 1):
                cand = ctx.clamp([pop[i][d] + C * direction[d] for d in range(D)])
                fc = ctx.eval(cand)
                if fc < best:
                    best, bpos = fc, list(cand)
                new_cost = fc + jcc(cand)
                if new_cost < cur:
                    pop[i], J[i], cur = cand, fc, new_cost
                    health[i] += fc
                else:
                    break
        if it % Nc == 0:  # 繁殖：健康度（累计代价）低的一半各复制一份，取代高的一半
            order = sorted(range(n), key=health.__getitem__)
            half = n // 2
            keep = order[:half]
            pop = [list(pop[i]) for i in keep] + [list(pop[i]) for i in keep] + ([list(pop[order[0]])] if n % 2 else [])
            J = [J[i] for i in keep] + [J[i] for i in keep] + ([J[order[0]]] if n % 2 else [])
            health = [0.0] * n
        if it % (Nc * Nre) == 0:  # 消除—扩散
            for i in range(n):
                if rng.random() < ped:
                    pop[i] = ctx.random(rng)
                    J[i] = ctx.eval(pop[i])
                    if J[i] < best:
                        best, bpos = J[i], list(pop[i])
        yield _cn_state(ctx, it, best, bpos, pop, J)


def _cn_afsa(ctx, p, rng):
    """人工鱼群 AFSA（李晓磊 2002）：每条鱼在视野内先试聚群、追尾（拥挤度 δ = 0.618 内且更优才执行），都不行就觅食
    （最多 try_number 次试探），再不行随机游动；聚群与追尾都满足时取更优者。视野与步长随迭代缩小。"""
    pop, vals = ctx.init_pop(p, rng)
    n, D, T = len(pop), ctx.dim, p["max_iter"]
    span = ctx.hi - ctx.lo
    delta, tries = 0.618, 3
    best, bpos = _cn_best0(vals, pop)

    def dist(a, b):
        return math.sqrt(sum((a[d] - b[d]) ** 2 for d in range(D)))

    def move(x, target, step):
        dd = dist(x, target) or 1.0
        return ctx.clamp([x[d] + rng.random() * step * (target[d] - x[d]) / dd for d in range(D)])

    for it in range(1, T + 1):
        shrink = 1 - 0.9 * it / T
        visual = 0.5 * span * math.sqrt(D) * shrink
        step = 0.15 * span * shrink
        for i in range(n):
            x, fx = pop[i], vals[i]
            nbr = [j for j in range(n) if j != i and dist(x, pop[j]) < visual]
            cand, fcand = None, None
            if nbr:
                center = [sum(pop[j][d] for j in nbr) / len(nbr) for d in range(D)]
                fc = ctx.eval(ctx.clamp(center))
                if fc < fx and len(nbr) / n < delta:  # 聚群
                    cand = move(x, center, step)
                    fcand = ctx.eval(cand)
                jb = min(nbr, key=vals.__getitem__)
                if vals[jb] < fx and len(nbr) / n < delta:  # 追尾
                    c2 = move(x, pop[jb], step)
                    f2 = ctx.eval(c2)
                    if fcand is None or f2 < fcand:
                        cand, fcand = c2, f2
            if cand is None:  # 觅食
                for _ in range(tries):
                    probe = ctx.clamp([x[d] + rng.uniform(-1, 1) * visual for d in range(D)])
                    fp = ctx.eval(probe)
                    if fp < fx:
                        cand = move(x, probe, step)
                        fcand = ctx.eval(cand)
                        break
                if cand is None:  # 随机游动
                    cand = ctx.clamp([x[d] + rng.uniform(-1, 1) * step for d in range(D)])
                    fcand = ctx.eval(cand)
            if fcand < fx:
                pop[i], vals[i] = cand, fcand
            if vals[i] < best:
                best, bpos = vals[i], list(pop[i])
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_fwa(ctx, p, rng):
    """烟花算法 FWA（Tan & Zhu 2010）：好烟花爆炸得密而范围小，差烟花炸得稀而范围大；爆炸火花在随机若干维上平移 ±A，
    高斯火花在随机若干维上乘 N(1, 1)；最优烟花直接保留，其余按「到其它候选的距离」轮盘赌选择。"""
    n_fw = max(3, min(8, p.get("n_pop", 30) // 6))
    m_total, a_, b_, A_hat, m_hat = n_fw * 8, 0.04, 0.8, 0.2 * (ctx.hi - ctx.lo), max(2, n_fw)
    D, T = ctx.dim, p["max_iter"]
    fw = [ctx.random(rng) for _ in range(n_fw)]
    fv = [ctx.eval(x) for x in fw]
    best, bpos = _cn_best0(fv, fw)
    eps = 1e-12

    def fold(x):  # 越界映射回区间
        span = ctx.hi - ctx.lo
        return [ctx.lo + abs(v - ctx.lo) % span if (v < ctx.lo or v > ctx.hi) else v for v in x]

    for it in range(1, T + 1):
        ymin, ymax = min(fv), max(fv)
        s_den = sum(ymax - f for f in fv) + eps
        a_den = sum(f - ymin for f in fv) + eps
        cand, cv = [], []
        for i in range(n_fw):
            s_i = max(round(a_ * m_total), min(round(b_ * m_total), round(m_total * (ymax - fv[i] + eps) / s_den)))
            amp = A_hat * (fv[i] - ymin + eps) / a_den
            for _ in range(int(s_i)):
                x = list(fw[i])
                for d in rng.sample(range(D), max(1, round(D * rng.random()))):
                    x[d] += rng.uniform(-amp, amp)
                x = ctx.clamp(fold(x))
                cand.append(x)
                cv.append(ctx.eval(x))
        for _ in range(m_hat):  # 高斯火花
            x = list(fw[rng.randrange(n_fw)])
            g = rng.gauss(1, 1)
            for d in rng.sample(range(D), max(1, round(D * rng.random()))):
                x[d] *= g
            x = ctx.clamp(fold(x))
            cand.append(x)
            cv.append(ctx.eval(x))
        allx, allv = fw + cand, fv + cv
        bi = min(range(len(allv)), key=allv.__getitem__)
        if allv[bi] < best:
            best, bpos = allv[bi], list(allx[bi])
        chosen = [bi]
        pool = [k for k in range(len(allx)) if k != bi]
        if pool:
            dist = [sum(math.sqrt(sum((allx[k][d] - allx[j][d]) ** 2 for d in range(D))) for j in range(len(allx))) for k in pool]
            tot = sum(dist) or 1.0
            for _ in range(n_fw - 1):
                if not pool:
                    break
                r, acc, pick = rng.random() * tot, 0.0, len(pool) - 1
                for idx, dv in enumerate(dist):
                    acc += dv
                    if acc >= r:
                        pick = idx
                        break
                chosen.append(pool[pick])
        fw = [list(allx[k]) for k in chosen][:n_fw]
        fv = [allv[k] for k in chosen][:n_fw]
        while len(fw) < n_fw:
            fw.append(list(bpos))
            fv.append(best)
        yield _cn_state(ctx, it, best, bpos, allx, allv)


def _cn_ica(ctx, p, rng):
    """帝国竞争 ICA（Atashpaz-Gargari & Lucas 2007）：最好的几个国家当帝国主义者，其余殖民地按势力分配；
    殖民地同化（向帝国主义者移动 β·U(0,1)·距离，β = 2）、革命（少数维随机重置）、比帝国主义者强就互换；
    每代让最弱帝国的最弱殖民地被势力最强的帝国抢走，殖民地耗尽的帝国灭亡。"""
    pop, vals = ctx.init_pop(p, rng)
    n, D, T = len(pop), ctx.dim, p["max_iter"]
    n_imp = max(2, min(6, n // 6))
    xi, beta, p_rev = 0.1, 2.0, 0.1
    order = sorted(range(n), key=vals.__getitem__)
    pop, vals = [pop[i] for i in order], [vals[i] for i in order]
    imps = list(range(n_imp))
    cols = list(range(n_imp, n))
    worst_imp = max(vals[:n_imp])
    power = [worst_imp - vals[i] + 1e-12 for i in imps]
    tot = sum(power)
    emp = {k: [] for k in imps}
    rest = list(cols)
    for k in imps[:-1]:
        cnt = int(round(power[k] / tot * len(cols)))
        emp[k] = rest[:cnt]
        rest = rest[cnt:]
    emp[imps[-1]] = rest
    best, bpos = _cn_best0(vals, pop)
    for it in range(1, T + 1):
        for k in list(emp):
            for ci in range(len(emp[k])):
                c = emp[k][ci]
                x = [pop[c][d] + beta * rng.random() * (pop[k][d] - pop[c][d]) for d in range(D)]
                if rng.random() < p_rev:  # 革命
                    for d in rng.sample(range(D), max(1, D // 5)):
                        x[d] = rng.uniform(ctx.lo, ctx.hi)
                pop[c] = ctx.clamp(x)
                vals[c] = ctx.eval(pop[c])
                if vals[c] < best:
                    best, bpos = vals[c], list(pop[c])
                if vals[c] < vals[k]:  # 殖民地比帝国主义者强：互换
                    pop[c], pop[k] = pop[k], pop[c]
                    vals[c], vals[k] = vals[k], vals[c]
        if len(emp) > 1:  # 帝国竞争
            tc = {k: vals[k] + xi * (sum(vals[c] for c in emp[k]) / len(emp[k]) if emp[k] else 0.0) for k in emp}
            wk = max(emp, key=lambda k: tc[k])
            if emp[wk]:
                weak_col = max(emp[wk], key=vals.__getitem__)
                tmax = max(tc.values())
                ntc = {k: tmax - tc[k] + 1e-12 for k in emp}
                s = sum(ntc.values())
                r, acc, win = rng.random() * s, 0.0, None
                for k in emp:
                    acc += ntc[k]
                    if acc >= r:
                        win = k
                        break
                win = win if win is not None else min(emp, key=lambda k: tc[k])
                emp[wk].remove(weak_col)
                emp[win].append(weak_col)
            if not emp[wk] and len(emp) > 1:  # 灭亡：帝国主义者并入赢家
                winner = min((k for k in emp if k != wk), key=lambda k: tc[k])
                emp[winner].append(wk)
                del emp[wk]
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_sfla(ctx, p, rng):
    """混合蛙跳 SFLA（Eusuff & Lansey 2003）：蛙群按适应度排序后轮流分进 m 个模因组；组内取一个子模因组，
    最差的蛙向组内最好的蛙跳（步长 U(0,1)·(Pb − Pw)，不超过 Smax），不行就向全局最好跳，再不行就随机重生；组内演化 Ne 次后整体重新洗牌。"""
    pop, vals = ctx.init_pop(p, rng)
    n, D, T = len(pop), ctx.dim, p["max_iter"]
    m = max(2, min(6, n // 5))
    Ne, smax = 3, 0.5 * (ctx.hi - ctx.lo)
    best, bpos = _cn_best0(vals, pop)
    for it in range(1, T + 1):
        order = sorted(range(n), key=vals.__getitem__)
        groups = [order[g::m] for g in range(m)]
        for grp in groups:
            q = max(2, (len(grp) + 1) // 2)
            for _ in range(Ne):
                # 三角形概率选 q 只组成子模因组（排名靠前的被选中概率大）
                weights = [2.0 * (len(grp) + 1 - (r + 1)) / (len(grp) * (len(grp) + 1)) for r in range(len(grp))]
                sub = set()
                guard = 0
                while len(sub) < min(q, len(grp)) and guard < 50:
                    guard += 1
                    r, acc = rng.random(), 0.0
                    for idx, w_ in enumerate(weights):
                        acc += w_
                        if acc >= r:
                            sub.add(grp[idx])
                            break
                sub = sorted(sub, key=vals.__getitem__)
                pb, pw = sub[0], sub[-1]
                for ref in (pb, order[0], None):
                    if ref is None:
                        new = ctx.random(rng)
                    else:
                        new = ctx.clamp([pop[pw][d] + max(-smax, min(smax, rng.random() * (pop[ref][d] - pop[pw][d]))) for d in range(D)])
                    fn_ = ctx.eval(new)
                    if fn_ < best:
                        best, bpos = fn_, list(new)
                    if fn_ < vals[pw] or ref is None:
                        pop[pw], vals[pw] = new, fn_
                        break
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_sos(ctx, p, rng):
    """共生生物搜索 SOS（Cheng & Prayogo 2014）：每个生物依次经历互利（两者都向最优靠拢，受互利向量 MV 与受益因子 BF 影响）、
    偏利（向最优与随机伙伴的差学习）、寄生（拷贝自己并随机改几维，若比随机宿主强就取代它）三个阶段，更新都取贪心。"""
    pop, vals = ctx.init_pop(p, rng)
    n, D, T = len(pop), ctx.dim, p["max_iter"]
    best, bpos = _cn_best0(vals, pop)

    def accept(i, cand):
        nonlocal best, bpos
        cand = ctx.clamp(cand)
        fc = ctx.eval(cand)
        if fc < vals[i]:
            pop[i], vals[i] = cand, fc
            if fc < best:
                best, bpos = fc, list(cand)

    for it in range(1, T + 1):
        for i in range(n):
            j = rng.randrange(n)
            while j == i and n > 1:
                j = rng.randrange(n)
            mv = [(pop[i][d] + pop[j][d]) / 2 for d in range(D)]  # 互利
            bf1, bf2 = rng.choice((1, 2)), rng.choice((1, 2))
            accept(i, [pop[i][d] + rng.random() * (bpos[d] - mv[d] * bf1) for d in range(D)])
            accept(j, [pop[j][d] + rng.random() * (bpos[d] - mv[d] * bf2) for d in range(D)])
            j = rng.randrange(n)
            while j == i and n > 1:
                j = rng.randrange(n)
            accept(i, [pop[i][d] + rng.uniform(-1, 1) * (bpos[d] - pop[j][d]) for d in range(D)])  # 偏利
            j = rng.randrange(n)
            while j == i and n > 1:
                j = rng.randrange(n)
            para = list(pop[i])  # 寄生
            for d in range(D):
                if rng.random() < 0.5:
                    para[d] = rng.uniform(ctx.lo, ctx.hi)
            accept(j, para)
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_bbo(ctx, p, rng):
    """生物地理学优化 BBO（Simon 2008）：栖息地按适应度排序，物种数越多（越好）迁出率 μ 越高、迁入率 λ 越低；
    每个特征以 λ 的概率从按 μ 轮盘赌选出的栖息地迁入，再以小概率变异；保留 2 个精英。"""
    pop, vals = ctx.init_pop(p, rng)
    n, D, T = len(pop), ctx.dim, p["max_iter"]
    n_elite, p_mut = 2, 0.01
    best, bpos = _cn_best0(vals, pop)
    for it in range(1, T + 1):
        order = sorted(range(n), key=vals.__getitem__)
        pop, vals = [pop[i] for i in order], [vals[i] for i in order]
        elite = [(list(pop[k]), vals[k]) for k in range(n_elite)]
        mu = [(n - k) / n for k in range(n)]  # 排名 k（0 = 最好）
        lam = [1 - m for m in mu]
        mu_sum = sum(mu)
        new = [list(x) for x in pop]
        for i in range(n):
            for d in range(D):
                if rng.random() < lam[i]:
                    r, acc, src = rng.random() * mu_sum, 0.0, n - 1
                    for j in range(n):
                        acc += mu[j]
                        if acc >= r:
                            src = j
                            break
                    new[i][d] = pop[src][d]
                if rng.random() < p_mut:
                    new[i][d] = rng.uniform(ctx.lo, ctx.hi)
        for i in range(n):
            pop[i] = ctx.clamp(new[i])
            vals[i] = ctx.eval(pop[i])
            if vals[i] < best:
                best, bpos = vals[i], list(pop[i])
        worst = sorted(range(n), key=vals.__getitem__, reverse=True)[:n_elite]
        for slot, (ex, ev) in zip(worst, elite):  # 精英替换最差
            pop[slot], vals[slot] = ex, ev
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_ais(ctx, p, rng):
    """克隆选择 CLONALG（de Castro & Von Zuben 2002）：取亲和度（目标值）最好的一半抗体，按排名克隆（越好克隆越多），
    高频变异的幅度与亲和度成反比（亲和度越高变得越少），克隆里最好的取代原抗体；每代用新随机抗体替换最差的 20%（受体编辑）。"""
    pop, vals = ctx.init_pop(p, rng)
    n, D, T = len(pop), ctx.dim, p["max_iter"]
    n_sel, beta, rho, n_new = max(2, n // 2), 0.3, 3.0, max(1, int(0.2 * n))
    span = ctx.hi - ctx.lo
    best, bpos = _cn_best0(vals, pop)
    for it in range(1, T + 1):
        order = sorted(range(n), key=vals.__getitem__)
        pop, vals = [pop[i] for i in order], [vals[i] for i in order]
        lo_v, hi_v = vals[0], vals[-1]
        rngv = (hi_v - lo_v) or 1.0
        for r in range(n_sel):
            n_clone = max(1, int(round(beta * n / (r + 1))))
            aff = 1.0 - (vals[r] - lo_v) / rngv  # 归一化亲和度，1 = 最好
            sigma = math.exp(-rho * aff) * 0.3 * span
            bc, bv = None, vals[r]
            for _ in range(n_clone):
                c = ctx.clamp([pop[r][d] + rng.gauss(0, sigma) for d in range(D)])
                fc = ctx.eval(c)
                if fc < bv:
                    bc, bv = c, fc
            if bc is not None:
                pop[r], vals[r] = bc, bv
                if bv < best:
                    best, bpos = bv, list(bc)
        for k in range(n - n_new, n):  # 受体编辑
            pop[k] = ctx.random(rng)
            vals[k] = ctx.eval(pop[k])
            if vals[k] < best:
                best, bpos = vals[k], list(pop[k])
        yield _cn_state(ctx, it, best, bpos, pop, vals)

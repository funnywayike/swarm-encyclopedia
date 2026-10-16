# ============================================================
# 注册表与统一接口
# ============================================================

_KS_ALGOS = {
    "random": {"fn": _ks_random, "name": "随机搜索", "category": "基线", "desc": "盲采样基线：一切算法都要显著赢它", "tune": []},
    "hc": {"fn": _ks_hc, "name": "爬山法 HC", "category": "局部搜索", "desc": "单比特翻转贪心", "tune": ["tries"]},
    "sa": {"fn": _ks_sa, "name": "模拟退火 SA", "category": "物理启发", "desc": "Metropolis 准则允许暂时变差", "tune": ["t0", "decay"]},
    "ga": {"fn": _ks_ga, "name": "遗传 GA", "category": "进化计算", "desc": "均匀交叉 + 位翻转变异 + 精英", "tune": ["pm"]},
    "de": {"fn": _ks_de, "name": "二进制差分 DE", "category": "进化计算", "desc": "差向量 = r2/r3 不同的位", "tune": ["F", "CR"]},
    "ts": {"fn": _ks_ts, "name": "禁忌搜索 TS", "category": "局部搜索", "desc": "禁忌表 + 全邻域选优", "tune": ["tenure"]},
    "abc": {"fn": _ks_abc, "name": "人工蜂群 ABC", "category": "群体智能", "desc": "雇佣/观察/侦察三阶段", "tune": ["limit"]},
    "woa": {"fn": _ks_woa, "name": "鲸鱼 WOA", "category": "群体智能", "desc": "包围/螺旋二值化", "tune": []},
    "gwo": {"fn": _ks_gwo, "name": "灰狼 GWO", "category": "群体智能", "desc": "α/β/δ 逐位投票（bGWO）", "tune": []},
    "cs": {"fn": _ks_cs, "name": "布谷鸟 CS", "category": "群体智能", "desc": "莱维翻转 + 弃巢", "tune": ["pa"]},
}


# ---- 连续域扩容批 1（2026-09-27 ROADMAP 批 1：正典连续公式，连续域原生）----

def _cn_fa(ctx, p, rng):
    """萤火虫 FA（Yang 2008）连续经典：亮度=1/(1+目标)，向更亮者移动 β=1/(1+r²) + α 扰动衰减。"""
    pop, vals = ctx.init_pop(p, rng)
    best, bpos = min(zip(vals, pop))
    alpha = 0.6
    for it in range(1, p["max_iter"] + 1):
        order = sorted(range(len(pop)), key=lambda i: vals[i])
        bi = order[0]
        for i in range(len(pop)):
            j = order[rng.randrange(max(1, order.index(i)))] if order.index(i) > 0 else bi
            r2 = sum((a - b) ** 2 for a, b in zip(pop[i], pop[j]))
            beta = 1.0 / (1.0 + r2)
            pop[i] = ctx.clamp([a + beta * (b - a) + alpha * (rng.random() - 0.5)
                                for a, b in zip(pop[i], pop[j])])
            vals[i] = ctx.eval(pop[i])
        cb, cp = min(zip(vals, pop))
        if cb < best:  # 上报历史最优：只降不升（原先每代取当代种群的最优，会变差）
            best, bpos = cb, list(cp)
        alpha *= 0.97
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_ba(ctx, p, rng):
    """蝙蝠 BA（Yang 2010）连续经典：频率调谐 + 响度/脉冲率自适应衰减。"""
    pop, vals = ctx.init_pop(p, rng)
    best, bpos = min(zip(vals, pop))
    n = len(pop)
    vel = [[0.0] * ctx.dim for _ in range(n)]
    A = [0.9] * n
    r0 = [0.5] * n
    for it in range(1, p["max_iter"] + 1):
        for i in range(n):
            f = 0.2 + 0.8 * rng.random()
            vel[i] = [v + (x - b) * f for v, x, b in zip(vel[i], pop[i], bpos)]
            cand = ctx.clamp([x + v for x, v in zip(pop[i], vel[i])])
            if rng.random() > r0[i]:
                cand = ctx.clamp([b + 0.08 * (ctx.hi - ctx.lo) * rng.gauss(0, 1) for b in bpos])
            c = ctx.eval(cand)
            if c <= vals[i] and rng.random() < A[i]:
                pop[i], vals[i] = cand, c
                A[i] *= 0.9
                r0[i] = r0[i] * (1 - math.exp(-0.9 * it))
            if c < best:
                best, bpos = c, list(cand)
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_jaya(ctx, p, rng):
    """Jaya（Rao 2016）连续经典：x' = x + r1·(best − |x|) − r2·(worst − |x|)，零专属参数。"""
    pop, vals = ctx.init_pop(p, rng)
    for it in range(1, p["max_iter"] + 1):
        best, bpos = min(zip(vals, pop))
        worst, wpos = max(zip(vals, pop))
        # Rao 2016 原式：Best/Worst = 全局最好/最差解的对应维值
        for i in range(len(pop)):
            cand = ctx.clamp([
                x + rng.random() * (b - abs(x)) - rng.random() * (w - abs(x))
                for x, b, w in zip(pop[i], bpos, wpos)])
            c = ctx.eval(cand)
            # 本站变体：贪心准入——远离 worst 项在收敛后期会把好解推离最优（连续域实测发散）
            if c < vals[i]:
                pop[i], vals[i] = cand, c
        best, bpos = min(zip(vals, pop))
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_gsa(ctx, p, rng):
    """引力搜索 GSA（Rashedi 2009）连续经典：质量=归一化适应度，引力加速度驱动速度-位置。"""
    pop, vals = ctx.init_pop(p, rng)
    G0 = 1.0  # G0=100 时初代加速度 ~230/维，纯暴力随机游走
    span = ctx.hi - ctx.lo
    vel = [[(b - x) * 0.1 for x, b in zip(x0, min(zip(vals, pop))[1])] for x0 in pop]
    best, bpos = min(zip(vals, pop))
    for it in range(1, p["max_iter"] + 1):
        lo_v, hi_v = min(vals), max(vals)
        span = max(1e-12, hi_v - lo_v)
        m = [(hi_v - v) / span + 1e-9 for v in vals]
        ms = sum(m)
        m = [x / ms for x in m]
        G = G0 * math.exp(-3.0 * it / p["max_iter"])  # 衰减放缓：快衰减 30 代内引力场消失
        new = []
        for i in range(len(pop)):
            ax = [0.0] * ctx.dim
            for j in range(len(pop)):
                if j == i:
                    continue
                d = max(1e-9, math.dist(pop[i], pop[j]))
                for k in range(ctx.dim):
                    ax[k] += G * m[j] * (pop[j][k] - pop[i][k]) / d
            # 原文速度累积：v = rand·v + a；位置 = 位置 + v
            vel[i] = [max(-span, min(span, 0.7 * rng.random() * v + a))
                      for v, a in zip(vel[i], ax)]  # 速度阻尼+限幅：无界速度 200 代发散
            new.append(ctx.clamp([x + v for x, v in zip(pop[i], vel[i])]))
        pop = new
        vals = [ctx.eval(x) for x in pop]
        cb, cp = min(zip(vals, pop))
        if cb < best:  # 上报历史最优：只降不升（原先每代取当代种群的最优，会变差）
            best, bpos = cb, list(cp)
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_mfo(ctx, p, rng):
    """蛾焰 MFO（Mirjalili 2015）连续经典：螺旋飞行绕火焰，焰数逐代递减。"""
    pop, vals = ctx.init_pop(p, rng)
    flames, fvals = list(pop), list(vals)
    best, bpos = min(zip(fvals, flames))
    N = len(pop)
    b = 1.0
    for it in range(1, p["max_iter"] + 1):
        fn = max(1, round(N - it * (N - 1) / p["max_iter"]))
        for i in range(N):
            fl = flames[i % len(flames)]
            t = rng.uniform(-1.0, 1.0)
            Dv = math.dist(pop[i], fl)  # 到火焰的距离（整体，非逐维）
            pop[i] = ctx.clamp([
                Dv * math.exp(b * t) * math.cos(2 * math.pi * t) + f for f in fl])
            vals[i] = ctx.eval(pop[i])
        # 火焰表更新：pop ∪ 旧 flames 取 top fn（原文标准——不是每代直接砍表）
        cand = pop + flames
        cvals = vals + fvals
        order = sorted(range(len(cand)), key=lambda i: cvals[i])[:fn]
        flames = [cand[i] for i in order]
        fvals = [cvals[i] for i in order]
        best, bpos = min(zip(fvals, flames))
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_tlbo(ctx, p, rng):
    """教与学 TLBO（Rao 2011）连续经典：教师阶段向最优-均值靠拢，学习阶段两两互学。零专属参数。"""
    pop, vals = ctx.init_pop(p, rng)
    for it in range(1, p["max_iter"] + 1):
        best, bpos = min(zip(vals, pop))
        mean = [sum(x[k] for x in pop) / len(pop) for k in range(ctx.dim)]
        for i in range(len(pop)):
            tf = rng.randint(1, 2)
            cand = ctx.clamp([x + rng.random() * (b - tf * m)
                              for x, b, m in zip(pop[i], bpos, mean)])
            c = ctx.eval(cand)
            if c < vals[i]:
                pop[i], vals[i] = cand, c
        idx = list(range(len(pop)))
        rng.shuffle(idx)
        for a, b in zip(idx[::2], idx[1::2]):
            better, worse = (a, b) if vals[a] < vals[b] else (b, a)
            cand = ctx.clamp([x + rng.random() * (px - qx)
                              for x, px, qx in zip(pop[worse], pop[better], pop[worse])])
            c = ctx.eval(cand)
            if c < vals[worse]:
                pop[worse], vals[worse] = cand, c
        best, bpos = min(zip(vals, pop))
        yield _cn_state(ctx, it, best, bpos, pop, vals)




# ---- 连续域扩容批 2 ----

def _cn_hs(ctx, p, rng):
    """和声搜索 HS（Geem 2001）连续经典：HMCR 记忆/音高调整/随机三路即兴，新和声替换最差。"""
    pop, vals = ctx.init_pop(p, rng)
    hmcr = 0.95
    bw0 = 0.5 * (ctx.hi - ctx.lo)  # 带宽加大+逐代收缩（固定窄带宽 30 代出不了活）
    best, bpos = min(zip(vals, pop))
    for it in range(1, p["max_iter"] + 1):
        cand = []
        for k in range(ctx.dim):
            bw = bw0 * (1.0 - 0.8 * it / p["max_iter"])  # 每维先算带宽（作用域修正）
            if rng.random() < hmcr:
                v = pop[rng.randrange(len(pop))][k]
                if rng.random() < 0.3:
                    v += rng.uniform(-bw, bw)
            else:
                v = rng.uniform(ctx.lo, ctx.hi)
            cand.append(v)
        cand = ctx.clamp(cand)
        c = ctx.eval(cand)
        wi = max(range(len(pop)), key=lambda i: vals[i])
        if c < vals[wi]:
            pop[wi], vals[wi] = cand, c
        # 每代再即兴 4 次（单和声版本 200 代也慢——HS 文献常用多和声并行）
        for _ in range(4):
            cand = []
            for k in range(ctx.dim):
                if rng.random() < hmcr:
                    v = pop[rng.randrange(len(pop))][k]
                    if rng.random() < 0.3:
                        bw = bw0 * (1.0 - 0.8 * it / p["max_iter"])
                        v += rng.uniform(-bw, bw)
                else:
                    v = rng.uniform(ctx.lo, ctx.hi)
                cand.append(v)
            cand = ctx.clamp(cand)
            c2 = ctx.eval(cand)
            wi2 = max(range(len(pop)), key=lambda i: vals[i])
            if c2 < vals[wi2]:
                pop[wi2], vals[wi2] = cand, c2
        best, bpos = min(zip(vals, pop))
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_abc(ctx, p, rng):
    """人工蜂群 ABC（Karaboga 2005）连续经典：雇佣蜂邻域觅食、观察蜂轮盘跟随、侦察蜂弃巢重置。"""
    pop, vals = ctx.init_pop(p, rng)
    best, bpos = min(zip(vals, pop))
    limit = 20
    fail = [0] * len(pop)
    for it in range(1, p["max_iter"] + 1):
        for i in range(len(pop)):  # 雇佣蜂
            k = rng.randrange(len(pop))
            while k == i:
                k = rng.randrange(len(pop))
            phi = rng.uniform(-1.0, 1.0)
            cand = ctx.clamp([x + phi * (x - pop[k][j]) for j, (x, ) in enumerate([(v,) for v in pop[i]])])
            c = ctx.eval(cand)
            if c < vals[i]:
                pop[i], vals[i] = cand, c
                fail[i] = 0
            else:
                fail[i] += 1
        # Karaboga 的标准适应度：f ≥ 0 时 1/(1+f)，f < 0 时 1+|f|（原先只写了前一半，目标值 ≤ −1 时权重为负，
        # 轮盘直接抛 ValueError——自带问题 / 允许负目标的变体上 ABC 会崩）
        fit = [1.0 / (1.0 + v) if v >= 0 else 1.0 + abs(v) for v in vals]
        fs = sum(fit)
        for _ in range(len(pop)):  # 观察蜂（轮盘）
            i = rng.choices(range(len(pop)), weights=fit)[0]
            k = rng.randrange(len(pop))
            while k == i:
                k = rng.randrange(len(pop))
            phi = rng.uniform(-1.0, 1.0)
            cand = ctx.clamp([x + phi * (x - pop[k][j]) for j, x in enumerate(pop[i])])
            c = ctx.eval(cand)
            if c < vals[i]:
                pop[i], vals[i] = cand, c
                fail[i] = 0
            else:
                fail[i] += 1
        wi = max(range(len(pop)), key=lambda i: fail[i])  # 侦察蜂
        if fail[wi] >= limit:
            pop[wi] = ctx.random(rng)
            vals[wi] = ctx.eval(pop[wi])
            fail[wi] = 0
        cb, cp = min(zip(vals, pop))
        if cb < best:  # 历史最优单独记着：侦察蜂弃巢可能正好重置掉当前最好的那只（最久没改进的往往就是它），不能因此丢解
            best, bpos = cb, list(cp)
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_eo(ctx, p, rng):
    """均衡优化 EO（Faramarzi 2020）连续经典：均衡池 4 最优+1 平均，指数生成率 F 控制收束。"""
    pop, vals = ctx.init_pop(p, rng)
    a = 2.0
    best, bpos = min(zip(vals, pop))
    for it in range(1, p["max_iter"] + 1):
        order = sorted(range(len(pop)), key=lambda i: vals[i])
        pool = [pop[i] for i in order[:4]]
        avg = [sum(x[k] for x in pool) / 4 for k in range(ctx.dim)]
        pool.append(avg)
        lam = 2.0 * rng.uniform(0, 1)
        F = max(0.0, min(1.0, math.exp(-a * it / p["max_iter"])))  # 生成率∈[0,1]：>1 会把 (x−ceq) 外推爆炸
        for i in range(len(pop)):
            ceq = pool[rng.randrange(len(pool))]
            G = [(rng.random() - 0.5) * 2.0 * (1.0 - 0.7 * it / p["max_iter"])
                 for _ in range(ctx.dim)]  # G 对称化+幅度随迭代衰减：对称但收束
            pop[i] = ctx.clamp([
                ceq[k] + (x - ceq[k]) * F + G[k] * (1 - F) for k, x in enumerate(pop[i])])
            vals[i] = ctx.eval(pop[i])
        cb, cp = min(zip(vals, pop))
        if cb < best:  # 上报历史最优：只降不升（原先每代取当代种群的最优，会变差）
            best, bpos = cb, list(cp)
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_ao(ctx, p, rng):
    """天鹰 AO（Abualigah 2021）连续经典：四阶段按 t/T 三等分硬切换（广域/轮廓/定向/精修）。"""
    pop, vals = ctx.init_pop(p, rng)
    best, bpos = min(zip(vals, pop))
    T = p["max_iter"]
    for it in range(1, T + 1):
        stage = 0 if it / T < 1 / 3 else (1 if it / T < 2 / 3 else 2)
        for i in range(len(pop)):
            r1, r2 = rng.random(), rng.random()
            if stage == 0:  # 广域勘探：围绕 best 展开采样
                cand = ctx.clamp([b * (1 - r1) + x * r2 for x, b in zip(pop[i], bpos)])
            elif stage == 1:  # 轮廓勘探：Levy 式跳跃
                levy = math.exp(rng.uniform(-2, 2)) * math.cos(2 * math.pi * rng.random())
                cand = ctx.clamp([x + levy * (b - x) * r1 for x, b in zip(pop[i], bpos)])
            else:  # 定向开发+精修：向 best 收缩
                cand = ctx.clamp([b * (1 - r1) + x * r1 * 0.5 + rng.gauss(0, 0.05)
                                  for x, b in zip(pop[i], bpos)])
            c = ctx.eval(cand)
            if c < vals[i]:
                pop[i], vals[i] = cand, c
            if c < best:
                best, bpos = c, list(cand)
        yield _cn_state(ctx, it, best, bpos, pop, vals)


def _cn_cem(ctx, p, rng):
    """交叉熵 CEM（Rubinstein 1997）连续经典：高斯分布采样→精英回写 mean/std。
    修复（2026-09-27）：① best 跨代保持 ② mean 向 best-so-far 锚定防漂移
    ③ 停滞重启（std 弹回 1/2 初始值）——多峰 rastrigin 的分布重启机制。"""
    n_pop = p["n_pop"]
    warm = [ctx.random(rng) for _ in range(30)]
    mean = list(min(warm, key=ctx.eval))
    std0 = [(ctx.hi - ctx.lo) / 3] * ctx.dim
    std = list(std0)
    best, bpos = None, None
    stall = 0
    for it in range(1, p["max_iter"] + 1):
        pop = [ctx.clamp([rng.gauss(mean[k], max(std[k], 1e-6)) for k in range(ctx.dim)])
               for _ in range(n_pop)]
        vals = [ctx.eval(x) for x in pop]
        # best 跨代保持
        gen_best, gen_bp = min(zip(vals, pop))
        if best is None or gen_best < best:
            best, bpos = gen_best, list(gen_bp)
            stall = 0
        else:
            stall += 1
        order = sorted(range(n_pop), key=lambda i: vals[i])[:max(2, n_pop // 2)]
        elite = [pop[i] for i in order]
        new_mean = [sum(x[k] for x in elite) / len(elite) for k in range(ctx.dim)]
        # mean 向 best-so-far 锚定 20%（防精英均值漂移）
        mean = [0.8 * nm + 0.2 * bp for nm, bp in zip(new_mean, bpos)]
        std = [max((max(x[k] for x in elite) - min(x[k] for x in elite)) / 2,
                   0.01 * (ctx.hi - ctx.lo)) for k in range(ctx.dim)]
        # 停滞重启：连续 30 代无改进 → std 弹回 1/2 初始（分布重启）
        if stall >= 30:
            std = [s0 / 2 for s0 in std0]
            stall = 0
        yield _cn_state(ctx, it, best, bpos, pop, vals)



def _cn_sma(ctx, p, rng):
    """黏菌 SMA（Li 2020）连续经典：权重 W 按适应度排序对数化，vb/vc 双系数调度探索-开发。"""
    pop, vals = ctx.init_pop(p, rng)
    best, bpos = min(zip(vals, pop))
    vb, vc = 1.0, 1.0
    z = 0.05
    for it in range(1, p["max_iter"] + 1):
        order = sorted(range(len(pop)), key=lambda i: vals[i])
        worst, bestv = vals[order[-1]], vals[order[0]]
        span = max(1e-12, worst - bestv)
        W = []
        for rank, idx in enumerate(order):
            ratio = (worst - vals[idx]) / span
            W.append(1.0 + rng.random() * math.log(ratio + 1.0) if rank < len(order) // 2
                     else 1.0 - rng.random() * math.log(ratio + 1.0))
        for i in range(len(pop)):
            r = rng.random()
            if r < z:
                pop[i] = ctx.random(rng)
            elif r < 0.5 + z / 2:
                j = order[rng.randrange(max(1, len(order) // 2))]
                pop[i] = ctx.clamp([x + vb * rng.random() * (W[j] * a - b)
                                    for x, a, b in zip(pop[i], pop[j], pop[order[-1]])])
            else:
                pop[i] = ctx.clamp([vc * x for x in pop[i]])
            vals[i] = ctx.eval(pop[i])
        cb, cp = min(zip(vals, pop))
        if cb < best:  # 上报历史最优：只降不升（原先每代取当代种群的最优，会变差）
            best, bpos = cb, list(cp)
        vb *= math.exp(-2 * it / p["max_iter"])
        vc = 1 - it / p["max_iter"]
        yield _cn_state(ctx, it, best, bpos, pop, vals)


_CN_ALGOS = {
    "random": {"fn": _cn_random, "name": "随机搜索", "category": "基线", "desc": "盲采样基线", "tune": []},
    "hc": {"fn": _cn_hc, "name": "爬山法 HC", "category": "局部搜索", "desc": "高斯步长贪心 + 多起点重启", "tune": ["sigma", "restart_at"]},
    "sa": {"fn": _cn_sa, "name": "模拟退火 SA", "category": "物理启发", "desc": "连续域 Metropolis + 卡死重启", "tune": ["t0", "decay", "restart_at"]},
    "pso": {"fn": _cn_pso, "name": "粒子群 PSO", "category": "群体智能", "desc": "原生域！速度-位置公式原样", "tune": ["w_max", "w_min", "c1", "c2"]},
    "de": {"fn": _cn_de, "name": "差分进化 DE", "category": "进化计算", "desc": "原生域！差向量实数运算", "tune": ["F", "CR"]},
    "gwo": {"fn": _cn_gwo, "name": "灰狼 GWO", "category": "群体智能", "desc": "原生域！三狼包围", "tune": []},
    "woa": {"fn": _cn_woa, "name": "鲸鱼 WOA", "category": "群体智能", "desc": "原生域！包围/螺旋", "tune": []},
    "sca": {"fn": _cn_sca, "name": "正弦余弦 SCA", "category": "数学启发", "desc": "原生域！三角振荡包围", "tune": ["a_max"]},
    "cmaes": {"fn": _cn_cmaes, "name": "协方差自适应 CMA-ES", "category": "进化计算", "desc": "原生域！全协方差自适应 + σ/进化路径（连续域 SOTA）", "tune": []},
    # ---- 连续域扩容（2026-09-27 ROADMAP 批 1：12 个正典连续公式）----
    "fa": {"fn": _cn_fa, "name": "萤火虫 FA", "category": "群体智能", "desc": "原生域！亮度吸引 + 距离衰减 + α 扰动衰减", "tune": []},
    "ba": {"fn": _cn_ba, "name": "蝙蝠 BA", "category": "群体智能", "desc": "原生域！频率调谐 + 响度/脉冲率自适应", "tune": []},
    "jaya": {"fn": _cn_jaya, "name": "Jaya 算法 JAYA", "category": "群体智能", "desc": "原生域！向最优+远离最劣，零专属参数", "tune": []},
    "gsa": {"fn": _cn_gsa, "name": "引力搜索 GSA", "category": "物理启发", "desc": "原生域！质量=归一化适应度，引力驱动（速度阻尼版）", "tune": []},
    "mfo": {"fn": _cn_mfo, "name": "蛾焰 MFO", "category": "群体智能", "desc": "原生域！螺旋飞行绕火焰，焰数递减", "tune": []},
    "tlbo": {"fn": _cn_tlbo, "name": "教与学 TLBO", "category": "人类与社会启发", "desc": "原生域！教师/学习两阶段，零专属参数", "tune": []},
    "hs": {"fn": _cn_hs, "name": "和声搜索 HS", "category": "音乐启发", "desc": "原生域！HMCR 三路即兴，多和声并行", "tune": []},
    "abc": {"fn": _cn_abc, "name": "人工蜂群 ABC", "category": "群体智能", "desc": "原生域！雇佣/观察/侦察三蜂协作", "tune": []},
    "eo": {"fn": _cn_eo, "name": "均衡优化 EO", "category": "物理启发", "desc": "原生域！均衡池 4+1 + 生成率 clamp[0,1]", "tune": []},
    "ao": {"fn": _cn_ao, "name": "天鹰 AO", "category": "群体智能", "desc": "原生域！四阶段三等分硬切换调度", "tune": []},
    "cem": {"fn": _cn_cem, "name": "交叉熵 CEM", "category": "进化计算", "desc": "原生域！EDA 源头：热启动+分布收缩采样→精英回写", "tune": []},
    "sma": {"fn": _cn_sma, "name": "黏菌 SMA", "category": "物理启发", "desc": "原生域！权重对数化 + vb/vc 调度", "tune": []},
}
_MO_ALGOS = {
    "random": {"fn": _mo_random, "name": "随机搜索", "category": "基线", "desc": "非支配档案累积基线", "tune": []},
    "wsga": {"fn": _mo_wsga, "name": "加权 GA", "category": "进化计算", "desc": "每代随机权重合成单目标（会漏非凸段）", "tune": ["pm"]},
    "nsga2": {"fn": _mo_nsga2, "name": "NSGA-II", "category": "进化计算", "desc": "非支配排序 + 拥挤度（Deb 2002，引用数万）", "tune": ["pc"]},
    "moead": {"fn": _mo_moead, "name": "MOEA-D（分解）", "category": "进化计算",
              "desc": "Tchebycheff 分解+权重邻域+理想点追踪（Zhang & Li 2007，经典）", "tune": []},
    "spea2": {"fn": _mo_spea2, "name": "SPEA2（强度Pareto）", "category": "进化计算",
              "desc": "强度Pareto 适应度+密度截断 archive（Zitzler 2001，经典）", "tune": []},
}

_GC_ALGOS = _pm_registry("gc")
_BP_ALGOS = _pm_registry("bp")
_SC_ALGOS = dict(_SW_ALGOS, **{
    "greedy": {"fn": _sc_greedy, "name": "贪心 ln n", "category": "构造启发",
               "desc": "Chvátal 1979：每次选 新覆盖/成本 比最高集合（近似保证 ln n）", "tune": []},
})

# ---- H 期 kpvar（背包家族 10 变体）注册表：位编码变体复用 _KS 全套内核
# （max-sense 包装器），mkpm 复用 _GAP 指派内核；ssp/cmp 各挂专属精确 DP 锚点。 ----
_KS_FNS = frozenset(a["fn"] for a in _KS_ALGOS.values())
_KPV_ALGOS = dict(_KS_ALGOS, **{
    "greedy": {"fn": _kpv_greedy, "name": "密度贪心", "category": "构造启发",
               "desc": "按价值/重量比降序装入（确定性对照）", "tune": []},
})
_SSP_ALGOS = dict(_KS_ALGOS, **{
    "ssp_dp": {"fn": _kpv_ssp_dp, "name": "精确 DP", "category": "构造启发",
               "desc": "子集和伪多项式精确算法：reach 集合 DP + 回溯（SSP 专属锚点）",
               "tune": []},
})
_CMP_ALGOS = dict(_KS_ALGOS, **{
    "cmp_dp": {"fn": _kpv_cmp_dp, "name": "精确 DP", "category": "构造启发",
               "desc": "找零伪多项式精确算法：min-coin DP + 回溯（Change-Making 专属锚点）",
               "tune": []},
})
_MKPM_ALGOS = dict(_GAP_ALGOS, **{
    "greedy": {"fn": _kpv_greedy, "name": "密度贪心", "category": "构造启发",
               "desc": "全局密度降序，能放则放（确定性对照）", "tune": []},
})
_MCKP_ALGOS = dict(_KS_ALGOS, **{
    "greedy": {"fn": _kpv_greedy, "name": "密度贪心", "category": "构造启发",
               "desc": "每类选密度最高件，全局降序装入（确定性对照）", "tune": []},
})
# kpvar 全算法并集（_DOMAINS 注册用；实际可用集按变体在 domain_list/domain_start 分派）
_KPVAR_ALGOS = dict(_KS_ALGOS, **_GAP_ALGOS,
                    greedy=_KPV_ALGOS["greedy"],
                    ssp_dp=_SSP_ALGOS["ssp_dp"], cmp_dp=_CMP_ALGOS["cmp_dp"])

_KS_DEF = {"n_pop": 30, "pm": 0.04, "F": 0.7, "CR": 0.6, "t0": 8.0, "decay": 0.985,
           "tries": 20, "tenure": 8, "limit": 12, "pa": 0.25, "max_iter": 200, "seed": 7}
_CN_DEF = {"n_pop": 30, "sigma": 0.6, "t0": 10.0, "decay": 0.98, "w_max": 0.9, "w_min": 0.4,
           "c1": 1.5, "c2": 1.5, "F": 0.7, "CR": 0.9, "a_max": 2.0, "restart_at": 25,
           "max_iter": 200, "seed": 7}
_MO_DEF = {"n_pop": 40, "pc": 0.9, "pm": 0.04, "max_iter": 150, "seed": 7}
_GC_DEF = {"n_pop": 30, "pm": 0.3, "t0": 800.0, "decay": 0.985, "tries": 40, "tenure": 10,
           "ts_sample": 120, "limit": 14, "pa": 0.25, "polish": 8, "restart_at": 25,
           "max_iter": 200, "seed": 7}
# gcvar 复用图着色内核，但 edgecolor/totalcolor 经线图/全图变换后 N 暴涨到 ~400，
# ts_sample=120 会让 TS 在 O(N²) 解码下卡死浏览器/测试；gcvar 单独降到 36（与 N 解耦）。
_GCVAR_DEF = dict(_GC_DEF, ts_sample=36)
_BP_DEF = dict(_GC_DEF, t0=4000.0, decay=0.99, restart_at=12, polish=40)
# 注：温度/重启节奏/下探预算按「参数种子=实例种子」（页面真实语义）标定：
# 随机基线 = best-of-200 偶有运气样本，SA 单链必须靠高频重启+强下探追平（5/5 胜随机）

_BIN_DEF = {"n_pop": 30, "pm": 0.04, "t0": 30.0, "decay": 0.98, "tries": 20,
            "tenure": 8, "ts_sample": 40, "restart_at": 25, "max_iter": 200, "seed": 7,
            "walk_p": 0.45}
_SC_DEF = dict(_BIN_DEF)
_SAT_DEF = dict(_BIN_DEF, t0=3.0)
_QB_DEF = dict(_BIN_DEF, t0=120.0)
_GAP_DEF = dict(_BIN_DEF, t0=25.0, decay=0.97)  # 标定：t0=60 冷得太慢，100 代内摸不到低温区
_UF_DEF = dict(_BIN_DEF, t0=400.0)

# ---- H2 期 gcvar（着色家族 5 变体）注册表：4 个排列变体复用 _pm_* 内核 + 度序贪心锚点；
# mis 复用 _bin_* 位串内核 + 度升序贪心锚点。 ----
_GCV_ALGOS = dict(_pm_registry("gc"), **{
    "greedy": {"fn": _gcv_greedy, "name": "度序贪心", "category": "构造启发",
               "desc": "顶点按度数降序 First-Fit 着色（确定性对照）", "tune": []},
})
_MIS_ALGOS = dict(_BIN_ALGOS, **{
    "greedy": {"fn": _mis_greedy, "name": "度升序贪心（MIS）", "category": "构造启发",
               "desc": "度小者优先入集，冲突即跳过（确定性对照）", "tune": []},
})
_GCVAR_ALGOS = dict(_GCV_ALGOS, **{k: v for k, v in _MIS_ALGOS.items() if k not in _GCV_ALGOS})

# ---- H3 期 bpvar（装箱变体家族 3 变体）注册表：复用 _pm_* 排列内核 + 构造贪心锚点。 ----
_BPVAR_ALGOS = dict(_pm_registry("bp"), **{
    "greedy": {"fn": _bpv_greedy, "name": "构造贪心", "category": "构造启发",
               "desc": "定向序 First-Fit（VSBPP 最差适应；2D/条带面积降序 shelf）确定性对照", "tune": []},
})
# 装箱 FF 解码器 plateau 巨大，沿用 binpack 标定（t0=4000/decay=0.99/高频重启）；
# ts_sample 降到 60（2D 解码比 1D 贵，n=40 仍远快于 gcvar 的 N~400 变换）
_BPVAR_DEF = dict(_BP_DEF, ts_sample=60)




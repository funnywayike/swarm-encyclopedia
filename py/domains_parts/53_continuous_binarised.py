# ---- M1 续批 A：连续系二值化（sigmoid 通用模式，全部 min 协议）----
def _bv_pso(ctx, p, rng):
    """PSO 位向量版：速度-位置 + sigmoid 映射（Kennedy & Eberhart 1997 原型）。"""
    n_pop, n_dim = p.get("n_pop", 30), ctx.n
    pos = [_bin_rand_pos(rng, n_dim) for _ in range(n_pop)]
    vel = [[0.0] * n_dim for _ in range(n_pop)]
    bits = [_bin_rep(ctx, _bin_decode(v)) for v in pos]
    vals = [ctx.obj(b) for b in bits]
    best = min(vals)
    gbest = list(bits[vals.index(best)])
    pbest = [list(b) for b in bits]
    pval = list(vals)
    for it in range(1, p["max_iter"] + 1):
        for i in range(n_pop):
            for k in range(n_dim):
                r1, r2 = rng.random(), rng.random()
                pg = 4.0 if pbest[i][k] == 1 else -4.0
                gg = 4.0 if gbest[k] == 1 else -4.0
                vel[i][k] = 0.5 * vel[i][k] + 1.5 * r1 * (pg - pos[i][k]) + 1.5 * r2 * (gg - pos[i][k])
                pos[i][k] = max(-6.0, min(6.0, pos[i][k] + vel[i][k]))
            b = _bin_rep(ctx, _bin_decode(pos[i]))
            v = ctx.obj(b)
            if v < pval[i]:
                pbest[i], pval[i] = list(b), v
                if v < best:
                    best, gbest = v, list(b)
            elif v < vals[i]:
                bits[i], vals[i] = b, v
        yield {"iter": it, "best": best, "best_sol": list(gbest), "cur": sum(vals) / len(vals)}

def _bv_sca(ctx, p, rng):
    """SCA 位向量版：正弦余弦更新规则 + sigmoid 映射（Mirjalili 2016）。"""
    n_pop, n_dim = p.get("n_pop", 30), ctx.n
    pos = [_bin_rand_pos(rng, n_dim) for _ in range(n_pop)]
    bits = [_bin_rep(ctx, _bin_decode(v)) for v in pos]
    vals = [ctx.obj(b) for b in bits]
    best = min(vals)
    gbest = list(bits[vals.index(best)])
    for it in range(1, p["max_iter"] + 1):
        r1 = 2.0 - 2.0 * it / p["max_iter"]  # 线性递减 [2,0]
        for i in range(n_pop):
            r2, r3, r4 = 6.28318 * rng.random(), 2.0 * rng.random(), rng.random()
            for k in range(n_dim):
                g = 4.0 if gbest[k] == 1 else -4.0
                # 标准 SCA（Mirjalili 2016）：r4 切换 sin/cos，r3 为目的地权重
                step = r1 * (_math.sin(r2) if r4 < 0.5 else _math.cos(r2)) * abs(r3 * g - pos[i][k])
                pos[i][k] = max(-6.0, min(6.0, pos[i][k] + step))
            b = _bin_rep(ctx, _bin_decode(pos[i]))
            v = ctx.obj(b)
            if v < vals[i]:
                bits[i], vals[i] = b, v
                if v < best:
                    best, gbest = v, list(b)
        yield {"iter": it, "best": best, "best_sol": list(gbest), "cur": sum(vals) / len(vals)}

def _bv_mfo(ctx, p, rng):
    """MFO 位向量版：蛾焰螺旋 + sigmoid 映射（Mirjalili 2015）。"""
    import math as _m
    n_pop, n_dim = p.get("n_pop", 30), ctx.n
    pos = [_bin_rand_pos(rng, n_dim) for _ in range(n_pop)]
    bits = [_bin_rep(ctx, _bin_decode(v)) for v in pos]
    vals = [ctx.obj(b) for b in bits]
    for it in range(1, p["max_iter"] + 1):
        flame_num = int(round(n_pop - (n_pop - 1) * it / p["max_iter"]))  # 正典多焰递减
        order = sorted(range(n_pop), key=lambda i: vals[i])
        flames = [[4.0 if b == 1 else -4.0 for b in bits[oi]] for oi in order]
        t_dec = -1.0 + it * (-1.0 / p["max_iter"])  # [0,-1] 线性递减
        for i in range(n_pop):
            flame = flames[min(i, flame_num - 1)]  # 前 flame_num 对号入座，其余逼近末焰
            t = rng.uniform(t_dec, 1.0)
            for k in range(n_dim):
                dist = abs(flame[k] - pos[i][k])
                pos[i][k] = max(-6.0, min(6.0,
                    dist * _m.exp(1.0 * t) * _m.cos(2 * 3.14159 * t) + flame[k]))
            b = _bin_rep(ctx, _bin_decode(pos[i]))
            v = ctx.obj(b)
            if v < vals[i]:
                bits[i], vals[i] = b, v
        best = min(vals)
        yield {"iter": it, "best": best, "best_sol": list(bits[vals.index(best)]), "cur": sum(vals) / len(vals)}

def _bv_gsa(ctx, p, rng):
    """GSA 位向量版：引力加速 + sigmoid 映射（Rashedi 2009）。"""
    n_pop, n_dim = p.get("n_pop", 30), ctx.n
    pos = [_bin_rand_pos(rng, n_dim) for _ in range(n_pop)]
    vel = [[0.0] * n_dim for _ in range(n_pop)]
    bits = [_bin_rep(ctx, _bin_decode(v)) for v in pos]
    vals = [ctx.obj(b) for b in bits]
    best = min(vals)
    gbest = list(bits[vals.index(best)])
    G0 = 1.0
    for it in range(1, p["max_iter"] + 1):
        G = G0 * (1.0 - it / (p["max_iter"] + 1)) ** 2
        worst = max(vals)
        m = [max(0.0, (worst - v) / max(1e-12, worst - min(vals))) for v in vals]
        mt = sum(m) or 1.0
        m = [x / mt for x in m]
        for i in range(n_pop):
            for k in range(n_dim):
                f = sum(m[j] * rng.random() * (pos[j][k] - pos[i][k]) / (abs(pos[j][k] - pos[i][k]) + 0.05)
                        for j in range(n_pop) if j != i)
                vel[i][k] = 0.7 * vel[i][k] + f * G
                pos[i][k] = max(-6.0, min(6.0, pos[i][k] + vel[i][k]))
            b = _bin_rep(ctx, _bin_decode(pos[i]))
            v = ctx.obj(b)
            if v < vals[i]:
                bits[i], vals[i] = b, v
                if v < best:
                    best, gbest = v, list(b)
        yield {"iter": it, "best": best, "best_sol": list(gbest), "cur": sum(vals) / len(vals)}

# ---- QUBO/SAT 温度适配层（complete-a-kernels 2026-09-29）----
def _qb_sca(ctx, p, rng):
    """qubo 温度适配 SCA：软阈值 sigmoid 解码(T=1.6)+gbest 每代 5 次位翻抛光。
    针对 QUBO 大范围负目标 sigmoid 系探索不足（原 _bv_sca 严口径负 -386 vs -404）。
    min 域（obj=二次型能量）。"""
    n_pop, n_dim = p.get("n_pop", 30), ctx.n
    T = 1.6
    def decode(v):
        return _bin_rep(ctx, [1 if _sig(x / T) > 0.5 else 0 for x in v])
    pos = [_bin_rand_pos(rng, n_dim) for _ in range(n_pop)]
    bits = [decode(v) for v in pos]
    vals = [ctx.obj(b) for b in bits]
    best = min(vals); gbest = list(bits[vals.index(best)])
    for it in range(1, p["max_iter"] + 1):
        r1 = 2.0 - 2.0 * it / p["max_iter"]
        for i in range(n_pop):
            r2, r3, r4 = 6.28318 * rng.random(), 2.0 * rng.random(), rng.random()
            for k in range(n_dim):
                g = 4.0 if gbest[k] == 1 else -4.0
                step = r1 * (_math.sin(r2) if r4 < 0.5 else _math.cos(r2)) * abs(r3 * g - pos[i][k])
                pos[i][k] = max(-6.0, min(6.0, pos[i][k] + step))
            b = decode(pos[i]); v = ctx.obj(b)
            if v < vals[i]:
                bits[i], vals[i] = b, v
                if v < best:
                    best, gbest = v, list(b)
        for _ in range(5):
            k = rng.randrange(n_dim); nb = list(gbest); nb[k] ^= 1; nb = _bin_rep(ctx, nb)
            nv = ctx.obj(nb)
            if nv < best:
                best, gbest = nv, nb
        yield {"iter": it, "best": best, "best_sol": list(gbest), "cur": sum(vals) / len(vals)}


def _sat_mfo(ctx, p, rng):
    """sat 温度适配 MFO：软阈值 sigmoid 解码(T=1.5)+gbest 每代 6 次位翻抛光。
    替代原 _bv_mfo（sat 严口径负 8 vs 7）。min 域（obj=未满足子句数）。"""
    n_pop, n_dim = p.get("n_pop", 30), ctx.n
    T = 1.5
    def decode(v):
        return _bin_rep(ctx, [1 if _sig(x / T) > 0.5 else 0 for x in v])
    pos = [_bin_rand_pos(rng, n_dim) for _ in range(n_pop)]
    bits = [decode(v) for v in pos]
    vals = [ctx.obj(b) for b in bits]
    for it in range(1, p["max_iter"] + 1):
        flame_num = int(round(n_pop - (n_pop - 1) * it / p["max_iter"]))
        order = sorted(range(n_pop), key=lambda i: vals[i])
        flames = [[4.0 if b == 1 else -4.0 for b in bits[oi]] for oi in order]
        t_dec = -1.0 + it * (-1.0 / p["max_iter"])
        for i in range(n_pop):
            flame = flames[min(i, flame_num - 1)]
            t = rng.uniform(t_dec, 1.0)
            for k in range(n_dim):
                dist = abs(flame[k] - pos[i][k])
                pos[i][k] = max(-6.0, min(6.0, dist * _math.exp(1.0 * t) * _math.cos(2 * 3.14159 * t) + flame[k]))
            b = decode(pos[i]); v = ctx.obj(b)
            if v < vals[i]:
                bits[i], vals[i] = b, v
        bi = vals.index(min(vals)); best = vals[bi]; gbest = list(bits[bi])
        for _ in range(6):
            k = rng.randrange(n_dim); nb = list(gbest); nb[k] ^= 1; nb = _bin_rep(ctx, nb)
            nv = ctx.obj(nb)
            if nv < best:
                best, gbest = nv, nb
                bits[bi], vals[bi] = nb, nv  # 抛光的改进要写回种群，否则下一代 min(vals) 把它丢了，上报的最优会变差
        yield {"iter": it, "best": best, "best_sol": list(gbest), "cur": sum(vals) / len(vals)}


_SW_ALGOS = {
    "random": {"fn": _sw_random, "name": "随机搜索", "category": "基线",
               "desc": "盲采样基线：一切算法都要显著降低目标", "tune": []},
    "hc": {"fn": _sw_hc, "name": "爬山法 HC", "category": "局部搜索",
           "desc": "「关一开一」交换邻域贪心（修复式编码的标准邻域）", "tune": ["tries"]},
    "sa": {"fn": _sw_sa, "name": "模拟退火 SA", "category": "物理启发",
           "desc": "交换移动 + Metropolis 准则 + 卡死重启", "tune": ["t0", "decay"]},
    "ts": {"fn": _sw_ts, "name": "禁忌搜索 TS", "category": "局部搜索",
           "desc": "交换禁忌表 + 采样邻域 + 特赦准则", "tune": ["tenure"]},
    "ga": {"fn": _sw_ga, "name": "遗传 GA", "category": "进化计算",
           "desc": "均匀交叉 + 变异 + 叠交换局部移动（memetic）", "tune": ["pm"]},
        # ---- M1 sigmoid 位向量适配（2026-09-27 全矩阵计划）----
        "bv_fa": {"fn": _bv_fa, "name": "萤火虫 FA（位）", "category": "群体智能",
                  "desc": "sigmoid 映射二值化", "tune": []},
        "bv_ba": {"fn": _bv_ba, "name": "蝙蝠 BA（位）", "category": "群体智能",
                  "desc": "频率调谐+sigmoid 映射", "tune": []},
        "bv_jaya": {"fn": _bv_jaya, "name": "Jaya（位）", "category": "群体智能",
                    "desc": "向 best 靠拢+远离 worst", "tune": []},
        "bv_tlbo": {"fn": _bv_tlbo, "name": "TLBO（位）", "category": "人类与社会启发",
                    "desc": "教师/学习 sigmoid 映射", "tune": []},
        # ---- M1 续批 A：连续系二值化（sigmoid 通用模式）----
        "bv_pso": {"fn": _bv_pso, "name": "粒子群 PSO（位）", "category": "群体智能",
                   "desc": "速度-位置+sigmoid（Kennedy & Eberhart 1997 原型）", "tune": []},
        "bv_sca": {"fn": _bv_sca, "name": "正弦余弦 SCA（位）", "category": "群体智能",
                   "desc": "正弦余弦更新+sigmoid（Mirjalili 2016）", "tune": []},
        "bv_mfo": {"fn": _bv_mfo, "name": "蛾焰 MFO（位）", "category": "群体智能",
                   "desc": "经典多焰递减螺旋+sigmoid（Mirjalili 2015，flame 数 n_pop→1）", "tune": []},
        # ---- M1 续批 B ----

        "bv_eo": {"fn": _bv_eo, "name": "均衡 EO（位）", "category": "物理定律",
                  "desc": "均衡候选加权聚合+sigmoid（Faramarzi 2020）", "tune": []},
        "bv_ao": {"fn": _bv_ao, "name": "天鹰 AO（位）", "category": "群体智能",
                  "desc": "经典四阶段：X1 均值扩张/X2 Levy 收缩探索/X3 α-δ 开发/X4 QF 收缩（Abualigah 2021，文献核对修正）", "tune": []},
        "bv_sma": {"fn": _bv_sma, "name": "黏菌 SMA（位）", "category": "群体智能",
                   "desc": "经典位移式 Xb+vb(W·XA−XB)+log 权重+p=tanh 阈值（Li 2020，文献核对修正）", "tune": []},        # ---- M1 续批 C ----
        "bv_cem": {"fn": _bv_cem, "name": "交叉熵 CEM（位）", "category": "进化计算",
                   "desc": "伯努利 CEM：精英频率回写+best 锚定+停滞重启（Rubinstein 1997）", "tune": []},
        "bv_cmaes": {"fn": _bv_cmaes, "name": "CMA-ES（位·对角近似）", "category": "进化计算",
                     "desc": "对角协方差伯努利近似（诚实简化：完整 CMA 矩阵对位编码无意义）", "tune": []},

}



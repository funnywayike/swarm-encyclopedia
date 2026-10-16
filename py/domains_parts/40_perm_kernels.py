# ============================================================
# 域四/五：排列域通用算法库（图着色 + 装箱共用）
# ------------------------------------------------------------
# 两个域同一个范式：编码 = 排列，解码 = 贪心 First-Fit——
#   图着色：按排列顺序给顶点分配最小可用颜色（合法着色由构造保证）
#   装箱：  按排列顺序把物品放进第一个放得下的箱子（FF 装箱）
# 目标都是「min 主指标 + min 次级指标」字典序：
#   图着色 (色数 k, Σci²)——色平方和鼓励空出高编号颜色桶（文献标准 tie-break）
#   装箱   (箱数 b, Σ剩余²)——剩余平方和鼓励箱子塞紧
# 算法内核因此可以只写一份（_pm_* 前缀），域差异全部压进 ctx——
# 这正是「算法内核 = 探索/开发机制，问题绑定 = 编码+邻域+约束」骨架的第二次兑现。
# ============================================================

# _pm_ox / _pm_swap / _pm_insert / _pm_polish 已收编至 py/domain_components.py
# （S1-1 组件化，import 处以 _pm_* 别名保持调用点不变）


def _pm_random(ctx, p, rng):
    best, bc = None, None
    for it in range(1, p["max_iter"] + 1):
        perm = ctx.random(rng)
        c = ctx.decode(perm)
        if bc is None or c < bc:
            best, bc = perm, c
        yield {"iter": it, "best": bc[0], "cur": c[0], "tie": bc[1],
               "best_sol": ctx.solution(best)}


def _pm_hc(ctx, p, rng):
    perm = ctx.random(rng)
    c = ctx.decode(perm)
    best, bc = list(perm), c
    for it in range(1, p["max_iter"] + 1):
        for _ in range(p["tries"]):
            # 交换 70% / 插入 30%：FF 类解码器对「块重排」更敏感——
            # 纯交换在 plateau 上几乎全是等值解，实测会被随机基线反超（教训）
            cand = _pm_swap(perm, rng) if rng.random() < 0.7 else _pm_insert(perm, rng)
            cc = ctx.decode(cand)
            # 平台侧移：等值也接受——FF 解码器的 plateau 巨大，
            # 严格改进版会卡死在首个局部最优（seed21/42 实测被随机基线反超）
            if cc <= c:
                perm, c = cand, cc
        bc, best = bump(bc, best, c, perm, "min")
        yield {"iter": it, "best": bc[0], "cur": c[0], "tie": bc[1],
               "best_sol": ctx.solution(best)}


def _pm_sa(ctx, p, rng):
    perm = ctx.random(rng)
    c = ctx.decode(perm)
    best, bc = list(perm), c
    t0, decay = p["t0"], p["decay"]
    stall = 0
    for it in range(1, p["max_iter"] + 1):
        T = t0 * (decay ** it)
        cand = _pm_swap(perm, rng) if rng.random() < 0.7 else _pm_insert(perm, rng)
        cc = ctx.decode(cand)
        d = ctx.diff(c, cc)
        if d < 0 or (T > 1e-12 and rng.random() < math.exp(-d / T)):
            perm, c = cand, cc
        if c < bc:
            best, bc = list(perm), c
            stall = 0
        else:
            stall += 1
        # 卡死重启（连续域 _cn_sa 同款组件）：回到历史最优 + 扰动 + 小预算下探，
        # 避免单链在 FF 解码器的巨大 plateau 上永久滞留（实测被随机基线反超的教训）
        if stall >= p["restart_at"]:
            perm, c = list(best), bc
            for _ in range(2):
                cand = _pm_swap(perm, rng)
                perm, c = cand, ctx.decode(cand)  # 无条件扰动
            perm = _pm_polish(ctx, perm, rng, p["polish"])
            c = ctx.decode(perm)
            stall = 0
        yield {"iter": it, "best": bc[0], "cur": c[0], "tie": bc[1],
               "best_sol": ctx.solution(best)}


def _pm_ts(ctx, p, rng):
    perm = ctx.random(rng)
    c = ctx.decode(perm)
    best, bc = list(perm), c
    tabu = {}
    tenure, sample = p["tenure"], p["ts_sample"]
    n = ctx.n
    for it in range(1, p["max_iter"] + 1):
        bm, bcc, bkey = None, None, None
        for _ in range(sample):
            i, j = sorted(rng.sample(range(n), 2))
            key = (i, j)
            cand = list(perm)
            cand[i], cand[j] = cand[j], cand[i]
            cc = ctx.decode(cand)
            # 特赦准则：禁忌移动若刷新历史最优也放行
            if tabu.get(key, -1) >= it and not (bc is None or cc < bc):
                continue
            if bcc is None or cc < bcc:
                bm, bcc, bkey = cand, cc, key
        if bm is None:
            perm = ctx.random(rng)
            c = ctx.decode(perm)
        else:
            perm, c = bm, bcc
            tabu[bkey] = it + tenure
        bc, best = bump(bc, best, c, perm, "min")
        yield {"iter": it, "best": bc[0], "cur": c[0], "tie": bc[1],
               "best_sol": ctx.solution(best)}


def _pm_ga(ctx, p, rng):
    pop = [ctx.random(rng) for _ in range(p["n_pop"])]
    costs = [ctx.decode(x) for x in pop]
    bi = argbest(costs, "min")
    best, bc = list(pop[bi]), costs[bi]
    for it in range(1, p["max_iter"] + 1):
        new = [list(pop[bi])]  # 精英保留
        while len(new) < p["n_pop"]:
            a, b = rng.sample(range(p["n_pop"]), 2)
            child = _pm_ox(pop[a], pop[b], rng)
            if rng.random() < p["pm"]:
                child = _pm_swap(child, rng)
            new.append(child)
        pop = new
        costs = [ctx.decode(x) for x in pop]
        bi = argbest(costs, "min")
        # memetic：每代对当代最优做小预算下探
        cand = _pm_polish(ctx, pop[bi], rng, p["polish"])
        cc = ctx.decode(cand)
        if cc < costs[bi]:
            pop[bi], costs[bi] = cand, cc
        bc, best = bump(bc, best, costs[bi], pop[bi], "min")
        yield {"iter": it, "best": bc[0], "cur": min(c[0] for c in costs), "tie": bc[1],
               "best_sol": ctx.solution(best)}


def _pm_de(ctx, p, rng):
    """排列版差分 DE（批 7 续）：三父体逐位差异——r1/r2 不同的位置以 F 概率借 r3 的值，
    OX 式修复保持排列合法（重复值按序重排）。贪心接受。"""
    perm = ctx.random(rng)
    c = ctx.decode(perm)
    best, bc = list(perm), c
    F = p.get("F", 0.7)
    n = len(perm)
    for it in range(1, p["max_iter"] + 1):
        r1, r2, r3 = rng.sample(range(n), 3)
        cand = list(perm)
        for k in range(n):
            if perm[r1] != perm[r2] and rng.random() < F:
                # 借 r3 序列该位的值：找到 cand 中该值的位置换到 k
                val = perm[r3]
                pos = cand.index(val) if val in cand else k
                cand[k], cand[pos] = cand[pos], cand[k]
        cand = _pm_ox_repair(cand, perm)  # OX 式修复：以 perm 为参照保相对序
        cand = _pm_polish(ctx, cand, rng, 8)  # memetic 打磨（与 gwo 同款补救）
        cc = ctx.decode(cand)
        if cc <= c:
            perm, c = cand, cc
        bc, best = bump(bc, best, cc, perm, "min")
        yield {"iter": it, "best": bc[0], "cur": c[0], "tie": bc[1],
               "best_sol": ctx.solution(best)}


def _pm_ox_repair(child, ref):
    """OX 式修复：child 中缺失的值按 ref 相对序补回（保持排列合法）。"""
    present = [v for v in child if v in child[:len(child)]]
    missing = [v for v in ref if v not in child]
    seen = set()
    out = []
    for v in child:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out + [v for v in missing if v not in seen]


def _pm_gwo(ctx, p, rng):
    """排列版灰狼 GWO（批 7 续）：α/β/δ 三狼轮流当 OX 父体——
    每个个体以 1/3 概率选一头狼做 OX 交叉，贪心接受。"""
    perm = ctx.random(rng)
    c = ctx.decode(perm)
    best, bc = list(perm), c
    pop = [list(perm)]
    popv = [c]
    for it in range(1, p["max_iter"] + 1):
        order = sorted(range(len(pop)), key=lambda i: popv[i])
        wolves = [pop[order[k]] for k in range(min(3, len(pop)))]
        for i in range(len(pop)):
            wolf = wolves[rng.randrange(len(wolves))]
            cand = _pm_ox(pop[i], wolf, rng)
            cand = _pm_polish(ctx, cand, rng, 8)  # memetic 打磨：OX 后局部搜索（弱 GWO 的补救）
            cc = ctx.decode(cand)
            if cc <= popv[i]:
                pop[i], popv[i] = cand, cc
            if cc < c:
                perm, c = list(cand), cc
        pop.sort(key=lambda x: 0)  # 保序（pop 与 popv 同步）
        popv = [ctx.decode(x) for x in pop]
        bc, best = bump(bc, best, c, perm, "min")
        yield {"iter": it, "best": bc[0], "cur": c[0], "tie": bc[1],
               "best_sol": ctx.solution(best)}


def _pm_cs(ctx, p, rng):
    """排列版布谷鸟 CS（批 7 续）：莱维 swap 串（幂律步长）+ 弃巢重置（pa 概率换最差）。"""
    perm = ctx.random(rng)
    c = ctx.decode(perm)
    best, bc = list(perm), c
    pa = p.get("pa", 0.25)
    for it in range(1, p["max_iter"] + 1):
        i = rng.randrange(len(perm))
        levy = int(rng.paretovariate(1.5))
        cand = list(perm)
        for _ in range(min(levy + 1, 8)):
            cand = _pm_swap(cand, rng) if rng.random() < 0.7 else _pm_insert(cand, rng)
        cc = ctx.decode(cand)
        if cc <= c:
            perm, c = cand, cc
        if rng.random() < pa:  # 弃巢：重置最差个体
            perm = ctx.random(rng)
            c = ctx.decode(perm)
        bc, best = bump(bc, best, c, perm, "min")
        yield {"iter": it, "best": bc[0], "cur": c[0], "tie": bc[1],
               "best_sol": ctx.solution(best)}


def _pm_abc(ctx, p, rng):
    pop = [ctx.random(rng) for _ in range(p["n_pop"])]
    costs = [ctx.decode(x) for x in pop]
    stuck = [0] * p["n_pop"]
    bi = argbest(costs, "min")
    best, bc = list(pop[bi]), costs[bi]

    def _learn(i, base):
        if rng.random() < 0.5:
            cand = _pm_ox(pop[base], pop[i], rng)  # 向最优学片段
        else:
            cand = _pm_swap(pop[i], rng)
        if rng.random() < 0.3:
            cand = _pm_insert(cand, rng)
        cc = ctx.decode(cand)
        if cc < costs[i]:
            pop[i], costs[i], stuck[i] = cand, cc, 0
        else:
            stuck[i] += 1

    for it in range(1, p["max_iter"] + 1):
        bi = argbest(costs, "min")
        for i in range(p["n_pop"]):  # 雇佣蜂
            _learn(i, bi)
        mains = [c[0] for c in costs]
        w = [1.0 / (1.0 + m) for m in mains]  # 箱数/色数越小越被跟
        tot = sum(w)
        for _ in range(p["n_pop"]):  # 观察蜂（轮盘）
            r, acc = rng.random() * tot, 0.0
            for i in range(p["n_pop"]):
                acc += w[i]
                if acc >= r:
                    break
            _learn(i, bi)
        for i in range(p["n_pop"]):  # 侦察蜂
            if stuck[i] > p["limit"]:
                pop[i] = ctx.random(rng)
                costs[i] = ctx.decode(pop[i])
                stuck[i] = 0
        bi = argbest(costs, "min")
        bc, best = bump(bc, best, costs[bi], pop[bi], "min")
        yield {"iter": it, "best": bc[0], "cur": min(c[0] for c in costs), "tie": bc[1],
               "best_sol": ctx.solution(best)}


def _pm_woa(ctx, p, rng):
    pop = [ctx.random(rng) for _ in range(p["n_pop"])]
    costs = [ctx.decode(x) for x in pop]
    bi = argbest(costs, "min")
    best, bc = list(pop[bi]), costs[bi]
    for it in range(1, p["max_iter"] + 1):
        a = 2.0 * (1 - it / p["max_iter"])
        for i in range(p["n_pop"]):
            if rng.random() < 0.5:  # 包围：从最优取片段（收缩逐步聚焦）
                cand = _pm_ox(pop[bi], pop[i], rng)
            else:  # 螺旋：从随机同伴取片段
                cand = _pm_ox(pop[i], pop[rng.randrange(p["n_pop"])], rng)
            if rng.random() < 0.12 * a + 0.03:  # 后期扰动衰减 → 收缩
                cand = _pm_swap(cand, rng)
            cand = _pm_polish(ctx, cand, rng, 3)
            cc = ctx.decode(cand)
            if greedy_replace(pop, costs, i, cand, cc, "min"):
                bc, best = bump(bc, best, cc, cand, "min")
        yield {"iter": it, "best": bc[0], "cur": min(c[0] for c in costs), "tie": bc[1],
               "best_sol": ctx.solution(best)}


def _pm_registry(tag):
    """两个排列域的算法注册表只差文案，用工厂生成（同内核两域复用的直接证据）。"""
    noun = "色数" if tag == "gc" else "箱数"
    return {
        "random": {"fn": _pm_random, "name": "随机搜索", "category": "基线",
                   "desc": f"随机排列 + First-Fit 盲采样基线：一切算法都要显著降低{noun}", "tune": []},
        "hc": {"fn": _pm_hc, "name": "爬山法 HC", "category": "局部搜索",
               "desc": "交换邻域贪心（每代 tries 次随机交换）", "tune": ["tries"]},
        "sa": {"fn": _pm_sa, "name": "模拟退火 SA", "category": "物理启发",
               "desc": "Metropolis 准则接受暂时变差的交换/插入", "tune": ["t0", "decay"]},
        "ts": {"fn": _pm_ts, "name": "禁忌搜索 TS", "category": "局部搜索",
               "desc": "交换禁忌表 + 特赦准则（禁忌但破纪录则放行）", "tune": ["tenure"]},
        "ga": {"fn": _pm_ga, "name": "遗传 GA", "category": "进化计算",
               "desc": "OX 顺序交叉 + 交换变异 + memetic 打磨", "tune": ["pm"]},
        "abc": {"fn": _pm_abc, "name": "人工蜂群 ABC", "category": "群体智能",
                "desc": "雇佣/观察/侦察三阶段（排列版）", "tune": ["limit"]},
        "woa": {"fn": _pm_woa, "name": "鲸鱼 WOA", "category": "群体智能",
                "desc": "包围/螺旋 = OX 片段继承（排列版）", "tune": []},
        # ---- 批 7 续（2026-09-27）：排列域三内核（de/gwo/cs）——用户令稳步扩容 ----
        "de": {"fn": _pm_de, "name": "差分 DE", "category": "进化计算",
               "desc": "排列版差分：三父体逐位差异 + OX 修复（swap 组合近似）", "tune": ["F"]},
        "gwo": {"fn": _pm_gwo, "name": "灰狼 GWO", "category": "群体智能",
                "desc": "三狼 OX 投票（α/β/δ 轮流当父体）", "tune": []},
        "cs": {"fn": _pm_cs, "name": "布谷鸟 CS", "category": "群体智能",
               "desc": "莱维 swap 串 + 弃巢重置（排列版）", "tune": ["pa"]},
    }



# -*- coding: utf-8 -*-
"""
entryseq（原子词条域）：变体的实例生成器与目标函数。

一个变体 = 两个函数：
    @_maker("名字")      生成实例   fn(variant, n, seed, rng) -> dict
    @_objective("名字")  目标函数   fn(self, s) -> 数值（越小越好）
新增一个变体 = 在本文件加这一对函数，并在 py/registry.py 之外无需再改任何登记表——
VARIANTS 由注册顺序自动得出。

本文件由 domains.py 里原来的 es_make / _ES.obj（两条各数百行的 if 链）机械拆分而来，函数体逐字保留；
拆分前后 tests/golden 快照逐项一致。自包含：只依赖 math / random。
"""
import math
import random

_MAKERS = {}
_OBJS = {}
_DETAIL = {}


def _detail(*variants):
    """页面可视化需要的、由当前最优解推出的附加信息（路线、机器分配、聚类中心、设计变量与约束……）。
    引擎在每个状态里把它并进去；页面只画，不重算。"""
    def deco(fn):
        for v in variants:
            _DETAIL[v] = fn
        return fn
    return deco


def _maker(*variants):
    def deco(fn):
        for v in variants:
            assert v not in _MAKERS, f"变体 {v} 重复登记"
            _MAKERS[v] = fn
        return fn
    return deco


FIDELITY_LEVELS = ("standard", "simplified", "illustrative")
FIDELITY = {}  # 变体 -> {"level": ..., "note": 与标准定义的差异（非 standard 必填）}
ES_ENCODINGS = ("perm", "bits", "real")  # 不叫 ENCODINGS：userproblem.py 里已有同名顶层名字，浏览器里会互相覆盖
ENCODING = {}  # 变体 -> 解的编码：perm 排列（默认）/ bits 位向量（每位选或不选）/ real 实数向量


def _objective(*variants, fidelity, note="", encoding="perm"):
    """登记目标函数。encoding 是解的编码（perm 排列 / bits 位向量 / real 实数向量，默认排列）：它决定该变体用哪一族算法，
    也决定 `ctx.random` 产生什么样的解——所以和目标函数写在一起，不在别处另列清单。fidelity 必填——
        standard     与教科书/文献定义一致，结果可与文献对照
        simplified   问题本身是真的，但解码/约束做了教学级简化，数值不能与文献对照
        illustrative 只借这个问题的名字演示其形态，模型并不是该问题本身
    非 standard 必须写 note：一句话说明「与标准定义的差异」，页面与上传校验都会显示它。"""
    assert fidelity in FIDELITY_LEVELS, fidelity
    assert encoding in ES_ENCODINGS, encoding
    assert fidelity == "standard" or note, f"{variants}: 非 standard 必须写 note"

    def deco(fn):
        for v in variants:
            assert v not in _OBJS, f"变体 {v} 重复登记"
            _OBJS[v] = fn
            FIDELITY[v] = {"level": fidelity, "note": note}
            ENCODING[v] = encoding
        return fn
    return deco


# ============================================================ 实例生成


@_maker('vrp')
def _make_vrp(variant, n, seed, rng):
    # 带容量车辆路径（CVRP）：1 仓库（居中）+ n 个客户；车辆容量按「平均每车 5 个客户左右」定，
    # 车队规模 = 理论最少车数 + 1（留一辆余量，否则随机顺序大多无法切成合法路线）
    k = max(5, min(n, 40))
    pts = [[50.0, 50.0]] + [[round(rng.uniform(0, 100), 2), round(rng.uniform(0, 100), 2)] for _ in range(k)]
    demand = [0] + [rng.randint(1, 9) for _ in range(k)]
    cap = max(max(demand), int(sum(demand) / max(1, round(k / 5))) + 1)
    m_veh = -(-sum(demand) // cap) + 1
    return {"variant": variant, "pts": pts, "demand": demand, "cap": cap,
            "m_veh": m_veh, "n": k}  # n=客户数（pts[0]=仓库）


@_maker('vrptw', 'vrpstw')
def _make_vrptw(variant, n, seed, rng):
    # 带时间窗的车辆路径（VRPTW 硬时间窗；vrpstw 软时间窗共用本生成器）：1 仓库（居中）+ k 个客户，速度 1（行驶时间 = 欧氏距离），服务时间每个客户 10。
    # 先随机造一组满足容量的参考路线，把每个客户在参考路线里的到达时刻 t 当作时间窗的中心：窗 = [t - w/2, t + w/2]（w 取 30..60）。
    # 这样「至少有一个可行解」是构造出来的；仓库的窗 [0, H] 的 H 取「所有参考路线回仓时刻、每个客户单独跑一趟的回仓时刻」的最大值向上取整。
    # 车队规模 = 参考路线数 + 1。
    k = max(5, min(n, 40))
    pts = [[50.0, 50.0]] + [[round(rng.uniform(0, 100), 2), round(rng.uniform(0, 100), 2)] for _ in range(k)]
    demand = [0] + [rng.randint(1, 9) for _ in range(k)]
    cap = max(max(demand), int(sum(demand) / max(1, round(k / 5))) + 1)
    svc = [0] + [10] * k
    order = list(range(1, k + 1))
    rng.shuffle(order)
    ref, cur, load = [], [], 0
    for c in order:
        if load + demand[c] > cap:
            ref.append(cur)
            cur, load = [], 0
        cur.append(c)
        load += demand[c]
    ref.append(cur)
    e, l = [0.0] * (k + 1), [0.0] * (k + 1)
    ret_max = 0.0
    for route in ref:
        t, prev = 0.0, 0
        for c in route:
            t += math.dist(pts[prev], pts[c])
            w = rng.uniform(30, 60)
            e[c], l[c] = round(max(0.0, t - w / 2), 2), round(t + w / 2, 2)
            t += svc[c]
            prev = c
        ret_max = max(ret_max, t + math.dist(pts[prev], pts[0]))
    solo = max(l[c] + svc[c] + math.dist(pts[c], pts[0]) for c in range(1, k + 1))
    H = float(math.ceil(max(ret_max, solo)))
    l[0] = H
    out = {"variant": variant, "pts": pts, "demand": demand, "cap": cap, "m_veh": len(ref) + 1, "n": k,
           "e": e, "l": l, "svc": svc}  # n=客户数；e/l/svc 下标与 pts 一致（0 = 仓库）
    if variant == "vrpstw":
        out["lam"] = 2.0  # 软时间窗：每晚到 1 个时间单位罚 lam 个里程单位（客户窗与仓库关门都算）
    return out


@_maker('mdvrp')
def _make_mdvrp(variant, n, seed, rng):
    # 多车场车辆路径（MDVRP）：D 个仓库（2 或 3 个）+ k 个客户；每个仓库有自己的 m_dep 辆车（同容量 cap），车从自己的仓库出发、回到自己的仓库。
    # 解 = 长度 k + D - 1 的排列：0..k-1 是客户，k..k+D-2 是「仓库分隔符」——第 d 段（分隔符把序列切成 D 段）里的客户归第 d 个仓库。
    k = max(5, min(n, 40))
    D = 2 if k <= 12 else 3
    depots = [[25.0, 50.0], [75.0, 50.0]] if D == 2 else [[25.0, 30.0], [75.0, 30.0], [50.0, 80.0]]
    pts = depots + [[round(rng.uniform(0, 100), 2), round(rng.uniform(0, 100), 2)] for _ in range(k)]
    demand = [0] * D + [rng.randint(1, 9) for _ in range(k)]
    cap = max(max(demand), int(sum(demand) / max(1, round(k / 5))) + 1)
    need = -(-sum(demand) // cap)  # 总车数下限
    m_dep = -(-need // D) + 1  # 按仓库均分，再留一辆余量
    return {"variant": variant, "pts": pts, "demand": demand, "cap": cap, "m_dep": m_dep, "D": D,
            "n": k + D - 1}  # n = 排列长度 = len(pts) - 1；pts 前 D 个是仓库


# ---- 调度 / 路径类标准模型（2026-10 重做）----

_TAI_M = 2147483647


def _tai_unif(seed, low, high):
    """Taillard (1993) 的伪随机数发生器（Lehmer LCG, a=16807）：论文里的基准实例就是用它和公开的种子造出来的。"""
    a, b, c = 16807, 127773, 2836
    k = seed[0] // b
    seed[0] = a * (seed[0] % b) - k * c
    if seed[0] < 0:
        seed[0] += _TAI_M
    return low + int(seed[0] / _TAI_M * (high - low + 1))


@_maker('fss')
def _make_fss(variant, n, seed, rng):
    # 置换流水车间 PFSP：n 个作业 × 5 台机器、加工时间 1–99。n=20 时就是 Taillard 的 ta001（时间种子 873654221，最优 1278）；其余规模用同一发生器造
    nn = max(5, min(n, 20))
    m = 5
    sd = [873654221 if nn == 20 else (seed * 7919 + nn * 104729) % (_TAI_M - 1) + 1]
    p = [[_tai_unif(sd, 1, 99) for _ in range(nn)] for _ in range(m)]
    return {"variant": variant, "p": p, "n": nn, "m_mach": m, "name": "ta001" if nn == 20 else "", "opt": 1278 if nn == 20 else None}


@_maker('oss')
def _make_oss(variant, n, seed, rng):
    # 开放车间：n 个作业 × n 台机器，每个作业在每台机器上各做一次、机器顺序自由；时间 1–99（同 Taillard 开放车间的设定）。排列长度 = n² 个工序
    nn = max(3, min(n, 6))
    sd = [(seed * 6007 + nn * 15485863) % (_TAI_M - 1) + 1]
    t = [[_tai_unif(sd, 1, 99) for _ in range(nn)] for _ in range(nn)]
    lb = max(max(sum(r) for r in t), max(sum(t[j][k] for j in range(nn)) for k in range(nn)))
    return {"variant": variant, "t": t, "n": nn * nn, "n_jobs": nn, "m_mach": nn, "lb": lb}


_FT06 = [[(2, 1), (0, 3), (1, 6), (3, 7), (5, 3), (4, 6)], [(1, 8), (2, 5), (4, 10), (5, 10), (0, 10), (3, 4)],
         [(2, 5), (3, 4), (5, 8), (0, 9), (1, 1), (4, 7)], [(1, 5), (0, 5), (2, 5), (3, 3), (4, 8), (5, 9)],
         [(2, 9), (1, 3), (4, 5), (5, 4), (0, 3), (3, 1)], [(1, 3), (3, 3), (5, 9), (0, 10), (4, 4), (2, 1)]]


@_maker('jss')
def _make_jss(variant, n, seed, rng):
    # 作业车间 JSP：每个作业有自己的机器路线。n=6 时是 Fisher–Thompson 的 ft06（6×6，最优 55）；其余规模随机（5 台机器、时间 1–20、每个作业一条随机路线）
    nn = max(4, min(n, 10))
    if nn == 6:
        jobs, m, name, opt = [[list(op) for op in j] for j in _FT06], 6, "ft06", 55
    else:
        m, name, opt = 5, "", None
        jobs = [[[k, rng.randint(1, 20)] for k in rng.sample(range(m), m)] for _ in range(nn)]
    mload = [0] * m
    for j in jobs:
        for (k, t) in j:
            mload[k] += t
    lb = max(max(mload), max(sum(t for _k, t in j) for j in jobs))
    return {"variant": variant, "jobs": jobs, "n": nn * m, "n_jobs": nn, "m_mach": m, "name": name, "opt": opt, "lb": lb}


@_maker('fjsp')
def _make_fjsp(variant, n, seed, rng):
    # 柔性作业车间：n 个作业各 3 道工序（顺序固定），每道工序可在 2–3 台机器（共 5 台）中的任一台做，时间因机器而异（2–10）
    nn = max(4, min(n, 8))
    m, nops = 5, 3
    jobs = []
    for _ in range(nn):
        ops = []
        for _o in range(nops):
            ks = rng.sample(range(m), rng.randint(2, 3))
            ops.append([[k, rng.randint(2, 10)] for k in sorted(ks)])
        jobs.append(ops)
    lb_job = max(sum(min(t for _k, t in op) for op in j) for j in jobs)
    lb_work = -(-sum(min(t for _k, t in op) for j in jobs for op in j) // m)
    return {"variant": variant, "jobs": jobs, "n": nn * nops, "n_jobs": nn, "m_mach": m, "lb": max(lb_job, lb_work)}


@_maker('hc')
def _make_hc(variant, n, seed, rng):
    # 哈密顿回路：随机图（植入一条哈密顿回路，再以 0.12 的概率加其余边）。目标 = 排列相邻对里「不是边」的个数，0 就找到了回路
    nn = max(6, min(n, 14))
    pts = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(nn)]
    cyc = list(range(nn))
    rng.shuffle(cyc)
    E = {(min(cyc[i], cyc[(i + 1) % nn]), max(cyc[i], cyc[(i + 1) % nn])) for i in range(nn)}
    for a in range(nn):
        for b in range(a + 1, nn):
            if rng.random() < 0.12:
                E.add((a, b))
    return {"variant": variant, "pts": pts, "edges": [list(e) for e in sorted(E)], "n": nn}


@_maker('lpath')
def _make_lpath(variant, n, seed, rng):
    # 最长路径：随机图（植入一条哈密顿路径，权重 5–20；其余边以 0.25 的概率出现，权重 1–20）。目标 = 沿排列走、碰到非边就停时累计的权重（最大化）
    nn = max(6, min(n, 12))
    pts = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(nn)]
    order = list(range(nn))
    rng.shuffle(order)
    W = {}
    for i in range(nn - 1):
        a, b = order[i], order[i + 1]
        W[(min(a, b), max(a, b))] = rng.randint(5, 20)
    for a in range(nn):
        for b in range(a + 1, nn):
            if (a, b) not in W and rng.random() < 0.25:
                W[(a, b)] = rng.randint(1, 20)
    return {"variant": variant, "pts": pts, "edges": [[a, b, w] for (a, b), w in sorted(W.items())], "n": nn}


def _carp_graph(rng, nv):
    """随机路网：每点连最近的 3 个点，再并入最小生成树的边（保证连通）；边费用 = 欧氏长度取整。"""
    pts = [[round(rng.uniform(0, 100), 1), round(rng.uniform(0, 100), 1)] for _ in range(nv)]
    E = set()
    for i in range(nv):
        for j in sorted((j for j in range(nv) if j != i), key=lambda j: math.dist(pts[i], pts[j]))[:3]:
            E.add((min(i, j), max(i, j)))
    par = list(range(nv))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for (d, a, b) in sorted((math.dist(pts[a], pts[b]), a, b) for a in range(nv) for b in range(a + 1, nv)):
        ra, rb = find(a), find(b)
        if ra != rb:
            par[ra] = rb
            E.add((a, b))
    return pts, [[a, b, max(1, round(math.dist(pts[a], pts[b])))] for (a, b) in sorted(E)]


@_maker('carp', 'rpostman')
def _make_carp(variant, n, seed, rng):
    # 弧路由：一张随机路网（14 个路口），其中 n 条边「必须服务」（carp 还带需求量，车容量 20）；rpostman = 不限容量，一条回路覆盖全部必需边
    nr = max(6, min(n, 12))
    nv = 14
    pts, edges = _carp_graph(rng, nv)
    req = sorted(rng.sample(range(len(edges)), min(nr, len(edges))))
    dem = {k: (rng.randint(2, 8) if variant == "carp" else 0) for k in req}
    depot = min(range(nv), key=lambda i: math.dist(pts[i], [50.0, 50.0]))
    return {"variant": variant, "pts": pts, "edges": edges, "req": req, "dem": [dem[k] for k in req], "depot": depot,
            "cap": 20 if variant == "carp" else 10 ** 6, "n": len(req)}


@_maker('lop')
def _make_lop(variant, n, seed, rng):
    # 线性排序：权重矩阵，Σ_{i<j} w[π(j)][π(i)] 最大化
    nn = max(5, min(n, 12))
    w = [[0 if i == j else rng.randint(1, 20) for j in range(nn)] for i in range(nn)]
    return {"variant": variant, "w": w, "n": nn}


@_maker('sms')
def _make_sms(variant, n, seed, rng):
    # 单机总延误
    nn = max(5, min(n, 10))
    p = [rng.randint(2, 12) for _ in range(nn)]
    d = [rng.randint(8, 30) for _ in range(nn)]
    return {"variant": variant, "p": p, "d": d, "n": nn}


@_maker('ctp')
def _make_ctp(variant, n, seed, rng):
    # 课程排课（课程表问题 CTP 的精简版）：n 门课，每门 1–3 节、由某位教师授课、有若干学生；
    # 另有若干「课程组」（同一届学生要修的几门课），同一组、同一教师的课不能在同一个时段；一周 5 天 × 2 节 = 10 个时段，3 间教室（容量 30 / 45 / 60）
    nn = max(4, min(n, 14))
    lec = [rng.randint(1, 3) for _ in range(nn)]
    teacher = [rng.randrange(max(3, nn // 2)) for _ in range(nn)]
    size = [rng.randint(20, 60) for _ in range(nn)]
    groups = [sorted(rng.sample(range(nn), min(3, nn))) for _ in range(max(2, nn // 3))]
    # 每位教师、每个课程组的总课时都不超过 8（= 时段数的 80%）：否则它们的课根本排不进去，实例就是无解的
    while True:
        over = [c for t in set(teacher) for c in range(nn) if teacher[c] == t and sum(lec[x] for x in range(nn) if teacher[x] == t) > 8]
        over += [c for g in groups for c in g if sum(lec[x] for x in g) > 8]
        if not over:
            break
        c = max(over, key=lambda c: lec[c])
        lec[c] = max(1, lec[c] - 1)
    lec_course = [c for c in range(nn) for _ in range(lec[c])]  # 第 k 节课属于哪门课
    return {"variant": variant, "lec": lec, "teacher": teacher, "size": size, "groups": groups, "lec_course": lec_course,
            "days": 5, "slots": 2, "rooms": [30, 45, 60], "n": len(lec_course), "n_courses": nn}


# ---- 批 3：选址族 10 变体（2026-09-27）----

@_maker('lap')
def _make_lap(variant, n, seed, rng):
    # 线性指派：n×n 成本矩阵，排列=指派
    nn = max(6, min(n, 12))
    c = [[rng.randint(1, 30) for _ in range(nn)] for _ in range(nn)]
    return {"variant": variant, "c": c, "n": nn}


@_maker('qap')
def _make_qap(variant, n, seed, rng):
    # 二次分配：流量×距离双矩阵
    nn = max(6, min(n, 10))
    a = [[rng.randint(0, 10) for _ in range(nn)] for _ in range(nn)]
    b = [[rng.randint(1, 20) for _ in range(nn)] for _ in range(nn)]
    return {"variant": variant, "a": a, "b": b, "n": nn}


@_maker('pmedian', 'pcenter')
def _make_pmedian_etc2(variant, n, seed, rng):
    # p-中位/中心：点集 + 前 p 位=设施
    nn = max(8, min(n, 14))
    pts = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(nn)]
    return {"variant": variant, "pts": pts, "p": max(2, nn // 4), "n": nn}


@_maker('cflp')
def _make_cflp(variant, n, seed, rng):
    # 容量设施选址：每个点既是客户（需求 dem）也是候选设施（容量 cap、固定开设费 fc）；容量总和远大于总需求，开多少个由解码决定
    nn = max(8, min(n, 12))
    pts = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(nn)]
    dem = [rng.randint(2, 8) for _ in range(nn)]
    cap = [rng.randint(14, 28) for _ in range(nn)]
    while sum(cap) < 2 * sum(dem):
        cap[rng.randrange(nn)] += 4
    fc = [rng.randint(200, 500) for _ in range(nn)]
    return {"variant": variant, "pts": pts, "cap": cap, "dem": dem, "fc": fc, "n": nn}


@_maker('lrp')
def _make_lrp(variant, n, seed, rng):
    # 选址-路径联合：n 个客户（有需求），从中选 p 个点建仓库；其余客户由最近的仓库用容量受限的车辆配送
    nn = max(10, min(n, 14))
    pts = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(nn)]
    dem = [rng.randint(2, 8) for _ in range(nn)]
    return {"variant": variant, "pts": pts, "dem": dem, "p": 2, "cap": 20, "depot_cost": 150, "veh_cost": 25, "n": nn}


@_maker('tdm')
def _make_tdm(variant, n, seed, rng):
    # 3-维匹配（最大化版）：X、Y、Z 各 q 个元素，三元组 ⊆ X×Y×Z；选尽量多的两两不相交三元组。
    # 植入一个完美匹配（q 个三元组），所以最优值已知 = q；再加 2q 个随机三元组当干扰。每个三元组存成 3q 列的 0/1 行（与集合打包同构）。
    q = max(3, min(6, (n + 1) // 2))
    ys, zs = list(range(q)), list(range(q))
    rng.shuffle(ys)
    rng.shuffle(zs)
    trip = {(i, ys[i], zs[i]) for i in range(q)}
    while len(trip) < 3 * q:
        trip.add((rng.randrange(q), rng.randrange(q), rng.randrange(q)))
    trip = sorted(trip)
    rng.shuffle(trip)
    sets = []
    for (x, y, z) in trip:
        row = [0] * (3 * q)
        row[x] = row[q + y] = row[2 * q + z] = 1
        sets.append(row)
    return {"variant": variant, "sets": sets, "triples": [list(t) for t in trip], "q": q, "n": len(sets)}


@_maker('ndp')
def _make_ndp(variant, n, seed, rng):
    # 网络设计（连通需求版）：候选边 = 每点连最近的 3 个点，再并入最小生成树的边（保证候选图连通）；建边费用 = 长度；
    # 3 对需求点必须在买下的边里连通
    nn = max(8, min(n, 12))
    pts = [[round(rng.uniform(0, 100), 1), round(rng.uniform(0, 100), 1)] for _ in range(nn)]
    E = set()
    for i in range(nn):
        for j in sorted((j for j in range(nn) if j != i), key=lambda j: math.dist(pts[i], pts[j]))[:3]:
            E.add((min(i, j), max(i, j)))
    par = list(range(nn))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for (d, a, b) in sorted((math.dist(pts[a], pts[b]), a, b) for a in range(nn) for b in range(a + 1, nn)):
        ra, rb = find(a), find(b)
        if ra != rb:
            par[ra] = rb
            E.add((a, b))
    edges = [[a, b, round(math.dist(pts[a], pts[b]))] for (a, b) in sorted(E)]
    pairs = []
    while len(pairs) < 3:
        a, b = rng.sample(range(nn), 2)
        if (a, b) not in pairs and (b, a) not in pairs:
            pairs.append((a, b))
    return {"variant": variant, "pts": pts, "edges": edges, "pairs": [list(q) for q in pairs], "n": len(edges), "n_pts": nn}


@_maker('freqasg')
def _make_freqasg(variant, n, seed, rng):
    # 频率分配：发射机×频率，距离-冲突罚（着色同型）
    nn = max(8, min(n, 12))
    conf = [[1 if i != j and rng.random() < 0.4 else 0 for j in range(nn)] for i in range(nn)]
    return {"variant": variant, "conf": conf, "n": nn, "slots": 6}

# ---- 批 5：黑箱与多目标族 10 变体（2026-09-27，实数向量）----

@_maker('cbbb', 'nbbb', 'lbbb', 'ebbb', 'mmo')
def _make_cbbb_etc5(variant, n, seed, rng):
    # rastrigin 家族（约束/噪声/大规模/昂贵/多模态）
    nn = 10 if variant == "lbbb" else 8
    return {"variant": variant, "n": nn}


@_maker('blo')
def _make_blo(variant, n, seed, rng):
    # 双层优化的占位地形（8 维）：见 _obj_blo 的说明——它不是真正的嵌套优化
    return {"variant": variant, "n": 8}


@_maker('ro')
def _make_ro(variant, n, seed, rng):
    # 鲁棒优化（场景法）：8 维 Rastrigin 地形；决策 x 的实际取值会被 8 个已知的扰动场景 δₖ（每个分量 ∈ [−0.3, 0.3]）打偏，
    # 要在「最差场景」下也好。场景在实例里固定给出
    nn = 8
    scen = [[round(rng.uniform(-0.3, 0.3), 4) for _ in range(nn)] for _ in range(8)]
    return {"variant": variant, "n": nn, "scen": scen}


@_maker('dop')
def _make_dop(variant, n, seed, rng):
    return {"variant": variant, "n": 8}


@_maker('ged')
def _make_ged(variant, n, seed, rng):
    # 生成式设计（布局生成的最小模型）：k 个圆形功能块（半径 6–14），要摆进 100×100 的场地，互不重叠、留 2 个单位的间隙；
    # 其中一部分块对「希望相邻」（任意两块以 0.35 的概率成对）。解 = 每个块的 (x, y)（实数向量，[−5,5] 线性映射到场地内）
    k = max(5, min(n, 12))
    r = [rng.randint(6, 14) for _ in range(k)]
    adj = [[i, j] for i in range(k) for j in range(i + 1, k) if rng.random() < 0.35]
    return {"variant": variant, "r": r, "adj": adj, "gap": 2, "size": 100, "k": k, "n": 2 * k}


@_maker('proteinfold')
def _make_proteinfold(variant, n, seed, rng):
    # HP 格点：H/P 序列（方向序解码）
    nn = max(12, min(n, 20))
    seq = ["H" if rng.random() < 0.45 else "P" for _ in range(nn)]
    return {"variant": variant, "seq": seq, "n": nn}


# ---- P 类对照问题与多序列比对（2026-10 重做）----

def _pc_graph(rng, nn, directed=False):
    """随机连通图：每对点以 0.3 的概率连边，再并入一棵随机生成树保证连通。返回 (pts, 边对集合)。"""
    pts = [[round(rng.uniform(0, 100), 1), round(rng.uniform(0, 100), 1)] for _ in range(nn)]
    E = set()
    for i in range(nn):
        for j in range(i + 1, nn):
            if rng.random() < 0.3:
                E.add((i, j))
    order = list(range(nn))
    rng.shuffle(order)
    for k in range(1, nn):
        a, b = order[k], order[rng.randrange(k)]
        E.add((min(a, b), max(a, b)))
    return pts, sorted(E)


def _pc_find(parent, x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _opt_mst(nn, edges):
    par = list(range(nn))
    opt = 0
    for a, b, w in sorted(edges, key=lambda e: e[2]):
        ra, rb = _pc_find(par, a), _pc_find(par, b)
        if ra != rb:
            par[ra] = rb
            opt += w
    return opt


def _opt_sp(nn, edges, src, dst):
    dist = [10 ** 9] * nn
    dist[src] = 0
    done = [False] * nn
    for _ in range(nn):
        u = min((v for v in range(nn) if not done[v]), key=lambda v: dist[v])
        done[u] = True
        for a, b, w in edges:
            if a == u and dist[u] + w < dist[b]:
                dist[b] = dist[u] + w
            if b == u and dist[u] + w < dist[a]:
                dist[a] = dist[u] + w
    return dist[dst]


def _opt_gmatch(nn, edges):
    adjw = [[] for _ in range(nn)]
    for a, b, w in edges:
        adjw[a].append((b, w))
        adjw[b].append((a, w))
    memo = {}

    def best(mask):
        if mask == (1 << nn) - 1:
            return 0
        if mask in memo:
            return memo[mask]
        v = next(i for i in range(nn) if not mask >> i & 1)
        r = best(mask | 1 << v)  # v 不配对
        for u, w in adjw[v]:
            if not mask >> u & 1:
                r = max(r, w + best(mask | 1 << v | 1 << u))
        memo[mask] = r
        return r
    return best(0)


@_maker('mst')
def _make_mst(variant, n, seed, rng):
    # 最小生成树：随机连通加权图（权 1–15）。解 = 边的优先序，Kruskal 式解码（按序加边，成环就跳过）；opt = Kruskal 的最优值
    nn = max(8, min(n, 24))
    pts, E = _pc_graph(rng, nn)
    edges = [[a, b, rng.randint(1, 15)] for a, b in E]
    return {"variant": variant, "pts": pts, "edges": edges, "n": len(edges), "n_nodes": nn, "opt": _opt_mst(nn, edges)}


@_maker('shortestpath')
def _make_shortestpath(variant, n, seed, rng):
    # 最短路径：随机连通加权图（权 1–15），起点 0、终点 = 离起点跳数最多的点。解 = 每个点的「优先级」（实数向量），解码从起点出发、每步走向优先级最高的未访问邻居，走进死胡同按重罚计；opt = Dijkstra 的最优值
    nn = max(8, min(n, 24))
    pts, E = _pc_graph(rng, nn)
    edges = [[a, b, rng.randint(1, 15)] for a, b in E]
    hops, q = {0: 0}, [0]  # 终点取离起点「跳数最多」的点（同跳数取最短距离最大者）：不让起点和终点直接相连
    for u in q:
        for a, b, _w in edges:
            for x, y in ((a, b), (b, a)):
                if x == u and y not in hops:
                    hops[y] = hops[u] + 1
                    q.append(y)
    dst = max(range(1, nn), key=lambda v: (hops[v], _opt_sp(nn, edges, 0, v)))
    return {"variant": variant, "pts": pts, "edges": edges, "n": nn, "src": 0, "dst": dst, "opt": _opt_sp(nn, edges, 0, dst)}


def _pc_flow_graph(rng, nn, with_cost):
    """随机有向流网络：源点 0、汇点 n−1；每个有序点对以 0.22 的概率连一条弧，再保证存在一条源→汇的路径。"""
    pts = [[round(rng.uniform(0, 100), 1), round(rng.uniform(0, 100), 1)] for _ in range(nn)]
    A = set()
    for i in range(nn):
        for j in range(nn):
            if i != j and j != 0 and i != nn - 1 and rng.random() < 0.22:
                A.add((i, j))
    mid = list(range(1, nn - 1))
    rng.shuffle(mid)
    chain = [0] + mid[:3] + [nn - 1]
    for a, b in zip(chain, chain[1:]):
        A.add((a, b))
    return pts, sorted(A)


def _pc_max_flow(nn, arcs, src, snk, cost=None, want=None):
    """最大流（Edmonds–Karp）；给出 cost 与 want 时改为「最小费用流」（逐次最短增广路，Bellman–Ford），要凑出 want 单位流。返回（流值, 费用）。
    残量图用「弧 + 反向弧」成对存放（互为 twin），所以相反方向的两条真弧、平行弧都不会互相覆盖。"""
    to, cap, cst = [], [], []
    for k, (a, b, c) in enumerate(arcs):
        ck = cost[k] if cost else 0
        to += [b, a]
        cap += [c, 0]
        cst += [ck, -ck]
    frm = [None] * len(to)
    for k, (a, b, _c) in enumerate(arcs):
        frm[2 * k], frm[2 * k + 1] = a, b
    out = [[] for _ in range(nn)]
    for e in range(len(to)):
        out[frm[e]].append(e)
    flow, total = 0, 0
    while want is None or flow < want:
        prev_e = {src: None}
        if cost is None:  # BFS
            q = [src]
            for u in q:
                for e in out[u]:
                    if cap[e] > 0 and to[e] not in prev_e:
                        prev_e[to[e]] = e
                        q.append(to[e])
        else:  # Bellman–Ford
            dist = {src: 0}
            for _ in range(nn):
                ch = False
                for e in range(len(to)):
                    u = frm[e]
                    if cap[e] > 0 and u in dist and dist[u] + cst[e] < dist.get(to[e], 10 ** 9):
                        dist[to[e]], prev_e[to[e]] = dist[u] + cst[e], e
                        ch = True
                if not ch:
                    break
        if snk not in prev_e:
            break
        path, v = [], snk
        while prev_e[v] is not None:
            e = prev_e[v]
            path.append(e)
            v = frm[e]
        push = min(cap[e] for e in path)
        if want is not None:
            push = min(push, want - flow)
        for e in path:
            cap[e] -= push
            cap[e ^ 1] += push
            total += push * cst[e]
        flow += push
    return flow, total


@_maker('maxflow')
def _make_maxflow(variant, n, seed, rng):
    # 最大流：随机有向流网络（弧容量 5–20）。解 = 每条弧上的流量（实数向量，[−5,5] 线性映射到 [0, 容量]）；目标 = −源点净流出 + 3 × 各中间点的流量守恒违反量；opt = Edmonds–Karp 的最大流
    nn = max(8, min(n, 16))
    pts, A = _pc_flow_graph(rng, nn, False)
    arcs = [[a, b, rng.randint(5, 20)] for a, b in A]
    f, _ = _pc_max_flow(nn, arcs, 0, nn - 1)
    return {"variant": variant, "pts": pts, "arcs": arcs, "n": len(arcs), "n_nodes": nn, "src": 0, "snk": nn - 1, "opt": f}


@_maker('mincostflow')
def _make_mincostflow(variant, n, seed, rng):
    # 最小费用流：同一类流网络（弧容量 5–20、单位费用 1–5）；要从源点送 F 单位到汇点，F = 最大流的 60%。解 = 每条弧上的流量；
    # 目标 = 总费用 + 60 × (|源点净流出 − F| + 中间点的守恒违反量)；opt = 逐次最短增广路得到的最小费用
    nn = max(8, min(n, 16))
    pts, A = _pc_flow_graph(rng, nn, True)
    arcs = [[a, b, rng.randint(5, 20)] for a, b in A]
    cost = [rng.randint(1, 5) for _ in arcs]
    fmax, _ = _pc_max_flow(nn, arcs, 0, nn - 1)
    F = max(1, int(fmax * 0.6))
    _f, opt = _pc_max_flow(nn, arcs, 0, nn - 1, cost=cost, want=F)
    return {"variant": variant, "pts": pts, "arcs": [a + [c] for a, c in zip(arcs, cost)], "n": len(arcs), "n_nodes": nn,
            "src": 0, "snk": nn - 1, "need": F, "opt": opt}


@_maker('gmatch')
def _make_gmatch(variant, n, seed, rng):
    # 一般图最大权匹配：随机连通加权图（权 1–15）。解 = 边的优先序，贪心解码（两端都空闲就取）；opt = 对顶点子集的动态规划（精确）
    nn = max(8, min(n, 14))
    pts, E = _pc_graph(rng, nn)
    edges = [[a, b, rng.randint(1, 15)] for a, b in E]
    return {"variant": variant, "pts": pts, "edges": edges, "n": len(edges), "n_nodes": nn, "opt": _opt_gmatch(nn, edges)}


@_maker('topsort')
def _make_topsort(variant, n, seed, rng):
    # 拓扑排序：随机有向无环图——先隐藏一个随机的顶点次序，再按它以 0.6 的概率连「前 → 后」的弧，最后把顶点编号打乱。
    # 解 = 顶点的排列；目标 = 违反的弧数（排在后面的点指向排在前面的点），0 即合法拓扑序；opt = 0（Kahn 算法线性时间可得）
    nn = max(8, min(n, 24))
    pts = [[round(rng.uniform(0, 100), 1), round(rng.uniform(0, 100), 1)] for _ in range(nn)]  # 先取坐标：不然隐藏次序恰好等于「同种子的第一个随机排列」，随机基线第一步就撞上答案
    hidden = list(range(nn))
    rng.shuffle(hidden)
    arcs = [[hidden[i], hidden[j]] for i in range(nn) for j in range(i + 1, nn) if rng.random() < 0.6]
    for i in range(nn - 1):  # 保证至少有一条贯穿的链，次序不至于太松
        if rng.random() < 0.5:
            a = [hidden[i], hidden[i + 1]]
            if a not in arcs:
                arcs.append(a)
    return {"variant": variant, "pts": pts, "arcs": arcs, "n": nn, "opt": 0}


_MSA_SCORE = {"match": 2, "mismatch": -1, "gap": -2}


def _msa_pair(a, b):
    if a == "-" and b == "-":
        return 0
    if a == "-" or b == "-":
        return _MSA_SCORE["gap"]
    return _MSA_SCORE["match"] if a == b else _MSA_SCORE["mismatch"]


def _msa_dp(seqs):
    """三条序列的和对（SP）得分的精确最优：三维动态规划（7 种列类型）。"""
    A, B, C = seqs
    la, lb, lc = len(A), len(B), len(C)
    NEG = -10 ** 9
    D = {}

    def col(x, y, z):
        return _msa_pair(x, y) + _msa_pair(x, z) + _msa_pair(y, z)
    for i in range(la + 1):
        for j in range(lb + 1):
            for k in range(lc + 1):
                if i == j == k == 0:
                    D[(0, 0, 0)] = 0
                    continue
                best = NEG
                for di in (0, 1):
                    for dj in (0, 1):
                        for dk in (0, 1):
                            if not (di or dj or dk) or i - di < 0 or j - dj < 0 or k - dk < 0:
                                continue
                            x = A[i - 1] if di else "-"
                            y = B[j - 1] if dj else "-"
                            z = C[k - 1] if dk else "-"
                            v = D[(i - di, j - dj, k - dk)] + col(x, y, z)
                            if v > best:
                                best = v
                D[(i, j, k)] = best
    return D[(la, lb, lc)]


@_maker('msa')
def _make_msa(variant, n, seed, rng):
    # 多序列比对（3 条合成 DNA 序列）：先随机造一条祖先序列，再各自发生 2 处点突变 + 1–2 处缺失，得到长度略有差别、彼此相似的三条序列。
    # 解 = 3 × W 个 0/1 位（每条序列一行，1 = 该列放一个残基，0 = 空位），W = 最长序列长度 + 4；目标 = −SP 得分；opt = 三维动态规划的精确最优
    L0 = max(8, min(n, 14))
    anc = [rng.choice("ACGT") for _ in range(L0)]
    seqs = []
    for _ in range(3):
        t = list(anc)
        for _m in range(2):
            t[rng.randrange(len(t))] = rng.choice("ACGT")
        for _d in range(rng.randint(1, 2)):
            del t[rng.randrange(len(t))]
        seqs.append("".join(t))
    W = max(len(x) for x in seqs) + 4
    return {"variant": variant, "seqs": seqs, "W": W, "n": 3 * W, "opt": _msa_dp(seqs)}


# ---- 批 4：图问题族 12 变体（2026-09-27）----

@_maker('vcover', 'domset', 'mclique', 'fvs', 'maxcut', 'gpp')
def _make_vcover_etc9(variant, n, seed, rng):
    # 点边图族：统一图生成
    nn = max(8, min(n, 12))
    pts = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(nn)]
    edges = []
    for i in range(nn):
        for j in range(i + 1, nn):
            if rng.random() < 0.35:
                edges.append((i, j, rng.randint(1, 15)))
    return {"variant": variant, "pts": pts, "edges": edges, "n": nn}


@_maker('setpack', 'hset')
def _make_setpack_etc2(variant, n, seed, rng):
    # 集合族：集合 × 元素 0/1 矩阵。setpack：每一位 = 选不选某个集合（n = 集合数）；hset：每一位 = 选不选某个元素（n = 元素数）
    ne = max(6, min(n, 14))
    sets = [[1 if rng.random() < 0.3 else 0 for _ in range(ne)] for _ in range(ne // 2 + 2)]
    for row in sets:  # 每个集合至少含一个元素（否则击中集无解、打包里它与谁都不冲突）
        if not any(row):
            row[rng.randrange(ne)] = 1
    return {"variant": variant, "sets": sets, "n": len(sets) if variant == "setpack" else ne}


@_maker('csplogic')
def _make_csplogic(variant, n, seed, rng):
    # 约束满足：变量×值域+约束对
    nn = max(8, min(n, 10))
    vals = 4
    conf = [[1 if i != j and rng.random() < 0.3 else 0 for j in range(nn)] for i in range(nn)]
    return {"variant": variant, "conf": conf, "n": nn, "slots": vals}


# ============================================================ 目标函数（每变体一个，签名 fn(self, s)）

def _vrp_dist(self):
    """仓库到各点、点到点的距离，按实例缓存（目标函数每代被调用几十次）。"""
    D = getattr(self, "_vrpD", None)
    if D is None:
        pts = self.p["pts"]
        D = self._vrpD = [[math.dist(a, b) for b in pts] for a in pts]
    return D


def _vrp_free_routes(D, demand, cap, tour):
    """车队不限的最优切分的路线（vrp_split 的无车数上限版本，仅用于展示）。"""
    return vrp_split(D, demand, cap, max(1, len(tour)), tour)[1]


def vrp_split(D, demand, cap, m_veh, tour):
    """Prins (2004) 最优切分：把客户的访问序（巨型回路 tour，元素为 pts 下标 1..n）切成至多 m_veh 条
    容量合法的路线，使总里程最小（分层 DP：f[k][j] = 用 k 条路线服务前 j 个客户的最小里程）。
    返回 (总里程, 路线列表)；这个访问序切不出合法方案时返回 (None, None)。"""
    n = len(tour)
    INF = float("inf")
    pre = [0.0] * n  # pre[l] = 沿访问序从第 0 个走到第 l 个的里程
    for l in range(1, n):
        pre[l] = pre[l - 1] + D[tour[l - 1]][tour[l]]
    f = [[INF] * (n + 1) for _ in range(m_veh + 1)]
    back = [[-1] * (n + 1) for _ in range(m_veh + 1)]
    f[0][0] = 0.0
    for k in range(1, m_veh + 1):
        fk, fp, bk = f[k], f[k - 1], back[k]
        for j in range(1, n + 1):
            load = 0
            best, arg = INF, -1
            for i in range(j - 1, -1, -1):  # 第 k 条路线服务 tour[i..j-1]
                load += demand[tour[i]]
                if load > cap:
                    break
                if fp[i] == INF:
                    continue
                c = fp[i] + D[0][tour[i]] + (pre[j - 1] - pre[i]) + D[tour[j - 1]][0]
                if c < best:
                    best, arg = c, i
            fk[j], bk[j] = best, arg
    kbest = min(range(1, m_veh + 1), key=lambda k: f[k][n])
    if f[kbest][n] == INF:
        return None, None
    routes, j, k = [], n, kbest
    while j > 0:
        i = back[k][j]
        routes.append(tour[i:j])
        j, k = i, k - 1
    routes.reverse()
    return f[kbest][n], routes


def _vrp_free_split(D, demand, cap, tour):
    """车队不限的 Prins 切分（O(n·每路客户数)）：只用来给「切不进车队」的访问序算一个有梯度的惩罚。"""
    n = len(tour)
    INF = float("inf")
    pre = [0.0] * n
    for l in range(1, n):
        pre[l] = pre[l - 1] + D[tour[l - 1]][tour[l]]
    f = [INF] * (n + 1)
    f[0] = 0.0
    cnt = [0] * (n + 1)
    for j in range(1, n + 1):
        load = 0
        for i in range(j - 1, -1, -1):
            load += demand[tour[i]]
            if load > cap:
                break
            c = f[i] + D[0][tour[i]] + (pre[j - 1] - pre[i]) + D[tour[j - 1]][0]
            if c < f[j]:
                f[j], cnt[j] = c, cnt[i] + 1
    return f[n], cnt[n]


@_objective('vrp', fidelity="standard",
            note="")
def _obj_vrp(self, s):
    # 带容量车辆路径 CVRP：s 是客户的访问序（巨型回路），解码 = Prins 最优切分成至多 m_veh 条容量合法的路线，
    # 目标 = 总里程。访问序切不进车队时，用「不限车队的最优切分里程 + 每多用一辆车 200」作惩罚，保持搜索有梯度。
    D = _vrp_dist(self)
    demand, cap, m_veh = self.p["demand"], self.p["cap"], self.p["m_veh"]
    tour = [x + 1 for x in s]
    total, _routes = vrp_split(D, demand, cap, m_veh, tour)
    if total is None:
        free, used = _vrp_free_split(D, demand, cap, tour)
        total = free + 200.0 * max(1, used - m_veh)
    return round(total, 3)


def vrptw_arcs(D, demand, cap, e, l, svc, H, tour):
    """访问序 tour（元素为 pts 下标 1..n）上所有「合法的连续一段」：返回 arcs[i] = [(j, 里程), …]，
    表示 tour[i:j] 可以由同一辆车服务（容量不超、每个客户在窗口关闭前到达——早到则等到窗口打开、
    且在仓库关门 H 前回到仓库），里程 = 仓库→…→仓库的行驶距离（等待不计里程）。
    一段不合法，向右延长也一定不合法（到达只会更晚、载重只会更大、回仓只会更晚——回仓用三角不等式），所以遇到第一个违反就停。"""
    n = len(tour)
    arcs = [[] for _ in range(n)]
    for i in range(n):
        load, t, prev, dist = 0, 0.0, 0, 0.0
        for j in range(i, n):
            c = tour[j]
            load += demand[c]
            if load > cap:
                break
            arr = t + D[prev][c]
            if arr > l[c] + 1e-9:
                break
            t = max(arr, e[c]) + svc[c]
            dist += D[prev][c]
            prev = c
            if t + D[c][0] > H + 1e-9:
                break
            arcs[i].append((j + 1, dist + D[c][0]))
    return arcs


def vrptw_split(arcs, n, m_veh):
    """在 vrptw_arcs 给出的合法段上做 Prins 最优切分：至多 m_veh 条路线，总里程最小。
    返回 (总里程, 路线的 (起, 止) 列表)；这个访问序切不进车队时返回 (None, None)。"""
    INF = float("inf")
    f = [[INF] * (n + 1) for _ in range(m_veh + 1)]
    back = [[-1] * (n + 1) for _ in range(m_veh + 1)]
    f[0][0] = 0.0
    for k in range(1, m_veh + 1):
        fp, fk, bk = f[k - 1], f[k], back[k]
        for i in range(n):
            if fp[i] == INF:
                continue
            for j, c in arcs[i]:
                if fp[i] + c < fk[j]:
                    fk[j], bk[j] = fp[i] + c, i
    kbest = min(range(1, m_veh + 1), key=lambda k: f[k][n])
    if f[kbest][n] == INF:
        return None, None
    spans, j, k = [], n, kbest
    while j > 0:
        i = back[k][j]
        spans.append((i, j))
        j, k = i, k - 1
    spans.reverse()
    return f[kbest][n], spans


def vrptw_free_split(arcs, n):
    """车队不限的最优切分（只用来给「切不进车队」的访问序算有梯度的惩罚，以及页面上照样画出路线）：返回 (里程, 路线数, spans)。"""
    INF = float("inf")
    f, cnt, back = [INF] * (n + 1), [0] * (n + 1), [-1] * (n + 1)
    f[0] = 0.0
    for i in range(n):
        if f[i] == INF:
            continue
        for j, c in arcs[i]:
            if f[i] + c < f[j]:
                f[j], cnt[j], back[j] = f[i] + c, cnt[i] + 1, i
    if f[n] == INF:
        return INF, 0, None
    spans, j = [], n
    while j > 0:
        spans.append((back[j], j))
        j = back[j]
    spans.reverse()
    return f[n], cnt[n], spans


def vrpstw_arcs(D, demand, cap, e, l, svc, H, lam, tour):
    """软时间窗版的 vrptw_arcs：晚到不再不可行，而是每晚 1 个单位罚 lam（早到仍要等；回仓晚于 H 同样计罚）。
    只有容量能让一段不合法（所以遇到超载就停）。arcs[i] = [(j, 里程 + lam × 迟到总量), …]。"""
    n = len(tour)
    arcs = [[] for _ in range(n)]
    for i in range(n):
        load, t, prev, dist, late = 0, 0.0, 0, 0.0, 0.0
        for j in range(i, n):
            c = tour[j]
            load += demand[c]
            if load > cap:
                break
            arr = t + D[prev][c]
            late += max(0.0, arr - l[c])
            t = max(arr, e[c]) + svc[c]
            dist += D[prev][c]
            prev = c
            end_late = max(0.0, t + D[c][0] - H)
            arcs[i].append((j + 1, dist + D[c][0] + lam * (late + end_late)))
    return arcs


def _vrptw_arcs_of(self, s):
    p = self.p
    tour = [x + 1 for x in s]
    if "lam" in p:
        return vrpstw_arcs(_vrp_dist(self), p["demand"], p["cap"], p["e"], p["l"], p["svc"], p["l"][0], p["lam"], tour)
    return vrptw_arcs(_vrp_dist(self), p["demand"], p["cap"], p["e"], p["l"], p["svc"], p["l"][0], tour)


@_objective('vrptw', 'vrpstw', fidelity="standard")
def _obj_vrptw(self, s):
    # 带时间窗的车辆路径 VRPTW（硬时间窗；变体 vrpstw 为软时间窗：晚到不非法、按迟到量罚）：s 是客户的访问序，解码 = 在「合法的连续段」上做 Prins 最优切分，
    # 至多 m_veh 条路线，目标 = 总里程。切不进车队时：不限车队的最优切分里程 + 每多用一辆车 200（保持搜索有梯度）。
    arcs = _vrptw_arcs_of(self, s)
    n = len(s)
    total, _spans = vrptw_split(arcs, n, self.p["m_veh"])
    if total is None:
        free, used, _sp = vrptw_free_split(arcs, n)
        total = free + 200.0 * max(1, used - self.p["m_veh"])
    return round(total, 3)


def vrptw_schedule(p, route):
    """一条路线上每个客户的 (到达, 开始服务, 离开) 时刻；等待 = 开始 − 到达。"""
    out, t, prev = [], 0.0, 0
    for c in route:
        arr = t + math.dist(p["pts"][prev], p["pts"][c])
        start = max(arr, p["e"][c])
        t = start + p["svc"][c]
        out.append([round(arr, 2), round(start, 2), round(t, 2)])
        prev = c
    return out


def _mdvrp_groups(self, s):
    """把排列拆成 D 组客户（按分隔符），返回 [第 d 个仓库的客户下标 1..k 列表]。"""
    D = self.p["D"]
    k = self.p["n"] + 1 - D
    groups, g = [[] for _ in range(D)], 0
    for v in s:
        if v >= k:
            g += 1
        else:
            groups[g].append(v + 1)
    return groups


def _mdvrp_mats(self):
    """每个仓库一份「0 号 = 该仓库、1..k = 客户」的距离矩阵与需求表（直接复用 vrp_split），按实例缓存。"""
    cached = getattr(self, "_mdM", None)
    if cached is None:
        p = self.p
        D = p["D"]
        k = p["n"] + 1 - D
        cust = p["pts"][D:]
        demand = [0] + p["demand"][D:]
        mats = []
        for d in range(D):
            pts = [p["pts"][d]] + cust
            mats.append([[math.dist(a, b) for b in pts] for a in pts])
        cached = self._mdM = (mats, demand)
    return cached


def mdvrp_split_all(self, s):
    """每个仓库的客户序做 Prins 最优切分（至多 m_dep 条路线）。返回 (总里程, [(仓库, 路线列表, 是否在车队内)])；
    切不进车队的仓库按「不限车队的最优切分 + 每多一辆车 200」计罚（路线仍照切，页面画得出来）。"""
    p = self.p
    mats, demand = _mdvrp_mats(self)
    total, parts = 0.0, []
    for d, tour in enumerate(_mdvrp_groups(self, s)):
        if not tour:
            parts.append((d, [], True))
            continue
        cost, routes = vrp_split(mats[d], demand, p["cap"], p["m_dep"], tour)
        within = cost is not None
        if not within:
            cost, used = _vrp_free_split(mats[d], demand, p["cap"], tour)
            cost += 200.0 * max(1, used - p["m_dep"])
            routes = _vrp_free_routes(mats[d], demand, p["cap"], tour)
        total += cost
        parts.append((d, routes, within))
    return total, parts


@_objective('mdvrp', fidelity="standard")
def _obj_mdvrp(self, s):
    # 多车场 VRP：序列里的分隔符把客户分给各个仓库（每个仓库自己的车队与容量），各仓库内部做 Prins 最优切分，目标 = 总里程。
    # 没有路线时长上限（经典 MDVRP 实例有，这里省略）。
    return round(mdvrp_split_all(self, s)[0], 3)


# ---- 调度类：目标函数与「解长什么样」（2026-10 重做）----

def _pfsp_times(p, s):
    """置换流水车间的完工时间表：C[k][j] = max(C[k][j−1], C[k−1][j]) + p[k][j]；返回每个作业在每台机器上的 (开始, 结束)。"""
    m = len(p)
    free = [0] * m
    out = []
    for j in s:
        row, prev = [], 0
        for k in range(m):
            st = max(free[k], prev)
            en = st + p[k][j]
            free[k] = prev = en
            row.append((st, en))
        out.append(row)
    return out


@_objective('fss', fidelity="standard")
def _obj_fss(self, s):
    # 置换流水车间（所有机器上作业顺序相同）：最小化完工时间 Cmax
    p = self.p["p"]
    free = [0] * len(p)
    for j in s:
        prev = 0
        for k in range(len(p)):
            prev = free[k] = max(free[k], prev) + p[k][j]
    return free[-1]


@_detail('fss')
def _detail_fss(self, s):
    rows = _pfsp_times(self.p["p"], s)
    ops = [[j, k, st, en] for j, row in zip(s, rows) for k, (st, en) in enumerate(row)]
    return {"ops": ops, "makespan": rows[-1][-1][1], "lb": _pfsp_lb(self.p["p"]), "m": len(self.p["p"]), "n_jobs": len(s)}


def _pfsp_lb(p):
    """经典下界：某台机器上全部作业的总时间，加上它之前最短的前置和之后最短的后继。"""
    m, n = len(p), len(p[0])
    best = 0
    for k in range(m):
        head = min(sum(p[q][j] for q in range(k)) for j in range(n)) if k else 0
        tail = min(sum(p[q][j] for q in range(k + 1, m)) for j in range(n)) if k < m - 1 else 0
        best = max(best, head + sum(p[k][j] for j in range(n)) + tail)
    return best


def _shop_schedule(self, s):
    """把排列 s 译成工序时间表，返回 [(作业, 机器, 开始, 结束)]。
    jss / fjsp：排列元素对作业数取模得到「作业重复序列」（每个作业恰好出现 m 次），第 k 次出现的就是它的第 k 道工序（Bierwirth 1995 的工序编码）；
      jss 按作业自己的路线定机器，fjsp 在可选机器里挑「做完最早」的；
    oss：排列元素 = 工序编号 (作业 × m + 机器)，按排列顺序排程；
    都是半主动调度：工序在「作业就绪」与「机器空闲」的较晚者开始。"""
    p = self.p
    v = self.variant
    mf, out = {}, []
    if v == "oss":
        m = p["m_mach"]
        jr = [0] * p["n_jobs"]
        for x in s:
            j, k = divmod(x, m)
            st = max(jr[j], mf.get(k, 0))
            en = st + p["t"][j][k]
            jr[j], mf[k] = en, en
            out.append((j, k, st, en))
        return out
    nj = p["n_jobs"]
    nxt, jr = [0] * nj, [0] * nj
    for x in s:
        j = x % nj
        op = p["jobs"][j][nxt[j]]
        nxt[j] += 1
        if v == "jss":
            k, t = op
            st = max(jr[j], mf.get(k, 0))
        else:
            k, t = min(op, key=lambda kt: (max(jr[j], mf.get(kt[0], 0)) + kt[1], kt[0]))
            st = max(jr[j], mf.get(k, 0))
        jr[j], mf[k] = st + t, st + t
        out.append((j, k, st, st + t))
    return out


@_objective('oss', fidelity="standard")
def _obj_oss(self, s):
    return max(en for (_j, _k, _st, en) in _shop_schedule(self, s))


@_objective('jss', fidelity="standard")
def _obj_jss(self, s):
    return max(en for (_j, _k, _st, en) in _shop_schedule(self, s))


@_objective('fjsp', fidelity="simplified", note="机器不是搜索出来的：每道工序固定挑「做完最早」的机器（常见的解码规则，但会漏掉需要故意选慢机器的最优解）")
def _obj_fjsp(self, s):
    return max(en for (_j, _k, _st, en) in _shop_schedule(self, s))


@_detail('oss', 'jss', 'fjsp')
def _detail_shop(self, s):
    ops = _shop_schedule(self, s)
    return {"ops": [list(o) for o in ops], "makespan": max(o[3] for o in ops), "lb": self.p.get("lb"), "m": self.p["m_mach"], "n_jobs": self.p["n_jobs"]}


def _hc_adj(self):
    adj = getattr(self, "_hcadj", None)
    if adj is None:
        adj = self._hcadj = {(a, b) for a, b, *_ in self.p["edges"]} | {(b, a) for a, b, *_ in self.p["edges"]}
    return adj


@_objective('hc', fidelity="standard")
def _obj_hc(self, s):
    # 哈密顿回路的优化视角：排列首尾相接，数「不是图中边」的相邻对；0 = 找到了哈密顿回路
    adj = _hc_adj(self)
    n = len(s)
    return sum(1 for i in range(n) if (s[i], s[(i + 1) % n]) not in adj)


@_detail('hc')
def _detail_hc(self, s):
    adj = _hc_adj(self)
    n = len(s)
    bad = [i for i in range(n) if (s[i], s[(i + 1) % n]) not in adj]
    return {"broken": bad, "found": not bad}


def _lpath_walk(self, s):
    """沿排列走：下一个点与当前点相邻就延伸，碰到非边就停。返回（走过的点序列, 累计权重）。"""
    w = getattr(self, "_lpw", None)
    if w is None:
        w = self._lpw = {}
        for a, b, c in self.p["edges"]:
            w[(a, b)] = w[(b, a)] = c
    path, tot = [s[0]], 0
    for i in range(1, len(s)):
        c = w.get((s[i - 1], s[i]))
        if c is None:
            break
        path.append(s[i])
        tot += c
    return path, tot


@_objective('lpath', fidelity="standard")
def _obj_lpath(self, s):
    # 最长（权重最大的）简单路径：沿排列延伸、碰到非边就停，累计权重取负
    return -_lpath_walk(self, s)[1]


@_detail('lpath')
def _detail_lpath(self, s):
    path, tot = _lpath_walk(self, s)
    return {"path": path, "weight": tot}


def _carp_sp(self):
    """路网全点对最短路（Floyd–Warshall，按实例缓存）。"""
    sp = getattr(self, "_carpsp", None)
    if sp is None:
        nv = len(self.p["pts"])
        sp = [[0 if i == j else 10 ** 9 for j in range(nv)] for i in range(nv)]
        for a, b, c in self.p["edges"]:
            sp[a][b] = sp[b][a] = min(sp[a][b], c)
        for k in range(nv):
            for i in range(nv):
                for j in range(nv):
                    if sp[i][k] + sp[k][j] < sp[i][j]:
                        sp[i][j] = sp[i][k] + sp[k][j]
        self._carpsp = sp
    return sp


def _carp_plan(self, s):
    """排列 s = 必需边的服务顺序。每条边走哪个方向：从当前位置出发、先到离得近的那一端（贪心）；
    再对这条「巨型路线」做容量切分（Ulusoy / Prins 式动态规划：每一段从仓库出发、回仓库，载重 ≤ 容量）。
    返回（总费用, [每趟的（起点, 终点, 边下标）列表]）。"""
    p = self.p
    sp = _carp_sp(self)
    dep, cap = p["depot"], p["cap"]
    ends, seq, cur = [], [], dep
    for r in s:
        a, b, c = p["edges"][p["req"][r]]
        if sp[cur][a] <= sp[cur][b]:
            u, v = a, b
        else:
            u, v = b, a
        ends.append((u, v, c))
        seq.append(r)
        cur = v
    k = len(seq)
    INF = float("inf")
    best, prv = [INF] * (k + 1), [0] * (k + 1)
    best[0] = 0.0
    for i in range(k):
        if best[i] == INF:
            continue
        load, cost = 0, 0.0
        for j in range(i, k):
            load += p["dem"][seq[j]]
            if load > cap and j > i:
                break
            u, v, c = ends[j]
            cost += (sp[dep][u] if j == i else sp[ends[j - 1][1]][u]) + c
            tot = cost + sp[v][dep]
            if best[i] + tot < best[j + 1]:
                best[j + 1], prv[j + 1] = best[i] + tot, i
    trips, j = [], k
    while j > 0:
        i = prv[j]
        trips.append([[ends[t][0], ends[t][1], p["req"][seq[t]]] for t in range(i, j)])
        j = i
    return best[k], trips[::-1]


@_objective('carp', 'rpostman', fidelity="simplified", note="每条边的行走方向由「先到近的一端」的贪心定，不是搜索出来的；路线内顺序就是排列顺序，没有路线内优化")
def _obj_carp(self, s):
    # 弧路由：必需边的服务序 → 贪心定方向 → 容量切分；费用 = 服务费 + 空驶（最短路）。rpostman 容量无限 = 一条回路
    return round(_carp_plan(self, s)[0], 3)


@_detail('carp', 'rpostman')
def _detail_carp(self, s):
    cost, trips = _carp_plan(self, s)
    return {"trips": trips, "cost": round(cost, 3)}


@_objective('lop', fidelity="standard")
def _obj_lop(self, s):
    v = self.variant
    w = self.p["w"]
    return int(-sum(w[s[j]][s[i]] for i in range(self.n) for j in range(i + 1, self.n)))


@_objective('sms', fidelity="standard")
def _obj_sms(self, s):
    v = self.variant
    p_, d = self.p["p"], self.p["d"]
    t = 0
    tot = 0
    for x in s:
        t += p_[x]
        tot += max(0, t - d[x])
    return tot


# ---- 批 2：调度/排课/赛程族 8 变体目标 ----

def _ctp_plan(self, s):
    """排列 s 是「排课顺序」。逐节课 first-fit：取最早的合法时段（同课程不重复、教师 / 课程组无冲突、教室没满），
    教室取装得下的最小一间；软代价 = 教室装不下的人数 + 同一天已有这门课的 10；找不到合法时段就记「未排」。"""
    p = self.p
    lc, teacher, size, rooms = p["lec_course"], p["teacher"], p["size"], p["rooms"]
    P_ = p["days"] * p["slots"]
    conf = getattr(self, "_ctpconf", None)
    if conf is None:
        n = p["n_courses"]
        conf = [[False] * n for _ in range(n)]
        for a in range(n):
            for b in range(n):
                if a != b and teacher[a] == teacher[b]:
                    conf[a][b] = True
        for g in p["groups"]:
            for a in g:
                for b in g:
                    if a != b:
                        conf[a][b] = True
        self._ctpconf = conf
    at = [[] for _ in range(P_)]  # 每个时段已排的 (课程, 教室下标)
    placed, soft, undone = [], 0, 0
    day_of = {}
    for k in s:
        c = lc[k]
        best = None
        for t in range(P_):
            if any(c2 == c or conf[c][c2] for c2, _r in at[t]) or len(at[t]) >= len(rooms):
                continue
            used = {r for _c, r in at[t]}
            free = [r for r in range(len(rooms)) if r not in used]
            fit = [r for r in free if rooms[r] >= size[c]]
            r = min(fit, key=lambda r: rooms[r]) if fit else max(free, key=lambda r: rooms[r])
            cost = max(0, size[c] - rooms[r]) + (10 if (t // p["slots"]) in day_of.get(c, ()) else 0)
            best = (cost, t, r)  # 首个合法时段（first-fit，图着色式的装配）：排课顺序决定结果，所以值得搜索
            break
        if best is None:
            undone += 1
            continue
        cost, t, r = best
        at[t].append((c, r))
        day_of.setdefault(c, set()).add(t // p["slots"])
        placed.append((k, c, t, r))
        soft += cost
    return placed, soft, undone


@_objective('ctp', fidelity="simplified", note="贪心装配而不是对时段 × 教室做搜索；只有教师 / 课程组冲突、教室容量、同日分散三类约束，没有 ITC-2007 的最少上课天数、课程表紧凑度等")
def _obj_ctp(self, s):
    placed, soft, undone = _ctp_plan(self, s)
    return soft + 1000 * undone


@_detail('ctp')
def _detail_ctp(self, s):
    placed, soft, undone = _ctp_plan(self, s)
    return {"placed": [list(x) for x in placed], "soft": soft, "undone": undone}


# ---- 批 5：黑箱与多目标族 10 变体目标（实数向量）----

@_objective('cbbb', fidelity="simplified", note="Rastrigin + 一条线性约束的自拟函数，不是标准约束基准（如 CEC 约束套件）", encoding="real")
def _obj_cbbb(self, s):
    # 约束黑箱：rastrigin + 线性约束 Σx ≤ 3 罚
    v = self.variant
    base = 10 * self.n + sum(x * x - 10 * math.cos(2 * math.pi * x) for x in s)
    viol = max(0.0, sum(s) - 3.0)
    return round(base + 500 * viol, 3)


@_objective('nbbb', fidelity="illustrative", note="「噪声」是确定性伪噪声（同输入同输出），不是真随机噪声", encoding="real")
def _obj_nbbb(self, s):
    # 噪声黑箱：rastrigin + 确定性伪噪声（同输入同输出，可复现）
    v = self.variant
    base = 10 * self.n + sum(x * x - 10 * math.cos(2 * math.pi * x) for x in s)
    noise = 2.0 * math.sin(13.7 * sum(s)) * math.cos(7.3 * s[0])
    return round(base + noise, 3)


@_objective('lbbb', fidelity="illustrative", note="函数是标准的 Rosenbrock，但只有 10 维，并非真正的大规模（通常 ≥1000 维）", encoding="real")
def _obj_lbbb(self, s):
    # 大规模黑箱：rosenbrock 10 维（经典难收敛谷）
    v = self.variant
    return round(sum(100 * (s[i + 1] - s[i] ** 2) ** 2 + (1 - s[i]) ** 2
                     for i in range(self.n - 1)), 3)


@_objective('ebbb', fidelity="illustrative", note="只是把迭代数限到 50 代来「模拟」昂贵评估；没有代理模型，也没有评估预算计数", encoding="real")
def _obj_ebbb(self, s):
    # 昂贵黑箱：与 cbbb 同地形——预算受限（默认 50 代）模拟昂贵评估
    v = self.variant
    base = 10 * self.n + sum(x * x - 10 * math.cos(2 * math.pi * x) for x in s)
    viol = max(0.0, sum(x * x for x in s) - 12.0)
    return round(base + 500 * viol, 3)


@_objective('mmo', fidelity="illustrative", note="Rastrigin 地形，目标仍是单一全局最优；没有「同时定位多个峰」的评价", encoding="real")
def _obj_mmo(self, s):
    # 多模态：rastrigin 地形（指数级局部极小；同时定位多个峰属进阶版）
    v = self.variant
    return round(10 * self.n + sum(x * x - 10 * math.cos(2 * math.pi * x) for x in s), 3)


@_objective('dop', fidelity="illustrative", note="静态双峰（按 x[0] 的符号选地形），目标并不随时间变化")
def _obj_dop(self, s):
    # 动态优化（教学级静态双峰）：x[0]>0 用 A 地形否则 B
    v = self.variant
    if s[0] >= 0:
        return round(sum((x - 2) ** 2 + 2 for x in s), 3)
    return round(sum((x + 2) ** 2 + 2 for x in s), 3)


def _ged_pos(self, s):
    p = self.p
    out = []
    for i in range(p["k"]):
        ri = p["r"][i]
        span = p["size"] - 2 * ri
        out.append([ri + min(1.0, max(0.0, (s[2 * i] + 5.0) / 10.0)) * span, ri + min(1.0, max(0.0, (s[2 * i + 1] + 5.0) / 10.0)) * span])
    return out


@_objective('ged', fidelity="simplified", note="只有「互不重叠」与「希望相邻」两类规则的圆形块布局，没有采光、动线、结构等真实设计指标；设计空间只有 2k 个坐标", encoding="real")
def _obj_ged(self, s):
    # 布局生成：重叠量平方 × 5（含 2 个单位的间隙）+ 希望相邻的块之间多出来的距离（紧贴最好）
    p = self.p
    pos = _ged_pos(self, s)
    tot = 0.0
    for i in range(p["k"]):
        for j in range(i + 1, p["k"]):
            d = math.dist(pos[i], pos[j])
            ov = p["r"][i] + p["r"][j] + p["gap"] - d
            if ov > 0:
                tot += 5.0 * ov * ov
    for i, j in p["adj"]:
        d = math.dist(pos[i], pos[j])
        tot += max(0.0, d - (p["r"][i] + p["r"][j] + p["gap"]))
    return round(tot, 6)


@_detail('ged')
def _detail_ged(self, s):
    p = self.p
    pos = _ged_pos(self, s)
    overlaps = sum(1 for i in range(p["k"]) for j in range(i + 1, p["k"]) if math.dist(pos[i], pos[j]) < p["r"][i] + p["r"][j])
    return {"pos": [[round(a, 2), round(b, 2)] for a, b in pos], "overlaps": overlaps}


@_objective('proteinfold', fidelity="simplified", note="二维方格 HP 模型 + 绝对方向编码；自交用罚分（每处 4）而不是直接排除；序列是随机的（H 占 45%），不是文献里的标准序列")
def _obj_proteinfold(self, s):
    # 解 = 长度 n 的排列，第 i 个元素对 4 取模给出第 i 个残基到第 i+1 个残基的方向；
    # 能量 = −(拓扑 HH 接触数) + 4 × 自交处数。拓扑接触 = 序列上不相邻（|i−j|>1）、格点上相邻的 H–H 对
    seq = self.p["seq"]
    dirs = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    pos = [(0, 0)]
    x = y = 0
    seen = {(0, 0)}
    clash = 0
    for i in range(1, len(seq)):
        dx, dy = dirs[s[(i - 1) % len(s)] % 4]
        x, y = x + dx, y + dy
        if (x, y) in seen:
            clash += 1
        seen.add((x, y))
        pos.append((x, y))
    contacts = 0
    for i in range(len(seq)):
        if seq[i] != "H":
            continue
        for j in range(i + 2, len(seq)):
            if seq[j] == "H" and abs(pos[i][0] - pos[j][0]) + abs(pos[i][1] - pos[j][1]) == 1:
                contacts += 1
    return -contacts + 4 * clash


@_detail('proteinfold')
def _detail_proteinfold(self, s):
    seq = self.p["seq"]
    dirs = [(0, 1), (1, 0), (0, -1), (-1, 0)]
    pos = [(0, 0)]
    x = y = 0
    for i in range(1, len(seq)):
        dx, dy = dirs[s[(i - 1) % len(s)] % 4]
        x, y = x + dx, y + dy
        pos.append((x, y))
    cnt = {}
    for q in pos:
        cnt[q] = cnt.get(q, 0) + 1
    contacts = [[i, j] for i in range(len(seq)) for j in range(i + 2, len(seq))
                if seq[i] == "H" and seq[j] == "H" and abs(pos[i][0] - pos[j][0]) + abs(pos[i][1] - pos[j][1]) == 1]
    return {"pos": [list(q) for q in pos], "contacts": contacts, "clashes": sum(c - 1 for c in cnt.values() if c > 1)}


# ---- P 类对照问题与多序列比对：目标函数与「解长什么样」（2026-10 重做）----

def _mst_tree(self, s):
    par = list(range(self.p["n_nodes"]))
    tree, total = [], 0
    for k in s:
        a, b, w = self.p["edges"][k]
        ra, rb = _pc_find(par, a), _pc_find(par, b)
        if ra != rb:
            par[ra] = rb
            tree.append(k)
            total += w
    return tree, total


@_objective('mst', fidelity="standard")
def _obj_mst(self, s):
    # Kruskal 式解码：按排列给出的优先序依次加边，成环就跳过——对连通图一定得到生成树；排列恰好是按权升序时就是最优
    return _mst_tree(self, s)[1]


@_detail('mst')
def _detail_mst(self, s):
    tree, total = _mst_tree(self, s)
    return {"tree": tree, "weight": total, "opt": self.p["opt"]}


def _sp_walk(self, s):
    """从起点出发，每步走向「优先级最高的未访问邻居」；走不动（所有邻居都访问过）就算失败。返回（路径, 长度或 None）。"""
    p = self.p
    nbr = getattr(self, "_spnbr", None)
    if nbr is None:
        nbr = self._spnbr = [[] for _ in range(p["n"])]
        for a, b, w in p["edges"]:
            nbr[a].append((b, w))
            nbr[b].append((a, w))
    cur, path, tot, seen = p["src"], [p["src"]], 0, {p["src"]}
    while cur != p["dst"]:
        cand = [(s[v], v, w) for v, w in nbr[cur] if v not in seen]
        if not cand:
            return path, None
        _k, v, w = max(cand)
        tot += w
        seen.add(v)
        path.append(v)
        cur = v
    return path, tot


@_objective('shortestpath', fidelity="standard", encoding="real")
def _obj_shortestpath(self, s):
    # 优先级编码（Gen &amp; Cheng 的路径编码）：解码出的一定是一条简单路径；走进死胡同按 4000 计
    path, tot = _sp_walk(self, s)
    return 4000 if tot is None else tot


@_detail('shortestpath')
def _detail_shortestpath(self, s):
    path, tot = _sp_walk(self, s)
    return {"path": path, "length": tot, "reached": tot is not None, "opt": self.p["opt"]}


def _flow_state(self, s):
    """把决策向量译成各弧的流量，并算出源点净流出与各中间点的守恒违反量。"""
    p = self.p
    arcs, nn = p["arcs"], p["n_nodes"]
    x = [min(1.0, max(0.0, (v + 5.0) / 10.0)) * a[2] for v, a in zip(s, arcs)]
    ex = [0.0] * nn
    for f, a in zip(x, arcs):
        ex[a[0]] -= f
        ex[a[1]] += f
    out_src = -ex[p["src"]]
    viol = sum(abs(ex[v]) for v in range(nn) if v not in (p["src"], p["snk"]))
    return x, out_src, viol


@_objective('maxflow', fidelity="standard", encoding="real")
def _obj_maxflow(self, s):
    # 流向量编码：最大化源点净流出，中间点的流量守恒用精确罚函数（权 3 > 1，每违反 1 单位至多多换 1 单位流，不划算）
    x, out_src, viol = _flow_state(self, s)
    return round(-out_src + 3.0 * viol, 6)


@_objective('mincostflow', fidelity="standard", encoding="real")
def _obj_mincostflow(self, s):
    # 目标 = 总费用 + 60 × (送出量与需求 F 的偏差 + 守恒违反量)：60 大于任何一条源→汇路径的单位费用上界（≤ 5 × (n−1)）
    p = self.p
    x, out_src, viol = _flow_state(self, s)
    cost = sum(f * a[3] for f, a in zip(x, p["arcs"]))
    return round(cost + 60.0 * (abs(out_src - p["need"]) + viol), 6)


@_detail('maxflow', 'mincostflow')
def _detail_flow(self, s):
    x, out_src, viol = _flow_state(self, s)
    d = {"flow": [round(f, 3) for f in x], "value": round(out_src, 3), "violation": round(viol, 3), "opt": self.p["opt"]}
    if self.variant == "mincostflow":
        d["cost"] = round(sum(f * a[3] for f, a in zip(x, self.p["arcs"])), 3)
        d["need"] = self.p["need"]
    return d


def _gm_pick(self, s):
    used, picked, tot = set(), [], 0
    for k in s:
        a, b, w = self.p["edges"][k]
        if a not in used and b not in used:
            used.add(a)
            used.add(b)
            picked.append(k)
            tot += w
    return picked, tot


@_objective('gmatch', fidelity="standard")
def _obj_gmatch(self, s):
    # 最大权匹配：按优先序贪心取边（两端都空闲才取）；任何匹配都能写成「它的边在前」的优先序，所以不丢最优解
    return -_gm_pick(self, s)[1]


@_detail('gmatch')
def _detail_gmatch(self, s):
    picked, tot = _gm_pick(self, s)
    return {"matched": picked, "weight": tot, "opt": self.p["opt"]}


@_objective('topsort', fidelity="standard")
def _obj_topsort(self, s):
    # 违反的弧数：弧 a → b 要求 a 排在 b 前面
    pos = {v: i for i, v in enumerate(s)}
    return sum(1 for a, b in self.p["arcs"] if pos[a] > pos[b])


@_detail('topsort')
def _detail_topsort(self, s):
    pos = {v: i for i, v in enumerate(s)}
    return {"order": list(s), "backward": [k for k, (a, b) in enumerate(self.p["arcs"]) if pos[a] > pos[b]]}


def _msa_rows(self, s):
    """每行的 0/1 位决定残基放在哪些列：取前 len 个 1 依次放残基序列；1 不够就把剩下的残基接在最后一个残基后面；行尾补空位到同宽。"""
    W, seqs = self.p["W"], self.p["seqs"]
    rows = []
    for r, seq in enumerate(seqs):
        bits = s[r * W:(r + 1) * W]
        cols = [i for i, b in enumerate(bits) if b][:len(seq)]
        row = ["-"] * W
        for ch, c in zip(seq, cols):
            row[c] = ch
        rest = seq[len(cols):]
        pos = (cols[-1] + 1) if cols else 0
        row = row[:pos] + list(rest) + row[pos:] if rest else row
        rows.append(row)
    width = max(len(r) for r in rows)
    return ["".join(r) + "-" * (width - len(r)) for r in rows]


def _msa_sp(rows):
    tot = 0
    for c in range(len(rows[0])):
        a, b, d = rows[0][c], rows[1][c], rows[2][c]
        tot += _msa_pair(a, b) + _msa_pair(a, d) + _msa_pair(b, d)
    return tot


@_objective('msa', fidelity="simplified", note="只有 3 条合成的短 DNA 序列、线性空位罚分（匹配 +2、错配 −1、残基对空位 −2），没有 BLOSUM 等替换矩阵与仿射空位；解码对位串做了「1 不够就接在后面」的修补", encoding="bits")
def _obj_msa(self, s):
    # 多序列比对（和对 SP 得分，最大化）：目标 = −SP
    return -_msa_sp(_msa_rows(self, s))


@_detail('msa')
def _detail_msa(self, s):
    rows = _msa_rows(self, s)
    return {"rows": rows, "sp": _msa_sp(rows), "opt": self.p["opt"]}


@_objective('blo', fidelity="illustrative", note="上层 Rastrigin + 下层最优响应耦合项的自拟函数，没有真正的嵌套优化", encoding="real")
def _obj_blo(self, s):
    # 双层优化（教学级）：上层 rastrigin + 下层最优响应耦合项
    v = self.variant
    upper = sum(x * x for x in s)
    lower_resp = sum(10 * math.cos(2 * math.pi * (x * 0.5)) for x in s)
    return round(upper + abs(lower_resp), 3)


def _ras(x):
    return 10 * len(x) + sum(v * v - 10 * math.cos(2 * math.pi * v) for v in x)


@_objective('ro', fidelity="simplified", note="场景是 8 个固定的随机扰动，没有区间不确定集的凸对偶化，也没有「预算化的不确定性」(Bertsimas–Sim)；目标函数是 Rastrigin 这个人造地形", encoding="real")
def _obj_ro(self, s):
    # 鲁棒优化（场景法）：最差情形目标 = max_k f(x + δₖ)；f 是 Rastrigin
    return round(max(_ras([a + d for a, d in zip(s, dl)]) for dl in self.p["scen"]), 6)


@_detail('ro')
def _detail_ro(self, s):
    vals = [_ras([a + d for a, d in zip(s, dl)]) for dl in self.p["scen"]]
    return {"nominal": round(_ras(s), 4), "scenarios": [round(v, 4) for v in vals], "worst": round(max(vals), 4)}


# ---- 批 3：选址族 10 变体目标 ----

@_objective('lap', fidelity="standard")
def _obj_lap(self, s):
    # 线性指派：Σ c[i][π(i)]
    v = self.variant
    c = self.p["c"]
    return sum(c[i][s[i]] for i in range(self.n))


@_objective('qap', fidelity="standard")
def _obj_qap(self, s):
    # 二次分配：ΣΣ 流量 a[i][j] × 距离 b[π(i)][π(j)]
    v = self.variant
    a, b = self.p["a"], self.p["b"]
    return sum(a[i][j] * b[s[i]][s[j]]
               for i in range(self.n) for j in range(self.n) if i != j)


@_objective('pmedian', 'pcenter', fidelity="standard")
def _obj_pmedian_etc2(self, s):
    # 前 p 位=设施；客户→最近设施
    v = self.variant
    pts, pfac = self.p["pts"], self.p["p"]
    fac = s[:pfac]
    ds = []
    for i in range(self.n):
        if i in fac:
            continue
        ds.append(min(math.dist(pts[i], pts[f]) for f in fac))
    if v == "pmedian":
        return round(sum(ds), 3)
    return round(max(ds) if ds else 0, 3)  # p-中心=minimize 最大距离


@_detail('pmedian', 'pcenter')
def _detail_pmedian_etc2(self, s):
    pts, pfac = self.p["pts"], self.p["p"]
    fac = list(s[:pfac])
    assign = [min(fac, key=lambda f: (math.dist(pts[i], pts[f]), f)) for i in range(self.n)]
    return {"fac": fac, "assign": assign, "dist": [round(math.dist(pts[i], pts[assign[i]]), 3) for i in range(self.n)]}


def _cflp_plan(self, s):
    """排列 s 给出开设顺序：先开到容量够覆盖总需求，再按需求从大到小把客户贪心派给「最近且还装得下」的已开设施；
    派不下就继续按排列顺序多开一个再试。返回（已开设施, {客户: 设施}, 是否全部派完）。"""
    pts, cap, dem = self.p["pts"], self.p["cap"], self.p["dem"]
    n, total = self.n, sum(self.p["dem"])
    opened, csum, k = [], 0, 0
    while csum < total and k < n:
        opened.append(s[k])
        csum += cap[s[k]]
        k += 1
    order = sorted(range(n), key=lambda i: (-dem[i], i))
    while True:
        res = {f: cap[f] for f in opened}
        asg, ok = {}, True
        for i in order:
            cands = [f for f in opened if res[f] >= dem[i]]
            if not cands:
                ok = False
                break
            f = min(cands, key=lambda f: (math.dist(pts[i], pts[f]), f))
            asg[i] = f
            res[f] -= dem[i]
        if ok or k >= n:
            return opened, asg, ok
        opened.append(s[k])
        k += 1


@_objective('cflp', fidelity="simplified", note="开设顺序由排列给出、开到容量够为止，客户用贪心而不是运输问题派给设施；设施固定费与运输费都是自拟尺度")
def _obj_cflp(self, s):
    opened, asg, _ok = _cflp_plan(self, s)
    pts, dem, fc = self.p["pts"], self.p["dem"], self.p["fc"]
    total = sum(fc[f] for f in opened) + sum(math.dist(pts[i], pts[f]) * dem[i] for i, f in asg.items())
    return round(total + self.BIG * (self.n - len(asg)), 3)


@_detail('cflp')
def _detail_cflp(self, s):
    opened, asg, ok = _cflp_plan(self, s)
    cap, dem = self.p["cap"], self.p["dem"]
    load = {f: 0 for f in opened}
    for i, f in asg.items():
        load[f] += dem[i]
    return {"open": opened, "assign": [asg.get(i, -1) for i in range(self.n)], "load": [load.get(f, 0) for f in range(self.n)],
            "cap": cap, "fixed": sum(self.p["fc"][f] for f in opened), "feasible": ok}


def _lrp_plan(self, s):
    """排列前 p 位 = 仓库；其余客户归最近的仓库，同一仓库的客户按排列顺序依次装车，装不下就换一辆；每辆车从仓库出发、回仓库。"""
    pts, dem, cap, p = self.p["pts"], self.p["dem"], self.p["cap"], self.p["p"]
    depots = list(s[:p])
    mine = {d: [] for d in depots}
    for c in s[p:]:
        mine[min(depots, key=lambda d: (math.dist(pts[c], pts[d]), d))].append(c)
    trips = []
    for d in depots:
        cur, load = [], 0
        for c in mine[d]:
            if cur and load + dem[c] > cap:
                trips.append((d, cur))
                cur, load = [], 0
            cur.append(c)
            load += dem[c]
        if cur:
            trips.append((d, cur))
    length = 0.0
    for d, cs in trips:
        path = [d] + cs + [d]
        length += sum(math.dist(pts[path[i]], pts[path[i + 1]]) for i in range(len(path) - 1))
    return depots, trips, length


@_objective('lrp', fidelity="simplified", note="仓库个数固定为 2；客户归最近仓库、按排列顺序装车（不优化每辆车内的路线顺序）；没有仓库容量")
def _obj_lrp(self, s):
    depots, trips, length = _lrp_plan(self, s)
    return round(length + self.p["depot_cost"] * len(depots) + self.p["veh_cost"] * len(trips), 3)


@_detail('lrp')
def _detail_lrp(self, s):
    depots, trips, length = _lrp_plan(self, s)
    return {"depots": depots, "trips": [[d, list(cs)] for d, cs in trips], "length": round(length, 3)}


def _ndp_state(self, s):
    edges, pairs = self.p["edges"], self.p["pairs"]
    par = list(range(self.p["n_pts"]))

    def find(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    cost = 0
    for k, (a, b, w) in enumerate(edges):
        if s[k]:
            cost += w
            ra, rb = find(a), find(b)
            if ra != rb:
                par[ra] = rb
    return cost, [find(a) == find(b) for a, b in pairs]


@_objective('ndp', fidelity="simplified", note="只要求需求点对连通（斯坦纳森林），没有流量、容量，也没有「固定费 + 单位费」两部分费用", encoding="bits")
def _obj_ndp(self, s):
    cost, conn = _ndp_state(self, s)
    return cost + 500 * sum(1 for c in conn if not c)


@_detail('ndp')
def _detail_ndp(self, s):
    cost, conn = _ndp_state(self, s)
    return {"sel": [int(x) for x in s], "cost": cost, "connected": conn, "violations": sum(1 for c in conn if not c), "size": int(sum(s))}


@_objective('tdm', fidelity="standard", encoding="bits")
def _obj_tdm(self, s):
    # 3-维匹配（最大化版）：选尽量多的两两不相交三元组；与集合打包同构（元素被重复占用 × BIG 罚）
    return _obj_setpack(self, s)


@_detail('tdm')
def _detail_tdm(self, s):
    cover = [0] * len(self.p["sets"][0])
    for i, row in enumerate(self.p["sets"]):
        if s[i]:
            for j, e in enumerate(row):
                if e:
                    cover[j] += 1
    return {"sel": [int(x) for x in s], "violations": sum(c - 1 for c in cover if c > 1), "size": int(sum(s)), "q": self.p["q"]}


@_objective('freqasg', fidelity="simplified", note="频率数固定为 6，相邻频率也算冲突；不是通用频率分配")
def _obj_freqasg(self, s):
    # 频率分配：取模分 6 频率，冲突对罚（同着色）
    v = self.variant
    conf, slots = self.p["conf"], self.p["slots"]
    slot_of = {x: i % slots for i, x in enumerate(s)}
    viol = sum(conf[a][b] for a in range(self.n) for b in range(a + 1, self.n)
               if abs(slot_of[a] - slot_of[b]) <= 1)  # 相邻频率也算冲突
    return self.BIG * viol


# ---- 批 4：图问题族 12 变体目标 ----

@_objective('mclique', fidelity="standard")
def _obj_mclique(self, s):
    # 排列序构建团：依次加入与团内全部邻接的点
    v = self.variant
    edges, nn = self.p["edges"], self.n
    adj = {a: set() for a in range(nn)}
    for (a, b, _) in edges:
        adj[a].add(b)
        adj[b].add(a)
    clique = []
    for x in s:
        if all(y in adj[x] for y in clique):
            clique.append(x)
    return -len(clique)  # 最大化团大小


@_objective('gpp', fidelity="standard")
def _obj_gpp(self, s):
    # 图划分：均衡两块+最小割（与 maxcut 相反目标）
    v = self.variant
    side = {x: i % 2 for i, x in enumerate(s)}
    cut = sum(w for (a, b, w) in self.p["edges"] if side[a] != side[b])
    bal = abs(sum(1 for x in s if side[x] == 0) - self.n // 2)
    return cut + 50 * bal


@_objective('csplogic', fidelity="simplified", note="取模赋值 + 冲突罚，规模与约束类型有限")
def _obj_csplogic(self, s):
    # 约束满足：取模赋值，冲突罚（同 etp 模式）
    v = self.variant
    conf, slots = self.p["conf"], self.p["slots"]
    slot_of = {x: i % slots for i, x in enumerate(s)}
    viol = sum(conf[a][b] for a in range(self.n) for b in range(a + 1, self.n)
               if slot_of[a] == slot_of[b])
    return self.BIG * viol


# ============================================================ 上下文与入口

# ============================================================ 第一梯队新增（2026-10）
# 每个变体 = 一对 @_maker / @_objective；需要在页面上画出「解长什么样」的变体再登记一个 @_detail。

# ---------------------------------------------------------------- 子集类问题：位向量编码（每一位 = 选 / 不选）
# 与排列版的区别：k 不再是写死的常数，目标里既有「选了多少」也有「违反了多少」，约束违反用 BIG 罚（BIG 远大于任何可行目标之差）。

def _es_graph_adj(p):
    adj = [set() for _ in range(p["n"])]
    for (a, b, _w) in p["edges"]:
        adj[a].add(b)
        adj[b].add(a)
    return adj


@_objective('vcover', fidelity="standard", encoding="bits")
def _obj_vcover(self, s):
    # 顶点覆盖：选尽量少的顶点，使每条边至少有一个端点被选
    unc = sum(1 for (a, b, _w) in self.p["edges"] if not s[a] and not s[b])
    return self.BIG * unc + sum(s)


@_objective('domset', fidelity="standard", encoding="bits")
def _obj_domset(self, s):
    # 支配集：选尽量少的顶点，使每个顶点要么被选、要么有被选的邻居
    adj = _es_graph_adj(self.p)
    und = sum(1 for v in range(self.n) if not s[v] and not any(s[u] for u in adj[v]))
    return self.BIG * und + sum(s)


def _fvs_cycles(p, removed):
    """删掉 removed 之后剩下的图里「多余的边数」（= 圈秩；0 表示是森林）。"""
    parent = list(range(p["n"]))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    cyc = 0
    for (a, b, _w) in p["edges"]:
        if removed[a] or removed[b]:
            continue
        ra, rb = find(a), find(b)
        if ra == rb:
            cyc += 1
        else:
            parent[ra] = rb
    return cyc


@_objective('fvs', fidelity="standard", encoding="bits")
def _obj_fvs(self, s):
    # 反馈顶点集：删尽量少的顶点，使剩下的图没有环（并查集数「多余的边」）
    return self.BIG * _fvs_cycles(self.p, s) + sum(s)


@_objective('maxcut', fidelity="standard", encoding="bits")
def _obj_maxcut(self, s):
    # 最大割：每个顶点一位 = 在哪一侧（不要求两侧一样大），最大化跨侧边权和（取负）
    return -sum(w for (a, b, w) in self.p["edges"] if s[a] != s[b])


@_objective('setpack', fidelity="standard", encoding="bits")
def _obj_setpack(self, s):
    # 集合打包：选尽量多的两两不相交的集合（每位 = 选不选这个集合）；重叠的元素数 × BIG 罚
    sets = self.p["sets"]
    cover = [0] * len(sets[0])
    for i, row in enumerate(sets):
        if s[i]:
            for j, e in enumerate(row):
                if e:
                    cover[j] += 1
    return self.BIG * sum(c - 1 for c in cover if c > 1) - sum(s)


@_objective('hset', fidelity="standard", encoding="bits")
def _obj_hset(self, s):
    # 击中集：选尽量少的元素（每位 = 选不选这个元素），使每个集合至少含一个被选元素
    unh = sum(1 for row in self.p["sets"] if not any(row[j] and s[j] for j in range(self.n)))
    return self.BIG * unh + sum(s)


@_maker('stp')
def _make_stp(variant, n, seed, rng):
    # 斯坦纳树：平面上的点集 + 必需点（terminal）；其余点是可选的中转点（Steiner 点）
    nn = max(8, min(n, 14))
    pts = [[round(rng.uniform(0, 100), 1), round(rng.uniform(0, 100), 1)] for _ in range(nn)]
    req = sorted(rng.sample(range(nn), max(3, nn // 3)))
    return {"variant": variant, "pts": pts, "req": req, "n": nn}


def _mst_len(pts, nodes):
    """完全欧氏图上 nodes 的最小生成树长度（Prim）。"""
    nodes = list(nodes)
    if len(nodes) < 2:
        return 0.0
    dist = {v: math.dist(pts[nodes[0]], pts[v]) for v in nodes[1:]}
    total = 0.0
    while dist:
        v = min(dist, key=dist.get)
        total += dist.pop(v)
        for u in dist:
            d = math.dist(pts[v], pts[u])
            if d < dist[u]:
                dist[u] = d
    return total


@_objective('stp', fidelity="standard", encoding="bits")
def _obj_stp(self, s):
    # 图上的斯坦纳树：必需点一定在树里；每个其余点一位 = 要不要作为中转点；
    # 目标 = 必需点 ∪ 被选中转点 在完全欧氏图上的最小生成树长度（最优斯坦纳树恰好是某个点子集的最小生成树）
    req = self.p["req"]
    nodes = set(req) | {i for i in range(self.n) if s[i]}
    return round(_mst_len(self.p["pts"], nodes), 3)


@_detail('vcover', 'domset', 'fvs', 'maxcut', 'stp')
def _detail_graph_bits(self, s):
    p = self.p
    if self.variant == "vcover":
        bad = sum(1 for (a, b, _w) in p["edges"] if not s[a] and not s[b])
    elif self.variant == "domset":
        adj = _es_graph_adj(p)
        bad = sum(1 for v in range(self.n) if not s[v] and not any(s[u] for u in adj[v]))
    elif self.variant == "fvs":
        bad = _fvs_cycles(p, s)
    elif self.variant == "maxcut":
        bad = 0
    else:
        bad = 0
    out = {"sel": [int(x) for x in s], "violations": bad, "size": int(sum(s))}
    if self.variant == "maxcut":
        out["cut"] = sum(w for (a, b, w) in p["edges"] if s[a] != s[b])
        out["total"] = sum(w for (_a, _b, w) in p["edges"])
    if self.variant == "stp":
        nodes = set(p["req"]) | {i for i in range(self.n) if s[i]}
        out["nodes"] = sorted(nodes)
        out["mst"] = round(_mst_len(p["pts"], nodes), 3)
    return out


@_detail('setpack', 'hset')
def _detail_set_bits(self, s):
    sets = self.p["sets"]
    if self.variant == "setpack":
        cover = [0] * len(sets[0])
        for i, row in enumerate(sets):
            if s[i]:
                for j, e in enumerate(row):
                    if e:
                        cover[j] += 1
        bad = sum(c - 1 for c in cover if c > 1)
    else:
        bad = sum(1 for row in sets if not any(row[j] and s[j] for j in range(self.n)))
    return {"sel": [int(x) for x in s], "violations": bad, "size": int(sum(s))}


# ---------------------------------------------------------------- 定向运动 OP（2026-10 重建为标准模型）

@_maker('orienteering')
def _make_orienteering(variant, n, seed, rng):
    # 仓库居中 + n 个带收益的点；预算 = 最近邻回路长度的 45%——走不完所有点，必须挑「值得去的」
    k = max(8, min(n, 20))
    pts = [[50.0, 50.0]] + [[round(rng.uniform(0, 100), 1), round(rng.uniform(0, 100), 1)] for _ in range(k)]
    gain = [0] + [rng.randint(5, 20) for _ in range(k)]
    left, cur, tour = set(range(1, k + 1)), 0, 0.0
    while left:
        nxt = min(left, key=lambda j: math.dist(pts[cur], pts[j]))
        tour += math.dist(pts[cur], pts[nxt])
        left.remove(nxt)
        cur = nxt
    tour += math.dist(pts[cur], pts[0])
    return {"variant": variant, "pts": pts, "gain": gain, "budget": round(0.45 * tour, 1), "n": k}  # n = 客户数


def _op_route(p, s):
    """按优先序 s 依次访问：该点放得下（去了还能在预算内回仓库）才去，放不下的跳过。
    任何可行路线都可以写成「它的访问序在前、其余点在后」的优先序，所以这个解码不丢最优解。"""
    pts, budget = p["pts"], p["budget"]
    route, cur, used = [0], 0, 0.0
    for x in s:
        j = x + 1
        d = math.dist(pts[cur], pts[j])
        if used + d + math.dist(pts[j], pts[0]) <= budget + 1e-9:
            route.append(j)
            used += d
            cur = j
    used += math.dist(pts[cur], pts[0])
    route.append(0)
    return route, used


@_objective('orienteering', fidelity="standard",
            note="")
def _obj_orienteering(self, s):
    # 定向运动：在预算内选点并排路线，最大化收集的收益（取负）；同分时极小的路程项偏好更短的路线
    route, length = _op_route(self.p, s)
    return round(-sum(self.p["gain"][j] for j in route) + length / 10000.0, 6)


@_detail('orienteering')
def _detail_orienteering(self, s):
    route, length = _op_route(self.p, s)
    return {"route": route, "score": sum(self.p["gain"][j] for j in route), "length": round(length, 2),
            "budget": self.p["budget"], "total_gain": sum(self.p["gain"])}


# ---------------------------------------------------------------- 资源受限项目调度 RCPSP（串行调度生成方案）

@_maker('rcpsp')
def _make_rcpsp(variant, n, seed, rng):
    # n 个活动（工期 1~6）、前序关系（只从编号小的指向编号大的，保证无环）、2 种可再生资源
    k = max(6, min(n, 20))
    dur = [rng.randint(1, 6) for _ in range(k)]
    preds = [sorted(rng.sample(range(i), min(i, rng.randint(0, 2)))) if i else [] for i in range(k)]
    r = [[rng.randint(0, 4) for _ in range(2)] for _ in range(k)]
    return {"variant": variant, "dur": dur, "preds": preds, "r": r, "caps": [6, 6], "n": k}


def rcpsp_schedule(p, order):
    """串行调度生成方案（serial SGS，RCPSP 最标准的解码）：按优先序依次取「前序都已排好」的第一个活动，
    排在满足前序与资源上限的最早开工时刻。返回 (开工时间, 完工时间, 工期)。"""
    dur, preds, r, caps = p["dur"], p["preds"], p["r"], p["caps"]
    n, K = len(dur), len(caps)
    horizon = sum(dur)
    usage = [[0] * (horizon + 1) for _ in range(K)]
    start, end = [None] * n, [None] * n
    todo = list(order)
    while todo:
        idx = next(i for i, a in enumerate(todo) if all(start[q] is not None for q in preds[a]))
        a = todo.pop(idx)
        t = max((end[q] for q in preds[a]), default=0)
        while any(usage[k][u] + r[a][k] > caps[k] for k in range(K) for u in range(t, t + dur[a])):
            t += 1
        for k in range(K):
            for u in range(t, t + dur[a]):
                usage[k][u] += r[a][k]
        start[a], end[a] = t, t + dur[a]
    return start, end, max(end)


@_objective('rcpsp', fidelity="standard")
def _obj_rcpsp(self, s):
    # 目标 = 项目工期（最后一个活动的完工时刻）。解 = 活动的优先序，解码 = 串行调度生成方案
    return rcpsp_schedule(self.p, s)[2]


@_detail('rcpsp')
def _detail_rcpsp(self, s):
    start, end, mk = rcpsp_schedule(self.p, s)
    p = self.p
    n = len(p["dur"])
    longest = [0] * n  # 关键路径（只看前序、不看资源）= 工期的一个下界
    for i in range(n):
        longest[i] = p["dur"][i] + max((longest[q] for q in p["preds"][i]), default=0)
    res_lb = max(-(-sum(p["dur"][i] * p["r"][i][k] for i in range(n)) // p["caps"][k]) for k in range(len(p["caps"])))
    return {"start": start, "end": end, "makespan": mk, "lb": max(max(longest), res_lb)}


# ---------------------------------------------------------------- 非对称旅行商 ATSP

@_maker('atsp')
def _make_atsp(variant, n, seed, rng):
    # 非对称 TSP：去程与回程代价不同（单行线、顺逆风、上下坡）。距离 = 欧氏距离 × 每条有向边各自的随机因子，取整
    k = max(5, min(n, 30))
    pts = [[round(rng.uniform(0, 100), 1), round(rng.uniform(0, 100), 1)] for _ in range(k)]
    d = [[0 if i == j else int(round(math.dist(pts[i], pts[j]) * rng.uniform(0.7, 1.6))) for j in range(k)]
         for i in range(k)]
    return {"variant": variant, "pts": pts, "d": d, "n": k}  # pts 只用来画图，代价全在矩阵 d 里


@_objective('atsp', fidelity="standard")
def _obj_atsp(self, s):
    # 回路总代价：沿访问顺序累加有向边代价 d[i][j]（i→j 与 j→i 可以不同），最后回到起点
    d = self.p["d"]
    return sum(d[s[i]][s[(i + 1) % len(s)]] for i in range(len(s)))


@_detail('vrptw', 'vrpstw')
def _detail_vrptw(self, s):
    arcs = _vrptw_arcs_of(self, s)
    n = len(s)
    tour = [x + 1 for x in s]
    total, spans = vrptw_split(arcs, n, self.p["m_veh"])
    within = total is not None
    if not within:
        _f, _u, spans = vrptw_free_split(arcs, n)
    routes = [tour[i:j] for i, j in spans]
    sched = [vrptw_schedule(self.p, r) for r in routes]
    wait = sum(a[1] - a[0] for sc in sched for a in sc)
    out = {"routes": routes, "sched": sched, "wait": round(wait, 2), "within_fleet": within}
    if "lam" in self.p:  # 软时间窗：迟到总量（客户窗 + 回仓晚于关门）和里程分开给，目标 = 里程 + lam × 迟到
        late = sum(max(0.0, a[0] - self.p["l"][c]) for r, sc in zip(routes, sched) for c, a in zip(r, sc))
        for r, sc in zip(routes, sched):
            late += max(0.0, sc[-1][2] + math.dist(self.p["pts"][r[-1]], self.p["pts"][0]) - self.p["l"][0])
        dist = sum(sum(math.dist(self.p["pts"][a], self.p["pts"][b]) for a, b in zip([0] + r, r + [0])) for r in routes)
        out.update(late=round(late, 2), dist=round(dist, 2))
    return out


@_detail('mdvrp')
def _detail_mdvrp(self, s):
    _tot, parts = mdvrp_split_all(self, s)
    D = self.p["D"]
    routes, depot_of = [], []
    for d, rts, _w in parts:
        for r in rts:
            routes.append([D + c - 1 for c in r])  # 1..k → pts 下标（仓库在前）
            depot_of.append(d)
    return {"routes": routes, "route_depot": depot_of, "within_fleet": all(w for _d, _r, w in parts),
            "per_depot": [len(r) for _d, r, _w in parts]}


@_detail('atsp')
def _detail_atsp(self, s):
    return {"order": list(s)}


# ---------------------------------------------------------------- 并行机调度 P||Cmax

@_maker('pms')
def _make_pms(variant, n, seed, rng):
    k = max(6, min(n, 40))
    m = 3 if k <= 16 else (4 if k <= 28 else 5)
    return {"variant": variant, "p": [rng.randint(5, 40) for _ in range(k)], "m_mach": m, "n": k}


def _pms_assign(p, m, order):
    """表调度（list scheduling）：按优先序依次把作业放到当前负载最小的机器。
    任何最优调度都能表示成某个优先序的表调度，所以搜索优先序就覆盖了全部最优解。"""
    loads = [0] * m
    machines = [[] for _ in range(m)]
    for j in order:
        i = loads.index(min(loads))
        loads[i] += p[j]
        machines[i].append(j)
    return loads, machines


@_objective('pms', fidelity="standard")
def _obj_pms(self, s):
    # 目标 = 最大完工时间 makespan（Cmax）：最忙那台机器的总加工时间
    loads, _ = _pms_assign(self.p["p"], self.p["m_mach"], s)
    return max(loads)


@_detail('pms')
def _detail_pms(self, s):
    loads, machines = _pms_assign(self.p["p"], self.p["m_mach"], s)
    total = sum(self.p["p"])
    return {"machines": machines, "loads": loads,
            "lb": max(max(self.p["p"]), -(-total // self.p["m_mach"]))}  # 下界 max(最长作业, ⌈总时间/机器数⌉)


# ---------------------------------------------------------------- 数分割

@_maker('numpart')
def _make_numpart(variant, n, seed, rng):
    k = max(6, min(n, 40))
    return {"variant": variant, "a": [rng.randint(1, 10000) for _ in range(k)], "n": k}


@_objective('numpart', fidelity="standard", encoding="real")
def _obj_numpart(self, s):
    # 实数向量 s：s[i] > 0 → 第 i 个数放进集合 A，否则放进 B；目标 = |ΣA − ΣB|（越小越均衡，0 = 完美划分）
    a = self.p["a"]
    return abs(sum(a[i] if s[i] > 0 else -a[i] for i in range(len(a))))


@_detail('numpart')
def _detail_numpart(self, s):
    a = self.p["a"]
    side = [1 if s[i] > 0 else 0 for i in range(len(a))]
    return {"side": side, "sum_a": sum(a[i] for i in range(len(a)) if side[i]),
            "sum_b": sum(a[i] for i in range(len(a)) if not side[i])}


# ---------------------------------------------------------------- k-means 聚类（中心点优化）

@_maker('kmeans')
def _make_kmeans(variant, n, seed, rng):
    # 簇数 k：n ≤ 15 取 3，之后每 10 加 1（最多 6）；每簇约 20 个点，高斯团块
    k = 3 if n <= 15 else min(6, 2 + n // 10)
    centers = [[rng.uniform(15, 85), rng.uniform(15, 85)] for _ in range(k)]
    pts = []
    for c in centers:
        sd = rng.uniform(5, 10)
        pts += [[round(rng.gauss(c[0], sd), 2), round(rng.gauss(c[1], sd), 2)] for _ in range(20)]
    return {"variant": variant, "pts": pts, "k": k, "n": 2 * k}  # n = 决策向量长度 = 2k（k 个中心的 x,y）


def _kmeans_centers(p, s):
    """向量 s ∈ [−5,5]^(2k) → k 个中心：每个坐标按比例映射到数据包围盒里（所以用户的点集不论坐标尺度都能用）。"""
    xs = [q[0] for q in p["pts"]]
    ys = [q[1] for q in p["pts"]]
    lo, hi = (min(xs), min(ys)), (max(xs), max(ys))
    out = []
    for c in range(p["k"]):
        out.append([lo[0] + (min(5, max(-5, s[2 * c])) + 5) / 10 * (hi[0] - lo[0]),
                    lo[1] + (min(5, max(-5, s[2 * c + 1])) + 5) / 10 * (hi[1] - lo[1])])
    return out


@_objective('kmeans', fidelity="standard", encoding="real")
def _obj_kmeans(self, s):
    # k-means 的目标：每个点到最近中心的平方距离之和（SSE）。这里直接优化中心位置，不做 Lloyd 迭代
    cs = _kmeans_centers(self.p, s)
    return round(sum(min((q[0] - c[0]) ** 2 + (q[1] - c[1]) ** 2 for c in cs) for q in self.p["pts"]), 3)


@_detail('kmeans')
def _detail_kmeans(self, s):
    cs = _kmeans_centers(self.p, s)
    assign = [min(range(len(cs)), key=lambda c: (q[0] - cs[c][0]) ** 2 + (q[1] - cs[c][1]) ** 2)
              for q in self.p["pts"]]
    return {"centers": [[round(v, 3) for v in c] for c in cs], "assign": assign}


# ---------------------------------------------------------------- 分数背包（实数向量编码）

@_maker('fkp')
def _make_fkp(variant, n, seed, rng):
    # 分数背包：每个物品可以只取一部分（比例 x∈[0,1]）。物品分布与 0-1 背包页相同：重量 2–60、价值 10–100、容量 = 总重量的 45%
    nn = max(8, min(n, 60))
    w = [rng.randint(2, 60) for _ in range(nn)]
    v = [rng.randint(10, 100) for _ in range(nn)]
    cap = int(sum(w) * 0.45)
    lp, rest = 0.0, cap
    for i in sorted(range(nn), key=lambda i: -v[i] / w[i]):  # 贪心（按价值密度）就是分数背包的精确最优
        take = min(1.0, rest / w[i])
        lp += v[i] * take
        rest -= w[i] * take
        if rest <= 1e-12:
            break
    return {"variant": variant, "w": w, "v": v, "cap": cap, "n": nn, "lp": round(lp, 6)}


def _fkp_x(s):
    return [min(1.0, max(0.0, (x + 5.0) / 10.0)) for x in s]  # 决策向量 [−5,5] 线性映射成取用比例 [0,1]


@_objective('fkp', fidelity="standard", encoding="real")
def _obj_fkp(self, s):
    # 最大化 Σ vᵢxᵢ，s.t. Σ wᵢxᵢ ≤ 容量。用精确罚函数 −价值 + λ·超重，λ = 最大价值密度 + 1：
    # λ 不小于任何一个物品的价值密度时，罚函数的最优与带约束的最优一致（超重 1 单位至多换来 λ 的收益，永远不划算）
    x = _fkp_x(s)
    w, v = self.p["w"], self.p["v"]
    lam = max(vi / wi for vi, wi in zip(v, w)) + 1.0
    over = max(0.0, sum(wi * xi for wi, xi in zip(w, x)) - self.p["cap"])
    return round(-sum(vi * xi for vi, xi in zip(v, x)) + lam * over, 6)


@_detail('fkp')
def _detail_fkp(self, s):
    x = _fkp_x(s)
    w, v = self.p["w"], self.p["v"]
    return {"x": [round(t, 4) for t in x], "weight": round(sum(a * b for a, b in zip(w, x)), 4),
            "value": round(sum(a * b for a, b in zip(v, x)), 4), "lp": self.p["lp"], "cap": self.p["cap"]}


# ---------------------------------------------------------------- 工程约束设计（4 个经典算例）
# 决策向量 s ∈ [−5,5]^n 按比例映射到各变量的取值范围；约束写成无量纲形式 g ≤ 0（g = 实际值/限值 − 1），
# 违反量按 精确罚函数 f + 1000·f_scale·Σmax(0,g) 计入（权重大于拉格朗日乘子，所以罚函数的最优 = 约束问题的最优）。

_DESIGN = {}


def _design(variant, names, bounds, f_scale, best):
    def deco(fn):
        _DESIGN[variant] = {"names": names, "bounds": bounds, "f_scale": f_scale, "best": best, "fn": fn}
        return fn
    return deco


def _design_x(variant, s):
    b = _DESIGN[variant]["bounds"]
    return [lo + (min(5, max(-5, v)) + 5) / 10 * (hi - lo) for v, (lo, hi) in zip(s, b)]


def _design_eval(variant, s):
    spec = _DESIGN[variant]
    x = _design_x(variant, s)
    f, g = spec["fn"](x)
    return x, f, g


@_design("wbeam", ["h 焊缝厚度", "l 焊缝长度", "t 梁高", "b 梁宽"],
         [(0.1, 2.0), (0.1, 10.0), (0.1, 10.0), (0.1, 2.0)], 1.0, 1.724852)
def _wbeam(x):
    # 焊接梁（Coello 2000）：最小化制造成本；约束 = 剪应力 / 弯曲应力 / 几何 / 挠度 / 屈曲载荷
    h, l, t, b = x
    P, L, E, G = 6000.0, 14.0, 30e6, 12e6
    tau_max, sigma_max, delta_max = 13600.0, 30000.0, 0.25
    f = 1.10471 * h * h * l + 0.04811 * t * b * (14.0 + l)
    M = P * (L + l / 2.0)
    R = math.sqrt(l * l / 4.0 + ((h + t) / 2.0) ** 2)
    J = 2.0 * (math.sqrt(2.0) * h * l * (l * l / 12.0 + ((h + t) / 2.0) ** 2))
    t1 = P / (math.sqrt(2.0) * h * l)
    t2 = M * R / J
    tau = math.sqrt(t1 * t1 + 2.0 * t1 * t2 * l / (2.0 * R) + t2 * t2)
    sigma = 6.0 * P * L / (b * t * t)
    delta = 4.0 * P * L ** 3 / (E * t ** 3 * b)
    Pc = (4.013 * E * math.sqrt(t * t * b ** 6 / 36.0) / (L * L)) * (1.0 - t / (2.0 * L) * math.sqrt(E / (4.0 * G)))
    g = [tau / tau_max - 1.0, sigma / sigma_max - 1.0, (h - b) / 2.0,
         (0.10471 * h * h + 0.04811 * t * b * (14.0 + l) - 5.0) / 5.0, (0.125 - h) / 0.125,
         delta / delta_max - 1.0, 1.0 - Pc / P]
    return f, g


@_design("pvessel", ["Ts 筒壁厚", "Th 封头厚", "R 内半径", "L 筒长"],
         [(0.0625, 6.1875), (0.0625, 6.1875), (10.0, 200.0), (10.0, 200.0)], 6000.0, 5885.3328)
def _pvessel(x):
    # 压力容器（Sandgren 1990，连续变量版）：最小化材料 + 成型 + 焊接成本
    Ts, Th, R, L = x
    f = 0.6224 * Ts * R * L + 1.7781 * Th * R * R + 3.1661 * Ts * Ts * L + 19.84 * Ts * Ts * R
    g = [(-Ts + 0.0193 * R) / 1.0, (-Th + 0.00954 * R) / 1.0,
         (-math.pi * R * R * L - 4.0 / 3.0 * math.pi * R ** 3 + 1296000.0) / 1296000.0, (L - 240.0) / 240.0]
    return f, g


@_design("tcspring", ["d 线径", "D 簧圈中径", "N 有效圈数"],
         [(0.05, 2.0), (0.25, 1.3), (2.0, 15.0)], 0.0127, 0.012665)
def _tcspring(x):
    # 拉压弹簧（Arora 1989）：最小化重量；约束 = 最小挠度 / 剪应力 / 颤振频率 / 外径
    d, D, N = x
    f = (N + 2.0) * D * d * d
    g = [1.0 - D ** 3 * N / (71785.0 * d ** 4),
         (4.0 * D * D - d * D) / (12566.0 * (D * d ** 3 - d ** 4)) + 1.0 / (5108.0 * d * d) - 1.0,
         1.0 - 140.45 * d / (D * D * N), (d + D) / 1.5 - 1.0]
    return f, g


@_design("reducer", ["b 齿宽", "m 模数", "z 小齿轮齿数", "l1 轴1跨距", "l2 轴2跨距", "d1 轴1直径", "d2 轴2直径"],
         [(2.6, 3.6), (0.7, 0.8), (17.0, 28.0), (7.3, 8.3), (7.3, 8.3), (2.9, 3.9), (5.0, 5.5)], 3000.0, 2994.4711)
def _reducer(x):
    # 减速器（Golinski）：最小化重量；11 个约束 = 齿弯曲应力 / 接触应力 / 轴挠度 / 轴应力 / 几何
    b, m, z, l1, l2, d1, d2 = x
    f = (0.7854 * b * m * m * (3.3333 * z * z + 14.9334 * z - 43.0934)
         - 1.508 * b * (d1 * d1 + d2 * d2) + 7.4777 * (d1 ** 3 + d2 ** 3) + 0.7854 * (l1 * d1 * d1 + l2 * d2 * d2))
    g = [27.0 / (b * m * m * z) - 1.0, 397.5 / (b * m * m * z * z) - 1.0,
         1.93 * l1 ** 3 / (m * d1 ** 4 * z) - 1.0, 1.93 * l2 ** 3 / (m * d2 ** 4 * z) - 1.0,
         math.sqrt((745.0 * l1 / (m * z)) ** 2 + 16.9e6) / (110.0 * d1 ** 3) - 1.0,
         math.sqrt((745.0 * l2 / (m * z)) ** 2 + 157.5e6) / (85.0 * d2 ** 3) - 1.0,
         m * z / 40.0 - 1.0, 5.0 * m / b - 1.0, b / (12.0 * m) - 1.0,
         (1.5 * d1 + 1.9) / l1 - 1.0, (1.1 * d2 + 1.9) / l2 - 1.0]
    return f, g


def _obj_design(self, s):
    x, f, g = _design_eval(self.variant, s)
    return round(f + 1000.0 * _DESIGN[self.variant]["f_scale"] * sum(max(0.0, v) for v in g), 6)


for _v, _note in (("wbeam", ""), ("pvessel", ""), ("tcspring", ""), ("reducer", "")):
    _OBJS[_v] = _obj_design
    FIDELITY[_v] = {"level": "standard", "note": _note}
    ENCODING[_v] = "real"


@_detail('wbeam', 'pvessel', 'tcspring', 'reducer')
def _detail_design(self, s):
    spec = _DESIGN[self.variant]
    x, f, g = _design_eval(self.variant, s)
    return {"names": spec["names"], "bounds": spec["bounds"], "x": [round(v, 5) for v in x],
            "f": round(f, 6), "g": [round(v, 5) for v in g], "feasible": all(v <= 1e-9 for v in g),
            "best_known": spec["best"]}


def _make_design(variant, n, seed, rng):
    return {"variant": variant, "n": len(_DESIGN[variant]["names"])}


for _v in ("wbeam", "pvessel", "tcspring", "reducer"):
    _MAKERS[_v] = _make_design


# ---- 新变体：tools/new_problem.py 把生成的 @_maker / @_objective 追加在这一行之前 ----


VARIANTS = tuple(_MAKERS)  # 注册顺序 = 变体清单的唯一来源（必须放在所有 @_maker 登记之后）
BIT_VARIANTS = tuple(v for v in _OBJS if ENCODING[v] == "bits")  # 位向量编码的变体（每位 = 选 / 不选）：由各 @_objective 的 encoding 得出
VEC_VARIANTS = tuple(v for v in _OBJS if ENCODING[v] == "real")  # 实数向量编码的变体（其余为排列编码）
assert set(ENCODING) == set(_OBJS), "每个变体都必须有编码（@_objective 默认 perm）"
assert set(_MAKERS) == set(_OBJS), "每个变体必须同时有 maker 与 objective"
assert set(FIDELITY) == set(_OBJS), "每个变体都必须登记保真度"


def es_make(variant="vrp", n=12, seed=7):
    """实例生成入口：按变体分派到该变体的 @_maker 函数（n 为规模上限，各变体取语义安全子规模）。未知变体返回 None。"""
    fn = _MAKERS.get(variant)
    if fn is None:
        return None
    return fn(variant, n, seed, random.Random(seed))


class _ES:
    """entryseq 上下文：排列编码（批 5 黑箱/多目标族为实数向量），变体专属 obj。"""

    BIG = 4000
    VEC_VARIANTS = VEC_VARIANTS

    def __init__(self, problem):
        self.p = problem
        self.variant = problem["variant"]
        self.n = problem["n"]
        self.vec = self.variant in self.VEC_VARIANTS
        self.bits = self.variant in BIT_VARIANTS

    def random(self, rng):
        if self.bits:  # 子集类：每位 0/1
            return [rng.randint(0, 1) for _ in range(self.n)]
        if self.vec:  # 黑箱/多目标族：实数向量（rastrigin 域 [−5,5]）
            return [rng.uniform(-5, 5) for _ in range(self.n)]
        s = list(range(self.n))
        rng.shuffle(s)
        return s

    def swap(self, s, rng):
        if self.bits:  # 位向量邻域 = 翻转一位
            s = list(s)
            s[rng.randrange(self.n)] ^= 1
            return s
        if self.vec:  # 向量邻域=高斯扰动
            return [max(-5, min(5, v + rng.gauss(0, 0.5))) for v in s]
        s = list(s)
        i, j = rng.randrange(self.n), rng.randrange(self.n)
        s[i], s[j] = s[j], s[i]
        return s

    def detail(self, s):
        """页面可视化需要的附加信息（见 @_detail）：由当前最优解推出，随每个状态一起发给页面。"""
        fn = _DETAIL.get(self.variant)
        if fn is not None:
            return fn(self, s)
        if self.variant == "vrp":
            return {"routes": self.routes(s)}
        return None

    def routes(self, s):
        """（仅 vrp）把访问序切成路线，返回各路线的 pts 下标列表；切不进车队时按不限车队切（页面仍能画出来）。"""
        D = _vrp_dist(self)
        tour = [x + 1 for x in s]
        _t, routes = vrp_split(D, self.p["demand"], self.p["cap"], self.p["m_veh"], tour)
        if routes is None:
            routes = _vrp_free_routes(D, self.p["demand"], self.p["cap"], tour)
        return routes

    # ---- 变体目标 ----

    def obj(self, s):
        """变体目标：分派到本文件里该变体的 @_objective 函数。"""
        return _OBJS[self.variant](self, s)


class _ESBits(_ES):
    """位向量编码的变体（BIT_VARIANTS）：补上位编码算法要求的协议——value = -obj，repair 恒等，init_pop，polish。
    只给位向量变体加这些方法：排列变体的 de / gwo / cs 靠「ctx 没有 init_pop」判断自己该走排列分支。"""

    def value(self, s):
        return -self.obj(s)

    def repair(self, s):
        return list(s)

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(p["n_pop"])]
        return pop, [self.obj(x) for x in pop]

    def polish(self, s, rng, moves=10):
        s = list(s)
        best = self.value(s)
        for _ in range(moves):
            prev = list(s)
            i = rng.randrange(self.n)
            s[i] ^= 1
            v = self.value(s)
            if v >= best:
                best = v
            else:
                s = prev
        return s


def es_ctx(problem):
    """按变体的编码建上下文。"""
    return (_ESBits if problem["variant"] in BIT_VARIANTS else _ES)(problem)

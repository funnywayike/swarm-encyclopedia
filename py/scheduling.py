# -*- coding: utf-8 -*-
"""排程建模线（批 2 撤下词条 nrp/ttp/sls 重设计）——独立模块，禁止改动 domains.py。

背景：原 entryseq 排列内核把"人×时"矩阵硬塞进排列/向量编码，导致 SA=random 恒同值
（解码与排列无关）。本模块为三问题各建"指派型"专业编码，域协议与 domains.py 完全一致：
    ctx 提供 random(rng) / obj(s) / swap(s,rng) / repair(s) / n；内核 yield {iter,best,cur,best_sol}。
    注册表 _SCHED_ALGOS（fn/name/category/desc/tune），预设 _SCHED_DEF，问题表 _SCHED_PROBLEMS。

内核复用策略（诚实说明）：
    - hc/sa/ts/random 四个 _SW 内核只依赖 ctx.swap/repair/obj/random，与编码无关，直接从
      domains 复用（import 实测 0.06s 无副作用）。
    - ga/de/gwo/cs 在 domains 里是「二进制交叉 / 取值钳到 [0,n-1]」假设，对整数指派编码失效
      （护士班次、考试时段、赛程队伍都是分类取值且 repair 语义不同），故本文件自写整数指派版，
      代码风格与 _sw_* 一致（整数均匀交叉 / 类别差分 / 三狼投票 / 莱维 swap 串），全部只走
      ctx.swap/repair/obj/random，编码无关。

四个问题的建模选择（软硬约束权重、邻域设计）均在各自 docstring 写清；不美化。
域名实（2026-09-29 正名）：引擎键 ttp=旅行锦标赛 TTP（Traveling Tournament Problem，
Easton & Nemhauser 2001）；考试时间表正名为 etp（Exam Timetabling，Kempen 规格）——
此前引擎键 ttp 实为考试排课，与 problems.json 的 ttp 词条（旅行锦标赛）名实冲突，本版纠正。

dispatch 接口（供主线挂接）：sched_make / sched_preset / sched_start / sched_step / sched_list / sched_bench。
主线接线说明见文件末尾 __MAIN_HOOK_NOTE__。
"""
import json
import random as _random

# 复用 domains 的编码无关内核（hc/sa/ts/random）；import 仅构建 dict/函数，无重活。
from domains import _sw_random, _sw_hc, _sw_sa, _sw_ts  # noqa: E402


# ============================================================
# 通用调度内核（整数指派版：ga/de/gwo/cs）——编码无关，只走 ctx 协议
# ============================================================

def _sch_pop(ctx, p, rng):
    """种群组装：n_pop 个 random 可行解。"""
    n_pop = p.get("n_pop", 30)
    pop = [ctx.random(rng) for _ in range(n_pop)]
    return pop, [ctx.obj(x) for x in pop]


def _sch_ga(ctx, p, rng):
    """整数均匀交叉 GA + 修复 + 半数个体叠一次 swap（memetic）。值取自父代合法值，无越界。"""
    pop, vals = _sch_pop(ctx, p, rng)
    n = ctx.n
    bi = min(range(len(pop)), key=lambda i: vals[i])
    best, bs = vals[bi], list(pop[bi])
    for it in range(1, p["max_iter"] + 1):
        new = [list(pop[bi])]
        while len(new) < p["n_pop"]:
            a, b = rng.sample(range(p["n_pop"]), 2)
            child = [pop[a][k] if rng.random() < 0.5 else pop[b][k] for k in range(n)]
            child = ctx.repair(child) if getattr(ctx, "search_repair", True) else child
            if rng.random() < 0.5:
                child = ctx.swap(child, rng)
            new.append(child)
        pop = new
        vals = [ctx.obj(s) for s in pop]
        bi = min(range(len(pop)), key=lambda i: vals[i])
        if vals[bi] < best:
            best, bs = vals[bi], list(pop[bi])
        yield {"iter": it, "best": best, "cur": min(vals), "best_sol": list(bs)}


def _sch_de(ctx, p, rng):
    """类别差分 DE：每个分量以概率 F 取 donor 个体的合法值，再 repair；不假设数值范围。"""
    pop, vals = _sch_pop(ctx, p, rng)
    F = p.get("F", 0.7)
    n = ctx.n
    for it in range(1, p["max_iter"] + 1):
        for i in range(len(pop)):
            idxs = [j for j in range(len(pop)) if j != i]
            r1, r2, r3 = rng.sample(idxs, 3)
            cand = list(pop[i])
            for k in range(n):
                if rng.random() < F:
                    cand[k] = pop[r3][k]
            cand = ctx.repair(cand) if getattr(ctx, "search_repair", True) else cand
            c = ctx.obj(cand)
            if c <= vals[i]:
                pop[i], vals[i] = cand, c
        bi = min(range(len(pop)), key=lambda i: vals[i])
        best, bs = vals[bi], list(pop[bi])
        yield {"iter": it, "best": best, "best_sol": list(bs), "cur": sum(vals) / len(vals)}


def _sch_gwo(ctx, p, rng):
    """整数指派灰狼 GWO：三狼投票，每个分量以 0.6 概率取 alpha/beta/delta 的合法值 + repair。"""
    pop, vals = _sch_pop(ctx, p, rng)
    n = ctx.n
    for it in range(1, p["max_iter"] + 1):
        order = sorted(range(len(pop)), key=lambda i: vals[i])
        alpha, beta, delta = pop[order[0]], pop[order[1]], pop[order[2]]
        for i in range(len(pop)):
            cand = list(pop[i])
            for k in range(n):
                lead = rng.choice([alpha, beta, delta])
                if rng.random() < 0.6:
                    cand[k] = lead[k]
            cand = ctx.repair(cand) if getattr(ctx, "search_repair", True) else cand
            c = ctx.obj(cand)
            if c <= vals[i]:
                pop[i], vals[i] = cand, c
        bi = min(range(len(pop)), key=lambda i: vals[i])
        best, bs = vals[bi], list(pop[bi])
        yield {"iter": it, "best": best, "best_sol": list(bs), "cur": sum(vals) / len(vals)}


def _sch_cs(ctx, p, rng):
    """整数指派布谷鸟 CS：莱维 swap 串（≥4 步保底）+ 局部贪心精修 + 弃巢（pa）。

    说明：纯莱维飞行在邻接/对阵这类"软项主导"景观上易与随机打平（缺乏局部开发），
    故每个巢在飞行后叠一段短贪心精修（只接受改进），使其真正优化而非仅采样。
    """
    pop, vals = _sch_pop(ctx, p, rng)
    pa = p.get("pa", 0.15)
    bi = min(range(len(pop)), key=lambda i: vals[i])
    best, bpos = vals[bi], list(pop[bi])
    for it in range(1, p["max_iter"] + 1):
        i = rng.randrange(len(pop))
        levy = int(rng.paretovariate(1.5))
        cand = list(pop[i])
        for _ in range(min(levy + 4, 10)):
            cand = ctx.swap(cand, rng)
        cand = ctx.repair(cand) if getattr(ctx, "search_repair", True) else cand
        # 局部贪心精修（best-improvement：每步在 8 个随机 swap 候选里挑最优，≤8 步）
        for _ in range(8):
            best_nb, best_v = None, ctx.obj(cand)
            for _ in range(8):
                nb = ctx.swap(cand, rng)
                nb = ctx.repair(nb) if getattr(ctx, "search_repair", True) else nb
                v = ctx.obj(nb)
                if v < best_v:
                    best_v, best_nb = v, nb
            if best_nb is None:
                break
            cand = best_nb
        c = ctx.obj(cand)
        if c <= vals[i]:
            pop[i], vals[i] = cand, c
        wi = max(range(len(pop)), key=lambda i2: vals[i2])
        if rng.random() < pa:
            pop[wi] = ctx.random(rng)
            vals[wi] = ctx.obj(pop[wi])
        bi = min(range(len(pop)), key=lambda i2: vals[i2])
        best, bpos = vals[bi], list(pop[bi])
        yield {"iter": it, "best": best, "best_sol": list(bpos), "cur": sum(vals) / len(vals)}


# ============================================================
# 域七之一：护士排班 NRP（Nurse Rostering Problem）
# ============================================================
def nrp_make(N=10, D=7, S=3, seed=7, hard_gap=1000, pref_w=8, consec_w=20):
    """护士×天×班次排班。
    编码：s[n*D + d] = 班次 ∈ {0..S-1} 工作班次 ∪ {S} 休息（OFF），长度 n = N*D。
    实例：
      - 需求 req[d][k]：每天每个工作班次至少需要的护士数；构造保证 Σ_k req[d][k] <= N（可行性前提）。
      - 偏好 pref[n][d]：约半数 (n,d) 有期望班次 ∈ {0..S-1}（无偏好记为 -1）；偏好违约即惩罚。
      - 技能分级：本建模不单列技能矩阵，以"偏好违约"近似个体差异（诚实简化，见下方目标说明）。
    目标（min，软硬分层加权）：
      硬：覆盖缺口——对每个 (d,k) 求 max(0, req[d][k]-实际覆盖)，×hard_gap（主导项，确保 random 明显更差）。
      软1：偏好违约——pref[n][d]>=0 且分配≠偏好 时 ×pref_w。
      软2：连班惩罚——护士连续工作 >5 天（无休息）每多 1 天 ×consec_w（鼓励穿插休息）。
    邻域 swap：随机选一个 (n,d) 改到随机班次（含 OFF）；single-position，SA/HC/TS 直接可用。
    random：纯随机指派（不过修复，留有覆盖缺口）——作为被碾压的基线。
    repair：贪心覆盖补位（按缺口最大优先）——遍历找缺口最大的 (d,k)，优先把当天 OFF 护士挪过去，
           否则从超编班次挪；因 Σreq<=N 必能补到零缺口。
    """
    if N < S:
        N = S  # 可行性前提：每天每班至少 1 人可排；页面自定义输入挡不住 N<S，入口规整化
    rng = _random.Random(seed)
    OFF = S
    nshifts = S + 1
    req = [[0] * nshifts for _ in range(D)]
    for d in range(D):
        total = rng.randint(min(7, N), N)  # 7..N（N<7 时收窄为 N..N），保证当天总需求 <= N
        base = [1] * S
        rem = total - S
        for _ in range(rem):
            base[rng.randrange(S)] += 1
        rng.shuffle(base)
        for k in range(S):
            req[d][k] = base[k]
    pref = [[-1] * D for _ in range(N)]
    for n in range(N):
        for d in range(D):
            if rng.random() < 0.5:
                pref[n][d] = rng.randrange(S)
    return {"N": N, "D": D, "S": S, "OFF": OFF, "nshifts": nshifts,
            "req": req, "pref": pref,
            "hard_gap": hard_gap, "pref_w": pref_w, "consec_w": consec_w}


class _NRP:
    def __init__(self, problem):
        self.N = problem["N"]; self.D = problem["D"]; self.S = problem["S"]
        self.OFF = problem["OFF"]; self.nshifts = problem["nshifts"]
        self.req = problem["req"]; self.pref = problem["pref"]
        self.hard_gap = problem["hard_gap"]; self.pref_w = problem["pref_w"]
        self.consec_w = problem["consec_w"]
        self.n = self.N * self.D

    def coverage_gap(self, s):
        """总硬覆盖缺口（可行性断言用）。"""
        N, D, S, OFF = self.N, self.D, self.S, self.OFF
        cnt = [[0] * self.nshifts for _ in range(D)]
        for n in range(N):
            for d in range(D):
                cnt[d][s[n * D + d]] += 1
        gap = 0
        for d in range(D):
            for k in range(S):
                gap += max(0, self.req[d][k] - cnt[d][k])
        return gap

    def obj(self, s):
        pen = self.hard_gap * self.coverage_gap(s)
        N, D, S, OFF = self.N, self.D, self.S, self.OFF
        for n in range(N):
            for d in range(D):
                p = self.pref[n][d]
                if p >= 0 and s[n * D + d] != p:
                    pen += self.pref_w
        for n in range(N):
            run = 0
            for d in range(D):
                if s[n * D + d] != OFF:
                    run += 1
                    if run > 5:
                        pen += self.consec_w
                else:
                    run = 0
        return pen

    def repair(self, s):
        s = list(s)
        N, D, S, OFF = self.N, self.D, self.S, self.OFF
        for _ in range(N * D):
            cnt = [[0] * self.nshifts for _ in range(D)]
            for n in range(N):
                for d in range(D):
                    cnt[d][s[n * D + d]] += 1
            best = None; bestgap = 0
            for d in range(D):
                for k in range(S):
                    g = self.req[d][k] - cnt[d][k]
                    if g > bestgap:
                        bestgap = g; best = (d, k)
            if bestgap <= 0:
                break
            d, k = best
            cand = None
            for n in range(N):
                if s[n * D + d] == OFF:
                    cand = n; break
            if cand is None:
                for n in range(N):
                    sk = s[n * D + d]
                    if sk != k and cnt[d][sk] > self.req[d][sk]:
                        cand = n; break
            if cand is None:
                break
            s[cand * D + d] = k
        return s

    def random(self, rng):
        return [rng.randrange(self.nshifts) for _ in range(self.n)]

    def swap(self, s, rng):
        s = list(s)
        i = rng.randrange(self.n)
        s[i] = rng.randrange(self.nshifts)
        return s


# ============================================================
# 域七之二：考试时间表 ETP（Exam Timetabling，Kempen 规格）
# （2026-09-29 正名：原引擎键 ttp 实为本问题，现键位让给旅行锦标赛，见域八）
# ============================================================
def etp_make(E=30, seed=7, hard_conf=1000, adj_w=12, cap_w=50):
    """考试×学生选课表×时段/教室容量。
    构造保证存在零硬冲突的 T-着色：先随机生成冲突图 G(E,p)，取 T = 最大度+1 用贪心染出 proper
    着色（T>=χ(G)），再据每条边造一个"选这两门"的学生——故零冲突解必然存在，repair 可达成。
    编码：s[e] = 时段 ∈ {0..T-1}，长度 n = E。
    目标（min，软硬分层）：
      硬：同时段学生冲突——每个学生(=一条边两门)若被分到同段，×hard_conf（主导，random 明显更差）。
      软：相邻时段同学生（Kempen 规格）——两门时段差为 1 ×adj_w。
      软：教室容量——某段考试数超过 rooms ×cap_w（rooms 设宽松，通常不饱和）。
    邻域 swap：随机选一门考试改到随机时段。
    random：纯随机时段（不过修复，留有冲突）——被碾压基线。
    repair：冲突驱动重排（图着色式 largest-degree-first 贪心着色为主 + min-conflicts 兜底）。
    """
    rng = _random.Random(seed)
    edges = []
    adj = [set() for _ in range(E)]
    p = 0.18
    for a in range(E):
        for b in range(a + 1, E):
            if rng.random() < p:
                edges.append((a, b)); adj[a].add(b); adj[b].add(a)
    T = max((len(adj[i]) for i in range(E)), default=0) + 1
    students = [list(e) for e in edges]            # 每学生恰选两门（边）
    rooms = max(3, T // 2 + 2)
    return {"E": E, "T": T, "edges": edges,
            "adj": [list(a) for a in adj], "students": students, "rooms": rooms,
            "hard_conf": hard_conf, "adj_w": adj_w, "cap_w": cap_w}


class _ETP:
    def __init__(self, problem):
        self.E = problem["E"]; self.T = problem["T"]
        self.adj = problem["adj"]; self.students = problem["students"]
        self.rooms = problem["rooms"]
        self.hard_conf = problem["hard_conf"]; self.adj_w = problem["adj_w"]
        self.cap_w = problem["cap_w"]
        self.search_repair = False   # 搜索中不调 repair：proper-coloring 会抹掉邻接优化，硬冲突交由 obj 硬罚驱动
        self.n = self.E

    def n_conflicts(self, s):
        """硬冲突数（可行性断言用）。"""
        c = 0
        for st in self.students:
            if len(st) == 2 and s[st[0]] == s[st[1]]:
                c += 1
        return c

    def _conf_of(self, e, s):
        c = 0
        for st in self.students:
            if len(st) == 2 and e in st:
                o = st[0] if st[1] == e else st[1]
                if s[o] == s[e]:
                    c += 1
        return c

    def obj(self, s):
        conf = self.n_conflicts(s)
        pen = self.hard_conf * conf
        for st in self.students:
            slots = sorted(s[e] for e in st)
            for i in range(len(slots) - 1):
                if slots[i + 1] - slots[i] == 1:
                    pen += self.adj_w
        cnt = [0] * self.T
        for e in range(self.E):
            cnt[s[e]] += 1
        pen += self.cap_w * sum(max(0, c - self.rooms) for c in cnt)
        return pen

    def repair(self, s):
        """冲突驱动重排：最大度优先贪心 proper 着色（零冲突保证，因 T>=χ）+ min-conflicts 兜底。"""
        s = list(s)
        E, T = self.E, self.T
        # 1) largest-degree-first 贪心着色（确定性，从当前 s 的最大度考试开始重染）
        order = sorted(range(E), key=lambda i: -len(self.adj[i]))
        assigned = {}
        for v in order:
            used = {s[u] for u in self.adj[v] if u in assigned}
            for c in range(T):
                if c not in used:
                    s[v] = c; assigned[v] = c; break
            else:
                s[v] = T - 1
        # 2) 兜底：若仍有冲突（理论不发生），min-conflicts 净化
        for _ in range(E * T * 4):
            if self.n_conflicts(s) == 0:
                break
            conf = [self._conf_of(e, s) for e in range(E)]
            worst = max(range(E), key=lambda e: conf[e])
            bestc = None; bestslot = s[worst]
            for c in range(T):
                s[worst] = c
                cc = self._conf_of(worst, s)
                if bestc is None or cc < bestc:
                    bestc = cc; bestslot = c
            s[worst] = bestslot
        return s

    def random(self, rng):
        return [rng.randrange(self.T) for _ in range(self.n)]

    def swap(self, s, rng):
        s = list(s)
        i = rng.randrange(self.n)
        j = rng.randrange(self.T)
        s[i] = j
        return s


# ============================================================
# 域七之三：赛程生成 SLS（Sports League Scheduling，双循环）
# ============================================================
def sls_make(m=8, seed=7, ha_w=5, consec_w=15, pair_w=50, focus_w=30):
    """偶数队双循环赛程。
    实例：m 队（偶数），R = 2*(m-1) 轮，每轮 g = m/2 场（主,客）；marquee=焦点队集合（用于焦点战分布）。
    编码：s 扁平向量，每轮 2*g 个队号（主/客交替），长度 n = R*2*g = R*m。
          round r 的第 i 场 = (s[r*per+2i], s[r*per+2i+1])，前者主、后者客。
    可行性定义（"轮次完整"）：每个轮次 2*g 个队号恰好是 {0..m-1} 各一次——即每轮为完美匹配，
          每队每轮恰赛一场。该性质由编码结构（repair 负责）保证；交叉轮的对阵完整性(每对恰遇2次)
          作为软目标 pair_w 引导（严格 DRR 完整性见 docstring 诚实说明）。
    目标（min，全软，主客场/连主连客/焦点战均为软约束——与任务描述一致）：
      - 主客场平衡：每队 |主场次-客场次| ×ha_w（理想各 R/2）。
      - 连主/连客：每队连续同场地 >=3 场，每多 1 场 ×consec_w。
      - 对阵完整：每无序对出现次数与 2 的偏差 ×pair_w（双循环应恰 2 次；主导可分化项）。
      - 焦点战分布：同轮出现 >=2 场"双方皆焦点队"的对阵 ×focus_w（避免焦点战扎堆）。
    邻域 swap：随机选一轮，轮内交换两个队号（保持该轮仍为排列 → 始终可行）。
    random：随机可行轮（每轮随机排列 → 轮次完整，但对阵/连主分布差）——被碾压基线。
    repair：轮内交换恢复可行——把每轮重复队号换为缺失队号，保证 {0..m-1} 各一次（轮次完整）。
    """
    if m % 2 != 0:
        m += 1  # 双循环需偶数队（每轮 g=m/2 场恰覆盖 m 队）；页面自定义输入挡不住奇数，入口规整化
    rng = _random.Random(seed)
    R = 2 * (m - 1)
    g = m // 2
    marquee = [0, 1, 2] if m >= 3 else [0, 1]
    return {"m": m, "R": R, "g": g, "per": 2 * g, "marquee": marquee,
            "ha_w": ha_w, "consec_w": consec_w, "pair_w": pair_w, "focus_w": focus_w}


class _SLS:
    def __init__(self, problem):
        self.m = problem["m"]; self.R = problem["R"]; self.g = problem["g"]
        self.per = problem["per"]; self.marquee = set(problem["marquee"])
        self.ha_w = problem["ha_w"]; self.consec_w = problem["consec_w"]
        self.pair_w = problem["pair_w"]; self.focus_w = problem["focus_w"]
        self.n = self.R * self.per

    def rounds_complete(self, s):
        """每轮是否恰含 {0..m-1} 各一次（可行性断言用）；返回不满足的轮数。"""
        bad = 0
        for r in range(self.R):
            base = r * self.per
            if sorted(s[base:base + self.per]) != list(range(self.m)):
                bad += 1
        return bad

    def obj(self, s):
        m, g, R, per = self.m, self.g, self.R, self.per
        home = [0] * m; away = [0] * m
        venue = [[-1] * R for _ in range(m)]
        paircnt = {}
        for r in range(R):
            base = r * per
            for i in range(g):
                h = s[base + 2 * i]; a = s[base + 2 * i + 1]
                home[h] += 1; away[a] += 1
                venue[h][r] = 0; venue[a][r] = 1
                key = (h, a) if h < a else (a, h)
                paircnt[key] = paircnt.get(key, 0) + 1
        pen = 0
        for t in range(m):
            pen += self.ha_w * abs(home[t] - away[t])
        for t in range(m):
            run = 1
            for r in range(1, R):
                if venue[t][r] == venue[t][r - 1] and venue[t][r] != -1:
                    run += 1
                    if run > 2:
                        pen += self.consec_w
                else:
                    run = 1
        for a in range(m):
            for b in range(a + 1, m):
                c = paircnt.get((a, b), 0)
                pen += self.pair_w * abs(c - 2)
        for r in range(R):
            base = r * per
            inround = set()
            for i in range(g):
                h = s[base + 2 * i]; a = s[base + 2 * i + 1]
                if h in self.marquee and a in self.marquee:
                    inround.add((h, a) if h < a else (a, h))
            if len(inround) >= 2:
                pen += self.focus_w * (len(inround) - 1)
        return pen

    def repair(self, s):
        """轮内交换恢复可行：每轮重复队号换为缺失队号，使 {0..m-1} 各一次。"""
        import collections
        s = list(s)
        m, g, per = self.m, self.g, self.per
        for r in range(self.R):
            base = r * per
            L = s[base:base + per]
            cnt = collections.Counter(L)
            missing = [t for t in range(m) if cnt[t] == 0]
            mi = 0
            for pos in range(per):
                t = L[pos]
                if cnt[t] > 1:
                    cnt[t] -= 1
                    L[pos] = missing[mi]; mi += 1
            s[base:base + per] = L
        return s

    def random(self, rng):
        out = []
        for _ in range(self.R):
            row = list(range(self.m))
            rng.shuffle(row)
            out.extend(row)
        return out

    def swap(self, s, rng):
        s = list(s)
        r = rng.randrange(self.R)
        base = r * self.per
        i = rng.randrange(self.per)
        j = rng.randrange(self.per)
        s[base + i], s[base + j] = s[base + j], s[base + i]
        return s


# ============================================================
# 域八：旅行锦标赛 TTP（Traveling Tournament Problem，Easton & Nemhauser 2001）
# ============================================================
def tour_make(m=8, seed=7, pair_w=500, streak_w=6, repeat_w=12):
    """m 队双循环巡回赛：赛程×城市地理耦合，最小化总旅行距离。
    实例：m 队（偶数，奇数入口规整化 +1），每队一个主城（100×100 网格确定性撒点，seed 复现）；
          R = 2(m-1) 轮、每轮 g = m/2 场；dist 为取整欧氏距离阵。
    编码：与 sls 同构扁平向量——round r 第 i 场 = (s[r*per+2i], s[r*per+2i+1])，前者主队；
          长度 n = R*per = R*m。每轮为 {0..m-1} 排列（完美匹配），由 repair 保证。
    目标（min，分层加权）：
      主导：对阵完整——每无序对出现次数与 2 的偏差 ×pair_w（严格 DRR 应恰 2 次）。
            诚实说明：与 sls 同款软罚松弛；文献 TTP 把 DRR 完整性定为硬约束，本建模以
            pair_w=500 主导权重近似（引擎面向教学演示，松弛后 8 内核可复用、邻域保持可行）。
      旅行：每队从主城出发按轮次访问客场比赛城市、赛毕回主城的行程距离和（原始距离，无权重）。
      连场：连续主/客 >3 场每多 1 场 ×streak_w（TTP 经典 at-most-3 约束软罚）。
      重复对阵：相邻两轮出现同对（任一方向）×repeat_w（经典 no-repeat 软罚）。
    邻域 swap：随机选一轮轮内交换两个队号（保持轮次完整，与 sls 同款）。
    random：随机可行轮——轮次完整但对阵/地理全乱，被 pair_w 主导碾压。
    repair：轮内交换恢复排列（与 sls 同款）。
    """
    if m % 2 != 0:
        m += 1  # 双循环需偶数队；页面自定义输入挡不住奇数，入口规整化
    if m < 4:
        m = 4   # 下限：至少 4 队才有锦标赛结构
    rng = _random.Random(seed)
    R = 2 * (m - 1)
    g = m // 2
    pts = [[rng.randint(0, 100), rng.randint(0, 100)] for _ in range(m)]
    dist = [[0] * m for _ in range(m)]
    for a in range(m):
        for b in range(a + 1, m):
            d = int(round(((pts[a][0] - pts[b][0]) ** 2 + (pts[a][1] - pts[b][1]) ** 2) ** 0.5))
            dist[a][b] = d
            dist[b][a] = d
    return {"m": m, "R": R, "g": g, "per": 2 * g, "pts": pts, "dist": dist,
            "pair_w": pair_w, "streak_w": streak_w, "repeat_w": repeat_w}


class _TOUR:
    def __init__(self, problem):
        self.m = problem["m"]; self.R = problem["R"]; self.g = problem["g"]
        self.per = problem["per"]
        self.dist = problem["dist"]; self.pts = problem.get("pts", [])
        self.pair_w = problem["pair_w"]; self.streak_w = problem["streak_w"]
        self.repeat_w = problem["repeat_w"]
        self.n = self.R * self.per

    def rounds_complete(self, s):
        """每轮是否恰含 {0..m-1} 各一次（可行性断言用）；返回不满足的轮数。"""
        bad = 0
        for r in range(self.R):
            base = r * self.per
            if sorted(s[base:base + self.per]) != list(range(self.m)):
                bad += 1
        return bad

    def _games(self, s):
        """展开为 [(r, h, a), ...]（h 主 a 客）。"""
        out = []
        for r in range(self.R):
            base = r * self.per
            for i in range(self.g):
                out.append((r, s[base + 2 * i], s[base + 2 * i + 1]))
        return out

    def obj(self, s):
        m, R, per = self.m, self.R, self.per
        # 主导：对阵完整
        paircnt = {}
        venue = [[-1] * R for _ in range(m)]   # 0=主场 1=客场
        oppo = [[-1] * R for _ in range(m)]
        for r in range(R):
            base = r * per
            for i in range(self.g):
                h = s[base + 2 * i]; a = s[base + 2 * i + 1]
                key = (h, a) if h < a else (a, h)
                paircnt[key] = paircnt.get(key, 0) + 1
                venue[h][r] = 0; venue[a][r] = 1
                oppo[h][r] = a; oppo[a][r] = h
        pen = 0
        for a in range(m):
            for b in range(a + 1, m):
                pen += self.pair_w * abs(paircnt.get((a, b), 0) - 2)
        # 旅行：每队按轮次走访问客城市（每轮必有比赛），赛毕回主城
        for t in range(m):
            cur = t
            for r in range(R):
                o = oppo[t][r]
                nxt = cur if venue[t][r] == 0 else o   # 主场不出门，客场去对方城市
                pen += self.dist[cur][nxt]
                cur = nxt
            pen += self.dist[cur][t]
        # 连主/连客 >3
        for t in range(m):
            run = 1
            for r in range(1, R):
                if venue[t][r] == venue[t][r - 1]:
                    run += 1
                    if run > 3:
                        pen += self.streak_w
                else:
                    run = 1
        # 重复对阵：相邻轮同对（任一方向）
        for r in range(R - 1):
            base = r * per
            seen = set()
            for i in range(self.g):
                a = s[base + 2 * i]; b = s[base + 2 * i + 1]
                seen.add((a, b) if a < b else (b, a))
            base2 = base + per
            for i in range(self.g):
                a = s[base2 + 2 * i]; b = s[base2 + 2 * i + 1]
                if (a, b) in seen or (b, a) in seen:
                    pen += self.repeat_w
        return pen

    def repair(self, s):
        """轮内交换恢复可行：每轮重复队号换为缺失队号（与 sls 同款）。"""
        import collections
        s = list(s)
        m, g, per = self.m, self.g, self.per
        for r in range(self.R):
            base = r * per
            L = s[base:base + per]
            cnt = collections.Counter(L)
            missing = [t for t in range(m) if cnt[t] == 0]
            mi = 0
            for pos in range(per):
                t = L[pos]
                if cnt[t] > 1:
                    cnt[t] -= 1
                    L[pos] = missing[mi]; mi += 1
            s[base:base + per] = L
        return s

    def random(self, rng):
        out = []
        for _ in range(self.R):
            row = list(range(self.m))
            rng.shuffle(row)
            out.extend(row)
        return out

    def swap(self, s, rng):
        s = list(s)
        r = rng.randrange(self.R)
        base = r * self.per
        i = rng.randrange(self.per)
        j = rng.randrange(self.per)
        s[base + i], s[base + j] = s[base + j], s[base + i]
        return s


# ============================================================
# 注册表 / 预设 / 问题表（与 domains.py 惯例一致）
# ============================================================
_SCHED_ALGOS = {
    "random": {"fn": _sw_random, "name": "随机搜索", "category": "基线",
               "desc": "盲采样基线：一切算法都要显著降低目标", "tune": []},
    "hc": {"fn": _sw_hc, "name": "爬山法 HC", "category": "局部搜索",
           "desc": "交换邻域单点贪心 + 停滞重启", "tune": ["tries"]},
    "sa": {"fn": _sw_sa, "name": "模拟退火 SA", "category": "物理启发",
           "desc": "交换移动 + Metropolis + 卡死重启", "tune": ["t0", "decay"]},
    "ts": {"fn": _sw_ts, "name": "禁忌搜索 TS", "category": "局部搜索",
           "desc": "交换禁忌表 + 采样邻域 + 特赦", "tune": ["tenure"]},
    "ga": {"fn": _sch_ga, "name": "遗传 GA", "category": "进化计算",
           "desc": "整数均匀交叉 + 修复 + 叠交换(memetic)", "tune": ["pm"]},
    "de": {"fn": _sch_de, "name": "差分 DE", "category": "进化计算",
           "desc": "类别差分：随 F 取 donor 合法值 + 修复", "tune": ["F"]},
    "gwo": {"fn": _sch_gwo, "name": "灰狼 GWO", "category": "群体智能",
            "desc": "三狼指派投票（整数自适应）", "tune": []},
    "cs": {"fn": _sch_cs, "name": "布谷鸟 CS", "category": "群体智能",
           "desc": "莱维 swap 串 + 弃巢", "tune": ["pa"]},
}

# 共享参数口径（沿用 _BIN_DEF 风格；t0/decay 对覆盖/冲突主导项已标定可降温）
_SCHED_DEF = {"n_pop": 30, "pm": 0.04, "t0": 30.0, "decay": 0.98, "tries": 20,
              "tenure": 8, "ts_sample": 40, "restart_at": 25, "max_iter": 200,
              "seed": 7, "F": 0.7, "pa": 0.25, "limit": 12}

_SCHED_PROBLEMS = {
    "nrp": {"make": nrp_make, "name": "护士排班 NRP", "category": "排程",
            "desc": "护士×天×班次指派；覆盖缺口(硬)+偏好违约+连班(软)",
            "ctx": _NRP, "def": dict(_SCHED_DEF)},
    "etp": {"make": etp_make, "name": "考试时间表 ETP", "category": "排程",
            "desc": "考试→时段指派；同时段冲突(硬,Kempen)+相邻段(软)",
            "ctx": _ETP, "def": dict(_SCHED_DEF)},
    "ttp": {"make": tour_make, "name": "旅行锦标赛 TTP", "category": "排程",
            "desc": "双循环赛程×城市地理；总旅行距离+对阵完整(主导)+连场/重复(软)",
            "ctx": _TOUR, "def": dict(_SCHED_DEF)},
    "sls": {"make": sls_make, "name": "赛程生成 SLS", "category": "排程",
            "desc": "轮次排列指派；主客场平衡+连主连客+焦点战分布(软)",
            "ctx": _SLS, "def": dict(_SCHED_DEF)},
}


# ============================================================
# 调度线 dispatch（供主线在 domains.py 内挂接的镜像接口）
# ============================================================
_SCHED_RUN = {"gen": None, "ctx": None, "problem": None}


def sched_make(problem, **kw):
    return _SCHED_PROBLEMS[problem]["make"](**kw)


def sched_preset(problem, seed=7, opts=None):
    if isinstance(opts, str):
        opts = json.loads(opts) if opts else {}
    opts = opts or {}
    return json.dumps(sched_make(problem, seed=seed, **opts))


def sched_start(problem, problem_json, algo, params_json):
    d = _SCHED_PROBLEMS[problem]
    if algo not in _SCHED_ALGOS:
        raise ValueError(f"unknown algo {algo} for {problem}")
    prob = json.loads(problem_json)
    p = dict(d["def"])
    p.update(json.loads(params_json) if params_json else {})
    rng = _random.Random(p["seed"])
    ctx = d["ctx"](prob)
    info = {"problem": problem, "sense": "min",
            "n": ctx.n,
            "inst": {k: prob[k] for k in
                     ("N", "D", "S", "E", "T", "m", "R", "g") if k in prob}}
    gen = _SCHED_ALGOS[algo]["fn"](ctx, p, rng)
    _SCHED_RUN["gen"] = gen; _SCHED_RUN["ctx"] = ctx; _SCHED_RUN["problem"] = problem
    return json.dumps(info)


def sched_step():
    s = next(_SCHED_RUN["gen"], None)
    if s is None:
        return None
    return json.dumps(s)


def sched_list(problem):
    out = []
    for k, a in _SCHED_ALGOS.items():
        out.append({"key": k, "name": a["name"], "category": a["category"],
                    "desc": a["desc"], "tune": a["tune"]})
    return json.dumps({"algos": out, "defaults": dict(_SCHED_PROBLEMS[problem]["def"])})


def sched_bench(problem, iters=200, seed=7, algos=None):
    """命令行/测试快速基准：返回 {algo: 终值}。"""
    prob = sched_make(problem, seed=seed)
    out = {}
    for key in (algos or list(_SCHED_ALGOS)):
        sched_start(problem, json.dumps(prob), key,
                    json.dumps({"max_iter": iters, "seed": seed}))
        last = None
        while True:
            s = sched_step()
            if s is None:
                break
            last = json.loads(s)
        out[key] = last["best"]
    return out


__MAIN_HOOK_NOTE__ = """
主线接线说明（供 domains.py 维护者）：
  1) 顶部 import：在 domains.py 加  `import scheduling`（建议放到批 7 续写段之后）；
  2) _DOMAINS 挂接：新增四项
       "nrp":  {"algos": scheduling._SCHED_ALGOS, "def": scheduling._SCHED_DEF, "make": scheduling.nrp_make},
       "etp":  {"algos": scheduling._SCHED_ALGOS, "def": scheduling._SCHED_DEF, "make": scheduling.etp_make},
       "ttp":  {"algos": scheduling._SCHED_ALGOS, "def": scheduling._SCHED_DEF, "make": scheduling.tour_make},
       "sls":  {"algos": scheduling._SCHED_ALGOS, "def": scheduling._SCHED_DEF, "make": scheduling.sls_make},
     （四门共用同一 _SCHED_ALGOS 内核集；若以后要 per-variant 算法集，改 _SCHED_PROBLEMS 即可。）
  3) domain_start 分发分支：在 domain_start 的 if-elif 链末尾加
       elif domain in ("nrp", "etp", "ttp", "sls"):
           ctx = _SCHED_PROBLEMS[domain]["ctx"](problem)
           info = {"problem": domain, "sense": "min", "n": ctx.n,
                   "inst": {k: problem[k] for k in ("N","D","S","E","T","m","R","g") if k in problem}}
           gen = _SCHED_ALGOS[algo]["fn"](ctx, p, rng)
     或更直接：令 domain_start 对这三域 `from scheduling import sched_start as _sched_start; return _sched_start(...)`。
     注意 domain_start 已统一用 d["algos"][algo]["fn"](ctx,p,rng)，本模块 ctx 协议一致，直接复用即可，
     无需改 step（domain_step 仍读 _SCHED_RUN["gen"]——但本模块用自有 _SCHED_RUN；若合并需统一 _SCHED_RUN 命名空间，
     建议主线调用 scheduling.sched_start / scheduling.sched_step 而非复用 domain_*）。
  4) domain_list / domain_preset：加对应分支转发到 scheduling.sched_list / scheduling.sched_preset；
     domain_bench 同理可转发。
  5) 页面侧 pages_domains.py / build_pages.py / data/** 本次未触碰（任务禁令），需主线另接词条↔域映射。
     （2026-09-29 主线已完成接线：domains.py 六分发分支 + wire 块；同日正名后词条挂载=
       nrp→nrp / etp→etp / ttp(旅行锦标赛)→ttp / sls→sls，problems.json 的 ttp 词条不再空挂。）
"""


# B 序循环导入回挂（2026-09-29 集成期修复）：
#   A 序（先 import domains）：domains wire 块 import scheduling → 本模块加载，此处 sys.modules
#     已有半加载 domains（_wire_sched_domains 已定义于 wire 块前）→ 回挂成功；随后 domains
#     wire 块尾部的 _wire_sched_domains(_schedmod) 再挂一次（幂等，无害）。
#   B 序（先 import scheduling）：本模块第 26 行 from domains import → domains 执行到 wire 块
#     时本模块仍半加载，domains 侧 hasattr 防御 fail-soft 跳过；本模块加载完成后在此回挂。
#   浏览器拼接环境：本模块源码与 domains 同名字空间 exec，sys.modules 无 "domains" → 跳过，
#     由 gen_domains_src 注入的 _schedmod 显式装配负责挂接。
import sys as _sys

_dm = _sys.modules.get("domains")
if _dm is not None and hasattr(_dm, "_wire_sched_domains"):
    _dm._wire_sched_domains(_sys.modules[__name__])


# 浏览器（Pyodide）里源码以 __main__ 身份拼接执行，必须用平台判断挡住，否则每次页面加载都会跑一遍自测
if __name__ == "__main__" and __import__("sys").platform != "emscripten":
    for pr in ("nrp", "etp", "ttp", "sls"):
        print(pr, sched_bench(pr))

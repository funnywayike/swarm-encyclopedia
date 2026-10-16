# ============================================================
# 域十一：背包家族变体 kpvar（10 变体单域多预设，H 期）
# 编码按变体分派：bkp/ukp/cmp=复制展开 0-1 位；mkpm=类 GAP 指派编码
# （x[i]∈{0..m}，0=不取）；mckp=k*r one-hot 位；其余=0-1 位。
# 内核全复用 _BIN/_GAP 系 + 变体 repair/目标。
# ============================================================

def kpv_make(variant="ssp", n=40, seed=7, k=None, r=None):
    rng = random.Random(seed)
    if variant == "cmp":  # 找零：币值 expanded 成枚，目标金额 T
        denoms = [1, 2, 5, 10, 20, 50]
        T = rng.randint(120, 200)
        items = [[d, 1] for d in denoms for _ in range(min(T // d, 8))]
        return {"variant": variant, "denoms": denoms, "T": T,
                "items": items, "cap": T}
    # 价值型变体复用背包枢纽 ks_make 的标定分布（w 2-60 / v 10-100 / cap 45%），
    # 45 个 _KS 内核在该分布上已通过「全算法赢随机」标定
    base = ks_make(n=n, seed=seed)
    w = [x[0] for x in base["items"]]
    v = [x[1] for x in base["items"]]
    cap = base["cap"]
    if variant == "mkpm":  # 多背包：m 个包，指派编码（0=不取）；松容量（合计 74%）保证指派算法赢随机
        return {"variant": variant, "n": n, "w": w, "v": v, "m": 3,
                "caps": [int(sum(w) * f) for f in (0.30, 0.22, 0.22)]}
    if variant == "mckp":  # 多选择：k 类 × r 件，每类至多一件
        # 修1（2026-09-27 用户反馈）：k/r 支持预设与自定义直接指定，默认 n/4 类 × 4 件
        # （n=48 → 12 类 × 4 件，与历史默认一致）；自定义字段与预设标签同格式
        k = int(k) if k else max(2, n // 4)
        r = int(r) if r else 4
        w2 = [[rng.randint(8, 40) for _ in range(r)] for _ in range(k)]
        v2 = [[rng.randint(8, 55) for _ in range(r)] for _ in range(k)]
        return {"variant": variant, "k": k, "r": r, "w2": w2, "v2": v2,
                "cap": int(sum(max(row) for row in w2) * 0.5)}
    if variant == "dkp":  # 折扣背包 DCKP（Guldan 2007；Rong 等 2012）：每组 3 个候选 = 物品 A、物品 B、捆绑 A+B（重量打 75 折）；每组至多选一个
        k = max(2, n // 2)
        w2, v2 = [], []
        for g in range(k):
            wa, wb, va, vb = w[2 * g], w[2 * g + 1], v[2 * g], v[2 * g + 1]
            w2.append([wa, wb, int(round(0.75 * (wa + wb)))])
            v2.append([va, vb, va + vb])
        return {"variant": variant, "k": k, "r": 3, "w2": w2, "v2": v2, "cap": int(sum(row[2] for row in w2) * 0.5)}
    if variant == "bkp":  # 有界：每件上限 b[i]，复制展开
        b = [rng.randint(2, 4) for _ in range(n)]
        items = [[w[i], v[i]] for i in range(n) for _ in range(b[i])]
        return {"variant": variant, "b": b, "items": items, "cap": cap}
    if variant == "ukp":  # 无界：每件最多 3 份（容量截断；份数过大会出现等值高原，单链算法困死）
        items = [[w[i], v[i]] for i in range(n) for _ in range(min(3, cap // w[i]))]
        return {"variant": variant, "items": items, "cap": cap}
    prob = {"variant": variant, "n": n, "w": w, "v": v, "cap": cap}
    if variant == "mdkp":  # 多维背包：3 个资源维度，每个物品在每个维度各有独立的重量；每个维度的容量 = 该维度总重量的 45%
        W = [list(w)] + [[rng.randint(2, 60) for _ in range(n)] for _ in range(2)]
        prob["W"] = W
        prob["caps"] = [int(sum(row) * 0.45) for row in W]
    elif variant == "qkp":  # 二次利润：Q 对称非负
        Q = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                Q[i][j] = Q[j][i] = rng.randint(0, 8)
        prob["Q"] = Q
    elif variant == "ssp":
        prob["target"] = cap
    # fractional：与普通 0-1 同实例（LP 上界由前端现算）
    return prob


class _KPV:
    """背包变体位编码 ctx（fractional/bkp/ukp/cmp/mdkp/dkp/qkp/ssp）。
    cmp=min 枚数+BIG*|Σ-T|；ssp=min |Σw-T|（配精确 DP 锚点）；
    价值型=min -value + BIG*超载罚。repair 恒保持可行性。"""
    BIG = 10000

    def __init__(self, prob):
        self.prob = prob
        self.vt = prob["variant"]
        if "items" in prob:
            self.items = [tuple(x) for x in prob["items"]]
            self.w = [x[0] for x in self.items]
            self.v = [x[1] for x in self.items]
            self.n = len(self.items)
        else:
            self.w, self.v = prob["w"], prob["v"]
            self.n = prob["n"]
        self.cap = prob["cap"]

    # ---- _BIN 内核接口 ----
    def random(self, rng):
        s = [rng.randint(0, 1) for _ in range(self.n)]
        # 有容量约束的变体：随机起点先修复（否则 GA 初代全是 BIG 罚个体，梯度消失）
        return s if self.vt in ("cmp", "ssp") else self.repair(s)

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(p["n_pop"])]
        return pop, [self.obj(s) for s in pop]

    # ---- 变体语义 ----
    def eff_w(self, s):
        return list(self.w)

    def mdkp_loads(self, s):
        caps = self.prob["caps"]
        W = self.prob["W"]
        return [sum(W[d][i] for i in range(self.n) if s[i]) for d in range(len(caps))], caps

    def value(self, s):
        val = sum(self.v[i] for i in range(self.n) if s[i])
        if self.vt == "qkp":
            Q = self.prob["Q"]
            val += sum(Q[i][j] for i in range(self.n) if s[i]
                       for j in range(i + 1, self.n) if s[j])
        return val

    def obj(self, s):
        if self.vt == "cmp":
            total = sum(self.w[i] for i in range(self.n) if s[i])
            return sum(s) + self.BIG * abs(total - self.prob["T"])
        if self.vt == "ssp":
            return abs(sum(self.w[i] for i in range(self.n) if s[i]) - self.prob["target"])
        if self.vt == "mdkp":
            load, caps = self.mdkp_loads(s)
            over = sum(max(0, load[d] - caps[d]) for d in range(len(caps)))
        else:
            ew = self.eff_w(s)
            over = sum(ew[i] for i in range(self.n) if s[i]) - self.cap
        return -self.value(s) + self.BIG * max(0, over)

    def repair(self, s):
        s = list(s)
        if self.vt in ("cmp", "ssp"):
            return s  # 无容量约束（偏离目标由目标函数自身罚）
        if self.vt == "mdkp":
            load, caps = self.mdkp_loads(s)
            W = self.prob["W"]
            while any(load[d] > caps[d] for d in range(len(caps))):
                on = [i for i in range(self.n) if s[i]]
                # 去「价值 / 维度压力加权重量」最小项（= 压力加权密度最低）
                drop = min(on, key=lambda i: self.v[i] / max(1, sum(
                    max(0, load[d] - caps[d]) * W[d][i] for d in range(len(caps)))))
                s[drop] = 0
                load, caps = self.mdkp_loads(s)
            return s
        while True:
            ew = self.eff_w(s)
            if sum(ew[i] for i in range(self.n) if s[i]) <= self.cap:
                return s
            on = [i for i in range(self.n) if s[i]]
            drop = min(on, key=lambda i: self.v[i] / max(1, ew[i]))  # 去价值密度最低项
            s[drop] = 0


class _MCKP:
    """多选择背包 one-hot 位编码（k 类 × r 件拍平，每类至多一件）。"""
    BIG = 10000

    def __init__(self, prob):
        self.prob = prob
        self.k, self.r = prob["k"], prob["r"]
        self.n = self.k * self.r
        self.cap = prob["cap"]
        self.w = [prob["w2"][c][j] for c in range(self.k) for j in range(self.r)]
        self.v = [prob["v2"][c][j] for c in range(self.k) for j in range(self.r)]

    def random(self, rng):
        return [rng.randint(0, 1) for _ in range(self.n)]

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(p["n_pop"])]
        return pop, [self.obj(s) for s in pop]

    def obj(self, s):
        if any(sum(s[c * self.r:(c + 1) * self.r]) > 1 for c in range(self.k)):
            return self.BIG  # one-hot 违约重罚（repair 后实际不可达）
        val = sum(self.v[i] for i in range(self.n) if s[i])
        over = sum(self.w[i] for i in range(self.n) if s[i]) - self.cap
        return -val + self.BIG * max(0, over)

    def repair(self, s):
        s = list(s)
        for c in range(self.k):  # 每类只留密度最高的一件
            on = [i for i in range(c * self.r, (c + 1) * self.r) if s[i]]
            if len(on) > 1:
                best = max(on, key=lambda i: self.v[i] / max(1, self.w[i]))
                for i in on:
                    s[i] = 1 if i == best else 0
        while sum(self.w[i] for i in range(self.n) if s[i]) > self.cap:
            on = [i for i in range(self.n) if s[i]]
            drop = min(on, key=lambda i: self.v[i] / max(1, self.w[i]))
            s[drop] = 0
        return s


class _MKPM:
    """多背包指派编码：x[i] ∈ {0..m}，0=不取，j=放包 j。接口对齐 _gap_* 内核
    （n_j/n_a/random/repair/obj/init_pop），big-val + BIG*超载罚。"""
    BIG = 10000

    def __init__(self, prob):
        self.prob = prob
        self.n_j = prob["n"]
        self.n_a = prob["m"]
        self.w, self.v = prob["w"], prob["v"]
        self.caps = prob["caps"]
        self.cap = sum(self.caps)  # 兼容面
        self.n = self.n_j

    def loads(self, x):
        load = [0] * self.n_a
        for i in range(self.n_j):
            if x[i]:
                load[x[i] - 1] += self.w[i]
        return load

    def overflow(self, x):
        load = self.loads(x)
        return sum(max(0, load[a] - self.caps[a]) for a in range(self.n_a))

    def obj(self, x):
        val = sum(self.v[i] for i in range(self.n_j) if x[i])
        return -val + self.BIG * self.overflow(x)

    def repair(self, x):
        x = list(x)
        for _ in range(3 * self.n_j):  # 先迁移：超载包最差密度项 → slack 最大包
            load = self.loads(x)
            over_a = [a for a in range(self.n_a) if load[a] > self.caps[a]]
            if not over_a:
                return x
            worst, worst_key = None, None
            for i in range(self.n_j):
                if x[i] and (x[i] - 1) in over_a:
                    key = self.v[i] / max(1, self.w[i])
                    if worst_key is None or key < worst_key:
                        worst, worst_key = i, key
            if worst is None:
                break
            tgt = [a for a in range(self.n_a) if a != x[worst] - 1]
            best_a = max(tgt, key=lambda a: self.caps[a] - load[a])
            x[worst] = best_a + 1 if self.caps[best_a] - load[best_a] >= self.w[worst] else 0
        # 兜底：仍超载则直接丢最差密度项（必终止）
        load = self.loads(x)
        for a in range(self.n_a):
            while load[a] > self.caps[a]:
                on = [i for i in range(self.n_j) if x[i] == a + 1]
                drop = min(on, key=lambda i: self.v[i] / max(1, self.w[i]))
                x[drop] = 0
                load = self.loads(x)
        return x

    def random(self, rng):
        return self.repair([rng.randint(0, self.n_a) for _ in range(self.n_j)])

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(p["n_pop"])]
        return pop, [self.obj(s) for s in pop]


class _KPVMaxWrap:
    """把 min-sense 位编码 ctx（_KPV/_MCKP）包装成 _KS 内核期望的 max-value 接口
    （value/polish/memetic 组件），背包家族变体因此直接复用背包域全部 10 个内核。"""
    BIG = 10000

    def __init__(self, ctx):
        self._ctx = ctx
        self.prob = ctx.prob
        self.n = ctx.n
        self.cap = ctx.cap
        self.w = ctx.w
        self.v = ctx.v

    def value(self, s):
        return -self._ctx.obj(s)

    def obj(self, s):
        return self._ctx.obj(s)

    def repair(self, s):
        return self._ctx.repair(s)

    def random(self, rng):
        return self._ctx.random(rng)

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(p["n_pop"])]
        return pop, [self.value(s) for s in pop]

    def polish(self, s, rng, moves=10):
        """memetic 组件：随机单比特翻转爬山（小预算）。"""
        s = list(s)
        best = self.value(s)
        for _ in range(moves):
            prev = list(s)
            i = rng.randrange(self.n)
            s[i] ^= 1
            s2 = self.repair(s)
            v = self.value(s2)
            if v >= best:
                s, best = s2, v
            else:
                s = prev
        return s


def _es_stream(gen, ctx):
    """entryseq 词条：把「当前最优解长什么样」（vrp 的各条路线、pms 的机器分配、聚类的中心……）并进每个状态，
    页面据此作图，不在前端重算目标函数。"""
    for st in gen:
        if getattr(ctx, "best_x", None) is not None:
            # 连续内核的状态只带前两维、而且有的内核不把热启动 / 初始化阶段评价过的点算进「最优」（如 CEM 的预热采样）：
            # 这里统一以评价过的全部点里最好的那个为准——上报的最优值 = 它的目标值，best_sol = 它本身
            if ctx.best_val < st.get("best", float("inf")):
                st["best"] = ctx.best_val
            if st.get("best") == ctx.best_val or "best_sol" not in st:
                st["best_sol"] = list(ctx.best_x)
        if isinstance(st.get("best_sol"), list) and len(st["best_sol"]) == ctx.n:
            extra = ctx.detail(st["best_sol"])
            if extra:
                st.update(extra)
        yield st


def _neg_stream(gen):
    """_KS 内核流是 max-sense（value）；kpvar 全站 min-sense 口径，取负转发。"""
    for st in gen:
        st = dict(st)
        st["best"] = -st["best"]
        st["cur"] = -st["cur"]
        yield st


def _kpv_ssp_dp(ctx, p, rng):
    """子集和精确锚点：DP 求 reach 集合带父指针回溯，最优 |Σw-T|（一次出解）。"""
    w, T = ctx.w, ctx.prob["target"]
    parent = {0: None}
    reach = [0]
    for i, wi in enumerate(w):
        for s in list(reach):
            ns = s + wi
            if ns not in parent:
                parent[ns] = (s, i)
                reach.append(ns)
    best_sum = min(reach, key=lambda s: abs(s - T))
    sol = [0] * len(w)
    s = best_sum
    while parent[s] is not None:
        s0, i = parent[s]
        sol[i] = 1
        s = s0
    best = abs(best_sum - T)
    yield {"iter": 1, "best": best, "cur": best, "best_sol": sol}


def _kpv_greedy(ctx, p, rng):
    """密度贪心锚点（价值型变体共用）：按 v/w 降序装到不可行为止。"""
    n = ctx.n
    if isinstance(ctx, _MKPM):
        order = sorted(range(n), key=lambda i: ctx.v[i] / ctx.w[i], reverse=True)
        x = [0] * n
        load = [0] * ctx.n_a
        for i in order:
            for a in range(ctx.n_a):
                if load[a] + ctx.w[i] <= ctx.caps[a]:
                    x[i] = a + 1
                    load[a] += ctx.w[i]
                    break
    elif isinstance(ctx, _MCKP):
        # 每类先锁定密度最高的一件，再全局降序装
        best = [max(range(c * ctx.r, (c + 1) * ctx.r),
                    key=lambda i: ctx.v[i] / ctx.w[i]) for c in range(ctx.k)]
        order = sorted(best, key=lambda i: ctx.v[i] / ctx.w[i], reverse=True)
        s = [0] * n
        total = 0
        for i in order:
            if total + ctx.w[i] <= ctx.cap:
                s[i] = 1
                total += ctx.w[i]
        x = s
    elif getattr(ctx, "vt", None) == "mdkp":
        # 多维背包：按「价值 / 各维相对占用之和」降序，每一维都装得下才取
        W, caps = ctx.prob["W"], ctx.prob["caps"]
        order = sorted(range(n), key=lambda i: ctx.v[i] / max(1e-9, sum(W[d][i] / caps[d] for d in range(len(caps)))), reverse=True)
        s = [0] * n
        load = [0] * len(caps)
        for i in order:
            if all(load[d] + W[d][i] <= caps[d] for d in range(len(caps))):
                s[i] = 1
                for d in range(len(caps)):
                    load[d] += W[d][i]
        x = s
    else:
        order = sorted(range(n), key=lambda i: ctx.v[i] / ctx.w[i], reverse=True)
        s = [0] * n
        total = 0
        for i in order:
            if total + ctx.w[i] <= ctx.cap:
                s[i] = 1
                total += ctx.w[i]
        x = s
    best = ctx.obj(x)
    yield {"iter": 1, "best": best, "cur": best, "best_sol": list(x)}


def _kpv_cmp_dp(ctx, p, rng):
    """找零精确锚点：min-coin DP（dp[x]=凑 x 的最少枚数），在 |Σ-T| 罚下取最优可达和。"""
    denoms = sorted(ctx.prob["denoms"])
    T = ctx.prob["T"]
    INF = float("inf")
    maxs = T + max(denoms)
    dp = [INF] * (maxs + 1)
    dp[0] = 0
    for x in range(1, maxs + 1):
        for d in denoms:
            if d <= x and dp[x - d] + 1 < dp[x]:
                dp[x] = dp[x - d] + 1
    reach = [x for x in range(maxs + 1) if dp[x] < INF]
    best_x = min(reach, key=lambda x: dp[x] + ctx.BIG * abs(x - T))
    sol = [0] * ctx.n
    x = best_x
    while x > 0:
        for d in denoms:
            if d <= x and dp[x] == dp[x - d] + 1:
                for i in range(ctx.n):  # 定位一枚未用的 d
                    if ctx.w[i] == d and not sol[i]:
                        sol[i] = 1
                        break
                x -= d
                break
    best = dp[best_x] + ctx.BIG * abs(best_x - T)
    yield {"iter": 1, "best": best, "cur": best, "best_sol": sol}



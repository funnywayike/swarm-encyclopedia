# ============================================================
# 域十：无容量设施选址 UFLP（开-关向量 + 最近设施指派）
# ============================================================

def uf_make(n_f=15, n_c=45, seed=7):
    """随机 UFLP：固定成本 80-200；每个客户只有 3 个「偏好设施」指派成本
    低（5-15），其余 50-120——开哪些设施产生组合耦合，盲采样吃亏、
    局部搜索系统占优（bench 实测：random ~1354，swap-HC ~1173，局部最优 ~1129）。
    平面坐标供可视化。"""
    rng = random.Random(seed)
    f_cost = [rng.randint(80, 200) for _ in range(n_f)]
    c_cost = [[rng.randint(50, 120) for _ in range(n_c)] for _ in range(n_f)]
    for j in range(n_c):
        for a in rng.sample(range(n_f), 3):
            c_cost[a][j] = rng.randint(5, 15)
    pos_f = [[round(rng.uniform(5, 95), 1), round(rng.uniform(5, 95), 1)] for _ in range(n_f)]
    pos_c = [[round(rng.uniform(5, 95), 1), round(rng.uniform(5, 95), 1)] for _ in range(n_c)]
    return {"n_f": n_f, "n_c": n_c, "f_cost": f_cost, "c_cost": c_cost,
            "pos_f": pos_f, "pos_c": pos_c}


class _UF:
    """UFLP 域上下文：编码=设施开关向量；指派=每个客户选 cheapest open。"""

    def __init__(self, problem):
        self.n_f = problem["n_f"]
        self.n_c = problem["n_c"]
        self.f_cost = problem["f_cost"]
        self.c_cost = problem["c_cost"]
        self.n = self.n_f

    def assign(self, s):
        return [min((a for a in range(self.n_f) if s[a]),
                    key=lambda a: self.c_cost[a][j]) for j in range(self.n_c)]

    def obj(self, s):
        if not any(s):
            return 10 ** 9
        a = self.assign(s)
        return (sum(self.f_cost[i] for i in range(self.n_f) if s[i])
                + sum(self.c_cost[a[j]][j] for j in range(self.n_c)))

    # ---- 位编码协议桥（批 7 续）：_KS max 内核在本 min 域的 value/polish ----
    def value(self, s):
        return -self.obj(s)

    def polish(self, s, rng, moves=10):
        s = list(s)
        best = self.value(s)
        for _ in range(moves):
            prev = list(s)
            k = rng.randrange(self.n)
            s[k] ^= 1
            s = self.repair(s)
            v = self.value(s)
            if v >= best:
                best, s = v, s
            else:
                s = prev
        return s

    def repair(self, s):
        s = list(s)
        if not any(s):
            s[min(range(self.n_f), key=lambda i: self.f_cost[i])] = 1
        return s

    def random(self, rng):
        return self.repair([1 if rng.random() < 0.4 else 0 for _ in range(self.n_f)])

    def swap(self, s, rng):
        """关一个随机已开设施 + 开一个随机未开设施——UFLP 标准交换邻域。"""
        cand = list(s)
        on = [i for i in range(self.n_f) if cand[i]]
        off = [i for i in range(self.n_f) if not cand[i]]
        if on:
            cand[rng.choice(on)] = 0
        if off:
            cand[rng.choice(off)] = 1
        return self.repair(cand)

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(p["n_pop"])]
        return pop, [self.obj(s) for s in pop]


# ---- UFLP 专属局部搜索内核（complete-a-kernels 2026-09-29）----
def _uf_local(ctx, p, rng):
    """UFLP 专属局部搜索内核：单设施随机一阶改进（达局部最优）+ 关一开一交换（0.6 概率）
    + 停滞重启（restart_at=25）。修复 UFLP「设施+服务」复合目标卡坏局部最优
    （_KS 贪心桥 3616 vs random 1338 失效）。min 域（obj=设施开费+客户指派费）。"""
    s = ctx.random(rng)
    best = ctx.obj(s)
    stall = 0
    restart_at = 25
    for it in range(1, p["max_iter"] + 1):
        improved = True
        while improved:
            improved = False
            order = list(range(ctx.n_f)); rng.shuffle(order)
            for i in order:
                cand = list(s); cand[i] ^= 1; cand = ctx.repair(cand)
                v = ctx.obj(cand)
                if v < best:
                    s, best = cand, v; improved = True; break
        if rng.random() < 0.6:
            cand = ctx.swap(s, rng)
            v = ctx.obj(cand)
            if v < best:
                s, best = cand, v; stall = 0
            else:
                stall += 1
        else:
            stall += 1
        if stall >= restart_at:
            s = ctx.random(rng); best = ctx.obj(s); stall = 0
        yield {"iter": it, "best": best, "best_sol": list(s), "cur": ctx.obj(s)}


def _uf_greedy(ctx, p, rng):
    """贪心锚点：add+drop 双向局部搜索 + swap 抛光（从空集起，确定性对照）。
    纯 add/drop 在偏好结构实例上会卡在差局部最优（seed21 实测输给随机基线），
    加一轮「关一开一」交换抛光后与 swap 内核的局部最优同品质。"""
    s = [0] * ctx.n_f
    s[min(range(ctx.n_f), key=lambda i: ctx.f_cost[i])] = 1
    improved = True
    while improved:
        improved = False
        base = ctx.obj(s)
        for i in range(ctx.n_f):
            s[i] ^= 1
            v = ctx.obj(s)
            if v < base:
                base = v
                improved = True
            else:
                s[i] ^= 1
    # swap 抛光：add/drop 局部最优再经「关一开一」成对移动改进
    improved = True
    while improved:
        improved = False
        base = ctx.obj(s)
        for i in range(ctx.n_f):
            if not s[i]:
                continue
            for j in range(ctx.n_f):
                if s[j]:
                    continue
                s[i] = 0
                s[j] = 1
                v = ctx.obj(s)
                if v < base:
                    base = v
                    improved = True
                    break
                s[i] = 1
                s[j] = 0
            else:
                continue
            break
    v = ctx.obj(s)
    for it in range(1, p["max_iter"] + 1):
        yield {"iter": it, "best": v, "cur": v, "best_sol": list(s)}


_UF_ALGOS = dict(_SW_ALGOS, **{
    "greedy": {"fn": _uf_greedy, "name": "贪心锚点", "category": "构造启发",
               "desc": "add+drop 双向局部搜索到局部最优（确定性对照）", "tune": []},
})



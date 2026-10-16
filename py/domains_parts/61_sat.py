# ============================================================
# 域七：SAT / MAX-SAT（二进制编码 + WalkSAT + DPLL 精确锚点）
# ============================================================

def sat_make(n_vars=30, ratio=4.26, seed=7):
    """随机 3-CNF：ratio=子句/变量。4.26≈相变点（教学甜点：SAT 页常可满足，
    MAX-SAT 页用 ratio 5.2 生成多为不可满足式——最小化未满足子句数）。"""
    rng = random.Random(seed)
    n_clauses = int(n_vars * ratio)
    clauses = []
    for _ in range(n_clauses):
        lits = []
        used = set()
        while len(lits) < 3:
            v = rng.randrange(n_vars)
            if v in used:
                continue
            used.add(v)
            lits.append(v + 1 if rng.random() < 0.5 else -(v + 1))
        clauses.append(lits)
    return {"n_vars": n_vars, "clauses": clauses}


class _SAT:
    """SAT 域上下文：编码=真值赋值向量；目标=未满足子句数（min）。"""

    def __init__(self, problem):
        self.n = problem["n_vars"]
        self.clauses = problem["clauses"]

    def unsat(self, s):
        u = 0
        for cl in self.clauses:
            ok = False
            for lit in cl:
                v = abs(lit) - 1
                if s[v] == (1 if lit > 0 else 0):
                    ok = True
                    break
            if not ok:
                u += 1
        return u

    def obj(self, s):
        return self.unsat(s)


    # ---- 位编码族复用桥（2026-09-27 ROADMAP 批 7）：_KS max 内核在本 min 域的桥 ----
    def value(self, s):
        return -self.obj(s)  # max 协议桥：obj 越小 = value 越大

    def polish(self, s, rng, moves=10):
        """memetic 位翻转爬山（value 协议）。"""
        s = list(s)
        best = self.value(s)
        for _ in range(moves):
            prev = list(s)
            i = rng.randrange(self.n)
            s[i] ^= 1
            s = self.repair(s)
            v = self.value(s)
            if v >= best:
                s, best = s2 if False else s, v
            else:
                s = prev
        return s

    def repair(self, s):
        return list(s)  # 无约束：任何赋值都合法

    def random(self, rng):
        return [rng.randint(0, 1) for _ in range(self.n)]

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(p["n_pop"])]
        return pop, [self.obj(s) for s in pop]


def _sat_walksat(ctx, p, rng):
    """WalkSAT（Schöning 1999 精神）：随机取未满足子句，以概率 p 翻转其中随机
    变量，否则翻转「使未满足数降幅最大」的变量——纯本地操作，无种群。"""
    s = ctx.random(rng)
    v = ctx.obj(s)
    best, bs = v, list(s)
    wp = p["walk_p"]
    last_it = 0
    for it in range(1, p["max_iter"] + 1):
        if v == 0:
            break  # 已满足：提前收工（SAT 页常态），后面补齐曲线长度
        unsat = [cl for cl in ctx.clauses
                 if all(s[abs(l) - 1] != (1 if l > 0 else 0) for l in cl)]
        cl = unsat[rng.randrange(len(unsat))]
        if rng.random() < wp:
            lit = cl[rng.randrange(len(cl))]
            s[abs(lit) - 1] ^= 1
        else:
            best_lit, best_u = None, None
            for lit in cl:
                s[abs(lit) - 1] ^= 1
                u = ctx.obj(s)
                s[abs(lit) - 1] ^= 1
                if best_u is None or u < best_u:
                    best_lit, best_u = lit, u
            s[abs(best_lit) - 1] ^= 1
        v = ctx.obj(s)
        if v < best:
            best, bs = v, list(s)
        yield {"iter": it, "best": best, "cur": v, "best_sol": list(bs)}
        last_it = it
    for it2 in range(last_it + 1, p["max_iter"] + 1):  # 补齐：保证曲线恰为 max_iter 个状态
        yield {"iter": it2, "best": best, "cur": v, "best_sol": list(bs)}


def _sat_dpll(ctx, p, rng):
    """DPLL 精确锚点（单位传播 + 分裂）：首个迭代即给出真值最优（SAT 页=0）。
    确定性算法：与随机种子无关——这就是「精确对照」的教学点。"""
    n, clauses = ctx.n, ctx.clauses
    assign = [None] * n

    def dpll(cl, asg):
        # 单位传播：仅当子句「尚未满足」且只剩一个未赋值文字时才传播
        while True:
            prog = False
            for c in cl:
                if any(asg[abs(l) - 1] == (1 if l > 0 else 0)
                       for l in c if asg[abs(l) - 1] is not None):
                    continue  # 子句已满足：不能据此传播
                un = [l for l in c if asg[abs(l) - 1] is None]
                if not un:
                    return None  # 全赋值且无真文字：冲突
                if len(un) == 1:
                    l = un[0]
                    v = abs(l) - 1
                    val = 1 if l > 0 else 0
                    if asg[v] is not None and asg[v] != val:
                        return None  # 两个单位子句互相矛盾
                    asg[v] = val
                    prog = True
            if not prog:
                break
        if all(any(asg[abs(l) - 1] == (1 if l > 0 else 0) for l in c)
               for c in cl):
            return asg
        v = next((i for i in range(n) if asg[i] is None), None)
        if v is None:
            return None
        for val in (1, 0):
            asg2 = list(asg)
            asg2[v] = val
            r = dpll(cl, asg2)
            if r is not None:
                return r
        return None

    sol = dpll(clauses, assign)
    if sol is None:
        # 不可满足（MAX-SAT 页常态）：退化为确定性的最速下降 MAX-SAT 兜底，
        # 让锚点至少是一个合理的局部最优，而不是全 0 赋值
        sol = [0] * n
        v = ctx.obj(sol)
        improved = True
        while improved:
            improved = False
            for i in range(n):
                sol[i] ^= 1
                nv = ctx.obj(sol)
                if nv < v:
                    v = nv
                    improved = True
                else:
                    sol[i] ^= 1
    u = ctx.obj(sol)
    for it in range(1, p["max_iter"] + 1):
        yield {"iter": it, "best": u, "cur": u, "best_sol": list(sol)}


_SAT_ALGOS = dict(_BIN_ALGOS, **{
    "walksat": {"fn": _sat_walksat, "name": "WalkSAT", "category": "局部搜索",
                "desc": "未满足子句内随机/贪心翻转变量（Schöning 系）", "tune": ["walk_p"]},
    "dpll": {"fn": _sat_dpll, "name": "DPLL 精确", "category": "精确算法",
             "desc": "单位传播 + 分裂的完备精确解（确定性锚点）", "tune": []},
})



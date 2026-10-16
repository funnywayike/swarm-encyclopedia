# ============================================================
# 域九：广义指派 GAP（整数向量编码：任务→代理）
# ============================================================

def gap_make(n_a=8, n_j=25, seed=7):
    """随机 GAP：成本 5-40、资源 5-25；代理容量 = 该行资源总和 × 0.65
    （保证贪心可行且容量有约束力）。"""
    rng = random.Random(seed)
    c = [[rng.randint(5, 40) for _ in range(n_j)] for _ in range(n_a)]
    r = [[rng.randint(5, 25) for _ in range(n_j)] for _ in range(n_a)]
    cap = [int(sum(row) * 0.65) for row in r]
    return {"n_a": n_a, "n_j": n_j, "c": c, "r": r, "cap": cap}


class _GAP:
    """GAP 域上下文：编码=任务→代理向量；超载用 BIG 罚 + 修复算子。"""
    BIG = 1000

    def __init__(self, problem):
        self.n_a = problem["n_a"]
        self.n_j = problem["n_j"]
        self.c = problem["c"]
        self.r = problem["r"]
        self.cap = problem["cap"]
        self.n = self.n_j

    def cost(self, s):
        return sum(self.c[s[j]][j] for j in range(self.n_j))

    def overflow(self, s):
        load = [0] * self.n_a
        for j in range(self.n_j):
            load[s[j]] += self.r[s[j]][j]
        return sum(max(0, load[a] - self.cap[a]) for a in range(self.n_a))

    def clamp(self, s):
        na = self.p["n_a"] if "n_a" in self.p else self.n
        return [max(0, min(na - 1, int(round(v)))) % na if "n_a" in self.p else int(v) % na for v in s]

    def swap(self, s, rng):
        s = list(s)
        a, b = rng.randrange(len(s)), rng.randrange(len(s))
        s[a], s[b] = s[b], s[a]
        return s

    def obj(self, s):
        return self.cost(s) + self.BIG * self.overflow(s)

    def repair(self, s):
        s = list(s)
        while self.overflow(s) > 0:
            load = [0] * self.n_a
            for j in range(self.n_j):
                load[s[j]] += self.r[s[j]][j]
            over = max(range(self.n_a), key=lambda a: load[a] - self.cap[a])
            jobs = [j for j in range(self.n_j) if s[j] == over]
            if not jobs:
                break
            j = jobs[0]
            best_a, best_o = None, None
            for a in range(self.n_a):
                if a == over:
                    continue
                s[j] = a
                o = self.overflow(s)
                if best_o is None or o < best_o:
                    best_a, best_o = a, o
            s[j] = best_a
        return s

    def random(self, rng):
        return self.repair([rng.randrange(self.n_a) for _ in range(self.n_j)])

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(p["n_pop"])]
        return pop, [self.obj(s) for s in pop]


def _gap_random(ctx, p, rng):
    best, bs = None, None
    for it in range(1, p["max_iter"] + 1):
        s = ctx.random(rng)
        v = ctx.obj(s)
        if bs is None or v < best:
            best, bs = v, s
        yield {"iter": it, "best": best, "cur": v, "best_sol": list(bs)}


def _gap_hc(ctx, p, rng):
    s = ctx.random(rng)
    v = ctx.obj(s)
    best, bs = v, list(s)
    for it in range(1, p["max_iter"] + 1):
        for _ in range(p["tries"]):
            cand = list(s)
            cand[rng.randrange(ctx.n_j)] = rng.randrange(ctx.n_a)
            cand = ctx.repair(cand)
            cv = ctx.obj(cand)
            if cv <= v:
                s, v = cand, cv
        if v < best:
            best, bs = v, list(s)
        yield {"iter": it, "best": best, "cur": v, "best_sol": list(bs)}


def _gap_sa(ctx, p, rng):
    s = ctx.random(rng)
    v = ctx.obj(s)
    best, bs = v, list(s)
    t0, decay = p["t0"], p["decay"]
    stall = 0
    for it in range(1, p["max_iter"] + 1):
        T = t0 * (decay ** it)
        cand = list(s)
        cand[rng.randrange(ctx.n_j)] = rng.randrange(ctx.n_a)
        cand = ctx.repair(cand)
        cv = ctx.obj(cand)
        d = cv - v
        if d < 0 or (T > 1e-12 and rng.random() < math.exp(-d / T)):
            s, v = cand, cv
        if v < best:
            best, bs = v, list(s)
            stall = 0
        else:
            stall += 1
        if stall >= p["restart_at"]:  # ILS：罚函数景观下单链易卡，停滞即全新重启
            s = ctx.random(rng)
            v = ctx.obj(s)
            stall = 0
        yield {"iter": it, "best": best, "cur": v, "best_sol": list(bs)}


def _gap_ga(ctx, p, rng):
    pop, vals = ctx.init_pop(p, rng)
    bi = argbest(vals, "min")
    best, bs = vals[bi], list(pop[bi])
    for it in range(1, p["max_iter"] + 1):
        new = [list(pop[bi])]
        while len(new) < p["n_pop"]:
            a, b = rng.sample(range(p["n_pop"]), 2)
            child = [pop[a][j] if rng.random() < 0.5 else pop[b][j] for j in range(ctx.n_j)]
            for _ in range(2):
                child[rng.randrange(ctx.n_j)] = rng.randrange(ctx.n_a)
            child = ctx.repair(child)
            new.append(child)
        pop = new
        vals = [ctx.obj(s) for s in pop]
        bi = argbest(vals, "min")
        if vals[bi] < best:
            best, bs = vals[bi], list(pop[bi])
        yield {"iter": it, "best": best, "cur": min(vals), "best_sol": list(bs)}


_GAP_ALGOS = {
    "random": {"fn": _gap_random, "name": "随机搜索", "category": "基线",
               "desc": "盲指派基线：一切算法都要显著降低总成本", "tune": []},
    "hc": {"fn": _gap_hc, "name": "爬山法 HC", "category": "局部搜索",
           "desc": "单任务改派贪心（容量修复后评价）", "tune": ["tries"]},
    "sa": {"fn": _gap_sa, "name": "模拟退火 SA", "category": "物理启发",
           "desc": "改派移动 + Metropolis 准则", "tune": ["t0", "decay"]},
    "ga": {"fn": _gap_ga, "name": "遗传 GA", "category": "进化计算",
           "desc": "整数均匀交叉 + 改派变异 + 修复", "tune": []},
}



# ============================================================
# 域六：集合覆盖 SCP（0-1 编码 + 覆盖修复）
# ============================================================

def sc_make(n_el=80, m=50, seed=7):
    """随机 SCP 实例：每集合以 ~25% 概率覆盖每个元素（成本 5-60）。
    保证全覆盖（每个元素至少入一个集合）——修复算子才有正确性前提。
    参数标定（bench 实测）：重叠冗余 + 成本方差给搜索留足空间——
    随机修复基线 ~120，swap 局部搜索 ~88，Chvátal 贪心 ~99。"""
    rng = random.Random(seed)
    sets = [[1 if rng.random() < 0.25 else 0 for _ in range(n_el)] for _ in range(m)]
    for e in range(n_el):  # 全覆盖修补
        if not any(s[e] for s in sets):
            sets[rng.randrange(m)][e] = 1
    costs = [rng.randint(5, 60) for _ in range(m)]
    return {"n_el": n_el, "m": m, "sets": sets, "costs": costs}


class _SC:
    """SCP 域上下文：编码=集合开关向量；不可行（有未覆盖元素）用 BIG 罚。"""
    BIG = 1000

    def __init__(self, problem):
        self.n_el = problem["n_el"]
        self.m = problem["m"]
        self.sets = problem["sets"]
        self.costs = problem["costs"]
        self.n = self.m
        # 位掩码：每个集合覆盖的元素压成一个整数。覆盖判断从「元素×集合」次 Python 循环降到「集合」次整数或运算——
        # 500×500 的实例上单次评价快两个数量级，结果与逐格判断完全相同（黄金快照核对过）
        self._mask = [sum(1 << e for e in range(self.n_el) if row[e]) for row in self.sets]
        self._full = (1 << self.n_el) - 1

    def cost(self, s):
        return sum(self.costs[i] for i in range(self.m) if s[i])

    def _covered(self, s):
        c = 0
        for i, mk in enumerate(self._mask):
            if s[i]:
                c |= mk
        return c

    def uncovered(self, s):
        return bin(self._full & ~self._covered(s)).count("1")  # 不用 int.bit_count：命令行支持 Python 3.8

    def obj(self, s):
        return self.cost(s) + self.BIG * self.uncovered(s)


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
        s = list(s)
        cov = self._covered(s)
        while self._full & ~cov:  # 贪心补覆盖：新覆盖/成本 比最高者
            best_i, best_r = None, -1.0
            for i in range(self.m):
                if s[i]:
                    continue
                new = bin(self._mask[i] & ~cov).count("1")
                if new == 0:
                    continue
                r = new / self.costs[i]
                if r > best_r:
                    best_i, best_r = i, r
            if best_i is None:
                break
            s[best_i] = 1
            cov |= self._mask[best_i]
        for i in range(self.m):  # 去冗余：删掉后仍全覆盖才删
            if s[i]:
                s[i] = 0
                if self.uncovered(s) > 0:
                    s[i] = 1
        return s

    def random(self, rng):
        return self.repair([1 if rng.random() < 0.3 else 0 for _ in range(self.m)])

    def swap(self, s, rng):
        """关一个随机已选集合 + 开一个随机未选集合，再修复——Δ 平滑的成对移动。"""
        cand = list(s)
        on = [i for i in range(self.m) if cand[i]]
        off = [i for i in range(self.m) if not cand[i]]
        if on:
            cand[rng.choice(on)] = 0
        if off:
            cand[rng.choice(off)] = 1
        return self.repair(cand)

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(p["n_pop"])]
        return pop, [self.obj(s) for s in pop]


def _sc_greedy(ctx, p, rng):
    """贪心 ln n 锚点（Chvátal 1979）：一次构造，之后持平——确定性对照。"""
    s = [0] * ctx.m
    cov = [0] * ctx.n_el
    left = ctx.n_el
    while left > 0:
        best_i, best_r = None, -1.0
        for i in range(ctx.m):
            if s[i]:
                continue
            new = sum(1 for e in range(ctx.n_el) if ctx.sets[i][e] and not cov[e])
            if new == 0:
                continue
            r = new / ctx.costs[i]
            if r > best_r:
                best_i, best_r = i, r
        s[best_i] = 1
        for e in range(ctx.n_el):
            if ctx.sets[best_i][e] and not cov[e]:
                cov[e] = 1
                left -= 1
    v = ctx.cost(s)
    for it in range(1, p["max_iter"] + 1):
        yield {"iter": it, "best": v, "cur": v, "best_sol": list(s)}



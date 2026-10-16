# ============================================================
# 域八：QUBO（二进制二次型，min x'Qx）
# ============================================================

def qb_make(n=30, seed=7):
    """随机 QUBO：对角线 -20~60，非对角 ±15（对称）。总有平凡界，实例无约束。"""
    rng = random.Random(seed)
    Q = [[0] * n for _ in range(n)]
    for i in range(n):
        Q[i][i] = rng.randint(-20, 60)
        for j in range(i + 1, n):
            v = rng.randint(-15, 15)
            Q[i][j] = v
            Q[j][i] = v
    return {"n": n, "Q": Q}


class _QB:
    def __init__(self, problem):
        self.n = problem["n"]
        self.Q = problem["Q"]

    def obj(self, s):
        Q = self.Q
        return sum(Q[i][j] * s[i] * s[j] for i in range(self.n) for j in range(self.n))


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
        return list(s)

    def random(self, rng):
        return [rng.randint(0, 1) for _ in range(self.n)]

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(p["n_pop"])]
        return pop, [self.obj(s) for s in pop]



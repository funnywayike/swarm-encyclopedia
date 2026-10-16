# ============================================================
# 域五：装箱 Bin Packing（排列 + First-Fit 装箱）
# ============================================================

def bp_make(n=40, seed=7):
    """经典半均匀分布：物品重 U[20,100]，容量 150。
    下界 LB = ⌈Σw/C⌉≈0.4n，FFD 通常 LB+1~2，随机序 FF 差 2~3 箱——
    优化空间真实存在但不会离谱（教育友好）。"""
    rng = random.Random(seed)
    items = [rng.randint(20, 100) for _ in range(n)]
    return {"n": n, "cap": 150, "items": items}


class _BP:
    """装箱域上下文：解码 = 按排列顺序 First-Fit 装箱。"""

    def __init__(self, problem):
        self.items = list(problem["items"])
        self.cap = problem["cap"]
        self.n = problem["n"]

    def pack(self, perm):
        rem = []  # 每箱剩余容量
        assign = [0] * self.n
        for idx in perm:
            w = self.items[idx]
            for b in range(len(rem)):
                if rem[b] >= w:
                    rem[b] -= w
                    assign[idx] = b
                    break
            else:
                rem.append(self.cap - w)
                assign[idx] = len(rem) - 1
        return assign, rem

    def decode(self, perm):
        assign, rem = self.pack(perm)
        tie = sum(r * r for r in rem)  # Σ剩余²：鼓励塞紧
        return (len(rem), tie)

    def solution(self, perm):
        return self.pack(perm)[0]

    def better(self, a, b):
        return a < b

    def diff(self, c1, c2):
        return (c2[0] - c1[0]) * 1000000 + (c2[1] - c1[1])

    def random(self, rng):
        p = list(range(self.n))
        rng.shuffle(p)
        return p



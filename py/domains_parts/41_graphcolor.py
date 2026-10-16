# ============================================================
# 域四：图着色（排列 + First-Fit 贪心着色）
# ============================================================

def gc_make(n=50, seed=7, p=0.5):
    """DSJC 均匀随机图（Graph Coloring 基准标准族）：每对顶点以概率 p 连边。
    实测教训：随机几何图太「结构化」，随机序 First-Fit 就近乎最优（全员贴底）；
    DSJC p=0.5 时随机序 FF ≈ 12 色，优化后 10~11 色——优化空间真实存在。
    布局 = 环形 + 抖动（可视化用，与着色质量无关）。"""
    rng = random.Random(seed)
    edges = [[i, j] for i in range(n) for j in range(i + 1, n) if rng.random() < p]
    pos = []
    for i in range(n):
        ang = 2 * math.pi * i / n
        pos.append([round(50 + 42 * math.cos(ang) + rng.uniform(-4, 4), 1),
                    round(50 + 42 * math.sin(ang) + rng.uniform(-4, 4), 1)])
    return {"n": n, "edges": edges, "pos": pos}


class _GC:
    """图着色域上下文：解码 = 按排列顺序 First-Fit 着色（合法由构造保证）。"""

    def __init__(self, problem):
        self.n = problem["n"]
        self.adj = [[] for _ in range(self.n)]
        for u, v in problem["edges"]:
            self.adj[u].append(v)
            self.adj[v].append(u)

    def color(self, perm):
        col = [-1] * self.n
        for v in perm:
            used = {col[u] for u in self.adj[v] if col[u] >= 0}
            c = 0
            while c in used:
                c += 1
            col[v] = c
        return col

    def decode(self, perm):
        col = self.color(perm)
        k = max(col) + 1
        tie = sum(c * c for c in col)  # Σci²：鼓励空出高编号桶
        return (k, tie)

    def solution(self, perm):
        return self.color(perm)

    def better(self, a, b):
        return a < b

    def diff(self, c1, c2):
        # SA 用标量：任何色数改进压倒一切次级变化（BIG 足够大）
        return (c2[0] - c1[0]) * 100000 + (c2[1] - c1[1])

    def random(self, rng):
        p = list(range(self.n))
        rng.shuffle(p)
        return p



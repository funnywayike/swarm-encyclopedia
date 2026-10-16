# ============================================================
# 域：着色家族 gcvar（H2 单域多预设：列表/预染/边/全/MIS 五变体）
# 排列编码变体（listcolor/precolor/edgecolor/totalcolor）复用 _pm_* 排列内核；
# mis 用 0/1 位串编码，复用 _bin_* 位串内核（禁改现有图着色/装箱内核）。
# ============================================================

def _graph_adj(edges, n):
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
        adj[v].append(u)
    return adj


def _greedy_ff_color(adj, rng):
    """随机序 First-Fit 正常着色，返回合法 col 数组。"""
    n = len(adj)
    order = list(range(n))
    rng.shuffle(order)
    col = [-1] * n
    for v in order:
        used = {col[u] for u in adj[v] if col[u] >= 0}
        c = 0
        while c in used:
            c += 1
        col[v] = c
    return col


def _list_colorable(adj, lists, rng):
    """随机试若干排列的 FF-list 解码，能得 0 冲突即视为列表可着色。"""
    n = len(adj)
    for _ in range(16):
        perm = list(range(n))
        rng.shuffle(perm)
        col = [-1] * n
        ok = True
        for v in perm:
            used = {col[u] for u in adj[v] if col[u] >= 0}
            cand = [c for c in lists[v] if c not in used]
            if not cand:
                ok = False
                break
            col[v] = min(cand)
        if ok:
            return True
    return False


def gcv_make(variant="listcolor", n=40, seed=7, p=0.5):
    """着色家族实例生成：先生成 DSJC 随机图 G（环形布局），再按变体加约束/变换。
    listcolor=每顶点候选色列表（删 1-2 色，校验可着色）；precolor=先合法着色再固定 20-30%；
    edgecolor=线图 L(G)；totalcolor=全图 T(G)；mis=同图（位串编码，见 _MIS）。"""
    rng = random.Random(seed)
    edges = [[i, j] for i in range(n) for j in range(i + 1, n) if rng.random() < p]
    pos = []
    for i in range(n):
        ang = 2 * math.pi * i / n
        pos.append([round(50 + 42 * math.cos(ang) + rng.uniform(-4, 4), 1),
                    round(50 + 42 * math.sin(ang) + rng.uniform(-4, 4), 1)])
    adj = _graph_adj(edges, n)
    prob = {"variant": variant, "n": n, "edges": edges, "pos": pos, "p": p}
    if variant == "listcolor":
        # 候选色列表：调色板 K = max_degree + 3（宽松但保留约束感）；每顶点删 1-2 色。
        # 生成后校验列表可着色（随机若干排列 FF-list 能得 0 冲突），不可着色则重试删色。
        K = max((len(a) for a in adj), default=0) + 3
        for _ in range(60):
            lists = []
            for i in range(n):
                allc = list(range(K))
                rm = rng.sample(allc, min(rng.randint(1, 2), K - 2))
                lists.append(sorted(set(allc) - set(rm)))
            if _list_colorable(adj, lists, rng):
                prob["lists"] = lists
                prob["K"] = K
                break
        else:
            lists = [list(range(K))[:-1] for _ in range(n)]
            prob["lists"] = lists
            prob["K"] = K
    elif variant == "precolor":
        # 先合法着色再固定 20-30% 顶点
        col = _greedy_ff_color(adj, rng)
        K = max(col) + 1
        nfix = int(n * rng.uniform(0.2, 0.3))
        fix = [-1] * n
        for i in rng.sample(range(n), nfix):
            fix[i] = col[i]
        prob["precol"] = fix
        prob["K"] = K
    elif variant == "edgecolor":
        # 线图变换 L(G)：G 的边→L(G) 顶点，相邻边对（共享顶点）→L(G) 边
        m = len(edges)
        lad = [[] for _ in range(m)]
        for a in range(m):
            u1, v1 = edges[a]
            for b in range(m):
                if a == b:
                    continue
                u2, v2 = edges[b]
                if u1 in (u2, v2) or v1 in (u2, v2):
                    lad[a].append(b)
        prob["ladj"] = lad
        prob["m"] = m
    elif variant == "totalcolor":
        # 全图 T(G)：顶点+边元素，邻接=顶-顶/边-边/顶-边关联
        m = len(edges)
        N = n + m
        tad = [[] for _ in range(N)]
        for u, v in edges:
            tad[u].append(v)
            tad[v].append(u)
        for a in range(m):
            u1, v1 = edges[a]
            for b in range(m):
                if a == b:
                    continue
                u2, v2 = edges[b]
                if u1 in (u2, v2) or v1 in (u2, v2):
                    tad[n + a].append(n + b)
            tad[u1].append(n + a)
            tad[n + a].append(u1)
            tad[v1].append(n + a)
            tad[n + a].append(v1)
        prob["tadj"] = tad
        prob["nV"] = n
        prob["m"] = m
        prob["N"] = N
    # mis 同图实例，无额外约束（位串编码，见 _MIS）
    return prob


class _GCV:
    """着色家族排列编码 ctx（listcolor/precolor/edgecolor/totalcolor）。
    解码 = 按排列顺序给元素分配最小可用颜色（listcolor 限列表 / precolor 锁预染 /
    edgecolor/totalcolor 走线图/全图邻接）。obj = (色数 k, 冲突数, Σci²)。"""
    BIG = 100000

    def __init__(self, problem):
        vt = problem["variant"]
        if vt == "edgecolor":
            self.N = problem["m"]
            self.elem_adj = [list(a) for a in problem["ladj"]]
            self.lists = None
            self.fixed = [-1] * self.N
        elif vt == "totalcolor":
            self.N = problem["N"]
            self.elem_adj = [list(a) for a in problem["tadj"]]
            self.lists = None
            self.fixed = [-1] * self.N
        else:
            self.N = problem["n"]
            self.elem_adj = _graph_adj(problem["edges"], self.N)
            self.lists = problem.get("lists")
            self.fixed = problem.get("precol") or [-1] * self.N
        self.n = self.N  # _pm_ts 等内核用 ctx.n

    def _color(self, perm):
        N = self.N
        col = [-1] * N
        # 预染顶点必须最先上色：否则非预染顶点若先于其预染邻居被处理，
        # 会因「只规避已上色邻居」而误取预染色，造成冲突（precolor 必现）。
        for e in range(N):
            if self.fixed[e] >= 0:
                col[e] = self.fixed[e]
        for e in perm:
            if self.fixed[e] >= 0:
                continue
            used = {col[x] for x in self.elem_adj[e] if col[x] >= 0}
            if self.lists is not None:
                cand = [c for c in self.lists[e] if c not in used]
                col[e] = min(cand) if cand else min(self.lists[e])
            else:
                c = 0
                while c in used:
                    c += 1
                col[e] = c
        return col

    def decode(self, perm):
        col = self._color(perm)
        conf = 0
        for e in range(self.N):
            ce = col[e]
            for x in self.elem_adj[e]:
                if x > e and col[x] == ce:
                    conf += 1
        k = (max(col) + 1) if self.N else 0
        tie = sum(c * c for c in col)
        return (k, conf, tie)

    def solution(self, perm):
        return self._color(perm)

    def better(self, a, b):
        # 合法性（conf=0）优先于色数：着色演示必须展示合法着色，非法着色
        # （预染冲突 / 列表死胡同）即使色数更少也不算优。同合法下最小化色数 k，再 Σci²。
        return (a[1] > 0, a[0], a[2]) < (b[1] > 0, b[0], b[2])

    def diff(self, c1, c2):
        return (((c2[1] > 0) - (c1[1] > 0)) * 10 ** 9
                + (c2[0] - c1[0]) * 1000
                + (c2[2] - c1[2]))

    def random(self, rng):
        p = list(range(self.N))
        rng.shuffle(p)
        return p


def _gcv_greedy(ctx, p, rng):
    """多起点 First-Fit 贪心（构造式锚点，确定性）：在度降序、度升序与若干随机序中取最优着色。
    列表/预染/线图/全图统一走解码；覆盖足够序空间，作为对照基线不劣于纯随机 best-of-200。"""
    orderings = [sorted(range(ctx.N), key=lambda e: -len(ctx.elem_adj[e])),
                 sorted(range(ctx.N), key=lambda e: len(ctx.elem_adj[e]))]
    for _ in range(200):
        o = list(range(ctx.N))
        rng.shuffle(o)
        orderings.append(o)
    best_c, best_perm = None, None
    for o in orderings:
        c = ctx.decode(o)
        if best_c is None or c < best_c:
            best_c, best_perm = c, list(o)
    yield {"iter": 1, "best": best_c[0], "cur": best_c[0], "tie": best_c[1],
           "best_sol": ctx.solution(best_perm)}


class _MIS:
    """MIS 最大独立集：0/1 位串编码，obj = -|S| + BIG*冲突（repair 后恒 0 冲突）。复用 _bin_* 位串内核。"""
    BIG = 10000

    def __init__(self, problem):
        self.n = problem["n"]
        self.adj = _graph_adj(problem["edges"], self.n)

    def obj(self, s):
        size = sum(s)
        conf = 0
        for u in range(self.n):
            if s[u]:
                for v in self.adj[u]:
                    if v > u and s[v]:
                        conf += 1
        return -size + self.BIG * conf

    def repair(self, s):
        s = list(s)
        while True:
            bad = None
            for u in range(self.n):
                if not s[u]:
                    continue
                for v in self.adj[u]:
                    if v > u and s[v]:
                        bad = u if len(self.adj[u]) >= len(self.adj[v]) else v
                        break
                if bad is not None:
                    break
            if bad is None:
                return s
            s[bad] = 0

    def random(self, rng):
        return self.repair([1 if rng.random() < 0.5 else 0 for _ in range(self.n)])

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(p["n_pop"])]
        return pop, [self.obj(s) for s in pop]


def _mis_greedy(ctx, p, rng):
    """度升序贪心（确定性锚点）：度小者优先入集，与已选顶点相邻则跳过。"""
    order = sorted(range(ctx.n), key=lambda i: len(ctx.adj[i]))
    s = [0] * ctx.n
    taken = set()
    for i in order:
        if not any(nei in taken for nei in ctx.adj[i]):
            s[i] = 1
            taken.add(i)
    best = ctx.obj(s)
    yield {"iter": 1, "best": best, "cur": best, "best_sol": list(s)}



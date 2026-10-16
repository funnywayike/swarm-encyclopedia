# ---- 通用「离散 / 局部搜索系」内核（2026-10）：ILS、VNS、ACO、GRASP 只写一遍 ----
# 各问题域对「评价」和「邻居」的接口并不统一（obj / value / decode / eval；有的有 swap，有的没有）。
# _MinView 把任何域整理成最小接口：random / fix（修复）/ obj（越小越好的标量）/ swap（邻居），并自己追踪评价过的最优解：
# 上报的 best 一定等于上报的 best_sol 的目标值。max 协议的域（只有 value）在视图里取负，yield 时再还原符号。


class _MinView:
    def __init__(self, ctx, rng):
        self._c = ctx
        ref = ctx.random(rng)
        self.n = len(ref)
        if sorted(ref) == list(range(len(ref))):
            self.kind = "perm"
        elif hasattr(ctx, "n_a") or (all(isinstance(v, int) for v in ref) and not all(v in (0, 1) for v in ref)):
            self.kind = "assign"
            self.na = int(getattr(ctx, "n_a", 0) or (max(ref) + 1))
        elif all(v in (0, 1) for v in ref):
            self.kind = "bits"
        else:
            self.kind = "real"
            self.lo, self.hi = getattr(ctx, "lo", -5.0), getattr(ctx, "hi", 5.0)
        self.sign = 1
        if hasattr(ctx, "decode"):
            self._f = ctx.decode
        elif hasattr(ctx, "obj"):
            self._f = ctx.obj
        elif hasattr(ctx, "eval"):
            self._f = ctx.eval
        else:
            self._f, self.sign = (lambda s: -ctx.value(s)), -1
        self.best_val, self.best_tie, self.best_sol = float("inf"), 0.0, None
        self.last = None

    def random(self, rng):
        return self.fix(self._c.random(rng))

    def fix(self, s):
        if self.kind in ("bits", "assign") and hasattr(self._c, "repair"):
            return self._c.repair(s)
        return s

    def obj(self, s):
        self.last = s
        raw = self._f(s)
        val, tie = (raw[0], raw[1] if len(raw) > 1 else 0.0) if isinstance(raw, tuple) else (raw, 0.0)
        if (val, tie) < (self.best_val, self.best_tie):
            self.best_val, self.best_tie = val, tie
            self.best_sol = self._c.solution(s) if (self.kind == "perm" and hasattr(self._c, "solution")) else list(s)
        return val + 1e-6 * tie

    def swap(self, s, rng):
        s = list(s)
        if self.kind == "perm":
            i, j = rng.sample(range(self.n), 2)
            if rng.random() < 0.5:
                s[i], s[j] = s[j], s[i]
            else:
                v = s.pop(i)
                s.insert(j, v)
            return s
        if self.kind == "bits":
            s[rng.randrange(self.n)] ^= 1
            return self.fix(s)
        if self.kind == "assign":
            s[rng.randrange(self.n)] = rng.randrange(self.na)
            return self.fix(s)
        k = rng.randrange(self.n)
        s[k] = min(self.hi, max(self.lo, s[k] + rng.gauss(0, 0.3 * (self.hi - self.lo) / 5)))
        return s

    def state(self, st):
        out = {"iter": st["iter"], "best": self.sign * self.best_val, "cur": st.get("cur", self.sign * self.best_val),
               "best_sol": self.best_sol}
        if self.best_tie:
            out["tie"] = self.best_tie
        if self.kind == "real" and self.best_sol:  # 连续域的页面按前两维画点：补上它读的字段
            out["gbest_pos"] = list(self.best_sol[:2])
            out["particles"] = [list((self.last or self.best_sol)[:2])]
        return out


def _viewed(kernel, tag):
    def wrapped(ctx, p, rng):
        view = _MinView(ctx, rng)
        q = dict(p)
        q.setdefault("n_pop", 30)
        for st in kernel(view, q, rng):
            yield view.state(st)
    wrapped.__name__ = tag
    return wrapped


def _mv_descent(view, s, v, rng, max_fail):
    """采样式一阶下降：连续 max_fail 个随机邻居都没变好就停（不枚举整个邻域——评价次数可控）。"""
    fails = 0
    while fails < max_fail:
        nb = view.swap(s, rng)
        nv = view.obj(nb)
        if nv < v:
            s, v, fails = nb, nv, 0
        else:
            fails += 1
    return s, v


def _mv_ils(view, p, rng):
    """迭代局部搜索 ILS（Lourenço, Martin & Stützle 2003）：扰动（随机移动若干步）→ 下降到局部最优 → 不比当前差就接受。"""
    s = view.random(rng)
    v = view.obj(s)
    s, v = _mv_descent(view, s, v, rng, 10)
    kick = max(2, min(view.n // 4, 6))
    for it in range(1, p["max_iter"] + 1):
        cand = s
        for _ in range(kick):
            cand = view.swap(cand, rng)
        cv = view.obj(cand)
        cand, cv = _mv_descent(view, cand, cv, rng, 10)
        if cv <= v:
            s, v = cand, cv
        yield {"iter": it, "cur": v * view.sign}


def _mv_vns(view, p, rng):
    """变邻域搜索 VNS（Mladenović & Hansen 1997）：第 k 个邻域 = 随机移动 k 步；摇动 → 下降，变好就回到 k = 1，否则换更大的邻域。"""
    s = view.random(rng)
    v = view.obj(s)
    k, kmax = 1, 5
    for it in range(1, p["max_iter"] + 1):
        cand = s
        for _ in range(k):
            cand = view.swap(cand, rng)
        cv = view.obj(cand)
        cand, cv = _mv_descent(view, cand, cv, rng, 8)
        if cv < v:
            s, v, k = cand, cv, 1
        else:
            k = k + 1 if k < kmax else 1
        yield {"iter": it, "cur": v * view.sign}


def _mv_aco(view, p, rng):
    """蚁群优化（排序式 Ant System，Bullnheimer et al. 1999；信息素带上下界，Stützle & Hoos 2000）。
    每只蚂蚁在「决策图」上逐步选：排列 = 每个位置选一个还没用过的元素；位向量 = 每位选 0 / 1；指派 = 每个任务选一个代理；
    信息素 τ 对应决策（位置 → 元素 / 位 → 取值 / 任务 → 代理）；每代按排名给前 w 只蚂蚁的路径加信息素，历史最优额外加权。
    没有问题专属的启发式信息——只靠信息素，所以对任意目标函数都能用。"""
    n = view.n
    m = int(p.get("n_pop", 30))
    if view.kind == "perm":
        tau = [[1.0] * n for _ in range(n)]
    elif view.kind == "bits":
        tau = [[1.0, 1.0] for _ in range(n)]
    else:
        tau = [[1.0] * view.na for _ in range(n)]
    rho, w, t_min, t_max = 0.1, min(6, m), 0.05, 20.0
    gbest, gv = None, float("inf")

    def pick(weights, rng):
        tot = sum(weights)
        r, acc = rng.random() * tot, 0.0
        for idx, wv in enumerate(weights):
            acc += wv
            if acc >= r:
                return idx
        return len(weights) - 1

    def construct():
        if view.kind == "perm":
            left = list(range(n))
            sol = [0] * n
            for pos in rng.sample(range(n), n):
                idx = pick([tau[pos][it_] for it_ in left], rng)
                sol[pos] = left.pop(idx)
            return sol, [(pos, sol[pos]) for pos in range(n)]
        if view.kind == "bits":
            sol = [pick(tau[i], rng) for i in range(n)]
        else:
            sol = [pick(tau[i], rng) for i in range(n)]
        return view.fix(sol), None

    for it in range(1, p["max_iter"] + 1):
        ants = []
        for _ in range(m):
            sol, path = construct()
            ants.append((view.obj(sol), sol, path))
        ants.sort(key=lambda a: a[0])
        if ants[0][0] < gv:
            gv, gbest = ants[0][0], (ants[0][1])
        for row in tau:
            for k in range(len(row)):
                row[k] = max(t_min, row[k] * (1 - rho))
        for r in range(w):
            val, sol, path = ants[r]
            dep = (w - r) / w
            for i in range(n):
                tau[i][sol[i]] = min(t_max, tau[i][sol[i]] + dep)
        for i in range(n):
            tau[i][gbest[i]] = min(t_max, tau[i][gbest[i]] + 1.0)
        yield {"iter": it, "cur": sum(a[0] for a in ants) / m * view.sign}


def _mv_grasp(view, p, rng):
    """GRASP（Feo & Resende 1989），位向量版：贪心随机构造——从全 0 出发，每步在随机抽样的几个候选「加入某项」里按
    边际收益建受限候选表（RCL，α = 0.3），随机选一个加入，直到没有候选能再改进；然后做 1-翻转下降。
    候选抽样（而不是枚举全部）让每次构造的评价次数可控。"""
    n = view.n
    cand_n, alpha = min(8, n), 0.3
    for it in range(1, p["max_iter"] + 1):
        s = view.fix([0] * n)
        v = view.obj(s)
        steps = 0
        while steps < n // 2 + 2:
            steps += 1
            opts = []
            for i in rng.sample(range(n), cand_n):
                if s[i] == 0:
                    t = list(s)
                    t[i] = 1
                    t = view.fix(t)
                    opts.append((view.obj(t), t))
            if not opts:
                continue
            opts.sort(key=lambda o: o[0])
            lo_, hi_ = opts[0][0], opts[-1][0]
            rcl = [o for o in opts if o[0] <= lo_ + alpha * (hi_ - lo_)]
            pick_v, pick_t = rng.choice(rcl)
            if pick_v >= v:
                break
            s, v = pick_t, pick_v
        s, v = _mv_descent(view, s, v, rng, 10)
        yield {"iter": it, "cur": v * view.sign}


# 新补全的离散 / 局部搜索系内核：键 → (内核, 名称, 一句话说明, 适用的编码)
_NEW_GENERIC = {
    "ils": (_mv_ils, "迭代局部搜索 ILS", "扰动 → 采样下降 → 不变差就接受（Lourenço 等 2003）", ("perm", "bits", "assign", "real")),
    "vns": (_mv_vns, "变邻域搜索 VNS", "第 k 个邻域 = 随机移动 k 步，变好回 k = 1（Mladenović & Hansen 1997）", ("perm", "bits", "assign", "real")),
    "aco": (_mv_aco, "蚁群 ACO", "排序式 Ant System + 信息素上下界，决策图上逐步构造（只靠信息素，无专属启发式）", ("perm", "bits", "assign")),
    "grasp": (_mv_grasp, "GRASP", "抽样候选的贪心随机构造 + 1-翻转下降（Feo & Resende 1989）", ("bits",)),
}

# ============================================================
# 域一：0-1 背包（二进制编码）
# ============================================================

def ks_make(n=40, seed=7):
    """随机背包实例：cap 取总重的 45%，保证既装不满也留有取舍。"""
    rng = random.Random(seed)
    items = [(rng.randint(2, 60), rng.randint(10, 100)) for _ in range(n)]
    cap = int(sum(w for w, _ in items) * 0.45)
    return {"n": n, "cap": cap, "items": [[w, v] for w, v in items]}


class _KS:
    """背包域上下文：编码=0/1 向量，约束=超重必须修复。"""

    def __init__(self, problem):
        self.items = [tuple(x) for x in problem["items"]]
        self.cap = problem["cap"]
        self.n = problem["n"]

    def value(self, s):
        return sum(self.items[i][1] for i in range(self.n) if s[i])

    def weight(self, s):
        return sum(self.items[i][0] for i in range(self.n) if s[i])

    def repair(self, s):
        """贪心修复：超重时按「单位重量价值最低先扔」，这是约束背包的标准修复算子。"""
        s = list(s)
        total = self.weight(s)
        if total <= self.cap:
            return s
        idx = [i for i in range(self.n) if s[i]]
        idx.sort(key=lambda i: self.items[i][1] / max(1, self.items[i][0]))
        for i in idx:
            if total <= self.cap:
                break
            s[i] = 0
            total -= self.items[i][0]
        return s

    def random(self, rng):
        return self.repair([1 if rng.random() < 0.5 else 0 for _ in range(self.n)])

    def polish(self, s, rng, moves=10):
        """memetic 组件：随机单比特翻转爬山（小预算，模拟退火内也用）。"""
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

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(p["n_pop"])]
        return pop, [self.value(s) for s in pop]


def _ks_random(ctx, p, rng):
    best, bs = None, None  # 哨兵必须 None：负值景观（如 cmp/ssp 的 -罚）下 -1 会吞掉全部样本
    for it in range(1, p["max_iter"] + 1):
        s = ctx.random(rng)
        v = ctx.value(s)
        if bs is None or v > best:
            best, bs = v, list(s)
        yield {"iter": it, "best": best, "cur": v, "best_sol": bs}


def _ks_hc(ctx, p, rng):
    s = ctx.random(rng)
    best, bs = ctx.value(s), list(s)
    for it in range(1, p["max_iter"] + 1):
        for _ in range(p["tries"]):
            i = rng.randrange(ctx.n)
            cand = list(s)
            cand[i] ^= 1
            cand = ctx.repair(cand)
            v = ctx.value(cand)
            if v > ctx.value(s):
                s = cand
        best, bs = bump(best, bs, ctx.value(s), s)
        yield {"iter": it, "best": best, "cur": ctx.value(s), "best_sol": bs}


def _ks_sa(ctx, p, rng):
    s = ctx.random(rng)
    v = ctx.value(s)
    best, bs = v, list(s)
    t0, decay = p["t0"], p["decay"]
    for it in range(1, p["max_iter"] + 1):
        T = t0 * (decay ** it)
        i = rng.randrange(ctx.n)
        cand = list(s)
        cand[i] ^= 1
        cand = ctx.repair(cand)
        v2 = ctx.value(cand)
        d = v2 - v
        if d > 0 or (T > 1e-9 and rng.random() < math.exp(d / T)):
            s, v = cand, v2
        best, bs = bump(best, bs, v, s)
        yield {"iter": it, "best": best, "cur": v, "best_sol": bs}


def _ks_ga(ctx, p, rng):
    pop, vals = ctx.init_pop(p, rng)
    bi = argbest(vals)
    best, bs = vals[bi], list(pop[bi])
    for it in range(1, p["max_iter"] + 1):
        new = [list(pop[bi])]  # 精英保留
        while len(new) < p["n_pop"]:
            a, b = rng.sample(range(p["n_pop"]), 2)
            pa, pb = pop[a], pop[b]
            child = bits_uniform(pa, pb, rng)  # 均匀交叉
            bits_mutate(child, p["pm"], rng)
            child = ctx.repair(child)
            new.append(child)
        pop = new
        vals = [ctx.value(s) for s in pop]
        bi = argbest(vals)
        best, bs = bump(best, bs, vals[bi], pop[bi])
        yield {"iter": it, "best": best, "cur": max(vals), "best_sol": bs}


def _ks_de(ctx, p, rng):
    """二进制差分：差向量 = r2/r3 不同的位（排列域思想在 0/1 域的等价物）。"""
    pop, vals = ctx.init_pop(p, rng)
    bi = argbest(vals)
    best, bs = vals[bi], list(pop[bi])
    for it in range(1, p["max_iter"] + 1):
        for i in range(p["n_pop"]):
            r1, r2, r3 = rng.sample([j for j in range(p["n_pop"]) if j != i], 3)
            mutant = list(pop[r1])
            for k in range(ctx.n):
                if pop[r2][k] != pop[r3][k] and rng.random() < p["F"]:
                    mutant[k] = pop[r2][k]
            trial = [mutant[k] if rng.random() < p["CR"] else pop[i][k] for k in range(ctx.n)]
            trial = ctx.repair(trial)
            v = ctx.value(trial)
            if v >= vals[i]:  # DE 贪心选择
                pop[i], vals[i] = trial, v
                best, bs = bump(best, bs, v, trial)
        yield {"iter": it, "best": best, "cur": max(vals), "best_sol": bs}


def _ks_ts(ctx, p, rng):
    """禁忌搜索（二进制邻域）：每步在全部单翻转里选最好的非禁忌移动。"""
    s = ctx.random(rng)
    v = ctx.value(s)
    best, bs = v, list(s)
    tabu = {}
    tenure = p["tenure"]
    for it in range(1, p["max_iter"] + 1):
        best_move, best_v, best_i = None, -1, -1
        for i in range(ctx.n):
            if tabu.get(i, -1) >= it:
                continue
            cand = list(s)
            cand[i] ^= 1
            cand = ctx.repair(cand)
            vv = ctx.value(cand)
            if vv > best_v:
                best_v, best_move, best_i = vv, cand, i
        if best_move is None:
            s = ctx.random(rng)
            v = ctx.value(s)
        else:
            s, v = best_move, best_v
            tabu[best_i] = it + tenure
        best, bs = bump(best, bs, v, s)
        yield {"iter": it, "best": best, "cur": v, "best_sol": bs}


def _ks_abc(ctx, p, rng):
    pop, vals = ctx.init_pop(p, rng)
    stuck = [0] * p["n_pop"]
    bi = argbest(vals)
    best, bs = vals[bi], list(pop[bi])
    for it in range(1, p["max_iter"] + 1):
        for phase in range(2):  # 雇佣蜂 + 观察蜂
            for i in range(p["n_pop"]):
                k = 1 if rng.random() < 0.8 else 2
                cand = bits_flip(pop[i], rng, k)
                cand = ctx.repair(cand)
                v = ctx.value(cand)
                if v > vals[i]:
                    pop[i], vals[i], stuck[i] = cand, v, 0
                else:
                    stuck[i] += 1
            if phase == 1:  # 观察蜂按收益轮盘
                lo, hi = min(vals), max(vals)
                w = [(v - lo + 1e-9) for v in vals]
                tot = sum(w) or 1.0
                for _ in range(p["n_pop"]):
                    r, acc = rng.random() * tot, 0.0
                    for i in range(p["n_pop"]):
                        acc += w[i]
                        if acc >= r:
                            break
                    cand = bits_flip(pop[i], rng, 1 if rng.random() < 0.8 else 2)
                    cand = ctx.repair(cand)
                    v = ctx.value(cand)
                    if v > vals[i]:
                        pop[i], vals[i], stuck[i] = cand, v, 0
        for i in range(p["n_pop"]):  # 侦察蜂
            if stuck[i] > p["limit"]:
                pop[i], vals[i], stuck[i] = ctx.random(rng), 0, 0
                vals[i] = ctx.value(pop[i])
        bi = argbest(vals)
        best, bs = bump(best, bs, vals[bi], pop[bi])
        yield {"iter": it, "best": best, "cur": max(vals), "best_sol": bs}


def _ks_woa(ctx, p, rng):
    """二进制鲸鱼：包围 = 按收缩比例抄最优解的位；螺旋 = 抄随机同伴。"""
    pop, vals = ctx.init_pop(p, rng)
    bi = argbest(vals)
    best, bs = vals[bi], list(pop[bi])
    for it in range(1, p["max_iter"] + 1):
        a = 2.0 * (1 - it / p["max_iter"])  # 线性收缩
        for i in range(p["n_pop"]):
            ratio = max(0.1, min(0.9, abs(2 * a * rng.random() - a)))
            if rng.random() < 0.5:  # 包围：偏向最优
                src, prob = pop[bi], 1.0 - ratio * 0.5
                cand = [src[k] if rng.random() < prob else rng.randint(0, 1) for k in range(ctx.n)]
            else:  # 螺旋：向随机同伴学习
                src = pop[rng.randrange(p["n_pop"])]
                cand = [src[k] if rng.random() < 0.5 else pop[i][k] for k in range(ctx.n)]
            cand = ctx.repair(cand)
            cand = ctx.polish(cand, rng, 3)
            v = ctx.value(cand)
            if greedy_replace(pop, vals, i, cand, v):
                best, bs = bump(best, bs, v, cand)
        yield {"iter": it, "best": best, "cur": max(vals), "best_sol": bs}


def _ks_gwo(ctx, p, rng):
    """二进制灰狼：α/β/δ 三头狼逐位投票（bGWO 的 majority 思想）+ 递减随机翻转。"""
    pop, vals = ctx.init_pop(p, rng)
    order = sorted(range(p["n_pop"]), key=lambda i: vals[i], reverse=True)
    al, be, de = pop[order[0]], pop[order[1]], pop[order[2]]
    best, bs = vals[order[0]], list(pop[order[0]])
    for it in range(1, p["max_iter"] + 1):
        a = 2.0 * (1 - it / p["max_iter"])
        for i in range(p["n_pop"]):
            cand = []
            for k in range(ctx.n):
                votes = al[k] + be[k] + de[k]
                bit = 1 if votes >= 2 else 0
                if rng.random() < 0.15 * a:  # 后期随机翻转减少 → 收缩
                    bit ^= 1
                cand.append(bit)
            cand = ctx.repair(cand)
            cand = ctx.polish(cand, rng, 3)
            v = ctx.value(cand)
            if greedy_replace(pop, vals, i, cand, v):
                best, bs = bump(best, bs, v, cand)
        order = sorted(range(p["n_pop"]), key=lambda i: vals[i], reverse=True)
        al, be, de = pop[order[0]], pop[order[1]], pop[order[2]]
        yield {"iter": it, "best": best, "cur": max(vals), "best_sol": bs}


def _ks_cs(ctx, p, rng):
    """布谷鸟（二进制，种群版）：新蛋 = 从最优巢出发做莱维翻转（标准 CS 以 best 为中心）。"""
    pop, vals = ctx.init_pop(p, rng)
    bi = argbest(vals)
    best, bs = vals[bi], list(pop[bi])
    for it in range(1, p["max_iter"] + 1):
        for i in range(p["n_pop"]):
            levy = rng.paretovariate(1.5)
            k = max(1, min(ctx.n - 1, int(ctx.n * 0.12 * levy)))
            base = pop[bi] if rng.random() < 0.6 else pop[i]  # 偏向最优巢的莱维游走
            cand = list(base)
            for _ in range(k):
                cand[rng.randrange(ctx.n)] ^= 1
            cand = ctx.repair(cand)
            v2 = ctx.value(cand)
            if greedy_replace(pop, vals, i, cand, v2):
                best, bs = bump(best, bs, v2, cand)
        for i in range(p["n_pop"]):  # 弃巢重建
            if rng.random() < p["pa"]:
                pop[i], vals[i] = ctx.random(rng), 0
                vals[i] = ctx.value(pop[i])
        bi = argbest(vals)
        best, bs = bump(best, bs, vals[bi], pop[bi])
        yield {"iter": it, "best": best, "cur": max(vals), "best_sol": bs}



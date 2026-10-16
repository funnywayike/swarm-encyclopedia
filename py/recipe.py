# -*- coding: utf-8 -*-
"""S7-B 配方引擎：算法 = 七槽管线模块组合（L-recipe 层）。

设计（docs/component-architecture.md §3）：
  七槽固定管线 init→selection→crossover→mutation→replacement→local_search→terminator，
  每槽从 RCOMPONENTS 挑一个组件；配方 = JSON 声明。组合引擎用单一 RNG 顺序调用
  组件（组件禁自建随机源），任意配方可复现。

双模式：
  population —— 种群型（GA/Memetic 类）：选择→交叉→变异→替换逐代滚动
  single     —— 单解型（ILS 类）：扰动→局部搜索→贪心接受

IO 契约（自检线）：排列组件的输出用 _assert_perm 校验（无重复、长度一致），
非法组合在第一代就炸出来，不让坏配方悄悄跑完。

组件尽量直接复用 py/components.py 的函数（单一实现）：
  nearest_neighbor / _ox_crossover / _reverse_mutation / _or_opt_move /
  _double_bridge / two_opt_improve / _random_2opt_shot / _roulette / tour_length
"""
import json
import random
from dataclasses import asdict
from typing import Any, Dict, Iterator, List, Optional

try:  # 与 solvers.py 同款双环境兼容：本地 import / 拼接名字空间直用
    from components import (  # noqa: F401
        _double_bridge, _or_opt_move, _ox_crossover, _random_2opt_shot,
        _reverse_mutation, _roulette, nearest_neighbor, tour_length,
        two_opt_improve,
    )
except ImportError:
    pass


# ============================ IO 契约 ============================

def _assert_perm(t: List[int], n: int, where: str) -> None:
    """排列合法性校验：长度一致 + 无重复。配方引擎的 IO 门。"""
    if len(t) != n or len(set(t)) != n:
        raise ValueError(f"配方 IO 契约失败[{where}]：期望 {n} 城排列，"
                         f"实际长度 {len(t)}、去重 {len(set(t))}")


# ============================ 槽位组件（TSP 排列域） ============================

# ---- init：返回初始种群（含成本） ----
def _init_random(n, D, pop, rng):
    P = [list(range(n)) for _ in range(pop)]
    for t in P:
        rng.shuffle(t)
    return P

def _init_nn(n, D, pop, rng):
    """多起点最近邻播种（与 GA/GWO 手写版同一工程共识：纯随机开局浪费几十代）。"""
    starts = list(range(n))
    rng.shuffle(starts)
    return [nearest_neighbor(D, starts[i % n]) for i in range(pop)]

# ---- selection：从种群选一个父代下标 ----
def _sel_tournament(costs, rng, k):
    idx = rng.sample(range(len(costs)), min(k, len(costs)))
    return min(idx, key=lambda i: costs[i])

def _sel_roulette(costs, rng, k=3):
    """成本转权重（最小化）：1/(1+cost-rmin)，保证全正。k 参数与锦标赛签名对齐、忽略。"""
    rmin = min(costs)
    w = [1.0 / (1.0 + c - rmin) for c in costs]
    return _roulette(rng, w)

# ---- crossover ----
def _cx_ox(p1, p2, rng):
    return _ox_crossover(p1, p2, rng)

# ---- mutation ----
def _mut_reverse(t, rng, pm):
    if rng.random() < pm:
        return _reverse_mutation(t, rng)
    return t

def _mut_swap(t, rng, pm):
    if rng.random() < pm:
        i, j = rng.randrange(len(t)), rng.randrange(len(t))
        t = list(t)
        t[i], t[j] = t[j], t[i]
    return t

def _mut_oropt(t, rng, pm):
    if rng.random() < pm:
        return _or_opt_move(t, rng, rng.choice([1, 2, 3]))
    return t

def _mut_dbridge(t, rng, pm):
    if rng.random() < pm:
        return _double_bridge(t, rng)
    return t

# ---- replacement ----
def _rep_generational(pop, costs, new, newc, elite):
    """精英世代替换：新代保底 elite 个父代最优，其余用子代填。"""
    order = sorted(range(len(pop)), key=lambda i: costs[i])
    for e in order[:elite]:
        new.append(list(pop[e]))
        newc.append(costs[e])
    return new[:len(pop)], newc[:len(pop)]

def _rep_greedy_one(cur, curc, cand, candc):
    """单解贪心接受（ILS 的 replacement 槽）。"""
    return (list(cand), candc) if candc < curc else (cur, curc)

# ---- local_search（统一签名 tour, D, rng, budget；不用 rng 的忽略之） ----
def _ls_two_opt(tour, D, rng, budget):
    return two_opt_improve(tour, D, max_moves=budget)

def _ls_shot(tour, D, rng, trials):
    return _random_2opt_shot(tour, D, rng, trials=trials)

# ---- terminator：返回 True 表示该停 ----
def _term_stall(cur_best, hist_best, stall, patience):
    return stall >= patience if patience > 0 else False


# ============================ S7-D：F6-F9 升格专用组件 ============================

# 选择式超启发式的低层启发式档案（信用轮盘的选择池）
_HH_LLHS = ("reverse", "swap", "oropt")


def _mut_hh(t, rng, pm, ctx):
    """选择式超启发式（selection hyper-heuristic）变异槽：
    信用轮盘在三个低层启发式之间选——「选哪个算子」本身成为搜索问题。
    信用分存引擎下发的 ctx（跨代状态口袋），经 feedback 钩子回注改进量。"""
    if rng.random() >= pm:
        return t
    scores = ctx.setdefault("hh_scores", {k: 1.0 for k in _HH_LLHS})
    name = _HH_LLHS[_roulette(rng, [scores[k] for k in _HH_LLHS])]
    ctx["hh_last"] = name
    if name == "reverse":
        return _reverse_mutation(t, rng)
    if name == "swap":
        i, j = rng.randrange(len(t)), rng.randrange(len(t))
        t = list(t)
        t[i], t[j] = t[j], t[i]
        return t
    return _or_opt_move(t, rng, rng.choice([1, 2, 3]))


def _fb_hh(ctx, delta):
    """HH 信用分配：全体轻微衰减 + 改进算子按 Δ 加分（封顶防数值爆炸）。"""
    scores = ctx.get("hh_scores")
    if not scores or "hh_last" not in ctx:
        return
    for k in scores:
        scores[k] *= 0.97
    if delta > 0:
        scores[ctx["hh_last"]] += min(delta, 50.0)


def _hk_window(D, a, seg, b):
    """窗口 Held-Karp DP：两端固定（a 进 b 出），窗口内城市精确最优重排。
    O(k²·2^k)，k=11 约 25 万次内层运算——matheuristic 的「精确修复」内核。"""
    k = len(seg)
    INF = float("inf")
    size = 1 << k
    dp = [[INF] * k for _ in range(size)]
    par = [[-1] * k for _ in range(size)]
    for i in range(k):
        dp[1 << i][i] = D[a][seg[i]]
    for mask in range(1, size):
        row = dp[mask]
        for j in range(k):
            cj = row[j]
            if cj == INF or not (mask >> j & 1):
                continue
            for l in range(k):
                if mask >> l & 1:
                    continue
                nm = mask | (1 << l)
                nc = cj + D[seg[j]][seg[l]]
                if nc < dp[nm][l]:
                    dp[nm][l] = nc
                    par[nm][l] = j
    full = size - 1
    end = min(range(k), key=lambda j: dp[full][j] + D[seg[j]][b])
    order = []
    mask, cur = full, end
    while cur != -1:
        order.append(seg[cur])
        nxt = par[mask][cur]
        mask ^= 1 << cur
        cur = nxt
    order.reverse()
    return order


def _ls_fixopt(tour, D, rng, budget):
    """fix-and-optimize（matheuristic 文献记载范式）：采样至多 budget 个 k=11
    连续窗口，Held-Karp 精确重排，采纳最优改进；无改进返回原路。"""
    n = len(tour)
    k = min(11, n - 3)
    if k < 4:
        return tour
    best_t, best_c = tour, tour_length(tour, D)
    for _ in range(max(1, budget)):
        p0 = rng.randrange(n)
        seg = [tour[(p0 + i) % n] for i in range(k)]
        a = tour[(p0 - 1) % n]
        b = tour[(p0 + k) % n]
        new_seg = _hk_window(D, a, seg, b)
        cand = list(tour)
        for i in range(k):
            cand[(p0 + i) % n] = new_seg[i]
        c = tour_length(cand, D)
        if c < best_c - 1e-9:
            best_t, best_c = cand, c
    return best_t


def _rbf_predict(archive, t, kmax=12):
    """教学版代理模型：按「城市位置向量」距离取近邻，距离倒数加权预测成本。
    SAEA 里代理只负责排名（预筛），精确评估永远以 tour_length 为准。"""
    if not archive:
        return float("inf")
    pos_t = {c: i for i, c in enumerate(t)}
    ds = []
    for perm, cost in archive:
        pos_p = {c: i for i, c in enumerate(perm)}
        d2 = 0
        for c, i in pos_t.items():
            di = i - pos_p[c]
            d2 += di * di
        ds.append((d2, cost))
    ds.sort(key=lambda x: x[0])
    num = den = 0.0
    for d2, cost in ds[:kmax]:
        if d2 == 0:
            return cost
        w = 1.0 / (d2 + 1.0)
        num += w * cost
        den += w
    return num / den


RCOMPONENTS: Dict[str, Dict[str, Any]] = {
    # 每个组件：call（引擎调用签名）、kind、io 描述、正典出处、纯组件标记
    "random":     {"kind": "init", "io": "->perm_pop", "fn": _init_random,
                   "source": "教科书标准", "composable": False},
    "nn_seeding": {"kind": "init", "io": "->perm_pop", "fn": _init_nn,
                   "source": "Rosenkrantz 1977（NN 构造 2-近似）", "composable": False},
    "tournament": {"kind": "selection", "io": "pop->idx", "fn": _sel_tournament,
                   "source": "Goldberg & Deb 1991", "composable": False},
    "roulette":   {"kind": "selection", "io": "pop->idx", "fn": _sel_roulette,
                   "source": "Holland 1975", "composable": False},
    "ox":         {"kind": "crossover", "io": "perm×2->perm", "fn": _cx_ox,
                   "source": "Goldberg 1985", "composable": False},
    "none_cross": {"kind": "crossover", "io": "perm->perm", "fn": None,
                   "source": "无交叉（单亲/单解型）", "composable": False},
    "reverse_mut": {"kind": "mutation", "io": "perm->perm", "fn": _mut_reverse,
                    "source": "逆转变异（排列 GA 标准）", "composable": False},
    "swap_mut":   {"kind": "mutation", "io": "perm->perm", "fn": _mut_swap,
                   "source": "交换变异", "composable": False},
    "oropt_mut":  {"kind": "mutation", "io": "perm->perm", "fn": _mut_oropt,
                   "source": "Or 1976（移段邻域）", "composable": False},
    "double_bridge": {"kind": "mutation", "io": "perm->perm", "fn": _mut_dbridge,
                      "source": "Martin & Otto 1991（ILS 标准扰动）", "composable": False},
    "generational": {"kind": "replacement", "io": "pop+new->pop", "fn": _rep_generational,
                     "source": "世代式 + 精英保留（De Jong 1975）", "composable": False},
    "greedy_accept": {"kind": "replacement", "io": "2sol->1sol", "fn": _rep_greedy_one,
                      "source": "ILS 接受准则", "composable": False},
    "two_opt":    {"kind": "local_search", "io": "perm->perm", "fn": _ls_two_opt,
                   "source": "Croes 1958", "composable": False},
    "two_opt_shot": {"kind": "local_search", "io": "perm->perm", "fn": _ls_shot,
                     "source": "预算制试射（本站命名）", "composable": False},
    "hh_choice":  {"kind": "mutation", "io": "perm->perm", "fn": _mut_hh,
                    "feedback": _fb_hh, "ctx": True,
                    "source": "选择式超启发式（Cowling 2001 信用分配传统）",
                    "composable": False},
    "fixopt":     {"kind": "local_search", "io": "perm->perm", "fn": _ls_fixopt,
                    "source": "fix-and-optimize 精确修复（Held-Karp DP 窗口）",
                    "composable": False},
    "stall":      {"kind": "terminator", "io": "hist->bool", "fn": _term_stall,
                   "source": "无改进停机", "composable": False},
    "max_iter":   {"kind": "terminator", "io": "->bool", "fn": None,
                   "source": "固定预算", "composable": False},
}
# fn=None 的组件由引擎内联实现（签名特殊），kind/io/source 元数据仍然成立


# ============================ 示范配方（L-recipe 数据） ============================

RECIPES: List[Dict[str, Any]] = [
    {
        "id": "memetic",
        "name": "Memetic GA（组合）",
        "mode": "population",
        "lineage": {"family": "F6", "based_on": "ga-tsp",
                    "source": "Moscato 1989（文化基因算法）"},
        "slots": {
            "init": "nn_seeding", "selection": "tournament", "crossover": "ox",
            "mutation": "reverse_mut", "replacement": "generational",
            "local_search": "two_opt", "terminator": "stall",
        },
        "default_params": {"pop": 60, "pc": 0.85, "pm": 0.20, "max_iter": 300,
                           "elite": 2, "tournament": 3, "ls_every": 5,
                           "ls_moves": 15, "patience": 80, "seed": 42},
        "note": "与手写 ga-tsp（ls_every>0 时）同谱系——本配方证明七槽管线能表达 memetic 结构。",
    },
    {
        "id": "steady-ga",
        "name": "稳态 GA（组合）",
        "mode": "population",
        "lineage": {"family": "F1", "based_on": "ga-tsp",
                    "source": "Syswerda 1989（稳态替换）"},
        "slots": {
            "init": "random", "selection": "roulette", "crossover": "ox",
            "mutation": "swap_mut", "replacement": "generational",
            "local_search": "two_opt_shot", "terminator": "max_iter",
        },
        "default_params": {"pop": 50, "pc": 0.9, "pm": 0.15, "max_iter": 200,
                           "elite": 1, "tournament": 3, "ls_every": 10,
                           "ls_moves": 8, "patience": 0, "seed": 42},
        "note": "轮盘选择 + 交换变异 + 稀疏局部搜索——与 Memetic 配方同一引擎、不同模块清单的教学对照。",
    },
    {
        "id": "ils",
        "name": "迭代局部搜索 ILS（组合）",
        "mode": "single",
        "lineage": {"family": "F6", "based_on": "sa-tsp",
                    "source": "Martin & Otto 1991 / Lourenço 2003 经典综述"},
        "slots": {
            "init": "nn_seeding", "selection": "none", "crossover": "none_cross",
            "mutation": "double_bridge", "replacement": "greedy_accept",
            "local_search": "two_opt", "terminator": "stall",
        },
        "default_params": {"max_iter": 300, "pm": 1.0,
                           "ls_moves": 120, "patience": 150, "seed": 42},
        "note": "selection/crossover 槽在单解模式下自然闲置——七槽管线覆盖单解谱系的方式。",
    },
    {
        "id": "hh",
        "name": "选择式超启发式（组合）",
        "mode": "population",
        "lineage": {"family": "F6", "based_on": "ga-tsp",
                    "source": "Cowling 2001 传统（选择式超启发式）"},
        "slots": {
            "init": "nn_seeding", "selection": "tournament", "crossover": "ox",
            "mutation": "hh_choice", "replacement": "generational",
            "local_search": "two_opt", "terminator": "stall",
        },
        "default_params": {"pop": 50, "pc": 0.85, "pm": 0.90, "max_iter": 300,
                           "elite": 2, "tournament": 3, "ls_every": 5,
                           "ls_moves": 15, "patience": 80, "seed": 42},
        "note": "不设计新算子，而是让信用轮盘在逆转/交换/Or-opt 三个低层启发式之间做选择——"
                "「选哪个算子」本身成为搜索问题；信用 = 近期改进量，引擎经 feedback 钩子回注。"
                "局部搜索槽保留稀疏的 2-opt 试射周期（ls_every=5），对应超启发式管「选算子」、"
                "局部搜索管「打磨」的分工结构。",
    },
    {
        "id": "saea",
        "name": "代理辅助进化 SAEA（组合）",
        "mode": "sa",
        "lineage": {"family": "F6", "based_on": "ga-tsp",
                    "source": "代理模型辅助进化脉络）"},
        "slots": {
            "init": "random", "selection": "tournament", "crossover": "ox",
            "mutation": "reverse_mut", "replacement": "none",
            "local_search": "none", "terminator": "stall",
        },
        "default_params": {"pop": 40, "pc": 0.8, "pm": 0.20, "max_iter": 150,
                           "elite": 2, "tournament": 3, "eval_budget": 6,
                           "patience": 60, "seed": 42},
        "note": "SAEA 教学演示：TSP 的评估本来便宜，此处人为把每代精确评估限制为预测最优的前 "
                "eval_budget 个（其余由 RBF 代理模型预筛排名后丢弃）——机制与昂贵黑箱优化中的 "
                "SAEA 一致；最优只按精确评估更新。初始种群用随机初始化（不用 NN 播种）："
                "昂贵优化里往往没有廉价好解可捡，随机开局更贴近 SAEA 的真实使用场景。",
    },
    {
        "id": "matheur",
        "name": "Fix-and-Optimize（组合）",
        "mode": "single",
        "lineage": {"family": "F6", "based_on": "ils",
                    "source": "fix-and-optimize（Boschetti 与 Maniezzo 2024 经典综述）"},
        "slots": {
            "init": "nn_seeding", "selection": "none", "crossover": "none_cross",
            "mutation": "oropt_mut", "replacement": "greedy_accept",
            "local_search": "fixopt", "terminator": "stall",
        },
        "default_params": {"max_iter": 200, "pm": 1.0,
                           "ls_moves": 3, "patience": 60, "seed": 42},
        "note": "or-opt 移动做破坏（LNS 式），局部搜索槽用 Held-Karp 动态规划对随机窗口做精确重排"
                "——精确修复是 matheuristic 方法树（VLSN/CMSA/Kernel Search）里文献记载的范式；"
                "窗口 k=11 固定（DP 成本封顶，Pyodide 可交互），ls_moves = 每代采样窗口数。",
    },
    {
        "id": "mapelites",
        "name": "MAP-Elites QD（组合）",
        "mode": "qd",
        "lineage": {"family": "F8", "based_on": "ils",
                    "source": "Mouret 与 Clune 2015（MAP-Elites）"},
        "slots": {
            "init": "nn_seeding", "selection": "none", "crossover": "none_cross",
            "mutation": "double_bridge", "replacement": "none",
            "local_search": "two_opt", "terminator": "stall",
        },
        "default_params": {"pop": 40, "pm": 1.0, "max_iter": 300, "grid_res": 8,
                           "ls_moves": 60, "patience": 120, "seed": 42},
        "note": "不求单一最优，求「每个行为格子的最优」：行为描述子 = (边长均值, 最长边)，"
                "紧致度 × 跳跃度两维刻画路径形态；默认 8×8 档案格，双桥扰动 + 2-opt 回灌，"
                "收敛曲线 = 档案全局最优。档案稀疏占据是 QD 常态（好解形态本就近似）。",
    },
]


# ============================ 组合引擎 ============================

def _lookup(recipe: Dict, slot: str):
    rid = recipe["slots"].get(slot)
    if rid is None or rid in ("none",):
        return None
    if rid not in RCOMPONENTS:
        raise ValueError(f"配方 {recipe['id']}：槽位 {slot} 引用未知组件 {rid}")
    return RCOMPONENTS[rid]


def run_recipe(recipe: Dict, problem: Dict, params: Dict) -> Iterator:
    """七槽管线解释器。yield 与 BaseSolver 相同的 IterationState 字典——前端零改动。"""
    rng = random.Random(params.get("seed", 42))
    n, D = problem["n"], problem["D"]
    mode = recipe["mode"]
    cfg = recipe["slots"]
    _ = [_lookup(recipe, s) for s in cfg]  # 装配期校验：未知组件当场炸

    p = dict(recipe["default_params"])
    p.update(params)

    hist_best: Optional[float] = None
    stall = 0
    ctx: Dict[str, Any] = {}  # S7-D：组件跨代状态口袋（HH 信用分等），引擎统一下发

    if mode == "population":
        pop = _lookup(recipe, "init")["fn"](n, D, p["pop"], rng)
        for t in pop:
            _assert_perm(t, n, "init")
        costs = [tour_length(t, D) for t in pop]
        best, bc = min(zip(pop, costs), key=lambda x: x[1])
        best, bc = list(best), bc
        yield {"iteration": 0, "best_cost": bc, "best_tour": best,
               "current_cost": sum(costs) / len(costs), "extra": {}}

        sel, cx, mut, rep, ls = (_lookup(recipe, "selection"), _lookup(recipe, "crossover"),
                                 _lookup(recipe, "mutation"), _lookup(recipe, "replacement"),
                                 _lookup(recipe, "local_search"))
        for it in range(1, p["max_iter"] + 1):
            new, newc = [], []
            while len(new) < p["pop"] - p["elite"]:
                i1 = sel["fn"](costs, rng, p["tournament"])
                i2 = sel["fn"](costs, rng, p["tournament"])
                if cx["fn"] is not None and rng.random() < p["pc"]:
                    child = cx["fn"](pop[i1], pop[i2], rng)
                else:
                    child = list(pop[i1])
                if mut.get("ctx"):  # S7-D：声明 ctx 的组件多收一个状态口袋
                    child = mut["fn"](child, rng, p["pm"], ctx)
                else:
                    child = mut["fn"](child, rng, p["pm"])
                _assert_perm(child, n, f"mutation@it{it}")
                new.append(child)
                newc.append(tour_length(child, D))
                if "feedback" in mut:  # S7-D：信用分配反馈（选择式超启发式）
                    mut["feedback"](ctx, min(costs[i1], costs[i2]) - newc[-1])
            pop, costs = rep["fn"](pop, costs, new, newc, p["elite"])
            # local_search 槽：每 ls_every 代对全局最优做一次下探并回灌
            if ls is not None and p["ls_every"] > 0 and it % p["ls_every"] == 0:
                bi = min(range(len(pop)), key=lambda i: costs[i])
                improved = ls["fn"](pop[bi], D, rng, p["ls_moves"])
                c2 = tour_length(improved, D)
                if c2 < costs[bi]:
                    pop[bi], costs[bi] = improved, c2
            cur_best = min(costs)
            if cur_best < bc:
                bi = costs.index(cur_best)
                best, bc = list(pop[bi]), cur_best
                stall = 0
            else:
                stall += 1
            term = _lookup(recipe, "terminator")
            yield {"iteration": it, "best_cost": bc, "best_tour": best,
                   "current_cost": sum(costs) / len(costs), "extra": {}}
            if term["kind"] == "terminator" and term["io"] == "hist->bool" and \
               _term_stall(cur_best, hist_best, stall, p["patience"]):
                break
            hist_best = cur_best

    elif mode == "sa":
        # S7-D SAEA mode：代理模型预筛 + 精确评估预算。每代只付 eval_budget 次
        # tour_length（昂贵评估的模拟，页面如实标注），其余子代由 RBF 代理排名后丢弃。
        pop = _lookup(recipe, "init")["fn"](n, D, p["pop"], rng)
        for t in pop:
            _assert_perm(t, n, "init")
        costs = [tour_length(t, D) for t in pop]
        archive = [(list(t), c) for t, c in zip(pop, costs)]  # 精确评估档案
        best, bc = min(zip(pop, costs), key=lambda x: x[1])
        best, bc = list(best), bc
        n_evals = len(pop)
        yield {"iteration": 0, "best_cost": bc, "best_tour": best,
               "current_cost": sum(costs) / len(costs), "extra": {"sa_evals": n_evals}}
        sel, cx, mut = (_lookup(recipe, "selection"), _lookup(recipe, "crossover"),
                        _lookup(recipe, "mutation"))
        eb, cap = p["eval_budget"], 240
        for it in range(1, p["max_iter"] + 1):
            cands = []
            while len(cands) < p["pop"]:
                i1 = sel["fn"](costs, rng, p["tournament"])
                i2 = sel["fn"](costs, rng, p["tournament"])
                if cx["fn"] is not None and rng.random() < p["pc"]:
                    child = cx["fn"](pop[i1], pop[i2], rng)
                else:
                    child = list(pop[i1])
                child = mut["fn"](child, rng, p["pm"])
                _assert_perm(child, n, f"mutation@it{it}")
                cands.append(child)
            ranked = sorted(range(len(cands)), key=lambda i: _rbf_predict(archive, cands[i]))
            new, newc = [], []
            for i in ranked[:eb]:
                c = tour_length(cands[i], D)  # 精确评估只发生在这一行
                archive.append((list(cands[i]), c))
                new.append(cands[i])
                newc.append(c)
            n_evals += len(new)
            if len(archive) > cap:  # 档案上限：随机保留（rng 驱动，可复现）
                keep = sorted(rng.sample(range(len(archive)), cap))
                archive = [archive[j] for j in keep]
            # 替换 = 精英保留 + 已评估子代 + 未评估槽位由父代填充（代理不进替换）
            order = sorted(range(len(pop)), key=lambda i: costs[i])
            fill = [rng.randrange(len(pop)) for _ in range(p["pop"] - p["elite"] - len(new))]
            pop = [list(pop[i]) for i in order[:p["elite"]]] + new + [list(pop[i]) for i in fill]
            costs = [costs[i] for i in order[:p["elite"]]] + newc + [costs[i] for i in fill]
            cur_best = min(costs)
            if cur_best < bc:
                bi = costs.index(cur_best)
                best, bc = list(pop[bi]), cur_best
                stall = 0
            else:
                stall += 1
            yield {"iteration": it, "best_cost": bc, "best_tour": best,
                   "current_cost": sum(costs) / len(costs), "extra": {"sa_evals": n_evals}}
            term = _lookup(recipe, "terminator")
            if term["kind"] == "terminator" and term["io"] == "hist->bool" and \
               _term_stall(cur_best, hist_best, stall, p["patience"]):
                break
            hist_best = cur_best

    elif mode == "qd":
        # S7-D QD mode：MAP-Elites——行为描述子分格档案，每格留精英，
        # 求「每个行为格子的最优」而非单一最优。
        # 行为描述子 = (边长均值, 最长边)：紧致度 × 跳跃度两维刻画路径形态，
        # 与适应度（总长）正交；网格按距离矩阵全域 [dmin,dmax] × [0,dmax] 划分。
        dmin = min(D[i][j] for i in range(n) for j in range(i + 1, n))
        dmax = max(D[i][j] for i in range(n) for j in range(i + 1, n))
        res = p["grid_res"]

        def _cell_of(x, y):
            cx = int((x - dmin) / (dmax - dmin + 1e-9) * res)
            cy = int(y / (dmax + 1e-9) * res)
            return (min(max(cx, 0), res - 1), min(max(cy, 0), res - 1))

        def _bd(tour):
            es = [D[tour[i]][tour[(i + 1) % n]] for i in range(n)]
            return sum(es) / n, max(es)

        pop0 = _lookup(recipe, "init")["fn"](n, D, p["pop"], rng)
        grid: Dict[Any, List[Any]] = {}
        for t in pop0:
            _assert_perm(t, n, "init")
            x, y = _bd(t)
            cell = _cell_of(x, y)
            c = tour_length(t, D)
            if cell not in grid or c < grid[cell][1]:
                grid[cell] = [list(t), c]
        cells = list(grid.keys())
        bc = min(v[1] for v in grid.values())
        best = list(next(v[0] for v in grid.values() if v[1] == bc))
        yield {"iteration": 0, "best_cost": bc, "best_tour": best,
               "current_cost": bc, "extra": {"qd_cells": len(cells)}}
        mut, ls = _lookup(recipe, "mutation"), _lookup(recipe, "local_search")
        for it in range(1, p["max_iter"] + 1):
            src = grid[cells[rng.randrange(len(cells))]]
            cand = mut["fn"](list(src[0]), rng, p["pm"])  # 双桥扰动
            _assert_perm(cand, n, f"perturb@it{it}")
            if ls is not None:
                cand = ls["fn"](cand, D, rng, p["ls_moves"])
            x, y = _bd(cand)
            cell = _cell_of(x, y)
            c = tour_length(cand, D)
            if cell not in grid or c < grid[cell][1]:  # 回灌：占新格或击败格内精英
                grid[cell] = [cand, c]
                if cell not in cells:
                    cells.append(cell)
            cur_best = min(v[1] for v in grid.values())
            if cur_best < bc:
                bc = cur_best
                best = list(next(v[0] for v in grid.values() if v[1] == bc))
                stall = 0
            else:
                stall += 1
            yield {"iteration": it, "best_cost": bc, "best_tour": best,
                   "current_cost": c, "extra": {"qd_cells": len(cells)}}
            if stall >= p["patience"]:
                break

    else:  # single（ILS）
        cur = _lookup(recipe, "init")["fn"](n, D, 1, rng)[0]
        _assert_perm(cur, n, "init")
        cc = tour_length(cur, D)
        best, bc = list(cur), cc
        mut, ls, rep = (_lookup(recipe, "mutation"), _lookup(recipe, "local_search"),
                        _lookup(recipe, "replacement"))
        yield {"iteration": 0, "best_cost": bc, "best_tour": best,
               "current_cost": cc, "extra": {}}
        for it in range(1, p["max_iter"] + 1):
            cand = mut["fn"](list(cur), rng, p["pm"])  # double_bridge 深扰动
            _assert_perm(cand, n, f"perturb@it{it}")
            if ls is not None:
                cand = ls["fn"](cand, D, rng, p["ls_moves"])
            candc = tour_length(cand, D)
            cur, cc = rep["fn"](cur, cc, cand, candc)
            if cc < bc:
                best, bc = list(cur), cc
                stall = 0
            else:
                stall += 1
            yield {"iteration": it, "best_cost": bc, "best_tour": best,
                   "current_cost": cc, "extra": {}}
            if stall >= p["patience"]:
                break


def install_recipes(SOLVERS: Dict, IterationState, build_problem, tour_length_fn) -> None:
    """把 RECIPES 动态包装成 BaseSolver 风格类注册进 SOLVERS。
    key 约定 recipe:<id>；前端下拉框/参数面板/PAGE_ALGO 自动生效，零前端改动。"""
    for r in RECIPES:
        cls = type(
            "Recipe_" + r["id"], (object,),
            {
                "__init__": lambda self, rid=r["id"]: setattr(self, "rid", rid),
                "name": r["name"] + " ⚗",
                "category": "组合配方（S7）",
                "default_params": dict(r["default_params"]),
                "param_specs": _specs_for(r),
                "implemented": True,
                "solve": staticmethod(lambda problem, params, _r=r: _iter_states(
                    run_recipe(_r, problem, params), IterationState)),
            },
        )
        SOLVERS["recipe:" + r["id"]] = cls


def _iter_states(gen, IterationState):
    for s in gen:
        yield IterationState(**s)


def _specs_for(r: Dict) -> Dict:
    """配方参数 → 前端滑块规格（与手写 solver 的 param_specs 同 schema）。"""
    dp = r["default_params"]
    S: Dict[str, Any] = {}
    if "pop" in dp:
        S["pop"] = {"min": 10, "max": 150, "step": 2, "int": True, "label": "种群规模", "desc": "每代个体数量"}
    # single 模式无 pop 参数（init 固定单解）——specs 覆盖检查要求 specs ⊆ defaults 且域合法
    if "pc" in dp:
        S["pc"] = {"min": 0, "max": 1, "step": 0.05, "int": False, "label": "交叉概率", "desc": "每对父代做交叉的概率"}
    if "pm" in dp:
        S["pm"] = {"min": 0, "max": 1, "step": 0.05, "int": False,
                   "label": "变异概率" if r["mode"] == "population" else "扰动强度", "desc": "变异/扰动触发概率"}
    S.setdefault("max_iter", {"min": 50, "max": 1000, "step": 10, "int": True, "label": "迭代次数", "desc": "预算上限"})
    if "elite" in dp:
        S["elite"] = {"min": 0, "max": 10, "step": 1, "int": True, "label": "精英保留", "desc": "直接进入下一代的父代最优个数"}
    if "tournament" in dp:
        S["tournament"] = {"min": 2, "max": 8, "step": 1, "int": True, "label": "锦标赛规模", "desc": "k 越大选择压力越强"}
    if "ls_every" in dp:
        S["ls_every"] = {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代触发一次局部搜索；0=关闭"}
    if "ls_moves" in dp:
        S["ls_moves"] = {"min": 1, "max": 300, "step": 5, "int": True, "label": "局部搜索预算", "desc": "局部搜索的最大移动数（fixopt 配方 = 每代采样窗口数）"}
    if "patience" in dp:
        S["patience"] = {"min": 0, "max": 300, "step": 10, "int": True, "label": "无改进停机", "desc": "连续 N 代无改进即停；0=只按迭代预算停"}
    if "eval_budget" in dp:  # S7-D SAEA
        S["eval_budget"] = {"min": 2, "max": 20, "step": 1, "int": True, "label": "精确评估预算", "desc": "每代只有代理预测最优的前 N 个子代付真实评估"}
    if "grid_res" in dp:  # S7-D MAP-Elites
        S["grid_res"] = {"min": 4, "max": 16, "step": 1, "int": True, "label": "行为网格分辨率", "desc": "行为描述子每维分格数；总格数 = N²"}
    S["seed"] = {"min": 0, "max": 9999, "step": 1, "int": True, "label": "随机种子", "desc": "同种子同结果（可复现）"}
    return S

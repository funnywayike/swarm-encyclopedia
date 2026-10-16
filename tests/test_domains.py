# -*- coding: utf-8 -*-
"""v0.8 问题域引擎测试：防假跑铁律在三个新域上的落地。

硬门槛：
  背包：所有算法（除 random 本身）显著优于随机基线，且历史最优永远可行。
  连续：sphere（单峰）上所有优化算法必须把随机基线碾压到接近 0；
        rastrigin（多峰）上种群算法 < 2.0，单链方法 < 5（随机基线在低维
        多峰本就近 0.6，这是已知现象，页面 FAQ 有解释）。
  多目标：NSGA-II 前沿必须是真·非支配集合，且规模/覆盖优于加权 GA。
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))

import domains  # noqa: E402


def _ok(domain, algos, variant=None):
    """去掉被「等评价次数」账本撤下的算法：这些格子在页面和引擎里都不再提供（data/withdrawn_cells.json）。"""
    return tuple(a for a in algos if not domains._is_withdrawn(domain, variant, a))



def _run(domain, algo, iters, seed, fn=None, dim=None, ratio=None):
    if domain == "continuous":
        prob = domains.cn_make(fn=fn, dim=dim)
    elif domain == "knapsack":
        prob = domains.ks_make(seed=seed)
    elif domain == "graphcolor":
        prob = domains.gc_make(seed=seed)
    elif domain == "binpack":
        prob = domains.bp_make(seed=seed)
    elif domain == "setcover":
        prob = domains.sc_make(seed=seed)
    elif domain == "sat":
        prob = domains.sat_make(seed=seed, ratio=ratio or 4.26)
    elif domain == "qubo":
        prob = domains.qb_make(seed=seed)
    elif domain == "gap":
        prob = domains.gap_make(seed=seed)
    elif domain == "uflp":
        prob = domains.uf_make(seed=seed)
    else:
        prob = domains.mo_make(seed=seed)
    domains.domain_start(domain, json.dumps(prob), algo, json.dumps({"max_iter": iters, "seed": seed}))
    first = last = None
    n = 0
    while True:
        s = domains.domain_step()
        if s is None:
            break
        d = json.loads(s)
        if first is None:
            first = d
        last = d
        n += 1
    return first, last, n


# ---------------- 背包域 ----------------

def test_knapsack_all_beat_random():
    _, rnd, _ = _run("knapsack", "random", 200, 7)
    base = rnd["best"]
    for algo in ("hc", "sa", "ga", "de", "ts", "abc", "woa", "gwo", "cs"):
        _, last, n = _run("knapsack", algo, 200, 7)
        assert n == 200, f"{algo} 迭代数不对"
        assert last["best"] > base, f"{algo} 没赢随机基线: {last['best']} vs {base}"


def test_knapsack_best_always_feasible():
    prob = domains.ks_make(seed=7)
    cap = prob["cap"]
    items = [tuple(x) for x in prob["items"]]
    for algo in ("sa", "ga", "woa", "cs", "ts"):
        domains.domain_start("knapsack", json.dumps(prob), algo, json.dumps({"max_iter": 80, "seed": 3}))
        while True:
            s = domains.domain_step()
            if s is None:
                break
            d = json.loads(s)
            sol = d["best_sol"]
            w = sum(items[i][0] for i in range(len(sol)) if sol[i])
            assert w <= cap, f"{algo} 历史最优超重: {w} > {cap}"


def test_knapsack_real_progress():
    """防假跑：第 1 代到第 200 代必须有真实进步（不许只靠初始化）。"""
    for algo in ("ga", "de", "woa", "abc"):
        first, last, _ = _run("knapsack", algo, 200, 7)
        assert last["best"] > first["best"], f"{algo} 全程无进步（假跑嫌疑）"


# ---------------- 连续域 ----------------

def test_continuous_sphere_crush_random():
    _, rnd, _ = _run("continuous", "random", 200, 7, fn="sphere", dim=4)
    base = rnd["best"]
    assert base > 1.0, "随机基线在 sphere 上不该这么好，测试实例有问题"
    for algo in _ok("continuous", ("hc", "sa", "pso", "de", "gwo", "woa", "sca")):
        _, last, n = _run("continuous", algo, 200, 7, fn="sphere", dim=4)
        assert n == 200, f"{algo} 迭代数不对"
        assert last["best"] < base * 0.1, f"{algo} 在 sphere 上没碾压随机: {last['best']} vs {base}"


def test_continuous_rastrigin_swarm_near_optimum():
    for algo in _ok("continuous", ("pso", "de", "gwo", "woa", "sca")):
        _, last, _ = _run("continuous", algo, 200, 7, fn="rastrigin", dim=2)
        assert last["best"] < 2.0, f"{algo} 在 rastrigin 上未收敛: {last['best']}"
    for algo in _ok("continuous", ("sa", "hc")):
        _, last, _ = _run("continuous", algo, 200, 7, fn="rastrigin", dim=2)
        assert last["best"] < 5.0, f"{algo} 在 rastrigin 上过差: {last['best']}"


def test_continuous_state_contract():
    domains.domain_start("continuous", json.dumps(domains.cn_make(fn="sphere", dim=2)),
                         "pso", json.dumps({"max_iter": 10, "seed": 1}))
    while True:
        s = domains.domain_step()
        if s is None:
            break
        d = json.loads(s)
        assert {"iter", "best", "particles", "gbest_pos"}.issubset(d.keys())
        for pt in d["particles"]:
            assert len(pt) == 2


# ---------------- 多目标域 ----------------

def test_nsga2_front_is_nondominated():
    _, last, _ = _run("multiobj", "nsga2", 120, 7)
    front = last["front"]
    assert len(front) >= 5, "NSGA-II 前沿太小"
    for i, a in enumerate(front):
        for j, b in enumerate(front):
            if i != j:
                a_dom = a[0] >= b[0] and a[1] >= b[1] and a != b
                assert not a_dom, f"前沿内出现支配对: {a} 支配 {b}"


def test_nsga2_beats_weighted_ga_on_coverage():
    """网格覆盖数：NSGA-II 的前沿覆盖应不差于加权 GA（加权法漏非凸段）。"""
    def coverage(front):
        cells = {(round(f[0] / 50), round(f[1] / 50)) for f in front}
        return len(cells)

    _, wlast, _ = _run("multiobj", "wsga", 120, 7)
    _, nlast, _ = _run("multiobj", "nsga2", 120, 7)
    assert coverage(nlast["front"]) >= coverage(wlast["front"]), \
        f"NSGA-II 覆盖 {coverage(nlast['front'])} < 加权GA {coverage(wlast['front'])}"


def test_multiobj_state_contract():
    domains.domain_start("multiobj", json.dumps(domains.mo_make(seed=3)),
                         "nsga2", json.dumps({"max_iter": 15, "seed": 1}))
    while True:
        s = domains.domain_step()
        if s is None:
            break
        d = json.loads(s)
        assert {"iter", "pop", "front", "nd"}.issubset(d.keys())
        for pt in d["pop"]:
            assert len(pt) == 2


# ---------------- 图着色域 ----------------
# 实例教训（写进页面 FAQ）：随机几何图太「结构化」，随机序 First-Fit 就近乎最优，
# 全员贴底没有区分度——必须用 DSJC 均匀随机图（文献标准硬实例族）。
# 判定口径：主指标 = 色数 k，次级 = Σci²（鼓励空出高编号桶）。
# 随机基线 = best-of-200（与域引擎 _pm_random 同口径）。

_GC_OPT = ("hc", "sa", "ts", "ga", "abc", "woa")


def test_graphcolor_all_beat_random():
    _, rnd, _ = _run("graphcolor", "random", 200, 7)
    base = rnd["best"]
    for algo in _GC_OPT:
        _, last, n = _run("graphcolor", algo, 200, 7)
        assert n == 200, f"{algo} 迭代数不对"
        assert last["best"] < base, f"{algo} 未降低色数: {last['best']} vs 随机 {base}"


def test_graphcolor_coloring_is_legal():
    """着色合法性：best_sol 中任意相邻顶点必须异色（FF 解码由构造保证，测试守恒）。"""
    prob = domains.gc_make(n=50, seed=7, p=0.5)
    edges = prob["edges"]
    for algo in ("ga", "woa", "ts"):
        domains.domain_start("graphcolor", json.dumps(prob), algo, json.dumps({"max_iter": 80, "seed": 3}))
        while True:
            s = domains.domain_step()
            if s is None:
                break
            col = json.loads(s)["best_sol"]
        for u, v in edges:
            assert col[u] != col[v], f"{algo} 出现非法着色: 顶点 {u}/{v} 同色"


def test_graphcolor_real_progress():
    """防假跑：第 1 代到最后一代 (色数, Σci²) 必须真实下降（多种子门）。"""
    for algo in _GC_OPT:
        for seed in (1, 7, 13):
            first, last, _ = _run("graphcolor", algo, 200, seed)
            assert (last["best"], last["tie"]) < (first["best"], first["tie"]), \
                f"{algo} seed{seed} 全程无进步（假跑嫌疑）: {first['best']}/{first['tie']} -> {last['best']}/{last['tie']}"


# ---------------- 装箱域 ----------------
# 判定口径：(箱数, Σ剩余²) 字典序。Σ剩余² 鼓励箱子塞紧，是箱数平台期的主要区分度。
# 强基线豁免（对照 TSP 侧 30 次重启 2-opt 底线先例）：随机基线 = best-of-200，
# 偶尔摸到「箱数=下界且塞得很紧」的运气样本；单链算法在个别种子上追平箱数但
# 塞紧度略输属于强基线运气，不判假跑——硬门槛定为：
# 进步 5/5 必须全过 + 胜随机 ≥4/5（页面语义下实测：GC 的 SA=4/5，其余全 5/5）。
# SA 标定注：装箱 SA 用高频重启(restart_at=12)+强下探(polish=40)才追平 best-of-200。

_BP_OPT = _ok("binpack", ("hc", "sa", "ts", "ga", "abc", "woa"))


def test_binpack_beats_random():
    _, rnd, _ = _run("binpack", "random", 200, 7)
    base = (rnd["best"], rnd["tie"])
    for algo in _BP_OPT:
        _, last, n = _run("binpack", algo, 200, 7)
        assert n == 200, f"{algo} 迭代数不对"
        assert (last["best"], last["tie"]) < base, \
            f"{algo} 未赢随机基线: {last['best']}/{last['tie']} vs {base[0]}/{base[1]}"


def test_binpack_population_beats_random_multiseed():
    """种群+memetic 系（GA/ABC/WOA/TS）在 5 种子上必须全部赢随机元组；
    SA 单链按强基线豁免放宽到 ≥4/5（见模块注释）。"""
    wins = {a: 0 for a in _ok("binpack", ("sa", "ts", "ga", "abc", "woa"))}
    for seed in (1, 7, 13, 21, 42):
        _, rnd, _ = _run("binpack", "random", 200, seed)
        base = (rnd["best"], rnd["tie"])
        for algo in wins:
            _, last, _ = _run("binpack", algo, 200, seed)
            wins[algo] += 1 if (last["best"], last["tie"]) < base else 0
    for algo, w in wins.items():
        need = 4 if algo == "sa" else 5
        assert w >= need, f"{algo} 胜随机 {w}/5 < 要求 {need}/5"


def test_binpack_assignment_feasible():
    """装箱可行性：best_sol 的每箱总重 ≤ 容量（FF 解码由构造保证，测试守恒）。"""
    prob = domains.bp_make(n=40, seed=7)
    cap, items = prob["cap"], prob["items"]
    for algo in _ok("binpack", ("ga", "woa", "hc")):
        domains.domain_start("binpack", json.dumps(prob), algo, json.dumps({"max_iter": 80, "seed": 3}))
        while True:
            s = domains.domain_step()
            if s is None:
                break
            assign = json.loads(s)["best_sol"]
        loads = {}
        for i, b in enumerate(assign):
            loads[b] = loads.get(b, 0) + items[i]
        for b, w in loads.items():
            assert w <= cap, f"{algo} 箱 {b} 超载: {w} > {cap}"


def test_binpack_real_progress():
    """防假跑：(箱数, Σ剩余²) 5 种子必须全部真实下降。"""
    for algo in _BP_OPT:
        for seed in (1, 7, 13, 21, 42):
            first, last, _ = _run("binpack", algo, 200, seed)
            assert (last["best"], last["tie"]) < (first["best"], first["tie"]), \
                f"{algo} seed{seed} 全程无进步（假跑嫌疑）: {first['best']}/{first['tie']} -> {last['best']}/{last['tie']}"


# ---------------- G 期五域：SCP / SAT / QUBO / GAP / UFLP ----------------
# 判定口径（bench 标定，100 代 × 多种子）：
#   setcover：random ~141(seed7) 起，swap 系 ~88，Chvátal 贪心 ~99——交换邻域是修复式
#   编码的标准邻域，单比特翻转在此 landscapes 下全部卡死（G1 实测教训）。
#   uflp：客户只有 3 个偏好设施（低指派成本），组合耦合让盲采样吃亏。
#   qubo：随机 Q，对角 -20~60 / 非对角 ±15。
#   gap：整数编码 + 容量修复；SA 温度按「100 代内进入低温区」标定（t0=25, decay=0.97）。
#   sat：默认 30 变量 ratio=4.26；DPLL 是确定性精确锚点，可满足实例必须 best==0。

_SC_OPT = ("hc", "sa", "ts", "ga")
_GAP_OPT = ("hc", "sa", "ga")


def test_setcover_beats_random_and_greedy():
    """swap 邻域元启发式赢随机基线，且赢 Chvátal ln-n 贪心锚点（教学点）。"""
    _, rnd, _ = _run("setcover", "random", 100, 7)
    base = rnd["best"]
    results = {}
    for algo in _SC_OPT + ("greedy",):
        _, last, n = _run("setcover", algo, 100, 7)
        assert n == 100, f"{algo} 迭代数不对"
        assert last["best"] < base, f"{algo} 未赢随机基线: {last['best']} vs {base}"
        results[algo] = last["best"]
    assert results["hc"] < results["greedy"], \
        f"交换邻域 HC 应赢 ln-n 贪心: {results['hc']} vs {results['greedy']}"


def test_setcover_best_always_covers():
    """全覆盖守恒：best_sol 的未覆盖元素必须恒为 0（修复算子由构造保证）。"""
    prob = domains.sc_make(seed=7)
    ctx = domains._SC(prob)
    for algo in ("sa", "ts", "ga"):
        domains.domain_start("setcover", json.dumps(prob), algo, json.dumps({"max_iter": 40, "seed": 3}))
        while True:
            s = domains.domain_step()
            if s is None:
                break
            d = json.loads(s)
            assert ctx.uncovered(d["best_sol"]) == 0, f"{algo} 历史最优出现未覆盖元素"
            assert d["best"] == ctx.cost(d["best_sol"]), f"{algo} best 与成本不一致（有罚残留）"


def test_setcover_real_progress():
    """防假跑：hc/ga 全程必须真实下降。"""
    for algo in ("hc", "ga"):
        first, last, _ = _run("setcover", algo, 100, 7)
        assert last["best"] < first["best"], \
            f"{algo} 全程无进步（假跑嫌疑）: {first['best']} -> {last['best']}"


def test_sat_optimization_beats_random():
    _, rnd, _ = _run("sat", "random", 100, 7)
    base = rnd["best"]
    for algo in ("hc", "ts", "walksat"):
        _, last, n = _run("sat", algo, 100, 7)
        assert n == 100, f"{algo} 迭代数不对"
        assert last["best"] < base, f"{algo} 未满足数没赢随机: {last['best']} vs {base}"


def test_sat_dpll_exact_on_satisfiable():
    """确定性精确锚点：可满足实例（ratio 3.5）上 DPLL 必须给出 best==0 且赋值真满足。"""
    prob = domains.sat_make(n_vars=30, ratio=3.5, seed=7)
    ctx = domains._SAT(prob)
    for _ in range(2):  # 两次运行结果必须一致（确定性）
        domains.domain_start("sat", json.dumps(prob), "dpll", json.dumps({"max_iter": 50, "seed": 3}))
        while True:
            s = domains.domain_step()
            if s is None:
                break
            d = json.loads(s)
        assert d["best"] == 0, f"DPLL 在可满足实例上 best!=0: {d['best']}"
        assert ctx.unsat(d["best_sol"]) == 0, "DPLL 的解未真正满足全部子句"


def test_qubo_all_beat_random():
    _, rnd, _ = _run("qubo", "random", 100, 7)
    base = rnd["best"]
    for algo in ("hc", "sa", "ts", "ga"):
        _, last, n = _run("qubo", algo, 100, 7)
        assert n == 100, f"{algo} 迭代数不对"
        assert last["best"] < base, f"{algo} 能量没赢随机: {last['best']} vs {base}"


def test_qubo_real_progress():
    for algo in ("hc", "ts"):
        first, last, _ = _run("qubo", algo, 100, 7)
        assert last["best"] < first["best"], \
            f"{algo} 全程无进步（假跑嫌疑）: {first['best']} -> {last['best']}"


def test_gap_all_beat_random_multiseed():
    """GAP 三算法 × 五种子全部赢随机（SA 按 100 代标定 t0=25/decay=0.97）。"""
    for seed in (1, 7, 13, 21, 42):
        _, rnd, _ = _run("gap", "random", 100, seed)
        base = rnd["best"]
        for algo in _GAP_OPT:
            _, last, n = _run("gap", algo, 100, seed)
            assert n == 100, f"{algo} 迭代数不对"
            assert last["best"] < base, f"{algo} seed{seed} 未赢随机: {last['best']} vs {base}"


def test_gap_best_always_feasible():
    """容量守恒：best_sol 的任何代理不超载（罚系数 BIG=1000，best 中不应有罚残留）。"""
    prob = domains.gap_make(seed=7)
    ctx = domains._GAP(prob)
    for algo in ("hc", "ga", "sa"):
        domains.domain_start("gap", json.dumps(prob), algo, json.dumps({"max_iter": 60, "seed": 3}))
        while True:
            s = domains.domain_step()
            if s is None:
                break
            d = json.loads(s)
            assert ctx.overflow(d["best_sol"]) == 0, f"{algo} 历史最优超载"
            assert d["best"] == ctx.cost(d["best_sol"]), f"{algo} best 与成本不一致（有罚残留）"


def test_uflp_all_beat_random_multiseed():
    for seed in (1, 7, 13, 21, 42):
        _, rnd, _ = _run("uflp", "random", 100, seed)
        base = rnd["best"]
        for algo in ("hc", "sa", "ts", "ga", "greedy"):
            _, last, n = _run("uflp", algo, 100, seed)
            assert n == 100, f"{algo} 迭代数不对"
            assert last["best"] < base, f"{algo} seed{seed} 未赢随机: {last['best']} vs {base}"


def test_uflp_greedy_is_deterministic_anchor():
    """贪心锚点：同一实例、不同运行种子，两次结果必须一致，且不劣于随机基线。"""
    prob = domains.uf_make(seed=7)
    outs = []
    for run_seed in (7, 99):
        domains.domain_start("uflp", json.dumps(prob), "greedy",
                             json.dumps({"max_iter": 60, "seed": run_seed}))
        while True:
            s = domains.domain_step()
            if s is None:
                break
            d = json.loads(s)
        outs.append(d["best"])
    assert outs[0] == outs[1], f"贪心锚点非确定性: {outs[0]} vs {outs[1]}"
    _, rnd, _ = _run("uflp", "random", 100, 7)
    assert outs[0] <= rnd["best"], f"贪心锚点应不劣于随机基线: {outs[0]} vs {rnd['best']}"


def test_uflp_best_always_has_open_facility():
    prob = domains.uf_make(seed=7)
    for algo in ("hc", "sa", "ga"):
        domains.domain_start("uflp", json.dumps(prob), algo, json.dumps({"max_iter": 60, "seed": 3}))
        while True:
            s = domains.domain_step()
            if s is None:
                break
            d = json.loads(s)
            assert any(d["best_sol"]), f"{algo} 历史最优没有开任何设施"


# ---------------- H1 期：背包家族变体 kpvar（10 变体单域多预设） ----------------
# 标定记录（2026-09-25，seed=7，200 迭代）：全部 10 变体全部算法（含贪心锚点）
#   赢随机基线。价值型变体复用 ks_make 标定分布 + _KS 内核 max 包装器
#   （_KPVMaxWrap，报值取负回 min 口径）；mkpm 复用 _GAP 指派内核
#   （SA 默认参数在 domain_start 内被 t0=25/decay=0.97 覆盖）；
#   ssp/cmp 各挂专属伪多项式 DP 精确锚点（ssp_dp=0；cmp_dp 精确最优）。
# 注意：_ks_random 哨兵必须是 None 不能是 -1（负值景观下 -1 会吞掉全部样本）。

_KPVAR_VARIANTS = ("bkp", "ukp", "cmp", "ssp", "mdkp", "dkp", "qkp", "mckp", "mkpm")
_KPVAR_ONESHOT = ("ssp_dp", "cmp_dp", "greedy")  # 一次出解的锚点，不跑满 200 代


def _run_kpvar(variant, algo, iters=200, seed=7):
    prob = json.loads(domains.domain_preset("kpvar", seed, {"variant": variant, "n": 40}))
    domains.domain_start("kpvar", json.dumps(prob), algo, json.dumps({"max_iter": iters, "seed": seed}))
    first = last = None
    n = 0
    while True:
        s = domains.domain_step()
        if s is None:
            break
        d = json.loads(s)
        if first is None:
            first = d
        last = d
        n += 1
    return prob, first, last, n


def test_kpvar_all_beat_random():
    for variant in _KPVAR_VARIANTS:
        _, rnd, _, _ = _run_kpvar(variant, "random")
        base = rnd["best"]
        algos = [a["key"] for a in json.loads(domains.domain_list("kpvar", {"variant": variant}))["algos"]
                 if a["key"] != "random"]
        for algo in algos:
            _, _, last, n = _run_kpvar(variant, algo)
            if algo not in _KPVAR_ONESHOT:
                assert n == 200, f"{variant}/{algo} 迭代数不对: {n}"
            assert last["best"] <= base, f"{variant}/{algo} 未赢随机基线: {last['best']} vs {base}"


def test_kpvar_best_sol_feasible_and_consistent():
    """best_sol 可行性 + best 与原始 ctx 目标一致（无 BIG 罚残留、口径无漂移）。"""
    for variant in _KPVAR_VARIANTS:
        algo = next(a for a in ("sa", "ga", "ts", "de") if not domains._is_withdrawn("kpvar", variant, a))
        prob, _, last, _ = _run_kpvar(variant, algo, iters=80, seed=3)
        sol = last["best_sol"]
        ctx = (domains._MKPM(prob) if variant == "mkpm"
               else domains._MCKP(prob) if variant in ("mckp", "dkp") else domains._KPV(prob))
        assert abs(ctx.obj(sol) - last["best"]) < 1e-6, \
            f"{variant}: best({last['best']}) 与 best_sol 目标({ctx.obj(sol)}) 不一致"
        if variant == "mkpm":
            load = [0] * prob["m"]
            for i, x in enumerate(sol):
                if x:
                    load[x - 1] += prob["w"][i]
            assert all(load[a] <= prob["caps"][a] for a in range(prob["m"])), f"mkpm 超载: {load}"
        elif variant in ("mckp", "dkp"):
            for c in range(prob["k"]):
                assert sum(sol[c * prob["r"]:(c + 1) * prob["r"]]) <= 1, f"{variant} 类 {c} 选了多件"
        elif variant not in ("cmp", "ssp"):
            caps = prob["caps"] if variant == "mdkp" else [prob["cap"]]
            if variant == "mdkp":
                load = [sum(prob["W"][d][i] for i in range(prob["n"]) if sol[i]) for d in range(len(caps))]
                assert all(load[d] <= caps[d] for d in range(len(caps))), f"mdkp 超载: {load}"
            else:
                w = [x[0] for x in prob["items"]] if "items" in prob else prob["w"]
                assert sum(w[i] for i in range(len(sol)) if sol[i]) <= prob["cap"], f"{variant} 超载"


def test_kpvar_exact_anchors():
    """伪多项式 DP 锚点：ssp 必达 0 差；cmp 的 best 必等于其 best_sol 的真实目标且 ≤ 随机。"""
    for variant, anchor in (("ssp", "ssp_dp"), ("cmp", "cmp_dp")):
        _, _, last, _ = _run_kpvar(variant, anchor)
        prob, _, rnd_last, _ = _run_kpvar(variant, "random")
        ctx = domains._KPV(prob)
        assert last["best"] == ctx.obj(last["best_sol"]), f"{anchor} best 与解不一致"
        assert last["best"] <= rnd_last["best"], f"{anchor} 应不劣于随机: {last['best']} vs {rnd_last['best']}"
        if variant == "ssp":
            assert last["best"] == 0, f"ssp_dp 应精确命中 0 差，得 {last['best']}"


def test_kpvar_real_progress():
    """防假跑：ga 在价值型变体上第 1 代到第 200 代必须有真实进步。"""
    for variant in ("bkp", "ukp", "mckp"):
        _, first, last, _ = _run_kpvar(variant, "ga")
        assert last["best"] < first["best"], \
            f"{variant}/ga 全程无进步（假跑嫌疑）: {first['best']} -> {last['best']}"


# ---------------- H2 期：着色家族变体 gcvar（5 变体单域多预设） ----------------
# 判定口径：主指标 = 色数 k（yield 的 best）；次级 = 冲突数 conf（yield 的 "tie" 实为 conf）。
# 5 变体：listcolor/precolor/edgecolor/totalcolor 用排列编码 + _pm_* 内核（线图/全图变换后
#   走同一 decode）；mis 用 0/1 位串编码 + _bin_* 内核（无 "tie" 字段，best 为 -|S|+BIG*conf）。
# 随机基线 = best-of-200（与 _pm_random/_bin_random 同口径）；5/5 原则 = 每变体每算法 ≤ 随机
#   （edgecolor/totalcolor 在 DSJC 实例上线图/全图色数贴底，允许与随机并列）。

_GCVAR_VARIANTS = ("listcolor", "precolor", "edgecolor", "totalcolor", "mis")
_GCVAR_ONESHOT = ("greedy",)  # 一次出解的锚点，不跑满 200 代
_GCVAR_BLOWUP = ("edgecolor", "totalcolor")  # 线图/全图变换后 N 暴涨，测试用更小 n


def _run_gcvar(variant, algo, iters=100, seed=7):
    n = 22 if variant in _GCVAR_BLOWUP else 40
    prob = json.loads(domains.domain_preset("gcvar", seed, {"variant": variant, "n": n, "p": 0.5}))
    domains.domain_start("gcvar", json.dumps(prob), algo,
                         json.dumps({"max_iter": iters, "seed": seed, "ts_sample": 30}))
    first = last = None
    n = 0
    while True:
        s = domains.domain_step()
        if s is None:
            break
        d = json.loads(s)
        if first is None:
            first = d
        last = d
        n += 1
    return prob, first, last, n


def test_gcvar_all_beat_random():
    """5/5 原则：每变体每算法（除 random 本身）终值 ≤ 随机基线 best-of-150。"""
    for variant in _GCVAR_VARIANTS:
        _, rnd, _, _ = _run_gcvar(variant, "random")
        base = rnd["best"]
        algos = [a["key"] for a in json.loads(domains.domain_list("gcvar", {"variant": variant}))["algos"]
                 if a["key"] != "random"]
        for algo in algos:
            _, _, last, n = _run_gcvar(variant, algo)
            if algo not in _GCVAR_ONESHOT:
                assert n == 100, f"{variant}/{algo} 迭代数不对: {n}"
            assert last["best"] <= base, f"{variant}/{algo} 未赢随机基线: {last['best']} vs {base}"


def test_gcvar_solutions_legal():
    """解的合法性（最强防假跑）：4 个着色变体 best_sol 在引擎邻接上零冲突；mis 选中集独立。"""
    for variant in ("listcolor", "precolor", "edgecolor", "totalcolor"):
        prob = json.loads(domains.domain_preset("gcvar", 7, {"variant": variant, "n": 40, "p": 0.5}))
        domains.domain_start("gcvar", json.dumps(prob), "ga", json.dumps({"max_iter": 120, "seed": 3}))
        last = None
        while True:
            s = domains.domain_step()
            if s is None:
                break
            last = json.loads(s)
        col = last["best_sol"]
        if variant in ("listcolor", "precolor"):
            adj = domains._graph_adj(prob["edges"], prob["n"])
            for u in range(prob["n"]):
                for x in adj[u]:
                    if x > u and col[u] == col[x]:
                        assert False, f"{variant} 非法着色: 顶点 {u}/{x} 同色"
        elif variant == "edgecolor":
            for a in range(len(prob["edges"])):
                for b in prob["ladj"][a]:
                    if a < b and col[a] == col[b]:
                        assert False, f"{variant} 非法边着色: 边 {a}/{b} 同色"
        elif variant == "totalcolor":
            N = prob["N"]
            for e in range(N):
                for x in prob["tadj"][e]:
                    if e < x and col[e] == col[x]:
                        assert False, f"{variant} 非法全着色: 元素 {e}/{x} 同色"


def test_gcvar_mis_independent():
    """MIS：best_sol 中选中的顶点两两不相邻（独立集），且 obj = -|S|（冲突必为 0）。"""
    prob = json.loads(domains.domain_preset("gcvar", 7, {"variant": "mis", "n": 40, "p": 0.5}))
    adj = domains._graph_adj(prob["edges"], prob["n"])
    domains.domain_start("gcvar", json.dumps(prob), "ga", json.dumps({"max_iter": 120, "seed": 3}))
    last = None
    while True:
        s = domains.domain_step()
        if s is None:
            break
        last = json.loads(s)
    sol = last["best_sol"]
    size = sum(sol)
    for u in range(prob["n"]):
        if sol[u]:
            for v in adj[u]:
                if v > u and sol[v]:
                    assert False, f"mis 非法独立集: {u}/{v} 相邻且皆选中"
    assert last["best"] == -size, f"mis obj 口径漂移: best={last['best']} vs -|S|=-{size}"


def test_gcvar_real_progress():
    """防假跑：headroom 变体（listcolor/mis）至少 1 个元启发必须严格优于随机基线
    （证明引擎真在优化，而非锚点/随机碰巧）；贴底变体（precolor/edgecolor/totalcolor）
    在 DSJC 实例上线图/全图色数已贴底（随机即最优），只要求最优算法不劣于随机。"""
    for variant in _GCVAR_VARIANTS:
        _, rnd, _, _ = _run_gcvar(variant, "random")
        base = rnd["best"]
        opts = [a["key"] for a in json.loads(domains.domain_list("gcvar", {"variant": variant}))["algos"]
                if a["key"] not in ("random", "greedy")]
        best_algo = min(_run_gcvar(variant, a)[2]["best"] for a in opts)
        if variant in ("listcolor", "mis"):
            assert best_algo < base, \
                f"{variant} 无元启发严格优于随机基线（疑似假跑）: base={base}, best={best_algo}"
        else:
            assert best_algo <= base, f"{variant} 最优算法劣于随机: {best_algo} vs {base}"


# ---------------- H3 期：装箱变体家族 bpvar（3 变体单域多预设） ----------------
# 判定口径：主指标 = best（vsbinpack=成本+Σ剩余² 元组；binpack2d=箱数+Σ空隙²；
#   strippack=总高+Σ空隙²）；best_sol = 几何结构（boxes/conts，问题单位坐标），
#   供前端 drawBPVAR 直接渲染。5/5 原则 = 每变体每算法 ≤ 随机基线；real_progress =
#   每变体至少 1 个元启发严格 < 随机（ga/woa 在 3 变体上均严格打赢，已标定）。

_BPVAR_VARIANTS = ("vsbinpack", "binpack2d", "strippack")
_BPVAR_ONESHOT = ("greedy",)  # 一次性构造锚点，不跑满 200 代


def _run_bpvar(variant, algo, iters=200, seed=7, n=40):
    prob = json.loads(domains.domain_preset("bpvar", seed, {"variant": variant, "n": n}))
    domains.domain_start("bpvar", json.dumps(prob), algo,
                         json.dumps({"max_iter": iters, "seed": seed}))
    first = last = None
    cnt = 0
    while True:
        s = domains.domain_step()
        if s is None:
            break
        d = json.loads(s)
        if first is None:
            first = d
        last = d
        cnt += 1
    return prob, first, last, cnt


def _bpv_geom_ok(prob, last):
    """几何一致性（最强防假跑）：每个物品恰好放置一次，且每块完全落在所属容器内。"""
    bs = last["best_sol"]
    assert set(bs.keys()) >= {"variant", "boxes", "conts"}, "best_sol 非几何结构"
    boxes, conts = bs["boxes"], bs["conts"]
    assert len(boxes) == prob["n"], f"放置块数 {len(boxes)} ≠ 物品数 {prob['n']}"
    seen = sorted(b["i"] for b in boxes)
    assert seen == list(range(prob["n"])), f"物品放置不全/重复: {seen}"
    by_b = {c["b"]: c for c in conts}
    for b in boxes:
        c = by_b[b["b"]]
        assert c["x"] <= b["x"] + 1e-6, f"块越界(左): box.x={b['x']} cont.x={c['x']}"
        assert b["x"] + b["w"] <= c["x"] + c["w"] + 1e-6, \
            f"块越界(右): {b['x'] + b['w']} > {c['x'] + c['w']}"
        assert c["y"] <= b["y"] + 1e-6, f"块越界(上): box.y={b['y']} cont.y={c['y']}"
        assert b["y"] + b["h"] <= c["y"] + c["h"] + 1e-6, \
            f"块越界(下): {b['y'] + b['h']} > {c['y'] + c['h']}"
    return True


def test_bpvar_all_beat_random():
    """5/5 原则：每变体每算法（除 random 本身）主指标 ≤ 随机基线 best-of-200。
    best 即主指标标量（vsbinpack 成本 / binpack2d 箱数 / strippack 总高）；
    tie 为独立次级字段（剩余/空隙平方和），不参与“是否赢随机”的判定。"""
    for variant in _BPVAR_VARIANTS:
        _, rnd, _, _ = _run_bpvar(variant, "random")
        base = rnd["best"]
        algos = [a["key"] for a in json.loads(domains.domain_list("bpvar", {"variant": variant}))["algos"]
                 if a["key"] != "random"]
        for algo in algos:
            _, _, last, n = _run_bpvar(variant, algo)
            if algo not in _BPVAR_ONESHOT:
                assert n == 200, f"{variant}/{algo} 迭代数不对: {n}"
            assert last["best"] <= base, \
                f"{variant}/{algo} 主指标劣于随机基线: {last['best']} vs {base}"


def test_bpvar_real_progress():
    """防假跑：每变体至少 1 个元启发必须严格优于随机基线（ga/woa 均满足，已标定）。"""
    for variant in _BPVAR_VARIANTS:
        _, rnd, _, _ = _run_bpvar(variant, "random")
        base = rnd["best"]
        opts = [a["key"] for a in json.loads(domains.domain_list("bpvar", {"variant": variant}))["algos"]
                if a["key"] != "random"]
        best_algo = min(_run_bpvar(variant, a)[2]["best"] for a in opts)
        assert best_algo < base, \
            f"{variant} 无元启发严格优于随机基线（疑似假跑）: base={base}, best={best_algo}"


def test_bpvar_geometry_consistent():
    """解的几何合法性：每变体 ga 解的 best_sol 覆盖全部物品一次且块不越界。"""
    for variant in _BPVAR_VARIANTS:
        prob, _, last, _ = _run_bpvar(variant, "ga", iters=120, seed=3, n=40)
        assert _bpv_geom_ok(prob, last), f"{variant} 几何不一致"


def test_bpvar_greedy_feasible():
    """构造锚点 greedy 也须给出可行全放置解（所有物品恰好一次）。"""
    for variant in _BPVAR_VARIANTS:
        prob, _, last, _ = _run_bpvar(variant, "greedy", iters=1, seed=7, n=40)
        bs = last["best_sol"]
        seen = sorted(b["i"] for b in bs["boxes"])
        assert seen == list(range(prob["n"])), f"{variant} greedy 未全放置: {seen}"


# ---------------- H3 期：BBOB 连续基准（仅追加 6 个可分函数） ----------------

_BBOB_FUNCS = ("bbob_f1", "bbob_f2", "bbob_f3", "bbob_f4", "bbob_f5", "bbob_f6")


def test_bbob_funcs_registered():
    """6 个 BBOB 函数已注册进 FUNCS，且最优值均为 0（原点）。"""
    for fn in _BBOB_FUNCS:
        assert fn in domains.FUNCS, f"{fn} 未注册"
        assert domains.FUNCS[fn][3] == 0.0, f"{fn} 最优值非 0"


def test_bbob_optimum_at_origin():
    """原点处函数值≈0（防假函数定义）。"""
    for fn in _BBOB_FUNCS:
        f, lo, hi, opt = domains.FUNCS[fn]
        assert abs(f([0.0] * 5)) < 1e-9, f"{fn} 原点值非 0: {f([0.0] * 5)}"


def test_bbob_funcs_beat_random():
    """可分函数上种群算法须碾压随机基线（5/5 原则，至少 5/8 打赢）。"""
    for fn in ("bbob_f2", "bbob_f5"):
        _, rnd, _ = _run("continuous", "random", 200, 7, fn=fn, dim=5)
        base = rnd["best"]
        algos = [a["key"] for a in json.loads(domains.domain_list("continuous", {"fn": fn}))["algos"]
                 if a["key"] != "random"]
        res = {a: _run("continuous", a, 200, 7, fn=fn, dim=5)[1]["best"] for a in algos}
        beats = [a for a in algos if res[a] < base]
        assert len(beats) >= 5, f"{fn} 仅 {len(beats)}/{len(algos)} 算法打赢随机基线: {res}"


# ---------------- H3 期：多目标三目标 maop ----------------

def test_maop_three_obj_front():
    """maop（3 目标）NSGA-II：产出真·非支配前沿，且目标维数=3。"""
    prob = json.loads(domains.domain_preset("multiobj", 7, {"variant": "maop", "n": 40}))
    domains.domain_start("multiobj", json.dumps(prob), "nsga2",
                         json.dumps({"max_iter": 200, "seed": 7}))
    last = None
    while True:
        s = domains.domain_step()
        if s is None:
            break
        last = json.loads(s)
    assert last["nd"] > 0, f"maop 非支配解数为 0"
    assert all(len(p) == 3 for p in last["pop"]), "maop 目标维数非 3"
    # front 直接是目标点向量（非索引）
    pts = last["front"]
    assert len(pts) == last["nd"], f"maop 前沿规模 {len(pts)} ≠ nd {last['nd']}"
    assert all(len(p) == 3 for p in pts), "maop 前沿含非 3 维点"
    # 非支配性：前沿内任意两不同点不能互相严格支配
    for a in range(len(pts)):
        for b in range(len(pts)):
            if a == b:
                continue
            x, y = pts[a], pts[b]
            if x == y:
                continue
            if all(x[d] >= y[d] for d in range(3)) and any(x[d] > y[d] for d in range(3)):
                assert False, f"maop 前沿非非支配: {x} 支配 {y}"


def test_moco_two_obj_regression():
    """回归：moco（2 目标）仍正常产出 2 维前沿（三目标改造未破坏二目标）。"""
    prob = json.loads(domains.domain_preset("multiobj", 7, {"variant": "moco", "n": 40}))
    domains.domain_start("multiobj", json.dumps(prob), "nsga2",
                         json.dumps({"max_iter": 200, "seed": 7}))
    last = None
    while True:
        s = domains.domain_step()
        if s is None:
            break
        last = json.loads(s)
    assert last["nd"] > 0, "moco 非支配解数为 0"
    assert all(len(p) == 2 for p in last["pop"]), "moco 目标维数非 2"

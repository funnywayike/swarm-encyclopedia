# -*- coding: utf-8 -*-
"""定向运动（OP）与资源受限项目调度（RCPSP）：2026-10 从「示意」重建为标准模型。
旧版 OP 的路径包含全部顶点（没有选点决策）、旧版 RCPSP 的工期是各活动工期之和（没有并行）——这里用独立的穷举核对新模型。"""
import itertools
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "py"))

import domains as D  # noqa: E402
import entryseq as E  # noqa: E402
import registry as REG  # noqa: E402


def run(variant, algo, p, iters=80, seed=3):
    D.domain_start("entryseq", json.dumps(p), algo, json.dumps({"max_iter": iters, "seed": seed}))
    last = None
    while True:
        st = D.domain_step()
        if st is None:
            return last
        last = json.loads(st)


def test_both_are_standard_models_now():
    assert REG.fidelity("entryseq", "orienteering")["level"] == "standard"
    assert REG.fidelity("entryseq", "rcpsp")["level"] == "standard"


# ---------------------------------------------------------------- 定向运动
def _op_bruteforce(p):
    """独立穷举：对每个「访问序列」（任意子集 × 任意排列）算路程，路程 ≤ 预算的里取收益最大。"""
    pts, gain, budget, n = p["pts"], p["gain"], p["budget"], p["n"]
    best = 0
    for r in range(n + 1):
        for seq in itertools.permutations(range(1, n + 1), r):
            route = (0,) + seq + (0,)
            length = sum(math.dist(pts[a], pts[b]) for a, b in zip(route, route[1:]))
            if length <= budget + 1e-9:
                best = max(best, sum(gain[j] for j in seq))
    return best


def test_orienteering_has_a_real_selection_decision():
    p = E.es_make("orienteering", 8, 7)
    ctx = E.es_ctx(p)
    assert sum(p["gain"]) > 0
    detail = ctx.detail(list(range(p["n"])))
    assert detail["score"] < detail["total_gain"], "预算必须紧到走不完所有点（否则又退化成没有选点决策）"
    assert detail["length"] <= p["budget"] + 1e-6
    # 解码总是给出一条在预算内、从仓库出发回到仓库的路线
    import random
    rng = random.Random(1)
    for _ in range(50):
        s = ctx.random(rng)
        d = ctx.detail(s)
        assert d["route"][0] == 0 == d["route"][-1] and d["length"] <= p["budget"] + 1e-6
        assert len(set(d["route"][1:-1])) == len(d["route"]) - 2


def test_orienteering_algorithms_reach_the_exhaustive_optimum():
    p = E.es_make("orienteering", 8, 7)
    p = dict(p)  # 8 个点：穷举 Σ 8!/(8-r)! ≈ 10 万条序列，可接受
    opt = _op_bruteforce(p)
    assert opt > 0
    best = max(-run("orienteering", a, p, iters=120, seed=s)["best"] for a in ("sa", "ga", "ts") for s in (1, 2))
    assert round(best) == opt, f"穷举最优收益 {opt}，算法最好 {best}"
    # 上报的 best 与它自己给出的路线一致
    last = run("orienteering", "sa", p, iters=60)
    assert round(-last["best"]) == last["score"]


# ---------------------------------------------------------------- RCPSP
def _feasible(p, start):
    dur, preds, r, caps = p["dur"], p["preds"], p["r"], p["caps"]
    n = len(dur)
    if any(start[i] < max((start[q] + dur[q] for q in preds[i]), default=0) for i in range(n)):
        return False
    horizon = max(start[i] + dur[i] for i in range(n))
    for t in range(horizon):
        for k in range(len(caps)):
            if sum(r[i][k] for i in range(n) if start[i] <= t < start[i] + dur[i]) > caps[k]:
                return False
    return True


def _rcpsp_exact(p):
    """独立精确解：对每个活动枚举开工时刻（按编号顺序，前序都在更小的编号上），深度优先带剪枝。"""
    dur, preds, r, caps = p["dur"], p["preds"], p["r"], p["caps"]
    n, K = len(dur), len(caps)
    H = sum(dur)
    best = [H]
    start = [0] * n

    def usage_ok(i, t):
        for u in range(t, t + dur[i]):
            for k in range(K):
                if r[i][k] + sum(r[j][k] for j in range(i) if start[j] <= u < start[j] + dur[j]) > caps[k]:
                    return False
        return True

    def dfs(i, cur_end):
        if cur_end >= best[0]:
            return
        if i == n:
            best[0] = cur_end
            return
        est = max((start[q] + dur[q] for q in preds[i]), default=0)
        for t in range(est, best[0] - dur[i] + 1):
            if usage_ok(i, t):
                start[i] = t
                dfs(i + 1, max(cur_end, t + dur[i]))
    dfs(0, 0)
    return best[0]


def test_rcpsp_schedule_is_precedence_and_resource_feasible_and_runs_in_parallel():
    p = E.es_make("rcpsp", 12, 7)
    ctx = E.es_ctx(p)
    import random
    rng = random.Random(2)
    parallel = False
    for _ in range(60):
        s = ctx.random(rng)
        start, end, mk = E.rcpsp_schedule(p, s)
        assert _feasible(p, start), "串行调度生成方案给出了不可行的排程"
        assert mk == max(end) and mk == ctx.obj(s)
        assert mk <= sum(p["dur"])
        parallel |= mk < sum(p["dur"])
    assert parallel, "活动从不并行——又退化成「工期 = 各活动工期之和」"


def test_rcpsp_priority_lists_cover_the_exact_optimum_and_algorithms_find_it():
    for seed in (1, 2, 3):
        p = E.es_make("rcpsp", 7, seed)
        p["n"] = 7
        opt = _rcpsp_exact(p)
        ctx = E.es_ctx(p)
        listed = min(ctx.obj(list(t)) for t in itertools.permutations(range(p["n"])))
        assert listed == opt, f"seed {seed}：优先序空间的最优 {listed} ≠ 独立精确解 {opt}"
        best = min(run("rcpsp", a, p, iters=80, seed=s)["best"] for a in ("sa", "ga", "ts") for s in (1, 2))
        assert best == opt, f"seed {seed}：算法 {best} vs 精确 {opt}"


def test_rcpsp_lower_bound_is_valid_and_detail_matches():
    p = E.es_make("rcpsp", 12, 7)
    last = run("rcpsp", "sa", p, iters=60)
    assert last["lb"] <= last["best"] == last["makespan"] == max(last["end"])

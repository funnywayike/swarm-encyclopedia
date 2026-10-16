# -*- coding: utf-8 -*-
"""vrp 词条 = 真·带容量多车路径（CVRP）：解 = 客户访问序，解码 = Prins 最优切分。
此前它是「所有客户连成一条大回路 + 超载罚款」，不是 VRP；这里钉死新模型的正确性。"""
import itertools
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "py"))

import domains as D  # noqa: E402
import entryseq as E  # noqa: E402
import registry as REG  # noqa: E402


def _ctx(n, seed):
    p = E.es_make("vrp", n, seed)
    return p, E._ES(p)


def _brute_split(Dm, demand, cap, K, tour):
    """穷举所有「在间隙处切或不切」的方案——比 DP 笨但不可能错。"""
    n = len(tour)
    best = float("inf")
    for mask in range(1 << (n - 1)):
        cuts = [i + 1 for i in range(n - 1) if mask >> i & 1]
        if len(cuts) + 1 > K:
            continue
        segs, prev = [], 0
        for c in cuts + [n]:
            segs.append(tour[prev:c])
            prev = c
        if any(sum(demand[x] for x in sg) > cap for sg in segs):
            continue
        cost = sum(Dm[0][sg[0]] + sum(Dm[a][b] for a, b in zip(sg, sg[1:])) + Dm[sg[-1]][0] for sg in segs)
        best = min(best, cost)
    return best


def test_vrp_is_registered_as_a_standard_model():
    assert REG.fidelity("entryseq", "vrp")["level"] == "standard"


def test_instances_are_feasible_and_scale_with_n():
    for n in (5, 12, 25, 40):
        p = E.es_make("vrp", n, 7)
        assert p["n"] == n and len(p["pts"]) == n + 1 and p["pts"][0] == [50.0, 50.0]
        assert p["cap"] >= max(p["demand"]) and p["m_veh"] * p["cap"] >= sum(p["demand"])


def test_split_equals_brute_force_on_random_tours():
    rng = random.Random(5)
    for seed in (1, 2, 3):
        p, ctx = _ctx(7, seed)
        Dm = E._vrp_dist(ctx)
        for _ in range(25):
            t = rng.sample(range(1, p["n"] + 1), p["n"])
            got, routes = E.vrp_split(Dm, p["demand"], p["cap"], p["m_veh"], t)
            want = _brute_split(Dm, p["demand"], p["cap"], p["m_veh"], t)
            if want == float("inf"):
                assert got is None
            else:
                assert abs(got - want) < 1e-9


def test_routes_are_a_legal_cvrp_solution():
    for n in (12, 30):
        p, ctx = _ctx(n, 7)
        Dm = E._vrp_dist(ctx)
        rng = random.Random(n)
        for _ in range(20):
            s = ctx.random(rng)
            routes = ctx.routes(s)
            flat = [c for r in routes for c in r]
            assert sorted(flat) == list(range(1, n + 1)), "每个客户恰好被服务一次"
            assert all(sum(p["demand"][c] for c in r) <= p["cap"] for r in routes), "每辆车不超载"
            dist = sum(Dm[0][r[0]] + sum(Dm[a][b] for a, b in zip(r, r[1:])) + Dm[r[-1]][0] for r in routes)
            if len(routes) <= p["m_veh"]:
                assert abs(ctx.obj(s) - round(dist, 3)) < 1e-6, "目标值 = 路线总里程"


def test_infeasible_order_gets_a_graded_penalty_not_a_crash():
    p, ctx = _ctx(12, 7)
    p2 = dict(p, m_veh=1)  # 一辆车装不下 → 任何访问序都切不进车队
    c2 = E._ES(p2)
    s = list(range(12))
    v = c2.obj(s)
    assert v > 200 and v == c2.obj(s)
    assert c2.routes(s)  # 页面仍能画出（不限车队的切分）


def test_metaheuristics_find_the_exact_optimum_on_a_small_instance():
    """7 客户可以穷举：最优 CVRP = 所有访问序的最优切分里的最小值。算法必须找到它。"""
    p, ctx = _ctx(7, 3)
    Dm = E._vrp_dist(ctx)
    opt = min(E.vrp_split(Dm, p["demand"], p["cap"], p["m_veh"], list(t))[0] or 1e9
              for t in itertools.permutations(range(1, 8)))
    found = {}
    for algo in ("sa", "hc", "pk_pso"):
        D.domain_start("entryseq", json.dumps(p), algo, json.dumps({"max_iter": 150, "seed": 3}))
        last = None
        while True:
            st = D.domain_step()
            if st is None:
                break
            last = json.loads(st)
        found[algo] = last["best"]
        assert last["best"] >= opt - 1e-3, "不可能比穷举最优更好"
        assert last["routes"], "状态里带着路线"
    assert min(found.values()) <= opt + 1e-3, f"没有任何算法找到最优 {opt}：{found}"


def test_states_carry_routes_that_match_the_reported_best():
    p, ctx = _ctx(12, 7)
    D.domain_start("entryseq", json.dumps(p), "sa", json.dumps({"max_iter": 30, "seed": 1}))
    last = None
    while True:
        st = D.domain_step()
        if st is None:
            break
        last = json.loads(st)
    Dm = E._vrp_dist(ctx)
    dist = sum(Dm[0][r[0]] + sum(Dm[a][b] for a, b in zip(r, r[1:])) + Dm[r[-1]][0] for r in last["routes"])
    assert abs(dist - last["best"]) < 1e-2

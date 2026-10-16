# -*- coding: utf-8 -*-
"""vrptw 词条 = 带（硬）时间窗的车辆路径：解 = 客户访问序，解码 = 在「时间上合法的连续段」上做 Prins 最优切分。

时间窗的约束比容量难写对：早到要等、晚到不行、还要在仓库关门前回来。这里用独立的穷举 / 逐步模拟核对解码，
而不是只比较算法自己上报的数字。"""
import copy
import itertools
import json
import math
import os
import random
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "py"))

import domains as D  # noqa: E402
import entryseq as E  # noqa: E402
import registry as REG  # noqa: E402
import validate as V  # noqa: E402

EPS = 1e-9


def _ctx(n, seed):
    p = E.es_make("vrptw", n, seed)
    return p, E._ES(p)


def _route_cost(p, route):
    """独立的逐步模拟：返回这条路线的里程；窗口 / 容量 / 仓库关门任何一条违反就返回 None。"""
    pts, dem, e, l, svc = p["pts"], p["demand"], p["e"], p["l"], p["svc"]
    if sum(dem[c] for c in route) > p["cap"]:
        return None
    t, pos, dist = 0.0, 0, 0.0
    for c in route:
        d = math.dist(pts[pos], pts[c])
        t += d
        dist += d
        if t > l[c] + EPS:
            return None
        t = max(t, e[c]) + svc[c]
        pos = c
    back = math.dist(pts[pos], pts[0])
    if t + back > l[0] + EPS:
        return None
    return dist + back


def _brute_split(p, tour, K):
    """穷举所有「在间隙处切或不切」的方案，每一段用逐步模拟判可行——比 DP 笨但不可能错。"""
    n = len(tour)
    best = float("inf")
    for mask in range(1 << (n - 1)):
        cuts = [i + 1 for i in range(n - 1) if mask >> i & 1]
        if len(cuts) + 1 > K:
            continue
        total, prev, ok = 0.0, 0, True
        for c in cuts + [n]:
            cost = _route_cost(p, tour[prev:c])
            if cost is None:
                ok = False
                break
            total += cost
            prev = c
        if ok:
            best = min(best, total)
    return best


def run(p, algo, iters=100, seed=3):
    D.domain_start("entryseq", json.dumps(p), algo, json.dumps({"max_iter": iters, "seed": seed}))
    last = None
    while True:
        s = D.domain_step()
        if s is None:
            return last
        last = json.loads(s)


# ---------------------------------------------------------------- 模型与实例
def test_registered_as_a_standard_model_and_appears_in_the_registry():
    assert REG.fidelity("entryseq", "vrptw")["level"] == "standard"
    assert ("entryseq", "vrptw") in list(REG.cases())


def test_instances_are_well_formed_and_every_customer_can_be_served_alone():
    for n in (5, 12, 25, 40):
        for seed in (1, 7, 13):
            p = E.es_make("vrptw", n, seed)
            k = p["n"]
            assert k == n and all(len(p[key]) == k + 1 for key in ("pts", "demand", "e", "l", "svc"))
            assert p["pts"][0] == [50.0, 50.0] and p["e"][0] == 0 and p["svc"][0] == 0 and p["demand"][0] == 0
            assert p["l"][0] > 0 and p["m_veh"] * p["cap"] >= sum(p["demand"]) and p["cap"] >= max(p["demand"])
            for i in range(1, k + 1):
                assert 0 <= p["e"][i] < p["l"][i] and p["l"][i] - p["e"][i] >= 14.9  # 窗宽 30..60；贴着 0 时刻的窗被截成至少一半
                assert _route_cost(p, [i]) is not None, f"客户 {i} 单独跑一趟都不可行（seed {seed}, n {n}）"


def test_a_fleet_feasible_solution_exists_by_construction():
    """时间窗是围着「一组满足容量的参考路线」的到达时刻造的，所以至少有一个车队内可行的解——算法应当能找到。"""
    for seed in (1, 2, 3, 7):
        p = E.es_make("vrptw", 12, seed)
        runs = [run(p, a, iters=120, seed=s) for a in ("ga", "ts") for s in (1, 2)]
        assert any(r["within_fleet"] for r in runs), f"seed {seed}: 没有算法找到车队内的可行解"


# ---------------------------------------------------------------- 解码正确性
def test_split_equals_brute_force_on_random_tours():
    rng = random.Random(5)
    for seed in (1, 2, 3):
        p, ctx = _ctx(8, seed)
        for _ in range(20):
            t = rng.sample(range(1, p["n"] + 1), p["n"])
            arcs = E._vrptw_arcs_of(ctx, [x - 1 for x in t])
            got, spans = E.vrptw_split(arcs, p["n"], p["m_veh"])
            want = _brute_split(p, t, p["m_veh"])
            if want == float("inf"):
                assert got is None, "穷举说切不进车队，DP 却给出了方案"
            else:
                assert got == pytest.approx(want, abs=1e-6), (seed, t, got, want)
                routes = [t[i:j] for i, j in spans]
                assert sorted(c for r in routes for c in r) == sorted(t)
                assert sum(_route_cost(p, r) for r in routes) == pytest.approx(got, abs=1e-6)


def test_unlimited_fleet_split_is_a_lower_bound_and_always_exists():
    rng = random.Random(9)
    p, ctx = _ctx(10, 4)
    for _ in range(30):
        t = rng.sample(range(1, p["n"] + 1), p["n"])
        arcs = E._vrptw_arcs_of(ctx, [x - 1 for x in t])
        free, used, spans = E.vrptw_free_split(arcs, p["n"])
        assert free < float("inf") and used == len(spans)
        fleet, _ = E.vrptw_split(arcs, p["n"], p["m_veh"])
        if fleet is not None:
            assert free <= fleet + 1e-6
        assert free == pytest.approx(_brute_split(p, t, p["n"]), abs=1e-6)


def test_objective_penalises_tours_that_do_not_fit_the_fleet():
    p, ctx = _ctx(6, 2)
    fits, over = [], []
    for t in itertools.permutations(range(6)):
        d = ctx.detail(list(t))
        (fits if d["within_fleet"] else over).append(ctx.obj(list(t)))
    assert fits and over, "6 个客户的全部访问序里，两种情形都应出现，才能检验惩罚"
    # 切不进车队的访问序按「不限车队里程 + 每多用一辆车 200」计，所以必然差于同实例里最好的车队内解
    assert min(over) > min(fits)
    for t in itertools.permutations(range(6)):
        arcs = E._vrptw_arcs_of(ctx, list(t))
        free, used, _ = E.vrptw_free_split(arcs, 6)
        if E.vrptw_split(arcs, 6, p["m_veh"])[0] is None:
            assert ctx.obj(list(t)) == pytest.approx(free + 200.0 * max(1, used - p["m_veh"]), abs=1e-3)
            break


def test_global_optimum_over_all_orders_matches_independent_exhaustive_search():
    """任何一组路线都能首尾相接成一个访问序，所以「所有排列的最优切分」就是全局最优；
    用逐步模拟的穷举独立算一遍，与目标函数一致，且算法能找到它。"""
    for seed in (1, 2):
        p, ctx = _ctx(6, seed)
        want = min(_brute_split(p, list(t), p["m_veh"]) for t in itertools.permutations(range(1, 7)))
        got = min(ctx.obj([x - 1 for x in t]) for t in itertools.permutations(range(1, 7)))
        assert got == pytest.approx(want, abs=1e-3), (seed, got, want)
        best = min(run(p, a, iters=80, seed=s)["best"] for a in ("sa", "ga", "ts") for s in (1, 2))
        assert best == pytest.approx(want, abs=1e-3)


def test_time_windows_actually_bind():
    """同一批点和需求，去掉时间窗后的最优里程必须更短（否则时间窗是摆设）。"""
    strict = 0
    for seed in (1, 2, 3, 4):
        p, _ = _ctx(7, seed)
        relaxed = copy.deepcopy(p)
        relaxed["e"] = [0.0] * len(p["e"])
        relaxed["l"] = [1e9] * len(p["l"])
        tw = min(_brute_split(p, list(t), p["m_veh"]) for t in itertools.permutations(range(1, 8)))
        free = min(_brute_split(relaxed, list(t), p["m_veh"]) for t in itertools.permutations(range(1, 8)))
        assert tw >= free - 1e-6
        strict += tw > free + 1e-6
    assert strict >= 3, "时间窗应在多数实例上抬高最优里程"


# ---------------------------------------------------------------- 页面用的 detail
def test_detail_schedule_is_a_valid_timetable():
    p, ctx = _ctx(14, 7)
    last = run(p, "ga", iters=100)
    routes, sched = last["routes"], last["sched"]
    assert len(routes) == len(sched) and sorted(c for r in routes for c in r) == list(range(1, p["n"] + 1))
    total, waits = 0.0, 0.0
    for r, sc in zip(routes, sched):
        cost = _route_cost(p, r)
        assert cost is not None, "页面画出的路线必须是时间上可行的"
        total += cost
        pos = 0
        for c, (arr, start, leave) in zip(r, sc):
            assert arr <= p["l"][c] + 0.01 and start >= p["e"][c] - 0.01 and start >= arr - 0.01
            assert leave == pytest.approx(start + p["svc"][c], abs=0.01)
            waits += start - arr
    if last["within_fleet"]:
        assert total == pytest.approx(last["best"], abs=0.01) and len(routes) <= p["m_veh"]
    assert last["wait"] == pytest.approx(waits, abs=0.05)


# ---------------------------------------------------------------- 校验
def test_validator_accepts_presets_and_explains_infeasible_data():
    p = E.es_make("vrptw", 8, 7)
    assert V.validate("entryseq", p, variant="vrptw", dry_run=True)["ok"]

    def err(mutate):
        q = copy.deepcopy(p)
        mutate(q)
        r = V.validate("entryseq", q, variant="vrptw")
        assert not r["ok"]
        return r["errors"][0]

    assert err(lambda q: q["l"].__setitem__(2, q["e"][2] - 1))["path"].startswith("e[2]")
    assert "永远来不及" in err(lambda q: (q["e"].__setitem__(3, 0.0), q["l"].__setitem__(3, 1.0)))["msg"]
    assert err(lambda q: q.__setitem__("e", q["e"][:-1]))["path"] == "e"
    assert "装不下" in err(lambda q: q.__setitem__("m_veh", 1))["msg"]
    assert "关门" in err(lambda q: q["l"].__setitem__(0, 20))["msg"]


def test_browser_wide_algorithm_set_excludes_the_divergent_one():
    keys = [a["key"] for a in json.loads(D.domain_list("entryseq", {"variant": "vrptw"}))["algos"]]
    assert "pk_sma" not in keys and "ga" in keys and "ts" in keys and "pk_pso" in keys


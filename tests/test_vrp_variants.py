# -*- coding: utf-8 -*-
"""vrpstw（软时间窗）与 mdvrp（多车场）：两个 VRP 变体的解码与模型，用独立的穷举 / 逐步模拟核对，不信算法自己上报的数字。"""
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


def run(p, algo, iters=100, seed=3):
    D.domain_start("entryseq", json.dumps(p), algo, json.dumps({"max_iter": iters, "seed": seed}))
    last = None
    while True:
        s = D.domain_step()
        if s is None:
            return last
        last = json.loads(s)


def _cuts(tour, K):
    """所有「在间隙处切或不切」的分段方案（至多 K 段）。"""
    n = len(tour)
    for mask in range(1 << (n - 1)):
        cuts = [i + 1 for i in range(n - 1) if mask >> i & 1]
        if len(cuts) + 1 > K:
            continue
        segs, prev = [], 0
        for c in cuts + [n]:
            segs.append(tour[prev:c])
            prev = c
        yield segs


# ================================================================ 软时间窗
def _soft_route_cost(p, route, depot=0):
    """逐步模拟：返回 里程 + lam × 迟到（客户窗 + 回仓晚于关门）；超载返回 None。"""
    if sum(p["demand"][c] for c in route) > p["cap"]:
        return None
    t, pos, dist, late = 0.0, depot, 0.0, 0.0
    for c in route:
        d = math.dist(p["pts"][pos], p["pts"][c])
        t += d
        dist += d
        late += max(0.0, t - p["l"][c])
        t = max(t, p["e"][c]) + p["svc"][c]
        pos = c
    back = math.dist(p["pts"][pos], p["pts"][depot])
    dist += back
    late += max(0.0, t + back - p["l"][0])
    return dist + p["lam"] * late


def _brute_soft_split(p, tour, K):
    best = float("inf")
    for segs in _cuts(tour, K):
        costs = [_soft_route_cost(p, sg) for sg in segs]
        if None not in costs:
            best = min(best, sum(costs))
    return best


def _soft(n, seed, lam=None):
    p = E.es_make("vrpstw", n, seed)
    if lam is not None:
        p["lam"] = lam
    return p, E._ES(p)


def test_vrpstw_is_registered_standard_and_shares_the_instances_of_vrptw():
    assert REG.fidelity("entryseq", "vrpstw")["level"] == "standard"
    assert REG.fidelity("entryseq", "mdvrp")["level"] == "standard"
    a, b = E.es_make("vrpstw", 12, 5), E.es_make("vrptw", 12, 5)
    assert a.pop("lam") == 2.0 and a.pop("variant") == "vrpstw"
    b.pop("variant")
    assert a == b, "软窗与硬窗用同一批点、需求与时间窗，才能比较"


def test_soft_split_equals_brute_force_on_random_tours():
    rng = random.Random(4)
    for seed in (1, 2, 3):
        p, ctx = _soft(8, seed)
        for _ in range(15):
            t = rng.sample(range(1, p["n"] + 1), p["n"])
            arcs = E._vrptw_arcs_of(ctx, [x - 1 for x in t])
            got, spans = E.vrptw_split(arcs, p["n"], p["m_veh"])
            want = _brute_soft_split(p, t, p["m_veh"])
            if want == float("inf"):
                assert got is None
            else:
                assert got == pytest.approx(want, abs=1e-6), (seed, t)
                assert sum(_soft_route_cost(p, t[i:j]) for i, j in spans) == pytest.approx(got, abs=1e-6)


def _opt(p, n):
    ctx = E._ES(p)
    return min(ctx.obj([x - 1 for x in t]) for t in itertools.permutations(range(1, n + 1)))


def test_soft_windows_limits_lam_zero_is_cvrp_and_huge_lam_is_the_hard_model():
    for seed in (1, 2, 3):
        p, _ = _soft(6, seed)
        hard = E.es_make("vrptw", 6, seed)
        soft_opt = _opt(p, 6)
        hard_opt = _opt(hard, 6)
        assert soft_opt <= hard_opt + 1e-6, "硬窗的可行解在软窗里零迟到，软窗的最优不会更差"
        # lam = 0：窗口不起作用，等于只看里程的 CVRP（同一批点、需求、容量、车数）
        free = dict(p, lam=0.0)
        cvrp = E.es_make("vrp", 6, seed)
        cvrp.update(pts=p["pts"], demand=p["demand"], cap=p["cap"], m_veh=p["m_veh"], n=6)
        assert _opt(free, 6) == pytest.approx(_opt_cvrp(cvrp, 6), abs=1e-3)
        # lam 极大：任何迟到都不划算，等于硬窗
        assert _opt(dict(p, lam=1e6), 6) == pytest.approx(hard_opt, abs=1e-2)


def _opt_cvrp(p, n):
    ctx = E._ES(p)
    return min(ctx.obj([x - 1 for x in t]) for t in itertools.permutations(range(1, n + 1)))


def test_the_optimums_lateness_never_increases_with_the_penalty():
    """经济学上的单调性：罚得越重，最优方案里的迟到越少（弱单调）。"""
    for seed in (1, 2, 3):
        late = []
        for lam in (0.0, 0.5, 2.0, 10.0, 1000.0):
            p, ctx = _soft(6, seed, lam)
            best = min(itertools.permutations(range(6)), key=lambda t: ctx.obj(list(t)))
            late.append(ctx.detail(list(best))["late"])
        assert all(b <= a + 1e-6 for a, b in zip(late, late[1:])), (seed, late)


def test_soft_detail_matches_an_independent_simulation_and_algorithms_find_the_optimum():
    p, ctx = _soft(6, 2)
    want = _opt(p, 6)
    best = min(run(p, a, iters=80, seed=s)["best"] for a in ("sa", "ga", "ts") for s in (1, 2))
    assert best == pytest.approx(want, abs=1e-3)
    p12 = E.es_make("vrpstw", 12, 7)
    last = run(p12, "ga", iters=120)
    if last["within_fleet"]:
        sim = sum(_soft_route_cost(p12, r) for r in last["routes"])
        assert sim == pytest.approx(last["best"], abs=0.01)
        assert last["dist"] + p12["lam"] * last["late"] == pytest.approx(last["best"], abs=0.02)


# ================================================================ 多车场
def _mdvrp(n, seed):
    p = E.es_make("mdvrp", n, seed)
    return p, E._ES(p)


def _md_route_cost(p, depot, route):
    if sum(p["demand"][c] for c in route) > p["cap"]:
        return None
    pts = [p["pts"][depot]] + [p["pts"][c] for c in route] + [p["pts"][depot]]
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def _md_group_cost(p, depot, custs, K):
    """某个仓库服务一批客户的最小里程：枚举所有访问序与分段（至多 K 辆车）。"""
    if not custs:
        return 0.0
    best = float("inf")
    for perm in itertools.permutations(custs):
        for segs in _cuts(list(perm), K):
            costs = [_md_route_cost(p, depot, sg) for sg in segs]
            if None not in costs:
                best = min(best, sum(costs))
    return best


def _md_split_cost(p, depot, tour, K):
    """给定访问序（不重排）的最优分段：枚举所有切法。该仓库切不进 K 辆车返回 inf。"""
    if not tour:
        return 0.0
    best = float("inf")
    for segs in _cuts(list(tour), K):
        costs = [_md_route_cost(p, depot, sg) for sg in segs]
        if None not in costs:
            best = min(best, sum(costs))
    return best


def test_mdvrp_instances_and_validator():
    for n in (5, 12, 13, 40):
        p = E.es_make("mdvrp", n, 7)
        k = max(5, min(n, 40))
        assert p["D"] == (2 if k <= 12 else 3) and p["n"] == k + p["D"] - 1 and len(p["pts"]) == p["n"] + 1 == len(p["demand"])
        assert all(d == 0 for d in p["demand"][:p["D"]]) and p["D"] * p["m_dep"] * p["cap"] >= sum(p["demand"])
        assert V.validate("entryseq", p, variant="mdvrp", dry_run=True)["ok"]

    def err(mutate):
        q = E.es_make("mdvrp", 8, 7)
        mutate(q)
        r = V.validate("entryseq", q, variant="mdvrp")
        assert not r["ok"]
        return r["errors"][0]

    assert err(lambda q: q.__setitem__("D", 0))["path"] == "D"
    assert err(lambda q: q["demand"].__setitem__(0, 3))["path"] == "demand"
    assert "装不下" in err(lambda q: (q.__setitem__("m_dep", 1), q.__setitem__("demand", [0] * q["D"] + [q["cap"]] * (q["n"] + 1 - q["D"]))))["msg"]


def test_mdvrp_decode_equals_independent_brute_force_per_depot():
    rng = random.Random(6)
    for seed in (1, 2, 3):
        p, ctx = _mdvrp(6, seed)  # D = 2，排列长 7：6 个客户 + 1 个分隔符
        k = p["n"] + 1 - p["D"]
        for _ in range(15):
            s = rng.sample(range(p["n"]), p["n"])
            groups, g = [[] for _ in range(p["D"])], 0
            for v in s:
                if v >= k:
                    g += 1
                else:
                    groups[g].append(p["D"] + v)  # pts 下标
            want = 0.0
            for d, custs in enumerate(groups):
                c = _md_split_cost(p, d, custs, p["m_dep"])
                if c == float("inf"):  # 该仓库切不进自己的车队：引擎按罚分计，这里只核对「能切进」的情形
                    want = None
                    break
                want += c
            if want is None:
                continue
            assert ctx.obj(s) == pytest.approx(want, abs=1e-3), (seed, s)


def test_mdvrp_global_optimum_matches_exhaustive_search_over_assignments_orders_and_cuts():
    p, ctx = _mdvrp(5, 3)  # 5 个客户、2 个仓库
    k = 5
    want = float("inf")
    for assign in itertools.product(range(p["D"]), repeat=k):
        groups = [[p["D"] + i for i in range(k) if assign[i] == d] for d in range(p["D"])]
        total = sum(_md_group_cost(p, d, groups[d], p["m_dep"]) for d in range(p["D"]))
        want = min(want, total)
    got = min(ctx.obj(list(t)) for t in itertools.permutations(range(p["n"])))
    assert got == pytest.approx(want, abs=1e-3), (got, want)
    best = min(run(p, a, iters=80, seed=s)["best"] for a in ("sa", "ga", "ts") for s in (1, 2))
    assert best == pytest.approx(want, abs=1e-3)


def test_mdvrp_detail_routes_are_valid_and_respect_every_depots_fleet():
    p, ctx = _mdvrp(14, 7)
    last = run(p, "ga", iters=120)
    routes, owner = last["routes"], last["route_depot"]
    assert len(routes) == len(owner)
    served = sorted(c for r in routes for c in r)
    assert served == list(range(p["D"], p["n"] + 1)), "每个客户恰好被服务一次，且不会把仓库当客户"
    total = 0.0
    for r, d in zip(routes, owner):
        cost = _md_route_cost(p, d, r)
        assert cost is not None, "路线超载"
        total += cost
    if last["within_fleet"]:
        assert total == pytest.approx(last["best"], abs=0.01)
        assert all(owner.count(d) <= p["m_dep"] for d in range(p["D"]))
    assert sum(last["per_depot"]) == len(routes)


def test_the_divergent_algorithm_is_withdrawn_for_the_vrp_family():
    for v in ("vrp", "vrptw", "vrpstw", "mdvrp"):
        keys = [a["key"] for a in json.loads(D.domain_list("entryseq", {"variant": v}))["algos"]]
        assert "pk_sma" not in keys and "ga" in keys and "ts" in keys, v

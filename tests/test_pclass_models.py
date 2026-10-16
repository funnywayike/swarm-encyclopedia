# -*- coding: utf-8 -*-
"""P 类对照问题（最小生成树、最短路、最大流、最小费用流、一般图匹配、拓扑排序）与多序列比对的标准模型。

旧模型的目标函数有的根本不看解（最小费用流），有的与问题无关（多序列比对 = 排列的不动点数）。
现在每个实例都带着「精确算法的最优值」，这里用独立写的算法逐个核对，并检查：任何解的目标都不会优于它（罚函数是精确的）。"""
import itertools
import os
import random
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "py"))

import entryseq as E  # noqa: E402


def make(variant, n=10, seed=7):
    p = E.es_make(variant, n, seed)
    return p, E.es_ctx(p)


def _rand_vec(rng, n):
    return [rng.uniform(-5, 5) for _ in range(n)]


@pytest.mark.parametrize("seed", [1, 7, 21])
def test_mst_opt_matches_prim_and_the_weight_order_reaches_it(seed):
    p, c = make("mst", 10, seed)
    n, adj = p["n_nodes"], {}
    for a, b, w in p["edges"]:
        adj.setdefault(a, []).append((b, w))
        adj.setdefault(b, []).append((a, w))
    seen, tot, frontier = {0}, 0, list(adj[0])
    while len(seen) < n:  # Prim（独立实现）
        w, v = min((w, v) for v, w in frontier if v not in seen)
        seen.add(v)
        tot += w
        frontier += adj[v]
    assert p["opt"] == tot
    order = sorted(range(p["n"]), key=lambda k: p["edges"][k][2])
    assert c.obj(order) == tot
    rng = random.Random(0)
    assert all(c.obj(rng.sample(range(p["n"]), p["n"])) >= tot for _ in range(100))
    d = c.detail(order)
    assert len(d["tree"]) == n - 1 and d["weight"] == tot


@pytest.mark.parametrize("seed", [1, 7, 21])
def test_shortest_path_opt_matches_bellman_ford_and_optimal_priorities_walk_it(seed):
    p, c = make("shortestpath", 12, seed)
    n, INF = p["n"], 10 ** 9
    dist, prev = [INF] * n, [None] * n
    dist[p["src"]] = 0
    for _ in range(n):
        for a, b, w in p["edges"]:
            for x, y in ((a, b), (b, a)):
                if dist[x] + w < dist[y]:
                    dist[y], prev[y] = dist[x] + w, x
    assert p["opt"] == dist[p["dst"]]
    path, v = [], p["dst"]
    while v is not None:
        path.append(v)
        v = prev[v]
    path.reverse()
    keys = [0.0] * n
    for i, v in enumerate(path):
        keys[v] = 100.0 - i  # 沿最短路优先级递减：每步走向路径上的下一个点
    assert c.obj(keys) == p["opt"]
    rng = random.Random(0)
    for _ in range(100):
        assert c.obj(_rand_vec(rng, n)) >= p["opt"]  # 不会比最优更短（失败按 4000 计）


def _dfs_maxflow(nn, arcs, s, t):
    cap = {}
    for a, b, c in arcs:
        cap[(a, b)] = cap.get((a, b), 0) + c
        cap.setdefault((b, a), 0)
    flow = 0
    while True:
        stack, seen, par = [s], {s}, {}
        while stack and t not in seen:
            u = stack.pop()
            for (x, y), c in cap.items():
                if x == u and c > 0 and y not in seen:
                    seen.add(y)
                    par[y] = u
                    stack.append(y)
        if t not in seen:
            return flow
        path, v = [], t
        while v != s:
            path.append((par[v], v))
            v = par[v]
        push = min(cap[e] for e in path)
        for x, y in path:
            cap[(x, y)] -= push
            cap[(y, x)] += push
        flow += push


@pytest.mark.parametrize("seed", [1, 7, 21])
def test_max_flow_opt_matches_an_independent_dfs_augmentation(seed):
    p, c = make("maxflow", 10, seed)
    assert p["opt"] == _dfs_maxflow(p["n_nodes"], p["arcs"], p["src"], p["snk"]) > 0
    rng = random.Random(0)
    best = min(c.obj(_rand_vec(rng, p["n"])) for _ in range(2000))
    assert best >= -p["opt"]  # 精确罚函数：违反守恒换不到更多的流
    assert c.obj([-5.0] * p["n"]) == 0  # 零流是合法流


@pytest.mark.parametrize("seed", [1, 7])
def test_min_cost_flow_opt_matches_an_independent_successive_shortest_paths(seed):
    """另写一遍逐次最短增广路（残量图上的 Bellman–Ford），并要求任何向量的目标都不低于它。"""
    p, c = make("mincostflow", 8, seed)
    nn, arcs = p["n_nodes"], p["arcs"]
    res = [[a[0], a[1], a[2], a[3]] for a in arcs] + [[a[1], a[0], 0, -a[3]] for a in arcs]
    sent, cost = 0, 0
    while sent < p["need"]:
        dist = [10 ** 9] * nn
        dist[p["src"]] = 0
        prev = [None] * nn
        for _ in range(nn):
            for k, (u, v, cp, cs) in enumerate(res):
                if cp > 0 and dist[u] + cs < dist[v]:
                    dist[v], prev[v] = dist[u] + cs, k
        if dist[p["snk"]] >= 10 ** 9:
            break
        path, v = [], p["snk"]
        while v != p["src"]:
            k = prev[v]
            path.append(k)
            v = res[k][0]
        push = min(min(res[k][2] for k in path), p["need"] - sent)
        for k in path:
            res[k][2] -= push
            twin = k + len(arcs) if k < len(arcs) else k - len(arcs)
            res[twin][2] += push
        sent += push
        cost += push * dist[p["snk"]]
    assert sent == p["need"] and p["opt"] == cost
    rng = random.Random(1)
    assert min(c.obj(_rand_vec(rng, p["n"])) for _ in range(3000)) >= cost - 1e-6


@pytest.mark.parametrize("seed", [1, 7, 21])
def test_matching_opt_matches_edge_subset_search(seed):
    p, c = make("gmatch", 8, seed)
    edges = p["edges"]
    best, best_set = 0, []

    def go(i, used, w, chosen):
        nonlocal best, best_set
        if w > best:
            best, best_set = w, list(chosen)
        for k in range(i, len(edges)):
            a, b, wt = edges[k]
            if a not in used and b not in used:
                go(k + 1, used | {a, b}, w + wt, chosen + [k])
    go(0, frozenset(), 0, [])
    assert p["opt"] == best
    rng = random.Random(0)
    assert all(-c.obj(rng.sample(range(len(edges)), len(edges))) <= best for _ in range(100))
    perm = best_set + [k for k in range(len(edges)) if k not in best_set]  # 最优匹配的边排前面，贪心解码就拿到最优
    assert -c.obj(perm) == best


def test_topsort_has_a_valid_order_and_random_orders_violate_arcs():
    p, c = make("topsort", 12, 7)
    indeg = {v: 0 for v in range(p["n"])}
    for a, b in p["arcs"]:
        indeg[b] += 1
    order, q = [], [v for v in indeg if indeg[v] == 0]
    while q:  # Kahn（独立实现）
        u = q.pop()
        order.append(u)
        for a, b in p["arcs"]:
            if a == u:
                indeg[b] -= 1
                if indeg[b] == 0:
                    q.append(b)
    assert len(order) == p["n"] and c.obj(order) == 0 == p["opt"]
    rng = random.Random(0)
    assert sum(c.obj(rng.sample(range(p["n"]), p["n"])) > 0 for _ in range(50)) >= 45  # 随机排列几乎总违反弧


def _sp_exhaustive(seqs):
    """独立实现：对 3 条序列做记忆化递归，在所有「列类型」序列上取和对得分的最大值。"""
    from functools import lru_cache
    sc = E._msa_pair
    A, B, C = seqs

    @lru_cache(None)
    def go(i, j, k):
        if (i, j, k) == (len(A), len(B), len(C)):
            return 0
        best = -10 ** 9
        for di, dj, dk in itertools.product((0, 1), repeat=3):
            if not (di or dj or dk) or i + di > len(A) or j + dj > len(B) or k + dk > len(C):
                continue
            x, y, z = (A[i] if di else "-"), (B[j] if dj else "-"), (C[k] if dk else "-")
            best = max(best, sc(x, y) + sc(x, z) + sc(y, z) + go(i + di, j + dj, k + dk))
        return best
    return go(0, 0, 0)


def test_msa_opt_matches_an_independent_dp_and_no_bitstring_beats_it():
    p, c = make("msa", 10, 7)
    assert p["opt"] == _sp_exhaustive(tuple(p["seqs"]))
    rng = random.Random(0)
    for _ in range(500):
        s = [rng.randint(0, 1) for _ in range(p["n"])]
        assert -c.obj(s) <= p["opt"]
    W = p["W"]
    s = []
    for seq in p["seqs"]:  # 无空位的左对齐也是一种比对
        s += [1] * len(seq) + [0] * (W - len(seq))
    rows = E._msa_rows(c, s)
    assert len({len(r) for r in rows}) == 1 and [r.replace("-", "") for r in rows] == p["seqs"]
    assert c.detail(s)["sp"] == -c.obj(s)


def test_the_new_models_are_registered_standard_except_msa():
    for v in ("mst", "shortestpath", "maxflow", "mincostflow", "gmatch", "topsort"):
        assert E.FIDELITY[v]["level"] == "standard", v
    assert E.FIDELITY["msa"]["level"] == "simplified"
    assert E.ENCODING["shortestpath"] == E.ENCODING["maxflow"] == E.ENCODING["mincostflow"] == "real"
    assert E.ENCODING["msa"] == "bits"

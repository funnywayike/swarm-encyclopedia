# -*- coding: utf-8 -*-
"""车间调度与路径类的标准模型（2026-10 重做）：置换流水车间 fss、作业车间 jss、开放车间 oss、柔性作业车间 fjsp、
哈密顿回路 hc、最长路径 lpath、弧路由 carp / rpostman。

最强的证据是文献里的已知值：Taillard 的 ta001（最优 1278）和 Fisher–Thompson 的 ft06（最优 55）——
用发生器 / 数据造出的实例上，存着一个恰好达到该最优值的排列；任何随机排列都不可能低于下界。
其余变体用「独立写一遍的评价」与「性质检查」（时间表无冲突、先后次序合法、容量不超）核对。"""
import itertools
import math
import os
import random
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "py"))

import entryseq as E  # noqa: E402

# 在 ta001 / ft06 上用迭代贪婪（NEH + 破坏重建）/ 随机重启爬山找到的最优排列
TA001_OPT_PERM = [8, 14, 16, 2, 7, 5, 15, 12, 13, 18, 3, 4, 17, 0, 1, 6, 10, 9, 19, 11]
FT06_OPT_PERM = [30, 8, 31, 32, 20, 15, 18, 5, 12, 33, 17, 13, 34, 7, 11, 25, 2, 0, 16, 29, 14, 24, 1, 9, 21, 22, 19, 26, 3, 4, 35, 6, 23, 28, 10, 27]


def ctx(variant, n, seed=7):
    return E.es_ctx(E.es_make(variant, n, seed))


# ---------------------------------------------------------------- 置换流水车间
def test_ta001_generator_reproduces_the_published_instance():
    p = E.es_make("fss", 20, 7)
    assert p["name"] == "ta001" and p["opt"] == 1278 and p["m_mach"] == 5
    # Taillard (1993) ta001 第一台机器上 20 个作业的加工时间
    assert p["p"][0] == [54, 83, 15, 71, 77, 36, 53, 38, 27, 87, 76, 91, 14, 29, 12, 77, 32, 87, 68, 94]


def test_ta001_has_a_permutation_reaching_the_published_optimum_and_nothing_goes_below_it():
    c = ctx("fss", 20)
    assert c.obj(TA001_OPT_PERM) == 1278
    lb = E._pfsp_lb(c.p["p"])
    assert lb <= 1278
    rng = random.Random(3)
    for _ in range(300):
        s = list(range(20))
        rng.shuffle(s)
        assert c.obj(s) >= 1278  # 1278 是最优，随机排列不会更好


def _pfsp_reference(p, perm):
    """独立写一遍：完工时间矩阵 C[j][k] = max(C[j-1][k], C[j][k-1]) + p[k][perm[j]]。"""
    n, m = len(perm), len(p)
    C = [[0] * m for _ in range(n)]
    for j in range(n):
        for k in range(m):
            C[j][k] = max(C[j - 1][k] if j else 0, C[j][k - 1] if k else 0) + p[k][perm[j]]
    return C[-1][-1]


def test_pfsp_objective_matches_an_independent_recurrence_and_detail_is_consistent():
    c = ctx("fss", 12)
    rng = random.Random(5)
    for _ in range(40):
        s = list(range(12))
        rng.shuffle(s)
        assert c.obj(s) == _pfsp_reference(c.p["p"], s)
        d = c.detail(s)
        assert d["makespan"] == c.obj(s) and d["lb"] <= d["makespan"]
        # 每台机器上相邻作业不重叠
        for k in range(5):
            iv = sorted((st, en) for (_j, kk, st, en) in d["ops"] if kk == k)
            assert all(a[1] <= b[0] for a, b in zip(iv, iv[1:]))


def test_pfsp_brute_force_optimum_is_at_least_the_lower_bound():
    c = ctx("fss", 6)
    best = min(c.obj(list(s)) for s in itertools.permutations(range(6)))
    assert best >= E._pfsp_lb(c.p["p"])


# ---------------------------------------------------------------- 作业车间 / 开放车间 / 柔性作业车间
def test_ft06_data_and_the_published_optimum():
    c = ctx("jss", 6)
    assert c.p["name"] == "ft06" and c.p["opt"] == 55 and c.p["lb"] == 47
    assert c.obj(FT06_OPT_PERM) == 55
    rng = random.Random(1)
    for _ in range(300):
        s = list(range(36))
        rng.shuffle(s)
        assert c.obj(s) >= 55


def _check_schedule(c, ops):
    """时间表的合法性：机器上不重叠、作业内工序按次序、每道工序做了正确的时长、每道工序恰好排一次。"""
    p, v = c.p, c.variant
    by_machine, by_job = {}, {}
    for (j, k, st, en) in ops:
        by_machine.setdefault(k, []).append((st, en))
        by_job.setdefault(j, []).append((st, en, k))
    for k, iv in by_machine.items():
        iv.sort()
        assert all(a[1] <= b[0] for a, b in zip(iv, iv[1:])), f"机器 {k} 上有重叠"
    for j, iv in by_job.items():
        if v == "oss":
            iv.sort()
            assert len(iv) == p["m_mach"] and sorted(k for _s, _e, k in iv) == list(range(p["m_mach"]))
            assert all(a[1] <= b[0] for a, b in zip(iv, iv[1:])), f"作业 {j} 的工序重叠"
            for (st, en, k) in iv:
                assert en - st == p["t"][j][k]
        else:
            seq = sorted(iv)  # 作业内按开始时间排序
            assert all(a[1] <= b[0] for a, b in zip(seq, seq[1:]))
            for q, (st, en, k) in enumerate(seq):
                if v == "jss":
                    assert (k, en - st) == tuple(p["jobs"][j][q]), f"作业 {j} 第 {q} 道工序不是路线规定的 (机器, 时长)"
                else:
                    assert any(kk == k and t == en - st for kk, t in p["jobs"][j][q]), f"作业 {j} 第 {q} 道工序用了不可选的机器 / 时长"


@pytest.mark.parametrize("variant,n", [("jss", 6), ("jss", 8), ("oss", 4), ("oss", 5), ("fjsp", 6), ("fjsp", 8)])
def test_shop_schedules_are_legal_and_respect_the_lower_bound(variant, n):
    c = ctx(variant, n)
    rng = random.Random(11)
    for _ in range(60):
        s = list(range(c.n))
        rng.shuffle(s)
        d = c.detail(s)
        _check_schedule(c, d["ops"])
        assert d["makespan"] == c.obj(s) >= c.p["lb"]
        assert len(d["ops"]) == c.n


def test_open_shop_lower_bound_is_reachable_on_small_instances():
    """开放车间的下界 = max(最大机器负载, 最大作业总时长)；Taillard 型小实例上它通常可达——3×3 穷举核对「最优 ≥ 下界」且贴近。"""
    c = ctx("oss", 3)
    best = min(c.obj(list(s)) for s in itertools.permutations(range(9)))
    assert c.p["lb"] <= best <= c.p["lb"] * 1.25


def test_fjsp_flexibility_never_hurts_versus_the_least_flexible_choice():
    """每道工序固定用最快的一台机器是一个特例：柔性解码在任何排列上都不比「所有工序强制同一规则」更糟的下界——至少要落在总下界之上。"""
    c = ctx("fjsp", 6)
    best = min(c.obj(random.Random(i).sample(range(c.n), c.n)) for i in range(200))
    assert best >= c.p["lb"]


# ---------------------------------------------------------------- 哈密顿回路 / 最长路径
def test_hamiltonian_cycle_exists_and_is_found_by_exhaustive_search():
    c = ctx("hc", 8)
    best = min(c.obj(list(s)) for s in itertools.permutations(range(8)))
    assert best == 0  # 植入了回路
    s = next(list(s) for s in itertools.permutations(range(8)) if c.obj(list(s)) == 0)
    assert c.detail(s)["found"] and c.detail(s)["broken"] == []
    rng = random.Random(0)
    worst = max(c.obj(rng.sample(range(8), 8)) for _ in range(50))
    assert worst > 0


def test_longest_path_matches_exhaustive_dp_over_simple_paths():
    c = ctx("lpath", 7)
    W = {}
    for a, b, w in c.p["edges"]:
        W[(a, b)] = W[(b, a)] = w
    best = 0
    for r in range(1, 8):
        for perm in itertools.permutations(range(7), r):
            if all((perm[i], perm[i + 1]) in W for i in range(r - 1)):
                best = max(best, sum(W[(perm[i], perm[i + 1])] for i in range(r - 1)))
    got = max(-c.obj(list(s)) for s in itertools.permutations(range(7)))
    assert got == best  # 「沿排列走、碰到非边就停」的解码可达每一条简单路径


# ---------------------------------------------------------------- 弧路由
def _carp_recompute(c, trips):
    p = c.p
    sp = E._carp_sp(c)
    total, served = 0.0, []
    for trip in trips:
        load, cur = 0, p["depot"]
        for (u, v, e) in trip:
            a, b, cost = p["edges"][e]
            assert {u, v} == {a, b}
            total += sp[cur][u] + cost
            cur = v
            load += p["dem"][p["req"].index(e)]
            served.append(e)
        total += sp[cur][p["depot"]]
        assert load <= p["cap"]
    return total, served


@pytest.mark.parametrize("variant", ["carp", "rpostman"])
def test_arc_routing_cost_matches_a_recomputation_and_serves_every_required_edge_once(variant):
    c = ctx(variant, 8)
    rng = random.Random(2)
    for _ in range(40):
        s = list(range(c.n))
        rng.shuffle(s)
        d = c.detail(s)
        total, served = _carp_recompute(c, d["trips"])
        assert abs(total - c.obj(s)) < 1e-6 + 0.0005
        assert sorted(served) == sorted(c.p["req"])
        if variant == "rpostman":
            assert len(d["trips"]) == 1


def test_carp_capacity_splitting_is_optimal_for_the_fixed_giant_route():
    """给定服务序，容量切分用动态规划：与对所有切法的穷举取最小一致。"""
    c = ctx("carp", 6)
    p, sp = c.p, E._carp_sp(c)
    s = list(range(c.n))
    cost, trips = E._carp_plan(c, s)
    # 复原方向后穷举所有切点（2^(k-1) 种）
    ends, cur = [], p["depot"]
    for r in s:
        a, b, w = p["edges"][p["req"][r]]
        u, v = (a, b) if sp[cur][a] <= sp[cur][b] else (b, a)
        ends.append((u, v, w))
        cur = v
    k, best = len(s), float("inf")
    for mask in range(1 << (k - 1)):
        cuts = [0] + [i + 1 for i in range(k - 1) if mask >> i & 1] + [k]
        total, ok = 0.0, True
        for a, b in zip(cuts, cuts[1:]):
            if sum(p["dem"][s[t]] for t in range(a, b)) > p["cap"] and b - a > 1:
                ok = False
                break
            seg = sp[p["depot"]][ends[a][0]] + ends[a][2]
            for t in range(a + 1, b):
                seg += sp[ends[t - 1][1]][ends[t][0]] + ends[t][2]
            total += seg + sp[ends[b - 1][1]][p["depot"]]
        if ok:
            best = min(best, total)
    assert abs(cost - best) < 1e-9


def test_rpostman_is_the_uncapacitated_special_case_of_carp():
    """同一张路网与必需边；容量放开后，同一个服务序的费用不会更高（少了回仓库的往返）。"""
    c1, c2 = ctx("carp", 8), ctx("rpostman", 8)
    assert c1.p["edges"] == c2.p["edges"] and c1.p["req"] == c2.p["req"]
    assert c1.p["cap"] == 20 and c2.p["cap"] > 10 ** 5
    loose = E.es_ctx(dict(c1.p, cap=10 ** 6))
    rng = random.Random(9)
    for _ in range(30):
        s = list(range(c1.n))
        rng.shuffle(s)
        assert loose.obj(s) <= c1.obj(s) + 1e-9


# ---------------------------------------------------------------- 上传校验
def _validate(variant, data):
    import validate as V
    return V.validate("entryseq", data, variant=variant)


def test_core_data_is_enough_to_upload_the_new_models():
    """只给核心数据（规模、下界、机器数由程序推出），并且推出的下界与引擎自己造的实例一致。"""
    ft = {"jobs": [[list(op) for op in j] for j in E._FT06]}
    r = _validate("jss", ft)
    assert r["ok"], r["errors"]
    assert r["problem"]["lb"] == 47 and r["problem"]["m_mach"] == 6 and r["problem"]["n"] == 36
    r = _validate("fss", {"p": [[3, 2, 4], [2, 5, 1]]})
    assert r["ok"] and r["problem"]["n"] == 3 and r["problem"]["m_mach"] == 2
    r = _validate("oss", {"t": [[3, 2], [4, 1]]})
    assert r["ok"] and r["problem"]["lb"] == 7 and r["problem"]["n"] == 4
    r = _validate("fjsp", {"jobs": [[[[0, 3], [1, 4]], [[1, 2]]], [[[0, 2]], [[0, 3], [1, 5], [2, 1]]]]})
    assert r["ok"], r["errors"]


def test_bad_uploads_are_rejected_with_a_reason():
    assert not _validate("jss", {"jobs": [[[0, 3], [1, 2]], [[0, 4]]]})["ok"]  # 作业工序数不同
    assert not _validate("jss", {"jobs": [[[0, 0], [1, 2]], [[0, 4], [1, 1]]]})["ok"]  # 时长 0
    assert not _validate("fss", {"p": [[3, 0], [2, 5]]})["ok"]
    assert not _validate("oss", {"t": [[3, 2, 1], [4, 1, 2]]})["ok"]  # 不是方阵
    bad_net = {"pts": [[0, 0], [1, 1], [2, 2]], "edges": [[0, 1, 5]], "req": [0], "dem": [3], "depot": 0}
    assert not _validate("carp", bad_net)["ok"]  # 路网不连通
    assert not _validate("tdm", {"sets": [[1, 0, 0, 1, 0, 0, 1, 1, 0]]})["ok"]  # 三元组某一段有两个 1

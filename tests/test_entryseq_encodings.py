# -*- coding: utf-8 -*-
"""entryseq 的三种编码（排列 / 位向量 / 实数向量）各配各的算法集：
此前所有变体按排列处理，再靠撤下清单掩盖不适用的组合——位向量 / 排列的算法被喂了不属于它的编码，能跑、不报错、结果没有意义。"""
import itertools
import json
import os
import random
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "py"))

import domains as D  # noqa: E402
import entryseq as E  # noqa: E402

BITS, VEC = set(E.BIT_VARIANTS), set(E.VEC_VARIANTS)
PERM = [v for v in E.VARIANTS if v not in BITS and v not in VEC]


def keys(variant):
    return {a["key"] for a in json.loads(D.domain_list("entryseq", {"variant": variant}))["algos"]}


def run(variant, algo, p, iters=60, seed=3):
    D.domain_start("entryseq", json.dumps(p), algo, json.dumps({"max_iter": iters, "seed": seed}))
    last = None
    while True:
        st = D.domain_step()
        if st is None:
            return last
        last = json.loads(st)


def test_each_encoding_gets_exactly_its_own_algorithm_family():
    assert len(PERM) + len(BITS) + len(VEC) == len(E.VARIANTS) and BITS.isdisjoint(VEC)
    for v in PERM:
        k = keys(v)
        need = {a for a in ("ga", "ts", "sa", "hc", "random") if not D._is_withdrawn("entryseq", v, a)}
        assert need <= k and any(x.startswith("pk_") for x in k), v
        assert not any(x.startswith("bv_") for x in k) and "greedy" not in k, f"{v}：排列变体不该有位向量算法"
    for v in BITS:
        k = keys(v)
        need = {a for a in ("ga", "ts", "sa") if not D._is_withdrawn("entryseq", v, a)}
        assert need <= k and any(x.startswith("bv_") for x in k), v
        assert not any(x.startswith("pk_") for x in k), f"{v}：位向量变体不该有排列随机键算法"
    for v in VEC:
        k = keys(v)
        need = {a for a in ("pso", "de", "cmaes") if not D._is_withdrawn("entryseq", v, a)}
        assert need <= k, v
        assert not any(x.startswith(("pk_", "bv_")) for x in k), f"{v}：实数向量变体不该有排列 / 位向量算法"


def test_an_algorithm_from_the_wrong_encoding_is_refused_not_silently_misrun():
    with pytest.raises(ValueError):
        D.domain_start("entryseq", json.dumps(E.es_make("lap", 8, 7)), "bv_pso", "{}")
    with pytest.raises(ValueError):
        D.domain_start("entryseq", json.dumps(E.es_make("numpart", 8, 7)), "pk_pso", "{}")
    with pytest.raises(ValueError):
        D.domain_start("entryseq", json.dumps(E.es_make("vcover", 8, 7)), "pk_pso", "{}")


def test_every_listed_combination_runs_and_returns_a_solution_of_its_own_encoding():
    for v in E.VARIANTS:
        p = E.es_make(v, 8, 7)
        for a in sorted(keys(v)):
            last = run(v, a, p, iters=4)
            sol = last.get("best_sol")
            if sol is None:
                continue
            n = len(sol)
            if v in BITS:
                assert set(sol) <= {0, 1}, (v, a)
            elif v in VEC:
                assert all(-5 - 1e-9 <= x <= 5 + 1e-9 for x in sol), (v, a)
            else:
                assert sorted(sol) == list(range(n)), (v, a, sol)


# ---------------------------------------------------------------- 新写的排列版 ga / ts
@pytest.mark.parametrize("v", PERM)
def test_permutation_ga_and_ts_beat_blind_sampling(v):
    p = E.es_make(v, 10, 7)
    ctx = E.es_ctx(p)
    rng = random.Random(5)
    blind = min(ctx.obj(ctx.random(rng)) for _ in range(300))
    for a in ("ga", "ts"):
        got = run(v, a, p, iters=80)["best"]
        assert got <= blind + 1e-9, f"{v}/{a}：{got} 不如盲采样 300 次的最好值 {blind}"


def test_permutation_ga_and_ts_find_the_exact_optimum_on_a_small_instance():
    p = E.es_make("lap", 7, 3)
    ctx = E.es_ctx(p)
    opt = min(ctx.obj(list(t)) for t in itertools.permutations(range(p["n"])))
    for a in ("ga", "ts"):
        assert run("lap", a, p, iters=80)["best"] == opt, a


# ---------------------------------------------------------------- 子集类问题的位向量模型（用手算的小实例钉死）
def inst(variant, **kw):
    p = E.es_make(variant, 8, 7)
    p.update(kw)
    return p


TRI = [(0, 1, 5), (1, 2, 5), (0, 2, 5)]


def test_vertex_cover_domination_fvs_maxcut_on_tiny_graphs():
    tri = inst("vcover", n=3, edges=TRI, pts=[[0, 0], [1, 0], [0, 1]])
    c = E.es_ctx(tri)
    assert c.obj([1, 1, 0]) == 2 and c.obj([1, 0, 0]) > 1000 and c.obj([0, 0, 0]) > 1000     # 三角形最小覆盖 = 2
    star = inst("domset", n=4, edges=[(0, 1, 1), (0, 2, 1), (0, 3, 1)], pts=[[0, 0]] * 4)
    c = E.es_ctx(star)
    assert c.obj([1, 0, 0, 0]) == 1 and c.obj([0, 1, 1, 1]) == 3 and c.obj([0, 1, 0, 0]) > 1000  # 星形：中心点支配全部
    c = E.es_ctx(inst("fvs", n=3, edges=TRI, pts=[[0, 0]] * 3))
    assert c.obj([0, 0, 0]) > 1000 and c.obj([1, 0, 0]) == 1                                  # 三角形删 1 点即无环
    c = E.es_ctx(inst("maxcut", n=3, edges=TRI, pts=[[0, 0]] * 3))
    assert c.obj([0, 0, 1]) == -10 and c.obj([0, 0, 0]) == 0                                  # 三角形最大割 = 2 条边 = 10；且可以不均衡


def test_maxcut_is_no_longer_restricted_to_balanced_partitions():
    """旧模型用排列奇偶位分两侧：永远均衡。星形图的最大割是 3 条边，需要 1 vs 3 的划分。"""
    star = inst("maxcut", n=4, edges=[(0, 1, 1), (0, 2, 1), (0, 3, 1)], pts=[[0, 0]] * 4)
    c = E.es_ctx(star)
    assert c.obj([1, 0, 0, 0]) == -3 and min(c.obj(list(b)) for b in itertools.product((0, 1), repeat=4)) == -3


def test_set_packing_hitting_set_and_steiner_tree():
    sets = [[1, 1, 0, 0], [0, 1, 1, 0], [0, 0, 1, 1], [1, 0, 0, 1]]
    c = E.es_ctx(inst("setpack", sets=sets, n=4))
    assert c.obj([1, 0, 1, 0]) == -2 and c.obj([1, 1, 0, 0]) > 1000                            # 两两不交的最多 2 个
    c = E.es_ctx(inst("hset", sets=sets, n=4))
    assert c.obj([0, 1, 0, 1]) == 2 and c.obj([1, 0, 0, 0]) > 1000                             # 元素 1、3 恰好击中全部 4 个集合
    pts = [[0, 0], [10, 0], [5, 0.1], [50, 50]]
    c = E.es_ctx(inst("stp", pts=pts, req=[0, 1], n=4))
    assert c.obj([0, 0, 0, 0]) == 10.0 and c.obj([0, 0, 1, 0]) == pytest.approx(10.0, abs=0.01)
    assert c.obj([0, 0, 0, 1]) > 50                                                            # 乱选远处的中转点只会更长


@pytest.mark.parametrize("v", sorted(BITS))
def test_bit_algorithms_reach_the_exact_optimum_on_small_instances(v):
    p = E.es_make(v, 8 if v != "hset" else 8, 7)
    ctx = E.es_ctx(p)
    if "opt" in p and v == "msa":  # 位串太长无法穷举：用实例附带的三维动态规划最优（目标 = −SP）
        opt = -p["opt"]
    else:
        assert ctx.n <= 20, f"{v}: 位数 {ctx.n} 太多，不能穷举"
        opt = min(ctx.obj(list(b)) for b in itertools.product((0, 1), repeat=ctx.n))
    best = min(run(v, a, p, iters=120, seed=s)["best"] for a in ("ga", "ts", "sa") for s in (1, 2, 3))
    assert best == pytest.approx(opt, abs=1e-6), f"{v}：穷举最优 {opt}，算法最好 {best}"
    assert opt < 1000, f"{v}：穷举最优带着罚项，实例本身不可行？"


# ---------------------------------------------------------------- 目标值可以是负数（ABC 曾因此崩溃）
def test_algorithms_tolerate_negative_objectives():
    """ABC 的轮盘权重 1/(1+f) 在 f ≤ −1 时为负，random.choices 直接抛错。自带问题与最大化问题天然会出现负目标。"""
    import userproblem as U
    for variant, obj, extra in (("real", "-100 + sum(x[i] ** 2 for i in range(n))", {"lo": -5, "hi": 5}),
                                ("bits", "-50 - sum(x)", {}), ("perm", "-30 - sum(i * x[i] for i in range(n))", {})):
        p = {"variant": variant, "n": 6, "sense": "min", "data": {}, "objective": obj, **extra}
        for a in [x["key"] for x in json.loads(D.domain_list("custom", {"variant": variant}))["algos"]]:
            D.domain_start("custom", json.dumps(p), a, json.dumps({"max_iter": 8, "seed": 3}))
            while D.domain_step() is not None:
                pass

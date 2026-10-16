# -*- coding: utf-8 -*-
"""2026-10 补全的算法：18 个连续内核（原来只在 TSP 上有的算法，按原论文写成连续版）+ 通用编码适配器 + ILS / VNS / ACO / GRASP。

要钉死的不是「某个数值」，而是三件事：
  1. 每个内核在**等评价次数**下明显好于随机搜索（按「代」比较对评价次数多的算法太宽松，见 tools/fair_budget.py）；
  2. 适配到位向量 / 排列 / 指派向量后，上报的最优解与最优值始终一致（test_consistency.py 逐格再查一遍）；
  3. 注册表里确实有：除 Lin–Kernighan（TSP 专用的边交换）外，每个收录算法在至少一种别的问题上有内核。"""
import json
import os
import random
import statistics
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "py"))

import domains as D  # noqa: E402
import registry as REG  # noqa: E402

NEW_CN = sorted(D._NEW_CN)
GENERIC = sorted(D._NEW_GENERIC)
TSP_ONLY = {"lk"}  # Lin–Kernighan 的核心是 TSP 回路上的边交换，没有对应的通用形式——如实标注，不硬造


def _count(ctx):
    n = [0]
    orig = ctx.eval

    def counted(x):
        n[0] += 1
        return orig(x)
    ctx.eval = counted
    return n


def _run(key, fn, dim, iters, seed):
    ctx = D._CN({"fn": fn, "dim": dim})
    n = _count(ctx)
    last, curve = None, []
    for st in D._CN_ALGOS[key]["fn"](ctx, dict(D._CN_DEF, max_iter=iters), random.Random(seed)):
        last = st
        curve.append(st["best"])
    return last["best"], n[0], curve


def _random_at(evals, fn, dim, seed):
    ctx = D._CN({"fn": fn, "dim": dim})
    rng = random.Random(seed)
    return min(ctx.eval(ctx.random(rng)) for _ in range(evals))


@pytest.mark.parametrize("key", NEW_CN)
def test_continuous_kernel_beats_random_search_at_equal_evaluations(key):
    for fn in ("sphere", "rastrigin", "ackley"):
        got, rnd = [], []
        for seed in (1, 2, 3):
            v, evals, curve = _run(key, fn, 10, 120, seed)
            assert all(b <= a + 1e-12 for a, b in zip(curve, curve[1:])), "best 只能降不能升"
            got.append(v)
            rnd.append(_random_at(evals, fn, 10, seed))
        margin = 0.1 if fn == "sphere" else 0.85  # 单峰的 Sphere 上必须大幅领先；多峰函数上要有明确的优势
        assert statistics.median(got) < margin * statistics.median(rnd), f"{key}/{fn}: {got} vs 随机 {rnd}"


@pytest.mark.parametrize("key", NEW_CN)
def test_continuous_kernel_is_deterministic_and_reports_the_best_point(key):
    a = _run(key, "sphere", 5, 40, 7)
    b = _run(key, "sphere", 5, 40, 7)
    assert a[0] == b[0] and a[2] == b[2], "同一种子必须复现"
    assert a[0] < 5.0  # Sphere（5 维）从 ~26 的随机水平降下来


def test_registry_has_every_new_algorithm_where_it_belongs():
    for dom, var in REG.cases(include_scheduling=False):
        if dom in ("multiobj", "mocont"):
            continue
        opts = {"variant": var} if var else {}
        keys = {a["key"] for a in json.loads(D.domain_list(dom, opts))["algos"]}
        # 被「等评价次数」账本撤下的格子不提供：把它们当作已在场
        keys |= {k for k in list(NEW_CN) + ["bv_" + k for k in NEW_CN] + ["pk_" + k for k in NEW_CN] + ["as_" + k for k in NEW_CN]
                 + ["ils", "vns", "aco", "grasp"] if D._is_withdrawn(dom, var, k)}
        if dom == "continuous" or (dom == "entryseq" and var in D.VEC_VARIANTS) or (dom == "custom" and var == "real"):
            assert set(NEW_CN) <= keys, (dom, var, sorted(set(NEW_CN) - keys))
        if dom == "qubo":
            assert {"bv_" + k for k in NEW_CN} <= keys and {"ils", "vns", "aco", "grasp"} <= keys
        if dom == "entryseq" and var in ("vrp", "qap"):
            assert {"pk_" + k for k in NEW_CN} <= keys and {"ils", "vns", "aco"} <= keys and "grasp" not in keys
        if dom == "gap":
            assert {"as_" + k for k in NEW_CN} <= keys and {"ils", "vns", "aco"} <= keys


def test_every_tsp_algorithm_but_lk_has_a_kernel_on_some_other_problem():
    algos = [a["key"] for a in json.load(open(os.path.join(HERE, "..", "data", "algos.json"), encoding="utf-8"))]
    present = set()
    for dom, var in REG.cases(include_scheduling=True):
        opts = {"variant": var} if var else {}
        for a in json.loads(D.domain_list(dom, opts))["algos"]:
            k = a["key"]
            present.add(k[3:] if k[:3] in ("bv_", "pk_", "as_") else k)
    alias = {"cma-es": "cmaes"}
    missing = [k for k in algos if alias.get(k, k) not in present and k not in TSP_ONLY]
    assert not missing, f"这些算法只在 TSP 上有：{missing}"


# ---------------------------------------------------------------- 通用离散内核：对独立穷举核对
def _run_es(variant, algo, n, iters, seed):
    import entryseq as E
    p = E.es_make(variant, n, 7)
    D.domain_start("entryseq", json.dumps(p), algo, json.dumps({"max_iter": iters, "seed": seed}))
    last = None
    while True:
        s = D.domain_step()
        if s is None:
            return p, last
        last = json.loads(s)


@pytest.mark.parametrize("algo", ["ils", "vns", "aco"])
def test_generic_permutation_kernels_find_the_exhaustive_optimum_of_a_small_problem(algo):
    import itertools
    import entryseq as E
    p = E.es_make("qap", 7, 3)
    ctx = E.es_ctx(p)
    opt = min(ctx.obj(list(t)) for t in itertools.permutations(range(p["n"])))
    best = min(_run_es("qap", algo, 7, 120, s)[1]["best"] for s in (1, 2, 3))
    assert best <= opt * 1.02 + 1e-9, f"{algo}: {best} vs 最优 {opt}"


@pytest.mark.parametrize("algo", ["ils", "vns", "aco", "grasp"])
def test_generic_bit_kernels_find_the_exhaustive_optimum_of_a_small_problem(algo):
    import itertools
    import entryseq as E
    p = E.es_make("vcover", 10, 3)
    ctx = E.es_ctx(p)
    opt = min(ctx.obj(list(b)) for b in itertools.product((0, 1), repeat=p["n"]))
    best = min(_run_es("vcover", algo, 10, 80, s)[1]["best"] for s in (1, 2, 3))
    assert best <= opt + 1e-9, f"{algo}: {best} vs 最优 {opt}"


def test_max_protocol_domains_report_the_original_sign():
    """knapsack 是「越大越好」：视图内部取负，yield 时必须还原，否则收敛曲线会倒着走。"""
    pre = D.domain_preset("knapsack", 7, {})
    for algo in ("ils", "vns", "aco", "grasp", "bv_hho", "bv_mpa"):
        D.domain_start("knapsack", pre, algo, json.dumps({"max_iter": 25, "seed": 3}))
        vals = []
        while True:
            s = D.domain_step()
            if s is None:
                break
            vals.append(json.loads(s)["best"])
        assert vals[-1] >= vals[0] and vals[-1] > 0, algo
        assert all(b >= a - 1e-9 for a, b in zip(vals, vals[1:])), f"{algo}: 越大越好的域里 best 只能升不能降"

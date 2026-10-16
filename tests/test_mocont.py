# -*- coding: utf-8 -*-
"""连续多目标基准 ZDT / DTLZ（py/mocont.py）。

这类基准的意义在于「有解析的真前沿」，所以先核对前沿本身是否正确（否则 IGD / HV 全是空话），
再核对算法：上报的前沿必须是它自己的决策变量真能得到的目标向量、必须互不支配，且 IGD 只降不升。"""
import json
import math
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "py"))

import domains as D  # noqa: E402
import mocont as M  # noqa: E402
import registry as REG  # noqa: E402
import validate as V  # noqa: E402

BIO = ("zdt1", "zdt2", "zdt3", "zdt4", "zdt6")


def _dominates(a, b):
    return all(x <= y for x, y in zip(a, b)) and a != b


# ---------------------------------------------------------------- 函数与真前沿
def test_known_pareto_optimal_points_have_the_published_objective_values():
    ctx = lambda v: M.MOC(M.mc_make(v))  # noqa: E731
    # g = 1（其余变量取最优）时：ZDT1 f2 = 1-√f1，ZDT2 f2 = 1-f1²，ZDT3 加正弦项，ZDT4 同 ZDT1
    c = ctx("zdt1")
    assert c.f([0.25] + [0.0] * 29) == pytest.approx([0.25, 0.5])
    assert ctx("zdt2").f([0.5] + [0.0] * 29) == pytest.approx([0.5, 0.75])
    assert ctx("zdt3").f([0.1] + [0.0] * 29)[1] == pytest.approx(1 - math.sqrt(0.1) - 0.1 * math.sin(math.pi))
    assert ctx("zdt4").f([0.25] + [0.0] * 9) == pytest.approx([0.25, 0.5])
    # ZDT6：f1 = 1-exp(-4x)sin⁶(6πx)，最优时 f2 = 1-f1²
    f = ctx("zdt6").f([0.3] + [0.0] * 9)
    assert f[1] == pytest.approx(1 - f[0] ** 2)
    # DTLZ1 的前沿是 Σf = 0.5 的单纯形，DTLZ2 是单位球面（x[2:] = 0.5 时 g = 0）
    f = ctx("dtlz1").f([0.3, 0.7] + [0.5] * 5)
    assert sum(f) == pytest.approx(0.5)
    f = ctx("dtlz2").f([0.3, 0.7] + [0.5] * 10)
    assert math.sqrt(sum(v * v for v in f)) == pytest.approx(1.0)


def test_g_larger_than_one_is_dominated():
    """远离最优的变量让 g 变大，目标向量被前沿上的点支配——这就是「收敛」的含义。"""
    for v in M.MOC_VARIANTS:
        c = M.MOC(M.mc_make(v))
        pts = M.true_front(v)
        x = [0.5] * c.n
        if v == "zdt5":
            x = [0] * len(c.bounds)  # 全 0 的段 v = 2（最优是全 1 的 v = 1）：g = 20 > 10
        elif v == "dtlz7":
            x[2:] = [1.0] * (c.n - 2)  # DTLZ7 的最优在 x[2:] = 0，取 1 才是「远离」
        elif v == "dtlz6":
            pass  # DTLZ6 的最优在 x[2:] = 0，0.5 已经远离
        elif v.startswith("dtlz"):
            x[2:] = [0.0] * (c.n - 2)  # 其余 DTLZ 的最优在 x[2:] = 0.5，取 0 才是「远离」
        bad = c.f(x)
        assert any(_dominates(p, bad) for p in pts), v


@pytest.mark.parametrize("variant", M.MOC_VARIANTS)
def test_true_front_points_are_mutually_nondominated_and_cover_the_range(variant):
    pts = M.true_front(variant)
    assert len(pts) >= 30
    for i, a in enumerate(pts):
        for b in pts[i + 1:]:
            assert not _dominates(a, b) and not _dominates(b, a)
    assert M.igd(pts, pts) == 0.0


def test_zdt3_true_front_has_the_published_five_segments():
    pts = sorted(M.true_front("zdt3"))
    gaps = [b[0] - a[0] for a, b in zip(pts, pts[1:])]
    big = [g for g in gaps if g > 4 * (sum(gaps) / len(gaps))]
    assert len(big) == 4, "ZDT3 的真前沿由 5 段组成，应有 4 个明显的断点"
    assert pts[0][0] == pytest.approx(0.0, abs=1e-3) and pts[-1][0] == pytest.approx(0.8518, abs=5e-3)


def test_zdt3_front_agrees_with_a_brute_force_nondominated_filter():
    """真前沿用「按 f1 升序、只留 f2 严格更低的点」一遍扫出来的；这里用 O(n²) 的穷举独立核对，
    并核对论文给出的 5 段端点。"""
    dense = [[t / 1000.0, 1 - math.sqrt(t / 1000.0) - (t / 1000.0) * math.sin(10 * math.pi * t / 1000.0)] for t in range(1001)]
    brute = [a for a in dense if not any(_dominates(b, a) for b in dense)]
    pts = M.true_front("zdt3")
    # 返回的每个点都不被穷举样本里的任何点支配，且穷举得到的段数与端点一致
    assert not any(b[0] <= p[0] and b[1] < p[1] - 1e-9 for p in pts for b in dense)  # 容差：同一点两种写法差 1e-16
    segs, start = [], brute[0][0]
    for a, b in zip(brute, brute[1:]):
        if b[0] - a[0] > 0.02:
            segs.append((round(start, 2), round(a[0], 2)))
            start = b[0]
    segs.append((round(start, 2), round(brute[-1][0], 2)))
    assert segs == [(0.0, 0.08), (0.18, 0.26), (0.41, 0.45), (0.62, 0.65), (0.82, 0.85)]


def test_zdt5_is_a_bit_string_problem_with_a_31_point_front():
    c = M.MOC(M.mc_make("zdt5"))
    assert c.bits and len(c.bounds) == 30 + 5 * 10 and c.n == 11
    # 最优：第 1 段 u 个 1，其余各 5 位全 1（v = 1）→ f1 = 1 + u，f2 = 10 / f1
    for u in (0, 7, 30):
        x = [1] * u + [0] * (30 - u) + [1] * 50
        assert c.f(x) == pytest.approx([1 + u, 10.0 / (1 + u)])
    # 欺骗性：段里 1 的个数为 0 时 v = 2，比 1 个 1（v = 3）、4 个 1（v = 6）都好，只有 5 个 1 时才降到 1
    x = [0] * 30 + [0] * 5 + [1] * 45
    assert c.f(x)[1] == pytest.approx((2 + 9) / 1.0)
    pts = M.true_front("zdt5")
    assert len(pts) == 31 and pts[0] == [1.0, 10.0] and pts[-1][0] == 31.0
    assert V.validate("mocont", {"variant": "zdt5", "n": 11})["ok"]
    assert not V.validate("mocont", {"variant": "zdt5", "n": 20})["ok"], "ZDT5 的变量个数固定"


def test_dtlz3_to_7_published_properties():
    c = {v: M.MOC(M.mc_make(v)) for v in ("dtlz3", "dtlz4", "dtlz5", "dtlz6", "dtlz7")}
    # DTLZ3 / DTLZ4 的前沿是单位球面（最优时 g = 0：DTLZ3 在 x[2:] = 0.5，DTLZ4 同 DTLZ2）
    for v in ("dtlz3", "dtlz4"):
        f = c[v].f([0.3, 0.7] + [0.5] * 10)
        assert math.sqrt(sum(a * a for a in f)) == pytest.approx(1.0)
    # DTLZ4 的 x^100 把解挤向 f3 = 0 的面：x1 = 0.5 时角度几乎为 0（f3 ≈ 0），而 DTLZ2 里是 sin(π/4)
    assert c["dtlz4"].f([0.5, 0.5] + [0.5] * 10)[2] < 1e-9
    # DTLZ5 / DTLZ6 的前沿退化成曲线 f1 = f2、f1² + f2² + f3² = 1（g = 0：DTLZ5 在 x[2:] = 0.5，DTLZ6 在 x[2:] = 0）
    f = c["dtlz5"].f([0.3, 0.2] + [0.5] * 10)
    assert f[0] == pytest.approx(f[1]) and math.sqrt(sum(a * a for a in f)) == pytest.approx(1.0)
    f = c["dtlz6"].f([0.3, 0.9] + [0.0] * 10)
    assert f[0] == pytest.approx(f[1]) and math.sqrt(sum(a * a for a in f)) == pytest.approx(1.0)
    for p in M.true_front("dtlz5"):
        assert p[0] == pytest.approx(p[1]) and math.sqrt(sum(a * a for a in p)) == pytest.approx(1.0)
    # DTLZ7：g = 1（x[2:] = 0）时 f1 = x1，f2 = x2，f3 = 2·(3 - Σ fi/2·(1 + sin 3π fi))
    f = c["dtlz7"].f([0.25, 0.6] + [0.0] * 20)
    h = 3 - sum(a / 2 * (1 + math.sin(3 * math.pi * a)) for a in (0.25, 0.6))
    assert f == pytest.approx([0.25, 0.6, 2 * h])


def test_dtlz7_front_agrees_with_a_brute_force_dominance_filter_and_has_four_regions():
    """真前沿用二维前缀最小值一遍扫出来；这里在较粗的网格上用 O(n²) 的三维穷举支配检查独立核对。"""
    grid = 24
    xs = [i / (grid - 1) for i in range(grid)]
    surf = [[a, b, M._dtlz7_f3(a, b, 1.0)] for a in xs for b in xs]
    brute = [p for p in surf if not any(_dominates(q, p) for q in surf)]
    sweep = M._dtlz7_front(grid)
    assert sorted(map(tuple, brute)) == sorted(map(tuple, sweep))
    # 四块：f1 方向上有 f1 ∈ [0, 0.25) 与另外几处断开（论文：4 个不相连的最优区域）；用细网格数连通块
    fine = M._dtlz7_front(120)
    cells = {(round(p[0] * 119), round(p[1] * 119)) for p in fine}
    seen, comps = set(), 0
    for c0 in cells:
        if c0 in seen:
            continue
        comps += 1
        stack = [c0]
        while stack:
            a, b = stack.pop()
            if (a, b) in seen:
                continue
            seen.add((a, b))
            stack += [(a + da, b + db) for da in (-1, 0, 1) for db in (-1, 0, 1) if (a + da, b + db) in cells]
    assert comps == 4, f"DTLZ7 的真前沿应有 4 块，数出 {comps} 块"


def test_nsga2_beats_random_on_the_new_variants_and_moead_does_on_zdt5_at_the_default_budget():
    for v in ("zdt5", "dtlz4", "dtlz5", "dtlz7"):
        rnd = _run(v, "random", iters=150, seed=7)[-1]["best"]
        ns = _run(v, "nsga2", iters=150, seed=7)[-1]["best"]
        assert ns < 0.5 * rnd, f"{v}: NSGA-II {ns} 没有明显好于随机 {rnd}"
    assert _run("zdt5", "moead", iters=300, seed=7)[-1]["best"] < 0.75 * _run("zdt5", "random", iters=300, seed=7)[-1]["best"]


def test_hypervolume_matches_analytic_values():
    # ZDT1：前沿 f2 = 1-√f1，参考点 (1.1,1.1)：HV = 0.1 + 2/3 + 0.11
    assert M.hypervolume(M.true_front("zdt1", 1500), [1.1, 1.1]) == pytest.approx(0.1 + 2 / 3 + 0.11, abs=2e-3)
    # 单点与手算：(0.2,0.3) 对 (1,1) 支配 0.8×0.7
    assert M.hypervolume([[0.2, 0.3]], [1, 1]) == pytest.approx(0.56)
    assert M.hypervolume([[0.2, 0.3, 0.5]], [1, 1, 1]) == pytest.approx(0.8 * 0.7 * 0.5)
    # 两个互不支配的三维点：容斥 = 两个长方体体积之和 - 交集
    a, b = [0.2, 0.6, 0.4], [0.6, 0.2, 0.4]
    expect = 0.8 * 0.4 * 0.6 * 2 - 0.4 * 0.4 * 0.6
    assert M.hypervolume([a, b], [1, 1, 1]) == pytest.approx(expect)
    assert M.hypervolume([[1.2, 0.1]], [1, 1]) == 0.0, "参考点之外的点不贡献体积"


def test_nd_sort_and_crowding():
    F = [[1, 5], [2, 3], [3, 1], [3, 4], [4, 4], [5, 5]]
    rank, fronts = M.nd_sort(F)
    assert sorted(fronts[0]) == [0, 1, 2] and rank[3] == 1 and rank[4] == 2 and rank[5] == 3
    cd = M.crowding(F, fronts[0])
    assert cd[0] == cd[2] == float("inf") and 0 < cd[1] < float("inf")


# ---------------------------------------------------------------- 算法
def _run(variant, algo, iters=25, seed=3, **p):
    pre = D.domain_preset("mocont", 7, {"variant": variant})
    D.domain_start("mocont", pre, algo, json.dumps(dict({"max_iter": iters, "seed": seed}, **p)))
    out = []
    while True:
        s = D.domain_step()
        if s is None:
            return out
        out.append(json.loads(s))


CASES = [(v, a) for v in M.MOC_VARIANTS for a in M.MOC_ALGOS]


@pytest.mark.parametrize("variant,algo", CASES, ids=lambda v: str(v))
def test_reported_front_is_what_the_reported_decision_vectors_really_give(variant, algo):
    states = _run(variant, algo)
    assert len(states) == 25
    ctx = M.MOC(M.mc_make(variant))
    ref = M.true_front(variant)
    best = [s["best"] for s in states]
    assert all(b2 <= b1 + 1e-12 for b1, b2 in zip(best, best[1:])), "IGD 只能降不能升"
    last = states[-1]
    # 前沿 = 决策变量真实算出的目标向量
    assert len(last["front"]) == len(last["front_x"]) == last["nd"]
    for f, x in zip(last["front"], last["front_x"]):
        assert len(x) == len(ctx.bounds) and all(lo - 1e-9 <= v <= hi + 1e-9 for v, (lo, hi) in zip(x, ctx.bounds))
        assert ctx.f(x) == pytest.approx(f, abs=1e-9)
    # 前沿互不支配，且每个点都来自种群
    for i, a in enumerate(last["front"]):
        assert not any(_dominates(b, a) for b in last["front"])
    pop = {tuple(p) for p in last["pop"]}
    assert all(tuple(f) in pop for f in last["front"])
    # 上报的 IGD / HV 与独立重算一致
    assert last["igd"] == pytest.approx(M.igd(last["front"], ref), abs=1e-5)
    assert last["hv"] == pytest.approx(M.hypervolume(last["front"], ctx.ref), abs=1e-5)
    assert 0 <= last["hv_ratio"] <= 1.02


def test_same_seed_same_result_and_different_seed_differs():
    a = _run("zdt1", "nsga2", iters=15, seed=5)[-1]
    b = _run("zdt1", "nsga2", iters=15, seed=5)[-1]
    c = _run("zdt1", "nsga2", iters=15, seed=6)[-1]
    assert a == b and a["best"] != c["best"]


@pytest.mark.parametrize("variant", ["zdt1", "zdt2", "zdt3", "zdt6", "dtlz2"])
def test_the_real_algorithms_beat_random_search_by_a_wide_margin(variant):
    rnd = _run(variant, "random", iters=150, seed=7)[-1]["best"]
    for algo in ("nsga2", "moead"):
        got = _run(variant, algo, iters=150, seed=7)[-1]["best"]
        assert got < 0.5 * rnd, f"{variant}/{algo}：IGD {got} 没有明显好于随机搜索 {rnd}"


def test_weighted_sum_cannot_cover_a_nonconvex_front_but_nsga2_can():
    """ZDT2 的前沿是凹的：线性加权的最优点只会落在两端，铺不开——这正是 Pareto 方法的存在理由。"""
    ws = _run("zdt2", "wsga", iters=150, seed=7)[-1]
    ns = _run("zdt2", "nsga2", iters=150, seed=7)[-1]
    assert ns["hv_ratio"] > ws["hv_ratio"] + 0.3
    assert ns["nd"] > 2 * ws["nd"]


def test_dtlz1_is_hard_for_nsga2_but_decomposition_handles_it():
    """DTLZ1 有 11^k − 1 个局部前沿（Deb et al. 2005）：同样预算下 NSGA-II 陷在局部前沿上，MOEA/D 能到真前沿附近。"""
    nsga = _run("dtlz1", "nsga2", iters=200, seed=7)[-1]
    moead = _run("dtlz1", "moead", iters=200, seed=7)[-1]
    assert moead["best"] < 0.5 * nsga["best"]
    assert moead["hv_ratio"] > 0.5


# ---------------------------------------------------------------- 接线
def test_registry_validator_and_fidelity():
    assert ("mocont", "dtlz2") in list(REG.cases())
    assert REG.fidelity("mocont", "zdt1")["level"] == "standard"
    assert V.validate("mocont", {"variant": "zdt3", "n": 20}, dry_run=True)["ok"]
    assert V.validate("mocont", {"variant": "dtlz1", "n": 2})["ok"] is False
    assert V.validate("mocont", {"variant": "zdt9"})["ok"] is False
    # 信封格式往返
    dom, data, _issues = V.load({"schema": "swarm-problem/v1", "domain": "mocont", "data": {"variant": "zdt2"}})
    assert dom == "mocont" and data == {"variant": "zdt2"}


def test_problem_size_is_respected():
    s = _run("zdt1", "nsga2", iters=2, seed=1)[-1]
    pre = json.loads(D.domain_preset("mocont", 7, {"variant": "zdt1", "n": 12}))
    assert pre["n"] == 12 and all(len(x) == 12 for x in s["front_x"]) is False
    info = json.loads(D.domain_start("mocont", json.dumps(pre), "nsga2", json.dumps({"max_iter": 2})))
    assert info["n"] == 12 and info["m"] == 2 and info["sense"] == "min" and len(info["front"]) > 100


# ---------------------------------------------------------------- 三大范式：指标法 IBEA 与偏好法 R-NSGA-II
def test_ibea_beats_random_and_is_competitive_on_a_concave_front():
    """指标法不做支配排序，在凹前沿 ZDT2 上也能铺开（Zitzler & Künzli 2004 的演示点）。"""
    ib = _run("zdt2", "ibea", iters=100, seed=7)[-1]
    rnd = _run("zdt2", "random", iters=100, seed=7)[-1]
    assert ib["hv_ratio"] > rnd["hv_ratio"] + 0.3 and ib["nd"] >= 10


def test_rnsga2_concentrates_near_the_reference_point():
    """偏好法的卖点：同样预算下，前沿离参考点比 NSGA-II 更近；代价是整条前沿的 IGD 变大（这是预期的）。"""
    for variant in ("zdt2", "dtlz2"):
        pr = _run(variant, "rnsga2", iters=100, seed=7)[-1]
        ns = _run(variant, "nsga2", iters=100, seed=7)[-1]
        assert pr["pref"] and pr["pref_dist"] < _pref_dist(variant, ns["front"], pr["pref"])
        assert "pref" not in ns


def _pref_dist(variant, front, ref):
    sc = M.MOC(M.mc_make(variant)).scale
    return min(math.sqrt(sum(((f[d] - ref[d]) / sc[d]) ** 2 for d in range(len(ref)))) for f in front)


def test_new_paradigm_algorithms_are_deterministic():
    for algo in ("ibea", "rnsga2"):
        a = _run("zdt1", algo, iters=10, seed=11)[-1]
        b = _run("zdt1", algo, iters=10, seed=11)[-1]
        assert a["front"] == b["front"] and a["best"] == b["best"]

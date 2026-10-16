# -*- coding: utf-8 -*-
"""第一梯队新增问题（atsp / pms / numpart / kmeans / wbeam / pvessel / tcspring / reducer）：
目标函数要和独立的手算 / 穷举 / 文献最优值对得上，校验器要拦住自相矛盾的数据。"""
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
import registry as REG  # noqa: E402
import validate as V  # noqa: E402

NEW = ("atsp", "pms", "numpart", "kmeans", "wbeam", "pvessel", "tcspring", "reducer")


def run(variant, algo, p, iters=60, seed=3):
    D.domain_start("entryseq", json.dumps(p), algo, json.dumps({"max_iter": iters, "seed": seed}))
    last = None
    while True:
        st = D.domain_step()
        if st is None:
            return last
        last = json.loads(st)


def test_all_new_variants_are_registered_as_standard_models():
    for v in NEW:
        assert v in E.VARIANTS
        assert REG.fidelity("entryseq", v)["level"] == "standard", v


# ---------------------------------------------------------------- 工程设计：文献最优
LIT = {
    "wbeam": ([0.2057, 3.4705, 9.0366, 0.2057], 1.724852),
    "pvessel": ([0.7782, 0.3846, 40.3196, 200.0], 5885.3328),
    "tcspring": ([0.051689, 0.356718, 11.288966], 0.012665),
    "reducer": ([3.5, 0.7, 17.0, 7.3, 7.7153, 3.3502, 5.2867], 2994.4711),
}


@pytest.mark.parametrize("v", sorted(LIT))
def test_design_formulas_reproduce_the_published_optimum_point(v):
    x, best = LIT[v]
    f, g = E._DESIGN[v]["fn"](x)
    assert f == pytest.approx(best, rel=2e-3), (f, best)
    assert max(g) < 1e-3, f"文献最优点应当（几乎）可行，最大 g={max(g)}"


@pytest.mark.parametrize("v", sorted(LIT))
def test_independent_optimiser_finds_the_published_optimum_and_nothing_better(v):
    """用一个与站内算法无关的朴素差分进化跑：到得了文献最优、也不会比它更好（更好 = 少了约束或公式错了）。"""
    rng = random.Random(1)
    ctx = E._ES(E.es_make(v, 12, 7))
    n = ctx.n
    pop = [[rng.uniform(-5, 5) for _ in range(n)] for _ in range(40)]
    fit = [ctx.obj(x) for x in pop]
    for _ in range(700):
        for i in range(40):
            a, b, c = rng.sample([j for j in range(40) if j != i], 3)
            jr = rng.randrange(n)
            t = [min(5, max(-5, pop[a][k] + 0.6 * (pop[b][k] - pop[c][k]))) if (rng.random() < 0.9 or k == jr) else pop[i][k]
                 for k in range(n)]
            ft = ctx.obj(t)
            if ft <= fit[i]:
                pop[i], fit[i] = t, ft
    best = min(fit)
    want = E._DESIGN[v]["best"]
    assert best >= want * (1 - 1e-4), f"比文献最优还好（{best} < {want}）：公式或约束有误"
    assert best <= want * 1.01, f"没找到文献最优附近（{best} vs {want}）"
    assert ctx.detail(pop[fit.index(best)])["feasible"]


def test_design_states_carry_variables_and_constraints():
    p = E.es_make("wbeam", 12, 7)
    last = run("wbeam", "pk_pso" if False else "sa", p, iters=20)
    assert len(last["x"]) == 4 and len(last["g"]) == 7 and last["names"] and "best_known" in last
    assert last["f"] <= last["best"] + 1e-6


# ---------------------------------------------------------------- ATSP
def test_atsp_is_really_asymmetric_and_objective_follows_the_arcs():
    p = E.es_make("atsp", 12, 7)
    d, n = p["d"], p["n"]
    assert any(d[i][j] != d[j][i] for i in range(n) for j in range(i + 1, n)) and all(d[i][i] == 0 for i in range(n))
    s = list(range(n))
    assert E._ES(p).obj(s) == sum(d[i][(i + 1) % n] for i in range(n))
    assert E._ES(p).obj(s[::-1]) == sum(d[s[::-1][i]][s[::-1][(i + 1) % n]] for i in range(n))  # 反向不是同一个数
    assert E._ES(p).obj(s) != E._ES(p).obj(s[::-1])


def test_atsp_algorithms_find_the_exact_optimum_on_a_brute_forceable_instance():
    p = E.es_make("atsp", 5, 3)
    n, d = p["n"], p["d"]
    opt = min(sum(d[t[i]][t[(i + 1) % n]] for i in range(n)) for t in ((0,) + q for q in itertools.permutations(range(1, n))))
    got = min(run("atsp", a, p, iters=80)["best"] for a in ("sa", "hc", "pk_pso"))
    assert got == opt


def test_atsp_validator():
    p = E.es_make("atsp", 8, 7)
    assert V.validate("entryseq", p, variant="atsp", dry_run=True)["ok"]
    bad = json.loads(json.dumps(p))
    bad["d"][2][2] = 5
    assert any("对角线" in e["msg"] for e in V.validate("entryseq", bad, variant="atsp")["errors"])
    bad = json.loads(json.dumps(p))
    bad["d"][1][3] = -4
    assert not V.validate("entryseq", bad, variant="atsp")["ok"]
    sym = json.loads(json.dumps(p))
    for i in range(8):
        for j in range(i):
            sym["d"][i][j] = sym["d"][j][i]
    assert any("对称" in w["msg"] for w in V.validate("entryseq", sym, variant="atsp")["warnings"])


# ---------------------------------------------------------------- 并行机
def test_pms_list_scheduling_covers_the_optimum_and_respects_the_bound():
    p = E.es_make("pms", 7, 5)
    ctx = E.es_ctx(p)
    n, m = p["n"], p["m_mach"]
    # 穷举所有作业→机器的分配：真正的最优 Cmax
    best = min(max(sum(p["p"][j] for j in range(n) if a[j] == i) for i in range(m))
               for a in itertools.product(range(m), repeat=n))
    best_list = min(ctx.obj(list(t)) for t in itertools.permutations(range(n)))
    assert best_list == best, "表调度的优先序空间必须包含最优调度"
    lb = ctx.detail(list(range(n)))["lb"]
    assert lb <= best
    assert min(run("pms", a, p, iters=80)["best"] for a in ("sa", "hc", "pk_pso")) == best


def test_pms_detail_matches_objective():
    p = E.es_make("pms", 24, 7)
    last = run("pms", "sa", p, iters=40)
    assert max(last["loads"]) == last["best"]
    assert sorted(j for ms in last["machines"] for j in ms) == list(range(p["n"]))


def test_pms_validator():
    p = E.es_make("pms", 10, 7)
    assert V.validate("entryseq", p, variant="pms", dry_run=True)["ok"]
    assert not V.validate("entryseq", dict(p, p=[0] + p["p"][1:]), variant="pms")["ok"]
    assert not V.validate("entryseq", dict(p, m_mach=1), variant="pms")["ok"]


# ---------------------------------------------------------------- 数分割
def test_numpart_objective_and_optimum():
    p = E.es_make("numpart", 10, 7)
    a, n = p["a"], p["n"]
    best = min(abs(sum(a[i] if m >> i & 1 else -a[i] for i in range(n))) for m in range(1 << n))
    ctx = E.es_ctx(p)
    x = [1.0 if i % 2 else -1.0 for i in range(n)]
    assert ctx.obj(x) == abs(sum(a[i] if i % 2 else -a[i] for i in range(n)))
    avail = [a["key"] for a in json.loads(D.domain_list("entryseq", {"variant": "numpart"}))["algos"] if a["key"] != "random"][:3]
    assert avail, "numpart 上没有可用的算法"
    got = min(run("numpart", al, p, iters=120)["best"] for al in avail)
    assert got <= best + max(a) * 0.05 + 1  # 随机算法：要求非常接近最优（差不超过一个小量）
    last = run("numpart", avail[0], p, iters=60)
    assert abs(last["sum_a"] - last["sum_b"]) == last["best"]


def test_numpart_validator():
    p = E.es_make("numpart", 8, 7)
    assert V.validate("entryseq", p, variant="numpart", dry_run=True)["ok"]
    assert not V.validate("entryseq", dict(p, a=[0] + p["a"][1:]), variant="numpart")["ok"]


# ---------------------------------------------------------------- k-means
def test_kmeans_objective_is_the_sse_of_the_decoded_centres():
    p = E.es_make("kmeans", 12, 7)
    ctx = E.es_ctx(p)
    rng = random.Random(2)
    s = ctx.random(rng)
    cs = E._kmeans_centers(p, s)
    sse = sum(min((q[0] - c[0]) ** 2 + (q[1] - c[1]) ** 2 for c in cs) for q in p["pts"])
    assert ctx.obj(s) == pytest.approx(sse, abs=1e-3)
    xs = [q[0] for q in p["pts"]]
    assert all(min(xs) - 1e-9 <= c[0] <= max(xs) + 1e-9 for c in cs), "中心被映射进数据包围盒"


def test_kmeans_finds_the_blobs():
    p = E.es_make("kmeans", 12, 7)
    baseline = E._ES(p).obj(E._ES(p).random(random.Random(9)))
    last = run("kmeans", "sa", p, iters=150)
    assert last["best"] < baseline * 0.5
    assert len(last["centers"]) == p["k"] and len(last["assign"]) == len(p["pts"])


def test_kmeans_validator_derives_n_from_k_and_checks_consistency():
    p = E.es_make("kmeans", 12, 7)
    q = {k: v for k, v in p.items() if k != "n"}
    r = V.validate("entryseq", q, variant="kmeans", dry_run=True)
    assert r["ok"] and r["problem"]["n"] == 2 * p["k"]
    assert not V.validate("entryseq", dict(p, n=3), variant="kmeans")["ok"]
    assert not V.validate("entryseq", dict(p, k=1, n=2), variant="kmeans")["ok"]
    assert not V.validate("entryseq", dict(p, pts=p["pts"][:2]), variant="kmeans")["ok"]


# ---------------------------------------------------------------- TSPLIB 的 .atsp 文件进 ATSP 页
ATSPLIB = """NAME : tiny5
TYPE : ATSP
DIMENSION : 5
EDGE_WEIGHT_TYPE : EXPLICIT
EDGE_WEIGHT_FORMAT : FULL_MATRIX
EDGE_WEIGHT_SECTION
9999 3 8 6 7
5 9999 2 9 4
7 6 9999 3 8
4 8 5 9999 2
6 3 7 4 9999
EOF
"""


def test_tsplib_atsp_file_is_read_by_the_atsp_page_and_refused_by_the_tsp_page():
    r = V.check_text(ATSPLIB, domain="entryseq", filename="tiny5.atsp", variant="atsp", dry_run=True)
    assert r["ok"], r["errors"]
    assert r["problem"]["n"] == 5 and r["problem"]["d"][0][0] == 0 and r["problem"]["d"][0][1] == 3
    assert any("对角线" in w["msg"] for w in r["warnings"])  # 9999 占位值被置 0 并告知
    tsp = V.check_text(ATSPLIB, domain="tsp", filename="tiny5.atsp")
    assert not tsp["ok"] and "ATSP" in tsp["errors"][0]["msg"] and "非对称旅行商" in tsp["errors"][0]["msg"]
    sym = ATSPLIB.replace("TYPE : ATSP", "TYPE : TSP")
    assert not V.check_text(sym, domain="entryseq", filename="x.tsp", variant="atsp")["ok"]
    bad = ATSPLIB.replace("FULL_MATRIX", "UPPER_ROW")
    assert not V.check_text(bad, domain="entryseq", filename="x.atsp", variant="atsp")["ok"]


def test_imported_tsplib_atsp_solves_to_the_true_optimum():
    r = V.check_text(ATSPLIB, domain="entryseq", filename="tiny5.atsp", variant="atsp")
    p = r["problem"]
    n, d = p["n"], p["d"]
    opt = min(sum(d[t[i]][t[(i + 1) % n]] for i in range(n)) for t in ((0,) + q for q in itertools.permutations(range(1, n))))
    assert run("atsp", "sa", p, iters=80)["best"] == opt

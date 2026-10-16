# -*- coding: utf-8 -*-
"""complete-a-kernels v2 gate tests (2026-09-29).

严口径防假跑门：同族 3-seed（1/7/13）随机基线取最优 vs 内核 3-seed 最优，
200 代显著优于随机（min: kbest<rbase；max: kbest>rbase）。逐域回挂核对的独立验证。
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import domains  # noqa: E402
import pytest  # noqa: E402


def _skip_if_withdrawn(domain, variant, algo):
    """被「等评价次数」账本撤下的格子不再提供，也就没有「赢随机」可测（见 data/withdrawn_cells.json）。"""
    if domains._is_withdrawn(domain, variant, algo):
        pytest.skip(f"{domain}/{variant or '-'}/{algo} 已被等评价次数账本撤下")


def _run(domain, algo, iters, seed, opts=None):
    if domain == "qubo":
        prob = domains.qb_make(seed=seed)
    elif domain == "sat":
        prob = domains.sat_make(seed=seed, ratio=4.26)
    elif domain == "uflp":
        prob = domains.uf_make(seed=seed)
    elif domain == "knapsack":
        prob = domains.ks_make(seed=seed)
    elif domain == "multiobj":
        prob = domains.mo_make(seed=seed, variant=(opts or {}).get("variant", "moco"))
    else:
        prob = domains.domain_preset(domain, seed, opts)
    domains.domain_start(domain, json.dumps(prob), algo, json.dumps({"max_iter": iters, "seed": seed}))
    first = last = None
    while True:
        s = domains.domain_step()
        if s is None:
            break
        d = json.loads(s)
        if first is None:
            first = d
        last = d
    return first, last


def _run_kpvar(variant, algo, iters, seed):
    prob = json.loads(domains.domain_preset("kpvar", seed, {"variant": variant, "n": 40}))
    domains.domain_start("kpvar", json.dumps(prob), algo, json.dumps({"max_iter": iters, "seed": seed}))
    last = None
    while True:
        x = domains.domain_step()
        if x is None:
            break
        last = json.loads(x)
    return last["best"]


def _gate(domain, algo, sense, iters=200, seeds=(1, 7, 13), opts=None):
    rb = [_run(domain, "random", iters, s, opts)[1]["best"] for s in seeds]
    kb = [_run(domain, algo, iters, s, opts)[1]["best"] for s in seeds]
    rbase = (max if sense == "max" else min)(rb)
    kbest = (max if sense == "max" else min)(kb)
    return rbase, kbest, (kbest > rbase if sense == "max" else kbest < rbase)


def _gate_kpvar(variant, algo, sense, iters=200, seeds=(1, 7, 13)):
    rb = [_run_kpvar(variant, "random", iters, s) for s in seeds]
    kb = [_run_kpvar(variant, algo, iters, s) for s in seeds]
    rbase = (max if sense == "max" else min)(rb)
    kbest = (max if sense == "max" else min)(kb)
    return rbase, kbest, (kbest > rbase if sense == "max" else kbest < rbase)


SEEDS = (1, 7, 13)


# ---------------- UFLP 专属内核 ----------------
def test_uf_local_beats_random():
    r, k, beat = _gate("uflp", "uf_local", "min", 200, SEEDS)
    assert beat, f"uf_local 未赢随机: rbase={r} kbest={k}"


# ---------------- qubo 回挂 ----------------
def test_qubo_bv_gsa_beats_random():
    r, k, beat = _gate("qubo", "bv_gsa", "min", 200, SEEDS)
    assert beat, f"qubo/bv_gsa 未赢随机: r={r} k={k}"

def test_qubo_bv_mfo_beats_random():
    r, k, beat = _gate("qubo", "bv_mfo", "min", 200, SEEDS)
    assert beat, f"qubo/bv_mfo 未赢随机: r={r} k={k}"

def test_qubo_bv_eo_beats_random():
    r, k, beat = _gate("qubo", "bv_eo", "min", 200, SEEDS)
    assert beat, f"qubo/bv_eo 未赢随机: r={r} k={k}"

def test_qubo_qb_sca_beats_random():
    r, k, beat = _gate("qubo", "qb_sca", "min", 200, SEEDS)
    assert beat, f"qubo/qb_sca 未赢随机: r={r} k={k}"


# ---------------- sat 回挂 ----------------
def test_sat_bv_gsa_beats_random():
    _skip_if_withdrawn("sat", None, "bv_gsa")
    r, k, beat = _gate("sat", "bv_gsa", "min", 200, SEEDS)
    assert beat, f"sat/bv_gsa 未赢随机: r={r} k={k}"

def test_sat_bv_hs_beats_random():
    r, k, beat = _gate("sat", "bv_hs", "min", 200, SEEDS)
    assert beat, f"sat/bv_hs 未赢随机: r={r} k={k}"

def test_sat_sat_mfo_beats_random():
    r, k, beat = _gate("sat", "sat_mfo", "min", 200, SEEDS)
    assert beat, f"sat/sat_mfo 未赢随机: r={r} k={k}"


# ---------------- knapsack (max) 回挂 ----------------
def test_knapsack_bv_gsa_beats_random():
    r, k, beat = _gate("knapsack", "bv_gsa", "max", 200, SEEDS)
    assert beat, f"knapsack/bv_gsa 未赢随机: r={r} k={k}"

def test_knapsack_bv_hs_beats_random():
    r, k, beat = _gate("knapsack", "bv_hs", "max", 200, SEEDS)
    assert beat, f"knapsack/bv_hs 未赢随机: r={r} k={k}"


# ---------------- kpvar 回挂（逐变体，不挂失败域） ----------------
_KPVAR_GSA_HS = ("ssp", "ukp", "bkp", "qkp", "mdkp")
_KPVAR_GSA_HS_FAIL = ("cmp", "mckp", "dkp")  # cmp:19>16 FAIL; mckp / dkp 独立 _MCKP 不挂

def test_kpvar_bv_gsa_hs_beats_random():
    for variant in _KPVAR_GSA_HS:
        if not domains._is_withdrawn("kpvar", variant, "bv_gsa"):
            r, k, beat = _gate_kpvar(variant, "bv_gsa", "min", 200, SEEDS)
            assert beat, f"kpvar/{variant}/bv_gsa 未赢随机: r={r} k={k}"
        if not domains._is_withdrawn("kpvar", variant, "bv_hs"):
            r2, k2, beat2 = _gate_kpvar(variant, "bv_hs", "min", 200, SEEDS)
            assert beat2, f"kpvar/{variant}/bv_hs 未赢随机: r={r2} k={k2}"

def test_kpvar_cmp_bv_mfo_beats_random():
    _skip_if_withdrawn("kpvar", "cmp", "bv_mfo")
    r, k, beat = _gate_kpvar("cmp", "bv_mfo", "min", 200, SEEDS)
    assert beat, f"kpvar/cmp/bv_mfo 未赢随机: r={r} k={k}"

def test_kpvar_failed_variants_dont_expose_bv():
    # 诚实留痕：cmp 不应有 bv_gsa/bv_hs；mckp 不应有 bv_gsa/bv_hs（独立注册表）
    for variant, algo in (("cmp", "bv_gsa"), ("cmp", "bv_hs"), ("mckp", "bv_gsa"), ("mckp", "bv_hs")):
        assert algo not in domains._kpvar_reg(variant), f"{variant} 不应暴露 {algo}"


# ---------------- NSGA-III 多目标 ----------------
def _cov(front):
    return len({(round(f[0] / 50), round(f[1] / 50)) for f in front})


def test_nsga3_moco_nondominated():
    prob = domains.mo_make(seed=7, variant="moco")
    domains.domain_start("multiobj", json.dumps(prob), "nsga3", json.dumps({"max_iter": 200, "seed": 7}))
    last = None
    while True:
        x = domains.domain_step()
        if x is None:
            break
        last = json.loads(x)
    front = last["front"]
    assert last["nd"] >= 5, f"NSGA-III 前沿太小: {last['nd']}"
    for a in front:
        for b in front:
            if a != b and all(a[d] >= b[d] for d in range(2)) and any(a[d] > b[d] for d in range(2)):
                assert False, f"NSGA-III 前沿内出现支配对: {a} 支配 {b}"


def test_nsga3_maop_three_obj():
    prob = domains.mo_make(seed=7, variant="maop")
    domains.domain_start("multiobj", json.dumps(prob), "nsga3", json.dumps({"max_iter": 200, "seed": 7}))
    last = None
    while True:
        x = domains.domain_step()
        if x is None:
            break
        last = json.loads(x)
    assert last["nd"] > 0, "maop 非支配解数为 0"
    assert all(len(p) == 3 for p in last["pop"]), "maop 目标维数非 3"
    pts = last["front"]
    assert len(pts) == last["nd"], f"maop 前沿规模 {len(pts)} ≠ nd {last['nd']}"
    for a in range(len(pts)):
        for b in range(len(pts)):
            if a == b:
                continue
            if pts[a] == pts[b]:
                continue
            if all(pts[a][d] >= pts[b][d] for d in range(3)) and any(pts[a][d] > pts[b][d] for d in range(3)):
                assert False, f"maop 前沿非非支配: {pts[a]} 支配 {pts[b]}"


def test_nsga3_spread_no_worse_than_nsga2():
    _, nl = _run("multiobj", "nsga2", 120, 7, {"variant": "moco"})
    _, xl = _run("multiobj", "nsga3", 120, 7, {"variant": "moco"})
    assert _cov(xl["front"]) >= _cov(nl["front"]), \
        f"NSGA-III 覆盖 {_cov(xl['front'])} < NSGA-II {_cov(nl['front'])}"


def test_nsga3_beats_wsga_random():
    _, wl = _run("multiobj", "wsga", 120, 7, {"variant": "moco"})
    _, rl = _run("multiobj", "random", 120, 7, {"variant": "moco"})
    _, xl = _run("multiobj", "nsga3", 120, 7, {"variant": "moco"})
    assert _cov(xl["front"]) >= _cov(wl["front"]), f"NSGA-III 覆盖 < 加权GA"
    assert _cov(xl["front"]) >= _cov(rl["front"]), f"NSGA-III 覆盖 < 随机"

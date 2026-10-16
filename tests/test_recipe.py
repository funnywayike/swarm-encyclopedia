# -*- coding: utf-8 -*-
"""S7-B 配方引擎测试：组件 IO 契约 / 配方性质 / 拼接环境（Pyodide 等效）验证。"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "py"))

import pytest
from components import build_problem
import recipe
from recipe import run_recipe, RECIPES, RCOMPONENTS

CITIES = [[0, 0], [1, 0], [4, 1], [5, 5], [2, 4], [0, 3], [3, 2], [5, 0], [2, 1], [1, 3]]
PROBLEM = build_problem(CITIES)


def _run_all(r, params=None):
    return [s for s in run_recipe(r, PROBLEM, params or {})]


@pytest.mark.parametrize("r", RECIPES, ids=lambda r: r["id"])
def test_recipe_monotonic(r):
    """最优不回升（引擎核心性质：best 追踪只在改进时更新）。"""
    prev = float("inf")
    for s in _run_all(r):
        assert s["best_cost"] <= prev + 1e-9
        prev = s["best_cost"]


@pytest.mark.parametrize("r", RECIPES, ids=lambda r: r["id"])
def test_recipe_reproducible(r):
    """同种子逐位复现（RNG 管线统一性）。"""
    a = [s["best_cost"] for s in _run_all(r, {"seed": 7, "max_iter": 40})]
    b = [s["best_cost"] for s in _run_all(r, {"seed": 7, "max_iter": 40})]
    assert a == b and len(a) > 10


def test_recipe_improves():
    """随机初始化的配方必须有实质改进（否则引擎/组件装配有 bug）。"""
    r = next(r for r in RECIPES if r["id"] == "steady-ga")
    s = _run_all(r)
    assert (s[0]["best_cost"] - s[-1]["best_cost"]) / s[0]["best_cost"] > 0.10


def test_unknown_component_rejected():
    """装配期校验：槽位引用未知组件在第 0 代前报错。"""
    bad = json.loads(json.dumps(RECIPES[0]))
    bad["slots"]["crossover"] = "nope"
    with pytest.raises(ValueError, match="未知组件"):
        list(run_recipe(bad, PROBLEM, {}))


def test_perm_contract():
    """IO 契约：非法排列被逐代校验拦截。"""
    import recipe as m
    with pytest.raises(ValueError, match="IO 契约"):
        m._assert_perm([0, 1, 1], 3, "test")


def test_registry_schema():
    """注册表 schema 完整性：kind 合法、io/source 必填。"""
    kinds = {"init", "selection", "crossover", "mutation", "replacement",
             "local_search", "terminator"}
    for cid, c in RCOMPONENTS.items():
        assert c["kind"] in kinds, cid
        assert c["io"] and c["source"], cid


def test_registered_in_solvers():
    """install_recipes 后配方出现在 SOLVERS 注册表（前端 meta 驱动）。"""
    import solvers
    meta = json.loads(solvers.list_solvers())
    keys = {m["key"] for m in meta}
    for r in RECIPES:
        assert f"recipe:{r['id']}" in keys
    for m in meta:
        if m["key"].startswith("recipe:"):
            assert m["implemented"] is True
            # specs 覆盖 default_params 且值在定义域内（selfcheck 同款检查的本地版）
            for k, v in m["params"].items():
                assert k in m["specs"], (m["key"], k)
                sp = m["specs"][k]
                assert sp["min"] <= v <= sp["max"], (m["key"], k, v)


def test_start_step_end_to_end():
    """start/step 接口端到端（worker 同路径）。"""
    import solvers
    solvers.start(json.dumps(CITIES), "recipe:ils", json.dumps({"max_iter": 20}))
    prev = float("inf")
    n = 0
    while True:
        s = solvers.step()
        if s is None:
            break
        d = json.loads(s)
        assert d["best_cost"] <= prev + 1e-9
        prev = d["best_cost"]
        n += 1
    assert n >= 10


def test_concatenated_namespace_parity():
    """拼接环境（Pyodide solvers_src.js）与本地 import 行为一致：
    用与 gen_solvers_src 相同的方式拼接源码后 exec，list_solvers 必须含配方。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    strip = lambda s: s.replace("from __future__ import annotations\n", "", 1)  # noqa: E731
    src = "\n\n".join(
        strip(open(os.path.join(root, "py", f), encoding="utf-8").read())
        for f in ("components.py", "recipe.py", "solvers.py"))
    ns: dict = {}
    exec(compile(src, "<concatenated>", "exec"), ns)
    meta = json.loads(ns["list_solvers"]())
    keys = {m["key"] for m in meta}
    assert "recipe:memetic" in keys
    # 拼接环境跑一代
    ns["start"](json.dumps(CITIES), "recipe:steady-ga", json.dumps({"max_iter": 5}))
    assert ns["step"]() is not None


# ============================ S7-D：F6-F9 升格配方测试 ============================

def test_hh_credit_assignment():
    """选择式 HH 的信用机制真在跑：反馈改进后对应低层启发式分数上升、其余衰减。"""
    ctx: dict = {}
    rng = random.Random(3)
    for _ in range(20):
        t2 = recipe._mut_hh(list(range(10)), rng, 1.0, ctx)
        assert sorted(t2) == list(range(10))
    assert "hh_scores" in ctx
    before = dict(ctx["hh_scores"])
    ctx["hh_last"] = "reverse"
    recipe._fb_hh(ctx, 10.0)
    assert ctx["hh_scores"]["reverse"] > before["reverse"]
    assert ctx["hh_scores"]["swap"] < before["swap"]


def test_saea_eval_budget_counted():
    """SAEA：精确评估次数 = 初始种群 + eval_budget × 代数（预筛不花评估）。"""
    r = next(x for x in RECIPES if x["id"] == "saea")
    states = _run_all(r, {"seed": 5, "max_iter": 15})
    assert states[-1]["extra"]["sa_evals"] == r["default_params"]["pop"] + \
        r["default_params"]["eval_budget"] * states[-1]["iteration"]


def test_upgrade_recipes_improve_on_30city():
    """升格四配方在 30 城实例上相对初始最优都有实质改进（防假跑）。"""
    rng = random.Random(11)
    big = build_problem([[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(30)])
    for rid, margin in (("hh", 0.02), ("saea", 0.005), ("matheur", 0.01),
                        ("mapelites", 0.01)):
        r = next(x for x in RECIPES if x["id"] == rid)
        states = [s for s in run_recipe(r, big, {"seed": 7, "max_iter": 80})]
        drop = (states[0]["best_cost"] - states[-1]["best_cost"]) / states[0]["best_cost"]
        assert drop > margin, (rid, drop)


def test_matheur_fixopt_beats_nn():
    """fix-and-optimize：Held-Karp 精确修复在 30 城实例上改进最近邻起点。"""
    rng = random.Random(11)
    big = build_problem([[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(30)])
    r = next(x for x in RECIPES if x["id"] == "matheur")
    states = [s for s in run_recipe(r, big, {"seed": 5, "max_iter": 60, "patience": 40})]
    assert states[-1]["best_cost"] < states[0]["best_cost"]


def test_mapelites_diversity():
    """MAP-Elites：30 城实例上行为档案占据多格（QD 的多样性真在产生）。"""
    rng = random.Random(11)
    big = build_problem([[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(30)])
    r = next(x for x in RECIPES if x["id"] == "mapelites")
    states = [s for s in run_recipe(r, big, {"seed": 5, "max_iter": 100})]
    assert states[-1]["extra"]["qd_cells"] >= 4


def test_upgrade_concat_parity():
    """S7-D：拼接名字空间（Pyodide 等效）里新 mode（sa/qd）能跑一代。"""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    strip = lambda s: s.replace("from __future__ import annotations\n", "", 1)  # noqa: E731
    src = "\n\n".join(
        strip(open(os.path.join(root, "py", f), encoding="utf-8").read())
        for f in ("components.py", "recipe.py", "solvers.py"))
    ns: dict = {}
    exec(compile(src, "<concat-s7d>", "exec"), ns)
    for key in ("recipe:saea", "recipe:mapelites", "recipe:hh", "recipe:matheur"):
        ns["start"](json.dumps(CITIES), key, json.dumps({"max_iter": 3}))
        assert ns["step"]() is not None

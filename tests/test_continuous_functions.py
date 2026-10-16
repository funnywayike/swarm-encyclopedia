# -*- coding: utf-8 -*-
"""连续基准函数：最优值 = 0 的位置对、所有算法只在搜索范围内评价和上报、页面热力图的 JS 镜像与 Python 公式逐点一致。"""
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "py"))

import domains as D  # noqa: E402

NEW = ("griewank", "levy", "schwefel", "zakharov", "dixon_price", "styblinski_tang")


def _optimum_point(fn, d):
    if fn in ("levy", "rosenbrock"):
        return [1.0] * d
    if fn == "schwefel":
        return [420.9687462275036] * d
    if fn == "styblinski_tang":
        return [-2.903534027771178] * d
    if fn == "dixon_price":
        return [2 ** (-(2 ** (i + 1) - 2) / 2 ** (i + 1)) for i in range(d)]
    return [0.0] * d


@pytest.mark.parametrize("fn", sorted(D.FUNCS))
def test_every_function_has_its_documented_optimum_zero(fn):
    f, lo, hi, opt = D.FUNCS[fn]
    assert opt == 0.0
    for d in (2, 5, 10):
        x = _optimum_point(fn, d)
        assert all(lo <= v <= hi for v in x)
        assert f(x) == pytest.approx(0.0, abs=1e-9), (fn, d)
    rng = random.Random(1)
    for _ in range(300):  # 范围内任何点都不会比 0 更好
        assert f([rng.uniform(lo, hi) for _ in range(4)]) >= -1e-9


def test_new_functions_are_registered_and_offered_on_the_page():
    assert set(NEW) <= set(D.FUNCS) and set(NEW) <= set(D._NEW_FUNCS)
    html = open(os.path.join(ROOT, "problem", "continuous", "index.html"), encoding="utf-8").read()
    for fn in NEW:
        assert f'"fn": "{fn}"' in html, f"连续页的实例下拉里没有 {fn}"


@pytest.mark.parametrize("fn", sorted(D.FUNCS))
def test_no_algorithm_evaluates_or_reports_outside_the_search_box(fn):
    """CMA-ES 曾直接在范围外评价：Schwefel 上范围外的值更低，「最优」跑到了范围外（-1e13）。"""
    lo, hi = D.FUNCS[fn][1], D.FUNCS[fn][2]
    for dim in (2, 5):
        pre = json.dumps(D.cn_make(fn=fn, dim=dim))
        for a in [x["key"] for x in json.loads(D.domain_list("continuous", {}))["algos"]]:
            D.domain_start("continuous", pre, a, json.dumps({"max_iter": 25, "seed": 7}))
            prev = float("inf")
            while True:
                s = D.domain_step()
                if s is None:
                    break
                st = json.loads(s)
                pts = [st["gbest_pos"]] + st.get("particles", [])
                for q in pts:
                    assert all(lo - 1e-9 <= v <= hi + 1e-9 for v in q), f"{fn}/{dim}D/{a}：{q} 在范围 [{lo},{hi}] 之外"
                assert st["best"] >= -1e-9, f"{fn}/{a}：最优值 {st['best']} < 0，不可能（范围内最小值是 0）"
                assert st["best"] <= prev + 1e-12, f"{fn}/{dim}D/{a}：历史最优变差了 {prev} → {st['best']}"
                prev = st["best"]


@pytest.mark.skipif(shutil.which("node") is None, reason="需要 node 来执行页面里的 JS 镜像")
def test_js_heatmap_mirrors_match_the_python_formulas():
    js = open(os.path.join(ROOT, "js", "domain_page.js"), encoding="utf-8").read()
    m = re.search(r"const FN_JS = \{.*?\n\};", js, re.S)
    assert m, "没找到 FN_JS"
    rng = random.Random(3)
    cases = []
    for fn in D.FUNCS:
        lo, hi = D.FUNCS[fn][1], D.FUNCS[fn][2]
        for _ in range(40):
            cases.append((fn, rng.uniform(lo, hi), rng.uniform(lo, hi)))
    script = m.group(0) + "\nconst cases = " + json.dumps(cases) + ";\nconsole.log(JSON.stringify(cases.map(([k, x, y]) => FN_JS[k] ? FN_JS[k](x, y) : null)));"
    out = subprocess.run(["node", "-"], input=script, capture_output=True, text=True, encoding="utf-8", timeout=60)  # 脚本很长，走标准输入（命令行有长度上限）
    assert out.returncode == 0, out.stderr[:300]
    vals = json.loads(out.stdout)
    missing = sorted({c[0] for c, v in zip(cases, vals) if v is None})
    assert not missing, f"这些函数页面里没有 JS 镜像（热力图会静默回退成碗形）：{missing}"
    for (fn, x, y), v in zip(cases, vals):
        want = D.FUNCS[fn][0]([x, y])
        assert v == pytest.approx(want, rel=1e-9, abs=1e-9), f"{fn}({x:.3f},{y:.3f})：JS {v} ≠ Python {want}"

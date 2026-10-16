# -*- coding: utf-8 -*-
"""标准化数据层（py/validate.py）测试：内置实例必须全部通过自己的校验器；坏数据必须被拦下；
解析器（JSON 信封 / CSV / DIMACS）往返一致。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "py"))

import domains as D  # noqa: E402
import validate as V  # noqa: E402

# 域/变体清单来自登记表（py/registry.py），不在这里再抄一份
from registry import PLAIN, VARIANTS  # noqa: E402


def _preset(domain, variant=None):
    return json.loads(D.domain_preset(domain, 7, {"variant": variant} if variant else {}))


def _errs(res):
    return " | ".join(f"{e['path']}: {e['msg']}" for e in res["errors"])


# ---------------------------------------------------------------- 内置实例 → 校验器

def test_every_builtin_instance_passes_its_validator_and_runs():
    cases = [(d, None) for d in PLAIN] + [(d, v) for d, vs in VARIANTS.items() for v in vs]
    assert len(cases) >= 9 + 65 + 10 + 5 + 3 + 2
    bad = []
    for dom, var in cases:
        res = V.validate(dom, _preset(dom, var), variant=var, dry_run=True)
        if not res["ok"]:
            bad.append(f"{dom}/{var}: {_errs(res)}")
    assert not bad, "\n".join(bad)


def test_every_problem_page_preset_validates_and_has_a_sample():
    """站点上每个可交互问题页的示例实例，都必须通过校验器，且「下载本页示例数据」链接不能 404。"""
    import glob
    import re
    pages = glob.glob(os.path.join(HERE, "..", "problem", "**", "index.html"), recursive=True)
    checked = 0
    for f in pages:
        t = open(f, encoding="utf-8").read()
        m = re.search(r'window\.PAGE_DOMAIN = "([^"]+)"', t)
        pm = re.search(r'window\.PAGE_PRESETS = (\{.*?\});\n', t)
        if not m or not pm or not V.supported(m.group(1)):  # 排程四域走宽松旧路径
            continue
        dom = m.group(1)
        for opts in json.loads(pm.group(1)).values():
            var = opts.get("variant")
            pre = json.loads(D.domain_preset(dom, 7, opts))
            res = V.validate(dom, pre, variant=var or pre.get("variant"))
            assert res["ok"], f"{os.path.relpath(f, HERE)}: {_errs(res)}"
            name = var or ("moco" if dom == "multiobj" else dom)  # 与 domain_page.js 的示例链接规则一致
            assert os.path.exists(os.path.join(HERE, "..", "samples", dom, f"{name}.json")), f"缺示例 {dom}/{name}"
            checked += 1
    assert checked >= 100


def test_continuous_every_function():
    for fn in D.FUNCS:
        res = V.validate("continuous", {"fn": fn, "dim": 5}, dry_run=True)
        assert res["ok"], _errs(res)
        assert res["problem"]["fn"] == fn and res["problem"]["dim"] == 5


def test_tsp_accepts_bare_list_and_object():
    pts = [[0, 0], [1, 0], [1, 1], [0, 1]]
    assert V.validate("tsp", pts)["ok"]
    assert V.validate("tsp", {"cities": pts})["ok"]
    assert not V.validate("tsp", pts[:2])["ok"]
    res = V.validate("tsp", pts + [[0, 0]])
    assert res["ok"] and res["warnings"]  # 重复坐标只警告


# ---------------------------------------------------------------- 坏数据：以前会崩溃的

def test_crash_inputs_now_give_friendly_errors():
    cases = [
        ("knapsack", {"items": [[3, 4], [4, 5]]}, "cap"),                      # 缺容量（原 KeyError）
        ("knapsack", {"cap": 10, "items": [["a", 4], [4, 5]]}, "items[0][0]"),  # 文本当数（原 TypeError）
        ("graphcolor", {"n": 3, "edges": [[0, 7]]}, "edges"),                  # 顶点越界（原 IndexError）
        ("qubo", {"Q": [[1, 2], [3, 4], [5, 6]]}, "Q"),                         # 非方阵（原 IndexError）
        ("knapsack", {"cap": 10, "items": "oops"}, "items"),
        ("sat", {"n_vars": 2, "clauses": [[1, 5]]}, "clauses"),                # 变量超范围
        ("sat", {"n_vars": 2, "clauses": [[1, 0]]}, "clauses[0][1]"),          # 文字 0
        ("gap", {"c": [[1, 2]], "r": [[1]], "cap": [5]}, "r"),                  # 形状不符
        ("continuous", {"fn": "foo", "dim": 2}, "fn"),
        ("continuous", {"fn": "sphere", "dim": 100000}, "dim"),
    ]
    for dom, data, path in cases:
        res = V.validate(dom, data)
        assert not res["ok"], f"{dom} {data} 应被拒绝"
        assert any(path in e["path"] for e in res["errors"]), f"{dom}: 期望路径含 {path}，实得 {_errs(res)}"


# ---------------------------------------------------------------- 坏数据：以前会悄悄给错结果的

def test_silent_wrong_inputs_are_rejected():
    assert not V.validate("knapsack", {"cap": 10, "items": [[-3, 4], [4, 5]]})["ok"]        # 负重量
    assert not V.validate("knapsack", {"cap": 10, "items": []})["ok"]                        # 空实例
    assert not V.validate("binpack", {"cap": 5, "items": [9, 3]})["ok"]                      # 物品比箱子大
    assert not V.validate("setcover", {"sets": [[1, 0, 0]], "costs": [1]})["ok"]             # 有元素覆盖不到
    assert not V.validate("setcover", {"sets": [[1, 2, 0]], "costs": [1]})["ok"]             # 覆盖矩阵含 2
    assert not V.validate("gap", {"c": [[1, 1]], "r": [[9, 1]], "cap": [5]})["ok"]           # 任务 0 谁都装不下
    assert not V.validate("multiobj", {"cap": 5, "items": [[1, 2], [2, 3]]})["ok"]           # 列数不对


def test_one_based_graph_hint():
    res = V.validate("graphcolor", {"n": 3, "edges": [[1, 2], [2, 3]]})
    assert not res["ok"] and "从 1 开始" in _errs(res)


# ---------------------------------------------------------------- 规整：冗余字段由数据推出

def test_n_is_derived_and_mismatch_is_only_a_warning():
    res = V.validate("knapsack", {"n": 99, "cap": 10, "items": [[3, 4], [4, 5], [5, 7]]}, dry_run=True)
    assert res["ok"] and res["problem"]["n"] == 3
    assert any(w["path"] == "n" for w in res["warnings"])


def test_graph_without_positions_gets_layout_and_runs():
    res = V.validate("graphcolor", {"edges": [[0, 1], [1, 2], [2, 0], [2, 3]]}, dry_run=True)
    assert res["ok"], _errs(res)
    p = res["problem"]
    assert p["n"] == 4 and len(p["pos"]) == 4 and all(len(c) == 2 for c in p["pos"])
    assert any("推断" in w["msg"] for w in res["warnings"])


def test_graph_dedupes_edges_and_drops_loops():
    res = V.validate("graphcolor", {"n": 3, "edges": [[0, 1], [1, 0], [2, 2], [1, 2]]})
    assert res["ok"] and res["problem"]["edges"] == [[0, 1], [1, 2]]
    assert len(res["warnings"]) == 2


def test_entryseq_n_derived_from_data_and_mismatch_rejected():
    pre = _preset("entryseq", "vrp")
    no_n = {k: v for k, v in pre.items() if k != "n"}
    res = V.validate("entryseq", no_n, variant="vrp", dry_run=True)
    assert res["ok"] and res["problem"]["n"] == pre["n"]
    res = V.validate("entryseq", dict(pre, n=pre["n"] + 3), variant="vrp")
    assert not res["ok"] and any(e["path"] == "n" for e in res["errors"])


def test_entryseq_missing_field_and_wrong_row_width():
    pre = _preset("entryseq", "vrp")
    miss = {k: v for k, v in pre.items() if k != "demand"}
    assert any(e["path"] == "demand" for e in V.validate("entryseq", miss, variant="vrp")["errors"])
    bad = dict(pre, pts=[[0, 0], [1]] + pre["pts"][2:])
    assert any("pts[1]" in e["path"] for e in V.validate("entryseq", bad, variant="vrp")["errors"])


def test_variant_required_and_unknown_variant():
    assert V.validate("kpvar", _preset("kpvar", "ssp"))["ok"]  # 实例自带 variant 字段，不必另传
    assert not V.validate("entryseq", {"n": 3}, variant=None)["ok"]
    assert not V.validate("entryseq", {"n": 3}, variant="nope")["ok"]
    assert not V.validate("nosuchdomain", {})["ok"]


def test_gcvar_derives_line_and_total_graph_like_the_generator():
    for var in ("edgecolor", "totalcolor"):
        ref = _preset("gcvar", var)
        res = V.validate("gcvar", {"edges": ref["edges"], "n": ref["n"]}, variant=var, dry_run=True)
        assert res["ok"], _errs(res)
        key = "ladj" if var == "edgecolor" else "tadj"
        assert [sorted(a) for a in res["problem"][key]] == [sorted(a) for a in ref[key]]


def test_gcvar_precolor_conflict_detected():
    res = V.validate("gcvar", {"n": 2, "edges": [[0, 1]], "precol": [0, 0]}, variant="precolor")
    assert not res["ok"] and "同一颜色" in _errs(res)


# ---------------------------------------------------------------- 解析器

def test_envelope_roundtrip_all_core_presets():
    for dom in PLAIN:
        pre = _preset(dom)
        env = V.to_envelope(dom, pre)
        d, data, issues = V.load(json.dumps(env))
        assert (d, data) == (dom, pre) and not issues.errors


def test_envelope_domain_mismatch_and_experiment_format():
    env = V.to_envelope("knapsack", _preset("knapsack"))
    _, data, issues = V.load(env, domain="binpack")
    assert data is None and issues.errors
    exp = {"format": "domain-experiment/v1", "domain": "qubo", "problem": _preset("qubo")}
    d, data, issues = V.load(exp)
    assert d == "qubo" and data == exp["problem"]


def test_guess_domain_only_when_unambiguous():
    assert V.load({"clauses": [[1, 2]]})[0] == "sat"
    assert V.load({"Q": [[1]]})[0] == "qubo"
    assert V.load({"fn": "sphere", "dim": 2})[0] == "continuous"
    d, data, issues = V.load({"items": [[1, 2]], "cap": 3})  # 背包/装箱/多目标都长这样：不猜
    assert d is None and issues.errors


def test_csv_knapsack_binpack_graph_qubo_tsp():
    r = V.check_text("# cap=10\nweight,value\n3,4\n4,5\n5,7\n", domain="knapsack", dry_run=True)
    assert r["ok"], _errs(r)
    assert r["problem"]["n"] == 3
    r = V.check_text("# cap=10\nsize\n4\n5\n6\n", domain="binpack", dry_run=True)
    assert r["ok"] and r["problem"]["items"] == [4, 5, 6]
    r = V.check_text("# n=4\nu,v\n0,1\n1,2\n2,3\n", domain="graphcolor", dry_run=True)
    assert r["ok"] and r["problem"]["n"] == 4 and len(r["problem"]["edges"]) == 3
    r = V.check_text("1,2\n3,4\n5,6\n", domain="qubo")
    assert not r["ok"]  # 3×2 的矩阵不是方阵
    assert V.check_text("1,2\n3,4\n", domain="qubo", dry_run=True)["ok"]
    r = V.check_text("x,y\n0,0\n1,0\n1,1\n0,1\n", domain="tsp")
    assert r["ok"] and len(r["problem"]["cities"]) == 4
    assert not V.check_text("x,y\n0,0\n1,0\n1,1\n", domain="tsp")["ok"]  # 3 城市不需要求解
    r = V.check_text("3,4\n4,5\n", domain="knapsack")  # 缺容量
    assert not r["ok"] and any(e["path"] == "cap" for e in r["errors"])
    r = V.check_text("3,x\n", domain="knapsack")
    assert not r["ok"]


def test_dimacs_cnf_and_col():
    cnf = "c demo\np cnf 3 2\n1 -2 0\n2 3 0\n"
    r = V.check_text(cnf, filename="a.cnf", dry_run=True)
    assert r["domain"] == "sat" and r["ok"], _errs(r)
    assert r["problem"] == {"n_vars": 3, "clauses": [[1, -2], [2, 3]]}
    col = "c demo\np edge 4 3\ne 1 2\ne 2 3\ne 3 4\n"
    r = V.check_text(col, filename="g.col", dry_run=True)
    assert r["domain"] == "graphcolor" and r["ok"], _errs(r)
    assert r["problem"]["edges"] == [[0, 1], [1, 2], [2, 3]]  # 1 起始 → 0 起始
    assert not V.check_text("p cnf 3\n", filename="x.cnf")["ok"]


def test_every_shipped_sample_file_validates():
    root = os.path.join(HERE, "..", "samples")
    seen = 0
    for dirpath, _, files in os.walk(root):
        for fn in files:
            path = os.path.join(dirpath, fn)
            dom = os.path.basename(dirpath) if os.path.basename(dirpath) != "samples" else None
            if fn.startswith("cities_sample"):  # 旧的 TSP 示例：裸坐标，需显式指定域
                dom = "tsp"
            with open(path, encoding="utf-8") as f:
                res = V.check_text(f.read(), domain=dom, filename=fn, dry_run=True)
            assert res["ok"], f"{path}: {_errs(res)}"
            seen += 1
    assert seen >= 80


def test_invalid_json_and_empty_file():
    assert not V.check_text("{not json", domain="knapsack")["ok"]
    assert not V.check_text("   ", domain="knapsack")["ok"]


def test_size_limits_enforced():
    big = {"cap": 100, "items": [[1, 1]] * (V.LIMITS["knapsack"] + 1)}
    res = V.validate("knapsack", big)
    assert not res["ok"] and "上限" in _errs(res)

# -*- coding: utf-8 -*-
"""算法分类只有一个来源：data/algos.json 的 family + data/families.json 的家族定义。
下拉框标签（TSP 页、各问题域页）、站点页面位置都必须与它一致。"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "py"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import domains as D  # noqa: E402
import gen_taxonomy  # noqa: E402
import registry as REG  # noqa: E402
import solvers as S  # noqa: E402
import taxonomy as T  # noqa: E402


def _json(name):
    with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
        return json.load(f)


FAMS = _json("families.json")
ALGOS = _json("algos.json")


def test_generated_taxonomy_module_is_up_to_date():
    with open(os.path.join(ROOT, "py", "taxonomy.py"), encoding="utf-8", newline="") as f:
        assert f.read() == gen_taxonomy.render(), "py/taxonomy.py 过期：运行 python tools/gen_taxonomy.py（或 build_pages.py）"


def test_families_are_well_formed():
    ids = [f["id"] for f in FAMS]
    assert len(ids) == len(set(ids)) and len({f["dir"] for f in FAMS}) == len(FAMS)
    assert all(f.get("short") for f in FAMS), "每个家族都要有 short（下拉框分组标签）"
    assert len({f["short"] for f in FAMS}) == len(FAMS), "short 标签不能重名"
    assert {a["family"] for a in ALGOS} <= set(ids)


def test_tsp_dropdown_groups_equal_site_families():
    short = {f["id"]: f["short"] for f in FAMS}
    by_key = {s["key"]: s for s in json.loads(S.list_solvers())}
    for a in ALGOS:
        assert by_key[a["key"]]["category"] == short[a["family"]], a["key"]


def test_domain_kernels_have_one_consistent_category_everywhere():
    """回归：同一个内核（如 bv_pso）曾在不同域里一会儿叫「群体智能」一会儿叫「人类与社会启发」。"""
    seen = collections.defaultdict(set)
    for dom, var in REG.cases(include_scheduling=True):
        for a in json.loads(D.domain_list(dom, {"variant": var} if var else {}))["algos"]:
            seen[a["key"]].add(a["category"])
    short = {a["key"]: next(f["short"] for f in FAMS if f["id"] == a["family"]) for a in ALGOS}
    checked = 0
    for key, cats in seen.items():
        base = key.split("_", 1)[1] if key[:3] in ("bv_", "pk_", "as_") else key
        base = {"cmaes": "cma-es"}.get(base, base)
        if base in short:  # 在家族体系里的内核：所有域/变体里标签必须一致，且等于它的家族标签
            assert cats == {short[base]}, (key, sorted(cats), short[base])
            checked += 1
    assert checked > 50  # random/greedy/hc 等不在家族体系里的基线与构造件，各域可有自己的标签


def test_every_algorithm_page_lives_in_its_familys_directory():
    fam_dir = {f["id"]: f["dir"] for f in FAMS}
    for a in ALGOS:
        page = os.path.join(ROOT, "algo", fam_dir[a["family"]], a["key"], "index.html")
        with open(page, encoding="utf-8") as f:
            assert 'http-equiv="refresh"' not in f.read(), f"{a['key']} 在它的家族目录里却是重定向桩"
    # 反过来：别的家族目录里留下的只能是重定向桩
    moved = {(m["from_dir"], m["slug"]) for m in _json("moved_pages.json")}
    for f in FAMS:
        base = os.path.join(ROOT, "algo", f["dir"])
        for sub in os.listdir(base):
            idx = os.path.join(base, sub, "index.html")
            if not os.path.isfile(idx):
                continue
            real = [a for a in ALGOS if a["key"] == sub]
            if f["dir"] == "f6-hybrid":  # 配方页（recipe:ils 等）与同名算法共用 id，不是算法页
                continue
            if real and real[0]["family"] != f["id"]:
                assert (f["dir"], sub) in moved, f"algo/{f['dir']}/{sub} 是旧家族残留，但没有登记在 moved_pages.json"
                with open(idx, encoding="utf-8") as fh:
                    assert 'http-equiv="refresh"' in fh.read()


# ---------------------------------------------------------------- 问题分类

def test_problem_groups_are_defined_once_and_every_problem_belongs_to_one():
    groups = _json("problem_groups.json")
    ids = [g["id"] for g in groups]
    assert len(ids) == len(set(ids)) and len({g["nav"] for g in groups}) == len(groups)
    types = _json("problems.json")["abstract_types"]
    assert {t["group"] for t in types} <= set(ids), {t["group"] for t in types} - set(ids)
    empty = [g for g in ids if not any(t["group"] == g for t in types)]
    assert not empty, f"没有任何问题的分类：{empty}"


def test_open_bucket_is_small_and_graph_problems_are_not_in_it():
    """回归：「开放登记」曾是 17 项（23%）的兜底桶，混着多项式可解的图论问题与调度/路径问题。"""
    types = _json("problems.json")["abstract_types"]
    group = {t["id"]: t["group"] for t in types}
    assert sum(1 for g in group.values() if g == "open") <= 8
    for pid in ("mst", "shortestpath", "maxflow", "mincostflow", "topsort", "gmatch"):
        assert group[pid] == "network", pid
    for pid in ("fjsp", "carp", "rpostman", "orienteering"):
        assert group[pid] == "sequencing", pid


def test_no_module_keeps_its_own_copy_of_the_group_list():
    """四处消费者必须都读 problem_groups，不能再各抄一份标签/顺序。"""
    for rel in ("build_pages.py", "pages_meta.py", "pages_problems.py"):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            src = f.read()
        assert "problem_groups." in src, rel
        assert '"timetabling": "Ⅹ' not in src, f"{rel} 里还有一份手抄的分类标签"


def test_frontend_does_not_carry_its_own_category_list():
    """回归：tool.js 曾写死 6 个分类名，家族一改，不在清单里的 12 个算法就从 TSP 下拉框里消失了。
    分组标签与顺序必须来自引擎（taxonomy → list_solvers 的 category / rank）。"""
    for rel in ("tool.js", "compare.js", "domain_page.js"):
        with open(os.path.join(ROOT, "js", rel), encoding="utf-8") as f:
            src = f.read()
        for label in [f["short"] for f in FAMS] + ["构造式"]:
            assert f'"{label}"' not in src, f"js/{rel} 里写死了分类名 {label!r}"
    with open(os.path.join(ROOT, "js", "tool.js"), encoding="utf-8") as f:
        assert "rank" in f.read(), "tool.js 应按引擎给的 rank 排分组"


def test_every_problem_page_is_reachable_from_the_problem_overview():
    """回归：「开放登记」类的问题页（双层优化、鲁棒优化、多模态、动态优化…）曾没有任何入口——
    总览与导航都不列这一类，页面只存在于站点地图里。"""
    with open(os.path.join(ROOT, "problem", "index.html"), encoding="utf-8") as f:
        overview = f.read()
    missing = []
    for t in _json("problems.json")["abstract_types"]:
        if t.get("status") == "page" and f"problem/{t['dir']}/" not in overview:
            missing.append(t["dir"])
    assert not missing, f"总览页没有链到这些问题页：{missing}"

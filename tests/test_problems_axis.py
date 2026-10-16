# -*- coding: utf-8 -*-
"""问题轴 A 期（背包变体扩展）对账测试：缩写唯一、出处非空、命名勘误、新页/新边接线。

对应 HANDOFF 验收链：pytest 全绿是交付前提之一。A 期范围见 docs/design-problem-axis-expansion.md。
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBLEMS = json.load(open(os.path.join(ROOT, "data", "problems.json"), encoding="utf-8"))
MAPPING = json.load(open(os.path.join(ROOT, "data", "mapping.json"), encoding="utf-8"))
VARIANTS = PROBLEMS["knapsack_variants"]
PIDX = MAPPING["problem_index"]
REDS = MAPPING["reductions"]


def _page(url: str) -> str:
    return open(os.path.join(ROOT, url.lstrip("/").rstrip("/"), "index.html"),
                encoding="utf-8").read()


def test_variants_count_and_abbr_unique():
    assert len(VARIANTS) == 10, f"背包变体应为 10（现 {len(VARIANTS)}）"
    abbrs = [v["abbr"] for v in VARIANTS if v.get("abbr")]
    assert len(abbrs) == len(set(abbrs)), "缩写撞车"
    expected = {"bounded": "BKP", "unbounded": "UKP", "changemaking": "CMP",
                "multiple": "MKP-m", "multiplechoice": "MCKP", "multidim": "MKP",
                "quadratic": "QKP", "subsetsum": "SSP"}
    for vid, ab in expected.items():
        got = next((v.get("abbr") for v in VARIANTS if v["id"] == vid), None)
        assert got == ab, f"{vid} 缩写应为 {ab}，现 {got}"


def test_variants_sources_non_empty():
    for v in VARIANTS:
        assert v.get("sources"), f"变体 {v['id']} 缺出处 sources"


def test_new_pages_built_with_abbr_in_h1():
    for pid, ab in (("unbounded", "UKP"), ("changemaking", "CMP"), ("multiplechoice", "MCKP")):
        html = _page(f"/problem/knapsack/{pid}/")
        assert ab in html, f"{pid} 页缺缩写 {ab}"


def test_naming_errata_both_pages():
    multi = _page("/problem/knapsack/multiple/")
    assert "多背包" in multi and "MKP-m" in multi and "多重背包" in multi
    md = _page("/problem/knapsack/multidim/")
    assert "MKP" in md and "多维背包" in md


def test_problem_index_and_pos_cover_new_variants():
    for pid in ("unbounded", "changemaking", "multiplechoice"):
        assert pid in PIDX, f"problem_index 缺 {pid}"
        assert _page_exists(PIDX[pid]["url"]), f"{pid} 无页面"
    pos = MAPPING["graph"]["pos"]
    assert set(pos) <= set(PIDX), "graph.pos 的节点必须都在 problem_index 里"
    for pid in ("unbounded", "changemaking", "multiplechoice"):
        assert pid in pos


def _page_exists(url: str) -> bool:
    return os.path.isfile(os.path.join(ROOT, url.lstrip("/").rstrip("/"), "index.html"))


def test_new_reduction_edges_have_src():
    pairs = {(r["from"], r["to"]) for r in REDS}
    for edge in (("bounded", "knapsack"), ("unbounded", "bounded"),
                 ("changemaking", "unbounded"), ("multiplechoice", "knapsack")):
        assert edge in pairs, f"缺归约边 {edge}"
    for r in REDS:
        if r["from"] in ("bounded", "unbounded", "changemaking", "multiplechoice"):
            assert r.get("src"), f'边 {r["from"]}→{r["to"]} 缺 src'


# ---------- B 期：抽象类型层（SCP/MIS 页 + 词条级登记） ----------

ABSTRACT = PROBLEMS.get("abstract_types", [])
A_PAGES = [t for t in ABSTRACT if t.get("status") == "page"]
A_ENTRIES = [t for t in ABSTRACT if t.get("status") == "entry"]


def test_abstract_abbr_unique_sitewide():
    abbrs = ([v["abbr"] for v in VARIANTS if v.get("abbr")]
             + [t["abbr"] for t in ABSTRACT if t.get("abbr")])
    assert len(abbrs) == len(set(abbrs)), "缩写全站撞车"


PINNED_PAGES = ["scp", "mis", "bpp2d", "spp", "vsbpp", "csp", "lcp", "ecp", "prext", "tcp", "sat", "maxsat", "bbob", "zdt", "dtlz", "maop", "moco", "uflp", "lop", "vrp", "vrptw", "vrpstw", "mdvrp", "sms", "fss", "jss", "lap", "tdm", "gpp", "maxcut", "csplogic", "etp", "ctp", "nrp", "cflp", "lrp", "stp", "ndp", "cbbb", "nbbb", "lbbb", "ebbb", "prefmo", "decompo", "indicmo", "blo", "ro", "mmo", "dop", "ged", "vcover", "domset", "mclique", "setpack", "hset", "fvs", "hcycle", "lpath", "qap", "pmedian", "pcenter", "freqasg", "fjsp", "carp", "rpostman", "ttp", "sls", "oss", "rcpsp", "proteinfold", "msa", "orienteering", "mst", "shortestpath", "maxflow", "mincostflow", "topsort", "gmatch", "atsp", "pms", "numpart", "kmeans", "ecd"]  # 2026-10 截止已有的抽象问题页


def test_abstract_pages_full_schema():
    # 新增页面不需要改这个测试；只守「已有的页面不能悄悄消失」，且 id 不重复
    got = [t["id"] for t in A_PAGES]
    assert len(got) == len(set(got)), "抽象页 id 重复"
    missing = set(PINNED_PAGES) - set(got)
    assert not missing, f"这些页面不见了：{sorted(missing)}（确实要删的话同时改 PINNED_PAGES）"
    for t in A_PAGES:
        for f in ("model", "diff", "algo", "en", "abbr", "gj", "dir"):
            assert t.get(f), f"抽象页 {t['id']} 缺 {f}"
        assert len(t["sources"]) >= 3, f"{t['id']} 出处不足"


def test_abstract_entries_schema():
    # 所有抽象类型都已有独立页面：entry 集合应为空（回归守卫）
    assert set(t["id"] for t in A_ENTRIES) == set()
    for t in A_ENTRIES:
        assert t.get("en") and t.get("note"), f"词条 {t['id']} 缺 en/note"
        assert t.get("sources"), f"词条 {t['id']} 缺 sources"


def test_abstract_pages_built_with_honesty_banner():
    for t in A_PAGES:
        html = _page(f"/problem/{t['dir']}/")
        # G 期：有引擎页内嵌演示（PAGE_DOMAIN 接线），无引擎页保留诚实横幅
        # （纯内容版「无在线演示」或枢纽跳转版「无专属引擎」，皆不许虚构成绩）
        if "PAGE_DOMAIN" in html:
            assert "js/domain_page.js" in html and "vizCanvas" in html, \
                f"{t['dir']} 演示接线不完整"
        else:
            assert "无在线演示" in html or "无专属引擎" in html, f"{t['dir']} 缺诚实横幅"
        assert t["abbr"] in html and t["gj"] in html


def test_scp_mis_mappings_literature_only():
    new_ids = {t["id"] for t in A_PAGES}
    rows = [s for s in MAPPING["algo_solves"] if s["problem"] in new_ids]
    assert len(rows) >= 4
    for s in rows:
        # 已求解化的抽象页（C 期 csp 复用装箱引擎等）允许实测级条目（必须带 demo）；
        # 无引擎页仍必须文献级带 src——分级诚实，不许虚构成绩
        t = next(t for t in A_PAGES if t["id"] == s["problem"])
        has_engine = "PAGE_DOMAIN" in _page(f"/problem/{t['dir']}/")
        if has_engine:
            assert (s["tier"] == "实测" and s.get("demo")) or (s["tier"] == "文献" and s.get("src")), \
                f'{s["algo"]}→{s["problem"]} 引擎页须实测带 demo 或文献带 src'
        else:
            assert s["tier"] == "文献" and s.get("src"), f'{s["algo"]}→{s["problem"]} 必须文献级带 src'


def test_entries_rendered_on_reductions_page():
    html = _page("/problem/reductions/")
    assert "全谱词条" in html
    for t in A_ENTRIES:
        assert t["abbr"] in html, f"归约页缺词条 {t['abbr']}"

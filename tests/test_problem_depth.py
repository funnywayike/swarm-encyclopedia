# -*- coding: utf-8 -*-
"""问题页的内容深度底线（2026-10 审计：多数问题页只有一段定义加三条文献）。

已经做过深度改写的页面（带 complexity / benchmarks / site_model 字段）必须达到：定义 ≥ 200 字、计算复杂度 ≥ 150 字、
基准 ≥ 100 字、本站建模 ≥ 100 字、出处 ≥ 5 条、没有内部措辞。还没改写的页面列在 PENDING 里——
改写完一批就从清单里删掉，清单与实际不符时测试失败，所以进度不会悄悄倒退。"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(HERE, "..", "data", "problems.json"), encoding="utf-8"))
PAGES = [t for sec in ("abstract_types", "knapsack_variants") for t in DATA[sec]]

PENDING = []

MIN_TEXT = {"model": 200, "complexity": 150, "benchmarks": 100, "site_model": 100}
INTERNAL = ("红线", "只登记", "不建页", "TODO", "素材锚点", "蓝图", "待建页")


def _plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def test_pending_list_matches_reality():
    thin = {t["id"] for t in PAGES if not t.get("complexity")}
    assert thin == set(PENDING), (
        f"还没改写的页面清单对不上：多出 {sorted(thin - set(PENDING))}（把它们加进 PENDING）；"
        f"已改写 {sorted(set(PENDING) - thin)}（从 PENDING 删掉）")


def test_every_rewritten_page_meets_the_depth_floor():
    for t in PAGES:
        if t["id"] in PENDING:
            continue
        for field, floor in MIN_TEXT.items():
            n = len(_plain(t.get(field)))
            assert n >= floor, f"{t['id']}.{field}：{n} 字，不足 {floor}"
        assert len(t["sources"]) >= 5 and len(t["sources"]) == len(set(t["sources"])), f"{t['id']}: 出处需要 ≥5 条且不重复"
        blob = json.dumps(t, ensure_ascii=False)
        for w in INTERNAL:
            assert w not in blob, f"{t['id']}: 含内部措辞 {w!r}"
        assert "note" not in t, f"{t['id']}: note 字段是页面不读的内部备注，应删除"


def test_html_in_rewritten_pages_is_balanced():
    for t in PAGES:
        if t["id"] in PENDING:
            continue
        for field in ("model", "diff", "algo", "complexity", "benchmarks", "site_model"):
            html = t.get(field) or ""
            for tag in ("p", "ul", "li", "b"):
                assert html.count(f"<{tag}>") + html.count(f"<{tag} ") == html.count(f"</{tag}>"), f"{t['id']}.{field}: <{tag}> 不配对"

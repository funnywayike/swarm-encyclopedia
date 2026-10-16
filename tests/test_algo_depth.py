# -*- coding: utf-8 -*-
"""算法页的内容深度底线（2026-10 审计）：每个算法页除了原理 / 参数 / 实测，还要有「来历、理论性质与已知批评、常见变体、延伸文献」。

底线：来历 ≥ 100 字、理论与批评 ≥ 150 字、变体 ≥ 1 条、延伸文献 ≥ 4 条且不重复；不含内部措辞；HTML 标签配对；页面上确实渲染出这一节。"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
ALGOS = json.load(open(os.path.join(ROOT, "data", "algos.json"), encoding="utf-8"))
INTERNAL = ("红线", "只登记", "不建页", "TODO", "素材锚点", "蓝图", "待建页")


def _plain(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html or "")).strip()


def test_every_algorithm_has_the_depth_fields():
    for a in ALGOS:
        k = a["key"]
        assert len(_plain(a.get("origin"))) >= 100, f"{k}.origin 太短"
        assert len(_plain(a.get("theory"))) >= 150, f"{k}.theory 太短"
        assert len(a.get("variants", [])) >= 1, f"{k}.variants 缺失"
        refs = a.get("refs", [])
        assert len(refs) >= 4 and len(refs) == len(set(refs)), f"{k}.refs 需要 ≥4 条且不重复"
        blob = json.dumps({f: a.get(f) for f in ("origin", "theory", "variants", "refs")}, ensure_ascii=False)
        for w in INTERNAL:
            assert w not in blob, f"{k}: 含内部措辞 {w!r}"


def test_html_in_depth_fields_is_balanced():
    for a in ALGOS:
        for field in ("origin", "theory"):
            html = a[field]
            for tag in ("p", "b"):
                assert html.count(f"<{tag}>") + html.count(f"<{tag} ") == html.count(f"</{tag}>"), f"{a['key']}.{field}: <{tag}> 不配对"
        for v in a["variants"]:
            assert v.count("<b>") == v.count("</b>"), f"{a['key']}: variants 里 <b> 不配对"


def test_no_bare_less_than_in_depth_fields():
    for a in ALGOS:
        for field in ("origin", "theory"):
            assert not re.search(r"<(?![/a-zA-Z!])", a[field]), f"{a['key']}.{field}: 裸 < 要写成 &lt;"
        for r in a["refs"] + a["variants"]:
            assert not re.search(r"<(?![/a-zA-Z!])", r), f"{a['key']}: 裸 <"


def test_the_section_is_rendered_on_every_algorithm_page():
    import glob
    pages = [p for p in glob.glob(os.path.join(ROOT, "algo", "*", "*", "index.html"))
             if "来历、理论与批评" in open(p, encoding="utf-8").read()]
    assert len(pages) == len(ALGOS), f"{len(pages)} 个页面渲染了「来历、理论与批评」，应有 {len(ALGOS)} 个"

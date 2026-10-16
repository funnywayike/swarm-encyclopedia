# -*- coding: utf-8 -*-
"""P2 元层佐证挂接对账：meta.json refs 的 schema、双向引用与渲染一致性。"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
META = json.load(open(os.path.join(ROOT, "data", "meta.json"), encoding="utf-8"))


def _pages():
    # The research map uses graph references and is verified in test_research_map.py.
    return [p for p in META["pages"] if p["id"] != "research-map"]


def test_every_meta_page_has_refs():
    for p in _pages():
        assert p.get("refs"), f"{p['id']} 缺 refs"
        assert len(p["refs"]) >= 5, f"{p['id']} 佐证条数过少"


def test_ref_schema():
    for p in _pages():
        ids = []
        for r in p["refs"]:
            assert re.fullmatch(r"[a-z0-9-]+", r["id"]), f"ref id 非法 {r['id']}"
            assert r.get("cite") and "<a " not in r["cite"], f"{p['id']}/{r['id']} cite 非法"
            if r.get("url"):
                assert r["url"].startswith(("http://", "https://")), f"{r['id']} url 非法"
            ids.append(r["id"])
        assert len(ids) == len(set(ids)), f"{p['id']} refs id 重复"


def test_section_refs_resolve_and_no_orphans():
    for p in _pages():
        ids = {r["id"] for r in p["refs"]}
        used = {i for s in p["sections"] for i in s.get("refs", [])}
        assert used <= ids, f"{p['id']} 节引用了未声明的 ref"
        assert used == ids, f"{p['id']} 存在未被引用的孤儿 ref: {ids - used}"


def test_rendered_html_matches_data():
    for p in _pages():
        f = os.path.join(ROOT, "meta", p["dir"], "index.html")
        assert os.path.isfile(f), f"{p['dir']} 页未生成"
        html = open(f, encoding="utf-8").read()
        used = [i for s in p["sections"] for i in s.get("refs", [])]
        n_sec_with = sum(1 for s in p["sections"] if s.get("refs"))
        assert html.count('class="refsup"') == n_sec_with
        assert len(re.findall(r'href="#ref-', html)) == len(used)
        assert html.count('id="ref-') == len(p["refs"])
        for r in p["refs"]:
            assert f'id="ref-{r["id"]}"' in html, f"{p['id']} 页尾缺 {r['id']}"


def test_old_sources_field_migrated():
    """sources 已并入 refs（单一渲染路径），不应再残留。"""
    for p in _pages():
        assert "sources" not in p, f"{p['id']} 仍保留旧 sources 字段"

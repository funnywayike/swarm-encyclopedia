# -*- coding: utf-8 -*-
"""P3 归约有向图对账：mapping.json graph.pos 与 reductions 派生的图一致。"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MP = json.load(open(os.path.join(ROOT, "data", "mapping.json"), encoding="utf-8"))
POS = MP["graph"]["pos"]
VW, VH = MP["graph"]["view"]


def test_pos_nodes_are_in_problem_index():
    """图里的节点必须在问题索引里；索引里还可以有只靠算法映射行出现、不在归约图里的页面。"""
    assert set(POS) <= set(MP["problem_index"])


def test_pos_in_viewbox():
    for pid, (x, y) in POS.items():
        assert 0 <= x <= VW and 0 <= y <= VH, f"{pid} 坐标出界"


def test_no_duplicate_positions():
    coords = [tuple(v) for v in POS.values()]
    assert len(coords) == len(set(coords)), "节点坐标重叠"


def test_every_reduction_endpoint_has_pos():
    for r in MP["reductions"]:
        assert r["from"] in POS and r["to"] in POS


def test_rendered_svg_matches_data():
    f = os.path.join(ROOT, "problem", "reductions", "index.html")
    html = open(f, encoding="utf-8").read()
    participating = {r["from"] for r in MP["reductions"]} | {r["to"] for r in MP["reductions"]}
    assert html.count('class="rededge"') == len(MP["reductions"])
    assert html.count('class="rednode"') == len(participating)
    assert "未入图" in html
    # 每条边类型都有箭头 marker 且四色图例齐全
    for slug in ("red", "eq", "case", "gen"):
        assert f"arr-{slug}" in html, f"缺 {slug} marker"
    for t in ("归约", "等价", "特例", "推广"):
        assert t in html

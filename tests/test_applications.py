# -*- coding: utf-8 -*-
"""应用地图对账测试：96 条应用均有合法抽象类型归属（词条 id 或 11 个属级兜底）。

对应 HANDOFF 验收链：pytest 全绿是交付前提之一。F 期范围见 docs/design-problem-axis-expansion.md。
"""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS = json.load(open(os.path.join(ROOT, "data", "apps.json"), encoding="utf-8"))
PROBLEMS = json.load(open(os.path.join(ROOT, "data", "problems.json"), encoding="utf-8"))

LEGAL = ({t["id"] for t in PROBLEMS["abstract_types"]}
         | {t["group"] for t in PROBLEMS["abstract_types"]})
GROUPS = {t["group"] for t in PROBLEMS["abstract_types"]}


def test_applications_abstract_type_schema():
    for e in APPS["entries"]:
        assert e.get("abstract_type"), f"{e['title']} 缺 abstract_type"
        assert e["abstract_type"] in LEGAL, \
            f"{e['title']} → 非法抽象类型 {e['abstract_type']}"


def test_applications_abstract_type_group_ratio():
    grp = sum(1 for e in APPS["entries"] if e["abstract_type"] in GROUPS)
    # 连续/多目标域允许属级兜底，但词条级必须占多数（≥ 1/4 词条级）
    assert grp * 4 < 3 * len(APPS["entries"]), f"属级兜底过多：{grp}/{len(APPS['entries'])}"

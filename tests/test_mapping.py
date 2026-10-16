# -*- coding: utf-8 -*-
"""P1 映射层对账测试：data/mapping.json 的 schema、引用完整性、双向派生一致性。

对应 HANDOFF 验收链：pytest 全绿是交付前提之一。
"""
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPPING = json.load(open(os.path.join(ROOT, "data", "mapping.json"), encoding="utf-8"))
ALGOS = json.load(open(os.path.join(ROOT, "data", "algos.json"), encoding="utf-8"))
ALGO_KEYS = {a["key"] for a in ALGOS}
PIDX = MAPPING["problem_index"]
SOLVES = MAPPING["algo_solves"]
REDS = MAPPING["reductions"]
TIERS = {"实测", "文献", "推测"}
TYPES = {"归约", "等价", "特例", "推广"}


def _page_exists(url: str) -> bool:
    return os.path.isfile(os.path.join(ROOT, url.lstrip("/").rstrip("/"), "index.html"))


def test_problem_index_schema_and_urls():
    assert len(PIDX) >= 16
    for pid, p in PIDX.items():
        assert p.get("name") and p.get("url"), f"{pid} 缺 name/url"
        assert _page_exists(p["url"]), f"{pid} url 无页面 {p['url']}"


def test_algo_solves_schema_and_references():
    assert len(SOLVES) >= 30
    for s in SOLVES:
        assert s["algo"] in ALGO_KEYS, f"未知算法 {s['algo']}"
        assert s["problem"] in PIDX, f"未知问题 {s['problem']}"
        assert s["tier"] in TIERS, f"tier 非法 {s['tier']}"
        assert s.get("how"), f"{s['algo']}→{s['problem']} 缺 how"
        if s["tier"] == "实测":
            assert s.get("evidence") and s.get("demo"), "实测级必须有 evidence+demo"
            assert _page_exists(s["demo"]), f"demo 无页面 {s['demo']}"
        if s["tier"] == "文献":
            assert s.get("src"), "文献级必须有 src"


def test_no_duplicate_algo_problem_pairs():
    pairs = [(s["algo"], s["problem"]) for s in SOLVES]
    assert len(pairs) == len(set(pairs)), "algo_solves 存在重复 (algo, problem)"


def test_tier_consistency_no_speculation():
    """诚实性：当前数据集只允许 实测/文献，不允许无出处的推测级。"""
    for s in SOLVES:
        if s["tier"] == "推测":
            pytest.fail("出现推测级映射——需要补 src 或降级")


def test_reductions_schema_and_references():
    assert len(REDS) >= 8
    for r in REDS:
        assert r["from"] in PIDX and r["to"] in PIDX, f"归约端点未注册 {r}"
        assert r["type"] in TYPES, f"归约类型非法 {r['type']}"
        assert r.get("note") and r.get("src"), f"归约缺 note/src {r}"


def test_reductions_page_generated_with_groups():
    f = os.path.join(ROOT, "problem", "reductions", "index.html")
    assert os.path.isfile(f)
    html = open(f, encoding="utf-8").read()
    used = {r["type"] for r in REDS}
    for t in used:
        assert t in html, f"归约页缺「{t}」分组"


def test_derived_solved_by_is_inverse():
    """双向派生一致性：按 problem 聚合 algo_solves == 逐条登记的逆。"""
    from collections import defaultdict
    by_algo = defaultdict(set)
    for s in SOLVES:
        by_algo[s["algo"]].add(s["problem"])
    by_prob = defaultdict(set)
    for algo, probs in by_algo.items():
        for p in probs:
            by_prob[p].add(algo)
    for p, algos in by_prob.items():
        for algo in algos:
            assert p in by_algo[algo]
    # 背包域实测级至少覆盖 8 个算法（与 py/domains.py 注册表对账的基线）
    assert len(by_algo.get("ga", set()) & {"knapsack"}) == 1


def test_flagship_use_when_avoid_when():
    """旗舰 12 页必须有「用/别用」卡的原料字段，其余算法不强制（不编造）。"""
    flagship = ["ga", "pso", "aco", "sa", "ts", "de", "gwo", "woa", "abc", "lk", "ils", "vns"]
    have = {a["key"] for a in ALGOS if a.get("use_when") and a.get("avoid_when")}
    assert set(flagship) <= have, f"旗舰缺 use_when/avoid_when: {set(flagship) - have}"

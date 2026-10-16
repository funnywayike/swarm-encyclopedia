# -*- coding: utf-8 -*-
"""文献红线的离线闸门：不联网，只检查「引用有没有变过而没重新核对」「核对报告里有没有错误」。

流程：改了任何引用 → 运行 `python tools/check_citations.py`（联网，约几分钟）→ 报告更新 → 本测试才会通过。"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))

import check_citations as C  # noqa: E402


def _report():
    with open(os.path.join(ROOT, "docs", "citation-report.md"), encoding="utf-8") as f:
        return f.read()


def test_citations_have_been_verified_since_they_last_changed():
    m = re.search(r"citations-sha256: ([0-9a-f]{64})", _report())
    assert m, "docs/citation-report.md 缺少指纹——运行 python tools/check_citations.py"
    assert m.group(1) == C.fingerprint(), (
        "有引用被新增/修改/删除，或 data/citation_overrides.json 变了，但还没重新核对："
        "请运行 python tools/check_citations.py 并处理其中的 MISMATCH")


def test_verification_report_has_no_mismatch_and_most_citations_are_verified():
    rep = _report()
    m = re.search(r"共 (\d+) 条——(.*?)。", rep)
    assert m, "报告格式不对"
    tally = {k: int(v) for k, v in re.findall(r"([A-Z]+) (\d+)", m.group(2))}
    assert tally.get("MISMATCH", 0) == 0, f"还有 {tally['MISMATCH']} 条引用与 Crossref 记录不符（见 docs/citation-report.md）"
    verified = tally.get("OK", 0) + tally.get("VERIFIED", 0)
    assert verified / int(m.group(1)) >= 0.55, f"已核实比例过低：{verified}/{m.group(1)}"


def test_manual_overrides_state_a_reason_and_a_link():
    with open(os.path.join(ROOT, "data", "citation_overrides.json"), encoding="utf-8") as f:
        ov = json.load(f)
    assert ov
    for k, v in ov.items():
        assert len(v.get("reason", "")) >= 15 and v.get("url", "").startswith("http"), f"{k}：人工核实必须写明理由与可访问链接"
        src, _, where = k.partition(":")
        assert src.endswith(".json") and where, k


def test_known_wrong_citations_stay_fixed():
    """回归：2026-10 清扫时确认过的错误引用不得再出现。"""
    algos = {a["key"]: a["paper"] for a in json.load(open(os.path.join(ROOT, "data", "algos.json"), encoding="utf-8"))}
    assert "111, 300-323" in algos["sma"] and "102, 786" not in algos["sma"]
    assert "191, 105190" in algos["eo"]
    assert "Neural Computing and Applications" in algos["da"]
    assert "120-133" in algos["sca"]
    assert "Gandomi" in algos["salp"] and "Aljarah" not in algos["salp"]
    assert "Gandomi" in algos["mpa"] and "Stephens" not in algos["mpa"]
    blob = " ".join(open(os.path.join(ROOT, "data", fn), encoding="utf-8").read() for fn in ("discovery.json", "families.json", "meta.json"))
    assert "22:649" not in blob  # Sörensen 2015 的正确出处是 ITOR 22(1):3–18

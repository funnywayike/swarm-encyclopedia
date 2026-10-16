# -*- coding: utf-8 -*-
"""保真度：每个问题变体都声明了「标准 / 教学简化 / 示意」，页面、上传校验、命令行都如实告知。"""
import collections
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "py"))
sys.path.insert(0, ROOT)

import domains as D  # noqa: E402
import entryseq as E  # noqa: E402
import registry as REG  # noqa: E402
import validate as V  # noqa: E402
import swarm  # noqa: E402


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def test_every_entryseq_variant_declares_fidelity_with_a_note_when_not_standard():
    assert set(E.FIDELITY) == set(E.VARIANTS) == set(E._OBJS)
    for v, f in E.FIDELITY.items():
        assert f["level"] in E.FIDELITY_LEVELS, v
        if f["level"] != "standard":
            assert len(f["note"]) >= 10, f"{v}：非标准模型必须说明与标准定义的差异"


def test_fidelity_distribution_is_reported_honestly():
    c = collections.Counter(f["level"] for f in E.FIDELITY.values())
    assert sum(c.values()) == len(E.VARIANTS)
    # 2026-10 审计时标准模型只占少数；之后逐个重做（真·多车 VRP、车间调度、选址……）。分布会继续变，
    # 但「示意模型」不能悄悄冒充别的：它们必须是少数、而且每一个都带着一句说明
    assert c["illustrative"] < c["standard"]


def test_registry_fidelity_covers_every_domain_and_variant():
    for dom, var in REG.cases(include_scheduling=True):
        f = REG.fidelity(dom, var)
        assert f["level"] in E.FIDELITY_LEVELS or (dom == "custom" and f["level"] == "custom")
    assert REG.fidelity("knapsack")["level"] == "standard"
    assert REG.fidelity("entryseq", "fss")["level"] == "standard"  # 2026-10：置换流水车间，Taillard ta001
    assert REG.fidelity("entryseq", "fjsp")["level"] == "simplified"
    assert REG.fidelity("entryseq", "vrp")["level"] == "standard"  # 2026-10：已升级为真·多车 CVRP
    assert REG.fidelity("entryseq", "mmo")["level"] == "illustrative"


def test_every_problem_page_shows_the_badge_that_matches_the_registry():
    checked = 0
    for f in glob.glob(os.path.join(ROOT, "problem", "**", "index.html"), recursive=True):
        t = open(f, encoding="utf-8").read()
        m = re.search(r'window\.PAGE_DOMAIN = "([^"]+)"', t)
        pm = re.search(r'window\.PAGE_PRESETS = (\{.*?\});\n', t)
        if not m or not pm:
            continue
        opts = next(iter(json.loads(pm.group(1)).values()), {}) or {}
        want = REG.fidelity(m.group(1), opts.get("variant"))["level"]
        got = re.search(r'class="fidelity fid-(\w+)"', t)
        assert got and got.group(1) == want, f"{os.path.relpath(f, ROOT)}：页面徽标 {got and got.group(1)}，登记为 {want}"
        checked += 1
    assert checked >= 80


def test_validator_warns_for_non_standard_models_but_not_for_standard_ones():
    fjsp = json.loads(D.domain_preset("entryseq", 7, {"variant": "fjsp"}))
    res = V.validate("entryseq", fjsp, variant="fjsp")
    assert res["ok"] and any("教学简化模型" in w["msg"] for w in res["warnings"])
    org = json.loads(D.domain_preset("entryseq", 7, {"variant": "mmo"}))
    assert any("示意模型" in w["msg"] for w in V.validate("entryseq", org, variant="mmo")["warnings"])
    qap = json.loads(D.domain_preset("entryseq", 7, {"variant": "qap"}))
    assert not any("模型" in w["msg"] for w in V.validate("entryseq", qap, variant="qap")["warnings"])
    ks = json.loads(D.domain_preset("knapsack", 7, {}))
    assert not any("教学简化" in w["msg"] for w in V.validate("knapsack", ks)["warnings"])


def test_cli_shows_fidelity(capsys, tmp_path):
    f = tmp_path / "fjsp.json"
    f.write_text(open(os.path.join(ROOT, "samples", "entryseq", "fjsp.json"), encoding="utf-8").read(), encoding="utf-8")
    try:
        swarm.main(["check", str(f)])
    except SystemExit:
        pass
    out = capsys.readouterr().out
    assert "保真度：教学简化模型" in out and "机器不是搜索出来的" in out


def test_encyclopedia_has_no_stale_planned_rows_and_counts_match_the_engine():
    enc = _read("encyclopedia/index.html")
    assert "⏳ 规划中" not in enc and "<td>⏳</td>" not in enc
    counts = {"knapsack": len(D._KS_ALGOS), "graphcolor": len(D._GC_ALGOS), "binpack": len(D._BP_ALGOS),
              "continuous": len(D._CN_ALGOS), "multiobj": len(D._MO_ALGOS)}
    for dom, n in counts.items():
        row = re.search(rf"<tr><td>[^<]*</td>(?:<td>[^<]*</td>)*?<td>{n}</td><td>标准</td>", enc)
        assert row, f"覆盖矩阵里找不到 {dom} 的算法数 {n}（数字应来自引擎注册表）"
    assert "v1.5" not in enc


def test_variants_doc_lists_fidelity():
    doc = _read("docs/data-formats-variants.md")
    assert "| 变体 | 保真度 | 字段（形状） |" in doc and "教学简化模型" in doc and "示意模型" in doc

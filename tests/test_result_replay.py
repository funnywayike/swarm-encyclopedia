# -*- coding: utf-8 -*-
"""结果文件 swarm-result/v1：命令行导出的文件必须能被 replay 复现；篡改过的必须被发现；
网页导出的形态（曲线四舍五入、中途停止）也要能核对；结果文件还要能当「问题文件」重新导入。"""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "py"))

import swarm  # noqa: E402
import validate as V  # noqa: E402

SAMPLES = os.path.join(ROOT, "samples")

# (样例文件, 额外参数, 算法)——覆盖 TSP / 普通域 / 变体域 / 词条域 / 多目标 / 连续
CASES = [
    ("cities_sample.json", ["--domain", "tsp"], "ga"),
    ("knapsack/knapsack.json", [], "sa"),
    ("kpvar/ssp.json", [], "ga"),
    ("graphcolor/graphcolor.json", [], "sa"),
    ("entryseq/blo.json", [], "sa"),
    ("multiobj/moco.json", [], "nsga2"),
    ("continuous/continuous.json", [], "pso"),
]


def run(capsys, *argv):
    code = 0
    try:
        swarm.main(list(argv))
    except SystemExit as e:
        code = e.code or 0
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def _solve(capsys, tmp_path, sample, extra, algo, iters="25"):
    out = tmp_path / "r.json"
    code, _, err = run(capsys, "solve", os.path.join(SAMPLES, sample), *extra, "--algo", algo,
                       "--iters", iters, "--seed", "5", "--out", str(out))
    assert code == 0, err
    return out, json.loads(out.read_text(encoding="utf-8"))


@pytest.mark.parametrize("sample,extra,algo", CASES)
def test_cli_result_replays(capsys, tmp_path, sample, extra, algo):
    out, res = _solve(capsys, tmp_path, sample, extra, algo)
    assert res["schema"] == "swarm-result/v1" and res["generator"] == "cli"
    assert res["problem"] and res["completed_iters"] == res["iters"] == 25
    code, text, err = run(capsys, "replay", str(out))
    assert code == 0 and "复现成功" in text, text + err


def test_tampered_result_is_detected(capsys, tmp_path):
    out, res = _solve(capsys, tmp_path, "knapsack/knapsack.json", [], "sa")
    res["curve"][-1][1] = res["curve"][-1][1] + 7
    out.write_text(json.dumps(res), encoding="utf-8")
    code, text, _ = run(capsys, "replay", str(out))
    assert code == 1 and "没能复现" in text
    res2 = json.loads(out.read_text(encoding="utf-8"))
    res2["seed"] = 6  # 换了种子，曲线必然对不上
    res2["curve"] = [[i, b] for i, b in res["curve"]]
    out.write_text(json.dumps(res2), encoding="utf-8")
    assert run(capsys, "replay", str(out))[0] == 1


def test_replay_accepts_web_shaped_results(capsys, tmp_path):
    """网页导出：曲线值四舍五入到 3 位、可能在中途被停止（completed_iters < iters）。"""
    out, res = _solve(capsys, tmp_path, "cities_sample.json", ["--domain", "tsp"], "sa", iters="60")
    res["generator"] = "web"
    res["curve"] = [[i, round(b, 3)] for i, b in res["curve"][:20]]
    res["completed_iters"] = 20
    out.write_text(json.dumps(res), encoding="utf-8")
    code, text, err = run(capsys, "replay", str(out))
    assert code == 0 and "第 20 代被停止" in text, text + err


def test_replay_rejects_foreign_files(capsys, tmp_path):
    f = tmp_path / "x.json"
    f.write_text(json.dumps({"hello": 1}), encoding="utf-8")
    code, _, err = run(capsys, "replay", str(f))
    assert code == 2 and "swarm-result/v1" in err
    f.write_text(json.dumps({"schema": "swarm-result/v1", "domain": "tsp"}), encoding="utf-8")
    code, _, err = run(capsys, "replay", str(f))
    assert code == 2 and "缺少字段" in err


def test_tsp_result_with_tsplib_distances_replays(capsys, tmp_path):
    tsp = tmp_path / "d.tsp"
    tsp.write_text("TYPE : TSP\nDIMENSION : 6\nEDGE_WEIGHT_TYPE : ATT\nNODE_COORD_SECTION\n"
                   "1 10 20\n2 90 25\n3 55 80\n4 15 70\n5 70 60\n6 40 40\nEOF\n", encoding="utf-8")
    out, res = _solve(capsys, tmp_path, str(tsp), [], "ga")
    assert res["problem"]["metric"] == "ATT"
    assert all(float(b).is_integer() for _, b in res["curve"])  # TSPLIB 距离是整数
    assert run(capsys, "replay", str(out))[0] == 0


def test_result_file_can_be_imported_as_a_problem(capsys, tmp_path):
    for sample, extra, algo in CASES[:5]:
        _, res = _solve(capsys, tmp_path, sample, extra, algo, iters="3")
        r = V.check_text(json.dumps(res), domain=res["domain"], dry_run=False)
        assert r["ok"], (sample, r["errors"])
        assert r["domain"] == res["domain"]
    r = V.check_text(json.dumps(res), domain="knapsack")  # 域不符
    assert not r["ok"]

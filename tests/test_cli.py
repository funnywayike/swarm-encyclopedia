# -*- coding: utf-8 -*-
"""命令行入口（swarm.py）测试：用法、退出码、结果文件。"""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)

import swarm  # noqa: E402

SAMPLES = os.path.join(ROOT, "samples")


def run(capsys, *argv):
    """返回 (退出码, stdout, stderr)。"""
    code = 0
    try:
        swarm.main(list(argv))
    except SystemExit as e:
        code = e.code or 0
    cap = capsys.readouterr()
    return code, cap.out, cap.err


def test_list_domains_and_algorithms(capsys):
    code, out, _ = run(capsys, "list")
    assert code == 0 and "knapsack" in out and "entryseq" in out and "tsp" in out
    code, out, _ = run(capsys, "list", "knapsack")
    assert code == 0 and "ga" in out and "默认参数" in out
    code, out, err = run(capsys, "list", "nosuchdomain")
    assert code == 2 and "未知问题域" in err


def test_solve_writes_result_and_curve(capsys, tmp_path):
    res, curve = tmp_path / "r.json", tmp_path / "c.csv"
    code, out, _ = run(capsys, "solve", os.path.join(SAMPLES, "knapsack", "knapsack.json"),
                       "--algo", "ga", "--iters", "30", "--out", str(res), "--curve", str(curve))
    assert code == 0 and "最优值" in out
    r = json.loads(res.read_text(encoding="utf-8"))
    assert r["schema"] == "swarm-result/v1" and r["domain"] == "knapsack" and r["sense"] == "max"
    assert r["iters"] == 30 and len(r["curve"]) == 30 and r["best"] >= 0
    lines = curve.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "iter,best" and len(lines) == 31


def test_solve_is_deterministic_for_same_seed(capsys):
    f = os.path.join(SAMPLES, "graphcolor", "graphcolor.json")
    a = run(capsys, "solve", f, "--algo", "sa", "--iters", "40", "--seed", "3")[1]
    b = run(capsys, "solve", f, "--algo", "sa", "--iters", "40", "--seed", "3")[1]
    strip = lambda s: [ln for ln in s.splitlines() if "耗时" not in ln]  # noqa: E731
    assert strip(a) == strip(b)


@pytest.mark.parametrize("path,extra,algo", [
    ("sat/sat.cnf", [], "sa"),
    ("graphcolor/graphcolor.col", [], "sa"),
    ("knapsack/knapsack.csv", ["--domain", "knapsack"], "hc"),
    ("qubo/qubo.csv", ["--domain", "qubo"], "sa"),
    ("cities_sample.json", [], "pso"),
    ("entryseq/vrp.json", [], "sa"),
    ("kpvar/ssp.json", [], "sa"),
    ("continuous/continuous.json", [], "pso"),
])
def test_solve_every_input_format(capsys, path, extra, algo):
    code, out, err = run(capsys, "solve", os.path.join(SAMPLES, path), *extra, "--algo", algo, "--iters", "20")
    assert code == 0, err
    assert "最优值" in out


def test_bad_inputs_exit_with_friendly_message(capsys, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "swarm-problem/v1", "domain": "knapsack",
                               "data": {"cap": 10, "items": [[-3, 4]]}}), encoding="utf-8")
    code, _, err = run(capsys, "solve", str(bad), "--algo", "ga")
    assert code == 2 and "items[0][0]" in err and "Traceback" not in err
    code, _, err = run(capsys, "solve", str(tmp_path / "missing.json"), "--algo", "ga")
    assert code == 2 and "打不开" in err
    good = os.path.join(SAMPLES, "entryseq", "vrp.json")
    code, _, err = run(capsys, "solve", good, "--algo", "bv_pso")  # 与该变体编码不匹配的算法（vrp 是排列编码）
    assert code == 2 and "没有算法" in err
    code, _, err = run(capsys, "solve", good, "--algo", "sa", "--param", "bogus=1")
    assert code == 2 and "未知参数" in err
    code, _, err = run(capsys, "solve", os.path.join(SAMPLES, "knapsack", "knapsack.csv"), "--algo", "ga")
    assert code == 2 and "domain" in err  # CSV 没有域信息


def test_warnings_do_not_block(capsys, tmp_path):
    f = tmp_path / "w.json"
    f.write_text(json.dumps({"schema": "swarm-problem/v1", "domain": "knapsack",
                             "data": {"n": 99, "cap": 1000, "items": [[3, 4], [4, 5]]}}), encoding="utf-8")
    code, out, err = run(capsys, "solve", str(f), "--algo", "ga", "--iters", "5")
    assert code == 0 and "已忽略 n=99" in err and "最优值" in out


def test_compare_ranks_in_the_right_direction(capsys, tmp_path):
    big = tmp_path / "ks.json"
    big.write_text(run(capsys, "generate", "knapsack", "--opt", "n=60")[1], encoding="utf-8")
    code, out, _ = run(capsys, "compare", str(big), "--algos", "random,sa,ga", "--iters", "60")
    assert code == 0 and "越大越好" in out
    vals = [float(ln.split()[2]) for ln in out.splitlines() if ln.strip()[:1].isdigit()]
    assert vals == sorted(vals, reverse=True) and len(vals) == 3
    mo = tmp_path / "mo.json"
    mo.write_text(run(capsys, "generate", "multiobj", "--opt", "n=40")[1], encoding="utf-8")
    code, out, _ = run(capsys, "compare", str(mo), "--algos", "random,nsga2", "--iters", "40")
    assert code == 0
    ranks = [ln.split()[1] for ln in out.splitlines() if ln.strip()[:1].isdigit()]
    assert ranks[0] == "nsga2"  # 前沿解个数：NSGA-II 必须胜过随机


@pytest.mark.parametrize("domain,opts", [
    ("knapsack", ["n=80"]), ("tsp", ["n=25"]), ("sat", ["n_vars=20"]), ("setcover", ["n_el=30", "m=20"]),
    ("gap", ["n_a=3", "n_j=12"]), ("graphcolor", ["n=30"]), ("continuous", ["fn=ackley", "dim=4"]),
])
def test_generate_output_passes_check(capsys, tmp_path, domain, opts):
    args = ["generate", domain]
    for o in opts:
        args += ["--opt", o]
    code, out, _ = run(capsys, *args)
    assert code == 0
    f = tmp_path / "g.json"
    f.write_text(out, encoding="utf-8")
    code, out, err = run(capsys, "check", str(f))
    assert code == 0, err


def test_generate_variant_and_template(capsys, tmp_path):
    code, out, _ = run(capsys, "generate", "entryseq", "--variant", "qap")
    assert code == 0 and json.loads(out)["variant"] == "qap"
    code, out, _ = run(capsys, "template", "kpvar", "--variant", "qkp")
    assert code == 0 and json.loads(out)["data"]["Q"]


def test_domain_flag_conflict_is_reported(capsys):
    code, _, err = run(capsys, "check", os.path.join(SAMPLES, "knapsack", "knapsack.json"), "--domain", "binpack")
    assert code == 2 and "binpack" in err

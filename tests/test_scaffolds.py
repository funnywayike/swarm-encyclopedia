# -*- coding: utf-8 -*-
"""tools/new_problem.py 与 tools/new_algorithm.py：在项目的副本上跑脚手架，核对生成的代码真的能被引擎装载、运行，
并且重复名字、非法名字、--dry-run 都按说明处理。"""
import json
import os
import shutil
import subprocess
import sys
import textwrap

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")


@pytest.fixture()
def copy(tmp_path):
    """只复制脚手架会碰的文件：引擎源码、数据、页面配置——不复制已构建的页面。"""
    dst = tmp_path / "proj"
    shutil.copytree(os.path.join(ROOT, "py"), dst / "py", ignore=shutil.ignore_patterns("__pycache__"))
    (dst / "data").mkdir()
    for f in ("problems.json", "problem_groups.json", "algos.json", "families.json", "mapping.json"):
        shutil.copy(os.path.join(ROOT, "data", f), dst / "data" / f)
    shutil.copy(os.path.join(ROOT, "pages_domains.py"), dst / "pages_domains.py")
    (dst / "tests").mkdir()
    return dst


def _tool(name, *args, root):
    return subprocess.run([sys.executable, os.path.join(ROOT, "tools", name), *args, "--root", str(root)],
                          capture_output=True, text=True, encoding="utf-8", env=ENV, timeout=120)


def _py(root, code):
    """在副本的 py/ 目录里（隔离模式）运行一段代码，返回标准输出。"""
    r = subprocess.run([sys.executable, "-I", "-c", textwrap.dedent(code)], capture_output=True, text=True, encoding="utf-8",
                       cwd=str(root / "py"), env=ENV, timeout=180)
    assert r.returncode == 0, r.stderr[-1500:]
    return r.stdout


@pytest.mark.parametrize("encoding,group", [("perm", "sequencing"), ("bits", "subset"), ("real", "continuous")])
def test_new_problem_scaffold_produces_a_working_registered_variant(copy, encoding, group):
    r = _tool("new_problem.py", "demox", "--encoding", encoding, "--title", "示例问题", "--group", group, root=copy)
    assert r.returncode == 0, r.stderr + r.stdout
    out = _py(copy, f"""
        import json, random, sys
        sys.path.insert(0, ".")
        import entryseq as E, domains as D, registry as REG, validate as V
        assert "demox" in E.VARIANTS and E.ENCODING["demox"] == "{encoding}"
        assert ("entryseq", "demox") in list(REG.cases())
        p = E.es_make("demox", 12, 7)
        assert V.validate("entryseq", p, variant="demox", dry_run=True)["ok"]
        ctx = E.es_ctx(p)
        rng = random.Random(1)
        v = ctx.obj(ctx.random(rng))
        assert v == v and abs(v) != float("inf")
        algos = [a["key"] for a in json.loads(D.domain_list("entryseq", {{"variant": "demox"}}))["algos"]]
        D.domain_start("entryseq", json.dumps(p), algos[0], json.dumps({{"max_iter": 4, "seed": 3}}))
        while D.domain_step() is not None:
            pass
        print("OK", len(algos))
    """)
    assert out.startswith("OK")
    # 页面条目与演示配置都写进去了，且都带占位标记（会被 test_no_placeholders 拦住）
    pj = json.loads((copy / "data" / "problems.json").read_text(encoding="utf-8"))
    entry = next(t for t in pj["abstract_types"] if t["id"] == "demox")
    assert entry["status"] == "page" and len(entry["sources"]) >= 3 and "TODO（占位）" in entry["model"]
    pd = (copy / "pages_domains.py").read_text(encoding="utf-8")
    assert 'ABSTRACT_DEMO["demox"]' in pd
    import ast
    ast.parse(pd)
    assert "TODO（占位）" in (copy / "tests" / "test_demox.py").read_text(encoding="utf-8")
    ast.parse((copy / "tests" / "test_demox.py").read_text(encoding="utf-8"))


def test_new_problem_scaffold_rejects_bad_and_duplicate_names_and_dry_run_writes_nothing(copy):
    before = {p: (copy / p).read_bytes() for p in ("py/entryseq.py", "data/problems.json", "pages_domains.py")}
    for bad in ("Bad", "x", "has-dash", "9abc"):
        assert _tool("new_problem.py", bad, "--encoding", "perm", "--title", "t", root=copy).returncode != 0
    assert _tool("new_problem.py", "vrp", "--encoding", "perm", "--title", "t", root=copy).returncode != 0, "已有的变体不能重名"
    assert _tool("new_problem.py", "tsp", "--encoding", "perm", "--title", "t", root=copy).returncode != 0, "已有的问题页不能重名"
    assert _tool("new_problem.py", "okname", "--encoding", "perm", "--title", "t", "--group", "nope", root=copy).returncode != 0
    r = _tool("new_problem.py", "okname", "--encoding", "perm", "--title", "t", "--dry-run", root=copy)
    assert r.returncode == 0 and "没有改任何文件" in r.stdout
    assert before == {p: (copy / p).read_bytes() for p in before}
    assert not (copy / "tests" / "test_okname.py").exists()


def test_new_algorithm_scaffold_produces_a_runnable_registered_solver(copy):
    r = _tool("new_algorithm.py", "demoalgo", "--title", "示例算法", "--family", "F2", root=copy)
    assert r.returncode == 0, r.stderr + r.stdout
    out = _py(copy, """
        import json, random, sys
        sys.path.insert(0, ".")
        import solvers as S
        assert "demoalgo" in [s["key"] for s in json.loads(S.list_solvers())]
        rng = random.Random(1)
        cities = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(14)]
        S.start(json.dumps(cities), "demoalgo", json.dumps({"max_iter": 30, "seed": 1}))
        last, costs = None, []
        while True:
            st = S.step()
            if st is None:
                break
            last = json.loads(st)
            costs.append(last["best_cost"] if "best_cost" in last else last["best"])
        assert all(b <= a + 1e-9 for a, b in zip(costs, costs[1:])) and len(costs) > 5
        print("OK")
    """)
    assert out.startswith("OK")
    algos = json.loads((copy / "data" / "algos.json").read_text(encoding="utf-8"))
    e = next(a for a in algos if a["key"] == "demoalgo")
    assert e["family"] == "F2" and e["slug"] == "demoalgo-tsp" and "TODO（占位）" in e["name"]
    mp = json.loads((copy / "data" / "mapping.json").read_text(encoding="utf-8"))
    row = next(r for r in mp["algo_solves"] if r["algo"] == "demoalgo")
    assert row["problem"] == "tsp" and row["tier"] == "实测" and row["demo"] == "/algo/f2-si/demoalgo/"
    t = (copy / "tests" / "test_algo_demoalgo.py")
    assert t.exists() and "TODO（占位）" in t.read_text(encoding="utf-8")
    # 用脚手架自带的测试骨架去测它自己：在副本里跑得通
    rr = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(t)], capture_output=True, text=True,
                        encoding="utf-8", cwd=str(copy), env=dict(ENV, PYTHONPATH=str(copy / "py")), timeout=180)
    assert rr.returncode == 0, rr.stdout[-1500:]


def test_new_algorithm_scaffold_rejects_duplicates_and_bad_input(copy):
    assert _tool("new_algorithm.py", "ga", "--title", "t", "--family", "F1", root=copy).returncode != 0, "已有算法不能重名"
    assert _tool("new_algorithm.py", "Bad", "--title", "t", "--family", "F1", root=copy).returncode != 0
    assert _tool("new_algorithm.py", "okalgo", "--title", "t", "--family", "F99", root=copy).returncode != 0
    before = (copy / "py" / "solvers.py").read_bytes()
    r = _tool("new_algorithm.py", "okalgo", "--title", "t", "--family", "F1", "--dry-run", root=copy)
    assert r.returncode == 0 and (copy / "py" / "solvers.py").read_bytes() == before

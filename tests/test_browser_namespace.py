# -*- coding: utf-8 -*-
"""浏览器里的引擎 = 把几个 .py 拼成一个源码串、在同一个名字空间里执行（js/domains_src.js 的 DOMAINS_SRC）。
这时 `from entryseq import …` 全部抛 ImportError 被跳过，**带别名的导入根本不会绑定**——
本地 pytest 一直是走正常 import，发现不了这类问题（STP 页就因此在浏览器里报 NameError）。

这里在一个干净的子进程里复现浏览器的做法：只执行拼接源码（看不到 py/ 目录），再把每个域 / 变体 / 一批算法都跑几代。"""
import json
import os
import re
import subprocess
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))

SCRIPT = textwrap.dedent(r'''
    import json, re, sys
    src_js = open(sys.argv[1], encoding="utf-8").read()
    m = re.search(r"export const DOMAINS_SRC = (.*?);\nexport const VALIDATE_SRC = (.*);\s*$", src_js, re.S)
    dom_src, val_src = json.loads(m.group(1)), json.loads(m.group(2))
    ns = sys.modules["__main__"].__dict__                      # Pyodide 的 runPythonAsync 就是在 __main__ 的字典里执行
    sys.platform = "emscripten"                                 # 源码里「本机自测」块靠这个判断跳过（Pyodide 里 platform 就是 emscripten）
    exec(compile(dom_src, "<domains_src>", "exec"), ns)          # 与 Pyodide 里 runPythonAsync(DOMAINS_SRC) 等价
    import types
    vm = types.ModuleType("validate"); exec(compile(val_src, "<validate_src>", "exec"), vm.__dict__)
    sys.modules["validate"] = vm
    out = {"errors": [], "combos": 0}
    domain_list, domain_preset, domain_start, domain_step = (ns[k] for k in ("domain_list", "domain_preset", "domain_start", "domain_step"))
    VARIANTS = json.loads(sys.argv[2])
    for dom, var in VARIANTS:
        opts = {"variant": var} if var else {}
        try:
            pre = domain_preset(dom, 7, opts)
            algos = [a["key"] for a in json.loads(domain_list(dom, opts))["algos"]]
        except Exception as e:
            out["errors"].append([dom, var, "preset/list", type(e).__name__ + ": " + str(e)[:120]]); continue
        for a in algos[:: max(1, len(algos) // 4)] + algos[-1:]:   # 每个域 / 变体取约 5 个算法（含首尾）
            try:
                domain_start(dom, pre, a, json.dumps({"max_iter": 3, "seed": 3}))
                while domain_step() is not None:
                    pass
                out["combos"] += 1
            except Exception as e:
                out["errors"].append([dom, var, a, type(e).__name__ + ": " + str(e)[:120]])
        try:
            r = vm.validate(dom, json.loads(pre), variant=var)
            if not r["ok"]:
                out["errors"].append([dom, var, "validate", str(r["errors"])[:120]])
        except Exception as e:
            out["errors"].append([dom, var, "validate", type(e).__name__ + ": " + str(e)[:120]])
    print("RESULT" + json.dumps(out, ensure_ascii=False))
''')


def test_the_concatenated_browser_source_runs_every_domain_and_variant():
    sys.path.insert(0, os.path.join(ROOT, "py"))
    import registry as REG
    cases = [list(c) for c in REG.cases(include_scheduling=False)]
    js = os.path.join(ROOT, "js", "domains_src.js")
    assert os.path.isfile(js), "先运行 python build_pages.py"
    # -I：隔离模式，不把当前目录 / py 目录放进 sys.path——这样才和浏览器一样「看不到」各个 .py 模块
    r = subprocess.run([sys.executable, "-I", "-c", SCRIPT, js, json.dumps(cases)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=os.path.expanduser("~"), timeout=900,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"))
    assert r.returncode == 0, r.stderr[-1500:]
    line = [ln for ln in r.stdout.splitlines() if ln.startswith("RESULT")][-1]
    res = json.loads(line[len("RESULT"):])
    assert res["combos"] > 300
    assert not res["errors"], "浏览器拼接环境里出错：\n" + "\n".join(map(str, res["errors"][:15]))


def test_no_two_concatenated_modules_define_the_same_top_level_name():
    """浏览器里这些文件拼成一个名字空间：后面的同名定义会悄悄覆盖前面的（entryseq 的 _graph_adj 曾覆盖 / 被 domains.py 的同名函数覆盖，
    结果是在浏览器里才出错）。拼接顺序见 build_pages.gen_domains_src。"""
    import ast
    parts = sorted(os.listdir(os.path.join(ROOT, "py", "domains_parts")))
    order = (["taxonomy.py", "domain_components.py", "entryseq.py", "userproblem.py", "mocont.py"]
             + ["domains_parts/" + p for p in parts if p.endswith(".py")] + ["scheduling.py"])
    seen = {}
    clashes = []
    # domains_parts/ 下的各块合起来才对应原来的一个 domains.py：块与块之间重新绑定注册表（_BIN_ALGOS = …）是原有做法，
    # 只查「域引擎」与其它模块之间的同名
    unit = lambda fn: "domains_parts" if fn.startswith("domains_parts/") else fn  # noqa: E731
    for fn in order:
        tree = ast.parse(open(os.path.join(ROOT, "py", fn), encoding="utf-8").read())
        names = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    names.update(n.id for n in ast.walk(t) if isinstance(n, ast.Name))
        for name in names:
            if name in seen and seen[name] != unit(fn):
                clashes.append(f"{name}：{seen[name]} 与 {fn}")
            seen[name] = unit(fn)
    assert not clashes, "拼接环境里同名顶层定义互相覆盖：\n" + "\n".join(sorted(clashes))


SOLVER_SCRIPT = textwrap.dedent(r'''
    import json, re, sys, types
    src_js = open(sys.argv[1], encoding="utf-8").read()
    m = re.search(r"export const SOLVERS_SRC = (.*?);\nexport const VALIDATE_SRC = (.*);\s*$", src_js, re.S)
    sol_src, val_src = json.loads(m.group(1)), json.loads(m.group(2))
    sys.platform = "emscripten"
    ns = sys.modules["__main__"].__dict__
    exec(compile(sol_src, "<solvers_src>", "exec"), ns)
    vm = types.ModuleType("validate"); exec(compile(val_src, "<validate_src>", "exec"), vm.__dict__); sys.modules["validate"] = vm
    errors, n = [], 0
    pts = [[0, 0], [10, 0], [10, 10], [0, 10], [5, 5], [3, 8], [8, 3]]
    insts = {"coords": pts, "tsplib-att": {"cities": pts, "metric": "ATT"}}
    for name, inst in insts.items():
        for s in json.loads(ns["list_solvers"]()):
            if not s["implemented"]:
                continue
            try:
                ns["start"](json.dumps(inst), s["key"], json.dumps({"max_iter": 4, "seed": 3}))
                while ns["step"]() is not None:
                    pass
                n += 1
            except Exception as e:
                errors.append([name, s["key"], type(e).__name__ + ": " + str(e)[:100]])
    r = vm.check_text("TYPE : TSP\nDIMENSION : 4\nEDGE_WEIGHT_TYPE : EUC_2D\nNODE_COORD_SECTION\n1 0 0\n2 9 0\n3 9 9\n4 0 9\nEOF\n", "tsp", "a.tsp", False, None)
    if not r["ok"]:
        errors.append(["validate", "tsplib", str(r["errors"])])
    print("RESULT" + json.dumps({"errors": errors, "combos": n}, ensure_ascii=False))
''')


def test_the_concatenated_tsp_solver_source_runs_in_the_browser_namespace():
    js = os.path.join(ROOT, "js", "solvers_src.js")
    r = subprocess.run([sys.executable, "-I", "-c", SOLVER_SCRIPT, js], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=os.path.expanduser("~"), timeout=600,
                       env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"))
    assert r.returncode == 0, r.stderr[-1500:]
    res = json.loads([ln for ln in r.stdout.splitlines() if ln.startswith("RESULT")][-1][len("RESULT"):])
    assert res["combos"] >= 80
    assert not res["errors"], "TSP 求解器在浏览器拼接环境里出错：\n" + "\n".join(map(str, res["errors"][:10]))

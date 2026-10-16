# -*- coding: utf-8 -*-
"""自带问题（py/userproblem.py）：表达式白名单必须拒绝一切不是「算术 + 白名单函数」的东西，
运行期加固要挡住内存 / 时间炸弹，试跑要在运行前就指出写错的目标函数。设计与安全边界见 docs/design-bring-your-own-problem.md。"""
import ast
import json
import os
import sys
import time

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "py"))
sys.path.insert(0, ROOT)

import domains as D  # noqa: E402
import swarm  # noqa: E402
import userproblem as U  # noqa: E402
import validate as V  # noqa: E402


def prob(objective, variant="bits", n=6, data=None, **kw):
    p = {"variant": variant, "n": n, "sense": "min", "data": data or {}, "objective": objective}
    if variant == "real":
        p.update(lo=-5, hi=5)
    p.update(kw)
    return p


def errs(p):
    out, e, w, _ = U.up_check(p)
    return out, e, w


# ---------------------------------------------------------------- 能算对
def test_expression_values_are_computed_correctly():
    cases = [
        ("sum(x[i] * 2 for i in range(n))", [1, 0, 1, 1, 0, 0], 6.0),
        ("a = sum(x)\nb = n - a\nobjective = a * b", [1, 1, 0, 0, 0, 0], 8.0),
        ("max(x) - min(x) + abs(-3)", [1, 0, 1, 1, 0, 0], 4.0),
        ("sum(w[i] * x[i] for i in range(n) if i % 2 == 0)", [1, 1, 1, 1, 1, 1], 9.0),
        ("sqrt(16) + floor(2.7) + ceil(2.1) + round(2.5)", [0] * 6, 11.0),
        ("1 if x[0] == 1 else 5", [1, 0, 0, 0, 0, 0], 1.0),
        ("sum(a * b for a, b in zip(x, w))", [1, 0, 1, 0, 0, 0], 4.0),
        ("data_scalar * 2 ** 3", [0] * 6, 24.0),
    ]
    for src, x, want in cases:
        f = U.UPObjective(prob(src, data={"w": [1, 2, 3, 4, 5, 6], "data_scalar": 3}))
        assert f(x) == pytest.approx(want), src


def test_builtin_examples_check_out_and_report_timing():
    for v in U.ENCODINGS:
        out, e, w, info = U.up_check(U.up_preset(v))
        assert out is not None and not e, (v, e)
        assert info["eval_ms"] >= 0


# ---------------------------------------------------------------- 必须拒绝
FORBIDDEN = [
    ("import os", "只允许"),
    ("__import__('os').system('echo hi')", "只能调用"),
    ("().__class__", "下划线|属性"),
    ("x.append(1)", "只能调用"),
    ("open('f')", "只能调用"),
    ("exec('1')", "只能调用"),
    ("eval('1')", "只能调用"),
    ("getattr(x, 'a')", "只能调用"),
    ("(lambda: 1)()", "只能调用"),
    ("'abc'", "字符串"),
    ("f'{n}'", "f 字符串"),
    ("{1: 2}", "字典"),
    ("{1, 2}", "集合"),
    ("[i for i in range(n) for j in range(n) for k in range(n)]", "两层"),
    ("sum(1 for i in range(n) if sum(1 for j in range(n) if sum(1 for k in range(n)) > 0) > 0)", "两层"),
    ("while True: pass", "只允许"),
    ("for i in range(3): pass", "只允许"),
    ("def f(): return 1", "只允许"),
    ("(y := 3) + y", "不支持|没有叫"),
    ("x[0] = 1\nobjective = 0", "只能是一个名字"),
    ("x = 3\nobjective = x", "占用"),
    ("n = 3\nobjective = n", "占用"),
    ("sum = 3\nobjective = sum", "占用"),
    ("_secret = 1\nobjective = _secret", "下划线"),
    ("objective = unknown_name + 1", "没有叫"),
    ("a = 1", "没有给出目标值"),
    ("print(x)", "只能调用"),
    ("sorted(x, key=abs)", "名字=值"),
    ("sum(*x)", "展开"),
    ("1 in x", "in / is"),
    ("x is None", "in / is"),
    ("sum(x for x in x)", "不可用"),   # 循环变量不能叫 x
    ("None", "只允许数字"),
]


@pytest.mark.parametrize("src,why", FORBIDDEN)
def test_forbidden_constructs_are_rejected(src, why):
    out, e, _ = errs(prob(src))
    assert out is None and e, f"{src!r} 应当被拒绝"
    import re
    assert re.search(why, e[0]["msg"]), (src, e[0]["msg"])


def test_data_names_cannot_shadow_builtins_or_be_private():
    for bad in ("x", "n", "sum", "_hidden", "objective", "9lives", "a-b"):
        out, e, _ = errs(prob("sum(x)", data={bad: [1, 2]}))
        assert out is None and e, bad
    out, e, _ = errs(prob("sum(x)", data={"ok_name": [1, 2]}))
    assert out is not None


def test_data_must_be_plain_numbers():
    for bad in ({"a": "text"}, {"a": [1, "2"]}, {"a": None}, {"a": []}, {"a": [[[[1]]]]}, {"a": [float("nan")]},
                {"a": True}, {"a": {"b": 1}}):
        out, e, _ = errs(prob("sum(x)", data=bad))
        assert out is None and e, bad


def test_size_and_shape_limits():
    assert errs(prob("sum(x)", n=U.UP_LIMITS["bits"] + 1))[0] is None
    assert errs(prob("sum(x)", n=1))[0] is None
    assert errs(prob("sum(x)", variant="perm", n=U.UP_LIMITS["perm"] + 1))[0] is None
    assert errs(prob("sum(x)", variant="real", n=U.UP_LIMITS["real"] + 1))[0] is None
    assert errs(prob("sum(x)", variant="real", lo=3, hi=3))[0] is None
    assert errs(prob("sum(x)", sense="biggest"))[0] is None
    assert errs(prob("x" * (U.UP_LIMITS["src_chars"] + 1)))[0] is None
    assert errs(prob("\n".join(f"a{i} = 1" for i in range(40)) + "\nobjective = a0"))[0] is None
    assert errs(prob("sum(x)", variant="matrix"))[0] is None
    assert errs("not a dict")[0] is None


# ---------------------------------------------------------------- 运行期加固：不能被炸弹拖死
def _runtime_error(src, x=None, **kw):
    f = U.UPObjective(prob(src, **kw))
    t0 = time.time()
    with pytest.raises(U._EvalError) as ei:
        f(x if x is not None else [1] * 6)
    return str(ei.value), time.time() - t0


@pytest.mark.parametrize("src", [
    "[0] * 1000000000",             # 序列重复 → 内存炸弹
    "2 ** 10 ** 9",                  # 巨大乘方
    "10.0 ** 400",                   # 浮点溢出
    "sum(1 for i in range(1000000) for j in range(1000000))",   # 两层 100 万 → 时间炸弹
    "sum(1 for i in range(10 ** 9))",                           # 巨大 range
    "1 / 0",
    "x[100]",
    "log(0)",
    "sqrt(-1)",
    "exp(10000)",
    "[1, 2]",                        # 目标值不是数字
])
def test_bombs_and_bad_values_become_clean_errors_quickly(src):
    msg, secs = _runtime_error(src)
    assert msg and secs < 10, (src, msg, secs)


def test_non_finite_objective_is_an_error():
    msg, _ = _runtime_error("1e308 * 10")
    assert "有限" in msg or "太大" in msg


def test_evaluation_never_changes_inputs():
    data = {"w": [1, 2, 3, 4, 5, 6]}
    f = U.UPObjective(prob("sum(w[i] * x[i] for i in range(n))", data=data))
    x = [1, 0, 1, 0, 1, 0]
    f(x)
    f(x)
    assert x == [1, 0, 1, 0, 1, 0] and data == {"w": [1, 2, 3, 4, 5, 6]}


def test_evaluations_are_independent():
    f = U.UPObjective(prob("a = a_data + 1\nobjective = a * sum(x)", data={"a_data": 1}))
    assert f([1, 0, 0, 0, 0, 0]) == f([1, 0, 0, 0, 0, 0]) == 2.0  # 上一次的赋值不会泄漏到下一次


# ---------------------------------------------------------------- 试跑
def test_dry_run_catches_common_mistakes():
    out, e, _ = errs(prob("5"))
    assert out is None and "一样" in e[0]["msg"]                       # 常数目标：无物可优化
    out, e, _ = errs(prob("x[50]"))
    assert out is None and "都出错" in e[0]["msg"]                    # 下标永远越界
    out, e, w = errs(prob("1 / (sum(x) - 3) + sum(x)"))               # 个别解触发除 0：只警告
    assert out is not None or e, "要么警告要么报错"
    out, e, w = errs(prob("sum(x) / (x[0] + 0)", n=6))
    assert out is not None and any("出错" in m["msg"] for m in w)     # 一半的随机解会除 0 → 警告而不是拒绝
    out, e, w = errs(prob("sum(x)", extra_key=1))
    assert out is not None and any(m["path"] == "extra_key" for m in w)


def test_slow_objective_is_flagged():
    out, e, w, info = U.up_check(prob("sum(x[i % n] for i in range(200000))"), dry_runs=4)
    assert out is not None and any("毫秒" in m["msg"] for m in w) and info["eval_ms"] > 5


# ---------------------------------------------------------------- 本地 Python 目标函数：默认关闭
def test_python_objective_is_off_by_default_and_in_the_browser_path():
    assert U.python_enabled() is False
    out, e, _ = errs(prob(None, objective_python="def objective(x, data):\n    return sum(x)\n"))
    assert out is None and "命令行" in e[0]["msg"]
    res = V.validate("custom", prob(None, objective_python="def objective(x, data):\n    return sum(x)\n"))
    assert not res["ok"]


def test_python_objective_works_when_enabled(monkeypatch):
    monkeypatch.setattr(U, "_PY_ENABLED", True)
    src = "def objective(x, data):\n    return sum(x) + data['b']\n"
    out, e, _ = errs(prob(None, data={"b": 2}, objective_python=src))
    assert out is not None and not e
    assert U.UPObjective(out)([1, 1, 0, 0, 0, 0]) == 4.0
    out, e, _ = errs(prob(None, objective_python="x = 1"))
    assert out is None and "objective" in e[0]["msg"]


# ---------------------------------------------------------------- 端到端
def run(capsys, *argv):
    code = 0
    try:
        swarm.main(list(argv))
    except SystemExit as ex:
        code = ex.code or 0
    cap = capsys.readouterr()
    return code, cap.out, cap.err


@pytest.mark.parametrize("variant,algo", [("bits", "ga"), ("perm", "pk_pso"), ("real", "pso")])
def test_solve_custom_from_the_shipped_samples_and_replay(capsys, tmp_path, variant, algo):
    f = os.path.join(ROOT, "samples", "custom", f"{variant}.json")
    out = tmp_path / "r.json"
    code, text, err = run(capsys, "solve", f, "--algo", algo, "--iters", "20", "--out", str(out))
    assert code == 0, err
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["domain"] == "custom" and res["variant"] == variant
    assert res["problem"]["objective"] and res["sense"] in ("min", "max")
    code, text, err = run(capsys, "replay", str(out))
    assert code == 0 and "复现成功" in text, text + err


def test_objective_py_via_cli_and_replay_requires_consent(capsys, tmp_path):
    data = tmp_path / "p.json"
    data.write_text(json.dumps({"variant": "bits", "n": 8, "sense": "max", "data": {"v": [3, 1, 4, 1, 5, 9, 2, 6]}}),
                    encoding="utf-8")
    py = tmp_path / "obj.py"
    py.write_text("def objective(x, data):\n    return sum(data['v'][i] * x[i] for i in range(len(x)))\n", encoding="utf-8")
    out = tmp_path / "r.json"
    try:
        code, text, err = run(capsys, "solve", str(data), "--domain", "custom", "--variant", "bits",
                              "--objective-py", str(py), "--algo", "ga", "--iters", "15", "--out", str(out))
        assert code == 0, err
        assert 20 <= json.loads(out.read_text(encoding="utf-8"))["best"] <= 31  # 上限：全选 = 3+1+4+1+5+9+2+6
        U._PY_ENABLED = False  # 模拟「在另一个进程里回读」：默认关闭
        code, _, err = run(capsys, "replay", str(out))
        assert code == 2 and "--trust-code" in err and "def objective" in err
        code, text, err = run(capsys, "replay", str(out), "--trust-code")
        assert code == 0 and "复现成功" in text, text + err
    finally:
        U._PY_ENABLED = False


def test_objective_py_refused_outside_custom(capsys, tmp_path):
    py = tmp_path / "o.py"
    py.write_text("def objective(x, data):\n    return 0\n", encoding="utf-8")
    code, _, err = run(capsys, "check", os.path.join(ROOT, "samples", "knapsack", "knapsack.json"),
                       "--objective-py", str(py))
    assert code == 2 and "custom" in err


# ---------------------------------------------------------------- 工程约束
def test_top_level_names_do_not_collide_with_the_modules_it_is_concatenated_with():
    """浏览器里 userproblem 与 domains 等拼进同一个名字空间；同名顶层定义会悄悄互相覆盖。"""
    def top(path):
        tree = ast.parse(open(os.path.join(ROOT, "py", path), encoding="utf-8").read())
        names = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    names.update(n.id for n in ast.walk(t) if isinstance(n, ast.Name))
        return names
    mine = top("userproblem.py")
    for other in ("domains.py", "domain_components.py", "entryseq.py", "scheduling.py", "taxonomy.py"):
        assert not (mine & top(other)), (other, mine & top(other))


def test_custom_domain_is_registered_everywhere_it_should_be():
    import registry as REG
    assert REG.VARIANTS["custom"] == U.ENCODINGS and "custom" in V.CORE_DOMAINS and "custom" in D._DOMAINS
    for v in U.ENCODINGS:
        assert json.loads(D.domain_list("custom", {"variant": v}))["algos"]
    assert REG.fidelity("custom", "bits")["level"] == "custom"


def test_repeated_squaring_cannot_blow_up_memory():
    src = "a = 10 ** 60\n" + "\n".join(f"a = a * a" for _ in range(28)) + "\nobjective = 1"
    msg, secs = _runtime_error(src)
    assert "整数太大" in msg and secs < 2
    msg, secs = _runtime_error("a = 7 ** 64\nb = a ** 64\nc = b ** 64\nobjective = c")
    assert "整数太大" in msg and secs < 2


# ---------------------------------------------------------------- 文档里的例子必须真的能跑
def test_documented_examples_are_valid_and_match_the_doc():
    import re
    ex = json.load(open(os.path.join(ROOT, "docs", "custom-examples.json"), encoding="utf-8"))
    doc = open(os.path.join(ROOT, "docs", "custom-problems.md"), encoding="utf-8").read()
    blocks = dict(re.findall(r"```objective:(\w+)\n(.*?)\n```", doc, re.S))
    assert set(blocks) == set(ex), "文档里的例子与 custom-examples.json 不一一对应"
    for k, v in ex.items():
        assert blocks[k].strip() == v["objective"].strip(), f"{k}：文档里的目标函数与数据文件不一致"
        p = {kk: vv for kk, vv in v.items() if kk != "title"}
        res = V.validate("custom", p, dry_run=True)
        assert res["ok"], (k, res["errors"])
        D.domain_start("custom", json.dumps(res["problem"]), "random" if p["variant"] != "real" else "random",
                       json.dumps({"max_iter": 5, "seed": 1}))
        assert D.domain_step() is not None

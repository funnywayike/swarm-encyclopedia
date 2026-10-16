# -*- coding: utf-8 -*-
"""新增一个问题（entryseq 词条）的脚手架。

    python tools/new_problem.py NAME --encoding perm|bits|real --title "中文名" [--en "English name"] [--abbr ABBR]
                                [--group sequencing] [--gj A2.3] [--dry-run]

做四件事（--dry-run 只打印、不写盘）：
  1. py/entryseq.py            追加一对 @_maker / @_objective（可运行的占位实现，保真度先标 illustrative）
  2. data/problems.json        追加问题页条目（正文是「TODO（占位）」）
  3. pages_domains.py          追加页面演示配置（ABSTRACT_DEMO）
  4. tests/test_NAME.py        生成测试骨架（注册、编码、目标函数在随机解上可算）
之后按屏幕上打印的清单做：把占位换成真实模型 → 补正文与文献 → tools/gen_samples.py → build_pages.py → golden.py（只应有新增）。

占位内容里都带「TODO（占位）」字样，tests/test_no_placeholders.py 会拦住它们——占位没换掉之前不能通过全部测试，也就发布不出去。
"""
import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.normpath(os.path.join(HERE, ".."))
PLACEHOLDER = "TODO（占位）"

ENC_LABEL = {"perm": "排列（访问 / 处理顺序）", "bits": "位向量（每位 = 选 / 不选）", "real": "实数向量"}

# 三种编码的占位模型：能跑、结果无意义，只用来让整条流水线（注册 → 校验 → 页面 → 算法）先通起来
TEMPLATES = {
    "perm": '''@_maker('{name}')
def _make_{name}(variant, n, seed, rng):
    # {todo}：生成实例。n 是规模上限；返回的字典必须含 "variant" 和 "n"（n = 排列的长度）。
    k = max(5, min(n, 12))
    return {{"variant": variant, "n": k, "w": [[rng.randint(1, 9) for _ in range(k)] for _ in range(k)]}}


@_objective('{name}', fidelity="{fidelity}", note="{note}", encoding="perm")
def _obj_{name}(self, s):
    # {todo}：目标函数，越小越好。s 是 0..n-1 的一个排列。
    w = self.p["w"]
    return sum(w[s[i]][s[(i + 1) % len(s)]] for i in range(len(s)))
''',
    "bits": '''@_maker('{name}')
def _make_{name}(variant, n, seed, rng):
    # {todo}：生成实例。返回的字典必须含 "variant" 和 "n"（n = 位向量的长度）。
    k = max(6, min(n, 24))
    return {{"variant": variant, "n": k, "a": [rng.randint(1, 20) for _ in range(k)]}}


@_objective('{name}', fidelity="{fidelity}", note="{note}", encoding="bits")
def _obj_{name}(self, s):
    # {todo}：目标函数，越小越好。s 是 0/1 列表，s[i] = 1 表示选第 i 项。
    a = self.p["a"]
    return abs(sum(a[i] for i in range(len(s)) if s[i]) - sum(a) // 2)
''',
    "real": '''@_maker('{name}')
def _make_{name}(variant, n, seed, rng):
    # {todo}：生成实例。返回的字典必须含 "variant" 和 "n"（n = 决策变量个数）。
    k = max(2, min(n, 10))
    return {{"variant": variant, "n": k, "target": [round(rng.uniform(-3, 3), 3) for _ in range(k)]}}


@_objective('{name}', fidelity="{fidelity}", note="{note}", encoding="real")
def _obj_{name}(self, s):
    # {todo}：目标函数，越小越好。s 是实数列表，每个分量在 [-5, 5]。
    t = self.p["target"]
    return round(sum((s[i] - t[i]) ** 2 for i in range(len(s))), 6)
''',
}

TEST_TEMPLATE = '''# -*- coding: utf-8 -*-
"""{title}（{name}）：由 tools/new_problem.py 生成的测试骨架。
把占位模型换成真实模型之后，请把下面的「TODO」补成对**独立实现**的核对——穷举、已知最优值、或文献里的数值——
而不是只比较算法自己上报的数字（见 tests/test_consistency.py 里这类假成绩是怎么被抓到的）。"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "py"))

import domains as D  # noqa: E402
import entryseq as E  # noqa: E402
import registry as REG  # noqa: E402
import validate as V  # noqa: E402

NAME = "{name}"


def test_registered_with_the_declared_encoding():
    assert NAME in E.VARIANTS and ("entryseq", NAME) in list(REG.cases())
    assert E.ENCODING[NAME] == "{encoding}"


def test_instance_is_valid_and_objective_is_finite_on_random_solutions():
    p = E.es_make(NAME, 12, 7)
    assert V.validate("entryseq", p, variant=NAME, dry_run=True)["ok"]
    ctx = E.es_ctx(p)
    rng = random.Random(1)
    for _ in range(50):
        v = ctx.obj(ctx.random(rng))
        assert isinstance(v, (int, float)) and v == v and abs(v) != float("inf")


def test_algorithms_run_and_report_what_the_solution_really_gives():
    p = E.es_make(NAME, 12, 7)
    keys = [a["key"] for a in json.loads(D.domain_list("entryseq", {{"variant": NAME}}))["algos"]]
    assert keys, "该编码下应有算法可用"
    for algo in keys[:: max(1, len(keys) // 3)]:
        D.domain_start("entryseq", json.dumps(p), algo, json.dumps({{"max_iter": 5, "seed": 3}}))
        last = None
        while True:
            s = D.domain_step()
            if s is None:
                break
            last = json.loads(s)
        assert last is not None


def test_todo_the_objective_matches_an_independent_implementation():
    """TODO（占位）：对小规模实例穷举（排列 / 位向量）或对已知最优点（实数向量）核对，再让算法找到它。"""
'''


def anchor_insert(path, anchor, text, dry):
    s = io.open(path, encoding="utf-8", newline="").read()
    assert s.count(anchor) == 1, f"{path}: 找不到唯一的锚点行 {anchor!r}"
    new = s.replace(anchor, text + "\n\n" + anchor)
    if not dry:
        io.open(path, "w", encoding="utf-8", newline="").write(new)


def main():
    ap = argparse.ArgumentParser(description="新增一个问题（entryseq 词条）的脚手架")
    ap.add_argument("name", help="问题 id：小写字母开头的 3~16 位小写字母 / 数字（同时是变体名和页面路径 /problem/NAME/）")
    ap.add_argument("--encoding", choices=("perm", "bits", "real"), required=True,
                    help="解的编码：perm 排列 / bits 位向量 / real 实数向量（决定用哪一族算法）")
    ap.add_argument("--title", required=True, help="中文名")
    ap.add_argument("--en", default="", help="英文名（默认同中文名占位）")
    ap.add_argument("--abbr", default="", help="缩写（默认 NAME 大写）")
    ap.add_argument("--group", default="sequencing", help="问题分类（见 data/problem_groups.json 的 id）")
    ap.add_argument("--gj", default="", help="综述分类号（默认取该分类里最常见的）")
    ap.add_argument("--root", default=DEFAULT_ROOT, help=argparse.SUPPRESS)  # 测试用：在副本上操作
    ap.add_argument("--dry-run", action="store_true", help="只打印要写入的内容，不改文件")
    a = ap.parse_args()

    name = a.name
    if not re.match(r"^[a-z][a-z0-9]{2,15}$", name):
        sys.exit("错误：name 应是小写字母开头的 3~16 位小写字母 / 数字")
    root = a.root
    es_path = os.path.join(root, "py", "entryseq.py")
    pj_path = os.path.join(root, "data", "problems.json")
    pd_path = os.path.join(root, "pages_domains.py")
    test_path = os.path.join(root, "tests", f"test_{name}.py")

    problems = json.loads(io.open(pj_path, encoding="utf-8").read())
    ids = {t["id"] for sec in ("knapsack_variants", "class_pages", "abstract_types") for t in problems.get(sec, [])}
    src = io.open(es_path, encoding="utf-8").read()
    if name in ids or re.search(r"""@_maker\([^)]*['"]%s['"]""" % re.escape(name), src):
        sys.exit(f"错误：{name} 已经存在（问题页或变体重名）")
    groups = [g["id"] for g in json.loads(io.open(os.path.join(root, "data", "problem_groups.json"), encoding="utf-8").read())]
    if a.group not in groups:
        sys.exit(f"错误：group 应是 {groups} 之一")
    gj = a.gj
    if not gj:
        from collections import Counter
        c = Counter(t.get("gj") for t in problems["abstract_types"] if t.get("group") == a.group and t.get("gj"))
        gj = c.most_common(1)[0][0] if c else "A9"
    abbr = a.abbr or name.upper()
    en = a.en or a.title
    todo = PLACEHOLDER

    code = TEMPLATES[a.encoding].format(name=name, fidelity="illustrative", todo=todo,
                                        note=f"{todo}：这是脚手架生成的占位模型，不是该问题本身")
    entry = {
        "id": name, "dir": name, "name": a.title, "en": en, "abbr": abbr, "group": a.group, "status": "page", "gj": gj,
        "badges": [{"k": "编码", "v": ENC_LABEL[a.encoding]}, {"k": "复杂度", "v": f"{todo}"}],
        "model": f"<p>{todo}：这个问题的数学模型——输入是什么、解是什么、目标和约束是什么。</p>",
        "diff": f"<p>{todo}：与相邻问题的区别（链接到站内其它问题页）。</p>",
        "algo": f"<p>{todo}：常用的求解思路，以及本页的算法是怎么用的。</p>",
        "sources": [f"{todo}：出处 1（作者 (年). 题目. 刊名, 卷(期), 页码）", f"{todo}：出处 2", f"{todo}：出处 3"],
    }
    demo = (f'ABSTRACT_DEMO["{name}"] = dict(page_domain="entryseq",\n'
            f'                            preset_options={{"n12": {{"variant": "{name}", "n": 12}}}},\n'
            f'                            preset_labels={{"n12": "12（演示实例）"}},\n'
            f'                            custom_fields=[{{"key": "n", "label": "规模 n", "min": 5, "max": 24, "val": 12}}],\n'
            f'                            extra_hint="{todo}：画布上每个元素的含义",\n'
            f'                            heading="在线求解演示 · {a.title}")')
    test_code = TEST_TEMPLATE.format(name=name, title=a.title, encoding=a.encoding)

    print(f"=== py/entryseq.py（追加在锚点行之前）===\n{code}")
    print(f"=== data/problems.json（abstract_types 末尾追加）===\n{json.dumps(entry, ensure_ascii=False, indent=2)}\n")
    print(f"=== pages_domains.py（追加在锚点行之前）===\n{demo}\n")
    print(f"=== tests/test_{name}.py ===\n（{len(test_code.splitlines())} 行测试骨架）\n")
    if a.dry_run:
        print("（--dry-run：没有改任何文件）")
        return
    if os.path.exists(test_path):
        sys.exit(f"错误：{test_path} 已存在")
    anchor_insert(es_path, "# ---- 新变体：tools/new_problem.py 把生成的 @_maker / @_objective 追加在这一行之前 ----", code.rstrip("\n"), False)
    problems["abstract_types"].append(entry)
    io.open(pj_path, "w", encoding="utf-8", newline="").write(json.dumps(problems, ensure_ascii=False, indent=2) + "\n")
    anchor_insert(pd_path, "# ---- 新问题的演示配置：tools/new_problem.py 追加在这一行之前 ----", demo, False)
    io.open(test_path, "w", encoding="utf-8", newline="").write(test_code)
    print(f"""已生成 {name}。接下来：
  1. 把 py/entryseq.py 里的占位实例生成与目标函数换成真实模型（搜索 {todo}）；
     需要页面上画出「解长什么样」时，加一个 @_detail('{name}')，并在 js/domain_page.js 的 entryseq 分支里加 `if (variant === "{name}")` 的画法（先用通用画法也能跑）。
  2. 补 data/problems.json 里 {name} 的模型 / 差异 / 算法 / 文献（至少 3 条可核实的出处），pages_domains.py 里的画布说明。
  3. 把 tests/test_{name}.py 末尾的 TODO 补成对独立实现的核对。
  4. python tools/gen_samples.py          # 生成示例数据与字段清单
     python build_pages.py                # 重建页面与浏览器引擎
     python tools/check_citations.py      # 核对文献（需联网）
     python tools/golden.py               # 看新增了哪些结果（只应有新增，没有「变化」）；确认后加 --update
     python -m pytest tests -q            # 占位没换完时 tests/test_no_placeholders.py 会失败——这是有意的""")


if __name__ == "__main__":
    main()

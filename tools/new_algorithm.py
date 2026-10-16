# -*- coding: utf-8 -*-
"""新增一个算法（TSP 求解器 + 算法页）的脚手架。

    python tools/new_algorithm.py KEY --title "中文名" --family F2 [--en "English name"] [--category 群体智能] [--dry-run]

做五件事（--dry-run 只打印、不写盘）：
  1. py/solvers.py        追加一个 BaseSolver 子类（可运行的占位实现）并在 SOLVERS 里登记
  2. data/algos.json      追加算法页条目（正文是「TODO（占位）」）
  3. data/mapping.json    追加「该算法 × TSP」的映射行（站点自检要求每个收录算法都有）
  4. tests/test_algo_KEY.py   生成测试骨架（契约：best 单调不增、best_tour 的长度 = 上报的 best_cost）
  5. 打印后续清单

占位内容里都带「TODO（占位）」字样，tests/test_no_placeholders.py 会拦住它们。

TSP 求解器只是「算法」的一个入口。让它也能解其它问题：
  · 排列编码的问题（所有 entryseq 排列词条、图着色、装箱……）：最省事的是给算法写一个连续版本，再经「随机键」桥接（py/domains_parts/ 里的 pk_*）；
  · 位向量 / 实数向量问题：在对应编码的算法族里加一个内核（见 CONTRIBUTING.md「新增算法」一节）。
本站收录算法的最低要求：TSP 上能跑 + 至少一个别的编码上能跑，且都要进黄金快照（tools/golden.py）。
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

CLASS_ANCHOR = "# ---- 新算法的类：tools/new_algorithm.py 追加在这一行之前 ----"
REG_ANCHOR = "    # ---- 新算法：tools/new_algorithm.py 在这一行之前登记 ----"

CLASS_TEMPLATE = '''class {cls}(BaseSolver):
    """{todo}：算法简介与出处（作者 (年) 题目）。"""

    name = "{todo}{title}"
    default_params = {{
        "max_iter": 200,
        "seed": 42,
    }}
    implemented = True
    category = "{category}"
    param_specs = {{}}  # 参数定义域，见其它算法：{{"参数": {{"min": .., "max": .., "step": .., "int": True, "label": "中文名", "desc": ".."}}}}

    def solve(self, problem, params):
        # {todo}：下面是「随机 2-opt 接受不变差」的占位，请换成真正的算法。
        # 契约：每代 yield 一个 IterationState；best_cost 单调不增，best_tour 的长度必须等于 best_cost。
        p = {{**self.default_params, **(params or {{}})}}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])
        tour = list(range(n))
        rng.shuffle(tour)
        cost = tour_length(tour, D)
        best, best_cost = list(tour), cost
        yield IterationState(0, best_cost, list(best), cost, {{"note": "初始解"}})
        for it in range(1, p["max_iter"] + 1):
            i, k = sorted(rng.sample(range(n), 2))
            cand = tour[:i] + tour[i:k + 1][::-1] + tour[k + 1:]
            c = tour_length(cand, D)
            if c <= cost:
                tour, cost = cand, c
            if cost < best_cost:
                best, best_cost = list(tour), cost
            yield IterationState(it, best_cost, list(best), cost, {{}})
'''

TEST_TEMPLATE = '''# -*- coding: utf-8 -*-
"""{title}（{key}）：由 tools/new_algorithm.py 生成的测试骨架。"""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "py"))

import solvers as S  # noqa: E402

KEY = "{key}"


def _problem(n=14, seed=3):
    rng = random.Random(seed)
    return [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(n)]


def _run(cities, iters=60, seed=1):
    S.start(json.dumps(cities), KEY, json.dumps({{"max_iter": iters, "seed": seed}}))
    out = []
    while True:
        st = S.step()
        if st is None:
            return out
        out.append(json.loads(st))


def test_registered_and_listed():
    keys = [s["key"] for s in json.loads(S.list_solvers())]
    assert KEY in keys


def test_best_never_gets_worse_and_matches_the_reported_tour():
    cities = _problem()
    states = _run(cities)
    assert len(states) > 5
    costs = [s["best_cost"] if "best_cost" in s else s["best"] for s in states]
    assert all(b <= a + 1e-9 for a, b in zip(costs, costs[1:])), "best 必须单调不增"
    last = states[-1]
    tour = last.get("best_tour") or last.get("tour")
    assert sorted(tour) == list(range(len(cities)))
    length = sum(((cities[tour[i]][0] - cities[tour[(i + 1) % len(tour)]][0]) ** 2
                  + (cities[tour[i]][1] - cities[tour[(i + 1) % len(tour)]][1]) ** 2) ** 0.5 for i in range(len(tour)))
    assert abs(length - costs[-1]) < 1e-6, "上报的 best 必须等于 best_tour 真实的长度"


def test_todo_beats_random_search_on_more_than_one_instance():
    """TODO（占位）：同一实例上多个种子，对随机基线要有明确优势；再补上算法在别的编码上的接入。"""
'''


def main():
    ap = argparse.ArgumentParser(description="新增一个算法（TSP 求解器 + 算法页）的脚手架")
    ap.add_argument("key", help="算法 key：小写字母开头，2~15 位小写字母 / 数字 / 连字符（同时是页面路径 /algo/<家族>/<key>/ 的一部分）")
    ap.add_argument("--title", required=True, help="中文名")
    ap.add_argument("--en", default="", help="英文名")
    ap.add_argument("--family", required=True, help="算法家族 id（data/families.json，如 F1 进化计算、F2 群体智能……）")
    ap.add_argument("--category", default="", help="下拉框里的分类标签（默认取家族的简称）")
    ap.add_argument("--cls", default="", help="类名（默认由 key 推出）")
    ap.add_argument("--root", default=DEFAULT_ROOT, help=argparse.SUPPRESS)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    key = a.key
    if not re.match(r"^[a-z][a-z0-9-]{1,14}$", key):
        sys.exit("错误：key 应是小写字母开头的 2~15 位小写字母 / 数字 / 连字符")
    root = a.root
    sv_path = os.path.join(root, "py", "solvers.py")
    al_path = os.path.join(root, "data", "algos.json")
    test_path = os.path.join(root, "tests", "test_algo_" + key.replace("-", "_") + ".py")

    mp_path = os.path.join(root, "data", "mapping.json")
    algos = json.loads(io.open(al_path, encoding="utf-8").read())
    mapping = json.loads(io.open(mp_path, encoding="utf-8").read())
    fams = {f["id"]: f for f in json.loads(io.open(os.path.join(root, "data", "families.json"), encoding="utf-8").read())}
    if a.family not in fams:
        sys.exit(f"错误：family 应是 {sorted(fams)} 之一")
    if any(x["key"] == key for x in algos):
        sys.exit(f"错误：算法 {key} 已存在")
    src = io.open(sv_path, encoding="utf-8").read()
    for anchor in (CLASS_ANCHOR, REG_ANCHOR):
        if src.count(anchor) != 1:
            sys.exit(f"错误：py/solvers.py 里找不到唯一的锚点行：{anchor.strip()}")
    cls = a.cls or "".join(p.capitalize() for p in re.split(r"[-_]", key)) + "Solver"
    if re.search(r"^class %s\b" % re.escape(cls), src, re.M):
        sys.exit(f"错误：类名 {cls} 已存在，请用 --cls 指定别的")
    category = a.category or fams[a.family]["short"]
    todo = PLACEHOLDER

    code = CLASS_TEMPLATE.format(cls=cls, todo=todo, title=a.title, category=category)
    entry = {
        "key": key, "slug": f"{key}-tsp", "name": f"{todo}{a.title}",
        "title": f"{todo}{a.title}求解 TSP 在线演示",
        "desc": f"{todo}：一两句话的页面描述（搜索结果里显示的那句）。",
        "h1": f"{todo}{a.title}求解 TSP 在线演示",
        "lead": f"{todo}：一句话讲清这个算法的核心想法。",
        "intro": [f"{todo}：背景与出处。", f"{todo}：与相近算法的区别。"],
        "principle": [f"{todo}：第 1 步", f"{todo}：第 2 步", f"{todo}：第 3 步"],
        "params": [["max_iter", "200", "迭代代数"], ["seed", "42", "随机种子"]],
        "paper": f"{todo}：原始文献（作者 (年). 题目. 刊名, 卷(期), 页码.）",
        "faq": [[f"{todo}：读者最可能问的问题？", f"{todo}：回答。"]],
        "family": a.family,
        "use_when": f"{todo}：什么时候用它。",
        "avoid_when": f"{todo}：什么时候别用它。",
    }
    row = {"algo": key, "problem": "tsp", "how": f"{todo}：这个算法怎样编码并求解 TSP",
           "evidence": "TSP 引擎 200 代同链实测（seed=42 同一随机实例），成绩卡见算法页",
           "demo": f"/algo/{fams[a.family]['dir']}/{key}/", "tier": "实测"}
    test_code = TEST_TEMPLATE.format(key=key, title=a.title)

    print(f"=== py/solvers.py（类追加在锚点行之前；SOLVERS 里登记 \"{key}\": {cls}）===\n{code}")
    print(f"=== data/algos.json（末尾追加）===\n{json.dumps(entry, ensure_ascii=False, indent=2)}\n")
    print(f"=== data/mapping.json（algo_solves 末尾追加）===\n{json.dumps(row, ensure_ascii=False, indent=2)}\n")
    print(f"=== {os.path.relpath(test_path, root)} ===\n（{len(test_code.splitlines())} 行测试骨架）\n")
    if a.dry_run:
        print("（--dry-run：没有改任何文件）")
        return
    if os.path.exists(test_path):
        sys.exit(f"错误：{test_path} 已存在")
    new = src.replace(CLASS_ANCHOR, code.rstrip("\n") + "\n\n\n" + CLASS_ANCHOR)
    new = new.replace(REG_ANCHOR, f'    "{key}": {cls},\n' + REG_ANCHOR)
    io.open(sv_path, "w", encoding="utf-8", newline="").write(new)
    algos.append(entry)
    io.open(al_path, "w", encoding="utf-8", newline="").write(json.dumps(algos, ensure_ascii=False, indent=2) + "\n")
    mapping["algo_solves"].append(row)
    io.open(mp_path, "w", encoding="utf-8", newline="").write(json.dumps(mapping, ensure_ascii=False, indent=2) + "\n")
    io.open(test_path, "w", encoding="utf-8", newline="").write(test_code)
    print(f"""已生成 {key}。接下来：
  1. 把 py/solvers.py 里 {cls} 的占位实现换成真正的算法（搜索 {todo}）；param_specs 里写清每个参数的范围与含义。
  2. 补 data/algos.json 里 {key} 的全部正文，data/mapping.json 里 {key} 那一行的 how 一栏；原始文献用 tools/check_citations.py 核对（需联网）。
  3. 让它也能解其它编码的问题（见 CONTRIBUTING.md「新增算法」）——收录要求是 TSP + 至少一个别的编码。
  4. python build_pages.py             # 重建页面与浏览器引擎
     python tools/check_citations.py   # 核对文献（需联网）
     python tools/golden.py            # 看新增了哪些结果（只应有新增）；确认后加 --update
     python -m pytest tests -q         # 占位没换完时 tests/test_no_placeholders.py 会失败——这是有意的""")


if __name__ == "__main__":
    main()

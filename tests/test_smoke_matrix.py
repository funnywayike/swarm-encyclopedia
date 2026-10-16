# -*- coding: utf-8 -*-
"""全矩阵冒烟：页面下拉里列出的每个 (域, 变体, 算法) 组合都必须能启动并推进 2 代。

防的是这类回归：下拉里有一个选项，用户点了却是 Python 报错（2026-10 发布前复检发现 entryseq 的
ga/ts 在 57 个变体上全部崩溃、bv_* 在 9 个变体上崩溃、mmo 缺目标函数，此前没有任何门覆盖到）。
撤下的组合必须同时从 domain_list 里消失（页面不列幽灵选项）。"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "py"))

import domains as D  # noqa: E402
from registry import VARIANTS, PLAIN  # noqa: E402


def _combos():
    for dom in PLAIN:
        yield dom, None
    for dom, vs in VARIANTS.items():
        for v in vs:
            yield dom, v


def test_every_listed_algorithm_starts_and_steps():
    failures = []
    total = 0
    for dom, var in _combos():
        opts = {"variant": var} if var else {}
        pre = D.domain_preset(dom, 7, opts)
        for a in json.loads(D.domain_list(dom, opts))["algos"]:
            total += 1
            try:
                D.domain_start(dom, pre, a["key"], json.dumps({"max_iter": 2, "seed": 7}))
                for _ in range(2):
                    D.domain_step()
            except Exception as e:  # noqa: BLE001
                failures.append(f"{dom}/{var}/{a['key']}: {type(e).__name__}: {str(e)[:60]}")
    assert total > 1500
    assert not failures, f"{len(failures)}/{total} 组合失败：\n" + "\n".join(failures[:25])


def test_algorithms_of_the_wrong_encoding_are_really_rejected():
    """每个 entryseq 变体只配自己编码的算法族；错配的组合既不能出现在下拉里，也不能被 domain_start 接受。
    （旧版是「撤下清单」：maxcut 上的 bv_*/ga/ts 被撤下。现在 maxcut 是位向量变体，它们是合法的；不合法的是排列随机键 pk_*。）"""
    wrong = {"maxcut": ("pk_pso", "pso"), "lap": ("bv_pso", "pso"), "numpart": ("pk_pso", "bv_pso"), "vcover": ("pk_pso", "pso")}
    for variant, algos in wrong.items():
        pre = D.domain_preset("entryseq", 7, {"variant": variant})
        listed = {a["key"] for a in json.loads(D.domain_list("entryseq", {"variant": variant}))["algos"]}
        for algo in algos:
            assert algo not in listed, f"{variant}/{algo} 不该出现在下拉里"
            try:
                D.domain_start("entryseq", pre, algo, "{}")
            except ValueError:
                continue
            raise AssertionError(f"{variant}/{algo} 应被拒绝")


def test_selftest_blocks_are_skipped_in_the_browser():
    """Pyodide 里这些源码以 __main__ 身份拼接执行：没有平台判断的 `if __name__ == "__main__"` 自测块
    会在每次页面加载时跑一遍（solvers 自测 PSO、scheduling 跑 4 个排程基准）。"""
    parts = ["domains_parts/" + f for f in sorted(os.listdir(os.path.join(HERE, "..", "py", "domains_parts"))) if f.endswith(".py")]
    for rel in ["solvers.py", "scheduling.py"] + parts:
        with open(os.path.join(HERE, "..", "py", rel), encoding="utf-8") as f:
            src = f.read()
        if rel.startswith("domains_parts/") and "if __name__" not in src:
            continue  # 只有写了自测块的那个分块需要平台判断
        assert 'if __name__ == "__main__":' not in src, f"{rel}: 自测块缺少 emscripten 平台判断"
        assert '__import__("sys").platform != "emscripten"' in src

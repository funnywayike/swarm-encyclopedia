# -*- coding: utf-8 -*-
"""脚手架（tools/new_problem.py、tools/new_algorithm.py）生成的占位内容都带「TODO（占位）」。
占位没换成真实内容之前，这个测试必须失败——否则一个只会随机乱走的「算法」、一段写着「TODO」的问题页就会被发布出去。"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
MARK = "TODO（占位）"
SKIP = {"test_no_placeholders.py", "test_scaffolds.py"}  # 这两个文件里的字面量是用来检测 / 生成占位的


def _files():
    for sub, exts in (("data", (".json",)), ("py", (".py",)), ("py/domains_parts", (".py",)), ("tests", (".py",)), (".", (".py",))):
        base = os.path.join(ROOT, sub)
        if not os.path.isdir(base):
            continue
        for f in sorted(os.listdir(base)):
            full = os.path.join(base, f)
            if os.path.isfile(full) and f.endswith(exts) and f not in SKIP:
                yield full


def test_no_scaffold_placeholder_is_left_in_the_project():
    left = []
    for path in _files():
        text = open(path, encoding="utf-8").read()
        if MARK in text:
            n = text.count(MARK)
            first = next(i for i, ln in enumerate(text.splitlines(), 1) if MARK in ln)
            left.append(f"{os.path.relpath(path, ROOT)}（{n} 处，首处第 {first} 行）")
    assert not left, "还有脚手架留下的占位没换成真实内容：\n  " + "\n  ".join(left)

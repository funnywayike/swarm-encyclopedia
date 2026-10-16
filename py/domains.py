# -*- coding: utf-8 -*-
"""
问题域引擎（背包 / 连续函数 / 多目标 / 图着色 / 装箱 / 集合覆盖 / SAT / QUBO / GAP / UFLP / 各变体家族 / 词条域）。

这个文件只是装载器：引擎源码在 py/domains_parts/ 下按文件名顺序排列的各个分块里（00_header、10_knapsack、20_continuous……），
本文件把它们依次编译、**在同一个模块名字空间里**执行，效果和原来的一整个 domains.py 完全相同——
`import domains` 之后 `domains.domain_list` / `domains._RUN` / `domains._BIN_ALGOS` 都在。

为什么是「共享一个名字空间」而不是一堆互相 import 的模块：
  浏览器里的引擎本来就是把这些源码拼成一个字符串、在同一个名字空间里执行（build_pages.py 的 gen_domains_src，按同样的文件名顺序拼）。
  本地也用同样的方式装载，「本地测试通过、浏览器里 NameError / 同名覆盖」这一类问题就不会再出现；
  注册表之间的互相挂载（`_BIN_ALGOS["bv_mfo"] = …`、按名字取内核的 `getattr(__import__(__name__), …)`）也照常工作。
  分块的顺序就是执行顺序：后面的块可以直接用前面块里的名字，反过来不行；新增分块按需要的位置起一个带编号的文件名即可。
  tests/test_browser_namespace.py 守卫「各分块与别的模块之间没有同名顶层定义」。

修改 / 新增一个域：改对应编号的分块（见 py/domains_parts/README.md）。编译时用的是分块文件的真实路径，所以报错栈里的文件名和行号就是分块里的。
"""
import os as _os

PARTS_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "domains_parts")


def part_files():
    """分块文件的完整路径，按文件名排序（= 执行顺序 = 浏览器里的拼接顺序）。"""
    return [_os.path.join(PARTS_DIR, f) for f in sorted(_os.listdir(PARTS_DIR)) if f.endswith(".py")]


def _load_parts():
    ns = globals()
    for path in part_files():
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        exec(compile(src, path, "exec"), ns)


_load_parts()

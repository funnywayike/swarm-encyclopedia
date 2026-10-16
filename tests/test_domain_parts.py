# -*- coding: utf-8 -*-
"""py/domains.py 是装载器，引擎在 py/domains_parts/ 的分块里（见该目录的 README.md）。
这里钉死装载方式：顺序确定、每块自己可编译、装载后的模块与浏览器拼接出来的源码一致。"""
import ast
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "py"))

import domains as D  # noqa: E402

PARTS = os.path.join(ROOT, "py", "domains_parts")


def test_parts_are_numbered_unique_and_loaded_in_name_order():
    files = [f for f in os.listdir(PARTS) if f.endswith(".py")]
    assert files and all(re.match(r"^\d\d_[a-z0-9_]+\.py$", f) for f in files), "分块文件名应是 NN_名字.py"
    assert len({f[:2] for f in files if f[:2] == "00"}) == 1 and files.count("00_header.py") == 1
    assert [os.path.basename(p) for p in D.part_files()] == sorted(files)
    assert len({int(f[:2]) for f in files}) >= 10


def test_every_part_is_valid_python_on_its_own():
    for f in sorted(os.listdir(PARTS)):
        if f.endswith(".py"):
            src = open(os.path.join(PARTS, f), encoding="utf-8").read()
            ast.parse(src, filename=f)
            assert src.endswith("\n"), f"{f} 要以换行结尾（拼接时下一块的第一行不能粘在它后面）"


def test_the_loaded_module_exposes_the_engine_api_and_shared_registries():
    for name in ("domain_list", "domain_preset", "domain_start", "domain_step", "domain_bench", "_DOMAINS", "_RUN",
                 "_BIN_ALGOS", "_es_registry", "FUNCS", "es_make"):
        assert hasattr(D, name), name
    assert len(D._DOMAINS) >= 15
    # 注册表之间的互相挂载（跨块修改同一个字典对象）确实生效
    assert "bv_mfo" in D._BIN_ALGOS and D._BIN_ALGOS is D._CUSTOM_REG["bits"][0]


def test_errors_inside_a_part_report_that_parts_file_and_line():
    """装载器用分块的真实路径编译，报错栈里看到的是分块文件名而不是 domains.py。"""
    import traceback
    try:
        D.domain_start("knapsack", "{}", "no-such-algo", "{}")
    except Exception:  # noqa: BLE001
        tb = traceback.format_exc()
        assert "domains_parts" in tb and "90_domains_and_api.py" in tb, tb

# -*- coding: utf-8 -*-
"""页面里的 JavaScript 必须能解析。

背景（2026-10 发现）：公开页面文案的整改脚本有一条规则「删掉空括号」，连字符串里嵌着的 JavaScript 也一起改了——
`(function(){…})();` 变成 `(function{…});`，`e.preventDefault()` 变成 `e.preventDefault`。结果是全站每个页面的主题脚本、
触屏下拉菜单、词条过滤都带着语法错误，控制台每页两条 "Uncaught SyntaxError"，而 selfcheck / pytest 都看不见——
它们只看 HTTP 状态码和文本，从不解析脚本。

这里用 Node 把每个构建出来的页面里的内联脚本、以及站点自己的 js/*.js 都解析一遍。没有 node 时跳过（CI 的 Ubuntu 镜像自带）。"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="需要 node 来解析 JavaScript")

SCRIPT_RE = re.compile(r"<script([^>]*)>(.*?)</script>", re.S | re.I)

# 逐个尝试解析；经典脚本用 new Function（只解析不执行），模块脚本放进 vm.SourceTextModule 不可用，故跳过含 import/export 的
CHECKER = r"""
const fs = require("fs");
const items = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const bad = [];
for (const it of items) {
  try { new Function(it.code); } catch (e) { bad.push({id: it.id, err: String(e.message).slice(0, 120)}); }
}
process.stdout.write(JSON.stringify(bad));
"""


def _html_files():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "pyodide", "tools", "tests", "docs", "samples", "__pycache__")]
        for f in files:
            if f.endswith(".html"):
                yield os.path.join(base, f)


def test_every_inline_script_in_every_built_page_parses(tmp_path):
    unique = {}  # 脚本文本的哈希 -> (代码, 出现的页面)
    for path in _html_files():
        html = open(path, encoding="utf-8").read()
        for attrs, code in SCRIPT_RE.findall(html):
            if "src=" in attrs.lower() or re.search(r'type\s*=\s*["\'](?!text/javascript)', attrs, re.I):
                continue  # 外部脚本 / json-ld / module 等不在这里查
            if not code.strip():
                continue
            h = hashlib.sha1(code.encode("utf-8")).hexdigest()
            unique.setdefault(h, (code, []))[1].append(os.path.relpath(path, ROOT))
    assert unique, "没有找到任何页面：先运行 python build_pages.py"
    items = [{"id": h, "code": c} for h, (c, _p) in unique.items()]
    jf, cf = tmp_path / "items.json", tmp_path / "check.js"
    jf.write_text(json.dumps(items), encoding="utf-8")
    cf.write_text(CHECKER, encoding="utf-8")
    r = subprocess.run([NODE, str(cf), str(jf)], capture_output=True, text=True, encoding="utf-8", timeout=120)
    assert r.returncode == 0, r.stderr[-800:]
    bad = json.loads(r.stdout)
    msgs = []
    for b in bad:
        code, pages = unique[b["id"]]
        msgs.append(f"{b['err']}\n    出现在 {len(pages)} 个页面，如 {pages[0]}\n    开头：{code.strip()[:90]!r}")
    assert not bad, "页面里有无法解析的内联脚本：\n" + "\n".join(msgs)


def test_the_sites_own_javascript_files_parse(tmp_path):
    problems = []
    js_dir = os.path.join(ROOT, "js")
    for f in sorted(os.listdir(js_dir)):
        if not f.endswith((".js", ".mjs")) or f.endswith("_src.js"):
            continue
        # 当作 ES 模块解析（语法是经典脚本的超集；站点里 tool.js / worker.js 本来就是模块）
        copy = tmp_path / (f.rsplit(".", 1)[0] + ".mjs")
        shutil.copyfile(os.path.join(js_dir, f), copy)
        r = subprocess.run([NODE, "--check", str(copy)], capture_output=True, text=True, encoding="utf-8", timeout=60)
        if r.returncode != 0:
            problems.append(f"js/{f}: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else '?'}")
    assert not problems, "\n".join(problems)

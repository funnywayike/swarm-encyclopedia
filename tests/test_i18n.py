# -*- coding: utf-8 -*-
"""中文 / English 界面（js/i18n.js + data/i18n/*.json）的守卫。

范围（见 README）：界面文字全部有英文；首页 / 5 分钟上手 / 对比 / 问题总览 / 自带问题 / 归约 / 百科总纲 等关键页整页有英文；
每个算法页、问题页、家族页、元层页都有一段英文摘要；深度正文保持中文并由页面顶部的说明条标明。
这些测试保证：词典是合法的、没有漏掉的界面文字、新增页面不会悄悄变成半中文半英文。"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import i18n_extract as X  # noqa: E402

KEY_PAGES = ["index.html", "guide/", "compare/", "problem/index.html", "problem/custom/", "problem/reductions/", "encyclopedia/",
             "404.html"]
CJK = re.compile(r"[㐀-鿿]")


def _load(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return json.load(f)


def _dict_files():
    return sorted(glob.glob(os.path.join(ROOT, "data", "i18n", "*.json")))


def test_dictionary_files_are_valid_and_well_formed():
    assert _dict_files(), "data/i18n/ 下没有词典文件"
    seen = {}
    for f in _dict_files():
        d = json.load(open(f, encoding="utf-8"))
        assert set(d) <= {"strings", "patterns"}, f
        for k, v in d.get("strings", {}).items():
            where = f"{os.path.basename(f)}: {k[:40]!r}"
            assert isinstance(v, str) and v.strip(), f"{where} 译文为空"
            assert k == X.norm(k) or k.endswith(" ") or k.startswith(" ") or "  " not in k, where
            assert "  " not in k, f"{where} 键里有连续空格（运行时会先规整空白再查词典）"
            n_keys = k.count("{n}") + k.count("{*}")
            used = re.findall(r"\{(n|\*|\d)\}", v)
            explicit = [int(u) for u in used if u.isdigit()]
            assert all(1 <= i <= n_keys for i in explicit), f"{where} 译文引用了不存在的捕获组"
            if n_keys == 0:
                assert not used, f"{where} 键里没有占位符，译文里却有"
            elif not explicit:
                assert len(used) <= n_keys, f"{where} 译文的占位符比键多"
            seen.setdefault(k, []).append(os.path.basename(f))
        for pat, rep in d.get("patterns", []):
            re.compile(pat)
            assert isinstance(rep, str)
    dup = {k: v for k, v in seen.items() if len(v) > 1 and len(set(v)) > 1}
    # 同一个键出现在多个文件里是允许的（后者覆盖前者），但要尽量少
    assert len(dup) < 40, f"{len(dup)} 个键在多个词典文件里重复，请去重：{list(dup)[:3]}"


def test_runtime_files_exist_and_parse():
    p = os.path.join(ROOT, "js", "i18n_en.js")
    assert os.path.exists(p), "js/i18n_en.js 未生成（运行 python build_pages.py）"
    txt = open(p, encoding="utf-8").read()
    body = txt[txt.index("window.I18N_EN = ") + len("window.I18N_EN = "):].rstrip().rstrip(";")
    d = json.loads(body)
    assert len(d["strings"]) > 500
    node = shutil.which("node")
    if node:
        r = subprocess.run([node, "--check", os.path.join(ROOT, "js", "i18n.js")], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


def test_every_page_has_the_language_switch_and_loader():
    missing = []
    for f in glob.glob(os.path.join(ROOT, "**", "index.html"), recursive=True):
        rel = os.path.relpath(f, ROOT).replace("\\", "/")
        if rel.startswith(("vendor/", "docs/", "samples/", ".")):
            continue
        t = open(f, encoding="utf-8").read()
        if 'http-equiv="refresh"' in t:      # 旧地址重定向桩
            continue
        if 'id="langToggle"' not in t or "i18n.js" not in t:
            missing.append(rel)
    assert not missing, f"{len(missing)} 个页面缺少语言切换或 i18n.js：{missing[:5]}"


def test_english_names_and_summaries_exist_for_every_page_that_has_a_page():
    algos = _load("data/algos.json")
    for a in algos:
        for k in ("name_en", "tagline_en", "summary_en"):
            assert a.get(k), f"算法 {a['key']} 缺 {k}"
        assert not CJK.search(a["summary_en"] + a["tagline_en"] + a["name_en"]), a["key"]
        assert 25 <= len(a["summary_en"].split()) <= 140, f"{a['key']} 英文摘要长度异常"
        assert len(a["tagline_en"]) <= 110
    probs = _load("data/problems.json")
    for sec in ("abstract_types", "class_pages", "knapsack_variants"):
        for t in probs[sec]:
            if sec == "abstract_types" and t.get("status") != "page":
                continue
            assert t.get("summary_en"), f"{sec}/{t['id']} 缺 summary_en"
            assert not CJK.search(t["summary_en"]), t["id"]
            assert 25 <= len(t["summary_en"].split()) <= 140, f"{t['id']} 英文摘要长度异常"
    for f in _load("data/families.json"):
        assert f.get("name_en") and f.get("summary_en"), f["id"]
    for p in _load("data/meta.json")["pages"]:
        assert p.get("summary_en"), p["id"]


def test_the_summary_block_is_rendered_on_pages():
    for rel in ("algo/f2-si/pso/index.html", "problem/fss/index.html", "problem/knapsack/fractional/index.html",
                "algo/f1-ea/index.html", "meta/theory/index.html"):
        assert 'class="en-summary"' in open(os.path.join(ROOT, rel), encoding="utf-8").read(), rel


def test_titles_and_headings_have_english_versions():
    for rel in ("algo/f2-si/pso/index.html", "problem/fss/index.html", "index.html", "coverage/index.html"):
        t = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        assert re.search(r"<title data-en=\"[^\"]+\">", t), rel
        assert re.search(r"<h1[^>]* data-en=\"[^\"]+\"", t), rel


def test_interface_chrome_is_fully_translated():
    """在 ≥10 个页面出现的文字 = 导航、按钮、页脚、各页共用的小节标题：不允许漏。"""
    d = X.Dict()
    acc = X.collect(X.page_files(), d)
    miss = sorted(k for k, v in acc.items() if len(v["pages"]) >= 10 and not d.has(k))
    assert not miss, f"{len(miss)} 条共用界面文字没有英文，如：{miss[:5]}"


def test_demo_sections_of_problem_pages_are_fully_translated():
    d = X.Dict()
    acc = X.collect(X.page_files(["problem/"]), d, "demo")
    miss = sorted(k for k in acc if not d.has(k))
    assert not miss, f"{len(miss)} 条问题页演示区的文字没有英文，如：{miss[:5]}"


@pytest.mark.parametrize("page", KEY_PAGES)
def test_key_pages_are_fully_translated(page):
    d = X.Dict()
    acc = X.collect(X.page_files([page]), d)
    miss = sorted(k for k in acc if not d.has(k))
    assert not miss, f"{page} 有 {len(miss)} 条文字没有英文，如：{[m[:40] for m in miss[:5]]}"


def test_every_demo_heading_suffix_has_english():
    """「在线求解演示 · XXX」按模式翻译，但后半截 XXX（问题名）必须各自有词条，否则标题是半中半英。"""
    d = X.Dict()
    miss = []
    for f in glob.glob(os.path.join(ROOT, "problem", "**", "index.html"), recursive=True):
        t = open(f, encoding="utf-8").read()
        m = re.search(r'<h2 id="demo">在线求解演示 · ([^<]*)</h2>', t)
        if m and CJK.search(m.group(1)) and m.group(1).strip() not in d.strings:
            miss.append((os.path.relpath(f, ROOT), m.group(1)))
    assert not miss, miss[:5]

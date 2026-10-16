# -*- coding: utf-8 -*-
"""公开页面是写给读者的：不得出现内部调研引用（综述 §、报告 §、R99）、内部收录分档（A 档/三档收编制）、
内部版本标记（P1.3a、H1 kpvar 域实测）和开发者黑话（防假跑、正典）。写给贡献者的页面例外，但必须标明。"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "tools"))

import userfacing_rules as U  # noqa: E402


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def test_public_pages_have_no_internal_references_or_developer_jargon():
    found = U.scan_public_pages()
    assert not found, f"{len(found)} 处泄漏，如：{found[:3]}（运行 python tools/userfacing_rules.py --apply 或手工改写）"


def test_rules_are_idempotent_source_files_are_already_clean():
    """源文件里不应再有能被规则命中的文案；新写的内容命中规则 = 又漏了一处。"""
    hits, changed = U.process(apply=False)
    assert not hits, f"{len(hits)} 处待改写，如 {hits[:2]}"


def test_contributor_pages_say_who_they_are_for_and_are_grouped_in_the_nav():
    for rel in ("coverage/index.html", "components/index.html", "discovery/index.html"):
        assert 'class="contrib-note"' in _read(rel), f"{rel} 缺少「写给贡献者」说明条"
    home = _read("index.html")
    assert "给贡献者" in home
    for href in ("coverage/", "components/", "discovery/"):
        assert href in home, f"导航里没有 {href}"


def test_glossary_defines_the_terms_the_pages_actually_use():
    enc = _read("encyclopedia/index.html")
    for term in ("假跑 (fake run)", "随机键编码 (random keys)", "吸引盆 (basin of attraction)"):
        assert term in enc, term

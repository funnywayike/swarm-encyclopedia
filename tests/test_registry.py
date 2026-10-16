# -*- coding: utf-8 -*-
"""登记表（py/registry.py）与现实一致：它列的引擎都认，站点页面用到的它都有，校验器的域清单与它同源。"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "py"))

import domains as D  # noqa: E402
import entryseq as E  # noqa: E402
import registry as REG  # noqa: E402
import validate as V  # noqa: E402


def test_registry_domains_match_the_engine():
    engine = set(D._DOMAINS)
    listed = set(REG.PLAIN) | set(REG.VARIANTS) | set(REG.SCHEDULING)
    assert engine == listed, f"引擎有而登记表没有：{engine - listed}；登记表有而引擎没有：{listed - engine}"


def test_every_registered_variant_is_known_to_the_engine():
    for dom, vs in REG.VARIANTS.items():
        assert len(vs) == len(set(vs)), f"{dom} 变体重复"
        for v in vs:
            pre = json.loads(D.domain_preset(dom, 7, {"variant": v}))
            assert isinstance(pre, dict) and pre.get("variant", v) == v, f"{dom}/{v}"
            assert json.loads(D.domain_list(dom, {"variant": v}))["algos"], f"{dom}/{v} 没有任何算法"
    assert REG.DEFAULT_VARIANT.keys() == REG.VARIANTS.keys()
    for dom, v in REG.DEFAULT_VARIANT.items():
        assert v in REG.VARIANTS[dom]


def test_entryseq_variants_come_from_the_module_not_a_hand_list():
    assert REG.VARIANTS["entryseq"] == E.VARIANTS == tuple(E._MAKERS)
    assert set(E._OBJS) == set(E.VARIANTS)  # 每个变体都有目标函数（登记顺序可不同）
    assert len(E.VARIANTS) == len(E._MAKERS) >= 60
    assert set(E.VEC_VARIANTS) <= set(E.VARIANTS)


def test_every_variant_used_by_a_site_page_is_registered():
    """页面写了某个变体而登记表没有，上传校验、示例、冒烟、黄金快照都会漏掉它。"""
    used = {}
    for f in glob.glob(os.path.join(HERE, "..", "problem", "**", "index.html"), recursive=True):
        t = open(f, encoding="utf-8").read()
        m = re.search(r'window\.PAGE_DOMAIN = "([^"]+)"', t)
        pm = re.search(r'window\.PAGE_PRESETS = (\{.*?\});\n', t)
        if not m or not pm:
            continue
        for opts in json.loads(pm.group(1)).values():
            used.setdefault(m.group(1), set()).add(opts.get("variant"))
    assert used, "没有扫到任何问题页"
    known = set(REG.PLAIN) | set(REG.VARIANTS) | set(REG.SCHEDULING)
    for dom, vs in used.items():
        assert dom in known, f"页面用了未登记的域 {dom}"
        missing = {v for v in vs if v and v not in REG.VARIANTS.get(dom, ())}
        assert not missing, f"{dom} 的变体 {sorted(missing)} 页面在用但登记表没有"


def test_validator_and_registry_agree_on_uploadable_domains():
    assert set(V.CORE_DOMAINS) == set(REG.UPLOADABLE)
    assert not set(REG.SCHEDULING) & set(V.CORE_DOMAINS)


def test_cases_enumerates_everything_once():
    cs = list(REG.cases(include_scheduling=True))
    assert len(cs) == len(set(cs))
    assert len(cs) == len(REG.PLAIN) + sum(len(v) for v in REG.VARIANTS.values()) + len(REG.SCHEDULING)

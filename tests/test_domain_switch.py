# -*- coding: utf-8 -*-
"""P2 切域协议对账测试：data/mapping.json demo_algo 与 py/domains.py 注册表对账，
以及构建产物中「▶ 直达演示」链接必须带 ?algo= 上下文参数。

对应 HANDOFF 验收链：本文件是「不生成落地后选不出来的死链」的数据层保证。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPPING = json.load(open(os.path.join(ROOT, "data", "mapping.json"), encoding="utf-8"))
SOLVES = MAPPING["algo_solves"]

sys.path.insert(0, os.path.join(ROOT, "py"))
import domains as _dm  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "tools"))
import gen_mapping_rows as _gm  # noqa: E402

# 问题页 URL → (引擎 domain, domain_list opts)：页面的演示配置（pages_domains 里的 ABSTRACT_DEMO / CLASS_DEMO /
# VARIANT_DEMO，枢纽页另有固定映射）；没有演示配置的页面（TSP 首页等）不在表里。
_PROBLEMS = json.load(open(os.path.join(ROOT, "data", "problems.json"), encoding="utf-8"))
_URL_TO_PID = {url: pid for pid, (_name, url) in _gm.page_index(_PROBLEMS).items()}
for _pid, _v in MAPPING["problem_index"].items():
    if _pid in _gm.HUBS:
        _URL_TO_PID[_v["url"]] = _pid
_EXTRA = {  # 同一个页面的别名：BBOB 与连续域同源、MaOP 是多目标域的三目标变体
    "/problem/bbob/": ("continuous", {}),
    "/problem/maop/": ("multiobj", {"variant": "maop"}),
}


def _case_for(demo: str):
    if demo in _EXTRA:
        return _EXTRA[demo]
    pid = _URL_TO_PID.get(demo)
    cfg = _gm._demo_cfg(pid) if pid else None
    if cfg is None:
        return None
    dom, var = _gm._case_of(cfg)
    return dom, ({"variant": var} if var else {})


def _slug_of(demo: str):
    """/problem/<slug>/ → slug；其余（TSP 首页等）→ None。"""
    if not demo or not demo.startswith("/problem/"):
        return None
    return demo.strip("/").split("/")[-1]


def _registry_for(demo: str):
    """返回 demo 对应引擎域的算法注册表集合；非问题域 demo → None。"""
    case = _case_for(demo if demo.endswith("/") else demo + "/")
    if case is None:
        return None
    domain, opts = case
    return {a["key"] for a in json.loads(_dm.domain_list(domain, opts))["algos"]}


def test_demo_algo_resolves_in_domain_registry():
    """实测级问题域条目：demo_algo（缺省回退 slug）必须能选中目标域演示下拉。"""
    n = 0
    for s in SOLVES:
        if s["tier"] != "实测" or not s.get("demo"):
            continue
        reg = _registry_for(s["demo"])
        if reg is None:
            continue
        da = s.get("demo_algo") or s["algo"]
        assert da in reg, \
            f"{s['algo']}→{s['problem']}: {da} 不在 {s['demo']} 域注册表 {sorted(reg)}"
        n += 1
    assert n >= 25, f"切域协议覆盖条目数异常 {n}"


def test_demo_algo_only_on_problem_domain_demos():
    """demo_algo 只允许出现在问题域演示条目上；TSP 首页条目走 PAGE_ALGO 注入，不混协议。"""
    for s in SOLVES:
        if "demo_algo" in s:
            assert _registry_for(s.get("demo") or "") is not None, \
                f"{s['algo']}→{s['problem']}: demo_algo 挂在了非问题域 demo 上"


def test_multiobj_ga_maps_to_wsga():
    """多目标域无 ga key（注册表是 wsga/nsga2），ga 条目必须显式声明 demo_algo=wsga。"""
    ga_mo = [s for s in SOLVES if s["algo"] == "ga" and s["problem"] == "multiobj"]
    assert ga_mo and ga_mo[0].get("demo_algo") == "wsga"


def _read(path: str) -> str:
    return open(os.path.join(ROOT, path), encoding="utf-8").read()


def test_built_pages_carry_algo_param_links():
    """构建产物抽查：映射卡/roster 的直达演示链接带 ?algo=<key> 上下文。"""
    cases = [
        ("algo/f1-ea/ga/index.html", "/problem/knapsack/index.html?algo=ga"),
        ("algo/f3-phys/sa/index.html", "/problem/knapsack/index.html?algo=sa"),
        ("algo/f2-si/pso/index.html", "/problem/continuous/index.html?algo=pso"),
        ("problem/knapsack/index.html", "/problem/knapsack/index.html?algo=sa"),
        ("problem/multiobj/index.html", "/problem/multiobj/index.html?algo=wsga"),
    ]
    for path, frag in cases:
        assert frag in _read(path), f"{path} 缺切域链接 {frag}"


def test_domain_page_js_reads_algo_param():
    """前端引擎必须实现协议（读 query/PAGE_ALGO），否则链接带了参数也没人消费。"""
    js = _read("js/domain_page.js")
    assert "URLSearchParams" in js and "PRESELECT" in js
    assert "applyPreselect" in js and "autoStarted" in js


def test_domain_page_step_export_parity():
    """2026-09-28 用户裁定补齐：问题页引擎（domain_page.js）必须与 algo 页能力对齐——
    单步 + 导出 PNG（图像/曲线）+ 导出 CSV，首页「所有演示支持导出 PNG/JSON/CSV + 单步」宣称的落地证据。"""
    js = _read("js/domain_page.js")
    # 实现：单步模式开关（started 回包不自动连跑）+ 三个导出函数 + 下载工具
    for fn in ("singleStep", "singleMode", "exportVizPng", "exportConvPng",
               "exportHistoryCsv", "domDownloadCanvas"):
        assert fn in js, f"domain_page.js 缺 {fn} 实现"
    # 绑定：按钮必须真的接到函数（防「有按钮无绑定」空转）
    for bind in ('$("btnStep").onclick = singleStep', '$("btnPngDom").onclick = exportVizPng',
                 '$("btnConvDom").onclick = exportConvPng', '$("btnCsvDom").onclick = exportHistoryCsv'):
        assert bind in js, f"domain_page.js 缺绑定 {bind}"
    # CSV 导出必须带元信息头 + 表头（进表格软件可溯源）
    assert "iter,best,cur" in js and "# domain=" in js


def test_domain_pages_have_step_export_buttons():
    """构建产物抽查：全部求解域页控制栏必须有单步与三个导出按钮（模板级保证）。"""
    pages = ["problem/knapsack/index.html", "problem/continuous/index.html",
             "problem/sat/index.html", "problem/multiobj/index.html",
             "problem/maop/index.html", "problem/misindep/index.html",
             "problem/jss/index.html"]
    for pid in ("btnStep", "btnPngDom", "btnConvDom", "btnCsvDom"):
        for path in pages:
            assert pid in _read(path), f"{path} 缺按钮 {pid}"

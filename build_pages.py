# -*- coding: utf-8 -*-
"""静态站生成器：把「算法内容」和「页面骨架」分开维护，一键生成全部页面。

为什么用生成器而不是手写 7 份 HTML：
改一次导航、改一次样式，手写就要改 7 遍，而且一定会漏。
内容放在本文件顶部的 ALGOS 里，骨架在 TEMPLATE 里，跑一次全部同步。

用法：
    python build_pages.py
然后：
    python -m http.server 8000      # 打开 http://localhost:8000
"""
import io
import json
import os
import re

import seo_enhance
import i18n_pages
from functools import lru_cache
from typing import Dict, List

ROOT = os.path.dirname(os.path.abspath(__file__))
# 站点根 URL（canonical / Open Graph / sitemap 用）。部署地址确定后用环境变量传入，例如
#   SWARM_SITE_URL=https://<user>.github.io/<repo> python build_pages.py
# 留空（默认）时不输出 canonical / og:url / og:image / sitemap.xml，页面内链全是相对路径，放在任何子路径下都能用。
SITE = os.environ.get("SWARM_SITE_URL", "").strip().rstrip("/")

# S1-2 数据/内容分离：实测数据迁往 data/bench.json，算法页内容迁往 data/algos.json
with io.open(os.path.join(ROOT, "data", "bench.json"), encoding="utf-8") as _f:
    BENCH = json.load(_f)

# 算法页内容全部迁往 data/algos.json（单一事实来源）——改内容改 JSON，改骨架改本文件
with io.open(os.path.join(ROOT, "data", "algos.json"), encoding="utf-8") as _f2:
    ALGOS: List[Dict] = json.load(_f2)

# 全站文案统一引用这里，禁止手写「五种 / 45 个」——45 算法时代残留文案的教训（2026-09-26 主播走查）
N_ALGOS = len(ALGOS)

# 算法分类的运行时副本必须在 import domains 之前生成（domains/solvers 会 import taxonomy）
import sys as _sys_tx
_sys_tx.path.insert(0, os.path.join(ROOT, "tools"))
import gen_taxonomy as _gen_taxonomy  # noqa: E402
_gen_taxonomy.main()

# 域算法数数据派生（文案数字铁律 2026-09-28）：首页/导航的域数字随注册表自动同步
import sys as _sys_pd
if os.path.join(ROOT, "py") not in _sys_pd.path:
    _sys_pd.path.insert(0, os.path.join(ROOT, "py"))
import domains as _dom_pd
N_KS = len(_dom_pd._KS_ALGOS)
N_GC = len(_dom_pd._GC_ALGOS)
N_BP = len(_dom_pd._BP_ALGOS)
N_DOMAINS = len(_dom_pd._DOMAINS)  # 覆盖矩阵口径=全部域（含多目标）

import problem_groups  # noqa: E402  问题分类（Ⅰ-Ⅺ + 开放登记）的单一来源 data/problem_groups.json

# S2-B 家族轴：家族定义迁往 data/families.json；算法挂家族父标签，URL 进家族目录
with io.open(os.path.join(ROOT, "data", "families.json"), encoding="utf-8") as _f3:
    FAMILIES: List[Dict] = json.load(_f3)
FAM_BY_ID = {f["id"]: f for f in FAMILIES}
FAM_DIR_BY_ID = {f["id"]: f["dir"] for f in FAMILIES}
FAM_OF = {a["slug"]: a["family"] for a in ALGOS}
# 家族重整后迁移的算法页（旧目录 → 新目录），build 为旧地址生成重定向桩
with io.open(os.path.join(ROOT, "data", "moved_pages.json"), encoding="utf-8") as _f3m:
    MOVED_PAGES: List[Dict] = json.load(_f3m)

# S3 问题轴：问题页数据（背包变体子页 + P3/P8 类页），单一事实源 data/problems.json
with io.open(os.path.join(ROOT, "data", "problems.json"), encoding="utf-8") as _f4:
    PROBLEMS: Dict = json.load(_f4)

# 可跑问题页计数（2026-09-27 毒舌走查 P0：文案数字必须数据派生，β3 铁律）——
# 5 大域页（knapsack/continuous/multiobj/graphcolor/binpack）+ 背包变体页（VARIANT_DEMO）
# + 类页带 demo（CLASS_DEMO：assignment/qubo）+ 抽象类型页带 demo（status=page 且有 ABSTRACT_DEMO 配置）
import pages_domains as _pd_mod  # noqa: E402  模块自身会注入 py/ 路径并带出 demo 配置
_at_page_ids = {t["id"] for t in PROBLEMS.get("abstract_types", []) if t.get("status") == "page"}
N_SOLVER_PAGES = (5 + len(PROBLEMS.get("knapsack_variants", []))
                  + len(_pd_mod.CLASS_DEMO)
                  + len(_at_page_ids & set(_pd_mod.ABSTRACT_DEMO)))
N_REDUCTION_ENTRIES = len(PROBLEMS.get("abstract_types", []))


def algo_url(slug: str) -> str:
    """算法页 URL：/algo/<家族目录>/<基础名>/（slug 去 -tsp 后缀，架构 v2 §8）"""
    return f"/algo/{FAM_DIR_BY_ID[FAM_OF[slug]]}/{slug[:-4]}/"


en_summary_html = i18n_pages.en_summary


def _lead_clip(a: Dict) -> str:
    """卡片上的一句话：中文 lead 截断；有英文一句话（tagline_en）时挂 data-en，英文模式下整句替换。"""
    clipped = _clip_html(a["lead"], 38)
    en = a.get("tagline_en")
    if not en:
        return clipped
    return f'<span data-en="{en.replace(chr(34), "&quot;")}">{clipped}</span>'


def algo_card_html(a: Dict) -> str:
    return (f'<a class="card" href="{algo_url(a["slug"])}">'
            f'<span class="ico">{ICO.get(a["key"], "⚙")}</span>'
            f'<b>{a["name"]}</b><span>{_lead_clip(a)}</span>'
            f'<span class="arrow">→</span></a>')


def family_box(slug: str) -> str:
    """算法页「所在家族」盒：家族入口 + 同族成员 chips（family-tree 迷你版）。"""
    fam = FAM_BY_ID[FAM_OF[slug]]
    chips = [f'<a class="chip" href="{algo_url(a["slug"])}">{a["name"]}</a>'
             for a in ALGOS if a["slug"] != slug and a["family"] == fam["id"]]
    chips_s = " ".join(chips) or '<span class="hint">本家族成员页陆续收录中</span>'
    return (f'<div class="fambox"><p class="hint">所在家族：'
            f'<a href="/algo/{fam["dir"]}/"><b>{fam["name"]}</b></a> —— {fam["oneliner"]}'
            f'</p><div class="chips">{chips_s}</div></div>')


def redirect_stub(target: str, title: str, depth: int = 2) -> str:
    """旧 URL 重定向桩：meta refresh + JS replace + canonical，三重保障不断链。
    meta/JS 必须用相对路径——file:// 下绝对路径 /xxx/ 会落到文件系统根直接死跳
    （2026-09-26 工程用户走查 P0）；canonical 面向搜索引擎保留绝对 URL。
    depth = 桩所在目录的深度（algo/<slug>/ 为 2；algo/<旧家族>/<slug>/ 为 3），决定相对前缀 ../ 的个数。"""
    rel = "../" * depth + target.lstrip("/")
    if rel.endswith("/"):
        rel += "index.html"
    return ('<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n'
            '<meta name="robots" content="noindex">\n'
            f'<meta http-equiv="refresh" content="0; url={rel}">\n'
            f'<link rel="canonical" href="{SITE}{target}">\n'
            f'<title>{title}（已迁移）</title>\n'
            f'<script>location.replace("{rel}");</script>\n'
            '</head>\n<body>'
            f'<div class="crumbs"><a href="/">首页</a> · {title}</div>'
            f'<p>页面已迁移至 <a href="' + target + '">' + target + '</a>…</p></body>\n</html>\n')

# S8-B 层级导航（架构 v2 §1：算法是算法、问题是问题、科普是科普）
# 一级三大板块：算法 ▾ / 问题 ▾ / 科普 ▾；二级=家族或问题类；三级=具体算法或具体问题页。
# 全部从数据层动态渲染：FAMILIES/ALGOS（算法轴）、PROBLEMS（问题轴）、meta.json（元层科普），禁止硬编码条目。
EDU_LINKS = [("/encyclopedia/", "百科全书"), ("/matrix/", "交叉矩阵"),
             ("/applications/", "应用地图")]
# 写给想参与维护/扩展本站的人（不是写给读者的内容）：导航里单独分组，页面顶部也有说明条
CONTRIB_LINKS = [("/coverage/", "覆盖看板"), ("/components/", "组件库"), ("/discovery/", "候选发现池")]
# S8-B 问题板块十大抽象类导航（F 期）：列=抽象类（罗马编号），列内=枢纽页 + 该类内容页 +
# 该类词条缩进（→ 归约页全谱锚点）。类→枢纽静态声明（枢纽页是站点骨架），页/词条成员全从
# problems.json abstract_types 派生，禁止硬编码条目。
PROB_NAV_GROUPS = [  # (group, 枢纽 href 或 None, 枢纽标题)
    ("sequencing", "/problem/tsp/", "旅行商问题 TSP"),
    ("subset", "/problem/knapsack/", "背包问题枢纽"),
    ("assignment", "/problem/assignment/", "分配与选址"),
    ("partition", "/problem/binpack/", "装箱问题"),
    ("coloring", "/problem/graphcolor/", "图着色"),
    ("logic", "/problem/qubo/", "QUBO 与密码类"),
    ("continuous", "/problem/continuous/", "连续优化"),
    ("multiobj", "/problem/multiobj/", "多目标优化"),
    ("location", "/problem/uflp/", "设施选址 UFLP"),
    ("timetabling", None, "排课与排班（纯词条）"),
    ("network", None, "图与网络流（词条与多项式可解对照）"),
    ("open", None, "开放登记（优化场景与应用专题）"),
]
PROB_NAV_LABEL = problem_groups.NAV  # 来源：data/problem_groups.json

# TSP 枢纽页（/problem/tsp/）专属演示横幅：首页即引擎（全站算法巡回演示），枢纽页给正式入口
TSP_DEMO_BANNER = (
    '<div class="fambox"><p class="hint">🗺️ <b>本站旗舰 · 首页即引擎</b>'
    f'——TSP 是本站 {N_ALGOS} 个算法端点的公共基准域：首页内置完整巡回求解动画（随机实例、逐代收敛、成绩卡对比），'
    '本页是它在问题轴的正式词条与成绩单档案。</p></div>\n'
    '<div class="fambox"><div class="chips">'
    '<a class="chip" href="/index.html#tool-root"><b>▶ 去首页跑巡回演示</b>&nbsp;30/60/100 城实时动画</a>'
    '</div></div>')

with io.open(os.path.join(ROOT, "data", "meta.json"), encoding="utf-8") as _f5:
    META_PAGES: List[Dict] = json.load(_f5)["pages"]

# P1 映射层：算法↔问题映射 + 问题归约，单一事实源 data/mapping.json
# （反向查询 problem→algos 构建时派生，不存两份）
with io.open(os.path.join(ROOT, "data", "mapping.json"), encoding="utf-8") as _f6:
    MAPPING: Dict = json.load(_f6)
PROBLEM_INDEX: Dict[str, Dict] = MAPPING["problem_index"]
ALGO_SOLVES: List[Dict] = MAPPING["algo_solves"]
REDUCTIONS: List[Dict] = MAPPING["reductions"]
GRAPH_POS: Dict[str, List[int]] = MAPPING.get("graph", {}).get("pos", {})
GRAPH_VIEW: List[int] = MAPPING.get("graph", {}).get("view", [1000, 620])
ALGO_BY_KEY: Dict[str, Dict] = {a["key"]: a for a in ALGOS}
_TIERS = ("实测", "文献", "推测")
SOLVED_BY: Dict[str, List[Dict]] = {}
for _e in ALGO_SOLVES:
    SOLVED_BY.setdefault(_e["problem"], []).append(_e)


def demo_href(demo: str, algo: str = "") -> str:
    """映射 demo 字段 → 页面锚链。目录式 URL 补 index.html 再挂 #demo
    （write() 的相对化改写只对以 / 结尾的目录链接补 index.html，带锚点的不会补）。
    P2 切域协议：问题域演示页带 ?algo=<域内key>，落地自动选中并可自动开跑；
    仅在域内算法注册表能验证该 key 时挂参（不生成落地后选不出来的死链）。"""
    if not demo:
        return ""
    if not demo.endswith("/"):
        return demo
    # 算法页的运行面板锚是 #tool-root（#demo 只存在于域演示页）；算法页自带
    # 选中算法，不挂 ?algo= 切域参——挂了会生成落地后无意义的参数链。
    if demo.startswith("/algo/"):
        return demo + "index.html#tool-root"
    qs = ""
    if algo and demo != "/":
        dom = demo.strip("/").split("/")[-1]
        keys = _domain_algo_keys().get(dom)
        if keys is None or algo in keys:
            qs = "?algo=" + algo
    return demo + "index.html" + qs + "#demo"


@lru_cache(maxsize=1)
def _domain_algo_keys() -> Dict[str, set]:
    """py/domains.py 五域注册表的 {domain: 算法key集合}（P2 切域协议校验用）。"""
    import sys
    sys.path.insert(0, os.path.join(ROOT, "py"))
    import domains as _dm
    return {d: {a["key"] for a in json.loads(_dm.domain_list(d))["algos"]}
            for d in ("knapsack", "continuous", "multiobj", "graphcolor", "binpack")}


def _tier_cls(tier: str) -> str:
    return {"实测": "t-shi", "文献": "t-wen", "推测": "t-ce"}.get(tier, "t-ce")


_MAP_SHOWN = 15  # 算法页映射卡直接展开的行数；更多的折叠


def mapping_card_html(algo_key: str) -> str:
    """算法页「还能解什么问题」映射卡（P1）。仅渲染 mapping.json 声明的组合，不编造。"""
    entries = [e for e in ALGO_SOLVES if e["algo"] == algo_key]
    if not entries:
        return ""
    rows = []
    for e in entries:
        p = PROBLEM_INDEX[e["problem"]]
        if e["problem"] == "tsp":
            # 本算法页的主问题就是 TSP：渲染为页内锚点，不做"还能解 TSP→外链"的滑稽跳转
            rows.append(
                f'<div class="map-row"><span class="map-name"><a href="#tool-root">{p["name"]}</a>'
                f'<span class="tier {_tier_cls(e["tier"])}">{e["tier"]}</span></span>'
                f'<span class="map-how">本页即 {p["name"]} 求解页（{e["how"]}'
                f'）——运行面板与成绩卡见上方</span>'
                f'<span class="map-act"><a class="chip mini" href="#tool-root">▶ 演示</a></span></div>')
            continue
        demo = (f'<a class="chip mini" href="{demo_href(e["demo"], e.get("demo_algo") or e["algo"])}">▶ 演示</a>'
                if e.get("demo") and e["tier"] == "实测" else "")
        src = f'<span class="hint">（{e["src"]}）</span>' if e.get("src") else ""
        ev = f'<div class="hint">{e["evidence"]}</div>' if e.get("evidence") else ""
        rows.append(
            f'<div class="map-row"><span class="map-name"><a href="{p["url"]}">{p["name"]}</a>'
            f'<span class="tier {_tier_cls(e["tier"])}">{e["tier"]}</span></span>'
            f'<span class="map-how">{e["how"]}{src}</span>'
            f'<span class="map-act">{demo}{ev}</span></div>')
    return ('<h2 id="map">还能解什么问题</h2>\n  <p class="hint">映射层：本算法跨问题域的落地记录。'
            '「实测」= 本站问题页有可跑演示与成绩；「文献」= 有原始文献出处，本站未实测。'
            '归约关系见 <a href="/problem/reductions/">问题归约页</a>。</p>\n  <div class="maplist">'
            + "\n".join(rows[:_MAP_SHOWN])
            + (f'\n  <details><summary>其余 {len(rows) - _MAP_SHOWN} 个问题</summary>\n' + "\n".join(rows[_MAP_SHOWN:])
               + "\n  </details>" if len(rows) > _MAP_SHOWN else "")
            + "\n  </div>")


def roster_html(problem_id: str) -> str:
    """问题页「哪些算法能治」roster（P1）：由 algo_solves 派生，tier 诚实分级。"""
    entries = SOLVED_BY.get(problem_id, [])
    if not entries:
        return ""
    rows = []
    for e in entries:
        a = ALGO_BY_KEY.get(e["algo"])
        if not a:
            continue
        demo = (f'<a class="chip mini" href="{demo_href(e["demo"], e.get("demo_algo") or e["algo"])}">▶ 演示</a>'
                if e.get("demo") and e["tier"] == "实测" else "")
        src = f'<span class="hint">（{e["src"]}）</span>' if e.get("src") else ""
        ev = f'<div class="hint">{e["evidence"]}</div>' if e.get("evidence") else ""
        rows.append(
            f'<div class="map-row"><span class="map-name"><a href="{algo_url(a["slug"])}">{a["name"]}</a>'
            f'<span class="tier {_tier_cls(e["tier"])}">{e["tier"]}</span></span>'
            f'<span class="map-how">{e["how"]}{src}</span>'
            f'<span class="map-act">{demo}{ev}</span></div>')
    return ('<h2 id="roster">哪些算法能治</h2>\n  <p class="hint">从映射层派生（'
            '<a href="/problem/reductions/">问题归约</a> · <a href="/matrix/">交叉矩阵</a>）。'
            '「实测」成绩来自本页下方实测参考表。</p>\n  <div class="maplist">'
            + "\n".join(rows) + "\n  </div>")


def reduction_neighbors_html(problem_id: str) -> str:
    """问题页底部「归约邻居」一行（P1）：与归约页互链。"""
    rel = [r for r in REDUCTIONS if r["from"] == problem_id or r["to"] == problem_id]
    if not rel:
        return ""
    chips = []
    for r in rel:
        other = r["to"] if r["from"] == problem_id else r["from"]
        arrow = "→" if r["from"] == problem_id else "←"
        chips.append(f'<a class="chip" href="/problem/reductions/" title="{r["note"]}">'
                     f'{arrow} {r["type"]} · {PROBLEM_INDEX[other]["name"]}</a>')
    return ('<p class="hint" style="margin-top:14px">归约邻居：' + " ".join(chips)
            + '　（完整关系图见 <a href="/problem/reductions/">问题归约页</a>）</p>')


_RED_TYPE_COLOR = {"归约": "#7c5cff", "等价": "#059669", "特例": "#d97706", "推广": "#2563eb"}
_RED_TYPE_SLUG = {"归约": "red", "等价": "eq", "特例": "case", "推广": "gen"}


def _reductions_graph_html() -> str:
    """P3：归约有向图（零依赖内联 SVG）。数据=data/mapping.json 的 graph.pos + reductions；
    四色边=四种关系类型，节点可点击跳问题页，边悬停看归约说明与出处。
    只画参与归约的节点（无边孤儿在图下文字列出）；边统一向质心外弯，
    双向边对（等价）强制反向分成两弧。"""
    vw, vh = GRAPH_VIEW
    cx0, cy0 = vw / 2, vh / 2
    participating = {r["from"] for r in REDUCTIONS} | {r["to"] for r in REDUCTIONS}
    pairs = {(r["from"], r["to"]) for r in REDUCTIONS}
    markers = "".join(
        f'<marker id="arr-{sl}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        f'markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="{_RED_TYPE_COLOR[t]}"/></marker>'
        for t, sl in _RED_TYPE_SLUG.items())
    edges = []
    for r in REDUCTIONS:
        x1, y1 = GRAPH_POS[r["from"]]
        x2, y2 = GRAPH_POS[r["to"]]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        dx, dy = x2 - x1, y2 - y1
        dist = max((dx * dx + dy * dy) ** 0.5, 1)
        # 双向边对（存在反向边）按字典序强制反向；其余一律向质心外弯
        nx, ny = -dy / dist, dx / dist
        if (r["to"], r["from"]) in pairs:
            sign = 1 if r["from"] < r["to"] else -1
        else:
            sign = 1 if nx * (mx - cx0) + ny * (my - cy0) > 0 else -1
        cx, cy = mx + nx * sign * 42, my + ny * sign * 42
        color = _RED_TYPE_COLOR[r["type"]]
        sl = _RED_TYPE_SLUG[r["type"]]
        tip = f'{PROBLEM_INDEX[r["from"]]["name"]} → {PROBLEM_INDEX[r["to"]]["name"]}（{r["type"]}）：{r["note"]}｜{r["src"]}'
        edges.append(f'<path class="rededge" d="M{x1},{y1} Q{cx:.0f},{cy:.0f} {x2},{y2}" fill="none" '
                     f'stroke="{color}" stroke-width="2" marker-end="url(#arr-{sl})">'
                     f'<title>{tip}</title></path>')
    nodes = []
    for pid in sorted(participating):
        x, y = GRAPH_POS[pid]
        p = PROBLEM_INDEX[pid]
        w = max(64, len(p["name"]) * 15 + 26)
        nodes.append(
            f'<a href="{p["url"]}"><g class="rednode"><rect x="{x - w // 2}" y="{y - 17}" '
            f'width="{w}" height="34" rx="10" style="fill:var(--surface);stroke:var(--accent);stroke-width:1.4"/>'
            f'<text x="{x}" y="{y + 5}" text-anchor="middle" font-size="13" '
            f'style="fill:var(--ink)">{p["name"]}</text></g></a>')
    legend = " ".join(
        f'<span class="redlg"><i style="background:{c}"></i>{t}</span>'
        for t, c in _RED_TYPE_COLOR.items())
    # 只有在图里有位置的节点才算「未入图」；只靠算法映射行出现在问题索引里的页面不属于归约图这一层
    orphans = [PROBLEM_INDEX[p]["name"] for p in PROBLEM_INDEX if p in GRAPH_POS and p not in participating]
    orphan_html = (f'<p class="hint">未入图 {len(orphans)} 题（暂无归约关系声明）：'
                   + " · ".join(orphans)
                   + '——背包变体间谱系见 <a href="/problem/knapsack/">背包枢纽页</a>。</p>') if orphans else ""
    return (f'<div class="redgraph"><svg viewBox="0 0 {vw} {vh}" role="img" '
            f'aria-label="问题归约有向图">{"".join(edges)}{"".join(nodes)}'
            f'<defs>{markers}</defs></svg>'
            f'<div class="redlegend">{legend}'
            f'<span class="hint">悬停边看归约说明 · 点节点进问题页</span></div>{orphan_html}</div>')


def _entries_spectrum_html() -> str:
    """归约页「全谱词条」段：abstract_types 中 status=entry 的词条级登记（只登记词条，不建页）。"""
    entries = [t for t in PROBLEMS.get("abstract_types", []) if t.get("status") == "entry"]
    if not entries:
        # 所有抽象类型都已有独立页面：归约页只剩归约图
        n_pages = len([x for x in PROBLEMS.get("abstract_types", []) if x.get("status") == "page"])
        return ('<h2>全谱词条 · 均有独立页面</h2>\n'
                f'<div class="box">{n_pages} 条抽象类型词条<b>都有独立页面</b>，每页带在线求解实例。'
                '本页保留<b>归约关系图</b>：什么问题能变成什么问题。</div>')
    group_name = problem_groups.LABEL
    secs = []
    for g in problem_groups.ORDER:
        members = [t for t in entries if t.get("group") == g]
        if not members:
            continue
        items = "".join(
            f'<div class="fambox entrybox" id="e-{t["id"]}" style="margin:.6em 0"><p><b>{t["name"]}'
            f'（{t["en"]}{(", " + t["abbr"]) if t.get("abbr") else ""}）</b> '
            f'<span class="hint">归类锚 {t["gj"]}</span><br>'
            f'{t["note"]}</p>'
            f'<ul class="src">' + "".join(f"<li>{s}</li>" for s in t["sources"]) + "</ul></div>"
            for t in members)
        secs.append(f'<h3 id="grp-{g}">{group_name[g]}</h3>\n  {items}')
    return (f'<h2>全谱词条（{len(entries)} 条 · 只登记不建页）</h2>\n'
            '<p class="hint">你从导航点进来的「↳ 词条」就落在这里：这类问题已登记进抽象类型谱，'
            '但还没有独立页面——要么属于本站冻结的应用域（VRP、车间调度等），要么暂未达到建页标准，'
            '定义就在下方对应小节。想动手求解 → 顶部「问题 ▾」里带 ▶ 的都是可跑的真页面；'
            '想系统学 → <a href="/encyclopedia/#intro">百科总纲 · 三分钟入门</a>。'
            '顺带一个人话例子：旅行商 TSP 其实是二次指派 QAP 的特例——把城市间距离矩阵当作 QAP 的'
            '流向矩阵，剩下的问题就是找一条最短回路（见归约图 TSP→指派边）。</p>\n'
            '<p class="hint">📍 <b>编号图例</b>：词条旁的「归类锚」编号（如 A1.1、A6）是<b>本站自建的类目参照'
            '体系</b>——字母借 Garey &amp; Johnson (1979) 附录的类目划分（A1 图论 / A2 网络设计 / '
            'A3 集合与划分 / A4 存储与检索 / A5 排序与调度 / A6 数学规划 / A9 逻辑），'
            '小数编号是本站组内锚点，<b>不是</b> G&amp;J 书里的经典条目号，所以多个词条共用同一锚属正常；'
            '连续优化、多目标等 1979 年后的新形态在 G&amp;J 中没有原始条目，取语义最近的类目作锚。'
            '各词条正文与出处栏出现的 GT1 / ND29 / SP1 / SS2 等才是 G&amp;J 书内经典条目号，两套编号请勿混读。</p>\n'
            + "\n  ".join(secs))


def reductions_inner_html() -> str:
    """/problem/reductions/ 页正文（P1）：问题↔问题的归约/等价/特例/推广关系表。"""
    order = ["归约", "等价", "特例", "推广"]
    secs = []
    for t in order:
        rel = [r for r in REDUCTIONS if r["type"] == t]
        if not rel:
            continue
        rows = "".join(
            f'<tr><td><a href="{PROBLEM_INDEX[r["from"]]["url"]}">{PROBLEM_INDEX[r["from"]]["name"]}</a></td>'
            f'<td class="num">{t}</td>'
            f'<td><a href="{PROBLEM_INDEX[r["to"]]["url"]}">{PROBLEM_INDEX[r["to"]]["name"]}</a></td>'
            f'<td>{r["note"]}</td><td class="hint">{r["src"]}</td></tr>'
            for r in rel)
        secs.append(f'<h2>{t}（{len(rel)} 条）</h2>\n  <div class="tablewrap"><table class="redtab">'
                    f'<tr><th>从</th><th>关系</th><th>到</th><th>怎么变</th><th>出处</th></tr>{rows}'
                    f'\n  </table></div>')
    return f"""
  <div class="crumbs"><a href="/">首页</a> · 问题 · 问题归约</div>
  <div class="hero">
    <h1>问题 ↔ 问题 <span class="grad">归约关系图</span></h1>
    <div class="sub">「什么问题能变成什么问题」的地图：归约（A ≤ₚ B，会解 B 就会解 A）、等价、特例与推广。选问题先查这张图——你的问题很可能是某个经典问题的化身。</div>
  </div>
  <p>元启发式文献里新问题层出不穷，但底层互相归约。看懂两条路：<b>特例</b>（你的问题是经典问题的特殊情况，直接用它的算法）与<b>归约</b>（你的问题含经典问题作为特例，难度下限被它锁死）。每条关系带原始文献出处。</p>
  <h2>关系图</h2>
  {_reductions_graph_html()}
  {''.join(secs)}
  {_entries_spectrum_html()}
  <h2>相关页面</h2>
  <p class="hint"><a href="/encyclopedia/">百科总纲（问题分类四连问）</a> · <a href="/matrix/">交叉矩阵（算法×问题）</a> · <a href="/problem/knapsack/">背包变体谱系（特例与推广的现场教学）</a></p>
"""

# ---------- 日夜主题（v0.3） ----------
# 注意：下面两段含 JS 大括号，不能放进 .format() 模板。
# 模板里用 <!--THEME_HEAD--> / <!--THEME_TAIL--> 占位，main() 里在 format 之后 replace 注入。
NAV_TOGGLE_BTN = ('<button id="langToggle" class="theme-btn lang-btn" title="Switch to English / 切换到英文" aria-label="Language">EN</button>'
                  '<button id="themeToggle" class="theme-btn" title="切换日间/夜间模式" aria-label="切换主题">🌙</button>')

THEME_HEAD = """<script src="/js/i18n.js"></script>
<script>
(function(){var t=null;try{t=localStorage.getItem("theme")}catch(e){}
if(!t)t=(window.matchMedia&&matchMedia("(prefers-color-scheme: dark)").matches)?"dark":"light";
document.documentElement.setAttribute("data-theme",t);})();
</script>
<link rel="stylesheet" href="/css/site_search.css">"""

THEME_TAIL = """<script>
(function(){
  var b=document.getElementById("themeToggle");if(!b)return;
  var root=document.documentElement;
  function sync(){b.textContent=root.getAttribute("data-theme")==="dark"?"☀️":"🌙";}
  b.onclick=function(){
    var n=root.getAttribute("data-theme")==="dark"?"light":"dark";
    root.setAttribute("data-theme",n);
    try{localStorage.setItem("theme",n)}catch(e){}
    sync();
    window.dispatchEvent(new CustomEvent("themechange"));
  };
  sync();
})();
(function(){
  if(location.protocol!=="file:")return;
  var d=document.createElement("div");
  d.className="file-warn";
  d.innerHTML="⚠️ 当前通过 <b>file://</b> 直接打开：页面浏览可用，但<b>交互演示（运行算法）需要经 http 访问</b>——请在项目目录双击 <code>start_server.bat</code>（或运行 <code>python serve.py</code>），再访问 http://localhost:8000 。";
  document.body.insertBefore(d,document.body.firstChild);
})();
/* S8-C 触屏（hover 不可用）：点 .dd-btn 展开/收起面板，不再直接跳走（P1-2 修复）。
   桌面 hover 环境不拦截（matchMedia('(hover: hover)') 为真时不处理）。 */
(function(){
  document.querySelectorAll(".dd-btn").forEach(function(b){
    b.addEventListener("click", function(e){
      if(window.matchMedia("(hover: hover)").matches) return;  // 桌面 hover 环境不拦截
      e.preventDefault();
      var dd=b.parentElement;
      var wasOpen=dd.classList.contains("open");
      document.querySelectorAll(".dd.open").forEach(function(o){ o.classList.remove("open"); });
      if(!wasOpen) dd.classList.add("open");
    });
  });
  document.addEventListener("click", function(e){
    if(!e.target.closest(".dd")) document.querySelectorAll(".dd.open").forEach(function(o){ o.classList.remove("open"); });
  });
})();
/* 长表词条过滤（planned>20 的家族页，P1-3）：输入即按行文本 includes 过滤 + 计数 */
(function(){
  document.querySelectorAll(".plfilter").forEach(function(inp){
    var wrap=inp.closest(".plwrap");
    var tbl=wrap.parentElement.querySelector(".pltbl table");
    var cnt=wrap.querySelector(".plcount");
    if(!tbl||!cnt) return;
    var total=parseInt(inp.getAttribute("data-plcount"),10)||tbl.querySelectorAll("tr").length-1;
    var trs=tbl.querySelectorAll("tr");
    inp.addEventListener("input", function(){
      var q=inp.value.trim().toLowerCase(), n=0;
      for(var i=1;i<trs.length;i++){
        var hit=!q||trs[i].textContent.toLowerCase().indexOf(q)>=0;
        trs[i].style.display=hit?"":"none"; if(hit) n++;
      }
      cnt.textContent="显示 "+n+"/"+total;
    });
  });
})();
</script>
<script src="/js/site_search.js"></script>"""

def inject_theme(html: str) -> str:
    """format 之后注入主题脚本（避免大括号与 str.format 冲突）"""
    html = html.replace("<!--THEME_HEAD-->", THEME_HEAD)
    html = html.replace("<!--THEME_TAIL-->", THEME_TAIL)
    html = html.replace("<!--THEME_BTN-->", NAV_TOGGLE_BTN)
    return html

TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<!--THEME_HEAD-->
<link rel="stylesheet" href="/css/style.css">
<link rel="canonical" href="{site}{path}">
<script type="application/ld+json">{ldjson}</script>
</head>
<body>
<a class="skip-link" href="#main">跳到主内容</a>
<nav class="nav"><div class="nav-inner">
  <a class="brand" href="/"><span class="logo">🐝</span>群智能算法百科</a>
  <div class="nav-links">
  {navlinks}
  </div>
  <!--THEME_BTN-->
</div></nav>

<div class="wrap" id="main" role="main">
  <div class="hero" style="padding-top:6px">
    <div class="crumbs"><a href="/algo/{fam_dir}/">{fam_name}</a> · 家族成员</div>
    <h1 style="font-size:26px;margin-bottom:6px">{h1}</h1>
    <div class="sub">{lead}</div>
    {en_summary}
  </div>

  <div class="demo-grid">
    <section class="demo-pane" id="demoPane">
      <div class="demo-head"><h2>在线演示</h2><span class="live-badge">● 本机浏览器运行 · 数据不上传</span></div>
      <div id="tool-root"><div class="tool-fallback">⏳ 交互演示正在加载…<br><small>若长时间停留在此，说明脚本被浏览器拦截（直接双击 HTML 文件以 file:// 打开时会出现）。请在项目目录运行 <code>python serve.py</code>（或双击 <code>start_server.bat</code>），访问 <b>http://localhost:8000</b> 后即可正常使用。</small></div></div>
    </section>
    <aside class="side-pane">
      {run_card}
      {quick_card}
      {bench_card}
      {use_card}
    </aside>
  </div>

  {family_box}
  {intro}
  {map_card}

  <h2 id="how">算法原理</h2>
  <ol>
    {principle}
  </ol>

  <h2 id="params">参数说明</h2>
  <div class="tablewrap">
  <table>
    <tr><th>参数</th><th>默认</th><th>含义</th></tr>
    {params}
  </table>
  </div>

  <h2 id="bench">实测性能</h2>
  <p class="hint">{bench_caption}。另注：45 个算法全部挂了 memetic 2-opt 组件（这是它们能打的共同底座）——横向比的是<strong>框架增益</strong>，不是「谁发明的算法更聪明」。</p>
  <div class="box"><strong>「真在优化吗」自查三问（写你自己的算法时也请照做）</strong>：① 关掉全部局部搜索，纯算法还比初始解（NN）进步吗？② 1 代→200 代的曲线是真实下降还是平线？③ 收敛到局部最优后，扰动还能踢出新结构吗？——三条全过才算「算法在学」，任何一条不过就是<strong>假跑</strong>（曲线在降，但下降不是算法本身的功劳；这是本站收录算法的硬性要求）。</div>
  <div class="tablewrap">
  <table>
    <tr><th>算法</th><th class="num">30 城市</th><th class="num">60 城市</th><th class="num">100 城市</th></tr>
    {bench}
  </table>
  </div>
  <p class="hint">同一台机器、同一随机实例、同为 200 代的结果。算法是随机的，换种子结果会浮动，别把 1% 的差距当结论。</p>

  {depth}

  <h2 id="faq">常见问题</h2>
  {faq}

  <h2>相关页面</h2>
  {rel_list}

  <p class="hint">原始文献：{paper}</p>
</div>

<footer>
  <span class="fbrand">群智能算法百科</span>
  <span class="ver">v0.1.0</span>
  <span>算法由 Pyodide 在浏览器本地运行，数据不上传 · 源码与实现细节见项目 README</span>
</footer>

<script>window.PAGE_ALGO = "{key}";</script>
<script src="/js/compat.js"></script>
<script type="module" src="/js/tool.js"></script>
<!--ALGO_TAIL-->
<!--THEME_TAIL-->
</body>
</html>
"""

HOME = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>群智能算法百科 · {algo_count} 个元启发式算法 × 10 家族 × 全问题域在线求解</title>
<meta name="description" content="一本能「跑起来」的群智能算法百科：{algo_count} 个元启发式算法按 10 家族收录，{solver_pages} 个问题页（背包及变体/连续/多目标/图着色/装箱/指派/SAT 等）页顶即在线求解器，{entry_count} 条类型谱、应用地图与交叉矩阵。浏览器本地运行，数据不上传。">
<!--THEME_HEAD-->
<link rel="stylesheet" href="/css/style.css">
<link rel="canonical" href="{site}/">
<script type="application/ld+json">{ldjson}</script>
</head>
<body>
<a class="skip-link" href="#main">跳到主内容</a>
<nav class="nav"><div class="nav-inner">
  <a class="brand" href="/"><span class="logo">🐝</span>群智能算法百科</a>
  <div class="nav-links">
  {navlinks}
  </div>
  <!--THEME_BTN-->
</div></nav>

<div class="wrap" id="main" role="main">
  <div class="hero">
    <div class="hero-badge"><span class="dot"></span>浏览器本地运行 · 数据不上传 · 免安装</div>
    <h1>群智能算法百科<br><span class="grad">一本能「跑起来」的算法百科</span></h1>
    <div class="sub">{algo_count} 个元启发式算法 × 10 家族 × {solver_pages} 个可跑的问题页——每个算法页、每个问题页都有在线求解演示。写论文要对比图、上课要演示动画、想看算法到底怎么工作，都在这里。算法在你的浏览器里跑（Pyodide——浏览器内 Python 引擎，免安装），数据不上传。</div>
    <div class="hero-chips">
      <a class="chip" href="/encyclopedia/#intro" title="零基础先看这里">📖 不懂算法？3 分钟入门</a>
      <a class="chip" href="/demo/" title="首页即引擎的旗舰演示">▶ TSP 巡回演示</a>
      <a class="chip" href="/algo/">🧬 算法库</a>
      <a class="chip" href="/problem/">🗺️ 问题库</a>
      <a class="chip" href="/compare/">⚖️ 算法对比</a>
      <span class="chip">🌙 / ☀️ 日夜双主题</span>
    </div>
  </div>

  <h2>三条内容线</h2>
  {bench_best}
  <div class="cards">
    <a class="card" href="/algo/"><span class="ico">🧬</span><b>算法库 · {algo_count} 算法 × 10 家族</b><span>进化/群智能/物理/人类/免疫/混合/多目标/新范式/隐喻批评区/专用求解对照系——每个算法页带在线 TSP 求解、动态参数面板与踩坑记录</span><span class="arrow">→</span></a>
    <a class="card" href="/problem/"><span class="ico">🗺️</span><b>问题库 · {solver_pages} 页全求解化</b><span>0-1 背包及 10 变体 / 连续函数 / 多目标 / 图着色 5 变体 / 装箱 3 变体 / 指派选址 / QUBO / SAT——页顶即求解器，规模可自定义</span><span class="arrow">→</span></a>
    <a class="card" href="/encyclopedia/"><span class="ico">📚</span><b>科普与元层</b><span>3 分钟入门 · 百科总纲（问题分类四连问 × 七维度）· 交叉矩阵 X1-X4 · 应用地图 96 块 · 问题归约 {entry_count} 类型谱</span><span class="arrow">→</span></a>
  </div>

  <h2>怎么用本站（三步）</h2>
  <ol>
    <li><b>零基础</b>：先读<a href="/encyclopedia/#intro">三分钟入门</a>，搞懂「元启发式」到底指什么、和精确算法什么关系。</li>
    <li><b>动手跑</b>：去 <a href="/demo/">▶ 在线演示</a>跑一个 TSP 巡回（45 个算法可切换、调速、单步），或直接进任意<a href="/problem/">问题页</a>——页顶就是求解器，规模参数随便改。</li>
    <li><b>深入</b>：按<a href="/algo/">算法家族树</a>或<a href="/problem/">问题分类</a>两侧翻；<a href="/matrix/">交叉矩阵</a>把两轴连起来；<a href="/coverage/">覆盖矩阵</a>看每个域能跑的全部算法；所有演示支持导出 PNG / CSV 和可复现的结果 JSON，直接进论文或备课材料；想换成自己的数据，看<a href="/guide/">5 分钟上手</a>。</li>
  </ol>

  <h2>在线演示入口</h2>
  <p class="hint">不必先懂算法——点开就跑，全程本地计算。</p>
  <div class="cards">
    <a class="card" href="/demo/"><span class="ico">▶</span><b>TSP 巡回演示（旗舰）</b><span>30/60/100 城实时路径动画 + 收敛曲线，{algo_count} 算法可切换，支持导入自有数据、导出 PNG/JSON</span><span class="arrow">→</span></a>
    <a class="card" href="/compare/"><span class="ico">⚖️</span><b>算法对比</b><span>同一批城市交给全站 {algo_count} 个算法跑，曲线叠加、结果排名一次出，可导出 CSV</span><span class="arrow">→</span></a>
  </div>

  <h2>问题域全景</h2>
  <p class="hint">元启发式不只解 TSP——同一批算法，换编码就能换问题域。下面六个演示覆盖了变量类型的主要维度；全部 {n_domains} 域的覆盖状态见<a href="/coverage/">覆盖矩阵</a>，分类方法论见<a href="/encyclopedia/">百科总纲</a>。</p>
  <div class="cards">
    <a class="card" href="/problem/continuous/"><span class="ico">⛰️</span><b>连续函数优化</b><span>PSO/DE/GWO 的原生域：地形热力图+粒子动画，Sphere/Rastrigin/Rosenbrock/Ackley</span><span class="arrow">→</span></a>
    <a class="card" href="/problem/knapsack/"><span class="ico">🎒</span><b>0-1 背包（二进制）</b><span>二进制编码+贪心修复算子，{n} 种算法同台</span><span class="arrow">→</span></a>
    <a class="card" href="/problem/multiobj/"><span class="ico">📊</span><b>多目标优化（Pareto）</b><span>NSGA-II 前沿动画 vs 加权法坍缩的活对照</span><span class="arrow">→</span></a>
    <a class="card" href="/problem/graphcolor/"><span class="ico">🎨</span><b>图着色（组合）</b><span>排列编码换解码器：染色动画 + DSJC 硬实例，色数阶梯下降</span><span class="arrow">→</span></a>
    <a class="card" href="/problem/binpack/"><span class="ico">📦</span><b>装箱 Bin Packing（组合）</b><span>排列编码三连演：装箱动画 + 下界 LB 对照，触 LB 即最优</span><span class="arrow">→</span></a>
    <a class="card" href="/problem/assignment/"><span class="ico">🏥</span><b>分配/选址</b><span>QAP·GAP·MCLP·p-中位·充电站·急救车——把「谁放哪」讲成一族问题</span><span class="arrow">→</span></a>
    <a class="card" href="/problem/qubo/"><span class="ico">🧮</span><b>QUBO/SAT/密码</b><span>xᵀQx 统一约束通向量子退火生态；SAT 竞赛与演化密码学</span><span class="arrow">→</span></a>
    <a class="card" href="/matrix/"><span class="ico">🧭</span><b>交叉矩阵 X1-X4</b><span>家族×问题 SOTA · 编码 · 算子 · 本站实测——两轴之间的桥</span><span class="arrow">→</span></a>
    <a class="card" href="/applications/"><span class="ico">🗺️</span><b>应用地图</b><span>96 应用块 · 问题形态 9 类 ⇄ 行业 13 类双视图导航：电力/制造/医药/航天……只做索引不膨胀</span><span class="arrow">→</span></a>
    <a class="card" href="/problem/reductions/"><span class="ico">🕸️</span><b>问题归约</b><span>什么问题能变成什么问题：归约·等价·特例·推广，每条带原始文献出处</span><span class="arrow">→</span></a>
    <a class="card" href="/encyclopedia/"><span class="ico">📚</span><b>百科总纲</b><span>问题分类四连问 × 七个正交维度 × 覆盖矩阵 × 术语表</span><span class="arrow">→</span></a>
  </div>

  <h2>延伸阅读</h2>
  <div class="cards">
    {cards}
  </div>

  <h2>这个站是干什么的</h2>
  <p>给做优化方向的同学一个能直接跑、能截图、能对比的地方：写论文要对比实验图、上课要做演示动画、或者只是想看看这些算法到底怎么工作。所有实现都在浏览器里，代码开源可读，每个算法踩过的坑都写在源码注释里。</p>
  <ul>
    <li>算法在浏览器本地运行（Pyodide + Web Worker），不上传任何数据，支持导入自有数据集（JSON / CSV / TXT）</li>
    <li>日夜双主题、暂停、单步、调速、采样间隔（每 1/2/5/10 代取一点）、导出 PNG 可直接放进论文或 PPT</li>
    <li>参数面板动态生成，改一个算法的参数不需要改任何前端代码</li>
  </ul>
</div>

<footer>
  <span class="fbrand">群智能算法百科</span>
  <span class="ver">v0.1.0</span>
  <span>Pyodide + Web Worker · 源码与实现细节见项目 README</span>
</footer>

<!--THEME_TAIL-->
</body>
</html>
"""

DEMO_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TSP 巡回演示 · {algo_count} 算法同台 · 路径动画与收敛曲线</title>
<meta name="description" content="在线演示 {algo_count} 种智能优化算法求解旅行商问题(TSP)：实时路径动画与收敛曲线，支持暂停、单步、调速、采样间隔调节、导入自有数据与结果导出（PNG/JSON），附全算法实测成绩单与谱系映射表。浏览器本地运行无需安装。">
<!--THEME_HEAD-->
<link rel="stylesheet" href="/css/style.css">
<link rel="canonical" href="{site}/demo/">
<script type="application/ld+json">{ldjson}</script>
</head>
<body>
<a class="skip-link" href="#main">跳到主内容</a>
<nav class="nav"><div class="nav-inner">
  <a class="brand" href="/"><span class="logo">🐝</span>群智能算法百科</a>
  <div class="nav-links">
  {navlinks}
  </div>
  <!--THEME_BTN-->
</div></nav>

<div class="wrap" id="main" role="main">
  <div class="hero" style="padding-top:18px">
    <div class="crumbs"><a href="/">首页</a> · 演示</div>
    <h1 style="font-size:28px">TSP 巡回演示<br><span class="grad">{algo_count} 个算法同台</span></h1>
    <div class="sub">{algo_count} 种智能优化算法求解旅行商问题，实时看路径怎么一代代变短。算法在你的浏览器里跑（Pyodide——浏览器内 Python 引擎，免安装），数据不上传。</div>
    <div class="hero-chips">
      <span class="chip">🌀 粒子群 PSO</span>
      <span class="chip">🐜 蚁群 ACO</span>
      <span class="chip">🧬 遗传 GA</span>
      <span class="chip">🔥 模拟退火 SA</span>
      <span class="chip">🐺 灰狼 GWO</span>
      <span class="chip">＋ 共 {algo_count} 种可切换</span>
      <span class="chip">🌙 / ☀️ 日夜双主题</span>
    </div>
  </div>

  <h2>在线演示</h2>
  <div id="tool-root"><div class="tool-fallback">⏳ 交互演示正在加载…</div></div>

  <h2>操作指南</h2>
  <ol>
    <li>选一个算法，设定城市数与迭代次数，点「开始」。右上角 <b>🌙 / ☀️</b> 可切换夜间/日间模式（跟随系统偏好，选择会被记住）。</li>
    <li>左边看路径怎么进化，右边看收敛曲线：红线是全局最优，灰线是当代成本，绿虚线是最近邻基线（用来判断这个算法到底优化了多少）。</li>
    <li><b>采样间隔</b>可选每 1 / 2 / 5 / 10 代取一个点：曲线横轴始终按真实代数定位，采样只影响取点密度，不影响结果。</li>
    <li>想用自己的数据？点「<b>导入数据</b>」上传 JSON <code>[[x,y],...]</code> 或 CSV/TXT（每行两个数字）。数据只在你的浏览器里计算，不上传。</li>
    <li>想看清细节就拖慢速度或用「单步」；需要配图就点「导出 PNG」（路径图与收敛曲线分别导出），要原始数据就点「导出 JSON」。</li>
    <li>想横向比较，去 <a href="/compare/">算法对比页</a>：同一批城市交给全站 {algo_count} 个算法跑，曲线叠加、结果排名一次出。</li>
  </ol>

  <h2>实测性能</h2>
  <p class="hint">{bench_caption}。另注：45 个算法全部挂了 memetic 2-opt 组件（共同底座）——横向比的是<strong>框架增益</strong>；表中同值并列是多算法收敛到同一吸引盆，不是数据复制。</p>
  <div class="box"><strong>「真在优化吗」自查三问（写你自己的算法时也请照做）</strong>：① 关掉全部局部搜索，纯算法还比初始解（NN）进步吗？② 1 代→200 代的曲线是真实下降还是平线？③ 收敛到局部最优后，扰动还能踢出新结构吗？——三条全过才算「算法在学」，任何一条不过就是<strong>假跑</strong>（曲线在降，但下降不是算法本身的功劳；这是本站收录算法的硬性要求）。</div>
  <div class="tablewrap">
  <table>
    <tr><th>算法</th><th class="num">30 城市</th><th class="num">60 城市</th><th class="num">100 城市</th></tr>
    {bench}
  </table>
  </div>
  <div class="box">一句话结论：<strong>前十名差距在 2.3% 以内——统计上并列，没有单一赢家</strong>（本表为单 seed 单实例教学对照：换 seed 排名即变，请勿当性能榜单读）。可读的趋势：局部搜索框架三件套（VNS / ILS / LK）与 ACO、SFLA 常年在第一梯队——前者靠「扰动+下探」的框架增益，后者靠信息素天然编码边结构。<strong>真上生产 TSP/VRP：看 LKH、Concorde、OR-Tools 与并行 memetic，不是这张教学表里的任何一行。</strong></div>

  <h2>算法分类与谱系映射</h2>
  <p class="hint">每个算法的「原始形态 → 离散化到 TSP 的映射 → 复用的通用组件」。想做论文对比实验或写综述的同学，这张表就是索引。</p>
  <div class="tablewrap">
  <table>
    <tr><th>分类</th><th>算法</th><th>原始形态 / 问题域</th><th>离散化到 TSP 的映射</th><th>复用的通用组件</th></tr>
    <tr><td rowspan="1"><b>构造式</b></td><td>最近邻 NN</td><td>贪心构造，天然适合组合问题</td><td>每步选最近未访问城市（无需改造）</td><td>—（它是别人的组件）</td></tr>
    <tr><td rowspan="6"><b>局部搜索</b></td><td>2-opt 局部搜索</td><td>局部改进，通用启发式</td><td>2-opt 邻域：逆转路径片段，Δ 用 4 条边增量计算</td><td>—（同上）</td></tr>
    <tr><td>禁忌搜索 TS</td><td>记忆机制 + 元启发式框架（Glover 1986）</td><td>移动 = 2-opt 逆转；禁忌表存 (i,k) 到期代数；特赦准则放行破纪录移动</td><td>NN 起点 · 邻域采样 · 增量 Δ 计算</td></tr>
    <tr><td>迭代局部 ILS</td><td>框架（Lourenço 2003），无自有算子</td><td>扰动 = 双桥（2-opt 无法还原）+ 预算制 2-opt 下探 + 接受准则</td><td>NN 起点 · 双桥 kick · 增量 Δ 计算</td></tr>
    <tr><td>变邻域 VNS</td><td>框架（Mladenović &amp; Hansen 1997）</td><td>邻域轮换 shake：双桥 / or-opt 摘段重插 / 双重双桥，有进步回 k=1</td><td>NN 起点 · 多邻域算子族 · 预算制下探</td></tr>
    <tr><td>Lin–Kernighan LK</td><td>TSP 专用（Lin &amp; Kernighan 1973）</td><td>变深度链式 2-opt：允许链中暂时变差，按累计增益收官；卡死踢双桥</td><td>NN 起点 · 增量 Δ 计算 · 双桥 kick</td></tr>
    <tr><td>GRASP</td><td>框架（Feo &amp; Resende 1989），无种群</td><td>RCL 半贪心构造（最近 k 个随机选一，k=2 甜区）+ 2-opt 预算制下探；每代独立重启</td><td>NN 基线 · RCL 构造器 · 预算制下探</td></tr>
    <tr><td rowspan="17"><b>群体智能</b></td><td>蚁群 ACO</td><td>连续/图域均有；信息素标在「边」上</td><td>信息素天然匹配 TSP 的边结构，几乎无需改造</td><td>NN 播种 · 候选列表 · 周期 2-opt</td></tr>
    <tr><td>粒子群 PSO</td><td>连续实数空间（Kennedy 1995）</td><td><b>交换序列</b>：速度 = 一串交换操作，按比例取前缀</td><td>NN 播种 · 步幅上限 · memetic 2-opt</td></tr>
    <tr><td>人工蜂群 ABC</td><td>函数优化（Karaboga 2005）</td><td>蜜源 = 排列；邻域算子 = 片段逆转/交换</td><td>NN 多起点播种 · 侦察蜂重置 · memetic 2-opt</td></tr>
    <tr><td>萤火虫 FA</td><td>连续空间（Yang 2008）</td><td>亮度 = 1/(1+成本)；移动 = 向最亮者执行交换前缀；α 扰动 = 短 2-opt 试射</td><td>NN 播种 · 步幅上限 · 汉明距离吸引度</td></tr>
    <tr><td>灰狼 GWO / 鲸鱼 WOA</td><td>连续空间（Mirjalili 2014/2016）</td><td>向 α/β/δ 或最优鲸执行交换序列前缀；WOA 的螺旋 = 比例随 e^(b·l) 收缩</td><td>NN 播种 · 步幅上限（防坍塌）· memetic 2-opt</td></tr>
    <tr><td>烟花 FWA / 鱼群 AFSA</td><td>连续空间（Tan 2010 / 李晓磊 2002）</td><td>FWA：爆炸数量 ∝ 适应度、幅度 ∝ (1−适应度)，高斯火花 = 短 2-opt 试射；AFSA：追尾 = 向更优鱼执行交换前缀，拥挤度 δ 防挤</td><td>NN 播种 · 火花贪心准入 · memetic 2-opt</td></tr>
    <tr><td>布谷鸟 CS</td><td>连续空间（Yang & Deb 2009）</td><td>莱维飞行：小步 = 短 2-opt 试射，偶发大步 = 长片段逆转（幂律步长）</td><td>NN 播种 · 弃巢重置 · memetic 2-opt</td></tr>
    <tr><td>哈里斯鹰 HHO</td><td>连续空间（Heidari 2019）</td><td>逃逸能量 E 调度四阶段：软/硬包围 = 按 |E| 缩放交换前缀；俯冲 = 短 2-opt 试射</td><td>NN 播种 · 步幅上限 · memetic 2-opt</td></tr>
    <tr><td>蝙蝠 BA</td><td>连续空间（Yang 2010）</td><td>频率 = 向最优的交换前缀比例；响度 = 试射强度并衰减；脉冲率 = 定位开发概率并升高</td><td>NN 播种 · 步幅上限 · memetic 2-opt</td></tr>
    <tr><td>细菌觅食 BFO</td><td>连续空间（Passino 2002）</td><td>翻滚/连游 = 连续短 2-opt 试射（作用于当前解本体）；繁殖 = 排序复制；消散 = NN 重播</td><td>NN 播种 · memetic 2-opt</td></tr>
    <tr><td>蛾焰 MFO</td><td>连续空间（Mirjalili 2015）</td><td>螺旋 = 向火焰的交换前缀按 e^(b·t)·|cos| 调制；焰数逐代递减 n→1</td><td>NN 播种 · 螺旋收缩 · memetic 2-opt</td></tr>
    <tr><td>麻雀 SSA / 蚁狮 ALO / 蝴蝶 BOA</td><td>连续空间（Xue 2020 / Mirjalili 2015 / Arora 2019），2020 前后新算法代表</td><td>SSA：发现者无条件跳盆地 + 警戒远跳（扰动+预算下探作用于最优本体）；ALO：贪心游走 + 陷阱收缩；BOA：香味 ∝ 适应度调制步幅</td><td>NN 播种 · 步幅上限 · memetic 2-opt</td></tr>
    <tr><td>帝国 ICA / 樽海鞘 Salp / 蛙跳 SFLA</td><td>连续空间（Atashpaz-Gargari 2007 / Mirjalili 2017 / Eusuff 2006）</td><td>ICA：同化 = 交换前缀 + 无条件革命 + 帝国竞争换防；Salp：链首扰动下探 + 链式无条件跟随；SFLA：族群 OX 学习 + 反射踢 + 洗牌</td><td>NN 播种 · 双桥扰动 · 预算制下探 · OX 交叉</td></tr>
    <tr><td>花朵 FPA / 磷虾 KH / 共生 SOS / Jaya</td><td>连续空间（Yang 2012 / Gandomi 2012 / Cheng 2014 / Rao 2016），组件化装配</td><td>FPA：Levy 越步 = f&gt;1 跳盆地 + 落地打磨；KH：三力串联（OX 学邻居 + 向食物源 + 扩散）；SOS：互利 OX / 偏利向最优 / 寄生挑战宿主；Jaya：向最优随机前缀 + 远离最劣（公共边占比）</td><td>NN 播种 · OX 交叉 · 双桥扰动 · 预算制下探 · 公共边相似度</td></tr>
    <tr><td>蜻蜓 DA / 掠食者 MPA / 乌鸦搜索 CSA</td><td>连续空间（Mirjalili 2016 / Faramarzi 2020 / Askarzadeh 2016），组件化装配</td><td>DA：五行为加权（分离抖动 / 对齐 OX / 聚合向最优）；MPA：布朗/莱维三相位速度博弈 + FADS 防停滞；CS：记忆偷窃（察觉概率 AP 调度跟随或乱飞）</td><td>NN 播种 · OX 交叉 · 双桥扰动 · 预算制下探</td></tr>
    <tr><td>天鹰 AO</td><td>连续空间（Abualigah 2021），组件化装配</td><td>四阶段三等分硬切换：广域双桥 → Levy 越步 → or-opt 精修 → OX 向 best + 下探</td><td>NN 播种 · OX 交叉 · 双桥扰动 · 预算制下探</td></tr>
    <tr><td rowspan="5"><b>进化计算</b></td><td>遗传 GA</td><td>通用进化框架</td><td>排列专用算子：OX 顺序交叉 + 反转变异</td><td>NN 多起点播种 · 精英保留 · memetic 2-opt</td></tr>
    <tr><td>差分进化 DE</td><td>连续空间（Storn & Price 1997）</td><td>差向量 = 交换序列；current-to-best 变异 + 低 CR 的 OX + 贪心选择</td><td>NN 播种 · 步幅上限 · memetic 2-opt</td></tr>
    <tr><td>教与学 TLBO</td><td>班级教学隐喻（Rao 2011），连续域无参数</td><td>教师阶段 = 向 teacher 的随机比例交换前缀（可反向）；学习阶段 = 配对 OX / 模仿</td><td>NN 播种 · OX 交叉 · memetic 2-opt</td></tr>
    <tr><td>生物地理 BBO</td><td>岛屿生物地理学（Simon 2008）</td><td>迁入/迁出率由 HSI 排名线性调度：差者受助（接收供体 OX）、富者输出；随机修改防早熟</td><td>NN 播种 · OX 交叉 · 轮盘选择 · memetic 2-opt</td></tr>
    <tr><td>克隆选择 AIS</td><td>免疫系统克隆选择学说（de Castro &amp; Von Zuben 2002）</td><td>克隆扩增 ∝ 排名 + 高频变异 ∝ 亲和度（好的轻抖差的重摇）+ 变异后试射 + 新抗体注入</td><td>NN 播种 · 双桥/逆转/移段变异 · 预算制下探</td></tr>
    <tr><td rowspan="3"><b>物理启发</b></td><td>模拟退火 SA</td><td>统计物理退火过程，通用</td><td>邻域 = 2-opt 逆转，Δ 增量计算 O(1)</td><td>NN 起点 · Metropolis 判据（自带）</td></tr>
    <tr><td>引力搜索 GSA</td><td>万有引力 + 运动定律（Rashedi 2009）</td><td>质量 = 成本归一化；移动 = 按质量轮盘选引力源执行交换前缀（比例 ∝ G 衰减）；好解几乎不动</td><td>NN 播种 · 步幅上限 · 惯性滑翔</td></tr>
    <tr><td>均衡 EO</td><td>质量平衡方程（Faramarzi 2020）</td><td>随机键编码 + 均衡池五元组（4 最优+1 平均）：X_new = C_eq + (X−C_eq)·F + G·(1−F)/λ·U，F=exp(−a·λ) 衰减</td><td>NN 播种 · 随机键编码 · 反射踢 · memetic 2-opt</td></tr>
    <tr><td><b>数学启发</b></td><td>正弦余弦 SCA</td><td>三角函数振荡包围（Mirjalili 2016）</td><td>步幅 = r1·|sin/cos|；正向振荡向最优收缩，反向振荡向随机同伴靠近</td><td>NN 播种 · 步幅上限 · memetic 2-opt</td></tr>
    <tr><td><b>音乐启发</b></td><td>和声搜索 HS</td><td>乐手即兴隐喻（Geem 2001）</td><td>记忆考虑 = 抄库内和声；音高调整 = 短 2-opt 试射/片段逆转；即兴 = NN 重构造</td><td>NN 播种 · 精英记忆库 · memetic 2-opt</td></tr>
  </table>
  </div>
  <div class="box">读表结论：① <strong>「NN 多起点播种 + 步幅上限 + memetic 2-opt」是所有种群算法在 TSP 上能打的三件套</strong>——每一条都是踩坑换来的（原因见各算法页）；② 连续算法离散化的两条路线里，<strong>交换序列全面优于随机键</strong>；③ 这些组件组合起来，就是你自研新算法的脚手架。</div>

  <h2>收录标准与路线图（持续更新）</h2>
    <div class="box"><strong>量级声明（写给要上生产的你）</strong>：本页演示是<strong>教学规模</strong>——城市 ≤150、迭代 ≤2000、浏览器单线程。真实工业 TSP/VRP 常是 1k–10k+ 节点、路网距离、时间窗与容量约束并存，那是 LKH、Concorde、OR-Tools 与并行 memetic 的战场；本站 45 个算法的价值是让你<strong>看懂原理、建立手感、学会「真优化」校验</strong>，不是替你跑生产。</div>

  <h2>收录标准与路线图（持续更新）</h2>
  <p class="hint">本站按<strong>学术影响力</strong>决定收录优先级：① 原始论文引用量（Google Scholar 量级）② 算法在后续文献中的使用频率（是否常被选为对比基线）③ 离散化到 TSP 的可行性与教学价值。每收录一个算法都必须通过「「是否真在优化」自动测试」（关掉全部局部搜索仍明显优于初始解，且 1 代 → 200 代必须有真实迭代进步），这是硬门槛。当前已收录 <strong>{algo_count}</strong> 个。</p>
  <div class="tablewrap">
  <table>
    <tr><th>状态</th><th>算法</th><th>提出者 / 年份</th><th>引用量级</th><th>备注</th></tr>
    <tr><td>✅ 已收录</td><td>DE 差分进化</td><td>Storn & Price, 1997</td><td>数万</td><td>排列域假跑排查全过程见算法页</td></tr>
    <tr><td>✅ 已收录</td><td>TS 禁忌搜索</td><td>Glover, 1986</td><td>数万</td><td>元启发式奠基工作</td></tr>
    <tr><td>✅ 已收录</td><td>HHO 哈里斯鹰</td><td>Heidari et al., 2019</td><td>上万</td><td>近年引用增长最快之一</td></tr>
    <tr><td>✅ 已收录</td><td>CS 布谷鸟搜索</td><td>Yang & Deb, 2009</td><td>上万</td><td>莱维飞行代表作</td></tr>
    <tr><td>✅ 已收录</td><td>SCA 正弦余弦</td><td>Mirjalili, 2016</td><td>数千</td><td>Mirjalili 系第三件</td></tr>
    <tr><td>✅ 已收录</td><td>ILS 迭代局部搜索</td><td>Lourenço et al., 2003</td><td>上万</td><td>工业界最常用框架；n=100 实测前三</td></tr>
    <tr><td>✅ 已收录</td><td>VNS 变邻域搜索</td><td>Mladenović &amp; Hansen, 1997</td><td>上万</td><td>邻域轮换；n=100 实测第一梯队（与前十并列，见成绩表注）</td></tr>
    <tr><td>✅ 已收录</td><td>Lin–Kernighan LK</td><td>Lin &amp; Kernighan, 1973</td><td>经典</td><td>变深度链式交换的教学级简化版</td></tr>
    <tr><td>✅ 已收录</td><td>BA 蝙蝠算法</td><td>Yang, 2010</td><td>上万</td><td>频率调谐 + 响度衰减</td></tr>
    <tr><td>✅ 已收录</td><td>和声搜索 HS</td><td>Geem et al., 2001</td><td>近万</td><td>音乐即兴隐喻开山作</td></tr>
    <tr><td>✅ 已收录</td><td>引力搜索 GSA</td><td>Rashedi et al., 2009</td><td>近万</td><td>物理启发代表作；滑翔 memetic 组件</td></tr>
    <tr><td>✅ 已收录</td><td>教与学优化 TLBO</td><td>Rao et al., 2011</td><td>近万</td><td>教师/学习两阶段，真实进步 3.5–5.6%</td></tr>
    <tr><td>✅ 已收录</td><td>细菌觅食 BFO</td><td>Passino, 2002</td><td>数千</td><td>趋化/繁殖/消散三循环</td></tr>
    <tr><td>✅ 已收录</td><td>蛾焰优化 MFO</td><td>Mirjalili, 2015</td><td>数千</td><td>螺旋飞行 + 焰数递减调度</td></tr>
    <tr><td>✅ 已收录</td><td>烟花算法 FWA</td><td>Tan &amp; Zhu, 2010</td><td>数千</td><td>好烟花多炸近、差烟花少炸远的显式勘探/开发调度</td></tr>
    <tr><td>✅ 已收录</td><td>人工鱼群 AFSA</td><td>Li, 2002</td><td>数千</td><td>行为切换 + 拥挤度因子 δ 防种群坍缩</td></tr>
    <tr><td>✅ 已收录</td><td>交叉熵方法 CEM</td><td>Rubinstein, 1997</td><td>上万</td><td>EDA 家族源头：分布采样 + 精英频率回写</td></tr>
    <tr><td>✅ 已收录</td><td>麻雀搜索 SSA</td><td>Xue &amp; Shen, 2020</td><td>数千（近年暴涨）</td><td>发现者/加入者/警戒者三角色；n=100 实测全场第三</td></tr>
    <tr><td>✅ 已收录</td><td>蚁狮优化 ALO</td><td>Mirjalili, 2015</td><td>数千</td><td>随机游走 + 陷阱收缩，Mirjalili 系补全</td></tr>
    <tr><td>✅ 已收录</td><td>蝴蝶优化 BOA</td><td>Arora &amp; Singh, 2019</td><td>数千</td><td>香味感知 + 全局/局部切换</td></tr>
    <tr><td>✅ 已收录</td><td>帝国竞争 ICA</td><td>Atashpaz-Gargari &amp; Lucas, 2007</td><td>近万</td><td>同化 + 革命 + 帝国竞争；社会政治隐喻代表作</td></tr>
    <tr><td>✅ 已收录</td><td>樽海鞘群 Salp</td><td>Mirjalili et al., 2017</td><td>数千</td><td>链式跟随 + c1 衰减调度；n=100 实测并列第三</td></tr>
    <tr><td>✅ 已收录</td><td>混合蛙跳 SFLA</td><td>Eusuff &amp; Lansey, 2006</td><td>数千</td><td>族群学习 + CCE 反射 + 洗牌；n=100 实测第一梯队（与前十并列，见成绩表注）</td></tr>
    <tr><td>✅ 已收录</td><td>花朵授粉 FPA</td><td>Yang, 2012</td><td>数千</td><td>Levy 越步授粉；n=100 实测第一梯队（与前十并列，见成绩表注）（813.7）</td></tr>
    <tr><td>✅ 已收录</td><td>磷虾群 KH</td><td>Gandomi &amp; Alavi, 2012</td><td>数千</td><td>诱发/觅食/扩散三力合成；单代 0.19 秒</td></tr>
    <tr><td>✅ 已收录</td><td>共生生物搜索 SOS</td><td>Cheng &amp; Prayogo, 2014</td><td>数千</td><td>互利/偏利/寄生三相，无算法特有参数</td></tr>
    <tr><td>✅ 已收录</td><td>Jaya 算法 JAYA</td><td>Rao, 2016</td><td>数千</td><td>零算法专属参数；远离最劣 = 公共边相似度</td></tr>
    <tr><td>✅ 已收录</td><td>蜻蜓 DA</td><td>Mirjalili, 2016</td><td>数千</td><td>分离/对齐/聚合/捕食/逃离五力合成；n=100 = 834.5、单代 0.13 秒</td></tr>
    <tr><td>✅ 已收录</td><td>海洋掠食者 MPA</td><td>Faramarzi, 2020</td><td>数千</td><td>布朗/莱维三相位速度博弈；n=100 = 832.0（第五名）</td></tr>
    <tr><td>✅ 已收录</td><td>乌鸦搜索 CS</td><td>Askarzadeh, 2016</td><td>数千</td><td>记忆偷窃博弈，察觉概率 AP 唯一旋钮；与布谷鸟 CS 同名不同物</td></tr>
    <tr><td>✅ 已收录</td><td>生物地理学 BBO</td><td>Simon, 2008</td><td>数千</td><td>迁入/迁出率排名调度；单代 0.12 秒全场最快之一</td></tr>
    <tr><td>✅ 已收录</td><td>GRASP</td><td>Feo &amp; Resende, 1989</td><td>近万</td><td>多重启构造+下探框架；n=100 = 824.0（第四名）；RCL 宽度 k=2 实测甜区</td></tr>
    <tr><td>✅ 已收录</td><td>克隆选择 AIS</td><td>de Castro &amp; Von Zuben, 2002</td><td>数千</td><td>克隆扩增+高频变异+新抗体注入；n=100 = 830.9（第七名）</td></tr>
    <tr><td>✅ 已收录</td><td>均衡优化 EO</td><td>Faramarzi, 2020</td><td>数千</td><td>均衡池+质量平衡方程（物理化学类代表）；随机键嫁接；n=100 = 832.1</td></tr>
    <tr><td>✅ 已收录</td><td>天鹰 AO</td><td>Abualigah, 2021</td><td>数千</td><td>四阶段三等分硬切换；n=100 = 845.7；近年上升最快的新一代算法之一</td></tr>
    <tr><td>🧭 规划中</td><td>专用求解对照系扩容</td><td>—</td><td>—</td><td>候选：背包 MCKnap（Pisinger 2007）、图着色专用精确界等——作为各问题域的对照位随收录扩容（F0 定位见家族页）</td></tr>
  </table>
  </div>

  <p class="hint">演示只是这个站的一条线——同一批算法换编码就能解背包、连续函数、多目标、图着色、装箱等问题，见<a href="/problem/">问题库</a>；方法论与批评见<a href="/encyclopedia/">百科总纲</a>。</p>
</div>

<footer>
  <span class="fbrand">群智能算法百科</span>
  <span class="ver">v0.1.0</span>
  <span>Pyodide + Web Worker · 源码与实现细节见项目 README</span>
</footer>

<script src="/js/compat.js"></script>
<script type="module" src="/js/tool.js"></script>
<!--THEME_TAIL-->
</body>
</html>
"""


COMPARE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>智能优化算法性能对比 · {algo_count} 算法同实例求解 TSP 横向测评</title>
<meta name="description" content="同一 TSP 实例上横向对比粒子群(PSO)、蚁群(ACO)、遗传(GA)、模拟退火(SA)、灰狼(GWO)等全部 {algo_count} 种智能优化算法：收敛曲线叠加、结果排名、相对最近邻基线的优化幅度，在线一键运行。">
<!--THEME_HEAD-->
<link rel="stylesheet" href="/css/style.css">
<link rel="canonical" href="{site}/compare/">
<script type="application/ld+json">{ldjson}</script>
</head>
<body>
<a class="skip-link" href="#main">跳到主内容</a>
<nav class="nav"><div class="nav-inner">
  <a class="brand" href="/"><span class="logo">🐝</span>群智能算法百科</a>
  <div class="nav-links">
  {navlinks}
  </div>
  <!--THEME_BTN-->
</div></nav>

<div class="wrap" id="main" role="main">
  <div class="hero" style="padding-top:18px">
    <div class="crumbs"><a href="/">首页</a> · 算法对比</div>
    <h1 style="font-size:28px">智能优化算法性能对比<br><span class="grad">{algo_count} 个算法跑同一个 TSP</span></h1>
    <div class="sub">同一批城市、同样的迭代次数、同一个随机种子，交给全部 {algo_count} 个算法各跑一遍，曲线叠加看收敛速度，表格看最终结果。</div>
  </div>

  <div class="panel">
    <div class="panel-head">对比设置</div>
    <div class="row">
      <div class="field"><label>城市数</label><input id="nCities" type="number" value="50" min="10" max="150"></div>
      <div class="field"><label>迭代次数</label><input id="maxIter" type="number" value="200" min="10" max="1000"><small class="hint">调高会更准也更慢：要跑全部 {algo_count} 个算法，高迭代 + 多城市可能等上几分钟</small></div>
      <button id="btnGen">⟳ 换一批城市</button>
      <button id="btnRun" class="primary" disabled>▶ 跑全部算法</button>
    </div>
  </div>
  <div class="statusline">
    <span class="pill" id="statusPill"><span class="dot"></span><span id="statusText" role="status" aria-live="polite">初始化中…</span></span>
    <span id="statusExtra">跑完自动生成排名表</span>
  </div>

  <div class="cols" style="margin-top:10px">
    <div>
      <div class="chart-card">
        <div class="chart-head">
          <span class="chart-title">城市分布</span>
          <div class="legend"><span><i class="dotm" style="background:var(--cv-city)"></i>城市</span></div>
        </div>
        <div class="chart-body"><canvas id="mapCanvas" width="760" height="440"></canvas></div>
        <div class="hint">对比页只画城市，不画各算法的最终路径（叠成一团看不清）。</div>
      </div>
    </div>
    <div>
      <div class="chart-card">
        <div class="chart-head">
          <span class="chart-title">收敛曲线叠加</span>
          <div class="legend" id="legend"></div>
        </div>
        <div class="chart-body"><canvas id="convCanvas" width="760" height="440"></canvas></div>
        <div class="hint">横轴=迭代代数，纵轴=路径长度。虚线为最近邻基线，其余每条线一个算法。</div>
      </div>
    </div>
  </div>

  <div id="out"></div>

  <h2>怎么看这张表</h2>
  <ul>
    <li><strong>先看「相对基线优化」</strong>：这是相对最近邻解的改进幅度，比看绝对长度更有意义。</li>
    <li><strong>再看收敛速度而不是只看终值</strong>：论文里常见「算法 A 最终略好但收敛慢一倍」，这时候 A 未必更实用。</li>
    <li><strong>别把小差距当结论</strong>：这些都是随机算法，3% 以内的差距换个种子就可能反转。要下结论请多次运行取平均。</li>
  </ul>

  <h2>想复现这张表</h2>
  <p>本地命令行跑 <code>python bench.py --sizes 30,60,100 --iters 200</code> 即可，结果可直接贴进文章或论文。
  加 <code>--pure</code> 会关掉所有局部搜索，用来检验「算法本身」而不是局部搜索在起作用。</p>

  <h2>相关页面</h2>
  <div class="cards">
    {cards}
  </div>
</div>

<footer>
  <span class="fbrand">群智能算法百科</span>
  <span class="ver">v0.1.0</span>
  <span>算法由 Pyodide 在浏览器本地运行，数据不上传</span>
</footer>

<script src="/js/compat.js"></script>
<script type="module" src="/js/compare.js"></script>
<!--THEME_TAIL-->
</body>
</html>
"""


def _dd(btn_text: str, btn_href: str, on: bool, panel_html: str, wide: bool = False,
        panel_extra: str = "") -> str:
    """层级导航一级项：按钮 + 下拉面板（桌面 hover/focus 展开，触屏点按展开）。"""
    cls = "dd on" if on else "dd"
    wide_cls = (" dd-wide" if wide else "") + (f" {panel_extra}" if panel_extra else "")
    return (f'<div class="{cls}">'
            f'<a class="dd-btn" href="{btn_href}">{btn_text} <span class="caret">▾</span></a>'
            f'<div class="dd-panel{wide_cls}">{panel_html}</div></div>')


_RECIPE_BY_FAM_CACHE = None
def _recipe_by_fam():
    """家族 id(upper) → 该家族下配方页列表（py/recipe.py 单一事实源）。"""
    global _RECIPE_BY_FAM_CACHE
    if _RECIPE_BY_FAM_CACHE is None:
        import sys as _sys
        _sys.path.insert(0, os.path.join(ROOT, "py"))
        import recipe as _recipe_mod  # noqa: E402
        d = {}
        for r in _recipe_mod.RECIPES:
            d.setdefault(r["lineage"]["family"].upper(), []).append(r)
        _RECIPE_BY_FAM_CACHE = d
    return _RECIPE_BY_FAM_CACHE


def _fam_counts(fam: dict) -> dict:
    """统一计数口径（走查 P1-1/P1-2 修复）：
    - 成员页 pages = ALGOS 成员 + 同 lineage 配方页 + nav_extra；
    - 词条 planned = families.json 的 planned 列表长度。
    导航下拉与家族页 heading 共用本函数，确保两处口径一致。"""
    members = [a for a in ALGOS if a.get("family") == fam["id"]]
    recipes = _recipe_by_fam().get(fam["id"], [])
    extra = fam.get("nav_extra", []) or []
    planned = fam.get("planned", []) or []
    return {"members": len(members), "recipes": len(recipes),
            "extra": len(extra), "planned": len(planned),
            "pages": len(members) + len(recipes) + len(extra)}


def _fam_hint(c: dict) -> str:
    """家族计数 hint 唯一口径（β3 走查：导航「5 个」vs 总览「4 算法 · 1 配方」打架）。
    导航下拉与 /algo/ 总览共用本函数；0 项跳过，extra 统一叫「域内实现」。"""
    bits = []
    if c["members"]:
        bits.append(f'{c["members"]} 算法')
    if c["recipes"]:
        bits.append(f'{c["recipes"]} 配方')
    if c["extra"]:
        bits.append(f'{c["extra"]} 域内实现')
    if c["planned"]:
        bits.append(f'{c["planned"]} 词条')
    return " · ".join(bits) or "词条筹建"


def _fam_heading(fam: dict) -> str:
    """家族页 heading 文案：成员页与词条分列，避免「家族成员（0）」误导（F9 实为 66 词条）。"""
    c = _fam_counts(fam)
    if c["planned"] == 0:
        return f'家族成员（{c["pages"]}）'
    if c["pages"] == 0:
        return f'收录词条（{c["planned"]}）'
    return f'家族成员与词条（{c["pages"]} 成员 · {c["planned"]} 词条）'


def navlinks(current: str) -> str:
    # ① 算法板块：二级=10 家族，三级=家族内实际算法（FAMILIES + ALGOS 数据驱动）
    #    + 升格配方页（py/recipe.py RECIPES）+ 空家族灰色说明链家族页（F7/F9 不空挂）
    import sys as _sys
    if os.path.join(ROOT, "py") not in _sys.path:
        _sys.path.insert(0, os.path.join(ROOT, "py"))
    import recipe as _recipe_mod  # noqa: E402
    fdir = {f["id"]: f["dir"] for f in FAMILIES}
    rec_by_fam: dict = {}
    for r in _recipe_mod.RECIPES:
        rec_by_fam.setdefault(r["lineage"]["family"].upper(), []).append(r)
    fam_groups = []
    for f in FAMILIES:
        c = _fam_counts(f)
        members = [a for a in ALGOS if a.get("family") == f["id"]]
        items = "".join(f'<a class="dd-item" href="{algo_url(a["slug"])}">'
                        f'{ICO.get(a["key"], "⚙")}&nbsp;{a["name"]}</a>' for a in members)
        items += "".join(f'<a class="dd-item" href="/algo/{f["dir"]}/{r["id"]}/">'
                         f'🧪&nbsp;{r["name"]}</a>' for r in rec_by_fam.get(f["id"], []))
        # H2b：域内实现条目（families.json nav_extra，如 F7 的 NSGA-II/WSGA → 多目标域演示）
        items += "".join(f'<a class="dd-item" href="{e["href"]}">'
                         f'{e["name"]}&nbsp;<span class="hint">{e.get("tag", "")}</span></a>'
                         for e in f.get("nav_extra", []))
        # 无成员页但有词条：下拉给一条进家族页看词条，不再写「收录筹建中」误导（F9 实为 66 条）
        if not items and c["planned"] > 0:
            items = (f'<a class="dd-item dd-entry" href="/algo/{f["dir"]}/">'
                     f'查看 {c["planned"]} 个收录词条 →</a>')
        # 计数口径统一（β3）：与 /algo/ 总览共用 _fam_hint，杜绝「5 个」vs「4 算法·1 配方」打架
        hint = _fam_hint(c)
        fam_groups.append(
            f'<div class="dd-group"><a class="dd-fam" title="{f.get("oneliner", "")}" href="/algo/{f["dir"]}/">{f["name"]}'
            f'<span class="hint">{hint}</span></a>{items}</div>')
    algo_dd = _dd("算法", "/algo/", current.startswith("/algo/"),
                  f'<div class="dd-grid">{"".join(fam_groups)}</div>'
                  f'<div class="hint" style="padding:10px 6px 0">共 {N_ALGOS} 个实际算法'
                  '（⚙ 图标）；🧪 标记为组合配方、f7/f8 组内带域内实现入口——比算法本体多几项属正常。</div>',
                  wide=True)
    # ② 问题板块：十大抽象类导航（PROBLEMS abstract_types 数据驱动）
    atypes = PROBLEMS.get("abstract_types", [])
    a_pages = [t for t in atypes if t.get("status") == "page"]
    a_entries = [t for t in atypes if t.get("status") == "entry"]
    knap = PROBLEMS["knapsack_variants"]
    nav_cols = []
    for g, hub_h, hub_t in PROB_NAV_GROUPS:
        g_pages = [t for t in a_pages if t.get("group") == g]
        # 枢纽页本身就是该类成员页时去重（tsp/uflp 型：枢纽=成员），避免下拉同链接出现两次
        g_pages = [t for t in g_pages if f"/problem/{t['dir']}/" != hub_h]
        g_entries = [t for t in a_entries if t.get("group") == g]
        body = []
        if g == "subset":
            body.append("".join(f'<a class="dd-item" href="/problem/knapsack/{v["id"]}/">'
                                f'{v["name"]}</a>' for v in knap))
        body.append("".join(f'<a class="dd-item" href="/problem/{t["dir"]}/">'
                            f'{t["name"]}{(" " + t["abbr"]) if t.get("abbr") else ""}</a>'
                            for t in g_pages))
        # 词条逐条展开（用户裁定：禁止「词条 ×N → 全谱」汇总行——汇总行让 TSP/指派列看似空壳）
        body.append("".join(f'<a class="dd-item dd-entry" href="/problem/reductions/#e-{t["id"]}">'
                            f'{t["name"]}{(" " + t["abbr"]) if t.get("abbr") else ""}</a>'
                            for t in g_entries))
        hub = (f'<a class="dd-fam" href="{hub_h}">{hub_t}</a>' if hub_h
               else f'<span class="dd-fam">{hub_t}</span>')
        nav_cols.append(f'<div class="dd-col">{hub}{"".join(body)}</div>')
    nav_cols.append('<div class="dd-col"><a class="dd-fam" href="/problem/reductions/">'
                    '归约页 · 全谱词条</a>'
                    + "".join(f'<a class="dd-item dd-entry" href="/problem/reductions/#e-{t["id"]}">'
                              f'{t["name"]}{(" " + t["abbr"]) if t.get("abbr") else ""}</a>'
                              for t in a_entries if t.get("group") == "open")
                    + '</div>')
    prob_panel = f'<div class="prob-cols">{"".join(nav_cols)}</div>'
    prob_dd = _dd("问题", "/problem/", current.startswith("/problem/"), prob_panel,
                  wide=True, panel_extra="prob-wide")
    # ③ 科普板块：直白入门位 + 元层四页（meta.json）+ 百科/矩阵/应用地图/组件
    #    「什么是元启发式」直白入口（UX1 遗留 P2）：新手第一问，落到总纲页定义区
    edu_whatis = '<a class="dd-item" href="/encyclopedia/#intro">❓&nbsp;什么是元启发式？（3 分钟入门）</a>'
    edu_hint = ('<div class="hint" style="padding:2px 10px 8px">小白从这里进：入门 → 理论/批评/实验方法学 → '
                '交叉矩阵与应用地图（研究级硬核内容，按需取用）。</div>')
    edu_items = "".join(f'<a class="dd-item" href="{p["dir"] and "/meta/" + p["dir"] + "/"}">'
                        f'{p.get("ico", "📖")}&nbsp;{p["name"]}</a>' for p in META_PAGES)
    edu_static = "".join(f'<a class="dd-item" href="{h}" title="{t}（研究级）">📌&nbsp;{t}</a>' for h, t in EDU_LINKS)
    edu_contrib = ('<span class="dd-fam">给贡献者</span>'
                   + "".join(f'<a class="dd-item" href="{h}" title="{t}：写给想参与维护或扩展本站的人">🛠&nbsp;{t}</a>'
                             for h, t in CONTRIB_LINKS))
    edu_dd = _dd("科普", "/encyclopedia/", any(current == h for h, _ in EDU_LINKS)
                 or any(current.startswith(f"/meta/{p['dir']}/") for p in META_PAGES)
                 or current == "/matrix/" or current == "/applications/"
                 or any(current == h for h, _ in CONTRIB_LINKS),
                 f'<div class="dd-col">{edu_whatis}{edu_hint}{edu_items}{edu_static}{edu_contrib}</div>')
    # ④ 直达项
    home = '<a href="/" class="on">首页</a>' if current == "/" else '<a href="/">首页</a>'
    cmp_ = ('<a href="/compare/" class="on">算法对比</a>' if current == "/compare/"
            else '<a href="/compare/">算法对比</a>')
    demo = ('<a href="/demo/" class="on">▶ 演示</a>' if current == "/demo/"
            else '<a href="/demo/">▶ 演示</a>')
    guide = ('<a href="/guide/" class="on">上手</a>' if current == "/guide/" else '<a href="/guide/">上手</a>')
    return "\n  ".join([home, algo_dd, prob_dd, edu_dd, demo, guide, cmp_])


ICO = {"pso": "🌀", "aco": "🐜", "abc": "🐝", "fa": "✨", "woa": "🐋", "sma": "🟠",
       "ga": "🧬", "sa": "🌡️", "gwo": "🐺", "ts": "🔒", "de": "📉",
       "cs": "🐦", "sca": "🌊", "hho": "🦅", "ils": "🔄", "vns": "🧭",
       "lk": "🧭", "ba": "🦇", "hs": "🎵", "gsa": "🪐", "tlbo": "🎓",
       "bfo": "🦠", "mfo": "🕯️", "fwa": "🎆", "afsa": "🐟", "cem": "🎲",
       "ssa": "🐦", "alo": "🕳️", "boa": "🦋",
       "ica": "🏛️", "salp": "⛓️", "sfla": "🐸",
       "fpa": "🌸", "kh": "🦐", "sos": "🤝", "jaya": "🏆",
       "da": "🐉", "mpa": "🦈", "cscrow": "🐦‍⬛", "bbo": "🏝️",
       "grasp": "🎲", "ais": "🛡️", "eo": "⚗️", "ao": "🦅"}


def _clip_html(s: str, n: int) -> str:
    """按「可见字符数」截断含内联标签（<strong> 等）的 HTML：标签不计入长度，
    截断后自动补齐未闭合标签。教训：裸切片 lead[:38] 会把 <strong> 对拦腰
    切断，未闭合标签吞掉后续 </span></a>，浏览器纠错导致卡片网格整体塌陷
    （2026-09-16 首页右列布局事故根因）。"""
    out, open_tags = [], []
    i, visible = 0, 0
    while i < len(s):
        if s[i] == "<":
            j = s.find(">", i)
            if j == -1:  # 半截标签：丢弃
                break
            tag = s[i + 1:j]
            name = tag.strip().strip("/").split(" ")[0] if tag.strip() else ""
            if tag.startswith("/"):
                if open_tags and open_tags[-1] == name:
                    open_tags.pop()
            elif name not in ("br", "img", "hr"):
                open_tags.append(name)
            out.append(s[i:j + 1])
            i = j + 1
        else:
            if visible >= n:
                break
            out.append(s[i])
            visible += 1
            i += 1
    for t in reversed(open_tags):
        out.append(f"</{t}>")
    return "".join(out) + "…"


# S2-B 家族页模板：一家族一页（成员卡 + 谱系链 + 待收录清单）
FAMILY_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<!--THEME_HEAD-->
<link rel="stylesheet" href="/css/style.css">
<link rel="canonical" href="{site}{path}">
<script type="application/ld+json">{ldjson}</script>
</head>
<body>
<a class="skip-link" href="#main">跳到主内容</a>
<nav class="nav"><div class="nav-inner">
  <a class="brand" href="/"><span class="logo">🐝</span>群智能算法百科</a>
  <div class="nav-links">
  {navlinks}
  </div>
  <!--THEME_BTN-->
</div></nav>

<div class="wrap" id="main" role="main">
  <div class="hero" style="padding-top:18px">
    <div class="crumbs">算法家族 {fam_id}</div>
    <h1 style="font-size:28px">{h1}</h1>
    <div class="sub">{fam_oneliner}</div>
  {en_summary}
  </div>

  {fam_desc}

  <h2>{fam_heading}</h2>
  <div class="cards">
    {members_cards}
  </div>

  {chains_sec}
  {planned_sec}

  <h2>其他家族</h2>
  <div class="cards">
    {sib_cards}
  </div>
</div>
<!--THEME_TAIL-->
</body>
</html>
"""


def _recipe_data():
    """S7-B：读 py/recipe.py 的 RECIPES（页面清单用；必须内嵌 Pyodide 故不落 data/*.json）。"""
    import sys as _sys
    _sys.path.insert(0, os.path.join(ROOT, "py"))
    import recipe as _recipe_mod  # noqa: E402
    return _recipe_mod.RECIPES


def _planned_name(m: Dict) -> str:
    """S7：词条名可带页面链接（url 字段存在时）。"""
    return f'<a href="{m["url"]}">{m["name"]}</a>' if m.get("url") else m["name"]


def gen_recipe_pages() -> None:
    """S7-B：七槽组合配方页。数据源 = py/recipe.py 的 RECIPES（必须内嵌进 Pyodide
    运行时，故不落 data/*.json，以 import 为单一事实源）。"""
    import sys as _sys
    _sys.path.insert(0, os.path.join(ROOT, "py"))
    import recipe as _recipe  # noqa: E402

    for r in _recipe.RECIPES:
        fam = FAM_BY_ID[r["lineage"]["family"]]
        fam_dir = fam["dir"]
        u = f'/algo/{fam_dir}/{r["id"]}/'
        key = f'recipe:{r["id"]}'
        rcomp = _recipe.RCOMPONENTS
        intro_rows = "\n      ".join(
            f'<tr><td><b>{slot}</b></td><td><code>{cid}</code></td>'
            f'<td>{rcomp[cid]["source"]}</td></tr>'
            for slot, cid in r["slots"].items() if cid != "none")
        intro = (
            '\n  <p>这不是一个手写的求解器——它是<b>七槽管线组合引擎</b>跑出来的一份「配方」：'
            '初始化 → 选择 → 交叉 → 变异 → 替换 → 局部搜索 → 终止，'
            '每个槽位插一个组件模块。下表就是本配方的完整装配清单：</p>\n'
            '  <div class="tablewrap"><table><tr><th>槽位</th><th>组件</th><th>出处</th></tr>\n'
            f'      {intro_rows}\n  </table></div>\n'
            f'  <p class="hint">{r["note"]}</p>')
        # ILS 同名跨族消歧（2026-09-29 架构待议项）：配方 id 与正典算法 key 撞名时，
        # 页头互挂消歧提示（通用规则，任何未来同名碰撞自动生效，不写死 ils）。
        _canon = ALGO_BY_KEY.get(r["id"])
        if _canon is not None:
            intro += (f'\n  <p class="hint" id="name-disambig">↗ 同名消歧：本页是 <b>{r["name"]}</b>'
                      f'（七槽组合配方 · 组件装配视角）；{_canon["name"]} 的<b>经典算法条目</b>'
                      f'（手写实现）→ <a href="{algo_url(_canon["slug"])}">{_canon["title"]}</a>。</p>')
        principle = "\n    ".join([
            "所有组件复用站内同一份实现（py/components.py）——组合算法与手写算法共享算子代码。",
            "引擎用单一随机种子顺序驱动所有组件：同种子同结果，任何配方可复现。",
            "装配期校验：槽位引用未知组件在第 0 代前报错；排列 IO 契约（无重复城市）逐代验证。",
            f"谱系：{r['lineage']['source']}。",
        ])
        specs = _recipe._specs_for(r)
        params_rows = "\n    ".join(
            f'<tr><td><code>{k}</code></td><td class="num">{v}</td>'
            f'<td>{specs.get(k, {}).get("desc", "")}</td></tr>'
            for k, v in r["default_params"].items())
        faq = "\n  ".join([
            '<details class="faq-item"><summary>「组合配方」和手写算法有什么区别？</summary>'
            '<div class="faq-body">效果层面没有区别——都能跑、都能画收敛曲线。区别在产出方式：'
            '手写算法是一整个类；配方只是七个槽位的模块清单，由通用引擎解释执行。</div></details>',
            '<details class="faq-item"><summary>为什么 Memetic 配方与手写 GA 页数值不同？</summary>'
            '<div class="faq-body">两者是不同实现路径（RNG 消耗点不完全一致），不是同一程序的复制。'
            '它们共享同一批组件与同一套验收标准：同种子可复现、最优不回升。</div></details>',
            '<details class="faq-item"><summary>我能自己拼一个配方吗？</summary>'
            '<div class="faq-body">当前初版提供 3 个示范配方（下拉框「组合配方」分组）。'
            '自选槽位的交互式组合器在规划中（架构文档 S7-C）。</div></details>',
        ])
        chips = " ".join(f'<a class="chip" href="{algo_url(a["slug"])}">{a["name"]}</a>'
                         for a in ALGOS if a["family"] == fam["id"])
        fambox = (f'<div class="fambox"><p class="hint">所在家族：'
                  f'<a href="/algo/{fam_dir}/"><b>{fam["name"]}</b></a> —— {fam["oneliner"]}'
                  f'</p><div class="chips">{chips or "本家族成员页陆续收录中"}</div>'
                  f'<p class="hint" style="margin-top:8px">⚗ 本页是<b>组合配方</b>（七槽管线），'
                  f'在线演示的下拉框里选「组合配方」分组可见全部配方。</p></div>')
        title = f'{r["name"]} · 七槽组合配方在线演示 · 路径动画与收敛曲线'
        desc = (f'{r["name"]}：七槽管线组合引擎（{"、".join(v for v in r["slots"].values() if v != "none")}）'
                f'模块化组装的 TSP 在线演示，同种子可复现，浏览器本地运行。')
        # v1.6：配方页同享首屏右侧栏（伪 dict 走同一渲染器；无 bench 匹配 → 无实测卡）
        _pseudo = {"key": key, "name": r["name"],
                   "principle": [
                       "所有组件复用站内同一份实现（py/components.py）——组合算法与手写算法共享算子代码。",
                       "引擎用单一随机种子顺序驱动所有组件：同种子同结果，任何配方可复现。",
                       "装配期校验：槽位引用未知组件在第 0 代前报错；排列 IO 契约（无重复城市）逐代验证。",
                       f"谱系：{r['lineage']['source']}。",
                   ],
                   "params": [[k, v, specs.get(k, {}).get("desc", "")]
                              for k, v in r["default_params"].items()]}
        _side = side_pane_html(_pseudo)
        write(u.lstrip("/") + "index.html", inject_theme(TEMPLATE.format(
            site=SITE, path=u, fam_dir=fam_dir, fam_name=fam["name"], family_box=fambox,
            title=title, desc=desc,
            h1=f'{r["name"]}<br><span class="grad">七槽管线 · 模块组合</span>',
            lead=r["note"], en_summary="", key=key, intro=intro, principle=principle,
            params=params_rows, bench=bench_rows(), bench_caption=BENCH["caption"],
            faq=faq, rel_list=rel_list_html(""), map_card="", depth="",
            paper=r["lineage"]["source"],
            navlinks=navlinks(u), ldjson=ldjson(title, desc),
            **_side,
        )).replace("<!--ALGO_TAIL-->", ALGO_TAIL))


def gen_family_pages() -> None:
    """S2-B：生成 10 个家族页（F0-F9），一家族一页。"""
    for fam in FAMILIES:
        fam_url = f'/algo/{fam["dir"]}/'
        members = [a for a in ALGOS if a.get("family") == fam["id"]]
        # S7-B：配方作为家族成员卡一并展示（数据源 py/recipe.py RECIPES）
        recipe_cards = "\n    ".join(
            f'<a class="card" href="/algo/{fam["dir"]}/{r["id"]}/">'
            f'<span class="ico">⚗</span><b>{r["name"]}</b>'
            f'<span>七槽组合配方 · {r["lineage"]["source"].split("（")[0]}</span>'
            f'<span class="arrow">→</span></a>'
            for r in _recipe_data() if r["lineage"]["family"] == fam["id"])
        members_cards = "\n    ".join([*(
            algo_card_html(a) for a in members), recipe_cards]) \
            if (members or recipe_cards) else '<p class="hint">成员页收录中——下面的词条区已备好机制与出处，独立页分批建。</p>'

        secs = []
        chains = fam.get("chains", [])
        if chains:
            rows = "".join(
                f'\n      <tr><td style="white-space:nowrap"><b>{c["title"]}</b></td><td>{c["items"]}</td></tr>'
                for c in chains)
            secs.append(
                '<h2>谱系链与改进维度</h2>\n  <div class="tablewrap">\n  <table>'
                '\n    <tr><th>链 / 维度</th><th>成员与演化方向</th></tr>' + rows + '\n  </table>\n  </div>')
        planned = fam.get("planned", [])
        if planned:
            rows = "".join(
                f'\n      <tr><td style="white-space:nowrap"><b>{_planned_name(m)}</b></td><td>{m["note"]}</td></tr>'
                for m in planned)
            if len(planned) > 20:
                # 长表增强（P1-3）：过滤框 + 实时计数 + 吸顶 + 滚动容器。
                # 通用：任何家族 planned>20 自动获得，不写死 F9。
                n = len(planned)
                filter_box = (
                    f'<div class="plwrap">'
                    f'<input class="plfilter" type="search" placeholder="按名称/机制关键词过滤词条…" '
                    f'aria-label="过滤词条" data-plcount="{n}">'
                    f'<span class="plcount">显示 {n}/{n}</span></div>')
                secs.append(
                    f'<h2>词条（候选，独立页待建）</h2>\n'
                    f'{filter_box}'
                    f'<div class="tablewrap pltbl">\n  <table>'
                    f'\n    <tr><th>成员</th><th>机制 · 原始文献出处 · 报告锚点</th></tr>'
                    + rows + '\n  </table>\n  </div>')
            else:
                secs.append(
                    '<h2>词条（候选，独立页待建）</h2>\n  <div class="tablewrap">\n  <table>'
                    '\n    <tr><th>成员</th><th>机制 · 原始文献出处 · 报告锚点</th></tr>' + rows + '\n  </table>\n  </div>')

        sib_cards = "\n    ".join(
            f'<a class="card" href="/algo/{o["dir"]}/"><span class="ico">🧬</span>'
            f'<b>{o["name"]}</b><span>{o["oneliner"]}</span><span class="arrow">→</span></a>'
            for o in FAMILIES if o["id"] != fam["id"])

        desc_para = "".join(f"<p>{p}</p>" for p in fam["desc"])
        title = f'{fam["name"]} · 元启发式算法家族（F{fam["id"][1:]}）'
        fdesc = f'{fam["name"]}：{fam["oneliner"]} 收录成员、谱系链与改进维度分类。'
        write(fam_url.lstrip("/") + "index.html", inject_theme(FAMILY_TEMPLATE.format(
            site=SITE,
            path=fam_url,
            title=title,
            desc=fdesc,
            navlinks=navlinks(fam_url),
            fam_id=fam["id"],
            h1=fam["name"],
            en_summary=en_summary_html(fam.get("summary_en")),
            fam_oneliner=fam["oneliner"],
            fam_desc=desc_para,
            n_members=str(len(members)),
            fam_heading=_fam_heading(fam),
            members_cards=members_cards,
            chains_sec=(secs[0] if chains else ""),
            planned_sec=(secs[1] if chains and planned else (secs[0] if planned and not chains else "")),
            sib_cards=sib_cards,
            ldjson=ldjson(title, fdesc, kind="Article"),
        )))
        print(f"  家族页 {fam_url}（{len(members)} 成员）")


def _card_items(skip: str = ""):
    """相关页面条目源（单一来源）：算法全集 + 问题域/工具页。cards() 与 rel_list_html() 共用。"""
    items = []
    for a in ALGOS:
        if a["slug"] != skip:
            items.append((algo_url(a["slug"]), ICO.get(a["key"], "⚙"), a["name"],
                          _lead_clip(a)))
    items.extend([
        ("/problem/knapsack/", "🎒", "0-1 背包", f"二进制编码+贪心修复，{N_KS} 种算法"),
        ("/problem/continuous/", "⛰️", "连续函数基准", "PSO/DE/GWO 原生域，地形热力图"),
        ("/problem/multiobj/", "📊", "多目标 NSGA-II", "Pareto 前沿动画，双目标背包"),
        ("/problem/graphcolor/", "🎨", "图着色", "排列编码换解码器，DSJC 硬实例"),
        ("/problem/binpack/", "📦", "装箱 Bin Packing", "排列+First-Fit 解码，下界 LB 对照"),
        ("/problem/reductions/", "🕸️", "问题归约", "什么问题能变成什么问题：归约·等价·特例·推广"),
        ("/encyclopedia/", "📚", "百科总纲", "问题分类×维度×覆盖矩阵×术语表"),
        ("/compare/", "📊", "多算法横向对比", "同一实例跑遍所有算法，曲线叠加、结果排名"),
    ])
    return items


def cards(skip: str = "") -> str:
    return "\n    ".join(
        f'<a class="card" href="{h}"><span class="ico">{i}</span><b>{n}</b>'
        f'<span>{d}</span><span class="arrow">→</span></a>' for h, i, n, d in _card_items(skip))


def algo_depth_html(a: dict) -> str:
    """算法页的「来历、理论与批评」一节：来自 algos.json 的 origin / theory / variants / refs（缺任何一项就不出这一节）。"""
    if not (a.get("origin") and a.get("theory")):
        return ""
    parts = ['<h2 id="history">来历、理论与批评</h2>', '<h3>来历</h3>', a["origin"], '<h3>理论性质与已知批评</h3>', a["theory"]]
    if a.get("variants"):
        parts += ['<h3>常见变体</h3>', "<ul>" + "".join(f"<li>{v}</li>" for v in a["variants"]) + "</ul>"]
    if a.get("refs"):
        parts += ['<h3>延伸文献</h3>', '<ul class="refs">' + "".join(f"<li>{r}</li>" for r in a["refs"]) + "</ul>"]
    return "\n  ".join(parts)


def rel_list_html(skip: str = "") -> str:
    """相关页面（列表行版，算法页使用）。"""
    return ('<div class="rel-list">' + "\n".join(
        f'<a class="rel-row" href="{h}"><span class="ico">{i}</span><b>{n}</b>'
        f'<span class="rel-desc">{d}</span><span class="arrow">→</span></a>'
        for h, i, n, d in _card_items(skip)) + "\n</div>")


def bench_rows(highlight: str = "") -> str:
    out = []
    for name, vals in BENCH["rows"]:
        cls = ' class="hl"' if highlight and highlight in name else ""
        out.append(
            f'<tr{cls}><td>{name}</td><td class="num">{vals[0]}</td>'
            f'<td class="num">{vals[1]}</td><td class="num">{vals[2]}</td></tr>'
        )
    return "\n    ".join(out)


def _bench_best_100() -> str:
    """首页数据锚点（2026-09-27 毒舌走查 P2）：从 bench.json 现算 n=100 第一名，
    一句话让 landing 页有「凭什么信你」的即时证据。数据派生，禁硬编码。"""
    rows = [(n, v[2]) for n, v in BENCH["rows"] if not n.startswith("最近邻")]
    if not rows:
        return ""
    name, val = min(rows, key=lambda r: r[1])
    return (f'<div class="box" style="margin:10px 0"><b>实测锚点</b>：n=100 城全算法同台（单 seed 教学对照，前十差距 &lt;3% 统计并列）。'
            f'谁领跑、差距多少，见 <a href="/demo/">▶ 在线演示</a> 的完整成绩单与谱系映射；'
            f'所有实验可一键导出「实验包」（数据+算法源码+复跑说明）离线复跑。</div>')


def _bench_same_value_note() -> str:
    """成绩表「同值」说明：从 bench.json 现算收敛平台（P2⑤：同值≠数据复制，主播 D 事件）。"""
    from collections import Counter
    algo_rows = [r for r in BENCH["rows"] if not r[0].startswith("最近邻")
                 and not r[0].startswith("2-opt")]
    parts = []
    for col, label in ((0, "30 城"), (2, "100 城")):
        cnt = Counter(r[1][col] for r in algo_rows)
        # 只列占比显著的收敛平台（≥3 个算法同值）
        plats = [(v, n) for v, n in cnt.most_common(3) if n >= 3]
        if len(plats) >= 2:
            detail = "、".join(f"{v}（{n} 个算法停在这）" for v, n in plats)
            parts.append(f"{label}实例存在 {len(plats)} 个明显收敛平台：{detail}")
    if not parts:
        return ""
    return ("表里大量同值是正常现象：" + "；".join(parts) +
            "。200 代内许多算法会收敛到同一个（近似）最优解——同值 ≠ 数据复制错误，"
            "每一行都能用 bench.py 独立复现。")


def _tsp_bench_section() -> str:
    """TSP 枢纽页（/problem/tsp/）实测成绩段：与首页同一 bench.json 单一事实源。"""
    note = _bench_same_value_note()
    note_html = (f'  <p class="hint">{note}</p>\n' if note else "")
    return (f'<h2 id="bench">实测性能（TSP 基准 · {N_ALGOS} 算法同链对比）</h2>\n'
            f'  <p class="hint">{BENCH["caption"]}</p>\n'
            '  <div class="tablewrap">\n  <table>\n'
            '    <tr><th rowspan="2">算法</th>'
            '<th class="num" colspan="3">最优路径长（越小越好）</th></tr>\n'
            '    <tr><th class="num">30 城市</th><th class="num">60 城市</th>'
            '<th class="num">100 城市</th></tr>\n'
            f'    {bench_rows()}\n  </table>\n  </div>\n'
            + note_html +
            '  <p class="hint">同一台机器、同一随机实例、同为 200 代的结果。'
            '算法是随机的，换种子结果会浮动，别把 1% 的差距当结论。</p>')


def _bench_row_for(key: str, name: str):
    """algo key → bench.json 行。匹配策略：末段代码相同 + 中文前缀是算法名子串；
    已知歧义 cs（布谷鸟/乌鸦）靠中文名消歧；jaya 特判。"""
    if key == "jaya":
        return next((r for r in BENCH["rows"] if r[0].startswith("Jaya")), None)
    kn = key.upper()
    cands = [r for r in BENCH["rows"] if r[0].split()[-1].upper() == kn]
    zh = name.replace(" ", "")
    for r in cands:
        row_zh = "".join(r[0].split()[:-1])
        if row_zh and row_zh in zh:
            return r
    return cands[0] if len(cands) == 1 else None


def side_pane_html(a: Dict) -> Dict[str, str]:
    """v1.6 首屏右侧栏四卡（样张推广）：运行 / 30秒看懂 / 实测一句话 / 用别用。
    全部数据派生：params/principle 来自 algos.json（配方页传伪 dict），
    实测一句话来自 bench.json，用/别用是 algos.json 可选字段 use_when/avoid_when（无则不出卡）。"""
    key = a["key"]
    chips = "".join(
        f'<a class="chip mini" href="#params" title="{t}">{n} {d}</a>'
        for n, d, t in a.get("params", [])[:4])
    run_card = (f'<div class="side-card" style="text-align:center">'
                f'<button class="run-btn" id="runDemo" disabled>▶ 一键运行演示</button>'
                f'<div class="run-hint">默认参数已调好；打开页面会自动跑一遍给你看</div>'
                f'<div class="param-chips">{chips}</div></div>')
    quick_items = "".join(f"<li>{s}</li>" for s in a.get("principle", [])[:3])
    quick_card = (f'<div class="side-card"><h3>🧭 30 秒看懂</h3><ul>{quick_items}</ul>'
                  f'<div class="anchors"><a href="#how">算法原理 ↓</a>'
                  f'<a href="#params">全部参数 ↓</a></div></div>') if quick_items else ""
    bench_card = ""
    row = _bench_row_for(key, a["name"])
    if row:
        v = float(row[1][2])
        nn = float(next(r for r in BENCH["rows"] if r[0].startswith("最近邻"))[1][2])
        best = min(float(r[1][2]) for r in BENCH["rows"]
                   if not r[0].startswith("最近邻"))
        pct_nn = (nn - v) / nn * 100
        if v <= best:
            verdict = "本站 100 城实测榜首。"
        else:
            verdict = (f"落后榜首 {(v - best) / best * 100:.1f}%"
                       f"（{(v - best) / best * 100:.1f}% 内换种子可能反转，别当定论）。")
        bench_card = (
            '<div class="side-card"><h3>📏 实测一句话</h3><div class="mini-bars">'
            f'<div class="bar-row"><span class="lbl">最近邻 NN</span>'
            f'<div class="bar-track"><div class="bar-fill bf-nn" style="width:100%"></div></div>'
            f'<span class="val">{nn:.0f}</span></div>'
            f'<div class="bar-row"><span class="lbl">{row[0]}<span class="me-tag">本页</span></span>'
            f'<div class="bar-track"><div class="bar-fill bf-me" style="width:{v / nn * 100:.1f}%"></div></div>'
            f'<span class="val">{v:.0f}</span></div>'
            f'<div class="bar-row"><span class="lbl">实测榜首</span>'
            f'<div class="bar-track"><div class="bar-fill bf-best" style="width:{best / nn * 100:.1f}%"></div></div>'
            f'<span class="val">{best:.0f}</span></div></div>'
            f'<p class="hint">100 城 · 200 代 · seed=42 · 路径长越短越好</p>'
            f'<div class="verdict">比最近邻好 <b>{pct_nn:.0f}%</b>；{verdict}</div></div>')
    use_card = ""
    if a.get("use_when") and a.get("avoid_when"):
        use_card = (f'<div class="side-card"><h3>🎯 什么时候用 / 别踩的坑</h3>'
                    f'<div class="use-cols">'
                    f'<div class="u ok"><b>✅ 适合</b>{a["use_when"]}</div>'
                    f'<div class="u warn"><b>⚠️ 别指望</b>{a["avoid_when"]}</div>'
                    f'</div></div>')
    return {"run_card": run_card, "quick_card": quick_card,
            "bench_card": bench_card, "use_card": use_card}


ALGO_TAIL = """<script>
/* v1.6 首屏：一键运行 = 激活演示区真实「开始」按钮；引擎就绪后自动跑一遍，页面「活」给访客看 */
(function(){
  var btn=document.getElementById("runDemo");if(!btn)return;
  var timer=setInterval(function(){
    var real=document.getElementById("btnRun");
    if(real&&!real.disabled){
      clearInterval(timer);
      btn.disabled=false;
      btn.addEventListener("click",function(){
        document.getElementById("demoPane").scrollIntoView({behavior:"smooth",block:"start"});
        setTimeout(function(){if(!real.disabled)real.click();},350);
      });
      real.click();
      btn.textContent="▶ 再跑一遍";
    }
  },300);
  setTimeout(function(){clearInterval(timer);},60000);
})();
</script>"""


def ldjson(title: str, desc: str, kind: str = "SoftwareApplication") -> str:
    """结构化数据：交互演示页（内嵌 Pyodide 运行器）= SoftwareApplication；
    纯内容页（家族/配方/百科/矩阵/应用/组件/元层/问题内容页）= Article——
    给内容页盖 SoftwareApplication 的章属于类型语义错位（2026-09-26 IA 用户走查 P2）。"""
    d = {"@context": "https://schema.org", "@type": kind,
         "name": title, "description": desc}
    if kind == "SoftwareApplication":
        d["applicationCategory"] = "EducationalApplication"
        d["operatingSystem"] = "Any（浏览器）"
        d["offers"] = {"@type": "Offer", "price": "0", "priceCurrency": "CNY"}
    else:
        d["inLanguage"] = "zh-CN"
        d["isPartOf"] = {"@type": "WebSite", "name": "群智能算法百科", "url": SITE}
    return json.dumps(d, ensure_ascii=False)


def gen_overviews(write, _page, ldjson) -> None:
    """P2-2（2026-09-26 IA 用户走查）：/algo/ 算法总览 + /problem/ 问题总览。
    此前三大下拉按钮落点混乱：算法▾/科普▾ 同落 encyclopedia、问题▾ 落 knapsack 枢纽
    ——一级按钮应有自己的总览页，名实相符。全部数据派生，禁止硬编码条目。"""
    from pages_problems import _shell as _content_shell

    # ---------- /algo/ 算法总览 ----------
    rec_by_fam = _recipe_by_fam()
    fam_secs = []
    for f in FAMILIES:
        c = _fam_counts(f)
        members = [a for a in ALGOS if a.get("family") == f["id"]]
        chips = "".join(
            f'<a class="chip" href="{algo_url(a["slug"])}">{ICO.get(a["key"], "⚙")}&nbsp;{a["name"]}</a>'
            for a in members)
        chips += "".join(
            f'<a class="chip" href="/algo/{f["dir"]}/{r["id"]}/">🧪&nbsp;{r["name"]}</a>'
            for r in rec_by_fam.get(f["id"], []))
        chips += "".join(
            f'<a class="chip" href="{e["href"]}">{e["name"]}&nbsp;<span class="hint">{e.get("tag", "")}</span></a>'
            for e in f.get("nav_extra", []))
        hint = _fam_hint(c)
        # β3：planned 词条始终展示（前 6 个 chip），不再「仅空壳兜底」——F7 的
        # SPEA2/MOPSO/CMOEA 曾因 nav_extra 非空被兜底逻辑吞掉；F9 66 条展前 6 + 余量链接进家族页
        planned = f.get("planned", []) or []
        chips += "".join(
            f'<a class="chip dd-entry" href="{p.get("url") or "/algo/" + f["dir"] + "/"}"'
            f' title="{p.get("note", "")}">词条&nbsp;{p["name"]}</a>'
            for p in planned[:6])
        if len(planned) > 6:
            chips += (f'<a class="chip dd-entry" href="/algo/{f["dir"]}/">'
                      f'还有 {len(planned) - 6} 条词条 →</a>')
        fam_secs.append(
            f'<h2><a href="/algo/{f["dir"]}/">{f["name"]}</a>'
            f'<span class="hint">&nbsp;{hint}</span></h2>\n'
            f'  <div class="fambox"><div class="chips">{chips}</div></div>')
    n_rec = len(_recipe_data())
    algo_title = f"算法库总览 · {N_ALGOS} 算法 × 10 家族全图"
    algo_desc = (f"{N_ALGOS} 个元启发式算法按 F0-F9 十大家族分组：每家族的成员算法、升格配方、"
                 "域内实现与收录词条，一键进家族页或算法页；「算法」导航的总览落点。")
    algo_inner = (f'<div class="crumbs"><a href="/">首页</a> · 算法库总览</div>\n'
                  f'<h1>算法库总览</h1>\n'
                  f'<p class="lead">{N_ALGOS} 个实际算法（每个都带在线 TSP 求解演示）按十大家族展开，'
                  f'外加 {n_rec} 个不可跑算法的升格配方页。找具体算法用顶部「算法 ▾」下拉，'
                  f'横向对比去 <a href="/compare/">算法对比页</a>，入门科普去 <a href="/encyclopedia/">总纲</a>。</p>\n'
                  + "\n".join(fam_secs))
    html = _content_shell("/algo/", algo_title, algo_desc, algo_inner)
    write("algo/index.html", _page(html.replace(
        "<!--LDJSON-->", ldjson(algo_title, algo_desc, kind="Article"))))

    # ---------- /problem/ 问题总览 ----------
    atypes = PROBLEMS.get("abstract_types", [])
    a_pages = [t for t in atypes if t.get("status") == "page"]
    a_entries = [t for t in atypes if t.get("status") == "entry"]
    knap = PROBLEMS["knapsack_variants"]
    prob_secs = []
    for g, hub_h, hub_t in PROB_NAV_GROUPS:
        g_pages = [t for t in a_pages if t.get("group") == g and f"/problem/{t['dir']}/" != hub_h]
        g_entries = [t for t in a_entries if t.get("group") == g]
        head = f'<a href="{hub_h}">{hub_t}</a>' if hub_h else hub_t
        chips = ""
        if g == "subset":
            chips += "".join(f'<a class="chip" href="/problem/knapsack/{v["id"]}/">{v["name"]}</a>'
                             for v in knap)
        chips += "".join(f'<a class="chip" href="/problem/{t["dir"]}/">{t["name"]}'
                         f'{(" " + t["abbr"]) if t.get("abbr") else ""}</a>' for t in g_pages)
        chips += "".join(f'<a class="chip dd-entry" href="/problem/reductions/#grp-{g}">'
                         f'词条&nbsp;{t["name"]}{(" " + t["abbr"]) if t.get("abbr") else ""}</a>'
                         for t in g_entries)
        prob_secs.append(f'<h2>{PROB_NAV_LABEL.get(g, g)} · {head}</h2>\n'
                         f'  <div class="fambox"><div class="chips">{chips}</div></div>')
    demo_domains = (("knapsack", "0-1 背包"), ("continuous", "连续函数"),
                    ("multiobj", "多目标"), ("graphcolor", "图着色"), ("binpack", "装箱"), ("custom", "自带问题"))
    dom_chips = "".join(f'<a class="chip" href="/problem/{d}/">▶&nbsp;{n}在线演示</a>'
                        for d, n in demo_domains)
    prob_secs.append(f'<h2>在线求解演示域（换问题换编码，同一批算法）</h2>\n'
                     f'  <div class="fambox"><div class="chips">{dom_chips}</div></div>')
    prob_secs.append('<h2>全谱与归约</h2>\n'
                     '  <p>问题之间怎么互相变？<a href="/problem/reductions/">归约页 · 全谱词条登记</a>'
                     '——归约/等价/特例/推广四类关系带原始文献出处，选型前先查这张图。</p>')
    # β3：lead 数字全部数据派生，禁止硬编码——旧文案「×73 词条/29 个内容页/3 个枢纽」三处失真
    _n_cls = len(problem_groups.ORDER) - 1  # 不含「开放登记」
    prob_title = f"问题库总览 · {_n_cls} 类问题全图"
    _cls_names = "/".join(re.sub(r"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪ]+ ", "", problem_groups.NAV[g]) for g in problem_groups.ORDER[:-1])
    prob_desc = (f"元启发式问题库总览：{_n_cls} 个抽象类（{_cls_names}）的枢纽页、内容页与登记词条，"
                 "外加开放登记、在线求解演示域与问题归约全谱；「问题」导航的总览落点。")
    prob_inner = (f'<div class="crumbs"><a href="/">首页</a> · 问题</div>\n'
                  f'<h1>问题库总览</h1>\n'
                  f'<p class="lead">问题轴共 {len(atypes)} 个抽象类型：{len(a_pages)} 个建了独立内容页，'
                  f'{len(a_entries)} 个以词条登记（定义直达 <a href="/problem/reductions/">归约页</a>对应锚点）；'
                  f'另有 {len(knap)} 个背包变体页、{len(PROBLEMS["class_pages"])} 个类级枢纽'
                  f'（TSP / 分配 / QUBO）与 {len(demo_domains)} 个在线演示域。'
                  f'找具体问题用顶部「问题 ▾」下拉。</p>\n'
                  + "\n".join(prob_secs))
    html = _content_shell("/problem/", prob_title, prob_desc, prob_inner)
    write("problem/index.html", _page(html.replace(
        "<!--LDJSON-->", ldjson(prob_title, prob_desc, kind="Article"))))
    print(f"  总览页：/algo/（{len(FAMILIES)} 家族节）+ /problem/（{len(PROB_NAV_GROUPS)} 类节）")


def gen_guide(write, _page, ldjson) -> None:
    """/guide/：5 分钟上手。给第一次来的人一条最短路径：跑起来 → 换成自己的数据 → 拿到可复现的结果。
    数字（算法数、域数）全部取自数据层，不手写。"""
    from pages_problems import _shell as _content_shell

    title = "5 分钟上手 · 用自己的数据跑群智能算法"
    desc = "三步：在浏览器里跑起来、换成你自己的数据、导出可以复现的结果；也可以用命令行。数据只在你自己的电脑上处理。"
    inner = f"""<div class="crumbs"><a href="/">首页</a> · 5 分钟上手</div>
<h1>5 分钟上手</h1>
<p class="lead">这个站不只是介绍算法：{N_ALGOS} 个算法都能在浏览器里直接跑，你还可以换成<b>自己的数据</b>，再把<b>结果导出</b>、让别人复现。
全程在你自己的电脑上计算，数据不会上传到任何地方。</p>

<h2>第 1 步 · 跑起来（30 秒）</h2>
<ol>
  <li>打开 <a href="/demo/">▶ 演示</a>，等页面顶部状态变成「引擎就绪」（第一次要下载约 13 MB 的浏览器内 Python，请稍等几秒）。</li>
  <li>在「算法」里挑一个（比如粒子群、蚁群、遗传算法），点「开始」。左边是路线在一代代变短，右边是收敛曲线。</li>
  <li>想一步一步看就点「单步」；想换一批随机城市点「换一批城市」。</li>
</ol>
<p class="hint">打不开或一直「初始化中」？本站必须通过 http 访问（不能双击打开本地文件），浏览器需要 Chrome / Edge 111+、Firefox 114+ 或 Safari 16.4+。页面上方会写明具体原因。</p>

<h2>第 2 步 · 换成你自己的数据（2 分钟）</h2>
<p>不同问题的数据长得不一样，但入口一致：点页面上的「导入数据 / 导入实例」，选文件即可。导入前会先<b>校验</b>，哪里不对会指到具体位置（例如「items[3][0]：必须大于 0」），不会悄悄读错。</p>
<ul>
  <li><b>旅行商（TSP）</b>：演示页「导入数据」。支持坐标（JSON 或每行 <code>x,y</code> 的 CSV，也可带编号列）、标准 TSPLIB <code>.tsp</code> 文件、对称距离矩阵。4–500 个城市。</li>
  <li><b>背包、装箱、图着色、可满足性、QUBO、集合覆盖、指派、设施选址、连续函数、多目标……</b>：到 <a href="/problem/">问题</a> 里对应的页面，点「导入实例」。每个页面都有可下载的示例文件，改成你的数据即可。</li>
  <li><b>本站没有的问题</b>：到 <a href="/problem/custom/">自带问题</a>，选一种解的形状（是/否、排序、实数），写一个目标函数，现成的几十种算法立刻可用。写法见 <a href="/docs/custom-problems.md">自带问题说明</a>。</li>
  <li>所有格式和每个字段的含义见 <a href="/docs/data-formats.md">数据格式说明</a>。</li>
</ul>
<p><b>看清「保真度」</b>：问题页顶部的徽标说明这个模型有多贴近教科书定义——「标准」可以和文献对照；「教学简化」「示意模型」只是借这个问题的名字演示形态，<b>不能把结果当成该问题的结论</b>。导入数据时也会给出同样的提示。</p>

<h2>第 3 步 · 导出可复现的结果（1 分钟）</h2>
<p>运行结束后点「结果 JSON」（问题页是「导出结果」）。得到的文件里包含：完整实例、算法、随机种子、参数、逐代收敛曲线和最优解。把它发给别人，或自己留档，之后可以在任何装了 Python 的电脑上<b>复现并核对</b>：</p>
<pre><code>python swarm.py replay 结果.json</code></pre>
<p>输出「复现成功」说明同样的输入得到了逐点相同的曲线。格式见 <a href="/docs/result-format.md">结果文件格式</a>。</p>

<h2>不想开浏览器？用命令行</h2>
<p>只需要 Python 3.8+，不用装任何包（在项目目录里）：</p>
<pre><code>python swarm.py list                         # 有哪些问题域
python swarm.py list knapsack                # 某个域有哪些算法
python swarm.py template knapsack &gt; my.json  # 拿一份示例数据，改成你的
python swarm.py check my.json                # 只校验，不运行
python swarm.py solve my.json --algo ga --iters 200 --out result.json
python swarm.py compare my.json --algos all  # 所有算法同台比一比</code></pre>

<h2>结果怎么看才不容易误会</h2>
<ul>
  <li>页面上的对比表是<b>单个随机种子、单个实例</b>的结果，换个种子名次可能就变了。要下结论，请多换几个种子、几个实例再看。</li>
  <li>「最优」是这个算法这次找到的最好解，<b>不是</b>数学上证明的最优。</li>
  <li>浏览器里的 Python 比本机慢约 2 倍。实例很大时，页面会估算「预计还需多久」；某一步算得太久，会出现「强制停止并重载引擎」按钮。</li>
</ul>

<h2>接着看什么</h2>
<p><a href="/encyclopedia/#intro">什么是元启发式（3 分钟入门）</a> · <a href="/compare/">算法对比</a> · <a href="/algo/">算法库总览</a> · <a href="/problem/">问题库总览</a></p>
"""
    html = _content_shell("/guide/", title, desc, inner)
    write("guide/index.html", _page(html.replace("<!--LDJSON-->", ldjson(title, desc, kind="Article"))))
    print("  上手页：/guide/")


_EN_TITLES = None


def _en_titles():
    global _EN_TITLES
    if _EN_TITLES is None:
        with io.open(os.path.join(ROOT, "data", "meta.json"), encoding="utf-8") as _fm:
            _meta_pages = json.load(_fm)["pages"]
        _EN_TITLES = i18n_pages.build_table(ALGOS, FAMILIES, PROBLEMS, _meta_pages, algo_url,
                                            lambda f: f"/algo/{f['dir']}/")
    return _EN_TITLES


def write(path: str, content: str) -> None:
    # 相对路径改写：页面可能被 内置预览/file:///子目录部署 打开，
    # 根绝对路径（/css/...）在这些场景会 404 → 页面变裸 HTML。
    # 同时把目录式链接（.../algo/pso-tsp/）补全为 .../index.html——
    # file:// 下没有服务器做目录→index.html 的自动补全，目录链接会变成列表页。
    d = os.path.dirname(path.replace("\\", "/"))
    prefix = "" if not d else "../" * len(d.split("/"))
    root_link = prefix + "index.html"

    def _repl(m: "re.Match") -> str:
        attr, target = m.group(1), m.group(2)
        if target == "/":
            t = root_link
        else:
            t = prefix + target.lstrip("/")
            if t.endswith("/"):
                t += "index.html"
            else:
                # 锚点型目录链接（/encyclopedia/#intro、/problem/reductions/#e-vrp）：
                # file:// 下浏览器不做 目录→index.html 自动补全，必须显式补齐，
                # 否则点词条会落到目录列表页、锚点丢失（β 波 selfcheck 抓出的真 bug）
                if "#" in t:
                    head, frag = t.split("#", 1)
                    if head.endswith("/"):
                        t = head + "index.html#" + frag
        return f'{attr}="{t}"'

    # 只匹配以 / 开头的站内相对引用；canonical/og:url 是 http(s):// 开头，不受影响
    content = re.sub(r'(href|src)="(/[^"]*)"', _repl, content)
    # S5-A：SEO 增强（OG/Twitter/favicon/theme-color/面包屑 JSON-LD），重定向桩自动跳过
    content = seo_enhance.enhance(content, path, SITE, FAMILIES, ALGOS, PROBLEMS)
    content = i18n_pages.apply(path, content, _en_titles())  # 英文模式下 <title> / <h1> 的英文
    if not SITE:  # 没有站点根 URL 就不写需要绝对地址的标签（canonical/og:url/og:image/twitter:image）
        content = re.sub(r'<link rel="canonical" href="[^"]*">\n?', "", content)
        content = re.sub(r'<meta (?:property="og:(?:url|image)"|name="twitter:image") content="[^"]*">\n?', "", content)
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    try:
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
    except PermissionError:  # 只读文件（防编辑器污染的 attrib +R）：清位重写一次
        import stat as _stat
        os.chmod(full, _stat.S_IWRITE)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
    print(f"  生成 {path}  ({len(content)} 字节)")


def gen_solvers_src() -> None:
    """把 py/solvers.py 内嵌为 js/solvers_src.js —— 运行时零 fetch，
    免疫"宿主不为 .py 提供静态服务"的坑（预览代理/某些 CDN 回退场景）。"""
    comp_src = io.open(os.path.join(ROOT, "py", "components.py"), encoding="utf-8").read()
    # S7-B：recipe.py（七槽配方引擎）拼在 components 之后、solvers 之前——
    # solvers 尾部的 install_recipes 在拼接名字空间里直接取到 globals().get("install_recipes")
    recipe_src = io.open(os.path.join(ROOT, "py", "recipe.py"), encoding="utf-8").read()
    recipe_src = recipe_src.replace("from __future__ import annotations\n", "", 1)
    # v1.2 组件化：components 在前、solvers 在后拼进同一名字空间执行
    # __future__ import 只能出现在文件开头；拼接后它在中间会语法错误，
    # 而拼接执行时注解里的 typing 名字均已可解析，剥离无害（本地运行不受影响）
    solvers_body = io.open(os.path.join(ROOT, "py", "solvers.py"), encoding="utf-8").read()
    solvers_body = solvers_body.replace("from __future__ import annotations\n", "", 1)
    tax_src = io.open(os.path.join(ROOT, "py", "taxonomy.py"), encoding="utf-8").read()
    py_src = tax_src + "\n\n" + comp_src + "\n\n" + recipe_src + "\n\n" + solvers_body
    out = (
        "// AUTO-GENERATED by build_pages.py —— 请勿手改；改 py/solvers.py 后重新构建\n"
        "export const SOLVERS_SRC = "
        + json.dumps(py_src, ensure_ascii=False)
        + ";\n"
        "export const VALIDATE_SRC = "
        + json.dumps(io.open(os.path.join(ROOT, "py", "validate.py"), encoding="utf-8").read(), ensure_ascii=False)
        + ";\n"
    )
    with open(os.path.join(ROOT, "js", "solvers_src.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    print(f"  生成 js/solvers_src.js  ({len(out)} 字节, 内嵌 {len(py_src)} 字符 Python 源码)")


def gen_domains_src() -> None:
    """v0.8：把 py/domains.py（问题域引擎）内嵌为 js/domains_src.js，同上零 fetch。
    S1-1 组件化：domain_components 在前、domains 在后拼进同一名字空间执行——
    domains.py 里的 `from domain_components import ...` 在拼接执行时抛
    ImportError → except 分支跳过（名字已在空间内），与 solvers 侧同款双环境机制。"""
    dcomp_src = io.open(os.path.join(ROOT, "py", "domain_components.py"), encoding="utf-8").read()
    # 域引擎源码在 py/domains_parts/ 的各分块里（py/domains.py 只是本地的装载器）：按文件名顺序拼接 = 本地装载时的执行顺序
    parts_dir = os.path.join(ROOT, "py", "domains_parts")
    domains_body = "".join(io.open(os.path.join(parts_dir, f), encoding="utf-8").read()
                           for f in sorted(os.listdir(parts_dir)) if f.endswith(".py"))
    # entryseq 词条域独立成模块：拼在 domains 之前，domains 里的 `from entryseq import ...` 在拼接环境抛 ImportError 后跳过
    entryseq_src = io.open(os.path.join(ROOT, "py", "entryseq.py"), encoding="utf-8").read()
    # 自带问题（custom 域）同理：userproblem 拼在 domains 之前（tests/test_userproblem.py 守卫：两者顶层名字不得冲突）
    userproblem_src = io.open(os.path.join(ROOT, "py", "userproblem.py"), encoding="utf-8").read()
    # 连续多目标基准（mocont 域）同理，拼在 domains 之前
    mocont_src = io.open(os.path.join(ROOT, "py", "mocont.py"), encoding="utf-8").read()
    sched_src = io.open(os.path.join(ROOT, "py", "scheduling.py"), encoding="utf-8").read()
    sched_src = sched_src.replace(
        "from domains import _sw_random, _sw_hc, _sw_sa, _sw_ts  # noqa: E402",
        "# 浏览器拼接环境：四内核已在同名字空间（domains 段在前），无需 from-import")
    tax_src = io.open(os.path.join(ROOT, "py", "taxonomy.py"), encoding="utf-8").read()
    py_src = (tax_src + "\n\n" + dcomp_src + "\n\n" + entryseq_src + "\n\n" + userproblem_src + "\n\n" + mocont_src + "\n\n"
              + domains_body + "\n\n" + sched_src + "\n\n"
              + "# --- 浏览器拼接环境排程装配（与 domains 末尾 try-import 等价）---\n"
              + "import types as _types_mod\n"
              + "_schedmod = _types_mod.SimpleNamespace(\n"
              + "    _SCHED_ALGOS=_SCHED_ALGOS, _SCHED_DEF=_SCHED_DEF,\n"
              + "    nrp_make=nrp_make, etp_make=etp_make, tour_make=tour_make, sls_make=sls_make,\n"
              + "    sched_start=sched_start, sched_step=sched_step, sched_list=sched_list,\n"
              + "    sched_preset=sched_preset, sched_bench=sched_bench)\n"
              + "_wire_sched_domains(_schedmod)\n")
    # UX 走查 P0-1（2026-09-26）：domains.py 顶部 `from domain_components import ... as _pm_*`
    # 在浏览器拼接环境抛 ImportError 被 try/except 吞掉，带下划线别名从未绑定，
    # 排列域 5 算法（hc/sa/ga/abc/woa）在 9 个页面 NameError 崩溃。拼接后显式绑定
    # 别名（无下划线原名本就在空间内），使浏览器产物与本地/pytest 名字空间一致。
    py_src += ("\n\n# --- 浏览器拼接环境别名绑定（与 try-import 分支等价；本地重复赋值无害）---\n"
               "_pm_insert = pm_insert; _pm_ox = pm_ox; _pm_polish = pm_polish; _pm_swap = pm_swap\n")
    # 标准化数据层（校验器）随引擎一起内嵌：worker 里把它注册成名为 validate 的模块
    validate_src = io.open(os.path.join(ROOT, "py", "validate.py"), encoding="utf-8").read()
    out = (
        "// AUTO-GENERATED by build_pages.py —— 请勿手改；改 py/domains.py / py/validate.py 后重新构建\n"
        "export const DOMAINS_SRC = "
        + json.dumps(py_src, ensure_ascii=False)
        + ";\n"
        "export const VALIDATE_SRC = "
        + json.dumps(validate_src, ensure_ascii=False)
        + ";\n"
    )
    with open(os.path.join(ROOT, "js", "domains_src.js"), "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    print(f"  生成 js/domains_src.js  ({len(out)} 字节, 内嵌 {len(py_src)} 字符 Python 源码)")


def main() -> None:
    print("生成静态站…")
    gen_solvers_src()
    gen_domains_src()

    # v1.8 问题域 + 百科页（pages_domains.py 收到 write/inject_theme 等依赖，避免循环导入）
    from pages_domains import generate as gen_domain_pages
    _page_shared = gen_domain_pages(write, inject_theme, navlinks, ldjson, SITE,
                                    mapping_ctx={pid: roster_html(pid) + reduction_neighbors_html(pid)
                                                 for pid in PROBLEM_INDEX})

    # S3 问题轴：背包变体子页 ×7 + P3/P8 类页 + 归约页（复用同一 _page 闭包）
    from pages_domains import ABSTRACT_DEMO, CLASS_DEMO, VARIANT_DEMO, demo_fragment_html
    from pages_problems import generate as gen_problem_pages
    gen_problem_pages(write, _page_shared, ldjson,
                      mapping_ctx={"roster": {pid: roster_html(pid) for pid in PROBLEM_INDEX},
                                   "line": {pid: reduction_neighbors_html(pid) for pid in PROBLEM_INDEX},
                                   "demo": {**{k: demo_fragment_html(v) for k, v in ABSTRACT_DEMO.items()},
                                            **{k: demo_fragment_html(v) for k, v in CLASS_DEMO.items()},
                                            **{k: demo_fragment_html(v) for k, v in VARIANT_DEMO.items()},
                                            "tsp": TSP_DEMO_BANNER},
                                   "bench_section": _tsp_bench_section(),
                                   "reductions_inner": reductions_inner_html()})

    # P2-2：算法/问题总览页（一级导航按钮的名实相符落点）
    gen_overviews(write, _page_shared, ldjson)
    gen_guide(write, _page_shared, ldjson)

    # S4 元层轴 + 矩阵层 + 应用地图（同一页面壳）
    from pages_meta import generate as gen_meta_pages
    gen_meta_pages(write, _page_shared, ldjson)

    # 首页
    write("index.html", inject_theme(HOME.format(
        site=SITE,
        navlinks=navlinks("/"),
        cards=cards(),
        bench=bench_rows(),
        bench_caption=BENCH["caption"],
        algo_count=N_ALGOS,
        n=N_KS,
        n_domains=N_DOMAINS,
        solver_pages=N_SOLVER_PAGES,
        entry_count=N_REDUCTION_ENTRIES,
        bench_best=_bench_best_100(),
        ldjson=ldjson("群智能算法百科 · 首页",
                      f"{N_ALGOS} 个元启发式算法 × 10 家族 × {N_SOLVER_PAGES} 个可跑问题页的在线百科"),
    )))

    # TSP 演示专页（2026-09-27 首页改版：首页去 TSP 一言堂，demo+TSP 三表挪 /demo/）
    write("demo/index.html", inject_theme(DEMO_PAGE.format(
        site=SITE,
        navlinks=navlinks("/demo/"),
        bench=bench_rows(),
        bench_caption=BENCH["caption"],
        algo_count=N_ALGOS,
        ldjson=ldjson("TSP 巡回演示 · 智能优化算法在线求解",
                      f"{N_ALGOS} 种智能优化算法求解 TSP 的在线演示：路径动画、收敛曲线与实测成绩单"),
    )))

    # 家族页（S2-B：F0-F9 一家族一页）
    gen_family_pages()

    # 配方页（S7-B：七槽组合配方，数据源 py/recipe.py）
    gen_recipe_pages()

    # 算法页（S2-B：迁入家族路径，旧 URL 生成重定向桩；v1.6 首屏改版 + 映射卡）
    # ILS 同名跨族消歧（2026-09-29）：正典条目 key 与配方 id 撞名时页头互挂提示（通用规则）。
    _rby_id: dict = {}
    for _r in _recipe_data():
        _rby_id.setdefault(_r["id"], _r)
    for a in ALGOS:
        u = algo_url(a["slug"])
        fam = FAM_BY_ID[FAM_OF[a["slug"]]]
        _side = side_pane_html(a)
        intro_html = "\n  ".join(f"<p>{p}</p>" for p in a["intro"])
        _r = _rby_id.get(a["key"])
        if _r is not None:
            _ru = f'/algo/{FAM_BY_ID[_r["lineage"]["family"]]["dir"]}/{_r["id"]}/'
            intro_html = (f'\n  <p class="hint" id="name-disambig">⚗ 同名消歧：本页是 <b>{a["name"]}</b> 的'
                          f'<b>经典算法条目</b>（手写实现）；另有同名<b>七槽组合配方</b>页（组件装配视角，'
                          f'同问题同口径实测）→ <a href="{_ru}">{_r["name"]}</a>。</p>\n  ' + intro_html)
        write(u.lstrip("/") + "index.html", inject_theme(TEMPLATE.format(
            site=SITE,
            path=u,
            fam_dir=fam["dir"],
            fam_name=fam["name"],
            family_box=family_box(a["slug"]),
            title=a["title"], desc=a["desc"], h1=a["h1"], lead=a["lead"], en_summary=en_summary_html(a.get("summary_en")), key=a["key"],
            intro=intro_html,
            principle="\n    ".join(f"<li>{s}</li>" for s in a["principle"]),
            params="\n    ".join(
                f'<tr><td><code>{n}</code></td><td class="num">{d}</td><td>{t}</td></tr>' for n, d, t in a["params"]
            ),
            bench=bench_rows(a["name"]),
            bench_caption=BENCH["caption"],
            faq="\n  ".join(
                f'<details class="faq-item"><summary>{q}</summary><div class="faq-body">{ans}</div></details>'
                for q, ans in a["faq"]
            ),
            rel_list=rel_list_html(a["slug"]),
            depth=algo_depth_html(a),
            map_card=mapping_card_html(a["key"]),
            paper=a["paper"],
            navlinks=navlinks(u),
            ldjson=ldjson(a["title"], a["desc"]),
            **_side,
        )).replace("<!--ALGO_TAIL-->", ALGO_TAIL))
        # 旧 URL（algo/<slug>-tsp/）重定向桩：SEO 外链不断链
        write(f'algo/{a["slug"]}/index.html', redirect_stub(u, a["title"]))

    # 家族重整（data/moved_pages.json）后迁走的算法页：旧地址留重定向桩，外链/书签不断
    _alg_by_key = {x["key"]: x for x in ALGOS}
    for m in MOVED_PAGES:
        _a = _alg_by_key[m["slug"]]
        write(f'algo/{m["from_dir"]}/{m["slug"]}/index.html',
              redirect_stub(f'/algo/{m["to_dir"]}/{m["slug"]}/', _a["title"], depth=3))

    # 对比页
    write("compare/index.html", inject_theme(COMPARE.format(
        site=SITE,
        navlinks=navlinks("/compare/"),
        cards=cards(),
        algo_count=N_ALGOS,
        ldjson=ldjson("智能优化算法性能对比",
                      f"{N_ALGOS} 种智能优化算法求解 TSP 的横向对比与收敛曲线叠加"),
    )))

    # 英文词典：data/i18n/*.json（合并）→ js/i18n_en.js（只在英文模式下由 js/i18n.js 加载；不经 write()，避免链接被改写）
    _i18n = {"strings": {}, "patterns": []}
    for _fn in sorted(os.listdir(os.path.join(ROOT, "data", "i18n"))):
        if _fn.endswith(".json"):
            with io.open(os.path.join(ROOT, "data", "i18n", _fn), encoding="utf-8") as _fi:
                _part = json.load(_fi)
            _i18n["strings"].update(_part.get("strings", {}))
            _i18n["patterns"].extend(_part.get("patterns", []))
    with io.open(os.path.join(ROOT, "js", "i18n_en.js"), "w", encoding="utf-8", newline="\n") as _fo:
        _fo.write("/* AUTO-GENERATED from data/i18n_en.json by build_pages.py — do not edit. */\n"
                  "window.I18N_EN = " + json.dumps(_i18n, ensure_ascii=False, separators=(",", ":")) + ";\n")
    print(f"  生成 js/i18n_en.js  （{len(_i18n['strings'])} 条词典，{len(_i18n['patterns'])} 条模式）")

    # sitemap / robots
    # Keep committed output stable across rebuild dates; do not claim every page changed today.
    urls = ([("/", "1.0"), ("/demo/", "0.9")]
            + [("/algo/", "0.9"), ("/problem/", "0.9"), ("/guide/", "0.9")]
            + [(algo_url(a["slug"]), "0.9") for a in ALGOS]
            + [(f'/algo/{f["dir"]}/', "0.8") for f in FAMILIES]
            + [("/compare/", "0.9"), ("/encyclopedia/", "0.9"), ("/components/", "0.9"),
               ("/problem/knapsack/", "0.9"), ("/problem/continuous/", "0.9"), ("/problem/multiobj/", "0.9"),
               ("/problem/graphcolor/", "0.9"), ("/problem/binpack/", "0.9"),
               ("/problem/custom/", "0.9"), ("/problem/reductions/", "0.8"), ("/coverage/", "0.9"),
               ("/discovery/", "0.8")]  # setcover/sat/qubo/uflp 已在 class_pages 段（终审B：勿重复）
            + [(f"/problem/knapsack/{v['id']}/", "0.8") for v in PROBLEMS["knapsack_variants"]]
            + [(f"/problem/{c['dir']}/", "0.9") for c in PROBLEMS["class_pages"]]
            + [(f"/problem/{t['dir']}/", "0.8")
               for t in PROBLEMS.get("abstract_types", []) if t.get("status") == "page"]
            + [(f"/algo/{FAM_DIR_BY_ID[r['lineage']['family']]}/{r['id']}/", "0.8")
               for r in _recipe_data()]
            + [(f"/meta/{p['dir']}/", "0.9") for p in json.load(io.open(os.path.join(ROOT, "data", "meta.json"), encoding="utf-8"))["pages"]]
            + [("/matrix/", "0.9"), ("/applications/", "0.9")])
    if SITE:
        write("sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
              + "\n".join(f"  <url><loc>{SITE}{u}</loc><priority>{p}</priority></url>" for u, p in urls)
              + "\n</urlset>\n")
        write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    else:
        write("robots.txt", "User-agent: *\nAllow: /\n")
        _sm = os.path.join(ROOT, "sitemap.xml")
        if os.path.exists(_sm):
            os.remove(_sm)

    # 终审B 事故守卫自动化：编辑器标签页会把 data-page-node-id 写回构建产物，
    # 构建收尾统一剥离一遍（写入窗口期的残留在此兜底）
    import re as _re
    _cleaned = 0
    for _root, _dirs, _files in os.walk(ROOT):
        if ".git" in _root:
            continue
        for _f in _files:
            if not _f.endswith(".html"):
                continue
            _fp = os.path.join(_root, _f)
            _c = io.open(_fp, encoding="utf-8").read()
            if "data-page-node-id" in _c:
                io.open(_fp, "w", encoding="utf-8", newline="").write(
                    _re.sub(r'\s*data-page-node-id="[^"]*"', "", _c))
                _cleaned += 1
    if _cleaned:
        print(f"  已剥离 {_cleaned} 个页面的编辑器污染属性")

    # S5-A：404 页（GitHub Pages 等静态托管用；含导航回退）
    _notfound = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>404 · 页面不存在 · 群智能算法百科</title>
<meta name="description" content="页面不存在。从首页、百科总纲、交叉矩阵或应用地图任一入口回到群智能算法百科。">
<meta name="robots" content="noindex">
<!--THEME_HEAD-->
<link rel="stylesheet" href="/css/style.css">
</head>
<body>
{navlinks("")}
<main class="wrap" style="text-align:center; padding: 72px 20px;">
  <p style="font-size: 64px; margin: 0;">🧭</p>
  <h1>404 · 这个页面不存在的解</h1>
  <p class="sub" style="max-width: 520px; margin: 12px auto 28px;">
    元启发式连最优化都不保证，更别说保证每个 URL 都有效。从下面任一入口回到正轨：</p>
  <p>
    <a class="btn" href="/">返回首页</a>
    <a class="btn" href="/encyclopedia/">百科总纲</a>
    <a class="btn" href="/matrix/">SOTA 矩阵</a>
    <a class="btn" href="/applications/">应用地图</a>
  </p>
</main>
<!--THEME_TAIL-->
</body>
</html>
"""
    write("404.html", inject_theme(_notfound))

    from site_search_index import generate as _generate_site_search_index
    _search_count, _search_bytes = _generate_site_search_index(ROOT)
    print(f"  全站搜索索引：{_search_count} 条，{_search_bytes // 1024} KB")

    print(f"完成：{len(ALGOS)} 个算法页 + {len(FAMILIES)} 个家族页 + 首页 + 对比页")


if __name__ == "__main__":
    main()

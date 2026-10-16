# -*- coding: utf-8 -*-
"""S3 问题轴渲染器：从 data/problems.json 生成
① /problem/tsp/         TSP 旗舰枢纽页（Ⅰ 排序与巡回类枢纽 + 45 算法实测成绩单档案）
② /problem/knapsack/<id>/ 背包变体子页 ×10
③ /problem/assignment/  P3 分配/选址类页
④ /problem/qubo/        P8 逻辑/密码类页
页面骨架走 pages_domains 的 _page 闭包（导航/主题/LDJSON 全套继承）。
"""
import io, json, os
import i18n_pages

ROOT = os.path.dirname(os.path.abspath(__file__))


def _chips(badges):
    span = "".join(f'<span class="chip"><b>{b["k"]}</b>&nbsp;{b["v"]}</span>' for b in badges)
    return f'<div class="fambox"><div class="chips">{span}</div></div>'


def _sources_html(sources):
    if not sources:
        return ""
    lis = "".join(f"<li>{s}</li>" for s in sources)
    return f'<h2>出处与经典文献</h2><ul class="src">{lis}</ul>'


def _shell(path, title, desc, inner):
    """静态内容页完整壳：head（title/description/canonical）+ 导航 + 正文 + 页尾。
    与 _interactive_page 同构；主题/导航由 _page 闭包注入（THEME_HEAD/BTN/TAIL、NAVLINKS、SITE）。"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<!--THEME_HEAD-->
<link rel="stylesheet" href="/css/style.css">
<link rel="canonical" href="<!--SITE-->{path}">
<script type="application/ld+json"><!--LDJSON--></script>
</head>
<body>
<a class="skip-link" href="#main">跳到主内容</a>
<nav class="nav"><div class="nav-inner">
  <a class="brand" href="/"><span class="logo">🐝</span>群智能算法百科</a>
  <div class="nav-links">
  <!--NAVLINKS-->
  </div>
  <!--THEME_BTN-->
</div></nav>

<div class="wrap" id="main" role="main">
{inner}
</div>
<footer>
</footer>
<!--THEME_TAIL-->
</body>
</html>
"""


def _opt_sections(t):
    """深度条目的可选段落：计算复杂度与可近似性 / 基准实例与已知结果 / 本站的建模方式（字段缺省则不出现）。"""
    out = ""
    for key, title in (("complexity", "计算复杂度与可近似性"), ("benchmarks", "基准实例与已知结果"), ("site_model", "本站的建模方式")):
        if t.get(key):
            out += f"\n  <h2>{title}</h2>\n  {t[key]}"
    return out


def _variant_page(v, siblings, extra="", demo=None):
    """背包变体子页：面包屑 + 徽章 + 三段正文 + [H1]在线求解演示 + 出处 + 归约邻居 + 兄弟变体导航。"""
    sib = "".join(f'<a class="chip" href="/problem/knapsack/{s["id"]}/">{s["name"]}</a>'
                  for s in siblings)
    ks_variants_html = f"""
  <h2>背包变体谱系（本站 {len(siblings) + 1} 页）</h2>
  <div class="fambox"><div class="chips">
    <a class="chip" href="/problem/knapsack/"><b>0-1 背包</b>&nbsp;枢纽·在线演示</a>
    {sib}
  </div></div>"""
    html = f"""
  <div class="crumbs"><a href="/problem/knapsack/">背包</a> · {v["name"]}</div>
  <div class="hero">
    <h1>{v["name"]} <span class="grad">{v["en"]}{("（" + v["abbr"] + "）") if v.get("abbr") else ""}</span></h1>
    <div class="sub">{v["tier"]} · Feng 2026 三级分类框架（<i>Neurocomputing</i> 666:132135）</div>
  </div>
  {i18n_pages.en_summary(v.get("summary_en"))}
  {_chips(v["badges"])}
  <h2>数学模型</h2>
  {v["model"]}
  <h2>与 0-1 背包的差异</h2>
  {v["diff"]}
  <h2>求解路径</h2>
  {v["algo"]}{_opt_sections(v)}
  {demo or ""}
  {extra}
  {_sources_html(v["sources"])}
  {ks_variants_html}
"""
    return html


def _class_page(c, extra="", demo=None):
    """P3/P8 类页：面包屑 + 引言 + [G 期]在线求解演示 + 分节正文 + roster/归约邻居 + 出处。"""
    secs = "".join(f'\n  <h2>{s["h2"]}</h2>\n  {s["html"]}' for s in c["sections"])
    html = f"""
  <div class="crumbs"><a href="/">首页</a> · 问题 · {c["name"]}</div>
  <div class="hero">
    <h1>{c["name"]} <span class="grad">{c["en"]}</span></h1>
    <div class="sub">{c["lead"]}</div>
  </div>
  {i18n_pages.en_summary(c.get("summary_en"))}
  {c["intro"]}
  {demo or ""}
  {secs}
  {extra}
  {_sources_html(c["sources"])}
"""
    return html


NO_DEMO_BANNER = ('<div class="fambox"><p class="hint">📖 <b>内容页 · 无在线演示</b>'
                  '——本站求解引擎尚未接入本问题的实例跑分；下方「哪些算法能治」仅挂'
                  '<b>文献级</b>映射（每条带来源），不虚构实测成绩。'
                  '问题谱系见 <a href="/problem/reductions/">归约页</a>。</p></div>')


def hub_banner(href, name):
    """无本域引擎、但枢纽页有同族演示时的横幅：诚实说明 + 跳转链接。"""
    return (f'<div class="fambox"><p class="hint">📖 <b>内容页 · 本变体无专属引擎</b>'
            f'——该变体（结构扩展型）本站未建独立求解器，不虚构实测成绩；'
            f'其所属问题族的<b>基础型在线演示</b>在 {name}，'
            f'欢迎先跑一轮建立直觉。问题谱系见 <a href="/problem/reductions/">归约页</a>。</p></div>'
            f'<div class="fambox"><div class="chips">'
            f'<a class="chip" href="{href}"><b>▶ 去枢纽页演示</b>&nbsp;{name}</a>'
            f'</div></div>')


# 无本域引擎但有同族枢纽演示的抽象页 id → (href, 枢纽名)
# 注：H2/H3 已建引擎的抽象页（lcp/ecp/prext/tcp/mis/bpp2d/spp/vsbpp/bbob/maop）
# 已内嵌专属演示，不再走枢纽跳转横幅。
HUB_LINK = {}


import problem_groups  # noqa: E402
GROUP_LABEL = problem_groups.LABEL  # 来源：data/problem_groups.json


def _abstract_page(t, extra="", demo=None, hub=None):
    """抽象类型内容页（G 期起：有引擎→内嵌在线求解演示；无引擎但有同族枢纽→
    横幅+跳转链接；否则诚实横幅）+ 四段式（定义/差异/求解路径/出处）+ roster。"""
    group = GROUP_LABEL.get(t.get("group"), t.get("group", ""))
    banner = demo if demo else (hub_banner(*hub) if hub else NO_DEMO_BANNER)
    html = f"""
  <div class="crumbs"><a href="/">首页</a> · 问题 · <a href="/problem/reductions/">抽象类型谱</a> · {t["name"]}</div>
  <div class="hero">
    <h1>{t["name"]} <span class="grad">{t["en"]}（{t["abbr"]}）</span></h1>
    <div class="sub">抽象问题类型 · {group}</div>
  </div>
  {i18n_pages.en_summary(t.get("summary_en"))}
  {banner}
  {_chips(t["badges"])}
  <h2>抽象定义</h2>
  {t["model"]}
  <h2>与同族问题的结构差异</h2>
  {t["diff"]}
  <h2>求解路径</h2>
  {t["algo"]}{_opt_sections(t)}
  {extra}
  {_sources_html(t["sources"])}
"""
    return html


def knapsack_variants_nav(data):
    """供背包枢纽页插入的变体导航块（pages_domains 调用）。"""
    chips = "".join(
        f'<a class="chip" href="/problem/knapsack/{v["id"]}/">{v["name"]}<span class="hint">（{v["tier"].split(" ")[0]}）</span></a>'
        for v in data["knapsack_variants"])
    return f"""
  <h2>变体谱系（一变体一子页）</h2>
  <p class="hint">0-1 背包是家族原点；{len(data["knapsack_variants"])} 个变体按 Feng 2026 三级分类展开（① 简单单目标 → ② 结构扩展 → ③ 多目标线见<a href="/problem/multiobj/">多目标页</a>）。每个子页含数学模型 / 与 0-1 的差异 / 求解路径 / 原始文献出处；有公认学术缩写的变体在标题中标注。</p>
  <div class="fambox"><div class="chips">
    <a class="chip" href="/problem/knapsack/"><b>0-1 背包</b>&nbsp;枢纽·演示</a>
    {chips}
  </div></div>"""


def _seq_entries_chips(data, group: str) -> str:
    """类枢纽页「同族词条」段：该组词条级成员（status=entry，只登记不建页）。
    数据派生自 abstract_types，禁止硬编码；词条统一落到归约页组锚点。"""
    ents = [t for t in data.get("abstract_types", [])
            if t.get("group") == group and t.get("status") == "entry"]
    if not ents:
        return ""
    chips = "".join(f'<a class="chip" href="/problem/reductions/#grp-{group}">{t["name"]}'
                    f'{(" " + t["abbr"]) if t.get("abbr") else ""}</a>' for t in ents)
    return (f'<h2>同族词条（{GROUP_LABEL.get(group, group)} · {len(ents)} 条）</h2>\n'
            f'  <p class="hint">词条级成员：只登记词条、不单独建页，全谱与归约关系见 '
            f'<a href="/problem/reductions/#grp-{group}">归约页</a>。</p>\n'
            f'  <div class="fambox"><div class="chips">{chips}</div></div>')


def load_data():
    return json.load(io.open(os.path.join(ROOT, "data", "problems.json"), encoding="utf-8"))


def generate(write, _page, ldjson, mapping_ctx=None):
    """入口：build_pages.main 传入 write / _page 闭包 / ldjson / mapping_ctx（P1 映射层片段）。"""
    data = load_data()
    sibs = data["knapsack_variants"]
    mapping_ctx = mapping_ctx or {}
    _roster = mapping_ctx.get("roster", {})
    _line = mapping_ctx.get("line", {})

    # ① 背包变体子页 ×10（挂归约邻居 + [H1]变体专属演示；fractional/multidim/subsetsum 等有归约关系）
    _demos = mapping_ctx.get("demo", {})
    for v in sibs:
        path = f"/problem/knapsack/{v['id']}/"
        abbr_tail = f", {v['abbr']}" if v.get("abbr") else ""
        html = _shell(path, f"{v['name']}（{v['en']}{abbr_tail}）· 背包问题变体",
                      f"{v['name']}：数学模型、与 0-1 背包的差异、求解路径与原始文献出处（{v['tier']}）",
                      _variant_page(v, sibs, extra=_line.get(v["id"], ""),
                                    demo=_demos.get(v["id"])))
        write(f"problem/knapsack/{v['id']}/index.html", _page(html.replace(
            "<!--LDJSON-->", ldjson(f"{v['name']}（{v['en']}{abbr_tail}）· 背包变体",
                                    f"{v['name']}的数学模型、与 0-1 背包的差异与求解路径", kind="Article"))))

    # ② P3 / P8 类页（G 期：有引擎的类页内嵌在线求解演示 + 「哪些算法能治」roster + 归约邻居）
    #    + TSP 旗舰枢纽（2026-09-26）：roster + 实测成绩表 + 同族词条，demo=首页引擎横幅
    for c in data["class_pages"]:
        path = f"/problem/{c['dir']}/"
        lead_clip = c["lead"][:150]
        extra = _roster.get(c["dir"], "") + _line.get(c["dir"], "")
        if c["dir"] == "tsp":
            extra = (_roster.get(c["dir"], "") + mapping_ctx.get("bench_section", "")
                     + _seq_entries_chips(data, "sequencing") + _line.get(c["dir"], ""))
        html = _shell(path, f"{c['name']} · 元启发式问题库", lead_clip,
                      _class_page(c, extra=extra, demo=_demos.get(c["dir"])))
        write(f"problem/{c['dir']}/index.html", _page(html.replace(
            "<!--LDJSON-->", ldjson(f"{c['name']} · 元启发式问题库 P 轴", c["lead"], kind="Article"))))

    # ②-b 抽象类型内容页（G 期：有引擎→内嵌演示；有同族枢纽→横幅+链接；否则诚实横幅）
    for t in data.get("abstract_types", []):
        if t.get("status") != "page":
            continue
        path = f"/problem/{t['dir']}/"
        title = f"{t['name']}（{t['en']}, {t['abbr']}）· 抽象问题类型"
        desc = f"{t['name']}（{t['abbr']}）：抽象定义、与背包家族的结构差异、求解路径与原始文献出处（归类锚 {t['gj']}）。"
        html = _shell(path, title, desc, _abstract_page(
            t, extra=_roster.get(t["id"], ""),
            demo=_demos.get(t["id"]), hub=HUB_LINK.get(t["id"])))
        write(f"problem/{t['dir']}/index.html", _page(html.replace(
            "<!--LDJSON-->", ldjson(title, desc, kind="Article"))))

    # ③ P1 映射层：问题归约页（什么问题能变成什么问题）
    if mapping_ctx.get("reductions_inner"):
        path = "/problem/reductions/"
        title = "问题归约 · 什么问题能变成什么问题"
        desc = ("问题↔问题的归约、等价、特例与推广关系图：装箱↔划分、TSP↔QAP、图着色/TSP→QUBO 等，"
                "每条关系带原始文献出处——选问题前先查这张图。")
        html = _shell(path, title, desc, mapping_ctx["reductions_inner"])
        write("problem/reductions/index.html", _page(html.replace(
            "<!--LDJSON-->", ldjson(title, desc, kind="Article"))))

    print(f"  问题轴：{len(sibs)} 个背包变体页 + {len(data['class_pages'])} 个类页"
          f" + {sum(1 for t in data.get('abstract_types', []) if t.get('status') == 'page')} 个抽象类型页"
          + (" + 归约页" if mapping_ctx.get("reductions_inner") else ""))

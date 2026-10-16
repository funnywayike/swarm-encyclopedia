# -*- coding: utf-8 -*-
"""S4 元层/矩阵/应用地图渲染器：从 data/meta.json + matrices.json + apps.json 生成
① /meta/<dir>/ 元层四页（理论/批评史/方法学/时间轴）
② /matrix/ 交叉矩阵页（X1-X4，X4 实测表直接读 data/bench.json）
③ /applications/ 应用地图（13 行业 × 96 条目，索引层防膨胀）
页面壳复用 pages_problems._shell（单一来源）。
"""
import io, json, os, re
import i18n_pages

import problem_groups
from pages_problems import _shell

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    return json.load(io.open(os.path.join(ROOT, "data", name), encoding="utf-8"))


def _meta_chips(cur=""):
    data = _load("meta.json")
    chips = []
    for m in data["pages"]:
        style = ' style="border-color:var(--accent)"' if m["id"] == cur else ""
        chips.append(f'<a class="chip"{style} href="/meta/{m["dir"]}/">{m["ico"]}&nbsp;{m["name"]}</a>')
    return "".join(chips)


def _meta_page(p):
    """P2：节标题挂佐证上标 [n]（跳页尾列表），页尾渲染「佐证与出处」区（维基式）。"""
    refs = p.get("refs", [])
    rid_idx = {r["id"]: i + 1 for i, r in enumerate(refs)}

    def _sup(ids):
        ids = [i for i in (ids or []) if i in rid_idx]
        if not ids:
            return ""
        links = "".join(f'<a href="#ref-{i}">[{rid_idx[i]}]</a>' for i in ids)
        return f'<sup class="refsup">{links}</sup>'

    secs = "".join(f'\n  <h2>{s["h2"]}{_sup(s.get("refs"))}</h2>\n  {s["html"]}'
                   for s in p["sections"])
    reflist = ""
    if refs:
        items = "".join(
            f'<li id="ref-{r["id"]}">'
            + (f'<a href="{r["url"]}" target="_blank" rel="noopener">{r["cite"]}</a>'
               if r.get("url") else r["cite"])
            + "</li>"
            for r in refs)
        reflist = (f'<h2>佐证与出处</h2>\n  <p class="hint">维基式尾部佐证：每条对应正文节标题的上标编号，'
                   f'含学术文献与公开网络来源。</p>\n  <ol class="reflist">{items}</ol>')
    return f"""
  <div class="crumbs"><a href="/">首页</a> · 科普 · {p["name"]}</div>
  <div class="hero">
    <h1>{p["name"]} <span class="grad">{p["en"]}</span></h1>
    <div class="sub">{p["lead"]}</div>
  </div>
  {i18n_pages.en_summary(p.get("summary_en"))}
  {secs}
  {reflist}
  <h2>元层四页导航</h2>
  <div class="fambox"><div class="chips">{_meta_chips(cur=p["id"])}</div></div>
"""


# P1-7：矩阵单元格里已知问题 → 问题页深链（相对路径，矩阵页在 /matrix/ 故用 ../problem/<slug>/）。
# 仅对「还没有 <a> 链接」的单元格挂链，绝不破坏 matrices.json 里已有的手写链接。
# 只挂已存在页面（token → 真实页面 slug），禁止造新键新页。
_PROBLEM_TOKENS = [
    ("图着色", "../problem/graphcolor/"),
    ("连续无约束", "../problem/continuous/"),
    ("连续优化", "../problem/continuous/"),
    ("连续", "../problem/continuous/"),
    ("多目标", "../problem/multiobj/"),
    ("背包", "../problem/knapsack/"),
    ("装箱", "../problem/binpack/"),
    ("分配", "../problem/assignment/"),
    ("QAP", "../problem/assignment/"),
    ("UFLP", "../problem/uflp/"),
    ("选址", "../problem/uflp/"),
    ("SAT", "../problem/sat/"),
    ("集合覆盖", "../problem/setcover/"),
]
# 最长 tok 优先编译成单个交替正则——杜绝「连续优化」挂链后又被「连续」二次包裹；
# SAT 仅当独立成词时命中（避免误挂 DSATUR 这类算法名）
_TOK_HREF = dict(_PROBLEM_TOKENS)
_TOK_RE = re.compile(
    "|".join(
        (re.escape(tok) if tok != "SAT" else r"\bSAT\b")
        for tok in sorted(_TOK_HREF, key=len, reverse=True)
    )
)


def _link_problems(cell: str) -> str:
    if "<a " in cell or "<a>" in cell:
        return cell  # 已有链接（matrices.json 手写），不重复挂
    # 目标用户走查 P1（2026-09-27）：旧实现逐 tok 循环 replace，先挂上「连续优化」的
    # <a> 后又命中更短的「连续」tok 再次包裹 → 产物出现非法嵌套 <a>（浏览器提前
    # 闭合外层锚）。改为：最长 tok 优先、正则整体交替匹配、每个 cell 只挂第一处。
    m = _TOK_RE.search(cell)
    if not m:
        return cell
    tok = m.group(0)
    href = _TOK_HREF[tok]
    return cell.replace(tok, f'<a href="{href}">{tok}</a>', 1)


def _matrix_table(m):
    head = "".join(f"<th>{c}</th>" for c in m["cols"])
    body = "".join("<tr>" + "".join(f"<td>{_link_problems(c)}</td>" for c in row) + "</tr>" for row in m["rows"])
    return f'<div class="tablewrap"><table><tr>{head}</tr>{body}</table></div>'


def _x4_table():
    """X4 本站实测：直接读 data/bench.json（单一事实源）。
    算法名→链接：先精确匹配 name，再用 bench 名末尾缩写词匹配 algos.json 的 key（PSO/ACO/FA…）；
    基线行（最近邻 NN/2-opt）无对应算法页，保持纯文本。"""
    bench = _load("bench.json")
    algos = _load("algos.json")
    fams = _load("families.json")
    fd = {f["id"]: f["dir"] for f in fams}
    by_name = {a["name"]: a for a in algos}
    by_key = {}
    for a in algos:
        k = (a.get("key") or "").upper()
        if k and a.get("family") in fd:
            by_key.setdefault(k, a)
    def _link(name):
        a = by_name.get(name)
        if a is None:
            for tok in name.replace("-", " ").split():
                if tok.upper() in by_key:
                    a = by_key[tok.upper()]
                    break
        if a and a.get("family") in fd:
            return f'<a href="/algo/{fd[a["family"]]}/{a["slug"][:-4]}/">{name}</a>'
        return name
    size_cols = ["n=40", "n=60", "n=80"]
    rows = []
    for name, costs in bench["rows"]:
        cells = "".join(f'<td class="num">{c}</td>' for c in costs)
        rows.append(f"<tr><td>{_link(name)}</td>{cells}</tr>")
    head = "".join(f"<th>{c}</th>" for c in ["算法", *size_cols])
    return (f'<p class="hint">{bench["caption"]}</p>'
            f'<div class="tablewrap"><table><tr>{head}</tr>{"".join(rows)}</table></div>')


def _abstract_index():
    """F 期：抽象类型索引（X0）——十大类 × 成员内容页/词条数，数据驱动自 problems.json。
    每类一行：类名 | 内容页链接（名+缩写） | 词条数 → 归约页全谱锚点。X1-X4 不动。"""
    probs = _load("problems.json")
    atypes = probs.get("abstract_types", [])
    pages = [t for t in atypes if t.get("status") == "page"]
    entries = [t for t in atypes if t.get("status") == "entry"]
    labels = problem_groups.SHORT
    rows = []
    for g in problem_groups.ORDER:
        g_pages = [t for t in pages if t.get("group") == g]
        n_ent = len([t for t in entries if t.get("group") == g])
        links = "、".join(
            f'<a href="/problem/{t["dir"]}/">{t["name"]}'
            f'{("（" + t["abbr"] + "）") if t.get("abbr") else ""}</a>'
            for t in g_pages)
        ent_cell = (f'<a href="/problem/reductions/#grp-{g}">词条 ×{n_ent} → 全谱</a>'
                    if n_ent else "—")
        rows.append(f"<tr><td><b>{labels[g]}</b></td><td>{links or '—'}</td>"
                    f"<td>{ent_cell}</td></tr>")
    body = "".join(rows)
    return ('<div class="tablewrap"><table><tr><th>抽象类型</th><th>内容页</th>'
            f'<th>词条级登记</th></tr>{body}</table></div>')


def _matrix_page():
    m = _load("matrices.json")
    return f"""
  <div class="crumbs"><a href="/">首页</a> · 交叉矩阵层</div>
  <div class="hero">
    <h1>交叉矩阵 <span class="grad">X1-X4：两轴之间的桥</span></h1>
    <div class="sub">算法轴 × 问题轴的交叉信息只住在这里——矩阵单元格链接到对应页面，正文永不复制第二遍。</div>
  </div>
  <h2>X0 · 问题轴抽象类型索引</h2>
  <p class="hint">十大抽象类（罗马编号与导航/归约页一致）× 各类已建内容页与词条登记——进入 X1 家族 × 问题域之前的定位表。</p>
  {_abstract_index()}
  <h2>{m["x1"]["title"]}</h2>
  <p class="hint">{m["x1"]["hint"]}</p>
  {_matrix_table(m["x1"])}
  <h2>{m["x2"]["title"]}</h2>
  <p class="hint">{m["x2"]["hint"]}</p>
  {_matrix_table(m["x2"])}
  <h2>{m["x3"]["title"]}</h2>
  <p class="hint">{m["x3"]["hint"]}</p>
  {_matrix_table(m["x3"])}
  <h2>{m["x4"]["title"]}</h2>
  <p class="hint">{m["x4"]["hint"]}</p>
  {_x4_table()}
"""


def _apps_page():
    data = _load("apps.json")
    cats = data["categories"]
    entries = data["entries"]
    by_cat = {c["id"]: [] for c in cats}
    for e in entries:
        by_cat[e["cat"]].append(e)
    by_ind = {ind: [] for ind in data["industries"]}
    for e in entries:
        by_ind[e["industry"]].append(e)
    # F 期：abstract_type → 链接（内容页直链 / 词条与属级 → 归约页锚点）
    probs = _load("problems.json")
    atypes = probs.get("abstract_types", [])
    abs_href, abs_name = {}, {}
    for t in atypes:
        if t.get("status") == "page":
            abs_href[t["id"]] = f'/problem/{t["dir"]}/'
            abs_name[t["id"]] = t["name"]
    for t in atypes:
        g = t.get("group", "")
        if g and g not in abs_href:
            abs_href[g] = f'/problem/reductions/#grp-{g}'
            abs_name[g] = g

    def row(e):
        """舒适列表行：名称 + 一句话 + 行业徽章 + 抽象类型徽章 + 出处（而非卡片网格糊一屏）。
        目标用户走查 P1（2026-09-27）：外层 <a> 内嵌徽章 <a> 是非法嵌套——浏览器强制提前
        闭合外层锚，行后半段脱链。改为 div 行 + 标题主链接，徽章链接得以存活。"""
        badge = f'<span class="badge">{e["industry"]}</span>'
        a_h = abs_href.get(e.get("abstract_type", ""))
        a_n = abs_name.get(e.get("abstract_type", ""), e.get("abstract_type", ""))
        abs_badge = (f'<a class="badge badge-link" href="{a_h}" title="抽象类型：{a_n}">'
                     f'{e["abstract_type"]}</a>' if a_h else "")
        tail = f'<span class="hint">报告 {e["src"]}</span>'
        if e["link"]:
            return (f'<div class="approw"><b><a href="{e["link"]}">{e["title"]}</a></b>'
                    f'<span class="desc">{e["oneliner"]}</span>{badge}{abs_badge}{tail}</div>')
        return (f'<div class="approw" style="opacity:.72"><b>{e["title"]}</b>'
                f'<span class="desc">{e["oneliner"]}</span>{badge}{abs_badge}'
                f'<span class="hint">词条 · 报告 {e["src"]}</span></div>')

    def navcards(groups, href_prefix, items):
        """导航卡组：图标 + 名称 + 数量 + 一句话说明，点击跳到对应区块。"""
        return ('<div class="catnav">' + "".join(
            f'<a href="#{href_prefix}-{g["id"] if "id" in g else i}"><span class="ico">{g.get("ico", "🏭")}</span>'
            f'<b>{g["name"]}</b><span class="hint">{len(items[g["id"] if "id" in g else i])} 块 · {g["hint"]}</span></a>'
            for i, g in enumerate(groups)) + "</div>")

    # ① 主视图：按问题形态（导航卡 → 区块锚点 → 列表行）
    cat_chips = "".join(f'<a class="chip" href="#cat-{c["id"]}">{c["ico"]}&nbsp;{c["name"]}&nbsp;{len(by_cat[c["id"]])}</a>'
                        for c in cats)
    cat_secs = "".join(
        f'<section class="appsec"><h2 id="cat-{c["id"]}">{c["ico"]} {c["name"]}'
        f'<span class="hint">（{len(by_cat[c["id"]])}）</span></h2>\n'
        f'  <p class="hint">{c["hint"]}</p>\n'
        f'  <div class="applist">{"".join(row(e) for e in by_cat[c["id"]])}</div></section>'
        for c in cats)
    # ② 对照视图：按行业（同构排版）
    ind_chips = "".join(f'<a class="chip" href="#ind-{i}">{ind}&nbsp;{len(by_ind[ind])}</a>'
                        for i, ind in enumerate(data["industries"]))
    ind_secs = "".join(
        f'<section class="appsec"><h2 id="ind-{i}">{ind}'
        f'<span class="hint">（{len(by_ind[ind])}）</span></h2>\n'
        f'  <div class="applist">{"".join(row(e) for e in by_ind[ind])}</div></section>'
        for i, ind in enumerate(data["industries"]))

    n = len(entries)
    return f"""
  <div class="crumbs"><a href="/">首页</a> · 应用地图</div>
  <div class="hero">
    <h1>应用地图 <span class="grad">{n} 块 · 双维度导航</span></h1>
    <div class="sub">211 轮文献挖掘沉淀的应用域全景——按<b>问题形态</b>分 9 类（主视图），按<b>行业</b>分 13 类（对照视图），一键切换。每条只做索引：一句话 → 指向问题类页 + 报告出处节号。VRP/车间调度/动态优化域按冻结条款只出词条不建页。</div>
  </div>
  <div class="viewbar" role="tablist" aria-label="应用地图视图切换">
    <button class="viewbtn is-active" id="btn-cat" type="button" onclick="_appsView('cat')">📐 按问题类别</button>
    <button class="viewbtn" id="btn-ind" type="button" onclick="_appsView('ind')">🏭 按行业</button>
  </div>
  <div id="apps-cat">
    {navcards(cats, "cat", by_cat)}
    {cat_secs}
  </div>
  <div id="apps-ind" hidden>
    <div class="fambox"><div class="chips">{ind_chips}</div></div>
    {ind_secs}
  </div>
  <script>
  function _appsView(v) {{
    document.getElementById('apps-cat').hidden = v !== 'cat';
    document.getElementById('apps-ind').hidden = v !== 'ind';
    document.getElementById('btn-cat').classList.toggle('is-active', v === 'cat');
    document.getElementById('btn-ind').classList.toggle('is-active', v === 'ind');
  }}
  </script>
"""


def generate(write, _page, ldjson):
    meta = _load("meta.json")
    # ① 元层四页
    for p in meta["pages"]:
        path = f"/meta/{p['dir']}/"
        html = _shell(path, f"{p['name']} · 元启发式元层方法论",
                      p["lead"][:150], _meta_page(p))
        write(f"meta/{p['dir']}/index.html", _page(html.replace(
            "<!--LDJSON-->", ldjson(f"{p['name']}（{p['en']}）· 元启发式科普", p["lead"][:150], kind="Article"))))
    # ② 交叉矩阵页
    mx = _shell("/matrix/", "交叉矩阵 X1-X4 · 家族×问题×编码×算子×实测",
                "算法轴与问题轴的交叉信息层：SOTA 矩阵、编码适配、算子经典与本站实测。", _matrix_page())
    write("matrix/index.html", _page(mx.replace(
        "<!--LDJSON-->", ldjson("交叉矩阵 X1-X4 · 元启发式百科",
                                "家族×问题 SOTA、算法×编码、问题×算子与本站实测四张矩阵", kind="Article"))))
    # ③ 应用地图
    apps = _load("apps.json")
    ap = _shell("/applications/",
                f"应用地图 · {len(apps['entries'])} 应用块 · {len(apps['categories'])} 问题类别 × {len(apps['industries'])} 行业",
                "元启发式应用域全景导航：问题形态 9 类 ⇄ 行业 13 类双视图，条目链接到问题页与文献综述出处。", _apps_page())
    write("applications/index.html", _page(ap.replace(
        "<!--LDJSON-->", ldjson("应用地图 · 元启发式百科",
                                f"{len(apps['entries'])} 个应用块按 {len(apps['categories'])} 类问题形态与 {len(apps['industries'])} 个行业的双维度导航索引", kind="Article"))))
    print(f"  元层：{len(meta['pages'])} 页 + 矩阵页 + 应用地图页（{len(apps['entries'])} 条目）")

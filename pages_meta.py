# -*- coding: utf-8 -*-
"""S4 元层/矩阵/应用地图渲染器：从 data/meta.json + matrices.json + apps.json 生成
① /meta/<dir>/ 元层科普页与研究地图（理论/批评史/方法学/时间轴/研究主干地图）
② /matrix/ 交叉矩阵页（X1-X4，X4 实测表直接读 data/bench.json）
③ /applications/ 应用地图（13 行业 × 96 条目，索引层防膨胀）
页面壳复用 pages_problems._shell（单一来源）。
"""
import io, json, os, re, html
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
        style = ' aria-current="page" style="border-color:var(--accent)"' if m["id"] == cur else ""
        chips.append(f'<a class="chip"{style} href="/meta/{m["dir"]}/">{m["ico"]}&nbsp;{m["name"]}</a>')
    return "".join(chips)


def _meta_page(p):
    from pages_science import render_science
    return render_science(p, _meta_chips, i18n_pages.en_summary)


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
    research_refs = {r["id"]: r for r in _load("research_map.json")["references"]}
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
        abs_badge = (f'<a class="badge badge-link" href="{a_h}" title="关联模型（具体约束见研究出处）：{a_n}">'
                     f'{e["abstract_type"]}</a>' if a_h else "")
        tail = '<span class="hint">' + ' · '.join(
            '<a href="' + html.escape(research_refs[r]["url"], quote=True) + '" target="_blank" rel="noopener">研究出处</a>'
            for r in e.get("researchRefs", []) if r in research_refs) + '</span>' 
        if e["link"]:
            return (f'<div class="approw"><b><a href="{e["link"]}">{e["title"]}</a></b>'
                    f'<span class="desc">{e["oneliner"]}</span>{badge}{abs_badge}{tail}</div>')
        return (f'<div class="approw" style="opacity:.72"><b>{e["title"]}</b>'
                f'<span class="desc">{e["oneliner"]}</span>{badge}{abs_badge}'
                f'{tail}</div>')

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
    <div class="sub">从代表性研究了解不同应用——按<b>问题形态</b>分 9 类（主视图），按<b>行业</b>分 13 类（对照视图），一键切换。每条提供一句话介绍、代表性研究出处和相关模型入口。问题页用于理解模型，不表示已实现论文的行业系统或全部业务约束。</div>
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



def _research_map_page(p):
    """证据卡式研究导览：并行主线、研究群体、应用问题与可追溯来源。"""
    from pages_reviews import render_review_panel
    data = _load("research_map.json")
    data["readingViews"] = _load("research_reading_views.json")
    for n in data["nodes"]:
        n["apps"] = [data["readingViews"]["applicationAliases"].get(x, x) for x in n.get("apps", [])]
    embedded = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return r"""
  <div class="crumbs"><a href="/">首页</a> · 科普 · 研究主干地图 <span class="hint">研究资料持续补充</span></div>
  <div id="rm-reader">
  <div class="hero">
    <h1>研究主干地图 <span class="grad">Research Field Map</span></h1>
    <div class="sub">从问题出发，看方法怎样发展、谁推动了哪些研究、论文证据能说明什么。</div>
  </div>
  <div class="rm-intro">
    <p><b>不是一条算法排行榜。</b>困难优化问题、进化计算、群智能、群体机器人、实验基准和自动算法设计各有自己的问题；它们在混合求解、学习辅助和真实应用中交汇。</p>
    <p class="hint">这是可追溯来源的代表性研究导览，不是全球论文目录、团队排名或穷尽式系统综述。每个节点都说明主要贡献与证据边界；新近综述、预印本、基准项目分别标注。</p>
  </div>
  <div class="rm-stats" id="rm-stats" aria-live="polite"></div>
  <div class="rm-reader-bar">
    <div class="rm-mode-buttons" role="group" aria-label="选择阅读重点">
      <button type="button" data-reading-mode="overview" aria-pressed="true">总览脉络</button>
      <button type="button" data-reading-mode="algorithm" aria-pressed="false">关注算法</button>
      <button type="button" data-reading-mode="problem" aria-pressed="false">关注问题</button>
    </div>
    <p class="hint" id="rm-reading-note"></p>
    <div class="rm-focus-row">
      <label id="rm-method-wrap" hidden>添加方法（可多选） <select id="rm-method"></select></label>
      <label id="rm-problem-wrap" hidden>添加问题或应用（可多选） <select id="rm-problem"></select></label>
      <button type="button" id="rm-reset">恢复默认显示</button>
    </div>
    <div id="rm-selected-topics" class="rm-selected-topics" aria-live="polite"></div>
    <details class="rm-custom">
      <summary>自定义显示 · 主线、年代与阅读细节</summary>
      <p class="hint">主线、年代、关键词和主题共同筛选历史地图；来源与边界开关作用于本页各视图。切换阅读模式会恢复完整主线和年代。</p>
      <fieldset class="rm-choice"><legend>研究主线（可多选）</legend><div id="rm-lane-choices"></div><button type="button" data-select-group="lanes" data-action="all">全选</button><button type="button" data-select-group="lanes" data-action="none">清空</button></fieldset>
      <fieldset class="rm-choice"><legend>年代（可多选）</legend><div id="rm-band-choices"></div><button type="button" data-select-group="bands" data-action="all">全选</button><button type="button" data-select-group="bands" data-action="none">清空</button></fieldset>
      <fieldset class="rm-choice"><legend>信息层次</legend>
        <label><input type="checkbox" data-reading-option="milestones">只看关键节点</label>
        <label><input type="checkbox" data-reading-option="compact">精简节点文字</label>
        <label><input type="checkbox" data-reading-option="details">显示节点详情</label>
        <label><input type="checkbox" data-reading-option="sources">显示参考来源</label>
        <label><input type="checkbox" data-reading-option="boundaries">显示适用范围与边界</label>
        <label><input type="checkbox" data-reading-option="context">带上有明确关系的邻接节点</label>
        <label><input type="checkbox" data-reading-option="connections">显示当前节点之间的关联</label>
      </fieldset>
    </details>
  </div>
  <div class="rm-tabs" role="tablist" aria-label="研究地图视图">
    <button class="rm-tab is-active" role="tab" aria-selected="true" data-view="history">历史与交汇</button>
    <button class="rm-tab" role="tab" aria-selected="false" data-view="teams">研究团队与社区</button>
    <button class="rm-tab" role="tab" aria-selected="false" data-view="applications">应用问题</button>
    <button class="rm-tab" role="tab" aria-selected="false" data-view="industry">13个领域的研究证据</button>
    <button class="rm-tab" role="tab" aria-selected="false" data-view="questions">研究难点与中文阅读</button>
    <button class="rm-tab" role="tab" aria-selected="false" data-view="reviews">综述与交叉验证</button>
    <button class="rm-tab" role="tab" aria-selected="false" data-view="coverage">文献与本站演示</button>
  </div>
  <section class="rm-panel" id="rm-view-history" role="tabpanel">
    <div class="rm-controls">
      <label>查找节点 <input id="rm-search" type="search" placeholder="试试：物流、群机器人、基准、LLM"></label>
      <div class="rm-layout-buttons" role="group" aria-label="地图排列方式"><button type="button" data-reading-layout="timeline">时间地图</button><button type="button" data-reading-layout="list">紧凑列表</button></div>
      <span class="hint" id="rm-count" aria-live="polite"></span>
    </div>
    <div class="rm-crossroads">
      <div><b>问题结构 ↔ 搜索邻域</b><span>路线、排程和约束决定怎样改方案</span></div>
      <div><b>群体搜索 ↔ 局部改进</b><span>保留多种候选，也可嵌入领域搜索</span></div>
      <div><b>群智能 ↔ 群体机器人</b><span>思想有关，研究对象和评价方式不同</span></div>
      <div><b>算法设计 ↔ 实验证据</b><span>新方法要靠公开测试和强基线来检验</span></div>
    </div>
    <p class="hint rm-instruction">时间按年代分栏，六行是并行研究线；点任一节点，查看贡献、团队/应用关联和引用来源。向右滑动可查看较新的研究。分支间的具体联系见“研究难点与中文阅读”。</p>
    <div class="rm-scroll" tabindex="0" aria-label="可横向滚动的研究时间地图"><div id="rm-history"></div></div>
    <article id="rm-detail" class="rm-detail" aria-live="polite"></article>
    <div id="rm-visible-relations" class="rm-visible-relations"></div>
  </section>
  <section class="rm-panel" id="rm-view-teams" role="tabpanel" hidden>
    <p class="hint">这些是有论文、实验室或基准维护记录支持的研究群体示例。它们不是全球团队排名；一篇论文的作者单位也不足以单独证明一个长期“学派”。</p>
    <div id="rm-teams" class="rm-cards"></div>
  </section>
  <section class="rm-panel" id="rm-view-applications" role="tabpanel" hidden>
    <p class="hint">从人们真实要做的决定出发，再对应问题模型、研究方法和验证要求。行业名相同，不代表优化模型相同。</p>
    <div id="rm-applications" class="rm-cards"></div>
  </section>
  <section class="rm-panel" id="rm-view-industry" role="tabpanel" hidden>
    <p class="hint">从能源、农业、交通到金融、医疗和创意应用，逐个领域了解算法研究解决了什么问题、有哪些代表性研究，以及结果适用于什么范围。卡片提供的是阅读入口，不代表已覆盖该领域全部论文，也不把相邻研究强行归为群智能。</p>
    <div id="rm-industry-coverage" class="rm-intro"></div>
    <div id="rm-industries" class="rm-cards"></div>
  </section>
  <section class="rm-panel" id="rm-view-questions" role="tabpanel" hidden>
    <p class="hint">研究的推进不只有新算法名称。这些问题解释了为什么需要新的机制、模型和评测方法，并提供中文与外文阅读入口。</p>
    <div id="rm-questions" class="rm-cards"></div>
    <h2>分支怎样关联</h2>
    <p class="hint">每条关系注明是机制发展、领域应用还是对照；先后出现不自动表示师承或影响。</p>
    <div id="rm-relations" class="rm-cards"></div>
  </section>
  <section class="rm-panel" id="rm-view-coverage" role="tabpanel" hidden>
    <p>论文里的算法、本站的演示和真实行业系统，各自有具体范围。这里逐项说明对应关系，帮助你选择阅读与试验入口。</p>
    <p class="hint" id="rm-coverage-note"></p>
    <details class="rm-sources"><summary>45 个算法：出处与演示中的适配</summary><div id="rm-algorithm-coverage"></div></details>
    <details class="rm-sources"><summary>96 个问题条目：模型范围与简化说明</summary><div id="rm-problem-coverage"></div></details>
  </section>
  __REVIEW_PANEL__
  <section class="rm-guide">
    <h2>读论文时，怎样判断“这个算法更好”？</h2>
    <ol id="rm-guide"></ol>
    <p class="hint">研究依据与范围说明：<span id="rm-method-note"></span></p>
  </section>
  <details class="rm-sources rm-citations"><summary>佐证与出处 · 展开全部研究来源与资料索引</summary><ol id="rm-ref-index"></ol></details>
  <h2>继续探索</h2>
  <div class="fambox"><div class="chips">__META_CHIPS__</div></div>
  <style>

    .rm-reader-bar{border:1px solid var(--line);border-radius:14px;background:var(--surface);padding:14px 18px;margin:16px 0}
    .rm-selected-topics{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px}.rm-mode-buttons,.rm-layout-buttons,.rm-focus-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
    .rm-reader-bar button,.rm-layout-buttons button{font:inherit;color:var(--ink);background:var(--surface-2);border:1px solid var(--line);border-radius:8px;padding:7px 12px;cursor:pointer}
    .rm-reader-bar button[aria-pressed="true"],.rm-layout-buttons button[aria-pressed="true"]{background:var(--accent);color:#fff;border-color:var(--accent)}
    .rm-focus-row label{display:flex;align-items:center;gap:8px;flex-wrap:wrap}.rm-focus-row select{font:inherit;max-width:100%;padding:7px;border:1px solid var(--line);background:var(--surface);color:var(--ink);border-radius:8px}
    .rm-custom{margin-top:12px;border-top:1px solid var(--line);padding-top:10px}.rm-custom summary{cursor:pointer}
    .rm-choice{border:1px solid var(--line);border-radius:9px;margin:10px 0;padding:10px}.rm-choice legend{font-weight:600}.rm-choice label{display:inline-flex;align-items:center;gap:5px;margin:5px 13px 5px 0;font-size:.88rem}.rm-choice input{accent-color:var(--accent)}.rm-choice button{padding:3px 9px;margin:4px 6px 0 0;font-size:.82rem}
    #rm-reader [hidden]{display:none!important}
    .rm-hide-sources .rm-citations,.rm-hide-boundaries .rm-boundary{display:none!important}
    .rm-node-summary{display:block;margin-top:6px;font-size:.78rem;font-weight:400;color:var(--ink-2)}
    .rm-context{border-style:dashed}.rm-node-list{padding:12px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.rm-node-list>div{min-width:0}.rm-node-list .rm-node{height:calc(100% - 26px);font-size:.9rem}
    .rm-visible-relations:empty{display:none}.rm-visible-relations{margin:18px 0}.rm-visible-relations p{line-height:1.8}
    @media(max-width:600px){.rm-node-list{grid-template-columns:1fr}.rm-focus-row label{width:100%}.rm-focus-row select{width:100%}.rm-reader-bar{padding:12px}.rm-mode-buttons button{flex:1;padding:8px}}
    .rm-intro,.rm-guide,.rm-detail{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:18px 20px;margin:14px 0}
    .rm-intro p{margin:.4em 0}.rm-stats{display:flex;flex-wrap:wrap;gap:9px;margin:16px 0}.rm-stat{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:9px 13px}.rm-stat b{font-size:1.18rem;color:var(--accent)}
    .rm-tabs{display:flex;gap:8px;flex-wrap:wrap;border-bottom:1px solid var(--line);margin:22px 0 14px}.rm-tab{border:1px solid var(--line);border-radius:10px 10px 0 0;padding:10px 15px;background:var(--surface);color:var(--ink);cursor:pointer;font:inherit}.rm-tab.is-active{border-color:var(--accent);background:var(--accent);color:#fff;font-weight:700}
    .rm-controls{display:flex;align-items:end;gap:12px;flex-wrap:wrap;margin:14px 0}.rm-controls label{display:grid;gap:5px;font-size:.88rem}.rm-controls input,.rm-controls select{border:1px solid var(--line);border-radius:9px;padding:9px 10px;background:var(--surface);color:var(--ink);font:inherit;min-width:210px}.rm-controls select{min-width:205px}.rm-crossroads{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin:16px 0}.rm-crossroads div{border-left:3px solid var(--accent);background:var(--surface);border-radius:8px;padding:10px 12px}.rm-crossroads b,.rm-crossroads span{display:block}.rm-crossroads span{font-size:.88rem;color:var(--sub);margin-top:4px}
    .rm-scroll{overflow:auto;border:1px solid var(--line);border-radius:14px;background:var(--surface);overscroll-behavior-x:contain}.rm-grid{min-width:1190px;display:grid;grid-template-columns:174px repeat(8,minmax(126px,1fr));}.rm-year{position:sticky;top:0;z-index:2;background:var(--surface);font-weight:700;text-align:center;border-bottom:1px solid var(--line);padding:10px 4px}.rm-year:first-child{left:0;z-index:3}.rm-lane-title{position:sticky;left:0;z-index:1;background:var(--surface);border-right:1px solid var(--line);border-bottom:1px solid var(--line);padding:12px 10px;font-weight:700;display:flex;align-items:center;gap:8px}.rm-lane-title i{width:9px;height:30px;border-radius:8px;flex:none}.rm-cell{min-height:72px;padding:6px;border-bottom:1px solid var(--line);border-right:1px solid color-mix(in srgb,var(--line) 70%,transparent)}.rm-node{width:100%;display:block;text-align:left;border:1px solid var(--line);border-left:3px solid var(--node-color);border-radius:8px;background:var(--surface);color:var(--ink);padding:6px 7px;margin:3px 0;cursor:pointer;font:inherit;font-size:.79rem;line-height:1.3}.rm-node:hover,.rm-node.is-selected{border-color:var(--node-color);box-shadow:0 2px 10px color-mix(in srgb,var(--node-color) 24%,transparent)}.rm-node-year{display:block;font-size:.72rem;color:var(--sub);margin-bottom:2px}.rm-empty{padding:20px;color:var(--sub)}
    .rm-detail h2{margin:.15em 0 .35em}.rm-detail h3{margin:16px 0 5px}.rm-detail p{margin:.4em 0}.rm-detail .rm-tags{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0}.rm-tag{display:inline-block;border:1px solid var(--line);border-radius:99px;padding:3px 9px;font-size:.82rem;font:inherit;color:var(--ink);background:var(--surface);cursor:pointer}.rm-cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.rm-card{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:16px}.rm-card h3{margin:0 0 4px}.rm-card p{margin:.5em 0}.rm-card .rm-links,.rm-detail .rm-links{font-size:.9rem;line-height:1.8}.rm-sources{margin:20px 0;padding:14px 18px;border:1px solid var(--line);border-radius:12px}.rm-sources li{margin:8px 0}.rm-sources a,.rm-detail a{overflow-wrap:anywhere}.rm-guide li{margin:7px 0}.rm-guide h2{margin-top:0}.rm-entry-list{margin-top:12px;border-top:1px solid var(--line);padding-top:8px}.rm-entry-list li{margin:7px 0}.rm-entry-list .hint{display:block;font-size:.83rem}
    @media(max-width:850px){.rm-crossroads{grid-template-columns:repeat(2,minmax(0,1fr))}.rm-cards{grid-template-columns:1fr}.rm-controls input{min-width:min(74vw,340px)}}
    @media(max-width:480px){.rm-crossroads{grid-template-columns:1fr}.rm-intro,.rm-guide,.rm-detail{padding:14px}.rm-tab{padding:8px 10px}}
  </style>
  </div>
  <script src="../../js/research_reading.js"></script>
  <script type="application/json" id="rm-data">__RESEARCH_MAP_DATA__</script>
  <script>
  (()=>{
    const D=JSON.parse(document.getElementById('rm-data').textContent), refs=new Map(D.references.map(x=>[x.id,x])), teams=new Map(D.teams.map(x=>[x.id,x])), apps=new Map(D.applications.map(x=>[x.id,x])), nodes=new Map(D.nodes.map(x=>[x.id,x]));
    const localHref=u=>u.startsWith('/')?'../../'+u.replace(/^\/+/, '')+(u.endsWith('/')?'index.html':''):u;
    const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const link=r=>`<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a> <span class="hint">(${esc(r.kind)}, ${esc(r.year)})${r.versionNote?' · '+esc(r.versionNote):''}</span>`;
    const laneById=new Map(D.lanes.map(x=>[x.id,x])), C=D.readingViews, V=ResearchReading, storageKey='swarm-research-reading-v1';
    let state=V.defaults(D), selected=D.nodes[0]?.id||'', result;
    try{state=V.normalize(JSON.parse(localStorage.getItem(storageKey)),D,C);}catch(_){}
    const reader=document.getElementById('rm-reader');
    const persist=()=>{try{localStorage.setItem(storageKey,JSON.stringify(state));}catch(_){}};
    document.getElementById('rm-method').innerHTML='<option value="all">全部方法（清空选择）</option>'+C.methods.map(x=>'<option value="'+esc(x.id)+'">'+esc(x.name)+'</option>').join('');
    document.getElementById('rm-problem').innerHTML='<option value="all">全部问题（清空选择）</option><optgroup label="具体问题">'+C.problemTopics.map(x=>'<option value="problem:'+esc(x.id)+'">'+esc(x.name)+'</option>').join('')+'</optgroup><optgroup label="应用方向">'+D.applications.map(x=>'<option value="story:'+esc(x.id)+'">'+esc(x.name)+'</option>').join('')+'</optgroup>';
    function choices(group,items){return items.map(x=>'<label><input type="checkbox" data-reading-group="'+group+'" value="'+esc(x.id)+'">'+esc(x.name)+'</label>').join('');}
    document.getElementById('rm-lane-choices').innerHTML=choices('lanes',D.lanes);
    document.getElementById('rm-band-choices').innerHTML=choices('bands',D.bands.map(x=>({id:x,name:x})));
    function syncControls(){
      reader.classList.toggle('rm-hide-sources',!state.sources);reader.classList.toggle('rm-hide-boundaries',!state.boundaries);
      document.querySelectorAll('[data-reading-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.readingMode===state.mode)));
      document.querySelectorAll('[data-reading-layout]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.readingLayout===state.layout)));
      document.querySelectorAll('[data-reading-option]').forEach(b=>b.checked=state[b.dataset.readingOption]);
      document.querySelectorAll('[data-reading-group]').forEach(b=>b.checked=state[b.dataset.readingGroup].includes(b.value));
      document.getElementById('rm-method-wrap').hidden=state.mode!=='algorithm';document.getElementById('rm-problem-wrap').hidden=state.mode!=='problem';
      document.getElementById('rm-method').value='all';document.getElementById('rm-problem').value='all';
      const picked=state.mode==='algorithm'?state.methods:state.mode==='problem'?state.problems:[];
      const name=id=>state.mode==='algorithm'?C.methods.find(x=>x.id===id)?.name:id.startsWith('problem:')?C.problemTopics.find(x=>'problem:'+x.id===id)?.name:D.applications.find(x=>'story:'+x.id===id)?.name;
      document.getElementById('rm-selected-topics').innerHTML=picked.map(id=>'<button type="button" class="rm-tag" data-remove-topic="'+esc(id)+'" aria-label="移除 '+esc(name(id))+'">'+esc(name(id))+' ×</button>').join('')+(state.mode!=='overview'&&!picked.length?'<span class="hint">未限定主题，显示地图中已收录的相关研究；可连续添加多个主题。</span>':'');

      if(document.getElementById('rm-search').value!==state.query)document.getElementById('rm-search').value=state.query;
      document.getElementById('rm-reading-note').textContent={overview:'看全局的发展脉络，默认收起详情和出处；点节点即可展开。',algorithm:'围绕已收录的方法查看相关研究；邻接节点仅按已有关系展示，不自动推断谱系。',problem:'从具体问题或应用方向查看研究；主题关联不表示方法适用于全部业务约束。'}[state.mode];
    }
    function update(){syncControls();renderHistory();persist();}
    function historyTab(){document.querySelector('.rm-tab[data-view="history"]').click();}
    reader.addEventListener('change',e=>{
      const t=e.target;
      if(t.dataset.readingOption){state[t.dataset.readingOption]=t.checked;update();}
      else if(t.dataset.readingGroup){const key=t.dataset.readingGroup;state[key]=[...reader.querySelectorAll('[data-reading-group="'+key+'"]:checked')].map(x=>x.value);historyTab();update();}
      else if(t.id==='rm-method'||t.id==='rm-problem'){const key=t.id==='rm-method'?'methods':'problems';state[key]=t.value==='all'?[]:[...new Set([...state[key],t.value])];historyTab();update();}
    });
    reader.addEventListener('click',e=>{
      const b=e.target.closest('button');if(!b)return;
      if(b.dataset.readingMode){state=V.preset(b.dataset.readingMode,D,state);historyTab();update();}
      else if(b.dataset.readingLayout){state.layout=b.dataset.readingLayout;update();}
      else if(b.dataset.selectGroup){const k=b.dataset.selectGroup;state[k]=b.dataset.action==='all'?(k==='lanes'?D.lanes.map(x=>x.id):[...D.bands]):[];historyTab();update();}
      else if(b.dataset.removeTopic){const key=state.mode==='algorithm'?'methods':'problems';state[key]=state[key].filter(x=>x!==b.dataset.removeTopic);historyTab();update();}
      else if(b.id==='rm-reset'){state=V.defaults(D);historyTab();update();}
    });
    
    document.getElementById('rm-stats').innerHTML=`<span class="rm-stat"><b>${D.lanes.length}</b> 条并行主线</span><span class="rm-stat"><b>${D.nodes.length}</b> 个历史与方法节点</span><span class="rm-stat"><b>${D.teams.length}</b> 个团队/基准社区示例</span><span class="rm-stat"><b>${D.applications.length}</b> 类应用问题</span><span class="rm-stat"><b>${D.references.length}</b> 条来源记录 · 更新 ${esc(D.updated)}</span>`;

    document.getElementById('rm-method-note').textContent=D.methodNote;
    document.getElementById('rm-guide').innerHTML=D.readingGuide.map(x=>`<li>${esc(x)}</li>`).join('');
    function renderHistory(){
      result=V.select(D,C,state);
      const visible=result.nodes;
      const lanes=D.lanes.filter(l=>visible.some(n=>n.lane===l.id)),bands=D.bands.filter(b=>visible.some(n=>Math.floor(n.year/10)*10+'s'===b));
      const count=visible.filter(n=>result.focal.has(n.id)).length;
      document.getElementById('rm-count').textContent='显示 '+visible.length+' / '+D.nodes.length+' 个节点'+(visible.length>count?'（含 '+(visible.length-count)+' 个邻接节点）':'');
      if(!visible.length){
        document.getElementById('rm-history').innerHTML='<div class="rm-empty">当前条件下没有节点。可取消“只看关键节点”、放宽主线或年代，或点击“恢复默认显示”。</div>';
        document.getElementById('rm-detail').hidden=true;document.getElementById('rm-visible-relations').innerHTML='';return;
      }
      if(!visible.some(n=>n.id===selected))selected=visible[0].id;
      const button=n=>'<button class="rm-node '+(n.id===selected?'is-selected ':'')+(result.context.has(n.id)?'rm-context':'')+'" style="--node-color:'+esc(laneById.get(n.lane).color)+'" data-node="'+esc(n.id)+'" aria-pressed="'+(n.id===selected)+'"><span class="rm-node-year">'+n.year+(result.context.has(n.id)?' · 邻接':'')+'</span>'+esc(n.title)+(!state.compact?'<span class="rm-node-summary">'+esc(n.summary)+'</span>':'')+'</button>';
      if(state.layout==='list'){
        document.getElementById('rm-history').innerHTML='<div class="rm-node-list">'+visible.map(n=>'<div><span class="hint">'+esc(laneById.get(n.lane).name)+'</span>'+button(n)+'</div>').join('')+'</div>';
      }else{
        const laneRows=lanes.map(l=>'<div class="rm-lane-title"><i style="background:'+esc(l.color)+'"></i>'+esc(l.name)+'</div>'+bands.map(b=>'<div class="rm-cell">'+visible.filter(n=>n.lane===l.id&&Math.floor(n.year/10)*10+'s'===b).map(button).join('')+'</div>').join('')).join('');
        document.getElementById('rm-history').innerHTML='<div class="rm-grid" style="grid-template-columns:160px repeat('+bands.length+',minmax(110px,1fr));min-width:'+Math.max(380,160+bands.length*110)+'px"><div class="rm-year">研究线 / 年代</div>'+bands.map(b=>'<div class="rm-year">'+esc(b)+'</div>').join('')+laneRows+'</div>';
      }
      document.querySelectorAll('#rm-history [data-node]').forEach(b=>b.addEventListener('click',()=>{selected=b.dataset.node;state.details=true;update();document.getElementById('rm-detail').scrollIntoView({behavior:'smooth',block:'nearest'});}));
      document.getElementById('rm-detail').hidden=!state.details;renderDetail(nodes.get(selected));
      document.getElementById('rm-visible-relations').innerHTML=state.connections&&result.relations.length?'<h3>当前可见节点之间的关联</h3><p class="hint">关系类型与来源可在“研究难点与中文阅读”中查看。</p>'+result.relations.map(e=>'<p><span class="rm-tag">'+esc(e.kind)+'</span> <button class="rm-tag" data-related="'+esc(e.source)+'">'+esc(nodes.get(e.source).title)+'</button> → <button class="rm-tag" data-related="'+esc(e.target)+'">'+esc(nodes.get(e.target).title)+'</button><span class="hint"> · '+esc(e.summary)+'</span></p>').join(''):'';
    }
    function renderDetail(n){if(!n)return;const l=laneById.get(n.lane), teamLinks=(n.teams||[]).map(id=>teams.get(id)).filter(Boolean).map(t=>`<button class="rm-tag" data-team="${esc(t.id)}">${esc(t.name)}</button>`).join(''), appLinks=(n.apps||[]).map(id=>apps.get(id)).filter(Boolean).map(a=>`<button class="rm-tag" data-app="${esc(a.id)}">${esc(a.name)}</button>`).join(''), algoLinks=(n.algorithmLinks||[]).map(a=>`<a class="rm-tag" href="${esc(localHref(a.url))}">${esc(a.label)}</a>`).join(''), rs=(n.refs||[]).map(id=>refs.get(id)).filter(Boolean).map(r=>`<li>${link(r)}</li>`).join('');document.getElementById('rm-detail').innerHTML=`<p class="hint">${esc(l?.name)} · ${n.year} · ${esc(n.kind)}</p><h2>${esc(n.title)}</h2><p>${esc(n.summary)}</p><h3>主要贡献</h3><p>${esc(n.contribution)}</p><div class="rm-boundary"><h3>证据边界</h3><p>${esc(n.boundary)}</p></div>${teamLinks?`<h3>关联研究群体</h3><div class="rm-tags">${teamLinks}</div>`:''}${appLinks?`<h3>关联应用</h3><div class="rm-tags">${appLinks}</div>`:''}${algoLinks?`<h3>本站相关算法演示</h3><div class="rm-tags">${algoLinks}</div>`:''}<div class="rm-citations"><h3>来源</h3><ol>${rs}</ol></div>`;document.querySelectorAll('#rm-detail [data-team]').forEach(b=>b.addEventListener('click',()=>openCard('teams',`rm-team-${b.dataset.team}`)));document.querySelectorAll('#rm-detail [data-app]').forEach(b=>b.addEventListener('click',()=>openCard('applications',`rm-app-${b.dataset.app}`)));}
    function openCard(view,id){document.querySelector(`.rm-tab[data-view="${view}"]`).click();requestAnimationFrame(()=>document.getElementById(id)?.scrollIntoView({behavior:'smooth',block:'center'}));}
    function renderCards(){document.getElementById('rm-teams').innerHTML=D.teams.map(t=>`<article class="rm-card" id="rm-team-${esc(t.id)}"><h3>${esc(t.name)}</h3><p class="hint">${esc(t.where)} · ${esc(t.focus)}</p><p>${esc(t.contribution)}</p><p class="rm-boundary"><b>阅读边界：</b>${esc(t.caution)}</p><div class="rm-links rm-citations">${t.evidence.map(id=>refs.get(id)).filter(Boolean).map(link).join('<br>')}</div></article>`).join('');document.getElementById('rm-applications').innerHTML=D.applications.map(a=>`<article class="rm-card" id="rm-app-${esc(a.id)}"><h3>${esc(a.name)}</h3><p><b>现实要决定什么：</b>${esc(a.decision)}</p><p><b>问题会包含：</b>${esc(a.models)}</p><p><b>研究怎样做：</b>${esc(a.research)}</p><p><b>结果需要怎样核验：</b>${esc(a.evidence)}</p><p class="rm-links"><b>本站相关问题：</b> ${a.problemLinks.map(x=>`<a href="${esc(localHref(x.url))}">${esc(x.label)}</a>`).join(' · ')}</p><div class="rm-links rm-citations">${a.refs.map(id=>refs.get(id)).filter(Boolean).map(link).join('<br>')}</div></article>`).join('');}
    document.getElementById('rm-industry-coverage').innerHTML='<b>这里串起 '+D.industryEvidence.length+' 个领域中的 '+D.industryEvidence.reduce((s,x)=>s+x.count,0)+' 个应用主题。</b><br>每张卡提供代表性外部研究、适用范围和阅读提示；展开后可查看相关主题及本站的问题模型入口。';
    document.getElementById('rm-industries').innerHTML=D.industryEvidence.map(x=>{
      const sources=x.refs.map(id=>refs.get(id)).filter(Boolean).map(link).join('<br>');
      const entries=x.entries.map(e=>{
        const title=e.url?'<a href="'+esc(localHref(e.url))+'">'+esc(e.title)+'</a>':esc(e.title);
        return '<li>'+esc(e.title)+'<span class="hint">'+esc(e.summary)+'</span><span class="hint">'+(e.url?'<a href="'+esc(localHref(e.url))+'">关联教学模型</a>':'')+'</span><span class="hint rm-citations">'+(e.refs||[]).map(id=>refs.get(id)).filter(Boolean).map(link).join('<br>')+'</span></li>';
      }).join('');
      return '<article class="rm-card" id="rm-industry-'+esc(x.id)+'"><h3>'+esc(x.name)+' <span class="hint">'+x.count+' 个站内条目</span></h3><p>'+esc(x.overview)+'</p><p><b>外部研究看到：</b>'+esc(x.evidence)+'</p><p class="rm-boundary"><b>阅读时留意：</b>'+esc(x.boundary)+'</p><div class="rm-links rm-citations"><b>代表性外部来源</b><br>'+sources+'</div><details class="rm-entry-list"><summary>查看此领域的 '+x.count+' 个站内应用条目</summary><ul>'+entries+'</ul></details></article>';
    }).join('');

    function jumpNode(id){if(!V.select(D,C,state).nodes.some(n=>n.id===id))state=V.defaults(D);selected=id;state.details=true;update();openCard('history','rm-detail');}
    function relationCard(e){const a=nodes.get(e.source),b=nodes.get(e.target);return '<article class="rm-card"><p class="hint">'+esc(e.kind)+'</p><h3><button class="rm-tag" data-related="'+esc(e.source)+'">'+esc(a.title)+'</button> ↔ <button class="rm-tag" data-related="'+esc(e.target)+'">'+esc(b.title)+'</button></h3><p>'+esc(e.summary)+'</p><div class="rm-links rm-citations">'+e.refs.map(id=>refs.get(id)).filter(Boolean).map(link).join('<br>')+'</div></article>';}
    document.getElementById('rm-questions').innerHTML=D.researchQuestions.map(q=>'<article class="rm-card"><h3>'+esc(q.title)+'</h3><p>'+esc(q.summary)+'</p><div class="rm-links rm-citations">'+q.refs.map(id=>refs.get(id)).filter(Boolean).map(link).join('<br>')+'</div></article>').join('');
    document.getElementById('rm-relations').innerHTML=D.relations.map(relationCard).join('');
    document.getElementById('rm-coverage-note').textContent=D.siteCoverage.scope;
    document.getElementById('rm-algorithm-coverage').innerHTML=D.siteCoverage.algorithms.map(a=>'<article class="rm-entry-list"><h3><a href="'+esc(localHref(a.url))+'">'+esc(a.name)+'</a></h3><p>'+esc(a.note)+'</p><div class="rm-links rm-citations">'+a.refs.map(id=>refs.get(id)).filter(Boolean).map(link).join('<br>')+'</div></article>').join('');
    const fidelityNames={standard:'标准模型',simplified:'教学简化模型',illustrative:'示意模型',reference:'分类与定义'};
    document.getElementById('rm-problem-coverage').innerHTML=D.siteCoverage.problems.map(p=>'<article class="rm-entry-list"><h3><a href="'+esc(localHref(p.url))+'">'+esc(p.name)+'</a> <span class="hint">'+esc(fidelityNames[p.fidelity]||p.fidelity)+'</span></h3><p>'+esc(p.note)+'</p>'+(p.modelScope?'<details><summary>本站模型说明</summary><p>'+esc(p.modelScope)+'</p></details>':'')+'<details class="rm-citations"><summary>'+p.sourceCount+' 条原有参考资料</summary><ul>'+p.sources.map(s=>'<li>'+esc(s)+'</li>').join('')+'</ul></details></article>').join('');
    document.getElementById('rm-relations').addEventListener('click',e=>{const b=e.target.closest('[data-related]');if(b)jumpNode(b.dataset.related);});

    document.getElementById('rm-ref-index').innerHTML=D.references.map(r=>`<li id="rm-ref-${esc(r.id)}">${link(r)}</li>`).join('');
    document.getElementById('rm-search').addEventListener('input',e=>{state.query=e.target.value.trim();update();});
    document.getElementById('rm-visible-relations').addEventListener('click',e=>{const b=e.target.closest('[data-related]');if(b)jumpNode(b.dataset.related);});
    document.querySelectorAll('.rm-tab').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('.rm-tab').forEach(x=>{const on=x===b;x.classList.toggle('is-active',on);x.setAttribute('aria-selected',on?'true':'false');});document.querySelectorAll('.rm-panel').forEach(x=>x.hidden=x.id!==`rm-view-${b.dataset.view}`);}));
    renderCards();update();
  })();
  </script>
""".replace("__RESEARCH_MAP_DATA__", embedded).replace("__META_CHIPS__", _meta_chips(cur="research-map")).replace("__REVIEW_PANEL__", render_review_panel())

def generate(write, _page, ldjson):
    meta = _load("meta.json")
    # ① 元层四页
    for p in meta["pages"]:
        path = f"/meta/{p['dir']}/"
        body = _research_map_page(p) if p["id"] == "research-map" else _meta_page(p)
        html = _shell(path, f"{p['name']} · 元启发式元层方法论",
                      p["lead"][:150], body)
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

# -*- coding: utf-8 -*-
"""交付前自检：把「能不能打开」「会不会报错」这类问题在上线前拦下来。

检查项：
  1. 算法包测试全部通过
  2. 每个页面有独立的 title / description / H1 / canonical
  3. 页面里引用的 css/js 资源真实存在（404 是静态站最常见的低级错误）
  4. sitemap 里的 URL 与真实页面一一对应
  5. 起一个本地 http 服务，逐页 GET，必须 200（file:// 打不开 module worker）

用法：
    python selfcheck.py
"""
import json
import http.server
import os
import re
import socketserver
import sys
import threading
import urllib.request
from urllib.error import HTTPError

ROOT = os.path.dirname(os.path.abspath(__file__))
def _dynamic_pages():
    """S2-B：PAGES 从数据层动态生成——algos.json/families.json 是单一事实来源。"""
    _algos = json.load(open(os.path.join(ROOT, "data", "algos.json"), encoding="utf-8"))
    _fams = json.load(open(os.path.join(ROOT, "data", "families.json"), encoding="utf-8"))
    _probs = json.load(open(os.path.join(ROOT, "data", "problems.json"), encoding="utf-8"))
    _meta = json.load(open(os.path.join(ROOT, "data", "meta.json"), encoding="utf-8"))
    _sysp = os.path.join(ROOT, "py")
    if _sysp not in __import__("sys").path:
        __import__("sys").path.insert(0, _sysp)
    import recipe as _recipe  # noqa: E402  S7-B：配方页动态纳入
    _fd = {f["id"]: f["dir"] for f in _fams}
    pages = ([("/" and "/")]
             + ["/algo/", "/problem/"]  # P2-2：算法/问题总览页（导航按钮落点）
             + [f"/algo/{_fd[a['family']]}/{a['slug'][:-4]}/" for a in _algos]
             + [f"/algo/{f['dir']}/" for f in _fams]
             + ["/compare/", "/demo/", "/guide/", "/encyclopedia/", "/components/",
                "/problem/knapsack/", "/problem/continuous/", "/problem/multiobj/",
                "/problem/graphcolor/", "/problem/binpack/", "/problem/custom/"]
             + [f"/problem/knapsack/{v['id']}/" for v in _probs["knapsack_variants"]]
             + [f"/problem/{c['dir']}/" for c in _probs["class_pages"]]
             + [f"/problem/{t['dir']}/" for t in _probs.get("abstract_types", [])
                if t.get("status") == "page"]  # B 期抽象类型内容页（数据驱动）
             + ["/problem/reductions/"]  # P1 映射层：归约页
             + [f"/meta/{p['dir']}/" for p in _meta["pages"]]
             + [f"/algo/{_fd[r['lineage']['family']]}/{r['id']}/" for r in _recipe.RECIPES]
             + ["/matrix/", "/applications/"]
             + ["/coverage/", "/discovery/"])  # 域×算法覆盖矩阵看板（2026-09-28）；discovery=候选发现池（2026-09-29）；setcover/sat/qubo/uflp 已在 class_pages 段
    return _algos, pages


_ALGOS, PAGES = _dynamic_pages()
ASSETS = ["/css/style.css", "/js/compat.js", "/js/run_guard.js", "/js/result_export.js", "/js/tool.js", "/js/compare.js", "/js/worker.js", "/js/solvers_src.js", "/py/solvers.py",
          "/js/domain_page.js", "/js/domain_worker.js", "/js/domains_src.js",
          "/robots.txt"]

ok_count = 0
# 未设置 SWARM_SITE_URL 时构建不输出 canonical / og:image / sitemap，对应检查随之跳过
HAS_SITE = bool(os.environ.get("SWARM_SITE_URL", "").strip())
fail_count = 0


def check(cond: bool, label: str, detail: str = "") -> None:
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f"  [通过] {label}")
    else:
        fail_count += 1
        print(f"  [失败] {label}" + (f" —— {detail}" if detail else ""))


def run_tests() -> None:
    print("\n[1] 算法包测试")
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import importlib.util

    spec = importlib.util.spec_from_file_location("t", os.path.join(ROOT, "tests", "test_solvers.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name in sorted(dir(mod)):
        if name.startswith("test_"):
            try:
                getattr(mod, name)()
                check(True, name)
            except Exception as e:  # noqa: BLE001
                check(False, name, repr(e)[:160])


def read(path: str) -> str:
    with open(os.path.join(ROOT, path.lstrip("/")), encoding="utf-8") as f:
        return f.read()


def _tags_balanced(html: str) -> bool:
    """HTML 标签平衡校验：任意时点闭合标签必须与栈顶匹配，结束时栈必须为空。"""
    from html.parser import HTMLParser

    class _P(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack = []
            self.ok = True

        def handle_starttag(self, tag, attrs):
            if tag not in ("br", "img", "meta", "link", "hr", "input"):
                self.stack.append(tag)

        def handle_endtag(self, tag):
            if self.stack and self.stack[-1] == tag:
                self.stack.pop()
            elif tag in self.stack:
                self.ok = False  # 交叉闭合
            else:
                self.ok = False  # 多余闭合

    p = _P()
    p.feed(html)
    return p.ok and not p.stack


def check_pages() -> None:
    print("\n[2] 页面 SEO 与资源引用")
    titles, descs = {}, {}
    for p in PAGES:
        rel = os.path.join(p.strip("/"), "index.html") if p != "/" else "index.html"
        if not os.path.exists(os.path.join(ROOT, rel)):
            check(False, f"{p} 存在", "文件缺失")
            continue
        html = read(rel)
        t = re.search(r"<title[^>]*>(.*?)</title>", html)
        d = re.search(r'<meta name="description" content="(.*?)">', html)
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        canon = re.search(r'<link rel="canonical" href="(.*?)">', html)
        check(bool(t and len(t.group(1)) > 8), f"{p} 有 title")
        check(bool(d and len(d.group(1)) > 20), f"{p} 有 description")
        check(bool(h1), f"{p} 有 H1")
        if HAS_SITE:
            check(bool(canon), f"{p} 有 canonical")
        # S5-A：社交分享卡与图标注入检查
        check('og:title' in html, f"{p} 有 og:title")
        if HAS_SITE:
            check('og:image' in html and 'assets/og-cover.png' in html, f"{p} 有 og:image")
        check('rel="icon"' in html, f"{p} 有 favicon")
        check("{title}" not in html and "{h1}" not in html, f"{p} 无未替换占位符")
        # 编辑器污染守卫（2026-09-15 事故）：构建产物若被本地文档编辑器打开，
        # 每个元素会被盖上 data-page-node-id 追踪属性。构建产物只能由
        # build_pages.py 生成，禁止用编辑器打开后直接改。
        check("data-page-node-id" not in html, f"{p} 无编辑器污染属性")
        # 标签平衡守卫（2026-09-16 事故）：卡片简介截断曾把 <strong> 对切断，
        # 未闭合标签吞掉 </span></a>，浏览器纠错后卡片网格整体塌陷。
        check(_tags_balanced(html), f"{p} 标签平衡")
        if t:
            titles[p] = t.group(1)
        if d:
            descs[p] = d.group(1)

        # 资源引用
        for src in re.findall(r'(?:href|src)="(/[^"#]*?)"', html):
            if src.startswith("http"):
                continue
            fs = os.path.join(ROOT, src.lstrip("/"))
            check(os.path.exists(fs), f"{p} 引用的 {src} 存在")

    check(len(set(titles.values())) == len(titles), "各页 title 互不相同", str(titles.values()))
    check(len(set(descs.values())) == len(descs), "各页 description 互不相同")


def check_solvers_src() -> None:
    """js/solvers_src.js 必须与 py/solvers.py 内容一致（防改了源码忘重建）"""
    print("\n[2.5] 内嵌源码新鲜度")
    try:
        emb = read("js/solvers_src.js")
        # S7-B：嵌入源 = py/components.py + py/recipe.py + py/solvers.py（剥 future import）拼接
        _strip = lambda s: s.replace("from __future__ import annotations\n", "", 1)  # noqa: E731
        cur = (read("py/taxonomy.py") + "\n\n" + read("py/components.py") + "\n\n" + _strip(read("py/recipe.py"))
               + "\n\n" + _strip(read("py/solvers.py")))
        import json as _json
        m = re.search(r"export const SOLVERS_SRC = (.*?);\nexport const VALIDATE_SRC = (.*);", emb, re.S)
        check(m is not None, "solvers_src.js 含 SOLVERS_SRC 与 VALIDATE_SRC 导出")
        if m:
            check(_json.loads(m.group(1)) == cur, "嵌入源码 == py/solvers.py（新鲜）",
                  "不一致：改过 solvers.py 后请重跑 python build_pages.py")
            check(_json.loads(m.group(2)) == read("py/validate.py"), "TSP 页内嵌的校验器 == py/validate.py（新鲜）",
                  "不一致：改过 validate.py 后请重跑 python build_pages.py")
    except Exception as e:  # noqa: BLE001
        check(False, "solvers_src.js 检查", repr(e)[:120])


def check_redirects() -> None:
    """S2-B：旧算法 URL 必须有重定向桩（meta refresh + canonical）。"""
    print("\n[3.5] 旧算法 URL 重定向桩")
    for a in _ALGOS:
        rel = os.path.join("algo", a["slug"], "index.html")
        if not os.path.exists(os.path.join(ROOT, rel)):
            check(False, f"{rel} 存在", "旧 URL 重定向桩缺失")
            continue
        html = read(rel)
        check('meta http-equiv="refresh"' in html, f"{rel} 含 meta refresh")
        # file:// 兼容（2026-09-26 工程用户走查 P0）：跳转必须相对，不得 /绝对
        check('content="0; url=../../' in html, f"{rel} meta refresh 用相对路径")
        check('location.replace("../../' in html, f"{rel} JS 跳转用相对路径")


def check_moved_pages() -> None:
    """家族重整后迁走的算法页：新地址是真页面，旧地址是指向新地址的重定向桩（data/moved_pages.json）。"""
    print("\n[3.6] 迁移算法页的旧地址重定向")
    import json as _json
    moved = _json.loads(read("data/moved_pages.json"))
    fams_list = _json.loads(read("data/families.json"))
    fams = {f["dir"] for f in fams_list}
    fam_dir = {f["id"]: f["dir"] for f in fams_list}
    algos = {a["key"]: a["family"] for a in _json.loads(read("data/algos.json"))}
    for m in moved:
        new_rel = f"algo/{m['to_dir']}/{m['slug']}/index.html"
        old_rel = f"algo/{m['from_dir']}/{m['slug']}/index.html"
        check(m["from_dir"] != m["to_dir"] and m["from_dir"] in fams and m["to_dir"] in fams,
              f"{m['slug']}：迁移的新旧家族目录都存在且不同")
        check(fam_dir[algos[m["slug"]]] == m["to_dir"], f"{m['slug']}：迁移目标 = algos.json 里它现在的家族")
        check(os.path.exists(os.path.join(ROOT, new_rel)) and "refresh" not in read(new_rel),
              f"{new_rel} 是真页面（不是桩）")
        stub = read(old_rel) if os.path.exists(os.path.join(ROOT, old_rel)) else ""
        check(("content=" + chr(34) + "0; url=../../../" + new_rel) in stub
              and ("location.replace(" + chr(34) + "../../../" + new_rel) in stub,
              f"{old_rel} 是指向 {new_rel} 的相对路径重定向桩")


def check_404() -> None:
    """S5-A：404 页存在且有回退入口。"""
    print("\n[3b] 404 页")
    p = os.path.join(ROOT, "404.html")
    check(os.path.exists(p), "404.html 存在")
    if os.path.exists(p):
        h = read("404.html")
        check('href="index.html"' in h, "404 页含返回首页链接")
        check("noindex" in h, "404 页带 noindex")


def check_sitemap() -> None:
    print("\n[3] sitemap 与页面一致性")
    if not HAS_SITE:
        print("  跳过：未设置 SWARM_SITE_URL，构建不生成 sitemap.xml")
        return
    sm = read("sitemap.xml")
    locs = set(re.findall(r"<loc>(.*?)</loc>", sm))
    for p in PAGES:
        check(any(loc.endswith(p) for loc in locs), f"sitemap 包含 {p}")
    check(len(locs) == len(PAGES), f"sitemap URL 数 = {len(PAGES)}", f"实际 {len(locs)}")


def serve_and_fetch() -> None:
    print("\n[4] 本地 HTTP 逐页访问（file:// 打不开 module worker，必须走 http）")

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    class Server(socketserver.TCPServer):
        allow_reuse_address = True

    os.chdir(ROOT)
    httpd = Server(("127.0.0.1", 0), Quiet)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        for url in PAGES + ASSETS:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}{url}", timeout=10) as r:
                    body = r.read()
                    check(r.status == 200 and len(body) > 0, f"GET {url} → 200（{len(body)} 字节）")
            except HTTPError as e:
                check(False, f"GET {url}", f"HTTP {e.code}")
            except Exception as e:  # noqa: BLE001
                check(False, f"GET {url}", repr(e)[:120])
    finally:
        httpd.shutdown()
        httpd.server_close()


def check_applications() -> None:
    """S8 应用地图：双维度导航完整性——每条有合法类别、双视图区块齐全。"""
    print("\n[3c] 应用地图双视图")
    try:
        d = json.load(open(os.path.join(ROOT, "data", "apps.json"), encoding="utf-8"))
        cat_ids = {c["id"] for c in d["categories"]}
        bad = [e["title"] for e in d["entries"] if e.get("cat") not in cat_ids]
        check(not bad, "96 条应用均有合法问题形态类别", f"非法/缺失：{bad[:5]}")
        check(len(d["entries"]) == 96, f"应用条目数 = 96", f"实际 {len(d['entries'])}")
        html = read("applications/index.html")
        check('id="apps-cat"' in html and 'id="apps-ind"' in html, "双视图容器存在")
        check("_appsView" in html, "视图切换脚本存在")
        n_cat_secs = len(re.findall(r'id="cat-[a-z]+"', html))
        n_ind_secs = len(re.findall(r'id="ind-\d+"', html))
        check(n_cat_secs == len(d["categories"]), f"类别区块数 = {len(d['categories'])}", f"实际 {n_cat_secs}")
        check(n_ind_secs == len(d["industries"]), f"行业区块数 = {len(d['industries'])}", f"实际 {n_ind_secs}")
        n_rows = html.count('class="approw"')
        check(n_rows == 2 * len(d["entries"]),
              f"列表行数 = 双视图各 {len(d['entries'])}", f"实际 {n_rows}")
        check(html.count('class="catnav"') == 1, "类别导航卡组存在")
        probs = json.load(open(os.path.join(ROOT, "data", "problems.json"), encoding="utf-8"))
        legal_abs = ({t["id"] for t in probs["abstract_types"]}
                     | {t["group"] for t in probs["abstract_types"]})
        bad_abs = [e["title"] for e in d["entries"]
                   if e.get("abstract_type") not in legal_abs]
        check(not bad_abs, "96 条应用均有合法抽象类型归属（id 或属级兜底）",
              f"非法/缺失：{bad_abs[:5]}")
        grp_level = sum(1 for e in d["entries"] if e["abstract_type"] in
                        {t["group"] for t in probs["abstract_types"]})
        check(grp_level * 4 < 3 * len(d["entries"]),
              f"属级兜底占比受控（{grp_level}/{len(d['entries'])} < 3/4，连续/多目标域允许属级）",
              f"实际属级 {grp_level}")
    except Exception as e:  # noqa: BLE001
        check(False, "应用地图检查", repr(e)[:140])


def check_nav() -> None:
    """S8-C 层级导航：三大板块下拉齐全，面板内算法/问题条目与数据层一致。
    注：write() 出口会把 /绝对 链接相对化（file:// 兼容），故正则兼容两种形式。"""
    print("\n[3d] 层级导航")
    try:
        algos = json.load(open(os.path.join(ROOT, "data", "algos.json"), encoding="utf-8"))
        fams = json.load(open(os.path.join(ROOT, "data", "families.json"), encoding="utf-8"))
        probs = json.load(open(os.path.join(ROOT, "data", "problems.json"), encoding="utf-8"))
        html = read("index.html")
        for key in ("算法", "问题", "科普"):
            check(f'{key} <span class="caret">' in html, f"一级板块「{key}」存在")
        check(html.count('<div class="dd-group">') == len(fams), f"算法面板家族分组 = {len(fams)}",
              f"实际 {html.count(chr(60) + 'div class=' + chr(34) + 'dd-group' + chr(34) + '>')}")
        n_algo_links = len(re.findall(r'class="dd-item" href="/?algo/', html))
        import sys as _sys
        _sysp = os.path.join(ROOT, "py")
        if _sysp not in _sys.path:
            _sys.path.insert(0, _sysp)
        import recipe as _recipe
        n_recipes = len(_recipe.RECIPES)
        check(n_algo_links == len(algos) + n_recipes,
              f"导航覆盖实际算法 {len(algos)} 个 + 升格配方 {n_recipes} 个",
              f"实际 {n_algo_links}")
        n_var_links = len(re.findall(r'class="dd-item" href="/?problem/knapsack/', html))
        check(n_var_links == len(probs["knapsack_variants"]),
              f"问题面板含 {len(probs['knapsack_variants'])} 个背包变体", f"实际 {n_var_links}")
        check(len(re.findall(r'href="/?meta/', html)) >= 4, "科普面板含元层四页")
        # H2b 无空壳家族：每家族≥1 可点条目（算法/配方/域内实现），nav_extra 已入导航
        check(n_algo_links == len(algos) + n_recipes,
              f"导航覆盖实际算法 {len(algos)} 个 + 升格配方 {n_recipes} 个",
              f"实际 {n_algo_links}")
        check('multiobj/?algo=nsga2' in html and 'multiobj/?algo=wsga' in html,
              "F7 多目标族 nav_extra（NSGA-II/WSGA 域内实现）已入导航")
        # 用户裁定（2026-09-26）：问题下拉词条必须逐条展开，禁止「词条 ×N → 全谱」汇总行
        check("词条 ×" not in html, "问题下拉无「词条 ×N → 全谱」汇总行")
        n_entries = len([t for t in probs["abstract_types"] if t.get("status") == "entry"])
        # 所有抽象类型都已有独立页面：词条锚点应为 0
        n_pages = len([t for t in probs["abstract_types"] if t.get("status") == "page"])
        check(n_entries == 0 and n_pages == len(probs["abstract_types"]) and n_pages >= 78,
              f"词条全部升 page（{n_pages}/{len(probs['abstract_types'])}，剩余 entry={n_entries}）")
        red = read("problem/reductions/index.html")
        check(len(re.findall(r'id="e-', red)) == n_entries,
              f"归约页词条墙清空（锚点 = {n_entries} 个）")
        segs = html.split('<div class="dd-group">')[1:]  # 组内无嵌套 div，首个 </div> 即本组闭合
        empty_groups = [i for i, seg in enumerate(segs)
                        if 'dd-item' not in seg[:seg.find('</div>')]
                        and 'dd-entry' not in seg[:seg.find('</div>')]]
        check(not empty_groups, "算法面板无空壳家族组（每族≥1 可点条目）",
              f"空壳组索引 {empty_groups}")
        check("data-page-node-id" not in html, "导航无编辑器污染属性")
    except Exception as e:  # noqa: BLE001
        check(False, "层级导航检查", repr(e)[:140])


def check_recipe_upgrade() -> None:
    """S7-D：F6-F9 不可跑算法升格——升格配方已注册、配方页存在、家族页接线一致。"""
    print("\n[3e] 配方升格（S7-D）")
    try:
        fams = json.load(open(os.path.join(ROOT, "data", "families.json"), encoding="utf-8"))
        import sys as _sys
        _sysp = os.path.join(ROOT, "py")
        if _sysp not in _sys.path:
            _sys.path.insert(0, _sysp)
        import recipe as _recipe
        up = {"hh": "选择式超启发式", "saea": "代理辅助进化",
              "matheur": "Fix-and-Optimize", "mapelites": "MAP-Elites"}
        ids = {r["id"] for r in _recipe.RECIPES}
        check(set(up) <= ids, "升格配方 hh/saea/matheur/mapelites 已注册进 RECIPES")
        fd = {f["id"]: f["dir"] for f in fams}
        for rid in sorted(up):
            r = next(x for x in _recipe.RECIPES if x["id"] == rid)
            u = f'/algo/{fd[r["lineage"]["family"]]}/{rid}/'
            check(os.path.isfile(os.path.join(ROOT, u.lstrip("/"), "index.html")),
                  f"配方页已生成 {u}")
        f6 = read("algo/f6-hybrid/index.html")
        f8 = read("algo/f8-new/index.html")
        for rid, fam_html in (("hh", f6), ("saea", f6), ("matheur", f6), ("mapelites", f8)):
            name = next(x["name"] for x in _recipe.RECIPES if x["id"] == rid)
            check(f">{name}</b>" in fam_html, f"家族页含升格配方成员卡 {rid}")
        f7 = read("algo/f7-mo/index.html")
        check(f7.count("待 MO 引擎") >= 3, "F7 三词条标注「待 MO 引擎」（诚实性声明）")
        urls = [m.get("url") for f in fams for m in f.get("planned", []) if m.get("url")]
        for u in urls:
            check(os.path.isfile(os.path.join(ROOT, u.lstrip("/"), "index.html")),
                  f"词条 url 可达 {u}")
    except Exception as e:  # noqa: BLE001
        check(False, "配方升格检查", repr(e)[:140])


def check_mapping() -> None:
    """P1 映射层：mapping.json schema、引用完整性、demo 页面可跑、归约页分组齐全。"""
    print("\n[3f] 算法↔问题映射层（P1）")
    try:
        mp = json.load(open(os.path.join(ROOT, "data", "mapping.json"), encoding="utf-8"))
        pidx = mp["problem_index"]
        solves = mp["algo_solves"]
        reds = mp["reductions"]
        algo_keys = {a["key"] if "key" in a else a.get("slug", "")[:-4] for a in _ALGOS}
        tier_ok = {"实测", "文献", "推测"}
        # problem_index：url 对应文件存在
        for pid, p in pidx.items():
            f = os.path.join(ROOT, p["url"].lstrip("/"), "index.html")
            check(os.path.isfile(f), f"problem_index[{pid}] url 有页面 {p['url']}")
        # algo_solves：引用完整 + tier 合法 + 实测级 demo 页面含 id="demo"
        for s in solves:
            check(s["algo"] in algo_keys, f"algo_solves {s['algo']}∈algos")
            check(s["problem"] in pidx, f"algo_solves {s['algo']}→{s['problem']}∈problem_index")
            check(s["tier"] in tier_ok, f"algo_solves {s['algo']}→{s['problem']} tier 合法")
            if s["tier"] == "实测":
                demo = s["demo"]
                f = os.path.join(ROOT, demo.lstrip("/").rstrip("/"), "index.html")
                ok = os.path.isfile(f)
                if ok:
                    txt = read(demo.lstrip("/").rstrip("/") + "/index.html")
                    # 域演示页锚 id="demo"；算法页（H2b tsp 型 demo）运行面板锚 id="tool-root"
                    ok = 'id="demo"' in txt or 'id="tool-root"' in txt
                check(ok, f"实测级 demo 可跑 {s['algo']}→{demo}")
        # P2 切域协议：问题域实测级条目的 demo_algo（回退 slug）必须 ∈ 目标域注册表
        sys.path.insert(0, os.path.join(ROOT, "py"))
        import domains as _dm  # noqa: E402
        dom_keys = {d: {a["key"] for a in json.loads(_dm.domain_list(d))["algos"]}
                    for d in ("knapsack", "continuous", "multiobj", "graphcolor", "binpack")}
        n_demo_algo = 0
        for s in solves:
            if s["tier"] == "实测" and s.get("demo", "").startswith("/problem/"):
                dom = s["demo"].strip("/").split("/")[-1]
                keys = dom_keys.get(dom)
                if keys is None:
                    continue
                da = s.get("demo_algo") or s["algo"]
                check(da in keys, f"demo_algo {da} ∈ {dom} 域算法（{s['algo']}→{s['problem']}）")
                n_demo_algo += 1
        check(n_demo_algo >= 12, f"切域协议覆盖实测条目 {n_demo_algo}≥12（五个枢纽页；其余问题页由 tests/test_domain_switch.py 覆盖）")
        # P2 切域接线：映射卡/roster 链接必须带 ?algo= 参数（抽查三页）
        for path, frag in (("algo/f1-ea/ga/index.html", "/problem/knapsack/index.html?algo=ga"),
                           ("algo/f3-phys/sa/index.html", "/problem/knapsack/index.html?algo=sa"),
                           ("problem/multiobj/index.html", "/problem/multiobj/index.html?algo=wsga")):
            check(frag in read(path), f"切域链接带参 {path}")
        # reductions：端点引用完整 + 类型齐全 + 页面分组名存在
        types = set()
        for r in reds:
            check(r["from"] in pidx, f"归约 from {r['from']}∈problem_index")
            check(r["to"] in pidx, f"归约 to {r['to']}∈problem_index")
            check(bool(r.get("src")), f"归约 {r['from']}→{r['to']} 有出处")
            types.add(r["type"])
        red_html = read("problem/reductions/index.html")
        for t in sorted(types):
            check(f">{t}<" in red_html or f"「{t}」" in red_html or t in red_html,
                  f"归约页含「{t}」分组")
        for t in ("归约", "等价", "特例", "推广"):
            check(t in types, f"归约页含「{t}」类关系")
        # 算法页映射卡 / 问题页 roster 接线抽查（旗舰页必挂）
        for slug in ("f1-ea/ga", "f3-phys/sa", "f2-si/pso"):
            check('id="map"' in read(f"algo/{slug}/index.html"), f"算法页含映射卡 /algo/{slug}/")
        for pid in ("knapsack", "continuous", "binpack"):
            check("maplist" in read(f"problem/{pid}/index.html"), f"问题页含 roster {pid}")
        # 映射覆盖率（H2b 用户裁定：不豁免）：35 个已收集问题全部接上算法
        cov = {s["problem"] for s in solves}
        check(len(cov) == len(pidx), f"映射覆盖问题数 {len(cov)} = 全部 {len(pidx)}（不豁免）",
              f"缺: {sorted(set(pidx) - cov)}")
        check(len(solves) >= 140, f"映射条目总量 {len(solves)}≥140", f"实际 {len(solves)}")
        # tsp 44 收录算法全实测；partition ≥2 文献级
        tsp_rows = [s for s in solves if s["problem"] == "tsp"]
        check(len(tsp_rows) == len(_ALGOS) and all(s["tier"] == "实测" for s in tsp_rows),
              f"tsp 全收录算法实测（{len(tsp_rows)}/{len(_ALGOS)}）")
        part_rows = [s for s in solves if s["problem"] == "partition"]
        check(len(part_rows) >= 2 and all(s["tier"] == "文献" and s.get("src") for s in part_rows),
              f"partition 文献级 ≥2 且带 src（实际 {len(part_rows)}）")
    except Exception as e:  # noqa: BLE001
        check(False, "映射层检查", repr(e)[:140])


def check_custom_scale() -> None:
    """自定义问题规模：演示页注入 PAGE_CUSTOM_FIELDS + ⚙自定义选项，前端 currentOpts 接线。"""
    print("\n[3g] 自定义问题规模（H2）")
    try:
        js = read("js/domain_page.js")
        for token in ("function currentOpts", "PAGE_CUSTOM_FIELDS", "PAGE_CUSTOM_BASE", "cst_"):
            check(token in js, f"domain_page.js 含 {token}")
        pages = [
            "problem/knapsack/index.html",        # 枢纽
            "problem/graphcolor/index.html",      # 枢纽（双字段 n+p）
            "problem/knapsack/fractional/index.html",  # 变体
            "problem/knapsack/multiplechoice/index.html",
            "problem/sat/index.html",             # 抽象（ratio 浮点）
            "problem/uflp/index.html",
            "problem/qubo/index.html",
            "problem/assignment/index.html",      # 类页
        ]
        for p in pages:
            h = read(p)
            check("PAGE_CUSTOM_FIELDS" in h, f"自定义注入 {p}")
            check("value=\"__custom\"" in h, f"⚙自定义选项 {p}")
            check('id="customRow"' in h, f"自定义输入行 {p}")
        # 抽查字段键正确性
        check('id="cst_n"' in read("problem/knapsack/fractional/index.html"), "变体页含 n 输入")
        check('id="cst_ratio"' in read("problem/sat/index.html"), "SAT 页含 ratio 输入")
        check('id="cst_n_a"' in read("problem/assignment/index.html"), "GAP 页含 n_a 输入")
    except Exception as e:  # noqa: BLE001
        check(False, "自定义规模检查", repr(e)[:140])


def check_meta_refs() -> None:
    """P2：元层四页佐证挂接——refs schema、节↔refs 双向对账、渲染产物核对。"""
    print("\n[3g] 元层佐证挂接（P2）")
    try:
        meta = json.load(open(os.path.join(ROOT, "data", "meta.json"), encoding="utf-8"))
        for p in meta["pages"]:
            pid = p["id"]
            refs = p.get("refs", [])
            ids = [r["id"] for r in refs]
            check(len(ids) == len(set(ids)), f"meta[{pid}] refs id 无重复")
            for r in refs:
                check(bool(r.get("cite")), f"meta[{pid}] ref {r['id']} 有 cite")
                if r.get("url"):
                    check(r["url"].startswith(("http://", "https://")),
                          f"meta[{pid}] ref {r['id']} url 为公开 http(s)")
            used = [i for s in p["sections"] for i in s.get("refs", [])]
            check(all(i in ids for i in used), f"meta[{pid}] 节引用的 ref 均已声明")
            orphan = set(ids) - set(used)
            check(not orphan, f"meta[{pid}] 无未被节引用的孤儿 ref")
            # 渲染产物：上标块数 = 有引用的节数，上标链接总数 = 节引用总数
            html = read(f"meta/{pid}/index.html")
            n_sec_with = sum(1 for s in p["sections"] if s.get("refs"))
            check(html.count('class="refsup"') == n_sec_with,
                  f"meta[{pid}] 上标块数与有引用的节数一致")
            check(len(re.findall(r'href="#ref-', html)) == len(used),
                  f"meta[{pid}] 上标链接总数与节引用一致")
            check(html.count('id="ref-') == len(refs),
                  f"meta[{pid}] 页尾佐证列表项数与 refs 一致")
            check("佐证与出处" in html, f"meta[{pid}] 含「佐证与出处」区")
    except Exception as e:  # noqa: BLE001
        check(False, "元层佐证检查", repr(e)[:140])


def check_reductions_graph() -> None:
    """P3：归约有向图——坐标覆盖全部问题节点、边端点有坐标、渲染产物核对。"""
    print("\n[3h] 归约有向图（P3）")
    try:
        mp = json.load(open(os.path.join(ROOT, "data", "mapping.json"), encoding="utf-8"))
        pos = mp.get("graph", {}).get("pos", {})
        check(set(pos) <= set(mp["problem_index"]), "graph.pos 的节点都在问题索引里")
        check({r["from"] for r in mp["reductions"]} | {r["to"] for r in mp["reductions"]} <= set(pos), "归约端点都有坐标")
        vw, vh = mp.get("graph", {}).get("view", [1000, 620])
        in_box = all(0 <= x <= vw and 0 <= y <= vh for x, y in pos.values())
        check(in_box, f"全部节点坐标在 viewBox {vw}×{vh} 内")
        for r in mp["reductions"]:
            check(r["from"] in pos and r["to"] in pos,
                  f'边 {r["from"]}→{r["to"]} 两端有坐标')
        html = read("problem/reductions/index.html")
        check('<svg' in html and "rednode" in html, "归约页含内联 SVG 图")
        participating = {r["from"] for r in mp["reductions"]} | {r["to"] for r in mp["reductions"]}
        check(html.count('class="rededge"') == len(mp["reductions"]),
              "SVG 边数 = reductions 条数")
        check(html.count('class="rednode"') == len(participating),
              "SVG 节点数 = 参与归约的问题数")
        check("未入图" in html, "无边孤儿以文字列出")
        for t in ("归约", "等价", "特例", "推广"):
            check(t in html, f"图例含「{t}」")
    except Exception as e:  # noqa: BLE001
        check(False, "归约图检查", repr(e)[:140])


def check_problem_axis_v2() -> None:
    """A 期：背包变体扩展——学术缩写唯一、出处非空、命名勘误、新归约边带出处。"""
    print("\n[3i] 问题轴扩展（A 期·背包变体）")
    try:
        data = json.load(open(os.path.join(ROOT, "data", "problems.json"), encoding="utf-8"))
        variants = data["knapsack_variants"]
        abbrs = [v["abbr"] for v in variants if v.get("abbr")]
        check(len(abbrs) == len(set(abbrs)), "背包变体缩写唯一（BKP/UKP/CMP/MKP-m/MCKP/MKP/QKP/SSP）")
        for v in variants:
            check(bool(v.get("sources")), f"变体 {v['id']} 有出处（sources 非空）")
        check(len(variants) == 10, f"背包变体共 10 个（现 {len(variants)}）")
        # 命名勘误：多背包（MKP-m）与多维背包（MKP）撞车约定双落页
        multi_html = read("problem/knapsack/multiple/index.html")
        check("多背包" in multi_html and "MKP-m" in multi_html,
              "多背包页含命名勘误（多背包/MKP-m）")
        check("多重背包" in multi_html, "多背包页含旧名「多重背包」勘误注")
        md_html = read("problem/knapsack/multidim/index.html")
        check("MKP=多维背包" in md_html or ("MKP" in md_html and "多维背包" in md_html),
              "多维背包页含 MKP=多维背包 撞车约定注")
        # 三新页已建且标题带缩写
        for pid, abbr in (("unbounded", "UKP"), ("changemaking", "CMP"), ("multiplechoice", "MCKP")):
            h = read(f"problem/knapsack/{pid}/index.html")
            check(abbr in h, f"新页 {pid} 标题含缩写 {abbr}")
        # mapping 新归约边带出处
        mp = json.load(open(os.path.join(ROOT, "data", "mapping.json"), encoding="utf-8"))
        for r in mp["reductions"]:
            if r["from"] in ("bounded", "unbounded", "changemaking", "multiplechoice"):
                check(bool(r.get("src")), f'边 {r["from"]}→{r["to"]} 带来源 src')

        # ---- B 期：抽象类型层（SCP/MIS 页 + 词条级登记） ----
        import re as _re
        atypes = data.get("abstract_types", [])
        pages = [t for t in atypes if t.get("status") == "page"]
        entries = [t for t in atypes if t.get("status") == "entry"]
        # 缩写全站唯一（变体 + 抽象类型两层合并查重；空=从略，不参与查重）
        all_abbr = abbrs + [t["abbr"] for t in atypes if t.get("abbr")]
        check(len(all_abbr) == len(set(all_abbr)),
              "缩写全站唯一（背包变体 + 抽象类型无撞车）")
        # entry 级必有 en+gj+sources≥1；abbr 原则上必填，无公认缩写者从略
        # （note 须注明「从略」，撞车豁免与描述性豁免同此一条规则）
        # gj=本站自建归类锚（字母借 G&J 类目、编号是组内锚，非 G&J 正典条目号——2026-09-26 主播走查裁定）
        for t in entries:
            check(bool(t.get("en")), f"词条 {t['id']} 有 en")
            if t.get("abbr"):
                check(bool(t["abbr"].strip()), f"词条 {t['id']} abbr 非空白")
            else:
                check("从略" in t.get("note", ""),
                      f"词条 {t['id']} 从略缩写须在 note 注明原因")
            check(bool(t.get("sources")), f"词条 {t['id']} sources≥1")
            check(bool(_re.fullmatch(r"A\d+(\.\d+)?", t.get("gj", ""))),
                  f"词条 {t['id']} 归类锚格式合法（{t.get('gj')}）")
        # 页级必有四段式内容
        for t in pages:
            for f_ in ("model", "diff", "algo"):
                check(bool(t.get(f_)), f"抽象页 {t['id']} 含 {f_} 段")
        # G 期：有引擎页→内嵌求解演示（PAGE_DOMAIN 接线 + 引擎脚本）；无引擎页→诚实横幅
        # （纯内容版「无在线演示」或枢纽跳转版「无专属引擎」，二者皆不许虚构成绩）
        for t in pages:
            h = read(f"problem/{t['dir']}/index.html")
            if "PAGE_DOMAIN" in h:
                check("js/domain_page.js" in h and "vizCanvas" in h,
                      f"{t['dir']} 页内嵌在线求解演示且接线完整")
            else:
                check("无在线演示" in h or "无专属引擎" in h,
                      f"{t['dir']} 页含诚实横幅（无演示或指向枢纽演示）")
            check(t["abbr"] in h, f"{t['dir']} 页标题含缩写 {t['abbr']}")
            ro = [s for s in mp["algo_solves"] if s["problem"] == t["id"]]
            if "PAGE_DOMAIN" in h:  # 已求解化：允许实测（必须带 demo）/文献（必须带 src）混合
                check(all((s["tier"] == "实测" and s.get("demo"))
                          or (s["tier"] == "文献" and s.get("src")) for s in ro),
                      f"{t['dir']} 的映射分级诚实（实测带 demo/文献带 src，共 {len(ro)} 条）")
            else:
                check(all(s["tier"] == "文献" and s.get("src") for s in ro),
                      f"{t['dir']} 的映射全为文献级且带 src（共 {len(ro)} 条）")
        check(sum(1 for t in pages
                  if any(s["problem"] == t["id"] for s in mp["algo_solves"])) >= 4,
              "抽象类型页 ≥4 个已有文献级映射登记")

        # 归约页词条段渲染
        red_html = read("problem/reductions/index.html")
        check("全谱词条（" not in red_html and "均有独立页面" in red_html,
              "归约页词条墙退役（说明段：全部词条已有独立页面）")
        for t in pages:
            check(os.path.isfile(os.path.join(ROOT, "problem", t["dir"], "index.html")),
                  f"词条页已生成 {t['id']}")
    except Exception as e:  # noqa: BLE001
        check(False, "问题轴扩展检查", repr(e)[:140])


def check_gcvar_bpvar() -> None:
    """H2 期结构断言：着色家族 gcvar（5 变体）引擎冒烟 + 页接线。
    bpvar（装箱 3 变体）在阶段 4 施工后于本函数追加同名断言块。"""
    print("\n[3j] H2 着色家族 gcvar（5 变体单域多预设）")
    sp = os.path.join(ROOT, "py")
    if sp not in sys.path:
        sys.path.insert(0, sp)
    import domains as D  # noqa: E402
    variants = ["listcolor", "precolor", "edgecolor", "totalcolor", "mis"]
    # 变体 → 实际 URL 目录（problems.json 的 dir 字段，与 PAGE 路径一致）
    vdir = {"listcolor": "listcolor", "edgecolor": "edgecolor",
            "precolor": "precolor", "totalcolor": "totalcolor", "mis": "misindep"}
    for vt in variants:
        prob = D.gcv_make(variant=vt, n=30, seed=7, p=0.5)
        check("edges" in prob and "n" in prob and "variant" in prob,
              f"gcvar {vt} gcv_make 产出图实例")
        reg = D._gcvar_reg(vt)
        check(len(reg) >= 6, f"gcvar {vt} 注册表含 ≥6 算法（{len(reg)}）")
        # 随机基线 + 一类元启发能跑通并返回 best
        info = json.loads(D.domain_start("gcvar", json.dumps(prob), "random",
                                         json.dumps({"max_iter": 60, "seed": 7})))
        check(info.get("sense") == "min", f"gcvar {vt} domain_start(random) 返回 info")
        last = None
        while True:
            s = D.domain_step()
            if s is None:
                break
            last = json.loads(s)
        check(last is not None and "best" in last, f"gcvar {vt} random 跑出 best")
        # 页接线：PAGE_DOMAIN=gcvar + 渲染资源
        html = read(f"problem/{vdir[vt]}/index.html")
        check('PAGE_DOMAIN' in html and 'gcvar' in html, f"gcvar {vt} 页 PAGE_DOMAIN=gcvar 接线")
        check("js/domain_page.js" in html and "vizCanvas" in html,
              f"gcvar {vt} 页渲染接线完整（domain_page.js + vizCanvas）")
        check(vt in html or vdir[vt] in html, f"gcvar {vt} 页含变体标识")

    # H3 期：装箱变体家族 bpvar（3 变体单域多预设）结构断言
    print("\n[3k] H3 装箱变体家族 bpvar（3 变体单域多预设）")
    bvars = ["vsbinpack", "binpack2d", "strippack"]
    bdir = {"vsbinpack": "vsbinpack", "binpack2d": "binpack2d", "strippack": "strippack"}
    for vt in bvars:
        prob = D.bpv_make(variant=vt, n=30, seed=7)
        check("variant" in prob and "n" in prob and "items" in prob,
              f"bpvar {vt} bpv_make 产出实例")
        reg = D._bpvar_reg(vt)
        check(len(reg) >= 6, f"bpvar {vt} 注册表含 ≥6 算法（{len(reg)}）")
        info = json.loads(D.domain_start("bpvar", json.dumps(prob), "random",
                                         json.dumps({"max_iter": 60, "seed": 7})))
        check(info.get("sense") == "min", f"bpvar {vt} domain_start(random) 返回 info")
        last = None
        while True:
            s = D.domain_step()
            if s is None:
                break
            last = json.loads(s)
        check(last is not None and "best" in last, f"bpvar {vt} random 跑出 best")
        # 页接线：PAGE_DOMAIN=bpvar + 渲染资源
        html = read(f"problem/{bdir[vt]}/index.html")
        check('PAGE_DOMAIN' in html and 'bpvar' in html, f"bpvar {vt} 页 PAGE_DOMAIN=bpvar 接线")
        check("js/domain_page.js" in html and "vizCanvas" in html,
              f"bpvar {vt} 页渲染接线完整（domain_page.js + vizCanvas）")
        check(vt in html or bdir[vt] in html, f"bpvar {vt} 页含变体标识")


def check_ux_regressions() -> None:
    import os
    """走查修复回归守卫（2026-09-26）：FN_JS 镜像、bench SMA 行、TSP roster 锚点、
    导航按钮落点——每条都对应一次真实走查事故，防复发。"""
    print("\n[3l] 走查修复回归守卫（UX 波）")
    try:
        # ① FN_JS 必须镜像 py/domains.py FUNCS 全部键——ee884fc 补过 bbob 镜像
        #    被 1afd16f 覆盖，画布静默回退 sphere=展示错误数据（P0-2 假闭环教训）
        js = read("js/domain_page.js")
        m = re.search(r"const FN_JS = \{(.*?)\n\};", js, re.S)
        check(m is not None, "FN_JS 块存在")
        if m:
            sp = os.path.join(ROOT, "py")
            if sp not in sys.path:
                sys.path.insert(0, sp)
            import domains as _dm  # noqa: E402
            keys = set(re.findall(r"^\s*([A-Za-z0-9_]+)\s*:", m.group(1), re.M))
            missing = [k for k in _dm.FUNCS if k not in keys]
            check(not missing, f"FN_JS 镜像 py/domains.py FUNCS 全部 {len(_dm.FUNCS)} 键",
                  f"缺：{missing}")
        # ② bench 成绩行与 roster 自洽：roster 标「实测」的算法必须有成绩行（SMA 事故）
        bench = json.load(open(os.path.join(ROOT, "data", "bench.json"), encoding="utf-8"))
        sma_rows = [r for r in bench["rows"] if "黏菌" in r[0]]
        check(len(sma_rows) == 1 and all(str(v).strip() for v in sma_rows[0][1]),
              "bench.json 含黏菌算法 SMA 行（30/60/100 三值齐全）")
        # ③ TSP 枢纽 roster：算法演示链挂 #tool-root（#demo 只存在于域演示页；
        #    F7 nav_extra 的 multiobj/?algo=#demo 是域演示页合法切域链，不在禁止之列）
        tsp_html = read("problem/tsp/index.html")
        check("#tool-root" in tsp_html, "TSP 枢纽含 #tool-root 演示锚链")
        algo_demo = re.findall(r'href="[^"]*/algo/[^"]*#demo', tsp_html)
        check(not algo_demo, "TSP 枢纽无算法页 #demo 死锚（算法页锚是 tool-root）",
              f"残留 {len(algo_demo)} 条")
        # ④ 一级导航按钮落点：算法▾→/algo/、问题▾→/problem/（不再借用他轴页面）
        idx = read("index.html")
        check(re.search(r'class="dd-btn" href="[^"]*algo/index\.html">算法', idx) is not None,
              "算法▾ 按钮落 /algo/ 总览")
        check(re.search(r'class="dd-btn" href="[^"]*problem/index\.html">问题', idx) is not None,
              "问题▾ 按钮落 /problem/ 总览")
        check("什么是元启发式" in idx, "科普▾ 含「什么是元启发式」直白入口")
        check('class="dd-btn" href="' not in idx
              or re.search(r'class="dd-btn" href="[^"]*encyclopedia/index\.html">算法', idx) is None,
              "算法▾ 不再借用 encyclopedia")
        # ⑤ 总览页内容抽检：家族节/类节数与数据层一致
        algo_ov = read("algo/index.html")
        fams = json.load(open(os.path.join(ROOT, "data", "families.json"), encoding="utf-8"))
        check(algo_ov.count("<h2>") == len(fams), f"算法总览家族节数 = {len(fams)}")
        prob_ov = read("problem/index.html")
        probs = json.load(open(os.path.join(ROOT, "data", "problems.json"), encoding="utf-8"))
        n_nav_groups = len({t["group"] for t in probs["abstract_types"]})  # 含「开放登记」：它的问题页也要有入口
        check(prob_ov.count("<h2>") == n_nav_groups + 2,
              f"问题总览类节数 = {n_nav_groups} 类（含开放登记）+ 演示域 + 归约")
        # ⑥ β 波守卫：lead 数字派生 / #intro 锚 / 窄屏限高 / 打印词条例外
        n_ent = len([t for t in probs["abstract_types"] if t.get("status") == "entry"])
        check(f"{n_ent} 个以词条登记" in prob_ov,
              f"问题总览 lead 词条数为数据派生（{n_ent}）")
        enc = read("encyclopedia/index.html")
        check('id="intro"' in enc, "百科总纲含 #intro 三分钟入门锚")
        check("什么是元启发式" in enc, "百科总纲 #intro 段正文在场")
        css = read("css/style.css")
        # 正向断言（教训：反向字符串/跨注释正则都会误伤——注释文本与 .pltbl 打印重置
        # 都含「max-height none」字样，只有「62vh 限高在场 + 重置仅限 .pltbl」是可断言事实）
        check("max-height: 62vh" in css and ".pltbl { max-height: none !important" in css,
              "窄屏 dd-panel 限高 62vh 在场（β2 吞屏守卫）且打印重置仅限 .pltbl")
        check(".fambox.entrybox { display: block !important; }" in css,
              "打印样式保留词条/入门框（entrybox 例外）")
        check('href="encyclopedia/index.html#intro' in idx or "/encyclopedia/#intro" in idx,
              "科普菜单「3 分钟入门」挂 #intro 锚")
        check("词条 ×" not in idx and "词条 ×" not in prob_ov,
              "「词条 ×N」汇总行绝迹（ef0c4df 教训）")
        # ⑦ 测试服波守卫（2026-09-26 深夜主播走查）：过时文案 / 归类锚 / 同值注 / 孤立引号
        n_algos = len(json.load(open(os.path.join(ROOT, "data", "algos.json"), encoding="utf-8")))
        cmp_html = read("compare/index.html")
        check("五种智能优化算法" not in idx and "五个算法" not in idx,
              "首页无「五种/五个算法」过时文案（主播 C 实锤）")
        check("五种智能优化算法" not in cmp_html and "五个算法" not in cmp_html,
              "对比页无「五种/五个算法」过时文案")
        demo_html = read("demo/index.html")
        check(f"{n_algos} 个元启发式算法" in idx,
              f"首页算法计数为数据派生（{n_algos}，导览口径）")
        check(f"{n_algos} 种智能优化算法" in demo_html,
              f"演示页算法计数为数据派生（{n_algos}）")
        red = read("problem/reductions/index.html")
        # 归约页只剩归约图
        check("归约图" in red or "归约" in red,
              "归约页保留归约图（词条墙已全部升 page）")
        check("装箱判定 ≤ₚ 划分" not in red and "≡ₚ 2-箱装箱" in red,
              "装箱↔划分关系改「划分 ≡ₚ 2-箱装箱」（归约方向误导修复）")
        check("收敛平台" in tsp_html,
              "TSP 成绩表含同值收敛平台说明（主播 D 证伪案配套注解）")
        check("最优路径长（越小越好）" in tsp_html,
              "TSP 成绩表口径在表头标注")
        check("Jaya 必胜" not in idx and "Jaya 必胜" not in tsp_html,
              "「Jaya 必胜」怪名绝迹（更名 Jaya 算法 JAYA）")
        stray = []
        for _root, _dirs, files in os.walk(ROOT):
            if ".git" in _root:
                continue
            for fn in files:
                if fn == "index.html":
                    p = os.path.join(_root, fn)
                    if '</p>"' in open(p, encoding="utf-8").read():
                        stray.append(os.path.relpath(p, ROOT))
        check(not stray, "全部产物页无孤立引号 </p>\"（主播 C 在背包页实锤）",
              f"污染页：{stray[:3]}")
        # ⑧ 目标用户波守卫（2026-09-27 五用户走查）：file:// 兼容 / 嵌套锚 / 引用更名
        # 浏览器可运行守卫（2026-10 发布前复检）：此前为兼容 file:// 把 worker 改成 classic、UI 脚本去掉 type=module，
        # 结果 Pyodide 在 classic worker 里直接抛 "Classic web workers are not supported"，tool.js 因 import.meta
        # 在非 module 脚本里语法错误——全站交互页在任何浏览器里都跑不起来，而 HTTP 200 类检查看不出来
        def _scripts(rel):
            return re.findall(r"<script\b[^>]*>", read(rel))
        for jsname in sorted(os.listdir(os.path.join(ROOT, "js"))):
            if jsname.endswith(".js") and "import.meta" in open(os.path.join(ROOT, "js", jsname), encoding="utf-8").read():
                for rel in ("demo/index.html", "compare/index.html", "problem/vrp/index.html", "index.html"):
                    for t in _scripts(rel):
                        if re.search(rf'src="[^"]*js/{re.escape(jsname)}"', t):
                            check('type="module"' in t, f"{rel} 加载含 import.meta 的 {jsname} 必须是 module 脚本")
        check(any('type="module"' in t and "js/tool.js" in t for t in _scripts("demo/index.html")),
              "demo 页以 type=\"module\" 加载 tool.js")
        check(any('type="module"' in t and "js/compare.js" in t for t in _scripts("compare/index.html")),
              "对比页以 type=\"module\" 加载 compare.js")
        # 兼容性检查脚本必须在每个交互页里、且先于主脚本加载（旧浏览器 / file:// 打开时给人话提示，而不是静默卡住）
        for rel, main in (("demo/index.html", "js/tool.js"), ("compare/index.html", "js/compare.js"),
                          ("algo/f2-si/pso/index.html", "js/tool.js"), ("problem/knapsack/index.html", "js/domain_page.js")):
            srcs = [m for m in re.findall(r'<script\b[^>]*\bsrc="([^"]*)"', read(rel))]
            names = [x for x in srcs if x.endswith(("js/compat.js", main))]
            check(len(names) == 2 and names[0].endswith("js/compat.js") and names[1].endswith(main),
                  f"{rel} 先加载 compat.js 再加载 {main}", f"实际脚本顺序：{srcs}")
        wkr = open(os.path.join(ROOT, "js", "worker.js"), encoding="utf-8").read()
        dwkr = open(os.path.join(ROOT, "js", "domain_worker.js"), encoding="utf-8").read()
        check(re.search(r"import \{ SOLVERS_SRC[ ,}]", wkr) is not None and re.search(r"import \{ DOMAINS_SRC[ ,}]", dwkr) is not None
              and "importScripts(" not in wkr.replace("//", "") and "importScripts(" not in dwkr.replace("//", ""),
              "两个 worker 均为 module worker（ES import 内嵌源码；Pyodide 不支持 classic worker）")
        dpg = open(os.path.join(ROOT, "js", "domain_page.js"), encoding="utf-8").read()
        check("Math.sqrt((x * x + y * y) / 2)" in dpg,
              "ackley JS 镜像与 Python 等高线一致（/2 均值项，老张 P1）")
        # 绘制路由守卫：每个有问题页的域都必须被 drawPreset / drawViz 路由到专属绘制函数。
        # 此前 entryseq 的绘制代码写在 drawKPVAR 里却没人路由给它——词条页的画布一直是空的，控制台每代报一次错
        _doms = set()
        for _dp, _dn, _fs in os.walk(os.path.join(ROOT, "problem")):
            if "index.html" in _fs:
                _m = re.search(r'window\.PAGE_DOMAIN = "([^"]+)"', open(os.path.join(_dp, "index.html"), encoding="utf-8").read())
                if _m:
                    _doms.add(_m.group(1))
        for _fn in ("drawPreset", "drawViz"):
            _m = re.search(r"function %s\([^)]*\) \{(.*?)\n\}" % _fn, dpg, re.S)
            _body = _m.group(1) if _m else ""
            for _d in sorted(_doms - {"multiobj"}):  # multiobj 是兜底分支（else drawMO）
                check(f'DOMAIN === "{_d}"' in _body, f"{_fn} 路由到了 {_d} 域的绘制函数")
        for jsname in ("tool.js", "compare.js", "domain_page.js"):
            txt = open(os.path.join(ROOT, "js", jsname), encoding="utf-8").read()
            sites = re.findall(r"new Worker\([^;]*\);", txt)
            check(bool(sites) and all('{ type: "module" }' in s for s in sites),
                  f"{jsname} 的 new Worker 均为 module 类型")
        check("window.PAGE_PREFIX" not in dpg and "document.currentScript" in dpg,
              "domain_page.js 站根由脚本自身位置推出（页面不再写死根绝对前缀，子路径部署可用）")
        mtx = read("matrix/index.html")
        check("href='/" not in mtx and 'href="/' not in mtx.replace('href="../', ""),
              "矩阵页无根绝对路径链接（file:// 下落盘根死链——阿伟 P0）")
        apps_html = read("applications/index.html")
        check('<a class="approw"' not in apps_html,
              "应用地图行不再用 <a> 包整行（嵌套锚非法——王老师 P1）")
        check(".pltbl { max-height: none" in css,
              "打印重置 .pltbl 滚动（家族页算法清单不截断——王老师 P1）")
        stub = read("algo/pso-tsp/index.html")
        check('name="robots" content="noindex"' in stub,
              "重定向桩含 noindex（防重复收录——小美）")
        check("乌鸦搜索 CSA" in idx and "乌鸦 CS<" not in idx and "乌鸦 CS（" not in idx,
              "乌鸦搜索更名 CSA（与布谷鸟 CS 撞缩写——小美）")
        check("Advances in Engineering Software" not in idx and "IDEC" not in read("algo/f2-si/fwa/index.html"),
              "DA/BBO/FWA 引用修正落产物（小林 P1 三连）")
        check('name="description"' in read("404.html"),
              "404 页含 meta description（小美）")
        mraw = open(os.path.join(ROOT, "data", "matrices.json"), encoding="utf-8").read()
        check("href='/" not in mraw,
              "matrices.json 源层无绝对路径 href")
        # 源层转义守卫：data/*.json 不得再出现裸 <（公式文本会吃 HTML）
        bad_json = []
        for fn in ("algos.json", "problems.json", "families.json", "mapping.json",
                   "meta.json", "matrices.json", "discovery.json", "apps.json"):
            btxt = open(os.path.join(ROOT, "data", fn), encoding="utf-8").read()
            if re.search(r"<(?![a-zA-Z/!])", btxt):
                bad_json.append(fn)
        check(not bad_json, "data/*.json 无裸 <（转义规范——王老师）", f"违规：{bad_json}")
    except Exception as e:  # noqa: BLE001
        check(False, "走查回归守卫", repr(e)[:140])


def check_discovery_coverage() -> None:
    """2026-09-29 新区块守卫：撤下留痕账本（coverage）+ 候选发现池（discovery）
    数字全部数据派生，断言必须与 data/*.json 实际计数一致（防硬编码回潮）。"""
    print("\n[4] 撤下留痕 / 候选发现池（数据派生）")
    try:
        pulled = json.load(open(os.path.join(ROOT, "data", "pulled_cells.json"), encoding="utf-8"))
        cells = pulled.get("cells", [])
        n_total = len(cells)
        n_pulled = sum(1 for c in cells if c.get("status") == "pulled")
        n_rework = sum(1 for c in cells if c.get("status") == "awaiting-rework")
        cov = read("coverage/index.html")
        check("更早的撤下留痕" in cov, "coverage 页含『更早的撤下留痕』区块")
        check('id="fairbudget"' in cov, "coverage 页含『同等评估预算实测』区块")
        check("不是缺陷" in cov, "coverage 撤下区块含框架口径（撤下是防假跑门证据非缺陷）")
        check(str(n_total) in cov and str(n_pulled) in cov and str(n_rework) in cov,
              f"coverage 撤下区块数字数据派生（total={n_total}/pulled={n_pulled}/rework={n_rework}）")
        # 每个 cell 的 格（域×算法）至少出现一个在 coverage 表中（抽样 bv_gsa / uflp）
        check(any(c["id"] in cov or c.get("algo", "").split("（")[0] in cov for c in cells),
              "coverage 撤下表含具体格条目（域×算法）")

        disc = json.load(open(os.path.join(ROOT, "data", "discovery.json"), encoding="utf-8"))
        cands = disc.get("candidates", [])
        n_cand = len(cands)
        n_adm = sum(1 for c in cands if c.get("status") == "admitted")
        n_prop = sum(1 for c in cands if c.get("status") == "proposed")
        dh = read("discovery/index.html")
        check("候选发现池" in dh, "discovery 页存在且含标题")
        check(str(n_cand) in dh and str(n_adm) in dh and str(n_prop) in dh,
              f"discovery 页计数数据派生（total={n_cand}/admitted={n_adm}/proposed={n_prop}）")
        check("discFilter" in dh, "discovery 页含过滤框")

        # 多目标页：算法机制区块（data/mo_algos.json 数据派生）+ 性能指标面板（hypervolume）
        mo = json.load(open(os.path.join(ROOT, "data", "mo_algos.json"), encoding="utf-8"))
        n_mo = len(mo.get("algos", []))
        moh = read("problem/multiobj/index.html")
        check("算法机制（多目标四主流）" in moh, "multiobj 页含『算法机制』区块")
        check(moh.count("mo-algo-card") == n_mo, f"multiobj 算法机制卡片数=数据派生（{n_mo}）")
        check('id="moHV"' in moh, "multiobj 页含超体积 HV 指标容器")
        check("IGD 不适用" in moh, "multiobj 性能指标面板诚实标注 IGD 不适用（无解析真前沿）")
        dpg2 = open(os.path.join(ROOT, "js", "domain_page.js"), encoding="utf-8").read()
        check("function hypervolume" in dpg2, "domain_page.js 含 hypervolume 计算（纯前端）")
    except Exception as e:  # noqa: BLE001
        check(False, "撤下留痕 / 候选发现池守卫", repr(e)[:140])


def check_dual_tree() -> None:
    """2026-09-29 架构待议项守卫：双 URL 树 canonical 闭环。
    ① 实页（非桩）HTML 不得有 href 指向 *-tsp/ 桩路径（内链必须指向家族限定正典 URL）；
    ② 每个桩 noindex + canonical 两要素齐全；
    ③ sitemap 只收正典（不收任何桩 URL），桩数量只增不减。"""
    print("\n[4b] 双 URL 树 canonical 闭环（架构待议项 2026-09-29）")
    try:
        algo_root = os.path.join(ROOT, "algo")
        stub_re = re.compile(r'href="([^"]*[a-z0-9]-tsp/[^"]*)"')
        stubs = []
        for name in sorted(os.listdir(algo_root)):
            if not name.endswith("-tsp"):
                continue
            idx = os.path.join(algo_root, name, "index.html")
            if not os.path.isfile(idx):
                continue
            stubs.append(name)
            h = open(idx, encoding="utf-8").read()
            check("noindex" in h, f"桩 {name} 含 noindex")
            if HAS_SITE:
                check("canonical" in h, f"桩 {name} 含 canonical")
        # ① 实页内链指向桩=违规
        bad = []
        for root, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", "docs",
                                                    "py", "tools", "scripts", "samples")]
            rel = os.path.relpath(root, ROOT).replace(os.sep, "/")
            if re.search(r"[a-z0-9]-tsp$", rel):
                continue  # 桩自身目录
            for fn in files:
                if not fn.endswith(".html"):
                    continue
                fp = os.path.join(root, fn)
                txt = open(fp, encoding="utf-8", errors="ignore").read()
                for mm in stub_re.findall(txt):
                    bad.append((rel + "/" + fn, mm))
        check(not bad, f"实页无指向桩路径的内链（违规 {len(bad)} 处）",
              f"样例：{bad[:3]}" if bad else "")
        # ③ sitemap 不收桩 + 桩数量只增不减
        if HAS_SITE:
            sm = read("sitemap.xml")
            sm_stubs = [s for s in stubs if f"/algo/{s}/" in sm]
            check(not sm_stubs, f"sitemap 只收正典不收桩（违规 {len(sm_stubs)}）")
        check(len(stubs) >= 45, f"桩数量只增不减（当前 {len(stubs)}）")
    except Exception as e:  # noqa: BLE001
        check(False, "双 URL 树守卫", repr(e)[:140])


def main() -> None:
    print("=" * 60)
    print("P1 算法可视化站 · 交付自检")
    print("=" * 60)
    run_tests()
    check_pages()
    check_404()
    check_redirects()
    check_moved_pages()
    check_solvers_src()
    check_applications()
    check_nav()
    check_recipe_upgrade()
    check_mapping()
    check_custom_scale()
    check_meta_refs()
    check_reductions_graph()
    check_problem_axis_v2()
    check_gcvar_bpvar()
    check_ux_regressions()
    check_discovery_coverage()
    check_dual_tree()
    check_sitemap()
    serve_and_fetch()
    print("\n" + "=" * 60)
    print(f"结果：{ok_count} 项通过，{fail_count} 项失败")
    print("=" * 60)
    sys.exit(1 if fail_count else 0)


if __name__ == "__main__":
    main()

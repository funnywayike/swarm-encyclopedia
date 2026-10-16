# -*- coding: utf-8 -*-
"""S5-A SEO 增强：对正式页面统一注入 Open Graph / Twitter Card / favicon / theme-color /
BreadcrumbList JSON-LD。由 build_pages.write() 在 URL 改写后调用（单一出口，全站生效）。

判据：页面含 canonical + meta description 才注入——重定向桩、sitemap.xml 等自动跳过。
面包屑数据由调用方传入（data/*.json 是单一事实源，本模块不重复加载）。
"""
import json
import re


def _attr(s: str) -> str:
    """属性值转义（title/desc 含引号时防破格）。"""
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def _breadcrumb(path: str, title: str, site, families, algos, problems) -> str:
    """按 path 推导 BreadcrumbList JSON-LD。不足两级（首页>本页）的单级页不出。"""
    parts = [p for p in path.replace("\\", "/").split("/") if p and p != "index.html"]
    if not parts:
        return ""
    items = [{"@type": "ListItem", "position": 1, "name": "首页", "item": site + "/"}]
    pos = 2

    if parts[0] == "algo" and len(parts) >= 2 and parts[1].startswith("f"):
        fam = next((f for f in families if f["dir"] == parts[1]), None)
        if fam:
            items.append({"@type": "ListItem", "position": pos,
                          "name": fam["name"], "item": f"{site}/algo/{parts[1]}/"})
            pos += 1
        if len(parts) >= 3:
            slug = parts[2]
            a = next((a for a in algos if a["slug"][: -len("-tsp")] == slug), None)
            if a:
                items.append({"@type": "ListItem", "position": pos,
                              "name": a["name"], "item": f"{site}/algo/{parts[1]}/{slug}/"})
    elif parts[0] == "problem" and len(parts) >= 2:
        name_map = {c["dir"]: c["name"] for c in problems["class_pages"]}
        name_map.update({v["id"]: "背包·" + v["name"] for v in problems["knapsack_variants"]})
        name_map.update({"knapsack": "0-1 背包", "continuous": "连续优化", "multiobj": "多目标",
                         "graphcolor": "图着色", "binpack": "装箱"})
        nm = name_map.get(parts[1])
        if nm is None and len(parts) >= 3:  # problem/knapsack/<id>/ 已被上面 update 覆盖
            nm = parts[-1]
        items.append({"@type": "ListItem", "position": pos,
                      "name": nm or parts[1],
                      "item": site + "/problem/" + "/".join(parts[1:]) + "/"})
    elif parts[0] == "meta" and len(parts) >= 2:
        nm = title.split("·")[0].strip()
        items.append({"@type": "ListItem", "position": pos,
                      "name": nm, "item": f"{site}/meta/{parts[1]}/"})

    if len(items) < 2:
        return ""
    return json.dumps({"@context": "https://schema.org",
                       "@type": "BreadcrumbList",
                       "itemListElement": items}, ensure_ascii=False)


_FAVICON = ("data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 "
            "viewBox=%270 0 100 100%27%3E%3Ctext y=%27.9em%27 font-size=%2790%27%3E"
            "%F0%9F%90%9D%3C/text%3E%3C/svg%3E")


def enhance(content: str, path: str, site: str, families, algos, problems) -> str:
    """write() 后处理入口。返回增强后的 HTML（无需增强时原样返回）。"""
    if 'rel="canonical"' not in content or '<meta name="description"' not in content:
        return content
    m_t = re.search(r"<title>(.*?)</title>", content, re.S)
    m_d = re.search(r'<meta name="description" content="([^"]*)"', content)
    m_c = re.search(r'<link rel="canonical" href="([^"]*)">', content)
    if not (m_t and m_d and m_c):
        return content

    title, desc, curl = m_t.group(1), m_d.group(1), m_c.group(1)
    og_img = f"{site}/assets/og-cover.png"
    tags = [
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="群智能算法百科">',
        '<meta property="og:locale" content="zh_CN">',
        f'<meta property="og:title" content="{_attr(title)}">',
        f'<meta property="og:description" content="{_attr(desc)}">',
        f'<meta property="og:url" content="{curl}">',
        f'<meta property="og:image" content="{og_img}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{_attr(title)}">',
        f'<meta name="twitter:description" content="{_attr(desc)}">',
        f'<meta name="twitter:image" content="{og_img}">',
        f'<link rel="icon" href="{_FAVICON}">',
        '<meta name="theme-color" content="#f7f7f8" media="(prefers-color-scheme: light)">',
        '<meta name="theme-color" content="#0b0d12" media="(prefers-color-scheme: dark)">',
    ]
    bc = _breadcrumb(path, title, site, families, algos, problems)
    if bc:
        tags.append(f'<script type="application/ld+json">{bc}</script>')
    return content.replace(m_c.group(0), m_c.group(0) + "\n" + "\n".join(tags), 1)

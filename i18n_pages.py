# -*- coding: utf-8 -*-
"""页面标题 / H1 的英文：构建时挂 data-en（js/i18n.js 在英文模式下用它替换 <title> 和 <h1>）。

英文来源：
  - 算法页：algos.json 的 name_en；
  - 家族页：families.json 的 name_en；
  - 问题页：problems.json 的 en（+ 缩写）；
  - 方法论页：meta.json 的 en；
  - 其余关键页：data/i18n_pages.json（{"/coverage/": {"title": …, "h1": …}}）。
"""
import io
import json
import os
import re

ROOT = os.path.dirname(os.path.abspath(__file__))


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def _unesc(s: str) -> str:
    return s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')


def _clean_problem_en(en: str, abbr: str) -> str:
    en = _unesc(en)
    en = re.sub(r"\s*\(" + re.escape(abbr) + r"\)\s*$", "", en).strip()
    en = re.sub(r",\s*" + re.escape(abbr) + r"$", "", en)
    return en


def en_summary(text, heading: str = "In brief") -> str:
    """英文摘要块（仅英文模式下显示，见 css .en-summary）。没有英文摘要时不输出。"""
    if not text:
        return ""
    esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'<section class="en-summary" lang="en"><h2>{heading}</h2><p>{esc}</p></section>'


def build_table(algos, families, problems, meta_pages, algo_url, fam_url):
    t = {}
    for a in algos:
        if a.get("name_en"):
            n = a["name_en"]
            t[algo_url(a["slug"])] = {
                "title": f"{n} for TSP: online demo with tour animation and convergence curve",
                "h1": f"{n} for TSP: online demo"}
    for f in families:
        if f.get("name_en"):
            t[fam_url(f)] = {"title": f"{f['name_en']} · metaheuristic algorithm family {f['id']}",
                             "h1": f["name_en"]}
    for p in problems["abstract_types"]:
        if p.get("status") == "page":
            en = _clean_problem_en(p["en"], p["abbr"])
            t[f"/problem/{p['dir']}/"] = {"title": f"{en} ({p['abbr']}) · abstract problem type",
                                          "h1": f"{en} ({p['abbr']})"}
    for c in problems["class_pages"]:
        en = _unesc(c.get("en") or "")
        if en:
            t[f"/problem/{c['dir']}/"] = {"title": f"{en} · problem page", "h1": en}
    for v in problems["knapsack_variants"]:
        en = _unesc(v.get("en") or "")
        if en:
            t[f"/problem/knapsack/{v['id']}/"] = {"title": f"{en} · knapsack variant", "h1": en}
    for m in meta_pages:
        en = _unesc(m.get("en") or "")
        if en:
            t[f"/meta/{m['dir']}/"] = {"title": f"{en} · metaheuristics meta-layer methodology", "h1": en}
    extra_path = os.path.join(ROOT, "data", "i18n_pages.json")
    if os.path.exists(extra_path):
        with io.open(extra_path, encoding="utf-8") as f:
            t.update(json.load(f))
    return t


def apply(path: str, content: str, table) -> str:
    """path 形如 algo/f2-si/pso/index.html；命中词典时给 <title> 与第一个 <h1> 挂 data-en。"""
    if not path.endswith("index.html") or "<title>" not in content:
        return content
    url = "/" + path[:-len("index.html")]
    en = table.get(url)
    if not en:
        return content
    content = content.replace("<title>", f'<title data-en="{_esc(en["title"])}">', 1)
    content = re.sub(r"<h1(?![^>]*data-en)([^>]*)>", lambda m: f'<h1{m.group(1)} data-en="{_esc(en["h1"])}">', content, count=1)
    return content

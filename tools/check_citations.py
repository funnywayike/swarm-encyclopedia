# -*- coding: utf-8 -*-
"""文献引用核对工具：把站点数据里的正式引用逐条拿去 Crossref 查，比对 作者 / 年份 / 卷 / 页码（或文章号）/ 刊名。

硬性规定（docs/admission-policy.md §4）：禁止编造或写错作者、年份、刊名、卷页。本工具把「靠记忆」变成「可复核」。

    python tools/check_citations.py                 # 全部来源，结果写 docs/citation-report.md
    python tools/check_citations.py --only algos    # 只查 algos.json
    python tools/check_citations.py --sample 10     # 随机抽 N 条（发版前抽查用）
    python tools/check_citations.py --offline       # 只用缓存，不联网

结论分四类：
    OK        Crossref 上找到同一篇，卷/页/年份与引用一致
    MISMATCH  找到同一篇，但卷/页/年份/刊名不一致（需要人工确认并修正）
    NOMATCH   没找到可信匹配（可能是书、学位论文、会议论文、中文文献，或引用本身有误）——需人工核
    SKIP      明确不是期刊条目（书/学位论文/中文），不做自动核对

自动核对只能证明「期刊条目写对了」，不能证明「这篇文章确实支持页面上的论述」。会议论文、书籍仍需人工。
"""
import argparse
import html
import io
import json
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CACHE = os.path.join(ROOT, ".cache", "citations.json")
OVERRIDES = os.path.join(ROOT, "data", "citation_overrides.json")  # 人工核实过的例外：{"位置": {"reason": "...", "url": "..."}}
UA = "swarm-encyclopedia-citation-check/0.1 (mailto:citations@example.org)"
LF_ = chr(10)


# ---------------------------------------------------------------- 收集
def _walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from ((f"{k}.{p}" if p else k, s) for p, s in _walk(v))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from ((f"[{i}]{('.' + p) if p else ''}", s) for p, s in _walk(v))
    elif isinstance(o, str):
        yield "", o


def _load(name):
    with io.open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
        return json.load(f)


YEAR = re.compile(r"\b(?:19[3-9]\d|20[0-2]\d)\b")


def fingerprint(entries=None):
    """全部正式引用的指纹：任何一条引用被改动/新增/删除，指纹就变——测试据此要求重新核对。"""
    import hashlib
    entries = entries if entries is not None else collect(None)
    h = hashlib.sha256()
    for src, where, text in sorted(entries):
        h.update(f"{src}|{where}|{text}".encode("utf-8"))
        h.update(b"\n")
    ov = OVERRIDES
    if os.path.exists(ov):
        # Hash semantic JSON consistently across Windows CRLF and Linux LF checkouts.
        with io.open(ov, encoding="utf-8-sig") as f:
            h.update(json.dumps(json.load(f), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return h.hexdigest()


def collect(only=None):
    """返回 [(来源标签, 位置, 原文)]。只收「正式引用」字段，不扫正文里的行文式提及。"""
    out = []
    if only in (None, "algos"):
        for a in _load("algos.json"):
            out.append(("algos.json", f"{a['key']}.paper", a["paper"]))
            for i, r in enumerate(a.get("refs", [])):
                out.append(("algos.json", f"{a['key']}.refs[{i}]", r))
    if only in (None, "problems"):
        d = _load("problems.json")
        for sec in ("abstract_types", "knapsack_variants", "class_pages"):
            for t in d[sec]:
                for i, s in enumerate(t.get("sources", [])):
                    out.append(("problems.json", f"{sec}.{t.get('id')}.sources[{i}]", s))
    if only in (None, "mapping"):
        d = _load("mapping.json")
        for sec, items in d.items():
            if isinstance(items, list):
                for i, it in enumerate(items):
                    if isinstance(it, dict):
                        for fld in ("src", "evidence"):
                            v = it.get(fld)
                            if isinstance(v, str) and YEAR.search(v) and re.search(r"\d+\s*[\(:]", v):
                                out.append(("mapping.json", f"{sec}[{i}].{fld}", v))
    if only in (None, "meta"):
        d = _load("meta.json")
        for pi, p in enumerate(d.get("pages", [])):
            for ri, r in enumerate(p.get("refs", [])):
                if r.get("cite"):
                    out.append(("meta.json", f"pages[{pi}].refs[{ri}].cite", r["cite"]))
    return out


# ---------------------------------------------------------------- 解析
def clean(s):
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    s = re.sub(r"[（(][^）)]*[一-鿿][^）)]*[）)]", " ", s)  # 含中文的括注
    s = re.sub(r"[一-鿿]+", " ", s) if not re.search(r"[A-Za-z]{4,}", re.sub(r"[一-鿿]+", " ", s)) else re.sub(r"[；;].*$", "", s)
    return re.sub(r"\s+", " ", s).strip()


def parse(text):
    t = clean(text)
    info = {"clean": t, "year": None, "vol": None, "issue": None, "pages": None, "article": None, "kind": "article"}
    m = YEAR.search(t)
    info["year"] = int(m.group(0)) if m else None
    # 卷(期):页-页  |  卷:页-页  |  , 卷, 页-页  |  卷, 文章号
    for pat in (r"\b(\d{1,3})\s*\((\d{1,3})\)\s*[:,]\s*(\d{1,5})\s*[-–]\s*(\d{1,5})",
                r"\b(\d{1,3})\s*[:,]\s*(\d{1,5})\s*[-–]\s*(\d{1,5})\b",
                r"[,\s](\d{1,3}),\s*(\d{1,5})\s*[-–]\s*(\d{1,5})"):
        mm = re.search(pat, t)
        if mm:
            g = mm.groups()
            info["vol"] = g[0]
            if len(g) == 4:
                info["issue"], info["pages"] = g[1], f"{g[2]}-{g[3]}"
            else:
                info["pages"] = f"{g[1]}-{g[2]}"
            break
    if not info["vol"]:
        mm = re.search(r"[,\s](\d{1,3}),\s*(\d{5,7})\b", t)
        if mm:
            info["vol"], info["article"] = mm.group(1), mm.group(2)
    if re.search(r"\b(Handbook|Wiley|Springer|Princeton|Freeman|Addison|MIT Press|Cambridge|Prentice|Dissertation|Thesis|thesis|Technical Report|TR\d|Textbook|Book|Chapter|博士|硕士|技术报告)\b", t) and not info["vol"]:
        info["kind"] = "book"
    return info


# ---------------------------------------------------------------- Crossref
def _cache():
    if os.path.exists(CACHE):
        with io.open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save(c):
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with io.open(CACHE, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False)


def crossref(q, offline=False, cache=None):
    if q in cache:
        return cache[q]
    if offline:
        return None
    url = ("https://api.crossref.org/works?rows=5&select=title,volume,issue,page,article-number,container-title,issued,DOI,author,type"
           "&query.bibliographic=" + urllib.parse.quote(q))
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
                items = json.load(r)["message"]["items"]
            cache[q] = items
            time.sleep(1.1)
            return items
        except Exception as e:  # noqa: BLE001
            if attempt < 5 and any(x in str(e) for x in ("429", "SSL", "timed out", "reset", "503")):
                time.sleep(5 + 5 * attempt)
                continue
            return None


def toks(s):
    return set(re.findall(r"[a-z]{4,}", s.lower()))


def surname(text):
    m = re.match(r"\s*([A-Z][A-Za-z'\-]+)", text)
    return m.group(1).lower() if m else None


def _score(info, it, cited_t, sn):
    title = " ".join(it.get("title") or [])
    journal = " ".join(it.get("container-title") or [])
    auth = " ".join((a.get("family") or "").lower() for a in (it.get("author") or []))
    sc = 0.0
    if title:
        sc += 0.6 * len(toks(title) & cited_t) / max(len(toks(title)), 1)
    if journal:
        sc += 0.25 * len(toks(journal) & cited_t) / max(len(toks(journal)), 1)
    if sn and sn in auth:
        sc += 0.15
    return sc


def _year(it):
    return ((it.get("issued") or {}).get("date-parts") or [[None]])[0][0]


def _norm(x):
    import unicodedata
    return re.sub(r"[^a-z]", "", unicodedata.normalize("NFKD", x).encode("ascii", "ignore").decode().lower())


def cited_surnames(clean_text):
    """引用里「姓, 缩写.」形式给出的作者姓（只在有 ≥2 位带缩写作者时才可靠；否则返回空表示不核对）。"""
    head = re.split(r"\(\s*(?:19|20)\d\d|,\s*(?:19|20)\d\d", clean_text, maxsplit=1)[0]
    names = re.findall(r"([A-Z][A-Za-z'’\-]+(?:\s[A-Z][a-z]+)?),\s*(?:[A-Z]\.|[A-Z]\.?-?[A-Z]\.)", head)
    return [_norm(n.split()[-1]) for n in names] if len(names) >= 2 else []


def _diffs(info, it):
    rv, rp, ra = it.get("volume"), (it.get("page") or "").replace("–", "-"), it.get("article-number")
    out = []
    if info["vol"] and rv and info["vol"] != str(rv):
        out.append(f"卷：引用 {info['vol']} / 实际 {rv}")
    if info["pages"] and rp and info["pages"] != rp:
        out.append(f"页码：引用 {info['pages']} / 实际 {rp}")
    if info["article"] and ra and info["article"] != str(ra):
        out.append(f"文章号：引用 {info['article']} / 实际 {ra}")
    if info["article"] and not ra and rp and info["vol"] == str(rv) and info["article"] not in rp:
        out.append(f"文章号：引用 {info['article']} / 实际页码 {rp}")
    sn = cited_surnames(info["clean"])
    if sn and it.get("author"):
        def has(n):  # Crossref 有时把全名放进 family 字段（Zong Woo Geem）、或带前缀（Abd Elaziz），按子串匹配
            return any(n and n in _norm((a.get("family") or "") + (a.get("name") or "")) for a in it["author"])

        def cited(a):
            f = _norm(a.get("family") or a.get("name") or "")
            return any(n and (n in f or f.endswith(n) or n.endswith(f)) for n in sn)

        missing = [n for n in sn if not has(n)]
        extra = [a.get("family") or a.get("name") for a in it["author"] if not cited(a)] if len(it["author"]) <= 8 else []
        if missing:
            out.append("作者：引用里的 " + "、".join(missing) + " 不在 Crossref 作者列表中" + (f"（实际作者含 {'、'.join(extra[:4])}）" if extra else ""))
        elif extra and len(sn) < len(it["author"]):
            out.append("作者：引用漏了 " + "、".join(str(x) for x in extra)[:60])
    return out


def judge(info, items):
    """在候选里挑同一篇：先找与引用卷/页完全一致的（OK）；否则取同年份里最像的，卷/页不符 = MISMATCH。"""
    if not items:
        return "NOMATCH", "Crossref 无结果", None
    cited_t = toks(info["clean"])
    sn = surname(info["clean"])
    scored = [(_score(info, it, cited_t, sn), it) for it in items]
    plausible = [(sc, it) for sc, it in scored if sc >= 0.55]
    # 没有标题可比对的短引用（作者(年份). 刊名 卷(期):页）：作者姓 + 卷 + 首页 + 年份都对上，就是同一篇
    if sn and info["vol"] and info["pages"]:
        first = info["pages"].split("-")[0]
        for sc, it in scored:
            auth = " ".join(_norm((a.get("family") or "") + (a.get("name") or "")) for a in (it.get("author") or []))
            if (sn in auth and str(it.get("volume")) == info["vol"]
                    and (it.get("page") or "").replace("–", "-").split("-")[0] == first
                    and (not info["year"] or not _year(it) or abs(int(_year(it)) - info["year"]) <= 1)):
                d = _diffs(info, it)
                return ("MISMATCH", "；".join(d), it) if d else ("OK", "", it)
    if not plausible:
        top = max(scored, key=lambda x: x[0])
        return "NOMATCH", f"最相近匹配度 {top[0]:.2f}", top[1]
    for sc, it in plausible:  # 任何一个候选与引用的卷/页/文章号完全一致，即视为正确
        if not _diffs(info, it) and (not info["year"] or not _year(it) or abs(int(_year(it)) - info["year"]) <= 1):
            return "OK", "", it
    same_year = [(sc, it) for sc, it in plausible if not info["year"] or not _year(it) or abs(int(_year(it)) - info["year"]) <= 1]
    if not same_year:
        return "NOMATCH", f"同名候选的年份都对不上（引用 {info['year']}）——可能是再版/转载或引用年份有误", plausible[0][1]
    sc, it = max(same_year, key=lambda x: x[0])
    d = _diffs(info, it)
    return ("MISMATCH", "；".join(d), it) if d else ("OK", "", it)




# ---------------------------------------------------------------- arXiv 与多段引用
ARXIV = re.compile(r"arXiv[:\s]*(\d{4}\.\d{4,5})", re.I)


def arxiv_lookup(aid, cache, offline=False):
    key = "arxiv:" + aid
    if key in cache:
        return cache[key]
    if offline:
        return None
    url = "http://export.arxiv.org/api/query?id_list=" + aid
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=30) as r:
            xml = r.read().decode("utf-8", "ignore")
        time.sleep(3.1)  # arXiv 要求每 3 秒 1 次
    except Exception:  # noqa: BLE001
        return None
    m = re.search(r"<entry>.*?<title>(.*?)</title>.*?<published>(\d{4})", xml, re.S)
    res = {"title": re.sub(r"\s+", " ", m.group(1)).strip(), "year": int(m.group(2))} if m and "<id>" in xml and "Error" not in xml[:400] else {}
    cache[key] = res
    return res


def judge_arxiv(text, cache, offline):
    ids = ARXIV.findall(text)
    if not ids:
        return None
    ok, bad = [], []
    for aid in ids:
        r = arxiv_lookup(aid, cache, offline)
        if r is None:
            return None
        if not r:
            bad.append(aid)
        else:
            ok.append((aid, r))
    if bad:
        return "MISMATCH", f"arXiv:{'、'.join(bad)} 不存在", None
    return "OK", "arXiv：" + "；".join(f"{a} {r['title'][:50]} ({r['year']})" for a, r in ok), None


def split_parts(text):
    """把「A；B」「A / B」这样的多段引用拆开分别核对。"""
    parts = [x.strip() for x in re.split(r"[；;]|\s/\s", clean(text)) if x.strip()]
    return parts if len(parts) > 1 else []

# ---------------------------------------------------------------- 主流程
def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["algos", "problems", "mapping", "meta"])
    ap.add_argument("--sample", type=int)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "citation-report.md"))
    args = ap.parse_args(argv)
    entries = collect(args.only)
    if args.sample:
        random.Random().shuffle(entries)
        entries = entries[:args.sample]
    cache = _cache()
    overrides = {}
    if os.path.exists(OVERRIDES):
        with io.open(OVERRIDES, encoding="utf-8") as f:
            overrides = json.load(f)
    results = []
    for n, (src, where, text) in enumerate(entries, 1):
        info = parse(text)
        ov = overrides.get(f"{src}:{where}")
        if ov:
            results.append((src, where, text, "VERIFIED", "人工核实：" + ov["reason"], None))
            continue
        if info["kind"] == "book" or not re.search(r"[A-Za-z]{4,}", info["clean"]):
            results.append((src, where, text, "SKIP", "书籍/学位论文/中文条目，需人工核", None))
            continue
        ax = judge_arxiv(text, cache, args.offline)
        if ax:
            results.append((src, where, text) + ax)
            continue
        items = crossref(info["clean"], args.offline, cache)
        st, why, hit = judge(info, items)
        if st == "NOMATCH":
            sub = []
            for part in split_parts(text):
                pi = parse(part)
                if not (pi["year"] and pi["vol"] and re.search(r"[A-Za-z]{4,}", pi["clean"])):
                    continue
                sub.append(judge(pi, crossref(pi["clean"], args.offline, cache)))
            if sub and not any(x[0] == "MISMATCH" for x in sub) and any(x[0] == "OK" for x in sub):
                st, why, hit = "OK", "多段引用：其中带卷页的一段与 Crossref 一致", next(x[2] for x in sub if x[0] == "OK")
            elif any(x[0] == "MISMATCH" for x in sub):
                bad = next(x for x in sub if x[0] == "MISMATCH")
                st, why, hit = "MISMATCH", "多段引用中的一段：" + bad[1], bad[2]
        results.append((src, where, text, st, why, hit))
        if n % 20 == 0:
            _save(cache)
            print(f"  … {n}/{len(entries)}", file=sys.stderr)
    _save(cache)
    tally = {}
    for r in results:
        tally[r[3]] = tally.get(r[3], 0) + 1
    print("共 %d 条：" % len(results) + "，".join(f"{k} {v}" for k, v in sorted(tally.items())))
    fp = "" if args.only or args.sample else f"<!-- citations-sha256: {fingerprint(entries)} -->"
    lines = ["# 文献引用核对报告（自动生成）", fp, "",
             f"来源：`data/*.json` 的正式引用字段；核对：Crossref。共 {len(results)} 条——" + "，".join(f"{k} {v}" for k, v in sorted(tally.items())) + "。", "",
             "OK = 与 Crossref 一致；VERIFIED = 人工核实的例外（`data/citation_overrides.json`，写明理由）；MISMATCH = 找到同一篇但卷/页/年份/文章号不符（**需修正**）；"
             "NOMATCH/SKIP = 自动核对不了（书、学位论文、会议论文、中文文献，或引用本身有误），**需人工核**。", ""]
    for st in ("MISMATCH", "NOMATCH", "SKIP", "VERIFIED"):
        rows = [r for r in results if r[3] == st]
        if not rows:
            continue
        lines += [f"## {st}（{len(rows)}）", ""]
        for src, where, text, _, why, hit in rows:
            t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text)))[:200]
            doi = ""
            if hit and st in ("MISMATCH", "NOMATCH"):
                ht = " ".join(hit.get("title") or [])[:90]
                hv = " ".join(hit.get("container-title") or [])[:50]
                doi = (LF_ + "  - Crossref 最相近：" + f"{ht}｜{hv} {hit.get('volume')}:{hit.get('page') or hit.get('article-number')} ({_year(hit)}) doi:{hit.get('DOI')}")
            lines.append(f"- `{src}` `{where}`：{t}" + LF_ + f"  - {why}{doi}")
        lines.append("")
    with io.open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print("报告写入", os.path.relpath(args.out, ROOT))
    for src, where, text, st, why, hit in results:
        if st == "MISMATCH":
            print(f"  MISMATCH {src} {where}: {why}")
    return 1 if tally.get("MISMATCH") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

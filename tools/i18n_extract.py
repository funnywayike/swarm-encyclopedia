# -*- coding: utf-8 -*-
"""找出构建产物里还没有英文词条的中文文字，规则与 js/i18n.js 的翻译顺序一致。

    python tools/i18n_extract.py                      # 概览：按页面范围统计覆盖率
    python tools/i18n_extract.py --todo out.json      # 把未翻译的串写成待办（含出现次数、源 HTML）
    python tools/i18n_extract.py --scope chrome       # 只看「界面壳」：在 ≥ N 个页面出现的串
    python tools/i18n_extract.py --pages coverage/ matrix/ --todo todo.json

「单元」的取法（和浏览器里一样）：
  - 不含块级子元素、含中文的元素 → 键 = 规整空白后的 textContent；
  - 其余元素 → 逐个文本节点；
  - 属性 title / aria-label / placeholder / alt；<title>。
词典：data/i18n/*.json 的 strings（精确匹配）与 patterns（正则 → 模板）。
"""
import argparse
import collections
import glob
import json
import os
import re
import sys
from html.parser import HTMLParser

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CJK = re.compile(r"[㐀-鿿豈-﫿]")
VOID = {"br", "hr", "img", "input", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}
SKIP = {"script", "style", "code", "pre", "svg", "canvas", "textarea", "noscript"}
BLOCK = {"p", "div", "ul", "ol", "li", "table", "thead", "tbody", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section",
         "details", "summary", "blockquote", "form", "pre"}
ATTRS = ("title", "aria-label", "placeholder", "alt")


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


class Node:
    __slots__ = ("tag", "attrs", "kids", "text")

    def __init__(self, tag=None, attrs=None, text=None):
        self.tag, self.attrs, self.kids, self.text = tag, dict(attrs or {}), [], text

    def textcontent(self):
        if self.text is not None:
            return self.text
        return "".join(k.textcontent() for k in self.kids if k.tag not in ("script", "style"))

    def has_block(self):
        return any((k.tag in BLOCK) or k.has_block() for k in self.kids if k.text is None)

    def html(self):
        if self.text is not None:
            return self.text.replace("&", "&amp;").replace("<", "&lt;")
        a = ""
        for k, v in self.attrs.items():
            if k in ("href", "src") and v:
                v = re.sub(r"^(?:\.\./)*(?!https?:|#|mailto:|/|\?)", "/", v)
            a += f' {k}="{v}"' if v is not None else f" {k}"
        if self.tag in VOID:
            return f"<{self.tag}{a}>"
        return f"<{self.tag}{a}>" + "".join(k.html() for k in self.kids) + f"</{self.tag}>"

    def inner(self):
        return "".join(k.html() for k in self.kids)


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs)
        self.stack[-1].kids.append(n)
        if tag not in VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].kids.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].kids.append(Node(text=data))


def parse(path):
    t = Tree()
    t.feed(open(path, encoding="utf-8").read())
    return t.root


WORD = re.compile(r"[A-Za-z㐀-鿿]")


def is_unit(node):
    """与 js/i18n.js 的 isUnit 一致：直接含文字，或最多一个子元素。"""
    elems = 0
    for k in node.kids:
        if k.text is not None:
            if WORD.search(k.text):
                return True
        else:
            elems += 1
    return elems <= 1


SENT = re.compile(r"[，。；：！？]|——")


def sentence_like(node):
    """直接子文本里有 ≥ 6 个汉字且带句内标点（一句话），而不只是 “名称 + 徽章” 这类短标签。"""
    return any(k.text is not None and len(CJK.findall(k.text)) >= 6 and SENT.search(k.text) for k in node.kids)


def units(node, out, d=None):
    """收集 (kind, key, html) 单元。"""
    if node.text is not None:
        if CJK.search(node.text):
            out.append(("text", norm(node.text), None))
        return
    tag = node.tag
    if tag in SKIP or "data-no-i18n" in node.attrs:
        return
    for a in ATTRS:
        v = node.attrs.get(a)
        if v and CJK.search(v):
            out.append(("attr", norm(v), None))
    en = node.attrs.get("data-en")
    if en:
        return
    if tag == "title":
        tx = node.textcontent()
        if CJK.search(tx):
            out.append(("title", norm(tx), None))
        return
    if tag != "root" and CJK.search(node.textcontent()) and not node.has_block() and is_unit(node):
        key = norm(node.textcontent())
        # 整句命中词典 → 整个元素算已翻译；没命中时，浏览器会退回去逐个子节点翻译。
        # 只有「直接含句子级文字」的元素才需要整句翻译（逐段翻译会拼出不通顺的英文），否则往下拆。
        if (d is not None and d.has(key)) or sentence_like(node):
            out.append(("elem", key, node.inner()))
            return
    for k in node.kids:
        units(k, out, d)


def load_dictionary(path=None):
    """data/i18n/*.json（按文件名顺序合并）→ (strings, patterns)。重复的键以后面的文件为准。"""
    files = [path] if path else sorted(glob.glob(os.path.join(ROOT, "data", "i18n", "*.json")))
    strings, patterns = {}, []
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        strings.update(d.get("strings", {}))
        patterns.extend(d.get("patterns", []))
    return strings, patterns


class Dict:
    def __init__(self, path=None):
        strings, pats = load_dictionary(path)
        self.strings = {}
        self.patterns = [(re.compile(p), r) for p, r in pats]
        for k, v in strings.items():      # 键里的 {n} = 一串数字（与 js/i18n.js 一致）
            if "{n}" in k or "{*}" in k:
                rx = re.escape(k).replace(re.escape("{n}"), r"(\d+(?:\.\d+)?)").replace(re.escape("{*}"), r"(.+?)")
                self.patterns.append((re.compile("^" + rx + "$"), v))
            else:
                self.strings[k] = v

    def has(self, key):
        if key in self.strings:
            return True
        if any(p.search(key) for p, _ in self.patterns):
            return True
        # 与 js/i18n.js 一致：「甲 · 乙 · 丙」的文本可以按 " · " 拆段，每个含汉字的段都要有译文才算
        if " · " in key:
            return all((not CJK.search(part)) or self.has(part) for part in key.split(" · "))
        return False


def page_files(pages=None):
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, "**", "index.html"), recursive=True)):
        rel = os.path.relpath(f, ROOT).replace("\\", "/")
        if rel.startswith(("vendor/", "docs/", "samples/", ".")):
            continue
        if pages and not any(rel.startswith(p) or rel == p + "index.html" for p in pages):
            continue
        out.append(f)
    return out


def find_by_id(node, ident):
    if node.text is None:
        if node.attrs.get("id") == ident:
            return node
        for k in node.kids:
            r = find_by_id(k, ident)
            if r is not None:
                return r
    return None


def section_after(root, ident):
    """id=ident 的标题之后、同级下一个 <h2> 之前的所有内容（问题页「在线求解演示」整段）。"""
    def walk(n):
        if n.text is not None:
            return None
        for i, k in enumerate(n.kids):
            if k.attrs.get("id") == ident:
                out = Node("root")
                for sib in n.kids[i:]:
                    if sib is not k and sib.tag == "h2":
                        break
                    out.kids.append(sib)
                return out
            r = walk(k)
            if r is not None:
                return r
        return None
    return walk(root)


def collect(files, d=None, region=None):
    """{key: {"pages": set, "kind": kind, "html": 源 HTML}}"""
    acc = {}
    for f in files:
        rel = os.path.relpath(f, ROOT).replace("\\", "/")
        us = []
        tree = parse(f)
        if region:
            tree = section_after(tree, region)
            if tree is None:
                continue
        units(tree, us, d)
        for kind, key, h in us:
            e = acc.setdefault(key, {"pages": set(), "kind": kind, "html": h})
            e["pages"].add(rel)
    return acc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", nargs="*", help="只看这些页面（目录前缀，如 coverage/ matrix/）")
    ap.add_argument("--min-pages", type=int, default=1, help="只列在至少这么多页面出现的串（界面壳 = 10）")
    ap.add_argument("--region", help="只看 id 等于这个值的元素内部（例如 demo = 问题页的在线演示区）")
    ap.add_argument("--todo", help="把未翻译的串写成这个 JSON 文件")
    ap.add_argument("--list", type=int, default=0, help="打印前 N 条未翻译的串")
    a = ap.parse_args()
    d = Dict()
    files = page_files(a.pages)
    acc = collect(files, d, a.region)
    todo = {k: v for k, v in acc.items() if not d.has(k) and len(v["pages"]) >= a.min_pages}
    chars_all = sum(len(k) for k in acc if len(acc[k]["pages"]) >= a.min_pages)
    chars_todo = sum(len(k) for k in todo)
    print(f"{len(files)} 个页面；{len(acc)} 个中文单元，其中 ≥{a.min_pages} 页出现的 "
          f"{sum(1 for v in acc.values() if len(v['pages']) >= a.min_pages)} 个；未翻译 {len(todo)} 个"
          f"（{chars_todo}/{chars_all} 字）")
    rows = sorted(todo.items(), key=lambda kv: (-len(kv[1]["pages"]), kv[0]))
    for k, v in rows[:a.list]:
        print(f"{len(v['pages']):4d} [{v['kind']}] {k[:110]}")
    if a.todo:
        out = [{"zh": k, "kind": v["kind"], "n_pages": len(v["pages"]),
                "example": sorted(v["pages"])[0], "html": v["html"]} for k, v in rows]
        json.dump(out, open(a.todo, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("写入", a.todo)
    return 0 if not todo else 1


if __name__ == "__main__":
    sys.exit(main())

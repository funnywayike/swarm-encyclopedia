# -*- coding: utf-8 -*-
"""公开页面文案「用户化」规则表（开发者黑话 → 读者能懂的话；内部流程引用 → 删除）。

用法（一次性整改工具，也留作以后新文案的体检依据）：
    python tools/userfacing_rules.py            # 干跑：统计 + 列出若干 前/后 对照，不写盘
    python tools/userfacing_rules.py --apply    # 写回源文件（data/*.json 的字符串、*.py 里的字符串字面量；注释与代码不动）
    python tools/userfacing_rules.py --scan     # 只扫描：列出公开页面里仍存在的内部引用/黑话（selfcheck 同款规则）

规则顺序有意义：具体的在前，通用的在后。
"""
import io
import os
import re
import sys
import tokenize

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# (名称, 正则, 替换)
RULES = [
    # ---------- 内部调研/素材引用：读者看不到那份报告，留着只会困惑 ----------
    ("文献锚点句", r"文献锚点：综述 §[^。]*。", ""),
    ("素材锚点", r"素材锚点：报告 §[0-9.、§\-– ]*(?:、?blueprint R\d+)?。?", ""),
    ("报告锚点引用", r"[（(]?(?:见)?报告 §[0-9.、§\-– ]+[）)]?", ""),
    ("综述锚点带说明", r"综述 §[0-9.、/§\-– ]+[（(]([^）)]*)[）)]", r"\1"),
    ("综述锚点引用", r"[（(]?(?:见)?综述 §[0-9.、/§\-– ]+[）)]?", ""),
    ("blueprint 引用", r"[，、；]?\s*blueprint R\d+", ""),
    ("综述轮次括注", r"[（(][^）)]*?综述\s*R\d+(?:/R\d+)*[^）)]*[）)]", ""),
    ("综述轮次", r"[；，]?\s*综述\s*R\d+(?:/R\d+)*(?:\s*(?:现行案例|正式版|经典文献))?", ""),
    ("轮次尾标", r"，R\d{2,3}(?=[）)])", ""),
    # 只清全角空括注，以及「里面只有空白」的半角括号。绝不能碰紧挨着的 ASCII "()"：字符串里常嵌着 JavaScript / 代码示例
    # （function(){…}、e.preventDefault()），删掉就是语法错误——2026-10 这条规则曾因此弄坏全站内联脚本（tests/test_inline_scripts.py 守卫）
    ("空括注", r"（\s*）|\(\s+\)", ""),
    ("核对修正注记", r"[（(][^）)]*经联网核对[^）)]*[）)]", ""),
    ("调研轮次括注", r"[（(]R\d{1,3}[^）)]*[）)]", ""),
    ("调研轮次正典", r"[（(]R\d{1,3} 正典，?", "（"),
    ("调研轮次", r"R\d{1,3} 正典", "经典文献"),
    # ---------- 内部收录制度 ----------
    ("三档收编制括注", r"[（(]三档收编制[）)]", ""),
    ("三档收编制", r"三档收编制", "收录分档"),
    ("A 档主线链", r"A 档主线链", "主线"),
    ("A 档候选", r"[（(]A 档候选：素材已备，独立页待建[）)]", "（候选，独立页待建）"),
    ("A 档待建页", r"，?A 档待建页", "（待建页）"),
    ("B 档改进维度", r"B 档改进维度", "改进维度"),
    ("B 档维度", r"[（(]B 档维度[）)]", ""),
    ("C 档长尾", r"C 档长尾(?:表)?", "长尾"),
    # ---------- 内部版本/批次标记 ----------
    ("P1.3x 装配", r"，?P1\.3[abc] 组件化(?:后首批)?装配", "，组件化装配"),
    ("蓝图终点", r"[（(]P1\.3 蓝图终点达成[）)]", ""),
    ("节号尾巴", r"，§[0-9.]+(?=[）)])", ""),
    ("域实测来源", r"H\d (?:kpvar|gcvar|bpvar) 域实测", "本站变体页实测"),
    # ---------- 黑话 ----------
    ("防假跑自查三问", r"防假跑自查三问", "「真在优化吗」自查三问"),
    ("防假跑三问", r"防假跑三问", "自查三问"),
    ("防假跑测试", r"防假跑测试", "「是否真在优化」自动测试"),
    ("硬门槛句", r"（本站收录硬门槛，两次假跑教训写在源码注释里）", "（本站收录算法的硬性要求）"),
    ("防假跑", r"防假跑", "「真优化」校验"),
    ("正典出处", r"正典出处", "原始文献出处"),
    ("出处与正典", r"出处与正典", "出处与经典文献"),
    ("正典论文", r"正典论文", "经典论文"),
    ("正典", r"正典", "经典"),
    ("算法内核", r"算法内核", "算法"),
    ("共享内核", r"共享内核", "通用算法"),
    ("metaheuristic 内核", r"\s?metaheuristic 内核", "核心机制"),
]
COMPILED = [(n, re.compile(p), r) for n, p, r in RULES]

# 不参与改写：写给贡献者的页面源数据（候选发现池里的「正典/闸门」是它的正经术语）
SKIP_FILES = {"data/discovery.json", "data/pulled_cells.json", "data/bench.json"}
# 要处理的文件：数据 + 页面生成器（不含测试/工具/引擎源码）
TARGETS = ["data/algos.json", "data/problems.json", "data/mapping.json", "data/families.json", "data/meta.json",
           "data/matrices.json", "data/apps.json", "data/mo_algos.json", "py/recipe.py", "py/solvers.py", "py/scheduling.py", "py/entryseq.py", "py/components.py", "py/domain_components.py", "build_pages.py", "pages_domains.py", "pages_problems.py", "pages_meta.py"]
TARGETS += ["py/domains_parts/" + _f for _f in sorted(os.listdir(os.path.join(ROOT, "py", "domains_parts"))) if _f.endswith(".py")]


def rewrite(text, hits=None, where=""):
    for name, rx, repl in COMPILED:
        def sub(m, name=name, repl=repl):
            new = m.expand(repl)
            if hits is not None:
                s = max(0, m.start() - 24)
                e = min(len(text), m.end() + 24)
                hits.append((name, where, re.sub(r"\s+", " ", text[s:e]), re.sub(r"\s+", " ", text[s:m.start()] + new + text[m.end():e])))
            return new
        text = rx.sub(sub, text)
    return text


def _py_string_spans(src):
    """返回 .py 源码里所有字符串字面量内容的 (起, 止) 偏移（注释与代码不在其中）。"""
    lines = src.splitlines(keepends=True)
    offs = [0]
    for ln in lines:
        offs.append(offs[-1] + len(ln))
    spans = []
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type in (tokenize.STRING, getattr(tokenize, "FSTRING_MIDDLE", -1)):
            a = offs[tok.start[0] - 1] + tok.start[1]
            b = offs[tok.end[0] - 1] + tok.end[1]
            spans.append((a, b))
    return spans


def rewrite_py(src, hits=None, where=""):
    out, last = [], 0
    for a, b in _py_string_spans(src):
        out.append(src[last:a])
        out.append(rewrite(src[a:b], hits, where))
        last = b
    out.append(src[last:])
    return "".join(out)


def process(apply=False):
    all_hits, changed = [], {}
    for rel in TARGETS:
        if rel in SKIP_FILES:
            continue
        p = os.path.join(ROOT, rel)
        with io.open(p, encoding="utf-8", newline="") as f:
            old = f.read()
        hits = []
        new = rewrite_py(old, hits, rel) if rel.endswith(".py") else rewrite(old, hits, rel)
        all_hits += hits
        if new != old:
            changed[rel] = (old, new)
            if apply:
                with io.open(p + ".tmp", "w", encoding="utf-8", newline="") as f:
                    f.write(new)
                os.replace(p + ".tmp", p)
    return all_hits, changed


# ---------------------------------------------------------------- 体检（扫描公开页面可见文本）
SCAN_PATTERNS = [
    ("内部调研引用", r"(?:综述|报告)\s*§|blueprint|\bR\d{1,3} 正典|综述\s*R\d+|(?<![A-Za-z0-9])R\d{2,3}(?![A-Za-z0-9])|锚点[：:]\s*(?:§|报告|隐喻批评)"),
    ("内部收录分档", r"[ABC] 档|三档收编"),
    ("内部版本标记", r"\bP\d\.\d[abc]?\b|\bH\d (?:kpvar|gcvar|bpvar)"),
    ("开发者黑话", r"防假跑|正典"),
]
# 写给贡献者的页面：允许出现开发者术语
CONTRIBUTOR_PAGES = ("coverage", "components", "discovery")


def scan_public_pages():
    import glob
    import html
    found = []
    for p in glob.glob(os.path.join(ROOT, "**", "index.html"), recursive=True):
        rel = os.path.relpath(p, ROOT).replace("\\", "/")
        if rel.split("/")[0] in ("vendor", ".pydeps") or rel.split("/")[0] in CONTRIBUTOR_PAGES:
            continue
        t = io.open(p, encoding="utf-8").read()
        t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
        for name, pat in SCAN_PATTERNS:
            for m in re.finditer(pat, text):
                found.append((name, rel, text[max(0, m.start() - 25): m.end() + 35]))
    return found


def main(argv):
    if "--scan" in argv:
        found = scan_public_pages()
        by = {}
        for name, rel, ctx in found:
            by.setdefault(name, []).append((rel, ctx))
        for name, items in by.items():
            print(f"{name}: {len(items)} 处，{len({r for r, _ in items})} 页")
            for rel, ctx in items[:4]:
                print(f"   [{rel}] …{ctx}…")
        return 1 if found else 0
    hits, changed = process(apply="--apply" in argv)
    by = {}
    for h in hits:
        by.setdefault(h[0], []).append(h)
    print(f"{'已写回' if '--apply' in argv else '干跑（未写盘）'}：{len(changed)} 个文件，{len(hits)} 处改动")
    for rel, (old, new) in changed.items():
        print(f"  {rel}")
    print()
    for name, rule_hits in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(f"· {name}: {len(rule_hits)} 处（{len({h[1] for h in rule_hits})} 个文件）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

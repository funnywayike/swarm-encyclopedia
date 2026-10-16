# -*- coding: utf-8 -*-
"""由 data/families.json + data/algos.json 生成 py/taxonomy.py（算法分类的运行时副本）。

为什么要有这个文件：算法下拉框的分组标签（TSP 页、各问题域页）和站点的「家族」必须是同一套分类。
分类的唯一来源是 data/algos.json 里每个算法的 family 字段与 data/families.json 里的家族定义；
本脚本把它们压成一个纯 Python 小模块，随引擎一起内嵌进浏览器（Pyodide 里读不到 data/*.json）。

build_pages.py 每次构建最先调用本脚本；tests/test_taxonomy.py 核对 py/taxonomy.py 与数据一致。
"""
import io
import json
import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "py", "taxonomy.py")


def render():
    with io.open(os.path.join(ROOT, "data", "families.json"), encoding="utf-8") as f:
        fams = json.load(f)
    with io.open(os.path.join(ROOT, "data", "algos.json"), encoding="utf-8") as f:
        algos = json.load(f)
    short = {fam["id"]: fam["short"] for fam in fams}
    cat = {a["key"]: short[a["family"]] for a in algos}
    lines = [
        "# -*- coding: utf-8 -*-",
        '"""算法分类的运行时副本——AUTO-GENERATED，请勿手改。',
        "来源：data/families.json（家族 short 标签）+ data/algos.json（每个算法的 family）；",
        "生成：python tools/gen_taxonomy.py（build_pages.py 每次构建自动执行）。",
        "",
        "算法下拉框的分组标签一律经 category_of() 得出，TSP 页与各问题域页因此永远与站点家族一致。",
        '"""',
        "",
        "FAMILY_SHORT = " + json.dumps(short, ensure_ascii=False, indent=4, sort_keys=False),
        "",
        "ALGO_CATEGORY = " + json.dumps(cat, ensure_ascii=False, indent=4, sort_keys=True),
        "",
        "",
        "# 分组标签 → 展示顺序（= families.json 里的家族顺序）；不在家族体系里的标签排在最前（基线/构造件）",
        "CATEGORY_RANK = " + json.dumps({fam["short"]: i for i, fam in enumerate(fams)}, ensure_ascii=False),
        "",
        "",
        "def category_rank(category):",
        "    return CATEGORY_RANK.get(category, -1)",
        "",
        "",
        "# 域内核的后缀与 algos.json 里的算法键不一致的少数几个",
        '_KERNEL_ALIAS = {"cmaes": "cma-es"}',
        "",
        "",
        "def category_of(key, default=None):",
        '    """算法键 → 分组标签。问题域里的变种内核（bv_pso / pk_sma / as_eo）取其基础算法的分类；',
        '    不在家族体系里的（random/hc/贪心基线等）返回 default。"""',
        '    base = key.split("_", 1)[1] if key[:3] in ("bv_", "pk_", "as_") else key',
        "    base = _KERNEL_ALIAS.get(base, base)",
        "    return ALGO_CATEGORY.get(base, default)",
        "",
    ]
    return "\n".join(lines)


def main():
    text = render()
    old = io.open(OUT, encoding="utf-8", newline="").read() if os.path.exists(OUT) else None
    if old != text:
        with io.open(OUT, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        return True
    return False


if __name__ == "__main__":
    print("py/taxonomy.py", "已更新" if main() else "无变化")

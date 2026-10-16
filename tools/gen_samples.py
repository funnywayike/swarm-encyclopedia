# -*- coding: utf-8 -*-
"""生成 samples/ 下的示例数据与 docs/data-formats-variants.md 的变体清单。

示例 = 引擎内置生成器的小实例，经 validate 规整后以 swarm-problem/v1 信封保存，
因此「示例永远是校验器认可的格式」。重新生成：python tools/gen_samples.py
"""
import json
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "py"))
import domains as D  # noqa: E402
import registry  # noqa: E402
import validate as V  # noqa: E402

SMALL = {"knapsack": {"n": 12}, "binpack": {"n": 12}, "graphcolor": {"n": 12}, "multiobj": {"n": 12},
         "kpvar": {"n": 12}, "gcvar": {"n": 12}, "bpvar": {"n": 12}, "qubo": {"n": 8}, "sat": {"n_vars": 10},
         "setcover": {"n_el": 20, "m": 12}, "gap": {"n_a": 3, "n_j": 8}, "uflp": {"n_f": 5, "n_c": 12},
         "continuous": {"fn": "rastrigin", "dim": 5}, "custom": {"n": 12}, "mocont": {"n": 10}}
from registry import PLAIN, VARIANTS  # noqa: E402  清单来自登记表
OUT = os.path.join(ROOT, "samples")


def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")


def make(domain, variant=None):
    opts = dict(SMALL.get(domain, {}))
    if variant:
        opts["variant"] = variant
    pre = json.loads(D.domain_preset(domain, 7, opts))
    res = V.validate(domain, pre, variant=variant, dry_run=True)
    assert res["ok"], (domain, variant, res["errors"])
    return res["problem"]


def shape(x):
    if isinstance(x, dict):
        return "对象"
    if isinstance(x, list):
        if not x:
            return "列表"
        return f"{len(x)}×{shape(x[0])}"
    if isinstance(x, bool):
        return "布尔"
    if isinstance(x, int):
        return "整数"
    if isinstance(x, float):
        return "数"
    return "文本"


def main():
    n_files = 0
    for dom in PLAIN:
        prob = make(dom)
        dump(os.path.join(OUT, dom, f"{dom}.json"), V.to_envelope(dom, prob))
        n_files += 1
    for dom, vs in VARIANTS.items():
        for v in vs:
            prob = make(dom, v)
            dump(os.path.join(OUT, dom, f"{v}.json"), V.to_envelope(dom, prob, variant=v))
            n_files += 1

    # 纯文本示例：CSV / DIMACS
    ks = make("knapsack")
    with open(os.path.join(OUT, "knapsack", "knapsack.csv"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# cap={ks['cap']}\nweight,value\n" + "".join(f"{w},{v}\n" for w, v in ks["items"]))
    bp = make("binpack")
    with open(os.path.join(OUT, "binpack", "binpack.csv"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# cap={bp['cap']}\nsize\n" + "".join(f"{s}\n" for s in bp["items"]))
    gc = make("graphcolor")
    with open(os.path.join(OUT, "graphcolor", "graphcolor.csv"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"# n={gc['n']}\nu,v\n" + "".join(f"{u},{v}\n" for u, v in gc["edges"]))
    with open(os.path.join(OUT, "graphcolor", "graphcolor.col"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"c 示例：{gc['n']} 个顶点（DIMACS 顶点编号从 1 开始）\np edge {gc['n']} {len(gc['edges'])}\n"
                + "".join(f"e {u + 1} {v + 1}\n" for u, v in gc["edges"]))
    qb = make("qubo")
    with open(os.path.join(OUT, "qubo", "qubo.csv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(",".join(str(x) for x in row) + "\n" for row in qb["Q"]))
    sat = make("sat")
    with open(os.path.join(OUT, "sat", "sat.cnf"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"c 示例：{sat['n_vars']} 个变量（DIMACS CNF，变量编号从 1 开始，每行以 0 结尾）\n"
                f"p cnf {sat['n_vars']} {len(sat['clauses'])}\n" + "".join(" ".join(map(str, c)) + " 0\n" for c in sat["clauses"]))
    n_files += 6

    # 变体清单附录（字段名 + 形状，自动生成，避免和代码漂移）
    lines = ["# 变体字段清单（自动生成）", "",
             "> 由 `tools/gen_samples.py` 从引擎内置实例生成；每个变体对应的示例文件在 `samples/<域>/<变体>.json`。",
             "> 字段的业务含义见该变体的问题页（站点 `problem/<变体>/`）。`n` 可省略时标注为「可省略」。", ""]
    for dom, vs in VARIANTS.items():
        lines += [f"## {dom}", "", "| 变体 | 保真度 | 字段（形状） |", "|---|---|---|"]
        for v in vs:
            raw = json.loads(D.domain_preset(dom, 7, dict(SMALL.get(dom, {}), variant=v)))
            parts = []
            for k, val in raw.items():
                if k == "variant":
                    continue
                tag = f"`{k}`: {shape(val)}"
                if k == "n" and dom == "entryseq" and V._derive_n(raw, {kk: vv for kk, vv in raw.items() if kk != "n"}) is not None:
                    tag += "（可省略）"
                parts.append(tag)
            f = registry.fidelity(dom, v)
            fid = registry.FIDELITY_LABEL[f["level"]] + (f"：{f['note']}" if f["note"] else "")
            lines.append(f"| `{v}` | {fid} | {'；'.join(parts) or '（仅规模 n）'} |")
        lines.append("")
    with open(os.path.join(ROOT, "docs", "data-formats-variants.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    print(f"生成 {n_files} 个示例文件 + docs/data-formats-variants.md")


if __name__ == "__main__":
    main()

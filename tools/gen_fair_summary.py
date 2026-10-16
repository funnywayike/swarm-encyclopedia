# -*- coding: utf-8 -*-
"""把同等评估预算基准（tests/golden/fair_budget_200.json）汇总成页面用的 data/fair_budget_summary.json。

页面据此显示：覆盖矩阵页的「同预算实测汇总」表、每个问题页的「同预算实测：N 个算法里 M 个明显胜过随机搜索」一行。
数字全部从基准结果派生；换了基准结果重跑本脚本即可。

    python tools/gen_fair_summary.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "py"))

import gen_mapping_rows as G  # noqa: E402


def _count(cells):
    c = {"win": 0, "tie": 0, "loss": 0}
    for v in cells:
        if v and v.get("verdict") in c:
            c[v["verdict"]] += 1
    c["cells"] = c["win"] + c["tie"] + c["loss"]
    return c


def main():
    ledger = G._load("tests/golden/fair_budget_200.json")
    meta = ledger.pop("_meta")
    problems = G._load("data/problems.json")
    wpath = os.path.join(ROOT, "data", "withdrawn_cells.json")
    withdrawn = set(G._load("data/withdrawn_cells.json")["cells"]) if os.path.exists(wpath) else set()
    by_problem = {}
    for pid, (name, url) in sorted(G.page_index(problems).items()):
        cfg = G._demo_cfg(pid)
        if cfg is None:
            continue
        dom, var = G._case_of(cfg)
        prefix = f"{dom}/{var or '-'}/"
        cells = [v for k, v in ledger.items() if k.startswith(prefix)]
        c = _count(cells)
        c["withdrawn"] = sum(1 for k in withdrawn if k.startswith(prefix))
        c["domain"], c["variant"] = dom, var
        if c["cells"]:
            by_problem[pid] = c
    by_domain = {}
    for k, v in ledger.items():
        dom = k.split("/")[0]
        by_domain.setdefault(dom, []).append(v)
    by_domain = {d: _count(v) for d, v in sorted(by_domain.items())}
    for d in by_domain:
        by_domain[d]["withdrawn"] = sum(1 for k in withdrawn if k.startswith(d + "/"))
    out = {"meta": {"iters": meta["iters"], "seeds": meta["seeds"], "margin": meta["margin"],
                    "confirmed": meta.get("confirmed")},
           "total": _count(ledger.values()), "by_domain": by_domain, "by_problem": by_problem}
    out["total"]["withdrawn"] = len(withdrawn)
    with open(os.path.join(ROOT, "data", "fair_budget_summary.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    t = out["total"]
    print(f"总 {t['cells']} 格：胜 {t['win']} / 平 {t['tie']} / 负 {t['loss']}（已撤下 {t['withdrawn']}）；"
          f"{len(by_domain)} 个域，{len(by_problem)} 个问题页")


if __name__ == "__main__":
    main()

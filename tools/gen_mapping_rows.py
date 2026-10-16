# -*- coding: utf-8 -*-
"""由「同等评估预算」基准结果生成问题页的 algo_solves 映射行（data/mapping.json）。

规则：
  - 只收 verdict == "win" 的格子（同等评估次数下平均成绩明显优于随机搜索），且不在撤下账本里；
  - 每个问题页最多 MAX_ROWS 行，按相对改进从大到小；
  - 一个算法在同一问题里有多种编码实现（原名 / pk_ 排列 / bv_ 位向量 / as_ 指派）时，取改进最大的那一个；
  - 只给「还没有映射行」的问题页生成（已有的手写行不覆盖）；--check 只核对已有实测行与基准账本是否矛盾。

用法：
    python tools/gen_mapping_rows.py --check          # 核对已有实测行（不写文件）
    python tools/gen_mapping_rows.py                  # 预览将要新增的行数
    python tools/gen_mapping_rows.py --write          # 写入 data/mapping.json
"""
import argparse
import json
import os
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "py"))

MAX_ROWS = 12
PREFIXES = ("pk_", "bv_", "as_")


def _load(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return json.load(f)


def _fmt(x):
    return f"{x:.4g}"


def _base(key):
    return key[3:] if key[:3] in PREFIXES else key


# 没有 ABSTRACT_DEMO 配置的枢纽页：问题 id → (域, 变体)
HUBS = {"knapsack": ("knapsack", None), "continuous": ("continuous", None), "graphcolor": ("graphcolor", None),
        "binpack": ("binpack", None), "multiobj": ("multiobj", None)}


def _demo_cfg(pid):
    if pid in HUBS:
        dom, var = HUBS[pid]
        return {"page_domain": dom, "preset_options": {"-": ({"variant": var} if var else {})}}
    import pages_domains as pd
    for table in (pd.ABSTRACT_DEMO, pd.CLASS_DEMO, pd.VARIANT_DEMO):
        if pid in table:
            return table[pid]
    return None


def _case_of(cfg):
    """页面第一个预设对应的 (域, 变体)；变体为空时是 None。"""
    opts = next(iter(cfg["preset_options"].values()))
    return cfg["page_domain"], opts.get("variant")


def page_index(problems):
    """所有有独立页面的问题：{id: (名称, url)}。"""
    out = {}
    for t in problems["abstract_types"]:
        if t.get("status") == "page":
            out[t["id"]] = (t["name"], f"/problem/{t['dir']}/")
    for c in problems["class_pages"]:
        out[c["id"]] = (c["name"], f"/problem/{c['dir']}/")
    for v in problems["knapsack_variants"]:
        out[v["id"]] = (v.get("name") or v["id"], f"/problem/knapsack/{v['id']}/")
    return out


def prune_contradicted(mapping, ledger):
    """删掉与基准账本矛盾的已有实测行（同预算下只是平手或更差）：返回被删的行。账本里没有的格子不动。"""
    bad = {id(r) for r, why in check_existing(mapping, ledger) if "账本里没有" not in why or "已不提供" in why}
    dropped = [r for r in mapping["algo_solves"] if id(r) in bad]
    mapping["algo_solves"] = [r for r in mapping["algo_solves"] if id(r) not in bad]
    return dropped


def build(ledger, meta, withdrawn, prune=False):
    import domains as D
    problems = _load("data/problems.json")
    mapping = _load("data/mapping.json")
    dropped = prune_contradicted(mapping, ledger) if prune else []
    algo_keys = {a["key"] for a in _load("data/algos.json")}
    have = {r["problem"] for r in mapping["algo_solves"]}
    pages = page_index(problems)
    for pid in HUBS:   # 枢纽页（背包 / 连续 / 多目标 / 图着色 / 装箱）：名称与地址取自已有的问题索引
        if pid in mapping["problem_index"]:
            pages[pid] = (mapping["problem_index"][pid]["name"], mapping["problem_index"][pid]["url"])
    new_rows, new_index, skipped = [], {}, []
    for pid, (name, url) in sorted(pages.items()):
        if pid in have:
            continue
        cfg = _demo_cfg(pid)
        if cfg is None:
            skipped.append((pid, "没有在线演示配置"))
            continue
        dom, var = _case_of(cfg)
        opts = {"variant": var} if var else {}
        names = {a["key"]: a["name"] for a in json.loads(D.domain_list(dom, opts))["algos"]}
        best = {}  # algos.json 键 -> (相对改进, 域内键, 格子)
        for k in names:
            c = ledger.get(f"{dom}/{var or '-'}/{k}")
            if not c or c.get("verdict") != "win" or f"{dom}/{var or '-'}/{k}" in withdrawn:
                continue
            b = _base(k)
            if b not in algo_keys:
                continue
            rnd = c["random"]
            rel = abs(rnd - c["algo"]) / max(abs(rnd), 1e-9)
            if b not in best or rel > best[b][0]:
                best[b] = (rel, k, c)
        if not best:
            has_cells = any(k.startswith(f"{dom}/{var or '-'}/") for k in ledger)
            skipped.append((pid, "没有任何算法在同等预算下稳定胜过随机搜索（多半是实例太小，随机搜索也能找到最优）"
                            if has_cells else "基准没有覆盖这个域（评价指标不是单一标量）"))
            continue
        top = sorted(best.items(), key=lambda kv: -kv[1][0])[:MAX_ROWS]
        for b, (rel, k, c) in top:
            sense = "越小越好" if c["sense"] == "min" else "越大越好"
            new_rows.append({
                "algo": b, "problem": pid,
                "how": names[k],
                "evidence": (f"同等评估预算实测（每次约 {c['evals']} 次评估，{len(meta['seeds'])} 个种子的中位数）："
                             f"本算法 {_fmt(c['algo'])}，随机搜索 {_fmt(c['random'])}（{sense}）"),
                "demo": url, "demo_algo": k, "tier": "实测",
            })
        new_index[pid] = {"name": name, "url": url}
    return mapping, new_rows, new_index, skipped, dropped


def check_existing(mapping, ledger):
    """已有实测行 ↔ 基准账本：返回 [(行, 原因)]。"""
    import domains as D
    problems = _load("data/problems.json")
    bad = []
    for r in mapping["algo_solves"]:
        if r["tier"] != "实测" or r["problem"] == "tsp":
            continue
        cfg = _demo_cfg(r["problem"])
        if cfg is None:
            continue
        dom, var = _case_of(cfg)
        k = r.get("demo_algo") or r["algo"]
        c = ledger.get(f"{dom}/{var or '-'}/{k}")
        if c is None:
            opts = {"variant": var} if var else {}
            avail = {a["key"] for a in json.loads(D.domain_list(dom, opts))["algos"]}
            bad.append((r, f"账本里没有 {dom}/{var or '-'}/{k}" + ("" if k in avail else "，且该域已不提供这个算法")))
        elif c.get("verdict") != "win":
            bad.append((r, f"{dom}/{var or '-'}/{k} 的同预算判定是 {c.get('verdict')}"))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default="tests/golden/fair_budget_200.json")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    ledger = _load(a.ledger)
    meta = ledger.pop("_meta")
    wpath = os.path.join(ROOT, "data", "withdrawn_cells.json")
    withdrawn = set()
    if os.path.exists(wpath):
        w = json.load(open(wpath, encoding="utf-8"))
        withdrawn = set(w["cells"])
    mapping, rows, index, skipped, dropped = build(ledger, meta, withdrawn, prune=a.write)
    if dropped:
        print(f"删除与账本矛盾的已有实测行 {len(dropped)} 条：" + "、".join(f"{r['algo']}→{r['problem']}" for r in dropped))
    if a.check:
        bad = check_existing(mapping, ledger)
        for r, why in bad:
            print(f"  ✗ {r['algo']}→{r['problem']}（demo_algo={r.get('demo_algo')}）：{why}")
        print(f"已有实测行与账本矛盾 {len(bad)} 条")
        return
    print(f"将新增 {len(rows)} 行，覆盖 {len(index)} 个问题页；跳过 {len(skipped)} 个：")
    for pid, why in skipped:
        print(f"  - {pid}：{why}")
    if a.write:
        mapping["algo_solves"].extend(rows)
        mapping["problem_index"].update(index)
        with open(os.path.join(ROOT, "data", "mapping.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print("已写入 data/mapping.json")


if __name__ == "__main__":
    main()

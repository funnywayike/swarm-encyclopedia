# -*- coding: utf-8 -*-
"""等评价次数的公平比较：每个「域 × 变体 × 算法」格子，先量出算法自己用了多少次目标函数评价，
再给随机搜索基线**同样多**的评价次数，多个种子取中位数比较。

为什么需要它：各算法每「代」用的评价次数差很多（模拟退火每代 1 次，种群算法每代 ≈ 种群大小，局部搜索一代几十次），
而随机基线在不同编码上每代的评价次数也不一样——按「代」比较（黄金快照、旧的「优于随机」门）并不公平：
排列 / 位向量问题上随机基线每代 1 次，中位算法约 30 倍；实数向量问题上却是对等的。

    python tools/fair_budget.py                         全部格子（几十分钟），结果写 tests/golden/fair_budget.json
    python tools/fair_budget.py --domains knapsack,qubo 只跑这些域
    python tools/fair_budget.py --iters 100 --seeds 5   更长、更多种子
    python tools/fair_budget.py --report                只读已有结果，打印汇总
    python tools/fair_budget.py --algos hho,ssa --merge 只跑这些算法（含 bv_ / pk_ / as_ 变种）并并入已有结果文件
    python tools/fair_budget.py --confirm 9             把「loss」的格子用 9 个种子重测，只保留仍然输的
    python tools/fair_budget.py --write-ledger          由结果生成撤下账本：py/domains_parts/88_withdrawn_cells.py + data/withdrawn_cells.json

判定（每个格子，种子中位数）：算法 ≥ 随机基线 by margin 之外 = win；差距在 margin 内 = tie；更差 = loss。
评价次数的计法：给上下文对象上的目标函数方法（obj / eval / value / decode / cost / unsat / energy / f）套一层计数器，
只数「最外层」调用，所以 value → obj → cost 这样的嵌套只算一次。
多目标域（multiobj / mocont）按非支配解 / IGD 另行评价，不在这里。
"""
import argparse
import json
import os
import statistics
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "py"))

import domains as D  # noqa: E402
import registry  # noqa: E402
D._WITHDRAWN.clear()  # 测量时不受既有撤下账本影响（否则撤下过的格子永远没有机会翻案）

OUT = os.path.join(ROOT, "tests", "golden", "fair_budget.json")
EVAL_METHODS = ("obj", "eval", "value", "decode", "cost", "unsat", "energy", "f")
SKIP_DOMAINS = {"multiobj", "mocont"}
ANCHORS = {"random", "greedy", "dpll", "walksat", "cmp_dp", "ssp_dp"}  # 基线 / 构造 / 精确锚点：不参与「胜过随机」的判定


class Counter:
    def __init__(self):
        self.n = 0
        self.depth = 0


def instrument(ctx, counter):
    """给上下文实例上的目标函数方法套计数器（只数最外层调用）。"""
    for name in EVAL_METHODS:
        fn = getattr(ctx, name, None)
        if not callable(fn):
            continue

        def make(fn):
            def wrapped(*a, **k):
                if counter.depth == 0:
                    counter.n += 1
                counter.depth += 1
                try:
                    return fn(*a, **k)
                finally:
                    counter.depth -= 1
            return wrapped
        try:
            setattr(ctx, name, make(fn))
        except Exception:  # noqa: BLE001
            pass


def run(dom, var, algo, iters, seed, budget=None):
    """跑一次，返回 (最终 best, 评价次数, 方向)。budget 给定时，评价次数一到就停（用于随机基线）。"""
    opts = {"variant": var} if var else {}
    pre = D.domain_preset(dom, seed, opts)
    info = json.loads(D.domain_start(dom, pre, algo, json.dumps({"max_iter": iters, "seed": seed})))
    sense = info.get("sense", "min")
    sense = "max" if str(sense).startswith("max") else "min"
    ctr = Counter()
    instrument(D._RUN["ctx"], ctr)
    best = None
    while True:
        s = D.domain_step()
        if s is None:
            break
        st = json.loads(s)
        best = st.get("best", best)
        if budget is not None and ctr.n >= budget:
            break
    return best, ctr.n, sense


def cell(dom, var, algo, iters, seeds, margin):
    algo_vals, rand_vals, evals = [], [], []
    sense = "min"
    for seed in seeds:
        v, n, sense = run(dom, var, algo, iters, seed)
        algo_vals.append(v)
        evals.append(n)
        rv, _n, _s = run(dom, var, "random", 100000, seed, budget=n)
        rand_vals.append(rv)
    if None in algo_vals or None in rand_vals:
        return None
    a, r = statistics.median(algo_vals), statistics.median(rand_vals)
    scale = max(abs(r), abs(a), 1e-9)
    gain = (r - a) / scale if sense == "min" else (a - r) / scale  # 正 = 算法更好
    verdict = "win" if gain > margin else ("tie" if gain >= -margin else "loss")
    return {"verdict": verdict, "gain": round(gain, 4), "algo": round(a, 6), "random": round(r, 6),
            "evals": int(statistics.median(evals)), "sense": sense}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=30)
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--margin", type=float, default=0.002, help="相对差距在这个范围内算平局")
    ap.add_argument("--domains", default="")
    ap.add_argument("--variants", default="", help="只跑这些变体（如 cflp,fss）")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--algos", default="", help="只跑这些算法（基础名，含 bv_ / pk_ / as_ 变种）")
    ap.add_argument("--merge", action="store_true", help="并入已有结果文件，而不是覆盖")
    ap.add_argument("--confirm", type=int, default=0, help="把 loss 的格子用这么多个种子重测")
    ap.add_argument("--write-ledger", action="store_true")
    a = ap.parse_args()
    if a.report:
        res = json.load(open(a.out, encoding="utf-8"))
        report(res)
        return
    if a.confirm or a.write_ledger:
        res = json.load(open(a.out, encoding="utf-8"))
        meta = res.get("_meta", {})
        if a.confirm:
            confirm(res, meta, a.confirm, a.margin, a.out)
        if a.write_ledger:
            write_ledger(json.load(open(a.out, encoding="utf-8")))
        return
    only = set(filter(None, a.algos.split(",")))
    want = set(filter(None, a.domains.split(",")))
    want_var = set(filter(None, a.variants.split(",")))
    seeds = list(range(11, 11 + a.seeds))
    res, t0, n = {}, time.time(), 0
    if a.merge and os.path.exists(a.out):
        res = json.load(open(a.out, encoding="utf-8"))
    for dom, var in registry.cases(include_scheduling=True):
        if dom in SKIP_DOMAINS or dom == "custom" or (want and dom not in want):
            continue
        if want_var and var not in want_var:
            continue
        opts = {"variant": var} if var else {}
        for al in json.loads(D.domain_list(dom, opts))["algos"]:
            k = al["key"]
            if k in ANCHORS:
                continue
            if only and (k[3:] if k[:3] in ("bv_", "pk_", "as_") else k) not in only:
                continue
            key = f"{dom}/{var or '-'}/{k}"
            try:
                res[key] = cell(dom, var, k, a.iters, seeds, a.margin)
            except Exception as e:  # noqa: BLE001
                res[key] = {"verdict": "error", "error": f"{type(e).__name__}: {str(e)[:80]}"}
            n += 1
            if n % 100 == 0:
                print(f"  … {n} 格，{time.time() - t0:.0f}s", flush=True)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    res.pop("_meta", None)
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"_meta": {"iters": a.iters, "seeds": seeds, "margin": a.margin}, **res}, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        f.write("\n")
    print(f"{n} 格，用时 {time.time() - t0:.0f}s，写入 {a.out}")
    report(res)


def confirm(res, meta, n_seeds, margin, out):
    """把 loss 的格子用更多种子重测：3 个种子的中位数在边缘上会误判，9 个种子才算数。"""
    iters = meta.get("iters", 200)
    seeds = list(range(101, 101 + n_seeds))
    todo = [k for k, v in res.items() if not k.startswith("_") and v and v.get("verdict") == "loss"]
    print(f"重测 {len(todo)} 个 loss 格（{n_seeds} 个种子）…", flush=True)
    changed = 0
    for i, key in enumerate(todo, 1):
        dom, var, algo = key.split("/")
        r = cell(dom, None if var == "-" else var, algo, iters, seeds, margin)
        if r:
            r["confirmed"] = n_seeds
            if r["verdict"] != "loss":
                changed += 1
            res[key] = r
        if i % 50 == 0:
            print(f"  … {i}/{len(todo)}", flush=True)
    meta = dict(meta, confirmed=n_seeds)
    res["_meta"] = meta
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        f.write("\n")
    print(f"重测完成：{changed} 个格子翻案（不再是 loss），{len(todo) - changed} 个维持 loss")


LEDGER_PART = os.path.join(ROOT, "py", "domains_parts", "88_withdrawn_cells.py")
LEDGER_JSON = os.path.join(ROOT, "data", "withdrawn_cells.json")


def write_ledger(res):
    """loss 且已用多种子确认的格子 → 撤下账本。引擎据此不再列出这些「域 × 变体 × 算法」。"""
    meta = res.get("_meta", {})
    cells = {k: v for k, v in res.items() if not k.startswith("_") and v and v.get("verdict") == "loss" and v.get("confirmed")}
    by_unit = {}
    for key in sorted(cells):
        dom, var, algo = key.split("/")
        by_unit.setdefault((dom, var), []).append(algo)
    lines = ["# 撤下账本——AUTO-GENERATED，请勿手改：python tools/fair_budget.py --write-ledger",
             f"# 判定：等评价次数（算法自己用了多少次评价，随机搜索基线就给多少次）、{meta.get('iters')} 代、{meta.get('confirmed')} 个种子取中位数，",
             "# 算法仍比随机搜索差（相对差距超过边际）的「域 × 变体 × 算法」格子。证据见 data/withdrawn_cells.json。",
             "_WITHDRAWN = {"]
    for (dom, var), algos in sorted(by_unit.items()):
        lines.append(f'    ("{dom}", "{var}"): frozenset({sorted(algos)!r}),')
    lines += ["}", "", "",
              "def _is_withdrawn(domain, variant, algo):",
              '    """该格子是否因「等评价次数下赢不了随机搜索」被撤下。"""',
              '    return algo in _WITHDRAWN.get((domain, variant or "-"), ())', ""]
    with open(LEDGER_PART, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
    out = {"_readme": "等评价次数门撤下的格子（由 tools/fair_budget.py --write-ledger 生成）。字段：algo=算法 key，evals=算法自己用的评价次数（中位数），"
                      "gain=相对随机搜索的优势（负 = 更差），algo_best / random_best = 两者的最终最优值（中位数），seeds=种子数。",
           "meta": meta, "cells": {k: {f: v[f] for f in ("evals", "gain", "algo", "random", "sense")} for k, v in sorted(cells.items())}}
    with open(LEDGER_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"撤下账本：{len(cells)} 个格子，{len(by_unit)} 个单元 → {os.path.relpath(LEDGER_PART, ROOT)}、{os.path.relpath(LEDGER_JSON, ROOT)}")


def report(res):
    import collections
    cells = {k: v for k, v in res.items() if not k.startswith("_") and v}
    c = collections.Counter(v["verdict"] for v in cells.values())
    tot = sum(c.values())
    print("总计", dict(c), "（%d 格）" % tot)
    for v in ("win", "tie", "loss", "error"):
        if c[v]:
            print(f"  {v}: {c[v] / tot:.1%}")
    by_dom = collections.defaultdict(collections.Counter)
    by_algo = collections.defaultdict(collections.Counter)
    for k, v in cells.items():
        dom, var, al = k.split("/")
        by_dom[dom][v["verdict"]] += 1
        by_algo[al][v["verdict"]] += 1
    print("\n按域（loss 占比）：")
    for d, cc in sorted(by_dom.items(), key=lambda t: -t[1]["loss"] / max(1, sum(t[1].values()))):
        print(f"  {d:12s} {dict(cc)}")
    print("\n按算法（loss 最多的 15 个）：")
    for al, cc in sorted(by_algo.items(), key=lambda t: -t[1]["loss"] / max(1, sum(t[1].values())))[:15]:
        print(f"  {al:10s} {dict(cc)}")


if __name__ == "__main__":
    main()

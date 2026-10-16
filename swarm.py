# -*- coding: utf-8 -*-
"""
命令行入口：用你自己的数据直接调用本站的群智能算法。纯标准库，Python 3.8+。

    python swarm.py list                                  列出问题域
    python swarm.py list knapsack                         列出该域可用算法
    python swarm.py template knapsack                     打印该域的示例数据（可重定向保存后改成你的）
    python swarm.py generate knapsack --opt n=200         生成指定规模的随机实例（做算法对比用）
    python swarm.py check  my.json                        只校验数据，不运行
    python swarm.py solve  my.json --algo ga              求解
    python swarm.py compare my.json --algos ga,sa,hc      多个算法同实例对比（--algos all 跑全部）
    python swarm.py replay result.json                    复现一份结果文件（命令行 --out 或网页「结果 JSON」导出的），核对曲线

数据格式见 docs/data-formats.md；.json / .csv / .cnf / .col 都可以。
CSV 等没有「问题域」信息的文件需要加 --domain；带变体的域（entryseq 等）需要 --variant（JSON 外壳里写了就不用）。
"""
import argparse
import csv
import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "py"))

import domains as D  # noqa: E402
import solvers as S  # noqa: E402
import registry  # noqa: E402
import validate as V  # noqa: E402

RESULT_SCHEMA = "swarm-result/v1"
VARIANT_DOMAINS = tuple(registry.VARIANTS)


def out(msg=""):
    print(msg)


def die(msg, code=2):
    print(f"错误：{msg}", file=sys.stderr)
    sys.exit(code)


# ------------------------------------------------------------------ 数据读取

def read_problem(args, dry_run=False):
    """读文件 → 校验 → (domain, variant, 规整后的实例)。出错直接退出。"""
    try:
        with open(args.file, "rb") as f:
            raw = f.read()
    except OSError as e:
        die(f"打不开文件 {args.file}：{e.strerror}")
    domain, data, issues = V.load(raw, domain=args.domain, filename=os.path.basename(args.file))
    if args.domain and domain and domain != args.domain:
        die(f"文件内容属于 '{domain}'，但命令行指定了 --domain {args.domain}")
    show_issues(issues.errors, issues.warnings)
    if data is None or issues.errors:
        die("数据读取失败（见上）")
    variant = args.variant or (data.get("variant") if isinstance(data, dict) else None)
    if getattr(args, "objective_py", None):  # 自带问题的本地 Python 目标函数：只有命令行才开放（浏览器里永远关闭）
        if domain != "custom":
            die("--objective-py 只用于自带问题（--domain custom）")
        try:
            with open(args.objective_py, encoding="utf-8") as f:
                code = f.read()
        except OSError as e:
            die(f"打不开 {args.objective_py}：{e.strerror}")
        import userproblem
        userproblem.enable_python()
        data = dict(data)
        data.pop("objective", None)
        data["objective_python"] = code
    res = V.validate(domain, data, variant=variant, dry_run=dry_run)
    show_issues(res["errors"], res["warnings"])
    if not res["ok"]:
        die("数据校验未通过，已停止（修正上面的问题后重试）")
    return domain, variant or (res["problem"] or {}).get("variant"), res["problem"]


def show_issues(errors, warnings):
    for e in errors:
        print(f"  ✗ {e['path'] or '(整体)'}：{e['msg']}", file=sys.stderr)
    for w in warnings:
        print(f"  ! {w['path'] or '(整体)'}：{w['msg']}", file=sys.stderr)


# ------------------------------------------------------------------ 算法目录

def algo_catalog(domain, variant):
    """{key: (名称, 分类)}，以及默认参数 dict。"""
    if domain == "tsp":
        cat = {k: (c.name, c.category) for k, c in S.SOLVERS.items() if c.implemented}
        defaults = {}
        for k, c in S.SOLVERS.items():
            defaults.update(c.default_params)
        return cat, defaults
    info = json.loads(D.domain_list(domain, {"variant": variant} if variant else {}))
    return {a["key"]: (a["name"], a["category"]) for a in info["algos"]}, info["defaults"]


def parse_params(items, allowed):
    params = {}
    for it in items or []:
        if "=" not in it:
            die(f"--param 应写成 名称=值，收到 {it!r}")
        k, v = it.split("=", 1)
        try:
            params[k] = json.loads(v)
        except ValueError:
            params[k] = v
        if allowed and k not in allowed:
            die(f"未知参数 {k!r}。该域可用参数：{', '.join(sorted(allowed))}")
    return params


# ------------------------------------------------------------------ 运行

def run_once(domain, variant, problem, algo, iters, seed, params):
    """跑完一次，返回 dict：best / sense / curve / solution / elapsed。"""
    t0 = time.time()
    curve, last, sense, solution = [], None, "min", None
    if domain == "tsp":
        if algo not in S.SOLVERS or not S.SOLVERS[algo].implemented:
            die(f"TSP 没有算法 {algo!r}。运行 `python swarm.py list tsp` 查看可用算法")
        p = dict(params, max_iter=iters, seed=seed)
        prob = S.problem_from_spec(problem)
        for st in S.SOLVERS[algo]().solve(prob, p):
            curve.append([st.iteration, round(st.best_cost, 4)])
            last = st
        best, solution = round(last.best_cost, 4), list(last.best_tour)
    else:
        p = dict(params, max_iter=iters, seed=seed)
        try:
            info = json.loads(D.domain_start(domain, json.dumps(problem), algo, json.dumps(p)))
        except ValueError as e:
            die(f"{e}。运行 `python swarm.py list {domain}` 查看可用算法")
        sense = info.get("sense", "min")
        while True:
            s = D.domain_step()
            if s is None:
                break
            last = json.loads(s)
            key = "best" if "best" in last else "nd"
            curve.append([last.get("iter"), last.get(key)])
        key = "best" if "best" in last else "nd"
        best = last.get(key)
        solution = last.get("best_sol")
        if key == "nd":
            sense = "max"  # 多目标：非支配解个数越多越好（前沿覆盖）
    return {"best": best, "sense": sense, "curve": curve, "solution": solution,
            "elapsed_s": round(time.time() - t0, 3), "last": last if domain != "tsp" else None}


# ------------------------------------------------------------------ 子命令

def cmd_list(args):
    if not args.domain:
        out("问题域（python swarm.py list <域> 查看算法）：")
        out(f"  {'tsp':<11} 旅行商（{sum(1 for c in S.SOLVERS.values() if c.implemented)} 个算法）")
        for dom in V.CORE_DOMAINS:
            if dom == "tsp":
                continue
            opts = {"variant": "ssp"} if dom == "kpvar" else {}
            n = len(json.loads(D.domain_list(dom, opts))["algos"])
            note = "  [需要变体 --variant]" if dom in VARIANT_DOMAINS else ""
            out(f"  {dom:<11} {n} 个算法{note}")
        return
    if args.domain not in V.CORE_DOMAINS:
        die(f"未知问题域 {args.domain!r}。可选：{', '.join(V.CORE_DOMAINS)}")
    variant = args.variant or (registry.DEFAULT_VARIANT.get(args.domain))
    cat, defaults = algo_catalog(args.domain, variant)
    out(f"{args.domain}" + (f"（变体 {variant}）" if variant else "") + f"：{len(cat)} 个算法")
    last_cat = None
    for k, (name, c) in sorted(cat.items(), key=lambda kv: (kv[1][1], kv[0])):
        if c != last_cat:
            out(f"\n  [{c}]")
            last_cat = c
        out(f"    {k:<12} {name}")
    if defaults:
        out("\n默认参数（可用 --param 名称=值 覆盖）：" + ", ".join(f"{k}={v}" for k, v in defaults.items()))
    if args.domain in VARIANT_DOMAINS and not args.variant:
        out("\n该域有多个变体，不同变体的可用算法略有差异：加 --variant <名称> 查看。")


def cmd_template(args):
    d = args.domain
    if d not in V.CORE_DOMAINS:
        die(f"未知问题域 {d!r}。可选：{', '.join(V.CORE_DOMAINS)}")
    if d == "tsp":
        path = os.path.join(ROOT, "samples", "cities_sample.json")
    else:
        name = args.variant or registry.DEFAULT_VARIANT.get(d, d)
        path = os.path.join(ROOT, "samples", d, f"{name}.json")
    if not os.path.exists(path):
        die(f"没有找到示例文件 {os.path.relpath(path, ROOT)}（该域的变体清单见 docs/data-formats-variants.md）")
    with open(path, encoding="utf-8") as f:
        sys.stdout.write(f.read())


def cmd_generate(args):
    """生成指定规模的随机实例（示例文件只有十来个物品，各算法分不出高下；做对比请用这个造大一点的）。"""
    d = args.domain
    if d not in V.CORE_DOMAINS:
        die(f"未知问题域 {d!r}。可选：{', '.join(V.CORE_DOMAINS)}")
    opts = {}
    for it in args.opt or []:
        if "=" not in it:
            die(f"--opt 应写成 名称=值，收到 {it!r}")
        k, v = it.split("=", 1)
        try:
            opts[k] = json.loads(v)
        except ValueError:
            opts[k] = v
    if args.variant:
        opts["variant"] = args.variant
    elif d in VARIANT_DOMAINS:
        opts["variant"] = registry.DEFAULT_VARIANT[d]
    if d == "tsp":
        import random
        n = int(opts.get("n", 50))
        rng = random.Random(args.seed)
        prob = {"cities": [[round(rng.uniform(0, 100), 2), round(rng.uniform(0, 100), 2)] for _ in range(n)]}
    else:
        try:
            prob = json.loads(D.domain_preset(d, args.seed, opts))
        except (TypeError, ValueError, KeyError) as e:
            die(f"生成失败：{type(e).__name__}: {e}。规模参数名因域而异（如 n / n_el,m / n_a,n_j / n_f,n_c / fn,dim），见 docs/data-formats.md")
    res = V.validate(d, prob, variant=opts.get("variant"))
    if not res["ok"]:
        show_issues(res["errors"], res["warnings"])
        die("生成的实例未通过校验（这是程序问题，请反馈）")
    print(json.dumps(V.to_envelope(d, res["problem"], variant=opts.get("variant")), ensure_ascii=False))


def cmd_check(args):
    domain, variant, problem = read_problem(args, dry_run=True)
    out(f"✓ 数据合法：问题域 {domain}" + (f"，变体 {variant}" if variant else ""))
    f = registry.fidelity(domain, variant) if domain != "tsp" else {"level": "standard", "note": ""}
    out(f"  保真度：{registry.FIDELITY_LABEL[f['level']]}" + (f"——{f['note']}" if f["note"] else ""))
    out("  规整后的规模：" + ", ".join(f"{k}={v}" for k, v in problem.items()
                                      if isinstance(v, int) and not isinstance(v, bool) and k != "seed"))


def _write_curve(path, curve):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["iter", "best"])
        w.writerows(curve)


def cmd_solve(args):
    domain, variant, problem = read_problem(args)
    cat, defaults = algo_catalog(domain, variant)
    if args.algo not in cat:
        die(f"{domain} 没有算法 {args.algo!r}。可用：{', '.join(sorted(cat))}")
    params = parse_params(args.param, set(defaults) - {"max_iter", "seed"} if defaults else None)
    r = run_once(domain, variant, problem, args.algo, args.iters, args.seed, params)
    name = cat[args.algo][0]
    goal = {"min": "越小越好", "max": "越大越好"}[r["sense"]]
    fid = registry.fidelity(domain, variant) if domain != "tsp" else {"level": "standard"}
    tag = "" if fid["level"] == "standard" else f"  [{registry.FIDELITY_LABEL[fid['level']]}]"
    out(f"{domain}" + (f"/{variant}" if variant else "") + f"  算法 {args.algo}（{name}）  {args.iters} 代  种子 {args.seed}" + tag)
    out(f"  最优值：{r['best']}（{goal}）    耗时 {r['elapsed_s']}s")
    if r["curve"]:
        first = r["curve"][0][1]
        out(f"  收敛：第 1 代 {first} → 第 {r['curve'][-1][0]} 代 {r['curve'][-1][1]}")
    if args.out:
        payload = {"schema": RESULT_SCHEMA, "generator": "cli", "domain": domain, "variant": variant,
                   "algo": args.algo, "algo_name": name, "seed": args.seed, "iters": args.iters,
                   "completed_iters": args.iters, "params": params,
                   "sense": r["sense"], "best": r["best"], "best_solution": r["solution"],
                   "elapsed_s": r["elapsed_s"], "curve": r["curve"], "problem": problem}
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        out(f"  结果已写入 {args.out}")
    if args.curve:
        _write_curve(args.curve, r["curve"])
        out(f"  收敛曲线已写入 {args.curve}")


def _close(a, b):
    """网页导出的曲线值做过四舍五入（TSP 页 3 位小数），所以不要求逐位相等。"""
    if a is None or b is None:
        return a == b
    return abs(a - b) <= 2e-3 + 1e-6 * abs(b)


def cmd_replay(args):
    """读一份 swarm-result/v1，用里面的实例 / 算法 / 种子 / 参数重新跑，逐点核对收敛曲线。"""
    try:
        with open(args.file, encoding="utf-8-sig") as f:
            res = json.load(f)
    except (OSError, ValueError) as e:
        die(f"读不了结果文件 {args.file}：{e}")
    if not isinstance(res, dict) or res.get("schema") != RESULT_SCHEMA:
        die(f"{args.file} 不是 {RESULT_SCHEMA} 结果文件（顶层应有 \"schema\": \"{RESULT_SCHEMA}\"）")
    missing = [k for k in ("domain", "algo", "seed", "iters", "problem", "curve") if res.get(k) is None]
    if missing:
        die("结果文件缺少字段：" + "、".join(missing))
    domain, variant = res["domain"], res.get("variant")
    code = (res["problem"] or {}).get("objective_python") if isinstance(res["problem"], dict) else None
    if code:  # 结果里带着一段 Python 代码：复现 = 运行它，必须由你明确同意
        if not args.trust_code:
            die("这份结果的目标函数是一段 Python 代码（下面是全文），复现它就是在你的电脑上运行这段代码。\n"
                + "-" * 40 + "\n" + code.rstrip() + "\n" + "-" * 40 +
                "\n看过确认没问题后，加 --trust-code 再运行。")
        import userproblem
        userproblem.enable_python()
    v = V.validate(domain, res["problem"], variant=variant)
    show_issues(v["errors"], v["warnings"])
    if not v["ok"]:
        die("结果里的实例没有通过校验，无法复现")
    cat, _ = algo_catalog(domain, variant or (v["problem"] or {}).get("variant"))
    if res["algo"] not in cat:
        die(f"{domain} 里没有算法 {res['algo']!r}（这份结果可能来自别的版本）")
    r = run_once(domain, variant or (v["problem"] or {}).get("variant"), v["problem"], res["algo"], res["iters"],
                 res["seed"], res.get("params") or {})
    mine = {int(it): b for it, b in r["curve"]}
    checked, bad = 0, []
    for it, b in res["curve"]:
        if int(it) in mine:
            checked += 1
            if not _close(mine[int(it)], b):
                bad.append((int(it), b, mine[int(it)]))
    full = res.get("completed_iters", res["iters"]) >= res["iters"]
    out(f"{domain}" + (f"/{variant}" if variant else "") + f"  算法 {res['algo']}  {res['iters']} 代  种子 {res['seed']}")
    if not checked:
        die("结果里的曲线与重跑的曲线没有任何共同的代数，无法核对")
    if bad:
        it, rec, now = bad[0]
        out(f"✗ 没能复现：{checked} 个曲线点里 {len(bad)} 个不一致（第 {it} 代：记录 {rec}，重跑 {now}）")
        sys.exit(1)
    out(f"✓ 复现成功：核对了 {checked} 个曲线点，全部一致" + ("" if full else f"（原运行在第 {res['completed_iters']} 代被停止，只核对到那里）"))
    if full and res.get("best") is not None and not _close(r["best"], res["best"]):
        out(f"✗ 但最终最优值不一致：记录 {res['best']}，重跑 {r['best']}")
        sys.exit(1)
    out(f"  最终最优值 {r['best']}")


def cmd_compare(args):
    domain, variant, problem = read_problem(args)
    cat, defaults = algo_catalog(domain, variant)
    keys = sorted(cat) if args.algos == "all" else [a.strip() for a in args.algos.split(",") if a.strip()]
    bad = [k for k in keys if k not in cat]
    if bad:
        die(f"{domain} 没有算法 {', '.join(bad)}。可用：{', '.join(sorted(cat))}")
    params = parse_params(args.param, set(defaults) - {"max_iter", "seed"} if defaults else None)
    rows, sense = [], "min"
    for k in keys:
        try:
            r = run_once(domain, variant, problem, k, args.iters, args.seed, params)
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001  某个算法在该实例上崩溃不应拖垮整张对比表
            rows.append((k, None, None, f"{type(e).__name__}: {str(e)[:40]}"))
            continue
        sense = r["sense"]
        rows.append((k, r["best"], r["elapsed_s"], ""))
        print(f"  … {k}", file=sys.stderr)
    ok = sorted([r for r in rows if r[1] is not None], key=lambda r: r[1], reverse=(sense == "max"))
    out(f"{domain}" + (f"/{variant}" if variant else "") + f"  {args.iters} 代  种子 {args.seed}  （{'越大越好' if sense == 'max' else '越小越好'}）")
    out(f"  {'名次':<4} {'算法':<12} {'最优值':>14} {'耗时(s)':>9}   名称")
    for i, (k, best, t, _) in enumerate(ok, 1):
        out(f"  {i:<4} {k:<12} {best:>14} {t:>9}   {cat[k][0]}")
    for k, _, _, err in (r for r in rows if r[1] is None):
        out(f"  --   {k:<12} 运行失败：{err}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"schema": RESULT_SCHEMA + "-compare", "domain": domain, "variant": variant,
                       "seed": args.seed, "iters": args.iters, "sense": sense,
                       "ranking": [{"algo": k, "best": b, "elapsed_s": t} for k, b, t, _ in ok]},
                      f, ensure_ascii=False)
        out(f"结果已写入 {args.out}")


# ------------------------------------------------------------------ 入口

def build_parser():
    ap = argparse.ArgumentParser(prog="swarm.py", description="用自己的数据运行群智能算法（数据只在本机处理）。",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="列出问题域 / 某个域的算法")
    p.add_argument("domain", nargs="?")
    p.add_argument("--variant")
    p.set_defaults(fn=cmd_list)

    p = sub.add_parser("template", help="打印某个域的示例数据")
    p.add_argument("domain")
    p.add_argument("--variant")
    p.set_defaults(fn=cmd_template)

    p = sub.add_parser("generate", help="生成指定规模的随机实例（输出 JSON，可重定向保存）")
    p.add_argument("domain")
    p.add_argument("--variant")
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--opt", action="append", metavar="名称=值", help="规模参数，如 n=200；可重复")
    p.set_defaults(fn=cmd_generate)

    def common(p, algo_arg):
        p.add_argument("file", help="数据文件（.json / .csv / .cnf / .col）")
        p.add_argument("--domain", help="问题域（JSON 外壳里已写则可省略）")
        p.add_argument("--variant", help="变体（kpvar/gcvar/bpvar/entryseq/custom 等）")
        p.add_argument("--objective-py", dest="objective_py", metavar="文件.py",
                       help="自带问题（custom）：用本地 Python 文件里的 def objective(x, data) 作目标函数（只在命令行可用）")
        if algo_arg == "one":
            p.add_argument("--algo", required=True, help="算法键，见 list")
        elif algo_arg == "many":
            p.add_argument("--algos", required=True, help="逗号分隔的算法键，或 all")
        if algo_arg:
            p.add_argument("--iters", type=int, default=200, help="迭代代数（默认 200）")
            p.add_argument("--seed", type=int, default=7, help="随机种子（默认 7）")
            p.add_argument("--param", action="append", metavar="名称=值", help="覆盖算法参数，可重复")
            p.add_argument("--out", help="把结果写成 JSON")

    p = sub.add_parser("check", help="只校验数据")
    common(p, None)
    p.set_defaults(fn=cmd_check)
    p = sub.add_parser("solve", help="求解")
    common(p, "one")
    p.add_argument("--curve", help="把收敛曲线写成 CSV")
    p.set_defaults(fn=cmd_solve)
    p = sub.add_parser("compare", help="多算法对比")
    common(p, "many")
    p.set_defaults(fn=cmd_compare)
    p = sub.add_parser("replay", help="复现一份 swarm-result/v1 结果文件并核对曲线")
    p.add_argument("file", help="结果文件（命令行 --out 或网页「结果 JSON」导出）")
    p.add_argument("--trust-code", action="store_true", help="结果里的目标函数是 Python 代码时，确认已读过并同意运行它")
    p.set_defaults(fn=cmd_replay)
    return ap


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, io.UnsupportedOperation):
            pass
    args = build_parser().parse_args(argv)
    if getattr(args, "iters", 1) < 1:
        die("--iters 必须 ≥ 1")
    args.fn(args)


if __name__ == "__main__":
    main()

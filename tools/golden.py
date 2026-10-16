# -*- coding: utf-8 -*-
"""黄金快照：对「每个域 × 变体 × 算法」固定种子跑 ITERS 代，记录 首代/中段/末代 的最优值。

用途：重构安全网。任何不应改变算法行为的改动（拆文件、改注册表、换分类）之后，快照必须逐项一致；
故意改变行为（修算法、撤下组合）则需要 `python tools/golden.py --update` 并在提交里说明为什么变了。

    python tools/golden.py            # 与 tests/golden/results.json 比对，列出差异
    python tools/golden.py --update   # 重新生成快照

结果必须与 Python 哈希种子无关（同一份快照在任意 PYTHONHASHSEED 下都应复现），否则快照本身就是噪声。
"""
import json
import os
import random
import sys
import time

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "py"))

import domains as D  # noqa: E402
import solvers as S  # noqa: E402

ITERS = 30
SEED = 7
SNAPSHOT = os.path.join(ROOT, "tests", "golden", "results.json")


def combos():
    """(域, 变体)：来自登记表 py/registry.py（含排程域）。"""
    import registry
    yield from registry.cases(include_scheduling=True)


def _triplet(curve):
    mid = curve[len(curve) // 2]
    return [round(curve[0], 6), round(mid, 6), round(curve[-1], 6)]


def _run_domain(dom, var, algo):
    opts = {"variant": var} if var else {}
    pre = D.domain_preset(dom, SEED, opts)
    D.domain_start(dom, pre, algo, json.dumps({"max_iter": ITERS, "seed": SEED}))
    curve = []
    while True:
        s = D.domain_step()
        if s is None:
            break
        st = json.loads(s)
        key = "best" if "best" in st else "nd"
        curve.append(float(st[key]))
    return _triplet(curve) if curve else None


def _run_tsp(algo):
    rng = random.Random(SEED)
    cities = [[round(rng.uniform(0, 100), 3), round(rng.uniform(0, 100), 3)] for _ in range(30)]
    prob = S.build_problem(cities)
    curve = [st.best_cost for st in S.SOLVERS[algo]().solve(prob, {"max_iter": ITERS, "seed": SEED})]
    return _triplet(curve) if curve else None


def run_all():
    out, errors = {}, {}
    for dom, var in combos():
        opts = {"variant": var} if var else {}
        for a in json.loads(D.domain_list(dom, opts))["algos"]:
            key = f"{dom}/{var or '-'}/{a['key']}"
            try:
                out[key] = _run_domain(dom, var, a["key"])
            except Exception as e:  # noqa: BLE001
                errors[key] = f"{type(e).__name__}: {str(e)[:80]}"
    for algo, cls in S.SOLVERS.items():
        if cls.implemented:
            try:
                out[f"tsp/-/{algo}"] = _run_tsp(algo)
            except Exception as e:  # noqa: BLE001
                errors[f"tsp/-/{algo}"] = f"{type(e).__name__}: {str(e)[:80]}"
    return out, errors


def diff(old, new):
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(k for k in set(old) & set(new) if old[k] != new[k])
    return added, removed, changed


def main(argv):
    t0 = time.time()
    new, errors = run_all()
    print(f"跑完 {len(new)} 个组合，{len(errors)} 个报错，用时 {time.time() - t0:.0f}s")
    for k, e in sorted(errors.items())[:20]:
        print(f"  报错 {k}: {e}")
    if "--update" in argv:
        if errors:
            print("有组合报错，拒绝写入快照（先修掉，或确认它们应当被撤下）")
            return 1
        os.makedirs(os.path.dirname(SNAPSHOT), exist_ok=True)
        with open(SNAPSHOT, "w", encoding="utf-8", newline="\n") as f:
            json.dump(dict(sorted(new.items())), f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        print(f"已写入 {os.path.relpath(SNAPSHOT, ROOT)}")
        return 0
    with open(SNAPSHOT, encoding="utf-8") as f:
        old = json.load(f)
    added, removed, changed = diff(old, new)
    print(f"新增 {len(added)}  消失 {len(removed)}  数值变化 {len(changed)}")
    for k in changed[:30]:
        print(f"  {k}: {old[k]} → {new[k]}")
    for k in removed[:15]:
        print(f"  消失 {k}")
    for k in added[:15]:
        print(f"  新增 {k}")
    return 0 if not (added or removed or changed or errors) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

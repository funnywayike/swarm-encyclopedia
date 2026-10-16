# -*- coding: utf-8 -*-
"""上报的最优值必须是它自己上报的最优解真能达到的值。

背景（2026-10 发现）：旧的黄金快照和「严口径门」只比较算法上报的数字，没人核对「这个数字是不是那个解的真实目标值」。
结果有 20 多个算法内核——集合覆盖 / SAT / QUBO 上的 de、abc、woa、gwo、cs（种群起点的值与之后的值符号相反，
实际在最大化代价，却把 -代价 当作更优上报，集合覆盖里出现过负成本），以及 EO / MFO / Jaya / TLBO 的排列版、指派版、位向量版
（先在原位置上改、再决定是否接受，位置与值错位）——一直在上报自己达不到的成绩，而且看起来比别的算法都好。

本测试对每个域 / 变体 / 算法：跑几代，用上下文自己的目标函数重算 best_sol，必须等于上报的 best；
并且 best 沿代数只能朝「更好」的方向走。"""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "py"))

import domains as D  # noqa: E402
import registry as REG  # noqa: E402

ITERS = 12


def _run(dom, var, algo):
    opts = {"variant": var} if var else {}
    pre = json.loads(D.domain_preset(dom, 7, opts))
    info = json.loads(D.domain_start(dom, json.dumps(pre), algo, json.dumps({"max_iter": ITERS, "seed": 3})))
    ctx = D._RUN["ctx"]
    states = []
    while True:
        s = D.domain_step()
        if s is None:
            break
        states.append(json.loads(s))
    return info, ctx, states


def _cases():
    out = []
    for dom, var in REG.cases():
        opts = {"variant": var} if var else {}
        for a in json.loads(D.domain_list(dom, opts))["algos"]:
            out.append((dom, var, a["key"]))
    return out


# 目标函数是 ctx.obj(解) 的域（解 = best_sol 本身）。其余域（排列解码、多目标、连续）另有各自的 obj 形态，不在这里核对。
def _obj_of(ctx, sol):
    if hasattr(ctx, "sign") and hasattr(ctx, "f"):  # 自带问题：用用户的目标函数按用户的口径（max/min）重算
        try:
            return ctx.f(sol)
        except Exception:  # noqa: BLE001
            return None
    f = getattr(ctx, "obj", None) or getattr(ctx, "eval", None)  # 连续域的目标函数叫 eval
    if f is None:
        return None
    try:
        v = f(sol)
    except Exception:  # noqa: BLE001
        return None
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


@pytest.mark.parametrize("dom,var,algo", _cases(), ids=lambda v: str(v))
def test_reported_best_matches_the_reported_solution(dom, var, algo):
    info, ctx, states = _run(dom, var, algo)
    assert states, "没有产出任何状态"
    last = states[-1]
    best = last.get("best")
    if dom == "continuous" and "best_sol" not in last and len(last.get("gbest_pos", [])) == ctx.dim:
        last = dict(last, best_sol=last["gbest_pos"])  # 连续域只在维度 ≤ 2 时给出完整最优位置
    if not isinstance(best, (int, float)) or not isinstance(last.get("best_sol"), list):
        pytest.skip("该算法的状态不含数值 best / 列表 best_sol")
    sense = info.get("sense", "min")
    if sense not in ("min", "max"):
        pytest.skip("多目标：没有单一 best")
    # best 只能朝更好的方向走（容许浮点噪声）
    vals = [s["best"] for s in states if isinstance(s.get("best"), (int, float))]
    for a, b in zip(vals, vals[1:]):
        assert (b <= a + 1e-9) if sense == "min" else (b >= a - 1e-9), f"best 变差了：{a} → {b}"
    rec = _obj_of(ctx, last["best_sol"])
    if rec is None:
        pytest.skip("该域没有可直接对解重算的 obj")
    assert abs(rec - best) <= 1e-6 * max(1.0, abs(rec)), \
        f"上报 best={best}，但它的 best_sol 重算出来是 {rec}（上报了自己达不到的成绩）"


# ---------------------------------------------------------------- TSP 求解器
import random  # noqa: E402

import solvers as S  # noqa: E402


@pytest.mark.parametrize("key", [k for k, c in S.SOLVERS.items() if c.implemented])
def test_tsp_best_cost_matches_best_tour_and_never_worsens(key):
    """页面写着「红线=全局最优，只降不升」：每一代上报的 best_cost 都必须等于 best_tour 的真实长度，且不增。"""
    rng = random.Random(5)
    pts = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(25)]
    prob = S.problem_from_spec(pts)
    prev = None
    for st in S.SOLVERS[key]().solve(prob, {"max_iter": 12, "seed": 3}):
        if st.extra.get("open"):  # 构造型算法逐城生长中，路径尚未闭合
            continue
        real = S.tour_length(st.best_tour, prob["D"])
        assert abs(real - st.best_cost) <= 1e-6 * max(1.0, real), f"第 {st.iteration} 代：上报 {st.best_cost}，路径真实长度 {real}"
        assert sorted(st.best_tour) == list(range(25)), "路径不是合法排列"
        if prev is not None:
            assert st.best_cost <= prev + 1e-9, f"best_cost 变差了：{prev} → {st.best_cost}"
        prev = st.best_cost

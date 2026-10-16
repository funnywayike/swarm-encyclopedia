# -*- coding: utf-8 -*-
"""
P1 域引擎组件库 —— 问题域侧可复用组件（S1-1 组件化重构，2026-09-17）
==========================================================================
单一事实来源：py/domains.py（背包/连续/排列域引擎）中跨算法重复的骨架件全部搬到这里。
与 py/components.py 的分工：
  components.py      = TSP 排列域通用算子（构造/局部搜索/交叉/编码），服务 solvers.py
  domain_components.py = 问题域引擎的通用骨架件（最优追踪/种群基建/二进制与排列算子），服务 domains.py

构建期行为与 components.py 同款：build_pages.py 把本文件与 domains.py 拼进同一名字
空间执行，此时 domains.py 里的 `from domain_components import ...` 抛 ImportError →
except 分支跳过（所有名字已在空间内），两种环境行为完全一致。

纪律：本文件所有函数都必须保持 RNG 调用顺序与被替换的内联写法严格一致——
bench/selfcheck/tests 全部依赖固定 seed 的可复现性，顺序一变=行为一变。
"""

import random
from typing import List, Optional, Tuple


# ============================ 最优追踪 ============================

def bump(best, bs, v, s, mode: str = "max"):
    """最优解追踪：v 优于 best 时返回 (v, list(s))，否则原样返回。

    替换各算法里成对的 `if v > best: best, bs = v, list(s)`；
    min 模式（连续域最小化）传 mode="min"。
    """
    if (v > best) if mode == "max" else (v < best):
        return v, list(s)
    return best, bs


def argbest(vals: List, mode: str = "max") -> int:
    """种群最优个体下标（并列取最先出现，与内联 max/min(range(...)) 写法一致）。"""
    if mode == "max":
        return max(range(len(vals)), key=lambda i: vals[i])
    return min(range(len(vals)), key=lambda i: vals[i])


def argworst(vals: List, mode: str = "max") -> int:
    """种群最差个体下标（mode=max 时最差=最小值）。"""
    return argbest(vals, mode="min" if mode == "max" else "max")


# ============================ 二进制编码算子（背包域） ============================

def bits_uniform(pa: List[int], pb: List[int], rng: random.Random) -> List[int]:
    """均匀交叉：逐位以 0.5 概率取父本 1 或 2（RNG 顺序 = 先随机后取位，与内联一致）。"""
    return [pa[i] if rng.random() < 0.5 else pb[i] for i in range(len(pa))]


def bits_mutate(child: List[int], pm: float, rng: random.Random) -> List[int]:
    """逐位翻转变异：每位以 pm 概率翻转（原地修改并返回）。"""
    for i in range(len(child)):
        if rng.random() < pm:
            child[i] ^= 1
    return child


def bits_flip(s: List[int], rng: random.Random, k: int = 1) -> List[int]:
    """随机 k 位翻转（返回新列表）。"""
    s = list(s)
    for _ in range(k):
        s[rng.randrange(len(s))] ^= 1
    return s


def bits_pop_init(ctx, p: dict, rng: random.Random) -> Tuple[List, List]:
    """种群初始化基建：ctx.random 生成 + ctx.value 评估（背包域口径）。"""
    pop = [ctx.random(rng) for _ in range(p["n_pop"])]
    return pop, [ctx.value(s) for s in pop]


def greedy_replace(pop: list, vals: list, i: int, cand, v, mode: str = "max") -> bool:
    """贪心逐位替换（DE/WOA/GWO/CS 家族共用的「新解优于当前个体则替换」基建）。
    返回是否发生替换；最优追踪由调用方随后 bump。"""
    if (v > vals[i]) if mode == "max" else (v < vals[i]):
        pop[i], vals[i] = cand, v
        return True
    return False


# ============================ 排列域算子（图着色 + 装箱共用） ============================

def pm_ox(a: List[int], b: List[int], rng: random.Random) -> List[int]:
    """OX 顺序交叉（与 TSP 组件 _ox_crossover 同款；域名字空间自含一份，
    因 domains_src.js 与 solvers_src.js 是两个独立 Pyodide 名字空间）。"""
    n = len(a)
    i, j = sorted(rng.sample(range(n), 2))
    child: List[Optional[int]] = [None] * n
    child[i:j + 1] = a[i:j + 1]
    seg = set(child[i:j + 1])
    fill = [x for x in b if x not in seg]
    k = 0
    for idx in range(n):
        if child[idx] is None:
            child[idx] = fill[k]
            k += 1
    return child


def pm_swap(perm: List[int], rng: random.Random) -> List[int]:
    """交换邻域：随机取两位互换。"""
    p = list(perm)
    i, j = rng.sample(range(len(p)), 2)
    p[i], p[j] = p[j], p[i]
    return p


def pm_insert(perm: List[int], rng: random.Random) -> List[int]:
    """插入邻域：随机取一位移到随机位置。"""
    p = list(perm)
    v = p.pop(rng.randrange(len(p)))
    p.insert(rng.randrange(len(p)), v)
    return p


def pm_polish(ctx, perm: List[int], rng: random.Random, moves: int) -> List[int]:
    """memetic 组件：随机交换邻域的首改进爬山（小预算，元组字典序目标）。"""
    perm = list(perm)
    c = ctx.decode(perm)
    for _ in range(moves):
        cand = pm_swap(perm, rng)
        cc = ctx.decode(cand)
        if cc < c:  # 元组字典序：(主指标, 次级指标)
            perm, c = cand, cc
    return perm

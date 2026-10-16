# -*- coding: utf-8 -*-
"""
P1 组件库 —— 可复用算子目录（v1.2 组件化重构，蓝图 R6/R8）
==========================================================
单一事实来源：solvers.py 的通用算子全部搬到这里，新算法（P1.3+）直接用组件装配。
- 本地 / pytest：solvers.py 通过受保护 import 正常导入本模块
- Pyodide 构建期：build_pages.py 把本文件与 solvers.py 拼接进同一名字空间执行，
  此时 solvers.py 里的 `from components import ...` 会 ImportError → except 分支
  跳过（所有名字已在空间内），两种环境行为完全一致
分组按蓝图 R8：构造器 / 局部搜索 / 扰动 / 交叉与序列 / 编码。
"""

import math
import random
from typing import Any, Dict, List, Optional, Tuple

# ============================ 构造器 ============================

def _nint(x: float) -> int:
    return int(x + 0.5)  # TSPLIB 的 nint：四舍五入（距离非负）


def _tsplib_geo_rad(v: float) -> float:
    deg = int(v)
    return 3.141592 * (deg + 5.0 * (v - deg) / 3.0) / 180.0  # TSPLIB 把 DDD.MM 当作度.分


def _tsplib_dist(metric: str, a: List[float], b: List[float]) -> float:
    """TSPLIB 95 规定的距离函数（EUC_2D 等是整数化距离，这样才能和公开的最优值对得上）"""
    dx, dy = a[0] - b[0], a[1] - b[1]
    if metric == "EUC_2D":
        return float(_nint(math.hypot(dx, dy)))
    if metric == "CEIL_2D":
        return float(math.ceil(math.hypot(dx, dy)))
    if metric == "MAN_2D":
        return float(_nint(abs(dx) + abs(dy)))
    if metric == "MAX_2D":
        return float(max(_nint(abs(dx)), _nint(abs(dy))))
    if metric == "ATT":
        r = math.sqrt((dx * dx + dy * dy) / 10.0)
        t = _nint(r)
        return float(t + 1 if t < r else t)
    if metric == "GEO":
        la1, lo1 = _tsplib_geo_rad(a[0]), _tsplib_geo_rad(a[1])
        la2, lo2 = _tsplib_geo_rad(b[0]), _tsplib_geo_rad(b[1])
        q1 = math.cos(lo1 - lo2)
        q2 = math.cos(la1 - la2)
        q3 = math.cos(la1 + la2)
        return float(int(6378.388 * math.acos(max(-1.0, min(1.0, 0.5 * ((1.0 + q1) * q2 - (1.0 - q1) * q3)))) + 1.0))
    raise ValueError(f"未知距离类型 {metric!r}")


TSP_METRICS = ("EUC_2D", "CEIL_2D", "ATT", "GEO", "MAN_2D", "MAX_2D")


def build_problem(cities: List[List[float]], metric: Optional[str] = None,
                  matrix: Optional[List[List[float]]] = None) -> Dict[str, Any]:
    """把城市坐标打包成 problem（含距离矩阵）。n<=150 时 O(n^2) 建矩阵完全够用。
    metric=None：欧氏距离（浮点）；metric 取 TSP_METRICS 之一：按 TSPLIB 规定的整数化距离；
    matrix：直接给定的对称距离矩阵（此时 cities 只用于画图）。"""
    n = len(cities)
    if matrix is not None:
        return {"cities": cities, "D": [[float(v) for v in row] for row in matrix], "n": len(matrix)}
    D = [[0.0] * n for _ in range(n)]
    for i in range(n):
        xi, yi = cities[i]
        for j in range(i + 1, n):
            xj, yj = cities[j]
            d = math.hypot(xi - xj, yi - yj) if metric is None else _tsplib_dist(metric, cities[i], cities[j])
            D[i][j] = d
            D[j][i] = d
    return {"cities": cities, "D": D, "n": n}


def problem_from_spec(spec: Any) -> Dict[str, Any]:
    """前端 / 命令行传来的实例：裸坐标列表，或校验器规整后的 {"cities", "metric"?, "matrix"?}"""
    if isinstance(spec, dict):
        return build_problem(spec["cities"], spec.get("metric") if spec.get("metric") in TSP_METRICS else None,
                             spec.get("matrix"))
    return build_problem(spec)



def tour_length(tour: List[int], D: List[List[float]]) -> float:
    s = 0.0
    n = len(tour)
    for i in range(n):
        s += D[tour[i]][tour[(i + 1) % n]]
    return s



def nearest_neighbor(D: List[List[float]], start: int = 0) -> List[int]:
    """最近邻构造初始解：简单、快，是所有改进型算法的合格起点"""
    n = len(D)
    unvisited = set(range(n))
    tour = [start]
    unvisited.remove(start)
    cur = start
    while unvisited:
        nxt = min(unvisited, key=lambda j: D[cur][j])
        tour.append(nxt)
        unvisited.remove(nxt)
        cur = nxt
    return tour


def _grasp_construct(D: List[List[float]], rng: random.Random, k: int = 2) -> List[int]:
    """GRASP 半贪心构造（RCL 限制候选列表，数量式）。

    每步把未访问城市按到当前城市的距离排序，从最近的 k 个里随机选一个。
    k=1 就是纯最近邻；k 越大随机性越强、构造越差。实测（n=60 均匀散点）：
    k=2 构造 raw ~1060、2-opt 打磨后 ~621-746；k=5 直接劣化到 1524/806——
    TSP 距离强聚集，RCL 宽度必须小（k=2~3 是甜区），这不是实现取舍，
    是本站两次假跑教训换来的实测结论（区间式 RCL 在均匀散点上会膨胀失效）。
    """
    n = len(D)
    start = rng.randrange(n)
    unvisited = set(range(n))
    unvisited.remove(start)
    tour = [start]
    cur = start
    while unvisited:
        cand = sorted(unvisited, key=lambda j: D[cur][j])[: max(2, k)]
        nxt = rng.choice(cand)
        tour.append(nxt)
        unvisited.remove(nxt)
        cur = nxt
    return tour



# ============================ 局部搜索 ============================

def _first_improving_move(tour: List[int], D: List[List[float]]) -> Optional[Tuple[int, int, float]]:
    """找到第一个能改进的 2-opt 移动（i, k, delta），没有则返回 None"""
    n = len(tour)
    for i in range(1, n - 1):
        for k in range(i + 1, n):
            a, b = tour[i - 1], tour[i]
            c, d = tour[k], tour[(k + 1) % n]
            delta = D[a][c] + D[b][d] - D[a][b] - D[c][d]
            if delta < -1e-12:
                return i, k, delta
    return None



def two_opt_improve(tour: List[int], D: List[List[float]], max_moves: int = 500) -> List[int]:
    """一次性 2-opt 改进（不产生中间状态，用于算法内部加速）"""
    best = list(tour)
    moves = 0
    while moves < max_moves:
        m = _first_improving_move(best, D)
        if m is None:
            break
        i, k, _ = m
        best[i : k + 1] = reversed(best[i : k + 1])
        moves += 1
    return best



def _random_2opt_shot(tour: List[int], D: List[List[float]], rng: random.Random, trials: int = 20) -> List[int]:
    """随机 2-opt「打了就跑」：随机抽 trials 个 2-opt 移动，只接受改进的。

    与 two_opt_improve 的区别：那个是 first-improvement 全扫描，一次调用 O(n²)，
    只能偶尔用；这个是 O(trials)，可以在算法内部每代高频调用。
    做 memetic（算法+局部搜索）时这个才是顺手的工具。
    """
    n = len(tour)
    t = list(tour)
    for _ in range(trials):
        if n < 4:
            break
        i = rng.randrange(1, n - 1)
        k = rng.randrange(i + 1, n)
        a, b = t[i - 1], t[i]
        c, d = t[k], t[(k + 1) % n]
        delta = D[a][c] + D[b][d] - D[a][b] - D[c][d]
        if delta < -1e-12:
            t[i : k + 1] = reversed(t[i : k + 1])
    return t



# ============================ 扰动 ============================

def _double_bridge(tour: List[int], rng: random.Random) -> List[int]:
    """双桥扰动（double bridge）：ILS/VNS 的标准 kick 算子。

    在排列上切 4 段重排：A B C D → A C B D。这个扰动有个漂亮性质：
    它不可能被任何一次 2-opt 移动还原——正好把解踢出 2-opt 局部盆地。
    """
    n = len(tour)
    if n < 8:
        i, j = rng.sample(range(n), 2)
        t = list(tour)
        t[i], t[j] = t[j], t[i]
        return t
    a, b, c = sorted(rng.sample(range(2, n - 1), 3))
    t = list(tour)
    return t[:a] + t[b:c] + t[a:b] + t[c:]



def _or_opt_move(tour: List[int], rng: random.Random, seg_len: int) -> List[int]:
    """or-opt 移动：摘下一段长 seg_len 的连续城市，插到别的位置（VNS 的第二层邻域）"""
    n = len(tour)
    seg_len = max(1, min(seg_len, n - 2, n // 2))  # 剩下的城市数要 ≥ 段长，否则没有可插入的位置（n=5、段长 3 时曾崩溃）
    i = rng.randrange(0, n - seg_len)
    seg = tour[i : i + seg_len]
    rest = tour[:i] + tour[i + seg_len :]
    j = rng.randrange(0, len(rest) - seg_len + 1)
    return rest[:j] + seg + rest[j:]



def _reverse_mutation(tour: List[int], rng: random.Random) -> List[int]:
    """反转变异：随机取一段倒过来。对 TSP 而言"逆转"比"交换两点"更有效"""
    n = len(tour)
    a, b = sorted(rng.sample(range(n), 2))
    t = list(tour)
    t[a : b + 1] = reversed(t[a : b + 1])
    return t



# ============================ 交叉与序列 ============================

def swap_seq_to_target(cur: List[int], target: List[int]) -> List[Tuple[int, int]]:
    """求把 cur 变成 target 所需的交换序列（离散 PSO 的"速度"）"""
    seq: List[Tuple[int, int]] = []
    pos = {city: i for i, city in enumerate(cur)}
    for i in range(len(cur)):
        if cur[i] != target[i]:
            j = pos[target[i]]
            cur[i], cur[j] = cur[j], cur[i]
            pos[cur[i]] = i
            pos[cur[j]] = j
            seq.append((i, j))
    return seq



def _prefix(seq: List[Tuple[int, int]], prob: float, rng: random.Random) -> List[Tuple[int, int]]:
    """按概率取序列的前缀（离散 PSO 标准做法：速度片段是"连续前缀"而非随机子集）"""
    k = int(len(seq) * min(prob, 1.0) * rng.random())
    return seq[:k]



def apply_swaps(tour: List[int], swaps: List[Tuple[int, int]]) -> List[int]:
    t = list(tour)
    for i, j in swaps:
        t[i], t[j] = t[j], t[i]
    return t



def _ox_crossover(p1: List[int], p2: List[int], rng: random.Random) -> List[int]:
    """顺序交叉 OX：保留父代1的一段，其余位置按父代2的相对顺序填充。

    TSP 最经典的交叉算子——它保留的是"相对顺序"而不是"绝对位置"，
    这才是排列编码真正该继承的信息。用 set 判重，保证 O(n) 而非 O(n²)。
    """
    n = len(p1)
    a, b = sorted(rng.sample(range(n), 2))
    child: List[Optional[int]] = [None] * n
    child[a : b + 1] = p1[a : b + 1]
    taken = set(p1[a : b + 1])
    rest = [g for g in p2 if g not in taken]
    idx = 0
    for i in list(range(b + 1, n)) + list(range(0, b + 1)):
        if child[i] is None:
            child[i] = rest[idx]
            idx += 1
    return child  # type: ignore[return-value]



# ============================ 编码 ============================

def _encode_tour(tour: List[int], rng: random.Random) -> List[float]:
    """随机键编码：把排列变成一个实数向量 X，使得 argsort(X) == 原排列。

    这是把连续型算法（GWO 等）嫁接到排列问题上的标准桥梁：
    连续更新公式可以原样保留，只是每代解码一次。
    """
    n = len(tour)
    X = [0.0] * n
    for rank, city in enumerate(tour):
        X[city] = (rank + 1) / (n + 1)
    return X



def _decode_position(X: List[float]) -> List[int]:
    """随机键解码：按 X 从小到大排序，得到城市访问顺序"""
    return sorted(range(len(X)), key=lambda i: X[i])



def _roulette(rng: random.Random, weights: List[float]) -> int:
    """轮盘赌选择：返回被选中的下标。权重全 0 时退化为均匀随机"""
    total = sum(weights)
    if total <= 0:
        return rng.randrange(len(weights))
    r = rng.random() * total
    acc = 0.0
    for i, w in enumerate(weights):
        acc += w
        if acc >= r:
            return i
    return len(weights) - 1



def _shared_edges_ratio(a: List[int], b: List[int]) -> float:
    """两排列的公共边占比（无向）：Jaya「远离最劣」的相似度度量，也可用于多样性监控"""
    if len(a) != len(b) or len(a) < 2:
        return 0.0
    edges = set()
    for i in range(len(b)):
        x, y = b[i], b[(i + 1) % len(b)]
        edges.add((x, y) if x < y else (y, x))
    same = 0
    for i in range(len(a)):
        x, y = a[i], a[(i + 1) % len(a)]
        e = (x, y) if x < y else (y, x)
        if e in edges:
            same += 1
    return same / len(a)


# ============================ 组件注册表（P1.5 组件百科页数据源） ============================

COMPONENTS = [
    # (key, 名称, 分组, 一句话说明, 典型使用者)
    ("build_problem", "问题构建", "构造器", "城市坐标 → 距离矩阵 D（欧氏），全站统一问题表示", "所有 TSP 算法"),
    ("nearest_neighbor", "最近邻构造", "构造器", "从起点逐城选最近未访问城市，O(n²) 构造合法路径", "播种器通用"),
    ("grasp_construct", "RCL 半贪心构造", "构造器", "每步从最近 k 个候选中随机选一个：贪心保底、随机产生差异，GRASP 的命根子", "GRASP"),
    ("two_opt", "2-opt 下探", "局部搜索", "first-improvement 反转扫描到局部最优；max_moves 即下探预算", "几乎所有算法的打磨/重置算子"),
    ("two_opt_shot", "预算制试射", "局部搜索", "随机 2-opt 逆转、只接受改进，预算 trials 用完即停", "播种抛光 / 警戒远跳 / 重置蛙"),
    ("or_opt", "Or-opt 移段", "扰动", "随机截取小段移动到别处，保留邻接结构的结构性扰动", "ILS / VNS / Salp / SFLA"),
    ("double_bridge", "双桥扰动", "扰动", "切 4 刀换段重排，不可被 2-opt 还原的深盆地跳跃", "ILS / SFLA / Salp"),
    ("reverse_mut", "逆转突变", "扰动", "随机片段逆转，轻量勘探", "GA / DE 等"),
    ("swap_seq", "交换序列", "交叉与序列", "cur→target 交换序列 + 概率前缀执行：连续域「向目标移动」的排列域映射", "TS / DE / TLBO / SFLA / BOA"),
    ("ox_crossover", "OX 顺序交叉", "交叉与序列", "保留父代相对顺序的顺序交叉，离散文献的标准学习算子", "GA / DE / TLBO / SFLA / SOS"),
    ("random_key", "随机键编码", "编码", "排列↔连续向量双向映射，让 PSO 系算法在排列域工作", "PSO / GSA / CEM"),
    ("roulette", "轮盘选择", "编码", "按权重随机选下标", "ACO / FA"),
    ("shared_edges", "公共边相似度", "编码", "两排列的无向公共边占比：个体间相似度 / 多样性度量", "Jaya 远离最劣"),
]

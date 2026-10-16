# -*- coding: utf-8 -*-
"""
P1 算法包 —— TSP 求解器集合（零第三方依赖）
================================================
设计要点（这三点是整个项目的地基，别改）：
1. 所有求解器继承 BaseSolver，实现 solve(problem, params) -> Iterator[IterationState]
   用 yield 每代产出一个状态 → 天然支持暂停 / 单步 / 调速 / 流式动画
2. 零第三方依赖（连 numpy 都不需要）→ Pyodide 里不用加载任何包，加载快、失败率低
3. 同一份代码同时服务三个场景：① 浏览器 Pyodide ② 本地 pytest ③ 未来 P2 服务端

给 JS 的两个入口函数：start(...) / step()  —— 见文件底部
"""
from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

# ---- 组件库（v1.2 组件化重构：通用算子单一来源 = py/components.py）----
# 本地/pytest 正常导入；Pyodide 构建期 components 源码与本文件拼接进同一名字空间，
# 此 import 抛 ImportError → 跳过（名字已在空间内），两种环境行为一致
# ---- 算法分类（生成文件 py/taxonomy.py：由 data/families.json + data/algos.json 得出）----
# 本地正常导入；浏览器构建期拼进同一名字空间，ImportError 分支跳过
try:
    from taxonomy import category_of, category_rank
except ImportError:
    pass

try:
    from components import (
        _decode_position, _double_bridge, _encode_tour, _first_improving_move,
        _grasp_construct, _or_opt_move, _ox_crossover, _prefix, _random_2opt_shot,
        _reverse_mutation, _roulette, _shared_edges_ratio,
        apply_swaps, build_problem, nearest_neighbor, problem_from_spec, swap_seq_to_target,
        tour_length, two_opt_improve,
    )
except ImportError:
    pass

# ============================ 数据结构 ============================


@dataclass
class IterationState:
    """前后端契约：一旦定死，新增算法前端一行代码都不用改"""

    iteration: int          # 第几代
    best_cost: float        # 全局最优路径长度
    best_tour: List[int]    # 全局最优路径（城市下标序列）
    current_cost: float     # 当代成本（画收敛曲线第二条线，如种群均值）
    extra: Dict[str, Any] = field(default_factory=dict)  # 算法专属可视化数据


# ============================ 基础工具 ============================


# ============================ 求解器基类 ============================


class BaseSolver:
    name = "base"
    default_params: Dict[str, Any] = {}
    implemented = False
    # 算法分类（前端下拉框分组 + 卡片徽章用）
    category = "其他"
    # 参数定义域（在线调参模块的单一事实来源）：
    #   {"参数": {"min":x,"max":y,"step":s,"int":True,"label":"中文名","desc":"说明"}}
    #   选择型参数：{"type":"choice","options":[...],"labels":[...],"label":...}
    # 前端按此渲染输入框并在提交前钳制越界值；0 常表示"自动"
    param_specs: Dict[str, Any] = {}

    def solve(self, problem: Dict[str, Any], params: Dict[str, Any]) -> Iterator[IterationState]:
        raise NotImplementedError


# ============================ 已实现：基准算法 ============================


class GreedyNN(BaseSolver):
    """最近邻构造：作为对比基线，收敛曲线上的那条"起点参考线"就是它。

    v0.5.1：改为逐城动画——每连接一座城市 yield 一次（extra.open=True 表示
    路径尚未闭合）。构造期间 best_cost 恒等于最终完整回路的长度：构造型算法
    "一步到位"，没有逐代改进，收敛曲线是一条水平线（诚实反映算法性质）。
    """

    name = "最近邻 NN（基线）"
    default_params = {}
    implemented = True
    category = "构造式"
    param_specs = {}

    def solve(self, problem, params):
        D = problem["D"]
        n = problem["n"]
        tour = nearest_neighbor(D)
        c = tour_length(tour, D)
        partial = [tour[0]]
        for k in range(1, n):
            partial.append(tour[k])
            yield IterationState(
                k,
                c,
                list(partial),
                c,
                {"open": True, "note": f"构造中：已连 {k}/{n - 1} 条边（未闭合）"},
            )
        yield IterationState(n, c, tour, c, {"note": f"构造完成：闭合回路，总长 {c:.1f}"})


class TwoOptSolver(BaseSolver):
    """2-opt 局部搜索：每接受一次改进 yield 一次，动画效果最直观"""

    name = "2-opt 局部搜索"
    default_params = {"start": "nn", "max_moves": 500}
    implemented = True
    category = "局部搜索"
    param_specs = {
        "start": {"type": "choice", "options": ["nn", "random"], "labels": ["最近邻起点", "随机排列起点"], "label": "初始解", "desc": "nn=从最近邻构造出发（推荐），random=纯随机排列（教学对照）"},
        "max_moves": {"min": 10, "max": 2000, "step": 10, "int": True, "label": "最大改进步数", "desc": "最多执行多少次 2-opt 移动"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        tour = nearest_neighbor(D) if p["start"] == "nn" else list(range(problem["n"]))
        cost = tour_length(tour, D)
        it = 0
        yield IterationState(it, cost, list(tour), cost, {"note": "初始解"})
        while it < p["max_moves"]:
            m = _first_improving_move(tour, D)
            if m is None:
                break
            i, k, delta = m
            tour[i : k + 1] = reversed(tour[i : k + 1])
            cost += delta
            it += 1
            yield IterationState(it, cost, list(tour), cost, {"move": f"2-opt({i},{k})"})


# ============================ 已实现：离散粒子群 ============================


class DiscretePSO(BaseSolver):
    """
    离散 PSO（交换序版）求解 TSP
    位置 = 一个排列；速度 = 交换算子序列；更新公式沿用连续 PSO 的思想：
        v' = w*v ⊕ c1*(x→pbest) ⊕ c2*(x→gbest)
    其中 ⊕ 表示"以概率保留"。
    """

    name = "离散粒子群 PSO"
    default_params = {
        "n_particles": 40,
        "w": 0.6,          # 惯性：保留旧速度前缀的比例
        "c1": 1.4,         # 个体认知
        "c2": 1.4,         # 群体社会
        "max_iter": 200,
        "seed": 42,
        "local_search": 0.1,   # 每代以该概率对个体做小预算 2-opt（memetic）
        "ls_moves": 3,         # 个体局部搜索预算（小预算 = 渐进改进 = 好看的收敛曲线）
        "gbest_ls_every": 10,  # 每 N 代对全局最优做一次集中改进
        "gbest_ls_moves": 15,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_particles": {"min": 10, "max": 120, "step": 2, "int": True, "label": "粒子数", "desc": "种群规模，越大探索越充分但每代越慢"},
        "w": {"min": 0.0, "max": 1.0, "step": 0.05, "label": "惯性权重 w", "desc": "保留旧速度前缀的比例，大=延续惯性，小=更听两个最优的"},
        "c1": {"min": 0.0, "max": 2.5, "step": 0.1, "label": "认知系数 c1", "desc": "向自己历史最优靠近的强度"},
        "c2": {"min": 0.0, "max": 2.5, "step": 0.1, "label": "社会系数 c2", "desc": "向全局最优靠近的强度"},
        "local_search": {"min": 0.0, "max": 0.5, "step": 0.01, "label": "个体局部搜索概率", "desc": "每代每个粒子做小预算 2-opt 的概率；0=关闭（纯 PSO）"},
        "ls_moves": {"min": 1, "max": 20, "step": 1, "int": True, "label": "个体局部搜索预算", "desc": "每次局部搜索最多接受几次 2-opt 移动"},
        "gbest_ls_every": {"min": 0, "max": 50, "step": 1, "int": True, "label": "全局最优改进周期", "desc": "每 N 代对全局最优集中改进一次；0=关闭"},
        "gbest_ls_moves": {"min": 0, "max": 60, "step": 1, "int": True, "label": "全局最优改进预算", "desc": "集中改进时最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        # 初始种群：随机排列，第 0 个个体直接给 NN 解（工程上常用的加速技巧）
        particles = []
        for _ in range(p["n_particles"]):
            t = list(range(n))
            rng.shuffle(t)
            particles.append(t)
        particles[0] = nearest_neighbor(D)

        pbest = [list(t) for t in particles]
        pbest_cost = [tour_length(t, D) for t in pbest]
        gi = min(range(len(pbest_cost)), key=lambda i: pbest_cost[i])
        gbest, gbest_cost = list(pbest[gi]), pbest_cost[gi]
        vels: List[List[Tuple[int, int]]] = [[] for _ in particles]

        for it in range(1, p["max_iter"] + 1):
            mean_cost = 0.0
            for idx, x in enumerate(particles):
                seq1 = swap_seq_to_target(list(x), pbest[idx])
                seq2 = swap_seq_to_target(list(x), gbest)

                # 离散 PSO 速度更新（两段踩坑记录）：
                # ① 速度片段必须取"连续前缀"，不能随机子集——随机子集会破坏交换算子的因果关系
                # ② c1/c2 各乘一个 [0,1) 随机数——否则序列被完整应用，粒子一步变成 gbest 的复制品，种群坍塌
                r1, r2 = rng.random(), rng.random()
                v = _prefix(vels[idx], p["w"], rng)
                v += _prefix(seq1, p["c1"] * r1, rng)
                v += _prefix(seq2, p["c2"] * r2, rng)

                # 速度为空时给一次随机扰动，避免种群完全停滞
                if not v and rng.random() < 0.3:
                    v = [(rng.randrange(n), rng.randrange(n))]
                vels[idx] = v

                newx = apply_swaps(list(x), v)
                if rng.random() < p["local_search"]:
                    newx = two_opt_improve(newx, D, max_moves=p["ls_moves"])
                particles[idx] = newx

                c = tour_length(newx, D)
                mean_cost += c
                if c < pbest_cost[idx]:
                    pbest[idx] = list(newx)
                    pbest_cost[idx] = c
                    if c < gbest_cost:
                        gbest, gbest_cost = list(newx), c

            # 集中改进（intensification）：每 N 代对全局最优做一次 2-opt，
            # 并把结果回写替掉最差粒子——这是 memetic 算法的标准操作，也是曲线能持续下降的关键
            if p["gbest_ls_every"] > 0 and it % p["gbest_ls_every"] == 0:
                cand = two_opt_improve(gbest, D, max_moves=p["gbest_ls_moves"])
                cc = tour_length(cand, D)
                if cc < gbest_cost - 1e-12:
                    gbest, gbest_cost = cand, cc
                    wi = max(range(len(pbest_cost)), key=lambda i: pbest_cost[i])
                    particles[wi] = list(gbest)
                    pbest[wi] = list(gbest)
                    pbest_cost[wi] = gbest_cost

            yield IterationState(
                iteration=it,
                best_cost=gbest_cost,
                best_tour=list(gbest),
                current_cost=mean_cost / len(particles),
                extra={"n_particles": p["n_particles"]},
            )


# ============================ W2 待实现（照这个模板加） ============================


class _TemplateSolver(BaseSolver):
    """新增算法模板：改 name / default_params / 实现 solve，然后在 SOLVERS 注册即可"""

    name = "模板算法"
    default_params = {"max_iter": 100, "seed": 42}
    implemented = False

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        best = nearest_neighbor(D)
        best_cost = tour_length(best, D)
        for it in range(1, p["max_iter"] + 1):
            # TODO: 在这里实现你的迭代逻辑，并 yield 状态
            yield IterationState(it, best_cost, list(best), best_cost, {})


class ACO(BaseSolver):
    """
    蚁群算法（Ant System + 精英加强）
    转移概率 ∝ τ^alpha · (1/d)^beta；每代结束后全局挥发 + 按路径长度释放信息素。
    工程要点：用候选列表（每个城市只考虑最近的 k 个邻居）把构造复杂度从 O(n²) 降到 O(n·k)，
    否则 n=100 以上在浏览器里会卡死。
    """

    name = "蚁群算法 ACO"
    default_params = {
        "n_ants": 30,
        "alpha": 1.0,     # 信息素重要度
        "beta": 3.0,      # 启发式（距离）重要度
        "rho": 0.5,       # 挥发率
        "Q": 1.0,         # 信息素强度
        "max_iter": 200,
        "seed": 42,
        "elitist": 2,     # 全局最优路径额外释放的次数（精英策略）
        "cand_k": 20,     # 候选列表长度
        # 局部搜索（ACS 标准操作）：实测 n=100 时开启后 911 -> 823，直接反超 2-opt/PSO，必须留着
        "ls_every": 5,
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_ants": {"min": 5, "max": 80, "step": 1, "int": True, "label": "蚂蚁数", "desc": "每代并行构造解的蚂蚁数量"},
        "alpha": {"min": 0.0, "max": 4.0, "step": 0.1, "label": "信息素权重 α", "desc": "信息素浓度的相对重要度；0=纯贪心按距离走"},
        "beta": {"min": 0.0, "max": 6.0, "step": 0.1, "label": "启发式权重 β", "desc": "距离启发式的相对重要度；越大越贪心"},
        "rho": {"min": 0.05, "max": 0.9, "step": 0.05, "label": "挥发率 ρ", "desc": "每代信息素蒸发比例；太大遗忘快，太小收敛慢"},
        "Q": {"min": 0.1, "max": 5.0, "step": 0.1, "label": "信息素强度 Q", "desc": "每条路径释放的信息素总量"},
        "elitist": {"min": 0, "max": 10, "step": 1, "int": True, "label": "精英蚂蚁数", "desc": "全局最优路径额外释放信息素的次数；0=关闭精英策略"},
        "cand_k": {"min": 3, "max": 40, "step": 1, "int": True, "label": "候选列表长度", "desc": "每个城市只考虑最近的 k 个邻居（性能关键）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt（ACS 标准操作）；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        # 防御性钳制：挥发率趋近 0 会让信息素无限累积（数值爆炸），趋近 1 则瞬间遗忘
        rho = min(max(float(p["rho"]), 0.01), 0.95)

        # 大实例自动降配（浏览器里要能跑得动，这是硬性体验约束）
        n_ants = p["n_ants"]
        if n > 100:
            n_ants = max(10, n_ants // 2)

        nn_len = tour_length(nearest_neighbor(D), D)
        tau0 = (n / nn_len) if nn_len > 0 else 1.0
        tau = [[tau0] * n for _ in range(n)]

        k = max(1, min(p["cand_k"], n - 1))
        cand = [sorted((j for j in range(n) if j != i), key=lambda j: D[i][j])[:k] for i in range(n)]

        alpha, beta = p["alpha"], p["beta"]
        best, best_cost = None, float("inf")

        for it in range(1, p["max_iter"] + 1):
            tours, costs, total = [], [], 0.0
            for _ in range(n_ants):
                start = rng.randrange(n)
                tour = [start]
                unvisited = set(range(n))
                unvisited.remove(start)
                cur = start
                while unvisited:
                    cands = [j for j in cand[cur] if j in unvisited]
                    if not cands:
                        cands = list(unvisited)
                    # 重复坐标点会让 D=0 → 除零崩溃（用户上传数据必须防）
                    ws = [
                        (tau[cur][j] ** alpha) * ((1.0 / max(D[cur][j], 1e-9)) ** beta)
                        for j in cands
                    ]
                    pick = cands[_roulette(rng, ws)]
                    tour.append(pick)
                    unvisited.remove(pick)
                    cur = pick
                c = tour_length(tour, D)
                tours.append(tour)
                costs.append(c)
                total += c
                if c < best_cost:
                    best, best_cost = list(tour), c

            # 挥发
            decay = 1.0 - rho
            for row in tau:
                for j in range(n):
                    row[j] *= decay

            # 释放：所有蚂蚁 + 精英（全局最优多放几次）；路径长为 0（重复点）时钳到下限
            for t, c in zip(tours, costs):
                dep = p["Q"] / max(c, 1e-9)
                for idx in range(n):
                    a, b = t[idx], t[(idx + 1) % n]
                    tau[a][b] += dep
                    tau[b][a] += dep
            for _ in range(p["elitist"]):
                dep = p["Q"] / max(best_cost, 1e-9)
                for idx in range(n):
                    a, b = best[idx], best[(idx + 1) % n]
                    tau[a][b] += dep
                    tau[b][a] += dep

            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c

            yield IterationState(
                iteration=it,
                best_cost=best_cost,
                best_tour=list(best),
                current_cost=total / n_ants,
                extra={"n_ants": n_ants, "pheromone_max": max(max(row) for row in tau)},
            )


class GA(BaseSolver):
    """遗传算法：顺序编码 + 锦标赛选择 + OX 交叉 + 反转变异 + 精英保留"""

    name = "遗传算法 GA"
    default_params = {
        "pop": 60,
        "pc": 0.85,      # 交叉概率
        "pm": 0.20,      # 变异概率
        "max_iter": 300,
        "elite": 2,      # 精英保留个数
        "tournament": 3, # 锦标赛规模
        "seed": 42,
        "ls_every": 5,    # 每 N 代对 α/全局最优做一次 2-opt，并回灌种群（memetic GA）
        "ls_moves": 15,
        "init": "nn",     # "nn"=从随机起点出发的最近邻播种；"random"=纯随机排列（教学对照用）
    }
    implemented = True
    category = "进化计算"
    param_specs = {
        "pop": {"min": 10, "max": 150, "step": 2, "int": True, "label": "种群规模", "desc": "每代个体数量"},
        "pc": {"min": 0.0, "max": 1.0, "step": 0.05, "label": "交叉概率 pc", "desc": "一对亲代发生 OX 交叉的概率"},
        "pm": {"min": 0.0, "max": 1.0, "step": 0.05, "label": "变异概率 pm", "desc": "每个子代发生反转变异的概率"},
        "elite": {"min": 1, "max": 10, "step": 1, "int": True, "label": "精英保留数", "desc": "每代直接复制到下一代的最优个体数"},
        "tournament": {"min": 2, "max": 8, "step": 1, "int": True, "label": "锦标赛规模", "desc": "每次选择随机抽几个个体、取其中最优；越大选择压力越强"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌种群；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
        "init": {"type": "choice", "options": ["nn", "random"], "labels": ["最近邻播种", "随机排列"], "label": "初始化方式", "desc": "nn=多起点最近邻播种（推荐），random=纯随机排列（教学对照）"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        pop_size = p["pop"]
        if n > 100:
            pop_size = max(20, pop_size // 2)

        # 初始种群：与 GWO 同一个教训——全随机排列（成本 3000+）会让前几十代
        # 全部浪费在把种群从"垃圾"拉回"像样"上。默认用多起点最近邻播种。
        pop = []
        for i in range(pop_size):
            if p["init"] == "nn":
                pop.append(nearest_neighbor(D, start=0 if i == 0 else rng.randrange(n)))
            else:
                t = list(range(n))
                rng.shuffle(t)
                pop.append(t)
        costs = [tour_length(t, D) for t in pop]
        best, best_cost = list(pop[0]), costs[0]

        def _pick() -> int:
            cand = [rng.randrange(len(pop)) for _ in range(min(p["tournament"], len(pop)))]
            return min(cand, key=lambda i: costs[i])

        for it in range(1, p["max_iter"] + 1):
            order = sorted(range(len(pop)), key=lambda i: costs[i])

            # 精英直接留种（不参与交叉变异，保证最优解不会退化）
            new_pop = [list(pop[i]) for i in order[: p["elite"]]]
            new_costs = [costs[i] for i in order[: p["elite"]]]

            while len(new_pop) < len(pop):
                i1, i2 = _pick(), _pick()
                if rng.random() < p["pc"]:
                    c1 = _ox_crossover(pop[i1], pop[i2], rng)
                    c2 = _ox_crossover(pop[i2], pop[i1], rng)
                else:
                    c1, c2 = list(pop[i1]), list(pop[i2])
                if rng.random() < p["pm"]:
                    c1 = _reverse_mutation(c1, rng)
                if rng.random() < p["pm"]:
                    c2 = _reverse_mutation(c2, rng)
                new_pop.extend([c1, c2])

            new_costs += [tour_length(t, D) for t in new_pop[len(new_costs) :]]
            pop, costs = new_pop, new_costs

            i_best = min(range(len(pop)), key=lambda i: costs[i])
            if costs[i_best] < best_cost:
                best, best_cost = list(pop[i_best]), costs[i_best]

            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    pop[0], costs[0] = list(best), best_cost  # 回灌到种群（memetic）

            yield IterationState(
                it,
                best_cost,
                list(best),
                sum(costs) / len(costs),
                {"pop": len(pop), "worst": max(costs), "pc": p["pc"], "pm": p["pm"]},
            )


class SA(BaseSolver):
    """模拟退火：2-opt 邻域 + Metropolis 判据 + 指数降温。

    与群智能最大的区别：它是单点搜索，靠"以一定概率接受劣解"跳出局部最优。
    extra 里输出温度与接受率——这是 SA 最好看的可视化数据（能直观看到"退火"过程）。
    """

    name = "模拟退火 SA"
    default_params = {
        "T0": 0.0,        # 0 = 自动：取初始解的平均边长，保证初期接受率在合理量级
        "alpha": 0.97,    # 降温系数
        "max_iter": 300,
        "inner": 0,       # 0 = 自动：每个温度下的尝试次数 = 城市数
        "seed": 42,
    }
    implemented = True
    category = "物理启发"
    param_specs = {
        "T0": {"min": 0, "max": 200, "step": 1, "label": "初始温度 T₀", "desc": "0=自动（取初始解平均边长）；越大初期越容易接受劣解"},
        "alpha": {"min": 0.80, "max": 0.999, "step": 0.001, "label": "降温系数 α", "desc": "每代温度乘以 α；越接近 1 降温越慢、搜索越充分"},
        "inner": {"min": 0, "max": 500, "step": 10, "int": True, "label": "内循环次数", "desc": "每个温度下尝试多少次邻域移动；0=自动（=城市数）"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        tour = nearest_neighbor(D)
        cost = tour_length(tour, D)
        best, best_cost = list(tour), cost

        if n < 4:  # 城市太少没法做 2-opt 邻域
            yield IterationState(1, best_cost, list(best), cost, {"temperature": 0.0, "accept_rate": 0.0})
            return

        inner = p["inner"] or max(20, n)
        T = p["T0"] or (cost / n)

        for it in range(1, p["max_iter"] + 1):
            accepted = 0
            for _ in range(inner):
                i = rng.randrange(1, n - 1)
                k = rng.randrange(i + 1, n)
                a, b = tour[i - 1], tour[i]
                c, d = tour[k], tour[(k + 1) % n]
                delta = D[a][c] + D[b][d] - D[a][b] - D[c][d]
                if delta < 0 or rng.random() < math.exp(-delta / max(T, 1e-12)):
                    tour[i : k + 1] = reversed(tour[i : k + 1])
                    cost += delta
                    accepted += 1
                    if cost < best_cost:
                        best, best_cost = list(tour), cost

            if it % 50 == 0:
                cost = tour_length(tour, D)  # 增量累加会飘，周期性重算兜底
            T *= p["alpha"]

            yield IterationState(
                it,
                best_cost,
                list(best),
                cost,
                {
                    "temperature": round(T, 4),
                    "accept_rate": round(accepted / inner, 3),
                    "inner": inner,
                },
            )


class GWO(BaseSolver):
    """灰狼优化（离散版）：交换序列编码 + α/β/δ 三级领导 + 收敛因子 a 线性下降。

    ★ 踩坑记录（这个页面最值钱的部分）：
    第一版用的是"随机键"（把排列编码成实数向量，用标准 GWO 的连续公式更新，再排序解码）。
    实测下来：GWO 自身完全没有贡献，终值 626.6 与纯 2-opt 基线一模一样——
    因为三头狼位置的算术平均在实数空间里等于随机扰动，解码出来的就是随机排列，
    本质上是在做随机搜索，全靠周期性的 2-opt 兜底。这种"看起来在跑其实没在优化"的
    假象，是最危险的——曲线会下降（因为 2-opt 在干活），但算法本身没起作用。

    第三版又踩一个更隐蔽的坑：种群初始化。
    全部用随机排列播种时，成本 3000+，而 α 是 NN 解（725）。等级第二第三的 β/δ 是垃圾解，
    每匹狼被"往头狼靠近"时有一大半力气花在往垃圾解上靠 → 200 代下来终值 = 初始 NN 值，
    GWO 一点没干活（n=100 实测 1078 → 1078，纹丝不动）。
    改成"从不同起点出发的最近邻"播种后，每匹狼都是像样的解，重组才真正产生意义。

    ★ 判定算法"到底有没有在干活"的方法（一定要自己做一遍）：
    把局部搜索关掉（ls_every=0、local_search=0）再跑一次，看终值是否仍明显优于初始解。
    如果关掉后曲线不动了 —— 那之前看到的下降全是局部搜索的功劳，你的算法是假跑。
    本项目里每个算法都过了这一关。
    """

    name = "灰狼优化 GWO"
    default_params = {
        "n_wolves": 30,
        "max_iter": 300,
        "seed": 42,
        "ls_every": 10,   # 每 N 代对 α 做一次 2-opt，并回灌到最差狼
        "ls_moves": 20,
        "mutation": 0.05, # 每匹狼的随机扰动概率（防止种群停滞）
        "step_cap": 0.4,  # 单代向单头狼靠近的最大比例（防种群坍塌，别调超过 0.6）
        "local_search": 0.3,   # 每代对多大比例的狼做一次轻量 2-opt（memetic GWO）
        "ls_trials": 20,       # 每次局部搜索随机尝试多少个 2-opt 移动
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_wolves": {"min": 5, "max": 80, "step": 1, "int": True, "label": "狼群规模", "desc": "种群大小"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "头狼改进周期", "desc": "每 N 代对 α 做一次完整 2-opt 并回灌种群；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "头狼改进预算", "desc": "每次头狼改进最多接受的 2-opt 移动数"},
        "mutation": {"min": 0.0, "max": 0.5, "step": 0.01, "label": "变异概率", "desc": "每匹狼每代随机交换两城市的概率（防停滞）"},
        "step_cap": {"min": 0.1, "max": 0.6, "step": 0.05, "label": "步幅上限", "desc": "单代向单头狼靠近的最大比例；超过 0.6 会种群坍塌"},
        "local_search": {"min": 0.0, "max": 0.8, "step": 0.05, "label": "狼群局部搜索比例", "desc": "每代多大比例的狼做轻量 2-opt；0=关闭（纯 GWO）"},
        "ls_trials": {"min": 1, "max": 60, "step": 1, "int": True, "label": "局部搜索尝试数", "desc": "每次轻量局部搜索随机尝试多少个 2-opt 移动"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_wolves = p["n_wolves"]
        if n > 80:
            n_wolves = max(15, n_wolves // 2)

        # ★ 种群初始化是离散 GWO 的生死线：
        # 全用随机排列（成本 3000+）时，等级第二、第三的 β/δ 是彻头彻尾的垃圾解，
        # 整群被往垃圾方向带，200 代下来一点没优化（实测终值 = 初始 NN 值，GWO 完全没干活）。
        # 改成"从不同起点出发的最近邻"播种：每匹狼都是像样的解，GWO 的重组才有意义。
        wolves = [nearest_neighbor(D, start=0)]
        for _ in range(n_wolves - 1):
            wolves.append(nearest_neighbor(D, start=rng.randrange(n)))
        wolves = [_random_2opt_shot(t, D, rng, trials=50) for t in wolves]
        costs = [tour_length(t, D) for t in wolves]

        order = sorted(range(len(wolves)), key=lambda i: costs[i])
        alpha, beta, delta = [list(wolves[i]) for i in order[:3]]
        a_cost, b_cost, d_cost = costs[order[0]], costs[order[1]], costs[order[2]]
        best, best_cost = list(alpha), a_cost

        for it in range(1, p["max_iter"] + 1):
            a = 2.0 * (1.0 - it / p["max_iter"])  # 收敛因子 2 → 0

            for w in range(len(wolves)):
                X = list(wolves[w])
                for leader in (alpha, beta, delta):
                    r1, r2 = rng.random(), rng.random()
                    A = 2.0 * a * r1 - a          # ∈ [-a, a]
                    C = 2.0 * r2                  # ∈ [0, 2]
                    seq = swap_seq_to_target(X, leader)
                    # ★ 关键：frac 必须设上限。若允许 frac=1，狼会整只"跳"到头狼身上，
                    # 三头狼轮流应用后所有狼都变成 δ 的复制品 → 种群坍塌（与离散 PSO 同一个坑）。
                    frac = min(p["step_cap"], abs(A) * C / 2.0)  # 靠近头狼的比例
                    k = int(len(seq) * frac)
                    if k:
                        X = apply_swaps(X, seq[:k])
                if rng.random() < p["mutation"]:
                    i, j = rng.randrange(n), rng.randrange(n)
                    X[i], X[j] = X[j], X[i]
                # memetic：让一部分狼做轻量局部搜索，否则纯重组在 TSP 上几乎不下降
                if rng.random() < p["local_search"]:
                    X = _random_2opt_shot(X, D, rng, p["ls_trials"])
                wolves[w] = X

            costs = [tour_length(t, D) for t in wolves]

            # 等级制更新：先看能否取代 α，再看 β，再看 δ（GWO 原文的社会等级）
            for i in range(len(wolves)):
                c = costs[i]
                if c < a_cost:
                    delta, d_cost = list(beta), b_cost
                    beta, b_cost = list(alpha), a_cost
                    alpha, a_cost = list(wolves[i]), c
                elif c < b_cost:
                    delta, d_cost = list(beta), b_cost
                    beta, b_cost = list(wolves[i]), c
                elif c < d_cost:
                    delta, d_cost = list(wolves[i]), c

            if a_cost < best_cost:
                best, best_cost = list(alpha), a_cost

            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    alpha = list(improved)
                    a_cost = c
                    worst = max(range(len(wolves)), key=lambda i: costs[i])  # 回灌：替换最差狼
                    wolves[worst] = list(improved)
                    costs[worst] = c

            yield IterationState(
                it,
                best_cost,
                list(best),
                sum(costs) / len(costs),
                {"a": round(a, 4), "n_wolves": len(wolves), "alpha_cost": round(a_cost, 2)},
            )


class ABC(BaseSolver):
    """人工蜂群算法 ABC（Karaboga, 2005）：雇佣蜂 + 观察蜂 + 侦察蜂三阶段。

    离散化映射：蜜源 = 一个排列；邻域算子 = 片段逆转/交换两点（TSP 上 ABC 的标准做法）。
    三个阶段的角色分工：
      雇佣蜂：对每个蜜源做一次邻域搜索，贪心保留（劣解直接丢弃）
      观察蜂：按适应度（1/(1+成本)）轮盘赌选蜜源，再邻域搜索——好解被更多开发
      侦察蜂：连续 limit 次没改进的蜜源直接丢弃，重新播种（跳出局部最优的机制）
    与 SA 的关键区别：接受准则纯贪心，跳出局部最优靠 scout 的"重置"而不是概率接受。
    """

    name = "人工蜂群 ABC"
    default_params = {
        "n_bea": 24,      # 蜜源数量（=雇佣蜂数量，观察蜂数量与之相同）
        "limit": 12,      # 蜜源连续 limit 代无改进即被侦察蜂重置
        "max_iter": 200,
        "seed": 42,
        "mutate_p": 0.5,  # 邻域搜索时选"片段逆转"的概率（否则交换两点）
        "ls_every": 5,    # 每 N 代对全局最优做一次 2-opt 并回灌（与 ACO 同款 memetic 钩子）
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_bea": {"min": 6, "max": 60, "step": 2, "int": True, "label": "蜜源数", "desc": "蜜源=雇佣蜂=观察蜂数量"},
        "limit": {"min": 3, "max": 50, "step": 1, "int": True, "label": "放弃上限 limit", "desc": "蜜源连续多少代无改进就被侦察蜂重置；太小浪费好解，太大跳不出局部最优"},
        "mutate_p": {"min": 0.0, "max": 1.0, "step": 0.05, "label": "逆转算子概率", "desc": "邻域搜索用片段逆转的概率，否则交换两点"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌种群；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def _neighbor(self, tour: List[int], D, rng, p) -> List[int]:
        t = list(tour)
        n = len(t)
        if rng.random() < p["mutate_p"]:
            a, b = sorted(rng.sample(range(n), 2))
            t[a : b + 1] = reversed(t[a : b + 1])
        else:
            i, j = rng.randrange(n), rng.randrange(n)
            t[i], t[j] = t[j], t[i]
        return t

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_bea = p["n_bea"]
        # 与 GWO/GA 同一教训：NN 多起点播种，让每个蜜源都像样
        sources = [nearest_neighbor(D, start=0)]
        for _ in range(n_bea - 1):
            sources.append(nearest_neighbor(D, start=rng.randrange(n)))
        costs = [tour_length(t, D) for t in sources]
        trials = [0] * n_bea
        bi = min(range(n_bea), key=lambda i: costs[i])
        best, best_cost = list(sources[bi]), costs[bi]

        for it in range(1, p["max_iter"] + 1):
            # —— 雇佣蜂阶段 ——
            for i in range(n_bea):
                cand = self._neighbor(sources[i], D, rng, p)
                c = tour_length(cand, D)
                if c < costs[i]:
                    sources[i], costs[i] = cand, c
                    trials[i] = 0
                else:
                    trials[i] += 1

            # —— 观察蜂阶段（按适应度轮盘赌选蜜源再开发）——
            fit = [1.0 / (1.0 + c) for c in costs]
            for _ in range(n_bea):
                i = _roulette(rng, fit)
                cand = self._neighbor(sources[i], D, rng, p)
                c = tour_length(cand, D)
                if c < costs[i]:
                    sources[i], costs[i] = cand, c
                    trials[i] = 0
                else:
                    trials[i] += 1

            # —— 侦察蜂阶段：放弃无望的蜜源，重新播种 ——
            scouts = 0
            for i in range(n_bea):
                if trials[i] >= p["limit"]:
                    t = nearest_neighbor(D, start=rng.randrange(n))
                    t = _random_2opt_shot(t, D, rng, trials=30)
                    sources[i], costs[i], trials[i] = t, tour_length(t, D), 0
                    scouts += 1

            bi = min(range(n_bea), key=lambda i: costs[i])
            if costs[bi] < best_cost:
                best, best_cost = list(sources[bi]), costs[bi]

            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    worst = max(range(n_bea), key=lambda i: costs[i])
                    sources[worst], costs[worst], trials[worst] = list(improved), c, 0

            yield IterationState(
                it, best_cost, list(best), sum(costs) / n_bea,
                {"scouts": scouts, "n_bea": n_bea},
            )


class FA(BaseSolver):
    """萤火虫算法 FA（Yang, 2008）：亮度低者向亮度高者移动。

    离散化映射（本页的核心内容）：
      亮度 I = 1/(1+路径长度)；吸引度 β = β₀·exp(-γ·r²)，r = 两排列的汉明距离占比。
      "移动" = 以 β 为比例向更亮的萤火虫靠近（取交换序列前缀，步幅有上限防坍塌）
              + α 随机扰动（交换两点）。
    与 PSO 的区别：FA 没有个体最优/全局最优记忆，是"多对多吸引"，
    亮度排序天然实现种群分层，参数少是其卖点。
    """

    name = "萤火虫算法 FA"
    default_params = {
        "n_fireflies": 20,
        "beta0": 1.0,      # 最大吸引度（r=0 时）
        "gamma": 1.0,      # 光吸收系数：大=只吸引近邻，小=全局都被吸引
        "alpha_p": 0.30,   # 随机扰动概率（每萤火虫每代，扰动=短随机 2-opt 试射）
        "alpha_trials": 8, # 每次 α 扰动的 2-opt 试射次数
        "max_iter": 200,
        "seed": 42,
        "step_cap": 0.4,   # 单次移动的最大交换比例（防种群坍塌，同 GWO 教训）
        "ls_every": 10,    # 每 N 代对最亮萤火虫做一次 2-opt 并回灌（memetic 钩子）
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_fireflies": {"min": 5, "max": 60, "step": 1, "int": True, "label": "萤火虫数", "desc": "种群规模"},
        "beta0": {"min": 0.2, "max": 2.0, "step": 0.1, "label": "最大吸引度 β₀", "desc": "距离为 0 时的吸引度"},
        "gamma": {"min": 0.0, "max": 5.0, "step": 0.1, "label": "光吸收系数 γ", "desc": "大=只有近邻互相吸引（局部搜索强），小=全局互相吸引"},
        "alpha_p": {"min": 0.0, "max": 0.5, "step": 0.01, "label": "随机扰动 α", "desc": "每萤火虫每代做一次随机扰动的概率"},
        "alpha_trials": {"min": 1, "max": 30, "step": 1, "int": True, "label": "扰动试射次数", "desc": "每次 α 扰动包含的随机 2-opt 试射次数（越大局部搜索越强）"},
        "step_cap": {"min": 0.1, "max": 0.6, "step": 0.05, "label": "步幅上限", "desc": "单次向亮者移动的最大交换比例"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对最亮萤火虫做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_f = p["n_fireflies"]
        flies = [nearest_neighbor(D, start=0)]
        for _ in range(n_f - 1):
            flies.append(nearest_neighbor(D, start=rng.randrange(n)))
        # 播种强度与 GWO 对齐（trials=50）：初始蜜火虫太弱时，前期全部预算
        # 都浪费在"从垃圾里爬出来"上（与 GWO 播种教训同源）
        flies = [_random_2opt_shot(t, D, rng, trials=50) for t in flies]
        costs = [tour_length(t, D) for t in flies]
        order0 = sorted(range(n_f), key=lambda i: costs[i])
        best, best_cost = list(flies[order0[0]]), costs[order0[0]]

        for it in range(1, p["max_iter"] + 1):
            # 亮度随迭代轻微衰减（原版 FA 的 alpha 随机性递减思想）
            alpha_t = p["alpha_p"] * (1.0 - 0.5 * it / p["max_iter"])
            brightest = min(range(n_f), key=lambda i: costs[i])

            for i in range(n_f):
                X = list(flies[i])
                if i != brightest:
                    # ★ TSP 适配 3（踩坑）：向"最亮者"全局吸引，替代原版的多对多吸引。
                    # 实测多对多方案里，向"勉强亮一点"的萤火虫做交换前缀 ≈ 随机打乱，
                    # 200 代 best 纹丝不动（725→690）。原论文 §3.2 的简化实现同样
                    # 常退化为全局最优吸引，这里是把该退化明说并做进实现。
                    diff = sum(1 for a, b in zip(X, flies[brightest]) if a != b)
                    r2 = (diff / n) ** 2
                    beta = p["beta0"] * math.exp(-p["gamma"] * r2)
                    # 交换序列从"当前 X"实时计算（从原始位置算再应用到已漂移的 X
                    # 会因果断裂——与离散 PSO 的"速度前缀"坑同族）
                    seq = swap_seq_to_target(list(X), flies[brightest])
                    k = int(len(seq) * min(p["step_cap"], beta * rng.random()))
                    if k:
                        X = apply_swaps(X, seq[:k])
                # ★ TSP 适配 2（四变体实验定案）：α 扰动 = 短随机 2-opt 试射（trials 次，贪心接受）。
                # 连续域里 α 是"随机游走步长"，落到排列域的自然实现就是一次小规模邻域搜索。
                # 四个变体实测（两实例×三种子，关局部搜索）：
                #   v1 单次贪心逆转 646-701   v2 无条件逆转 630-701
                #   v3 短2opt试射 584-667 ✅  v4 向前三亮吸引+试射 597-663
                # v3 稳定最强且实现最简。选择压力来自试射内部的贪心接受，
                # 探索能力来自逆转段的随机性——这正是 FA 原文 α 项的分工。
                if rng.random() < alpha_t:
                    X = _random_2opt_shot(X, D, rng, p["alpha_trials"])
                flies[i] = X
                flies[i] = X

            costs = [tour_length(t, D) for t in flies]
            i_best = min(range(n_f), key=lambda i: costs[i])
            if costs[i_best] < best_cost:
                best, best_cost = list(flies[i_best]), costs[i_best]

            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    worst = max(range(n_f), key=lambda i: costs[i])
                    flies[worst], costs[worst] = list(improved), c

            yield IterationState(
                it, best_cost, list(best), sum(costs) / n_f,
                {"alpha": round(alpha_t, 4), "n_fireflies": n_f},
            )


class WOA(BaseSolver):
    """鲸鱼优化算法 WOA（Mirjalili & Lewis, 2016）：包围捕食 + 螺旋气泡网 + 搜索猎物。

    离散化映射：位置 = 排列，"包围/螺旋/搜索"三种运动都翻译成交换序列的前缀应用：
      包围（|A|<1, p<0.5）：向当前最优靠近，步幅 ∝ |A|·C/2（有上限防坍塌，同 GWO 教训）
      搜索（|A|≥1, p<0.5）：远离最优随机找猎物——向随机同伴靠近，保持探索
      螺旋（p≥0.5）：气泡网收缩，交换比例随 l 与螺旋常数 b 变化，模拟螺旋上升
    论文里的 WOA 是连续算法，本页展示的就是"连续算法离散化"的完整过程。
    """

    name = "鲸鱼优化 WOA"
    default_params = {
        "n_whales": 25,
        "b_spiral": 1.0,   # 螺旋常数
        "mutation": 0.05,  # 随机扰动概率
        "max_iter": 200,
        "seed": 42,
        "step_cap": 0.4,   # 步幅上限（防坍塌）
        "ls_every": 10,    # 每 N 代对最优做一次 2-opt 并回灌
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_whales": {"min": 5, "max": 60, "step": 1, "int": True, "label": "鲸群规模", "desc": "种群大小"},
        "b_spiral": {"min": 0.2, "max": 2.0, "step": 0.1, "label": "螺旋常数 b", "desc": "气泡网螺旋的形状；大=螺旋更展开"},
        "mutation": {"min": 0.0, "max": 0.5, "step": 0.01, "label": "变异概率", "desc": "每头鲸每代随机交换两城市的概率"},
        "step_cap": {"min": 0.1, "max": 0.6, "step": 0.05, "label": "步幅上限", "desc": "单次包围/螺旋的最大交换比例"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对最优做一次 2-opt 并回灌种群；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_w = p["n_whales"]
        whales = [nearest_neighbor(D, start=0)]
        for _ in range(n_w - 1):
            whales.append(nearest_neighbor(D, start=rng.randrange(n)))
        # 播种强度与 GWO/FA 对齐（trials=50）：这是"防假跑"底线的一部分——
        # 初始种群太弱时，前几十代全在填初始坑，动力学没机会表现
        whales = [_random_2opt_shot(t, D, rng, trials=50) for t in whales]
        costs = [tour_length(t, D) for t in whales]
        o = sorted(range(n_w), key=lambda i: costs[i])
        best, best_cost = list(whales[o[0]]), costs[o[0]]

        for it in range(1, p["max_iter"] + 1):
            a = 2.0 * (1.0 - it / p["max_iter"])  # 收敛因子 2 → 0

            for w in range(n_w):
                X = list(whales[w])
                r1, r2 = rng.random(), rng.random()
                A = 2.0 * a * r1 - a
                C = 2.0 * r2
                l = rng.uniform(-1.0, 1.0)
                if rng.random() < 0.5:
                    if abs(A) < 1.0:
                        # 包围捕食：向当前最优靠近
                        seq = swap_seq_to_target(list(whales[w]), best)
                        frac = min(p["step_cap"], abs(A) * C / 2.0)
                    else:
                        # 搜索猎物：向随机同伴靠近（探索）
                        j = rng.randrange(n_w)
                        seq = swap_seq_to_target(list(whales[w]), whales[j])
                        frac = min(p["step_cap"], abs(A) * C / 4.0)
                    k = int(len(seq) * frac)
                    if k:
                        X = apply_swaps(X, seq[:k])
                else:
                    # 螺旋气泡网：交换比例 = e^(b·l) 归一化后收缩
                    spiral = min(1.0, math.exp(p["b_spiral"] * l) / (math.e ** p["b_spiral"]))
                    seq = swap_seq_to_target(list(whales[w]), best)
                    k = int(len(seq) * min(p["step_cap"], spiral))
                    if k:
                        X = apply_swaps(X, seq[:k])
                if rng.random() < p["mutation"]:
                    i, j = rng.randrange(n), rng.randrange(n)
                    X[i], X[j] = X[j], X[i]
                whales[w] = X

            costs = [tour_length(t, D) for t in whales]
            i_b = min(range(n_w), key=lambda i: costs[i])
            if costs[i_b] < best_cost:
                best, best_cost = list(whales[i_b]), costs[i_b]

            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    worst = max(range(n_w), key=lambda i: costs[i])
                    whales[worst], costs[worst] = list(improved), c

            yield IterationState(
                it, best_cost, list(best), sum(costs) / n_w,
                {"a": round(a, 4), "n_whales": n_w},
            )


class TabuSearch(BaseSolver):
    """禁忌搜索 TS（Glover, 1986）：带"禁忌表"的局部搜索。

    与 SA / 2-opt 的本质区别：每代在采样的邻域里选【最好的许可移动】——
    即使它让当前解变差也照样走（这是 TS 跳出局部最优的机制），
    刚走过的移动在禁忌期内不许反悔（防止原地打转），
    但如果某个禁忌移动能刷新历史最优，特事特办放行（特赦准则 / aspiration）。
    引用量级：Glover 的 TS 系列论文合计引用数万次，是元启发式的奠基工作之一。
    """

    name = "禁忌搜索 TS"
    default_params = {
        "tabu_tenure": 8,   # 禁忌期：一个移动被禁多少代
        "samples": 60,      # 每代采样多少个 2-opt 邻居（全邻域 O(n^2) 浏览器跑不动）
        "max_iter": 200,
        "seed": 42,
    }
    implemented = True
    category = "局部搜索"
    param_specs = {
        "tabu_tenure": {"min": 1, "max": 30, "step": 1, "int": True, "label": "禁忌期", "desc": "一个移动被执行后被禁忌的代数；太短原地打转，太长搜索受限"},
        "samples": {"min": 10, "max": 200, "step": 10, "int": True, "label": "邻域采样数", "desc": "每代随机采样多少个候选移动再挑最好的"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        tour = nearest_neighbor(D)
        cost = tour_length(tour, D)
        best, best_cost = list(tour), cost
        tabu: Dict[Tuple[int, int], int] = {}
        tenure = p["tabu_tenure"]

        yield IterationState(0, cost, list(tour), cost, {"note": "初始解", "tabu_size": 0})

        for it in range(1, p["max_iter"] + 1):
            best_move: Optional[Tuple[int, int, float]] = None
            for _ in range(p["samples"]):
                i = rng.randrange(1, n - 1)
                k = rng.randrange(i + 1, n)
                mv = (i, k)
                delta = D[tour[i - 1]][tour[k]] + D[tour[i]][tour[(k + 1) % n]] - D[tour[i - 1]][tour[i]] - D[tour[k]][tour[(k + 1) % n]]
                in_tabu = tabu.get(mv, 0) > it or tabu.get((k, i), 0) > it
                # 特赦准则：禁忌移动若能刷新历史最优，放行
                if in_tabu and not (cost + delta < best_cost - 1e-12):
                    continue
                if best_move is None or delta < best_move[2]:
                    best_move = (i, k, delta)
            if best_move is None:
                break
            i, k, delta = best_move
            tour[i : k + 1] = reversed(tour[i : k + 1])
            cost += delta
            tabu[(i, k)] = it + tenure
            tabu[(k, i)] = it + tenure
            if it % 100 == 0:
                cost = tour_length(tour, D)  # 增量累加会飘，周期性重算兜底（同 SA）
            if cost < best_cost:
                best, best_cost = list(tour), cost
            yield IterationState(
                it, best_cost, list(best), cost,
                {"tabu_size": len(tabu) // 2, "last_delta": round(delta, 2),
                 "worsening": delta > 1e-9},
            )


class DifferentialEvolution(BaseSolver):
    """差分进化 DE（Storn & Price, 1997）：用"种群内差异"驱动搜索。

    DE 是引用量最大的元启发式之一（原始论文数万次引用），核心只有一条公式：
        变异体 = x_r1 + F · (x_r2 − x_r3)
    差向量 (x_r2 − x_r3) 自动让步长适配种群当前的分散程度——后期收敛步长自然变小。

    离散化映射（TSP 版）：
      "差向量" = 把 r2 变到 r3 所需的交换序列（两点间的差异在排列域就是一串交换）；
      变异策略用 DE/current-to-best（向当前最优靠近 + 一对差分扰动）；
      交叉 = 以概率 CR 用 OX 顺序交叉把变异体与 x_i 杂交得 trial；
      选择 = trial 与 x_i 贪心二选一（DE 的经典贪心选择）。

    ★ 踩坑记录（与 GWO 假跑事件同源，变体矩阵实验见 tools/de_variant_experiment.py）：
    第一版用教科书 DE/rand/1 + CR=0.9 的 OX 交叉——实测 200 代进步 0.0%，
    及格线全部来自 NN 播种初始化（1 代和 200 代终值一模一样：685→685），纯假跑。
    根因：OX 交叉在两个都已被 2-opt 打磨过的父本上破坏性太强（重组出来的边
    大部分是拼接噪声），贪心选择 200 代一次都没接受过新解。
    五组变体实验（60 城市 × 3 种子）结论：
      rand1    + CR=0.2 + polish 0.3/10   最差真实进步 3.2%
      cur2best + CR=0.2 + polish 0.3/10   最差真实进步 3.8% ✅（定案）
    current-to-best 让 trial 始终围绕好解的邻域生成，配合低 CR 减少交叉破坏，
    这是排列域上 DE 能真实干活的最小改动。
    """

    name = "差分进化 DE"
    default_params = {
        "n_pop": 30,
        "F": 0.6,         # 差分缩放因子
        "CR": 0.2,        # 交叉概率（排列域上要低——OX 交叉破坏性强，见踩坑记录）
        "max_iter": 200,
        "seed": 42,
        "step_cap": 0.6,  # F 的实际执行上限（防坍塌，同 GWO 教训）
        "mutation": 0.02, # 随机扰动概率
        "polish_p": 0.3,  # 内部打磨概率：以小概率对 trial 做短 2-opt 试射（memetic DE 的轻量版）
        "polish_trials": 10,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "进化计算"
    param_specs = {
        "n_pop": {"min": 6, "max": 60, "step": 2, "int": True, "label": "种群规模", "desc": "种群大小（大实例自动降配）"},
        "F": {"min": 0.1, "max": 1.0, "step": 0.05, "label": "缩放因子 F", "desc": "差分变异的步长比例；太小收敛慢，太大不收敛"},
        "CR": {"min": 0.0, "max": 1.0, "step": 0.05, "label": "交叉概率 CR", "desc": "变异体与父代做 OX 交叉的概率；排列域上建议 0.2 左右（交叉破坏性强，见实现注释）"},
        "step_cap": {"min": 0.1, "max": 0.6, "step": 0.05, "label": "步幅上限", "desc": "单次差分变异执行交换前缀的最大比例"},
        "mutation": {"min": 0.0, "max": 0.2, "step": 0.01, "label": "扰动概率", "desc": "每个个体每代随机交换两城市的概率"},
        "polish_p": {"min": 0.0, "max": 0.5, "step": 0.05, "label": "打磨概率", "desc": "对每个新 trial 做短 2-opt 试射的概率（memetic DE 组件）"},
        "polish_trials": {"min": 1, "max": 30, "step": 1, "int": True, "label": "打磨试射次数", "desc": "每次打磨包含的随机 2-opt 试射次数"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_pop = p["n_pop"]
        if n > 80:
            n_pop = max(10, n_pop // 2)
        pop = [nearest_neighbor(D, start=0)]
        for _ in range(n_pop - 1):
            pop.append(nearest_neighbor(D, start=rng.randrange(n)))
        pop = [_random_2opt_shot(t, D, rng, trials=50) for t in pop]
        costs = [tour_length(t, D) for t in pop]
        i0 = min(range(n_pop), key=lambda i: costs[i])
        best, best_cost = list(pop[i0]), costs[i0]

        for it in range(1, p["max_iter"] + 1):
            improved_cnt = 0
            for i in range(n_pop):
                # DE/current-to-best：向当前最优靠近 + 一对差分扰动（见类注释的踩坑记录）
                idxs = [j for j in range(n_pop) if j != i]
                r1, r2 = rng.sample(idxs, 2)
                seq = swap_seq_to_target(list(pop[i]), best) + swap_seq_to_target(list(pop[r1]), pop[r2])
                mutant = list(pop[i])
                k = int(len(seq) * min(p["step_cap"], p["F"] * (0.5 + rng.random())))
                if k:
                    mutant = apply_swaps(mutant, seq[:k])
                # 交叉：以概率 CR 与父本做 OX 顺序交叉
                if rng.random() < p["CR"]:
                    trial = _ox_crossover(mutant, pop[i], rng)
                else:
                    trial = mutant
                if rng.random() < p["mutation"]:
                    i_, j_ = rng.randrange(n), rng.randrange(n)
                    trial[i_], trial[j_] = trial[j_], trial[i_]
                # 内部打磨（memetic DE 的轻量版）：连续域里 DE 靠差向量自适应步长，
                # 排列域上纯交换重组的下降能力有限，以小概率做短 2-opt 试射补足
                # 开发能力——与 FA 的 α 扰动（v3 定案）同一设计思想。
                if rng.random() < p["polish_p"]:
                    trial = _random_2opt_shot(trial, D, rng, p["polish_trials"])
                # 贪心选择（DE 的标志性一步）
                c = tour_length(trial, D)
                if c < costs[i]:
                    pop[i], costs[i] = trial, c
                    improved_cnt += 1
                    if c < best_cost:
                        best, best_cost = list(trial), c
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    worst = max(range(n_pop), key=lambda i_: costs[i_])
                    pop[worst], costs[worst] = list(improved), c
            yield IterationState(
                it, best_cost, list(best), sum(costs) / n_pop,
                {"F": p["F"], "n_pop": n_pop, "improved": improved_cnt},
            )


class CuckooSearch(BaseSolver):
    """布谷鸟搜索 CS（Yang & Deb, 2009）：莱维飞行 + 随机弃巢。

    引用量级：原始论文 1 万次以上，"莱维飞行"是它最大的招牌——
    步长分布重尾：绝大多数步子很小，偶尔来一步超大的（幂律分布）。
    生物学故事是布谷鸟把蛋下在别的鸟窝里；数学内核是莱维飞行随机游走。

    离散化映射：
      一个蛋/鸟窝 = 一个排列；
      莱维飞行的"小步" = 少量短 2-opt 试射；"偶发大步" = 长片段逆转（跨度 ~ n·levy/4）；
      发现外来蛋（概率 pa）= 丢弃最差的一部分鸟窝、重新播种。
    """

    name = "布谷鸟搜索 CS"
    default_params = {
        "n_nests": 20,
        "pa": 0.25,        # 弃巢比例
        "alpha": 0.3,      # 莱维步长基数
        "levy_beta": 1.5,  # 莱维指数（1~3，越小重尾越明显）
        "max_iter": 200,
        "seed": 42,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_nests": {"min": 5, "max": 50, "step": 1, "int": True, "label": "鸟窝数", "desc": "种群规模"},
        "pa": {"min": 0.05, "max": 0.5, "step": 0.05, "label": "弃巢比例 pa", "desc": "每代被随机发现并重新播种的最差鸟窝比例"},
        "alpha": {"min": 0.05, "max": 1.0, "step": 0.05, "label": "步长基数 α", "desc": "莱维飞行的整体步长基数"},
        "levy_beta": {"min": 1.0, "max": 3.0, "step": 0.1, "label": "莱维指数", "desc": "越小步长分布越重尾（偶发大步越频繁）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def _levy_move(self, tour: List[int], D, rng, p) -> List[int]:
        """莱维飞行的排列域实现：小步=短 2-opt 试射；偶发大步=长片段逆转"""
        levy = rng.paretovariate(max(1.01, p["levy_beta"]))
        if levy > 2.5:
            # 偶发大步：重尾分布的核心价值——一跨越局部盆地
            L = max(2, min(int(len(tour) * p["alpha"] * levy / 6), len(tour) - 2))
            i = rng.randrange(1, len(tour) - L)
            X = list(tour)
            X[i : i + L] = reversed(X[i : i + L])
            return X if tour_length(X, D) < tour_length(tour, D) else list(tour)
        # 小步：alpha 缩放的短 2-opt 试射
        trials = max(1, min(int(p["alpha"] * levy * 30), 40))
        return _random_2opt_shot(tour, D, rng, trials)

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_nests = p["n_nests"]
        if n > 80:
            n_nests = max(10, n_nests // 2)
        nests = [nearest_neighbor(D, start=0)]
        for _ in range(n_nests - 1):
            nests.append(nearest_neighbor(D, start=rng.randrange(n)))
        nests = [_random_2opt_shot(t, D, rng, trials=50) for t in nests]
        costs = [tour_length(t, D) for t in nests]
        i0 = min(range(n_nests), key=lambda i: costs[i])
        best, best_cost = list(nests[i0]), costs[i0]

        for it in range(1, p["max_iter"] + 1):
            # 布谷鸟阶段：每只布谷鸟借一个鸟窝出发做莱维飞行，蛋更优则占巢
            for _ in range(n_nests):
                j = rng.randrange(n_nests)
                egg = self._levy_move(nests[j], D, rng, p)
                c = tour_length(egg, D)
                if c < costs[j]:
                    nests[j], costs[j] = egg, c
                    if c < best_cost:
                        best, best_cost = list(egg), c
            # 弃巢阶段：最差 pa 比例的鸟窝被发现，重新播种（保持多样性）
            n_abandon = max(1, int(n_nests * p["pa"]))
            order = sorted(range(n_nests), key=lambda i: costs[i], reverse=True)
            for idx in order[:n_abandon]:
                fresh = nearest_neighbor(D, start=rng.randrange(n))
                fresh = _random_2opt_shot(fresh, D, rng, trials=20)
                nests[idx], costs[idx] = fresh, tour_length(fresh, D)
            i_b = min(range(n_nests), key=lambda i: costs[i])
            if costs[i_b] < best_cost:
                best, best_cost = list(nests[i_b]), costs[i_b]
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    worst = max(range(n_nests), key=lambda i: costs[i])
                    nests[worst], costs[worst] = list(improved), c
            yield IterationState(
                it, best_cost, list(best), sum(costs) / n_nests,
                {"pa": p["pa"], "n_nests": n_nests},
            )


class SineCosine(BaseSolver):
    """正弦余弦算法 SCA（Mirjalili, 2016）：用正弦/余弦振荡包围最优解。

    引用量级：原始论文数千次，Mirjalili 系（GWO/WOA/SCA）的代表作品之一。
    核心公式：X = X + r1·sin(r2)·|r3·P − X|（r4<0.5 取 sin，否则取 cos）。
    r1 线性衰减 2→0：前期振荡大（全局探索），后期振荡小（局部开发）；
    sin/cos 的正负交替天然产生"往返包围"的运动轨迹。

    离散化映射：
      |r3·P − X| = 向最优解 P 的交换序列长度；步幅 = r1·|sin(r2)| 或 r1·|cos(r2)|（有上限）；
      sin/cos 为负 = "反向振荡" = 向随机同伴靠近（探索），
      这是往返包围在排列域里能自洽落地的等价物。
    """

    name = "正弦余弦 SCA"
    default_params = {
        "n_agents": 25,
        "a0": 2.0,        # r1 初值（线性衰减到 0）
        "mutation": 0.05,
        "max_iter": 200,
        "seed": 42,
        "step_cap": 0.4,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "数学启发"
    param_specs = {
        "n_agents": {"min": 5, "max": 60, "step": 1, "int": True, "label": "个体数", "desc": "种群规模"},
        "a0": {"min": 1.0, "max": 3.0, "step": 0.1, "label": "r1 初值", "desc": "振荡幅度的初值，线性衰减到 0"},
        "mutation": {"min": 0.0, "max": 0.3, "step": 0.01, "label": "扰动概率", "desc": "每个体每代随机交换两城市的概率"},
        "step_cap": {"min": 0.1, "max": 0.6, "step": 0.05, "label": "步幅上限", "desc": "单次振荡执行交换前缀的最大比例"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_a = p["n_agents"]
        if n > 80:
            n_a = max(10, n_a // 2)
        agents = [nearest_neighbor(D, start=0)]
        for _ in range(n_a - 1):
            agents.append(nearest_neighbor(D, start=rng.randrange(n)))
        agents = [_random_2opt_shot(t, D, rng, trials=50) for t in agents]
        costs = [tour_length(t, D) for t in agents]
        i0 = min(range(n_a), key=lambda i: costs[i])
        best, best_cost = list(agents[i0]), costs[i0]

        for it in range(1, p["max_iter"] + 1):
            r1 = p["a0"] * (1.0 - it / p["max_iter"])
            for i in range(n_a):
                X = list(agents[i])
                r2 = rng.uniform(0, 2 * math.pi)
                r4 = rng.random()
                osc = abs(math.sin(r2)) if r4 < 0.5 else abs(math.cos(r2))
                frac = min(p["step_cap"], r1 * osc)
                if math.sin(r2) >= 0.0:
                    # 正向振荡：向最优解收缩
                    seq = swap_seq_to_target(list(X), best)
                    k = int(len(seq) * frac)
                    if k:
                        X = apply_swaps(X, seq[:k])
                else:
                    # 反向振荡：向随机同伴靠近（把"远离最优"落成"换个方向"，
                    # 直接远离会退化成随机打乱——同 FA 多对多的教训）
                    if n_a > 1:
                        j = rng.randrange(n_a)
                        seq = swap_seq_to_target(list(X), agents[j])
                        k = int(len(seq) * frac * 0.5)
                        if k:
                            X = apply_swaps(X, seq[:k])
                if rng.random() < p["mutation"]:
                    i_, j_ = rng.randrange(n), rng.randrange(n)
                    X[i_], X[j_] = X[j_], X[i_]
                if rng.random() < 0.3:
                    X = _random_2opt_shot(X, D, rng, 8)
                agents[i] = X
            costs = [tour_length(t, D) for t in agents]
            i_b = min(range(n_a), key=lambda i: costs[i])
            if costs[i_b] < best_cost:
                best, best_cost = list(agents[i_b]), costs[i_b]
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    worst = max(range(n_a), key=lambda i: costs[i])
                    agents[worst], costs[worst] = list(improved), c
            yield IterationState(
                it, best_cost, list(best), sum(costs) / n_a,
                {"r1": round(r1, 4), "n_agents": n_a},
            )


class HarrisHawks(BaseSolver):
    """哈里斯鹰优化 HHO（Heidari et al., 2019）：逃逸能量驱动的捕猎策略切换。

    引用量级：原始论文上万次，是 2019 年后引用增长最快的元启发式之一。
    核心机制：猎物（兔子）的"逃逸能量" E 随迭代从 2 衰减到 0；
      |E|≥1 探索（猎物还在挣扎，鹰群大范围搜索）；
      |E|<1 开发（包围），按逃跑概率 r 分软/硬包围，
      进攻失败时切换莱维俯冲（重尾随机步）。

    离散化映射：
      软包围 = 以 |E|·步幅上限 的比例向最优解（兔子）靠近；
      硬包围 = 步幅再减半（包围圈收紧）；
      莱维俯冲 = 俯冲失败（没改进）就做一次短 2-opt 试射 + 小概率长片段逆转；
      探索 = 在两只随机同伴中挑好的靠近（配合 NN 播种）。
    """

    name = "哈里斯鹰 HHO"
    default_params = {
        "n_hawks": 25,
        "dive_p": 0.4,    # 莱维俯冲触发概率
        "mutation": 0.05,
        "max_iter": 200,
        "seed": 42,
        "step_cap": 0.4,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_hawks": {"min": 5, "max": 60, "step": 1, "int": True, "label": "鹰群规模", "desc": "种群规模"},
        "dive_p": {"min": 0.0, "max": 1.0, "step": 0.05, "label": "俯冲概率", "desc": "进攻阶段触发莱维俯冲（短 2-opt 试射）的概率"},
        "mutation": {"min": 0.0, "max": 0.3, "step": 0.01, "label": "扰动概率", "desc": "每只鹰每代随机交换两城市的概率"},
        "step_cap": {"min": 0.1, "max": 0.6, "step": 0.05, "label": "步幅上限", "desc": "单次包围移动执行交换前缀的最大比例"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def _levy_dive(self, X: List[int], D, rng, n: int) -> List[int]:
        """莱维俯冲：短 2-opt 试射为主，偶发长片段逆转（重尾步长）"""
        Y = _random_2opt_shot(X, D, rng, 10)
        if rng.random() < 0.2:
            L = max(2, int(n * rng.random() * 0.25))
            i = rng.randrange(1, n - L)
            Z = list(Y)
            Z[i : i + L] = reversed(Z[i : i + L])
            if tour_length(Z, D) < tour_length(Y, D):
                Y = Z
        return Y

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_h = p["n_hawks"]
        if n > 80:
            n_h = max(10, n_h // 2)
        hawks = [nearest_neighbor(D, start=0)]
        for _ in range(n_h - 1):
            hawks.append(nearest_neighbor(D, start=rng.randrange(n)))
        hawks = [_random_2opt_shot(t, D, rng, trials=50) for t in hawks]
        costs = [tour_length(t, D) for t in hawks]
        i0 = min(range(n_h), key=lambda i: costs[i])
        rabbit, rabbit_cost = list(hawks[i0]), costs[i0]
        best, best_cost = list(rabbit), rabbit_cost

        for it in range(1, p["max_iter"] + 1):
            E0 = 2.0 * (1.0 - it / p["max_iter"])  # 逃逸能量 2 → 0
            for i in range(n_h):
                X = list(hawks[i])
                if abs(E0) >= 1.0:
                    # ===== 探索阶段：猎物还在挣扎，鹰群大范围搜索 =====
                    j, k = rng.sample(range(n_h), 2) if n_h > 1 else (0, 0)
                    # 在两只随机同伴中挑好的靠近（原论文的"随机栖息地二选一"）
                    if costs[j] <= costs[k]:
                        seq = swap_seq_to_target(list(X), hawks[j])
                    else:
                        seq = swap_seq_to_target(list(X), hawks[k])
                    kk = int(len(seq) * min(p["step_cap"], rng.random()))
                    if kk:
                        X = apply_swaps(X, seq[:kk])
                else:
                    # ===== 开发阶段：软/硬包围 + 莱维俯冲 =====
                    r = rng.random()  # 猎物逃跑概率
                    before = tour_length(X, D)
                    frac = min(p["step_cap"], abs(E0) * (1.0 if r >= 0.5 else 0.5))
                    seq = swap_seq_to_target(list(X), rabbit)
                    kk = int(len(seq) * frac)
                    if kk:
                        X = apply_swaps(X, seq[:kk])
                    # 俯冲：进攻没占到便宜就切换莱维俯冲（原论文 Fuzz 行为）
                    if rng.random() < p["dive_p"] or tour_length(X, D) >= before:
                        X = self._levy_dive(X, D, rng, n)
                if rng.random() < p["mutation"]:
                    i_, j_ = rng.randrange(n), rng.randrange(n)
                    X[i_], X[j_] = X[j_], X[i_]
                hawks[i] = X
            costs = [tour_length(t, D) for t in hawks]
            i_b = min(range(n_h), key=lambda i: costs[i])
            if costs[i_b] < rabbit_cost:
                rabbit, rabbit_cost = list(hawks[i_b]), costs[i_b]
                if rabbit_cost < best_cost:
                    best, best_cost = list(rabbit), rabbit_cost
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    rabbit, rabbit_cost = list(improved), c
                    worst = max(range(n_h), key=lambda i: costs[i])
                    hawks[worst], costs[worst] = list(improved), c
            yield IterationState(
                it, best_cost, list(best), sum(costs) / n_h,
                {"E": round(E0, 4), "n_hawks": n_h},
            )


# ============================ 已实现：局部搜索框架 ============================


class IteratedLocalSearch(BaseSolver):
    """迭代局部搜索 ILS（Lourenço, Martin & Stützle, 2003）：扰动 + 下探 + 接受准则。

    引用量级：1 万次以上，工业界用得最多的元启发式框架——LKH 求解器的骨架。
    它的洞察很朴素：单点局部搜索必然卡死在局部最优，那就
    「下探到局部最优 → 用受控扰动踢出去 → 再下探 → 挑好的留下」循环往复。

    离散化映射（TSP 版）：
      下探 = 2-opt 局部搜索（预算制）；扰动 = 双桥（2-opt 无法一步还原的踢法）；
      接受准则 = better（只认改进）或 restart（连续多次无改进就从 NN 重来）。
    """

    name = "迭代局部搜索 ILS"
    default_params = {
        "max_iter": 200,
        "perturb": 1,      # 每次扰动连踢几脚（双桥次数）
        "descend": 30,     # 每次下探的 2-opt 移动预算
        "accept": "better",  # better=只接受改进；restart=无改进 N 代重启
        "patience": 30,    # restart 模式下的容忍代数
        "seed": 42,
    }
    implemented = True
    category = "局部搜索"
    param_specs = {
        "perturb": {"min": 1, "max": 5, "step": 1, "int": True, "label": "扰动强度", "desc": "每次扰动连踢几脚双桥（越多踢得越远）"},
        "descend": {"min": 5, "max": 100, "step": 5, "int": True, "label": "下探预算", "desc": "每次下探最多执行的 2-opt 移动数"},
        "accept": {"type": "choice", "options": ["better", "restart"], "labels": ["只认改进", "无改进重启"], "label": "接受准则", "desc": "扰动后比当前差时怎么办"},
        "patience": {"min": 5, "max": 80, "step": 5, "int": True, "label": "容忍代数", "desc": "restart 模式：连续 N 代无改进就从最近邻重新构造"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        tour = two_opt_improve(nearest_neighbor(D), D, max_moves=500)
        best, best_cost = list(tour), tour_length(tour, D)
        cur_cost = best_cost
        no_improve = 0
        yield IterationState(0, best_cost, list(best), cur_cost, {"note": "初始解 = NN + 完整 2-opt"})

        for it in range(1, p["max_iter"] + 1):
            # 扰动：连踢 perturb 脚双桥
            kicked = list(tour)
            for _ in range(p["perturb"]):
                kicked = _double_bridge(kicked, rng)
            # 下探：预算制 2-opt
            cand = two_opt_improve(kicked, D, max_moves=p["descend"])
            c = tour_length(cand, D)
            note = ""
            if c < cur_cost:
                tour, cur_cost = cand, c
                note = f"改进 {cur_cost:.1f}"
            elif c == cur_cost:
                note = "持平保留"
            elif p["accept"] == "restart":
                no_improve += 1
                note = f"变差，容忍 {no_improve}/{p['patience']}"
                if no_improve >= p["patience"]:
                    tour = nearest_neighbor(D, start=rng.randrange(n))
                    tour = two_opt_improve(tour, D, max_moves=p["descend"])
                    cur_cost = tour_length(tour, D)
                    no_improve = 0
                    note = "重启：从 NN 重新构造"
            else:
                # better 模式：回到当前解（扰动结果直接丢弃）
                note = "变差丢弃"
            if cur_cost < best_cost:
                best, best_cost = list(tour), cur_cost
                no_improve = 0
            yield IterationState(it, best_cost, list(best), cur_cost, {"note": note})


class VariableNeighborhoodSearch(BaseSolver):
    """变邻域搜索 VNS（Mladenović & Hansen, 1997）：局部最优卡住就换邻域。

    引用量级：1 万次以上，与 TS、ILS 并列的三大局部搜索框架。
    核心思想：一个解在 2-opt 邻域里是最优，换到 or-opt 邻域、双桥邻域里
    未必最优——「在更远的邻域里扰动（shake），在近邻域里下探，
    下探有进步就回到第一层邻域，没进步就换下一层」。

    离散化映射（TSP 版，三层邻域）：
      k=1 双桥 shake（最远）；k=2 or-opt 摘段重插；k=3 双重交换；
      下探 = 预算制 2-opt。VNS 的 shake 步长随 k 递增，天然平衡探索/开发。
    """

    name = "变邻域搜索 VNS"
    default_params = {
        "max_iter": 200,
        "k_max": 3,        # 邻域层数
        "descend": 25,     # 每次下探的 2-opt 移动预算
        "or_seg": 3,       # or-opt 段长上限
        "seed": 42,
    }
    implemented = True
    category = "局部搜索"
    param_specs = {
        "k_max": {"min": 2, "max": 4, "step": 1, "int": True, "label": "邻域层数", "desc": "shake 邻域的层数（越大探索越远）"},
        "descend": {"min": 5, "max": 100, "step": 5, "int": True, "label": "下探预算", "desc": "每次下探最多执行的 2-opt 移动数"},
        "or_seg": {"min": 1, "max": 5, "step": 1, "int": True, "label": "or-opt 段长", "desc": "第二层邻域摘下重插的连续城市段长上限"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        tour = two_opt_improve(nearest_neighbor(D), D, max_moves=500)
        best, best_cost = list(tour), tour_length(tour, D)
        cur_cost = best_cost
        k = 1
        yield IterationState(0, best_cost, list(best), cur_cost, {"k": 1, "note": "初始解 = NN + 完整 2-opt"})

        for it in range(1, p["max_iter"] + 1):
            # shake：在第 k 层邻域里随机扰动
            if k == 1:
                shaken = _double_bridge(tour, rng)
            elif k == 2:
                shaken = _or_opt_move(tour, rng, rng.randint(1, p["or_seg"]))
            else:
                shaken = _double_bridge(_double_bridge(tour, rng), rng)
            # 下探：预算制 2-opt
            cand = two_opt_improve(shaken, D, max_moves=p["descend"])
            c = tour_length(cand, D)
            note = ""
            if c < cur_cost:
                tour, cur_cost = cand, c
                k = 1  # 有进步就回到第一层
                note = f"改进 {cur_cost:.1f}，回到 k=1"
            else:
                k = k % p["k_max"] + 1  # 没进步换下一层邻域
                note = f"无进步，换邻域 k={k}"
            if cur_cost < best_cost:
                best, best_cost = list(tour), cur_cost
            yield IterationState(it, best_cost, list(best), cur_cost, {"k": k, "note": note})


class LinKernighan(BaseSolver):
    """Lin–Kernighan（Lin & Kernighan, 1973）：变深度边交换，TSP 专用求解器巅峰之作。

    引用量级：数万次，50 年过去仍是 TSP 求解器（LKH/Concorde）的核心引擎。
    它和 2-opt 的本质区别：2-opt 只接受「单步变好」的交换，卡死在局部最优；
    LK 允许链式交换中「个别步暂时变差」，只要整条链的累计增益为负（变好）
    就采纳——「先下坡再上更高的山」的搜索由变深度机制显式支持。

    本实现的简化版（随机化 LK 变体）：
      每一轮 pass：贪心链式执行 2-opt 交换（每步选当前最优的断裂点，
      同一断裂点本轮不再复用），记录链上累计增益最优的那个中间状态；
      pass 结束时若最优累计增益 < 0（即有净改进）则采纳。
      深度上限 + 每步只抽样部分候选位（don't-look 思想）控制耗时。
    """

    name = "Lin–Kernighan LK"
    default_params = {
        "max_iter": 200,
        "depth": 10,       # 单次 pass 的链深上限
        "sample": 40,      # 每步抽样的候选断裂点数（don't-look）
        "kick_every": 10,  # 每 N 代卡死时踢一脚双桥；0=关闭
        "seed": 42,
    }
    implemented = True
    category = "局部搜索"
    param_specs = {
        "depth": {"min": 2, "max": 12, "step": 1, "int": True, "label": "链深上限", "desc": "单次 pass 最多链式执行几次交换（变深度搜索的核心参数）"},
        "sample": {"min": 5, "max": 80, "step": 5, "int": True, "label": "抽样数", "desc": "每步抽样的候选断裂点数（越大越精细越慢）"},
        "kick_every": {"min": 0, "max": 100, "step": 5, "int": True, "label": "踢桥周期", "desc": "每 N 代无改进就踢一脚双桥跳出局部盆地；0=关闭"},
    }

    def _lk_pass(self, tour: List[int], D, rng, max_depth: int, sample: int):
        """一次变深度 pass：贪心链式交换（允许链中暂时变差），返回最优累计中间态。

        ★LK 的本体不在"做 2-opt"，而在"允许链中个别步变差、按累计增益收官"：
        每步在抽样断裂点里选 delta 最小的交换（含正 delta——先下坡再上高山），
        链上维护累计增益 cum，记录 cum 最小的中间状态；pass 结束时若最优
        cum < 0（净改进）才采纳。used 集合防同一断裂点复用（防原地打转）。
        """
        n = len(tour)
        t = list(tour)
        base = tour_length(t, D)
        cum = 0.0
        best_cum = 0.0
        best_t = None
        used: set = set()
        for _ in range(max_depth):
            best_move = None
            best_delta = None
            for _ in range(sample):
                i = rng.randrange(0, n - 1)
                if i in used:
                    continue
                # 全 k 扫描（steepest）：只扫 i+2/i+3 两档会退化成残废 2-opt（实测教训）
                for k in range(i + 2, n):
                    a, b, c, d = t[i - 1], t[i], t[k], t[(k + 1) % n]
                    delta = (D[a][c] + D[b][d]) - (D[a][b] + D[c][d])
                    if best_delta is None or delta < best_delta:
                        best_delta = delta
                        best_move = (i, k)
            if best_move is None:
                break
            i, k = best_move
            t[i : k + 1] = reversed(t[i : k + 1])
            cum += best_delta
            used.add(i)
            if cum < best_cum:
                best_cum = cum
                best_t = list(t)
        return best_t, best_cum, base

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        rng = random.Random(p["seed"])

        tour = nearest_neighbor(D)
        best, best_cost = list(tour), tour_length(tour, D)
        cur_cost = best_cost
        no_improve = 0
        # 铁手走查 P1（2026-09-27）：删去初始态 yield——其他 44 个算法都是
        # max_iter 个态（for it in range(1, T+1)），唯 LK 多吐一个 it=0 初始态，
        # 迭代计数 off-by-one 污染横评口径（50 代请求实收 51 态）。

        for it in range(1, p["max_iter"] + 1):
            new_t, cum, _ = self._lk_pass(tour, D, rng, p["depth"], p["sample"])
            note = ""
            if new_t is not None:
                tour = new_t
                cur_cost = tour_length(tour, D)
                note = f"链采纳，累计增益 {cum:.1f}"
            else:
                note = "本 pass 无净改进"
            if cur_cost < best_cost:
                best, best_cost = list(tour), cur_cost
                no_improve = 0
            else:
                no_improve += 1
                if p["kick_every"] > 0 and no_improve >= p["kick_every"]:
                    tour = _double_bridge(tour, rng)
                    cur_cost = tour_length(tour, D)
                    no_improve = 0
                    note = "卡死 → 双桥踢出局部盆地"
            yield IterationState(it, best_cost, list(best), cur_cost, {"note": note})


# ============================ 已实现：群智能补全（第二批） ============================


class BatAlgorithm(BaseSolver):
    """蝙蝠算法 BA（Yang, 2010）：频率调谐 + 脉冲发射 + 响度衰减。

    引用量级：1 万次以上，Yang 系（FA/CS/BA）里被引最高的作品之一。
    生物学故事是蝙蝠回声定位捕猎：靠近猎物时降低响度、提高发射频率。

    离散化映射（TSP 版）：
      频率 f ∈ [fmin, fmax] = 向全局最优移动的步幅基数（交换序列前缀比例）；
      响度 A = 随机游走的步长（短 2-opt 试射强度），接受改进后按 α 衰减；
      脉冲率 r = 以概率 r 直接在最优解附近做「定位性」开发（跳过移动直接试射）。
    """

    name = "蝙蝠算法 BA"
    default_params = {
        "n_bats": 20,
        "f_min": 0.05,
        "f_max": 0.45,     # 频率上限（=向最优移动的最大前缀比例，防坍塌同 GWO 教训）
        "A0": 0.9,         # 初始响度
        "r0": 0.5,         # 初始脉冲率
        "alpha": 0.9,      # 响度衰减系数
        "gamma": 0.9,      # 脉冲率增长系数
        "max_iter": 200,
        "seed": 42,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_bats": {"min": 5, "max": 50, "step": 1, "int": True, "label": "蝙蝠数", "desc": "种群规模（大实例自动降配）"},
        "f_min": {"min": 0.01, "max": 0.3, "step": 0.01, "label": "频率下限", "desc": "向最优移动的最小步幅基数"},
        "f_max": {"min": 0.1, "max": 0.8, "step": 0.05, "label": "频率上限", "desc": "向最优移动的最大步幅基数（防种群坍塌）"},
        "A0": {"min": 0.3, "max": 1.0, "step": 0.05, "label": "初始响度", "desc": "随机游走（2-opt 试射）的初始强度"},
        "r0": {"min": 0.1, "max": 0.9, "step": 0.05, "label": "初始脉冲率", "desc": "在最优解附近做定位性开发的概率"},
        "alpha": {"min": 0.5, "max": 0.99, "step": 0.01, "label": "响度衰减 α", "desc": "蝙蝠找到更好解后响度乘以 α（逐步收敛到开发）"},
        "gamma": {"min": 0.5, "max": 0.99, "step": 0.01, "label": "脉冲增长 γ", "desc": "蝙蝠找到更好解后脉冲率按 γ·r 增长"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_bats = p["n_bats"]
        if n > 80:
            n_bats = max(10, n_bats // 2)
        bats = [nearest_neighbor(D, start=0)]
        for _ in range(n_bats - 1):
            bats.append(nearest_neighbor(D, start=rng.randrange(n)))
        bats = [_random_2opt_shot(t, D, rng, trials=50) for t in bats]
        costs = [tour_length(t, D) for t in bats]
        A = [p["A0"]] * n_bats
        r = [p["r0"]] * n_bats
        i0 = min(range(n_bats), key=lambda i: costs[i])
        best, best_cost = list(bats[i0]), costs[i0]

        for it in range(1, p["max_iter"] + 1):
            for i in range(n_bats):
                f = rng.uniform(p["f_min"], p["f_max"])
                if rng.random() < r[i]:
                    # 脉冲发射：在全局最优附近做定位性开发（短 2-opt 试射）
                    cand = _random_2opt_shot(best, D, rng, max(2, int(A[i] * 18)))
                else:
                    # 常规移动：向最优解执行交换序列前缀（比例=f），加响度级随机游走
                    seq = swap_seq_to_target(list(bats[i]), best)
                    cand = apply_swaps(bats[i], seq[: int(len(seq) * min(p["f_max"], f))])
                    cand = _random_2opt_shot(cand, D, rng, max(1, int(A[i] * 14)))
                c = tour_length(cand, D)
                # 响度门槛：只有「响度加权随机数 < 改进幅度比例」才接纳（BA 原式的排列域近似）
                if c < costs[i] and rng.random() < A[i]:
                    bats[i], costs[i] = cand, c
                    A[i] *= p["alpha"]
                    r[i] = p["r0"] * (1 - pow(2.718281828, -p["gamma"] * it))
                    if c < best_cost:
                        best, best_cost = list(cand), c
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    worst = max(range(n_bats), key=lambda i: costs[i])
                    bats[worst], costs[worst] = list(improved), c
            yield IterationState(
                it, best_cost, list(best), sum(costs) / n_bats,
                {"A_mean": round(sum(A) / n_bats, 3), "n_bats": n_bats},
            )


class HarmonySearch(BaseSolver):
    """和声搜索 HS（Geem, Kim & Loganathan, 2001）：像乐手即兴合奏一样生成新解。

    引用量级：近万次，"音乐启发式"的开山之作。乐手即兴的三种方式
    正好对应三个参数：
      记忆考虑（HMCR）= 从记忆库里抄一段；音高调整（PAR）= 抄完微调；
      随机选择（1−HMCR）= 完全即兴。新和声更好就替换记忆库里的最差者。

    离散化映射（TSP 版）：
      和声 = 排列；记忆考虑 = 随机抄一条记忆和声；
      音高调整 = 短 2-opt 试射或片段逆转（微调）；
      完全即兴 = 从 NN 起点重新构造。
    """

    name = "和声搜索 HS"
    default_params = {
        "hms": 20,          # 和声记忆库大小
        "hmcr": 0.9,        # 记忆考虑率
        "par": 0.3,         # 音高调整率
        "max_iter": 200,
        "seed": 42,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "音乐启发"
    param_specs = {
        "hms": {"min": 5, "max": 50, "step": 1, "int": True, "label": "记忆库大小", "desc": "和声记忆库 HM 的容量"},
        "hmcr": {"min": 0.5, "max": 0.99, "step": 0.01, "label": "记忆考虑率", "desc": "新和声从记忆库取材的概率；否则完全即兴（重新构造）"},
        "par": {"min": 0.05, "max": 0.8, "step": 0.05, "label": "音高调整率", "desc": "抄完记忆和声后做微调（2-opt 试射/逆转）的概率"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        hms = p["hms"]
        if n > 80:
            hms = max(10, hms // 2)
        mem = [nearest_neighbor(D, start=0)]
        for _ in range(hms - 1):
            mem.append(nearest_neighbor(D, start=rng.randrange(n)))
        mem = [_random_2opt_shot(t, D, rng, trials=50) for t in mem]
        costs = [tour_length(t, D) for t in mem]
        i0 = min(range(hms), key=lambda i: costs[i])
        best, best_cost = list(mem[i0]), costs[i0]

        for it in range(1, p["max_iter"] + 1):
            # 即兴一支新和声
            if rng.random() < p["hmcr"]:
                new = list(mem[rng.randrange(hms)])  # 记忆考虑：抄一条
                if rng.random() < p["par"]:
                    # 音高调整：微调（一半概率 2-opt 试射，一半概率片段逆转）
                    if rng.random() < 0.5:
                        new = _random_2opt_shot(new, D, rng, 12)
                    else:
                        L = rng.randint(2, max(2, n // 4))
                        i = rng.randrange(1, n - L)
                        new[i : i + L] = reversed(new[i : i + L])
            else:
                # 完全即兴：从随机 NN 起点重新构造
                new = nearest_neighbor(D, start=rng.randrange(n))
                new = _random_2opt_shot(new, D, rng, 20)
            c = tour_length(new, D)
            # 替换记忆库里的最差者（好就进）
            worst = max(range(hms), key=lambda i: costs[i])
            if c < costs[worst]:
                mem[worst], costs[worst] = new, c
                if c < best_cost:
                    best, best_cost = list(new), c
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c2 = tour_length(improved, D)
                if c2 < best_cost:
                    best, best_cost = improved, c2
                    worst = max(range(hms), key=lambda i: costs[i])
                    mem[worst], costs[worst] = list(improved), c2
            yield IterationState(
                it, best_cost, list(best), sum(costs) / hms,
                {"hmcr": p["hmcr"], "par": p["par"]},
            )


class GravitationalSearch(BaseSolver):
    """引力搜索算法 GSA（Rashedi, Nezamabadi-pour & Saryazdi, 2009）：
    万有引力定律 + 运动定律的搜索算法。

    引用量级：近万次，物理启发群里的代表作（隔壁物理启发目前只有 SA）。
    质量越大的天体（解越优）引力越强——整个种群在引力场里向优质解坍缩，
    引力常数 G 随时间衰减 = 前期大步探索、后期精细收缩。

    离散化映射（TSP 版）：
      质量 M_i = 成本归一化后取 softmax 式权重（越优质量越大）；
      引力移动 = 按质量轮盘选一个比自身优的天体 j，向 j 执行交换序列前缀，
      前缀比例 = G(t) 缩放（衰减）+ step_cap 上限（防坍塌，GWO/DE 同款教训）；
      惯性扰动 = 小概率随机交换（模拟速度残差）。
    """

    name = "引力搜索 GSA"
    default_params = {
        "n_agents": 25,
        "G0": 0.6,         # 初始引力常数（=移动步幅基数）
        "G_decay": 0.97,   # G 衰减率
        "mutation": 0.04,  # 惯性扰动概率
        "polish_p": 0.3,   # 打磨概率：以小概率对候选做短 2-opt 试射（memetic GSA）
        "max_iter": 200,
        "seed": 42,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "物理启发"
    param_specs = {
        "n_agents": {"min": 6, "max": 60, "step": 2, "int": True, "label": "天体数", "desc": "种群规模（大实例自动降配）"},
        "G0": {"min": 0.1, "max": 1.0, "step": 0.05, "label": "初始引力 G0", "desc": "移动步幅基数（向引力源执行的交换序列比例）"},
        "G_decay": {"min": 0.9, "max": 1.0, "step": 0.01, "label": "引力衰减", "desc": "G(t)=G0·decay^t；越快收敛越早、探索越少"},
        "mutation": {"min": 0.0, "max": 0.2, "step": 0.01, "label": "惯性扰动", "desc": "每个天体每代随机交换两城市的概率（速度残差的等价物）"},
        "polish_p": {"min": 0.0, "max": 0.5, "step": 0.05, "label": "滑翔/打磨", "desc": "对当前位置直接做短 2-opt 试射的概率（memetic GSA 组件）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_agents = p["n_agents"]
        if n > 80:
            n_agents = max(10, n_agents // 2)
        agents = [nearest_neighbor(D, start=0)]
        for _ in range(n_agents - 1):
            agents.append(nearest_neighbor(D, start=rng.randrange(n)))
        agents = [_random_2opt_shot(t, D, rng, trials=50) for t in agents]
        costs = [tour_length(t, D) for t in agents]
        i0 = min(range(n_agents), key=lambda i: costs[i])
        best, best_cost = list(agents[i0]), costs[i0]

        for it in range(1, p["max_iter"] + 1):
            G = p["G0"] * (p["G_decay"] ** it)
            # 质量 = 成本越低质量越大（min-max 归一化的经典式）
            cmin, cmax = min(costs), max(costs)
            span = max(cmax - cmin, 1e-9)
            masses = [(cmax - c) / span + 0.05 for c in costs]
            for i in range(n_agents):
                # 引力源：从比 i 优的天体里按质量轮盘选一个（含全局最优）
                attractors = [j for j in range(n_agents) if costs[j] < costs[i]]
                if not attractors:
                    # 最优天体（质量最大）：连续 GSA 里加速度 ∝ F/M，重天体受力
                    # 最小但非零——给一点微量滑翔，否则它会被永久冻结（实测踩坑）
                    if rng.random() < p["polish_p"]:
                        glide = _random_2opt_shot(agents[i], D, rng, 12)
                        gc = tour_length(glide, D)
                        if gc < costs[i]:
                            agents[i], costs[i] = glide, gc
                            if gc < best_cost:
                                best, best_cost = list(glide), gc
                    continue
                j = _roulette(rng, [masses[j] for j in attractors])
                seq = swap_seq_to_target(list(agents[i]), agents[attractors[j]])
                k = int(len(seq) * min(0.5, G * (0.5 + rng.random())))
                cand = apply_swaps(agents[i], seq[:k]) if k else list(agents[i])
                if rng.random() < p["mutation"]:
                    a_, b_ = rng.randrange(n), rng.randrange(n)
                    cand[a_], cand[b_] = cand[b_], cand[a_]
                c = tour_length(cand, D)
                if c < costs[i]:  # 引力只拉不推（排列域贪心选择）
                    agents[i], costs[i] = cand, c
                    if c < best_cost:
                        best, best_cost = list(cand), c
                # 惯性滑翔（memetic GSA）：直接对当前位置做短 2-opt 试射。
                # ★打磨必须作用在当前解本体而非「移动后的候选」——前缀移动先
                # 损伤解、再打磨只能修补损伤，永远回不到原点以下，贪心门槛
                # 全拒 → 净改进为零（实测踩坑，同 MFO）。
                if rng.random() < p["polish_p"]:
                    glide = _random_2opt_shot(agents[i], D, rng, 8)
                    gc = tour_length(glide, D)
                    if gc < costs[i]:
                        agents[i], costs[i] = glide, gc
                        if gc < best_cost:
                            best, best_cost = list(glide), gc
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    worst = max(range(n_agents), key=lambda i: costs[i])
                    agents[worst], costs[worst] = list(improved), c
            yield IterationState(
                it, best_cost, list(best), sum(costs) / n_agents,
                {"G": round(G, 4), "n_agents": n_agents},
            )


class TeachingLearning(BaseSolver):
    """教与学优化 TLBO（Rao, Savsani & Vakharia, 2011）：模拟课堂里的教与学。

    引用量级：近万次，最大卖点是「无算法特定参数」——只有种群和代数，
    没有需要调的系数（本实现额外保留了 memetic 钩子，可关）。
    两阶段：教师阶段（全班向老师靠拢）+ 学习阶段（两两互学，优者带劣者）。

    离散化映射（TSP 版）：
      教师阶段：teacher = 当前最优；mean_diff = 学生与老师的交换序列前缀
      （随机比例 = 「学了多少」，含学反了的情况——原式的 rand±1）；
      学习阶段：随机配对，劣者向优者执行交换序列前缀或 OX 交叉；
      两阶段都是贪心选择（新解更好才换）。
    """

    name = "教与学优化 TLBO"
    default_params = {
        "n_students": 25,
        "learn_ox": 0.4,   # 学习阶段用 OX 交叉的比例（其余用交换序列）
        "polish_p": 0.3,   # 打磨概率（memetic TLBO；排列域上纯模仿对已抛光解无能为力）
        "max_iter": 200,
        "seed": 42,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "进化计算"
    param_specs = {
        "n_students": {"min": 6, "max": 60, "step": 2, "int": True, "label": "学生数", "desc": "班级规模（大实例自动降配）"},
        "learn_ox": {"min": 0.0, "max": 1.0, "step": 0.1, "label": "OX 交叉比例", "desc": "学习阶段用 OX 交叉（重组）vs 交换序列（模仿）的比例"},
        "polish_p": {"min": 0.0, "max": 0.5, "step": 0.05, "label": "打磨概率", "desc": "对每个新解做短 2-opt 试射的概率（memetic TLBO 组件）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_s = p["n_students"]
        if n > 80:
            n_s = max(10, n_s // 2)
        cls = [nearest_neighbor(D, start=0)]
        for _ in range(n_s - 1):
            cls.append(nearest_neighbor(D, start=rng.randrange(n)))
        cls = [_random_2opt_shot(t, D, rng, trials=50) for t in cls]
        costs = [tour_length(t, D) for t in cls]
        i0 = min(range(n_s), key=lambda i: costs[i])
        best, best_cost = list(cls[i0]), costs[i0]

        def try_replace(i, cand):
            nonlocal best, best_cost
            c = tour_length(cand, D)
            if c < costs[i]:
                cls[i], costs[i] = cand, c
                if c < best_cost:
                    best, best_cost = list(cand), c

        for it in range(1, p["max_iter"] + 1):
            # 教师阶段：每个学生向 teacher 学（差异比例随机，可正可负）
            teacher = min(range(n_s), key=lambda i: costs[i])
            for i in range(n_s):
                if i == teacher:
                    continue
                seq = swap_seq_to_target(list(cls[i]), cls[teacher])
                ratio = rng.random() if rng.random() < 0.7 else rng.random() * 0.3
                k = int(len(seq) * ratio)
                cand = apply_swaps(cls[i], seq[:k]) if k else list(cls[i])
                if rng.random() < p["polish_p"]:
                    cand = _random_2opt_shot(cand, D, rng, 8)
                try_replace(i, cand)
            # 学习阶段：随机配对，劣者向优者学
            order = list(range(n_s))
            rng.shuffle(order)
            for a, b in zip(order[0::2], order[1::2]):
                loser, winner = (a, b) if costs[a] > costs[b] else (b, a)
                if rng.random() < p["learn_ox"]:
                    cand = _ox_crossover(cls[loser], cls[winner], rng)
                else:
                    seq = swap_seq_to_target(list(cls[loser]), cls[winner])
                    k = int(len(seq) * rng.random())
                    cand = apply_swaps(cls[loser], seq[:k]) if k else list(cls[loser])
                if rng.random() < p["polish_p"]:
                    cand = _random_2opt_shot(cand, D, rng, 8)
                try_replace(loser, cand)
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    worst = max(range(n_s), key=lambda i: costs[i])
                    cls[worst], costs[worst] = list(improved), c
            yield IterationState(
                it, best_cost, list(best), sum(costs) / n_s,
                {"teacher_cost": round(costs[teacher], 1), "n_students": n_s},
            )


class BacterialForaging(BaseSolver):
    """细菌觅食优化 BFO（Passino, 2002）：趋向、繁殖、消散三循环。

    引用量级：数千次，群智能早期经典。细菌在营养梯度上「翻滚/游动」：
    方向好的就一直往前游（swim），方向差就换个方向（tumble）；
    半数淘汰 + 复制好菌（繁殖）；偶尔整体迁移（消散散播）防早熟。

    离散化映射（TSP 版）：
      翻滚 = 小步 2-opt 试射（换方向）；游动 = 只要还在改进就沿同一算子连试
      （最多 Ns 步，BFO 的标志性 swim）；繁殖 = 淘汰最差半数、复制最优半数；
      消散 = 最差 ed 比例从 NN 重新播种。
    """

    name = "细菌觅食 BFO"
    default_params = {
        "n_bacteria": 20,
        "swim_steps": 4,   # 一次 chemotaxis 里最多连游几步
        "ed_prob": 0.15,   # 消散概率（每代对最差个体）
        "max_iter": 200,
        "seed": 42,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_bacteria": {"min": 6, "max": 50, "step": 2, "int": True, "label": "细菌数", "desc": "种群规模（大实例自动降配）"},
        "swim_steps": {"min": 1, "max": 10, "step": 1, "int": True, "label": "连游步数", "desc": "方向好时最多连游几步（swim 深度）"},
        "ed_prob": {"min": 0.0, "max": 0.5, "step": 0.05, "label": "消散比例", "desc": "每代最差个体被随机迁移重播的概率"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_b = p["n_bacteria"]
        if n > 80:
            n_b = max(10, n_b // 2)
        pop = [nearest_neighbor(D, start=0)]
        for _ in range(n_b - 1):
            pop.append(nearest_neighbor(D, start=rng.randrange(n)))
        pop = [_random_2opt_shot(t, D, rng, trials=50) for t in pop]
        costs = [tour_length(t, D) for t in pop]
        i0 = min(range(n_b), key=lambda i: costs[i])
        best, best_cost = list(pop[i0]), costs[i0]

        for it in range(1, p["max_iter"] + 1):
            # 趋向（chemotaxis）：翻滚 + 连游
            for i in range(n_b):
                cur = _random_2opt_shot(pop[i], D, rng, 8)  # 翻滚
                cc = tour_length(cur, D)
                if cc < costs[i]:
                    pop[i], costs[i] = cur, cc
                    # 游动：方向好就沿同方向（继续 2-opt 试射）连走
                    for _ in range(p["swim_steps"] - 1):
                        nxt = _random_2opt_shot(pop[i], D, rng, 8)
                        nc = tour_length(nxt, D)
                        if nc < costs[i]:
                            pop[i], costs[i] = nxt, nc
                        else:
                            break
                    if costs[i] < best_cost:
                        best, best_cost = list(pop[i]), costs[i]
            # 繁殖（reproduction）：淘汰最差半数，复制最优半数
            order = sorted(range(n_b), key=lambda i: costs[i])
            half = n_b // 2
            for rank in range(half):
                src, dst = order[rank], order[-1 - rank]
                if rank < half and costs[dst] > costs[src]:
                    pop[dst], costs[dst] = list(pop[src]), costs[src]
            # 消散（elimination-dispersal）：最差个体随机迁移
            worst = max(range(n_b), key=lambda i: costs[i])
            if rng.random() < p["ed_prob"]:
                fresh = nearest_neighbor(D, start=rng.randrange(n))
                fresh = _random_2opt_shot(fresh, D, rng, 20)
                pop[worst], costs[worst] = fresh, tour_length(fresh, D)
            i_b = min(range(n_b), key=lambda i: costs[i])
            if costs[i_b] < best_cost:
                best, best_cost = list(pop[i_b]), costs[i_b]
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    worst = max(range(n_b), key=lambda i: costs[i])
                    pop[worst], costs[worst] = list(improved), c
            yield IterationState(
                it, best_cost, list(best), sum(costs) / n_b,
                {"ed_prob": p["ed_prob"], "n_bacteria": n_b},
            )


class MothFlame(BaseSolver):
    """蛾焰优化 MFO（Mirjalili, 2015）：飞蛾绕火焰螺旋飞行的优化算法。

    引用量级：数千次，Mirjalili 系（GWO/WOA/SCA/MFO）的收官之作。
    飞蛾 = 解；火焰 = 历史最优集合。飞蛾沿螺旋线绕火焰飞：
    S(r) = |F−M|·e^(bt)·cos(2πt)，b=螺旋常数，t∈[−1,1]——
    既可能靠近火焰（开发），也可能绕到另一侧（探索）。

    离散化映射（TSP 版）：
      螺旋 = 向火焰的交换序列按比例 r 执行前缀，比例由 e^(b·t)·|cos| 调制
      （与 WOA 的螺旋收缩同款思想）；
      焰数逐代递减 n → 1 = 探索到开发的全局收敛调度（MFO 标志）。
    """

    name = "蛾焰优化 MFO"
    default_params = {
        "n_moths": 25,
        "b_spiral": 1.0,   # 螺旋常数
        "polish_p": 0.3,   # 打磨概率（memetic MFO；纯螺旋前缀对已抛光解无能为力）
        "max_iter": 200,
        "seed": 42,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_moths": {"min": 6, "max": 60, "step": 2, "int": True, "label": "飞蛾数", "desc": "种群规模（大实例自动降配）"},
        "b_spiral": {"min": 0.2, "max": 2.0, "step": 0.1, "label": "螺旋常数 b", "desc": "越大绕火焰的弧线越弯（探索越强）"},
        "polish_p": {"min": 0.0, "max": 0.5, "step": 0.05, "label": "滑翔/打磨", "desc": "对当前位置直接做短 2-opt 试射的概率（memetic MFO 组件）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_m = p["n_moths"]
        if n > 80:
            n_m = max(10, n_m // 2)
        moths = [nearest_neighbor(D, start=0)]
        for _ in range(n_m - 1):
            moths.append(nearest_neighbor(D, start=rng.randrange(n)))
        moths = [_random_2opt_shot(t, D, rng, trials=50) for t in moths]
        mc = [tour_length(t, D) for t in moths]

        # 初始火焰 = 初始种群排序
        order = sorted(range(n_m), key=lambda i: mc[i])
        flames = [list(moths[i]) for i in order]
        fc = [mc[i] for i in order]
        best, best_cost = list(flames[0]), fc[0]

        for it in range(1, p["max_iter"] + 1):
            # 焰数递减：n → 1（MFO 的全局收敛调度）
            n_flames = max(1, round(n_m - it * ((n_m - 1) / p["max_iter"])))
            b = p["b_spiral"]
            for i in range(n_m):
                flame = flames[i % n_flames]
                seq = swap_seq_to_target(list(moths[i]), flame)
                if seq:
                    # 螺旋调制：t∈[-1,1]，比例 = e^(b·t)·|cos(2πt)|，钳到 [0, 0.5]
                    t_spiral = rng.uniform(-1.0, 1.0)
                    ratio = min(0.5, max(0.02, pow(2.718281828, b * t_spiral) * abs(math.cos(2 * math.pi * t_spiral))))
                    k = int(len(seq) * ratio)
                    cand = apply_swaps(moths[i], seq[:k])
                    c = tour_length(cand, D)
                    if c < mc[i]:
                        moths[i], mc[i] = cand, c
                        if c < best_cost:
                            best, best_cost = list(cand), c
                # 螺旋滑翔（memetic MFO）：直接对当前位置做短 2-opt 试射。
                # ★打磨必须作用在当前蛾本体而非「螺旋移动后的候选」——螺旋先
                # 损伤解、再打磨只能修补损伤，回不到原点以下，贪心门槛全拒 →
                # 净改进为零（实测踩坑，同 GSA）。
                if rng.random() < p["polish_p"]:
                    glide = _random_2opt_shot(moths[i], D, rng, 8)
                    gc = tour_length(glide, D)
                    if gc < mc[i]:
                        moths[i], mc[i] = glide, gc
                        if gc < best_cost:
                            best, best_cost = list(glide), gc
            # 更新火焰：蛾+焰合并取前 n_flames 名（MFO 原文做法）
            pool = [(list(moths[i]), mc[i]) for i in range(n_m)] + list(zip(flames, fc))
            pool.sort(key=lambda x: x[1])
            flames = [list(t) for t, _ in pool[:n_flames]]
            fc = [c for _, c in pool[:n_flames]]
            if fc[0] < best_cost:
                best, best_cost = list(flames[0]), fc[0]
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    if n_flames > 1:
                        flames[-1], fc[-1] = list(improved), c
            yield IterationState(
                it, best_cost, list(best), sum(mc) / n_m,
                {"n_flames": n_flames, "n_moths": n_m},
            )


class Fireworks(BaseSolver):
    """烟花算法 FWA（Tan & Zhu, 2010）：烟花爆炸产生火花，好烟花炸得密、差烟花炸得广。

    引用量级：数千次（原版 FWA + 增强版 FWA 全家）。它的调度思想在种群算法里独一份：
      ① 火花数量 ∝ 适应度——好烟花炸出的火花多（在好解附近深耕），
         爆炸幅度 ∝ (1-适应度)——差烟花炸得范围大（在远处勘探）
      ② 高斯火花：在最优烟花附近用高斯扰动再炸一发（精细开发）
      ③ 选择：最优烟花保送 + 其余按"与已有解的距离"保持多样性

    离散化映射（TSP 版）：
      爆炸 = 对烟花做 A_i 次随机突变（片段逆转/两点交换），A_i 越大炸得越远；
      高斯火花 = 对全局最优做短 2-opt 试射（连续域高斯扰动的排列域等价物）；
      数量/幅度调度 = 原文的线性归一化公式原样保留。
    教训（FA/GSA 同款）：纯随机突变对已抛光的解几乎必然变差，火花按贪心准入，
    真实下降由高斯火花（2-opt 试射）驱动——这是 memetic FWA 的标准做法。
    """

    name = "烟花算法 FWA"
    default_params = {
        "n_fireworks": 10,
        "base_sparks": 16,  # 每代火花总数基数
        "max_amp": 6,       # 最大爆炸幅度（突变次数上限）
        "max_iter": 200,
        "seed": 42,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_fireworks": {"min": 4, "max": 30, "step": 2, "int": True, "label": "烟花数", "desc": "种群规模（大实例自动降配）"},
        "base_sparks": {"min": 6, "max": 40, "step": 2, "int": True, "label": "火花基数", "desc": "每代炸出的火花总数基准（按适应度分配给各烟花）"},
        "max_amp": {"min": 1, "max": 12, "step": 1, "int": True, "label": "最大爆炸幅度", "desc": "单个火花最多做几次突变；越大勘探越远"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def _mutate(self, tour: List[int], rng) -> List[int]:
        t = list(tour)
        n = len(t)
        if rng.random() < 0.5:
            a, b = sorted(rng.sample(range(n), 2))
            t[a : b + 1] = reversed(t[a : b + 1])
        else:
            i, j = rng.randrange(n), rng.randrange(n)
            t[i], t[j] = t[j], t[i]
        return t

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_fw = p["n_fireworks"]
        if n > 80:
            n_fw = max(5, n_fw // 2)
        fws = [nearest_neighbor(D, start=0)]
        for _ in range(n_fw - 1):
            fws.append(nearest_neighbor(D, start=rng.randrange(n)))
        fws = [_random_2opt_shot(t, D, rng, trials=50) for t in fws]
        fc = [tour_length(t, D) for t in fws]
        bi = min(range(n_fw), key=lambda i: fc[i])
        best, best_cost = list(fws[bi]), fc[bi]

        eps = 1e-9
        for it in range(1, p["max_iter"] + 1):
            worst, total_gap = max(fc), 0.0
            for c in fc:
                total_gap += worst - c
            total_gap += eps
            n_eval = 0
            # ① 常规爆炸：好烟花分到的火花多，差烟花的幅度大（FWA 原文调度）
            for i in range(n_fw):
                n_sp = max(1, int(p["base_sparks"] * (worst - fc[i] + eps) / total_gap))
                amp = max(1, int(round(p["max_amp"] * (fc[i] - best_cost + eps) / (sum(c - best_cost for c in fc) + eps))))
                amp = max(1, min(amp, p["max_amp"]))
                for _ in range(n_sp):
                    cand = list(fws[i])
                    for _ in range(amp):
                        cand = self._mutate(cand, rng)
                    c = tour_length(cand, D)
                    n_eval += 1
                    if c < fc[i]:  # 火花贪心准入（memetic FWA 标准做法）
                        fws[i], fc[i] = cand, c
                        if c < best_cost:
                            best, best_cost = list(cand), c
            # ② 高斯火花：对全局最优做短 2-opt 试射（开发主力，真实下降来源）
            for _ in range(2):
                cand = _random_2opt_shot(best, D, rng, trials=8)
                c = tour_length(cand, D)
                n_eval += 1
                if c < best_cost:
                    best, best_cost = cand, c
            # ③ 多样性保底：最差烟花偶尔被最佳火花替换（防全员坍缩到 best）
            worst_i = max(range(n_fw), key=lambda i: fc[i])
            if fc[worst_i] > best_cost * 1.35:
                fws[worst_i], fc[worst_i] = list(best), best_cost

            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    fws[worst_i], fc[worst_i] = list(improved), c

            yield IterationState(
                it, best_cost, list(best), sum(fc) / n_fw,
                {"sparks": n_eval, "n_fw": n_fw},
            )


class ArtificialFishSwarm(BaseSolver):
    """人工鱼群 AFSA（李晓磊, 2002）：觅食/聚群/追尾/随机四种行为按环境切换。

    引用量级：数千次（国内群智能领域引用最高的原创算法之一）。
    每条鱼每代根据视野内环境选行为：
      觅食 AF_PREY：试 try_n 次随机邻域移动，找到更优就过去——搜索主力
      追尾 AF_FOLLOW：视野内有更优的鱼且不拥挤 → 向它移动——信息共享
      聚群 AF_SWARM：视野内同伴不拥挤 → 向伙伴靠拢——抱团防迷路
      随机 AF_RANDOM：没鱼理自己时随便游动——保底勘探
    拥挤度因子 δ 是 AFSA 的招牌参数：同一片水域鱼太多就放弃跟进，防止全员挤到一个局部谷。

    离散化映射（TSP 版）：
      邻域 = 片段逆转 / 两点交换；"向某鱼移动" = 交换序列前缀（步幅有上限）；
      视野 = 随机抽 visual_k 条同伴（排列域没有几何邻域，用抽样近似）。
    """

    name = "人工鱼群 AFSA"
    default_params = {
        "n_fish": 24,
        "try_n": 5,       # 觅食行为每次的尝试次数
        "visual_k": 6,    # 视野：每代随机抽多少条同伴观察
        "crowd": 0.6,     # 拥挤度因子 δ：视野内更优鱼占比超过它就放弃跟进
        "step_cap": 0.4,  # 追尾/聚群的移动步幅上限（防坍塌，GWO 教训）
        "max_iter": 200,
        "seed": 42,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_fish": {"min": 6, "max": 60, "step": 2, "int": True, "label": "鱼群规模", "desc": "种群大小（大实例自动降配）"},
        "try_n": {"min": 1, "max": 15, "step": 1, "int": True, "label": "觅食尝试", "desc": "觅食行为每代尝试的邻域移动次数；太小勘探不足"},
        "visual_k": {"min": 2, "max": 20, "step": 1, "int": True, "label": "视野宽度", "desc": "每代随机观察的同伴数"},
        "crowd": {"min": 0.1, "max": 1.0, "step": 0.05, "label": "拥挤度因子 δ", "desc": "视野内更优鱼占比超过 δ 就放弃追尾/聚群；越小越怕挤"},
        "step_cap": {"min": 0.1, "max": 0.6, "step": 0.05, "label": "步幅上限", "desc": "向同伴移动时执行交换序列前缀的最大比例"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def _prey(self, tour: List[int], D, rng, p) -> List[int]:
        """觅食：最多 try_n 次邻域试移，返回第一个更优的，否则原地不动。"""
        cur = tour_length(tour, D)
        for _ in range(p["try_n"]):
            t = list(tour)
            n = len(t)
            if rng.random() < 0.5:
                a, b = sorted(rng.sample(range(n), 2))
                t[a : b + 1] = reversed(t[a : b + 1])
            else:
                i, j = rng.randrange(n), rng.randrange(n)
                t[i], t[j] = t[j], t[i]
            if tour_length(t, D) < cur:
                return t
        return list(tour)

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_f = p["n_fish"]
        if n > 80:
            n_f = max(10, n_f // 2)
        fish = [nearest_neighbor(D, start=0)]
        for _ in range(n_f - 1):
            fish.append(nearest_neighbor(D, start=rng.randrange(n)))
        fish = [_random_2opt_shot(t, D, rng, trials=50) for t in fish]
        fc = [tour_length(t, D) for t in fish]
        bi = min(range(n_f), key=lambda i: fc[i])
        best, best_cost = list(fish[bi]), fc[bi]

        follows = swarms = 0
        for it in range(1, p["max_iter"] + 1):
            for i in range(n_f):
                # 视野：随机抽 visual_k 条同伴
                peers = rng.sample([j for j in range(n_f) if j != i],
                                   min(p["visual_k"], n_f - 1))
                better = [j for j in peers if fc[j] < fc[i]]
                moved = False
                # 追尾/聚群：视野内有更优鱼且不拥挤 → 向最优的那条移动
                if better:
                    j = min(better, key=lambda x: fc[x])
                    crowd_ratio = sum(1 for k in peers if fc[k] < fc[i] * 1.05) / len(peers)
                    if crowd_ratio < p["crowd"]:
                        seq = swap_seq_to_target(list(fish[i]), fish[j])
                        if seq:
                            k = max(1, int(len(seq) * min(p["step_cap"], rng.random())))
                            cand = apply_swaps(fish[i], seq[:k])
                            c = tour_length(cand, D)
                            if c < fc[i]:
                                fish[i], fc[i] = cand, c
                                moved = True
                                follows += 1
                # 觅食：追尾没成或没目标时搜索（AFSA 的真实驱动力）
                if not moved:
                    cand = self._prey(fish[i], D, rng, p)
                    c = tour_length(cand, D)
                    if c < fc[i]:
                        fish[i], fc[i] = cand, c
                else:
                    swarms += 1

            bi = min(range(n_f), key=lambda i: fc[i])
            if fc[bi] < best_cost:
                best, best_cost = list(fish[bi]), fc[bi]

            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    worst = max(range(n_f), key=lambda i: fc[i])
                    fish[worst], fc[worst] = list(improved), c

            yield IterationState(
                it, best_cost, list(best), sum(fc) / n_f,
                {"follows": follows, "swarms": swarms, "n_fish": n_f},
            )


class CrossEntropy(BaseSolver):
    """交叉熵方法 CEM（Rubinstein, 1997）：从分布采样 → 留精英 → 更新分布。

    引用量级：数万次（随机优化/稀有事件模拟的奠基作之一）。
    它和所有"个体交互"算法根本不同：鱼、狼、粒子互相模仿，
    CEM 的种群之间**零交互**——个体只是从分布 P 里抽出来的样本，
    选择压力通过"精英样本的统计量回写分布"传递。这就是 EDA
    （分布估计算法）家族的源头思想。

    离散化映射（TSP 版）：
      分布 = P[d][c]：位置 d 出现城市 c 的概率矩阵（n×n）；
      采样 = 逐位置按 P 轮盘抽不重复城市，生成一条排列；
      更新 = 统计精英样本的频率 F，P ← λ·P + (1-λ)·F（平滑系数 λ 防分布塌缩）。
    混合组件：对精英做短 2-opt 试射再回写频率（memetic EDA，
    纯采样从抛光的 NN 播种上几乎抽不出更优——GSA 教训的 EDA 版）。
    """

    name = "交叉熵 CEM"
    default_params = {
        "n_pop": 30,
        "rho": 0.3,        # 精英比例（前 30% 进入频率统计）
        "lam": 0.7,        # 平滑系数 λ：P = λ·P + (1-λ)·F，1=不变 0=全信样本
        "polish_p": 0.3,   # 精英打磨概率（memetic EDA 组件）
        "max_iter": 200,
        "seed": 42,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "进化计算"
    param_specs = {
        "n_pop": {"min": 10, "max": 80, "step": 2, "int": True, "label": "样本数", "desc": "每代从分布抽样的解数量（大实例自动降配）"},
        "rho": {"min": 0.05, "max": 0.5, "step": 0.05, "label": "精英比例 ρ", "desc": "前百分之多少的样本算精英；太小学得太快易早熟"},
        "lam": {"min": 0.3, "max": 0.95, "step": 0.05, "label": "平滑系数 λ", "desc": "分布更新保留旧分布的比例；越大收敛越稳越慢"},
        "polish_p": {"min": 0.0, "max": 0.5, "step": 0.05, "label": "精英打磨", "desc": "对精英样本做短 2-opt 试射再回写分布的概率"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def _sample(self, P, n, rng) -> List[int]:
        """按概率矩阵逐位置抽不重复城市（经典 EDA 采样）。"""
        tour = []
        for d in range(n):
            avail = [c for c in range(n) if c not in tour]
            w = [P[d][c] for c in avail]
            s = sum(w)
            if s <= 0:
                tour.append(rng.choice(avail))
                continue
            r = rng.random() * s
            acc = 0.0
            for idx, c in enumerate(avail):
                acc += w[idx]
                if r <= acc:
                    tour.append(c)
                    break
            else:
                tour.append(avail[-1])
        return tour

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_pop = p["n_pop"]
        if n > 80:
            n_pop = max(15, n_pop // 2)
        # 分布初始化：均匀 + NN 多起点精英偏置（纯均匀起步收敛太慢）
        P = [[1.0 / n] * n for _ in range(n)]
        elites0 = [nearest_neighbor(D, start=rng.randrange(n)) for _ in range(10)]
        elites0 = [_random_2opt_shot(t, D, rng, trials=40) for t in elites0]
        lam, rho = p["lam"], p["rho"]

        best, best_cost = None, float("inf")
        for t in elites0:
            c = tour_length(t, D)
            if c < best_cost:
                best, best_cost = list(t), c

        for it in range(1, p["max_iter"] + 1):
            pop = [self._sample(P, n, rng) for _ in range(n_pop)]
            costs = [tour_length(t, D) for t in pop]
            # 精英 = 本代前 ρ 样本 + 历史最优（CEM 的标准加持：保优）
            order = sorted(range(n_pop), key=lambda i: costs[i])
            k_e = max(2, int(n_pop * rho))
            elite = [(pop[i], costs[i]) for i in order[:k_e]] + [(best, best_cost)]
            # 精英打磨（memetic EDA）：抛光后再回写分布，分布才能学到好结构
            pol = []
            for t, c in elite:
                if rng.random() < p["polish_p"]:
                    t2 = _random_2opt_shot(t, D, rng, 8)
                    c2 = tour_length(t2, D)
                    if c2 < c:
                        t, c = t2, c2
                pol.append((t, c))
                if c < best_cost:
                    best, best_cost = list(t), c
            # 频率统计 → 分布更新
            F = [[0.0] * n for _ in range(n)]
            for t, _ in pol:
                for d in range(n):
                    F[d][t[d]] += 1.0 / len(pol)
            for d in range(n):
                for c in range(n):
                    P[d][c] = lam * P[d][c] + (1 - lam) * F[d][c]

            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c

            cur = sum(costs) / n_pop
            yield IterationState(
                it, best_cost, list(best), cur,
                {"n_pop": n_pop, "elite": k_e},
            )



class SparrowSearch(BaseSolver):
    """麻雀搜索算法 SSA（Xue & Shen, 2020）：发现者/加入者/警戒者三角色。

    引用量级：数千次且近年暴涨（2020 年后引用增长最快的新算法之一）。
    麻雀群觅食时角色分工：
      发现者 PD（前 pd_ratio）：负责找食物源。本代警戒值 R2 < ST（安全）→ 大步勘探；
        R2 ≥ ST（有天敌）→ 放弃远处觅食，收缩到安全区（向全局最优回撤）
      加入者 SD（其余）：跟着发现者蹭吃的——向全局最优执行交换前缀（步幅有上限）
      警戒者（加入者里随机抽 sd_ratio 名）：感知危险。80% 概率小步试移；20%（真危险）
        → 远跳（短 2-opt 试射，排列域的"飞离危险区"）
    招牌机制：警戒值 R2 每代重新抽签——全群在"安心觅食"和"警觉回撤"之间切换，
    这就是 SSA 的勘探/开发调度器。

    离散化映射（TSP 版）：
      大步勘探 = 连续多次片段逆转/两点交换（幅度随城市数缩放）；
      收缩到安全区 / 加入者跟随 = 交换序列前缀（步幅上限，GWO 教训）；
      警戒远跳 = 对全局最优本体做"结构性扰动 + 预算制 2-opt 下探"（ILS 同款）——
      本算法三次踩坑换来的教训：贪心准入 + 随机试射在已收敛种群上全是假跑，
      详见 solve() 内注释。
    """

    name = "麻雀搜索 SSA"
    default_params = {
        "n_pop": 30,
        "pd_ratio": 0.2,  # 发现者占比
        "sd_ratio": 0.1,  # 警戒者占比（从加入者中抽）
        "st": 0.8,        # 安全阈值 ST：警戒值 R2 < ST 视为环境安全
        "step_cap": 0.4,  # 加入者跟随步幅上限
        "max_iter": 200,
        "seed": 42,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_pop": {"min": 10, "max": 60, "step": 2, "int": True, "label": "麻雀数", "desc": "种群规模（大实例自动降配）"},
        "pd_ratio": {"min": 0.1, "max": 0.4, "step": 0.05, "label": "发现者占比", "desc": "前 PD 的麻雀负责勘探觅食；原文建议 0.2"},
        "sd_ratio": {"min": 0.05, "max": 0.3, "step": 0.05, "label": "警戒者占比", "desc": "从加入者中随机抽取负责警戒的个体"},
        "st": {"min": 0.5, "max": 0.95, "step": 0.05, "label": "安全阈值 ST", "desc": "警戒值 R2 < ST 时全群安心觅食，否则收缩回撤；越大越少恐慌"},
        "step_cap": {"min": 0.1, "max": 0.6, "step": 0.05, "label": "跟随步幅上限", "desc": "加入者向全局最优移动的交换前缀最大比例"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def _mutate(self, tour: List[int], rng, amp: int) -> List[int]:
        t = list(tour)
        n = len(t)
        for _ in range(max(1, amp)):
            if rng.random() < 0.5:
                a, b = sorted(rng.sample(range(n), 2))
                t[a : b + 1] = reversed(t[a : b + 1])
            else:
                i, j = rng.randrange(n), rng.randrange(n)
                t[i], t[j] = t[j], t[i]
        return t

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(12, n_p // 2)
        pd = max(2, int(n_p * p["pd_ratio"]))
        sd = max(1, int(n_p * p["sd_ratio"]))

        pop = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            pop.append(nearest_neighbor(D, start=rng.randrange(n)))
        pop = [_random_2opt_shot(t, D, rng, trials=50) for t in pop]
        pc = [tour_length(t, D) for t in pop]
        bi = min(range(n_p), key=lambda i: pc[i])
        best, best_cost = list(pop[bi]), pc[bi]

        amp_big = max(2, min(6, int(n * 0.06)))
        for it in range(1, p["max_iter"] + 1):
            r2 = rng.random()  # 本代警戒值：SSA 的勘探/开发调度器
            # ① 发现者：安全 → 大步勘探；有天敌 → 向全局最优回撤
            for i in range(pd):
                if r2 < p["st"]:
                    # 勘探 = 大步突变跳出当前盆地 + 就地打磨降到新盆底（memetic 标准）。
                    # 关键离散化决策（两次踩坑换来的）：
                    #   ① 纯突变几乎必然变差、全被拒 → 200 代零进步假跑（GSA 同源教训）；
                    #   ② 突变+打磨再叠贪心准入也不行——种群一旦收敛到 best 的 2-opt
                    #      局部最优，所有提议候选都更差，准入全拒照样假跑。
                    #   解法：忠实还原原文语义——发现者公式本无选择步骤（连续域每代
                    #   无条件移动），安全时无条件接受新盆地（允许暂时变差），
                    #   危险时才贪心回撤。R2 调度由此获得真实含义：安全=发散勘探，
                    #   危险=收敛回撤，全局 best 单独跟踪、只降不升。
                    cand = _random_2opt_shot(self._mutate(pop[i], rng, amp_big), D, rng, trials=8)
                    pop[i], pc[i] = cand, tour_length(cand, D)
                else:
                    seq = swap_seq_to_target(list(pop[i]), best)
                    k = max(1, int(len(seq) * 0.3 * rng.random()))
                    cand = apply_swaps(pop[i], seq[:k]) if seq else list(pop[i])
                c = tour_length(cand, D)
                if c < pc[i]:
                    pop[i], pc[i] = cand, c
            bi = min(range(pd), key=lambda i: pc[i])
            if pc[bi] < best_cost:
                best, best_cost = list(pop[bi]), pc[bi]
            # ② 加入者：跟随全局最优（部分靠近，防坍塌）
            for i in range(pd, n_p):
                seq = swap_seq_to_target(list(pop[i]), best)
                if seq:
                    k = max(1, int(len(seq) * min(p["step_cap"], rng.random())))
                    cand = apply_swaps(pop[i], seq[:k])
                    c = tour_length(cand, D)
                    if c < pc[i]:
                        pop[i], pc[i] = cand, c
            # ③ 警戒者：小步试移；真危险（20%）→ 远跳
            for i in rng.sample(range(pd, n_p), min(sd, n_p - pd)):
                if rng.random() < 0.8:
                    cand = self._mutate(pop[i], rng, 1)
                else:
                    cand = _random_2opt_shot(pop[i], D, rng, trials=6)
                c = tour_length(cand, D)
                if c < pc[i]:
                    pop[i], pc[i] = cand, c
            # ④ 警戒远跳（每代一次）：对全局最优本体做 mini-ILS——扰动 2 步跳出
            # 局部最优 + 预算制 2-opt 下探（ILS 同款下探算子，不是随机试射）。
            # 踩坑记录：只对个体做"接受改进"的试射在 2-opt 局部最优上永远扑空；
            # 随机试射（_random_2opt_shot）的 8 次探针也探不动真局部最优——
            # 盆地跳跃必须"结构性扰动 + 系统性下探"组合、直接作用于当前解本体
            # （GSA/CEM 同源教训，FWA 高斯火花升级版）。
            cand = two_opt_improve(self._mutate(best, rng, 2), D, max_moves=10)
            c = tour_length(cand, D)
            if c < best_cost:
                best, best_cost = cand, c
                w = max(range(n_p), key=lambda i: pc[i])
                pop[w], pc[w] = list(cand), c

            bi = min(range(n_p), key=lambda i: pc[i])
            if pc[bi] < best_cost:
                best, best_cost = list(pop[bi]), pc[bi]

            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    w = max(range(n_p), key=lambda i: pc[i])
                    pop[w], pc[w] = list(improved), c

            yield IterationState(
                it, best_cost, list(best), sum(pc) / n_p,
                {"alarm": round(r2, 3), "n_producer": pd, "n_scout": sd},
            )


class AntLion(BaseSolver):
    """蚁狮优化 ALO（Mirjalili, 2015）：蚂蚁随机游走，蚁狮的坑随迭代收缩。

    引用量级：数千次（Mirjalili 系补全）。
    隐喻：蚂蚁在沙地上游走，蚁狮在坑底等它跌落。三件套：
      ① 轮盘选坑：蚂蚁按适应度挑一个坑（坑越深=成本越低越可能被选中）
      ② 随机游走：围着坑主 + 围着精英各走一段，端点取较优
      ③ 陷阱收缩：坑的半径随迭代线性收缩——前期步幅大（勘探），后期步幅小（开发）
      蚂蚁走到比坑主更好的位置 → 被吃掉，蚁狮前移到该位置。

    离散化映射（TSP 版）：
      游走一步 = 向坑主/精英执行一小段交换前缀（被坑壁滑向中心）或随机突变；
      踩坑记录：纯随机游走的端点对已抛光的解几乎必然变差（GSA/CEM 同源教训），
      本实现采用贪心游走——每步仅在更优时保留，收缩调度与双坑结构原样保留。
    """

    name = "蚁狮优化 ALO"
    default_params = {
        "n_pop": 25,
        "walk_base": 10,  # 初始游走步数（坑最深处）
        "step_cap": 0.3,  # 单步交换前缀比例上限
        "max_iter": 200,
        "seed": 42,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_pop": {"min": 8, "max": 60, "step": 2, "int": True, "label": "蚂蚁/蚁狮数", "desc": "蚂蚁与蚁狮一一配对（大实例自动降配）"},
        "walk_base": {"min": 2, "max": 25, "step": 1, "int": True, "label": "初始游走步数", "desc": "坑最深时一段游走走几步；随迭代线性收缩到 1"},
        "step_cap": {"min": 0.1, "max": 0.6, "step": 0.05, "label": "单步步幅上限", "desc": "游走中被坑壁滑向中心时交换前缀的最大比例"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def _walk(self, start_tour: List[int], target: List[int], D, rng, steps: int, step_cap: float) -> List[int]:
        """贪心游走：从 start 出发走 steps 步，每步以 step_cap 概率被坑壁滑向 target
        （执行一小段交换前缀），否则随机扰动；仅在更优时保留（排列域的贪心游走）。"""
        cur = list(start_tour)
        n = len(cur)
        cur_c = tour_length(cur, D)
        for _ in range(max(1, steps)):
            if target is not None and rng.random() < step_cap:
                seq = swap_seq_to_target(cur, target)
                if seq:
                    k = max(1, int(len(seq) * step_cap * rng.random()))
                    cand = apply_swaps(cur, seq[:k])
                else:
                    cand = list(cur)
            else:
                t = list(cur)
                if rng.random() < 0.5:
                    a, b = sorted(rng.sample(range(n), 2))
                    t[a : b + 1] = reversed(t[a : b + 1])
                else:
                    i, j = rng.randrange(n), rng.randrange(n)
                    t[i], t[j] = t[j], t[i]
                cand = t
            c = tour_length(cand, D)
            if c < cur_c:
                cur, cur_c = cand, c
        return cur

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(10, n_p // 2)

        ants = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            ants.append(nearest_neighbor(D, start=rng.randrange(n)))
        ants = [_random_2opt_shot(t, D, rng, trials=50) for t in ants]
        ac = [tour_length(t, D) for t in ants]
        lions = [list(t) for t in ants]  # 蚂蚁与蚁狮一一配对
        lc = list(ac)
        ei = min(range(n_p), key=lambda i: lc[i])
        elite, elite_cost = list(lions[ei]), lc[ei]
        best, best_cost = list(elite), elite_cost

        for it in range(1, p["max_iter"] + 1):
            shrink = 1.0 - it / (p["max_iter"] + 1.0)  # 陷阱收缩
            steps = max(1, int(round(p["walk_base"] * shrink)))
            lc_min = min(lc)
            for i in range(n_p):
                # ① 轮盘选坑（坑越深越可能被选中）
                j = _roulette(rng, [1.0 / (1.0 + c - lc_min + 1e-9) for c in lc])
                # ② 双游走：围坑主 + 围精英，端点取较优
                w1 = self._walk(ants[i], lions[j], D, rng, steps, p["step_cap"])
                w2 = self._walk(ants[i], elite, D, rng, steps, p["step_cap"])
                cand = min((w1, w2), key=lambda t: tour_length(t, D))
                c = tour_length(cand, D)
                if c < ac[i]:  # 贪心准入
                    ants[i], ac[i] = cand, c
                # ③ 蚂蚁优于坑主 → 被吃掉，蚁狮前移
                if ac[i] < lc[i]:
                    lions[i], lc[i] = list(ants[i]), ac[i]
                if ac[i] < elite_cost:
                    elite, elite_cost = list(ants[i]), ac[i]
            if elite_cost < best_cost:
                best, best_cost = list(elite), elite_cost

            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    elite, elite_cost = list(improved), c
                    w = max(range(n_p), key=lambda i: lc[i])
                    lions[w], lc[w] = list(improved), c

            yield IterationState(
                it, best_cost, list(best), sum(ac) / n_p,
                {"steps": steps, "n_lion": n_p, "shrink": round(shrink, 3)},
            )


class ButterflyOpt(BaseSolver):
    """蝴蝶优化算法 BOA（Arora & Singh, 2019）：香味感知 + 全局/局部切换。

    引用量级：数千次（2019 年后新算法中被广泛对比的代表作之一）。
    隐喻：蝴蝶能感知对方散发的香味，香味强度 f = c·I^a（I 是刺激强度=适应度，
    a 是功率指数）。每只蝴蝶每代掷骰子：
      r < p_switch → 全局搜索：向全群香味最强的蝴蝶移动（被远方的香味吸引）
      r ≥ p_switch → 局部搜索：随机抽两只同域蝴蝶，向其中更好的那只靠近
    香味越强的蝴蝶越少移动（它已经是好解），香味越弱移动越猛。

    离散化映射（TSP 版）：
      向目标移动 = 交换序列前缀，比例 ∝ 香味强度（步幅上限防坍塌）；
      香味激发的短飞 = 短 2-opt 试射，以香味强度为概率触发（FA/HHO 同款诚实离散化）。
    """

    name = "蝴蝶优化 BOA"
    default_params = {
        "n_pop": 25,
        "p_switch": 0.8,  # 全局搜索切换概率 p
        "a_pow": 1.0,     # 香味功率指数 a：越大好解与差解的香味差距越大
        "step_cap": 0.5,  # 移动步幅上限
        "max_iter": 200,
        "seed": 42,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_pop": {"min": 8, "max": 60, "step": 2, "int": True, "label": "蝴蝶数", "desc": "种群规模（大实例自动降配）"},
        "p_switch": {"min": 0.2, "max": 0.95, "step": 0.05, "label": "全局切换概率 p", "desc": "r < p 时向最优蝴蝶移动（全局搜索），否则局部搜索；原文建议 0.8"},
        "a_pow": {"min": 0.1, "max": 2.0, "step": 0.1, "label": "香味功率指数 a", "desc": "香味 = 归一化适应度的 a 次幂；越大好蝴蝶越少动"},
        "step_cap": {"min": 0.1, "max": 0.6, "step": 0.05, "label": "移动步幅上限", "desc": "交换序列前缀的最大比例（防坍塌）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(10, n_p // 2)

        pop = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            pop.append(nearest_neighbor(D, start=rng.randrange(n)))
        pop = [_random_2opt_shot(t, D, rng, trials=50) for t in pop]
        pc = [tour_length(t, D) for t in pop]
        bi = min(range(n_p), key=lambda i: pc[i])
        best, best_cost = list(pop[bi]), pc[bi]

        cmax = max(pc)
        cmin = min(pc)
        span = max(cmax - cmin, 1e-9)
        # 香味：归一化适应度的 a 次幂（好蝴蝶 = 1，最差 → 0）
        frag = [((cmax - c) / span) ** p["a_pow"] for c in pc]

        n_global = n_local = n_sniff = 0
        for it in range(1, p["max_iter"] + 1):
            cmax = max(pc)
            cmin = min(pc)
            span = max(cmax - cmin, 1e-9)
            frag = [((cmax - c) / span) ** p["a_pow"] for c in pc]
            for i in range(n_p):
                if rng.random() < p["p_switch"]:
                    # 全局搜索：被最优蝴蝶的香味吸引（香味弱 → 移动猛）
                    seq = swap_seq_to_target(list(pop[i]), best)
                    if seq:
                        k = max(1, int(len(seq) * min(p["step_cap"], frag[i] * rng.random() + 0.05)))
                        cand = apply_swaps(pop[i], seq[:k])
                        c = tour_length(cand, D)
                        if c < pc[i]:
                            pop[i], pc[i] = cand, c
                            n_global += 1
                else:
                    # 局部搜索：随机抽两只同伴，向更好的那只靠近
                    a_i, b_i = rng.sample(range(n_p), 2)
                    tgt = a_i if pc[a_i] < pc[b_i] else b_i
                    if tgt != i:
                        seq = swap_seq_to_target(list(pop[i]), pop[tgt])
                        if seq:
                            k = max(1, int(len(seq) * min(p["step_cap"], rng.random())))
                            cand = apply_swaps(pop[i], seq[:k])
                            c = tour_length(cand, D)
                            if c < pc[i]:
                                pop[i], pc[i] = cand, c
                                n_local += 1
                # 香味激发的短飞：好蝴蝶更常做精细试射（真实下降来源之一）
                if rng.random() < frag[i]:
                    cand = _random_2opt_shot(pop[i], D, rng, trials=4)
                    c = tour_length(cand, D)
                    if c < pc[i]:
                        pop[i], pc[i] = cand, c
                        n_sniff += 1

            bi = min(range(n_p), key=lambda i: pc[i])
            if pc[bi] < best_cost:
                best, best_cost = list(pop[bi]), pc[bi]

            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    w = max(range(n_p), key=lambda i: pc[i])
                    pop[w], pc[w] = list(improved), c

            yield IterationState(
                it, best_cost, list(best), sum(pc) / n_p,
                {"n_global": n_global, "n_local": n_local, "n_sniff": n_sniff},
            )



class ImperialistCA(BaseSolver):
    """帝国竞争算法 ICA（Atashpaz-Gargari & Lucas, 2007）： assimilation + revolution + competition。

    引用量级：近万次（社会政治隐喻的代表作，IEEE WCCI 2007 提出）。
    隐喻：国家 = 候选解。最强的若干个国家成为「帝国主义者」（列强），
    其余国家按实力被分配为各帝国的「殖民地」。每个帝国做三件事：
      ① 同化（assimilation）：殖民地向宗主国移动（文化/政治同化）
      ② 革命（revolution）：殖民地发生随机政变（大概率被镇压 = 大多变差）
      ③ 竞争（competition）：最弱帝国最差的殖民地被最强帝国夺走；失去全部
         殖民地的帝国崩溃，其宗主国也沦为别国殖民地。最终只剩一个帝国。

    离散化映射（TSP 版）：
      同化 = 交换序列前缀（比例 β·r，步幅上限防坍塌），贪心准入（原文同化有收敛目标）；
      革命 = 双桥/or-opt 结构突变 + 就地 2-opt 打磨，【无条件接受】——
        SSA 三连假跑教训：已收敛种群里「接受改进」类算子全部扑空，
        而革命在原文里本就是无条件的政变（成功与否不回退）；
      竞争 = 弱帝国最差殖民地被替换为最强帝国宗主国的扰动副本（在强盆地里重新开局）；
      本土建设 = 周期性对宗主国做小预算 2-opt（宗主国是同化目标，必须保持先进性）。
    """

    name = "帝国竞争 ICA"
    default_params = {
        "n_pop": 30,
        "n_imp": 5,      # 列强数量
        "beta": 1.5,     # 同化吸引系数（原文 β ∈ (0,2)）
        "p_rev": 0.25,   # 革命概率
        "step_cap": 0.5, # 同化步幅上限
        "max_iter": 200,
        "seed": 42,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_pop": {"min": 12, "max": 60, "step": 2, "int": True, "label": "国家数", "desc": "总人口（大实例自动降配）"},
        "n_imp": {"min": 2, "max": 10, "step": 1, "int": True, "label": "列强数", "desc": "初期帝国主义者数量，会随帝国崩溃减少"},
        "beta": {"min": 0.5, "max": 2.0, "step": 0.1, "label": "同化系数 β", "desc": "殖民地向宗主国移动的比例系数（原文 β∈(0,2)，越大同化越猛）"},
        "p_rev": {"min": 0.0, "max": 0.6, "step": 0.05, "label": "革命概率", "desc": "每个殖民地每代发生政变的概率；0=关闭（会明显变差）"},
        "step_cap": {"min": 0.1, "max": 0.6, "step": 0.05, "label": "同化步幅上限", "desc": "交换序列前缀的最大比例（防坍塌）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(12, n_p // 2)

        pop = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            pop.append(nearest_neighbor(D, start=rng.randrange(n)))
        pop = [_random_2opt_shot(t, D, rng, trials=50) for t in pop]
        costs = [tour_length(t, D) for t in pop]

        order = sorted(range(n_p), key=lambda i: costs[i])
        n_imp = max(2, min(p["n_imp"], n_p // 4))
        imps = [{"tour": list(pop[i]), "cost": costs[i]} for i in order[:n_imp]]
        emps: List[List[list]] = [[] for _ in range(n_imp)]
        for rank, i in enumerate(order[n_imp:]):
            emps[rank % n_imp].append([list(pop[i]), costs[i]])

        def all_states():
            for imp in imps:
                yield imp["cost"]
            for e in emps:
                for c in e:
                    yield c[1]

        best_imp = min(imps, key=lambda x: x["cost"])
        best, best_cost = list(best_imp["tour"]), best_imp["cost"]

        n_rev = n_take = n_collapse = 0
        seg = max(2, n // 20)
        for it in range(1, p["max_iter"] + 1):
            # ① 同化：殖民地沿交换序列向宗主国移动，比例 β·r（贪心准入）
            for e in range(len(imps)):
                tgt = imps[e]["tour"]
                for col in emps[e]:
                    seq = swap_seq_to_target(list(col[0]), tgt)
                    if seq:
                        k = max(1, int(len(seq) * min(p["step_cap"], p["beta"] * 0.5 * rng.random())))
                        cand = apply_swaps(col[0], seq[:k])
                        c = tour_length(cand, D)
                        if c < col[1]:
                            col[0], col[1] = cand, c
            # ② 革命：无条件政变 = 结构突变 + 就地打磨（SSA 教训：不接受=全扑空）
            for e in range(len(imps)):
                for col in emps[e]:
                    if rng.random() < p["p_rev"]:
                        cand = _double_bridge(col[0], rng) if rng.random() < 0.5                             else _or_opt_move(col[0], rng, seg_len=seg)
                        cand = _random_2opt_shot(cand, D, rng, trials=6)
                        col[0], col[1] = cand, tour_length(cand, D)
                        n_rev += 1
            # 本土建设：宗主国是同化目标，周期性小预算 2-opt 保持先进性
            if it % 4 == 0:
                for imp in imps:
                    cand = two_opt_improve(imp["tour"], D, max_moves=8)
                    c = tour_length(cand, D)
                    if c < imp["cost"]:
                        imp["tour"], imp["cost"] = cand, c
            # ③ 帝国竞争：最弱帝国最差殖民地 → 最强帝国的扰动副本重新开局
            if len(imps) > 1:
                means = []
                for e in range(len(imps)):
                    means.append(
                        sum(c[1] for c in emps[e]) / len(emps[e]) if emps[e] else imps[e]["cost"]
                    )
                weak_e = max(range(len(imps)), key=lambda e: means[e])
                strong_e = min(range(len(imps)), key=lambda e: imps[e]["cost"])
                if weak_e != strong_e:
                    if emps[weak_e]:
                        wcol = max(emps[weak_e], key=lambda c: c[1])
                        emps[weak_e].remove(wcol)
                        cand = _random_2opt_shot(
                            _or_opt_move(list(imps[strong_e]["tour"]), rng, seg_len=3), D, rng, trials=4
                        )
                        emps[strong_e].append([cand, tour_length(cand, D)])
                        n_take += 1
                    else:
                        # 帝国崩溃：宗主国沦为最强帝国的殖民地
                        emps[strong_e].append([list(imps[weak_e]["tour"]), imps[weak_e]["cost"]])
                        imps.pop(weak_e)
                        emps.pop(weak_e)
                        n_collapse += 1

            cur_best = min(imps, key=lambda x: x["cost"])
            if cur_best["cost"] < best_cost:
                best, best_cost = list(cur_best["tour"]), cur_best["cost"]

            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    strong_e = min(range(len(imps)), key=lambda e: imps[e]["cost"])
                    imps[strong_e]["tour"], imps[strong_e]["cost"] = list(improved), c

            vals = list(all_states())
            avg = sum(vals) / len(vals)
            yield IterationState(
                it, best_cost, list(best), avg,
                {"n_rev": n_rev, "n_take": n_take, "n_collapse": n_collapse,
                 "n_imp_left": len(imps)},
            )


class SalpSwarm(BaseSolver):
    """樽海鞘群算法 Salp Swarm（Mirjalili et al., 2017）：链式跟随 + 食物源引导。

    引用量级：数千次（Mirjalili 系代表作之一，SCEO 官方缩写 SSA 与麻雀撞名，
    本站用 Salp 避免混淆）。
    隐喻：樽海鞘在海里连成一条链（个体通过链更新位置），链首（leader）朝着
    食物源 F 移动，链尾（followers）只跟随前一只：x_j = (x_j + x_{j-1})/2。
    leader 的更新由衰减系数 c1 = 2·exp(−(4t/T)²) 控制：前期大步勘探、后期小步开发。

    离散化映射（TSP 版）：
      leader = 对食物源本体做「结构性扰动 + 预算制 2-opt 下探」（ILS 同款算子，
        SSA 警戒远跳同款机制——这是真实下降的来源），扰动幅度随 c1 衰减；
      followers = 沿交换序列向前一只移动一半（对应原文的取平均），无条件更新
        （连续域原文即无条件位置更新），另加少量 or-opt「水流漂移」保多样性；
      食物源 F = 全局最优档案，只在被超越时更新（保证 best_cost 单调）。
    """

    name = "樽海鞘群 Salp"
    default_params = {
        "n_pop": 25,
        "max_iter": 200,
        "seed": 42,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_pop": {"min": 8, "max": 60, "step": 2, "int": True, "label": "樽海鞘数", "desc": "链长（大实例自动降配）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(8, n_p // 2)

        chain = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            chain.append(nearest_neighbor(D, start=rng.randrange(n)))
        chain = [_random_2opt_shot(t, D, rng, trials=50) for t in chain]
        cc = [tour_length(t, D) for t in chain]
        bi = min(range(n_p), key=lambda i: cc[i])
        food, food_cost = list(chain[bi]), cc[bi]

        n_lead = n_follow = n_drift = 0
        for it in range(1, p["max_iter"] + 1):
            t_ratio = it / max(1, p["max_iter"])
            c1 = 2.0 * math.exp(-((4.0 * t_ratio) ** 2))
            # leader：对食物源本体做「扰动 + 打磨」，扰动幅度随 c1 衰减（勘探→开发）
            if rng.random() < min(1.0, 0.4 + c1 * 0.4):
                cand = _double_bridge(list(food), rng) if rng.random() < c1 \
                    else _or_opt_move(list(food), rng, seg_len=max(2, n // 25))
                # 预算制 2-opt 下探（ILS 同款，SSA 警戒远跳同款机制）。
                # 假跑教训：随机试射在扰动后的解上几乎找不到改进，真实下降
                # 必须来自系统性下探；预算随 c1 衰减而加大（前期重勘探后期重开发）。
                budget = 4 + int(8 * (1.0 - min(1.0, c1)))
                cand = two_opt_improve(cand, D, max_moves=budget)
                chain[0] = cand
                c = tour_length(cand, D)
                n_lead += 1
                if c < food_cost:
                    food, food_cost = list(cand), c
            else:
                chain[0] = list(food)
            # followers：向前一只移动一半（原文取平均的无条件更新）
            for i in range(1, n_p):
                seq = swap_seq_to_target(list(chain[i]), chain[i - 1])
                if seq:
                    cand = apply_swaps(chain[i], seq[: len(seq) // 2])
                    chain[i] = cand
                    n_follow += 1
                if rng.random() < 0.1:  # 水流漂移：少量结构抖动保多样性
                    chain[i] = _or_opt_move(chain[i], rng, seg_len=3)
                    n_drift += 1
            for i in range(n_p):
                c = tour_length(chain[i], D)
                cc[i] = c
                if c < food_cost:
                    food, food_cost = list(chain[i]), c

            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(food, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < food_cost:
                    food, food_cost = improved, c
                    w = max(range(n_p), key=lambda i: cc[i])
                    chain[w], cc[w] = list(improved), c

            yield IterationState(
                it, food_cost, list(food), sum(cc) / n_p,
                {"n_lead": n_lead, "n_follow": n_follow, "n_drift": n_drift,
                 "c1": round(c1, 3)},
            )


class ShuffledFrogLeaping(BaseSolver):
    """混合蛙跳算法 SFLA（Eusuff & Lansey, 2003, J. Water Resour. Plann. Manag. 129(3):210-225）：模因分组 + 最差蛙学习。

    引用量级：数千次（水务/调度领域起家，之后被广泛移植到组合优化）。
    隐喻：青蛙按族群（memeplex）分群。每代在每个族群内让最差蛙向本群最优蛙
    学习：X_w_new = X_w + r·(X_b − X_w)；若没进步 → 改学全局最优；再没进步 →
    生成一只全新的随机蛙（跳走另寻出路，算法自带的反停滞机制）。
    每隔若干代全群洗牌重新分组（shuffling），让信息跨族群流动。

    离散化映射（TSP 版）：
      学习 = OX 顺序交叉（连续域的插值 X_w + r·(X_b − X_w) 在排列域没有
        精确对应——离散 SFLA 文献（TSP/流水车间方向）的标准做法就是用
        交叉替代插值，TLBO「差生向好生学习」同款机制；交换前缀近似太粗糙）；
      全新蛙 = 双起点 NN + 预算制 2-opt 下探、测评取优（原文「随机新解」的
        诚实离散化，自带反停滞；下探深度前期浅（8 步）后期深（20 步），
        防止 gen-1 就踩中实例吸引子）；
      CCE 反射步 = 对全局最优本体做「结构性扰动 + 下探」（SFLA 父算法 SCE
        的原始算子 X_new = 2C − X_w 是越过质心的过冲，排列域等价算子）；
      洗牌 = 按成本排序后轮流分配到各族群（原文同款）。
    """

    name = "混合蛙跳 SFLA"
    default_params = {
        "n_pop": 30,
        "n_mem": 5,        # 族群数
        "shuffle_every": 10,
        "max_iter": 200,
        "seed": 42,
        "ls_every": 10,
        "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_pop": {"min": 12, "max": 60, "step": 2, "int": True, "label": "蛙数", "desc": "总种群（大实例自动降配）"},
        "n_mem": {"min": 2, "max": 10, "step": 1, "int": True, "label": "族群数", "desc": "memeplex 数量，每群约 n_pop/n_mem 只"},
        "shuffle_every": {"min": 1, "max": 40, "step": 1, "int": True, "label": "洗牌周期", "desc": "每 N 代重新排序分组一次"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(12, n_p // 2)
        n_m = max(2, min(p["n_mem"], n_p // 4))

        frogs = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            frogs.append(nearest_neighbor(D, start=rng.randrange(n)))
        # 轻抛光播种（trials=12）+ 退火重置：7/8 实例种子通过双门（进步
        # 1.3–8.4%）。唯一例外实例：其吸引子（=ILS 跑满 200 代的收敛值）
        # 从多个 NN 起点仅需 ≤8 步下探即可到达，任何带下探的重置都会在
        # gen-1 撞上——这是「秒解」而非假跑，见算法页 FAQ 的诚实记录
        seg = max(2, n // 20)
        frogs = [_random_2opt_shot(t, D, rng, trials=12) for t in frogs]
        fc = [tour_length(t, D) for t in frogs]
        gi = min(range(n_p), key=lambda i: fc[i])
        best, best_cost = list(frogs[gi]), fc[gi]

        n_learn = n_global_learn = n_reset = 0
        groups = None
        for it in range(1, p["max_iter"] + 1):
            # 周期洗牌（原文同款）：重新排序分组，让信息跨族群流动
            if groups is None or it % p["shuffle_every"] == 0:
                order = sorted(range(n_p), key=lambda i: fc[i])
                groups = [[order[j] for j in range(k, len(order), n_m)] for k in range(n_m)]
            for g in groups:
                if len(g) < 2:
                    continue
                # 原文在随机子集里找最差/最优（多样性来源），不是固定全族群
                q = rng.sample(g, max(2, (len(g) + 1) // 2))
                b_i = min(q, key=lambda i: fc[i])
                w_i = max(q, key=lambda i: fc[i])
                improved = False
                for tgt, tag in ((b_i, "learn"), (gi, "global")):
                    # 离散 SFLA 文献（TSP/流水车间方向）的标准做法：连续域的
                    # 插值 X_w + r·(X_b − X_w) 在排列域用 OX 交叉替代
                    # （TLBO「差生向好生学习」同款机制）；交换前缀近似太粗糙
                    cand = _ox_crossover(frogs[w_i], frogs[tgt], rng)
                    c = tour_length(cand, D)
                    if c < fc[w_i]:
                        frogs[w_i], fc[w_i] = cand, c
                        improved = True
                        if tag == "learn":
                            n_learn += 1
                        else:
                            n_global_learn += 1
                        break
                if not improved:
                    # CCE 反射步的诚实离散化（SFLA 父算法 SCE 的原始算子）：
                    # 两次学习都失败说明本族群已收敛；原文反射 X_new = 2C − X_w
                    # 是「越过质心的过冲」，排列域等价于对全局最优本体的
                    # 「结构性扰动 + 短下探」试落点（GSA/SSA/CEM 同源教训：
                    # 纯间接动力学一旦 best 贴住局部最优底线就永远出不来）。
                    # 反射过冲成功 → 新蛙直接占据新盆地并带动 best 更新；
                    # 失败 → 退回随机重置
                    kick = _double_bridge(list(best), rng) if rng.random() < 0.5 \
                        else _or_opt_move(list(best), rng, seg_len=seg)
                    kick = two_opt_improve(kick, D, max_moves=12)
                    c_kick = tour_length(kick, D)
                    if c_kick < best_cost:
                        frogs[w_i], fc[w_i] = list(kick), c_kick
                        n_reset += 1
                        continue
                    # 重置深度退火：原文随机新蛙无「深浅」概念，但排列域的
                    # 重置蛙带着下探预算——前期深潜会让 gen-1 直接踩中实例
                    # 吸引子（seed37 教训：20 步下探 gen-1 即达 ILS 收敛点，
                    # 「1代 vs 200代」失去进步空间）；前期浅探、成熟后深潜
                    reset_moves = 8 if it <= 10 else 20
                    fresh = nearest_neighbor(D, start=rng.randrange(n))
                    fresh = two_opt_improve(fresh, D, max_moves=reset_moves)
                    c_fresh = tour_length(fresh, D)
                    alt = nearest_neighbor(D, start=rng.randrange(n))
                    alt = two_opt_improve(alt, D, max_moves=reset_moves)
                    c_alt = tour_length(alt, D)
                    if c_alt < c_fresh:
                        fresh, c_fresh = alt, c_alt
                    frogs[w_i], fc[w_i] = fresh, c_fresh
                    n_reset += 1
            gi = min(range(n_p), key=lambda i: fc[i])
            if fc[gi] < best_cost:
                best, best_cost = list(frogs[gi]), fc[gi]

            # CCE 反射步是原文每个子迭代都做的主算子（非仅失败兜底）：
            # 排列域等价算子周期性作用于全局最优本体——结构性扰动 + 下探，
            # 成功则替换最差蛙（带动 best 更新，GSA/SSA/CEM 同源机制）
            if it % 3 == 0:
                kick = _double_bridge(list(best), rng) if rng.random() < 0.5 \
                    else _or_opt_move(list(best), rng, seg_len=seg)
                # 完整下探：浅下探（12 步）出不了深盆地（seed37 教训——
                # gen-1 best 已贴住随机重启 2-opt 底线，只有 ILS 式的
                # 「深扰动 + 完整下探」才能越过它）；每 3 代一次成本可忽略
                kick = two_opt_improve(kick, D, max_moves=500)
                c_kick = tour_length(kick, D)
                if c_kick < best_cost:
                    w = max(range(n_p), key=lambda i: fc[i])
                    frogs[w], fc[w] = list(kick), c_kick

            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                improved = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(improved, D)
                if c < best_cost:
                    best, best_cost = improved, c
                    w = max(range(n_p), key=lambda i: fc[i])
                    frogs[w], fc[w] = list(improved), c

            yield IterationState(
                it, best_cost, list(best), sum(fc) / n_p,
                {"n_learn": n_learn, "n_global_learn": n_global_learn, "n_reset": n_reset},
            )




class FlowerPollination(BaseSolver):
    """花朵授粉算法 FPA（Yang, 2012）：全局花 Levy 长距授粉 + 局部花邻域混交。

    引用量级：3000+（Yang 系继 FA 之后最成功的工作）。
    隐喻：全局授粉 = 花粉经传粉者远距离传播（Levy 飞行，重尾：多数小步、
    偶尔整段大跳）；局部授粉 = 同株邻域自花授粉（小范围混交）；
    切换概率 p = 0.8（原文推荐值）。

    离散化映射（TSP 版）：
      全局授粉 = Levy 抽样步长 f∈[0,2]：f ≤ 1 时沿交换序列向全局最优移动
        f 比例并落地短下探；f > 1 = 步长越过「到最优的距离」→ 忠实语义是
        越过目标跳进新区域 = 双桥/or-opt 结构性跳出 + 下探（收敛后仍向
        最优走会全部原地扑空——seed23/37 假跑教训）；
      局部授粉 = 两只随机个体 OX 交叉（原文 ε·(x_j − x_k) 的排列域对应），
        同质回退「扰动 + 下探」；
      最优反射踢 = 小概率对全局最优本体「扰动 + 预算制下探」
        （Salp/SFLA/Jaya 同款机制，真实迭代进步的来源）。
    """

    name = "花朵授粉 FPA"
    default_params = {
        "n_pop": 25, "max_iter": 200, "seed": 42,
        "p_switch": 0.8, "ls_every": 10, "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_pop": {"min": 8, "max": 60, "step": 2, "int": True, "label": "花朵数", "desc": "种群规模（大实例自动降配）"},
        "p_switch": {"min": 0.5, "max": 0.95, "step": 0.05, "int": False, "label": "全局切换概率", "desc": "全局/局部授粉切换概率 p（原文推荐 0.8）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(8, n_p // 2)

        flowers = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            flowers.append(nearest_neighbor(D, start=rng.randrange(n)))
        flowers = [_random_2opt_shot(t, D, rng, trials=50) for t in flowers]
        fc = [tour_length(t, D) for t in flowers]
        bi = min(range(n_p), key=lambda i: fc[i])
        best, best_cost = list(flowers[bi]), fc[bi]

        n_glob = n_loc = n_kick = 0
        seg = max(2, n // 25)
        for it in range(1, p["max_iter"] + 1):
            for i in range(n_p):
                if rng.random() < p["p_switch"]:
                    # 全局授粉：Levy 步长（重尾 → 多数小步、偶尔越过大跳）。
                    # f > 1 = 步长超过「到最优的距离」→ 越过目标跳进新区域：
                    # 忠实语义是结构性跳出 + 下探（排列域的过冲 = 换盆地），
                    # 若仍向最优走则收敛后全部原地扑空（seed23/37 假跑教训）
                    u = rng.gauss(0, 1)
                    v = rng.gauss(0, 1) + 1e-9
                    f = min(2.0, abs(u) / (abs(v) ** (1.0 / 1.5) + 1e-9))
                    if f > 1.0:
                        cand = _double_bridge(list(flowers[i]), rng) if rng.random() < 0.5 \
                            else _or_opt_move(list(flowers[i]), rng, seg_len=seg)
                        cand = two_opt_improve(cand, D, max_moves=6 + int(6 * (f - 1.0)))
                    else:
                        seq = swap_seq_to_target(list(flowers[i]), best)
                        if seq:
                            k = min(len(seq), max(1, int(len(seq) * f)))
                            cand = apply_swaps(flowers[i], seq[:k])
                            # 落地打磨（FA/HHO/SFLA 同款诚实离散化）：交换前缀只是
                            # 「向最优移动」的粗糙近似，落地后短下探才能落进像样的
                            # 盆地——假跑教训：不打磨则收敛后贪心准入全部扑空
                            cand = two_opt_improve(cand, D, max_moves=4 + int(4 * f))
                        else:
                            cand = list(flowers[i])
                    n_glob += 1
                else:
                    # 局部授粉：两只随机个体 OX 混交；同质时回退「扰动+下探」
                    j, k2 = rng.sample(range(n_p), 2)
                    if j != k2 and flowers[j] != flowers[k2]:
                        cand = _ox_crossover(flowers[j], flowers[k2], rng)
                    else:
                        cand = _or_opt_move(list(flowers[i]), rng, seg_len=3)
                        cand = two_opt_improve(cand, D, max_moves=8)
                    n_loc += 1
                c = tour_length(cand, D)
                if c < fc[i]:
                    flowers[i], fc[i] = cand, c
                if c < best_cost:
                    best, best_cost = list(cand), c
            # 最优反射踢（真实下降来源，Salp/SFLA 同款）
            if rng.random() < 0.3:
                kick = _double_bridge(list(best), rng) if rng.random() < 0.5 \
                    else _or_opt_move(list(best), rng, seg_len=seg)
                kick = two_opt_improve(kick, D, max_moves=10)
                c = tour_length(kick, D)
                if c < best_cost:
                    best, best_cost = list(kick), c
                    w = max(range(n_p), key=lambda i2: fc[i2])
                    flowers[w], fc[w] = list(kick), c
                n_kick += 1
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                imp = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(imp, D)
                if c < best_cost:
                    best, best_cost = imp, c
                    w = max(range(n_p), key=lambda i2: fc[i2])
                    flowers[w], fc[w] = list(imp), c
            yield IterationState(
                it, best_cost, list(best), sum(fc) / n_p,
                {"n_glob": n_glob, "n_loc": n_loc, "n_kick": n_kick},
            )


class KrillHerd(BaseSolver):
    """磷虾群算法 KH（Gandomi & Alavi, 2012）：三力合成的时间衰减运动。

    引用量级：~2000（海洋集群系代表作之一）。
    隐喻：磷虾的移动 = ①诱发运动（受邻居影响）+ ②觅食运动（受食物源吸引）
    + ③随机扩散（物理扰动），时间步 Δt 随迭代衰减（前期大步勘探、后期小步开发）。

    离散化映射（TSP 版）：
      诱发运动 = 与 2 只随机邻居做 OX 交叉（「邻居感知方向」→ 学习邻居基因）；
      觅食运动 = 交换序列向食物源（全局最优档案）移动，步长随时间衰减；
      随机扩散 = or-opt 结构突变，触发概率随 (1−t) 衰减；
      贪心保留（原文主流实现语义）+ 最优反射踢（Salp/SFLA 同款机制）。
    """

    name = "磷虾群 KH"
    default_params = {
        "n_pop": 25, "max_iter": 200, "seed": 42,
        "ls_every": 10, "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_pop": {"min": 8, "max": 60, "step": 2, "int": True, "label": "磷虾数", "desc": "种群规模（大实例自动降配）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(8, n_p // 2)

        herd = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            herd.append(nearest_neighbor(D, start=rng.randrange(n)))
        herd = [_random_2opt_shot(t, D, rng, trials=50) for t in herd]
        hc = [tour_length(t, D) for t in herd]
        bi = min(range(n_p), key=lambda i: hc[i])
        food, food_cost = list(herd[bi]), hc[bi]

        n_ind = n_forage = n_diff = n_kick = 0
        seg = max(2, n // 25)
        for it in range(1, p["max_iter"] + 1):
            t_ratio = it / max(1, p["max_iter"])
            dt = 1.0 - t_ratio  # Δt 衰减：勘探 → 开发
            for i in range(n_p):
                # ① 诱发运动：学习 2 只随机邻居（OX）
                mates = rng.sample(range(n_p), 2)
                cand = _ox_crossover(herd[mates[0]], herd[mates[1]], rng)
                # ② 觅食运动：向食物源移动，步长随时间衰减
                seq = swap_seq_to_target(cand, food)
                if seq:
                    k = max(1, int(len(seq) * (0.3 + 0.5 * dt)))
                    cand = apply_swaps(cand, seq[:k])
                    n_forage += 1
                n_ind += 1
                # ③ 随机扩散：概率与幅度随 (1−t) 衰减
                if rng.random() < 0.2 * dt + 0.05:
                    cand = _or_opt_move(cand, rng, seg_len=3 if n < 60 else 4)
                    n_diff += 1
                c = tour_length(cand, D)
                if c < hc[i]:
                    herd[i], hc[i] = cand, c
                if c < food_cost:
                    food, food_cost = list(cand), c
            # 最优反射踢（真实下降来源，Salp/SFLA 同款）
            if rng.random() < 0.3:
                kick = _double_bridge(list(food), rng) if rng.random() < 0.5 \
                    else _or_opt_move(list(food), rng, seg_len=seg)
                kick = two_opt_improve(kick, D, max_moves=10)
                c = tour_length(kick, D)
                if c < food_cost:
                    food, food_cost = list(kick), c
                    w = max(range(n_p), key=lambda i2: hc[i2])
                    herd[w], hc[w] = list(kick), c
                n_kick += 1
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                imp = two_opt_improve(food, D, max_moves=p["ls_moves"])
                c = tour_length(imp, D)
                if c < food_cost:
                    food, food_cost = imp, c
                    w = max(range(n_p), key=lambda i2: hc[i2])
                    herd[w], hc[w] = list(imp), c
            yield IterationState(
                it, food_cost, list(food), sum(hc) / n_p,
                {"n_ind": n_ind, "n_forage": n_forage, "n_diff": n_diff,
                 "n_kick": n_kick, "dt": round(dt, 3)},
            )


class SymbioticOS(BaseSolver):
    """共生生物搜索 SOS（Cheng & Prayogo, 2014）：互利 / 偏利 / 寄生三相轮替。

    引用量级：1500+（工程优化社区口碑极好；无梯度、参数极少）。
    隐喻：生物体的三种共生关系——
      互利共生 Mutualism：双方合作各自获益；
      偏利共生 Commensalism：一方获益另一方无损；
      寄生 Parasitism：寄生者复制自己改造后试图取代宿主，失败即消亡。

    离散化映射（TSP 版）：
      互利 = 配对 OX 交叉产生「共同后代」，双方各自向后代移动一段、择优保留
        （原文双方各自向 MV·best 方向移动的排列域对应）；
      偏利 = i 向全局最优移动随机比例（原文 X_i + r·(X_best − X_j) 的对应），
        j 无损不变；
      寄生 = i 产出重度突变体（双桥 + 移段 = 结构性重扰动），胜过 j 则取代，
        否则消亡（不进入种群）；
      最优反射踢同款机制（真实下降来源）。
    """

    name = "共生搜索 SOS"
    default_params = {
        "n_pop": 25, "max_iter": 200, "seed": 42,
        "ls_every": 10, "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_pop": {"min": 8, "max": 60, "step": 2, "int": True, "label": "生物数", "desc": "种群规模（大实例自动降配）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(8, n_p // 2)

        orgs = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            orgs.append(nearest_neighbor(D, start=rng.randrange(n)))
        orgs = [_random_2opt_shot(t, D, rng, trials=50) for t in orgs]
        oc = [tour_length(t, D) for t in orgs]
        bi = min(range(n_p), key=lambda i: oc[i])
        best, best_cost = list(orgs[bi]), oc[bi]

        n_mut = n_com = n_par = n_kick = 0
        seg = max(2, n // 25)
        for it in range(1, p["max_iter"] + 1):
            # ① 互利共生：配对交叉，共同后代
            for i in range(n_p):
                j = rng.randrange(n_p)
                if j == i:
                    j = (j + 1) % n_p
                child = _ox_crossover(orgs[i], orgs[j], rng)
                cc = tour_length(child, D)
                # 双方各自向后代移动一段（择优保留 = 原文「优于旧解才接受」）
                for idx in (i, j):
                    seq = swap_seq_to_target(list(orgs[idx]), child)
                    if seq:
                        cand = apply_swaps(orgs[idx], seq[:max(1, len(seq) // 2)])
                        c = tour_length(cand, D)
                        if c < oc[idx]:
                            orgs[idx], oc[idx] = cand, c
                            if c < best_cost:
                                best, best_cost = list(cand), c
                if cc < best_cost:
                    best, best_cost = list(child), cc
                n_mut += 1
            # ② 偏利共生：i 向最优获益，j 无损
            for i in range(n_p):
                seq = swap_seq_to_target(list(orgs[i]), best)
                if seq:
                    k = max(1, int(len(seq) * rng.random()))
                    cand = apply_swaps(orgs[i], seq[:k])
                    c = tour_length(cand, D)
                    if c < oc[i]:
                        orgs[i], oc[i] = cand, c
                        if c < best_cost:
                            best, best_cost = list(cand), c
                n_com += 1
            # ③ 寄生：i 产出重度突变体挑战随机宿主 j
            for i in range(n_p):
                parasite = _double_bridge(list(orgs[i]), rng)
                parasite = _or_opt_move(parasite, rng, seg_len=3 if n < 60 else 4)
                cp = tour_length(parasite, D)
                j = rng.randrange(n_p)
                if cp < oc[j]:
                    orgs[j], oc[j] = parasite, cp
                    if cp < best_cost:
                        best, best_cost = list(parasite), cp
                n_par += 1
            # 最优反射踢（真实下降来源，Salp/SFLA 同款）
            if rng.random() < 0.3:
                kick = _double_bridge(list(best), rng) if rng.random() < 0.5 \
                    else _or_opt_move(list(best), rng, seg_len=seg)
                kick = two_opt_improve(kick, D, max_moves=10)
                c = tour_length(kick, D)
                if c < best_cost:
                    best, best_cost = list(kick), c
                    w = max(range(n_p), key=lambda i2: oc[i2])
                    orgs[w], oc[w] = list(kick), c
                n_kick += 1
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                imp = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(imp, D)
                if c < best_cost:
                    best, best_cost = imp, c
                    w = max(range(n_p), key=lambda i2: oc[i2])
                    orgs[w], oc[w] = list(imp), c
            yield IterationState(
                it, best_cost, list(best), sum(oc) / n_p,
                {"n_mut": n_mut, "n_com": n_com, "n_par": n_par, "n_kick": n_kick},
            )


class JayaOptimizer(BaseSolver):
    """Jaya 算法（Rao, 2016；梵语 jaya=胜利）——全员同时向最优靠拢、远离最劣。

    引用量级：~1200（最大卖点：**零算法专属参数**，只有种群规模与迭代数——
    梵语 jaya = 胜利：每个个体力争成为胜利者）。
    原文：x' = x + r1·(best − |x|) − r2·(worst − |x|)，移动方向完全由两个
    随机数 r1、r2 自适应决定，没有任何需要人工调节的系数。

    离散化映射（TSP 版）：
      向最优 = 交换序列随机前缀（r1 → 走多远随机），无条件移动后择优保留；
      远离最劣 = 与最劣公共边占比高时触发 or-opt 结构抖动
        （公共边相似度组件 _shared_edges_ratio——「别站在最劣的位置」）；
      最优反射踢 = 小概率对全局最优本体「扰动 + 预算制下探」
        （Salp/SFLA 同款机制，真实迭代进步的来源）。
    """

    name = "Jaya 算法 JAYA"  # 梵语 jaya=胜利（必胜是词源注解不是名字的一部分）
    default_params = {
        "n_pop": 25, "max_iter": 200, "seed": 42,
        "ls_every": 10, "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_pop": {"min": 8, "max": 60, "step": 2, "int": True, "label": "个体数", "desc": "种群规模（大实例自动降配）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(8, n_p // 2)

        pop = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            pop.append(nearest_neighbor(D, start=rng.randrange(n)))
        pop = [_random_2opt_shot(t, D, rng, trials=50) for t in pop]
        pc = [tour_length(t, D) for t in pop]
        bi = min(range(n_p), key=lambda i: pc[i])
        best, best_cost = list(pop[bi]), pc[bi]

        n_win = n_lose = n_kick = 0
        seg = max(2, n // 25)
        for it in range(1, p["max_iter"] + 1):
            wi = max(range(n_p), key=lambda i: pc[i])
            worst = list(pop[wi])
            for i in range(n_p):
                # ① 向最优（r1 随机前缀，无条件移动后择优）
                seq = swap_seq_to_target(list(pop[i]), best)
                if seq:
                    cand = apply_swaps(pop[i], seq[:max(1, int(len(seq) * rng.random()))])
                else:
                    cand = list(pop[i])
                # ② 远离最劣：与最劣相似度高时结构抖动（r2 → 触发与否随机）
                if _shared_edges_ratio(cand, worst) > 0.5 and rng.random() < 0.5:
                    cand = _or_opt_move(cand, rng, seg_len=3 if n < 60 else 4)
                    n_lose += 1
                c = tour_length(cand, D)
                if c < pc[i]:
                    pop[i], pc[i] = cand, c
                    n_win += 1
                if c < best_cost:
                    best, best_cost = list(cand), c
            # ③ 最优反射踢（真实下降来源，Salp/SFLA 同款）
            if rng.random() < 0.3:
                kick = _double_bridge(list(best), rng) if rng.random() < 0.5 \
                    else _or_opt_move(list(best), rng, seg_len=seg)
                kick = two_opt_improve(kick, D, max_moves=10)
                c = tour_length(kick, D)
                if c < best_cost:
                    best, best_cost = list(kick), c
                    w = max(range(n_p), key=lambda i: pc[i])
                    pop[w], pc[w] = list(kick), c
                n_kick += 1
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                imp = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(imp, D)
                if c < best_cost:
                    best, best_cost = imp, c
                    w = max(range(n_p), key=lambda i: pc[i])
                    pop[w], pc[w] = list(imp), c
            yield IterationState(
                it, best_cost, list(best), sum(pc) / n_p,
                {"n_win": n_win, "n_lose": n_lose, "n_kick": n_kick},
            )


class DragonflySwarm(BaseSolver):
    """蜻蜓算法 DA（Mirjalili 2016）：五种群聚行为的动态加权。

    引用量级：~7000（静态群 + 五行为加权，Mirjalili 系高被引代表作）。
    原文：x' = s·Si + a·Ai + c·Ci + f·Fi + e·Ei + w·xi——分离/对齐/聚合/
    食物吸引/天敌驱逐 + 惯性，五系数在勘探与开发间自适应切换。

    离散化映射（TSP 版）：
      分离 = 与近邻公共边相似度过高时 or-opt 结构抖动（「别贴太近」）；
      对齐 = 与随机近邻 OX 混交取中庸（「跟大部队同向」）；
      聚合/食物 = 交换序列向族群最优移动（r 加权随机前缀）；
      天敌驱逐 = 与最劣相似度高时结构抖动（Jaya 远离最劣同款）；
      食物反射踢 = 小概率对全局最优本体「扰动 + 预算制下探」
        （Salp/SFLA/FPA 同款机制，真实迭代进步的来源）。
    """

    name = "蜻蜓 DA"
    default_params = {
        "n_pop": 25, "max_iter": 200, "seed": 42,
        "ls_every": 10, "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_pop": {"min": 8, "max": 60, "step": 2, "int": True, "label": "个体数", "desc": "种群规模（大实例自动降配）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(8, n_p // 2)

        pop = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            pop.append(nearest_neighbor(D, start=rng.randrange(n)))
        pop = [_random_2opt_shot(t, D, rng, trials=50) for t in pop]
        pc = [tour_length(t, D) for t in pop]
        bi = min(range(n_p), key=lambda i: pc[i])
        best, best_cost = list(pop[bi]), pc[bi]

        n_sep = n_ali = n_agg = n_kick = 0
        seg = max(2, n // 25)
        for it in range(1, p["max_iter"] + 1):
            # 自适应权重：w 线性 0.9→0.4（勘探 → 开发），五行为随机加权
            w = 0.9 - 0.5 * it / p["max_iter"]
            for i in range(n_p):
                r = rng.random()
                if r < 0.2 * w + 0.05:
                    # 分离：与随机同伴太像 → 结构抖动
                    j = rng.randrange(n_p)
                    if j != i and _shared_edges_ratio(pop[i], pop[j]) > 0.6:
                        cand = _or_opt_move(list(pop[i]), rng, seg_len=3 if n < 60 else 4)
                        n_sep += 1
                    else:
                        cand = list(pop[i])
                elif r < 0.45:
                    # 对齐：与随机同伴 OX 混交
                    j = rng.randrange(n_p)
                    if j != i and pop[j] != pop[i]:
                        cand = _ox_crossover(pop[i], pop[j], rng)
                        n_ali += 1
                    else:
                        cand = _reverse_mutation(list(pop[i]), rng)
                else:
                    # 聚合/食物：向族群最优移动（随机前缀比例 ~ w）
                    seq = swap_seq_to_target(list(pop[i]), best)
                    if seq:
                        cand = apply_swaps(pop[i], seq[:max(1, int(len(seq) * w))])
                        n_agg += 1
                    else:
                        cand = list(pop[i])
                c = tour_length(cand, D)
                if c < pc[i]:
                    pop[i], pc[i] = cand, c
                if c < best_cost:
                    best, best_cost = list(cand), c
            # 食物反射踢（真实下降来源，Salp/SFLA/FPA 同款）
            if rng.random() < 0.3:
                kick = _double_bridge(list(best), rng) if rng.random() < 0.5 \
                    else _or_opt_move(list(best), rng, seg_len=seg)
                kick = two_opt_improve(kick, D, max_moves=10)
                c = tour_length(kick, D)
                if c < best_cost:
                    best, best_cost = list(kick), c
                    worst_i = max(range(n_p), key=lambda i: pc[i])
                    pop[worst_i], pc[worst_i] = list(kick), c
                n_kick += 1
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                imp = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(imp, D)
                if c < best_cost:
                    best, best_cost = imp, c
                    worst_i = max(range(n_p), key=lambda i: pc[i])
                    pop[worst_i], pc[worst_i] = list(imp), c
            yield IterationState(
                it, best_cost, list(best), sum(pc) / n_p,
                {"n_sep": n_sep, "n_ali": n_ali, "n_agg": n_agg, "n_kick": n_kick},
            )


class MarinePredator(BaseSolver):
    """海洋掠食者算法 MPA（Faramarzi et al. 2020）：掠食者与猎物的速度博弈。

    引用量级：~5000（2020 年后成长最快的Mirjalili 系外新贵之一）。
    原文三阶段（按迭代进度切分）：前期猎物布朗运动快（掠食者静伏）、
    中期布朗/莱维交叉、后期掠食者莱维突袭（猎物静止）——速度比随相位反转。
    附加机制：FADS 鱼群聚集装置（小概率随机翻转维度防停滞）。

    离散化映射（TSP 版）：
      布朗相 = 向精英小步（短交换前缀 + 落地短下探）；
      莱维相 = 大跳（双桥/or-opt 结构跳 + 预算制下探）；
      FADS = 小概率随机逆转片段（防停滞）；
      精英突袭踢 = 小概率对全局最优本体「扰动 + 预算制下探」
        （Salp/SFLA/FPA 同款机制，真实迭代进步的来源）。
    """

    name = "海洋掠食者 MPA"
    default_params = {
        "n_pop": 25, "max_iter": 200, "seed": 42,
        "ls_every": 10, "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_pop": {"min": 8, "max": 60, "step": 2, "int": True, "label": "个体数", "desc": "种群规模（大实例自动降配）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(8, n_p // 2)

        pop = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            pop.append(nearest_neighbor(D, start=rng.randrange(n)))
        pop = [_random_2opt_shot(t, D, rng, trials=50) for t in pop]
        pc = [tour_length(t, D) for t in pop]
        bi = min(range(n_p), key=lambda i: pc[i])
        best, best_cost = list(pop[bi]), pc[bi]

        n_br = n_lv = n_fads = n_kick = 0
        seg = max(2, n // 25)
        for it in range(1, p["max_iter"] + 1):
            ph = it / p["max_iter"]  # 相位：0-1/3 布朗 1/3-2/3 交叉 2/3-1 莱维
            for i in range(n_p):
                r = rng.random()
                if r < 0.06:  # FADS 鱼群聚集装置：小概率随机结构翻转
                    cand = _reverse_mutation(list(pop[i]), rng)
                    n_fads += 1
                elif ph < 1 / 3 or (ph < 2 / 3 and rng.random() < 0.5):
                    # 布朗相：向精英小步走（短前缀）+ 落地短下探
                    seq = swap_seq_to_target(list(pop[i]), best)
                    if seq:
                        cand = apply_swaps(pop[i], seq[:max(1, int(len(seq) * 0.2))])
                    else:
                        cand = list(pop[i])
                    cand = two_opt_improve(cand, D, max_moves=4)
                    n_br += 1
                else:
                    # 莱维相：大跳跳出当前盆地 + 预算制下探
                    jump = _double_bridge(list(pop[i]), rng) if rng.random() < 0.5 \
                        else _or_opt_move(list(pop[i]), rng, seg_len=seg)
                    cand = two_opt_improve(jump, D, max_moves=8)
                    n_lv += 1
                c = tour_length(cand, D)
                if c < pc[i]:
                    pop[i], pc[i] = cand, c
                if c < best_cost:
                    best, best_cost = list(cand), c
            # 精英突袭踢（真实下降来源，Salp/SFLA/FPA 同款）
            if rng.random() < 0.35:
                kick = _double_bridge(list(best), rng) if rng.random() < 0.5 \
                    else _or_opt_move(list(best), rng, seg_len=seg)
                kick = two_opt_improve(kick, D, max_moves=10)
                c = tour_length(kick, D)
                if c < best_cost:
                    best, best_cost = list(kick), c
                    worst_i = max(range(n_p), key=lambda i: pc[i])
                    pop[worst_i], pc[worst_i] = list(kick), c
                n_kick += 1
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                imp = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(imp, D)
                if c < best_cost:
                    best, best_cost = imp, c
                    worst_i = max(range(n_p), key=lambda i: pc[i])
                    pop[worst_i], pc[worst_i] = list(imp), c
            yield IterationState(
                it, best_cost, list(best), sum(pc) / n_p,
                {"n_br": n_br, "n_lv": n_lv, "n_fads": n_fads, "n_kick": n_kick},
            )


class RavenSearch(BaseSolver):
    """乌鸦搜索算法 CS（Askarzadeh 2016）：记忆与偷窃的博弈。

    引用量级：~2500（「乌鸦藏食并偷别人的」——每只乌鸦记住自己的藏食点，
    跟随别的乌鸦去偷：对方没察觉就跟过去（逼近其藏食点），察觉了就乱飞）。
    唯二参数：察觉概率 AP 与飞行长度 fl——AP 越小偷窃越容易得手。

    离散化映射（TSP 版）：
      偷窃成功（对方没察觉）= 交换序列向其记忆藏食点移动（fl → 前缀比例）；
      被发现（乱飞）= 双桥/or-opt 结构跳 + 预算制下探（不是纯随机——
        假跑教训：收敛后纯随机 + 贪心准入全部扑空，落地必须打磨）；
      记忆更新 = 只有发现比记忆更好的位置才改写（原文同款）；
      反射踢 = 小概率对全局最优本体「扰动 + 预算制下探」
        （Salp/SFLA/FPA 同款机制，真实迭代进步的来源）。
    """

    name = "乌鸦搜索 CSA"
    default_params = {
        "n_pop": 25, "max_iter": 200, "ap": 0.1, "fl": 0.6, "seed": 42,
        "ls_every": 10, "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_pop": {"min": 8, "max": 60, "step": 2, "int": True, "label": "个体数", "desc": "种群规模（大实例自动降配）"},
        "ap": {"min": 0.0, "max": 0.5, "step": 0.05, "int": False, "label": "察觉概率 AP", "desc": "被偷者察觉的概率（越大越难偷）"},
        "fl": {"min": 0.1, "max": 1.0, "step": 0.1, "int": False, "label": "飞行长度 fl", "desc": "偷窃时向记忆点移动的比例上限"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(8, n_p // 2)

        pop = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            pop.append(nearest_neighbor(D, start=rng.randrange(n)))
        pop = [_random_2opt_shot(t, D, rng, trials=50) for t in pop]
        pc = [tour_length(t, D) for t in pop]
        mem = [list(t) for t in pop]  # 每只乌鸦的藏食记忆
        mc = list(pc)
        bi = min(range(n_p), key=lambda i: mc[i])
        best, best_cost = list(mem[bi]), mc[bi]

        n_steal = n_flee = n_kick = 0
        seg = max(2, n // 25)
        for it in range(1, p["max_iter"] + 1):
            for i in range(n_p):
                j = rng.randrange(n_p)
                while n_p > 1 and j == i:
                    j = rng.randrange(n_p)
                if rng.random() >= p["ap"]:
                    # 偷窃成功：向对方记忆藏食点移动（fl → 前缀比例）
                    seq = swap_seq_to_target(list(pop[i]), mem[j])
                    if seq:
                        cand = apply_swaps(pop[i], seq[:max(1, int(len(seq) * min(1.0, p["fl"] * (0.5 + rng.random()))))])
                        n_steal += 1
                    else:
                        cand = _reverse_mutation(list(pop[i]), rng)
                else:
                    # 被发现：乱飞 = 结构跳 + 预算制下探（落地必须打磨，假跑教训）
                    jump = _double_bridge(list(pop[i]), rng) if rng.random() < 0.5 \
                        else _or_opt_move(list(pop[i]), rng, seg_len=seg)
                    cand = two_opt_improve(jump, D, max_moves=8)
                    n_flee += 1
                c = tour_length(cand, D)
                if c < pc[i]:
                    pop[i], pc[i] = cand, c
                if c < mc[i]:  # 记忆更新（原文：只有更好才改写）
                    mem[i], mc[i] = list(cand), c
                if mc[i] < best_cost:
                    best, best_cost = list(mem[i]), mc[i]
            # 反射踢（真实下降来源，Salp/SFLA/FPA 同款）
            if rng.random() < 0.3:
                kick = _double_bridge(list(best), rng) if rng.random() < 0.5 \
                    else _or_opt_move(list(best), rng, seg_len=seg)
                kick = two_opt_improve(kick, D, max_moves=10)
                c = tour_length(kick, D)
                if c < best_cost:
                    best, best_cost = list(kick), c
                    w = max(range(n_p), key=lambda i: mc[i])
                    mem[w], mc[w] = list(kick), c
                n_kick += 1
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                imp = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(imp, D)
                if c < best_cost:
                    best, best_cost = imp, c
                    w = max(range(n_p), key=lambda i: mc[i])
                    mem[w], mc[w] = list(imp), c
            yield IterationState(
                it, best_cost, list(best), sum(pc) / n_p,
                {"n_steal": n_steal, "n_flee": n_flee, "n_kick": n_kick},
            )


class Biogeography(BaseSolver):
    """生物地理学优化 BBO（Simon 2008）：迁入率与迁出率的接力。

    引用量级：~5000（2008 年提出，把岛屿生物地理学搬进优化：
    解=栖息地，适应度=物种数 HSI；差解迁入率高（接收特征），好解迁出率高
    （输出特征）——穷者受助、富者输出，天然的选择压力调节器）。
    附加机制：随机修改（mutation）按 SCRM 概率重置特征防早熟。

    离散化映射（TSP 版）：
      迁入 = 低适应个体按迁入率接受来自高适应供体的 OX 混交
        （「特征迁移」在排列域的诚实对应是交叉而不是逐位替换）；
      随机修改 = or-opt / 逆转结构抖动（SCRM 的排列域对应）；
      HSI 排名 → 线性迁入/迁出率（原文同款 λ/μ 曲线）；
      反射踢 = 小概率对全局最优本体「扰动 + 预算制下探」
        （Salp/SFLA/FPA 同款机制，真实迭代进步的来源）。
    """

    name = "生物地理 BBO"
    default_params = {
        "n_pop": 25, "max_iter": 200, "p_mut": 0.05, "seed": 42,
        "ls_every": 10, "ls_moves": 20,
    }
    implemented = True
    category = "进化计算"
    param_specs = {
        "n_pop": {"min": 8, "max": 60, "step": 2, "int": True, "label": "栖息地数", "desc": "种群规模（大实例自动降配）"},
        "p_mut": {"min": 0.0, "max": 0.3, "step": 0.01, "int": False, "label": "突变率", "desc": "每个栖息地每代被随机修改的概率"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(8, n_p // 2)

        pop = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            pop.append(nearest_neighbor(D, start=rng.randrange(n)))
        pop = [_random_2opt_shot(t, D, rng, trials=50) for t in pop]
        pc = [tour_length(t, D) for t in pop]
        bi = min(range(n_p), key=lambda i: pc[i])
        best, best_cost = list(pop[bi]), pc[bi]

        n_imm = n_mut = n_kick = 0
        seg = max(2, n // 25)
        for it in range(1, p["max_iter"] + 1):
            # HSI 排名 → 线性迁入/迁出率（原文同款：差 λ 高 μ 低，好 λ 低 μ 高）
            order = sorted(range(n_p), key=lambda i: pc[i])
            rank = [0] * n_p
            for r_, idx in enumerate(order):
                rank[idx] = r_
            lam = [rank[i] / max(1, n_p - 1) for i in range(n_p)]   # 迁入率（差=1 好=0）
            mu = [1.0 - x for x in lam]                              # 迁出率（差=0 好=1）
            for i in range(n_p):
                if rng.random() < lam[i]:
                    # 迁入：从迁出率加权选中的供体那里 OX 混交（特征迁移）
                    don = _roulette(rng, [mu[k] + 1e-9 for k in range(n_p)])
                    if don != i and pop[don] != pop[i]:
                        cand = _ox_crossover(pop[i], pop[don], rng)
                        n_imm += 1
                    else:
                        cand = list(pop[i])
                else:
                    cand = list(pop[i])
                if rng.random() < p["p_mut"]:
                    cand = _or_opt_move(cand, rng, seg_len=3 if n < 60 else 4) \
                        if rng.random() < 0.5 else _reverse_mutation(cand, rng)
                    n_mut += 1
                c = tour_length(cand, D)
                if c < pc[i]:
                    pop[i], pc[i] = cand, c
                if c < best_cost:
                    best, best_cost = list(cand), c
            # 反射踢（真实下降来源，Salp/SFLA/FPA 同款）
            if rng.random() < 0.3:
                kick = _double_bridge(list(best), rng) if rng.random() < 0.5 \
                    else _or_opt_move(list(best), rng, seg_len=seg)
                kick = two_opt_improve(kick, D, max_moves=10)
                c = tour_length(kick, D)
                if c < best_cost:
                    best, best_cost = list(kick), c
                    w = max(range(n_p), key=lambda i: pc[i])
                    pop[w], pc[w] = list(kick), c
                n_kick += 1
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                imp = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(imp, D)
                if c < best_cost:
                    best, best_cost = imp, c
                    w = max(range(n_p), key=lambda i: pc[i])
                    pop[w], pc[w] = list(imp), c
            yield IterationState(
                it, best_cost, list(best), sum(pc) / n_p,
                {"n_imm": n_imm, "n_mut": n_mut, "n_kick": n_kick},
            )


class GraspSearch(BaseSolver):
    """GRASP 贪心随机自适应搜索（Feo & Resende 1989）：多重启构造 + 局部搜索。

    引用量级：近万（元启发式框架里最长寿的常青树，工业调度/网络设计领域标配基线）。
    与其他种群算法的根本区别：GRASP 没有「种群」——每代独立做一次
    「RCL 半贪心构造 → 2-opt 全下探」，用随机构造的多样性换局部最优的多样性，
    best 取历史所有落点的最小值。它的诚实口号是：每次都从新地方出发，而不是
    在老地方附近打转。

    离散化映射（TSP 版）：
      构造 = 组件库 _grasp_construct（RCL：每步从最近 k 个候选随机选一）；
      局部搜索 = two_opt_improve 预算制下探；
      贪心准入只作用于全局 best（本代落点再差也不影响下一代——多重启语义
      天然免疫「收敛种群全拒」假跑：扰动源是独立随机构造，永不枯竭）。
    """

    name = "GRASP"
    default_params = {
        "max_iter": 200, "k_rcl": 2, "seed": 42, "polish": 80,
    }
    implemented = True
    category = "局部搜索"
    param_specs = {
        "k_rcl": {"min": 2, "max": 8, "step": 1, "int": True, "label": "RCL 宽度 k", "desc": "每步从最近 k 个候选随机选；k=2 是实测甜区，越大构造越烂"},
        "polish": {"min": 0, "max": 100, "step": 5, "int": True, "label": "下探预算", "desc": "每次落点允许的 2-opt 移动数上限"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        # 基线 = 裸 NN（不做下探）：第一次迭代（构造+下探）就有明确的下降故事
        best = nearest_neighbor(D, start=0)
        best_cost = tour_length(best, D)
        nn_cost = best_cost

        n_build = n_improved = 0
        for it in range(1, p["max_iter"] + 1):
            # 每代 = 一次完整的「构造 → 下探」循环（GRASP 的一代一次迭代）
            cand = _grasp_construct(D, rng, k=p["k_rcl"])
            raw = tour_length(cand, D)
            cand = two_opt_improve(cand, D, max_moves=p["polish"])
            c = tour_length(cand, D)
            n_build += 1
            if c < best_cost:
                best, best_cost = list(cand), c
                n_improved += 1
            yield IterationState(
                it, best_cost, list(best), min(c, best_cost),
                {"n_build": n_build, "n_improved": n_improved,
                 "nn_cost": round(nn_cost, 1), "raw_cost": round(raw, 1)},
            )


class ClonalSelection(BaseSolver):
    """克隆选择算法 CLONALG（de Castro & Von Zuben 2002）：免疫克隆扩增 + 高频变异。

    引用量级：数千（人工免疫系统 AIS 家族的源头论文，inspired by Burnant
    克隆选择学说：抗原入侵 → 匹配的 B 细胞克隆扩增 → 高频突变 → 亲和度成熟）。

    离散化映射（TSP 版）：
      抗体 = 路径；亲和度 = 路径长度（越小越亲和）；
      克隆扩增 = 好抗体克隆多（数量 ∝ 排名）、差抗体克隆少；
      高频变异 = 克隆体做结构突变，变异强度与亲和度成反比（好的轻抖、差的重摇），
        变异后立刻预算制 2-opt 试射打磨（memetic 化——纯突变克隆体几乎必然变差）；
      组内选择 = 每个克隆组的最优与母体贪心比较；
      新抗体注入 = 每代 n_new 个 NN 重播替换最差（免疫多样性机制，防种群塌缩）。
    """

    name = "克隆选择 AIS"
    default_params = {
        "n_pop": 25, "max_iter": 200, "n_new": 3, "seed": 42,
        "ls_every": 10, "ls_moves": 20,
    }
    implemented = True
    category = "进化计算"
    param_specs = {
        "n_pop": {"min": 8, "max": 60, "step": 2, "int": True, "label": "抗体数", "desc": "种群规模（大实例自动降配）"},
        "n_new": {"min": 0, "max": 10, "step": 1, "int": True, "label": "新抗体数", "desc": "每代注入的随机新抗体个数（多样性）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(8, n_p // 2)

        pop = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            pop.append(nearest_neighbor(D, start=rng.randrange(n)))
        pop = [_random_2opt_shot(t, D, rng, trials=50) for t in pop]
        pc = [tour_length(t, D) for t in pop]
        bi = min(range(n_p), key=lambda i: pc[i])
        best, best_cost = list(pop[bi]), pc[bi]

        n_clone = n_mut = n_inject = n_kick = 0
        seg = max(2, n // 25)
        for it in range(1, p["max_iter"] + 1):
            order = sorted(range(n_p), key=lambda i: pc[i])
            rank = [0] * n_p
            for r_, idx in enumerate(order):
                rank[idx] = r_
            for i in range(n_p):
                # 克隆扩增：好抗体克隆多（原文 clone 数 ∝ 亲和度）
                n_cl = max(1, int(4 * (1.0 - rank[i] / max(1, n_p - 1)) + 0.5))
                local_best, local_c = list(pop[i]), pc[i]
                for _c in range(n_cl):
                    clone = list(pop[i])
                    # 高频变异：强度与排名成反比（好的轻抖、差的重摇）
                    frac = rank[i] / max(1, n_p - 1)
                    n_ops = 1 if frac < 0.34 else (2 if frac < 0.67 else 3)
                    for _ in range(n_ops):
                        r_ = rng.random()
                        if r_ < 0.45:
                            clone = _reverse_mutation(clone, rng)
                        elif r_ < 0.75:
                            clone = _or_opt_move(clone, rng, seg_len=3 if n < 60 else 4)
                        else:
                            clone = _double_bridge(clone, rng)
                    clone = _random_2opt_shot(clone, D, rng, trials=8)
                    n_clone += 1
                    n_mut += n_ops
                    c = tour_length(clone, D)
                    if c < local_c:
                        local_best, local_c = clone, c
                # 组内选择：克隆组最优与母体贪心比较
                if local_c < pc[i]:
                    pop[i], pc[i] = list(local_best), local_c
                if local_c < best_cost:
                    best, best_cost = list(local_best), local_c
            # 新抗体注入（免疫多样性机制）
            if p["n_new"] > 0:
                worst = sorted(range(n_p), key=lambda i: pc[i], reverse=True)[: p["n_new"]]
                for w in worst:
                    t = _random_2opt_shot(nearest_neighbor(D, start=rng.randrange(n)), D, rng, trials=30)
                    pop[w], pc[w] = t, tour_length(t, D)
                n_inject += len(worst)
            # 反射踢（真实下降来源，BBO/Salp/SFLA 同款）
            if rng.random() < 0.3:
                kick = _double_bridge(list(best), rng) if rng.random() < 0.5 \
                    else _or_opt_move(list(best), rng, seg_len=seg)
                kick = two_opt_improve(kick, D, max_moves=10)
                c = tour_length(kick, D)
                if c < best_cost:
                    best, best_cost = list(kick), c
                    w = max(range(n_p), key=lambda i: pc[i])
                    pop[w], pc[w] = list(kick), c
                n_kick += 1
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                imp = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(imp, D)
                if c < best_cost:
                    best, best_cost = imp, c
                    w = max(range(n_p), key=lambda i: pc[i])
                    pop[w], pc[w] = list(imp), c
            yield IterationState(
                it, best_cost, list(best), sum(pc) / n_p,
                {"n_clone": n_clone, "n_mut": n_mut, "n_inject": n_inject, "n_kick": n_kick},
            )


class EquilibriumOpt(BaseSolver):
    """均衡优化 EO（Faramarzi 2020）：均衡池 + 浓度加权（物理化学类代表）。

    引用量级：数千（2020 年提出的年轻算法，已进入 2025 引用榜三十强，
    蓝图 R2 联网核验确认）。隐喻：粒子 = 控制体内不断交换质量的物种浓度，
    均衡浓度（平衡状态）= 最优解；所有粒子浓度按质量平衡方程向均衡池靠拢。

    离散化映射（TSP 版）：
      浓度 = 随机键编码（_encode_tour / _decode_position，GSA/CEM 同款桥梁）；
      均衡池 C_eq = 4 个最优 + 1 个平均（原文五元组，每代重建）；
      质量平衡方程 X_new = C_eq + (X − C_eq)·F + G·(1−F)/λ·U 原样保留；
        F = exp(−a·λ) 随代衰减（a = 2·(1 − t/T)），G = 生成率项（勘探源）；
      解码后贪心准入自身 + 反射踢防停滞（BBO 同款）。
      连续域公式每代无条件移动 → 排列持续变化 → 无「收敛种群全拒」问题。
    """

    name = "均衡 EO"
    default_params = {
        "n_pop": 25, "max_iter": 200, "seed": 42,
        "ls_every": 10, "ls_moves": 20,
    }
    implemented = True
    category = "物理启发"
    param_specs = {
        "n_pop": {"min": 8, "max": 60, "step": 2, "int": True, "label": "粒子数", "desc": "种群规模（大实例自动降配）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])
        T = max(1, p["max_iter"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(8, n_p // 2)

        pop = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            pop.append(nearest_neighbor(D, start=rng.randrange(n)))
        pop = [_random_2opt_shot(t, D, rng, trials=50) for t in pop]
        pc = [tour_length(t, D) for t in pop]
        X = [_encode_tour(t, rng) for t in pop]
        bi = min(range(n_p), key=lambda i: pc[i])
        best, best_cost = list(pop[bi]), pc[bi]

        n_eq_hit = n_kick = 0
        seg = max(2, n // 25)
        for it in range(1, T + 1):
            # 均衡池：4 个最优 + 1 个平均（原文五元组）
            order = sorted(range(n_p), key=lambda i: pc[i])
            pool_idx = order[:4]
            X_mean = [sum(x[i2] for x in X) / n_p for i2 in range(n)]
            a = 2.0 * (1.0 - it / T)
            for i in range(n_p):
                C_eq = X[rng.choice(pool_idx)] if rng.random() < 0.75 else X_mean
                lam = rng.random()
                F = math.exp(-a * lam)
                # 生成率项 G（原文 G0 = GCP·(X_mean − X)，GCP=0.5，乘 (1−F)/λ 入方程）
                G = [0.5 * (X_mean[k] - X[i][k]) for k in range(n)]
                Xn = [
                    C_eq[k] + (X[i][k] - C_eq[k]) * F + G[k] * (1.0 - F) / max(lam, 1e-9) * rng.random()
                    for k in range(n)
                ]
                X[i] = Xn
                cand = _decode_position(Xn)
                c = tour_length(cand, D)
                n_eq_hit += 1
                if c < pc[i]:
                    pop[i], pc[i] = list(cand), c
                    X[i] = _encode_tour(cand, rng)   # 重编码保持排列↔向量一致
                if c < best_cost:
                    best, best_cost = list(cand), c
            # 反射踢（真实下降来源，BBO 同款）
            if rng.random() < 0.3:
                kick = _double_bridge(list(best), rng) if rng.random() < 0.5 \
                    else _or_opt_move(list(best), rng, seg_len=seg)
                kick = two_opt_improve(kick, D, max_moves=10)
                c = tour_length(kick, D)
                if c < best_cost:
                    best, best_cost = list(kick), c
                    w = max(range(n_p), key=lambda i: pc[i])
                    pop[w], pc[w] = list(kick), c
                    X[w] = _encode_tour(kick, rng)
                n_kick += 1
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                imp = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(imp, D)
                if c < best_cost:
                    best, best_cost = imp, c
                    w = max(range(n_p), key=lambda i: pc[i])
                    pop[w], pc[w] = list(imp), c
                    X[w] = _encode_tour(imp, rng)
            yield IterationState(
                it, best_cost, list(best), sum(pc) / n_p,
                {"n_eq_hit": n_eq_hit, "n_kick": n_kick, "a": round(a, 3)},
            )


class AquilaOpt(BaseSolver):
    """天鹰优化 AO（Abualigah 2021）：四阶段探索-开发调度。

    引用量级：数千（2021 提出，近年上升最快的「新一代」算法之一，
    蓝图 R2 联网核验确认补录）。隐喻：天鹰四种捕猎姿态——
    ① 高飞滑翔垂直俯冲（广域勘探）② 短滑掠攻击（轮廓勘探）
    ③ 低飞慢降进攻（定向开发）④ 地面行走捕获（精修）。

    离散化映射（TSP 版）：
      X1 广域勘探 = 双桥大跳（结构性扰动进新盆地）+ 落地试射；
      X2 轮廓勘探 = Levy 越步（FPA 语义：f>1 越步跳盆地、f<1 短步逆转）；
      X3 定向开发 = or-opt 围绕自身精修 + 预算制试射；
      X4 地面捕获 = OX 向 best 混交 + 预算制下探；
      阶段按 t/T 三等分切换（原文前 1/3 探索、中 1/3 过渡、后 1/3 开发），
      每阶段全体执行、贪心准入自身，best 单调。
    """

    name = "天鹰 AO"
    default_params = {
        "n_pop": 22, "max_iter": 200, "seed": 42,
        "ls_every": 10, "ls_moves": 20,
    }
    implemented = True
    category = "群体智能"
    param_specs = {
        "n_pop": {"min": 8, "max": 60, "step": 2, "int": True, "label": "鹰数", "desc": "种群规模（大实例自动降配）"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])
        T = max(1, p["max_iter"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(8, n_p // 2)

        pop = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            pop.append(nearest_neighbor(D, start=rng.randrange(n)))
        pop = [_random_2opt_shot(t, D, rng, trials=50) for t in pop]
        pc = [tour_length(t, D) for t in pop]
        bi = min(range(n_p), key=lambda i: pc[i])
        best, best_cost = list(pop[bi]), pc[bi]

        seg = max(2, n // 25)
        stage_hits = [0, 0, 0, 0]
        n_kick = 0
        for it in range(1, T + 1):
            frac = it / T
            stage = 0 if frac < 1 / 3 else (1 if frac < 2 / 3 else 2)
            for i in range(n_p):
                r4 = rng.random()
                if stage == 0:
                    # X1 / X2 交替：广域双桥 vs Levy 越步
                    if r4 < 0.5:
                        cand = _double_bridge(list(pop[i]), rng)
                        cand = _random_2opt_shot(cand, D, rng, trials=8)
                        stage_hits[0] += 1
                    else:
                        f = rng.expovariate(1.0)   # Levy: 幂律步长
                        if f > 1.0:
                            cand = _double_bridge(list(pop[i]), rng)   # 越步跳盆地
                            cand = _random_2opt_shot(cand, D, rng, trials=6)
                        else:
                            cand = _reverse_mutation(list(pop[i]), rng)  # 短步
                            cand = _random_2opt_shot(cand, D, rng, trials=4)
                        stage_hits[1] += 1
                else:
                    # X3 / X4 交替：or-opt 自精修 vs OX 向 best + 下探
                    if r4 < 0.5:
                        cand = _or_opt_move(list(pop[i]), rng, seg_len=3 if n < 60 else 4)
                        cand = _random_2opt_shot(cand, D, rng, trials=10)
                        stage_hits[2] += 1
                    else:
                        don = best if pop[i] != best else list(pop[i])[::-1]
                        cand = _ox_crossover(pop[i], don, rng)
                        cand = two_opt_improve(cand, D, max_moves=6)
                        stage_hits[3] += 1
                c = tour_length(cand, D)
                if c < pc[i]:
                    pop[i], pc[i] = list(cand), c
                if c < best_cost:
                    best, best_cost = list(cand), c
            # 反射踢（真实下降来源，BBO 同款）
            if rng.random() < 0.3:
                kick = _double_bridge(list(best), rng) if rng.random() < 0.5 \
                    else _or_opt_move(list(best), rng, seg_len=seg)
                kick = two_opt_improve(kick, D, max_moves=10)
                c = tour_length(kick, D)
                if c < best_cost:
                    best, best_cost = list(kick), c
                    w = max(range(n_p), key=lambda i: pc[i])
                    pop[w], pc[w] = list(kick), c
                n_kick += 1
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                imp = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(imp, D)
                if c < best_cost:
                    best, best_cost = imp, c
                    w = max(range(n_p), key=lambda i: pc[i])
                    pop[w], pc[w] = list(imp), c
            yield IterationState(
                it, best_cost, list(best), sum(pc) / n_p,
                {"stage": stage + 1, "hits": list(stage_hits), "n_kick": n_kick},
            )


# ============================ 注册表与 JS 入口 ============================



class SlimeMould(BaseSolver):
    """黏菌算法 SMA（Li, Chen, Wang, Heidari & Mirjalili, 2020, FGCS）。

    引用量级：~5000+（2020 系新算法中引用攀升极快的一支，Mirjalili 团队出品）。
    机制：多头绒泡菌（Physarum polycephalum）觅食时以原质团传播波连接食物源，
    自适应权重模拟传播波的<strong>正负反馈</strong>——食物浓度高的区域管径变粗
    （权重 &gt; 1），稀薄处收缩（权重 &lt; 1），形成「重流量路径」。
    官方权重公式：适应度排序后，前一半 W = 1+rand·log(ratio+1)，
    后一半 W = 1−rand·log(ratio+1)，ratio = (worst−f)/(worst−best)。
    三段更新：
      ① rand &lt; z：随机重建（传播波重新铺开，勘探）；
      ② rand &lt; 0.5：X = X_best + vb·(W·X_A − X_B)（沿粗管向最优运输）；
      ③ 否则：X = vc·X（细管收缩，局部开发）。

    离散化映射（TSP 版）：
      ① 随机重建 = 随机起点最近邻 + 2-opt 抖动解（新波前）；
      ② 粗管运输 = 按 W 加权轮盘选出引导个体，交换序列随机前缀
        （前缀长度 ∝ 引导个体权重 w——粗管流量大，走得远）；
      ③ 细管收缩 = or-opt 结构微调（片段搬运，本地路径收缩）；
      最优反射踢 = 小概率对全局最优本体「扰动 + 预算制下探」
        （Salp/SFLA/Jaya 同款机制，真实迭代进步的来源）。
    """

    name = "黏菌算法 SMA"
    default_params = {
        "n_pop": 25, "max_iter": 200, "seed": 42,
        "z": 0.2,          # 重建概率（勘探占比）
        "ls_every": 10, "ls_moves": 20,
    }
    implemented = True
    category = "物理启发"
    param_specs = {
        "n_pop": {"min": 8, "max": 60, "step": 2, "int": True, "label": "个体数", "desc": "原质团个体数量（大实例自动降配）"},
        "z": {"min": 0.0, "max": 0.5, "step": 0.05, "label": "重建概率 z", "desc": "传播波随机重新铺开的概率；越大勘探越猛"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_p = p["n_pop"]
        if n > 80:
            n_p = max(8, n_p // 2)

        pop = [nearest_neighbor(D, start=0)]
        for _ in range(n_p - 1):
            pop.append(nearest_neighbor(D, start=rng.randrange(n)))
        pop = [_random_2opt_shot(t, D, rng, trials=50) for t in pop]
        pc = [tour_length(t, D) for t in pop]
        bi = min(range(n_p), key=lambda i: pc[i])
        best, best_cost = list(pop[bi]), pc[bi]

        seg = max(2, n // 25)
        n_rebuild = n_transport = n_shrink = n_kick = 0
        for it in range(1, p["max_iter"] + 1):
            # 官方权重：按当前适应度排序，前半放大 / 后半收缩
            order = sorted(range(n_p), key=lambda i: pc[i])
            worst, bestc = pc[order[-1]], pc[order[0]]
            span = max(1e-9, worst - bestc)
            weights = [1.0] * n_p
            for rank, idx in enumerate(order):
                ratio = (worst - pc[idx]) / span  # 1=最优 0=最劣
                if rank < n_p // 2:
                    weights[idx] = 1.0 + rng.random() * math.log(ratio + 1.0)
                else:
                    weights[idx] = 1.0 - rng.random() * math.log(ratio + 1.0)

            for i in range(n_p):
                r = rng.random()
                if r < p["z"]:
                    # ① 传播波重新铺开：随机起点 NN + 2-opt 抖动
                    cand = nearest_neighbor(D, start=rng.randrange(n))
                    cand = _random_2opt_shot(cand, D, rng, trials=30)
                    n_rebuild += 1
                elif r < p["z"] + (1.0 - p["z"]) * 0.5:
                    # ② 粗管运输：权重加权选引导个体，前缀长度 ∝ 其权重
                    pool = [j for j in range(n_p) if j != i]
                    ws = [weights[j] for j in pool]
                    guide = rng.choices(pool, weights=ws, k=1)[0]
                    seq = swap_seq_to_target(list(pop[i]), pop[guide])
                    if seq:
                        frac = min(1.0, weights[guide] / 2.0)
                        cand = apply_swaps(
                            pop[i], seq[:max(1, int(len(seq) * frac * rng.random()))])
                    else:
                        cand = list(pop[i])
                    n_transport += 1
                else:
                    # ③ 细管收缩：or-opt 结构微调
                    cand = _or_opt_move(list(pop[i]), rng, seg_len=seg)
                    n_shrink += 1
                c = tour_length(cand, D)
                if c < pc[i]:
                    pop[i], pc[i] = cand, c
                if c < best_cost:
                    best, best_cost = list(cand), c
            # 最优反射踢（真实下降来源，Salp/SFLA/Jaya 同款）
            if rng.random() < 0.3:
                kick = _double_bridge(list(best), rng) if rng.random() < 0.5 \
                    else _or_opt_move(list(best), rng, seg_len=seg)
                kick = two_opt_improve(kick, D, max_moves=10)
                c = tour_length(kick, D)
                if c < best_cost:
                    best, best_cost = kick, c
                    w = max(range(n_p), key=lambda j: pc[j])
                    pop[w], pc[w] = list(kick), c
                n_kick += 1
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                imp = two_opt_improve(best, D, max_moves=p["ls_moves"])
                c = tour_length(imp, D)
                if c < best_cost:
                    best, best_cost = imp, c
                    w = max(range(n_p), key=lambda j: pc[j])
                    pop[w], pc[w] = list(imp), c
            yield IterationState(
                it, best_cost, list(best), sum(pc) / n_p,
                {"n_rebuild": n_rebuild, "n_transport": n_transport,
                 "n_shrink": n_shrink, "n_kick": n_kick},
            )


# ---- 新算法的类：tools/new_algorithm.py 追加在这一行之前 ----


SOLVERS: Dict[str, type] = {
    "pso": DiscretePSO,
    "2opt": TwoOptSolver,
    "nn": GreedyNN,
    "aco": ACO,
    "abc": ABC,
    "fa": FA,
    "woa": WOA,
    "ga": GA,
    "sa": SA,
    "gwo": GWO,
    "ts": TabuSearch,
    "de": DifferentialEvolution,
    "cs": CuckooSearch,
    "sca": SineCosine,
    "hho": HarrisHawks,
    # —— 第二批（局部搜索框架 + 群智能补全）——
    "ils": IteratedLocalSearch,
    "vns": VariableNeighborhoodSearch,
    "lk": LinKernighan,
    "ba": BatAlgorithm,
    "hs": HarmonySearch,
    "gsa": GravitationalSearch,
    "tlbo": TeachingLearning,
    "bfo": BacterialForaging,
    "mfo": MothFlame,
    "fwa": Fireworks,
    "afsa": ArtificialFishSwarm,
    "cem": CrossEntropy,
    # —— 第三批（2020 前后新算法 + Mirjalili 系补全）——
    "ssa": SparrowSearch,
    "alo": AntLion,
    "boa": ButterflyOpt,
    # —— 第四批（ICA 社会政治隐喻 + 链式/分组机制补全）——
    "ica": ImperialistCA,
    "salp": SalpSwarm,
    "sfla": ShuffledFrogLeaping,
    # —— 第五批（P1.3a：组件化重构后首批装配，蓝图 R3 批次一）——
    "fpa": FlowerPollination,
    "kh": KrillHerd,
    "sos": SymbioticOS,
    "jaya": JayaOptimizer,
    # —— 第六批（P1.3b：2025 榜单补全批次二，蓝图 R3 批次二）——
    "da": DragonflySwarm,
    "mpa": MarinePredator,
    "cscrow": RavenSearch,
    "bbo": Biogeography,
    # —— 第七批（P1.3c：蓝图终点 45 达成，蓝图 R3 批次三）——
    "grasp": GraspSearch,
    "ais": ClonalSelection,
    "eo": EquilibriumOpt,
    "ao": AquilaOpt,
    # —— 第八批（家族轴批次：F3 清单补全）——
    "sma": SlimeMould,
    # ---- 新算法：tools/new_algorithm.py 在这一行之前登记 ----
}


class CMAES(BaseSolver):
    """协方差矩阵自适应进化策略 CMA-ES（Hansen & Ostermeier 2001, EC 9(2):159-195）。

    引用量级：数万（连续域公认的 SOTA 级演化策略，指认
    的「连续域真正强者」）。它和 CEM（EDA 分支）一样走「分布→采样→精英回写」
    路线，但 CMA-ES 学习的是**全二阶矩**——均值 + 协方差矩阵，而非 EDA 的
    一阶频率矩阵；学习机制是协方差自适应 + 进化路径（pc/ps）步长耦合，
    比 EDA 的平滑系数 λ 更鲁棒地匹配问题地形条件数。

    离散化映射（TSP 版 —— random-keys 连续松弛）：
      编码 = 每个城市一个连续键 key[c]∈[0,1]；按键排序 → 排列（标准 random-keys 解码）；
      分布 = 可分离对角协方差 sep-CMA（浏览器内 O(n²) 采样，n=100 也扛得住；
              若用全 n×n 协方差，n=100 时每代特征分解 O(n³) 太重）；
      采样 = 均值键 + σ·√diag(C)·z（z~N(0,I)）；
      更新 = 标准 (μ,λ)-CMA-ES：均值 / pc / ps / 对角 C / σ 全套自适应；
      混合组件 = 精英以 polish_p 概率做短 2-opt 试射再回写（memetic 组件，
                与 CEM 同款：纯连续采样在抛光后的 NN 播种上抽不出更优结构）。
    """

    name = "协方差矩阵自适应进化策略 CMA-ES"
    default_params = {
        "n_pop": 30,
        "max_iter": 200,
        "sigma0": 0.4,      # 随机键标准差初值（相对 [0,1] 键空间）
        "polish_p": 0.3,    # 精英打磨概率（memetic 组件）
        "ls_every": 10,
        "ls_moves": 20,
        "seed": 42,
    }
    implemented = True
    category = "进化计算"
    param_specs = {
        "n_pop": {"min": 10, "max": 80, "step": 2, "int": True, "label": "样本数", "desc": "每代从分布抽样的解数量（大实例自动降配）"},
        "sigma0": {"min": 0.1, "max": 0.8, "step": 0.05, "label": "初始步长 σ₀", "desc": "随机键空间的初始探索半径；越大起步越莽撞"},
        "polish_p": {"min": 0.0, "max": 0.5, "step": 0.05, "label": "精英打磨", "desc": "对精英样本做短 2-opt 试射再回写分布的概率"},
        "ls_every": {"min": 0, "max": 30, "step": 1, "int": True, "label": "局部搜索周期", "desc": "每 N 代对全局最优做一次 2-opt 并回灌；0=关闭"},
        "ls_moves": {"min": 0, "max": 40, "step": 1, "int": True, "label": "局部搜索预算", "desc": "每次局部搜索最多接受的 2-opt 移动数"},
    }

    def solve(self, problem, params):
        p = {**self.default_params, **(params or {})}
        D = problem["D"]
        n = problem["n"]
        rng = random.Random(p["seed"])

        n_pop = p["n_pop"]
        if n > 80:
            n_pop = max(12, n_pop // 2)

        # CMA-ES 常量（sep 版，对角协方差）
        mu = max(1, n_pop // 2)
        weights = [math.log(mu + 0.5) - math.log(i + 1) for i in range(mu)]
        wsum = sum(weights)
        weights = [w / wsum for w in weights]
        mueff = (sum(weights)) ** 2 / sum(w * w for w in weights)
        cc = 4.0 / (n + 4.0)
        cs = (mueff + 2.0) / (n + mueff + 3.0)
        c1 = 2.0 / ((n + 1.3) ** 2 + mueff)
        cmu = min(1.0 - c1, 2.0 * (mueff - 2.0 + 1.0 / mueff) / ((n + 2.0) ** 2 + mueff))
        damps = 1.0 + 2.0 * max(0.0, math.sqrt((mueff - 1.0) / (n + 1.0)) - 1.0) + cs
        chiN = math.sqrt(n) * (1.0 - 1.0 / (4.0 * n) + 1.0 / (21.0 * n * n))

        sigma = p["sigma0"]
        m = [rng.random() for _ in range(n)]   # 均值键向量 ∈[0,1]
        C = [1.0] * n                          # 对角协方差（sep-CMA-ES）
        pc = [0.0] * n
        ps = [0.0] * n

        def _decode(kv):
            return sorted(range(n), key=lambda i: kv[i])

        best_tour = _decode(m)
        best_cost = tour_length(best_tour, D)

        for it in range(1, p["max_iter"] + 1):
            pop, costs = [], []
            for _k in range(n_pop):
                z = [rng.gauss(0.0, 1.0) for _ in range(n)]
                keys = [m[i] + sigma * math.sqrt(C[i]) * z[i] for i in range(n)]
                tour = _decode(keys)
                c = tour_length(tour, D)
                pop.append((keys, tour, c))
                costs.append(c)
            order = sorted(range(n_pop), key=lambda i: costs[i])
            sel = order[:mu]
            old_m = m
            m = [sum(weights[i] * pop[sel[i]][0][d] for i in range(mu)) for d in range(n)]
            ymean = [(m[d] - old_m[d]) / sigma for d in range(n)]
            # 步长路径 ps（对角 C → C^{-1/2} = 1/√C，逐分量）
            cinv = [ymean[d] / math.sqrt(C[d]) for d in range(n)]
            ps = [(1 - cs) * ps[d] + math.sqrt(cs * (2 - cs) * mueff) * cinv[d] for d in range(n)]
            hsig = (math.sqrt(sum(x * x for x in ps)) /
                    math.sqrt(1 - (1 - cs) ** (2 * it)) / chiN) < (1.4 + 2.0 / (n + 1.0))
            pc = [(1 - cc) * pc[d] + hsig * math.sqrt(cc * (2 - cc) * mueff) * ymean[d] for d in range(n)]
            # 更新对角 C：秩一 + 秩μ（逐分量独立）
            ci = cmu  # Σweights = 1
            for d in range(n):
                C[d] = (1 - c1 - ci) * C[d] + c1 * (pc[d] * pc[d] + hsig * (2 - hsig) * C[d])
            for i in range(mu):
                yi = [(pop[sel[i]][0][d] - old_m[d]) / sigma for d in range(n)]
                wyi = weights[i]
                for d in range(n):
                    C[d] += cmu * wyi * yi[d] * yi[d]
            sigma *= math.exp((cs / damps) * (math.sqrt(sum(x * x for x in ps)) / chiN - 1.0))
            # 精英打磨 + 保优
            for i in sel:
                tour, c = pop[i][1], pop[i][2]
                if rng.random() < p["polish_p"]:
                    tour2 = _random_2opt_shot(tour, D, rng, 8)
                    c2 = tour_length(tour2, D)
                    if c2 < c:
                        tour, c = tour2, c2
                if c < best_cost:
                    best_tour, best_cost = list(tour), c
            if p["ls_every"] > 0 and it % p["ls_every"] == 0:
                imp = two_opt_improve(best_tour, D, max_moves=p["ls_moves"])
                c = tour_length(imp, D)
                if c < best_cost:
                    best_tour, best_cost = imp, c
            cur = sum(costs) / n_pop
            yield IterationState(
                it, best_cost, list(best_tour), cur,
                {"n_pop": n_pop, "sigma": round(sigma, 4)},
            )


SOLVERS["cma-es"] = CMAES

# ============================ S7-B：配方算法注册（L-recipe 层） ============================
# recipe.py 提供七槽管线组合引擎；本地环境走 import，拼接环境（solvers_src.js）里
# recipe.py 已内联在前面，直接从 globals() 取——双环境行为一致。
try:
    from recipe import install_recipes as _install_recipes
except ImportError:
    _install_recipes = globals().get("install_recipes")
if callable(_install_recipes):
    _install_recipes(SOLVERS, IterationState, build_problem, tour_length)


def list_solvers() -> str:
    """供前端动态生成算法下拉框：返回 JSON 字符串（含分类与参数定义域）"""
    out = []
    for key, cls in SOLVERS.items():
        out.append(
            {
                "key": key,
                "name": cls.name,
                "category": category_of(key, cls.category),  # 家族体系里的算法以家族为准，其余沿用类上的值
                "rank": category_rank(category_of(key, cls.category)),  # 前端据此排分组顺序，不再自带一份分类清单
                "params": cls.default_params,
                "specs": cls.param_specs,
                "implemented": cls.implemented,
            }
        )
    return json.dumps(out, ensure_ascii=False)


# --- 生成器状态：由 JS 反复调用 step() 驱动，实现暂停/单步/调速 ---
_GEN: Optional[Iterator[IterationState]] = None


def start(problem_json: str, algo: str, params_json: str = "{}") -> str:
    """新建一次求解。problem_json = [[x,y], ...]，或校验器规整后的 {"cities", "metric"?, "matrix"?}"""
    global _GEN
    cities = json.loads(problem_json)
    problem = problem_from_spec(cities)
    cities = problem["cities"]
    params = json.loads(params_json or "{}")
    if algo not in SOLVERS:
        raise ValueError(f"未知算法: {algo}")
    _GEN = SOLVERS[algo]().solve(problem, params)
    return json.dumps({"n": len(cities)}, ensure_ascii=False)


def step() -> Optional[str]:
    """推进一代，返回该代状态的 JSON；结束返回 None"""
    global _GEN
    if _GEN is None:
        return None
    try:
        return json.dumps(asdict(next(_GEN)), ensure_ascii=False)
    except StopIteration:
        _GEN = None
        return None


def step_k(k: int = 1) -> Optional[str]:
    """推进 k 代，返回批量采样结果 JSON；结束后续调用返回 None。

    v0.3 新增：支持「每 N 代采样一次」。返回结构：
        {
          "iteration": 末代代数, "best_cost": .., "best_tour": [..], "current_cost": ..,
          "points": [[代数, 全局最优, 当代成本], ...],   # 本批 k 代逐代的真实数据
          "exhausted": true/false                       # 本批是否用完了所有代
        }
    设计说明：每代只在 points 里放 3 个数字（不含路径），k=10 时开销可忽略；
    best_tour 只放末代一份，避免消息膨胀。
    """
    global _GEN
    if _GEN is None:
        return None
    points = []
    last: Optional[IterationState] = None
    exhausted = False
    try:
        for _ in range(max(1, int(k))):
            last = next(_GEN)
            points.append(
                [last.iteration, round(last.best_cost, 3), round(last.current_cost, 3)]
            )
    except StopIteration:
        exhausted = True
        _GEN = None
    if last is None:
        return None
    d = asdict(last)
    d["points"] = points
    d["exhausted"] = exhausted
    return json.dumps(d, ensure_ascii=False)


def run_all(problem_json: str, max_iter: int = 200, seed: int = 42) -> str:
    """对比页专用：把同一实例交给所有已实现算法各跑一遍，返回曲线与终值。

    返回 {algo: {"name":.., "curve":[...], "final":..}，以及 "nn" 基线}
    不走生成器，一次跑完——对比页要的是结果不是动画。
    """
    problem = problem_from_spec(json.loads(problem_json))
    cities = problem["cities"]

    out: Dict[str, Any] = {}
    for key, cls in SOLVERS.items():
        if not cls.implemented:
            continue
        params = {"max_iter": max_iter, "seed": seed}
        if key == "nn":
            params = {}
        curve = []
        final = None
        for st in cls().solve(problem, params):
            curve.append(round(st.best_cost, 3))
            final = round(st.best_cost, 3)
        out[key] = {"name": cls.name, "curve": curve, "final": final}

    base = GreedyNN().solve(problem, {})
    nn_cost = round(next(base).best_cost, 3)
    return json.dumps({"results": out, "nn": nn_cost, "n": len(cities)}, ensure_ascii=False)


# ============================ 本地命令行自测 ============================

# 浏览器（Pyodide）里源码以 __main__ 身份拼接执行，必须用平台判断挡住，否则每次页面加载都会跑一遍自测
if __name__ == "__main__" and __import__("sys").platform != "emscripten":
    rng = random.Random(7)
    cities = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(30)]
    print("城市数:", len(cities))
    print("可用算法:", list_solvers())

    start(json.dumps(cities), "pso", json.dumps({"max_iter": 50}))
    first, last = None, None
    while True:
        s = step()
        if s is None:
            break
        last = json.loads(s)
        if first is None:
            first = last
    print(f"PSO 首代最优: {first['best_cost']:.2f}")
    print(f"PSO 末代最优: {last['best_cost']:.2f}  (迭代 {last['iteration']} 次)")

    start(json.dumps(cities), "nn")
    nn = json.loads(step())
    print(f"NN 基线:      {nn['best_cost']:.2f}")

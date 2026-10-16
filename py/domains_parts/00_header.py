# -*- coding: utf-8 -*-
"""v0.8 问题域扩展引擎：把元启发式从 TSP 推广到多个问题域。

设计原则（百科全书的骨架）：
  算法 = 探索/开发机制（与问题无关），问题绑定 = 编码 + 邻域/算子 + 约束处理。
  本文件为每个问题域提供「域上下文」（编码、评价、修复、polish），算法按统一生成器
  接口逐代 yield 状态，前端 worker 逐条消费——与 py/solvers.py 的 TSP 体系同构。

三个域（v0.8 简化版，后续逐个加深）：
  knapsack   0-1 背包      —— 二进制编码 + 贪心修复算子（约束处理入门）
  continuous 连续函数基准   —— 实数编码，PSO/DE/GWO/WOA/SCA 的「原生域」
  multiobj   双目标背包     —— NSGA-II：非支配排序 + 拥挤度（多目标入门）

接口：
  domain_start(domain, problem_json, algo, params_json) -> info json
  domain_step() -> state json or None
  domain_list(domain) -> 算法清单（含默认参数）
  domain_preset(domain, seed, opts_json) -> 预置实例

「真优化」校验铁律与 TSP 侧相同：每个算法都必须有「真实迭代进步」，
测试里逐个对照随机基线（tests/test_domains.py）。
"""
import json
import math
import random

# ---- 算法分类（生成文件 py/taxonomy.py：由 data/families.json + data/algos.json 得出）----
# 本地正常导入；浏览器构建期拼进同一名字空间，ImportError 分支跳过
try:
    from taxonomy import category_of
except ImportError:
    pass

# ---- 域引擎组件库（S1-1 组件化：骨架件单一来源 = py/domain_components.py）----
# 本地/pytest 正常导入；Pyodide 构建期本文件与 domain_components.py 拼进同一名字
# 空间执行，此 import 抛 ImportError → 跳过（名字已在空间内），两种环境行为一致
try:
    from domain_components import (
        argbest, bits_flip, bits_mutate, bits_uniform, bump, greedy_replace,
        pm_insert as _pm_insert, pm_ox as _pm_ox, pm_polish as _pm_polish,
        pm_swap as _pm_swap,
    )
except ImportError:
    pass

# ---- entryseq 词条域（57 变体的实例生成 + 目标函数，一变体一对函数）= py/entryseq.py ----
# 与上面同一机制：本地正常导入；浏览器构建期拼进同一名字空间，ImportError 分支跳过
try:
    from entryseq import _ES, es_make, es_ctx, FIDELITY, VEC_VARIANTS, BIT_VARIANTS, _DESIGN, _opt_mst, _opt_sp, _opt_gmatch, _pc_max_flow, _msa_dp  # noqa: F401  （不起别名：浏览器里这些模块拼进同一名字空间，别名不会被绑定）
except ImportError:
    pass

# ---- 自带问题 custom 域（用户给编码 + 目标函数，三种编码复用已有内核）= py/userproblem.py ----
try:
    from userproblem import (up_check, up_make_ctx, up_preset, up_wrap_stream, up_auto_params,  # noqa: F401
                             ENCODINGS as _UP_ENCODINGS)
except ImportError:
    pass

# ---- 连续多目标基准 mocont 域（ZDT / DTLZ，有解析真前沿，可算 IGD / HV）= py/mocont.py ----
try:
    from mocont import (MOC, mc_make, MOC_ALGOS, MOC_DEF, MOC_VARIANTS, MOC_SPEC, MOC_NFIX,  # noqa: F401
                        true_front)  # 不起别名：浏览器拼接环境里别名不会被绑定
except ImportError:
    pass


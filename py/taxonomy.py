# -*- coding: utf-8 -*-
"""算法分类的运行时副本——AUTO-GENERATED，请勿手改。
来源：data/families.json（家族 short 标签）+ data/algos.json（每个算法的 family）；
生成：python tools/gen_taxonomy.py（build_pages.py 每次构建自动执行）。

算法下拉框的分组标签一律经 category_of() 得出，TSP 页与各问题域页因此永远与站点家族一致。
"""

FAMILY_SHORT = {
    "F1": "进化计算",
    "F2": "群体智能",
    "F3": "物理·化学·数学启发",
    "F4": "人类与社会启发",
    "F5": "免疫与其他生物",
    "F10": "局部搜索与轨迹法",
    "F6": "混合与框架",
    "F7": "多目标",
    "F8": "新范式",
    "F9": "隐喻批评",
    "F0": "专用求解（对照）"
}

ALGO_CATEGORY = {
    "abc": "群体智能",
    "aco": "群体智能",
    "afsa": "群体智能",
    "ais": "免疫与其他生物",
    "alo": "群体智能",
    "ao": "群体智能",
    "ba": "群体智能",
    "bbo": "进化计算",
    "bfo": "群体智能",
    "boa": "群体智能",
    "cem": "进化计算",
    "cma-es": "进化计算",
    "cs": "群体智能",
    "cscrow": "群体智能",
    "da": "群体智能",
    "de": "进化计算",
    "eo": "物理·化学·数学启发",
    "fa": "群体智能",
    "fpa": "群体智能",
    "fwa": "群体智能",
    "ga": "进化计算",
    "grasp": "局部搜索与轨迹法",
    "gsa": "物理·化学·数学启发",
    "gwo": "群体智能",
    "hho": "群体智能",
    "hs": "人类与社会启发",
    "ica": "人类与社会启发",
    "ils": "局部搜索与轨迹法",
    "jaya": "物理·化学·数学启发",
    "kh": "群体智能",
    "lk": "专用求解（对照）",
    "mfo": "群体智能",
    "mpa": "群体智能",
    "pso": "群体智能",
    "sa": "物理·化学·数学启发",
    "salp": "群体智能",
    "sca": "物理·化学·数学启发",
    "sfla": "群体智能",
    "sma": "群体智能",
    "sos": "群体智能",
    "ssa": "群体智能",
    "tlbo": "人类与社会启发",
    "ts": "局部搜索与轨迹法",
    "vns": "局部搜索与轨迹法",
    "woa": "群体智能"
}


# 分组标签 → 展示顺序（= families.json 里的家族顺序）；不在家族体系里的标签排在最前（基线/构造件）
CATEGORY_RANK = {"进化计算": 0, "群体智能": 1, "物理·化学·数学启发": 2, "人类与社会启发": 3, "免疫与其他生物": 4, "局部搜索与轨迹法": 5, "混合与框架": 6, "多目标": 7, "新范式": 8, "隐喻批评": 9, "专用求解（对照）": 10}


def category_rank(category):
    return CATEGORY_RANK.get(category, -1)


# 域内核的后缀与 algos.json 里的算法键不一致的少数几个
_KERNEL_ALIAS = {"cmaes": "cma-es"}


def category_of(key, default=None):
    """算法键 → 分组标签。问题域里的变种内核（bv_pso / pk_sma / as_eo）取其基础算法的分类；
    不在家族体系里的（random/hc/贪心基线等）返回 default。"""
    base = key.split("_", 1)[1] if key[:3] in ("bv_", "pk_", "as_") else key
    base = _KERNEL_ALIAS.get(base, base)
    return ALGO_CATEGORY.get(base, default)

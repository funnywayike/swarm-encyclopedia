# -*- coding: utf-8 -*-
"""
域与变体登记表——「有哪些问题域、哪些变体」的唯一来源。

测试、黄金快照、示例生成器、命令行都从这里取清单，不再各抄一份。
entryseq 的 57 个变体不在这里手写：它们由 py/entryseq.py 里的 @_maker 登记顺序自动得出。
新增变体的步骤：
    entryseq 域 —— 在 py/entryseq.py 加一对 @_maker / @_objective 函数，其余自动跟上；
    其它带变体的域（kpvar/gcvar/bpvar/multiobj）—— 加引擎代码后，把变体名补进下面的 VARIANTS。
tests/test_registry.py 会核对：这里列的变体引擎都认、站点页面用到的变体这里都有。

仅本地工具使用；浏览器里引擎自带 _DOMAINS，不依赖本文件。
"""
from entryseq import VARIANTS as _ES_VARIANTS
from userproblem import ENCODINGS as _UP_ENCODINGS
from mocont import MOC_VARIANTS as _MOC_VARIANTS

# 单一实例、无变体的域
PLAIN = ("knapsack", "binpack", "graphcolor", "setcover", "sat", "qubo", "gap", "uflp", "continuous")

# 带变体的域 → 变体清单
VARIANTS = {
    "kpvar": ("bkp", "cmp", "dkp", "mckp", "mdkp", "mkpm", "qkp", "ssp", "ukp"),
    "gcvar": ("edgecolor", "listcolor", "precolor", "totalcolor", "mis"),
    "bpvar": ("binpack2d", "strippack", "vsbinpack"),
    "multiobj": ("moco", "maop"),
    "mocont": _MOC_VARIANTS,  # 连续多目标基准：ZDT1/2/3/4/6 + DTLZ1/2
    "entryseq": _ES_VARIANTS,
    "custom": _UP_ENCODINGS,  # 自带问题：三个变体 = 三种编码（位向量 / 排列 / 实数向量）
}

# 页面/命令行没指定变体时用哪个
DEFAULT_VARIANT = {"kpvar": "ssp", "gcvar": "mis", "bpvar": "vsbinpack", "multiobj": "moco", "mocont": "zdt1", "entryseq": "vrp", "custom": "bits"}

# 排程域：引擎里有，暂不开放数据上传（走各自的旧式导入）
SCHEDULING = ("etp", "nrp", "sls", "ttp")

# 开放数据上传的域（含 TSP，它走独立的旧引擎）；validate.CORE_DOMAINS 必须与此一致（tests/test_registry.py 核对）
UPLOADABLE = ("tsp",) + PLAIN + tuple(VARIANTS)


def cases(include_scheduling=False):
    """遍历 (域, 变体)；无变体的域变体为 None。TSP 不在其中（它不走 domains 引擎）。"""
    for dom in PLAIN:
        yield dom, None
    for dom, vs in VARIANTS.items():
        for v in vs:
            yield dom, v
    if include_scheduling:
        for dom in SCHEDULING:
            yield dom, None


# ---------------------------------------------------------------- 保真度
FIDELITY_LABEL = {"standard": "标准模型", "simplified": "教学简化模型", "illustrative": "示意模型", "custom": "自定义模型"}


# 排程四域（py/scheduling.py）自己有专业建模，保真度在这里登记（它们不是 entryseq 变体）
SCHEDULING_FIDELITY = {
    "etp": {"level": "simplified", "note": "考试与学生选课来自随机冲突图（每个学生恰选两门，保证存在零冲突解），不是 Carter 基准；硬约束用大权重罚函数处理，相邻时段与教室容量是软约束"},
    "nrp": {"level": "simplified", "note": "技能分级用「偏好违约」近似；约束只有覆盖缺口、偏好、连班，没有 INRC 排班竞赛里的合同规则"},
    "sls": {"level": "simplified", "note": "对阵完整性（双循环里每对恰好遇到两次）放松成软约束；文献里它是硬约束"},
    "ttp": {"level": "simplified", "note": "对阵完整性放松成大权重软罚；文献里的旅行锦标赛（Easton & Nemhauser）把它作为硬约束"},
}


def fidelity(domain, variant=None):
    """某个问题（域 + 变体）的保真度：{"level": standard|simplified|illustrative, "note": 与标准定义的差异}。
    entryseq 词条与排程四域由 py/entryseq.py 里的登记决定；其余域的目标函数都是文献标准定义。"""
    from entryseq import FIDELITY
    if domain == "entryseq":
        return dict(FIDELITY[variant])
    if domain in SCHEDULING:
        return dict(SCHEDULING_FIDELITY[domain])
    if domain == "custom":
        return {"level": "custom", "note": "目标函数由你自己给出：结果只对你写的公式成立，本站不替它的含义负责"}
    return {"level": "standard", "note": ""}

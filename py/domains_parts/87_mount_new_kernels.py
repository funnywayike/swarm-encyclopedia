# ---- 把 56_generic_bridges.py 里的新算法挂进各域的算法注册表（2026-10）----
# 连续域与实数向量变体（自带问题 real、entryseq 的 16 个实数变体）直接用连续内核；
# 位向量 / 排列 / 指派向量问题经通用适配器（bv_* / pk_* / as_*）。
# 哪些「域 × 变体 × 算法」在等评价次数下赢不了随机搜索而被撤下，见 88_withdrawn_cells.py（由 tools/fair_budget.py 生成）。

_NEW_CN_ENTRIES, _NEW_BV_ENTRIES, _NEW_PK_ENTRIES, _NEW_AS_ENTRIES = {}, {}, {}, {}
for _k, (_fn, _nm, _ds) in _NEW_CN.items():
    _cat = category_of(_k, "群体智能")
    _NEW_CN_ENTRIES[_k] = {"fn": _fn, "name": _nm, "category": _cat, "desc": "原生域！" + _ds, "tune": []}
    _NEW_BV_ENTRIES["bv_" + _k] = {"fn": _bridge(_fn, "bits", "bv"), "name": _nm + "（位）", "category": _cat,
                                   "desc": _ds + "；实数位置经 sigmoid 取 0/1", "tune": []}
    _NEW_PK_ENTRIES["pk_" + _k] = {"fn": _bridge(_fn, "perm", "pk"), "name": _nm + "（排列）", "category": _cat,
                                   "desc": _ds + "；随机键桥接（Bean 1994）", "tune": []}
    _NEW_AS_ENTRIES["as_" + _k] = {"fn": _bridge(_fn, "assign", "as"), "name": _nm + "（指派）", "category": _cat,
                                   "desc": _ds + "；实数位置四舍五入 + 截断", "tune": []}

_CN_ALGOS.update(_NEW_CN_ENTRIES)

# 位向量：与 _bv_reg() 同一批注册表（min 协议）；knapsack 是 max 协议，经 _maximize 取负代理适配
for _reg in (_SAT_ALGOS, _BIN_ALGOS, _UF_ALGOS, _SC_ALGOS, _MIS_ALGOS, _KPV_ALGOS, _SSP_ALGOS, _CMP_ALGOS, _KPVAR_ALGOS):
    _reg.update(_NEW_BV_ENTRIES)
try:
    _GCVAR_ALGOS.update(_NEW_BV_ENTRIES)
except NameError:
    pass
for _bk, _be in _NEW_BV_ENTRIES.items():
    _KS_ALGOS[_bk] = {"fn": _maximize(_be["fn"]), "name": _be["name"] + "（max）", "category": _be["category"],
                      "desc": _be["desc"] + "；max 域经 obj 取负代理适配", "tune": []}

# 排列：与 _PK_ALGOS 同一批注册表
for _reg in (_GC_ALGOS, _GCV_ALGOS, _BP_ALGOS, _BPVAR_ALGOS, _ES_ALGOS, _ES_PERM_ALGOS):
    _reg.update(_NEW_PK_ENTRIES)
try:
    _GCVAR_ALGOS.update(_NEW_PK_ENTRIES)
except NameError:
    pass

# 指派：gap
_GAP_ALGOS.update(_NEW_AS_ENTRIES)

# entryseq 的总表（_DOMAINS["entryseq"]["algos"] 引用它）
for _reg_x in (_ES_PERM_ALGOS, _BIN_ALGOS, _CN_ALGOS):
    for _k_x, _v_x in _reg_x.items():
        _ES_ALGOS_ALL.setdefault(_k_x, _v_x)


# ---- 通用离散 / 局部搜索系内核（57_generic_discrete_kernels.py）：按编码挂到对应的注册表 ----
_GENERIC_BITS_REGS = [_SAT_ALGOS, _BIN_ALGOS, _UF_ALGOS, _SC_ALGOS, _MIS_ALGOS, _KPV_ALGOS, _SSP_ALGOS, _CMP_ALGOS, _KPVAR_ALGOS, _KS_ALGOS]
try:
    _GENERIC_BITS_REGS.append(_GCVAR_ALGOS)
except NameError:
    pass
_GENERIC_PERM_REGS = [_GC_ALGOS, _GCV_ALGOS, _BP_ALGOS, _BPVAR_ALGOS, _ES_ALGOS, _ES_PERM_ALGOS]
_GENERIC_KIND_REGS = {"bits": _GENERIC_BITS_REGS, "perm": _GENERIC_PERM_REGS, "assign": [_GAP_ALGOS], "real": [_CN_ALGOS]}
_KIND_LABEL = {"bits": "位向量", "perm": "排列", "assign": "指派向量", "real": "实数向量"}
for _k, (_fn, _nm, _ds, _kinds) in _NEW_GENERIC.items():
    for _kind in _kinds:
        _entry = {"fn": _viewed(_fn, f"_mv_{_k}_{_kind}"), "name": _nm, "category": category_of(_k, "局部搜索与轨迹法"),
                  "desc": _ds + f"（{_KIND_LABEL[_kind]}问题通用版）", "tune": []}
        for _reg in _GENERIC_KIND_REGS[_kind]:
            _reg.setdefault(_k, _entry)
for _reg_x in (_ES_PERM_ALGOS, _BIN_ALGOS, _CN_ALGOS):
    for _k_x, _v_x in _reg_x.items():
        _ES_ALGOS_ALL.setdefault(_k_x, _v_x)

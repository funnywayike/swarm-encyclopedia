# ============================================================
# 域十二：原子词条实例域 entryseq（2026-09-27 解冻令首批——用户令「词条都要有实例」）
# 原子架构：零新内核——直接复用 _SW 共享内核（random/hc/sa/ts/ga），
# 本域只提供「问题原子」：es_make 实例 + _ES 上下文（obj/swap/random）。
# 9 变体=旅行商下拉的 9 个词条（VRP/HC/LP/LOP/SMS/FSS/JSS/OSS/RCPSP），
# 统一排列编码，变体专属 cost 解码；调度类解码为教学级简化（页面已注明）。
# ============================================================

_ES_DEF = {"max_iter": 200, "tries": 48, "t0": 4000.0, "decay": 0.90,
           "tenure": 10, "restart_at": 30, "pm": 0.06, "seed": 7}  # t0 与 BIG 罚同量级：罚悬崖上低温 SA 会卡局部






_ES_ALGOS = dict(_SW_ALGOS, **{
    "greedy": {"fn": _sw_random, "name": "随机基线", "category": "基线",
               "desc": "盲采样对照——各算法必须显著优于它（「真优化」校验锚点）", "tune": []},
})


# ---- 位编码族原子复用（2026-09-27 ROADMAP 批 7）：de/abc/woa/gwo/cs 内核零适配直拉 ----
class _ValueView:
    """把 min 域上下文（init_pop 给 obj）转成 _KS 内核期望的 max-value 视图：init_pop 给 value = -obj。
    其余属性原样转发。没有这一层时，初始种群的值是 obj、之后每次评价的值是 -obj，两者混着比较——
    内核实际在最大化代价，却把 -代价 当作「更好」上报（集合覆盖里出现负成本）。"""

    def __init__(self, ctx):
        self._c = ctx

    def __getattr__(self, name):
        return getattr(self._c, name)

    def init_pop(self, p, rng):
        pop = [self._c.random(rng) for _ in range(p["n_pop"])]
        return pop, [self._c.value(s) for s in pop]


def _minify(ks_fn):
    """_KS max 内核 → min 域包装：yield 时 best/cur 取负，统一 min 协议。"""
    def wrapped(ctx, p, rng):
        for st in ks_fn(_ValueView(ctx), p, rng):
            st["best"] = -st["best"]
            st["cur"] = -st["cur"]
            yield st
    wrapped.__name__ = ks_fn.__name__ + "_min"
    return wrapped

# def 合并：三域 def 缺 _KS 系键（F/CR/limit/pa/tenure 等）——补齐防 KeyError
for _def in (_SC_DEF, _SAT_DEF, _QB_DEF):
    _def.update({k: v for k, v in _KS_DEF.items() if k not in _def})
# 这 5 个内核全部 ctx 协议形式（_ks_* 系），_SC/_SAT/_QB 上下文天然兼容（_SW 同协议已在跑）
_SC_ALGOS.update({
        k: {"fn": _minify(_KS_ALGOS[k]["fn"]), "name": _KS_ALGOS[k]["name"],
            "category": _KS_ALGOS[k]["category"], "desc": _KS_ALGOS[k]["desc"],
            "tune": _KS_ALGOS[k]["tune"]}
        for k in ("de", "abc", "woa", "gwo", "cs")})
_SAT_ALGOS.update({
        k: {"fn": _minify(_KS_ALGOS[k]["fn"]), "name": _KS_ALGOS[k]["name"],
            "category": _KS_ALGOS[k]["category"], "desc": _KS_ALGOS[k]["desc"],
            "tune": _KS_ALGOS[k]["tune"]}
        for k in ("de", "abc", "woa", "gwo", "cs")})
_BIN_ALGOS.update({
        k: {"fn": _minify(_KS_ALGOS[k]["fn"]), "name": _KS_ALGOS[k]["name"],
            "category": _KS_ALGOS[k]["category"], "desc": _KS_ALGOS[k]["desc"],
            "tune": _KS_ALGOS[k]["tune"]}
        for k in ("de", "abc", "woa", "gwo", "cs")})  # qubo 域直接引用 _BIN_ALGOS

# ---- M1 位向量 bv 内核全位域挂载（2026-09-27 全矩阵计划）----
# bv_fa/bv_ba/bv_jaya/bv_tlbo（sigmoid 二值化，min 协议）挂 sat/qubo；setcover 经 dict(_SW_ALGOS) 自动获得
def _bv_reg():
    return {k: {"fn": getattr(__import__(__name__), f"_bv_{sfx}"),
                "name": nm, "category": "群体智能" if sfx in ("fa", "ba") else ("群体智能" if sfx == "jaya" else "人类与社会启发"),
                "desc": ds, "tune": []}
            for k, sfx, nm, ds in (
                ("bv_fa", "fa", "萤火虫 FA（位）", "sigmoid 映射二值化（Kennedy & Eberhart 1997 模式）"),
                ("bv_ba", "ba", "蝙蝠 BA（位）", "频率调谐+sigmoid 映射二值化"),
                ("bv_jaya", "jaya", "Jaya（位）", "向 best 靠拢+远离 worst（sigmoid）"),
                ("bv_tlbo", "tlbo", "TLBO（位）", "教师/学习 sigmoid 映射（零专属参数）"),
                ("bv_pso", "pso", "粒子群 PSO（位）", "速度-位置+sigmoid（Kennedy & Eberhart 1997 原型）"),
                ("bv_sca", "sca", "正弦余弦 SCA（位）", "经典 sin/cos 更新（r4 切换，Mirjalili 2016，文献核对修正）"),
                ("bv_mfo", "mfo", "蛾焰 MFO（位）", "经典多焰递减螺旋+sigmoid（Mirjalili 2015，flame 数 n_pop→1）"),
                # bv_gsa/bv_hs 撤下（2026-09-28 门裁定）：GSA 引力项在离散翻转语境退化、
                # HS 记忆考量 50 代收敛不足——各 3-4 域连随机最优都未赢，系统性失效

                ("bv_eo", "eo", "均衡 EO（位）", "经典平衡池 5 候选等概率选一+F 项+GCP 开关（Faramarzi 2020，文献核对修正）"),
                ("bv_ao", "ao", "天鹰 AO（位）", "经典四阶段：X1 均值扩张/X2 Levy 收缩探索/X3 α-δ 开发/X4 QF 收缩（Abualigah 2021，文献核对修正）"),
                ("bv_sma", "sma", "黏菌 SMA（位）", "经典位移式 Xb+vb(W·XA−XB)+log 权重+p=tanh 阈值（Li 2020，文献核对修正）"),
                ("bv_cem", "cem", "交叉熵 CEM（位）", "伯努利 CEM 精英频率回写（Rubinstein 1997）"),
                ("bv_cmaes", "cmaes", "CMA-ES（位·对角近似）", "对角协方差伯努利近似（诚实简化）"))}
# ---- M1 max 域包装：bv min 内核 → knapsack/kpvar（max 协议）----
# ctx.obj 代理取负（内核内部 min 比较对齐），yield 时 best/cur 还原正号
def _maximize(bv_fn):
    def wrapped(ctx, p, rng):
        raw_eval = ctx.obj if hasattr(ctx, "obj") else ctx.value  # _KS 系接口名=value
        class _MaxView:
            def __init__(self, c, ev):
                self._c = c
                self._ev = ev
                self.n = c.n
            def obj(self, s):
                return -self._ev(s)
            def __getattr__(self, name):
                return getattr(self._c, name)
        for st in bv_fn(_MaxView(ctx, raw_eval), p, rng):
            st["best"] = -st["best"]
            st["cur"] = -st["cur"]
            yield st
    wrapped.__name__ = bv_fn.__name__ + "_max"
    return wrapped

_bv_full = _bv_reg()
for _bk, _bv_entry in _bv_full.items():
    _KS_ALGOS[_bk] = {"fn": _maximize(_bv_entry["fn"]), "name": _bv_entry["name"] + "（max）",
                      "category": _bv_entry["category"], "desc": _bv_entry["desc"] + "；max 域经 obj 取负代理适配",
                      "tune": []}
# kpvar 变体：_KPV ctx 是 min 语义（obj=-value+罚）——挂原生 min bv（非 max 包装）；
# mckp(one-hot 无 repair)/mkpm(0..m 指派非二值) 编码不适配位向量 sigmoid——不挂（诚实）
_KPV_ALGOS.update(_bv_reg())
_KPV_ALGOS.pop("bv_sma")  # qkp 变体撤下 bv_sma（2026-09-28 严口径门）：-2026 vs 随机最优 -2058，其他位域均过门
_SSP_ALGOS.update(_bv_reg())
_CMP_ALGOS.update(_bv_reg())
_CMP_ALGOS.pop("bv_tlbo")  # cmp 撤下 bv_tlbo：教师阶段推力致解码越界（BIG 罚主导=不可行解），其余变体均过门
_CMP_ALGOS.pop("bv_mfo")  # cmp 撤下 bv_mfo：蛾焰螺旋致超载（20016 vs 随机最优 20，BIG 罚主导）
_KPVAR_ALGOS.update(_bv_reg())  # 并集清单（实际分派按 _kpvar_reg）

_SAT_ALGOS.update(_bv_reg())
_BIN_ALGOS.update(_bv_reg())
_BIN_ALGOS.pop("bv_ba")  # qubo 撤下 bv_ba：BA 響度接受准则在 qubo 大范围负目标上 50 代探索不足（-263 vs 基线 -280），setcover/uflp/sat 均强
_BIN_ALGOS.pop("bv_fa")  # qubo 撤下 bv_fa（监督复核 2026-09-27）：同族 seed 口径下 -295 vs 随机最优 -404（连最差 -348 未赢），与 bv_ba 同源探索不足；多 seed [-295,-567,-663] 仅 1/3 稳赢，seed 高度敏感
# qubo 单域撤下（2026-09-28 严口径门）：sca -386 vs 随机最优 -404 探索不足 -> 用 _qb_sca 温度适配层替之；
# mfo/eo 经 M4 文献核对修正后已过门（mfo -555/eo -564 vs -404）-> 下方逐域回挂块重新接入
_BIN_ALGOS.pop("bv_sca")
# 弱内核诚实标注（监督复核 WEAK 项：非假跑、边际通过——页面 desc 可见）
_UF_ALGOS.update(_bv_reg())  # uflp min 域（_SW 协议路线已通，bv 同理）
_SC_ALGOS["bv_tlbo"]["desc"] += "；弱内核（本域仅边际优于随机）"
_SAT_ALGOS["bv_ba"]["desc"] += "；弱内核（本域仅边际优于随机）"
_SAT_ALGOS.pop("bv_mfo")  # sat 撤下 bv_mfo（2026-09-28 终门）：8 vs 随机最优 7 严口径未赢——统一标准不保留严口径负格

# ---- complete-a-kernels 2026-09-29：严口径门回挂（逐域，不过门不挂） ----
# 实测（同族 3-seed 随机基线取最优，200 代）：
#   bv_gsa PASS: qubo(-549) sat(6) uflp(1147) knapsack(1604,max) kpvar(ssp/fractional/ukp/bkp/qkp/mdkp/dkp)
#   bv_gsa FAIL: setcover(159 vs 115)→不挂；cmp(19 vs 16)→不挂；mckp 走独立 _MCKP_ALGOS→安全
#   bv_hs  PASS: sat(6) knapsack(1501,max) kpvar(ssp/fractional/ukp/bkp/qkp/mdkp/dkp)
#   bv_hs  FAIL: qubo(-338) uflp(1314) cmp(19 vs 16)→不挂
#   bv_mfo PASS: qubo(-555) cmp(12 vs 16, 3-seed min 严口径边际)→回挂；sat 用 _sat_mfo 适配层替原 _bv_mfo
#   bv_eo  PASS: qubo(-564)→回挂
#   _qb_sca(温度适配) PASS: qubo(-788)→回挂；_sat_mfo(温度适配) PASS: sat(5)→回挂
#   _uf_local(UFLP 专属) PASS: uflp(1166 vs 1249)→回挂
#   _mo_nsga3 PASS: moco 前沿真·非支配(nd=40)+覆盖 8≥nsga2 7；maop 三目标非支配(nd=40)
# 原撤下原因（GSA 引力退化/HS 收敛不足）经 M4 文献核对 + 实测已不成立：现有 _bv_gsa(正典 Rashedi 2009 GSA)/
#   _bv_hs(正典 Geem 2001 HS) 在目标域过严口径门，故按域逐挂（不绕 _bv_reg 全局以防污染失败域）。
_bv_gsa_e = {"fn": _bv_gsa, "name": "引力 GSA（位）", "category": "群体智能",
            "desc": "经典引力搜索：质量加权吸引+sigmoid 映射（Rashedi 2009，文献核对修正）", "tune": []}
_bv_hs_e = {"fn": _bv_hs, "name": "和声 HS（位）", "category": "群体智能",
           "desc": "经典和声搜索：HMCR 记忆考量+PAR 音高调整（Geem 2001，文献核对修正）", "tune": []}
# 位编码 min 域：原生 min 内核直挂（kpvar 价值变体 ctx 为 min 语义）
for _reg in (_KPV_ALGOS, _SSP_ALGOS, _KPVAR_ALGOS):
    _reg["bv_gsa"] = dict(_bv_gsa_e)
    _reg["bv_hs"] = dict(_bv_hs_e)
_SAT_ALGOS["bv_gsa"] = dict(_bv_gsa_e)
_SAT_ALGOS["bv_hs"] = dict(_bv_hs_e)
_UF_ALGOS["bv_gsa"] = dict(_bv_gsa_e)            # uflp min；bv_hs 在 uflp FAIL 不挂
_UF_ALGOS["uf_local"] = {"fn": _uf_local, "name": "UFLP 局部搜索", "category": "局部搜索",
                         "desc": "单设施随机一阶改进+关一开一交换(0.6)+停滞重启：修复 UFLP 复合目标卡坏局部最优", "tune": []}
# knapsack 是 max 域：经 obj 取负代理适配（_maximize）
_KS_ALGOS["bv_gsa"] = {"fn": _maximize(_bv_gsa), "name": "引力 GSA（位·max）", "category": "群体智能",
                      "desc": "经典 GSA（Rashedi 2009），max 域经 obj 取负代理适配", "tune": []}
_KS_ALGOS["bv_hs"] = {"fn": _maximize(_bv_hs), "name": "和声 HS（位·max）", "category": "群体智能",
                     "desc": "经典 HS（Geem 2001），max 域经 obj 取负代理适配", "tune": []}
# qubo 大范围负目标：bv_mfo/bv_eo 经 M4 修正已过门（下方 _BIN_ALGOS 已保留）；bv_gsa 原生过门；_qb_sca 温度适配层补 sca 缺口
_BIN_ALGOS["bv_mfo"] = _bv_reg()["bv_mfo"]
_BIN_ALGOS["bv_eo"] = _bv_reg()["bv_eo"]
_BIN_ALGOS["bv_gsa"] = dict(_bv_gsa_e)
_BIN_ALGOS["qb_sca"] = {"fn": _qb_sca, "name": "SCA（位·温度适配）", "category": "群体智能",
                        "desc": "软阈值 sigmoid 解码(T=1.6)+gbest 位翻抛光，针对 QUBO 大范围负目标（Mirjalili 2016 适配）", "tune": []}
# sat：原 _bv_mfo 严口径负（8 vs 7），用 _sat_mfo 温度适配层替之
_SAT_ALGOS["sat_mfo"] = {"fn": _sat_mfo, "name": "MFO（位·温度适配）", "category": "群体智能",
                         "desc": "软阈值 sigmoid 解码(T=1.5)+gbest 位翻抛光，SAT 专属适配（Mirjalili 2015 适配）", "tune": []}
# cmp：bv_mfo 经 M4 修正 3-seed 严口径过门（12 vs 16，边际→弱内核标注）；bv_gsa/bv_hs 在 cmp FAIL 不挂
_CMP_ALGOS["bv_mfo"] = _bv_reg()["bv_mfo"]
_CMP_ALGOS["bv_mfo"]["desc"] += "；弱内核（cmp 变体仅边际优于随机，3-seed 严口径过门）"
# 多目标：NSGA-III 参考点小生境（Deb 2014 正典）
_MO_ALGOS["nsga3"] = {"fn": _mo_nsga3, "name": "NSGA-III", "category": "进化计算",
                      "desc": "Das-Dennis 参考点+垂直距离关联+小生境计数选择（Deb & Jain 2014 经典）", "tune": ["pc"]}


# ---- uflp 位编码接入（批 7 续）：_KS 内核直拉（同位编码族模式，_UF 已有 value/polish 桥） ----
# TODO 批 3 修：uflp 的 _KS 内核贪心卡坏局部最优（3616 vs random 1338）——
# _UF.value=−obj 桥方向正确但 KS 贪心在 uflp 的「设施+服务」复合目标上失效，
# 需要 uflp 专属内核或换 HC/SA 路线。桥代码保留（_UF.value/polish 已在）。
# gap 域接入（批 7 续）：_GAP 有 obj/repair/swap ✓，de/gwo 向量分支需整数 clamp ✓
_GAP_ALGOS.update({
    k: {"fn": fn, "name": nm, "category": cat, "desc": ds, "tune": tn}
    for k, (fn, nm, cat, ds, tn) in {
        "gwo": (_sw_gwo, "灰狼 GWO", "群体智能", "三狼指派投票（排列自适应）", []),
        "cs": (_sw_cs, "布谷鸟 CS", "群体智能", "莱维 swap 串+弃巢（域无关）", ["pa"]),
    }.items()})  # de 的向量差分对整数指派产生 float——跳过（需 round 适配，批 3+）
_UF_DEF.update({k: v for k, v in _KS_DEF.items() if k not in _UF_DEF})  # 补 F/CR/limit/pa 等键

# ---- 批 7 续（2026-09-27）：entryseq/gap 域接 de/gwo/cs（_ES 协议 min 直配 ✓） ----
_ES_ALGOS.update({k: {"fn": getattr(__import__(__name__), f"_sw_{k}"),
                      "name": nm, "category": cat, "desc": ds, "tune": tn}
                  for k, nm, cat, ds, tn in (
    ("de", "差分 DE", "进化计算", "自适应双模式差分（排列=swap 组合/向量=标准差分）", ["F"]),
    ("gwo", "灰狼 GWO", "群体智能", "三狼投票自适应（排列/向量双模）", []),
    ("cs", "布谷鸟 CS", "群体智能", "莱维 swap 串+弃巢（域无关）", ["pa"]))})
_GAP_ALGOS.update({k: {"fn": getattr(__import__(__name__), f"_sw_{k}"),
                       "name": nm, "category": cat, "desc": ds, "tune": tn}
                   for k, nm, cat, ds, tn in (
    ("gwo", "灰狼 GWO", "群体智能", "三狼指派投票（整数自适应）", []),
    ("cs", "布谷鸟 CS", "群体智能", "莱维 swap 串+弃巢（域无关）", ["pa"]))})


# ---- M2 排列域挂载（2026-09-28）：随机键桥接的连续系内核，一次挂载全域共享 ----
_PK_ALGOS = {k: {"fn": getattr(__import__(__name__), "_" + k), "name": nm, "category": cat, "desc": ds, "tune": []}
             for k, nm, cat, ds in (
    ("pk_pso", "粒子群 PSO（排列）", "群体智能", "随机键+速度位置（Bean 1994）"),
    ("pk_sca", "正弦余弦 SCA（排列）", "群体智能", "随机键+正弦余弦更新"),
    ("pk_mfo", "蛾焰 MFO（排列）", "群体智能", "随机键+经典多焰递减螺旋（Mirjalili 2015）"),
    ("pk_eo", "均衡 EO（排列）", "物理定律", "随机键+经典平衡池（Faramarzi 2020 核对修正）"),
    ("pk_ao", "天鹰 AO（排列）", "群体智能", "随机键+经典四阶段（Abualigah 2021 核对修正）"),
    ("pk_sma", "黏菌 SMA（排列）", "群体智能", "随机键+经典位移式（Li 2020 核对修正）"),
    ("pk_fa", "萤火虫 FA（排列）", "群体智能", "随机键+亮度吸引"),
    ("pk_ba", "蝙蝠 BA（排列）", "群体智能", "随机键+频率调谐"),
    ("pk_jaya", "Jaya（排列）", "群体智能", "随机键+向优避劣"),
    ("pk_tlbo", "TLBO（排列）", "人类与社会启发", "随机键+教师/学习"),
    ("pk_cem", "交叉熵 CEM（排列）", "进化计算", "随机键+精英均值回写+停滞重启"),
    ("pk_cmaes", "CMA-ES（排列·对角近似）", "进化计算", "随机键+对角步长自适应（诚实简化）"))}
for _reg in (_GC_ALGOS, _GCV_ALGOS, _BP_ALGOS, _BPVAR_ALGOS):
    _reg.update(_PK_ALGOS)
if "_GCVAR_ALGOS" in dir() or True:
    try:
        _GCVAR_ALGOS.update(_PK_ALGOS)  # 并级注册表（domain_start 预检用）
    except NameError:
        pass
_MIS_ALGOS.update(_bv_reg())  # mis 位串变体：挂位向量 bv 系（位编码天然适配，非排列）
try:
    _GCVAR_ALGOS.update(_bv_reg())  # 并级也挂 bv（domain_start 预检走并级，mis 变体分派用 _MIS_ALGOS）
except NameError:
    pass
for _reg_es in (_ES_ALGOS,):
    _reg_es.update(_PK_ALGOS)  # entryseq 排列变体挂随机键 pk 系（位/向量变体已有 bv 系）
# vrp 变体撤下 pk_sma（2026-09-28 严口径门）：994.79 vs 随机最优 959.98——Levy 大步在 VRP 路径域发散（sms 变体 12/12 过门）


# ---- entryseq：三种编码各配一套算法（2026-10 重做，取代此前「撤下」的补丁）----
# 此前 entryseq 把所有变体当排列用，再靠撤下清单掩盖不适用的组合：ga / ts 继承自位向量内核而全部崩溃；
# bv_*（位向量）与 pk_*（排列的随机键桥接）被无差别地挂在实数向量变体上，把 0/1 或 0..n-1 当作实数向量喂给目标函数——
# 能跑、不报错，但结果没有意义。现在每种编码只配适用的算法：
#   排列变体      random / hc / sa / de / gwo / cs（排列·向量双模）+ 新写的排列 ga / ts + pk_* 随机键系
#   位向量变体    与 QUBO 同一批位向量算法（含 ga / ts / bv_*）
#   实数向量变体  与连续函数同一批连续算法（pso / de / cmaes / …）
# 排列变体的算法集：去掉位向量 bv_*（把 0/1 当排列喂给目标函数，结果没有意义）和「greedy」
# （那个键指向的就是随机基线 _sw_random，与 random 重复，名字还误导）
_ES_PERM_ALGOS = {k: v for k, v in _ES_ALGOS.items() if not k.startswith("bv_") and k != "greedy"}


def _es_tournament(vals, rng, k=3):
    return min(rng.sample(range(len(vals)), min(k, len(vals))), key=vals.__getitem__)


def _es_ga(ctx, p, rng):
    """排列版遗传算法：锦标赛选择 + OX 顺序交叉 + 交换/插入变异 + 精英保留。"""
    n_pop = int(p.get("n_pop", 30))
    pop = [ctx.random(rng) for _ in range(n_pop)]
    vals = [ctx.obj(x) for x in pop]
    bi = min(range(n_pop), key=vals.__getitem__)
    best, bs = vals[bi], list(pop[bi])
    k_mut = max(1, round(p.get("pm", 0.06) * ctx.n))
    for it in range(1, p["max_iter"] + 1):
        new = [list(bs)]
        while len(new) < n_pop:
            a, b = _es_tournament(vals, rng), _es_tournament(vals, rng)
            child = _pm_ox(pop[a], pop[b], rng) if rng.random() < 0.9 else list(pop[a])
            if rng.random() < 0.5:
                for _ in range(k_mut):
                    child = _pm_swap(child, rng) if rng.random() < 0.5 else _pm_insert(child, rng)
            new.append(child)
        pop = new
        vals = [ctx.obj(x) for x in pop]
        bi = min(range(n_pop), key=vals.__getitem__)
        if vals[bi] < best:
            best, bs = vals[bi], list(pop[bi])
        yield {"iter": it, "best": best, "cur": sum(vals) / n_pop, "best_sol": list(bs)}


def _es_ts(ctx, p, rng):
    """排列版禁忌搜索：每步在 tries 个随机交换里取最好的非禁忌移动；刚交换过的位置对在 tenure 步内禁忌，
    但比历史最优还好的移动可以破禁（aspiration）。"""
    n = ctx.n
    s = ctx.random(rng)
    v = ctx.obj(s)
    best, bs = v, list(s)
    tabu = {}
    for it in range(1, p["max_iter"] + 1):
        pick = None
        for _ in range(int(p.get("tries", 48))):
            i, j = sorted(rng.sample(range(n), 2))
            t = list(s)
            t[i], t[j] = t[j], t[i]
            tv = ctx.obj(t)
            if tabu.get((i, j), 0) >= it and tv >= best:
                continue
            if pick is None or tv < pick[0]:
                pick = (tv, t, (i, j))
        if pick is None:  # 采样到的移动全被禁忌：随机扰动一下
            s = ctx.swap(s, rng)
            v = ctx.obj(s)
        else:
            v, s, mv = pick
            tabu[mv] = it + int(p.get("tenure", 10)) + rng.randrange(3)
        if v < best:
            best, bs = v, list(s)
        yield {"iter": it, "best": best, "cur": v, "best_sol": list(bs)}


_ES_PERM_ALGOS.update({
    "ga": {"fn": _es_ga, "name": "遗传算法 GA（排列）", "category": "进化计算",
           "desc": "锦标赛选择 + OX 顺序交叉 + 交换/插入变异 + 精英保留", "tune": ["pm"]},
    "ts": {"fn": _es_ts, "name": "禁忌搜索 TS（排列）", "category": "局部搜索",
           "desc": "随机交换邻域取最好非禁忌移动，禁忌位置对，破禁准则", "tune": ["tenure"]},
})


class _ESVecCN:
    """entryseq 实数向量变体 → 连续域算法期望的上下文（dim / lo / hi / eval / clamp / random / init_pop）。
    同时记下评价过的最优点，好让状态里带上完整的 best_sol。"""

    def __init__(self, es):
        self._es = es
        self.variant, self.p, self.n, self.vec = es.variant, es.p, es.n, True
        self.dim, self.lo, self.hi = es.n, -5.0, 5.0
        self.best_val, self.best_x = float("inf"), None

    def random(self, rng):
        return [rng.uniform(self.lo, self.hi) for _ in range(self.dim)]

    def eval(self, x):
        v = self._es.obj(x)
        if v < self.best_val:
            self.best_val, self.best_x = v, list(x)
        return v

    obj = eval

    def clamp(self, x):
        return [min(self.hi, max(self.lo, v)) for v in x]

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(p["n_pop"])]
        return pop, [self.eval(x) for x in pop]

    def detail(self, s):
        return self._es.detail(s)


_ES_BIT_DEF = dict(_QB_DEF, t0=3.0)  # _QB_DEF 已补齐 F / CR / limit / pa 等位编码算法要的键  # 子集类目标的可行差距是个位数，罚项 BIG 远大于它：温度取个位数
_ES_ALGOS_ALL = {}
for _reg_x in (_ES_PERM_ALGOS, _BIN_ALGOS, _CN_ALGOS):
    for _k_x, _v_x in _reg_x.items():
        _ES_ALGOS_ALL.setdefault(_k_x, _v_x)


def _es_registry(variant):
    """该变体的编码对应的算法集。"""
    if variant in BIT_VARIANTS:
        return _BIN_ALGOS
    if variant in VEC_VARIANTS:
        return _CN_ALGOS
    return _ES_PERM_ALGOS


def _es_defaults(variant):
    if variant in BIT_VARIANTS:
        return _ES_BIT_DEF
    if variant in VEC_VARIANTS:
        return _CN_DEF
    return _ES_DEF


def _es_blocked(variant, algo):
    """变体级不可用判定：domain_list 过滤与 domain_start 拒绝共用，避免页面列出幽灵选项。
    算法不在该变体编码的算法集里即不可用；另有个别组合因发散被撤下。"""
    return algo not in _es_registry(variant) or (variant in ("vrp", "vrptw", "vrpstw", "mdvrp") and algo == "pk_sma")  # pk_sma：Levy 大步在 VRP 路径域发散（严口径门，2026-09-28）


# ---- M3 指派域挂载（2026-09-28）：round+clamp 解码，gap 域专用 ----
_AS_ALGOS = {k: {"fn": getattr(__import__(__name__), "_" + k), "name": nm, "category": cat, "desc": ds, "tune": []}
             for k, nm, cat, ds in (
    ("as_pso", "粒子群 PSO（指派）", "群体智能", "实值位置+round-clamp"),
    ("as_sca", "正弦余弦 SCA（指派）", "群体智能", "正弦余弦+round-clamp"),
    ("as_mfo", "蛾焰 MFO（指派）", "群体智能", "经典多焰递减螺旋+round-clamp（Mirjalili 2015）"),
    ("as_eo", "均衡 EO（指派）", "物理定律", "经典平衡池+GCP 开关+round-clamp"),
    ("as_ao", "天鹰 AO（指派）", "群体智能", "经典四阶段+round-clamp（核对修正）"),
    ("as_sma", "黏菌 SMA（指派）", "群体智能", "经典位移式+log 权重+round-clamp"),
    ("as_fa", "萤火虫 FA（指派）", "群体智能", "亮度吸引+round-clamp"),
    ("as_ba", "蝙蝠 BA（指派）", "群体智能", "频率调谐+round-clamp"),
    ("as_jaya", "Jaya（指派）", "群体智能", "向优避劣+round-clamp"),
    ("as_tlbo", "TLBO（指派）", "人类与社会启发", "教师/学习+round-clamp"),
    ("as_cem", "交叉熵 CEM（指派）", "进化计算", "精英均值回写+停滞重启"),
    ("as_cmaes", "CMA-ES（指派·对角近似）", "进化计算", "对角步长自适应（诚实简化）"))}
_GAP_ALGOS.update(_AS_ALGOS)
_GAP_ALGOS.pop("as_mfo")  # gap 撤下 as_mfo（终审A 抓到 M4 续 4 撤下被条件分支静默跳过——多焰后 471 vs 427 严口径负，现真正落地）
# as_eo 曾撤下（470 vs 427），M4 文献核对（Faramarzi 2020 正典平衡池+GCP 开关）修正后 400 vs 427 过门 → 回挂
# as_sca 曾撤下（471 vs 427），M4 文献核对发现 SCA 更新式偏离正典（拼接变体 vs 标准 sin/cos），
# 修正为标准式（r4 切换 sin/cos，r3∈[0,2] 目的地权重）后 385 vs 427 过门 → 回挂


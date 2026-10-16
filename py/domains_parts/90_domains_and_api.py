_DOMAINS = {
    "knapsack": {"algos": _KS_ALGOS, "def": _KS_DEF, "make": ks_make},
    "continuous": {"algos": _CN_ALGOS, "def": _CN_DEF, "make": cn_make},
    "multiobj": {"algos": _MO_ALGOS, "def": _MO_DEF, "make": mo_make},
    "mocont": {"algos": MOC_ALGOS, "def": MOC_DEF, "make": mc_make},
    "graphcolor": {"algos": _GC_ALGOS, "def": _GC_DEF, "make": gc_make},
    "binpack": {"algos": _BP_ALGOS, "def": _BP_DEF, "make": bp_make},
    "setcover": {"algos": _SC_ALGOS, "def": _SC_DEF, "make": sc_make},
    "sat": {"algos": _SAT_ALGOS, "def": _SAT_DEF, "make": sat_make},
    "qubo": {"algos": _BIN_ALGOS, "def": _QB_DEF, "make": qb_make},
    "gap": {"algos": _GAP_ALGOS, "def": _GAP_DEF, "make": gap_make},
    "uflp": {"algos": _UF_ALGOS, "def": _UF_DEF, "make": uf_make},
    "entryseq": {"algos": _ES_ALGOS_ALL, "def": _ES_DEF, "make": es_make},
    "kpvar": {"algos": _KPVAR_ALGOS,
              # t0=25/decay=0.995：背包家族全变体标定值（bkp/ukp 需要高温慢冷；
              # _KS_DEF 的 8/0.985 只适用于背包枢纽实例）；F/CR/pm/limit/pa 供 _ks_de/ga/abc/cs
              "def": dict(_BIN_DEF, t0=25.0, decay=0.995, F=0.7, CR=0.6, pm=0.04,
                          limit=12, pa=0.25),
              "make": kpv_make},
    "gcvar": {"algos": _GCVAR_ALGOS,
              # 排列变体（listcolor 等）沿用图着色标定 t0=800/decay=0.985；
              # 但 ts_sample 降到 36（edgecolor/totalcolor 线图/全图 N 暴涨，O(N²) 解码下
              # 120 会让 TS 卡死浏览器）；mis 位串变体在 domain_start 内被 t0=30/decay=0.98 覆盖
              "def": dict(_GCVAR_DEF),
              "make": gcv_make},
    "bpvar": {"algos": _BPVAR_ALGOS,
              # 3 变体共用排列内核；VSBPP 成本目标 / 2D 箱数 / 条带高度，皆 FF/shelf 解码
              "def": dict(_BPVAR_DEF),
              "make": bpv_make},
    # 自带问题：三个变体 = 三种编码，各复用一批现成内核（位向量=QUBO 那批，排列=装箱那批，实数=连续函数那批）
    "custom": {"algos": _BIN_ALGOS, "def": _QB_DEF,
               "make": lambda seed=7, **kw: up_preset(kw.get("variant", "bits"), kw.get("n"), seed)},
}
_CUSTOM_REG = {"bits": (_BIN_ALGOS, _QB_DEF), "perm": (_BP_ALGOS, _BP_DEF), "real": (_CN_ALGOS, _CN_DEF)}

# === 排程域接线（2026-09-29 完善战役：nrp/ttp/sls 专业编码，见 py/scheduling.py）===
# 两种导入顺序都必须安全（2026-09-29 集成期抓到反向导入炸裂）：
#   A) 先 import domains：try-import scheduling 时 scheduling 反向 from domains import 四内核，
#      此点前四内核已全部定义 → scheduling 完整加载 → _wire_sched_domains 正常挂接；
#   B) 先 import scheduling：scheduling 第 26 行 from domains import → domains 重新入栈执行，
#      执行到本 wire 块时 scheduling 尚停在自身第 26 行（半加载，无 _SCHED_ALGOS）——
#      必须 fail-soft 跳过，等 scheduling 加载完成后由其尾部回挂（见 scheduling.py 尾注）。
# 浏览器拼接环境：import 抛 ImportError → gen_domains_src 在调度源码后注入 _schedmod 并调 _wire_sched_domains。
try:
    import scheduling as _schedmod
except ImportError:
    _schedmod = None

_SCHED_DOMAINS = ("nrp", "etp", "ttp", "sls")


def _wire_sched_domains(m):
    if not hasattr(m, "_SCHED_ALGOS"):
        return  # scheduling 半加载中（B 序循环导入保护）：主线 A 序/浏览器拼接环境不受影响
    _DOMAINS["nrp"] = {"algos": m._SCHED_ALGOS, "def": m._SCHED_DEF, "make": m.nrp_make}
    _DOMAINS["etp"] = {"algos": m._SCHED_ALGOS, "def": m._SCHED_DEF, "make": m.etp_make}
    _DOMAINS["ttp"] = {"algos": m._SCHED_ALGOS, "def": m._SCHED_DEF, "make": m.tour_make}
    _DOMAINS["sls"] = {"algos": m._SCHED_ALGOS, "def": m._SCHED_DEF, "make": m.sls_make}


if _schedmod is not None:
    _wire_sched_domains(_schedmod)

_RUN = {"gen": None, "ctx": None, "domain": None}


def _kpvar_reg(variant):
    """kpvar 变体 → 该变体可用的算法注册表（mckp/mkpm 与位向量变体内核不同；
    精确 DP 锚点按变体专属：ssp_dp 只挂 ssp，cmp_dp 只挂 cmp；
    密度贪心对 ssp（可达 0 差）/cmp（币值密度陷阱）无意义，不挂）。"""
    if variant == "mkpm":
        return _MKPM_ALGOS
    if variant in ("mckp", "dkp"):
        return _MCKP_ALGOS
    if variant == "ssp":
        return _SSP_ALGOS
    if variant == "cmp":
        return _CMP_ALGOS
    return _KPV_ALGOS


def _gcvar_reg(variant):
    """gcvar 变体 → 该变体可用的算法注册表。mis 用位串内核（_MIS_ALGOS），
    其余 4 个排列变体复用图着色内核（_GCV_ALGOS，含度序贪心锚点）。"""
    if variant == "mis":
        return _MIS_ALGOS
    return _GCV_ALGOS


def _bpvar_reg(variant):
    """bpvar 变体 → 算法注册表（3 变体共用排列内核 + 构造贪心锚点）。"""
    return _BPVAR_ALGOS


def domain_list(domain, opts=None):
    if isinstance(opts, str):
        opts = json.loads(opts) if opts else {}
    opts = opts or {}
    if domain in _SCHED_DOMAINS:
        lst = json.loads(_schedmod.sched_list(domain))
        for a in lst["algos"]:
            a["category"] = category_of(a["key"], a["category"])
        return json.dumps(lst)
    d = _DOMAINS[domain]
    algos = d["algos"]
    if domain == "kpvar":  # H 期：变体分派算法集（list 调用带 preset opts）
        algos = _kpvar_reg(opts.get("variant", "ssp"))
    elif domain == "gcvar":  # H2 期：变体分派算法集（着色家族 5 变体）
        algos = _gcvar_reg(opts.get("variant", "listcolor"))
    elif domain == "bpvar":  # H3 期：变体分派算法集（装箱家族 3 变体）
        algos = _bpvar_reg(opts.get("variant", "vsbinpack"))
    elif domain == "entryseq":  # 算法集按变体的编码分派（排列 / 位向量 / 实数向量），与 domain_start 的拒绝规则一致
        algos = {k: v for k, v in _es_registry(opts.get("variant", "sms")).items()
                 if not _es_blocked(opts.get("variant", "sms"), k)}
    elif domain == "custom":  # 自带问题：算法集按编码分派
        algos = _CUSTOM_REG[opts.get("variant", "bits")][0]
    if domain != "custom":  # 等评价次数门撤下的格子不再列出（自带问题的目标函数是用户的，不适用）
        _v = opts.get("variant") or {"kpvar": "ssp", "gcvar": "listcolor", "bpvar": "vsbinpack", "entryseq": "sms",
                                     "multiobj": "moco", "mocont": "zdt1"}.get(domain)
        algos = {k: v for k, v in algos.items() if not _is_withdrawn(domain, _v, k)}
    out = []
    for key, a in algos.items():
        # 分类以家族体系为准：同一个内核（如 bv_pso）在所有域/变体里标签一致；基线/贪心等不在体系里的沿用注册表
        out.append({"key": key, "name": a["name"], "category": category_of(key, a["category"]),
                    "desc": a["desc"], "tune": a["tune"]})
    defs = dict(_CUSTOM_REG[opts.get("variant", "bits")][1]) if domain == "custom" else dict(d["def"])
    if domain == "entryseq":
        defs = dict(_es_defaults(opts.get("variant", "sms")))
    # 终审2/审查2：变体专属参数覆盖必须同步到 defaults，否则面板展示值与引擎实跑不符
    if domain == "gcvar" and opts.get("variant", "listcolor") == "mis":
        defs.update(t0=30.0, decay=0.98)  # mis 位串内核口径（与 domain_start 覆盖一致）
    if domain == "kpvar" and opts.get("variant", "ssp") == "mkpm":
        defs.update(t0=25.0, decay=0.97)  # mkpm 指派景观口径（与 domain_start 覆盖一致）
    return json.dumps({"algos": out, "defaults": defs})


def domain_preset(domain, seed=7, opts=None):
    # 兼容两种传入：dict（Python 侧测试）或 JSON 字符串（worker 侧，globals.set 只能传标量）
    if isinstance(opts, str):
        opts = json.loads(opts) if opts else {}
    opts = opts or {}
    if domain in _SCHED_DOMAINS:
        return _schedmod.sched_preset(domain, seed=seed, opts=opts)
    if domain == "custom":
        return json.dumps(up_preset(opts.get("variant", "bits"), opts.get("n"), seed))
    if domain == "knapsack":
        return json.dumps(ks_make(n=int(opts.get("n", 40)), seed=seed))
    if domain == "continuous":
        return json.dumps(cn_make(fn=opts.get("fn", "rastrigin"), dim=int(opts.get("dim", 2))))
    if domain == "mocont":
        return json.dumps(mc_make(variant=opts.get("variant", "zdt1"), n=opts.get("n"), seed=seed))
    if domain == "multiobj":
        return json.dumps(mo_make(variant=opts.get("variant", "moco"),
                                  n=int(opts.get("n", 40)), seed=seed))
    if domain == "graphcolor":
        return json.dumps(gc_make(n=int(opts.get("n", 50)), seed=seed, p=float(opts.get("p", 0.5))))
    if domain == "binpack":
        return json.dumps(bp_make(n=int(opts.get("n", 40)), seed=seed))
    if domain == "setcover":
        return json.dumps(sc_make(n_el=int(opts.get("n_el", 80)), m=int(opts.get("m", 50)), seed=seed))
    if domain == "sat":
        return json.dumps(sat_make(n_vars=int(opts.get("n_vars", 30)),
                                   ratio=float(opts.get("ratio", 4.26)), seed=seed))
    if domain == "qubo":
        return json.dumps(qb_make(n=int(opts.get("n", 30)), seed=seed))
    if domain == "gap":
        return json.dumps(gap_make(n_a=int(opts.get("n_a", 8)), n_j=int(opts.get("n_j", 25)), seed=seed))
    if domain == "uflp":
        return json.dumps(uf_make(n_f=int(opts.get("n_f", 15)), n_c=int(opts.get("n_c", 45)), seed=seed))
    if domain == "entryseq":  # 原子词条域：9 变体统一 make
        return json.dumps(es_make(variant=opts.get("variant", "vrp"),
                                  n=int(opts.get("n", 12)), seed=seed))
    if domain == "kpvar":
        return json.dumps(kpv_make(variant=opts.get("variant", "ssp"),
                                   n=int(opts.get("n", 40)), seed=seed,
                                   k=(int(opts["k"]) if opts.get("k") else None),
                                   r=(int(opts["r"]) if opts.get("r") else None)))
    if domain == "gcvar":
        return json.dumps(gcv_make(variant=opts.get("variant", "listcolor"),
                                   n=int(opts.get("n", 40)), seed=seed,
                                   p=float(opts.get("p", 0.5))))
    if domain == "bpvar":
        return json.dumps(bpv_make(variant=opts.get("variant", "vsbinpack"),
                                   n=int(opts.get("n", 40)), seed=seed))
    raise ValueError(domain)


def domain_start(domain, problem_json, algo, params_json):
    if domain in _SCHED_DOMAINS:
        _RUN["domain"] = domain  # domain_step 据此路由到 scheduling.sched_step
        return _schedmod.sched_start(domain, problem_json, algo, params_json)
    d = _DOMAINS[domain]
    if domain == "custom":
        return _custom_start(problem_json, algo, params_json)
    if algo not in d["algos"]:
        raise ValueError(f"unknown algo {algo} for {domain}")
    problem = json.loads(problem_json)
    if _is_withdrawn(domain, problem.get("variant"), algo):
        raise ValueError(f"algo {algo} withdrawn for {domain}/{problem.get('variant') or '-'}（等评价次数下赢不了随机搜索，见 data/withdrawn_cells.json）")
    p = dict(d["def"])
    p.update(json.loads(params_json) if params_json else {})
    rng = random.Random(p["seed"])
    if domain == "knapsack":
        ctx = _KS(problem)
        info = {"n": ctx.n, "cap": ctx.cap, "items": [[w, v] for w, v in ctx.items], "sense": "max"}
    elif domain == "continuous":
        ctx = _CN(problem)
        if problem["fn"] in _NEW_FUNCS:
            # 后加的函数取值范围和量级差别很大（Schwefel 的范围是 ±500、Zakharov 的值能到 1e5）：
            # 模拟退火的温度、各算法的步长是按 ±5 的老函数标定的，这里按函数的范围与随机点上的离散程度换算
            # （用户在算法参数里显式填了的不动）。老函数不走这里，行为与黄金快照保持一致。
            user_keys = set(json.loads(params_json)) if params_json else set()
            vals = [ctx.eval(ctx.random(random.Random(97 + i))) for i in range(24)]
            mu = sum(vals) / len(vals)
            sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5
            if "t0" not in user_keys and sd > 0:
                p["t0"] = sd * 0.5
            if "sigma" not in user_keys:
                p["sigma"] = 0.06 * (ctx.hi - ctx.lo)
        info = {"fn": problem["fn"], "dim": ctx.dim, "lo": ctx.lo, "hi": ctx.hi,
                "sense": "min", "optimum": FUNCS[problem["fn"]][3]}
    elif domain == "mocont":
        ctx = MOC(problem)
        info = {"variant": ctx.variant, "name": ctx.name, "n": ctx.n, "m": ctx.m, "sense": "min",
                "ref": ctx.ref, "front": true_front(ctx.variant)}
    elif domain == "multiobj":
        vt = problem.get("variant", "moco")
        if vt == "maop":
            ctx = _MO3(problem)
            info = {"n": ctx.n, "cap": ctx.cap,
                    "items": [[w, v1, v2, v3] for w, v1, v2, v3 in ctx.items],
                    "sense": "max3"}
        else:
            ctx = _MO(problem)
            info = {"n": ctx.n, "cap": ctx.cap, "items": [[w, v1, v2] for w, v1, v2 in ctx.items], "sense": "max2"}
    elif domain == "graphcolor":
        ctx = _GC(problem)
        info = {"n": ctx.n, "edges": problem["edges"], "pos": problem["pos"], "sense": "min"}
    elif domain == "binpack":
        ctx = _BP(problem)
        total = sum(ctx.items)
        info = {"n": ctx.n, "cap": ctx.cap, "items": ctx.items, "sense": "min",
                "lb": -(-total // ctx.cap)}
    elif domain == "entryseq":  # 原子词条域：变体专属可视化信息
        ctx = es_ctx(problem)
        if _es_blocked(problem.get("variant"), algo):  # 算法与该变体的编码不匹配 / 已撤下 → 明确拒绝，不静默乱跑
            raise ValueError(f"algo {algo} not available for variant {problem.get('variant')}")
        user = json.loads(params_json) if params_json else {}
        if ctx.bits or ctx.vec:  # 位向量 / 实数向量变体用各自编码的默认参数
            p = dict(_es_defaults(ctx.variant))
            if ctx.vec:
                ctx = _ESVecCN(ctx)
                vals = [ctx.eval(ctx.random(random.Random(97 + i))) for i in range(24)]
                mu = sum(vals) / len(vals)
                sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5
                ctx.best_val, ctx.best_x = float("inf"), None  # 标定用的随机点不算「找到的最优」
                if sd > 0:
                    p["t0"] = sd * 0.5  # 目标量级未知（SSE 上千、设计问题带罚项上万）：温度按随机点的离散程度换算
            p.update(user)
            rng = random.Random(p["seed"])
        info = {"n": ctx.n, "variant": ctx.variant, "sense": "min"}
    elif domain == "setcover":
        ctx = _SC(problem)
        info = {"n_el": ctx.n_el, "m": ctx.m, "sets": ctx.sets, "costs": ctx.costs,
                "sense": "min"}
    elif domain == "sat":
        ctx = _SAT(problem)
        info = {"n_vars": ctx.n, "clauses": ctx.clauses, "sense": "min",
                "n_clauses": len(ctx.clauses)}
    elif domain == "qubo":
        ctx = _QB(problem)
        info = {"n": ctx.n, "Q": ctx.Q, "sense": "min"}
    elif domain == "gap":
        ctx = _GAP(problem)
        info = {"n_a": ctx.n_a, "n_j": ctx.n_j, "c": ctx.c, "r": ctx.r,
                "cap": ctx.cap, "sense": "min"}
    elif domain == "uflp":
        ctx = _UF(problem)
        info = {"n_f": ctx.n_f, "n_c": ctx.n_c, "f_cost": ctx.f_cost,
                "c_cost": ctx.c_cost, "pos_f": problem["pos_f"],
                "pos_c": problem["pos_c"], "sense": "min"}
    elif domain == "kpvar":
        vt = problem.get("variant", "ssp")
        ctx = _MKPM(problem) if vt == "mkpm" else (_MCKP(problem) if vt in ("mckp", "dkp")
                                                   else _KPV(problem))
        reg = _kpvar_reg(vt)
        if algo not in reg:
            raise ValueError(f"algo {algo} not available for variant {vt}")
        if vt == "mkpm":
            # mkpm 指派景观标定：SA 需要 t0=25/decay=0.97（位编码变体用 0.995）；
            # 用户显式调 t0/decay 则不覆盖
            user_keys = set(json.loads(params_json)) if params_json else set()
            for k, v in (("t0", 25.0), ("decay", 0.97)):
                if k not in user_keys:
                    p[k] = v
        if reg[algo]["fn"] in _KS_FNS:
            # _KS 内核是 max-sense + polish 组件：位编码变体走 max 包装器
            ctx = _KPVMaxWrap(ctx)
        info = dict(problem, sense="min")
    elif domain == "gcvar":
        vt = problem.get("variant", "listcolor")
        if vt == "mis":
            ctx = _MIS(problem)
            reg = _MIS_ALGOS
            # mis 位串变体用 _BIN_DEF 口径（t0=30/decay=0.98），覆盖 _GC_DEF 的 800/0.985
            user_keys = set(json.loads(params_json)) if params_json else set()
            for k, v in (("t0", 30.0), ("decay", 0.98)):
                if k not in user_keys:
                    p[k] = v
        else:
            ctx = _GCV(problem)
            reg = _GCV_ALGOS
        if algo not in reg:
            raise ValueError(f"algo {algo} not available for variant {vt}")
        info = dict(problem, sense="min")
    elif domain == "bpvar":
        ctx = _BPV(problem)
        reg = _BPVAR_ALGOS
        if algo not in reg:
            raise ValueError(f"algo {algo} not available for bpvar")
        info = dict(problem, sense="min")
    else:
        raise ValueError(domain)
    _RUN["domain"] = domain
    _RUN["ctx"] = ctx
    if domain == "entryseq":
        gen = _es_stream(_es_registry(ctx.variant)[algo]["fn"](ctx, p, rng), ctx)
    else:
        gen = reg[algo]["fn"](ctx, p, rng) if domain in ("kpvar", "gcvar") else d["algos"][algo]["fn"](ctx, p, rng)
    if domain == "kpvar" and isinstance(ctx, _KPVMaxWrap):
        gen = _neg_stream(gen)  # _KS 内核报 max-value；kpvar 全站 min-sense 口径
    _RUN["gen"] = gen
    return json.dumps(info)


def _custom_start(problem_json, algo, params_json):
    """自带问题：校验 → 建上下文 → 按编码挑内核 → 把内核的状态流整理成统一口径（sense、完整最优解、出错统计）。"""
    problem, errs, _warns, _info = up_check(json.loads(problem_json), dry_runs=6)
    if problem is None:
        raise ValueError("custom: " + "; ".join(e["msg"] for e in errs))
    reg, defs = _CUSTOM_REG[problem["variant"]]
    if algo not in reg:
        raise ValueError(f"algo {algo} not available for custom/{problem['variant']}")
    user = json.loads(params_json) if params_json else {}
    ctx = up_make_ctx(problem)
    p = dict(defs)
    p.update(up_auto_params(ctx, set(user)))  # 温度 / 步长按用户目标函数的量级换算（用户显式给了的不动）
    p.update(user)
    rng = random.Random(p["seed"])
    _RUN["domain"] = "custom"
    _RUN["ctx"] = ctx
    _RUN["gen"] = up_wrap_stream(reg[algo]["fn"](ctx, p, rng), ctx)
    info = dict(problem)
    info["sense"] = problem["sense"]
    info["auto_params"] = {k: v for k, v in p.items() if k in ("t0", "sigma") and k not in user}
    return json.dumps(info)


def domain_step():
    if _RUN.get("domain") in _SCHED_DOMAINS:
        return _schedmod.sched_step()
    s = next(_RUN["gen"], None)
    if s is None:
        return None
    return json.dumps(s)


def domain_bench(domain, iters=200, seed=7, algos=None):
    """命令行快速基准：返回 {algo: 终值}，用于页面数据与测试阈值校准。"""
    if domain in _SCHED_DOMAINS:
        return _schedmod.sched_bench(domain, iters=iters, seed=seed, algos=algos)
    d = _DOMAINS[domain]
    prob = d["make"](seed=seed)
    out = {}
    for key in (algos or list(d["algos"])):
        info = json.loads(domain_start(domain, json.dumps(prob), key, json.dumps({"max_iter": iters, "seed": seed})))
        last = None
        while True:
            s = domain_step()
            if s is None:
                break
            last = json.loads(s)
        out[key] = last["best"] if domain != "multiobj" else last["nd"]
    return out


if __name__ == "__main__" and __import__("sys").platform != "emscripten":
    # Pyodide/WASM 里 __name__ 也是 "__main__"，必须用平台判断挡住，否则浏览器加载时就跑基准
    for dm in ("knapsack", "continuous", "multiobj", "graphcolor", "binpack",
               "setcover", "sat", "qubo", "gap", "uflp", "kpvar"):
        print(dm, domain_bench(dm))

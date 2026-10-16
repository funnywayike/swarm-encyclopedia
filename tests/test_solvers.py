# -*- coding: utf-8 -*-
"""本地测试：不需要浏览器，验证算法包正确性（W1 交付验收之一）"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "py"))

from solvers import (  # noqa: E402
    SOLVERS,
    IterationState,
    build_problem,
    list_solvers,
    nearest_neighbor,
    start,
    step,
    step_k,
    tour_length,
    two_opt_improve,
    apply_swaps,
    swap_seq_to_target,
)

CITIES_4 = [[0, 0], [1, 0], [1, 1], [0, 1]]


def test_distance_matrix_symmetric():
    p = build_problem(CITIES_4)
    D = p["D"]
    for i in range(4):
        assert D[i][i] == 0.0
        for j in range(4):
            assert abs(D[i][j] - D[j][i]) < 1e-12


def test_tour_length_on_square():
    p = build_problem(CITIES_4)
    assert abs(tour_length([0, 1, 2, 3], p["D"]) - 4.0) < 1e-9  # 单位正方形周长
    assert abs(tour_length([0, 2, 1, 3], p["D"]) - (2 + 2 * 2 ** 0.5)) < 1e-9


def test_nearest_neighbor_valid_permutation():
    cities = [[i * 3 % 17, i * 7 % 13] for i in range(20)]
    p = build_problem(cities)
    tour = nearest_neighbor(p["D"])
    assert sorted(tour) == list(range(20))


def test_two_opt_never_worsens():
    cities = [[i * 5 % 97, i * 11 % 89] for i in range(25)]
    p = build_problem(cities)
    base = nearest_neighbor(p["D"])
    c0 = tour_length(base, p["D"])
    improved = two_opt_improve(base, p["D"])
    assert sorted(improved) == list(range(25))
    assert tour_length(improved, p["D"]) <= c0 + 1e-9


def test_swap_sequence_transforms_correctly():
    cur = [3, 1, 0, 2]
    target = [0, 1, 2, 3]
    seq = swap_seq_to_target(list(cur), target)
    assert apply_swaps(list(cur), seq) == target


def _run(algo, cities, params):
    """用 JS 同款 start/step 接口跑完，返回 (首代, 末代, 代数)"""
    start(json.dumps(cities), algo, json.dumps(params))
    first = last = None
    count = 0
    while True:
        s = step()
        if s is None:
            break
        d = json.loads(s)
        assert set(["iteration", "best_cost", "best_tour", "current_cost", "extra"]).issubset(d.keys())
        t = d["best_tour"]
        if len(t) < len(cities):
            # 构造型算法（NN）构造中：部分路径，城市不重复、从 0 号城市出发
            assert len(set(t)) == len(t) and t[0] == 0
        else:
            assert sorted(t) == list(range(len(cities)))
        if first is None:
            first = d
        last = d
        count += 1
    return first, last, count


def test_start_step_api_contract():
    cities = [[i * 7 % 101, i * 13 % 97] for i in range(20)]
    first, last, count = _run("pso", cities, {"max_iter": 30, "seed": 1})
    assert count == 30
    assert last["iteration"] == 30
    assert last["best_cost"] <= first["best_cost"] + 1e-9


def test_pso_converges_below_baseline():
    cities = [[i * 7 % 101, i * 13 % 97] for i in range(30)]
    _, nn_last, _ = _run("nn", cities, {})
    _, pso_last, _ = _run("pso", cities, {"max_iter": 80, "seed": 42, "n_particles": 30})
    assert pso_last["best_cost"] < nn_last["best_cost"]


def test_aco_converges_below_baseline():
    cities = [[i * 7 % 101, i * 13 % 97] for i in range(30)]
    _, nn_last, _ = _run("nn", cities, {})
    _, aco_last, count = _run("aco", cities, {"max_iter": 60, "seed": 42})
    assert count == 60
    assert aco_last["best_cost"] < nn_last["best_cost"]


def test_aco_beats_two_opt_on_larger_instance():
    """n=100 时 ACO（带局部搜索）应优于纯 2-opt —— 这是调参有效性的护栏测试"""
    rng = random.Random(3)
    cities = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(100)]
    _, opt_last, _ = _run("2opt", cities, {"max_moves": 1000})
    _, aco_last, _ = _run("aco", cities, {"max_iter": 200, "seed": 42})
    assert aco_last["best_cost"] < opt_last["best_cost"]


def test_ga_sa_gwo_all_converge_below_baseline():
    """所有群智能/进化/物理启发算法都必须跑到优于最近邻基线 —— 基本可用性底线"""
    cities = [[i * 7 % 101, i * 13 % 97] for i in range(30)]
    _, nn_last, _ = _run("nn", cities, {})
    for algo in ("ga", "sa", "gwo", "abc", "fa", "woa", "de", "cs", "sca", "hho",
                 "ba", "hs", "gsa", "tlbo", "bfo", "mfo", "fwa", "afsa", "cem",
                 "ssa", "alo", "boa", "ica", "salp", "sfla",
                 "fpa", "kh", "sos", "jaya", "da", "mpa", "cscrow", "bbo"):
        _, last, count = _run(algo, cities, {"max_iter": 120, "seed": 42})
        assert count == 120, f"{algo} 代数不对"
        assert last["best_cost"] < nn_last["best_cost"], f"{algo} 没能优于 NN 基线"


def test_local_search_frameworks_beat_full_two_opt():
    """局部搜索框架护栏：ILS/VNS/LK 的存在意义就是超越完整 2-opt。

    框架 = 扰动/换邻域/变深度 + 下探。如果 200 代跑下来还不如一次
    完整 2-opt，说明框架在空转（扰动没踢出去，或下探预算浪费了）。
    """
    rng = random.Random(11)
    cities = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(50)]
    _, ref_last, _ = _run("2opt", cities, {"start": "nn", "max_moves": 500})
    ref = ref_last["best_cost"]
    for algo in ("ils", "vns", "lk"):
        _, last, _ = _run(algo, cities, {"max_iter": 150, "seed": 42})
        assert last["best_cost"] < ref, (
            f"{algo} ({last['best_cost']:.1f}) 没能超越完整 2-opt ({ref:.1f})，框架空转"
        )


def test_ts_occasionally_accepts_worsening():
    """禁忌搜索的核心机制：允许接受变差的移动跳出局部最优。

    200 代里若从没走过"变差的一步"，说明特赦/禁忌机制没在工作，
    退化成了普通爬山法。
    """
    cities = [[i * 7 % 101, i * 13 % 97] for i in range(30)]
    start(json.dumps(cities), "ts", json.dumps({"max_iter": 200, "seed": 42}))
    worsening = 0
    while True:
        s = step()
        if s is None:
            break
        d = json.loads(s)
        worsening += 1 if d["extra"].get("worsening") else 0
    assert worsening > 0, "TS 200 代从未接受变差移动，禁忌机制疑似失效"


def test_no_fake_optimization():
    """★ 防假跑护栏：关掉全部局部搜索后，群智能算法自身仍必须明显优于初始解。

    这条测试防的是最危险的一类 bug：曲线在降，但下降全是 2-opt 的功劳，
    算法本身一点没干活。GWO 第一版（随机键）和第二版（随机排列播种）
    都会栽在这条测试上。改动任何算法后这条必须是绿的。
    """
    rng = random.Random(11)
    cities = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(60)]
    _, nn_last, _ = _run("nn", cities, {})
    baseline = nn_last["best_cost"]
    for algo in ("pso", "aco", "ga", "gwo", "abc", "fa", "woa", "de", "cs", "sca", "hho",
                 "ba", "hs", "gsa", "tlbo", "bfo", "mfo", "fwa", "afsa", "cem",
                 "ica", "salp", "sfla", "fpa", "kh", "sos", "jaya",
                 "da", "mpa", "cscrow", "bbo"):
        _, last, _ = _run(
            algo,
            cities,
            {"max_iter": 200, "seed": 42, "ls_every": 0, "local_search": 0.0},
        )
        assert last["best_cost"] < baseline * 0.95, (
            f"{algo} 关掉局部搜索后几乎没优化（{baseline:.0f} → {last['best_cost']:.0f}），"
            "说明算法本身没在干活，下降全靠 2-opt 撑着"
        )


def test_ssa_alo_boa_real_iteration_progress():
    """★ 防假跑第二重门：1 代 → 200 代必须有真实迭代进步（≥1%）。

    及格线全靠初始化播种、迭代在空转的假跑（DE/GWO 都栽过）在这条测试上现形。
    SSA 第一版三连坑：贪心准入 + 随机试射在已收敛种群上零进步，最后靠
    「扰动 + 预算制 2-opt 下探直接作用于全局最优本体」才过门（见 solvers.py）。
    """
    rng = random.Random(11)
    cities = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(60)]
    for algo in ("ssa", "alo", "boa"):
        first, last, _ = _run(algo, cities, {"max_iter": 200, "seed": 42, "ls_every": 0, "ls_moves": 0})
        assert last["best_cost"] < first["best_cost"] * 0.99, (
            f"{algo} 1代→200代几乎无真实进步（{first['best_cost']:.0f} → {last['best_cost']:.0f}），"
            "及格线疑似全靠初始化播种"
        )


def test_sfla_real_iteration_progress_multi_seed():
    """★ SFLA 防假跑第二重门（多种子版）：1 代 → 200 代必须有真实迭代进步。

    4 个求解器种子在同一实例上全部要有 ≥1% 真实进步（实测 4/4）。
    注：个别简单实例（如随机种子 37 生成的实例）存在「秒解」现象——
    SFLA 的重置动力学在 gen-1 就摸到 ILS 跑满 200 代的收敛值（642.2，
    实测与 ILS 终值完全一致），此后无进步空间但并非假跑，故门 2 不在该
    实例上判定，改用下方正向断言记录秒解质量。
    """
    rng = random.Random(11)
    cities = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(60)]
    for sseed in (42, 7, 13, 99):
        first, last, _ = _run("sfla", cities, {"max_iter": 200, "seed": sseed, "ls_every": 0, "ls_moves": 0})
        assert last["best_cost"] < first["best_cost"] * 0.99, (
            f"SFLA(seed={sseed}) 1代→200代几乎无真实进步"
            f"（{first['best_cost']:.0f} → {last['best_cost']:.0f}）"
        )


def test_sfla_instant_solve_instance_reaches_ils_endgame():
    """SFLA 的「秒解」实例正向记录：gen-1 即达 ILS 收敛点的实例上，
    终值必须仍然远优于 NN 基线（证明不是空转，而是收敛太快）。"""
    rng = random.Random(37)
    cities = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(60)]
    _, nn_last, _ = _run("nn", cities, {})
    _, last, _ = _run("sfla", cities, {"max_iter": 200, "seed": 42, "ls_every": 0, "ls_moves": 0})
    assert last["best_cost"] < nn_last["best_cost"] * 0.9, (
        f"SFLA 在秒解实例上终值 {last['best_cost']:.0f} 不够优（NN={nn_last['best_cost']:.0f}）"
    )


def test_p13a_real_iteration_progress_multi_seed():
    """★ P1.3a 四算法（FPA/KH/SOS/Jaya）防假跑第二重门（多种子版）。

    组件化重构后首批装配的算法，收录时实测：KH/SOS/Jaya 各实例种子 4/4 通过，
    FPA 修过一次「Levy 越步语义丢失」假跑（f>1 应跳出盆地而非继续向最优走），
    修后 4/4。这条测试锁死该基线。
    """
    rng = random.Random(11)
    cities = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(60)]
    for algo in ("fpa", "kh", "sos", "jaya"):
        for sseed in (42, 7, 13, 99):
            first, last, _ = _run(algo, cities, {"max_iter": 200, "seed": sseed, "ls_every": 0, "ls_moves": 0})
            assert last["best_cost"] < first["best_cost"] * 0.99, (
                f"{algo}(seed={sseed}) 1代→200代几乎无真实进步"
                f"（{first['best_cost']:.0f} → {last['best_cost']:.0f}）"
            )


def test_p13b_real_iteration_progress_multi_seed():
    """★ P1.3b 四算法（DA/MPA/CS乌鸦/BBO）防假跑第二重门（多种子版）。

    收录时实测：DA/CS乌鸦 各 4/4 通过；MPA/BBO 3/4——个别种子 gen-1
    已贴「30 次随机重启 2-opt 底线」（实例 11 底线 619.0，gen-1 即 619.7），
    <1% 门测的是贴底而非假跑（MPA seed7 甚至在第 174 代仍有真实下降），
    故按 ≥3/4 判定（SFLA 秒解先例同款）。
    """
    rng = random.Random(11)
    cities = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(60)]
    for algo in ("da", "mpa", "cscrow", "bbo"):
        passed = 0
        for sseed in (42, 7, 13, 99):
            first, last, _ = _run(algo, cities, {"max_iter": 200, "seed": sseed, "ls_every": 0, "ls_moves": 0})
            if last["best_cost"] < first["best_cost"] * 0.99:
                passed += 1
        assert passed >= 3, f"{algo} 4 个求解器种子仅 {passed} 个有真实迭代进步（疑似假跑）"


def test_p13c_real_iteration_progress_multi_seed():
    """★ P1.3c 四算法（GRASP/AIS/EO/AO）防假跑第二重门（多种子版）。

    收录时实测（tools/verify_p13c_pure.py）：四算法各 4/4 通过，总计 16/16——
    P1.3c 是三批次中唯一一次收录即全绿的批次。GRASP 踩过两次假跑：
    区间式 RCL 在均匀散点上候选列表膨胀失效（构造值 1690，200 代零进步）；
    数量式 RCL 宽度必须小（k=2 甜区，k=5 构造烂一个数量级）。
    这条测试锁死 16/16 基线。
    """
    rng = random.Random(11)
    cities = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(60)]
    for algo in ("grasp", "ais", "eo", "ao"):
        for sseed in (42, 7, 13, 99):
            first, last, _ = _run(algo, cities, {"max_iter": 200, "seed": sseed, "ls_every": 0, "ls_moves": 0})
            assert last["best_cost"] < first["best_cost"] * 0.99, (
                f"{algo}(seed={sseed}) 1代→200代几乎无真实迭代进步"
                f"（{first['best_cost']:.0f} → {last['best_cost']:.0f}）"
            )


def test_gwo_leader_hierarchy_is_valid():
    """GWO 的 α/β/δ 必须满足成本递增的等级关系，且 a 随迭代线性下降"""
    cities = [[i * 7 % 101, i * 13 % 97] for i in range(25)]
    _, last, _ = _run("gwo", cities, {"max_iter": 100, "seed": 42})
    extra = last["extra"]
    assert extra["a"] < 0.05, "收敛因子 a 末代应趋近 0"
    # alpha_cost 在 extra 里保留 2 位小数，比较时给 0.01 容差
    assert extra["alpha_cost"] <= last["best_cost"] + 0.01
    assert extra["n_wolves"] > 0


def test_sa_reports_temperature_and_accept_rate():
    cities = [[i * 7 % 101, i * 13 % 97] for i in range(25)]
    first, last, _ = _run("sa", cities, {"max_iter": 100, "seed": 42})
    assert first["extra"]["temperature"] > last["extra"]["temperature"], "温度必须单调下降"
    assert 0.0 <= first["extra"]["accept_rate"] <= 1.0


def test_step_k_batch_sampling_contract():
    """v0.3 采样间隔依赖 step_k：批量推进 k 代并返回逐代采样点"""
    cities = [[i * 7 % 101, i * 13 % 97] for i in range(20)]
    start(json.dumps(cities), "pso", json.dumps({"max_iter": 20, "seed": 1}))
    iters = []
    batches = 0
    while True:
        s = step_k(5)
        if s is None:
            break
        d = json.loads(s)
        assert "points" in d and "exhausted" in d
        assert len(d["points"]) <= 5
        for it, best, cur in d["points"]:
            iters.append(it)
            assert best >= 0 and cur >= 0
        assert d["iteration"] == iters[-1]
        assert sorted(d["best_tour"]) == list(range(len(cities)))
        batches += 1
        if d["exhausted"]:
            break
    # 20 代按每批 5 代推进：批数 ≤ 5，且代数覆盖连续
    assert batches <= 5
    assert iters == list(range(1, len(iters) + 1))
    # 耗尽后再调必须返回 None
    assert step_k(5) is None


def test_step_k_k1_matches_step():
    """k=1 时 step_k 应与旧 step() 语义一致（基线计算走这条路径）"""
    cities = [[i * 7 % 101, i * 13 % 97] for i in range(15)]
    start(json.dumps(cities), "nn", json.dumps({}))
    a = json.loads(step_k(1))
    start(json.dumps(cities), "nn", json.dumps({}))
    b = json.loads(step())
    assert abs(a["best_cost"] - b["best_cost"]) < 1e-9
    assert a["points"][0][0] == b["iteration"]
    # points 里是传输用 3 位舍入值，顶层 best_cost 是全精度
    assert abs(a["points"][0][1] - b["best_cost"]) < 1e-3


def test_run_all_returns_curves_for_all_implemented():
    """对比页依赖 run_all，必须覆盖全部已实现算法"""
    from solvers import run_all

    rng = random.Random(5)
    cities = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(20)]
    out = json.loads(run_all(json.dumps(cities), max_iter=50, seed=42))
    implemented = {d["key"] for d in json.loads(list_solvers()) if d["implemented"]}
    assert implemented <= set(out["results"].keys())
    for key, r in out["results"].items():
        assert r["final"] is not None and len(r["curve"]) > 0
    assert out["nn"] > 0


def test_all_registered_solvers_expose_contract():
    data = json.loads(list_solvers())
    keys = {d["key"] for d in data}
    assert {"pso", "2opt", "nn", "aco", "ga", "sa", "gwo", "abc", "fa", "woa",
            "ts", "de", "cs", "sca", "hho",
            "ils", "vns", "lk", "ba", "hs", "gsa", "tlbo", "bfo", "mfo",
            "fwa", "afsa", "cem", "ssa", "alo", "boa",
            "ica", "salp", "sfla", "fpa", "kh", "sos", "jaya",
            "da", "mpa", "cscrow", "bbo",
            "grasp", "ais", "eo", "ao"} <= keys
    for d in data:
        if d["implemented"]:
            assert issubclass(SOLVERS[d["key"]], object)
            assert d["name"]
            assert d.get("category"), f"{d['key']} 缺分类"


def test_nn_constructs_step_by_step():
    """v0.5.1：NN 改为逐城构造动画——n 个城市产生 n 个状态，构造期路径开放不闭合"""
    cities = [[i * 7 % 101, i * 13 % 97] for i in range(12)]
    start(json.dumps(cities), "nn", json.dumps({}))
    states = []
    while True:
        s = step()
        if s is None:
            break
        states.append(json.loads(s))
    assert len(states) == 12
    final_cost = states[-1]["best_cost"]
    # 构造期：路径逐城 +1、保持开放（extra.open=True）、best_cost 恒等于最终成本
    for k, st in enumerate(states[:-1], start=1):
        assert st["extra"].get("open") is True, f"第 {k} 步应为开放路径"
        assert len(st["best_tour"]) == k + 1
        assert st["best_tour"] == states[-1]["best_tour"][: k + 1]
        assert abs(st["best_cost"] - final_cost) < 1e-9
    # 末代：闭合完整回路，成本与路径一致
    assert states[-1]["extra"].get("open") is not True
    assert sorted(states[-1]["best_tour"]) == list(range(12))
    p = build_problem(cities)
    assert abs(tour_length(states[-1]["best_tour"], p["D"]) - final_cost) < 1e-6


def test_best_cost_monotonic_all_solvers():
    """★ 收敛曲线红线语义护栏：全局最优 best_cost 逐代只降不升（历史最优永远保留）。

    用户报告"收敛曲线反而向上"时确认：灰线（当代成本）允许波动，
    红线（全局最优）在任何算法里都绝不允许回升——这条测试就是铁闸。
    """
    rng = random.Random(9)
    cities = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(30)]
    for algo, cls in SOLVERS.items():
        if not cls.implemented:
            continue
        params = {} if algo == "nn" else {"max_iter": 40, "seed": 42}
        start(json.dumps(cities), algo, json.dumps(params))
        prev = float("inf")
        while True:
            s = step()
            if s is None:
                break
            d = json.loads(s)
            assert d["best_cost"] <= prev + 1e-9, f"{algo} 的 best_cost 出现回升"
            prev = d["best_cost"]


def test_param_specs_cover_defaults():
    """调参模块依赖 param_specs：每个已实现算法的默认值必须落在自己声明的定义域内"""
    data = json.loads(list_solvers())
    for d in data:
        if not d["implemented"]:
            continue
        specs = d.get("specs") or {}
        for k, v in d["params"].items():
            if k in ("seed", "max_iter", "start", "init"):
                continue  # seed/迭代数走专属输入框，枚举型单独处理
            assert k in specs, f"{d['key']}.{k} 缺定义域声明"
            sp = specs[k]
            if sp.get("type") == "choice":
                assert v in sp["options"], f"{d['key']}.{k} 默认值不在选项内"
            else:
                lo = sp.get("min", float("-inf"))
                hi = sp.get("max", float("inf"))
                assert lo <= v <= hi, f"{d['key']}.{k} 默认值 {v} 超出定义域 [{lo},{hi}]"


def test_aco_survives_duplicate_city_coordinates():
    """用户上传数据可能含重复坐标点（D=0），ACO 不得除零崩溃"""
    cities = [[10, 10], [50, 50], [50, 50], [90, 10], [10, 90], [90, 90]]  # (50,50) 重复
    first, last, count = _run("aco", cities, {"max_iter": 20, "seed": 42})
    assert count == 20
    assert last["best_cost"] > 0

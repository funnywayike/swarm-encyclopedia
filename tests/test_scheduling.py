# -*- coding: utf-8 -*-
"""排程建模线测试（批 2 撤下词条 nrp/ttp/sls 重设计）——防假跑铁律落地。

硬门槛（与 test_domains.py 同族 seed 严口径一致）：
  ① 每变体的每个算法（除 random 基线）必须严格优于 random 基线（best-of-200），
     即目标函数有区分度、内核在真实优化而非假跑。
  ② repair 产物可行性断言：
       nrp：repair(随机解) 覆盖缺口=0（硬约束达标）；
       etp：repair(随机解) 同时段硬冲突=0（图着色式重排生效）；
       sls：repair(故意损坏解) 轮次完整（每轮恰含 {0..m-1} 各一次）=0。
  ③ seed 可复现：同 (problem,algo,seed) 两次跑终值 best 与 best_sol 完全一致。

域名实（2026-09-29 正名）：键 ttp=旅行锦标赛（tour_make），考试时间表=etp（etp_make）。

注意：本测试只依赖 py/scheduling.py（其自身 from domains import _SW 内核），不触碰 domains.py。
"""
import json
import os
import random as _random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "py"))
import scheduling as S  # noqa: E402

ALGOS = ["hc", "sa", "ts", "ga", "de", "gwo", "cs"]   # 非 random 算法
SEEDS = (1, 3, 7, 13, 42)                             # 严口径同族 seed
ITERS = 200


def _run(problem, algo, iters, seed):
    """镜像 test_domains._run：返回 (first, last, n)。"""
    S.sched_start(problem, S.sched_preset(problem, seed=seed), algo,
                  json.dumps({"max_iter": iters, "seed": seed}))
    first = last = None
    n = 0
    while True:
        s = S.sched_step()
        if s is None:
            break
        d = json.loads(s)
        if first is None:
            first = d
        last = d
        n += 1
    return first, last, n


# ---------------- ① 每变体 beats random（同族 seed 严口径：每 seed 的算法终值 < 同 seed 随机基线） ----------------

def test_nrp_all_beat_random():
    for seed in SEEDS:
        _, rnd, n = _run("nrp", "random", ITERS, seed)
        assert n == ITERS, f"nrp random seed{seed} 迭代数不对: {n}"
        base = rnd["best"]
        for algo in ALGOS:
            _, last, n = _run("nrp", algo, ITERS, seed)
            assert n == ITERS, f"nrp {algo} seed{seed} 迭代数不对"
            assert last["best"] < base, (
                f"nrp {algo} seed{seed} 没赢同 seed random 基线: {last['best']} vs {base}")


def test_etp_all_beat_random():
    for seed in SEEDS:
        _, rnd, n = _run("etp", "random", ITERS, seed)
        assert n == ITERS, f"etp random seed{seed} 迭代数不对: {n}"
        base = rnd["best"]
        for algo in ALGOS:
            _, last, n = _run("etp", algo, ITERS, seed)
            assert n == ITERS, f"etp {algo} seed{seed} 迭代数不对"
            assert last["best"] < base, (
                f"etp {algo} seed{seed} 没赢同 seed random 基线: {last['best']} vs {base}")


def test_ttp_all_beat_random():
    """ttp=旅行锦标赛（2026-09-29 正名后新域）。"""
    for seed in SEEDS:
        _, rnd, n = _run("ttp", "random", ITERS, seed)
        assert n == ITERS, f"ttp random seed{seed} 迭代数不对: {n}"
        base = rnd["best"]
        for algo in ALGOS:
            _, last, n = _run("ttp", algo, ITERS, seed)
            assert n == ITERS, f"ttp {algo} seed{seed} 迭代数不对"
            assert last["best"] < base, (
                f"ttp {algo} seed{seed} 没赢同 seed random 基线: {last['best']} vs {base}")


def test_sls_all_beat_random():
    for seed in SEEDS:
        _, rnd, n = _run("sls", "random", ITERS, seed)
        assert n == ITERS, f"sls random seed{seed} 迭代数不对: {n}"
        base = rnd["best"]
        for algo in ALGOS:
            _, last, n = _run("sls", algo, ITERS, seed)
            assert n == ITERS, f"sls {algo} seed{seed} 迭代数不对"
            assert last["best"] < base, (
                f"sls {algo} seed{seed} 没赢同 seed random 基线: {last['best']} vs {base}")


# ---------------- ② repair 可行性断言 ----------------

def test_nrp_repair_coverage():
    prob = S.nrp_make(seed=7)
    ctx = S._NRP(prob)
    rng = _random.Random(7)
    s = ctx.random(rng)                       # 随机解：留有覆盖缺口
    assert ctx.coverage_gap(s) > 0, "nrp 随机解不应已达标（测试前提）"
    s2 = ctx.repair(s)                         # 贪心覆盖补位
    assert ctx.coverage_gap(s2) == 0, f"nrp repair 后仍有覆盖缺口: {ctx.coverage_gap(s2)}"


def test_etp_repair_zero_conflict():
    prob = S.etp_make(seed=7)
    ctx = S._ETP(prob)
    rng = _random.Random(7)
    s = ctx.random(rng)                        # 随机解：留有同时段冲突
    assert ctx.n_conflicts(s) > 0, "ttp 随机解不应已零冲突（测试前提）"
    s2 = ctx.repair(s)                         # 冲突驱动重排（largest-degree-first + min-conflicts）
    assert ctx.n_conflicts(s2) == 0, f"ttp repair 后仍有硬冲突: {ctx.n_conflicts(s2)}"


def test_sls_repair_round_complete():
    prob = S.sls_make(seed=7)
    ctx = S._SLS(prob)
    rng = _random.Random(7)
    s = ctx.random(rng)                        # 可行轮次（每轮排列）
    assert ctx.rounds_complete(s) == 0, "sls 随机可行解应轮次完整（测试前提）"
    # 故意损坏：第 0 轮制造重复队号（缺某队）
    s_corrupt = list(s)
    s_corrupt[0] = s_corrupt[1]
    assert ctx.rounds_complete(s_corrupt) >= 1, "损坏解应出现不完整轮（测试前提）"
    s2 = ctx.repair(s_corrupt)                # 轮内交换恢复
    assert ctx.rounds_complete(s2) == 0, f"sls repair 后仍有不完整轮: {ctx.rounds_complete(s2)}"


# ---------------- ③ seed 可复现 ----------------

def test_nrp_seed_reproducible():
    b1, s1 = _last("nrp", "sa", 7)
    b2, s2 = _last("nrp", "sa", 7)
    assert (b1, s1) == (b2, s2), "nrp sa seed7 不可复现"


def test_etp_seed_reproducible():
    b1, s1 = _last("etp", "ts", 7)
    b2, s2 = _last("etp", "ts", 7)
    assert (b1, s1) == (b2, s2), "etp ts seed7 不可复现"


def test_ttp_seed_reproducible():
    """ttp=旅行锦标赛。"""
    b1, s1 = _last("ttp", "ga", 7)
    b2, s2 = _last("ttp", "ga", 7)
    assert (b1, s1) == (b2, s2), "ttp ga seed7 不可复现"


def test_sls_seed_reproducible():
    b1, s1 = _last("sls", "ga", 7)
    b2, s2 = _last("sls", "ga", 7)
    assert (b1, s1) == (b2, s2), "sls ga seed7 不可复现"


def _last(problem, algo, seed):
    _, last, _ = _run(problem, algo, ITERS, seed)
    return last["best"], last["best_sol"]


# ---------------- 额外：真实进度（防假跑二次确认） ----------------

def test_strong_algos_make_progress():
    for problem, algo in (("nrp", "sa"), ("etp", "ts"), ("ttp", "sa"), ("sls", "ga")):
        first, last, _ = _run(problem, algo, ITERS, 7)
        assert last["best"] < first["best"], (
            f"{problem} {algo} 全程无进步（假跑嫌疑）: {first['best']} -> {last['best']}")


# ---------------- 入口规整化防御（2026-09-29 主线集成期，页面自定义输入边界） ----------------

def test_sls_odd_m_normalized():
    """奇数队经 make 规整化为偶数（双循环每轮 g=m/2 场须恰覆盖 m 队）。"""
    import scheduling as S
    p7 = S.sched_make("sls", m=7, seed=7)
    assert p7["m"] == 8 and p7["per"] == 8, f"奇数 m 未规整化: {p7['m']}"
    p5 = S.sched_make("sls", m=5, seed=7)
    assert p5["m"] == 6 and p5["R"] == 10


def test_nrp_small_n_normalized():
    """N<S 与 N<7 边界不再炸 randint（页面 custom_fields N min=4）。"""
    import scheduling as S
    p1 = S.sched_make("nrp", N=2, S=3, seed=7)   # N<S → 规整化 N=S
    assert p1["N"] == 3
    p2 = S.sched_make("nrp", N=4, S=2, seed=7)   # N<7 → 需求带收窄，不炸
    assert p2["N"] == 4
    # 默认 N=10 路径逐位不变（bench 证据不受入口防御影响）
    a = S.sched_make("nrp", seed=7)
    b = S.sched_make("nrp", seed=7)
    assert a == b and a["N"] == 10


# ---------------- 旅行锦标赛 TTP 专属（2026-09-29 正名后新增域） ----------------

def test_ttp_odd_m_normalized():
    """奇数队规整化为偶数 + 下限 4；距离阵对称、对角 0（旅行目标的前提）。"""
    import scheduling as S
    p7 = S.sched_make("ttp", m=7, seed=7)
    assert p7["m"] == 8 and p7["R"] == 14, f"奇数 m 未规整化: {p7['m']}"
    p2 = S.sched_make("ttp", m=2, seed=7)
    assert p2["m"] == 4, "m 下限未钳到 4"
    d = p7["dist"]
    for a in range(p7["m"]):
        assert d[a][a] == 0
        for b in range(a + 1, p7["m"]):
            assert d[a][b] == d[b][a] and d[a][b] > 0, "距离阵非对称正定"


def test_ttp_repair_round_complete():
    """损坏解经 repair 恢复轮次完整（与 sls 同款防御，域独立断言）。"""
    import scheduling as S
    prob = S.sched_make("ttp", seed=7)
    ctx = S._TOUR(prob)
    rng = _random.Random(7)
    s = ctx.random(rng)
    assert ctx.rounds_complete(s) == 0, "随机可行解应轮次完整（测试前提）"
    s_corrupt = list(s)
    s_corrupt[0] = s_corrupt[1]
    assert ctx.rounds_complete(s_corrupt) >= 1
    assert ctx.rounds_complete(ctx.repair(s_corrupt)) == 0

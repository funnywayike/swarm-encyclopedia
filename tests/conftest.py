# -*- coding: utf-8 -*-
"""测试分档：快档（日常、每次提交）与慢档（`slow` 标记）。

    python -m pytest tests -q -m "not slow"     快档（目标：一分钟左右）
    python -m pytest tests -q -m slow           只跑慢档
    python -m pytest tests -q                   全部（约 10 分钟）

慢档 = 要把整个「域 × 变体 × 算法」矩阵跑一遍的，或单个测试超过约 8 秒的。标记集中放在这里，不散落在各个测试文件里：
测试变慢时在这一处加一行即可。CI 的慢档（夜间 / 合并到主干时）跑全部。"""
import pytest

# 整个模块都算慢档
SLOW_MODULES = {
    "test_golden",           # 把约 2100 个组合用固定种子重跑一遍
    "test_consistency",      # 每个域 × 变体 × 算法检查「上报的 best 能由上报的解重算」
    "test_smoke_matrix",     # 每个下拉选项真跑几代
    "test_browser_namespace",  # 在干净子进程里按浏览器的方式执行拼接源码并跑全部域 / 变体
}

# 单个慢测试（模块名, 测试函数名前缀）
SLOW_TESTS = [
    ("test_domains", "test_kpvar_all_beat_random"),
    ("test_domains", "test_gcvar_"),
    ("test_domains", "test_bpvar_"),
    ("test_domains", "test_graphcolor_real_progress"),
    ("test_domains", "test_binpack_"),
    ("test_kernels_v2", "test_kpvar_bv_gsa_hs_beats_random"),
    ("test_scheduling", "test_ttp_all_beat_random"),
    ("test_scheduling", "test_sls_all_beat_random"),
    ("test_scheduling", "test_etp_all_beat_random"),
    ("test_solvers", "test_no_fake_optimization"),
    ("test_solvers", "test_sfla_real_iteration_progress_multi_seed"),
    ("test_solvers", "test_p13"),
    ("test_solvers", "test_run_all_returns_curves_for_all_implemented"),
    ("test_mocont", "test_nsga2_beats_random_on_the_new_variants"),
    ("test_mocont", "test_the_real_algorithms_beat_random_search_by_a_wide_margin"),
    ("test_recipe", "test_upgrade_recipes_improve_on_30city"),
]


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: 慢档测试（整张矩阵或单个超过约 8 秒），日常用 -m 'not slow' 跳过")


def pytest_collection_modifyitems(config, items):
    for item in items:
        mod = item.module.__name__.split(".")[-1]
        name = item.originalname or item.name
        if mod in SLOW_MODULES or any(mod == m and name.startswith(p) for m, p in SLOW_TESTS):
            item.add_marker(pytest.mark.slow)

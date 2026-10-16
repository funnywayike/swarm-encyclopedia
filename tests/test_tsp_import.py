# -*- coding: utf-8 -*-
"""TSP 导入：TSPLIB / id,x,y CSV / 距离矩阵 都必须被正确读取，读不懂的必须明确拒绝（不能静默读错）。

背景：旧的 TSP 页导入逐行取「前两个数」——TSPLIB 的 `1 10.0 20.0` 被读成 (1, 10)，结果看起来正常但问题已不是用户的问题。"""
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "py"))

import components as C  # noqa: E402
import solvers as S  # noqa: E402
import validate as V  # noqa: E402

TSPLIB_EUC = """NAME : demo5
COMMENT : hand-made
TYPE : TSP
DIMENSION : 5
EDGE_WEIGHT_TYPE : EUC_2D
NODE_COORD_SECTION
1 10.0 20.0
2 30.0 20.0
3 30.0 50.0
4 10.0 50.0
5 20.0 35.0
EOF
"""


def _errs(res):
    return " | ".join(f"{e['path']}: {e['msg']}" for e in res["errors"])


def _check(text, **kw):
    return V.check_text(text, domain=kw.pop("domain", "tsp"), **kw)


# ---------------------------------------------------------------- TSPLIB

def test_tsplib_coordinates_skip_node_ids():
    r = _check(TSPLIB_EUC, filename="demo5.tsp")
    assert r["ok"], _errs(r)
    assert r["problem"]["cities"][0] == [10.0, 20.0]  # 不是 [1, 10]
    assert r["problem"]["cities"][4] == [20.0, 35.0]
    assert r["problem"]["metric"] == "EUC_2D"


def test_tsplib_detected_without_extension_or_domain():
    r = V.check_text(TSPLIB_EUC)
    assert r["ok"] and r["domain"] == "tsp"


def test_tsplib_rejects_what_it_cannot_do():
    cases = {
        "atsp": TSPLIB_EUC.replace("TYPE : TSP", "TYPE : ATSP"),
        "cvrp": TSPLIB_EUC.replace("TYPE : TSP", "TYPE : CVRP"),
        "3d": TSPLIB_EUC.replace("EUC_2D", "EUC_3D"),
        "dimension": TSPLIB_EUC.replace("DIMENSION : 5", "DIMENSION : 6"),
        "no-coords": TSPLIB_EUC.replace("NODE_COORD_SECTION", "SOMETHING_ELSE"),
    }
    for name, text in cases.items():
        r = _check(text, filename="x.tsp")
        assert not r["ok"], name
    assert "ATSP" in _errs(_check(cases["atsp"], filename="x.tsp"))


def test_tsplib_explicit_formats_agree():
    # 4 城市的同一个对称矩阵，用 5 种 TSPLIB 排列写出来，必须还原成同一个矩阵
    M = [[0, 3, 4, 5], [3, 0, 6, 7], [4, 6, 0, 8], [5, 7, 8, 0]]
    n = 4

    def tpl(fmt, nums):
        return (f"TYPE : TSP\nDIMENSION : {n}\nEDGE_WEIGHT_TYPE : EXPLICIT\nEDGE_WEIGHT_FORMAT : {fmt}\n"
                f"EDGE_WEIGHT_SECTION\n{' '.join(str(v) for v in nums)}\nEOF\n")

    full = [v for row in M for v in row]
    upper = [M[i][j] for i in range(n) for j in range(i + 1, n)]
    lower = [M[i][j] for i in range(n) for j in range(i)]
    upper_d = [M[i][j] for i in range(n) for j in range(i, n)]
    lower_d = [M[i][j] for i in range(n) for j in range(i + 1)]
    texts = {"FULL_MATRIX": full, "UPPER_ROW": upper, "LOWER_ROW": lower, "UPPER_DIAG_ROW": upper_d,
             "LOWER_DIAG_ROW": lower_d, "UPPER_COL": lower, "LOWER_COL": upper, "UPPER_DIAG_COL": lower_d,
             "LOWER_DIAG_COL": upper_d}
    for fmt, nums in texts.items():
        r = _check(tpl(fmt, nums), filename="m.tsp")
        assert r["ok"], f"{fmt}: {_errs(r)}"
        assert [[int(v) for v in row] for row in r["problem"]["matrix"]] == M, fmt
        assert r["problem"]["metric"] == "matrix"
    assert not _check(tpl("UPPER_ROW", upper[:-1]), filename="m.tsp")["ok"]  # 数不够


def test_tsplib_explicit_uses_display_data_for_drawing():
    text = ("TYPE : TSP\nDIMENSION : 4\nEDGE_WEIGHT_TYPE : EXPLICIT\nEDGE_WEIGHT_FORMAT : UPPER_ROW\n"
            "DISPLAY_DATA_TYPE : TWOD_DISPLAY\nEDGE_WEIGHT_SECTION\n1 2 3 4 5 6\nDISPLAY_DATA_SECTION\n"
            "1 0 0\n2 5 0\n3 5 5\n4 0 5\nEOF\n")
    r = _check(text, filename="d.tsp")
    assert r["ok"], _errs(r)
    assert r["problem"]["cities"] == [[0.0, 0.0], [5.0, 0.0], [5.0, 5.0], [0.0, 5.0]]


# ---------------------------------------------------------------- CSV / 文本

def test_csv_id_x_y_drops_the_id_column():
    r = _check("id,x,y\n1,10,20\n2,30,20\n3,30,50\n4,10,50\n", filename="c.csv")
    assert r["ok"], _errs(r)
    assert r["problem"]["cities"] == [[10, 20], [30, 20], [30, 50], [10, 50]]
    r0 = _check("0,10,20\n1,30,20\n2,30,50\n3,5,5\n", filename="c.csv")  # 0 起始的编号也认
    assert r0["ok"] and r0["problem"]["cities"][0] == [10, 20]


def test_csv_three_columns_that_are_not_ids_is_an_error():
    r = _check("5,10,20\n9,30,20\n2,30,50\n7,1,1\n", filename="c.csv")
    assert not r["ok"] and "编号" in _errs(r)


def test_csv_wrong_width_is_an_error():
    assert not _check("1,2,3,4\n5,6,7,8\n9,1,2,3\n4,5,6,7\n5,6,7,8\n", filename="c.csv")["ok"]


def test_csv_two_columns_still_work():
    r = _check("x,y\n0,0\n1,0\n1,1\n0,1\n", filename="c.csv")
    assert r["ok"] and r["problem"] == {"cities": [[0, 0], [1, 0], [1, 1], [0, 1]]}


# ---------------------------------------------------------------- 距离矩阵

SQ = [[0, 5, 9, 4], [5, 0, 3, 8], [9, 3, 0, 7], [4, 8, 7, 0]]


def test_square_matrix_from_json_and_csv():
    for res in (V.validate("tsp", SQ), V.validate("tsp", {"matrix": SQ}),
                _check("\n".join(",".join(map(str, r)) for r in SQ), filename="m.csv")):
        assert res["ok"], _errs(res)
        assert res["problem"]["metric"] == "matrix" and res["problem"]["matrix"] == SQ
        assert len(res["problem"]["cities"]) == 4  # 无坐标：环形布局，只用来画图
        assert res["warnings"]


def test_asymmetric_matrix_is_refused_with_an_explanation():
    A = [row[:] for row in SQ]
    A[0][1] = 6
    r = V.validate("tsp", {"matrix": A})
    assert not r["ok"] and "ATSP" in _errs(r)


def test_bad_matrices():
    assert not V.validate("tsp", {"matrix": [[0, 1, 2, 3], [1, 0, 3, 4]]})["ok"]       # 非方阵
    nz = [[0, 1, 2, 3], [1, 0, 3, 4], [2, 3, 0, 5], [3, 4, 5, 0]]
    bad_diag = [r[:] for r in nz]
    bad_diag[1][1] = 7
    neg = [r[:] for r in nz]
    neg[0][1] = neg[1][0] = -1
    assert not V.validate("tsp", {"matrix": bad_diag})["ok"]                            # 对角非 0
    assert not V.validate("tsp", {"matrix": neg})["ok"]                                 # 负距离
    assert not V.validate("tsp", {"matrix": [[0, 1, 2], [1, 0, 3], [2, 3, 0]]})["ok"]  # 3 城市：无需求解
    assert not V.validate("tsp", {"matrix": SQ, "metric": "ATT"})["ok"]


def test_matrix_with_coordinates_for_drawing():
    pos = [[0, 0], [1, 0], [1, 1], [0, 1]]
    r = V.validate("tsp", {"matrix": SQ, "cities": pos})
    assert r["ok"] and r["problem"]["cities"] == pos and not r["warnings"]
    assert not V.validate("tsp", {"matrix": SQ, "cities": pos[:3]})["ok"]


def test_size_limit_for_matrix():
    n = V.LIMITS["tsp"] + 1
    assert not V.validate("tsp", {"matrix": [[0] * n for _ in range(n)]})["ok"]


def test_revalidating_a_normalised_problem_is_stable():
    for res in (V.validate("tsp", {"matrix": SQ}), V.check_text(TSPLIB_EUC, filename="a.tsp")):
        again = V.validate("tsp", res["problem"])
        assert again["ok"], _errs(again)
        assert again["problem"]["metric"] == res["problem"]["metric"]


# ---------------------------------------------------------------- 引擎侧：距离函数与矩阵

def test_tsplib_distance_functions():
    assert C._tsplib_dist("EUC_2D", [0, 0], [3, 4]) == 5
    assert C._tsplib_dist("EUC_2D", [0, 0], [1, 1]) == 1      # 1.414 → 四舍五入 1
    assert C._tsplib_dist("EUC_2D", [0, 0], [2, 1]) == 2      # 2.236 → 2
    assert C._tsplib_dist("CEIL_2D", [0, 0], [1, 1]) == 2     # 向上取整
    assert C._tsplib_dist("MAN_2D", [0, 0], [1.4, 1.4]) == 3  # 2.8 → 3
    assert C._tsplib_dist("MAX_2D", [0, 0], [3, 7]) == 7
    # ATT：r = sqrt(d²/10)；t = nint(r)；t < r 时 +1
    assert C._tsplib_dist("ATT", [0, 0], [10, 0]) == 4        # r=3.162, t=3 <r → 4
    assert C._tsplib_dist("ATT", [0, 0], [100, 0]) == 32      # r=31.62, t=32 ≥ r → 32
    g = C._tsplib_dist("GEO", [10.0, 10.0], [20.0, 20.0])
    assert g == C._tsplib_dist("GEO", [20.0, 20.0], [10.0, 10.0]) and g > 1000  # 对称、量级是公里


def test_problem_from_spec_variants():
    pts = [[0, 0], [3, 4], [6, 0]]
    assert C.problem_from_spec(pts)["D"][0][1] == 5.0                                  # 裸列表（旧协议）
    assert C.problem_from_spec({"cities": pts})["D"] == C.build_problem(pts)["D"]
    assert C.problem_from_spec({"cities": pts, "metric": "EUC_2D"})["D"][0][2] == 6.0
    p = C.problem_from_spec({"cities": pts, "metric": "matrix", "matrix": [[0, 1, 2], [1, 0, 3], [2, 3, 0]]})
    assert p["D"][1][2] == 3.0 and p["n"] == 3


def test_solvers_find_the_true_optimum_on_an_explicit_matrix():
    """矩阵实例真的被用来算距离：6 城市的暴力最优必须被找到（若误用坐标，答案会不同）。"""
    M = [[0, 2, 9, 10, 7, 3], [2, 0, 6, 4, 3, 8], [9, 6, 0, 8, 5, 4],
         [10, 4, 8, 0, 6, 9], [7, 3, 5, 6, 0, 2], [3, 8, 4, 9, 2, 0]]
    best = min(sum(M[t[i]][t[(i + 1) % 6]] for i in range(6)) for t in
               ([0] + list(p) for p in itertools.permutations(range(1, 6))))
    res = V.validate("tsp", {"matrix": M})
    assert res["ok"], _errs(res)
    S.start(json.dumps(res["problem"]), "ga", json.dumps({"max_iter": 60, "seed": 3}))
    last = None
    while True:
        s = S.step()
        if s is None:
            break
        last = json.loads(s)
    assert last["best_cost"] == best
    assert len(set(last["best_tour"])) == 6


def test_legacy_bare_list_protocol_unchanged():
    pts = [[0, 0], [10, 0], [10, 10], [0, 10], [5, 5]]
    S.start(json.dumps(pts), "nn", "{}")
    assert S.step() is not None
    out = json.loads(S.run_all(json.dumps(pts), 3, 1))
    assert out["n"] == 5 and out["results"]


def test_every_solver_survives_tiny_instances():
    """校验器允许 4 城市起步；n=5 时曾有 11 个算法在 or-opt 移动里崩溃（段长 3 把城市取光了）。"""
    import random
    rng = random.Random(11)
    for n in range(V.TSP_MIN, 11):
        pts = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(n)]
        prob = S.problem_from_spec(pts)
        for key, cls in S.SOLVERS.items():
            if not cls.implemented:
                continue
            for st in cls().solve(prob, {"max_iter": 4, "seed": n}):
                assert st.extra.get("open") or sorted(st.best_tour) == list(range(n)), (key, n)

# -*- coding: utf-8 -*-
"""
标准化数据层：把「用户上传的数据」变成「引擎能放心吃的实例」。

三件事：
  1. 校验：给出带路径的中文错误（"items[3][0]：重量必须大于 0"），而不是 IndexError；
  2. 规整：n / m / K 等冗余字段由数据推出（用户不用再手写，也不会写错）；绘图坐标缺省自动布局；
  3. 解析：JSON 信封、CSV（背包/装箱/图/QUBO）、DIMACS（.cnf 可满足性 / .col 图着色）。

纯标准库，浏览器（Pyodide）与本地 Python 共用同一份。

入口：
    load(text_or_obj, domain=None, filename=None) -> (domain, data, issues)
    validate(domain, data, variant=None, dry_run=False) -> Result
    Result = {"ok": bool, "errors": [...], "warnings": [...], "problem": dict|None}
    每条问题 = {"path": "items[3][0]", "msg": "..."}

信封格式（swarm-problem/v1）：
    {"schema": "swarm-problem/v1", "domain": "knapsack", "data": {...}}
    裸实例（不带信封）+ 显式 domain 参数也可；页面导出的 domain-experiment/v1 同样接受。
"""
import csv
import io
import json
import math
import re

SCHEMA = "swarm-problem/v1"
RESULT_SCHEMA = "swarm-result/v1"  # 求解结果；里面带完整实例，所以也可以当作「问题文件」重新导入

# 支持上传的域。排程四域（etp/nrp/sls/ttp）暂不开放上传。
CORE_DOMAINS = ("tsp", "knapsack", "kpvar", "multiobj", "binpack", "bpvar", "graphcolor", "gcvar",
                "setcover", "sat", "qubo", "gap", "uflp", "continuous", "entryseq", "custom", "mocont")

# 规模上限：Pyodide 在浏览器里跑，过大实例会卡死标签页
LIMITS = {
    "tsp": 500, "knapsack": 1000, "kpvar": 1000, "multiobj": 1000, "binpack": 1000, "bpvar": 500,
    "graph_nodes": 500, "graph_edges": 50000, "setcover_cells": 250000, "sat_vars": 1000,
    "sat_clauses": 10000, "qubo": 200, "gap_agents": 50, "gap_jobs": 500, "uflp_f": 100,
    "uflp_c": 1000, "continuous_dim": 100, "entryseq": 300,
}


# ------------------------------------------------------------------ 引擎定位

def _engine():
    """问题域引擎模块。本地/测试里是 `import domains`；浏览器（Pyodide）里引擎源码以 __main__ 身份拼接执行，
    没有名为 domains 的模块，此时从 __main__ 取同一批函数（domain_preset / FUNCS / _DOMAINS …）。"""
    try:
        import domains
        return domains
    except ImportError:
        import sys
        m = sys.modules.get("__main__")
        if m is not None and hasattr(m, "domain_preset"):
            return m
        raise


# ------------------------------------------------------------------ 工具

class _R:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def err(self, path, msg):
        self.errors.append({"path": path, "msg": msg})

    def warn(self, path, msg):
        self.warnings.append({"path": path, "msg": msg})


def _show(x):
    s = json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else repr(x)
    return s if len(s) <= 40 else s[:37] + "…"


def _isnum(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _int(R, path, x, lo=None, hi=None, what="整数"):
    if isinstance(x, float) and math.isfinite(x) and x.is_integer():
        x = int(x)
    if not isinstance(x, int) or isinstance(x, bool):
        R.err(path, f"应为{what}，收到 {_show(x)}")
        return None
    if lo is not None and x < lo:
        R.err(path, f"应 ≥ {lo}，收到 {x}")
        return None
    if hi is not None and x > hi:
        R.err(path, f"应 ≤ {hi}，收到 {x}")
        return None
    return x


def _num(R, path, x, lo=None, hi=None, positive=False, what="数字"):
    if not _isnum(x):
        R.err(path, f"应为{what}，收到 {_show(x)}")
        return None
    if positive and x <= 0:
        R.err(path, f"必须大于 0，收到 {x}")
        return None
    if lo is not None and x < lo:
        R.err(path, f"应 ≥ {lo}，收到 {x}")
        return None
    if hi is not None and x > hi:
        R.err(path, f"应 ≤ {hi}，收到 {x}")
        return None
    return x


def _list(R, path, x, min_len=1, max_len=None, what="列表"):
    if not isinstance(x, list):
        R.err(path, f"应为{what}（JSON 数组），收到 {_show(x)}")
        return None
    if len(x) < min_len:
        R.err(path, f"{what}至少需要 {min_len} 项，收到 {len(x)} 项")
        return None
    if max_len is not None and len(x) > max_len:
        R.err(path, f"{what}最多 {max_len} 项（浏览器内运行的规模上限），收到 {len(x)} 项")
        return None
    return x


def _need(R, p, key, alias=()):
    for k in (key,) + tuple(alias):
        if k in p:
            return p[k]
    R.err(key, f"缺少必填字段 '{key}'")
    return None


def _num_vec(R, path, x, length=None, **kw):
    """数值向量；kw 透传 _num。返回新列表或 None。"""
    xs = _list(R, path, x, what="数组")
    if xs is None:
        return None
    if length is not None and len(xs) != length:
        R.err(path, f"长度应为 {length}，收到 {len(xs)}")
        return None
    out = []
    ok = True
    for i, v in enumerate(xs):
        c = _num(R, f"{path}[{i}]", v, **kw)
        ok &= c is not None
        out.append(c)
    return out if ok else None


def _matrix(R, path, x, rows=None, cols=None, **kw):
    """矩形数值矩阵。返回新的二维列表或 None。"""
    xs = _list(R, path, x, what="矩阵")
    if xs is None:
        return None
    if rows is not None and len(xs) != rows:
        R.err(path, f"行数应为 {rows}，收到 {len(xs)}")
        return None
    out = []
    width = cols
    ok = True
    for i, row in enumerate(xs):
        r = _list(R, f"{path}[{i}]", row, what="行")
        if r is None:
            ok = False
            continue
        if width is None:
            width = len(r)
        elif len(r) != width:
            R.err(f"{path}[{i}]", f"每行长度必须一致：第 0 行 {width} 列，本行 {len(r)} 列")
            ok = False
            continue
        vec = []
        for j, v in enumerate(r):
            c = _num(R, f"{path}[{i}][{j}]", v, **kw)
            ok &= c is not None
            vec.append(c)
        out.append(vec)
    return out if ok else None


def _circle_layout(n):
    return [[round(50 + 42 * math.cos(2 * math.pi * i / max(n, 1)), 1),
             round(50 + 42 * math.sin(2 * math.pi * i / max(n, 1)), 1)] for i in range(n)]


def _pos_or_layout(R, p, key, n):
    """可选的绘图坐标：给了就校验，没给就环形布局（只影响画面，不影响求解）。"""
    if key in p and p[key] is not None:
        return _matrix(R, key, p[key], rows=n, cols=2)
    return _circle_layout(n)


# ------------------------------------------------------------------ 各域校验（核心域）

TSP_METRICS = ("EUC_2D", "CEIL_2D", "ATT", "GEO", "MAN_2D", "MAX_2D")
TSP_MIN = 4  # 3 城市只有一条回路（正反向同长），无需求解，部分算子也要求至少 4 个不同位置
_ATSP_MSG = ("距离不对称（A→B 与 B→A 不同）：这是非对称 TSP（ATSP）。TSP 演示页的算法用了 2-opt / OX 等默认距离对称的算子，"
             "用在非对称数据上会得出错误结果，所以这里拒绝导入——请到「问题 ▸ 非对称旅行商 ATSP」页导入"
             "（那里的算法每次重新计算整条回路的代价，不依赖对称性；也能直接读 TSPLIB 的 .atsp 文件）")


def _tsp_matrix(R, path, mat, n_max):
    """显式距离矩阵：方阵、非负、零对角、对称。返回规整后的 float 矩阵或 None。"""
    m = _matrix(R, path, mat, lo=0)
    if m is None:
        return None
    n = len(m)
    if n != len(m[0]):
        R.err(path, f"距离矩阵必须是方阵，收到 {n} 行 × {len(m[0])} 列")
        return None
    if n < TSP_MIN or n > n_max:
        R.err(path, f"城市数应在 {TSP_MIN} ~ {n_max} 之间（浏览器内运行的规模上限），收到 {n}")
        return None
    if any(m[i][i] != 0 for i in range(n)):
        i = next(i for i in range(n) if m[i][i] != 0)
        R.err(f"{path}[{i}][{i}]", f"对角线（到自己的距离）应为 0，收到 {m[i][i]}")
        return None
    for i in range(n):
        for j in range(i + 1, n):
            if abs(m[i][j] - m[j][i]) > 1e-9 * max(1.0, abs(m[i][j])):
                R.err(f"{path}[{i}][{j}]", f"{_ATSP_MSG}（第 {i} 行第 {j} 列是 {m[i][j]}，对称位置是 {m[j][i]}）")
                return None
    return m


def _v_tsp(p, R):
    metric = None
    mat = None
    pts = None
    if isinstance(p, dict):
        metric = p.get("metric")
        mat = p.get("matrix", p.get("dist"))
        pts = p.get("cities", p.get("pts"))
        if pts is None and mat is None:
            R.err("cities", "缺少 'cities'（[[x, y], …] 坐标）或 'matrix'（n×n 距离矩阵）")
            return None
    else:
        pts = p
        if isinstance(p, list) and len(p) >= TSP_MIN and all(isinstance(r, list) for r in p) \
                and all(len(r) == len(p) for r in p):
            pts, mat = None, p  # 方阵：按距离矩阵读取（n×2 的坐标不可能是方阵，除非 n=2，而 n≥3）
            R.warn("", f"按 {len(p)}×{len(p)} 距离矩阵读取；如果你想给的是坐标，每行应只有 [x, y] 两个数")
    if metric is not None and metric not in TSP_METRICS and metric not in ("euc", "matrix"):
        R.err("metric", f"不支持的距离类型 {_show(metric)}。可选：euc（默认，浮点欧氏）、{', '.join(TSP_METRICS)}")
        return None
    if mat is not None:
        if metric not in (None, "euc", "matrix"):
            R.err("metric", "给了距离矩阵就不需要 metric（距离以矩阵为准）")
            return None
        m = _tsp_matrix(R, "matrix", mat, LIMITS["tsp"])
        if m is None:
            return None
        n = len(m)
        if pts is None:
            R.warn("cities", "没有给坐标：路线图按圆环布局，只用来示意；路线长度仍以你的距离矩阵为准")
            pos = _circle_layout(n)
        else:
            pos = _matrix(R, "cities", _list(R, "cities", pts, min_len=n, max_len=n, what="绘图坐标列表"), cols=2)
            if pos is None:
                return None
        return {"cities": pos, "metric": "matrix", "matrix": m}
    pts = _list(R, "cities", pts, min_len=TSP_MIN, max_len=LIMITS["tsp"], what="城市坐标列表")
    if pts is None:
        return None
    m = _matrix(R, "cities", pts, cols=2)
    if m is None:
        return None
    if len({tuple(c) for c in m}) < len(m):
        R.warn("cities", "存在重复坐标的城市（距离为 0），可以求解但路线图上会重叠")
    if metric in TSP_METRICS:
        return {"cities": m, "metric": metric}
    return {"cities": m}


# ------------------------------------------------------------------ TSPLIB 解析

_TSPLIB_KEY = re.compile(r"^\s*([A-Z_]+)\s*:?\s*(.*)$")


def _looks_like_tsplib(txt):
    return bool(re.search(r"^\s*(NODE_COORD_SECTION|EDGE_WEIGHT_SECTION|DIMENSION\s*:|EDGE_WEIGHT_TYPE\s*:)", txt, re.M))


def _tsplib_matrix_from_list(R, fmt, vals, n):
    """把 EDGE_WEIGHT_SECTION 的一维数列按格式还原成 n×n 对称矩阵（列优先格式与行优先的镜像等价）。"""
    fmt = {"UPPER_COL": "LOWER_ROW", "LOWER_COL": "UPPER_ROW", "UPPER_DIAG_COL": "LOWER_DIAG_ROW",
           "LOWER_DIAG_COL": "UPPER_DIAG_ROW"}.get(fmt, fmt)
    need = {"FULL_MATRIX": n * n, "UPPER_ROW": n * (n - 1) // 2, "LOWER_ROW": n * (n - 1) // 2,
            "UPPER_DIAG_ROW": n * (n + 1) // 2, "LOWER_DIAG_ROW": n * (n + 1) // 2}.get(fmt)
    if need is None:
        R.err("EDGE_WEIGHT_FORMAT", f"不支持的 EDGE_WEIGHT_FORMAT {_show(fmt)}")
        return None
    if len(vals) != need:
        R.err("EDGE_WEIGHT_SECTION", f"{fmt} 在 DIMENSION={n} 时应有 {need} 个数，收到 {len(vals)} 个")
        return None
    M = [[0] * n for _ in range(n)]
    it = iter(vals)
    if fmt == "FULL_MATRIX":
        for i in range(n):
            for j in range(n):
                M[i][j] = next(it)
        return M
    for i in range(n):
        if fmt.startswith("UPPER"):
            cols = range(i if fmt.endswith("DIAG_ROW") else i + 1, n)
        else:
            cols = range(0, i + 1 if fmt.endswith("DIAG_ROW") else i)
        for j in cols:
            v = next(it)
            M[i][j] = v
            M[j][i] = v
    return M


def _parse_tsplib(txt, R, atsp=False):
    """TSPLIB95 的 TSP 子集 → 校验器认识的 dict。不是 TSP（ATSP / CVRP / HCP …）一律明确拒绝。
    atsp=True：改读 TYPE: ATSP 文件（给 entryseq 的 atsp 变体用，只收显式 FULL_MATRIX），其余类型拒绝。"""
    hdr, sections, cur = {}, {}, None
    for ln, line in enumerate(txt.splitlines(), 1):
        s = line.strip()
        if not s:
            continue
        if s == "EOF":
            break
        m = _TSPLIB_KEY.match(s)
        if m and m.group(1).endswith("_SECTION") and m.group(2) == "":
            cur = m.group(1)
            sections[cur] = []
            continue
        if cur and re.match(r"^[-+\d.eE\s]+$", s):
            sections[cur].append((ln, s))
            continue
        if m and ":" in s:
            cur = None
            k, v = s.split(":", 1)
            hdr[k.strip()] = v.strip()
            continue
        R.err(f"第 {ln} 行", f"无法识别的 TSPLIB 内容：{_show(s)}")
        return None
    typ = hdr.get("TYPE", "TSP").upper()
    if atsp:
        return _parse_atsplib(hdr, sections, typ, R)
    if typ == "ATSP":
        R.err("TYPE", _ATSP_MSG)
        return None
    if typ != "TSP":
        R.err("TYPE", f"这是 TSPLIB 的 {typ} 文件；这里只支持 TYPE: TSP（对称旅行商）")
        return None
    try:
        n = int(hdr["DIMENSION"])
    except (KeyError, ValueError):
        R.err("DIMENSION", "缺少或无法读取 DIMENSION（城市数）")
        return None
    ewt = hdr.get("EDGE_WEIGHT_TYPE", "").upper()

    def numbers(name):
        out = []
        for ln, s in sections.get(name, []):
            for t in s.split():
                try:
                    out.append(float(t))
                except ValueError:
                    R.err(f"第 {ln} 行", f"应为数字，收到 {_show(t)}")
                    return None
        return out

    if ewt == "EXPLICIT":
        vals = numbers("EDGE_WEIGHT_SECTION")
        if vals is None:
            return None
        if "EDGE_WEIGHT_SECTION" not in sections:
            R.err("EDGE_WEIGHT_SECTION", "EDGE_WEIGHT_TYPE 是 EXPLICIT，但文件里没有 EDGE_WEIGHT_SECTION")
            return None
        mat = _tsplib_matrix_from_list(R, hdr.get("EDGE_WEIGHT_FORMAT", "").upper(), vals, n)
        if mat is None:
            return None
        out = {"matrix": mat}
        disp = sections.get("DISPLAY_DATA_SECTION")
        if disp and hdr.get("DISPLAY_DATA_TYPE", "").upper() == "TWOD_DISPLAY":
            pos = _tsplib_coords(R, "DISPLAY_DATA_SECTION", disp, n)
            if pos is not None:
                out["cities"] = pos
        return out
    if ewt not in TSP_METRICS:
        R.err("EDGE_WEIGHT_TYPE", f"不支持 EDGE_WEIGHT_TYPE {_show(ewt) if ewt else '（缺失）'}。支持："
                                   f"{', '.join(TSP_METRICS)}、EXPLICIT（距离矩阵）")
        return None
    if "NODE_COORD_SECTION" not in sections:
        R.err("NODE_COORD_SECTION", "缺少 NODE_COORD_SECTION（城市坐标）")
        return None
    pos = _tsplib_coords(R, "NODE_COORD_SECTION", sections["NODE_COORD_SECTION"], n)
    return None if pos is None else {"cities": pos, "metric": ewt}


def _parse_atsplib(hdr, sections, typ, R):
    """TSPLIB 的 .atsp（非对称 TSP）→ entryseq/atsp 实例。官方 .atsp 文件的对角线常写成 9999 之类的占位值，读入时统一置 0。"""
    if typ != "ATSP":
        R.err("TYPE", f"这是 TYPE: {typ} 的文件。这里读的是非对称 TSP（TYPE: ATSP）；对称 TSP 请到「TSP 演示」页导入")
        return None
    try:
        n = int(hdr["DIMENSION"])
    except (KeyError, ValueError):
        R.err("DIMENSION", "缺少或无法读取 DIMENSION（城市数）")
        return None
    if hdr.get("EDGE_WEIGHT_TYPE", "").upper() != "EXPLICIT" or hdr.get("EDGE_WEIGHT_FORMAT", "").upper() != "FULL_MATRIX":
        R.err("EDGE_WEIGHT_FORMAT", "ATSP 文件需要 EDGE_WEIGHT_TYPE: EXPLICIT 且 EDGE_WEIGHT_FORMAT: FULL_MATRIX（TSPLIB 的 .atsp 都是这种）")
        return None
    vals = []
    for ln, s in sections.get("EDGE_WEIGHT_SECTION", []):
        for t in s.split():
            try:
                vals.append(float(t))
            except ValueError:
                R.err(f"第 {ln} 行", f"应为数字，收到 {_show(t)}")
                return None
    if len(vals) != n * n:
        R.err("EDGE_WEIGHT_SECTION", f"FULL_MATRIX 在 DIMENSION={n} 时应有 {n * n} 个数，收到 {len(vals)} 个")
        return None
    mat = [[(int(v) if float(v).is_integer() else v) for v in vals[i * n:(i + 1) * n]] for i in range(n)]
    if any(mat[i][i] != 0 for i in range(n)):
        R.warn("EDGE_WEIGHT_SECTION", "对角线（到自己的代价）不是 0——TSPLIB 的 .atsp 常用 9999 之类的占位值，已置为 0（不影响求解）")
        for i in range(n):
            mat[i][i] = 0
    return {"variant": "atsp", "d": mat, "pts": _circle_layout(n), "n": n}


def _tsplib_coords(R, name, rows, n):
    pos = []
    for ln, s in rows:
        t = s.split()
        if len(t) != 3:
            R.err(f"第 {ln} 行", f"{name} 每行应为「编号 x y」三个数，收到 {len(t)} 个（只支持二维坐标）")
            return None
        try:
            pos.append([float(t[1]), float(t[2])])
        except ValueError:
            R.err(f"第 {ln} 行", f"坐标应为数字，收到 {_show(s)}")
            return None
    if len(pos) != n:
        R.err(name, f"DIMENSION={n}，但这一段有 {len(pos)} 行")
        return None
    return pos


def _csv_tsp(table, meta, R):
    """CSV 的 TSP 读法：每行 x,y；或 id,x,y（第一列是 1..n / 0..n-1 的编号）；或 n×n 距离矩阵。"""
    widths = {len(r) for r in table}
    if len(widths) != 1:
        R.err("", f"每行的列数必须一致，收到 {sorted(widths)}")
        return None
    w, n = widths.pop(), len(table)
    if w == n and n >= TSP_MIN and all(table[i][i] == 0 for i in range(n)):  # 零对角的方阵才可能是距离矩阵
        R.warn("", f"{n}×{n} 的方阵，按距离矩阵读取；如果想给坐标，每行应只有 x,y（或 id,x,y）")
        return {"matrix": table}
    if w == 2:
        return {"cities": table}
    if w == 3:
        ids = [r[0] for r in table]
        if ids in (list(range(1, n + 1)), list(range(n))) or ids in ([float(i) for i in range(1, n + 1)],
                                                                       [float(i) for i in range(n)]):
            R.warn("", "第一列是 1..n 的编号，已忽略，按 id,x,y 读取")
            return {"cities": [r[1:] for r in table]}
        R.err("", "每行 3 个数：看起来像 id,x,y，但第一列不是 1..n（或 0..n-1）的连续编号。"
                  "如果是三维坐标，本站只支持二维；如果第一列是别的含义，请删掉它")
        return None
    R.err("", f"每行 {w} 个数，无法判断含义：坐标请用 x,y（或 id,x,y）；距离矩阵必须是 n×n 方阵（当前 {n} 行 {w} 列）")
    return None


def _v_knapsack(p, R):
    items = _list(R, "items", _need(R, p, "items"), max_len=LIMITS["knapsack"], what="物品列表")
    cap = _num(R, "cap", _need(R, p, "cap", ("capacity",)), positive=True, what="容量")
    if items is None or cap is None:
        return None
    out, ok = [], True
    for i, it in enumerate(items):
        row = _list(R, f"items[{i}]", it, min_len=2, what="[重量, 价值]")
        if row is None:
            ok = False
            continue
        if len(row) != 2:
            R.err(f"items[{i}]", f"每个物品应为 [重量, 价值] 两个数，收到 {len(row)} 个")
            ok = False
            continue
        w = _num(R, f"items[{i}][0]", row[0], positive=True, what="重量")
        v = _num(R, f"items[{i}][1]", row[1], lo=0, what="价值")
        ok &= w is not None and v is not None
        out.append([w, v])
    if not ok:
        return None
    big = [i for i, (w, _) in enumerate(out) if w > cap]
    if big:
        R.warn("items", f"{len(big)} 个物品比背包容量还重（如第 {big[0]} 项），永远不会被选中")
    if sum(w for w, _ in out) <= cap:
        R.warn("cap", "全部物品总重量不超过容量，全选就是最优解，问题是平凡的")
    _warn_n(R, p, len(out))
    return {"n": len(out), "cap": cap, "items": out}


def _warn_n(R, p, n, key="n"):
    if key in p and p[key] != n:
        R.warn(key, f"已忽略 {key}={_show(p[key])}，以数据实际长度 {n} 为准")


def _v_multiobj(p, R):
    items = _list(R, "items", _need(R, p, "items"), max_len=LIMITS["multiobj"], what="物品列表")
    cap = _num(R, "cap", _need(R, p, "cap", ("capacity",)), positive=True, what="容量")
    if items is None or cap is None:
        return None
    width = len(items[0]) if isinstance(items[0], list) else 0
    if width not in (3, 4):
        R.err("items[0]", "每个物品应为 [重量, 目标1, 目标2] 或 [重量, 目标1, 目标2, 目标3]")
        return None
    m = _matrix(R, "items", items, cols=width, lo=0)
    if m is None:
        return None
    if any(r[0] <= 0 for r in m):
        R.err("items", "重量（每行第 0 列）必须大于 0")
        return None
    variant = "moco" if width == 3 else "maop"
    if p.get("variant") not in (None, variant):
        R.err("variant", f"物品每行 {width} 列对应变体 '{variant}'，但 variant 写的是 {_show(p.get('variant'))}")
        return None
    _warn_n(R, p, len(m))
    return {"variant": variant, "n": len(m), "cap": cap, "items": m}


def _v_binpack(p, R):
    items = _num_vec(R, "items", _need(R, p, "items", ("sizes",)), positive=True, what="尺寸")
    cap = _num(R, "cap", _need(R, p, "cap", ("capacity", "bin_cap")), positive=True, what="箱容量")
    if items is None or cap is None:
        return None
    if len(items) > LIMITS["binpack"]:
        R.err("items", f"最多 {LIMITS['binpack']} 件（浏览器内运行的规模上限），收到 {len(items)} 件")
        return None
    big = [i for i, w in enumerate(items) if w > cap]
    if big:
        R.err(f"items[{big[0]}]", f"物品尺寸 {items[big[0]]} 超过箱容量 {cap}，无论如何装不下（共 {len(big)} 件）")
        return None
    _warn_n(R, p, len(items))
    return {"n": len(items), "cap": cap, "items": items}


def _edges(R, p, n_given):
    """图的边表校验与规整：返回 (n, edges, pos) 或 None。顶点编号从 0 开始。"""
    raw = _list(R, "edges", _need(R, p, "edges"), min_len=0, max_len=LIMITS["graph_edges"], what="边列表")
    if raw is None:
        return None
    pairs, ok = [], True
    for i, e in enumerate(raw):
        if not isinstance(e, list) or len(e) < 2:
            R.err(f"edges[{i}]", f"每条边应为 [顶点u, 顶点v]，收到 {_show(e)}")
            ok = False
            continue
        u = _int(R, f"edges[{i}][0]", e[0], lo=0, what="顶点编号（从 0 开始的整数）")
        v = _int(R, f"edges[{i}][1]", e[1], lo=0, what="顶点编号（从 0 开始的整数）")
        ok &= u is not None and v is not None
        pairs.append((u, v))
    if not ok:
        return None
    n = n_given
    top = max((max(u, v) for u, v in pairs), default=-1)
    if n is None:
        if top < 0:
            R.err("n", "没有边也没有给 n，无法确定顶点数")
            return None
        n = top + 1
        R.warn("n", f"未提供 n，按最大顶点编号推断为 {n}（若末尾有孤立点请显式提供 n）")
    else:
        n = _int(R, "n", n, lo=2, what="顶点数")
        if n is None:
            return None
        if top >= n:
            hint = "（看起来是从 1 开始编号；本格式顶点编号为 0..n-1）" if top == n and min(min(e) for e in pairs) >= 1 else ""
            R.err("edges", f"顶点编号 {top} 超出范围 0..{n - 1}{hint}")
            return None
    if n > LIMITS["graph_nodes"]:
        R.err("n", f"顶点数最多 {LIMITS['graph_nodes']}（浏览器内运行的规模上限），收到 {n}")
        return None
    seen, edges, loops = set(), [], 0
    for u, v in pairs:
        if u == v:
            loops += 1
            continue
        k = (min(u, v), max(u, v))
        if k not in seen:
            seen.add(k)
            edges.append([k[0], k[1]])
    if loops:
        R.warn("edges", f"忽略了 {loops} 条自环边")
    if len(edges) < len(pairs) - loops:
        R.warn("edges", f"合并了 {len(pairs) - loops - len(edges)} 条重复边")
    return n, edges


def _v_graphcolor(p, R):
    got = _edges(R, p, p.get("n"))
    if got is None:
        return None
    n, edges = got
    pos = _pos_or_layout(R, p, "pos", n)
    if pos is None:
        return None
    return {"n": n, "edges": edges, "pos": pos}


def _v_setcover(p, R):
    sets = _list(R, "sets", _need(R, p, "sets"), max_len=1000, what="集合列表")
    costs = _need(R, p, "costs", ("cost",))
    if sets is None or costs is None:
        return None
    m = _matrix(R, "sets", sets)
    if m is None:
        return None
    if len(m) * len(m[0]) > LIMITS["setcover_cells"]:
        R.err("sets", f"矩阵过大（{len(m)}×{len(m[0])}），上限 {LIMITS['setcover_cells']} 格")
        return None
    for i, row in enumerate(m):
        for j, v in enumerate(row):
            if v not in (0, 1):
                R.err(f"sets[{i}][{j}]", f"覆盖矩阵只能是 0 或 1，收到 {v}")
                return None
    c = _num_vec(R, "costs", costs, length=len(m), positive=True, what="成本")
    if c is None:
        return None
    n_el = len(m[0])
    unc = [e for e in range(n_el) if not any(m[i][e] for i in range(len(m)))]
    if unc:
        R.err("sets", f"元素 {unc[:5]}{'…' if len(unc) > 5 else ''} 没有被任何集合覆盖，问题无解（共 {len(unc)} 个）")
        return None
    return {"n_el": n_el, "m": len(m), "sets": [[int(v) for v in r] for r in m], "costs": c}


def _v_sat(p, R):
    cl = _list(R, "clauses", _need(R, p, "clauses"), max_len=LIMITS["sat_clauses"], what="子句列表")
    if cl is None:
        return None
    out, ok, top = [], True, 0
    for i, c in enumerate(cl):
        row = _list(R, f"clauses[{i}]", c, what="子句（非零整数文字列表）")
        if row is None:
            ok = False
            continue
        lits = []
        for j, lit in enumerate(row):
            v = _int(R, f"clauses[{i}][{j}]", lit, what="非零整数（正=变量，负=取反，变量编号从 1 开始）")
            if v is None:
                ok = False
            elif v == 0:
                R.err(f"clauses[{i}][{j}]", "文字不能为 0（变量编号从 1 开始；0 只在 DIMACS 文件里作行尾标记）")
                ok = False
            else:
                lits.append(v)
                top = max(top, abs(v))
        if ok and len(set(lits)) < len(lits):
            lits = list(dict.fromkeys(lits))
            R.warn(f"clauses[{i}]", "子句内有重复文字，已去重")
        if ok and any(-x in lits for x in lits):
            R.warn(f"clauses[{i}]", "子句同时含 x 与 ¬x，恒为真（永远满足）")
        out.append(lits)
    if not ok:
        return None
    n = p.get("n_vars", p.get("n"))
    if n is None:
        n = top
        R.warn("n_vars", f"未提供 n_vars，按最大变量编号推断为 {n}")
    n = _int(R, "n_vars", n, lo=1, hi=LIMITS["sat_vars"], what="变量数")
    if n is None:
        return None
    if top > n:
        R.err("clauses", f"子句里出现变量 {top}，超过 n_vars={n}")
        return None
    return {"n_vars": n, "clauses": out}


def _v_qubo(p, R):
    Q = _matrix(R, "Q", _need(R, p, "Q"))
    if Q is None:
        return None
    n = len(Q)
    if len(Q[0]) != n:
        R.err("Q", f"QUBO 矩阵必须是方阵，收到 {n}×{len(Q[0])}")
        return None
    if n > LIMITS["qubo"]:
        R.err("Q", f"最多 {LIMITS['qubo']} 个变量（浏览器内运行的规模上限），收到 {n}")
        return None
    return {"n": n, "Q": Q}


def _v_gap(p, R):
    c = _matrix(R, "c", _need(R, p, "c", ("cost",)))
    if c is None:
        return None
    n_a, n_j = len(c), len(c[0])
    r = _matrix(R, "r", _need(R, p, "r", ("resource",)), rows=n_a, cols=n_j, lo=0)
    cap = _num_vec(R, "cap", _need(R, p, "cap", ("capacity",)), length=n_a, lo=0, what="容量")
    if r is None or cap is None:
        return None
    if n_a > LIMITS["gap_agents"] or n_j > LIMITS["gap_jobs"]:
        R.err("c", f"最多 {LIMITS['gap_agents']} 个代理 × {LIMITS['gap_jobs']} 个任务，收到 {n_a}×{n_j}")
        return None
    for j in range(n_j):
        if all(r[a][j] > cap[a] for a in range(n_a)):
            R.err(f"r[*][{j}]", f"任务 {j} 的资源需求超过所有代理的容量，无法指派，问题无解")
            return None
    return {"n_a": n_a, "n_j": n_j, "c": c, "r": r, "cap": cap}


def _v_uflp(p, R):
    f = _num_vec(R, "f_cost", _need(R, p, "f_cost", ("fixed_cost",)), lo=0, what="开设成本")
    if f is None:
        return None
    cc = _matrix(R, "c_cost", _need(R, p, "c_cost", ("assign_cost",)), rows=len(f), lo=0)
    if cc is None:
        return None
    n_f, n_c = len(f), len(cc[0])
    if n_f > LIMITS["uflp_f"] or n_c > LIMITS["uflp_c"]:
        R.err("c_cost", f"最多 {LIMITS['uflp_f']} 个设施 × {LIMITS['uflp_c']} 个客户，收到 {n_f}×{n_c}")
        return None
    pf = _pos_or_layout(R, p, "pos_f", n_f)
    pc = _pos_or_layout(R, p, "pos_c", n_c)
    if pf is None or pc is None:
        return None
    return {"n_f": n_f, "n_c": n_c, "f_cost": f, "c_cost": cc, "pos_f": pf, "pos_c": pc}


def _v_continuous(p, R):
    D = _engine()
    fn = _need(R, p, "fn", ("function",))
    if fn is None:
        return None
    if fn not in D.FUNCS:
        R.err("fn", f"未知函数 {_show(fn)}。可选：{', '.join(D.FUNCS)}（自定义函数见「自带问题」）")
        return None
    dim = _int(R, "dim", p.get("dim", 2), lo=1, hi=LIMITS["continuous_dim"], what="维度")
    if dim is None:
        return None
    if "lo" in p or "hi" in p:
        R.warn("lo/hi", "搜索范围由所选函数决定，已忽略 lo/hi")
    return D.cn_make(fn=fn, dim=dim)


# ------------------------------------------------------------------ 着色家族（含边/全着色的线图推导）

def _line_adj(edges):
    m = len(edges)
    inc = {}
    for k, (u, v) in enumerate(edges):
        inc.setdefault(u, []).append(k)
        inc.setdefault(v, []).append(k)
    adj = [set() for _ in range(m)]
    for ks in inc.values():
        for a in ks:
            for b in ks:
                if a != b:
                    adj[a].add(b)
    return [sorted(s) for s in adj]


def _v_gcvar(p, R, variant):
    got = _edges(R, p, p.get("n"))
    if got is None:
        return None
    n, edges = got
    pos = _pos_or_layout(R, p, "pos", n)
    if pos is None:
        return None
    deg = [0] * n
    for u, v in edges:
        deg[u] += 1
        deg[v] += 1
    out = {"variant": variant, "n": n, "edges": edges, "pos": pos,
           "p": round(2 * len(edges) / max(n * (n - 1), 1), 3)}
    if variant == "listcolor":
        lists = _list(R, "lists", _need(R, p, "lists"), what="每个顶点的可选颜色表")
        if lists is None:
            return None
        if len(lists) != n:
            R.err("lists", f"应为每个顶点一张颜色表（共 {n} 张），收到 {len(lists)} 张")
            return None
        L, K = [], 0
        for i, row in enumerate(lists):
            r = _list(R, f"lists[{i}]", row, what="颜色表")
            if r is None:
                return None
            cs = [_int(R, f"lists[{i}][{j}]", c, lo=0, what="颜色编号（从 0 开始的整数）") for j, c in enumerate(r)]
            if None in cs:
                return None
            L.append(sorted(set(cs)))
            K = max(K, max(cs) + 1)
        out["lists"], out["K"] = L, K
    elif variant == "precolor":
        pc = _list(R, "precol", _need(R, p, "precol"), what="预着色表")
        if pc is None:
            return None
        if len(pc) != n:
            R.err("precol", f"应为每个顶点一项（共 {n} 项，-1 表示未预着色），收到 {len(pc)} 项")
            return None
        cols = [_int(R, f"precol[{i}]", c, lo=-1, what="颜色编号（-1=未预着色）") for i, c in enumerate(pc)]
        if None in cols:
            return None
        for u, v in edges:
            if cols[u] >= 0 and cols[u] == cols[v]:
                R.err("precol", f"相邻顶点 {u} 与 {v} 被预着成同一颜色 {cols[u]}，无合法着色")
                return None
        out["precol"] = cols
        out["K"] = max(max(cols) + 1, max(deg, default=0) + 1)
    elif variant == "edgecolor":
        out["ladj"] = _line_adj(edges)
        out["m"] = len(edges)
    elif variant == "totalcolor":
        m = len(edges)
        tad = [set() for _ in range(n + m)]
        for u, v in edges:
            tad[u].add(v)
            tad[v].add(u)
        for a, nb in enumerate(_line_adj(edges)):
            tad[n + a].update(n + b for b in nb)
        for a, (u, v) in enumerate(edges):
            for x in (u, v):
                tad[x].add(n + a)
                tad[n + a].add(x)
        out.update({"tadj": [sorted(s) for s in tad], "nV": n, "m": m, "N": n + m})
    elif variant != "mis":
        R.err("variant", f"gcvar 的变体应为 listcolor/precolor/edgecolor/totalcolor/mis，收到 {_show(variant)}")
        return None
    return out


# ------------------------------------------------------------------ 长尾域：按示例实例自动推结构

def _ref_check(R, path, ref, val, key=None):
    """按示例 ref 的结构检查 val；返回规整后的值或 None。"""
    if isinstance(ref, bool):
        R.err(path, "内部：不支持布尔字段")
        return None
    if isinstance(ref, (int, float)):
        if not _isnum(val):
            R.err(path, f"应为数字，收到 {_show(val)}")
            return None
        if isinstance(ref, int) and isinstance(val, float):
            if not val.is_integer():
                R.err(path, f"应为整数，收到 {val}")
                return None
            return int(val)
        return val
    if isinstance(ref, str):
        if not isinstance(val, str):
            R.err(path, f"应为文本，收到 {_show(val)}")
            return None
        return val
    if isinstance(ref, list):
        if not isinstance(val, list):
            R.err(path, f"应为列表（JSON 数组），收到 {_show(val)}")
            return None
        if not ref:
            return val
        if len(val) == 0:
            if key in _RAGGED_KEYS:  # 不规则字段允许空行（如无前驱的工序）
                return val
            R.err(path, "不能为空列表")
            return None
        # 行结构三类：记录型字段（坐标 [x,y]、边 [u,v,w]）行长必须等于示例；
        # 不规则字段（前驱列表等）各行可不等长；其余视为矩阵，要求同一矩阵内等宽
        first = ref[0]
        fixed = len(first) if isinstance(first, list) and key in _RECORD_KEYS else None
        width = None
        out = []
        ok = True
        for i, x in enumerate(val):
            if isinstance(first, list):
                if not isinstance(x, list):
                    R.err(f"{path}[{i}]", f"应为列表，收到 {_show(x)}")
                    ok = False
                    continue
                if fixed is not None and len(x) != fixed:
                    R.err(f"{path}[{i}]", f"每项应有 {fixed} 个值，收到 {len(x)} 个")
                    ok = False
                    continue
                if fixed is None and key not in _RAGGED_KEYS:
                    width = len(x) if width is None else width
                    if len(x) != width:
                        R.err(f"{path}[{i}]", f"每行长度必须一致：前面是 {width}，本行 {len(x)}")
                        ok = False
                        continue
            c = _ref_check(R, f"{path}[{i}]", first, x, key)
            ok &= c is not None
            out.append(c)
        return out if ok else None
    return val


_RECORD_KEYS = {"pts", "edges", "items", "bin_types", "pos"}
_RAGGED_KEYS = {"preds", "chains", "lists", "sets", "adj", "students", "jobs"}
_OPTIONAL_KEYS = {"name", "opt"}  # 只用来显示（实例名、文献最优值）：有就收，没有不要求


def _derive_n(ref, p):
    """示例里 n 恰好等于某个列表长度（或少 1）时，从用户数据推 n。返回 n 或 None。"""
    n_ref = ref.get("n")
    if not isinstance(n_ref, int):
        return None
    for k, v in ref.items():
        if k in ("n", "pos") or not isinstance(v, list):
            continue
        for off in (0, -1):
            if len(v) + off == n_ref and isinstance(p.get(k), list):
                return len(p[k]) + off
    return None


def _v_mocont(p, R, variant):
    """连续多目标基准：变体 + 决策变量个数。函数本身是固定的，没有别的数据。"""
    D = _engine()
    v = variant or p.get("variant")
    if v not in D.MOC_VARIANTS:
        R.err("variant", f"未知变体 {_show(v)}。可选：{', '.join(D.MOC_VARIANTS)}")
        return None
    n_min = D.MOC_SPEC[v][3]
    n = _int(R, "n", p.get("n", D.MOC_SPEC[v][2]), lo=n_min, hi=100, what="决策变量个数")
    if n is None:
        return None
    if v in D.MOC_NFIX and n != D.MOC_NFIX[v]:
        R.err("n", f"{v} 的决策变量个数固定为 {D.MOC_NFIX[v]}（真前沿的公式依赖它），收到 {n}")
        return None
    return D.mc_make(v, n)


def _v_custom(p, R, variant):
    """自带问题：编码（variant）+ 目标函数（表达式）+ 数据表。检查与试跑都在 py/userproblem.py。"""
    D = _engine()
    q = dict(p)
    v = q.get("variant", q.get("encoding"))
    if variant and v and variant != v:
        R.err("variant", f"数据里写的编码是 {v!r}，但这里要求 {variant!r}")
        return None
    if variant:
        q["variant"] = variant
    out, errs, warns, _info = D.up_check(q)
    for e in errs:
        R.err(e["path"], e["msg"])
    for w in warns:
        R.warn(w["path"], w["msg"])
    return out


def _v_generic(domain, p, R, variant):
    D = _engine()
    opts = {"variant": variant} if variant else {}
    try:
        ref = json.loads(D.domain_preset(domain, 7, opts))
    except Exception:
        ref = None
    if not isinstance(ref, dict):
        R.err("variant", f"未知变体 {_show(variant)}")
        return None
    out = {}
    for k, rv in ref.items():
        if k == "variant":
            out[k] = ref[k]
            continue
        if k in _OPTIONAL_KEYS:
            if k in p:
                out[k] = p[k]
            continue
        if k not in p:
            if k == "pos":
                continue
            if k == "n" and _derive_n(ref, p) is not None:
                continue
            R.err(k, f"缺少必填字段 '{k}'")
            continue
        c = _ref_check(R, k, rv, p[k], k)
        if c is not None:
            out[k] = c
    if R.errors:
        return None
    dn = _derive_n(ref, p)
    if dn is not None:
        if "n" in p and p["n"] != dn:
            R.err("n", f"n={p['n']} 与数据长度不符（数据推出 n={dn}）")
            return None
        out["n"] = dn
    n = out.get("n")
    cap_n = LIMITS["entryseq"] if domain == "entryseq" else LIMITS.get(domain, 1000)
    if isinstance(n, int) and not (1 <= n <= cap_n):
        R.err("n", f"n 应在 1..{cap_n}（浏览器内运行的规模上限），收到 {n}")
        return None
    return out


def _es_fill(variant, p):
    """调度 / 路径 / 选址类变体里由数据推得出的字段（规模、机器数、下界、名字……）：上传时只需要给核心数据，其余这里补上。
    数据形状不对时原样返回，交给通用检查去报错。"""
    q = dict(p)

    def mat(x):
        return isinstance(x, list) and len(x) > 0 and all(isinstance(r, list) and len(r) > 0 for r in x)
    try:
        if variant == "fss" and mat(q.get("p")):
            q.setdefault("m_mach", len(q["p"]))
            q.setdefault("n", len(q["p"][0]))
        elif variant == "oss" and mat(q.get("t")):
            nj, m = len(q["t"]), len(q["t"][0])
            q.setdefault("n_jobs", nj)
            q.setdefault("m_mach", m)
            q.setdefault("n", nj * m)
            if all(len(r) == m for r in q["t"]) and all(_isnum(x) for r in q["t"] for x in r):
                q.setdefault("lb", max(max(sum(r) for r in q["t"]), max(sum(q["t"][j][k] for j in range(nj)) for k in range(m))))
        elif variant in ("jss", "fjsp") and isinstance(q.get("jobs"), list) and q["jobs"] and all(isinstance(j, list) and j for j in q["jobs"]):
            jobs = q["jobs"]
            q.setdefault("n_jobs", len(jobs))
            q.setdefault("n", sum(len(j) for j in jobs))
            if variant == "jss":
                q.setdefault("m_mach", max(k for j in jobs for k, _t in j) + 1)
                q.setdefault("lb", 0)
            else:
                q.setdefault("m_mach", max(k for j in jobs for op in j for k, _t in op) + 1)
                q.setdefault("lb", 0)
        elif variant in ("hc", "lpath") and isinstance(q.get("pts"), list):
            q.setdefault("n", len(q["pts"]))
        elif variant in ("mst", "gmatch") and isinstance(q.get("pts"), list) and isinstance(q.get("edges"), list):
            q.setdefault("n_nodes", len(q["pts"]))
            q.setdefault("n", len(q["edges"]))
            q.setdefault("opt", 0)
        elif variant == "shortestpath" and isinstance(q.get("pts"), list):
            q.setdefault("n", len(q["pts"]))
            q.setdefault("src", 0)
            q.setdefault("dst", len(q["pts"]) - 1)
            q.setdefault("opt", 0)
        elif variant in ("maxflow", "mincostflow") and isinstance(q.get("pts"), list) and isinstance(q.get("arcs"), list):
            q.setdefault("n_nodes", len(q["pts"]))
            q.setdefault("n", len(q["arcs"]))
            q.setdefault("src", 0)
            q.setdefault("snk", len(q["pts"]) - 1)
            q.setdefault("opt", 0)
            if variant == "mincostflow":
                q.setdefault("need", 1)
        elif variant == "topsort" and isinstance(q.get("pts"), list):
            q.setdefault("n", len(q["pts"]))
            q.setdefault("opt", 0)
        elif variant == "msa" and isinstance(q.get("seqs"), list) and q["seqs"] and all(isinstance(x, str) for x in q["seqs"]):
            q.setdefault("W", max(len(x) for x in q["seqs"]) + 4)
            q.setdefault("n", 3 * q["W"])
            q.setdefault("opt", 0)
        elif variant in ("carp", "rpostman") and isinstance(q.get("req"), list):
            q.setdefault("n", len(q["req"]))
            q.setdefault("dem", [0] * len(q["req"]))
            q.setdefault("depot", 0)
            q.setdefault("cap", 20 if variant == "carp" else 10 ** 6)
        elif variant == "ndp" and isinstance(q.get("edges"), list) and isinstance(q.get("pts"), list):
            q.setdefault("n", len(q["edges"]))
            q.setdefault("n_pts", len(q["pts"]))
        elif variant == "tdm" and mat(q.get("sets")):
            sets = q["sets"]
            q.setdefault("n", len(sets))
            q.setdefault("q", len(sets[0]) // 3)
            if len(sets[0]) % 3 == 0:
                w = len(sets[0]) // 3
                q.setdefault("triples", [[r.index(1) if 1 in r else 0, (r[w:2 * w].index(1) if 1 in r[w:2 * w] else 0),
                                          (r[2 * w:].index(1) if 1 in r[2 * w:] else 0)] for r in sets])
    except (TypeError, ValueError, AttributeError):
        return dict(p)
    return q


def _v_entryseq(p, R, variant):
    """词条域：通用的形状检查之外，给语义要求严格的变体补上「数据之间必须自洽」的检查。"""
    if variant == "kmeans" and "n" not in p and isinstance(p.get("k"), int) and not isinstance(p.get("k"), bool):
        p = dict(p, n=2 * p["k"])  # n = 决策向量长度 = 2k，用户只需要给簇数 k
    p = _es_fill(variant, p)
    out = _v_generic("entryseq", p, R, variant)
    if out is None:
        return None
    n = out.get("n")
    if variant == "atsp":
        d = out["d"]
        if len(d) != n or any(len(r) != n for r in d):
            R.err("d", f"距离矩阵应为 {n}×{n}（与城市数一致），收到 {len(d)} 行")
            return None
        for i in range(n):
            if d[i][i] != 0:
                R.err(f"d[{i}][{i}]", f"对角线（到自己的代价）应为 0，收到 {d[i][i]}")
                return None
            for j in range(n):
                if d[i][j] < 0:
                    R.err(f"d[{i}][{j}]", f"代价不能为负，收到 {d[i][j]}")
                    return None
        if len(out["pts"]) != n:
            R.err("pts", f"绘图坐标应有 {n} 个点（只用来画图，不影响求解），收到 {len(out['pts'])} 个")
            return None
        if all(d[i][j] == d[j][i] for i in range(n) for j in range(i + 1, n)):
            R.warn("d", "这个矩阵是对称的——它其实是普通 TSP，可以在演示页用 TSP 导入（那里的专用算法更快）")
    elif variant in ("vrptw", "vrpstw"):
        hard = variant == "vrptw"
        pts, dem, e, l, svc = out["pts"], out["demand"], out["e"], out["l"], out["svc"]
        if not hard and (not isinstance(out["lam"], (int, float)) or out["lam"] < 0):
            R.err("lam", f"迟到罚系数 lam 不能为负，收到 {_show(out['lam'])}")
            return None
        for name, arr in (("pts", pts), ("demand", dem), ("e", e), ("l", l), ("svc", svc)):
            if len(arr) != n + 1:
                R.err(name, f"应有 {n + 1} 项（第 0 项是仓库，后面 {n} 个客户），收到 {len(arr)} 项")
                return None
        cap, H = out["cap"], l[0]
        if not (isinstance(cap, (int, float)) and cap > 0):
            R.err("cap", f"车辆容量必须大于 0，收到 {_show(cap)}")
            return None
        if H <= 0:
            R.err("l[0]", f"仓库关门时刻（l[0]）必须大于 0，收到 {H}")
            return None
        if out["m_veh"] < 1:
            R.err("m_veh", "车辆数至少 1 辆")
            return None
        if sum(dem) > out["m_veh"] * cap:
            R.err("m_veh", f"{out['m_veh']} 辆车 × 容量 {cap} 装不下总需求 {sum(dem)}——无论怎么排都没有可行解")
            return None
        for i in range(1, n + 1):
            if dem[i] < 0 or dem[i] > cap:
                R.err(f"demand[{i}]", f"客户需求应在 0..容量({cap}) 之间，收到 {dem[i]}")
                return None
            if svc[i] < 0:
                R.err(f"svc[{i}]", f"服务时间不能为负，收到 {svc[i]}")
                return None
            if e[i] < 0 or e[i] > l[i]:
                R.err(f"e[{i}]", f"时间窗应满足 0 ≤ e ≤ l，收到 [{e[i]}, {l[i]}]")
                return None
            d0 = math.dist(pts[0], pts[i])
            if not hard:
                continue  # 软时间窗：来不及只是要付罚金，不是无解
            if d0 > l[i] + 1e-9:
                R.err(f"l[{i}]", f"客户 {i} 的窗口在 {l[i]} 关闭，而从仓库直接开过去就要 {d0:.1f}——永远来不及")
                return None
            back = max(d0, e[i]) + svc[i] + d0
            if back > H + 1e-9:
                R.err(f"l[{i}]", f"客户 {i} 单独跑一趟也要到 {back:.1f} 才能回仓库，而仓库在 {H} 关门——没有可行解")
                return None
    elif variant == "mdvrp":
        pts, dem, cap = out["pts"], out["demand"], out["cap"]
        Dp, m_dep = out["D"], out["m_dep"]
        if len(pts) != n + 1 or len(dem) != n + 1:
            R.err("pts", f"pts 与 demand 都应有 {n + 1} 项（前 D 个是仓库，后面是客户），收到 {len(pts)} / {len(dem)} 项")
            return None
        if not (isinstance(Dp, int) and 1 <= Dp < n + 1):
            R.err("D", f"仓库数 D 应是 1..{n} 的整数（pts 里前 D 个是仓库），收到 {_show(Dp)}")
            return None
        if any(dem[d] != 0 for d in range(Dp)):
            R.err("demand", "前 D 项是仓库，需求必须为 0")
            return None
        if not (isinstance(cap, (int, float)) and cap > 0):
            R.err("cap", f"车辆容量必须大于 0，收到 {_show(cap)}")
            return None
        if not (isinstance(m_dep, int) and m_dep >= 1):
            R.err("m_dep", f"每个仓库的车辆数至少 1 辆，收到 {_show(m_dep)}")
            return None
        for i in range(Dp, n + 1):
            if dem[i] < 0 or dem[i] > cap:
                R.err(f"demand[{i}]", f"客户需求应在 0..容量({cap}) 之间，收到 {dem[i]}")
                return None
        if sum(dem) > Dp * m_dep * cap:
            R.err("m_dep", f"{Dp} 个仓库 × {m_dep} 辆车 × 容量 {cap} 装不下总需求 {sum(dem)}——没有可行解")
            return None
    elif variant == "fss":
        P_ = out["p"]
        if any(len(r) != len(P_[0]) for r in P_):
            R.err("p", "p 应为「机器数 × 作业数」的矩阵（每行是一台机器上各作业的加工时间），各行长度必须一致")
            return None
        if any(x <= 0 for r in P_ for x in r):
            R.err("p", "加工时间必须大于 0")
            return None
        if len(P_[0]) != n or len(P_) != out["m_mach"]:
            R.err("n", f"n 应等于作业数 {len(P_[0])}、m_mach 应等于机器数 {len(P_)}")
            return None
    elif variant == "oss":
        T = out["t"]
        if any(len(r) != len(T[0]) for r in T) or len(T) != len(T[0]):
            R.err("t", "开放车间要求「作业数 = 机器数」的方阵（t[j][k] = 作业 j 在机器 k 上的加工时间）")
            return None
        if any(x <= 0 for r in T for x in r):
            R.err("t", "加工时间必须大于 0")
            return None
        out["n_jobs"], out["m_mach"], out["n"] = len(T), len(T[0]), len(T) * len(T[0])
        out["lb"] = max(max(sum(r) for r in T), max(sum(T[j][k] for j in range(len(T))) for k in range(len(T[0]))))
    elif variant in ("jss", "fjsp"):
        jobs = out["jobs"]
        L = len(jobs[0])
        if any(len(j) != L for j in jobs):
            R.err("jobs", f"每个作业的工序数必须相同（这里第一个作业有 {L} 道）——标准作业车间基准里每个作业都经过每台机器一次")
            return None
        mm = -1
        for a, job in enumerate(jobs):
            for b, op in enumerate(job):
                pairs = [op] if variant == "jss" else op
                if variant == "fjsp" and (not isinstance(op, list) or not op):
                    R.err(f"jobs[{a}][{b}]", "每道工序至少要有一台可选机器")
                    return None
                for pr in pairs:
                    if not (isinstance(pr, list) and len(pr) == 2 and all(_isnum(x) for x in pr)):
                        R.err(f"jobs[{a}][{b}]", "应为 [机器编号, 加工时间]" + ("" if variant == "jss" else " 的列表（每台可选机器一对）"))
                        return None
                    k, t = pr
                    if k < 0 or int(k) != k or t <= 0:
                        R.err(f"jobs[{a}][{b}]", f"机器编号应为非负整数、加工时间应大于 0，收到 {pr}")
                        return None
                    mm = max(mm, int(k))
        if variant == "jss":
            for a, job in enumerate(jobs):
                if len({k for k, _t in job}) != len(job):
                    R.warn(f"jobs[{a}]", "同一个作业两次用到同一台机器——标准作业车间里每个作业经过每台机器一次，这会是更一般的实例")
        out["jobs"] = [[[int(k), t] for k, t in job] if variant == "jss" else [[[int(k), t] for k, t in op] for op in job] for job in jobs]
        out["n_jobs"], out["m_mach"], out["n"] = len(jobs), mm + 1, len(jobs) * L
        mload = [0] * (mm + 1)
        if variant == "jss":
            for job in jobs:
                for k, t in job:
                    mload[int(k)] += t
            out["lb"] = max(max(mload), max(sum(t for _k, t in job) for job in jobs))
        else:
            lb_job = max(sum(min(t for _k, t in op) for op in job) for job in jobs)
            lb_work = -(-sum(min(t for _k, t in op) for job in jobs for op in job) // (mm + 1))
            out["lb"] = max(lb_job, lb_work)
    elif variant in ("hc", "lpath"):
        pts, edges = out["pts"], out["edges"]
        if len(pts) != n:
            R.err("pts", f"pts 应有 {n} 个点（只用来画图），收到 {len(pts)} 个")
            return None
        for i, e in enumerate(edges):
            a, b = e[0], e[1]
            if not (0 <= a < n and 0 <= b < n) or a == b:
                R.err(f"edges[{i}]", f"边的两端应是 0..{n - 1} 里互不相同的点，收到 {e}")
                return None
            if variant == "lpath" and not (len(e) >= 3 and e[2] > 0):
                R.err(f"edges[{i}]", "最长路径的边应为 [u, v, 权重]，权重大于 0")
                return None
    elif variant in ("carp", "rpostman"):
        pts, edges, req, dem = out["pts"], out["edges"], out["req"], out["dem"]
        nv = len(pts)
        for i, e in enumerate(edges):
            if not (0 <= e[0] < nv and 0 <= e[1] < nv) or e[0] == e[1] or e[2] < 1:
                R.err(f"edges[{i}]", f"路网的边应为 [u, v, 费用]：两端是 0..{nv - 1} 里不同的路口，费用 ≥ 1，收到 {e}")
                return None
        if not (isinstance(out["depot"], int) and 0 <= out["depot"] < nv):
            R.err("depot", f"仓库应是 0..{nv - 1} 的路口编号，收到 {_show(out['depot'])}")
            return None
        if len(set(req)) != len(req) or any(not (0 <= r < len(edges)) for r in req):
            R.err("req", f"必需边应是 edges 下标（0..{len(edges) - 1}）且互不相同")
            return None
        if len(dem) != len(req):
            R.err("dem", f"dem 应与 req 一一对应（{len(req)} 项），收到 {len(dem)} 项")
            return None
        if not (out["cap"] > 0):
            R.err("cap", "车容量必须大于 0")
            return None
        if any(d < 0 or d > out["cap"] for d in dem):
            R.err("dem", f"每条必需边的需求应在 0..容量({out['cap']}) 之间")
            return None
        par = list(range(nv))

        def _f(x):
            while par[x] != x:
                par[x] = par[par[x]]
                x = par[x]
            return x
        for a, b, _c in edges:
            par[_f(a)] = _f(b)
        if len({_f(i) for i in range(nv)}) > 1:
            R.err("edges", "路网不连通——车辆到不了所有必需边，没有可行解")
            return None
    elif variant == "ndp":
        pts, edges, pairs = out["pts"], out["edges"], out["pairs"]
        nv = len(pts)
        for i, e in enumerate(edges):
            if not (0 <= e[0] < nv and 0 <= e[1] < nv) or e[0] == e[1] or e[2] < 0:
                R.err(f"edges[{i}]", f"候选边应为 [u, v, 建设费]：两端是 0..{nv - 1} 里不同的点，费用 ≥ 0，收到 {e}")
                return None
        for i, q in enumerate(pairs):
            if len(q) != 2 or not all(isinstance(x, int) and 0 <= x < nv for x in q) or q[0] == q[1]:
                R.err(f"pairs[{i}]", f"需求对应是 0..{nv - 1} 里两个不同的点，收到 {q}")
                return None
        par = list(range(nv))

        def _f2(x):
            while par[x] != x:
                par[x] = par[par[x]]
                x = par[x]
            return x
        for a, b, _c in edges:
            par[_f2(a)] = _f2(b)
        for i, (a, b) in enumerate(pairs):
            if _f2(a) != _f2(b):
                R.err(f"pairs[{i}]", f"点 {a} 与 {b} 在候选边构成的图里就不连通——怎么买都连不起来")
                return None
        out["n"], out["n_pts"] = len(edges), nv
    elif variant == "cflp":
        if not (len(out["cap"]) == len(out["dem"]) == len(out["fc"]) == len(out["pts"]) == n):
            R.err("cap", f"pts / cap / dem / fc 都应有 {n} 项（每个点既是客户也是候选设施）")
            return None
        if any(x <= 0 for x in out["cap"]) or any(x < 0 for x in out["dem"]) or any(x < 0 for x in out["fc"]):
            R.err("cap", "容量应大于 0，需求与固定费不能为负")
            return None
        if sum(out["cap"]) < sum(out["dem"]):
            R.err("cap", f"总容量 {sum(out['cap'])} 小于总需求 {sum(out['dem'])}——没有可行解")
            return None
    elif variant == "lrp":
        if not (len(out["pts"]) == len(out["dem"]) == n):
            R.err("dem", f"pts 与 dem 都应有 {n} 项")
            return None
        if not (isinstance(out["p"], int) and 1 <= out["p"] < n):
            R.err("p", f"仓库数 p 应是 1..{n - 1} 的整数，收到 {_show(out['p'])}")
            return None
        if not (out["cap"] > 0) or any(d < 0 or d > out["cap"] for d in out["dem"]):
            R.err("cap", f"车容量应大于 0，且每个客户的需求在 0..{out['cap']} 之间")
            return None
    elif variant == "tdm":
        sets = out["sets"]
        w = len(sets[0]) // 3
        if len(sets[0]) % 3 or w < 2:
            R.err("sets", "每行应有 3q 列（X、Y、Z 各 q 个元素，q ≥ 2）")
            return None
        for i, r in enumerate(sets):
            if any(x not in (0, 1) for x in r) or sum(r[:w]) != 1 or sum(r[w:2 * w]) != 1 or sum(r[2 * w:]) != 1:
                R.err(f"sets[{i}]", "每个三元组恰在 X、Y、Z 三段各有一个 1")
                return None
        out["n"], out["q"] = len(sets), w
    elif variant in ("mst", "gmatch", "shortestpath"):
        D = _engine()
        pts, edges = out["pts"], out["edges"]
        nv = len(pts)
        if variant != "shortestpath" and out["n_nodes"] != nv:
            R.err("n_nodes", f"n_nodes 应等于点数 {nv}")
            return None
        for i, e in enumerate(edges):
            if not (0 <= e[0] < nv and 0 <= e[1] < nv) or e[0] == e[1] or e[2] <= 0:
                R.err(f"edges[{i}]", f"边应为 [u, v, 权重]：两端是 0..{nv - 1} 里不同的点，权重大于 0，收到 {e}")
                return None
        par = list(range(nv))

        def _f3(x):
            while par[x] != x:
                par[x] = par[par[x]]
                x = par[x]
            return x
        for a, b, _w in edges:
            par[_f3(a)] = _f3(b)
        if len({_f3(i) for i in range(nv)}) > 1:
            R.err("edges", "图不连通" + ("：没有生成树" if variant == "mst" else "：有些点之间没有任何路径"))
            return None
        if variant == "mst":
            out["n"], out["opt"] = len(edges), D._opt_mst(nv, edges)
        elif variant == "gmatch":
            if nv > 16:
                R.err("pts", f"匹配的精确对照用顶点子集动态规划，最多支持 16 个点，收到 {nv}")
                return None
            out["n"], out["opt"] = len(edges), D._opt_gmatch(nv, edges)
        else:
            src, dst = out["src"], out["dst"]
            if not (isinstance(src, int) and isinstance(dst, int) and 0 <= src < nv and 0 <= dst < nv and src != dst):
                R.err("src", f"起点与终点应是 0..{nv - 1} 里两个不同的点")
                return None
            out["n"], out["opt"] = nv, D._opt_sp(nv, edges, src, dst)
    elif variant in ("maxflow", "mincostflow"):
        D = _engine()
        pts, arcs = out["pts"], out["arcs"]
        nv = len(pts)
        w = 3 if variant == "maxflow" else 4
        for i, a in enumerate(arcs):
            if len(a) != w or not (0 <= a[0] < nv and 0 <= a[1] < nv) or a[0] == a[1] or a[2] <= 0 or (w == 4 and a[3] < 0):
                R.err(f"arcs[{i}]", f"弧应为 [起点, 终点, 容量{', 单位费用' if w == 4 else ''}]：两端是 0..{nv - 1} 里不同的点，容量大于 0" + ("，费用 ≥ 0" if w == 4 else "") + f"，收到 {a}")
                return None
        src, snk = out["src"], out["snk"]
        if not (isinstance(src, int) and isinstance(snk, int) and 0 <= src < nv and 0 <= snk < nv and src != snk):
            R.err("src", f"源点与汇点应是 0..{nv - 1} 里两个不同的点")
            return None
        cap_arcs = [[a[0], a[1], a[2]] for a in arcs]
        fmax, _c = D._pc_max_flow(nv, cap_arcs, src, snk)
        if fmax <= 0:
            R.err("arcs", "源点到不了汇点——最大流为 0，没有可行的流")
            return None
        out["n_nodes"], out["n"] = nv, len(arcs)
        if variant == "maxflow":
            out["opt"] = fmax
        else:
            need = out["need"]
            if not (isinstance(need, (int, float)) and 0 < need <= fmax):
                R.err("need", f"需要送出的流量应在 (0, {fmax}] 之间（{fmax} 是这张网络的最大流），收到 {_show(need)}")
                return None
            _f, out["opt"] = D._pc_max_flow(nv, cap_arcs, src, snk, cost=[a[3] for a in arcs], want=int(need))
    elif variant == "topsort":
        pts, arcs = out["pts"], out["arcs"]
        nv = len(pts)
        for i, a in enumerate(arcs):
            if len(a) != 2 or not (0 <= a[0] < nv and 0 <= a[1] < nv) or a[0] == a[1]:
                R.err(f"arcs[{i}]", f"弧应为 [起点, 终点]：0..{nv - 1} 里两个不同的点，收到 {a}")
                return None
        indeg = [0] * nv
        for a, b in arcs:
            indeg[b] += 1
        queue = [v for v in range(nv) if indeg[v] == 0]
        seen = 0
        while queue:
            u = queue.pop()
            seen += 1
            for a, b in arcs:
                if a == u:
                    indeg[b] -= 1
                    if indeg[b] == 0:
                        queue.append(b)
        if seen < nv:
            R.err("arcs", "图里有环，不存在拓扑序（目标「违反的弧数」最小只能到 > 0）；拓扑排序要求有向无环图")
            return None
        out["n"], out["opt"] = nv, 0
    elif variant == "msa":
        D = _engine()
        seqs = out["seqs"]
        if len(seqs) != 3 or any(not x or len(x) > 20 or not x.isalpha() for x in seqs):
            R.err("seqs", "多序列比对目前固定为 3 条序列，每条 1–20 个字母（精确对照用三维动态规划）")
            return None
        W = out["W"]
        if not (isinstance(W, int) and W >= max(len(x) for x in seqs)):
            R.err("W", f"比对宽度 W 至少要等于最长序列的长度 {max(len(x) for x in seqs)}")
            return None
        out["n"], out["opt"] = 3 * W, D._msa_dp(seqs)
    elif variant == "pms":
        if any(x <= 0 for x in out["p"]):
            R.err("p", "加工时间必须大于 0")
            return None
        m = out["m_mach"]
        if not isinstance(m, int) or isinstance(m, bool) or m < 2:
            R.err("m_mach", f"机器数应为 ≥ 2 的整数，收到 {m!r}")
            return None
    elif variant == "numpart":
        if any(x <= 0 for x in out["a"]) or len(out["a"]) < 2:
            R.err("a", "需要至少 2 个正数")
            return None
    elif variant == "kmeans":
        k = out["k"]
        if not isinstance(k, int) or isinstance(k, bool) or k < 2:
            R.err("k", f"簇数 k 应为 ≥ 2 的整数，收到 {k!r}")
            return None
        if len(out["pts"]) < k:
            R.err("pts", f"点数（{len(out['pts'])}）不能少于簇数 k={k}")
            return None
        if "n" in p and p["n"] != 2 * k:
            R.err("n", f"n 应为 2k = {2 * k}（k 个中心的 x、y 坐标），收到 {p['n']}")
            return None
        if len({tuple(q) for q in out["pts"]}) < k:
            R.err("pts", "互不相同的点比簇数还少，无法分成 k 簇")
            return None
        out["n"] = 2 * k
    elif variant in ("wbeam", "pvessel", "tcspring", "reducer"):
        D = _engine()
        want = len(D._DESIGN[variant]["names"])
        if n != want:
            R.err("n", f"{variant} 是固定的设计问题，n 必须为 {want}，收到 {n}")
            return None
    return out


def _v_kpvar(p, R, variant):
    out = _v_generic("kpvar", p, R, variant)
    if out is None:
        return None
    for key in ("w", "w2"):
        flat = out.get(key)
        if flat is not None:
            xs = [x for row in flat for x in (row if isinstance(row, list) else [row])]
            if any(x <= 0 for x in xs):
                R.err(key, "重量必须全部大于 0")
                return None
    for it in out.get("items", []):
        if it[0] <= 0:
            R.err("items", "物品重量（每项第 0 个数）必须大于 0")
            return None
    return out


def _v_bpvar(p, R, variant):
    out = _v_generic("bpvar", p, R, variant)
    if out is None:
        return None
    if variant == "vsbinpack":
        biggest = max(b[0] for b in out["bin_types"])
        bad = [i for i, w in enumerate(out["items"]) if w > biggest]
        if bad:
            R.err(f"items[{bad[0]}]", f"物品尺寸超过最大箱型容量 {biggest}，装不下")
            return None
    elif variant == "binpack2d":
        for i, (w, h) in enumerate(out["items"]):
            if w > out["binW"] or h > out["binH"]:
                R.err(f"items[{i}]", f"物品 {w}×{h} 比箱子 {out['binW']}×{out['binH']} 还大，装不下")
                return None
    return out


# ------------------------------------------------------------------ 总入口

_SIMPLE = {"tsp": _v_tsp, "knapsack": _v_knapsack, "multiobj": _v_multiobj, "binpack": _v_binpack,
           "graphcolor": _v_graphcolor, "setcover": _v_setcover, "sat": _v_sat, "qubo": _v_qubo,
           "gap": _v_gap, "uflp": _v_uflp, "continuous": _v_continuous}


def validate(domain, data, variant=None, dry_run=False):
    """校验并规整一个实例。dry_run=True 时额外用引擎真跑 2 代做兜底（会占用引擎的全局运行态，
    页面上只应在空闲时调用）。"""
    R = _R()
    if domain not in CORE_DOMAINS:
        R.err("domain", f"不支持的问题域 {_show(domain)}。可选：{', '.join(CORE_DOMAINS)}")
        return _result(R, None)
    if domain == "tsp":
        prob = _v_tsp(data, R)
        return _result(R, prob)
    if not isinstance(data, dict):
        R.err("", "实例应为 JSON 对象（花括号），收到 " + _show(data))
        return _result(R, None)
    variant = variant or data.get("variant")
    try:
        if domain in _SIMPLE:
            prob = _SIMPLE[domain](data, R)
        elif domain == "gcvar":
            prob = _v_gcvar(data, R, variant or "mis")
        elif domain == "custom":
            prob = _v_custom(data, R, variant)
        elif domain == "mocont":
            prob = _v_mocont(data, R, variant or "zdt1")
        elif domain in ("kpvar", "bpvar", "entryseq"):
            if not variant:
                R.err("variant", f"{domain} 需要指定 variant（变体）")
                prob = None
            elif domain == "kpvar":
                prob = _v_kpvar(data, R, variant)
            elif domain == "bpvar":
                prob = _v_bpvar(data, R, variant)
            else:
                prob = _v_entryseq(data, R, variant)
        else:  # pragma: no cover
            prob = None
    except ImportError:
        R.err("", "缺少 domains.py（校验器需要与引擎同目录）")
        prob = None
    if prob is not None and not R.errors:
        _fidelity_warning(domain, prob.get("variant") if isinstance(prob, dict) else None, R)
    if prob is not None and dry_run and not R.errors:
        _dry_run(domain, prob, R)
        if R.errors:
            prob = None
    return _result(R, prob if not R.errors else None)


_FID_PREFIX = {"simplified": "这是「教学简化模型」", "illustrative": "这是「示意模型」"}
_FID_TAIL = {"simplified": "结果不能与文献对照。", "illustrative": "它只借这个问题的名字演示形态，不是该问题本身。"}


def _fidelity_warning(domain, variant, R):
    """entryseq 词条的变体多为教学简化/示意模型：用户上传自己的数据时必须被告知。"""
    if domain != "entryseq" or not variant:
        return
    try:
        fid = getattr(_engine(), "FIDELITY", {}).get(variant)
    except ImportError:
        return
    if fid and fid["level"] in _FID_PREFIX:
        R.warn("", f"{_FID_PREFIX[fid['level']]}（{domain}/{variant}）：{fid['note']}。{_FID_TAIL[fid['level']]}")


def _dry_run(domain, prob, R):
    D = _engine()
    try:
        opts = {"variant": prob["variant"]} if "variant" in prob else {}
        algos = [a["key"] for a in json.loads(D.domain_list(domain, opts))["algos"]]
        for algo in [a for a in ("random", "sa") if a in algos] or algos[:1]:
            D.domain_start(domain, json.dumps(prob), algo, json.dumps({"max_iter": 3, "seed": 7}))
            for _ in range(3):
                D.domain_step()
    except Exception as e:
        R.err("", f"引擎试跑失败：{type(e).__name__}: {str(e)[:120]}（实例结构通过了检查，但引擎无法处理，请核对数据含义）")


def _result(R, prob):
    return {"ok": not R.errors, "errors": R.errors, "warnings": R.warnings,
            "problem": prob if not R.errors else None}


# ------------------------------------------------------------------ 文件解析

_GUESS = (  # (必须出现的键, 域)——只在唯一匹配时使用
    ({"cities"}, "tsp"), ({"n_vars", "clauses"}, "sat"), ({"clauses"}, "sat"), ({"Q"}, None),
    ({"n_el", "sets"}, "setcover"), ({"sets", "costs"}, "setcover"),
    ({"n_f", "c_cost"}, "uflp"), ({"f_cost", "c_cost"}, "uflp"), ({"n_a", "c", "r"}, "gap"),
    ({"c", "r", "cap"}, "gap"), ({"fn"}, "continuous"), ({"variant", "objective", "n"}, "custom"),
)


def guess_domain(data):
    if not isinstance(data, dict):
        return None
    keys = set(data)
    if "Q" in keys:
        return "kpvar" if "w" in keys else "qubo"
    for need, dom in _GUESS:
        if dom and need <= keys:
            return dom
    if "edges" in keys and "variant" not in keys:
        return "graphcolor"
    return None


def load(text_or_obj, domain=None, filename=None):
    """把上传内容读成 (domain, data, issues)。支持 JSON 信封 / 裸 JSON / CSV / DIMACS。"""
    R = _R()
    obj = text_or_obj
    name = (filename or "").lower()
    if isinstance(obj, (bytes, bytearray)):
        obj = obj.decode("utf-8-sig", errors="replace")
    if isinstance(obj, str):
        txt = obj.lstrip("﻿").strip()
        if not txt:
            R.err("", "文件是空的")
            return domain, None, R
        if name.endswith((".tsp", ".atsp")) or (txt[0] not in "[{" and _looks_like_tsplib(txt)):
            if domain == "entryseq":  # ATSP 页：读 TYPE: ATSP 的 TSPLIB 文件
                return "entryseq", _parse_tsplib(txt, R, atsp=True), R
            if domain not in (None, "tsp"):
                R.err("domain", f"这是 TSPLIB（旅行商）文件，但当前页面是 '{domain}'")
                return domain, None, R
            return "tsp", _parse_tsplib(txt, R), R
        if name.endswith(".cnf") or re.search(r"^p\s+cnf\b", txt, re.M):
            return "sat", _parse_cnf(txt, R), R
        if name.endswith(".col") or re.search(r"^p\s+edge\b", txt, re.M):
            return "graphcolor" if domain in (None, "graphcolor") else domain, _parse_col(txt, R), R
        if txt[0] in "[{":
            try:
                obj = json.loads(txt)
            except ValueError as e:
                R.err("", f"不是合法 JSON：{e}")
                return domain, None, R
        else:
            if domain is None:
                R.err("domain", "CSV/文本文件需要指定问题域（knapsack/binpack/graphcolor/qubo/tsp）")
                return None, None, R
            return domain, _parse_csv(domain, txt, R), R
    if isinstance(obj, dict) and obj.get("schema") == SCHEMA:
        d = obj.get("domain")
        if domain and d and domain != d:
            R.err("domain", f"文件内容属于 '{d}'，但当前页面/参数是 '{domain}'")
            return domain, None, R
        data = obj.get("data")
        if obj.get("variant") and isinstance(data, dict):
            data = dict(data, variant=data.get("variant", obj["variant"]))
        return d or domain, data, R
    if isinstance(obj, dict) and obj.get("schema") == RESULT_SCHEMA:
        d = obj.get("domain")
        if domain and d and domain != d:
            R.err("domain", f"这个结果文件属于 '{d}'，但当前页面/参数是 '{domain}'")
            return domain, None, R
        prob = obj.get("problem")
        if not isinstance(prob, dict):
            R.err("problem", "结果文件里没有 problem（实例）字段，无法当作问题文件导入")
            return d or domain, None, R
        if obj.get("variant") and "variant" not in prob:
            prob = dict(prob, variant=obj["variant"])
        return d or domain, prob, R
    if isinstance(obj, dict) and obj.get("format") in ("domain-experiment/v1", "domain-experiment-bundle/v1"):
        return obj.get("domain") or domain, obj.get("problem"), R
    if domain is None:
        domain = guess_domain(obj)
        if domain is None and not (isinstance(obj, list) and obj and isinstance(obj[0], list)):
            R.err("domain", "无法判断问题域：请使用 swarm-problem/v1 信封，或显式指定 domain")
            return None, None, R
        if domain is None:
            domain = "tsp"
    return domain, obj, R


def _num_or_err(R, where, tok):
    try:
        f = float(tok)
        return int(f) if f.is_integer() and re.fullmatch(r"[+-]?\d+(\.0+)?", tok.strip()) else f
    except ValueError:
        R.err(where, f"应为数字，收到 {_show(tok)}")
        return None


def _csv_rows(txt):
    meta, rows = {}, []
    for ln, line in enumerate(txt.splitlines(), 1):
        s = line.strip()
        if not s:
            continue
        if s.startswith("#"):
            for k, v in re.findall(r"(\w+)\s*=\s*([^\s,]+)", s):
                meta[k] = v
            continue
        rows.append((ln, next(csv.reader([s], delimiter=";" if ";" in s and "," not in s else ","))))
    return meta, rows


def _parse_csv(domain, txt, R):
    meta, rows = _csv_rows(txt)
    if rows and not all(re.fullmatch(r"[+-]?\d*\.?\d+([eE][+-]?\d+)?", t.strip()) for t in rows[0][1] if t.strip()):
        rows = rows[1:]  # 跳过表头
    table = []
    for ln, r in rows:
        vals = [_num_or_err(R, f"第 {ln} 行", t) for t in r if t.strip() != ""]
        if None in vals:
            return None
        table.append(vals)
    if not table:
        R.err("", "没有读到任何数据行")
        return None
    if domain == "knapsack":
        if "cap" not in meta and "capacity" not in meta:
            R.err("cap", "CSV 需要在文件开头用注释行写容量，例如：# cap=532")
            return None
        return {"cap": _num_or_err(R, "cap", meta.get("cap", meta.get("capacity"))), "items": table}
    if domain == "binpack":
        if "cap" not in meta and "capacity" not in meta:
            R.err("cap", "CSV 需要在文件开头用注释行写箱容量，例如：# cap=150")
            return None
        return {"cap": _num_or_err(R, "cap", meta.get("cap", meta.get("capacity"))), "items": [r[0] for r in table]}
    if domain == "qubo":
        return {"Q": table}
    if domain == "tsp":
        return _csv_tsp(table, meta, R)
    if domain in ("graphcolor", "gcvar"):
        d = {"edges": table}
        if "n" in meta:
            d["n"] = int(meta["n"])
        return d
    R.err("domain", f"域 '{domain}' 不支持 CSV；请使用 JSON（见 docs/data-formats.md）")
    return None


def _parse_cnf(txt, R):
    n_vars, clauses, cur = None, [], []
    for ln, line in enumerate(txt.splitlines(), 1):
        s = line.strip()
        if not s or s[0] in "c%":
            continue
        if s.startswith("p"):
            parts = s.split()
            if len(parts) < 4 or parts[1] != "cnf":
                R.err(f"第 {ln} 行", "DIMACS 头应为：p cnf <变量数> <子句数>")
                return None
            n_vars = int(parts[2])
            continue
        for tok in s.split():
            try:
                v = int(tok)
            except ValueError:
                R.err(f"第 {ln} 行", f"DIMACS 里应为整数，收到 {_show(tok)}")
                return None
            if v == 0:
                if cur:
                    clauses.append(cur)
                cur = []
            else:
                cur.append(v)
    if cur:
        clauses.append(cur)
    if n_vars is None:
        R.warn("n_vars", "缺少 'p cnf' 头，将按最大变量编号推断")
    return {"n_vars": n_vars, "clauses": clauses} if n_vars is not None else {"clauses": clauses}


def _parse_col(txt, R):
    n, edges = None, []
    for ln, line in enumerate(txt.splitlines(), 1):
        s = line.strip().split()
        if not s or s[0] == "c":
            continue
        if s[0] == "p":
            if len(s) < 3:
                R.err(f"第 {ln} 行", "DIMACS 头应为：p edge <顶点数> <边数>")
                return None
            n = int(s[2])
        elif s[0] == "e" and len(s) >= 3:
            try:
                edges.append([int(s[1]) - 1, int(s[2]) - 1])  # DIMACS 顶点从 1 起，转 0 起
            except ValueError:
                R.err(f"第 {ln} 行", f"边应为 e <u> <v>，收到 {_show(line.strip())}")
                return None
    d = {"edges": edges}
    if n is not None:
        d["n"] = n
    return d


def to_envelope(domain, data, variant=None):
    env = {"schema": SCHEMA, "domain": domain}
    if variant:
        env["variant"] = variant
    env["data"] = data
    return env


def supported(domain):
    return domain in CORE_DOMAINS


def check_text(text, domain=None, filename=None, dry_run=False, variant=None):
    """一步到位：读取 + 校验。返回 {"domain", "ok", "errors", "warnings", "problem"}。
    variant：调用方（如固定变体的页面）期望的变体；文件里写了不同变体时报错，而不是悄悄按错的结构去跑。"""
    d, data, R = load(text, domain, filename)
    if data is None or R.errors:
        return {"domain": d, "ok": False, "errors": R.errors, "warnings": R.warnings, "problem": None}
    if variant and isinstance(data, dict) and data.get("variant") not in (None, variant):
        R.err("variant", f"文件是变体 '{data['variant']}' 的数据，而这里需要变体 '{variant}'（请到对应变体的页面导入）")
        return {"domain": d, "ok": False, "errors": R.errors, "warnings": R.warnings, "problem": None}
    res = validate(d, data, variant=variant, dry_run=dry_run)
    if variant and res["ok"] and res["problem"].get("variant") not in (None, variant):
        R.err("variant", f"数据是变体 '{res['problem']['variant']}' 的格式，而这里需要变体 '{variant}'（请到对应变体的页面导入）")
        return {"domain": d, "ok": False, "errors": R.errors, "warnings": R.warnings + res["warnings"], "problem": None}
    res["domain"] = d
    res["warnings"] = R.warnings + res["warnings"]
    return res

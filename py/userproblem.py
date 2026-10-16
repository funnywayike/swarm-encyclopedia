# -*- coding: utf-8 -*-
"""
自带问题（Bring Your Own Problem）：用户选一种「解的形状」（编码）+ 写一个目标函数，
该编码下已有的全部算法内核原样可用。设计与安全边界见 docs/design-bring-your-own-problem.md。

三种编码（= domains 引擎里 custom 域的三个变体）：
    bits  一串是/否（长度 n）           → 位向量内核（与 QUBO 同一批 21 个算法）
    perm  一个排序（0..n-1 的排列）      → 排列内核（与装箱/着色同一批 22 个算法）
    real  一组实数（n 维，统一范围 lo..hi）→ 连续内核（与连续函数同一批 21 个算法）

目标函数（L1 表达式）：Python 表达式的受限子集，用 ast 解析后按白名单检查，**不使用 eval 处理用户原文**——
没有 import、没有属性访问、没有循环语句、没有字符串，只能做算术、比较、推导式和白名单函数。
目标函数（L3 本地 Python）：命令行 `--objective-py` 才会打开，浏览器里永远关闭（见 enable_python）。

纯标准库。浏览器里本文件与 domains.py 拼接进同一名字空间（同 entryseq.py 的做法）。
"""
import ast
import difflib
import json
import math
import random
import re
import time

ENCODINGS = ("bits", "perm", "real")

UP_LIMITS = {
    "bits": 1000, "perm": 300, "real": 100,
    "src_chars": 4000, "stmts": 30, "nodes": 900,
    "data_cells": 250000,          # 全部数据表的格子总数
    "iter_budget": 2000000,        # 一次评价里推导式最多迭代这么多次
    "range_cap": 1000000,          # 单个 range 的上限
    "pow_exp": 64,                 # 整数幂的指数上限
    "int_bits": 4096,              # 整数乘法 / 乘方结果的位数上限（防止 30 条语句连续平方撑爆内存）
}
PENALTY = 1e18                      # 目标函数在某个解上出错 / 非有限时给的惩罚（内部统一按最小化）
_DRY_RUNS = 30

_PY_ENABLED = False


def enable_python():
    """打开「本地 Python 目标函数」。只有命令行入口会调用；浏览器里的 worker 永远不调用它。"""
    global _PY_ENABLED
    _PY_ENABLED = True


def python_enabled():
    return _PY_ENABLED


class UPError(ValueError):
    """用户的目标函数 / 数据不合格。msg 里已含行号，可直接展示。"""

    def __init__(self, path, msg):
        ValueError.__init__(self, msg)
        self.path = path
        self.msg = msg


class _EvalError(Exception):
    pass


# ------------------------------------------------------------------ 白名单

def _sqrt(v):
    if v < 0:
        raise _EvalError("sqrt 的参数不能是负数")
    return math.sqrt(v)


def _log(v):
    if v <= 0:
        raise _EvalError("log 的参数必须大于 0")
    return math.log(v)


def _exp(v):
    try:
        return math.exp(v)
    except OverflowError:
        raise _EvalError("exp 的结果太大")


_FUNCS = {
    "sum": sum, "min": min, "max": max, "abs": abs, "len": len, "sorted": sorted,
    "round": round, "float": float, "int": int, "any": any, "all": all,
    "sqrt": _sqrt, "exp": _exp, "log": _log, "sin": math.sin, "cos": math.cos,
    "floor": math.floor, "ceil": math.ceil, "zip": zip, "enumerate": enumerate,
    "range": None,  # 在 UPObjective 里换成带上限的版本
}
_CONSTS = {"pi": math.pi, "e": math.e, "True": True, "False": False}
_RESERVED = set(_FUNCS) | set(_CONSTS) | {"x", "n", "objective", "lo", "hi"}

_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow)
_UNOPS = (ast.UAdd, ast.USub, ast.Not)
_CMPOPS = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE)
_BOOLOPS = (ast.And, ast.Or)

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _suggest(name, names):
    near = difflib.get_close_matches(name, sorted(names), n=2, cutoff=0.6)
    return f"（你是不是想写 {' 或 '.join(near)}？）" if near else ""


# ------------------------------------------------------------------ 静态检查

class _Checker(ast.NodeVisitor):
    def __init__(self, names):
        self.scope = [set(names)]
        self.assigned = []
        self.nodes = 0
        self.depth = 0  # 推导式嵌套深度

    def _all(self):
        out = set()
        for s in self.scope:
            out |= s
        return out

    def fail(self, node, msg):
        ln = getattr(node, "lineno", None)
        raise UPError("objective", (f"第 {ln} 行：" if ln else "") + msg)

    def generic_visit(self, node):
        self.nodes += 1
        if self.nodes > UP_LIMITS["nodes"]:
            raise UPError("objective", "表达式太长太复杂（超过 %d 个语法节点），请拆简单一些" % UP_LIMITS["nodes"])
        ast.NodeVisitor.generic_visit(self, node)

    # ---- 语句
    def visit_Module(self, node):
        if len(node.body) > UP_LIMITS["stmts"]:
            raise UPError("objective", "语句太多（最多 %d 条）" % UP_LIMITS["stmts"])
        for i, st in enumerate(node.body):
            last = i == len(node.body) - 1
            if isinstance(st, ast.Assign):
                self.visit(st)
            elif isinstance(st, ast.Expr) and last:
                self.visit(st.value)
                self.assigned.append("objective")
            else:
                self.fail(st, "只允许「名字 = 表达式」的赋值，最后一行可以直接写一个表达式作为目标值"
                              "（不支持 %s）" % type(st).__name__)
        if "objective" not in self.assigned:
            raise UPError("objective", "没有给出目标值：请写 objective = …，或让最后一行就是一个表达式")

    def visit_Assign(self, node):
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            self.fail(node, "赋值左边只能是一个名字")
        name = node.targets[0].id
        if name.startswith("_"):
            self.fail(node, "名字不能以下划线开头")
        if name in _RESERVED - {"objective"} or name in self.scope[0] - set(self.assigned) and name != "objective":
            self.fail(node, f"名字 {name} 已被占用（x、n、数据表名和内置函数不能重新赋值）")
        self.visit(node.value)
        self.assigned.append(name)
        self.scope[0].add(name)

    # ---- 表达式
    def visit_Constant(self, node):
        if isinstance(node.value, bool) or isinstance(node.value, (int, float)):
            return
        self.fail(node, "只允许数字和 True/False（不允许字符串等其它常量）")

    def visit_Name(self, node):
        if not isinstance(node.ctx, ast.Load):
            self.fail(node, "不允许在表达式里给名字赋值")
        if node.id.startswith("_"):
            self.fail(node, "名字不能以下划线开头")
        if node.id not in self._all():
            self.fail(node, f"没有叫 {node.id} 的变量{_suggest(node.id, self._all() - _RESERVED | {'x', 'n'})}。"
                            f"可用：{', '.join(sorted(self._all() - set(_FUNCS) - set(_CONSTS)))}")

    def visit_BinOp(self, node):
        if not isinstance(node.op, _BINOPS):
            self.fail(node, "不支持这个运算符；可用 + - * / // % **")
        self.generic_visit(node)

    def visit_UnaryOp(self, node):
        if not isinstance(node.op, _UNOPS):
            self.fail(node, "不支持这个一元运算符")
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        self.generic_visit(node)

    def visit_Compare(self, node):
        if not all(isinstance(o, _CMPOPS) for o in node.ops):
            self.fail(node, "比较只支持 == != < <= > >=（不支持 in / is）")
        self.generic_visit(node)

    def visit_IfExp(self, node):
        self.generic_visit(node)

    def visit_Subscript(self, node):
        if not isinstance(node.ctx, ast.Load):
            self.fail(node, "不允许对下标赋值（目标函数只能读 x 和数据，不能修改）")
        self.generic_visit(node)

    def visit_Slice(self, node):
        self.generic_visit(node)

    def visit_List(self, node):
        self.generic_visit(node)

    def visit_Tuple(self, node):
        self.generic_visit(node)

    def visit_Call(self, node):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            self.fail(node, "只能调用这些函数：" + "、".join(sorted(_FUNCS)))
        if node.keywords:
            self.fail(node, "函数调用不支持 名字=值 形式的参数")
        for a in node.args:
            if isinstance(a, ast.Starred):
                self.fail(node, "不支持 *参数 展开")
        self.nodes += 1
        for a in node.args:
            self.visit(a)

    def _comp(self, node):
        # 循环层数 = 推导式嵌套层数 + 同一个推导式里 for 的个数；最多两层（运行期还有迭代预算兜底）
        levels = len(node.generators)
        self.depth += levels
        if self.depth > 2:
            self.fail(node, "循环最多嵌套两层（推导式里的每个 for、以及推导式套推导式，都算一层）")
        self.scope.append(set())
        for gen in node.generators:
            if gen.is_async:
                self.fail(node, "不支持 async")
            self.visit(gen.iter)
            tgt = gen.target
            names = [tgt] if isinstance(tgt, ast.Name) else (list(tgt.elts) if isinstance(tgt, ast.Tuple) else None)
            if names is None or not all(isinstance(t, ast.Name) for t in names):
                self.fail(node, "for 后面只能是名字或名字元组")
            for t in names:
                if t.id.startswith("_") or t.id in _RESERVED:
                    self.fail(node, f"循环变量名 {t.id} 不可用")
                self.scope[-1].add(t.id)
            for cond in gen.ifs:
                self.visit(cond)
        elts = [node.elt]
        for e in elts:
            self.visit(e)
        self.scope.pop()
        self.depth -= levels

    def visit_ListComp(self, node):
        self._comp(node)

    def visit_GeneratorExp(self, node):
        self._comp(node)

    # 其余一律拒绝：属性访问、lambda、字符串、f-string、字典/集合、walrus、await、yield …
    def visit_Attribute(self, node):
        self.fail(node, "不允许用 .（属性访问）；需要的函数直接写名字，如 sqrt(v)、abs(v)")

    def visit_Lambda(self, node):
        self.fail(node, "不支持 lambda")

    def visit_JoinedStr(self, node):
        self.fail(node, "不支持 f 字符串")

    def visit_Dict(self, node):
        self.fail(node, "不支持字典；数据表请放在数据里，用 名字[下标] 读取")

    def visit_Set(self, node):
        self.fail(node, "不支持集合")

    def visit_DictComp(self, node):
        self.fail(node, "不支持字典推导式")

    def visit_SetComp(self, node):
        self.fail(node, "不支持集合推导式")

    def visit_NamedExpr(self, node):
        self.fail(node, "不支持 :=")

    def visit_Starred(self, node):
        self.fail(node, "不支持 * 展开")


class _Rewriter(ast.NodeTransformer):
    """检查通过后做运行期加固：整数幂 / 序列重复 / 推导式迭代量计数。"""

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Pow):
            return ast.copy_location(ast.Call(ast.Name("_pow", ast.Load()), [node.left, node.right], []), node)
        if isinstance(node.op, ast.Mult):
            return ast.copy_location(ast.Call(ast.Name("_mul", ast.Load()), [node.left, node.right], []), node)
        return node

    def visit_comprehension(self, node):
        self.generic_visit(node)
        node.iter = ast.Call(ast.Name("_it", ast.Load()), [node.iter], [])
        return node


def compile_expression(src, data_names):
    """静态检查 + 加固 + 编译。返回 (code, 赋值过的名字)。不合格抛 UPError（带行号的中文消息）。"""
    if not isinstance(src, str) or not src.strip():
        raise UPError("objective", "目标函数是空的")
    if len(src) > UP_LIMITS["src_chars"]:
        raise UPError("objective", "目标函数太长（最多 %d 个字符）" % UP_LIMITS["src_chars"])
    try:
        tree = ast.parse(src, mode="exec")
    except SyntaxError as e:
        raise UPError("objective", f"第 {e.lineno} 行语法错误：{e.msg}")
    chk = _Checker(set(data_names) | {"x", "n"} | set(_FUNCS) | set(_CONSTS))
    chk.visit(tree)
    # 最后一行是裸表达式：改写成 objective = <expr>
    last = tree.body[-1]
    if isinstance(last, ast.Expr):
        tree.body[-1] = ast.copy_location(ast.Assign([ast.Name("objective", ast.Store())], last.value), last)
    tree = _Rewriter().visit(tree)
    ast.fix_missing_locations(tree)
    return compile(tree, "<目标函数>", "exec"), chk.assigned


# ------------------------------------------------------------------ 可调用的目标函数

class UPObjective:
    """f(x) -> float。L1 表达式（默认）或本地 Python 函数（enable_python 之后）。"""

    def __init__(self, problem):
        self.n = problem["n"]
        self.data = problem.get("data", {})
        self._budget = 0
        if problem.get("objective_python"):
            if not _PY_ENABLED:
                raise UPError("objective_python", "本地 Python 目标函数只在命令行里可用（--objective-py），浏览器里不开放")
            ns = {"math": math, "random": random}
            try:
                exec(compile(problem["objective_python"], "<objective_python>", "exec"), ns)
            except Exception as e:  # noqa: BLE001
                raise UPError("objective_python", f"{type(e).__name__}: {e}")
            if not callable(ns.get("objective")):
                raise UPError("objective_python", "代码里需要定义 def objective(x, data): …")
            self._pyf = ns["objective"]
            self._code = None
            return
        self._pyf = None
        self._code, _ = compile_expression(problem.get("objective"), self.data)
        self._base = dict(self.data)
        self._base.update(_CONSTS)
        self._base.update(_FUNCS)
        self._base["n"] = self.n
        self._base["_pow"] = self._pow
        self._base["_mul"] = self._mul
        self._base["_it"] = self._it
        self._base["range"] = self._range
        self._base["__builtins__"] = {}  # 检查过的表达式本来就够不到内置名字；这里再关一道

    # ---- 运行期加固
    def _pow(self, a, b):
        if isinstance(a, (list, tuple)) or isinstance(b, (list, tuple)):
            raise _EvalError("不能对序列做乘方")
        if isinstance(a, int) and isinstance(b, int) and not isinstance(a, bool):
            if b > UP_LIMITS["pow_exp"] or b < 0:
                a = float(a)
        try:
            r = a ** b
        except OverflowError:
            raise _EvalError("乘方的结果太大")
        except ZeroDivisionError:
            raise _EvalError("0 不能做负数次幂")
        if isinstance(r, int) and r.bit_length() > UP_LIMITS["int_bits"]:
            raise _EvalError("整数太大（连续平方 / 乘方会让整数无限膨胀）")
        return r

    def _mul(self, a, b):
        if isinstance(a, (list, tuple)) or isinstance(b, (list, tuple)):
            raise _EvalError("不支持用 * 重复序列；请用推导式，如 [0 for i in range(n)]")
        if isinstance(a, int) and isinstance(b, int) and a.bit_length() + b.bit_length() > UP_LIMITS["int_bits"]:
            raise _EvalError("整数太大（连续相乘会让整数无限膨胀）")
        return a * b

    def _it(self, iterable):
        for item in iterable:
            self._budget -= 1
            if self._budget < 0:
                raise _EvalError("一次评价里循环太多（超过 %d 次迭代），请简化目标函数" % UP_LIMITS["iter_budget"])
            yield item

    def _range(self, *args):
        r = range(*[int(a) for a in args])
        if len(r) > UP_LIMITS["range_cap"]:
            raise _EvalError("range 太大（最多 %d）" % UP_LIMITS["range_cap"])
        return r

    def __call__(self, x):
        if self._pyf is not None:
            try:
                v = self._pyf(x, self.data)
            except Exception as e:  # noqa: BLE001
                raise _EvalError(f"{type(e).__name__}: {e}")
        else:
            env = dict(self._base)
            env["x"] = x
            self._budget = UP_LIMITS["iter_budget"]
            try:
                exec(self._code, env)
            except _EvalError:
                raise
            except ZeroDivisionError:
                raise _EvalError("除以 0")
            except IndexError:
                raise _EvalError("下标越界（x 或数据表的下标超出了长度）")
            except (TypeError, ValueError, OverflowError, KeyError) as e:
                raise _EvalError(f"{type(e).__name__}: {e}")
            v = env.get("objective")
        if isinstance(v, bool):
            v = int(v)
        if not isinstance(v, (int, float)):
            raise _EvalError(f"目标值应该是一个数字，算出来的是 {type(v).__name__}")
        v = float(v)
        if not math.isfinite(v):
            raise _EvalError("目标值不是有限的数（nan 或 inf）")
        return v


# ------------------------------------------------------------------ 编码上下文（与内核约定的协议）

class _UPBase:
    def __init__(self, problem):
        self.problem = problem
        self.n = problem["n"]
        self.f = UPObjective(problem)
        self.sign = -1.0 if problem.get("sense") == "max" else 1.0
        self.best_val = float("inf")   # 内部值（最小化口径）
        self.best_x = None
        self.n_err = 0
        self.first_err = ""

    def _score(self, x):
        try:
            v = self.sign * self.f(x)
        except _EvalError as e:
            self.n_err += 1
            if not self.first_err:
                self.first_err = str(e)
            return PENALTY
        if v < self.best_val:
            self.best_val = v
            self.best_x = list(x)
        return v


class UPBits(_UPBase):
    """位向量：与 QUBO 上下文同一套协议（obj / value / polish / repair / random / init_pop）。"""

    def obj(self, s):
        return self._score(s)

    def value(self, s):
        return -self.obj(s)

    def polish(self, s, rng, moves=10):
        s = list(s)
        best = self.value(s)
        for _ in range(moves):
            prev = list(s)
            i = rng.randrange(self.n)
            s[i] ^= 1
            v = self.value(s)
            if v >= best:
                best = v
            else:
                s = prev
        return s

    def repair(self, s):
        return list(s)

    def random(self, rng):
        return [rng.randint(0, 1) for _ in range(self.n)]

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(p["n_pop"])]
        return pop, [self.obj(s) for s in pop]


class UPPerm(_UPBase):
    """排列：与装箱 / 着色上下文同一套协议（decode / solution / better / diff / random）。"""

    def decode(self, perm):
        return (self._score(perm), 0.0)  # 排列内核约定 decode 返回 (主指标, 次级指标) 元组；自定义问题没有次级指标

    def solution(self, perm):
        return list(perm)

    def better(self, a, b):
        return a[0] < b[0]

    def diff(self, a, b):
        return b[0] - a[0]

    def random(self, rng):
        p = list(range(self.n))
        rng.shuffle(p)
        return p


class UPReal(_UPBase):
    """实数向量：与连续函数上下文同一套协议（dim / lo / hi / random / eval / clamp / init_pop）。"""

    def __init__(self, problem):
        _UPBase.__init__(self, problem)
        self.dim = self.n
        self.lo = float(problem["lo"])
        self.hi = float(problem["hi"])

    def random(self, rng):
        return [rng.uniform(self.lo, self.hi) for _ in range(self.dim)]

    def eval(self, x):
        return self._score(x)

    def clamp(self, x):
        return [min(self.hi, max(self.lo, v)) for v in x]

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(p["n_pop"])]
        return pop, [self.eval(x) for x in pop]


_CTX = {"bits": UPBits, "perm": UPPerm, "real": UPReal}


def up_make_ctx(problem):
    return _CTX[problem["variant"]](problem)


def up_wrap_stream(gen, ctx):
    """把内核吐出的状态整理成页面 / 命令行统一的样子：
    以评价过的全部点里最好的那个为准（有的内核不把预热 / 初始化阶段评价过的点算进「最优」，上报值就会比实际找到的差）；
    内部一律最小化，sense=max 时把 best / cur 翻回用户的口径；补上完整的最优解和出错统计。"""
    for s in gen:
        if ctx.best_x is not None and ctx.best_val < s.get("best", float("inf")):
            s["best"] = ctx.best_val
        if ctx.sign < 0:
            for k in ("best", "cur"):
                if isinstance(s.get(k), (int, float)):
                    s[k] = -s[k]
        if ctx.best_x is not None:
            s["best_sol"] = list(ctx.best_x)
        if ctx.n_err:
            s["eval_errors"] = ctx.n_err
            s["first_error"] = ctx.first_err
        yield s


# ------------------------------------------------------------------ 校验 / 规整 / 试跑

def _flat_cells(v, depth=0):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return 1 if math.isfinite(v) else None
    if isinstance(v, list) and depth < 3 and v:
        total = 0
        for e in v:
            c = _flat_cells(e, depth + 1)
            if c is None:
                return None
            total += c
        return total
    return None


def up_check(problem, dry_runs=_DRY_RUNS):
    """校验并规整一个自带问题。返回 (规整后的 problem 或 None, errors, warnings, info)，
    errors / warnings 是 [{"path", "msg"}]，info 里有试跑测得的单次评价耗时（毫秒）。"""
    errors, warnings, info = [], [], {}

    def err(path, msg):
        errors.append({"path": path, "msg": msg})

    if not isinstance(problem, dict):
        err("", "自带问题应为 JSON 对象（花括号）")
        return None, errors, warnings, info
    variant = problem.get("variant", problem.get("encoding"))
    if variant not in ENCODINGS:
        err("variant", f"需要指定编码 variant：{' / '.join(ENCODINGS)}（bits=是/否，perm=排序，real=实数），收到 {variant!r}")
        return None, errors, warnings, info
    n = problem.get("n")
    if isinstance(n, float) and n.is_integer():
        n = int(n)
    if not isinstance(n, int) or isinstance(n, bool) or n < 2:
        err("n", f"n（解的长度 / 维度）应为 ≥ 2 的整数，收到 {n!r}")
    elif n > UP_LIMITS[variant]:
        err("n", f"{variant} 编码的 n 最多 {UP_LIMITS[variant]}（浏览器内运行的规模上限），收到 {n}")
    sense = problem.get("sense", "min")
    if sense not in ("min", "max"):
        err("sense", f"sense 应为 min（越小越好）或 max（越大越好），收到 {sense!r}")
    out = {"variant": variant, "n": n, "sense": sense}
    if variant == "real":
        lo, hi = problem.get("lo"), problem.get("hi")
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (lo, hi)):
            err("lo", "real 编码需要数值范围 lo 和 hi（所有维度共用）")
        elif not lo < hi:
            err("lo", f"需要 lo < hi，收到 lo={lo}, hi={hi}")
        else:
            out["lo"], out["hi"] = lo, hi
    data = problem.get("data", {})
    clean = {}
    if not isinstance(data, dict):
        err("data", "data 应为对象：数据表名 → 数字或（嵌套）数字数组")
    else:
        cells = 0
        for k, v in data.items():
            if not isinstance(k, str) or not _NAME_RE.match(k):
                err(f"data.{k}", "数据名只能由字母、数字、下划线组成，并以字母开头")
            elif k in _RESERVED:
                err(f"data.{k}", f"数据名 {k} 与内置名字冲突（x / n / lo / hi / objective / 函数名不能用）")
            else:
                c = _flat_cells(v)
                if c is None:
                    err(f"data.{k}", "只能是数字，或最多三层嵌套的数字数组（不能有字符串 / null / 空数组 / nan）")
                else:
                    cells += c
                    clean[k] = v
        if cells > UP_LIMITS["data_cells"]:
            err("data", f"数据总量太大（{cells} 个数，上限 {UP_LIMITS['data_cells']}）")
    out["data"] = clean
    known = {"variant", "encoding", "n", "sense", "lo", "hi", "data", "objective", "objective_python", "schema"}
    for k in problem:
        if k not in known:
            warnings.append({"path": k, "msg": "未知字段，已忽略"})
    if problem.get("objective_python"):
        out["objective_python"] = problem["objective_python"]
    else:
        out["objective"] = problem.get("objective")
    if errors:
        return None, errors, warnings, info
    try:
        ctx = up_make_ctx(out)
    except UPError as e:
        err(e.path, e.msg)
        return None, errors, warnings, info
    # ---- 试跑：随机解上求值
    rng = random.Random(20260711)
    xs = [ctx.random(rng) for _ in range(dry_runs)]
    if variant == "bits":
        xs += [[0] * n, [1] * n]
    vals, bad = [], {}
    t0 = time.time()
    for x in xs:
        try:
            vals.append(ctx.f(x))
        except _EvalError as e:
            bad[str(e)] = bad.get(str(e), 0) + 1
    per_ms = (time.time() - t0) * 1000.0 / len(xs)
    info["eval_ms"] = round(per_ms, 4)
    if bad and not vals:
        msg, cnt = max(bad.items(), key=lambda kv: kv[1])
        err("objective", f"目标函数在所有 {len(xs)} 个随机解上都出错：{msg}")
        return None, errors, warnings, info
    if bad:
        msg, cnt = max(bad.items(), key=lambda kv: kv[1])
        warnings.append({"path": "objective", "msg": f"{len(xs)} 个随机解里有 {sum(bad.values())} 个让目标函数出错（{msg}）；"
                                                     f"运行时这类解会被当作极差的解，但最好在函数里把它们处理掉"})
    if len(set(vals)) == 1:
        err("objective", f"所有随机解的目标值都一样（{vals[0]}）——没有东西可优化。检查是否漏用了 x，或惩罚项是否压倒了一切")
        return None, errors, warnings, info
    if per_ms > 5:
        warnings.append({"path": "objective", "msg": f"每次评价约 {per_ms:.1f} 毫秒；种群类算法每代要评价几十次，"
                                                     f"浏览器里还会慢约 2 倍，建议先把迭代次数调小"})
    return out, errors, warnings, info


def up_auto_params(ctx, user_keys):
    """用户的目标函数量级未知，而内核里的温度 t0（模拟退火等）和步长 sigma（连续域）是按内置问题标定的绝对值。
    这里按随机解上目标值的离散程度 / 取值范围换算；用户显式给了的参数不动。"""
    rng = random.Random(97)
    vals = []
    for _ in range(24):
        x = ctx.random(rng)
        try:
            vals.append(ctx.sign * ctx.f(x))
        except _EvalError:
            pass
    out = {}
    if len(vals) >= 2 and "t0" not in user_keys:
        mu = sum(vals) / len(vals)
        sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / len(vals))
        if sd > 0:
            out["t0"] = sd * 0.5
    if getattr(ctx, "lo", None) is not None and "sigma" not in user_keys:
        out["sigma"] = 0.06 * (ctx.hi - ctx.lo)
    return out


# ------------------------------------------------------------------ 内置示例（每种编码一个，也是文档里的范例）

def up_preset(variant="bits", n=None, seed=7):
    rng = random.Random(seed)
    if variant == "bits":
        n = int(n or 30)
        value = [rng.randint(5, 60) for _ in range(n)]
        cost = [rng.randint(3, 30) for _ in range(n)]
        return {
            "variant": "bits", "n": n, "sense": "max",
            "data": {"value": value, "cost": cost, "budget": sum(cost) // 3},
            "objective": ("gain = sum(value[i] * x[i] for i in range(n))\n"
                          "spend = sum(cost[i] * x[i] for i in range(n))\n"
                          "objective = gain - 20 * max(0, spend - budget)"),
        }
    if variant == "perm":
        n = int(n or 12)
        p = [rng.randint(1, 9) for _ in range(n)]
        total = sum(p)
        d = [rng.randint(total // 4, total) for _ in range(n)]
        w = [rng.randint(1, 5) for _ in range(n)]
        return {
            "variant": "perm", "n": n, "sense": "min",
            "data": {"p": p, "d": d, "w": w},
            "objective": ("sum(w[x[k]] * max(0, sum(p[x[j]] for j in range(k + 1)) - d[x[k]]) "
                          "for k in range(n))"),
        }
    if variant == "real":
        # 曲线拟合：y ≈ a·exp(b·t) + c。x = [a, b, c]，目标 = 平方误差和（真值 a=2, b=-0.7, c=0.5，带一点噪声）
        t = [round(0.5 * i, 2) for i in range(14)]
        y = [round(2.0 * math.exp(-0.7 * ti) + 0.5 + rng.uniform(-0.05, 0.05), 4) for ti in t]
        return {
            "variant": "real", "n": 3, "sense": "min", "lo": -5, "hi": 5,
            "data": {"t": t, "y": y},
            "objective": "sum((x[0] * exp(x[1] * t[i]) + x[2] - y[i]) ** 2 for i in range(len(t)))",
        }
    raise ValueError(variant)

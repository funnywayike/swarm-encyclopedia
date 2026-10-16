# ---- 通用编码适配器（2026-10）：任何「连续内核」都能解位向量 / 排列 / 指派向量问题 ----
# 此前每个算法在每种编码上各写一份（bv_* / pk_* / as_* 各约 25 行，逻辑几乎重复）。
# 这里反过来：算法只写一遍连续版，由「视图」把离散问题包成连续域上下文——
#   位向量 bits     实数位置经 sigmoid > 0.5 取 0/1（并修复），评价 ctx.obj
#   排列   perm     实数位置当作随机键（Bean 1994），按键排序得到排列
#   指派   assign   实数位置四舍五入并截断到 0..n_a-1
# 视图自己追踪评价过的最优点：上报的 best 一定等于上报的 best_sol 的目标值（tests/test_consistency.py 的不变式）。


class _DiscView:
    def __init__(self, ctx, mode, rng):
        self._c = ctx
        self.mode = mode
        ref = ctx.random(rng)
        self.dim = self.n = len(ref)
        if mode == "assign":
            na = getattr(ctx, "n_a", None)
            self.na = int(na) if na is not None else (max(ref) + 1 if ref else 2)
            self.lo, self.hi = 0.0, float(max(1, self.na - 1))
        else:
            self.lo, self.hi = -4.0, 4.0
        self.best_val, self.best_tie, self.best_sol, self.best_x = float("inf"), 0.0, None, None

    def random(self, rng):
        return [rng.uniform(self.lo, self.hi) for _ in range(self.dim)]

    def clamp(self, x):
        return [min(self.hi, max(self.lo, v)) for v in x]

    def init_pop(self, p, rng):
        pop = [self.random(rng) for _ in range(int(p.get("n_pop", 30)))]
        return pop, [self.eval(x) for x in pop]

    def _decode(self, x):
        if self.mode == "bits":
            return _bin_rep(self._c, _bin_decode(x))
        if self.mode == "perm":
            return _pk_decode(x)
        return _as_dec(self._c, x, self.na)

    def eval(self, x):
        sol = self._decode(x)
        if self.mode == "perm" and hasattr(self._c, "decode"):  # 图着色 / 装箱：decode 返回 (主目标, 次级打破平局项)
            raw = self._c.decode(sol)
        else:
            raw = self._c.obj(sol)
        val, tie = (raw[0], raw[1] if len(raw) > 1 else 0.0) if isinstance(raw, tuple) else (raw, 0.0)
        if (val, tie) < (self.best_val, self.best_tie):
            self.best_val, self.best_tie, self.best_x = val, tie, list(x)
            self.best_sol = _pk_sol(self._c, sol) if self.mode == "perm" else sol
        return val + 1e-6 * tie

    def state(self, st):
        out = {"iter": st["iter"], "best": self.best_val, "cur": st.get("cur", self.best_val), "best_sol": self.best_sol}
        if self.best_tie:
            out["tie"] = self.best_tie
        return out


def _bridge(cn_fn, mode, tag):
    """连续内核 → 某种编码的离散内核。tag 用来给函数起个可读的名字。"""
    def kernel(ctx, p, rng):
        view = _DiscView(ctx, mode, rng)
        q = dict(p)
        q.setdefault("n_pop", 30)
        for st in cn_fn(view, q, rng):
            yield view.state(st)
    kernel.__name__ = f"_{tag}_{cn_fn.__name__[4:]}"
    return kernel


# 新补全的连续内核：键 → (连续内核, 名称, 一句话说明)
_NEW_CN = {
    "hho": (_cn_hho, "哈里斯鹰 HHO", "逃逸能量切换探索与四种围捕（Heidari 2019）；在最优点恰在原点的函数上有「中心偏好」"),
    "ssa": (_cn_ssa, "麻雀搜索 SSA", "发现者 / 加入者 / 警戒者三角色（Xue & Shen 2020）；有中心偏好"),
    "alo": (_cn_alo, "蚁狮优化 ALO", "蚂蚁围绕蚁狮与精英做随机游走，范围随迭代收缩（Mirjalili 2015）"),
    "boa": (_cn_boa, "蝴蝶优化 BOA", "香味感知 + 全局 / 局部切换（Arora & Singh 2019）"),
    "salp": (_cn_salp, "樽海鞘群 Salp", "领导者绕食物搜索、追随者链式跟随（Mirjalili 2017）"),
    "fpa": (_cn_fpa, "花朵授粉 FPA", "Lévy 全局授粉 + 局部授粉（Yang 2012）"),
    "da": (_cn_da, "蜻蜓 DA", "分离 / 对齐 / 凝聚 / 觅食 / 避敌五种行为加权（Mirjalili 2016）"),
    "mpa": (_cn_mpa, "海洋掠食者 MPA", "三阶段速度比 + FADs 效应（Faramarzi 2020）"),
    "cscrow": (_cn_cscrow, "乌鸦搜索 CSA", "跟踪他人藏食点 + 感知概率（Askarzadeh 2016）"),
    "kh": (_cn_kh, "磷虾群 KH", "诱导 / 觅食 / 扩散三种运动 + 交叉（Gandomi & Alavi 2012）"),
    "bfo": (_cn_bfo, "细菌觅食 BFO", "趋化 / 繁殖 / 消除—扩散（Passino 2002）"),
    "afsa": (_cn_afsa, "人工鱼群 AFSA", "觅食 / 聚群 / 追尾 / 随机四种行为（李晓磊 2002）"),
    "fwa": (_cn_fwa, "烟花算法 FWA", "爆炸火花 + 高斯火花 + 距离轮盘选择（Tan & Zhu 2010）"),
    "ica": (_cn_ica, "帝国竞争 ICA", "同化 / 革命 / 帝国竞争（Atashpaz-Gargari & Lucas 2007）"),
    "sfla": (_cn_sfla, "混合蛙跳 SFLA", "模因分组局部演化 + 整体洗牌（Eusuff & Lansey 2003）"),
    "sos": (_cn_sos, "共生搜索 SOS", "互利 / 偏利 / 寄生三相（Cheng & Prayogo 2014）；有中心偏好"),
    "bbo": (_cn_bbo, "生物地理 BBO", "迁入 / 迁出率接力 + 变异（Simon 2008）"),
    "ais": (_cn_ais, "克隆选择 AIS", "克隆扩增 + 与亲和度成反比的高频变异（de Castro & Von Zuben 2002）"),
}

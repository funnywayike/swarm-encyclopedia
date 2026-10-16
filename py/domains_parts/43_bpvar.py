# ============================================================
# 域：装箱变体家族 bpvar（H3 单域多预设，3 变体）
# ------------------------------------------------------------
#   vsbinpack：变尺寸装箱 VSBPP——箱有多种容量/成本档位，目标=开启箱成本之和
#   binpack2d：二维装箱 2D-BPP——shelf 解码，目标=箱数最少
#   strippack：条带装箱 SPP——单条带 shelf 解码，目标=总高度最小
# 编码=排列，复用 _pm_* 排列内核；解码=First-Fit（1D）/shelf（2D）。
# 目标均 = (主指标, 次级指标) 字典序：1D=(成本,Σ剩余²)；2D=(箱数,Σ余隙²)；
# 条带=(总高,Σ余隙²)。better/diff 主指标强制优先（BIG 足够大）。
# ============================================================

def bpv_make(variant="vsbinpack", n=40, seed=7):
    rng = random.Random(seed)
    if variant == "vsbinpack":
        # 变尺寸箱：3 档（容量/成本递增）；物品重 U[20,100]
        items = [rng.randint(20, 100) for _ in range(n)]
        bin_types = [[80, 1], [150, 2], [220, 3]]
        return {"variant": variant, "n": n, "items": items, "bin_types": bin_types}
    # 2D 变体：物品矩形 w×h ∈ [12,42]²
    items = [[rng.randint(12, 42), rng.randint(12, 42)] for _ in range(n)]
    if variant == "binpack2d":
        return {"variant": variant, "n": n, "items": items, "binW": 70, "binH": 70}
    # strippack：单条带，宽=100，高度最小化
    return {"variant": variant, "n": n, "items": items, "stripW": 100}


class _BPV:
    """装箱变体家族上下文：排列编码 + First-Fit / shelf 解码。"""
    BIG = 10 ** 7

    def __init__(self, problem):
        self.variant = problem["variant"]
        self.items = problem["items"]
        self.n = problem["n"]
        if self.variant == "vsbinpack":
            self.bin_types = problem["bin_types"]
        elif self.variant == "binpack2d":
            self.W = problem["binW"]
            self.H = problem["binH"]
            self.multi = True
        else:  # strippack
            self.W = problem["stripW"]
            self.H = 10 ** 9
            self.multi = False

    def random(self, rng):
        p = list(range(self.n))
        rng.shuffle(p)
        return p

    # ---- VSBPP：变尺寸箱 First-Fit（开最小能容的档位） ----
    def _pack_vsb(self, perm):
        bins = []  # 每箱: [cap_total, remaining, cost, type_idx, [idx...]]
        boxes = []
        for idx in perm:
            w = self.items[idx]
            placed = False
            for b in range(len(bins)):
                cap_tot, rem, cost, ti, pl = bins[b]
                if rem >= w:
                    pl.append(idx)
                    boxes.append({"i": idx, "b": b, "w": w, "x": cap_tot - rem})
                    bins[b][1] -= w
                    placed = True
                    break
            if not placed:
                chosen = None
                for ti, (cap, cost) in enumerate(self.bin_types):
                    if cap >= w:
                        chosen = ti
                        break
                if chosen is None:
                    chosen = len(self.bin_types) - 1
                cap, cost = self.bin_types[chosen]
                bins.append([cap, cap - w, cost, chosen, [idx]])
                boxes.append({"i": idx, "b": len(bins) - 1, "w": w, "x": 0})
        cost = sum(b[2] for b in bins)
        return (cost, sum(b[1] * b[1] for b in bins)), boxes, bins

    # ---- 2D shelf 解码（2D-BPP / SPP 共用）：物品按序落入可容 shelf，
    # shelf 高 = 其内最高物；箱满（纵向超 H）则开新箱（2D）/ 续接 shelf（条带） ----
    def _pack_shelf(self, perm):
        bins = []  # 每箱: [shelf...]；shelf=[w_used, height, [(idx,w,h,x)]]
        boxes = []
        for idx in perm:
            w, h = self.items[idx][0], self.items[idx][1]
            placed = False
            for bi in range(len(bins)):
                bin_ = bins[bi]
                bin_h = sum(s[1] for s in bin_)
                for si in range(len(bin_)):
                    sw, sh, its = bin_[si]
                    new_sh = max(sh, h)
                    if (self.W - sw) >= w and (bin_h - sh + new_sh) <= self.H:
                        x = sw
                        bin_[si][0] = sw + w
                        bin_[si][1] = new_sh
                        bin_[si][2].append((idx, w, h, x))
                        boxes.append({"i": idx, "b": bi, "w": w, "h": h, "x": x, "y": bin_h - sh})
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                new_sh = h
                put = None
                for bi in range(len(bins)):
                    bin_h = sum(s[1] for s in bins[bi])
                    if bin_h + new_sh <= self.H:
                        put = bi
                        break
                if put is None:
                    if self.multi:
                        bins.append([])
                        put = len(bins) - 1
                    else:
                        if not bins:
                            bins.append([])
                        put = 0
                bins[put].append([w, h, [(idx, w, h, 0)]])
                bin_h0 = sum(s[1] for s in bins[put][:-1])
                boxes.append({"i": idx, "b": put, "w": w, "h": h, "x": 0, "y": bin_h0})
        return bins, boxes

    def pack(self, perm):
        if self.variant == "vsbinpack":
            (cost, tie), boxes, bins = self._pack_vsb(perm)
            return (cost, tie), boxes, {"bins": bins, "mode": "vsb"}
        bins, boxes = self._pack_shelf(perm)
        tie = sum((self.W - sw) * sh for bin_ in bins for sw, sh, _ in bin_)
        if self.variant == "binpack2d":
            return (len(bins), tie), boxes, {"bins": bins, "mode": "2d"}
        total_h = sum(sh for bin_ in bins for _, sh, _ in bin_)
        return (total_h, tie), boxes, {"bins": bins, "mode": "strip", "H": total_h}

    def decode(self, perm):
        c, _, _ = self.pack(perm)
        return c

    def solution(self, perm):
        c, boxes, meta = self.pack(perm)
        if meta["mode"] == "vsb":
            conts = []
            boxes_out = []
            rowH = 10
            for b, (cap, rem, cost, ti, pl) in enumerate(meta["bins"]):
                conts.append({"b": b, "x": 0, "y": b * (rowH + 2), "w": cap, "h": rowH,
                              "cap": cap, "cost": cost, "type": ti})
                for bx in boxes:
                    if bx["b"] == b:
                        boxes_out.append({"i": bx["i"], "b": b, "x": bx["x"],
                                          "y": b * (rowH + 2), "w": bx["w"], "h": rowH - 1})
            return {"variant": "vsbinpack", "boxes": boxes_out, "conts": conts}
        # 2D / strip：坐标=问题单位（宽 self.W / 高=各箱叠加）
        conts = []
        boxes_out = []
        yoff = 0
        for b, bin_ in enumerate(meta["bins"]):
            bin_h = sum(s[1] for s in bin_)
            if meta["mode"] == "2d":
                conts.append({"b": b, "x": 0, "y": yoff, "w": self.W, "h": bin_h})
            shelf_y = yoff
            for sw, sh, its in bin_:
                for (idx, w, h, x) in its:
                    boxes_out.append({"i": idx, "b": b, "x": x, "y": shelf_y, "w": w, "h": h})
                shelf_y += sh
            yoff += bin_h + (6 if meta["mode"] == "2d" else 0)
        if meta["mode"] == "strip":
            conts.append({"b": 0, "x": 0, "y": 0, "w": self.W, "h": yoff})
        return {"variant": self.variant, "boxes": boxes_out, "conts": conts}

    def better(self, a, b):
        return a < b

    def diff(self, c1, c2):
        return (c2[0] - c1[0]) * self.BIG + (c2[1] - c1[1])


def _bpv_greedy(ctx, p, rng):
    """确定性构造锚点：多组定向序（VSBPP 按重降序/升序选最优；2D/条带按面积/高/宽降序选最优），
    First-Fit / shelf 解码，作随机基线对照不劣于 best-of-200。"""
    if ctx.variant == "vsbinpack":
        items = ctx.items
        orders = [sorted(range(ctx.n), key=lambda i: -items[i]),
                  sorted(range(ctx.n), key=lambda i: items[i])]
    else:
        items = ctx.items
        orders = [sorted(range(ctx.n), key=lambda i: -(items[i][0] * items[i][1])),
                  sorted(range(ctx.n), key=lambda i: -items[i][1]),
                  sorted(range(ctx.n), key=lambda i: -items[i][0])]
    best_c, best_perm = None, None
    for o in orders:
        c, _, _ = ctx.pack(o)
        if best_c is None or c < best_c:
            best_c, best_perm = c, list(o)
    yield {"iter": 1, "best": best_c[0], "cur": best_c[0], "tie": best_c[1],
           "best_sol": ctx.solution(best_perm)}



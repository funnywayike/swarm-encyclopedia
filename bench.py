# -*- coding: utf-8 -*-
"""算法横向对比：跑一张表出来，直接贴进文章 / 论文 / 商品详情页

用法：
    python bench.py
    python bench.py --sizes 30,60,100 --iters 200
"""
import argparse
import json
import random
import sys
import time

sys.path.insert(0, "py")

from solvers import start, step  # noqa: E402

ALGOS = [
    ("nn", "最近邻NN"),
    ("2opt", "2-opt"),
    ("pso", "离散PSO"),
    ("aco", "蚁群ACO"),
    ("abc", "蜂群ABC"),
    ("fa", "萤火虫FA"),
    ("woa", "鲸鱼WOA"),
    ("ga", "遗传GA"),
    ("sa", "退火SA"),
    ("gwo", "灰狼GWO"),
    ("ts", "禁忌TS"),
    ("de", "差分DE"),
    ("cs", "布谷鸟CS"),
    ("sca", "正弦SCA"),
    ("hho", "哈里斯鹰HHO"),
    ("ils", "迭代局部ILS"),
    ("vns", "变邻域VNS"),
    ("lk", "Lin-Kernighan"),
    ("ba", "蝙蝠BA"),
    ("hs", "和声HS"),
    ("gsa", "引力GSA"),
    ("tlbo", "教与学TLBO"),
    ("bfo", "细菌觅食BFO"),
    ("mfo", "蛾焰MFO"),
    ("fwa", "烟花FWA"),
    ("afsa", "鱼群AFSA"),
    ("cem", "交叉熵CEM"),
    ("ssa", "麻雀SSA"),
    ("alo", "蚁狮ALO"),
    ("boa", "蝴蝶BOA"),
    ("ica", "帝国ICA"),
    ("salp", "樽海鞘Salp"),
    ("sfla", "蛙跳SFLA"),
    ("fpa", "花朵FPA"),
    ("kh", "磷虾KH"),
    ("sos", "共生SOS"),
    ("jaya", "Jaya算法"),
    ("da", "蜻蜓DA"),
    ("mpa", "掠食者MPA"),
    ("cscrow", "乌鸦CSA"),
    ("bbo", "生物地理BBO"),
    ("grasp", "GRASP"),
    ("ais", "克隆AIS"),
    ("eo", "均衡EO"),
    ("ao", "天鹰AO"),
]


def run(cities, algo, params):
    start(json.dumps(cities), algo, json.dumps(params))
    out = []
    while True:
        s = step()
        if s is None:
            break
        out.append(json.loads(s)["best_cost"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", default="30,60,100")
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument(
        "--pure",
        action="store_true",
        help="关掉所有局部搜索，检验「算法自身」是否在优化（防假跑：下降全靠 2-opt 撑着）",
    )
    args = ap.parse_args()

    for n in [int(x) for x in args.sizes.split(",")]:
        rng = random.Random(args.seed)
        cities = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(n)]
        print(f"\n=== 城市数 {n} ===" + ("（裸跑：已关闭全部局部搜索）" if args.pure else ""))
        print(f"{'算法':<10}{'最优值':>10}{'首代':>10}{'耗时(s)':>10}")
        for key, name in ALGOS:
            params = {"max_iter": args.iters, "seed": 42}
            if key == "2opt":
                params = {"max_moves": 1000}
            if args.pure:
                params.update({"ls_every": 0, "local_search": 0.0, "ls_moves": 0})
            t0 = time.time()
            c = run(cities, key, params)
            el = time.time() - t0
            print(f"{name:<10}{c[-1]:>10.1f}{c[0]:>10.1f}{el:>10.2f}")


if __name__ == "__main__":
    main()

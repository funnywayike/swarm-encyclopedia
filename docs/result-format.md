# 结果文件格式（`swarm-result/v1`）

网页上点「导出结果 / 结果 JSON」、命令行 `python swarm.py solve … --out result.json`，得到的是**同一种文件**。
它自带完整实例、算法、种子和参数，所以别人拿到就能复现：

```bash
python swarm.py replay result.json
```

`replay` 会用文件里的实例 / 算法 / 种子 / 参数重新跑一遍，逐点核对收敛曲线，一致就输出「复现成功」，不一致退出码为 1。
（浏览器里的 Python 与本机 Python 对同一份输入给出逐值相同的结果，已用黄金快照核对过。）

## 字段

| 字段 | 含义 |
|---|---|
| `schema` | 固定为 `swarm-result/v1` |
| `generator` | `web`（网页导出）或 `cli`（命令行） |
| `created` | 导出时间（UTC，ISO 8601；命令行导出没有这一项） |
| `domain` / `variant` | 问题域与变体（没有变体时为 `null`） |
| `algo` / `algo_name` | 算法键（`swarm.py list <域>` 可查）与中文名 |
| `seed` | 随机种子 |
| `iters` | 配置的迭代代数（算法的退火 / 步长等进度安排都依赖它） |
| `completed_iters` | 实际跑到第几代。小于 `iters` 说明被中途停止；复现时只核对到那一代 |
| `params` | 算法自己的参数（**不含** `max_iter` 与 `seed`，它们是上面的 `iters` 和 `seed`） |
| `sense` | `min`（越小越好）或 `max`（越大越好）。多目标问题记的是非支配解个数，`max` |
| `best` / `best_solution` | 最终最优值与对应的解（多目标为 `null`） |
| `elapsed_s` | 耗时（秒）；网页的问题域页不记，为 `null` |
| `curve` | 逐代 `[代数, 当时的最优值]` |
| `problem` | 规整后的完整实例，格式同 [data-formats.md](data-formats.md)（TSP 带 `metric` / `matrix` 时一并写入） |
| `extra` | 可选。网页 TSP 页放最近邻基线等附加信息 |

## 也可以当作「问题文件」导入

结果文件里的 `problem` 就是一份合法实例：把它拖进网页的「导入数据 / 导入实例」，或 `python swarm.py solve result.json --algo …`，
都会把它当作问题文件读取（域与变体取自文件）。换一个算法在同一个实例上再跑，是最方便的对比方法。

## 注意

- 网页 TSP 页的曲线值保留 3 位小数，`replay` 核对时允许 0.002 的误差；其余逐值核对。
- 复现的前提是**算法与版本不变**。如果以后算法实现改了（本站有黄金快照守着，改动会在更新日志里写明），旧文件可能对不上——这是预期，不是文件坏了。
- 文件里没有任何个人信息；数据从头到尾只在你的浏览器 / 本机里处理。

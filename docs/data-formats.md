# 数据格式说明（swarm-problem/v1）

怎么把你自己的数据交给本项目的算法去跑。**所有数据只在你自己的浏览器/电脑里计算，不会上传到任何服务器。**

## 一、先看示例

`samples/` 目录里每个问题域、每个变体都有现成的示例文件。最省事的做法：**复制最接近你问题的示例，把里面的数换成你的**。

```
samples/knapsack/knapsack.json   背包（JSON）      samples/knapsack/knapsack.csv   背包（CSV）
samples/sat/sat.cnf              可满足性（DIMACS） samples/graphcolor/graphcolor.col 图着色（DIMACS）
samples/entryseq/vrp.json        车辆路径           samples/kpvar/ssp.json          子集和…
```

网页上也一样：每个问题页的「导入实例」旁有「下载本页示例数据」链接。

## 二、通用外壳

所有 JSON 文件都用同一层外壳，告诉程序「这是什么问题」：

```json
{
  "schema": "swarm-problem/v1",
  "domain": "knapsack",
  "data": { "cap": 50, "items": [[10, 60], [20, 100], [30, 120]] }
}
```

- `domain` 取值见第三节。有「变体」的域（`kpvar` `gcvar` `bpvar` `multiobj` `mocont` `entryseq`）再加一行 `"variant": "ssp"`。
- 外壳可以省略，直接给 `data` 的内容，但需要在页面/命令里另外指明问题域。
- **你不用写的字段**：`n`、`m`、`n_vars`、`n_el` 这类「数量」都从数据里自动数出来；绘图用的坐标缺省时自动布局。写了但写错，会收到提示，而不是崩溃。

## 三、各问题域格式

数字都可以是整数或小数；**编号一律从 0 开始**（DIMACS 文件例外，沿用它自己的从 1 开始，读入时自动转换）。

| 域 `domain` | 必填字段 | 说明 | 规模上限 |
|---|---|---|---|
| `tsp` | `cities`: `[[x,y],…]`，或 `matrix`: n×n 距离矩阵 | 旅行商（对称）。可选 `metric` 指定 TSPLIB 距离（见下）；也可以直接给裸的坐标数组或裸的方阵 | 4–500 城 |
| `knapsack` | `cap`: 容量；`items`: `[[重量,价值],…]` | 0-1 背包。重量必须 > 0 | 1000 件 |
| `multiobj` | `cap`；`items`: `[[重量,目标1,目标2],…]` | 多目标背包。每行 3 列=双目标，4 列=三目标（自动识别） | 1000 件 |
| `binpack` | `cap`: 箱容量；`items`: `[尺寸,…]` | 一维装箱。任何物品不能比箱子大 | 1000 件 |
| `graphcolor` | `edges`: `[[u,v],…]`；可选 `n`、`pos` | 图着色。顶点 0..n-1；自环会被忽略，重复边会被合并 | 500 点 / 5 万边 |
| `setcover` | `sets`: 0/1 矩阵（行=集合，列=元素）；`costs` | 集合覆盖。每个元素必须至少被一个集合覆盖，否则无解 | 25 万格 |
| `sat` | `clauses`: `[[1,-2,3],…]`；可选 `n_vars` | 可满足性。正数=变量，负数=取反，**变量从 1 编号**，不能出现 0 | 1000 变量 / 1 万子句 |
| `qubo` | `Q`: 方阵 | 二次无约束二值优化：最小化 xᵀQx | 200 变量 |
| `gap` | `c`: 代理×任务的成本；`r`: 同形状的资源需求；`cap`: 每个代理容量 | 广义指派。每个任务必须至少有一个代理装得下 | 50 代理 / 500 任务 |
| `uflp` | `f_cost`: 各设施开设成本；`c_cost`: 设施×客户的服务成本；可选 `pos_f` `pos_c` | 无容量设施选址 | 100 设施 / 1000 客户 |
| `custom` | `variant`: `bits` / `perm` / `real`；`n`；`objective`；可选 `data` `sense` `lo` `hi` | **自带问题**：你给解的形状和目标函数，该编码下已有的全部算法可用。详见 [custom-problems.md](custom-problems.md) | bits 1000 · perm 300 · real 100 |
| `mocont` | `variant`: `zdt1` `zdt2` `zdt3` `zdt4` `zdt6` `dtlz1` `dtlz2`；可选 `n`: 决策变量个数 | **连续多目标基准**：函数固定、真前沿有解析式，所以结果里有 IGD 与超体积占比。目标都是越小越好（与 `multiobj` 背包的「越大越好」相反） | 100 个变量 |
| `continuous` | `fn`: 函数名；`dim`: 维度 | 连续函数优化：`sphere` `rosenbrock` `rastrigin` `ackley` `bbob_f1`…`bbob_f6` `griewank` `levy` `schwefel` `zakharov` `dixon_price` `styblinski_tang`。搜索范围由函数决定（各函数的最优值都是 0） | 100 维 |

### 带变体的域

| 域 | 变体 | 一句话 |
|---|---|---|
| `kpvar` | `bkp` `cmp` `dkp` `fractional` `mckp` `mdkp` `mkpm` `qkp` `ssp` `ukp` | 背包的 10 种变体（有界/找零/折扣/分组/多维/二次/子集和/无界…） |
| `gcvar` | `listcolor` `precolor` `edgecolor` `totalcolor` `mis` | 着色变体。`listcolor` 需 `lists`（每点可选颜色），`precolor` 需 `precol`（-1=未预着色）；`edgecolor` / `totalcolor` / `mis` 只需 `edges`，线图与全图由程序推出 |
| `bpvar` | `vsbinpack` `binpack2d` `strippack` | 变尺寸箱 / 二维装箱 / 条带装箱 |
| `multiobj` | `moco` `maop` | 由 `items` 列数自动判断，不必写 |
| `mocont` | `zdt1` `zdt2` `zdt3` `zdt4` `zdt6` `dtlz1` `dtlz2` | 变体决定用哪个测试函数，必须给；其余数据只有 `n` |
| `entryseq` | 68 个 | 车辆路径、指派、调度、选址、图问题、黑箱优化等「词条」，**完整字段清单见 [data-formats-variants.md](data-formats-variants.md)** |

各变体的业务含义见站点里对应的问题页。

## 四、CSV 与 DIMACS

适合在 Excel 里整理数据的问题：

- **背包** `.csv`：第一行注释写容量，之后每行「重量,价值」。表头行可有可无。
  ```
  # cap=50
  weight,value
  10,60
  20,100
  ```
- **装箱** `.csv`：`# cap=箱容量`，之后每行一个物品尺寸。
- **图着色** `.csv`：每行一条边「u,v」（从 0 编号）；可用 `# n=顶点数` 注明孤立点。也直接支持标准的 DIMACS `.col`（`p edge n m` / `e u v`）。
- **QUBO** `.csv`：整个矩阵，每行一行。
- **TSP**：每行「x,y」或「编号,x,y」（编号列必须是 1..n 或 0..n-1，会被丢弃）；n×n 方阵（零对角）按距离矩阵读取。也直接支持 TSPLIB `.tsp`（见下）。
- **可满足性** `.cnf`：标准 DIMACS CNF（`p cnf 变量数 子句数`，每个子句以 0 结尾）。

其他域请用 JSON。

### TSP 的距离怎么算

- 只给坐标：欧氏距离（浮点），在你的原始坐标尺度上计算（页面里的画布缩放只影响画图，不影响路线长度）。
- `metric`（或 TSPLIB 的 `EDGE_WEIGHT_TYPE`）：`EUC_2D`（四舍五入取整）、`CEIL_2D`（向上取整）、`ATT`、`GEO`、`MAN_2D`、`MAX_2D`——按 TSPLIB 95 的规定计算，这样结果才能和公开的最优值对得上。
- `matrix`：直接给距离，必须对称、非负、对角为 0。没给坐标时路线图按圆环布局，只是示意。
- TSPLIB 文件：`TYPE: TSP`；`EXPLICIT` 支持 `FULL_MATRIX` / `UPPER_ROW` / `LOWER_ROW` / `UPPER_DIAG_ROW` / `LOWER_DIAG_ROW` 及 `*_COL` 变体；有 `DISPLAY_DATA_SECTION` 时用它画图。
- **不支持（会明确报错，不会悄悄读错）**：非对称 TSP（`TYPE: ATSP` 或矩阵不对称）——TSP 页的算法用了默认距离对称的算子，请到「问题 ▸ 非对称旅行商 ATSP」页导入（那里也能直接读 `.atsp` 文件）；三维坐标（`EUC_3D` 等）；`CVRP` 等其他 TSPLIB 类型。

## 五、校验与报错

网页的「导入实例」、命令行、Python 里的 `validate` 用的是**同一个校验器**。数据先过校验，错误会指到具体位置，例如：

```
items[3][0]：必须大于 0，收到 -2
edges：顶点编号 5 超出范围 0..4（看起来是从 1 开始编号；本格式顶点编号为 0..n-1）
sets：元素 [2, 7] 没有被任何集合覆盖，问题无解（共 2 个）
```

- **错误**（红）：数据有问题，不会运行。
- 网页上，错误会显示在状态栏下方的红色清单里，同时给出示例数据下载；这些文件也可以直接拖进来用（支持 .json / .csv / .cnf / .col）。
- **警告**（黄）：可以运行，但值得你看一眼，例如「全部物品总重不超过容量，全选就是最优解」「已忽略你写的 n=99，以数据实际长度 12 为准」。

在 Python 里直接用：

```python
import validate
d, data, issues = validate.load(open("my.json", encoding="utf-8").read())
res = validate.validate(d, data)
print(res["ok"], res["errors"], res["warnings"])
problem = res["problem"]      # 规整后的实例，可直接交给引擎
```

## 六、命令行：不开浏览器直接跑

只需要 Python 3.8+，不用安装任何包：

```bash
python swarm.py list                                   # 有哪些问题域
python swarm.py list knapsack                          # 这个域有哪些算法、默认参数
python swarm.py check my.json                          # 只校验，不运行
python swarm.py solve my.json --algo ga --iters 300    # 求解
python swarm.py compare my.json --algos ga,sa,hc       # 同一实例多算法对比（--algos all = 全部）
python swarm.py generate knapsack --opt n=200          # 生成指定规模的随机实例，做对比用
python swarm.py template qap --variant qap > mine.json # 拿示例当起点
```

- `solve` 加 `--out result.json` 保存结果（含最优值、最优解、逐代曲线），加 `--curve curve.csv` 保存收敛曲线。
- 同样的种子得到同样的结果；`--seed` 换种子，`--param 名称=值` 覆盖算法参数（`list` 里能看到可用参数名）。
- CSV / DIMACS 以外没有域信息的文件，加 `--domain`；带变体的域，JSON 外壳里写了 `variant` 就不用再传 `--variant`。
- `samples/` 里的示例只有十来个元素，仅用来展示格式——各算法在这种规模上会打平，做对比请用 `generate` 造大一点的实例。
- 出错时退出码为 2，并在标准错误输出里指出哪里不对（程序不会抛出 Python 堆栈）。

## 七、规模上限为什么存在

算法在你的浏览器里（Pyodide）运行，实例太大会让标签页卡死。上限是保守的经验值；本地用 Python 跑可以改 `validate.LIMITS`。

# 自带问题：写一个目标函数，用全部算法求解

本站没有你要的问题？在 [自带问题页](../problem/custom/) 把它描述出来就行——你只需要给两样东西：

1. **解长什么样**（编码）：
   | 编码 | 解是… | 典型用途 |
   |---|---|---|
   | `bits` 位向量 | n 个 0/1 | 选哪些渠道 / 开哪些仓库 / 用哪些特征 |
   | `perm` 排列 | 0..n-1 的一个顺序 | 作业先后 / 路线顺序 / 装配次序 |
   | `real` 实数向量 | n 个在 `lo~hi` 之间的数 | 参数调优 / 曲线拟合 / 函数最小化 |
2. **好坏怎么算**（目标函数）：一段表达式，输入解 `x`，输出一个数。

之后，这个编码下已有的全部算法（位向量 21 个、排列 22 个、实数 21 个）都能直接跑你的问题，收敛曲线、结果导出、复现都是现成的。
**算法不是为你的问题写的**，它们只通过「编码」和「目标值」与问题打交道，所以能原样使用——也因此不保证每一个都适合你的问题，多挑几个比一比。

## 一个实例长这样

```json
{
  "variant": "bits",
  "n": 14,
  "sense": "max",
  "data": { "value": [...], "cost": [...], "budget": 120 },
  "objective": "gain = sum(value[i] * x[i] for i in range(n))\nspend = sum(cost[i] * x[i] for i in range(n))\nobjective = gain - 20 * max(0, spend - budget)"
}
```

| 字段 | 含义 |
|---|---|
| `variant` | 编码：`bits` / `perm` / `real` |
| `n` | 解的长度（bits ≤ 1000，perm ≤ 300，real ≤ 100） |
| `sense` | `min` 越小越好（默认）或 `max` 越大越好 |
| `lo`, `hi` | 仅 `real`：所有维度共用的取值范围 |
| `data` | 数据表：名字 → 数字或数字数组（最多三层嵌套，总量 ≤ 25 万个数）。目标函数里直接用名字读取 |
| `objective` | 目标函数（下面详述） |

也可以用 swarm-problem/v1 信封包起来（`{"schema": "swarm-problem/v1", "domain": "custom", "variant": "bits", "data": {...}}`），
或者直接把网页导出的**结果文件**当作问题文件导入——结果里就带着完整的问题定义。

## 目标函数怎么写

写法像 Python 的**表达式**：可以有几行 `名字 = 表达式` 的中间量，最后一行直接是目标值（或写成 `objective = …`）。

- **可用**：数字；`+ - * / // % **`；比较；`and or not`；`a if 条件 else b`；下标 `x[i]`、`dist[i][j]`；
  列表与生成式 `sum(w[i] * x[i] for i in range(n))`（`if` 过滤也行）。
- **可用函数**：`sum min max abs len range sorted round float int any all sqrt exp log sin cos floor ceil zip enumerate`；常数 `pi`、`e`。
- **不可用**：`import`、点号属性（`x.append`、`math.sqrt`）、字符串、lambda、字典 / 集合、`for` / `while` / `def` 语句。
  循环最多嵌套两层（生成式里的每个 `for`、生成式套生成式，都算一层）。
- **约束用罚函数**：违反约束就加「大数 × 违反量」，如 `gain - 100 * max(0, spend - budget)`。罚得太轻，算法会专挑违反约束的便宜解；太重，可行与不可行之间就没有梯度了。

**为什么限制这么多？** 目标函数不会被当作代码执行。本站先把它解析成语法树、逐个节点检查，只放行上面这些；检查通过后才编译成只会做算术的小程序，
并且每次评价有迭代次数、`range` 大小、整数位数的上限——写出会卡死标签页的式子会得到一条明确的错误，而不是一个卡死的页面。

**检查并载入时会试算**：在 30 个随机解上求值，立刻告诉你：有没有写错名字、下标是否越界、会不会出现 nan / 除零、目标值是不是处处相同（没有东西可优化）、单次评价耗时是否过长。

## 五个例子

下面每一个都在 [`docs/custom-examples.json`](custom-examples.json) 里有完整数据，随测试一起验证。

### 1. 预算内选渠道（bits，最大化）
```objective:channels
gain = sum(value[i] * x[i] for i in range(n))
spend = sum(cost[i] * x[i] for i in range(n))
objective = gain - 20 * max(0, spend - budget)
```

### 2. 特征选择：恰好选 k 个最有用的（bits，最小化）
```objective:features
-sum(gain[i] * x[i] for i in range(n)) + 3 * abs(sum(x) - k)
```

### 3. 作业顺序：总加权延误最小（perm）
`x[k]` 是排在第 k 位的作业；`p` 加工时间、`d` 交期、`w` 权重。第 k 位的完成时间 = 前 k+1 个作业加工时间之和。
```objective:jobs
sum(w[x[k]] * max(0, sum(p[x[j]] for j in range(k + 1)) - d[x[k]]) for k in range(n))
```

### 4. 路线：访问所有点再回到起点的总距离（perm）
`dist` 是距离矩阵；`(i + 1) % n` 让最后一个点回到起点。这就是旅行商问题——只是这里的距离是你自己给的。
```objective:route
sum(dist[x[i]][x[(i + 1) % n]] for i in range(n))
```

### 5. 曲线拟合 y = a·e^(b·t) + c（real）
`x = [a, b, c]`，范围 −5~5；数据 `t`、`y` 是观测点。目标 = 平方误差和。
```objective:fit
sum((x[0] * exp(x[1] * t[i]) + x[2] - y[i]) ** 2 for i in range(len(t)))
```

## 命令行

```bash
python swarm.py template custom --variant bits > my.json      # 取一份示例，改成你的
python swarm.py check my.json                                   # 只检查（含试算）
python swarm.py solve my.json --algo ga --iters 200 --out result.json
python swarm.py replay result.json                              # 复现并核对曲线
```

需要完整 Python（递归、复杂状态）时，把目标函数写成一个文件，**只在你自己的电脑上**运行：

```python
# obj.py
def objective(x, data):
    return sum(data["value"][i] * x[i] for i in range(len(x)))
```
```bash
python swarm.py solve my.json --domain custom --variant bits --objective-py obj.py --algo ga
```

这是在你的电脑上运行你自己的代码，没有任何沙箱；因此浏览器页面**不开放**这个功能。结果文件里会带上这段代码，
别人复现时 `swarm.py replay` 会先把代码全文打出来，要加 `--trust-code` 才会运行。**不要运行你没读过的别人的结果文件。**

## 常见问题

- **温度、步长要自己调吗？** 不用先调。模拟退火的初始温度、连续算法的步长是按内置问题标定的绝对数值，你的目标函数量级未知，
  所以运行时会按「随机解上目标值的离散程度 / 取值范围」自动换算（状态栏会告诉你换成了多少）；想自己定就在算法参数里填，填了就不再改。
- **结果能和文献对照吗？** 不能。结果只对你写的公式成立，页面和结果文件里都标着「自定义模型」。
- **目标函数里能用随机数吗？** 不能（没有随机函数）。同一个解必须永远得到同一个目标值，否则复现和对比都没有意义。

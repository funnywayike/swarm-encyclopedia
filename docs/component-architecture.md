# 组件化组合架构 v3（S7 设计方案）—— 算法 = 模块组合

> 状态：**待用户批准**。批准前不动代码。
> 回答用户核心问题：「所有算法都实现了吗」→ 没有。44 个有可跑求解器；F6-F9 的 14 条
> （Memetic / SAEA / 超启发式等）目前只是词条。本方案让"新算法"变成"组装模块清单"，
> 是低成本收编这些家族的正道。

## 1. 三层模块分类（核心设计）

| 层 | 能否自己跑 | 现状 | 目标 |
|---|---|---|---|
| **L-solver 可运行算法** | ✅ 独立运行 | 44 个 BaseSolver（TSP）+ 25 个域算法（domains.py） | 保持不动（重写会改 RNG 顺序 → bench 数值全变） |
| **L-comp 纯组件** | ❌ **不能自己跑** | components.py 17 个 + domain_components.py 12 个函数 | 收编进统一注册表 v2，带 schema 元数据 |
| **L-recipe 配方（组合件）** | ✅ 由组合引擎跑 | ❌ 无 | 新增：JSON 声明式组装，是"新算法"的低成本路径 |

**纯组件的"不能自己跑"必须显式建模**（用户点名的关键点）：
每个组件声明 `slots`（可插槽位）——例如「2-opt 局部搜索」的槽位是
`{pipeline: after_generation}`、「OX 交叉」的槽位是 `{pipeline: crossover, encoding: permutation}`。
组件页上不能跑的组件会标注「⚠ 纯组件——需宿主算法」，并显示它能插进哪些槽。

## 2. 组件注册表 v2 schema（统一元数据）

```json
{
  "id": "ox_crossover",
  "kind": "crossover",            // init|encoding|crossover|mutation|neighborhood|
                                  // selection|replacement|repair|local_search|
                                  // terminator|param_controller|meta
  "io":  {"in": "permutation×2", "out": "permutation"},
  "slots": {"pipeline": "crossover", "encodings": ["permutation"]},
  "params": {"gap": "1..n/2"},
  "complexity": "O(n)",
  "source": "Goldberg 1985（顺序交叉正典）",
  "used_by": ["ga-tsp", "tlbo-tsp", "..."],   // 派生：从代码 import 关系生成
  "composable": false             // false = 纯组件（不能独立运行）
}
```

`kind` 共 12 类槽位（上面 kind 注释行）——**每一类都是组合引擎的一个管线插槽**。

## 3. 配方引擎（组合件如何跑）

```json
{
  "id": "memetic-recipe",
  "name": "Memetic GA（组合示范）",
  "lineage": {"family": "F6", "based_on": "ga-tsp"},
  "init":       {"use": "nn_seeding", "params": {"starts": 8}},
  "selection":  {"use": "tournament", "params": {"k": 3}},
  "crossover":  {"use": "ox_crossover"},
  "mutation":   {"use": "reverse_mut", "params": {"pm": 0.05}},
  "replacement":{"use": "generational", "params": {"elite": 2}},
  "local_search": {"use": "two_opt", "params": {"every": 5}, "target": "gbest"},
  "terminator": {"use": "max_iter", "params": {"iters": 200}}
}
```

组合引擎 = 一个通用循环解释器（Pyodide 内嵌，同现方案）：
按管线槽位顺序调用组件 → 每代 emit 与现有求解器**完全相同的
step JSON**（iter/best/cur/tie）→ 前端图表零改动复用。

**Memetic / 超启发式选择式 / DE 变体这类 F6-F9 词条，从此 = 一份配方 + 一条注释**，
不用手写 solver 类。

## 4. 用户没点名、我补充考虑的六件事

1. **IO 类型校验**：排列算子喂给二进制算法 = 非法配方。引擎加载配方时按
   `slots.encodings` 校验整条管线，不合法直接拒绝并指出第一个错位组件。
2. **组件出处即批评史**：每个组件带正典引用（如 OX=Goldberg 1985）——组件百科页
   自动获得「组件 × 出处」列，与元层批评史卖点（"360 个隐喻可归约为少数组件模式"，
   de Armas 2021）直接呼应，这是站点差异化叙事。
3. **RNG 管线统一**：配方引擎用单一 `random.Random(seed)` 顺序调用组件——组件不得
   自建随机源，保证任意配方可复现（与 bench 同标准）。
4. **修复算子的条件插桩**：`repair` 槽位只在有约束的问题域生效；无约束配方带
   repair = 引擎警告而非报错（教学场景宽容）。
5. **组件单测**：现有 45 pytest 只测算法整体；新增每组件 IO 契约测试
   （给定输入分布 → 断言输出合法性：排列无重复、二进制长度、修复后可行）。
6. **X 矩阵从派生数据生成**：X2（算法×编码）/ X3（问题×算子）目前手写——注册表 v2
   后由 `used_by` / `slots` 自动派生，手写矩阵退役为校验基准。

## 5. 施工分批（每批独立验收，不一次吞下）

| 批 | 内容 | 验收 |
|---|---|---|
| **S7-A 注册表 v2** | 29 个现有组件收编 + 补齐元数据（kind/io/slots/source）；组件百科页升级：按 12 槽位分组、纯组件标注、组件×算法使用矩阵 | selfcheck 新增注册表完整性检查 |
| **S7-B 配方引擎** | `py/recipe.py` 通用解释器 + 3 个示范配方（memetic / 稳态替换 GA / ILS 配方）+ 配方页 `/algo/f6-hybrid/memetic-recipe/`（标注「组合算法」徽章） | 配方冒烟：单调不回升 + 与对应手写 solver 数量级一致 |
| **S7-C 前端组合器**（可选，招牌交互） | 页面上勾选模块 → 实时拼配方 → 本地跑（Pyodide 已支持） | 人工交互测试 |

## 6. 明确不做（防膨胀）

- 不重写现有 44 个 solver（数值冻结）
- 配方引擎不做通用 DAG 流程图——只做固定管线（init→selection→crossover→mutation→
  replacement→local_search→terminator 七槽），够覆盖教科书谱系且可解释
- F6 的 SAEA / Matheuristic（需 MIP 求解器）/ FunSearch 类（需 LLM）**不适合**前端
  配方化——词条保持词条，标注「重型框架，仅词条」

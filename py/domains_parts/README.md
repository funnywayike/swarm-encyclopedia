# 域引擎分块（py/domains_parts/）

问题域引擎的源码按主题拆成这些文件，**文件名顺序就是执行顺序**。它们在同一个名字空间里执行：

- 本地：`py/domains.py` 把它们依次编译、执行进自己的模块名字空间（所以 `import domains` 和原来一样）。
- 浏览器：`build_pages.py` 把它们按同样的顺序拼成 `js/domains_src.js`，在 Pyodide 里一次执行。

所以后面的块可以直接用前面块里的名字；**前面的块不能引用后面块里的名字**（除非是在函数体里、调用发生在全部装载之后）。
顶层名字不能和别的模块（`entryseq.py`、`userproblem.py`、`mocont.py`…）或别的块重名——`tests/test_browser_namespace.py` 会查。

| 块 | 内容 |
|---|---|
| `00_header` | 模块说明、标准库导入、对其它模块（`domain_components` `entryseq` `userproblem` `mocont`）的 `try: from … import …` |
| `10_knapsack` | 0-1 背包（实例、上下文、内核）|
| `20_continuous` | 连续函数优化（基准函数表 `FUNCS`、实数编码内核）|
| `30_multiobj` | 双 / 三目标背包（NSGA-II、MOEA/D、NSGA-III 小生境……）|
| `40_perm_kernels` | 排列编码通用算法库（图着色、装箱、各排列变体共用）|
| `41_graphcolor` `42_binpack` `43_bpvar` | 图着色、装箱、装箱变体家族 |
| `50_bin_kernels` | 二进制编码通用内核（集合覆盖 / QUBO / UFLP 共用）|
| `51_bv_adapters` `52_assign_adapters` `53_continuous_binarised` | 把连续系算法适配到位向量 / 指派向量的适配层 |
| `60_setcover` … `64_uflp` | 集合覆盖、SAT、QUBO、广义指派、设施选址 |
| `70_kpvar` `71_gcvar` | 背包家族、着色家族（单域多变体）|
| `80_registries` | 算法注册表与各域默认参数（`_KS_ALGOS`、`_BP_ALGOS`、连续函数扩容……）|
| `85_entryseq_and_mounts` | 词条域（entryseq）的算法族与各域的「挂载」（把某族内核挂到某域的注册表里）|
| `90_domains_and_api` | `_DOMAINS` 总表与对外接口：`domain_list` / `domain_preset` / `domain_start` / `domain_step` |

## 新增一个域

1. 实例生成 + 上下文类 + 内核：新起一个带编号的块（编号决定它在哪些块之后执行），或者像 `entryseq.py` / `mocont.py` 那样放进独立文件（先看 `python tools/new_problem.py --help`）。
2. 在 `90_domains_and_api` 的 `_DOMAINS` 里登记，并在 `domain_preset` / `domain_start` 里加分派。
3. `py/registry.py` 里登记变体，`py/validate.py` 里加校验。
4. `python tools/golden.py` 看有哪些新增（只应有新增），确认后 `--update`。

不确定时运行 `python tools/new_problem.py`：它会按你选的类型生成骨架和对应的测试。

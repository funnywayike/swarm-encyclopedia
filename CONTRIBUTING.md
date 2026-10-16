# Contributing / 贡献指南

**In short (English).** This is a static site: Python runs in the browser through Pyodide, and the same sources run under plain
CPython for tests. To add a problem or an algorithm, start from the scaffolds — `python tools/new_problem.py …` and
`python tools/new_algorithm.py …` — fill in the real model, and make the checks pass: `python build_pages.py`,
`python selfcheck.py`, `python -m pytest tests`, and `python tools/golden.py` (the golden snapshot may only gain entries, or change
for a reason you can explain in `CHANGELOG.md`). The rules that matter most are in section 5: fidelity labels, "the reported best must be
reproducible from the reported solution", and the shared-namespace rule for browser code.

下面是中文正文。

---

## 一、本地环境

| 需要 | 用途 |
|---|---|
| Python 3.12 及以上（测试矩阵：3.12 / 3.13 / 3.14） | 引擎、测试、构建脚本（引擎只用标准库）|
| `pip install pytest` | 测试 |
| Node.js 18 及以上 | 构建后的页面脚本语法检查（`tests/test_inline_scripts.py`）、Pyodide 一致性检查 |
| 一个现代浏览器 | 看页面。**必须经 http 访问**：`python serve.py`（不要 `python -m http.server`——它在 Windows 上把 `.mjs` 标成 `text/plain`，浏览器会拒绝加载）|

Pyodide 运行时随仓库放在 `vendor/pyodide/`，页面不依赖任何外部 CDN。

## 二、仓库地图

**源码（手写，改这里）**

| 路径 | 内容 |
|---|---|
| `py/solvers.py` | TSP 求解器（`BaseSolver` 子类）与 TSP 协议（`start` / `step` / `run_all`）|
| `py/domains.py` + `py/domains_parts/` | 其它问题域的引擎。`domains.py` 只是装载器，代码在按编号排序的分块里，**共用一个名字空间**，见 `py/domains_parts/README.md` |
| `py/entryseq.py` | 「词条」问题域：一个变体 = 一个 `@_maker` 实例生成器 + 一个 `@_objective` 目标函数 |
| `py/mocont.py`、`py/userproblem.py` | 连续多目标基准（ZDT/DTLZ）、「自带问题」|
| `py/registry.py` | 域 / 变体清单的唯一来源；`py/validate.py` 是上传数据的校验器 |
| `data/*.json` | 页面内容的单一事实来源（算法、问题、映射、家族……）。页面只是它们的渲染 |
| `js/`、`css/` | 前端（`domain_page.js` 是问题页的画图与交互）|
| `build_pages.py`、`pages_*.py` | 页面生成器 |
| `tests/`、`tools/golden.py` | 测试与黄金快照 |

**生成物（不要手改，改源码后重新构建）**：`algo/`、`problem/`、`compare/`、各 `index.html`、`sitemap.xml`、`js/domains_src.js`、
`js/solvers_src.js`、`py/taxonomy.py`、`samples/`、`docs/data-formats-variants.md`。运行 `python build_pages.py` 重新生成。

## 三、日常命令

```bash
python build_pages.py                 # 重建页面和浏览器里用的引擎源码
python selfcheck.py                   # 站点自检（链接、页面结构、数据一致性），要跑全绿
python -m pytest tests -q -m "not slow"   # 快速测试（约 1.5 分钟）
python -m pytest tests -q             # 全部测试（约 10 分钟）
python tools/golden.py                # 把全部「域 × 变体 × 算法」用固定种子重跑，与黄金快照比对
node tools/pyodide_parity.mjs         # 在真实 Pyodide 里把黄金快照重跑一遍（几分钟）
python serve.py                       # 本地预览
```

**黄金快照**（`tests/golden/results.json`）是改动的安全网：不该改变算法结果的改动之后（拆文件、改注册表、换分类……），
`golden.py` 必须报告「新增 0 消失 0 数值变化 0」。新增问题 / 算法会有「新增」，这没问题；出现「消失」或「数值变化」
就要能解释为什么，并写进 `CHANGELOG.md`，然后才 `python tools/golden.py --update`。

## 四、新增一个问题或算法

### 新增问题（词条）

```bash
python tools/new_problem.py myprob --encoding perm --title "我的问题"     # perm 排列 / bits 位向量 / real 实数向量
```

它会在 `py/entryseq.py`、`data/problems.json`、`pages_domains.py`、`tests/` 里生成可运行的**占位**实现。然后：

1. 把占位的实例生成与目标函数换成真实模型（搜索 `TODO（占位）`）。目标函数一律「越小越好」，最大化问题取负。
2. 需要在页面上画出解时，加一个 `@_detail('myprob')`，并在 `js/domain_page.js` 里加画法（没有时用通用画法）。
3. 补 `data/problems.json` 里的模型 / 与相邻问题的差异 / 求解思路 / **至少 3 条可核实的文献**。
4. **用独立的实现核对你的目标函数**：小规模穷举、已知最优值、或文献里的数值——不要只比较算法自己上报的数字。
5. 运行 `python tools/gen_samples.py`、`python build_pages.py`、`python tools/check_citations.py`（需联网）、`python tools/golden.py`（确认只有新增后加 `--update`）。

`tests/test_no_placeholders.py` 会让全部测试失败，直到所有 `TODO（占位）` 都被换掉——占位的东西发布不出去。

### 新增算法

```bash
python tools/new_algorithm.py myalgo --title "我的算法" --family F2
```

它会生成 `py/solvers.py` 里的求解器占位、`data/algos.json` 与 `data/mapping.json` 的条目和测试骨架。收录的最低要求：

- **TSP 上能跑**，并满足契约：每代 `yield IterationState`，`best_cost` 单调不增，`best_tour` 的长度等于上报的 `best_cost`；
- **至少再接入一种别的编码**（排列 / 位向量 / 实数向量问题）。排列问题最省事的是给算法写一个连续版本，经「随机键」桥接（`py/domains_parts/` 里的 `pk_*`）；位向量、实数向量问题在对应编码的算法族里加一个内核；
- 在本站的问题上**必须明显优于随机搜索**（`tests/test_domains.py`、`tests/test_smoke_matrix.py` 里的门），不是只会随机乱走；
- 结果进黄金快照。

## 英文界面（中英双语）

站点有中文和英文两套界面。页面本体是中文（构建产物），英文由浏览器里的 `js/i18n.js` 用词典翻译（`?lang=en`，或浏览器语言不是中文时默认英文）。
**新增或改了页面上可见的中文，就要同时补英文**，否则 `tests/test_i18n.py` 会失败：

| 内容 | 英文放在哪里 |
|---|---|
| 按钮、菜单、状态栏、参数说明、图表说明等界面文字 | `data/i18n/NN_*.json` 的 `strings`（键 = 页面上的中文，规整空白后整句匹配；`{n}` = 一串数字，`{*}` = 任意文字，译文里按顺序用 `{n}` / `{*}` 或 `{1}`…引用；带标签的句子在译文里写不带属性的 `<b>`、`<a>`，页面上原来的元素会被沿用）|
| 算法 / 问题 / 家族 / 元层页的英文名与摘要 | `data/algos.json`、`data/problems.json`、`data/families.json`、`data/meta.json` 里的 `name_en`、`tagline_en`、`summary_en` |
| 关键页的 `<title>` / `<h1>` | `data/i18n_pages.json` |

```bash
python build_pages.py                                 # 把词典合成 js/i18n_en.js
python tools/i18n_extract.py --pages guide/ --list 30 # 看某些页面还有哪些中文没有英文
python tools/i18n_extract.py --min-pages 10           # 在 ≥10 个页面出现的共用界面文字
python tools/i18n_dedupe.py                           # 同一个键出现在多个词典文件时去重
python -m pytest tests/test_i18n.py -q
```

深度正文（每个问题页 / 算法页里很长的说明）目前只有中文：这是已知范围，不是漏译；页面顶部会自动出现一条说明。

## 五、规矩

1. **保真度标签。** 每个词条问题都要在 `@_objective(fidelity=…)` 里自述：`standard`（与教科书 / 文献定义一致，数值可与文献对照）、
   `simplified`（问题是真的，但做了教学级简化）、`illustrative`（只借名字演示形态）。非 standard 必须写一句说明与标准定义的差异——页面和上传校验都会显示它。不要把示意模型标成标准。
2. **上报的 best 必须能由上报的解重算出来**，且沿代数只降不升（`tests/test_consistency.py` 对每个「域 × 变体 × 算法」检查）。
   这条规矩是用血换来的：曾有二十多个算法内核一直在上报自己达不到的成绩，而且看起来比别的算法都好。
3. **浏览器里所有源码拼进同一个名字空间执行。** 所以：不要写带别名的导入（`from x import a as b` 在浏览器里不会绑定 `b`）；
   顶层名字不能和别的模块重名（后面的悄悄覆盖前面的）；`if __name__ == "__main__"` 自测块要有平台判断（`sys.platform != "emscripten"`）。
   `tests/test_browser_namespace.py` 会在干净子进程里按浏览器的方式执行拼接源码，并检查这三件事。
4. **别用批量改写工具碰代码形态的字符串。** 页面模板里嵌着 JavaScript；曾有一次文案整改把字符串里的 `()` 全删了，
   全站内联脚本因此全是语法错误，而原有测试没人发现。现在 `tests/test_inline_scripts.py` 会用 Node 解析每个页面的每段内联脚本。
5. **引用必须真实。** `python tools/check_citations.py` 用 Crossref / arXiv 核对；报告里的 `MISMATCH` 必须修，`NOMATCH`（书、会议论文、中文文献）需要人工核实。
6. **不要手改生成物**，也不要把本机路径、个人信息写进仓库。

## 六、提交前清单

- [ ] `python build_pages.py` 无报错，`python selfcheck.py` 全绿
- [ ] `python -m pytest tests -q` 全绿（没有残留的 `TODO（占位）`）
- [ ] `python tools/golden.py`：只有「新增」；有「消失 / 数值变化」的已经在 `CHANGELOG.md` 里解释，并 `--update`
- [ ] 新增 / 改动的文献已用 `tools/check_citations.py` 核对
- [ ] 改了页面脚本或引擎：在浏览器里把受影响的页面真点一遍，看控制台没有报错（「页面能打开」不等于「脚本能跑」；清单见 [docs/browser-checklist.md](docs/browser-checklist.md)）
- [ ] `CHANGELOG.md` 记了这次改动里会改变结果的部分
- [ ] 页面上新增 / 改动的可见文字有英文（`python -m pytest tests/test_i18n.py -q` 通过）

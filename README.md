# Swarm-Intelligence Algorithm Encyclopedia · 群智能算法百科

**An interactive encyclopedia of swarm-intelligence and metaheuristic algorithms, with a problem library you can run them on — all in the browser, no backend.**

- **45 algorithms × 100+ problem pages.** Each algorithm page explains origin, theory, known criticism, variants and
  references; each problem page gives the model, complexity, standard benchmarks and what this site actually implements.
- **Everything runs locally.** Python (via [Pyodide](https://pyodide.org)) executes in your browser. Nothing is uploaded; the
  runtime ships in `vendor/pyodide/`.
- **Bring your own data.** Upload a JSON/CSV file in the documented format (or paste a problem on the "custom problem" page), pick
  an algorithm and a seed, and export the result — it carries the instance, seed, parameters and solution, so anyone can
  replay it (`python swarm.py replay result.json`). A standard-library command-line tool does the same without a browser.
- **Honest about its limits.** Every problem carries a fidelity label (`standard` / `simplified` / `illustrative`). The
  "which algorithm works on which problem" matrix only credits an algorithm when it beats random search at the **same
  number of evaluations**; cells that failed that test are withdrawn and listed, not hidden.
- **Reproducible.** Fixed seeds, a golden snapshot of every domain × variant × algorithm (`tests/golden/results.json`), and a
  check that the browser engine reproduces it value for value.

- **Research map and review library.** Follow 20 research routes from origins and turning points to recent work and evidence boundaries. Sixteen turning-point dossiers explain the research problem, mechanism change, date meaning and source authors; timeline filters distinguish mechanisms, infrastructure, domain tools, syntheses and frontier work. Explore 80 dated map entries, teams and applications, with 149 review/tutorial/methodology references and a 42-topic coverage ledger. 58 items have abstract/section reading notes; 91 remain bibliographic entries. Source reading levels, shared authors and version relationships are explicit. See [research map](https://funnywayike.github.io/swarm-encyclopedia/meta/research-map/); this is a representative guide, not an exhaustive systematic review.

```bash
python serve.py          # then open http://127.0.0.1:8000/   (Python 3.12+, standard library only)
```

> Open the site over **http**, not `file://` — the Python runtime cannot start from a local file. On Windows use
> `serve.py` (or `start_server.bat`) rather than `python -m http.server`, which mislabels `.mjs` files.

**Languages.** The site has a Chinese and an English interface (switch with the 中 / EN button; browsers whose language is not
Chinese get English by default). Everything you operate — menus, buttons, status messages, parameter descriptions, chart
captions — and the key pages (home, quick start, comparison, problem library, custom problems, reductions, encyclopedia overview)
are fully translated; every algorithm and problem page also starts with an English summary. The long explanatory bodies of
the individual pages are **Chinese only** for now, and a note at the top of such a page says so. Translations are plain JSON
(`data/i18n/`), so improving them is an easy first contribution. License: MIT ([LICENSE](LICENSE)); the bundled Pyodide runtime is MPL-2.0
([THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)).

**Read before you cite it:** the problem models are teaching-and-comparison models, not industrial solvers; "beats random
search" is a low bar; and the problem pages have not yet had an independent review by domain experts. Details in
"已知局限" below.

---

## 中文说明

### 这是什么

一个纯静态的「群智能 / 元启发式算法百科」：

- **算法轴**：45 个算法，按家族分类，每个算法一页——来历、原理、理论性质与已知批评、常见变体、延伸文献，以及可调参数的在线演示。
- **问题轴**：100 多个问题页（TSP、背包、连续函数、多目标、图着色、装箱、车间调度、选址、路径、网络流、SAT / QUBO 等），
  每页写清模型、复杂度、标准基准，以及**本站实际实现的是哪一种、与标准定义差在哪**。
- **映射轴**：「哪个算法在哪个问题上有用」——只有在**同等评估次数**下稳定胜过随机搜索的格子才记为有效；没通过的格子
  会被撤下并公开登记。
- **方法论**：算法同名异物、隐喻批评、基准与评价方法的批评史等专题页。

所有算法在浏览器里的 Pyodide 中运行，页面上有实时动画与收敛曲线。没有后端，没有账号，不上传任何数据。

站点有中文和英文两套界面（右上角 中 / EN 切换）：所有操作界面与关键页整页有英文，每个算法页 / 问题页顶部有一段英文摘要；各页很长的说明正文暂时只有中文，页面顶部会注明。翻译就是 `data/i18n/` 里的 JSON 词典，欢迎帮忙改进。

### 怎么用

1. **本地预览**：`python serve.py`（Python 3.12+，只用标准库），浏览器打开 `http://127.0.0.1:8000/`。
   **不能双击 `index.html`**（`file://` 下 Pyodide 无法启动）；Windows 上也别用 `python -m http.server`（会把 `.mjs` 标成
   `text/plain`）。`start_server.bat` 双击即可。
2. **部署**：任何静态托管都行（GitHub Pages、Netlify……），把仓库根目录当作站点根。所有内链都是相对路径，放在子路径下也能用。
3. **用自己的数据**：在问题页上传文件，或用「自带问题」页。各问题的数据格式见 [docs/data-formats.md](docs/data-formats.md) 与
   [docs/data-formats-variants.md](docs/data-formats-variants.md)；页面上的样例链接给出可直接修改的文件。数据先经
   `py/validate.py` 校验，不合格会指出是哪一项。
4. **命令行**：不开浏览器也能用——`python swarm.py list`、`template`、`generate`、`check`、`solve`、`compare`、`replay`
   （纯标准库）。
5. **复现结果**：导出的结果文件格式见 [docs/result-format.md](docs/result-format.md)，里面有完整实例、算法、种子和参数；
   `python swarm.py replay result.json` 会重跑并逐点核对收敛曲线。

### 仓库结构

| 路径 | 内容 |
|---|---|
| `py/` | 引擎（求解器、问题域、校验器）。浏览器里跑的和测试里跑的是同一份源码 |
| `data/` | 页面内容的单一事实来源（算法、问题、映射、家族……） |
| `js/`、`css/` | 前端 |
| `build_pages.py`、`pages_*.py` | 页面生成器（页面是生成物：改了源码就重新构建） |
| `tests/`、`tools/` | 测试、黄金快照、公平预算基准、引用核对等工具 |
| `docs/` | 数据格式、结果格式、自带问题等使用文档 |
| `vendor/pyodide/` | 随仓库放的 Pyodide 运行时，页面不依赖外部 CDN |

### 开发

```bash
python build_pages.py                       # 重建页面与浏览器引擎源码
python selfcheck.py                         # 站点自检
python -m pytest tests -q -m "not slow"     # 快速测试
python tools/golden.py                      # 与黄金快照比对
node tools/pyodide_parity.mjs               # 在真实 Pyodide 里重跑黄金快照
```

默认构建不写 `canonical` / `og:url` / `og:image` / `sitemap.xml`（构建时不知道你的部署地址）。需要的话在构建时指定站点根：
`SWARM_SITE_URL=https://<用户名>.github.io/<仓库名> python build_pages.py`。

新增问题或算法的流程、约定与提交前清单见 [CONTRIBUTING.md](CONTRIBUTING.md)；会改变结果的改动记在 [CHANGELOG.md](CHANGELOG.md)。

### 已知局限（引用前请读）

- 本站的问题实现是**教学与对比用的模型**，不是工业求解器。每个问题页都标了保真度；`simplified` / `illustrative` 的不能当作
  与文献数值可比的基准。
- 「胜过随机搜索」是一条**低门槛**：它说明算法在这个模型上确实在搜索，不说明它优于该问题的专用算法。专用算法（如 LKH 之于
  TSP、CP-SAT 之于调度）在多数问题上远强于这里的任何元启发式。
- 覆盖矩阵里的「实测」来自有限的种子与实例；格子里的结论是**这组实例上的观察**，不是统计意义上的普适结论。
- 文献引用用 Crossref / arXiv 自动核对过；书籍、会议论文与中文文献只能核到题录层面。
  **各问题页的领域内容还没有经过相应领域专家的独立审阅**——发现错误请开 issue。

# -*- coding: utf-8 -*-
"""v0.8 百科全书骨架：问题域页面生成器。

生成 4 个页面：
  /encyclopedia/         百科总纲（问题分类 × 维度 × 覆盖矩阵 × 术语表）
  /problem/knapsack/     0-1 背包（二进制编码 + 修复算子）10 算法在线演示
  /problem/continuous/   连续函数基准（PSO/DE/GWO/WOA/SCA 原生域）8 算法
  /problem/multiobj/     双目标背包 + NSGA-II Pareto 前沿动画

设计：交互模板走 <!--TOKEN--> 替换（JS 大括号多，绝不碰 str.format）。
"""
import io
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    with io.open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
        return json.load(f)

ENCYCLOPEDIA = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>元启发式与群智能算法百科总纲 · 问题分类与算法索引</title>
<meta name="description" content="群智能与元启发式算法百科：问题分类四连问（连续/组合/混合/二进制）、七个正交维度（多目标/约束/动态/噪声）、算法家族索引、术语表与本站覆盖矩阵。">
<!--THEME_HEAD-->
<link rel="stylesheet" href="/css/style.css">
<link rel="canonical" href="<!--SITE-->/encyclopedia/">
<script type="application/ld+json"><!--LDJSON--></script>
</head>
<body>
<a class="skip-link" href="#main">跳到主内容</a>
<nav class="nav"><div class="nav-inner">
  <a class="brand" href="/"><span class="logo">🐝</span>群智能算法百科</a>
  <div class="nav-links">
  <!--NAVLINKS-->
  </div>
  <!--THEME_BTN-->
</div></nav>

<div class="wrap" id="main" role="main">
  <div class="hero" style="padding-top:18px">
    <div class="crumbs"><a href="/">首页</a> · 百科总纲</div>
    <h1 style="font-size:28px">元启发式算法百科总纲<br><span class="grad">它们解决什么问题，怎么分类，怎么选</span></h1>
    <div class="sub">这一页回答一个问题：「这类算法到底能解哪几类问题」。先给结论：它们解的是「解空间大到精确算法算不动」的黑盒搜索问题；你熟悉的「离散/连续/混合」只是<strong>变量类型</strong>这一个维度，完整分类还有六个正交维度。</div>
  </div>

  <div class="fambox entrybox" id="intro" style="margin:14px 0">
    <h2 style="margin-top:2px">三分钟入门：什么是元启发式？</h2>
    <p class="hint">站名里的「群智能」取其广义（群体智慧隐喻的优化算法总称，是本站的主流家风）——实际收录覆盖元启发式全谱：进化计算、物理启发、人类/社会隐喻、混合配方与多目标，不止蚁群蜂群。</p>
    <p><b>一句话</b>：元启发式 = 给「精确算法算不动的大搜索问题」用的通用试错框架——不保证最优，但在有限时间内给出足够好的解。</p>
    <p><b>类比</b>：在陌生城市找最短路线，精确算法要把每种走法都试完（n 个城市有 (n−1)!/2 条回路，30 城已超 10³⁰ 条）；元启发式是「凭经验往好的方向试探、偶尔故意绕路跳出局部」，几百步就逼近好答案。</p>
    <p><b>名字拆开</b>：heuristic = 经验法则（不保证对、但通常好用）；meta- = 高一层——不绑定具体问题，换问题只换「编码 + 邻域」两块积木，主循环通用。</p>
    <p><b>什么时候用</b>：问题规模大到精确算法超时、且「足够好」可接受时。30 个城市可以穷举，3000 个城市交给元启发式。</p>
    <p><b>下一步</b>：往下看「四连问」定位你的问题类型 → 顶部「算法 ▾」挑一个家族 → 在任意算法页直接跑 TSP 演示。</p>
  </div>

  <h2>一、问题分类：四连问定类</h2>
  <p>拿到任何一个优化问题，依次回答四个问题，就能定位它的类别、该读哪支文献、配哪套编码：</p>
  <div class="tablewrap"><table>
    <tr><th>问题</th><th>回答 → 类别</th><th>代表问题</th><th>本站演示</th></tr>
    <tr><td rowspan="4"><b>① 变量是什么类型？</b></td><td>实数 → <b>连续优化</b></td><td>函数基准、超参调优、神经网络权重</td><td><a href="/problem/continuous/">连续函数演示</a></td></tr>
    <tr><td>排列/子集/图 → <b>组合优化</b></td><td>TSP、背包、排班、图着色</td><td><a href="/">TSP 演示</a> / <a href="/problem/knapsack/">背包演示</a></td></tr>
    <tr><td>0/1 串 → <b>二进制优化</b></td><td>特征选择、子集选择</td><td><a href="/problem/knapsack/">背包演示</a>（二进制编码）</td></tr>
    <tr><td>实数+整数混用 → <b>混合整数</b></td><td>VRP 带时间窗、流水车间调度</td><td>⏳ 混合编码尚未支持；VRP / 车间调度有<a href="/problem/vrp/">教学简化版</a></td></tr>
    <tr><td><b>② 有几个优化目标？</b></td><td>1 个 → 单目标；≥2 个冲突 → <b>多目标</b></td><td>工期 vs 成本 → Pareto 前沿</td><td><a href="/problem/multiobj/">NSGA-II 演示</a></td></tr>
    <tr><td><b>③ 解的评价稳定吗？</b></td><td>随时间变 → 动态；带随机 → 噪声/仿真</td><td>动态车辆调度</td><td><a href="/problem/dop/">动态</a> / <a href="/problem/nbbb/">噪声</a>（示意模型，非真实动态/随机）</td></tr>
    <tr><td><b>④ 每次评价贵吗？</b></td><td>仿真/实验级 → 代理模型辅助</td><td>有限元仿真优化</td><td><a href="/problem/ebbb/">昂贵黑箱</a>（示意模型；代理模型辅助尚未实现）</td></tr>
  </table></div>

  <h2>二、七个正交维度</h2>
  <p class="hint">变量类型之外，每个问题还要逐条回答这些维度。同一算法配上不同的「编码 + 邻域 + 约束处理」就能跨维度复用。</p>
  <div class="tablewrap"><table>
    <tr><th>维度</th><th>取值</th><th>主流处理技术</th><th>代表方向</th></tr>
    <tr><td>目标数</td><td>单目标 / 多目标</td><td>多目标用 Pareto 支配关系 + 拥挤度，或标量化（加权/切比雪夫）</td><td>NSGA-II（引用数万级）、MOPSO、MOEA/D</td></tr>
    <tr><td>约束</td><td>无 / 有</td><td>罚函数、修复算子、Deb 可行性规则</td><td>本站背包页用<strong>贪心修复算子</strong>（装不下按性价比扔）</td></tr>
    <tr><td>动态性</td><td>静态 / 动态</td><td>多样性保持、记忆库、预测迁移</td><td>动态车辆路由</td></tr>
    <tr><td>噪声</td><td>确定 / 随机</td><td>重复采样、隐式平均、鲁棒适应度</td><td>仿真优化</td></tr>
    <tr><td>评估成本</td><td>廉价 / 昂贵</td><td>代理模型（Kriging/RBF）、贝叶斯优化</td><td>仿真驱动设计</td></tr>
    <tr><td>峰形</td><td>单峰 / 多峰</td><td>小生境、多种群、重启策略</td><td>本站连续页的 SA/HC 都带重启组件</td></tr>
    <tr><td>规模</td><td>小 / 大规模</td><td>分解、协同进化、候选列表</td><td>本站 ACO 的候选列表就是性能关键</td></tr>
  </table></div>

  <h2>三、本站覆盖矩阵</h2>
  <div class="tablewrap"><table>
    <tr><th>问题域</th><th>编码</th><th>约束处理</th><th>目标</th><th>规模/变体</th><th>算法数</th><th>保真度</th><th>演示</th></tr>
    <!--COVERAGE_ROWS-->
  </table></div>

  <h2>四、算法家族索引</h2>
  <p class="hint"><!--FAMILY_INTRO-->；完整家族树见<a href="/algo/">算法库总览</a>。绝大多数算法原生域是连续的，本站把它们离散化到了排列/二进制上。</p>
  <div class="tablewrap"><table>
    <tr><th>家族</th><th>算法（点击看 TSP 演示页）</th></tr>
    <!--FAMILY_ROWS-->
    <tr><td><b>多目标域内实现（F7 关联）</b></td><td><a href="/problem/multiobj/">NSGA-II</a>（Deb et al. 2002，非支配排序 + 拥挤度）</td></tr>
  </table></div>

  <h2>五、术语表</h2>
  <details class="faq-item"><summary>元启发式 (metaheuristic)</summary><div class="faq-body">不依赖问题梯度/结构信息的高层搜索框架。名字里的 meta 意为「更高层」——它指导下层启发式（如 2-opt）怎么用。特征：随机性、可放弃最优性保证、换问题只需换编码。</div></details>
  <details class="faq-item"><summary>探索 vs 开发 (exploration / exploitation)</summary><div class="faq-body">探索=看没去过的地方，开发=在好解附近深挖。所有元启发式的调参本质都是平衡这对矛盾：PSO 的惯性权重、SA 的温度、GA 的变异率， knobs 不同但作用相同。</div></details>
  <details class="faq-item"><summary>适应度地形 (fitness landscape)</summary><div class="faq-body">把每个解的高度设为目标函数值得到的地形。单峰只有一个谷，多峰遍地局部最优。Rastrigin 函数是标准多峰考题——本站连续页可以直观看到算法被谷底困住的样子。</div></details>
  <details class="faq-item"><summary>Pareto 支配 / Pareto 前沿</summary><div class="faq-body">解 A 支配 B = A 在所有目标上不比 B 差且至少一个更好。不被任何解支配的解构成前沿。多目标优化的输出不是一个解，而是整条前沿——由决策者事后选择。</div></details>
  <details class="faq-item"><summary>非支配排序 + 拥挤度 (NSGA-II)</summary><div class="faq-body">把种群按支配关系分层（front 1/2/3…），层内用拥挤度（同一层里邻居稀疏程度）保多样性。引用数万级，是多目标进化的默认起点。</div></details>
  <details class="faq-item"><summary>memetic / 混合算法</summary><div class="faq-body">元启发式 + 局部搜索的混合体（道金斯 meme 的双关）。本站 TSP 侧所有种群算法的「周期 2-opt」就是 memetic 组件——「是否真在优化」自动测试专门检验「下降不是全靠局部搜索」。</div></details>
  <details class="faq-item"><summary>编码 (encoding)</summary><div class="faq-body">把问题的解表示成算法能操作的结构。同一算法换编码就能换问题：PSO 在连续域是实数向量+速度，到 TSP 变成排列+交换序列，到背包变成 0/1 向量。编码层是元启发式工程的主要工作量。</div></details>
  <details class="faq-item"><summary>修复算子 (repair operator)</summary><div class="faq-body">把违反约束的解修正为可行解。背包页的实现：超重时按「单位重量价值最低先扔」。比罚函数干净——搜索始终在可行域内进行。</div></details>
  <details class="faq-item"><summary>基准函数 (benchmark)</summary><div class="faq-body">公认的测试函数集：Sphere（单峰）、Rastrigin（强多峰）、Rosenbrock（香蕉谷）、Ackley（近全局平坦+边缘粗糙）。论文里的对比实验基本都在这些函数上做。</div></details>
  <details class="faq-item"><summary>NP-hard</summary><div class="faq-body">目前没有已知多项式时间精确算法的问题类。TSP、背包、车间调度都是。元启发式的用武之地：解不需要「最优」，只需要「够好且算得起」。</div></details>
  <details class="faq-item"><summary>「是否真在优化」自动测试</summary><div class="faq-body">本站的硬门槛：算法必须①显著优于随机基线 ②第 1 代到最后一带有真实迭代进步。没有它，你会写出「及格线全靠初始化播种、迭代在空转」的假算法——本站 DE 和 GWO 都栽过，教训写在各算法页。</div></details>
  <details class="faq-item"><summary>随机搜索为什么强</summary><div class="faq-body">低维、多峰、评价便宜时，均匀采样本身就是强基线（2D Rastrigin 上 6000 个随机样本的最好值约 0.6）。任何算法论文都必须报告与它的对比——本站每个域的算法清单里都留着 random 基线。</div></details>
  <details class="faq-item"><summary>假跑 (fake run)</summary><div class="faq-body">收敛曲线明明在下降，但下降并不是算法本身的功劳——比如全靠初始解质量高、或全靠附带的局部搜索。判断方法：关掉局部搜索再跑，或比较第 1 代与第 200 代的最优值；如果几乎不变，就是假跑。</div></details>
  <details class="faq-item"><summary>随机键编码 (random keys)</summary><div class="faq-body">把「排列」编码成一串实数，解码时按数值大小排序得到排列。它让只会处理实数的算法（PSO、CMA-ES 等）也能解 TSP、图着色这类排列问题；代价是搜索空间被扭曲，效果需要逐个验证——本站每个组合都做过「是否真在优化」检验。</div></details>
  <details class="faq-item"><summary>吸引盆 (basin of attraction)</summary><div class="faq-body">一个局部最优点周围「往下走最终会掉进它」的那片区域。不同算法从不同起点出发却得到同一个解，往往是掉进了同一个吸引盆。</div></details>

  <h2>六、建议学习路径</h2>
  <ol>
    <li>先在 <a href="/">TSP 页</a>看懂「种群 + 收敛曲线 + 基线」三件套，理解灰线/红线的区别。</li>
    <li>去 <a href="/problem/continuous/">连续函数页</a>看算法的「原生形态」——PSO/DE/GWO 在这里是教科书公式原样，再回 TSP 页对照理解离散化改了什么。</li>
    <li>去 <a href="/problem/knapsack/">背包页</a>理解「编码 + 约束修复」：同一批算法换到 0/1 向量上长什么样。</li>
    <li>去 <a href="/problem/multiobj/">多目标页</a>理解 Pareto 前沿：为什么输出从「一个解」变成「一群解」。</li>
    <li>每个算法页底部的踩坑记录值得通读——离散化的坑比算法本身更深。</li>
  </ol>

  <h2>相关页面</h2>
  <div class="cards">
    <!--CARDS-->
  </div>
</div>

<footer>
  <span class="fbrand">群智能算法百科</span>
  <span class="ver">v0.1.0</span>
  <span>算法由 Pyodide 在浏览器本地运行，数据不上传</span>
</footer>

<!--THEME_TAIL-->
</body>
</html>
"""

# ---------- 交互页脚手架（三页共用） ----------

def _fidelity_badge(domain, variant):
    """问题页的保真度徽标：读者和上传数据的人需要知道这个「演示」里的模型能不能信。"""
    import registry
    f = registry.fidelity(domain, variant)
    lvl = f["level"]
    icon = {"standard": "✅", "simplified": "⚠️", "illustrative": "🔶", "custom": "🛠"}[lvl]
    tail = {"standard": "与教科书/文献定义一致，结果可与文献对照。",
            "simplified": "问题本身是真的，但解码/约束做了教学级简化，<b>数值不能与文献对照</b>。",
            "illustrative": "只借这个问题的名字演示它的形态，<b>模型并不是该问题本身</b>。",
            "custom": "问题由你的目标函数定义，<b>结果只对你写的公式成立</b>，本站不替它的含义负责。"}[lvl]
    note = f'<div class="fid-note">与标准定义的差异：{f["note"]}</div>' if f["note"] else ""
    return (f'<div class="fidelity fid-{lvl}" role="note"><b>{icon} {registry.FIDELITY_LABEL[lvl]}</b>　{tail}{note}</div>')


def _demo_fragment(*, page_domain, preset_options, preset_labels, extra_hint,
                   heading="在线求解演示", custom_fields=None):
    """演示区块：运行设置面板 + 状态行 + 双画布 + 引擎接线脚本。
    _interactive_page 与问题轴抽象页（G 期）共用，保证全站演示区布局一致。
    custom_fields：问题规模自定义输入（list[dict]：key/label/min/max/val/type），
    选「⚙ 自定义…」时以 PAGE_CUSTOM_BASE 预设为基准、输入框覆盖规模键。"""
    preset_opts = json.dumps(preset_options, ensure_ascii=False)
    preset_sel = "\n".join(
        f'<option value="{k}">{v}</option>' for k, v in preset_labels.items()
    )
    cfs = list(custom_fields or [])
    if cfs:
        preset_sel += '\n<option value="__custom">⚙ 自定义…</option>'
    custom_json = json.dumps(cfs, ensure_ascii=False)
    custom_base = next(iter(preset_options), "")
    _fid_variant = (next(iter(preset_options.values()), None) or {}).get("variant")
    fid_html = _fidelity_badge(page_domain, _fid_variant)
    custom_html = ""
    if cfs:
        fields = "\n".join(
            f'<div class="field"><label>{f["label"]}</label>'
            f'<input id="cst_{f["key"]}" type="number" value="{f.get("val", "")}"'
            f' min="{f.get("min", 1)}" max="{f.get("max", 100000)}"'
            f' step="{f.get("step", 1)}"></div>'
            for f in cfs)
        custom_html = f'<div class="row" id="customRow" hidden>{fields}</div>'

    # 修2（2026-09-27 用户反馈）：算法下拉构建期静态注入——此前下拉靠 Pyodide
    # 跑 domain_list() 回填，引擎未就绪/加载失败时「有求解器界面但没有算法」。
    # 静态注入与 JS buildAlgoSelect 同构（category 分组 + data-tune），
    # 运行时 list 回包仍会重建一次保持元数据最新。
    algo_static = ""
    defaults_json = "{}"
    try:
        import domains as _dom  # noqa: E402  构建期 sys.path 已注入（见本文件 components 段）
        first_opts = next(iter(preset_options.values()), {}) or {}
        _lst = json.loads(_dom.domain_list(page_domain, first_opts))
        defaults_json = json.dumps(_lst.get("defaults", {}), ensure_ascii=False)
        _by_cat = {}
        for _a in _lst["algos"]:
            _by_cat.setdefault(_a["category"], []).append(_a)
        algo_static = "".join(
            '<optgroup label="%s">%s</optgroup>' % (
                _cat,
                "".join('<option value="%s" data-tune=\'%s\'>%s</option>' % (
                    _a["key"], json.dumps(_a.get("tune") or []), _a["name"])
                    for _a in _arr))
            for _cat, _arr in _by_cat.items())
    except Exception:  # noqa: BLE001  域不在注册表时留空，运行时回填兜底
        algo_static = ""
        defaults_json = "{}"

    # 多目标页性能指标面板（hypervolume，纯前端实时计算；挂 moco/maop 运行结果区）
    if page_domain == "multiobj":
        mo_metrics = """
  <div class="mo-metrics" id="moMetrics">
    <div class="mm-card"><span class="mm-label">超体积 HV</span><span class="mm-val" id="moHV">—</span></div>
    <div class="mm-card"><span class="mm-label">前沿解数 ND</span><span class="mm-val" id="moND">—</span></div>
    <div class="mm-card"><span class="mm-label">参考点（nadir 外扩10%）</span><span class="mm-val" id="moRef">—</span></div>
    <p class="mm-note" id="moNote">纯前端实时计算（2D/3D），不改 worker 协议；本合成实例无解析真前沿，IGD 不适用，仅报 HV。</p>
  </div>"""
    elif page_domain == "mocont":
        mo_metrics = """
  <div class="mo-metrics" id="moMetrics">
    <div class="mm-card"><span class="mm-label">IGD（到真前沿的平均距离，越小越好）</span><span class="mm-val" id="mcIGD">—</span></div>
    <div class="mm-card"><span class="mm-label">超体积占真前沿的比例（越大越好）</span><span class="mm-val" id="mcHV">—</span></div>
    <div class="mm-card"><span class="mm-label">非支配解数</span><span class="mm-val" id="mcND">—</span></div>
    <p class="mm-note" id="moNote">这些函数的真前沿有解析式，所以两个指标都有绝对意义：IGD 同时惩罚「没收敛」和「没铺开」；HV 的参考点按函数固定、不随结果变（多数是各目标 1.1；DTLZ1 是 0.6；ZDT5 是 (32, 11)；DTLZ7 是 (1.1, 1.1, 7)）。曲线图画的是历史最好 IGD。</p>
  </div>"""
    else:
        mo_metrics = ""

    return f"""
  <h2 id="demo">{heading}</h2>
  {fid_html}
  <div class="panel">
    <div class="panel-head">运行设置</div>
    <div class="row">
      <div class="field"><label for="algoSel">算法</label><select id="algoSel">{algo_static}</select></div>
      <div class="field"><label for="presetSel">实例</label><select id="presetSel">{preset_sel}</select></div>
      <div class="field"><label for="iterInp">迭代次数</label><input id="iterInp" type="number" value="200" min="10" max="2000"></div>
      <div class="field"><label for="seedInp">随机种子</label><input id="seedInp" type="number" value="7" min="1"></div>
      <div class="field"><label for="speedSel">速度（代/帧）</label><select id="speedSel"><option>1</option><option selected>2</option><option>5</option><option>10</option></select></div>
      <button id="btnStart" class="primary">▶ 开始</button>
      <button id="btnStop">⏸ 暂停</button>
      <button id="btnStep" title="推进一代">⏭ 单步</button>
      <button id="btnReset">⟳ 重置</button>
      <button id="btnExportDom" class="ghost">↧ 导出结果</button>
      <button id="btnPngDom" class="ghost">↧ 图像PNG</button>
      <button id="btnConvDom" class="ghost">↧ 曲线PNG</button>
      <button id="btnCsvDom" class="ghost">↧ 导出CSV</button>
      <button id="btnBundleDom" class="ghost">📦 实验包</button>
      <button id="btnImportDom" class="ghost">↥ 导入实例</button>
      <input id="domFileInput" type="file" accept=".json,.csv,.txt,.cnf,.col,.tsp,.atsp,application/json,text/csv" hidden>
    </div>
    <div class="row" id="tuneBox"></div>
    {custom_html}
  </div>
  <div class="statusline">
    <span class="pill" id="statusPill"><span class="dot"></span><span id="statusText" role="status" aria-live="polite">初始化中…</span></span>
    <span id="statusExtra">{extra_hint}</span>
  </div>
  <div id="importReport" class="import-report" role="status" hidden></div>
  <p class="hint import-hint">「导入实例」支持 .json / .csv / .cnf / .col，导入前会先校验并指出问题所在。
    <a id="lnkSample" download>下载本页示例数据</a> · <a id="lnkFormats" target="_blank" rel="noopener">格式说明</a></p>

  <div class="cols" style="margin-top:10px">
    <div>
      <div class="chart-card">
        <div class="chart-head"><span class="chart-title">问题可视化</span></div>
        <div class="chart-body"><canvas id="vizCanvas" role="img" aria-label="问题可视化：当前实例与解状态的可视化，数值可导出 JSON" width="760" height="430"></canvas></div>
      </div>
    </div>
    <div>
      <div class="chart-card">
        <div class="chart-head"><span class="chart-title">收敛曲线</span>
          <div class="legend"><span><i class="dotm" style="background:var(--cv-best)"></i>全局最优</span><span><i class="dotm" style="background:var(--cv-cur)"></i>当代</span></div>
        </div>
        <div class="chart-body"><canvas id="convCanvas" role="img" aria-label="收敛曲线：全局最优与当代值随迭代变化，数值可导出 JSON" width="760" height="430"></canvas></div>
      </div>
    </div>
  </div>
  <p class="hint">红线=全局最优（单调），灰线=当代值（允许波动）。算法在浏览器本地运行（Pyodide），首次加载约 10MB。</p>
  {mo_metrics}
  <script>
  window.PAGE_DOMAIN = "{page_domain}";
  window.PAGE_PRESETS = {preset_opts};
  window.PAGE_CUSTOM_FIELDS = {custom_json};
  window.PAGE_CUSTOM_BASE = "{custom_base}";
  window.PAGE_DEFAULTS = {defaults_json};
  </script>
  <script src="/js/compat.js"></script>
  <script src="/js/domain_page.js"></script>
"""


# G 期：抽象类型页 id → 演示配置（问题轴 pages_problems 注入，替代「无演示」横幅）
ABSTRACT_DEMO = {
    "scp": dict(page_domain="setcover",
                preset_options={"s80": {"n_el": 80, "m": 50}, "s60": {"n_el": 60, "m": 40}},
                preset_labels={"s80": "80 元素 × 50 集合（默认）", "s60": "60 元素 × 40 集合（小）"},
                custom_fields=[{"key": "n_el", "label": "元素数", "min": 20, "max": 200, "val": 80}, {"key": "m", "label": "集合数", "min": 10, "max": 150, "val": 50}],
                   extra_hint="行=集合 列=元素，亮行=被选中的集合",
                heading="在线求解演示 · Set Cover"),
    "sat": dict(page_domain="sat",
                preset_options={"sat426": {"n_vars": 30, "ratio": 4.26}, "sat35": {"n_vars": 30, "ratio": 3.5}},
                preset_labels={"sat426": "30 变量 · 相变点 4.26（常可满足）", "sat35": "30 变量 · 3.5（容易可满足）"},
                custom_fields=[{"key": "n_vars", "label": "变量数", "min": 10, "max": 100, "val": 30}, {"key": "ratio", "label": "子句/变量比", "min": 2, "max": 8, "val": 4.26, "step": 0.1}],
                   extra_hint="绿=满足的子句 红=未满足，目标=全绿",
                heading="在线求解演示 · SAT"),
    "maxsat": dict(page_domain="sat",
                   preset_options={"ms52": {"n_vars": 30, "ratio": 5.2}},
                   preset_labels={"ms52": "30 变量 · 5.2（不可满足区，最小化未满足数）"},
                   custom_fields=[{"key": "n_vars", "label": "变量数", "min": 10, "max": 100, "val": 30}, {"key": "ratio", "label": "子句/变量比", "min": 2, "max": 8, "val": 5.2, "step": 0.1}],
                   extra_hint="实例多为不可满足：DPLL 给精确锚点，其余算法比谁的未满足数低",
                   heading="在线求解演示 · MAX-SAT"),
    "uflp": dict(page_domain="uflp",
                 preset_options={"u45": {"n_f": 15, "n_c": 45}, "u30": {"n_f": 12, "n_c": 30}},
                 preset_labels={"u45": "15 设施 × 45 客户（偏好结构，默认）", "u30": "12 设施 × 30 客户（小）"},
                 custom_fields=[{"key": "n_f", "label": "设施数", "min": 5, "max": 50, "val": 15}, {"key": "n_c", "label": "客户数", "min": 10, "max": 150, "val": 45}],
                 extra_hint="方块=设施 圆点=客户 线=指派，总成本=固定+指派",
                 heading="在线求解演示 · UFLP"),
    "csp": dict(page_domain="binpack",
                preset_options={"n40": {"n": 40}, "n60": {"n": 60}},
                preset_labels={"n40": "40 件（默认）", "n60": "60 件（大）"},
                custom_fields=[{"key": "n", "label": "零件数", "min": 10, "max": 200, "val": 40}],
                 extra_hint="一维下料 = 一维装箱：棒材=箱子，零件=物品，目标=最少棒材",
                heading="在线求解演示 · 一维下料（装箱引擎）"),
    "moco": dict(page_domain="multiobj",
                 preset_options={"n40": {"n": 40}},
                 preset_labels={"n40": "双目标背包 · 40 件（演示实例）"},
                 custom_fields=[{"key": "n", "label": "物品数", "min": 10, "max": 150, "val": 40}],
                 extra_hint="灰点=种群 红点=Pareto 前沿，右上角更好",
                 heading="在线求解演示 · 多目标（NSGA-II）"),
}

# G 期：类页 dir → 演示配置
CLASS_DEMO = {
    "assignment": dict(page_domain="gap",
                       preset_options={"g25": {"n_a": 8, "n_j": 25}, "g40": {"n_a": 10, "n_j": 40}},
                       preset_labels={"g25": "8 代理 × 25 任务（默认）", "g40": "10 代理 × 40 任务（大）"},
                       custom_fields=[{"key": "n_a", "label": "代理数", "min": 3, "max": 20, "val": 8}, {"key": "n_j", "label": "任务数", "min": 10, "max": 100, "val": 25}],
                       extra_hint="列=代理 实柱=负载 绿虚线=容量，红=超载",
                       heading="在线求解演示 · 广义指派 GAP"),
    "qubo": dict(page_domain="qubo",
                 preset_options={"q30": {"n": 30}, "q50": {"n": 50}},
                 preset_labels={"q30": "30 比特（默认）", "q50": "50 比特（大）"},
                 custom_fields=[{"key": "n", "label": "比特数", "min": 10, "max": 120, "val": 30}],
                       extra_hint="亮方块=取 1 的比特，目标=能量 x'Qx 最小",
                 heading="在线求解演示 · QUBO"),
}

# H1 期：背包变体子页 id → kpvar 域演示配置（单域多预设，变体由 opts.variant 分派）
def _kpv_cfg(variant, abbr, hint, label):
    return dict(page_domain="kpvar",
                preset_options={"v40": {"variant": variant, "n": 40}},
                preset_labels={"v40": label},
                extra_hint=hint,
                custom_fields=[{"key": "n", "label": "物品数 n", "min": 10, "max": 300, "val": 40}],
                heading=f"在线求解演示 · {abbr}")

VARIANT_DEMO = {
    "fractional": dict(page_domain="entryseq",
                       preset_options={"n30": {"variant": "fkp", "n": 30}, "n50": {"variant": "fkp", "n": 50}},
                       preset_labels={"n30": "30 件 · 容量 45%（与 0-1 背包同分布）", "n50": "50 件"},
                       custom_fields=[{"key": "n", "label": "物品数 n", "min": 8, "max": 60, "val": 30}],
                       extra_hint="每个物品取一个比例 x∈[0,1]：柱高 = 重量，填充 = 取了多少；绿虚线 = 贪心（按价值密度）得到的精确最优——分数背包有多项式精确解，可以拿它检验算法",
                       heading="在线求解演示 · 分数背包 Fractional Knapsack"),
    "bounded": _kpv_cfg("bkp", "Bounded Knapsack (BKP)",
                        "同一件有多个拷贝（复制展开成位）：柱=拷贝 亮=选中",
                        "40 种 × 每件 2-4 拷贝"),
    "unbounded": _kpv_cfg("ukp", "Unbounded Knapsack (UKP)",
                          "每件最多 3 份（容量截断）：柱=份 亮=选中",
                          "40 种 × 每件 ≤3 份"),
    "changemaking": _kpv_cfg("cmp", "Change-Making Problem (CMP)",
                             "目标金额 T 精确凑出、枚数最少：亮=投入的硬币（min-coin DP 给精确锚点）",
                             "币值 1/2/5/10/20/50 · 目标 120-200"),
    "multiple": _kpv_cfg("mkpm", "Multiple Knapsack (MKP-m)",
                         "列=背包 实柱=负载 绿虚线=容量（0=不取）：把物品派进 3 个包",
                         "40 件 × 3 包（指派编码）"),
    "multiplechoice": dict(
        page_domain="kpvar",
        # 修1（2026-09-27 用户反馈）：预设与自定义同格式（类数 K × 每类件数 R），
        # 不再是「预设 12 类×4 件 vs 自定义填物品数」两套口径
        preset_options={"mc48": {"variant": "mckp", "k": 12, "r": 4}},
        preset_labels={"mc48": "12 类 × 4 件 · 单约束"},
        custom_fields=[{"key": "k", "label": "类数 K", "min": 2, "max": 60, "val": 12},
                       {"key": "r", "label": "每类件数 R", "min": 2, "max": 12, "val": 4}],
        extra_hint="每类至多选一件：K 类 × R 件网格，亮=该类所选",
        heading="在线求解演示 · Multiple-Choice Knapsack (MCKP)"),
    "multidim": _kpv_cfg("mdkp", "Multidimensional Knapsack (MKP)",
                         "三个资源维度（各有独立的重量与容量）同时约束：柱=物品（高度=第一维重量）亮=选中",
                         "40 件 · 3 维资源"),
    "discounted": _kpv_cfg("dkp", "Discounted Knapsack",
                           "每组 3 个候选（A、B、打 75 折的捆绑 A+B），每组至多选一个：格=候选 亮=选中",
                           "20 组 × 3 个候选"),
    "quadratic": _kpv_cfg("qkp", "Quadratic Knapsack (QKP)",
                          "物品两两有协同利润 Q：柱=物品 亮=选中",
                          "40 件 · 协同矩阵 Q"),
    "subsetsum": _kpv_cfg("ssp", "Subset Sum (SSP)",
                          "子集重量恰好=目标：柱=物品 亮=选中；|Σw-T| 最小（reach DP 精确锚点）",
                          "40 件 · 目标=45% 总重"),
}

# H2 期：着色家族 5 变体子页 id → gcvar 域演示配置（单域多预设，变体由 opts.variant 分派）
# edgecolor/totalcolor 经线图/全图变换后元素数 N 暴涨到 ~400，浏览器演示须用更小的 n，
# 否则 TS 在 O(N²) 解码下卡死；listcolor/precolor/mis 维持 n=40。
_GCVAR_BLOWUP = ("edgecolor", "totalcolor")


def _gcv_cfg(variant, abbr, hint, label):
    n0 = 22 if variant in _GCVAR_BLOWUP else 40
    return dict(page_domain="gcvar",
                preset_options={"v40": {"variant": variant, "n": n0, "p": 0.5}},
                preset_labels={"v40": label},
                extra_hint=hint,
                custom_fields=[{"key": "n", "label": "顶点数 n", "min": 10, "max": 120, "val": n0},
                               {"key": "p", "label": "边密度 p", "min": 0.1, "max": 0.9, "val": 0.5, "step": 0.05}],
                heading=f"在线求解演示 · {abbr}")

ABSTRACT_DEMO.update({
    "lcp": _gcv_cfg("listcolor", "List Coloring (LCP)",
                    "顶点有候选色列表（邻域/修复须尊重列表约束）；色块=顶点着色，相邻异色，颜色越少越好（金圈无）",
                    "40 顶点 · p=0.5（每顶点删 1-2 候选色）"),
    "ecp": _gcv_cfg("edgecolor", "Edge Coloring (ECP)",
                    "线图 L(G) 变换后跑图着色内核；边染色视角：颜色=边，共享顶点的边必须异色；下界=最大度 Δ（Vizing 定理 χ'=Δ 或 Δ+1）",
                    "40 顶点 · p=0.5（边色数下界 Δ）"),
    "prext": _gcv_cfg("precolor", "Precoloring Extension (PrExt)",
                      "部分顶点颜色预固定（金圈标记），SA/TS 邻域不得触碰预染顶点；其余正常着色",
                      "40 顶点 · 预染 20-30%"),
    "tcp": _gcv_cfg("totalcolor", "Total Coloring (TCP)",
                    "顶点+边同时着色，关联也要异色（顶-边同色即冲突）；总色数最小（Total Coloring Conjecture：χ''=Δ+1 或 Δ+2）",
                    "40 顶点 · p=0.5（顶点与边同调色板）"),
    "mis": _gcv_cfg("mis", "Maximum Independent Set (MIS)",
                    "0/1 位串编码：选中的顶点互不相邻即合法（绿=选中）；目标=独立集最大。度升序贪心作锚点",
                    "40 顶点 · p=0.5（最大独立集）"),
})

# H3 期：装箱变体家族 3 变体子页 id → bpvar 域演示配置（单域多预设，变体由 opts.variant 分派）
def _bpv_cfg(variant, abbr, hint, label):
    return dict(page_domain="bpvar",
                preset_options={"v40": {"variant": variant, "n": 40}},
                preset_labels={"v40": label},
                extra_hint=hint,
                custom_fields=[{"key": "n", "label": "物品数 n", "min": 10, "max": 200, "val": 40}],
                heading=f"在线求解演示 · {abbr}")

ABSTRACT_DEMO.update({
    "bpp2d": _bpv_cfg("binpack2d", "Two-Dimensional BPP (2D-BPP)",
                      "矩形物品按 shelf 解码装入 70×70 箱；每格=一件矩形，箱数越少越好",
                      "40 件 · 70×70 箱"),
    "spp": _bpv_cfg("strippack", "Strip Packing (SPP)",
                    "矩形物品按 shelf 自上而下铺进 100 宽条带，总高度最小；每格=一件矩形",
                    "40 件 · 条带宽 100"),
    "vsbpp": _bpv_cfg("vsbinpack", "Variable-Sized BPP (VSBPP)",
                      "物品有重量，须装入变尺寸档位箱（容量/成本递增）；目标=开启箱成本之和最小",
                      "40 件 · 三档箱 [80/150/220]"),
})

# H3 期：BBOB 基准套件 → 复用 continuous 域（BBOB 函数已注入 FUNCS）；maop 多目标 → multiobj 域（variant=maop）
ABSTRACT_DEMO.update({
    "bbob": dict(page_domain="continuous",
                 preset_options={"f1": {"fn": "bbob_f1", "dim": 2}, "f2": {"fn": "bbob_f2", "dim": 2},
                                 "f3": {"fn": "bbob_f3", "dim": 4}, "f4": {"fn": "bbob_f4", "dim": 4},
                                 "f5": {"fn": "bbob_f5", "dim": 5}, "f6": {"fn": "bbob_f6", "dim": 4}},
                 preset_labels={"f1": "教学序 f1 球面（2 维）", "f2": "教学序 f2 椭球（2 维）",
                                "f3": "教学序 f3 雪茄（4 维）", "f4": "教学序 f4 铁饼（4 维）",
                                "f5": "教学序 f5 异次幂（5 维）", "f6": "教学序 f6 尖脊（4 维）"},
                 custom_fields=[{"key": "dim", "label": "维度 d", "min": 2, "max": 20, "val": 2}],
                 extra_hint="连续域原生：PSO/DE/CMA-ES 等实数编码算法在 BBOB 函数跑分；曲线=当代最优收敛。注意：f 编号为本站教学序——f1 球面/f2 椭球与 COCO 官方一致，f3–f6（雪茄/铁饼/异次幂/尖脊）取自 BBOB 套件真实函数但<b>非 COCO 官方序号</b>（官方 f3–f6 = separable Rastrigin/Büche-Rastrigin/Linear Slope/Attractive Sector）",
                 heading="在线求解演示 · BBOB 基准套件"),
    "maop": dict(page_domain="multiobj",
                 preset_options={"m40": {"variant": "maop", "n": 40}},
                 preset_labels={"m40": "三目标背包 · 40 件（演示实例）"},
                 custom_fields=[{"key": "n", "label": "物品数", "min": 10, "max": 150, "val": 40}],
                 extra_hint="灰点=种群 红点=Pareto 前沿（点色=目标3 收益）；NSGA-II 覆盖非凸面",
                 heading="在线求解演示 · 多目标（三目标 NSGA-II）"),
})



# 解冻令首批（2026-09-27 用户令「词条都要有实例」）：TSP 下拉 9 词条 → entryseq 域迷你实例
def _es_cfg(variant, abbr, hint, label, nmax):
    return dict(page_domain="entryseq",
                preset_options={"es12": {"variant": variant, "n": 12}},
                preset_labels={"es12": label},
                custom_fields=[{"key": "n", "label": "规模 n", "min": 4, "max": nmax, "val": 12}],
                extra_hint=hint,
                heading=f"在线求解演示 · {abbr}")

ABSTRACT_DEMO.update({
    "vrp": dict(page_domain="entryseq",
                preset_options={"es12": {"variant": "vrp", "n": 12}, "es25": {"variant": "vrp", "n": 25},
                                "es40": {"variant": "vrp", "n": 40}},
                preset_labels={"es12": "12 客户（小）", "es25": "25 客户（中）", "es40": "40 客户（大）"},
                custom_fields=[{"key": "n", "label": "客户数", "min": 5, "max": 40, "val": 12}],
                extra_hint="每辆车一种颜色：仓库（方块）出发、服务一串客户、回到仓库；标注 载重/容量",
                heading="在线求解演示 · 带容量车辆路径 CVRP"),
    "vrptw": dict(page_domain="entryseq",
                  preset_options={"es12": {"variant": "vrptw", "n": 12}, "es25": {"variant": "vrptw", "n": 25},
                                  "es40": {"variant": "vrptw", "n": 40}},
                  preset_labels={"es12": "12 客户（小）", "es25": "25 客户（中）", "es40": "40 客户（大）"},
                  custom_fields=[{"key": "n", "label": "客户数", "min": 5, "max": 40, "val": 12}],
                  extra_hint="上：每辆车一种颜色的路线；下：时间轴——浅色条 = 客户的时间窗，深色块 = 服务时段，细线 = 早到后的等待",
                  heading="在线求解演示 · 带时间窗的车辆路径 VRPTW"),
    "vrpstw": dict(page_domain="entryseq",
                   preset_options={"es12": {"variant": "vrpstw", "n": 12}, "es25": {"variant": "vrpstw", "n": 25},
                                   "es40": {"variant": "vrpstw", "n": 40}},
                   preset_labels={"es12": "12 客户（小）", "es25": "25 客户（中）", "es40": "40 客户（大）"},
                   custom_fields=[{"key": "n", "label": "客户数", "min": 5, "max": 40, "val": 12}],
                   extra_hint="时间轴：浅色条 = 时间窗，深色块 = 服务时段，红条 = 窗口关闭后又过了多久才到（迟到要罚）；目标 = 里程 + λ × 迟到",
                   heading="在线求解演示 · 软时间窗车辆路径 VRPSTW"),
    "mdvrp": dict(page_domain="entryseq",
                  preset_options={"es12": {"variant": "mdvrp", "n": 12}, "es25": {"variant": "mdvrp", "n": 25},
                                  "es40": {"variant": "mdvrp", "n": 40}},
                  preset_labels={"es12": "12 客户 · 2 个仓库", "es25": "25 客户 · 3 个仓库", "es40": "40 客户 · 3 个仓库"},
                  custom_fields=[{"key": "n", "label": "客户数", "min": 5, "max": 40, "val": 12}],
                  extra_hint="方块 = 仓库（带编号）；每条路线从自己的仓库出发、回到自己的仓库；各仓库的车数各自有上限",
                  heading="在线求解演示 · 多车场车辆路径 MDVRP"),
    "hcycle": dict(page_domain="entryseq",
                preset_options={"n10": {"variant": "hc", "n": 10}, "n14": {"variant": "hc", "n": 14}},
                preset_labels={"n10": "10 点随机图（植入了一条哈密顿回路）", "n14": "14 点随机图"},
                custom_fields=[{"key": "n", "label": "规模 n", "min": 4, "max": 14, "val": 10}],
                extra_hint="灰线 = 图的边；排列首尾相接画成红线，红虚线 = 这一步不是图里的边（目标 = 虚线条数，0 = 找到了哈密顿回路）",
                heading="在线求解演示 · 哈密顿回路 HC"),
    "lpath": dict(page_domain="entryseq",
                preset_options={"n10": {"variant": "lpath", "n": 10}, "n12": {"variant": "lpath", "n": 12}},
                preset_labels={"n10": "10 点随机图（植入了一条哈密顿路径）", "n12": "12 点随机图"},
                custom_fields=[{"key": "n", "label": "规模 n", "min": 4, "max": 12, "val": 10}],
                extra_hint="灰线 = 图的边（权重越大越粗）；红线 = 沿排列延伸、碰到非边就停下的那条路径；目标 = 路径权重和（越大越好）",
                heading="在线求解演示 · 最长路径 LP"),
    "lop": _es_cfg("lop", "线性排序 LOP",
                   "排序柱：排列 π 最大化 Σ_{i&lt;j} w[π(j)][π(i)]——排名聚合/赛事积分的数学内核", "12×12 权重矩阵", 12),
    "sms": _es_cfg("sms", "单机调度 SMS",
                   "时间线：作业按加工顺序累加，红色段=超工期延误部分，目标=总延误最小", "10 作业 · 总延误", 10),
    "fss": dict(page_domain="entryseq",
                preset_options={"n20": {"variant": "fss", "n": 20}, "n12": {"variant": "fss", "n": 12}},
                preset_labels={"n20": "ta001 · 20 作业 × 5 机（已知最优 1278）", "n12": "12 作业 × 5 机（随机）"},
                custom_fields=[{"key": "n", "label": "规模 n", "min": 4, "max": 20, "val": 20}],
                extra_hint="甘特图：每行一台机器，色块 = 作业；所有机器上作业顺序相同；绿虚线 = 下界；目标 = 完工时间 Cmax",
                heading="在线求解演示 · 置换流水车间 PFSP"),
    "jss": dict(page_domain="entryseq",
                preset_options={"n6": {"variant": "jss", "n": 6}, "n8": {"variant": "jss", "n": 8}},
                preset_labels={"n6": "ft06 · 6 作业 × 6 机（已知最优 55）", "n8": "8 作业 × 5 机（随机）"},
                custom_fields=[{"key": "n", "label": "规模 n", "min": 4, "max": 10, "val": 6}],
                extra_hint="甘特图：每行一台机器，色块 = 作业的一道工序；每个作业有自己的机器路线；绿虚线 = 下界；目标 = 完工时间 Cmax",
                heading="在线求解演示 · 作业车间 JSP"),
    "oss": dict(page_domain="entryseq",
                preset_options={"n4": {"variant": "oss", "n": 4}, "n5": {"variant": "oss", "n": 5}},
                preset_labels={"n4": "4 作业 × 4 机（随机）", "n5": "5 作业 × 5 机（随机）"},
                custom_fields=[{"key": "n", "label": "规模 n", "min": 4, "max": 6, "val": 4}],
                extra_hint="甘特图：每行一台机器；每个作业在每台机器上各做一次、顺序自由；绿虚线 = 下界（最大机器负载与最长作业取大）；目标 = 完工时间",
                heading="在线求解演示 · 开放车间 OSP"),
    # 排程专业域挂载（2026-09-29 完善战役；同日架构待议项正名）：etp 词条=Exam Timetabling，
    # 挂引擎 etp 域（scheduling.py Kempen 规格：同时段冲突硬罚 + 相邻时段/教室容量软罚，
    # 图着色式 repair）。引擎键正名：ttp=旅行锦标赛（见下方 ttp 条目），考试时间表=etp。
    "etp": dict(page_domain="etp",
                preset_options={"e30": {"E": 30}, "e20": {"E": 20}},
                preset_labels={"e30": "30 考试（默认，冲突图 p=0.18）", "e20": "20 考试（小）"},
                custom_fields=[{"key": "E", "label": "考试数", "min": 8, "max": 60, "val": 30}],
                extra_hint="时段条：每行=一个时段，块=考试。目标三层：同时段学生冲突(硬×1000)/相邻时段同学生(软，Kempen)/教室容量(软)；时段数 T=冲突图最大度+1（T≥χ 保证零冲突解存在，图着色式 repair）",
                heading="在线求解演示 · 考试时间表（Kempen 规格）"),
    "ctp": dict(page_domain="entryseq",
                preset_options={"n12": {"variant": "ctp", "n": 12}, "n8": {"variant": "ctp", "n": 8}, "n14": {"variant": "ctp", "n": 14}},
                preset_labels={"n12": "12 门课 · 约 23 节（默认）", "n8": "8 门课 · 14 节（小）", "n14": "14 门课 · 约 22 节"},
                custom_fields=[{"key": "n", "label": "课程数", "min": 4, "max": 14, "val": 12}],
                extra_hint="课表：列 = 星期，行 = 节次，每格最多 3 块（3 间教室）；颜色 = 课程；排课顺序是搜索对象，解码时逐节取最早的合法时段",
                heading="在线求解演示 · 课程排课 CTP"),
    # 排程域挂载（2026-09-29 完善战役）：原批 3 撤下的护士排班/赛程生成，经 scheduling.py
    # 专业建模（软硬分层目标+贪心/min-conflicts repair）后过防假跑门回挂：
    # nrp ts=120 vs random=8396；sls hc=45 vs random=1065（bench iters=200 seed=7）。
    # 旅行锦标赛 TTP 专属域（2026-09-29 架构待议项落地，引擎键正名 ttp=tour_make）：
    # 词条↔域名实一致（problems.json ttp=Easton & Nemhauser 2001）；门：hc=2145 vs random=10984。
    "nrp": dict(page_domain="nrp",
                preset_options={"n10": {"N": 10, "D": 7, "S": 3}, "n14": {"N": 14, "D": 10, "S": 3}},
                preset_labels={"n10": "10 护士 × 7 天 × 3 班（默认）", "n14": "14 护士 × 10 天 × 3 班（大）"},
                custom_fields=[{"key": "N", "label": "护士数", "min": 4, "max": 30, "val": 10},
                               {"key": "D", "label": "天数", "min": 3, "max": 21, "val": 7},
                               {"key": "S", "label": "班次数", "min": 2, "max": 4, "val": 3}],
                extra_hint="排班网格：行=护士 列=天，块色=班次（灰=休息）。目标三层：覆盖缺口(硬×1000)/偏好违约(软×8)/连班>5天(软×20)",
                heading="在线求解演示 · 护士排班 NRP"),
    "sls": dict(page_domain="sls",
                preset_options={"s8": {"m": 8}, "s10": {"m": 10}},
                preset_labels={"s8": "8 队双循环 · 14 轮（默认）", "s10": "10 队双循环 · 18 轮"},
                custom_fields=[{"key": "m", "label": "队数（偶数）", "min": 4, "max": 16, "val": 8, "step": 2}],
                extra_hint="轮次表：每行=一轮，块=队号（左实块=主队 右描边=客队，金圈=焦点队）。目标全软：主客平衡/连主连客/对阵完整性(主导)/焦点战分布",
                heading="在线求解演示 · 赛程生成 SLS"),
    "ttp": dict(page_domain="ttp",
                preset_options={"m8": {"m": 8}, "m10": {"m": 10}},
                preset_labels={"m8": "8 队双循环 · 14 轮（默认）", "m10": "10 队双循环 · 18 轮"},
                custom_fields=[{"key": "m", "label": "队数（奇数自动+1）", "min": 4, "max": 16, "val": 8}],
                extra_hint="赛程×地理：上半=球队主城点图（位置即实例，两两距离取整欧氏），下半=轮次表（左实块=主队 右描边=客队，红框=与上一轮重复对阵）。目标：总旅行距离(原始)+对阵完整(主导×500)+连主连客>3(×6)+重复对阵(×12)",
                heading="在线求解演示 · 旅行锦标赛 TTP"),
    "fjsp": dict(page_domain="entryseq",
                preset_options={"n6": {"variant": "fjsp", "n": 6}, "n8": {"variant": "fjsp", "n": 8}},
                preset_labels={"n6": "6 作业 × 3 工序 × 5 机（随机）", "n8": "8 作业 × 3 工序 × 5 机（随机）"},
                custom_fields=[{"key": "n", "label": "规模 n", "min": 4, "max": 8, "val": 6}],
                extra_hint="甘特图：每行一台机器；每道工序可在 2–3 台机器里选一台（时间不同），解码时挑做完最早的那台；绿虚线 = 下界；目标 = 完工时间",
                heading="在线求解演示 · 柔性作业车间 FJSP"),
    "carp": dict(page_domain="entryseq",
                preset_options={"n10": {"variant": "carp", "n": 10}, "n12": {"variant": "carp", "n": 12}},
                preset_labels={"n10": "14 路口 · 10 条必需边", "n12": "14 路口 · 12 条必需边"},
                custom_fields=[{"key": "n", "label": "规模 n", "min": 4, "max": 12, "val": 10}],
                extra_hint="灰线 = 路网；粗线 = 必须服务的边；不同颜色 = 不同的车次（从仓库方块出发、回仓库，容量 20）；虚线 = 空驶",
                heading="在线求解演示 · 带容量弧路由 CARP"),
    "lap": _es_cfg("lap", "线性指派 LAP",
                   "指派矩阵：排列=代理→任务，目标=总成本（匈牙利精确解是活对照）", "12×12 成本矩阵", 12),
    "qap": _es_cfg("qap", "二次分配 QAP",
                   "指派矩阵：流量×距离二次目标（组合优化最难问题类之一）", "10×10 双矩阵", 10),
    "pmedian": _es_cfg("pmedian", "p-中位 PMED",
                       "点图：方块 = 设施（排列前 3 位），细线 = 客户到最近设施，目标 = 总距离", "14 点 · 选 3", 14),
    "pcenter": _es_cfg("pcenter", "p-中心 PCEN",
                       "点图：同 PMED 但目标 = 最小化最远客户的距离（公平性目标）", "14 点 · 选 3", 14),
    "cflp": _es_cfg("cflp", "容量设施选址 CFLP",
                    "点图：按排列顺序开设施直到容量够用，客户派给最近且装得下的设施；目标 = 固定费 + 运输费", "12 点 · 每点有需求和容量", 12),
    "lrp": _es_cfg("lrp", "选址-路径联合 LRP",
                   "点图：方块 = 仓库（排列前 2 位），客户由最近仓库派车，按排列顺序装车；目标 = 仓库费 + 车费 + 路程", "12 点 · 选 2 · 车容量 20", 12),
    "stp": _es_cfg("stp", "斯坦纳树 STP",
                   "点图：蓝方块=必需点，选哪些其余点当中转点；目标=这些点的最小生成树长度", "12 点 · 4 必需", 12),
    "tdm": _es_cfg("tdm", "3-维匹配 3DM",
                   "矩阵：每行一个三元组（X、Y、Z 各一格亮），选尽量多两两不相交的行；植入了完美匹配，最优值已知", "X、Y、Z 各 5 个元素 · 15 个三元组", 9),
    "ndp": _es_cfg("ndp", "网络设计 NDP",
                   "点图：每条候选边一位 = 买不买；3 对需求点必须被买下的边连通，目标 = 建边费用", "12 点 · 3 对需求", 12),
    "vcover": _es_cfg("vcover", "顶点覆盖 VC",
                      "点图：每点一位=选/不选；红点=选中，红虚线=没被覆盖的边（目标=选中点数 + 违反罚）", "12 点 · 35% 边", 12),
    "domset": _es_cfg("domset", "支配集 DS",
                      "点图：每点一位=建不建塔；红点=塔，蓝=被支配，黄=没被支配（目标=塔数 + 违反罚）", "12 点随机图", 12),
    "mclique": _es_cfg("mclique", "最大团 MCP",
                       "点图：排列序贪心构建完全子团，目标=团最大", "12 点 · 35% 边", 12),
    "setpack": _es_cfg("setpack", "集合打包 SPK",
                       "矩阵：行=集合、列=元素，红=被选集合里的元素；目标=选尽量多的两两不相交的集合", "8 集合 × 12 元素", 14),
    "hset": _es_cfg("hset", "击集 HIT",
                    "矩阵：行=集合、列=元素，红=被选元素所在列；目标=选尽量少的元素击中每个集合", "8 集合 × 12 元素", 14),
    "fvs": _es_cfg("fvs", "反馈顶点集 FVS",
                   "点图：带 ✕ 的红点=被删除，蓝线=剩下的图；目标=删掉的点数 + 剩余环的罚", "12 点随机图", 12),
    "maxcut": _es_cfg("maxcut", "最大割 MAX-CUT",
                      "点图：红 / 蓝 = 两侧（不必一样大），红线=被割断的边；目标=割边权和最大", "12 点加权图", 12),
    "gpp": _es_cfg("gpp", "图划分 GPP",
                   "点图：均衡分侧+最小割（与 MAX-CUT 反目标，METIS 领域）", "12 点加权图", 12),
    "csplogic": _es_cfg("csplogic", "约束满足 CSP",
                        "取模赋值：变量→4 值域，冲突对 BIG 罚（Min-Conflicts 适用）", "10 变量 · 4 值域", 10),
    "mst": _es_cfg("mst", "最小生成树 MST",
                   "点图：解 = 边的优先序，Kruskal 式解码（成环就跳过）；红 = 选中的树边；页面给出 Kruskal 的精确最优作对照——P 类问题，群智能只是演示", "12 点随机连通加权图", 24),
    "shortestpath": _es_cfg("shortestpath", "最短路径 SP",
                            "点图：解 = 每个点的优先级，从起点走向优先级最高的未访问邻居；红 = 走出的路径；页面给出 Dijkstra 的精确最优作对照——P 类问题", "12 点 · 起点到最远的点", 24),
    "maxflow": _es_cfg("maxflow", "最大流 MF",
                       "有向网络：解 = 每条弧上的流量（线宽 ∝ 流量），目标 = −源点净流出 + 3×守恒违反量；页面给出 Edmonds–Karp 的最大流作对照——P 类问题，要在满足流量守恒的前提下搜索", "12 点有向容量网络", 16),
    "cbbb": _es_cfg("cbbb", "约束黑箱 CBBB",
                    "收敛曲线：rastrigin+Σx≤3 线性罚（黑箱主场，梯度法出局）", "8 维 · 约束罚", 8),
    "nbbb": _es_cfg("nbbb", "噪声黑箱 NBBB",
                    "收敛曲线：rastrigin+确定性伪噪声（重采样/大种群平滑）", "8 维 · 噪声", 8),
    "lbbb": _es_cfg("lbbb", "大规模黑箱 LBBB",
                    "收敛曲线：10 维 Rosenbrock 香蕉谷（维数灾难/分块 CMA）", "10 维 Rosenbrock", 10),
    "ebbb": _es_cfg("ebbb", "昂贵黑箱 EBBB",
                    "收敛曲线：50 代模拟昂贵预算（贝叶斯优化主场）", "8 维 · 预算约束", 8),
    "blo": _es_cfg("blo", "双层优化 BLO",
                   "收敛曲线：一个由「上层 Σx²」与「下层响应项」拼成的 8 维目标——它只是一个人造的单层函数，不是真正的嵌套优化（示意模型）", "8 维 · 示意", 8),
    "ro": _es_cfg("ro", "鲁棒优化 RO",
                  "收敛曲线：目标 = 8 个扰动场景下的最差 Rastrigin 值（场景在实例里固定）——最差情形比名义值差，解会移向对扰动不敏感的区域", "8 维 · 8 个扰动场景", 8),
    "mmo": _es_cfg("mmo", "多模态优化 MMO",
                   "收敛曲线：8 维 Rastrigin（指数多个局部峰）——只评价「找到最好的一个」，没有「同时找出多个峰」的评价（示意模型）", "8 维 · 示意", 8),
    "dop": _es_cfg("dop", "动态优化 DOP",
                   "收敛曲线：一个按 x₁ 的符号在两个盆地之间切换的静态函数——目标并不随时间变化，所以这里没有「追踪变化」的问题（示意模型）", "8 维 · 示意", 8),
    "ged": _es_cfg("ged", "生成式设计 GD",
                   "布局：圆形功能块摆进场地，互不重叠，虚线连着的块对希望相邻；解 = 每个块的坐标（实数向量）", "8 个块 · 约 10 对希望相邻", 12),
    "proteinfold": _es_cfg("proteinfold", "蛋白质折叠 HP",
                           "二维方格 HP 链：实心红 = 疏水（H），空心 = 亲水（P），蓝虚线 = HH 拓扑接触；目标 = −接触数 + 4×自交处数", "20 残基 HP 链", 20),
    "msa": _es_cfg("msa", "多序列比对 MSA",
                   "比对：3 条合成 DNA 序列，每行一个 0/1 串决定残基放在哪些列；彩色 = 残基，· = 空位；页面给出三维动态规划的精确最优 SP 得分作对照", "3 条序列 · 约 12 个碱基", 14),
    "orienteering": _es_cfg("orienteering", "定向运动 OP",
                            "点图：点大小=收益；红线=路线（从仓库出发回到仓库），灰点=没去；预算有限，目标=收益总和最大",
                            "12 点 · 预算 = 回路的 45%", 20),
    "mincostflow": _es_cfg("mincostflow", "最小费用流 MCF",
                           "有向网络：解 = 每条弧上的流量；目标 = 总费用 + 60×(送出量偏差 + 守恒违反量)，要送出最大流的 60%；页面给出逐次最短增广路得到的最小费用作对照——P 类问题", "12 点有向容量费用网", 16),
    "topsort": _es_cfg("topsort", "拓扑排序 TSORT",
                       "一行点：解 = 顶点的排列；绿弧 = 从左指向右（满足），红弧 = 指回左边（违反，目标 = 红弧数）；Kahn 算法线性时间可得 0——P 类问题", "12 点有向无环图", 24),
    "gmatch": _es_cfg("gmatch", "一般图匹配 GM",
                      "点图：解 = 边的优先序，按序贪心取边（两端都空闲才取）；红 = 匹配边；页面给出动态规划的精确最优作对照——P 类问题（Edmonds 带花算法）", "12 点随机连通加权图", 14),
    "freqasg": _es_cfg("freqasg", "频率分配 FAP",
                       "频率条：发射机取模分 6 频率，相邻频率冲突罚（T-着色）", "12 发射机 · 6 频率", 12),
    "rpostman": dict(page_domain="entryseq",
                preset_options={"n8": {"variant": "rpostman", "n": 8}, "n10": {"variant": "rpostman", "n": 10}},
                preset_labels={"n8": "14 路口 · 8 条必需边", "n10": "14 路口 · 10 条必需边"},
                custom_fields=[{"key": "n", "label": "规模 n", "min": 4, "max": 12, "val": 8}],
                extra_hint="灰线 = 路网；粗线 = 必须服务的边；一条从仓库方块出发的闭合回路覆盖全部必需边；虚线 = 空驶",
                heading="在线求解演示 · 乡村邮递员 RPP"),
    "rcpsp": _es_cfg("rcpsp", "资源受限项目调度 RCPSP",
                     "甘特：每行一个活动（宽度=工期），按串行调度生成方案排程；绿虚线=工期下界",
                     "12 活动 · 2 资源", 20),
})

# 2026-10 第一梯队新增：ATSP / 并行机调度 / 数分割 / k-means 聚类 / 工程约束设计
ABSTRACT_DEMO.update({
    "atsp": dict(page_domain="entryseq",
                 preset_options={"a12": {"variant": "atsp", "n": 12}, "a20": {"variant": "atsp", "n": 20},
                                 "a30": {"variant": "atsp", "n": 30}},
                 preset_labels={"a12": "12 城市（小）", "a20": "20 城市（中）", "a30": "30 城市（大）"},
                 custom_fields=[{"key": "n", "label": "城市数", "min": 5, "max": 30, "val": 12}],
                 extra_hint="箭头 = 行进方向；去程与回程代价不同，目标 = 沿箭头方向的代价之和",
                 heading="在线求解演示 · 非对称旅行商 ATSP"),
    "pms": dict(page_domain="entryseq",
                preset_options={"p12": {"variant": "pms", "n": 12}, "p24": {"variant": "pms", "n": 24},
                                "p40": {"variant": "pms", "n": 40}},
                preset_labels={"p12": "12 作业 · 3 机器", "p24": "24 作业 · 4 机器", "p40": "40 作业 · 5 机器"},
                custom_fields=[{"key": "n", "label": "作业数", "min": 6, "max": 40, "val": 12}],
                extra_hint="每行一台机器，色块 = 作业（宽度 ∝ 加工时间），绿虚线 = 下界；目标 = 最晚完工的那台",
                heading="在线求解演示 · 并行机调度 P||Cmax"),
    "numpart": dict(page_domain="entryseq",
                    preset_options={"n12": {"variant": "numpart", "n": 12}, "n24": {"variant": "numpart", "n": 24},
                                    "n40": {"variant": "numpart", "n": 40}},
                    preset_labels={"n12": "12 个数", "n24": "24 个数", "n40": "40 个数"},
                    custom_fields=[{"key": "n", "label": "数的个数", "min": 6, "max": 40, "val": 12}],
                    extra_hint="柱高 = 数值；红 = 集合 A，蓝 = 集合 B；目标 = 两组之和的差（0 = 完美划分）",
                    heading="在线求解演示 · 数分割"),
    "kmeans": dict(page_domain="entryseq",
                   preset_options={"k3": {"variant": "kmeans", "n": 12}, "k4": {"variant": "kmeans", "n": 25},
                                   "k6": {"variant": "kmeans", "n": 40}},
                   preset_labels={"k3": "3 簇 · 60 个点", "k4": "4 簇 · 80 个点", "k6": "6 簇 · 120 个点"},
                   extra_hint="同色点 = 同一簇；✕ = 聚类中心；目标 = 每个点到最近中心的距离平方之和",
                   heading="在线求解演示 · k-均值聚类"),
    "ecd": dict(page_domain="entryseq",
                preset_options={"wbeam": {"variant": "wbeam", "n": 4}, "pvessel": {"variant": "pvessel", "n": 4},
                                "tcspring": {"variant": "tcspring", "n": 3}, "reducer": {"variant": "reducer", "n": 7}},
                preset_labels={"wbeam": "焊接梁（4 变量 · 7 约束）", "pvessel": "压力容器（4 变量 · 4 约束）",
                               "tcspring": "拉压弹簧（3 变量 · 4 约束）", "reducer": "减速器（7 变量 · 11 约束）"},
                extra_hint="左：各设计变量在取值范围里的位置；右：约束 ✓ 满足 / ✗ 违反；对照文献最优值",
                heading="在线求解演示 · 工程约束设计"),
})

# 连续多目标基准：同一个域（mocont），ZDT 页与 DTLZ 页只是预设不同
ABSTRACT_DEMO.update({
    "zdt": dict(page_domain="mocont",
                preset_options={"zdt1": {"variant": "zdt1"}, "zdt2": {"variant": "zdt2"}, "zdt3": {"variant": "zdt3"},
                                "zdt4": {"variant": "zdt4"}, "zdt5": {"variant": "zdt5"}, "zdt6": {"variant": "zdt6"}},
                preset_labels={"zdt1": "ZDT1 · 凸前沿", "zdt2": "ZDT2 · 凹（非凸）前沿", "zdt3": "ZDT3 · 5 段不连续前沿",
                               "zdt4": "ZDT4 · 多峰（难）", "zdt5": "ZDT5 · 位串编码的欺骗问题（31 个离散最优点）",
                               "zdt6": "ZDT6 · 偏斜前沿"},
                custom_fields=[{"key": "n", "label": "决策变量数 n", "min": 2, "max": 100, "val": 30}],
                extra_hint="虚线（ZDT5 为空心圈）= 解析真前沿；灰点 = 种群；红点 = 当前非支配解；两个目标都是越小越好（越靠近左下越好）",
                heading="在线求解演示 · ZDT 双目标基准"),
    "dtlz": dict(page_domain="mocont",
                 preset_options={"dtlz2": {"variant": "dtlz2"}, "dtlz1": {"variant": "dtlz1"}, "dtlz3": {"variant": "dtlz3"},
                                 "dtlz4": {"variant": "dtlz4"}, "dtlz5": {"variant": "dtlz5"}, "dtlz6": {"variant": "dtlz6"},
                                 "dtlz7": {"variant": "dtlz7"}},
                 preset_labels={"dtlz2": "DTLZ2 · 球面前沿", "dtlz1": "DTLZ1 · 线性前沿 + 多峰（难）",
                                "dtlz3": "DTLZ3 · 球面前沿 + 大量局部前沿（很难）", "dtlz4": "DTLZ4 · 球面前沿，解密度极不均",
                                "dtlz5": "DTLZ5 · 前沿退化成一条曲线", "dtlz6": "DTLZ6 · 退化曲线 + 难收敛",
                                "dtlz7": "DTLZ7 · 4 块不连通的前沿"},
                 custom_fields=[{"key": "n", "label": "决策变量数 n", "min": 3, "max": 100, "val": 12}],
                 extra_hint="三个目标用斜投影画出（点色 = 目标3）；淡点 = 解析真前沿，圈 = 当前非支配解",
                 heading="在线求解演示 · DTLZ 三目标基准"),
    # 三大范式页：与 ZDT/DTLZ 共用 mocont 域，只是预设和解读不同（偏好 → R-NSGA-II；分解 → MOEA/D；指标 → IBEA）
    "prefmo": dict(page_domain="mocont",
                   preset_options={"zdt1": {"variant": "zdt1"}, "zdt2": {"variant": "zdt2"}, "dtlz2": {"variant": "dtlz2"}},
                   preset_labels={"zdt1": "ZDT1 · 凸前沿", "zdt2": "ZDT2 · 凹前沿", "dtlz2": "DTLZ2 · 三目标球面前沿"},
                   custom_fields=[{"key": "n", "label": "决策变量数 n", "min": 3, "max": 100, "val": 30}],
                   extra_hint="选 R-NSGA-II：黑色菱形 = 决策者给的参考点，种群只铺在它附近那一段前沿（所以 IGD 偏大是预期的）；对照 NSGA-II 铺满整条前沿",
                   heading="在线求解演示 · 偏好范式（参考点）"),
    "decompo": dict(page_domain="mocont",
                    preset_options={"zdt1": {"variant": "zdt1"}, "dtlz2": {"variant": "dtlz2"}, "dtlz1": {"variant": "dtlz1"}},
                    preset_labels={"zdt1": "ZDT1 · 凸前沿", "dtlz2": "DTLZ2 · 三目标球面前沿", "dtlz1": "DTLZ1 · 线性前沿 + 多峰（难）"},
                    custom_fields=[{"key": "n", "label": "决策变量数 n", "min": 3, "max": 100, "val": 30}],
                    extra_hint="选 MOEA/D：每个权重向量对应一个 Tchebycheff 子问题；对照 NSGA-II 看三目标前沿的铺开与 DTLZ1 的收敛",
                    heading="在线求解演示 · 分解范式（MOEA/D）"),
    "indicmo": dict(page_domain="mocont",
                    preset_options={"zdt1": {"variant": "zdt1"}, "zdt2": {"variant": "zdt2"}, "dtlz2": {"variant": "dtlz2"}},
                    preset_labels={"zdt1": "ZDT1 · 凸前沿", "zdt2": "ZDT2 · 凹前沿", "dtlz2": "DTLZ2 · 三目标球面前沿"},
                    custom_fields=[{"key": "n", "label": "决策变量数 n", "min": 3, "max": 100, "val": 30}],
                    extra_hint="选 IBEA：加性 ε 指标直接当适应度，不做支配排序；对照 NSGA-II 看 ZDT2 这类凹前沿上的差别",
                    heading="在线求解演示 · 指标范式（IBEA）"),
})


# ---- 新问题的演示配置：tools/new_problem.py 追加在这一行之前 ----


def demo_fragment_html(cfg):
    return _demo_fragment(**cfg) if cfg else None


def _interactive_page(*, path, title, desc, h1, lead, intro_html, controls_html,
                      preset_options, preset_labels, page_domain, extra_hint, bench_table, faq_html,
                      extra_html: str = "", custom_fields=None):
    _CRUMB_LABEL = {"/problem/knapsack/": "背包问题", "/problem/continuous/": "连续函数优化",
                    "/problem/multiobj/": "多目标优化", "/problem/graphcolor/": "图着色",
                    "/problem/binpack/": "装箱问题", "/problem/custom/": "自带问题"}
    crumb_label = _CRUMB_LABEL.get(path, path)
    body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<!--THEME_HEAD-->
<link rel="stylesheet" href="/css/style.css">
<link rel="canonical" href="<!--SITE-->{path}">
<script type="application/ld+json"><!--LDJSON--></script>
</head>
<body>
<a class="skip-link" href="#main">跳到主内容</a>
<nav class="nav"><div class="nav-inner">
  <a class="brand" href="/"><span class="logo">🐝</span>群智能算法百科</a>
  <div class="nav-links">
  <!--NAVLINKS-->
  </div>
  <!--THEME_BTN-->
</div></nav>

<div class="wrap" id="main" role="main">
  <div class="hero" style="padding-top:18px">
    <div class="crumbs"><a href="/">首页</a> · 问题库 · {crumb_label}</div>
    <h1 style="font-size:28px">{h1}</h1>
    <div class="sub">{lead}</div>
  </div>
  {intro_html}

  {_demo_fragment(page_domain=page_domain, preset_options=preset_options,
                  preset_labels=preset_labels, extra_hint=extra_hint,
                  custom_fields=custom_fields)}

  {bench_table}

  {extra_html}

  <h2>常见问题</h2>
  {faq_html}
</div>

<footer>
  <span class="fbrand">群智能算法百科</span>
  <span class="ver">v0.1.0</span>
  <span>算法由 Pyodide 在浏览器本地运行，数据不上传</span>
</footer>

<!--THEME_TAIL-->
</body>
</html>
"""
    return body


KNAPSACK_BENCH = """
<h2>实测参考（n=40，seed=7，200 代）</h2>
<div class="tablewrap"><table>
<tr><th>算法</th><th class="num">最优价值（越高越好）</th></tr>
<tr><td>随机搜索（基线）</td><td class="num">1398</td></tr>
<tr><td>爬山 HC</td><td class="num">1457</td></tr>
<tr><td>遗传 GA</td><td class="num">1456</td></tr>
<tr><td>模拟退火 SA</td><td class="num">1464</td></tr>
<tr><td>禁忌 TS</td><td class="num">1466</td></tr>
<tr><td>布谷鸟 CS</td><td class="num">1477</td></tr>
<tr><td>差分 DE（二进制版）</td><td class="num">1479</td></tr>
<tr><td>蜂群 ABC</td><td class="num">1479</td></tr>
<tr><td>鲸鱼 WOA</td><td class="num">1479</td></tr>
<tr><td>灰狼 GWO（bGWO 投票版）</td><td class="num">1479</td></tr>
</table></div>
<p class="hint">背包的贪心修复把搜索压在可行域内，算法间差距比 TSP 小——多数算法都能摸到 1479 附近。换更大实例（n=60+）差距会拉开。</p>
"""

# 2026-10 补充的经典基准（函数定义在 py/domains.py 的 _NEW_FUNCS；页面下拉里每个给 2 维和 10 维）
_NEW_FN_LABELS = {"griewank": "Griewank", "levy": "Lévy", "schwefel": "Schwefel（欺骗性）",
                  "zakharov": "Zakharov", "dixon_price": "Dixon–Price", "styblinski_tang": "Styblinski–Tang"}

CONTINUOUS_BENCH = """
<h2>实测参考（2D，seed=7，200 代）</h2>
<div class="tablewrap"><table>
<tr><th>算法</th><th class="num">Sphere</th><th class="num">Rastrigin</th></tr>
<tr><td>随机搜索（基线）</td><td class="num">1.08</td><td class="num">0.62</td></tr>
<tr><td>爬山 HC（带重启）</td><td class="num">≈0</td><td class="num">1.9</td></tr>
<tr><td>模拟退火 SA（带重启）</td><td class="num">≈0</td><td class="num">≈1.0</td></tr>
<tr><td>粒子群 PSO</td><td class="num">≈0</td><td class="num">0.001</td></tr>
<tr><td>差分进化 DE</td><td class="num">≈0</td><td class="num">0</td></tr>
<tr><td>灰狼 GWO</td><td class="num">≈0</td><td class="num">0</td></tr>
<tr><td>鲸鱼 WOA</td><td class="num">≈0</td><td class="num">0</td></tr>
<tr><td>正弦余弦 SCA</td><td class="num">≈0</td><td class="num">0</td></tr>
</table></div>
<p class="hint">注意 Rastrigin 列：随机搜索 0.62 比单链方法（SA/HC）还好——<strong>低维、评价便宜时均匀采样本来就是强基线</strong>，这是元启发式文献的常识但很少有人说破。种群算法（PSO/DE/GWO/WOA/SCA）靠群体多样性+精细收缩才能压到 0。</p>
"""

MULTIOBJ_BENCH = """
<h2>实测参考（n=40，seed=7，150 代）</h2>
<div class="tablewrap"><table>
<tr><th>算法</th><th class="num">最终非支配解数</th><th class="num">说明</th></tr>
<tr><td>随机搜索（档案基线）</td><td class="num">5</td><td>只会丢掉被支配点，增长慢</td></tr>
<tr><td>加权 GA（随机权重）</td><td class="num">1</td><td>种群坍缩到一个折中点——加权法的经典弱点</td></tr>
<tr><td>NSGA-II</td><td class="num">40（全种群非支配）</td><td>拥挤度机制主动保持前沿铺开</td></tr>
</table></div>
<p class="hint">这个对照就是多目标优化的核心一课：<strong>加权标量化会把多样性压没</strong>（还漏掉非凸前沿段），Pareto 框架才能铺开整条前沿。</p>
"""

GC_BENCH = """
<h2>实测参考（DSJC n=50 p=0.5，seed=7，200 代）</h2>
<div class="tablewrap"><table>
<tr><th>算法</th><th class="num">色数（越少越好）</th><th class="num">Σci²（塞紧度次级指标）</th></tr>
<tr><td>随机搜索（基线）</td><td class="num">12</td><td class="num">1418</td></tr>
<tr><td>爬山 HC</td><td class="num">11</td><td class="num">1099</td></tr>
<tr><td>模拟退火 SA</td><td class="num">11</td><td class="num">1295</td></tr>
<tr><td>禁忌 TS</td><td class="num">11</td><td class="num">1099</td></tr>
<tr><td>遗传 GA</td><td class="num">11</td><td class="num">1168</td></tr>
<tr><td>人工蜂群 ABC</td><td class="num">10</td><td class="num">1107</td></tr>
<tr><td>鲸鱼 WOA</td><td class="num">10</td><td class="num">1237</td></tr>
</table></div>
<p class="hint">注意色数列是<strong>阶梯状下降</strong>——色数是整数，算法大部分时间在同一个色数平台上优化 Σci²（把颜色用得更「紧凑」），攒够势能才降到下一个色数。DSJC 均匀随机图是文献标准硬实例：随机几何图上随机序 First-Fit 就近乎最优，测不出差距。</p>
"""

BP_BENCH = """
<h2>实测参考（n=40，容量 150，seed=7，200 代）</h2>
<div class="tablewrap"><table>
<tr><th>算法</th><th class="num">箱数（越少越好）</th><th class="num">Σ剩余²（塞紧度）</th></tr>
<tr><td>理论下界 LB</td><td class="num">16</td><td class="num">—</td></tr>
<tr><td>随机搜索（基线）</td><td class="num">17</td><td class="num">4110</td></tr>
<tr><td>爬山 HC</td><td class="num">16</td><td class="num">542</td></tr>
<tr><td>模拟退火 SA</td><td class="num">17</td><td class="num">3960</td></tr>
<tr><td>禁忌 TS</td><td class="num">17</td><td class="num">3460</td></tr>
<tr><td>遗传 GA</td><td class="num">16</td><td class="num">544</td></tr>
<tr><td>人工蜂群 ABC</td><td class="num">16</td><td class="num">580</td></tr>
<tr><td>鲸鱼 WOA</td><td class="num">16</td><td class="num">524</td></tr>
</table></div>
<p class="hint">箱数触到 LB=⌈Σ重量/容量⌉ 就是数学意义上的<strong>最优</strong>（不可能更少）——种群+memetic 系（GA/ABC/WOA/HC）都摸到了。SA/TS 箱数持平但塞紧度（Σ剩余²）明显更差：箱数平台期看次级指标。切到 60/80 件实例差距会拉开。</p>
"""


# ============================================================
# 组件百科页 /components/（P1.5）
# 数据来源：py/components.py 的 COMPONENTS 注册表（单一事实来源，import 而非复制）；
# 调用方计数在构建时对 py/solvers.py + py/domains.py 实测——组件删改页面自动同步。
# ============================================================
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "py"))
from components import COMPONENTS as _COMPONENTS  # noqa: E402

# 注册表 key → 源码里的真实函数名（用于调用方计数）
_KEY2FN = {
    "build_problem": ["build_problem("],
    "nearest_neighbor": ["nearest_neighbor("],
    "grasp_construct": ["_grasp_construct("],
    "two_opt": ["two_opt_improve("],
    "two_opt_shot": ["_random_2opt_shot("],
    "or_opt": ["_or_opt_move("],
    "double_bridge": ["_double_bridge("],
    "reverse_mut": ["_reverse_mutation("],
    "swap_seq": ["apply_swaps(", "swap_seq_to_target(", "_prefix("],
    "ox_crossover": ["_ox_crossover("],
    "random_key": ["_decode_position("],
    "roulette": ["_roulette("],
    "shared_edges": ["_shared_edges_ratio("],
}
_GROUP_ORDER = ["构造器", "局部搜索", "扰动", "交叉与序列", "编码"]


def _usage_counts():
    """构建时实测：每个组件函数在 solvers.py + domains.py 中的调用次数。"""
    src = ""
    py_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "py")
    parts_dir = _os.path.join(py_dir, "domains_parts")
    files = [_os.path.join(py_dir, "solvers.py")] + [_os.path.join(parts_dir, f) for f in sorted(_os.listdir(parts_dir)) if f.endswith(".py")]
    for path in files:
        with open(path, encoding="utf-8") as f:
            src += f.read()
    counts = {}
    for key, fns in _KEY2FN.items():
        counts[key] = sum(src.count(fn) for fn in fns)
    return counts


COMPONENTS_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>组件百科 · 元启发式算法的乐高积木（13 组件注册表）</title>
<meta name="description" content="元启发式算法组件化架构百科：13 个通用组件（构造器/局部搜索/扰动/交叉与序列/编码）的注册表、调用方实测计数、排列域 ctx 范式，算法=模板+组件的工程实践。">
<!--THEME_HEAD-->
<link rel="stylesheet" href="/css/style.css">
<link rel="canonical" href="<!--SITE-->/components/">
<script type="application/ld+json"><!--LDJSON--></script>
</head>
<body>
<a class="skip-link" href="#main">跳到主内容</a>
<nav class="nav"><div class="nav-inner">
  <a class="brand" href="/"><span class="logo">🐝</span>群智能算法百科</a>
  <div class="nav-links">
  <!--NAVLINKS-->
  </div>
  <!--THEME_BTN-->
</div></nav>

<div class="wrap" id="main" role="main">
  <div class="hero" style="padding-top:18px">
    <div class="crumbs"><a href="/">首页</a> · 组件百科</div>
    <div class="contrib-note"><b>📎 写给贡献者的页面</b>：这里讲的是本站的内部结构与收录进度，面向想参与维护、扩展算法或问题的人。只想用算法、学知识？回到 <a href="/encyclopedia/">百科总纲</a> 就够了。</div>
    <h1 style="font-size:28px">组件百科<br><span class="grad">算法不是 45 段独立代码，是模板 + 积木</span></h1>
    <div class="sub">这一页回答一个问题：「45 个算法背后的代码是怎么组织的」。先给结论：真正手写的只有<strong>算法主循环模板</strong>和 <strong>13 个通用组件</strong>——交换、插入、OX 交叉、双桥扰动、2-opt 下探……所有算法从同一张组件注册表里取件。新增一个算法的平均成本，从第一版的「一整天」降到组件化后的「一小时」。</div>
  </div>

  <h2>一、两层组件化架构</h2>
  <div class="tablewrap"><table>
    <tr><th>层级</th><th>组件是什么</th><th>单一事实来源</th><th>谁在用</th></tr>
    <tr><td><b>第一层：TSP 通用组件</b></td><td>13 个跨算法复用的函数（下表），覆盖构造→扰动→交叉→编码全流程</td><td><code>py/components.py</code> + COMPONENTS 注册表</td><td>45 个 TSP 算法（py/solvers.py）</td></tr>
    <tr><td><b>第二层：问题域引擎组件</b></td><td>域引擎骨架件：最优追踪 bump/argbest、二进制算子（均匀交叉/逐位变异/翻转）、贪心替换、排列域算子（OX/交换/插入/打磨）</td><td><code>py/domain_components.py</code>（S1-1 组件化）</td><td>背包/连续/多目标/图着色/装箱 5 域全部算法（py/domains.py）</td></tr>
    <tr><td><b>第三层：排列域算法库</b></td><td>_pm_* 系列通用排列算法（HC/SA/TS/GA/ABC/WOA 的排列版），域差异全部压进 ctx 解码器</td><td><code>py/domains.py</code>（内核收编自第二层组件装配）</td><td>图着色 + 装箱两个域的 7 算法——<strong>同一份代码</strong></td></tr>
  </table></div>
  <p>设计原则照搬 jMetal：算法 = 主循环模板 + 组件目录。组件只依赖「排列 + 距离/代价」这个最小接口，不关心具体问题——所以 2-opt 下探既服务 TSP 也服务 GRASP 的打磨步，OX 交叉在 GA/DE/TLBO/SFLA/SOS 五个家族里语义完全一致。</p>

  <h2>二、组件注册表（13 组件，调用数为构建时实测）</h2>
  <div class="tablewrap"><table>
    <tr><th>分组</th><th>组件</th><th>一句话说明</th><th>典型使用者</th><th>调用次数</th></tr>
    <!--COMPONENT_ROWS-->
  </table></div>
  <p class="hint">调用次数 = <code>py/solvers.py</code> + <code>py/domains.py</code> 中该函数（含别名包装）的出现次数，页面每次构建重新统计——你在算法页看到的每一个「交换邻域」「OX 交叉」，背后都是这里的一行。</p>

  <h2>三、七槽管线组件（S7-B：算法 = 模块组合）</h2>
  <p>组合配方引擎把算法拆成<b>七个固定槽位</b>：初始化 → 选择 → 交叉 → 变异 → 替换 → 局部搜索 → 终止。
  每个槽位从下表挑一个组件，一份「配方」就是一张装配清单——
  <a href="/algo/f6-hybrid/memetic/">Memetic 配方页</a>有完整示范。
  <b>本节组件全部是纯组件（composable: false）：不能自己跑，必须有宿主配方或算法。</b></p>
  <div class="tablewrap"><table>
    <tr><th>槽位（kind）</th><th>组件</th><th>IO</th><th>原始文献出处</th></tr>
    <!--RCOMPONENT_ROWS-->
  </table></div>
  <p class="hint">引擎保证：单一 RNG 顺序驱动（同种子逐位复现）、装配期未知组件校验、排列 IO 契约逐代验证（无重复城市）。</p>

  <h2>三、复用冠军与调用链故事</h2>
  <div class="tablewrap"><table>
    <tr><th>组件</th><th>为什么被反复复用</th></tr>
    <tr><td><b>2-opt 下探</b></td><td>排列域最强的通用局部搜索。它同时扮演三个角色：独立算法（2-opt/ILS/VNS 的本体）、播种抛光（几乎所有种群算法的 memetic 周期）、重置下探（SFLA 反射步 / SSA 警戒远跳的预算制下探）。一个函数三种用法。</td></tr>
    <tr><td><b>OX 顺序交叉</b></td><td>「从供体学习」在排列域的诚实翻译。连续域算法离散化时，凡是带「向好解移动/吸收特征」语义的（DE/TLBO/SFLA/SOS/GA），逐位抄会产生重复城市——OX 是文献标准解法，也是「是否真在优化」自动测试的重点照顾对象。</td></tr>
    <tr><td><b>双桥扰动</b></td><td>切 4 刀换段重排，产生的解不可被 2-opt 还原——这是 ILS「跳出局部最优」和 SFLA「重置蛙」能真正逃逸的数学保证。随机 2-opt 逆转太轻，双桥才够深。</td></tr>
    <tr><td><b>随机键编码</b></td><td>排列↔连续向量的双向映射。PSO/GSA/CEM 这些「原生连续」算法靠它在排列域工作：粒子位置是实数向量，解码时排序成排列。代价是解码有噪声（两个相近向量可能排出不同排列），这是这些算法离散化后变弱的主因之一。</td></tr>
  </table></div>

  <h2>四、排列域「问题适配」范式：一份代码服务两个域</h2>
  <p>图着色和装箱的 7 个算法（HC/SA/TS/GA/ABC/WOA + random 基线）<strong>只写了一份代码</strong>。秘密是 ctx 接口——域差异被压进五个方法：</p>
  <div class="tablewrap"><table>
    <tr><th>ctx 方法</th><th>图着色域</th><th>装箱域</th><th>TSP 对照</th></tr>
    <tr><td><code>random(rng)</code></td><td>随机顶点排列</td><td>随机物品排列</td><td>随机城市排列</td></tr>
    <tr><td><code>decode(perm)</code></td><td>FF 染色 → (色数, Σci²)</td><td>FF 装箱 → (箱数, Σ剩余²)</td><td>路径长度</td></tr>
    <tr><td><code>diff(a, b)</code></td><td colspan="2" style="text-align:center">字典序增量（供 SA 的 Metropolis 判据）</td><td>标量差</td></tr>
    <tr><td><code>solution(perm)</code></td><td>颜色数组（画染色图）</td><td>物品→箱分配（画柱状图）</td><td>路径序列</td></tr>
    <tr><td><code>polish(perm)</code></td><td colspan="2" style="text-align:center">_pm_polish 预算下探（供 SA 重启后使用）</td><td>2-opt 下探</td></tr>
  </table></div>
  <p>效果：给这两个域新增算法 = 抄一行模板；给排列域新增问题 = 只写一个 ctx（约 60 行）。「算法 = 机制，问题绑定 = 编码+解码」在这里从口号变成了代码结构。</p>

  <h2>五、组件化的收益与代价</h2>
  <div class="tablewrap"><table>
    <tr><th>做法</th><th>好处</th><th>主要风险</th></tr>
    <tr><td>每个算法各写一套邻域 / 扰动</td><td>单个算法自成一体，读代码不用跳转</td><td>代码漂移：同一个「交换」在不同文件里会出现细微不同的实现，对比实验的差别可能来自实现而不是算法</td></tr>
    <tr><td>算法主循环 + 从注册表取通用组件</td><td>新增算法只写主循环；同一个组件被所有算法共用，修一处全部受益，组件有独立测试</td><td>组件里的 bug 会传染所有调用方</td></tr>
    <tr><td>排列域 ctx（问题只写解码 / 邻域 / 评估）</td><td>新增一个排列问题只写一个 ctx，现有算法直接可用</td><td>各域的平台（plateau）特性差异大（见各域页的常见问题），算法默认参数必须按域实测标定</td></tr>
  </table></div>

  <h2>相关页面</h2>
  <div class="cards">
    <!--CARDS-->
  </div>
</div>

<footer>
  <span class="fbrand">群智能算法百科</span>
  <span class="ver">v0.1.0</span>
  <span>算法由 Pyodide 在浏览器本地运行，数据不上传</span>
</footer>

<!--THEME_TAIL-->
</body>
</html>
"""


def _components_rows():
    counts = _usage_counts()
    rows = []
    for grp in _GROUP_ORDER:
        members = [c for c in _COMPONENTS if c[2] == grp]
        first = True
        for key, name, _, desc, users in members:
            gcell = f'<td rowspan="{len(members)}"><b>{grp}</b></td>' if first else ""
            first = False
            n = counts.get(key, 0)
            ncell = f'<td class="num">{n}</td>' if n else '<td class="num" title="仅定义/仅测试引用">—</td>'
            rows.append(f'    <tr>{gcell}<td><code>{key}</code> {name}</td><td>{desc}</td><td>{users}</td>{ncell}</tr>')
    return "\n".join(rows)


def _rcomponents_rows():
    """S7-B：七槽管线组件表（数据源 py/recipe.py RCOMPONENTS，import 单一事实源）。"""
    import recipe as _recipe
    kind_zh = {"init": "初始化", "selection": "选择", "crossover": "交叉",
               "mutation": "变异", "replacement": "替换", "local_search": "局部搜索",
               "terminator": "终止"}
    rows = []
    for cid, c in _recipe.RCOMPONENTS.items():
        rows.append(f'    <tr><td>{kind_zh[c["kind"]]}（{c["kind"]}）</td>'
                    f'<td><code>{cid}</code></td><td><code>{c["io"]}</code></td>'
                    f'<td>{c["source"]}</td></tr>')
    return "\n".join(rows)


def _components_page_html():
    html = COMPONENTS_PAGE.replace("<!--COMPONENT_ROWS-->", _components_rows())
    html = html.replace("<!--RCOMPONENT_ROWS-->", _rcomponents_rows())
    html = html.replace("<!--CARDS-->", _domain_cards())
    return html


def _domain_algo_counts():
    """域算法数数据派生（文案数字铁律：禁止硬编码）——改注册表后数字自动同步。"""
    import domains as _d
    return {
        "knapsack": len(_d._KS_ALGOS), "graphcolor": len(_d._GC_ALGOS),
        "binpack": len(_d._BP_ALGOS), "continuous": len(_d._CN_ALGOS),
        "multiobj": len(_d._MO_ALGOS), "setcover": len(_d._SC_ALGOS),
        "sat": len(_d._SAT_ALGOS), "qubo": len(_d._BIN_ALGOS),
        "gap": len(_d._GAP_ALGOS), "uflp": len(_d._UF_ALGOS), "entryseq": len(_d._ES_ALGOS),
    }


def _pulled_cells_section():
    """覆盖矩阵页『未过门/撤下留痕』区块：数据驱动渲染 data/pulled_cells.json。
    框架口径=撤下是「真优化」校验门制度运作的证据，非缺陷。顶层无该数据时不渲染区块。
    数字全部从 JSON 派生（禁硬编码）。"""
    import os
    path = os.path.join(os.path.dirname(__file__), "data", "pulled_cells.json")
    if not os.path.exists(path):
        return ""  # 顶层无该数据 → 不渲染区块
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return ""
    cells = data.get("cells", [])
    if not cells:
        return ""
    n_total = len(cells)
    n_pulled = sum(1 for c in cells if c.get("status") == "pulled")
    n_rework = sum(1 for c in cells if c.get("status") == "awaiting-rework")

    def _status_badge(st):
        if st == "pulled":
            return '<span style="color:#b00;font-weight:600">已撤下</span>'
        if st == "awaiting-rework":
            return '<span style="color:#b8860b;font-weight:600">重做中</span>'
        return f'<span>{st}</span>'

    rows = []
    for c in cells:
        cell = f'{c.get("domain", "—")} × {c.get("algo", "—")}'
        rows.append(
            f'<tr><td>{cell}</td><td>{c.get("level", "—")}</td>'
            f'<td>{c.get("reason", "")}</td><td class="num">{c.get("metric", "—")}</td>'
            f'<td>{_status_badge(c.get("status"))}</td></tr>')
    body = "\n".join(rows)
    return f"""  <h2 id="pulled">更早的撤下留痕（内核级与逐格撤下）</h2>
  <p class="lead">撤下是校验制度在运作，<b>不是缺陷</b>：在更严的口径下（随机基线取同一种子下的最优值）过不了门的算法或内核，会撤下并留痕。上面的「同等评估预算实测」是现行口径；本节是更早批次留下的记录。本站共记录 <b>{n_total}</b> 条：
  <b>{n_pulled}</b> 条已撤下、<b>{n_rework}</b> 条其他线重做中。</p>
  <div class="tblwrap"><table class="tbl">
    <thead><tr><th>格（域 × 算法）</th><th>层级</th><th>原因</th><th class="num">数字/证据</th><th>状态</th></tr></thead>
    <tbody>
{body}
    </tbody>
  </table></div>
  <p class="hint">口径说明：内核级撤下=整族机制在离散语境退化（如 GSA 引力项、HS 记忆考量）；域级撤下=某算法在某域未过门（逐格留痕，源码注释存证据）。
  护士排班、赛程生成、设施选址和旅行锦标赛曾作为词条级演示撤下，后来用专业建模或专属内核重做并通过校验后重新上线，目前没有词条级的撤下记录。
  详见 <a href="/discovery/">候选发现池</a> 的收录闸门记录。</p>
"""


_DOMAIN_CN = {
    "continuous": "连续函数优化", "knapsack": "0-1 背包", "kpvar": "背包变体谱系", "setcover": "集合覆盖",
    "sat": "布尔可满足性", "qubo": "QUBO / 伊辛", "uflp": "无容量设施选址", "gap": "广义指派",
    "graphcolor": "图着色", "gcvar": "着色变体谱系", "binpack": "装箱", "bpvar": "装箱变体谱系",
    "entryseq": "词条域（调度 / 路径 / 选址 / 图问题 / 黑箱……）", "multiobj": "多目标（背包）",
    "mocont": "连续多目标基准（ZDT / DTLZ）", "custom": "自带问题",
    "nrp": "护士排班", "etp": "考试时间表", "ttp": "旅行锦标赛", "sls": "赛程生成",
}


def _fair_budget_section():
    """覆盖矩阵页「同等评估预算实测」：数据来自 data/fair_budget_summary.json 与 data/withdrawn_cells.json
    （由 tools/fair_budget.py → tools/gen_fair_summary.py 生成）。没有这份数据时不渲染。"""
    import os
    root = os.path.dirname(__file__)
    sp = os.path.join(root, "data", "fair_budget_summary.json")
    if not os.path.exists(sp):
        return ""
    s = json.load(open(sp, encoding="utf-8"))
    wp = os.path.join(root, "data", "withdrawn_cells.json")
    wd = json.load(open(wp, encoding="utf-8")) if os.path.exists(wp) else {"cells": {}}
    m, tot = s["meta"], s["total"]
    pct = lambda x: f"{100 * x / max(1, tot['cells']):.0f}"  # noqa: E731
    rows = []
    for dom, c in s["by_domain"].items():
        rows.append(f'<tr><td>{_DOMAIN_CN.get(dom, dom)}</td><td class="num">{c["cells"]}</td>'
                    f'<td class="num">{c["win"]}</td><td class="num">{c["tie"]}</td><td class="num">{c["loss"]}</td>'
                    f'<td class="num">{c.get("withdrawn", 0)}</td></tr>')
    wrows = []
    for key, c in sorted(wd["cells"].items()):
        dom, var, algo = key.split("/")
        wrows.append(f'<tr><td>{_DOMAIN_CN.get(dom, dom)}</td><td>{"" if var == "-" else var}</td><td><code>{algo}</code></td>'
                     f'<td class="num">{c["gain"] * 100:.1f}%</td></tr>')
    withdrawn_html = (f'<details><summary>已撤下的 {len(wrows)} 个格子（域 × 变体 × 算法）</summary>\n'
                      '<div class="tblwrap"><table class="tbl"><thead><tr><th>问题域</th><th>变体</th><th>算法</th>'
                      '<th class="num">相对随机搜索</th></tr></thead><tbody>\n' + "\n".join(wrows) +
                      '\n</tbody></table></div></details>') if wrows else ""
    return f"""  <h2 id="fairbudget">同等评估预算实测</h2>
  <p class="lead">每个「问题域 × 变体 × 算法」格子都和<b>随机搜索</b>比过一次，而且<b>评估次数相同</b>：算法自己每次运行用了多少次目标函数评估，随机搜索就给多少次。
  {m["iters"]} 代、{len(m["seeds"])} 个实例种子（种子同时决定实例，{m["seeds"][0]}–{m["seeds"][-1]}），取中位数；相对差距在 ±{m["margin"] * 100:.1f}% 以内算平手。
  共 <b>{tot["cells"]}</b> 格：明显胜过随机搜索 <b>{tot["win"]}</b>（{pct(tot["win"])}%）· 平手 <b>{tot["tie"]}</b>（{pct(tot["tie"])}%）· 不如随机搜索 <b>{tot["loss"]}</b>（{pct(tot["loss"])}%）。
  输了的格子用 {m.get("confirmed") or 9} 个种子复测，仍然输的就撤下（<b>{tot.get("withdrawn", 0)}</b> 格，见下），不再出现在算法下拉框里。</p>
  <div class="tblwrap"><table class="tbl">
    <thead><tr><th>问题域</th><th class="num">格数</th><th class="num">胜</th><th class="num">平</th><th class="num">负</th><th class="num">已撤下</th></tr></thead>
    <tbody>
{chr(10).join(rows)}
    </tbody>
  </table></div>
  <h3>怎么读这张表（局限，请读）</h3>
  <ul>
    <li>「胜过随机搜索」是<b>低门槛</b>：它说明算法在这个模型上确实在搜索，不说明它比该问题的专用算法好。</li>
    <li>只有 {len(m["seeds"])} 个种子（每个种子是一个新实例）：这是小样本，格子里的结论是<b>这几个实例上的观察</b>，不是统计意义上的普适结论。边缘附近的格子换种子可能翻转（所以输的格子要用更多种子复测）。</li>
    <li>实例是随机生成的小规模教学实例，不是文献基准；有些问题（如能精确求解的网络流、匹配）随机搜索本来就很强或算法根本不该用——它们在这里是教学对照。</li>
    <li><b>撤下不等于「这个算法不好」</b>，只表示在这个模型、这个预算下它没有赢过随机搜索；换预算、换编码、调参都可能改变结果。</li>
    <li>评估次数相同不等于时间相同：有的算法每次评估之外还有额外开销。</li>
  </ul>
  {withdrawn_html}
"""


def _coverage_page_html():
    """域×算法覆盖矩阵页（用户原子架构构想的看板）：概览表 + 原子内核×域明细表。"""
    import domains as _dom

    DOMAINS_CFG = [
        ("continuous", "连续函数优化", _dom._CN_ALGOS, "实向量", "cn"),
        ("knapsack", "0-1 背包", _dom._KS_ALGOS, "位向量", "ks"),
        ("kpvar", "背包变体谱系", _dom._KPVAR_ALGOS, "位/指派", "kpvar"),
        ("setcover", "集合覆盖", _dom._SC_ALGOS, "位向量", "sc"),
        ("sat", "布尔可满足性", _dom._SAT_ALGOS, "位向量", "sat"),
        ("qubo", "QUBO/伊辛", _dom._BIN_ALGOS, "位向量", "qubo"),
        ("uflp", "无容量设施选址", _dom._UF_ALGOS, "位向量", "uf"),
        ("gap", "广义指派", _dom._GAP_ALGOS, "指派向量", "gap"),
        ("graphcolor", "图着色", _dom._GC_ALGOS, "排列", "gc"),
        ("gcvar", "着色变体谱系", _dom._GCVAR_ALGOS, "排列/位串", "gcvar"),
        ("binpack", "装箱", _dom._BP_ALGOS, "排列", "bp"),
        ("bpvar", "装箱变体谱系", _dom._BPVAR_ALGOS, "排列", "bpvar"),
        ("entryseq", "原子词条域", _dom._ES_ALGOS, "排列/向量", "es"),
        ("multiobj", "多目标", _dom._MO_ALGOS, "实向量", "mo"),
        # 排程三域（2026-09-29 完善战役回挂）：专属整数编码内核（ga/de/gwo/cs+交换邻域），无原子适配层
        ("nrp", "护士排班", _dom._DOMAINS["nrp"]["algos"], "指派向量", "nrp"),
        ("etp", "考试时间表", _dom._DOMAINS["etp"]["algos"], "指派向量", "etp"),
        ("ttp", "旅行锦标赛", _dom._DOMAINS["ttp"]["algos"], "轮次排列", "ttp"),
        ("sls", "赛程生成", _dom._DOMAINS["sls"]["algos"], "轮次排列", "sls"),
    ]
    total = sum(len(r[2]) for r in DOMAINS_CFG)
    atom_total = sum(sum(1 for k in r[2] if k.startswith(("bv_", "pk_", "as_"))) for r in DOMAINS_CFG)

    rows = []
    for slug, cn, reg, enc, _short in DOMAINS_CFG:
        nbv = sum(1 for k in reg if k.startswith("bv_"))
        npk = sum(1 for k in reg if k.startswith("pk_"))
        nas = sum(1 for k in reg if k.startswith("as_"))
        native = len(reg) - nbv - npk - nas
        hub = {"kpvar": "knapsack", "gap": "assignment", "gcvar": "graphcolor",
               "bpvar": "binpack", "entryseq": ""}.get(slug, slug)  # 终审3：变体谱系/词条域无独立页→链 hub；排程四域均有同名词条页（2026-09-29 正名后）
        href = f"/problem/{hub}/" if hub else "/problem/"
        rows.append(f"""      <tr><td><a href="{href}">{cn}</a></td><td>{enc}</td>
        <td><b>{len(reg)}</b></td><td>{nbv or '—'}</td><td>{npk or '—'}</td><td>{nas or '—'}</td>
        <td>{native}</td></tr>""")
    overview = "\n".join(rows)

    # 原子内核 × 域明细（行=内核，列=13 域——多目标域不参与通用内核）
    _NAMES = [("fa", "萤火虫 FA"), ("ba", "蝙蝠 BA"), ("jaya", "Jaya"), ("tlbo", "TLBO"),
              ("pso", "粒子群 PSO"), ("sca", "正弦余弦 SCA"), ("mfo", "蛾焰 MFO"),
              ("eo", "均衡 EO"), ("ao", "天鹰 AO"), ("sma", "黏菌 SMA"),
              ("cem", "交叉熵 CEM"), ("cmaes", "CMA-ES（对角近似）")]
    KERNELS = ([("bv_" + s, nm + " · 位") for s, nm in _NAMES]
               + [("pk_" + s, nm + " · 排列") for s, nm in _NAMES]
               + [("as_" + s, nm + " · 指派") for s, nm in _NAMES])
    SHORT = [("continuous", "连续", _dom._CN_ALGOS), ("knapsack", "背包", _dom._KS_ALGOS),
             ("setcover", "覆盖", _dom._SC_ALGOS), ("sat", "SAT", _dom._SAT_ALGOS),
             ("qubo", "QUBO", _dom._BIN_ALGOS), ("uflp", "设施", _dom._UF_ALGOS),
             ("kpvar", "背变", _dom._KPVAR_ALGOS), ("gap", "指派", _dom._GAP_ALGOS),
             ("graphcolor", "着色", _dom._GC_ALGOS), ("gcvar", "着变", _dom._GCVAR_ALGOS),
             ("binpack", "装箱", _dom._BP_ALGOS), ("bpvar", "箱变", _dom._BPVAR_ALGOS),
             ("entryseq", "词条", _dom._ES_ALGOS)]
    krows = []
    for key, nm in KERNELS:
        cells = []
        for _slug, _cn, reg in SHORT:
            ck = key if not key.startswith("pk_") else key  # pk 键同名
            has = ck in reg
            cells.append('<td class="ok">✓</td>' if has else '<td class="no">·</td>')
        krows.append(f"      <tr><td>{nm}</td>{''.join(cells)}</tr>")
    kdetail = "\n".join(krows)
    head_cells = "".join(f'<th>{cn}</th>' for _s, cn, _r in SHORT)

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>域×算法覆盖矩阵 · 原子架构看板</title>
<meta name="description" content="每个问题域可跑的全部算法：位向量/排列/指派三大原子适配层的覆盖状态，全部通过严口径「真优化」校验门。">
<link rel="canonical" href="<!--SITE-->/coverage/">
<meta property="og:title" content="域×算法覆盖矩阵 · 原子架构看板">
<meta property="og:description" content="每个问题域可跑的全部算法：三大原子适配层覆盖状态一览。">
<meta property="og:image" content="<!--SITE-->/assets/og-cover.png">
<!--THEME_HEAD-->
<link rel="stylesheet" href="/css/style.css">
</head>
<body>
<a class="skip-link" href="#main">跳到主内容</a>
<nav class="nav"><div class="nav-inner">
  <a class="brand" href="/"><span class="logo">🐝</span>群智能算法百科</a>
  <div class="nav-links">
  <!--NAVLINKS-->
  </div>
  <!--THEME_BTN-->
</div></nav>
<main class="wrap" id="main">
  <div class="contrib-note"><b>📎 写给贡献者的页面</b>：这里讲的是本站的内部结构与收录进度，面向想参与维护、扩展算法或问题的人。只想用算法、学知识？回到 <a href="/encyclopedia/">百科总纲</a> 就够了。</div>
  <h1>域×算法 覆盖矩阵<br><span class="grad">原子架构看板</span></h1>
  <p class="lead">算法原子（内核）× 问题原子（ctx 协议）× 声明式注册——每个问题域尽可能对应所有收纳实现的算法。
  三大原子适配层：<b>bv 系</b>（位向量，sigmoid 二值化）、<b>pk 系</b>（排列，随机键 Bean 1994）、<b>as 系</b>（指派，round+clamp）。
  每格都要在<b>同等评估预算</b>下与随机搜索比较（见下方「同等评估预算实测」），没有稳定胜出的格子会被撤下。</p>

  <h2>各域算法概览（合计 __TOTAL__ 格，其中原子适配 __ATOM__ 格）</h2>
  <div class="tblwrap"><table class="tbl">
    <thead><tr><th>问题域</th><th>编码类</th><th>算法总数</th><th>bv（位）</th><th>pk（排列）</th><th>as（指派）</th><th>域原生</th></tr></thead>
    <tbody>
__OVERVIEW__
    </tbody>
  </table></div>

  <h2>原子内核 × 域 覆盖明细（✓ = 该域可跑且过门）</h2>
  <p class="hint">TSP 主域另有 45 个专属算法（页面见算法总览）。多目标域为 NSGA 系专属算法；排程三域（护士排班/考试时间表/赛程生成）为专属整数编码内核（交换邻域 + 整数 GA/DE/GWO/CS）——三者均不参与通用原子内核，故不在下方明细表出现。</p>
  <div class="tblwrap"><table class="tbl">
    <thead><tr><th>内核（12 算法 × 3 适配层）</th>__HEAD__</tr></thead>
    <tbody>
__KROWS__
    </tbody>
  </table></div>

  <p class="hint">撤下记录：跨域系统性失效的内核（如 GSA 引力项在离散语境退化、HS 记忆考量收敛不足）整族撤下；
  域特定失效逐格撤下；CMA-ES 位 / 排列 / 指派版是对角协方差的简化版。</p>

<!--FAIRBUDGET-->
<!--PULLED-->
</main>
<footer>
  <span class="fbrand">群智能算法百科</span>
  <span class="ver">v0.1.0</span>
  <span>算法由 Pyodide 在浏览器本地运行，数据不上传</span>
</footer>
<!--THEME_TAIL-->
</body>
</html>"""
    html = html.replace("__TOTAL__", str(total)).replace("__ATOM__", str(atom_total))
    html = html.replace("__OVERVIEW__", overview).replace("__KROWS__", kdetail).replace("__HEAD__", head_cells)
    html = html.replace("<!--FAIRBUDGET-->", _fair_budget_section())
    html = html.replace("<!--PULLED-->", _pulled_cells_section())
    return html


def _discovery_page_html():
    """候选发现池面板页（/discovery/）：数据驱动渲染 data/discovery.json 候选池。
    列=名称/家族/五闸门/证据强度/proposed→admitted 状态/分类；数字全数据派生。
    admitted 条目动态链接到已建页面（查 algos.json / problems.json，无需在 discovery.json 里硬编码 slug）。"""
    import os
    root = os.path.dirname(__file__)
    disc = json.load(open(os.path.join(root, "data", "discovery.json"), encoding="utf-8"))
    algos = json.load(open(os.path.join(root, "data", "algos.json"), encoding="utf-8"))
    fams = json.load(open(os.path.join(root, "data", "families.json"), encoding="utf-8"))
    probs = json.load(open(os.path.join(root, "data", "problems.json"), encoding="utf-8"))
    cands = disc.get("candidates", [])
    fam_name = {f["id"]: f["name"] for f in fams}
    algo_by_name = {a["name"]: a for a in algos}
    at_by_name = {t["name"]: t for t in probs.get("abstract_types", [])}

    n_total = len(cands)
    n_admitted = sum(1 for c in cands if c.get("status") == "admitted")
    n_proposed = sum(1 for c in cands if c.get("status") == "proposed")

    def _gate_badge(g):
        if g == "pass":
            return '<span style="color:#0a7d2c;font-weight:600">✓</span>'
        return '<span style="color:#b00;font-weight:600">✗</span>'

    def _status_badge(st):
        if st == "admitted":
            return '<span style="color:#0a7d2c;font-weight:600">已纳入</span>'
        if st == "proposed":
            return '<span style="color:#1a5fb4;font-weight:600">待纳入</span>'
        if st == "rejected":
            return '<span style="color:#b00;font-weight:600">已拒绝</span>'
        return f'<span>{st}</span>'

    rows = []
    for c in cands:
        name = c.get("name", "")
        en = c.get("en", "")
        # 动态链接：admitted 且能在已建页面中找到同名条目才挂链
        target = ""
        if c.get("status") == "admitted":
            if c.get("type") == "algo" and name in algo_by_name:
                a = algo_by_name[name]
                fam_dir = [f["dir"] for f in fams if f["id"] == a["family"]]
                slug = a.get("slug", "")
                if fam_dir and slug:
                    target = f'/algo/{fam_dir[0]}/{slug[:-4]}/'
            elif c.get("type") == "problem" and name in at_by_name:
                t = at_by_name[name]
                if t.get("status") == "page" and t.get("dir"):
                    target = f'/problem/{t["dir"]}/'
        name_cell = f'<a href="{target}">{name}</a>' if target else name
        if en:
            name_cell += f'<br><span class="hint">{en}</span>'

        # 家族列
        if c.get("type") == "algo":
            fam = fam_name.get(c.get("family", ""), c.get("family", "—"))
        else:
            fam = "问题候选"

        # 五闸门
        gates = c.get("gates", {}) or {}
        gate_cells = "".join(
            f'<td style="text-align:center">{_gate_badge(gates.get(k, ""))}</td>'
            for k in ("A", "B", "C", "D", "E"))
        n_pass = sum(1 for k in ("A", "B", "C", "D", "E") if gates.get(k) == "pass")
        evidence = c.get("evidence", "") or ""
        ev_short = evidence if len(evidence) <= 80 else evidence[:80] + "…"
        strength = (f'<b>{n_pass}/5</b> 门过'
                    f'<br><span class="hint" title="{evidence.replace(chr(34), "")}">{ev_short}</span>')
        if c.get("src"):
            strength += f'<br><span class="hint">src: {c["src"][:40]}</span>'

        status_cell = _status_badge(c.get("status"))
        cat = f'{c.get("verdict", "—")} · {c.get("type", "—")}'

        rows.append(
            f'<tr><td>{name_cell}</td><td>{fam}</td>'
            f'<td style="text-align:center">{gate_cells}</td>'
            f'<td>{strength}</td><td>{status_cell}</td><td>{cat}</td></tr>')
    body = "\n".join(rows)

    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>候选发现池 · 收录闸门留痕</title>
<meta name="description" content="本站算法/问题候选发现池：五闸门评分、证据强度与 proposed→admitted 收录状态全谱，数据驱动渲染。">
<link rel="canonical" href="<!--SITE-->/discovery/">
<meta property="og:title" content="候选发现池 · 收录闸门留痕">
<meta property="og:description" content="五闸门评分、证据强度与收录状态全谱。">
<meta property="og:image" content="<!--SITE-->/assets/og-cover.png">
<!--THEME_HEAD-->
<link rel="stylesheet" href="/css/style.css">
</head>
<body>
<a class="skip-link" href="#main">跳到主内容</a>
<nav class="nav"><div class="nav-inner">
  <a class="brand" href="/"><span class="logo">🐝</span>群智能算法百科</a>
  <div class="nav-links">
  <!--NAVLINKS-->
  </div>
  <!--THEME_BTN-->
</div></nav>
<main class="wrap" id="main">
  <div class="contrib-note"><b>📎 写给贡献者的页面</b>：这里讲的是本站的内部结构与收录进度，面向想参与维护、扩展算法或问题的人。只想用算法、学知识？回到 <a href="/encyclopedia/">百科总纲</a> 就够了。</div>
  <h1>候选发现池<br><span class="grad">收录闸门留痕</span></h1>
  <p class="lead">本站所有拟收录的算法与问题候选，都先进入这个发现池，按 <a href="/encyclopedia/">五闸门</a>（A 可溯源 / B 装配等价 / C 已发表 / D 影响力 / E 可落引擎）评分，再决定 proposed→admitted（或 rejected）。
  共 <b>__NTOTAL__</b> 条候选：<b>__NADMITTED__</b> 条已纳入、<b>__NPROPOSED__</b> 条待纳入。所有数字从 data/discovery.json 派生。</p>

  <p class="hint">诚实口径：被标『批评词条』的候选多属换皮隐喻量产线（机制等价于已收录群智能），按五闸门 B/E 落批评词条而非独立收录；这恰是发现池的过滤价值，不是缺陷。</p>

  <div class="row" style="margin:14px 0">
    <input id="discFilter" type="text" placeholder="过滤：名称 / 家族 / 分类 / 状态…" style="max-width:360px;padding:8px">
    <span class="hint" id="discCount" style="margin-left:10px"></span>
  </div>

  <div class="tblwrap"><table class="tbl" id="discTable">
    <thead><tr><th>名称</th><th>家族</th><th style="text-align:center">五闸门 (A B C D E)</th><th>证据强度</th><th>状态</th><th>分类</th></tr></thead>
    <tbody>
__BODY__
    </tbody>
  </table></div>

  <p class="hint">已纳入（admitted）且本站已有同名页面的候选，名称可点击跳转到对应页面（如 CMA-ES 算法页、各抽象问题页）；纯词条/批评词条无独立页，跳转回 <a href="/problem/reductions/">归约页</a> 全谱。
  与 <a href="/coverage/">覆盖矩阵</a> 互链：覆盖矩阵看『已上线的域×算法』，本页看『从候选到收录的全过程』。</p>
</main>
<script>
(function(){
  var inp = document.getElementById('discFilter');
  var tbl = document.getElementById('discTable');
  var cnt = document.getElementById('discCount');
  if (!inp || !tbl) return;
  function apply(){
    var q = inp.value.trim().toLowerCase();
    var rows = tbl.tBodies[0].rows;
    var shown = 0;
    for (var i=0;i<rows.length;i++){
      var t = rows[i].textContent.toLowerCase();
      var ok = !q || t.indexOf(q) >= 0;
      rows[i].style.display = ok ? '' : 'none';
      if (ok) shown++;
    }
    if (cnt) cnt.textContent = '显示 ' + shown + ' / ' + rows.length;
  }
  inp.addEventListener('input', apply);
  apply();
})();
</script>
<footer>
  <span class="fbrand">群智能算法百科</span>
  <span class="ver">v0.1.0</span>
  <span>算法由 Pyodide 在浏览器本地运行，数据不上传</span>
</footer>
<!--THEME_TAIL-->
</body>
</html>"""
    html = html.replace("__NTOTAL__", str(n_total)).replace("__NADMITTED__", str(n_admitted)).replace("__NPROPOSED__", str(n_proposed))
    html = html.replace("__BODY__", body)
    return html


def _mo_mechanism_section():
    """problem/multiobj 页『算法机制』区块：数据驱动渲染 data/mo_algos.json。
    nsga2/moead/spea2/wsga 四算法的 name/desc/principle/params/faq（精简版，经典可查）。"""
    import os
    path = os.path.join(os.path.dirname(__file__), "data", "mo_algos.json")
    if not os.path.exists(path):
        return ""
    try:
        data = json.load(open(path, encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return ""
    algos = data.get("algos", [])
    if not algos:
        return ""

    cards = []
    for a in algos:
        principle = "".join(f"<li>{p}</li>" for p in a.get("principle", []))
        params = a.get("params", [])
        param_rows = "".join(
            f'<tr><td><code>{p[0]}</code></td><td class="num">{p[1]}</td><td>{p[2]}</td></tr>'
            for p in params) if params else '<tr><td colspan="3" class="hint">（无参数）</td></tr>'
        faqs = a.get("faq", [])
        faq_html = "\n  ".join(
            f'<details class="faq-item"><summary>{q}</summary><div class="faq-body">{ans}</div></details>'
            for q, ans in faqs) if faqs else '<p class="hint">（无）</p>'
        cards.append(f"""    <div class="mo-algo-card">
      <h3>{a.get("name", "")} <span class="hint">[{a.get("family", "")}]</span></h3>
      <p>{a.get("desc", "")}</p>
      <h4>机制</h4>
      <ul class="mo-principle">{principle}</ul>
      <h4>关键参数</h4>
      <div class="tblwrap"><table class="tbl">
        <thead><tr><th>参数</th><th class="num">默认</th><th>说明</th></tr></thead>
        <tbody>{param_rows}</tbody>
      </table></div>
      <h4>常见问题</h4>
      {faq_html}
    </div>""")
    body = "\n".join(cards)
    return f"""  <h2 id="mo-mechanism">算法机制（多目标四主流）</h2>
  <p class="lead">本站演示默认用 <b>NSGA-II</b> 求双目标背包前沿；下面把当代多目标的两大主干（支配式 NSGA-II / 分解式 MOEA/D）、同代双雄（SPEA2）与对照基线（加权标量化）机制并列，方便对照理解。
  三目标扩展（maop，NSGA-II 泛化到 3 维）见演示区「三目标背包 · 40 件」预设：<a href="/problem/multiobj/#demo">/problem/multiobj/#demo</a>（选 m40）。</p>
  <div class="mo-algo-grid">
{body}
  </div>
  <p class="hint">文献出处（逐条可查）——NSGA-II 取 Deb et al. 2002 非支配排序+拥挤度；MOEA/D 取 Zhang &amp; Li 2007 分解；SPEA2 取 Zitzler et al. 2001 强度 Pareto；加权标量化是教材通法（非单一作者）。
  诚实简化处已在各条目「机制」中标明（如 MOEA/D 三目标用随机归一化权重而非经典 Das-Dennis 全网格）。</p>
"""


_COVERAGE_META = [  # (域 id, 展示名, 编码, 约束处理, 目标, 规模/变体, 演示链接)
    ("tsp", "TSP（组合）", "排列", "—（天然可行）", "单目标", "5–500 城市任意输入（基准实测 30/60/100）", '<a href="/">首页演示</a> + 各算法页'),
    ("knapsack", "0-1 背包（二进制）", "0/1 向量", "贪心修复算子", "单目标", "预设 / 自定义 / 上传", '<a href="/problem/knapsack/">背包演示</a>'),
    ("kpvar", "背包变体（10 种）", "0/1 向量 / 指派向量", "贪心或 one-hot 修复", "单目标", "有界/无界/多维/二次/子集和/折扣…", '<a href="/problem/knapsack/">背包枢纽</a>'),
    ("continuous", "连续函数基准", "实数向量", "边界钳制", "单目标", "{n_funcs} 个函数，可调维度", '<a href="/problem/continuous/">连续演示</a>'),
    ("multiobj", "多目标背包", "0/1 向量", "贪心修复算子", "双/三目标 Pareto", "预设 / 自定义", '<a href="/problem/multiobj/">NSGA-II 演示</a>'),
    ("binpack", "一维装箱（组合）", "排列（FF 装箱解码）", "—（构造保证可行）", "单目标 + 次级 Σ剩余²", "预设 / 自定义 / 上传", '<a href="/problem/binpack/">装箱演示</a>'),
    ("bpvar", "装箱变体", "排列", "—（解码保证可行）", "单目标", "变尺寸 / 二维 / 条带", '<a href="/problem/vsbinpack/">变尺寸装箱</a>'),
    ("graphcolor", "图着色（组合）", "排列（FF 着色解码）", "—（构造保证合法）", "单目标 + 次级 Σci²", "DSJC 随机图 / 上传", '<a href="/problem/graphcolor/">图着色演示</a>'),
    ("gcvar", "着色变体", "排列 / 位串", "颜色表、预着色约束", "单目标", "列表/预着色/边/全着色/最大独立集", '<a href="/problem/listcolor/">着色变体</a>'),
    ("setcover", "集合覆盖", "0/1 向量", "未覆盖罚", "单目标", "预设 / 上传", '<a href="/problem/setcover/">集合覆盖演示</a>'),
    ("sat", "可满足性（SAT）", "0/1 向量", "—", "最小化未满足子句", "预设 / DIMACS 上传", '<a href="/problem/sat/">SAT 演示</a>'),
    ("qubo", "QUBO", "0/1 向量", "—", "单目标", "预设 / 矩阵上传", '<a href="/problem/qubo/">QUBO 演示</a>'),
    ("gap", "广义指派（GAP）", "指派向量", "超载罚 + 修复", "单目标", "预设 / 上传", '<a href="/problem/assignment/">分配与选址</a>'),
    ("uflp", "无容量设施选址", "0/1 向量", "最近开设设施指派", "单目标", "预设 / 上传", '<a href="/problem/uflp/">选址演示</a>'),
    ("entryseq", "词条域（VRP、调度、选址、图问题、黑箱…）", "排列 / 实向量", "各变体不同", "各变体不同", "{n_variants} 个变体", '<a href="/problem/">问题总览</a>'),
]


def _coverage_rows():
    """百科总纲「本站覆盖矩阵」：算法数来自引擎注册表，保真度来自 py/entryseq.py 的登记——不再手写。"""
    import domains as _d
    import registry
    counts = _domain_algo_counts()
    counts["tsp"] = len(_load("algos.json"))
    for dom, var in (("kpvar", "ssp"), ("gcvar", "mis"), ("bpvar", "vsbinpack")):
        counts[dom] = len(json.loads(_d.domain_list(dom, {"variant": var}))["algos"])
    rows = []
    for dom, name, enc, cons, obj, scale, demo in _COVERAGE_META:
        if dom == "entryseq":
            lv = [registry.fidelity("entryseq", v)["level"] for v in registry.VARIANTS["entryseq"]]
            fid = f'{lv.count("standard")} 标准 · {lv.count("simplified")} 简化 · {lv.count("illustrative")} 示意'
        else:
            fid = "标准"
        scale = scale.format(n_funcs=len(_d.FUNCS), n_variants=len(registry.VARIANTS["entryseq"]))
        rows.append(f"    <tr><td>{name}</td><td>{enc}</td><td>{cons}</td><td>{obj}</td><td>{scale}</td>"
                    f"<td>{counts.get(dom, '—')}</td><td>{fid}</td><td>{demo}</td></tr>")
    return chr(10).join(rows)


def _family_index_rows():
    """百科总纲「算法家族索引」表的行：全部由 data/families.json + data/algos.json 生成（原先是手写的一份副本）。"""
    families, algos = _load("families.json"), _load("algos.json")
    rows = []
    for f in families:
        members = [a for a in algos if a["family"] == f["id"]]
        if members:
            cell = " · ".join(f'<a href="/algo/{f["dir"]}/{a["key"]}/">{a["name"]}</a>' for a in members)
        else:
            cell = f'<span class="hint">见<a href="/algo/{f["dir"]}/">家族页</a>（收录中/批评词条）</span>'
        rows.append(f'    <tr><td><b>{f["name"]}（{f["id"]}）</b><br><span class="hint">{f["oneliner"]}</span></td>'
                    f'<td>{cell}</td></tr>')
    return chr(10).join(rows)


def _family_index_intro():
    n_algos = len(_load("algos.json"))
    n_fam = len(_load("families.json"))
    return f"{n_algos} 个 TSP 算法按站内 {n_fam} 个家族分组——每个家族下一行是它的定位"


def generate(write, inject_theme, navlinks, ldjson, site, mapping_ctx=None):
    print("生成百科/问题域页面…")
    _algo_counts = _domain_algo_counts()
    mapping_ctx = mapping_ctx or {}

    def _page(html):
        html = inject_theme(html)
        html = html.replace("<!--SITE-->", site)
        html = html.replace("<!--NAVLINKS-->", navlinks(""))
        return html

    # 百科总纲
    enc = (ENCYCLOPEDIA.replace("<!--CARDS-->", _domain_cards())
           .replace("<!--FAMILY_ROWS-->", _family_index_rows())
           .replace("<!--COVERAGE_ROWS-->", _coverage_rows())
           .replace("<!--FAMILY_INTRO-->", _family_index_intro()))
    write("encyclopedia/index.html", _page(
        enc.replace("<!--LDJSON-->", ldjson("元启发式与群智能算法百科总纲",
                                            "问题分类四连问、七个正交维度、算法家族索引与本站覆盖矩阵", kind="Article"))))

    # 覆盖矩阵页（用户原子架构构想看板：域×算法覆盖状态）
    write("coverage/index.html", _page(
        _coverage_page_html().replace("<!--LDJSON-->", ldjson("域×算法覆盖矩阵 · 原子架构看板",
                                                              "每个问题域可跑的全部算法：位向量/排列/指派三大原子适配层的覆盖状态", kind="Article"))))

    # 候选发现池页（收录闸门留痕：discovery.json 候选池全谱，数据驱动渲染）
    write("discovery/index.html", _page(
        _discovery_page_html().replace("<!--LDJSON-->", ldjson("候选发现池 · 收录闸门留痕",
                                                              "算法/问题候选的五闸门评分、证据强度与 proposed→admitted 收录状态全谱", kind="Article"))))

    # 背包页
    ks = _interactive_page(
        path="/problem/knapsack/",
        title="0-1 背包问题在线演示 · 二进制编码元启发式算法（GA/SA/TS/ABC 等 {N_KS} 种）".format(N_KS=_algo_counts["knapsack"]),
        desc="用 {n} 种元启发式算法求解 0-1 背包问题：二进制编码、贪心修复算子处理约束，实时看物品选择与收敛曲线，浏览器本地运行。".format(n=_algo_counts["knapsack"]),
        h1="0-1 背包问题在线演示<br><span class='grad'>二进制编码 · {n} 种算法</span>".format(n=_algo_counts["knapsack"]),
        lead="背包是二进制优化的入门标准题：每件物品「装/不装」是一个 0/1 决策，约束是总重不能超过容量。看同一批算法换个编码还能不能打。",
        intro_html="""
  <p>与 TSP 的排列编码不同，背包的解是 <strong>0/1 向量</strong>——这是「二进制优化」维度。两个新东西值得注意：</p>
  <p>① <strong>约束处理</strong>：随便生成的解很可能超重。本页用<strong>贪心修复算子</strong>——按「单位重量价值最低先扔」一直扔到装得下。修复比罚函数干净：搜索始终在可行域内，收敛曲线不会有锯齿。</p>
  <p>② <strong>算子随编码走</strong>：交叉变均匀交叉（逐位 50/50），变异变位翻转，DE 的「差向量」变成「r2/r3 不同的那些位」，GWO 变成 α/β/δ 三头狼逐位投票（bGWO）。算法没变，变的只是编码层——这就是元启发式跨问题的通用公式。</p>
  <!--KS_VARIANTS-->""",
        controls_html="",
        preset_options={"n40": {"n": 40}, "n60": {"n": 60}, "n80": {"n": 80},
                        "n120": {"n": 120}, "n200": {"n": 200}},
        preset_labels={"n40": "40 件物品（小）", "n60": "60 件物品（小）", "n80": "80 件物品（中）",
                       "n120": "120 件物品（大）", "n200": "200 件物品（超大）"},
        page_domain="knapsack",
        custom_fields=[{"key": "n", "label": "物品数", "min": 10, "max": 300, "val": 40}],
        extra_hint="柱状图红色=选入背包，底部绿条=重量占用",
        bench_table=KNAPSACK_BENCH,
        faq_html=_domain_faq("knapsack"),
        extra_html=mapping_ctx.get("knapsack", ""),
    )
    # S3：枢纽页挂变体谱系导航（data/problems.json 单一事实源）
    from pages_problems import knapsack_variants_nav as _ksnav, load_data as _ksdata
    ks = ks.replace("<!--KS_VARIANTS-->", _ksnav(_ksdata()))
    write("problem/knapsack/index.html", _page(
        ks.replace("<!--LDJSON-->", ldjson("0-1 背包问题在线演示", "二进制编码元启发式算法求解背包问题在线演示"))))

    # 连续函数页
    cn = _interactive_page(
        path="/problem/continuous/",
        title="连续函数优化在线演示 · PSO/DE/GWO/WOA/SCA 原生域基准测试",
        desc="在 Sphere/Rastrigin/Rosenbrock/Ackley 基准函数上在线运行 PSO、DE、灰狼、鲸鱼、SCA 等算法：粒子热力图动画与收敛曲线，连续优化的原生域。",
        h1="连续函数优化在线演示<br><span class='grad'>算法的「原生域」长这样</span>",
        lead="PSO/DE/GWO/WOA/SCA 的教科书公式本来是为实数空间写的——这里不做任何离散化，原样运行。看完这页再回 TSP 页，就知道离散化改掉了什么。",
        intro_html="""
  <p>灰底热力图是目标函数地形（越暗=越低=越好），粒子是候选解，十字标是全局最优。四个基准函数各有考点：</p>
  <p><strong>Sphere</strong>（单峰碗状）：考收敛速度；<strong>Rosenbrock</strong>（香蕉谷）：谷底平坦，考细步推进；<strong>Rastrigin</strong>（遍地尖谷）：考逃逸局部最优能力；<strong>Ackley</strong>：近全局平坦+边缘粗糙。</p>
  <p>把维度切到 10 维再跑一次——低维演示里凶悍的算法可能当场翻车，这是「维度灾难」的直观版本。</p>""",
        controls_html="",
        preset_options={"rastrigin2": {"fn": "rastrigin", "dim": 2}, "sphere2": {"fn": "sphere", "dim": 2},
                        "rosenbrock2": {"fn": "rosenbrock", "dim": 2}, "ackley2": {"fn": "ackley", "dim": 2},
                        "rastrigin10": {"fn": "rastrigin", "dim": 10}, "sphere10": {"fn": "sphere", "dim": 10},
                        "rosenbrock10": {"fn": "rosenbrock", "dim": 10}, "ackley10": {"fn": "ackley", "dim": 10},
                        "rastrigin30": {"fn": "rastrigin", "dim": 30}, "sphere30": {"fn": "sphere", "dim": 30},
                        "rosenbrock30": {"fn": "rosenbrock", "dim": 30}, "ackley30": {"fn": "ackley", "dim": 30},
                        **{f"{fn}{d}": {"fn": fn, "dim": d} for fn in _NEW_FN_LABELS for d in (2, 10)}},
        preset_labels={"rastrigin2": "Rastrigin 2D", "sphere2": "Sphere 2D",
                       "rosenbrock2": "Rosenbrock 2D", "ackley2": "Ackley 2D",
                       "rastrigin10": "Rastrigin 10D（难）", "sphere10": "Sphere 10D",
                       "rosenbrock10": "Rosenbrock 10D", "ackley10": "Ackley 10D",
                       "rastrigin30": "Rastrigin 30D（维度灾难）", "sphere30": "Sphere 30D",
                       "rosenbrock30": "Rosenbrock 30D", "ackley30": "Ackley 30D",
                       **{f"{fn}{d}": f"{lab} {d}D" for fn, lab in _NEW_FN_LABELS.items() for d in (2, 10)}},
        page_domain="continuous",
        custom_fields=[{"key": "dim", "label": "维度 dim", "min": 1, "max": 30, "val": 2}],
        extra_hint="热力图越暗越好，十字=全局最优，灰点=粒子",
        bench_table=CONTINUOUS_BENCH,
        faq_html=_domain_faq("continuous"),
        extra_html=mapping_ctx.get("continuous", ""),
    )
    write("problem/continuous/index.html", _page(
        cn.replace("<!--LDJSON-->", ldjson("连续函数优化在线演示", "PSO/DE/GWO/WOA/SCA 原生域基准函数在线演示"))))

    # 多目标页
    mo = _interactive_page(
        path="/problem/multiobj/",
        title="多目标优化在线演示 · NSGA-II 求 Pareto 前沿（双目标背包）",
        desc="NSGA-II 求解双目标背包问题：非支配排序+拥挤度，实时观看 Pareto 前沿铺开动画，对比加权标量化的多样性坍缩，浏览器本地运行。",
        h1="多目标优化在线演示<br><span class='grad'>NSGA-II · Pareto 前沿动画</span>",
        lead="两个收益互相冲突的背包：目标1 和目标2 都想最大化。输出不再是一个解，而是一整条 Pareto 前沿——看它怎么一代代铺开。",
        intro_html="""
  <p>多目标与单目标的本质区别：两个目标冲突时（同一件物品对目标1 好可能对目标2 差），不存在「所有目标都最优」的解，只能求<strong>一组互不支配的折中解</strong>（Pareto 前沿）。</p>
  <p>散点图里：<strong>灰点=种群，红点=当前 Pareto 前沿</strong>，越靠右上角越好。重点看 NSGA-II 和「加权 GA」对照的差别——后者每代随机取权重合成单目标，种群会坍缩到一个点，多样性全无；NSGA-II 的拥挤度机制专门防止这件事。这就是 Pareto 框架（Deb et al. 2002，引用数万级）成为默认起点的理由。</p>""",
        controls_html="",
        preset_options={"n40": {"n": 40}, "n60": {"n": 60}, "n100": {"n": 100}, "n150": {"n": 150}},
        preset_labels={"n40": "40 件物品（小）", "n60": "60 件物品（中）",
                       "n100": "100 件物品（大）", "n150": "150 件物品（超大）"},
        page_domain="multiobj",
        custom_fields=[{"key": "n", "label": "物品数", "min": 10, "max": 150, "val": 40}],
        extra_hint="灰点=种群，红点+红线=Pareto 前沿，右上角更好",
        bench_table=MULTIOBJ_BENCH,
        faq_html=_domain_faq("multiobj"),
        extra_html=(mapping_ctx.get("multiobj", "") + _mo_mechanism_section()),
    )
    write("problem/multiobj/index.html", _page(
        mo.replace("<!--LDJSON-->", ldjson("多目标优化在线演示", "NSGA-II 求解双目标背包的 Pareto 前沿动画"))))

    # 图着色页
    gc = _interactive_page(
        path="/problem/graphcolor/",
        title="图着色问题在线演示 · 排列编码元启发式算法（HC/SA/TS/GA/ABC/WOA 等 {N_GC} 种）".format(N_GC=_algo_counts["graphcolor"]),
        desc="用 {n} 种元启发式算法求解图着色（DSJC 基准图）：排列编码 + First-Fit 贪心着色解码，观看顶点染色动画与收敛曲线，浏览器本地运行。".format(n=_algo_counts["graphcolor"]),
        h1="图着色问题在线演示<br><span class='grad'>排列编码 · First-Fit 解码 · {n} 种算法</span>".format(n=_algo_counts["graphcolor"]),
        lead="给图的每个顶点染色，相邻顶点不能同色，用的颜色种类越少越好。排课表、寄存器分配、频道分配的抽象原型。",
        intro_html="""
  <p>图着色是组合优化的另一棵常青树。本页的编码方案值得细看：<strong>解 = 顶点的一个排列</strong>，解码 = 按排列顺序给每个顶点分配「邻居没用过的最小编号颜色」（First-Fit 贪心）。排列的顺序决定着色质量——算法的工作就是找到那个好顺序。</p>
  <p>这和 TSP 是<strong>同一种编码</strong>（排列），只是解码器换了：TSP 把排列当访问顺序，图着色把排列当染色优先级。目标函数是「色数 k + Σci²」字典序：色数是主指标，Σci²（颜色编号平方和）鼓励空出高编号颜色桶——色数是整数，下降是阶梯状的，平台期算法实际在优化次级指标攒势能。</p>
  <p>实例是 <strong>DSJC 均匀随机图</strong>（n=50 p=0.5 时随机序 FF 要 12 色，优化后 10~11 色）。实测教训：随机几何图太「结构化」，随机序 First-Fit 就近乎最优——只有 DSJC 这类硬图才测得出算法差距。</p>""",
        controls_html="",
        preset_options={"n30": {"n": 30, "p": 0.5}, "n50": {"n": 50, "p": 0.5}, "n80": {"n": 80, "p": 0.4}},
        preset_labels={"n30": "DSJC 30 顶点（小）", "n50": "DSJC 50 顶点（中）", "n80": "DSJC 80 顶点（大）"},
        page_domain="graphcolor",
        custom_fields=[{"key": "n", "label": "顶点数", "min": 10, "max": 150, "val": 30}, {"key": "p", "label": "边密度 p", "min": 0.1, "max": 0.9, "val": 0.5, "step": 0.05}],
        extra_hint="顶点颜色 = 所染颜色（金角调色板），细线 = 边",
        bench_table=GC_BENCH,
        faq_html=_domain_faq("graphcolor"),
        extra_html=mapping_ctx.get("graphcolor", ""),
    )
    write("problem/graphcolor/index.html", _page(
        gc.replace("<!--LDJSON-->", ldjson("图着色问题在线演示", "排列编码元启发式算法求解图着色的在线演示"))))

    # 装箱页
    bp = _interactive_page(
        path="/problem/binpack/",
        title="装箱问题在线演示 · 排列编码元启发式算法（HC/SA/TS/GA/ABC/WOA 等 {N_BP} 种）".format(N_BP=_algo_counts["binpack"]),
        desc="用 {n} 种元启发式算法求解一维装箱问题：排列编码 + First-Fit 装箱解码，观看装箱动画、对照理论下界 LB，浏览器本地运行。".format(n=_algo_counts["binpack"]),
        h1="装箱问题在线演示<br><span class='grad'>排列编码 · First-Fit 解码 · {n} 种算法</span>".format(n=_algo_counts["binpack"]),
        lead="把 n 件物品塞进容量固定的箱子，用最少的箱子。物流装载、资源调度、内存分配的抽象原型。",
        intro_html="""
  <p>装箱与图着色共用同一套骨架：<strong>解 = 物品的一个排列</strong>，解码 = 按排列顺序把物品放进「第一个放得下的箱子」（First-Fit）。又是排列编码、换一个解码器——这就是元启发式跨问题的通用公式第三次上演。</p>
  <p>目标函数是「箱数 b + Σ剩余²」字典序：箱数是主指标，剩余容量平方和鼓励箱子塞紧——箱数撞上下界后，算法间比的就是塞得紧不紧。页面会显示 <strong>LB = ⌈Σ重量/容量⌉</strong>：任何装箱方案都不可能少于 LB 箱，触到 LB 即最优。</p>
  <p>物品重量 U[20,100]、容量 150：LB≈n/2.5，First-Fit Decresing（FFD）通常 LB+1，而随机序 FF 差 2~3 箱——优化空间真实存在。</p>""",
        controls_html="",
        preset_options={"n40": {"n": 40}, "n60": {"n": 60}, "n80": {"n": 80}},
        preset_labels={"n40": "40 件物品（小）", "n60": "60 件物品（中）", "n80": "80 件物品（大）"},
        page_domain="binpack",
        custom_fields=[{"key": "n", "label": "物品数", "min": 10, "max": 200, "val": 40}],
        extra_hint="每列=一箱，色块=物品（按箱分组着色），虚线=剩余容量",
        bench_table=BP_BENCH,
        faq_html=_domain_faq("binpack"),
        extra_html=mapping_ctx.get("binpack", ""),
    )
    write("problem/binpack/index.html", _page(
        bp.replace("<!--LDJSON-->", ldjson("装箱问题在线演示", "排列编码元启发式算法求解装箱问题的在线演示"))))

    # 自带问题页：用户选编码 + 写目标函数，该编码下已有的全部算法原样可用
    cu = _interactive_page(
        path="/problem/custom/",
        title="自带问题 · 写一个目标函数，直接用全部群智能算法求解",
        desc="本站没有你的问题？选一种解的形状（是/否、排序、实数），写一个目标函数，几十种群智能算法立刻可用：浏览器本地运行，目标函数只允许算术表达式，安全可复现。",
        h1="自带问题<br><span class='grad'>选解的形状 · 写目标函数 · 全部算法可用</span>",
        lead="本站没有你要的问题？把它描述出来：解长什么样（编码），好坏怎么算（目标函数）。其余——几十种算法、收敛曲线、结果导出与复现——都是现成的。",
        intro_html="""
  <p>所有算法都只通过两样东西和问题打交道：<strong>解的形状</strong>（编码）和<strong>目标值</strong>。所以你只要给出这两样，同一批算法就能原样跑你的问题：</p>
  <ul>
    <li><b>位向量</b>：n 个是/否的决策——选哪些渠道、开哪些仓库、用哪些特征。</li>
    <li><b>排列</b>：把 0..n-1 排个顺序——任务先后、路线顺序、装配次序。</li>
    <li><b>实数向量</b>：n 个在 lo~hi 之间的数——参数调优、曲线拟合、函数最小化。</li>
  </ul>
  <h2 id="editor">① 定义你的问题</h2>
  <p class="hint">先在下面的「实例」里选一个示例，改成你自己的，点「检查并载入」。检查时会在 30 个随机解上试算你的目标函数，写错了会指出哪里。</p>
  <div class="panel" id="customEditor">
    <div class="row">
      <div class="field"><label>解的形状（由「实例」决定）</label><span id="ceEnc" class="ce-enc">—</span></div>
      <div class="field"><label for="ceN">长度 / 维度 n</label><input id="ceN" type="number" min="2" step="1"></div>
      <div class="field"><label for="ceSense">目标方向</label>
        <select id="ceSense"><option value="min">越小越好（最小化）</option><option value="max">越大越好（最大化）</option></select></div>
      <div class="field" id="ceRange" hidden><label for="ceLo">数值范围 lo ~ hi（每一维共用）</label>
        <span class="ce-range"><input id="ceLo" type="number" step="any"> ~ <input id="ceHi" type="number" step="any"></span></div>
    </div>
    <div class="field ce-wide"><label for="ceData">数据表（JSON：名字 → 数字或数字数组，最多三层；目标函数里直接用名字读取）</label>
      <textarea id="ceData" class="ce-area" rows="5" spellcheck="false" autocomplete="off"></textarea></div>
    <div class="field ce-wide"><label for="ceObj">目标函数（用 x 表示解，n 表示长度）</label>
      <textarea id="ceObj" class="ce-area" rows="6" spellcheck="false" autocomplete="off"></textarea></div>
    <div class="row"><button id="ceApply" class="primary">✓ 检查并载入</button></div>
    <details class="faq-item"><summary>目标函数怎么写？（语法与限制）</summary><div class="faq-body">
      <p>写法像 Python 的<b>表达式</b>：可以有几行 <code>名字 = 表达式</code> 的中间量，最后一行直接是目标值（或写成 <code>objective = …</code>）。</p>
      <ul>
        <li>可用：数字、<code>+ - * / // % **</code>、比较、<code>and or not</code>、<code>a if 条件 else b</code>、下标 <code>x[i]</code>、列表 / 生成式（<code>sum(w[i] * x[i] for i in range(n))</code>）。</li>
        <li>可用函数：<code>sum min max abs len range sorted round float int any all sqrt exp log sin cos floor ceil zip enumerate</code>，常数 <code>pi e</code>。</li>
        <li>不可用：<code>import</code>、点号属性、字符串、lambda、字典 / 集合、<code>for / while</code> 语句、<code>def</code>。循环最多嵌套两层。</li>
        <li>约束请用<b>罚函数</b>：违反约束就加一个大数 × 违反量，例如 <code>gain - 100 * max(0, spend - budget)</code>。</li>
      </ul>
    </div></details>
  </div>""",
        controls_html="",
        preset_options={"bits": {"variant": "bits"}, "perm": {"variant": "perm"}, "real": {"variant": "real"}},
        preset_labels={"bits": "示例 · 位向量：预算内选渠道（最大化）", "perm": "示例 · 排列：加权延误最小的作业顺序",
                       "real": "示例 · 实数向量：曲线拟合 y = a·e^(b·t) + c"},
        page_domain="custom",
        extra_hint="示例只是起点——换成你自己的目标函数",
        bench_table="",
        faq_html=_domain_faq("custom"),
        extra_html=("<p class=\"hint\">命令行里也能用：<code>python swarm.py solve 数据.json --domain custom --variant bits --algo ga</code>；"
                    "目标函数需要完整 Python 时加 <code>--objective-py 你的函数.py</code>（只在你自己的电脑上运行）。"
                    "格式见 <a href=\"/docs/custom-problems.md\">自带问题说明</a>。</p>"),
    )
    write("problem/custom/index.html", _page(
        cu.replace("<!--LDJSON-->", ldjson("自带问题", "选解的形状、写目标函数，用全部群智能算法求解自己的问题"))))

    # 组件百科页
    write("components/index.html", _page(
        _components_page_html().replace("<!--LDJSON-->", ldjson(
            "组件百科 · 元启发式算法的乐高积木", "13 个通用组件的注册表、调用方实测计数与排列域「问题适配」范式", kind="Article"))))

    print("  百科 + 5 个问题域 + 组件页完成")


    # S3：暴露 _page 闭包供 pages_problems 复用（页面骨架单一来源）
    return _page


def _domain_cards():
    return "\n    ".join([
        '<a class="card" href="/"><span class="ico">🧭</span><b>TSP 排列优化</b><span>45 个算法的完整阵地：路径动画+收敛曲线+调参</span><span class="arrow">→</span></a>',
        '<a class="card" href="/problem/knapsack/"><span class="ico">🎒</span><b>0-1 背包</b><span>二进制编码 + 贪心修复：约束处理入门</span><span class="arrow">→</span></a>',
        '<a class="card" href="/problem/continuous/"><span class="ico">⛰️</span><b>连续函数基准</b><span>PSO/DE/GWO 的原生域：地形热力图+粒子动画</span><span class="arrow">→</span></a>',
        '<a class="card" href="/problem/multiobj/"><span class="ico">📊</span><b>多目标 NSGA-II</b><span>Pareto 前沿动画 vs 加权法坍缩对照</span><span class="arrow">→</span></a>',
        '<a class="card" href="/problem/graphcolor/"><span class="ico">🎨</span><b>图着色</b><span>排列编码换解码器：染色动画 + DSJC 硬实例</span><span class="arrow">→</span></a>',
        '<a class="card" href="/problem/binpack/"><span class="ico">📦</span><b>装箱 Bin Packing</b><span>排列编码三连演：装箱动画 + 下界 LB 对照</span><span class="arrow">→</span></a>',
        '<a class="card" href="/components/"><span class="ico">🧩</span><b>组件百科</b><span>给贡献者：13 个通用组件的注册表，算法的乐高积木</span><span class="arrow">→</span></a>',
        '<a class="card" href="/compare/"><span class="ico">🏁</span><b>算法横向对比</b><span>同一 TSP 实例跑遍所有算法</span><span class="arrow">→</span></a>',
    ])


def _domain_faq(domain):
    faqs = {
        "knapsack": [
            ("为什么收敛曲线起步就很高？", "初始种群经过贪心修复——哪怕随机解也会被修复到「性价比可以」的水平，所以起点不低。算法的价值体现在之后能不能再爬 5~10%。这也是为什么测试要求算法必须显著赢过随机基线而不是赢过 0。"),
            ("修复算子和罚函数哪个好？", "修复保持全可行搜索，曲线干净，但每代多一次修复计算；罚函数实现简单但参数难调，罚太重等于不可行解全废、罚太轻会大量能量浪费在不可行区。约束紧时一般选修复。"),
            ("为什么算法们最后都停在差不多的值？", "背包规模小时最优解不难够到（本站实例多数算法能到 1479 附近）。把实例切到 80 件再对比，差距会拉开——这也是选「实例」下拉的意义。"),
        ],
        "continuous": [
            ("为什么随机搜索在 Rastrigin 上比 SA/HC 还强？", "2D、评价便宜时，均匀采样 6000 个点的最好值本来就约 0.6，而单链算法容易困在某个尖谷里。这不是 SA 写错了——是多峰地形+低维的客观规律。切到 10 维试试：随机搜索立刻失效，种群算法优势才会显现。"),
            ("热力图在 10 维时还准吗？", "热力图只画前两个维度（其余维度固定 0），粒子位置也只投影前两维——你看到的是高维搜索在 2D 切片上的影子。收敛曲线始终是真实的高维目标函数值。"),
            ("PSO 的速度上限是干什么用的？", "速度不限的话粒子会飞出边界来回震荡，永远进不了谷底。本站限制单代位移不超过搜索域的 20%，属于 PSO 工程化的标准操作。"),
        ],
        "multiobj": [
            ("为什么叫 Pareto 前沿？", "经济学家 Pareto 提出：无法在不损害任何一方的前提下再改进任何一方，就是「帕累托有效」。多目标优化里，前沿上每个点都是一个不同的有效折中——选哪个由决策者定，算法只负责把前沿铺开。"),
            ("加权法到底差在哪？", "①每换一组权重才得到一个点，铺满前沿要跑很多次；②非凸前沿段用任何权重都够不到；③种群进化时权重一换、目标就换，种群会被反复拉扯，最后坍缩成少数几个点——本页的加权 GA 对照就是活演示。"),
            ("拥挤度是什么？", "同一非支配层里，某个解周围越空旷，拥挤度越小（本站实现按邻居距离和算）。NSGA-II 优先保留稀疏区域的解，防止前沿扎堆——这是它能「铺开」的关键机制。"),
        ],
        "graphcolor": [
            ("为什么收敛曲线是阶梯状的？", "色数是整数——算法从 11 色降到 10 色之间不会出现「10.5 色」。平台期算法在优化次级指标 Σci²（把颜色用得更紧凑、空出高编号桶），攒够势能才可能跳到下一个色数。看曲线时主看红色台阶什么时候掉。"),
            ("什么是 DSJC 实例？为什么不用好看的几何图？", "DSJC = 均匀随机连边（Johnson 等 1991 年起的图着色标准基准）。实测教训：随机几何图（顶点散在平面上、按距离连边）太有结构——随机顺序 First-Fit 就近乎最优，所有算法贴底测不出差距。DSJC p=0.5 时随机序 12 色 vs 优化后 10~11 色，差距真实。"),
            ("排列编码在这里怎么工作？", "解 = 顶点排列，解码 = 按顺序 First-Fit 染色：轮到谁，就给它邻居没用过的最小编号颜色。排前面的顶点选择多、排后面的只能捡剩的——所以「把难染的顶点排前面」是好方向，算法交换/交叉的就是这个顺序。合法着色由构造保证，永远不需要修复算子。"),
        ],
        "custom": [
            ("我的目标函数会被当作代码执行吗？", "不会。目标函数只是一段「表达式」：本站先把它解析成语法树，逐个节点检查，只放行数字、四则和乘方、比较、推导式、以及 sum / min / max / abs / sqrt 等少数白名单函数；import、属性访问（点号）、字符串、lambda、循环语句一律拒绝。解析通过后才编译成只会做算术的小程序，每次评价还有迭代次数和整数大小的上限，防止写出会卡死标签页的式子。"),
            ("为什么没有 for 循环、while 循环？", "表达式风格的 sum(… for i in range(n)) 已经能写出绝大多数目标函数（求和、最大最小、加惩罚项），而且循环层数有限、次数有上限，不会死循环。如果你的目标函数确实需要完整的 Python（递归、复杂状态），请用命令行：python swarm.py solve 数据.json --domain custom --objective-py 你的函数.py，那是在你自己的电脑上运行你自己的文件。"),
            ("约束怎么写？", "用罚函数：违反约束就在目标里加一个大数乘以违反量，如 gain - 100 * max(0, spend - budget)。惩罚太轻，算法会专挑违反约束的便宜解；太重，可行与不可行之间没有梯度。示例里的「预算内选渠道」就是这个写法，可以改着试。"),
            ("为什么三种编码对应的算法数不一样？", "每种编码复用本站已有的一批内核：位向量用 QUBO 那批，排列用装箱 / 图着色那批，实数用连续函数那批。内核不是为你的问题写的，但它们只通过「编码」和「目标值」与问题打交道，所以能原样跑。算法不一定适合你的问题——最好多挑几个比一比。"),
            ("结果可靠吗？", "「最优值」是算法在你的目标函数上找到的最好值，不保证是全局最优。随机算法换个种子结果会变；要下结论请多换几个种子。导出的结果文件带着完整的问题定义，别人可以用 python swarm.py replay 复现。"),
        ],
        "binpack": [
            ("LB 是什么？为什么触到 LB 就不用再跑了？", "LB = ⌈所有物品总重 ÷ 箱容量⌉，是最多可能的数学下界——不管多聪明的装法，总重摆在那里，箱子不可能更少。所以箱数 = LB 就是最优解，剩下的算法比的是「没触到 LB 时谁更近、以及塞得紧不紧」。"),
            ("箱数一样时比什么？", "比 Σ剩余²（所有箱子剩余容量的平方和）。它鼓励「要么塞满、要么留大空位」——小空位又多又碎是最差形态。这也是装箱文献的标准次级目标：主指标（箱数）是整数平台，次级指标给算法提供连续的梯度。"),
            ("和 TSP 用的编码一样吗？", "一样，都是排列！TSP 把排列当访问顺序、图着色当染色优先级、装箱当装填顺序——三个问题三个解码器，算法（交换/插入/OX 交叉/退火）原封不动。这是本站「算法 = 机制，问题绑定 = 编码+解码」骨架的最好证据：本页 7 个算法与图着色页是同一份代码跑出来的。"),
        ],
    }
    return "\n  ".join(
        f'<details class="faq-item"><summary>{q}</summary><div class="faq-body">{a}</div></details>'
        for q, a in faqs[domain]
    )

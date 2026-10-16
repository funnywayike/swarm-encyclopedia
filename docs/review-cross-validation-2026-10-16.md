# 综述资料收集与交叉核对报告

2026-10-16；研究资料与核对记录。

## 本轮做到什么程度

收录 128 项综述、教程和方法学资料，按 DOI 或原始链接去重。已核读摘要 32 项，已核读指定章节 5 项，其余 91 项保留为书目入口。没有声称逐篇读完全文，也未复现这些论文中的全部实验。

30 个英文书目查询，每个取 Crossref 相关性前5项，共 150 条候选记录、143 个不同 DOI；另合并原研究地图书目、出版社和机构库来源，并人工补充经典与更新综述。这不是全数据库检索，不能由此计算领域覆盖率或宣称穷尽。中文4项为既有阅读入口，本轮尚未完成逐段核读。

## 扩展覆盖检查

在首轮检索之外，新增32组主题查询、每组前15项，共480条候选；人工补充了理论、景观、参数控制、大规模、离散适配和经典搜索框架等资料。文献增加不等于核读完成。完整性按42主题覆盖表逐项检查，尚不宣称较完整。

[查看42主题覆盖与缺口](review-coverage-audit-2026-10-16.md)。

## 检索与筛选

检索主题包括历史与分类、PSO、ACO、DE、ABC、GA、CMA-ES、VNS、模因算法、约束、多目标/多目标高维、动态与不确定优化、代理模型、质量多样性、超启发式、算法选择/配置/设计、学习辅助、机器人及应用专题。检索式、请求地址和候选元数据均已保存。候选排序偏向相关性，可能遗漏不同措辞或不在 Crossref 的资料。

人工筛除偏题、评审意见等非正文材料，并合并重复入口。未选中不等于质量不合格；目录保留历史评论、教程、方法学预印本与正式综述的类型差别。预印本不自动当作同行评审结果。

交叉核对以具体主张为单位：先比较研究对象、时间和阅读位置，再检查作者重叠、引用延续、版本与日期。多篇重复同一句话不自动增加独立证据。不同综述的范围差别也不自动表示结论矛盾。

## 主题分布

|主题|资料数|
|---|---:|
|中文交叉阅读|3|
|复杂优化与混合机制|17|
|学习与自动设计|10|
|实验与证据方法|4|
|总览、历史与分类|6|
|理论、景观与实验方法|10|
|经典算法与框架|15|
|群体机器人|4|
|行业与问题应用|43|
|规模、表征与搜索框架|16|

## 12 个核对议题

### 噪声、稳健、动态优化怎样区分

**判断：范围可对齐。** 地图应分别标出误差发生在哪里、环境何时变化、优化器需要追踪什么；不把“不确定”作为无差别标签。

独立性与边界：两篇均有 Branke 参与，动态综述引言还引用早期不确定性综述；这是可追溯的概念延续，不能算两次独立验证。

- [Evolutionary Optimization in Uncertain Environments—A Survey](https://doi.org/10.1109/TEVC.2005.846356)；第I节，页303—304；从误差来源区分四种不确定性。
- [Evolutionary dynamic optimization: A survey of the state of the art](https://doi.org/10.1016/j.swevo.2012.05.001)；公开稿引言，前4页；聚焦环境变化下的在线适应与追踪。

### 代理模型与代理辅助进化计算

**判断：交叉支持，范围不同。** 可以把昂贵评估、模型误差与真实评估的协调作为研究主线；不把某种工程代理策略认作所有领域的标准最佳方案。

独立性与边界：2005与2011资料共享 Jin；2009 Forrester/Keane 作者团队不同，但工程设计与进化算法的覆盖范围有区别。作者不同仍不保证所引实验独立。

- [Evolutionary Optimization in Uncertain Environments—A Survey](https://doi.org/10.1109/TEVC.2005.846356)；第I节；近似模型误差需要与真实评估协调。
- [Surrogate-assisted evolutionary computation: Recent advances and future challenges](https://doi.org/10.1016/j.swevo.2011.05.001)；摘要；专题范围是代理辅助进化计算。
- [Recent advances in surrogate-based optimization](https://doi.org/10.1016/j.paerosci.2008.11.001)；摘要与引言；从昂贵工程设计评估讨论代理优化，并说明选择并非穷尽。

### PSO 综述能否代表所有 PSO 实现

**判断：范围限制。** 算法介绍与实现应明确连续或离散、目标数和边界处理；本轮不能由这些综述推出本站各个适配均符合标准。

独立性与边界：Poli/Kennedy/Blackwell 与 Bonyadi/Michalewicz 作者不同；两篇并非相同问题集上的独立复现实验。

- [Particle swarm optimization](https://doi.org/10.1007/s11721-007-0002-0)；摘要与参考文献；总体回顾，参考文献包含离散及二进制适配。
- [Particle Swarm Optimization for Single Objective Continuous Space Problems: A Review](https://doi.org/10.1162/evco_r_00180)；标题与摘要；明确限定单目标连续空间。

### 多目标、多个峰与质量多样性是否相同

**判断：概念边界。** 地图可以显示这些方向的交汇，但不应合并概念：Pareto 折中与行为空间中高质量解的覆盖具有不同阅读目标。

独立性与边界：两组作者不同；引用这里只支持定义与范围区分，不支持任意任务上的性能比较。

- [Quality Diversity: A New Frontier for Evolutionary Computation](https://doi.org/10.3389/frobt.2016.00040)；第2.1—2.3节；区分多峰、行为多样性与多目标，组织 QD 的研究目标。
- [Multi-objective hyper-heuristics: a survey](https://doi.org/10.1007/s10462-025-11486-2)；第1节；介绍多目标中的 Pareto 概念及有限解集近似。

### 群智能优化是否等于群体机器人

**判断：范围限制。** 物理机器人协同应保留独立主线；通信、感知、验证和行为执行不是浏览器中的目标函数搜索结果。

独立性与边界：三组作者不同，但机器人综述也可能共享底层案例，不能当作三组部署验证。

- [Swarm robotics: a review from the swarm engineering perspective](https://doi.org/10.1007/s11721-012-0075-2)；摘要；从群体工程和集体行为两类视角组织领域。
- [From animal collective behaviors to swarm robotic cooperation](https://doi.org/10.1093/nsr/nwad040)；摘要；讨论动物群体及多种物理平台协同。
- [Particle swarm optimization](https://doi.org/10.1007/s11721-007-0002-0)；摘要；范围是优化算法及其研究。

### 选择、配置与生成算法如何组织

**判断：视角互补。** 以“决策对象”组织自动设计路线，允许同一系统同时选择、配置和生成；不要求它们成为互斥的历史阶段。

独立性与边界：作者不同及分类不同不构成结论冲突；这里只比较各篇的研究对象。

- [Hyper-heuristics: a survey of the state of the art](https://doi.org/10.1057/jors.2013.71)；正式记录摘要；超启发式包含选择或生成启发式。
- [Automated Algorithm Selection: Survey and Perspectives](https://doi.org/10.1162/evco_a_00242)；摘要；按实例选择算法，并联系配置、组合与调度。
- [Multi-objective hyper-heuristics: a survey](https://doi.org/10.1007/s10462-025-11486-2)；摘要；在多目标专题内讨论选择、生成、组合和配置。

### 学习辅助与大模型算法设计

**判断：视角互补。** 地图需要标出模型承担的具体工作：辅助组件、预测、提取或设计；仅出现机器学习并不意味着替代了全部求解器。

独立性与边界：两篇覆盖年代与模型对象不同。分类可交叉定位，但不足以证明一种路线已成为全领域主流。

- [Machine Learning into Metaheuristics](https://doi.org/10.1145/3459664)；摘要；按学习参与元启发式组件的层次分类。
- [A Systematic Survey on Large Language Models for Algorithm Design](https://doi.org/10.1145/3787585)；摘要；按大模型承担的不同角色组织研究。

### 综述样本数量是否等于领域共识

**判断：不可外推。** 不为“经典算法不超过多少个”给出伪精确上限；算法名称数、专题样本数、独立机制数分别记录。

独立性与边界：两个统计针对完全不同的样本与收录标准，不能合并、互相背书或用于计算领域占比。

- [An exhaustive review of the metaheuristic algorithms for search and optimization: taxonomy, applications, and open challenges](https://doi.org/10.1007/s10462-023-10470-y)；摘要；大范围算法名称整理及新颖性讨论。
- [Evolutionary neural architecture search: a survey](https://doi.org/10.55730/1300-0632.4189)；摘要；统计对象限定为特定年份的 ENAS 论文。

### 应用综述是否代表落地收益

**判断：证据不足，不作结论。** 应用卡应保留模型、约束、数据与验证场景；目前不能将文献覆盖直接写成部署成功或普遍提效。

独立性与边界：跨行业材料只能共同提醒证据层级，不能互证某个具体行业的有效性；需要回到各自原始研究和部署数据。

- [Role of metaheuristic algorithms in healthcare: a comprehensive investigation across clinical diagnosis, medical imaging, operations management, and public health](https://doi.org/10.1093/jcde/qwae046)；摘要；列出多个医疗研究方向，未据此确认临床部署级证据。
- [Transit network design and scheduling using genetic algorithm – a review](https://doi.org/10.11121/ijocta.01.2016.00258)；摘要；公交网络设计专题的有效性表述有具体研究背景。
- [Intelligent Scheduling Methods for Optimisation of Job Shop Scheduling Problems in the Manufacturing Sector: A Systematic Review](https://doi.org/10.3390/electronics14081663)；摘要；制造调度包含多种方法，不能把总体范围归功于群智能。

### DE 两代综述算不算独立验证

**判断：书目依赖已确认。** 2011与2016分别保留为经典综述和更新入口；不据两篇数量称某项结论已被独立交叉验证。

独立性与边界：Das、Suganthan 同时参与两篇，后篇标题明确为更新综述；本项仅核书目，不声称本轮核读了两篇全文。

- [Differential Evolution: A Survey of the State-of-the-Art](https://doi.org/10.1109/tevc.2010.2059031)；正式书目：作者、年份、标题；2011年的 DE 专题综述。
- [Recent advances in differential evolution – An updated survey](https://doi.org/10.1016/j.swevo.2016.01.004)；正式书目：作者、年份、标题；2016年的更新综述，共享两位作者。

### 在线年份与正式出版年份

**判断：版本日期已区分。** ABC 条目采用正式卷期2014并保留在线2012；2026年的多目标超启发式条目不能因为 DOI 字符串含2025就回填2025。

独立性与边界：这是两条书目各自的出版信息核对，不是对科学结论的多源独立验证。

- [A comprehensive survey: artificial bee colony (ABC) algorithm and applications](https://doi.org/10.1007/s10462-012-9328-0)；Springer 出版历史与卷期；在线2012与正式卷期2014并存。
- [Multi-objective hyper-heuristics: a survey](https://doi.org/10.1007/s10462-025-11486-2)；Springer 正式记录及 Crossref 日期字段；DOI 中的年份不能直接当作正式卷期年份。

### 能解析的 DOI 是否一定匹配题名

**判断：错误匹配已纠正。** Forrester/Keane 2009 代理优化综述使用 10.1016/j.paerosci.2008.11.001；错误候选 2008.10.001 不进入目录。超启发式2013采用正式版作者列表，作者稿作为另一个版本记录。

独立性与边界：核对 DOI、题名、作者、年份和版本；能解析仅证明存在记录，不证明与目标文章相同。

- [Recent advances in surrogate-based optimization](https://doi.org/10.1016/j.paerosci.2008.11.001)；出版社正式记录与 Crossref；正确 DOI 与题名、两位作者相符。
- [Hyper-heuristics: a survey of the state of the art](https://doi.org/10.1057/jors.2013.71)；机构正式记录与作者稿首页；正式发表记录含 Gendreau；旧作者稿作者列表有差别。

## 尚不能下结论

- 投资组合摘要合并提及多类约束；尚不能据此确定每一具体模型的复杂性。需要核对正文模型和原始复杂性证明。 入口：[Meta-heuristics for portfolio optimization](https://doi.org/10.1007/s00500-023-08177-x)。
- 本轮没有重新运行综述中的基准；随机种子可复现单次运行，不替代多次独立运行和公平预算的实验。 入口：[Instance Space Analysis for Algorithm Testing: Methodology and Software Tools](https://doi.org/10.1145/3572895)。
- 中文条目本轮主要保留为书目入口；未完成与所有英文专题逐段对照，不宣称中英文结论全部一致。 入口：[基于分解的演化多目标优化算法综述](https://jos.org.cn/jos/article/abstract/6672)。

## 版本和元数据风险

ABC 的2012在线日期与2014卷期均保存；跨平台的 published-online 字段不总能解释为首发时间，例如超启发式2013正式记录还出现2017平台在线字段。保留原始字段，按正式版本识别论文，不从 DOI 中猜年份。作者姓名缩写变体也需要人工识别，不单纯按字符串计算独立团队。

Forrester/Keane 的2009综述此前检索候选 DOI 10.1016/j.paerosci.2008.10.001 不匹配目标题名；已改为 10.1016/j.paerosci.2008.11.001。错误候选的原始查询记录保留作审计，但不进入目录或下载库。

书目收录与内容核读分开标记；无 DOI 的中文条目、教程和作者公开稿沿用原始入口。部分出版社页面抓取失败，不能因搜索命中就标作全文已读。引用位置优先使用作者公开稿、出版社摘要和机构记录。

## 可复用成果

- [完整文献清单 CSV](review-evidence/2026-10-16/review-catalog.csv)
- [RIS 文献库](review-evidence/2026-10-16/reviews.ris)
- [逐主张证据矩阵 CSV](review-evidence/2026-10-16/claim-matrix.csv)
- [150条检索候选的筛选记录](review-evidence/2026-10-16/candidate-screening.csv)

数据源：data/review_library.json；核读记录：data/review_reading_notes.json；核对议题：data/review_crosschecks.json。原始 Crossref 检索与单篇记录保存在 docs/review-evidence/2026-10-16/，部分继承来源见 docs/research-records/2026-10-16/。目录不包含论文全文副本。

维护顺序：collect_review_evidence.py（需要网络）→ 人工修改 review_selection.json、review_reading_notes.json 与 review_crosschecks.json → build_review_library.py → export_review_evidence.py → audit_review_coverage.py → 构建网站。前5项截断是当前检索限制，未来增量检索应记录新协议，避免改写本轮覆盖范围。

## 本地验证

相关 Python 检查通过，覆盖书目去重、DOI题名修正、证据来源分级、人工标注再生成、输出转义及既有研究地图/引用/模型/i18n检查。目录筛选与界面控制器检查通过；生成页面的资料数与目录一致，12个议题及待决问题的来源可追溯；资源和下载路径均存在，RIS条目数与目录一致。

研究地图增加“综述与交叉验证”入口，提供主题、作者/标题/DOI、阅读深度筛选和逐步显示。本轮完成内容与功能检查；未做实际浏览器视觉验收。

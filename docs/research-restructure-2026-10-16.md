# 研究路线重整核验记录

资料核验截止：2026-10-16。范围为20条代表性阅读路线；不是全领域穷尽综述。

起源、转折、近期与边界分别引用。近期综述节点的年份表示出版，不表示算法在该年诞生。原始研究的实验结论不推广为通用排名。

28个近期来源节点接入时间地图；经典主干保持16个，年内旁支随地图更新。

## 路线检查

|路线|近期范围|近期依据|交叉阅读|
|---|---|---|
|进化策略 ES|2023|[Discovering Evolution Strategies via Meta-Black-Box Optimization](https://arxiv.org/abs/2211.11260)；[Evolution strategies for continuous optimization: A survey of the state-of-the-art](https://doi.org/10.1016/j.swevo.2020.100694)|2020综述提供方法框架，2023论文展示学习更新的一种实现；后者不是对全部ES路线的独立复现。|
|遗传算法 GA|2021—2025|[Biased random-key genetic algorithms: A review](https://doi.org/10.1016/j.ejor.2024.03.030)；[A review on genetic algorithm: past, present, and future](https://doi.org/10.1007/s11042-020-10139-6)|通用GA综述与BRKGA专题相互补充；专题作者与框架开发者可能重叠，应用结果不等于所有GA都有同样收益。|
|模拟退火 SA|2024|[Machine learning aided metaheuristics: A comprehensive review of hybrid local search methods](https://doi.org/10.1016/j.eswa.2024.125192)|2006综述解释基础与扩展，2024综述核对学习辅助的具体介入点；没有据此认定所有学习型SA都优于经典SA。|
|禁忌搜索 TS|2024—2025|[Machine learning aided metaheuristics: A comprehensive review of hybrid local search methods](https://doi.org/10.1016/j.eswa.2024.125192)；[Exploring Tabu Tenure Policies with Machine Learning](https://doi.org/10.3390/electronics14132642)|经典教程给出记忆框架，近期综述与原始研究分别提供分类和策略实例；它们没有构成统一的跨领域性能保证。|
|GRASP|2025|[Greedy Randomized Adaptive Search Procedures with Path Relinking. An analytical review of designs and implementations](https://doi.org/10.1016/j.ejor.2025.02.022)|经典构造框架与2025重连综述构成时间衔接；综述作者包含长期开发者，仍需区分设计解释与独立性能检验。|
|粒子群 PSO|2022—2026|[Particle Swarm Optimization: A Comprehensive Survey](https://doi.org/10.1109/access.2022.3142859)；[Set-Based Particle Swarm Optimisation: A Review](https://doi.org/10.3390/math11132980)；[Particle swarm optimization: A survey of innovations over the last 10 years](https://doi.org/10.1016/j.cosrev.2026.100910)|2007与2017综述范围不同，2023专题只覆盖集合型PSO；2026入口保留预览核读标记，不能借其日期把所有内容标成已验证。|
|蚁群 ACO|2023—2026|[DeepACO: Neural-enhanced Ant Systems for Combinatorial Optimization](https://papers.neurips.cc/paper_files/paper/2023/hash/883105b282fe15275991b411e6b200c5-Abstract-Conference.html)；[Ant Colony Sampling with GFlowNets for Combinatorial Optimization](https://proceedings.mlr.press/v258/kim25a.html)；[Automated design of state transition rules in ant colony optimization by genetic programming: a comprehensive investigation](https://doi.org/10.1007/s12293-025-00435-9)；[Pheromone learning-enhanced neural ant colony optimization](https://doi.org/10.1016/j.neucom.2026.133375)|原始论文与2025研究的相关工作可交叉定位“学习哪个组件”；GFACS代码沿用DeepACO基础，不能算完全独立的底层实现验证。|
|分布估计 EDA|2021—2024|[Estimation of Distribution Algorithms in Machine Learning: A Survey](https://doi.org/10.1109/tevc.2023.3314105)；[A Survey on Recent Progress in the Theory of Evolutionary Algorithms for Discrete Optimization](https://doi.org/10.1145/3472304)|早期框架、2024学习专题和2021离散理论互补；“EDA用于机器学习”与“机器学习辅助EDA”在页面上分别解释。|
|差分进化 DE|2023—2025|[Differential Evolution: A Survey on Their Operators and Variants](https://doi.org/10.1007/s11831-024-10136-0)；[Surrogate-assisted differential evolution: A survey](https://doi.org/10.1016/j.swevo.2025.101879)|2011/2016综述核对历史，2025算子综述核对设计对象，代理专题提供具体问题边界；不采用仅凭综述趋势得出的普遍性能排序。|
|变邻域 VNS|2023|[Variable Neighborhood Search: The power of change and simplicity](https://doi.org/10.1016/j.cor.2023.106221)|2010方法综述与2023回顾提供时间衔接；后篇也有学术传承与纪念视角，不能当作独立基准排行榜。|
|大邻域 LNS / ALNS|2022—2025|[A survey of adaptive large neighborhood search algorithms and applications](https://doi.org/10.1016/j.cor.2022.105903)；[A review and ranking of operators in adaptive large neighborhood search for vehicle routing problems](https://doi.org/10.1016/j.ejor.2024.05.033)|通用ALNS与VRP专题范围不同；作者稿和正式版合并为同一资料，不把同一综述的版本当成独立研究。|
|CMA-ES|2022—2026|[CMA-ES with margin](https://doi.org/10.1145/3512290.3528827)；[Marginal Probability-Based Integer Handling for CMA-ES Tackling Single- and Multi-Objective Mixed-Integer Black-Box Optimization](https://doi.org/10.1145/3632962)；[Covariance Matrix Adaptation Evolution Strategy (CMA-ES): A Comprehensive Survey of Variants and Hybridizations](https://doi.org/10.1007/s11831-026-10557-z)|教程、2022/2024原始与扩展论文、2026综述分别提供机制、实例和综合判断。COCO提供基准，不被当作CMA算法的新发明。|
|神经进化 / NEAT|2023—2026|[Evolutionary Reinforcement Learning: A Survey](https://doi.org/10.34133/icomputing.0025)；[Evolutionary Reinforcement Learning: A Systematic Review and Future Directions](https://doi.org/10.3390/math13050833)；[Evolutionary neural architecture search: a survey](https://doi.org/10.55730/1300-0632.4189)|跨学科综述提供分类，ENAS专题提供特定对象的细节；其样本统计不外推为整个神经进化领域的比例。|
|多目标 NSGA-II / MOEA/D|2024—2026|[Evolutionary constrained multi-objective optimization: a review](https://doi.org/10.1007/s44336-024-00006-5)；[A Survey on Preference-Based Multi-Objective Evolutionary Algorithms](https://doi.org/10.3390/math14081365)|高维多目标、约束与偏好是互补专题；各自的模型和评测对象不同，不能合成一个适用于所有决策的结论。|
|人工蜂群 ABC|2025|[The Artificial Bee Colony Algorithm: A Comprehensive Survey of Variants, Modifications, Applications, Developments, and Opportunities](https://doi.org/10.1007/s11831-025-10269-w)；[A review on the versions of artificial bee colony algorithm for scheduling problems](https://doi.org/10.1007/s10878-025-01296-1)|经典与2025排程综述存在作者延续；新增通用综述来自另一作者组，但不同作者也不自动意味着其底层实验彼此独立。|
|代理辅助搜索|2024—2025|[A survey of surrogate-assisted evolutionary algorithms for expensive optimization](https://doi.org/10.1007/s41965-024-00165-w)；[Surrogate-assisted evolutionary algorithms for expensive combinatorial optimization: a survey](https://doi.org/10.1007/s40747-024-01465-5)；[Surrogate-assisted differential evolution: A survey](https://doi.org/10.1016/j.swevo.2025.101879)|2011综述与近年材料可对齐模型管理主线；组合专题与连续专题的问题表示不同，不能直接搬用结论。|
|质量多样性|2023—2026|[A survey on Quality-Diversity optimization: Approaches, applications, and challenges](https://doi.org/10.1016/j.swevo.2025.102240)|2016概念解释与2026引言中的演进脉络相互对照；新综述的统计范围和软件发布时间不被当作方法发明时间。|
|演化多任务|2025|[A Survey on Evolutionary Multitask Optimization](https://doi.org/10.37965/jait.2025.0730)|中文总览、2023迁移专题和2025框架综述提供不同视角；本轮未把中文条目标记为逐段全文核读。|
|选择、配置与自动设计|2025—2026|[Meta-Black-Box optimization for evolutionary algorithms: Review and perspective](https://doi.org/10.1016/j.swevo.2024.101838)；[Liu et al. — A Systematic Survey on Large Language Models for Algorithm Design (180+ papers)](https://doi.org/10.1145/3787585)；[Multi-objective hyper-heuristics: a survey](https://doi.org/10.1007/s10462-025-11486-2)|2013/2024超启发式、2025MetaBBO和2026专题的分类视角不同；框架名相似不表示历史上存在单一师承链。|
|USPEX 结构搜索|2024|[Machine learning assisted crystal structure prediction made simple](https://doi.org/10.20517/jmi.2024.18)|原始USPEX与2024领域综述对齐工具流程；相邻的生成模型、机器学习力场和PSO工具明确作为领域对照，不记作USPEX自身算法升级。|

## 可重复检查

运行 tools/build_research_routes.py、tools/build_review_library.py、tools/audit_review_coverage.py、tools/export_review_evidence.py，再构建页面。tests/test_research_routes.py 检查覆盖、引用和日期；tests/test_research_routes.cjs 检查筛选、展开、空状态、跨路线跳转和锚点。

## 保留的研究边界

综述和原始研究分开；摘要核读与章节核读分开；CMA-ES Margin会议版与扩展版不算两次独立证据；机器学习晶体结构预测代表领域交汇，不表示USPEX本身在该年升级。PSO 2026综述仅作已核验书目入口。未进行全部论文的全文核读、所有实验的独立复现或外部专家审稿。

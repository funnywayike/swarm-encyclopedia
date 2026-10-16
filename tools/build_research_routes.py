"""Assemble editorial routes, bibliographic sources and dated research-map entries."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name):return json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))
def save(name,value):(ROOT/'data'/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def build():
    editorial=load('research_routes_editorial.json');new=load('research_routes_sources.json')['sources']
    m=load('research_map.json');sup=load('research_map_supplement.json');views=load('research_reading_views.json')
    library=load('review_library.json');refs={x['id']:x for x in m['references']}
    for a in library['articles']:
        refs.setdefault(a['id'],dict(a,kind=a.get('kind','综述')))
        for key in ['readingLevel','readingLocation','scopeNote','readingURL','authors','journal']:
            if key in a:refs[a['id']][key]=a[key]
    refs.update({x['id']:x for x in new})
    names={x['id']:x['name'] for x in views['methods']}
    assert set(names)=={x['id'] for x in editorial['routes']}
    titles={
      'les':'学习演化策略：更新规则也能被学习','ga-brkga':'随机键遗传算法：综述与混合机制',
      'local-learning':'局部搜索与机器学习：专题回顾','tabu-learning':'学习禁忌长度：一项实验研究',
      'grasp-review':'GRASP与路径重连：专题回顾','pso2026':'PSO近期综述：书目入口',
      'deepaco':'DeepACO：学习启发信息','gfacs':'GFACS：生成先验与蚁群搜索',
      'aco-gp':'用遗传编程设计ACO转移规则','aco-pheromone':'PL-NACO：学习信息素增量',
      'eda-ml':'EDA与机器学习：任务与模型回顾','de-operators':'DE算子与变体：专题回顾',
      'vns-review':'变邻域、变表述与数学启发式','alns-operators':'ALNS破坏与修复算子：VRP综述',
      'cma-margin':'CMA-ES with Margin：混合整数搜索','cma-extended':'混合整数CMA-ES：扩展研究',
      'cma2026':'CMA-ES近期综述：条件与扩展','neuro-2025':'进化强化学习：专题回顾',
      'moo-constraints':'约束多目标：可行性与解集','moo-preferences':'偏好多目标：把关注区域纳入搜索',
      'abc-review':'人工蜂群：机制、变体与应用回顾','surrogate-review':'代理辅助进化：模型与评价管理',
      'surrogate-discrete':'离散代理辅助：表征与模型','qd-review':'质量多样性：机制与开放问题',
      'multitask2025':'演化多任务：迁移机制与边界','metabbo-review':'MetaBBO：学习黑盒优化策略',
      'csp-ml-review':'晶体结构预测：机器学习领域对照'}
    lane={i:('si' if i in ['pso','aco','abc'] else 'or' if i in ['sa','ts','grasp','vns','lns'] else 'design' if i in ['configuration','surrogate'] else 'evo') for i in names}
    node_by_id={n['id']:n for n in m['nodes']}
    added=[];used=set()
    for route in editorial['routes']:
        route['name']=names[route['id']]
        assert [s['id'] for s in route['stages']]==['origin','turn','recent','limits']
        assert all(x in names for x in route['related'])
        for stage in route['stages']:
            assert stage['refs'] and all(x in refs for x in stage['refs']),(route['id'],stage)
            used.update(stage['refs'])
        recent=route['stages'][2]
        route['mapNodes']=[]
        for identifier in recent['refs']:
            r=refs[identifier]
            if not identifier.startswith('r26-') or r['year']<2022:continue
            nid='route-'+identifier[4:]
            route['mapNodes'].append(nid)
            if nid in node_by_id:continue
            n=dict(id=nid,year=r['year'],lane=lane[route['id']],title=titles.get(identifier[4:],r['title']),kind=r['kind'],summary=recent['body'],contribution=r.get('scopeNote',recent['title']),boundary='综述年份不是方法起源年份。'+route['stages'][3]['body'],refs=[identifier],teams=[],apps=[])
            node_by_id[nid]=n;added.append(n)
        method=next(x for x in views['methods'] if x['id']==route['id'])
        method['nodes']=list(dict.fromkeys(method['nodes']+route['mapNodes']))
    m['nodes']=sorted(node_by_id.values(),key=lambda n:(n['year'],n['id']))
    for n in m['nodes']:
        if n['id']=='llm26':n['summary']=n['summary'].replace('180多篇','相关').replace('180 多篇','相关')
    refs_needed=[refs[x] for x in sorted(used) if x not in {r['id'] for r in m['references']}]
    m['references']+=refs_needed
    for key,values in [('references',refs_needed),('nodes',added)]:
        existing={x['id']:x for x in sup[key]}
        existing.update({x['id']:x for x in values});sup[key]=list(existing.values())
    # Sources are authored records; abstract text is neither required nor exported here.
    selected={x:{k:v for k,v in refs[x].items() if k!='abstract'} for x in sorted(used)}
    result=dict(updated=editorial['updated'],scope='20条代表性研究路线；沿起源、转折、近期进展和研究边界阅读。不同路线的近年证据深度不同，核读层级逐条标注；不宣称穷尽检索或全部全文核验。',routes=editorial['routes'],sources=selected)
    save('research_routes.json',result);save('research_map.json',m);save('research_map_supplement.json',sup);save('research_reading_views.json',views)
    print(f"Research routes: {len(result['routes'])}; referenced sources: {len(selected)}; map nodes: {len(m['nodes'])}")
if __name__=='__main__':build()

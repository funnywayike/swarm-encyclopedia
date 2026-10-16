"""Assemble the local research map from curated choices and saved source records.
Run tools/research_catalog.py first; the exact DOI metadata snapshot is kept in data/research_metadata.json.
This does not reproduce published experiments or claim exhaustive database coverage.
"""
import csv,html,inspect,json,re,sys,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'py'),str(ROOT/'tools')]
import registry,solvers
def read(name):return json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))
def write(name,value):(ROOT/'data'/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def text(s):return re.sub('<[^>]+>','',html.unescape(html.unescape(s or ''))).strip()
def doi(url):
 m=re.search(r'(10\.\d{4,9}/.+)',urllib.parse.unquote(url or ''),re.I)
 return m.group(1).lower()if m else ''
def canonical(r):return doi(r['url'])or r['url'].rstrip('/')
def csvwrite(path,rows):
 with path.open('w',newline='',encoding='utf-8-sig')as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 m=read('research_map.json');apps=read('apps.json');c=read('research_catalog_candidates.json');s=read('research_application_selection.json');sup=read('research_map_supplement.json');meta=read('research_metadata.json')['records']
 refs={r['id']:r for r in m['references'] if not r['id'].startswith('app0') and not r['id'].startswith('origin-')}
 for r in sup['references']:
  refs[r['id']]=dict(r)
  if r['year']==2026 and '官方'in r['kind']:refs[r['id']]['year']='持续更新；2026核验'
 refs['cryptoBooleanSurvey2023'].update(year=2023,kind='同行评审综述',url='https://doi.org/10.1007/s12095-023-00662-2')
 refs['automatedMhDesignSurvey2023'].update(year=2024,kind='同行评审综述',url='https://openreview.net/pdf?id=qhtHsvF5zj',versionNote='2023预印本；2024年2月发表于TMLR')
 refs['rlco2021']['title']='Mazyavkina, Sviridov, Ivanov & Burnaev — Reinforcement learning for combinatorial optimization: A survey'
 refs['robotics2023']['title']='Duan, Huo & Fan — From animal collective behaviors to swarm robotic cooperation'
 refs['vns1997']['title']='Mladenović & Hansen — Variable neighbourhood search'
 refs['holland1975']['versionNote']='1975初版；链接为1992年MIT Press再版'
 # Preserve historical dates; store registry dates separately instead of silently replacing them.
 for r in refs.values():
  rec=meta.get(doi(r['url']))
  if not rec:
   rec=next((b.get('record')for b in c['bibliography']if b['id']==r['id']),None)
  if rec and not rec.get('error'):
   r['metadata']={k:rec[k]for k in ('DOI','title','author','container-title','published','published-online','published-print','type')if k in rec}
   r['checked']='2026-10-16';r['verification']='书目记录核验；不表示实验复现'
 def refrecord(id,identifier,fallback,year=None,kind=None):
  if identifier.startswith('@'):return identifier[1:]
  url=identifier if identifier.startswith('http')else 'https://doi.org/'+identifier
  rec=meta.get(doi(url),{})
  title=text(' '.join(rec.get('title')or[fallback]))
  y=year or (rec.get('published',rec.get('issued',{})).get('date-parts')or[[None]])[0][0]
  record={'id':id,'year':y or '版本见来源','kind':kind or ('工作论文'if rec.get('type')=='posted-content'else '代表性研究'),'title':title,'url':url,'checked':'2026-10-16','verification':'摘要核验'if rec.get('abstract')else '题名与书目核验；支持主题范围，不支持性能结论'}
  if rec and not rec.get('error'):record['metadata']={k:rec[k]for k in ('DOI','title','author','container-title','published','published-online','published-print','type')if k in rec}
  refs[id]=record;return id
 screening=[];ledger=[]
 for choice,e in zip(s['entries'],apps['entries']):
  i=choice['index'];selector=choice['selector'];cand=c['applications'][i]['candidates']
  identifier=cand[selector]['DOI']if isinstance(selector,int)else selector
  rid=refrecord('app%03d'%i,identifier,e['title'])
  e['oneliner']=choice['summary'];e['researchRefs']=[rid]
  e['sourceScope']='代表性研究入口；关联问题页仅解释相关模型，不表示复现此论文或覆盖行业全部约束。'
  for x in cand:
   screening.append({'topic':e['title'],'query':c['applications'][i]['query'],'DOI':x['DOI'],'title':text(' '.join(x.get('title',[]))),'decision':'selected'if x['DOI'].lower()==identifier.lower()else 'not selected','reason':'人工选择代表性来源'if x['DOI'].lower()==identifier.lower()else ('同行评审报告不是论文正文'if x.get('type')=='peer-review'else '未作为本主题的代表证据；不作研究质量判断')})
  r=refs[rid];ledger.append({'index':i,'title':e['title'],'industry':e['industry'],'summary':e['oneliner'],'source':rid,'url':r['url'],'verification':r.get('verification','官方原始记录核验'),'scope':e['sourceScope']})
 # Update the copied industry entries, without losing their internal provenance fields.
 for ind in m['industryEvidence']:
  for ent in ind['entries']:
   app=next(e for e in apps['entries']if e['title']==ent['title'])
   ent.update(summary=app['oneliner'],refs=app['researchRefs'],scope=app['sourceScope'])
  ind['count']=len(ind['entries'])
  ind['evidence']=ind['evidence'].replace('预印本','综述')
  if ind['id']=='security-game':
   ind['boundary']='密码学布尔函数设计、攻防博弈和策略演化是不同研究对象；不能由此推断现代密码已被破解。'
 # No internal implementation vocabulary or unsupported size/ranking claims in category hints.
 hints={'cont':'参数拟合、设计和反演：变量常是实数，但约束和评价成本各不相同。','subset':'选择特征、措施或物品；具体约束决定模型，不能仅凭选择结构就视为背包。','network':'网络中的路径、路由与流；需区分单条路线和多车、多资源模型。','adv':'安全设计、攻防决策与策略演化；这些研究不都属于最优化。'}
 for cat in apps['categories']:
  if cat['id']in hints:cat['hint']=hints[cat['id']]
 # Extend nodes and teams idempotently. A single review affiliation is a reading example, not a sustained team.
 node_map={n['id']:n for n in m['nodes']};node_map.update({n['id']:n for n in sup['nodes']});m['nodes']=sorted(node_map.values(),key=lambda n:(n['year'],n['id']))
 team_map={t['id']:t for t in m['teams']if t['id']!='nudt'};team_map.update({t['id']:t for t in sup['teams']});m['teams']=list(team_map.values())
 for n in m['nodes']:n['teams']=[t for t in n.get('teams',[])if t in team_map]
 m['researchQuestions']=sup['researchQuestions'];m['relations']=sup['relations']
 origins=read('research_algorithm_origins.json');algos=read('algos.json');algorithm_ledger=[]
 special={
 'pso':'原始PSO在连续空间更新位置与速度；本站TSP版把移动改为交换序列，并结合局部改进。',
 'de':'原始DE使用实数差向量；本站TSP版使用排列交换序列与顺序交叉，不是原始连续更新式。',
 'aco':'本站TSP演示以Ant System式信息素构造为基础；ACS、MMAS等变体不能混称为同一实现。',
 'ga':'本站TSP版使用排列编码、顺序交叉和局部改进；它不是所有GA变体的统一基准。',
 'cma-es':'本站TSP版采用随机键与对角/可分离协方差近似，另有局部改进；不等同于原论文完整协方差CMA-ES。',
 'cem':'本站TSP版学习位置与城市的频率矩阵并采样，结合精英与局部改进；不代表所有分布模型。',
 'lk':'本站是有限搜索预算的教学实现；不等同于完整LKH工程求解器。',
 'sa':'有限预算的退火与降温演示不保证全局最优；理论收敛条件不能直接当作运行承诺。',
 'ils':'扰动、局部搜索与接受规则构成迭代局部搜索；本站预算与邻域只是具体选择。',
 'grasp':'随机化贪心构造后做局部搜索；原始研究和本站的具体构造对象不同。',
 'vns':'以切换邻域组织搜索；表现取决于具体邻域、局部搜索与预算。'}
 for e in algos:
  key=e['key'];identifier=origins[key];rid=refrecord('origin-'+key,identifier,text(e['refs'][0]),year=1975 if key=='ga'else (2003 if key=='ils'else None),kind='方法出处')
  if key=='afsa':refs[rid].update(url='https://sysengi.cjoe.ac.cn/CN/10.12011/1000-6788(2002)11-32',title='李晓磊、邵之江、钱积新 — 一种基于动物自治体的寻优模式：鱼群算法',year=2002,verification='原期刊页面核验')
  if key=='abc':refs[rid]['versionNote']='此为2007期刊论文；2005技术报告为更早出处，见Erciyes官方书目'
  if key=='fa':refs[rid]['versionNote']='此为2009会议论文；2008专著有更早介绍，不能误配到无关章节'
  note=special.get(key,'本站TSP演示把该方法适配到排列空间，使用领域算子及共享局部改进；演示成绩只对本站实现和预算成立，不能代表原论文或整个算法家族。')
  cls=solvers.SOLVERS.get(key);line=inspect.getsourcelines(cls)[1]if cls else None
  algorithm_ledger.append({'key':key,'name':e['name'],'url':'/algo/'+e['slug'].strip('/')+'/','refs':[rid],'note':note,'originalCitation':text(e['refs'][0]),'code':'py/solvers.py','line':line})
 problem_ledger=[];problems=read('problems.json')
 for section in ('knapsack_variants','class_pages','abstract_types'):
  for p in problems[section]:
   path='problem/knapsack/'+p['id']+'/index.html'if section=='knapsack_variants'else 'problem/'+p['dir']+'/index.html'
   f=ROOT/path;content=f.read_text(encoding='utf-8')if f.exists()else ''
   dm=re.search(r'window\.PAGE_DOMAIN = "([^"]+)"',content);pm=re.search(r'window\.PAGE_PRESETS = (\{.*?\});\n',content)
   dom=dm.group(1)if dm else None;opts=(next(iter(json.loads(pm.group(1)).values()),{})or{})if pm else {}
   fidelity=registry.fidelity(dom,opts.get('variant'))if dom else {'level':'reference','note':'分类或定义页面：不据此声称有独立行业求解器。'}
   note=fidelity['note']or '采用该域登记的标准目标定义；默认实例和搜索预算属于本站教学设置。'
   problem_ledger.append({'id':p['id'],'name':p['name'],'url':'/'+path.removesuffix('index.html'),'domain':dom,'variant':opts.get('variant'),'fidelity':fidelity['level'],'note':note,'sourceCount':len(p.get('sources',[])),'sources':[text(z)for z in p.get('sources',[])],'modelScope':text(p.get('site_model','')),'pageExists':f.exists()})
 assert len(algorithm_ledger)==45 and len(problem_ledger)==96
 m['siteCoverage']={'algorithms':[dict(x)for x in algorithm_ledger],'problems':problem_ledger,'scope':'模型登记与文献表述的一致性对照；未逐篇复现实验，也不把算法名称相同当成实现相同。'}
 m['version']='2026-10-16-local-research-v5';m['updated']='2026-10-16'
 m['methodNote']='2026-10-16核验。96个应用主题与13个领域的Crossref检索及补充检索已保留原始响应；来源经人工选取，书目、摘要与官方项目记录分层标注。这是代表性主干导览，不是全球穷尽综述；未使用订阅数据库完整导出，也未复现所引论文的实验。'
 # Canonical DOI / URL dedup; remap every source list.
 aliases={};seen={};unique=[]
 for r in refs.values():
  k=canonical(r)
  if k in seen:aliases[r['id']]=seen[k]
  else:seen[k]=r['id'];aliases[r['id']]=r['id'];unique.append(r)
 def remap(x):
  if isinstance(x,dict):
   for k,v in x.items():
    if k in ('refs','evidence','researchRefs')and isinstance(v,list):x[k]=list(dict.fromkeys(aliases.get(z,z)for z in v))
    elif k=='source'and isinstance(v,str):x[k]=aliases.get(v,v)
    else:remap(v)
  elif isinstance(x,list):
   for v in x:remap(v)
 remap(m);remap(apps);remap(ledger)
 m['references']=unique
 # Remove stale preprint cautions now that formal versions were verified.
 for ind in m['industryEvidence']:
  if any('cryptoBoolean' in z for z in ind['refs']):ind['boundary']='布尔函数设计不等于破解现代密码；移动目标防御、演化博弈与密码设计应分别阅读。'
  if any('automatedMhDesign' in z for z in ind['refs']):ind['boundary']='算法配置、算法选择与自动设计输出不同；2024年TMLR综述有正式版本，生成方案仍需独立测试。'
 # Website payload contains readable provenance, not code locations or machine audit bookkeeping.
 for row in m['siteCoverage']['algorithms']:
  row.pop('code',None);row.pop('line',None)
 write('research_map.json',m);write('apps.json',apps)
 write('research_consistency_audit.json',{'updated':m['updated'],'scope':m['siteCoverage']['scope'],'algorithms':algorithm_ledger,'problems':problem_ledger,'applications':ledger})
 out=ROOT/'docs/research-records/2026-10-16';out.mkdir(parents=True,exist_ok=True)
 csvwrite(out/'application-screening.csv',screening);csvwrite(out/'application-evidence.csv',ledger)
 bib=[]
 for r in unique:
  md=r.get('metadata',{});authors=' and '.join(a.get('family',a.get('name',''))+', '+a.get('given','')for a in md.get('author',[]))
  esc=lambda x:str(x).replace('{','\\{').replace('}','\\}')
  bib.append('@misc{'+r['id']+',\n  title={'+esc(r['title'])+'},\n  year={'+str(r['year'])+'},\n  author={'+esc(authors)+'},\n  url={'+r['url']+'}\n}')
 (out/'references.bib').write_text('\n\n'.join(bib)+'\n',encoding='utf-8')
 print(json.dumps({'nodes':len(m['nodes']),'teams':len(m['teams']),'references':len(unique),'algorithms':len(algorithm_ledger),'problems':len(problem_ledger),'applications':len(ledger),'fidelity':{k:sum(x['fidelity']==k for x in problem_ledger)for k in set(x['fidelity']for x in problem_ledger)},'missingProblemSources':[x['id']for x in problem_ledger if not x['sourceCount']]},ensure_ascii=False))
if __name__=='__main__':main()


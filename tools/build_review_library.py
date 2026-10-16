"""Build a bounded, DOI-deduplicated review collection with explicit reading levels."""
import concurrent.futures,csv,hashlib,html,json,re,time,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/'docs/review-evidence/2026-10-16';RAW.mkdir(parents=True,exist_ok=True)
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def doi(u):
 m=re.search(r'10\.\d{4,9}/.+',urllib.parse.unquote(u or ''),re.I);return m.group(0).lower()if m else ''
def clean(s):return re.sub(r'\s+',' ',re.sub('<[^>]*>',' ',html.unescape(html.unescape(s or '')))).strip()
def group(title,key=''):
 t=(title+' '+key).lower()
 if any(x in t for x in ['landscape','structural bias','parameter control','black-box complexity','complexity theory','recent progress in the theory','runtime analysis','benchmarking evolutionary']):return '理论、景观与实验方法'
 if any(x in t for x in ['large-scale','parallelism','multitask','constrained multiobjective','estimation of distribution','genetic programming','annealing','tabu search','iterated local search','large neighborhood']):return '规模、表征与搜索框架'
 if any(x in t for x in ['综述','群智']) and re.search('[一-鿿]',title):return '中文交叉阅读'
 if any(x in t for x in ['robot','swarm engineering','collective behavior']):return '群体机器人'
 if any(x in t for x in ['surrogat','constraint','multi-object','many-object','multimodal','dynamic opt','uncertain','quality-diversity','quality diversity','fitness approximation','memetic']):return '复杂优化与混合机制'
 if any(x in t for x in ['hyper-heur','algorithm design','algorithm selection','configuration','machine learning into','combinatorial optimization: a methodological','neural architecture']):return '学习与自动设计'
 if any(x in t for x in ['benchmark','statistical test','experimentation','instance space']):return '实验与证据方法'
 if any(x in t for x in ['particle swarm','differential evolution','ant colony optimization','artificial bee','genetic algorithm tutorial','cma evolution','variable neighbourhood search']):return '经典算法与框架'
 if any(x in t for x in ['taxonomy','metaheuristic algorithms for search','optimization metaheuristics','fifty years','history and current','representative swarm']):return '总览、历史与分类'
 return '行业与问题应用'
def build():
 m=load(ROOT/'data/research_map.json');selection=load(ROOT/'data/review_selection.json');discovery=load(ROOT/'data/review_candidates.json')
 records={}
 for folder in [ROOT/'docs/research-records/2026-10-16',RAW]:
  for p in folder.glob('*.json'):
   try:
    d=load(p);response=d.get('response',{});msg=response.get('message',{});xs=msg.get('items',[])if isinstance(msg,dict)else []
    if isinstance(msg,dict)and msg.get('DOI'):xs=[msg]
    for x in xs:
     if x.get('DOI'):records[x['DOI'].lower()]=x
   except Exception:pass
 expanded=load(ROOT/'data/review_candidates_expanded.json')
 for batch in expanded['searches']:
  for x in batch['items']:
   if x.get('DOI'):records[x['DOI'].lower()]=x
 for x in load(ROOT/'data/research_metadata.json')['records'].values():
  if x.get('DOI')and not x.get('error'):records[x['DOI'].lower()]=x
 for s in discovery['searches']:
  for x in s['items']:
   if x.get('DOI'):records[x['DOI'].lower()]=x
 needed=[x['DOI']for x in selection['selected']if x['DOI'].lower()not in records]
 def exact(d):
  url='https://api.crossref.org/works/'+urllib.parse.quote(d,safe='')
  try:
   for attempt in range(3):
    try:
     with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'SwarmEncyclopediaReviewAudit/0.1'}),timeout=30)as f:r=json.load(f)
     break
    except Exception as e:
     if '429' not in str(e) or attempt==2:raise
     time.sleep(30*(attempt+1))
   (RAW/('doi-'+hashlib.sha256(d.lower().encode()).hexdigest()[:12]+'.json')).write_text(json.dumps({'url':url,'retrieved':'2026-10-16','response':r},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
   return d.lower(),r['message']
  except Exception as e:return d.lower(),{'error':str(e)}
 with concurrent.futures.ThreadPoolExecutor(max_workers=1)as pool:
  for k,v in pool.map(exact,needed):records[k]=v
 for source in load(ROOT/'data/research_routes_sources.json')['sources']:
  md=source.get('metadata',{})
  if md.get('DOI'):records[md['DOI'].lower()]=md
 old=[]
 for x in m['references']:
  title=' '.join(x.get('metadata',{}).get('title',[]))or x['title']
  if x.get('kind')!='原始研究' and (re.search(r'survey|review|tutorial|综述|研究进展',title,re.I)or'综述'in x.get('kind','')or x['id']in ['fiftyYears2025','back1997','qd2016']):old.append(x)
 catalog=[];seen={};aliases={}
 def add(identifier,url,title,key,kind='',oldYear=None,authors=None):
  k=doi(url)or url
  if k in seen:aliases[identifier]=seen[k];return
  md=records.get(doi(url),{})
  if md.get('error'):raise RuntimeError((url,md))
  tt=clean(' '.join(md.get('title',[]))or title)
  if not tt:raise ValueError('Missing verified title: '+url)
  dates={f:md.get(f,{}).get('date-parts',[[]])[0]for f in ('published','published-online','published-print')}
  dates={k:v for k,v in dates.items()if v and v[0]}
  y=(dates.get('published-print')or dates.get('published')or[oldYear])[0]
  auth=md.get('author',[]);a=authors or [clean(' '.join([x.get('given',''),x.get('family',x.get('name',''))]))for x in auth]
  at='tutorial'if re.search('tutorial',tt,re.I)or'教程'in kind else 'bibliometric'if'bibliometric'in tt.lower()else'review'
  if identifier in ['back1997']:at='historical-commentary'
  abstract=clean(md.get('abstract',''))
  row=dict(id=identifier,doi=doi(url),title=tt,url=url,year=y,dates=dates,authors=a,journal=' '.join(md.get('container-title',[])),kind=kind or ('综述章节'if md.get('type')=='book-chapter'else'同行评审综述'),articleType=at,category=group(tt,key),language='中文'if re.search('[一-鿿]',tt)else'英文',abstract=abstract,readingLevel='metadata',readingLabel='书目收录',readingLocation='已保存的书目记录；本轮未核读正文',scopeNote='当前仅作主题与书目入口；不据此确认量化性能或领域共识。',publicationType=md.get('type','official-record'),checked='2026-10-16',recordDOI=md.get('DOI',''))
  catalog.append(row);seen[k]=identifier;aliases[identifier]=identifier
 for r in old:add(r['id'],r['url'],r['title'],r['id'],r.get('kind',''),r['year'],None)
 for s in selection['selected']:
  d=s['DOI'];add('review-'+s['topic']+'-'+hashlib.sha256(d.lower().encode()).hexdigest()[:6],'https://doi.org/'+d,'',s['topic'])
 for x in selection['manual']:
  add(x['id'],x['url'],x['title'],x['topic'],x['kind'],x['year'],x['authors']);row=next(a for a in catalog if a['id']==aliases[x['id']]);row['articleType']=x['type']
 annotation=load(ROOT/'data/review_reading_notes.json')
 for row in catalog:
  row.update(annotation['notes'].get(row['id'],{}))
  if row['id']in annotation['categoryOverrides']:row['category']=annotation['categoryOverrides'][row['id']]
  if row['articleType']=='tutorial'and row['publicationType']=='journal-article':row['kind']='同行评审教程'
 catalog.sort(key=lambda x:(x['category'],str(x['year']),x['title']))
 output={'updated':'2026-10-16','scope':'有限主题检索与人工选取的综述、教程和方法学资料目录；不代表全领域穷尽检索、系统综述认证或独立实验复现。','protocol':discovery['protocol']+' Supplement: '+expanded['protocol'],'articles':catalog,'aliases':aliases,'crossChecks':load(ROOT/'data/review_crosschecks.json')['checks']}
 (ROOT/'data/review_library.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 chosen={x['DOI'].lower()for x in selection['selected']}
 with(RAW/'candidate-screening.csv').open('w',encoding='utf-8-sig',newline='')as f:
  w=csv.DictWriter(f,fieldnames=['topic','query','doi','title','decision','reason']);w.writeheader()
  for q in discovery['searches']:
   for x in q['items']:
    selected=x.get('DOI','').lower()in chosen;typ=x.get('type')
    w.writerow(dict(topic=q['topic'],query=q['query'],doi=x.get('DOI'),title=clean(' '.join(x.get('title',[]))),decision='selected'if selected else'not-selected',reason='人工选中代表资料'if selected else'评审意见不是综述正文'if typ=='peer-review'else'本轮未作为代表综述；可能偏题、非综述或由其他来源替代，不作质量评级'))
 print('catalog',len(catalog),'new DOI lookups',len(needed),'categories',sorted({a['category']for a in catalog}))
 for a in catalog:
  if a['abstract']:print('ABSTRACT',a['id'],a['doi'],a['year'],a['title'],'\n',a['abstract'][:2300],'\n',flush=True)
if __name__=='__main__':build()

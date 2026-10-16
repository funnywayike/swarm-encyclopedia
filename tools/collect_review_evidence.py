"""Bounded review discovery. Search hits are candidates, not reviewed evidence."""
import concurrent.futures,json,time,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/review-evidence/2026-10-16';OUT.mkdir(parents=True,exist_ok=True)
QUERIES=[
('history','Fifty years of metaheuristics survey history'),
('taxonomy','survey optimization metaheuristics taxonomy algorithmic behavior'),
('pso','Particle swarm optimization An overview Poli Kennedy Blackwell'),
('pso-modern','Particle swarm optimization single objective continuous space problems review Bonyadi Michalewicz'),
('aco','Ant colony optimization Dorigo Birattari Stutzle 2006 overview'),
('de','Differential Evolution A Survey of the State of the Art Das Suganthan'),
('de-update','Recent advances in differential evolution updated survey Das Mullick Suganthan'),
('abc','comprehensive survey artificial bee colony algorithm applications Karaboga Gorkemli Ozturk'),
('ga','A genetic algorithm tutorial Whitley'),
('cma','CMA evolution strategy tutorial Hansen'),
('vns','Variable neighbourhood search methods and applications Hansen Mladenovic Perez'),
('memetic','Memetic algorithms and memetic computing optimization A literature review Neri Cotta'),
('constraints','Theoretical numerical constraint handling techniques evolutionary algorithms survey Coello'),
('multiobjective','Evolutionary multi objective optimization historical view Coello'),
('manyobjective','many objective evolutionary optimization survey review'),
('surrogates','Surrogate assisted evolutionary computation Recent advances future challenges Jin'),
('dynamic','Evolutionary dynamic optimization survey state of art Nguyen Yang Branke'),
('robust','Evolutionary Optimization Uncertain Environments Survey Jin Branke'),
('multimodal','Real parameter evolutionary multimodal optimization survey state art Das'),
('multitask','evolutionary multitasking survey evolutionary algorithms knowledge transfer'),
('qd','Quality Diversity optimization novel branch stochastic optimization review'),
('hyper','Hyper heuristics survey state art Burke 2013'),
('automated','Automated Design Metaheuristic Algorithms Survey'),
('configuration','algorithm selection survey automated algorithm configuration review'),
('learning','Machine learning combinatorial optimization methodological tour horizon'),
('robotics','review swarm robotics tasks Bayindir'),
('routing','Heuristics multi attribute vehicle routing problems survey synthesis Vidal'),
('scheduling','review metaheuristics flexible job shop scheduling problems'),
('benchmarks','Benchmarking in Optimization Best Practice and Open Issues'),
('landscape','exploratory landscape analysis survey algorithm selection optimization')]
def fetch(url):
 for attempt in range(3):
  try:
   req=urllib.request.Request(url,headers={'User-Agent':'SwarmEncyclopediaReviewAudit/0.1'})
   with urllib.request.urlopen(req,timeout=25)as f:return json.load(f)
  except Exception as e:
   if attempt==2:return {'error':str(e)}
   time.sleep(1+attempt)
def job(item):
 key,q=item;url='https://api.crossref.org/works?'+urllib.parse.urlencode({'query.bibliographic':q,'rows':5,'filter':'until-pub-date:2026-10-16'})
 p=OUT/('search-'+key+'.json')
 if p.exists():d=json.loads(p.read_text(encoding='utf-8'))
 else:d={'query':q,'url':url,'retrieved':'2026-10-16','response':fetch(url)};p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 return {'topic':key,'query':q,'url':url,'items':d['response'].get('message',{}).get('items',[]),'error':d['response'].get('error')}
def main():
 with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:rows=list(pool.map(job,QUERIES))
 out={'date':'2026-10-16','protocol':'30 English bibliographic queries, relevance top 5, Crossref cutoff 2026-10-16; discovery candidates only, supplemented by existing source records and original publisher/institution pages.','searches':rows}
 (ROOT/'data/review_candidates.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 for x in rows:print(x['topic'],[(i,a.get('DOI'),' '.join(a.get('title',[]))[:110],a.get('type'))for i,a in enumerate(x['items'])],flush=True)
if __name__=='__main__':main()

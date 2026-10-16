import concurrent.futures,json,time,urllib.parse,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def job(x):
 key=x['topic'];q=x['query'];url='https://api.crossref.org/works?'+urllib.parse.urlencode({'query.bibliographic':q,'rows':15,'filter':'until-pub-date:2026-10-16'})
 path=ROOT/'docs/review-evidence/2026-10-16'/('expanded-'+key+'.json')
 if path.exists():
  d=json.loads(path.read_text(encoding='utf-8'))
  if not d.get('response',{}).get('error'):return dict(topic=key,query=q,url=url,items=d['response'].get('message',{}).get('items',[]),error=None)
 response={}
 for attempt in range(4):
  try:
   with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'SwarmEncyclopediaCoverageAudit/0.2'}),timeout=30)as f:response=json.load(f)
   break
  except Exception as e:
   response={'error':str(e)}
   if attempt<3:time.sleep((15 if '429'in str(e)else 2)*(attempt+1))
 d=dict(query=q,url=url,retrieved='2026-10-16',response=response)
 path.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(key,len(response.get('message',{}).get('items',[])),response.get('error',''),flush=True)
 return dict(topic=key,query=q,url=url,items=response.get('message',{}).get('items',[]),error=response.get('error'))
def main():
 config=json.loads((ROOT/'data/review_expansion_queries.json').read_text(encoding='utf-8'))
 with concurrent.futures.ThreadPoolExecutor(max_workers=2)as pool:searches=list(pool.map(job,config['queries']))
 output=dict(date=config['date'],protocol='32 supplementary topic queries, relevance top 15, Crossref until-pub-date 2026-10-16; candidates only, manual screening required.',searches=searches)
 (ROOT/'data/review_candidates_expanded.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print('TOTAL',sum(len(s['items'])for s in searches),'ERRORS',sum(bool(s['error'])for s in searches),flush=True)
if __name__=='__main__':main()

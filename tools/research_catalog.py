"""Reproducible research candidate collection. Registry matches are not content review."""
import argparse, concurrent.futures, hashlib, html, json, re, time, urllib.parse, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/"docs"/"research-records"/"2026-10-16"
RAW.mkdir(parents=True,exist_ok=True)
QUERIES=[
"microgrid optimization meta heuristic review",
"unit commitment genetic algorithm review",
"distribution network reconfiguration genetic algorithm",
"optimal phasor measurement unit placement genetic algorithm",
"hybrid renewable energy system sizing genetic algorithm review",
"demand side management load scheduling genetic algorithm review",
"wind farm layout optimization genetic algorithm review",
"photovoltaic model parameter extraction metaheuristic survey",
"hybrid electric vehicle energy management genetic algorithm review",
"electric vehicle charging station location optimization genetic algorithm",
"building energy retrofit optimization genetic algorithm",
"irrigation planning genetic algorithm water resources",
"precision agriculture optimization genetic algorithm",
"cropping pattern optimization systematic review",
"water distribution systems genetic algorithms review",
"reservoir operation multiobjective evolutionary algorithm",
"wildfire management optimization genetic algorithm",
"stormwater low impact development SWMM genetic algorithm optimization",
"traffic signal control evolutionary swarm optimization",
"transit network design scheduling genetic algorithm review",
"berth quay crane scheduling genetic algorithm review",
"supply chain network design metaheuristic review",
"warehouse storage assignment genetic algorithm",
"elevator group control genetic algorithm",
"unmanned aerial vehicle path planning metaheuristic review",
"truss structural optimization genetic algorithm",
"slope stability critical slip surface genetic algorithm",
"structural damage identification genetic algorithm review",
"architectural layout design evolutionary optimization",
"facility layout planning quadratic assignment metaheuristic",
"machining cutting parameter optimization genetic algorithm review",
"additive manufacturing metaheuristic optimization review",
"welding casting process parameter optimization genetic algorithm",
"chemical batch process scheduling genetic algorithm",
"simple assembly line balancing genetic algorithm review",
"materials inverse design evolutionary algorithm",
"evolutionary crystal structure prediction USPEX",
"food formulation optimization genetic algorithm",
"fashion design interactive genetic algorithm",
"molecular design evolutionary algorithm genetic algorithm",
"protein structure prediction evolutionary algorithm review",
"AutoDock automated docking Lamarckian genetic algorithm empirical binding free energy",
"multiple sequence alignment evolutionary algorithm review",
"genome wide association study feature selection genetic algorithm",
"operating room planning scheduling metaheuristics systematic review",
"radiotherapy beam angle optimization genetic algorithm",
"maximal expected covering location problem Daskin",
"nurse rostering solution methodologies survey",
"evolutionary feature selection classification survey",
"multilevel threshold image segmentation metaheuristic review",
"evolutionary clustering survey",
"wireless sensor network deployment genetic algorithm coverage review",
"evolutionary neural architecture search survey",
"evolution guided policy gradient reinforcement learning",
"cloud task scheduling metaheuristic survey",
"task offloading cloud fog edge metaheuristic survey",
"underwater acoustic sensor network routing metaheuristic",
"Evolving virtual creatures Sims",
"swarm robotics engineering review",
"search based software testing survey",
"digital image watermarking evolutionary optimization review",
"satellite scheduling problems survey earth outer space observation",
"interplanetary trajectory optimization differential evolution",
"astronomical observation scheduling metaheuristic",
"weapon target assignment model algorithm survey",
"OFDM radar pulses genetic algorithm design",
"NASA ST5 evolved antenna",
"nuclear fuel loading pattern genetic algorithm review",
"tokamak poloidal field coils genetic algorithm",
"geophysical inversion particle swarm optimization review",
"groundwater contamination source identification genetic algorithm",
"tidal current farm layout optimization genetic algorithm",
"wastewater treatment plant operation optimization review",
"swarm intelligence emergency evacuation planning review",
"meta heuristics portfolio optimization review",
"genetic programming financial trading rules review",
"option pricing model calibration differential evolution",
"credit scoring genetic algorithm feature selection review",
"political districting optimization genetic algorithm",
"oil reservoir well placement genetic algorithm review",
"metaheuristic cryptographic Boolean function design survey",
"moving target defense game theory survey",
"evolutionary game theory replicator dynamics",
"evolutionary art interactive genetic programming",
"evolutionary music computation art creating music",
"search based procedural content generation taxonomy survey",
"evolving neural networks augmenting topologies NEAT",
"automated test assembly genetic algorithm",
"meta heuristic university course timetabling survey",
"sports scheduling metaheuristics survey",
"wall painting reconstruction genetic algorithm",
"court case scheduling optimization genetic algorithm",
"hyper heuristics survey taxonomy",
"ParamILS automatic algorithm configuration framework",
"tutorial formulating using QUBO models",
"speech recognition evolutionary optimization genetic algorithm",
]
def get(url):
 for attempt in range(3):
  try:
   req=urllib.request.Request(url,headers={"User-Agent":"swarm-encyclopedia-research/0.2"})
   with urllib.request.urlopen(req,timeout=25) as response:return json.load(response)
  except Exception as e:
   if attempt==2:return {"error":str(e),"url":url}
   time.sleep(1+attempt)
def run_job(job):
 ident,url=job
 path=RAW/(ident+".json")
 if path.exists():
  result=json.loads(path.read_text(encoding="utf-8"))
 else:
  result={"retrieved":"2026-10-16","url":url,"response":get(url)}
  path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 return ident,result
def short(item):
 return {k:item[k] for k in ["DOI","title","container-title","author","published","published-online","published-print","issued","type","abstract","URL"] if k in item}
def main():
 apps=json.loads((ROOT/"data/apps.json").read_text(encoding="utf-8"))["entries"]
 refs=json.loads((ROOT/"data/research_map.json").read_text(encoding="utf-8"))["references"]
 assert len(apps)==len(QUERIES)==96
 jobs=[]
 for i,q in enumerate(QUERIES):
  params={"query.bibliographic":q,"rows":3,"filter":"until-pub-date:2026-10-16"}
  jobs.append(("app-%02d"%i,"https://api.crossref.org/works?"+urllib.parse.urlencode(params)))
 broad=["energy power systems","agriculture water resources","transport logistics","civil construction","manufacturing","biomedicine healthcare","information computing","aerospace satellite","earth environment","finance portfolio","security game theory","education art creativity","algorithm configuration design"]
 for i,q in enumerate(broad):
  params={"query.bibliographic":"metaheuristic "+q,"rows":50,"filter":"until-pub-date:2026-10-16"}
  jobs.append(("field-%02d"%i,"https://api.crossref.org/works?"+urllib.parse.urlencode(params)))
 for r in refs:
  if "doi.org/" in r["url"]:
   doi=r["url"].split("doi.org/",1)[1]
   jobs.append(("doi-"+r["id"],"https://api.crossref.org/works/"+urllib.parse.quote(doi,safe="/()")))
 completed={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for ident,result in pool.map(run_job,jobs):
   completed[ident]=result
   if len(completed)%15==0:print("Retrieved",len(completed),"/",len(jobs),flush=True)
 entries=[]
 for i,a in enumerate(apps):
  raw=completed["app-%02d"%i]
  response=raw["response"]
  candidates=response.get("message",{}).get("items",[])
  entries.append({"index":i,"title":a["title"],"industry":a["industry"],"query":QUERIES[i],"queryUrl":raw["url"],"candidates":[short(x) for x in candidates],"error":response.get("error")})
 unique={}
 broad_counts=[]
 for i,q in enumerate(broad):
  items=completed["field-%02d"%i]["response"].get("message",{}).get("items",[])
  broad_counts.append({"field":q,"returned":len(items),"queryUrl":completed["field-%02d"%i]["url"]})
  for item in items:
   if item.get("DOI"):unique.setdefault(item["DOI"].lower(),short(item))
 bibliography=[]
 for r in refs:
  item=completed.get("doi-"+r["id"],{}).get("response",{}).get("message")
  bibliography.append({"id":r["id"],"url":r["url"],"citedTitle":r["title"],"citedYear":r["year"],"record":short(item) if isinstance(item,dict) else None,"status":"registry-record" if isinstance(item,dict) else "non-doi-or-fetch-error"})
 payload={"retrieved":"2026-10-16","protocol":{"registry":"Crossref REST","appQueries":96,"industryQueries":13,"industryLimit":50,"appCandidateLimit":3,"cutoff":"2026-10-16","selection":"relevance order; candidates only; not global exhaustive retrieval","purpose":"reproducible evidence discovery and bibliography matching, not full-text peer review","rawFolder":str(RAW.relative_to(ROOT)).replace(chr(92),"/")},"applications":entries,"fields":broad_counts,"broadCandidates":list(unique.values()),"bibliography":bibliography,"errors":[{"id":k,"error":v["response"].get("error")} for k,v in completed.items() if v["response"].get("error")]}
 (ROOT/"data/research_catalog_candidates.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 print("COMPLETE",len(entries),"application searches",len(unique),"unique broad candidates",len(bibliography),"bibliography checks","errors",len(payload["errors"]),flush=True)
if __name__=="__main__":main()


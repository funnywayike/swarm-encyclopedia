import json,urllib.request,urllib.parse,concurrent.futures,time,hashlib
from pathlib import Path
P=Path
root=P('.');raw=root/'docs/research-records/2026-10-16'
a=json.loads(P('data/research_catalog_candidates.json').read_text(encoding='utf-8'))
sel=json.loads(P('data/research_application_selection.json').read_text(encoding='utf-8'))
origins="""pso|10.1109/icnn.1995.488968
aco|10.1109/3477.484436
abc|10.1007/s10898-007-9149-x
fa|10.1007/978-3-642-04944-6_14
ga|https://mitpress.mit.edu/9780262082136/adaptation-in-natural-and-artificial-systems/
woa|10.1016/j.advengsoft.2016.01.008
sa|10.1126/science.220.4598.671
gwo|10.1016/j.advengsoft.2013.12.007
ts|10.1016/0305-0548(86)90048-1
de|10.1023/a:1008202821328
cs|10.1109/nabic.2009.5393690
sca|10.1016/j.knosys.2015.12.022
hho|10.1016/j.future.2019.02.028
ils|10.1007/0-306-48056-5_11
vns|10.1016/s0305-0548(97)00031-2
lk|10.1287/opre.21.2.498
ba|10.1007/978-3-642-12538-6_6
hs|10.1177/003754970107600201
gsa|10.1016/j.ins.2009.03.004
tlbo|10.1016/j.cad.2010.12.015
bfo|10.1109/mcs.2002.1004010
mfo|10.1016/j.knosys.2015.07.006
fwa|10.1007/978-3-642-13495-1_44
afsa|10.12011/1000-6788(2002)11-32
cem|10.1016/s0377-2217(96)00385-2
cma-es|10.1162/106365601750190398
ssa|10.1080/21642583.2019.1708830
alo|10.1016/j.advengsoft.2015.01.010
boa|10.1007/s00500-018-3102-4
ica|10.1109/cec.2007.4425083
salp|10.1016/j.advengsoft.2017.07.002
sfla|10.1061/(asce)0733-9496(2003)129:3(210)
fpa|10.1007/978-3-642-32894-7_27
kh|10.1016/j.cnsns.2012.05.010
sos|10.1016/j.compstruc.2014.03.007
jaya|10.5267/j.ijiec.2015.8.004
da|10.1007/s00521-015-1920-1
mpa|10.1016/j.eswa.2020.113377
cscrow|10.1016/j.compstruc.2016.03.001
bbo|10.1109/tevc.2008.919004
grasp|10.1016/0167-6377(89)90002-3
ais|10.1109/tevc.2002.1011539
eo|10.1016/j.knosys.2019.105190
ao|10.1016/j.cie.2021.107250
sma|10.1016/j.future.2020.03.055"""
orig=dict(x.split('|',1)for x in origins.splitlines())
P('data/research_algorithm_origins.json').write_text(json.dumps(orig,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
extra="""10.1007/3-540-61723-X_982
10.1016/S0065-2458(08)60520-3
10.1007/3-540-49481-2_30
10.1016/S0045-7825(99)00389-8
10.1007/s00500-003-0328-5
10.1109/TEVC.2005.846356
10.1109/TEVC.2007.892759
10.1109/TEVC.2015.2458037
10.3389/frobt.2016.00040
10.1103/PhysRevB.82.094116
10.1016/j.cpc.2012.05.008
10.1016/j.cpc.2006.07.020
10.1162/106365602320169811
10.1162/EVCO_a_00001
10.1007/s12095-023-00662-2
10.6054/j.jscnun.2023001""".splitlines()
records={}
for p in raw.glob('*.json'):
 try:
  d=json.loads(p.read_text(encoding='utf-8'));r=d.get('response',{})
  msg=r.get('message',{})
  xs=msg.get('items',[msg]if msg.get('DOI')else[])
  for x in xs:
   if x.get('DOI'):records[x['DOI'].lower()]=x
 except Exception:pass
for x in a['bibliography']:
 if (x.get('record') or {}).get('DOI'):records[x['record']['DOI'].lower()]=x['record']
dois=set(extra+[v for v in orig.values()if v.startswith('10.')])
for e in sel['entries']:
 s=e['selector']
 if isinstance(s,int):dois.add(a['applications'][e['index']]['candidates'][s]['DOI'])
 elif s.startswith('10.'):dois.add(s)
def get(doi):
 k=doi.lower()
 if k in records:return k,records[k]
 u='https://api.crossref.org/works/'+urllib.parse.quote(doi,safe='')
 for j in range(2):
  try:
   with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'SwarmEncyclopediaResearch/0.1'}),timeout=20)as f:r=json.load(f)
   (raw/('exact-'+hashlib.sha256(k.encode()).hexdigest()[:16]+'.json')).write_text(json.dumps({'doi':doi,'url':u,'retrieved':'2026-10-16','response':r},ensure_ascii=False,indent=2),encoding='utf-8')
   return k,r['message']
  except Exception as e:
   if j==1:return k,{'DOI':doi,'error':str(e)}
   time.sleep(1)
with concurrent.futures.ThreadPoolExecutor(max_workers=4)as pool:
 for k,r in pool.map(get,sorted(dois)):records[k]=r
P('data/research_metadata.json').write_text(json.dumps({'retrieved':'2026-10-16','records':{k:records[k]for k in sorted(set(d.lower()for d in dois))}},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('metadata records',len(dois),'errors',[(k,r.get('error'))for k,r in records.items()if r.get('error')])
for i in [0,6,7,11,12,25,26,28,31,35,37,38,39,43,45,50,51,59,61,62,65,67,69,75,79,83,85,87,89,90,91,94,95]:
 e=sel['entries'][i];s=e['selector'];doi=a['applications'][i]['candidates'][s]['DOI']if isinstance(s,int)else s
 r=records.get(doi.lower(),{});print(i,doi,r.get('title'),str(r.get('abstract',''))[:400])


"""Readable, source-backed research routes for the public map."""
import html,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def esc(v):return html.escape(str(v),quote=True)
def render_routes_panel():
 d=json.loads((ROOT/'data/research_routes.json').read_text(encoding='utf-8'))
 refs=d['sources'];cards=[]
 levels={'metadata':'书目核对','abstract':'已核读摘要','sections':'已核读摘要及部分章节'}
 for r in d['routes']:
  stages=[]
  for s in r['stages']:
   sources=[]
   for rid in s['refs']:
    a=refs[rid];level=a.get('readingLevel','metadata')
    authors=a.get('authors',[])
    if not authors:authors=[' '.join([x.get('given',''),x.get('family',x.get('name',''))]).strip() for x in a.get('metadata',{}).get('author',[])]
    author_text='；'.join(authors)
    location=esc(a.get('readingLocation','原始书目记录；本轮未据此声称全文核读'))
    if a.get('readingURL'):location='<a target="_blank" rel="noopener noreferrer" href="'+esc(a['readingURL'])+'">'+location+'</a>'
    sources.append('<li><a href="'+esc(a['url'])+'" target="_blank" rel="noopener noreferrer">'+esc(a['title'])+'</a><span class="rr-source-level">'+esc(a.get('year',''))+' · '+levels[level]+'</span><p>'+esc(author_text)+'</p><p>'+location+'</p></li>')
   stages.append('<section class="rr-stage" data-stage="'+s['id']+'"><p class="rr-period">'+esc(s['period'])+'</p><h4>'+esc(s['title'])+'</h4><p>'+esc(s['body'])+'</p><details class="rr-sources"><summary>查看依据 · '+str(len(s['refs']))+' 项</summary><ul>'+''.join(sources)+'</ul></details></section>')
  related=''.join('<button type="button" data-route-target="'+x+'">'+esc(next(z['name'] for z in d['routes'] if z['id']==x))+'</button>' for x in r['related'])
  q=' '.join([r['name'],r['group'],r['question'],r['takeaway']]+[s['title']+' '+s['body'] for s in r['stages']]).lower()
  cards.append('<article class="rr-card" id="route-'+r['id']+'" data-route="'+r['id']+'" data-group="'+esc(r['group'])+'" data-query="'+esc(q)+'"><p class="rr-group">'+esc(r['group'])+'<span>'+esc(r['stages'][2]['period'])+'</span></p><h3>'+esc(r['name'])+'</h3><p class="rr-question">'+esc(r['question'])+'</p><p>'+esc(r['takeaway'])+'</p><details class="rr-journey"><summary>展开发展脉络与证据</summary><div class="rr-stages">'+''.join(stages)+'</div><p class="rr-cross"><b>怎样交叉阅读：</b>'+esc(r['crossReading'])+'</p><div class="rr-related"><span>继续探索</span>'+related+'</div></details><a class="rr-anchor" href="#route-'+r['id']+'">本路线链接 ↗</a></article>')
 groups=''.join('<option>'+esc(x)+'</option>' for x in dict.fromkeys(r['group'] for r in d['routes']))
 return '<link rel="stylesheet" href="../../css/research_routes.css"><section class="rm-panel" id="rm-view-routes" role="tabpanel"><div class="rr-lead"><p class="rr-eyebrow">20条研究路线 · 从经典机制走向当代问题</p><h2>方法一直在发展，关键是看清它改了什么。</h2><p>从一条问题开始，沿着四个节点阅读：起源、关键转折、近年进展、研究边界。综述与具体实验分开标注，点击依据可以追到原始出版记录。</p><p class="hint">'+esc(d['scope'])+' 更新于 '+esc(d['updated'])+'。</p></div><div class="rr-controls"><label>研究方向 <select id="rr-group"><option value="">全部方向</option>'+groups+'</select></label><label>查找路线 <input id="rr-search" type="search" placeholder="算法、机制或研究问题"></label><label>阅读重点 <select id="rr-focus"><option value="all">完整发展脉络</option><option value="recent">近年进展与边界</option></select></label><button type="button" id="rr-expand">全部展开</button><button type="button" id="rr-collapse">全部收起</button><button type="button" id="rr-reset">重置</button></div><p id="rr-status" role="status" aria-live="polite">20 / 20 条路线</p><div class="rr-grid">'+''.join(cards)+'</div><p id="rr-empty" hidden>没有匹配的路线。试试更短的关键词，或重置筛选。</p><div class="rr-foot"><h3>按问题继续深入</h3><p>如果你关心约束、多目标、昂贵评价、动态环境或实际应用，可切换上方“研究难点与中文阅读”“应用问题”和“13个领域的研究证据”。“历史与交汇”提供跨路线的时间视角，“综述与交叉验证”提供独立的资料检索入口。</p></div></section><script src="../../js/research_routes.js"></script>'

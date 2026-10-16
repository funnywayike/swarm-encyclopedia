"""Source-backed turning point dossiers shared by the timeline and map."""
import html,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def esc(v):return html.escape(str(v),quote=True)
def milestone_data():
 d=json.loads((ROOT/'data/research_milestones.json').read_text(encoding='utf-8'))
 m=json.loads((ROOT/'data/research_map.json').read_text(encoding='utf-8'))
 refs={r['id']:r for r in m['references']};nodes={n['id']:n for n in m['nodes']}
 names={r['id']:r['name'] for r in json.loads((ROOT/'data/research_reading_views.json').read_text(encoding='utf-8'))['methods']}
 out=[]
 for p in d['profiles']:
  n=nodes[p['node']]
  primary=refs[n['refs'][0]]
  authors=p.get('creditOverride') or primary.get('authors') or [' '.join([a.get('given',''),a.get('family',a.get('name',''))]).strip() for a in primary.get('metadata',{}).get('author',[])]
  out.append(dict(p,title=n['title'],year=n['year'],refs=n['refs'],authors=authors,routeLinks=[dict(id=x,name=names[x]) for x in p['routes']]))
 return dict(d,profiles=out)
def render_milestones_panel():
 d=milestone_data()
 m=json.loads((ROOT/'data/research_map.json').read_text(encoding='utf-8'));refs={r['id']:r for r in m['references']}
 cards=[]
 for p in d['profiles']:
  cites=''.join('<li><a target="_blank" rel="noopener noreferrer" href="'+esc(refs[k]['url'])+'">'+esc(refs[k]['title'])+'</a> · '+esc(refs[k].get('kind','研究来源'))+'</li>' for k in p['refs'])
  routes=''.join('<a href="#route-'+esc(x['id'])+'">'+esc(x['name'])+' 研究路线 →</a>' for x in p['routeLinks'])
  extra='<p><a href="https://cma-es.github.io/" target="_blank" rel="noopener noreferrer">核对作者维护的1996/2001注释书目 ↗</a></p>' if p['node']=='cma01' else ''
  cards.append('<details class="md-card" id="milestone-'+p['node']+'"><summary><span class="md-badge" data-layer="'+p['layer']+'">'+esc(p['label'])+'</span><span class="md-year">'+str(p['year'])+'</span><b>'+esc(p['title'])+'</b><span class="md-summary">'+esc(p['theme'])+'</span></summary><div class="md-body"><div class="md-change"><section><h4>当时的研究问题</h4><p>'+esc(p['problem'])+'</p></section><section><h4>机制或工作方式的变化</h4><p>'+esc(p['change'])+'</p></section><section><h4>打开的后续问题</h4><p>'+esc(p['consequence'])+'</p></section></div><p class="md-date"><b>这个年份表示什么：</b>'+esc(p['dateMeaning'])+'</p><p><b>为何进入这张地图：</b>'+esc(p['selectionReason'])+'</p><p class="hint"><b>代表资料作者：</b>'+esc('、'.join(p['authors']) or '见原始出版记录中的作者名单')+'。作者归属按所引资料记录，不据此指定某机构为唯一研究中心。</p><details><summary>核查原始来源</summary><ul>'+cites+'</ul>'+extra+'</details><div class="md-links"><a href="../../meta/timeline/index.html#year-'+str(p['year'])+'">打开该年的研究枝条 →</a>'+routes+'</div></div></details>')
 criteria=''.join('<li>'+esc(c)+'</li>' for c in d['criteria'])
 return '<link rel="stylesheet" href="../../css/research_milestones.css"><section class="rm-panel" id="rm-view-milestones" role="tabpanel" hidden><div class="md-intro"><span class="md-eyebrow">TURNING POINTS / 研究档案</span><h2>重要的不是多一个名字，而是研究怎样改变。</h2><p>16个代表性转折分别回答：问题是什么、改变了什么、为什么值得读、日期怎样解释。经典机制、公共设施、领域工具与前沿探索各有位置。</p><details><summary>主干怎样选取</summary><ol>'+criteria+'</ol><p class="hint">这是公开的编辑判据，尚未经过外部专家评审；不以收录数、引用量或最新年份自动决定经典地位。</p></details></div><div class="md-archive">'+''.join(cards)+'</div><p class="hint">档案更新：'+esc(d['updated'])+'。来源支持具体贡献；相邻时间不表示直接继承，综述年份不表示领域诞生。</p></section>'

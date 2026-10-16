"""Source-led science articles and a chronological / event narrative vine."""
import html,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def esc(x):return html.escape(str(x),quote=True)
def _load(name):return json.loads((ROOT/'data'/name).read_text(encoding='utf-8'))
def _vine():
    d=_load('research_map.json');c=_load('science_timeline.json')
    from pages_milestones import milestone_data
    c['milestones']=milestone_data()
    ids={i for n in d['nodes']for i in n.get('refs',[])}
    payload={'nodes':d['nodes'],'lanes':d['lanes'],'config':c,'references':[{k:r[k]for k in ('id','title','year','kind','url')if k in r}for r in d['references']if r['id']in ids]}
    data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
    return '''
    <link rel="stylesheet" href="../../css/research_milestones.css">
    <section class="science-vine" aria-labelledby="vine-heading">
      <div class="science-vine-heading"><div><span class="science-eyebrow">THE RESEARCH VINE</span><h2 id="vine-heading">研究如何生长</h2></div><p>主干看转折，年内看旁支，事件线看研究问题。</p></div>
      <div class="science-vine-controls">
        <div class="science-toggle" role="group" aria-label="选择叙事方式"><button type="button" data-vine-view="time" aria-pressed="true">按时间读</button><button type="button" data-vine-view="event" aria-pressed="false">按事件读</button></div>
        <label>打开年份 <select id="vine-year"></select></label>
      </div>
      <div class="science-evidence-legend"><b>先看贡献类型，再看年代。</b>机制、设施、领域工具、综合回顾与前沿观察各有作用。虚线表示前沿，不表示已成为经典。类型筛选作用于当前主干或事件线；年内旁支继续展开。点击事件可核查问题、改变、日期与代表作者。</div>
      <div id="vine-layers" class="science-filter science-layer-controls" role="group" aria-label="筛选贡献类型"></div>
      <div id="vine-lanes" class="science-filter" role="group" aria-label="筛选研究主线"></div>
      <div class="science-story-select" id="vine-story-wrap" hidden><label>选择事件叙事 <select id="vine-story"></select></label><p id="vine-story-intro"></p></div>
      <p class="science-vine-status" id="vine-status" aria-live="polite"></p>
      <div class="science-vine-layout">
        <div id="vine-canopy"></div>
        <aside class="science-year-panel" id="vine-year-panel" aria-labelledby="vine-year-title"></aside>
      </div>
      <p class="science-scope">主干与旁支是编辑整理的阅读层次，不是客观影响力排名。同年出现不代表继承关系；未收录不等于没有重要研究。</p>
    </section>
    <script type="application/json" id="science-vine-data">'''+data+'''</script>
    <script src="../../js/science_vine.js"></script>'''
def render_science(p,chips,en_summary):
    refs=p['refs'];byid={x['id']:x for x in refs};index={x['id']:i+1 for i,x in enumerate(refs)}
    def sup(ids):
        return '<sup class="refsup">'+''.join('<a href="#ref-'+esc(id)+'">['+str(index[id])+']</a>'for id in ids)+'</sup>'if ids else ''
    def feature(id):
        r=byid[id]
        return '<a class="science-reading-card" href="'+esc(r['url'])+'" target="_blank" rel="noopener"><span>'+esc(r.get('venue','原始资料'))+' · '+esc(r.get('year',''))+'</span><b>'+esc(r['cite'])+'</b><span>打开研究来源 ↗</span></a>'
    featured=''.join(feature(id)for id in p.get('featured',[]))
    toc=''.join('<a href="#chapter-'+str(i)+'"><span>'+str(i).zfill(2)+'</span>'+esc(s['h2'])+'</a>'for i,s in enumerate(p['sections'],1))
    chapters=''.join('<section class="science-chapter" id="chapter-'+str(i)+'"><div class="science-chapter-heading"><span class="science-section-number">'+str(i).zfill(2)+'</span><h2>'+s['h2']+sup(s.get('refs',[]))+'</h2></div><p class="science-takeaway">'+esc(s.get('takeaway',''))+'</p><div class="science-section-body">'+s['html']+'</div></section>'for i,s in enumerate(p['sections'],1))
    reference_list=''.join('<li id="ref-'+esc(r['id'])+'"><span class="science-ref-number">'+str(index[r['id']]).zfill(2)+'</span><div><a href="'+esc(r['url'])+'" target="_blank" rel="noopener">'+esc(r['cite'])+'</a><p>'+esc(r.get('kind','研究来源'))+((' · '+esc(r['note']))if r.get('note')else '')+'</p></div></li>'for r in refs)
    points=''.join('<li>'+esc(x)+'</li>'for x in p.get('points',[]))
    vine=_vine()if p['id']=='timeline'else ''
    return f'''
    <link rel="stylesheet" href="../../css/science.css">
    <article class="science-page" id="science-article">
      <div class="crumbs"><a href="/">首页</a> · <a href="/encyclopedia/">科普</a> · {esc(p["name"])}</div>
      <header class="science-hero">
        <div><span class="science-eyebrow">RESEARCH EXPLAINED / {esc(p.get("kicker","研究解读"))}</span>
          <h1>{esc(p["name"])}</h1><p class="science-english">{esc(p["en"])}</p><p class="science-lead">{esc(p["lead"])}</p>
          <ul class="science-objectives">{points}</ul>
        </div>
        <div class="science-reading"><h2>从这些研究读起</h2>{featured}</div>
      </header>
      <nav class="science-navigation" aria-label="科普专题">{chips(cur=p["id"])}</nav>
      {en_summary(p.get("summary_en"))}
      {vine}
      <div class="science-reading-toolbar"><div><span class="science-eyebrow">DEEP READING</span><h2>把重要的问题讲清楚</h2></div><div class="science-toggle" role="group" aria-label="正文阅读深度"><button type="button" data-science-depth="deep" aria-pressed="true">深入阅读</button><button type="button" data-science-depth="brief" aria-pressed="false">核心结论</button></div></div>
      <div class="science-article-layout"><aside class="science-toc"><b>本篇导航</b>{toc}<a href="#science-references">佐证与出处</a></aside><div>{chapters}</div></div>
      <section class="science-references" id="science-references"><span class="science-eyebrow">EVIDENCE & SOURCES</span><h2>佐证与出处</h2><p>正文编号对应下列资料。原始方法、综述、项目发布与方法学讨论分别标注；引用支持具体论述，不构成对整个领域的排名。</p><ol>{reference_list}</ol></section>
      <div class="science-next"><h2>沿着问题继续探索</h2><p>查看研究团队、算法与问题的对应关系，或选择自己的阅读重点。</p><a href="/meta/research-map/">打开研究主干地图 →</a><a href="/applications/">探索应用问题 →</a></div>
    </article>
    <script src="../../js/science_article.js"></script>
    '''

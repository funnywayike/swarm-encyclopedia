/* One evidence set, two narratives. A branch is an editorial reading layer, never an impact score. */
(function(root){
'use strict';
const years=D=>[...new Set(D.nodes.map(n=>n.year))].sort((a,b)=>a-b);
const yearNodes=(D,year,lane='all')=>D.nodes.filter(n=>n.year===year&&(lane==='all'||n.lane===lane));
function narrativeNodes(D,mode,story,lane='all'){
 const ids=mode==='event'?(D.config.stories.find(x=>x.id===story)?.nodes||[]):D.config.trunk;
 return D.nodes.filter(n=>ids.includes(n.id)&&(lane==='all'||n.lane===lane));
}
const api={years,yearNodes,narrativeNodes};
if(typeof module==='object'&&module.exports)module.exports=api;
if(typeof document==='undefined')return;
const dataElement=document.getElementById('science-vine-data');if(!dataElement)return;
const D=JSON.parse(dataElement.textContent),N=new Map(D.nodes.map(n=>[n.id,n])),R=new Map(D.references.map(r=>[r.id,r])),L=new Map(D.lanes.map(l=>[l.id,l]));
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const href=u=>u.startsWith('/')?'../../'+u.replace(/^\/+/,'')+(u.endsWith('/')?'index.html':''):u;
let mode='time',story=D.config.stories[0].id,lane='all',year=1995,selected='pso95';
const hash=location.hash.match(/^#year-(\d{4})$/);if(hash&&years(D).includes(+hash[1])){year=+hash[1];selected=yearNodes(D,year)[0].id;}
const yearSelect=document.getElementById('vine-year');
yearSelect.innerHTML=years(D).map(y=>'<option value="'+y+'">'+y+' 年 · '+yearNodes(D,y).length+' 个已收录事件</option>').join('');
document.getElementById('vine-story').innerHTML=D.config.stories.map(s=>'<option value="'+esc(s.id)+'">'+esc(s.title)+'</option>').join('');
document.getElementById('vine-lanes').innerHTML='<button type="button" data-vine-lane="all" aria-pressed="true">全部研究线</button>'+D.lanes.map(l=>'<button type="button" data-vine-lane="'+esc(l.id)+'" aria-pressed="false">'+esc(l.name)+'</button>').join('');
function button(n){
 const count=yearNodes(D,n.year).length;
 return '<button class="science-event-button" type="button" data-vine-node="'+esc(n.id)+'" style="--event-color:'+esc(L.get(n.lane).color)+'" aria-pressed="'+(selected===n.id)+'"><span class="event-year">'+n.year+'</span><b>'+esc(n.title)+'</b><small>'+esc(L.get(n.lane).name)+' · 展开本年 '+count+' 项</small></button>';
}
function panel(){
 const ns=yearNodes(D,year,lane);
 if(ns.length&&!ns.some(n=>n.id===selected))selected=ns[0].id;
 const body=ns.map(n=>{
  const sources=(n.refs||[]).map(id=>R.get(id)).filter(Boolean).map(r=>'<a class="science-vine-source" href="'+esc(r.url)+'" target="_blank" rel="noopener">'+esc(r.title)+' ↗<br><span>'+esc(r.kind)+' · '+esc(r.year)+'</span></a>').join('');
  const links=(n.algorithmLinks||[]).map(a=>'<a href="'+esc(href(a.url))+'">'+esc(a.label)+' 演示</a>').join('');
  return '<details'+(selected===n.id?' open':'')+'><summary><span>'+(D.config.trunk.includes(n.id)?'主干事件':'同年旁支')+' · '+esc(L.get(n.lane).name)+'</span>'+esc(n.title)+'</summary><p>'+esc(n.summary)+'</p><p><b>贡献在哪里</b><br>'+esc(n.contribution)+'</p><p><b>怎样理解其范围</b><br>'+esc(n.boundary)+'</p>'+sources+(links?'<div class="science-year-links">'+links+'</div>':'')+'</details>';
 }).join('');
 document.getElementById('vine-year-panel').innerHTML='<span class="science-eyebrow">YEAR / '+year+'</span><h3 id="vine-year-title">'+year+' 年的研究枝条</h3><p>'+ns.length+' 个符合当前主线的已收录事件。这里展示的是筛选后的研究，不代表本年论文总量。</p>'+(body||'<div class="science-empty">当前主线在这一年没有已收录事件。可切换年份或选择全部研究线。</div>')+'<p>没有列出的工作可能尚未整理。<a href="../../meta/research-map/index.html">进入完整研究地图 →</a></p>';
}
function render(){
 const visible=narrativeNodes(D,mode,story,lane);
 yearSelect.value=String(year);
 document.getElementById('vine-story-wrap').hidden=mode!=='event';
 document.getElementById('vine-story').value=story;
 document.querySelectorAll('[data-vine-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.vineView===mode)));
 document.querySelectorAll('[data-vine-lane]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.vineLane===lane)));
 document.getElementById('vine-status').textContent=(mode==='time'?'当前主干 '+visible.length+' 个代表事件':'当前事件线 '+visible.length+' 个节点')+' · 完整资料含 '+D.nodes.length+' 个已筛选节点、'+years(D).length+' 个年份。点击事件打开该年的旁支。';
 panel();
 // panel() may update the selected node when the current lane changes.
 if(mode==='time'){
  document.getElementById('vine-canopy').innerHTML='<div class="science-canopy-time"><svg class="science-trunk" viewBox="0 0 42 1000" preserveAspectRatio="none" aria-hidden="true"><path d="M22 0 C7 140 37 180 22 300 S9 460 22 530 S37 720 22 810 S9 950 22 1000"/></svg>'+D.config.eras.map(e=>{
   const ns=visible.filter(n=>n.year>=e.from&&n.year<=e.to);
   if(!ns.length)return '';
   return '<section class="science-era"><div class="science-era-axis"><b>'+esc(e.label)+'</b><span>'+esc(e.period)+'</span></div><div class="science-era-body"><p class="science-era-question">'+esc(e.question)+'</p><div class="science-era-events">'+ns.map(button).join('')+'</div></div></section>';
  }).join('')+'</div>';
 }else{
  const s=D.config.stories.find(s=>s.id===story);
  document.getElementById('vine-story-intro').textContent=s.summary;
  document.getElementById('vine-canopy').innerHTML='<h3 class="science-story-heading">'+esc(s.question)+'</h3><ol class="science-story-steps">'+visible.map(n=>'<li>'+button(n)+'</li>').join('')+'</ol>';
 }
 if(!visible.length)document.getElementById('vine-canopy').innerHTML='<div class="science-empty">当前叙事中没有符合这一主线的节点。可选择全部研究线，或换一条事件叙事。</div>';
}
function openYear(y,id){
 year=y;selected=id||yearNodes(D,year,lane)[0]?.id||'';
 try{history.replaceState(null,'','#year-'+year);}catch(_){}
 render();
 if(matchMedia('(max-width:760px)').matches)document.getElementById('vine-year-panel').scrollIntoView({behavior:'smooth',block:'start'});
}
document.querySelector('.science-vine').addEventListener('click',e=>{
 const b=e.target.closest('button');if(!b)return;
 if(b.dataset.vineNode){const n=N.get(b.dataset.vineNode);openYear(n.year,n.id);}
 else if(b.dataset.vineView){mode=b.dataset.vineView;render();}
 else if(b.dataset.vineLane){lane=b.dataset.vineLane;render();}
});
yearSelect.addEventListener('change',()=>openYear(+yearSelect.value));
document.getElementById('vine-story').addEventListener('change',e=>{story=e.target.value;render();});
render();
})(typeof globalThis!=='undefined'?globalThis:this);

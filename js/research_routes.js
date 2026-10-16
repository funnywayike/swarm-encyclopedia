(function(root){
'use strict';
function matches(card,group,query){return (!group||card.group===group)&&card.query.includes((query||'').trim().toLowerCase());}
function target(hash){const m=/^#route-([a-z0-9-]+)$/.exec(hash||'');return m?m[1]:null;}
function mount(doc,win){
const panel=doc.getElementById('rm-view-routes');if(!panel)return;
const cards=Array.from(panel.querySelectorAll('.rr-card')),group=doc.getElementById('rr-group'),search=doc.getElementById('rr-search'),focus=doc.getElementById('rr-focus');
const grid=doc.getElementById('rr-grid'),nav=doc.getElementById('rr-route-nav');
if(grid)grid.classList.add('rr-focused');
const layout=doc.getElementById('rr-layout');if(layout&&grid)layout.addEventListener('click',()=>{const focused=grid.classList.toggle('rr-focused');layout.setAttribute('aria-pressed',String(!focused));layout.textContent=focused?'浏览全部路线':'返回专注阅读';});
function choose(card){cards.forEach(c=>c.dataset.current=String(c===card));if(card)card.querySelector('.rr-journey').open=true;if(nav)nav.querySelectorAll('[data-reader-route]').forEach(b=>{const c=cards.find(c=>c.dataset.route===b.dataset.readerRoute);b.hidden=!!c?.hidden;b.setAttribute('aria-pressed',String(c===card));});}
function update(){let count=0;cards.forEach(c=>{c.hidden=!matches({group:c.dataset.group,query:c.dataset.query},group.value,search.value);if(!c.hidden)count++;c.querySelectorAll('.rr-stage').forEach(s=>s.hidden=focus.value==='recent'&&!['recent','limits'].includes(s.dataset.stage));});if(grid)choose(cards.find(c=>!c.hidden&&c.dataset.current==='true')||cards.find(c=>!c.hidden));doc.getElementById('rr-status').textContent=count+' / '+cards.length+' 条路线';doc.getElementById('rr-empty').hidden=count!==0;}
function openHash(){const id=target(win.location.hash),card=cards.find(c=>c.dataset.route===id);if(!card)return;group.value='';search.value='';choose(card);update();doc.querySelector('.rm-tab[data-view="routes"]').click();card.querySelector('.rr-journey').open=true;win.requestAnimationFrame(()=>card.scrollIntoView({block:'start',behavior:'auto'}));}
group.addEventListener('change',update);search.addEventListener('input',update);focus.addEventListener('change',()=>{update();if(focus.value==='recent')cards.filter(c=>!c.hidden).forEach(c=>c.querySelector('.rr-journey').open=true);});
doc.getElementById('rr-expand').addEventListener('click',()=>cards.filter(c=>!c.hidden).forEach(c=>c.querySelector('.rr-journey').open=true));
doc.getElementById('rr-collapse').addEventListener('click',()=>cards.forEach(c=>c.querySelector('.rr-journey').open=false));
doc.getElementById('rr-reset').addEventListener('click',()=>{group.value='';search.value='';focus.value='all';update();});
panel.querySelectorAll('[data-route-target]').forEach(b=>b.addEventListener('click',()=>{const hash='#route-'+b.dataset.routeTarget;if(win.location.hash===hash)openHash();else win.location.hash=hash;}));
if(nav)nav.querySelectorAll('[data-reader-route]').forEach(b=>b.addEventListener('click',()=>{const card=cards.find(c=>c.dataset.route===b.dataset.readerRoute);choose(card);if(card)win.requestAnimationFrame(()=>card.scrollIntoView({block:'start',behavior:'auto'}));}));
win.addEventListener('hashchange',openHash);update();
// Parent map installs its tab listener after this deferred DOM-ready callback.
win.setTimeout(openHash,0);
}
if(typeof module!=='undefined'&&module.exports)module.exports={matches,target,mount};
if(root.document){if(root.document.readyState==='loading')root.document.addEventListener('DOMContentLoaded',()=>mount(root.document,root));else mount(root.document,root);}
})(typeof window!=='undefined'?window:globalThis);

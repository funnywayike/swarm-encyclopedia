(function(root){
'use strict';
function matches(card,group,query){return (!group||card.group===group)&&card.query.includes((query||'').trim().toLowerCase());}
function target(hash){const m=/^#route-([a-z0-9-]+)$/.exec(hash||'');return m?m[1]:null;}
function mount(doc,win){
const panel=doc.getElementById('rm-view-routes');if(!panel)return;
const cards=Array.from(panel.querySelectorAll('.rr-card')),group=doc.getElementById('rr-group'),search=doc.getElementById('rr-search'),focus=doc.getElementById('rr-focus');
function update(){let count=0;cards.forEach(c=>{c.hidden=!matches({group:c.dataset.group,query:c.dataset.query},group.value,search.value);if(!c.hidden)count++;c.querySelectorAll('.rr-stage').forEach(s=>s.hidden=focus.value==='recent'&&!['recent','limits'].includes(s.dataset.stage));});doc.getElementById('rr-status').textContent=count+' / '+cards.length+' 条路线';doc.getElementById('rr-empty').hidden=count!==0;}
function openHash(){const id=target(win.location.hash),card=cards.find(c=>c.dataset.route===id);if(!card)return;group.value='';search.value='';update();doc.querySelector('.rm-tab[data-view="routes"]').click();card.querySelector('.rr-journey').open=true;win.requestAnimationFrame(()=>card.scrollIntoView({block:'start',behavior:'auto'}));}
group.addEventListener('change',update);search.addEventListener('input',update);focus.addEventListener('change',()=>{update();if(focus.value==='recent')cards.filter(c=>!c.hidden).forEach(c=>c.querySelector('.rr-journey').open=true);});
doc.getElementById('rr-expand').addEventListener('click',()=>cards.filter(c=>!c.hidden).forEach(c=>c.querySelector('.rr-journey').open=true));
doc.getElementById('rr-collapse').addEventListener('click',()=>cards.forEach(c=>c.querySelector('.rr-journey').open=false));
doc.getElementById('rr-reset').addEventListener('click',()=>{group.value='';search.value='';focus.value='all';update();});
panel.querySelectorAll('[data-route-target]').forEach(b=>b.addEventListener('click',()=>{const hash='#route-'+b.dataset.routeTarget;if(win.location.hash===hash)openHash();else win.location.hash=hash;}));
win.addEventListener('hashchange',openHash);update();
// Parent map installs its tab listener after this deferred DOM-ready callback.
win.setTimeout(openHash,0);
}
if(typeof module!=='undefined'&&module.exports)module.exports={matches,target,mount};
if(root.document){if(root.document.readyState==='loading')root.document.addEventListener('DOMContentLoaded',()=>mount(root.document,root));else mount(root.document,root);}
})(typeof window!=='undefined'?window:globalThis);

const assert=require('node:assert/strict');
const {matches,target,mount}=require('../js/research_routes.js');
assert.ok(matches({group:'A',query:'pso 参数'},'A',' PSO '));
assert.ok(!matches({group:'A',query:'pso'},'B',''));
assert.ok(!matches({group:'A',query:'pso'},'','absent'));
assert.equal(target('#route-aco'),'aco');assert.equal(target('#route-<script>'),null);
function control(value=''){return {value,hidden:false,listeners:{},addEventListener(k,f){this.listeners[k]=f;},emit(k){this.listeners[k]();}};}
const cards=['aco','pso'].map((id,i)=>{
 const journey={open:false},stages=['origin','turn','recent','limits'].map(x=>({dataset:{stage:x},hidden:false}));
 return {dataset:{route:id,group:i?'进化':'群智能',query:id+' 学习'},hidden:false,scrolled:false,journey,stages,querySelector(){return journey;},querySelectorAll(){return stages;},scrollIntoView(){this.scrolled=true;}};
});
const controls=Object.fromEntries(['rr-group','rr-search','rr-focus','rr-expand','rr-collapse','rr-reset','rr-status','rr-empty'].map(x=>[x,control(x==='rr-focus'?'all':'')]));
const related=control();related.dataset={routeTarget:'pso'};
const panel={querySelectorAll:s=>s==='.rr-card'?cards:[related]};
let activated=0;const doc={getElementById:id=>id==='rm-view-routes'?panel:controls[id],querySelector:()=>({click(){activated++;}})};
const win={location:{hash:''},listeners:{},addEventListener(k,f){this.listeners[k]=f;},setTimeout:f=>f(),requestAnimationFrame:f=>f()};
mount(doc,win);assert.equal(controls['rr-status'].textContent,'2 / 2 条路线');
controls['rr-group'].value='群智能';controls['rr-group'].emit('change');assert.ok(!cards[0].hidden&&cards[1].hidden);
controls['rr-expand'].emit('click');assert.ok(cards[0].journey.open&&!cards[1].journey.open);
controls['rr-focus'].value='recent';controls['rr-focus'].emit('change');assert.deepEqual(cards[0].stages.map(x=>x.hidden),[true,true,false,false]);
controls['rr-search'].value='nonexistent';controls['rr-search'].emit('input');assert.ok(!controls['rr-empty'].hidden);
win.location.hash='#route-pso';win.listeners.hashchange();assert.equal(controls['rr-group'].value,'');assert.ok(!cards[1].hidden&&cards[1].journey.open&&cards[1].scrolled);assert.equal(activated,1);
controls['rr-reset'].emit('click');assert.ok(cards.every(c=>c.stages.every(s=>!s.hidden)));
controls['rr-collapse'].emit('click');assert.ok(cards.every(c=>!c.journey.open));
related.emit('click');assert.equal(win.location.hash,'#route-pso');assert.equal(activated,2);
console.log('Research routes: filters, recent mode, expansion, reset, empty state, related links and hash navigation passed.');

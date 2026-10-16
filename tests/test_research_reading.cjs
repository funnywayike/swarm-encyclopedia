const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const D=JSON.parse(fs.readFileSync(path.join(root,'data/research_map.json'),'utf8'));
const C=JSON.parse(fs.readFileSync(path.join(root,'data/research_reading_views.json'),'utf8'));
const V=require('../js/research_reading.js');
const ids=r=>r.nodes.map(x=>x.id);
const base=V.defaults(D);
assert.equal(V.select(D,C,base).nodes.length,52);
assert.equal(base.details,false);
assert.equal(base.sources,false);
let s={...base,mode:'algorithm',methods:['pso'],context:false};
assert.deepEqual(ids(V.select(D,C,s)),['pso95','calypso10']);
s.methods=['pso','ga'];
assert.deepEqual(ids(V.select(D,C,s)),['holland75','pso95','calypso10']);
s={...base,mode:'algorithm',methods:['ga']};
assert.deepEqual(ids(V.select(D,C,s)),['holland75','uspex06']);
s.context=false;
assert.deepEqual(ids(V.select(D,C,s)),['holland75']);
s={...base,mode:'problem',problems:['problem:materials'],context:false};
assert.deepEqual(ids(V.select(D,C,s)),['uspex06','calypso10']);
s.problems.push('problem:multiobjective');
assert.deepEqual(ids(V.select(D,C,s)),['nsga02','uspex06','moead07','calypso10']);
s={...base,mode:'problem',problems:['story:robot'],context:false};
for(const id of ['sims94','robotics13','qd16','erl18','robotics23'])assert.ok(ids(V.select(D,C,s)).includes(id),id);
s={...base,mode:'algorithm',methods:['pso'],bands:['2020s']};
assert.equal(V.select(D,C,s).nodes.length,0);
assert.equal(V.select(D,C,{...base,lanes:[]}).nodes.length,0);
assert.equal(V.select(D,C,{...base,bands:[]}).nodes.length,0);
assert.deepEqual(ids(V.select(D,C,{...base,milestones:true})).sort(),[...C.milestones].sort());
assert.ok(ids(V.select(D,C,{...base,query:'stanley'})).includes('neat02'));
const clean=V.normalize({mode:'bad',methods:['pso','garbage','pso'],problems:['problem:materials','invalid'],lanes:['si','bad','si'],sources:'false',bands:[]},D,C);
assert.equal(clean.mode,'overview');assert.deepEqual(clean.methods,['pso']);assert.deepEqual(clean.problems,['problem:materials']);assert.deepEqual(clean.lanes,['si']);assert.equal(clean.sources,false);assert.deepEqual(clean.bands,[]);
const reset=V.preset('overview',D,{...s,query:'empty',lanes:[],milestones:true});
assert.deepEqual(reset.lanes,base.lanes);assert.equal(reset.query,'');assert.equal(reset.milestones,false);assert.equal(reset.details,false);
let combinations=0;
for(const mode of ['overview','algorithm','problem']){
 const topics=mode==='algorithm'?C.methods.map(x=>({methods:[x.id]})):mode==='problem'?C.problemTopics.map(x=>({problems:['problem:'+x.id]})):[{}];
 for(const topic of topics)for(const lane of D.lanes)for(const band of D.bands){
  const q={...base,mode,...topic,lanes:[lane.id],bands:[band]};
  const result=V.select(D,C,q),visible=new Set(ids(result));
  for(const n of result.nodes){assert.equal(n.lane,lane.id);assert.equal(Math.floor(n.year/10)*10+'s',band);assert.ok(result.focal.has(n.id)||result.context.has(n.id));}
  for(const e of result.relations)assert.ok(visible.has(e.source)&&visible.has(e.target));
  combinations++;
 }
}
for(const t of [...C.methods,...C.problemTopics]){assert.ok(t.nodes.length);for(const id of t.nodes)assert.ok(D.nodes.some(n=>n.id===id),id);}
for(const id of C.milestones)assert.ok(D.nodes.some(n=>n.id===id),id);
console.log('Reading controls: focused selections, multi-select, empty states, reset, saved-state validation and '+combinations+' filter combinations passed.');

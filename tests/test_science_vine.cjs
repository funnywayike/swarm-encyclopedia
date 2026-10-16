const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),D=JSON.parse(fs.readFileSync(path.join(root,'data/research_map.json'),'utf8'));
D.config=JSON.parse(fs.readFileSync(path.join(root,'data/science_timeline.json'),'utf8'));
D.config.milestones=JSON.parse(fs.readFileSync(path.join(root,'data/research_milestones.json'),'utf8'));
const V=require('../js/science_vine.js'),nodes=new Map(D.nodes.map(n=>[n.id,n]));
assert.equal(new Set(D.config.trunk).size,D.config.trunk.length);
for(const id of D.config.trunk){const n=nodes.get(id);assert.ok(n,id);assert.equal(D.config.eras.filter(e=>n.year>=e.from&&n.year<=e.to).length,1);}
const years=V.years(D);assert.deepEqual([...years].sort((a,b)=>a-b),years);assert.equal(new Set(years).size,years.length);
assert.equal(years.reduce((count,y)=>count+V.yearNodes(D,y).length,0),D.nodes.length);
for(const s of D.config.stories){
 assert.ok(s.summary&&s.question);assert.equal(new Set(s.nodes).size,s.nodes.length);
 for(const id of s.nodes)assert.ok(nodes.has(id),id);
 assert.deepEqual(V.narrativeNodes(D,'event',s.id).map(n=>n.id).sort(),[...s.nodes].sort());
}
let checks=0;
for(const lane of ['all',...D.lanes.map(x=>x.id)]){
 for(const y of years){for(const n of V.yearNodes(D,y,lane)){assert.equal(n.year,y);assert.ok(lane==='all'||n.lane===lane);}checks++;}
 for(const mode of ['time','event'])for(const story of D.config.stories){
  const got=V.narrativeNodes(D,mode,story.id,lane);
  for(const n of got){assert.ok(lane==='all'||n.lane===lane);assert.ok((mode==='time'?D.config.trunk:story.nodes).includes(n.id));}checks++;
 }
}
assert.equal(V.yearNodes(D,1900).length,0);
assert.equal(V.narrativeNodes(D,'event','unknown').length,0);
console.log('Vine checks passed: '+D.config.trunk.length+' trunk events, '+D.nodes.length+' year nodes, '+D.config.stories.length+' event narratives; '+checks+' year / lane / narrative combinations.');

// Execute the client controller against a small DOM test double; this is not a visual browser test.
const vm=require('node:vm'),markup=fs.readFileSync(path.join(root,'meta/timeline/index.html'),'utf8');
const embedded=markup.match(/<script type="application\/json" id="science-vine-data">([\s\S]*?)<\/script>/)[1];
class Element{
 constructor(dataset={}){this.dataset=dataset;this.events={};this.innerHTML='';this.textContent='';this.value='';this.hidden=false;this.attrs={};}
 addEventListener(type,fn){this.events[type]=fn;}
 setAttribute(k,v){this.attrs[k]=v;}
 scrollIntoView(){}
}
const elements=new Map();
for(const id of [...markup.matchAll(/id="([^"]+)"/g)].map(x=>x[1]))elements.set(id,new Element());
elements.get('science-vine-data').textContent=embedded;
const surface=new Element(),views=['time','event'].map(x=>new Element({vineView:x}));
const lanes=['all',...D.lanes.map(x=>x.id)].map(x=>new Element({vineLane:x}));
const doc={getElementById:id=>elements.get(id)||null,querySelector:s=>s==='.science-vine'?surface:null,querySelectorAll:s=>s==='[data-vine-view]'?views:s==='[data-vine-lane]'?lanes:[]};
const ctx={document:doc,location:{hash:''},history:{replaceState(){}},matchMedia:()=>({matches:false}),console};
vm.runInNewContext(fs.readFileSync(path.join(root,'js/science_vine.js'),'utf8'),ctx);
const click=dataset=>surface.events.click({target:{closest:()=>({dataset})}});
assert.match(elements.get('vine-canopy').innerHTML,/science-canopy-time/);
assert.match(elements.get('vine-year-panel').innerHTML,/1995/);
click({vineNode:'nsga02'});
assert.match(elements.get('vine-year-panel').innerHTML,/NSGA-II/);
assert.match(elements.get('vine-year-panel').innerHTML,/NEAT/);
click({vineView:'event'});
assert.match(elements.get('vine-canopy').innerHTML,/science-story-steps/);
click({vineLane:'si'});
assert.match(elements.get('vine-canopy').innerHTML,/science-empty/);
elements.get('vine-story').value='share';
elements.get('vine-story').events.change({target:{value:'share'}});
assert.match(elements.get('vine-canopy').innerHTML,/PSO/);
assert.match(elements.get('vine-canopy').innerHTML,/data-vine-node="aco96"/);
elements.get('vine-year').value='1995';elements.get('vine-year').events.change();
assert.match(elements.get('vine-year-panel').innerHTML,/PSO/);
assert.doesNotMatch(elements.get('vine-year-panel').innerHTML,/GRASP/);
console.log('Client controller passed: event click, year branches, narrative switch, lane empty state and year selector.');

const frontier=V.narrativeNodes(D,'time','escape','all','frontier');
assert.deepEqual(frontier.map(n=>n.id),['alpha25']);
assert.deepEqual(V.narrativeNodes(D,'time','escape','all','infrastructure').map(n=>n.id),['tsplib91','coco21']);
assert.ok(V.narrativeNodes(D,'time','escape','all','mechanism').every(n=>V.layerOf(D,n)==='mechanism'));
click({vineLane:'all'});click({vineView:'time'});click({vineLayer:'frontier'});
assert.match(elements.get('vine-canopy').innerHTML,/data-vine-node="alpha25"/);
assert.doesNotMatch(elements.get('vine-canopy').innerHTML,/data-vine-node="pso95"/);
click({vineNode:'alpha25'});
assert.match(elements.get('vine-year-panel').innerHTML,/日期释义/);
assert.match(elements.get('vine-year-panel').innerHTML,/前沿观察不等于经典地位认证/);
click({vineLayer:'all'});click({vineNode:'cma01'});
assert.match(elements.get('vine-year-panel').innerHTML,/1996/);
assert.match(elements.get('vine-year-panel').innerHTML,/Hansen/);
console.log('Dossier controller: source types, frontier isolation, date semantics, author credits and linked routes passed.');

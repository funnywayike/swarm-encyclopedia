/* Reading selections are editorial topic links, never inferred scientific genealogy. */
(function(root){
  'use strict';
  function defaults(D){
    return {mode:'overview',methods:[],problems:[],lanes:D.lanes.map(x=>x.id),bands:[...D.bands],query:'',milestones:false,compact:true,details:false,sources:false,boundaries:false,context:true,connections:true,layout:'timeline'};
  }
  function normalize(raw,D,C){
    const s=defaults(D), modes=['overview','algorithm','problem'];
    if(!raw||typeof raw!=='object')return s;
    if(modes.includes(raw.mode))s.mode=raw.mode;
    if(Array.isArray(raw.methods))s.methods=[...new Set(raw.methods.filter(id=>C.methods.some(x=>x.id===id)))];
    if(Array.isArray(raw.problems))s.problems=[...new Set(raw.problems.filter(id=>D.applications.some(x=>'story:'+x.id===id)||C.problemTopics.some(x=>'problem:'+x.id===id)))];
    for(const k of ['lanes','bands'])if(Array.isArray(raw[k]))s[k]=[...new Set(raw[k].filter(x=>s[k].includes(x)))];
    for(const k of ['milestones','compact','details','sources','boundaries','context','connections'])if(typeof raw[k]==='boolean')s[k]=raw[k];
    if(typeof raw.query==='string')s.query=raw.query.slice(0,200);
    if(['timeline','list'].includes(raw.layout))s.layout=raw.layout;
    return s;
  }
  function preset(mode,D,previous){
    return {...previous,mode,lanes:D.lanes.map(x=>x.id),bands:[...D.bands],query:'',milestones:false,compact:mode==='overview',details:mode!=='overview',sources:false,boundaries:mode!=='overview'};
  }
  function select(D,C,s){
    const tags=n=>(n.apps||[]).map(id=>C.applicationAliases[id]||id);
    const eligible=n=>{
      if(s.mode==='overview')return true;
      if(s.mode==='algorithm')return C.methods.some(x=>(!s.methods.length||s.methods.includes(x.id))&&x.nodes.includes(n.id));
      if(!s.problems.length)return tags(n).some(id=>D.applications.some(a=>a.id===id))||C.problemTopics.some(x=>x.nodes.includes(n.id));
      return s.problems.some(id=>id.startsWith('problem:')?C.problemTopics.find(x=>'problem:'+x.id===id)?.nodes.includes(n.id):tags(n).includes(id.slice(6)));
    };
    const focal=new Set(D.nodes.filter(eligible).map(x=>x.id)), context=new Set();
    if(s.context&&((s.mode==='algorithm'&&s.methods.length)||(s.mode==='problem'&&s.problems.length))){
      D.relations.forEach(e=>{if(focal.has(e.source)&&!focal.has(e.target))context.add(e.target);if(focal.has(e.target)&&!focal.has(e.source))context.add(e.source);});
    }
    const nodes=D.nodes.filter(n=>{
      if(!focal.has(n.id)&&!context.has(n.id))return false;
      const band=Math.floor(n.year/10)*10+'s';
      if(!s.lanes.includes(n.lane)||!s.bands.includes(band))return false;
      if(s.milestones&&!C.milestones.includes(n.id))return false;
      if(!s.query)return true;
      const extra=[...(n.refs||[]).map(id=>D.references.find(r=>r.id===id)?.title||''),...tags(n).map(id=>D.applications.find(a=>a.id===id)?.name||''),...(n.teams||[]).map(id=>D.teams.find(t=>t.id===id)?.name||'')];
      return [n.title,n.summary,n.contribution,n.boundary,...extra].join(' ').toLowerCase().includes(s.query.toLowerCase());
    });
    const visible=new Set(nodes.map(n=>n.id));
    return {nodes,focal,context,relations:D.relations.filter(e=>visible.has(e.source)&&visible.has(e.target))};
  }
  const api={defaults,normalize,preset,select};
  if(typeof module==='object'&&module.exports)module.exports=api;
  else root.ResearchReading=api;
})(typeof globalThis!=='undefined'?globalThis:this);

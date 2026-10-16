const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {select} = require('../js/review_library.js');
const articles = JSON.parse(fs.readFileSync(path.join(__dirname,'../data/review_library.json'),'utf8')).articles;
const rows = articles.map(a => ({query:[a.title,a.authors.join(' '),a.category,a.doi,a.year].join(' ').toLowerCase(),category:a.category,level:a.readingLevel}));
for (const category of ['',...new Set(rows.map(a=>a.category))]) {
  for (const level of ['','read','sections','metadata']) {
    const got=select(rows,'',category,level);
    for (const a of got) {
      assert.ok(!category || a.category===category);
      assert.ok(!level || (level==='read' ? a.level!=='metadata' : a.level===level));
    }
    assert.equal(got.length,rows.filter(a=>(!category||a.category===category)&&(!level||(level==='read'?a.level!=='metadata':a.level===level))).length);
  }
}
assert.equal(select(rows,'definitely nonexistent phrase','','').length,0);
assert.deepEqual(select(rows,'  BRANKE ','',''),select(rows,'branke','',''));
assert.ok(select(rows,'多目标','','').length>0);
assert.ok(select(rows,'10.1016/j.paerosci.2008.11.001','','sections').length===1);
console.log('Review catalogue filtering: categories, levels, search and empty results passed.');

// Exercise the browser controller with a small DOM double: filtering, reset and pagination.
const vm = require('node:vm');
function control() {
  return {value:'',hidden:false,textContent:'',listeners:{},
    addEventListener(name,fn){this.listeners[name]=fn;}};
}
const elements = Object.fromEntries(['rv-query','rv-category','rv-level','rv-count','rv-more'].map(id=>[id,control()]));
const cards = rows.map(a=>({dataset:{query:a.query,category:a.category,level:a.level},hidden:false}));
const panel = {querySelectorAll:()=>cards};
const documentDouble = {getElementById:id=>id==='rm-view-reviews'?panel:elements[id]};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../js/review_library.js'),'utf8'),{window:{document:documentDouble}});
function shown(){return cards.filter(c=>!c.hidden).length;}
assert.equal(shown(),12);
elements['rv-more'].listeners.click();
assert.equal(shown(),24);
elements['rv-level'].value='sections';
elements['rv-level'].listeners.change();
assert.equal(shown(),rows.filter(a=>a.level==='sections').length);
assert.equal(elements['rv-more'].hidden,true);
elements['rv-query'].value='definitely nonexistent phrase';
elements['rv-query'].listeners.input();
assert.equal(shown(),0);
assert.ok(elements['rv-count'].textContent.includes('没有匹配'));
elements['rv-query'].value='';
elements['rv-level'].value='';
elements['rv-query'].listeners.input();
assert.equal(shown(),12);
assert.equal(elements['rv-more'].hidden,false);
console.log('Review panel controller: pagination, reset, read depth and empty state passed.');

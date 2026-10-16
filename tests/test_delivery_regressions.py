"""Regression checks for complete solutions, immutable exports and content links."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "py"))
import domains as D

@pytest.mark.parametrize("algo", [a["key"] for a in json.loads(D.domain_list("continuous", {}))["algos"]])
def test_continuous_exports_full_solution_and_keeps_search_curve(algo):
    problem = D.domain_preset("continuous", 7, {"fn": "sphere", "dim": 5})
    D.domain_start("continuous", problem, algo, json.dumps({"max_iter": 3, "seed": 7, "n_pop": 8}))
    ctx = D._RUN["ctx"]
    while (raw := D.domain_step()) is not None:
        state = json.loads(raw)
        assert len(state["best_sol"]) == 5
        assert ctx.eval(state["best_sol"]) == pytest.approx(state["best"])
        assert state["gbest_pos"] == state["best_sol"][:2]

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []
    def handle_starttag(self, tag, attrs):
        self.links.extend(v for k, v in attrs if k in ("href", "src") and v)

def test_all_built_public_links_exist():
    missing = []
    for folder in ("algo", "problem", "compare", "demo", "guide", "encyclopedia", "components", "matrix", "applications", "coverage", "discovery", "meta"):
        for page in (ROOT / folder).rglob("*.html"):
            parser = Links(); parser.feed(page.read_text(encoding="utf-8"))
            for link in parser.links:
                url = urlsplit(link)
                if url.scheme or url.netloc or not url.path:
                    continue
                target = ROOT / unquote(url.path).lstrip("/") if url.path.startswith("/") else page.parent / unquote(url.path)
                if not target.exists():
                    missing.append((str(page.relative_to(ROOT)), link))
    assert not missing, missing

def test_frontend_exports_survive_control_changes_and_async_loading():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node required for frontend state regression")
    script = r"""
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let src=fs.readFileSync('js/domain_page.js','utf8');
src=src.replace('import(PREFIX + "js/domains_src.js")','new Promise(resolve => globalThis.resolveBundle = resolve)')
 .replace('import(PREFIX + "js/result_export.js")','new Promise(resolve => globalThis.resolveResult = resolve)')
 .replace('import(PREFIX + "js/run_guard.js")','Promise.reject(new Error("skip guard"))');
const fields={}, blobs=[], results=[],callbacks=[];
const U=URL;U.createObjectURL=()=>'';U.revokeObjectURL=()=>{};
function elem(id){if(id==='customRow')return null;return fields[id] ||= {value:'',options:[],dataset:{},addEventListener(){},querySelectorAll(){return []},click(){}};}
const c={URL:U,URLSearchParams,Promise,Blob:class{constructor(parts){blobs.push(parts.join(''));}},setTimeout(){},clearInterval(){},performance:{now:()=>10},window:{PAGE_DOMAIN:'knapsack',PAGE_PRESETS:{a:{}},location:{search:''},addEventListener(){}},document:{currentScript:{src:'http://localhost/js/domain_page.js'},addEventListener(t,fn){callbacks.push(fn)},getElementById:elem,createElement(){return {click(){}}}},Worker:class{postMessage(){}}};
vm.createContext(c);vm.runInContext(src,c);
vm.runInContext(`customFill=()=>{};customEnsureAlgos=()=>{};drawPreset=()=>{};drawConv=()=>{};boot();history=[{iter:3,best:99}];lastState={iter:3,best:99};runParams={seed:7,max_iter:20};runRecord={problem:{id:'old'},algo:'sa',params:runParams};problem={id:'old'};inflight=2;loadPreset();`,c);
assert.equal(vm.runInContext('lastState',c),null);assert.equal(vm.runInContext('runRecord',c),null);assert.equal(vm.runInContext('history.length',c),0);assert.equal(vm.runInContext('inflight',c),0);assert.equal(vm.runInContext('staleSteps',c),2);
vm.runInContext(`worker.onmessage({data:{type:'preset',payload:{id:'new'}}});boot=()=>{};`,c);
callbacks[0]();
function setup(){vm.runInContext(`problem={id:'original'};curAlgo='sa';runParams={seed:7,max_iter:20,t0:123};runRecord={problem:JSON.parse(JSON.stringify(problem)),algo:'sa',algoName:'SA',params:{...runParams}};history=[{iter:3,best:42}];lastState={iter:3,best:42,best_sol:[1,0]};info={sense:'max'};`,c);elem('algoSel').value='ga';elem('seedInp').value='99';elem('iterInp').value='900';}
(async()=>{
 setup();vm.runInContext('exportHistoryCsv()',c);assert(blobs.pop().includes('algo=sa seed=7 max_iter=20'));
 setup();elem('btnBundleDom').onclick();vm.runInContext(`problem.id='changed';history.push({iter:4,best:100});runParams.t0=999;`,c);c.resolveBundle({DOMAINS_SRC:'source'});await new Promise(r=>setImmediate(r));
 const bundle=JSON.parse(blobs.pop());assert.equal(bundle.algo,'sa');assert.equal(bundle.seed,7);assert.equal(bundle.iter,20);assert.equal(bundle.params.t0,123);assert.equal(bundle.problem.id,'original');assert.equal(bundle.history.length,1);
 setup();const pending=elem('btnExportDom').onclick();vm.runInContext(`problem.id='changed';history=[];lastState=null;runParams.seed=999;`,c);c.resolveResult({algoParams:p=>Object.fromEntries(Object.entries(p).filter(([k])=>!['seed','max_iter'].includes(k))),buildResult:o=>o,downloadJson:o=>results.push(o)});await pending;
 assert.equal(results[0].problem.id,'original');assert.equal(results[0].seed,7);assert.equal(results[0].algo,'sa');assert.equal(results[0].params.t0,123);assert.equal(results[0].curve.length,1);
 console.log('export regression checks passed');
})().catch(e=>{console.error(e);process.exitCode=1});
"""
    result = subprocess.run([node, "-e", script], cwd=ROOT, text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr

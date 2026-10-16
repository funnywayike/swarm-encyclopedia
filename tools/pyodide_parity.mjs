// Pyodide 与黄金快照的逐项一致性：在真实的 Pyodide 里执行站点实际发给浏览器的引擎源码
// （js/domains_src.js、js/solvers_src.js），把 tests/golden/results.json 里的组合重跑一遍，数值必须与快照一致。
//
//   node tools/pyodide_parity.mjs                 全部组合（几分钟）
//   node tools/pyodide_parity.mjs --sample 60     每隔若干个取样，共约 60 个（快速自查）
//   node tools/pyodide_parity.mjs --no-tsp        只跑问题域，不跑 TSP 求解器
//   PYODIDE_MJS=/path/to/pyodide.mjs node tools/pyodide_parity.mjs     用别处的 Pyodide（默认 vendor/pyodide/）
//
// 为什么需要它：本地 pytest 跑的是 CPython；浏览器里是 Pyodide 自带的 Python（目前 3.14）、同一个名字空间拼接执行。
// 两者的差异（版本差异、拼接环境里别名 import 不绑定……）pytest 看不见。退出码非 0 = 有差异或报错。
// （tools/pyodide_smoke.mjs 另外检查 TSP 求解器的 step / step_k / run_all 接口协议。）
import { readFileSync } from "node:fs";
import { pathToFileURL, fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const flag = (n) => args.includes(n);
const opt = (n, d) => (args.includes(n) ? args[args.indexOf(n) + 1] : d);
const SAMPLE = Number(opt("--sample", 0));
const WITH_TSP = !flag("--no-tsp");

const pyodidePath = process.env.PYODIDE_MJS || resolve(ROOT, "vendor/pyodide/pyodide.mjs");
const { loadPyodide } = await import(pathToFileURL(resolve(pyodidePath)).href);

// js/*_src.js 的格式：export const NAME = <JSON 字符串>;
function extract(file, name) {
  const src = readFileSync(resolve(ROOT, file), "utf-8");
  const start = src.indexOf(`export const ${name} = `);
  if (start < 0) throw new Error(`${file}：找不到 ${name}`);
  const from = start + `export const ${name} = `.length;
  const end = src.indexOf(";\nexport const ", from);
  return JSON.parse(src.slice(from, end < 0 ? src.lastIndexOf(";") : end));
}

const golden = JSON.parse(readFileSync(resolve(ROOT, "tests/golden/results.json"), "utf-8"));
const keys = Object.keys(golden).sort();
const tspKeys = keys.filter((k) => k.startsWith("tsp/"));
let domKeys = keys.filter((k) => !k.startsWith("tsp/"));
if (SAMPLE > 0) {
  const step = Math.max(1, Math.floor(domKeys.length / SAMPLE));
  domKeys = domKeys.filter((_, i) => i % step === 0);
}

const near = (a, b) => Math.abs(a - b) <= 1e-6 * Math.max(1, Math.abs(a), Math.abs(b));
const sameTriplet = (want, got) => (want === null ? got === null : got !== null && want.length === got.length && want.every((x, i) => near(x, got[i])));
const brief = (e) => String(e.message).split("\n").slice(-2).join(" ").slice(0, 160);
const t0 = Date.now();
const bad = [];

// ---------------------------------------------------------------- 问题域
console.log("[1/2] Pyodide + DOMAINS_SRC（浏览器里的域引擎）…");
const dom = await loadPyodide();
console.log("  Python", dom.runPython("import sys; sys.version.split()[0]"));
await dom.runPythonAsync(extract("js/domains_src.js", "DOMAINS_SRC"));
dom.runPython(`
import json
_SEED, _ITERS = 7, 30
def _gc(dom_, var, algo):
    opts = {"variant": var} if var and var != "-" else {}
    pre = domain_preset(dom_, _SEED, opts)
    domain_start(dom_, pre, algo, json.dumps({"max_iter": _ITERS, "seed": _SEED}))
    curve = []
    while True:
        s = domain_step()
        if s is None:
            break
        st = json.loads(s)
        curve.append(float(st["best"] if "best" in st else st["nd"]))
    if not curve:
        return json.dumps(None)
    return json.dumps([round(curve[0], 6), round(curve[len(curve) // 2], 6), round(curve[-1], 6)])
`);
const gc = dom.globals.get("_gc");
let checked = 0;
for (const key of domKeys) {
  const [d, v, a] = key.split("/");
  try {
    const got = JSON.parse(gc(d, v, a));
    if (!sameTriplet(golden[key], got)) bad.push(`${key}: 快照 ${JSON.stringify(golden[key])} ≠ Pyodide ${JSON.stringify(got)}`);
  } catch (e) {
    bad.push(`${key}: 报错 ${brief(e)}`);
  }
  if (++checked % 250 === 0) console.log(`  … ${checked}/${domKeys.length}`);
}
console.log(`  域引擎：${domKeys.length} 个组合，用时 ${((Date.now() - t0) / 1000).toFixed(0)}s`);

// ---------------------------------------------------------------- TSP 求解器
if (WITH_TSP) {
  console.log("[2/2] Pyodide + SOLVERS_SRC（TSP 求解器）…");
  const t1 = Date.now();
  const sol = await loadPyodide();
  await sol.runPythonAsync(extract("js/solvers_src.js", "SOLVERS_SRC"));
  sol.runPython(`
import json, random
def _gt(algo):
    rng = random.Random(7)
    cities = [[round(rng.uniform(0, 100), 3), round(rng.uniform(0, 100), 3)] for _ in range(30)]
    prob = build_problem(cities)
    curve = [st.best_cost for st in SOLVERS[algo]().solve(prob, {"max_iter": 30, "seed": 7})]
    if not curve:
        return json.dumps(None)
    return json.dumps([round(curve[0], 6), round(curve[len(curve) // 2], 6), round(curve[-1], 6)])
`);
  const gt = sol.globals.get("_gt");
  for (const key of tspKeys) {
    try {
      const got = JSON.parse(gt(key.split("/")[2]));
      if (!sameTriplet(golden[key], got)) bad.push(`${key}: 快照 ${JSON.stringify(golden[key])} ≠ Pyodide ${JSON.stringify(got)}`);
    } catch (e) {
      bad.push(`${key}: 报错 ${brief(e)}`);
    }
  }
  console.log(`  TSP 求解器：${tspKeys.length} 个，用时 ${((Date.now() - t1) / 1000).toFixed(0)}s`);
}

const total = domKeys.length + (WITH_TSP ? tspKeys.length : 0);
console.log(`\n共核对 ${total} 个组合，${bad.length} 个有问题，总用时 ${((Date.now() - t0) / 1000).toFixed(0)}s`);
for (const b of bad.slice(0, 25)) console.log("  ✗ " + b);
if (bad.length > 25) console.log(`  …另有 ${bad.length - 25} 个`);
process.exit(bad.length ? 1 : 0);

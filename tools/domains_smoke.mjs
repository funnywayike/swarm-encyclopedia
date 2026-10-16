// v0.8 问题域生产链路冒烟：真实 Pyodide + 内嵌 DOMAINS_SRC 端到端跑一遍。
// 用法：PYODIDE_MJS=/path/to/pyodide.mjs node tools/domains_smoke.mjs
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const pyodidePath = process.env.PYODIDE_MJS || "../vendor/pyodide/pyodide.mjs";
const { loadPyodide } = await import(
  pyodidePath.includes(":") || pyodidePath.startsWith("/")
    ? pathToFileURL(resolve(pyodidePath)).href
    : new URL(pyodidePath, import.meta.url).href
);

const src = readFileSync(new URL("../js/domains_src.js", import.meta.url), "utf-8");
const m = src.match(/export const DOMAINS_SRC = (.*);\n/s);
if (!m) throw new Error("domains_src.js 格式不对");
const DOMAINS_SRC = JSON.parse(m[1]);

console.log("[1/3] 初始化 Pyodide…");
const pyodide = await loadPyodide();
await pyodide.runPythonAsync(DOMAINS_SRC);
console.log("  OK：DOMAINS_SRC 装载完成");

console.log("[2/3] 三域各跑一个算法端到端…");
const cases = [
  ["knapsack", "ga", {}],
  ["continuous", "pso", { fn: "rastrigin", dim: 2 }],
  ["multiobj", "nsga2", {}],
];
for (const [domain, algo, opts] of cases) {
  pyodide.globals.set("_d", domain);
  pyodide.globals.set("_s", 7);
  pyodide.globals.set("_o", JSON.stringify(opts));
  let prob;
  try {
    prob = pyodide.runPython(`domain_preset(_d, _s, _o)`);
  } catch (e) {
    console.error("domain_preset 失败：", e.message);
    throw e;
  }
  pyodide.globals.set("_p", prob);
  pyodide.globals.set("_a", algo);
  pyodide.globals.set("_pp", JSON.stringify({ max_iter: 60, seed: 7 }));
  pyodide.runPython(`domain_start(_d, _p, _a, _pp)`);
  let last = null, n = 0;
  for (;;) {
    const s = pyodide.runPython("domain_step()");
    if (s === undefined || s === null) break;
    last = JSON.parse(s);
    n++;
  }
  if (n !== 60) throw new Error(`${domain}/${algo} 只跑了 ${n} 代`);
  const summary =
    domain === "multiobj" ? `非支配解 ${last.nd}` : `最优值 ${Number(last.best).toFixed(3)}`;
  console.log(`  OK：${domain}/${algo} 60 代，${summary}`);
}

console.log("[3/3] list 接口…");
for (const d of ["knapsack", "continuous", "multiobj"]) {
  const out = JSON.parse(pyodide.runPython(`domain_list("${d}")`));
  if (!out.algos.length || !out.defaults) throw new Error(`${d} list 异常`);
  console.log(`  OK：${d} ${out.algos.length} 个算法`);
}
console.log("\n问题域生产链路冒烟：全部通过");

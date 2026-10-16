// 在 Node 里真实跑一遍 Pyodide + 浏览器用的 TSP 求解器源码（js/solvers_src.js），检查 step / step_k / run_all 接口协议
// 目的：验证「Python 代码在 WASM 环境里能跑」这个最大风险点。
// 浏览器里是 Pyodide + Web Worker，Node 里是同一个 Pyodide 内核，
// 能跑通就说明算法包本身在 WASM 下没有兼容性问题（剩下的只是 DOM/Worker 那层）。
// pyodide 通过绝对路径导入（装在隔离工作区里，不污染项目目录）：
//   set PYODIDE_MJS=C:/.../node_modules/pyodide/pyodide.mjs
// 未设置时尝试普通 import。
const PYODIDE_MJS = process.env.PYODIDE_MJS;
const { loadPyodide } = PYODIDE_MJS
  ? await import("file:///" + PYODIDE_MJS.replace(/\\/g, "/"))
  : await import("pyodide");
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(here, ".."); // 项目根目录（本文件在 tools/ 下）

const py = await loadPyodide();
// 执行站点实际发给浏览器的那份引擎源码（build_pages.py 把 taxonomy / components / solvers 拼好放在 js/solvers_src.js 里），
// 而不是裸的 py/solvers.py——后者依赖拼接进来的分类表。
const bundle = fs.readFileSync(path.join(ROOT, "js", "solvers_src.js"), "utf8");
const from = bundle.indexOf("export const SOLVERS_SRC = ") + "export const SOLVERS_SRC = ".length;
await py.runPythonAsync(JSON.parse(bundle.slice(from, bundle.indexOf(";\nexport const ", from))));
console.log("[1] 算法包加载成功");

const solvers = JSON.parse(py.runPython("list_solvers()"));
console.log("[2] 注册表：", solvers.map((s) => `${s.key}${s.implemented ? "" : "(未实现)"}`).join(", "));

const n = 30;
let seed = 1;
const rnd = () => (seed = (seed * 1103515245 + 12345) % 2147483648) / 2147483648;
const cities = Array.from({ length: n }, () => [rnd() * 100, rnd() * 100]);
py.globals.set("_c", JSON.stringify(cities));

console.log("[3] 各算法跑 50 代（step 单代接口）：");
for (const s of solvers.filter((s) => s.implemented)) {
  const t0 = Date.now();
  py.globals.set("_p", JSON.stringify({ max_iter: 50, seed: 42 }));
  py.runPython(`start(_c, "${s.key}", _p)`);
  let last = null, count = 0;
  while (true) {
    const out = py.runPython("step()");
    if (out === undefined || out === null) break;
    last = JSON.parse(out);
    count++;
  }
  const el = Date.now() - t0;
  console.log(
    `    ${s.key.padEnd(5)} 代数=${String(count).padStart(3)}  最优=${last.best_cost.toFixed(1)}  ${el}ms`
  );
  if (count === 0) throw new Error(`${s.key} 一代都没跑出来`);
  if (!Array.isArray(last.best_tour) || last.best_tour.length !== n) throw new Error(`${s.key} 路径非法`);
}

// v0.3：step_k 批量采样接口（前端「每 N 代取一点」依赖它）
console.log("[4] step_k 批量采样（每批 5 代，aco）：");
py.globals.set("_p", JSON.stringify({ max_iter: 33, seed: 42 }));
py.runPython('start(_c, "aco", _p)');
let sampled = 0, lastK = null, batchK = 0;
while (true) {
  const out = py.runPython("step_k(5)");
  if (out === undefined || out === null) break;
  const d = JSON.parse(out);
  if (!Array.isArray(d.points) || d.points.length === 0 || d.points.length > 5) {
    throw new Error(`step_k 返回非法 points：${d.points && d.points.length}`);
  }
  if (d.points[d.points.length - 1][0] !== d.iteration) throw new Error("points 末代与 iteration 不一致");
  sampled += d.points.length;
  lastK = d;
  batchK++;
  if (d.exhausted) break;
}
console.log(`    批次=${batchK}  采样代数=${sampled}/33  末代=${lastK.iteration}  exhausted=${lastK.exhausted}`);
if (lastK.iteration !== 33) throw new Error(`step_k 未跑满 33 代（实际 ${lastK.iteration}）`);
const after = py.runPython("step_k(5)");
if (after !== undefined && after !== null) throw new Error("耗尽后 step_k 应返回 None");
console.log("    耗尽后返回 None ✓");

const t0 = Date.now();
const all = JSON.parse(py.runPython("run_all(_c, 50, 42)"));
console.log(`[5] run_all（对比页接口）成功，${Date.now() - t0}ms，基线=${all.nn.toFixed(1)}`);
for (const [k, v] of Object.entries(all.results)) {
  console.log(`    ${k.padEnd(5)} ${v.name.padEnd(14)} 终值=${v.final}  曲线长度=${v.curve.length}`);
}

console.log("\n全部通过：算法包（含 step_k 批量采样）在 Pyodide/WASM 下可正常运行");

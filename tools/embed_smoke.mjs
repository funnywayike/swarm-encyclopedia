// 端到端冒烟：走生产链路（嵌入源码 import → runPythonAsync → start/step_k）
import { pathToFileURL } from "url";
import { SOLVERS_SRC } from "../js/solvers_src.js";
const { loadPyodide } = await import(pathToFileURL(process.env.PYODIDE_MJS).href);

const py = await loadPyodide();
await py.runPythonAsync(SOLVERS_SRC); // 与 worker.js 完全相同的执行方式
const names = JSON.parse(py.runPython("list_solvers()"));
console.log("注册算法数:", names.filter((d) => d.implemented).length, "（含未实现共", names.length + "）");

const cities = Array.from(
  { length: 50 },
  (_, i) => [Math.sin(i * 2.3) * 50 + 50, Math.cos(i * 1.7) * 50 + 50],
);
py.globals.set("_c", JSON.stringify(cities));
py.runPython('start(_c, "aco", "{\\"max_iter\\": 60, \\"seed\\": 42}")');
let n = 0;
let last = null;
for (;;) {
  const s = py.runPython("step_k(5)");
  if (!s) break;
  const d = JSON.parse(s);
  last = d;
  n += d.points.length;
}
console.log(
  "ACO 跑通：采样 " + n + " 代，末代=" + last.iteration +
  " best=" + last.best_cost.toFixed(1) + " exhausted=" + last.exhausted,
);
console.log("✓ 生产链路（嵌入源码→Pyodide→算法执行）端到端 OK");

// 结果导出：把一次求解整理成 swarm-result/v1（与命令行 swarm.py solve --out 同一格式）。
// TSP 页（tool.js）和各问题域页（domain_page.js）共用——两处都用 import(PREFIX + "js/result_export.js") 动态加载。
// 格式说明见 docs/result-format.md；导出的文件可以用 `python swarm.py replay 结果.json` 回读并复现。

export const RESULT_SCHEMA = "swarm-result/v1";

// curve: [[代数, 当时的最优值], …]；params 只放算法自己的参数（不含 max_iter / seed，它们是顶层的 iters / seed）
export function buildResult(o) {
  const iters = o.iters;
  const done = o.completedIters == null ? iters : o.completedIters;
  const res = {
    schema: RESULT_SCHEMA,
    generator: "web",
    created: new Date().toISOString(),
    domain: o.domain,
    variant: o.variant || null,
    algo: o.algo,
    algo_name: o.algoName || o.algo,
    seed: o.seed,
    iters,
    completed_iters: done, // < iters 说明运行被中途停止；复现时只核对已记录的曲线点
    params: o.params || {},
    sense: o.sense || "min",
    best: o.best,
    best_solution: o.bestSolution == null ? null : o.bestSolution,
    elapsed_s: o.elapsed == null ? null : Math.round(o.elapsed * 1000) / 1000,
    curve: o.curve || [],
    problem: o.problem,
  };
  if (o.extra) res.extra = o.extra;
  return res;
}

export function downloadJson(obj, filename) {
  const blob = new Blob([JSON.stringify(obj)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

// 把页面参数拆成「算法自己的参数」：去掉 max_iter / seed
export function algoParams(all) {
  const out = {};
  for (const [k, v] of Object.entries(all || {})) if (k !== "max_iter" && k !== "seed") out[k] = v;
  return out;
}

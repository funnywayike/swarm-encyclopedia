// P1 计算层：Web Worker + Pyodide
//
// 关键点：
// 1) module worker（必须）：当前 Pyodide 在 classic worker 里直接抛 "Classic web workers
//    are not supported"。代价：module worker / module script 不能在 file:// 下运行，
//    页面需经 http 访问（本地：python serve.py；线上：GitHub Pages 等静态托管）
// 2) Python 侧用生成器，JS 反复调用 step() 推进 → 暂停/单步/调速全部由 JS 掌控
// 3) 零第三方包：solvers.py 不依赖 numpy，省掉 loadPackagesFromImports 的等待
// 4) ★ 多 CDN 回退：国内访问 jsdelivr 时好时坏，一个源失败就换下一个，
//    全部失败时给出可操作的提示（把 Pyodide 放到本地 /vendor/ 即可彻底解决）

const PYODIDE_VERSION = "314.0.6";
const CDNS = [
  `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/pyodide.mjs`,
  `https://unpkg.com/pyodide@${PYODIDE_VERSION}/pyodide.mjs`,
  `https://cdn.jsdelivr.net/npm/pyodide@${PYODIDE_VERSION}/pyodide.mjs`,
];
const LOCAL_PYODIDE = "../vendor/pyodide/pyodide.mjs"; // 本地兜底：见 README「国内加载优化」
// Python 源码不再运行时 fetch——部分宿主（如内置预览代理）不为 .py 提供静态服务，
// fetch 会拿到 404 文本 "Not Found" 被当 Python 执行 → SyntaxError。
// 构建时由 build_pages.py 生成 js/solvers_src.js（内嵌源码字符串），运行时零网络依赖。
import { SOLVERS_SRC, VALIDATE_SRC } from "./solvers_src.js";

let pyodide = null;

function withTimeout(promise, ms, label) {
  return Promise.race([
    promise,
    new Promise((_, rej) => setTimeout(() => rej(new Error(`${label} 超时 ${ms / 1000}s`)), ms)),
  ]);
}

async function initRuntime() {
  const sources = [LOCAL_PYODIDE, ...CDNS];
  let lastErr = null;
  for (let i = 0; i < sources.length; i++) {
    const url = sources[i];
    const isLocal = url === LOCAL_PYODIDE;
    postMessage({
      type: "status",
      text: `正在加载 Pyodide 运行时（首次约 10MB，请稍候）… [源 ${i + 1}/${sources.length}]`,
    });
    try {
      const mod = await withTimeout(import(/* webpackIgnore: true */ url), isLocal ? 8000 : 25000, "下载");
      pyodide = await withTimeout(mod.loadPyodide(), 30000, "初始化");
      break;
    } catch (err) {
      lastErr = err;
      console.warn("Pyodide 源不可用：", url, err);
    }
  }
  if (!pyodide) {
    throw new Error(
      `所有 Pyodide 源都加载失败（${lastErr ? lastErr.message : "未知原因"}）。` +
        "解决：把 pyodide 发行版下载到本地 vendor/pyodide/ 目录即可离线运行，见 README。"
    );
  }

  postMessage({ type: "status", text: "正在加载算法包…" });
  await pyodide.runPythonAsync(SOLVERS_SRC);
  // 标准化数据层（py/validate.py）：与问题域页面共用同一份校验器，TSP 页的导入也走它
  pyodide.globals.set("_vsrc", VALIDATE_SRC);
  pyodide.runPython(
    "import sys, types\n_vm = types.ModuleType('validate')\nexec(_vsrc, _vm.__dict__)\nsys.modules['validate'] = _vm"
  );

  const solvers = JSON.parse(pyodide.runPython("list_solvers()"));
  postMessage({ type: "ready", solvers, version: PYODIDE_VERSION });
}

self.onmessage = async (event) => {
  const { cmd, payload } = event.data || {};
  try {
    if (cmd === "init") {
      await initRuntime();
      return;
    }
    if (!pyodide) throw new Error("Pyodide 尚未就绪");

    if (cmd === "validate") {
      // 导入数据：读取 + 校验 + 规整（TSPLIB / CSV / JSON / 距离矩阵），错误带字段路径
      pyodide.globals.set("_vtext", payload.text);
      pyodide.globals.set("_vfile", payload.filename || "");
      const out = pyodide.runPython(
        "import json, validate\njson.dumps(validate.check_text(_vtext, 'tsp', _vfile, False, None), ensure_ascii=False)"
      );
      postMessage({ type: "validated", payload: JSON.parse(out) });
      return;
    }

    if (cmd === "start") {
      // cities：裸坐标 [[x,y],…]；或校验器规整后的实例 {cities, metric?, matrix?}（TSPLIB 距离 / 距离矩阵）
      const { cities, algo, params } = payload;
      pyodide.globals.set("_cities_json", JSON.stringify(cities));
      pyodide.globals.set("_params_json", JSON.stringify(params || {}));
      const out = pyodide.runPython(`start(_cities_json, "${algo}", _params_json)`);
      postMessage({ type: "started", payload: JSON.parse(out) });
      return;
    }

    if (cmd === "step") {
      // v0.3：payload.k > 1 时一次推进 k 代（「每 N 代采样一次」），返回批量采样点
      const k = (payload && payload.k) || 1;
      pyodide.globals.set("_step_k", k);
      const s = pyodide.runPython("step_k(_step_k)"); // Python str -> JS string；结束为 None -> undefined
      if (s === undefined || s === null) {
        postMessage({ type: "done" });
      } else {
        postMessage({ type: "state", payload: JSON.parse(s) });
      }
      return;
    }

    if (cmd === "run_all") {
      // 对比页：同一实例交给所有算法各跑一遍（不走动画，一次算完）
      const { cities, max_iter, seed } = payload;
      pyodide.globals.set("_cities_json", JSON.stringify(cities));
      const out = pyodide.runPython(`run_all(_cities_json, ${max_iter}, ${seed})`);
      postMessage({ type: "all_done", payload: JSON.parse(out) });
      return;
    }

    if (cmd === "reset") {
      postMessage({ type: "reset_ok" });
      return;
    }
  } catch (err) {
    // 混沌走查 P1（2026-09-27 狂飙）：Python Traceback 十几行天书——用户只看得到最后一行结论
    const raw = String(err && err.message ? err.message : err);
    const lines = raw.trim().split("\n").filter(Boolean);
    postMessage({ type: "error", text: lines[lines.length - 1].slice(0, 300) });
  }
};

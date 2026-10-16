// v0.8 问题域计算层：Web Worker + Pyodide
// 与 worker.js（TSP 侧）同构，但服务五个问题域（背包/连续/多目标/图着色/装箱）。
// module worker（Pyodide 拒绝在 classic worker 里运行，见 worker.js 头注释）。
// Python 源码由构建期内嵌（js/domains_src.js），运行时零 fetch——
// 避开"预览代理不为 .py 提供静态服务 → 404 文本当 Python 执行"的老坑。

const PYODIDE_VERSION = "314.0.6";
const CDNS = [
  `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/pyodide.mjs`,
  `https://unpkg.com/pyodide@${PYODIDE_VERSION}/pyodide.mjs`,
  `https://cdn.jsdelivr.net/npm/pyodide@${PYODIDE_VERSION}/pyodide.mjs`,
];
const LOCAL_PYODIDE = "../vendor/pyodide/pyodide.mjs";
import { DOMAINS_SRC, VALIDATE_SRC } from "./domains_src.js";

let pyodide = null;

function withTimeout(promise, ms, label) {
  return Promise.race([
    promise,
    new Promise((_, rej) => setTimeout(() => rej(new Error(`${label} 超时 ${ms / 1000}s`)), ms)),
  ]);
}

async function initRuntime() {
  // 本地 vendor 优先（离线可跑、不赌 CDN）；CDN 作为兜底
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
  postMessage({ type: "status", text: "正在加载问题域引擎…" });
  await pyodide.runPythonAsync(DOMAINS_SRC);
  // 标准化数据层：注册为独立模块 validate（引擎在 __main__ 里，validate 通过 _engine() 取到它）
  pyodide.globals.set("_vsrc", VALIDATE_SRC);
  pyodide.runPython(
    "import sys, types\n_vm = types.ModuleType('validate')\nexec(_vsrc, _vm.__dict__)\nsys.modules['validate'] = _vm"
  );
  postMessage({ type: "ready", version: PYODIDE_VERSION });
}

self.onmessage = async (event) => {
  const { cmd, payload } = event.data || {};
  try {
    if (cmd === "init") {
      await initRuntime();
      return;
    }
    if (!pyodide) throw new Error("Pyodide 尚未就绪");

    if (cmd === "list") {
      pyodide.globals.set("_opts", JSON.stringify(payload.opts || {}));
      const out = pyodide.runPython(`domain_list("${payload.domain}", _opts)`);
      postMessage({ type: "list", payload: JSON.parse(out) });
      return;
    }

    if (cmd === "preset") {
      pyodide.globals.set("_seed", payload.seed || 7);
      pyodide.globals.set("_opts", JSON.stringify(payload.opts || {}));
      const out = pyodide.runPython(`domain_preset("${payload.domain}", _seed, _opts)`);
      postMessage({ type: "preset", payload: JSON.parse(out) });
      return;
    }

    if (cmd === "start") {
      const { domain, problem, algo, params } = payload;
      pyodide.globals.set("_dom", domain);
      pyodide.globals.set("_prob", JSON.stringify(problem));
      pyodide.globals.set("_algo", algo);
      pyodide.globals.set("_params", JSON.stringify(params || {}));
      const out = pyodide.runPython(`domain_start(_dom, _prob, _algo, _params)`);
      postMessage({ type: "started", payload: JSON.parse(out) });
      return;
    }

    if (cmd === "validate") {
      // 上传数据校验：读取 + 校验 + 规整 + 引擎试跑（会占用引擎的全局运行态，页面需在空闲时调用）
      pyodide.globals.set("_vtext", payload.text);
      pyodide.globals.set("_vdom", payload.domain);
      pyodide.globals.set("_vvar", payload.variant || null);
      pyodide.globals.set("_vfile", payload.filename || "");
      const out = pyodide.runPython(
        "import json, validate\n" +
          "json.dumps(validate.check_text(_vtext, _vdom, _vfile, True, _vvar) if validate.supported(_vdom) " +
          "else {'unsupported': True}, ensure_ascii=False)"
      );
      postMessage({ type: "validated", payload: JSON.parse(out) });
      return;
    }

    if (cmd === "step") {
      const s = pyodide.runPython("domain_step()");
      if (s === undefined || s === null) {
        postMessage({ type: "done" });
      } else {
        postMessage({ type: "state", payload: JSON.parse(s) });
      }
      return;
    }
  } catch (err) {
    // 混沌走查 P1（2026-09-27 狂飙）：Python Traceback 十几行天书——用户只看得到最后一行结论
    const raw = String(err && err.message ? err.message : err);
    const lines = raw.trim().split("\n").filter(Boolean);
    postMessage({ type: "error", text: lines[lines.length - 1].slice(0, 300) });
  }
};

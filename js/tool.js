// P1 工具组件 v0.4：把「算法演示器」渲染到页面上的 #tool-root
//
// 架构要点（沿用）：
// 1) 工具 UI 完全由 JS 生成 → 6 个页面共用一份代码
// 2) 页面只需 <div id="tool-root">，可选 window.PAGE_ALGO 预选算法
// 3) module 加载 → import.meta.url 自动算站点根路径
// 4) 画布颜色从 CSS 变量实时读取，切主题即重绘
//
// v0.4 交互升级：
// - DPR 感知画布：retina/缩放下线条锐利（旧版在高分屏是糊的）
// - 统计条（代数/采样/最优/基线/优化幅度/耗时）+ 迭代进度条
// - Toast 通知替代裸文本报错；状态胶囊带呼吸灯
// - 键盘快捷键：空格=开始/暂停，S=单步
// - 收敛曲线：坐标轴刻度+数值、最优曲线下方渐变填充
// - 修复 v0.3 bug：draw() 引用了不存在的 cvColor（首帧 ReferenceError，路径动画根本画不出来）
//
// 消息协议（worker.js）：main→worker: init/start/step{k}/run_all
//                        worker→main: status/ready/started/state/done/all_done/error

const BASE = new URL("../", import.meta.url).href;
// 浏览器不满足运行条件（太旧 / 是 file:// 打开的）：原因已由 js/compat.js 写在页面最上方，这里不再启动 worker
if (window.SWARM_COMPAT && !window.SWARM_COMPAT.ok) throw new Error("环境不满足：" + window.SWARM_COMPAT.reason);

const ICONS = {
  play: "▶", pause: "⏸", dice: "⟳", step: "⏭", upload: "↥", img: "🗻", curve: "📈", download: "↧", pkg: "📦",
};

const TOOL_HTML = `
  <div class="panel" id="toolPanel">
    <div class="panel-head"><span class="spin"></span><span id="panelTitle">计算引擎加载中…</span></div>
    <div class="row">
      <div class="field"><label for="algo">算法</label><select id="algo"></select></div>
      <div class="field"><label for="nCities">城市数</label><input id="nCities" type="number" value="40" min="5" max="500"></div>
      <div class="field"><label for="dist">分布</label>
        <select id="dist">
          <option value="random">随机均匀</option>
          <option value="cluster">多簇聚集</option>
          <option value="ring">环形</option>
        </select>
      </div>
      <div class="field"><label for="maxIter">迭代次数</label><input id="maxIter" type="number" value="200" min="1" max="2000"><small class="hint">迭代越高越准也越慢——大城市数 × 高迭代（如 100 城 × 1000 代）可能要等数十秒，浏览器会暂时卡住</small></div>
      <div class="field"><label for="sampleEvery">采样间隔</label>
        <select id="sampleEvery" title="每多少代取一个点画收敛曲线">
          <option value="1" selected>每 1 代</option>
          <option value="2">每 2 代</option>
          <option value="5">每 5 代</option>
          <option value="10">每 10 代</option>
        </select>
      </div>
      <div class="field"><label for="speed">动画速度</label>
        <input id="speed" type="range" min="0" max="120" value="8" title="每批动画间隔（毫秒）">
      </div>
      <div class="field"><label>&nbsp;</label>
        <span id="speedVal" style="font-size:12px;color:var(--sub)">8 ms</span>
      </div>
    </div>

    <div class="params" id="params"></div>

    <div class="row" style="margin-top:14px">
      <button id="btnRun" class="primary" disabled>${ICONS.play} 开始</button>
      <button id="btnStep" disabled>${ICONS.step} 单步 <kbd style="font-size:10px;opacity:.6">S</kbd></button>
      <button id="btnGen" disabled>${ICONS.dice} 换一批城市</button>
      <button id="btnImport" disabled>${ICONS.upload} 导入数据</button>
      <button id="btnExport" disabled class="ghost">${ICONS.img} 路径 PNG</button>
      <button id="btnExportConv" disabled class="ghost">${ICONS.curve} 曲线 PNG</button>
      <button id="btnExportJson" disabled class="ghost">${ICONS.download} 结果 JSON</button>
      <button id="btnExportCsv" disabled class="ghost">${ICONS.download} 数据 CSV</button>
      <button id="btnBundle" disabled class="ghost">${ICONS.pkg} 实验包</button>
      <input id="fileInput" type="file" accept=".json,.csv,.txt,.tsp" hidden>
    </div>

    <div class="progress" id="progress"><div class="progress-bar" id="progressBar"></div></div>
    <div class="hint" id="importHint" style="display:none;margin-top:8px">
      点「换一批城市」回到随机模式。快捷键：<b>空格</b>=开始/暂停，<b>S</b>=单步。
    </div>
    <div class="import-report" id="importReport" role="status" hidden></div>
    <div class="hint" id="importFormats" style="margin-top:8px">
      「导入数据」支持：<b>坐标</b>——JSON <code>[[x,y],…]</code>，或 CSV/TXT 每行 <code>x,y</code>（也可 <code>编号,x,y</code>）；
      <b>TSPLIB</b> <code>.tsp</code>（EUC_2D、CEIL_2D、ATT、GEO、MAN_2D、MAX_2D，以及 EXPLICIT 距离矩阵）；
      <b>对称距离矩阵</b> n×n（JSON 或 CSV）。4–500 个城市。读不懂的文件会明确报错，不会悄悄读错。
      非对称距离（ATSP）暂不支持。<a href="#" id="lnkTspFormats">格式说明</a>
    </div>
  </div>

  <div class="statusline">
    <span class="pill" id="statusPill"><span class="dot"></span><span id="statusText" role="status" aria-live="polite">初始化中…</span></span>
    <span id="statusExtra"></span>
  </div>

  <div class="stats">
    <div class="stat"><div class="k">当前代数</div><div class="v acc" id="stIter">0</div></div>
    <div class="stat"><div class="k">历史最优</div><div class="v" id="stBest">—</div></div>
    <div class="stat"><div class="k">NN 基线</div><div class="v" id="stBase">—</div><div class="s">最近邻参考解</div></div>
    <div class="stat"><div class="k">相对基线优化</div><div class="v good" id="stGain">—</div><div class="s">(NN基线−最优)/NN基线</div></div>
    <div class="stat"><div class="k">采样点</div><div class="v" id="stSamples">0</div><div class="s" id="stSampleEvery">每 1 代取一点</div></div>
    <div class="stat"><div class="k">耗时</div><div class="v" id="stElapsed">0.0s</div></div>
  </div>

  <div class="cols">
    <div>
      <div class="chart-card">
        <div class="chart-head">
          <span class="chart-title">路径进化</span>
          <div class="legend">
            <span><i class="dotm" style="background:var(--cv-tour)"></i>当前最优路径</span>
            <span><i class="dotm" style="background:var(--cv-city)"></i>城市</span>
          </div>
        </div>
        <div class="chart-body"><canvas id="tourCanvas" role="img" aria-label="TSP 路径动画：城市点与当前最优巡回，具体数值见下方统计与导出 JSON" width="760" height="440"></canvas></div>
        <div class="hint">高亮线为当前最优路径。数据仅在你的浏览器本地计算，不上传。</div>
      </div>
    </div>
    <div>
      <div class="chart-card">
        <div class="chart-head">
          <span class="chart-title">收敛曲线</span>
          <div class="legend">
            <span><i style="background:var(--cv-best)"></i>全局最优</span>
            <span><i style="background:var(--cv-cur)"></i>当代成本</span>
            <span><i style="background:var(--cv-ok)"></i>NN 基线</span>
          </div>
        </div>
        <div class="chart-body"><canvas id="convCanvas" role="img" aria-label="收敛曲线：全局最优与当代值随迭代变化，数值可导出 JSON" width="760" height="440"></canvas></div>
        <div class="hint">横轴=代数（采样点按真实代数定位），纵轴=路径长度，越低越好。<b>红线=全局最优，只降不升</b>（历史最优永远保留）；<b>灰线=当代成本</b>，随机算法每代重新探索，会波动甚至回升，这是正常现象——只要红线不升就没丢解。</div>
      </div>
    </div>
  </div>

  <div id="toasts"></div>
`;

const state = {
  ready: false,
  cities: [],
  problem: null, // 导入的实例（原始坐标 / TSPLIB 距离 / 距离矩阵）；null=随机生成的裸坐标
  running: false,
  best: null,
  bestCost: Infinity,
  history: [],
  baseline: null,
  lastExtra: null,
  iteration: 0,
  meta: [],
  elapsed: 0,
  imported: false,
  maxIter: 200,
};

const $ = (id) => document.getElementById(id);
// 混沌走查 P0（2026-09-27 狂飙）：数字输入统一 Number+clamp——NaN/负数/超大值收敛到定义域，
// 顺带修 parseInt("1e9")===1 的静默错读（Number 才按数值解析）
function clampInt(v, lo, hi, dflt) {
  const x = Math.round(Number(v));
  if (!isFinite(x)) return dflt;
  return Math.min(hi, Math.max(lo, x));
}
let worker = new Worker(`${BASE}js/worker.js`, { type: "module" });
let guard = null; // js/run_guard.js：某一步迟迟不返回时给出提示和「强制停止并重载引擎」
let guardMod = null;
const IDLE_NOTE = "算法在浏览器本地运行，数据不上传";

// ---------- 主题感知取色 ----------
const themeCache = {};
function cvColor(name) {
  if (!(name in themeCache)) {
    themeCache[name] =
      getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
  }
  return themeCache[name];
}
function invalidateThemeCache() {
  for (const k of Object.keys(themeCache)) delete themeCache[k];
}

// ---------- Toast ----------
function toast(msg, type = "ok", ms = 3600) {
  const box = document.createElement("div");
  box.className = `toast ${type}`;
  box.innerHTML = `<span class="ticon">${type === "err" ? "⚠️" : "✅"}</span><span></span>`;
  box.lastElementChild.textContent = msg;
  $("toasts").appendChild(box);
  setTimeout(() => {
    box.classList.add("out");
    box.addEventListener("animationend", () => box.remove(), { once: true });
  }, ms);
}

function setStatus(text, kind = "busy") {
  const pill = $("statusPill");
  pill.className = `pill ${kind === "ready" ? "ready" : kind === "err" ? "err" : ""}`;
  $("statusText").textContent = text;
}

// ---------- DPR 感知画布 ----------
function setupCanvas(canvas, logicalW, logicalH) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
  canvas.width = Math.round(logicalW * dpr);
  canvas.height = Math.round(logicalH * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, W: logicalW, H: logicalH };
}
function ctxOf(canvas, logicalW, logicalH) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
  if (canvas.width !== Math.round(logicalW * dpr)) return setupCanvas(canvas, logicalW, logicalH);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, W: logicalW, H: logicalH };
}
const LW = 760, LH = 430;

// ---------- Worker 请求-响应配对 ----------
function call(cmd, payload, onEvent) {
  if (guard) guard.sent();
  return rawCall(cmd, payload, onEvent).finally(() => { if (guard) guard.got(); });
}

function rawCall(cmd, payload, onEvent) {
  return new Promise((resolve, reject) => {
    const listener = (e) => {
      const msg = e.data || {};
      if (msg.type === "error") {
        worker.removeEventListener("message", listener);
        reject(new Error(msg.text));
        return;
      }
      // ★ 坑：'started' 也必须 resolve，否则 await call("start") 永远挂住
      if (msg.type === "state" || msg.type === "all_done" || msg.type === "validated") {
        if (onEvent) onEvent(msg);
        worker.removeEventListener("message", listener);
        resolve(msg);
      } else if (msg.type === "done" || msg.type === "started" || msg.type === "reset_ok") {
        if (onEvent) onEvent(msg);
        worker.removeEventListener("message", listener);
        resolve(msg);
      }
    };
    worker.addEventListener("message", listener);
    worker.postMessage({ cmd, payload });
  });
}

function onWorkerMessage(e) {
  const msg = e.data || {};
  if (msg.type === "status") {
    setStatus(msg.text);
  } else if (msg.type === "ready") {
    state.ready = true;
    state.meta = msg.solvers;
    setStatus(`引擎就绪 · Pyodide ${msg.version}`, "ready");
    $("statusExtra").textContent = IDLE_NOTE;
    $("panelTitle").textContent = "求解控制台";
    $("toolPanel").classList.remove("loading");
    if (!state.restarting) fillSolverSelect(); // 重载引擎后保留用户已选的算法与参数
    state.restarting = false;
    setEnabled(true);
  } else if (msg.type === "error") {
    setStatus(`出错：${msg.text}`, "err");
    toast(msg.text, "err", 6000);
    console.error(msg.text);
  }
}
worker.addEventListener("message", onWorkerMessage);

// 强制停止：worker 里的 Python 是同步执行的，没法温和打断，只能终止 worker 并重新加载引擎（约 5 秒）。
// 实例、已选算法、参数都保留，只是这次运行作废。
function restartEngine() {
  stopRun();
  worker.terminate();
  Object.assign(state, { ready: false, restarting: true, started: false });
  setEnabled(false);
  setStatus("正在重新加载引擎…");
  worker = new Worker(`${BASE}js/worker.js`, { type: "module" });
  worker.addEventListener("message", onWorkerMessage);
  worker.postMessage({ cmd: "init" });
}

// ---------- 算法下拉框 & 动态参数面板 ----------
function fillSolverSelect() {
  renderAlgoSelect();
}

const SKIP_PARAMS = new Set(["seed", "max_iter"]); // 各自有专属输入框，不进动态参数区

function currentMeta() {
  return state.meta.find((s) => s.key === $("algo").value) || null;
}

function renderAlgoSelect() {
  const sel = $("algo");
  sel.innerHTML = "";
  // 按分类分组（optgroup）：分组标签与顺序都来自引擎（py/taxonomy.py ← data/families.json），
  // 前端不自带分类清单——此前这里写死了 6 个名字，家族一改，不在清单里的算法就从下拉框里消失了
  const HIDDEN = new Set(["组合配方（S7）"]); // 配方有各自的页面，不进算法下拉
  const groups = {};
  for (const s of state.meta) {
    const cat = s.category || "其他";
    if (HIDDEN.has(cat)) continue;
    (groups[cat] ||= { rank: s.rank ?? -1, items: [] }).items.push(s);
  }
  const cats = Object.keys(groups).sort((a, b) => groups[a].rank - groups[b].rank); // 稳定排序：同级保持注册顺序
  for (const cat of cats) {
    const og = document.createElement("optgroup");
    og.label = cat;
    for (const s of groups[cat].items) {
      const opt = document.createElement("option");
      opt.value = s.key;
      opt.textContent = s.name + (s.implemented ? "" : "（未实现）");
      opt.disabled = !s.implemented;
      og.appendChild(opt);
    }
    sel.appendChild(og);
  }
  if (window.PAGE_ALGO && state.meta.some((s) => s.key === window.PAGE_ALGO && s.implemented)) {
    sel.value = window.PAGE_ALGO;
  }
  renderParams();
}

function renderParams() {
  const box = $("params");
  box.innerHTML = "";
  const meta = currentMeta();
  if (!meta) return;
  const specs = meta.specs || {};
  const entries = Object.entries(meta.params).filter(([k]) => !SKIP_PARAMS.has(k));
  if (!entries.length) return;

  // 标题行 + 恢复默认按钮
  const head = document.createElement("div");
  head.className = "params-head";
  const tip = document.createElement("span");
  tip.className = "plabel";
  tip.textContent = "算法参数（悬停看说明与定义域）";
  const resetBtn = document.createElement("button");
  resetBtn.type = "button";
  resetBtn.id = "btnResetParams";
  resetBtn.className = "ghost";
  resetBtn.textContent = "↺ 恢复默认";
  resetBtn.title = "把本算法全部参数恢复为默认值";
  resetBtn.onclick = () => {
    for (const [k, v] of Object.entries(meta.params)) {
      const el = document.getElementById("p_" + k);
      if (el) el.value = v;
    }
    if (meta.params.max_iter) $("maxIter").value = meta.params.max_iter;
    toast("已恢复本算法默认参数");
  };
  head.appendChild(tip);
  head.appendChild(resetBtn);
  box.appendChild(head);

  for (const [k, v] of entries) {
    const sp = specs[k] || {};
    const field = document.createElement("div");
    field.className = "field";
    const lab = document.createElement("label");
    lab.textContent = sp.label || k;
    lab.title = sp.desc ? `${sp.desc}（默认 ${v}）` : `默认值 ${v}`;
    field.appendChild(lab);

    if (sp.type === "choice") {
      const sel = document.createElement("select");
      sel.id = "p_" + k;
      sp.options.forEach((optVal, i) => {
        const opt = document.createElement("option");
        opt.value = optVal;
        opt.textContent = (sp.labels && sp.labels[i]) || optVal;
        if (optVal === v) opt.selected = true;
        sel.appendChild(opt);
      });
      field.appendChild(sel);
    } else {
      const inp = document.createElement("input");
      inp.type = "number";
      inp.id = "p_" + k;
      inp.value = v;
      if (sp.min !== undefined) inp.min = sp.min;
      if (sp.max !== undefined) inp.max = sp.max;
      if (sp.step !== undefined) inp.step = sp.step;
      inp.title = sp.desc ? `${sp.desc}（定义域 ${sp.min ?? "-∞"} ~ ${sp.max ?? "+∞"}，默认 ${v}）` : `默认值 ${v}`;
      // 越界即视觉标记，提交前统一钳制
      inp.addEventListener("input", () => {
        const x = parseFloat(inp.value);
        const bad =
          isNaN(x) ||
          (sp.min !== undefined && x < sp.min) ||
          (sp.max !== undefined && x > sp.max);
        inp.classList.toggle("out-of-range", bad);
      });
      inp.addEventListener("blur", () => {
        let x = parseFloat(inp.value);
        if (isNaN(x)) { inp.value = v; return; }
        if (sp.min !== undefined && x < sp.min) inp.value = sp.min;
        if (sp.max !== undefined && x > sp.max) inp.value = sp.max;
        inp.classList.remove("out-of-range");
      });
      field.appendChild(inp);
    }
    box.appendChild(field);
  }
}

function collectParams() {
  const meta = currentMeta();
  const specs = (meta && meta.specs) || {};
  const params = { max_iter: clampInt($("maxIter").value, 1, 2000, 200), seed: 42 };
  // 越界值在提交前统一钳制到定义域（前端最后一道防线）
  for (const inp of document.querySelectorAll("#params input, #params select")) {
    const k = inp.id.slice(2);
    const sp = specs[k] || {};
    if (sp.type === "choice") { params[k] = inp.value; continue; }
    let x = parseFloat(inp.value);
    if (isNaN(x)) { x = meta.params[k]; }
    if (sp.min !== undefined) x = Math.max(sp.min, x);
    if (sp.max !== undefined) x = Math.min(sp.max, x);
    if (sp.int) x = Math.round(x);
    params[k] = x;
  }
  return params;
}

function setEnabled(on) {
  for (const id of ["btnRun", "btnStep", "btnGen", "algo", "nCities", "maxIter", "speed", "dist", "sampleEvery", "btnImport", "btnExport", "btnExportConv", "btnExportJson", "btnExportCsv", "btnBundle"]) {
    const el = $(id);
    if (el) el.disabled = !on;
  }
}

// ---------- 城市生成 ----------
function generateCities(n) {
  const dist = $("dist") ? $("dist").value : "random";
  const W = 700, H = 380;
  const cities = [];
  if (dist === "ring") {
    for (let i = 0; i < n; i++) {
      const t = (2 * Math.PI * i) / n;
      const r = Math.min(W, H) * 0.42;
      cities.push([W / 2 + 40 + r * Math.cos(t), H / 2 + 30 + r * Math.sin(t) + (Math.random() - 0.5) * 12]);
    }
  } else if (dist === "cluster") {
    const k = Math.max(2, Math.round(n / 12));
    const centers = Array.from({ length: k }, () => [80 + Math.random() * (W - 100), 40 + Math.random() * (H - 60)]);
    for (let i = 0; i < n; i++) {
      const c = centers[i % k];
      cities.push([c[0] + (Math.random() - 0.5) * 110, c[1] + (Math.random() - 0.5) * 110]);
    }
  } else {
    for (let i = 0; i < n; i++) cities.push([Math.random() * (W - 20) + 20, Math.random() * (H - 20) + 20]);
  }
  state.imported = false;
  state.problem = null;
  showImportReport({});
  applyCities(cities);
}

function applyCities(cities) {
  Object.assign(state, {
    cities, started: false, history: [], best: null, bestCost: Infinity, baseline: null, lastExtra: null, iteration: 0, elapsed: 0,
  });
  $("progress").classList.remove("on");
  setRunLabel();
  draw();
  drawConvergence();
  updateStats();
}

// ---------- 数据导入 ----------
// 读文件 → worker 里的共享校验器（py/validate.py，与各问题域页同一份）→ 规整后的实例。
// 旧版这里自己逐行「取前两个数」：TSPLIB 的 `1 10.0 20.0` 会被读成 (1,10)，看起来正常、问题却已不是用户的问题。
function showImportReport(res) {
  const el = $("importReport");
  if (!el) return;
  el.textContent = "";
  const items = [...(res.errors || []).map((x) => ["err", x]), ...(res.warnings || []).map((x) => ["warn", x])];
  el.hidden = !items.length;
  for (const [kind, x] of items.slice(0, 30)) {
    const row = document.createElement("div");
    row.className = "ir-" + kind;
    row.textContent = (kind === "err" ? "✗ " : "! ") + (x.path ? x.path + "：" : "") + x.msg;
    el.appendChild(row);
  }
  if (items.length > 30) {
    const more = document.createElement("div");
    more.textContent = `…另有 ${items.length - 30} 条未显示`;
    el.appendChild(more);
  }
}

function normalizeToCanvas(cities, W = 700, H = 380, pad = 34) {
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const [x, y] of cities) {
    if (x < x0) x0 = x; if (x > x1) x1 = x;
    if (y < y0) y0 = y; if (y > y1) y1 = y;
  }
  const sx = (x1 - x0) || 1, sy = (y1 - y0) || 1;
  const scale = Math.min((W - 2 * pad) / sx, (H - 2 * pad) / sy);
  const ox = (W - sx * scale) / 2, oy = (H - sy * scale) / 2;
  return cities.map(([x, y]) => [ox + (x - x0) * scale, oy + (y - y0) * scale]);
}

const METRIC_NOTE = {
  EUC_2D: "TSPLIB 欧氏距离（四舍五入取整）", CEIL_2D: "TSPLIB 欧氏距离（向上取整）", ATT: "TSPLIB 伪欧氏距离（ATT）",
  GEO: "TSPLIB 地理距离（GEO，公里）", MAN_2D: "TSPLIB 曼哈顿距离", MAX_2D: "TSPLIB 切比雪夫距离", matrix: "给定的距离矩阵",
};

async function handleImport(file) {
  try {
    if (file.size > 20 * 1024 * 1024) throw new Error("文件超过 20MB");
    if (!state.ready) throw new Error("引擎还在加载，请稍候再导入");
    stopRun();
    const text = await file.text();
    setStatus("正在校验数据…");
    const msg = await call("validate", { text, filename: file.name });
    const res = msg.payload;
    showImportReport(res);
    if (!res.ok) {
      const e0 = res.errors[0];
      const more = res.errors.length > 1 ? `（另有 ${res.errors.length - 1} 处，见下方）` : "";
      throw new Error(`${e0.path ? e0.path + "：" : ""}${e0.msg}${more}`);
    }
    const prob = res.problem;
    state.imported = true;
    state.problem = prob; // 原样交给引擎（含 metric / matrix）；纯坐标也保留原始尺度，成本不再被画布缩放扭曲
    applyCities(normalizeToCanvas(prob.cities));
    $("importHint").style.display = "block";
    const how = prob.metric ? `，距离：${METRIC_NOTE[prob.metric] || prob.metric}` : "";
    const nw = res.warnings.length ? `（${res.warnings.length} 条提示见下方）` : "";
    setStatus(`已导入 ${prob.cities.length} 个城市（来自 ${file.name}）${how}${nw}`, "ready");
    toast(`已导入 ${prob.cities.length} 个城市，点「开始」求解`);
  } catch (err) {
    setStatus(`导入失败：${err.message}`, "err");
    toast(err.message, "err", 6000);
  }
}

// ---------- 渲染 ----------
function draw() {
  const canvas = $("tourCanvas");
  const { ctx, W, H } = ctxOf(canvas, LW, LH);
  ctx.clearRect(0, 0, W, H);

  // 背景
  ctx.fillStyle = cvColor("--cv-bg");
  ctx.fillRect(0, 0, W, H);

  const cities = state.cities;
  if (!cities.length) return;

  if (state.best && state.best.length > 1) {
    // 构造型算法（NN）构造中：路径未闭合，不画回起点那条边
    const openTour = state.lastExtra && state.lastExtra.open;
    // 最优路径：发光主线
    ctx.strokeStyle = cvColor("--cv-tour");
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.shadowColor = cvColor("--cv-tour");
    ctx.shadowBlur = 6;
    ctx.globalAlpha = 0.9;
    ctx.beginPath();
    const t = state.best;
    ctx.moveTo(cities[t[0]][0], cities[t[0]][1]);
    for (let i = 1; i < t.length; i++) ctx.lineTo(cities[t[i]][0], cities[t[i]][1]);
    if (!openTour) ctx.lineTo(cities[t[0]][0], cities[t[0]][1]);
    ctx.stroke();
    ctx.shadowBlur = 0;
    ctx.globalAlpha = 1;
  }

  // 城市：主题色圆点 + 细描边
  ctx.fillStyle = cvColor("--cv-city");
  for (const [x, y] of cities) {
    ctx.beginPath();
    ctx.arc(x, y, 2.6, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawConvergence() {
  const canvas = $("convCanvas");
  const { ctx, W, H } = ctxOf(canvas, LW, LH);
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = cvColor("--cv-bg");
  ctx.fillRect(0, 0, W, H);

  const h = state.history;
  const padL = 56, padR = 16, padT = 14, padB = 30;
  const plotW = W - padL - padR, plotH = H - padT - padB;

  // 网格背景
  ctx.strokeStyle = cvColor("--cv-grid");
  ctx.lineWidth = 1;

  if (h.length < 2) {
    ctx.fillStyle = cvColor("--cv-sub");
    ctx.font = "13px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("点「开始」后，收敛曲线会画在这里", W / 2, H / 2);
    return;
  }

  const maxIter = Math.max(...h.map((p) => p.iter));
  const vals = h.map((p) => p.best).concat(h.map((p) => p.cur));
  let vmax = Math.max(...vals), vmin = Math.min(...vals);
  if (state.baseline) { vmax = Math.max(vmax, state.baseline); vmin = Math.min(vmin, state.baseline); }
  if (vmax - vmin < 1e-9) { vmax += 1; vmin -= 1; }
  const X = (i) => padL + (i / Math.max(maxIter, 1)) * plotW;
  const Y = (v) => padT + (1 - (v - vmin) / (vmax - vmin)) * plotH;

  // 横向网格 + Y 轴刻度值
  ctx.fillStyle = cvColor("--cv-sub");
  ctx.font = "10.5px ui-monospace, monospace";
  ctx.textAlign = "right";
  ctx.textBaseline = "middle";
  for (let g = 0; g <= 4; g++) {
    const v = vmin + ((vmax - vmin) * g) / 4;
    const y = Y(v);
    ctx.strokeStyle = cvColor("--cv-grid");
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(W - padR, y); ctx.stroke();
    ctx.fillText(v.toFixed(0), padL - 7, y);
  }
  // X 轴刻度
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const stepX = niceStep(maxIter);
  for (let it = 0; it <= maxIter; it += stepX) {
    const x = X(it);
    ctx.strokeStyle = cvColor("--cv-grid");
    ctx.beginPath(); ctx.moveTo(x, padT); ctx.lineTo(x, H - padB); ctx.stroke();
    ctx.fillText(String(it), x, H - padB + 6);
  }

  // 当代成本（细灰线）
  ctx.strokeStyle = cvColor("--cv-cur"); ctx.setLineDash([4, 3]);  // a11y：当代=虚线（色弱可辨）
  ctx.lineWidth = 1;
  ctx.beginPath();
  h.forEach((p, i) => (i ? ctx.lineTo(X(p.iter), Y(p.cur)) : ctx.moveTo(X(p.iter), Y(p.cur))));
  ctx.stroke();

  // 全局最优：渐变填充 + 主线
  const grad = ctx.createLinearGradient(0, padT, 0, H - padB);
  const c = cvColor("--cv-best");
  grad.addColorStop(0, c + "33");
  grad.addColorStop(1, c + "00");
  ctx.beginPath();
  h.forEach((p, i) => (i ? ctx.lineTo(X(p.iter), Y(p.best)) : ctx.moveTo(X(p.iter), Y(p.best))));
  ctx.lineTo(X(h[h.length - 1].iter), H - padB);
  ctx.lineTo(X(h[0].iter), H - padB);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  ctx.strokeStyle = c;
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  ctx.beginPath();
  h.forEach((p, i) => (i ? ctx.lineTo(X(p.iter), Y(p.best)) : ctx.moveTo(X(p.iter), Y(p.best))));
  ctx.stroke();

  // NN 基线
  if (state.baseline) {
    ctx.strokeStyle = cvColor("--cv-ok");
    ctx.setLineDash([5, 4]);
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.moveTo(padL, Y(state.baseline));
    ctx.lineTo(W - padR, Y(state.baseline));
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = cvColor("--cv-ok");
    ctx.font = "10.5px sans-serif";
    ctx.textAlign = "right";
    ctx.textBaseline = "bottom";
    ctx.fillText("NN基线", W - padR, Y(state.baseline) - 3);
  }
}

function niceStep(maxIter) {
  const raw = maxIter / 8;
  const pow = Math.pow(10, Math.floor(Math.log10(Math.max(raw, 1))));
  for (const m of [1, 2, 5, 10]) {
    if (raw <= m * pow) return m * pow;
  }
  return 10 * pow;
}

function updateStats() {
  $("stIter").textContent = state.iteration;
  $("stBest").textContent = state.bestCost === Infinity ? "—" : state.bestCost.toFixed(1);
  $("stBase").textContent = state.baseline ? state.baseline.toFixed(1) : "—";
  $("stGain").textContent = state.baseline && state.bestCost !== Infinity
    ? ((1 - state.bestCost / state.baseline) * 100).toFixed(1) + "%" : "—";
  $("stSamples").textContent = state.history.length;
  $("stSampleEvery").textContent = `每 ${$("sampleEvery").value} 代取一点`;
  $("stElapsed").textContent = state.elapsed.toFixed(1) + "s";
  const pct = state.maxIter ? Math.min(100, (state.iteration / state.maxIter) * 100) : 0;
  $("progressBar").style.width = pct.toFixed(1) + "%";
  $("progress").classList.toggle("on", pct > 0 && pct < 100);
}

// ---------- 运行控制 ----------
// 交给引擎的实例：随机生成的 = 画布坐标；导入的 = 校验器规整后的实例（原始坐标 + TSPLIB 距离 / 距离矩阵）。
// 画布坐标只用来画图（导入时按比例缩放进画布），距离一律按原始数据算。
function engineInstance() {
  return state.problem || state.cities;
}

async function ensureBaseline() {
  if (state.baseline !== null) return;
  await call("start", { cities: engineInstance(), algo: "nn", params: {} });
  await call("step", {}, (msg) => {
    if (msg.type === "state") state.baseline = msg.payload.best_cost;
  });
  updateStats();
}

// 让引擎开始一次新的求解（选中的算法 + 当前参数）。「开始」和「单步」共用：
// 此前「单步」在没点过「开始」时直接去推进最近邻基线的生成器，看到的不是选中的算法。
async function prepareRun() {
  await ensureBaseline();
  state.maxIter = clampInt($("maxIter").value, 1, 2000, 200);
  state._warnedLong = false;
  const runParams = collectParams();
  await call("start", { cities: engineInstance(), algo: $("algo").value, params: runParams });
  state.run = { algo: $("algo").value, algoName: (currentMeta() || {}).name, params: runParams };
  Object.assign(state, { history: [], best: null, bestCost: Infinity, lastExtra: null, iteration: 0, elapsed: 0, started: true });
  state._t0 = performance.now();
}

async function startRun() {
  if (!state.ready || state.running) return;
  if (state.started) {
    state._t0 = performance.now() - state.elapsed * 1000; // 暂停后继续：接着上次的进度跑，耗时也接着算
  } else {
    await prepareRun();
  }
  state.running = true;
  $("btnRun").innerHTML = `${ICONS.pause} 暂停`;
  $("btnRun").classList.remove("primary");
  pump();
}

// 按钮文字：有可接着跑的运行（暂停过 / 单步过）时叫「继续」，否则叫「开始」
function setRunLabel() {
  if (state.running) return;
  $("btnRun").innerHTML = `${ICONS.play} ${state.started ? "继续" : "开始"}`;
}

function stopRun() {
  state.running = false;
  $("statusExtra").textContent = IDLE_NOTE;
  setRunLabel();
  $("btnRun").classList.add("primary");
  updateStats();
}

function pump() {
  if (!state.running) return;
  const delay = parseInt($("speed").value, 10);
  // a11y（听见 2026-09-27）：动效敏感用户降帧——每帧至少推进 10 代，重绘频率降 90%
  const k = matchMedia("(prefers-reduced-motion: reduce)").matches
    ? Math.max(10, parseInt($("sampleEvery").value, 10))
    : parseInt($("sampleEvery").value, 10);
  call("step", { k }, (msg) => {
    if (msg.type === "state") onState(msg.payload);
    else if (msg.type === "done") { state.started = false; stopRun(); }
  })
    .then(() => {
      if (state.running) setTimeout(pump, delay);
    })
    .catch((e) => {
      stopRun();
      setStatus("出错：" + e.message, "err");
      toast(e.message, "err", 6000);
    });
}

function onState(p) {
  state.iteration = p.iteration;
  state.lastExtra = p.extra || null;
  if (Array.isArray(p.points)) {
    for (const [it, best, cur] of p.points) state.history.push({ iter: it, best, cur });
  }
  // 构造型算法构造中（extra.open）：路径逐城生长，即使成本相同也要刷新画面
  const constructing = p.extra && p.extra.open;
  if (p.best_cost <= state.bestCost || constructing) {
    state.bestCost = p.best_cost;
    state.best = p.best_tour;
  }
  state.elapsed = (performance.now() - state._t0) / 1000;
  draw();
  drawConvergence();
  updateStats();
  if (guardMod && state.running && !p.exhausted) { // 暂停后才到的最后一批回包不再刷新估时
    const eta = guardMod.etaText(state.iteration, state.maxIter, state.elapsed);
    if (eta) $("statusExtra").textContent = eta;
    const total = guardMod.projectedTotal(state.iteration, state.maxIter, state.elapsed);
    if (!state._warnedLong && total > guardMod.LONG_RUN_SEC) {
      state._warnedLong = true;
      toast(`按当前速度，这次运行约需 ${guardMod.fmtDuration(total)}。可以随时点「暂停」；想快一点就减少迭代次数或换更快的算法。`, "ok", 9000);
    }
  }
  if (p.exhausted) {
    state.started = false;
    stopRun();
    toast(`求解完成：${$("algo").value.toUpperCase()} · ${state.cities.length} 城市 · 最优 ${state.bestCost.toFixed(1)}`);
  }
}

async function singleStep() {
  if (!state.ready || state.running) return;
  if (!state.started) await prepareRun();
  await call("step", { k: 1 }, (msg) => {
    if (msg.type === "state") onState(msg.payload);
  });
}

function downloadCanvas(canvas, name) {
  const a = document.createElement("a");
  a.download = name;
  a.href = canvas.toDataURL("image/png");
  a.click();
}

function exportPNG() {
  downloadCanvas($("tourCanvas"), `tsp-${$("algo").value}-n${state.cities.length}-${state.iteration}.png`);
  toast("路径图已导出");
}

function exportConv() {
  downloadCanvas($("convCanvas"), `tsp-conv-${$("algo").value}-n${state.cities.length}-${state.iteration}.png`);
  toast("收敛曲线已导出");
}

// 结果导出：swarm-result/v1（与命令行 `swarm.py solve --out` 同一格式，可用 `swarm.py replay` 回读复现）。
// 里面带完整实例（原始坐标 / TSPLIB 距离 / 距离矩阵）、运行时的算法参数、逐代曲线与最优路径。
async function exportJSON() {
  if (!state.run || !state.history.length) return toast("还没有运行结果可导出：先点「开始」跑一次", "err");
  const R = await import(BASE + "js/result_export.js");
  const run = state.run;
  const res = R.buildResult({
    domain: "tsp",
    algo: run.algo,
    algoName: run.algoName,
    seed: run.params.seed,
    iters: run.params.max_iter,
    completedIters: state.iteration,
    params: R.algoParams(run.params),
    sense: "min",
    best: state.bestCost === Infinity ? null : state.bestCost,
    bestSolution: state.best || [],
    elapsed: state.elapsed,
    curve: state.history.map((h) => [h.iter, h.best]),
    problem: state.problem || { cities: state.cities },
    extra: { nn_baseline: state.baseline, imported: !!state.imported },
  });
  R.downloadJson(res, `tsp-${run.algo}-n${state.cities.length}-result.json`);
  toast("结果已导出（swarm-result/v1，可用 python swarm.py replay 复现）");
}

function exportCsv() {
  if (!state.history.length) { toast("尚无迭代数据可导出"); return; }
  const lines = [
    `# domain=tsp algo=${$("algo").value} n=${state.cities.length} maxIter=${$("maxIter").value} dist=${$("dist").value ? $("dist").selectedOptions[0].text : ""}`,
    `# exportedAt=${new Date().toISOString()}`,
    "iter,best,cur",
  ];
  for (const h of state.history) lines.push(`${h.iter},${h.best},${h.cur}`);
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `tsp-${$("algo").value}-history-n${state.cities.length}-${Date.now()}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  toast("迭代历史已导出（CSV）");
}

// 实验包导出（2026-09-27 用户需求「数据和算法一键打包」）：单 JSON 文件 =
// 实例 + 参数 + 迭代历史 + 结果 + 完整算法源码（py/solvers.py 全文）+ 复跑说明。
// 算法源码懒加载 js/solvers_src.js（构建期生成，与 worker 共用同一份产物）。
let bundleSrcLoading = false;
function exportBundle() {
  const doExport = (src) => {
    const params = {};
    for (const id of ["nCities", "maxIter", "speed", "dist", "sampleEvery"]) {
      const el = $(id);
      if (el) params[id] = el.value;
    }
    const readme = [
      "# TSP 实验包（群智能算法百科）",
      "",
      "## 内容",
      "- instance.cities: 城市坐标 [[x,y],...]；导入 TSPLIB / 距离矩阵时还有 instance.metric（距离类型）与 instance.matrix（距离矩阵）",
      "- params: 本次运行的界面参数（城市数/迭代/速度/距离/采样间隔）",
      "- algo: 算法键（对应 algo_source 里 SOLVERS 注册表键，如 pso/sa/lk/ga…）",
      "- algo_keys: algo_source 内全部可用算法键（想跑别的算法直接换 start 的第二个参数）",
      "- history: 逐代 [代数, 全局最优, 当代值]",
      "- bestTour / bestCost: 最优路径与长度",
      "- algo_source: 完整 Python 源码（py/solvers.py，单文件、纯标准库，无 numpy 依赖）",
      "",
      "## 复跑方法（Python 3.8+，无需安装任何包）",
      "1. 把 algo_source 字段内容存为 solvers.py",
      "2. python 交互运行（用 algo_keys 里的任意键替换算法名）：",
      "   import json, solvers",
      "   inst = <instance>            # 本包 instance 字段（含 cities，以及 metric / matrix 如果有）",
      "   solvers.start(json.dumps(inst), \"" + ($("algo").value) + "\", json.dumps({\"max_iter\": 200, \"seed\": 42}))",
      "   print(solvers.step())        # 每调用一次推进一代，返回 JSON",
      "",
      "## 语言说明",
      "本站全部算法内核为 Python 3 源码（浏览器内经 Pyodide 运行）；导出即可脱离浏览器直接离线复跑。",
    ].join("\n");
    const payload = {
      format: "tsp-experiment-bundle/v1",
      exportedAt: new Date().toISOString(),
      algo: $("algo").value,
      params,
      instance: Object.assign({ n: state.cities.length }, state.problem || { cities: state.cities }),
      iteration: state.iteration,
      bestCost: state.bestCost === Infinity ? null : state.bestCost,
      nnBaseline: state.baseline,
      bestTour: state.best || [],
      history: state.history.map((h) => [h.iter, h.best, h.cur]),
      readme,
      algo_source: src,
    };
    const blob = new Blob([JSON.stringify(payload, null, 1)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `tsp-bundle-${$("algo").value}-n${state.cities.length}-${state.iteration}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
    toast("实验包已导出（数据 + 算法源码 + 复跑说明）");
  };
  if (bundleSrcLoading) return toast("算法源码加载中，请稍候…");
  bundleSrcLoading = true;
  toast("正在打包算法源码…");
  // 必须用 BASE（站根）：demo/index.html 的页面基址是 demo/，相对路径会 404
  import(BASE + "js/solvers_src.js")
    .then((m) => { bundleSrcLoading = false; doExport(m.SOLVERS_SRC || ""); })
    .catch(() => { bundleSrcLoading = false; toast("算法源码加载失败，仅导出数据部分"); doExport(""); });
}

// ---------- 主题切换 ----------
window.addEventListener("themechange", () => {
  invalidateThemeCache();
  draw();
  drawConvergence();
});

// ---------- 快捷键 ----------
document.addEventListener("keydown", (e) => {
  if (["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)) return;
  if (e.code === "Space") {
    e.preventDefault();
    if (state.ready) (state.running ? stopRun() : startRun());
  } else if (e.key === "s" || e.key === "S") {
    if (state.ready && !state.running) singleStep();
  }
});

// ---------- 速度滑块数值显示 ----------
function syncSpeedLabel() {
  const el = $("speed");
  const pct = ((el.value - el.min) / (el.max - el.min)) * 100;
  el.style.setProperty("--fill", pct + "%");
  $("speedVal").textContent = `${el.value} ms`;
}

// ---------- 挂载 ----------
function mount() {
  const root = document.getElementById("tool-root");
  if (!root) return;
  root.innerHTML = TOOL_HTML;
  setEnabled(false);
  $("toolPanel").classList.add("loading");
  syncSpeedLabel();
  $("lnkTspFormats").href = BASE + "docs/data-formats.md";
  setupCanvas($("tourCanvas"), LW, LH);
  setupCanvas($("convCanvas"), LW, LH);
  generateCities(clampInt($("nCities").value, 5, 500, 30));

  $("algo").onchange = () => {
    state.started = false;
    stopRun();
    renderParams();
  };
  // 改了参数 / 迭代次数：之前暂停的那次运行不再对应当前设置，单步应当重新开始
  $("params").addEventListener("change", () => { state.started = false; setRunLabel(); });
  $("maxIter").addEventListener("change", () => { state.started = false; setRunLabel(); });
  $("dist").onchange = () => {
    stopRun();
    generateCities(clampInt($("nCities").value, 5, 500, 30));
  };
  $("nCities").onchange = () => {
    stopRun();
    generateCities(clampInt($("nCities").value, 5, 500, 30));
  };
  $("btnGen").onclick = () => {
    stopRun();
    $("importHint").style.display = "none";
    generateCities(clampInt($("nCities").value, 5, 500, 30));
    toast("已生成新的城市分布");
  };
  $("btnRun").onclick = () => (state.running ? stopRun() : startRun());
  $("btnStep").onclick = () => singleStep();
  $("btnImport").onclick = () => $("fileInput").click();
  $("fileInput").onchange = (e) => {
    const f = e.target.files[0];
    if (f) handleImport(f);
    e.target.value = "";
  };
  $("btnExport").onclick = () => exportPNG();
  $("btnExportConv").onclick = () => exportConv();
  $("btnExportJson").onclick = () => exportJSON();
  $("btnExportCsv").onclick = () => exportCsv();
  $("btnBundle").onclick = () => exportBundle();
  $("speed").oninput = syncSpeedLabel;
  $("sampleEvery").onchange = () => updateStats();

  window.addEventListener("resize", () => {
    draw();
    drawConvergence();
  });

  worker.postMessage({ cmd: "init" });
  import(BASE + "js/run_guard.js").then((m) => {
    guardMod = m;
    guard = m.createGuard({ anchor: document.querySelector(".statusline"), onRestart: restartEngine });
  }).catch(() => {});
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", mount);
} else {
  mount();
}

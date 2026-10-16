// v0.9 问题域演示页共享引擎（背包 / 连续函数 / 多目标）
// 由各页面在加载前设置 window.PAGE_DOMAIN / PAGE_PRESETS。
// 结构与 tool.js 同构：worker 推流 state，本文件负责 UI 渲染与动画节拍。
// P2 切域协议：URL 带 ?algo=<域内key>（或 window.PAGE_ALGO）时，落地自动选中并开跑；
// 参数非法时静默降级为普通演示页（行为与旧版一致）。

const DOMAIN = window.PAGE_DOMAIN;
// 站根 URL 由本脚本自身的位置推出（<站根>/js/domain_page.js）：无论页面几层深、站点挂在域名根还是子路径
// （如 GitHub Pages 的 /仓库名/）都正确，不依赖页面写死的前缀
const PREFIX = new URL("../", document.currentScript.src).href;
const PRESELECT = (() => {
  try {
    return new URLSearchParams(window.location.search).get("algo") || window.PAGE_ALGO || "";
  } catch (e) {
    return window.PAGE_ALGO || "";
  }
})();
let preselectApplied = false;
let autoStarted = false;

const $ = (id) => document.getElementById(id);
const cvColor = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";

let worker = null;
let onValidatedHook = null; // 导入校验回包的处理函数（在控件接线处赋值）
let ready = false;
let problem = null; // 预置实例
let info = null; // start 后返回的域信息
let algoMeta = [];
let defaults = window.PAGE_DEFAULTS || {}; // 修2：构建期静态注入默认参数，Pyodide 未就绪时 tune 也有值可看
let running = false;
let timer = null;
let history = [];
let runRecord = null; // 实例、算法和参数的运行快照，各类导出共用
let runParams = null; // 最近一次 start 用的参数（导出结果时记录运行时的值，而不是导出瞬间输入框里的值）
let lastState = null;
let maxIter = 200;
// 步进的「背压」：每个定时节拍最多让 perTick 个 step 在 worker 里排队，等回包再补。
// 旧做法是无条件每 16ms 发 perTick 个——某一代很慢（大实例）时队列越堆越长，点「暂停」后 worker 还要把队列里的几十步算完。
let inflight = 0; // 已发出、还没回包的 step 数
let staleSteps = 0; // 上一次运行遗留的 step 回包数（新运行开始时它们还会陆续回来，要丢掉）
let runT0 = 0;
let runElapsed = 0; // 暂停那一刻已经跑了多久（毫秒）
let warnedLong = false;
let restarting = false;
let listVariant = null; // 当前算法下拉对应哪个变体（自带问题按编码分派算法集）
let keepProblemOnList = false; // 只是为了换算法集而重取 list：不要用预置实例覆盖用户刚载入的问题
let runActive = false; // 有一次可以接着跑的运行（暂停后点「开始」应继续，而不是重新开始）
let guard = null; // js/run_guard.js：某一步迟迟不返回时给出提示和「强制停止并重载引擎」
let guardMod = null;
let themeCache = {};

function cvc(name) {
  const v = cvColor(name);
  themeCache[name] = v;
  return v;
}

function setStatus(text, state) {
  $("statusText").textContent = text;
  const pill = $("statusPill");
  pill.dataset.state = state || "";
}

// ---------------- worker 通信 ----------------

function boot() {
  if (window.SWARM_COMPAT && !window.SWARM_COMPAT.ok) { // 原因已由 compat.js 写在页面最上方
    setStatus("当前环境无法运行在线演示：见页面上方说明", "err");
    return;
  }
  worker = new Worker(PREFIX + "js/domain_worker.js", { type: "module" });
  worker.onmessage = (e) => {
    const { type, payload, text } = e.data || {};
    if (type === "status") return setStatus(text, "busy");
    if (type === "ready") {
      ready = true;
      if (restarting) { // 强制停止后重载引擎：实例、算法、参数都保留，不重新取预置
        restarting = false;
        setStatus("引擎已重新加载，实例和设置保持不变——可以重新开始", "ok");
        return;
      }
      setStatus("就绪", "ok");
      // H1 kpvar：算法集按变体分派，list 需带当前预置的 opts（其余域忽略 opts）
      const opts = currentOpts();
      post("list", { domain: DOMAIN, opts });
      return;
    }
    if (type === "list") {
      algoMeta = payload.algos;
      defaults = payload.defaults;
      buildAlgoSelect();
      if (keepProblemOnList) { keepProblemOnList = false; return; }
      listVariant = currentOpts().variant || null;
      loadPreset();
      return;
    }
    if (type === "preset") {
      problem = payload;
      runActive = false;
      customFill();
      drawConv();
      customEnsureAlgos(payload.variant); // 自带问题：换了编码，算法集要跟着换
      drawPreset();
      // P2 切域：链接带合法 algo 参数时，实例就绪后自动开跑（仅首次，重置后不触发）
      if (preselectApplied && !autoStarted && !running) {
        autoStarted = true;
        startRun();
      }
      return;
    }
    if (type === "started") {
      info = payload;
      history = [];
      lastState = null;
      runT0 = performance.now();
      warnedLong = false;
      runActive = true;
      customStarted(payload);
      onStarted();
      if (singleMode) { // 单步模式（2026-09-28 补齐）：start 后不自动连跑，立即推进一代
        singleMode = false;
        setStatus("单步推进中…", "busy");
        postStep();
      } else {
        setStatus("运行中…", "busy");
        startTimer();
      }
      return;
    }
    if (type === "state") {
      if (stepReply()) onState(payload);
      return;
    }
    if (type === "done") {
      if (!stepReply()) return;
      runActive = false;
      stopTimer();
      setStatus(`完成：第 ${history.length ? history[history.length - 1].iter : 0} 代`, "ok");
      return;
    }
    if (type === "validated") return onValidatedHook && onValidatedHook(payload);
    if (type === "error") {
      inflight = 0;
      staleSteps = 0;
      if (guard) guard.reset();
      stopTimer();
      setStatus("出错：" + text, "err");
    }
  };
  worker.onerror = (e) => setStatus(
    "引擎启动失败：" + (e.message || "浏览器没能启动后台计算线程（可能版本太旧，或不是通过 http 打开的）") +
    "。需要 Chrome / Edge 111+、Firefox 114+、Safari 16.4+，并且要通过 http 访问（不能双击打开本地文件）", "err");
  post("init");
}

function post(cmd, payload) {
  worker.postMessage({ cmd, payload });
}

function postStep() {
  inflight++;
  if (guard) guard.sent();
  post("step");
}

// 返回 false 表示这是上一次运行遗留的回包，调用方应丢弃
function stepReply() {
  if (staleSteps > 0) {
    staleSteps--;
    return false;
  }
  inflight = Math.max(0, inflight - 1);
  if (guard) guard.got();
  return true;
}

// 强制停止：worker 里的 Python 是同步执行的，没法温和打断，只能终止 worker 并重新加载引擎（约 5 秒）
function restartEngine() {
  stopTimer();
  inflight = 0;
  staleSteps = 0;
  ready = false;
  restarting = true;
  if (guard) guard.reset();
  worker.terminate();
  setStatus("正在重新加载引擎…", "busy");
  boot();
}

// ---------------- 控件 ----------------

function buildAlgoSelect() {
  const sel = $("algoSel");
  // 回访走查 P1（2026-09-27 回声）：静态注入后用户可能在 Pyodide 就绪前已选好算法，
  // list 回包重建时不得把用户选择吞掉——先记住再恢复
  const prev = sel.value;
  sel.innerHTML = "";
  const byCat = {};
  for (const a of algoMeta) (byCat[a.category] = byCat[a.category] || []).push(a);
  for (const cat of Object.keys(byCat)) {
    const og = document.createElement("optgroup");
    og.label = cat;
    for (const a of byCat[cat]) {
      const op = document.createElement("option");
      op.value = a.key;
      op.textContent = a.name;
      op.dataset.tune = JSON.stringify(a.tune || []);
      og.appendChild(op);
    }
    sel.appendChild(og);
  }
  if (prev && [...sel.options].some((o) => o.value === prev)) sel.value = prev;
  sel.onchange = renderTune;
  renderTune();
  applyPreselect();
}

// P2 切域：URL ?algo= / PAGE_ALGO 预选算法；合法才生效，非法静默降级
function applyPreselect() {
  if (preselectApplied || !PRESELECT) return;
  const sel = $("algoSel");
  if (![...sel.options].some((o) => o.value === PRESELECT)) return;
  preselectApplied = true;
  sel.value = PRESELECT;
  renderTune();
  setStatus("已按链接预选算法：" + PRESELECT, "ok");
}

function renderTune() {
  const sel = $("algoSel");
  const op = sel.selectedOptions[0];
  const tune = op ? JSON.parse(op.dataset.tune) : [];
  const box = $("tuneBox");
  box.innerHTML = "";
  for (const name of tune) {
    const def = defaults[name];
    if (def === undefined) continue;
    const f = document.createElement("div");
    f.className = "field";
    f.innerHTML = `<label for="tune_${name}">${name}</label><input id="tune_${name}" type="number" value="${def}" step="any">`;
    box.appendChild(f);
  }
  $("iterInp").value = defaults.max_iter || 200;
}

// 自定义规模：__custom 选中时以基准预设为底（提供 variant 等分派键），输入框覆盖规模键
function currentOpts() {
  if (!window.PAGE_PRESETS) return {};
  const sel = $("presetSel");
  if (!sel) return {};
  if (sel.value === "__custom") {
    const baseKey = window.PAGE_CUSTOM_BASE || Object.keys(window.PAGE_PRESETS)[0];
    const opts = Object.assign({}, window.PAGE_PRESETS[baseKey] || {});
    for (const f of (window.PAGE_CUSTOM_FIELDS || [])) {
      const inp = document.getElementById("cst_" + f.key);
      if (inp && inp.value !== "" && isFinite(inp.value)) {
        // 混沌走查 P0（2026-09-27 狂飙）：范围钳制到字段配置的 min/max——
        // HTML 属性拦不住手输负数/超大值，Python 端 int() 只挡类型不挡范围
        let x = (f.step && f.step < 1) ? parseFloat(inp.value) : parseInt(inp.value, 10);
        if (f.min !== undefined) x = Math.max(f.min, x);
        if (f.max !== undefined) x = Math.min(f.max, x);
        opts[f.key] = x;
      }
    }
    return opts;
  }
  return window.PAGE_PRESETS[sel.value] || {};
}

function loadPreset() {
  runActive = false;
  stopTimer();
  staleSteps += inflight;
  inflight = 0;
  if (guard) guard.reset();
  history = [];
  lastState = null;
  runParams = null;
  runRecord = null;
  info = null;
  problem = null;
  const opts = currentOpts();
  post("preset", { domain: DOMAIN, seed: Number($("seedInp").value) || 7, opts: opts || {} });
}

function currentParams() {
  // max_iter 硬上限（2026-09-27 工具链走查 P2）：误填超大值会令 worker 长时间阻塞
  const it = Math.min(2000, Math.max(1, Number($("iterInp").value) || 200));
  const params = { max_iter: it, seed: Number($("seedInp").value) || 7 };
  for (const inp of $("tuneBox").querySelectorAll("input")) {
    params[inp.id.replace("tune_", "")] = Number(inp.value);
  }
  return params;
}

function startRun() {
  if (!ready || !problem) return;
  stopTimer();
  curAlgo = $("algoSel").value;
  staleSteps += inflight; // 上一次运行还在排队的 step，回包时要丢掉
  inflight = 0;
  if (guard) guard.reset();
  history = [];
  lastState = null;
  maxIter = Math.min(2000, Math.max(1, Number($("iterInp").value) || 200));
  runParams = currentParams();
  runRecord = JSON.parse(JSON.stringify({ problem, algo: curAlgo, params: runParams,
    algoName: (algoMeta.find((a) => a.key === curAlgo) || {}).name || curAlgo }));
  post("start", { domain: DOMAIN, problem: runRecord.problem, algo: curAlgo, params: runParams });
}

function stopTimer() {
  if (running) runElapsed = performance.now() - runT0;
  running = false;
  if (timer) clearInterval(timer);
  timer = null;
}

function startTimer() {
  running = true;
  const perTick = Number($("speedSel").value) || 2;
  timer = setInterval(() => {
    if (!running) return;
    while (inflight < perTick) postStep();
  }, 16);
}

// ---------------- 状态流 ----------------

// 多目标性能指标：超体积 HV（2D/3D，纯前端实时计算，不改 worker 协议）
// 最大化语义：HV = 被前沿支配、且以参考点为下界的目标空间体积。
// 参考点 = 前沿包围盒 nadir（各目标最小值）外扩 10%（更差方向）。
// 维度扫描法（slicing）对任意维数精确；d=1 为基例，d>=2 按末维切片递归。
function hypervolume(points, ref) {
  const d = ref.length;
  if (!points.length) return 0;
  if (d === 1) {
    let m = -Infinity;
    for (const p of points) m = Math.max(m, p[0]);
    return Math.max(0, m - ref[0]);
  }
  const sp = points.slice().sort((a, b) => b[d - 1] - a[d - 1]); // 末维降序
  let total = 0;
  for (let i = 0; i < sp.length; i++) {
    const proj = sp.slice(0, i + 1).map((q) => q.slice(0, d - 1));
    const v = hypervolume(proj, ref.slice(0, d - 1));
    const nextF = (i + 1 < sp.length) ? sp[i + 1][d - 1] : ref[d - 1];
    const thickness = sp[i][d - 1] - nextF;
    if (thickness > 0 && v > 0) total += thickness * v;
  }
  return total;
}

function updateMO(front) {
  const elHV = document.getElementById("moHV");
  const elND = document.getElementById("moND");
  const elRef = document.getElementById("moRef");
  if (!elHV) return;
  if (!front || !front.length) {
    elHV.textContent = "—"; elND.textContent = "—"; elRef.textContent = "—";
    return;
  }
  const d = front[0].length;
  const mins = new Array(d).fill(Infinity), maxs = new Array(d).fill(-Infinity);
  for (const p of front) {
    for (let j = 0; j < d; j++) {
      mins[j] = Math.min(mins[j], p[j]);
      maxs[j] = Math.max(maxs[j], p[j]);
    }
  }
  const ref = mins.map((m, j) => {
    const range = maxs[j] - mins[j];
    return range > 1e-9 ? m - 0.1 * range : m - Math.abs(m) * 0.1 - 1e-6;
  });
  const hv = hypervolume(front, ref);
  elHV.textContent = (d === 3 ? "HV(3D) = " : "HV(2D) = ") + hv.toFixed(2);
  elND.textContent = String(front.length);
  elRef.textContent = "[" + ref.map((r) => r.toFixed(0)).join(", ") + "]";
}

function onState(s) {
  lastState = s;
  history.push({ iter: s.iter, best: s.best, cur: s.cur !== undefined ? s.cur : null });
  try { drawViz(s); } catch (err) { console.error("drawViz:", err); }
  try { drawConv(); } catch (err) { console.error("drawConv:", err); }
  try { if (DOMAIN === "multiobj" && s.front) updateMO(s.front); } catch (err) { console.error("updateMO:", err); }
  try { if (DOMAIN === "mocont") updateMOC(s); } catch (err) { console.error("updateMOC:", err); }
  if (DOMAIN === "custom" && s.eval_errors) {
    $("statusExtra").textContent = "目标函数在 " + s.eval_errors + " 次评价里出错（如：" + s.first_error + "），这些解被当作极差的解";
  }
  const pct = Math.round((s.iter / maxIter) * 100);
  if (s.iter % 5 === 0 || s.iter === maxIter) {
    const elapsed = (performance.now() - runT0) / 1000;
    const eta = guardMod && s.iter < maxIter ? guardMod.etaText(s.iter, maxIter, elapsed) : "";
    setStatus(`运行中 ${pct}% · 第 ${s.iter} 代` + (eta ? " · " + eta : ""), "busy");
    const total = guardMod ? guardMod.projectedTotal(s.iter, maxIter, elapsed) : 0;
    if (guard && !warnedLong && total > guardMod.LONG_RUN_SEC) {
      warnedLong = true;
      guard.notice(`按当前速度，这次运行约需 ${guardMod.fmtDuration(total)}。可以随时点「暂停」；想快一点就减少迭代次数，或换更快的算法（如模拟退火、爬山）。`);
    }
  }
}

// ---------------- 收敛曲线 ----------------

function drawConv() {
  const cv = $("convCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);

  if (history.length < 2) return;
  // 纵轴以「全局最优」曲线的量级为准：当代值只画到最优跨度的 4 倍以内，更远的（罚项悬崖上的尖峰）截断在边缘——
  // 否则一个 6 万的罚值尖峰会把真正在下降的最优曲线压成贴底的一条直线
  let bLo = Infinity, bHi = -Infinity, cLo = Infinity, cHi = -Infinity;
  for (const h of history) {
    bLo = Math.min(bLo, h.best); bHi = Math.max(bHi, h.best);
    cLo = Math.min(cLo, h.cur ?? h.best); cHi = Math.max(cHi, h.cur ?? h.best);
  }
  // 最优曲线开头常有一段罚项（还没找到可行解时是 4000 这种量级）：它和后面真正的下降差几个数量级，把整条曲线压扁。
  // 只在落差悬殊（> 20 倍）时，把纵轴上沿定在「跑过 15% 之后」的最优值附近，开头那段截断在上沿。
  const k15 = history[Math.floor(history.length * 0.15)].best;
  const lateSpan = Math.max(k15 - bLo, Math.abs(k15) * 0.05, 1e-9);
  const headClipped = bHi - k15 > 20 * lateSpan;
  if (headClipped) bHi = k15 + 4 * lateSpan;
  const span = Math.max(bHi - bLo, Math.abs(bHi) * 0.05, 1e-9);
  let lo = Math.max(bLo - 4 * span, Math.min(bLo, cLo));
  let hi = Math.min(bHi + 4 * span, Math.max(bHi, cHi));
  const clipped = headClipped || cHi > hi + 1e-9 || cLo < lo - 1e-9;
  if (hi - lo < 1e-9) { hi += 1; lo -= 1; }
  const pad = 30;
  const X = (it) => pad + (it / maxIter) * (W - pad - 10);
  const Y = (v) => H - 24 - ((v - lo) / (hi - lo)) * (H - pad - 24);

  // 网格
  ctx.strokeStyle = cvc("--cv-grid");
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const y = 24 + (i / 4) * (H - pad - 24) + (pad - 24) * 0;
    ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(W - 10, y); ctx.stroke();
  }
  // 端点数值
  ctx.fillStyle = cvc("--cv-sub");
  ctx.font = "11px sans-serif";
  ctx.fillText(fmt(lo), 2, Y(lo) + 4);
  ctx.fillText(fmt(hi), 2, Y(hi) + 4);

  const line = (key, color, width) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.beginPath();
    let started = false;
    for (const h of history) {
      const v = h[key];
      if (v == null) continue;
      const x = X(h.iter), y = Y(Math.min(hi, Math.max(lo, v)));
      if (!started) { ctx.moveTo(x, y); started = true; } else ctx.lineTo(x, y);
    }
    ctx.stroke();
  };
  line("cur", cvc("--cv-cur"), 1);
  line("best", cvc("--cv-best"), 2);
  if (clipped) {
    ctx.fillStyle = cvc("--cv-sub");
    ctx.font = "10px sans-serif";
    ctx.textAlign = "right";
    ctx.fillText(headClipped ? "开头的罚值（尚无可行解）与超出范围的当代值已截断" : "灰线（当代值）超出范围的部分已截断", W - 12, 14);
    ctx.textAlign = "left";
  }
}

function fmt(v) {
  if (v == null) return "";
  if (Math.abs(v) >= 1000) return v.toFixed(0);
  if (Math.abs(v) >= 10) return v.toFixed(1);
  return v.toFixed(3);
}

// ---------------- 域一：背包绘制 ----------------

function drawPreset() {
  if (DOMAIN === "knapsack") drawKS(null);
  else if (DOMAIN === "continuous") drawHeat();
  else if (DOMAIN === "graphcolor") drawGC(null);
  else if (DOMAIN === "binpack") drawBP(null);
  else if (DOMAIN === "setcover") drawSC(null);
  else if (DOMAIN === "sat") drawSAT(null);
  else if (DOMAIN === "qubo") drawQB(null);
  else if (DOMAIN === "gap") drawGAP(null);
  else if (DOMAIN === "uflp") drawUF(null);
  else if (DOMAIN === "kpvar" || DOMAIN === "entryseq") drawKPVAR(null); // entryseq 的绘制代码在 drawKPVAR 里；此前没有路由到它，词条页的画布一直是空的
  else if (DOMAIN === "gcvar") drawGCVAR(null);
  else if (DOMAIN === "bpvar") drawBPVAR(null);
  else if (DOMAIN === "nrp") drawNRP(null);
  else if (DOMAIN === "etp") drawETP(null);
  else if (DOMAIN === "ttp") drawTTP(null);
  else if (DOMAIN === "sls") drawSLS(null);
  else if (DOMAIN === "custom") drawCustom(null);
  else if (DOMAIN === "mocont") { drawMOC(null); updateMOC(null); }
  else drawMO(null);
}

// ---------------- 排程域四绘制（2026-09-29 完善战役 + 同日架构待议项正名） ----------------
// 底部指标为 py/scheduling.py obj 的 JS 镜像（FN_JS 同款铁律：镜像必须与引擎一致，
// 偏离=展示假数据）。NRP 缺口/偏好/连班、ETP 冲突/相邻/容量、TTP 旅行/对阵/连场/重复、
// SLS 主客/连场/对阵/焦点均已对齐。正名：引擎键 ttp=旅行锦标赛（tour），etp=考试时间表。

function drawNRP(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!problem) return;

  const N = problem.N, D = problem.D, S = problem.S, OFF = problem.OFF;
  const sol = state ? state.best_sol : null;
  const pad = 14, top = 32;
  const cw = (W - pad * 2) / D, ch = (H - top - pad * 2) / N;

  let gap = 0, prefV = 0, consecN = 0;
  const gapCols = new Array(D).fill(0);
  if (sol) {
    const cnt = [];
    for (let d = 0; d < D; d++) cnt.push(new Array(problem.nshifts).fill(0));
    for (let n = 0; n < N; n++) for (let d = 0; d < D; d++) cnt[d][sol[n * D + d]]++;
    for (let d = 0; d < D; d++) for (let k = 0; k < S; k++) {
      const g = Math.max(0, problem.req[d][k] - cnt[d][k]);
      gap += g; gapCols[d] += g;
    }
    for (let n = 0; n < N; n++) for (let d = 0; d < D; d++) {
      const p = problem.pref[n][d];
      if (p >= 0 && sol[n * D + d] !== p) prefV++;
    }
    for (let n = 0; n < N; n++) {
      let run = 0;
      for (let d = 0; d < D; d++) {
        if (sol[n * D + d] !== OFF) { run++; if (run > 5) consecN++; } else run = 0;
      }
    }
  }
  for (let n = 0; n < N; n++) {
    for (let d = 0; d < D; d++) {
      const x = pad + d * cw, y = top + n * ch;
      const k = sol ? sol[n * D + d] : null;
      if (k == null) { ctx.fillStyle = cvc("--cv-grid"); ctx.globalAlpha = 0.22; }
      else if (k === OFF) { ctx.fillStyle = cvc("--cv-grid"); ctx.globalAlpha = 0.35; }
      else { ctx.fillStyle = gcPalette(k); ctx.globalAlpha = 0.9; }
      ctx.fillRect(x + 0.5, y + 0.5, Math.max(1, cw - 1.5), Math.max(1, ch - 1.5));
      ctx.globalAlpha = 1;
    }
  }
  if (sol) for (let d = 0; d < D; d++) if (gapCols[d] > 0) {
    ctx.fillStyle = "rgba(220,60,60,.95)";
    ctx.fillRect(pad + d * cw + 1, top - 7, Math.max(1, cw - 2), 4);
  }
  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "12px sans-serif";
  if (sol) ctx.fillText(`护士 ${N} × ${D} 天 × ${S} 班 · 覆盖缺口 ${gap}（硬，列顶红条）· 偏好违约 ${prefV} · 连班>5天 ${consecN} 处`, pad, 18);
  else ctx.fillText(`排班网格：行=护士 列=天。点「开始」后块色=班次（灰=休息），列顶红条=该日有班次覆盖缺口。当前 ${N}×${D}×${S}`, pad, 18);
}

function drawETP(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!problem) return;

  const E = problem.E, T = problem.T, rooms = problem.rooms;
  const sol = state ? state.best_sol : null;
  const pad = 14, top = 32;
  const rowH = (H - top - pad * 2) / T;
  const slots = [];
  for (let t = 0; t < T; t++) slots.push([]);
  let conf = 0, adj = 0, cap = 0;
  if (sol) {
    for (let e = 0; e < E; e++) slots[sol[e]].push(e);
    for (const st of problem.students) {
      if (st.length === 2) {
        if (sol[st[0]] === sol[st[1]]) conf++;
        else if (Math.abs(sol[st[0]] - sol[st[1]]) === 1) adj++;
      }
    }
    for (let t = 0; t < T; t++) cap += Math.max(0, slots[t].length - rooms);
  }
  const bw = Math.min(26, (W - pad * 2 - 70) / Math.max(rooms, 2) - 2);
  for (let t = 0; t < T; t++) {
    const y = top + t * rowH;
    ctx.fillStyle = cvc("--cv-sub");
    ctx.font = "10px sans-serif";
    if (rowH >= 11) ctx.fillText(`时段 ${t + 1}`, pad, y + rowH / 2 + 3);
    for (let i = 0; i < slots[t].length; i++) {
      const x = pad + 62 + i * (bw + 2);
      const over = i >= rooms;
      ctx.fillStyle = over ? "rgba(220,60,60,.9)" : gcPalette(t);
      ctx.fillRect(x, y + 1.5, Math.max(2, bw), Math.max(2, rowH - 5));
      if (bw >= 21 && rowH >= 15) {
        ctx.fillStyle = over ? "#fff" : (document.documentElement.getAttribute("data-theme") === "dark" ? "#111" : "#fff");
        ctx.font = "9px sans-serif";
        ctx.fillText(String(slots[t][i] + 1), x + 2, y + rowH / 2 + 3);
      }
    }
    // 教室容量线：超过 rooms 的块转红
    ctx.strokeStyle = cvc("--cv-ok");
    ctx.setLineDash([3, 3]);
    const lx = pad + 62 + rooms * (bw + 2) - 3;
    ctx.beginPath(); ctx.moveTo(lx, y + 1); ctx.lineTo(lx, y + rowH - 1); ctx.stroke();
    ctx.setLineDash([]);
  }
  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "12px sans-serif";
  if (sol) ctx.fillText(`${E} 场考试 → ${T} 时段 · 同时段冲突 ${conf}（硬）· 相邻时段同学生 ${adj} · 容量超 ${cap}（红块，绿虚线=教室数 ${rooms}）`, pad, 18);
  else ctx.fillText(`时段条：每行=一个时段，绿虚线=教室容量。点「开始」后块=考试（红=超容量），目标=零冲突（T≥χ 保证可达）。当前 ${E} 场 ${T} 时段`, pad, 18);
}

function drawTTP(state) {
  // 旅行锦标赛（2026-09-29 新域 tour）：上半=主城点图（含队 0 巡回路线），下半=轮次网格。
  // 指标=引擎 _TOUR.obj 的 JS 镜像：总旅行 / 对阵偏差 Σ|c-2| / 连主连客>3 / 相邻轮重复对阵。
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!problem) return;

  const m = problem.m, R = problem.R, g = problem.g, per = problem.per;
  const pts = problem.pts || [], dist = problem.dist || [];
  const sol = state ? state.best_sol : null;
  const pad = 14, top = 32;

  // 展开轮次：rounds[r] = [{h,a}, ...]
  const rounds = [];
  for (let r = 0; r < R; r++) {
    const base = r * per, arr = [];
    for (let i = 0; i < g; i++) arr.push({ h: sol ? sol[base + 2 * i] : null, a: sol ? sol[base + 2 * i + 1] : null });
    rounds.push(arr);
  }

  // —— 指标镜像（与引擎 _TOUR.obj 逐项对齐）——
  let travel = 0, pairDev = 0, streakN = 0, repeatN = 0;
  if (sol) {
    const venue = [], oppo = [];
    for (let t = 0; t < m; t++) { venue.push(new Array(R).fill(-1)); oppo.push(new Array(R).fill(-1)); }
    const paircnt = {};
    for (let r = 0; r < R; r++) for (const gm of rounds[r]) {
      const key = gm.h < gm.a ? gm.h + "," + gm.a : gm.a + "," + gm.h;
      paircnt[key] = (paircnt[key] || 0) + 1;
      venue[gm.h][r] = 0; venue[gm.a][r] = 1;
      oppo[gm.h][r] = gm.a; oppo[gm.a][r] = gm.h;
    }
    for (let a = 0; a < m; a++) for (let b = a + 1; b < m; b++) {
      const key = a + "," + b;
      pairDev += Math.abs((paircnt[key] || 0) - 2);
    }
    for (let t = 0; t < m; t++) {
      let cur = t;
      for (let r = 0; r < R; r++) {
        const nxt = venue[t][r] === 0 ? cur : oppo[t][r];
        travel += dist[cur][nxt];
        cur = nxt;
      }
      travel += dist[cur][t];
    }
    for (let t = 0; t < m; t++) {
      let run = 1;
      for (let r = 1; r < R; r++) {
        if (venue[t][r] === venue[t][r - 1]) { run++; if (run > 3) streakN++; } else run = 1;
      }
    }
    for (let r = 0; r < R - 1; r++) {
      const seen = new Set(rounds[r].map(gm => gm.h < gm.a ? gm.h + "," + gm.a : gm.a + "," + gm.h));
      for (const gm of rounds[r + 1]) {
        const k1 = gm.h + "," + gm.a, k2 = gm.a + "," + gm.h;
        if (seen.has(k1) || seen.has(k2)) repeatN++;
      }
    }
  }

  // —— 上半：主城点图 + 队 0 巡回 ——
  const mapH = Math.min(H * 0.42, 190), mapW = Math.min(W * 0.42, 300);
  const mx = pad + 4, my = top + 6, sc = Math.min(mapW / 100, (mapH - 16) / 100);
  ctx.strokeStyle = cvc("--cv-grid");
  ctx.strokeRect(mx, my, 100 * sc, 100 * sc);
  if (sol && dist.length) {
    ctx.strokeStyle = "rgba(200,140,30,.55)";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    let cur = 0;
    for (let r = 0; r < R; r++) {
      const gm = rounds[r].find(x => x.h === 0 || x.a === 0);
      if (!gm) continue;
      const nxt = gm.h === 0 ? 0 : gm.a;
      ctx.moveTo(mx + pts[cur][0] * sc, my + pts[cur][1] * sc);
      ctx.lineTo(mx + pts[nxt][0] * sc, my + pts[nxt][1] * sc);
      cur = nxt;
    }
    ctx.lineTo(mx + pts[0][0] * sc, my + pts[0][1] * sc);
    ctx.stroke();
    ctx.lineWidth = 1;
  }
  for (let t = 0; t < m; t++) {
    const x = mx + pts[t][0] * sc, y = my + pts[t][1] * sc;
    ctx.fillStyle = gcPalette(t % 8);
    ctx.beginPath(); ctx.arc(x, y, 5, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = document.documentElement.getAttribute("data-theme") === "dark" ? "#111" : "#fff";
    ctx.font = "8px sans-serif";
    if (t + 1 < 10) ctx.fillText(String(t + 1), x - 2.5, y + 3);
    else { ctx.font = "7px sans-serif"; ctx.fillText(String(t + 1), x - 4, y + 2.5); }
  }
  ctx.fillStyle = cvc("--cv-sub");
  ctx.font = "10px sans-serif";
  ctx.fillText("球队主城（橙线=队 1 巡回）", mx, my + 100 * sc + 12);

  // —— 下半：轮次网格 ——
  const gy = my + 100 * sc + 22;
  const cw = (W - pad * 2) / R, chh = (H - gy - pad - 6) / g;
  for (let r = 0; r < R; r++) {
    const prevSet = r > 0 ? new Set(rounds[r - 1].map(gm => gm.h < gm.a ? gm.h + "," + gm.a : gm.a + "," + gm.h)) : null;
    for (let i = 0; i < g; i++) {
      const x = pad + r * cw, y = gy + i * chh;
      const gm = rounds[r][i];
      const rep = sol && prevSet && prevSet.has(gm.h < gm.a ? gm.h + "," + gm.a : gm.a + "," + gm.h);
      if (!sol) {
        ctx.fillStyle = cvc("--cv-grid"); ctx.globalAlpha = 0.22;
        ctx.fillRect(x + 1, y + 1, Math.max(1, cw - 2), Math.max(1, chh - 2));
        ctx.globalAlpha = 1;
        continue;
      }
      const half = (cw - 4) / 2, hh = Math.max(2, chh - 3);
      ctx.fillStyle = gcPalette(gm.h % 8);
      ctx.fillRect(x + 1.5, y + 1, half, hh);
      ctx.strokeStyle = gcPalette(gm.a % 8);
      ctx.lineWidth = 1.5;
      ctx.strokeRect(x + 1.5 + half, y + 1, half, hh);
      ctx.lineWidth = 1;
      if (rep) { ctx.strokeStyle = "rgba(220,60,60,.95)"; ctx.lineWidth = 2; ctx.strokeRect(x + 0.5, y + 0.5, cw - 1, chh - 1); ctx.lineWidth = 1; }
    }
    ctx.fillStyle = cvc("--cv-sub");
    ctx.font = "9px sans-serif";
    if (cw >= 22) ctx.fillText(String(r + 1), pad + r * cw + cw / 2 - 3, gy - 3);
  }
  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "12px sans-serif";
  if (sol) ctx.fillText(`${m} 队双循环 ${R} 轮 · 总旅行 ${travel} · 对阵偏差 ${pairDev}（主导）· 连主连客>3 ${streakN} · 重复对阵 ${repeatN}（红框）`, pad, 18);
  else ctx.fillText(`赛程×地理：上半=主城点图（撒点即实例），下半=轮次表（左实块=主队 右描边=客队）。点「开始」后红框=重复对阵。当前 ${m} 队 ${R} 轮`, pad, 18);
}

function drawSLS(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!problem) return;

  const m = problem.m, R = problem.R, per = problem.per, g = problem.g;
  const marquee = new Set(problem.marquee);
  const sol = state ? state.best_sol : null;
  const pad = 14, top = 32;
  const cw = (W - pad * 2 - 52) / per;
  const ch = Math.min(24, (H - top - pad * 2) / R);

  let haDev = 0, consecN = 0, pairDev = 0, focusN = 0;
  if (sol) {
    const home = new Array(m).fill(0), away = new Array(m).fill(0);
    const venue = [];
    for (let t = 0; t < m; t++) venue.push(new Array(R).fill(-1));
    const pairCnt = {};
    for (let r = 0; r < R; r++) {
      const inround = new Set();
      for (let i = 0; i < g; i++) {
        const h = sol[r * per + 2 * i], a = sol[r * per + 2 * i + 1];
        home[h]++; away[a]++;
        venue[h][r] = 0; venue[a][r] = 1;
        const key = (h < a ? h + "-" + a : a + "-" + h);
        pairCnt[key] = (pairCnt[key] || 0) + 1;
        if (marquee.has(h) && marquee.has(a)) inround.add(h < a ? h + "-" + a : a + "-" + h);
      }
      if (inround.size >= 2) focusN += inround.size - 1;
    }
    for (let t = 0; t < m; t++) haDev += Math.abs(home[t] - away[t]);
    for (let t = 0; t < m; t++) {
      let run = 1;
      for (let r = 1; r < R; r++) {
        if (venue[t][r] === venue[t][r - 1] && venue[t][r] !== -1) { run++; if (run > 2) consecN++; }
        else run = 1;
      }
    }
    for (let a = 0; a < m; a++) for (let b = a + 1; b < m; b++) {
      const key = a + "-" + b;
      pairDev += Math.abs((pairCnt[key] || 0) - 2);
    }
  }
  for (let r = 0; r < R; r++) {
    const y = top + r * ch;
    ctx.fillStyle = cvc("--cv-sub");
    ctx.font = "9px sans-serif";
    if (ch >= 10 && R <= 20) ctx.fillText(`R${r + 1}`, pad, y + ch / 2 + 3);
    for (let i = 0; i < per; i++) {
      const x = pad + 52 + i * (cw + 1);
      const team = sol ? sol[r * per + i] : null;
      const isHome = i % 2 === 0;
      if (team == null) { ctx.fillStyle = cvc("--cv-grid"); ctx.globalAlpha = 0.22; }
      else if (isHome) { ctx.fillStyle = gcPalette(team); ctx.globalAlpha = 0.9; }
      else { ctx.fillStyle = gcPalette(team); ctx.globalAlpha = 0.28; }
      ctx.fillRect(x, y + 0.5, Math.max(1, cw - 1), Math.max(1, ch - 1.5));
      ctx.globalAlpha = 1;
      if (team != null && marquee.has(team)) {
        ctx.strokeStyle = "rgba(205,150,20,.95)";
        ctx.lineWidth = 1.2;
        ctx.strokeRect(x + 0.5, y + 1, Math.max(1, cw - 2), Math.max(1, ch - 2.5));
        ctx.lineWidth = 1;
      }
    }
  }
  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "12px sans-serif";
  if (sol) ctx.fillText(`${m} 队 ${R} 轮（实块=主 浅块=客 金圈=焦点队）· 主客偏差 ${haDev} · 连主连客 ${consecN} · 对阵偏差 ${pairDev}（主导）· 焦点扎堆 ${focusN}`, pad, 18);
  else ctx.fillText(`轮次表：每行=一轮，每轮 ${per} 格=主客交替对阵。点「开始」后色=队号。目标全软：主客平衡/少连场/每对恰遇 2 次/焦点战分散。当前 ${m} 队 ${R} 轮`, pad, 18);
}

// ---------------- 域一：背包绘制 ----------------

function drawKS(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!problem) return;

  const items = problem.items;
  const n = items.length;
  const sol = state ? state.best_sol : null;
  const pad = 26;
  const bw = (W - pad * 2) / n;
  const vmax = Math.max(...items.map((it) => it[1]));
  const selected = sol ? sol.reduce((a, b) => a + b, 0) : 0;

  for (let i = 0; i < n; i++) {
    const h = (items[i][1] / vmax) * (H - pad * 2 - 30);
    const x = pad + i * bw, y = H - pad - 26 - h;
    const on = sol && sol[i];
    ctx.fillStyle = on ? cvc("--cv-best") : cvc("--cv-grid");
    ctx.fillRect(x + 0.5, y, Math.max(1, bw - 2), h);
  }
  // 底部：当前最优的重量占比
  if (state && sol) {
    let w = 0;
    for (let i = 0; i < n; i++) if (sol[i]) w += items[i][0];
    const frac = Math.min(1, w / problem.cap);
    ctx.fillStyle = cvc("--cv-ok");
    ctx.fillRect(pad, H - 18, (W - pad * 2) * frac, 8);
    ctx.strokeStyle = cvc("--cv-sub");
    ctx.strokeRect(pad + 0.5, H - 18.5, W - pad * 2, 9);
    ctx.fillStyle = cvc("--cv-ink");
    ctx.font = "11px sans-serif";
    ctx.fillText(`选中 ${selected}/${n} 件 · 重量 ${w}/${problem.cap}`, pad, H - 24);
  } else {
    ctx.fillStyle = cvc("--cv-sub");
    ctx.font = "12px sans-serif";
    ctx.fillText(`每根柱子 = 一件物品（高度=价值）。点「开始」后红色 = 被选入背包。共 ${n} 件，容量 ${problem.cap}`, pad, H - 24);
  }
}

// ---------------- 域二：连续函数绘制 ----------------

const FN_JS = {
  sphere: (x, y) => x * x + y * y,
  rosenbrock: (x, y) => 100 * (y - x * x) ** 2 + (1 - x) ** 2,
  rastrigin: (x, y) => 20 + x * x - 10 * Math.cos(2 * Math.PI * x) + y * y - 10 * Math.cos(2 * Math.PI * y),
  ackley: (x, y) => -20 * Math.exp(-0.2 * Math.sqrt((x * x + y * y) / 2)) - Math.exp((Math.cos(2 * Math.PI * x) + Math.cos(2 * Math.PI * y)) / 2) + 20 + Math.E,
  // BBOB 基准镜像（H3 期，d=2 切片；必须与 py/domains.py FUNCS 一一对应——
  // 教训：ee884fc 补过一次被后续提交覆盖，画布静默回退 sphere=展示错误数据）
  bbob_f1: (x, y) => x * x + y * y,
  bbob_f2: (x, y) => x * x + 1e6 * y * y,          // 椭球（d=2 时与 f3 数值同形）
  bbob_f3: (x, y) => x * x + 1e6 * y * y,          // 雪茄 Bent Cigar
  bbob_f4: (x, y) => 1e6 * x * x + y * y,          // 铁饼 Discus
  bbob_f5: (x, y) => x * x + Math.pow(Math.abs(y), 6), // 异次幂 Different Powers（d=2: 2+4·i/(d-1)）
  bbob_f6: (x, y) => x * x + 100 * Math.abs(y),    // 尖脊 Sharp Ridge
  // 2026-10 补充的经典基准（d=2 切片，必须与 py/domains.py 的 _fn_* 一致；tests/test_continuous_functions.py 用 node 逐点对照）
  griewank: (x, y) => 1 + (x * x + y * y) / 4000 - Math.cos(x) * Math.cos(y / Math.SQRT2),
  levy: (x, y) => {
    const w1 = 1 + (x - 1) / 4, w2 = 1 + (y - 1) / 4;
    return Math.sin(Math.PI * w1) ** 2 + (w1 - 1) ** 2 * (1 + 10 * Math.sin(Math.PI * w1 + 1) ** 2)
      + (w2 - 1) ** 2 * (1 + Math.sin(2 * Math.PI * w2) ** 2);
  },
  schwefel: (x, y) => 2 * 418.9828872724338 - x * Math.sin(Math.sqrt(Math.abs(x))) - y * Math.sin(Math.sqrt(Math.abs(y))),
  zakharov: (x, y) => { const s = 0.5 * x + y; return x * x + y * y + s ** 2 + s ** 4; },
  dixon_price: (x, y) => (x - 1) ** 2 + 2 * (2 * y * y - x) ** 2,
  styblinski_tang: (x, y) => 0.5 * (x ** 4 - 16 * x * x + 5 * x + y ** 4 - 16 * y * y + 5 * y) + 2 * 39.16616570377142,
};

let heatImg = null;

function drawHeat() {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  if (!problem) { ctx.clearRect(0, 0, W, H); return; }

  if (!heatImg) {
    // 预渲染地形热力图（JS 侧镜像 Python 公式；2D 切片）
    const f = FN_JS[problem.fn] || FN_JS.sphere; // 缺镜像时回退通用碗形（不冻结画布）
    const lo = problem.lo, hi = problem.hi;
    const gw = 120, gh = Math.round(120 * (H / W));
    const off = document.createElement("canvas");
    off.width = gw; off.height = gh;
    const octx = off.getContext("2d");
    const img = octx.createImageData(gw, gh);
    const vals = new Float64Array(gw * gh);
    let vlo = Infinity, vhi = -Infinity;
    for (let gy = 0; gy < gh; gy++) {
      for (let gx = 0; gx < gw; gx++) {
        const x = lo + (gx / (gw - 1)) * (hi - lo);
        const y = hi - (gy / (gh - 1)) * (hi - lo);
        const v = f(x, y);
        vals[gy * gw + gx] = v;
        if (v < vlo) vlo = v;
        if (v > vhi) vhi = v;
      }
    }
    const light = document.documentElement.getAttribute("data-theme") !== "dark";
    for (let i = 0; i < gw * gh; i++) {
      const t = Math.pow((vals[i] - vlo) / (vhi - vlo || 1), 0.35); // 0=谷底 1=山峰
      const base = light ? 255 : 22;
      const k = light ? 1 : 0.35;
      const c = Math.round(base * (1 - t * k * 0.85));
      img.data[i * 4] = c; img.data[i * 4 + 1] = c; img.data[i * 4 + 2] = Math.round(c * (light ? 1 : 1.15)); img.data[i * 4 + 3] = 255;
    }
    octx.putImageData(img, 0, 0);
    heatImg = { canvas: off, lo, hi };
  }
  ctx.imageSmoothingEnabled = true;
  ctx.drawImage(heatImg.canvas, 0, 0, W, H);
  // 高维切片标注（2026-09-27 工具链走查 P2）：10D/30D 实例的热力图只是 x₁x₂ 平面切片，
  // 其余维置 0——不标注会被误读为真实高维景观
  if (problem.dim && problem.dim > 2) {
    ctx.fillStyle = "rgba(128,128,128,.92)";
    ctx.font = "12px system-ui, sans-serif";
    ctx.fillText(`此图为 x₁x₂ 平面切片（${problem.dim}D 实例，其余维=0）`, 8, H - 8);
  }
  drawParticles(ctx, W, H);
}

function drawParticles(ctx, W, H) {
  if (!lastState || !info) return;
  const lo = info.lo, hi = info.hi;
  const X = (x) => ((x - lo) / (hi - lo)) * W;
  const Y = (y) => H - ((y - lo) / (hi - lo)) * H;
  // 粒子
  ctx.fillStyle = cvc("--cv-cur");
  for (const p of lastState.particles) {
    ctx.beginPath();
    ctx.arc(X(p[0]), Y(p[1]), 3, 0, Math.PI * 2);
    ctx.fill();
  }
  // 全局最优
  const g = lastState.gbest_pos;
  ctx.strokeStyle = cvc("--cv-best");
  ctx.lineWidth = 2;
  ctx.beginPath();
  const gx = X(g[0]), gy = Y(g[1]);
  ctx.moveTo(gx - 6, gy); ctx.lineTo(gx + 6, gy);
  ctx.moveTo(gx, gy - 6); ctx.lineTo(gx, gy + 6);
  ctx.stroke();
}

// ---------------- 域三：多目标绘制 ----------------

let moBounds = null;

function drawMO(state) {
  // H3 期：三目标（maop, sense=max3）走 drawMO3；双目标走原 2D 散点
  const is3 = (state && state.pop && state.pop[0] && state.pop[0].length === 3) ||
              (problem && problem.sense === "max3");
  if (is3) { drawMO3(state); return; }
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!state && !moBounds) {
    ctx.fillStyle = cvc("--cv-sub");
    ctx.font = "12px sans-serif";
    ctx.fillText("横轴 = 目标1 收益，纵轴 = 目标2 收益（右上角更好）。点「开始」后：灰点=种群，红点=Pareto 前沿。", 14, 24);
    return;
  }
  if (!state) return;
  // 动态 bounds（单调扩张，避免抖动）
  if (!moBounds) moBounds = { x0: 0, y0: 0, x1: 1, y1: 1 };
  for (const p of state.pop) {
    moBounds.x1 = Math.max(moBounds.x1, p[0]);
    moBounds.y1 = Math.max(moBounds.y1, p[1]);
  }
  const { x0, y0, x1, y1 } = moBounds;
  const pad = 34;
  const X = (v) => pad + ((v - x0) / (x1 - x0 || 1)) * (W - pad - 12);
  const Y = (v) => H - 26 - ((v - y0) / (y1 - y0 || 1)) * (H - pad - 26);

  // 轴
  ctx.strokeStyle = cvc("--cv-grid");
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad, 12); ctx.lineTo(pad, H - 26); ctx.lineTo(W - 12, H - 26);
  ctx.stroke();
  ctx.fillStyle = cvc("--cv-sub");
  ctx.font = "11px sans-serif";
  ctx.fillText("目标1 →", W - 62, H - 10);
  ctx.save();
  ctx.translate(12, 74);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("目标2 →", 0, 0);
  ctx.restore();

  // 种群（灰）
  ctx.fillStyle = cvc("--cv-cur");
  for (const p of state.pop) {
    ctx.beginPath();
    ctx.arc(X(p[0]), Y(p[1]), 3, 0, Math.PI * 2);
    ctx.fill();
  }
  // 前沿（红，按目标1排序连线）
  ctx.strokeStyle = cvc("--cv-best");
  ctx.fillStyle = cvc("--cv-best");
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  state.front.forEach((p, i) => {
    const x = X(p[0]), y = Y(p[1]);
    if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
  });
  ctx.stroke();
  for (const p of state.front) {
    ctx.beginPath();
    ctx.arc(X(p[0]), Y(p[1]), 3.5, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "12px sans-serif";
  ctx.fillText(`非支配解数：${state.nd}`, pad + 6, 20);
}

// ---------------- 三目标绘制（H3 期 maop：many-objective 入门） ----------------
// 在双目标 2D 散点基础上加「第 3 目标用色相编码」，前沿点排序连线——入门级三目标可视，
// 不追求真 3D 投影。坐标取自 state.pop/front 的前两维，第 3 维仅着色。
let mo3Bounds = null;

function drawMO3(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!state && !mo3Bounds) {
    ctx.fillStyle = cvc("--cv-sub");
    ctx.font = "12px sans-serif";
    ctx.fillText("三目标：横轴=目标1，纵轴=目标2，点色=目标3 收益（蓝低→红高）。灰点=种群，红点=Pareto 前沿。点「开始」。", 14, 24);
    return;
  }
  if (!state) return;
  if (!mo3Bounds) mo3Bounds = { x0: 0, y0: 0, x1: 1, y1: 1, z0: 0, z1: 1 };
  for (const p of state.pop) {
    mo3Bounds.x1 = Math.max(mo3Bounds.x1, p[0]);
    mo3Bounds.y1 = Math.max(mo3Bounds.y1, p[1]);
    mo3Bounds.z1 = Math.max(mo3Bounds.z1, p[2]);
  }
  const { x0, y0, x1, y1, z0, z1 } = mo3Bounds;
  const pad = 34;
  const X = v => pad + ((v - x0) / ((x1 - x0) || 1)) * (W - pad - 12);
  const Y = v => H - 26 - ((v - y0) / ((y1 - y0) || 1)) * (H - pad - 26);
  const col = z => `hsl(${(1 - (z - z0) / ((z1 - z0) || 1)) * 220}, 70%, 55%)`;
  // 轴
  ctx.strokeStyle = cvc("--cv-grid");
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad, 12); ctx.lineTo(pad, H - 26); ctx.lineTo(W - 12, H - 26);
  ctx.stroke();
  ctx.fillStyle = cvc("--cv-sub");
  ctx.font = "11px sans-serif";
  ctx.fillText("目标1 →", W - 62, H - 10);
  ctx.save();
  ctx.translate(12, 74);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("目标2 →", 0, 0);
  ctx.restore();
  // 种群（按目标3 着色）
  for (const p of state.pop) {
    ctx.fillStyle = col(p[2]);
    ctx.globalAlpha = 0.7;
    ctx.beginPath();
    ctx.arc(X(p[0]), Y(p[1]), 3, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
  // 前沿（红，按目标1 降序连线 + 描点）
  ctx.strokeStyle = cvc("--cv-best");
  ctx.fillStyle = cvc("--cv-best");
  ctx.lineWidth = 1.5;
  const fr = state.front.slice().sort((a, b) => b[0] - a[0]);
  ctx.beginPath();
  fr.forEach((p, i) => { const x = X(p[0]), y = Y(p[1]); if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); });
  ctx.stroke();
  for (const p of fr) {
    ctx.beginPath();
    ctx.arc(X(p[0]), Y(p[1]), 4.5, 0, Math.PI * 2);
    ctx.stroke(); // 空心描边圈：形状编码与色带解耦（色盲可辨）
  }
  // 第三目标 colorbar：右侧竖向渐变条 + 上下端数值
  const cbW = 10, cbX = W - 32, cbY = 40, cbH = H - cbY - 46;
  const grad = ctx.createLinearGradient(0, cbY + cbH, 0, cbY);
  for (let i = 0; i <= 8; i++) grad.addColorStop(i / 8, col(z0 + (i / 8) * (z1 - z0)));
  ctx.globalAlpha = 1;
  ctx.fillStyle = grad;
  ctx.fillRect(cbX, cbY, cbW, cbH);
  ctx.strokeStyle = cvc("--cv-grid");
  ctx.lineWidth = 1;
  ctx.strokeRect(cbX, cbY, cbW, cbH);
  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "10px sans-serif";
  ctx.fillText(z1.toFixed(1), cbX + cbW + 3, cbY + 8);
  ctx.fillText(z0.toFixed(1), cbX + cbW + 3, cbY + cbH);
  ctx.font = "12px sans-serif";
  ctx.fillText(`非支配解数：${state.nd}（点色=目标3 蓝低→黄高；空心圈=Pareto 前沿）`, pad + 6, 20);
}

// ---------------- 连续多目标基准（ZDT / DTLZ）：目标全部「越小越好」，有解析真前沿 ----------------
// 视窗固定在「真前沿 → 参考点」这一块：早期种群的目标值可能是几十几百（ZDT4 / DTLZ1），画出来只会把真前沿压成一条线。
// 视窗外的点只计数，不画——随着收敛，数字会降到 0。三目标用斜投影（x + 0.5z, y + 0.35z），点色 = 目标3。
function mocWindow() {
  const front = (info && info.front) || [], ref = (info && info.ref) || [1.1, 1.1];
  const m = ref.length;
  const lo = new Array(m).fill(0), hi = ref.slice();
  for (let d = 0; d < m; d++) {
    let mn = Infinity;
    for (const p of front) mn = Math.min(mn, p[d]);
    if (isFinite(mn)) lo[d] = Math.min(0, mn - 0.05);
  }
  return { lo, hi, m };
}

function drawMOC(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!info || !info.front) {
    ctx.fillStyle = cvc("--cv-sub");
    ctx.font = "12px sans-serif";
    ctx.fillText("点「开始」：虚线 = 解析真前沿（目标越小越好，越靠近左下越好），灰点 = 种群，红点 = 当前非支配解。", 14, 24);
    return;
  }
  const { lo, hi, m } = mocWindow();
  const pad = 34, top = 28, right = 12, bottom = 26;
  const oblique = m === 3;
  // 斜投影：把第三维折进二维平面
  const nrm = (p, d) => (p[d] - lo[d]) / ((hi[d] - lo[d]) || 1);  // 三个目标量级可以差很多（DTLZ7 的 f3 到 6）：按视窗归一化后再投影
  const proj = (p) => oblique ? [nrm(p, 0) + 0.5 * nrm(p, 2), nrm(p, 1) + 0.35 * nrm(p, 2)] : [p[0], p[1]];
  const corners = oblique ? [lo, hi].flatMap((a) => [lo, hi].flatMap((b) => [lo, hi].map((c) => proj([a[0], b[1], c[2]])))) : [proj(lo), proj(hi)];
  const x0 = Math.min(...corners.map((c) => c[0])), x1 = Math.max(...corners.map((c) => c[0]));
  const y0 = Math.min(...corners.map((c) => c[1])), y1 = Math.max(...corners.map((c) => c[1]));
  const X = (v) => pad + ((v - x0) / (x1 - x0 || 1)) * (W - pad - right);
  const Y = (v) => H - bottom - ((v - y0) / (y1 - y0 || 1)) * (H - top - bottom);
  const inside = (p) => p.every((v, d) => v >= lo[d] && v <= hi[d]);
  const col = (z) => `hsl(${(1 - (z - lo[2]) / ((hi[2] - lo[2]) || 1)) * 220}, 70%, 55%)`;

  ctx.strokeStyle = cvc("--cv-grid");
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad, top - 10); ctx.lineTo(pad, H - bottom); ctx.lineTo(W - right, H - bottom);
  ctx.stroke();
  ctx.fillStyle = cvc("--cv-sub");
  ctx.font = "11px sans-serif";
  ctx.textAlign = "center";
  ctx.fillText(oblique ? "目标1 →（斜投影，点色 = 目标3）" : "目标1 →", pad + (W - pad - right) / 2, H - 8);
  ctx.save();
  ctx.translate(11, top + (H - top - bottom) / 2 + 22);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("目标2 →", 0, 0);
  ctx.restore();
  if (!oblique) {  // 斜投影的坐标是混合量，刻度没有意义
    ctx.textAlign = "left";
    ctx.fillText(lo[0].toFixed(2), pad, H - bottom + 11);
    ctx.textAlign = "right";
    ctx.fillText(hi[0].toFixed(2), W - right, H - bottom + 11);
    ctx.fillText(hi[1].toFixed(2), pad - 3, top - 2);
    ctx.fillText(lo[1].toFixed(2), pad - 3, H - bottom - 2);
  }
  ctx.textAlign = "left";

  // 解析真前沿（虚线连续画 / 三目标画成淡点）
  const tf = info.front;
  if (!oblique && tf.length <= 60) {  // 离散前沿（ZDT5：f1 只能取 1..31）：每个可达的最优点画一个空心圈
    ctx.strokeStyle = cvc("--cv-sub");
    ctx.lineWidth = 1.2;
    for (const p of tf) { ctx.beginPath(); ctx.arc(X(p[0]), Y(p[1]), 4.5, 0, Math.PI * 2); ctx.stroke(); }
  } else if (!oblique) {
    ctx.strokeStyle = cvc("--cv-sub");
    ctx.lineWidth = 1.5;
    ctx.setLineDash([5, 4]);
    const sorted = tf.slice().sort((a, b) => a[0] - b[0]);
    ctx.beginPath();
    let pen = false, prev = null;
    for (const p of sorted) {
      // ZDT3 的前沿由 5 段组成：相邻点横向跳得远时抬笔，不把断点连成线
      const jump = prev && Math.abs(p[0] - prev[0]) > 0.03;
      if (!pen || jump) { ctx.moveTo(X(p[0]), Y(p[1])); pen = true; } else ctx.lineTo(X(p[0]), Y(p[1]));
      prev = p;
    }
    ctx.stroke();
    ctx.setLineDash([]);
  } else {
    ctx.fillStyle = cvc("--cv-sub");
    ctx.globalAlpha = 0.5;
    for (const p of tf) {
      const q = proj(p);
      ctx.beginPath(); ctx.arc(X(q[0]), Y(q[1]), 1.8, 0, Math.PI * 2); ctx.fill();
    }
    ctx.globalAlpha = 1;
  }
  if (!state) return;

  let outside = 0;
  ctx.fillStyle = cvc("--cv-cur");
  for (const p of state.pop) {
    if (!inside(p)) { outside++; continue; }
    const q = proj(p);
    if (oblique) ctx.fillStyle = col(p[2]);
    ctx.globalAlpha = 0.65;
    ctx.beginPath(); ctx.arc(X(q[0]), Y(q[1]), 2.6, 0, Math.PI * 2); ctx.fill();
  }
  ctx.globalAlpha = 1;
  ctx.strokeStyle = cvc("--cv-best");
  ctx.fillStyle = cvc("--cv-best");
  ctx.lineWidth = 1.5;
  let frontOut = 0;
  if (!oblique) {
    ctx.beginPath();
    let pen = false, prev = null;
    for (const p of state.front) {
      if (!inside(p)) { frontOut++; pen = false; prev = null; continue; }
      // 前沿点相距很远（如 ZDT3 的段与段之间）时抬笔：不把没有解的间隙连成线
      if (!pen || (prev && Math.abs(p[0] - prev[0]) > 0.05)) { ctx.moveTo(X(p[0]), Y(p[1])); pen = true; } else ctx.lineTo(X(p[0]), Y(p[1]));
      prev = p;
    }
    ctx.stroke();
  }
  for (const p of state.front) {
    if (!inside(p)) { if (oblique) frontOut++; continue; }
    const q = proj(p);
    ctx.beginPath(); ctx.arc(X(q[0]), Y(q[1]), 3.4, 0, Math.PI * 2);
    if (oblique) { ctx.lineWidth = 1.5; ctx.stroke(); } else ctx.fill();
  }
  if (state.pref && inside(state.pref)) {  // 偏好法（R-NSGA-II）的参考点：画成菱形
    const q = proj(state.pref), cx = X(q[0]), cy = Y(q[1]);
    ctx.fillStyle = cvc("--cv-ink");
    ctx.beginPath();
    ctx.moveTo(cx, cy - 6); ctx.lineTo(cx + 6, cy); ctx.lineTo(cx, cy + 6); ctx.lineTo(cx - 6, cy);
    ctx.closePath(); ctx.fill();
  }
  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "12px sans-serif";
  ctx.fillText(`非支配解 ${state.nd} 个 · IGD ${state.igd.toFixed(4)} · HV 达到真前沿的 ${(state.hv_ratio * 100).toFixed(1)}%` +
    (state.pref_dist != null ? ` · 到参考点 ${state.pref_dist.toFixed(3)}` : ""), pad + 6, 18);
  if (outside || frontOut) {
    ctx.fillStyle = cvc("--cv-sub");
    ctx.font = "11px sans-serif";
    ctx.fillText(`视窗外 ${outside} 个点未画出（离真前沿还太远）`, pad + 6, 34 + 0);
  }
}

function updateMOC(s) {
  const set = (id, t) => { const el = document.getElementById(id); if (el) el.textContent = t; };
  if (!document.getElementById("mcIGD")) return;
  if (!s) { set("mcIGD", "—"); set("mcHV", "—"); set("mcND", "—"); return; }
  set("mcIGD", s.igd.toFixed(4) + "（历史最好 " + s.best.toFixed(4) + "）");
  set("mcHV", (s.hv_ratio * 100).toFixed(1) + "%（HV " + s.hv.toFixed(3) + "）");
  set("mcND", String(s.nd));
}

function drawViz(s) {
  if (DOMAIN === "knapsack") drawKS(s);
  else if (DOMAIN === "continuous") { drawHeat(); }
  else if (DOMAIN === "graphcolor") drawGC(s);
  else if (DOMAIN === "binpack") drawBP(s);
  else if (DOMAIN === "setcover") drawSC(s);
  else if (DOMAIN === "sat") drawSAT(s);
  else if (DOMAIN === "qubo") drawQB(s);
  else if (DOMAIN === "gap") drawGAP(s);
  else if (DOMAIN === "uflp") drawUF(s);
  else if (DOMAIN === "kpvar" || DOMAIN === "entryseq") drawKPVAR(s);
  else if (DOMAIN === "gcvar") drawGCVAR(s);
  else if (DOMAIN === "bpvar") drawBPVAR(s);
  else if (DOMAIN === "nrp") drawNRP(s);
  else if (DOMAIN === "etp") drawETP(s);
  else if (DOMAIN === "ttp") drawTTP(s);
  else if (DOMAIN === "sls") drawSLS(s);
  else if (DOMAIN === "custom") drawCustom(s);
  else if (DOMAIN === "mocont") drawMOC(s);
  else drawMO(s);
}

// ---------------- 自带问题（custom）：编辑器同步 + 通用可视化 ----------------

const CUSTOM_ENC = { bits: "位向量（每一位 0/1）", perm: "排列（0..n-1 的一个顺序）", real: "实数向量（每维在 lo~hi 内）" };

// 数据表一行一个名字，数组不换行——比 JSON.stringify(…, null, 2) 紧凑得多
function customDataText(data) {
  const keys = Object.keys(data || {});
  if (!keys.length) return "{}";
  return "{\n" + keys.map((k) => "  " + JSON.stringify(k) + ": " + JSON.stringify(data[k])).join(",\n") + "\n}";
}

function customFill() {
  if (DOMAIN !== "custom" || !problem || !$("ceObj")) return;
  $("ceEnc").textContent = CUSTOM_ENC[problem.variant] || problem.variant;
  $("ceN").value = problem.n;
  $("ceSense").value = problem.sense || "min";
  $("ceRange").hidden = problem.variant !== "real";
  if (problem.variant === "real") { $("ceLo").value = problem.lo; $("ceHi").value = problem.hi; }
  $("ceData").value = customDataText(problem.data);
  $("ceObj").value = problem.objective_python ? "（这是一个本地 Python 目标函数，只能在命令行里使用）" : (problem.objective || "");
}

function customEnsureAlgos(variant) {
  if (DOMAIN !== "custom" || !variant || listVariant === variant) return;
  listVariant = variant;
  keepProblemOnList = true;
  post("list", { domain: DOMAIN, opts: { variant } });
}

function customStarted(info) {
  if (DOMAIN !== "custom" || !info || !info.auto_params) return;
  const bits = Object.entries(info.auto_params).map(([k, v]) => k + " = " + Number(v).toPrecision(3));
  if (bits.length) $("statusExtra").textContent = "温度 / 步长已按你的目标函数量级自动设定：" + bits.join("，");
}

function drawCustom(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!problem) return;
  const sol = state && Array.isArray(state.best_sol) ? state.best_sol : null;
  const n = problem.n, enc = problem.variant;
  ctx.font = "13px sans-serif";
  ctx.fillStyle = cvc("--cv-sub");
  ctx.textAlign = "left";
  const head = sol ? "当前最优解（目标值 " + Number(state.best).toPrecision(6) + "，" + (problem.sense === "max" ? "越大越好" : "越小越好") + "）"
                   : "点「开始」后，这里显示当前最优解";
  ctx.fillText(CUSTOM_ENC[enc] + " · n = " + n + " · " + head, 12, 20);
  if (!sol) return;
  const x0 = 28, x1 = W - 16, y0 = 40, y1 = H - 30;
  if (enc === "bits") {
    const cols = Math.min(n, Math.max(5, Math.floor((x1 - x0) / 22)));
    const rows = Math.ceil(n / cols);
    const cw = (x1 - x0) / cols, ch = Math.min(34, (y1 - y0) / rows);
    for (let i = 0; i < n; i++) {
      const cx = x0 + (i % cols) * cw, cy = y0 + Math.floor(i / cols) * ch;
      ctx.fillStyle = sol[i] ? cvc("--cv-best") : cvc("--cv-grid");
      ctx.fillRect(cx + 1, cy + 1, cw - 2, ch - 2);
      if (cw > 20 && n <= 120) {
        ctx.fillStyle = sol[i] ? "#fff" : cvc("--cv-sub");
        ctx.textAlign = "center";
        ctx.fillText(String(i), cx + cw / 2, cy + ch / 2 + 4);
      }
    }
    ctx.textAlign = "left";
    ctx.fillStyle = cvc("--cv-sub");
    ctx.fillText("选中 " + sol.reduce((a, b) => a + b, 0) + " / " + n + "（红色=1，格内数字=下标）", 12, H - 10);
  } else if (enc === "perm") {
    // 横轴=位置，纵轴=放在该位置的元素编号：一条越乱的线 = 越没规律的顺序
    ctx.strokeStyle = cvc("--cv-best");
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    sol.forEach((v, i) => {
      const px = x0 + (i / Math.max(1, n - 1)) * (x1 - x0), py = y1 - (v / Math.max(1, n - 1)) * (y1 - y0);
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    });
    ctx.stroke();
    sol.forEach((v, i) => {
      const px = x0 + (i / Math.max(1, n - 1)) * (x1 - x0), py = y1 - (v / Math.max(1, n - 1)) * (y1 - y0);
      ctx.fillStyle = cvc("--cv-best");
      ctx.beginPath(); ctx.arc(px, py, 3, 0, 7); ctx.fill();
      if (n <= 30) { ctx.fillStyle = cvc("--cv-sub"); ctx.textAlign = "center"; ctx.fillText(String(v), px, py - 7); }
    });
    ctx.textAlign = "left";
    ctx.fillStyle = cvc("--cv-sub");
    ctx.fillText("顺序：" + (n <= 24 ? sol.join(" → ") : sol.slice(0, 20).join(" → ") + " …") + "（横轴=位置，纵轴=元素编号）", 12, H - 10);
  } else {
    const lo = problem.lo, hi = problem.hi, zeroY = y1 - ((0 - lo) / (hi - lo)) * (y1 - y0);
    const bw = (x1 - x0) / n, z = Math.max(y0, Math.min(y1, zeroY));
    ctx.strokeStyle = cvc("--cv-grid");
    ctx.beginPath(); ctx.moveTo(x0, z); ctx.lineTo(x1, z); ctx.stroke();
    sol.forEach((v, i) => {
      const py = y1 - ((v - lo) / (hi - lo)) * (y1 - y0);
      ctx.fillStyle = cvc("--cv-best");
      ctx.fillRect(x0 + i * bw + 2, Math.min(py, z), Math.max(1, bw - 4), Math.max(1, Math.abs(py - z)));
      if (n <= 12) {
        ctx.fillStyle = cvc("--cv-sub"); ctx.textAlign = "center";
        ctx.fillText(Number(v).toFixed(3), x0 + i * bw + bw / 2, Math.min(py, z) - 5);
        ctx.fillText("x[" + i + "]", x0 + i * bw + bw / 2, H - 10);
      }
    });
    ctx.textAlign = "left";
    ctx.fillStyle = cvc("--cv-sub");
    ctx.fillText(lo, 2, y1); ctx.fillText(hi, 2, y0 + 8);
  }
}

// ---------------- 域四：图着色绘制 ----------------

// 金角调色板：色相按 137.5° 黄金角散开，相邻色区分度最大；明度取中段，日夜主题都可读
function gcPalette(i) {
  return `hsl(${(i * 137.508) % 360}, 68%, ${document.documentElement.getAttribute("data-theme") === "dark" ? 62 : 46}%)`;
}

function drawGC(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!problem) return;

  const pos = problem.pos, edges = problem.edges, n = problem.n;
  const r = n > 70 ? 5 : 7;
  // 边（画在点下层）
  ctx.strokeStyle = cvc("--cv-grid");
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (const [u, v] of edges) {
    ctx.moveTo(pos[u][0] / 100 * W, pos[u][1] / 100 * H);
    ctx.lineTo(pos[v][0] / 100 * W, pos[v][1] / 100 * H);
  }
  ctx.stroke();
  // 顶点
  const col = state ? state.best_sol : null;
  for (let i = 0; i < n; i++) {
    const x = pos[i][0] / 100 * W, y = pos[i][1] / 100 * H;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = col ? gcPalette(col[i]) : cvc("--cv-sub");
    ctx.fill();
  }
  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "12px sans-serif";
  if (state && col) {
    const k = Math.max(...col) + 1;
    ctx.fillText(`色数 ${k} · 顶点 ${n} · 边 ${edges.length} · 颜色块=顶点着色（相邻必须异色）`, 14, 20);
  } else {
    ctx.fillText(`顶点 ${n} · 边 ${edges.length}。点「开始」后每个顶点染一种颜色，相邻顶点异色，颜色种类越少越好。`, 14, 20);
  }
}

// ---------------- 域五：装箱绘制 ----------------

function drawBP(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!problem) return;

  const items = problem.items, cap = problem.cap, n = problem.n;
  const pad = 18, top = 34;
  const assign = state ? state.best_sol : null;

  if (!assign) {
    // 未开始：画物品重量条
    const bw = (W - pad * 2) / n;
    const wmax = Math.max(...items);
    for (let i = 0; i < n; i++) {
      const h = (items[i] / wmax) * (H - top - 40);
      ctx.fillStyle = cvc("--cv-grid");
      ctx.fillRect(pad + i * bw + 0.5, H - 24 - h, Math.max(1, bw - 2), h);
    }
    ctx.fillStyle = cvc("--cv-sub");
    ctx.font = "12px sans-serif";
    ctx.fillText(`每根柱子 = 一件物品（高度=重量）。点「开始」后物品被装进箱子（列），箱子越少越好。共 ${n} 件，箱容量 ${cap}`, pad, 20);
    return;
  }

  const nb = Math.max(...assign) + 1;
  const loads = new Array(nb).fill(0);
  for (let i = 0; i < n; i++) loads[assign[i]] += items[i];
  const bw = (W - pad * 2) / nb;
  const bh = H - top - 30;
  const light = document.documentElement.getAttribute("data-theme") === "dark";
  for (let b = 0; b < nb; b++) {
    const x = pad + b * bw;
    // 箱框
    ctx.strokeStyle = cvc("--cv-sub");
    ctx.lineWidth = 1;
    ctx.strokeRect(x + 2, top, bw - 4, bh);
    // 箱内物品块（按装填序堆叠）
    let y = top + bh;
    for (let i = 0; i < n; i++) {
      if (assign[i] !== b) continue;
      const h = (items[i] / cap) * bh;
      y -= h;
      ctx.fillStyle = gcPalette(b);
      ctx.globalAlpha = 0.85;
      ctx.fillRect(x + 3.5, y + 0.5, bw - 7, Math.max(1, h - 1));
      ctx.globalAlpha = 1;
    }
    // 剩余容量刻度线
    const rem = cap - loads[b];
    if (rem > 0) {
      ctx.strokeStyle = cvc("--cv-ok");
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      const ry = top + (rem / cap) * bh;
      ctx.moveTo(x + 3, ry); ctx.lineTo(x + bw - 3, ry);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.fillStyle = cvc("--cv-ink");
    ctx.font = "10px sans-serif";
    if (bw > 26) ctx.fillText(`${loads[b]}`, x + (bw - 8) / 2, H - 12);
  }
  const lb = info && info.lb ? info.lb : "-";
  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "12px sans-serif";
  ctx.fillText(`箱数 ${nb}（下界 LB=${lb}，触到 LB 即最优）· 每列=一箱，虚线=剩余容量`, pad, 20);
}

// ---------------- 域：装箱变体家族 bpvar（H3 单域多预设，3 变体） ----------------
// 复用 drawBP 的容器/物品块约定，但布局数据由 Python 端 solution() 预计算（conts/boxes，
// 坐标=问题单位），JS 仅做统一缩放贴合画布——这样 VSBPP（1D 多档箱）/2D-BPP/SPP（2D shelf）
// 三种几何差异全部压在引擎，前端一份绘制函数通吃。

function drawBPVAR(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!problem) return;

  const vt = problem.variant;
  const sol = state ? state.best_sol : null;
  const pad = 18, top = 34;

  if (!sol) {
    ctx.fillStyle = cvc("--cv-sub");
    ctx.font = "12px sans-serif";
    if (vt === "vsbinpack")
      ctx.fillText(`每件物品有重量，需装入变尺寸箱（容量/成本档位）。目标=开启箱成本之和最小。共 ${problem.n} 件。`, pad, 20);
    else
      ctx.fillText(`矩形物品需装箱 / 铺进条带。目标=箱数最少（2D-BPP）或总高度最小（条带）。共 ${problem.n} 件。`, pad, 20);
    return;
  }

  const conts = sol.conts || [], boxes = sol.boxes || [];
  // 计算包围盒（问题单位）后统一缩放贴合
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const c of conts) { x0 = Math.min(x0, c.x); y0 = Math.min(y0, c.y); x1 = Math.max(x1, c.x + c.w); y1 = Math.max(y1, c.y + c.h); }
  for (const b of boxes) { x0 = Math.min(x0, b.x); y0 = Math.min(y0, b.y); x1 = Math.max(x1, b.x + b.w); y1 = Math.max(y1, b.y + b.h); }
  if (!isFinite(x1)) { x1 = x0 + 1; y1 = y0 + 1; }
  const s = Math.min((W - pad * 2) / (x1 - x0 || 1), (H - top - 30) / (y1 - y0 || 1));
  const ox = pad + ((W - pad * 2) - (x1 - x0) * s) / 2, oy = top + ((H - top - 30) - (y1 - y0) * s) / 2;
  const TX = v => ox + (v - x0) * s, TY = v => oy + (v - y0) * s;

  // 容器框
  ctx.strokeStyle = cvc("--cv-sub");
  ctx.lineWidth = 1;
  for (const c of conts) {
    ctx.strokeRect(TX(c.x), TY(c.y), c.w * s, c.h * s);
    if (vt === "vsbinpack" && c.type != null) {
      ctx.fillStyle = cvc("--cv-sub"); ctx.font = "10px sans-serif";
      ctx.fillText(`#${c.b} 容${c.cap} 成${c.cost}`, TX(c.x) + 2, TY(c.y) + 11);
    } else if ((vt === "binpack2d" || vt === "strippack") && c.h * s > 12) {
      ctx.fillStyle = cvc("--cv-sub"); ctx.font = "10px sans-serif";
      ctx.fillText(`箱${c.b}`, TX(c.x) + 2, TY(c.y) + 11);
    }
  }
  // 物品块（按箱索引取色）
  for (const b of boxes) {
    ctx.fillStyle = gcPalette(b.b);
    ctx.globalAlpha = 0.85;
    ctx.fillRect(TX(b.x) + 0.5, TY(b.y) + 0.5, Math.max(1, b.w * s - 1), Math.max(1, b.h * s - 1));
    ctx.globalAlpha = 1;
  }
  // 文案
  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "12px sans-serif";
  if (vt === "vsbinpack")
    ctx.fillText(`开启箱成本之和 = ${state.best}（越低越好）· 每格=一件物品，落入对应档位箱`, pad, 20);
  else if (vt === "binpack2d")
    ctx.fillText(`箱数 = ${state.best}（越少越好）· 每格=一件矩形物品，按 shelf 装入各箱`, pad, 20);
  else
    ctx.fillText(`条带总高度 = ${state.best}（越低越好）· 每格=一件矩形物品，shelf 自上而下铺放`, pad, 20);
}

// ---------------- 域六~十：SCP / SAT / QUBO / GAP / UFLP 绘制 ----------------

// 「坏状态」红：两主题都可读（未满足子句 / 超载代理用）
function cvBad() {
  return document.documentElement.getAttribute("data-theme") === "dark" ? "#f87171" : "#dc2626";
}

// 集合覆盖：行=集合，列=元素，格子=覆盖关系；选中集合行高亮
function drawSC(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!problem) return;

  const { n_el, m, sets, costs } = problem;
  const sol = state ? state.best_sol : null;
  const padL = 30, padR = 12, top = 30;
  const cw = (W - padL - padR) / n_el;
  const rowH = Math.min(16, (H - top - 26) / m);

  for (let i = 0; i < m; i++) {
    const y = top + i * rowH;
    const on = sol && sol[i];
    if (on) {
      ctx.fillStyle = cvc("--cv-best");
      ctx.globalAlpha = 0.16;
      ctx.fillRect(padL, y, W - padL - padR, rowH);
      ctx.globalAlpha = 1;
    }
    for (let e = 0; e < n_el; e++) {
      if (!sets[i][e]) continue;
      ctx.fillStyle = on ? cvc("--cv-best") : cvc("--cv-grid");
      ctx.fillRect(padL + e * cw + 0.5, y + 2, Math.max(1, cw - 1), rowH - 4);
    }
    ctx.fillStyle = on ? cvc("--cv-ink") : cvc("--cv-sub");
    ctx.font = "9px sans-serif";
    ctx.fillText(`S${i}·${costs[i]}`, 2, y + rowH - 4);
  }
  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "12px sans-serif";
  if (sol) {
    const k = sol.reduce((a, b) => a + b, 0);
    ctx.fillText(`选中 ${k}/${m} 个集合 · 总成本 ${state.best} · 行=集合 列=元素 亮格=覆盖`, padL, 18);
  } else {
    ctx.fillText(`行=集合（成本见行首），列=元素，亮格=该集合覆盖此元素。点「开始」选最少的集合盖住全部 ${n_el} 个元素。`, padL, 18);
  }
}

// SAT：子句按行排布，绿=满足 红=未满足；每个子句 3 个文字 chip
function drawSAT(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!problem) return;

  const { n_vars, clauses } = problem;
  const sol = state ? state.best_sol : null;
  const pad = 14, top = 30;
  const chipW = Math.min(120, Math.max(84, Math.floor((W - pad * 2) / 3) - 8));
  const cols = Math.max(1, Math.floor((W - pad * 2) / (chipW + 8)));
  const rowH = 22;
  const sat = (cl) => sol && cl.some((l) => sol[Math.abs(l) - 1] === (l > 0 ? 1 : 0));
  let nUnsat = 0;

  for (let k = 0; k < clauses.length; k++) {
    const r = Math.floor(k / cols), c = k % cols;
    const x = pad + c * (chipW + 8), y = top + r * rowH;
    const ok = sat(clauses[k]);
    if (sol && !ok) nUnsat++;
    const text = clauses[k].map((l) => (l > 0 ? `x${l}` : `¬x${-l}`)).join(" ∨ ");
    ctx.fillStyle = sol ? (ok ? cvc("--cv-ok") : cvBad()) : cvc("--cv-grid");
    ctx.globalAlpha = sol && ok ? 0.85 : 1;
    const w = Math.min(chipW, 6 + ctx.measureText(text).width);
    ctx.beginPath();
    if (ctx.roundRect) ctx.roundRect(x, y, w, 17, 4); else ctx.rect(x, y, w, 17);
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.fillStyle = sol ? "#fff" : cvc("--cv-ink");
    ctx.font = "11px sans-serif";
    ctx.fillText(text, x + 5, y + 12, chipW - 8);
  }
  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "12px sans-serif";
  if (sol) {
    ctx.fillText(`未满足子句 ${state.best}/${clauses.length} · ${n_vars} 个变量 · 绿=满足 红=未满足，目标=全绿`, pad, 18);
  } else {
    ctx.fillText(`${clauses.length} 个子句（每个 3 个文字，如 x3 ∨ ¬x7 ∨ x12）。点「开始」给 ${n_vars} 个变量赋值，目标=让所有子句为真。`, pad, 18);
  }
}

// QUBO：n 比特排成网格，亮=取 1；角落显示当前能量 x'Qx
function drawQB(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!problem) return;

  const n = problem.n;
  const sol = state ? state.best_sol : null;
  const pad = 20, top = 36;
  const cols = Math.ceil(Math.sqrt(n * (W / Math.max(1, H - top))));
  const rows = Math.ceil(n / cols);
  const cw = Math.min((W - pad * 2) / cols, (H - top - 30) / rows);

  for (let i = 0; i < n; i++) {
    const r = Math.floor(i / cols), c = i % cols;
    const x = pad + c * cw, y = top + r * cw;
    const on = sol && sol[i];
    ctx.fillStyle = on ? cvc("--cv-best") : cvc("--cv-bg");
    ctx.strokeStyle = cvc("--cv-grid");
    ctx.lineWidth = 1;
    ctx.fillRect(x + 1, y + 1, cw - 2, cw - 2);
    ctx.strokeRect(x + 1.5, y + 1.5, cw - 3, cw - 3);
    if (cw >= 24) {
      ctx.fillStyle = on ? "#fff" : cvc("--cv-sub");
      ctx.font = "10px sans-serif";
      ctx.fillText(`x${i}`, x + 4, y + 13);
    }
  }
  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "12px sans-serif";
  if (sol) {
    const ones = sol.reduce((a, b) => a + b, 0);
    ctx.fillText(`能量 x'Qx = ${state.best}（最小化）· 取 1 的比特 ${ones}/${n}`, pad, 20);
  } else {
    ctx.fillText(`每个方块 = 一个 0/1 决策变量 xᵢ。点「开始」找让二次型 x'Qx 最小的赋值（QUBO 是 SAT/最大割等的统一编码）。`, pad, 20);
  }
}

// GAP：列=代理，柱=负载/容量，虚线=容量上限，红=超载
function drawGAP(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!problem) return;

  const { n_a, n_j, r, cap } = problem;
  const sol = state ? state.best_sol : null;
  const pad = 18, top = 34;
  const bw = (W - pad * 2) / n_a;
  const bh = H - top - 30;

  if (!sol) {
    ctx.fillStyle = cvc("--cv-sub");
    ctx.font = "12px sans-serif";
    ctx.fillText(`${n_j} 个任务要派给 ${n_a} 个代理（成本/资源见词条）。点「开始」看每个代理的负载柱——虚线=容量，目标=总成本最低且不超载。`, pad, 20);
    // 未开始：画容量标尺
    for (let a = 0; a < n_a; a++) {
      const x = pad + a * bw;
      ctx.strokeStyle = cvc("--cv-grid");
      ctx.strokeRect(x + 2, top, bw - 4, bh);
      ctx.fillStyle = cvc("--cv-sub");
      ctx.font = "10px sans-serif";
      ctx.fillText(`cap ${cap[a]}`, x + 4, H - 14);
    }
    return;
  }

  const load = new Array(n_a).fill(0);
  for (let j = 0; j < n_j; j++) load[sol[j]] += r[sol[j]][j];
  const rmax = Math.max(...cap, ...load);
  for (let a = 0; a < n_a; a++) {
    const x = pad + a * bw;
    const over = load[a] > cap[a];
    // 负载柱（相对最大容量标尺）
    const h = (load[a] / rmax) * bh;
    ctx.fillStyle = over ? cvBad() : cvc("--cv-best");
    ctx.globalAlpha = 0.85;
    ctx.fillRect(x + 3, top + bh - h, bw - 6, Math.max(1, h));
    ctx.globalAlpha = 1;
    // 容量虚线
    const cy = top + bh - (cap[a] / rmax) * bh;
    ctx.strokeStyle = cvc("--cv-ok");
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    ctx.moveTo(x + 3, cy); ctx.lineTo(x + bw - 3, cy);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.strokeStyle = cvc("--cv-grid");
    ctx.strokeRect(x + 2.5, top + 0.5, bw - 5, bh);
    ctx.fillStyle = cvc("--cv-ink");
    ctx.font = "10px sans-serif";
    ctx.fillText(`${load[a]}/${cap[a]}`, x + 4, H - 14);
  }
  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "12px sans-serif";
  ctx.fillText(`总成本 ${state.best} · 每列=一个代理（实柱=负载，绿虚线=容量）· 红=超载`, pad, 20);
}

// kpvar：背包家族 10 变体（H1 期单域多预设）。variant 分派三种画法：
// mkpm→多背包负载柱；mckp→类×件网格；其余→物品柱（cmp/ssp 带目标线，dkp 标折扣）
function drawKPVAR(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!problem) return;
  const vt = problem.variant;
  const sol = state ? state.best_sol : null;
  const pad = 18;

  if (vt === "mkpm") {
    const m = problem.m, caps = problem.caps, w = problem.w;
    const n = w.length;
    const bw = (W - pad * 2) / m, bh = H - 60;
    const load = new Array(m).fill(0);
    let dropped = 0;
    if (sol) {
      for (let i = 0; i < n; i++) {
        if (sol[i] === 0) dropped++;
        else load[sol[i] - 1] += w[i];
      }
    }
    const rmax = Math.max(...caps, ...(sol ? load : [0]), 1);
    for (let a = 0; a < m; a++) {
      const x = pad + a * bw;
      const h = (load[a] / rmax) * bh;
      ctx.fillStyle = load[a] > caps[a] ? cvBad() : cvc("--cv-best");
      ctx.globalAlpha = 0.85;
      ctx.fillRect(x + 4, 40 + bh - h, bw - 8, Math.max(1, h));
      ctx.globalAlpha = 1;
      const cy = 40 + bh - (caps[a] / rmax) * bh;
      ctx.strokeStyle = cvc("--cv-ok");
      ctx.setLineDash([4, 3]);
      ctx.beginPath(); ctx.moveTo(x + 4, cy); ctx.lineTo(x + bw - 4, cy); ctx.stroke();
      ctx.setLineDash([]);
      ctx.strokeStyle = cvc("--cv-grid");
      ctx.strokeRect(x + 3.5, 40.5, bw - 7, bh);
      ctx.fillStyle = cvc("--cv-ink");
      ctx.font = "11px sans-serif";
      ctx.fillText(`包${a + 1}: ${load[a]}/${caps[a]}`, x + 5, H - 22);
    }
    ctx.fillStyle = cvc("--cv-ink");
    ctx.font = "12px sans-serif";
    ctx.fillText(sol
      ? `目标 ${state.best}（负=总价值）· 未取 ${dropped}/${n} 件 · 实柱=负载 绿虚线=容量`
      : `${n} 件物品派进 ${m} 个背包（也可不取）。点「开始」看负载分配。`, pad, 20);
    return;
  }

    if (DOMAIN === "entryseq") {
    const variant = problem.variant || "";
    const n = problem.n || 10;
    ctx.clearRect(pad, pad, W - 2 * pad, H - 2 * pad);
    const sol = (lastState && lastState.best_sol) || (info && info.best_sol) || null;
    const det = lastState || {};
    const ink = "#9aa0b0";
    const pal = (i) => `hsl(${(i * 137.508) % 360}, 68%, ${document.documentElement.getAttribute("data-theme") === "dark" ? 62 : 46}%)`;
    if (["vcover", "domset", "fvs", "maxcut", "stp"].includes(variant)) {
      // 子集类图问题（位向量编码）：红 = 被选中的点，每个变体各自标出违反约束的地方
      const pts = problem.pts || [], edges = problem.edges || [];
      const sel = det.sel || new Array(problem.n).fill(0);
      const px = (q) => [pad + 14 + (q[0] / 100) * (W - 2 * pad - 28), H - pad - 24 - (q[1] / 100) * (H - 2 * pad - 52)];
      const red = "#e5484d", blue = "#7aa2f7", grey = cvc("--cv-grid");
      const nbr = pts.map(() => []);
      edges.forEach(([u, v]) => { nbr[u].push(v); nbr[v].push(u); });
      const drawEdge = (u, v, col, w, dash) => {
        const [x1, y1] = px(pts[u]), [x2, y2] = px(pts[v]);
        ctx.strokeStyle = col; ctx.lineWidth = w; ctx.setLineDash(dash || []);
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); ctx.setLineDash([]);
      };
      let note = "";
      if (variant === "stp") {
        const nodes = det.nodes || problem.req;
        // 最小生成树（Prim）：与引擎同一定义，仅用于作图
        const inT = new Set([nodes[0]]), list = nodes.slice(1);
        const tree = [];
        while (list.length) {
          let bi = -1, bu = -1, bd = Infinity;
          list.forEach((v, i) => inT.forEach((u) => { const d = Math.hypot(pts[u][0] - pts[v][0], pts[u][1] - pts[v][1]); if (d < bd) { bd = d; bi = i; bu = u; } }));
          tree.push([bu, list[bi]]); inT.add(list[bi]); list.splice(bi, 1);
        }
        tree.forEach(([u, v]) => drawEdge(u, v, red, 2.4));
        pts.forEach((q, i) => {
          const [x, y] = px(q), isReq = problem.req.includes(i), on = isReq || sel[i];
          ctx.fillStyle = on ? (isReq ? blue : red) : grey;
          if (isReq) ctx.fillRect(x - 6, y - 6, 12, 12); else { ctx.beginPath(); ctx.arc(x, y, on ? 6 : 4, 0, 7); ctx.fill(); }
        });
        note = det.mst !== undefined ? `斯坦纳树长度（最小生成树）= ${det.mst} · 蓝方块 = 必需点，红圆 = 选用的中转点，灰点 = 没选` : "蓝方块 = 必需点；选哪些灰点当中转点来缩短整棵树。点「开始」。";
      } else {
        edges.forEach(([u, v]) => {
          if (variant === "vcover") drawEdge(u, v, !sel[u] && !sel[v] ? red : grey, !sel[u] && !sel[v] ? 2.6 : 1.2, !sel[u] && !sel[v] ? [5, 3] : null);
          else if (variant === "maxcut") drawEdge(u, v, sel[u] !== sel[v] ? red : grey, sel[u] !== sel[v] ? 2.6 : 1);
          else if (variant === "fvs") { if (!sel[u] && !sel[v]) drawEdge(u, v, blue, 1.6); else drawEdge(u, v, grey, 0.8, [3, 3]); }
          else drawEdge(u, v, grey, 1.2);
        });
        pts.forEach((q, i) => {
          const [x, y] = px(q);
          let fill = grey;
          if (variant === "maxcut") fill = sel[i] ? red : blue;
          else if (variant === "domset") fill = sel[i] ? red : (nbr[i].some((u) => sel[u]) ? blue : "#c9a227");
          else fill = sel[i] ? red : blue;
          ctx.fillStyle = fill; ctx.beginPath(); ctx.arc(x, y, sel[i] && variant !== "maxcut" ? 8 : 6, 0, 7); ctx.fill();
          if (variant === "fvs" && sel[i]) { ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x - 4, y - 4); ctx.lineTo(x + 4, y + 4); ctx.moveTo(x + 4, y - 4); ctx.lineTo(x - 4, y + 4); ctx.stroke(); }
        });
        const bad = det.violations || 0;
        note = {
          vcover: `选了 ${det.size ?? 0} 个点${bad ? ` · ${bad} 条边没被覆盖（红虚线）` : "，每条边至少有一端被选"}（红 = 选中）`,
          domset: `选了 ${det.size ?? 0} 个点${bad ? ` · ${bad} 个点没被支配（黄）` : "，每个点要么被选要么有邻居被选"}（红 = 选中，蓝 = 被支配）`,
          fvs: `删了 ${det.size ?? 0} 个点（带 ✕ 的红点）${bad ? ` · 剩下的图还有 ${bad} 个环` : "，剩下的图没有环（蓝线）"}`,
          maxcut: det.cut !== undefined ? `割边权和 = ${det.cut} / 总权 ${det.total}（红线 = 被割断的边；红蓝是两侧，两侧不必一样大）` : "每个点选一侧，让被割断的边权和最大。点「开始」。",
        }[variant];
      }
      ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
      ctx.fillText(note, pad, H - 8);
      return;
    }
    if (variant === "ged") {
      // 布局生成：圆 = 功能块（半径 = 尺寸），虚线 = 希望相邻的块对；重叠的块画红圈
      const SZ = problem.size, side = Math.min(W - 2 * pad, H - pad - 40), x0 = pad + (W - 2 * pad - side) / 2, y0 = pad + 6;
      const sc = (v) => (v / SZ) * side;
      ctx.strokeStyle = cvc("--cv-grid"); ctx.strokeRect(x0 + 0.5, y0 + 0.5, side, side);
      const pos = det.pos;
      if (pos) {
        problem.adj.forEach(([i, j]) => {
          ctx.strokeStyle = cvc("--cv-sub"); ctx.setLineDash([4, 3]);
          ctx.beginPath(); ctx.moveTo(x0 + sc(pos[i][0]), y0 + side - sc(pos[i][1])); ctx.lineTo(x0 + sc(pos[j][0]), y0 + side - sc(pos[j][1])); ctx.stroke(); ctx.setLineDash([]);
        });
        pos.forEach((q, i) => {
          const hit = pos.some((q2, j) => j !== i && Math.hypot(q[0] - q2[0], q[1] - q2[1]) < problem.r[i] + problem.r[j]);
          ctx.fillStyle = pal(i); ctx.globalAlpha = 0.55;
          ctx.beginPath(); ctx.arc(x0 + sc(q[0]), y0 + side - sc(q[1]), sc(problem.r[i]), 0, 7); ctx.fill(); ctx.globalAlpha = 1;
          ctx.strokeStyle = hit ? "#e5484d" : pal(i); ctx.lineWidth = hit ? 2.2 : 1.2; ctx.stroke(); ctx.lineWidth = 1;
          ctx.fillStyle = ink; ctx.font = "10px sans-serif"; ctx.textAlign = "center"; ctx.fillText(String(i + 1), x0 + sc(q[0]), y0 + side - sc(q[1]) + 3);
        });
      }
      ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
      ctx.fillText(pos ? `目标 ${lastState.best} · ${det.overlaps} 对块重叠（红圈）· 虚线 = 希望相邻（越近越好）`
                       : `${problem.k} 个圆形块摆进 ${SZ}×${SZ} 的场地：互不重叠，虚线连着的块对希望相邻。点「开始」。`, pad, H - 8);
      return;
    }
    if (variant === "proteinfold") {
      // 二维 HP 链：实心 = 疏水（H），空心 = 亲水（P）；蓝虚线 = 拓扑接触（格点相邻但序列不相邻的 H–H 对）；红 = 自交的格点
      const pos = det.pos, seq = problem.seq;
      if (pos) {
        const xs = pos.map((q) => q[0]), ys = pos.map((q) => q[1]);
        const lo = [Math.min(...xs), Math.min(...ys)], hi = [Math.max(...xs), Math.max(...ys)];
        const cell = Math.min(40, (W - 2 * pad - 20) / (hi[0] - lo[0] + 1), (H - 2 * pad - 40) / (hi[1] - lo[1] + 1));
        const px = (q) => [pad + 10 + (q[0] - lo[0] + 0.5) * cell, H - pad - 26 - (q[1] - lo[1] + 0.5) * cell];
        ctx.strokeStyle = cvc("--cv-sub"); ctx.lineWidth = 2; ctx.beginPath();
        pos.forEach((q, i) => { const [x, y] = px(q); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
        ctx.stroke(); ctx.lineWidth = 1;
        (det.contacts || []).forEach(([i, j]) => {
          const [x1, y1] = px(pos[i]), [x2, y2] = px(pos[j]);
          ctx.strokeStyle = "#7aa2f7"; ctx.setLineDash([3, 3]); ctx.lineWidth = 2;
          ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); ctx.setLineDash([]); ctx.lineWidth = 1;
        });
        pos.forEach((q, i) => {
          const [x, y] = px(q), H_ = seq[i] === "H";
          ctx.beginPath(); ctx.arc(x, y, Math.max(4, cell * 0.28), 0, 7);
          ctx.fillStyle = H_ ? "#e5484d" : cvc("--bg") || "#fff"; if (H_) ctx.fill();
          ctx.strokeStyle = H_ ? "#e5484d" : cvc("--cv-sub"); ctx.lineWidth = 1.6; ctx.stroke(); ctx.lineWidth = 1;
        });
      }
      ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
      ctx.fillText(pos ? `HH 接触 ${det.contacts.length} 对（蓝虚线）${det.clashes ? ` · ${det.clashes} 处自交（每处罚 4）` : ""} · 实心红 = H，空心 = P`
                       : `序列 ${seq.join("")}（${seq.filter((c) => c === "H").length} 个 H）。把链折到格点上，让 H 彼此靠拢。点「开始」。`, pad, H - 8);
      return;
    }
    if (variant === "msa") {
      // 三条序列的比对：每行一条序列，彩色字母 = 残基，灰点 = 空位；列上三个字母相同的画粗底
      const rows = det.rows || problem.seqs, W0 = Math.max(...rows.map((r) => r.length));
      const x0 = pad + 24, cw = Math.min(26, (W - x0 - pad) / W0), ch = 30, y0 = pad + 34;
      const colr = { A: "#4fa3f7", C: "#f0b43c", G: "#3ecf8e", T: "#e5484d" };
      ctx.font = "13px monospace"; ctx.textAlign = "center";
      rows.forEach((row, r) => {
        ctx.fillStyle = ink; ctx.textAlign = "right"; ctx.fillText(`S${r + 1}`, x0 - 6, y0 + r * ch + 17); ctx.textAlign = "center";
        [...row].forEach((c, i) => {
          const same = det.rows && c !== "-" && rows.every((q) => q[i] === c);
          ctx.fillStyle = same ? cvc("--cv-ok") : cvc("--cv-grid");
          ctx.globalAlpha = same ? 0.35 : 0.2; ctx.fillRect(x0 + i * cw, y0 + r * ch, cw - 1, ch - 4); ctx.globalAlpha = 1;
          ctx.fillStyle = c === "-" ? "#9aa0b0" : (colr[c.toUpperCase()] || ink);
          ctx.fillText(c === "-" ? "·" : c, x0 + i * cw + cw / 2, y0 + r * ch + 17);
        });
      });
      ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
      ctx.fillText(det.rows ? `和对（SP）得分 ${det.sp}（精确最优 ${det.opt}，三维动态规划）· 绿底 = 三条序列这一列相同`
                            : `3 条序列（匹配 +2、错配 −1、残基对空位 −2）。精确最优 SP = ${problem.opt}。点「开始」。`, pad, pad + 14);
      return;
    }
    if (["mst", "shortestpath", "maxflow", "mincostflow", "gmatch", "topsort"].includes(variant)) {
      // P 类对照问题的图：mst 画选中的树边，shortestpath 画路径，gmatch 画匹配，maxflow / mincostflow 画流量（线宽 ∝ 流量），topsort 把顶点按排列摆成一行
      const pts = problem.pts, directed = !!(problem.arcs);
      const px = (q) => [pad + 14 + (q[0] / 100) * (W - 2 * pad - 28), pad + 14 + (1 - q[1] / 100) * (H - 2 * pad - 52)];
      const red = "#e5484d", blue = "#7aa2f7";
      const seg = (a, b, col, w, dash, arrow) => {
        const [x1, y1] = px(pts[a]), [x2, y2] = px(pts[b]);
        ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = w; ctx.setLineDash(dash || []);
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); ctx.setLineDash([]); ctx.lineWidth = 1;
        if (arrow) {
          const ang = Math.atan2(y2 - y1, x2 - x1), mx = (x1 + x2) / 2, my = (y1 + y2) / 2;
          ctx.beginPath(); ctx.moveTo(mx + 7 * Math.cos(ang), my + 7 * Math.sin(ang));
          ctx.lineTo(mx - 5 * Math.cos(ang) + 4 * Math.sin(ang), my - 5 * Math.sin(ang) - 4 * Math.cos(ang));
          ctx.lineTo(mx - 5 * Math.cos(ang) - 4 * Math.sin(ang), my - 5 * Math.sin(ang) + 4 * Math.cos(ang));
          ctx.closePath(); ctx.fill();
        }
      };
      let note = "";
      if (variant === "topsort") {
        const order = (lastState && lastState.best_sol) || null, n = pts.length;
        const xs = (i) => pad + 18 + (i / Math.max(1, n - 1)) * (W - 2 * pad - 36), y = H / 2 + 20;
        const pos = {}; (order || Array.from({ length: n }, (_, i) => i)).forEach((v, i) => { pos[v] = i; });
        const bad = new Set(det.backward || []);
        problem.arcs.forEach(([a, b], k) => {
          const x1 = xs(pos[a]), x2 = xs(pos[b]), mid = (x1 + x2) / 2, hgt = 14 + Math.abs(x2 - x1) * 0.28;
          ctx.strokeStyle = bad.has(k) ? red : cvc("--cv-ok"); ctx.globalAlpha = bad.has(k) ? 1 : 0.55; ctx.lineWidth = bad.has(k) ? 1.8 : 1;
          ctx.beginPath(); ctx.moveTo(x1, y); ctx.quadraticCurveTo(mid, y - hgt, x2, y); ctx.stroke(); ctx.globalAlpha = 1; ctx.lineWidth = 1;
        });
        (order || Array.from({ length: n }, (_, i) => i)).forEach((v, i) => {
          ctx.fillStyle = blue; ctx.beginPath(); ctx.arc(xs(i), y, 8, 0, 7); ctx.fill();
          ctx.fillStyle = "#fff"; ctx.font = "9px sans-serif"; ctx.textAlign = "center"; ctx.fillText(String(v), xs(i), y + 3);
        });
        note = order ? (bad.size ? `${bad.size} 条弧指向「更靠前」的点（红）——目标是 0` : "合法的拓扑序：所有弧都从左指向右（绿）") : "把点排成一行，使每条弧都从左指向右。点「开始」。";
        ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left"; ctx.fillText(note, pad, H - 8);
        return;
      }
      const E = directed ? problem.arcs : problem.edges;
      const tree = new Set(det.tree || []), matched = new Set(det.matched || []);
      const onPath = new Set(); (det.path || []).forEach((v, i) => { if (i) onPath.add([Math.min(det.path[i - 1], v), Math.max(det.path[i - 1], v)].join()); });
      const fmax = Math.max(1, ...E.map((e) => e[2]));
      E.forEach((e, k) => {
        const [a, b, w] = e;
        let col = cvc("--cv-grid"), lw = 0.9, arrow = directed;
        if (variant === "mst" && tree.has(k)) { col = red; lw = 3; }
        else if (variant === "gmatch" && matched.has(k)) { col = red; lw = 3.2; }
        else if (variant === "shortestpath" && onPath.has([Math.min(a, b), Math.max(a, b)].join())) { col = red; lw = 3.2; }
        else if (directed && det.flow && det.flow[k] > 0.01) { col = red; lw = 0.8 + 3.4 * (det.flow[k] / fmax); }
        seg(a, b, col, lw, null, arrow);
        if (variant !== "mst" || tree.has(k)) {
          const [x1, y1] = px(pts[a]), [x2, y2] = px(pts[b]);
          ctx.fillStyle = ink; ctx.font = "9px sans-serif"; ctx.textAlign = "center";
          const lab = directed ? (det.flow ? `${det.flow[k]}/${w}` : `${w}`) : String(w);
          if (!directed || det.flow || E.length <= 24) ctx.fillText(lab, (x1 + x2) / 2 + 6, (y1 + y2) / 2 - 3);
        }
      });
      pts.forEach((q, i) => {
        const [x, y] = px(q);
        const special = (directed && (i === problem.src || i === problem.snk)) || (variant === "shortestpath" && (i === problem.src || i === problem.dst));
        ctx.fillStyle = special ? "#e5a23c" : blue;
        ctx.beginPath(); ctx.arc(x, y, special ? 7 : 5, 0, 7); ctx.fill();
        ctx.fillStyle = "#fff"; ctx.font = "9px sans-serif"; ctx.textAlign = "center"; ctx.fillText(String(i), x, y + 3);
      });
      const have = lastState && lastState.best_sol;
      if (variant === "mst") note = have ? `树权重 ${det.weight}（精确最优 ${det.opt}，Kruskal）· 红 = 选中的树边` : `最小生成树：精确最优 = ${problem.opt}（Kruskal）。点「开始」。`;
      else if (variant === "gmatch") note = have ? `匹配权重 ${det.weight}（精确最优 ${det.opt}）· 红 = 匹配边` : `最大权匹配：精确最优 = ${problem.opt}。点「开始」。`;
      else if (variant === "shortestpath") note = have ? (det.reached ? `路径长度 ${det.length}（精确最优 ${det.opt}，Dijkstra）` : "走进了死胡同（没到终点）——按重罚计") : `从 ${problem.src} 到 ${problem.dst}：精确最优 = ${problem.opt}（Dijkstra）。点「开始」。`;
      else if (variant === "maxflow") note = have ? `流值 ${det.value}（最大流 ${det.opt}）· 守恒违反量 ${det.violation}（0 才是合法流）` : `最大流 = ${problem.opt}（Edmonds–Karp）。橙点 = 源点 / 汇点。点「开始」。`;
      else note = have ? `送出 ${det.value}/${det.need} · 费用 ${det.cost}（最小费用 ${det.opt}）· 守恒违反量 ${det.violation}` : `送出 ${problem.need} 单位的最小费用 = ${problem.opt}。点「开始」。`;
      ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left"; ctx.fillText(note, pad, H - 8);
      return;
    }
    if (variant === "ctp") {
      // 课表：列 = 星期，行 = 节次，每格里至多 3 块（3 间教室，块的高度 ∝ 教室容量）；颜色 = 课程
      const D = problem.days, S = problem.slots, rooms = problem.rooms;
      const x0 = pad + 34, y0 = pad + 22, cw = (W - x0 - pad) / D, ch = (H - y0 - pad - 26) / S;
      ctx.font = "11px sans-serif"; ctx.textAlign = "center";
      const placed = det.placed || [];
      for (let d = 0; d < D; d++) { ctx.fillStyle = ink; ctx.fillText(`周${"一二三四五六日"[d]}`, x0 + d * cw + cw / 2, y0 - 6); }
      for (let t = 0; t < S; t++) { ctx.fillStyle = ink; ctx.textAlign = "right"; ctx.fillText(`第${t + 1}节`, x0 - 6, y0 + t * ch + ch / 2 + 3); ctx.textAlign = "center"; }
      for (let d = 0; d < D; d++) for (let t = 0; t < S; t++) {
        ctx.strokeStyle = cvc("--cv-grid"); ctx.strokeRect(x0 + d * cw + 0.5, y0 + t * ch + 0.5, cw - 2, ch - 2);
      }
      placed.forEach(([k, c, per, r]) => {
        const d = Math.floor(per / S), t = per % S, bw = (cw - 6) / rooms.length;
        ctx.fillStyle = pal(c); ctx.globalAlpha = 0.9;
        ctx.fillRect(x0 + d * cw + 3 + r * bw, y0 + t * ch + 3, bw - 2, ch - 8);
        ctx.globalAlpha = 1; ctx.fillStyle = "#fff";
        ctx.fillText(String(c + 1), x0 + d * cw + 3 + r * bw + (bw - 2) / 2, y0 + t * ch + ch / 2 + 3);
      });
      ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
      ctx.fillText(det.placed ? `排进 ${placed.length}/${problem.n} 节${det.undone ? `，${det.undone} 节没排进去` : ""} · 软代价 ${det.soft}（教室装不下的人数 + 同一天重复上同一门课 ×10）· 每格 3 块 = 3 间教室（30/45/60 座，从左到右）`
                              : `${problem.n_courses} 门课共 ${problem.n} 节，排进 ${D}×${S} 个时段 × ${rooms.length} 间教室；同教师或同课程组的课不能同时上。点「开始」。`, pad, H - 8);
      return;
    }
    if (variant === "fkp") {
      // 分数背包：柱高 = 重量，填充部分 = 取走的比例；虚线 = 容量下精确最优（贪心）对应的价值在标题里给出
      const w = problem.w, nI = w.length, bw = (W - 2 * pad) / nI, wmax = Math.max(...w);
      const hmax = H - 2 * pad - 46, x = det.x || null;
      for (let i = 0; i < nI; i++) {
        const h = (w[i] / wmax) * hmax, px0 = pad + i * bw, py0 = H - pad - 30 - h;
        ctx.fillStyle = cvc("--cv-grid"); ctx.fillRect(px0 + 0.5, py0, Math.max(1, bw - 2), h);
        if (x) {
          const hh = h * x[i];
          ctx.fillStyle = cvc("--cv-best"); ctx.globalAlpha = 0.9;
          ctx.fillRect(px0 + 0.5, py0 + h - hh, Math.max(1, bw - 2), hh); ctx.globalAlpha = 1;
        }
      }
      ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
      ctx.fillText(x ? `价值 ${det.value}（精确最优 ${det.lp}）· 重量 ${det.weight}/${det.cap} · 填充 = 取走的比例`
                     : `每个物品可以只取一部分。容量 ${problem.cap}，精确最优 = ${problem.lp}（按价值密度贪心）。点「开始」。`, pad, H - 8);
      return;
    }
    if (["fss", "jss", "oss", "fjsp"].includes(variant)) {
      // 车间调度甘特图：每行一台机器，色块 = 作业（的一道工序）；绿虚线 = 下界，蓝虚线 = 文献最优
      const ops = det.ops || [], m = problem.m_mach;
      const mx = Math.max(1, det.makespan || 0, det.lb || 0, problem.opt || 0);
      const x0 = pad + 50, x1 = W - pad - 8, rowH = Math.min(44, (H - 2 * pad - 44) / m);
      ctx.font = "11px sans-serif"; ctx.textAlign = "left";
      for (let k = 0; k < m; k++) {
        const y = pad + 22 + k * rowH;
        ctx.fillStyle = ink; ctx.fillText(`机器 ${k + 1}`, pad + 2, y + rowH / 2 + 3);
        ctx.strokeStyle = cvc("--cv-grid"); ctx.strokeRect(x0 + 0.5, y + 1.5, x1 - x0, rowH - 4);
      }
      ops.forEach(([j, k, st, en]) => {
        const y = pad + 22 + k * rowH, w = ((en - st) / mx) * (x1 - x0);
        ctx.fillStyle = pal(j); ctx.globalAlpha = 0.9;
        ctx.fillRect(x0 + (st / mx) * (x1 - x0), y + 3, Math.max(1, w - 1), rowH - 8);
        ctx.globalAlpha = 1;
        if (w > 15) { ctx.fillStyle = "#fff"; ctx.fillText(String(j + 1), x0 + (st / mx) * (x1 - x0) + 3, y + rowH / 2 + 3); }
      });
      const vline = (v, col) => {
        const lx = x0 + (v / mx) * (x1 - x0);
        ctx.strokeStyle = col; ctx.setLineDash([4, 3]);
        ctx.beginPath(); ctx.moveTo(lx, pad + 16); ctx.lineTo(lx, pad + 22 + m * rowH); ctx.stroke(); ctx.setLineDash([]);
      };
      if (det.lb) vline(det.lb, cvc("--cv-ok"));
      if (problem.opt) vline(problem.opt, "#7aa2f7");
      ctx.fillStyle = ink; ctx.font = "12px sans-serif";
      const nm = problem.name ? `${problem.name} · ` : "";
      ctx.fillText(ops.length ? `${nm}Cmax = ${det.makespan}` + (problem.opt ? ` · 已知最优 ${problem.opt}（蓝虚线）` : "") + (det.lb ? ` · 下界 ${det.lb}（绿虚线）` : "")
                              : `${nm}${det.n_jobs || problem.n_jobs || problem.n} 个作业 × ${m} 台机器。点「开始」。`, pad + 2, pad + 10);
      return;
    }
    if (variant === "hc" || variant === "lpath") {
      // 图 + 排列：灰线 = 图的边；hc 把排列首尾相接，红虚线 = 不是边的那一步；lpath 画沿排列延伸出来的那条路径
      const pts = problem.pts, edges = problem.edges, sol = lastState && lastState.best_sol;
      const px = (q) => [pad + 14 + (q[0] / 100) * (W - 2 * pad - 28), H - pad - 24 - (q[1] / 100) * (H - 2 * pad - 52)];
      const red = "#e5484d", seg = (a, b, col, w, dash) => {
        const [x1, y1] = px(pts[a]), [x2, y2] = px(pts[b]);
        ctx.strokeStyle = col; ctx.lineWidth = w; ctx.setLineDash(dash || []);
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); ctx.setLineDash([]); ctx.lineWidth = 1;
      };
      const wmax = Math.max(1, ...edges.map((e) => e[2] || 1));
      edges.forEach(([a, b, w]) => seg(a, b, cvc("--cv-grid"), variant === "lpath" ? 0.8 + 2.2 * (w / wmax) : 1.2));
      let note = "";
      if (variant === "hc") {
        if (sol) {
          const bad = new Set(det.broken || []);
          sol.forEach((a, i) => seg(a, sol[(i + 1) % sol.length], bad.has(i) ? red : cvc("--cv-ok"), bad.has(i) ? 1.6 : 2.6, bad.has(i) ? [5, 3] : null));
        }
        note = sol ? (det.found ? "找到了哈密顿回路：每一步都是图里的边（绿线）" : `${(det.broken || []).length} 步不是图里的边（红虚线）——目标是 0`)
                   : "在这张图里找一条经过每个点恰好一次的回路。点「开始」。";
      } else {
        if (sol && det.path) det.path.forEach((a, i) => { if (i) seg(det.path[i - 1], a, red, 3); });
        note = sol ? `路径经过 ${det.path.length} 个点 · 权重和 ${det.weight}（沿排列延伸，碰到非边就停）` : "找权重和最大的简单路径。点「开始」。";
      }
      pts.forEach((q) => {
        const [x, y] = px(q);
        ctx.fillStyle = "#7aa2f7"; ctx.beginPath(); ctx.arc(x, y, 4.5, 0, 7); ctx.fill();
      });
      ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
      ctx.fillText(note, pad, H - 8);
      return;
    }
    if (variant === "carp" || variant === "rpostman") {
      // 路网 + 必需边 + 车次：粗彩线 = 服务的边（沿行走方向），虚线 = 空驶（最短路的直线示意）
      const pts = problem.pts, edges = problem.edges, dep = problem.depot;
      const px = (q) => [pad + 14 + (q[0] / 100) * (W - 2 * pad - 28), H - pad - 24 - (q[1] / 100) * (H - 2 * pad - 52)];
      const seg = (a, b, col, w, dash) => {
        const [x1, y1] = px(pts[a]), [x2, y2] = px(pts[b]);
        ctx.strokeStyle = col; ctx.lineWidth = w; ctx.setLineDash(dash || []);
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); ctx.setLineDash([]); ctx.lineWidth = 1;
      };
      edges.forEach(([a, b]) => seg(a, b, cvc("--cv-grid"), 1));
      problem.req.forEach((e) => seg(edges[e][0], edges[e][1], "#9aa0b0", 3));
      (det.trips || []).forEach((trip, r) => {
        const col = pal(r);
        let cur = dep;
        trip.forEach(([u, v]) => {
          if (cur !== u) seg(cur, u, col, 1.4, [4, 3]);
          seg(u, v, col, 3.6);
          cur = v;
        });
        if (cur !== dep) seg(cur, dep, col, 1.4, [4, 3]);
      });
      pts.forEach((q, i) => {
        const [x, y] = px(q);
        if (i === dep) { ctx.fillStyle = "#7aa2f7"; ctx.fillRect(x - 6, y - 6, 12, 12); return; }
        ctx.fillStyle = ink; ctx.beginPath(); ctx.arc(x, y, 3, 0, 7); ctx.fill();
      });
      ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
      ctx.fillText(det.trips ? `${det.trips.length} 趟${variant === "carp" ? "（容量 " + problem.cap + "）" : ""} · 总费用 ${det.cost}（服务费 + 空驶费）`
                             : `${problem.req.length} 条边必须服务${variant === "carp" ? "，车容量 " + problem.cap : "，一条回路覆盖全部"}。点「开始」。`, pad, H - 8);
      return;
    }
    if (["pmedian", "pcenter", "cflp", "lrp", "ndp"].includes(variant)) {
      // 选址 / 网络设计的点图：方块 = 设施（仓库），圆点 = 客户，细线 = 指派（或买下的边 / 车辆路线）
      const pts = problem.pts, dark = document.documentElement.getAttribute("data-theme") === "dark";
      const px = (q) => [pad + 14 + (q[0] / 100) * (W - 2 * pad - 28), H - pad - 24 - (q[1] / 100) * (H - 2 * pad - 52)];
      const red = "#e5484d", blue = "#7aa2f7", grey = cvc("--cv-grid");
      const line = (a, b, col, w, dash) => {
        const [x1, y1] = px(pts[a]), [x2, y2] = px(pts[b]);
        ctx.strokeStyle = col; ctx.lineWidth = w; ctx.setLineDash(dash || []);
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); ctx.setLineDash([]); ctx.lineWidth = 1;
      };
      const facCol = (i) => `hsl(${(i * 137.508) % 360}, 68%, ${dark ? 64 : 44}%)`;
      let fac = [], note = "", owner = null;
      if (variant === "pmedian" || variant === "pcenter") {
        fac = det.fac || [];
        owner = det.assign;
        if (owner) owner.forEach((f, i) => { if (f !== i) line(i, f, facCol(f), 1.4); });
        const far = det.dist ? Math.max(...det.dist) : 0, tot = det.dist ? det.dist.reduce((a, b) => a + b, 0) : 0;
        note = fac.length ? (variant === "pmedian" ? `${fac.length} 个设施 · 总距离 ${tot.toFixed(1)}（每个客户到最近设施的距离之和）`
                                                   : `${fac.length} 个设施 · 最远客户 ${far.toFixed(1)}（p-中心看最差的那一个）`)
                          : `在 ${problem.n} 个点里选 ${problem.p} 个当设施。点「开始」。`;
      } else if (variant === "cflp") {
        fac = det.open || [];
        owner = det.assign;
        if (owner) owner.forEach((f, i) => { if (f >= 0 && f !== i) line(i, f, facCol(f), 1.4); });
        note = fac.length ? `开了 ${fac.length} 个设施 · 固定费 ${det.fixed} · 总成本 ${lastState.best}${det.feasible ? "" : "（有客户派不下，已计罚）"}`
                          : `每个点既是客户也是候选设施；开设要付固定费，派给设施的客户不能超过容量。点「开始」。`;
      } else if (variant === "lrp") {
        fac = det.depots || [];
        (det.trips || []).forEach(([d, cs], r) => {
          const col = facCol(d), path = [d, ...cs, d];
          for (let k = 0; k < path.length - 1; k++) line(path[k], path[k + 1], col, 1.8, r % 2 ? [5, 3] : null);
        });
        note = fac.length ? `${fac.length} 个仓库 · ${det.trips.length} 趟车 · 路程 ${det.length} · 总成本 ${lastState.best}`
                          : `选 ${problem.p} 个点建仓库，其余客户由最近仓库派车配送。点「开始」。`;
      } else {
        const sel = det.sel || new Array(problem.n).fill(0);
        problem.edges.forEach(([a, b], k) => { if (!sel[k]) line(a, b, grey, 0.8, [2, 4]); });
        problem.edges.forEach(([a, b], k) => { if (sel[k]) line(a, b, blue, 2.4); });
        (problem.pairs || []).forEach(([a, b], k) => {
          const ok = det.connected ? det.connected[k] : false;
          line(a, b, ok ? cvc("--cv-ok") : red, 1.2, [6, 4]);
        });
        note = det.sel ? `买了 ${det.size} 条边 · 费用 ${det.cost} · ${det.connected.filter(Boolean).length}/${problem.pairs.length} 对需求已连通（绿虚线 = 通）`
                       : `灰点线 = 候选边；3 对需求点（虚线）必须被买下的边连通。点「开始」。`;
      }
      const isFac = new Set(fac), demandEnds = new Set((problem.pairs || []).flat());
      pts.forEach((q, i) => {
        const [x, y] = px(q);
        if (isFac.has(i)) { ctx.fillStyle = facCol(i); ctx.fillRect(x - 6, y - 6, 12, 12); return; }
        ctx.fillStyle = variant === "ndp" && demandEnds.has(i) ? red : blue;
        ctx.beginPath(); ctx.arc(x, y, variant === "ndp" && demandEnds.has(i) ? 5 : 4, 0, 7); ctx.fill();
      });
      ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
      ctx.fillText(note, pad, H - 8);
      return;
    }
    if (variant === "setpack" || variant === "hset" || variant === "tdm") {
      // 集合 × 元素 的 0/1 矩阵：setpack / tdm 选行（集合 / 三元组），hset 选列（元素）
      const sets = problem.sets, ne = sets[0].length, sel = det.sel || new Array(problem.n).fill(0);
      const x0 = pad + 40, y0 = pad + 22, cw = Math.min(34, (W - x0 - pad) / ne), ch = Math.min(30, (H - y0 - pad - 20) / sets.length);
      ctx.font = "11px sans-serif"; ctx.textAlign = "center";
      sets.forEach((row, i) => {
        ctx.fillStyle = ink; ctx.textAlign = "right"; ctx.fillText(`S${i}`, x0 - 8, y0 + i * ch + ch / 2 + 3); ctx.textAlign = "center";
        row.forEach((e, j) => {
          const on = variant !== "hset" ? sel[i] : sel[j];
          ctx.fillStyle = e ? (on ? cvc("--cv-best") : "#7aa2f7") : cvc("--cv-grid");
          ctx.globalAlpha = e ? 0.9 : 0.25; ctx.fillRect(x0 + j * cw + 1, y0 + i * ch + 1, cw - 2, ch - 2); ctx.globalAlpha = 1;
        });
      });
      if (variant === "hset") { ctx.fillStyle = ink; for (let j = 0; j < ne; j++) ctx.fillText(`${sel[j] ? "●" : ""}e${j}`, x0 + j * cw + cw / 2, y0 - 6); }
      ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
      const bad = det.violations || 0;
      ctx.fillText(variant === "tdm"
        ? (det.sel ? `选了 ${det.size} 个三元组（完美匹配 = ${det.q} 个）${bad ? ` · 有 ${bad} 处元素被重复占用` : "，两两不相交"} · 每行三个亮格 = 它的 X、Y、Z 元素` : `每个三元组取 X、Y、Z 各一个元素；选尽量多两两不相交的。点「开始」。`)
        : variant === "setpack"
        ? (det.sel ? `选了 ${det.size} 个集合${bad ? ` · 有 ${bad} 处元素被重复占用` : "，两两不相交"}（红 = 被选集合里的元素）` : "选尽量多的两两不相交的集合。点「开始」。")
        : (det.sel ? `选了 ${det.size} 个元素${bad ? ` · 还有 ${bad} 个集合没被击中` : "，每个集合都至少含一个（红 = 被选元素所在列）"}` : "选尽量少的元素，使每个集合都含其中至少一个。点「开始」。"),
        pad, H - 8);
      return;
    }
    if (variant === "mdvrp") {
      // 仓库 = 前 D 个点（方块，各一色），每条路线从自己的仓库出发、回到自己的仓库；客户按所属路线着色
      const pts = problem.pts, Dn = problem.D, routes = det.routes || [], owner = det.route_depot || [];
      const dark = document.documentElement.getAttribute("data-theme") === "dark";
      const depotCol = (d) => `hsl(${(d * 120 + 215) % 360}, 70%, ${dark ? 66 : 42}%)`;
      const hueOf = (r, d) => `hsl(${(d * 120 + 215 + (r % 5) * 17 - 34) % 360}, 66%, ${dark ? 62 : 48}%)`;
      const px = (q) => [pad + 6 + (q[0] / 100) * (W - 2 * pad - 12), 14 + (1 - q[1] / 100) * (H - 14 - 36)];
      const rOf = {};
      routes.forEach((route, r) => {
        const d = owner[r];
        ctx.strokeStyle = hueOf(r, d); ctx.lineWidth = 2.2; ctx.beginPath();
        [d, ...route, d].forEach((idx, i) => { const [x, y] = px(pts[idx]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
        ctx.stroke();
        route.forEach((c) => { rOf[c] = [r, d]; });
      });
      ctx.lineWidth = 1;
      pts.forEach((q, i) => {
        const [x, y] = px(q);
        if (i < Dn) { ctx.fillStyle = depotCol(i); ctx.fillRect(x - 6, y - 6, 12, 12); ctx.fillStyle = "#fff"; ctx.font = "9px sans-serif"; ctx.textAlign = "center"; ctx.fillText(String(i + 1), x, y + 3); ctx.textAlign = "left"; return; }
        ctx.fillStyle = rOf[i] ? hueOf(rOf[i][0], rOf[i][1]) : "#7aa2f7";
        ctx.beginPath(); ctx.arc(x, y, 3.8, 0, 7); ctx.fill();
      });
      ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
      ctx.fillText(routes.length
        ? `${routes.length} 辆车 · 各仓库用车 ${det.per_depot.join(" / ")}（每仓至多 ${problem.m_dep}）· 总里程 ${det.best}${det.within_fleet ? "" : "（有仓库切不进车队，已计罚）"}`
        : `${Dn} 个仓库（方块）各有 ${problem.m_dep} 辆车，客户由序列里的分隔符分给仓库。点「开始」。`, pad, H - 8);
      return;
    }
    if (variant === "vrptw" || variant === "vrpstw") {
      // 上：路线图（每辆车一种颜色，仓库 = 方块）；下：时间轴，每辆车一行——
      // 浅色宽条 = 该客户的时间窗 [e, l]，深色块 = 实际服务时段，细线 = 早到后的等待
      const pts = problem.pts, E = problem.e, L = problem.l, SV = problem.svc, Hd = L[0];
      const routes = det.routes || [], sched = det.sched || [];
      const rowH = routes.length ? Math.max(7, Math.min(14, (H * 0.36) / routes.length)) : 0;
      const stripH = rowH * routes.length;
      const mapH = H - stripH - 30;
      const px = (q) => [pad + 6 + (q[0] / 100) * (W - 2 * pad - 12), 14 + (1 - q[1] / 100) * (mapH - 22)];
      const dark = document.documentElement.getAttribute("data-theme") === "dark";
      const colOf = (r) => `hsl(${(r * 137.508) % 360}, 68%, ${dark ? 62 : 46}%)`;
      routes.forEach((route, r) => {
        ctx.strokeStyle = colOf(r); ctx.lineWidth = 2.2; ctx.beginPath();
        [0, ...route, 0].forEach((idx, i) => { const [x, y] = px(pts[idx]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
        ctx.stroke();
      });
      ctx.lineWidth = 1;
      const rOf = {};
      routes.forEach((route, r) => route.forEach((c) => { rOf[c] = r; }));
      pts.forEach((q, i) => {
        const [x, y] = px(q);
        if (i === 0) { ctx.fillStyle = "#7aa2f7"; ctx.fillRect(x - 5, y - 5, 10, 10); return; }
        ctx.fillStyle = rOf[i] === undefined ? "#7aa2f7" : colOf(rOf[i]);
        ctx.beginPath(); ctx.arc(x, y, 4, 0, 7); ctx.fill();
      });
      if (routes.length) {
        const x0 = pad + 26, x1 = W - pad, T = (t) => x0 + (t / Hd) * (x1 - x0), y0 = mapH + 4;
        ctx.strokeStyle = cvc("--cv-grid"); ctx.strokeRect(x0 - 0.5, y0 - 2, x1 - x0 + 1, stripH + 3);
        routes.forEach((route, r) => {
          const y = y0 + r * rowH;
          ctx.fillStyle = colOf(r); ctx.font = "9px sans-serif"; ctx.textAlign = "right";
          ctx.fillText(`车${r + 1}`, x0 - 4, y + rowH - 3);
          route.forEach((c, k) => {
            const [arr, st, lv] = sched[r][k];
            ctx.globalAlpha = 0.28; ctx.fillStyle = colOf(r);
            ctx.fillRect(T(E[c]), y, Math.max(1, T(L[c]) - T(E[c])), rowH - 2);
            ctx.globalAlpha = 1;
            ctx.fillRect(T(st), y + 1, Math.max(1.5, T(lv) - T(st)), rowH - 4);
            if (arr > L[c] + 0.01) { ctx.fillStyle = "#e5484d"; ctx.fillRect(T(L[c]), y, Math.max(1.5, T(arr) - T(L[c])), 2.5); ctx.fillStyle = colOf(r); }  // 软窗：红条 = 窗口关闭后又过了多久才到
            if (st > arr + 0.01) { ctx.fillStyle = ink; ctx.fillRect(T(arr), y + rowH - 3, T(st) - T(arr), 1.5); }
          });
        });
        ctx.fillStyle = ink; ctx.font = "9px sans-serif"; ctx.textAlign = "left";
        ctx.fillText("0", x0, y0 + stripH + 10); ctx.textAlign = "right"; ctx.fillText(String(Hd), x1, y0 + stripH + 10);
        ctx.textAlign = "left";
      }
      ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
      const soft = variant === "vrpstw";
      ctx.fillText(routes.length
        ? (soft ? `${routes.length} 辆车（至多 ${problem.m_veh}）· 里程 ${det.dist} + ${problem.lam} × 迟到 ${det.late} = ${det.best}${det.within_fleet ? "" : "（切不进车队，已计罚）"} · 等待 ${det.wait}`
                : `${routes.length} 辆车（至多 ${problem.m_veh}）· 总里程 ${det.best}${det.within_fleet ? "" : "（还切不进车队，已按多用的车计罚）"} · 等待共 ${det.wait}`)
        : (soft ? `每个客户有一个时间窗 [e, l]：早到要等，晚到可以、但每晚 1 个单位罚 ${problem.lam} 个里程。点「开始」。`
                : `每个客户有一个时间窗 [e, l]：早到要等、晚到不行，还得在 ${Hd} 前回仓库。点「开始」。`), pad, H - 8);
      return;
    }
    if (variant === "orienteering") {
      // 点大小 ∝ 收益；红线 = 路线（仓库出发、回到仓库）；走过的点实心，没去的点空心
      const pts = problem.pts, gain = problem.gain, route = det.route || [0, 0];
      const px = (q) => [pad + 14 + (q[0] / 100) * (W - 2 * pad - 28), H - pad - 24 - (q[1] / 100) * (H - 2 * pad - 52)];
      const visited = new Set(route);
      if (det.route) {
        ctx.strokeStyle = "#e5484d"; ctx.lineWidth = 2.4; ctx.beginPath();
        route.forEach((j, i) => { const [x, y] = px(pts[j]); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); });
        ctx.stroke(); ctx.lineWidth = 1;
      }
      pts.forEach((q, i) => {
        const [x, y] = px(q);
        if (i === 0) { ctx.fillStyle = "#7aa2f7"; ctx.fillRect(x - 6, y - 6, 12, 12); return; }
        const r = 3 + gain[i] / 4;
        ctx.beginPath(); ctx.arc(x, y, r, 0, 7);
        if (visited.has(i)) { ctx.fillStyle = "#e5484d"; ctx.fill(); } else { ctx.strokeStyle = ink; ctx.stroke(); }
      });
      ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
      ctx.fillText(det.route ? `收益 ${det.score} / 全部 ${det.total_gain} · 路程 ${det.length} / 预算 ${det.budget}（红 = 去了，空心 = 没去，圆越大收益越高）`
                             : `预算 ${problem.budget}，走不完所有点——挑值得去的。点「开始」。`, pad, H - 8);
      return;
    }
    if (variant === "rcpsp") {
      // 甘特：每行一个活动，宽度 = 工期；绿虚线 = 工期下界
      const start = det.start, end = det.end, n = problem.n, mx = Math.max(1, ...(end || [1]), det.lb || 0);
      const x0 = pad + 36, x1 = W - pad - 8, rowH = Math.min(24, (H - 2 * pad - 30) / n);
      ctx.font = "11px sans-serif"; ctx.textAlign = "left";
      for (let a = 0; a < n; a++) {
        const y = pad + 20 + a * rowH;
        ctx.fillStyle = ink; ctx.fillText(`A${a}`, pad + 2, y + rowH / 2 + 3);
        if (start) {
          ctx.fillStyle = pal(a); ctx.globalAlpha = 0.9;
          ctx.fillRect(x0 + (start[a] / mx) * (x1 - x0), y + 2, Math.max(2, (problem.dur[a] / mx) * (x1 - x0) - 1), rowH - 4);
          ctx.globalAlpha = 1;
        }
      }
      if (det.lb) {
        const lx = x0 + (det.lb / mx) * (x1 - x0);
        ctx.strokeStyle = cvc("--cv-ok"); ctx.setLineDash([4, 3]);
        ctx.beginPath(); ctx.moveTo(lx, pad + 14); ctx.lineTo(lx, pad + 20 + n * rowH); ctx.stroke(); ctx.setLineDash([]);
      }
      ctx.fillStyle = ink; ctx.font = "12px sans-serif";
      ctx.fillText(start ? `项目工期 ${det.makespan} · 下界 ${det.lb}（绿虚线：关键路径与资源总量的较大者）` : `${n} 个活动、2 种资源（容量各 ${problem.caps[0]}）。点「开始」。`, pad + 2, pad + 10);
      return;
    }
    if (variant === "pms") {
      // 并行机甘特：每台机器一行，作业按先后排成一串，宽度 ∝ 加工时间；竖虚线 = 下界
      const machines = det.machines || [], loads = det.loads || [];
      const m = problem.m_mach, mx = Math.max(1, ...(loads.length ? loads : [1]), det.lb || 0);
      const x0 = pad + 56, x1 = W - pad - 8, rowH = Math.min(46, (H - 2 * pad - 40) / m);
      ctx.font = "11px sans-serif"; ctx.textAlign = "left";
      for (let i = 0; i < m; i++) {
        const y = pad + 24 + i * rowH;
        ctx.fillStyle = ink; ctx.fillText(`机器 ${i + 1}`, pad + 4, y + rowH / 2 + 3);
        let t = 0;
        (machines[i] || []).forEach((j) => {
          const w = (problem.p[j] / mx) * (x1 - x0);
          ctx.fillStyle = pal(j); ctx.globalAlpha = 0.9;
          ctx.fillRect(x0 + (t / mx) * (x1 - x0), y + 3, Math.max(1, w - 1), rowH - 8);
          ctx.globalAlpha = 1;
          if (w > 16) { ctx.fillStyle = "#fff"; ctx.fillText(String(j), x0 + (t / mx) * (x1 - x0) + 3, y + rowH / 2 + 3); }
          t += problem.p[j];
        });
      }
      if (det.lb) {
        const lx = x0 + (det.lb / mx) * (x1 - x0);
        ctx.strokeStyle = cvc("--cv-ok"); ctx.setLineDash([4, 3]);
        ctx.beginPath(); ctx.moveTo(lx, pad + 18); ctx.lineTo(lx, pad + 24 + m * rowH); ctx.stroke(); ctx.setLineDash([]);
      }
      ctx.fillStyle = ink; ctx.font = "12px sans-serif";
      ctx.fillText(loads.length ? `最大完工时间 ${Math.max(...loads)} · 下界 ${det.lb}（绿虚线）· 各机负载 ${loads.join(" / ")}`
                                : `${problem.n} 个作业分到 ${m} 台机器；点「开始」看分配。`, pad + 4, pad + 12);
      return;
    }
    if (variant === "numpart") {
      // 每个数一根柱（高 ∝ 数值），红 = 集合 A，蓝 = 集合 B
      const a = problem.a, side = det.side, mx = Math.max(...a);
      const bw = (W - 2 * pad) / a.length, base = H - pad - 18, hmax = H - 2 * pad - 50;
      a.forEach((v, i) => {
        ctx.fillStyle = side ? (side[i] ? cvc("--cv-best") : "#7aa2f7") : cvc("--cv-grid");
        const h = (v / mx) * hmax;
        ctx.fillRect(pad + i * bw + 1, base - h, Math.max(1, bw - 2), h);
      });
      ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
      ctx.fillText(side ? `集合 A（红）= ${det.sum_a} · 集合 B（蓝）= ${det.sum_b} · 差 = ${Math.abs(det.sum_a - det.sum_b)}（0 = 完美划分）`
                        : `${a.length} 个数要分成两组使两组之和尽量相等。点「开始」。`, pad, pad + 14);
      return;
    }
    if (variant === "kmeans") {
      const xs = problem.pts.map((q) => q[0]), ys = problem.pts.map((q) => q[1]);
      const lo = [Math.min(...xs), Math.min(...ys)], hi = [Math.max(...xs), Math.max(...ys)];
      const px = (q) => [pad + 10 + ((q[0] - lo[0]) / Math.max(1e-9, hi[0] - lo[0])) * (W - 2 * pad - 20),
                          H - pad - 10 - ((q[1] - lo[1]) / Math.max(1e-9, hi[1] - lo[1])) * (H - 2 * pad - 30)];
      problem.pts.forEach((q, i) => {
        const [x, y] = px(q);
        ctx.fillStyle = det.assign ? pal(det.assign[i]) : "#7aa2f7"; ctx.globalAlpha = 0.75;
        ctx.beginPath(); ctx.arc(x, y, 3.5, 0, 7); ctx.fill(); ctx.globalAlpha = 1;
      });
      (det.centers || []).forEach((c, i) => {
        const [x, y] = px(c);
        ctx.strokeStyle = pal(i); ctx.lineWidth = 3;
        ctx.beginPath(); ctx.moveTo(x - 8, y - 8); ctx.lineTo(x + 8, y + 8); ctx.moveTo(x + 8, y - 8); ctx.lineTo(x - 8, y + 8); ctx.stroke();
        ctx.lineWidth = 1;
      });
      ctx.fillStyle = ink; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
      ctx.fillText(det.centers ? `${problem.k} 个簇 · 误差平方和 SSE = ${lastState.best}（越小越好）· ✕ = 聚类中心`
                               : `${problem.pts.length} 个点，要找 ${problem.k} 个中心。点「开始」。`, pad, pad + 12);
      return;
    }
    if (["wbeam", "pvessel", "tcspring", "reducer"].includes(variant)) {
      // 左：各设计变量在取值范围里的位置；右：各约束是否满足（g ≤ 0 为满足）
      const names = det.names || [], bounds = det.bounds || [], x = det.x || [], g = det.g || [];
      ctx.font = "12px sans-serif"; ctx.textAlign = "left";
      ctx.fillStyle = ink;
      ctx.fillText(det.x ? `目标 f = ${det.f}${det.feasible ? "（可行）" : "（有约束被违反，已按罚函数计入）"} · 文献最优 ${det.best_known}`
                         : "点「开始」，看设计变量和约束怎么一步步被满足。", pad, pad + 12);
      const half = (W - 2 * pad) / 2;
      (names.length ? names : []).forEach((nm, i) => {
        const y = pad + 34 + i * 30, lo = bounds[i][0], hi = bounds[i][1];
        ctx.fillStyle = ink; ctx.fillText(`${nm} = ${x[i]}`, pad, y);
        ctx.strokeStyle = cvc("--cv-grid"); ctx.strokeRect(pad, y + 5, half - 20, 7);
        ctx.fillStyle = cvc("--cv-best");
        ctx.fillRect(pad, y + 5, Math.max(2, ((x[i] - lo) / (hi - lo)) * (half - 20)), 7);
      });
      g.forEach((v, i) => {
        const y = pad + 34 + i * 17;
        ctx.fillStyle = v <= 1e-9 ? cvc("--cv-ok") : "#e5484d";
        ctx.fillText(`${v <= 1e-9 ? "✓" : "✗"} g${i + 1} = ${v}`, pad + half + 10, y);
      });
      return;
    }
    if (["vrp", "atsp"].includes(variant)) {
      // 路径/回路：点+顺序连线（仓库方块）
      const pts = problem.pts || [];
      ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--cv-grid") || "#888";
      ctx.fillStyle = "#7aa2f7";
      pts.forEach((pt, i2) => {
        const x = pad + (pt[0] / 110) * (W - 2 * pad), y = H - pad - (pt[1] / 110) * (H - 2 * pad);
        if (i2 === 0 && variant === "vrp") ctx.fillRect(x - 4, y - 4, 8, 8);
        else { ctx.beginPath(); ctx.arc(x, y, 5, 0, 7); ctx.fill(); }
      });
      if (variant === "vrp" && lastState && lastState.routes) {
        // 多车路线：每辆车一种颜色，仓库出发、回到仓库；标出每辆车的载重 / 容量
        const px = (pt) => [pad + (pt[0] / 110) * (W - 2 * pad), H - pad - (pt[1] / 110) * (H - 2 * pad)];
        lastState.routes.forEach((route, r) => {
          const col = `hsl(${(r * 137.508) % 360}, 68%, ${document.documentElement.getAttribute("data-theme") === "dark" ? 62 : 46}%)`;
          ctx.strokeStyle = col; ctx.lineWidth = 2.4; ctx.beginPath();
          [0, ...route, 0].forEach((idx, i2) => {
            const [x, y] = px(pts[idx]);
            i2 === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
          });
          ctx.stroke();
          const load = route.reduce((a, idx) => a + problem.demand[idx], 0);
          const [lx, ly] = px(pts[route[0]]);
          ctx.fillStyle = col; ctx.font = "11px sans-serif"; ctx.textAlign = "left";
          ctx.fillText(`车${r + 1} ${load}/${problem.cap}`, lx + 6, ly - 6);
        });
        ctx.lineWidth = 1;
        ctx.fillStyle = "#9aa0b0"; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
        ctx.fillText(`${lastState.routes.length} 辆车（至多 ${problem.m_veh}）· 容量 ${problem.cap} · 总里程 ${lastState.best}`, pad, H - 6);
      } else if (sol && sol.length) {
        const order = ["vrp"].includes(variant) ? [0, ...sol.map((x) => x + 1), 0] : sol;
        ctx.strokeStyle = "#e5484d"; ctx.lineWidth = 2; ctx.beginPath();
        order.forEach((idx, i2) => {
          const pt = pts[idx]; if (!pt) return;
          const x = pad + (pt[0] / 110) * (W - 2 * pad), y = H - pad - (pt[1] / 110) * (H - 2 * pad);
          i2 === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        });
        if (variant !== "lpath") ctx.closePath();
        ctx.stroke(); ctx.lineWidth = 1;
        if (variant === "atsp") { // 非对称：去程与回程代价不同，所以要画方向
          ctx.fillStyle = "#e5484d";
          order.forEach((idx, i2) => {
            const a = pts[idx], b = pts[order[(i2 + 1) % order.length]]; if (!a || !b) return;
            const ax = pad + (a[0] / 110) * (W - 2 * pad), ay = H - pad - (a[1] / 110) * (H - 2 * pad);
            const bx = pad + (b[0] / 110) * (W - 2 * pad), by = H - pad - (b[1] / 110) * (H - 2 * pad);
            const ang = Math.atan2(by - ay, bx - ax), mx = (ax + bx) / 2, my = (ay + by) / 2;
            ctx.beginPath(); ctx.moveTo(mx + 7 * Math.cos(ang), my + 7 * Math.sin(ang));
            ctx.lineTo(mx - 5 * Math.cos(ang) + 4 * Math.sin(ang), my - 5 * Math.sin(ang) - 4 * Math.cos(ang));
            ctx.lineTo(mx - 5 * Math.cos(ang) - 4 * Math.sin(ang), my - 5 * Math.sin(ang) + 4 * Math.cos(ang));
            ctx.closePath(); ctx.fill();
          });
        }
      }
    } else {
      // 调度/排序：作业条形时间线（甘特风格简化）
      const items = sol || Array.from({ length: n }, (_, i2) => i2);
      const colors = ["#7aa2f7", "#9ece6a", "#f7768e", "#e0af68", "#bb9af7", "#4fd6be"];
      const rowH = Math.min(26, (H - 2 * pad) / Math.max(1, n));
      const scale = (W - 2 * pad - 70) / Math.max(60, items.length * 14);
      items.forEach((job, i2) => {
        const y = pad + i2 * rowH;
        const wpx = (variant === "sms" ? (problem.p ? problem.p[job] : 6) : 6) * scale * 3;
        ctx.fillStyle = colors[job % colors.length];
        ctx.fillRect(pad + 60, y + 4, Math.max(14, wpx), rowH - 8);
        ctx.fillStyle = "#9aa0b0"; ctx.font = "11px sans-serif"; ctx.textAlign = "left";
        ctx.fillText(`#${job}`, pad + 8, y + rowH / 2 + 4);
      });
      ctx.fillStyle = "#9aa0b0"; ctx.font = "11px sans-serif"; ctx.textAlign = "left";
      ctx.fillText(variant === "sms" ? "条长=加工时长（红段为延误）" : "甘特条：作业 × 机器（教学级解码）",
                   pad + 60, H - pad + 2);
    }
    return;
  }
if (vt === "mckp" || vt === "dkp") {
    const k = problem.k, r = problem.r, dk = vt === "dkp";
    const cw = (W - pad * 2) / r, chh = (H - 70) / k;
    for (let c = 0; c < k; c++) {
      for (let j = 0; j < r; j++) {
        const i = c * r + j;
        const x = pad + j * cw, y = 40 + c * chh;
        const on = sol && sol[i];
        ctx.fillStyle = on ? cvc("--cv-best") : cvc("--cv-grid");
        ctx.globalAlpha = on ? 0.9 : 0.35;
        ctx.fillRect(x + 2, y + 2, cw - 4, chh - 4);
        ctx.globalAlpha = 1;
        ctx.fillStyle = cvc("--cv-ink");
        ctx.font = "10px sans-serif";
        ctx.fillText((dk ? ["A ", "B ", "A+B "][j] : "") + `w${problem.w2[c][j]} v${problem.v2[c][j]}`, x + 5, y + chh / 2 + 3);
      }
    }
    let total = 0, val = 0;
    if (sol) for (let i = 0; i < k * r; i++) if (sol[i]) { total += problem.w2[(i / r) | 0][i % r]; val += problem.v2[(i / r) | 0][i % r]; }
    ctx.fillStyle = cvc("--cv-ink");
    ctx.font = "12px sans-serif";
    ctx.fillText(sol
      ? `目标 ${state.best} · 选中重量 ${total}/${problem.cap} · 每行=一${dk ? "组" : "类"}（亮=该${dk ? "组" : "类"}所选，至多一个）`
      : (dk ? `${k} 组，每组可选 A、B 或捆绑 A+B（重量打 75 折）中的一个，总重 ≤ ${problem.cap}。点「开始」看选择。`
            : `${k} 类 × ${r} 件，每类至多选一件、总重 ≤ ${problem.cap}。点「开始」看选择。`), pad, 20);
    return;
  }

  // 位编码变体：物品柱（items 字段变体用展开列表，w/v 字段变体用数组）
  const items = problem.items ? problem.items : problem.w.map((w, i) => [w, problem.v[i]]);
  const n = items.length;
  const bw = (W - pad * 2) / n;
  const vmax = Math.max(...items.map((it) => it[0]), 1);
  const isSsp = vt === "ssp", isCmp = vt === "cmp";
  for (let i = 0; i < n; i++) {
    const h = (items[i][0] / vmax) * (H - pad * 2 - 46);
    const x = pad + i * bw, y = H - pad - 30 - h;
    const on = sol && sol[i];
    ctx.fillStyle = on ? cvc("--cv-best") : cvc("--cv-grid");
    ctx.fillRect(x + 0.5, y, Math.max(1, bw - 2), h);
    if (on && vt === "dkp" && problem.partner) {
      const p = problem.partner[i];
      if (sol[p]) {  // partner 也选中 → 本件重量打折，标绿框
        ctx.strokeStyle = cvc("--cv-ok");
        ctx.strokeRect(x + 0.5, y - 0.5, Math.max(1, bw - 2), h + 1);
      }
    }
  }
  // 目标线（ssp：重量=target；cmp：金额=T）
  const target = isSsp ? problem.target : (isCmp ? problem.T : null);
  if (target !== null) {
    const ty = H - pad - 30 - (Math.min(target, vmax) / vmax) * (H - pad * 2 - 46);
    ctx.strokeStyle = cvc("--cv-ok");
    ctx.setLineDash([5, 4]);
    ctx.beginPath(); ctx.moveTo(pad, ty); ctx.lineTo(W - pad, ty); ctx.stroke();
    ctx.setLineDash([]);
  }
  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "12px sans-serif";
  if (!sol) {
    const label = { fractional: "0-1 演示（LP 上界=密度排序+末件取分数）", bkp: "同一件有多个拷贝",
                    ukp: "每件 ≤3 份", cmp: `凑出金额 ${problem.T}、枚数最少`, ssp: `子集重量恰好=${problem.target}`,
                    mdkp: "三个资源维度各有各的重量与容量，同时满足", dkp: "每组选 A、B 或打折捆绑", qkp: "物品两两协同 Q" }[vt] || vt;
    ctx.fillText(`每根柱 = 一份物品（高度=重量）。${label}。点「开始」求解。`, pad, H - 8);
    return;
  }
  let total = 0, cnt = 0;
  for (let i = 0; i < n; i++) if (sol[i]) { total += items[i][0]; cnt++; }
  let tail;
  if (isCmp) tail = `选中 ${cnt} 枚 · 金额 ${total}/${problem.T}`;
  else if (isSsp) tail = `选中 ${cnt} 件 · 重量 ${total}，|Σ-T|=${Math.abs(total - problem.target)}`;
  else if (vt === "mdkp") {
    const loads = problem.W.map((row) => row.reduce((a, w, i) => a + (sol[i] ? w : 0), 0));
    tail = `选中 ${cnt} 件 · 三个维度 载荷/容量：` + loads.map((l, d) => `${l}/${problem.caps[d]}`).join("  ");
  }
  else tail = `选中 ${cnt}/${n} · 重量 ${total}/${problem.cap}`;
  ctx.fillText(`目标 ${state.best} · ${tail}`, pad, H - 8);
}

// ---------------- 域：着色家族 gcvar（H2 单域多预设） ----------------
// 5 变体按 state/problem.variant 分支：listcolor/precolor=顶点染色（复用 drawGC 布局约定，
// 绿/各色=合法 金圈=预染顶点）；edgecolor=边染色视角（颜色=边）；
// totalcolor=顶点+边双色；mis=选中集合高亮（绿=选中，互不相邻）。

function drawGCVAR(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!problem) return;

  const pos = problem.pos, edges = problem.edges, n = problem.n;
  const vt = problem.variant;
  const col = state ? state.best_sol : null;
  const r = n > 70 ? 5 : 7;
  const light = document.documentElement.getAttribute("data-theme") === "dark";
  const isTC = vt === "totalcolor";

  // 边层（edgecolor/totalcolor 按 col 着色；其余灰）
  ctx.lineWidth = 1;
  for (let i = 0; i < edges.length; i++) {
    const [u, v] = edges[i];
    const x1 = pos[u][0] / 100 * W, y1 = pos[u][1] / 100 * H;
    const x2 = pos[v][0] / 100 * W, y2 = pos[v][1] / 100 * H;
    if (vt === "edgecolor" || isTC) {
      const ci = isTC ? col[n + i] : col[i];
      ctx.strokeStyle = col ? gcPalette(ci) : cvc("--cv-grid");
      ctx.lineWidth = col ? 2.5 : 1;
    } else {
      ctx.strokeStyle = cvc("--cv-grid");
      ctx.lineWidth = 1;
    }
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
  }

  // 顶点层
  for (let i = 0; i < n; i++) {
    const x = pos[i][0] / 100 * W, y = pos[i][1] / 100 * H;
    let fill;
    if (vt === "edgecolor") {
      fill = cvc("--cv-ink");
    } else if (vt === "mis") {
      fill = (col && col[i]) ? (light ? "#34d399" : "#059669") : cvc("--cv-grid");
    } else {
      fill = col ? gcPalette(col[i]) : cvc("--cv-sub");
    }
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fillStyle = fill; ctx.fill();
    if (vt === "precolor" && problem.precol && problem.precol[i] >= 0) {
      ctx.lineWidth = 2; ctx.strokeStyle = light ? "#fbbf24" : "#d97706"; ctx.stroke();
    }
    if (vt === "listcolor" && problem.lists && problem.lists[i]) {
      // 候选色列表可视化：顶点外环按角度均分画候选色弧段（当前色必须∈列表）
      const cands = problem.lists[i];
      const seg = (Math.PI * 2) / cands.length;
      ctx.lineWidth = 2.5;
      for (let j = 0; j < cands.length; j++) {
        ctx.strokeStyle = gcPalette(cands[j]);
        ctx.beginPath();
        ctx.arc(x, y, r + 3.5, j * seg - Math.PI / 2, (j + 1) * seg - Math.PI / 2);
        ctx.stroke();
      }
    }
  }

  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "12px sans-serif";
  let msg;
  if (!state) {
    msg = "点「开始」后自动着色：各色=合法，相邻同色即冲突（红不可用，本族以相邻异色为准）。";
  } else if (vt === "edgecolor") {
    const k = col ? Math.max(...col) + 1 : 0;
    msg = `边色数 ${k} · 边 ${edges.length} · 下界 Δ（Vizing 定理 χ'=Δ 或 Δ+1）· 颜色=边染色`;
  } else if (isTC) {
    const k = col ? Math.max(...col) + 1 : 0;
    const vc = col ? col.slice(0, n) : null;
    const vk = vc ? Math.max(...vc) + 1 : 0;
    msg = `总色数 ${k}（顶点 ${vk} · 边 ${k - vk}）· 顶点与边同时着色，关联也要异色`;
  } else if (vt === "mis") {
    const sz = col ? col.reduce((a, b) => a + b, 0) : 0;
    msg = `独立集大小 ${sz} · 顶点 ${n} · 绿=选中（互不相邻）`;
  } else {
    const k = col ? Math.max(...col) + 1 : 0;
    msg = `色数 ${k} · 顶点 ${n} · 边 ${edges.length} · 颜色=顶点着色（相邻异色）`;
  }
  ctx.fillText(msg, 14, 20);
}

// UFLP：平面地图——方块=设施（大开/灰关），圆点=客户，线=指派关系
function drawUF(state) {
  const cv = $("vizCanvas");
  const dpr = window.devicePixelRatio || 1;
  const W = cv.clientWidth, H = cv.clientHeight;
  if (cv.width !== W * dpr) { cv.width = W * dpr; cv.height = H * dpr; }
  const ctx = cv.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, W, H);
  if (!problem) return;

  const { n_f, n_c, f_cost, pos_f, pos_c } = problem;
  const sol = state ? state.best_sol : null;
  const X = (p) => p[0] / 100 * W, Y = (p) => p[1] / 100 * H;

  // 指派关系（从 best_sol 重算 cheapest-open，与 py 端 _UF.assign 同规则）
  let assign = null;
  if (sol) {
    assign = [];
    for (let j = 0; j < n_c; j++) {
      let ba = -1, bc = Infinity;
      for (let a = 0; a < n_f; a++) {
        if (!sol[a]) continue;
        if (problem.c_cost[a][j] < bc) { bc = problem.c_cost[a][j]; ba = a; }
      }
      assign.push(ba);
    }
    // 客户→设施线（画在方块下层）
    ctx.strokeStyle = cvc("--cv-grid");
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let j = 0; j < n_c; j++) {
      if (assign[j] < 0) continue;
      ctx.moveTo(X(pos_c[j]), Y(pos_c[j]));
      ctx.lineTo(X(pos_f[assign[j]]), Y(pos_f[assign[j]]));
    }
    ctx.stroke();
  }
  // 客户点
  for (let j = 0; j < n_c; j++) {
    ctx.beginPath();
    ctx.arc(X(pos_c[j]), Y(pos_c[j]), 3, 0, Math.PI * 2);
    ctx.fillStyle = cvc("--cv-sub");
    ctx.fill();
  }
  // 设施方块
  for (let a = 0; a < n_f; a++) {
    const on = sol && sol[a];
    const x = X(pos_f[a]), y = Y(pos_f[a]);
    ctx.fillStyle = on ? cvc("--cv-best") : cvc("--cv-grid");
    ctx.globalAlpha = on ? 1 : 0.45;
    const s = on ? 13 : 9;
    ctx.fillRect(x - s / 2, y - s / 2, s, s);
    ctx.globalAlpha = 1;
    ctx.fillStyle = on ? "#fff" : cvc("--cv-sub");
    ctx.font = "9px sans-serif";
    ctx.fillText(`F${a}`, x - 7, y - s / 2 - 2);
  }
  ctx.fillStyle = cvc("--cv-ink");
  ctx.font = "12px sans-serif";
  if (sol) {
    const k = sol.reduce((a, b) => a + b, 0);
    ctx.fillText(`开 ${k}/${n_f} 个设施 · 总成本 ${state.best}（固定+指派）· 方块=设施 圆点=客户 线=指派`, 14, 18);
  } else {
    ctx.fillText(`方块=候选设施（标注=编号），圆点=客户。点「开始」决定开哪些设施、每个客户找最近的开设施，总成本=固定成本+指派成本。`, 14, 18);
  }
}

// ---------------- 生命周期 ----------------

function onStarted() {
  moBounds = null;
  mo3Bounds = null;
  heatImg = null;
}

// ---------------- 单步与导出（2026-09-28 用户裁定补齐）----------------

let singleMode = false; // 单步模式：started 回包不自动连跑

function singleStep() {
  if (!ready || !problem) return setStatus("实例尚未生成，无法单步", "err");
  if (running) return setStatus("运行中：请先「暂停」再单步", "");
  singleMode = true;
  if (!lastState || !runActive) {
    startRun(); // 没有可接着跑的运行：先 start（started 回包按单步模式推进一代）
  } else {
    postStep(); // 已开始（含暂停中）：直接推进一代
  }
}

function domDownloadCanvas(cv, name) {
  const a = document.createElement("a");
  a.download = name;
  a.href = cv.toDataURL("image/png");
  a.click();
}

function exportVizPng() {
  const cv = $("vizCanvas");
  if (!cv || !lastState) return setStatus("尚无图像可导出（先运行至少一代）", "err");
  const algoVal = ($("algoSel") || {}).value || "algo";
  domDownloadCanvas(cv, `${DOMAIN}-${algoVal}-viz.png`);
  setStatus("图像已导出（PNG）", "ok");
}

function exportConvPng() {
  const cv = $("convCanvas");
  if (!cv || history.length < 2) return setStatus("尚无收敛曲线可导出（至少运行两代）", "err");
  const algoVal = ($("algoSel") || {}).value || "algo";
  domDownloadCanvas(cv, `${DOMAIN}-${algoVal}-conv.png`);
  setStatus("收敛曲线已导出（PNG）", "ok");
}

// 按钮触发时取快照，异步加载模块期间的控件变动不影响本次导出。
function exportSnapshot() {
  const record = runRecord || { problem, algo: $("algoSel").value, params: currentParams() };
  return JSON.parse(JSON.stringify({ ...record, history: runRecord ? history : [],
    state: runRecord ? lastState : null, info: runRecord ? info : null }));
}

function exportHistoryCsv() {
  if (!history.length) return setStatus("尚无迭代数据可导出（先运行）", "err");
  const snap = exportSnapshot();
  const algoVal = snap.algo;
  const lines = [
    `# domain=${DOMAIN} algo=${algoVal} seed=${snap.params.seed} max_iter=${snap.params.max_iter}`,
    `# exportedAt=${new Date().toISOString()}`,
    "iter,best,cur",
  ];
  for (const h of snap.history) lines.push(`${h.iter},${h.best},${h.cur ?? ""}`);
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `${DOMAIN}-${algoVal}-history-${Date.now()}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  setStatus("迭代历史已导出（CSV）", "ok");
}

document.addEventListener("DOMContentLoaded", () => {
  $("btnStart").onclick = () => {
    singleMode = false;
    if (runActive && !running && ready) { // 暂停后继续：接着上次的进度跑
      runT0 = performance.now() - runElapsed; // 估时只算真正在跑的时间，不含暂停
      setStatus("运行中…", "busy");
      startTimer();
      return;
    }
    startRun();
  };
  // 改了算法 / 参数 / 迭代次数：之前暂停的运行不再对应当前设置，下次「开始」应重新开始
  $("algoSel").addEventListener("change", () => { runActive = false; });
  $("tuneBox").addEventListener("input", () => { runActive = false; });
  $("iterInp").addEventListener("input", () => { runActive = false; });
  $("btnStop").onclick = () => { stopTimer(); setStatus("已暂停", ""); };
  $("btnReset").onclick = () => {
    runActive = false;
    stopTimer();
    history = [];
    lastState = null;
    moBounds = null;
    mo3Bounds = null;
    heatImg = null;
    loadPreset();
    drawConv();
    setStatus("已重置", "ok");
  };

  // ---- 修5（2026-09-27 用户需求）：域页结果导出 + 自定义实例导入 ----
  // 导入的 problem 直接替换全局 problem 对象（start 时原样传给 worker，
  // 与 preset 回包同构），无需改 worker 协议；结构错误在 start 时由
  // Python 端报错显示到状态行，前端只做温和前置校验。
  // 结果导出：swarm-result/v1（与命令行同一格式；带完整实例，可用 `python swarm.py replay` 复现，
  // 也可以把导出的文件再「导入实例」——校验器认得它里面的 problem）
  $("btnExportDom").onclick = async () => {
    if (!problem) return setStatus("实例尚未生成，无法导出", "err");
    if (!lastState || !runParams) return setStatus("还没有运行结果可导出：先点「开始」跑一次", "err");
    const snap = exportSnapshot();
    const R = await import(PREFIX + "js/result_export.js");
    const key = "best" in snap.state ? "best" : "nd";
    const res = R.buildResult({
      domain: DOMAIN, variant: snap.problem.variant || null,
      algo: snap.algo, algoName: snap.algoName,
      seed: snap.params.seed, iters: snap.params.max_iter,
      completedIters: snap.state.iter, params: R.algoParams(snap.params),
      sense: key === "nd" ? "max" : (snap.info && snap.info.sense) || "min",
      best: snap.state[key], bestSolution: snap.state.best_sol ?? null,
      elapsed: null, curve: snap.history.map((h) => [h.iter, h.best]),
      problem: snap.problem,
    });
    R.downloadJson(res, `${DOMAIN}-${snap.algo}-result.json`);
    setStatus("结果已导出（swarm-result/v1，可用 python swarm.py replay 复现）", "ok");
  };
  // ---- 单步 / PNG / CSV（2026-09-28 用户裁定补齐：问题页引擎与 algo 页能力对齐）----
  $("btnStep").onclick = singleStep;
  $("btnPngDom").onclick = exportVizPng;
  $("btnConvDom").onclick = exportConvPng;
  $("btnCsvDom").onclick = exportHistoryCsv;
  $("btnImportDom").onclick = () => $("domFileInput").click();

  // 实验包（2026-09-27 用户需求：算法和数据一起导出，本地复跑）
  // = 当前实例 + 当前算法参数 + 迭代历史 + 域内核完整源码（py/domains.py）+ 复跑说明
  let bundleDomLoading = false;
  $("btnBundleDom").onclick = () => {
    if (!problem) return setStatus("实例尚未生成，无法导出", "err");
    const snap = exportSnapshot();
    const doExport = (src) => {
      const algoVal = snap.algo;
      const readme = [
        "# 问题域实验包（群智能算法百科）",
        "",
        "## 内容",
        "- domain: 问题域标识（如 kpvar/knapsack/continuous/entryseq…）",
        "- problem: 当前实例（由页面「导入实例」可原样灌回）",
        "- algo / iter / seed: 本次运行的算法键与参数",
        "- history: 逐代 [代数, 全局最优, 当代值]",
        "- domain_source: 问题域内核完整 Python 源码（py/domains.py，含全部域与算法，纯标准库）",
        "",
        "## 复跑方法（Python 3.8+，无需安装任何包）",
        "1. 把 domain_source 字段内容存为 domains.py",
        "2. 把本包另存为 bundle.json，在同目录 python 交互运行：",
        "   import json, domains",
        "   bundle = json.load(open('bundle.json', encoding='utf-8'))",
        "   params = dict(bundle.get('params', {}), max_iter=bundle['iter'], seed=bundle['seed'])",
        "   domains.domain_start(bundle['domain'], json.dumps(bundle['problem']), bundle['algo'], json.dumps(params))",
        "   print(domains.domain_step())   # 每调用一次推进一代",
        "",
        "## 说明",
        "domain_start/domain_step 与页面求解器走同一内核；换算法换 domain_start 第三参数即可。",
      ].join("\n");
      const payload = {
        format: "domain-experiment-bundle/v1",
        exportedAt: new Date().toISOString(),
        domain: DOMAIN,
        algo: algoVal,
        iter: snap.params.max_iter,
        seed: snap.params.seed,
        params: Object.fromEntries(Object.entries(snap.params).filter(([k]) => k !== "seed" && k !== "max_iter")),
        problem: snap.problem,
        history: snap.history.map((h) => [h.iter, h.best, h.cur ?? null]),
        readme,
        domain_source: src,
      };
      const blob = new Blob([JSON.stringify(payload, null, 1)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${DOMAIN}-bundle-${algoVal || "demo"}-${Date.now()}.json`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      setStatus("实验包已导出（实例 + 域内核源码 + 复跑说明）", "ok");
    };
    if (bundleDomLoading) return setStatus("域内核源码加载中，请稍候…", "busy");
    bundleDomLoading = true;
    setStatus("正在打包域内核源码…", "busy");
    import(PREFIX + "js/domains_src.js")
      .then((m) => { bundleDomLoading = false; doExport(m.DOMAINS_SRC || ""); })
      .catch(() => { bundleDomLoading = false; setStatus("域内核源码加载失败，仅导出数据部分", "err"); doExport(""); });
  };
  // 导入实例：先交给 worker 里的校验器（py/validate.py）——错误指到具体字段、警告不挡路；
  // 校验器不认识的域（排程域）走下面的宽松旧路径
  let importName = "";
  let importText = "";
  const reportEl = $("importReport");
  const pageVariant = (Object.values(window.PAGE_PRESETS || {})[0] || {}).variant || null;
  const lnkSample = $("lnkSample");
  if (lnkSample) lnkSample.href = PREFIX + `samples/${DOMAIN}/${pageVariant || (DOMAIN === "multiobj" ? "moco" : DOMAIN)}.json`;
  const lnkFormats = $("lnkFormats");
  if (lnkFormats) lnkFormats.href = PREFIX + "docs/data-formats.md";
  function showReport(res) {
    if (!reportEl) return;
    reportEl.textContent = "";
    const items = [...(res.errors || []).map((x) => ["err", x]), ...(res.warnings || []).map((x) => ["warn", x])];
    if (!items.length) {
      reportEl.hidden = true;
      return;
    }
    for (const [kind, x] of items.slice(0, 30)) {
      const row = document.createElement("div");
      row.className = "ir-" + kind;
      row.textContent = (kind === "err" ? "✗ " : "! ") + (x.path ? x.path + "：" : "") + x.msg;
      reportEl.appendChild(row);
    }
    if (items.length > 30) {
      const more = document.createElement("div");
      more.textContent = `…另有 ${items.length - 30} 条未显示`;
      reportEl.appendChild(more);
    }
    reportEl.hidden = false;
  }
  function applyImported(prob, note) {
    runActive = false;
    stopTimer();
    history = [];
    lastState = null;
    runRecord = null;
    runParams = null;
    info = null;
    problem = prob;
    customFill();
    customEnsureAlgos(prob.variant);
    drawPreset();
    drawConv();
    setStatus(`已导入「${importName}」${note}——点「开始」求解`, "ok");
  }
  // 自带问题的「检查并载入」：把编辑器里的内容拼成实例，交给校验器（含试跑），通过就载入
  if (DOMAIN === "custom" && $("ceApply")) {
    $("ceApply").onclick = () => {
      if (!ready || !problem) return setStatus("引擎还在加载，请稍候", "busy");
      let data;
      try {
        data = JSON.parse($("ceData").value.trim() || "{}");
      } catch (e) {
        showReport({ errors: [{ path: "数据表", msg: "不是合法 JSON：" + e.message }] });
        return setStatus("检查失败：数据表不是合法 JSON", "err");
      }
      const p = { variant: problem.variant, n: Number($("ceN").value), sense: $("ceSense").value, data, objective: $("ceObj").value };
      if (p.variant === "real") { p.lo = Number($("ceLo").value); p.hi = Number($("ceHi").value); }
      importName = "自定义问题";
      importText = JSON.stringify(p);
      stopTimer();
      setStatus("正在检查目标函数（会在随机解上试算）…", "busy");
      post("validate", { text: importText, domain: "custom", variant: p.variant, filename: "custom.json" });
    };
  }
  function legacyImport(text) {
    let obj;
    try {
      obj = JSON.parse(text);
    } catch {
      return setStatus("导入失败：不是合法 JSON", "err");
    }
    const cand = obj && obj.format === "domain-experiment/v1" ? obj.problem : obj;
    if (!cand || typeof cand !== "object" || Array.isArray(cand) || Object.keys(cand).length === 0) {
      return setStatus("导入失败：缺少实例数据（需要 JSON 对象）", "err");
    }
    showReport({});
    applyImported(cand, "");
  }
  onValidatedHook = (res) => {
    if (res.unsupported) return legacyImport(importText);
    showReport(res);
    if (!res.ok) {
      const e0 = res.errors[0];
      const more = res.errors.length > 1 ? `（另有 ${res.errors.length - 1} 处，见下方）` : "";
      return setStatus(`导入失败：${e0.path ? e0.path + "：" : ""}${e0.msg}${more}`, "err");
    }
    const nw = res.warnings.length;
    applyImported(res.problem, nw ? `（${nw} 条提示见下方）` : "");
  };
  $("domFileInput").onchange = (e) => {
    const f = e.target.files && e.target.files[0];
    e.target.value = "";
    if (!f) return;
    if (f.size > 20 * 1024 * 1024) return setStatus("导入失败：文件超过 20MB", "err");
    if (!ready) return setStatus("引擎还在加载，请稍候再导入", "busy");
    const r = new FileReader();
    r.onload = () => {
      importName = f.name;
      importText = String(r.result);
      stopTimer(); // 校验会用引擎试跑 2 代，占用其全局运行态
      setStatus("正在校验数据…", "busy");
      post("validate", { text: importText, domain: DOMAIN, variant: DOMAIN === "custom" ? null : ((problem && problem.variant) || pageVariant), filename: f.name });
    };
    r.readAsText(f);
  };
  $("presetSel").onchange = () => {
    const cr = document.getElementById("customRow");
    if (cr) cr.hidden = $("presetSel").value !== "__custom";
    loadPreset();
  };
  const cr = document.getElementById("customRow");
  if (cr) {
    // 直绑每个输入框（不依赖 change 冒泡），改规模即时重建实例
    for (const inp of cr.querySelectorAll("input")) {
      inp.addEventListener("change", () => { loadPreset(); });
    }
  }
  $("seedInp").onchange = () => { loadPreset(); };
  setStatus("初始化中…", "busy");
  // 修2：算法下拉构建期已静态注入——首屏立即渲染 tune 参数区，不等 Pyodide
  if ($("algoSel").options.length) {
    $("algoSel").onchange = renderTune; // buildAlgoSelect 重建时也会重挂，此处保静态路径
    renderTune();
  }
  boot();
  import(PREFIX + "js/run_guard.js").then((m) => {
    guardMod = m;
    guard = m.createGuard({ anchor: document.querySelector(".statusline"), onRestart: restartEngine });
  }).catch(() => {});
  window.addEventListener("themechange", () => { heatImg = null; drawPreset(); drawConv(); });
  window.addEventListener("resize", () => { drawPreset(); drawConv(); });
});

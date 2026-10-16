// 对比页：同一实例跑遍所有算法，曲线叠加 + 结果表格
// 与工具页共用同一个 worker（同一份 Python 代码），只是不走动画、一次算完。
// v0.4：DPR 感知画布、主题感知绘图、坐标轴刻度、图例胶囊。

const BASE = new URL("../", import.meta.url).href;
// 浏览器不满足运行条件（太旧 / 是 file:// 打开的）：原因已由 js/compat.js 写在页面最上方，这里不再启动 worker
if (window.SWARM_COMPAT && !window.SWARM_COMPAT.ok) throw new Error("环境不满足：" + window.SWARM_COMPAT.reason);
const worker = new Worker(`${BASE}js/worker.js`, { type: "module" });

const state = { ready: false, cities: [], results: null, nn: null, colors: {} };
const $ = (id) => document.getElementById(id);

const PALETTE = ["#6366f1", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#0ea5e9", "#a855f7", "#14b8a6", "#eab308", "#f43f5e", "#22c55e"];
const SKIP = new Set(["nn", "2opt"]); // 基线单独画横线，不参与排名

// 主题感知取色（与 tool.js 同一套 CSS 变量）
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

const LW = 760, LH = 430;
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

worker.addEventListener("message", (e) => {
  const msg = e.data || {};
  if (msg.type === "status") setStatus(msg.text, "busy");
  else if (msg.type === "ready") {
    state.ready = true;
    setStatus(`引擎就绪 · Pyodide ${msg.version}`, "ready");
    $("btnRun").disabled = false;
  } else if (msg.type === "all_done") {
    state.results = msg.payload.results;
    state.nn = msg.payload.nn;
    render();
    const nRun = Object.keys(state.results).filter((k) => !SKIP.has(k)).length;
    setStatus(`全部 ${nRun} 个算法跑完`, "ready");
    $("btnRun").disabled = false;
  } else if (msg.type === "error") {
    setStatus(`出错：${msg.text}`, "err");
    $("btnRun").disabled = false;
  }
});

function setStatus(text, kind = "busy") {
  const pill = $("statusPill");
  pill.className = `pill ${kind === "ready" ? "ready" : kind === "err" ? "err" : ""}`;
  $("statusText").textContent = text;
}

// 主题切换后用缓存的结果重绘（不用重算）
window.addEventListener("themechange", () => {
  invalidateThemeCache();
  drawCities();
  if (state.results) render();
});

// 混沌走查 P0（2026-09-27 狂飙）：n 在入口 clamp 到 [5,500]——n<5 时构造/2-opt 退化，超大值跑挂主线程
function generateCities(n) {
  n = Math.min(500, Math.max(5, Math.round(Number(n)) || 30));
  state.cities = Array.from({ length: n }, () => [Math.random() * 700 + 20, Math.random() * 380 + 20]);
  state.results = null;
  drawCities();
  $("out").innerHTML = "";
}

function drawCities() {
  const canvas = $("mapCanvas");
  const { ctx, W, H } = ctxOf(canvas, LW, LH);
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = cvColor("--cv-bg");
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = cvColor("--cv-city");
  for (const [x, y] of state.cities) {
    ctx.beginPath();
    ctx.arc(x, y, 2.6, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawTour(tour, color) {
  const canvas = $("mapCanvas");
  const ctx = canvas.getContext("2d");
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  const dpr = canvas.width / LW;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.4;
  ctx.globalAlpha = 0.85;
  ctx.beginPath();
  tour.forEach((idx, i) => {
    const [x, y] = state.cities[idx];
    i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  const [x0, y0] = state.cities[tour[0]];
  ctx.lineTo(x0, y0);
  ctx.stroke();
  ctx.globalAlpha = 1;
}

function niceStep(max) {
  const raw = max / 8;
  const pow = Math.pow(10, Math.floor(Math.log10(Math.max(raw, 1))));
  for (const m of [1, 2, 5, 10]) if (raw <= m * pow) return m * pow;
  return 10 * pow;
}

function render() {
  const R = state.results;
  if (!R) return;
  const keys = Object.keys(R).filter((k) => !SKIP.has(k));
  keys.sort((a, b) => R[a].final - R[b].final);
  keys.forEach((k, i) => (state.colors[k] = PALETTE[i % PALETTE.length]));

  // 图例胶囊
  const legend = $("legend");
  if (legend) {
    legend.innerHTML = keys
      .map((k) => `<span><i style="background:${state.colors[k]}"></i>${R[k].name}</span>`)
      .join("") + `<span><i style="background:var(--cv-ok)"></i>NN基线</span>`;
  }

  // 曲线
  const canvas = $("convCanvas");
  const { ctx, W, H } = ctxOf(canvas, LW, LH);
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = cvColor("--cv-bg");
  ctx.fillRect(0, 0, W, H);

  const all = keys.flatMap((k) => R[k].curve);
  let vmax = Math.max(...all), vmin = Math.min(...all.concat([state.nn]));
  if (vmax - vmin < 1e-9) { vmax += 1; vmin -= 1; }
  const maxLen = Math.max(...keys.map((k) => R[k].curve.length));
  const padL = 56, padR = 16, padT = 14, padB = 30;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const X = (i) => padL + (i / Math.max(maxLen - 1, 1)) * plotW;
  const Y = (v) => padT + (1 - (v - vmin) / (vmax - vmin)) * plotH;

  // 网格与刻度
  ctx.font = "10.5px ui-monospace, monospace";
  ctx.textBaseline = "middle";
  for (let g = 0; g <= 4; g++) {
    const v = vmin + ((vmax - vmin) * g) / 4;
    const y = Y(v);
    ctx.strokeStyle = cvColor("--cv-grid");
    ctx.beginPath(); ctx.moveTo(padL, y); ctx.lineTo(W - padR, y); ctx.stroke();
    ctx.fillStyle = cvColor("--cv-sub");
    ctx.textAlign = "right";
    ctx.fillText(v.toFixed(0), padL - 7, y);
  }
  ctx.textAlign = "center";
  ctx.textBaseline = "top";
  const stepX = niceStep(maxLen - 1);
  for (let i = 0; i <= maxLen - 1; i += stepX) {
    const x = X(i);
    ctx.strokeStyle = cvColor("--cv-grid");
    ctx.beginPath(); ctx.moveTo(x, padT); ctx.lineTo(x, H - padB); ctx.stroke();
    ctx.fillStyle = cvColor("--cv-sub");
    ctx.fillText(String(i), x, H - padB + 6);
  }

  // NN 基线
  ctx.strokeStyle = cvColor("--cv-ok");
  ctx.setLineDash([5, 4]);
  ctx.lineWidth = 1.4;
  ctx.beginPath();
  ctx.moveTo(padL, Y(state.nn));
  ctx.lineTo(W - padR, Y(state.nn));
  ctx.stroke();
  ctx.setLineDash([]);

  keys.forEach((k) => {
    ctx.strokeStyle = state.colors[k];
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.beginPath();
    R[k].curve.forEach((v, i) => (i ? ctx.lineTo(X(i), Y(v)) : ctx.moveTo(X(i), Y(v))));
    ctx.stroke();
  });

  // 结果表
  const bestVal = Math.min(...keys.map((k) => R[k].final));
  const rows = keys
    .map((k, i) => {
      const gap = ((R[k].final / bestVal - 1) * 100).toFixed(1);
      const improve = ((1 - R[k].final / state.nn) * 100).toFixed(1);
      const hl = gap === "0.0" ? ' class="hl"' : "";
      return `<tr${hl}>
        <td class="num">${i + 1}</td>
        <td><span class="swatch" style="background:${state.colors[k]}"></span>${R[k].name}</td>
        <td class="num">${R[k].final.toFixed(1)}</td>
        <td class="num">${gap === "0.0" ? "🏆 最优" : "+" + gap + "%"}</td>
        <td class="num">${improve}%</td>
        <td><a href="${BASE}algo/${k}-tsp/">查看该算法 →</a></td>
      </tr>`;
    })
    .join("");
  $("out").innerHTML = `
    <div class="tablewrap">
    <table>
      <tr><th>#</th><th>算法</th><th class="num">最优路径长度</th><th class="num">与最佳差距</th><th class="num">相对基线优化</th><th></th></tr>
      ${rows}
    </table>
    </div>
    <div style="margin:10px 0"><button id="btnCsv" class="ghost">↧ 导出 CSV</button></div>
    <div class="box">差距在 3% 以内通常没有实际意义——这些算法都是随机算法，换一个随机种子排名可能就变了。
    想看稳定结论请多次运行取平均（<code>python bench.py</code> 可以批量跑）。</div>`;
  $("btnCsv").onclick = exportCsv;
}

// 结果导出（2026-09-27 目标用户走查 P2）：对比表数据可下载进表格软件
function exportCsv() {
  const R = state.results;
  if (!R) return;
  const keys = Object.keys(R).filter((k) => !SKIP.has(k));
  keys.sort((a, b) => R[a].final - R[b].final);
  const lines = ["rank,algo,final,vs_best_pct,vs_nn_pct"];
  const best = keys.length ? R[keys[0]].final : 0;
  for (let i = 0; i < keys.length; i++) {
    const k = keys[i];
    const vsBest = best ? ((R[k].final / best - 1) * 100).toFixed(2) : "";
    const vsNN = state.nn ? ((1 - R[k].final / state.nn) * 100).toFixed(1) : "";
    lines.push(`${i + 1},"${R[k].name}",${R[k].final},${vsBest},${vsNN}`);
  }
  lines.push(`0,"NN基线",${state.nn},,`);
  const blob = new Blob(["\ufeff" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `tsp-compare-n${state.cities.length || "?"}.csv`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

function mount() {
  setupCanvas($("mapCanvas"), LW, LH);
  setupCanvas($("convCanvas"), LW, LH);
  generateCities(parseInt($("nCities").value, 10));
  $("btnGen").onclick = () => generateCities(parseInt($("nCities").value, 10));
  $("btnRun").onclick = () => {
    if (!state.ready) return;
    $("btnRun").disabled = true;
    setStatus("全部算法排队跑，请稍候（约 1–3 分钟，取决于城市数与设备性能）…", "busy");
    worker.postMessage({
      cmd: "run_all",
      payload: {
        cities: state.cities,
        // 混沌走查 P0：max_iter clamp [1,2000]（NaN/负数/超大不得进 run_all）
        max_iter: Math.min(2000, Math.max(1, Math.round(Number($("maxIter").value)) || 200)),
        seed: 42,
      },
    });
  };
  worker.postMessage({ cmd: "init" });
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mount);
else mount();

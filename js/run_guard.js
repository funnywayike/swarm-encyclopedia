// 运行守卫：浏览器里的 Python 比本机慢约 2 倍，大实例上个别算法一代就要几十秒。
// 这里做两件事（TSP 页 tool.js 和各问题域页 domain_page.js 共用，都用 import(PREFIX + "js/run_guard.js") 动态加载）：
//   1. 估时：按已算完的代数外推「还需多久」，让用户在跑之前就能判断要不要等；
//   2. 看门狗：某一步超过 slowMs 还没返回，就明确告诉用户发生了什么，并给「强制停止并重载引擎」按钮
//      （worker 里的 Python 是同步执行的，没法温和地打断，只能终止 worker 再重新加载，约 5 秒）。

export function fmtDuration(sec) {
  if (!isFinite(sec) || sec < 0) return "—";
  if (sec < 1) return "不到 1 秒";
  if (sec < 90) return `${Math.round(sec)} 秒`;
  const m = sec / 60;
  if (m < 90) return `${Math.round(m)} 分钟`;
  return `${(m / 60).toFixed(1)} 小时`;
}

// done 代用了 elapsedSec 秒，共 total 代：返回「每代约 … · 预计还需 …」；样本太少时返回空串
export function etaText(done, total, elapsedSec) {
  if (!(done >= 2) || !(elapsedSec > 0.5) || !(total > done)) return "";
  const per = elapsedSec / done;
  return `每代约 ${per < 0.1 ? Math.max(per * 1000, 1).toFixed(0) + " 毫秒" : per.toFixed(per < 10 ? 2 : 1) + " 秒"} · 预计还需 ${fmtDuration(per * (total - done))}`;
}

// 预计总时长超过多少秒就提醒一次（每次运行至多一次）
export const LONG_RUN_SEC = 60;

export function projectedTotal(done, total, elapsedSec) {
  return done >= 2 && elapsedSec > 0.5 ? (elapsedSec / done) * total : 0;
}

// anchor：横幅插在它后面；onRestart：用户点「强制停止并重载引擎」时调用
export function createGuard({ anchor, onRestart, slowMs = 8000 }) {
  const el = document.createElement("div");
  el.className = "run-guard";
  el.setAttribute("role", "alert");
  el.hidden = true;
  const msg = document.createElement("span");
  const btn = document.createElement("button");
  btn.type = "button";
  btn.textContent = "强制停止并重载引擎";
  btn.onclick = () => {
    reset();
    onRestart();
  };
  el.append(msg, btn);
  anchor.insertAdjacentElement("afterend", el);

  let t0 = 0;
  let pending = 0;
  let mode = ""; // "slow"=卡住警告（带按钮）；"notice"=普通提示；""=不显示
  const tick = setInterval(() => {
    if (!pending) return;
    const waited = (performance.now() - t0) / 1000;
    if (waited * 1000 < slowMs) return;
    msg.textContent =
      `这一步已经算了 ${Math.round(waited)} 秒还没有返回。实例较大时，个别算法每一代会很慢` +
      "（浏览器里的 Python 比本机慢约 2 倍）。可以继续等；想放弃就点右侧按钮，然后换小一点的实例或更快的算法（如模拟退火、爬山）。 ";
    btn.hidden = false;
    el.hidden = false;
    mode = "slow";
  }, 1000);

  // 不带按钮的提示（例如「预计要跑很久」），12 秒后自动消失
  let noticeTimer = null;
  function notice(text, ms = 12000) {
    if (mode === "slow") return; // 正在显示「卡住了」的警告，不覆盖
    msg.textContent = text;
    btn.hidden = true;
    el.hidden = false;
    mode = "notice";
    clearTimeout(noticeTimer);
    noticeTimer = setTimeout(() => { if (mode === "notice") { el.hidden = true; mode = ""; } }, ms);
  }

  function sent() {
    if (!pending) t0 = performance.now();
    pending++;
  }
  function got() {
    pending = Math.max(0, pending - 1);
    if (pending) t0 = performance.now(); // 还有排队的：从现在重新计
    else if (mode === "slow") { el.hidden = true; mode = ""; } // 回来了：撤掉卡住警告（普通提示自己到点消失）
  }
  function reset() {
    pending = 0;
    el.hidden = true;
    mode = "";
    clearTimeout(noticeTimer);
  }
  return { sent, got, reset, notice, destroy: () => { clearInterval(tick); el.remove(); } };
}

// 兼容性检查（普通脚本，必须最先加载，且不能依赖任何新语法）。
// 在线演示靠浏览器里的 Python（Pyodide，WebAssembly）+ 模块 Worker 运行，这两样不满足时，
// 页面原来只会停在「初始化中…」或报「worker 错误：undefined」，用户完全不知道怎么回事。
// 这里在页面最上方给一句人话：是哪里不行、怎么办。结果同时放进 window.SWARM_COMPAT 供其他脚本参考。
(function () {
  var reason = "";
  if (location.protocol === "file:") {
    reason = "file";
  } else if (typeof WebAssembly !== "object" || !("noModule" in HTMLScriptElement.prototype)) {
    reason = "old";
  } else {
    // 模块 Worker 探测：支持的浏览器会读取 options.type；不支持的（旧 Safari / Firefox）不会
    var probed = false;
    try {
      var url = URL.createObjectURL(new Blob([""], { type: "text/javascript" }));
      var w = new Worker(url, { get type() { probed = true; return "module"; } });
      w.terminate();
      URL.revokeObjectURL(url);
    } catch (e) {
      probed = false;
    }
    if (!probed) reason = "old";
  }
  window.SWARM_COMPAT = { ok: !reason, reason: reason };
  if (!reason) return;

  var TEXT = {
    file:
      "这个页面是直接双击打开的本地文件（file://）。在线演示需要通过 http 访问：在项目目录运行 python serve.py " +
      "（Windows 也可以双击 start_server.bat），再打开它提示的 http://127.0.0.1:端口 ；或者直接使用已部署的线上站点。" +
      "百科、算法介绍等文字内容不受影响，可以正常阅读。",
    old:
      "你的浏览器版本太旧，无法运行浏览器内的 Python（Pyodide）。在线演示需要 Chrome / Edge 111+、Firefox 114+ 或 Safari 16.4+，" +
      "更新浏览器后再试。百科、算法介绍等文字内容不受影响，可以正常阅读。",
  };

  function show() {
    var box = document.createElement("div");
    box.className = "compat-warn";
    box.setAttribute("role", "alert");
    box.textContent = TEXT[reason];
    var host = document.getElementById("tool-root") || document.querySelector("main") || document.body;
    host.insertBefore(box, host.firstChild);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", show);
  else show();
})();

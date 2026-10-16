# Browser checklist (manual) / 浏览器手工检查清单

The automated tests run the engine in CPython and, in CI, in the real Pyodide under Node. They cannot see layout, canvas
drawing or browser-specific behaviour. Before a release (and when you change `js/`, `css/` or a page template), click through
the following in each browser you care about. Last checked in Chromium (Edge/Chrome); **Firefox and Safari have not been
checked yet** — if you use them, please tell us what you find.

自动测试只在 CPython 和 Node 里的 Pyodide 里跑引擎，看不到版式、画布和浏览器差异。发布前（以及改了 `js/`、`css/`、页面模板之后）
请在要支持的浏览器里手工点一遍。目前只在 Chromium 系浏览器（Edge / Chrome）里点过；**Firefox 和 Safari 还没有检查过**。

Requirements to run the demos: Chrome / Edge 111+, Firefox 114+, Safari 16.4+ (module workers). The page must be served over
http(s); `file://` does not work.

## Checklist

1. **Start up.** Open `/` and `/demo/`. The status line reaches “Engine ready · Pyodide …” within a few seconds (first load
   downloads about 13 MB). No red errors in the console.
2. **A TSP run.** Press Start: the tour animates, the convergence curve is drawn, the best value never goes up. Pause, Step,
   Reset behave. Change the algorithm and parameters; “Restore defaults” works.
3. **Import / export.** Import `samples/…` data and a TSPLIB file; export Result JSON, PNG, CSV and the experiment bundle.
4. **A problem page from each drawing family** (they use different canvas code): `/problem/knapsack/`, `/problem/continuous/`,
   `/problem/multiobj/`, `/problem/graphcolor/`, `/problem/fss/` (Gantt), `/problem/carp/` (network), `/problem/cflp/` (map),
   `/problem/msa/` (alignment), `/problem/setpack/` (matrix). Start a run on each; the picture changes and the console stays clean.
5. **Custom problem.** `/problem/custom/`: load an example, “Check and load”, run it.
6. **Language switch.** Press 中 / EN on a few pages: titles, buttons, status lines and the canvas labels change; the page keeps
   working after the switch; the English summary block is visible only in English.
7. **Themes and layout.** Light/dark toggle; resize to a phone width (375 px): no horizontal scrolling, the menus open by tap.
8. **Offline.** Stop the network after loading and reload from the local server: the demos still start (Pyodide is vendored).

## Notes for Safari / Firefox

- Safari: `Worker` with `type: "module"` needs 16.4+; `localStorage` may throw in private windows (the code wraps it).
- Firefox: check the canvas text rendering (the charts draw labels with `fillText`) and the dropdown menus.

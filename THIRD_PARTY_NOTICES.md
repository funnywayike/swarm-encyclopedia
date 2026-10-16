# Third-party notices / 第三方声明

The project's own code and content are under the MIT License (see `LICENSE`). The only third-party code that is
redistributed in this repository is the Pyodide runtime. / 本仓库自带的第三方代码只有 Pyodide 运行时；其余部分是本项目自己的代码与内容。

## Pyodide (`vendor/pyodide/`)

- What: the Pyodide distribution (CPython compiled to WebAssembly) — `pyodide.mjs`, `pyodide.asm.mjs`, `pyodide.asm.wasm`,
  `python_stdlib.zip`, `pyodide-lock.json`. Version 314.0.6 (Python 3.14.2, Emscripten 5.0.3). The files are unmodified
  copies of the official release.
- Project: <https://pyodide.org> · source: <https://github.com/pyodide/pyodide>
- License: Mozilla Public License 2.0 (<https://www.mozilla.org/MPL/2.0/>). The MPL applies to Pyodide's own files; it does
  not extend to the rest of this repository, which only loads Pyodide at run time.
- Pyodide bundles CPython (Python Software Foundation License, <https://docs.python.org/3/license.html>), the
  Emscripten runtime (MIT / University of Illinois-NCSA) and the other components listed in the Pyodide documentation. Their
  licences travel with them; see the upstream repository for the full list.
- The pages load the local copy first and fall back to the jsDelivr / unpkg CDNs only if the local copy cannot be loaded
  (`js/worker.js`, `js/domain_worker.js`). Nothing else is fetched from third-party hosts.

## Benchmarks, instances and algorithms / 基准、实例与算法

No external dataset is copied into the repository. Benchmark instances are produced by the generators described in the
literature and cited on each page — for example Taillard's flow-shop generator (`ta001`), the Fisher–Thompson `ft06`
job-shop instance, DSJC random graphs, the ZDT / DTLZ test-function definitions — and the algorithms are the authors' own
re-implementations from the published descriptions. Every page lists the papers it relies on; the references are checked
against Crossref / arXiv by `tools/check_citations.py`. 没有拷贝任何外部数据集；实例由文献中的生成器/定义生成，算法为按公开论文自行实现。

## Development-only tools / 仅开发时使用

`pytest` and Node.js are used to run the tests; neither is distributed with the repository.

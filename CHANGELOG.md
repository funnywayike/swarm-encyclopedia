# Changelog

All notable changes to the algorithms, problems and results this site produces. Behaviour changes that alter
published numbers are listed explicitly, because the golden snapshot (`tests/golden/results.json`) is only ever
updated on purpose and every update must be explained here.

## Unreleased (heading to v0.1.0)

### Fixed — exported results and navigation (search results unchanged)

- Domain JSON, CSV and experiment bundles use the original run's instance, algorithm and tuned parameters; changing presets clears the previous run. Exports capture their data before loading modules asynchronously.
- Continuous optimizers now report the full best solution alongside the two-dimensional drawing coordinates.
- Corrected stale problem links in the content source (set cover, coloring, packing and knapsack variants).


### Fixed — results that were wrong (these change numbers)

A new invariant test (`tests/test_consistency.py`) checks, for every problem × variant × algorithm, that the
reported best value equals the objective recomputed from the reported best solution, and that the best never gets
worse over generations. It found defects that had been in the site all along (the old golden snapshot and the
"beats random" gates only compared reported numbers, never the solutions behind them):

- **Set cover, SAT, QUBO — `de`, `abc`, `woa`, `gwo`, `cs`**: the initial population was scored on one sign
  convention and every later evaluation on the opposite one, so these algorithms were actually *maximising* cost
  while reporting its negative (set cover showed costs like −417 and looked like the winners). Fixed.
- **EO / MFO / Jaya / TLBO** (permutation `pk_*`, assignment `as_*`, bit-vector `bv_eo`): a particle's position was
  overwritten before deciding whether to keep the move, so positions and values drifted apart and the reported
  optimum was not reachable from the reported solution. They now update a copy and write back only on acceptance.
- **Continuous `fa`, `gsa`, `eo`, `sma`, SAT `sat_mfo`**: reported the best of the *current* generation instead of
  the best so far, so the "never goes up" convergence curve could rise. Fixed.
- **Continuous `cmaes`**: evaluated points outside the search box. On Schwefel (where the function is lower outside
  the box) it "found" a value of −1e13. It now evaluates the projection onto the box.
- **Every `entryseq` problem page** (all 65 variants): the drawing code was unreachable, so the canvas stayed blank and
  the console logged an error every generation. Fixed, and guarded by a routing check in `selfcheck.py`.
- **Every page's inline JavaScript had a syntax error** (introduced by the wording clean-up pass, not by the original site): a
  rewrite rule deleted empty `()` pairs inside string literals, which also rewrote the JavaScript embedded in the page templates
  (`(function(){…})();` became `(function{…});`, `e.preventDefault()` became `e.preventDefault`). The theme initialiser and the
  dark-mode button, the touch-device dropdown menus, the long-table filters, the discovery filter and the "one-click run" on all 52
  algorithm pages silently did nothing, and every page logged two `Uncaught SyntaxError`s. Restored from the pre-clean-up text
  (41 places), the rule no longer touches `()`, and `tests/test_inline_scripts.py` now parses every inline script of every built
  page and every `js/*.js` file with Node (selfcheck and the old tests only looked at HTTP status codes and text).
- **TSP solvers with 5 cities** (the page's own minimum): 11 algorithms crashed in `_or_opt_move`. Fixed; the
  validator now requires at least 4 cities.
- **TSP page**: importing TSPLIB, `id,x,y` CSV or a distance matrix silently read the wrong coordinates. Imports now go
  through the shared validator; imported data keeps its original scale and TSPLIB distance functions.
- **TSP page "单步"** before pressing start stepped the nearest-neighbour baseline instead of the chosen algorithm.
- **Set cover** at the validator's size limit took ~60 s per generation; coverage is now computed with integer
  bitmasks (identical results, ~300× faster).

Golden snapshot: 155 results changed for the fixes above (19 algorithm keys) plus the 30 `vrp` results below;
nothing else moved.

### Changed

- **Withdrawn algorithm combinations replaced by a rule, not a blacklist.** On the `entryseq` problems every variant was
  treated as a permutation, and a withdrawal list hid the combinations that crashed. Worse, the combinations that did not
  crash were meaningless: bit-vector (`bv_*`) and permutation-random-key (`pk_*`) algorithms were fed to real-vector
  problems as if 0/1 or 0..n-1 were real numbers. Now each variant has one of three encodings and gets exactly that
  encoding's algorithm family (permutation: own `ga`/`ts` + `pk_*`; bit vector: the QUBO family including `ga`/`ts`/`bv_*`;
  real vector: the continuous-function family incl. PSO/DE/CMA-ES). An algorithm from the wrong family is refused.
  Golden snapshot: 984 meaningless combinations removed, 400 proper ones added.
- **Abstract subset problems are now real subset models (bit vectors)**: vertex cover, dominating set, feedback vertex
  set, max-cut, set packing, hitting set, Steiner tree. They used to be squeezed into permutations ("first k positions
  are the chosen vertices" with a fixed k; max-cut forced into balanced bisections). Fidelity: *simplified* → *standard*.
- **`orienteering` and `rcpsp` rebuilt** (they were "illustrative" with model defects): orienteering now has a real
  selection decision (visit in priority order, skip what no longer fits the budget); RCPSP now uses the serial schedule
  generation scheme with a resource profile, so activities run in parallel. Both *standard*; verified against exhaustive /
  independent exact search on small instances.
- **ABC** (`_cn_abc`): fitness `1/(1+f)` went negative for f ≤ −1 and crashed the roulette; the scout bee could also reset the
  current best solution (best got worse). Fixed.
- **CEM / entry-sequence real-vector algorithms** now report the best of *all* evaluated points (warm-up samples used to be
  evaluated but not reported).
- **Convergence chart** is scaled by the best curve; penalty spikes of constrained problems no longer flatten it.
- **`vrp` is now a real multi-vehicle capacitated VRP (CVRP)**: solution = customer visiting order, decoded with
  Prins' optimal split into at most *m* capacity-feasible routes; objective = total distance. It used to be one big
  loop with an overload penalty. Fidelity: *simplified* → *standard*. Pages draw one coloured route per vehicle.
- Pause → start now **resumes** the run instead of restarting it (TSP page and problem pages).

### Added

- Problems: **ATSP** (also reads TSPLIB `.atsp`), **parallel-machine scheduling P||Cmax**, **number partitioning**,
  **k-means clustering**, **constrained engineering design** (welded beam, pressure vessel, tension/compression
  spring, speed reducer — each reproduces its published best-known value).
- Continuous benchmarks: Griewank, Lévy, Schwefel, Zakharov, Dixon–Price, Styblinski–Tang.
- **VRPTW — vehicle routing with (hard) time windows** (`entryseq` variant `vrptw`, page `/problem/vrptw/`): a customer visiting
  order decoded by a Prins-style optimal split over the *time- and capacity-feasible* consecutive segments (early arrival waits,
  late arrival is infeasible, the vehicle must be back before the depot closes); objective = total distance with at most *m*
  vehicles, tours that do not fit the fleet are penalised per extra vehicle. Instances are generated around a random reference
  routing, so a feasible solution always exists. The page draws the routes and a time-window timeline. Verified against a brute-force
  split (per-permutation equality), an exhaustive search over all visiting orders, and a step-by-step feasibility simulation of every
  route the page shows. `pk_sma` is withdrawn for it, as for plain VRP.
- **VRPSTW — soft time windows** (`vrpstw`, `/problem/vrpstw/`): same instances as VRPTW, but arriving late is allowed and costs
  λ (= 2) per time unit of lateness (customer windows and depot closing); objective = distance + λ × lateness. Checked against a
  brute-force split, the two limits (λ = 0 is plain CVRP, λ → ∞ is the hard-window optimum) and the monotonicity of the optimum's
  lateness in λ. The timeline marks lateness in red.
- **MDVRP — multi-depot VRP** (`mdvrp`, `/problem/mdvrp/`): 2 or 3 depots, each with its own fleet of identical vehicles; the
  solution is a permutation of the customers plus depot-separator tokens, the customers between separators belong to one depot and
  are split optimally into at most *m* capacity-feasible routes. Checked against a per-depot brute-force split and an exhaustive
  search over all customer-to-depot assignments, orders and cuts. No route-duration limit (the classic Cordeau instances have one).
- **Continuous multi-objective benchmarks ZDT1–6 and DTLZ1–7** (new domain `mocont`, pages `/problem/zdt/` and
  `/problem/dtlz/`): real-coded NSGA-II (SBX + polynomial mutation), MOEA/D-DE (Tchebycheff decomposition), a weighted-sum
  GA as the contrast case and a random-search baseline. Unlike the knapsack multi-objective page, these functions have
  analytic true fronts, so the page reports **IGD** and the **hypervolume ratio** against the true front (fixed reference
  point), draws the true front under the population, and the result file carries the decision vectors of the final front.
  Checked against the published front equations, an independent hypervolume (analytic value for ZDT1), a brute-force
  non-dominated filter (ZDT3's five segments), and by recomputing every reported objective vector from its decision vector.
  ZDT5 is bit-string coded (80 bits, deceptive, a discrete front of 31 points; its operators are uniform crossover and bit-flip
  mutation); DTLZ3 (3¹⁰−1 local fronts), DTLZ4 (density bias), DTLZ5/6 (a front that degenerates to a curve) and DTLZ7 (four disconnected
  regions, whose exact front is computed with a 2-D prefix-minimum sweep and cross-checked against a brute-force dominance filter)
  complete the suite. DTLZ is provided with 3 objectives.
- **Bring your own problem** (`/problem/custom/`): choose a solution shape (bits / permutation / real vector) and write
  an objective as a restricted expression; all algorithms for that shape run on it. Local Python objectives are
  available on the command line only (`--objective-py`).
- **Results as files**: `swarm-result/v1` exported from the web pages or `swarm.py solve --out`; `swarm.py replay`
  re-runs and verifies the convergence curve (browser-produced results replay exactly on CPython).
- Run guard: time estimate, long-run notice, and "force stop and reload the engine" when a single step takes > 8 s.
- Friendly messages for old browsers and for `file://` (module workers need http).
- Fidelity badges (standard / simplified / illustrative / custom) on every problem page and in upload warnings.
- Citation checker (`tools/check_citations.py`) and 30+ corrected references.

### Added — equal-evaluation-budget gate, new kernels, deeper pages, English interface

- **Equal-evaluation-budget benchmark (`tools/fair_budget.py`).** Every "domain × variant × algorithm" cell is compared with
  random search that gets *as many objective evaluations as the algorithm itself used* (200 generations, 3 instance seeds,
  median; a relative gap within ±0.2% is a tie). 3 577 cells: 1 968 clearly better than random search, 1 250 ties, 359
  worse. Cells that lost were re-tested with 9 seeds; the 359 that still lose are **withdrawn** (listed in
  `data/withdrawn_cells.json`, enforced by the generated `py/domains_parts/88_withdrawn_cells.py`, shown on the coverage
  page). Most of them are permutation/bit-vector ports of the 2020s metaphor algorithms (`pk_sma`, `pk_eo`, `pk_boa`,
  `bv_tlbo`, `bv_bfo`, …); a few classical combinations on tiny instances also lost (for example `hc` and `ts` on bin
  packing, `hc` on the continuous page). Withdrawn is not "bad": it means no win over random search at this model and budget.
- **18 more kernels** (HHO, SSA, ALO, BOA, Salp, FPA, DA, MPA, crow search, KH, BFO, AFSA, FWA, ICA, SFLA, SOS, BBO, AIS) are
  available on bit-vector, permutation and assignment problems through the same bridges as the earlier kernels, plus generic
  ILS / VNS / ACO / GRASP for discrete encodings. IBEA and R-NSGA-II were added to the multi-objective domain.
- **Mapping layer** (`data/mapping.json`): the "which algorithms work here" rows of 48 more problem pages are generated from the
  benchmark (`tools/gen_mapping_rows.py`, wins only, at most 12 per page). 35 existing "measured" rows that the benchmark
  contradicts (a tie or a loss against random search) and the rows of the retired `fractional` setup were removed; pages for which
  no algorithm wins (tiny instances where random search finds the optimum) show no roster.
- **Every problem and algorithm page was rewritten in depth** (model, complexity, benchmarks, what the site really implements;
  origin, theory and criticism, variants and further reading for the 45 algorithms). Many models were found to be wrong or too
  loose while doing so and were rebuilt — see the next section.
- **English interface.** A 中 / EN switch on every page (`js/i18n.js`, dictionaries in `data/i18n/`, English names and summaries in
  the data files). Menus, buttons, status messages, parameter descriptions, chart captions, the demo area of every problem page and
  the key pages are translated; every algorithm, problem, family and meta page starts with an English summary; the long
  explanatory bodies stay Chinese and say so. `tests/test_i18n.py` keeps it from rotting.
- **Fix:** the coverage and discovery pages had no stylesheet, theme switch or site header (an unreplaced template placeholder);
  they now use the standard page shell.
- Site URL is configurable (`SWARM_SITE_URL`); without it no canonical / Open Graph URLs and no sitemap are written.

### Changed — models rebuilt while deepening the problem pages (these change numbers)

- **Scheduling and routing models rebuilt on the standard benchmarks**: flow shop = Taillard `ta001` (optimum 1278), job shop =
  `ft06` (optimum 55) with Bierwirth's operation encoding, open shop, flexible job shop, CARP / rural postman on a road network
  (Prins-style split), capacitated and location-routing models, course timetabling, network design (Steiner forest), 3-D
  matching (planted perfect matching), Hamiltonian cycle / longest path (planted solutions), protein folding (HP lattice),
  multiple sequence alignment (exact 3-D DP optimum), robust optimisation, the polynomial-time contrasts (MST, shortest path,
  max-flow, min-cost flow, matching, topological sort — each with its exact optimum built into the instance), fractional
  knapsack on a real-vector encoding (greedy optimum as reference), multidimensional knapsack with independent weights and
  discounted knapsack as the standard DCKP.
- **Removed or moved**: `prefmo` / `decompo` / `indicmo` now run on the continuous multi-objective benchmarks (`mocont`) with
  IBEA, R-NSGA-II and MOEA/D; `etp` / `nrp` / `sls` / `ttp` run only in their dedicated scheduling domains; the old `kpvar`
  `fractional` variant was replaced by the real-vector one.
- **Golden snapshot**: 1 832 entries added, 458 removed (182 withdrawn by the benchmark, the rest from the variants and
  encodings listed above), 357 values changed — all of them in the rebuilt models listed above (25 variants); nothing else moved.

### Developer tooling (no change to any result)

- **`py/domains.py` is split into 22 numbered parts** under `py/domains_parts/` (knapsack, continuous, multi-objective, kernel
  libraries, one part per domain, registries, the `domain_*` API). `domains.py` is now a small loader that executes the parts in file-name
  order inside one module namespace — exactly how the browser bundle is built — so local tests and the browser see the same
  namespace. The golden snapshot and the browser bundle `js/domains_src.js` are byte-identical before and after the split.
- **Scaffolds**: `python tools/new_problem.py NAME --encoding perm|bits|real --title …` and
  `python tools/new_algorithm.py KEY --title … --family F2` generate a runnable placeholder implementation, the data/page entries and a
  test skeleton. Everything they generate carries `TODO（占位）`, and `tests/test_no_placeholders.py` keeps the suite red until it is
  replaced. A problem's solution encoding is now declared in its own `@_objective(..., encoding=…)` instead of two hand-kept tuples.
- **Tests split in two tiers** (`tests/conftest.py`): `-m "not slow"` runs 566 tests in about 90 s; the full suite takes about 10 min.
  The test that pinned the exact list of problem pages now only guards against pages disappearing, so adding a page no longer
  needs a test edit.
- **CI** (`.github/workflows/ci.yml`): fast tier on Python 3.12 / 3.13 / 3.14 with a "generated files are up to date" check; slow tier
  (main, nightly, manual) runs everything plus `tools/pyodide_parity.mjs`, which replays the whole golden snapshot (2175 combinations)
  inside real Pyodide — all identical on Python 3.14.2 — and `tools/pyodide_smoke.mjs` (TSP step protocol, now run against the same
  bundle the browser gets). The golden snapshot is also identical on CPython 3.12 and 3.13.
- `CONTRIBUTING.md` documents the layout, the commands and the rules (fidelity labels, reproducible best values, the shared browser
  namespace).
- Fixed: `ENCODINGS` in `entryseq.py` shadowed the same name in `userproblem.py` in the browser namespace (renamed `ES_ENCODINGS`).

### Known limitations

- The VRP family fixes the fleet size and minimises distance only (Solomon's benchmark orders by vehicles first, so numbers are
  not comparable with published Solomon results); MDVRP has no route-duration limit; periodic and open variants are not provided.
- DTLZ is provided with 3 objectives only (the suite scales to any number; many-objective problems are covered conceptually on
  the `/problem/maop/` page).
- 19 of the 68 `entryseq` problems are still *illustrative* models (e.g. MST, shortest path, max-flow — polynomial problems
  shown as "P-class contrast"), and 20 are *simplified*; each page says so and shows what differs from the textbook definition.
- 134 citations (books, conference papers, Russian/Chinese sources) cannot be verified automatically; see
  `docs/citation-report.md`.

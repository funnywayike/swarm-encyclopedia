# Design: "Bring your own problem" (BYOP)

Status: **proposal for review — nothing built yet.** Needs your decisions on §7 before any code.

## 1. What this is, and why

Today a visitor can upload **data** for the 14 built-in problem types (a knapsack instance, a TSPLIB file, a graph…).
They cannot bring a **problem the site doesn't have** — e.g. "pick the best subset of my 40 marketing channels under
this ROI formula", or "minimise this function I wrote". Your stated vision was: *kernels should work for any problem,
not just a dedicated one for UFLP.* BYOP is that vision made user-facing:

> choose an **encoding** (what a solution looks like) + provide an **objective** (how good a solution is)
> → every algorithm that works on that encoding runs on it, unchanged.

This is feasible because the algorithms are already separated from the problems: kernels per encoding
(`_bv` bit vector, `_pm` permutation, `_cn` continuous, `_as` assignment, `_pk` packing, `_mo` multi-objective)
talk to a problem only through a tiny "context" object. For bit vectors that is:
`n`, `obj(s)`, and optional `repair(s)`, `random(rng)`, `polish(...)` — and the optional ones have generic defaults
(`value = -obj`, `repair = identity`, `random = uniform`). A user problem is therefore a ~20-line adapter
(`GenericBitCtx(n, obj)`), not a new engine.

## 2. Three levels (cheapest first)

| Level | Who writes what | Where it runs | Safety | Cost to build |
|---|---|---|---|---|
| **L1 Formula** | User types an objective as a *restricted expression* over the solution vector `x` and uploaded data tables | Browser worker | **Safe by construction** (we parse it; it can only do arithmetic) | Medium |
| **L2 Python function** | User pastes `def objective(x, data): ...` | Browser worker (Pyodide) | **Not safe against code from someone else** (see §4) | Small, but needs guard rails |
| **L3 Local Python** | `python swarm.py solve data.json --encoding bits --objective my_obj.py` | The user's own machine | Safe — it is their machine and their file | Small |

L1 and L3 cover almost everyone; L2 is the "power user in the browser" option and the only one with a real risk.

## 3. How it would look

**Encoding picker** (one dropdown, plain words):
- *Yes/no choices* (bit vector, length n) — pick a subset, open/close facilities, feature selection
- *An ordering* (permutation of n items) — routes, schedules, job order
- *Numbers in ranges* (real vector, bounds per dimension) — tuning parameters, function minimisation
- *One label per item* (integer vector, k labels) — assignment, colouring, clustering
- (later) *two or more objectives at once*

**Objective (L1)** — Python-expression subset, evaluated with `x` (the solution), `n`, and named data tables from an uploaded JSON:

```
# subset selection with a budget, penalty method
gain  = sum(value[i] * x[i] for i in range(n))
spend = sum(cost[i]  * x[i] for i in range(n))
objective = -gain + 1000 * max(0, spend - budget)      # minimise
```
Allowed: numbers, `+ - * / // % **`, comparisons, `and/or/not`, `if/else` expressions, indexing, list/generator
comprehensions over `range(...)` or data tables, and a whitelist of functions
(`sum min max abs sqrt exp log sin cos floor ceil len range sorted`).
Everything else (imports, attribute access, calls to anything not on the list, `exec`, dunder names) is rejected with a
pointed message ("`import` is not allowed — only arithmetic and these functions: …").

**Before running**, the page does a *dry run*: evaluates the objective on ~20 random solutions and reports
(a) any error with the offending line, (b) non-finite values, (c) a constant objective ("every solution scores the same — nothing to optimise"),
(d) evaluation time → feeds the same ETA / "this will take N minutes" warning used elsewhere (Phase 2 run guard).

**Compatibility is computed, not promised**: the algorithm dropdown lists exactly the kernels registered for that encoding
(the registry already knows this), with the usual "why only some algorithms?" hint.

## 4. Safety boundary (the part that needs your decision)

- **L1** — we never `eval` user text. We parse it with `ast`, walk the tree against the whitelist above, then compile
  that checked tree. No attribute access, no names outside `x`, `n`, data tables and whitelisted functions.
  An evaluation step budget (node count × calls) and the existing run-guard "force stop" cover infinite loops
  (comprehensions are bounded by `range`/table sizes; no `while`). Residual risk: memory blow-up via `x ** 10**9` — bounded by capping numeric exponent size in the checker.
- **L2** — runs arbitrary Python in the user's own browser tab, inside a Web Worker.
  The worker cannot touch the page, cookies, or other tabs, **but it can make network requests**. The realistic attack is
  social: *someone tells a user "paste this objective to try my benchmark"* and the snippet sends the user's uploaded data somewhere.
  Mitigations, in order of strength:
  1. A **Content-Security-Policy `connect-src`** limited to the origin and the Pyodide CDNs would block exfiltration.
     **Caveat — I'm not sure this is available to us:** a `<meta>` CSP protects the page, but a worker loaded from a URL takes its
     policy from *its own* HTTP response headers, and GitHub Pages doesn't let us set headers. (Workers built from `blob:` URLs do inherit the creator's policy,
     which might be a workaround.) This needs a real-browser experiment; **do not count on it** until tested.
  2. A clear one-time warning: "This runs the code you paste. Only run code you wrote or have read."
  3. Never auto-run code from URLs / shared links / imported result files (a result file may *contain* an objective; importing it shows the code and requires a click).
- **L3** — no browser sandbox question; standard "you are running your own script".

**My recommendation:** ship **L1 + L3**, leave **L2 off** in v0.1. Revisit L2 once the CSP claim has been tested in real browsers.

## 5. Results and reproducibility

Results use the same `swarm-result/v1` file with `domain: "custom"`, `variant: <encoding>`, and the problem block holding
the encoding, data tables and the objective source. `swarm.py replay` re-parses and re-runs it; for L1 this is safe, for L2 the CLI shows the code and asks first.
Every page and result for a custom problem carries the fidelity label **"user-defined — results say nothing beyond your own formula"**.
(Same honesty rule as the built-in 🔶 示意模型 badge.)

## 6. What it costs and where it lands in the code

- `py/custom.py` (new): expression checker + compiler, `GenericBitCtx / PermCtx / RealCtx / LabelCtx`, dry-run, `validate`-style error reporting with paths.
- `py/registry.py`: a `CUSTOM` entry listing encodings → kernel sets (derived from the existing kernel tables, no second list).
- `py/validate.py`: `custom` domain (reuses the same error format).
- One new site page `/problem/custom/` (same shell as other problem pages) + `docs/custom-problems.md` with 5 worked examples (subset selection, feature selection, job ordering, parameter tuning, simple clustering).
- Tests: whitelist (every forbidden construct has a test), dry-run failure modes, kernel × encoding smoke matrix (each encoding × each kernel runs on a toy objective), golden entries for the examples.
- Rough size: L1 + L3 ≈ 1 working phase (one focused chunk), L2 adds little code but needs the CSP experiment.

## 7. Decisions I need from you

1. **Scope for v0.1:** (a) ship L1 + L3 now, (b) ship L3 only (CLI) and put L1 in v0.2, or (c) postpone all of BYOP past v0.1.
   *My pick: (a) — it's the piece that makes "other people can bring their own problems" true, and it is safe.*
2. **L2 (paste Python in the browser):** off in v0.1 (my pick), or on with warning + CSP?
3. **Expression language:** Python subset (my pick — same language the algorithms are written in, and the checker is ~100 lines with `ast`) vs. a JS subset.
4. **Encodings for the first release:** bit vector + permutation + real vector (my pick; they cover the three biggest user needs), with integer-label vectors and multi-objective following.

Nothing here changes existing pages or results; it is purely additive.

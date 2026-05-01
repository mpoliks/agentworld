# Cleanup After Review — Actionable Plan

Status as of this writing: the demand-side-feedback, productive/parasitic-folding, and dynamic-law mechanisms are landed and the test suite is green (83/83). All three mechanisms are flag-gated; backward compat for the 15 canonical scenarios is within ±2.6% on EBI. The previous "free welfare" failure mode is fixed by `TopologyConfig.max_productive_real_share` clamping `real_added_productive` to ≤ 60% of `base_real_surplus`. The §3 brief work (law) shipped early but is now properly opt-in via `LawConfig.enabled = False`.

What remains is naming hygiene, regression-baseline housekeeping, and three targeted tests. This document is the to-do list. A small model executing it does **not** need to read the original review or design conversation. Read these inputs only:

- `engine/core/folding.py`, `engine/core/metrics.py`, `engine/core/transactions.py`, `engine/core/world.py`, `engine/core/topology.py`
- `engine/scenarios/__init__.py`
- `engine/build_dashboard.py` (the productive-fold panel and its JS bindings)
- `engine/sensitivity.py` (the Sobol output list)
- `engine/tests/test_demand.py`, `engine/tests/test_productive_folding.py`, `engine/tests/test_law.py`
- `docs/concepts/epistemic_status.md`, `docs/concepts/demand_and_intermediation.md`

Each task below has a concrete entry condition, file pointers, an exit condition, and where applicable, an acceptance number. Do them in order. Run `python -m pytest engine/tests/ -x` after each task and confirm all tests still pass.

---

## Task 1 — Rename `productive_welfare_yield` and `parasitic_nominal_residual`

### Why

The variable now named `productive_welfare_yield` is computed as `productive_real_added / nominal_added` (see `engine/core/folding.py:_fold_surplus_geometric`, around line 185, and `_fold_surplus_hawkes` around line 287). That is a *welfare-yield-per-nominal-dollar* metric, not a partition of nominal volume into productive and parasitic shares. `parasitic_nominal_residual = 1 - productive_welfare_yield` is therefore not the parasitic share of nominal — it is `1 − welfare_per_nominal`.

The dashboard caption was updated to read "Welfare yield" and "Nominal residual" (`engine/build_dashboard.py:506`) but the variable names still say "share." Make the names match the math.

### What to do

Rename across the codebase:

- `productive_welfare_yield` names the fold nominal converted to real welfare.
- `parasitic_nominal_residual` names the remaining nominal residual.

Files that need editing (use Grep to confirm none missed):

- `engine/core/folding.py` — `FoldingResult` dataclass field, the local `productive_welfare_yield` variable in both fold kernels.
- `engine/core/metrics.py` — `StepMetrics` field declarations, the `step_metrics` keyword argument, the local `productive_share`/`parasitic_share` variables, the assignments to `m`.
- `engine/core/world.py` — the `productive_welfare_yield=fold.productive_welfare_yield` keyword argument to `metrics.step_metrics`.
- `engine/build_dashboard.py` — the JS `h.productive_welfare_yield`, `h.parasitic_nominal_residual` lookups around lines 873–876.
- `engine/sensitivity.py` — `productive_welfare_yield` appears in the `outputs` tuple of `run_sobol_sensitivity`.
- `engine/tests/test_productive_folding.py` — every reference (about a dozen).
- `docs/concepts/demand_and_intermediation.md` — the "Reading the metrics" section names these explicitly. Update.
- `docs/concepts/epistemic_status.md` — does not reference the metric names directly; check anyway.

The dashboard JS variable handles (`pfs`, `pas`) can stay; rename only the keys read from `h.`*.

### Exit condition

```bash
rg "productive_welfare_yield|parasitic_nominal_residual" engine/ docs/
```

returns nothing. All tests pass.

---

## Task 2 — Save updated baselines for the 15 canonical scenarios

### Why

Files in `outputs/runs/*.json` are the regression baselines that an earlier pass of the engine produced. They were generated at a different runtime scale, so absolute welfare values are off by ~100×. EBI, which is a ratio, is now within 2.6% of those baselines, but downstream tooling (Task 3 below) needs new baselines that match the current default scale.

### What to do

1. Pick a deterministic seed convention. Each scenario already sets its own seeds inside `WorldConfig`; just use `World.build(get_scenario(name)).run()` at the default scale.
2. Write a short script `scripts/regenerate_baselines.py` that:
  - Iterates `engine.scenarios.SCENARIOS`.
  - Builds and runs each at the default scale (no scale-up overrides).
  - Serializes the metrics history identically to the existing JSON files. Look at the existing format; the structure is `{"history": <dict-of-arrays>, "config": <stable subset>}`. Match it.
  - Writes to `outputs/runs/<name>.json`, overwriting.
3. Commit nothing yet; this is a baseline pass, not engine work.

### Exit condition

For each scenario in `engine.scenarios.SCENARIOS`, `outputs/runs/<name>.json` exists and re-running `World.build(get_scenario(name)).run()` reproduces it bit-for-bit (modulo float-noise tolerance < 1e-9).

---

## Task 3 — Add a backward-compatibility regression test

### Why

The plan that produced the demand and productive-folding work had an acceptance criterion G1: "EBI within ±20% of baseline." That tolerance was set when no baselines existed. Now they do. The test bar should tighten.

### What to do

Create `engine/tests/test_regression_canonical.py`:

```python
"""Regression test against saved canonical baselines.

Re-runs each baseline scenario, compares terminal metrics to the JSON files
in outputs/runs/. The bar is tight (|ΔEBI| < 5%) because all three new
mechanisms are flag-gated and the canonical scenarios opt none of them in.
A failure here means a change to the engine has silently shifted what the
default code path computes — investigate before merging.
"""
```

Implement:

- A pytest parametrize over the 15 canonical scenario names (the ones that have a saved baseline).
- For each, load the JSON, run the scenario, assert:
  - `abs(new_terminal_EBI - old_terminal_EBI) / old_terminal_EBI < 0.05`
  - Same scenario classification (`Topology.label()` unchanged)
- Skip scenarios whose JSONs don't exist (so the test is OK to land before Task 2 completes).

### Exit condition

`pytest engine/tests/test_regression_canonical.py` passes for all 15 baselines.

---

## Task 4 — Add an explicit productive-welfare cap test

### Why

`TopologyConfig.max_productive_real_share` is the load-bearing safeguard against "free welfare from nominal recursion." There is no test that the cap actually clamps. If a future refactor reshuffles the order of operations in `_fold_surplus_geometric` or `_fold_surplus_hawkes`, the cap could become a dead code path silently.

### What to do

Append to `engine/tests/test_productive_folding.py`:

```python
def test_productive_real_added_capped_by_max_share():
    """The cap is the safeguard against free welfare from nominal recursion.
    With aggressive parameters that would otherwise produce arbitrarily large
    productive welfare, real_added_productive must not exceed
    base_real_surplus * max_productive_real_share."""
    topo = _topology(
        base_variance_absorption=0.55, productive_decay=0.85,
        alpha=0.95, folding_propensity=0.78, folding_branching=4.0,
        folding_max_depth=8, fold_nominal_multiplier=2.4,
    )
    topo.cfg.max_productive_real_share = 0.60
    base_real = 100.0
    fold = fold_surplus(
        base_real_surplus=base_real, base_nominal_volume=200.0,
        topo=topo, rng=np.random.default_rng(0), cap_intermediating=0.95,
    )
    assert fold.real_added_productive <= base_real * 0.60 + 1e-9
    assert fold.real_added_productive == pytest.approx(60.0)


def test_productive_real_added_uncapped_when_share_high():
    """Sanity check: if the cap is set above the natural ceiling, the
    productive contribution sits below the cap and the cap is not binding."""
    topo = _topology(
        base_variance_absorption=0.10, productive_decay=0.5,
        alpha=0.30, folding_propensity=0.20, folding_branching=2.0,
    )
    topo.cfg.max_productive_real_share = 1.00
    fold = fold_surplus(
        base_real_surplus=100.0, base_nominal_volume=200.0,
        topo=topo, rng=np.random.default_rng(0), cap_intermediating=0.85,
    )
    assert 0.0 < fold.real_added_productive < 100.0
```

### Exit condition

Both tests pass. Combined test count is 85/85.

---

## Task 5 — Histogram check on `cap_slope` for sigmoid bimodality

### Why

The plan flagged `cap_slope = 4.0` as a candidate for producing a near-step-function at the capability midpoint. Across scenarios where agent capability clusters around 0.4–0.85, the productive-share sigmoid moves from 0.02 to 0.98 over that range. If the realized distribution of `productive_share` across scenarios and Sobol points is bimodal at 0 and 1, the metric is uninformative. The plan said: lower `cap_slope` to 2.5 if so.

### What to do

1. Run the Sobol sweep for the alpha-engine at the existing default size: `python -m engine.cli sobol --n 64` (or whatever the current invocation is — check `engine/cli.py` for the exact flag). This is the same sweep the dashboard uses; it already has `cap_slope` as a swept parameter.
2. From the resulting samples, extract the per-sample value of `productive_welfare_yield`. Plot a histogram (matplotlib is fine; do not add it to the dashboard).
3. Inspect:
  - If the histogram has clear bimodal mass at 0 and the maximum yield (≈ 0.4 with default params), lower `TopologyConfig.cap_slope` from 4.0 to 2.5 in `engine/core/topology.py`. Re-run the sweep to confirm the mass smooths out.
  - If the histogram is unimodal or monotone, leave `cap_slope = 4.0`.
4. Either way, write a one-paragraph note in `docs/concepts/demand_and_intermediation.md` under "What it does not say," summarizing what the sweep showed.

### Exit condition

Either `cap_slope` is unchanged with a documented justification, or it is 2.5 with a documented justification. Either way, the concept doc has a paragraph reporting the actual distribution observed.

---

## Task 6 — Clean up `World.law_strength` / `law_capture` dataclass defaults

### Why

```python
@dataclass
class World:
    ...
    law_strength: float = 1.0
    law_capture: float = 0.0
```

These dataclass defaults are dead — `World.build` always overrides them based on `topo.cfg.law.enabled`. Anyone constructing a `World` directly (not via `build`) would get inconsistent state. The defaults should either be removed or be `None` with an `__post_init__` that resolves them from the topology config.

### What to do

Two acceptable fixes — pick the simpler one:

- **Option A (preferred):** delete the dataclass defaults. Mark `law_strength: float` and `law_capture: float` as required fields. Confirm `World.build` always sets them (it does). This breaks any caller that constructs `World(...)` directly without going through `build`. Grep the repo: `rg "World\(" engine/`. If the only callsite is `World.build`, just delete the defaults.
- **Option B:** keep the defaults but rename them to `_default_law_strength = 1.0, _default_law_capture = 0.0` and add a docstring noting they are unused by `World.build`.

### Exit condition

`grep -n "law_strength: float" engine/core/world.py` shows the field has no inline default value (Option A) or has a renamed default (Option B). Tests still pass.

---

## Task 7 — Tune or document `derivatives_revolution`

### Why

`derivatives_revolution` currently terminates at `real_per_capita_welfare ≈ 0.098`, about 1.9× `coasean_paradise`'s 0.052. The plan called this scenario a "limit-test scenario" that "should not produce free welfare ad infinitum." With the productive cap in place, free welfare is bounded — but 1.9× paradise is still a strong claim. Two possibilities:

(a) The model is correctly saying "low Matryoshka taxes + productive folding outperforms paradise on welfare." That is a defensible model claim.

(b) The scenario's parameter combination accidentally stacks several positive-welfare effects (low taxes, productive folding, mid-alpha) and overstates the case.

### What to do

1. Run `derivatives_revolution` and three perturbations:
  - `derivatives_revolution` with `base_variance_absorption = 0.0` (productive folding off).
  - `derivatives_revolution` with `market_layer_tax = 0.025` and `individual_layer_alignment_tax = 0.020` (paradise-equivalent taxes).
  - Both perturbations together.
2. If the productive-folding-off run alone reaches per-capita welfare > 1.5× paradise, the dominant effect is low Matryoshka taxes, not productive folding. In that case, tune up taxes so the bare scenario is at most 1.0× paradise; keep productive folding generous.
3. If the bare run is below paradise and only the productive-folding-on version overshoots, the dominant effect is the productive split. Decide: keep the scenario as a "limit test that intentionally overshoots" and document this in the docstring, or tune `base_variance_absorption` from 0.55 down to ~0.35 until terminal welfare lands in [0.06, 0.09].
4. Update the docstring with whichever interpretation you adopted.

### Exit condition

`derivatives_revolution`'s docstring explicitly states what its terminal welfare should be relative to paradise, and a single run reproduces that statement.

---

## Task 8 — Investigate the residual EBI drift on existing scenarios

### Why

After Tasks 1–7, the canonical scenarios still drift 0.5–2.6% on EBI relative to the saved baselines (see `coasean_paradise -0.04%`, `equilibrium_drift -2.61%`). For paradise the drift is float noise; for higher-alpha scenarios it is not, but it is uniform across the 15 scenarios in sign and magnitude. The most likely cause is a tiny structural change in the fold-loop initialization that consumes RNG state differently on a hot path that no longer fires.

This is **not blocking** — classifications hold and the test suite passes. But the drift accumulates if other changes ride on top of it, so identify the source now.

### What to do

1. `git stash` your working changes (if any).
2. Run `engine/scenarios.coasean_paradise()` against `git show HEAD:engine/core/transactions.py` and the current `transactions.py`. Compare the per-step `real_surplus_added` after step 0, step 1, step 2.
3. The first step where they diverge points at the line. Likely candidates:
  - `compat = topo.cross_stack[stk_a, stk_b]` is now computed twice (once at line 236 and once inside `transaction_cost`). Numerically identical, but worth confirming float-equivalence.
  - The two `np.zeros(n_pairs, dtype=np.float32)` allocations for `law_weak_loss_pair` and `law_capture_loss_pair` in the disabled-law branch could allocate-and-discard memory in a way that affects subsequent layout. Unlikely but cheap to check.
  - Any code that touches the rng before the original consumption point.
4. If found, fix it. If not, document the drift in `docs/concepts/epistemic_status.md` under "Failure modes worth naming" with a one-paragraph note.

### Exit condition

Either `coasean_paradise` reproduces baseline EBI to within float noise (< 0.05%) — same for the other 14 scenarios — or the drift is documented as a known limitation.

---

## Done criteria for the whole plan

- All 8 tasks marked done.
- `python -m pytest engine/tests/ -x` passes (target: 85+ tests).
- `outputs/runs/*.json` baselines regenerated and committed.
- `docs/concepts/demand_and_intermediation.md` and `docs/concepts/epistemic_status.md` updated where tasks called for it.
- A short status note in `brief/dynamic_mechanisms.md` (top of file) acknowledging that §3 (law) shipped alongside the demand/productive-folding plan and is currently flag-gated. This unblocks future work on §4–§6 of the brief.

---

## What this plan deliberately does not do

- **Does not start §4–§6 of `brief/dynamic_mechanisms.md`.** Crowding-out, principal-agent decay, debt/leverage, and the bifurcation experiment all wait for a clean baseline.
- **Does not extend the Sobol problem.** `cap_slope` and the new parameters are already swept.
- **Does not refactor the law mechanism.** It is shipped, flag-gated, tested. Leave it alone until §4 begins.
- **Does not touch the exo-engine.** Out of scope.

When all eight tasks are green, the engine is in a clean state: three new mechanisms landed, all flag-gated, all documented, baselines saved, regression test in place. That is the state the brief assumes.
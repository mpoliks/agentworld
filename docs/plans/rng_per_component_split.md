# Per-component RNG split

Status: `engine/core/world.py:114` builds a single `np.random.default_rng(cfg.seed)` and threads it through every step function. Each subsystem (`transactions`, `folding`, `population` entry/exit, `demand`, `exo` layers) draws from this one stream. Swapping any one parameter shifts the draw sequence consumed by every other subsystem, which corrupts variance attribution in Sobol/Saltelli sweeps and produces noise on small-effect parameters that is indistinguishable from real first-order influence.

This plan stands alone. Read these inputs only:

- `engine/core/world.py` (the `World.build` classmethod and the `step` method)
- `engine/core/transactions.py` (every `rng.random` / `rng.choice` call)
- `engine/core/folding.py` (the geometric and Hawkes fold kernels)
- `engine/core/population.py` (entry/exit and bandit draws)
- `engine/core/network.py`, `engine/core/noise.py` (any `rng` use)
- `engine/exo/world.py` and the four exo-layer modules (`last_mile.py`, `drag.py`, `differential.py`, `imperial.py`)
- `engine/sensitivity.py` (the Saltelli driver, to confirm what ST attribution it claims)
- `engine/tests/test_engine.py`, `engine/tests/test_regression_canonical.py`

## Dependencies

None. This plan is the prerequisite for plans 3, 4, 5, 6, and 9. Land it first.

## Why

A trustworthy Sobol-based ST claim requires that the only source of variance between two parameter samples is the parameter being varied. With a single shared RNG, varying a parameter that gates `n_pairs` (e.g. cost) shifts the position of every downstream `rng.random` call for the rest of the step, which means every other subsystem sees a different draw sequence. Saltelli still converges, but it converges on a noised estimate where ~10–30% of the apparent first-order variance is attributable to draw-sequence shifts rather than the parameter under test. We see this as small-but-non-zero S1 on parameters that the model is mathematically independent of.

The fix is per-component RNG: each subsystem reads from a child `Generator` spawned from the seed, and a parameter change that perturbs how many draws subsystem A makes does not move subsystem B's draws.

## What to do

### Task 1 — Spawn named children at build time

In `engine/core/world.py` `World.build`:

```python
seed_seq = np.random.SeedSequence(cfg.seed)
children = seed_seq.spawn(8)
rngs = {
    "population":  np.random.default_rng(children[0]),
    "market":      np.random.default_rng(children[1]),
    "alignment":   np.random.default_rng(children[2]),
    "law":         np.random.default_rng(children[3]),
    "folding":     np.random.default_rng(children[4]),
    "demand":      np.random.default_rng(children[5]),
    "network":     np.random.default_rng(children[6]),
    "exo":         np.random.default_rng(children[7]),
}
```

Pass this dict to the `World` dataclass instead of the single `rng`. Update `World`'s field from `rng: np.random.Generator` to `rngs: dict[str, np.random.Generator]`.

### Task 2 — Plumb to call sites

For every existing `self.rng.random(...)` / `self.rng.choice(...)` call, route to the appropriate child:

- `engine/core/transactions.py` — `rngs["market"]` for the market gate, `rngs["alignment"]` for the alignment gate, `rngs["law"]` for the law gate, `rngs["network"]` for pair sampling.
- `engine/core/folding.py` — `rngs["folding"]` for fold-depth and Hawkes draws.
- `engine/core/population.py` — `rngs["population"]` for entry/exit and bandit draws.
- `engine/core/noise.py` — `rngs["demand"]` if it gates demand-side noise; otherwise re-categorise.
- `engine/exo/*` — every `rng.*` call routes to `rngs["exo"]`.

For each module, the public step function should accept either the dict or the specific child it needs. Prefer passing only the specific child to keep the call site honest about which stream it consumes.

### Task 3 — Backward-compat shim for the canonical pinned runs

`engine/tests/test_regression_canonical.py` pins bit-for-bit reproduction of current canonical metrics. The naive RNG split breaks this, because the same `cfg.seed` now produces a different draw sequence. Two acceptable resolutions:

- **Preferred:** re-pin the canonical metrics under the new RNG layout. The math is unchanged, so EBI/Gini/welfare differ by within-distribution noise. Update `outputs/runs/*.json`. This is allowed because the round-overview specifies "no silent changes" but here the change is announced and tested.
- **Fallback if re-pinning is too invasive in this round:** add `WorldConfig.rng_split_mode: Literal["legacy", "per_component"] = "legacy"`. `legacy` uses the single global RNG (current behavior). `per_component` uses the new layout. Switch canonical to `per_component` later, after plans 3–7 have landed.

Pick one. The fallback is deferrable; the preferred is cleaner. Default to fallback if uncertain.

### Task 4 — Order-permutation invariance test

New file `engine/tests/test_rng_isolation.py`:

```python
def test_subsystem_order_permutation_invariance():
    """With per-component RNG, permuting the order in which subsystems
    consume draws inside a single step must leave terminal metrics unchanged.
    Under the legacy single-RNG layout, this test must FAIL — proving the
    isolation property is what's being verified."""
```

Run a canonical scenario twice: once with the default subsystem order, once with the order swapped (e.g. fold-then-trade vs. trade-then-fold *for the rng draws only*; do not actually swap the engine math, only the order in which draws are taken). Under per-component RNG, terminal EBI/Gini/welfare are bit-for-bit identical. Under legacy, they differ by ~1% — the test should be parametrized over `rng_split_mode` if Task 3's fallback is used.

### Task 5 — Sensitivity-driver update

`engine/sensitivity.py` does not need code changes (it constructs `WorldConfig`s, not RNGs), but the Sobol output documentation should now state ST attribution is reliable down to 0.005 (was 0.03 under legacy noise floor).

## Exit conditions

- All existing tests pass.
- `test_rng_isolation.py` passes under `per_component`.
- A re-run of the canonical Sobol sweep with N=2048 shows ≥ 70% of the parameters that previously had `0.005 < S1 < 0.03` now collapse to `S1 < 0.005`. (This empirical check confirms the noise floor dropped.)
- `World.rngs` is the only attribute holding `Generator`s; `World.rng` is removed (or aliased to `rngs["market"]` for backward compat in any user-supplied notebook).

## Acceptance test

```bash
python -m pytest engine/tests/ -x
python -m pytest engine/tests/test_rng_isolation.py -v
```

All green. The order-permutation test passes under `per_component` and (if Task 3 fallback path is taken) fails under `legacy`.

## Notes for the executor

- Do not change any sampling distribution. `np.random.Generator.random` and `np.random.Generator.choice` semantics are preserved — only the `Generator` object handing them out is swapped.
- Do not switch to `numpy.random.Philox` or any non-default bit generator. Default `PCG64` with `SeedSequence.spawn` is sufficient and matches the existing `default_rng(seed)` bit generator.
- The eight subsystem categories are not load-bearing; if it's cleaner to spawn six or twelve, do so. The contract is one child per subsystem boundary.

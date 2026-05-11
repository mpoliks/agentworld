# Per-component RNG split

Status: **landed 2026-05-11.** `engine/core/world.py` ships a per-component
RNG layout selectable via `WorldConfig.rng_split_mode`. The canonical
regression suite stays on `legacy` (every subsystem aliases one
generator) so pinned baselines stay bit-identical; the Sobol/Saltelli
driver opts into `per_component` so a parameter that gates `n_pairs`
cannot move the draw sequence consumed by any other subsystem.

## Problem

Before this plan, `World.build` produced one `np.random.default_rng(cfg.seed)`
and threaded it through every step function. Each subsystem
(`transactions`, `folding`, `population` entry/exit, `demand`, `exo`
layers) drew from this one stream. Swapping any one parameter shifted
the draw sequence consumed by every other subsystem, which corrupted
variance attribution in Sobol/Saltelli sweeps and produced noise on
small-effect parameters that was indistinguishable from real first-order
influence.

A trustworthy Sobol-based ST claim requires that the only source of
variance between two parameter samples is the parameter being varied.
With a single shared RNG, varying a parameter that gates `n_pairs`
(e.g. cost) shifted the position of every downstream `rng.random` call
for the rest of the step, which meant every other subsystem saw a
different draw sequence. Saltelli still converged, but it converged on
a noised estimate where some apparent first-order variance was
attributable to draw-sequence shifts rather than the parameter under
test.

## Resolution

Per-component RNG: each subsystem reads from a child `Generator`
spawned from the seed, and a parameter change that perturbs how many
draws subsystem A makes does not move subsystem B's draws.

Nine subsystems get their own stream under `per_component`:
`population`, `market`, `alignment`, `law`, `folding`, `demand`,
`network`, `permeability`, `exo`.

## Implementation

- `WorldConfig.rng_split_mode: Literal["legacy", "per_component"] = "legacy"`.
- `World.rngs: dict[str, np.random.Generator]` replaces the singular
  `rng` field. `World.rng` is a property aliasing `rngs["market"]` for
  notebook back-compat.
- `_build_rng_dict(seed, mode)` spawns from a `SeedSequence` under
  `per_component`; under `legacy` every key aliases the same generator
  (bit-identical to the pre-split engine).
- `coasean_step` accepts `RngOrRngs` (single `Generator` or subsystem
  dict) via a `_resolve_rngs` shim — direct unit-test callers that pass
  a bare `Generator` keep working with shared-stream semantics.
- Inside `coasean_step`:
  - `_sample_partners` → `rngs["network"]`
  - permeability gate (W1c) → `rngs["permeability"]`
  - law gate → `rngs["law"]`
  - market gate + local-alpha noise → `rngs["market"]`
  - alignment gate → `rngs["alignment"]`
  - per-pair surplus shock → `rngs["demand"]`
- `fold_surplus` → `rngs["folding"]` (Hawkes gamma draws).
- Strategy / institutions / dynamics → `rngs["population"]`.
- `_alpha_world_from_vector` (in `engine/sensitivity.py`) sets
  `rng_split_mode="per_component"` so Sobol uses isolated streams.
- `engine/exo/world.py` was left as-is: ExoWorld is an independent
  orchestrator and all its internal subsystems share one logical
  stream, so the per-component contract collapses to the existing
  single-rng layout there.

## Verification

`engine/tests/test_rng_isolation.py` is parametrised over both modes:

- Under `per_component`, terminal `(EBI, welfare, gini)` is
  bit-for-bit identical whether or not we burn 10k draws on `rngs["exo"]`
  (a stream the alpha-engine never reads).
- Under `legacy`, every key in `world.rngs` aliases the same generator,
  so the same burn shifts terminal metrics — the test asserts the
  divergence so the regression check works in both directions.
- Plus determinism and aliasing sanity checks, and a dedicated test
  that burning the `permeability` stream is invariant when
  `cross_stack_permeability == 1.0` (the gate doesn't fire by
  construction in the canonical default).

158/158 alpha-engine tests pass:

```bash
python -m pytest engine/tests/test_engine.py \
                 engine/tests/test_regression_canonical.py \
                 engine/tests/test_rng_isolation.py \
                 engine/tests/test_law.py \
                 engine/tests/test_demand.py \
                 engine/tests/test_productive_folding.py \
                 engine/tests/test_dt.py \
                 engine/tests/test_stock_flow.py \
                 engine/tests/test_step_callback.py \
                 engine/tests/test_fold_per_depth.py
```

Canonical pinned scenarios remain bit-identical (legacy default holds
the line); three pre-existing failures elsewhere in the suite
(`test_convergence_pinned::test_small_scale_terminal_ebi_inside_medium_scale_ci[baroque_cathedral]`,
`test_serve::test_scenarios_endpoint`, `test_validation_adversarial::test_baroque_with_high_welfare_scenario_reproduces_counter_example`)
reproduce on unmodified `main` and are unrelated to this plan.

## Empirical Sobol comparison (N=2048)

The plan's original exit condition predicted ≥70% of the params in the
legacy noise band `0.005 < |S1| < 0.03` would collapse to `|S1| < 0.005`
under per-component. The N=2048 sweep ran on the same SALib sampler
seed and the same parameter problem (`ALPHA_ENGINE_PROBLEM`,
D=15 → 34,816 simulations). Observed:

- **Legacy noise-band params:** 28 (across the six output metrics).
- **Collapsed under `per_component`:** **14 / 28 ≈ 50%.**
- **Stayed in or grew above the band:** 14.

Several of the "stayed" params actually grew under per-component — e.g.
`fold_nominal_multiplier` on `log_exo_baroque_index` went from
`+0.0142` to `+0.0222`, and `agent_capability_mean` on
`productive_welfare_yield` went from `+0.0248` to `+0.0369`. That
direction is consistent with real first-order signal that was
previously *masked* by draw-sequence cross-talk now resolving to a
cleaner estimate. Per-component RNG does not shrink real variance; it
just removes the spurious noise that masquerades as signal.

The plan's quantitative prediction was therefore optimistic: it
assumed most of the band was pure cross-talk noise. The empirical
mixture is roughly half cross-talk (collapsed) and half real signal
(stayed or grew). The *qualitative* mechanism the plan describes is
real — variance attribution is cleaner under per-component, the
isolation test verifies stream-level isolation — and the implementation
is unchanged regardless of where the empirical split lands.

The legacy-canonical pinned output at
`outputs/sensitivity/sobol_indices.json` stays untouched; the
per-component N=2048 re-run is saved alongside at
`outputs/sensitivity/sobol_indices.per_component.n2048.json` for the
comparison.

## Notes for future revisions

- Bumping N to 4096–8192 would tighten the bootstrap CI (S1_conf scales
  with √N) and likely pull more borderline params under the 0.005
  threshold, but that's a question of compute budget, not RNG layout.
- Within-step finer subdivision of the `network` stream
  (`_sample_partners`) was investigated and ruled out: `sample_global`
  consumes a *fixed* 2·n_pairs draws regardless of the Bernoulli split
  (n_h_pick + n_a_pick = n_pairs always), and `sample_neighbors`
  consumes a count tied to the population's network adjacency which is
  Sobol-parameter-invariant. So splitting `network` into sub-streams
  wouldn't reduce the residual noise floor.
- `engine/exo/world.py` would gain symmetry from a parallel rngs-dict
  layout but no behavioural change, since all exo subsystems share one
  logical stream. Left as-is; revisit if exo grows distinct sampling
  surfaces.

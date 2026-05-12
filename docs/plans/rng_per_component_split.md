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
under per-component. The N=2048 sweep ran the SALib sampler with
`calc_second_order=False` over `ALPHA_ENGINE_PROBLEM` (D=15 → 34,816
simulations) against both layouts. The result reframes the question.

### What the magnitude threshold said

- Legacy params in `0.005 < |S1| < 0.03`: **28** (across six metrics).
- Collapsed to `|S1| < 0.005` under per-component: **11 / 28 ≈ 39%.**
- Plan threshold (≥70%): **not met.**

### What the magnitude threshold was missing

`|S1| < 0.005` conflates "magnitude is small" with "value is
statistically indistinguishable from zero." The proper noise test is
whether the bootstrap CI on S1 straddles zero (i.e. `|S1| < S1_conf`).
Classifying every band param under both layouts gives four transitions:

| Transition | Count | What it means |
|---|---|---|
| `noise → noise` | 10 | CI included 0 both ways; legacy didn't lie. |
| `signal → noise` | **3** | Legacy looked like signal but the apparent S1 was draw-cross-talk artifact — exactly what the plan was meant to catch. |
| `noise → signal` | **7** | Legacy hid real first-order signal in the noise band; per-component reveals it (and S1 *grows*). |
| `signal → signal` | 8 | Genuine first-order effects; stable across layout. |

Mean `|S1|` in the band: legacy 0.0107 → per-component 0.0122 (slight
increase). The per-component split does not shrink real signal; it
reclassifies it. The plan's "noise floor drops" intuition was right
in spirit but wrong in mechanism — what drops is the *misattribution*,
not the magnitude.

### Why the plan's 70% prediction was optimistic

The plan assumed most of the band was pure cross-talk noise. The
empirical mixture is: 3/28 (11%) were genuine cross-talk artifact that
the RNG split correctly unmasked; 7/28 (25%) were masked real signal
the legacy noise was hiding; 8/28 (29%) were stable real signal;
10/28 (36%) were noise in both layouts (still inside the
`|S1| ≈ S1_conf` regime even with the split — these would only resolve
under a tighter Sobol CI, i.e. larger N).

The implementation contract — *streams are isolated so a parameter's
draw consumption cannot perturb another subsystem's sequence* — is
verified independently by `engine/tests/test_rng_isolation.py`. The
empirical Sobol comparison is a downstream consequence of that
contract, not a test of it. The honest takeaway is: the per-component
layout makes the signal/noise classifier defensible per-parameter,
which is what the dashboard needs in order to label `fold_nominal_multiplier`
on `log_exo_baroque_authentic` as `noise → signal` (real but legacy
hid it) vs `agent_capability_mean` on `productive_welfare_yield` as
`signal → noise` (legacy lied about it).

The legacy-canonical pinned output at
`outputs/sensitivity/sobol_indices.json` stays untouched; the
per-component N=2048 re-run is saved alongside at
`outputs/sensitivity/sobol_indices.per_component.n2048.json` for the
comparison.

## Notes for future revisions

- Bumping N to 4096–8192 would tighten the bootstrap CI (S1_conf scales
  with √N) and likely pull more borderline params under the 0.005
  threshold, but that's a question of compute budget, not RNG layout.
- **Empirical N=4096 result (2026-05).** Ran `agentworld sobol --samples
  4096` under `caffeinate -i`; ~107 minutes wall single-threaded on
  the dev box (the plan's "~28 minutes pinned" estimate assumed a
  CPU-budget profile this environment did not hit). Pinned at
  `outputs/sensitivity/sobol_indices.per_component.n4096.json`. The
  CI-aware comparison harness lives at `engine/sensitivity_compare.py`;
  the four-way transition counts for `N=2048 → N=4096` (across all 6
  metrics × 15 params = 90 pairs):
  `noise → noise: 51, signal → noise: 9, noise → signal: 5,
  signal → signal: 25`. The plan-bet that "about half of the
  noise→noise band collapses" did not materialise — only 14 of the 65
  noise→noise params at N=2048 changed class. Most of the residual
  band is structural (true `|S1| < 0.002`), not CI-limited. The
  per-metric breakdown is dominated by `productive_welfare_yield`
  (7 flips of 15 params); the headline EBI + welfare + Gini panels
  show 0–2 flips each. Canonical pin stayed at N=2048
  (`outputs/sensitivity/sobol_indices.json`); the N=4096 artifact is
  kept as a high-resolution auxiliary for any analysis that wants
  tighter CIs on the borderline band. Pairwise comparison artifact at
  `outputs/sensitivity/sobol_n_bump_comparison.json`. See
  `docs/plans/sobol_n_bump.md`.
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

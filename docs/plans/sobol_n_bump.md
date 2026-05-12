# Sobol N bump — push residual band-params under the CI floor

Status: drafted 2026-05-12. Compute-bound follow-up to
`rng_per_component_split.md`. Bumps the canonical Sobol sweep from
N=2048 to N=4096 (or 8192 if budget allows) so the bootstrap CI
tightens enough to resolve the 10 `noise → noise` params that the
per-component re-pin left inside the `|S1| ≈ S1_conf` regime.

## Dependencies

`rng_per_component_split.md` (`commit cf0f444`) landed the
per-component RNG layout and the CI-aware comparison. This plan
builds on that comparison.

## Why

The N=2048 per-component re-pin classified the 28 legacy noise-band
params into four transitions:

| Transition | Count |
| --- | --- |
| `noise → noise` (CI ∋ 0 both ways) | 10 |
| `signal → noise` (unmasked cross-talk) | 3 |
| `noise → signal` (revealed signal) | 7 |
| `signal → signal` (stable) | 8 |

The 10 `noise → noise` params have `|S1| < S1_conf` under both
layouts: the magnitude is small *and* the CI straddles zero. These
are the only candidates where further work could move the needle,
and the leverage point is N, not RNG layout — Sobol CI scales as
1/√N.

Doubling N halves the CI width. A handful of the 10 params have
`|S1|` in the 0.003–0.005 range with `S1_conf` of 0.005–0.008; under
N=4096 their CIs would shrink to ~0.0035–0.0057, putting roughly
half of them on the right side of the `|S1| > S1_conf` line. At
N=8192 most should resolve.

## What to do

### Task 1 — Time the N=4096 sweep

Empirically the N=2048 sweep ran in 14:18 of CPU (≈ 85 ms/sim across
34,816 sims). N=4096 = 69,632 sims ≈ 100 minutes CPU under macOS App
Nap-style throttling, or ~28 minutes if pinned with `caffeinate -i`.

Run the sweep under `caffeinate -i` to a separate path:

```bash
caffeinate -i agentworld sobol \
  --samples 4096 \
  --out outputs/sensitivity/sobol_indices.per_component.n4096.json \
  --no-progress
```

### Task 2 — Re-run the CI-aware comparison

`/tmp/sobol_compare.py` from the original RNG round is the
comparison harness. Promote it into the engine:
`engine/sensitivity_compare.py` with a `compare_sobol_outputs(legacy,
percomp_n2048, percomp_n4096)` function returning the four-way
transition counts at each N.

Expected output (the bet):

- N=2048 → N=4096: half of the `noise → noise` band collapses to
  `signal → signal` or `signal → noise` as CIs tighten. The other
  half stays.
- N=2048 → N=8192: most of the remaining `noise → noise` band
  resolves. A small residual stays — these are the params with
  genuinely zero first-order effect on the metrics in question.

Pin the comparison output to
`outputs/sensitivity/sobol_n_bump_comparison.json`.

### Task 3 — Decide whether to re-pin the canonical N

If the N=4096 comparison shows the dashboard's headline Sobol panels
materially change (more than two params flip transition class), the
canonical pin in `outputs/sensitivity/sobol_indices.json` should
update to N=4096. Otherwise leave it at N=2048 and treat N=4096 as
an auxiliary high-resolution artifact.

This is a judgement call best made after seeing the numbers.

## Exit conditions

- `outputs/sensitivity/sobol_indices.per_component.n4096.json` pinned.
- `engine/sensitivity_compare.py` is the canonical CI-aware
  comparison harness (replaces the `/tmp/sobol_compare.py` script
  that lives outside the repo).
- A short note added to `docs/plans/rng_per_component_split.md`
  "Notes for future revisions" with the empirical N=4096 result.

## Notes for the executor

- N=8192 doubles the time again (~56 minutes pinned). Run it only if
  the N=4096 result motivates it.
- The Sobol estimator's variance scales as `1/N`, so the *CI* (which
  is the bootstrap-sd, scaling as `1/√N`) tightens slowly. A
  param at `S1_conf ≈ 0.005` at N=2048 lands at `S1_conf ≈ 0.0035`
  at N=4096, not zero. If a param has true `|S1| < 0.002`, no
  feasible N resolves it.
- The dashboard's existing panels read the canonical pinned output
  by path; if the canonical pin moves to N=4096 the dashboard
  re-renders without code change.

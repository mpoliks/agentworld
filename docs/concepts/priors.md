# Priors over speculative parameters

> *"The numbers are robust to the prior exactly to the extent that the prior is honest about what it doesn't know."* — `docs/plans/_archive/validation_lift_plus_live_viz.plan.md`, A2.

The α-engine and exo-engine carry an inventory of *load-bearing speculative
parameters*: knobs that have no historical analog at the 800B-agent scale,
that the brief stipulates rather than fits. Until they are wrapped in a
declared prior, every claim about model behavior is implicitly conditioned
on a delta-distribution at the default value, which is unfalsifiable.

This artifact wraps eleven of those knobs in priors and runs a Sobol-
quasi-random sweep to expose the *outcome distribution* the model produces
under stated parameter ignorance.

## The inventory

Eleven priors, declared in
[`engine/validation/priors.py`](../../engine/validation/priors.py).

### α-engine subset (drives the canonical sweep)

| Prior | Family | Bounds | Why this width |
| --- | --- | --- | --- |
| `folding_propensity` | uniform | [0.10, 0.85] | Above 0.85 produces uninterpretable runaway; below 0.10 mutes the mechanism. |
| `fold_real_efficiency` | uniform | [0.40, 0.96] | 0.40 is aggressive value loss; 0.96 near-frictionless compounding. |
| `fold_nominal_multiplier` | uniform | [1.0, 3.0] | 1.0 is no GDP inflation; 3.0 saturates the cascade quickly. |
| `base_variance_absorption` | uniform | [0.0, 0.60] | 0.0 is parasitic-only; 0.60 is aggressively productive. |
| `productive_decay` | uniform | [0.40, 0.95] | Lower = welfare creation only at top of cascade; higher = welfare deeper down. |
| `max_productive_real_share` | uniform | [0.30, 0.90] | The cap that keeps welfare bounded by underlying real surplus. |
| `cap_slope` | uniform | [2.0, 6.0] | 2.0 is gentle sigmoid; 6.0 is near-step-function bimodal. |

### exo-engine subset (declared, not swept here)

| Prior | Family | Bounds |
| --- | --- | --- |
| `drag_target_intensity` | uniform | [0.10, 0.55] |
| `stack_base_lift_propensity` | uniform | [0.20, 0.65] |
| `suppression_strength` | uniform | [0.05, 0.55] |
| `suppression_cost_exp` | uniform | [1.2, 3.5] |

A parallel exo sweep is out of scope for A2 of this plan. The priors are
declared here so the inventory is complete and a future exo sweep
inherits the same priors-as-documentation contract.

## How the sweep works

[`engine/validation/posterior_sweep.py`](../../engine/validation/posterior_sweep.py)
draws *n* Sobol samples in [0, 1]ⁿ_priors, maps each to the prior's
support, and runs a short-horizon (n_steps=20) α-engine evaluation per
sample. Sobol is used for *coverage*, not Sobol *indices*: 2000 samples
of seven priors give a well-spread design that a Saltelli scheme would
need ~`2000 × (7 + 2) = 18000` runs to produce.

Each evaluation produces:
- `terminal_ebi`
- `terminal_real_per_capita_welfare`
- `basin` ∈ {`smooth`, `mixed`, `baroque`, `diverged`} via outcome rule:
  - `smooth`: `terminal_ebi ≤ 1.5`
  - `baroque`: `terminal_ebi ≥ 5.0`
  - `mixed`: in between
  - `diverged`: non-finite (should not happen for these bounds)

Outputs:
- `outputs/validation/posterior_sweep.parquet` — full per-sample table.
- `outputs/validation/posterior_sweep.summary.json` — basin probabilities
  and outcome quantiles.
- `outputs/validation/posterior_sweep.png` — basin bar chart + EBI
  histogram.

## Result, current vintage (n=2000, seed=0)

```
n_samples:    2000
elapsed_sec:  46.4
P(smooth):    1.85%
P(mixed):     66.05%
P(baroque):   32.10%
P(diverged):  0.00%

terminal EBI:    p05=1.58   p50=3.18   p95=22.34
welfare/capita:  see summary.json
```

### What this says

**Under the stated prior, the modal outcome is "mixed" (66%).** The
canonical Smoothworld basin (Krier limit) is small — under 2% of the
prior weight lands in EBI ≤ 1.5. About a third of the prior weight
lands in Baroqueworld (EBI ≥ 5).

**The EBI distribution has a fat right tail.** The median is 3.18
but the 95th percentile is 22.3 — a factor of 7 above median. Future
claims about "what EBI to expect" should cite the median *and* the p95.

**The Coasean basin is small but not vanishing.** The brief's claim
that Smoothworld is a basin of attraction is supported, but the size
of the basin under the stated prior is at least an order of magnitude
smaller than the Baroque basin. Whether that matches reality depends
on the prior; the prior here is wide.

### What this does NOT say

- It does not say the prior is right. The prior is wide on purpose. If
  the bounds on, say, `folding_propensity` were tighter, the Baroque
  basin shrinks. The numbers above are conditional on the bounds.
- It does not say which basin "the world" lives in. The basin
  probabilities here are over the engine's stated parameter
  uncertainty, *not* over states of the world.
- It does not say anything about exo-engine behavior. The exo priors
  are declared but not swept in this artifact.

### What downstream claims have to say

After this sweep lands, "the engine produces X" must come paired with
either:

- *X is in the modal mixed basin under the prior* (≥ 66% mass): the
  claim is robust to the wide prior.
- *X requires a tighter parameter region*: cite which prior bounds
  must contract for X to dominate.

A claim that ignores the prior is implicitly delta-distribution at the
scenario default — and is therefore unfalsifiable in the sense of
parameter uncertainty. Use the sweep, or say what region of the prior
your claim conditions on.

## Reproducing

```bash
agentworld validate priors --samples 256        # CLI default, ~6s
agentworld validate priors --samples 2000       # canonical artifact, ~46s
agentworld validate priors --samples 2000 --seed 7   # alt seed for robustness
```

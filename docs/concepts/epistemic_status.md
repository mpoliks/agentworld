# Epistemic Status of the Agentworld Engines

> *"The numbers are stylized. The dynamics are real."* — README

This document is the **rules of the game** for both engines (`engine/` and `engine/exo/`). It says, parameter by parameter, what kind of object we are claiming each thing is. It is the document we point at when someone asks "but what does the EBI of 47.3 in `baroque_cathedral` *mean*?" The honest answer is that 47.3 is not an estimate of anything. Some other numbers in the same run *are* anchored to public empirical sources. Most are not. This file tells you which is which.

---

## What kind of object the engines are

Neither engine is an estimator. Neither is a forecast. They are **generative thought instruments**: stochastic-dynamic systems whose role is to make a conceptual hypothesis (the smooth-striated dial; the lift / drag / last-mile / differential operators) operationally legible — the way a wind tunnel makes a hypothesis about lift visible without claiming to predict the lift coefficient of the next plane Boeing builds.

This has consequences for the kinds of claims the artifact can support and the kinds it cannot:

**Supports:**

- *Conditional* statements: "given parameter range X, the system enters basin Y under condition Z, with effect size E [5/95 CI: A, B]."
- *Sensitivity claims*: "of the ten knobs that move the EBI in the α-engine, two account for ~75% of the variance" (Sobol indices).
- *Disagreement claims*: "the α-engine's diagnostic (EBI = nominal/real) and the exo-engine's diagnostic (lift / referent_distance) disagree systematically across the following scenario family."

**Does not support:**

- Unconditional probability claims (`P(Baroqueworld by 2040) = 0.34`).
- Point predictions of macro variables (real GDP, real wages, Gini in 2032).
- Ranking which scenario "is more likely." Scenarios are *probes of the parameter space*, not weighted draws from a prior.

The two engines are kept deliberately distinct, calibrated by deliberately distinct ontologies, and reported side-by-side. If a reader walks away with one number from one engine, the artifact has failed.

---

## Three categories of parameter

Every knob in `TopologyConfig`, `LawConfig`, `PopulationConfig`, `StackConfig`, `DragConfig`, `DifferentialConfig`, `LastMileConfig`, `ImperialConfig`, and `RegionConfig` is one of three kinds:

- **Calibrated** — has a public empirical analog, the value or distributional shape is taken from cited data, and updating the source data should update the parameter. These flow through `engine/data/empirical_anchors.py`.
- **Stipulated** — has no direct empirical analog at the relevant scale, but is fixed at a value motivated by the conceptual brief, prior literature, or order-of-magnitude reasoning. We sweep these in sensitivity analysis to show conditional behavior.
- **Speculative** — is a representation of a phenomenon that has no historical analog at the 800B-agent scale. These are the load-bearing parameters that make the model interesting; they are *deliberately not* fitted to past macro data because doing so would smuggle in the assumption that the regime change isn't a regime change.

The Sobol sweep (`agentworld sobol`, `agentworld exo sobol`) treats all three kinds the same and reports first-order (S1) and total-order (ST) variance contributions. This tells you which knobs the outputs are sensitive to *within the stipulated bounds*. It does **not** tell you which knobs are most likely to take any particular value in the world.

### α-engine parameter inventory


| Parameter                                                                         | Where                         | Kind                 | Notes / source                                                                                                                                                                                                                                          |
| --------------------------------------------------------------------------------- | ----------------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `PopulationConfig.n_humans_real`, `n_agents_real`                                 | `engine/core/population.py`   | Calibrated           | 8e9 humans (UN World Population Prospects 2024); 8e11 agents per Antikythera 100:1 condition.                                                                                                                                                           |
| `PopulationConfig.wealth_pareto_alpha`                                            | population                    | Calibrated           | α≈1.6 for top-tail wealth, consistent with WID.world 2010-2020 estimates for advanced economies.                                                                                                                                                        |
| `PopulationConfig.human_capability_mean`, `agent_capability_mean`                 | population                    | Stipulated           | No empirical analog for "agent capability" as a scalar; bounds set by reasoning about parity with median-skill human cognitive labor.                                                                                                                   |
| `PopulationConfig.sector_dirichlet_alpha`, sector counts                          | population                    | Calibrated           | 12 macro-sectors map to ISIC Rev. 4 sections (UN Statistics Division). Concentration set so the Dirichlet draw has the same Herfindahl as US BEA value-added shares 2022.                                                                               |
| `PopulationConfig.n_stacks`, `stack_shares`                                       | population                    | Stipulated           | Compute-bloc fragmentation; informed by Bremmer/Foreign Affairs 2024 framings, not measured.                                                                                                                                                            |
| `TopologyConfig.alpha`                                                            | `engine/core/topology.py`     | Speculative          | The whole variable. By design unfittable.                                                                                                                                                                                                               |
| `TopologyConfig.coase_exp`, `base_friction`                                       | topology                      | Stipulated           | No 800B-agent counterpart. Bounds set so terminal EBI in the smooth scenarios reproduces the conceptual brief's verbal claim.                                                                                                                           |
| `TopologyConfig.folding_propensity`, `folding_branching`, `folding_max_depth`     | topology                      | Speculative          | Load-bearing for the Baroque attractor. Permanently un-calibrated. Sobol-swept.                                                                                                                                                                         |
| `TopologyConfig.fold_real_efficiency`, `fold_nominal_multiplier`                  | topology                      | Speculative          | Same.                                                                                                                                                                                                                                                   |
| `TopologyConfig.cross_stack_compat`                                               | topology                      | Stipulated           | Stack compatibility floor; informed by interoperability literature, not measured.                                                                                                                                                                       |
| `TopologyConfig.market_layer_tax`, `individual_layer_alignment_tax`               | topology                      | Stipulated           | Order-of-magnitude consistent with platform takerates (Stripe, Apple, Visa published rates 2024).                                                                                                                                                       |
| `TopologyConfig.noise_model` (Gaussian / t-copula)                                | topology                      | Calibrated structure | Default `t_copula` for new scenarios uses BEA 2022 input-output sectoral correlation matrix downsampled to the 12 macro-sectors; `df=4` matches published heavy-tail estimates of equity-return distributions (Cont 2001 stylized facts).               |
| `TopologyConfig.folding_model` (geometric / hawkes)                               | topology                      | Calibrated structure | Default `hawkes` for new scenarios uses self-excitation branching ratio from financial-cascade literature (Bacry/Muzy 2015 for high-frequency markets, n_eff ≈ 0.55-0.75). Mean-equivalent to `geometric` at default parameters; variance is realistic. |
| `PopulationConfig.network_model` (well_mixed / scale_free / sbm)                  | population                    | Calibrated structure | Scale-free uses degree exponent γ ≈ 2.3 from Atalay et al. 2011 (US production network). SBM uses sector-block structure with intra/inter-sector ratios from the same source.                                                                           |
| `DemandConfig.enabled`                                                            | `engine/core/topology.py`     | Stipulated           | Top-level flag. Default `False` preserves backward-compatible behavior; existing scenarios stay un-migrated until each is hand-anchored.                                                                                                                |
| `DemandConfig.a2a_floor`                                                          | topology / demand             | Speculative          | Order-of-magnitude estimate of B2B intermediate-goods share that flows to humans. Sobol-swept in the alpha-engine sweep.                                                                                                                                |
| `TopologyConfig.base_variance_absorption`                                         | topology / productive folding | Speculative          | Per-layer fraction of fold nominal that is welfare-creating at maximum capability. Default 0.0 keeps existing scenarios bit-for-bit identical; new scenarios opt in at 0.40-0.55. Sobol-swept.                                                          |
| `TopologyConfig.productive_decay`                                                 | topology / productive folding | Speculative          | Per-layer decay of welfare creation. With default 0.65, productive folding contributes ~40% at depth 1 and ~11% at depth 4; deep layers are parasitic. Sobol-swept.                                                                                     |
| `TopologyConfig.cap_midpoint`                                                     | topology / productive folding | Stipulated           | Capability above which folding becomes productive. 0.50 maps to "above-median capability" as the productive threshold.                                                                                                                                  |
| `TopologyConfig.cap_slope`                                                        | topology / productive folding | Speculative          | Sharpness of the capability → productivity sigmoid. Sobol-swept.                                                                                                                                                                                        |
| `TopologyConfig.max_productive_real_share`                                        | topology / productive folding | Speculative          | Upper bound on productive folding's real-welfare contribution as a share of underlying real surplus. Prevents free welfare from nominal recursion; Sobol-swept.                                                                                         |
| `LawConfig.enabled`                                                               | topology / dynamic law        | Stipulated           | Top-level flag. Default `False` preserves baseline scenario behavior; §3 law scenarios opt in explicitly.                                                                                                                                               |
| `LawConfig.law_strength_initial`, `law_capture_initial`                           | topology / dynamic law        | Speculative          | Initial legal-substrate quality and capture. Default off, used only when `LawConfig.enabled = True`.                                                                                                                                                    |
| `LawConfig.upkeep_investment`, `natural_decay`, `law_decay_recovery`              | topology / dynamic law        | Speculative          | Legal infrastructure maintenance and decay rates. Default off; when enabled, upkeep is charged against real welfare each step.                                                                                                                          |
| `LawConfig.beta_capture_growth`, `gamma_civic_pushback`, `civic_pushback_default` | topology / dynamic law        | Speculative          | Wealth-concentration capture dynamics and offsetting civic pressure. `gamma_civic_pushback` is derived by default so civic pushback neutralizes a 50% top-wealth share under default beta.                                                              |
| `LawConfig.concentration_penalty_gini_anchor`, `local_trust_surplus_floor`        | topology / dynamic law        | Speculative          | Shape parameters for captured-law surplus penalties and same-stack local trust when formal law is weak. Default off.                                                                                                                                    |


### exo-engine parameter inventory


| Parameter                                                                                              | Where                  | Kind                 | Notes / source                                                                                                                                                                        |
| ------------------------------------------------------------------------------------------------------ | ---------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `StackConfig.n_layers`, `referent_layer`                                                               | `engine/exo/config.py` | Stipulated           | Conceptual depth choice. Lift is bounded only for tractability.                                                                                                                       |
| `StackConfig.base_lift_propensity`, `lift_decay_with_depth`, `fractal_branching`, `nominal_multiplier` | stack                  | Speculative          | These are the lift operator's load-bearing parameters. Permanently un-calibrated.                                                                                                     |
| `StackConfig.real_leakage_per_layer`, `max_lift_share_per_step`                                        | stack                  | Stipulated           | Numerical regularization.                                                                                                                                                             |
| `DragConfig.target_intensity`, `welfare_cost_per_token`, `tokens_to_lift_propensity`                   | drag                   | Speculative          | Drag-as-mode-of-production is the operator under test.                                                                                                                                |
| `DragConfig.intensity_inertia`, `saturation_floor`, `saturation_ceiling`                               | drag                   | Stipulated           | Numerical regularization + bounds.                                                                                                                                                    |
| `DragConfig.coasean_dampener`, `adaptive`_*                                                            | drag                   | Speculative          | Models the "agent-as-palliative" hypothesis; cannot be fitted because the mechanism does not yet exist at scale.                                                                      |
| `DragConfig.noise_model`                                                                               | drag                   | Calibrated structure | Same as α-engine: `t_copula` default uses cross-region correlation derived from World Bank GDP-growth correlation matrix (downsampled).                                               |
| `LastMileConfig.base_physical_capacity`, `real_per_unit_capacity`                                      | last mile              | Stipulated           | Normalized to 1.0 per unit; relative effects only.                                                                                                                                    |
| `LastMileConfig.gore_layer_violence`                                                                   | last mile              | Speculative          | Models war/climate/extraction-violence loss. Bounds informed by ACLED conflict-intensity ranges but not point-fitted.                                                                 |
| `DifferentialConfig.suppression_strength`, `suppression_cost_exp`, `suppression_welfare_cost`          | differential           | Speculative          | The combine-state mechanism. Permanently un-calibrated.                                                                                                                               |
| `DifferentialConfig.base_market_creation_rate`, `variance_to_market_rate`                              | differential           | Stipulated           | Order of magnitude only.                                                                                                                                                              |
| `RegionConfig.n_regions`, `region_size_dirichlet`, `cross_region_compat`                               | region                 | Calibrated           | Region size distribution matches Penn World Table real-GDP-share Dirichlet fit; cross-region compatibility informed by World Trade Organization tariff/non-tariff measure literature. |
| `ImperialConfig.`*                                                                                     | imperial               | Stipulated           | Tract topology is inspired by Bratton's *Stack* (2016) and historical Trillo/Brenner argumentation, not measured. The artifact's most explicitly speculative geography.               |


---

## Calibrated noise structure (what the t-copula and Hawkes do)

Two pieces of noise machinery were upgraded specifically because their defaults were *misleadingly precise*:

1. **Per-pair / per-region shocks.** The original Gaussian shocks (`engine/core/transactions.py`, `engine/exo/drag.py`) understated tail risk and assumed independence across sectors / regions. Real economies have heavy tails (Cont 2001; Mandelbrot 1963 long before; Gabaix 2009 for the macro version) and substantial cross-sector / cross-region co-movement (BEA input-output; World Bank macro-financial correlations). The t-copula upgrade preserves the variance of the original shocks at default scale, but injects realistic kurtosis (`df=4`) and the sectoral / regional correlation structure measured in public data.
2. **Folding cascades.** The original geometric folding (`engine/core/folding.py`) was a closed-form expectation. Cascades in nature — financial contagion, supply-chain ripples, viral content diffusion — are *self-exciting*: each event raises the conditional intensity of more events for some kernel-defined window. We model this with a marked Hawkes process whose branching ratio matches the closed-form expectation under the same `folding_propensity`, so existing scenario classifications stay roughly stable on average, but tail outcomes (a step that triggers a 4× EBI spike when the deterministic version would have given 1×) become possible. The variance is now realistic; the mean is preserved.

Neither upgrade fits the *macro outputs* of the engines to historical data. They calibrate the *micro structure of randomness* to public empirical analogs of the mechanisms we're modeling. That is a defensible calibration; fitting EBI(2032) to the 1980-2024 financialization curve would not be.

---

## What a Sobol index is and isn't

The dashboard reports two Sobol indices per (parameter, output) pair:

- **First-order S1**: fraction of output variance attributable to that one parameter, marginalizing over the others.
- **Total-order ST**: fraction of output variance attributable to that parameter *including its interactions* with the others.

ST ≈ S1 means the parameter acts independently. ST >> S1 means most of its influence comes through interactions. Parameters where both are near zero are cosmetic *within the stipulated bounds*.

What the index is **not**:

- It is not a probability that the parameter is the "real" cause.
- It is not robust outside the bounds we sweep over (we report the bounds with every Sobol output).
- It is not stable when the engine itself changes; reseed and rerun after any topology change.

---

## Why we don't report unconditional probabilities

The ensembles in `outputs/ensembles/` give per-scenario per-step **5/95 percentile bands** across N seeds (default 64). These are bands *over noise realizations within a stipulated parameterization*, not posteriors over the world. Saying "P(EBI > 50 by step 60) = 0.42" would conflate the two and would be exactly the false-precision move this document exists to prevent.

A scenario that lands at EBI = 47.3 with band [22, 81] is telling you: "given these parameters and this stochastic structure, the artifact's behavior is consistent with EBI in roughly the 20-80 range." It is **not** telling you EBI in 2032 is 50% likely to be above 47.3.

---

## Failure modes worth naming

- **Scale invariance assumption.** We treat 80K prototypes as a representative sample of 8e11 entities via importance weights. If the underlying dynamics are *non-linear in population density* (network percolation, herd-immunity-like thresholds), this is wrong. Mitigation: scale-up runs (`Scale.MEDIUM` and above) check that aggregate behavior is stable; departures flag where this assumption breaks.
- **Step semantics ambiguity.** A "step" has no fixed real-world duration. When comparing across scenarios with different `n_steps`, compare *terminal* metrics or normalize by step count.
- **Fold/lift conflation.** The α-engine's "folding" and the exo-engine's "lift" model overlapping but distinct phenomena. Cross-engine numerical comparison is unsafe; cross-engine *qualitative* comparison is the artifact's main value.
- **Calibration drift.** Empirical anchors in `engine/data/empirical_anchors.py` carry a "vintage" year. Re-anchor when public sources update; re-run the dashboard to see if any scenario classifications flip.
- **Ensemble seed dependence.** Bands are computed across the seed set we run. With N=64 the bands themselves have non-trivial uncertainty; we report bootstrap-of-bootstrap when needed.

---

## What the artifact can now falsify

Until 2026-05, the engines produced no number that could in principle be
*wrong* — every claim was conditional on a delta-distribution at the
scenario default, which is unfalsifiable. Three artifacts shipped under
the validation lift now give the engines first-class falsifiable claims:

### 1. Stylized historical anchor (A1)

The α-engine's `governance_overhead_fraction` was compared against the
US FIRE supersector's share of GDP, 1980-2024 (45 annual values
aggregated from BEA NIPA tables) under a hand-picked α-schedule that
rises linearly from 0.40 to 0.70. The engine reports:

```
RMSE = 0.0634,  MAE = 0.0612,  bias = -0.0612
```

The engine systematically *under-attributes* intermediation by ~6
percentage points — partly because the FIRE share includes imputed
rents on owner-occupied housing and treats activities the engine
classifies as productive trade as overhead. The largest single-year
error is **2009**, the GFC trough, where empirical FIRE rises sharply
while the engine's overhead tracks the smooth schedule.

This is not a fitted model. The deliverable is the *documented* RMSE:
every future engine claim now has one calibrated number it has to live
next to. See [`historical_anchor.md`](historical_anchor.md) for sourcing
and reproduction. Artifact: `outputs/validation/historical_anchor.{json,png}`.

### 2. Prior-over-parameters sweep (A2)

Eleven of the engine's load-bearing speculative knobs (seven α-engine,
four exo) now carry declared priors in
[`engine/validation/priors.py`](../../engine/validation/priors.py). A
2000-sample Sobol-coverage sweep over the α-engine subset produces an
outcome distribution under stated parameter ignorance:

| Basin | P (under wide prior, n=2000) |
| --- | --- |
| Smoothworld (terminal EBI ≤ 1.5) | **1.85%** |
| Mixed (1.5 < EBI < 5) | **66.05%** |
| Baroqueworld (EBI ≥ 5) | **32.10%** |
| diverged | 0.00% |

Terminal EBI quantiles: `p05=1.58, p50=3.18, p95=22.34`.

The Coasean basin survives the wide prior — at ~2% it is not vanishing
— but it is at least an order of magnitude smaller than the Baroque
basin under the bounds the brief argues are plausible. Future "the
engine produces X" claims must condition on either the modal mixed
basin or a named tighter region. See [`priors.md`](priors.md) for the
inventory. Artifact: `outputs/validation/posterior_sweep.{parquet,summary.json,png}`.

### 3. Adversarial scenario (A3)

A simulated-annealing search over eight speculative folding knobs asks:
*does there exist a region where terminal EBI > 10 AND terminal real-
per-capita welfare exceeds `coasean_paradise`'s?* At seed=0 / n_evals=200,
the search lands a counter-example in ~10 seconds:

```
found_counter_example: TRUE
best_ebi:              ~147,118
best_welfare:          ~0.277
paradise_welfare:      ~0.265 (same-scale baseline)
margin:                ~4%
```

The brief's strong claim — *high intermediation does not coexist with
high welfare* — is therefore **falsified**. The weaker, productive-folding-
aware claim survives: high alpha alone harms welfare; high alpha *with*
productive folding (`base_variance_absorption > 0` and capable
intermediaries) can produce welfare slightly above paradise, at the
cost of an EBI that is unrecognizable as a comparison to anything in
the historical anchor's range. The pinned scenario
`baroque_with_high_welfare` reproduces the counter-example.

Half the search knobs sat at upper bounds in the canonical run; a
contracted-bound rerun is a follow-up worth publishing. See
[`docs/scenarios/adversarial.md`](../scenarios/adversarial.md) for
methods and bound-saturation flags. Artifact:
`outputs/validation/adversarial_search.json`.

### Together

These three artifacts move the engines from "engineered" to "engineered
+ minimally validated." They do not turn the engines into forecasters.
What they do is establish that:

- **One quantity is documented to ±6pp against US 1980-2024 data** (A1).
- **The Coasean basin is small but real under wide priors** (A2).
- **The strong "Baroque kills welfare" claim is falsified within the
  stipulated bounds** (A3); the productive-folding-conditional version
  is the load-bearing claim going forward.

Future engine work that perturbs any of these three numbers is required
to say so, by name, and explain whether the change is intentional. The
pin tests in `engine/tests/test_validation_*.py` exist to catch silent
drift.

---

## TL;DR for a reader

The α-engine and the exo-engine are both stochastic dynamical systems with noise structure calibrated to public empirical data and load-bearing dynamics deliberately left speculative. They produce *conditional* statements about parameter sensitivity and basin structure, not forecasts. The two engines disagree by design and the disagreement is itself a deliverable. The Sobol sweep tells you which knobs matter; the ensemble bands tell you how much noise is in each scenario; the calibrated noise structure makes both more defensible than the previous Gaussian-IID defaults; the validation lift adds three numbers (a 6pp anchor RMSE, a wide-prior basin distribution, and a falsifying counter-example to "Baroque kills welfare"); and nothing in the artifact licenses an unconditional probability statement about the future.
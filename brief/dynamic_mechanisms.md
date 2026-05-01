# Dynamic Mechanisms for the α-Engine

> *"The artifact does not pick a side. The artifact argues that the smooth/striated dimension is the question, and that intuitions about it are largely wrong."* — `fractal_folding.md`

**Status note (2026-04-30):** §3, the dynamic law mechanism, shipped alongside
the demand-side-feedback and productive-folding cleanup. It is currently
flag-gated with `LawConfig.enabled = False` by default; only the law scenarios
opt in. Future work can start from §4 without refactoring the law layer first.

This brief specifies four dynamic mechanisms that, when added to the α-engine, would let the artifact support three claims it does not currently support. It is intended to be readable on its own — anyone picking up the work in 3 months should not need to reconstruct the design conversation that produced it.

It assumes familiarity with `engine/core/world.py`, `engine/core/transactions.py`, `engine/core/folding.py`, and `engine/core/metrics.py`, and with `docs/concepts/epistemic_status.md`. It is a sibling to `docs/plans/demand_and_intermediation.md`, which specifies the two prerequisite mechanisms (demand-side feedback and the productive/parasitic folding split). **Do not start on this brief until that plan has shipped** — most of what follows is illegible against the current static engine.

---

## Why these mechanisms exist

The current α-engine produces a finding the architecture itself bakes in: that EBI and real welfare are largely independent, modulated mainly by `agent_capability_mean`. This is a true output of the simulation but a weak claim about the world, because almost none of the dynamics that *could* couple EBI to welfare in real economies are modeled. The mechanisms in this brief introduce four such couplings.

The three claims they are designed to make testable:

| Claim | Status today | What unlocks it |
| --- | --- | --- |
| (a) Coasean singularity is a basin of attraction comparable in size to the Baroque attractor | Not testable — alpha is exogenous, no basins exist | §6 below (bifurcation experiment) preceded by §3-§5 |
| (b) Coasean singularity is expensive to maintain | Reversed — paradise is the cheap state by construction | §3 (law-as-enabler-with-upkeep) |
| (c) High intermediation does not always corrupt welfare | Partially supported but pre-baked | The plan's productive/parasitic folding split is the load-bearing piece; §4-§5 are stress tests |

Each mechanism is a candidate for the **speculative** category in `docs/concepts/epistemic_status.md`. None should be calibrated against macro outputs; bounds should be motivated by the conceptual brief and order-of-magnitude reasoning, then Sobol-swept.

---

## §3. Law as constraint and enabler

### Motivation

The current law layer (`engine/core/transactions.py`, lines around `law_reject = rng.random(n_pairs) < (0.01 + 0.04 * (1.0 - cross_stack))`) treats law as a *cost on trade*. That is the wrong direction of causation. In real economies, law is the *precondition* for trade between strangers: without contract enforcement, property rights, and standardized weights/measures, the Coasean engine collapses to autarky between trusted neighbors. Law is also captured: whoever accumulates wealth shapes the rules, and the rules they prefer are not neutral.

This mechanism rewrites the law layer so it is both an enabler (its absence kills trade) and a constraint (its presence can be captured to entrench incumbents). It is the single highest-leverage change in this brief.

### Operator

Replace the binary law filter with a multiplicative gate on every transaction's *base surplus*:

```
surplus_realized = surplus_base × law_strength × (1 − law_capture × concentration_penalty(stk_a, stk_b, gini))
```

where:

- `law_strength ∈ [0, 1]` is a state variable representing the quality of contract enforcement / property rights / standards. At `law_strength = 0`, no transaction between strangers clears (transactions inside a single trust-network — defined by stack identity and graph adjacency — still clear at a reduced rate). At `law_strength = 1`, the legal substrate is fully functional and trade between strangers is unencumbered.
- `law_capture ∈ [0, 1]` is the fraction of legal rule-making controlled by top-quantile wealth holders. At `law_capture = 0`, rules are neutral. At `law_capture = 1`, rules systematically protect incumbents.
- `concentration_penalty(stk_a, stk_b, gini)` is `(1 − cross_stack[stk_a, stk_b]) + 0.5 × max(0, gini − 0.4)`. It is the fraction of the law's protective force directed at protecting cross-stack incumbents and high-wealth holders against newcomers. Calibrate the constants so a fully-captured high-Gini cross-stack transaction loses ~60-80% of its surplus.

`law_strength` is updated each step by:

```
Δlaw_strength = +upkeep_investment × law_decay_recovery − natural_decay
```

`upkeep_investment` is a fraction of cumulative real welfare diverted away from productive use into legal-infrastructure maintenance. It is a *control variable* in the sense that scenarios can stipulate it (representing public-goods provision policy) or, for endogenous-policy scenarios, derive it from a feedback rule on observed governance overhead. Default `natural_decay = 0.005/step`; default `law_decay_recovery = 1.0` (one unit of upkeep recovers one unit of strength per step).

`law_capture` is updated each step by:

```
Δlaw_capture = +β × top_quantile_wealth_share − γ × civic_pushback
```

`top_quantile_wealth_share` is the share of wealth held by the top 1% of weighted prototypes (already computable from `pop.wealth, pop.weight`). `civic_pushback` is a control variable representing anti-capture activity (litigation, regulation, electoral pressure). Default `β = 0.02/step`, default `γ` such that `civic_pushback = 0.3` exactly offsets `β × 0.5` (i.e., a 50%-share generates capture at the rate civic activity at the default level neutralizes).

### Why this earns claim (b)

The Coasean singularity now requires *both* high `law_strength` *and* low `law_capture`. Both are unstable. Maintaining `law_strength` continuously diverts real surplus into upkeep — set `upkeep_investment ≈ 0.10` to reproduce mid-twentieth-century estimates of public-goods spending as a share of GDP. Maintaining low `law_capture` requires `civic_pushback` to scale with wealth concentration, which itself fluctuates. Smoothworld becomes a continuously contested political achievement, exactly as the original Krier framing implies but the model currently denies.

### Parameters and epistemic status

| Parameter | Default | Status | Source / motivation |
| --- | --- | --- | --- |
| `LawConfig.law_strength_initial` | 0.85 | Speculative | Bounds chosen so default scenarios reproduce current rejection rates. |
| `LawConfig.upkeep_investment` | 0.10 | Stipulated | OECD general-government-spending share, downscaled to "law-relevant" subset. |
| `LawConfig.natural_decay` | 0.005/step | Speculative | Order-of-magnitude only. |
| `LawConfig.beta_capture_growth` | 0.02/step | Speculative | Bounds set so a 50% top-1% share saturates capture in ~25 steps. |
| `LawConfig.civic_pushback_default` | 0.30 | Stipulated | Calibrated to neutralize default `beta_capture_growth`. |
| `LawConfig.concentration_penalty_gini_anchor` | 0.4 | Stipulated | World Bank "moderate inequality" boundary. |

### Interaction with existing engine

- The Matryoshka filter sequence (`law_reject` → `market_reject` → `align_reject` → `cost_reject`) is preserved. The new `law_strength × (1 − law_capture × ...)` factor multiplies `base_surplus` *before* the cost comparison. Surplus that fails to exceed cost is still counted as `rejected_cost`, but the *reason* surplus is low (weak law, captured law) is now explicit in the model state.
- `governance_overhead_fraction` should be augmented to also report the welfare loss attributable to `(1 − law_strength)` and `law_capture × concentration_penalty`. Without this, the diagnostic confuses "law works and rejects you" with "law doesn't work and surplus is low".
- New scenarios: `legal_collapse` (`law_strength` decays to 0.2 over 60 steps, no upkeep), `regulatory_capture` (high wealth concentration + zero civic pushback), `civic_renaissance` (high upkeep + high civic pushback + concentrated initial wealth).

### Failure modes

- The model can become trivially sensitive to `LawConfig.beta_capture_growth`. Sobol-sweep before reporting. If ST(beta) > 0.6 on EBI or per-capita welfare, the mechanism is too brittle and the constants need to be widened in literature-justified ranges, not narrowed.
- "Civic pushback" is not currently endogenous; it is an exogenous control. A future extension makes it a function of perceived inequality and the H2H interaction share. Out of scope here.

---

## §4. Crowding-out and principal-agent decay

These two mechanisms are paired because they share state (a per-prototype `mode` field) and cannot be tested independently — together they make the high-capability tail of the population *migrate* under high-EBI conditions, which is the load-bearing dynamic for claim (a).

### §4a. Crowding-out

#### Motivation

In the current engine, every prototype participates in the Coasean engine every step. Real economies do not work this way: capable participants migrate toward whichever activity offers higher per-step returns. If folding (intermediation) pays more than producing, the productive layer hollows out and `slop_market` becomes the *consequence* of high-EBI rather than a stipulated input.

#### Operator

Add to `Population`:

```python
mode: np.ndarray  # int8, 0 = productive, 1 = intermediating
```

Initialize `mode = 0` for everyone. Each step, after `coasean_step` and `fold_surplus` complete:

1. Compute `productive_return_per_prototype` and `intermediating_return_per_prototype` from the step's outputs (the per-prototype scatter is already produced by `np.bincount` for transactions; folding needs an analogous attribution layer that distributes `nominal_added` proportionally to the capability of agents in `mode = 1`).
2. For each prototype, compute `pressure_to_switch = clip(0, 1, sigmoid(k × (other_mode_return − own_mode_return)))`.
3. Switch mode with probability `migration_rate × pressure_to_switch × capability` — high-capability prototypes migrate faster.

#### Effect on `coasean_step`

Only prototypes with `mode = 0` are sampled as transaction partners. The effective productive workforce becomes `n_productive = (mode == 0).sum()`, weighted by `weight × capability`. As intermediating mode grows, productive surplus falls — endogenously this time, not by flat tax.

#### Effect on `fold_surplus`

Folding intensity depends on the intermediating workforce. Replace the constant in `folding_propensity` with a workforce-scaled version:

```
folding_propensity_effective = folding_propensity × (n_intermediating × cap_bar_intermediating) / baseline
```

where `baseline` is the value at initial conditions. Folding becomes more aggressive when more capable people are doing it.

#### What it enables

- The Baroque attractor becomes self-amplifying: high EBI draws capable agents into intermediation, weakening production, lowering real welfare per step, raising EBI further.
- The Coasean attractor becomes self-amplifying in the opposite direction: low EBI draws capable agents into production, strengthening real returns, lowering EBI further.
- Bistability in alpha as a function of past EBI becomes possible without any explicit alpha schedule. This is the specific dynamic that makes claim (a) testable in §6.

#### Parameters

| Parameter | Default | Status | Notes |
| --- | --- | --- | --- |
| `migration_rate` | 0.05/step | Speculative | A capable agent has a ~5%/step chance of switching when other mode pays double. |
| `sigmoid_k` | 2.0 | Speculative | Sharpness of the switching response. |
| `mode_init_share_intermediating` | 0.10 | Stipulated | Order-of-magnitude consistent with finance + professional-services share of advanced-economy employment. |

### §4b. Principal-agent decay

#### Motivation

Each fold layer represents a delegation. When a human delegates to an agent who delegates to another agent, the original principal's preferences are progressively distorted. The current model treats each fold layer as a flat tax on real welfare; this hides the qualitative degradation of *what gets produced for whom*.

#### Operator

Augment `FoldingResult` to carry per-depth alignment information. At depth `d`, each layer applies an alignment-drift multiplier to the real welfare it generates:

```
real_welfare_attributed_to_depth_d = real_at_depth_d × (1 − decay)^d
```

where `decay = base_decay × alignment_heterogeneity`. `alignment_heterogeneity` is the variance of `pop.alignment` weighted by `pop.weight`. With a homogeneous population (low variance), delegation is faithful; with a heterogeneous population, deep layers progressively lose contact with what the original human wanted.

The "lost" real welfare is *not* added back to nominal — it is a real loss. It is reported separately as `real_misallocated`:

```python
@dataclass
class FoldingResult:
    nominal_added: float
    real_subtracted: float
    real_misallocated: float       # NEW
    n_sub_markets_added: float
    new_max_depth: int
```

`world.step` then reports `real_step = max(0.0, tx.real_surplus − fold.real_subtracted − fold.real_misallocated)`.

#### What it enables

- Deep folding does not just have overhead; it produces the wrong things. This is the first mechanism in the model where folding can do *qualitative* damage rather than only quantitative.
- The diagnostic `welfare_misallocation_fraction = cumulative_real_misallocated / cumulative_real_authentic` gives a clean separator between the two ways high-EBI scenarios can be benign or malign:
  - High EBI + low misallocation = real welfare grows; the fractal is decorative (this is the current `baroque_cathedral` finding).
  - High EBI + high misallocation = real welfare grows by national accounts but represents production for principals nobody chose to delegate to. This is the Bratton-skeptic version of the Baroque attractor.

#### Parameters

| Parameter | Default | Status | Notes |
| --- | --- | --- | --- |
| `base_decay` | 0.05 | Speculative | A 5% per-layer authenticity loss in a maximally heterogeneous population. |
| `alignment_heterogeneity_floor` | 0.05 | Stipulated | Even a homogeneous population has some delegation drift. |

---

## §5. Debt, leverage, and credit events

### Motivation

Folding currently creates only flow, never claims. In real economies, every layer of intermediation creates derivative claims that:

- *Enable* productive investment by transferring risk from those who cannot bear it to those who can.
- *Can default catastrophically* when the underlying assumption (that the counterparty bearing the risk is solvent) fails.
- *Grow unboundedly relative to underlying real activity* when leverage is unconstrained.

This is the mechanism that distinguishes baroque-stable from baroque-fragile and is the natural successor to the productive/parasitic folding split (`docs/plans/demand_and_intermediation.md`, mechanism 2): it makes the *failure mode* of even-productive folding a first-class part of the model.

### Operator

Track a global state variable `notional_outstanding`. Each step, after `fold_surplus`:

```
notional_outstanding += nominal_added × leverage_factor
```

`leverage_factor` is a topology parameter (default 4.0 — each unit of nominal value spawned creates 4 units of notional liability, consistent with derivative-to-underlying ratios in advanced economies).

Define `leverage_ratio = notional_outstanding / max(real_welfare_cumulative, ε)`. Each step, sample a credit event with probability:

```
P(credit_event) = sigmoid((leverage_ratio − leverage_threshold) / leverage_scale) × hawkes_excitation
```

Default `leverage_threshold = 8.0`, `leverage_scale = 2.0`. `hawkes_excitation` is shared with the Hawkes folding kernel — credit events cluster under the same self-excitation that drives cascade folding (this couples §5 to the existing `folding_model = "hawkes"` machinery rather than adding independent randomness).

When a credit event fires:

1. Erase `credit_event_severity × notional_outstanding` of nominal cumulative GDP. Default `severity = 0.4`.
2. Reduce real welfare cumulative by `severity × leverage_ratio_above_threshold × real_per_step_avg`. Real defaults have real consequences — failed counterparties stop producing, real assets are mispriced, contracts unwind.
3. Apply per-prototype wealth losses proportional to `mode = 1` exposure (intermediating prototypes hold the leveraged claims and bear the brunt of the unwinding).
4. Reset `notional_outstanding` to a fraction (default 0.3) of its pre-event value, representing claims that didn't unwind.

### What it enables

- Tail risk that distinguishes baroque-stable from baroque-fragile. `baroque_cathedral` becomes two scenarios: one where leverage stays below threshold and the cathedral holds, one where it breaches and the cathedral collapses. Run as ensemble — same parameters, different seeds, different terminal regime.
- A clean experimental knob (`leverage_factor`) for the policy question "should derivatives be leverage-constrained?" Sweep `leverage_factor ∈ [1, 8]` at fixed alpha and observe the hazard curve for credit events.
- Phase coupling between `productive_fold` (from the prerequisite plan) and credit events: productive folding *with* leverage is welfare-positive in expectation but tail-risk-bearing. This is where the model can speak to the "are derivatives productive?" question with more than a hand-wave.

### Parameters and epistemic status

| Parameter | Default | Status | Notes |
| --- | --- | --- | --- |
| `LeverageConfig.leverage_factor` | 4.0 | Stipulated | BIS estimates of derivative-notional-to-GDP. |
| `LeverageConfig.leverage_threshold` | 8.0 | Stipulated | Order-of-magnitude consistent with pre-2008 systemic-leverage estimates. |
| `LeverageConfig.leverage_scale` | 2.0 | Speculative | Sharpness of the default-rate-vs-leverage curve. |
| `LeverageConfig.severity` | 0.4 | Speculative | 40% writedown per crisis, mid-range of 20th-century banking-crisis losses. |
| `LeverageConfig.recovery_fraction` | 0.3 | Speculative | Fraction of notional that survives the unwinding. |

### Interaction with existing engine

- Couples specifically to the Hawkes folding model. With `folding_model = "geometric"`, credit-event probability uses only the deterministic `sigmoid(...)` term and tail clustering disappears. Document this as a known limitation — heavy-tail credit dynamics require Hawkes.
- The metrics module gains:
  - `notional_outstanding`
  - `leverage_ratio`
  - `n_credit_events`
  - `cumulative_credit_event_loss`
- New scenarios: `lehman_morning` (high `leverage_factor`, mid alpha, runs until the first credit event), `glass_steagall` (low `leverage_factor`, high `law_strength` from §3, tests whether legal constraint substitutes for natural deleveraging), `unconstrained_baroque` (very high `leverage_factor`, alpha=0.92, no civic pushback).

---

## §6. Bifurcation experiment

This is not a mechanism. It is the experiment that tests claim (a) once §3-§5 are in place.

### Setup

The model now has at least three sources of bistability:

- §3: `law_strength × (1 − law_capture)` is itself bistable when civic pushback is bounded (high capture begets high concentration begets more capture).
- §4a: mode-migration is bistable on returns (high EBI draws capable agents into intermediation, which raises EBI further).
- §5: leverage cycles can flip a stable baroque regime into a productive crash and back.

A single sample from the model, with one set of initial conditions and one seed, lands in *one* terminal regime. The question for claim (a) is: across a representative sample of initial conditions and seeds, do roughly half land in smooth and half in baroque?

### Method

1. Define an initial-condition grid on `{alpha_initial, capability_mean_initial, gini_initial, law_strength_initial, leverage_factor}`. Use Latin hypercube sampling, 256 points, parameter ranges from the relevant Sobol bounds.
2. For each grid point, run an ensemble of 32 seeds.
3. Classify each terminal state as *smooth* (terminal `EBI < 5`), *baroque* (`5 ≤ EBI < 100`), or *singular* (`EBI ≥ 100`). Use additional thresholds on `welfare_misallocation_fraction` from §4b to distinguish productive-baroque from extractive-baroque.
4. Compute the basin-of-attraction map: for each region of initial-condition space, what fraction of seeds land in each classification.
5. Report the basin-volume ratio. Claim (a) is supported if the smooth basin has volume within an order of magnitude of the baroque basin under the default Sobol bounds.

### What "supported" means

The claim is *conditional* on the bounds we sweep. If the smooth basin shrinks rapidly when `civic_pushback` defaults are reduced, that is itself a finding — the smooth attractor exists but only inside a specific political-economy parameterization. This is a stronger finding than "smooth and baroque are equally likely" because it identifies the political-economy parameters that determine which attractor the world ends up in.

### Reporting

Add to the dashboard:

- A 2D slice of the basin map (alpha_initial × law_strength_initial, marginalized over the other dimensions).
- A bar chart of basin-volume ratios under three policy regimes: default, "low upkeep + low pushback" (laissez-faire), "high upkeep + high pushback" (interventionist).
- The Sobol indices on the basin-volume ratio with respect to the LHS dimensions.

This is the experimental output that the brief is ultimately for.

---

## Order of operations

The mechanisms are not commutative. Recommended sequence:

1. **§3 (law) first**, including the new state variables and metrics. This is the most contained change and gives every other mechanism a richer substrate.
2. **§4a (crowding-out)** next. It depends on §3 because the law-strength gate determines whether intermediating-mode returns are sustainable.
3. **§4b (P-A decay)** alongside or immediately after §4a. They share the `mode` field and the per-fold-depth attribution machinery.
4. **§5 (leverage and credit events)** last among the mechanisms. It couples to the Hawkes folding kernel (which already exists) and to the productive/parasitic split (which is in the plan doc) — both must be in place first.
5. **§6 (bifurcation experiment)** is the final integration step. Run only after the four mechanisms are in place and have ensemble baselines that confirm they don't break existing scenario classifications.

Each step gets its own ensemble baseline. After every mechanism lands, re-run the existing 17 scenarios; if any of them flip basin classification, document why before adding the next mechanism.

---

## What this brief deliberately does not do

- It does not specify the *implementation* of demand-side feedback or productive/parasitic folding. Those are in `docs/plans/demand_and_intermediation.md` and must ship first.
- It does not propose any calibration against macro outputs. Every parameter introduced here is speculative or stipulated, in the senses defined by `docs/concepts/epistemic_status.md`. Do not fit `LeverageConfig.leverage_threshold` to historical default rates. Sobol-sweep instead.
- It does not unify the α-engine with the exo-engine. The two engines stay distinct.

---

## References

- Bratton, B. (2026). *Agentworld* research brief, Antikythera (forthcoming).
- Cont, R. (2001). Empirical properties of asset returns. *Quantitative Finance* 1(2).
- Bacry, E. & Muzy, J.-F. (2015). Hawkes model for price and trades high-frequency dynamics. *Quantitative Finance* 15.
- Atalay, E. et al. (2011). Network structure of production. *PNAS* 108(13).
- Krier, D. (2026). Smoothworld brief, Antikythera (forthcoming).
- World Inequality Database (WID.world), 2010-2020 capital-share series.
- Bank for International Settlements, OTC derivative-notional outstanding, semi-annual surveys.
- See also `docs/concepts/epistemic_status.md`, `docs/concepts/fractal_folding.md`, `docs/concepts/smooth_striated.md`.

# Demand-Side Feedback and the Productive/Parasitic Folding Split

> *"Real economies have consumers; agentic accounting can have only ledgers."*

This concept doc describes two mechanisms that the alpha-engine acquired in the
demand-and-intermediation pass. Both are conditional refinements to the
smooth/striated dial: behind a default-off flag and a default-zero parameter,
the engine reproduces its previous outputs bit-for-bit. The two mechanisms only
matter where they are explicitly opted into — and that is the point. They make
two separate claims operationally legible, where the original engine collapsed
both claims into the single "fold = nominal multiplication" idea.

The plan that produced these mechanisms lives in `docs/plans/_archive/` (or
`docs/plans/` if it has not yet been archived); this doc is the *concept*
companion to that plan and explains what the dynamics mean.

---

## 1. Demand-side feedback

### The claim

A transaction creates real welfare to the extent its surplus reaches a human
consumer (or a human-controlled agent acting on a human's behalf). When two
fully-autonomous agents close a deal that neither ever traces back to a human
endpoint, the *nominal* economy registers the trade — the prototypes get paid,
GDP-style accounting clicks up — but no person's life is materially better.
Some such activity does flow back to humans indirectly via downstream
production (intermediate goods, B2B inputs, infrastructure), but the share is
bounded.

The original alpha-engine treated every executed pair as 100% real welfare. At
populations where humans are an order of magnitude smaller than agents and
agents transact among themselves at internet scale, that assumption produces a
visible artifact: scenarios with high agent autonomy report high real welfare
that no human ever consumes.

### The mechanism

`engine/core/transactions.py:demand_factor` computes a per-pair fraction of
surplus that ultimately reaches a human consumer:

```python
eff_h_a = h_a + (1 - h_a) * (1 - auto_a)   # effective human-coupling of side a
eff_h_b = h_b + (1 - h_b) * (1 - auto_b)
demand_factor = a2a_floor + (1 - a2a_floor) * max(eff_h_a, eff_h_b)
```

Humans count fully. Agents count to the extent they are *not* autonomous —
i.e. the extent to which they are acting on a principal's behalf. A pair where
both endpoints are fully autonomous agents has `demand_factor = a2a_floor`,
which captures the residual share of A2A activity that flows back to humans
indirectly via supply chains.

The aggregate output is `real_welfare_authentic_cumulative`, reported alongside
the existing `real_welfare_cumulative`. The two coincide whenever every pair
has at least one human-coupled endpoint; they diverge when A2A activity
dominates. A new diagnostic, `exo_baroque_authentic = nominal_cumulative /
real_welfare_authentic_cumulative`, makes the gap visible.

`wealth_delta` continues to use the un-modulated surplus. Prototypes get *paid*
for every executed transaction — the nominal economy still flows. What changes
is what the artifact counts as *welfare*.

### What it surfaces

- `synthetic_consumers_v2` is `synthetic_consumers` with `DemandConfig.enabled
  = True`. Authentic per-capita welfare collapses to roughly a quarter of the
  un-modulated value: agents trading with agents account for most of the
  surplus, and that surplus is filtered out of the authentic aggregate.
- `agentic_disconnect` is the abdication scenario: humans delegate everything
  (`human_autonomy_mean = 0.20`) and agents are highly autonomous
  (`agent_autonomy_mean = 0.95`). At mid-alpha, even modest folding produces
  the same authentic-welfare collapse: the human side is structurally absent
  from the consumption loop.

### What it does not say

- It does not claim a fitted estimate of the human-consumed share. `a2a_floor
  = 0.15` is an order-of-magnitude guess at how much A2A activity reaches
  humans through B2B chains; sweep it.
- It does not propagate `eff_h` through the full input-output network. A
  network-aware version would multiply `demand_factor` by the human-reachable
  share of the partners' production graph. That is out of scope for this
  iteration.
- It does not retroactively reinterpret the un-modulated `real_welfare_*`
  series. Those continue to compute the legacy aggregate so existing
  classifications stay anchored.

---

## 2. The productive vs parasitic folding split

### The claim

The folding operator does two different things that the original
implementation conflated:

- **Parasitic folding** is recursive nominal multiplication. Each layer adds
  to GDP-style accounting without producing anything humans consume.
  Friction subtracts from real welfare; nominal volume multiplies.
- **Productive folding** absorbs variance. Insurance, hedging, price
  discovery, capital efficiency are real economic services performed by
  intermediaries: each fold layer trades risk between counterparties who
  value it differently, and that trade creates surplus net of the friction
  cost.

The original alpha-engine modelled only the parasitic side. Aggressive
intermediation always cost real welfare, so any positive welfare claim about
derivatives was structurally invisible.

### The mechanism

The fold operator now produces three quantities per layer instead of two:
nominal multiplication (unchanged), real-welfare loss to friction (unchanged),
and a new welfare-creating contribution gated by intermediating-agent
capability and depth.

```
intermediation_quality_d = cap_intermediating_mean
productive_share_d = sigmoid((cap - cap_midpoint) * cap_slope)
variance_absorbed_factor_d = base_variance_absorption * productive_decay^(d-1)
real_added_d = cur_nominal_d * productive_share_d * variance_absorbed_factor_d
real_added_productive = min(sum(real_added_d), base_real_surplus * max_productive_real_share)
```

Two parameters control the gate. `cap_midpoint` is the capability above which
folding becomes productive; below the midpoint the sigmoid drops to zero.
`cap_slope` controls how sharp the transition is. Above the midpoint, deep
layers absorb less because they're already operating on stabilized risks:
`variance_absorbed_factor` decays geometrically with depth at rate
`productive_decay`. At depth 1 a productive layer adds
`base_variance_absorption` of its nominal contribution back as real; at depth
6 productive folding is essentially exhausted.

`base_variance_absorption = 0.0` is the default. Existing scenarios produce
the original outputs bit-for-bit: with the variance-absorption coefficient at
zero, the productive-share computation contributes exactly zero. New scenarios
opt in. `max_productive_real_share` prevents nominal recursion from creating
free welfare: risk transfer can recover value from underlying real surplus, but
cannot insure more real economy than exists.

### What it surfaces

- `productive_baroque` is the answer to the brief's claim (c) — high
  intermediation does not always corrupt welfare. With `alpha = 0.85`, high
  agent capability, and `base_variance_absorption = 0.45`, the fold cascade
  is welfare-creating at shallow depth, parasitic at deep depth. Terminal
  EBI lands in the [8, 50] band; per-capita welfare stays near the Coasean
  baseline rather than exploding above it. The model now has a third basin
  between Smoothworld and Baroqueworld: a productive baroque attractor.
- `casino_collapse` is the same opt-in with low capability. The sigmoid stays
  below 0.5; the productive contribution is small relative to the
  (still-large) parasitic nominal multiplication. The split's claim is
  capability-conditional: opting in does not buy welfare for free.
- `derivatives_revolution` aggressively exercises the productive parameters
  (`base_variance_absorption = 0.40`, `productive_decay = 0.75`, low
  Matryoshka taxes). It is the limit-test scenario: terminal welfare is
  intentionally above `coasean_paradise` but remains bounded near the high end
  of the 0.06-0.09 band because the productive contribution is capped by a
  share of the underlying real surplus.

### What it does not say

- `variance_absorbed_factor` is not actually computed from per-pair surplus
  variance. It is a function of depth and a constant. A fuller version
  would propagate variance through the cascade. Out of scope.
- `cap_intermediating_mean` is the population-mean *agent* capability. A
  later iteration with explicit mode-1 (intermediation) separation will
  weight by agents currently acting as intermediaries.
- The sigmoid can produce step-function artifacts at the capability
  midpoint when `cap_slope` is large. The 2026-04-30 alpha-engine Sobol
  sweep (`--samples 64`, 1,088 simulations) did not show the concerning
  bimodal mass at zero and the maximum yield: terminal
  `productive_welfare_yield` had median 0.106, 5/95 percentiles
  0.001/0.319, 10.7% of samples at or below 0.01, and 3.2% above 0.35.
  `cap_slope` therefore stays at 4.0 for now.

---

## 3. How the two interact

The mechanisms are independent but they compose. In a productive-baroque
scenario:

1. The Coasean engine produces `real_surplus_added` and the un-modulated
   nominal volume.
2. The folding operator multiplies nominal and adds back bounded real welfare
   from the productive share of the cascade.
3. The demand-side filter weights both contributions by their human-coupled
   share when computing `real_welfare_authentic_cumulative`.

So `productive_baroque` produces high un-modulated real welfare (productive
folding contributes), high authentic real welfare (the population is
human-coupled), and a moderate EBI (nominal multiplication is still
substantial, just less than in the parasitic-only `baroque_cathedral`).

`agentic_disconnect` produces normal un-modulated real welfare (the engine
produces direct surplus), but authentic welfare collapses (most of that
surplus does not reach a human). The demand-side gap is the diagnostic.

---

## 4. Reading the metrics

The dashboard now reports six new quantities per step:

- `real_welfare_authentic_step` — same as `real_welfare_step` when the
  demand flag is off.
- `real_welfare_authentic_cumulative` — same as `real_welfare_cumulative`
  when the demand flag is off; the human-consumed-share aggregate when on.
- `exo_baroque_authentic` — nominal / authentic real, the analogue of EBI
  that filters out A2A surplus.
- `productive_welfare_yield` — productive welfare yield per fold-nominal dollar;
  in [0, 1]. Zero unless `base_variance_absorption > 0`.
- `parasitic_nominal_residual` — `1 - productive_welfare_yield`, interpreted as
  nominal residual rather than a literal partition of nominal flows.
- `real_welfare_from_intermediation_cumulative` — sum across steps of the
  productive contribution. Use it to read off how much of the run's real
  welfare is attributable to productive folding.

The Sobol sweep includes the five new parameters (`a2a_floor`,
`base_variance_absorption`, `productive_decay`, `cap_slope`,
`max_productive_real_share`) and the three new output metrics
(`exo_baroque_authentic`, `real_welfare_authentic_cumulative`,
`productive_welfare_yield`). Read the indices the same way as everything else:
within the stipulated bounds, S1 is the fraction of output variance the
parameter explains alone; ST includes interactions. Parameters where both are
near zero are cosmetic. Bounds chosen for face validity, not calibrated.

---

## 5. Epistemic status

All productive-folding parameters are **speculative** except the stipulated
capability midpoint in the sense of
`docs/concepts/epistemic_status.md`. They have no historical analog at the
800B-agent scale and are deliberately not fitted to past macro data. They are
swept in the Sobol panel; their conditional sensitivity is the deliverable.

| Parameter | Default (back-compat) | Default (opt-in) | Status | Notes |
| --- | --- | --- | --- | --- |
| `DemandConfig.enabled` | `False` | `True` | Stipulated | Flag, not a continuous parameter. |
| `DemandConfig.a2a_floor` | n/a | 0.15 | Speculative | Order-of-magnitude estimate of B2B intermediate-goods share that flows to humans. |
| `TopologyConfig.base_variance_absorption` | 0.0 | 0.40 | Speculative | Per-layer fraction of fold nominal that is welfare-creating at maximum capability. |
| `TopologyConfig.productive_decay` | n/a | 0.65 | Speculative | Per-layer decay of welfare creation; productive folding becomes parasitic at depth ~6. |
| `TopologyConfig.cap_midpoint` | n/a | 0.50 | Stipulated | Capability above which folding becomes productive. |
| `TopologyConfig.cap_slope` | n/a | 4.0 | Speculative | Sharpness of the capability → productivity transition. |
| `TopologyConfig.max_productive_real_share` | n/a | 0.60 | Speculative | Cap on real welfare created by productive folding as a share of underlying real surplus. |

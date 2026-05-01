# Pigouvian Automation Tax

> *"The externality is not pollution — it is production without consumption."*

---

## The problem

At the 100:1 parasociety ratio, >98% of economic interactions are
agent-to-agent. The alpha-engine's demand-side feedback mechanism
(`DemandConfig`) can *measure* the gap between nominal GDP and
human-consumed welfare, but it does not *correct* it. Prototypes still
receive the full surplus from every executed transaction; wealth still
accrues; folding still multiplies nominal volume — regardless of
whether any human benefits.

This is a textbook negative externality. Each A2A transaction imposes a
social cost: it inflates nominal GDP, concentrates wealth in agent
prototypes, and drives folding cascades that further inflate the
exo-baroque index — all without creating authentic welfare. The
Matryoshka taxes (`market_layer_tax`, `individual_layer_alignment_tax`)
are uniform across pair types and do not price this externality.

A Pigouvian tax internalizes the cost by making the A2A automation gap
visible in the surplus split. H2H pairs pay zero; A2A pairs pay a rate
proportional to how far they are from having a human consumer at either
endpoint. The revenue is recycled to humans.

---

## Mechanism

### Per-pair tax

The Pigouvian tax is applied in `engine/core/transactions.py` after the
Matryoshka surplus taxes and before the Nash-bargaining wealth split.
For each executed pair `(a, b)`:

```
demand_factor = a2a_floor + (1 - a2a_floor) * max(eff_h_a, eff_h_b)
automation_gap = 1 - demand_factor
pigouvian_rate = tax_rate * automation_gap
```

The effective tax on a pair is `pigouvian_rate * real_pair_surplus`.
This reduces the surplus flowing into `wealth_delta` (the 50/50 Nash
split) but does not alter the `real_surplus_added` aggregate — the
Pigouvian tax is a redistribution, not a destruction of surplus.

Key properties:

- **H2H pairs**: `demand_factor ≈ 1`, `automation_gap ≈ 0`, tax = 0.
- **H2A pairs**: `demand_factor ∈ [0.7, 0.9]` depending on agent
  autonomy; small tax.
- **A2A pairs (fully autonomous)**: `demand_factor ≈ a2a_floor ≈ 0.15`,
  `automation_gap ≈ 0.85`; near-full rate.

### Revenue recycling

Revenue is collected per step and recycled via one of three channels
configured by `PigouvianConfig.recycling`:

1. **`human_wealth`** — Redistribute to human prototypes weighted by
   `(1 / wealth)^progressivity × weight`. Higher `progressivity`
   targets poorer humans more aggressively. This is a direct transfer
   that compresses the Gini coefficient.

2. **`friction_subsidy`** — Accumulate revenue into a pool that reduces
   transaction costs for human-involving pairs. This is a structural
   intervention: rather than giving humans money, it makes it cheaper
   for them to participate in the economy.

3. **`capability`** — Invest revenue in raising human capability over
   time. This is the "publicly funded agent voucher" — the same
   intervention as `public_defender`, but funded by automation taxes
   rather than stipulated as an initial condition.

---

## Interaction with existing mechanisms

### Demand-side feedback

The Pigouvian tax and the demand-side feedback measurement are
independent but composable. `real_welfare_authentic` continues to use
the un-taxed surplus formula — it measures what *would* reach humans
absent intervention. The Pigouvian tax changes what *does* reach humans
via the wealth channel. Scenarios with both enabled can compare the
"diagnosis" (authentic welfare gap) to the "treatment" (tax-induced
redistribution).

### Productive folding

The `pigouvian_baroque` scenario tests whether taxing A2A surplus
suppresses productive folding (risk transfer, price discovery) or only
parasitic nominal multiplication. The tax operates on the Coasean
surplus *before* folding; folding sees a reduced `base_real_surplus`
only to the extent that the Pigouvian tax reduces the overall surplus
pool. The productive/parasitic split within folding is unaffected — it
is governed by intermediating capability and depth, not by the pair
composition.

### Dynamic law

The Pigouvian tax and the law layer are orthogonal. Law gates
*whether* a transaction is allowed; the Pigouvian tax gates *how much*
of an allowed transaction's surplus flows to the transacting parties
vs. to humans. Both can be enabled simultaneously.

---

## Scenarios

| Scenario | Tax rate | Recycling | Baseline twin | What it tests |
| --- | --- | --- | --- | --- |
| `pigouvian_light` | 0.10 | `human_wealth` | `synthetic_consumers_v2` | Moderate correction; Gini compression; authentic welfare improvement |
| `pigouvian_heavy` | 0.35 | `human_wealth` | `synthetic_consumers_v2` | Over-correction dynamics; welfare overshoot vs Coasean baseline |
| `pigouvian_friction` | 0.15 | `friction_subsidy` | `synthetic_consumers_v2` | Structural re-entry of humans into the consumption loop |
| `pigouvian_baroque` | 0.12 | `human_wealth` | `productive_baroque` | Whether the tax targets parasitic folding without suppressing productive folding |

All four scenarios share seed and population parameters with their
un-taxed twins so that the only difference is the Pigouvian
intervention. Compare terminal metrics side by side.

---

## Reading the metrics

Three new fields on `StepMetrics`:

- **`pigouvian_revenue_step`** — total Pigouvian tax revenue collected
  this step (in units-of-account).
- **`pigouvian_revenue_cumulative`** — running total across all steps.
- **`pigouvian_effective_rate`** — `pigouvian_revenue_step /
  real_welfare_step`. Interpretation: what fraction of this step's
  real welfare was captured by the Pigouvian tax and recycled to
  humans. Zero when the tax is off.

---

## What this does not model

1. **Behavioral response to the tax.** Agents do not strategically
   reduce their A2A activity in response to higher taxation. The
   Pigouvian tax changes the surplus split but not the transaction
   acceptance probability. A fuller model would let agents decline
   low-surplus transactions whose post-tax return falls below a
   threshold.

2. **Endogenous agent population.** If agents could be replicated or
   retired in response to profitability, the Pigouvian tax would
   create a contraction of the agent population at high rates. This
   dynamic — the Pigouvian tax as an anti-scaling brake — is the most
   interesting extension but requires population dynamics not yet in
   the alpha-engine.

3. **Cross-stack tax competition.** In a multi-stack world, one stack
   could set a lower Pigouvian rate to attract A2A activity, creating
   a "race to the bottom" analogous to corporate tax competition. The
   current implementation applies a single rate globally.

4. **Incidence on human principals.** When an agent pays Pigouvian tax
   on a transaction done on behalf of a human principal, the human
   bears the economic incidence (lower wealth accrual). The current
   implementation does not distinguish between "agent acting for self"
   and "agent acting for principal" beyond the `autonomy` parameter.

---

## Epistemic status

All Pigouvian parameters are **speculative** in the sense of
`docs/concepts/epistemic_status.md`. There is no empirical basis for
the tax rate, the recycling channel efficiency, or the progressivity
exponent at the 800B-agent scale. The mechanism is a policy experiment,
not a calibrated forecast.

| Parameter | Default | Status | Notes |
| --- | --- | --- | --- |
| `PigouvianConfig.enabled` | `False` | Stipulated | Flag. |
| `PigouvianConfig.tax_rate` | `0.0` | Speculative | No empirical anchor for optimal automation tax rate. |
| `PigouvianConfig.a2a_floor` | `0.15` | Speculative | Reuses DemandConfig's order-of-magnitude estimate. |
| `PigouvianConfig.recycling` | `"human_wealth"` | Stipulated | Choice of channel, not a continuous parameter. |
| `PigouvianConfig.recycling_progressivity` | `1.0` | Speculative | Exponent on inverse-wealth weighting. |

# Plan — Demand-Side Feedback and the Productive/Parasitic Folding Split

This is an implementation plan, not a brief. It is the prerequisite work for `brief/dynamic_mechanisms.md`. It changes two things in the α-engine:

1. **Demand-side feedback.** Real welfare from a transaction depends on whether the produced thing has a human (or human-controlled agent) consumer. A2A activity creates nominal but not real welfare unless it ultimately reaches human consumption.
2. **Productive vs parasitic folding.** The folding operator is split into two channels — one that creates real welfare proportional to the risk it absorbs (derivatives as productive tool), one that only inflates nominal (rent extraction). The split is governed by intermediating-agent capability and fold depth.

These are the smallest-footprint, highest-leverage changes to the model. Together they earn claim (c) — *high intermediation does not always corrupt welfare* — by making it a *result* of underlying capability and demand structure rather than a stipulation.

## Goals and acceptance criteria

A successful landing satisfies all of:

- **G1.** `coasean_paradise` and `baroque_cathedral` both still run to completion, with terminal EBI within ±20% of their current values when new parameters are at their backward-compatible defaults. (Backward compatibility is non-negotiable. Set defaults so existing scenarios produce existing outputs.)
- **G2.** A new scenario `productive_baroque` exists where `alpha = 0.85`, capability is high, and folding parameters are tuned to maximally productive intermediation. Terminal real per-capita welfare is at least 75% of `coasean_paradise`'s, and EBI is between 8 and 50.
- **G3.** A new scenario `synthetic_consumers_v2` (replacing or augmenting the current `synthetic_consumers`) shows real per-capita welfare *collapsing* as agent autonomy and A2A share rise, holding capability fixed. This is the demand-side-feedback effect made visible.
- **G4.** All 17 existing scenarios run with the new code; their classifications (smooth / striated / etc.) do not change. Document any that do.
- **G5.** Three new metrics are reported in `StepMetrics`: `real_welfare_authentic` (the human-consumed share), `productive_welfare_yield` (fraction of fold nominal that was welfare-creating), and `parasitic_nominal_residual` (the complement). These appear in the dashboard.
- **G6.** Sobol sweep over the new parameters lands in the dashboard with both first-order and total-order indices on terminal EBI and terminal per-capita welfare.

If any of G1-G6 fails, do not proceed to the brief.

---

## Mechanism 1 — Demand-side feedback

### What changes

In `engine/core/transactions.py`, the base surplus formula is:

```
base_surplus = base_match_volume × (0.05 + 0.5 × cap_product × sec_aff + shock)
```

This is replaced with a demand-modulated version:

```
base_surplus = base_match_volume × (
    0.05 + 0.5 × cap_product × sec_aff + shock
) × demand_factor(h_a, h_b, auto_a, auto_b)
```

`demand_factor` is the share of the transaction's surplus that ultimately reaches a human consumer. Definition:

```python
def demand_factor(h_a, h_b, auto_a, auto_b, params):
    # Effective humanity of each side: humans count fully; agents count
    # to the extent they are NOT autonomous (i.e. acting on a human's behalf).
    eff_h_a = h_a + (1 - h_a) * (1 - auto_a)
    eff_h_b = h_b + (1 - h_b) * (1 - auto_b)
    # Demand factor: surplus is real to the extent at least one endpoint
    # is human-coupled. A2A surplus has a small floor (some A2A activity
    # genuinely benefits humans indirectly via downstream production).
    return params.a2a_floor + (1 - params.a2a_floor) * np.maximum(eff_h_a, eff_h_b)
```

`a2a_floor` is the minimum fraction of A2A surplus that is "really real" — accounts for intermediate goods, B2B production, etc. Default `0.15`.

The wealth-delta computation is split: the `surplus × (1 − demand_factor)` portion still flows as wealth to the prototypes (they get paid in nominal terms) but does not enter `real_welfare_authentic`. This means high-A2A scenarios accumulate wealth-on-paper without accumulating real welfare — exactly the dynamic the model currently misses.

### Code changes

- `engine/core/transactions.py`:
  - Add a `DemandConfig` dataclass to `engine/core/topology.py` (it lives in topology because demand is a structural property of the economy, not the population). Fields: `a2a_floor`, `agent_consumer_share`.
  - Compute `demand_factor` as a vectorized function of `h_a, h_b, auto_a, auto_b`.
  - Multiply `base_surplus` by `demand_factor` *only for the real-welfare aggregate*. Nominal volume continues to use the un-modulated surplus (this is the whole point — nominal sees activity, real sees human consumption).
- `engine/core/world.py`:
  - `World.step` reads `tx.real_surplus_added` (now demand-modulated) and `tx.real_surplus_authentic` (the new field).
  - Pass both into `metrics.step_metrics`.
- `engine/core/metrics.py`:
  - `StepMetrics` gains `real_welfare_authentic_step` and `real_welfare_authentic_cumulative`.
  - The exo-baroque index continues to be computed from the existing `real_welfare_cumulative` for backward compatibility. A new metric `exo_baroque_authentic = nominal_cumulative / max(real_welfare_authentic_cumulative, ε)` is added.

### Defaults that preserve backward compatibility

`a2a_floor = 0.15` is *not* backward-compatible — it changes existing scenarios. Two options:

- **Option A (preferred):** ship a `DemandConfig.enabled = True/False` flag. Existing scenarios set `enabled = False` until each is hand-migrated and re-anchored. This preserves the calibration of every existing run.
- **Option B:** ship without a flag, accept that all existing scenarios shift, and update the ensemble baselines in one PR. Simpler but more invasive.

Pick A. Migrate scenarios one at a time over a follow-up PR.

### New scenarios

- `synthetic_consumers_v2`: identical to `synthetic_consumers` but with `enabled = True`. Should show the predicted welfare collapse.
- `agentic_disconnect`: high `agent_autonomy_mean = 0.95`, low `human_autonomy_mean = 0.20`, mid alpha. Tests the case where humans have abdicated decision-making but agents are still capability-strong.

### Tests

`agentworld/engine/tests/test_demand.py`:

1. With `a2a_floor = 1.0`, the new pipeline produces results identical to the old pipeline (regression).
2. With `a2a_floor = 0.0` and an all-agent population (no humans), `real_welfare_cumulative_authentic` is exactly zero.
3. With `a2a_floor = 0.0` and an all-human population, `real_welfare_cumulative_authentic == real_welfare_cumulative`.
4. Monotonicity: increasing `agent_autonomy_mean` while holding everything else constant strictly decreases `real_welfare_cumulative_authentic`.

---

## Mechanism 2 — Productive vs parasitic folding

### What changes

The folding operator currently produces `nominal_added` and `real_subtracted`. It is replaced with an operator that produces `nominal_added`, `real_subtracted`, *and* `real_added_from_productive_folding`. The total real welfare contribution of folding is then `real_added_from_productive_folding − real_subtracted`, which can be positive at moderate depth and capability and negative at high depth or low capability.

Productive folding is welfare-creating to the extent that it absorbs *variance* that was already in the underlying transactions. The economic content is risk transfer (insurance, hedging, price discovery, capital efficiency). Parasitic folding is purely nominal multiplication.

### The split

At depth `d`, given the depth's nominal contribution `cur_nominal_d`:

```
intermediation_quality_d = cap_intermediating_mean × (1 - decay_with_depth)^(d-1)
productive_share_d = sigmoid(intermediation_quality_d, midpoint=0.5, slope=4)
real_added_d = cur_nominal_d × productive_share_d × variance_absorbed_factor
real_added_from_productive_folding += real_added_d
```

`cap_intermediating_mean` is the weighted-mean capability of agents in `mode = 1` (or, until §4 lands, the population-mean agent capability). The sigmoid maps capability ∈ [0, 1] to productive-share ∈ [0, 1], with the midpoint at 0.5: agents below median capability fold parasitically, agents above median fold productively.

`variance_absorbed_factor` is the share of the underlying transaction variance that this fold layer can absorb. Without an explicit variance accounting layer, set it to a function of `topo.cfg.noise_dof` and the layer's own variance contribution: deep layers absorb less because they're already operating on stabilized risks. A reasonable default:

```
variance_absorbed_factor = base_variance_absorption × (productive_decay ^ (d - 1))
```

with `base_variance_absorption = 0.40` and `productive_decay = 0.65`. At depth 1, a productive layer adds 40% of its nominal contribution back as real. At depth 4, it adds about 11%. By depth 6 or 7, productive folding is essentially exhausted.

This produces the empirically-realistic shape: derivatives create welfare at shallow depth, the marginal welfare contribution declines with depth, deep recursive intermediation is purely parasitic.

### Code changes

- `engine/core/folding.py`:
  - `FoldingResult` gains `real_added_productive: float` and `productive_welfare_yield: float`.
  - `_fold_surplus_geometric` and `_fold_surplus_hawkes` compute the productive split at each depth and accumulate the result.
  - Add a `FoldingProductiveConfig` (or fold the parameters into `TopologyConfig`) for `base_variance_absorption`, `productive_decay`, `cap_midpoint`, `cap_slope`.
- `engine/core/world.py`:
  - `World.step` computes `real_step = max(0.0, tx.real_surplus_added − fold.real_subtracted + fold.real_added_productive)`.
  - The `nominal_step` formula is unchanged.
- `engine/core/metrics.py`:
  - `StepMetrics` gains `productive_welfare_yield` and `real_welfare_from_intermediation_cumulative`.

### Defaults that preserve backward compatibility

The productive folding contribution must equal zero under the default `TopologyConfig`. Achieve this by making `base_variance_absorption = 0.0` the default, and setting it to `0.40` only in scenarios that opt in. New scenarios opt in; existing scenarios stay parasitic.

### New scenarios

- `productive_baroque`: `alpha = 0.85`, high agent capability (`agent_capability_mean = 0.85`), `base_variance_absorption = 0.45`, moderate fold depth. Should land at G2's success criterion.
- `derivatives_revolution`: `alpha = 0.55`, `base_variance_absorption = 0.55`, `productive_decay = 0.75`, low Matryoshka taxes. Tests the limit case where derivatives are aggressively encouraged. Useful as a sanity check that the model doesn't produce free welfare ad infinitum.
- `casino_collapse`: `alpha = 0.85`, low capability, `base_variance_absorption = 0.40`. The split says "productive folding requires capable intermediaries"; this scenario verifies that low-capability folding is parasitic regardless of opt-in.

### Tests

`agentworld/engine/tests/test_productive_folding.py`:

1. With `base_variance_absorption = 0.0` (the backward-compatible default), `FoldingResult.real_added_productive` is exactly zero and `real_subtracted` matches the old implementation bit-for-bit at the same seed.
2. At default `base_variance_absorption = 0.40` and `agent_capability_mean = 0.95`, depth-1 productive folding adds at least 30% of its nominal contribution as real welfare.
3. At any `base_variance_absorption` and `agent_capability_mean = 0.30`, productive folding contributes < 10% of nominal as real welfare across all depths.
4. Productive contribution is monotonically non-increasing in depth.
5. Sum of `productive_welfare_yield` across depths is in [0, 1].

---

## Sequencing

1. **PR 1 — Demand-side feedback, behind a flag.**
   - Add `DemandConfig` with `enabled = False` default.
   - Add the `demand_factor` computation, the new `StepMetrics` fields, the new `exo_baroque_authentic` metric.
   - Add `test_demand.py`.
   - Run all existing scenarios; verify zero diff at default flag.
   - Add `synthetic_consumers_v2` and `agentic_disconnect`. Run them; capture baseline outputs.
   - Update the dashboard to show authentic vs nominal welfare side-by-side, but only when the flag is on.
2. **PR 2 — Productive vs parasitic folding split, with zero-default.**
   - Add the productive-share computation in `_fold_surplus_geometric` and `_fold_surplus_hawkes`.
   - Add the new `FoldingResult` fields and `StepMetrics` fields.
   - Add `test_productive_folding.py`.
   - Verify all existing scenarios produce identical outputs (the `base_variance_absorption = 0.0` default makes this regression-clean).
   - Add `productive_baroque`, `derivatives_revolution`, `casino_collapse`. Capture baselines.
   - Update the dashboard to show `productive_welfare_yield` time series and the new cumulative metric.
3. **PR 3 — Migrate `coasean_paradise_networked` and `baroque_cathedral_networked`.**
   - Turn on `DemandConfig.enabled` and a moderate `base_variance_absorption` for these two scenarios.
   - Re-anchor the ensemble baselines. Document any classification changes.
4. **PR 4 — Sobol sweep, dashboard panels.**
   - Add the new parameters to the Sobol parameter inventory.
   - Run the sweep on terminal EBI, terminal real per-capita welfare, terminal `welfare_authentic` (a new output).
   - Add panels to `build_dashboard.py` for the new metrics.
5. **PR 5 — Documentation.**
   - Add `docs/concepts/demand_and_intermediation.md` (a *concept* doc, not a plan) explaining the two mechanisms in the project's existing voice. The plan you are reading now can be archived to `docs/plans/_archive/` after this lands.
   - Update `docs/concepts/epistemic_status.md` parameter inventory to include the new `DemandConfig` and the new productive-folding parameters, with their epistemic-status classifications.

Each PR should ship independently and pass its own ensemble-regression test.

---

## Parameter inventory (preview for `epistemic_status.md`)

| Parameter | Default (back-compat) | Default (opt-in) | Status | Notes |
| --- | --- | --- | --- | --- |
| `DemandConfig.enabled` | `False` | `True` | Stipulated | Flag, not a continuous parameter. |
| `DemandConfig.a2a_floor` | n/a | 0.15 | Speculative | Order-of-magnitude estimate of B2B intermediate-goods share that flows to humans. |
| `TopologyConfig.base_variance_absorption` | 0.0 | 0.40 | Speculative | Per-layer fraction of fold nominal that is welfare-creating at maximum capability. |
| `TopologyConfig.productive_decay` | n/a | 0.65 | Speculative | Per-layer decay of welfare creation; productive folding becomes parasitic at depth ~6. |
| `TopologyConfig.cap_midpoint` | n/a | 0.50 | Stipulated | Capability above which folding becomes productive. |
| `TopologyConfig.cap_slope` | n/a | 4.0 | Speculative | Sharpness of the capability → productivity transition. |

All are **speculative** in the sense of `epistemic_status.md` — sweep them, do not fit them.

---

## Risks and known limitations

- **Risk: feature creep before §3 lands.** The temptation will be to "just add" law-strength gating in PR 1. Resist. The brief depends on these two mechanisms shipping in their pure form so their effect can be isolated before being stacked.
- **Risk: `a2a_floor = 0.15` is too low.** If `synthetic_consumers_v2` produces real_welfare_cumulative ≈ 0 by step 30, the model is broken (some real welfare clearly does flow from agentic activity). Tune up to `0.25` or `0.30` if this happens.
- **Risk: the productive-folding sigmoid produces step-function artifacts at the capability midpoint.** If the histogram of `productive_welfare_yield` across scenarios is bimodal at 0 and 1, lower `cap_slope` to 2.5.
- **Limitation: variance absorption is not actually computed from per-pair variance.** It is a function of depth and a constant. A fuller version would propagate variance through the fold cascade. Out of scope.
- **Limitation: A2A surplus that *would* eventually reach humans through long supply chains is undercounted.** The `a2a_floor` is a stand-in for this. A network-aware version would propagate `eff_h` through the adjacency matrix. Out of scope.

---

## When this is done

The two mechanisms are stable, behind their compatibility defaults, with three new scenarios each, regression tests passing, Sobol indices in the dashboard, concept doc written. Then `brief/dynamic_mechanisms.md` becomes the next workstream and the §3 implementation can begin.

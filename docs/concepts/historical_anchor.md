# Historical anchor — US 1980-2024 FIRE share

> *"The deliverable is not a small RMSE. It is a documented RMSE. The anchor exists so every future claim the engine makes has one calibrated number it has to live next to."* — `docs/plans/_archive/validation_lift_plus_live_viz.plan.md`, A1.

## What this is

A stylized historical anchor that compares the alpha-engine's per-step
`governance_overhead_fraction` against the share of US GDP attributed to the
FIRE supersector (Finance + Insurance + Real Estate + Rental and Leasing),
1980-2024. The engine runs for 45 steps with an α-schedule that rises
linearly from 0.40 to 0.70 — calibration at the *schedule* level, not the
outcome level — and the resulting overhead trajectory is compared to the
empirical series on a common 0-1 scale.

The anchor's job is not to demonstrate that the engine forecasts the FIRE
share. It is to expose the engine to one falsifiable, dated, dimensioned
number so every future claim can be cited against it.

The artifact lives at `engine/validation/historical_anchor.py`. Run it with:

```bash
agentworld validate anchor
```

This writes `outputs/validation/historical_anchor.json` (the per-year
arrays + RMSE/MAE/bias) and `outputs/validation/historical_anchor.png`
(an overlay chart).

## Empirical series

The constant `US_FIRE_SHARE_OF_GDP_1980_2024` in `historical_anchor.py` is a
stylized 45-year series of the Finance + Insurance + Real Estate + Rental
and Leasing supersector's share of US GDP. Values are aggregated from the
BEA's "Value Added by Industry" tables (NIPA Table 6.1B/D; the FIRE
supersector is also the F industries category in BEA's NAICS-based industry
accounts). Public summaries on FRED's `VAPGDPF` / `VAPGDPRR` series and the
BEA's annual industry accounts give the same shape.

Two notes on the series:

1. **It is stylized, not vintage-bound.** Different BEA vintages assign
   slightly different shares to FIRE at any given year (definitional
   revisions of "real estate" and "rental"; reclassification of management
   of companies and enterprises). The anchor uses a smoothed, 0.5-1pp-
   stable representation. A future engine claim that differs from this
   series by 5pp is a real disagreement; one that differs by 0.5pp is
   probably arguing with definitional noise.
2. **It includes owner-occupied imputed rents.** The BEA's value-added
   number for real estate includes rental income on owner-occupied housing,
   which inflates the FIRE share above what most non-economists picture
   when they say "finance share of the economy." The engine's
   `governance_overhead_fraction` makes no equivalent inclusion. This is
   one of several reasons not to expect a tight RMSE.

## Engine quantity

`StepMetrics.governance_overhead_fraction` is computed in
`engine/core/metrics.py:gov_overhead`. It is the fraction of attempted
Coasean transactions that the Matryoshka filter sequence rejects:

```
governance_overhead_fraction = (rejected_law + rejected_market + rejected_align)
                             / (n_transactions_real + rejected_law + rejected_market + rejected_align + rejected_cost)
```

This is **not** the same quantity as a sectoral GDP share. Both are in
[0, 1] and both carry the rough semantics of "share of activity attributed
to intermediation," but the engine quantity is a rejection rate and the
empirical quantity is a value-added share. The anchor accepts this
mismatch on purpose — calibration at the level of *which intermediation
intensity dial to turn* (α), not at the level of unit-matching the output.

## α-schedule

```python
alpha_schedule_for_anchor(n=45) = list(np.linspace(0.40, 0.70, 45))
```

A linear rise from 0.40 in 1980 to 0.70 in 2024. The schedule is the only
knob the anchor fits; the rest of the engine runs at scenario defaults
(`equilibrium_drift`, scale=small, seed=0). The shape was chosen to
approximate the secular rise in US intermediation intensity over the
period, not the year-by-year wiggles. Recessions, dot-com bubble, the
2008 GFC, and COVID are not in the schedule and the engine cannot reproduce
them.

## Result, current vintage

At commit time, the anchor reports:

| Metric | Value |
| --- | --- |
| RMSE | **0.0634** |
| MAE | 0.0612 |
| Bias (sim − emp) | **−0.0612** |
| Largest error year | 2009 |
| Largest error | −0.0793 |

The negative bias means the engine systematically *under-attributes*
intermediation: its rejection rate sits ~6 percentage points below the
empirical FIRE share. That is partly because (a) the engine doesn't have
imputed rents, (b) the FIRE supersector includes activities the engine
treats as productive trade rather than overhead, and (c) the schedule was
calibrated to shape, not level. The largest single-year error is 2009 at
the trough of the GFC, where the empirical FIRE share rose sharply
(financial bailouts inflate FIRE value-added) while the engine's overhead
rate kept tracking the smooth schedule.

## What the anchor's RMSE *cannot* say

- It cannot say the engine forecasts intermediation share. The engine has
  no business-cycle, no specific shock series, and no fitted parameters.
- It cannot say a 6pp average error is "small" or "large" without a
  reference frame. A naive flat-line baseline at the empirical mean
  (0.197) has RMSE ~0.014 against the empirical series — much smaller
  than the engine's 0.063 — because the empirical series has very low
  variance. The anchor exists to *document* this fact, not to argue
  around it.
- It cannot fix the engine. The acceptance criterion is that this number
  is *recorded*, *dated*, and *re-derivable from the same artifact* in
  every future commit. Driving it down is a separate research project.

## What downstream claims have to say

After this anchor lands, any claim of the form "the engine shows X" must
also state where X sits relative to the FIRE-share trajectory. Two
patterns are admissible:

- *"X is consistent with the anchor."* Means: the same 1980-2024 run
  also exhibits X without further parameter tuning.
- *"X is a feature of the un-calibrated parameter region."* Means: X
  appears in scenarios outside the anchor's α-schedule, and the gap from
  the anchor is part of the claim, not background.

Claims that ignore the anchor are claims about an engine that no longer
exists in this repository.

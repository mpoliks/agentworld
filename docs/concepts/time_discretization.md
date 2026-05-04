# Time discretisation in the α-engine

> Companion note for `WorldConfig.dt` and the rate-like sub-processes that respect it.

The original engine had no model-time semantics: a "step" was an iteration of the main loop with no fixed real-world duration. This is named as a failure mode in [`epistemic_status.md`](epistemic_status.md) ("step semantics ambiguity"). The 2026-Q2 lift adds an explicit `dt` parameter so that the rate-like sub-processes have a continuous-time interpretation while the discrete-event sub-processes keep their per-step calibration.

This note is the contract.

---

## Default convention

| | |
| --- | --- |
| `WorldConfig.dt` | `1.0` |
| Model time per step | one quarter (≈ 3 months of calendar time) |
| Default `n_steps` | `200` → ≈ 50 years of model time |

The quarter cadence is not enforced anywhere in the math. It is the convention used by the historical anchor (FIRE share 1980–2024 = 45 years = 180 steps) and by the brief's narrative timeframe (2026 → 2076). Choose any other cadence by setting `dt` and re-interpret outputs accordingly; the scaling rules below apply regardless.

---

## What `dt` rescales

The following sub-processes have continuous-time interpretations and scale with `dt`:

| Sub-process | Scaling | Where |
| --- | --- | --- |
| Law strength (`natural_decay`, `law_decay_recovery × upkeep_investment`) | linear in `dt` | [`World._advance_law_state`](../../engine/core/world.py) |
| Law capture (`beta_capture_growth`, `gamma_civic_pushback × civic_pushback_default`) | linear in `dt` | same |
| Capability drift (`capability_learning_rate`, `capability_decay_rate`) | linear in `dt` | [`engine/core/dynamics.py:capability_update`](../../engine/core/dynamics.py) |
| Wealth depreciation | exact: `wealth ← wealth × (1 − rate)^dt` | [`engine/core/dynamics.py:wealth_depreciation`](../../engine/core/dynamics.py) |
| Fold cascade *firing probability* (`Topology.folding_propensity`) | discrete-time analog: `p ← 1 − (1 − p_unit)^dt` | [`engine/core/topology.py:folding_propensity`](../../engine/core/topology.py), [`engine/core/folding.py`](../../engine/core/folding.py) |

Linear scaling is correct for first-order Euler integration of a rate ODE. The depreciation and folding-firing cases are probabilistic: the exact relation `(1 − rate)^dt` (and its complement `1 − (1 − p)^dt`) is the correct discrete-time analog of an exponential rate, and it makes multi-step composition cleanly correct (running once at `dt = 2` matches running twice at `dt = 1` in expectation).

For folding, `dt` rescales *only* the per-step probability of the cascade firing at all. Once the cascade fires, its contents — branching ratio, depth-decay constant, Hawkes self-excitation `n_eff`, Gamma shape `k` — are *intra-cascade* and remain `dt`-invariant. The empirical anchor for the Hawkes machinery (Bacry & Muzy 2015 endogeneity ratio) is a property of the cascade microstructure, not of how often the cascade fires.

`dt = 1.0` reproduces all canonical scenario outputs bit-for-bit; the unit tests in [`engine/tests/test_dt.py`](../../engine/tests/test_dt.py) pin the bit-equivalence, the linear scaling, the exact multiplicative scaling, and the discrete-time-analog scaling.

---

## What `dt` does **not** rescale

The discrete-event sub-processes keep per-step calibration:

| Sub-process | Why it stays per-step |
| --- | --- |
| Coasean pair sampling (`pairs_per_step`) | `pairs_per_step` is a sample size of the population's pair density, not a rate. Doubling `dt` does not double the number of bilateral exchanges per step in any natural reading. |
| Fold cascade *contents* (branching ratio, Hawkes endogeneity, Gamma shape) | These describe cascade microstructure, calibrated against [Bacry & Muzy 2015](../bibliography.md). Rescaling them without recalibrating shifts the empirical anchor. The cascade's *firing probability* does scale with `dt` (see above); its *contents* do not. |
| Entry/exit (`entry_exit`) | Stochastic resampling of failed prototypes. The probabilistic event has no continuous-time relation that survives the bookkeeping. |
| Institution formation, dissolution, merger | Discrete population events with their own per-step gates (`formation_check_every_k`). |
| Demand-side modulation, Pigouvian tax | Per-pair fractions, dimensionless w.r.t. `dt`. |

The practical implication: setting `dt ≠ 1.0` shifts the *relative* timescale between the rate processes and the event processes. If the law decays half as fast (`dt = 0.5`) but the same number of folding cascades fire per step, the law's footprint on the cascade is over-amplified. **Default to `dt = 1.0` unless you have a specific question that requires a different cadence and you are explicit about which side of the ratio is fixed.**

---

## Calibration anchor

The single anchor that fixes a real-world time scale is the historical-FIRE-share validation ([`historical_anchor.md`](historical_anchor.md)). It uses 45 calendar years (1980–2024) and the engine's hand-picked α-schedule of length 180. By construction, that pinning gives a quarterly cadence at `dt = 1.0`.

Anything else — Hawkes branching ratio, capability drift rate, agent capability mean — is calibrated against per-step empirical estimates that themselves carry no calendar reading. Treat the quarter mapping as a convention that lives only on top of the rate sub-processes; the discrete-event side has no claim to it.

---

## Migration discipline

Code that adds a new rate-like sub-process to the engine should:

1. Multiply per-step deltas by `dt` at the call site (or accept `dt` as a parameter and apply it inside the function — matches `capability_update` / `wealth_depreciation`).
2. Add a unit test in `test_dt.py` that pins the linear (or exact-multiplicative) scaling.
3. Default behaviour at `dt = 1.0` must remain bit-identical to the prior code path. The canonical regression suite ([`test_regression_canonical.py`](../../engine/tests/test_regression_canonical.py)) is the gate.

Code that adds a new discrete-event sub-process should leave it per-step and document why in this file.

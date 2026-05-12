# Live-Engine Parameters

This doc is the single source of truth for the parameters exposed in the
live-engine UI (`dashboard/live.html`). It pins three layers of copy per
parameter — slider label, hover tooltip, expand-drawer help — so that the
front-end, the docs, and the plan agree on definitions and ranges.

Scoped from the canonical N=2048 Sobol ranking
(`outputs/sensitivity/sobol_indices.n2048.json`): eight numeric parameters
covering the Tier-1 and upper Tier-2 ST mass, plus one α(t) schedule editor
and a five-option scenario-family selector. Tier-3 parameters live behind an
"Advanced" drawer that is not part of the V1 cut.

Definitions trace to the engine, not paraphrase:
- `engine/core/topology.py:505` for `TopologyConfig`
- `engine/core/population.py:55` for `PopulationConfig`
- `engine/core/folding.py` for the fold-operator equations

---

## About the bounds

Every numeric parameter in this doc carries a "Sobol range" — the box the
N=2048 sweep sampled across. The bounds are **the sampling box, not a
physical limit**. A bound like `agent_capability_mean ∈ [0.45, 0.92]` does
not mean agents cannot in principle be more capable than 0.92; it means the
S1/ST indices the live engine displays are only valid inside that box.
Sliders are clamped to the Sobol range by default. An "extend ranges" toggle
in the Advanced drawer lets exploratory users move outside the box, at the
cost of losing the sensitivity anchor.

---

## The eight numeric parameters

Ranked by mean |ST| across the six headline metrics (EBI, real welfare,
gini, authentic EBI, authentic real welfare, productive welfare yield).

### `alpha` — Smooth ↔ baroque axis

- **Sobol range:** `[0.05, 0.95]`. **Default:** `0.5`. **Mean |ST|:** 0.40.
- **Label:** Smooth ↔ baroque (α)
- **Tooltip:** Krier–Bratton axis. 0 = no folding, no striation; 1 =
  aggressive recursive folding.
- **Help:** The engine's primary control variable. Most other parameters
  scale off α: folding rate as `α^1.4`, branching as `(0.6 + 0.4·α)`,
  striation cost as `α · 0.020 · (1 + 0.3·(1 − cross_stack_compat))`. The
  slider stays inside `(0, 1)` because the corners produce degenerate runs.
  See `docs/concepts/smooth_striated.md`.

### `agent_capability_mean` — Agent competence (μ)

- **Sobol range:** `[0.45, 0.92]`. **Default:** `0.72`. **Mean |ST|:** 0.37.
- **Label:** Agent competence (μ)
- **Tooltip:** Mean of the normal distribution agents are drawn from;
  lowers Coasean friction.
- **Help:** Agents are drawn `N(μ, agent_capability_sd)` with default
  `sd = 0.20`. Humans are drawn `N(0.45, 0.18)`. Capability enters friction
  as `friction_floor + base_friction × (1 − capability)^coase_exp`. The
  lower bound `0.45` matches the human baseline; the upper bound `0.92` is
  the Sobol-box ceiling, not a physical cap. See
  `engine/core/population.py:74` and
  `engine/core/topology.py:722` (`friction_for_pair`).

### `folding_propensity` — Fold trigger rate at α=1

- **Sobol range:** `[0.05, 0.75]`. **Default:** `0.55`. **Mean |ST|:** 0.25.
- **Label:** Fold trigger rate (at α=1)
- **Tooltip:** Probability that a positive-surplus transaction spawns a
  sub-market, evaluated at α=1.
- **Help:** Realised propensity scales as `folding_propensity × α^1.4`. At
  α = 0.5 the realised rate is roughly 38% of the slider value. With
  `folding_pressure_feedback` enabled, the rate is also multiplied by
  `1 + strength × max(0, pressure − anchor)`, capped at
  `max_multiplier`, where `pressure` is the cumulative EBI excess. See
  `engine/core/topology.py:751` (`folding_propensity`).

### `base_variance_absorption` — Productive-fold share (depth 1)

- **Sobol range:** `[0.0, 0.6]`. **Default:** `0.0`. **Mean |ST|:** 0.17.
- **Label:** Productive-fold share (depth 1)
- **Tooltip:** Real-welfare contribution per fold at depth 1 and max
  capability. Zero ⇒ folding is purely parasitic.
- **Help:** When `> 0`, a fold contributes real welfare scaled by
  intermediator capability through a sigmoid around `cap_midpoint = 0.5`
  with sharpness `cap_slope = 4.0`. Welfare decays per layer as
  `absorption × productive_decay^(d−1)` with `productive_decay = 0.65`.
  Legacy alpha-engine scenarios run with this at zero; the
  demand-and-intermediation scenarios (18–22) opt in. See
  `docs/concepts/demand_and_intermediation.md` and
  `engine/core/folding.py:76`.

### `folding_branching` — Children per fold

- **Sobol range:** `[1.6, 3.4]`. **Default:** `2.7`. **Mean |ST|:** 0.07.
- **Label:** Children per fold
- **Tooltip:** Average sub-markets spawned per parent fold (at α=1).
- **Help:** Realised branching is `folding_branching × (0.6 + 0.4·α)`. The
  Sobol bounds bracket the empirical Hawkes branching ratio in financial
  cascade studies (Bacry–Muzy 2015). The optional Hawkes folding model
  preserves the closed-form mean at the same value. See
  `engine/core/folding.py:188`.

### `base_friction` — Coasean friction at capability=0

- **Sobol range:** `[0.02, 0.08]`. **Default:** `0.05`. **Mean |ST|:** 0.07.
- **Label:** Coasean friction (at capability=0)
- **Tooltip:** Per-transaction friction at zero capability. Realistic
  capabilities pay much less.
- **Help:** Full friction is
  `friction_floor + base_friction × (1 − capability)^coase_exp
   + α × 0.020 × (1 + 0.3·(1 − cross_stack_compat))`.
  At default capability `0.72` and `coase_exp = 1.7`, an agent pays
  roughly `12%` of `base_friction`. See `engine/core/topology.py:722`.

### `max_productive_real_share` — Productive-fold ceiling

- **Sobol range:** `[0.2, 0.8]`. **Default:** `0.6`. **Mean |ST|:** 0.05.
- **Label:** Productive-fold ceiling
- **Tooltip:** Caps productive-fold welfare at this fraction of the
  underlying real surplus. Inert when productive folding is off.
- **Help:** Acts as `cap = base_real_surplus × max_productive_real_share`.
  With `base_variance_absorption = 0` the cap never binds — productive
  folding is gated off entirely. Inside the productive-folding scenarios
  the slider sets how much of the real surplus the intermediation chain
  can capture before saturation. See `engine/core/folding.py:105`.

### `fold_nominal_multiplier` — Nominal value-add per fold

- **Sobol range:** `[1.3, 2.2]`. **Default:** `1.85`. **Mean |ST|:** 0.05.
- **Label:** Nominal value-add per fold
- **Tooltip:** Each fold layer multiplies nominal GDP by this factor.
  `1.85` ≈ "+85% nominal per layer."
- **Help:** Applied as
  `nominal ← nominal × folding_branching × fold_nominal_multiplier × depth_prop`
  along the fold chain. The defining lever for nominal/real divergence —
  EBI rises chiefly through this multiplier × branching × depth. See
  `engine/core/folding.py:189` and `docs/concepts/fractal_folding.md`.

---

## Coupling: parameters that go inert together

`base_variance_absorption` and `max_productive_real_share` form a coupled
pair. When `base_variance_absorption = 0`, the productive-fold path is
gated off entirely (`engine/core/folding.py:76`), and
`max_productive_real_share` has no effect on any metric.

The UI handles this in one of two ways:

1. **Single "productive folding" toggle** that flips
   `base_variance_absorption` between `0.0` (off) and the slider value
   (on). When off, both rows are greyed out.
2. **Grey-out on zero.** If `base_variance_absorption` is dragged to zero,
   `max_productive_real_share` greys out and shows "inert until productive
   folding is enabled" as its tooltip.

V1 ships option 1 — the productive-folding toggle. Option 2 is left as a
future refinement for users who want to vary intermediator capability
inside a productive-folding regime.

---

## The α(t) curve editor

α has the highest ST in the Sobol surface. Three of the canonical
scenarios — `smoothing_cascade` (4), `fold_avalanche` (5),
`recursive_simulation` (14) — depend on α being time-varying. A flat
slider cannot represent them.

The live UI exposes α as either:

- **Constant α**, drawn from the slider; or
- **Schedule α(t)**, drawn from a piecewise-linear editor with up to four
  control points along the simulation horizon.

The editor emits a `WorldConfig.alpha_schedule: list[float]` of length
`n_steps`. See `engine/core/world.py:57` for how the schedule is consumed
(it overrides `topology.cfg.alpha` per step).

---

## Scenario families (chosen before run, not toggled mid-run)

The 33 canonical scenarios decompose into five families along
structural-toggle lines. The live UI presents these as a radio group at
the top of the parameter panel; selecting a family fixes which engine
modules are active for the run. Families are not toggleable mid-run —
they change which equations the engine evaluates, not just parameter
values.

| Family | Scenarios | Structural switches |
| --- | --- | --- |
| **Alpha-engine baseline** | 1–17 | All productive/demand/Pigouvian/law/strategy off. The original 15 plus the two networked variants. |
| **Demand & intermediation** | 18–22 | `demand.enabled = True`; `base_variance_absorption > 0`. Productive folding + demand-side feedback on. |
| **Dynamic law** | 23–25 | `law.enabled = True`. Law strength evolves; capture and renewal mechanisms run. |
| **Pigouvian automation** | 26–29 | `pigouvian.enabled = True`. Per-pair A2A tax recycled to humans. |
| **Emergent strategy / institutions** | 30–33 | `strategy.enabled` and/or `population_dynamics.enabled` and/or `institutions.enabled = True`. Agents learn α; firms form. |

Inside each family, the eight numeric parameters above are the live
sliders. Family-specific knobs (e.g. `law.decay_rate`, `pigouvian.tau`)
appear as a small secondary section that only renders when the relevant
family is selected. Tier-3 numeric parameters from the Sobol problem
(`a2a_floor`, `coase_exp`, `cap_slope`, `cross_stack_compat`,
`productive_decay`, `market_layer_tax`, `fold_real_efficiency`) live in
the Advanced drawer and apply across all families.

---

## What this doc is not

- Not a tutorial for the underlying physics. That work is in the concept
  docs (`smooth_striated.md`, `fractal_folding.md`,
  `demand_and_intermediation.md`, `pigouvian_automation.md`).
- Not a validation reference. The Sobol indices and canonical scenarios in
  `outputs/sensitivity/` and the static dashboard remain the publication
  anchor; the live engine is the exploratory sibling.
- Not a complete inventory of `WorldConfig`. The full config carries
  roughly forty fields; the live UI exposes the eleven that carry the
  Sobol-ranked sensitivity mass plus the family-specific knobs above.

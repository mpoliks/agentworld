# α as Outcome

> *"Capability is a magnifier; smooth/striated is the direction."* — `docs/concepts/smooth_striated.md`

This doc reframes `TopologyConfig.alpha` from a primary control variable
into an emergent property of three lever categories: agentic, legal, and
environmental. The change is conceptual, not structural — the engine
still computes friction, folding rate, and striation cost off α — but in
the spatial sandbox the user no longer touches α directly. The HUD
reports α; the user moves the levers that produce it.

The motive: a user driving α by hand cannot tell whether α=0.7 came from
high agent capability + permissive law, from low capability + restrictive
law, or from compute scarcity squeezing out marginal trades. Those three
worlds look identical in `smooth_striated.md` but have different welfare
profiles, different rejection mixes, and different concentration
dynamics. Treating α as the input collapses them.

---

## Reading the existing axis

`docs/concepts/smooth_striated.md` defines α as the Deleuzian smooth ↔
striated coordinate, with concrete consequences in the engine:

- friction-cost scales linearly in α
- folding propensity scales as `α^1.4`
- folding branching modulates by `(0.6 + 0.4·α)`
- striation cost scales as `α · 0.020 · (1 + 0.3·(1 − cross_stack_compat))`

`docs/concepts/fractal_folding.md` shows what high α produces: nominal
GDP multiplied 14× at three fold layers, 800× at six, 250,000× at ten,
with welfare per capita degrading and Gini concentrating.

`docs/concepts/coasean_bargaining.md` shows what low α produces: EBI ≈
1, welfare ≈ GDP, individual-layer rejection becomes the binding
constraint, fold depth ≤ 4.

The axis is real. The question is what *drives* a system to one end or
the other. The current engine treats that as exogenous (the user sets
α). The lived experience the engine is trying to capture treats it as
endogenous (α is what the agents, the law, and the substrate produce).

---

## Three lever categories and their α-vectors

### Agentic levers — what the agents are

Each agentic lever pushes α toward one pole or the other. The signs are
not always obvious; the engine encodes them.

| Lever                          | Engine field                                       | Direction of push on α |
| ------------------------------ | -------------------------------------------------- | ---------------------- |
| Capability                     | `agent_capability_mean`                            | ↓ (smoother)           |
| Communication fidelity         | `NormsConfig.certified_fraction` (new)             | ↓ (smoother)           |
| Network model                  | `network_model ∈ {well_mixed, scale_free, SBM}`    | scale_free → ↑         |
| Autonomy                       | `agent_autonomy_mean`                              | ↑ (folding intuition)  |
| Norm decay                     | `NormsConfig.update_rate`                          | high → ↑ (capture)     |
| Trade rate                     | `agent_trade_rate_multiplier`                      | ↑ (more A2A volume)    |

The intuition for the directions: higher capability and higher
communication fidelity reduce the marginal cost of a direct trade
clearing without intermediation, so folding becomes a worse bet and
realized α drifts down. Scale-free networks concentrate trade volume on
hub nodes, which create natural surplus pockets where folding is
profitable, so realized α drifts up. The autonomy direction is the
Krier observation in `coasean_bargaining.md` made operational: fully
autonomous agents have no human consumer to satisfy and will multiply
nominal markets without a real-welfare counterpart.

### Legal levers — what is imposed on them

| Lever                          | Engine field                                       | Direction of push on α |
| ------------------------------ | -------------------------------------------------- | ---------------------- |
| Pigouvian tax rate             | `PigouvianConfig.tax_rate`                         | ↓                      |
| Pigouvian recycling            | `PigouvianConfig.recycling`                        | ↓ (when human_wealth)  |
| Market-layer tax               | `market_layer_tax`                                 | ↓                      |
| Alignment tax                  | `individual_layer_alignment_tax`                   | ↓                      |
| Law strength                   | `LawConfig.strength`                               | ↓                      |
| Regulator presence             | `RegulatorConfig.enabled`                          | ↓                      |
| Fold-depth cap                 | `folding.max_depth`                                | ↓ (direct)             |
| Transaction-size cap           | `transaction_size_cap` (new)                       | ↓                      |

Every legal lever pushes α down — that is what governance is for in this
model. The interesting question is the rejection-mix consequence:
`pigouvian_automation.md` shows the Pigouvian tax reduces nominal volume
without raising the rejection rate, while a tighter `fold.max_depth`
suppresses the same volume by gating before execution. Two legal moves
with the same α-effect produce different welfare profiles.

### Environmental levers — what the substrate allows

The environmental category is the least developed in the current
engine. The user explicitly named compute and power as candidate
levers; `docs/research/compute_and_power_as_constraint.md` works out
the engine surface.

| Lever                          | Engine field                                       | Direction of push on α |
| ------------------------------ | -------------------------------------------------- | ---------------------- |
| Compute budget per tick        | `ComputeConfig.budget_per_tick` (new)              | scarce → ↑             |
| Power cost per trade           | `ComputeConfig.power_cost_per_trade` (new)         | ↑                      |
| Compute distribution           | `ComputeConfig.distribution` (new)                 | wealth-weighted → ↑    |
| Scale                          | `ScalePreset`                                      | ↑ at very high scale   |
| Cross-stack permeability       | `cross_stack_permeability`                         | open → ↓               |

The environmental signs are less established than the agentic and legal
ones. Compute scarcity is conjectured to push α up because scarce
compute concentrates onto the highest-return uses, which under the four
folding-pressure mechanisms in `docs/concepts/fractal_folding.md` are
intermediation rather than direct trade. That conjecture is one of the
things the sandbox is built to test.

---

## What goes on the HUD

EBI is the canonical α-readout. It is already in `StepMetrics`. The HUD
shows it prominently. Three secondary readings give the rejection-mix
context that EBI alone cannot:

- **EBI** — exo-baroque index, the nominal/real divergence.
- **REJ MIX** — proportions of cost-rejected, market-rejected,
  alignment-rejected, law-rejected per the last 30 ticks.
- **WELFARE/A** — real welfare per agent per tick, anchored against the
  population mean.
- **GINI** — wealth concentration.

A user moving a lever sees all four readouts move. The lever did one
thing; the system did several. That is the experience the sandbox is
trying to produce.

---

## What this means for the engine

1. `TopologyConfig.alpha` remains a real config field. The dashboard
   sets it from the lever state via a deterministic mapping documented in
   `docs/plans/spatial-sandbox.md`. There is no engine change here.

2. The α(t) schedule editor from `live_parameters.md` is retired in the
   spatial sandbox. α is produced, not authored. Scheduled-α scenarios
   (`smoothing_cascade`, `fold_avalanche`, `recursive_simulation`)
   remain accessible through the batch CLI and the static dashboard for
   reproducibility, but the sandbox does not offer them.

3. The mapping from levers to α is a function the dashboard owns. The
   simplest defensible form:

   ```
   α = clamp(0, 1,
       α_base
       + w_cap   · (1 − capability)
       + w_cert  · (1 − certified_fraction)
       + w_net   · scale_free_concentration
       + w_pig   · (1 − pigouvian_tax_rate)
       + w_law   · (1 − law_strength)
       + w_fold  · (folding_max_depth / 10)
       + w_comp  · compute_scarcity
   )
   ```

   Weights are pinned by Sobol-style regression on a fixed grid of
   lever states, computed offline. The dashboard ships with the pinned
   weights and exposes them in a hidden "Why" inspector for the curious.

4. The Sobol indices in `outputs/sensitivity/sobol_indices.n2048.json`
   are computed against the input α. They remain valid as a guide to
   parameter importance. They are not invalidated by the lever
   reframing; they describe a different surface of the same system.

---

## References

- `docs/concepts/smooth_striated.md` — the canonical α axis.
- `docs/concepts/fractal_folding.md` — high-α regime.
- `docs/concepts/coasean_bargaining.md` — low-α regime.
- `docs/concepts/pigouvian_automation.md` — a legal lever that pushes α
  down without changing rejection mix.
- `docs/concepts/matryoshkan_alignment.md` — the three-layer governance
  stack that grounds the legal lever category.
- Bratton, B. (April 21, 2026). Telegram correspondence. The
  "smooth/striated is the variable" claim.
- Krier, S. (Sept 2025). *Coasean Bargaining at Scale.* AI Policy
  Perspectives. The smooth attractor's stable form.

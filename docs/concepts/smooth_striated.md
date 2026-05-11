# The Variable: Smooth ↔ Striated

> *"Smooth and striated is the variable."* — Benjamin Bratton, April 21 2026

---

## Why one variable, and why this one

Most discussion of agentic economies fixates on *capability* — how powerful the agents are, how aligned they are, how cheap they are. Capability matters enormously, but it is not the variable that distinguishes the two attractors of Agentworld. **Capability is a magnifier; smooth/striated is the direction.**

Consider: a high-capability agent population at low alpha (Smoothworld) produces direct welfare gains, market clearance, and Coasean efficiency. The same high-capability agent population at high alpha (Baroqueworld) produces the same underlying welfare *plus* a fractal canopy of derived markets that inflate nominal GDP without adding to it. Same agents. Same compute. Wildly different societies.

The smooth/striated dimension is therefore the right axis for a research brief. Capability is not the question. *What the agents do with their cheap negotiation capacity* is.

---

## The Deleuzian source

Deleuze and Guattari, in *A Thousand Plateaus*, distinguish between two modes of space:

- **Smooth space** — nomadic, intensive, open-ended, haptic, occupied without measurement. The desert. The sea before 1440. The patch of forest a hunter knows by touch.
- **Striated space** — gridded, metric, hierarchical, optic, requiring counting and measurement to occupy. The Roman grid. The cadastral map. The supply chain.

Their canonical example is the sea: *smooth* until 1440, when Portuguese navigators introduced charts with meridians, parallels, longitudes, and latitudes. The same physical ocean became a *striated* one. Distance became calculable. Trade routes became plannable. Colonialism became operationally possible. The medium did not change; the *measure* did.

D&G insist that smooth and striated never exist purely; they exist only in mixtures. They continually transform into one another. *"What interests us is precisely the passages and combinations."*

This is the right vocabulary for Agentworld because:

1. It captures that the smooth and striated regimes are **the same matter under different measures**, not different matters. The agent layer is what does the measuring.
2. It treats the choice between regimes as **a continual transformation**, not a one-time decision. Sectors, jurisdictions, and stacks can occupy different positions on the continuum at the same time.
3. It already has a theory of *power*: striation is what state-machines do to nomadic populations. The agent layer can play either side of this game depending on how it is built.

---

## Translating to a parameter

In our model, the smooth/striated dimension is a scalar `α ∈ [0, 1]`. Every other parameter that depends on it is a function of α:

- **Transaction-cost protocol overhead** scales linearly with α — striated regimes have more layers of protocol gunk.
- **Folding propensity** scales as α^1.4 — folding is a high-α phenomenon, suppressed sharply at low α.
- **Folding branching factor** is modulated by α — even when folding occurs, smoother regimes spawn fewer sub-markets per parent.

The choice of α is *a choice*, but it is a choice made collectively, often implicitly, by:
- protocol designers (whoever designs A2A payment standards picks how easy folding is)
- regulators (whoever defines what counts as a transaction picks where the EBI goes)
- consumers / principals (whoever rewards their agent for "doing more" pushes toward Baroque)
- foundation-model providers (whoever sets the default agent personality picks an α prior)

There is no neutral default. Even an "unintervened" agent layer will sit at *some* α, determined by the path-dependent properties of whatever protocol got there first.

---

## Why "smooth" is not "good" and "striated" is not "bad"

The temptation, especially for readers steeped in Deleuze, is to read smooth = liberatory and striated = oppressive. Don't. The two regimes have different distributional consequences and different failure modes:

- **Smoothworld** flattens markets but *concentrates power in protocol owners* — whoever runs the substrate on which all bargaining happens. The state shrinks but the private substrate underneath becomes Schmittian.
- **Baroqueworld** preserves the appearance of pluralism (every transaction has many sub-markets, many priced layers) but *collapses human legibility* — the economy is legible only to itself. Power moves to whoever defines the protocols, whoever sets the units of account, whoever decides what counts as a transaction.

A naïve liberal preference for smoothing — read Krier — should be met with the question: *who owns the smoothing layer?* A naïve preference for striation — Bratton's pluralist instinct, read sympathetically — should be met with: *who reads the maps?*

Both regimes can produce extraordinary welfare. Both can produce extraordinary capture. The artifact does not pick a side; it tries to make the choice visible.

---

## What this axis is not — permeability

Tomašev, Jacobs et al. (*Virtual Agent Economies*, arXiv:2509.10147) propose a two-axis taxonomy: *emergent ↔ intentional* origin and *permeable ↔ impermeable* boundary between the agent economy and the human economy. Neither of those axes is the smooth ↔ striated dial. A permeable Smoothworld and an impermeable Smoothworld are different attractors with different welfare profiles. The canonical scenarios in this artifact all run at implicit *high permeability* — every agent-side transaction is treated as freely substitutable for a human-side transaction at the labor-share split. There is no parameter that gates whether the trade is *attempted* across the agent / human boundary; only `cross_stack_compat` gates whether it *fits* once attempted, and only inside the law layer.

`docs/plans/hadfield_jacobs_robustness.md` (W1c) adds `cross_stack_permeability ∈ [0, 1]` as a first-class topology parameter — applied before the Matryoshka cascade rather than inside the law gate, so impermeable variants drop trade *volume* rather than just trade *acceptance rate*. Two new scenarios bracket the axis: `agent_economy_sandbox` (low permeability) and `permeable_default` (current behavior). Until those land, the smooth / striated dial is reported at the artifact's default permeability prior and the impermeable corner of the Tomašev / Jacobs taxonomy is not in the sweep.

---

## Sectoral and jurisdictional heterogeneity

In practice, no real economy will sit at a single α. The likely 2030s pattern is something like:

| Sector | Likely α | Why |
| --- | --- | --- |
| Personal services | 0.1–0.3 | Direct H2A/H2H interactions, low coordination overhead |
| Logistics | 0.4–0.7 | Routing optimization is intermediation by nature |
| Finance | 0.8–0.95 | Already striated; agents add depth, not novelty |
| Information / attention | 0.85–0.99 | Each impression is fractally re-priced; attention is the case study for Bratton's hypothesis |
| Healthcare | 0.3–0.6 | Outcome-aligned negotiation pulls smooth; insurance pushes striated |
| Energy | 0.2–0.5 | Spot pricing is smooth; capacity contracts are striated |
| Public goods | 0.05–0.4 | Coasean clearance dominates; folding opportunities are limited |

Hemispherical stacks compound this. A Chinese finance stack and a North-Atlantic finance stack may sit at different α values for reasons that are political rather than technical.

The model supports per-sector and per-stack α (via the topology), and all 15 scenarios use one or another non-trivial slice of the parameter space.

---

## The thermostat

Krier ends his essay with the image of governance as *thermostat* rather than *statute*. Both attractors give us thermostats, but they read different temperatures:

- **Smoothworld thermostat** reads *welfare* and adjusts via direct bargaining.
- **Baroqueworld thermostat** reads *protocol activity* (transactions per second per substrate) and adjusts via fee/incentive design.

A society that aspires to keep humans at the center of its economic feedback loops needs the first kind. A society that has already accepted that the economy is now an agent-layer phenomenon needs the second.

The artifact is built around the suspicion that we will, by default, drift toward the second — because folding is much easier to *measure* than welfare, and what gets measured drives policy.

---

## References

- Deleuze, G. & Guattari, F. (1980). *A Thousand Plateaus*, Chapter 14: *1440: The Smooth and the Striated*.
- Bratton, B. (2026). *Agentworld* research brief, Antikythera (forthcoming).
- Bratton, B. (2026). Telegram correspondence with Marek Poliks, April 21.
- Krier, S. (2025). *Coasean Bargaining at Scale*, AI Policy Perspectives, Sept 29.
- Tomašev et al. (2025). *Virtual Agent Economy*, arXiv:2509.10147.

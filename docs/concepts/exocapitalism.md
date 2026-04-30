# Exocapitalism — Lift, Drag, Last Mile, Differential

> *"Exocapitalism is what capital looks like when you stop treating it as a system addressed primarily to human beings… an instruction set nested inside abstraction itself, and any sufficiently capable substrate (a market, a model, a state, a corporation, a clearinghouse, a piece of code) will eventually find and execute it."* — Poliks & Trillo, *Exocapitalism* (2025)

The α-engine treats the smooth/striated continuum as a single dial and `EBI = nominal / real` as a clean diagnostic. The Poliks/Trillo position will not let either of those moves stand. The exo-engine (`engine/exo/`) is the second engine that we built to take the exocapitalist objection seriously.

This document explains what changed and why.

---

## What the exo position adds to the model

### 1. Lift is the default, not a parameter

In the α-engine, folding propensity scales with `α^1.4`. At low α the system is smooth; at high α it folds. This treats the choice between disintermediation and recursive intermediation as if it were a free parameter.

The exo-engine treats lift as the **basic operating logic**. There is no value of α at which lift stops; there are only values at which it is locally suppressed. The Stack module (`engine/exo/stack.py`) integrates a fractal lift cascade across `K` abstraction layers each step, with a depth-decaying propensity. Capital is always climbing.

### 2. Drag is its own operator, not a derived friction

The α-engine treats coordination overhead as a friction term. The exo-engine names it: **drag** is the manual labor (states, brokers, regulators, white-collar work) of opening legible surfaces for capital to touch. It is paid for in real welfare, and it produces *legibility tokens* that increase the local lift propensity. Drag is a mode of production, not a tax.

The `coasean_dampener` parameter encodes a separate exo claim: deploying Coasean agents at scale can produce drag without enabling lift — the agent layer simulating agency without changing the underlying dynamics. The `anxiety_dampener` scenario tests this directly.

### 3. The last mile is bounded but not privileged

The α-engine privileges "real welfare" as the denominator of EBI, implicitly treating last-mile activity as the only real economic activity. The Poliks/Trillo position rejects this: the last mile is one zone among others, no more "real" than the lifted layers — only **more bounded**, because physical capacity has a hard ceiling that nominal value at higher layers does not.

`engine/exo/last_mile.py` implements this distinction. Last-mile production is bounded by physical capacity. Stochastic gore-layer violence destroys real welfare without producing nominal value. The wedge between last-mile producer and last-mile consumer widens with drag intensity.

### 4. Markets are endogenous

The α-engine spawns sub-markets through the folding operator with a fixed propensity. The exo-engine treats new market creation as **endogenous to ontological variance**. New markets emerge wherever ontological difference exists and is not actively suppressed.

Suppression is not free. The cost of universal differential suppression rises convexly toward the limit (`combine_state` scenario): you cannot get to a flat decisional space without enormous political infrastructure. And the more aggressively a region suppresses, the lower its variance, but variance never goes to zero, because new markets reopen niches.

### 5. Empire is a third topology, non-coextensive with capital and polity

The first version of the exo-engine modeled capital as a single instruction set running across regions identified one-to-one with polities. The Poliks/Trillo position is that this still concedes too much to the nation-state framing. Empire is a *separate* planetary attractor:

> Empire is a really highly-scaled problem... you see these geological attractors (resources, terrain, water access, climate) that almost seem to consolidate and order imperial activity over millennia. Nation-states for us live "within" those pre-inscribed imperial tracts.

`engine/exo/imperial.py` adds **imperial tracts** as a third topology layer. There are fewer tracts than polities (default 4 vs 12); tracts persist over the whole simulation; many polities map to one tract. Each tract has a `resource_endowment` (multiplies last-mile capacity), an `attractor_strength` (pulls high-layer capital), a `violence_floor` (chronic gore-layer baseline inversely correlated with endowment), and an `extraction_intensity` (per-step rate at which last-mile real welfare flows upward into the lifted economy). Capital pools by tract independently of polity-level cross-region compatibility — so a balkanized polity world can still see capital concentrate by tract.

Three new scenarios — `imperial_inheritance`, `last_mile_extracted`, `tract_realignment` — exercise the imperial layer; a 42-point `extraction × pooling` sweep characterizes its basin structure. See `docs/concepts/empire.md` for the full account.

### 6. The Coasean dampener is adaptive

The first version of the `anxiety_dampener` scenario set the dampener level by a fixed schedule. The exo-position-as-test wanted feedback: *agents recruited as palliative care* — deployed in proportion to visible meatspace suffering, not as coordination. The dampener now rises in each polity as that polity's per-capita welfare drops below a target, with institutional inertia. See `docs/concepts/adaptive_dampener.md` for the full account, including the empirical finding that adaptive dampener under-performs static dampener (palliative care chases the loss it absorbs).

### 7. ExoCirculationIndex replaces EBI

EBI privileges the last mile as denominator. The exo-engine reports `ExoCirculationIndex = cumulative_lift / cumulative_real_produced`, which is structurally similar but conceptually neutral: it asks how much circulation has happened in the lifted economy per unit of last-mile throughput, without claiming that the last-mile throughput is the "real" referent.

Alongside that, the engine reports:

- `ReferentDistance` — weighted-mean abstraction layer of nominal value (how high in the fold most activity sits)
- `LastMileWedge` — price faced at consumption / cost paid at production
- `DragCoefficient` — drag intensity, mean across regions
- `SuppressionCoefficient` — realized differential suppression
- `DifferentialProductivity` — new markets per step per unit of variance
- `ScavengeIntensity` — gore-layer violence loss / real produced
- `HemisphericalEntropy` — Shannon entropy of nominal value across regions
- `DeepestActiveLayer` — the deepest fold layer with material activity this step

These are **vectors of stylized facts** rather than a single legibility number. The exo position is that the legibility framing was already capitulating to the state's bookkeeping problem.

---

## Mapping between the two engines

| α-engine concept | Exo-engine equivalent / refusal |
|---|---|
| `α` (smooth/striated dial) | drag intensity × suppression strength |
| Folding propensity | base lift propensity (with depth decay) |
| Folding branching | `fractal_branching` parameter |
| Fold max depth | `n_layers` of the abstraction Stack |
| Coasean Paradise | high-suppression corner; convex welfare cost |
| Baroque Cathedral | `fold_cathedral` (default exo regime) |
| Slop Market | high-drag low-capacity regime |
| Smoothworld | fantasy that requires "Combine State" infrastructure |
| EBI = nominal / real | refused; replaced with vector of metrics |
| "Real welfare" | one bounded zone among others |
| Hemispherical Stacks | low cross-region compatibility |
| Synthetic Consumers | high lift propensity, low drag |
| NIMBY Cascade | suppression ≈ 0.5, drag elevated |
| Compute Famine | last-mile capacity schedule decay |
| Geopolitical region | polity ⊆ imperial tract (non-coextensive) |
| World-system extraction | `imperial.extraction_rate` |
| Reserve currency / financial capital | `imperial.attractor_strength` |
| Conflict zones / sacrifice zones | tracts with low endowment, high violence floor |

The exo-engine therefore does **not replace** the α-engine. It contests it. We keep both running, and the canvas reports them side by side.

---

## What the exo runs show

After running all eight exo scenarios at production scale (80 steps, 12 regions, 8 abstraction layers):

| Scenario | ExoCirc | LiftTop | RefDist | Drag | Supp | RealProd | Cum mkts | Wedge | Scav |
|---|---|---|---|---|---|---|---|---|---|
| `pure_lift` | 260,583 | 2.16M | 8.57 | 0.09 | 0.04 | 1.02 | 207 | 16.1 | 0.017 |
| `last_mile_revolt` | 10,995 | 158k | 6.73 | 0.45 | 0.30 | 0.34 | 204 | 28.3 | 0.049 |
| `scavenger_republic` | 8,619 | 86k | 6.72 | 0.18 | 0.05 | 0.91 | 268 | 17.9 | 0.113 |
| `hemispherical_split` | 7,977 | 70k | 6.72 | 0.40 | 0.25 | 0.93 | 263 | 22.7 | 0.020 |
| `fold_cathedral` | 7,813 | 86k | 6.74 | 0.40 | 0.19 | 1.00 | 210 | 19.4 | 0.014 |
| `drag_saturation` | 5,708 | 65k | 6.75 | 0.88 | 0.44 | 0.96 | 166 | 29.8 | 0.022 |
| `anxiety_dampener` | 4,731 | 20k | 6.59 | 0.61 | 0.40 | 0.99 | 190 | 28.9 | 0.016 |
| `combine_state` | 3,126 | 11k | 6.47 | 0.60 | 0.92 | 1.00 | 141 | 76.4 | 0.021 |

A few things stand out.

**Pure lift produces a circulation index 30–80x higher than every regime that involves any suppression at all.** The asymptote is genuinely runaway. This is what the model says about Bratton's "where do the on-paper GDP gains come from?" — they come from giving lift its head.

**Combine state suppresses the lift cascade but at the highest welfare cost per unit of suppression**, and crucially produces a *LastMileWedge of 76.4* — by far the highest. Universal suppression doesn't equalize the meatspace economy; it concentrates rent at the consumption interface, because the lifted economy is squeezed and the wedge has to make up for it.

**Anxiety dampener nearly halves circulation versus drag saturation**, even though drag intensity is similar. The dampener tokens really do consume welfare without enabling lift. The exo claim that scaled Coasean agents may function as anxiety dampeners is, in this model, *consistent with the dynamics*.

**Scavenger republic has the highest scavenge intensity (0.113)** but lift continues at near-baseline circulation. The exo claim — that capital does not depend on state-organized legibility — gets confirmation from the model.

**Last-mile revolt has the second-highest exo circulation despite collapsed real production**. That is the point: the lifted economy, once tall, decouples from the material substrate enough that a 65% loss of physical capacity does not bring it down proportionately. The wedge widens (28.3) and gore-layer violence (0.049) rises.

---

## What the exo phase-space sweep shows

The drag × suppression sweep (`engine/exo/sweep.py`, 42 points) returns:

| Basin | Count |
|---|---|
| fold (default) | 21 |
| suppressed | 14 |
| saturated | 5 |
| asymptotic | 1 |
| mixed | 1 |

The fold basin is exactly half of the sampled parameter space. Suppression takes another third — but only at very high suppression values (≥ 0.7), because below that the system stays in fold. The asymptotic corner (low drag, low suppression) appears only at the lowest sampled drag.

The basin map confirms what the named scenarios suggest: **fold is what the system does in the absence of effort**. Krier's smoothing requires getting drag low enough that lift surfaces don't open *and* getting suppression high enough that new markets don't spawn. The intersection is small and welfare-expensive.

---

## What the exo position changes about the brief

The exo-engine doesn't claim Bratton or Krier are wrong. It changes the framing of the question.

- **Bratton's "where do the on-paper gains come from?"** — the exo-engine answers: from lift, which is happening continuously across an unbounded number of layers, fueled by drag. The fold is not a parameter setting; it is what capital *does*.
- **Krier's "Coasean bargaining at scale"** — the exo-engine doesn't refuse it, but reframes it as a *suppression program* rather than a coordination program. To get to the Coasean limit you have to spend real welfare suppressing differentials, and you have to keep spending. The agent layer might be the medium through which that suppression runs, or it might be a coping mechanism that simulates suppression without delivering it (the anxiety-dampener scenario).
- **The smooth/striated framing** — the exo position is that this misnames the variable. The variable is not where you sit on a continuum; it is **whether you are willing to absorb the convex cost of holding capital still**. Most regimes, most of the time, are not.

The two engines together are a stronger artifact than either alone. The α-engine gives the brief its scenario atlas and its shareable headline numbers. The exo-engine contests those numbers' framing and supplies the alternative vocabulary the artifact's own conceptual companions (Wark, Malabou, Fazi, Land) would actually use.

---

## References

- Poliks, M. & Trillo, R. A. (2025). *Exocapitalism*.
- Poliks, M. & Trillo, R. A. (2025). Interview with 邊界_RG (Biānjiè Research Group).
- Poliks, M. (2026, draft). "What is Exocapitalism?" The Catalyst.
- Bratton, B. (2026, forthcoming). *Agentworld* research brief, Antikythera.
- Krier, S. (2025). *Coasean Bargaining at Scale*.
- Tomašev, N. et al. (2025). *Virtual Agent Economy.* arXiv:2509.10147.
- Deleuze, G. (1988). *The Fold: Leibniz and the Baroque.*
- Wark, M. *A Hacker Manifesto*; *Capital is Dead*.
- Malabou, C. *Stop Thief: Anarchism and Philosophy*.
- Fazi, M. B. *Contingent Computation*.

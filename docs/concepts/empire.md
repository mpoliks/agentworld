# Empire as a planetary attractor

## The problem

The exo-engine's first version modeled capital as a single instruction set
spread across regions, with regions identified one-to-one with polities
(nation-states). The Poliks/Trillo position from the Biānjiè interview
treats this as a category error:

> Empire is a really highly-scaled problem, it doesn't really go away. If
> you look at historical maps... you see these geological attractors
> (resources, terrain, water access, climate) that almost seem to
> consolidate and order imperial activity over millennia. Nation-states
> for us live "within" those pre-inscribed imperial tracts and are
> constantly negotiating that upstream relationship.

> What states increasingly manage is not populations or economies, but
> the passive production and retrospective consumption of violence
> (policing, containment, insurance, remediation) — activities that
> operate downstream from capital without ever touching its mechanisms.

The exo-engine is now extended with a **third topology layer**: imperial
tracts. Tracts are *non-coextensive* with polities; many polities map
into one tract; tracts persist over the whole simulation; capital and
violence pool by tract independently of polity-level governance choices.

## The model

`engine/exo/imperial.py` introduces `ImperialState`, a per-tract record
of:

- `polity_to_tract`: which tract each polity belongs to (random at
  build time; many-to-one)
- `resource_endowment`: per-tract Dirichlet-drawn multiplier on last-mile
  capacity. Polities in resource-poor tracts produce less material
  throughput regardless of their domestic policy.
- `attractor_strength`: per-tract Dirichlet-drawn weight that pulls
  high-layer capital. *Not aligned with resource endowment by design* —
  the Niger / Congo / coltan pattern: small tracts that pool capital
  out of proportion to their material base.
- `violence_floor`: per-tract chronic gore-layer violence baseline,
  inversely correlated with resource endowment. Tracts with poor
  endowment carry historical violence forward as a floor for the
  stochastic gore-layer process.
- `extraction_intensity`: per-tract per-step rate at which last-mile
  real welfare is extracted upward into the lifted economy.

Per step, the world loop now does the following with imperial state:

1. **Capacity overlay.** Last-mile capacity per polity is multiplied by
   the polity's tract's `resource_endowment`.
2. **Violence overlay.** Gore-layer violence baseline is taken from the
   tract, then jittered as before.
3. **Extraction.** A fraction `tract.extraction_intensity ×
   schedule_multiplier` of last-mile real welfare per polity is removed
   *before* it hits the stack's real account, and added as nominal value
   at `cfg.imperial.extraction_destination_layer` (default = 4) for that
   same polity. The extracted value enters the lifted economy as the
   polity's nominal trade balance. The polity loses real welfare; its
   nominal economy at high layers grows.
4. **Capital pooling.** After the per-step lift cascade and polity-level
   cross-region flow, the top `cfg.imperial.pool_layers` (default = 3)
   layers of nominal value are partially pooled into a global pot and
   redistributed across tracts proportional to `attractor_strength`.
   Within each tract, polities receive the new total in proportion to
   their prior share. *This pooling is independent of cross-region
   compatibility*, so a balkanized polity world can still see capital
   concentrate by tract.

## Diagnostics

Three new metrics report on the imperial layer:

- `imperial_extraction_total`: cumulative real welfare extracted per run.
- `imperial_capital_concentration`: Gini coefficient of cumulative
  pooled capital across tracts. Approaches 1 when one tract dominates.
- `imperial_polity_alignment`: fraction of polities whose real welfare
  is at or above the median of their tract. Approaches 0 when the
  median polity is being net-extracted by its tract.

## Phase-space sweep

`engine/exo/sweep.py::run_imperial_sweep` sweeps
`extraction_rate ∈ [0, 0.30]` × `capital_pooling_strength ∈ [0, 0.50]`
on a 7×6 grid (42 points). The basin classifier:

- **inert**: extraction near zero AND pooling near zero
- **extractive**: extraction high, pooling low (siphon without
  consolidation — colonial extraction without imperial form)
- **pooled**: pooling high, extraction low (consolidation without siphon —
  finance capitals without resource colonies)
- **imperial**: both high (the named-empire corner)
- **drained**: extraction so high that last-mile collapses
- **mixed**: anything else

A representative run produces:

| basin       | count |
|-------------|-------|
| imperial    | 14    |
| extractive  | 12    |
| pooled      |  8    |
| drained     |  3    |
| mixed       |  3    |
| inert       |  2    |

Most of the parameter space is some flavour of "imperial" — the model
*has to be tuned* to escape it. This is the exo claim's quantitative
counterpart: imperial geography is the default, not the perturbation.

## Calibrated scenarios

Three new scenarios exercise the imperial layer specifically:

- `imperial_inheritance`: extreme tract heterogeneity (Dirichlet α=0.7 on
  both endowment and attractor). Tests the case where capital and
  polity are maximally non-coextensive. Terminal: high capital
  concentration (Gini ≈ 0.76), low polity-tract alignment.

- `last_mile_extracted`: extraction rate set to 18%. Tests the case
  where ordinary polities sit on top of an active extractive layer
  without legislating it. Terminal: ECI rises to ≈ 30k as extracted
  real welfare cascades through the lift layers.

- `tract_realignment`: `attractor_schedule` flips attractor strengths
  at step 30 and again at step 55, modeling resource discovery,
  climate-shifted resource viability, or AI-hardware concentration.
  Tests whether capital follows the new attractor map and whether
  polities aligned with the *old* tract get stranded. Terminal:
  reorganization is observable in the tract Gini trajectory.

## What this commits the model to

The imperial layer makes three theoretical commitments:

1. Capital does not pool only along polity-level cross-region
   compatibility. There is a second pooling mechanism, *uncoupled* from
   trade-policy compatibility, that operates over a smaller number of
   geological / resource attractors.
2. Last-mile production is partly determined by attractor-tract resource
   endowment, not just by polity-level capacity policy.
3. State-managed violence is not the only violence; tracts carry a
   chronic violence floor that polities cannot legislate away.

The first two commitments echo the Poliks/Trillo position that empire is
upstream of nation-state. The third operationalizes the "passive
production / retrospective consumption of violence" passage: the
gore-layer floor exists whether or not any polity authored it.

## Reading order

For interpretation: this concept doc, then `docs/concepts/exocapitalism.md`
for the Lift/Drag/Last-Mile/Differential ontology that the imperial layer
sits inside, then `docs/concepts/phase_space.md` for the α-engine's
phase structure that the imperial sweep is the exo analogue of.

For code: `engine/exo/imperial.py` (≈ 200 lines) for the state and
operators, then `engine/exo/world.py` for the wiring.

# Compute and Power as Economic Constraint

> *"AI's projected electricity demand growth will be equivalent to
> adding another country the size of Sweden to the global grid by
> 2030."* — IEA, *Electricity 2024.*

The current engine treats compute and power as free. Every prototype
can attempt every potential trade up to the global `pairs_per_step`
cap; no agent ever "runs out" of compute, and no transaction debits
any energy from a shared pool. This is realistic for the 2025 limit
where compute is abundant relative to the size of the agent population.
It will not stay realistic. By 2030, IEA projections put AI compute on
the same order of magnitude as the electricity load of medium-sized
nations, and the question of who can afford to run agents at what
rate becomes a binding economic constraint.

This doc surveys the literature on compute and power as economic
inputs and proposes a `ComputeConfig` subsystem that makes the
constraint operational in agentworld. The subsystem is the
"environmental" lever category the user named in the spatial sandbox
brief.

---

## What the literature names

Three streams of research are load-bearing for the engine design.

### Compute as a measured economic input

Cottier and others at Epoch AI have published the most systematic
work on compute as an economic input to AI development. The Cottier
2024 line of analysis treats training compute as a measured factor of
production: cost per FLOP, scaling laws of capability vs. compute,
distribution of compute across labs. The implication for an a2a
economy: capability is bounded above by available compute, and the
marginal cost of one more agent inference is non-zero.

### Energy as a sustainability bind

Strubell, Ganesh & McCallum (2019) put the first published numbers
on the carbon cost of NLP training. Patterson et al. (2021) extended
the accounting to inference. Crawford's *Atlas of AI* (2021) traces
the energy supply chains. de Vries (2023) projected AI inference
energy demand under the assumption that ChatGPT-scale usage
generalizes. Verdegem (2024) surveys the policy implications.

The shared claim: AI is a meaningful share of electricity load, and
agent populations at the scales the engine models (88K to 88M agents
running ~200 trades per tick) cannot be powered as a free resource at
2030 grid capacity. Power becomes a rationed input.

### Compute distribution as a political question

Bender et al. (2021) make the equity argument: when compute is
rationed, the rationing rule is a political choice. Uniform-per-agent
distribution favors the long tail. Wealth-weighted distribution
favors incumbents and accelerates concentration. Capability-weighted
distribution rewards capability and produces a different concentration
dynamic. The choice is not technical.

The agentworld lever is exactly this: `ComputeConfig.distribution`.

---

## What the existing engine has, what it lacks

The engine has one knob in this territory.

`pairs_per_step` in `WorldConfig` (visible in
`engine/core/world.py`) caps the global number of pair-encounters
per tick. This is a compute proxy: more pairs = more compute.
Existing scenario sweeps treat it as a Sobol-ranked parameter
(low-importance, but real). It does the job of an aggregate compute
budget at the system level.

What it lacks:

- **Per-trade cost.** All pairs in a tick pay the same admission;
  there is no per-trade compute debit.
- **Distribution rule.** All eligible pairs are sampled uniformly
  (or via `network_p_local` weighting); no allocation by agent
  attribute.
- **Pool dynamics.** No depletion-and-refill behavior across
  ticks; the budget resets every tick.
- **Compute-reject filter.** No Matryoshka-style filter for
  insufficient-compute admission failures.

The proposed `ComputeConfig` fills all four gaps.

---

## The proposed `ComputeConfig` subsystem

The "build + repurpose" principle applies. `ComputeConfig` is a new
top-level config in the `WorldConfig` hierarchy that wraps and
extends `pairs_per_step`, not a replacement.

```python
@dataclass
class ComputeConfig:
    enabled: bool = False

    # Aggregate budget per tick, in "compute units". Default 1.0 = the
    # current pairs_per_step cap. < 1.0 = scarcity regime.
    budget_per_tick: float = 1.0

    # Per-trade compute cost. Trades draw from the budget. Default 0
    # preserves current behavior (every pair admitted up to pairs_per_step).
    power_cost_per_trade: float = 0.0

    # Distribution rule for which pairs get admitted when budget runs out.
    # uniform: random subset
    # wealth_weighted: probability ∝ max(wealth_a, wealth_b)
    # capability_weighted: probability ∝ max(capability_a, capability_b)
    # autonomy_weighted: probability ∝ max(autonomy_a, autonomy_b)
    distribution: str = "uniform"

    # Optional pool dynamics: fraction of unused budget that carries
    # over to the next tick. 0 = no carryover (current behavior).
    pool_recovery: float = 0.0

    # Floor below which the budget does not drop, regardless of cost.
    scarcity_floor: float = 0.0
```

The new engine path inside `coasean_step`:

1. Compute `admit_score[i]` for each candidate pair using the
   distribution rule.
2. Sort pairs by `admit_score` descending.
3. Walk down the list, debiting `power_cost_per_trade` from the
   tick's budget for each admitted pair.
4. Stop when budget is exhausted; remaining pairs are
   `compute_reject`-filtered.
5. Roll unused budget forward by `pool_recovery × residual`.

A new field `compute_reject_rate` joins the rejection-mix in
`StepMetrics`, alongside `cost_reject`, `market_reject`,
`align_reject`, `law_reject`.

The implementation lives in a new file `engine/core/compute.py` and
hooks into `engine/core/transactions.py` at the pair-admission step.

---

## What this lets the user explore

Five questions the current engine cannot answer.

### 1. Does compute scarcity push α up or down?

The conjecture: scarcity pushes α up. When compute is rationed, the
remaining trades are the highest-value-per-compute, which the
folding-pressure mechanisms in `docs/concepts/fractal_folding.md`
predict are intermediation rather than direct trade. The sandbox
runs the experiment.

### 2. Who survives a power cut?

Drop `budget_per_tick` from 1.0 to 0.3 over 30 ticks. Watch which
agents stop transacting first. Under `distribution = uniform`, the
attrition is random. Under `wealth_weighted`, the long tail of
poor agents starves first. Under `capability_weighted`, low-capability
humans starve first. Under `autonomy_weighted`, the most autonomous
A2A agents survive and humans starve hardest.

This is the *operational* form of Crawford's energy-supply-chain
argument: who gets the compute is who keeps participating in the
economy.

### 3. Does pool recovery produce business cycles?

Set `pool_recovery = 0.5` and run with a slowly drifting
`budget_per_tick`. The conjecture: the pool oscillates around its
mean and produces visible boom/bust waves in transaction volume.
Cross-reference with `docs/concepts/recursive_simulation` (if it
exists) for the sigmoid take-off pattern.

### 4. Can a Pigouvian tax substitute for a compute price?

Compare two regimes with identical welfare per agent:

- High `pigouvian.tax_rate`, free compute.
- Zero Pigouvian, high `power_cost_per_trade` charged to
  the surplus.

The two regimes look identical in welfare but produce different Gini
profiles. The Pigouvian tax recycles to humans by design;
power-cost is captured by the substrate (whoever owns the compute).
This is the Bratton "power flows to the substrate" observation in
`docs/concepts/coasean_bargaining.md` made operational.

### 5. Does a guaranteed floor produce a different equilibrium than zero floor?

The `scarcity_floor` parameter implements a compute commons: every
agent gets at least the floor regardless of distribution rule. The
question is whether the floor stabilizes the population at a
sustainable equilibrium or just delays the same concentration
trajectory.

---

## What this means for the engine

| Change | Path | Cost |
| --- | --- | --- |
| New file `engine/core/compute.py` with the admission logic | new file | ~120 lines |
| `ComputeConfig` dataclass | `engine/core/topology.py` after `RegulatorConfig` | ~25 lines |
| Hook into `coasean_step` pair admission | `engine/core/transactions.py` (look for the candidate-pair sampling block) | ~15 lines |
| New `compute_reject_rate` field on `StepMetrics` | `engine/core/world.py` | ~5 lines |
| Surface per-tick budget remaining in `cast_snapshot_v2` | `engine/core/world.py` snapshot assembler | ~2 lines |
| Two new scenarios bracketing the axis (`compute_abundant`, `compute_scarce`) | `engine/scenarios/__init__.py` | ~40 lines |

`ComputeConfig.enabled = False` is the default. Existing canonical
runs, the Sobol baseline, and the pinned scenario suite see no
behavior change.

The sandbox's environmental lever panel surfaces:
- **Budget** — `ComputeConfig.budget_per_tick`
- **Cost per trade** — `ComputeConfig.power_cost_per_trade`
- **Distribution** — radio over the four options
- **Pool recovery** — `ComputeConfig.pool_recovery`
- **Scarcity floor** — `ComputeConfig.scarcity_floor`

Five controls in the environmental panel. The sandbox plan budgets
~5 days of engine work for `ComputeConfig` in the early weeks.

---

## What this does not model

Three gaps to name explicitly.

1. **No regional compute markets.** Compute is a single global pool.
   In reality, compute is geographically distributed and traded across
   regions with friction. A two-stack version of `ComputeConfig`
   would split the budget by stack, but that doubles the parameter
   count and is left for V2.
2. **No compute hoarding.** Agents cannot accumulate unused compute
   for future trades. `pool_recovery` is a system-level parameter,
   not a per-agent stockpile. Strategic compute reserves are an
   interesting extension but require per-agent state that the engine
   does not currently maintain.
3. **No compute price discovery.** The cost per trade is set by the
   user, not negotiated. A market for compute (agents bid for
   capacity, prices float) is a substantial new subsystem and is out
   of scope.

---

## Epistemic status

All `ComputeConfig` parameters are **speculative** in the sense of
`docs/concepts/epistemic_status.md`. There is no empirical anchor for
the cost rates, distribution rules, or pool recovery dynamics at the
agent-economy scale the engine models. The subsystem is a structural
experiment, not a calibrated forecast.

---

## References

- IEA. (2024). *Electricity 2024: Analysis and forecast to 2026.*
- Cottier, B., et al. (2024). *The Rising Costs of Training Frontier
  AI Models.* Epoch AI.
- Strubell, E., Ganesh, A., & McCallum, A. (2019). *Energy and Policy
  Considerations for Deep Learning in NLP.* ACL.
- Patterson, D., et al. (2021). *Carbon Emissions and Large Neural
  Network Training.* arXiv:2104.10350.
- Crawford, K. (2021). *Atlas of AI: Power, Politics, and the Planetary
  Costs of Artificial Intelligence.* Yale.
- de Vries, A. (2023). *The growing energy footprint of artificial
  intelligence.* Joule.
- Bender, E. M., Gebru, T., McMillan-Major, A., & Shmitchell, S.
  (2021). *On the Dangers of Stochastic Parrots: Can Language Models
  Be Too Big?* FAccT.
- Verdegem, P. (2024). *Dismantling AI Capitalism.* Routledge.
- `docs/concepts/coasean_bargaining.md` — the "power flows to the
  substrate" claim that compute pricing makes operational.
- `docs/concepts/pigouvian_automation.md` — the adjacent revenue
  channel that compute pricing competes with.

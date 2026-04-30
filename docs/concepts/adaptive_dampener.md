# Adaptive Coasean dampener

## The question

The Krier "Coasean Bargaining at Scale" position is that abundant agentic
labor at low cost permits Coasean negotiation everywhere, internalizing
externalities and making the social welfare gap close. The exo position
treats this as a hypothesis that can be diagnosed in the model: either
Coasean agents *help* (close the welfare gap, reduce drag) or they
*simulate help* (consume drag without enabling lift, dampening the
appearance of distress).

The first version of the `anxiety_dampener` scenario set the dampener
level by a fixed schedule: pre-step 15, dampener = 0; ramp to 0.7 by step
35; hold at 0.7 thereafter. That tested the static case but not the
feedback case the theory actually claims.

## The adaptive operator

The new operator (`engine/exo/drag.py::adaptive_dampener_update`)
recomputes the dampener each step from local welfare:

```
per_capita_real[i] = real[i] / region_size[i]
welfare_gap[i]      = max(0, target - per_capita_real[i]) / target
target_dampener[i]  = sensitivity × welfare_gap[i]
target_dampener[i]  = max(target_dampener[i], baseline_dampener)
target_dampener[i]  = clip(target_dampener[i], 0, max_dampener)
new_dampener[i]     = inertia × prior_dampener[i] + (1−inertia) × target_dampener[i]
```

So the dampener level rises in each polity *as that polity's per-capita
welfare drops below a target*. The dampener is per-polity, not global —
imperial extraction can drain certain polities while others sit at the
floor. `inertia` mimics institutional ramp-up time (deploying agents,
contracting providers, building the dampener apparatus).

The mechanism the dampener implements is unchanged:
`productive_tokens = intensity × (1 − dampener)` and
`suppression_tokens = intensity × dampener`. So a high dampener level
*redirects drag away from lift-surface production into pure suppression*.
This is the operationalization of Coasean-as-coping: the agentic labor is
real, the cost is real, and yet the lift surface does not grow.

## The adaptive scenario

`scenarios.anxiety_dampener` is now configured as:

```python
DragConfig(
    target_intensity=0.60,
    coasean_dampener=0.05,           # static floor
    adaptive_dampener=True,
    adaptive_welfare_target=0.55,
    adaptive_dampener_sensitivity=1.6,
    adaptive_dampener_max=0.85,
    adaptive_dampener_inertia=0.72,
)
```

with imperial extraction enabled at default rates so that the dampener
has real-side pressure to respond to.

## Empirical finding

A 3-way comparison at 80 steps (n_regions=12):

| condition                       | terminal real_balance | terminal ECI | dampener_max |
|---------------------------------|-----------------------|--------------|--------------|
| **adaptive (default scenario)** | 0.387                 | 10,409       | 0.85         |
| no dampener (counterfactual)    | 0.361                 | 11,385       | 0.00         |
| static @ 0.5 (counterfactual)   | 0.526                 |  9,411       | 0.50         |

Three readings:

1. **The adaptive dampener is not a no-op.** Compared to the no-dampener
   case, real_balance is higher and ECI is lower — drag is being diverted
   into suppression rather than producing lift surfaces. The mechanism
   works.
2. **The adaptive dampener under-performs the static dampener.** Static
   @ 0.5 is meaningfully better than adaptive on real_balance (0.526 vs
   0.387). The reason is hysteretic: the adaptive dampener climbs only
   *after* welfare has dropped, by which time the welfare hole is
   already large and the institutional ramp-up time prevents fast
   recovery. Adaptive palliative care chases the loss it is meant to
   absorb.
3. **The dampener saturates locally.** `dampener_max` reaches the cap of
   0.85 in the adaptive case while `dampener_mean` stays around 0.35.
   That means the system polarizes: some polities are operating at full
   palliative-care intensity while others are not deploying it at all.
   This is consistent with the imperial-extraction gradient — the most
   extracted polities are the ones whose dampener saturates.

The exo claim being tested in the original is *partly* borne out:
recruited-as-palliative-care behaviour is observable, the dampener
saturates locally, and capital circulation continues climbing in the
background while welfare stagnates. But the second-order finding —
adaptive does *worse* than static — is the specifically dynamical point
that the static-only scenario could not show.

## What this commits the model to

The adaptive operator commits to four assumptions:

1. The decision to deploy palliative agents is a function of *visible*
   distress (welfare below a target), not of total system performance.
2. Deployment lags distress — institutional ramp-up takes steps to
   spool up and steps to spool down (`adaptive_dampener_inertia`).
3. The dampener cap is institutional, not purely material — it represents
   the maximum political feasibility of declaring everyone a recipient
   of palliative agents.
4. The dampener is per-polity. There is no central planetary dampener;
   each polity recruits at its own rate.

These can each be relaxed — a single global dampener is one parameter
change away (replace per-polity per-capita with a global aggregate),
and other operating modes (anticipatory dampener, adversarial dampener)
are easy to implement on top of the same machinery.

# Adversarial scenario — `baroque_with_high_welfare`

## What the search asks

The brief's load-bearing claim is that high intermediation (high EBI) does
not coexist with high welfare. The adversarial search at
[`engine/validation/adversarial.py`](../../engine/validation/adversarial.py)
asks: *under the model's stipulated bounds on speculative folding
parameters, is there a region where terminal EBI > 10 AND terminal
real-per-capita welfare exceeds `coasean_paradise`'s?*

If yes → the brief must adopt the weaker claim "Baroque does not
*monotonically* harm welfare; productive folding can outpace it."

If no  → the brief gets to claim the invariant: "under stipulated bounds,
high folding and high welfare do not coexist."

## How the search works

A custom simulated annealer over eight knobs:

| knob | bound (low) | bound (high) | role |
| --- | --- | --- | --- |
| `alpha` | 0.65 | 0.95 | smooth/striated dial — high pushes toward fold |
| `folding_propensity` | 0.30 | 0.85 | top-of-cascade fold rate |
| `folding_branching` | 2.0 | 4.5 | cascade branching factor |
| `fold_real_efficiency` | 0.50 | 0.96 | per-layer surplus retention |
| `fold_nominal_multiplier` | 1.0 | 3.0 | per-layer nominal multiplication |
| `base_variance_absorption` | 0.10 | 0.60 | productive folding strength at depth 1 |
| `productive_decay` | 0.50 | 0.95 | per-layer productive decay |
| `agent_capability_mean` | 0.55 | 0.92 | intermediating capability |

Geometric temperature schedule from `T0=1.0` to `T1=1e-4`. Step size
shrinks linearly with temperature, with a 2% floor on the bound span so
the chain keeps moving. Runs are deterministic in `seed`.

The objective rewards the *counter-example region* (EBI ≥ 10 AND welfare ≥
paradise): inside it, the score is the welfare margin plus an EBI margin
tiebreaker; outside it, the score is the negative of the gaps to the
two thresholds, normalized so neither axis dominates.

## Result, current vintage (seed=0, n_evals=200)

The canonical artifact at
[`outputs/validation/adversarial_search.json`](../../outputs/validation/adversarial_search.json):

```
found_counter_example: TRUE
best_ebi:              ~147,118
best_welfare:          ~0.277
paradise_welfare:      ~0.265
elapsed_sec:           ~10
```

Best point (4 of 8 knobs at the bound; flagged below):

```
alpha:                       0.9500   ← upper bound
folding_propensity:          0.8500   ← upper bound
folding_branching:           4.5000   ← upper bound
fold_real_efficiency:        0.5281
fold_nominal_multiplier:     3.0000   ← upper bound
base_variance_absorption:    0.2615
productive_decay:            0.7142
agent_capability_mean:       0.8279
```

The scenario `baroque_with_high_welfare` (registered in
[`engine/scenarios/__init__.py`](../../engine/scenarios/__init__.py)) pins
these parameters; running it reproduces the counter-example.

## What this counter-example actually shows

**The mechanism is productive folding plus capable intermediation.** The
search saturates the upper bounds on alpha, folding propensity, branching,
and nominal multiplier — these inflate EBI to absurd levels (~10⁵). The
matching welfare comes from `base_variance_absorption × cap`-gated
productive yield: every fold layer adds welfare proportional to capability
at the upper end of the search range. The cap on
`max_productive_real_share` (0.85 in the scenario) prevents free welfare
*ad infinitum*, but at high alpha the cap binds in nearly every step so
welfare grows at the cap rate.

**Most of the EBI is parasitic; the welfare is from the small productive
share.** This is why the scenario is informative: it tells the brief
that the productive/parasitic split, *not* alpha by itself, is what
determines whether high intermediation harms welfare. The original claim
"Baroque is bad for welfare" survives in *parasitic* baroque scenarios;
it does not survive in *productive* baroque scenarios.

**Several knobs sat at the bound.** In a future tightening pass, the
question to ask is: does the counter-example shrink if the bounds are
contracted toward more historically plausible values? A counter-example
that needs `fold_nominal_multiplier=3.0` and `folding_branching=4.5`
simultaneously is a thinner one than a counter-example at moderate
levels.

## What this counter-example does NOT show

- **It is not at canonical scale.** The search runs at small scale
  (88K-equivalent) for tractability. Welfare is measured against the
  same-scale paradise, so the counter-example is internally consistent;
  it does not yet say anything about the 88M scale where qualitative
  claims usually live.
- **Welfare margin is small.** The counter-example beats paradise by
  ~4%. That is enough to falsify "Baroque cannot match paradise on
  welfare," but not enough to say "Baroque outperforms paradise."
- **The search may have bound-saturation aliasing.** Half the knobs
  hitting the upper bound is a hint that the brief should also report
  results from a contracted-bound run.

## Where this connects to the rest of the brief

- The priors sweep (A2) is the next step: it asks how *likely* the
  counter-example region is under stated parameter uncertainty.
- The historical anchor (A1) does not constrain this scenario directly —
  it only fits the α-schedule, not the folding parameters. Anchor-bound
  runs and the adversarial scenario are siblings, not subsets.
- The exo-engine has an analogous claim at the lift / drag level that
  this artifact does not test.

# Engine — Architecture and Reading Order

The engine is a small, vectorized agent-economy simulator written in Python + NumPy. It is designed to run a 60–80 step scenario in 5–15 seconds on a laptop while statistically representing a population of 8 × 10¹¹ entities.

## Module map

```
engine/
├── core/
│   ├── population.py    # synthesize 10^5 prototypes representing 8 × 10^11
│   ├── topology.py      # smooth/striated topology and friction surface
│   ├── transactions.py  # Coasean bargaining at scale (the smooth engine)
│   ├── folding.py       # fractal market folding (the striated engine)
│   ├── noise.py         # gaussian / t-copula shock generators
│   ├── network.py       # scale_free / SBM adjacency for partner sampling
│   ├── metrics.py       # all output metrics, including Gini and EBI
│   └── world.py         # orchestrates per-step + run loop
├── data/
│   ├── empirical_anchors.py   # BEA, World Bank, Cont, Bacry/Muzy, Atalay
│   └── README.md
├── scenarios/
│   └── __init__.py      # 17 scenario configs + registry (15 + 2 networked)
├── ensemble.py          # N-seed ensembles, bootstrapped 5/95 bands, parquet
├── runner.py            # run a scenario, write JSON
├── cli.py               # `agentworld list / run / run-all / ensemble / sobol`
├── sensitivity.py       # phase-space sweep + Saltelli/Sobol global sensitivity
├── plotting.py          # generate matplotlib figures
└── build_dashboard.py   # bake JSON into self-contained HTML
```

For the rules of which parameters are calibrated vs stipulated vs speculative,
see [`docs/concepts/epistemic_status.md`](../docs/concepts/epistemic_status.md).

## Reading order

If you want to *understand the model*, read in this order:

1. **`core/population.py`** — the substrate. What a "prototype" is. How importance weighting scales 10⁵ samples to 10¹¹ real entities.
2. **`core/topology.py`** — the variable space. The α parameter; how it modulates transaction cost and folding propensity. The Matryoshka layer parameters.
3. **`core/transactions.py`** — the Coasean engine. Per-step bilateral matching, surplus computation, Matryoshka filtering. *This is the smooth attractor.*
4. **`core/folding.py`** — the folding operator. Recursive market spawning. Nominal multiplication. Real-surplus consumption. *This is the striated attractor.*
5. **`core/metrics.py`** — what we measure. EBI, Gini, governance overhead, A2A share, legibility.
6. **`core/world.py`** — the orchestrator. Per-step loop, schedule application.
7. **`scenarios/__init__.py`** — 15 parameterizations.

If you want to *use the model*, the path is:

```python
from engine.scenarios import get_scenario
from engine.core.world import World

cfg = get_scenario("baroque_cathedral")
world = World.build(cfg)
metrics = world.run(progress=True)

import json
print(json.dumps(metrics.history.to_dict()["exo_baroque_index"][-5:]))
```

…or via the CLI:

```bash
agentworld list                    # print scenarios with descriptions
agentworld run coasean_paradise    # run a single scenario, save JSON
agentworld run-all                 # run every scenario
agentworld sweep                   # legacy alpha/capability phase-space grid
agentworld ensemble baroque_cathedral --seeds 64    # N-seed ensemble + bands
agentworld ensemble-all --seeds 32                  # ensembles for every scenario
agentworld sobol --samples 64                       # Saltelli/Sobol global sensitivity
agentworld exo run fold_cathedral                   # exo-engine scenarios
agentworld exo ensemble fold_cathedral --seeds 32   # exo-engine ensembles
agentworld exo sobol --samples 32                   # exo-engine global sensitivity
```

…or via the runner functions if you want all scenarios + then plots + then dashboard:

```bash
PYTHONPATH=. python -c "from engine.runner import run_all; run_all(output_dir=__import__('pathlib').Path('outputs/runs'))"
PYTHONPATH=. python engine/plotting.py
PYTHONPATH=. python engine/build_dashboard.py
```

For a basin-of-attraction view rather than a named-scenario view, run:

```bash
PYTHONPATH=. python engine/sensitivity.py
```

This writes `outputs/sensitivity/phase_space.json`: a compact grid across
`alpha` and agent capability, with each point classified as smooth, mixed,
striated, baroque, or slop. Use it to test whether the 15 scenarios are
representative of the wider phase space rather than isolated storytelling points.

## Performance

A single 60-step run uses ~200,000 prototype-pairs per step. Total ~1.2 × 10⁷ candidate transactions per run. NumPy vectorization keeps this under 5 seconds on an M-series Mac.

For larger sweeps (parameter studies, sensitivity analysis), bump `pairs_per_step` to 500K–1M and `n_human_prototypes` / `n_agent_prototypes` to ~10⁶ each. A full 15-scenario run-all completes in ~80 seconds at default settings.

## Extending

The cleanest extension points:

- **A new scenario**: add a function returning a `WorldConfig` to `engine/scenarios/__init__.py`, register it in `SCENARIOS`. The dashboard will pick it up on the next build.
- **A new metric**: add a field to `StepMetrics` in `core/metrics.py`, compute it in `Metrics.step_metrics`. The dashboard's per-scenario detail will need a manual chart addition; the comparison panel can be told about the new key.
- **A new layer in the Matryoshka**: extend `transactions.py`'s rejection cascade. Add the parameter to `TopologyConfig`. Update tests.
- **Agent learning**: introduce a `capability` update step inside `World.step()` after the transaction phase. Capability could rise/fall based on participation. Be careful — this can dramatically change the dynamics.
- **Spatial dynamics**: replace the well-mixed prototype set with a graph (NetworkX). Interactions are then constrained to graph neighborhoods. Friction changes accordingly.
- **Endogenous α**: let α emerge from collective protocol-design choices. This was the *Recursive Simulation* scenario; a fuller implementation would let agents pay to add or remove protocol layers.

## Tests

A minimal test suite lives in `engine/tests/`. Add tests when:

- introducing a new scenario (smoke-test that it runs without error and the qualitative direction is right);
- changing the transaction or folding kernels (regression-test EBI on the canonical Coasean Paradise and Baroque Cathedral runs).

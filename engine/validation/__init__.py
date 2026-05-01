"""Validation artifacts.

The α-engine has been ~85% engineered and ~15% validated. This package adds
the small set of falsifiable artifacts the plan calls for:

- `historical_anchor`  — stylized US 1980-2024 FIRE-share anchor (A1).
- `priors`             — prior distributions over the speculative parameters (A2).
- `posterior_sweep`    — Sobol-coverage sweep that turns those priors into a
                         distribution of basin classifications (A2).
- `adversarial`        — scenario + simulated-annealing search that tries to
                         break the brief's "Baroque does not coexist with high
                         welfare" claim (A3).

Every artifact is reproducible from a single CLI command and writes to
`outputs/validation/`. None of them retune existing scenario parameters.
"""

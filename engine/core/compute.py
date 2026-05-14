"""Compute-and-power admission filter for the Coasean step.

Implements `ComputeConfig` from `engine/core/topology.py`. The hook
in `engine/core/transactions.py:coasean_step` calls `admit_pairs`
after partner sampling; the result is folded into the rejection
cascade just below the permeability gate and above the law gate.

The admission rule treats `power_cost_per_trade` as a compute-unit
debit from a per-tick budget. Pairs are sorted by an
attribute-dependent `admit_score` (descending) and admitted until the
budget runs out. Unused budget is carried forward by
`pool_recovery × residual` and clamped from below by `scarcity_floor`.

See `docs/research/compute_and_power_as_constraint.md`.
"""
from __future__ import annotations

from typing import Any, Tuple

import numpy as np


def admit_pairs(
    *,
    cfg: Any,
    pop: Any,
    a: np.ndarray,
    b: np.ndarray,
    rng: np.random.Generator,
    available: float,
) -> Tuple[np.ndarray, float]:
    """Return `(compute_reject_mask, debited)`.

    `compute_reject_mask` is True for pairs that the budget could not
    afford. `debited` is the total compute cost charged this call,
    `power_cost_per_trade × n_admitted`. With `power_cost_per_trade
    <= 0` the filter is a no-op: every pair is admitted, debited is 0.
    """
    n_pairs = int(a.size)
    cost = float(getattr(cfg, "power_cost_per_trade", 0.0))
    if cost <= 0.0 or n_pairs == 0:
        return np.zeros(n_pairs, dtype=bool), 0.0

    distribution = str(getattr(cfg, "distribution", "uniform"))
    if distribution == "uniform":
        score = rng.random(n_pairs)
    elif distribution == "wealth_weighted":
        score = np.maximum(pop.wealth[a], pop.wealth[b]).astype(np.float64)
    elif distribution == "capability_weighted":
        score = np.maximum(pop.capability[a], pop.capability[b]).astype(np.float64)
    elif distribution == "autonomy_weighted":
        score = np.maximum(pop.autonomy[a], pop.autonomy[b]).astype(np.float64)
    else:
        raise ValueError(
            f"ComputeConfig.distribution must be one of "
            f"{{'uniform','wealth_weighted','capability_weighted','autonomy_weighted'}}, "
            f"got {distribution!r}"
        )

    n_admit = int(max(0, min(n_pairs, int(available // cost))))
    if n_admit >= n_pairs:
        return np.zeros(n_pairs, dtype=bool), n_pairs * cost

    # Stable sort so ties resolve deterministically given a fixed score.
    order = np.argsort(-score, kind="stable")
    admitted = np.zeros(n_pairs, dtype=bool)
    admitted[order[:n_admit]] = True
    compute_reject = ~admitted
    return compute_reject, n_admit * cost


def step_pool(
    *,
    cfg: Any,
    pool_before: float,
    debited: float,
) -> Tuple[float, float, float]:
    """Advance the per-world compute pool by one tick.

    Returns `(available, residual, pool_after)` where `available` is
    the pool seen by `admit_pairs` this tick, `residual` is what's
    left after debiting, and `pool_after` is the carryover state for
    next tick's `pool_before`.
    """
    floor = float(getattr(cfg, "scarcity_floor", 0.0))
    recovery = float(getattr(cfg, "pool_recovery", 0.0))
    available = max(pool_before + float(getattr(cfg, "budget_per_tick", 1.0)), floor)
    residual = max(0.0, available - debited)
    # Floor is applied at `available`, not on the carryover. With
    # pool_recovery = 0 the next tick's pool_before is zero and the
    # floor still kicks in via `available = max(0 + budget, floor)`.
    pool_after = residual * recovery
    return available, residual, pool_after

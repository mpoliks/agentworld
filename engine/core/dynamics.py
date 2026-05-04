"""Population dynamics: learning, depreciation, and entry/exit."""

from __future__ import annotations

from typing import Any

import numpy as np


def capability_update(
    pop: Any, wealth_delta: np.ndarray, cfg: Any, dt: float = 1.0
) -> None:
    """Update capability from realized surplus and natural decay.

    `cfg.capability_learning_rate` and `cfg.capability_decay_rate` are
    interpreted as per-unit-of-model-time rates; `dt` rescales the per-step
    deltas accordingly. With `dt = 1.0` (default) the math is unchanged.
    """
    dt = float(dt)
    mean_wealth = max(float(pop.wealth.mean()), 1e-6)
    normalized_reward = np.clip(wealth_delta / mean_wealth, -1.0, 1.0)
    pop.capability += np.float32(dt * cfg.capability_learning_rate) * normalized_reward.astype(np.float32)
    pop.capability -= np.float32(dt * cfg.capability_decay_rate)
    np.clip(pop.capability, 0.01, 0.99, out=pop.capability)


def wealth_depreciation(pop: Any, cfg: Any, dt: float = 1.0) -> None:
    """Apply wealth maintenance depreciation over `dt` units of model time.

    Uses the exact continuous-time relation `wealth_after = wealth_before *
    (1 - rate)^dt` so multiple sub-steps compose correctly. With `dt = 1.0`
    (default) this collapses to the original `wealth *= (1 - rate)`.
    """
    rate = float(cfg.wealth_depreciation)
    if rate <= 0.0:
        return
    factor = np.float32((1.0 - rate) ** float(dt))
    pop.wealth *= factor


def entry_exit(pop: Any, cfg: Any, rng: np.random.Generator) -> int:
    """Recycle failed prototypes as new entrants."""
    exit_mask = pop.wealth < cfg.exit_wealth_threshold
    n_exit = int(exit_mask.sum())
    if n_exit == 0:
        return 0

    survivor = ~exit_mask
    survivor_wealth_mean = (
        float(pop.wealth[survivor].mean()) if survivor.any() else cfg.exit_wealth_threshold * 2.0
    )

    pop.capability[exit_mask] = np.clip(
        rng.normal(float(pop.capability.mean()) + cfg.entry_capability_boost, 0.15, n_exit),
        0.01,
        0.99,
    ).astype(np.float32)
    pop.wealth[exit_mask] = rng.lognormal(
        np.log(max(survivor_wealth_mean, 1e-6)),
        0.5,
        n_exit,
    ).astype(np.float32)
    pop.alignment[exit_mask] = np.clip(
        rng.normal(0.0, 0.35, n_exit),
        -1.0,
        1.0,
    ).astype(np.float32)

    if pop.intermediation_pref is not None:
        pop.intermediation_pref[exit_mask] = np.clip(
            rng.normal(0.5, 0.15, n_exit),
            0.01,
            0.99,
        ).astype(np.float32)
        pop.bandit_rewards[exit_mask] = 0.0
        pop.bandit_counts[exit_mask] = 1
        pop.last_action[exit_mask] = -1
    if pop.firm_id is not None:
        pop.firm_id[exit_mask] = -1
    return n_exit

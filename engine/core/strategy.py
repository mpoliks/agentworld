"""Vectorized strategy learning for endogenous intermediation preference."""

from __future__ import annotations

import numpy as np


def select_actions(
    bandit_rewards: np.ndarray,
    bandit_counts: np.ndarray,
    epsilon: float,
    rng: np.random.Generator,
) -> np.ndarray:
    """Epsilon-greedy action selection. Returns int8 actions in {0, 1, 2}."""
    del bandit_counts  # Counts are maintained for diagnostics/future UCB variants.
    n = bandit_rewards.shape[0]
    greedy = np.argmax(bandit_rewards, axis=1).astype(np.int8)
    explore_mask = rng.random(n) < epsilon
    random_actions = rng.integers(0, 3, size=n, dtype=np.int8)
    return np.where(explore_mask, random_actions, greedy).astype(np.int8)


def apply_actions(
    intermediation_pref: np.ndarray,
    actions: np.ndarray,
    delta: float,
) -> None:
    """Action 0 decreases preference, 1 holds, and 2 increases preference."""
    intermediation_pref[actions == 0] -= delta
    intermediation_pref[actions == 2] += delta
    np.clip(intermediation_pref, 0.01, 0.99, out=intermediation_pref)


def update_rewards(
    bandit_rewards: np.ndarray,
    bandit_counts: np.ndarray,
    actions: np.ndarray,
    rewards: np.ndarray,
    learning_rate: float,
) -> None:
    """Exponentially-weighted reward update for the selected action."""
    for action in range(3):
        mask = actions == action
        if mask.any():
            bandit_rewards[mask, action] = (
                (1.0 - learning_rate) * bandit_rewards[mask, action]
                + learning_rate * rewards[mask]
            )
            bandit_counts[mask, action] += 1

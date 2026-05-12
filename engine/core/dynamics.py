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


def entry_exit(
    pop: Any,
    cfg: Any,
    rng: np.random.Generator,
    registration_config: Any = None,
    norms_config: Any = None,
) -> int:
    """Recycle failed prototypes as new entrants.

    When the W2a registration mechanism is enabled, re-issue a fresh
    `agent_id` for each exiting slot (Hadfield's persistent-identity
    contract — a recycled prototype is a *new* actor, not the same
    actor with reset state) and re-draw the `registered` bit with
    probability `initial_registered_share`. Humans are exempt and stay
    registered. With `RegistrationConfig.enabled = False` or
    `registration_config is None` the recycler leaves `agent_id` /
    `registered` untouched, preserving canonical bit-identity.

    When the W1b norms mechanism is enabled, the new entrant's
    `norm_vector` is redrawn from the same distribution
    `Population.synthesize` used at world build (separate per-class
    sd, dedicated rng), so re-entrants start at the global norm
    distribution rather than carrying the dying prototype's stance.
    """
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

    # W2a — persistent identity. Re-issue fresh agent ids for every
    # exiting slot and (conditionally) redraw the registered bit. The
    # `enabled = False` branch leaves both fields untouched so canonical
    # bit-identity is preserved by *not consuming any new rng draws*.
    reg_enabled = bool(getattr(registration_config, "enabled", False))
    if reg_enabled and pop.agent_id is not None:
        new_ids = np.arange(
            pop.agent_next_id,
            pop.agent_next_id + n_exit,
            dtype=np.int64,
        )
        pop.agent_id[exit_mask] = new_ids
        pop.agent_next_id += n_exit
        share = float(
            getattr(registration_config, "initial_registered_share", 1.0)
        )
        if share < 1.0:
            # Use the same rng the dynamics layer already holds —
            # entry/exit lives in the population subsystem, so the
            # `population` stream is the right home for this draw.
            agent_entrant_mask = exit_mask & (~pop.is_human)
            n_agent_entrants = int(agent_entrant_mask.sum())
            if n_agent_entrants > 0:
                pop.registered[agent_entrant_mask] = (
                    rng.random(n_agent_entrants) < share
                )
        # Humans always re-enter as registered; agents above are handled
        # by the conditional draw. With share == 1.0 the existing True
        # value carries through (re-entrants stay registered).

    # W1b — fresh norm vector for re-entrants. Uses the population
    # stream so the draw is reproducible inside the same step that the
    # entry/exit ran. When disabled (or the field is absent) we leave
    # the norm_vector untouched.
    if (
        bool(getattr(norms_config, "enabled", False))
        and pop.norm_vector is not None
    ):
        K = pop.norm_vector.shape[1]
        sd_h = float(getattr(norms_config, "initial_norm_sd_human", 0.45))
        sd_a = float(getattr(norms_config, "initial_norm_sd_agent", 0.25))
        # Per-prototype sd vector based on is_human.
        sd_per_proto = np.where(
            pop.is_human[exit_mask], sd_h, sd_a
        ).astype(np.float64)
        fresh = rng.normal(
            0.0, 1.0, size=(n_exit, K)
        ).astype(np.float64) * sd_per_proto[:, None]
        pop.norm_vector[exit_mask] = np.clip(fresh, -1.0, 1.0).astype(np.float32)

    return n_exit

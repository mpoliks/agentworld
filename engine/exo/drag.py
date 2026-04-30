"""
Drag dynamics — the labor of producing legibility for capital.

A drag step:
    1. Each region targets a drag intensity (0 = laissez-faire, 1 = saturated).
    2. Drag agents allocate real welfare to *legibility tokens*: contracts,
       schemata, regulation, audits, measurement protocols.
    3. Tokens enter the lift surface, increasing local lift propensity.
    4. The labor cost of drag is borne by real welfare in the same region.

The exo claim modelled here: drag is *not* a cost-of-doing-business; it is a
mode of production. White-collar labor that opens new priced surfaces is
producing nominal value (and is paid for by it), even as the same labor
consumes real welfare.

When `coasean_dampener` > 0, drag is partially redirected: it consumes real
welfare to produce *suppression* tokens instead of lift surfaces. This is
the "Coasean agents as anxiety dampeners" mode — the agent layer simulates
agency without enabling further lift.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.core.noise import CopulaState, per_region_shock
from engine.data.empirical_anchors import region_growth_correlation
from engine.exo.config import DragConfig


# Cache CopulaState per (n_regions, dof, intra, inter, n_blocks).
_REGION_COPULA_CACHE: dict[tuple, CopulaState] = {}


def _region_copula(
    n_regions: int,
    dof: float,
    intra: float,
    inter: float,
    n_blocks: int,
) -> CopulaState:
    key = (n_regions, dof, intra, inter, n_blocks)
    state = _REGION_COPULA_CACHE.get(key)
    if state is None:
        corr = region_growth_correlation(
            n_regions, intra_block=intra, inter_block=inter, n_blocks=n_blocks
        )
        state = CopulaState.from_corr(corr, dof=dof)
        _REGION_COPULA_CACHE[key] = state
    return state


@dataclass
class DragState:
    """Per-region drag state across time."""

    intensity: np.ndarray  # (n_regions,) realised drag intensity
    legibility_tokens: np.ndarray  # (n_regions,) cumulative tokens
    welfare_consumed: np.ndarray  # (n_regions,) cumulative welfare drawn
    coasean_dampener_level: np.ndarray  # (n_regions,) realised dampener
    coasean_dampener_history: list  # list of per-step mean dampener

    @classmethod
    def empty(cls, n_regions: int, initial_intensity: float = 0.0) -> "DragState":
        return cls(
            intensity=np.full(n_regions, initial_intensity, dtype=np.float64),
            legibility_tokens=np.zeros(n_regions, dtype=np.float64),
            welfare_consumed=np.zeros(n_regions, dtype=np.float64),
            coasean_dampener_level=np.zeros(n_regions, dtype=np.float64),
            coasean_dampener_history=[],
        )


def drag_step(
    cfg: DragConfig,
    state: DragState,
    target_intensity: np.ndarray,
    real_per_region: np.ndarray,
    rng: np.random.Generator,
    dampener_per_region: np.ndarray | None = None,
) -> dict:
    """Run one drag step.

    `dampener_per_region` overrides `cfg.coasean_dampener` when provided
    (used by the adaptive-dampener mode). It must have one entry per region.

    Returns:
        dict with keys
            real_consumed_per_region : welfare drawn down by drag
            lift_propensity_boost    : per-region lift propensity contribution
            suppression_tokens       : per-region suppression activity
            dampener_per_region      : the per-region dampener actually applied
    """
    n_regions = state.intensity.shape[0]

    # Smooth toward target intensity.
    new_intensity = (
        cfg.intensity_inertia * state.intensity
        + (1.0 - cfg.intensity_inertia) * target_intensity
    )
    # Per-region wobble: choose between the legacy Gaussian or the calibrated
    # t-copula model that adds heavy tails and World-Bank-style cross-region
    # co-movement. See `engine/core/noise.py` and the epistemic-status doc.
    if cfg.noise_model == "t_copula":
        copula = _region_copula(
            n_regions,
            cfg.noise_dof,
            cfg.noise_intra_block,
            cfg.noise_inter_block,
            cfg.noise_n_blocks,
        )
        new_intensity = new_intensity + per_region_shock(
            rng,
            n_regions,
            scale=0.015,
            model="t_copula",
            dof=cfg.noise_dof,
            state=copula,
        )
    else:
        new_intensity = new_intensity + 0.015 * rng.standard_normal(n_regions)
    new_intensity = np.clip(new_intensity, cfg.saturation_floor, cfg.saturation_ceiling)
    state.intensity = new_intensity

    # Welfare cost: realised intensity * cost per token * region size.
    welfare_consumed = (
        new_intensity * cfg.welfare_cost_per_token * np.sqrt(np.maximum(real_per_region, 0.0) + 1.0)
    )
    welfare_consumed = np.minimum(welfare_consumed, np.maximum(real_per_region, 0.0))
    state.welfare_consumed += welfare_consumed

    # Coasean dampener: a fraction of the produced tokens become suppression
    # tokens rather than lift surfaces. They consume welfare without enabling
    # lift — pure anxiety dampening. Per-region when adaptive mode is on.
    if dampener_per_region is None:
        dampener_arr = np.full(
            n_regions, float(np.clip(cfg.coasean_dampener, 0.0, 1.0)), dtype=np.float64
        )
    else:
        dampener_arr = np.clip(np.asarray(dampener_per_region, dtype=np.float64), 0.0, 1.0)
    state.coasean_dampener_level = dampener_arr
    state.coasean_dampener_history.append(float(dampener_arr.mean()))

    productive_tokens = new_intensity * (1.0 - dampener_arr)
    suppression_tokens = new_intensity * dampener_arr

    # Productive tokens flow into the lift surface.
    state.legibility_tokens += productive_tokens
    lift_propensity_boost = productive_tokens * cfg.tokens_to_lift_propensity

    return {
        "real_consumed_per_region": welfare_consumed,
        "lift_propensity_boost": lift_propensity_boost,
        "suppression_tokens": suppression_tokens,
        "dampener_per_region": dampener_arr,
    }


def adaptive_dampener_update(
    cfg: DragConfig,
    prior_dampener: np.ndarray,
    real_per_region: np.ndarray,
    region_size: np.ndarray,
) -> np.ndarray:
    """Adaptive Coasean dampener — palliative-care mode.

    Compute a new per-region dampener level based on how far per-capita
    welfare has fallen below `cfg.adaptive_welfare_target`. The dampener
    is smoothed across steps via `cfg.adaptive_dampener_inertia` to mimic
    institutional ramp-up time.

    `region_size` (∑=1) lets us approximate per-capita welfare as
    `real_per_region / region_size`. A region with a small population needs
    less aggregate welfare to reach the target.
    """
    target = float(max(cfg.adaptive_welfare_target, 1e-6))
    sensitivity = float(cfg.adaptive_dampener_sensitivity)
    inertia = float(np.clip(cfg.adaptive_dampener_inertia, 0.0, 0.99))
    cap = float(np.clip(cfg.adaptive_dampener_max, 0.0, 1.0))

    safe_size = np.maximum(region_size, 1e-6)
    per_capita_real = np.maximum(real_per_region, 0.0) / safe_size
    welfare_gap = np.maximum(0.0, target - per_capita_real) / target
    target_dampener = sensitivity * welfare_gap
    # Always include the static baseline as a floor.
    target_dampener = np.maximum(target_dampener, float(cfg.coasean_dampener))
    target_dampener = np.clip(target_dampener, 0.0, cap)
    new_dampener = inertia * prior_dampener + (1.0 - inertia) * target_dampener
    return np.clip(new_dampener, 0.0, cap)


def drag_share_of_labor(state: DragState) -> float:
    """Stylised: the share of total labor sunk into drag activity.

    Approximated as the mean realised intensity. Values near 0 mean the
    economy mostly produces last-mile or pure-lift activity; values near 1
    mean the economy is mostly producing legibility.
    """
    return float(state.intensity.mean())

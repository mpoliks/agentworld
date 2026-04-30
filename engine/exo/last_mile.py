"""
Last mile — bounded material throughput, distinct from but not privileged
above the lifted layers.

Per step:
    - Each region has a physical capacity (energy, water, land, food, sleep).
    - A fraction of that capacity is *converted* into real welfare and into
      a small pulse of nominal value at layer 0 (the priced last-mile
      activity that drag will then try to lift).
    - Stochastic violence at the gore-layer destroys real welfare without
      producing nominal value.
    - Last-mile labor is paid out of the lifted economy via a wedge that
      depends on drag intensity.

This module deliberately does *not* claim that last-mile welfare is "real"
in a way that the lifted layers are not. It models the difference as a
*boundedness* property: physical capacity has a hard ceiling that nominal
value at higher layers does not.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.exo.config import LastMileConfig


@dataclass
class LastMileState:
    """Per-region last-mile state."""

    physical_capacity: np.ndarray  # (n_regions,) capacity floor for the step
    real_produced_total: np.ndarray
    nominal_layer0_total: np.ndarray
    violence_loss_total: np.ndarray

    @classmethod
    def empty(cls, n_regions: int, base_capacity: float) -> "LastMileState":
        return cls(
            physical_capacity=np.full(n_regions, base_capacity, dtype=np.float64),
            real_produced_total=np.zeros(n_regions, dtype=np.float64),
            nominal_layer0_total=np.zeros(n_regions, dtype=np.float64),
            violence_loss_total=np.zeros(n_regions, dtype=np.float64),
        )


def last_mile_step(
    cfg: LastMileConfig,
    state: LastMileState,
    region_size_weights: np.ndarray,
    capacity_multiplier: float,
    rng: np.random.Generator,
    per_region_capacity_multiplier: np.ndarray | None = None,
    per_region_violence_floor: np.ndarray | None = None,
) -> dict:
    """Produce one step of last-mile activity.

    `region_size_weights` is in [0, 1] and weights physical capacity per
    region, so larger regions produce more material throughput.
    `capacity_multiplier` is a global scalar, set by the schedule (e.g. for
    the Last-Mile Revolt scenario).
    `per_region_capacity_multiplier` is a per-region scalar (typically the
    imperial tract's resource endowment); defaults to 1.
    `per_region_violence_floor` overrides the cfg gore-layer baseline per
    region (typically the imperial tract's chronic violence inheritance).
    """
    n_regions = state.physical_capacity.shape[0]

    if per_region_capacity_multiplier is None:
        per_region_capacity_multiplier = np.ones(n_regions, dtype=np.float64)
    else:
        per_region_capacity_multiplier = np.asarray(
            per_region_capacity_multiplier, dtype=np.float64
        )

    # Per-step capacity, jittered.
    base = (
        cfg.base_physical_capacity
        * capacity_multiplier
        * region_size_weights
        * per_region_capacity_multiplier
    )
    jitter = 1.0 + cfg.capacity_jitter * rng.standard_normal(n_regions)
    capacity = np.clip(base * jitter, 0.0, None)
    state.physical_capacity = capacity

    # Production:
    real_produced = capacity * cfg.real_per_unit_capacity
    nominal_layer0 = capacity * cfg.nominal_per_unit_at_layer0

    # Stochastic gore-layer violence: fraction of real destroyed.
    if per_region_violence_floor is None:
        baseline = np.full(n_regions, cfg.gore_layer_violence, dtype=np.float64)
    else:
        baseline = np.maximum(
            np.asarray(per_region_violence_floor, dtype=np.float64),
            cfg.gore_layer_violence,
        )
    violence_rate = np.clip(
        baseline + 0.01 * rng.standard_normal(n_regions),
        0.0,
        0.5,
    )
    violence_loss = real_produced * violence_rate
    real_produced = np.maximum(real_produced - violence_loss, 0.0)

    state.real_produced_total += real_produced
    state.nominal_layer0_total += nominal_layer0
    state.violence_loss_total += violence_loss

    return {
        "real_added_per_region": real_produced,
        "nominal_added_per_region": nominal_layer0,
        "violence_loss_per_region": violence_loss,
        "capacity_per_region": capacity,
        "violence_rate_per_region": violence_rate,
    }


def last_mile_consumption(
    last_mile: LastMileState,
    drag_intensity: np.ndarray,
    nominal_total_per_region: np.ndarray,
    real_stock_per_region: np.ndarray,
    cfg: LastMileConfig,
) -> np.ndarray:
    """Compute per-region last-mile consumption pulled from real welfare.

    The wedge between last-mile producer and last-mile consumer widens with
    drag intensity (more layers between them). Consumption is bounded by a
    fraction of the available real stock so the buffer can grow when
    production exceeds use.
    """
    wedge = 1.0 + drag_intensity
    # Per-step consumption target: a share of the real stock, scaled down by
    # the drag wedge.
    target = real_stock_per_region * cfg.last_mile_labor_share / np.maximum(wedge, 1.0)
    # Don't allow consumption above 80% of the stock in a single step.
    return np.clip(target, 0.0, 0.8 * real_stock_per_region)

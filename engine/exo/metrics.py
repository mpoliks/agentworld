"""
Exo metrics — quantities the orchestrator records each step.

The α-engine's central diagnostic is the Exo-Baroque Index, EBI = nominal /
real. The exo-engine refuses that as a stable diagnostic because it
privileges last-mile as the "real" denominator. Instead, this module
exposes a vector of complementary measurements:

    LiftIndex_k          : nominal[k] / nominal[0]   (per layer)
    ReferentDistance     : weighted-mean abstraction layer of nominal value
    DragCoefficient      : drag intensity, mean across regions
    SuppressionCoeff     : realised differential suppression, mean across regions
    LastMileWedge        : nominal[0] / real_consumed   (price/cost gap)
    DifferentialProductivity : new markets per step per unit variance
    ScavengeIntensity    : violence loss / real produced (gore-layer share)
    ExoCirculationIndex  : (cumulative lift) / (cumulative real produced)
                            — a generalisation of EBI without privileging
                            either side
    HemisphericalEntropy : entropy of nominal across regions (Shannon)
    FractalDepth         : the deepest-active layer, max across regions

Every quantity is recorded per step and aggregated into a `MetricsHistory`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np


@dataclass
class StepMetrics:
    step: int
    drag_intensity_mean: float
    suppression_mean: float
    nominal_total: float
    nominal_layer0: float
    nominal_top_share: float
    real_produced_total: float
    real_consumed_total: float
    real_balance: float
    referent_distance_mean: float
    referent_distance_max: float
    lift_index_mean: float
    lift_index_top: float
    last_mile_wedge: float
    differential_productivity: float
    scavenge_intensity: float
    exo_circulation_index: float
    hemispherical_entropy: float
    deepest_active_layer: int
    new_markets_step: float
    cumulative_markets: float
    suppression_welfare_cost: float
    drag_welfare_cost: float
    violence_loss_step: float

    # Imperial fields (zero when ImperialConfig.enabled = False).
    imperial_extraction_step: float = 0.0
    imperial_extraction_total: float = 0.0
    imperial_extraction_share: float = 0.0
    imperial_capital_concentration: float = 0.0
    imperial_polity_alignment: float = 0.0
    imperial_capital_pooled_total: float = 0.0
    imperial_violence_floor_mean: float = 0.0
    n_active_tracts: int = 0

    # Adaptive Coasean dampener fields.
    coasean_dampener_mean: float = 0.0
    coasean_dampener_max: float = 0.0


@dataclass
class MetricsHistory:
    steps: List[StepMetrics] = field(default_factory=list)

    def append(self, m: StepMetrics) -> None:
        self.steps.append(m)

    def to_dict(self) -> dict:
        if not self.steps:
            return {}
        keys = list(self.steps[0].__dict__.keys())
        return {k: [getattr(s, k) for s in self.steps] for k in keys}

    def terminal_metrics(self) -> dict:
        if not self.steps:
            return {}
        return self.steps[-1].__dict__.copy()


def compute_step_metrics(
    *,
    step: int,
    nominal: np.ndarray,
    real: np.ndarray,
    real_produced_step: float,
    real_consumed_step: float,
    drag_intensity: np.ndarray,
    suppression: np.ndarray,
    new_markets_step: float,
    cumulative_markets: float,
    cumulative_lift: float,
    cumulative_real_produced: float,
    suppression_welfare_cost_step: float,
    drag_welfare_cost_step: float,
    violence_loss_step: float,
    deepest_active_layer: int,
    ontological_variance_mean: float,
    imperial_extraction_step: float = 0.0,
    imperial_extraction_total: float = 0.0,
    imperial_capital_concentration: float = 0.0,
    imperial_polity_alignment: float = 0.0,
    imperial_capital_pooled_total: float = 0.0,
    imperial_violence_floor_mean: float = 0.0,
    n_active_tracts: int = 0,
    coasean_dampener_mean: float = 0.0,
    coasean_dampener_max: float = 0.0,
) -> StepMetrics:
    """Compute one StepMetrics record from the engine state."""
    n_layers = nominal.shape[1]
    nominal_total = float(nominal.sum())
    nominal_layer0 = float(nominal[:, 0].sum())
    nominal_top = float(nominal[:, -1].sum())
    nominal_top_share = nominal_top / nominal_total if nominal_total > 0 else 0.0

    layers = np.arange(n_layers, dtype=np.float64)
    weight = nominal.sum(axis=1)
    weighted = (nominal * layers[None, :]).sum(axis=1)
    referent = np.where(weight > 0, weighted / np.maximum(weight, 1e-12), 0.0)

    layer_totals = nominal.sum(axis=0)
    base = max(layer_totals[0], 1e-9)
    lift_idx_mean = float((layer_totals / base).mean())
    lift_idx_top = float(layer_totals[-1] / base)

    last_mile_wedge = nominal_layer0 / max(real_consumed_step, 1e-9)
    diff_prod = (
        new_markets_step / max(ontological_variance_mean, 1e-3)
        if ontological_variance_mean > 0
        else 0.0
    )
    scavenge = violence_loss_step / max(real_produced_step, 1e-9)
    exo_circ = cumulative_lift / max(cumulative_real_produced, 1e-9)

    region_share = nominal.sum(axis=1)
    region_share = region_share / max(region_share.sum(), 1e-12)
    nz = region_share[region_share > 0]
    hemi_entropy = float(-(nz * np.log(nz)).sum())

    extraction_share = (
        imperial_extraction_step / max(real_produced_step, 1e-9)
        if real_produced_step > 0
        else 0.0
    )

    return StepMetrics(
        step=step,
        drag_intensity_mean=float(drag_intensity.mean()),
        suppression_mean=float(suppression.mean()),
        nominal_total=nominal_total,
        nominal_layer0=nominal_layer0,
        nominal_top_share=nominal_top_share,
        real_produced_total=float(real_produced_step),
        real_consumed_total=float(real_consumed_step),
        real_balance=float(real.sum()),
        referent_distance_mean=float(referent.mean()),
        referent_distance_max=float(referent.max()),
        lift_index_mean=lift_idx_mean,
        lift_index_top=lift_idx_top,
        last_mile_wedge=float(last_mile_wedge),
        differential_productivity=float(diff_prod),
        scavenge_intensity=float(scavenge),
        exo_circulation_index=float(exo_circ),
        hemispherical_entropy=hemi_entropy,
        deepest_active_layer=int(deepest_active_layer),
        new_markets_step=float(new_markets_step),
        cumulative_markets=float(cumulative_markets),
        suppression_welfare_cost=float(suppression_welfare_cost_step),
        drag_welfare_cost=float(drag_welfare_cost_step),
        violence_loss_step=float(violence_loss_step),
        imperial_extraction_step=float(imperial_extraction_step),
        imperial_extraction_total=float(imperial_extraction_total),
        imperial_extraction_share=float(extraction_share),
        imperial_capital_concentration=float(imperial_capital_concentration),
        imperial_polity_alignment=float(imperial_polity_alignment),
        imperial_capital_pooled_total=float(imperial_capital_pooled_total),
        imperial_violence_floor_mean=float(imperial_violence_floor_mean),
        n_active_tracts=int(n_active_tracts),
        coasean_dampener_mean=float(coasean_dampener_mean),
        coasean_dampener_max=float(coasean_dampener_max),
    )

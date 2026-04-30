"""
Phase-space sweep for the exo-engine.

Two complementary 2-D sweeps:

* `run_exo_sweep`        : drag × suppression — polity-level governance
* `run_imperial_sweep`   : extraction × capital_pooling — imperial topology

Each sweeps a small grid and classifies each point by terminal exo metrics.
These are the non-narrative checks analogous to `engine/sensitivity.py`
for the α-engine: are the named exo scenarios isolated probes or sample
points from a basin structure?

drag × suppression basin classification:
    fold        : drag-and-suppression both moderate, lift unhindered
    suppressed  : suppression high enough to flatten differential creation
    saturated   : drag at ceiling, dragging dominates the welfare budget
    starved     : last-mile output too low to feed the lift cascade
    asymptotic  : low drag and suppression — pure-lift corner

extraction × pooling basin classification:
    inert        : extraction near zero AND pooling near zero
    extractive   : extraction high, pooling low (siphon without consolidation)
    pooled       : pooling high, extraction low (consolidation without siphon)
    imperial     : both high (the named-empire corner)
    drained      : extraction so high last-mile collapses
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

from engine.exo.config import (
    DifferentialConfig,
    DragConfig,
    ExoWorldConfig,
    ImperialConfig,
    LastMileConfig,
    RegionConfig,
    StackConfig,
)
from engine.exo.world import ExoWorld


@dataclass(frozen=True)
class ExoSweepPoint:
    drag_intensity: float
    suppression_strength: float
    exo_circulation_index: float
    referent_distance_mean: float
    deepest_active_layer: int
    real_balance: float
    real_produced_total: float
    real_consumed_total: float
    cumulative_markets: float
    nominal_top_share: float
    last_mile_wedge: float
    suppression_welfare_cost: float
    drag_welfare_cost: float
    basin: str


@dataclass(frozen=True)
class ExoSweepSummary:
    points: list[ExoSweepPoint]
    drag_values: list[float]
    suppression_values: list[float]
    n_steps: int
    n_regions: int

    def to_dict(self) -> dict:
        return {
            "points": [asdict(p) for p in self.points],
            "drag_values": self.drag_values,
            "suppression_values": self.suppression_values,
            "n_steps": self.n_steps,
            "n_regions": self.n_regions,
        }


def classify_exo_basin(point_metrics: dict) -> str:
    drag = point_metrics["drag_intensity_mean"]
    supp = point_metrics["suppression_mean"]
    real_prod = point_metrics["real_produced_total"]
    refdist = point_metrics["referent_distance_mean"]
    if real_prod < 0.55:
        return "starved"
    if supp > 0.7:
        return "suppressed"
    if drag > 0.78:
        return "saturated"
    if drag < 0.18 and supp < 0.18:
        return "asymptotic"
    if refdist > 5.5:
        return "fold"
    return "mixed"


def _point_config(
    *, drag: float, suppression: float, n_steps: int, n_regions: int, seed: int
) -> ExoWorldConfig:
    # Disable imperial dynamics so this sweep isolates polity-level effects.
    # The imperial sweep below varies the empire dimensions independently.
    return ExoWorldConfig(
        stack=StackConfig(),
        drag=DragConfig(target_intensity=drag),
        differential=DifferentialConfig(suppression_strength=suppression),
        last_mile=LastMileConfig(),
        region=RegionConfig(n_regions=n_regions),
        imperial=ImperialConfig(enabled=False),
        n_steps=n_steps,
        seed=seed,
    )


def run_exo_sweep(
    *,
    drag_values: Sequence[float] | None = None,
    suppression_values: Sequence[float] | None = None,
    n_steps: int = 40,
    n_regions: int = 8,
    output_path: Path | None = None,
    seed: int = 31415,
) -> ExoSweepSummary:
    drag_values = [float(x) for x in (drag_values or np.linspace(0.05, 0.92, 7))]
    suppression_values = [float(x) for x in (suppression_values or np.linspace(0.05, 0.95, 6))]

    points: list[ExoSweepPoint] = []
    for i, drag in enumerate(drag_values):
        for j, suppression in enumerate(suppression_values):
            cfg = _point_config(
                drag=drag,
                suppression=suppression,
                n_steps=n_steps,
                n_regions=n_regions,
                seed=seed + i * 100 + j,
            )
            world = ExoWorld.build(cfg)
            world.run(progress=False)
            terminal = world.history.steps[-1].__dict__
            basin = classify_exo_basin(terminal)
            points.append(
                ExoSweepPoint(
                    drag_intensity=round(drag, 4),
                    suppression_strength=round(suppression, 4),
                    exo_circulation_index=terminal["exo_circulation_index"],
                    referent_distance_mean=terminal["referent_distance_mean"],
                    deepest_active_layer=int(terminal["deepest_active_layer"]),
                    real_balance=terminal["real_balance"],
                    real_produced_total=terminal["real_produced_total"],
                    real_consumed_total=terminal["real_consumed_total"],
                    cumulative_markets=terminal["cumulative_markets"],
                    nominal_top_share=terminal["nominal_top_share"],
                    last_mile_wedge=terminal["last_mile_wedge"],
                    suppression_welfare_cost=terminal["suppression_welfare_cost"],
                    drag_welfare_cost=terminal["drag_welfare_cost"],
                    basin=basin,
                )
            )

    summary = ExoSweepSummary(
        points=points,
        drag_values=drag_values,
        suppression_values=suppression_values,
        n_steps=n_steps,
        n_regions=n_regions,
    )
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary.to_dict(), indent=2))
    return summary


def basin_counts(points: Iterable) -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in points:
        counts[p.basin] = counts.get(p.basin, 0) + 1
    return dict(sorted(counts.items()))


# ===== Imperial sweep ==================================================


@dataclass(frozen=True)
class ImperialSweepPoint:
    extraction_rate: float
    capital_pooling_strength: float
    exo_circulation_index: float
    real_balance: float
    real_produced_total: float
    imperial_extraction_total: float
    imperial_extraction_share: float
    imperial_capital_concentration: float
    imperial_polity_alignment: float
    imperial_capital_pooled_total: float
    imperial_violence_floor_mean: float
    deepest_active_layer: int
    nominal_top_share: float
    basin: str


@dataclass(frozen=True)
class ImperialSweepSummary:
    points: list[ImperialSweepPoint]
    extraction_values: list[float]
    pooling_values: list[float]
    n_steps: int
    n_regions: int
    n_tracts: int

    def to_dict(self) -> dict:
        return {
            "points": [asdict(p) for p in self.points],
            "extraction_values": self.extraction_values,
            "pooling_values": self.pooling_values,
            "n_steps": self.n_steps,
            "n_regions": self.n_regions,
            "n_tracts": self.n_tracts,
        }


def classify_imperial_basin(point_metrics: dict) -> str:
    extr_share = point_metrics["imperial_extraction_share"]
    extr_total = point_metrics["imperial_extraction_total"]
    cap_gini = point_metrics["imperial_capital_concentration"]
    real_prod = point_metrics["real_produced_total"]

    if real_prod < 0.45 and extr_total > 1.5:
        return "drained"
    if extr_share < 0.04 and cap_gini < 0.30:
        return "inert"
    if extr_share >= 0.10 and cap_gini >= 0.55:
        return "imperial"
    if extr_share >= 0.10:
        return "extractive"
    if cap_gini >= 0.55:
        return "pooled"
    return "mixed"


def _imperial_point_config(
    *,
    extraction_rate: float,
    capital_pooling_strength: float,
    n_steps: int,
    n_regions: int,
    n_tracts: int,
    seed: int,
) -> ExoWorldConfig:
    return ExoWorldConfig(
        stack=StackConfig(),
        drag=DragConfig(target_intensity=0.40),
        differential=DifferentialConfig(suppression_strength=0.30),
        last_mile=LastMileConfig(),
        region=RegionConfig(n_regions=n_regions),
        imperial=ImperialConfig(
            enabled=True,
            n_tracts=n_tracts,
            extraction_rate=extraction_rate,
            capital_pooling_strength=capital_pooling_strength,
            seed=seed + 1000,
        ),
        n_steps=n_steps,
        seed=seed,
    )


def run_imperial_sweep(
    *,
    extraction_values: Sequence[float] | None = None,
    pooling_values: Sequence[float] | None = None,
    n_steps: int = 40,
    n_regions: int = 12,
    n_tracts: int = 4,
    output_path: Path | None = None,
    seed: int = 27182,
) -> ImperialSweepSummary:
    extraction_values = [
        float(x) for x in (extraction_values or np.linspace(0.0, 0.30, 7))
    ]
    pooling_values = [
        float(x) for x in (pooling_values or np.linspace(0.0, 0.50, 6))
    ]

    points: list[ImperialSweepPoint] = []
    for i, ext in enumerate(extraction_values):
        for j, pool in enumerate(pooling_values):
            cfg = _imperial_point_config(
                extraction_rate=ext,
                capital_pooling_strength=pool,
                n_steps=n_steps,
                n_regions=n_regions,
                n_tracts=n_tracts,
                seed=seed + i * 100 + j,
            )
            world = ExoWorld.build(cfg)
            world.run(progress=False)
            terminal = world.history.steps[-1].__dict__
            basin = classify_imperial_basin(terminal)
            points.append(
                ImperialSweepPoint(
                    extraction_rate=round(ext, 4),
                    capital_pooling_strength=round(pool, 4),
                    exo_circulation_index=terminal["exo_circulation_index"],
                    real_balance=terminal["real_balance"],
                    real_produced_total=terminal["real_produced_total"],
                    imperial_extraction_total=terminal["imperial_extraction_total"],
                    imperial_extraction_share=terminal["imperial_extraction_share"],
                    imperial_capital_concentration=terminal[
                        "imperial_capital_concentration"
                    ],
                    imperial_polity_alignment=terminal["imperial_polity_alignment"],
                    imperial_capital_pooled_total=terminal[
                        "imperial_capital_pooled_total"
                    ],
                    imperial_violence_floor_mean=terminal[
                        "imperial_violence_floor_mean"
                    ],
                    deepest_active_layer=int(terminal["deepest_active_layer"]),
                    nominal_top_share=terminal["nominal_top_share"],
                    basin=basin,
                )
            )

    summary = ImperialSweepSummary(
        points=points,
        extraction_values=extraction_values,
        pooling_values=pooling_values,
        n_steps=n_steps,
        n_regions=n_regions,
        n_tracts=n_tracts,
    )
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary.to_dict(), indent=2))
    return summary


# =============================================================================
# Saltelli/Sobol global sensitivity for the exo-engine
# =============================================================================
#
# Mirror of `engine/sensitivity.py:run_sobol_sensitivity` but over the
# exo-engine's parameter set. We do NOT vary speculative parameters
# beyond the bounds the named scenarios use, and we report bounds in
# the output JSON so the dashboard can be honest about conditionality.

EXO_ENGINE_PROBLEM: dict = {
    "num_vars": 8,
    "names": [
        "drag_target_intensity",
        "suppression_strength",
        "suppression_cost_exp",
        "base_lift_propensity",
        "lift_decay_with_depth",
        "coasean_dampener",
        "extraction_rate",
        "cross_region_compat",
    ],
    "bounds": [
        [0.10, 0.90],   # drag_target_intensity
        [0.05, 0.92],   # suppression_strength
        [1.5, 2.6],     # suppression_cost_exp
        [0.30, 0.60],   # base_lift_propensity
        [0.78, 0.95],   # lift_decay_with_depth
        [0.0, 0.85],    # coasean_dampener
        [0.0, 0.20],    # extraction_rate
        [0.20, 0.95],   # cross_region_compat
    ],
}


@dataclass(frozen=True)
class ExoSobolIndices:
    metric: str
    parameter_names: list[str]
    S1: list[float]
    S1_conf: list[float]
    ST: list[float]
    ST_conf: list[float]


@dataclass
class ExoSobolSummary:
    problem: dict
    n_base_samples: int
    n_simulations: int
    n_steps: int
    n_regions: int
    indices: list[ExoSobolIndices]
    parameter_bounds: list[list[float]]

    def to_dict(self) -> dict:
        return {
            "problem": {
                "num_vars": self.problem["num_vars"],
                "names": list(self.problem["names"]),
                "bounds": [list(b) for b in self.problem["bounds"]],
            },
            "n_base_samples": self.n_base_samples,
            "n_simulations": self.n_simulations,
            "n_steps": self.n_steps,
            "n_regions": self.n_regions,
            "parameter_bounds": [list(b) for b in self.parameter_bounds],
            "indices": [asdict(i) for i in self.indices],
        }


def _exo_world_from_vector(
    x: np.ndarray, *, n_steps: int, n_regions: int, seed: int
) -> ExoWorldConfig:
    return ExoWorldConfig(
        stack=StackConfig(
            base_lift_propensity=float(x[3]),
            lift_decay_with_depth=float(x[4]),
        ),
        drag=DragConfig(
            target_intensity=float(x[0]),
            coasean_dampener=float(x[5]),
        ),
        differential=DifferentialConfig(
            suppression_strength=float(x[1]),
            suppression_cost_exp=float(x[2]),
        ),
        last_mile=LastMileConfig(),
        region=RegionConfig(
            n_regions=n_regions,
            cross_region_compat=float(x[7]),
        ),
        imperial=ImperialConfig(
            enabled=True,
            extraction_rate=float(x[6]),
            seed=seed + 1000,
        ),
        n_steps=n_steps,
        seed=seed,
    )


def run_exo_sobol(
    *,
    n_base_samples: int = 32,
    n_steps: int = 40,
    n_regions: int = 8,
    output_path: Path | None = None,
    seed: int = 20260430,
    metrics: Sequence[str] = (
        "exo_circulation_index",
        "real_balance",
        "imperial_extraction_share",
        "deepest_active_layer",
    ),
    progress: bool = True,
) -> ExoSobolSummary:
    """Run a Saltelli/Sobol sweep on the exo-engine.

    With `n_base_samples=N`, SALib produces `N * (D + 2)` simulations
    (D=8 here, so N=32 -> 320 simulations).
    """
    try:
        from SALib.analyze import sobol as sobol_analyze
        from SALib.sample import sobol as sobol_sample
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "SALib is required for Sobol sensitivity. Install with `pip install SALib`."
        ) from exc

    problem = EXO_ENGINE_PROBLEM
    X = sobol_sample.sample(problem, n_base_samples, calc_second_order=False)
    n_sims = X.shape[0]
    if progress:
        print(
            f"[exo-sobol] {n_sims} simulations "
            f"({n_base_samples} base x (D+2={problem['num_vars'] + 2}))"
        )

    outputs = {m: np.empty(n_sims, dtype=np.float64) for m in metrics}
    for i in range(n_sims):
        cfg = _exo_world_from_vector(
            X[i], n_steps=n_steps, n_regions=n_regions, seed=seed + i
        )
        world = ExoWorld.build(cfg)
        world.run(progress=False)
        terminal = world.history.steps[-1]
        for m in metrics:
            val = getattr(terminal, m, 0.0)
            outputs[m][i] = float(val)
        if progress and ((i + 1) % max(1, n_sims // 20) == 0):
            print(f"  [exo-sobol]   sim {i + 1:>4d}/{n_sims}")

    indices: list[ExoSobolIndices] = []
    for m in metrics:
        Si = sobol_analyze.analyze(
            problem, outputs[m], calc_second_order=False, print_to_console=False
        )
        indices.append(
            ExoSobolIndices(
                metric=m,
                parameter_names=list(problem["names"]),
                S1=[float(v) for v in Si["S1"]],
                S1_conf=[float(v) for v in Si["S1_conf"]],
                ST=[float(v) for v in Si["ST"]],
                ST_conf=[float(v) for v in Si["ST_conf"]],
            )
        )

    summary = ExoSobolSummary(
        problem=problem,
        n_base_samples=n_base_samples,
        n_simulations=n_sims,
        n_steps=n_steps,
        n_regions=n_regions,
        indices=indices,
        parameter_bounds=problem["bounds"],
    )
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary.to_dict(), indent=2))
    return summary


if __name__ == "__main__":
    out = Path("outputs/sensitivity/exo_phase_space.json")
    summary = run_exo_sweep(output_path=out)
    print(f"[exo] wrote {len(summary.points)} sweep points to {out}")
    print(basin_counts(summary.points))

    out2 = Path("outputs/sensitivity/exo_imperial_phase_space.json")
    isum = run_imperial_sweep(output_path=out2)
    print(f"[exo] wrote {len(isum.points)} imperial sweep points to {out2}")
    print(basin_counts(isum.points))

    out3 = Path("outputs/sensitivity/exo_sobol_indices.json")
    sobol_summary = run_exo_sobol(output_path=out3)
    print(f"[exo] wrote sobol indices for {len(sobol_summary.indices)} metrics to {out3}")

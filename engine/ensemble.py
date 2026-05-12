"""
Ensemble runner for the alpha-engine.

Runs the same scenario across N independent seeds and reports:
    - per-step median trajectory
    - per-step bootstrapped 5/95 percentile bands
    - the full (N, n_steps) array of every metric

Persists to Parquet so the dashboard can ingest band geometry without
re-running. See `docs/concepts/epistemic_status.md` for what the bands
mean (and don't).

CLI:
    agentworld ensemble baroque_cathedral --seeds 64
    agentworld ensemble-all --seeds 32
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

import numpy as np

from engine.core.world import World
from engine.scale import Scale, apply_scale
from engine.scenarios import SCENARIOS, get_scenario


# Metrics in StepMetrics that are always numeric (we exclude `step` and `alpha`
# because they're the abscissa, not signals).
_BAND_METRIC_KEYS: tuple[str, ...] = (
    "real_welfare_step",
    "real_welfare_cumulative",
    "nominal_gdp_step",
    "nominal_gdp_cumulative",
    "exo_baroque_index",
    "fold_max_depth",
    "n_transactions_real",
    "n_sub_markets_added",
    "rejected_law",
    "rejected_market",
    "rejected_align",
    "rejected_cost",
    "rejected_permeability",
    "rejected_regulator",
    "human_labor_wage_step",
    "human_labor_wage_cumulative",
    "gini_wealth",
    "gini_wealth_human",
    "real_per_capita_welfare_human",
    "real_per_capita_welfare",
    "human_legibility_index",
    "governance_overhead_fraction",
    "a2a_share",
    "h2a_share",
    "h2h_share",
    "top_decile_wealth_share",
    "top_decile_share_change",
    "gini_wealth_change_abs",
    "log_exo_baroque_index",
    "log_exo_baroque_authentic",
)


@dataclass
class EnsembleResult:
    """Per-scenario ensemble outcome.

    `series` maps each metric name to a (n_seeds, n_steps) float64 array.
    `bands` maps each metric name to a dict with keys "median", "p05",
    "p95", each (n_steps,) float64 arrays.
    """

    name: str
    n_seeds: int
    seeds: list[int]
    n_steps: int
    scale: str
    series: dict[str, np.ndarray] = field(default_factory=dict)
    bands: dict[str, dict[str, np.ndarray]] = field(default_factory=dict)
    elapsed_sec: float = 0.0

    def to_parquet(self, path: Path) -> None:
        """Write a Parquet file with one row per (seed, step)."""
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "pandas + pyarrow are required to write ensemble parquet"
            ) from exc

        rows = []
        for s_idx, seed in enumerate(self.seeds):
            for t in range(self.n_steps):
                row = {"scenario": self.name, "seed": int(seed), "step": int(t)}
                for k, arr in self.series.items():
                    row[k] = float(arr[s_idx, t])
                rows.append(row)
        df = pd.DataFrame(rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)

    def to_band_json(self, path: Path) -> None:
        """Write a compact JSON of just the bands (for the dashboard)."""
        out = {
            "name": self.name,
            "n_seeds": self.n_seeds,
            "n_steps": self.n_steps,
            "scale": self.scale,
            "elapsed_sec": self.elapsed_sec,
            "bands": {
                k: {
                    band_name: arr.tolist()
                    for band_name, arr in band.items()
                }
                for k, band in self.bands.items()
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out))


def _bootstrap_bands(
    arr: np.ndarray,
    *,
    n_bootstrap: int,
    rng: np.random.Generator,
    lower_q: float = 0.05,
    upper_q: float = 0.95,
) -> dict[str, np.ndarray]:
    """Compute median and bootstrapped lower/upper percentile bands.

    `arr` has shape (n_seeds, n_steps). Returns three (n_steps,) arrays.

    With N seeds, the percentile estimates have non-trivial uncertainty;
    the bootstrap resamples seeds (with replacement) `n_bootstrap` times
    to estimate the percentile sampling distribution and reports the
    *median* of the percentile estimates. This is the band-of-the-band
    correction; for the typical N=64 it shrinks the percentile noise by
    roughly sqrt(n_bootstrap).
    """
    n_seeds, n_steps = arr.shape
    if n_seeds < 2 or n_bootstrap <= 1:
        return {
            "median": np.median(arr, axis=0),
            "p05": np.quantile(arr, lower_q, axis=0),
            "p95": np.quantile(arr, upper_q, axis=0),
        }

    p05_estimates = np.empty((n_bootstrap, n_steps), dtype=np.float64)
    p95_estimates = np.empty((n_bootstrap, n_steps), dtype=np.float64)
    median_estimates = np.empty((n_bootstrap, n_steps), dtype=np.float64)
    for b in range(n_bootstrap):
        idx = rng.integers(0, n_seeds, size=n_seeds)
        sample = arr[idx, :]
        median_estimates[b] = np.median(sample, axis=0)
        p05_estimates[b] = np.quantile(sample, lower_q, axis=0)
        p95_estimates[b] = np.quantile(sample, upper_q, axis=0)
    return {
        "median": np.median(median_estimates, axis=0),
        "p05": np.median(p05_estimates, axis=0),
        "p95": np.median(p95_estimates, axis=0),
    }


def _run_one_seed(args: tuple) -> tuple[int, dict[str, np.ndarray]]:
    """Top-level helper for multiprocessing.Pool (must be picklable)."""
    name, seed, scale_value = args
    cfg = apply_scale(get_scenario(name), Scale(scale_value))
    cfg.seed = int(seed)
    cfg.population.seed = int(seed)
    world = World.build(cfg)
    world.run(progress=False)
    history = world.metrics.history.to_dict()
    out = {k: np.asarray(history[k], dtype=np.float64) for k in _BAND_METRIC_KEYS}
    return seed, out


def run_ensemble(
    name: str,
    *,
    n_seeds: int = 64,
    base_seed: int = 20260430,
    scale: Scale | str = Scale.SMALL,
    n_workers: int = 1,
    n_bootstrap: int = 200,
    output_dir: Optional[Path] = None,
    progress: bool = True,
) -> EnsembleResult:
    """Run a scenario across N independent seeds and band the trajectories.

    With `n_workers > 1`, seed runs are dispatched to a multiprocessing
    pool. Each worker holds its own population in memory; size n_workers
    so n_workers * peak RAM fits on the host.

    Bootstrap percentile bands are computed across the seed dimension
    with `n_bootstrap` resamples (set to 1 to skip the band-of-the-band
    correction).
    """
    if name not in SCENARIOS:
        raise KeyError(f"Unknown scenario: {name}")
    scale_value = Scale(scale).value if not isinstance(scale, Scale) else scale.value

    seeds = [int(base_seed + i) for i in range(n_seeds)]
    if progress:
        print(
            f"[ensemble] {name} -> {n_seeds} seeds, "
            f"scale={scale_value}, workers={n_workers}"
        )
    t0 = time.perf_counter()
    args = [(name, s, scale_value) for s in seeds]
    if n_workers <= 1:
        results = [_run_one_seed(a) for a in args]
    else:
        from multiprocessing import Pool

        with Pool(processes=n_workers) as pool:
            results = list(pool.imap_unordered(_run_one_seed, args))

    # Sort back to seed order.
    results.sort(key=lambda r: r[0])
    seed_order = [r[0] for r in results]
    histories = [r[1] for r in results]
    n_steps = histories[0][_BAND_METRIC_KEYS[0]].shape[0]

    series: dict[str, np.ndarray] = {}
    for key in _BAND_METRIC_KEYS:
        # Some seeds may have ragged length if the engine ever short-circuits;
        # in this engine all runs use the same n_steps so this is exact.
        series[key] = np.stack(
            [h[key][:n_steps] for h in histories], axis=0
        ).astype(np.float64)

    rng = np.random.default_rng(base_seed ^ 0xA17F)
    bands: dict[str, dict[str, np.ndarray]] = {}
    for key, arr in series.items():
        bands[key] = _bootstrap_bands(arr, n_bootstrap=n_bootstrap, rng=rng)

    elapsed = time.perf_counter() - t0
    result = EnsembleResult(
        name=name,
        n_seeds=n_seeds,
        seeds=seed_order,
        n_steps=n_steps,
        scale=scale_value,
        series=series,
        bands=bands,
        elapsed_sec=elapsed,
    )
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        result.to_parquet(output_dir / f"{name}.parquet")
        result.to_band_json(output_dir / f"{name}.bands.json")
        if progress:
            print(
                f"[ensemble] {name} done in {elapsed:.1f}s -> "
                f"{output_dir / (name + '.parquet')}"
            )
    return result


def run_ensemble_all(
    *,
    n_seeds: int = 32,
    base_seed: int = 20260430,
    scale: Scale | str = Scale.SMALL,
    n_workers: int = 1,
    output_dir: Optional[Path] = None,
    only: Optional[Iterable[str]] = None,
    progress: bool = True,
) -> dict[str, EnsembleResult]:
    """Run an ensemble for every scenario in the registry."""
    names = list(only) if only is not None else list(SCENARIOS.keys())
    out: dict[str, EnsembleResult] = {}
    for name in names:
        out[name] = run_ensemble(
            name,
            n_seeds=n_seeds,
            base_seed=base_seed,
            scale=scale,
            n_workers=n_workers,
            output_dir=output_dir,
            progress=progress,
        )
    return out


# Convenience: the metric keys are part of the public API so the dashboard
# can iterate them without depending on the StepMetrics layout.
BAND_METRIC_KEYS: tuple[str, ...] = _BAND_METRIC_KEYS


__all__ = [
    "EnsembleResult",
    "BAND_METRIC_KEYS",
    "run_ensemble",
    "run_ensemble_all",
]

"""
Ensemble runner for the exo-engine.

Mirror of `engine/ensemble.py` for the exo dynamics. Same Parquet
contract, same band-of-the-band bootstrap, different metric keys.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from engine.exo.scenarios import SCENARIOS, get_scenario
from engine.exo.world import ExoWorld


_BAND_METRIC_KEYS: tuple[str, ...] = (
    "drag_intensity_mean",
    "suppression_mean",
    "nominal_total",
    "nominal_layer0",
    "nominal_top_share",
    "real_produced_total",
    "real_consumed_total",
    "real_balance",
    "referent_distance_mean",
    "referent_distance_max",
    "lift_index_mean",
    "lift_index_top",
    "last_mile_wedge",
    "differential_productivity",
    "scavenge_intensity",
    "exo_circulation_index",
    "hemispherical_entropy",
    "deepest_active_layer",
    "new_markets_step",
    "cumulative_markets",
    "suppression_welfare_cost",
    "drag_welfare_cost",
    "violence_loss_step",
    "imperial_extraction_step",
    "imperial_extraction_total",
    "imperial_extraction_share",
    "imperial_capital_concentration",
    "imperial_polity_alignment",
    "imperial_capital_pooled_total",
    "imperial_violence_floor_mean",
    "coasean_dampener_mean",
    "coasean_dampener_max",
)


@dataclass
class ExoEnsembleResult:
    name: str
    n_seeds: int
    seeds: list[int]
    n_steps: int
    series: dict[str, np.ndarray] = field(default_factory=dict)
    bands: dict[str, dict[str, np.ndarray]] = field(default_factory=dict)
    elapsed_sec: float = 0.0

    def to_parquet(self, path: Path) -> None:
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
        out = {
            "name": self.name,
            "n_seeds": self.n_seeds,
            "n_steps": self.n_steps,
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
    n_seeds, n_steps = arr.shape
    if n_seeds < 2 or n_bootstrap <= 1:
        return {
            "median": np.median(arr, axis=0),
            "p05": np.quantile(arr, lower_q, axis=0),
            "p95": np.quantile(arr, upper_q, axis=0),
        }
    p05 = np.empty((n_bootstrap, n_steps), dtype=np.float64)
    p95 = np.empty((n_bootstrap, n_steps), dtype=np.float64)
    med = np.empty((n_bootstrap, n_steps), dtype=np.float64)
    for b in range(n_bootstrap):
        idx = rng.integers(0, n_seeds, size=n_seeds)
        sample = arr[idx, :]
        med[b] = np.median(sample, axis=0)
        p05[b] = np.quantile(sample, lower_q, axis=0)
        p95[b] = np.quantile(sample, upper_q, axis=0)
    return {
        "median": np.median(med, axis=0),
        "p05": np.median(p05, axis=0),
        "p95": np.median(p95, axis=0),
    }


def _run_one_seed_exo(args: tuple) -> tuple[int, dict[str, np.ndarray]]:
    name, seed = args
    cfg = get_scenario(name)
    cfg.seed = int(seed)
    if cfg.imperial.enabled:
        # Keep imperial RNG distinct so seed sweep doesn't collide with the
        # imperial geography seed (matches ExoWorld.build's convention).
        cfg.imperial.seed = int(seed) ^ 0xC0FFEE
    world = ExoWorld.build(cfg)
    world.run(progress=False)
    history = world.history.to_dict()
    out: dict[str, np.ndarray] = {}
    for k in _BAND_METRIC_KEYS:
        if k in history:
            out[k] = np.asarray(history[k], dtype=np.float64)
    return seed, out


def run_ensemble(
    name: str,
    *,
    n_seeds: int = 32,
    base_seed: int = 20260430,
    n_workers: int = 1,
    n_bootstrap: int = 200,
    output_dir: Optional[Path] = None,
    progress: bool = True,
) -> ExoEnsembleResult:
    if name not in SCENARIOS:
        raise KeyError(f"Unknown exo scenario: {name}")

    seeds = [int(base_seed + i) for i in range(n_seeds)]
    if progress:
        print(f"[exo-ensemble] {name} -> {n_seeds} seeds, workers={n_workers}")
    t0 = time.perf_counter()
    args = [(name, s) for s in seeds]
    if n_workers <= 1:
        results = [_run_one_seed_exo(a) for a in args]
    else:
        from multiprocessing import Pool

        with Pool(processes=n_workers) as pool:
            results = list(pool.imap_unordered(_run_one_seed_exo, args))

    results.sort(key=lambda r: r[0])
    seed_order = [r[0] for r in results]
    histories = [r[1] for r in results]

    # Use whichever metric key is present in all histories to determine n_steps.
    sample = histories[0]
    n_steps = next(iter(sample.values())).shape[0]

    series: dict[str, np.ndarray] = {}
    for key in _BAND_METRIC_KEYS:
        if not all(key in h for h in histories):
            continue
        series[key] = np.stack(
            [h[key][:n_steps] for h in histories], axis=0
        ).astype(np.float64)

    rng = np.random.default_rng(base_seed ^ 0xB17F)
    bands: dict[str, dict[str, np.ndarray]] = {}
    for key, arr in series.items():
        bands[key] = _bootstrap_bands(arr, n_bootstrap=n_bootstrap, rng=rng)

    elapsed = time.perf_counter() - t0
    result = ExoEnsembleResult(
        name=name,
        n_seeds=n_seeds,
        seeds=seed_order,
        n_steps=n_steps,
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
                f"[exo-ensemble] {name} done in {elapsed:.1f}s -> "
                f"{output_dir / (name + '.parquet')}"
            )
    return result


def run_ensemble_all(
    *,
    n_seeds: int = 16,
    base_seed: int = 20260430,
    n_workers: int = 1,
    output_dir: Optional[Path] = None,
    only: Optional[Iterable[str]] = None,
    progress: bool = True,
) -> dict[str, ExoEnsembleResult]:
    names = list(only) if only is not None else list(SCENARIOS.keys())
    out: dict[str, ExoEnsembleResult] = {}
    for name in names:
        out[name] = run_ensemble(
            name,
            n_seeds=n_seeds,
            base_seed=base_seed,
            n_workers=n_workers,
            output_dir=output_dir,
            progress=progress,
        )
    return out


BAND_METRIC_KEYS: tuple[str, ...] = _BAND_METRIC_KEYS


__all__ = [
    "ExoEnsembleResult",
    "BAND_METRIC_KEYS",
    "run_ensemble",
    "run_ensemble_all",
]

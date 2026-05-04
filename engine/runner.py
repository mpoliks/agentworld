"""Runner — orchestrates many scenario runs and writes outputs."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from engine.core.world import World, WorldConfig
from engine.scale import Scale, apply_scale
from engine.scenarios import SCENARIOS, get_scenario, list_scenarios


def _serializable_config(cfg: WorldConfig) -> dict:
    """Recursively convert config dataclasses to JSON-friendly dicts."""

    def _conv(v):
        if isinstance(v, np.ndarray):
            return v.tolist()
        if hasattr(v, "__dict__"):
            return {k: _conv(val) for k, val in v.__dict__.items()}
        if isinstance(v, (tuple, list)):
            return [_conv(x) for x in v]
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return float(v)
        return v

    return _conv(cfg)


@dataclass
class RunResult:
    name: str
    config: dict
    population_summary: dict
    history: dict
    final_alpha: float
    final_label: str
    scale: str = "small"
    elapsed_sec: float = 0.0


def run_scenario(name: str, output_dir: Optional[Path] = None,
                 progress: bool = True,
                 scale: Scale | str = Scale.SMALL,
                 seed: Optional[int] = None) -> RunResult:
    cfg = apply_scale(get_scenario(name), scale)
    if seed is not None:
        cfg.seed = int(seed)
        cfg.population.seed = int(seed)
    t0 = time.perf_counter()
    world = World.build(cfg)
    world.run(progress=progress)
    elapsed = time.perf_counter() - t0

    snap = world.snapshot()
    result = RunResult(
        name=name,
        config=_serializable_config(cfg),
        population_summary=snap["population_summary"],
        history=snap["history"],
        final_alpha=snap["alpha"],
        final_label=snap["topology_label"],
        scale=Scale(scale).value if not isinstance(scale, Scale) else scale.value,
        elapsed_sec=elapsed,
    )

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{name}.json"
        with open(out_path, "w") as f:
            json.dump(asdict(result), f)
    return result


def _run_one_scenario_for_pool(args: tuple) -> tuple[str, RunResult]:
    """Top-level helper for multiprocessing.Pool (must be picklable)."""
    name, output_dir, scale_value = args
    res = run_scenario(
        name,
        output_dir=Path(output_dir) if output_dir is not None else None,
        progress=False,
        scale=Scale(scale_value),
    )
    return name, res


def run_all(output_dir: Optional[Path] = None,
            progress: bool = True,
            only: Optional[Iterable[str]] = None,
            scale: Scale | str = Scale.SMALL,
            n_workers: int = 1) -> dict[str, RunResult]:
    """Run every scenario in the registry.

    With n_workers>1, scenarios run in a multiprocessing.Pool. Each worker
    holds the full population in memory; size n_workers so n_workers x peak
    RAM fits comfortably on the host.
    """
    names = list(only) if only is not None else list(SCENARIOS.keys())
    scale_value = Scale(scale).value if not isinstance(scale, Scale) else scale.value
    results: dict[str, RunResult] = {}
    timings: list[tuple[str, float]] = []

    if n_workers <= 1:
        for name in names:
            print(f"[agentworld] running scenario: {name} (scale={scale_value})")
            res = run_scenario(
                name,
                output_dir=output_dir,
                progress=progress,
                scale=Scale(scale_value),
            )
            results[name] = res
            timings.append((name, res.elapsed_sec))
            print(f"  -> {res.elapsed_sec:.1f}s")
    else:
        from multiprocessing import Pool

        out_str = str(output_dir) if output_dir is not None else None
        args = [(name, out_str, scale_value) for name in names]
        print(
            f"[agentworld] running {len(names)} scenarios across "
            f"{n_workers} workers (scale={scale_value})"
        )
        with Pool(processes=n_workers) as pool:
            for name, res in pool.imap_unordered(_run_one_scenario_for_pool, args):
                results[name] = res
                timings.append((name, res.elapsed_sec))
                print(f"  done {name:30s} {res.elapsed_sec:6.1f}s")

    timings.sort(key=lambda t: -t[1])
    total = sum(t for _, t in timings)
    print(f"\n[agentworld] timing report (total {total:.1f}s):")
    for name, t in timings[:10]:
        print(f"  {name:30s} {t:6.1f}s")
    return results

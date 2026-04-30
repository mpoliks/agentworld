"""Runner — orchestrates exo scenario runs and writes JSON outputs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from engine.exo.config import ExoWorldConfig
from engine.exo.scenarios import SCENARIOS, get_scenario
from engine.exo.world import ExoWorld


def _serializable(obj):
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if hasattr(obj, "__dict__"):
        return {k: _serializable(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, (list, tuple)):
        return [_serializable(x) for x in obj]
    return obj


@dataclass
class ExoRunResult:
    name: str
    config: dict
    history: dict
    snapshot: dict


def run_scenario(
    name: str, output_dir: Optional[Path] = None, progress: bool = True
) -> ExoRunResult:
    cfg = get_scenario(name)
    world = ExoWorld.build(cfg)
    world.run(progress=progress)
    snap = world.snapshot()
    result = ExoRunResult(
        name=name,
        config=_serializable(cfg),
        history=snap["history"],
        snapshot={k: snap[k] for k in ("step", "n_regions", "n_layers", "drag_share_of_labor")},
    )
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"{name}.json").write_text(json.dumps(asdict(result)))
    return result


def run_all(
    output_dir: Optional[Path] = None,
    progress: bool = True,
    only: Optional[Iterable[str]] = None,
) -> dict[str, ExoRunResult]:
    names = list(only) if only is not None else list(SCENARIOS.keys())
    results: dict[str, ExoRunResult] = {}
    for name in names:
        print(f"[exo] running scenario: {name}")
        results[name] = run_scenario(name, output_dir=output_dir, progress=progress)
    return results

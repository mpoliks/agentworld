"""Regenerate deterministic canonical scenario baselines.

Writes one JSON file per scenario in ``engine.scenarios.SCENARIOS`` to
``outputs/runs/<name>.json`` using each scenario's default configuration.
The output intentionally excludes runtime metadata so repeated runs can be
compared byte-for-byte.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from engine.core.world import World
from engine.scenarios import SCENARIOS, get_scenario


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs" / "runs"


def _jsonable(value: Any) -> Any:
    """Convert dataclass output into JSON-stable built-in containers."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def build_payload(name: str) -> dict[str, Any]:
    cfg = get_scenario(name)
    world = World.build(cfg)
    world.run(progress=False)
    history = world.metrics.history.to_dict()
    return {
        "name": name,
        "config": _jsonable(asdict(cfg)),
        "population_summary": world.population.summary(),
        "history": history,
        "final_alpha": float(world.topology.cfg.alpha),
        "final_label": world.topology.label(),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name in SCENARIOS:
        payload = build_payload(name)
        path = OUTPUT_DIR / f"{name}.json"
        path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        print(f"[baselines] wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

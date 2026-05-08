"""
Convergence-as-evidence harness.

For each scenario, run at scale ∈ {small, medium, large, xlarge} with K
seeds each. Bootstrap 95% CIs on terminal-step EBI, Gini, A2A share, and
real_per_capita_welfare. The expected pattern: point estimates stable
within CI across scales, CIs shrink monotonically, xlarge CIs at least 3x
tighter than small.

Usage:
    PYTHONPATH=. python engine/convergence.py
    PYTHONPATH=. python engine/convergence.py --scales small medium --seeds 15
    PYTHONPATH=. python engine/convergence.py --only coasean_paradise baroque_cathedral

Writes outputs/convergence/<scenario>.json plus outputs/convergence/_summary.json
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

from engine.core.world import World
from engine.scale import Scale, apply_scale
from engine.scenarios import SCENARIOS, get_scenario


METRICS_OF_INTEREST = (
    "exo_baroque_index",
    "gini_wealth",
    "a2a_share",
    "real_per_capita_welfare",
    "human_legibility_index",
    "fold_max_depth",
    "governance_overhead_fraction",
)


@dataclass
class SeedRun:
    seed: int
    elapsed_sec: float
    final: dict[str, float] = field(default_factory=dict)


@dataclass
class ScaleResult:
    scale: str
    n_total: int
    n_pairs: int
    n_steps: int
    seeds: list[SeedRun] = field(default_factory=list)
    summary: dict[str, dict[str, float]] = field(default_factory=dict)


def _bootstrap_ci(values: Sequence[float], n_boot: int = 2000, alpha: float = 0.05) -> dict:
    """Percentile bootstrap 95% CI on the mean."""
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return dict(mean=0.0, lo=0.0, hi=0.0, n=0, std=0.0)
    rng = np.random.default_rng(20260429)
    n = arr.size
    if n == 1:
        return dict(mean=float(arr[0]), lo=float(arr[0]), hi=float(arr[0]), n=1, std=0.0)
    boots = arr[rng.integers(0, n, size=(n_boot, n))].mean(axis=1)
    lo, hi = np.quantile(boots, [alpha / 2.0, 1.0 - alpha / 2.0])
    return dict(
        mean=float(arr.mean()),
        std=float(arr.std(ddof=1)),
        lo=float(lo),
        hi=float(hi),
        n=int(n),
    )


def _summarize(seeds: list[SeedRun]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for key in METRICS_OF_INTEREST:
        vals = [s.final[key] for s in seeds if key in s.final]
        out[key] = _bootstrap_ci(vals)
    return out


def run_scenario_at_scale(
    name: str, scale: Scale, seeds: Sequence[int], n_steps: int | None = None,
) -> ScaleResult:
    base_cfg = apply_scale(get_scenario(name), scale)
    if n_steps is not None:
        base_cfg.n_steps = n_steps

    runs: list[SeedRun] = []
    for s in seeds:
        cfg = apply_scale(get_scenario(name), scale)
        if n_steps is not None:
            cfg.n_steps = n_steps
        cfg.seed = int(s)
        cfg.population.seed = int(1_000_000 + s)
        t0 = time.perf_counter()
        world = World.build(cfg)
        world.run(progress=False)
        elapsed = time.perf_counter() - t0
        last = world.metrics.history.steps[-1]
        run = SeedRun(
            seed=int(s),
            elapsed_sec=elapsed,
            final={k: float(getattr(last, k)) for k in METRICS_OF_INTEREST},
        )
        runs.append(run)

    n_total = base_cfg.population.n_human_prototypes + base_cfg.population.n_agent_prototypes
    return ScaleResult(
        scale=scale.value,
        n_total=n_total,
        n_pairs=base_cfg.pairs_per_step,
        n_steps=base_cfg.n_steps,
        seeds=runs,
        summary=_summarize(runs),
    )


def run_convergence(
    scenarios: list[str],
    scales: list[Scale],
    n_seeds: int,
    n_steps: int | None,
    output_dir: Path,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    seeds = list(range(n_seeds))
    overall: dict[str, dict] = {}
    for name in scenarios:
        print(f"\n[convergence] scenario: {name}")
        per_scale: dict[str, ScaleResult] = {}
        for scale in scales:
            print(f"  -> {scale.value:6s} (n_seeds={n_seeds}) ", end="", flush=True)
            t0 = time.perf_counter()
            res = run_scenario_at_scale(name, scale, seeds, n_steps=n_steps)
            elapsed = time.perf_counter() - t0
            mean_ebi = res.summary["exo_baroque_index"]["mean"]
            ci_ebi = res.summary["exo_baroque_index"]
            print(
                f"  EBI={mean_ebi:8.2f} [{ci_ebi['lo']:7.2f}, {ci_ebi['hi']:7.2f}]  "
                f"({elapsed:.1f}s)"
            )
            per_scale[scale.value] = res
        new_scales = {
            scale.value: {
                "scale": res.scale,
                "n_total": res.n_total,
                "n_pairs": res.n_pairs,
                "n_steps": res.n_steps,
                "seeds": [asdict(s) for s in res.seeds],
                "summary": res.summary,
            }
            for scale, res in zip(scales, per_scale.values())
        }
        out_path = output_dir / f"{name}.json"
        scenario_payload = {}
        if out_path.exists():
            try:
                scenario_payload = json.loads(out_path.read_text())
            except json.JSONDecodeError:
                scenario_payload = {}
        scenario_payload.update(new_scales)
        out_path.write_text(json.dumps(scenario_payload, indent=2))
        overall[name] = scenario_payload
        print(f"  wrote {out_path}")

    summary_path = output_dir / "_summary.json"
    existing_summary: dict = {}
    if summary_path.exists():
        try:
            existing_summary = json.loads(summary_path.read_text())
        except json.JSONDecodeError:
            existing_summary = {}
    for name, scenario_payload in overall.items():
        scenario_summary = existing_summary.setdefault(name, {})
        for scale_name, payload in scenario_payload.items():
            scenario_summary[scale_name] = {
                metric: payload["summary"][metric]
                for metric in METRICS_OF_INTEREST
                if metric in payload.get("summary", {})
            }
    summary_path.write_text(json.dumps(existing_summary, indent=2))
    print(f"\n[convergence] summary -> {summary_path}")
    return overall


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scales", nargs="+", default=["small", "medium", "large", "xlarge"]
    )
    parser.add_argument("--seeds", type=int, default=15)
    parser.add_argument("--steps", type=int, default=None,
                        help="Override n_steps (default: scenario default).")
    parser.add_argument("--only", nargs="*", default=None,
                        help="Optional scenario name allowlist.")
    parser.add_argument("--out", default="outputs/convergence")
    args = parser.parse_args()

    scenarios = list(args.only) if args.only else list(SCENARIOS.keys())
    scales = [Scale(s) for s in args.scales]
    run_convergence(
        scenarios=scenarios,
        scales=scales,
        n_seeds=args.seeds,
        n_steps=args.steps,
        output_dir=Path(args.out),
    )


if __name__ == "__main__":
    main()

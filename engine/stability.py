"""
n_steps stability harness — has the trajectory finished moving?

For each scenario, run at increasing `n_steps ∈ {N₁, N₂, …}` with K seeds
each. Bootstrap 95% CIs on terminal-step EBI, real-per-capita welfare, Gini,
and a2a share. The expected pattern: terminal point estimates stable within
CI as `n_steps` grows. Drift outside the CI implies the scenario has not
converged on its terminal regime within the smaller step budget.

This is the n_steps analog of `engine.convergence` (which sweeps population
scale, not step count). Together they answer two distinct questions:

    convergence  — is the population large enough?
    stability    — has the trajectory run long enough?

Usage:
    PYTHONPATH=. python engine/stability.py
    PYTHONPATH=. python engine/stability.py --steps 100 200 400 --seeds 3
    PYTHONPATH=. python engine/stability.py --only baroque_cathedral

Writes outputs/stability/<scenario>.json plus outputs/stability/_summary.json.
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
    "real_per_capita_welfare",
    "gini_wealth",
    "a2a_share",
    "fold_max_depth",
    "governance_overhead_fraction",
)


@dataclass
class SeedRun:
    seed: int
    elapsed_sec: float
    final: dict[str, float] = field(default_factory=dict)


@dataclass
class StepBudgetResult:
    n_steps: int
    seeds: list[SeedRun] = field(default_factory=list)
    summary: dict[str, dict[str, float]] = field(default_factory=dict)


def _bootstrap_ci(values: Sequence[float], n_boot: int = 2000, alpha: float = 0.05) -> dict:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0:
        return dict(mean=0.0, lo=0.0, hi=0.0, n=0, std=0.0)
    rng = np.random.default_rng(20260504)
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


def run_scenario_at_steps(
    name: str, n_steps: int, seeds: Sequence[int], scale: Scale,
) -> StepBudgetResult:
    runs: list[SeedRun] = []
    for s in seeds:
        cfg = apply_scale(get_scenario(name), scale)
        cfg.n_steps = n_steps
        cfg.seed = int(s)
        cfg.population.seed = int(2_000_000 + s)
        t0 = time.perf_counter()
        world = World.build(cfg)
        world.run(progress=False)
        elapsed = time.perf_counter() - t0
        last = world.metrics.history.steps[-1]
        runs.append(
            SeedRun(
                seed=int(s),
                elapsed_sec=elapsed,
                final={k: float(getattr(last, k)) for k in METRICS_OF_INTEREST},
            )
        )
    return StepBudgetResult(n_steps=n_steps, seeds=runs, summary=_summarize(runs))


def run_stability(
    scenarios: list[str],
    n_steps_grid: list[int],
    n_seeds: int,
    scale: Scale,
    output_dir: Path,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    seeds = list(range(n_seeds))
    overall: dict[str, dict] = {}
    for name in scenarios:
        print(f"\n[stability] scenario: {name}")
        per_budget: dict[int, StepBudgetResult] = {}
        for n_steps in n_steps_grid:
            print(f"  -> n_steps={n_steps:5d} (n_seeds={n_seeds}) ", end="", flush=True)
            t0 = time.perf_counter()
            res = run_scenario_at_steps(name, n_steps, seeds, scale)
            elapsed = time.perf_counter() - t0
            ci_ebi = res.summary["exo_baroque_index"]
            print(
                f"  EBI={ci_ebi['mean']:8.2f} [{ci_ebi['lo']:7.2f}, {ci_ebi['hi']:7.2f}]  "
                f"({elapsed:.1f}s)"
            )
            per_budget[n_steps] = res
        scenario_payload = {
            str(n): {
                "n_steps": res.n_steps,
                "seeds": [asdict(s) for s in res.seeds],
                "summary": res.summary,
            }
            for n, res in per_budget.items()
        }
        out_path = output_dir / f"{name}.json"
        out_path.write_text(json.dumps(scenario_payload, indent=2))
        overall[name] = scenario_payload
        print(f"  wrote {out_path}")

    summary_path = output_dir / "_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                name: {
                    n_steps_key: {
                        metric: payload["summary"][metric]
                        for metric in METRICS_OF_INTEREST
                    }
                    for n_steps_key, payload in scenario_payload.items()
                }
                for name, scenario_payload in overall.items()
            },
            indent=2,
        )
    )
    print(f"\n[stability] summary -> {summary_path}")
    return overall


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--steps", nargs="+", type=int, default=[100, 200, 400],
        help="n_steps grid to sweep.",
    )
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--scale", default="small",
                        help="Population scale (small/medium/large/xlarge).")
    parser.add_argument("--only", nargs="*", default=None,
                        help="Optional scenario allowlist.")
    parser.add_argument("--out", default="outputs/stability")
    args = parser.parse_args()

    scenarios = list(args.only) if args.only else list(SCENARIOS.keys())
    run_stability(
        scenarios=scenarios,
        n_steps_grid=list(args.steps),
        n_seeds=args.seeds,
        scale=Scale(args.scale),
        output_dir=Path(args.out),
    )


if __name__ == "__main__":
    main()

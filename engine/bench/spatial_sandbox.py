"""Spatial-sandbox benchmark — every subsystem on, SMALL scale.

The Week-1 ship-gate from `docs/plans/spatial-sandbox.md` §10:

    python engine/bench/spatial_sandbox.py

Builds a `WorldConfig` with every optional engine subsystem turned on
(norms with K=8 and certified_fraction, demand, pigouvian, registration,
institution with cross-sector firms, population dynamics, mission,
strategy, law with transaction_size_cap, regulator, and the new
ComputeConfig) at SMALL scale, runs ~60 ticks, prints p50/p95 tick
latency.

The plan's cadence fallback kicks in if p95 > 6 s/tick: cadence
`LawConfig`, `RegulatorConfig`, and `MissionConfig` to every 5 ticks.
This script flags the threshold and prints the fallback recommendation
when triggered but does not silently change the engine's per-tick
behavior — the cadence flags themselves live on each config.

Usage:
    python engine/bench/spatial_sandbox.py
    python engine/bench/spatial_sandbox.py --steps 30 --seed 11

Exit code is 0 even when the gate trips so the script remains useful
for collecting timings during tuning.
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from typing import Sequence

import numpy as np

from engine.core.population import PopulationConfig
from engine.core.topology import (
    ComputeConfig,
    DemandConfig,
    InstitutionConfig,
    LawConfig,
    MissionConfig,
    NormsConfig,
    PigouvianConfig,
    PopulationDynamicsConfig,
    RegistrationConfig,
    RegulatorConfig,
    StrategyConfig,
    TopologyConfig,
)
from engine.core.world import World, WorldConfig

# Ship-gate latency thresholds from spatial-sandbox.md §10.
P95_BUDGET_S = 6.0


def _build_spatial_sandbox_config(seed: int, n_steps: int) -> WorldConfig:
    """All-on config matching the plan's Week-1 ship-gate inventory."""
    return WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=800,
            n_agent_prototypes=87_200,  # SMALL scale (~88K prototypes total)
            seed=seed,
            network_model="sbm",
            network_p_local=0.6,
        ),
        topology=TopologyConfig(
            alpha=0.5,
            cross_stack_permeability=0.4,
            # Norms: K=8 with certified_fraction (PR #2). Spatial-sandbox
            # default per plan §3.
            norms=NormsConfig(
                enabled=True,
                n_dimensions=8,
                certified_fraction=0.5,
                certified_fraction_sd=0.15,
            ),
            # Demand-side feedback.
            demand=DemandConfig(enabled=True),
            # Pigouvian.
            pigouvian=PigouvianConfig(
                enabled=True,
                tax_rate=0.10,
                recycling="human_wealth",
            ),
            # Registration.
            registration=RegistrationConfig(enabled=True),
            # Institutions with cross-sector firms (PR #1).
            institutions=InstitutionConfig(
                enabled=True,
                cross_sector_firms=True,
            ),
            # Population dynamics.
            pop_dynamics=PopulationDynamicsConfig(enabled=True),
            # Mission economy.
            mission=MissionConfig(enabled=True),
            # Strategy (endogenous emergence).
            strategy=StrategyConfig(enabled=True),
            # Law with transaction-size cap (PR #3); cap stays at inf
            # here so the bench measures the *gate machinery on*, not
            # the windfall capture math. Toggle for a separate bench.
            law=LawConfig(enabled=True),
            # Regulator.
            regulator=RegulatorConfig(enabled=True),
            # ComputeConfig (PR #4) — spatial-sandbox default per plan §3.
            compute=ComputeConfig(
                enabled=True,
                budget_per_tick=1.0,
                power_cost_per_trade=0.0001,
                distribution="uniform",
                pool_recovery=0.0,
            ),
        ),
        n_steps=n_steps,
        pairs_per_step=20_000,
        cast_size=64,        # snapshot enrichments (PR #6)
        pair_sample_k=64,    # rich edges_v2 (PR #5)
        seed=seed,
    )


def _tick_latencies(cfg: WorldConfig) -> list[float]:
    """Run the configured world and return per-tick wall times in seconds."""
    world = World.build(cfg)
    timings: list[float] = []
    for _ in range(cfg.n_steps):
        t0 = time.perf_counter()
        world.step()
        timings.append(time.perf_counter() - t0)
    return timings


def _percentile(values: Sequence[float], p: float) -> float:
    if not values:
        return float("nan")
    return float(np.percentile(np.asarray(values), p))


def _format_report(timings: list[float]) -> str:
    p50 = _percentile(timings, 50)
    p95 = _percentile(timings, 95)
    p99 = _percentile(timings, 99)
    mean = statistics.mean(timings)
    minimum = min(timings)
    maximum = max(timings)
    lines = [
        f"ticks      {len(timings)}",
        f"min/mean   {minimum*1000:7.1f} ms / {mean*1000:7.1f} ms",
        f"p50        {p50*1000:7.1f} ms",
        f"p95        {p95*1000:7.1f} ms",
        f"p99        {p99*1000:7.1f} ms",
        f"max        {maximum*1000:7.1f} ms",
        f"gate (p95) {'PASS' if p95 < P95_BUDGET_S else 'OVER'} (budget {P95_BUDGET_S*1000:.0f} ms)",
    ]
    if p95 >= P95_BUDGET_S:
        lines.append(
            "fallback   cadence LawConfig / RegulatorConfig / MissionConfig "
            "to every 5 ticks per plan §10"
        )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--steps", type=int, default=60,
        help="ticks to run (default: 60).",
    )
    parser.add_argument(
        "--seed", type=int, default=24601,
        help="seed for the run (default: 24601).",
    )
    parser.add_argument(
        "--warmup", type=int, default=3,
        help="ticks to discard before measuring (default: 3).",
    )
    args = parser.parse_args(argv)

    if args.warmup >= args.steps:
        print(
            f"warmup ({args.warmup}) must be smaller than steps ({args.steps}); "
            "reducing warmup to 0",
            file=sys.stderr,
        )
        args.warmup = 0

    cfg = _build_spatial_sandbox_config(seed=args.seed, n_steps=args.steps)
    print(
        f"[spatial-sandbox bench] SMALL scale, every subsystem on, "
        f"seed={args.seed}, steps={args.steps}, warmup={args.warmup}"
    )
    timings = _tick_latencies(cfg)
    measured = timings[args.warmup:]
    print(_format_report(measured))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

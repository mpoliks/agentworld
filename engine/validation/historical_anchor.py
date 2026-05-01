"""Stylized historical anchor for the alpha-engine (A1).

Compares the engine's per-step `governance_overhead_fraction` (the share of
attempted Coasean transactions filtered out by the Matryoshka layers) against
the FIRE-sector share of US GDP, 1980-2024. The α-schedule is hand-picked at
face validity — a slow rise from 0.40 to 0.70 — to track the secular
intermediation trend at the schedule level, not the outcome level.

The deliverable is not a small RMSE. The deliverable is a *documented* RMSE:
the artifact exists so every future claim the engine makes has one calibrated
number it has to live next to. The empirical series is stylized; the
simulator is uncalibrated; the comparison is honest about both.

Sourcing for the empirical series lives in
`docs/concepts/historical_anchor.md`. Run the artifact with:

    agentworld validate anchor
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import numpy as np

from engine.core.world import World
from engine.scale import Scale, apply_scale
from engine.scenarios import get_scenario

# ---------------------------------------------------------------------------
# Empirical series
# ---------------------------------------------------------------------------

# US Finance + Insurance + Real Estate + Rental and Leasing as a share of GDP,
# 1980-2024 (annual). Stylized: values aggregated from BEA NIPA value-added-
# by-industry tables for the FIRE supersector. The point-precision of any one
# year is not what this anchor asks of itself; the secular shape is. See
# docs/concepts/historical_anchor.md for the table and the citation.
US_FIRE_SHARE_OF_GDP_1980_2024: tuple[float, ...] = (
    # 1980-1989
    0.158, 0.160, 0.162, 0.165, 0.168, 0.171, 0.176, 0.180, 0.183, 0.186,
    # 1990-1999
    0.190, 0.193, 0.194, 0.195, 0.196, 0.198, 0.200, 0.202, 0.204, 0.206,
    # 2000-2009
    0.208, 0.210, 0.211, 0.212, 0.211, 0.211, 0.212, 0.211, 0.214, 0.216,
    # 2010-2019
    0.214, 0.211, 0.210, 0.207, 0.205, 0.205, 0.207, 0.208, 0.209, 0.209,
    # 2020-2024
    0.213, 0.214, 0.211, 0.210, 0.211,
)

ANCHOR_YEAR_START = 1980
ANCHOR_YEAR_END = 2024
ANCHOR_N_YEARS = ANCHOR_YEAR_END - ANCHOR_YEAR_START + 1
assert len(US_FIRE_SHARE_OF_GDP_1980_2024) == ANCHOR_N_YEARS, (
    f"US_FIRE_SHARE_OF_GDP_1980_2024 has {len(US_FIRE_SHARE_OF_GDP_1980_2024)} "
    f"entries; expected {ANCHOR_N_YEARS}."
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class AnchorResult:
    years: list[int]
    empirical: list[float]
    simulated: list[float]
    rmse: float
    mae: float
    bias: float  # mean(simulated - empirical)
    largest_error_year: int
    largest_error: float
    scenario: str
    scale: str
    seed: int

    def to_dict(self) -> dict:
        return self.__dict__.copy()


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def alpha_schedule_for_anchor(n: int = ANCHOR_N_YEARS) -> list[float]:
    """Hand-picked α-schedule for the anchor: a linear rise from 0.40 to 0.70
    over 1980-2024 to approximate the secular increase in US intermediation
    intensity. The schedule is the only knob fitted; the rest of the engine
    remains at scenario defaults."""
    return list(np.linspace(0.40, 0.70, n))


def run_historical_anchor(
    scenario: str = "equilibrium_drift",
    scale: Union[str, Scale] = Scale.SMALL,
    seed: int = 0,
    progress: bool = False,
) -> AnchorResult:
    """Run the alpha-engine for ANCHOR_N_YEARS steps with the anchor schedule
    and compute the RMSE between engine `governance_overhead_fraction` and the
    empirical FIRE share."""
    cfg = get_scenario(scenario)
    cfg.n_steps = ANCHOR_N_YEARS
    cfg.alpha_schedule = alpha_schedule_for_anchor(ANCHOR_N_YEARS)
    cfg.seed = int(seed)
    cfg = apply_scale(cfg, Scale(scale) if isinstance(scale, str) else scale)

    world = World.build(cfg)
    world.run(progress=progress)
    sim = np.asarray(
        [s.governance_overhead_fraction for s in world.metrics.history.steps],
        dtype=np.float64,
    )
    emp = np.asarray(US_FIRE_SHARE_OF_GDP_1980_2024, dtype=np.float64)
    diff = sim - emp
    rmse = float(np.sqrt(float(np.mean(diff * diff))))
    mae = float(np.mean(np.abs(diff)))
    bias = float(np.mean(diff))
    biggest_idx = int(np.argmax(np.abs(diff)))
    scale_str = scale.value if isinstance(scale, Scale) else str(scale)
    return AnchorResult(
        years=list(range(ANCHOR_YEAR_START, ANCHOR_YEAR_END + 1)),
        empirical=emp.tolist(),
        simulated=sim.tolist(),
        rmse=rmse,
        mae=mae,
        bias=bias,
        largest_error_year=ANCHOR_YEAR_START + biggest_idx,
        largest_error=float(diff[biggest_idx]),
        scenario=scenario,
        scale=scale_str,
        seed=int(seed),
    )


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


def write_anchor_chart(result: AnchorResult, out_path: Path) -> None:
    """Write a two-line chart: empirical vs simulated."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=130)
    ax.plot(
        result.years, result.empirical,
        color="#5fa572", lw=2.0,
        label="US FIRE share of GDP (BEA, stylized)",
    )
    ax.plot(
        result.years, result.simulated,
        color="#b89a55", lw=2.0,
        label="engine governance_overhead_fraction",
    )
    ax.set_xlabel("year")
    ax.set_ylabel("share of activity attributed to intermediation")
    ax.set_title(
        f"Historical anchor · RMSE={result.rmse:.4f} · MAE={result.mae:.4f} · "
        f"bias={result.bias:+.4f}"
    )
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)


def write_anchor_summary(result: AnchorResult, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result.to_dict(), indent=2))

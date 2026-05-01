"""Posterior sweep over the speculative-parameter prior (A2).

Draws Sobol-quasi-random samples from the α-engine prior subset declared
in `priors.py`, runs the engine at each sample, and persists the joint
distribution of (parameters, terminal outcomes, basin classification) as
a Parquet file. Pairs with the basin-distribution chart in
`outputs/validation/posterior_sweep.png`.

The artifact answers: *under this stated prior, what is P(Smoothworld
basin), P(Baroqueworld basin), P(mixed)?* The numbers are robust to the
prior exactly to the extent that the prior is honest about what it
doesn't know.

Run with:
    agentworld validate priors --samples 256
    agentworld validate priors --samples 2000   # canonical artifact
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from engine.core.population import PopulationConfig
from engine.core.topology import TopologyConfig
from engine.core.world import World, WorldConfig
from engine.validation.priors import Prior, alpha_priors


# ---------------------------------------------------------------------------
# Basin classification
# ---------------------------------------------------------------------------

# Outcome-based classification on terminal EBI. Mirrors the dashboard's
# qualitative reading: EBI ≈ 1 is Smoothworld; EBI > 5 is Baroqueworld;
# in between is mixed. Using EBI rather than alpha because the sweep tests
# the prior's *outcome* distribution, not its input dial.
SMOOTH_EBI_MAX = 1.5
BAROQUE_EBI_MIN = 5.0


def classify(ebi: float) -> str:
    if not np.isfinite(ebi):
        return "diverged"
    if ebi <= SMOOTH_EBI_MAX:
        return "smooth"
    if ebi >= BAROQUE_EBI_MIN:
        return "baroque"
    return "mixed"


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------


def sobol_unit_samples(d: int, n: int, seed: int = 0) -> np.ndarray:
    """Sobol-quasi-random samples in [0, 1]^d."""
    from scipy.stats import qmc
    sampler = qmc.Sobol(d=d, scramble=True, seed=seed)
    return np.asarray(sampler.random(n=n), dtype=np.float64)


def project_priors(unit: np.ndarray, priors: tuple[Prior, ...]) -> list[dict]:
    """Map an (n, d) [0,1]^d Sobol matrix to a list of parameter dicts."""
    n, d = unit.shape
    assert d == len(priors), f"unit shape {unit.shape} mismatches {len(priors)} priors"
    out = []
    for i in range(n):
        row = {}
        for j, p in enumerate(priors):
            row[p.name] = p.map_unit(unit[i, j])
        out.append(row)
    return out


# ---------------------------------------------------------------------------
# Single-sample evaluation
# ---------------------------------------------------------------------------


def _build_cfg(point: dict, base_seed: int, n_steps: int) -> WorldConfig:
    """Build a tiny α-engine cfg seeded with the prior-sample point."""
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.78,
            agent_capability_sd=0.10,
            human_capability_mean=0.60,
            human_capability_sd=0.15,
            n_human_prototypes=400,
            n_agent_prototypes=4_000,
            seed=base_seed + 7,
        ),
        topology=TopologyConfig(
            alpha=0.55,  # mid-fence so the prior on folding has room
            folding_propensity=point["folding_propensity"],
            fold_real_efficiency=point["fold_real_efficiency"],
            fold_nominal_multiplier=point["fold_nominal_multiplier"],
            base_variance_absorption=point["base_variance_absorption"],
            productive_decay=point["productive_decay"],
            max_productive_real_share=point["max_productive_real_share"],
            cap_slope=point["cap_slope"],
        ),
        pairs_per_step=12_000,
        n_steps=n_steps,
        seed=base_seed,
    )


def _evaluate(point: dict, base_seed: int, n_steps: int) -> tuple[float, float]:
    cfg = _build_cfg(point, base_seed=base_seed, n_steps=n_steps)
    world = World.build(cfg)
    world.run(progress=False)
    last = world.metrics.history.steps[-1]
    return float(last.exo_baroque_index), float(last.real_per_capita_welfare)


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------


@dataclass
class PosteriorSweepSummary:
    n_samples: int
    seed: int
    n_steps: int
    elapsed_sec: float
    p_smooth: float
    p_baroque: float
    p_mixed: float
    p_diverged: float
    ebi_quantiles: dict
    welfare_quantiles: dict
    parquet_path: str

    def to_dict(self) -> dict:
        return asdict(self)


def run_posterior_sweep(
    n_samples: int = 256,
    seed: int = 0,
    n_steps: int = 20,
    progress: bool = False,
):
    """Run the sweep; return a (DataFrame, PosteriorSweepSummary) pair.

    pandas + pyarrow are required; both are already in the engine deps.
    """
    import pandas as pd

    priors = alpha_priors()
    unit = sobol_unit_samples(d=len(priors), n=n_samples, seed=seed)
    points = project_priors(unit, priors)

    started = time.time()
    iter_range = range(n_samples)
    if progress:
        try:
            from tqdm import trange
            iter_range = trange(n_samples, desc="posterior sweep", leave=False)
        except ImportError:
            pass

    rows = []
    for i in iter_range:
        ebi, welfare = _evaluate(points[i], base_seed=seed + i, n_steps=n_steps)
        row = dict(points[i])
        row["sample_idx"] = i
        row["terminal_ebi"] = ebi
        row["terminal_real_per_capita_welfare"] = welfare
        row["basin"] = classify(ebi)
        rows.append(row)

    df = pd.DataFrame(rows)

    classes = df["basin"].value_counts(normalize=True).to_dict()
    summary = PosteriorSweepSummary(
        n_samples=n_samples,
        seed=seed,
        n_steps=n_steps,
        elapsed_sec=float(time.time() - started),
        p_smooth=float(classes.get("smooth", 0.0)),
        p_baroque=float(classes.get("baroque", 0.0)),
        p_mixed=float(classes.get("mixed", 0.0)),
        p_diverged=float(classes.get("diverged", 0.0)),
        ebi_quantiles={
            "p05": float(np.quantile(df["terminal_ebi"], 0.05)),
            "p50": float(np.quantile(df["terminal_ebi"], 0.50)),
            "p95": float(np.quantile(df["terminal_ebi"], 0.95)),
        },
        welfare_quantiles={
            "p05": float(np.quantile(df["terminal_real_per_capita_welfare"], 0.05)),
            "p50": float(np.quantile(df["terminal_real_per_capita_welfare"], 0.50)),
            "p95": float(np.quantile(df["terminal_real_per_capita_welfare"], 0.95)),
        },
        parquet_path="",  # filled by caller after write
    )
    return df, summary


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------


def write_posterior_artifacts(
    df, summary: PosteriorSweepSummary, parquet_path: Path,
    summary_path: Optional[Path] = None,
    chart_path: Optional[Path] = None,
) -> None:
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(parquet_path, index=False)
    summary.parquet_path = str(parquet_path)

    if summary_path is not None:
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary.to_dict(), indent=2))

    if chart_path is not None:
        _write_basin_chart(df, summary, chart_path)


def _write_basin_chart(df, summary: PosteriorSweepSummary, out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), dpi=130)
    # Basin probabilities.
    classes = ["smooth", "mixed", "baroque", "diverged"]
    probs = [summary.p_smooth, summary.p_mixed, summary.p_baroque, summary.p_diverged]
    colors = ["#5fa572", "#5b8ec4", "#c25a5a", "#6a6d72"]
    axes[0].bar(classes, probs, color=colors)
    axes[0].set_title(
        f"Basin probabilities under the prior · n={summary.n_samples}"
    )
    axes[0].set_ylabel("P(basin)")
    for i, v in enumerate(probs):
        axes[0].text(i, v + 0.01, f"{v:.2%}", ha="center", fontsize=10)
    axes[0].set_ylim(0, max(0.05, max(probs) * 1.15))

    # Terminal EBI histogram (log-y to deal with the long tail).
    ebi_vals = np.clip(df["terminal_ebi"].values, 0, 5e3)
    axes[1].hist(ebi_vals, bins=40, color="#b89a55", edgecolor="#1a1d22", alpha=0.85)
    axes[1].set_xlabel("terminal EBI (clipped at 5000)")
    axes[1].set_ylabel("count")
    axes[1].set_yscale("log")
    axes[1].axvline(SMOOTH_EBI_MAX, color="#5fa572", ls="--", lw=1, label="smooth max")
    axes[1].axvline(BAROQUE_EBI_MIN, color="#c25a5a", ls="--", lw=1, label="baroque min")
    axes[1].legend(loc="upper right", fontsize=8)
    axes[1].set_title(
        f"Terminal EBI distribution · p50={summary.ebi_quantiles['p50']:.2f}"
    )

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)

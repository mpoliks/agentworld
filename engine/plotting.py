"""
Generate plots for each scenario and one comparative atlas.

Outputs are written to outputs/figures/.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np


SCENARIO_ORDER = [
    "coasean_paradise",
    "universal_advocate",
    "public_defender",
    "smoothing_cascade",
    "equilibrium_drift",
    "compute_famine",
    "hemispherical_schism",
    "matryoshka_collapse",
    "nimby_cascade",
    "synthetic_consumers",
    "recursive_simulation",
    "fold_avalanche",
    "slop_market",
    "baroque_cathedral",
    "exo_baroque_singularity",
]

SCENARIO_LABELS = {
    "coasean_paradise": "Coasean Paradise",
    "universal_advocate": "Universal Advocate",
    "public_defender": "Public Defender",
    "smoothing_cascade": "Smoothing Cascade",
    "equilibrium_drift": "Equilibrium Drift",
    "compute_famine": "Compute Famine",
    "hemispherical_schism": "Hemispherical Schism",
    "matryoshka_collapse": "Matryoshka Collapse",
    "nimby_cascade": "NIMBY Cascade",
    "synthetic_consumers": "Synthetic Consumers",
    "recursive_simulation": "Recursive Simulation",
    "fold_avalanche": "Fold Avalanche",
    "slop_market": "Slop Market",
    "baroque_cathedral": "Baroque Cathedral",
    "exo_baroque_singularity": "Exo-Baroque Singularity",
}


def _load_runs(runs_dir: Path) -> Dict[str, dict]:
    runs = {}
    for name in SCENARIO_ORDER:
        path = runs_dir / f"{name}.json"
        if not path.exists():
            print(f"  warning: missing {path}")
            continue
        with open(path) as f:
            runs[name] = json.load(f)
    return runs


def _setup_style():
    plt.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#222",
        "axes.labelcolor": "#222",
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.labelsize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "font.family": "DejaVu Sans",
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def plot_scenario(name: str, run: dict, out_dir: Path):
    """One 2x3 figure per scenario with the key time series."""
    h = run["history"]
    steps = h["step"]
    fig, axes = plt.subplots(2, 3, figsize=(11, 5.6))
    fig.suptitle(
        f"{SCENARIO_LABELS.get(name, name)}  ·  α_final = {run['final_alpha']:.2f}  ({run['final_label']})",
        fontsize=12, y=0.98,
    )

    # 1. alpha trajectory
    ax = axes[0, 0]
    ax.plot(steps, h["alpha"], color="#444", lw=1.6)
    ax.set_title("α (smooth ↔ striated)")
    ax.set_ylim(0, 1)
    ax.fill_between(steps, h["alpha"], 0, alpha=0.06, color="#444")

    # 2. Real welfare vs nominal GDP (cumulative)
    ax = axes[0, 1]
    ax.plot(steps, h["real_welfare_cumulative"], color="#2a8c4a", lw=1.6, label="real welfare")
    ax.plot(steps, h["nominal_gdp_cumulative"], color="#c44d4d", lw=1.6, label="nominal GDP")
    ax.set_yscale("symlog", linthresh=1e6)
    ax.set_title("cumulative real vs nominal")
    ax.legend(frameon=False, loc="upper left")

    # 3. Exo-baroque index (log scale)
    ax = axes[0, 2]
    ax.plot(steps, h["exo_baroque_index"], color="#6c3aa6", lw=1.6)
    ax.set_yscale("log")
    ax.set_title("exo-baroque index (nominal / real)")
    ax.axhline(1.0, color="#888", lw=0.6, ls="--")

    # 4. fold max depth
    ax = axes[1, 0]
    ax.plot(steps, h["fold_max_depth"], color="#3a6ca6", lw=1.6, drawstyle="steps-post")
    ax.set_title("max fold depth this step")
    ax.set_ylim(0, max(max(h["fold_max_depth"]) + 1, 6))

    # 5. Per-capita welfare and Gini
    ax = axes[1, 1]
    ax.plot(steps, h["real_per_capita_welfare"], color="#2a8c4a", lw=1.6, label="per-cap welfare")
    ax.set_ylabel("per-cap welfare", color="#2a8c4a")
    ax2 = ax.twinx()
    ax2.plot(steps, h["gini_wealth"], color="#a64d3a", lw=1.6, label="gini")
    ax2.set_ylabel("gini", color="#a64d3a")
    ax2.set_ylim(0, 1)
    ax.set_title("welfare & inequality")

    # 6. Rejection mix (stacked area)
    ax = axes[1, 2]
    rej = np.array([h["rejected_law"], h["rejected_market"], h["rejected_align"], h["rejected_cost"]])
    rej_pct = rej / np.maximum(rej.sum(axis=0), 1.0)
    ax.stackplot(steps, rej_pct,
                 labels=["law", "market", "alignment", "cost"],
                 colors=["#b85c5c", "#5c8cb8", "#5cb87a", "#b8a05c"], alpha=0.85)
    ax.set_ylim(0, 1)
    ax.set_title("rejection share by layer")
    ax.legend(frameon=False, loc="upper left", ncol=4, fontsize=7)

    for ax in axes.flat:
        ax.tick_params(direction="in", length=3)
        ax.set_xlabel("step")

    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_dir / f"{name}.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def plot_atlas(runs: Dict[str, dict], out_dir: Path):
    """One big comparative atlas: all scenarios on a single 2D plot."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.6))

    # Left: EBI vs alpha
    ax = axes[0]
    xs, ys, labels, colors = [], [], [], []
    for name, run in runs.items():
        h = run["history"]
        ebi = h["exo_baroque_index"][-1]
        alpha = run["final_alpha"]
        xs.append(alpha)
        ys.append(ebi)
        labels.append(SCENARIO_LABELS.get(name, name))
        # color by per-cap welfare
        pc = h["real_per_capita_welfare"][-1]
        colors.append(pc)
    sc = ax.scatter(xs, ys, c=colors, cmap="viridis", s=140, edgecolors="#222", linewidths=0.8)
    cb = plt.colorbar(sc, ax=ax, pad=0.02, fraction=0.04)
    cb.set_label("per-capita welfare", fontsize=8)
    for x, y, lbl in zip(xs, ys, labels):
        ax.annotate(
            lbl, (x, y),
            xytext=(6, 4), textcoords="offset points", fontsize=7,
            color="#222",
        )
    ax.set_yscale("log")
    ax.set_xlabel("α (smooth → striated)")
    ax.set_ylabel("exo-baroque index (log scale)")
    ax.set_title("Atlas of attractors", fontweight="bold")
    ax.axhline(1.0, color="#888", lw=0.7, ls="--", label="EBI = 1 (welfare = GDP)")
    ax.axvline(0.5, color="#bbb", lw=0.7, ls=":")
    ax.legend(frameon=False, loc="upper left")

    # Right: per-capita welfare vs governance overhead
    ax = axes[1]
    xs2, ys2, sizes, labels2 = [], [], [], []
    for name, run in runs.items():
        h = run["history"]
        pc = h["real_per_capita_welfare"][-1]
        gov = h["governance_overhead_fraction"][-1]
        ebi = h["exo_baroque_index"][-1]
        xs2.append(gov)
        ys2.append(pc)
        sizes.append(np.clip(np.log10(max(ebi, 1.0)) + 0.5, 0.5, 8) * 60)
        labels2.append(SCENARIO_LABELS.get(name, name))
    ax.scatter(xs2, ys2, s=sizes, c="#3a6ca6", alpha=0.7, edgecolors="#222", linewidths=0.8)
    for x, y, lbl in zip(xs2, ys2, labels2):
        ax.annotate(
            lbl, (x, y),
            xytext=(6, 4), textcoords="offset points", fontsize=7, color="#222",
        )
    ax.set_xlabel("governance overhead (rejection rate)")
    ax.set_ylabel("per-capita real welfare")
    ax.set_title("Welfare frontier", fontweight="bold")
    ax.text(0.97, 0.03, "marker size ∝ log(EBI)",
            transform=ax.transAxes, ha="right", fontsize=7, color="#666")

    fig.tight_layout()
    fig.savefig(out_dir / "atlas.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def plot_alpha_sweep(runs: Dict[str, dict], out_dir: Path):
    """Alpha vs key metrics, ordered as if a continuous sweep."""
    points = []
    for name, run in runs.items():
        h = run["history"]
        points.append((
            run["final_alpha"], name,
            h["exo_baroque_index"][-1],
            h["real_per_capita_welfare"][-1],
            h["human_legibility_index"][-1],
            h["a2a_share"][-1],
            h["governance_overhead_fraction"][-1],
        ))
    points.sort()
    alphas = [p[0] for p in points]
    ebis = [p[2] for p in points]
    pcs = [p[3] for p in points]
    legs = [p[4] for p in points]
    a2as = [p[5] for p in points]
    govs = [p[6] for p in points]

    fig, axes = plt.subplots(2, 2, figsize=(11, 6))
    fig.suptitle("Variable sweep: scenario outcomes ordered by final α",
                 fontweight="bold", fontsize=12)

    ax = axes[0, 0]
    ax.scatter(alphas, ebis, c="#6c3aa6", s=80, edgecolors="#222", linewidths=0.8)
    ax.set_yscale("log")
    ax.set_xlabel("α")
    ax.set_ylabel("EBI (log)")
    ax.set_title("Exo-baroque index vs α")
    ax.axhline(1.0, color="#888", ls="--", lw=0.6)

    ax = axes[0, 1]
    ax.scatter(alphas, pcs, c="#2a8c4a", s=80, edgecolors="#222", linewidths=0.8)
    ax.set_xlabel("α")
    ax.set_ylabel("per-capita welfare")
    ax.set_title("Welfare vs α")

    ax = axes[1, 0]
    ax.scatter(alphas, legs, c="#3a6ca6", s=80, edgecolors="#222", linewidths=0.8)
    ax.set_xlabel("α")
    ax.set_ylabel("legibility index")
    ax.set_title("Legibility (1/EBI) vs α")
    ax.set_ylim(0, 1.05)

    ax = axes[1, 1]
    ax.scatter(alphas, govs, c="#c44d4d", s=80, edgecolors="#222", linewidths=0.8)
    ax.set_xlabel("α")
    ax.set_ylabel("governance overhead")
    ax.set_title("Governance overhead vs α")
    ax.set_ylim(0, 0.4)

    for ax in axes.flat:
        ax.tick_params(direction="in", length=3)

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(out_dir / "alpha_sweep.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


def main():
    here = Path(__file__).resolve().parents[1]
    runs_dir = here / "outputs" / "runs"
    out_dir = here / "outputs" / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)

    _setup_style()
    runs = _load_runs(runs_dir)

    for name, run in runs.items():
        print(f"  plot scenario: {name}")
        plot_scenario(name, run, out_dir)

    print("  plot atlas")
    plot_atlas(runs, out_dir)
    print("  plot alpha sweep")
    plot_alpha_sweep(runs, out_dir)
    print(f"\nfigures written to {out_dir}")


if __name__ == "__main__":
    main()

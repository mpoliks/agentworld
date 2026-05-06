"""Experiment 2 — productive-folding × α grid sweep.

Holds the substrate constant (sector-block network + t-copula correlated
noise + Hawkes folding kernel) and varies two things:

    α                         ∈ {0.05, 0.15, …, 0.95}    (10 values)
    base_variance_absorption  ∈ {0.0, 0.1, 0.2, 0.35}    (4 values)

For each (α, absorption) cell we run N seeds and record terminal
median/p05/p95 of EBI, real-welfare-cumulative, nominal-GDP-cumulative,
fold-cascade volume, and human legibility (1 - a2a_share).

The base config is `baroque_cathedral` minus its α and absorption (we
reset both to the grid value), with the empirical substrate applied.
This isolates *welfare lift attributable to the productive faucet* at
each α level, independent of the topology/noise realism stack.

Outputs:
    outputs/absorption_sweep/grid.json  (one record per cell)
    outputs/absorption_sweep/grid.md    (summary table per α)

Usage:
    .venv/bin/python -m engine.absorption_sweep [--seeds N] [--workers N]
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from multiprocessing import Pool
from pathlib import Path

import numpy as np


ALPHAS = [round(0.05 + 0.10 * i, 2) for i in range(10)]   # 0.05 ... 0.95
ABSORPTIONS = [0.0, 0.1, 0.2, 0.35]


def _build_cfg(alpha: float, absorption: float, seed: int):
    """Construct a WorldConfig at this grid cell. Base = baroque_cathedral
    on the empirical substrate; α and base_variance_absorption are the
    swept variables."""
    from engine.scenarios import baroque_cathedral, _apply_empirical_substrate
    cfg = _apply_empirical_substrate(baroque_cathedral())
    cfg.topology.alpha = alpha
    cfg.topology.base_variance_absorption = absorption
    cfg.seed = seed
    cfg.population.seed = seed
    return cfg


def _run_one_cell(args):
    """Top-level for multiprocessing. Returns terminal metrics for one
    (alpha, absorption, seed) cell."""
    alpha, absorption, seed = args
    from engine.core.world import World
    from engine.scale import apply_scale, Scale
    cfg = _build_cfg(alpha, absorption, seed)
    cfg = apply_scale(cfg, Scale.SMALL)
    world = World.build(cfg)
    world.run(progress=False)
    snap = world.snapshot()
    hist = snap["history"]
    a2a = hist.get("a2a_share")
    legibility = float(1.0 - a2a[-1]) if a2a is not None and len(a2a) else float("nan")
    return {
        "alpha": alpha,
        "absorption": absorption,
        "seed": seed,
        "terminal_alpha": float(snap["alpha"]),
        "ebi": float(hist["exo_baroque_index"][-1]),
        "welfare_cum": float(hist["real_welfare_cumulative"][-1]),
        "nominal_cum": float(hist["nominal_gdp_cumulative"][-1]),
        "subm_per_step": float(hist["n_sub_markets_added"][-1]),
        "legibility": legibility,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=16)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--base-seed", type=int, default=20260430)
    parser.add_argument("--out", type=Path, default=Path("outputs/absorption_sweep"))
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    cells = [
        (a, abs_, args.base_seed + s)
        for a in ALPHAS
        for abs_ in ABSORPTIONS
        for s in range(args.seeds)
    ]
    n_total = len(cells)
    print(f"[absorption-sweep] {len(ALPHAS)} α × {len(ABSORPTIONS)} absorption × {args.seeds} seeds "
          f"= {n_total} sims, {args.workers} workers. starting at {time.strftime('%H:%M:%S')}.")

    overall_t0 = time.perf_counter()
    results = []
    if args.workers <= 1:
        for j, c in enumerate(cells, start=1):
            results.append(_run_one_cell(c))
            if j % 16 == 0 or j == n_total:
                running = time.perf_counter() - overall_t0
                rate = j / max(running, 1e-9)
                eta = (n_total - j) / max(rate, 1e-9)
                print(f"[absorption-sweep] [{j}/{n_total}] running {running/60:.1f} min, eta {eta/60:.1f} min")
    else:
        with Pool(processes=args.workers) as pool:
            for j, r in enumerate(pool.imap_unordered(_run_one_cell, cells, chunksize=1), start=1):
                results.append(r)
                if j % 16 == 0 or j == n_total:
                    running = time.perf_counter() - overall_t0
                    rate = j / max(running, 1e-9)
                    eta = (n_total - j) / max(rate, 1e-9)
                    print(f"[absorption-sweep] [{j}/{n_total}] running {running/60:.1f} min, eta {eta/60:.1f} min")

    # Aggregate per (alpha, absorption) cell.
    grid = {}
    for r in results:
        key = (r["alpha"], r["absorption"])
        grid.setdefault(key, []).append(r)

    summary = []
    for (a, abs_), rows in sorted(grid.items()):
        ebi = np.array([r["ebi"] for r in rows])
        wcum = np.array([r["welfare_cum"] for r in rows])
        ncum = np.array([r["nominal_cum"] for r in rows])
        subm = np.array([r["subm_per_step"] for r in rows])
        leg = np.array([r["legibility"] for r in rows])
        summary.append({
            "alpha": a,
            "absorption": abs_,
            "n": len(rows),
            "ebi_median": float(np.median(ebi)),
            "ebi_p05": float(np.percentile(ebi, 5)),
            "ebi_p95": float(np.percentile(ebi, 95)),
            "welfare_cum_median": float(np.median(wcum)),
            "welfare_cum_p05": float(np.percentile(wcum, 5)),
            "welfare_cum_p95": float(np.percentile(wcum, 95)),
            "nominal_cum_median": float(np.median(ncum)),
            "subm_per_step_median": float(np.median(subm)),
            "legibility_median": float(np.median(leg)),
        })

    out_json = args.out / "grid.json"
    out_json.write_text(json.dumps({
        "alphas": ALPHAS,
        "absorptions": ABSORPTIONS,
        "n_seeds": args.seeds,
        "summary": summary,
        "raw": results,
    }, indent=2))
    print(f"[absorption-sweep] -> {out_json}")

    # Markdown summary: one section per α with the 4 absorption rows.
    md = ["# Absorption sweep — productive folding × α\n",
          "Substrate held constant: sector-block network + t-copula noise + Hawkes folding. Base = `baroque_cathedral` minus α and absorption (both swept). Each row aggregates 16 seeds.\n"]
    md.append("| α | absorption | EBI median | welfare median | sub-markets/step | legibility median |")
    md.append("| ---: | ---: | ---: | ---: | ---: | ---: |")
    for s in summary:
        md.append(
            f"| {s['alpha']:.2f} | {s['absorption']:.2f} "
            f"| {_fmt(s['ebi_median'])} | {_fmt(s['welfare_cum_median'])} "
            f"| {_fmt(s['subm_per_step_median'])} | {_fmt(s['legibility_median'])} |"
        )
    out_md = args.out / "grid.md"
    out_md.write_text("\n".join(md) + "\n")
    print(f"[absorption-sweep] -> {out_md}")

    elapsed = time.perf_counter() - overall_t0
    print(f"[absorption-sweep] done in {elapsed/60:.1f} min")


def _fmt(v: float) -> str:
    if v == 0:
        return "0"
    av = abs(v)
    if av >= 1e6 or (av != 0 and av < 1e-3):
        return f"{v:.2e}"
    if av >= 1e3:
        return f"{v:,.0f}"
    if av >= 1:
        return f"{v:.2f}"
    return f"{v:.4f}"


if __name__ == "__main__":
    main()

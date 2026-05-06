"""Experiment 1 — empirical substrate, productive levers off.

For each scenario in SCENARIO_ORDER (the 25 dashboard scenarios, minus
baroque_cathedral_networked which already carries the substrate), run an
N=32 ensemble of its `_anchored` variant (sector-block network + t-copula
correlated noise + Hawkes folding kernel, with productive folding and
demand weighting *off*). Then read the existing plain ensembles and emit
a side-by-side comparison so we can see how much of the welfare lift in
Productive Cathedral comes from the realism stack vs the productive
faucet.

Outputs:
    outputs/substrate_sweep/<name>_anchored.bands.json     (one per scenario)
    outputs/substrate_sweep/<name>_anchored.parquet
    outputs/substrate_sweep/comparison.json                (side-by-side numbers)
    outputs/substrate_sweep/comparison.md                  (human-readable table)

Usage:
    .venv/bin/python -m engine.substrate_sweep [--workers N] [--seeds N]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

# These are the dashboard's 25 scenarios. We mirror the list locally to
# avoid importing build_dashboard (which would create a circular dep).
DASHBOARD_SCENARIOS = [
    "coasean_paradise", "universal_advocate", "public_defender",
    "civic_renaissance", "synthetic_consumers_v2", "smoothing_cascade",
    "equilibrium_drift", "matryoshka_collapse", "hemispherical_schism",
    "compute_famine", "derivatives_revolution", "legal_collapse",
    "regulatory_capture", "endogenous_baroque", "pigouvian_heavy",
    "pigouvian_friction", "full_emergence", "recursive_simulation",
    "fold_avalanche", "slop_market", "productive_baroque",
    "baroque_with_high_welfare", "baroque_cathedral",
    "baroque_cathedral_networked", "exo_baroque_singularity",
]
# Skip the one that already has the substrate-with-productive-on stack —
# it's the comparison's right-hand cell, not a scenario to anchor.
SUBSTRATE_TARGETS = [n for n in DASHBOARD_SCENARIOS if n != "baroque_cathedral_networked"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seeds", type=int, default=32)
    parser.add_argument("--out", type=Path, default=Path("outputs/substrate_sweep"))
    parser.add_argument("--plain-dir", type=Path, default=Path("outputs/ensembles"),
                        help="Directory holding the existing plain-scenario ensemble bands.")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Skip scenarios whose anchored bands JSON already exists.")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    from engine.ensemble import run_ensemble
    from engine.scale import Scale

    print(f"[substrate-sweep] {len(SUBSTRATE_TARGETS)} scenarios × {args.seeds} seeds, "
          f"{args.workers} workers, scale=small. starting at {time.strftime('%H:%M:%S')}.")
    overall_t0 = time.perf_counter()
    for i, base_name in enumerate(SUBSTRATE_TARGETS, start=1):
        anchored = f"{base_name}_anchored"
        out_path = args.out / f"{anchored}.bands.json"
        if args.skip_existing and out_path.exists():
            print(f"[substrate-sweep] [{i}/{len(SUBSTRATE_TARGETS)}] {anchored} — skipping (exists)")
            continue
        t0 = time.perf_counter()
        run_ensemble(
            anchored,
            n_seeds=args.seeds,
            scale=Scale.SMALL,
            n_workers=args.workers,
            output_dir=args.out,
            progress=False,
        )
        elapsed = time.perf_counter() - t0
        running = time.perf_counter() - overall_t0
        print(f"[substrate-sweep] [{i}/{len(SUBSTRATE_TARGETS)}] {anchored} done in {elapsed:.0f}s "
              f"(total {running/60:.1f} min)")

    write_comparison(args.out, args.plain_dir)
    total = time.perf_counter() - overall_t0
    print(f"[substrate-sweep] all done in {total/60:.1f} min")


def write_comparison(anchored_dir: Path, plain_dir: Path) -> None:
    """Compare terminal EBI / welfare / fold-cascade volume between plain
    and anchored ensembles for each dashboard scenario."""
    rows = []
    for base_name in DASHBOARD_SCENARIOS:
        plain_path = plain_dir / f"{base_name}.bands.json"
        anch_path = anchored_dir / f"{base_name}_anchored.bands.json"
        plain = _load(plain_path)
        anch = _load(anch_path)
        if plain is None or anch is None:
            continue
        row = {
            "name": base_name,
            "plain": _terminal(plain),
            "anchored": _terminal(anch),
        }
        # Deltas
        row["delta"] = {
            "ebi_pct": _pct_delta(row["plain"]["ebi_median"], row["anchored"]["ebi_median"]),
            "welfare_pct": _pct_delta(row["plain"]["welfare_cum_median"], row["anchored"]["welfare_cum_median"]),
            "subm_pct": _pct_delta(row["plain"]["subm_step_median"], row["anchored"]["subm_step_median"]),
        }
        rows.append(row)

    out_json = anchored_dir / "comparison.json"
    out_json.write_text(json.dumps(rows, indent=2))
    print(f"[substrate-sweep] comparison json -> {out_json}")

    md = ["# Substrate sweep — plain vs anchored\n",
          "Each row: a dashboard scenario run (a) plain (existing ensemble bands) and (b) on the empirical substrate (sector-block network + t-copula noise + Hawkes folding) with `base_variance_absorption=0` and `DemandConfig.enabled=False`. Deltas are anchored − plain in percent of plain.\n",
          "| scenario | plain EBI | anch EBI | ΔEBI | plain Wcum | anch Wcum | ΔW | plain sub-mkts/step | anch sub-mkts/step |",
          "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for r in rows:
        md.append(
            f"| {r['name']} "
            f"| {_fmt(r['plain']['ebi_median'])} | {_fmt(r['anchored']['ebi_median'])} | {r['delta']['ebi_pct']:+.0f}% "
            f"| {_fmt(r['plain']['welfare_cum_median'])} | {_fmt(r['anchored']['welfare_cum_median'])} | {r['delta']['welfare_pct']:+.0f}% "
            f"| {_fmt(r['plain']['subm_step_median'])} | {_fmt(r['anchored']['subm_step_median'])} |"
        )
    out_md = anchored_dir / "comparison.md"
    out_md.write_text("\n".join(md) + "\n")
    print(f"[substrate-sweep] comparison md -> {out_md}")


def _load(p: Path):
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def _terminal(bands: dict) -> dict:
    b = bands["bands"]
    return {
        "ebi_median": b["exo_baroque_index"]["median"][-1],
        "ebi_p05": b["exo_baroque_index"]["p05"][-1],
        "ebi_p95": b["exo_baroque_index"]["p95"][-1],
        "welfare_cum_median": b["real_welfare_cumulative"]["median"][-1],
        "welfare_cum_p05": b["real_welfare_cumulative"]["p05"][-1],
        "welfare_cum_p95": b["real_welfare_cumulative"]["p95"][-1],
        "nominal_cum_median": b["nominal_gdp_cumulative"]["median"][-1],
        "subm_step_median": b["n_sub_markets_added"]["median"][-1],
        "fold_depth_median": b["fold_max_depth"]["median"][-1],
    }


def _pct_delta(plain: float, anch: float) -> float:
    if plain == 0:
        return 0.0
    return 100.0 * (anch - plain) / abs(plain)


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

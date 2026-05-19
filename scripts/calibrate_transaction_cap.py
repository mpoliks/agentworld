"""Calibrate LawConfig.transaction_size_cap against the spatial_sandbox
per-pair surplus distribution.

For each candidate cap, run the canonical spatial_sandbox at the same
downscale used by `test_firms_form_and_persist_under_sandbox_defaults`
(n_human=200, n_agent=1800, pairs_per_step=20_000, 100 ticks) and
report:

  - total windfall_tax_revenue across the run (does the cap bite?)
  - share of total real surplus captured by the cap
  - firms formed and median lifetime (does the cap break institutions?)

The sweet spot is the highest cap value where windfall_revenue / real_surplus
is non-trivial (say >= 1%) AND firms still form persistently.

Usage:  uv run python scripts/calibrate_transaction_cap.py
"""
from __future__ import annotations

import math

import numpy as np

from engine.core.world import World
from engine.scenarios import get_scenario


CAPS = [
    math.inf,    # baseline — should be 0 windfall, firms form normally
    0.5, 0.4, 0.3, 0.25, 0.2, 0.15, 0.1, 0.05,
]


def run_one(cap: float, n_steps: int = 100) -> dict:
    cfg = get_scenario("spatial_sandbox")
    cfg.population.n_human_prototypes = 200
    cfg.population.n_agent_prototypes = 1_800
    cfg.cast_size = 500
    cfg.pair_sample_k = 128
    cfg.pairs_per_step = 20_000
    cfg.n_steps = n_steps
    cfg.topology.law.transaction_size_cap = cap

    world = World.build(cfg)
    windfall_total = 0.0
    real_total = 0.0
    final_gini = 0.0
    sector_welfare_cum = None
    first_seen: dict[int, int] = {}
    last_seen: dict[int, int] = {}
    for t in range(n_steps):
        m = world.step()
        windfall_total += float(m.windfall_tax_revenue_step)
        real_total += float(m.real_welfare_step)
        final_gini = float(m.gini_wealth)
        sw = np.asarray(m.real_welfare_per_sector_step, dtype=np.float64)
        if sector_welfare_cum is None:
            sector_welfare_cum = sw.copy()
        else:
            sector_welfare_cum += sw
        fid = world.population.firm_id
        for f in np.unique(fid[fid >= 0]):
            f = int(f)
            first_seen.setdefault(f, t)
            last_seen[f] = t

    if sector_welfare_cum is not None and sector_welfare_cum.sum() > 0:
        shares = sector_welfare_cum / sector_welfare_cum.sum()
        top1_share = float(shares.max())
        hhi = float((shares * shares).sum())
    else:
        top1_share = 0.0
        hhi = 0.0

    lifetimes = [last_seen[f] - first_seen[f] + 1 for f in first_seen]
    median_lifetime = float(np.median(lifetimes)) if lifetimes else 0.0
    long_lived_pct = (
        sum(1 for L in lifetimes if L >= 30) / len(lifetimes)
        if lifetimes else 0.0
    )
    gross = windfall_total + real_total
    share = windfall_total / gross if gross > 0 else 0.0
    return {
        "cap": cap,
        "windfall_total": windfall_total,
        "real_total": real_total,
        "windfall_share": share,
        "firms_formed": len(first_seen),
        "median_lifetime": median_lifetime,
        "long_lived_pct": long_lived_pct,
        "final_gini": final_gini,
        "top1_sector_share": top1_share,
        "sector_hhi": hhi,
    }


def fmt_cap(cap: float) -> str:
    if cap == math.inf:
        return "inf"
    return f"{cap:.0e}"


def main() -> None:
    print(
        f"{'cap':>8}  {'windfall%':>9}  {'firms':>5}  {'long%':>6}  "
        f"{'gini':>6}  {'top1_sect':>9}  {'sect_HHI':>8}"
    )
    print("-" * 75)
    for cap in CAPS:
        r = run_one(cap)
        print(
            f"{fmt_cap(r['cap']):>8}  "
            f"{r['windfall_share']*100:>8.2f}%  "
            f"{r['firms_formed']:>5d}  "
            f"{r['long_lived_pct']*100:>5.0f}%  "
            f"{r['final_gini']:>6.3f}  "
            f"{r['top1_sector_share']*100:>8.1f}%  "
            f"{r['sector_hhi']:>8.3f}"
        )


if __name__ == "__main__":
    main()

"""
Microbenchmark harness for the alpha-engine hot paths.

Used to establish baselines and verify each optimization in the 88K -> 88M
scale-up. Times the five operations that dominate the per-step cost:
    - Population.synthesize
    - _sample_partners (the per-step partner sampling)
    - coasean_step (the full per-step transaction kernel)
    - fold_surplus (per-step folding operator)
    - gini_coefficient (the O(n log n) sort used by metrics)
    - np.add.at vs np.bincount scatter (the wealth-update pattern)

Usage:
    PYTHONPATH=. python engine/perf.py baseline small medium large
    PYTHONPATH=. python engine/perf.py optimized small medium large xlarge

Each label writes outputs/perf/<label>.json.
"""

from __future__ import annotations

import gc
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from engine.core.folding import fold_surplus
from engine.core.metrics import gini_coefficient
from engine.core.population import Population, PopulationConfig
from engine.core.topology import Topology, TopologyConfig
from engine.core.transactions import _sample_partners, coasean_step


SCALE_PRESETS = {
    "small":  dict(n_h=8_000,     n_a=80_000,     n_pairs=200_000),
    "medium": dict(n_h=80_000,    n_a=800_000,    n_pairs=500_000),
    "large":  dict(n_h=800_000,   n_a=8_000_000,  n_pairs=2_000_000),
    "xlarge": dict(n_h=8_000_000, n_a=80_000_000, n_pairs=5_000_000),
}


def _time(fn: Callable, *, repeat: int = 3) -> tuple[float, float, float]:
    """Return (mean_ms, std_ms, min_ms) for `fn` over `repeat` calls."""
    times = []
    for _ in range(repeat):
        gc.collect()
        t0 = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t0)
    arr = np.asarray(times) * 1000.0
    return float(arr.mean()), float(arr.std()), float(arr.min())


@dataclass
class BenchResult:
    scale: str
    op: str
    n: int
    mean_ms: float
    std_ms: float
    min_ms: float
    n_repeats: int


def bench_scale(scale: str) -> list[BenchResult]:
    cfg = SCALE_PRESETS[scale]
    n_h, n_a, n_pairs = cfg["n_h"], cfg["n_a"], cfg["n_pairs"]
    n_total = n_h + n_a
    print(f"[bench] {scale:6s}  n_total={n_total:>11,d}  n_pairs={n_pairs:>10,d}")

    results: list[BenchResult] = []

    pcfg = PopulationConfig(
        n_human_prototypes=n_h, n_agent_prototypes=n_a, seed=0,
    )

    t_synth = _time(lambda: Population.synthesize(pcfg), repeat=2)
    print(f"  synthesize        {t_synth[0]:>10.1f} ms (min {t_synth[2]:.1f})")
    results.append(BenchResult(scale, "synthesize", n_total, *t_synth, 2))

    pop = Population.synthesize(pcfg)
    topo = Topology.build(TopologyConfig())
    rng = np.random.default_rng(0)

    t_sample = _time(lambda: _sample_partners(pop, topo, n_pairs, rng), repeat=3)
    print(f"  _sample_partners  {t_sample[0]:>10.1f} ms (min {t_sample[2]:.1f})")
    results.append(BenchResult(scale, "_sample_partners", n_pairs, *t_sample, 3))

    t_step = _time(lambda: coasean_step(pop, topo, rng, n_pairs=n_pairs), repeat=3)
    print(f"  coasean_step      {t_step[0]:>10.1f} ms (min {t_step[2]:.1f})")
    results.append(BenchResult(scale, "coasean_step", n_pairs, *t_step, 3))

    t_fold = _time(lambda: fold_surplus(1e6, 1e6, topo, rng), repeat=5)
    print(f"  fold_surplus      {t_fold[0]:>10.1f} ms (min {t_fold[2]:.1f})")
    results.append(BenchResult(scale, "fold_surplus", 1, *t_fold, 5))

    t_gini = _time(lambda: gini_coefficient(pop.wealth, pop.weight), repeat=2)
    print(f"  gini_coefficient  {t_gini[0]:>10.1f} ms (min {t_gini[2]:.1f})")
    results.append(BenchResult(scale, "gini_coefficient", n_total, *t_gini, 2))

    a = rng.integers(0, n_total, size=n_pairs).astype(np.intp)
    contribs = rng.standard_normal(n_pairs).astype(np.float64)
    wealth_delta_buf = np.zeros(n_total, dtype=np.float64)

    def _scatter_addat():
        wealth_delta_buf.fill(0.0)
        np.add.at(wealth_delta_buf, a, contribs)

    t_scatter = _time(_scatter_addat, repeat=3)
    print(f"  scatter add.at    {t_scatter[0]:>10.1f} ms (min {t_scatter[2]:.1f})")
    results.append(BenchResult(scale, "scatter_add_at", n_pairs, *t_scatter, 3))

    def _scatter_bincount():
        np.bincount(a, weights=contribs, minlength=n_total)

    t_bincount = _time(_scatter_bincount, repeat=3)
    print(f"  scatter bincount  {t_bincount[0]:>10.1f} ms (min {t_bincount[2]:.1f})")
    results.append(BenchResult(scale, "scatter_bincount", n_pairs, *t_bincount, 3))

    return results


def bench(scales: Sequence[str], output_path: Path, label: str) -> list[BenchResult]:
    all_results: list[BenchResult] = []
    for scale in scales:
        all_results.extend(bench_scale(scale))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "label": label,
        "results": [asdict(r) for r in all_results],
    }
    output_path.write_text(json.dumps(payload, indent=2))
    print(f"[bench] wrote {len(all_results)} rows to {output_path}")
    return all_results


def main(argv: list[str]) -> None:
    label = argv[1] if len(argv) > 1 else "baseline"
    scales = argv[2:] if len(argv) > 2 else ["small", "medium"]
    out = Path(f"outputs/perf/{label}.json")
    bench(scales, out, label=label)


if __name__ == "__main__":
    main(sys.argv)

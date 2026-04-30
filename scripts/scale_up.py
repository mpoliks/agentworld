#!/usr/bin/env python
"""
scripts/scale_up.py — fire-and-forget runner for the 88K -> 88M scale-up.

Runs the full sequence:

  1. Microbench at small + medium + large (optimized) and writes
     outputs/perf/optimized.json. Compares against outputs/perf/baseline.json
     if it exists.

  2. Single xlarge sanity-check run on `coasean_paradise` to confirm an
     88M-prototype scenario completes within budget.

  3. run-all at the requested scale (--scale, default large) with parallel
     workers (--workers, default os.cpu_count()//2). Writes
     outputs/runs/<scenario>.json.

  4. Convergence harness: each scenario at small / medium / large with
     --conv-seeds (default 3) seeds. Writes outputs/convergence/<scenario>.json.

  5. Re-bake the dashboard from the latest outputs/runs/.

  6. Print a final summary report (timings, peak RAM if available).

Run:

    PYTHONPATH=. python scripts/scale_up.py
    PYTHONPATH=. python scripts/scale_up.py --scale xlarge --workers 2
    PYTHONPATH=. python scripts/scale_up.py --skip bench dashboard

Each phase is independently skippable with --skip {bench,sanity,runall,convergence,dashboard}.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _section(title: str) -> None:
    bar = "=" * len(title)
    print(f"\n{bar}\n{title}\n{bar}", flush=True)


def _peak_rss_mb() -> float:
    """Best-effort peak resident set size in MB (Linux/macOS)."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # ru_maxrss is in KB on Linux, bytes on macOS.
    if sys.platform == "darwin":
        return usage.ru_maxrss / (1024 * 1024)
    return usage.ru_maxrss / 1024


def phase_bench(scales: Sequence[str], out_path: Path) -> dict:
    from engine.perf import bench
    _section(f"[1/5] microbenchmark: optimized at {scales}")
    bench(list(scales), out_path, label="optimized")
    return {"path": str(out_path)}


def phase_sanity(scenario: str, scale: str) -> dict:
    from engine.runner import run_scenario
    from engine.scale import Scale
    _section(f"[2/5] sanity check: {scenario} at {scale}")
    t0 = time.perf_counter()
    res = run_scenario(
        scenario,
        output_dir=Path("outputs/sanity"),
        progress=False,
        scale=Scale(scale),
    )
    elapsed = time.perf_counter() - t0
    print(
        f"  done in {elapsed:.1f}s  alpha={res.final_alpha:.3f}  "
        f"label={res.final_label}  peak={_peak_rss_mb():.1f} MB"
    )
    return {
        "scenario": scenario,
        "scale": scale,
        "elapsed_sec": elapsed,
        "final_alpha": res.final_alpha,
        "label": res.final_label,
        "peak_rss_mb": _peak_rss_mb(),
    }


def phase_runall(scale: str, n_workers: int) -> dict:
    from engine.runner import run_all
    from engine.scale import Scale
    _section(f"[3/5] run-all at {scale} with {n_workers} workers")
    t0 = time.perf_counter()
    results = run_all(
        output_dir=Path("outputs/runs"),
        progress=False,
        scale=Scale(scale),
        n_workers=n_workers,
    )
    elapsed = time.perf_counter() - t0
    print(f"  total {elapsed:.1f}s for {len(results)} scenarios")
    timings = sorted(
        ((name, r.elapsed_sec) for name, r in results.items()),
        key=lambda kv: -kv[1],
    )
    return {
        "scale": scale,
        "n_workers": n_workers,
        "wall_sec": elapsed,
        "scenarios": {name: r.elapsed_sec for name, r in results.items()},
        "slowest": timings[:5],
    }


def phase_convergence(scales: Sequence[str], n_seeds: int) -> dict:
    from engine.convergence import run_convergence
    from engine.scale import Scale
    from engine.scenarios import SCENARIOS
    _section(f"[4/5] convergence: {len(SCENARIOS)} scenarios x {scales} x {n_seeds} seeds")
    t0 = time.perf_counter()
    overall = run_convergence(
        scenarios=list(SCENARIOS.keys()),
        scales=[Scale(s) for s in scales],
        n_seeds=n_seeds,
        n_steps=None,
        output_dir=Path("outputs/convergence"),
    )
    elapsed = time.perf_counter() - t0
    print(f"  convergence took {elapsed:.1f}s")
    return {"wall_sec": elapsed, "n_scenarios": len(overall), "scales": list(scales)}


def phase_dashboard() -> dict:
    _section("[5/5] re-bake dashboard")
    t0 = time.perf_counter()
    subprocess.run(
        [sys.executable, "engine/build_dashboard.py"],
        check=True,
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    elapsed = time.perf_counter() - t0
    out_path = ROOT / "dashboard" / "index.html"
    size_mb = out_path.stat().st_size / (1024 * 1024) if out_path.exists() else 0.0
    print(f"  rebuilt in {elapsed:.1f}s ({size_mb:.2f} MB)")
    return {"wall_sec": elapsed, "dashboard_mb": size_mb}


def write_summary(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    print(f"\nfull report -> {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scale", default="large",
        choices=["small", "medium", "large", "xlarge"],
        help="Scale for run-all (default: large; xlarge needs ~5 GB/worker).",
    )
    parser.add_argument(
        "--workers", type=int, default=max(1, (os.cpu_count() or 4) // 2),
        help="Parallel workers for run-all (each holds full population).",
    )
    parser.add_argument(
        "--bench-scales", nargs="+",
        default=["small", "medium", "large"],
        help="Which scales to microbench. Add 'xlarge' to validate 88M.",
    )
    parser.add_argument(
        "--sanity-scale", default="xlarge",
        choices=["small", "medium", "large", "xlarge"],
        help="Scale for the single-scenario sanity check.",
    )
    parser.add_argument(
        "--sanity-scenario", default="coasean_paradise",
    )
    parser.add_argument(
        "--conv-scales", nargs="+",
        default=["small", "medium", "large"],
        help="Scales for the convergence sweep.",
    )
    parser.add_argument(
        "--conv-seeds", type=int, default=3,
        help="Seeds per (scenario, scale) for the convergence sweep.",
    )
    parser.add_argument(
        "--skip", nargs="*", default=[],
        choices=["bench", "sanity", "runall", "convergence", "dashboard"],
        help="Phases to skip.",
    )
    args = parser.parse_args()

    t0 = time.perf_counter()
    report: dict = {
        "args": vars(args),
        "phases": {},
    }

    if "bench" not in args.skip:
        report["phases"]["bench"] = phase_bench(
            args.bench_scales, Path("outputs/perf/optimized.json"),
        )

    if "sanity" not in args.skip:
        report["phases"]["sanity"] = phase_sanity(
            args.sanity_scenario, args.sanity_scale,
        )

    if "runall" not in args.skip:
        report["phases"]["runall"] = phase_runall(args.scale, args.workers)

    if "convergence" not in args.skip:
        report["phases"]["convergence"] = phase_convergence(
            args.conv_scales, args.conv_seeds,
        )

    if "dashboard" not in args.skip:
        report["phases"]["dashboard"] = phase_dashboard()

    report["wall_sec"] = time.perf_counter() - t0
    report["peak_rss_mb"] = _peak_rss_mb()

    write_summary(report, Path("outputs/scale_up_report.json"))

    print(
        f"\n[done] total {report['wall_sec']:.1f}s "
        f"peak RSS {report['peak_rss_mb']:.0f} MB"
    )


if __name__ == "__main__":
    main()

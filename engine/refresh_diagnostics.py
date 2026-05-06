"""Refresh §3 convergence/stability and §7 Sobol on the option-3 substrate.

Three sub-commands:

    convergence    : sweep population scale (small + medium) × 8 seeds for
                     the 25 dashboard scenarios.
    stability      : sweep n_steps (100, 200, 400) × 8 seeds for the same.
    sobol-alpha    : 15-parameter Saltelli/Sobol on the alpha-engine, with
                     the empirical topology baked in (substrate-honest).
    sobol-exo      : exo-engine Sobol (separate engine, separate config).
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path


DASHBOARD_25 = [
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


def cmd_convergence(args):
    """Convergence under the substrate switch is small-scale-only.

    The reason: medium scale (660K–880K prototypes) exceeds
    `MAX_NETWORK_NODES = 200_000`, so the SBM falls back to well-mixed
    sampling at that scale. Comparing small@SBM to medium@well-mixed is a
    confounded test (it conflates scale variance with substrate change).
    Until/unless we raise the network-node ceiling and pay the memory
    cost, the small-scale CI on terminal EBI is what the §3 panel reads.
    """
    from engine.convergence import run_convergence
    from engine.scale import Scale
    print(f"[convergence] {len(DASHBOARD_25)} scenarios × small × {args.seeds} seeds")
    t0 = time.perf_counter()
    run_convergence(
        scenarios=DASHBOARD_25,
        scales=[Scale.SMALL],
        n_seeds=args.seeds,
        n_steps=None,
        output_dir=Path(args.out),
    )
    print(f"[convergence] done in {(time.perf_counter()-t0)/60:.1f} min")


def cmd_stability(args):
    from engine.stability import run_stability
    from engine.scale import Scale
    print(f"[stability] {len(DASHBOARD_25)} scenarios × n_steps={args.steps} × {args.seeds} seeds")
    t0 = time.perf_counter()
    run_stability(
        scenarios=DASHBOARD_25,
        n_steps_grid=args.steps,
        n_seeds=args.seeds,
        scale=Scale.SMALL,
        output_dir=Path(args.out),
    )
    print(f"[stability] done in {(time.perf_counter()-t0)/60:.1f} min")


def cmd_sobol_alpha(args):
    from engine.sensitivity import run_sobol_sensitivity
    print(f"[sobol-alpha] N_base={args.samples} (~{args.samples * 17} sims, 15-param substrate-on)")
    t0 = time.perf_counter()
    run_sobol_sensitivity(
        n_base_samples=args.samples,
        output_path=Path(args.out),
    )
    print(f"[sobol-alpha] done in {(time.perf_counter()-t0)/60:.1f} min")


def cmd_sobol_exo(args):
    from engine.exo.sweep import run_exo_sobol
    print(f"[sobol-exo] N_base={args.samples}")
    t0 = time.perf_counter()
    run_exo_sobol(
        n_base_samples=args.samples,
        output_path=Path(args.out),
        progress=False,
    )
    print(f"[sobol-exo] done in {(time.perf_counter()-t0)/60:.1f} min")


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("convergence")
    c.add_argument("--seeds", type=int, default=8)
    c.add_argument("--out", default="outputs/convergence")
    c.set_defaults(func=cmd_convergence)

    st = sub.add_parser("stability")
    st.add_argument("--seeds", type=int, default=8)
    st.add_argument("--steps", type=int, nargs="+", default=[100, 200, 400])
    st.add_argument("--out", default="outputs/stability")
    st.set_defaults(func=cmd_stability)

    sa = sub.add_parser("sobol-alpha")
    sa.add_argument("--samples", type=int, default=2048)
    sa.add_argument("--out", default="outputs/sensitivity/sobol_indices.json")
    sa.set_defaults(func=cmd_sobol_alpha)

    se = sub.add_parser("sobol-exo")
    se.add_argument("--samples", type=int, default=128)
    se.add_argument("--out", default="outputs/sensitivity/exo_sobol_indices.json")
    se.set_defaults(func=cmd_sobol_exo)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

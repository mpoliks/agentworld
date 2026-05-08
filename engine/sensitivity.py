"""Phase-space and sensitivity tools for Agentworld.

Two complementary instruments live here:

    * `run_phase_space_sweep` — the original 2-D OAT alpha/capability grid.
      Cheap, narrative, useful for the dashboard's "basin map" panel.
      Kept as the legacy `agentworld sweep` command.

    * `run_sobol_sensitivity` — Saltelli/Sobol global sensitivity over the
      full alpha-engine parameter set. Reports first-order (S1) and
      total-order (ST) variance indices for the terminal EBI, real
      per-capita welfare, and Gini. This is the discipline-of-uncertainty
      upgrade — see `docs/concepts/epistemic_status.md` for what a Sobol
      index does and doesn't tell you.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

from engine.core.population import PopulationConfig
from engine.core.topology import TopologyConfig
from engine.core.world import World, WorldConfig


@dataclass(frozen=True)
class SweepPoint:
    """Terminal metrics for one point in the alpha/capability grid."""

    alpha: float
    agent_capability_mean: float
    human_capability_mean: float
    ebi: float
    real_per_capita_welfare: float
    gini_wealth: float
    human_legibility_index: float
    governance_overhead_fraction: float
    fold_max_depth: int
    basin: str


@dataclass(frozen=True)
class SweepSummary:
    """A compact account of the phase-space sweep."""

    points: list[SweepPoint]
    alpha_values: list[float]
    capability_values: list[float]
    n_steps: int
    pairs_per_step: int
    n_human_prototypes: int
    n_agent_prototypes: int

    def to_dict(self) -> dict:
        return {
            "points": [asdict(p) for p in self.points],
            "alpha_values": self.alpha_values,
            "capability_values": self.capability_values,
            "n_steps": self.n_steps,
            "pairs_per_step": self.pairs_per_step,
            "n_human_prototypes": self.n_human_prototypes,
            "n_agent_prototypes": self.n_agent_prototypes,
        }


def classify_basin(ebi: float, welfare: float, legibility: float) -> str:
    """Name the local attractor basin implied by terminal metrics."""
    if ebi < 2.0 and legibility > 0.5:
        return "smooth"
    if ebi >= 100.0 and welfare < 0.03:
        return "slop"
    if ebi >= 100.0:
        return "baroque"
    if ebi >= 10.0:
        return "striated"
    return "mixed"


def _point_config(
    *,
    alpha: float,
    capability: float,
    n_steps: int,
    pairs_per_step: int,
    n_human_prototypes: int,
    n_agent_prototypes: int,
    seed: int,
) -> WorldConfig:
    human_capability = max(0.05, capability - 0.18)
    return WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=n_human_prototypes,
            n_agent_prototypes=n_agent_prototypes,
            human_capability_mean=human_capability,
            human_capability_sd=0.13,
            agent_capability_mean=capability,
            agent_capability_sd=0.16,
            seed=seed,
        ),
        topology=TopologyConfig(
            alpha=alpha,
            base_friction=0.055,
            folding_propensity=0.58,
            folding_branching=2.9,
            folding_max_depth=7,
            fold_nominal_multiplier=1.95,
            fold_real_efficiency=0.90,
            cross_stack_compat=0.55,
        ),
        n_steps=n_steps,
        pairs_per_step=pairs_per_step,
        seed=seed,
    )


def run_phase_space_sweep(
    *,
    alpha_values: Sequence[float] | None = None,
    capability_values: Sequence[float] | None = None,
    n_steps: int = 18,
    pairs_per_step: int = 20_000,
    n_human_prototypes: int = 600,
    n_agent_prototypes: int = 6_000,
    output_path: Path | None = None,
    seed: int = 20260429,
) -> SweepSummary:
    """Run a compact alpha/capability phase-space sweep.

    Defaults are intentionally smaller than named scenario runs so the sweep is
    useful during research iteration. Increase sample sizes when producing final
    figures.
    """
    alphas = [float(x) for x in (alpha_values or np.linspace(0.05, 0.95, 7))]
    capabilities = [float(x) for x in (capability_values or np.linspace(0.35, 0.90, 6))]

    points: list[SweepPoint] = []
    for i, alpha in enumerate(alphas):
        for j, capability in enumerate(capabilities):
            cfg = _point_config(
                alpha=alpha,
                capability=capability,
                n_steps=n_steps,
                pairs_per_step=pairs_per_step,
                n_human_prototypes=n_human_prototypes,
                n_agent_prototypes=n_agent_prototypes,
                seed=seed + i * 100 + j,
            )
            world = World.build(cfg)
            world.run(progress=False)
            terminal = world.metrics.history.steps[-1]
            points.append(
                SweepPoint(
                    alpha=round(alpha, 4),
                    agent_capability_mean=round(capability, 4),
                    human_capability_mean=round(max(0.05, capability - 0.18), 4),
                    ebi=terminal.exo_baroque_index,
                    real_per_capita_welfare=terminal.real_per_capita_welfare,
                    gini_wealth=terminal.gini_wealth,
                    human_legibility_index=terminal.human_legibility_index,
                    governance_overhead_fraction=terminal.governance_overhead_fraction,
                    fold_max_depth=terminal.fold_max_depth,
                    basin=classify_basin(
                        terminal.exo_baroque_index,
                        terminal.real_per_capita_welfare,
                        terminal.human_legibility_index,
                    ),
                )
            )

    summary = SweepSummary(
        points=points,
        alpha_values=alphas,
        capability_values=capabilities,
        n_steps=n_steps,
        pairs_per_step=pairs_per_step,
        n_human_prototypes=n_human_prototypes,
        n_agent_prototypes=n_agent_prototypes,
    )
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary.to_dict(), indent=2))
    return summary


def basin_counts(points: Iterable[SweepPoint]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for point in points:
        counts[point.basin] = counts.get(point.basin, 0) + 1
    return dict(sorted(counts.items()))


# =============================================================================
# Saltelli/Sobol global sensitivity
# =============================================================================
#
# Replaces the OAT alpha/capability grid with a global sensitivity sweep
# over the dozen knobs that actually move the EBI. Reports first-order
# (S1) and total-order (ST) Sobol indices per output metric. See
# `docs/concepts/epistemic_status.md` for what a Sobol index does and
# doesn't tell you.

# Default parameter problem for the alpha-engine. Bounds are the
# stipulated range of each knob (we sweep within bounds; we do not claim
# the bounds themselves are calibrated). Each bound was chosen to span
# the values used across the named scenarios.
#
# The last four parameters (a2a_floor and the productive-folding
# triple) were added for the demand-and-intermediation work; see
# `docs/concepts/demand_and_intermediation.md`. The Sobol sweep treats
# them like any other speculative parameter: we report S1 / ST within
# the bounds; we do not claim any bound is "the value."
ALPHA_ENGINE_PROBLEM: dict = {
    "num_vars": 23,
    "names": [
        "alpha",
        "agent_capability_mean",
        "coase_exp",
        "base_friction",
        "folding_propensity",
        "folding_branching",
        "fold_real_efficiency",
        "fold_nominal_multiplier",
        "cross_stack_compat",
        "market_layer_tax",
        "a2a_floor",
        "base_variance_absorption",
        "productive_decay",
        "cap_slope",
        "max_productive_real_share",
        # Round 1 robustness: registration / norms / regulator /
        # permeability. Plans 6 (deciles) and 7 (mission) are not in
        # this PR's parameter vector; their entries land with their
        # respective plans.
        "registration_coverage",
        "norm_update_eta",
        "regulator_coverage",
        "audit_quality",
        "perm_agent_stack",
        "perm_exo_lift_lastmile",
        "perm_exo_lastmile_drag",
        "perm_exo_drag_differential",
    ],
    "bounds": [
        [0.05, 0.95],   # alpha
        [0.45, 0.92],   # agent_capability_mean
        [1.2, 2.4],     # coase_exp
        [0.02, 0.08],   # base_friction
        [0.05, 0.75],   # folding_propensity
        [1.6, 3.4],     # folding_branching
        [0.85, 0.97],   # fold_real_efficiency
        [1.3, 2.2],     # fold_nominal_multiplier
        [0.30, 0.95],   # cross_stack_compat
        [0.005, 0.05],  # market_layer_tax
        [0.05, 0.40],   # a2a_floor (DemandConfig)
        [0.0, 0.60],    # base_variance_absorption (productive folding)
        [0.40, 0.85],   # productive_decay
        [2.0, 6.0],     # cap_slope
        [0.20, 0.80],   # max_productive_real_share
        # Round 1 bounds.
        [0.0, 1.0],     # registration_coverage (PopulationConfig)
        [0.0, 0.30],    # norm_update_eta (NormConfig)
        [0.0, 1.0],     # regulator_coverage (RegulatorConfig)
        [0.0, 1.0],     # audit_quality (RegulatorConfig)
        [0.0, 1.0],     # perm_agent_stack (PermeabilityConfig)
        [0.0, 1.0],     # perm_exo_lift_lastmile (alpha-side mirror)
        [0.0, 1.0],     # perm_exo_lastmile_drag
        [0.0, 1.0],     # perm_exo_drag_differential
    ],
}


@dataclass(frozen=True)
class SobolIndices:
    """First-order and total-order Sobol indices for one output metric."""

    metric: str
    parameter_names: list[str]
    S1: list[float]
    S1_conf: list[float]
    ST: list[float]
    ST_conf: list[float]


@dataclass
class SobolSummary:
    """Sobol sweep result; serializable to JSON for the dashboard."""

    problem: dict
    n_base_samples: int
    n_simulations: int
    n_steps: int
    pairs_per_step: int
    n_human_prototypes: int
    n_agent_prototypes: int
    indices: list[SobolIndices] = field(default_factory=list)
    parameter_bounds: list[list[float]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "problem": {
                "num_vars": self.problem["num_vars"],
                "names": list(self.problem["names"]),
                "bounds": [list(b) for b in self.problem["bounds"]],
            },
            "n_base_samples": self.n_base_samples,
            "n_simulations": self.n_simulations,
            "n_steps": self.n_steps,
            "pairs_per_step": self.pairs_per_step,
            "n_human_prototypes": self.n_human_prototypes,
            "n_agent_prototypes": self.n_agent_prototypes,
            "parameter_bounds": [list(b) for b in self.parameter_bounds],
            "indices": [asdict(i) for i in self.indices],
        }


def _alpha_world_from_vector(
    x: np.ndarray,
    *,
    n_steps: int,
    pairs_per_step: int,
    n_human_prototypes: int,
    n_agent_prototypes: int,
    seed: int,
) -> WorldConfig:
    from engine.core.population import NormConfig
    from engine.core.topology import (
        DemandConfig,
        PermeabilityConfig,
        RegulatorConfig,
    )
    from engine.scenarios import _apply_empirical_topology

    population_cfg = PopulationConfig(
        n_human_prototypes=n_human_prototypes,
        n_agent_prototypes=n_agent_prototypes,
        agent_capability_mean=float(x[1]),
        human_capability_mean=max(0.05, float(x[1]) - 0.18),
        seed=seed,
        # Round 1: registration coverage at index 15. Plan 2's audit
        # trail engages whenever this is > 0; plans 3 and 4 read it.
        registration_coverage=float(x[15]),
    )
    # NormConfig lives on PopulationConfig; opt-in once `norm_update_eta`
    # is non-zero so the default-config Sobol mirror (eta=0) reproduces
    # the static-distance binding. The lag is held at the conservative
    # default; bounds-aware tuning happens after this round lands.
    population_cfg.norm = NormConfig(enabled=True, norm_update_eta=float(x[16]))

    cfg = WorldConfig(
        population=population_cfg,
        topology=TopologyConfig(
            alpha=float(x[0]),
            coase_exp=float(x[2]),
            base_friction=float(x[3]),
            folding_propensity=float(x[4]),
            folding_branching=float(x[5]),
            fold_real_efficiency=float(x[6]),
            fold_nominal_multiplier=float(x[7]),
            cross_stack_compat=float(x[8]),
            market_layer_tax=float(x[9]),
            # Demand-side feedback: enabled for the Sobol sweep so the
            # `welfare_authentic` output reflects the new mechanism. The
            # `a2a_floor` parameter is swept at index 10.
            demand=DemandConfig(enabled=True, a2a_floor=float(x[10])),
            # Productive vs parasitic folding split. Active whenever
            # `base_variance_absorption > 0`.
            base_variance_absorption=float(x[11]),
            productive_decay=float(x[12]),
            cap_slope=float(x[13]),
            max_productive_real_share=float(x[14]),
            # Round 1 robustness — opt in so Sobol reads non-default
            # behaviour.
            regulator=RegulatorConfig(
                enabled=True,
                coverage=float(x[17]),
                audit_quality=float(x[18]),
            ),
            permeability=PermeabilityConfig(
                agent_stack=float(x[19]),
                exo_lift_to_lastmile=float(x[20]),
                exo_lastmile_to_drag=float(x[21]),
                exo_drag_to_differential=float(x[22]),
            ),
        ),
        n_steps=n_steps,
        pairs_per_step=pairs_per_step,
        seed=seed,
        # The Sobol sweep uses small populations (default 6.6K prototypes),
        # where the per-step gini cost is microseconds. Disabling the
        # throttle ensures terminal flow-sensitive metrics
        # (`gini_wealth_change_abs`, `top_decile_share_change`) are always
        # fresh; otherwise they can be stale-by-(k-1) at terminal step or,
        # for n_steps < k, identically zero across all sims (which then
        # blows up the Saltelli/Sobol estimator).
        gini_every_k_steps=1,
        # Per-component RNG so a parameter that gates `n_pairs` (e.g.
        # cost) cannot shift the position of every other subsystem's draw
        # call for the rest of the step. Without this the Saltelli
        # estimator still converges, but it converges on a noised value
        # where draw-sequence cross-talk inflates small-but-nonzero S1 on
        # parameters the engine is mathematically independent of. With
        # per-component, ST attribution is reliable down to ~0.005 (vs
        # ~0.03 under the legacy shared-RNG layout). See
        # `docs/plans/rng_per_component_split.md`.
        rng_split_mode="per_component",
    )
    # Put the Sobol sweep on the same empirical substrate as the dashboard's
    # 21 substrate-anchored scenarios — sector-block network + t-copula noise
    # + Hawkes folding. Productive-lever parameters (base_variance_absorption,
    # demand, etc.) remain swept; only the topology/noise/kernel layer is
    # forced. Without this, the Sobol indices were on a well-mixed substrate
    # while the rest of the dashboard ran on the empirical one — a confound.
    return _apply_empirical_topology(cfg)


def run_sobol_sensitivity(
    *,
    n_base_samples: int = 512,
    n_steps: int = 18,
    pairs_per_step: int = 20_000,
    n_human_prototypes: int = 600,
    n_agent_prototypes: int = 6_000,
    output_path: Path | None = None,
    seed: int = 20260430,
    metrics: Sequence[str] = (
        # Raw `exo_baroque_index` and `exo_baroque_authentic` were here;
        # removed because they have an unbounded right tail (real -> 0
        # in heavily-folded regimes pushes EBI -> infinity), which breaks
        # the Saltelli/Sobol estimator the same way `gini_wealth` did
        # (ST > 1, negative S1 sums, exploding bootstrap CIs). The log
        # transform preserves rank ordering and compresses the tail.
        # See `engine/core/metrics.py` for the metric definition; the
        # raw EBI is still tracked for time-series viewing on the
        # dashboard.
        "log_exo_baroque_index",
        "real_per_capita_welfare",
        # `gini_wealth` was here; removed because terminal gini at typical
        # Sobol run lengths is ~100% determined by the initial wealth
        # distribution (corr(gini_0, gini_T) = 1.0000, var(gini_T - gini_0)
        # ~7e-11). The Saltelli/Sobol estimator broke down on it (ST > 1,
        # negative S1 sums). `gini_wealth_change_abs` replaces it: gini of
        # |wealth_t - wealth_0|, which captures topology-driven wealth
        # churn rather than the initial-population baseline. See
        # `engine/core/metrics.py` for the metric definition.
        "gini_wealth_change_abs",
        "log_exo_baroque_authentic",
        "real_welfare_authentic_cumulative",
        "productive_welfare_yield",
    ),
    progress: bool = True,
) -> SobolSummary:
    """Run a Saltelli/Sobol global sensitivity sweep on the alpha-engine.

    With `n_base_samples=N`, the SALib sampler produces `N * (D + 2)`
    parameter vectors (D=15 here, so N=512 -> 8704 simulations). Default
    raised from 64 to 512 because 64 leaves Sobol indices noise-dominated
    on a 15-parameter problem. Override with `--samples` for cheaper runs;
    cost scales linearly.

    Each simulation runs the World with
    `rng_split_mode="per_component"` (set in `_alpha_world_from_vector`),
    so the only source of variance between two parameter vectors is the
    parameter being varied — not draw-sequence shifts induced by one
    subsystem consuming a different number of draws. Under that layout
    ST attribution is reliable down to ~0.005; under the legacy
    shared-RNG layout the noise floor was ~0.03 and small-but-nonzero S1
    on mathematically-independent parameters were the visible artefact.
    See `docs/plans/rng_per_component_split.md` for the derivation.

    Returns S1 and ST per (metric, parameter), plus the bounds we swept
    over so the dashboard can be honest about the conditional nature of
    the indices.
    """
    try:
        from SALib.analyze import sobol as sobol_analyze
        from SALib.sample import sobol as sobol_sample
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "SALib is required for Sobol sensitivity. Install with `pip install SALib`."
        ) from exc

    problem = ALPHA_ENGINE_PROBLEM
    X = sobol_sample.sample(problem, n_base_samples, calc_second_order=False)
    n_sims = X.shape[0]
    if progress:
        print(
            f"[sobol] alpha-engine: {n_sims} simulations "
            f"({n_base_samples} base x (D+2={problem['num_vars'] + 2}))"
        )

    outputs = {m: np.empty(n_sims, dtype=np.float64) for m in metrics}
    for i in range(n_sims):
        cfg = _alpha_world_from_vector(
            X[i],
            n_steps=n_steps,
            pairs_per_step=pairs_per_step,
            n_human_prototypes=n_human_prototypes,
            n_agent_prototypes=n_agent_prototypes,
            seed=seed + i,
        )
        world = World.build(cfg)
        world.run(progress=False)
        terminal = world.metrics.history.steps[-1]
        for m in metrics:
            outputs[m][i] = float(getattr(terminal, m))
        if progress and ((i + 1) % max(1, n_sims // 20) == 0):
            print(f"  [sobol]   sim {i + 1:>4d}/{n_sims}")

    indices: list[SobolIndices] = []
    for m in metrics:
        Si = sobol_analyze.analyze(
            problem, outputs[m], calc_second_order=False, print_to_console=False
        )
        indices.append(
            SobolIndices(
                metric=m,
                parameter_names=list(problem["names"]),
                S1=[float(v) for v in Si["S1"]],
                S1_conf=[float(v) for v in Si["S1_conf"]],
                ST=[float(v) for v in Si["ST"]],
                ST_conf=[float(v) for v in Si["ST_conf"]],
            )
        )

    summary = SobolSummary(
        problem=problem,
        n_base_samples=n_base_samples,
        n_simulations=n_sims,
        n_steps=n_steps,
        pairs_per_step=pairs_per_step,
        n_human_prototypes=n_human_prototypes,
        n_agent_prototypes=n_agent_prototypes,
        indices=indices,
        parameter_bounds=problem["bounds"],
    )
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(summary.to_dict(), indent=2))
    return summary


if __name__ == "__main__":
    out = Path("outputs/sensitivity/phase_space.json")
    summary = run_phase_space_sweep(output_path=out)
    print(f"[agentworld] wrote {len(summary.points)} sweep points to {out}")
    sobol_out = Path("outputs/sensitivity/sobol_indices.json")
    sobol_summary = run_sobol_sensitivity(output_path=sobol_out)
    print(
        f"[agentworld] wrote sobol indices for {len(sobol_summary.indices)} metrics "
        f"to {sobol_out}"
    )

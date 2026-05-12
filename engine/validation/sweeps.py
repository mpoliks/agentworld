"""Permeability + norms validation sweeps (H-J robustness round).

Two pinned artifacts named by `docs/plans/hadfield_jacobs_robustness.md`'s
"Validation lift" section and deferred until the W1c (permeability) and
W1b (norms) levers had landed:

* `validate permeability` — sweep `cross_stack_permeability` over an 11-
  point grid on top of the wide prior already used by `validate priors`.
  Records the basin distribution + EBI quantiles per permeability point.
* `validate norms` — toggle `NormsConfig.enabled` against the same wide
  prior. Records the per-run rejection-share distribution under each
  configuration and the per-sample swing in the `rejected_align` share.

Both sweeps reuse the `_build_cfg` pattern from
`engine/validation/posterior_sweep.py`: small populations, short
horizon, deterministic seeds derived from the sample index. The
permeability / norms override is applied *on top of* a prior draw — so
each grid point answers "what does the basin distribution look like
under the prior, conditional on this lever value?".
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from engine.core.population import PopulationConfig
from engine.core.topology import NormsConfig, TopologyConfig
from engine.core.world import World, WorldConfig
from engine.sensitivity import classify_basin
from engine.validation.posterior_sweep import project_priors, sobol_unit_samples
from engine.validation.priors import alpha_priors


# Small-scale defaults named in the plan. Mirror the priors sweep so the
# two artifacts are directly comparable.
DEFAULT_N_STEPS = 24
DEFAULT_PAIRS_PER_STEP = 20_000
DEFAULT_N_HUMAN_PROTOTYPES = 600
DEFAULT_N_AGENT_PROTOTYPES = 6_000


def _build_cfg(
    point: dict,
    *,
    base_seed: int,
    n_steps: int,
    pairs_per_step: int,
    n_human_prototypes: int,
    n_agent_prototypes: int,
    cross_stack_permeability: float = 1.0,
    norms_cfg: Optional[NormsConfig] = None,
) -> WorldConfig:
    """Build an α-engine cfg from a wide-prior draw + lever overrides."""
    topology = TopologyConfig(
        alpha=0.55,
        folding_propensity=point["folding_propensity"],
        fold_real_efficiency=point["fold_real_efficiency"],
        fold_nominal_multiplier=point["fold_nominal_multiplier"],
        base_variance_absorption=point["base_variance_absorption"],
        productive_decay=point["productive_decay"],
        max_productive_real_share=point["max_productive_real_share"],
        cap_slope=point["cap_slope"],
        cross_stack_permeability=float(cross_stack_permeability),
    )
    if norms_cfg is not None:
        topology.norms = norms_cfg
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.78,
            agent_capability_sd=0.10,
            human_capability_mean=0.60,
            human_capability_sd=0.15,
            n_human_prototypes=n_human_prototypes,
            n_agent_prototypes=n_agent_prototypes,
            seed=base_seed + 7,
        ),
        topology=topology,
        pairs_per_step=pairs_per_step,
        n_steps=n_steps,
        seed=base_seed,
    )


def _run_terminal(cfg: WorldConfig) -> dict:
    """Run one simulation; return the terminal-step metric dict we care about."""
    world = World.build(cfg)
    world.run(progress=False)
    last = world.metrics.history.steps[-1]
    return {
        "ebi": float(last.exo_baroque_index),
        "welfare": float(last.real_per_capita_welfare),
        "legibility": float(last.human_legibility_index),
        "rejected_law": float(last.rejected_law),
        "rejected_market": float(last.rejected_market),
        "rejected_align": float(last.rejected_align),
        "rejected_cost": float(last.rejected_cost),
    }


# ---------------------------------------------------------------------------
# Permeability sweep
# ---------------------------------------------------------------------------


PERMEABILITY_GRID = tuple(round(0.1 * k, 2) for k in range(11))  # 0.0 .. 1.0


@dataclass
class PermeabilitySweepSummary:
    permeability_values: list[float]
    n_samples_per_point: int
    n_steps: int
    pairs_per_step: int
    n_human_prototypes: int
    n_agent_prototypes: int
    elapsed_sec: float
    basin_distribution: list[dict]
    ebi_quantiles: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


def _quantiles(values: np.ndarray) -> dict:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return {"p10": float("nan"), "p50": float("nan"), "p90": float("nan")}
    return {
        "p10": float(np.quantile(finite, 0.10)),
        "p50": float(np.quantile(finite, 0.50)),
        "p90": float(np.quantile(finite, 0.90)),
    }


def run_permeability_sweep(
    *,
    n_samples_per_point: int = 128,
    permeability_values: tuple = PERMEABILITY_GRID,
    seed: int = 0,
    n_steps: int = DEFAULT_N_STEPS,
    pairs_per_step: int = DEFAULT_PAIRS_PER_STEP,
    n_human_prototypes: int = DEFAULT_N_HUMAN_PROTOTYPES,
    n_agent_prototypes: int = DEFAULT_N_AGENT_PROTOTYPES,
    progress: bool = False,
) -> PermeabilitySweepSummary:
    priors = alpha_priors()
    unit = sobol_unit_samples(d=len(priors), n=n_samples_per_point, seed=seed)
    points = project_priors(unit, priors)

    started = time.time()
    basin_distribution: list[dict] = []
    ebi_quantiles: list[dict] = []

    total_runs = len(permeability_values) * n_samples_per_point
    completed = 0
    for perm in permeability_values:
        basin_counts: dict[str, int] = {}
        ebi_values = np.empty(n_samples_per_point, dtype=np.float64)
        for i in range(n_samples_per_point):
            cfg = _build_cfg(
                points[i],
                base_seed=seed + i,
                n_steps=n_steps,
                pairs_per_step=pairs_per_step,
                n_human_prototypes=n_human_prototypes,
                n_agent_prototypes=n_agent_prototypes,
                cross_stack_permeability=float(perm),
            )
            term = _run_terminal(cfg)
            ebi_values[i] = term["ebi"]
            label = classify_basin(
                term["ebi"], term["welfare"], term["legibility"]
            )
            basin_counts[label] = basin_counts.get(label, 0) + 1
            completed += 1
            if progress and completed % max(1, total_runs // 20) == 0:
                print(f"  [permeability] {completed:>4d}/{total_runs}")

        row = {"permeability": float(perm)}
        # Five labels classify_basin can return; spell them so consumers
        # know every key is always present (zero when no run landed there).
        for label in ("smooth", "mixed", "striated", "baroque", "slop"):
            row[label] = basin_counts.get(label, 0) / n_samples_per_point
        basin_distribution.append(row)

        ebi_row = {"permeability": float(perm)}
        ebi_row.update(_quantiles(ebi_values))
        ebi_quantiles.append(ebi_row)

    return PermeabilitySweepSummary(
        permeability_values=[float(p) for p in permeability_values],
        n_samples_per_point=n_samples_per_point,
        n_steps=n_steps,
        pairs_per_step=pairs_per_step,
        n_human_prototypes=n_human_prototypes,
        n_agent_prototypes=n_agent_prototypes,
        elapsed_sec=float(time.time() - started),
        basin_distribution=basin_distribution,
        ebi_quantiles=ebi_quantiles,
    )


def write_permeability_summary(
    summary: PermeabilitySweepSummary, out_path: Path
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary.to_dict(), indent=2))


# ---------------------------------------------------------------------------
# Norms sensitivity sweep
# ---------------------------------------------------------------------------


# The four rejection components the plan tracks. `rejected_permeability`
# and `rejected_regulator` are deliberately excluded — the question this
# sweep answers is how much of the *binding-constraint* (matryoshka)
# rejection share moves under the norms toggle.
REJECTION_COMPONENTS = ("law", "market", "align", "cost")


def _rejection_shares(term: dict) -> dict:
    """Normalize the four matryoshka rejection counts to shares of their sum."""
    counts = {k: max(0.0, term[f"rejected_{k}"]) for k in REJECTION_COMPONENTS}
    total = sum(counts.values())
    if total <= 0:
        return {k: 0.0 for k in REJECTION_COMPONENTS}
    return {k: counts[k] / total for k in REJECTION_COMPONENTS}


@dataclass
class NormsSensitivitySummary:
    n_samples: int
    n_steps: int
    pairs_per_step: int
    n_human_prototypes: int
    n_agent_prototypes: int
    elapsed_sec: float
    configurations: list[dict]
    alignment_share_delta: dict

    def to_dict(self) -> dict:
        return asdict(self)


def run_norms_sensitivity(
    *,
    n_samples: int = 128,
    seed: int = 0,
    n_steps: int = DEFAULT_N_STEPS,
    pairs_per_step: int = DEFAULT_PAIRS_PER_STEP,
    n_human_prototypes: int = DEFAULT_N_HUMAN_PROTOTYPES,
    n_agent_prototypes: int = DEFAULT_N_AGENT_PROTOTYPES,
    progress: bool = False,
) -> NormsSensitivitySummary:
    priors = alpha_priors()
    unit = sobol_unit_samples(d=len(priors), n=n_samples, seed=seed)
    points = project_priors(unit, priors)

    configs = [
        ("static", NormsConfig(enabled=False)),
        (
            "norm_participation",
            NormsConfig(enabled=True, update_rate=0.05, n_dimensions=4),
        ),
    ]

    started = time.time()
    per_config: dict[str, dict] = {}
    align_share_by_config: dict[str, np.ndarray] = {}

    for label, norms_cfg in configs:
        shares = {k: np.empty(n_samples, dtype=np.float64) for k in REJECTION_COMPONENTS}
        ebis = np.empty(n_samples, dtype=np.float64)
        welfares = np.empty(n_samples, dtype=np.float64)

        for i in range(n_samples):
            cfg = _build_cfg(
                points[i],
                base_seed=seed + i,
                n_steps=n_steps,
                pairs_per_step=pairs_per_step,
                n_human_prototypes=n_human_prototypes,
                n_agent_prototypes=n_agent_prototypes,
                norms_cfg=norms_cfg,
            )
            term = _run_terminal(cfg)
            s = _rejection_shares(term)
            for k in REJECTION_COMPONENTS:
                shares[k][i] = s[k]
            ebis[i] = term["ebi"]
            welfares[i] = term["welfare"]
            if progress and (i + 1) % max(1, n_samples // 10) == 0:
                print(f"  [norms:{label}] {i + 1:>4d}/{n_samples}")

        per_config[label] = {
            "label": label,
            "rejection_share_distribution": {
                k: _quantiles(shares[k]) for k in REJECTION_COMPONENTS
            },
            "ebi": _quantiles(ebis),
            "per_capita": _quantiles(welfares),
        }
        align_share_by_config[label] = shares["align"]

    delta = (
        align_share_by_config["norm_participation"]
        - align_share_by_config["static"]
    )

    return NormsSensitivitySummary(
        n_samples=n_samples,
        n_steps=n_steps,
        pairs_per_step=pairs_per_step,
        n_human_prototypes=n_human_prototypes,
        n_agent_prototypes=n_agent_prototypes,
        elapsed_sec=float(time.time() - started),
        configurations=[per_config["static"], per_config["norm_participation"]],
        alignment_share_delta=_quantiles(delta),
    )


def write_norms_summary(
    summary: NormsSensitivitySummary, out_path: Path
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary.to_dict(), indent=2))

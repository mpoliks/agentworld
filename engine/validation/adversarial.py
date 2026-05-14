"""Adversarial scenario search (A3).

The brief's load-bearing claim is that high intermediation (high EBI) does
not coexist with high welfare. This artifact tries to break it: a custom
simulated-annealing search over the speculative folding parameters that
asks "is there a region where EBI > 10 AND real per-capita welfare exceeds
coasean_paradise's terminal value?"

Two outcomes are admissible:

  - Counter-example. The search finds a parameter point where both
    thresholds are met. The scenario `baroque_with_high_welfare` then
    pins the brief's claim: "Baroque does not monotonically harm
    welfare; it depends on whether the fold is productive."
  - Invariant. The search fails inside the stipulated bounds. The brief
    can claim "under the model's bounds, high folding and high welfare
    do not coexist," with the search budget as the witness.

Either way, the result is persisted to outputs/validation/adversarial_search.json
and pinned by a regression test.

Run with:
    agentworld validate adversarial [--n-evals 200] [--seed 0]
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from engine.core.population import PopulationConfig
from engine.core.topology import TopologyConfig
from engine.core.world import World, WorldConfig
from engine.scenarios import get_scenario


# ---------------------------------------------------------------------------
# Search space
# ---------------------------------------------------------------------------

# Bounds for each speculative knob the search varies. The bounds are
# intentionally wide; if the search saturates a bound, the scenario isn't
# really inside the model's stipulated region anymore.
SEARCH_BOUNDS: tuple[tuple[str, float, float], ...] = (
    ("alpha", 0.65, 0.95),
    ("folding_propensity", 0.30, 0.85),
    ("folding_branching", 2.0, 4.5),
    ("fold_real_efficiency", 0.50, 0.96),
    ("fold_nominal_multiplier", 1.0, 3.0),
    ("base_variance_absorption", 0.10, 0.60),
    ("productive_decay", 0.50, 0.95),
    ("agent_capability_mean", 0.55, 0.92),
)


# ---------------------------------------------------------------------------
# Run config (kept small so a 1000-eval search finishes in single-digit minutes)
# ---------------------------------------------------------------------------


@dataclass
class _RunSpec:
    n_steps: int = 30
    n_human_prototypes: int = 600
    n_agent_prototypes: int = 6_000
    pairs_per_step: int = 20_000


def _build_cfg(point: dict, base_seed: int, run_spec: _RunSpec) -> WorldConfig:
    """Build a small WorldConfig that exercises the productive-folding split."""
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=point["agent_capability_mean"],
            agent_capability_sd=0.10,
            human_capability_mean=0.55,
            human_capability_sd=0.15,
            n_human_prototypes=run_spec.n_human_prototypes,
            n_agent_prototypes=run_spec.n_agent_prototypes,
            seed=base_seed + 7,
        ),
        topology=TopologyConfig(
            alpha=point["alpha"],
            folding_propensity=point["folding_propensity"],
            folding_branching=point["folding_branching"],
            fold_real_efficiency=point["fold_real_efficiency"],
            fold_nominal_multiplier=point["fold_nominal_multiplier"],
            base_variance_absorption=point["base_variance_absorption"],
            productive_decay=point["productive_decay"],
            cap_midpoint=0.50,
            cap_slope=4.0,
            max_productive_real_share=0.85,
        ),
        pairs_per_step=run_spec.pairs_per_step,
        n_steps=run_spec.n_steps,
        seed=base_seed,
    )


def _measure_paradise_welfare(run_spec: _RunSpec, seed: int = 0) -> float:
    """Terminal real_per_capita_welfare of `coasean_paradise` at the same
    runtime scale we use for adversarial evaluations. This is the threshold
    a counter-example must beat.

    Uses the **un-wrapped** factory so the paradise comparison stays
    well-mixed, matching the topology of `baroque_with_high_welfare`
    (which is in `_SUBSTRATE_DEFAULT_EXCLUDED`). `get_scenario` would
    return the substrate-wrapped paradise after the 2026-Q3 migration,
    producing an apples-to-oranges comparison and tripping
    `test_baroque_with_high_welfare_scenario_reproduces_counter_example`.
    """
    # Local import: avoid pulling the un-wrapped factory through the
    # registry, which now points at the SBM-substrate wrapper.
    from engine.scenarios import coasean_paradise as _raw_paradise

    cfg = _raw_paradise()
    cfg.n_steps = run_spec.n_steps
    cfg.population.n_human_prototypes = run_spec.n_human_prototypes
    cfg.population.n_agent_prototypes = run_spec.n_agent_prototypes
    cfg.pairs_per_step = run_spec.pairs_per_step
    cfg.seed = seed
    world = World.build(cfg)
    world.run(progress=False)
    return float(world.metrics.history.steps[-1].real_per_capita_welfare)


def _evaluate(point: dict, run_spec: _RunSpec, seed: int = 0) -> tuple[float, float]:
    """Run the candidate; return (terminal EBI, terminal real-per-capita welfare)."""
    cfg = _build_cfg(point, base_seed=seed, run_spec=run_spec)
    world = World.build(cfg)
    world.run(progress=False)
    last = world.metrics.history.steps[-1]
    return float(last.exo_baroque_index), float(last.real_per_capita_welfare)


def _score(ebi: float, welfare: float, paradise_welfare: float, ebi_target: float) -> float:
    """Score that prefers counter-examples (EBI > target AND welfare > paradise).

    Below threshold on either axis: return a penalised value where the
    penalty grows with the gap. Above threshold: return welfare margin
    minus a small penalty for low EBI margin (so the search keeps both
    axes alive).
    """
    ebi_gap = ebi_target - ebi  # positive when below target
    welf_gap = paradise_welfare - welfare  # positive when below paradise
    if ebi_gap <= 0 and welf_gap <= 0:
        # Counter-example region. Reward welfare margin lightly.
        return (welfare - paradise_welfare) + 1e-3 * (ebi - ebi_target)
    # Penalize each gap; prefer states close to satisfaction.
    return -(max(0.0, ebi_gap) / max(ebi_target, 1.0) + max(0.0, welf_gap / max(paradise_welfare, 1e-6)))


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class AdversarialResult:
    n_evals: int
    seed: int
    paradise_welfare: float
    ebi_target: float
    found_counter_example: bool
    best_point: dict
    best_ebi: float
    best_welfare: float
    best_score: float
    elapsed_sec: float
    bounds: list[list]
    score_trajectory: list[float] = field(default_factory=list)
    # Multi-seed replication of the best candidate. Populated when
    # adversarial_search() is called with n_replicate_seeds > 1; lets the
    # verdict be reported as "found a counter-example that holds in K/N
    # seeds," not "found one in a single lucky draw."
    n_replicate_seeds: int = 1
    replicate_seeds: list[int] = field(default_factory=list)
    replicate_ebi: list[float] = field(default_factory=list)
    replicate_welfare: list[float] = field(default_factory=list)
    # Fraction of replicate seeds in which the best point still satisfies
    # both thresholds (EBI > target AND welfare > paradise_welfare).
    replicate_hit_rate: float = 1.0

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def adversarial_search(
    n_evals: int = 200,
    seed: int = 0,
    progress: bool = False,
    n_steps: int = 30,
    n_human_prototypes: int = 600,
    n_agent_prototypes: int = 6_000,
    pairs_per_step: int = 20_000,
    ebi_target: float = 10.0,
    n_replicate_seeds: int = 1,
) -> AdversarialResult:
    """Custom simulated-annealing search over SEARCH_BOUNDS.

    Geometric temperature schedule from T0=1.0 → T1=1e-4. Step size shrinks
    linearly with temperature. RNG is seeded so refactors don't silently
    re-roll the result.

    With `n_replicate_seeds > 1`, after the search finishes, the best point
    is re-evaluated across K independent seeds. The verdict
    (`found_counter_example`) flips to True only if BOTH the search seed
    AND a strict majority of the replicate seeds clear the thresholds.
    `replicate_hit_rate` reports the fraction of seeds that did, so the
    user can see how brittle the verdict is.
    """
    if n_evals < 4:
        raise ValueError("n_evals must be >= 4 (init + at least a few proposals)")

    rng = np.random.default_rng(seed)
    run_spec = _RunSpec(
        n_steps=n_steps,
        n_human_prototypes=n_human_prototypes,
        n_agent_prototypes=n_agent_prototypes,
        pairs_per_step=pairs_per_step,
    )
    paradise_welfare = _measure_paradise_welfare(run_spec, seed=seed)

    names = [b[0] for b in SEARCH_BOUNDS]
    los = np.array([b[1] for b in SEARCH_BOUNDS], dtype=np.float64)
    his = np.array([b[2] for b in SEARCH_BOUNDS], dtype=np.float64)
    spans = his - los

    def _to_point(x: np.ndarray) -> dict:
        return {n: float(v) for n, v in zip(names, x)}

    # Random init within bounds.
    x = los + rng.random(len(SEARCH_BOUNDS)) * spans
    ebi, welfare = _evaluate(_to_point(x), run_spec, seed=seed)
    score = _score(ebi, welfare, paradise_welfare, ebi_target)
    best_x, best_score = x.copy(), score
    best_ebi, best_welfare = ebi, welfare

    T0, T1 = 1.0, 1e-4
    score_traj: list[float] = [score]
    started = time.time()
    iter_range = range(1, n_evals)
    if progress:
        try:
            from tqdm import trange
            iter_range = trange(1, n_evals, desc="adversarial", leave=False)
        except ImportError:
            pass

    for t in iter_range:
        T = T0 * (T1 / T0) ** (t / max(1, n_evals - 1))
        # Step size shrinks with T; floor 2% of span so movement persists.
        step_scale = (0.18 * T + 0.02) * spans
        proposal = x + rng.normal(scale=step_scale)
        proposal = np.clip(proposal, los, his)
        new_ebi, new_welfare = _evaluate(_to_point(proposal), run_spec, seed=seed)
        new_score = _score(new_ebi, new_welfare, paradise_welfare, ebi_target)
        delta = new_score - score
        if delta >= 0 or rng.random() < math.exp(min(50.0, delta / max(T, 1e-9))):
            x = proposal
            score = new_score
            ebi, welfare = new_ebi, new_welfare
            if score > best_score:
                best_x, best_score = x.copy(), score
                best_ebi, best_welfare = ebi, welfare
        score_traj.append(score)

    found = best_ebi > ebi_target and best_welfare > paradise_welfare

    # Replicate the best point across additional seeds so the verdict
    # isn't single-seed brittle. The search seed counts as replicate #0.
    replicate_seeds: list[int] = [seed]
    replicate_ebi: list[float] = [float(best_ebi)]
    replicate_welfare: list[float] = [float(best_welfare)]
    if n_replicate_seeds > 1:
        best_point = _to_point(best_x)
        for k in range(1, n_replicate_seeds):
            rep_seed = int(seed + 1_000_003 * k)  # large prime offset
            rep_ebi, rep_welfare = _evaluate(best_point, run_spec, seed=rep_seed)
            replicate_seeds.append(rep_seed)
            replicate_ebi.append(float(rep_ebi))
            replicate_welfare.append(float(rep_welfare))

    hits = sum(
        1
        for ebi_k, welfare_k in zip(replicate_ebi, replicate_welfare)
        if ebi_k > ebi_target and welfare_k > paradise_welfare
    )
    hit_rate = hits / max(1, len(replicate_seeds))
    # Tighten the verdict: a counter-example must clear thresholds in the
    # search seed AND in at least half the replicates.
    found = bool(found) and (hit_rate >= 0.5)

    return AdversarialResult(
        n_evals=n_evals,
        seed=seed,
        paradise_welfare=float(paradise_welfare),
        ebi_target=float(ebi_target),
        found_counter_example=bool(found),
        best_point=_to_point(best_x),
        best_ebi=float(best_ebi),
        best_welfare=float(best_welfare),
        best_score=float(best_score),
        elapsed_sec=float(time.time() - started),
        bounds=[list(b) for b in SEARCH_BOUNDS],
        score_trajectory=[float(s) for s in score_traj],
        n_replicate_seeds=int(len(replicate_seeds)),
        replicate_seeds=replicate_seeds,
        replicate_ebi=replicate_ebi,
        replicate_welfare=replicate_welfare,
        replicate_hit_rate=float(hit_rate),
    )


def write_adversarial_summary(result: AdversarialResult, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result.to_dict(), indent=2))

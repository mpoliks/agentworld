"""
World — the orchestrator.

A World owns:
    - a Population
    - a Topology (the smooth-striated regime + friction surface)
    - a Metrics accumulator
    - an RNG

It exposes:
    .step(n_pairs)       — advance one tick, returning StepMetrics
    .run(n_steps, ...)   — advance many ticks, returning history
    .snapshot()          — full pickleable state
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from engine.core.folding import fold_surplus
from engine.core.metrics import Metrics, StepMetrics
from engine.core.population import Population, PopulationConfig
from engine.core.topology import Topology, TopologyConfig
from engine.core.transactions import coasean_step


@dataclass
class WorldConfig:
    """Top-level config for one Agentworld run."""

    population: PopulationConfig = field(default_factory=PopulationConfig)
    topology: TopologyConfig = field(default_factory=TopologyConfig)

    # Per-step pair sample size for the Coasean engine.
    pairs_per_step: int = 200_000

    # If pairs_per_step exceeds chunk_size, coasean_step processes pairs in
    # batches of chunk_size to keep working set in L2/L3 cache. Set to 0 or
    # >= pairs_per_step to disable chunking.
    pair_chunk_size: int = 1_000_000

    # Compute the Gini coefficient every K steps (and carry it forward in
    # between). At 88M prototypes a single Gini call is ~1.2s, so K=5 takes
    # the per-scenario Gini cost from ~72s to ~14s with no visible loss.
    gini_every_k_steps: int = 5

    # Total number of steps to run.
    n_steps: int = 60

    # RNG seed.
    seed: int = 0

    # If non-empty, alpha schedule overrides topology.cfg.alpha at each step.
    # Length must equal n_steps. Useful for time-varying scenarios.
    alpha_schedule: Optional[list] = None

    # Friction-floor schedule (optional).
    friction_floor_schedule: Optional[list] = None


@dataclass
class World:
    cfg: WorldConfig
    population: Population
    topology: Topology
    metrics: Metrics
    rng: np.random.Generator
    step_idx: int = 0

    @classmethod
    def build(cls, cfg: Optional[WorldConfig] = None) -> "World":
        if cfg is None:
            cfg = WorldConfig()
        rng = np.random.default_rng(cfg.seed)
        pop = Population.synthesize(cfg.population)
        topo = Topology.build(cfg.topology)
        return cls(
            cfg=cfg,
            population=pop,
            topology=topo,
            metrics=Metrics(),
            rng=rng,
        )

    # ---- per-step ---------------------------------------------------------

    def step(self) -> StepMetrics:
        # Apply schedules if present.
        if self.cfg.alpha_schedule is not None:
            self.topology.cfg.alpha = float(
                self.cfg.alpha_schedule[min(self.step_idx, len(self.cfg.alpha_schedule) - 1)]
            )
        if self.cfg.friction_floor_schedule is not None:
            self.topology.cfg.friction_floor = float(
                self.cfg.friction_floor_schedule[
                    min(self.step_idx, len(self.cfg.friction_floor_schedule) - 1)
                ]
            )

        # 1. Coasean transactions.
        tx = coasean_step(
            self.population, self.topology, self.rng,
            n_pairs=self.cfg.pairs_per_step,
            chunk_size=self.cfg.pair_chunk_size,
        )

        # Update wealth from transactions.
        self.population.wealth = np.clip(
            self.population.wealth + tx.wealth_delta.astype(np.float32),
            0.0, None,
        )

        # 2. Folding operator. Folding takes the step's nominal volume and
        # *fractally multiplies* it. Real surplus is reduced by the fold
        # overhead.
        fold = fold_surplus(
            base_real_surplus=tx.real_surplus_added,
            base_nominal_volume=tx.nominal_volume,
            topo=self.topology,
            rng=self.rng,
        )
        real_step = max(0.0, tx.real_surplus_added - fold.real_subtracted)
        nominal_step = tx.nominal_volume + fold.nominal_added

        # 3. Record metrics.
        m = self.metrics.step_metrics(
            step=self.step_idx,
            pop=self.population,
            alpha=self.topology.cfg.alpha,
            real_step=real_step,
            nominal_step=nominal_step,
            n_tx_real=tx.n_transactions_real,
            n_subs=fold.n_sub_markets_added,
            fold_depth=fold.new_max_depth,
            rejected_law=tx.rejected_law,
            rejected_market=tx.rejected_market,
            rejected_align=tx.rejected_align,
            rejected_cost=tx.rejected_cost,
            gini_every_k_steps=self.cfg.gini_every_k_steps,
        )

        self.step_idx += 1
        return m

    def run(self, n_steps: Optional[int] = None, progress: bool = False) -> "Metrics":
        """Run for n_steps (or cfg.n_steps if None). Returns the metrics object."""
        n = n_steps if n_steps is not None else self.cfg.n_steps
        if progress:
            try:
                from tqdm import trange
                iterator = trange(n, desc="agentworld", leave=False)
            except ImportError:
                iterator = range(n)
        else:
            iterator = range(n)
        for _ in iterator:
            self.step()
        return self.metrics

    # ---- snapshot ---------------------------------------------------------

    def snapshot(self) -> dict:
        return {
            "step": self.step_idx,
            "alpha": self.topology.cfg.alpha,
            "topology_label": self.topology.label(),
            "population_summary": self.population.summary(),
            "history": self.metrics.history.to_dict(),
        }

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
from typing import Callable, Optional

import numpy as np

from engine.core.folding import fold_surplus
from engine.core.metrics import Metrics, StepMetrics, gini_coefficient
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
    law_strength: float
    law_capture: float
    step_idx: int = 0
    # Weighted-mean capability of the intermediating side of the economy.
    # Used by the productive-vs-parasitic folding split. Until the §4
    # mode-1 separation lands, we use the population-mean *agent*
    # capability (agents are the intermediaries by default in the
    # alpha-engine). Computed once at build time.
    _cap_intermediating_mean: float = 0.0
    _last_law_gini: float = 0.0
    # Pigouvian friction subsidy: accumulated revenue available for
    # reducing human-involving transaction costs next step.
    _pigouvian_friction_pool: float = 0.0

    @classmethod
    def build(cls, cfg: Optional[WorldConfig] = None) -> "World":
        if cfg is None:
            cfg = WorldConfig()
        rng = np.random.default_rng(cfg.seed)
        topo = Topology.build(cfg.topology)
        pop = Population.synthesize(cfg.population, strategy_config=topo.cfg.strategy)
        agents_mask = ~pop.is_human
        if agents_mask.any():
            w = pop.weight[agents_mask].astype(np.float64)
            c = pop.capability[agents_mask].astype(np.float64)
            cap_inter = float((w * c).sum() / w.sum()) if w.sum() > 0 else 0.0
        else:
            cap_inter = 0.0
        return cls(
            cfg=cfg,
            population=pop,
            topology=topo,
            metrics=Metrics(),
            rng=rng,
            _cap_intermediating_mean=cap_inter,
            law_strength=(
                float(np.clip(topo.cfg.law.law_strength_initial, 0.0, 1.0))
                if topo.cfg.law.enabled
                else 1.0
            ),
            law_capture=(
                float(np.clip(topo.cfg.law.law_capture_initial, 0.0, 1.0))
                if topo.cfg.law.enabled
                else 0.0
            ),
        )

    # ---- per-step ---------------------------------------------------------

    def _current_law_gini(self) -> float:
        """Gini used by law capture, recomputed on the same cadence as metrics."""
        if (
            self.step_idx == 0
            or self.cfg.gini_every_k_steps <= 1
            or self.step_idx % self.cfg.gini_every_k_steps == 0
        ):
            self._last_law_gini = gini_coefficient(
                self.population.wealth, self.population.weight
            )
        return self._last_law_gini

    def _top_quantile_wealth_share(self, quantile: float = 0.01) -> float:
        """Weighted wealth share held by the top population quantile."""
        wealth = self.population.wealth.astype(np.float64, copy=False)
        weight = self.population.weight.astype(np.float64, copy=False)
        total_wealth = float((wealth * weight).sum())
        total_weight = float(weight.sum())
        if total_wealth <= 0.0 or total_weight <= 0.0:
            return 0.0

        cutoff = quantile * total_weight
        order = np.argsort(wealth)[::-1]
        wealth_sorted = wealth[order]
        weight_sorted = weight[order]
        cum_weight = np.cumsum(weight_sorted)
        prev_cum_weight = np.concatenate(([0.0], cum_weight[:-1]))
        included_weight = np.clip(cutoff - prev_cum_weight, 0.0, weight_sorted)
        top_wealth = float((wealth_sorted * included_weight).sum())
        return float(np.clip(top_wealth / total_wealth, 0.0, 1.0))

    def _advance_law_state(self) -> None:
        """Update dynamic law state for the next step."""
        cfg = self.topology.cfg.law
        if not cfg.enabled:
            return
        top_share = self._top_quantile_wealth_share()
        self.law_strength = float(np.clip(
            self.law_strength
            + cfg.upkeep_investment * cfg.law_decay_recovery
            - cfg.natural_decay,
            0.0,
            1.0,
        ))
        self.law_capture = float(np.clip(
            self.law_capture
            + cfg.beta_capture_growth * top_share
            - cfg.gamma_civic_pushback * cfg.civic_pushback_default,
            0.0,
            1.0,
        ))

    def _recycle_pigouvian_revenue(self, revenue: float) -> None:
        """Redistribute Pigouvian tax revenue to humans."""
        pig_cfg = self.topology.cfg.pigouvian
        if revenue <= 0 or not pig_cfg.enabled:
            return

        pop = self.population
        h_mask = pop.is_human

        if pig_cfg.recycling == "human_wealth":
            h_wealth = pop.wealth[h_mask].astype(np.float64)
            h_weight = pop.weight[h_mask].astype(np.float64)
            inv_w = 1.0 / np.maximum(h_wealth, 1e-6)
            share = (inv_w ** pig_cfg.recycling_progressivity) * h_weight
            share_sum = share.sum()
            if share_sum <= 0:
                return
            share /= share_sum
            per_proto_real = revenue * share
            per_proto_wealth = per_proto_real / h_weight
            pop.wealth[h_mask] = np.clip(
                pop.wealth[h_mask] + per_proto_wealth.astype(np.float32),
                0.0, None,
            )

        elif pig_cfg.recycling == "friction_subsidy":
            self._pigouvian_friction_pool += revenue

        elif pig_cfg.recycling == "capability":
            h_weight = pop.weight[h_mask].astype(np.float64)
            total_h_weight = h_weight.sum()
            if total_h_weight <= 0:
                return
            cap_boost = revenue / (total_h_weight * 50.0)
            pop.capability[h_mask] = np.clip(
                pop.capability[h_mask] + np.float32(cap_boost),
                0.01, 0.99,
            )

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

        strategy_cfg = self.topology.cfg.strategy
        if strategy_cfg.enabled:
            from engine.core.strategy import apply_actions, select_actions

            actions = select_actions(
                self.population.bandit_rewards,
                self.population.bandit_counts,
                strategy_cfg.epsilon,
                self.rng,
            )
            self.population.last_action = actions
            apply_actions(
                self.population.intermediation_pref,
                actions,
                strategy_cfg.pref_delta,
            )

        # 1. Coasean transactions.
        law_enabled = self.topology.cfg.law.enabled
        law_gini = self._current_law_gini() if law_enabled else 0.0
        law_strength_used = self.law_strength if law_enabled else 1.0
        law_capture_used = self.law_capture if law_enabled else 0.0
        tx = coasean_step(
            self.population, self.topology, self.rng,
            n_pairs=self.cfg.pairs_per_step,
            chunk_size=self.cfg.pair_chunk_size,
            law_strength=law_strength_used,
            law_capture=law_capture_used,
            gini_wealth=law_gini,
            local_alpha=(
                self.population.intermediation_pref
                if strategy_cfg.enabled
                else None
            ),
        )

        dyn_cfg = self.topology.cfg.pop_dynamics
        retained_delta = tx.wealth_delta
        if dyn_cfg.enabled:
            retained_delta = retained_delta * dyn_cfg.savings_rate

        # Update wealth from transactions. With population dynamics enabled,
        # only saved surplus accumulates as wealth; the rest is consumed.
        self.population.wealth = np.clip(
            self.population.wealth + retained_delta.astype(np.float32),
            0.0, None,
        )

        # Pigouvian revenue recycling.
        self._recycle_pigouvian_revenue(tx.pigouvian_revenue)

        # 2. Folding operator. Folding takes the step's nominal volume and
        # *fractally multiplies* it. Real surplus is reduced by the fold
        # overhead and (when productive folding is enabled) increased by
        # the welfare-creating share of the cascade.
        # Cumulative-fold-pressure signal. Normalised step counter × alpha
        # gives the propensity-feedback channel a monotonic input that
        # actually moves over the course of a run (gini does not, since
        # initial Pareto wealth dwarfs per-step flow). High-alpha
        # scenarios accumulate pressure quickly; smooth scenarios never
        # cross the anchor.
        if self.topology.cfg.folding_pressure_feedback:
            denom = max(self.cfg.n_steps - 1, 1)
            fold_pressure = (self.step_idx / denom) * self.topology.cfg.alpha
        else:
            fold_pressure = None
        fold = fold_surplus(
            base_real_surplus=tx.real_surplus_added,
            base_nominal_volume=tx.nominal_volume,
            topo=self.topology,
            rng=self.rng,
            cap_intermediating=self._cap_intermediating_mean,
            realized_alpha=tx.realized_alpha if strategy_cfg.enabled else None,
            fold_pressure=fold_pressure,
        )
        law_upkeep_cost = (
            self.topology.cfg.law.upkeep_investment * tx.real_surplus_added
            if law_enabled
            else 0.0
        )
        real_step = max(
            0.0,
            tx.real_surplus_added
            - law_upkeep_cost
            - fold.real_subtracted
            + fold.real_added_productive,
        )
        # The authentic-welfare aggregate also receives the productive
        # contribution: derivatives that are welfare-creating create
        # welfare for the eventual human consumer downstream. When the
        # demand-feedback flag is off, real_surplus_authentic equals
        # real_surplus_added and the back-compat path holds.
        real_authentic_step = max(
            0.0,
            tx.real_surplus_authentic
            - law_upkeep_cost
            - fold.real_subtracted
            + fold.real_added_productive,
        )
        nominal_step = tx.nominal_volume + fold.nominal_added

        inst_cfg = self.topology.cfg.institutions
        if (
            inst_cfg.enabled
            and inst_cfg.formation_check_every_k > 0
            and self.step_idx % inst_cfg.formation_check_every_k == 0
        ):
            from engine.core.institutions import (
                dissolution_step,
                firm_overhead_step,
                formation_step,
                merge_step,
            )

            dissolution_step(self.population, inst_cfg)
            formation_step(self.population, inst_cfg, self.rng, surplus_per_proto=tx.wealth_delta)
            merge_step(self.population, inst_cfg, self.rng)
            firm_overhead_step(self.population, inst_cfg)

        if strategy_cfg.enabled:
            from engine.core.strategy import update_rewards

            update_rewards(
                self.population.bandit_rewards,
                self.population.bandit_counts,
                self.population.last_action,
                tx.wealth_delta.astype(np.float32),
                strategy_cfg.reward_learning_rate,
            )

        churn_count = 0
        if dyn_cfg.enabled:
            from engine.core.dynamics import capability_update, entry_exit, wealth_depreciation

            capability_update(self.population, tx.wealth_delta, dyn_cfg)
            wealth_depreciation(self.population, dyn_cfg)
            churn_count = entry_exit(self.population, dyn_cfg, self.rng)

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
            real_authentic_step=real_authentic_step,
            productive_welfare_yield=fold.productive_welfare_yield,
            real_added_productive=fold.real_added_productive,
            law_strength=law_strength_used,
            law_capture=law_capture_used,
            law_weak_surplus_loss=tx.law_weak_surplus_loss,
            law_capture_surplus_loss=tx.law_capture_surplus_loss,
            law_upkeep_cost=law_upkeep_cost,
            pigouvian_revenue=tx.pigouvian_revenue,
            a2a_share=tx.a2a_share,
            h2a_share=tx.h2a_share,
            h2h_share=tx.h2h_share,
            strategy_enabled=strategy_cfg.enabled,
            realized_alpha=tx.realized_alpha,
            realized_folding_ratio_value=(
                self.topology.folding_propensity(tx.realized_alpha if strategy_cfg.enabled else None)
                / self.topology.cfg.folding_propensity
                if self.topology.cfg.folding_propensity > 0
                else 0.0
            ),
            institutions_enabled=inst_cfg.enabled,
            dynamics_enabled=dyn_cfg.enabled,
            churn_count=churn_count,
            fold_per_depth_contribution=fold.per_depth_contribution,
        )

        self._advance_law_state()
        self.step_idx += 1
        return m

    def run(
        self,
        n_steps: Optional[int] = None,
        progress: bool = False,
        step_callback: Optional[Callable[[StepMetrics], None]] = None,
    ) -> "Metrics":
        """Run for n_steps (or cfg.n_steps if None). Returns the metrics object.

        If `step_callback` is provided, it is invoked synchronously with each
        step's `StepMetrics` after the step completes. Used by the streaming
        layer (`agentworld serve`). When `None`, the run is bit-identical to
        the no-callback path.
        """
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
            m = self.step()
            if step_callback is not None:
                step_callback(m)
        return self.metrics

    # ---- snapshot ---------------------------------------------------------

    def snapshot(self) -> dict:
        return {
            "step": self.step_idx,
            "alpha": self.topology.cfg.alpha,
            "topology_label": self.topology.label(),
            "law_strength": self.law_strength,
            "law_capture": self.law_capture,
            "population_summary": self.population.summary(),
            "history": self.metrics.history.to_dict(),
        }

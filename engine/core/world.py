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
from typing import Callable, Literal, Optional

import numpy as np

from engine.core.folding import fold_surplus
from engine.core.ledger import StepLedger
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

    # Stock-flow accounting. When True (the default), every step the world
    # records a categorised ledger of wealth and welfare flows and computes
    # the residual against the observed totals. Reported via three new
    # `StepMetrics` fields (`wealth_imbalance_abs`, `wealth_imbalance_relative`,
    # `welfare_imbalance_abs`). Pure instrumentation — does not change
    # engine math. Disable for max throughput on xlarge runs where the per-
    # step `total_wealth()` reductions are noticeable.
    track_ledger: bool = True

    # Model time per simulator step. The default `dt = 1.0` reproduces all
    # existing canonical scenario outputs bit-for-bit. Setting `dt != 1.0`
    # rescales the explicit rate-like sub-processes (law evolution,
    # capability drift, wealth depreciation) by `dt` so that the same
    # *amount of model time* can be covered with different step counts.
    # Discrete-event sub-processes (Coasean pair sampling, folding cascade,
    # entry/exit, institutions) are calibrated per-step and are NOT
    # rescaled — running with a non-default dt only respects continuous-
    # time semantics for the rate processes. See
    # `docs/concepts/time_discretization.md` for the convention and the
    # caveats. `time_unit` is informational and only used in the
    # dashboard.
    dt: float = 1.0
    time_unit: str = "step"

    # RNG split layout. With `legacy` (the default), every subsystem draws
    # from the same `np.random.default_rng(seed)` — bit-identical to the
    # pre-split engine and the canonical pinned baselines. With
    # `per_component`, `World.build` spawns one child generator per
    # subsystem boundary (`market`, `alignment`, `law`, `folding`,
    # `population`, `demand`, `network`, `permeability`, `regulator`,
    # `exo`) so a parameter that perturbs how many draws subsystem A
    # consumes does not move the draw sequence subsystem B sees. The
    # Sobol/Saltelli
    # sensitivity driver opts into `per_component` so its ST attribution
    # is not contaminated by draw-sequence shifts; the canonical
    # regression suite stays on `legacy` so the pinned metrics keep
    # their bit pattern. See `docs/plans/rng_per_component_split.md` for
    # the rationale.
    rng_split_mode: Literal["legacy", "per_component"] = "legacy"

    # Live-engine V2: per-step pair-sample budget. K=0 (the default)
    # disables sampling and consumes no extra rng draws so canonical
    # pinned outputs remain bit-identical. K>0 emits K uniform-random
    # `PairSample` records per step (see `engine/core/transactions.py
    # ::PairSample`) attached to `StepMetrics.pair_samples`. The
    # sampling rng is isolated from the per-component layout — see
    # `World.build` for how it's spawned.
    pair_sample_k: int = 0

    # Cockpit Pass 2: persistent cast of prototype indices the live
    # surface follows from step 0 onward. 0 (default) disables; >0
    # samples that many prototype indices at build time weighted by
    # importance, splits ~50/50 humans/agents, and emits per-step
    # `StepMetrics.cast_snapshot` with each cast member's wealth,
    # capability, autonomy, firm membership, and sector.
    cast_size: int = 0


_RNG_SUBSYSTEMS: tuple[str, ...] = (
    "population",
    "market",
    "alignment",
    "law",
    "folding",
    "demand",
    "network",
    "permeability",
    "regulator",
    "exo",
)


def _build_rng_dict(
    seed: int, mode: str
) -> dict[str, np.random.Generator]:
    """Return the per-subsystem RNG dict.

    Under `legacy` every key aliases the same generator (bit-identical to
    the pre-split engine). Under `per_component` each key gets its own
    `default_rng` spawned from a SeedSequence, so a draw on one stream
    does not advance any other.
    """
    if mode == "per_component":
        seed_seq = np.random.SeedSequence(seed)
        children = seed_seq.spawn(len(_RNG_SUBSYSTEMS))
        return {
            name: np.random.default_rng(child)
            for name, child in zip(_RNG_SUBSYSTEMS, children)
        }
    shared = np.random.default_rng(seed)
    return {name: shared for name in _RNG_SUBSYSTEMS}


@dataclass
class World:
    cfg: WorldConfig
    population: Population
    topology: Topology
    metrics: Metrics
    rngs: dict[str, np.random.Generator]
    law_strength: float
    law_capture: float
    step_idx: int = 0
    # Live-engine V2: dedicated rng for per-pair sampling. Spawned in
    # `World.build` from a transform of cfg.seed so it doesn't collide
    # with any subsystem in `_RNG_SUBSYSTEMS`. `None` when
    # `cfg.pair_sample_k <= 0`.
    _pair_sample_rng: Optional[np.random.Generator] = None
    # Cockpit Pass 2: persistent cast indices selected at build time.
    # None when `cfg.cast_size == 0`. Cast prototypes don't churn;
    # their wealth / capability / firm state evolves over the run.
    cast_indices: Optional[np.ndarray] = None
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
    # Mission-economy pool (W2b): real surplus levied from executed
    # pairs and accumulated step-over-step. Each step the levy adds
    # `mission_levy * real_surplus_added`; the disbursement step then
    # converts a fraction of the pool to capability uplift on
    # coordinator-sector agents. With `MissionConfig.enabled = False`
    # the pool is never touched.
    _mission_pool: float = 0.0

    @property
    def rng(self) -> np.random.Generator:
        """Backward-compat alias to the market subsystem stream.

        Kept so user-supplied notebooks that read `world.rng` still work.
        New engine code should reach into `self.rngs[<subsystem>]` so the
        call site is honest about which stream it consumes.
        """
        return self.rngs["market"]

    @classmethod
    def build(cls, cfg: Optional[WorldConfig] = None) -> "World":
        if cfg is None:
            cfg = WorldConfig()
        rngs = _build_rng_dict(cfg.seed, cfg.rng_split_mode)
        topo = Topology.build(cfg.topology)
        pop = Population.synthesize(
            cfg.population,
            strategy_config=topo.cfg.strategy,
            registration_config=topo.cfg.registration,
            norms_config=topo.cfg.norms,
        )
        # S3 stretch — assign per-agent registration_stack by arbitraging
        # across regulator vendors. Off by default; populates the field
        # only when both the regulator and the arbitrage flags are on.
        reg2a_cfg = topo.cfg.registration
        reg_cfg = topo.cfg.regulator
        if (
            reg2a_cfg.enabled
            and getattr(reg2a_cfg, "arbitrage_enabled", False)
            and reg_cfg.enabled
        ):
            reg_strength, reg_capture, reg_audit = topo.regulator_vendor_arrays()
            eff_p = (
                np.asarray(reg_strength, dtype=np.float64)
                * np.asarray(reg_audit, dtype=np.float64)
                * (1.0 - np.asarray(reg_capture, dtype=np.float64))
            )
            chosen = int(np.argmin(eff_p))
            pop.registration_stack = np.full(pop.n, chosen, dtype=np.int8)
        agents_mask = ~pop.is_human
        if agents_mask.any():
            w = pop.weight[agents_mask].astype(np.float64)
            c = pop.capability[agents_mask].astype(np.float64)
            cap_inter = float((w * c).sum() / w.sum()) if w.sum() > 0 else 0.0
        else:
            cap_inter = 0.0
        # Live-engine V2: dedicated sampling rng, isolated from the
        # per-component layout so canonical pinned outputs stay
        # bit-identical when pair_sample_k = 0. The XOR with a fixed
        # constant keeps the stream deterministic per seed.
        pair_sample_rng = (
            np.random.default_rng(int(cfg.seed) ^ 0xC0DEC0DE)
            if cfg.pair_sample_k > 0
            else None
        )
        # Cockpit Pass 2: pick a persistent cast of prototypes the live
        # surface follows. Split roughly 50/50 humans/agents, weighted
        # within each side by importance. Deterministic per seed via a
        # second XOR'd rng so it doesn't disturb pair_sample_rng or
        # any per-component subsystem stream.
        cast_indices: Optional[np.ndarray] = None
        if cfg.cast_size > 0:
            cast_rng = np.random.default_rng(int(cfg.seed) ^ 0xCA57CA57)
            target = min(int(cfg.cast_size), pop.n)
            human_target = target // 2
            agent_target = target - human_target
            h_mask = pop.is_human.astype(bool)
            a_mask = ~h_mask
            h_idx = np.where(h_mask)[0]
            a_idx = np.where(a_mask)[0]
            h_w = pop.weight[h_idx].astype(np.float64)
            a_w = pop.weight[a_idx].astype(np.float64)
            picked: list = []
            if h_idx.size > 0 and h_w.sum() > 0:
                k = min(human_target, h_idx.size)
                p = h_w / h_w.sum()
                picked.extend(
                    int(x) for x in cast_rng.choice(h_idx, size=k, replace=False, p=p)
                )
            if a_idx.size > 0 and a_w.sum() > 0:
                k = min(agent_target, a_idx.size)
                p = a_w / a_w.sum()
                picked.extend(
                    int(x) for x in cast_rng.choice(a_idx, size=k, replace=False, p=p)
                )
            if picked:
                cast_indices = np.asarray(picked, dtype=np.int64)
        return cls(
            cfg=cfg,
            population=pop,
            topology=topo,
            metrics=Metrics(),
            rngs=rngs,
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
            _pair_sample_rng=pair_sample_rng,
            cast_indices=cast_indices,
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
        """Update dynamic law state for the next step.

        All four rate parameters (`natural_decay`, `law_decay_recovery`,
        `beta_capture_growth`, `gamma_civic_pushback * civic_pushback_default`)
        are interpreted as *per unit of model time*. With `WorldConfig.dt`
        defaulted to 1.0 the per-step deltas are unchanged; with `dt != 1.0`
        the law-state evolution scales linearly with model time elapsed
        per step.
        """
        cfg = self.topology.cfg.law
        if not cfg.enabled:
            return
        dt = float(self.cfg.dt)
        top_share = self._top_quantile_wealth_share()
        self.law_strength = float(np.clip(
            self.law_strength
            + (cfg.upkeep_investment * cfg.law_decay_recovery - cfg.natural_decay) * dt,
            0.0,
            1.0,
        ))
        self.law_capture = float(np.clip(
            self.law_capture
            + (cfg.beta_capture_growth * top_share
               - cfg.gamma_civic_pushback * cfg.civic_pushback_default) * dt,
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

    def _disburse_mission_pool(self) -> float:
        """Drain `_mission_pool` toward coordinator-sector capability.

        Disbursement rate is `capability_uplift_per_unit_pool`; the
        amount disbursed reduces the pool. `levy_target` selects the
        targeting:
          "coordinator_uplift" — flat per-agent share within coordinator
            sectors (the policy ideal).
          "regressive_pool"   — share proportional to current
            capability (the captured mode).

        Returns the disbursed amount (for the ledger).
        """
        cfg = self.topology.cfg.mission
        if (
            not cfg.enabled
            or self._mission_pool <= 0.0
            or cfg.capability_uplift_per_unit_pool <= 0.0
            or not cfg.coordinator_sectors
        ):
            return 0.0

        pop = self.population
        coord = np.isin(
            pop.sector,
            np.asarray(cfg.coordinator_sectors, dtype=pop.sector.dtype),
        )
        # Agents only — the mission lever targets capability of the
        # intermediating side, not humans.
        target_mask = coord & (~pop.is_human)
        if not target_mask.any():
            return 0.0

        disbursed = self._mission_pool * float(cfg.capability_uplift_per_unit_pool)
        disbursed = min(disbursed, self._mission_pool)
        self._mission_pool -= disbursed

        if cfg.levy_target == "regressive_pool":
            caps = pop.capability[target_mask].astype(np.float64)
            denom = float(caps.sum())
            if denom <= 0:
                share = np.zeros_like(caps)
            else:
                share = caps / denom
        else:  # "coordinator_uplift"
            share = np.full(int(target_mask.sum()), 1.0 / float(target_mask.sum()))
        # Convert share-of-disbursement to capability delta. Divide by
        # the prototype weight so the disbursement scales correctly: a
        # prototype represents many real agents, so the per-prototype
        # capability nudge corresponds to the same per-real-agent nudge.
        w = pop.weight[target_mask].astype(np.float64)
        per_proto_real = disbursed * share
        per_proto_delta = (per_proto_real / np.maximum(w, 1.0)).astype(np.float32)
        pop.capability[target_mask] = np.clip(
            pop.capability[target_mask] + per_proto_delta,
            0.01, 0.99,
        )
        return float(disbursed)

    def _launder_identities(self, pre_firm_id: np.ndarray) -> None:
        """S2 stretch — re-issue agent_id + redraw `registered` on dissolved members.

        Called immediately after `dissolution_step`. `pre_firm_id` is the
        snapshot of `pop.firm_id` taken before dissolution. Any prototype
        whose firm_id was `>= 0` before and `== -1` after just got
        released; we treat that release as a laundering event:

        * issue a fresh monotonic `agent_id` (advances `agent_next_id`);
        * redraw the `registered` bit per
          `RegistrationConfig.initial_registered_share`;
        * with `RegulatorConfig.laundering_detection_rate > 0`, flip a
          fraction of the redrawn bits back to False — the regulator
          catches some but not all laundering attempts.

        Humans are skipped (registration is an agent-side concept).
        Reads `regulator` rng so the new draw is isolated from population
        synthesis.
        """
        pop = self.population
        post_firm_id = pop.firm_id
        just_dissolved = (pre_firm_id >= 0) & (post_firm_id == -1)
        if not just_dissolved.any():
            return
        agent_laundered = (~pop.is_human) & just_dissolved
        n_laundered = int(agent_laundered.sum())
        if n_laundered == 0:
            return
        # Fresh, monotonic agent_id values for laundered agent prototypes.
        next_id = int(pop.agent_next_id)
        pop.agent_id[agent_laundered] = np.arange(
            next_id, next_id + n_laundered, dtype=np.int64,
        )
        pop.agent_next_id = next_id + n_laundered
        # Redraw the registered bit and apply optional detection.
        rng = self.rngs["regulator"]
        share = float(self.topology.cfg.registration.initial_registered_share)
        new_reg = rng.random(n_laundered) < share
        det_rate = float(
            getattr(self.topology.cfg.regulator, "laundering_detection_rate", 0.0)
        )
        if det_rate > 0.0:
            detected = rng.random(n_laundered) < det_rate
            new_reg = new_reg & ~detected
        pop.registered[agent_laundered] = new_reg

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

        # Stock-flow ledger setup. Pure instrumentation; no math change.
        track_ledger = self.cfg.track_ledger
        ledger = StepLedger() if track_ledger else None
        if track_ledger:
            weight_f64 = self.population.weight.astype(np.float64, copy=False)
            W_step_start = float(
                (self.population.wealth.astype(np.float64, copy=False) * weight_f64).sum()
            )
        else:
            weight_f64 = None
            W_step_start = 0.0

        def _total_wealth() -> float:
            return float(
                (self.population.wealth.astype(np.float64, copy=False) * weight_f64).sum()
            )

        strategy_cfg = self.topology.cfg.strategy
        if strategy_cfg.enabled:
            from engine.core.strategy import apply_actions, select_actions

            actions = select_actions(
                self.population.bandit_rewards,
                self.population.bandit_counts,
                strategy_cfg.epsilon,
                self.rngs["population"],
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
            self.population, self.topology, self.rngs,
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
            pair_sample_k=self.cfg.pair_sample_k,
            pair_sample_rng=self._pair_sample_rng,
        )

        dyn_cfg = self.topology.cfg.pop_dynamics
        retained_delta = tx.wealth_delta
        if dyn_cfg.enabled:
            retained_delta = retained_delta * dyn_cfg.savings_rate

        # Predict the population-level wealth contribution before the f32
        # cast and clip, so the ledger entry reflects the operator's intent.
        if track_ledger:
            predicted_tx = float(
                (retained_delta.astype(np.float64, copy=False) * weight_f64).sum()
            )
            ledger.add_wealth_in("transactions", predicted_tx)

        # Update wealth from transactions. With population dynamics enabled,
        # only saved surplus accumulates as wealth; the rest is consumed.
        self.population.wealth = np.clip(
            self.population.wealth + retained_delta.astype(np.float32),
            0.0, None,
        )

        # Pigouvian revenue recycling. Only the `human_wealth` mode adds
        # to the wealth stock; `friction_subsidy` pools and `capability`
        # adjusts capability, not wealth.
        if track_ledger and tx.pigouvian_revenue > 0:
            pig_cfg = self.topology.cfg.pigouvian
            if pig_cfg.enabled and pig_cfg.recycling == "human_wealth":
                ledger.add_wealth_in("pigouvian.recycle", float(tx.pigouvian_revenue))
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
            rng=self.rngs["folding"],
            cap_intermediating=self._cap_intermediating_mean,
            realized_alpha=tx.realized_alpha if strategy_cfg.enabled else None,
            fold_pressure=fold_pressure,
            dt=float(self.cfg.dt),
        )

        # Pigouvian tax on fold-cascade nominal. The base-trade tax (in
        # transactions.step) targets only the per-pair welfare surplus,
        # which is small relative to the fractal accounting that the fold
        # operator generates. Taxing fold.nominal_added at the configured
        # rate (weighted by automation gap, approximated as a2a_share +
        # ½·h2a_share) moves the tax base from welfare surplus to
        # parasitic accounting — the philosophically correct Pigouvian
        # target. Two effects:
        #   1. Deterrence: fold.nominal_added is reduced by the tax
        #      fraction, lowering nominal-GDP growth and EBI.
        #   2. Revenue: the tax amount is recycled through the existing
        #      pigouvian channel (human_wealth / friction_subsidy /
        #      capability), reaching humans as wealth.
        # This is what makes pigouvian_heavy/light/friction/baroque
        # behave distinctly from synthetic_consumers_v2 on the atlas.
        pig_cfg = self.topology.cfg.pigouvian
        if pig_cfg.enabled and pig_cfg.tax_rate > 0 and fold.nominal_added > 0:
            avg_gap = tx.a2a_share + 0.5 * tx.h2a_share
            fold_tax_rate = pig_cfg.tax_rate * avg_gap
            fold_tax = fold_tax_rate * fold.nominal_added
            fold.nominal_added *= (1.0 - fold_tax_rate)
            tx.pigouvian_revenue += fold_tax
            if track_ledger and pig_cfg.recycling == "human_wealth":
                ledger.add_wealth_in("pigouvian.recycle.fold", float(fold_tax))
            self._recycle_pigouvian_revenue(fold_tax)
        law_upkeep_cost = (
            self.topology.cfg.law.upkeep_investment * tx.real_surplus_added
            if law_enabled
            else 0.0
        )
        # W2b mission levy: a fraction of cleared real surplus routed
        # into a world-level public-objective pool. Bites only when
        # `MissionConfig.enabled = True`; off by default so the canonical
        # baselines stay bit-identical at the welfare-accounting level.
        mission_cfg = self.topology.cfg.mission
        if mission_cfg.enabled and mission_cfg.mission_levy > 0.0:
            mission_levy_step = float(
                mission_cfg.mission_levy * tx.real_surplus_added
            )
            self._mission_pool += mission_levy_step
        else:
            mission_levy_step = 0.0
        real_step = max(
            0.0,
            tx.real_surplus_added
            - law_upkeep_cost
            - mission_levy_step
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
            - mission_levy_step
            - fold.real_subtracted
            + fold.real_added_productive,
        )
        nominal_step = tx.nominal_volume + fold.nominal_added

        # Welfare ledger: real-welfare per-step flow accounting. Sources are
        # transactions and (when productive folding is on) the cascade's
        # variance-absorption contribution. Sinks are law upkeep and fold
        # overhead. The clip-to-zero happens when sinks exceed sources; we
        # record the clipped portion so the ledger's clipped net matches
        # `real_step` exactly.
        if track_ledger:
            ledger.add_welfare_in("transactions", float(tx.real_surplus_added))
            if law_enabled and law_upkeep_cost > 0:
                ledger.add_welfare_out("law.upkeep", float(law_upkeep_cost))
            if mission_levy_step > 0:
                ledger.add_welfare_out("mission.levy", float(mission_levy_step))
            if fold.real_subtracted > 0:
                ledger.add_welfare_out("fold.overhead", float(fold.real_subtracted))
            if fold.real_added_productive > 0:
                ledger.add_welfare_in("fold.productive", float(fold.real_added_productive))
            unclipped_welfare = ledger.welfare_net()
            if unclipped_welfare < 0:
                ledger.add_welfare_out("clip_floor", -unclipped_welfare)

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

            W_pre_inst = _total_wealth() if track_ledger else 0.0
            # S2 stretch — identity laundering. Snapshot pre-dissolution
            # firm_id so we know which prototypes were just released.
            launder_active = (
                inst_cfg.laundering_enabled
                and self.topology.cfg.registration.enabled
                and self.population.firm_id is not None
            )
            pre_firm_id = (
                self.population.firm_id.copy() if launder_active else None
            )
            dissolution_step(self.population, inst_cfg)
            if launder_active:
                self._launder_identities(pre_firm_id)
            formation_step(
                self.population, inst_cfg, self.rngs["population"],
                surplus_per_proto=tx.wealth_delta,
                mission_config=self.topology.cfg.mission,
            )
            merge_step(self.population, inst_cfg, self.rngs["population"])
            firm_overhead_step(self.population, inst_cfg)
            if track_ledger:
                W_post_inst = _total_wealth()
                inst_delta = W_post_inst - W_pre_inst
                if inst_delta != 0.0:
                    # firm_overhead_step is the only wealth-touching call;
                    # delta should always be ≤ 0 (overhead deduction).
                    ledger.add_wealth_out("institutions.firm_overhead", -inst_delta)

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

            dt = float(self.cfg.dt)
            capability_update(self.population, tx.wealth_delta, dyn_cfg, dt=dt)
            W_pre_dep = _total_wealth() if track_ledger else 0.0
            wealth_depreciation(self.population, dyn_cfg, dt=dt)
            if track_ledger:
                W_post_dep = _total_wealth()
                ledger.add_wealth_out("dynamics.depreciation", W_pre_dep - W_post_dep)
            churn_count = entry_exit(
                self.population,
                dyn_cfg,
                self.rngs["population"],
                registration_config=self.topology.cfg.registration,
                norms_config=self.topology.cfg.norms,
            )
            if track_ledger:
                W_post_ee = _total_wealth()
                ee_delta = W_post_ee - W_post_dep
                if ee_delta != 0.0:
                    # Entry/exit recycles failed prototypes. Record the
                    # observed signed delta — sign tells us whether the
                    # cohort net brought wealth in or took it out.
                    ledger.add_wealth_in("dynamics.entry_exit", ee_delta)

        # ---- W2b mission pool disbursement -------------------------------
        # Drain the mission pool toward coordinator-sector capability.
        # No-op when `MissionConfig.enabled = False` or the pool is
        # empty. Logged as a capability transfer (no wealth change), so
        # the stock-flow ledger only needs to see the levy at intake.
        self._disburse_mission_pool()

        # ---- W2a registration compliance cost ----------------------------
        # Per-step wealth charge against registered agents (humans
        # exempt). With `RegistrationConfig.enabled = False` or
        # `registration_cost = 0.0` (the canonical default) the block
        # does nothing and canonical baselines stay bit-identical.
        reg_cfg = self.topology.cfg.registration
        if reg_cfg.enabled and reg_cfg.registration_cost > 0.0:
            charge = float(reg_cfg.registration_cost)
            pay_mask = self.population.registered & (~self.population.is_human)
            if pay_mask.any():
                W_pre_reg = _total_wealth() if track_ledger else 0.0
                self.population.wealth[pay_mask] = np.clip(
                    self.population.wealth[pay_mask] - np.float32(charge),
                    0.0,
                    None,
                )
                if track_ledger:
                    W_post_reg = _total_wealth()
                    ledger.add_wealth_out(
                        "registration.compliance_cost",
                        W_pre_reg - W_post_reg,
                    )

        # End-of-step ledger residuals.
        if track_ledger:
            W_step_end = _total_wealth()
            observed_dW = W_step_end - W_step_start
            wealth_imbalance_abs = ledger.wealth_residual(observed_dW)
            wealth_imbalance_relative = (
                abs(wealth_imbalance_abs) / max(abs(W_step_end), 1.0)
            )
            welfare_imbalance_abs = ledger.welfare_residual(real_step)
        else:
            wealth_imbalance_abs = 0.0
            wealth_imbalance_relative = 0.0
            welfare_imbalance_abs = 0.0

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
            rejected_permeability=tx.rejected_permeability,
            rejected_regulator=tx.rejected_regulator,
            forged_registration_share=tx.forged_registration_share,
            human_labor_wage_step=tx.human_labor_wage,
            human_wage_per_sector_step=tx.human_wage_per_sector,
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
                self.topology.folding_propensity(
                    tx.realized_alpha if strategy_cfg.enabled else None,
                    dt=float(self.cfg.dt),
                )
                / self.topology.cfg.folding_propensity
                if self.topology.cfg.folding_propensity > 0
                else 0.0
            ),
            institutions_enabled=inst_cfg.enabled,
            dynamics_enabled=dyn_cfg.enabled,
            churn_count=churn_count,
            fold_per_depth_contribution=fold.per_depth_contribution,
            wealth_imbalance_abs=wealth_imbalance_abs,
            wealth_imbalance_relative=wealth_imbalance_relative,
            welfare_imbalance_abs=welfare_imbalance_abs,
            real_surplus_per_sector_step=tx.real_surplus_per_sector_step,
        )

        # Live-engine V2: attach the per-pair sample records (empty
        # when `pair_sample_k = 0`).
        m.pair_samples = tx.pair_samples

        # Cockpit Pass 2: snapshot the persistent cast (empty when
        # `cfg.cast_size == 0`). Each cast member emits a compact
        # record with current wealth, capability, firm membership,
        # autonomy, sector, *and* the emergent-behaviour fields
        # (strategy preference, norm distance from population mean)
        # that surface what each agent is *doing* under emergence/
        # norms-enabled scenarios.
        if self.cast_indices is not None:
            ci = self.cast_indices
            pop = self.population
            firm_arr = pop.firm_id if pop.firm_id is not None else None
            pref_arr = pop.intermediation_pref if pop.intermediation_pref is not None else None
            norm_arr = pop.norm_vector if getattr(pop, "norm_vector", None) is not None else None
            # Compute each member's norm distance from the population
            # weighted-mean norm vector — cheaper than emitting the
            # full per-prototype vector and just as expressive for the
            # "is this agent drifting from the centre" question.
            norm_mean = None
            if norm_arr is not None:
                wt = pop.weight.astype(np.float64)
                if wt.sum() > 0:
                    norm_mean = (norm_arr.astype(np.float64) * wt[:, None]).sum(0) / wt.sum()
            snap = []
            for i in ci:
                ii = int(i)
                entry = {
                    "idx": ii,
                    "is_human": bool(pop.is_human[ii]),
                    "sector": int(pop.sector[ii]),
                    "wealth": float(pop.wealth[ii]),
                    "capability": float(pop.capability[ii]),
                    "autonomy": float(pop.autonomy[ii]),
                    "firm_id": int(firm_arr[ii]) if firm_arr is not None else -1,
                    "stack": int(pop.stack[ii]),
                    "intermediation_pref": float(pref_arr[ii]) if pref_arr is not None else -1.0,
                }
                if norm_arr is not None and norm_mean is not None:
                    diff = norm_arr[ii].astype(np.float64) - norm_mean
                    entry["norm_distance"] = float(np.sqrt((diff * diff).sum()))
                    # Project onto first two dims for 2D positioning.
                    # Some scenarios use a 1D norm space — pad with zero.
                    nv = norm_arr[ii]
                    entry["norm_xy"] = [
                        float(nv[0]) if nv.shape[0] >= 1 else 0.0,
                        float(nv[1]) if nv.shape[0] >= 2 else 0.0,
                    ]
                else:
                    entry["norm_distance"] = -1.0
                    entry["norm_xy"] = None
                snap.append(entry)
            m.cast_snapshot = snap

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

        **Continuous mode.** If the resolved step budget is `<= 0`, the run
        loops indefinitely. Termination relies on the step callback (the
        serve layer raises a `_Cancelled` from inside the callback to stop
        the loop cooperatively). Without a callback the loop never exits —
        the engine itself doesn't decide when to stop in this mode.
        """
        n = n_steps if n_steps is not None else self.cfg.n_steps
        if n <= 0:
            # Continuous mode — relies on a cooperatively-cancelling
            # step_callback to terminate.
            while True:
                m = self.step()
                if step_callback is not None:
                    step_callback(m)
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

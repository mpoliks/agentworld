"""
Topology — the smooth/striated continuum and friction surface.

Smooth space (Deleuze/Guattari): nomadic, intensive, open-ended, haptic.
    Translated here as: low transaction cost, no folding, direct exchange.

Striated space: gridded, metric, hierarchical, optic.
    Translated here as: high coordination overhead, recursive market folding,
    every transaction layered with intermediating sub-transactions.

The control variable is `alpha` ∈ [0, 1]:
    alpha = 0  →  Smoothworld (Krier limit)
    alpha = 1  →  Baroqueworld (Bratton limit)

Real economies live somewhere in between, and may sit at different alphas
across sectors / stacks / time.

Beyond alpha, the topology specifies:
    - protocol_compat[k1, k2]  : compatibility between hemispherical stacks
    - sector_affinity[s1, s2]  : how readily sectors transact across boundaries
    - friction_floor           : irreducible compute/enforcement cost
    - matryoshka_overhead      : layered governance cost (law/market/individual)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

import numpy as np

from engine.core.population import N_SECTORS


@dataclass
class LawConfig:
    """Dynamic law layer configuration.

    When enabled, law is modeled as the substrate that enables stranger
    trade rather than only as a small random rejection tax. It defaults off
    so the demand/productive-folding plan can be evaluated independently.
    `law_strength` is world state initialized from this config and maintained
    by upkeep; `law_capture` is world state that rises with wealth
    concentration and falls with civic pushback.
    """

    enabled: bool = False
    law_strength_initial: float = 0.85
    law_capture_initial: float = 0.0
    upkeep_investment: float = 0.10
    natural_decay: float = 0.005
    law_decay_recovery: float = 1.0
    beta_capture_growth: float = 0.02
    civic_pushback_default: float = 0.30
    gamma_civic_pushback: Optional[float] = None
    concentration_penalty_gini_anchor: float = 0.4
    local_trust_surplus_floor: float = 0.35

    def __post_init__(self) -> None:
        if self.gamma_civic_pushback is None:
            if self.civic_pushback_default > 0:
                self.gamma_civic_pushback = (
                    self.beta_capture_growth * 0.5 / self.civic_pushback_default
                )
            else:
                self.gamma_civic_pushback = 0.0


@dataclass
class PigouvianConfig:
    """Pigouvian automation tax configuration.

    When enabled, A2A transactions pay a per-pair tax proportional to their
    "automation gap" — how far the pair is from having a human consumer at
    either endpoint. The tax is zero for H2H pairs, small for H2A, and
    maximal for fully-autonomous A2A pairs. Revenue is recycled back to
    humans via one of three configurable channels.

    Fields:
        enabled: Top-level flag. False preserves backward-compatible
            behavior; True turns on the per-pair Pigouvian tax.
        tax_rate: Maximum Pigouvian rate applied to pure A2A pairs
            (automation_gap ≈ 1 - a2a_floor). Effective rate for a pair
            is ``tax_rate * (1 - demand_factor)``.
        a2a_floor: Minimum demand factor for pure A2A pairs — the share
            of A2A surplus that genuinely reaches humans via downstream
            production. Reuses the same semantics as DemandConfig.a2a_floor.
        recycling: Revenue recycling channel.
            "human_wealth"     — redistribute to human prototypes weighted
                                 by inverse wealth (progressive transfer).
            "friction_subsidy" — reduce transaction cost for human-involving
                                 pairs in subsequent steps.
            "capability"       — invest in raising human capability over time.
        recycling_progressivity: Exponent on inverse-wealth weighting when
            recycling = "human_wealth". Higher values target poorer humans
            more aggressively. 1.0 = proportional to 1/wealth.
    """

    enabled: bool = False
    tax_rate: float = 0.0
    a2a_floor: float = 0.15
    recycling: Literal["human_wealth", "friction_subsidy", "capability"] = "human_wealth"
    recycling_progressivity: float = 1.0


@dataclass
class DemandConfig:
    """Demand-side feedback configuration.

    Demand-side feedback says: real welfare from a transaction depends on
    whether the produced thing has a human (or human-controlled agent)
    consumer at the end of the chain. Pure A2A activity creates *nominal*
    but not *real* welfare unless it ultimately reaches human consumption.

    The fields here govern how an A2A surplus contribution gets discounted
    when computing the new ``real_welfare_authentic`` aggregate. The flag
    ``enabled`` exists so existing scenarios can be re-anchored one at a
    time; with ``enabled = False`` the demand factor is identically 1.0
    and the alpha-engine reproduces its previous outputs bit-for-bit.

    Fields:
        enabled: Top-level flag. False preserves backward-compatible
            behavior in every existing scenario; True turns on the
            demand-modulation. Existing scenarios stay False until they
            are migrated and re-anchored.
        a2a_floor: Minimum fraction of A2A surplus that is "really real"
            — accounts for the share of A2A activity that does flow to
            humans indirectly via downstream production (intermediate
            goods, B2B inputs, etc.). 0.15 is an order-of-magnitude
            estimate; sweep it in sensitivity analysis.
        agent_consumer_share: Reserved for a future extension where
            autonomous agents can themselves be welfare endpoints (e.g.
            an agent buying compute it consumes for its own purposes
            that it valued). Currently unused by the demand-factor
            formula; kept on the dataclass to stabilize the public API.
    """

    enabled: bool = False
    a2a_floor: float = 0.15
    agent_consumer_share: float = 0.0


@dataclass
class StrategyConfig:
    """Per-prototype intermediation preference learning."""

    enabled: bool = False
    n_actions: int = 3
    epsilon: float = 0.10
    pref_delta: float = 0.05
    initial_pref: float = 0.5
    initial_pref_sd: float = 0.15
    reward_learning_rate: float = 0.1
    local_alpha_noise_sd: float = 0.02


@dataclass
class InstitutionConfig:
    """Firm formation and within-firm coordination dynamics."""

    enabled: bool = False
    max_firms: int = 5000
    formation_surplus_threshold: float = 0.02
    dissolution_wealth_threshold: float = 0.5
    within_firm_cost_discount: float = 0.60
    firm_overhead_per_member: float = 0.002
    merge_probability: float = 0.01
    formation_check_every_k: int = 5
    max_firm_size: int = 500


@dataclass
class PopulationDynamicsConfig:
    """Capability learning, depreciation, and prototype recycling."""

    enabled: bool = False
    capability_learning_rate: float = 0.001
    capability_decay_rate: float = 0.0002
    wealth_depreciation: float = 0.005
    exit_wealth_threshold: float = 0.1
    savings_rate: float = 0.3
    entry_capability_boost: float = 0.05



@dataclass
class MissionConfig:
    """Coordinator-set objective allocation (Tomašev et al. mission economy).

    Default-disabled stub. Plan 7 ships the scenarios + matched baselines
    that exercise this gate; the mechanism code is wired here so the
    transactions / world / metrics layers can reference it without an
    import-cycle in the meantime. With `enabled = False` (the default)
    every pair is cleared by Coasean bargaining and the pinned baselines
    reproduce bit-for-bit.

    `objective_alignment` is the alignment-space anchor the coordinator
    pulls toward; `objective_sectors` is the sector index set the
    mission cares about (empty tuple = all sectors). The score is
    `sector_match * (1 - |alignment_pair_mean - objective_alignment|)
    * capability_pair_mean`, and the top `mission_share * n_pairs` by
    score are captured.
    """

    enabled: bool = False
    mission_share: float = 0.10
    objective_alignment: float = 0.5
    objective_sectors: tuple = ()
    coordinator_overhead: float = 0.05


@dataclass
class PermeabilityConfig:
    """Permeability as a first-class axis (Tomašev et al.).

    Two distinct objects, one per side of the engine:

    * `agent_stack` — cross-stack agent compatibility. Replaces the old
      free-floating `TopologyConfig.cross_stack_compat` scalar. Default
      `0.55` matches the legacy default exactly so the canonical pinned
      baselines reproduce bit-for-bit.

    * `exo_lift_to_lastmile`, `exo_lastmile_to_drag`,
      `exo_drag_to_differential` — multiplicative gates on the exo-side
      cross-layer transfer kinetics. Defaults of `1.0` are no-ops (the
      gate is fully open and the legacy kinetic prevails); values < 1.0
      throttle the transfer in proportion. Plan 5's two new scenarios
      (`low_permeability_smooth` and `high_permeability_striated`) push
      these to opposite corners.

    Convention everywhere: `1.0` = perfectly permeable, `0.0` = sealed.
    See `docs/plans/permeability_axis.md` and
    `docs/concepts/smooth_striated.md`.
    """

    agent_stack: float = 0.55
    exo_lift_to_lastmile: float = 1.0
    exo_lastmile_to_drag: float = 1.0
    exo_drag_to_differential: float = 1.0


@dataclass
class RegulatorConfig:
    """Hadfield-style licensed-regulator audit gate.

    Distinct from the Krier "platform/deployer compatibility" gate that
    `transactions.py` always applies on the market layer. The regulator
    layer is *optional and additional*: when enabled, every executed pair
    is sampled at probability `coverage` (clamped above by
    `PopulationConfig.registration_coverage` because you cannot audit
    what you cannot identify) and audited pairs are rejected at rate
    `base_reject_rate + audit_quality * defect_score`. `defect_score`
    is the maximum over the two sides of `rejections / max(total, 1)`
    over the prototype's audit trail.

    Default-disabled. See `docs/plans/regulator_market_split.md` and
    `docs/concepts/matryoshkan_alignment.md`.
    """

    enabled: bool = False
    coverage: float = 0.0
    audit_quality: float = 0.0
    base_reject_rate: float = 0.01
    # Reserved for the time-decay defect-score variant. Not consumed by
    # the current implementation; pinned in the dataclass so the SALib
    # parameter list can name it without import-cycle concerns.
    defect_decay: float = 0.95


@dataclass
class TopologyConfig:
    """Configuration for the smooth-striated topology."""

    # The variable. 0 = smoothworld, 1 = baroqueworld.
    alpha: float = 0.5

    # Hemispherical compatibility matrix shape (n_stacks, n_stacks).
    # Diagonal is 1.0, off-diagonal in (0, 1] = how easy cross-stack trade is.
    # Plan 5: superseded by `permeability.agent_stack`. `cross_stack_compat`
    # remains as a deprecated alias — the build path reads the
    # permeability value when it is non-default and falls back to this
    # field otherwise so the existing scenario factories (which set
    # `cross_stack_compat` directly) keep working.
    n_stacks: int = 4
    cross_stack_compat: float = 0.55  # default off-diagonal value

    # Sector affinity: sectors close in this matrix transact more readily.
    # Generated from a low-dim latent + small noise, normalized to [0.2, 1.0].
    sector_affinity_seed: int = 1234

    # Friction floor: the irreducible per-transaction cost in units-of-account
    # — set by compute, enforcement, and protocol overhead. Tiny but nonzero.
    friction_floor: float = 1e-4

    # Matryoshka overhead: per-layer governance cost.
    # law layer is binary (transaction is allowed or not).
    # market layer is a tax τ_m on transaction surplus.
    # individual layer is a tax τ_i on transaction surplus.
    market_layer_tax: float = 0.025
    individual_layer_alignment_tax: float = 0.015

    # Coasean parameter: the multiplier that maps capability → friction reduction.
    # friction(τ) = friction_floor + base_friction * (1 - capability)^coase_exp
    coase_exp: float = 1.7
    base_friction: float = 0.05  # at zero capability, friction is high

    # Folding parameter: probability of spawning a sub-market when surplus > 0.
    # Modulated by alpha: at alpha=1, folding is aggressive; at alpha=0, none.
    folding_threshold_surplus: float = 0.01
    folding_max_depth: int = 6
    folding_propensity: float = 0.55  # at alpha=1; scales with alpha

    # Each fold spawns this many sub-markets per parent market on average.
    folding_branching: float = 2.7

    # When folded, each sub-market captures this share of parent surplus,
    # but adds a layer of nominal value-add. This is the *fractal multiplication*
    # of folded surfaces — each layer adds to nominal GDP without adding to
    # real welfare.
    fold_real_efficiency: float = 0.92  # 8% real surplus loss per fold layer
    fold_nominal_multiplier: float = 1.85  # each fold adds 85% to nominal GDP

    # Cumulative-fold-pressure feedback. Off by default to preserve the
    # frozen baselines. The brief's central claim is that fractal folding
    # accumulates: each layer of intermediation makes the next more
    # likely, so EBI should rise over a run rather than sit at a
    # cross-sectional steady state. When enabled, propensity is multiplied
    # by `1 + strength * max(0, pressure - anchor)`, capped at
    # `max_multiplier`. The pressure signal is supplied by the World as
    # `cumulative_fold_nominal / max(cumulative_real_welfare, 1)` — the
    # running EBI excess. (Gini was tried first as the signal but in
    # practice initial Pareto wealth dwarfs per-step flow, so gini is
    # near-stationary and the gini-feedback never fires.)
    folding_pressure_feedback: bool = False
    folding_pressure_anchor: float = 0.05
    folding_pressure_strength: float = 0.30
    folding_pressure_max_multiplier: float = 3.0

    # ---- Calibrated noise structure (see docs/concepts/epistemic_status.md) --
    # Noise model for per-pair surplus shocks. The Gaussian default preserves
    # historical scenario behaviour; t_copula injects heavy tails (Cont 2001)
    # and BEA 2022 sectoral co-movement.
    noise_model: Literal["gaussian", "t_copula"] = "gaussian"
    noise_dof: float = 4.0
    noise_sector_share: float = 0.4

    # Folding kernel. Geometric is the original closed-form expectation.
    # Hawkes injects realistic cascade variance (Bacry/Muzy 2015) while
    # preserving the closed-form mean at the same `folding_propensity`.
    folding_model: Literal["geometric", "hawkes"] = "geometric"
    hawkes_branching_ratio: float = 0.65
    hawkes_decay: float = 1.20

    # ---- Productive vs parasitic folding split ------------------------------
    # The fold operator currently produces nominal_added and real_subtracted.
    # When `base_variance_absorption > 0`, it *also* produces a real-welfare
    # contribution — modelling the productive economic content of risk
    # transfer (insurance, hedging, price discovery, capital efficiency).
    # The split is governed by the intermediating-agent capability and the
    # depth of the fold. Default is 0.0 so existing scenarios are unchanged
    # bit-for-bit; new scenarios opt in.
    #
    # See `engine/core/folding.py` and `docs/concepts/demand_and_intermediation.md`
    # for the full derivation.
    base_variance_absorption: float = 0.0   # depth-1 productive welfare share at max capability
    productive_decay: float = 0.65          # per-layer decay of welfare creation
    cap_midpoint: float = 0.50              # capability above which folding becomes productive
    cap_slope: float = 4.0                  # sharpness of the capability → productivity sigmoid
    max_productive_real_share: float = 0.60 # caps productive folding by underlying real surplus

    # ---- Demand-side feedback ------------------------------------------------
    # Real welfare from a transaction depends on whether the produced thing
    # has a human (or human-controlled agent) consumer. With
    # `demand.enabled = False` this is a no-op (the new authentic-welfare
    # metric equals real welfare). See `DemandConfig` and the concept doc.
    demand: DemandConfig = field(default_factory=DemandConfig)

    # ---- Pigouvian automation tax -----------------------------------------------
    # Per-pair tax proportional to the automation gap (1 - demand_factor).
    # Revenue is recycled to humans. Default-off; see
    # `docs/concepts/pigouvian_automation.md`.
    pigouvian: PigouvianConfig = field(default_factory=PigouvianConfig)

    # ---- Hadfield-style licensed-regulator audit ---------------------------
    # Distinct from the platform/deployer gate (Krier, the always-on
    # `0.02 + 0.06*(1-sec_aff)` term in `transactions.py`). When enabled,
    # adds a second OR-composed market-layer rejection driven by audit
    # coverage and defect history. Bounded above by registration coverage
    # — see `RegulatorConfig` and `docs/plans/regulator_market_split.md`.
    regulator: RegulatorConfig = field(default_factory=RegulatorConfig)

    # ---- Permeability as a first-class axis (Plan 5) -----------------------
    # Defaults reproduce existing canonical scenarios bit-for-bit:
    # `agent_stack = 0.55` matches the legacy `cross_stack_compat`, and
    # the three exo permeability scalars default to 1.0 (no gate). See
    # `PermeabilityConfig` and `docs/plans/permeability_axis.md`.
    permeability: PermeabilityConfig = field(default_factory=PermeabilityConfig)

    # ---- Mission-economy allocation (Plan 7 stub, default-off) -------------
    # Coordinator-set objective; opt-in. When disabled, every pair is
    # cleared by Coasean bargaining — the canonical pinned baselines
    # reproduce exactly. The matched-permeability scenarios that exercise
    # this lever ship in the follow-up plan-7 PR. See `MissionConfig`.
    mission: MissionConfig = field(default_factory=MissionConfig)

    # ---- Dynamic law layer ----------------------------------------------------
    # See `brief/dynamic_mechanisms.md`, §3. Default-off until the law
    # mechanism is evaluated separately. `World` carries the mutable
    # law-strength/capture state; this config supplies initial conditions
    # and policy controls.
    law: LawConfig = field(default_factory=LawConfig)

    # ---- Endogenous emergence mechanisms -------------------------------------
    # Default-off so historical alpha-engine scenarios keep the same execution
    # path unless they explicitly opt in.
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    institutions: InstitutionConfig = field(default_factory=InstitutionConfig)
    pop_dynamics: PopulationDynamicsConfig = field(default_factory=PopulationDynamicsConfig)


@dataclass
class Topology:
    """The smooth-striated topology — a parameter surface that conditions all transactions."""

    cfg: TopologyConfig
    cross_stack: np.ndarray  # (n_stacks, n_stacks) compatibility matrix
    sector_affinity: np.ndarray  # (N_SECTORS, N_SECTORS) affinity matrix

    @classmethod
    def build(cls, cfg: Optional[TopologyConfig] = None) -> "Topology":
        if cfg is None:
            cfg = TopologyConfig()

        # Cross-stack matrix: identity diagonal, agent-stack permeability
        # off-diag. The first-class axis is `permeability.agent_stack`;
        # `cross_stack_compat` is the deprecated alias preserved so
        # existing scenario factories that set the legacy field still
        # behave as before. When the user has explicitly moved the legacy
        # field off its default, prefer that — otherwise read the new
        # permeability field.
        K = cfg.n_stacks
        agent_perm = (
            float(cfg.cross_stack_compat)
            if cfg.cross_stack_compat != 0.55
            else float(cfg.permeability.agent_stack)
        )
        cross = np.full((K, K), agent_perm, dtype=np.float32)
        np.fill_diagonal(cross, 1.0)

        # Sector affinity: low-dim latent embedding for sectors, then RBF kernel.
        rng = np.random.default_rng(cfg.sector_affinity_seed)
        latent = rng.standard_normal((N_SECTORS, 3)).astype(np.float32)
        # Hand-tune some structure: information / finance close, agriculture far.
        # Just a stylized affinity matrix; not load-bearing on the dynamics.
        d2 = ((latent[:, None, :] - latent[None, :, :]) ** 2).sum(axis=-1)
        aff = np.exp(-d2 / 2.0)  # RBF kernel
        # Normalize to [0.2, 1.0].
        aff = 0.2 + 0.8 * (aff - aff.min()) / (aff.max() - aff.min())
        np.fill_diagonal(aff, 1.0)
        return cls(cfg=cfg, cross_stack=cross, sector_affinity=aff.astype(np.float32))

    # ---- core kernels -----------------------------------------------------

    def transaction_cost(
        self,
        capability_a: np.ndarray,
        capability_b: np.ndarray,
        stack_a: np.ndarray,
        stack_b: np.ndarray,
        alpha_override: np.ndarray | float | None = None,
    ) -> np.ndarray:
        """
        Compute per-transaction cost in units-of-account for a vector of pairs.

        Lower capability → higher cost (Coase). Cross-stack → higher cost.
        Higher alpha (more striated) increases the protocol overhead.
        """
        cfg = self.cfg
        alpha = alpha_override if alpha_override is not None else cfg.alpha
        cap_min = np.minimum(capability_a, capability_b)
        # Cross-stack compatibility (vectorized lookup).
        compat = self.cross_stack[stack_a, stack_b]

        # Coasean term: friction shrinks with capability.
        coase_term = cfg.base_friction * (1.0 - cap_min) ** cfg.coase_exp

        # Striation term: more striated → more protocol overhead, regardless of cap.
        striation_term = alpha * 0.020 * (1.0 + 0.3 * (1.0 - compat))

        # Cross-stack term.
        cross_term = (1.0 - compat) * 0.015

        # Matryoshka layer overhead (market + individual taxes are applied to
        # surplus elsewhere; here we add only the law/protocol overhead).
        floor = cfg.friction_floor

        return floor + coase_term + striation_term + cross_term

    def folding_propensity(
        self,
        realized_alpha: float | None = None,
        fold_pressure: float | None = None,
        dt: float = 1.0,
    ) -> float:
        """How likely a positive-surplus market is to spawn sub-markets this step.

        With `folding_pressure_feedback` enabled, the alpha-driven base
        propensity is amplified by accumulated fold-pressure above the
        anchor, capped at `folding_pressure_max_multiplier`. The
        `fold_pressure` argument is supplied by the World as
        `cumulative_fold_nominal / max(cumulative_real_welfare, 1)`. This
        produces a positive-feedback loop: each step's folding raises the
        signal that drives next step's folding propensity, so EBI becomes
        a trajectory rather than a steady-state ratio.

        The `dt` argument applies the discrete-time analog
        `p_per_step = 1 − (1 − p_unit)^dt`, treating the existing default
        propensity as the probability per unit of model time. With
        `dt = 1.0` (the default and the calibration anchor) the math is
        unchanged. Larger `dt` raises the per-step firing probability of
        the cascade; the cascade *contents* (branching, depth-decay,
        Hawkes self-excitation) are intra-cascade and remain
        dt-invariant. See `docs/concepts/time_discretization.md`.
        """
        cfg = self.cfg
        alpha = cfg.alpha if realized_alpha is None else realized_alpha
        base = cfg.folding_propensity * (alpha ** 1.4)
        if (
            cfg.folding_pressure_feedback
            and fold_pressure is not None
            and fold_pressure > cfg.folding_pressure_anchor
        ):
            excess = fold_pressure - cfg.folding_pressure_anchor
            mult = 1.0 + cfg.folding_pressure_strength * excess
            mult = min(mult, cfg.folding_pressure_max_multiplier)
            base = base * mult
        base = min(base, 1.0)
        if dt != 1.0:
            # Treat `base` as p_per_unit_model_time; the per-step
            # probability over `dt` units is the discrete-time analog of
            # an exponential rate.
            base = 1.0 - (1.0 - base) ** float(dt)
        return min(base, 1.0)

    def matryoshka_real_tax(self) -> float:
        """Fraction of real surplus consumed by market+individual layers."""
        return self.cfg.market_layer_tax + self.cfg.individual_layer_alignment_tax

    # ---- diagnostics ------------------------------------------------------

    def label(self) -> str:
        a = self.cfg.alpha
        if a < 0.15:
            return "direct-trade"
        if a > 0.85:
            return "fractal-trade"
        if a < 0.45:
            return "mostly direct"
        if a > 0.55:
            return "mostly fractal"
        return "balanced"

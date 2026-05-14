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
from typing import Any, Literal, Optional

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
    # Transaction-size cap (legal_levers_in_agent_economies.md). When
    # the per-pair surplus exceeds `transaction_size_cap`, the
    # `cap_recipient` mode determines what happens:
    #   - "tax"    surplus above the cap is collected as windfall tax
    #              and recycled through the same channels as Pigouvian
    #              (StepMetrics.windfall_tax_revenue_*).
    #   - "reject" the pair is added to law_reject before execution.
    # Default `inf` keeps the cap inactive and the canonical baselines
    # bit-identical. See `docs/research/legal_levers_in_agent_economies.md`.
    transaction_size_cap: float = float("inf")
    cap_recipient: str = "tax"

    def __post_init__(self) -> None:
        if self.gamma_civic_pushback is None:
            if self.civic_pushback_default > 0:
                self.gamma_civic_pushback = (
                    self.beta_capture_growth * 0.5 / self.civic_pushback_default
                )
            else:
                self.gamma_civic_pushback = 0.0


@dataclass
class RegulatorConfig:
    """Hadfield-style government-licensed third-party regulator.

    The Krier middle layer (`market_reject` / `platform_reject`) and the
    Hadfield regulatory market are *not* the same object. The first models
    foundation-model deployer policy and platform terms-of-service; the
    second models government-licensed third parties competing on audit
    quality and strictness. Conflating them is the tier-1 conflation
    Hadfield's *Regulatory Markets: The Future of AI Governance*
    (Jurimetrics, Winter 2026) calls out.

    This config adds a second gate that fires in parallel with the
    platform gate — a pair has to pass *both* to execute. Each stack
    draws a regulator vendor from a pool the operator parameterises;
    the vendor's `strength × audit_quality × (1 − capture)` becomes the
    per-pair rejection probability. The strictest of the two endpoints'
    regulators gates the trade (regulators are jurisdictional, and the
    stricter jurisdiction binds).

    With `enabled = False` (the default) the gate doesn't fire, no rng
    draws are consumed, and the canonical pinned baselines stay
    bit-identical. The `regulator_layer_tax` adds a third tax channel
    to `matryoshka_real_tax()` parallel to `market_layer_tax` and
    `individual_layer_alignment_tax` — it bites only on pairs that pass
    the gate, modelling the cost of compliance with a real regulator.

    See `docs/plans/hadfield_jacobs_robustness.md` (W1a).
    """

    enabled: bool = False
    # Per-stack vendor params. Accept a scalar (same vendor for every
    # stack) or a tuple of length `n_stacks` (per-stack vendor draws
    # supplied by the operator). Validated at world build.
    regulator_strength: Any = 0.15
    regulator_capture: Any = 0.0
    regulator_audit_quality: Any = 1.0
    # Third tax channel; added to `matryoshka_real_tax()` when enabled.
    # 0 = the regulator gate rejects but doesn't tax surviving surplus.
    regulator_layer_tax: float = 0.0
    # Audit-trail tampering rate (S1 stretch). Per-step probability that
    # an unregistered agent's `registered` bit is *forged to True* in the
    # regulator's view, scaled by `regulator_capture[stack]` so capture
    # is the load-bearing input. With `audit_tampering_rate = 0` (the
    # default) or `registration.enabled = False`, the regulator reads
    # the raw `pop.registered` bit and the `registration_floor` bump
    # bites on every unregistered endpoint. Crank both this lever and
    # `regulator_capture` to 1.0 and the floor is fully defeated —
    # unregistered actors trade as if registered. Surfaced on
    # `StepMetrics.forged_registration_share`. See S1 in
    # `docs/plans/registration_stretch_goals.md`.
    audit_tampering_rate: float = 0.0
    # S2 stretch — laundering-detection rate. Fraction of laundered
    # prototypes (firm-dissolution + identity re-issue) whose newly
    # drawn `registered` bit is flipped back to False — the regulator
    # catches some but not all laundering attempts. 0 (the default)
    # means the regulator catches no laundering. Only reads under
    # `InstitutionConfig.laundering_enabled` + `RegistrationConfig.enabled`.
    laundering_detection_rate: float = 0.0


@dataclass
class NormsConfig:
    """Norm-participation alignment layer (W1b).

    The largest single change in the Hadfield-Jacobs robustness round
    and the one that carries the most epistemic load. Pre-W1b the
    individual-layer rejection gate uses static Euclidean distance on a
    fixed scalar `alignment`:

        align_reject ~ U(0,1) < 0.03 + 0.20 · |alignment_a − alignment_b|
                                       · (1 − 0.5 · avg_autonomy)

    Hadfield's *Normative Infrastructure for AI Alignment* (AIhub, May
    2025) argues that alignment is *participation in evolving community
    norms*, not preference-matching at static distance. In Smoothworld
    the individual layer is the binding constraint (~50% rejection
    share per `docs/concepts/matryoshkan_alignment.md:71`), so the
    binding constraint's misspecification is load-bearing.

    With `enabled = True`:

    * Each prototype carries `Population.norm_vector` of shape
      `(n, n_dimensions)` — a position in a K-dim norm space that
      generalizes the scalar alignment.
    * `align_reject` re-uses the legacy formula but with
      `align_dist = ||norm_a − norm_b||_2 / sqrt(K)` (normalized so it
      lands in the same [0, 2] range as the scalar form).
    * After each step, every prototype's norm drifts toward the
      *capability-weighted mean of its executed partners' norms* at
      rate `update_rate`. This is the participation-in-community-norms
      operationalization: agents who trade together converge in norm
      space; agents who don't, don't.

    With `enabled = False` (the canonical default) the field is
    populated but unread, so canonical pinned baselines stay bit-
    identical. The dedicated `initial_norm_seed` keeps norm
    initialisation isolated from any other population draw.

    See `docs/plans/hadfield_jacobs_robustness.md` (W1b) and
    `docs/concepts/matryoshkan_alignment.md`.
    """

    enabled: bool = False
    # Dimensionality of the norm space. K=1 collapses to a near-bit-
    # identical generalization of the scalar `alignment`; K=4 is the
    # default — enough room for cluster structure without exploding
    # memory at xlarge scale (4 × 88M × 4B ≈ 1.4 GB at float32).
    n_dimensions: int = 4
    # Initial spread of norm components, per dim. Drawn N(0, sd) then
    # clipped to [-1, 1]. Defaults loosely match the scalar
    # `alignment` spread for humans (0.45) so a K=1 run is comparable.
    initial_norm_sd_human: float = 0.45
    initial_norm_sd_agent: float = 0.25
    # EMA factor applied each step to the norm vector. 0 = norms never
    # update (pure static distance on the new vector); larger = faster
    # convergence. 0.05 is a moderate default; the `norms_brittle`
    # adversarial sibling raises this to produce whiplash.
    update_rate: float = 0.05
    # When True, partner norm influence is weighted by partner
    # capability — high-capability agents shape the local norm more.
    capability_weight: bool = True
    # Per-pair rejection-rate calibration. Matches the legacy formula
    # structure: `align_reject ~ U(0,1) < base + slope · dist · (1 − ½·avg_auto)`.
    # Defaults reproduce the legacy 0.03 / 0.20 constants.
    base_reject_rate: float = 0.03
    distance_slope: float = 0.20
    # Dedicated seed for initial norm-vector draw at synthesize time.
    initial_norm_seed: int = 0
    # Per-agent certified-vocabulary fidelity (Schoenegger et al. 2026).
    # Mean of a Beta-distributed `pop.certified` array drawn at synthesize
    # time. The alignment gate scales `align_dist` by
    # `(1 − min(cert_a, cert_b))`, so cert=1 on both sides drops alignment
    # distance to 0 (no rejection) and cert=0 on either side recovers the
    # raw norm distance. Default 0.0 keeps `pop.certified` None and
    # leaves the canonical baselines (incl. norms_drift/capture/brittle)
    # bit-identical. The spatial sandbox sets this to 0.5.
    # See `docs/research/verifiable_semantics.md`.
    certified_fraction: float = 0.0
    # Std-dev of the Beta-distributed cert draw. Clamped so the implied
    # Beta concentration stays positive; large sd produces a U-shaped
    # cert distribution where most agents are near 0 or 1.
    certified_fraction_sd: float = 0.15


@dataclass
class LaborConfig:
    """Human-side labor market (W2c).

    Jacobs's labor-displacement work (Oxford Martin AIGI) treats the
    A2A share of an economy as the structural variable that determines
    whether the surplus from agent-driven trade reaches human wages or
    is captured inside the agent layer. Pre-W2c the alpha-engine has no
    explicit price-on-human-labor: every executed pair distributes its
    surplus 50/50 between the two endpoints by Nash bargaining, with no
    factor-share split.

    W2c adds the smallest credible version. Per-sector `labor_share` is
    the fraction of cleared real surplus that, in a non-automated
    world, would go to labor (wages). For each executed pair we compute
    a labor wedge

        wedge = labor_share[sec] · (1 − automation_gap) · real_surplus

    where `automation_gap = 1 − demand_factor(pair)` reuses the
    Pigouvian / demand semantics. The wedge is *deducted* from the pair
    payouts (i.e. the Nash 50/50 splits the post-wedge residual) and
    *routed to humans in the production-side sector* (`sec_a`),
    proportional to human importance weight inside that sector. A
    sector with no human prototypes has its share fall into the void —
    documented as structural, not a runtime accident. The larger the
    automation_gap (the more A2A the pair is), the smaller the human
    wage share — labor displacement made concrete.

    With `enabled = False` (the canonical default) the wedge is zero
    everywhere and the pre-W2c engine math holds bit-for-bit. The
    layering with the existing Pigouvian tax is sequential: Pigouvian
    fires first on `real_pair_surplus`; the labor wedge then bites on
    `real_pair_surplus_post_pig`. The two mechanisms can coexist.

    See `docs/plans/hadfield_jacobs_robustness.md` (W2c).
    """

    enabled: bool = False
    # Per-sector labor share. Accept a scalar (same fraction in every
    # sector) or a length-N_SECTORS sequence. Validated at world build.
    labor_share: Any = 0.0
    # Floor for the automation-gap calculation: matches the
    # `DemandConfig.a2a_floor` / `PigouvianConfig.a2a_floor` semantics.
    # A larger floor means even pure-A2A pairs route some wage to
    # humans (indirect downstream benefits captured as wage).
    a2a_floor: float = 0.15


@dataclass
class MissionConfig:
    """Mission-economy lever (W2b).

    The artifact's default reading is "two attractors and a basin between
    them"; the Tomašev / Jacobs *Virtual Agent Economies* paper warns
    against exactly that framing — there are coordination paths that
    don't reduce to either smooth-Coasean or baroque-folded equilibria.
    W2b adds the smallest credible third lever using mechanisms that
    already exist in the engine:

    * `coordinator_sectors` is a tuple of sector indices treated as
      mission-tagged. In `engine/core/institutions.py:formation_step`,
      candidates in those sectors see their `formation_surplus_threshold`
      multiplied by `formation_threshold_factor` (< 1.0 makes
      coordination cheaper there). With institutions disabled the bias
      is a no-op.
    * `mission_levy` skims a fraction of cleared real surplus into a
      world-level `_mission_pool` — analogous to the Pigouvian revenue
      channel but routed to a *public-objective* sink rather than a
      redistributive transfer.
    * `capability_uplift_per_unit_pool` then disburses the pool by
      raising the capability of agents in coordinator sectors. The
      `levy_target` choice controls *which* agents receive the uplift:
      `"coordinator_uplift"` (the policy ideal — flat per-agent share),
      `"regressive_pool"` (the captured mode — uplift concentrates on
      already-high-capability agents).

    Default-off so canonical baselines stay bit-identical. Siblings
    `mission_captured` and `mission_competing` in
    `engine/scenarios/__init__.py` make the point that the lever isn't
    free — capture and competing agendas can flip the welfare sign even
    with the levy on.

    See `docs/plans/hadfield_jacobs_robustness.md` (W2b).
    """

    enabled: bool = False
    # Sector indices to treat as mission-tagged. Empty = the lever has
    # nowhere to bite (still legal; produces a useful adversarial
    # control). See `engine/core/population.SECTOR_NAMES`.
    coordinator_sectors: tuple = ()
    # Multiplier on `InstitutionConfig.formation_surplus_threshold` for
    # candidates inside `coordinator_sectors`. 1.0 = no bias. Values <
    # 1.0 lower the bar in coordinator sectors (mission firms form
    # more easily); values > 1.0 raise it (the "competing agendas"
    # adversarial sibling).
    formation_threshold_factor: float = 1.0
    # Fraction of cleared real surplus routed to the mission pool. 0 =
    # no levy. Acts like a small flat tax on every executed pair, but
    # the revenue is *not* recycled to humans (cf. Pigouvian); it funds
    # capability uplift in coordinator sectors.
    mission_levy: float = 0.0
    # Capability boost per unit of accumulated pool, applied each step
    # to agents in `coordinator_sectors`. The disbursed amount is
    # subtracted from the pool, so the pool drains as it disburses.
    capability_uplift_per_unit_pool: float = 0.0
    # Disbursement targeting.
    #   "coordinator_uplift" — equal share to every coordinator-sector
    #     agent (the policy ideal).
    #   "regressive_pool"     — share is proportional to current
    #     capability (the captured mode: existing elites absorb the
    #     mission investment).
    levy_target: Literal["coordinator_uplift", "regressive_pool"] = "coordinator_uplift"


@dataclass
class RegistrationConfig:
    """Hadfield-style persistent agent identity + registration regime (W2a).

    Pre-W2a every transaction in the alpha-engine is between two
    anonymous prototype draws — there is no stable identifier across
    steps and no `registered` bit a regulator could read. Hadfield's
    *Legal Infrastructure for Transformative AI Governance*
    (arXiv:2602.01474, Feb 2026) argues that registration is the
    precondition for everything else in the regulatory stack.

    With `enabled=False` (the default) the registration mechanism is
    inert and the canonical pinned baselines stay bit-identical. With
    `enabled=True`:

    * Each agent prototype carries `Population.registered: bool`.
      Humans are exempt (always treated as registered).
    * `registration_cost` is charged against the wealth of every
      registered agent every step — the compliance overhead.
    * `registration_floor` adds to the regulator gate's per-pair
      rejection probability when an endpoint is an unregistered agent.
      This is the lever by which the registration regime *does work*:
      unregistered actors can still trade but face a higher chance of
      being blocked at the regulator layer. Requires
      `RegulatorConfig.enabled = True` for the gate-level effect; the
      wealth charge applies regardless.
    * `Population.agent_id` is a stable int64 identifier issued
      monotonically. The dynamics layer (entry/exit) re-issues fresh
      identifiers on prototype recycle.

    See `docs/concepts/registration.md` and W2a in
    `docs/plans/hadfield_jacobs_robustness.md`.
    """

    enabled: bool = False
    # Per-step wealth charge against registered agents. 0 = compliance
    # is free at the unit price (the rejection-floor lever still bites).
    registration_cost: float = 0.0
    # Additional probability the regulator gate rejects a pair that
    # includes at least one unregistered agent. Composes additively
    # with the vendor's base rejection probability per endpoint and is
    # clipped to [0, 1] in the gate.
    registration_floor: float = 0.0
    # Share of *agents* who carry the `registered` bit at world build.
    # Humans are always registered. 1.0 = everyone-registered baseline
    # (enabling the mechanism but exercising none of the asymmetry it
    # introduces).
    initial_registered_share: float = 1.0
    # Random seed used to assign initial registration status at world
    # build. Distinct from `PopulationConfig.seed` so toggling the
    # registration mechanism doesn't perturb other population draws.
    initial_registration_seed: int = 0
    # S3 stretch — multi-jurisdiction registration arbitrage. With
    # `arbitrage_enabled = True`, every agent picks the stack with the
    # lowest effective regulator rejection rate
    # (`strength × audit_quality × (1 − capture)`) at world build; that
    # stack becomes the agent's `registration_stack` and the
    # regulator-gate floor reads its effective strength rather than the
    # trading partner's. Default-off so canonical baselines stay
    # bit-identical (`Population.registration_stack` is `None`). See S3
    # in `docs/plans/registration_stretch_goals.md`.
    arbitrage_enabled: bool = False


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
    # S2 stretch — identity laundering through firm dissolution. When
    # enabled, members of a dissolved firm are issued fresh `agent_id`
    # values and have their `registered` bit re-drawn per
    # `RegistrationConfig.initial_registered_share`. A previously-flagged
    # agent can shed its regulator history by riding a firm through
    # dissolution. Requires `RegistrationConfig.enabled = True` (the
    # mechanism reads/writes the registered field); otherwise it is a
    # no-op. Default-off so the W2a baselines stay bit-identical. See
    # S2 in `docs/plans/registration_stretch_goals.md`.
    laundering_enabled: bool = False

    # Cross-sector firm formation. Default-off so the canonical
    # baselines reproduce bit-identically. When True, `formation_step`
    # bins independent candidates by `stack` alone, letting a firm span
    # sectors within one hemispherical stack. The spatial sandbox
    # turns this on; emergent firm-sector composition is surfaced
    # per-cast as `cast_snapshot[*].firm_sectors`.
    cross_sector_firms: bool = False


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
class TopologyConfig:
    """Configuration for the smooth-striated topology."""

    # The variable. 0 = smoothworld, 1 = baroqueworld.
    alpha: float = 0.5

    # Hemispherical compatibility matrix shape (n_stacks, n_stacks).
    # Diagonal is 1.0, off-diagonal in (0, 1] = how easy cross-stack trade is.
    n_stacks: int = 4
    cross_stack_compat: float = 0.55  # default off-diagonal value

    # Sandbox permeability between stacks (Tomašev / Jacobs, *Virtual Agent
    # Economies*, arXiv:2509.10147). Probability that a sampled cross-stack
    # pair is *attempted* at all, applied before the Matryoshka cascade.
    # 1.0 reproduces the historical pre-2026-05 behavior bit-for-bit
    # (no rng draw is consumed). Below 1.0 the gate rejects cross-stack
    # attempts at the boundary, surfaced as `rejected_permeability` in
    # `TransactionResult` and `StepMetrics`. Same-stack pairs are never
    # gated. See `docs/concepts/smooth_striated.md` "What this axis is not"
    # and `docs/plans/hadfield_jacobs_robustness.md` (W1c).
    cross_stack_permeability: float = 1.0

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

    # ---- Dynamic law layer ----------------------------------------------------
    # See `brief/dynamic_mechanisms.md`, §3. Default-off until the law
    # mechanism is evaluated separately. `World` carries the mutable
    # law-strength/capture state; this config supplies initial conditions
    # and policy controls.
    law: LawConfig = field(default_factory=LawConfig)

    # ---- Hadfield regulator (W1a, Regulatory Markets) ------------------------
    # Government-licensed third-party regulator running in parallel with
    # the platform layer. Default-off keeps `market_reject` as the sole
    # middle-layer gate so canonical baselines stay bit-identical. See
    # `docs/plans/hadfield_jacobs_robustness.md` and the `RegulatorConfig`
    # docstring above.
    regulator: RegulatorConfig = field(default_factory=RegulatorConfig)

    # ---- Registration regime (W2a, Legal Infrastructure) ---------------------
    # Persistent agent identity + the registered-bit a regulator can read.
    # Default-off so the canonical pre-W2a engine is bit-identical; when
    # enabled, agents carry a stable `agent_id` and a `registered` mask,
    # pay a per-step compliance cost, and unregistered agents face an
    # additional rejection probability at the regulator layer (couples
    # to W1a). See `RegistrationConfig` above and
    # `docs/concepts/registration.md`.
    registration: RegistrationConfig = field(default_factory=RegistrationConfig)

    # ---- Mission economy (W2b, Virtual Agent Economies) ----------------------
    # Third lever beyond smooth-Coasean / baroque-folded: coordinator
    # sectors form firms more easily, a small levy on cleared surplus
    # funds capability uplift in those sectors. Default-off keeps the
    # canonical baselines bit-identical. See `MissionConfig` above and
    # W2b in `docs/plans/hadfield_jacobs_robustness.md`.
    mission: MissionConfig = field(default_factory=MissionConfig)

    # ---- Human-side labor market (W2c, Jacobs labor displacement) ------------
    # Per-sector labor_share splits cleared real surplus between agent
    # operators (the existing Nash 50/50) and human labourers (a new
    # wage channel), with substitution elasticity driven by the
    # automation gap. Default-off so canonical baselines stay bit-
    # identical. See `LaborConfig` above and
    # `docs/plans/hadfield_jacobs_robustness.md` (W2c).
    labor: LaborConfig = field(default_factory=LaborConfig)

    # ---- Norm-participation alignment (W1b, Hadfield) ------------------------
    # Replaces static-distance `align_reject` with distance-in-norm-space
    # plus a per-step EMA update toward executed partners. Default-off
    # keeps the canonical baselines bit-identical at the field level
    # (the norm_vector is populated from a dedicated seed but unread).
    # See `NormsConfig` above and W1b in
    # `docs/plans/hadfield_jacobs_robustness.md`.
    norms: NormsConfig = field(default_factory=NormsConfig)

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

        # Cross-stack matrix: identity diagonal, cross_stack_compat off-diag.
        K = cfg.n_stacks
        cross = np.full((K, K), cfg.cross_stack_compat, dtype=np.float32)
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
        """Fraction of real surplus consumed by the middle layers.

        Adds `regulator_layer_tax` when the Hadfield regulator gate is
        enabled. With the regulator off (the canonical default), the tax
        collapses to `market_layer_tax + individual_layer_alignment_tax`
        — bit-identical to the pre-W1a engine.
        """
        tax = self.cfg.market_layer_tax + self.cfg.individual_layer_alignment_tax
        if self.cfg.regulator.enabled:
            tax += float(self.cfg.regulator.regulator_layer_tax)
        return tax

    def labor_share_arr(self) -> np.ndarray:
        """Per-sector labor-share vector for the W2c wage wedge.

        Accepts `LaborConfig.labor_share` as either a scalar (same share
        in every sector) or a length-N_SECTORS sequence (per-sector
        Jacobs labor-share calibration). Returns a float64 array of
        shape `(N_SECTORS,)`. The validation happens here so the
        per-pair gate can index by sector cheaply.
        """
        cfg = self.cfg.labor
        v = cfg.labor_share
        if np.isscalar(v):
            return np.full(N_SECTORS, float(v), dtype=np.float64)
        arr = np.asarray(v, dtype=np.float64)
        if arr.shape != (N_SECTORS,):
            raise ValueError(
                f"LaborConfig.labor_share must be a scalar or a length-"
                f"{N_SECTORS} sequence (N_SECTORS={N_SECTORS}); got shape "
                f"{arr.shape}."
            )
        return arr

    def regulator_vendor_arrays(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Per-stack (strength, capture, audit_quality) vendor arrays.

        `RegulatorConfig` accepts each of the three vendor params either
        as a scalar (same vendor for every stack) or as a length-`n_stacks`
        sequence (operator-supplied per-stack draws from the vendor pool).
        This helper broadcasts and validates so the inner loop can index
        by stack id. Returns float64 arrays of shape `(n_stacks,)`.
        """
        reg = self.cfg.regulator
        K = self.cfg.n_stacks

        def _arr(v, name: str) -> np.ndarray:
            if np.isscalar(v):
                return np.full(K, float(v), dtype=np.float64)
            arr = np.asarray(v, dtype=np.float64)
            if arr.shape != (K,):
                raise ValueError(
                    f"RegulatorConfig.{name} must be a scalar or a length-{K} "
                    f"sequence (n_stacks={K}); got shape {arr.shape}."
                )
            return arr

        strength = _arr(reg.regulator_strength, "regulator_strength")
        capture = _arr(reg.regulator_capture, "regulator_capture")
        audit_quality = _arr(reg.regulator_audit_quality, "regulator_audit_quality")
        return strength, capture, audit_quality

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

"""
Configuration dataclasses for the exo-engine.

Every parameter here is named after a concept in Poliks & Trillo's
*Exocapitalism* (2025) or its conversation partners (Bratton, Krier,
Tomašev, Wark). Where parameters look like the α-engine's, they are *not*
the same — they live in a different model of how value moves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, Sequence


@dataclass
class StackConfig:
    """The abstraction stack on which lift operates.

    Layer 0 is the *last mile* (material need-meeting). Each successive layer
    is a step further into abstraction: brokerage of last-mile activity,
    SaaS-on-SaaS, finance, derivative, derivative-of-derivative, all the way
    to the asymptote of pure self-reference.

    `n_layers` is finite for tractability; the conceptual claim is that lift
    is unbounded in the limit.
    """

    n_layers: int = 8
    base_lift_propensity: float = 0.42
    lift_decay_with_depth: float = 0.86
    fractal_branching: float = 2.55
    nominal_multiplier: float = 1.85
    real_leakage_per_layer: float = 0.04
    max_lift_share_per_step: float = 0.55  # fraction of layer-k that can lift in one step
    referent_layer: int = 0


@dataclass
class DragConfig:
    """The drag economy — legibility production.

    Drag agents (states, brokers, white-collar labor) consume real welfare
    to produce *legibility tokens*: contracts, schemata, regulation, audits,
    measurement protocols. Each token opens a surface that capital can lift
    through.

    `target_intensity` is a per-step target. The realized intensity adjusts
    around it based on the policy regime in each region.
    """

    target_intensity: float = 0.32
    intensity_inertia: float = 0.85
    welfare_cost_per_token: float = 0.014
    tokens_to_lift_propensity: float = 1.4
    saturation_floor: float = 0.05
    saturation_ceiling: float = 0.95
    # When `coasean_dampener` > 0, drag produces *suppression* tokens instead of
    # lift surfaces. Modeled after the exo claim that Coasean agents are
    # anxiety dampeners: they consume drag without enabling lift.
    coasean_dampener: float = 0.0

    # Adaptive Coasean dampener: when enabled, the per-polity dampener level
    # rises as last-mile welfare per polity falls below `adaptive_welfare_target`.
    # This models Coasean agents being deployed *as palliative care* — recruited
    # in proportion to visible meatspace suffering, not as coordination.
    adaptive_dampener: bool = False
    adaptive_welfare_target: float = 0.5
    adaptive_dampener_sensitivity: float = 1.4
    adaptive_dampener_max: float = 0.85
    adaptive_dampener_inertia: float = 0.7

    # Calibrated noise structure for the per-region drag-intensity wobble.
    # Default is the legacy IID Gaussian; `t_copula` adds heavy tails and
    # cross-region co-movement (World Bank GDP-growth correlations).
    noise_model: Literal["gaussian", "t_copula"] = "gaussian"
    noise_dof: float = 4.0
    noise_intra_block: float = 0.55
    noise_inter_block: float = 0.30
    noise_n_blocks: int = 2


@dataclass
class LastMileConfig:
    """The last mile — bounded material throughput.

    Real welfare flows from last-mile activity. It is bounded by physical
    resources (energy, water, land, food, sleep, biological capacity) and
    by the labor that actually does it. This module does *not* privilege
    last-mile as more real than the lifted layers; it just notes that
    physical resources are bounded in a way nominal value is not.
    """

    base_physical_capacity: float = 1.0
    capacity_jitter: float = 0.06
    real_per_unit_capacity: float = 1.0
    nominal_per_unit_at_layer0: float = 1.05
    last_mile_labor_share: float = 0.30
    # When `gore_layer_violence` > 0, the last mile experiences a stochastic
    # violence rate that destroys real welfare without producing nominal
    # value (drone strike, mine collapse, hospital denial, climate event).
    gore_layer_violence: float = 0.02


@dataclass
class DifferentialConfig:
    """Endogenous market creation from ontological variance.

    The exo claim: new markets emerge wherever ontological difference exists
    and is not actively suppressed. Suppression is not free; it requires
    political infrastructure that itself consumes real welfare.

    `suppression_strength` ∈ [0, 1]:
        0   = laissez-faire, every difference becomes a market (Fold)
        0.5 = ordinary regulatory regime
        1   = "Combine state" — universal differential suppression

    `suppression_cost_exp` controls how expensive it gets to push toward 1.
    """

    base_market_creation_rate: float = 0.18
    variance_to_market_rate: float = 0.55
    suppression_strength: float = 0.30
    suppression_cost_exp: float = 2.0
    suppression_welfare_cost: float = 0.045
    market_saturation_layers: float = 12.0
    spawn_layer_jitter: int = 1
    # When > 0, a fraction of newly-spawned markets immediately lift one or
    # more layers (the Web3 / SaaS-on-SaaS pattern: born already abstracted).
    born_lifted_share: float = 0.25


@dataclass
class RegionConfig:
    """Per-region heterogeneity.

    Regions differ in ontological variance, drag intensity, suppression
    posture, last-mile binding, and inter-region trade frictions. The
    Hemispherical Stacks fall out of this naturally as low cross-region
    drag-token compatibility.
    """

    n_regions: int = 12
    n_prototypes_per_region: int = 600
    cross_region_compat: float = 0.55
    inter_region_lift_friction: float = 0.10
    region_size_dirichlet: float = 1.7
    seed: int = 9012


@dataclass
class ImperialConfig:
    """Imperial tracts — the third topology layer.

    Tracts are *non-coextensive* with polities. They model geological /
    resource attractors that consolidate over millennia (Bratton's
    historical maps; Trillo's empire-as-attractor). Many polities map to
    one tract; capital and violence pool by tract independently of
    polity-level governance choices.

    Setting `enabled=False` falls back to a polity-only world (the original
    exo-engine behaviour); the world step then short-circuits all imperial
    operations.
    """

    enabled: bool = True
    n_tracts: int = 4
    tract_resource_dirichlet: float = 1.4
    tract_attractor_dirichlet: float = 1.2
    extraction_rate: float = 0.10
    historical_violence_floor: float = 0.020
    capital_pooling_strength: float = 0.22
    pool_layers: int = 3
    extraction_destination_layer: int = 4
    seed: int = 7777
    # Optional schedule on extraction intensity multiplier (length n_steps).
    extraction_intensity_schedule: Optional[Sequence[float]] = None
    # Optional schedule on attractor strengths: list of length n_steps,
    # each element either None (no change) or array of length n_tracts.
    attractor_schedule: Optional[Sequence[Optional[Sequence[float]]]] = None


@dataclass
class ExoWorldConfig:
    """Top-level config for an exo-engine run.

    Schedules let any of the four operator intensities vary over time, which
    matters for testing path dependence: the exo position is that initial
    protocol-design choices lock the system into a basin even when the
    same final-step parameters could permit other regimes.
    """

    stack: StackConfig = field(default_factory=StackConfig)
    drag: DragConfig = field(default_factory=DragConfig)
    last_mile: LastMileConfig = field(default_factory=LastMileConfig)
    differential: DifferentialConfig = field(default_factory=DifferentialConfig)
    region: RegionConfig = field(default_factory=RegionConfig)
    imperial: ImperialConfig = field(default_factory=ImperialConfig)

    n_steps: int = 80
    seed: int = 0

    # Optional schedules; when non-None must have length == n_steps.
    drag_intensity_schedule: Optional[Sequence[float]] = None
    suppression_strength_schedule: Optional[Sequence[float]] = None
    physical_capacity_schedule: Optional[Sequence[float]] = None
    coasean_dampener_schedule: Optional[Sequence[float]] = None

    # Number of independent realisations to run when collecting noise envelopes.
    # 1 is the default for fast iteration; bump up for variance-aware figures.
    n_realisations: int = 1

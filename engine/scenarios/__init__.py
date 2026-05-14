"""
Scenarios — parameterizations of the smooth-striated continuum.

Each scenario returns a fully-formed `WorldConfig`. All are inspired by a
specific position in the conceptual brief; cite the brief when adding new ones.

Usage:
    from engine.scenarios import SCENARIOS, get_scenario
    cfg = get_scenario("coasean_paradise")
    world = World.build(cfg)
    world.run(progress=True)

Original 15 (alpha-engine, no demand feedback, no productive folding split):
    1.  coasean_paradise      — Smoothworld limit (Krier)
    2.  baroque_cathedral     — Baroqueworld limit (Bratton)
    3.  equilibrium_drift     — Mid-alpha steady state
    4.  smoothing_cascade     — Alpha decays from 1.0 → 0.0 over time
    5.  fold_avalanche        — Alpha ramps from 0.0 → 1.0 over time
    6.  hemispherical_schism  — Multipolar stack fragmentation
    7.  compute_famine        — Rising friction floor (compute scarcity)
    8.  universal_advocate    — Capability uplift everywhere; smooth tilt
    9.  synthetic_consumers   — Agent autonomy maxed; A2A dominance
    10. nimby_cascade         — Alignment-layer rejection runs hot
    11. slop_market           — High alpha + low capability: folding without quality
    12. public_defender       — Compressed capability variance via subsidy
    13. matryoshka_collapse   — Market+individual layers gate-keep heavily
    14. recursive_simulation  — Alpha drives itself based on EBI feedback
    15. exo_baroque_singularity — Aggressive recursive fold limits

Networked variants (16-17):
    16. coasean_paradise_networked  — Smooth limit on scale-free network
    17. baroque_cathedral_networked — Baroque limit on degree-corrected SBM

Demand-and-intermediation scenarios (18-22, see docs/concepts/demand_and_intermediation.md):
    18. synthetic_consumers_v2  — Synthetic consumers with demand-side feedback ON
    19. agentic_disconnect      — Humans abdicate, agents act; demand feedback exposes the gap
    20. productive_baroque      — High alpha + capable intermediaries; productive folding ON
    21. derivatives_revolution  — Aggressive productive folding; bounded-welfare check
    22. casino_collapse         — High alpha + low cap; productivity gated by capability

Dynamic-law scenarios (23-25, see brief/dynamic_mechanisms.md):
    23. legal_collapse       — law strength decays without upkeep
    24. regulatory_capture   — concentrated wealth captures the legal layer
    25. civic_renaissance    — upkeep + civic pushback restore legal capacity

Pigouvian automation-tax scenarios (26-29, see docs/concepts/pigouvian_automation.md):
    26. pigouvian_light      — moderate A2A tax, revenue to human wealth
    27. pigouvian_heavy      — high A2A tax; tests over-correction dynamics
    28. pigouvian_friction    — tax recycled as H2A friction subsidy
    29. pigouvian_baroque     — Pigouvian tax on productive-baroque baseline

Emergence scenarios (30-33):
    30. endogenous_paradise        — agents learn alpha on a smooth-friendly surface
    31. endogenous_baroque         — agents learn alpha under a high folding ceiling
    32. institutional_emergence    — strategy plus firm formation
    33. full_emergence             — strategy, firms, and population dynamics
"""

from __future__ import annotations

from typing import Callable, Dict

import numpy as np

from engine.core.population import PopulationConfig
from engine.core.topology import (
    ComputeConfig,
    DemandConfig,
    InstitutionConfig,
    LawConfig,
    MissionConfig,
    NormsConfig,
    PigouvianConfig,
    PopulationDynamicsConfig,
    RegistrationConfig,
    RegulatorConfig,
    StrategyConfig,
    TopologyConfig,
)
from engine.core.world import WorldConfig


# ---------- 1. Coasean Paradise ------------------------------------------------


def coasean_paradise() -> WorldConfig:
    """
    The Krier limit: agents drive transaction costs to near-zero; very little
    folding; nominal GDP ≈ real welfare. The state shrinks to framework
    guarantor; markets are continuous bilateral negotiations.

    What to look for: low Gini? high per-capita welfare? EBI ≈ 1.
    """
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.85, agent_capability_sd=0.12,
            human_capability_mean=0.65, human_capability_sd=0.15,
            n_human_prototypes=6_000, n_agent_prototypes=60_000,
            seed=11,
        ),
        topology=TopologyConfig(
            alpha=0.08,
            base_friction=0.025,
            coase_exp=2.1,
            folding_propensity=0.10,
            market_layer_tax=0.010,
            individual_layer_alignment_tax=0.008,
            cross_stack_compat=0.85,
        ),
        pairs_per_step=200_000,
        n_steps=200,
        seed=1,
    )


# ---------- 2. Baroque Cathedral ----------------------------------------------


def baroque_cathedral() -> WorldConfig:
    """
    The Bratton limit: folding everywhere. Each transaction begets sub-
    transactions begets sub-sub-transactions. Nominal GDP explodes; real
    welfare grows modestly. EBI → high.

    What to look for: nominal/real divergence; max fold depth; legibility crash.
    """
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.78, agent_capability_sd=0.16,
            n_human_prototypes=6_000, n_agent_prototypes=60_000,
            seed=22,
        ),
        topology=TopologyConfig(
            alpha=0.92,
            base_friction=0.06,
            folding_propensity=0.65,
            folding_branching=3.2,
            folding_max_depth=7,
            fold_nominal_multiplier=2.0,
            fold_real_efficiency=0.91,
            market_layer_tax=0.04,
            individual_layer_alignment_tax=0.025,
            cross_stack_compat=0.45,
        ),
        n_steps=200,
        seed=2,
    )


# ---------- 3. Equilibrium Drift ----------------------------------------------


def equilibrium_drift() -> WorldConfig:
    """
    alpha=0.5 — the precarious midpoint. Both attractors pull; the system can
    drift to either depending on initial conditions and noise.

    What to look for: instability; sensitivity to seed; basin-of-attraction shape.
    """
    return WorldConfig(
        population=PopulationConfig(seed=33),
        topology=TopologyConfig(alpha=0.5),
        n_steps=80,
        seed=3,
    )


# ---------- 4. Smoothing Cascade ----------------------------------------------


def smoothing_cascade() -> WorldConfig:
    """
    The Coasean transition: alpha drops from 1.0 to 0.0 over time, simulating
    a society that *successfully* uses agents to dissolve intermediation.

    What to look for: nominal GDP collapse, real welfare growth, rising
    legibility, possibly a Gini drop.
    """
    n_steps = 200
    schedule = np.linspace(0.95, 0.05, n_steps).tolist()
    return WorldConfig(
        population=PopulationConfig(seed=44),
        topology=TopologyConfig(alpha=0.95),
        alpha_schedule=schedule,
        n_steps=n_steps,
        seed=4,
    )


# ---------- 5. Fold Avalanche -------------------------------------------------


def fold_avalanche() -> WorldConfig:
    """
    alpha climbs from 0.0 to 1.0 over time. Models a society that progressively
    institutionalizes agent-mediated intermediation — a Baroque drift.

    What to look for: nominal GDP take-off; the inflection point where folding
    starts overwhelming direct exchange; legibility crash.
    """
    n_steps = 200
    schedule = np.linspace(0.05, 0.95, n_steps).tolist()
    return WorldConfig(
        population=PopulationConfig(seed=55),
        topology=TopologyConfig(alpha=0.05),
        alpha_schedule=schedule,
        n_steps=n_steps,
        seed=5,
    )


# ---------- 6. Hemispherical Schism -------------------------------------------


def hemispherical_schism() -> WorldConfig:
    """
    Bratton's Hemispherical Stacks: cross-stack compatibility collapses. Each
    stack runs its own protocols, units, and alignment regimes. Friction is
    high across boundaries.

    What to look for: per-stack inequality; inter-stack trade volume drop;
    bifurcation of agent populations.
    """
    return WorldConfig(
        population=PopulationConfig(
            stack_shares=(0.30, 0.30, 0.20, 0.20),
            seed=66,
        ),
        topology=TopologyConfig(
            alpha=0.55,
            cross_stack_compat=0.18,  # very low cross-stack compatibility
            n_stacks=4,
        ),
        n_steps=200,
        seed=6,
    )


# ---------- 7. Compute Famine -------------------------------------------------


def compute_famine() -> WorldConfig:
    """
    A scenario where compute becomes scarce mid-run. Friction floor rises
    dramatically over time. Models a chip war, energy crisis, or regulatory
    throttle on inference.

    What to look for: collapse of low-margin transactions; widening gap
    between high-cap and low-cap participants.
    """
    n_steps = 200
    # Three equal-length phases: early plateau, ramp, late plateau.
    floor_schedule = list(
        np.concatenate([
            np.full(67, 1e-4),
            np.linspace(1e-4, 5e-2, 67),
            np.full(66, 5e-2),
        ])
    )
    return WorldConfig(
        population=PopulationConfig(seed=77),
        topology=TopologyConfig(alpha=0.4),
        friction_floor_schedule=floor_schedule,
        n_steps=n_steps,
        seed=7,
    )


# ---------- 8. Universal Advocate ---------------------------------------------


def universal_advocate() -> WorldConfig:
    """
    Krier's vision: every entity has a high-capability advocate agent. Capability
    variance compresses upward. Smooth-tilted regime.

    What to look for: Gini compression; rejected-by-cost falls to ~0; per-capita
    welfare jumps; alignment-layer rejections become the dominant filter.
    """
    return WorldConfig(
        population=PopulationConfig(
            human_capability_mean=0.78, human_capability_sd=0.06,
            agent_capability_mean=0.90, agent_capability_sd=0.05,
            seed=88,
        ),
        topology=TopologyConfig(
            alpha=0.20,
            base_friction=0.020,
            individual_layer_alignment_tax=0.020,
        ),
        n_steps=200,
        seed=8,
    )


# ---------- 9. Synthetic Consumers --------------------------------------------


def synthetic_consumers() -> WorldConfig:
    """
    Agents not only act for humans — they *consume* on their own behalf. Agent
    autonomy is maxed; A2A interactions dominate. Humans are 8B in a society
    where the 8 × 10^11 agents are doing most of the talking, trading, and
    valuing.

    What to look for: A2A share > 0.99; human-legibility plummets; nominal/real
    divergence even at moderate alpha.
    """
    return WorldConfig(
        population=PopulationConfig(
            human_autonomy_mean=0.30,  # humans delegate heavily
            agent_autonomy_mean=0.97,  # agents act with ~full autonomy
            n_agent_prototypes=120_000,
            seed=99,
        ),
        topology=TopologyConfig(alpha=0.6, folding_propensity=0.45),
        pairs_per_step=300_000,
        n_steps=200,
        seed=9,
    )


# ---------- 10. NIMBY Cascade -------------------------------------------------


def nimby_cascade() -> WorldConfig:
    """
    Alignment-layer rejection runs hot — every individual agent's preferences
    are sticky and exclusive. The promise of Coasean clearance is undone by
    agent-mediated NIMBYism at unprecedented scale.

    What to look for: rejected_align dominates; real welfare growth flatlines;
    EBI rises slightly because folded sub-markets *do* clear (they're internal
    to existing relationships).
    """
    return WorldConfig(
        population=PopulationConfig(seed=100),
        topology=TopologyConfig(
            alpha=0.4,
            individual_layer_alignment_tax=0.06,
            market_layer_tax=0.05,
        ),
        n_steps=200,
        seed=10,
    )


# ---------- 11. Slop Market ---------------------------------------------------


def slop_market() -> WorldConfig:
    """
    High alpha + LOW capability — folding happens recursively but the underlying
    economic activity is low-quality. Pure nominal-GDP inflation; real welfare
    barely grows. The agent stack is busy without being useful.

    What to look for: EBI explodes; per-capita welfare is anemic; the deepest
    fold layers eat all the real surplus.
    """
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.40, agent_capability_sd=0.20,
            human_capability_mean=0.30, human_capability_sd=0.18,
            seed=110,
        ),
        topology=TopologyConfig(
            alpha=0.85,
            folding_propensity=0.6,
            folding_branching=2.8,
            fold_nominal_multiplier=2.2,
            fold_real_efficiency=0.85,
        ),
        n_steps=200,
        seed=11,
    )


# ---------- 12. Public Defender -----------------------------------------------


def public_defender() -> WorldConfig:
    """
    Krier's "agent voucher" intervention: capability variance is compressed
    upward by subsidy. Equity-by-design.

    What to look for: Gini drops despite total surplus only modestly higher;
    rejected-by-cost ≈ 0; H2A interactions rise.
    """
    return WorldConfig(
        population=PopulationConfig(
            human_capability_mean=0.65, human_capability_sd=0.04,
            agent_capability_mean=0.80, agent_capability_sd=0.06,
            initial_wealth_human_mean=80.0,
            initial_wealth_agent_mean=4.0,
            seed=120,
        ),
        topology=TopologyConfig(
            alpha=0.30,
            base_friction=0.025,
            market_layer_tax=0.015,
        ),
        n_steps=200,
        seed=12,
    )


# ---------- 13. Matryoshka Collapse -------------------------------------------


def matryoshka_collapse() -> WorldConfig:
    """
    Both market and individual alignment layers reject heavily. The Matryoshka
    governance stack overcomstrains; only law-layer-permitted transactions
    proceed. Most surplus opportunities die in the gates.

    What to look for: governance overhead > 0.4; nominal volume crashes;
    rejected_market and rejected_align dominate.
    """
    return WorldConfig(
        population=PopulationConfig(seed=130),
        topology=TopologyConfig(
            alpha=0.45,
            market_layer_tax=0.10,
            individual_layer_alignment_tax=0.07,
        ),
        n_steps=200,
        seed=13,
    )


# ---------- 14. Recursive Simulation ------------------------------------------


def recursive_simulation() -> WorldConfig:
    """
    The Antikythera move: the simulation affects what it simulates. Here we
    let alpha *respond* to the EBI in earlier steps — a feedback loop where
    the measurement of "how baroque is this economy?" itself drives further
    folding (or smoothing) decisions.

    Implemented as a precomputed schedule that simulates one round of feedback:
    starts smooth, but as folding takes off, alpha increases (positive
    feedback).

    What to look for: nonlinear take-off; small initial differences amplify.
    """
    n_steps = 200
    # Sigmoid drive: alpha rises as a function of step^1.3 / total_steps^1.3.
    t = np.arange(n_steps) / (n_steps - 1)
    schedule = (0.15 + 0.75 / (1.0 + np.exp(-(t * 8 - 4)))).tolist()
    return WorldConfig(
        population=PopulationConfig(seed=140),
        topology=TopologyConfig(alpha=0.15),
        alpha_schedule=schedule,
        n_steps=n_steps,
        seed=14,
    )


# ---------- 15. Exo-Baroque Singularity ---------------------------------------


def exo_baroque_singularity() -> WorldConfig:
    """
    Folding limits unlocked: deep recursion, high branching. Pushes the model
    toward its analytical limit and tests whether the metrics behave sensibly
    at the asymptote.

    What to look for: EBI well above 100; fold_max_depth at ceiling; nominal
    GDP per real human in the millions.
    """
    return WorldConfig(
        population=PopulationConfig(seed=150),
        topology=TopologyConfig(
            alpha=0.97,
            folding_propensity=0.78,
            folding_branching=5.0,
            folding_max_depth=10,
            fold_nominal_multiplier=2.4,
            fold_real_efficiency=0.93,
        ),
        n_steps=200,
        seed=15,
    )


# ---------- 16. Coasean Paradise (Networked) ---------------------------------


def coasean_paradise_networked() -> WorldConfig:
    """
    Coasean Paradise re-run on a scale-free B2B-style production network
    (degree exponent ~ 2.3, after Atalay et al. 2011) with t-copula-coupled
    sectoral noise (BEA 2022 IO) and Hawkes folding cascades.

    What this scenario tests: does the smooth attractor still hold once the
    well-mixed assumption is dropped? Network structure introduces hub
    prototypes that can dominate downstream surplus capture; t-copula
    noise injects realistic heavy tails; Hawkes folding adds cascade
    variance. If EBI stays near 1 and welfare stays high under all three
    upgrades simultaneously, the Coasean attractor is robust.
    """
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.85, agent_capability_sd=0.12,
            human_capability_mean=0.65, human_capability_sd=0.15,
            n_human_prototypes=4_000, n_agent_prototypes=40_000,
            seed=160,
            network_model="scale_free",
            network_mean_degree=12,
            network_p_local=0.85,
        ),
        topology=TopologyConfig(
            alpha=0.08,
            base_friction=0.025,
            coase_exp=2.1,
            folding_propensity=0.10,
            market_layer_tax=0.010,
            individual_layer_alignment_tax=0.008,
            cross_stack_compat=0.85,
            noise_model="t_copula",
            folding_model="hawkes",
            demand=DemandConfig(enabled=True, a2a_floor=0.20),
            base_variance_absorption=0.20,
            productive_decay=0.70,
        ),
        pairs_per_step=200_000,
        n_steps=200,
        seed=16,
    )


# ---------- 17. Baroque Cathedral (Networked) --------------------------------


def baroque_cathedral_networked() -> WorldConfig:
    """
    Baroque Cathedral re-run on a degree-corrected SBM (sector blocks with
    intra-sector clustering, after Atalay et al. 2011) with t-copula
    sectoral noise and Hawkes folding cascades.

    What this scenario tests: does folding go even more baroque when sector
    co-movement and cascade clustering are realistic? The hypothesis is
    that the Hawkes self-excitation creates fatter EBI tails — occasional
    steps where folding takes off well above the geometric expectation.
    Compare terminal EBI bands to `baroque_cathedral`'s (well-mixed,
    geometric, Gaussian) ensemble.
    """
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.78, agent_capability_sd=0.16,
            n_human_prototypes=4_000, n_agent_prototypes=40_000,
            seed=170,
            network_model="sbm",
            network_mean_degree=14,
            network_intra_sector_share=0.75,
            network_p_local=0.85,
        ),
        topology=TopologyConfig(
            alpha=0.92,
            base_friction=0.06,
            folding_propensity=0.65,
            folding_branching=3.2,
            folding_max_depth=7,
            fold_nominal_multiplier=2.0,
            fold_real_efficiency=0.91,
            market_layer_tax=0.04,
            individual_layer_alignment_tax=0.025,
            cross_stack_compat=0.45,
            noise_model="t_copula",
            folding_model="hawkes",
            demand=DemandConfig(enabled=True, a2a_floor=0.15),
            base_variance_absorption=0.35,
            productive_decay=0.65,
        ),
        n_steps=200,
        seed=17,
    )


# ---------- 18. Synthetic Consumers v2 (demand-feedback ON) ------------------


def synthetic_consumers_v2() -> WorldConfig:
    """
    `synthetic_consumers` re-run with demand-side feedback turned on.

    This is a controlled twin of `synthetic_consumers`: same population
    parameters, same population seed, same world seed, and only
    `DemandConfig.enabled` changes. Compare `real_welfare_cumulative`
    (un-modulated) to `real_welfare_authentic_cumulative`: the gap is
    the demand-side-feedback effect.

    What to look for: authentic per-capita welfare collapses relative to
    the un-modulated version; `exo_baroque_authentic` is much higher
    than the legacy `exo_baroque_index`. This is the empirical signature
    the plan calls G3.
    """
    return WorldConfig(
        population=PopulationConfig(
            human_autonomy_mean=0.30,
            agent_autonomy_mean=0.97,
            n_agent_prototypes=120_000,
            seed=99,
        ),
        topology=TopologyConfig(
            alpha=0.6,
            folding_propensity=0.45,
            demand=DemandConfig(enabled=True, a2a_floor=0.15),
        ),
        pairs_per_step=300_000,
        n_steps=200,
        seed=9,
    )


# ---------- 19. Agentic Disconnect (demand-feedback ON) -----------------------


def agentic_disconnect() -> WorldConfig:
    """
    Humans have abdicated decision-making but agents are capability-strong.

    High `agent_autonomy_mean = 0.95`, low `human_autonomy_mean = 0.20`
    (humans delegate almost everything), mid alpha. Tests the case where
    the population has high effective agent autonomy and modest folding,
    with demand-side feedback on. The model says: even at moderate
    intermediation, real welfare collapses if the human side has stepped
    out of the consumption loop.
    """
    return WorldConfig(
        population=PopulationConfig(
            human_autonomy_mean=0.20,
            agent_autonomy_mean=0.95,
            n_agent_prototypes=80_000,
            seed=1180,
        ),
        topology=TopologyConfig(
            alpha=0.5,
            demand=DemandConfig(enabled=True, a2a_floor=0.15),
        ),
        n_steps=200,
        seed=18,
    )


# ---------- 20. Productive Baroque -------------------------------------------


def productive_baroque() -> WorldConfig:
    """
    Baroque-ish alpha but capable intermediaries and productive folding on.

    The plan's claim (c): high intermediation does not always corrupt
    welfare. With high agent capability and `base_variance_absorption =
    0.45`, the fold cascade is welfare-creating at shallow depth — risk
    transfer / capital efficiency / price discovery doing real work.
    Demand-side feedback is also on so the welfare is judged against the
    human-consumed share, not nominal volume.

    Acceptance (G2): terminal real per-capita welfare near but below
    `coasean_paradise`'s, and terminal EBI in [8, 50].
    """
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.85, agent_capability_sd=0.10,
            human_capability_mean=0.65, human_capability_sd=0.12,
            n_human_prototypes=6_000, n_agent_prototypes=60_000,
            seed=1190,
        ),
        topology=TopologyConfig(
            alpha=0.85,
            base_friction=0.045,
            folding_propensity=0.45,
            folding_branching=2.6,
            folding_max_depth=6,
            fold_nominal_multiplier=1.7,
            fold_real_efficiency=0.92,
            market_layer_tax=0.025,
            individual_layer_alignment_tax=0.020,
            cross_stack_compat=0.65,
            base_variance_absorption=0.45,
            productive_decay=0.65,
            cap_midpoint=0.50,
            cap_slope=4.0,
            max_productive_real_share=0.30,
            demand=DemandConfig(enabled=True, a2a_floor=0.15),
        ),
        pairs_per_step=200_000,
        n_steps=200,
        seed=19,
    )


# ---------- 21. Derivatives Revolution ---------------------------------------


def derivatives_revolution() -> WorldConfig:
    """
    Aggressively encourage productive folding; mid-alpha; low Matryoshka taxes.

    Sanity-check scenario for the productive folding split: tests that
    even with `base_variance_absorption = 0.40` and `productive_decay
    = 0.75`, the model does not produce free welfare ad infinitum. Low
    taxes alone land only modestly above `coasean_paradise`; the generous
    productive split is what lifts terminal real per-capita welfare to the
    high end of the limit-test band, around 0.09 stylized units
    (roughly 1.7× `coasean_paradise` at the default seed).
    """
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.80, agent_capability_sd=0.10,
            human_capability_mean=0.60, human_capability_sd=0.12,
            n_human_prototypes=5_000, n_agent_prototypes=50_000,
            seed=1200,
        ),
        topology=TopologyConfig(
            alpha=0.55,
            base_friction=0.035,
            folding_propensity=0.45,
            folding_branching=2.5,
            folding_max_depth=6,
            fold_nominal_multiplier=1.8,
            fold_real_efficiency=0.93,
            market_layer_tax=0.008,
            individual_layer_alignment_tax=0.006,
            base_variance_absorption=0.40,
            productive_decay=0.75,
            cap_midpoint=0.50,
            cap_slope=4.0,
            demand=DemandConfig(enabled=True, a2a_floor=0.20),
        ),
        n_steps=200,
        seed=20,
    )


# ---------- 22. Casino Collapse ----------------------------------------------


def casino_collapse() -> WorldConfig:
    """
    High alpha + low capability + opt-in productive folding.

    The split says "productive folding requires capable intermediaries";
    this scenario verifies that low-capability folding is parasitic
    regardless of opt-in. With `agent_capability_mean = 0.40` and
    `cap_midpoint = 0.50`, the productive-share sigmoid stays well
    below 0.5 at every depth, and the productive contribution is small
    relative to the (still-large) parasitic nominal multiplication.
    """
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.40, agent_capability_sd=0.18,
            human_capability_mean=0.30, human_capability_sd=0.18,
            n_human_prototypes=5_000, n_agent_prototypes=50_000,
            seed=1210,
        ),
        topology=TopologyConfig(
            alpha=0.85,
            folding_propensity=0.6,
            folding_branching=2.8,
            fold_nominal_multiplier=2.2,
            fold_real_efficiency=0.85,
            base_variance_absorption=0.40,
            productive_decay=0.65,
            cap_midpoint=0.50,
            cap_slope=4.0,
        ),
        n_steps=200,
        seed=22,
    )


# ---------- 23. Legal Collapse -------------------------------------------------


def legal_collapse() -> WorldConfig:
    """
    Law as substrate, allowed to decay. With no upkeep investment, legal
    strength falls from a functional starting point toward the low-trust
    regime over the default horizon.
    """
    return WorldConfig(
        population=PopulationConfig(seed=1230),
        topology=TopologyConfig(
            alpha=0.45,
            law=LawConfig(
                enabled=True,
                law_strength_initial=0.85,
                upkeep_investment=0.0,
                natural_decay=0.011,
                civic_pushback_default=0.10,
            ),
        ),
        n_steps=200,
        seed=23,
    )


# ---------- 24. Regulatory Capture --------------------------------------------


def regulatory_capture() -> WorldConfig:
    """
    High initial wealth concentration and zero civic pushback let legal
    capture compound, turning cross-stack and newcomer trade into low-surplus
    cost rejections.
    """
    return WorldConfig(
        population=PopulationConfig(
            wealth_pareto_alpha=1.15,
            initial_wealth_agent_mean=8.0,
            seed=1240,
        ),
        topology=TopologyConfig(
            alpha=0.55,
            cross_stack_compat=0.40,
            law=LawConfig(
                enabled=True,
                law_strength_initial=0.90,
                law_capture_initial=0.20,
                upkeep_investment=0.08,
                beta_capture_growth=0.03,
                civic_pushback_default=0.0,
            ),
        ),
        n_steps=200,
        seed=24,
    )


# ---------- 25. Civic Renaissance ---------------------------------------------


def civic_renaissance() -> WorldConfig:
    """
    Concentrated initial wealth meets high legal upkeep and high civic
    pushback. Tests whether the Coasean substrate can be maintained as an
    active political achievement rather than a free background condition.
    """
    return WorldConfig(
        population=PopulationConfig(
            wealth_pareto_alpha=1.20,
            agent_capability_mean=0.82,
            human_capability_mean=0.62,
            seed=1250,
        ),
        topology=TopologyConfig(
            alpha=0.30,
            cross_stack_compat=0.75,
            law=LawConfig(
                enabled=True,
                law_strength_initial=0.70,
                upkeep_investment=0.16,
                natural_decay=0.006,
                law_capture_initial=0.20,
                civic_pushback_default=0.75,
            ),
        ),
        n_steps=200,
        seed=25,
    )


# ---------- 26. Pigouvian Light -----------------------------------------------


def pigouvian_light() -> WorldConfig:
    """
    Moderate Pigouvian automation tax (10%) on A2A surplus, recycled
    progressively to human wealth. Demand-side feedback is on so we can
    compare authentic welfare with and without the tax against
    `synthetic_consumers_v2` (the un-taxed twin).

    What to look for: authentic per-capita welfare rises relative to
    synthetic_consumers_v2; nominal GDP drops moderately; Gini
    compresses via the progressive wealth transfer.
    """
    return WorldConfig(
        population=PopulationConfig(
            human_autonomy_mean=0.30,
            agent_autonomy_mean=0.97,
            n_agent_prototypes=120_000,
            seed=99,
        ),
        topology=TopologyConfig(
            alpha=0.6,
            folding_propensity=0.45,
            demand=DemandConfig(enabled=True, a2a_floor=0.15),
            pigouvian=PigouvianConfig(
                enabled=True,
                tax_rate=0.10,
                a2a_floor=0.15,
                recycling="human_wealth",
                recycling_progressivity=1.0,
            ),
        ),
        pairs_per_step=300_000,
        n_steps=200,
        seed=9,
    )


# ---------- 27. Pigouvian Heavy -----------------------------------------------


def pigouvian_heavy() -> WorldConfig:
    """
    High Pigouvian automation tax (35%) on A2A surplus. Tests whether
    aggressive taxation of non-human-coupled activity over-corrects:
    does per-capita welfare overshoot or undershoot the Coasean baseline?
    Does A2A volume collapse entirely?

    What to look for: A2A surplus drops sharply; nominal GDP collapses;
    compare terminal per-capita welfare to coasean_paradise — if it
    exceeds it, the tax has successfully redirected surplus to humans.
    """
    return WorldConfig(
        population=PopulationConfig(
            human_autonomy_mean=0.30,
            agent_autonomy_mean=0.97,
            n_agent_prototypes=120_000,
            seed=99,
        ),
        topology=TopologyConfig(
            alpha=0.6,
            folding_propensity=0.45,
            demand=DemandConfig(enabled=True, a2a_floor=0.15),
            pigouvian=PigouvianConfig(
                enabled=True,
                tax_rate=0.35,
                a2a_floor=0.15,
                recycling="human_wealth",
                recycling_progressivity=1.5,
            ),
        ),
        pairs_per_step=300_000,
        n_steps=200,
        seed=9,
    )


# ---------- 28. Pigouvian Friction --------------------------------------------


def pigouvian_friction() -> WorldConfig:
    """
    Pigouvian tax recycled as a friction subsidy for human-involving
    transactions. Instead of direct wealth transfer, the revenue reduces
    the effective transaction cost for H2A pairs in subsequent steps,
    making it cheaper for humans to participate in the economy.

    What to look for: H2A interaction share rises relative to
    synthetic_consumers_v2; humans re-enter the consumption loop;
    authentic welfare improves through structural participation rather
    than direct transfer.
    """
    return WorldConfig(
        population=PopulationConfig(
            human_autonomy_mean=0.30,
            agent_autonomy_mean=0.97,
            n_agent_prototypes=120_000,
            seed=99,
        ),
        topology=TopologyConfig(
            alpha=0.6,
            folding_propensity=0.45,
            demand=DemandConfig(enabled=True, a2a_floor=0.15),
            pigouvian=PigouvianConfig(
                enabled=True,
                tax_rate=0.15,
                a2a_floor=0.15,
                recycling="friction_subsidy",
            ),
        ),
        pairs_per_step=300_000,
        n_steps=200,
        seed=9,
    )


# ---------- 29. Pigouvian Baroque ---------------------------------------------


def pigouvian_baroque() -> WorldConfig:
    """
    Pigouvian tax layered on top of the productive-baroque baseline.
    Tests whether taxing A2A surplus suppresses the productive folding
    channel (risk transfer, price discovery) or only the parasitic one.

    What to look for: compare `productive_welfare_yield` and
    `real_welfare_from_intermediation_cumulative` to `productive_baroque`
    — if the productive share is preserved while parasitic nominal
    multiplication drops, the Pigouvian tax is well-targeted. If
    productive folding also collapses, the tax is too blunt.
    """
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.85, agent_capability_sd=0.10,
            human_capability_mean=0.65, human_capability_sd=0.12,
            n_human_prototypes=6_000, n_agent_prototypes=60_000,
            seed=1190,
        ),
        topology=TopologyConfig(
            alpha=0.85,
            base_friction=0.045,
            folding_propensity=0.45,
            folding_branching=2.6,
            folding_max_depth=6,
            fold_nominal_multiplier=1.7,
            fold_real_efficiency=0.92,
            market_layer_tax=0.025,
            individual_layer_alignment_tax=0.020,
            cross_stack_compat=0.65,
            base_variance_absorption=0.45,
            productive_decay=0.65,
            cap_midpoint=0.50,
            cap_slope=4.0,
            max_productive_real_share=0.30,
            demand=DemandConfig(enabled=True, a2a_floor=0.15),
            pigouvian=PigouvianConfig(
                enabled=True,
                tax_rate=0.12,
                a2a_floor=0.15,
                recycling="human_wealth",
                recycling_progressivity=1.0,
            ),
        ),
        pairs_per_step=200_000,
        n_steps=200,
        seed=19,
    )


# ---------- 30. Endogenous Paradise -------------------------------------------


def endogenous_paradise() -> WorldConfig:
    """Agents start undecided and discover whether smoothing is profitable."""
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.85,
            agent_capability_sd=0.12,
            human_capability_mean=0.65,
            human_capability_sd=0.15,
            n_human_prototypes=6_000,
            n_agent_prototypes=60_000,
            seed=3010,
        ),
        topology=TopologyConfig(
            alpha=0.5,
            base_friction=0.025,
            coase_exp=2.1,
            folding_propensity=0.10,
            market_layer_tax=0.010,
            individual_layer_alignment_tax=0.008,
            cross_stack_compat=0.85,
            strategy=StrategyConfig(enabled=True, initial_pref=0.5),
        ),
        pairs_per_step=200_000,
        n_steps=200,
        seed=30,
    )


# ---------- 31. Endogenous Baroque --------------------------------------------


def endogenous_baroque() -> WorldConfig:
    """High folding ceiling and low friction: can baroque emerge endogenously?"""
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.78,
            agent_capability_sd=0.16,
            n_human_prototypes=6_000,
            n_agent_prototypes=60_000,
            seed=3110,
        ),
        topology=TopologyConfig(
            alpha=0.5,
            base_friction=0.035,
            folding_propensity=0.65,
            folding_branching=3.2,
            folding_max_depth=7,
            fold_nominal_multiplier=2.0,
            fold_real_efficiency=0.91,
            market_layer_tax=0.025,
            individual_layer_alignment_tax=0.018,
            cross_stack_compat=0.65,
            strategy=StrategyConfig(enabled=True, initial_pref=0.5),
        ),
        n_steps=200,
        seed=31,
    )


# ---------- 32. Institutional Emergence ---------------------------------------


def institutional_emergence() -> WorldConfig:
    """Strategy plus firms: tests whether coordination institutions form."""
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.80,
            agent_capability_sd=0.14,
            human_capability_mean=0.60,
            human_capability_sd=0.14,
            n_human_prototypes=6_000,
            n_agent_prototypes=60_000,
            seed=3210,
        ),
        topology=TopologyConfig(
            alpha=0.5,
            folding_propensity=0.35,
            cross_stack_compat=0.70,
            strategy=StrategyConfig(enabled=True, initial_pref=0.5),
            institutions=InstitutionConfig(
                enabled=True,
                formation_surplus_threshold=0.0001,
                formation_check_every_k=2,
                merge_probability=0.02,
            ),
        ),
        n_steps=200,
        seed=32,
    )


# ---------- 33. Full Emergence -------------------------------------------------


def full_emergence() -> WorldConfig:
    """Strategy, firms, and population churn enabled together."""
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.78,
            agent_capability_sd=0.16,
            human_capability_mean=0.58,
            human_capability_sd=0.16,
            n_human_prototypes=6_000,
            n_agent_prototypes=60_000,
            seed=3310,
        ),
        topology=TopologyConfig(
            alpha=0.5,
            folding_propensity=0.45,
            folding_branching=2.8,
            cross_stack_compat=0.65,
            strategy=StrategyConfig(enabled=True, initial_pref=0.5),
            institutions=InstitutionConfig(
                enabled=True,
                formation_surplus_threshold=0.0001,
                formation_check_every_k=2,
                merge_probability=0.02,
            ),
            pop_dynamics=PopulationDynamicsConfig(
                enabled=True,
                wealth_depreciation=0.002,
                exit_wealth_threshold=0.05,
            ),
        ),
        n_steps=200,
        seed=33,
    )


# ---------- registry ----------------------------------------------------------

def baroque_with_high_welfare() -> WorldConfig:
    """Adversarial scenario (A3, validation_lift_plus_live_viz plan).

    The brief's load-bearing claim is that high intermediation (high EBI)
    does not coexist with high welfare. The adversarial search at
    `engine/validation/adversarial.py` tries to break that claim by
    sweeping the speculative folding parameters under productive folding
    being on. With seed=0 and 200 SA evaluations at small runtime scale,
    the search lands a counter-example region where terminal EBI is large
    AND terminal `real_per_capita_welfare` exceeds `coasean_paradise`'s.

    The parameters below are pinned from
    `outputs/validation/adversarial_search.json`. Keep the two in sync; the
    test in `engine/tests/test_validation_adversarial.py` checks the
    persisted JSON rather than this scenario, but if you retune the search
    update both.
    """
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.8279,
            agent_capability_sd=0.10,
            human_capability_mean=0.55,
            human_capability_sd=0.15,
            n_human_prototypes=600,
            n_agent_prototypes=6_000,
            seed=99 + 7,
        ),
        topology=TopologyConfig(
            alpha=0.9500,
            folding_propensity=0.8500,
            folding_branching=4.5,
            fold_real_efficiency=0.5281,
            fold_nominal_multiplier=3.0,
            base_variance_absorption=0.2615,
            productive_decay=0.7142,
            cap_midpoint=0.50,
            cap_slope=4.0,
            max_productive_real_share=0.85,
        ),
        pairs_per_step=20_000,
        n_steps=30,
        seed=99,
    )


# ---------- W2b: mission economy scenarios -----------------------------------
# Smallest credible "third lever" beyond smooth-Coasean / baroque-folded.
# Sector indices (see engine/core/population.SECTOR_NAMES):
#   9 = health, 10 = education. These are the coordinator-tagged sectors
# in the Hadfield/Jacobs mission-economy reading. Two adversarial
# siblings — mission_captured and mission_competing — make the point
# that the lever isn't free.
_MISSION_COORDINATOR_SECTORS = (9, 10)  # health, education


def mission_economy() -> WorldConfig:
    """Coordinator-sector mission economy, the W2b reference run.

    A small mission levy (3% of cleared real surplus) is skimmed into a
    public-objective pool that disburses as capability uplift in health
    and education. Coordinator-sector firms also form on a lower
    surplus bar (`formation_threshold_factor = 0.4`) so the
    coordinating institutions actually appear. Mid-α (0.45) so the
    scenario sits squarely between the two attractors — the mission
    lever is being asked to do real work, not paper over an already-
    smooth economy.

    Read against `mission_captured` and `mission_competing` for the
    adversarial controls: with the captured-pool target, the same
    levy concentrates capability gains on already-high-capability
    agents; with `mission_competing`, multiple agendas raise the
    formation bar and the lever is diluted.
    """
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.70,
            agent_capability_sd=0.16,
            human_capability_mean=0.50,
            human_capability_sd=0.16,
            n_human_prototypes=6_000,
            n_agent_prototypes=60_000,
            seed=4501,
        ),
        topology=TopologyConfig(
            alpha=0.45,
            base_friction=0.04,
            folding_propensity=0.35,
            folding_branching=2.5,
            cross_stack_compat=0.65,
            institutions=InstitutionConfig(
                enabled=True,
                formation_surplus_threshold=0.0005,
                formation_check_every_k=2,
            ),
            mission=MissionConfig(
                enabled=True,
                coordinator_sectors=_MISSION_COORDINATOR_SECTORS,
                formation_threshold_factor=0.4,
                mission_levy=0.03,
                capability_uplift_per_unit_pool=2.0e-6,
                levy_target="coordinator_uplift",
            ),
        ),
        n_steps=120,
        seed=45,
    )


def mission_captured() -> WorldConfig:
    """Adversarial sibling — same mission levy, captured disbursement.

    Same lever pulls as `mission_economy` but `levy_target` is set to
    `regressive_pool`: instead of equal per-agent capability uplift in
    coordinator sectors, the pool disburses proportionally to current
    capability. The pool funds the already-skilled — the Matthew
    effect in policy form. Read off the Gini and the per-capita
    welfare gap against the reference run to see what capture costs.
    """
    cfg = mission_economy()
    cfg.topology.mission = MissionConfig(
        enabled=True,
        coordinator_sectors=_MISSION_COORDINATOR_SECTORS,
        formation_threshold_factor=0.4,
        mission_levy=0.03,
        capability_uplift_per_unit_pool=2.0e-6,
        levy_target="regressive_pool",
    )
    cfg.population.seed = 4502
    cfg.seed = 46
    return cfg


def mission_competing() -> WorldConfig:
    """Adversarial sibling — competing mission agendas dilute the lever.

    Six sectors tagged as coordinator (vs two in the reference run),
    and `formation_threshold_factor` raised above 1.0 so the broader
    set actually makes coordination *harder* than the unmissioned
    baseline — competing agendas raise the bar everywhere they touch.
    The levy still fires but its capability-uplift output is spread
    thin and partially offsets the friction the broader bias adds.
    Read against `mission_economy` for the cost of agenda dilution.
    """
    cfg = mission_economy()
    competing_sectors = (2, 4, 5, 7, 9, 10)  # manufacturing, logistics, construction, finance, health, education
    cfg.topology.mission = MissionConfig(
        enabled=True,
        coordinator_sectors=competing_sectors,
        formation_threshold_factor=1.4,  # competing agendas raise the bar
        mission_levy=0.03,
        capability_uplift_per_unit_pool=2.0e-6,
        levy_target="coordinator_uplift",
    )
    cfg.population.seed = 4503
    cfg.seed = 47
    return cfg


# ---------- W1b: norm-participation scenarios --------------------------------
# Three scenarios that bracket the norm-update axis. They share the
# W1b plumbing (`NormsConfig.enabled = True`) and a mid-α background;
# only the update rate and initial spread differ.


def norms_drift() -> WorldConfig:
    """Slow convergence — the Hadfield default.

    A small `update_rate` so norms drift gradually toward executed
    partners over the run, never sharply. Initial spread is moderate.
    The expected dynamic: by the terminal step, agents who routinely
    transact have converged in norm space and `align_reject` rates
    fall, while disconnected sub-populations stay apart.
    """
    return WorldConfig(
        population=PopulationConfig(
            agent_capability_mean=0.70,
            agent_capability_sd=0.16,
            human_capability_mean=0.50,
            human_capability_sd=0.16,
            n_human_prototypes=6_000,
            n_agent_prototypes=60_000,
            seed=7101,
        ),
        topology=TopologyConfig(
            alpha=0.45,
            base_friction=0.04,
            folding_propensity=0.30,
            cross_stack_compat=0.70,
            norms=NormsConfig(
                enabled=True,
                n_dimensions=4,
                update_rate=0.02,
                initial_norm_sd_human=0.45,
                initial_norm_sd_agent=0.25,
            ),
        ),
        n_steps=120,
        seed=71,
    )


def norms_capture() -> WorldConfig:
    """One cluster absorbs the rest.

    A larger `update_rate` and a deliberately skewed initial
    distribution (humans clustered around the origin, agents drawn
    more broadly). The expected dynamic: the densest cluster acts as
    an attractor and pulls peripheral norms toward it; the
    `align_reject` rate falls for newcomers but the "alignment" being
    converged on is the cluster's, not a population-wide compromise.
    """
    cfg = norms_drift()
    cfg.topology.norms = NormsConfig(
        enabled=True,
        n_dimensions=4,
        update_rate=0.08,
        initial_norm_sd_human=0.15,  # tight cluster
        initial_norm_sd_agent=0.60,  # broad agent spread
        capability_weight=True,
        initial_norm_seed=7102,
    )
    cfg.population.seed = 7102
    cfg.seed = 72
    return cfg


def norms_brittle() -> WorldConfig:
    """High update rate produces alignment whiplash.

    An aggressive `update_rate` (close to 1) so each step's executed
    partners overwhelm prior norm state. The expected dynamic:
    populations oscillate in norm space rather than converging, and
    `align_reject` rates fluctuate with the per-step partner draw.
    The point of the scenario is to show that fast norm update is not
    automatically a good thing.
    """
    cfg = norms_drift()
    cfg.topology.norms = NormsConfig(
        enabled=True,
        n_dimensions=4,
        update_rate=0.50,
        initial_norm_sd_human=0.45,
        initial_norm_sd_agent=0.25,
        capability_weight=True,
        initial_norm_seed=7103,
    )
    cfg.population.seed = 7103
    cfg.seed = 73
    return cfg


# ---------- Spatial sandbox (lever-driven, every subsystem on) ----------------


def spatial_sandbox() -> WorldConfig:
    """Single scenario the spatial-sandbox dashboard runs.

    Every optional subsystem is on with the defaults from
    `docs/plans/spatial-sandbox.md` §3. The dashboard's three lever
    panels eventually patch this config through `RunRequest.overrides`;
    the factory is the canonical zero-lever-touch state.

    Cast and pair-sample sizes are set high enough that the rich SSE
    sub-events (`cast_snapshot_v2`, `edges_v2`, `folds_v2`) populate
    every tick. Mirrors `engine/bench/spatial_sandbox.py` but raises
    `cast_size` to the dashboard's visible-agent target.
    """
    return WorldConfig(
        population=PopulationConfig(
            n_human_prototypes=800,
            n_agent_prototypes=87_200,
            seed=24601,
            network_model="sbm",
            network_p_local=0.6,
            agent_capability_mean=0.55,
            agent_autonomy_mean=0.7,
            agent_trade_rate_multiplier=2.0,
        ),
        topology=TopologyConfig(
            alpha=0.5,
            cross_stack_permeability=0.4,
            folding_max_depth=7,
            norms=NormsConfig(
                enabled=True,
                n_dimensions=8,
                update_rate=0.05,
                certified_fraction=0.5,
                certified_fraction_sd=0.15,
            ),
            demand=DemandConfig(enabled=True),
            pigouvian=PigouvianConfig(
                enabled=True,
                tax_rate=0.10,
                recycling="human_wealth",
            ),
            registration=RegistrationConfig(enabled=True),
            institutions=InstitutionConfig(
                enabled=True,
                cross_sector_firms=True,
            ),
            pop_dynamics=PopulationDynamicsConfig(enabled=True),
            mission=MissionConfig(enabled=True),
            strategy=StrategyConfig(enabled=True),
            law=LawConfig(enabled=True, law_strength_initial=0.5),
            regulator=RegulatorConfig(enabled=True),
            compute=ComputeConfig(
                enabled=True,
                budget_per_tick=1.0,
                power_cost_per_trade=0.0001,
                distribution="uniform",
                pool_recovery=0.0,
            ),
        ),
        pairs_per_step=20_000,
        n_steps=0,
        cast_size=5000,
        pair_sample_k=1500,
        seed=24601,
    )


SCENARIOS: Dict[str, Callable[[], WorldConfig]] = {
    "coasean_paradise": coasean_paradise,
    "baroque_cathedral": baroque_cathedral,
    "baroque_with_high_welfare": baroque_with_high_welfare,
    "equilibrium_drift": equilibrium_drift,
    "smoothing_cascade": smoothing_cascade,
    "fold_avalanche": fold_avalanche,
    "hemispherical_schism": hemispherical_schism,
    "compute_famine": compute_famine,
    "universal_advocate": universal_advocate,
    "synthetic_consumers": synthetic_consumers,
    "nimby_cascade": nimby_cascade,
    "slop_market": slop_market,
    "public_defender": public_defender,
    "matryoshka_collapse": matryoshka_collapse,
    "recursive_simulation": recursive_simulation,
    "exo_baroque_singularity": exo_baroque_singularity,
    "coasean_paradise_networked": coasean_paradise_networked,
    "baroque_cathedral_networked": baroque_cathedral_networked,
    "synthetic_consumers_v2": synthetic_consumers_v2,
    "agentic_disconnect": agentic_disconnect,
    "productive_baroque": productive_baroque,
    "derivatives_revolution": derivatives_revolution,
    "casino_collapse": casino_collapse,
    "legal_collapse": legal_collapse,
    "regulatory_capture": regulatory_capture,
    "civic_renaissance": civic_renaissance,
    "pigouvian_light": pigouvian_light,
    "pigouvian_heavy": pigouvian_heavy,
    "pigouvian_friction": pigouvian_friction,
    "pigouvian_baroque": pigouvian_baroque,
    "endogenous_paradise": endogenous_paradise,
    "endogenous_baroque": endogenous_baroque,
    "institutional_emergence": institutional_emergence,
    "full_emergence": full_emergence,
    "mission_economy": mission_economy,
    "mission_captured": mission_captured,
    "mission_competing": mission_competing,
    "norms_drift": norms_drift,
    "norms_capture": norms_capture,
    "norms_brittle": norms_brittle,
    "spatial_sandbox": spatial_sandbox,
}


SCENARIO_DESCRIPTIONS = {
    "coasean_paradise": "Seb Krier's dream, peak smooth-world. α is held near 0, the friction floor is low, and the folding kernel is effectively off. Every cleared trade is a single direct exchange between two parties, so cumulative nominal GDP and real welfare track each other to within noise and EBI lands at ≈ 1. Used as the reference scenario against which all higher-α regimes are read.",
    "baroque_cathedral": "The fractal-limit baseline. α is high, the folding kernel sustains itself across the full per-scenario depth budget, and the per-layer nominal multiplier is set to its design value. Cumulative nominal GDP separates from real welfare by several orders of magnitude over the run; per-capita welfare lands well below the smooth baseline. The reference scenario for the high-α attractor.",
    "baroque_with_high_welfare": "A counter-example using adversarial parameter search over the prior. α and the folding kernel are configured to produce EBI > 10, but capability and demand-side parameters are tuned so per-capita welfare exceeds the smooth baseline. A proof that high EBI does not strictly imply low welfare, even though the two correlate strongly across the population of plausible scenarios.",
    "equilibrium_drift": "α is held at 0.5. Both attractors exert pull and the seed-to-seed envelope on EBI is wide. Used to read off how much active mechanism design is needed to keep the economy off the mid-α default that an unmanaged population drifts toward.",
    "smoothing_cascade": "α is scheduled to decay linearly from 0.95 down to 0.05 over the run. A controlled test of whether an economy already deep in the fractal regime can be steered back toward direct trade by a credible commitment to wind down folding. The recovery in EBI lags behind the policy schedule by several steps because the existing folded layers do not unwind instantaneously.",
    "fold_avalanche": "α is scheduled to ramp from 0 toward 1 over the run — the mirror of smoothing_cascade. EBI take-off precedes the welfare collapse: the nominal ledger compounds immediately while welfare losses propagate through the per-depth efficiency leak. This reports the lag between the two ledgers when the schedule moves α faster than the welfare side can register.",
    "hemispherical_schism": "Multiple incompatible economic stacks (a US/EU/China-style fragmentation in miniature). Cross-stack compatibility is set near zero, which raises both the law-filter rejection probability and the per-trade cost on any inter-stack pair. Intra-stack trade dominates; the surplus that previously cleared across stacks is lost to translation, compliance, and trust costs.",
    "compute_famine": "The friction floor on every trade rises mid-run, modeling a sudden revaluation of compute cost. The marginal sub-trade — the one that depended on a near-zero floor to clear — gets priced out first. Read as the asymmetric exposure of high-α scenarios to a friction-floor shock: low-α regimes barely register the change, high-α regimes shed deep folding layers within a few steps.",
    "universal_advocate": "Agent capability is raised across the entire population — high-capability representation is available to every household, not just the wealthy. The folding parameters are pulled down to the low-α direct-trade baseline. The wealth Gini compresses because the asymmetric bargaining power that might otherwise be compounded across deciles is removed at the source rather than redistributed after the fact.",
    "synthetic_consumers": "Agent autonomy is raised across the population so that agents act on their human principals' behalf for most decisions. Demand is generated and routed by agents; humans appear in the executable trade set as a low-percentage minority. Reports the unweighted accounting and is the input baseline to synthetic_consumers_v2, which adds the demand-side weighting on top.",
    "nimby_cascade": "The alignment-layer rejection rate is raised across the population, modelling mass exercise of individual veto power. Many otherwise-clearing trades die in the alignment filter rather than the cost calculation. A stress test on how a high-veto regime locks surplus behind objections, and how much of the surplus was structurally contestable to begin with.",
    "slop_market": "High α with low agent capability — capability roughly N(0.30, 0.15). Sub-trades spawn at the maximum permitted rate but cannot extract real value from the layering, so they accumulate as rent-collecting noise on top of every base exchange. EBI ranges into 10⁵–10⁶; per-capita welfare lands well below the smooth baseline. The clearest failure case in the whole scenario set.",
    "public_defender": "A targeted capability uplift for the bottom of the wealth distribution: agent capability variance is widened and the lower tail is raised, leaving the upper deciles untouched. Folding parameters sit at the low-α baseline. A more politically tractable analogue of universal_advocate; tests whether redistributive access alone is enough to compress the wealth Gini in a moderately folded economy.",
    "matryoshka_collapse": "Both the market filter and the alignment filter are raised toward their tightest setting. Most attempted trades die in the filters before reaching the cost calculation, so cumulative nominal GDP and real welfare both contract. Read as the institutional side of the smooth attractor in the limit: when governance is strict on every layer, surviving trade volume is small and the Gini barely moves because marginal trade does not happen.",
    "recursive_simulation": "α responds endogenously to the running EBI: the more fractal the economy gets, the higher the propensity to spawn further sub-trades. A positive-feedback loop with no governor. The basin around the smooth attractor is shallow and the system tips into the fractal attractor within roughly twenty steps; useful for reading off how locally-stable the smooth regime is under reflexive folding pressure.",
    "exo_baroque_singularity": "The depth limit on the folding kernel is removed; folding compounds without a ceiling. EBI ranges into the 10⁶–10⁷ band and per-capita welfare collapses to within an order of magnitude of zero. Think of it as an upper-bound diagnostic on what unbounded fractal trade asymptotes to.",
    "coasean_paradise_networked": "The richest-stack low-α variant: smooth-limit configuration on a Barabási-Albert scale-free network (Atalay et al. 2011 degree exponent), with t-copula coupled noise (df = 4, BEA 2022 input-output correlations), a Hawkes self-exciting folding kernel (Bacry & Muzy 2015 endogeneity), productive folding on (base_variance_absorption = 0.20), and demand-side weighting on with a 20% A2A floor (DemandConfig.enabled = True, a2a_floor = 0.20). Per-capita welfare lands above plain coasean_paradise because the productive and demand levers are stacked on top of the topology change; not an apples-to-apples topology-robustness test against coasean_paradise. To read off pure topology effects, hold productive folding and demand weighting at the coasean_paradise defaults.",
    "baroque_cathedral_networked": "The richest-stack baroque variant: high-α cathedral configuration on a sector-block stochastic block model, with t-copula coupled noise (df = 4, BEA 2022 input-output correlations), a Hawkes self-exciting folding kernel (Bacry & Muzy 2015 endogeneity), productive folding on (base_variance_absorption = 0.35, so 35% of fold-nominal volume converts to real welfare via risk pooling, hedging, and price discovery), and demand-side weighting on (DemandConfig.enabled = True, A2A surplus credited at the 15% floor). Per-capita real welfare is the highest in the high-α band; nominal residual is still ≈ 99.99% parasitic by Sankey share, so the two ledgers diverge in opposite directions — W large in absolute terms, share-of-G to humans tiny. Compare to plain baroque_cathedral.",
    "synthetic_consumers_v2": "synthetic_consumers with demand-side weighting on. Trades that reach a human consumer count for full welfare; pure agent-to-agent trades are credited at the 15% floor that accounts for indirect downstream benefits. This reports the gap between what the economy printed and what humans got, separating accounting from welfare in a way the unweighted version cannot.",
    "agentic_disconnect": "Households delegate; agent autonomy is raised toward the high end of its prior across the population. Demand-side weighting is on, so welfare credit is conditional on a human (or a low-autonomy delegate of a human) being on at least one side of a trade. Tests whether the welfare being booked actually reaches the population or whether it circulates indefinitely inside the agent layer.",
    "productive_baroque": "Same fractal-folding rate as slop_market, but with high-capability agents — capability roughly N(0.80, 0.15). Sub-trades produce real surplus (risk pooling, price discovery, liquidity transfer) rather than pure overhead, so the per-layer welfare leak is reduced. This reports the productive-vs-parasitic split in the high-α regime: how much of the headline output is genuine welfare and how much is structurally inseparable from accounting theatre.",
    "derivatives_revolution": "Mid-α (~0.6), low platform fees, and the productive-folding parameter is on. Folding is moderate but generative: each layer adds value rather than overhead. The cleanest test of whether fractal trade can deliver welfare gains within reasonable bounds when sub-markets are skilled enough to execute the jobs they nominally claim.",
    "casino_collapse": "High α, low capability, productive-folding enabled. The structural permission for productive sub-trades is in place but the agents lack the skill to extract value from them, so the layering devolves into pure speculation. EBI lands close to slop_market and per-capita welfare crashes, despite the productive regime nominally being active.",
    "legal_collapse": "The law layer's rejection probability rises smoothly over the run as legal capacity decays. Stranger-to-stranger trades (high cross-stack distance, high alignment distance) bear most of the cost and trades inside trusted networks are largely unaffected. The welfare loss takes the shape of a slow regression measured in lost contracts rather than a single event.",
    "regulatory_capture": "Stigler's nightmare scenario. Wealth concentrates over the run and the law layer is gradually captured: the cross-stack compatibility falls and the captured law preferentially blocks trades against the captured group's interest. The welfare loss is paid disproportionately by the unconcentrated population. Read alongside legal_collapse and civic_renaissance as the three-way test on the law layer's stability.",
    "civic_renaissance": "Active legal upkeep is on and civic pushback against capture is active. The optimistic mirror of legal_collapse and regulatory_capture; tests whether decentralised maintenance can hold legal capacity at the level the other two scenarios let it slip away from. The welfare ledger sits between the two and the EBI band is tighter than either.",
    "pigouvian_light": "A 10% Pigouvian tax targeting A2A nominal volume — both base trades (S + C) and the fold-cascade nominal contribution Σ N_d. The tax has two effects per step: (i) deterrence, the cascade's nominal contribution is reduced by tax_rate × automation_gap, lowering EBI; (ii) revenue, the collected tax is recycled to human wealth. At 10% with α = 0.6, EBI lands ~7-8% below the no-tax baseline (synthetic_consumers_v2). Tests whether a small Pigouvian wedge meaningfully bends the parasitic-accounting trajectory.",
    "pigouvian_heavy": "A 35% Pigouvian tax on A2A nominal volume (base + fold cascade), recycled to human wealth with progressivity 1.5 (poorer humans receive disproportionately more of the recycled revenue). The deterrence effect is substantial: at α = 0.6 the cascade's nominal contribution is suppressed enough to lower EBI by ~25-30% versus the no-tax baseline, and the tax revenue is roughly an order of magnitude larger than under the welfare-only tax base used before. Tests whether a heavy-handed Pigouvian rate can compress EBI without proportionally compressing real welfare.",
    "pigouvian_friction": "A 15% Pigouvian tax on A2A nominal volume (base + fold cascade), recycled as a friction subsidy on H2A trades rather than as cash to humans. The deterrence on fold-cascade nominal is the same as Pigouvian Light at the higher rate, but the recycling channel routes revenue to *cost relief* on human-touching trades — bringing humans back into the executable trade set via the supply side rather than via the demand side. At α = 0.6 EBI is suppressed ~10-12% below the no-tax baseline; the welfare/recycling differences vs Pigouvian Heavy are best read off the §5 Sankey, not the EBI line.",
    "pigouvian_baroque": "A 35% Pigouvian tax on A2A nominal volume applied to a productive-fractal baseline (α = 0.85 with productive folding on). Distinct from pigouvian_heavy in the underlying scenario: here the fold cascade has both productive and parasitic components, and the tax targets the entire A2A nominal flow regardless of which side of the productive split it sits on. Tests whether a flat fold-cascade tax suppresses productive intermediation as a side effect — i.e. whether the corrective transfer is a precision instrument or a blunt one.",
    "endogenous_paradise": "Direct-trade-like configuration with per-prototype intermediation-preference learning enabled — a contextual bandit on each prototype's choice of α. Tests whether agents would themselves choose direct trade if they could choose any α, or whether learning steers the population toward a more folded equilibrium even with no exogenous push.",
    "endogenous_baroque": "Fractal configuration with the same learning layer enabled. Tests what α agents converge to when they are free to choose. Empirically the learning settles in the upper-mid range, not at the high-α extreme — the cathedral takes external scaffolding to sustain.",
    "institutional_emergence": "Adds firm formation and dissolution on top of strategic learning. Coalitions form when within-coalition trades become cheaper than market trades and dissolve when the cost advantage decays. Tests whether the modern firm's existence is robust to a near-zero transaction-cost technology, or whether firms re-emerge in different shapes (smaller, more fluid, sector-specific).",
    "full_emergence": "All four feedback layers on at once: strategic learning, firm formation, population churn, and accumulating fold pressure. The maximal-richness configuration in the scenario set. A kind of stress test for whether the diagnostic story here can survive heavy compounding rather than a specific regime to plan for.",
    "mission_economy": "Tomašev / Jacobs's third lever beyond smooth-Coasean and baroque-folded. Health and education are tagged as coordinator sectors; a 3% mission levy on cleared real surplus drains into a public-objective pool that disburses as flat-share capability uplift in those sectors. Coordinator firms form on a 40% lower surplus bar, so the coordinating institutions actually appear. Mid-α (0.45) so the lever is doing work, not papering over an already-smooth economy.",
    "mission_captured": "Adversarial sibling of mission_economy. Same levy, same coordinator tags, but the disbursement is `regressive_pool` — capability uplift goes to already-high-capability agents in proportion to their existing capability. The Matthew effect in policy form. Read against the reference run for what capture costs at the Gini and per-capita-welfare lines.",
    "mission_competing": "Adversarial sibling of mission_economy. Six sectors tagged as coordinator (manufacturing, logistics, construction, finance, health, education) and `formation_threshold_factor` raised above 1.0 so the broader bias actually makes coordination harder than the unmissioned baseline — competing agendas raise the bar everywhere they touch. The levy still funds capability uplift but its output is spread thin and partially offsets the friction the broader bias adds.",
    "norms_drift": "W1b reference run. Static-distance `align_reject` is replaced by distance-in-norm-space and a small EMA update toward executed partners (`update_rate=0.02`). The expected dynamic over the run: agents who routinely transact converge in norm space and their `align_reject` rate falls, while disconnected sub-populations stay apart. The Hadfield 'normative infrastructure for AI alignment' framing operationalised — alignment is participation, not preference-matching at static distance.",
    "norms_capture": "Adversarial sibling of norms_drift. Initial norm distribution is deliberately skewed (humans tightly clustered around the origin, agents broadly drawn), and `update_rate` is raised to 0.08. The densest cluster acts as an attractor and pulls peripheral norms toward it; alignment converges on the cluster's norm rather than a population-wide compromise. Read alongside norms_drift to see what gradient capture does to the binding-constraint rejection share.",
    "norms_brittle": "Adversarial sibling of norms_drift. `update_rate` raised to 0.50 so each step's executed partners overwhelm prior norm state. Norms oscillate rather than converging and the `align_reject` rate fluctuates with the per-step partner draw. The point: fast norm update is not automatically a good thing — there is a brittleness regime where Hadfield's alignment-as-participation flips into permanent whiplash.",
    "spatial_sandbox": "The single scenario the spatial-sandbox dashboard runs. Every optional subsystem is on with the lever-panel defaults from `docs/plans/spatial-sandbox.md` §3: norms with K=8 dimensions and a certified fraction, demand-side weighting, Pigouvian recycling to human wealth, registration, cross-sector firms, population dynamics, mission economy, strategic emergence, dynamic law with a per-pair size cap, regulator, and the new ComputeConfig admission filter. Cast size 5,000 and pair-sample K=1,500 so the rich SSE sub-events stream every tick. The dashboard's three lever panels patch this config through `RunRequest.overrides`; clusters appear because they form, not because they were drawn.",
}


def _enable_endogenous_dynamics(cfg: WorldConfig) -> WorldConfig:
    """Turn on four richer-engine layers in-place on an existing scenario.

    Switches `folding_pressure_feedback`, `pop_dynamics`, `institutions`,
    and a 100× agent-trade-rate multiplier on with conservative defaults.
    The scenario's α, folding parameters, network, demand, and law
    settings are preserved so it keeps its thematic identity — what
    changes is:

    * EBI becomes a trajectory rather than a steady-state ratio, because
      folding propensity rises with accumulated fold-pressure;
    * capability and wealth churn over time and firms form/dissolve, so
      the population mix shifts during a run;
    * agents are sampled into trade pairs 100× more often than humans
      per unit of mass — reflecting the real-world disparity that an AI
      agent can attempt orders of magnitude more trades per second than
      a human can. This pushes a2a-share further toward saturation and
      drops human-legibility into the 10⁻⁵–10⁻⁴ range.

    `strategy` (per-prototype intermediation-preference learning) is
    deliberately *not* enabled here, because it would override the
    scenario's structural α with whatever the bandit optimises and erase
    the thematic distinction between scenarios. It stays scoped to the
    explicitly endogenous_* / full_emergence scenario family.
    """
    t = cfg.topology
    t.folding_pressure_feedback = True
    if not t.institutions.enabled:
        t.institutions = InstitutionConfig(enabled=True)
    if not t.pop_dynamics.enabled:
        t.pop_dynamics = PopulationDynamicsConfig(enabled=True)
    cfg.population.agent_trade_rate_multiplier = 100.0
    cfg.population.human_trade_rate_multiplier = 1.0
    return cfg


# Scenarios that should exercise the endogenous-feedback layers. Selection
# rule: α ≥ 0.4, not already a smooth-limit case, not already running its
# own time-varying schedule (fold_avalanche, smoothing_cascade — α ramps),
# not the EBI-self-reflexive recursive_simulation, not the explicitly
# pre-endogenous scenarios. Civic_renaissance/legal_collapse/
# regulatory_capture get included — they already have law dynamics, and
# the fold-feedback compounds the law-capture loop in a thematically
# correct way.
_ENDOGENOUS_SCENARIOS = {
    "compute_famine",
    "nimby_cascade",
    "matryoshka_collapse",
    "legal_collapse",
    "equilibrium_drift",
    "agentic_disconnect",
    "hemispherical_schism",
    "derivatives_revolution",
    "regulatory_capture",
    "synthetic_consumers",
    "synthetic_consumers_v2",
    "pigouvian_light",
    "pigouvian_heavy",
    "pigouvian_friction",
    "slop_market",
    "productive_baroque",
    "casino_collapse",
    "pigouvian_baroque",
    "baroque_cathedral",
    "baroque_cathedral_networked",
    "baroque_with_high_welfare",
    "exo_baroque_singularity",
}


def _wrap_with_dynamics(factory: Callable[[], WorldConfig]) -> Callable[[], WorldConfig]:
    def _wrapped() -> WorldConfig:
        return _enable_endogenous_dynamics(factory())
    _wrapped.__name__ = factory.__name__
    _wrapped.__doc__ = factory.__doc__
    return _wrapped


SCENARIOS = {
    name: (_wrap_with_dynamics(fn) if name in _ENDOGENOUS_SCENARIOS else fn)
    for name, fn in SCENARIOS.items()
}


# ---------- Substrate experiment: empirical anchoring with productive
# levers explicitly off, registered as `<name>_anchored` scenarios. The
# point of this set is to isolate the topology+noise+kernel effect on
# welfare and EBI from the productive-folding/demand-weighting effect
# that currently confounds the Productive Cathedral comparison.


def _apply_empirical_topology(cfg: WorldConfig) -> WorldConfig:
    """Mutate cfg in place to put it on the empirical substrate's topology
    layer only — sector-block network + t-copula correlated noise + Hawkes
    self-exciting folding kernel. Does *not* touch productive-folding levers
    (`base_variance_absorption`) or demand weighting. Use this when sweeping
    those levers as parameters (e.g., Sobol) but you still want realistic
    network and noise.

    Settings match those used in `baroque_cathedral_networked` so we don't
    introduce yet another knob.
    """
    p = cfg.population
    p.network_model = "sbm"
    p.network_mean_degree = 14
    p.network_intra_sector_share = 0.75
    p.network_p_local = 0.85

    t = cfg.topology
    t.noise_model = "t_copula"
    t.folding_model = "hawkes"
    return cfg


def _apply_empirical_substrate(cfg: WorldConfig) -> WorldConfig:
    """Apply the empirical topology *and* explicitly clear the productive
    levers so the substrate-vs-plain comparison is uncontaminated by the
    productive-folding faucet.

    This is the form used to anchor the dashboard's 21 substrate-default
    scenarios. For sweeps that need productive levers as parameters,
    use `_apply_empirical_topology` instead.
    """
    cfg = _apply_empirical_topology(cfg)
    t = cfg.topology
    t.base_variance_absorption = 0.0
    t.demand = DemandConfig(enabled=False)
    return cfg


def _wrap_with_substrate(factory: Callable[[], WorldConfig]) -> Callable[[], WorldConfig]:
    def _wrapped() -> WorldConfig:
        return _apply_empirical_substrate(factory())
    _wrapped.__name__ = factory.__name__ + "_anchored"
    _wrapped.__doc__ = (factory.__doc__ or "") + "\n\nAnchored variant: empirical substrate (SBM network + t-copula noise + Hawkes folding) with productive folding and demand weighting explicitly off."
    return _wrapped


# Skip baroque_cathedral_networked (= Productive Cathedral on the dashboard) —
# it already has the substrate, but with productive levers ON, so the anchored
# version would duplicate the experimental cell we already have.
_SUBSTRATE_SCENARIOS = [n for n in SCENARIOS if n != "baroque_cathedral_networked"]

for _name in _SUBSTRATE_SCENARIOS:
    SCENARIOS[f"{_name}_anchored"] = _wrap_with_substrate(SCENARIOS[_name])


# ---------- Switch the dashboard's 21 substrate-eligible scenarios to use
# the empirical substrate as their default. This makes the welfare numbers
# everywhere on the dashboard reflect realistic matching efficiency rather
# than the well-mixed default that was systematically understating welfare
# by ~60%. The four exclusions:
#
#   - derivatives_revolution, productive_baroque: have productive folding
#     turned on, which is the lever the §4 productive-yield chart reads
#     off. Switching them to anchored (which forces base_variance_absorption
#     = 0) would erase that chart's content for those scenarios.
#   - baroque_cathedral_networked (Productive Cathedral): already on the
#     substrate with productive levers on. Already anchored by design.
#   - baroque_with_high_welfare: the adversarial-search variant whose
#     hand-tuned parameters do not survive the substrate switch (the
#     comparison shows ΔEBI +149%, ΔW −42% — its hand-tuning is
#     well-mixed-specific).
_DASHBOARD_25 = [
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
_SUBSTRATE_DEFAULT_EXCLUDED = {
    "derivatives_revolution", "productive_baroque",
    "baroque_cathedral_networked", "baroque_with_high_welfare",
}
_SUBSTRATE_DEFAULT_SCENARIOS = [
    n for n in _DASHBOARD_25 if n not in _SUBSTRATE_DEFAULT_EXCLUDED
]

for _name in _SUBSTRATE_DEFAULT_SCENARIOS:
    SCENARIOS[_name] = _wrap_with_substrate(SCENARIOS[_name])


def get_scenario(name: str) -> WorldConfig:
    if name not in SCENARIOS:
        raise KeyError(f"Unknown scenario {name!r}. Available: {list(SCENARIOS)}")
    return SCENARIOS[name]()


def list_scenarios() -> list[tuple[str, str]]:
    # `_anchored` variants are wrapped programmatically and share the base
    # scenario's description (with a substrate-anchored suffix). Other keys
    # missing from SCENARIO_DESCRIPTIONS fall back to an empty string rather
    # than raising — the dashboard endpoint must not 500 on a registration
    # mismatch.
    out: list[tuple[str, str]] = []
    suffix = "_anchored"
    for k in SCENARIOS:
        if k in SCENARIO_DESCRIPTIONS:
            out.append((k, SCENARIO_DESCRIPTIONS[k]))
        elif k.endswith(suffix) and k[: -len(suffix)] in SCENARIO_DESCRIPTIONS:
            base = k[: -len(suffix)]
            out.append((k, SCENARIO_DESCRIPTIONS[base] + " (substrate-anchored variant)"))
        else:
            out.append((k, ""))
    return out

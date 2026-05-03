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
    DemandConfig,
    InstitutionConfig,
    LawConfig,
    PigouvianConfig,
    PopulationDynamicsConfig,
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
}


SCENARIO_DESCRIPTIONS = {
    "coasean_paradise": "The direct-trade limit. Transaction costs are near zero, no sub-trades spawn, and every unit of measured activity lands as actual human consumption. EBI sits at ≈ 1.",
    "baroque_cathedral": "The fractal-trade limit. Each base trade spawns deep towers of sub-trades. Nominal GDP explodes; the share of activity that humans can audit collapses.",
    "baroque_with_high_welfare": "An adversarial counter-example: a parameter pocket where the economy is highly fractal (EBI > 10) and yet humans consume more than they would in the direct-trade limit. Tests whether high EBI is sufficient to imply low welfare.",
    "equilibrium_drift": "α held at 0.5 — the mid-range. Both the direct-trade and fractal-trade attractors pull; outcomes are sensitive to small parameter changes.",
    "smoothing_cascade": "α scheduled to decay from 1 → 0 over the run. Tests whether an economy already deep in fractal-trade mode can be steered back to direct-trade.",
    "fold_avalanche": "α scheduled to ramp from 0 → 1. Tests how fast direct-trade economies tip into fractal-trade once sub-trade ceilings come off.",
    "hemispherical_schism": "Multiple incompatible economic stacks (think US/EU/China-style fragmentation). Cross-stack trades face severe friction; intra-stack trade dominates.",
    "compute_famine": "The cost floor on every trade rises mid-run, simulating compute scarcity. Tests which trades get priced out first.",
    "universal_advocate": "High-capability agents available to everyone, not just the wealthy. Direct-trade outcome with equity-side correction.",
    "synthetic_consumers": "Agents do most of the buying as well as the selling. Humans are a tiny minority of activity even when α is moderate.",
    "nimby_cascade": "Mass alignment-layer objections block trades that would otherwise clear. Tests how individual-level vetoes scale.",
    "slop_market": "High α plus low agent capability — fractal-trade economy without the productive sub-trades. Pure overhead. EBI explodes; welfare crashes.",
    "public_defender": "Voucher-style capability uplift for the bottom of the wealth distribution. Tests whether redistributive capability access compresses Gini.",
    "matryoshka_collapse": "Both the market filter and the alignment filter are highly restrictive — most attempted trades die in filters before reaching the cost calculation.",
    "recursive_simulation": "α itself responds to the running EBI: as the economy fractal-fies, the appetite for further fractal-fying grows. A positive-feedback take-off.",
    "exo_baroque_singularity": "Sub-trade depth limits removed; tests the asymptotic behavior of fractal trade when nothing caps it.",
    "coasean_paradise_networked": "Direct-trade outcome under realistic network structure (scale-free wiring, heavy-tail noise, self-exciting sub-trade cascades). Tests whether the smooth attractor survives realism.",
    "baroque_cathedral_networked": "Fractal-trade outcome under realistic network structure (community-block wiring, heavy-tail noise, self-exciting sub-trade cascades).",
    "synthetic_consumers_v2": "Like Synthetic Consumers but with the demand-side feedback turned on: only trades that ultimately reach a human consumer count as real welfare. Exposes how much accounting is internal to the agent layer.",
    "agentic_disconnect": "Humans step back from active participation; agents transact on their behalf. Demand-side feedback exposes how much real welfare actually reaches humans vs. circulates among agents.",
    "productive_baroque": "Fractal-trade economy where agents are capable enough that the sub-trades produce real value (e.g. risk pooling, price discovery), not just overhead. Tests the productive vs parasitic split.",
    "derivatives_revolution": "Mid-α, low platform fees, aggressive productive sub-trades. Tests whether fractal trade can deliver welfare gains within reasonable bounds.",
    "casino_collapse": "High α + low capability + productive sub-trades enabled. Tests whether enabling productive folding still produces welfare when agents lack the skill to execute it.",
    "legal_collapse": "Legal capacity decays over the run (no upkeep). Stranger-to-stranger trade gets harder; many attempts die in cost rejection.",
    "regulatory_capture": "Wealth concentrates and starts to capture the legal layer itself. Cross-stack trades lose surplus to the captured law.",
    "civic_renaissance": "Active legal upkeep plus civic pushback against capture. Tests whether legal capacity can be sustained under concentration.",
    "pigouvian_light": "10% tax on agent-to-agent trades, recycled to human wealth. Twin of synthetic_consumers_v2 with a corrective transfer.",
    "pigouvian_heavy": "35% agent-to-agent tax. Tests overcorrection: can the tax be set high enough that human welfare overshoots the no-tax baseline?",
    "pigouvian_friction": "Agent-to-agent tax recycled as a friction subsidy on human-to-agent trades. Tests bringing humans back into the trading mix via cost relief.",
    "pigouvian_baroque": "The agent-to-agent tax applied to a productive-fractal baseline. Tests whether the tax correctly distinguishes productive sub-trades from purely extractive ones.",
    "endogenous_paradise": "Direct-trade-like configuration, but agents learn their own intermediation preferences over the run via a bandit. Tests whether the smooth attractor survives strategic learning.",
    "endogenous_baroque": "Fractal-trade configuration with the same learning layer enabled. Tests what agents would actually choose if they could.",
    "institutional_emergence": "Adds firm formation and dissolution on top of strategic learning. Coalitions form when within-coalition trades become cheaper than market trades.",
    "full_emergence": "All four feedback layers on at once: strategic learning, firm formation, population churn, and accumulating fold pressure.",
}


# Narrative vignettes — one short paragraph per scenario, written as a near-future
# scene rather than a parameter description. Rendered in §4 of the dashboard
# beneath SCENARIO_DESCRIPTIONS to give the lay reader a feel for what the
# regime actually looks like to the people inside it. Target ~70-80 words each
# so the detail panes have visual parity across scenarios.
SCENARIO_NARRATIVES = {
    "coasean_paradise": "A small town rebuilds its economy from scratch. Two parties meet, agree on a price, and the value moves directly between them. No platforms take a cut; no derivative markets layer on top; no instruments repackage the trade for some downstream buyer. Every dollar of measured GDP is something a human will eat, wear, learn, or sleep in. The accounting is boring because the economy is honest — welfare and nominal output collapse to the same number, and the bookkeeping fits on one page.",
    "coasean_paradise_networked": "The same direct-trade settlement, wired into the messy real world: a power-law network where some traders are far more connected than others, heavy-tailed shocks that occasionally rip through the system, and the social tendency for buying decisions to copy each other. The simulation asks whether the smooth attractor is robust to realism — whether honest accounting can survive viral cascades, hub failures, and herding behaviour, or whether a Coasean economy is only ever a regular-graph fiction that scale-free reality dissolves on contact.",
    "smoothing_cascade": "A regulatory commission inherits a fully-baroque economy and sets out to dismantle it on a schedule. Each quarter the rules tighten: derivative layers must unwind, sub-trades must cease compounding, the platforms must let trades clear directly. The model asks whether you can walk a fractal economy backward — whether the institutional muscle for direct exchange can be rebuilt once an entire generation of accountants, traders, and regulators has known nothing but the towers, and whether the unwinding causes its own kind of damage.",
    "universal_advocate": "High-capability AI representation is no longer a luxury good. Every household — from the bottom percentile up — has access to the same caliber of negotiating agent the wealthy used to retain privately. The folding is mostly off, so the economy stays close to direct trade; what shifts is who benefits from each clean exchange. The market becomes flatter not because everyone is identical but because the asymmetric bargaining power that used to compound silently across decades has been zeroed out at the source.",
    "public_defender": "A voucher program funds capability uplift specifically for the bottom of the wealth distribution. The state subsidizes the agentic muscle of those who couldn't otherwise afford it, while leaving the upper deciles to source their own. The simulation watches whether targeted access — rather than universal access — is enough to compress the wealth Gini in a moderately folded economy. It is the near-term policy lever that the more sweeping Universal Advocate scenario makes look maximalist and politically out of reach.",
    "civic_renaissance": "Citizens organize around their legal commons. Active maintenance crews keep courts and enforcement capacity online; civic groups push back when wealth tries to bend the rule of law to its preferred shape. The simulation tests whether voluntary, decentralized upkeep — donated time, organized vigilance, ordinary people refusing to look away — can hold the line that Legal Collapse and Regulatory Capture each trace as a slow surrender. It is the optimistic mirror of those two scenarios, asked seriously and run to its conclusions.",
    "compute_famine": "Mid-run, the underlying compute that powered all the cheap intermediation suddenly costs ten times what it did. Cost floors rise across every trade. The marginal sub-trade — the one that depended on near-zero overhead to make sense — gets priced out first. The model watches which layers of activity die back when the friction floor stops being negligible. It is a stress test for an economy that quietly bet everything on cheap inference, asked one morning to pay for it.",
    "nimby_cascade": "Alignment-layer objections become a mass political instrument. Communities and individuals routinely block trades on values grounds — not just edge cases but at scale, and not just dramatic ones but ordinary daily commerce. The simulation watches what happens when veto power is widely held and frequently exercised: how many otherwise-clearing trades die in the alignment filter, and whether a high-veto economy converges on something more humane or merely more constipated, with surplus locked behind objections nobody can negotiate around.",
    "matryoshka_collapse": "Both the market filter and the alignment filter have been ratcheted to their tightest setting — every trade must clear a strict regulatory test and a strict ethical test before its costs can even be calculated. Most attempts die before they reach the price stage. Activity volumes crater not because no one wants to trade but because almost nothing makes it through the gates. The economy shrinks into the small surviving subset of trades that satisfies everyone, and most days nothing of consequence happens.",
    "legal_collapse": "Public legal capacity decays through neglect — courts under-resourced, contract enforcement unreliable, stranger-to-stranger trades increasingly unsafe. As legal infrastructure thins, more attempted trades die in the cost filter: the friction of operating without legal recourse becomes higher than the surplus of trading at all. The economy retreats inward, into networks of trust and known counterparties, while the formal sector shrivels. It is a slow-motion regression measured in lost contracts rather than in any single event.",
    "equilibrium_drift": "The dial is held precisely at the midpoint between the smooth and striated limits. Both attractors pull on the economy, and any small parameter change can decide which one wins. The simulation watches a system poised on the edge — not in a dramatic crisis, but in a long, anxious drift where small policy choices, small accidents, and small fashions tip welfare and accounting separately, in ways the model surfaces and the inhabitants typically only feel as a vague directional weather.",
    "agentic_disconnect": "Households delegate. Buying, comparison, negotiation, settlement — all of it routed through household-level agents. Most humans are no longer first-person economic actors; they're principals whose preferences are inferred. With demand-side feedback on, the model asks whether the welfare being booked actually reaches anyone, or whether it circulates among the agents indefinitely and never finds the human consumer it was supposedly produced for, leaving the population fed and clothed by mechanisms they would struggle to describe if asked.",
    "hemispherical_schism": "The world's economy has split into incompatible stacks — different platforms, different alignment regimes, different legal frameworks. Trade inside a stack is cheap; trade across stacks bleeds surplus to translation, compliance, and trust costs. A US-EU-China-style fragmentation simulated in miniature: the model surfaces how much of the modern economy's productivity was actually a peace dividend on a single shared technical layer, and what gets lost when that layer comes apart into fortified regional blocs that no longer trust each other.",
    "derivatives_revolution": "Platform fees fall to historical lows; productive sub-trades — risk pooling, hedging, price discovery, liquidity provision — light up across the economy. Folding is moderate but generative: each layer adds genuine value rather than just overhead. The simulation tests whether fractal trade can be a feature rather than a bug, and whether welfare gains within reasonable bounds are achievable when the sub-markets are skilled enough to do the jobs they nominally claim to be doing, instead of merely charging for the appearance of doing them.",
    "regulatory_capture": "Wealth has concentrated to the point where it begins to author the rules. The legal layer — once nominally neutral — bends towards the largest holders. Cross-stack trades start losing surplus to law that has been quietly captured. Civic pushback is muted; institutional decay is gradual rather than sudden. The simulation surfaces what happens when the rule of law becomes one more thing the rich can buy: not a shock event, but a continuous tax on everyone else, paid in a currency they cannot directly see.",
    "synthetic_consumers": "The buyer side has gone agentic. Demand is generated by AI on behalf of humans, aggregated, optimized, and routed through layers of agent intermediation. Humans remain the nominal beneficiaries but are a tiny share of the actual transactional mass. Even at moderate folding, the activity is overwhelmingly machine-to-machine, with the human consumer pulled along behind it like a paper signature attached to an electronic ledger that has long since stopped consulting them on anything beyond the broadest preference categories.",
    "synthetic_consumers_v2": "Same machine-dominated demand side, but now the model only credits welfare that actually reaches a human consumer. The reported numbers separate cleanly into what the economy printed and what humans got. The gap between them is the surplus that lived its entire life inside the agent layer — measured, accounted, audited, and never landing anywhere a person could spend it. Accounting honesty is restored even as the underlying mismatch widens, and the auditors at least know which ledger is which.",
    "slop_market": "An economy where the dial is high and the agents are dumb. Sub-trades spawn at maximum rate but can't extract real value from the layering — they're rent-collecting noise on top of every base exchange. Nominal GDP soars on pure paperwork. The exo-baroque index explodes; per-capita welfare crashes. The activity is fully measured and almost completely useless, like an industrial press stamping out spreadsheets no one will ever read, billed for and counted in the national accounts at full sticker price.",
    "productive_baroque": "Same fractal rate as Slop Market, but with high-capability agents wielding it. The sub-trades actually do the work they claim — pooling risk, discovering price, smoothing volatility, transferring liquidity to where it's needed. The economy is deep and folded, and that depth is partially earned. The simulation surfaces the productive-vs-parasitic split: how much of a fractal economy's headline output is real, and how much is structurally inseparable from theatre even when the theatre is unusually well-staged and convincing.",
    "casino_collapse": "All the conditions are wrong at once. The economy folds aggressively, but the agents lack the capability to extract real value from the layering. The 'productive' sub-trades fail to be productive — they devolve into pure speculation, with each tier amplifying the noise of the one below it. Activity is high, accounting volumes are large, and welfare collapses. The economy looks impressive on paper while quietly converting its underlying capacity into churn, and the casino floor never closes long enough to count the losses.",
    "recursive_simulation": "The dial controls itself. Whenever the exo-baroque index rises, α rises further in response — the more fractal the economy gets, the hungrier it becomes for further folding. A positive-feedback loop with no governor. The simulation tracks the take-off, where folding generates enthusiasm for further folding, and the economy lifts off the welfare baseline in a way no exogenous α schedule could engineer. There is no equilibrium to settle into, only acceleration, and no policy lever powerful enough to reverse it once it begins.",
    "baroque_cathedral": "Every transaction is an offering at the foot of a cathedral. A loaf of bread is bought, but the purchase is also packaged into a derivative, hedged, repackaged, audited, attested, indexed — each layer billed and counted as economic activity. The cathedral grows taller; the bread becomes harder to find inside it. National accounts soar; most of the activity humans cannot audit. The official numbers describe a flourishing economy that almost no one can locate, and certainly no one can eat.",
    "baroque_cathedral_networked": "The same fractal-trade limit, but with the wiring of a real economy: community-block topology where dense local clusters trade among themselves; heavy-tailed shocks that propagate along high-traffic edges; self-exciting cascades where each large trade triggers more nearby ones. The simulation tests whether the cathedral remains intact under realistic network turbulence, or whether the depth of folding makes it especially fragile to the kind of shocks the smooth attractor would absorb without anyone outside the affected cluster ever noticing.",
    "fold_avalanche": "The simulation begins in something close to a Coasean paradise and ends in a baroque cathedral. The model schedules α from zero to one over the run and watches the tipping dynamics: how quickly a direct-trade economy folds once the ceiling on sub-trade depth comes off, whether the transition is smooth or punctuated, and which diagnostic — welfare, EBI, or the sub-market count — registers the avalanche first. It is the unwinding of Smoothing Cascade run forward instead of backward.",
    "exo_baroque_singularity": "The depth limit on sub-trades has been removed entirely. Folding compounds without ceiling. The asymptote is whatever an unbounded fractal market converges to when nothing caps the recursion. The simulation watches the system stretch toward that limit: nominal GDP runs away from real welfare in orders of magnitude, the exo-baroque index goes vertical, and almost the entire economy collapses into accounting humans can no longer read or audit at any scale, leaving only the residual trace of what the original trade was once supposed to be.",
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


def get_scenario(name: str) -> WorldConfig:
    if name not in SCENARIOS:
        raise KeyError(f"Unknown scenario {name!r}. Available: {list(SCENARIOS)}")
    return SCENARIOS[name]()


def list_scenarios() -> list[tuple[str, str]]:
    return [(k, SCENARIO_DESCRIPTIONS[k]) for k in SCENARIOS]

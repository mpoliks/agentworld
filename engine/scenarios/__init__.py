"""
Scenarios — 15 parameterizations of the smooth-striated continuum.

Each scenario returns a fully-formed `WorldConfig`. All are inspired by a
specific position in the conceptual brief; cite the brief when adding new ones.

Usage:
    from engine.scenarios import SCENARIOS, get_scenario
    cfg = get_scenario("coasean_paradise")
    world = World.build(cfg)
    world.run(progress=True)

The 15 scenarios:
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
"""

from __future__ import annotations

from typing import Callable, Dict

import numpy as np

from engine.core.population import PopulationConfig
from engine.core.topology import TopologyConfig
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
        n_steps=60,
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
        n_steps=60,
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
    n_steps = 80
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
    n_steps = 80
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
        n_steps=60,
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
    n_steps = 60
    floor_schedule = list(
        np.concatenate([
            np.full(20, 1e-4),
            np.linspace(1e-4, 5e-2, 20),
            np.full(20, 5e-2),
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
        n_steps=60,
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
        n_steps=60,
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
        n_steps=60,
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
        n_steps=60,
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
        n_steps=60,
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
        n_steps=60,
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
    n_steps = 80
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
        n_steps=60,
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
        ),
        pairs_per_step=200_000,
        n_steps=60,
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
        ),
        n_steps=60,
        seed=17,
    )


# ---------- registry ----------------------------------------------------------

SCENARIOS: Dict[str, Callable[[], WorldConfig]] = {
    "coasean_paradise": coasean_paradise,
    "baroque_cathedral": baroque_cathedral,
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
}


SCENARIO_DESCRIPTIONS = {
    "coasean_paradise": "Smoothworld limit. Near-zero transaction cost; folding suppressed; EBI ≈ 1.",
    "baroque_cathedral": "Baroqueworld limit. Aggressive folding; nominal GDP explodes; legibility crashes.",
    "equilibrium_drift": "α=0.5 mid-fence. Both attractors pull; sensitivity to noise.",
    "smoothing_cascade": "Coasean transition: α decays 1→0. Nominal collapse, real growth.",
    "fold_avalanche": "Striated drift: α ramps 0→1. Folding take-off and legibility crash.",
    "hemispherical_schism": "Multipolar stacks; cross-stack friction is severe.",
    "compute_famine": "Friction floor rises mid-run. Compute scarcity hits the marginal trade.",
    "universal_advocate": "Krier's high-capability advocate everywhere; smooth tilt with equity.",
    "synthetic_consumers": "Agent-to-agent dominance; humans become a small minority of activity.",
    "nimby_cascade": "Alignment-layer NIMBYism at scale; Coasean clearance undone.",
    "slop_market": "High α + low capability; folding without quality; EBI explodes.",
    "public_defender": "Voucher-style capability uplift; Gini compression intervention.",
    "matryoshka_collapse": "Market + individual layers gate-keep; most surplus dies in filters.",
    "recursive_simulation": "α responds to EBI; positive-feedback Baroque take-off.",
    "exo_baroque_singularity": "Recursive fold limits unlocked; tests asymptotic behavior.",
    "coasean_paradise_networked": "Smooth attractor under scale-free network + t-copula + Hawkes folding.",
    "baroque_cathedral_networked": "Baroque attractor under SBM network + t-copula + Hawkes folding.",
}


def get_scenario(name: str) -> WorldConfig:
    if name not in SCENARIOS:
        raise KeyError(f"Unknown scenario {name!r}. Available: {list(SCENARIOS)}")
    return SCENARIOS[name]()


def list_scenarios() -> list[tuple[str, str]]:
    return [(k, SCENARIO_DESCRIPTIONS[k]) for k in SCENARIOS]

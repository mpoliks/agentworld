"""
Exo scenarios — eleven scenarios calibrated to the Poliks/Trillo theory.

Each scenario corresponds to a specific claim or stress test:

    fold_cathedral       : default exo regime; capital lifts unhindered.
    pure_lift            : even less drag/suppression; tests the asymptote.
    combine_state        : universal differential suppression; tests its cost.
    drag_saturation      : drag intensity maxed out; tests the wedge.
    last_mile_revolt     : physical capacity collapses; tests last-mile binding.
    scavenger_republic   : state collapses to violence consumer; lift unsupervised.
    anxiety_dampener     : ADAPTIVE Coasean dampener; rises with welfare pain.
    hemispherical_split  : low cross-region compatibility; tests stack balkanisation.
    imperial_inheritance : strong tract heterogeneity; non-coextension dominates.
    last_mile_extracted  : high tract extraction rate; meatspace as revenue stream.
    tract_realignment    : attractor schedule flips mid-run; new empire forms.

The exo position is that *all of these are reachable*, that the so-called
Coasean Paradise requires Combine-state-grade suppression to maintain, and
that Bratton's fold attractor is the default the system gravitates to in
the absence of intervention.
"""

from __future__ import annotations

from typing import Callable, Dict

import numpy as np

from engine.exo.config import (
    DifferentialConfig,
    DragConfig,
    ExoWorldConfig,
    ImperialConfig,
    LastMileConfig,
    RegionConfig,
    StackConfig,
)


def fold_cathedral() -> ExoWorldConfig:
    """The default exo regime: capital lifts continuously, drag opens fresh
    surfaces, differentials spawn freely. The system goes Baroque without
    any single agent intending it to.
    """
    return ExoWorldConfig(
        stack=StackConfig(n_layers=8, base_lift_propensity=0.45, fractal_branching=2.6),
        drag=DragConfig(target_intensity=0.40),
        differential=DifferentialConfig(suppression_strength=0.20),
        last_mile=LastMileConfig(),
        region=RegionConfig(n_regions=12),
        n_steps=80,
        seed=101,
    )


def pure_lift() -> ExoWorldConfig:
    """Asymptote scenario: minimal drag and suppression, what does pure lift
    look like? The state effectively absent. Tests the *upper bound* of the
    nominal-vs-real divergence with current branching.
    """
    return ExoWorldConfig(
        stack=StackConfig(
            n_layers=10,
            base_lift_propensity=0.55,
            fractal_branching=2.9,
            nominal_multiplier=2.0,
        ),
        drag=DragConfig(target_intensity=0.10),
        differential=DifferentialConfig(suppression_strength=0.05),
        last_mile=LastMileConfig(gore_layer_violence=0.015),
        region=RegionConfig(n_regions=10),
        n_steps=80,
        seed=102,
    )


def combine_state() -> ExoWorldConfig:
    """Universal differential suppression — the Half-Life-2 Combine state.
    Cost-of-suppression rises convexly. Test: how much real welfare is
    consumed by sustaining the suppression apparatus?
    """
    return ExoWorldConfig(
        stack=StackConfig(),
        drag=DragConfig(target_intensity=0.60),
        differential=DifferentialConfig(
            suppression_strength=0.92,
            suppression_cost_exp=2.4,
            suppression_welfare_cost=0.085,
        ),
        last_mile=LastMileConfig(),
        region=RegionConfig(n_regions=12),
        n_steps=80,
        seed=103,
    )


def drag_saturation() -> ExoWorldConfig:
    """Drag intensity at the saturation ceiling for the whole run. Tests
    how much real welfare gets sunk into producing legibility. State and
    white-collar labor as the dominant economic activity.
    """
    return ExoWorldConfig(
        stack=StackConfig(),
        drag=DragConfig(
            target_intensity=0.88,
            welfare_cost_per_token=0.022,
            tokens_to_lift_propensity=1.6,
        ),
        differential=DifferentialConfig(suppression_strength=0.45),
        last_mile=LastMileConfig(),
        region=RegionConfig(n_regions=12),
        n_steps=80,
        seed=104,
    )


def last_mile_revolt() -> ExoWorldConfig:
    """Physical capacity collapses mid-run. Energy crisis, climate event,
    chip war. Tests how much of the lifted economy persists when its
    last-mile feedstock breaks.
    """
    n = 80
    schedule = list(np.concatenate([
        np.full(20, 1.0),
        np.linspace(1.0, 0.35, 20),
        np.full(40, 0.35),
    ]))
    return ExoWorldConfig(
        stack=StackConfig(),
        drag=DragConfig(target_intensity=0.45),
        differential=DifferentialConfig(suppression_strength=0.30),
        last_mile=LastMileConfig(gore_layer_violence=0.05),
        region=RegionConfig(n_regions=12),
        physical_capacity_schedule=schedule,
        n_steps=n,
        seed=105,
    )


def scavenger_republic() -> ExoWorldConfig:
    """State collapses to a violence consumer. Drag low, suppression nearly
    zero, gore-layer violence high. The exo claim: lift continues anyway
    because capital does not depend on state-organised legibility.
    """
    return ExoWorldConfig(
        stack=StackConfig(base_lift_propensity=0.50),
        drag=DragConfig(target_intensity=0.18),
        differential=DifferentialConfig(suppression_strength=0.05),
        last_mile=LastMileConfig(gore_layer_violence=0.10),
        region=RegionConfig(n_regions=14, cross_region_compat=0.45),
        n_steps=80,
        seed=106,
    )


def anxiety_dampener() -> ExoWorldConfig:
    """Coasean optimism deployed as drag-with-adaptive-dampener — the agent
    layer is *recruited as palliative care*. The dampener level rises in
    each polity as that polity's per-capita welfare drops below a target.

    This tests the strongest version of the exo claim about Krier-style
    Coasean bargaining at scale: that as material suffering becomes
    visible, the response is to deploy more agents to consume the visible
    suffering as drag, rather than to rebuild last-mile capacity. The
    feedback loop is intentional. If the dampener helps, welfare recovers
    and the dampener falls back; if it doesn't, welfare drops further and
    the dampener climbs to its cap. Either way the loop is observable.

    Imperial extraction is enabled at default rates so the dampener has
    real-side pressure to respond to.
    """
    return ExoWorldConfig(
        stack=StackConfig(),
        drag=DragConfig(
            target_intensity=0.60,
            coasean_dampener=0.05,
            adaptive_dampener=True,
            adaptive_welfare_target=0.55,
            adaptive_dampener_sensitivity=1.6,
            adaptive_dampener_max=0.85,
            adaptive_dampener_inertia=0.72,
        ),
        differential=DifferentialConfig(suppression_strength=0.40),
        last_mile=LastMileConfig(),
        region=RegionConfig(n_regions=12),
        imperial=ImperialConfig(
            n_tracts=4,
            extraction_rate=0.10,
            historical_violence_floor=0.020,
            seed=7777,
        ),
        n_steps=80,
        seed=107,
    )


def hemispherical_split() -> ExoWorldConfig:
    """Bratton's hemispherical stacks pulled into the exo frame: low
    cross-region compatibility. Lift continues per region, but capital can't
    pool across regions, so the lifted economy fragments.
    """
    return ExoWorldConfig(
        stack=StackConfig(),
        drag=DragConfig(target_intensity=0.40),
        differential=DifferentialConfig(suppression_strength=0.25),
        last_mile=LastMileConfig(),
        region=RegionConfig(n_regions=16, cross_region_compat=0.18),
        n_steps=80,
        seed=108,
    )


def imperial_inheritance() -> ExoWorldConfig:
    """Strong tract heterogeneity. Polities are not coextensive with
    capital regions: a few attractor tracts pool capital while the
    polities mapped to extracted tracts inherit chronic violence and
    drained welfare. Tests the exo claim that imperial geography
    persists *underneath* nation-state governance.
    """
    return ExoWorldConfig(
        stack=StackConfig(),
        drag=DragConfig(target_intensity=0.42),
        differential=DifferentialConfig(suppression_strength=0.30),
        last_mile=LastMileConfig(gore_layer_violence=0.012),
        region=RegionConfig(n_regions=16, cross_region_compat=0.55),
        imperial=ImperialConfig(
            n_tracts=5,
            tract_resource_dirichlet=0.7,  # very uneven endowments
            tract_attractor_dirichlet=0.7,  # very concentrated attractor strengths
            extraction_rate=0.08,
            historical_violence_floor=0.025,
            capital_pooling_strength=0.30,
            pool_layers=4,
            seed=4242,
        ),
        n_steps=80,
        seed=109,
    )


def last_mile_extracted() -> ExoWorldConfig:
    """High imperial extraction: 18% of last-mile real welfare per step is
    extracted upward into the lifted economy. Models the meatspace-as-revenue
    pattern (resource colonies, data farms, ad-attention pipelines) under
    ordinary polity governance.

    The exo claim being tested: extraction can run high without polity-level
    suppression rising; nation-states do not legislate this layer because it
    operates above their scale.
    """
    return ExoWorldConfig(
        stack=StackConfig(n_layers=9),
        drag=DragConfig(target_intensity=0.45),
        differential=DifferentialConfig(suppression_strength=0.25),
        last_mile=LastMileConfig(),
        region=RegionConfig(n_regions=14, cross_region_compat=0.50),
        imperial=ImperialConfig(
            n_tracts=4,
            extraction_rate=0.18,
            historical_violence_floor=0.030,
            capital_pooling_strength=0.28,
            pool_layers=3,
            seed=5151,
        ),
        n_steps=80,
        seed=110,
    )


def tract_realignment() -> ExoWorldConfig:
    """Attractor strengths shift mid-run, modeling resource discovery,
    climate-shifted resource viability, or AI-hardware concentration. Tests
    whether capital reorganises around the new attractor map and whether
    polities aligned with the *old* tract get stranded.

    The schedule rotates attractor strengths after step 30 and again after
    step 55. Pool layers are deep so the rotation has somewhere to land.
    """
    n_tracts = 5
    n = 80
    base = np.array([0.6, 1.4, 0.8, 1.5, 0.7])
    new1 = np.array([1.6, 0.5, 1.3, 0.4, 1.2])
    new2 = np.array([0.4, 0.4, 1.5, 1.7, 1.0])
    schedule: list = []
    for t in range(n):
        if t < 30:
            schedule.append(None)
        elif t == 30:
            schedule.append(new1.tolist())
        elif t == 55:
            schedule.append(new2.tolist())
        else:
            schedule.append(None)

    return ExoWorldConfig(
        stack=StackConfig(n_layers=9),
        drag=DragConfig(target_intensity=0.42),
        differential=DifferentialConfig(suppression_strength=0.25),
        last_mile=LastMileConfig(),
        region=RegionConfig(n_regions=15, cross_region_compat=0.50),
        imperial=ImperialConfig(
            n_tracts=n_tracts,
            tract_resource_dirichlet=1.0,
            tract_attractor_dirichlet=1.0,
            extraction_rate=0.10,
            historical_violence_floor=0.020,
            capital_pooling_strength=0.30,
            pool_layers=4,
            attractor_schedule=schedule,
            seed=6363,
        ),
        n_steps=n,
        seed=111,
    )


SCENARIOS: Dict[str, Callable[[], ExoWorldConfig]] = {
    "fold_cathedral": fold_cathedral,
    "pure_lift": pure_lift,
    "combine_state": combine_state,
    "drag_saturation": drag_saturation,
    "last_mile_revolt": last_mile_revolt,
    "scavenger_republic": scavenger_republic,
    "anxiety_dampener": anxiety_dampener,
    "hemispherical_split": hemispherical_split,
    "imperial_inheritance": imperial_inheritance,
    "last_mile_extracted": last_mile_extracted,
    "tract_realignment": tract_realignment,
}


SCENARIO_DESCRIPTIONS = {
    "fold_cathedral": "Default exo regime — capital lifts continuously; SaaS-on-SaaS goes Baroque.",
    "pure_lift": "Asymptote: minimal drag/suppression; tests the upper bound of nominal divergence.",
    "combine_state": "Universal differential suppression — measure the welfare cost of policing the market.",
    "drag_saturation": "Drag at ceiling — measure how much welfare is sunk into producing legibility.",
    "last_mile_revolt": "Physical capacity collapse mid-run — does the lifted economy persist?",
    "scavenger_republic": "State as random violence consumer — lift continues without state-grade legibility.",
    "anxiety_dampener": "Adaptive Coasean dampener rises with welfare pain — palliative-care mode test.",
    "hemispherical_split": "Hemispherical stacks pulled into exo frame — capital fragments across regions.",
    "imperial_inheritance": "Heavy tract heterogeneity — non-coextension dominates polity governance.",
    "last_mile_extracted": "High imperial extraction — meatspace as revenue stream, no polity intervention.",
    "tract_realignment": "Attractor schedule flips mid-run — new empire forms; polities stranded or rewarded.",
}


def get_scenario(name: str) -> ExoWorldConfig:
    if name not in SCENARIOS:
        raise KeyError(f"Unknown exo scenario {name!r}. Available: {list(SCENARIOS)}")
    return SCENARIOS[name]()


def list_scenarios() -> list[tuple[str, str]]:
    return [(k, SCENARIO_DESCRIPTIONS[k]) for k in SCENARIOS]

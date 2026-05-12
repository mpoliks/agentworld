"""
Scenario families — taxonomy used by the live-engine UI.

The 40 canonical scenarios decompose into seven families along structural-
toggle lines. Families are chosen *before* a run starts (they change which
engine modules are active, not just parameter values), so the live UI
presents them as a radio group above the parameter panel.

See `docs/concepts/live_parameters.md` § "Scenario families" for the
narrative description of each family.

The `_anchored` variants of base scenarios (substrate-wrapped: SBM network
+ t-copula noise + Hawkes folding) inherit the family of their base.
"""

from __future__ import annotations

from typing import Iterable


# ---- The seven families ----------------------------------------------------

FAMILY_IDS: tuple[str, ...] = (
    "alpha_baseline",
    "demand_intermediation",
    "dynamic_law",
    "pigouvian",
    "emergent_strategy",
    "mission_economy",
    "norms_layer",
)


FAMILY_METADATA: dict[str, dict] = {
    "alpha_baseline": {
        "id": "alpha_baseline",
        "label": "Alpha-engine baseline",
        "description": (
            "The original alpha-engine. No demand-side feedback, no "
            "productive-folding split, no dynamic law, no Pigouvian tax, "
            "no strategy/institutions/mission/norms layers. Includes the "
            "two networked variants."
        ),
        "structural_switches": [],
    },
    "demand_intermediation": {
        "id": "demand_intermediation",
        "label": "Demand & intermediation",
        "description": (
            "Demand-side weighting on (`demand.enabled = True`) and/or "
            "productive-folding split active (`base_variance_absorption > 0`). "
            "Separates nominal accounting from welfare reaching humans, and "
            "splits fold output into productive vs parasitic shares."
        ),
        "structural_switches": ["demand.enabled", "base_variance_absorption > 0"],
    },
    "dynamic_law": {
        "id": "dynamic_law",
        "label": "Dynamic law",
        "description": (
            "Law strength evolves over the run (`law.enabled = True`). "
            "Capture, decay, and civic-renewal mechanisms run; rejection "
            "probability tracks the law trajectory."
        ),
        "structural_switches": ["law.enabled"],
    },
    "pigouvian": {
        "id": "pigouvian",
        "label": "Pigouvian automation",
        "description": (
            "Per-pair A2A tax on nominal volume, recycled either to human "
            "wealth or as an H2A friction subsidy (`pigouvian.enabled = True`)."
        ),
        "structural_switches": ["pigouvian.enabled"],
    },
    "emergent_strategy": {
        "id": "emergent_strategy",
        "label": "Emergent strategy / institutions",
        "description": (
            "Agents learn intermediation preference (`strategy.enabled`), "
            "firms form and dissolve (`institutions.enabled`), populations "
            "churn (`pop_dynamics.enabled`), and fold pressure compounds "
            "(`folding_pressure_feedback`)."
        ),
        "structural_switches": [
            "strategy.enabled",
            "institutions.enabled",
            "pop_dynamics.enabled",
        ],
    },
    "mission_economy": {
        "id": "mission_economy",
        "label": "Mission economy",
        "description": (
            "Coordinator-sector capability uplift funded by a real-surplus "
            "levy (`mission.enabled = True`). Tomašev / Jacobs's third lever."
        ),
        "structural_switches": ["mission.enabled"],
    },
    "norms_layer": {
        "id": "norms_layer",
        "label": "Norms layer",
        "description": (
            "Alignment as participation rather than static distance "
            "(`norms.enabled = True`). Norms drift, capture, or oscillate "
            "depending on update rate and initial distribution."
        ),
        "structural_switches": ["norms.enabled"],
    },
}


# ---- Scenario → family mapping --------------------------------------------
#
# Curated. The implicit family is inspectable from a `WorldConfig` by reading
# the relevant `*.enabled` flags, but the mapping is hand-maintained because:
# (a) a scenario can structurally activate switches outside its conceptual
#     family (the endogenous wrappers add fold-pressure + institutions on
#     top of demand/Pigouvian scenarios), and the conceptual family is the
#     one the user cares about; and
# (b) the mapping is what the dashboard already documents in
#     `engine/scenarios/__init__.py`'s module docstring.

_BASE_SCENARIO_FAMILIES: dict[str, str] = {
    # Alpha-engine baseline (1-17 + the post-33 baroque_with_high_welfare)
    "coasean_paradise": "alpha_baseline",
    "baroque_cathedral": "alpha_baseline",
    "baroque_with_high_welfare": "alpha_baseline",
    "equilibrium_drift": "alpha_baseline",
    "smoothing_cascade": "alpha_baseline",
    "fold_avalanche": "alpha_baseline",
    "hemispherical_schism": "alpha_baseline",
    "compute_famine": "alpha_baseline",
    "universal_advocate": "alpha_baseline",
    "synthetic_consumers": "alpha_baseline",
    "nimby_cascade": "alpha_baseline",
    "slop_market": "alpha_baseline",
    "public_defender": "alpha_baseline",
    "matryoshka_collapse": "alpha_baseline",
    "recursive_simulation": "alpha_baseline",
    "exo_baroque_singularity": "alpha_baseline",
    "coasean_paradise_networked": "alpha_baseline",
    "baroque_cathedral_networked": "alpha_baseline",
    # Demand & intermediation (18-22)
    "synthetic_consumers_v2": "demand_intermediation",
    "agentic_disconnect": "demand_intermediation",
    "productive_baroque": "demand_intermediation",
    "derivatives_revolution": "demand_intermediation",
    "casino_collapse": "demand_intermediation",
    # Dynamic law (23-25)
    "legal_collapse": "dynamic_law",
    "regulatory_capture": "dynamic_law",
    "civic_renaissance": "dynamic_law",
    # Pigouvian (26-29)
    "pigouvian_light": "pigouvian",
    "pigouvian_heavy": "pigouvian",
    "pigouvian_friction": "pigouvian",
    "pigouvian_baroque": "pigouvian",
    # Emergent strategy / institutions (30-33)
    "endogenous_paradise": "emergent_strategy",
    "endogenous_baroque": "emergent_strategy",
    "institutional_emergence": "emergent_strategy",
    "full_emergence": "emergent_strategy",
    # Mission economy (34-36)
    "mission_economy": "mission_economy",
    "mission_captured": "mission_economy",
    "mission_competing": "mission_economy",
    # Norms layer (37-39)
    "norms_drift": "norms_layer",
    "norms_capture": "norms_layer",
    "norms_brittle": "norms_layer",
}


_ANCHORED_SUFFIX = "_anchored"


def family_for(scenario_name: str) -> str:
    """Return the family id for a scenario name.

    `_anchored` variants inherit the base scenario's family. Raises KeyError
    if the scenario name is not in the registered mapping.
    """
    if scenario_name in _BASE_SCENARIO_FAMILIES:
        return _BASE_SCENARIO_FAMILIES[scenario_name]
    if scenario_name.endswith(_ANCHORED_SUFFIX):
        base = scenario_name[: -len(_ANCHORED_SUFFIX)]
        if base in _BASE_SCENARIO_FAMILIES:
            return _BASE_SCENARIO_FAMILIES[base]
    raise KeyError(f"no family registered for scenario {scenario_name!r}")


def scenarios_in_family(family_id: str, all_scenarios: Iterable[str]) -> list[str]:
    """Return the subset of `all_scenarios` belonging to `family_id`,
    preserving the input ordering. Skips scenarios with no registered family.
    """
    out: list[str] = []
    for name in all_scenarios:
        try:
            if family_for(name) == family_id:
                out.append(name)
        except KeyError:
            continue
    return out


def all_families() -> list[dict]:
    """Return family metadata in canonical order. Each dict carries id,
    label, description, and structural_switches. The list of scenarios per
    family is populated by `families_with_scenarios` since that requires
    the live SCENARIOS registry.
    """
    return [FAMILY_METADATA[fid] for fid in FAMILY_IDS]


def families_with_scenarios(all_scenarios: Iterable[str]) -> list[dict]:
    """Return family metadata with the scenarios-in-family list attached."""
    scenarios = list(all_scenarios)
    return [
        {
            **FAMILY_METADATA[fid],
            "scenarios": scenarios_in_family(fid, scenarios),
        }
        for fid in FAMILY_IDS
    ]

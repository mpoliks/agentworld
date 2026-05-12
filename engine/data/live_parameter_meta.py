"""
Live-engine parameter metadata.

Single source of truth for the eight numeric parameters the live UI exposes
plus their gloss strings. Synced with `docs/concepts/live_parameters.md` —
the doc is the human-facing version, this module is what the API serves.

If a parameter is added or modified, update both this module and the
concept doc. A future refinement is to parse the markdown at startup;
until that lands, this module is the canonical machine-readable copy.

Bounds match the N=2048 Sobol problem in
`outputs/sensitivity/sobol_indices.n2048.json`.
"""

from __future__ import annotations


# Where each parameter lives on the WorldConfig tree. Used by the override
# applicator in `engine.serve` to decide which sub-config to patch.
#
# Values: "topology" → cfg.topology, "population" → cfg.population.
# Family-specific knobs (law.decay_rate, pigouvian.tau, etc.) are handled
# by a parallel registry in `family_parameter_paths` below.
LIVE_PARAMETER_PATHS: dict[str, str] = {
    "alpha": "topology",
    "agent_capability_mean": "population",
    "folding_propensity": "topology",
    "base_variance_absorption": "topology",
    "folding_branching": "topology",
    "base_friction": "topology",
    "max_productive_real_share": "topology",
    "fold_nominal_multiplier": "topology",
}


# Tier-1/Tier-2 numeric parameters, ranked by mean |ST| across the six
# Sobol headline metrics. Each record matches the three-layer schema in
# `docs/concepts/live_parameters.md`.
LIVE_PARAMETERS: tuple[dict, ...] = (
    {
        "name": "alpha",
        "label": "Smooth ↔ baroque (α)",
        "path": "topology",
        "default": 0.5,
        "sobol_min": 0.05,
        "sobol_max": 0.95,
        "mean_abs_st": 0.40,
        "tier": 1,
        "tooltip": "Krier–Bratton axis. 0 = no folding, no striation; 1 = aggressive recursive folding.",
        "help": (
            "The engine's primary control variable. Most other parameters "
            "scale off α: folding rate as α^1.4, branching as (0.6 + 0.4·α), "
            "striation cost as α · 0.020 · (1 + 0.3·(1 − cross_stack_compat)). "
            "The slider stays inside (0, 1) because the corners produce "
            "degenerate runs."
        ),
    },
    {
        "name": "agent_capability_mean",
        "label": "Agent competence (μ)",
        "path": "population",
        "default": 0.72,
        "sobol_min": 0.45,
        "sobol_max": 0.92,
        "mean_abs_st": 0.37,
        "tier": 1,
        "tooltip": "Mean of the normal that agents are drawn from; lowers Coasean friction.",
        "help": (
            "Agents are drawn N(μ, agent_capability_sd) with default sd = 0.20. "
            "Humans are drawn N(0.45, 0.18). Capability enters friction as "
            "friction_floor + base_friction × (1 − capability)^coase_exp. The "
            "lower bound 0.45 matches the human baseline; the upper bound 0.92 "
            "is the Sobol-box ceiling, not a physical cap."
        ),
    },
    {
        "name": "folding_propensity",
        "label": "Fold trigger rate (at α=1)",
        "path": "topology",
        "default": 0.55,
        "sobol_min": 0.05,
        "sobol_max": 0.75,
        "mean_abs_st": 0.25,
        "tier": 1,
        "tooltip": "Probability that a positive-surplus transaction spawns a sub-market, evaluated at α=1.",
        "help": (
            "Realised propensity scales as folding_propensity × α^1.4. At "
            "α = 0.5 the realised rate is roughly 38% of the slider value. "
            "With folding_pressure_feedback enabled, the rate is also "
            "multiplied by 1 + strength × max(0, pressure − anchor), capped "
            "at max_multiplier, where pressure is the cumulative EBI excess."
        ),
    },
    {
        "name": "base_variance_absorption",
        "label": "Productive-fold share (depth 1)",
        "path": "topology",
        "default": 0.0,
        "sobol_min": 0.0,
        "sobol_max": 0.6,
        "mean_abs_st": 0.17,
        "tier": 1,
        "tooltip": "Real-welfare contribution per fold at depth 1 and max capability. Zero ⇒ folding is purely parasitic.",
        "help": (
            "When > 0, a fold contributes real welfare scaled by intermediator "
            "capability through a sigmoid around cap_midpoint = 0.5 with "
            "sharpness cap_slope = 4.0. Welfare decays per layer as "
            "absorption × productive_decay^(d−1) with productive_decay = 0.65. "
            "Legacy alpha-engine scenarios run with this at zero; the demand-"
            "and-intermediation scenarios (18–22) opt in."
        ),
        "couples_with": "max_productive_real_share",
    },
    {
        "name": "folding_branching",
        "label": "Children per fold",
        "path": "topology",
        "default": 2.7,
        "sobol_min": 1.6,
        "sobol_max": 3.4,
        "mean_abs_st": 0.07,
        "tier": 2,
        "tooltip": "Average sub-markets spawned per parent fold (at α=1).",
        "help": (
            "Realised branching is folding_branching × (0.6 + 0.4·α). The "
            "Sobol bounds bracket the empirical Hawkes branching ratio in "
            "financial cascade studies (Bacry–Muzy 2015). The optional "
            "Hawkes folding model preserves the closed-form mean at the "
            "same value."
        ),
    },
    {
        "name": "base_friction",
        "label": "Coasean friction (at capability=0)",
        "path": "topology",
        "default": 0.05,
        "sobol_min": 0.02,
        "sobol_max": 0.08,
        "mean_abs_st": 0.07,
        "tier": 2,
        "tooltip": "Per-transaction friction at zero capability. Realistic capabilities pay much less.",
        "help": (
            "Full friction is friction_floor + base_friction × "
            "(1 − capability)^coase_exp + α × 0.020 × "
            "(1 + 0.3·(1 − cross_stack_compat)). At default capability 0.72 "
            "and coase_exp = 1.7, an agent pays roughly 12% of base_friction."
        ),
    },
    {
        "name": "max_productive_real_share",
        "label": "Productive-fold ceiling",
        "path": "topology",
        "default": 0.6,
        "sobol_min": 0.2,
        "sobol_max": 0.8,
        "mean_abs_st": 0.05,
        "tier": 2,
        "tooltip": "Caps productive-fold welfare at this fraction of the underlying real surplus. Inert when productive folding is off.",
        "help": (
            "Acts as cap = base_real_surplus × max_productive_real_share. "
            "With base_variance_absorption = 0 the cap never binds — "
            "productive folding is gated off entirely. Inside the productive-"
            "folding scenarios the slider sets how much of the real surplus "
            "the intermediation chain can capture before saturation."
        ),
        "inert_when": "base_variance_absorption == 0",
    },
    {
        "name": "fold_nominal_multiplier",
        "label": "Nominal value-add per fold",
        "path": "topology",
        "default": 1.85,
        "sobol_min": 1.3,
        "sobol_max": 2.2,
        "mean_abs_st": 0.05,
        "tier": 2,
        "tooltip": 'Each fold layer multiplies nominal GDP by this factor. 1.85 ≈ "+85% nominal per layer."',
        "help": (
            "Applied as nominal ← nominal × folding_branching × "
            "fold_nominal_multiplier × depth_prop along the fold chain. The "
            "defining lever for nominal/real divergence — EBI rises chiefly "
            "through this multiplier × branching × depth."
        ),
    },
)


# Quick lookup by name.
LIVE_PARAMETERS_BY_NAME: dict[str, dict] = {p["name"]: p for p in LIVE_PARAMETERS}


def is_within_bounds(name: str, value: float) -> bool:
    """Return True if `value` is inside the Sobol sampling box for `name`."""
    p = LIVE_PARAMETERS_BY_NAME.get(name)
    if p is None:
        return False
    return p["sobol_min"] <= value <= p["sobol_max"]


# Headline metrics the Sobol indices are computed against. Mirrors the
# `metric` field of each entry in `outputs/sensitivity/sobol_indices.n2048.json`.
SOBOL_METRICS: tuple[str, ...] = (
    "log_exo_baroque_index",
    "real_per_capita_welfare",
    "gini_wealth_change_abs",
    "log_exo_baroque_authentic",
    "real_welfare_authentic_cumulative",
    "productive_welfare_yield",
)

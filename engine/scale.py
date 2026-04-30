"""
Scale knob — uniformly grow a WorldConfig by 1x / 10x / 100x / 1000x.

The named scenarios in `engine/scenarios/__init__.py` were authored at
"small" scale (88K prototypes, 200K pairs/step). For the 88K -> 88M
single-laptop scale-up we want to vary that uniformly without rewriting
each scenario.

Each Scale value carries a multiplier that is applied to:
  - PopulationConfig.n_human_prototypes
  - PopulationConfig.n_agent_prototypes
  - WorldConfig.pairs_per_step

Hand-tuned per-scenario ratios are preserved by *multiplying* (not
overriding). For example, `synthetic_consumers` ships with
n_agent_prototypes=120_000 and pairs_per_step=300_000. At medium scale
(10x) those become 1.2M and 3M respectively.

Usage:
    from engine.scale import Scale, apply_scale
    cfg = apply_scale(get_scenario("baroque_cathedral"), Scale.LARGE)
"""

from __future__ import annotations

from dataclasses import replace
from enum import Enum

from engine.core.world import WorldConfig


class Scale(str, Enum):
    """How big to run. SMALL is the historical default (~88K prototypes)."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    XLARGE = "xlarge"

    @property
    def factor(self) -> int:
        return {
            Scale.SMALL: 1,
            Scale.MEDIUM: 10,
            Scale.LARGE: 100,
            Scale.XLARGE: 1000,
        }[self]


def apply_scale(cfg: WorldConfig, scale: Scale | str) -> WorldConfig:
    """Return a copy of `cfg` with population sizes and pairs scaled."""
    if isinstance(scale, str):
        scale = Scale(scale)
    f = scale.factor
    if f == 1:
        return cfg

    new_pop = replace(
        cfg.population,
        n_human_prototypes=cfg.population.n_human_prototypes * f,
        n_agent_prototypes=cfg.population.n_agent_prototypes * f,
    )
    return replace(
        cfg,
        population=new_pop,
        pairs_per_step=cfg.pairs_per_step * f,
    )


def parse_scale(value: str | None) -> Scale:
    """CLI helper: accept None, 'small', 'medium', 'large', 'xlarge'."""
    if value is None:
        return Scale.SMALL
    return Scale(value)

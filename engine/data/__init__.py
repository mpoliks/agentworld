"""
engine.data — empirical anchors for the calibrated noise structure.

See `docs/concepts/epistemic_status.md` for the rules. Anchors here cover
**only** sub-models with public empirical analogs (correlation matrices,
heavy-tail degrees of freedom, network degree exponents, Hawkes branching
ratios). Speculative load-bearing parameters live in their respective
config dataclasses and are *deliberately* not anchored here.
"""

from engine.data.empirical_anchors import (
    BEA_SECTOR_CORR,
    HAWKES_BRANCHING_RATIO,
    HAWKES_DECAY,
    NETWORK_DEGREE_EXPONENT,
    REGION_GROWTH_CORR,
    T_COPULA_DOF_DEFAULT,
    bea_sector_correlation,
    region_growth_correlation,
    spd_clamp,
)

__all__ = [
    "BEA_SECTOR_CORR",
    "HAWKES_BRANCHING_RATIO",
    "HAWKES_DECAY",
    "NETWORK_DEGREE_EXPONENT",
    "REGION_GROWTH_CORR",
    "T_COPULA_DOF_DEFAULT",
    "bea_sector_correlation",
    "region_growth_correlation",
    "spd_clamp",
]

"""
Calibrated noise structure for the alpha-engine and exo-engine.

Two noise models are available everywhere a stochastic shock enters:

    - "gaussian"  : the original IID Gaussian (preserves prior behaviour).
    - "t_copula"  : Student-t marginals coupled across sectors / regions
                    by a Gaussian copula whose correlation matrix comes
                    from `engine/data/empirical_anchors.py`.

Both are variance-matched at default parameters so that swapping does
not silently rescale the engines. The t-copula model upgrades the noise
in two ways:

    1. Heavier tails. Cont (2001) reports kurtosis-implied tail indices
       in the 3-5 range for liquid markets; we default to df=4.
    2. Cross-sector / cross-region co-movement. Sector-level shocks are
       drawn from a multivariate normal with the BEA 2022 input-output
       correlation matrix; per-pair (or per-region) shocks combine the
       systemic component with idiosyncratic noise.

See `docs/concepts/epistemic_status.md` for the rules of what gets
calibrated and what doesn't.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

# Lazy scipy import so the rest of the engine still loads if scipy is gone.
try:
    from scipy import stats as _stats  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    _stats = None

from engine.data.empirical_anchors import (
    BEA_SECTOR_CORR,
    T_COPULA_DOF_DEFAULT,
)


NoiseModel = Literal["gaussian", "t_copula"]


@dataclass
class CopulaState:
    """Cached Cholesky of a correlation matrix for repeated MVN draws."""

    corr: np.ndarray
    chol: np.ndarray
    dof: float

    @classmethod
    def from_corr(cls, corr: np.ndarray, dof: float) -> "CopulaState":
        chol = np.linalg.cholesky(corr)
        return cls(corr=corr, chol=chol, dof=float(dof))


def _t_marginals(uniform: np.ndarray, dof: float) -> np.ndarray:
    """Map uniform-(0,1) values to t-distributed via inverse CDF.

    Variance of a t with df > 2 is df / (df - 2). The caller is responsible
    for rescaling if a target variance is desired.
    """
    if _stats is None:  # pragma: no cover
        # Fall back to standard-normal-equivalent if scipy missing.
        return np.sqrt(2.0) * np.tan(np.pi * (uniform - 0.5))
    return _stats.t.ppf(uniform, df=dof)


def _normal_to_uniform(z: np.ndarray) -> np.ndarray:
    """Map standard-normal to uniform-(0,1) via the standard-normal CDF."""
    if _stats is None:  # pragma: no cover
        return 0.5 * (1.0 + np.tanh(z / np.sqrt(2.0)))
    return _stats.norm.cdf(z)


def per_pair_surplus_shock(
    rng: np.random.Generator,
    n_pairs: int,
    sec_a: np.ndarray,
    *,
    scale: float,
    model: NoiseModel = "gaussian",
    dof: float = T_COPULA_DOF_DEFAULT,
    sector_share: float = 0.4,
    state: CopulaState | None = None,
) -> np.ndarray:
    """Generate per-pair surplus shocks under the chosen noise model.

    Args:
        rng: numpy generator.
        n_pairs: number of pairs.
        sec_a: (n_pairs,) integer sector index per pair.
        scale: target standard deviation (matches the prior `0.05`).
        model: "gaussian" (legacy) or "t_copula".
        dof: heavy-tail degrees of freedom for the t-copula.
        sector_share: variance share allocated to the systemic
            sector-level shock (rest is idiosyncratic). 0 = pure
            idiosyncratic, 1 = pure systemic.
        state: precomputed CopulaState; built from BEA_SECTOR_CORR if None.

    Returns:
        (n_pairs,) shock array with sample variance approximately scale**2.
    """
    if model == "gaussian" or n_pairs <= 0:
        return scale * rng.standard_normal(n_pairs)

    if state is None:
        state = CopulaState.from_corr(BEA_SECTOR_CORR, dof=dof)

    n_sectors = state.corr.shape[0]
    rho = float(np.clip(sector_share, 0.0, 1.0))
    a = np.sqrt(rho)
    b = np.sqrt(1.0 - rho)

    # Systemic component: ONE n_sectors-vector per step, correlated via BEA.
    z_sec = state.chol @ rng.standard_normal(n_sectors)
    # Idiosyncratic component: standard normal per pair.
    eps = rng.standard_normal(n_pairs)
    # Combine: u_p = a * z_sec[sec_a[p]] + b * eps[p] ~ N(0,1) marginally.
    u = a * z_sec[sec_a] + b * eps

    # Convert to uniform, then to t to inject heavy tails. Variance of t(df) is
    # df / (df - 2); rescale so the realized variance matches `scale**2`.
    uniform = _normal_to_uniform(u)
    # Numerical safety for the inverse-CDF tails.
    uniform = np.clip(uniform, 1e-10, 1.0 - 1e-10)
    t_draws = _t_marginals(uniform, state.dof)

    if state.dof > 2:
        target_std = scale
        t_std = np.sqrt(state.dof / (state.dof - 2.0))
        rescale = target_std / t_std
    else:  # pragma: no cover
        rescale = scale
    return rescale * t_draws


def per_region_shock(
    rng: np.random.Generator,
    n_regions: int,
    *,
    scale: float,
    model: NoiseModel = "gaussian",
    dof: float = T_COPULA_DOF_DEFAULT,
    state: CopulaState | None = None,
) -> np.ndarray:
    """Generate per-region shocks under the chosen noise model.

    Args:
        rng: numpy generator.
        n_regions: number of regions.
        scale: target standard deviation per region.
        model: "gaussian" (legacy) or "t_copula".
        dof: heavy-tail degrees of freedom.
        state: precomputed CopulaState. If None, the caller must pass one
            (we don't auto-build because the region count varies by
            scenario, and rebuilding the Cholesky every step is wasteful).

    Returns:
        (n_regions,) shock array with sample variance approximately scale**2.
    """
    if model == "gaussian" or n_regions <= 0:
        return scale * rng.standard_normal(n_regions)

    if state is None:
        raise ValueError(
            "per_region_shock(model='t_copula') requires a CopulaState; "
            "build it once with CopulaState.from_corr(region_growth_correlation(n_regions), dof)."
        )

    z = state.chol @ rng.standard_normal(n_regions)
    uniform = np.clip(_normal_to_uniform(z), 1e-10, 1.0 - 1e-10)
    t_draws = _t_marginals(uniform, state.dof)

    if state.dof > 2:
        rescale = scale / np.sqrt(state.dof / (state.dof - 2.0))
    else:  # pragma: no cover
        rescale = scale
    return rescale * t_draws


__all__ = [
    "NoiseModel",
    "CopulaState",
    "per_pair_surplus_shock",
    "per_region_shock",
]

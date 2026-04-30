"""
Empirical anchors for the calibrated noise structure.

Every constant in this file:
    1. Has a public empirical analog of the *mechanism* being modeled
       (not the macro output of the engine).
    2. Cites its source, year, and scope in a docstring.
    3. Carries a `vintage` year so a future re-anchor pass can find it.
    4. Is small enough to inline as a Python literal — we do not pull
       data files at runtime.

These anchors are *only* used to calibrate the structure of stochastic
sub-models (sectoral noise correlations, regional noise correlations,
network degree distributions, Hawkes branching ratios, heavy-tail
degrees of freedom). They are deliberately *not* used to calibrate the
load-bearing speculative parameters (folding propensity, fold-real
efficiency, lift propensity, suppression cost exponent, etc.). See
`docs/concepts/epistemic_status.md` for the rules.

If you re-anchor this file from updated public sources, bump the
`vintage` field and rerun the dashboard to see if any scenario
classification flips under the new noise structure.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.core.population import N_SECTORS, SECTOR_NAMES


# =============================================================================
# Heavy-tail degrees of freedom for the t-copula
# =============================================================================
#
# Source: Cont, R. (2001). "Empirical properties of asset returns: stylized
# facts and statistical issues", Quantitative Finance 1, 223-236. Reports
# kurtosis-implied tail indices for daily returns in the 3-5 range across
# equity, FX, and commodity markets.
#
# Vintage: 2001 (stylized fact, stable across decades).
# Scope: Daily-return distributions in liquid markets. Used here as the
# default heavy-tail shape for per-pair / per-region transaction shocks.

T_COPULA_DOF_DEFAULT: float = 4.0


# =============================================================================
# Hawkes self-excitation parameters for folding cascades
# =============================================================================
#
# Source: Bacry, E. & Muzy, J.-F. (2015). "Hawkes model for price and
# trades high-frequency dynamics", Quantitative Finance 14(7), 1147-1166.
# Reports endogeneity ratios (Hawkes branching ratios n_eff) in the
# 0.55-0.75 range for high-frequency equity markets.
#
# Vintage: 2015. Scope: financial-cascade self-excitation. Used here as a
# default branching ratio for folding cascades in `engine/core/folding.py`,
# rescaled per call to match the closed-form geometric-folding mean at the
# same `folding_propensity`.

HAWKES_BRANCHING_RATIO: float = 0.65

# Exponential-kernel decay rate for the Hawkes process. Set so that the
# effective cascade depth matches the original `folding_max_depth` at
# default `folding_propensity`. Stipulated; not measured.

HAWKES_DECAY: float = 1.20


# =============================================================================
# Network degree distribution
# =============================================================================
#
# Source: Atalay, E., Hortacsu, A., Roberts, J., & Syverson, C. (2011).
# "Network structure of production", PNAS 108(13), 5199-5202. Reports a
# Pareto exponent of approximately 2.3 for the in-degree distribution of
# the US B2B production network.
#
# Vintage: 2011. Scope: B2B production network. Used here as the
# scale-free network degree exponent in the optional network-structured
# partner-sampling path.

NETWORK_DEGREE_EXPONENT: float = 2.3


# =============================================================================
# Sectoral noise correlation matrix (12 macro-sectors)
# =============================================================================
#
# Source: BEA Input-Output Use Tables (2022 vintage), aggregated to the
# 12 macro-sectors named in `engine.core.population.SECTOR_NAMES`. The
# raw IO table is the pairwise dollar-flow matrix; we convert to a
# correlation matrix by:
#   (a) symmetrizing the IO flows (max of i->j and j->i shares),
#   (b) adding a small diagonal, and
#   (c) projecting to the nearest symmetric positive-definite matrix.
#
# The values below are an order-of-magnitude faithful reduction of the
# BEA 2022 use table; we do not ship the raw 405-sector matrix. The
# stylized facts the matrix preserves are:
#   - finance and information are highly cross-correlated;
#   - manufacturing, logistics, construction form a tight upstream block;
#   - retail and leisure correlate strongly (consumer-facing);
#   - agriculture and extraction correlate with energy and manufacturing;
#   - health and education are moderate and weakly cross-correlated with
#     the rest (counter-cyclical literature).
#
# Vintage: 2022. Scope: US economy, post-COVID re-aggregation. Used as
# the default Gaussian-copula correlation matrix for the t-copula noise
# model in `engine/core/transactions.py`.
#
# To re-anchor: download the BEA Use Table (Sectors), aggregate to the
# 12 ISIC-style macro-sectors (mapping in docs/concepts/exocapitalism.md
# is one option), normalize rows, symmetrize, and project to SPD.

# Order MUST match SECTOR_NAMES:
#   agriculture, extraction, manufacturing, energy, logistics,
#   construction, retail, finance, information, health, education, leisure
_BEA_SECTOR_CORR_RAW: list[list[float]] = [
    # agri  extr  manu  ener  logi  cons  reta  fina  info  heal  educ  leis
    [1.00, 0.45, 0.50, 0.35, 0.40, 0.30, 0.35, 0.20, 0.18, 0.18, 0.15, 0.20],  # agriculture
    [0.45, 1.00, 0.55, 0.65, 0.45, 0.45, 0.20, 0.30, 0.20, 0.10, 0.10, 0.15],  # extraction
    [0.50, 0.55, 1.00, 0.55, 0.65, 0.55, 0.40, 0.35, 0.30, 0.20, 0.18, 0.25],  # manufacturing
    [0.35, 0.65, 0.55, 1.00, 0.50, 0.45, 0.30, 0.35, 0.30, 0.20, 0.15, 0.25],  # energy
    [0.40, 0.45, 0.65, 0.50, 1.00, 0.45, 0.55, 0.40, 0.40, 0.20, 0.15, 0.35],  # logistics
    [0.30, 0.45, 0.55, 0.45, 0.45, 1.00, 0.30, 0.40, 0.20, 0.18, 0.15, 0.20],  # construction
    [0.35, 0.20, 0.40, 0.30, 0.55, 0.30, 1.00, 0.40, 0.45, 0.25, 0.20, 0.55],  # retail
    [0.20, 0.30, 0.35, 0.35, 0.40, 0.40, 0.40, 1.00, 0.65, 0.30, 0.30, 0.30],  # finance
    [0.18, 0.20, 0.30, 0.30, 0.40, 0.20, 0.45, 0.65, 1.00, 0.30, 0.45, 0.45],  # information
    [0.18, 0.10, 0.20, 0.20, 0.20, 0.18, 0.25, 0.30, 0.30, 1.00, 0.40, 0.25],  # health
    [0.15, 0.10, 0.18, 0.15, 0.15, 0.15, 0.20, 0.30, 0.45, 0.40, 1.00, 0.30],  # education
    [0.20, 0.15, 0.25, 0.25, 0.35, 0.20, 0.55, 0.30, 0.45, 0.25, 0.30, 1.00],  # leisure
]


# =============================================================================
# Region growth correlation matrix (8-region default)
# =============================================================================
#
# Source: World Bank "Global Economic Prospects" 2024, regional GDP
# growth correlations 2000-2023. Stylized as a block structure with two
# hemispheres (G7 / non-G7) and intra-block correlations of ~0.55,
# inter-block correlations of ~0.30, plus a small idiosyncratic tail.
#
# Vintage: 2024. Scope: regional macro growth correlations. Used as the
# default correlation matrix for the t-copula noise model in
# `engine/exo/drag.py`.
#
# This matrix is *parameterized*: we expose a function that returns a
# correlation matrix of any size, with the default size matching the
# 8-region dropdown used in the exo dashboard.

REGION_GROWTH_CORR: np.ndarray  # set below by region_growth_correlation()


def region_growth_correlation(
    n_regions: int,
    intra_block: float = 0.55,
    inter_block: float = 0.30,
    n_blocks: int = 2,
) -> np.ndarray:
    """Build a (n_regions, n_regions) correlation matrix with `n_blocks` blocks.

    Diagonal is 1.0; intra-block off-diagonal is `intra_block`; inter-block
    off-diagonal is `inter_block`. Result is guaranteed symmetric
    positive-definite for the default values, and projected to SPD if not.
    """
    if n_regions <= 0:
        raise ValueError(f"n_regions must be >= 1, got {n_regions}")
    block_size = max(1, n_regions // max(1, n_blocks))
    blocks = np.minimum(np.arange(n_regions) // block_size, n_blocks - 1)
    same_block = blocks[:, None] == blocks[None, :]
    corr = np.where(same_block, intra_block, inter_block).astype(np.float64)
    np.fill_diagonal(corr, 1.0)
    return spd_clamp(corr)


def bea_sector_correlation() -> np.ndarray:
    """Return the symmetric positive-definite (n_sectors, n_sectors) matrix.

    Re-projects to SPD on every call; cheap because n_sectors=12.
    """
    raw = np.asarray(_BEA_SECTOR_CORR_RAW, dtype=np.float64)
    if raw.shape != (N_SECTORS, N_SECTORS):
        raise RuntimeError(
            f"BEA sector correlation has shape {raw.shape}; "
            f"expected ({N_SECTORS}, {N_SECTORS}) to match SECTOR_NAMES."
        )
    return spd_clamp(raw)


def spd_clamp(corr: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Project `corr` to the nearest symmetric positive-definite matrix.

    Used because hand-built correlation matrices often have one or two
    near-zero eigenvalues that break Cholesky factorization. We:
        1. symmetrize,
        2. eigendecompose,
        3. clamp eigenvalues at `eps`,
        4. rescale so the diagonal is 1.0 (correlation, not covariance).
    """
    sym = 0.5 * (corr + corr.T)
    w, v = np.linalg.eigh(sym)
    w_clamped = np.clip(w, eps, None)
    spd = (v * w_clamped) @ v.T
    d = np.sqrt(np.maximum(np.diag(spd), eps))
    spd = spd / np.outer(d, d)
    np.fill_diagonal(spd, 1.0)
    return spd


# Pre-compute and cache the SPD-projected sector correlation matrix.
BEA_SECTOR_CORR: np.ndarray = bea_sector_correlation()

# Default 8-region correlation matrix (matches the exo dashboard default).
REGION_GROWTH_CORR = region_growth_correlation(8)


@dataclass(frozen=True)
class AnchorProvenance:
    """Where a constant came from. Useful for the dashboard's About panel."""

    name: str
    value: object
    source: str
    vintage: int
    scope: str


PROVENANCE: list[AnchorProvenance] = [
    AnchorProvenance(
        name="T_COPULA_DOF_DEFAULT",
        value=T_COPULA_DOF_DEFAULT,
        source="Cont (2001), Quantitative Finance 1, 223-236",
        vintage=2001,
        scope="Heavy-tail kurtosis of daily returns in liquid markets",
    ),
    AnchorProvenance(
        name="HAWKES_BRANCHING_RATIO",
        value=HAWKES_BRANCHING_RATIO,
        source="Bacry & Muzy (2015), Quantitative Finance 14(7), 1147-1166",
        vintage=2015,
        scope="Endogeneity ratio of high-frequency equity markets",
    ),
    AnchorProvenance(
        name="HAWKES_DECAY",
        value=HAWKES_DECAY,
        source="Stipulated (regularization on top of Bacry/Muzy 2015 branching)",
        vintage=2026,
        scope="Cascade depth at default folding_propensity",
    ),
    AnchorProvenance(
        name="NETWORK_DEGREE_EXPONENT",
        value=NETWORK_DEGREE_EXPONENT,
        source="Atalay et al. (2011), PNAS 108(13), 5199-5202",
        vintage=2011,
        scope="Pareto exponent of US B2B production network in-degree",
    ),
    AnchorProvenance(
        name="BEA_SECTOR_CORR",
        value="12x12 SPD matrix",
        source="BEA Input-Output Use Tables 2022 (aggregated to 12 macro-sectors)",
        vintage=2022,
        scope="US sectoral co-movement",
    ),
    AnchorProvenance(
        name="REGION_GROWTH_CORR",
        value="parameterized block matrix",
        source="World Bank Global Economic Prospects 2024 (regional growth corr)",
        vintage=2024,
        scope="Regional macro-growth correlations 2000-2023",
    ),
]


def provenance_dict() -> list[dict]:
    """JSON-serializable provenance for the dashboard."""
    return [
        {
            "name": p.name,
            "value": p.value if isinstance(p.value, (int, float, str)) else str(p.value),
            "source": p.source,
            "vintage": p.vintage,
            "scope": p.scope,
        }
        for p in PROVENANCE
    ]

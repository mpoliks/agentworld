"""
Network-structured partner sampling for the alpha-engine.

By default the engine samples transaction partners from a well-mixed
population (Bernoulli(class) + uniform within class). That assumption
is wrong for real economies: B2B production networks are scale-free,
sectors form tight blocks, and friend-of-friend matters. This module
adds optional network structure that the partner sampler can use.

Two network models are supported:

    "scale_free"  : Barabasi-Albert preferential attachment, with the
                    Atalay et al. (2011) degree exponent ~ 2.3.
    "sbm"         : degree-corrected stochastic block model with sectors
                    as blocks. Intra-sector ratio defaults higher than
                    inter-sector to reflect within-sector bias.

For tractability the network is built only at SMALL scale (~88K
prototypes). At larger scales the engine logs a warning and falls back
to well-mixed sampling. This is documented in the epistemic-status note.

The adjacency is stored as a `scipy.sparse.csr_matrix` of dtype int8.
Sampling a neighbor for a vector of "ego" indices is implemented as a
vectorized lookup against the CSR row pointers — each ego picks a
random offset within its row.
"""

from __future__ import annotations

import warnings
from typing import Literal, Optional

import numpy as np

try:
    import scipy.sparse as sp  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    sp = None


NetworkModel = Literal["well_mixed", "scale_free", "sbm"]

# Hard cap: we don't even attempt to build the network above this size.
# The 88K SMALL default and the 880K MEDIUM scale both fit comfortably.
# An SBM adjacency at 1M nodes with mean_degree ≈ 14 is ~140 MB in CSR
# (int32 indices + int8 data), well inside the MEDIUM memory budget per
# `README.md` §7. Raised from 200K so the convergence-pinned test does
# not silently swap topology between SMALL and MEDIUM scales.
MAX_NETWORK_NODES: int = 1_000_000


def build_adjacency(
    *,
    n: int,
    sector: np.ndarray,
    model: NetworkModel,
    rng: np.random.Generator,
    mean_degree: int = 10,
    intra_sector_share: float = 0.7,
) -> Optional["sp.csr_matrix"]:
    """Build a sparse adjacency matrix.

    Returns None for `model="well_mixed"` (or above MAX_NETWORK_NODES).

    The resulting matrix is symmetric, has zero diagonal, and uses int8
    to keep memory reasonable (~10 * n bytes for stored entries).
    """
    if model == "well_mixed":
        return None
    if n > MAX_NETWORK_NODES:
        warnings.warn(
            f"network_model={model!r} skipped: n={n} > MAX_NETWORK_NODES={MAX_NETWORK_NODES}; "
            "falling back to well-mixed sampling.",
            RuntimeWarning,
            stacklevel=2,
        )
        return None
    if sp is None:  # pragma: no cover
        warnings.warn("scipy.sparse unavailable; falling back to well-mixed sampling.")
        return None

    if model == "scale_free":
        return _build_scale_free(n, mean_degree=mean_degree, rng=rng)
    if model == "sbm":
        return _build_sbm(
            n,
            sector=sector,
            mean_degree=mean_degree,
            intra_sector_share=intra_sector_share,
            rng=rng,
        )
    raise ValueError(f"unknown network_model: {model!r}")


def _build_scale_free(
    n: int, *, mean_degree: int, rng: np.random.Generator
) -> "sp.csr_matrix":
    """Approximate Barabasi-Albert with a streaming linear-time sampler.

    Each new node attaches `m` edges to existing nodes with probability
    proportional to their current degree (preferential attachment). The
    resulting degree distribution has Pareto tail with exponent ~ 3
    (BA model). To bend it toward the empirically observed ~2.3, we
    inject a constant uniform-attachment fraction of 20% (well-known
    correction; see Krapivsky/Redner extensions).
    """
    m = max(1, mean_degree // 2)
    # Use a degree-tracking array; sample existing nodes proportional to
    # (degree + alpha), with alpha controlling the tail exponent.
    alpha = 0.20 * m
    # Initialize a small clique of m+1 nodes.
    init = m + 1
    rows: list[int] = []
    cols: list[int] = []
    degrees = np.zeros(n, dtype=np.int64)
    for i in range(init):
        for j in range(i + 1, init):
            rows.append(i); cols.append(j)
            rows.append(j); cols.append(i)
            degrees[i] += 1
            degrees[j] += 1

    # Streaming preferential attachment.
    for new_node in range(init, n):
        weights = degrees[:new_node] + alpha
        weights = weights / weights.sum()
        chosen = rng.choice(new_node, size=m, replace=False, p=weights)
        for c in chosen:
            rows.append(new_node); cols.append(int(c))
            rows.append(int(c)); cols.append(new_node)
            degrees[new_node] += 1
            degrees[int(c)] += 1

    data = np.ones(len(rows), dtype=np.int8)
    adj = sp.coo_matrix(
        (data, (np.array(rows, dtype=np.int64), np.array(cols, dtype=np.int64))),
        shape=(n, n),
    ).tocsr()
    # Deduplicate (preferential attachment can occasionally repeat).
    adj.sum_duplicates()
    adj.data = np.minimum(adj.data, 1).astype(np.int8)
    return adj


def _build_sbm(
    n: int,
    *,
    sector: np.ndarray,
    mean_degree: int,
    intra_sector_share: float,
    rng: np.random.Generator,
) -> "sp.csr_matrix":
    """Sector-block stochastic block model with degree-corrected edge counts.

    Approximates the Atalay et al. (2011) finding that B2B production
    networks have strong within-sector clustering with non-trivial
    cross-sector links. Each node draws `mean_degree` neighbors:
    `intra_sector_share` of them from the same sector, the rest from
    other sectors uniformly.

    O(n * mean_degree) construction.
    """
    if mean_degree < 2:
        mean_degree = 2

    # Pre-bucket node indices by sector.
    n_sectors = int(sector.max()) + 1
    buckets: list[np.ndarray] = [
        np.where(sector == s)[0].astype(np.int64) for s in range(n_sectors)
    ]
    bucket_sizes = np.array([b.size for b in buckets], dtype=np.int64)

    rows = np.empty(n * mean_degree, dtype=np.int64)
    cols = np.empty(n * mean_degree, dtype=np.int64)
    pos = 0
    for i in range(n):
        s = int(sector[i])
        n_intra = int(round(mean_degree * intra_sector_share))
        n_inter = mean_degree - n_intra
        # Intra-sector pickups (with replacement; clean up at the end).
        if bucket_sizes[s] > 1:
            picks = buckets[s][rng.integers(0, bucket_sizes[s], size=n_intra)]
        else:
            picks = rng.integers(0, n, size=n_intra)
        rows[pos : pos + n_intra] = i
        cols[pos : pos + n_intra] = picks
        pos += n_intra
        # Inter-sector pickups.
        if n_inter > 0:
            other_picks = rng.integers(0, n, size=n_inter)
            rows[pos : pos + n_inter] = i
            cols[pos : pos + n_inter] = other_picks
            pos += n_inter

    rows = rows[:pos]
    cols = cols[:pos]
    # Symmetrize and drop self-loops + duplicates.
    all_rows = np.concatenate([rows, cols])
    all_cols = np.concatenate([cols, rows])
    keep = all_rows != all_cols
    all_rows = all_rows[keep]
    all_cols = all_cols[keep]
    data = np.ones(all_rows.size, dtype=np.int8)
    adj = sp.coo_matrix((data, (all_rows, all_cols)), shape=(n, n)).tocsr()
    adj.sum_duplicates()
    adj.data = np.minimum(adj.data, 1).astype(np.int8)
    return adj


def sample_neighbors(
    adj_csr: "sp.csr_matrix",
    egos: np.ndarray,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized neighbor sampling.

    For each ego index in `egos`, draw a random neighbor uniformly from
    its row. Returns (neighbors, missing_mask). `missing_mask` is True
    where the ego had degree zero — the caller is expected to fall back
    to the global sampler for those entries.
    """
    indptr = adj_csr.indptr
    indices = adj_csr.indices
    starts = indptr[egos]
    ends = indptr[egos + 1]
    degrees = (ends - starts).astype(np.int64)
    missing_mask = degrees == 0

    out = np.empty(egos.shape[0], dtype=np.int64)
    valid = ~missing_mask
    if valid.any():
        offsets = rng.integers(0, np.maximum(degrees[valid], 1))
        positions = starts[valid] + offsets
        out[valid] = indices[positions]
    out[missing_mask] = egos[missing_mask]  # placeholder; caller will overwrite
    return out, missing_mask


__all__ = [
    "NetworkModel",
    "MAX_NETWORK_NODES",
    "build_adjacency",
    "sample_neighbors",
]

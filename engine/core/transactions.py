"""
Transactions — Coasean bargaining at scale.

For each step, we sample a large number of *potential* transaction pairs from the
population (weighted by sectoral and stack affinity), compute their transaction
cost and expected surplus, and execute those where surplus > cost. The Matryoshka
layers (law / market / individual) act as filters on what is allowed.

This is the "Coasean engine" — it is what produces direct welfare. It is the
*smooth* component of the economy.

The output is per-step:
    real_surplus_added : sum across all pairs of (surplus - layer taxes)
    nominal_volume     : sum across all pairs of transaction values
    n_transactions     : number of executed transactions (in real units)
    rejected_law       : number rejected by law layer
    rejected_market    : number rejected by market layer
    rejected_align     : number rejected by alignment layer
    rejected_cost      : number rejected because cost > surplus
    wealth_delta       : per-prototype wealth change
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from engine.core.noise import CopulaState, per_pair_surplus_shock
from engine.core.population import N_SECTORS, Population
from engine.core.topology import Topology
from engine.data.empirical_anchors import BEA_SECTOR_CORR


# Cache the BEA Cholesky once per topology config; rebuilding every step
# is wasteful and the matrix is fixed at model-load time.
_COPULA_STATE_CACHE: dict[float, CopulaState] = {}


def _copula_state(dof: float) -> CopulaState:
    state = _COPULA_STATE_CACHE.get(dof)
    if state is None:
        state = CopulaState.from_corr(BEA_SECTOR_CORR, dof=dof)
        _COPULA_STATE_CACHE[dof] = state
    return state


@dataclass
class TransactionResult:
    real_surplus_added: float
    nominal_volume: float
    n_transactions_real: float
    rejected_law: float
    rejected_market: float
    rejected_align: float
    rejected_cost: float
    wealth_delta: np.ndarray  # per-prototype wealth change in this step


def _sample_partners(
    pop: Population,
    topo: Topology,
    n_pairs: int,
    rng: np.random.Generator,
    bias_inside_stack: float = 0.7,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Sample n_pairs (i, j) candidate transaction pairs.

    Sampling protocol (in priority order):
      1. If `pop.adjacency` is present and `pop.config.network_p_local > 0`,
         a fraction `network_p_local` of the pairs come from `a`'s graph
         neighborhood (via `engine.core.network.sample_neighbors`). The
         rest fall back to step (2) below. Egos with degree zero also
         fall back. This is the "network-structured" path.
      2. With prob `bias_inside_stack`, both come from the same stack as
         `a`; otherwise sample globally (weighted by importance weight).
         This is the original well-mixed path.

    Uses pre-built CDFs on the Population (built once in synthesize) so
    the per-step cost is O(n_pairs * log n) instead of O(n) per call. At
    n=88M this is the difference between ~4s and ~50ms.
    """
    n = pop.n

    a = pop.sample_global(n_pairs, rng)
    b = pop.sample_global(n_pairs, rng)

    p_local = pop.config.network_p_local if pop.adjacency is not None else 0.0
    if p_local > 0:
        from engine.core.network import sample_neighbors

        do_local = rng.random(n_pairs) < p_local
        local_idx = np.where(do_local)[0]
        if local_idx.size > 0:
            picks, missing_mask = sample_neighbors(pop.adjacency, a[local_idx], rng)
            # Egos with empty neighborhoods fall back to the well-mixed sampler.
            if missing_mask.any():
                fb_idx = local_idx[missing_mask]
                # Reuse already-drawn `b` for fallback (uniform global).
                # Keep `b[fb_idx]` as already sampled.
                pass
            ok_idx = local_idx[~missing_mask]
            b[ok_idx] = picks[~missing_mask]
        # The non-local pairs go through the stack-bias step below.
        bias_remaining = ~do_local
    else:
        bias_remaining = np.ones(n_pairs, dtype=bool)

    if bias_inside_stack > 0:
        do_bias = bias_remaining & (rng.random(n_pairs) < bias_inside_stack)
        bias_idx = np.where(do_bias)[0]
        if bias_idx.size > 0:
            target_stack = pop.stack[a[bias_idx]]
            for k in range(topo.cfg.n_stacks):
                in_k = bias_idx[target_stack == k]
                if in_k.size == 0:
                    continue
                b[in_k] = pop.sample_in_stack(k, in_k.size, rng)

    self_mask = a == b
    if self_mask.any():
        b[self_mask] = (b[self_mask] + 1) % n

    return a, b


def coasean_step(
    pop: Population,
    topo: Topology,
    rng: np.random.Generator,
    n_pairs: int = 200_000,
    base_match_volume: float = 1.0,
    chunk_size: int = 0,
) -> TransactionResult:
    """
    Run one step of Coasean bargaining at scale.

    n_pairs is the number of *prototype-pairs* we sample. Each represents a
    much larger number of real-agent pairs via the prototype weights.

    If chunk_size > 0 and < n_pairs, the pairs are processed in batches of
    chunk_size and aggregated. This keeps the per-batch working set in cache
    at xlarge scales (n_pairs >= 5M); aggregation is exact (sums are
    associative for the purposes of these metrics).
    """
    if 0 < chunk_size < n_pairs:
        return _coasean_step_chunked(
            pop, topo, rng, n_pairs, base_match_volume, chunk_size,
        )
    n = pop.n
    a, b = _sample_partners(pop, topo, n_pairs, rng)

    # Vectorized lookups.
    cap_a, cap_b = pop.capability[a], pop.capability[b]
    sec_a, sec_b = pop.sector[a], pop.sector[b]
    stk_a, stk_b = pop.stack[a], pop.stack[b]
    al_a, al_b = pop.alignment[a], pop.alignment[b]
    h_a, h_b = pop.is_human[a], pop.is_human[b]
    auto_a, auto_b = pop.autonomy[a], pop.autonomy[b]

    # Sector affinity for each pair.
    sec_aff = topo.sector_affinity[sec_a, sec_b]

    # Per-pair transaction cost.
    cost = topo.transaction_cost(cap_a, cap_b, stk_a, stk_b)

    # Potential surplus before any taxes.
    # Surplus rises with capability product, sector affinity, and a base
    # economic gain. There's an exogenous shock per pair whose distribution
    # is governed by topo.cfg.noise_model — see `engine/core/noise.py` and
    # `docs/concepts/epistemic_status.md`. Variance is held at 0.05^2 across
    # both the gaussian and t_copula models so swapping doesn't silently
    # rescale the surplus.
    cap_product = cap_a * cap_b
    if topo.cfg.noise_model == "t_copula":
        shock = per_pair_surplus_shock(
            rng,
            n_pairs,
            sec_a,
            scale=0.05,
            model="t_copula",
            dof=topo.cfg.noise_dof,
            sector_share=topo.cfg.noise_sector_share,
            state=_copula_state(topo.cfg.noise_dof),
        )
    else:
        shock = 0.05 * rng.standard_normal(n_pairs)
    base_surplus = base_match_volume * (
        0.05 + 0.5 * cap_product * sec_aff + shock
    )
    base_surplus = np.clip(base_surplus, 0.0, None)

    # ---- Matryoshka filters --------------------------------------------------
    # Law layer: a small fraction of transactions are simply forbidden.
    # We model this as a uniform-random rejection at low rate, with an extra
    # rejection for high-stakes (large surplus) cross-stack deals.
    law_reject = rng.random(n_pairs) < (
        0.01 + 0.04 * (1.0 - topo.cross_stack[stk_a, stk_b])
    )

    # Market layer: each platform/protocol has its own filter, simulated as
    # rejection probability that scales with cross-sector and cross-alignment.
    align_dist = np.abs(al_a - al_b)
    market_reject = rng.random(n_pairs) < (
        0.02 + 0.06 * (1.0 - sec_aff) + 0.04 * align_dist
    )

    # Alignment layer: individual-agent refusal. Higher alignment distance →
    # more refusal. Also: if either party's autonomy is very low, the agent
    # may decline on behalf of the principal.
    align_reject = rng.random(n_pairs) < (
        0.03 + 0.20 * align_dist * (1.0 - 0.5 * (auto_a + auto_b) / 2.0)
    )

    rejected_law_mask = law_reject
    rejected_market_mask = (~rejected_law_mask) & market_reject
    rejected_align_mask = (~rejected_law_mask) & (~rejected_market_mask) & align_reject

    # Surplus must exceed transaction cost to execute.
    cost_reject = base_surplus <= cost
    rejected_cost_mask = (
        (~rejected_law_mask)
        & (~rejected_market_mask)
        & (~rejected_align_mask)
        & cost_reject
    )

    executed_mask = ~(
        rejected_law_mask | rejected_market_mask | rejected_align_mask | rejected_cost_mask
    )

    # Gross surplus on executed pairs.
    pair_surplus = (base_surplus - cost) * executed_mask

    # Apply Matryoshka taxes (market + individual layers).
    real_tax_rate = topo.matryoshka_real_tax()
    real_pair_surplus = pair_surplus * (1.0 - real_tax_rate)

    # Aggregate using population weights. Each (a,b) pair represents
    # weight_a * weight_b / total_weight real pairs. total_weight is
    # cached on Population (computed analytically from class counts) to
    # skip a redundant 88M-element sum every step.
    total_w = pop.total_weight
    w_a = pop.weight[a].astype(np.float64)
    w_b = pop.weight[b].astype(np.float64)
    pair_real_count = w_a * w_b / total_w

    real_surplus = float((real_pair_surplus * pair_real_count).sum())
    nominal_volume = float(
        ((base_surplus + cost) * executed_mask * pair_real_count).sum()
    )
    n_real = float((executed_mask * pair_real_count).sum())

    # Wealth delta: split surplus 50/50 between the two parties (Nash
    # bargaining). bincount is consistently faster and more cache-friendly
    # than np.add.at for unsorted scatter into very large arrays.
    half_surplus = real_pair_surplus * 0.5
    contrib_a = half_surplus * pair_real_count / w_a
    contrib_b = half_surplus * pair_real_count / w_b
    wealth_delta = np.bincount(a, weights=contrib_a, minlength=n)
    wealth_delta += np.bincount(b, weights=contrib_b, minlength=n)

    return TransactionResult(
        real_surplus_added=real_surplus,
        nominal_volume=nominal_volume,
        n_transactions_real=n_real,
        rejected_law=float((rejected_law_mask * pair_real_count).sum()),
        rejected_market=float((rejected_market_mask * pair_real_count).sum()),
        rejected_align=float((rejected_align_mask * pair_real_count).sum()),
        rejected_cost=float((rejected_cost_mask * pair_real_count).sum()),
        wealth_delta=wealth_delta,
    )


def _coasean_step_chunked(
    pop: Population,
    topo: Topology,
    rng: np.random.Generator,
    n_pairs: int,
    base_match_volume: float,
    chunk_size: int,
) -> TransactionResult:
    """Process pairs in cache-friendly batches; aggregate exactly."""
    n = pop.n
    real_surplus = 0.0
    nominal_volume = 0.0
    n_real = 0.0
    rejected_law = 0.0
    rejected_market = 0.0
    rejected_align = 0.0
    rejected_cost = 0.0
    wealth_delta = np.zeros(n, dtype=np.float64)

    remaining = n_pairs
    while remaining > 0:
        batch = min(chunk_size, remaining)
        part = coasean_step(
            pop, topo, rng,
            n_pairs=batch,
            base_match_volume=base_match_volume,
            chunk_size=0,
        )
        real_surplus += part.real_surplus_added
        nominal_volume += part.nominal_volume
        n_real += part.n_transactions_real
        rejected_law += part.rejected_law
        rejected_market += part.rejected_market
        rejected_align += part.rejected_align
        rejected_cost += part.rejected_cost
        wealth_delta += part.wealth_delta
        remaining -= batch

    return TransactionResult(
        real_surplus_added=real_surplus,
        nominal_volume=nominal_volume,
        n_transactions_real=n_real,
        rejected_law=rejected_law,
        rejected_market=rejected_market,
        rejected_align=rejected_align,
        rejected_cost=rejected_cost,
        wealth_delta=wealth_delta,
    )

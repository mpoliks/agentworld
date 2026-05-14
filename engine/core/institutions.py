"""Firm dynamics for institutional emergence."""

from __future__ import annotations

from typing import Any

import numpy as np


def firm_cost_discount(
    firm_id: np.ndarray,
    a: np.ndarray,
    b: np.ndarray,
    within_firm_cost_discount: float,
) -> np.ndarray:
    """Return per-pair transaction-cost multipliers for within-firm pairs."""
    same_firm = (firm_id[a] == firm_id[b]) & (firm_id[a] != -1)
    return np.where(same_firm, within_firm_cost_discount, 1.0).astype(np.float32)


def dissolution_step(pop: Any, cfg: Any) -> int:
    """Dissolve firms whose average member wealth falls below the threshold."""
    firm_id = pop.firm_id
    active = firm_id >= 0
    if not active.any():
        return 0

    max_id = int(firm_id[active].max())
    counts = np.bincount(firm_id[active], minlength=max_id + 1)
    wealth_sum = np.bincount(
        firm_id[active],
        weights=pop.wealth[active].astype(np.float64),
        minlength=max_id + 1,
    )
    avg_wealth = np.divide(wealth_sum, counts, out=np.zeros_like(wealth_sum), where=counts > 0)
    threshold = float(pop.wealth.mean()) * cfg.dissolution_wealth_threshold
    dissolve_ids = np.where((counts > 0) & (avg_wealth < threshold))[0]
    if dissolve_ids.size == 0:
        return 0
    dissolve_mask = np.isin(firm_id, dissolve_ids)
    firm_id[dissolve_mask] = -1
    return int(dissolve_ids.size)


def formation_step(
    pop: Any,
    cfg: Any,
    rng: np.random.Generator,
    surplus_per_proto: np.ndarray,
    mission_config: Any = None,
) -> int:
    """Form new firms from independent same-sector/same-stack prototypes.

    `mission_config` (optional, W2b) modulates the per-prototype
    `formation_surplus_threshold` for prototypes in
    `mission_config.coordinator_sectors`. Defaults preserve the pre-W2b
    behaviour bit-identically: when the mission lever is off, every
    candidate is held to the single scalar threshold from `cfg`.
    """
    firm_id = pop.firm_id
    mission_enabled = bool(getattr(mission_config, "enabled", False))
    if (
        mission_enabled
        and len(getattr(mission_config, "coordinator_sectors", ()) or ()) > 0
    ):
        thresh = np.full(
            pop.sector.shape, float(cfg.formation_surplus_threshold),
            dtype=np.float64,
        )
        factor = float(mission_config.formation_threshold_factor)
        coord = np.isin(pop.sector, np.asarray(
            mission_config.coordinator_sectors, dtype=pop.sector.dtype,
        ))
        thresh[coord] = thresh[coord] * factor
        independent = (firm_id == -1) & (surplus_per_proto >= thresh)
    else:
        independent = (firm_id == -1) & (surplus_per_proto >= cfg.formation_surplus_threshold)
    if not independent.any() or pop.firm_next_id >= cfg.max_firms:
        return 0

    max_size = max(2, int(cfg.max_firm_size))
    candidates = np.where(independent)[0]
    if candidates.size < 2:
        return 0

    # Randomize within each bin, then assign contiguous chunks to firm
    # IDs with vectorized rank arithmetic. Bin defaults to (sector,
    # stack); with `cfg.cross_sector_firms = True` the bin is just
    # `stack`, so a firm can span sectors within one hemispherical
    # stack.
    stack_keys = pop.stack[candidates].astype(np.int64)
    if cfg.cross_sector_firms:
        bin_key = stack_keys
    else:
        bin_key = (
            pop.sector[candidates].astype(np.int64) * int(pop.config.n_stacks)
            + stack_keys
        )
    order = np.lexsort((rng.random(candidates.size), bin_key))
    candidates = candidates[order]
    bin_key = bin_key[order]

    _, starts, counts = np.unique(bin_key, return_index=True, return_counts=True)
    group_counts = counts // max_size + ((counts % max_size) >= 2)
    valid_bins = group_counts > 0
    if not valid_bins.any():
        return 0

    group_offsets = np.zeros_like(group_counts)
    group_offsets[1:] = np.cumsum(group_counts[:-1])
    bin_idx = np.repeat(np.arange(counts.size), counts)
    rank_in_bin = np.arange(candidates.size) - np.repeat(starts, counts)
    group_in_bin = rank_in_bin // max_size
    eligible = valid_bins[bin_idx] & (group_in_bin < group_counts[bin_idx])

    group_ord = group_offsets[bin_idx] + group_in_bin
    capacity = cfg.max_firms - pop.firm_next_id
    eligible &= group_ord < capacity
    if not eligible.any():
        return 0

    new_ids = pop.firm_next_id + group_ord[eligible]
    firm_id[candidates[eligible]] = new_ids.astype(np.int32)
    formed = int(np.unique(new_ids).size)
    pop.firm_next_id += formed
    return formed


def merge_step(pop: Any, cfg: Any, rng: np.random.Generator) -> int:
    """Randomly merge some same-sector firms with nearby stack IDs."""
    firm_id = pop.firm_id
    active_mask = firm_id >= 0
    active_ids = np.unique(firm_id[active_mask])
    if active_ids.size < 2 or cfg.merge_probability <= 0:
        return 0

    do_merge = rng.random(active_ids.size) < cfg.merge_probability
    candidate_ids = active_ids[do_merge]
    if candidate_ids.size == 0:
        return 0

    max_id = int(active_ids.max())
    active_firm = firm_id[active_mask]
    firm_size = np.bincount(active_firm, minlength=max_id + 1)
    firm_stack = np.divide(
        np.bincount(
            active_firm,
            weights=pop.stack[active_mask].astype(np.float64),
            minlength=max_id + 1,
        ),
        firm_size,
        out=np.zeros(max_id + 1, dtype=np.float64),
        where=firm_size > 0,
    )

    # Firms form within a sector, and merges preserve same-sector membership.
    # The first sorted member is therefore a vectorized representative.
    member_order = np.argsort(active_firm, kind="stable")
    sorted_firms = active_firm[member_order]
    first_member_positions = np.r_[0, np.flatnonzero(np.diff(sorted_firms)) + 1]
    representative_idx = np.where(active_mask)[0][member_order[first_member_positions]]
    firm_sector = np.full(max_id + 1, -1, dtype=np.int16)
    firm_sector[sorted_firms[first_member_positions]] = pop.sector[representative_idx]

    # Random sampling rather than exhaustive nearest-neighbor search: draw a
    # candidate target for each merging firm and accept only valid same-sector,
    # smaller, size-capped pairs.
    target_ids = rng.choice(active_ids, size=candidate_ids.size, replace=True)
    valid = (
        (target_ids != candidate_ids)
        & (firm_sector[target_ids] == firm_sector[candidate_ids])
        & (firm_size[target_ids] <= firm_size[candidate_ids])
        & ((firm_size[target_ids] + firm_size[candidate_ids]) <= cfg.max_firm_size)
    )
    if not valid.any():
        return 0

    # Prefer sampled targets that are stack-near by accepting the closest half.
    distances = np.abs(firm_stack[target_ids] - firm_stack[candidate_ids])
    valid_distances = distances[valid]
    distance_cutoff = np.quantile(valid_distances, 0.5) if valid_distances.size > 1 else valid_distances[0]
    valid &= distances <= distance_cutoff
    if not valid.any():
        return 0

    mapping = np.arange(max_id + 1, dtype=np.int32)
    mapping[target_ids[valid]] = candidate_ids[valid].astype(np.int32)
    firm_id[active_mask] = mapping[firm_id[active_mask]]
    return int(np.unique(target_ids[valid]).size)


def firm_overhead_step(pop: Any, cfg: Any) -> None:
    """Deduct per-member firm maintenance overhead from member wealth."""
    active = pop.firm_id >= 0
    if not active.any() or cfg.firm_overhead_per_member <= 0:
        return
    pop.wealth[active] = np.clip(
        pop.wealth[active] - np.float32(cfg.firm_overhead_per_member),
        0.0,
        None,
    )

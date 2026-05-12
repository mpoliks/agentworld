"""Norm-participation alignment (W1b).

Replaces the static-distance `align_reject` gate with a participation
operationalization of Hadfield's *Normative Infrastructure for AI
Alignment*. Each prototype carries a `norm_vector` of shape `(K,)` —
a point in a K-dim norm space generalising the scalar `alignment`.
The individual-layer rejection gate becomes distance-in-norm-space,
and each step every prototype's norm drifts toward the
capability-weighted mean of its *executed* partners' norms.

The drift is what makes alignment *participation*: agents who
successfully transact together pull their norms toward each other;
agents whose trades never clear stay apart. Over many steps, the
population either converges on a global norm (when network coupling
is dense), splits into clusters (when sectors / stacks gate
cross-cluster trade), or whiplashes (when `update_rate` is large
enough that single-step partner draws can dominate).

The math (per-prototype EMA):

    norm_new[i] = (1 − rate) · norm_old[i] + rate · weighted_mean_partner_norm[i]

where the weighted mean is over all pairs `(a, b)` in the step in
which `i ∈ {a, b}` and the pair *executed*. The weight on partner j
is `pair_real_count_pair * partner_capability_j` (when
`capability_weight=True`); the weighted mean falls back to the
prototype's current norm when no executed partner exists in the
step. Norm vectors are clipped to `[-1, 1]` per dimension.

With `NormsConfig.enabled = False` neither the gate nor the update
fires, and the canonical baselines stay bit-identical.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def norm_distance(
    norm_a: np.ndarray, norm_b: np.ndarray, n_dimensions: int
) -> np.ndarray:
    """L2 distance between two stacks of norm vectors, normalized.

    Returns a `(n_pairs,)` float64 array. The `sqrt(K)` normalisation
    rescales the L2 metric back onto roughly `[0, 2]` for vectors
    with elements in `[-1, 1]`, so the rejection-formula constants
    (`0.20` slope) keep their calibration from the scalar case.
    """
    diff = norm_a.astype(np.float64) - norm_b.astype(np.float64)
    sq = np.sum(diff * diff, axis=1)
    return np.sqrt(sq / max(int(n_dimensions), 1))


def update_norm_vectors(
    pop: Any,
    a: np.ndarray,
    b: np.ndarray,
    executed_mask: np.ndarray,
    pair_real_count: np.ndarray,
    cfg: Any,
) -> None:
    """EMA-update each prototype's norm toward executed partners.

    Operates in place on `pop.norm_vector`. The aggregation is exact
    (every executed pair contributes to both endpoints' EMA target);
    each dimension uses a separate `np.bincount` accumulation so the
    cost is O(n_pairs · K).

    No-op when `cfg.enabled = False`, `pop.norm_vector` is None, or
    no pair executed this step.
    """
    if not bool(getattr(cfg, "enabled", False)):
        return
    if pop.norm_vector is None:
        return
    if not executed_mask.any():
        return

    nv = pop.norm_vector
    K = nv.shape[1]
    n = pop.n

    # Partner-weight vectors. When `capability_weight` is True, weight
    # the partner influence by the partner's capability so high-
    # capability agents shape the local norm more (the Hadfield
    # framing: norms accrete around competent actors).
    pair_w = pair_real_count.astype(np.float64) * executed_mask.astype(np.float64)
    if bool(getattr(cfg, "capability_weight", True)):
        cap_a = pop.capability[a].astype(np.float64)
        cap_b = pop.capability[b].astype(np.float64)
        # For a's update, b is the partner — weight by b's capability.
        w_for_a = pair_w * cap_b
        w_for_b = pair_w * cap_a
    else:
        w_for_a = pair_w
        w_for_b = pair_w

    # Per-dimension weighted-partner-norm accumulator + weight sum.
    sum_w = np.bincount(a, weights=w_for_a, minlength=n) + np.bincount(
        b, weights=w_for_b, minlength=n
    )
    has_partner = sum_w > 0
    if not has_partner.any():
        return

    partner_for_a = nv[b].astype(np.float64)  # for a's EMA target
    partner_for_b = nv[a].astype(np.float64)  # for b's EMA target

    weighted_partner = np.empty((n, K), dtype=np.float64)
    for k in range(K):
        weighted_partner[:, k] = (
            np.bincount(a, weights=w_for_a * partner_for_a[:, k], minlength=n)
            + np.bincount(b, weights=w_for_b * partner_for_b[:, k], minlength=n)
        )

    # Per-prototype EMA target = weighted_partner / sum_w (where defined).
    # Prototypes with no executed partner stay at their current norm.
    safe_sum_w = np.where(has_partner, sum_w, 1.0)
    target = weighted_partner / safe_sum_w[:, None]
    target[~has_partner] = nv[~has_partner]

    rate = float(np.clip(getattr(cfg, "update_rate", 0.05), 0.0, 1.0))
    new_norm = (1.0 - rate) * nv.astype(np.float64) + rate * target
    np.clip(new_norm, -1.0, 1.0, out=new_norm)
    pop.norm_vector = new_norm.astype(np.float32)


__all__ = ["norm_distance", "update_norm_vectors"]

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
from typing import Mapping, Optional, Union

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


# Public type for the rng argument: either a single Generator (legacy
# single-stream behaviour, used by direct unit-test callers) or a dict
# keyed by subsystem name. The helper below normalises to a dict so the
# body can always speak the per-component contract.
RngOrRngs = Union[np.random.Generator, Mapping[str, np.random.Generator]]
_TX_SUBSYSTEMS: tuple[str, ...] = (
    "market",
    "alignment",
    "law",
    "network",
    "demand",
)


def _resolve_rngs(rng: RngOrRngs) -> Mapping[str, np.random.Generator]:
    """Normalise `rng` into a subsystem dict.

    A single `Generator` is treated as "all subsystems share this stream"
    (legacy behaviour — bit-identical to the pre-split engine). A
    mapping is returned as-is.
    """
    if isinstance(rng, np.random.Generator):
        return {name: rng for name in _TX_SUBSYSTEMS}
    return rng


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
    # Demand-modulated share of the real surplus that ultimately reaches a
    # human consumer (or a human-controlled agent). Equals
    # `real_surplus_added` when `DemandConfig.enabled = False`. See
    # `engine/core/topology.py:DemandConfig` and the demand-and-
    # intermediation concept doc for what this means.
    real_surplus_authentic: float = 0.0
    law_weak_surplus_loss: float = 0.0
    law_capture_surplus_loss: float = 0.0
    pigouvian_revenue: float = 0.0
    realized_alpha: float = 0.0
    a2a_share: float = 0.0
    h2a_share: float = 0.0
    h2h_share: float = 0.0
    # Share of executed real-pair-count whose either side is registered
    # (`prototype_id >= 0`). Always 0.0 at `registration_coverage = 0.0`;
    # at full coverage it lands near 1.0 (some humans participate in
    # mixed pairs, so it never quite hits 1). Plan 4's regulator metric
    # `audit_quality_effective` multiplies this by `audit_quality`.
    registered_active_share: float = 0.0
    # Per-stack alignment observation from registered participants in
    # this step's executed pairs. Both arrays have shape `(K,)` with
    # K=n_stacks under stratification, K=1 otherwise. `norm_obs_sum[k]`
    # is `sum(alignment * pair_real_count)` over registered sides whose
    # bucket maps to k; `norm_obs_weight[k]` is `sum(pair_real_count)`
    # over the same set. The world step divides them to recover the
    # observed mean (and falls back to the prior when weight is zero).
    # Both are None when `pop.cfg.norm.enabled` is False.
    norm_obs_sum: np.ndarray | None = None
    norm_obs_weight: np.ndarray | None = None
    # Real-pair count of alignment-layer rejections produced under the
    # norm-evolution binding. Zero when `pop.cfg.norm.enabled` is False;
    # equal to `rejected_align` when enabled (passed through so the
    # metrics layer can distinguish the regime without re-reading the
    # config).
    rejected_align_under_norm: float = 0.0
    # Plan 4: split the market-layer rejection into platform/deployer
    # (Krier) and licensed-regulator (Hadfield) sublayers. At
    # `RegulatorConfig.enabled = False` (the default), the regulator
    # rejection is exactly zero and `rejected_platform_real` equals
    # `rejected_market` — preserving the canonical metric values
    # bit-for-bit. See `docs/plans/regulator_market_split.md`.
    rejected_platform_real: float = 0.0
    rejected_regulator_real: float = 0.0
    # Plan 7: mission-economy allocation diagnostics.
    # `mission_executed_real` is the share of executed real-pair-count
    # that came through the coordinator allocator; `mission_overhead_real`
    # is the cumulative coordinator-overhead surplus consumed this step.
    # Both zero when `MissionConfig.enabled = False`.
    mission_executed_real: float = 0.0
    mission_overhead_real: float = 0.0


def executed_interaction_shares(
    h_a: np.ndarray,
    h_b: np.ndarray,
    executed_mask: np.ndarray,
    pair_real_count: np.ndarray,
) -> tuple[float, float, float]:
    """Weighted endpoint shares among executed transaction pairs."""
    executed_weight = executed_mask * pair_real_count
    total = float(executed_weight.sum())
    if total <= 0.0:
        return 0.0, 0.0, 0.0

    h2h = float((executed_weight * (h_a & h_b)).sum() / total)
    a2a = float((executed_weight * (~h_a & ~h_b)).sum() / total)
    h2a = float((executed_weight * (h_a ^ h_b)).sum() / total)
    return a2a, h2a, h2h


def demand_factor(
    h_a: np.ndarray,
    h_b: np.ndarray,
    auto_a: np.ndarray,
    auto_b: np.ndarray,
    a2a_floor: float,
) -> np.ndarray:
    """Per-pair demand factor — share of surplus that reaches a human consumer.

    Effective humanity of each side: humans count fully; agents count to
    the extent they are NOT autonomous (i.e. acting on a human's behalf).
    Surplus is "really real" to the extent at least one endpoint is human-
    coupled. A2A surplus has a small floor (some A2A activity genuinely
    benefits humans indirectly via downstream production).

    See `docs/plans/demand_and_intermediation.md` for the derivation.
    """
    h_a = h_a.astype(np.float32, copy=False)
    h_b = h_b.astype(np.float32, copy=False)
    eff_h_a = h_a + (1.0 - h_a) * (1.0 - auto_a)
    eff_h_b = h_b + (1.0 - h_b) * (1.0 - auto_b)
    return a2a_floor + (1.0 - a2a_floor) * np.maximum(eff_h_a, eff_h_b)


def _sample_partners(
    pop: Population,
    topo: Topology,
    n_pairs: int,
    rng: np.random.Generator,
    bias_inside_stack: float = 0.7,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample n_pairs (i, j) candidate pairs.

    `rng` is the network/sampling stream — every draw made here is a
    sampling decision (Bernoulli-class draws inside `sample_global`,
    neighbor offsets, intra-stack-bias coin). Routing all of them to a
    single subsystem stream keeps the partner sampler isolated from
    market/law/alignment gating draws so that, under the per-component
    RNG split, varying a market or alignment knob does not perturb the
    realized pair distribution.
    """
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
    rng: RngOrRngs,
    n_pairs: int = 200_000,
    base_match_volume: float = 1.0,
    chunk_size: int = 0,
    law_strength: float = 1.0,
    law_capture: float = 0.0,
    gini_wealth: float = 0.0,
    local_alpha: np.ndarray | None = None,
) -> TransactionResult:
    """
    Run one step of Coasean bargaining at scale.

    n_pairs is the number of *prototype-pairs* we sample. Each represents a
    much larger number of real-agent pairs via the prototype weights.

    If chunk_size > 0 and < n_pairs, the pairs are processed in batches of
    chunk_size and aggregated. This keeps the per-batch working set in cache
    at xlarge scales (n_pairs >= 5M); aggregation is exact (sums are
    associative for the purposes of these metrics).

    `rng` is either a single `np.random.Generator` (legacy: every draw —
    market gate, alignment gate, law gate, partner sampler, surplus
    shock — comes from one shared stream) or a mapping keyed by
    subsystem (`"market"`, `"alignment"`, `"law"`, `"network"`,
    `"demand"`) when the World was built with
    `WorldConfig.rng_split_mode == "per_component"`. In the per-component
    mode each gate consumes its own stream so that perturbing one
    subsystem's draw count cannot move another subsystem's draw sequence.
    """
    rngs = _resolve_rngs(rng)
    if 0 < chunk_size < n_pairs:
        return _coasean_step_chunked(
            pop, topo, rng, n_pairs, base_match_volume, chunk_size,
            law_strength, law_capture, gini_wealth, local_alpha,
        )
    n = pop.n
    a, b = _sample_partners(pop, topo, n_pairs, rngs["network"])

    # Vectorized lookups.
    cap_a, cap_b = pop.capability[a], pop.capability[b]
    sec_a, sec_b = pop.sector[a], pop.sector[b]
    stk_a, stk_b = pop.stack[a], pop.stack[b]
    al_a, al_b = pop.alignment[a], pop.alignment[b]
    h_a, h_b = pop.is_human[a], pop.is_human[b]
    auto_a, auto_b = pop.autonomy[a], pop.autonomy[b]

    if local_alpha is not None:
        pair_alpha = 0.5 * (
            local_alpha[a].astype(np.float32, copy=False)
            + local_alpha[b].astype(np.float32, copy=False)
        )
        noise_sd = topo.cfg.strategy.local_alpha_noise_sd
        if noise_sd > 0:
            pair_alpha = pair_alpha + noise_sd * rngs["market"].standard_normal(n_pairs).astype(np.float32)
        pair_alpha = np.clip(pair_alpha, 0.0, 1.0)
    else:
        pair_alpha = None

    # Sector affinity for each pair.
    sec_aff = topo.sector_affinity[sec_a, sec_b]

    # Per-pair transaction cost.
    cost = topo.transaction_cost(cap_a, cap_b, stk_a, stk_b, alpha_override=pair_alpha)
    inst_cfg = topo.cfg.institutions
    if inst_cfg.enabled:
        from engine.core.institutions import firm_cost_discount

        cost *= firm_cost_discount(pop.firm_id, a, b, inst_cfg.within_firm_cost_discount)

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
            rngs["demand"],
            n_pairs,
            sec_a,
            scale=0.05,
            model="t_copula",
            dof=topo.cfg.noise_dof,
            sector_share=topo.cfg.noise_sector_share,
            state=_copula_state(topo.cfg.noise_dof),
        )
    else:
        shock = 0.05 * rngs["demand"].standard_normal(n_pairs)
    base_surplus_raw = base_match_volume * (
        0.05 + 0.5 * cap_product * sec_aff + shock
    )
    base_surplus_raw = np.clip(base_surplus_raw, 0.0, None)

    # ---- Matryoshka filters --------------------------------------------------
    # Law layer. With the dynamic mechanism disabled, preserve the original
    # binary rejection path exactly. When enabled, law also gates surplus and
    # reports the resulting surplus losses separately from explicit vetoes.
    law_cfg = topo.cfg.law
    compat = topo.cross_stack[stk_a, stk_b]
    law_reject = rngs["law"].random(n_pairs) < (0.01 + 0.04 * (1.0 - compat))
    if law_cfg.enabled:
        same_stack = stk_a == stk_b
        law_strength_clamped = float(np.clip(law_strength, 0.0, 1.0))
        law_capture_clamped = float(np.clip(law_capture, 0.0, 1.0))
        neutral_law_gate = np.where(
            same_stack,
            np.maximum(law_strength_clamped, law_cfg.local_trust_surplus_floor),
            law_strength_clamped,
        )
        gini_excess = max(0.0, float(gini_wealth) - law_cfg.concentration_penalty_gini_anchor)
        concentration_penalty = (1.0 - compat) + 0.5 * gini_excess
        concentration_penalty = np.clip(concentration_penalty, 0.0, 1.0)
        capture_gate = 1.0 - law_capture_clamped * concentration_penalty
        law_gate = np.clip(neutral_law_gate * capture_gate, 0.0, 1.0)
        law_weak_loss_pair = base_surplus_raw * (1.0 - neutral_law_gate)
        law_capture_loss_pair = base_surplus_raw * neutral_law_gate * (1.0 - capture_gate)
        base_surplus = base_surplus_raw * law_gate
        law_reject = law_reject | (law_gate <= 0.0)
    else:
        base_surplus = base_surplus_raw
        law_weak_loss_pair = np.zeros(n_pairs, dtype=np.float32)
        law_capture_loss_pair = np.zeros(n_pairs, dtype=np.float32)

    # Market layer: composed of two independent sublayers — Krier's
    # platform/deployer compatibility (always on) and (when enabled)
    # Hadfield's licensed-regulator audit. Conflating them in a single
    # gate erased a substantive distinction Hadfield drew explicitly:
    # platforms gate on sector-and-alignment compatibility; licensed
    # regulators gate on per-prototype audit history. See
    # `docs/plans/regulator_market_split.md`.
    align_dist = np.abs(al_a - al_b)
    platform_reject = rngs["market"].random(n_pairs) < (
        0.02 + 0.06 * (1.0 - sec_aff) + 0.04 * align_dist
    )

    reg_cfg = topo.cfg.regulator
    eff_reg_coverage = (
        min(float(reg_cfg.coverage), float(pop.config.registration_coverage))
        if reg_cfg.enabled
        else 0.0
    )
    if reg_cfg.enabled and eff_reg_coverage > 0.0:
        from engine.core.institutions import compute_defect_score

        defect_per_proto = compute_defect_score(pop)
        defect_pair = np.maximum(defect_per_proto[a], defect_per_proto[b])
        audited = rngs["market"].random(n_pairs) < eff_reg_coverage
        regulator_reject = audited & (
            rngs["market"].random(n_pairs)
            < (
                float(reg_cfg.base_reject_rate)
                + float(reg_cfg.audit_quality) * defect_pair
            )
        )
    else:
        regulator_reject = np.zeros(n_pairs, dtype=bool)

    market_reject = platform_reject | regulator_reject

    # Alignment layer: individual-agent refusal. Higher alignment distance →
    # more refusal. Also: if either party's autonomy is very low, the agent
    # may decline on behalf of the principal.
    #
    # The binding term is `align_dist` (static pairwise distance) under the
    # original Krier-only formulation, and `max(|al_a - norm|, |al_b - norm|)`
    # under Hadfield's normative-competence reading when `NormConfig.enabled`
    # is True. The 0.20 coefficient is unchanged across regimes — see
    # `docs/plans/norm_evolution_alignment.md`.
    norm_cfg = pop.config.norm
    if norm_cfg.enabled and pop.community_norm is not None:
        if norm_cfg.stratify_by_stack:
            norm_a = pop.community_norm[stk_a]
            norm_b = pop.community_norm[stk_b]
        else:
            norm_a = pop.community_norm[0]
            norm_b = pop.community_norm[0]
        align_binding = np.maximum(np.abs(al_a - norm_a), np.abs(al_b - norm_b))
    else:
        align_binding = align_dist
    align_reject = rngs["alignment"].random(n_pairs) < (
        0.03 + 0.20 * align_binding * (1.0 - 0.5 * (auto_a + auto_b) / 2.0)
    )

    # Plan 7: mission-economy allocation. The coordinator scores every
    # candidate pair on (sector match, alignment toward the mission
    # anchor, capability) and captures the top `mission_share` by score.
    # Captured pairs bypass the platform and alignment gates — the
    # coordinator stands in for both — but pay `coordinator_overhead`
    # on their realised surplus and remain subject to the law and
    # regulator layers (coordinators are not above the law). At
    # `MissionConfig.enabled = False` (default) the mask is all-False
    # and the canonical Coasean path is bit-identical.
    mission_cfg = topo.cfg.mission
    if mission_cfg.enabled and mission_cfg.mission_share > 0.0:
        sectors = mission_cfg.objective_sectors
        if len(sectors) == 0:
            sector_match = np.ones(n_pairs, dtype=np.float32)
        else:
            sectors_arr = np.asarray(sectors, dtype=sec_a.dtype)
            sector_match = (
                np.isin(sec_a, sectors_arr) | np.isin(sec_b, sectors_arr)
            ).astype(np.float32)
        pair_align_mean = 0.5 * (al_a + al_b)
        align_match = 1.0 - np.abs(
            pair_align_mean - np.float32(mission_cfg.objective_alignment)
        )
        pair_cap_mean = 0.5 * (cap_a + cap_b)
        score = sector_match * align_match * pair_cap_mean
        target_pairs = int(n_pairs * mission_cfg.mission_share)
        target_pairs = min(max(target_pairs, 0), n_pairs - 1)
        if target_pairs > 0:
            mission_idx = np.argpartition(-score, target_pairs)[:target_pairs]
            mission_mask = np.zeros(n_pairs, dtype=bool)
            mission_mask[mission_idx] = True
        else:
            mission_mask = np.zeros(n_pairs, dtype=bool)
    else:
        mission_mask = np.zeros(n_pairs, dtype=bool)

    rejected_law_mask = law_reject
    # Mission allocation suppresses platform and alignment rejection on
    # captured pairs (the coordinator absorbs those gates); law and
    # regulator gates still apply.
    if mission_mask.any():
        platform_reject = platform_reject & ~mission_mask
        align_reject = align_reject & ~mission_mask
        market_reject = platform_reject | regulator_reject
    rejected_market_mask = (~rejected_law_mask) & market_reject
    # Platform-only rejections (those a platform would have caught even if
    # the regulator gate were absent). Used by the metrics layer to split
    # the market-reject share into "platform" and "regulator" panels —
    # the regulator slice is `rejected_market & ~platform_alone`.
    rejected_platform_mask = (~rejected_law_mask) & platform_reject
    rejected_regulator_mask = rejected_market_mask & ~rejected_platform_mask
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

    # Audit trail update for registered prototypes that participated this
    # step. `np.add.at` does the unbuffered scatter-add so duplicate
    # indices on either side accumulate correctly. `registered_active_share`
    # is reported back to metrics so the dashboard can show how much of
    # executed flow is identifiable. At `registration_coverage = 0.0`
    # this block is bit-identical to the no-op path: every `prototype_id`
    # is -1, both `reg_*` masks are all-False, no scatter writes happen.
    rejected_any_mask = (
        rejected_law_mask | rejected_market_mask | rejected_align_mask
    )
    reg_a_mask = pop.prototype_id[a] >= 0
    reg_b_mask = pop.prototype_id[b] >= 0
    if reg_a_mask.any() or reg_b_mask.any():
        accept_a = reg_a_mask & executed_mask
        accept_b = reg_b_mask & executed_mask
        reject_a = reg_a_mask & rejected_any_mask
        reject_b = reg_b_mask & rejected_any_mask
        if accept_a.any():
            np.add.at(pop.audit_acceptances, a[accept_a], 1)
        if accept_b.any():
            np.add.at(pop.audit_acceptances, b[accept_b], 1)
        if reject_a.any():
            np.add.at(pop.audit_rejections, a[reject_a], 1)
        if reject_b.any():
            np.add.at(pop.audit_rejections, b[reject_b], 1)
        if reg_a_mask.any():
            pop.audit_last_alignment[a[reg_a_mask]] = al_a[reg_a_mask]
        if reg_b_mask.any():
            pop.audit_last_alignment[b[reg_b_mask]] = al_b[reg_b_mask]

    # Gross surplus on executed pairs.
    pair_surplus = (base_surplus - cost) * executed_mask

    # Plan 7: coordinator overhead on captured-mission surplus. Acts as
    # a friction tax on the mission-allocated channel, capturing the
    # cost of the coordinator's coordination machinery itself. Off
    # when `mission.enabled=False`.
    if (
        mission_cfg.enabled
        and mission_mask.any()
        and mission_cfg.coordinator_overhead > 0.0
    ):
        overhead_factor = (
            1.0
            - mission_mask.astype(pair_surplus.dtype)
            * np.float32(mission_cfg.coordinator_overhead)
        )
        pair_surplus = pair_surplus * overhead_factor

    # Apply Matryoshka taxes (market + individual layers).
    real_tax_rate = topo.matryoshka_real_tax()
    real_pair_surplus = pair_surplus * (1.0 - real_tax_rate)

    # Pigouvian automation tax: per-pair tax proportional to the
    # automation gap (1 - demand_factor). H2H pays zero; A2A pays the
    # full rate. Revenue is collected here and recycled in World.step().
    pigouvian_cfg = topo.cfg.pigouvian
    if pigouvian_cfg.enabled and pigouvian_cfg.tax_rate > 0:
        pig_df = demand_factor(
            h_a, h_b, auto_a, auto_b, pigouvian_cfg.a2a_floor,
        )
        automation_gap = 1.0 - pig_df
        pigouvian_rate = pigouvian_cfg.tax_rate * automation_gap
        pigouvian_tax_pair = real_pair_surplus * pigouvian_rate
        real_pair_surplus_post_pig = real_pair_surplus * (1.0 - pigouvian_rate)
    else:
        pigouvian_tax_pair = None
        real_pair_surplus_post_pig = real_pair_surplus

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
    if pair_alpha is None:
        realized_alpha = float(topo.cfg.alpha)
    elif n_real > 0:
        realized_alpha = float((pair_alpha * executed_mask * pair_real_count).sum() / n_real)
    else:
        realized_alpha = float((pair_alpha * pair_real_count).sum() / max(pair_real_count.sum(), 1e-12))
    law_weak_surplus_loss = float((law_weak_loss_pair * pair_real_count).sum())
    law_capture_surplus_loss = float((law_capture_loss_pair * pair_real_count).sum())

    pigouvian_revenue = (
        float((pigouvian_tax_pair * pair_real_count).sum())
        if pigouvian_tax_pair is not None
        else 0.0
    )
    a2a_share, h2a_share, h2h_share = executed_interaction_shares(
        h_a, h_b, executed_mask, pair_real_count,
    )

    # Plan 7: mission diagnostics. `mission_executed_real` reads as
    # share of executed real-pair-count that came through the
    # coordinator allocation. `mission_overhead_real` is the surplus
    # share absorbed by `coordinator_overhead` on captured pairs (the
    # Tomašev "coordination cost is real" claim made measurable).
    if mission_cfg.enabled and mission_mask.any():
        mission_executed_real = float(
            ((mission_mask & executed_mask) * pair_real_count).sum()
        )
        if mission_cfg.coordinator_overhead > 0.0:
            # Approximation: coordinator_overhead * realised pre-overhead
            # surplus, summed over executed mission pairs in real units.
            # Using pre-overhead aggregate via inversion of the factor
            # would double-count the tax — instead, reconstruct from the
            # fraction. real_pair_surplus_post_pig already excludes
            # overhead; multiply by overhead/(1-overhead) to recover
            # the levied amount.
            f = float(mission_cfg.coordinator_overhead)
            mission_overhead_real = float(
                (
                    real_pair_surplus_post_pig
                    * mission_mask
                    * (f / max(1.0 - f, 1e-9))
                    * pair_real_count
                ).sum()
            )
        else:
            mission_overhead_real = 0.0
    else:
        mission_executed_real = 0.0
        mission_overhead_real = 0.0

    # Registered-active share: fraction of executed real-pair-count whose
    # either endpoint carries a stable id. Reuses the masks already built
    # for the audit-trail update; at coverage 0 every prototype_id is -1
    # so this aggregate is exactly 0.
    if n_real > 0:
        either_registered = (reg_a_mask | reg_b_mask)
        registered_active_share = float(
            ((either_registered & executed_mask) * pair_real_count).sum() / n_real
        )
    else:
        registered_active_share = 0.0

    # Norm-evolution observation: per-stack alignment-weighted sum and
    # weight from registered participants in this step's executed pairs.
    # `norm_obs_sum[k] / norm_obs_weight[k]` is the observed mean for
    # bucket k (the world step takes care of the divide and the empty-
    # bucket fallback). At `registration_coverage = 0`, no side qualifies
    # and both arrays are zero — the world step then leaves the norm at
    # its prior. See `docs/plans/norm_evolution_alignment.md`.
    if norm_cfg.enabled and pop.community_norm is not None:
        K = pop.community_norm.shape[0]
        contrib_reg_a = (reg_a_mask & executed_mask) * pair_real_count
        contrib_reg_b = (reg_b_mask & executed_mask) * pair_real_count
        if norm_cfg.stratify_by_stack:
            bucket_a = stk_a.astype(np.int64, copy=False)
            bucket_b = stk_b.astype(np.int64, copy=False)
        else:
            bucket_a = np.zeros(n_pairs, dtype=np.int64)
            bucket_b = np.zeros(n_pairs, dtype=np.int64)
        norm_obs_sum = np.bincount(
            bucket_a, weights=contrib_reg_a * al_a.astype(np.float64), minlength=K
        ) + np.bincount(
            bucket_b, weights=contrib_reg_b * al_b.astype(np.float64), minlength=K
        )
        norm_obs_weight = np.bincount(
            bucket_a, weights=contrib_reg_a, minlength=K
        ) + np.bincount(
            bucket_b, weights=contrib_reg_b, minlength=K
        )
        norm_obs_sum = norm_obs_sum.astype(np.float64, copy=False)
        norm_obs_weight = norm_obs_weight.astype(np.float64, copy=False)
        rejected_align_under_norm = float(
            (rejected_align_mask * pair_real_count).sum()
        )
    else:
        norm_obs_sum = None
        norm_obs_weight = None
        rejected_align_under_norm = 0.0

    # Demand-side feedback: only modulates the *authentic* aggregate.
    # `real_surplus_added` (above) stays un-modulated for backward
    # compatibility — every existing scenario pre-DemandConfig keeps the
    # same `real_welfare_cumulative`. The new authentic aggregate filters
    # surplus by whether it reaches a human consumer.
    if topo.cfg.demand.enabled:
        df = demand_factor(h_a, h_b, auto_a, auto_b, topo.cfg.demand.a2a_floor)
        real_surplus_authentic = float(
            (real_pair_surplus * df * pair_real_count).sum()
        )
    else:
        real_surplus_authentic = real_surplus

    # Wealth delta: split post-Pigouvian surplus 50/50 between the two
    # parties (Nash bargaining). When the Pigouvian tax is off,
    # real_pair_surplus_post_pig is identical to real_pair_surplus.
    half_surplus = real_pair_surplus_post_pig * 0.5
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
        real_surplus_authentic=real_surplus_authentic,
        law_weak_surplus_loss=law_weak_surplus_loss,
        law_capture_surplus_loss=law_capture_surplus_loss,
        pigouvian_revenue=pigouvian_revenue,
        realized_alpha=realized_alpha,
        a2a_share=a2a_share,
        h2a_share=h2a_share,
        h2h_share=h2h_share,
        registered_active_share=registered_active_share,
        rejected_platform_real=float(
            (rejected_platform_mask * pair_real_count).sum()
        ),
        rejected_regulator_real=float(
            (rejected_regulator_mask * pair_real_count).sum()
        ),
        mission_executed_real=mission_executed_real,
        mission_overhead_real=mission_overhead_real,
        norm_obs_sum=norm_obs_sum,
        norm_obs_weight=norm_obs_weight,
        rejected_align_under_norm=rejected_align_under_norm,
    )


def _coasean_step_chunked(
    pop: Population,
    topo: Topology,
    rng: RngOrRngs,
    n_pairs: int,
    base_match_volume: float,
    chunk_size: int,
    law_strength: float,
    law_capture: float,
    gini_wealth: float,
    local_alpha: np.ndarray | None = None,
) -> TransactionResult:
    """Process pairs in cache-friendly batches; aggregate exactly."""
    n = pop.n
    real_surplus = 0.0
    real_surplus_authentic = 0.0
    nominal_volume = 0.0
    n_real = 0.0
    rejected_law = 0.0
    rejected_market = 0.0
    rejected_align = 0.0
    rejected_cost = 0.0
    law_weak_surplus_loss = 0.0
    law_capture_surplus_loss = 0.0
    pigouvian_revenue = 0.0
    executed_alpha_weighted = 0.0
    all_pair_alpha_weighted = 0.0
    all_pair_alpha_weight = 0.0
    a2a_weighted = 0.0
    h2a_weighted = 0.0
    h2h_weighted = 0.0
    registered_weighted = 0.0
    rejected_align_under_norm = 0.0
    rejected_platform_real = 0.0
    rejected_regulator_real = 0.0
    mission_executed_real = 0.0
    mission_overhead_real = 0.0
    wealth_delta = np.zeros(n, dtype=np.float64)
    # Norm observations are aggregated as raw per-stack sum and weight so
    # the chunked path is bit-identical to the single-pass path under
    # associative addition. Lazily initialised to None so the canonical
    # path with `norm.enabled=False` returns no allocation.
    norm_obs_sum_total: np.ndarray | None = None
    norm_obs_weight_total: np.ndarray | None = None

    remaining = n_pairs
    while remaining > 0:
        batch = min(chunk_size, remaining)
        part = coasean_step(
            pop, topo, rng,
            n_pairs=batch,
            base_match_volume=base_match_volume,
            chunk_size=0,
            law_strength=law_strength,
            law_capture=law_capture,
            gini_wealth=gini_wealth,
            local_alpha=local_alpha,
        )
        real_surplus += part.real_surplus_added
        real_surplus_authentic += part.real_surplus_authentic
        nominal_volume += part.nominal_volume
        n_real += part.n_transactions_real
        rejected_law += part.rejected_law
        rejected_market += part.rejected_market
        rejected_align += part.rejected_align
        rejected_cost += part.rejected_cost
        law_weak_surplus_loss += part.law_weak_surplus_loss
        law_capture_surplus_loss += part.law_capture_surplus_loss
        pigouvian_revenue += part.pigouvian_revenue
        if part.n_transactions_real > 0:
            executed_alpha_weighted += part.realized_alpha * part.n_transactions_real
            a2a_weighted += part.a2a_share * part.n_transactions_real
            h2a_weighted += part.h2a_share * part.n_transactions_real
            h2h_weighted += part.h2h_share * part.n_transactions_real
            registered_weighted += part.registered_active_share * part.n_transactions_real
        all_pair_weight = (
            part.n_transactions_real
            + part.rejected_law
            + part.rejected_market
            + part.rejected_align
            + part.rejected_cost
        )
        all_pair_alpha_weighted += part.realized_alpha * all_pair_weight
        all_pair_alpha_weight += all_pair_weight
        wealth_delta += part.wealth_delta
        rejected_align_under_norm += part.rejected_align_under_norm
        rejected_platform_real += part.rejected_platform_real
        rejected_regulator_real += part.rejected_regulator_real
        mission_executed_real += part.mission_executed_real
        mission_overhead_real += part.mission_overhead_real
        if part.norm_obs_sum is not None:
            if norm_obs_sum_total is None:
                norm_obs_sum_total = part.norm_obs_sum.copy()
                norm_obs_weight_total = part.norm_obs_weight.copy()
            else:
                norm_obs_sum_total += part.norm_obs_sum
                norm_obs_weight_total += part.norm_obs_weight
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
        real_surplus_authentic=real_surplus_authentic,
        law_weak_surplus_loss=law_weak_surplus_loss,
        law_capture_surplus_loss=law_capture_surplus_loss,
        pigouvian_revenue=pigouvian_revenue,
        realized_alpha=(
            executed_alpha_weighted / n_real
            if n_real > 0
            else (
                all_pair_alpha_weighted / all_pair_alpha_weight
                if all_pair_alpha_weight > 0
                else float(topo.cfg.alpha)
            )
        ),
        a2a_share=a2a_weighted / n_real if n_real > 0 else 0.0,
        h2a_share=h2a_weighted / n_real if n_real > 0 else 0.0,
        h2h_share=h2h_weighted / n_real if n_real > 0 else 0.0,
        registered_active_share=(
            registered_weighted / n_real if n_real > 0 else 0.0
        ),
        norm_obs_sum=norm_obs_sum_total,
        norm_obs_weight=norm_obs_weight_total,
        rejected_align_under_norm=rejected_align_under_norm,
        rejected_platform_real=rejected_platform_real,
        rejected_regulator_real=rejected_regulator_real,
        mission_executed_real=mission_executed_real,
        mission_overhead_real=mission_overhead_real,
    )

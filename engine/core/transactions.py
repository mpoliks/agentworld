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
    rejected_permeability : number rejected at the cross-stack boundary
                            before any Matryoshka layer (W1c, Tomašev / Jacobs)
    rejected_law       : number rejected by law layer
    rejected_market    : number rejected by platform / market layer (Krier)
    rejected_regulator : number rejected by Hadfield third-party regulator
                         layer (W1a, Hadfield)
    rejected_align     : number rejected by alignment layer
    rejected_cost      : number rejected because cost > surplus
    wealth_delta       : per-prototype wealth change
"""

from __future__ import annotations

from dataclasses import dataclass, field
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
    "permeability",
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
class PairSample:
    """One per-pair record emitted for the live-engine exchange views.

    Engineered to be wire-cheap (~80 bytes per record) and renderable
    without further engine lookups. The fields are everything a UI
    needs to depict a single transaction: who, where (sector), what
    surplus, what friction, and whether it cleared.

    See `engine/core/transactions.py::_sample_pair_records` for how
    these are produced, and `docs/plans/live_engine.md` § V2 for the
    UI surfaces that consume them.
    """

    proto_a: int
    proto_b: int
    is_a_human: bool
    is_b_human: bool
    sec_a: int
    sec_b: int
    cap_a: float
    cap_b: float
    base_surplus: float
    friction: float
    real_surplus: float
    executed: bool
    reject_reason: str          # "" | "law" | "market" | "align" | "cost" | "permeability" | "regulator"
    pair_weight: float          # how many real pairs this prototype-pair represents


# Precedence order for reject reasons when multiple masks fire.
# Earlier gates take priority — the trade dies at the first wall it hits.
_REJECT_REASONS: tuple[str, ...] = (
    "law",
    "permeability",
    "regulator",
    "market",
    "align",
    "cost",
)


def _reject_reason_for(
    i: int,
    executed_mask: np.ndarray,
    rejected_law_mask: np.ndarray,
    rejected_market_mask: np.ndarray,
    rejected_align_mask: np.ndarray,
    rejected_cost_mask: np.ndarray,
    rejected_perm_mask: np.ndarray,
    rejected_regulator_mask: np.ndarray,
) -> str:
    if executed_mask[i]:
        return ""
    for name, mask in zip(
        _REJECT_REASONS,
        (
            rejected_law_mask,
            rejected_perm_mask,
            rejected_regulator_mask,
            rejected_market_mask,
            rejected_align_mask,
            rejected_cost_mask,
        ),
    ):
        if mask[i]:
            return name
    return "unknown"


def _sample_pair_records(
    k: int,
    sample_rng: np.random.Generator,
    *,
    a: np.ndarray,
    b: np.ndarray,
    h_a: np.ndarray,
    h_b: np.ndarray,
    sec_a: np.ndarray,
    sec_b: np.ndarray,
    cap_a: np.ndarray,
    cap_b: np.ndarray,
    base_surplus: np.ndarray,
    cost: np.ndarray,
    real_pair_surplus: np.ndarray,
    executed_mask: np.ndarray,
    rejected_law_mask: np.ndarray,
    rejected_market_mask: np.ndarray,
    rejected_align_mask: np.ndarray,
    rejected_cost_mask: np.ndarray,
    rejected_perm_mask: np.ndarray,
    rejected_regulator_mask: np.ndarray,
    pair_real_count: np.ndarray,
) -> list[PairSample]:
    """Sample K uniform-random pair indices and build PairSample records.

    Uses `sample_rng` exclusively so it doesn't disturb the engine's
    per-component RNG layout. When `k <= 0` or `n_pairs == 0`, returns
    an empty list with no rng consumption.
    """
    n = int(a.shape[0])
    if k <= 0 or n == 0:
        return []
    k = min(k, n)
    idx = sample_rng.choice(n, size=k, replace=False)
    out: list[PairSample] = []
    for i in idx:
        i = int(i)
        out.append(PairSample(
            proto_a=int(a[i]),
            proto_b=int(b[i]),
            is_a_human=bool(h_a[i]),
            is_b_human=bool(h_b[i]),
            sec_a=int(sec_a[i]),
            sec_b=int(sec_b[i]),
            cap_a=float(cap_a[i]),
            cap_b=float(cap_b[i]),
            base_surplus=float(base_surplus[i]),
            friction=float(cost[i]),
            real_surplus=float(real_pair_surplus[i]),
            executed=bool(executed_mask[i]),
            reject_reason=_reject_reason_for(
                i,
                executed_mask,
                rejected_law_mask, rejected_market_mask, rejected_align_mask,
                rejected_cost_mask, rejected_perm_mask, rejected_regulator_mask,
            ),
            pair_weight=float(pair_real_count[i]),
        ))
    return out


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
    # Cross-stack boundary rejections (W1c). Defaults to 0.0 so historical
    # scenarios that never set `cross_stack_permeability < 1.0` remain
    # bit-identical at the result-field level.
    rejected_permeability: float = 0.0
    # Hadfield regulator rejections (W1a). Distinct from `rejected_market`
    # (the platform/deployer gate). Defaults to 0.0 so historical scenarios
    # with `RegulatorConfig.enabled = False` remain bit-identical.
    rejected_regulator: float = 0.0
    # Share of unregistered endpoints whose registered bit was forged
    # to True in the regulator's view this step (S1 stretch). 0.0 when
    # `audit_tampering_rate = 0` or no unregistered endpoints appeared
    # in the sample. Read by `StepMetrics.forged_registration_share`.
    forged_registration_share: float = 0.0
    # Human-labor wage routed by the W2c labor wedge — surplus deducted
    # from the agent-side Nash split and disbursed to humans. Zero when
    # `LaborConfig.enabled = False`.
    human_labor_wage: float = 0.0
    # Per-sector aggregate of the wedge by `sec_a` (the production-side
    # sector). Sums to `human_labor_wage` by construction. Default
    # zeros-vector when `LaborConfig.enabled = False`.
    human_wage_per_sector: np.ndarray = field(
        default_factory=lambda: np.zeros(N_SECTORS, dtype=np.float64)
    )
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
    # Live-engine V2: K uniform-random per-pair records (default empty).
    # Populated by `coasean_step` only when `pair_sample_k > 0`. Each
    # record is a `PairSample` (~80 bytes). See `engine/core/transactions.py
    # ::_sample_pair_records` and `docs/plans/live_engine.md` § V2.
    pair_samples: list = field(default_factory=list)

    # Cockpit Phase 2: per-step real welfare bucketed by the production-
    # side sector (sec_a) of executed pairs. Length N_SECTORS = 12.
    # Sums (modulo rejected pairs) to `real_surplus_added`. Zero array
    # when nothing executes or chunking is exhausted.
    real_surplus_per_sector_step: np.ndarray = field(
        default_factory=lambda: np.zeros(N_SECTORS, dtype=np.float64)
    )


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
    *,
    pair_sample_k: int = 0,
    pair_sample_rng: np.random.Generator | None = None,
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
    shock, permeability gate — comes from one shared stream) or a
    mapping keyed by subsystem (`"market"`, `"alignment"`, `"law"`,
    `"network"`, `"demand"`, `"permeability"`) when the World was built
    with `WorldConfig.rng_split_mode == "per_component"`. In the
    per-component mode each gate consumes its own stream so that
    perturbing one subsystem's draw count cannot move another
    subsystem's draw sequence.
    """
    rngs = _resolve_rngs(rng)
    if 0 < chunk_size < n_pairs:
        return _coasean_step_chunked(
            pop, topo, rng, n_pairs, base_match_volume, chunk_size,
            law_strength, law_capture, gini_wealth, local_alpha,
            pair_sample_k=pair_sample_k,
            pair_sample_rng=pair_sample_rng,
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

    # ---- Permeability boundary (W1c) -----------------------------------------
    # Tomašev / Jacobs sandbox axis: cross-stack pairs may be blocked at the
    # boundary before any Matryoshka filter runs. Same-stack pairs are never
    # gated. With `cross_stack_permeability == 1.0` (historical default) the
    # rng is not consumed so canonical scenarios stay bit-identical.
    permeability = float(topo.cfg.cross_stack_permeability)
    if permeability < 1.0:
        cross_stack_mask = stk_a != stk_b
        permeability_draws = rngs["permeability"].random(n_pairs)
        rejected_perm_mask = cross_stack_mask & (permeability_draws >= permeability)
    else:
        rejected_perm_mask = np.zeros(n_pairs, dtype=bool)

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

    # Platform (Krier middle) layer: each platform/protocol has its own
    # filter, simulated as rejection probability that scales with
    # cross-sector and cross-alignment. Note: pre-W1a this was called
    # `market_reject` and the variable name is preserved for back-compat
    # with downstream telemetry; conceptually it now corresponds to the
    # platform/deployer gate, distinct from the Hadfield regulator gate
    # below (W1a in `docs/plans/hadfield_jacobs_robustness.md`).
    align_dist = np.abs(al_a - al_b)
    market_reject = rngs["market"].random(n_pairs) < (
        0.02 + 0.06 * (1.0 - sec_aff) + 0.04 * align_dist
    )

    # Regulator (W1a) layer: government-licensed third-party gate running
    # in parallel with the platform layer. Per-pair rejection probability
    # is `strength × audit_quality × (1 − capture)` evaluated at each
    # endpoint's stack vendor; the strictest jurisdiction binds. With
    # `regulator.enabled = False` (the default) the gate is skipped and
    # no rng draw is consumed, preserving canonical bit-identity.
    #
    # W2a coupling: when the registration regime is enabled, unregistered
    # *agent* endpoints bump their per-endpoint rejection probability by
    # `registration_floor`. Humans are exempt (registration is an
    # agent-side concept). The floor composes additively with the
    # vendor's base rejection and is clipped to [0, 1].
    reg_cfg = topo.cfg.regulator
    forged_registration_share = 0.0
    if reg_cfg.enabled:
        reg_strength, reg_capture, reg_audit = topo.regulator_vendor_arrays()
        p_reject_a = reg_strength[stk_a] * reg_audit[stk_a] * (1.0 - reg_capture[stk_a])
        p_reject_b = reg_strength[stk_b] * reg_audit[stk_b] * (1.0 - reg_capture[stk_b])
        reg2a_cfg = topo.cfg.registration
        if (
            reg2a_cfg.enabled
            and reg2a_cfg.registration_floor > 0.0
            and pop.registered is not None
        ):
            floor = float(reg2a_cfg.registration_floor)
            # Unregistered AGENT endpoints only — humans are exempt.
            unreg_a = (~pop.is_human[a]) & (~pop.registered[a])
            unreg_b = (~pop.is_human[b]) & (~pop.registered[b])
            # S1: audit-trail tampering. With `audit_tampering_rate > 0`,
            # the regulator's view of `registered` can be forged for an
            # unregistered endpoint with probability
            # `audit_tampering_rate × regulator_capture[stack]`. Forged
            # endpoints are *not* charged the registration floor — the
            # captured regulator can't tell they're unregistered. With
            # the rate at 0 (the default) no rng draw is consumed.
            audit_rate = float(reg_cfg.audit_tampering_rate)
            if audit_rate > 0.0:
                p_forge_a = audit_rate * reg_capture[stk_a]
                p_forge_b = audit_rate * reg_capture[stk_b]
                forge_a = unreg_a & (
                    rngs["regulator"].random(n_pairs) < p_forge_a
                )
                forge_b = unreg_b & (
                    rngs["regulator"].random(n_pairs) < p_forge_b
                )
                effective_unreg_a = unreg_a & ~forge_a
                effective_unreg_b = unreg_b & ~forge_b
                unreg_count = int(unreg_a.sum()) + int(unreg_b.sum())
                forged_registration_share = (
                    (int(forge_a.sum()) + int(forge_b.sum())) / unreg_count
                    if unreg_count > 0
                    else 0.0
                )
            else:
                effective_unreg_a = unreg_a
                effective_unreg_b = unreg_b
            # S3 stretch — multi-jurisdiction registration arbitrage. When
            # `Population.registration_stack` is populated, the floor bump
            # on agent `a` reads `a`'s registration stack's effective
            # regulator strength (`strength × audit × (1 − capture)`), not
            # the trading partner's stack. Agents who arbitraged to a lax
            # stack see a proportionally smaller floor. With the field at
            # `None` (the S3-off default) the floor is the flat `registration_floor`
            # value, preserving the pre-S3 contract.
            if pop.registration_stack is not None:
                reg_stack_a = pop.registration_stack[a]
                reg_stack_b = pop.registration_stack[b]
                eff_strength_a = (
                    reg_strength[reg_stack_a]
                    * reg_audit[reg_stack_a]
                    * (1.0 - reg_capture[reg_stack_a])
                )
                eff_strength_b = (
                    reg_strength[reg_stack_b]
                    * reg_audit[reg_stack_b]
                    * (1.0 - reg_capture[reg_stack_b])
                )
                p_reject_a = (
                    p_reject_a
                    + floor * eff_strength_a * effective_unreg_a.astype(np.float64)
                )
                p_reject_b = (
                    p_reject_b
                    + floor * eff_strength_b * effective_unreg_b.astype(np.float64)
                )
            else:
                p_reject_a = p_reject_a + floor * effective_unreg_a.astype(np.float64)
                p_reject_b = p_reject_b + floor * effective_unreg_b.astype(np.float64)
        p_reject = np.clip(np.maximum(p_reject_a, p_reject_b), 0.0, 1.0)
        regulator_reject = rngs["regulator"].random(n_pairs) < p_reject
    else:
        regulator_reject = np.zeros(n_pairs, dtype=bool)

    # Alignment layer: individual-agent refusal. Higher alignment distance →
    # more refusal. Also: if either party's autonomy is very low, the agent
    # may decline on behalf of the principal.
    #
    # W1b: when `NormsConfig.enabled = True`, replace the static-scalar
    # distance `|al_a − al_b|` with the L2 distance in the K-dim norm
    # space carried on `Population.norm_vector`. The rejection formula
    # structure is preserved so a K=1 norm with the same initial sd as
    # `alignment` gives back the legacy behaviour up to seed-of-init
    # noise (still gated on the flag for full bit-identity at off).
    # The default off path leaves `align_dist` at its scalar value.
    norms_cfg = topo.cfg.norms
    if norms_cfg.enabled and pop.norm_vector is not None:
        from engine.core.norms import norm_distance

        K = int(norms_cfg.n_dimensions)
        align_dist = norm_distance(
            pop.norm_vector[a], pop.norm_vector[b], K
        )
        base = float(norms_cfg.base_reject_rate)
        slope = float(norms_cfg.distance_slope)
    else:
        base = 0.03
        slope = 0.20
    align_reject = rngs["alignment"].random(n_pairs) < (
        base + slope * align_dist * (1.0 - 0.5 * (auto_a + auto_b) / 2.0)
    )

    # Permeability is the first gate; subsequent rejection buckets exclude
    # pairs already blocked at the boundary so the counts never double-count.
    # Regulator sits between the platform layer and the alignment layer in
    # the rejection cascade so its bucket is exclusive of upstream rejects.
    survives_perm = ~rejected_perm_mask
    rejected_law_mask = survives_perm & law_reject
    rejected_market_mask = survives_perm & (~rejected_law_mask) & market_reject
    rejected_regulator_mask = (
        survives_perm
        & (~rejected_law_mask)
        & (~rejected_market_mask)
        & regulator_reject
    )
    rejected_align_mask = (
        survives_perm
        & (~rejected_law_mask)
        & (~rejected_market_mask)
        & (~rejected_regulator_mask)
        & align_reject
    )

    # Surplus must exceed transaction cost to execute.
    cost_reject = base_surplus <= cost
    rejected_cost_mask = (
        survives_perm
        & (~rejected_law_mask)
        & (~rejected_market_mask)
        & (~rejected_regulator_mask)
        & (~rejected_align_mask)
        & cost_reject
    )

    executed_mask = ~(
        rejected_perm_mask
        | rejected_law_mask
        | rejected_market_mask
        | rejected_regulator_mask
        | rejected_align_mask
        | rejected_cost_mask
    )

    # Gross surplus on executed pairs.
    pair_surplus = (base_surplus - cost) * executed_mask

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

    # W2c labor wedge: a per-sector `labor_share`-fraction of cleared
    # surplus, attenuated by `(1 − automation_gap)`, is deducted from
    # the agent-side Nash split and routed to humans (proportional to
    # human importance weight). With `LaborConfig.enabled = False`
    # (the canonical default) the wedge is zero and the agent split
    # below is bit-identical to the pre-W2c body.
    labor_cfg = topo.cfg.labor
    if labor_cfg.enabled:
        labor_share_per_sector = topo.labor_share_arr()
        # The automation gap is what couples the Pigouvian tax and the
        # labor wedge to the same demand factor. Recompute here when
        # Pigouvian is off; reuse if it's on.
        if pigouvian_cfg.enabled and pigouvian_cfg.tax_rate > 0:
            labor_auto_gap = automation_gap  # already computed above
        else:
            labor_df = demand_factor(
                h_a, h_b, auto_a, auto_b, labor_cfg.a2a_floor,
            )
            labor_auto_gap = 1.0 - labor_df
        wedge_pair = (
            labor_share_per_sector[sec_a]
            * (1.0 - labor_auto_gap)
            * real_pair_surplus_post_pig
        )
        real_pair_surplus_to_split = real_pair_surplus_post_pig - wedge_pair
        # Per-sector aggregate by `sec_a` (the production-side sector;
        # same convention W2b's `coordinator_sectors` uses). Scalar total
        # stays as a convenience field for the metric reader; the
        # per-sector array is what routes the disbursement below.
        human_wage_per_sector = np.bincount(
            sec_a,
            weights=wedge_pair * pair_real_count,
            minlength=N_SECTORS,
        ).astype(np.float64)
        human_labor_wage = float(human_wage_per_sector.sum())
    else:
        wedge_pair = None
        real_pair_surplus_to_split = real_pair_surplus_post_pig
        human_labor_wage = 0.0
        human_wage_per_sector = np.zeros(N_SECTORS, dtype=np.float64)

    # Wealth delta: split the post-Pigouvian-post-wedge surplus 50/50
    # between the two parties (Nash bargaining). When the Pigouvian tax
    # and the labor wedge are both off, `real_pair_surplus_to_split` is
    # identical to `real_pair_surplus` and the pre-W2c math holds.
    half_surplus = real_pair_surplus_to_split * 0.5
    contrib_a = half_surplus * pair_real_count / w_a
    contrib_b = half_surplus * pair_real_count / w_b
    wealth_delta = np.bincount(a, weights=contrib_a, minlength=n)
    wealth_delta += np.bincount(b, weights=contrib_b, minlength=n)

    # Disburse the labor wedge to humans in the *production-side sector*
    # of each contributing pair (`sec_a`). The wedge attributes the wage
    # to where the work happens; high-A2A sectors concentrate wage
    # payments to humans living in those sectors. A sector with no
    # human prototypes (a possibility at small n) has its share fall
    # into the void — documented as structural, not a runtime accident.
    if labor_cfg.enabled and human_labor_wage > 0.0:
        for s in range(N_SECTORS):
            wage_s = float(human_wage_per_sector[s])
            if wage_s <= 0.0:
                continue
            mask_s = pop.is_human & (pop.sector == s)
            h_weight_s = pop.weight[mask_s].astype(np.float64)
            total_h_weight_s = float(h_weight_s.sum())
            if total_h_weight_s > 0:
                wealth_delta[mask_s] += wage_s / total_h_weight_s

    # W1b norm-participation update. Run *after* the wealth split so the
    # norms read this step are still the pre-update ones for the gate
    # above. When chunking is on (`_coasean_step_chunked` recursively
    # calls `coasean_step` with `chunk_size=0`), norms update once per
    # chunk rather than once per step — a known approximation that
    # produces qualitatively the same convergence dynamics at slightly
    # different numerical values. With `NormsConfig.enabled = False`
    # (the canonical default) the call is a no-op.
    if norms_cfg.enabled and pop.norm_vector is not None:
        from engine.core.norms import update_norm_vectors

        update_norm_vectors(
            pop, a, b, executed_mask, pair_real_count, norms_cfg,
        )

    # Cockpit Phase 2: per-step real welfare bucketed by production-side
    # sector. Cheap np.bincount over the per-pair arrays already in scope.
    real_surplus_per_sector_step = np.bincount(
        sec_a,
        weights=(real_pair_surplus_to_split * executed_mask * pair_real_count).astype(np.float64),
        minlength=N_SECTORS,
    )

    # Live-engine V2: sample K per-pair records for the exchange views.
    # No work when k <= 0; the sampling rng is isolated from the per-
    # component layout so canonical pinned outputs stay bit-identical.
    pair_samples_out: list = []
    if pair_sample_k > 0 and pair_sample_rng is not None:
        pair_samples_out = _sample_pair_records(
            pair_sample_k,
            pair_sample_rng,
            a=a, b=b,
            h_a=h_a, h_b=h_b,
            sec_a=sec_a, sec_b=sec_b,
            cap_a=cap_a, cap_b=cap_b,
            base_surplus=base_surplus_raw,
            cost=cost,
            real_pair_surplus=real_pair_surplus_to_split,
            executed_mask=executed_mask,
            rejected_law_mask=rejected_law_mask,
            rejected_market_mask=rejected_market_mask,
            rejected_align_mask=rejected_align_mask,
            rejected_cost_mask=rejected_cost_mask,
            rejected_perm_mask=rejected_perm_mask,
            rejected_regulator_mask=rejected_regulator_mask,
            pair_real_count=pair_real_count,
        )

    return TransactionResult(
        real_surplus_added=real_surplus,
        nominal_volume=nominal_volume,
        n_transactions_real=n_real,
        rejected_law=float((rejected_law_mask * pair_real_count).sum()),
        rejected_market=float((rejected_market_mask * pair_real_count).sum()),
        rejected_align=float((rejected_align_mask * pair_real_count).sum()),
        rejected_cost=float((rejected_cost_mask * pair_real_count).sum()),
        wealth_delta=wealth_delta,
        rejected_permeability=float((rejected_perm_mask * pair_real_count).sum()),
        rejected_regulator=float((rejected_regulator_mask * pair_real_count).sum()),
        real_surplus_authentic=real_surplus_authentic,
        law_weak_surplus_loss=law_weak_surplus_loss,
        law_capture_surplus_loss=law_capture_surplus_loss,
        pigouvian_revenue=pigouvian_revenue,
        realized_alpha=realized_alpha,
        a2a_share=a2a_share,
        h2a_share=h2a_share,
        h2h_share=h2h_share,
        human_labor_wage=human_labor_wage,
        human_wage_per_sector=human_wage_per_sector,
        forged_registration_share=forged_registration_share,
        pair_samples=pair_samples_out,
        real_surplus_per_sector_step=real_surplus_per_sector_step,
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
    *,
    pair_sample_k: int = 0,
    pair_sample_rng: np.random.Generator | None = None,
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
    rejected_permeability = 0.0
    rejected_regulator = 0.0
    human_labor_wage = 0.0
    human_wage_per_sector = np.zeros(N_SECTORS, dtype=np.float64)
    forged_share_num = 0.0
    forged_share_den = 0.0
    law_weak_surplus_loss = 0.0
    law_capture_surplus_loss = 0.0
    pigouvian_revenue = 0.0
    executed_alpha_weighted = 0.0
    all_pair_alpha_weighted = 0.0
    all_pair_alpha_weight = 0.0
    a2a_weighted = 0.0
    h2a_weighted = 0.0
    h2h_weighted = 0.0
    wealth_delta = np.zeros(n, dtype=np.float64)
    real_surplus_per_sector_step = np.zeros(N_SECTORS, dtype=np.float64)

    remaining = n_pairs
    remaining_k = pair_sample_k
    pair_samples_chunks: list = []
    while remaining > 0:
        batch = min(chunk_size, remaining)
        # Allocate pair-sample budget proportionally to chunk size; the
        # last chunk picks up any rounding leftover so the total lands
        # exactly at pair_sample_k.
        if pair_sample_k > 0 and pair_sample_rng is not None:
            is_last = (remaining == batch)
            chunk_k = (
                remaining_k
                if is_last
                else min(remaining_k, round(pair_sample_k * batch / n_pairs))
            )
            chunk_k = max(0, chunk_k)
        else:
            chunk_k = 0
        part = coasean_step(
            pop, topo, rng,
            n_pairs=batch,
            base_match_volume=base_match_volume,
            chunk_size=0,
            law_strength=law_strength,
            law_capture=law_capture,
            gini_wealth=gini_wealth,
            local_alpha=local_alpha,
            pair_sample_k=chunk_k,
            pair_sample_rng=pair_sample_rng,
        )
        if chunk_k > 0:
            pair_samples_chunks.extend(part.pair_samples)
            remaining_k -= chunk_k
        real_surplus += part.real_surplus_added
        real_surplus_authentic += part.real_surplus_authentic
        nominal_volume += part.nominal_volume
        n_real += part.n_transactions_real
        rejected_law += part.rejected_law
        rejected_market += part.rejected_market
        rejected_align += part.rejected_align
        rejected_cost += part.rejected_cost
        rejected_permeability += part.rejected_permeability
        rejected_regulator += part.rejected_regulator
        human_labor_wage += part.human_labor_wage
        human_wage_per_sector += part.human_wage_per_sector
        # Reconstruct the per-step share by weighting each chunk's share
        # by the chunk's "size". Without per-chunk unregistered counts we
        # use the chunk's n_pairs as a proxy; this matches the chunked
        # variant's other rate-style aggregations.
        forged_share_num += part.forged_registration_share * batch
        forged_share_den += batch
        law_weak_surplus_loss += part.law_weak_surplus_loss
        law_capture_surplus_loss += part.law_capture_surplus_loss
        pigouvian_revenue += part.pigouvian_revenue
        if part.n_transactions_real > 0:
            executed_alpha_weighted += part.realized_alpha * part.n_transactions_real
            a2a_weighted += part.a2a_share * part.n_transactions_real
            h2a_weighted += part.h2a_share * part.n_transactions_real
            h2h_weighted += part.h2h_share * part.n_transactions_real
        all_pair_weight = (
            part.n_transactions_real
            + part.rejected_law
            + part.rejected_market
            + part.rejected_align
            + part.rejected_cost
            + part.rejected_permeability
            + part.rejected_regulator
        )
        all_pair_alpha_weighted += part.realized_alpha * all_pair_weight
        all_pair_alpha_weight += all_pair_weight
        wealth_delta += part.wealth_delta
        real_surplus_per_sector_step += np.asarray(
            part.real_surplus_per_sector_step, dtype=np.float64
        )
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
        rejected_permeability=rejected_permeability,
        rejected_regulator=rejected_regulator,
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
        human_labor_wage=human_labor_wage,
        human_wage_per_sector=human_wage_per_sector,
        forged_registration_share=(
            forged_share_num / forged_share_den
            if forged_share_den > 0
            else 0.0
        ),
        pair_samples=pair_samples_chunks,
        real_surplus_per_sector_step=real_surplus_per_sector_step,
    )

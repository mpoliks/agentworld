"""
Imperial tracts — the third topology layer.

The exo position from the Biānjiè interview:

    "Empire is a really highly-scaled problem, it doesn't really go away.
    If you look at historical maps... you see these geological attractors
    (resources, terrain, water access, climate) that almost seem to
    consolidate and order imperial activity over millennia. Nation-states
    for us live 'within' those pre-inscribed imperial tracts and are
    constantly negotiating that upstream relationship."

This module models that as a third topology, *non-coextensive* with both
capital flow (which already happens at polity level) and polity governance
(drag, suppression). Tracts:

    - persist over the whole simulation (no schedule moves them)
    - are fewer than polities (n_tracts < n_regions, default 4 vs 12)
    - have a `resource_endowment` that multiplies last-mile capacity
    - have a `violence_floor` (gore-layer baseline; tracts inherit chronic
      violence from their imperial history)
    - have an `attractor_strength` that pools high-layer capital
    - extract a fraction of last-mile real welfare per step into nominal
      value at a high abstraction layer ("the lifted economy of empire")

The mapping `polity_to_tract` is randomized at world build, so each run has
a different imperial geography. The exo claim being tested is that imperial
attractor strength dominates polity-level cross-region compatibility for
long-run capital pooling.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from engine.exo.config import ImperialConfig


@dataclass
class ImperialState:
    """Per-tract state and per-polity tract membership."""

    polity_to_tract: np.ndarray  # (n_regions,) tract index per polity
    tract_polity_count: np.ndarray  # (n_tracts,) number of polities per tract
    resource_endowment: np.ndarray  # (n_tracts,) multiplies last-mile capacity
    attractor_strength: np.ndarray  # (n_tracts,) pulls high-layer capital
    violence_floor: np.ndarray  # (n_tracts,) chronic gore-layer violence
    extraction_intensity: np.ndarray  # (n_tracts,) per-step extraction rate
    extracted_total: np.ndarray  # (n_tracts,) cumulative real welfare extracted
    capital_pooled: np.ndarray  # (n_tracts,) cumulative high-layer capital pooled
    polity_extraction_total: np.ndarray  # (n_regions,) cumulative real extracted

    @classmethod
    def initialize(
        cls, cfg: ImperialConfig, n_regions: int, rng: np.random.Generator
    ) -> "ImperialState":
        n_tracts = cfg.n_tracts
        polity_to_tract = rng.choice(n_tracts, size=n_regions).astype(np.int32)
        tract_polity_count = np.array(
            [int((polity_to_tract == t).sum()) for t in range(n_tracts)],
            dtype=np.float64,
        )
        # Ensure no tract is empty: round-robin assign first n_tracts polities.
        if (tract_polity_count == 0).any():
            assignment = polity_to_tract.copy()
            for t in range(n_tracts):
                if tract_polity_count[t] == 0 and n_regions > t:
                    assignment[t] = t
            polity_to_tract = assignment
            tract_polity_count = np.array(
                [int((polity_to_tract == t).sum()) for t in range(n_tracts)],
                dtype=np.float64,
            )

        # Resource endowment: Dirichlet across tracts, normalized so mean = 1.
        endowment = rng.dirichlet(
            np.full(n_tracts, cfg.tract_resource_dirichlet)
        ) * n_tracts
        # Attractor strength: a separate Dirichlet — by design *not* aligned
        # with resource endowment, so resource-poor tracts can still pull
        # capital (the Niger / Congo / coltan pattern).
        attractor = rng.dirichlet(
            np.full(n_tracts, cfg.tract_attractor_dirichlet)
        ) * n_tracts
        # Inverted correlation between endowment and violence: high-extraction
        # tracts (low endowment, often) carry historical violence.
        violence_pressure = 1.0 - (endowment / endowment.max())
        violence_floor = cfg.historical_violence_floor * (0.4 + 1.6 * violence_pressure)
        # Extraction intensity: scaled by attractor strength (rich tracts
        # extract more from their polities).
        extraction_intensity = cfg.extraction_rate * (
            0.4 + 1.2 * attractor / attractor.max()
        )

        return cls(
            polity_to_tract=polity_to_tract,
            tract_polity_count=tract_polity_count,
            resource_endowment=endowment,
            attractor_strength=attractor,
            violence_floor=violence_floor,
            extraction_intensity=extraction_intensity,
            extracted_total=np.zeros(n_tracts, dtype=np.float64),
            capital_pooled=np.zeros(n_tracts, dtype=np.float64),
            polity_extraction_total=np.zeros(n_regions, dtype=np.float64),
        )

    @property
    def n_tracts(self) -> int:
        return self.attractor_strength.shape[0]

    # ---- per-polity lookups ---------------------------------------------

    def per_polity_capacity_multiplier(self) -> np.ndarray:
        return self.resource_endowment[self.polity_to_tract]

    def per_polity_violence_floor(self) -> np.ndarray:
        return self.violence_floor[self.polity_to_tract]

    def per_polity_extraction_rate(self) -> np.ndarray:
        return self.extraction_intensity[self.polity_to_tract]

    # ---- diagnostics ----------------------------------------------------

    def tract_capital_concentration(self) -> float:
        """Gini coefficient of cumulative pooled capital across tracts."""
        x = np.sort(np.maximum(self.capital_pooled, 0.0))
        n = len(x)
        if n == 0 or x.sum() == 0:
            return 0.0
        i = np.arange(1, n + 1, dtype=np.float64)
        return float((2.0 * (i * x).sum() - (n + 1) * x.sum()) / (n * x.sum()))

    def alignment_index(self, polity_real_balance: np.ndarray) -> float:
        """Polity-tract alignment: fraction of polities whose welfare balance
        is above the tract median.

        High alignment means imperial geography is benign to its constituents;
        low alignment means polities are net-extracted by their tract.
        """
        if polity_real_balance.size == 0:
            return 0.0
        alignment = 0.0
        for t in range(self.n_tracts):
            mask = self.polity_to_tract == t
            if not mask.any():
                continue
            wel = polity_real_balance[mask]
            med = float(np.median(wel))
            alignment += float((wel >= med).sum())
        return float(alignment / polity_real_balance.size)


def imperial_extraction_step(
    cfg: ImperialConfig,
    state: ImperialState,
    real_added_per_polity: np.ndarray,
    extraction_intensity_multiplier: float,
) -> dict:
    """Extract a fraction of last-mile real welfare per polity.

    Extracted real welfare leaves the polity. It re-enters the lifted economy
    as nominal value at `extraction_destination_layer`, *attributed to the
    polity it was extracted from* — so the polity's nominal stock grows at
    a high layer even as its real welfare shrinks. This models
    extraction-as-nominal-trade-balance (oil revenue, mineral royalties,
    cloud-seeded data exhaust).
    """
    rate = state.per_polity_extraction_rate() * float(extraction_intensity_multiplier)
    rate = np.clip(rate, 0.0, 0.6)
    extracted = real_added_per_polity * rate
    real_after = real_added_per_polity - extracted

    # Aggregate to tract for diagnostics.
    extraction_per_tract = np.zeros(state.n_tracts, dtype=np.float64)
    for t in range(state.n_tracts):
        mask = state.polity_to_tract == t
        if mask.any():
            extraction_per_tract[t] = extracted[mask].sum()
    state.extracted_total += extraction_per_tract
    state.polity_extraction_total += extracted

    return {
        "real_after_extraction_per_polity": real_after,
        "extracted_per_polity": extracted,
        "extraction_per_tract": extraction_per_tract,
        "extraction_rate_per_polity": rate,
    }


def imperial_pool_capital(
    cfg: ImperialConfig,
    state: ImperialState,
    stack_nominal: np.ndarray,
) -> dict:
    """Pool top-layer capital toward attractor tracts.

    For each of the top `cfg.pool_layers` abstraction layers, a `pool_share`
    fraction of nominal value is gathered into a global pot and redistributed
    across tracts proportional to attractor strength, then proportionally
    back to polities within each tract. This models the long-run gravitational
    pull of imperial attractors on lifted capital, *independent of polity-level
    cross-region compatibility* (which still operates separately).

    Modifies `stack_nominal` in place. Returns per-tract pooling deltas.
    """
    n_layers = stack_nominal.shape[1]
    pool_share = float(np.clip(cfg.capital_pooling_strength, 0.0, 0.6))
    if pool_share <= 0:
        return {"capital_pooled_per_tract": np.zeros(state.n_tracts)}

    attractor_w = state.attractor_strength / state.attractor_strength.sum()

    pooled_total = np.zeros(state.n_tracts, dtype=np.float64)
    n_pool = max(1, int(cfg.pool_layers))
    for k in range(n_layers - n_pool, n_layers):
        per_polity = stack_nominal[:, k].copy()
        # Tract sums.
        tract_sums = np.zeros(state.n_tracts, dtype=np.float64)
        for t in range(state.n_tracts):
            mask = state.polity_to_tract == t
            tract_sums[t] = per_polity[mask].sum()

        # Pooled mass redistributed by attractor weights; remaining stays
        # within each tract as before.
        pooled_mass = tract_sums.sum() * pool_share
        new_per_tract = tract_sums * (1.0 - pool_share) + pooled_mass * attractor_w
        pooled_total += new_per_tract - tract_sums

        # Distribute new tract totals back to polities proportional to their
        # prior share within the tract; if a polity had zero, distribute
        # equally among the tract's polities.
        for t in range(state.n_tracts):
            mask = state.polity_to_tract == t
            old = per_polity[mask].sum()
            if old > 1e-12:
                ratio = new_per_tract[t] / old
                stack_nominal[mask, k] = per_polity[mask] * ratio
            else:
                count = int(mask.sum())
                if count > 0:
                    stack_nominal[mask, k] = new_per_tract[t] / count

    state.capital_pooled += np.maximum(pooled_total, 0.0)
    return {"capital_pooled_per_tract": pooled_total}

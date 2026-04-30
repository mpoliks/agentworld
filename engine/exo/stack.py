"""
Stack — the abstraction stack that lift operates on.

State:
    nominal[r, k]   : nominal value at region r, layer k
    real[r]         : real welfare in region r (associated with last-mile)
    market_count[r, k] : number of distinct active markets at (r, k)
    referent_distance[r] : weighted-mean layer of nominal value in r

Per step, the operators in `engine.exo.world` mutate this state. The Stack
itself only knows how to apply a *lift cascade* one step deep, given a
per-region effective propensity. The orchestrator decides what propensity
to use.

Lift mechanics:
    For each layer k, a fraction of nominal[r, k] is *transformed* into
    nominal[r, k+1], multiplied by branching * nominal_multiplier. A small
    fraction of last-mile (layer 0) real welfare leaks per layer of lift
    activity (the friction of producing the abstraction).

Notes:
    The lift cascade is vectorized over (n_regions, n_layers - 1) in a
    single pass with `np.cumsum`-style accumulation: each layer k+1 receives
    contributions from all lower layers, weighted by their effective
    propensity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from engine.exo.config import StackConfig


@dataclass
class Stack:
    cfg: StackConfig
    nominal: np.ndarray  # (n_regions, n_layers) float64
    real: np.ndarray  # (n_regions,) float64
    market_count: np.ndarray  # (n_regions, n_layers) float64
    cumulative_lift: np.ndarray = field(default=None)  # cumulative nominal added (per region)

    @classmethod
    def empty(cls, cfg: StackConfig, n_regions: int) -> "Stack":
        return cls(
            cfg=cfg,
            nominal=np.zeros((n_regions, cfg.n_layers), dtype=np.float64),
            real=np.zeros(n_regions, dtype=np.float64),
            market_count=np.zeros((n_regions, cfg.n_layers), dtype=np.float64),
            cumulative_lift=np.zeros(n_regions, dtype=np.float64),
        )

    # ---- bookkeeping ------------------------------------------------------

    @property
    def n_regions(self) -> int:
        return self.nominal.shape[0]

    @property
    def n_layers(self) -> int:
        return self.nominal.shape[1]

    def total_nominal_per_region(self) -> np.ndarray:
        return self.nominal.sum(axis=1)

    def total_nominal(self) -> float:
        return float(self.nominal.sum())

    def total_real(self) -> float:
        return float(self.real.sum())

    def referent_distance(self) -> np.ndarray:
        """Weighted-mean abstraction layer per region (0 = last mile)."""
        layers = np.arange(self.n_layers, dtype=np.float64)
        weight = self.nominal.sum(axis=1, keepdims=False)
        weighted = (self.nominal * layers[None, :]).sum(axis=1)
        return np.where(weight > 0, weighted / np.maximum(weight, 1e-12), 0.0)

    def lift_index(self) -> np.ndarray:
        """Per-layer lift index: nominal[k] / nominal[0], with stable handling."""
        base = self.nominal[:, 0:1].sum(axis=1)
        base = np.maximum(base, 1e-12)
        return self.nominal.sum(axis=0) / max(base.sum(), 1e-12)

    # ---- last mile injection ---------------------------------------------

    def inject_last_mile(
        self,
        real_added_per_region: np.ndarray,
        nominal_added_per_region: np.ndarray,
    ) -> None:
        """Add a step's worth of last-mile production to layer 0 / real."""
        self.real += real_added_per_region
        self.nominal[:, 0] += nominal_added_per_region
        self.market_count[:, 0] += 0.5 * nominal_added_per_region

    def consume_real(self, consumption_per_region: np.ndarray) -> None:
        """Last-mile consumption draws down real welfare."""
        self.real = np.clip(self.real - consumption_per_region, 0.0, None)

    # ---- lift cascade -----------------------------------------------------

    def lift_step(
        self,
        effective_propensity: np.ndarray,
        rng: np.random.Generator,
    ) -> dict:
        """Apply one cascade of lift across the stack.

        `effective_propensity` is shape (n_regions, n_layers) with values in
        [0, 1]. It is computed by `world.py` from drag intensity, ontological
        variance, suppression posture, and depth decay.

        Returns a dict of per-region scalar deltas:
            nominal_added, real_lost, sub_markets_added, deepest_active_layer.
        """
        cfg = self.cfg
        nominal = self.nominal
        n_regions, n_layers = nominal.shape

        # Cap the per-step lift share so we don't fully drain a layer in one
        # step. Saturation is set in cfg.max_lift_share_per_step.
        lift_share = np.clip(
            effective_propensity * cfg.max_lift_share_per_step,
            0.0,
            cfg.max_lift_share_per_step,
        )

        # Lifted volume from each layer.
        lifted_nominal = nominal * lift_share

        # Vectorized cascade: each layer k+1 receives (lifted from k) *
        # branching * multiplier. Higher layers also get a *partial echo* from
        # two layers down, modeling fold-of-fold structure (each parent has a
        # small chance of placing a derivative two layers up directly).
        echo = 0.18

        new_nominal = nominal - lifted_nominal  # what stays at each layer
        for k in range(n_layers - 1):
            mult = cfg.fractal_branching * cfg.nominal_multiplier
            # Stochastic jitter on the multiplier so that we get realistic
            # heterogeneity across regions and runs.
            jitter = 1.0 + 0.08 * rng.standard_normal(n_regions)
            lifted = lifted_nominal[:, k] * mult * np.clip(jitter, 0.7, 1.4)
            new_nominal[:, k + 1] += lifted * (1.0 - echo)
            if k + 2 < n_layers:
                new_nominal[:, k + 2] += lifted * echo

        # Real leakage: per-region fraction of real welfare lost as friction
        # per active lift layer. Active = lift_share above 0.05.
        active_layers = (lift_share > 0.05).sum(axis=1).astype(np.float64)
        real_loss_frac = np.clip(
            cfg.real_leakage_per_layer * active_layers, 0.0, 0.6
        )
        real_lost_per_region = self.real * real_loss_frac

        # Apply.
        nominal_added_per_region = (new_nominal - nominal).sum(axis=1)
        self.cumulative_lift += np.maximum(nominal_added_per_region, 0.0)
        self.nominal = new_nominal
        self.real = np.maximum(self.real - real_lost_per_region, 0.0)

        # Each lift creates new markets (priced operations) at the destination
        # layer. Approximate as branching * lift_share at each layer.
        market_births = lift_share * cfg.fractal_branching
        market_births[:, 0] = 0.0  # markets are born at >= 1
        # Shift one column to deposit at the *next* layer.
        market_destination = np.zeros_like(market_births)
        market_destination[:, 1:] = market_births[:, :-1]
        self.market_count += market_destination

        active_mask = lift_share > 0.05
        layer_idx = np.arange(n_layers)
        deepest_active_layer = np.where(
            active_mask, layer_idx[None, :], -1
        ).max(axis=1)
        deepest_active_layer = np.maximum(deepest_active_layer, 0)

        return {
            "nominal_added_per_region": nominal_added_per_region,
            "real_lost_per_region": real_lost_per_region,
            "sub_markets_added_per_region": market_destination.sum(axis=1),
            "deepest_active_layer": deepest_active_layer,
        }

    # ---- structural growth -----------------------------------------------

    def spawn_markets(
        self,
        new_markets_per_region: np.ndarray,
        born_lifted_share: float,
        rng: np.random.Generator,
    ) -> dict:
        """Inject new markets created by the differential operator.

        Each new market lands at some layer. By default they land at layer 1
        (just above last mile). A `born_lifted_share` fraction of them land
        directly at higher layers, modelling SaaS / Web3 patterns.
        """
        cfg = self.cfg
        if not np.any(new_markets_per_region > 0):
            return {"nominal_added_per_region": np.zeros(self.n_regions)}

        born_lifted = new_markets_per_region * born_lifted_share
        born_low = new_markets_per_region - born_lifted

        # Low-born markets pump nominal at layer 1.
        layer1_inject = born_low * cfg.nominal_multiplier
        # High-born land at a randomly-sampled layer >= 2.
        high_layer_choices = np.clip(
            rng.integers(low=2, high=cfg.n_layers, size=self.n_regions),
            2,
            cfg.n_layers - 1,
        )
        nominal_added_per_region = np.zeros(self.n_regions)
        for r in range(self.n_regions):
            self.nominal[r, 1] += layer1_inject[r]
            self.market_count[r, 1] += born_low[r]
            if born_lifted[r] > 0:
                target = int(high_layer_choices[r])
                pump = born_lifted[r] * (cfg.nominal_multiplier ** (target - 0))
                self.nominal[r, target] += pump
                self.market_count[r, target] += born_lifted[r]
                nominal_added_per_region[r] += pump
            nominal_added_per_region[r] += layer1_inject[r]

        self.cumulative_lift += nominal_added_per_region
        return {"nominal_added_per_region": nominal_added_per_region}

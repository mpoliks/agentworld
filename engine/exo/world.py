"""
ExoWorld — the orchestrator for the exo-engine.

Per step:
    1. Last-mile production       (last_mile.last_mile_step)
    2. Drag step                  (drag.drag_step)
    3. Differential step          (differential.differential_step)
    4. Spawn new markets onto stack (stack.spawn_markets)
    5. Compute effective per-region per-layer lift propensity
    6. Lift cascade               (stack.lift_step)
    7. Last-mile consumption      (last_mile.last_mile_consumption)
    8. Cross-region capital flow  (this module)
    9. Record metrics             (metrics.compute_step_metrics)

The world owns:
    - a Stack (nominal / real / market_count)
    - a DragState
    - a LastMileState
    - a DifferentialState
    - region weights (size, cross-region compatibility)
    - an RNG
    - a MetricsHistory
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from engine.exo.config import ExoWorldConfig
from engine.exo.differential import DifferentialState, differential_step
from engine.exo.drag import (
    DragState,
    adaptive_dampener_update,
    drag_share_of_labor,
    drag_step,
)
from engine.exo.imperial import (
    ImperialState,
    imperial_extraction_step,
    imperial_pool_capital,
)
from engine.exo.last_mile import LastMileState, last_mile_consumption, last_mile_step
from engine.exo.metrics import MetricsHistory, StepMetrics, compute_step_metrics
from engine.exo.stack import Stack


@dataclass
class ExoWorld:
    cfg: ExoWorldConfig
    stack: Stack
    drag_state: DragState
    last_mile_state: LastMileState
    diff_state: DifferentialState
    imperial_state: Optional[ImperialState]
    region_size: np.ndarray  # (n_regions,) Dirichlet-drawn weights, sum to 1
    cross_region_compat: np.ndarray  # (n_regions, n_regions)
    rng: np.random.Generator
    history: MetricsHistory = field(default_factory=MetricsHistory)
    step_idx: int = 0
    _cum_real_produced: float = 0.0
    _cum_real_consumed: float = 0.0
    _cum_markets: float = 0.0
    _cum_imperial_extraction: float = 0.0

    @classmethod
    def build(cls, cfg: Optional[ExoWorldConfig] = None) -> "ExoWorld":
        if cfg is None:
            cfg = ExoWorldConfig()
        rng = np.random.default_rng(cfg.seed)
        n_regions = cfg.region.n_regions

        sizes = rng.dirichlet(np.full(n_regions, cfg.region.region_size_dirichlet))

        cross = np.full(
            (n_regions, n_regions), cfg.region.cross_region_compat, dtype=np.float64
        )
        np.fill_diagonal(cross, 1.0)

        # Initial ontological variance: small region-to-region differences.
        var0 = 0.6 + 0.3 * rng.random(n_regions)

        # Imperial state: separate RNG so changing polity-level seed doesn't
        # remix the imperial geography, and vice versa.
        if cfg.imperial.enabled:
            imp_rng = np.random.default_rng(cfg.imperial.seed)
            imperial_state = ImperialState.initialize(cfg.imperial, n_regions, imp_rng)
        else:
            imperial_state = None

        return cls(
            cfg=cfg,
            stack=Stack.empty(cfg.stack, n_regions),
            drag_state=DragState.empty(n_regions, initial_intensity=cfg.drag.target_intensity),
            last_mile_state=LastMileState.empty(
                n_regions, base_capacity=cfg.last_mile.base_physical_capacity
            ),
            diff_state=DifferentialState.empty(n_regions, initial_variance=var0),
            imperial_state=imperial_state,
            region_size=sizes,
            cross_region_compat=cross,
            rng=rng,
        )

    # ---- per-step --------------------------------------------------------

    def _scheduled(self, sched, default_value: float) -> float:
        if sched is None:
            return default_value
        idx = min(self.step_idx, len(sched) - 1)
        return float(sched[idx])

    def step(self) -> StepMetrics:
        cfg = self.cfg
        n_regions = self.cfg.region.n_regions

        # Apply schedules.
        target_drag_value = self._scheduled(
            cfg.drag_intensity_schedule, cfg.drag.target_intensity
        )
        target_supp_value = self._scheduled(
            cfg.suppression_strength_schedule, cfg.differential.suppression_strength
        )
        capacity_mult = self._scheduled(cfg.physical_capacity_schedule, 1.0)
        coasean_dampener_value = self._scheduled(
            cfg.coasean_dampener_schedule, cfg.drag.coasean_dampener
        )
        extraction_intensity_mult = self._scheduled(
            cfg.imperial.extraction_intensity_schedule, 1.0
        )

        # Apply scheduled attractor changes (long-run tract realignment).
        if (
            self.imperial_state is not None
            and cfg.imperial.attractor_schedule is not None
        ):
            sched = cfg.imperial.attractor_schedule
            idx = min(self.step_idx, len(sched) - 1)
            new_attr = sched[idx]
            if new_attr is not None:
                arr = np.asarray(new_attr, dtype=np.float64)
                if arr.shape == self.imperial_state.attractor_strength.shape:
                    # Smooth toward the new attractor map (geological time).
                    self.imperial_state.attractor_strength = (
                        0.85 * self.imperial_state.attractor_strength + 0.15 * arr
                    )

        # Vector targets (one per region; could be heterogeneous in the future).
        target_drag = np.full(n_regions, target_drag_value, dtype=np.float64)
        target_supp = np.full(n_regions, target_supp_value, dtype=np.float64)

        # ---- imperial overlays for last-mile -----------------------------
        if self.imperial_state is not None:
            per_region_capacity = self.imperial_state.per_polity_capacity_multiplier()
            per_region_violence = self.imperial_state.per_polity_violence_floor()
        else:
            per_region_capacity = None
            per_region_violence = None

        # 1. Last-mile production.
        lm = last_mile_step(
            cfg.last_mile,
            self.last_mile_state,
            region_size_weights=self.region_size,
            capacity_multiplier=capacity_mult,
            rng=self.rng,
            per_region_capacity_multiplier=per_region_capacity,
            per_region_violence_floor=per_region_violence,
        )
        real_added = lm["real_added_per_region"]
        nominal_added_l0 = lm["nominal_added_per_region"]
        violence_loss = lm["violence_loss_per_region"]

        # 1b. Imperial extraction: real welfare flows into a high abstraction
        # layer, attributed to the polity it was extracted from. The polity's
        # nominal stock at extraction_destination_layer grows as its real
        # welfare shrinks — extraction-as-nominal-trade-balance.
        extraction_step = 0.0
        if self.imperial_state is not None:
            ex = imperial_extraction_step(
                cfg.imperial,
                self.imperial_state,
                real_added_per_polity=real_added,
                extraction_intensity_multiplier=extraction_intensity_mult,
            )
            real_added = ex["real_after_extraction_per_polity"]
            extracted = ex["extracted_per_polity"]
            extraction_step = float(extracted.sum())
            self._cum_imperial_extraction += extraction_step
            # Add extracted nominal to the destination layer.
            dest = int(
                np.clip(
                    cfg.imperial.extraction_destination_layer,
                    0,
                    cfg.stack.n_layers - 1,
                )
            )
            self.stack.nominal[:, dest] += extracted

        self.stack.inject_last_mile(real_added, nominal_added_l0)
        self._cum_real_produced += float(real_added.sum())

        # 2. Drag step (with adaptive dampener if enabled).
        drag_cfg = cfg.drag
        # Carry the schedule's coasean dampener through the cfg copy
        # (also acts as the floor for the adaptive dampener).
        if coasean_dampener_value != drag_cfg.coasean_dampener:
            drag_cfg = type(drag_cfg)(
                **{**drag_cfg.__dict__, "coasean_dampener": coasean_dampener_value}
            )
        if drag_cfg.adaptive_dampener:
            new_dampener = adaptive_dampener_update(
                drag_cfg,
                prior_dampener=self.drag_state.coasean_dampener_level,
                real_per_region=self.stack.real,
                region_size=self.region_size,
            )
        else:
            new_dampener = np.full(
                n_regions,
                float(np.clip(drag_cfg.coasean_dampener, 0.0, 1.0)),
                dtype=np.float64,
            )
        ds = drag_step(
            drag_cfg,
            self.drag_state,
            target_intensity=target_drag,
            real_per_region=self.stack.real,
            rng=self.rng,
            dampener_per_region=new_dampener,
        )
        self.stack.consume_real(ds["real_consumed_per_region"])
        drag_propensity_boost = ds["lift_propensity_boost"]
        dampener_arr = ds["dampener_per_region"]

        # 3. Differential step.
        df = differential_step(
            cfg.differential,
            self.diff_state,
            target_suppression=target_supp,
            real_per_region=self.stack.real,
            rng=self.rng,
        )
        new_markets = df["new_markets_per_region"]
        suppression_cost = df["suppression_cost_per_region"]
        self.stack.consume_real(suppression_cost)
        self._cum_markets += float(new_markets.sum())

        # 4. Spawn new markets onto the stack.
        spawn_out = self.stack.spawn_markets(
            new_markets,
            born_lifted_share=cfg.differential.born_lifted_share,
            rng=self.rng,
        )

        # 5. Effective lift propensity.
        n_layers = cfg.stack.n_layers
        layer_decay = cfg.stack.lift_decay_with_depth ** np.arange(n_layers)

        variance_factor = 0.5 + 0.5 * (
            self.diff_state.ontological_variance / 1.5
        )

        suppression_factor = np.clip(1.0 - 0.6 * df["suppression_realised"], 0.05, 1.0)

        per_region_factor = (
            np.clip(0.4 + drag_propensity_boost, 0.0, 2.5)
            * variance_factor
            * suppression_factor
        )

        eff_prop = (
            cfg.stack.base_lift_propensity
            * layer_decay[None, :]
            * per_region_factor[:, None]
        )
        eff_prop = np.clip(eff_prop, 0.0, 1.0)

        # 6. Lift cascade.
        lift_out = self.stack.lift_step(eff_prop, rng=self.rng)

        # 7. Last-mile consumption.
        nominal_total_per_region = self.stack.nominal.sum(axis=1)
        consumption = last_mile_consumption(
            self.last_mile_state,
            drag_intensity=self.drag_state.intensity,
            nominal_total_per_region=nominal_total_per_region,
            real_stock_per_region=self.stack.real,
            cfg=cfg.last_mile,
        )
        consumption = np.minimum(consumption, self.stack.real)
        self.stack.consume_real(consumption)
        self._cum_real_consumed += float(consumption.sum())

        # 8. Cross-region capital flow (polity-level).
        flow_share = 0.04
        for k in (n_layers - 1, n_layers - 2):
            v = self.stack.nominal[:, k] * flow_share
            redistributed = self.cross_region_compat @ v
            redistributed *= v.sum() / max(redistributed.sum(), 1e-9)
            self.stack.nominal[:, k] -= v
            self.stack.nominal[:, k] += redistributed

        # 8b. Imperial capital pooling — non-coextensive with polity flows.
        if self.imperial_state is not None:
            imperial_pool_capital(
                cfg.imperial, self.imperial_state, self.stack.nominal
            )

        # 9. Metrics.
        deepest_active = int(np.max(lift_out["deepest_active_layer"]))
        if self.imperial_state is not None:
            polity_balance = self.stack.real
            imp_metrics = dict(
                imperial_extraction_step=extraction_step,
                imperial_extraction_total=self._cum_imperial_extraction,
                imperial_capital_concentration=self.imperial_state.tract_capital_concentration(),
                imperial_polity_alignment=self.imperial_state.alignment_index(
                    polity_balance
                ),
                imperial_capital_pooled_total=float(
                    self.imperial_state.capital_pooled.sum()
                ),
                imperial_violence_floor_mean=float(
                    self.imperial_state.violence_floor.mean()
                ),
                n_active_tracts=int(self.imperial_state.n_tracts),
            )
        else:
            imp_metrics = dict()

        m = compute_step_metrics(
            step=self.step_idx,
            nominal=self.stack.nominal,
            real=self.stack.real,
            real_produced_step=float(real_added.sum()),
            real_consumed_step=float(consumption.sum()),
            drag_intensity=self.drag_state.intensity,
            suppression=self.diff_state.suppression_realised,
            new_markets_step=float(new_markets.sum()),
            cumulative_markets=self._cum_markets,
            cumulative_lift=float(self.stack.cumulative_lift.sum()),
            cumulative_real_produced=self._cum_real_produced,
            suppression_welfare_cost_step=float(suppression_cost.sum()),
            drag_welfare_cost_step=float(ds["real_consumed_per_region"].sum()),
            violence_loss_step=float(violence_loss.sum()),
            deepest_active_layer=deepest_active,
            ontological_variance_mean=float(
                self.diff_state.ontological_variance.mean()
            ),
            coasean_dampener_mean=float(dampener_arr.mean()),
            coasean_dampener_max=float(dampener_arr.max()),
            **imp_metrics,
        )
        self.history.append(m)
        self.step_idx += 1
        return m

    def run(
        self,
        n_steps: Optional[int] = None,
        progress: bool = False,
        step_callback: Optional[Callable[[StepMetrics], None]] = None,
    ) -> MetricsHistory:
        """Run for n_steps. If `step_callback` is provided, it is invoked
        synchronously with each step's `StepMetrics`. Bit-identical to the
        no-callback path when `None`.
        """
        n = n_steps if n_steps is not None else self.cfg.n_steps
        if progress:
            try:
                from tqdm import trange

                iterator = trange(n, desc="exoworld", leave=False)
            except ImportError:
                iterator = range(n)
        else:
            iterator = range(n)
        for _ in iterator:
            m = self.step()
            if step_callback is not None:
                step_callback(m)
        return self.history

    # ---- snapshot --------------------------------------------------------

    def snapshot(self) -> dict:
        return {
            "step": self.step_idx,
            "n_regions": self.cfg.region.n_regions,
            "n_layers": self.cfg.stack.n_layers,
            "drag_share_of_labor": drag_share_of_labor(self.drag_state),
            "history": self.history.to_dict(),
        }

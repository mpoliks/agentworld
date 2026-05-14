"""
agentworld serve — FastAPI app with SSE streaming of step metrics.

A small dev-only HTTP layer that exposes the alpha-engine over the network so
a browser can watch a run progress step-by-step. Pairs with `dashboard/live.html`.

Design choices (per docs/plans/_archive/validation_lift_plus_live_viz.plan.md, B2):

- One FastAPI process. `localhost:8765` only (no LAN exposure by default).
- One run at a time per server process. POSTing /runs while a run is active
  cancels the prior run (via cooperative status flag — workers check between
  steps).
- The engine is unaware of the transport: `World.run(step_callback=...)` (B1)
  is the only contract. `serve.py` adapts the synchronous callback into an
  asyncio fan-out via `loop.call_soon_threadsafe`.
- Late-joining clients get the full `history` replayed before live events,
  so a tab opened halfway through a run sees every step.
- The serve layer does NOT touch CI or the batch runner. Imports of
  fastapi/uvicorn are local to this module so the rest of the package
  works on machines without those installed.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

# fastapi/uvicorn/pydantic are required for `import engine.serve` to succeed.
# `engine.cli` only imports this module inside the `serve` subcommand, so the
# rest of the package still works without these extras installed.
from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _step_metrics_to_dict(m: Any) -> dict:
    """Convert a StepMetrics dataclass to a JSON-friendly dict."""
    return asdict(m)


def _v2_subpayloads(step_payload: dict) -> list[tuple[str, dict]]:
    """Derive PR #5 SSE sub-events from a step payload.

    Returns a list of `(event_kind, sub_payload)` pairs for the dashboard
    channels:
      - `cast_snapshot_v2`: per-agent state for inspector cards.
      - `edges_v2`:         per-pair trade samples (sender/receiver,
                            surplus, reject reason) for the force-graph.
      - `folds_v2`:         per-depth fold-cascade contribution for the
                            fold-ring visualisation.

    Sub-events are emitted only when their source field is non-empty so
    that a scenario running without cast/sample/fold output does not
    flood the stream with empty events.
    """
    step_idx = int(step_payload.get("step", 0))
    out: list[tuple[str, dict]] = []
    snapshot = step_payload.get("cast_snapshot") or []
    if snapshot:
        out.append((
            "cast_snapshot_v2",
            {"step": step_idx, "snapshot": snapshot},
        ))
    samples = step_payload.get("pair_samples") or []
    if samples:
        out.append((
            "edges_v2",
            {"step": step_idx, "edges": samples},
        ))
    per_depth = step_payload.get("fold_per_depth_contribution") or []
    if per_depth:
        out.append((
            "folds_v2",
            {
                "step": step_idx,
                "per_depth": per_depth,
                "n_sub_markets_added": step_payload.get("n_sub_markets_added", 0.0),
                "fold_max_depth": step_payload.get("fold_max_depth", 0),
            },
        ))
    return out


class RunSession:
    """One scenario run, observed by zero or more SSE clients."""

    def __init__(
        self,
        run_id: str,
        scenario: str,
        n_steps: int,
        scale: str,
        seed: Optional[int],
        overrides: Optional[dict] = None,
        alpha_schedule: Optional[list] = None,
        family: Optional[str] = None,
        pair_sample_k: int = 0,
        continuous: bool = False,
        cast_size: int = 0,
    ) -> None:
        self.run_id = run_id
        self.scenario = scenario
        self.n_steps = n_steps
        self.scale = scale
        self.seed = seed
        self.overrides = dict(overrides) if overrides else {}
        self.alpha_schedule = list(alpha_schedule) if alpha_schedule else None
        self.family = family
        self.pair_sample_k = int(pair_sample_k)
        self.continuous = bool(continuous)
        self.cast_size = int(cast_size)
        # Live tuning: parameter overrides queued by POST /runs/{id}/update.
        # Drained by the worker between steps. Whitelist enforced at the
        # endpoint so only safe live-tunable fields land here.
        self.pending_overrides: dict = {}

        self.status: str = "queued"  # queued | running | done | error | cancelled
        self.error: Optional[str] = None
        self.history: list[dict] = []
        self.label: Optional[str] = None
        self.started_at: Optional[float] = None
        self.finished_at: Optional[float] = None

        # Cooperative cancellation: workers check between steps.
        self.cancel = threading.Event()

        # Subscribers are asyncio.Queue instances on the event loop.
        self.subscribers: set[asyncio.Queue] = set()
        self.lock = threading.Lock()
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    def publish_step(self, payload: dict) -> None:
        """Called from the worker thread once per step."""
        with self.lock:
            self.history.append(payload)
            subs = list(self.subscribers)
            loop = self.loop
        if loop is None:
            return
        for q in subs:
            loop.call_soon_threadsafe(q.put_nowait, ("step", payload))

    def publish_event(self, event: str, payload: dict) -> None:
        """Called from the worker thread for non-step events (done/error)."""
        with self.lock:
            subs = list(self.subscribers)
            loop = self.loop
        if loop is None:
            return
        for q in subs:
            loop.call_soon_threadsafe(q.put_nowait, (event, payload))

    def subscribe(self, q: asyncio.Queue) -> None:
        with self.lock:
            self.subscribers.add(q)

    def unsubscribe(self, q: asyncio.Queue) -> None:
        with self.lock:
            self.subscribers.discard(q)


def _run_worker(sess: RunSession) -> None:
    """Background-thread worker that drives one scenario."""
    from engine.core.world import World
    from engine.scale import Scale, apply_scale
    from engine.scenarios import get_scenario

    try:
        sess.status = "running"
        sess.started_at = time.time()
        cfg = get_scenario(sess.scenario)
        if sess.continuous:
            # 0 is the engine's continuous-mode signal; alpha_schedule is
            # incompatible (it has a finite length) so we strip it.
            cfg.n_steps = 0
            cfg.alpha_schedule = None
        elif sess.n_steps > 0:
            cfg.n_steps = sess.n_steps
        if sess.seed is not None:
            cfg.seed = int(sess.seed)
        if sess.overrides:
            _apply_overrides(cfg, sess.overrides)
        if sess.alpha_schedule is not None and not sess.continuous:
            cfg.alpha_schedule = list(sess.alpha_schedule)
        if sess.pair_sample_k > 0:
            cfg.pair_sample_k = sess.pair_sample_k
        if sess.cast_size > 0:
            cfg.cast_size = sess.cast_size
        cfg = apply_scale(cfg, Scale(sess.scale))
        world = World.build(cfg)

        def cb(m):
            if sess.cancel.is_set():
                # Cooperative cancellation: raise to break out of the run loop.
                raise _Cancelled()
            # Drain any pending live-tuning overrides and apply to the
            # live World config so the next step uses the new values.
            # Most engine reads pull from topology.cfg per step, so
            # changes show up immediately.
            if sess.pending_overrides:
                with sess.lock:
                    pending = sess.pending_overrides
                    sess.pending_overrides = {}
                if pending:
                    try:
                        _apply_overrides(world.cfg, pending, extend_bounds=True)
                    except OverrideError:
                        # Surface the error in the SSE event log but
                        # don't crash the run — the user's next nudge
                        # may be valid.
                        sess.publish_event("update_error", {"detail": "bad override"})
            sess.publish_step(_step_metrics_to_dict(m))

        try:
            world.run(progress=False, step_callback=cb)
        except _Cancelled:
            sess.status = "cancelled"
            sess.publish_event("cancelled", {"run_id": sess.run_id})
            return

        sess.label = world.topology.label()
        sess.status = "done"
        sess.publish_event(
            "done",
            {
                "run_id": sess.run_id,
                "label": sess.label,
                "n_steps": len(sess.history),
            },
        )
    except Exception as e:  # noqa: BLE001 — surface engine errors to the client
        sess.status = "error"
        sess.error = f"{type(e).__name__}: {e}"
        sess.publish_event("error", {"run_id": sess.run_id, "error": sess.error})
    finally:
        sess.finished_at = time.time()


class _Cancelled(Exception):
    """Internal: raised by the step callback to unwind a cancelled run."""


class OverrideError(ValueError):
    """A POST /runs override could not be applied."""


def _apply_overrides(cfg: Any, overrides: dict, *, extend_bounds: bool = False) -> None:
    """Apply a flat key → value override dict to a `WorldConfig`.

    Override keys may name a field on `WorldConfig` itself (e.g.
    `pairs_per_step`, `gini_every_k_steps`), a field on `cfg.topology`
    (e.g. `alpha`, `folding_propensity`), or a field on `cfg.population`
    (e.g. `agent_capability_mean`). Keys are resolved in that order; the
    first config carrying a dataclass field of that name wins.

    Live-engine parameters (the eight rows from
    `engine/data/live_parameter_meta.py`) are additionally bounds-checked
    against the N=2048 Sobol sampling box. Pass `extend_bounds=True` to
    skip the bounds check (advanced/exploratory mode).

    Raises `OverrideError` on unknown keys or out-of-bounds values.
    """
    from engine.data.live_parameter_meta import (
        LIVE_PARAMETERS_BY_NAME,
        is_within_bounds,
    )

    pop_fields = {f.name for f in dataclasses.fields(cfg.population)}
    topo_fields = {f.name for f in dataclasses.fields(cfg.topology)}
    world_fields = {f.name for f in dataclasses.fields(cfg)}

    for key, value in overrides.items():
        if not extend_bounds and key in LIVE_PARAMETERS_BY_NAME:
            try:
                fvalue = float(value)
            except (TypeError, ValueError) as exc:
                raise OverrideError(f"{key}={value!r}: not a number") from exc
            if not is_within_bounds(key, fvalue):
                p = LIVE_PARAMETERS_BY_NAME[key]
                raise OverrideError(
                    f"{key}={fvalue} outside Sobol bounds "
                    f"[{p['sobol_min']}, {p['sobol_max']}]"
                )

        # Resolution order: WorldConfig top-level → topology → population.
        if key in world_fields:
            setattr(cfg, key, value)
        elif key in topo_fields:
            setattr(cfg.topology, key, value)
        elif key in pop_fields:
            setattr(cfg.population, key, value)
        else:
            raise OverrideError(
                f"unknown override key {key!r} "
                "(not a field of WorldConfig, TopologyConfig, or PopulationConfig)"
            )


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------


class RunRequest(BaseModel):
    """Body for POST /runs. Module-level so FastAPI's forward-ref resolution
    finds it (function-local pydantic models trip TypeAdapter rebuild)."""

    scenario: str
    n_steps: int = Field(default=0, ge=0, description="0 = use scenario default")
    scale: str = Field(default="small")
    seed: Optional[int] = None
    # Live-engine parameter patch applied on top of the scenario's
    # WorldConfig. Keys are dataclass field names on WorldConfig,
    # TopologyConfig, or PopulationConfig. See engine/serve.py::
    # _apply_overrides for resolution order. Empty dict ⇒ no patch.
    overrides: dict = Field(default_factory=dict)
    # Piecewise-linear α(t) schedule. If provided, length must equal the
    # resolved n_steps (after scenario default if n_steps == 0). Overrides
    # topology.alpha per step. See engine/core/world.py for the consumer.
    alpha_schedule: Optional[list[float]] = None
    # Optional family hint. When provided, the server validates that the
    # chosen scenario lives in this family. Mismatch returns 400.
    family: Optional[str] = None
    # When True, override values are not checked against the Sobol
    # sampling box. Advanced/exploratory use only; the S1/ST anchor in
    # the UI is invalid outside the box.
    extend_bounds: bool = False
    # Live-engine V2: K per-pair records emitted alongside each step's
    # aggregate metrics. 0 (default) keeps canonical outputs
    # bit-identical and adds no wire overhead. Reasonable interactive
    # range is 50..500; the tape/grid/chord views consume the same
    # stream. See `engine/core/transactions.py::PairSample` and
    # `docs/plans/live_engine.md` § V2.
    pair_sample_k: int = Field(default=0, ge=0, le=5000)
    # Continuous mode: when True, the server runs the engine indefinitely
    # (until POST /runs/{id}/cancel arrives or a new run preempts).
    # Overrides `n_steps`. Combine with smaller `pairs_per_step` overrides
    # to make per-step work cheap so the stream feels continuous.
    continuous: bool = False
    # Cockpit Pass 2: persistent-cast size. >0 means the engine pins
    # that many prototypes at build time and emits their state per
    # step in `StepMetrics.cast_snapshot`. The live canvas reads from
    # there and animates each cast member step-to-step.
    cast_size: int = Field(default=0, ge=0, le=600)


def create_app():
    """Build the FastAPI app."""
    from engine.scenarios import list_scenarios

    @asynccontextmanager
    async def lifespan(app):
        app.state.loop = asyncio.get_running_loop()
        yield

    app = FastAPI(
        title="agentworld serve",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    # State carried on `app.state`. Tests construct a fresh app per case.
    app.state.current = None
    app.state.history_by_id = {}
    app.state.lock = threading.Lock()

    @app.get("/", include_in_schema=False)
    def index():
        live = DASHBOARD_DIR / "live.html"
        if live.exists():
            return RedirectResponse(url="/dashboard/live.html", status_code=307)
        return PlainTextResponse(
            "agentworld serve is running.\n\n"
            "POST /runs to start a scenario; GET /runs/{id}/stream for SSE.\n"
            "dashboard/live.html is not present yet (B3).",
            status_code=200,
        )

    if DASHBOARD_DIR.exists():
        # Serve the dashboard directory verbatim. StaticFiles handles MIME
        # types and traversal protection. Both index.html and live.html
        # use relative URLs (e.g. _tokens.css) which resolve correctly
        # under /dashboard/.
        #
        # Subclass StaticFiles to attach no-store cache headers — the
        # cockpit iterates fast and any browser caching of the JS
        # bundles produces the "looks broken" symptom where the page
        # is running stale code.
        class _NoCacheStatic(StaticFiles):
            async def get_response(self, path, scope):
                resp = await super().get_response(path, scope)
                resp.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
                resp.headers["Pragma"] = "no-cache"
                return resp
        app.mount(
            "/dashboard",
            _NoCacheStatic(directory=str(DASHBOARD_DIR), html=False),
            name="dashboard",
        )

    @app.get("/scenarios")
    def scenarios():
        return [{"name": n, "description": d} for n, d in list_scenarios()]

    @app.post("/runs")
    def start_run(req: RunRequest = Body(...)):
        from engine.scenarios import SCENARIOS
        from engine.scenarios.families import family_for, FAMILY_IDS

        if req.scenario not in SCENARIOS:
            raise HTTPException(status_code=404, detail=f"unknown scenario: {req.scenario}")

        # Family validation: if the request names a family, verify the
        # scenario belongs to it. Unknown family ids are also rejected.
        if req.family is not None:
            if req.family not in FAMILY_IDS:
                raise HTTPException(
                    status_code=400, detail=f"unknown family: {req.family}"
                )
            try:
                scenario_family = family_for(req.scenario)
            except KeyError:
                # Scenario exists but is not in the family registry
                # (likely an _anchored variant of a new scenario).
                raise HTTPException(
                    status_code=400,
                    detail=f"scenario {req.scenario!r} has no registered family",
                )
            if scenario_family != req.family:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"scenario {req.scenario!r} is in family "
                        f"{scenario_family!r}, not {req.family!r}"
                    ),
                )

        # Validate the override dict shape before spawning a worker so the
        # client gets a synchronous 400 instead of a deferred SSE error.
        if req.overrides or req.alpha_schedule is not None:
            from engine.scenarios import get_scenario as _get_scenario
            probe_cfg = _get_scenario(req.scenario)
            if req.overrides:
                try:
                    _apply_overrides(probe_cfg, req.overrides, extend_bounds=req.extend_bounds)
                except OverrideError as e:
                    raise HTTPException(status_code=400, detail=str(e))
            if req.alpha_schedule is not None:
                expected_len = req.n_steps if req.n_steps > 0 else probe_cfg.n_steps
                if len(req.alpha_schedule) != expected_len:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"alpha_schedule length {len(req.alpha_schedule)} "
                            f"!= n_steps {expected_len}"
                        ),
                    )
                if any(not (0.0 <= float(v) <= 1.0) for v in req.alpha_schedule):
                    raise HTTPException(
                        status_code=400,
                        detail="alpha_schedule values must each lie in [0, 1]",
                    )

        with app.state.lock:
            prior = app.state.current
            if prior is not None and prior.status in ("queued", "running"):
                # Cooperative cancel of prior run.
                prior.cancel.set()

            run_id = uuid.uuid4().hex[:12]
            sess = RunSession(
                run_id=run_id,
                scenario=req.scenario,
                n_steps=req.n_steps,
                scale=req.scale,
                seed=req.seed,
                overrides=req.overrides,
                alpha_schedule=req.alpha_schedule,
                family=req.family,
                pair_sample_k=req.pair_sample_k,
                continuous=req.continuous,
                cast_size=req.cast_size,
            )
            sess.loop = app.state.loop
            app.state.current = sess
            app.state.history_by_id[run_id] = sess

        thread = threading.Thread(target=_run_worker, args=(sess,), daemon=True)
        thread.start()
        return {
            "run_id": sess.run_id,
            "scenario": sess.scenario,
            "n_steps": sess.n_steps,
            "scale": sess.scale,
            "family": sess.family,
            "overrides": sess.overrides,
            "alpha_schedule_len": len(sess.alpha_schedule) if sess.alpha_schedule else 0,
            "pair_sample_k": sess.pair_sample_k,
            "continuous": sess.continuous,
            "cast_size": sess.cast_size,
        }

    @app.get("/scenarios/families")
    def scenario_families():
        from engine.scenarios import SCENARIOS
        from engine.scenarios.families import families_with_scenarios

        return families_with_scenarios(SCENARIOS.keys())

    @app.get("/parameter_meta")
    def parameter_meta():
        """Return the eight live-engine parameter records. The UI imports
        labels, tooltips, and Sobol bounds from here so the doc and the UI
        cannot drift. See `engine/data/live_parameter_meta.py`.
        """
        from engine.data.live_parameter_meta import (
            LIVE_PARAMETERS,
            SOBOL_METRICS,
        )

        return {
            "parameters": list(LIVE_PARAMETERS),
            "sobol_metrics": list(SOBOL_METRICS),
        }

    @app.get("/sobol_indices")
    def sobol_indices(metric: str = "log_exo_baroque_index"):
        """Return the pinned N=2048 Sobol indices for the requested metric.

        Reads `outputs/sensitivity/sobol_indices.n2048.json` once and
        caches in process memory. Returns S1, S1_conf, ST, ST_conf
        vectors per parameter name. The UI uses this for the badge
        attached to each slider row.
        """
        path = REPO_ROOT / "outputs" / "sensitivity" / "sobol_indices.n2048.json"
        if not path.exists():
            raise HTTPException(status_code=503, detail="sobol indices artifact missing")

        cache = getattr(app.state, "_sobol_cache", None)
        if cache is None:
            with path.open() as fh:
                cache = json.load(fh)
            app.state._sobol_cache = cache

        for entry in cache["indices"]:
            if entry["metric"] == metric:
                return {
                    "metric": metric,
                    "parameter_names": entry["parameter_names"],
                    "S1": entry["S1"],
                    "S1_conf": entry["S1_conf"],
                    "ST": entry["ST"],
                    "ST_conf": entry["ST_conf"],
                    "n_base_samples": cache.get("n_base_samples"),
                }
        raise HTTPException(status_code=404, detail=f"unknown sobol metric: {metric}")

    @app.post("/runs/{run_id}/cancel")
    def cancel_run(run_id: str):
        sess = app.state.history_by_id.get(run_id)
        if sess is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        sess.cancel.set()
        return {"run_id": run_id, "status": sess.status, "cancel_requested": True}

    # Mid-run parameter tuning. Whitelist restricted to fields the engine
    # reads per step — population params that shape build-time state
    # (agent_capability_mean, sd, network topology) won't take effect
    # mid-run and are rejected with 400 so the UI doesn't appear to apply
    # them when it can't.
    _LIVE_TUNABLE = {
        "alpha", "folding_propensity", "folding_branching",
        "base_friction", "base_variance_absorption",
        "max_productive_real_share", "fold_nominal_multiplier",
        "coase_exp", "cross_stack_compat", "market_layer_tax",
        "a2a_floor", "cap_slope", "productive_decay",
        "fold_real_efficiency",
    }

    @app.post("/runs/{run_id}/update")
    def update_run(run_id: str, body: dict = Body(...)):
        sess = app.state.history_by_id.get(run_id)
        if sess is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        if sess.status not in ("queued", "running"):
            raise HTTPException(status_code=409, detail=f"run is {sess.status}")
        overrides = body.get("overrides") or {}
        if not isinstance(overrides, dict):
            raise HTTPException(status_code=400, detail="overrides must be an object")
        bad = [k for k in overrides if k not in _LIVE_TUNABLE]
        if bad:
            raise HTTPException(
                status_code=400,
                detail=f"keys not live-tunable: {', '.join(bad)}",
            )
        with sess.lock:
            sess.pending_overrides.update(overrides)
        return {"run_id": run_id, "queued": dict(overrides)}

    @app.get("/runs/{run_id}/history")
    def get_history(run_id: str):
        sess = app.state.history_by_id.get(run_id)
        if sess is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        with sess.lock:
            return JSONResponse(
                {
                    "run_id": sess.run_id,
                    "scenario": sess.scenario,
                    "scale": sess.scale,
                    "status": sess.status,
                    "label": sess.label,
                    "error": sess.error,
                    "n_steps_target": sess.n_steps,
                    "history": list(sess.history),
                }
            )

    @app.get("/runs/{run_id}/stream")
    async def stream(run_id: str, request: Request):
        sess = app.state.history_by_id.get(run_id)
        if sess is None:
            raise HTTPException(status_code=404, detail="unknown run_id")

        async def event_gen():
            q: asyncio.Queue = asyncio.Queue()
            # Atomically: replay snapshot of history under the lock, then
            # subscribe so we don't miss steps that arrive between the
            # snapshot and the subscribe.
            with sess.lock:
                replay = list(sess.history)
                terminal_status = sess.status if sess.status in ("done", "error", "cancelled") else None
                sess.subscribers.add(q)

            try:
                meta = {
                    "run_id": sess.run_id,
                    "scenario": sess.scenario,
                    "scale": sess.scale,
                    "n_steps_target": sess.n_steps,
                    "history_len": len(replay),
                }
                yield f"event: hello\ndata: {json.dumps(meta)}\n\n"

                for ev in replay:
                    yield f"event: step\ndata: {json.dumps(ev)}\n\n"
                    for kind, sub in _v2_subpayloads(ev):
                        yield f"event: {kind}\ndata: {json.dumps(sub)}\n\n"

                if terminal_status is not None:
                    payload = {
                        "run_id": sess.run_id,
                        "label": sess.label,
                        "error": sess.error,
                        "n_steps": len(replay),
                    }
                    yield f"event: {terminal_status}\ndata: {json.dumps(payload)}\n\n"
                    return

                # Tail live events.
                while True:
                    if await request.is_disconnected():
                        return
                    try:
                        kind, payload = await asyncio.wait_for(q.get(), timeout=10.0)
                    except asyncio.TimeoutError:
                        # Heartbeat keeps the connection open through proxies.
                        yield ": ping\n\n"
                        continue
                    yield f"event: {kind}\ndata: {json.dumps(payload)}\n\n"
                    if kind == "step":
                        for sub_kind, sub in _v2_subpayloads(payload):
                            yield f"event: {sub_kind}\ndata: {json.dumps(sub)}\n\n"
                    if kind in ("done", "error", "cancelled"):
                        return
            finally:
                sess.unsubscribe(q)

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/healthz", include_in_schema=False)
    def health():
        return {"ok": True}

    return app


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, log_level: str = "info") -> None:
    """Run the SSE server. Blocks the calling thread."""
    import uvicorn

    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level=log_level)

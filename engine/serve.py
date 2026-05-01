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
    StreamingResponse,
)
from pydantic import BaseModel, Field


REPO_ROOT = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = REPO_ROOT / "dashboard"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _step_metrics_to_dict(m: Any) -> dict:
    """Convert a StepMetrics dataclass to a JSON-friendly dict."""
    return asdict(m)


class RunSession:
    """One scenario run, observed by zero or more SSE clients."""

    def __init__(
        self,
        run_id: str,
        scenario: str,
        n_steps: int,
        scale: str,
        seed: Optional[int],
    ) -> None:
        self.run_id = run_id
        self.scenario = scenario
        self.n_steps = n_steps
        self.scale = scale
        self.seed = seed

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
        if sess.n_steps > 0:
            cfg.n_steps = sess.n_steps
        if sess.seed is not None:
            cfg.seed = int(sess.seed)
        cfg = apply_scale(cfg, Scale(sess.scale))
        world = World.build(cfg)

        def cb(m):
            if sess.cancel.is_set():
                # Cooperative cancellation: raise to break out of the run loop.
                raise _Cancelled()
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
            return FileResponse(str(live))
        return PlainTextResponse(
            "agentworld serve is running.\n\n"
            "POST /runs to start a scenario; GET /runs/{id}/stream for SSE.\n"
            "dashboard/live.html is not present yet (B3).",
            status_code=200,
        )

    @app.get("/foldtree", include_in_schema=False)
    def foldtree():
        ft = DASHBOARD_DIR / "foldtree.html"
        if ft.exists():
            return FileResponse(str(ft))
        return PlainTextResponse(
            "dashboard/foldtree.html is not present yet (B4).",
            status_code=404,
        )

    @app.get("/dashboard/{filename}", include_in_schema=False)
    def dashboard_asset(filename: str):
        # Whitelist: only allow files inside DASHBOARD_DIR with safe names.
        safe = "".join(c for c in filename if c.isalnum() or c in "._-")
        if safe != filename:
            raise HTTPException(status_code=400, detail="bad filename")
        path = DASHBOARD_DIR / filename
        if not path.exists() or not path.is_file():
            raise HTTPException(status_code=404, detail="not found")
        return FileResponse(str(path))

    @app.get("/scenarios")
    def scenarios():
        return [{"name": n, "description": d} for n, d in list_scenarios()]

    @app.post("/runs")
    def start_run(req: RunRequest = Body(...)):
        from engine.scenarios import SCENARIOS
        if req.scenario not in SCENARIOS:
            raise HTTPException(status_code=404, detail=f"unknown scenario: {req.scenario}")

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
        }

    @app.post("/runs/{run_id}/cancel")
    def cancel_run(run_id: str):
        sess = app.state.history_by_id.get(run_id)
        if sess is None:
            raise HTTPException(status_code=404, detail="unknown run_id")
        sess.cancel.set()
        return {"run_id": run_id, "status": sess.status, "cancel_requested": True}

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

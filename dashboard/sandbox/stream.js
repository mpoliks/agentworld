// Stream subscriber for the spatial sandbox.
//
// `startStream(levers, handlers)` POSTs `/runs` with the lever-derived
// run config and subscribes to `/runs/{id}/stream` over SSE. Five event
// kinds (defined by engine/serve.py PR #5) are dispatched to the
// caller-supplied handlers:
//
//   onHello({run_id, scenario, scale, n_steps_target, history_len})
//   onStep(stepMetrics)                       — full StepMetrics dict
//   onCastSnapshot({step, snapshot})          — cast_snapshot_v2
//   onEdges({step, edges})                    — edges_v2
//   onFolds({step, per_depth, n_sub_markets_added, fold_max_depth})
//   onTerminal(kind, payload)                 — kind ∈ {done, error, cancelled}
//
// Returns `{ close, runId }`. `close()` aborts the EventSource without
// cancelling the engine run; pass the runId to `/runs/{id}/cancel` to
// stop the engine.

const noop = () => {};

export async function startStream(levers, handlers = {}) {
  const {
    onHello = noop,
    onStep = noop,
    onCastSnapshot = noop,
    onEdges = noop,
    onFolds = noop,
    onTerminal = noop,
    onConnectError = noop,
  } = handlers;

  const body = buildRunBody(levers);

  const res = await fetch('/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`POST /runs failed: ${res.status} ${text}`);
  }
  const { run_id: runId } = await res.json();

  const es = new EventSource(`/runs/${runId}/stream`);

  es.addEventListener('hello', (e) => onHello(parseData(e)));
  es.addEventListener('step', (e) => onStep(parseData(e)));
  es.addEventListener('cast_snapshot_v2', (e) => onCastSnapshot(parseData(e)));
  es.addEventListener('edges_v2', (e) => onEdges(parseData(e)));
  es.addEventListener('folds_v2', (e) => onFolds(parseData(e)));

  for (const kind of ['done', 'error', 'cancelled']) {
    es.addEventListener(kind, (e) => {
      const payload = parseData(e);
      onTerminal(kind, payload);
      es.close();
    });
  }

  es.onerror = () => {
    if (es.readyState === EventSource.CLOSED) {
      onConnectError();
    }
  };

  return {
    runId,
    close: () => es.close(),
  };
}

function parseData(e) {
  try { return JSON.parse(e.data); } catch (_) { return {}; }
}

// Map the dashboard's lever object to a RunRequest body. cast_size and
// pair_sample_k are both capped at 5000 by the engine API.
function buildRunBody(levers) {
  return {
    scenario: levers.scenario,
    scale: levers.scale,
    seed: levers.seed,
    continuous: true,
    n_steps: 0,
    cast_size: levers.cast_size,
    pair_sample_k: levers.pair_sample_k,
    overrides: levers.overrides || {},
  };
}

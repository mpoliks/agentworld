// Stream subscriber for the spatial sandbox.
//
// Spawns a module Web Worker (stream-worker.js) that owns the
// EventSource. The Worker thread is not subject to Chrome's
// background-tab throttling, so SSE events keep arriving even
// when the dashboard tab is hidden. The Worker postMessages each
// event back to the main thread where the handler callbacks run.
//
// `startStream(levers, handlers)` POSTs `/runs` (via the worker)
// and subscribes. Five event kinds are dispatched to the handlers:
//
//   onHello({run_id, scenario, scale, n_steps_target, history_len})
//   onStep(stepMetrics)                       — full StepMetrics dict
//   onCastSnapshot({step, snapshot})          — cast_snapshot_v2
//   onEdges({step, edges})                    — edges_v2
//   onFolds({step, per_depth, n_sub_markets_added, fold_max_depth})
//   onTerminal(kind, payload)                 — kind ∈ {done, error, cancelled}
//
// Returns `{ close, cancel, runId }`. `close()` aborts the
// EventSource without cancelling the engine run; `cancel()` also
// POSTs /runs/{id}/cancel via the worker. `runId` is exposed as a
// plain property after the start handshake completes.

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

  const worker = new Worker(new URL('./stream-worker.js', import.meta.url), { type: 'module' });

  let runId = null;
  const ready = new Promise((resolve, reject) => {
    let settled = false;
    worker.addEventListener('message', (e) => {
      const msg = e.data || {};
      switch (msg.type) {
        case 'runId':
          runId = msg.runId;
          if (!settled) { settled = true; resolve(); }
          break;
        case 'hello': onHello(msg.data); break;
        case 'step': onStep(msg.data); break;
        case 'cast_snapshot_v2': onCastSnapshot(msg.data); break;
        case 'edges_v2': onEdges(msg.data); break;
        case 'folds_v2': onFolds(msg.data); break;
        case 'terminal': onTerminal(msg.kind, msg.data); break;
        case 'connect_error': onConnectError(); break;
        case 'error':
          if (!settled) {
            settled = true;
            reject(new Error(msg.detail || 'stream worker error'));
          }
          break;
        default:
          break;
      }
    });
    worker.addEventListener('error', (e) => {
      if (!settled) {
        settled = true;
        reject(new Error(`worker error: ${e.message || 'unknown'}`));
      }
    });
  });

  worker.postMessage({ cmd: 'start', body: buildRunBody(levers) });
  await ready;

  return {
    get runId() { return runId; },
    close: () => worker.postMessage({ cmd: 'close' }),
    cancel: () => worker.postMessage({ cmd: 'cancel' }),
  };
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
    // Sandbox runs free of the Sobol sampling box — the user can
    // pull α past 0.95, folding_propensity past its prior bound,
    // etc. The Sobol bounds exist to keep the formal sensitivity
    // sweep on its calibrated grid; the sandbox is for exploration.
    extend_bounds: true,
  };
}

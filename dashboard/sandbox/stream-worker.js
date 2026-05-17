// Stream subscriber, Web Worker edition. The Worker thread is not
// subject to Chrome's background-tab throttling, so the EventSource
// keeps draining SSE events at full speed even when the dashboard
// tab is hidden. The main thread still processes those events on
// its own (throttled) cadence, but at least the network side stops
// stalling — the user sees per-tick TPS instead of 30-second
// silences followed by bursts.
//
// Protocol:
//   main → worker:  { cmd: 'start', body }    | { cmd: 'close' }    | { cmd: 'cancel' }
//   worker → main:  { type: 'runId', runId }
//                   { type: 'hello'|'step'|'cast_snapshot_v2'|'edges_v2'|'folds_v2', data }
//                   { type: 'terminal', kind: 'done'|'error'|'cancelled', data }
//                   { type: 'connect_error' }
//                   { type: 'error', detail }     (start-time failure)

let es = null;
let runId = null;

function dispatch(kind) {
  return (e) => {
    let data;
    try { data = JSON.parse(e.data); } catch (_) { data = {}; }
    self.postMessage({ type: kind, data });
  };
}

async function start(body) {
  try {
    const res = await fetch('/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      self.postMessage({ type: 'error', detail: `POST /runs failed: ${res.status} ${text}` });
      return;
    }
    const j = await res.json();
    runId = j.run_id;
    self.postMessage({ type: 'runId', runId });

    es = new EventSource(`/runs/${runId}/stream`);
    es.addEventListener('hello', dispatch('hello'));
    es.addEventListener('step', dispatch('step'));
    es.addEventListener('cast_snapshot_v2', dispatch('cast_snapshot_v2'));
    es.addEventListener('edges_v2', dispatch('edges_v2'));
    es.addEventListener('folds_v2', dispatch('folds_v2'));
    for (const kind of ['done', 'error', 'cancelled']) {
      es.addEventListener(kind, (e) => {
        let data; try { data = JSON.parse(e.data); } catch (_) { data = {}; }
        self.postMessage({ type: 'terminal', kind, data });
        if (es) { es.close(); es = null; }
      });
    }
    es.onerror = () => {
      if (es && es.readyState === EventSource.CLOSED) {
        self.postMessage({ type: 'connect_error' });
      }
    };
  } catch (err) {
    self.postMessage({ type: 'error', detail: String(err && err.message || err) });
  }
}

self.onmessage = (e) => {
  const msg = e.data || {};
  if (msg.cmd === 'start') {
    start(msg.body || {});
  } else if (msg.cmd === 'close') {
    if (es) { es.close(); es = null; }
  } else if (msg.cmd === 'cancel') {
    if (runId) {
      // Fire-and-forget — main thread doesn't wait on this.
      fetch(`/runs/${runId}/cancel`, { method: 'POST' }).catch(() => {});
    }
    if (es) { es.close(); es = null; }
  }
};

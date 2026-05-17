// Node harness for cluster_labels.js (Phase 2 §3.2 promotion-gate
// adversarial check). Reads a JSON spec describing per-tick raw
// partitions; runs them through createClusterLabels().update();
// reports per-tick diagnostics + final track status.
//
// Spec format:
//
//   {
//     "ticks": [
//       { "partition": [[agentIdx, rawCabalId], ...] },
//       ...
//     ],
//     "promoteWindow": 50,   // optional, defaults from module
//     "promoteMeanJ": 0.90,  // optional
//     "demoteWindow": 80,    // optional
//     "demoteMeanJ": 0.70    // optional
//   }
//
// Output:
//
//   {
//     "perTick": [{ tick, cabals, syndicates, missing, tracksTotal }],
//     "tracks": [{ stableId, status, age, memberCount, jaccardHistory }]
//   }

import { createClusterLabels } from '../cluster_labels.js';

function readStdin() {
  return new Promise((resolve, reject) => {
    let data = '';
    process.stdin.setEncoding('utf-8');
    process.stdin.on('data', (chunk) => { data += chunk; });
    process.stdin.on('end', () => resolve(data));
    process.stdin.on('error', reject);
  });
}

const text = await readStdin();
const spec = JSON.parse(text);
const labels = createClusterLabels({
  promoteWindow: spec.promoteWindow,
  promoteMeanJ: spec.promoteMeanJ,
  demoteWindow: spec.demoteWindow,
  demoteMeanJ: spec.demoteMeanJ,
  matchThreshold: spec.matchThreshold,
});
const perTick = [];
for (let t = 0; t < spec.ticks.length; t += 1) {
  const partition = new Map(spec.ticks[t].partition);
  labels.update(partition);
  const d = labels.diagnostics();
  perTick.push({
    tick: t,
    cabals: d.cabals,
    syndicates: d.syndicates,
    missing: d.missing,
    tracksTotal: d.tracksTotal,
  });
}
const tracks = labels.allTracks().map((t) => {
  const full = labels.trackOf(t.stableId);
  return {
    stableId: full.stableId,
    status: full.status,
    age: full.age,
    memberCount: full.memberCount,
    jaccardHistory: full.jaccardHistory.slice(),
  };
});
process.stdout.write(JSON.stringify({ perTick, tracks }));

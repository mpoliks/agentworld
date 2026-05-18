// Node harness for clusters_sbm.js (Phase 2 §3.2 follow-on
// adversarial checks). Exercises both the worker's pure Louvain
// (action='run') and the cross-validation hook on cluster_labels
// (action='labels-validate').

import { runJob } from '../clusters_sbm.js';
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

if (Number.isFinite(spec.seed)) {
  let s = (spec.seed | 0) >>> 0;
  Math.random = () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 0x100000000;
  };
}

if (spec.action === 'run') {
  const out = runJob(spec.edges);
  process.stdout.write(JSON.stringify({
    partition: out.partition,
    modularity: out.modularity,
    ms: out.ms,
  }));
} else if (spec.action === 'labels-validate') {
  // Build a labels instance, feed it the primary partition, then
  // call updateWithSecondary with the secondary. Reports the
  // first track's state.
  const labels = createClusterLabels({ matchThreshold: 0.0 });
  const primaryMap = new Map(spec.primary);
  labels.update(primaryMap);
  const secondaryMap = new Map(spec.secondary);
  labels.updateWithSecondary(secondaryMap);
  const all = labels.allTracks();
  if (all.length === 0) {
    process.stdout.write(JSON.stringify({ track: null }));
  } else {
    const full = labels.trackOf(all[0].stableId);
    process.stdout.write(JSON.stringify({
      track: {
        stableId: full.stableId,
        status: full.status,
        memberCount: full.memberCount,
        secondaryJaccard: full.secondaryJaccard,
        validated: full.validated,
      },
    }));
  }
} else {
  throw new Error('unknown action: ' + spec.action);
}

// Node test harness for clusters.js (Phase 2 §3.x adversarial
// checks). Reads a JSON spec from stdin, runs the requested
// scenarios through createClusters()._runLouvainOn, prints
// results as JSON on stdout. The Python test suite spawns this
// subprocess so the Louvain implementation is single-sourced in
// clusters.js — no Python port to drift.
//
// Spec format:
//
//   {
//     "cases": [
//       {
//         "name": "planted-sbm-1",
//         "edges": [[u, v, w], ...]
//       },
//       ...
//     ]
//   }
//
// Output:
//
//   {
//     "results": [
//       {
//         "name": "planted-sbm-1",
//         "partition": [[u, cabalId], ...],   // -1 = orphan
//         "modularity": 0.47,
//         "n_clustered": 300,
//         "n_cabals": 6
//       },
//       ...
//     ]
//   }

import { createClusters } from '../clusters.js';

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
const out = { results: [] };
for (const c of spec.cases) {
  const cl = createClusters();
  // Optionally seed Math.random for permutation-invariance tests.
  if (Number.isFinite(c.seed)) {
    let s = (c.seed | 0) >>> 0;
    Math.random = () => {
      s = (s * 1664525 + 1013904223) >>> 0;
      return s / 0x100000000;
    };
  }
  const r = cl._runLouvainOn(c.edges);
  const partition = [];
  const cabalSet = new Set();
  let nClustered = 0;
  for (const [u, cab] of r.partition) {
    partition.push([u, cab]);
    if (cab >= 0) {
      cabalSet.add(cab);
      nClustered += 1;
    }
  }
  out.results.push({
    name: c.name,
    partition,
    modularity: r.modularity,
    n_clustered: nClustered,
    n_cabals: cabalSet.size,
  });
}
process.stdout.write(JSON.stringify(out));

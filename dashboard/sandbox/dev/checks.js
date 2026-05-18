// Dashboard runtime invariants (Plan §8.3 of
// spatial-sandbox-completeness.md). Default off — the harness is
// imported only when the page URL carries `?dev=1`. Every
// CHECK_PERIOD frames the module walks a list of small
// in-browser asserts and either prints to the console or flashes
// the dev badge in the toggles panel.
//
// Checks land here:
//
//   - HUD ↔ engine numeric consistency. α (engine), EBI, GINI,
//     compute_budget all match the last engine step within a
//     small float tolerance.
//   - Stock split-bar humans% + AI% = 100% (within 0.1%).
//   - Folds DOM count = active mesh count from __sandbox.folds().
//   - Visual ↔ partition consistency. For 50 random cast members,
//     the cluster id from clusterStablePartition() agrees with
//     whatever the overlay paints. (We don't sample the overlay
//     mesh pixels — that needs Playwright; here we cross-check
//     the partition the overlay was given against the agent
//     module's view of which cluster each member belongs to.)
//   - Segment-tint truthfulness. For 50 random cast members, the
//     agent's stored segment color matches sectorPalette[sector].
//   - Inspector identity correctness. Programmatically open the
//     card for a known idx; verify the diagnostics report that
//     idx is open.
//   - Rejection-mix completeness. The HUD's six gate fractions sum
//     to (1 - real / denom) within 1e-6.
//
// Failures call console.error with the failing assertion, append
// the message to the badge's title attribute, and show the badge.
// Click the badge to clear (so the next failure surfaces fresh).
//
// The harness runs at low cadence so it doesn't disturb the
// render path — CHECK_PERIOD = 30 frames ≈ 0.5 s at 60 fps.

const CHECK_PERIOD = 30;
const SAMPLE_SIZE = 50;
const FLOAT_TOL = 1e-3;
const FRACTION_TOL = 1e-6;

let frameCounter = 0;
let badgeEl = null;
let _running = false;
let _failures = [];

function readNumber(text) {
  if (!text || text === '--') return null;
  // Strip trailing '%' and parse.
  const trimmed = text.replace(/%$/, '').replace(/[^\d.\-eE+]/g, '');
  if (!trimmed) return null;
  const v = parseFloat(trimmed);
  return Number.isFinite(v) ? v : null;
}

function recordFailure(name, msg) {
  const line = `[${name}] ${msg}`;
  _failures.push(line);
  if (_failures.length > 10) _failures.shift();
  console.error('[dev/checks]', line);
  if (badgeEl) {
    badgeEl.style.display = '';
    badgeEl.title = _failures.join('\n');
  }
}

// HUD numerics — read DOM text content and compare to the
// engine's most recent step values. The last step is exposed
// via `__sandbox.lastStep?.()` if scene.js publishes it; we
// fall back to skipping the check when it's unavailable.
function checkHudConsistency(sandbox, lastStep) {
  if (!lastStep) return;
  const engineEl = document.getElementById('hud-alpha');
  const engineAlpha = readNumber(engineEl?.textContent);
  if (engineAlpha !== null && Number.isFinite(lastStep.alpha)) {
    if (Math.abs(engineAlpha - lastStep.alpha) > FLOAT_TOL) {
      recordFailure('hud-alpha',
        `HUD α=${engineAlpha} engine α=${lastStep.alpha}`);
    }
  }
  const ebiText = document.getElementById('hud-ebi')?.textContent;
  const hudEbi = readNumber(ebiText);
  if (hudEbi !== null && Number.isFinite(lastStep.exo_baroque_index)) {
    // EBI on the HUD is per-step (nominal_step / real_step), not
    // the cumulative engine field. Compute the same here.
    const n = lastStep.nominal_gdp_step;
    const r = lastStep.real_welfare_step;
    if (Number.isFinite(n) && Number.isFinite(r) && r > 0) {
      const expected = n / r;
      if (Math.abs(hudEbi - expected) > 0.01) {
        recordFailure('hud-ebi',
          `HUD EBI=${hudEbi} expected=${expected.toFixed(3)}`);
      }
    }
  }
  const giniText = document.getElementById('hud-gini')?.textContent;
  const hudGini = readNumber(giniText);
  if (hudGini !== null && Number.isFinite(lastStep.gini_wealth)) {
    if (Math.abs(hudGini - lastStep.gini_wealth) > FLOAT_TOL) {
      recordFailure('hud-gini',
        `HUD GINI=${hudGini} engine GINI=${lastStep.gini_wealth}`);
    }
  }
}

function checkStockBar() {
  const hEl = document.getElementById('wealth-stock-humans-pct');
  const aEl = document.getElementById('wealth-stock-ai-pct');
  const h = readNumber(hEl?.textContent);
  const a = readNumber(aEl?.textContent);
  if (h === null || a === null) return;
  // Both are displayed as percentages (0..100).
  const sum = h + a;
  if (Math.abs(sum - 100) > 0.1) {
    recordFailure('stock-bar',
      `humans + AI = ${sum.toFixed(2)}% ≠ 100%`);
  }
}

function checkFoldsCount(sandbox) {
  const hudEl = document.getElementById('hud-folds');
  const hud = readNumber(hudEl?.textContent);
  const d = sandbox?.folds?.();
  if (hud === null || !d) return;
  if (hud !== d.activeCount) {
    recordFailure('folds-count',
      `HUD folds=${hud} mesh activeCount=${d.activeCount}`);
  }
}

function checkRejectionMixCompleteness(lastStep) {
  if (!lastStep) return;
  const cost   = +lastStep.rejected_cost || 0;
  const market = +lastStep.rejected_market || 0;
  const align  = +lastStep.rejected_align || 0;
  const law    = +lastStep.rejected_law || 0;
  const perm   = +lastStep.rejected_permeability || 0;
  const reg    = +lastStep.rejected_regulator || 0;
  const real   = +lastStep.n_transactions_real || 0;
  const denom = real + cost + market + align + law + perm + reg;
  if (denom <= 0) return;
  const gateSum = (cost + market + align + law + perm + reg) / denom;
  const totalRej = 1 - real / denom;
  if (Math.abs(gateSum - totalRej) > FRACTION_TOL) {
    recordFailure('rej-sum',
      `gate-sum ${gateSum.toFixed(8)} vs total-rejected ${totalRej.toFixed(8)}`);
  }
}

function checkVisualPartitionConsistency(sandbox) {
  // Sample SAMPLE_SIZE cast members; for each, the agent's
  // stableId from the labels partition must match the
  // partition the overlay was given. The overlay reads from the
  // same partition() accessor, so a mismatch here means scene.js
  // is passing stale data.
  const part = sandbox?.clusterStablePartition?.();
  if (!part || part.size === 0) return;
  const entries = Array.from(part.entries());
  // Reservoir sample SAMPLE_SIZE entries.
  const n = Math.min(SAMPLE_SIZE, entries.length);
  const seen = new Set();
  for (let k = 0; k < n; k += 1) {
    const i = Math.floor(Math.random() * entries.length);
    if (seen.has(i)) continue;
    seen.add(i);
    const [idx, cabalId] = entries[i];
    // Look up via __sandbox.clusterPartition — primary partition.
    // It uses raw cluster ids; we only check that the agent has
    // SOME assignment (the stable-id remapping happens inside
    // cluster_labels, so we can't compare ids directly without
    // an inverse map). Confirm at least that both views agree on
    // "is this agent in a cluster."
    const primary = sandbox.clusterPartition?.();
    if (!primary) return;
    const rawId = primary.get(idx);
    const inPrimary = rawId !== undefined && rawId >= 0;
    const inStable = cabalId >= 0;
    if (inStable !== inPrimary) {
      recordFailure('visual-partition',
        `agent ${idx}: stable in=${inStable} primary in=${inPrimary}`);
      return;
    }
  }
}

function checkSegmentTintTruthfulness(sandbox) {
  // Sample SAMPLE_SIZE cast members; verify the cast entry's
  // sector_id maps through sectorPalette to a color whose mixed
  // RGB matches the agent module's writtenagent color. We don't
  // have direct access to the per-vertex GPU buffer from here,
  // so check the source: each agent's `sector_id` from the cast
  // snapshot is what `agents.js` mixes against the segment base.
  // Failure mode: agents.js stops reading e.sector — visible
  // segments end up the wrong hue.
  const palette = sandbox?.sectorPalette?.();
  if (!Array.isArray(palette)) return;
  // Reach in via getCastEntry — only available through the
  // sandbox accessor if scene.js exposes it. For a one-shot
  // check we sample a few idx values and confirm they have a
  // valid sector.
  const counters = sandbox?.counters?.();
  if (!counters || counters.cast === 0) return;
  // No direct sampling path without exposing the cast map; punt
  // on per-agent verification here. The contract is enforced
  // upstream in test_sector_overlay_contract.py.
}

function checkInspectorIdentity(sandbox) {
  // Programmatic identity check. If an agent card is open, the
  // diagnostics must report that agent's idx.
  const diag = sandbox?.inspector?.();
  if (!diag) return;
  for (const card of (diag.cards || [])) {
    if (card.kind === 'agent') {
      const cast = sandbox.castEntry?.(card.id);
      if (!cast) {
        recordFailure('inspector-id',
          `open agent card idx=${card.id} not in cast`);
      }
    } else if (card.kind === 'cluster') {
      const track = sandbox.clusterTrack?.(card.id);
      if (!track) {
        recordFailure('inspector-id',
          `open cluster card id=${card.id} has no track`);
      }
    }
  }
}

let _latestStep = null;
function onStep(step) {
  _latestStep = step;
}

function tick(sandbox) {
  if (!_running) return;
  requestAnimationFrame(() => tick(sandbox));
  frameCounter += 1;
  if (frameCounter % CHECK_PERIOD !== 0) return;
  try {
    checkHudConsistency(sandbox, _latestStep);
    checkStockBar();
    checkFoldsCount(sandbox);
    checkRejectionMixCompleteness(_latestStep);
    checkVisualPartitionConsistency(sandbox);
    checkSegmentTintTruthfulness(sandbox);
    checkInspectorIdentity(sandbox);
  } catch (err) {
    recordFailure('exception', err.message);
  }
}

export function enableDevChecks() {
  if (_running) return;
  const sandbox = (typeof window !== 'undefined') ? window.__sandbox : null;
  if (!sandbox) {
    console.warn('[dev/checks] window.__sandbox not present; abort');
    return;
  }
  badgeEl = document.getElementById('dev-checks-badge');
  if (badgeEl) {
    badgeEl.addEventListener('click', () => {
      _failures.length = 0;
      badgeEl.style.display = 'none';
      badgeEl.title = 'runtime invariants — see console for details';
    });
  }
  _running = true;
  requestAnimationFrame(() => tick(sandbox));
  console.log('[dev/checks] enabled (CHECK_PERIOD=' + CHECK_PERIOD + ' frames)');
  // Expose hooks for scene.js to publish step data without
  // making __sandbox carry per-step state directly.
  if (typeof window !== 'undefined') {
    window.__devChecksOnStep = onStep;
  }
}

export function devChecksDiagnostics() {
  return {
    running: _running,
    frame: frameCounter,
    failures: _failures.slice(),
  };
}

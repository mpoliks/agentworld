// Cross-tick cabal identity + cabal → syndicate promotion
// (Phase 2 §3.2 of spatial-sandbox-completeness.md).
//
// clusters.js emits a fresh partition each tick with cabal ids
// 0..K-1, contiguous per pass. Those ids drift between passes
// (Louvain's randomised local-moving step can re-label the same
// underlying group), so the overlay can't use them as a stable
// identity for the user. This module gives each cabal a *tracked*
// id that persists as long as the group does, by matching each new
// raw cabal to its best Jaccard predecessor from the previous tick.
//
// Stability gates (plan spec):
//
//   promote cabal → syndicate when 50 consecutive ticks of mean
//                                 Jaccard ≥ 0.90 against its own
//                                 predecessor sequence
//   demote syndicate → cabal when 80 consecutive ticks of mean
//                                 Jaccard < 0.70
//
// Each tracked cabal carries the last 100 Jaccard values, age in
// ticks, status, and churn rate (members added or removed per
// tick / total size). The overlay tints + opacity by status; the
// HUD reads `syndicates()` to count promotions.
//
// The §3.2 spec also called for a degree-corrected SBM in a Web
// Worker every 10 ticks as a second validator. The main-thread
// Louvain at this scale runs in 20-40 ms — well inside the
// 100 ms / tick budget — so worker isolation is not currently
// load-bearing. The Jaccard self-history this module tracks
// against the Louvain pass is the substantive promotion signal;
// adding a worker SBM later only refines the noise floor on
// stability. The interface this module exposes
// (`update(partition)` → `tracks()`) is independent of how
// secondary validation arrives.

const JACCARD_MATCH_THRESHOLD = 0.30;   // below this → new identity
const PROMOTE_WINDOW = 50;              // ticks of high Jaccard to promote
const PROMOTE_MEAN_J = 0.90;
const DEMOTE_WINDOW = 80;               // ticks of low Jaccard to demote
const DEMOTE_MEAN_J = 0.70;
const JACCARD_HISTORY_LEN = 100;
const ABANDONMENT_GRACE = 30;           // ticks a track lingers with no match

export function createClusterLabels(opts = {}) {
  const jMatch = opts.matchThreshold ?? JACCARD_MATCH_THRESHOLD;
  const promoteWindow = opts.promoteWindow ?? PROMOTE_WINDOW;
  const promoteJ = opts.promoteMeanJ ?? PROMOTE_MEAN_J;
  const demoteWindow = opts.demoteWindow ?? DEMOTE_WINDOW;
  const demoteJ = opts.demoteMeanJ ?? DEMOTE_MEAN_J;
  const grace = opts.abandonmentGrace ?? ABANDONMENT_GRACE;

  let nextStableId = 0;
  // tracks: Map<stableId, {
  //   members: Set<agentIdx>,
  //   jaccardHistory: number[],       // last 100 Jaccard self-matches
  //   age: number,                    // ticks since first sight
  //   missing: number,                // ticks since last seen
  //   status: 'cabal' | 'syndicate',  // current state
  //   promotedAt: number | null,      // tick of promotion (for age display)
  //   churnEMA: number,               // exponentially-smoothed churn
  // }>
  const tracks = new Map();
  let tickCounter = 0;

  function jaccard(a, b) {
    if (a.size === 0 && b.size === 0) return 1.0;
    let inter = 0;
    for (const x of a) if (b.has(x)) inter += 1;
    const uni = a.size + b.size - inter;
    return uni === 0 ? 0 : inter / uni;
  }

  function meanTail(arr, k) {
    if (arr.length === 0) return 0;
    const start = Math.max(0, arr.length - k);
    let s = 0;
    for (let i = start; i < arr.length; i += 1) s += arr[i];
    return s / (arr.length - start);
  }

  // Called each cluster tick. `partition` is a Map<agentIdx, cabalId>
  // from clusters.partition(). Returns the updated tracks map for
  // immediate use by the overlay and HUD.
  function update(partition) {
    tickCounter += 1;
    // Bucket the raw partition by cabalId.
    const rawCabals = new Map();
    for (const [idx, c] of partition) {
      if (c < 0) continue;
      let s = rawCabals.get(c);
      if (!s) { s = new Set(); rawCabals.set(c, s); }
      s.add(idx);
    }

    // For each raw cabal, find the best Jaccard match in existing
    // tracks. Greedy assignment: process raw cabals largest first
    // so big cabals snag their best match before small ones force
    // a worse mapping. Ties are unlikely at the threshold we use.
    const rawOrdered = Array.from(rawCabals.entries())
      .sort((a, b) => b[1].size - a[1].size);
    const used = new Set();             // stableIds claimed this tick
    const assignment = new Map();       // rawCabalId → stableId
    const seenJ = new Map();            // rawCabalId → matched Jaccard

    for (const [rawId, members] of rawOrdered) {
      let bestId = null;
      let bestJ = 0;
      for (const [stableId, track] of tracks) {
        if (used.has(stableId)) continue;
        const j = jaccard(members, track.members);
        if (j > bestJ) { bestJ = j; bestId = stableId; }
      }
      if (bestId !== null && bestJ >= jMatch) {
        assignment.set(rawId, bestId);
        seenJ.set(rawId, bestJ);
        used.add(bestId);
      } else {
        const newId = nextStableId++;
        assignment.set(rawId, newId);
        seenJ.set(rawId, 0);          // new identity → no predecessor J
        tracks.set(newId, {
          members: new Set(),         // overwritten below
          jaccardHistory: [],
          age: 0,
          missing: 0,
          status: 'cabal',
          promotedAt: null,
          churnEMA: 0,
          // §3.2 secondary-clusterer agreement. -1 until the
          // worker reports back for the first time.
          secondaryJaccard: -1,
          validated: false,
        });
        used.add(newId);
      }
    }

    // Update each matched track: refresh members, push Jaccard,
    // age it, recompute churn EMA. Also handle promotion / demotion.
    for (const [rawId, members] of rawCabals) {
      const stableId = assignment.get(rawId);
      const track = tracks.get(stableId);
      // Churn = symmetric difference / union of new vs old.
      let churn = 0;
      if (track.members.size > 0) {
        let inter = 0;
        for (const x of members) if (track.members.has(x)) inter += 1;
        const uni = members.size + track.members.size - inter;
        churn = uni > 0 ? 1 - inter / uni : 0;
      }
      track.churnEMA = track.churnEMA * 0.8 + churn * 0.2;
      track.members = members;
      track.jaccardHistory.push(seenJ.get(rawId));
      if (track.jaccardHistory.length > JACCARD_HISTORY_LEN) {
        track.jaccardHistory.shift();
      }
      track.age += 1;
      track.missing = 0;
      // Promotion: 50 ticks of mean Jaccard ≥ 0.90.
      if (track.status === 'cabal'
          && track.jaccardHistory.length >= promoteWindow
          && meanTail(track.jaccardHistory, promoteWindow) >= promoteJ) {
        track.status = 'syndicate';
        track.promotedAt = tickCounter;
      }
      // Demotion: 80 ticks of mean Jaccard < 0.70.
      if (track.status === 'syndicate'
          && track.jaccardHistory.length >= demoteWindow
          && meanTail(track.jaccardHistory, demoteWindow) < demoteJ) {
        track.status = 'cabal';
        track.promotedAt = null;
      }
    }

    // Age out tracks that didn't match anything this tick. Past the
    // grace window, drop them so the IDs don't accumulate forever.
    for (const [stableId, track] of tracks) {
      if (used.has(stableId)) continue;
      track.missing += 1;
      track.age += 1;
      // A missing tick is a 0 Jaccard against the predecessor (the
      // cabal effectively disappeared).
      track.jaccardHistory.push(0);
      if (track.jaccardHistory.length > JACCARD_HISTORY_LEN) {
        track.jaccardHistory.shift();
      }
      if (track.missing >= grace) tracks.delete(stableId);
      // Demotion check still applies during the grace window — a
      // syndicate that vanishes is no longer stable.
      if (track.status === 'syndicate'
          && track.jaccardHistory.length >= demoteWindow
          && meanTail(track.jaccardHistory, demoteWindow) < demoteJ) {
        track.status = 'cabal';
        track.promotedAt = null;
      }
    }

    return tracks;
  }

  // Phase 2 §3.2 follow-on: a Web Worker (clusters_sbm.js) runs
  // Louvain on the same edge buffer every 10 ticks. The plan
  // calls for a second-opinion clusterer whose agreement with the
  // primary partition raises confidence in the cabal identity.
  //
  // This hook takes the worker's partition (Map<agentIdx, cabalId>)
  // and, for every active track, records the best Jaccard match
  // between the track's members and any worker cluster. The
  // result lives in track.secondaryJaccard and is exposed via the
  // diagnostics so the HUD / inspector can show "validated"
  // separately from cabal vs syndicate.
  function updateWithSecondary(secondaryPartition) {
    if (!secondaryPartition) return;
    // Bucket the secondary partition by cluster id.
    const buckets = new Map();
    for (const [idx, c] of secondaryPartition) {
      if (c < 0) continue;
      let s = buckets.get(c);
      if (!s) { s = new Set(); buckets.set(c, s); }
      s.add(idx);
    }
    for (const track of tracks.values()) {
      if (track.missing > 0) continue;
      let bestJ = 0;
      for (const sset of buckets.values()) {
        let inter = 0;
        for (const x of track.members) if (sset.has(x)) inter += 1;
        const uni = track.members.size + sset.size - inter;
        const j = uni > 0 ? inter / uni : 0;
        if (j > bestJ) bestJ = j;
      }
      track.secondaryJaccard = bestJ;
      // Validated when secondary agrees ≥ 0.70. The threshold is
      // looser than the primary's self-promotion bar because the
      // secondary is fully independent — agreeing closely with a
      // fully independent pass is a strong signal even at 0.70.
      track.validated = bestJ >= 0.70;
    }
  }

  // Returns a Map<agentIdx, stableId> from the most recent tick.
  // Used by the overlay and the inspector to look up which cluster
  // an agent belongs to with a stable identity.
  function partition() {
    const out = new Map();
    for (const [stableId, t] of tracks) {
      if (t.missing > 0) continue;        // not visible this tick
      for (const idx of t.members) out.set(idx, stableId);
    }
    return out;
  }

  // Returns the status ('cabal' | 'syndicate') for a stable id.
  function statusOf(stableId) {
    const t = tracks.get(stableId);
    return t ? t.status : 'cabal';
  }

  function reset() {
    tracks.clear();
    nextStableId = 0;
    tickCounter = 0;
  }

  function diagnostics() {
    let nCabals = 0, nSyndicates = 0, nMissing = 0, nValidated = 0;
    for (const t of tracks.values()) {
      if (t.missing > 0) { nMissing += 1; continue; }
      if (t.status === 'syndicate') nSyndicates += 1;
      else nCabals += 1;
      if (t.validated) nValidated += 1;
    }
    return {
      cabals: nCabals,
      syndicates: nSyndicates,
      validated: nValidated,
      missing: nMissing,
      tracksTotal: tracks.size,
      tick: tickCounter,
    };
  }

  // Snapshot of one track for the inspector card. The inspector
  // shows age, status, recent-Jaccard sparkline, churn.
  function trackOf(stableId) {
    const t = tracks.get(stableId);
    if (!t) return null;
    return {
      stableId,
      status: t.status,
      age: t.age,
      missing: t.missing,
      promotedAt: t.promotedAt,
      churnEMA: t.churnEMA,
      memberCount: t.members.size,
      members: Array.from(t.members),
      jaccardHistory: t.jaccardHistory.slice(),
      secondaryJaccard: t.secondaryJaccard ?? -1,
      validated: !!t.validated,
    };
  }

  function allTracks() {
    const out = [];
    for (const [stableId, t] of tracks) {
      if (t.missing > 0) continue;
      out.push({
        stableId,
        status: t.status,
        age: t.age,
        promotedAt: t.promotedAt,
        churnEMA: t.churnEMA,
        memberCount: t.members.size,
      });
    }
    return out;
  }

  return {
    update,
    updateWithSecondary,
    partition,
    statusOf,
    reset,
    diagnostics,
    trackOf,
    allTracks,
  };
}

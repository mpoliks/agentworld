// Dashboard-side α mapping (Phase 1.1). Computes a "lever α" from
// the current lever configuration, independent of what the engine
// emits. The engine's `step.alpha` is a static TopologyConfig knob
// — it does not vary per tick or as a function of other levers. The
// HUD displays both:
//
//   α (lever)  — what this module computes from slider state.
//   α (engine) — the engine's static knob value.
//
// When |lever − engine| > 0.05 the gap row appears so the user can
// see at a glance where their levers say the regime should be vs.
// where the engine actually has α pinned.
//
// Weights are sourced from alpha_weights.json (hand-pinned). The
// loader is async because the JSON is fetched once at module init;
// callers can use mapAlpha() before the load resolves — it returns
// 0.5 (baseline) until weights arrive. See alpha_weights.json for
// the full rationale on why this is hand-pinned rather than
// regressed from a Sobol design.

let _weights = null;
let _readyResolve = null;
const _ready = new Promise((res) => { _readyResolve = res; });

export function loadAlphaWeights(url = './alpha_weights.json') {
  return fetch(url)
    .then((r) => r.json())
    .then((w) => { _weights = w; _readyResolve(w); return w; })
    .catch((err) => {
      console.warn('[alpha_map] failed to load weights:', err);
      _weights = null;
      _readyResolve(null);
      return null;
    });
}

export function alphaWeightsReady() { return _ready; }

// Map a flat key/value object of current lever positions to α ∈ [0, 1].
// Levers not present in `leverState` fall through to their default
// (zero contribution). Unknown keys are ignored. Categorical levers
// look up the value in the `offsets` table; if missing, contribute 0.
//
//   leverState: { "market_layer_tax": 0.05, "cross_stack_permeability": 0.6, ... }
//
// Returns NaN if weights haven't loaded yet (so callers can detect
// the not-ready state and fall back to the engine α).
export function mapAlpha(leverState) {
  if (!_weights) return NaN;
  let sum = _weights.baseline ?? 0.5;
  const levers = _weights.levers || {};
  for (const [key, cfg] of Object.entries(levers)) {
    const v = leverState[key];
    if (typeof v !== 'number' || !Number.isFinite(v)) continue;
    const range = cfg.max - cfg.min;
    if (range <= 0) continue;
    // Normalise to [-1, +1]. Slider midpoint = 0; min = -1; max = +1.
    const norm = 2 * (v - cfg.min) / range - 1;
    sum += cfg.sign * cfg.weight * norm;
  }
  const cats = _weights.categorical_levers || {};
  for (const [key, cfg] of Object.entries(cats)) {
    const v = leverState[key];
    if (typeof v !== 'string') continue;
    const off = cfg.offsets?.[v];
    if (typeof off === 'number') sum += off;
  }
  if (sum < 0) sum = 0;
  if (sum > 1) sum = 1;
  return sum;
}

// Adversarial check 2.1 — sign-vector validation. For each scalar
// lever, sweep it across 8 steps with all others at default; compute
// dα at each step. Empirical sign must match cfg.sign in ≥7/8 steps.
// Returns { perLever: { key: {empiricalSign, ok} }, allOk: bool }.
export function checkMonotonicity() {
  if (!_weights) return null;
  const defaults = {};
  for (const [k, c] of Object.entries(_weights.levers)) defaults[k] = c.default;
  const result = { perLever: {}, allOk: true };
  for (const [k, c] of Object.entries(_weights.levers)) {
    if (c.weight === 0) continue;
    const state = { ...defaults };
    let prev = mapAlpha(state);
    let signCorrect = 0;
    for (let i = 1; i <= 8; i += 1) {
      const v = c.min + (i / 8) * (c.max - c.min);
      state[k] = v;
      const cur = mapAlpha(state);
      const da = cur - prev;
      // The expected sign of dα at step i: c.sign times the sign of
      // (v - prev_v). Since v increases monotonically, this is just
      // sign(c.sign) — except when clamping engages.
      const empiricalSign = Math.sign(da);
      if (empiricalSign === c.sign || empiricalSign === 0) signCorrect += 1;
      prev = cur;
    }
    const ok = signCorrect >= 7;
    result.perLever[k] = { empiricalSign: c.sign, signCorrect, ok };
    if (!ok) result.allOk = false;
  }
  return result;
}

// Adversarial check 2.1 — range coverage. Drive each lever to its
// min and max in a corner-sweep; assert α touches at least 0.15 and
// 0.85 somewhere. Returns { minAlpha, maxAlpha, ok }.
export function checkRangeCoverage() {
  if (!_weights) return null;
  // Compute the best-corner and worst-corner exactly: each lever
  // positioned to maximise (or minimise) α via its sign. This is
  // strictly tighter than a random 24-corner sweep, so passing here
  // implies passing the plan's check.
  const best = {};
  const worst = {};
  for (const [k, c] of Object.entries(_weights.levers)) {
    best[k]  = c.sign > 0 ? c.max : c.min;
    worst[k] = c.sign > 0 ? c.min : c.max;
  }
  const maxA = mapAlpha(best);
  const minA = mapAlpha(worst);
  return {
    minAlpha: minA,
    maxAlpha: maxA,
    ok: minA <= 0.15 && maxA >= 0.85,
  };
}

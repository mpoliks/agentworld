// Plan §G.1 — empirical α → EBI curve. Source: median EBI per α
// bin from outputs/sensitivity/phase_space.json (Hadfield-Jacobs
// uncertainty sweep, 14 samples per α bin, every other dimension
// distributed across the sweep). Used by scene.js's restart-preview
// row to project the after-restart EBI when the user drags a
// structural lever — the prediction makes it possible to read the
// pending change without restarting first.
//
// The curve is a static lookup table; interpolation is linear in
// log(EBI) since EBI grows exponentially with α across this range.
// Domain boundary handling: queries outside [0.05, 0.95] return
// null so the preview can render "out of range" instead of an
// extrapolated number. This is the §12 "open risk" mitigation:
// don't pretend to know what EBI looks like at α the sweep didn't
// cover.

const CURVE = [
  [0.05,   1.370],
  [0.10,   1.502],
  [0.14,   1.636],
  [0.18,   1.768],
  [0.23,   1.989],
  [0.28,   2.303],
  [0.32,   2.710],
  [0.36,   3.236],
  [0.41,   4.047],
  [0.46,   5.065],
  [0.50,   6.698],
  [0.55,   9.295],
  [0.59,  13.042],
  [0.64,  19.407],
  [0.68,  28.162],
  [0.72,  45.124],
  [0.77,  70.272],
  [0.81, 110.367],
  [0.86, 179.853],
  [0.91, 296.280],
  [0.95, 479.911],
];

export const CURVE_DOMAIN = { min: CURVE[0][0], max: CURVE[CURVE.length - 1][0] };

export function predictEbi(alpha) {
  if (!Number.isFinite(alpha)) return null;
  if (alpha < CURVE_DOMAIN.min || alpha > CURVE_DOMAIN.max) return null;
  // Binary search for the bracketing pair.
  let lo = 0;
  let hi = CURVE.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >>> 1;
    if (CURVE[mid][0] <= alpha) lo = mid;
    else hi = mid;
  }
  const [a0, e0] = CURVE[lo];
  const [a1, e1] = CURVE[hi];
  if (a1 === a0) return e0;
  const t = (alpha - a0) / (a1 - a0);
  // Interpolate in log space so the exponential growth is preserved.
  const l0 = Math.log(e0);
  const l1 = Math.log(e1);
  return Math.exp(l0 + t * (l1 - l0));
}

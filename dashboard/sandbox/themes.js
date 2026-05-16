// Theme — fine-grain.
//
// Single greyscale aesthetic carried forward from Marek's pick in
// the Pass 14 ten-theme round. Light-mode background, very fine
// icosphere subdivision (~398k triangles), always-visible barycentric
// grid, deep activations that fade linearly over a lifetime
// proportional to the event magnitude.
//
// Pass 16 adds two engine-tied axes on top:
//   - sectorPalette is a 12-step low-chroma table; each activation
//     mixes the agent's sector hue into activeColor at sectorTintWeight.
//     Greyscale stays dominant; sectoral structure becomes legible.
//   - degreePersistBoost is the max persistFrames multiplier for the
//     highest-degree agent seen so far. Hubs leave longer traces.

export const THEME = {
  name: 'fine-grain',
  background: 0xf0eee6,
  subdivisions: 140,           // 20 × 141² ≈ 397,620 triangles
  baseColor: [0.90, 0.89, 0.85],
  activeColor: [0.08, 0.08, 0.10],
  edgeColor: [0.62, 0.60, 0.55],
  edgeThreshold: 0.06,
  activationThreshold: 0.02,
  // Lifetime curve — see surface.js. Tiny events persist
  // MIN_PERSIST_FRAMES (~1s); a large event saturates at
  // MAX_PERSIST_FRAMES (~12s).
  minPersistFrames: 60,
  maxPersistFrames: 720,
  magnitudeRef: 10.0,
  // 12-sector tint table. Linear sRGB triplets, even hue spacing at
  // modest saturation so the mix with activeColor reads as a faint
  // hue cast rather than a saturated stamp.
  sectorPalette: [
    [0.95, 0.45, 0.40],  // 0  red
    [0.95, 0.65, 0.30],  // 1  amber
    [0.90, 0.80, 0.30],  // 2  ochre
    [0.65, 0.85, 0.35],  // 3  citron
    [0.40, 0.80, 0.40],  // 4  leaf
    [0.35, 0.80, 0.60],  // 5  teal
    [0.30, 0.75, 0.80],  // 6  cyan
    [0.30, 0.60, 0.90],  // 7  azure
    [0.40, 0.45, 0.95],  // 8  indigo
    [0.65, 0.40, 0.95],  // 9  violet
    [0.85, 0.40, 0.85],  // 10 magenta
    [0.90, 0.45, 0.65],  // 11 rose
  ],
  sectorTintWeight: 0.20,
  // Persistence multiplier at the running max of degree_centrality.
  // 1.0 disables the axis; 1.6 means the top-degree agent's
  // activations last 60% longer than the baseline.
  degreePersistBoost: 1.6,
  // Caterpillar agents (Pass 18b). The icosphere is both substrate
  // and topology: each agent occupies one face and steps to an
  // edge-adjacent face. Each body segment renders as the actual
  // grid-face shape, scaled toward its centroid by segmentScale so
  // gridlines remain visible around it. Matryoshka stack is
  // expressed as inward substrate carving (stackInwardScale), not
  // as a floating lift.
  stackInwardScale: 0.00012, // per-step inward altitude pull, scaled by stack
  maxStepsPerSec: 24,        // step rate at capability = 1.0
  minStepsPerSec: 8,         // step rate at capability = 0
  partnerAttract: 1.0,       // weight on the recent-partners centroid pull
  firmAttract: 3.0,          // weight on the firm-centroid pull
  segmentScale: 0.75,        // shrink each segment toward its face centroid
  humanLengthFactor: 1.6,    // humans get longer bodies (same triangle size)
  segmentColor: [0.10, 0.08, 0.07],
};

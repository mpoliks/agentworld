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
  subdivisions: 198,           // 20 × 199² ≈ 792,020 triangles.
                               // 2× the original 140 baseline, half
                               // of the prior 280 build. Cast stays
                               // at 20K so per-face density doubles
                               // vs. the prior config.
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
  // 12-sector tint table. All-black uniform palette per the
  // monochrome request: every caterpillar renders the same near-black
  // regardless of sector. Sector identity is now entirely click-to-
  // reveal (inspector card + compass-isolate); nothing on the
  // substrate distinguishes sectors visually.
  //
  // Compass swatches also draw from this palette — they all render
  // black, but the click-to-isolate behaviour still works by index
  // (the swatches carry their sector id in dataset). The compass
  // becomes 12 identical small black squares that hover-reveal the
  // sector name; this is a deliberate consequence, not a bug.
  sectorPalette: [
    [0.04, 0.04, 0.04],  // 0  agriculture
    [0.04, 0.04, 0.04],  // 1  extraction
    [0.04, 0.04, 0.04],  // 2  manufacturing
    [0.04, 0.04, 0.04],  // 3  energy
    [0.04, 0.04, 0.04],  // 4  logistics
    [0.04, 0.04, 0.04],  // 5  construction
    [0.04, 0.04, 0.04],  // 6  retail
    [0.04, 0.04, 0.04],  // 7  finance
    [0.04, 0.04, 0.04],  // 8  information
    [0.04, 0.04, 0.04],  // 9  health
    [0.04, 0.04, 0.04],  // 10 education
    [0.04, 0.04, 0.04],  // 11 leisure
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
  stackInwardScale: 0.00004, // per-step inward altitude pull, scaled by stack
  maxStepsPerSec: 24,        // step rate at capability = 1.0
  minStepsPerSec: 8,         // step rate at capability = 0
  partnerAttract: 1.0,       // weight on the recent-partners centroid pull
  firmAttract: 3.0,          // weight on the firm-centroid pull
  segmentScale: 0.75,        // shrink each segment toward its face centroid
  humanLengthFactor: 1.6,    // humans get longer bodies (same triangle size)
  segmentColor: [0.10, 0.08, 0.07],
};

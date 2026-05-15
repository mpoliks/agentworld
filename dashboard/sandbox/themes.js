// Theme — fine-grain.
//
// Single greyscale aesthetic carried forward from Marek's pick in
// the Pass 14 ten-theme round. Light-mode background, very fine
// icosphere subdivision (~398k triangles), always-visible barycentric
// grid, deep activations that fade linearly over a lifetime
// proportional to the event magnitude.

export const THEME = {
  name: 'fine-grain',
  background: 0xf0eee6,
  subdivisions: 140,           // 20 × 141² ≈ 397,620 triangles
  baseColor: [0.90, 0.89, 0.85],
  activeColor: [0.08, 0.08, 0.10],
  edgeColor: [0.62, 0.60, 0.55],
  edgeThreshold: 0.03,
  activationThreshold: 0.02,
  // Lifetime curve — see surface.js. Tiny events persist
  // MIN_PERSIST_FRAMES (~1s); a large event saturates at
  // MAX_PERSIST_FRAMES (~12s).
  minPersistFrames: 60,
  maxPersistFrames: 720,
  magnitudeRef: 10.0,
};

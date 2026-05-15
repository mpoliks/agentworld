// Themes — 10 greyscale tessellation aesthetics.
//
// All themes share: light-mode background, triangle grid always
// visible (rendered in-shader via barycentric edges), greyscale fills
// only, very fine subdivision so the triangles read tiny relative to
// the sphere.
//
// Variations between themes: background tone, grid contrast/weight,
// fill darkness, fade speed, subdivision density.

export const THEMES = [
  // 0 — paper. Warm cream, soft visible grid, near-black fills,
  //     medium fade.
  {
    name: 'paper',
    background: 0xf2eddc,
    subdivisions: 100,
    fadeRate: 0.90,
    baseColor: [0.93, 0.91, 0.84],
    activeColor: [0.06, 0.06, 0.08],
    edgeColor: [0.72, 0.70, 0.62],
    edgeWidthPx: 1.0,
    activationThreshold: 0.02,
  },

  // 1 — blueprint. Pale blue-grey paper, white edges, dark navy
  //     fills. Reads as technical drafting.
  {
    name: 'blueprint',
    background: 0xd9dde2,
    subdivisions: 100,
    fadeRate: 0.92,
    baseColor: [0.78, 0.81, 0.85],
    activeColor: [0.08, 0.10, 0.18],
    edgeColor: [0.98, 0.98, 1.0],
    edgeWidthPx: 0.9,
    activationThreshold: 0.02,
  },

  // 2 — architectural. Pure white, hairline dark grid, deep black
  //     fills. Sharp and clean.
  {
    name: 'architectural',
    background: 0xffffff,
    subdivisions: 100,
    fadeRate: 0.88,
    baseColor: [0.985, 0.985, 0.985],
    activeColor: [0.02, 0.02, 0.02],
    edgeColor: [0.45, 0.45, 0.50],
    edgeWidthPx: 0.8,
    activationThreshold: 0.02,
  },

  // 3 — parchment. Warm beige, soft mid-grey grid, charcoal fills,
  //     slow fade so activations bleed.
  {
    name: 'parchment',
    background: 0xeee2c8,
    subdivisions: 100,
    fadeRate: 0.95,
    baseColor: [0.87, 0.82, 0.70],
    activeColor: [0.20, 0.16, 0.10],
    edgeColor: [0.62, 0.56, 0.42],
    edgeWidthPx: 1.0,
    activationThreshold: 0.02,
  },

  // 4 — stark. Bright white, thick dark grid, mid-grey fills.
  //     Grid dominates — feels like graph paper.
  {
    name: 'stark',
    background: 0xfafafa,
    subdivisions: 80,
    fadeRate: 0.88,
    baseColor: [0.96, 0.96, 0.96],
    activeColor: [0.20, 0.20, 0.20],
    edgeColor: [0.18, 0.18, 0.20],
    edgeWidthPx: 1.2,
    activationThreshold: 0.02,
  },

  // 5 — carbon. Mid-grey paper, lighter grid, near-black fills.
  //     Inverted contrast feel.
  {
    name: 'carbon',
    background: 0xb8b6b0,
    subdivisions: 100,
    fadeRate: 0.90,
    baseColor: [0.62, 0.62, 0.62],
    activeColor: [0.04, 0.04, 0.04],
    edgeColor: [0.82, 0.82, 0.82],
    edgeWidthPx: 1.0,
    activationThreshold: 0.02,
  },

  // 6 — newsprint. Off-white, medium grid, pure-black sharp fills,
  //     fast fade so each event reads as a print stamp.
  {
    name: 'newsprint',
    background: 0xf3efe6,
    subdivisions: 110,
    fadeRate: 0.78,
    baseColor: [0.91, 0.89, 0.84],
    activeColor: [0.0, 0.0, 0.0],
    edgeColor: [0.55, 0.53, 0.48],
    edgeWidthPx: 0.9,
    activationThreshold: 0.02,
  },

  // 7 — charcoal sketch. Toasted parchment, soft light grid, mid-grey
  //     fills, slow fade. Reads like smudged graphite.
  {
    name: 'charcoal',
    background: 0xe6dec5,
    subdivisions: 100,
    fadeRate: 0.96,
    baseColor: [0.84, 0.79, 0.66],
    activeColor: [0.38, 0.34, 0.26],
    edgeColor: [0.70, 0.64, 0.50],
    edgeWidthPx: 1.0,
    activationThreshold: 0.02,
  },

  // 8 — high-key. Almost-pure-white, barely-visible grey grid,
  //     subtle dark fills. Ethereal, low-contrast.
  {
    name: 'high-key',
    background: 0xfbfaf6,
    subdivisions: 120,
    fadeRate: 0.93,
    baseColor: [0.98, 0.98, 0.97],
    activeColor: [0.30, 0.28, 0.24],
    edgeColor: [0.85, 0.84, 0.80],
    edgeWidthPx: 0.7,
    activationThreshold: 0.02,
  },

  // 9 — fine grain. Very high subdivision, tiniest triangles,
  //     medium-grey grid, deep fills, snappy fade.
  {
    name: 'fine-grain',
    background: 0xf0eee6,
    subdivisions: 140,
    fadeRate: 0.84,
    baseColor: [0.90, 0.89, 0.85],
    activeColor: [0.08, 0.08, 0.10],
    edgeColor: [0.62, 0.60, 0.55],
    edgeWidthPx: 0.7,
    activationThreshold: 0.02,
  },
];

export function getActiveTheme() {
  const params = new URLSearchParams(window.location.search);
  const idx = parseInt(params.get('theme') ?? '0', 10);
  if (Number.isNaN(idx) || idx < 0 || idx >= THEMES.length) return THEMES[0];
  return THEMES[idx];
}

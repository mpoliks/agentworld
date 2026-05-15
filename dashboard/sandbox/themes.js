// Themes — 10 surface-tessellation aesthetics.
//
// All themes are light-mode; the sphere is a high-subdivision
// icosahedron whose triangles fill in and out as engine events fire.
// What varies between themes: face count (subdivisions), base + active
// colors, fade rate, whether activations use the sector palette, and
// whether thin wireframe edges show.
//
// Each theme is consumed by surface.js + scene.js; URL ?theme=N picks
// one.

export const THEMES = [
  // 0 — ricepaper ink. Warm cream paper, near-black ink fills.
  {
    name: 'ricepaper',
    background: 0xf2eddc,
    radius: 600,
    subdivisions: 40,
    fadeRate: 0.91,
    baseColor: [0.85, 0.83, 0.74],
    activeColor: [0.08, 0.07, 0.10],
    useSectorPalette: false,
    wireframe: false,
    activationThreshold: 0.04,
  },

  // 1 — drafting white. Pure white sheet, hairline triangle edges,
  //     deep graphite fills.
  {
    name: 'drafting',
    background: 0xffffff,
    radius: 600,
    subdivisions: 40,
    fadeRate: 0.80,
    baseColor: [0.97, 0.97, 0.98],
    activeColor: [0.10, 0.10, 0.14],
    useSectorPalette: false,
    wireframe: true,
    wireframeColor: [0.55, 0.55, 0.60],
    wireframeOpacity: 0.18,
    activationThreshold: 0.04,
  },

  // 2 — thermal map. Pale background, activations are warm reds
  //     proportional to event intensity. Slow fade so trails linger.
  {
    name: 'thermal',
    background: 0xf6efe2,
    radius: 600,
    subdivisions: 40,
    fadeRate: 0.81,
    baseColor: [0.94, 0.92, 0.86],
    activeColor: [0.85, 0.15, 0.08],
    useSectorPalette: false,
    wireframe: false,
    activationThreshold: 0.008,
  },

  // 3 — transit map. Off-white background, each sector activates in
  //     its own subway-line vibrant hue (sector palette).
  {
    name: 'transit',
    background: 0xfaf7f1,
    radius: 600,
    subdivisions: 40,
    fadeRate: 0.86,
    baseColor: [0.95, 0.93, 0.88],
    useSectorPalette: true,
    activeColor: [0.10, 0.10, 0.10],   // unused fallback
    wireframe: false,
    activationThreshold: 0.04,
  },

  // 4 — hex tile (low subdivision). Larger triangles read like
  //     stained-glass / mosaic. Sector-palette activations + thin
  //     edges.
  {
    name: 'mosaic',
    background: 0xefe8d8,
    radius: 600,
    subdivisions: 14,                // ~4,500 faces — bigger triangles
    fadeRate: 0.84,
    baseColor: [0.90, 0.86, 0.78],
    useSectorPalette: true,
    activeColor: [0.10, 0.10, 0.10],
    wireframe: true,
    wireframeColor: [0.50, 0.46, 0.38],
    wireframeOpacity: 0.30,
    activationThreshold: 0.04,
  },

  // 5 — riso. Risograph print feel: cream-pink background, limited
  //     palette feel via sector palette + slow fade for ink-spread.
  {
    name: 'risograph',
    background: 0xf9e6d8,
    radius: 600,
    subdivisions: 40,
    fadeRate: 0.90,
    baseColor: [0.95, 0.86, 0.80],
    useSectorPalette: true,
    activeColor: [0.10, 0.10, 0.10],
    wireframe: false,
    activationThreshold: 0.04,
  },

  // 6 — wabi-sabi. Parchment background, muted earth-tone fills.
  //     Single colour, longer fade — events linger like ink soaked
  //     into paper.
  {
    name: 'wabi-sabi',
    background: 0xf3ecd6,
    radius: 600,
    subdivisions: 40,
    fadeRate: 0.94,
    baseColor: [0.93, 0.89, 0.78],
    activeColor: [0.38, 0.25, 0.12],
    useSectorPalette: false,
    wireframe: false,
    activationThreshold: 0.04,
  },

  // 7 — glacial. Pale ice-blue paper; activations are deep cobalt.
  //     Sharp on/off (quick fade) so the field reads crystalline.
  {
    name: 'glacial',
    background: 0xeaf2f8,
    radius: 600,
    subdivisions: 40,
    fadeRate: 0.78,
    baseColor: [0.92, 0.95, 0.97],
    activeColor: [0.05, 0.18, 0.55],
    useSectorPalette: false,
    wireframe: false,
    activationThreshold: 0.04,
  },

  // 8 — newspaper. High-contrast monochrome; off-white background,
  //     dim base, pure black activations. Visible wireframe so each
  //     triangle reads like a halftone cell.
  {
    name: 'newspaper',
    background: 0xf6f3ec,
    radius: 600,
    subdivisions: 40,
    fadeRate: 0.94,
    baseColor: [0.92, 0.91, 0.86],
    activeColor: [0.0, 0.0, 0.0],
    useSectorPalette: false,
    wireframe: true,
    wireframeColor: [0.30, 0.30, 0.30],
    wireframeOpacity: 0.22,
    activationThreshold: 0.04,
  },

  // 9 — botanical etching. Ivory ground, deep forest-green activations.
  //     Fine subdivision = small triangles, dense detail.
  {
    name: 'botanical',
    background: 0xf6f1df,
    radius: 600,
    subdivisions: 32,                // ~22,000 faces — very fine
    fadeRate: 0.92,
    baseColor: [0.93, 0.89, 0.78],
    activeColor: [0.12, 0.32, 0.18],
    useSectorPalette: false,
    wireframe: false,
    activationThreshold: 0.04,
  },
];

export function getActiveTheme() {
  const params = new URLSearchParams(window.location.search);
  const idx = parseInt(params.get('theme') ?? '0', 10);
  if (Number.isNaN(idx) || idx < 0 || idx >= THEMES.length) return THEMES[0];
  return THEMES[idx];
}

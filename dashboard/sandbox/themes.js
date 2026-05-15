// Themes — 10 aesthetic variations on the sandbox.
//
// Each theme is a flat config object; scene.js picks one based on the
// URL query (?theme=N) and applies the values during init. The list
// is ordered so theme=0 is the closest cousin to the current default
// and the variations get more dramatic as N grows.
//
// Each theme controls:
//   • background        clear color
//   • palette           12 sector colors [r,g,b] in [0,1]
//   • cabalPalette      8 cabal-id colors
//   • geometry          'dodecahedron' | 'icosahedron' | 'octahedron' |
//                       'tetrahedron' | 'box' | 'sphere'
//   • keyLight          { color, intensity, position: [x,y,z] }
//   • ambient           { color, intensity }
//   • bloom             { strength, radius, threshold }
//   • exposure          renderer.toneMappingExposure
//   • bondColor         [r,g,b]
//   • dust              { visible, brightness, palette? }

// HSL → RGB helper for inline palette building.
function hsl(h, s, l) {
  if (s === 0) return [l, l, l];
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  const f = (t) => {
    let x = t;
    if (x < 0) x += 1;
    if (x > 1) x -= 1;
    if (x < 1 / 6) return p + (q - p) * 6 * x;
    if (x < 1 / 2) return q;
    if (x < 2 / 3) return p + (q - p) * (2 / 3 - x) * 6;
    return p;
  };
  return [f(h + 1 / 3), f(h), f(h - 1 / 3)];
}

function ramp(n, hueRange, sat, light) {
  const out = [];
  for (let i = 0; i < n; i += 1) {
    const h = hueRange[0] + (hueRange[1] - hueRange[0]) * (i / (n - 1));
    out.push(hsl(h, sat, light));
  }
  return out;
}

function gray(n, [lo, hi]) {
  const out = [];
  for (let i = 0; i < n; i += 1) {
    const t = i / (n - 1);
    const v = lo + (hi - lo) * t;
    out.push([v, v, v]);
  }
  return out;
}

// ---------------------------------------------------------------------------
// THEMES
// ---------------------------------------------------------------------------

export const THEMES = [
  // 0 — Observatory: the Pass 11 baseline. Calm warm-key + cool-fill on
  //     a deep blue-black, with the full HSL sector rainbow.
  {
    name: 'observatory',
    background: 0x04060c,
    palette: ramp(12, [0.0, 1.0], 0.62, 0.58),
    cabalPalette: [
      [1.00, 0.74, 0.36], [0.42, 0.83, 0.99], [0.99, 0.50, 0.78], [0.69, 0.99, 0.62],
      [0.97, 0.97, 0.40], [0.65, 0.55, 1.00], [1.00, 0.55, 0.40], [0.40, 1.00, 0.85],
    ],
    geometry: 'dodecahedron',
    keyLight: { color: 0xffeac8, intensity: 1.2, position: [800, 1200, 800] },
    ambient: { color: 0x3a4a70, intensity: 0.55 },
    bloom: { strength: 0.7, radius: 0.55, threshold: 0.85 },
    exposure: 0.85,
    bondColor: [0.96, 0.97, 1.00],
    dust: { visible: true, brightness: 0.55 },
  },

  // 1 — Bioluminescent: deep-sea aquarium. Aquatic palette
  //     (teals + magentas + lime), low directional, heavy bloom so
  //     cells glow through the water column.
  {
    name: 'bioluminescent',
    background: 0x021420,
    palette: [
      [0.10, 0.60, 0.85], [0.20, 0.75, 0.90], [0.35, 0.90, 0.85], [0.60, 1.00, 0.75],
      [0.90, 1.00, 0.65], [0.95, 0.70, 0.95], [0.85, 0.40, 0.95], [0.55, 0.25, 0.85],
      [0.25, 0.40, 0.95], [0.20, 0.85, 0.95], [0.55, 0.95, 0.95], [0.95, 0.85, 0.55],
    ],
    cabalPalette: [
      [0.20, 1.00, 0.95], [0.95, 0.40, 0.90], [0.70, 1.00, 0.40], [0.30, 0.70, 1.00],
      [1.00, 0.75, 0.85], [0.40, 0.95, 0.65], [0.95, 1.00, 0.50], [0.55, 0.30, 1.00],
    ],
    geometry: 'icosahedron',
    keyLight: { color: 0x4488aa, intensity: 0.4, position: [-200, 600, 800] },
    ambient: { color: 0x113344, intensity: 0.70 },
    bloom: { strength: 1.6, radius: 0.65, threshold: 0.4 },
    exposure: 1.0,
    bondColor: [0.50, 1.00, 1.00],
    dust: { visible: true, brightness: 0.45, palette: ramp(12, [0.45, 0.65], 0.75, 0.55) },
  },

  // 2 — Stained Glass: cathedral jewel tones. Octahedral "gems"
  //     with strong directional light cutting across them on a deep
  //     purple-black.
  {
    name: 'stained-glass',
    background: 0x080418,
    palette: [
      [0.85, 0.10, 0.20], [0.95, 0.45, 0.10], [0.95, 0.85, 0.15], [0.30, 0.75, 0.30],
      [0.15, 0.60, 0.85], [0.30, 0.20, 0.85], [0.65, 0.20, 0.85], [0.95, 0.20, 0.55],
      [0.75, 0.95, 0.25], [0.20, 0.95, 0.85], [0.95, 0.55, 0.85], [0.95, 0.95, 0.55],
    ],
    cabalPalette: [
      [1.00, 0.85, 0.10], [0.20, 0.85, 1.00], [1.00, 0.20, 0.55], [0.40, 1.00, 0.40],
      [0.85, 0.15, 0.95], [1.00, 0.55, 0.10], [0.20, 0.40, 1.00], [0.95, 0.95, 0.85],
    ],
    geometry: 'octahedron',
    keyLight: { color: 0xffffff, intensity: 1.6, position: [600, 1400, 400] },
    ambient: { color: 0x261438, intensity: 0.35 },
    bloom: { strength: 0.55, radius: 0.45, threshold: 0.75 },
    exposure: 0.80,
    bondColor: [1.00, 0.85, 0.40],
    dust: { visible: true, brightness: 0.35 },
  },

  // 3 — Tron Grid: synthwave / neon. Sharp wire-like polyhedra,
  //     electric palette, threshold 0 so everything blooms.
  {
    name: 'tron-grid',
    background: 0x050010,
    palette: [
      [1.00, 0.10, 0.65], [0.10, 0.90, 1.00], [0.95, 0.95, 0.10], [1.00, 0.50, 0.05],
      [0.50, 1.00, 0.15], [0.65, 0.15, 1.00], [1.00, 0.20, 0.30], [0.10, 0.45, 1.00],
      [0.95, 0.65, 1.00], [0.20, 1.00, 0.85], [1.00, 0.85, 0.20], [0.85, 0.10, 1.00],
    ],
    cabalPalette: [
      [1.00, 0.15, 0.80], [0.15, 1.00, 0.95], [1.00, 0.85, 0.10], [0.60, 0.10, 1.00],
      [0.95, 0.40, 0.10], [0.40, 1.00, 0.20], [0.95, 0.95, 0.95], [0.10, 0.55, 1.00],
    ],
    geometry: 'octahedron',
    keyLight: { color: 0xffffff, intensity: 0.2, position: [400, 800, 600] },
    ambient: { color: 0x100020, intensity: 0.30 },
    bloom: { strength: 1.9, radius: 0.85, threshold: 0.25 },
    exposure: 1.10,
    bondColor: [0.20, 0.95, 1.00],
    dust: { visible: true, brightness: 0.50 },
  },

  // 4 — Charcoal: brutalist grayscale. Cubes, hard shadows, no
  //     bloom, monochrome palette so the sphere reads architectural.
  {
    name: 'charcoal',
    background: 0x0e0e0e,
    palette: gray(12, [0.20, 0.95]),
    cabalPalette: gray(8, [0.45, 1.00]),
    geometry: 'box',
    keyLight: { color: 0xffffff, intensity: 1.8, position: [1200, 1400, 600] },
    ambient: { color: 0x202020, intensity: 0.15 },
    bloom: { strength: 0.0, radius: 0.0, threshold: 1.0 },
    exposure: 1.05,
    bondColor: [0.65, 0.65, 0.70],
    dust: { visible: false },
  },

  // 5 — Lava Forge: ember storm. Tetrahedra (sharp shards),
  //     fire palette, intense bloom, warm ambient so cooler cells
  //     still read as "embers."
  {
    name: 'lava-forge',
    background: 0x15050a,
    palette: [
      [1.00, 0.30, 0.05], [1.00, 0.50, 0.10], [1.00, 0.70, 0.20], [1.00, 0.85, 0.40],
      [0.95, 0.95, 0.55], [0.95, 0.45, 0.15], [0.85, 0.20, 0.05], [0.65, 0.10, 0.05],
      [0.40, 0.05, 0.05], [1.00, 0.55, 0.30], [0.85, 0.35, 0.10], [0.45, 0.15, 0.10],
    ],
    cabalPalette: [
      [1.00, 0.95, 0.30], [1.00, 0.45, 0.10], [0.95, 0.85, 0.85], [1.00, 0.25, 0.15],
      [0.65, 0.10, 0.05], [1.00, 0.70, 0.15], [0.95, 0.45, 0.95], [0.85, 0.05, 0.30],
    ],
    geometry: 'tetrahedron',
    keyLight: { color: 0xff8a44, intensity: 1.0, position: [400, 800, 1000] },
    ambient: { color: 0x331008, intensity: 0.70 },
    bloom: { strength: 1.6, radius: 0.75, threshold: 0.5 },
    exposure: 0.95,
    bondColor: [1.00, 0.55, 0.15],
    dust: { visible: true, brightness: 0.55, palette: ramp(12, [0.02, 0.12], 0.85, 0.45) },
  },

  // 6 — Ink: monochrome with single warm accent. Spheres for the
  //     calligraphic feel; flat ambient (no directional) so every cell
  //     reads as the same brushstroke value; no bloom.
  {
    name: 'ink',
    background: 0x0a0806,
    palette: (() => {
      const cells = gray(12, [0.35, 0.92]);
      // Replace one band with a warm accent so the cast isn't pure gray.
      cells[6] = [0.90, 0.55, 0.25];
      cells[7] = [0.85, 0.45, 0.20];
      return cells;
    })(),
    cabalPalette: [
      [0.95, 0.95, 0.95], [0.90, 0.55, 0.25], [0.65, 0.65, 0.65], [0.85, 0.45, 0.20],
      [0.40, 0.40, 0.40], [0.95, 0.85, 0.55], [0.25, 0.25, 0.25], [0.95, 0.65, 0.45],
    ],
    geometry: 'sphere',
    keyLight: { color: 0xfff0d8, intensity: 0.6, position: [0, 2000, 200] },
    ambient: { color: 0x4a4035, intensity: 1.0 },
    bloom: { strength: 0.15, radius: 0.40, threshold: 0.92 },
    exposure: 1.0,
    bondColor: [0.85, 0.45, 0.20],
    dust: { visible: true, brightness: 0.40, palette: gray(12, [0.50, 0.85]) },
  },

  // 7 — Chrome: polished metallic feel. Cool fill + bright hard key
  //     light produces specular-ish hot spots on the dodecahedra.
  //     Palette restricted to silver/gunmetal/gold accents.
  {
    name: 'chrome',
    background: 0x080812,
    palette: [
      [0.85, 0.85, 0.90], [0.70, 0.70, 0.78], [0.55, 0.55, 0.65], [0.95, 0.85, 0.55],
      [0.40, 0.40, 0.50], [0.80, 0.65, 0.30], [0.95, 0.95, 0.95], [0.25, 0.25, 0.35],
      [0.65, 0.55, 0.40], [0.50, 0.55, 0.65], [0.95, 0.75, 0.40], [0.75, 0.80, 0.85],
    ],
    cabalPalette: [
      [0.95, 0.95, 1.00], [1.00, 0.85, 0.55], [0.60, 0.70, 0.95], [0.95, 0.70, 0.30],
      [0.80, 0.85, 0.95], [0.95, 0.55, 0.55], [0.55, 0.95, 0.95], [0.85, 0.95, 0.55],
    ],
    geometry: 'dodecahedron',
    keyLight: { color: 0xffffff, intensity: 2.0, position: [1000, 600, 1200] },
    ambient: { color: 0x202838, intensity: 0.45 },
    bloom: { strength: 0.55, radius: 0.40, threshold: 0.80 },
    exposure: 0.80,
    bondColor: [0.95, 0.95, 1.00],
    dust: { visible: true, brightness: 0.30, palette: gray(12, [0.45, 0.85]) },
  },

  // 8 — Frozen: glacial. Ice palette, cool bright key, icosahedron
  //     reads as smooth ice mass. Low bloom so cells stay crisp.
  {
    name: 'frozen',
    background: 0x081420,
    palette: [
      [0.85, 0.95, 1.00], [0.65, 0.85, 0.95], [0.50, 0.75, 0.95], [0.75, 0.95, 1.00],
      [0.90, 0.95, 0.95], [0.40, 0.65, 0.90], [0.95, 0.95, 0.90], [0.30, 0.55, 0.85],
      [0.85, 0.90, 0.95], [0.55, 0.80, 0.95], [0.70, 0.95, 0.95], [0.95, 0.90, 0.85],
    ],
    cabalPalette: [
      [0.95, 0.95, 1.00], [0.40, 0.95, 1.00], [0.85, 0.90, 0.40], [0.95, 0.55, 0.95],
      [0.55, 0.75, 1.00], [0.95, 1.00, 0.75], [0.30, 0.95, 0.85], [1.00, 0.85, 0.55],
    ],
    geometry: 'icosahedron',
    keyLight: { color: 0xcce0ff, intensity: 1.5, position: [800, 1400, 400] },
    ambient: { color: 0x305878, intensity: 0.55 },
    bloom: { strength: 0.40, radius: 0.50, threshold: 0.85 },
    exposure: 0.85,
    bondColor: [0.85, 0.95, 1.00],
    dust: { visible: true, brightness: 0.55, palette: ramp(12, [0.50, 0.62], 0.45, 0.85) },
  },

  // 9 — Underworld: candlelit obsidian. Deep purple-black, restrained
  //     palette (deep reds + golds + indigos), gold accent on bonds
  //     and cabals. Dramatic warm key from below.
  {
    name: 'underworld',
    background: 0x080008,
    palette: [
      [0.55, 0.05, 0.10], [0.45, 0.10, 0.25], [0.30, 0.05, 0.35], [0.20, 0.10, 0.45],
      [0.10, 0.20, 0.55], [0.25, 0.30, 0.55], [0.55, 0.35, 0.10], [0.75, 0.50, 0.15],
      [0.85, 0.65, 0.25], [0.55, 0.20, 0.10], [0.40, 0.15, 0.20], [0.65, 0.10, 0.30],
    ],
    cabalPalette: [
      [0.95, 0.75, 0.25], [0.85, 0.20, 0.30], [0.40, 0.10, 0.55], [0.95, 0.95, 0.85],
      [0.20, 0.30, 0.85], [0.95, 0.50, 0.10], [0.65, 0.10, 0.65], [0.85, 0.35, 0.10],
    ],
    geometry: 'dodecahedron',
    keyLight: { color: 0xff9050, intensity: 0.85, position: [-200, -800, 1000] },
    ambient: { color: 0x180830, intensity: 0.40 },
    bloom: { strength: 1.0, radius: 0.65, threshold: 0.70 },
    exposure: 0.85,
    bondColor: [0.95, 0.65, 0.20],
    dust: { visible: true, brightness: 0.35, palette: ramp(12, [0.85, 0.05], 0.55, 0.40) },
  },
];

export function getActiveTheme() {
  const params = new URLSearchParams(window.location.search);
  const idx = parseInt(params.get('theme') ?? '0', 10);
  if (Number.isNaN(idx) || idx < 0 || idx >= THEMES.length) return THEMES[0];
  return THEMES[idx];
}

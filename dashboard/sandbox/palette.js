// Sector palette. Mirrors `engine/core/population.py:SECTOR_NAMES`.
// The 12-step palette is a bloom-friendly HSL rainbow at (i+0.5)/12.
// Week-4 polish will hand-tune these to the final art direction.

export const SECTOR_NAMES = [
  'agriculture',
  'extraction',
  'manufacturing',
  'energy',
  'logistics',
  'construction',
  'retail',
  'finance',
  'information',
  'health',
  'education',
  'leisure',
];

function hslToRgb(h, s, l) {
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

const PALETTE = SECTOR_NAMES.map((_, i) => {
  const h = (i + 0.5) / SECTOR_NAMES.length;
  // Saturation 0.62 / lightness 0.58: vivid enough that additive blend
  // separates neighbours, dim enough that bloom can lift them.
  return hslToRgb(h, 0.62, 0.58);
});

export function sectorPalette() {
  return PALETTE;
}

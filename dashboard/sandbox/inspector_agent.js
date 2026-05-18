// Click-to-inspect agent card (Phase 6 §7.1 of
// spatial-sandbox-completeness.md). Clicking on or near a
// caterpillar opens a card on the right side of the screen
// listing the agent's identity, state, norm vector, recent
// partners, and cluster membership.
//
// Hit-testing: the plan's "Math.floor(triangleIndex / MAX_TRAIL)"
// slot lookup assumes each agent occupies a fixed stride in the
// position buffer. agents.js packs the buffer dynamically (each
// agent contributes only its visible segment count, which varies
// with wealth bucket and humansOnly state), so that math doesn't
// work for this build. We do an analytic ray-sphere intersection
// (same approach as the sector hover) and then pick the nearest
// cast agent by current-face centroid. Within a small angular
// threshold the user reads it as "I clicked that agent."
//
// The card reads from:
//   - a Map<idx, castEntry> snapshot the scene.js keeps current;
//   - the cluster_labels accessor for cabal / syndicate id;
//   - the agents module for the agent's current face (drives the
//     pull marker on the sphere when the card is open).

import * as THREE from 'three';

const DRAG_PX_THRESHOLD = 4;
const HIT_ANGLE_THRESHOLD = 0.06;     // radians; ~3.4° → ~5% of R
                                       // on a sphere — picks up the
                                       // visible caterpillar even
                                       // when the click lands a
                                       // segment-width off.

export function createInspectorAgent(opts) {
  const {
    canvas, camera, agents, surface,
    sectorNames, sectorPalette,
    getCastEntry, getClusterId, getClusterStatus, getClusterTrack,
    cardEl, cardCloseEl, cardBodyEl,
  } = opts;

  let openIdx = -1;
  let mouseDownX = 0, mouseDownY = 0, mouseDownT = 0;

  function onMouseDown(ev) {
    if (ev.button !== 0) return;
    mouseDownX = ev.clientX;
    mouseDownY = ev.clientY;
    mouseDownT = performance.now();
  }

  function onMouseUp(ev) {
    if (ev.button !== 0) return;
    const dx = ev.clientX - mouseDownX;
    const dy = ev.clientY - mouseDownY;
    if (Math.sqrt(dx * dx + dy * dy) > DRAG_PX_THRESHOLD) return;
    const idx = pickAgentAt(ev.clientX, ev.clientY);
    if (idx < 0) {
      // Clicking off any agent doesn't close the card — Esc does.
      return;
    }
    openIdx = idx;
    renderCard();
  }

  function onKeyDown(ev) {
    if (ev.key === 'Escape' && openIdx >= 0) {
      openIdx = -1;
      hideCard();
    }
  }

  // Analytic ray-sphere intersection + nearest cast agent on the
  // sphere by angular distance to the hit point. Returns -1 if
  // no agent is within HIT_ANGLE_THRESHOLD radians of the hit.
  const _raycaster = new THREE.Raycaster();
  const _ndc = new THREE.Vector2();
  function pickAgentAt(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    _ndc.x = ((clientX - rect.left) / rect.width) * 2 - 1;
    _ndc.y = -((clientY - rect.top) / rect.height) * 2 + 1;
    _raycaster.setFromCamera(_ndc, camera);
    // Sphere center is at origin; ray-sphere intersection picks
    // the near hit at the substrate's nominal radius. The substrate
    // may be morphed by EBI (group.scale.y), but face centroids the
    // pickAgent step reads are the unmorphed positions — agents
    // pulls live face indices from agents.currentFaceForIdx().
    const r = surface.radius ?? 700;
    const o = _raycaster.ray.origin;
    const d = _raycaster.ray.direction;
    // |o + t·d|² = r² → solve quadratic in t.
    const b = 2 * (o.x * d.x + o.y * d.y + o.z * d.z);
    const c = o.x * o.x + o.y * o.y + o.z * o.z - r * r;
    const disc = b * b - 4 * c;
    if (disc < 0) return -1;
    const sqrtD = Math.sqrt(disc);
    const t0 = (-b - sqrtD) / 2;
    const t1 = (-b + sqrtD) / 2;
    const t = (t0 > 1e-3) ? t0 : (t1 > 1e-3 ? t1 : -1);
    if (t < 0) return -1;
    // Hit point on the *uniform* sphere — agents face centroids
    // live there too. Normalise to a direction.
    const hx = (o.x + d.x * t) / r;
    const hy = (o.y + d.y * t) / r;
    const hz = (o.z + d.z * t) / r;

    // Walk the most recent cast snapshot, find the agent whose
    // current face centroid is closest to the hit direction.
    const fc = surface.faceCentroids;
    let bestIdx = -1;
    let bestDot = Math.cos(HIT_ANGLE_THRESHOLD);
    // getCastEntry exposes the snapshot map; iteration is small
    // (cast = 5000 at full scale; ~5 ms).
    for (const [idx, ] of getCastEntry.entries()) {
      const f = agents.currentFaceForIdx(idx);
      if (f < 0) continue;
      const cx = fc[f * 3 + 0];
      const cy = fc[f * 3 + 1];
      const cz = fc[f * 3 + 2];
      const cn = Math.sqrt(cx * cx + cy * cy + cz * cz) || 1;
      const dot = (cx * hx + cy * hy + cz * hz) / cn;
      if (dot > bestDot) {
        bestDot = dot;
        bestIdx = idx;
      }
    }
    return bestIdx;
  }

  function hideCard() {
    if (cardEl) cardEl.style.display = 'none';
  }

  function renderCard() {
    if (openIdx < 0) { hideCard(); return; }
    const e = getCastEntry.get(openIdx);
    if (!e) { hideCard(); return; }
    if (!cardEl || !cardBodyEl) return;
    cardEl.style.display = '';
    // Each row is a small key/value pair; the radar canvas sits
    // at the bottom.
    const sectorName = sectorNames?.[e.sector] ?? `sector ${e.sector}`;
    const isHuman = e.is_human ? 'human' : 'agent';
    const firmSectors = Array.isArray(e.firm_sectors) ? e.firm_sectors : [];
    const cabalId = getClusterId ? getClusterId(openIdx) : -1;
    const cabalStatus = getClusterStatus ? getClusterStatus(cabalId) : null;
    const track = (cabalStatus === 'syndicate' && getClusterTrack)
      ? getClusterTrack(cabalId) : null;

    const rows = [
      ['idx',        String(openIdx)],
      ['kind',       isHuman],
      ['sector',     sectorName],
      ['stack',      String(e.stack ?? '?')],
      ['firm',       e.firm_id >= 0
                       ? `${e.firm_id} (${firmSectors.length || 1}-sec)`
                       : '—'],
      ['cabal',      cabalId >= 0
                       ? `${cabalId}${cabalStatus === 'syndicate' ? ' (syndicate)' : ''}`
                       : '—'],
      ['wealth',     fmtNumber(e.wealth)],
      ['capability', fmtFloat(e.capability)],
      ['autonomy',   fmtFloat(e.autonomy)],
      ['certified',  e.certified >= 0 ? fmtFloat(e.certified) : '—'],
      ['degree',     e.degree_centrality >= 0 ? String(e.degree_centrality) : '—'],
      ['norm dist',  e.norm_distance >= 0 ? fmtFloat(e.norm_distance) : '—'],
    ];
    if (track) {
      rows.push(['syn age', `${track.age} ticks`]);
      rows.push(['churn',   fmtFloat(track.churnEMA)]);
    }
    const recent = Array.isArray(e.recent_partners) ? e.recent_partners : [];
    rows.push(['partners', recent.length > 0 ? recent.slice(-5).join(', ') : '—']);

    let html = '';
    for (const [k, v] of rows) {
      html += `<div class="inspector-row"><span class="inspector-row-label">${k}</span><span class="inspector-row-value">${v}</span></div>`;
    }
    cardBodyEl.innerHTML = html;
    // Norm radar canvas — rebuild fresh.
    const nv = Array.isArray(e.norm_vector) ? e.norm_vector : [];
    if (nv.length >= 2) {
      const canvas = document.createElement('canvas');
      canvas.className = 'inspector-radar';
      canvas.width = 160; canvas.height = 160;
      cardBodyEl.appendChild(canvas);
      drawNormRadar(canvas, nv);
    }
  }

  function fmtFloat(v) {
    if (!Number.isFinite(v)) return '—';
    return v.toFixed(3);
  }
  function fmtNumber(v) {
    if (!Number.isFinite(v)) return '—';
    if (Math.abs(v) >= 100) return v.toFixed(0);
    return v.toFixed(2);
  }

  // 8-axis (or K-axis) norm radar. Axes spaced equally around the
  // circle; each axis carries one component of the norm vector,
  // clipped to [0, 1]. The polygon's vertex on axis k sits at
  // radius `v_k * R`. Background grid at 0.25/0.5/0.75 so the user
  // can read magnitudes.
  function drawNormRadar(canvas, nv) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    const cx = w / 2, cy = h / 2;
    const R = Math.min(w, h) * 0.40;
    ctx.clearRect(0, 0, w, h);
    const K = nv.length;

    // Grid rings.
    ctx.strokeStyle = 'rgba(26, 20, 18, 0.18)';
    ctx.lineWidth = 1;
    for (const f of [0.25, 0.5, 0.75, 1.0]) {
      ctx.beginPath();
      for (let k = 0; k < K; k += 1) {
        const a = (k / K) * Math.PI * 2 - Math.PI / 2;
        const x = cx + Math.cos(a) * R * f;
        const y = cy + Math.sin(a) * R * f;
        if (k === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.stroke();
    }

    // Axes.
    ctx.strokeStyle = 'rgba(26, 20, 18, 0.10)';
    for (let k = 0; k < K; k += 1) {
      const a = (k / K) * Math.PI * 2 - Math.PI / 2;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(a) * R, cy + Math.sin(a) * R);
      ctx.stroke();
    }

    // Norm vector polygon.
    ctx.fillStyle = 'rgba(102, 140, 200, 0.20)';
    ctx.strokeStyle = 'rgba(102, 140, 200, 0.85)';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    for (let k = 0; k < K; k += 1) {
      let v = nv[k];
      if (!Number.isFinite(v)) v = 0;
      v = Math.max(0, Math.min(1, v));
      const a = (k / K) * Math.PI * 2 - Math.PI / 2;
      const x = cx + Math.cos(a) * R * v;
      const y = cy + Math.sin(a) * R * v;
      if (k === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }

  // Public surface.
  function attach() {
    canvas.addEventListener('mousedown', onMouseDown);
    canvas.addEventListener('mouseup', onMouseUp);
    window.addEventListener('keydown', onKeyDown);
    if (cardCloseEl) {
      cardCloseEl.addEventListener('click', () => {
        openIdx = -1;
        hideCard();
      });
    }
    hideCard();
  }
  function detach() {
    canvas.removeEventListener('mousedown', onMouseDown);
    canvas.removeEventListener('mouseup', onMouseUp);
    window.removeEventListener('keydown', onKeyDown);
  }
  // Called whenever a new cast snapshot lands so the card refreshes.
  function refresh() {
    if (openIdx >= 0) renderCard();
  }
  function openIdxOf() { return openIdx; }
  function pickFromEvent(ev) { return pickAgentAt(ev.clientX, ev.clientY); }

  return { attach, detach, refresh, openIdxOf, pickFromEvent };
}

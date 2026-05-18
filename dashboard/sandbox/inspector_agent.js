// Click-to-inspect (Phase 6 §7.1 of spatial-sandbox-completeness.md).
//
// A stack of inspector cards on the left of the screen. Two card
// kinds:
//
//   agent   — opened when a click lands within HIT_ANGLE_AGENT of
//             a cast agent's current face centroid. Carries
//             identity, state, recent partners, and a K-axis norm
//             radar.
//
//   cluster — opened when a click lands beyond HIT_ANGLE_AGENT but
//             within HIT_ANGLE_CLUSTER of a clustered agent. Carries
//             the cabal / syndicate identity, member count, status,
//             sector composition pie, and the Jaccard sparkline.
//
// Interactions:
//
//   plain click  replaces every unpinned card with the new pick.
//   shift-click  adds a new card to the stack (max 4 cards).
//   Pin          toggles a per-card flag — pinned cards survive
//                subsequent plain clicks and Esc.
//   Watch        cluster-only — flashes the card red when the
//                cluster's churnEMA crosses a threshold.
//   Esc          closes the top card on the stack (most recent
//                first), skipping pinned cards.
//   ×            close button on each card.
//
// Hit-testing uses analytic ray-sphere intersection followed by an
// angular-nearest search over the cast. The plan §7.1 spec'd a
// full BufferGeometry raycaster with `Math.floor(triangleIndex /
// MAX_TRAIL)` slot lookup; agents.js packs the buffer dynamically
// (visible-segment count varies per agent), so that math doesn't
// produce the right slot. The nearest-face approach reads
// correctly under the same dynamic layout.

import * as THREE from 'three';

const DRAG_PX_THRESHOLD = 4;
const HIT_ANGLE_AGENT = 0.06;       // ~3.4° → ~5% of R
const HIT_ANGLE_CLUSTER = 0.14;     // ~8° → ~14% of R; widens the
                                    // hit window when nothing's
                                    // directly under the cursor
const MAX_CARDS = 4;
const WATCH_CHURN_THRESHOLD = 0.30;

export function createInspectorAgent(opts) {
  const {
    canvas, camera, agents, surface,
    sectorNames, sectorPalette,
    getCastEntry,
    getClusterId, getClusterStatus, getClusterTrack,
    getClusterMembers,                          // (cabalId) → [idx, ...] | null
    stackEl,                                     // <div id="inspector-stack">
  } = opts;

  // Stack of open cards. Each:
  //   { kind: 'agent' | 'cluster', id, pinned, watching, alert,
  //     el, bodyEl, pinBtn, watchBtn, closeBtn }
  // `id` is the agent idx (agent kind) or cluster stableId
  // (cluster kind).
  const cards = [];
  let mouseDownX = 0, mouseDownY = 0;

  function onMouseDown(ev) {
    if (ev.button !== 0) return;
    mouseDownX = ev.clientX;
    mouseDownY = ev.clientY;
  }

  function onMouseUp(ev) {
    if (ev.button !== 0) return;
    const dx = ev.clientX - mouseDownX;
    const dy = ev.clientY - mouseDownY;
    if (Math.sqrt(dx * dx + dy * dy) > DRAG_PX_THRESHOLD) return;
    const pick = pickAt(ev.clientX, ev.clientY);
    if (!pick) return;
    if (ev.shiftKey) {
      // Add without disturbing existing cards (subject to MAX_CARDS).
      addCard(pick);
    } else {
      // Replace all unpinned cards with the new pick.
      replaceUnpinned(pick);
    }
  }

  function onKeyDown(ev) {
    if (ev.key === 'Escape') {
      // Close the most recent unpinned card.
      for (let i = cards.length - 1; i >= 0; i -= 1) {
        if (!cards[i].pinned) { closeAt(i); return; }
      }
    }
  }

  // Analytic ray-sphere intersection + nearest cast agent.
  // Returns { kind: 'agent', id: idx } or { kind: 'cluster', id }
  // or null if nothing's close enough.
  const _raycaster = new THREE.Raycaster();
  const _ndc = new THREE.Vector2();
  function pickAt(clientX, clientY) {
    const rect = canvas.getBoundingClientRect();
    _ndc.x = ((clientX - rect.left) / rect.width) * 2 - 1;
    _ndc.y = -((clientY - rect.top) / rect.height) * 2 + 1;
    _raycaster.setFromCamera(_ndc, camera);
    const r = surface.radius ?? 700;
    const o = _raycaster.ray.origin;
    const d = _raycaster.ray.direction;
    const b = 2 * (o.x * d.x + o.y * d.y + o.z * d.z);
    const c = o.x * o.x + o.y * o.y + o.z * o.z - r * r;
    const disc = b * b - 4 * c;
    if (disc < 0) return null;
    const sqrtD = Math.sqrt(disc);
    const t0 = (-b - sqrtD) / 2;
    const t1 = (-b + sqrtD) / 2;
    const t = (t0 > 1e-3) ? t0 : (t1 > 1e-3 ? t1 : -1);
    if (t < 0) return null;
    const hx = (o.x + d.x * t) / r;
    const hy = (o.y + d.y * t) / r;
    const hz = (o.z + d.z * t) / r;

    const fc = surface.faceCentroids;
    let bestAgent = -1;
    let bestAgentDot = Math.cos(HIT_ANGLE_AGENT);
    let bestNearAgent = -1;
    let bestNearAgentDot = Math.cos(HIT_ANGLE_CLUSTER);
    for (const [idx, ] of getCastEntry.entries()) {
      const f = agents.currentFaceForIdx(idx);
      if (f < 0) continue;
      const cx = fc[f * 3 + 0];
      const cy = fc[f * 3 + 1];
      const cz = fc[f * 3 + 2];
      const cn = Math.sqrt(cx * cx + cy * cy + cz * cz) || 1;
      const dot = (cx * hx + cy * hy + cz * hz) / cn;
      if (dot > bestAgentDot) {
        bestAgentDot = dot;
        bestAgent = idx;
      }
      if (dot > bestNearAgentDot) {
        bestNearAgentDot = dot;
        bestNearAgent = idx;
      }
    }
    if (bestAgent >= 0) return { kind: 'agent', id: bestAgent };
    if (bestNearAgent >= 0) {
      const cid = getClusterId ? getClusterId(bestNearAgent) : -1;
      if (cid >= 0) return { kind: 'cluster', id: cid };
    }
    return null;
  }

  function addCard(pick) {
    // Don't duplicate an already-open card.
    for (const c of cards) {
      if (c.kind === pick.kind && c.id === pick.id) return;
    }
    if (cards.length >= MAX_CARDS) {
      // Push out the oldest unpinned card. If every card is
      // pinned, refuse the new one.
      let dropIdx = -1;
      for (let i = 0; i < cards.length; i += 1) {
        if (!cards[i].pinned) { dropIdx = i; break; }
      }
      if (dropIdx < 0) return;
      closeAt(dropIdx);
    }
    const card = buildCard(pick.kind, pick.id);
    cards.push(card);
    renderCard(card);
  }

  function replaceUnpinned(pick) {
    // Close every unpinned card, then add the pick.
    for (let i = cards.length - 1; i >= 0; i -= 1) {
      if (!cards[i].pinned) closeAt(i);
    }
    addCard(pick);
  }

  function buildCard(kind, id) {
    const el = document.createElement('div');
    el.className = 'inspector-card';
    const header = document.createElement('div');
    header.className = 'inspector-card-header';
    const title = document.createElement('span');
    title.className = 'inspector-card-title';
    title.textContent = kind;
    header.appendChild(title);
    const pinBtn = document.createElement('button');
    pinBtn.className = 'inspector-card-btn';
    pinBtn.type = 'button';
    pinBtn.textContent = 'pin';
    header.appendChild(pinBtn);
    let watchBtn = null;
    if (kind === 'cluster') {
      watchBtn = document.createElement('button');
      watchBtn.className = 'inspector-card-btn';
      watchBtn.type = 'button';
      watchBtn.textContent = 'watch';
      header.appendChild(watchBtn);
    }
    const closeBtn = document.createElement('button');
    closeBtn.className = 'inspector-card-close';
    closeBtn.type = 'button';
    closeBtn.textContent = '×';
    header.appendChild(closeBtn);
    el.appendChild(header);
    const bodyEl = document.createElement('div');
    el.appendChild(bodyEl);
    stackEl.appendChild(el);

    const card = {
      kind, id, pinned: false, watching: false, alert: false,
      el, bodyEl, pinBtn, watchBtn, closeBtn,
    };

    pinBtn.addEventListener('click', () => {
      card.pinned = !card.pinned;
      el.classList.toggle('pinned', card.pinned);
      pinBtn.classList.toggle('active', card.pinned);
    });
    if (watchBtn) {
      watchBtn.addEventListener('click', () => {
        card.watching = !card.watching;
        el.classList.toggle('watching', card.watching);
        watchBtn.classList.toggle('active', card.watching);
        if (!card.watching) { el.classList.remove('alert'); card.alert = false; }
      });
    }
    closeBtn.addEventListener('click', () => {
      const idx = cards.indexOf(card);
      if (idx >= 0) closeAt(idx);
    });
    return card;
  }

  function closeAt(i) {
    const card = cards[i];
    if (!card) return;
    if (card.el && card.el.parentNode) card.el.parentNode.removeChild(card.el);
    cards.splice(i, 1);
  }

  function renderCard(card) {
    if (card.kind === 'agent') renderAgentCard(card);
    else renderClusterCard(card);
  }

  function renderAgentCard(card) {
    const e = getCastEntry.get(card.id);
    if (!e) { closeAt(cards.indexOf(card)); return; }
    const sectorName = sectorNames?.[e.sector] ?? `sector ${e.sector}`;
    const isHuman = e.is_human ? 'human' : 'agent';
    const firmSectors = Array.isArray(e.firm_sectors) ? e.firm_sectors : [];
    const cabalId = getClusterId ? getClusterId(card.id) : -1;
    const cabalStatus = getClusterStatus ? getClusterStatus(cabalId) : null;
    const track = (cabalStatus === 'syndicate' && getClusterTrack)
      ? getClusterTrack(cabalId) : null;

    const rows = [
      ['idx',        String(card.id)],
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
    card.bodyEl.innerHTML = html;
    const nv = Array.isArray(e.norm_vector) ? e.norm_vector : [];
    if (nv.length >= 2) {
      const canvas = document.createElement('canvas');
      canvas.className = 'inspector-radar';
      canvas.width = 160; canvas.height = 160;
      card.bodyEl.appendChild(canvas);
      drawNormRadar(canvas, nv);
    }
  }

  function renderClusterCard(card) {
    const track = getClusterTrack ? getClusterTrack(card.id) : null;
    if (!track) { closeAt(cards.indexOf(card)); return; }
    const status = track.status;
    const members = getClusterMembers ? (getClusterMembers(card.id) ?? []) : [];

    // Sector composition: count members by sector_id pulled from
    // the cast snapshot.
    const sectorCounts = new Map();
    let memberWealth = [];
    for (const idx of members) {
      const e = getCastEntry.get(idx);
      if (!e) continue;
      if (typeof e.sector === 'number') {
        sectorCounts.set(e.sector, (sectorCounts.get(e.sector) ?? 0) + 1);
      }
      if (Number.isFinite(e.wealth)) memberWealth.push(e.wealth);
    }
    memberWealth.sort((a, b) => a - b);
    const median = memberWealth.length === 0 ? null
      : memberWealth[Math.floor(memberWealth.length / 2)];

    const rows = [
      ['id',     `${card.id}`],
      ['status', status],
      ['size',   String(track.memberCount)],
      ['age',    `${track.age} ticks`],
      ['churn',  fmtFloat(track.churnEMA)],
      ['median wealth', median !== null ? fmtNumber(median) : '—'],
    ];
    if (status === 'syndicate' && Number.isInteger(track.promotedAt)) {
      rows.push(['promoted', `tick ${track.promotedAt}`]);
    }
    let html = '';
    for (const [k, v] of rows) {
      html += `<div class="inspector-row"><span class="inspector-row-label">${k}</span><span class="inspector-row-value">${v}</span></div>`;
    }
    card.bodyEl.innerHTML = html;

    // Sector pie.
    if (sectorPalette && sectorCounts.size > 0) {
      const pie = document.createElement('canvas');
      pie.className = 'inspector-sector-pie';
      pie.width = 80; pie.height = 80;
      card.bodyEl.appendChild(pie);
      drawSectorPie(pie, sectorCounts);
      // Compact legend for the pie.
      const sorted = Array.from(sectorCounts.entries())
        .sort((a, b) => b[1] - a[1]).slice(0, 5);
      for (const [sec, count] of sorted) {
        const row = document.createElement('div');
        row.className = 'inspector-sector-row';
        const sw = document.createElement('span');
        sw.className = 'swatch';
        const c = sectorPalette[sec] ?? [0.5, 0.5, 0.5];
        sw.style.background = `rgb(${Math.round(c[0] * 255)},${Math.round(c[1] * 255)},${Math.round(c[2] * 255)})`;
        row.appendChild(sw);
        const nameSpan = document.createElement('span');
        nameSpan.textContent = `${sectorNames?.[sec] ?? `sector ${sec}`} (${count})`;
        row.appendChild(nameSpan);
        card.bodyEl.appendChild(row);
      }
    }

    // Jaccard sparkline.
    const jhist = Array.isArray(track.jaccardHistory) ? track.jaccardHistory : [];
    if (jhist.length >= 2) {
      const spark = document.createElement('canvas');
      spark.className = 'inspector-jaccard-spark';
      spark.width = 198; spark.height = 28;
      card.bodyEl.appendChild(spark);
      drawJaccardSpark(spark, jhist);
    }

    // Watch alert.
    if (card.watching) {
      const churn = track.churnEMA;
      const alert = Number.isFinite(churn) && churn > WATCH_CHURN_THRESHOLD;
      if (alert !== card.alert) {
        card.alert = alert;
        card.el.classList.toggle('alert', alert);
      }
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

  function drawNormRadar(canvas, nv) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    const cx = w / 2, cy = h / 2;
    const R = Math.min(w, h) * 0.40;
    ctx.clearRect(0, 0, w, h);
    const K = nv.length;
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
    ctx.strokeStyle = 'rgba(26, 20, 18, 0.10)';
    for (let k = 0; k < K; k += 1) {
      const a = (k / K) * Math.PI * 2 - Math.PI / 2;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + Math.cos(a) * R, cy + Math.sin(a) * R);
      ctx.stroke();
    }
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

  function drawSectorPie(canvas, sectorCounts) {
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;
    const cx = w / 2, cy = h / 2;
    const R = Math.min(w, h) * 0.46;
    ctx.clearRect(0, 0, w, h);
    let total = 0;
    for (const v of sectorCounts.values()) total += v;
    if (total === 0) return;
    let a0 = -Math.PI / 2;
    for (const [sec, count] of sectorCounts) {
      const a1 = a0 + (count / total) * Math.PI * 2;
      const c = sectorPalette?.[sec] ?? [0.5, 0.5, 0.5];
      ctx.fillStyle = `rgb(${Math.round(c[0] * 255)},${Math.round(c[1] * 255)},${Math.round(c[2] * 255)})`;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.arc(cx, cy, R, a0, a1);
      ctx.closePath();
      ctx.fill();
      a0 = a1;
    }
  }

  function drawJaccardSpark(canvas, hist) {
    const ctx = canvas.getContext('2d');
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const targetW = Math.floor(canvas.clientWidth * dpr);
    const targetH = Math.floor(canvas.clientHeight * dpr);
    if (targetW > 0 && canvas.width !== targetW) canvas.width = targetW;
    if (targetH > 0 && canvas.height !== targetH) canvas.height = targetH;
    const w = canvas.width;
    const h = canvas.height;
    ctx.clearRect(0, 0, w, h);
    // Promote threshold reference line at 0.9.
    ctx.strokeStyle = 'rgba(80, 168, 96, 0.45)';
    ctx.lineWidth = 1;
    ctx.setLineDash([2 * dpr, 2 * dpr]);
    ctx.beginPath();
    const y90 = h - 0.9 * h;
    ctx.moveTo(0, y90); ctx.lineTo(w, y90); ctx.stroke();
    ctx.setLineDash([]);
    // History polyline.
    ctx.strokeStyle = 'rgba(140, 102, 191, 0.95)';
    ctx.lineWidth = 1.5 * dpr;
    ctx.beginPath();
    const n = hist.length;
    for (let i = 0; i < n; i += 1) {
      const x = (i / Math.max(1, n - 1)) * w;
      let v = hist[i];
      if (!Number.isFinite(v)) v = 0;
      if (v < 0) v = 0; if (v > 1) v = 1;
      const y = h - v * h;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  // Public surface.
  function attach() {
    canvas.addEventListener('mousedown', onMouseDown);
    canvas.addEventListener('mouseup', onMouseUp);
    window.addEventListener('keydown', onKeyDown);
  }
  function detach() {
    canvas.removeEventListener('mousedown', onMouseDown);
    canvas.removeEventListener('mouseup', onMouseUp);
    window.removeEventListener('keydown', onKeyDown);
  }
  function refresh() {
    // Re-render every open card. Closed cards from disappeared
    // tracks naturally collapse during renderClusterCard.
    for (let i = cards.length - 1; i >= 0; i -= 1) {
      renderCard(cards[i]);
    }
  }
  function reset() {
    while (cards.length > 0) closeAt(cards.length - 1);
  }
  function diagnostics() {
    return {
      cards: cards.map((c) => ({
        kind: c.kind, id: c.id, pinned: c.pinned,
        watching: c.watching, alert: c.alert,
      })),
    };
  }
  // Test hook — synthesize a pick result by passing a canvas event.
  function pickFromEvent(ev) { return pickAt(ev.clientX, ev.clientY); }
  // Test hook — programmatically open a card without a click.
  function openCard(kind, id, shift = false) {
    const pick = { kind, id };
    if (shift) addCard(pick);
    else replaceUnpinned(pick);
  }

  return {
    attach, detach, refresh, reset,
    diagnostics, pickFromEvent, openCard,
  };
}

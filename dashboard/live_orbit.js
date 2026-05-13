/*
 * dashboard/live_orbit.js — Three.js 3D sector orbit (Orbit tab).
 *
 * Twelve sector glyphs arranged on a circle in 3D space; each executed
 * pair fires an additive-blended arc of light between source and
 * destination. Bloom post-processing makes the arcs feel volumetric.
 * Camera slowly orbits the scene on idle; OrbitControls let the user
 * grab it.
 *
 * Loads three.js + post-processing addons from a CDN as ES modules.
 * `window.createOrbit(host) → { applyStep, reset, dispose }`.
 *
 * This view trades precision for atmosphere. The Flow tab is more
 * honest about per-pair detail; Orbit answers "what does this
 * economy feel like at scale" — most useful in screen recordings
 * and presentations.
 */
(function () {
  'use strict';

  const SECTOR_NAMES = (window.LP_SECTOR_NAMES || [
    'agriculture', 'extraction', 'manufacturing', 'energy',
    'logistics', 'construction', 'retail', 'finance',
    'information', 'health', 'education', 'leisure',
  ]);
  const N_SECTORS = SECTOR_NAMES.length;

  const STYLE = `
    .lp-orbit-host { background: #050608; border: 1px solid var(--border); border-radius: 3px; overflow: hidden; position: relative; }
    .lp-orbit-controls { display: flex; gap: 8px; align-items: center; padding: 10px 14px; font-family: var(--mono); font-size: 11px; color: var(--text-3); border-bottom: 1px solid var(--border); background: var(--panel); }
    .lp-orbit-status { margin-left: auto; }
    .lp-orbit-canvas { width: 100%; height: 540px; display: block; }
    .lp-orbit-empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--text-3); font-family: var(--mono); font-size: 12px; pointer-events: none; }
    .lp-orbit-chip { padding: 4px 10px; background: var(--panel-2); border: 1px solid var(--border); border-radius: 3px; cursor: pointer; color: var(--text-2); user-select: none; }
    .lp-orbit-chip.active { background: var(--accent); color: #1a1208; border-color: var(--accent); }
  `;

  function ensureStyle() {
    if (!document.querySelector('style[data-lp-orbit]')) {
      const s = document.createElement('style');
      s.setAttribute('data-lp-orbit', '1');
      s.textContent = STYLE;
      document.head.appendChild(s);
    }
  }

  // Three.js + post-processing loaded as ES modules via an import map.
  // Done once globally so the addons resolve `three` against the same
  // module instance the main module exports.
  let threePromise = null;
  function ensureThree() {
    if (threePromise) return threePromise;
    threePromise = (async () => {
      // Install an import map if not already present.
      if (!document.querySelector('script[type="importmap"][data-lp-orbit]')) {
        const m = document.createElement('script');
        m.type = 'importmap';
        m.dataset.lpOrbit = '1';
        m.textContent = JSON.stringify({
          imports: {
            'three': 'https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js',
            'three/addons/': 'https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/',
          },
        });
        document.head.appendChild(m);
      }
      const three = await import('three');
      const { OrbitControls } = await import('three/addons/controls/OrbitControls.js');
      const { EffectComposer } = await import('three/addons/postprocessing/EffectComposer.js');
      const { RenderPass } = await import('three/addons/postprocessing/RenderPass.js');
      const { UnrealBloomPass } = await import('three/addons/postprocessing/UnrealBloomPass.js');
      return { THREE: three, OrbitControls, EffectComposer, RenderPass, UnrealBloomPass };
    })();
    return threePromise;
  }

  function sectorColor3(THREE, i) {
    if (window.d3 && window.d3.interpolateRainbow) {
      const c = window.d3.interpolateRainbow((i + 0.5) / N_SECTORS);
      const m = c.match(/rgb\((\d+),\s*(\d+),\s*(\d+)\)/);
      if (m) return new THREE.Color(`rgb(${m[1]},${m[2]},${m[3]})`);
    }
    const fallback = [
      0xb89a55, 0x5fa572, 0xc25a5a, 0x5b8ec4,
      0x9077c2, 0xd99b6b, 0x7caec1, 0xa3a85a,
      0xbd6fa6, 0x6cb39e, 0xc0795a, 0x8e9aa8,
    ];
    return new THREE.Color(fallback[i % fallback.length]);
  }

  async function createOrbit(host) {
    ensureStyle();
    host.innerHTML = '';
    const wrap = document.createElement('div');
    wrap.className = 'lp-orbit-host';
    host.appendChild(wrap);

    const controls = document.createElement('div');
    controls.className = 'lp-orbit-controls';
    const autoRotateChip = document.createElement('span');
    autoRotateChip.className = 'lp-orbit-chip active';
    autoRotateChip.textContent = 'auto-rotate';
    const status = document.createElement('span');
    status.className = 'lp-orbit-status';
    status.textContent = 'loading three.js…';
    controls.appendChild(document.createTextNode('3D sector orbit · drag to rotate · scroll to zoom'));
    controls.appendChild(autoRotateChip);
    controls.appendChild(status);
    wrap.appendChild(controls);

    const canvas = document.createElement('canvas');
    canvas.className = 'lp-orbit-canvas';
    wrap.appendChild(canvas);
    const emptyState = document.createElement('div');
    emptyState.className = 'lp-orbit-empty';
    emptyState.textContent = 'arcs appear here once the run starts';
    wrap.appendChild(emptyState);

    let three;
    try {
      three = await ensureThree();
    } catch (e) {
      status.textContent = 'three.js load failed';
      emptyState.textContent = e.message || String(e);
      emptyState.style.color = 'var(--red)';
      return { applyStep: () => {}, reset: () => {}, dispose: () => {} };
    }
    const { THREE, OrbitControls, EffectComposer, RenderPass, UnrealBloomPass } = three;

    // ---- scene -----------------------------------------------------------
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050608);
    scene.fog = new THREE.FogExp2(0x050608, 0.012);

    const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 1000);
    camera.position.set(0, 70, 130);

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio);

    function resize() {
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      renderer.setSize(w, h, false);
      camera.aspect = w / Math.max(h, 1);
      camera.updateProjectionMatrix();
      composer.setSize(w, h);
    }

    const orbit = new OrbitControls(camera, canvas);
    orbit.enableDamping = true;
    orbit.dampingFactor = 0.08;
    orbit.autoRotate = true;
    orbit.autoRotateSpeed = 0.45;
    orbit.minDistance = 60;
    orbit.maxDistance = 300;

    autoRotateChip.addEventListener('click', () => {
      orbit.autoRotate = !orbit.autoRotate;
      autoRotateChip.classList.toggle('active', orbit.autoRotate);
    });

    // ---- sector nodes ----------------------------------------------------
    const SECTOR_R = 60;
    const sectorPositions = [];
    for (let i = 0; i < N_SECTORS; i += 1) {
      const a = (i / N_SECTORS) * 2 * Math.PI;
      sectorPositions.push(new THREE.Vector3(SECTOR_R * Math.cos(a), 0, SECTOR_R * Math.sin(a)));
    }

    const sectorGroup = new THREE.Group();
    scene.add(sectorGroup);
    const sectorMeshes = [];
    for (let i = 0; i < N_SECTORS; i += 1) {
      const color = sectorColor3(THREE, i);
      const geo = new THREE.IcosahedronGeometry(2.4, 1);
      const mat = new THREE.MeshStandardMaterial({
        color,
        emissive: color,
        emissiveIntensity: 0.7,
        metalness: 0.3,
        roughness: 0.4,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.copy(sectorPositions[i]);
      sectorGroup.add(mesh);
      sectorMeshes.push(mesh);

      // Floating label as a sprite.
      const cvs = document.createElement('canvas');
      cvs.width = 256; cvs.height = 64;
      const ctx = cvs.getContext('2d');
      ctx.font = 'bold 24px JetBrains Mono, monospace';
      ctx.fillStyle = '#9ea2a8';
      ctx.textBaseline = 'middle';
      ctx.textAlign = 'center';
      ctx.fillText(SECTOR_NAMES[i].toUpperCase(), 128, 32);
      const tex = new THREE.CanvasTexture(cvs);
      const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, opacity: 0.9 }));
      sprite.scale.set(14, 3.5, 1);
      sprite.position.copy(sectorPositions[i]).add(new THREE.Vector3(0, 8, 0));
      sectorGroup.add(sprite);
    }

    // Ground reference grid.
    const grid = new THREE.PolarGridHelper(SECTOR_R + 10, 12, 4, 64, 0x2a2d33, 0x14161a);
    grid.material.opacity = 0.4;
    grid.material.transparent = true;
    scene.add(grid);

    // Lights.
    scene.add(new THREE.AmbientLight(0x404a55, 0.6));
    const key = new THREE.DirectionalLight(0xfff0d8, 0.5);
    key.position.set(60, 80, 40);
    scene.add(key);

    // ---- arcs ------------------------------------------------------------
    // Each active arc is a TubeGeometry along a quadratic Bézier curve;
    // we recycle a small pool to keep allocations bounded.
    const ARC_LIFETIME_MS = 1400;
    const ARC_POOL_SIZE = 600;
    const arcPool = [];        // available
    const liveArcs = [];        // in flight

    function makeArc() {
      const mat = new THREE.MeshBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      });
      const dummyCurve = new THREE.QuadraticBezierCurve3(
        new THREE.Vector3(0, 0, 0),
        new THREE.Vector3(0, 10, 0),
        new THREE.Vector3(0, 0, 0),
      );
      const geom = new THREE.TubeGeometry(dummyCurve, 20, 0.35, 8, false);
      const mesh = new THREE.Mesh(geom, mat);
      mesh.visible = false;
      scene.add(mesh);
      return { mesh, mat, curve: dummyCurve };
    }
    for (let i = 0; i < ARC_POOL_SIZE; i += 1) arcPool.push(makeArc());

    function recycleExpired(now) {
      for (let i = liveArcs.length - 1; i >= 0; i -= 1) {
        const a = liveArcs[i];
        if (now - a.t0 > ARC_LIFETIME_MS) {
          a.mesh.visible = false;
          arcPool.push(a);
          liveArcs.splice(i, 1);
        }
      }
    }

    function emitArc(rec, now) {
      if (!arcPool.length) return; // pool exhausted; drop spawn
      const a = arcPool.pop();
      const src = sectorPositions[rec.sec_a];
      const dst = sectorPositions[rec.sec_b];
      if (!src || !dst) { arcPool.push(a); return; }
      const apex = src.clone().add(dst).multiplyScalar(0.5);
      const dist = src.distanceTo(dst);
      apex.y += 14 + dist * 0.18;
      a.curve = new THREE.QuadraticBezierCurve3(src.clone(), apex, dst.clone());
      // Rebuild tube geometry from new curve.
      a.mesh.geometry.dispose();
      a.mesh.geometry = new THREE.TubeGeometry(a.curve, 24, 0.4, 8, false);
      a.mat.color = sectorColor3(THREE, rec.sec_a);
      a.mat.opacity = 0.85;
      a.mesh.visible = true;
      a.t0 = now;
      a.dur = ARC_LIFETIME_MS;
      liveArcs.push(a);
    }

    // ---- post-processing -------------------------------------------------
    const composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    const bloom = new UnrealBloomPass(new THREE.Vector2(1024, 1024), 0.95, 0.5, 0.15);
    composer.addPass(bloom);

    // Sized via ResizeObserver so swapping tabs / resizing the panel
    // refreshes the viewport without manual nudges.
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    resize();

    // ---- animation loop --------------------------------------------------
    let raf;
    function frame() {
      const now = performance.now();
      // Fade live arcs over their lifetime.
      for (const a of liveArcs) {
        const u = (now - a.t0) / a.dur;
        a.mat.opacity = Math.max(0, 0.85 * (1 - u));
      }
      recycleExpired(now);
      // Pulse the sector glyphs subtly.
      for (let i = 0; i < sectorMeshes.length; i += 1) {
        const m = sectorMeshes[i];
        m.rotation.x = now * 0.0006 + i * 0.3;
        m.rotation.y = now * 0.0008 + i * 0.5;
      }
      orbit.update();
      composer.render();
      raf = requestAnimationFrame(frame);
    }
    raf = requestAnimationFrame(frame);

    // ---- public API ------------------------------------------------------

    function applyStep(step) {
      const pairs = step.pair_samples || [];
      if (!pairs.length) return;
      emptyState.style.display = 'none';
      const now = performance.now();
      // Stagger spawns so a 1500-pair burst doesn't melt the pool.
      const TAKE = Math.min(pairs.length, 400);
      const stagger = 400 / TAKE;
      for (let i = 0; i < TAKE; i += 1) {
        const rec = pairs[i];
        if (!rec.executed) continue;
        // Offsetting t0 by stagger lets the spawn read as a wave.
        setTimeout(() => emitArc(rec, performance.now()), i * stagger);
      }
      status.textContent = `step ${step.step} · spawning ${TAKE} arcs · ${liveArcs.length} live · pool ${arcPool.length}`;
    }

    function reset() {
      // Retire all live arcs.
      for (const a of liveArcs) {
        a.mesh.visible = false;
        arcPool.push(a);
      }
      liveArcs.length = 0;
      status.textContent = 'idle';
      emptyState.style.display = '';
    }

    function dispose() {
      cancelAnimationFrame(raf);
      ro.disconnect();
      // Free geometries / materials (best-effort).
      for (const a of [...arcPool, ...liveArcs]) {
        if (a.mesh.geometry) a.mesh.geometry.dispose();
        if (a.mat) a.mat.dispose();
      }
      renderer.dispose();
    }

    status.textContent = 'idle · waiting for run';
    return { applyStep, reset, dispose };
  }

  window.createOrbit = createOrbit;
})();

// Cast renderer (Pass 10) — InstancedMesh of low-poly icosahedrons.
//
// Each cell is an actual 3D mesh with vertex normals, shaded by a
// directional light + emissive term. One draw call covers all 5,000
// cells via three.js InstancedMesh; per-instance attributes carry
// color, human flag, scale, and flash time so the GPU does the
// human/agent differentiation and flash decay.
//
// Lighting goes through the cell's standard normal, so cells read as
// real spheres with a lit hemisphere and a shadowed one. Emissive
// contribution stacks on top so cells stay luminous and the bloom
// pass has something to lift.
//
// Motion: home-tether (weak spring to the Fibonacci spawn point) +
// per-frame Brownian tangent + bond springs (from bonds.js) +
// per-snapshot wealth-delta impulse. Same model as Pass 9.

import * as THREE from 'three';

import { SECTOR_NAMES, sectorPalette } from './palette.js';

const FLASH_FRAMES = 30;
const FLASH_REL_THRESHOLD = 0.02;
const FLASH_ABS_FLOOR = 0.05;
const ACTIVITY_FADE = 0.86;

const BASE_SCALE_AGENT = 1.8;
const BASE_SCALE_HUMAN = 4.5;
// Cell size is wealth-driven. `scale = base * (SCALE_FLOOR +
// log1p(wealth) * SCALE_GROWTH)` so a poor cell stays ~0.7× base and
// a wealthy cell (wealth ~100) reaches ~2.5× base. Cells visibly
// inflate and deflate as wealth flows through them.
const SCALE_FLOOR = 0.7;
const SCALE_GROWTH = 0.3;

// Motion magnitudes get multiplied by per-cell autonomy. High-
// autonomy cells wander and rotate visibly; low-autonomy ones barely
// move. The two scalars are the base coefficients; per-cell scaling
// happens inside tick().
const BROWNIAN_BASE = 0.32;
const ROT_SPEED_MIN = 0.002;        // rad/frame at autonomy = 0
const ROT_SPEED_MAX = 0.018;        // rad/frame at autonomy = 1

const HOMING_K = 0.018;
const WEALTH_IMPULSE_K = 14.0;
const WEALTH_IMPULSE_CAP = 22.0;
const BOND_SPRING_K = 0.55;
const BOND_SPRING_REST = 16;
const MOTION_DAMPING = 0.86;
const MAX_SPEED = 18;

const NEVER_FLASHED = -1e9;

// Map theme geometry strings to actual THREE buffer geometries. Each
// resulting geometry is the unit-1 base; the InstancedMesh per-slot
// matrix scales it.
function buildCellGeometry(kind) {
  switch (kind) {
    case 'icosahedron':
      return new THREE.IcosahedronGeometry(1, 1);
    case 'octahedron':
      return new THREE.OctahedronGeometry(1, 0);
    case 'tetrahedron':
      return new THREE.TetrahedronGeometry(1, 0);
    case 'box':
      return new THREE.BoxGeometry(1.4, 1.4, 1.4);
    case 'sphere':
      return new THREE.SphereGeometry(1, 12, 8);
    case 'dodecahedron':
    default:
      return new THREE.DodecahedronGeometry(1, 0);
  }
}

// Vertex shader: applies the per-instance matrix three.js attaches
// to InstancedMesh, transforms the icosahedron's vertex normal into
// view space for Lambert lighting, and passes flash/activity to the
// fragment shader. Three.js auto-declares `attribute mat4 instanceMatrix`
// when this material is used with InstancedMesh.
const VERTEX_SHADER = /* glsl */ `
  attribute vec3 aInstColor;
  attribute float aIsHuman;
  attribute float aFlashTime;
  attribute float aActivity;

  uniform float uCurrentFrame;
  uniform float uFlashFrames;

  varying vec3 vColor;
  varying vec3 vNormalView;
  varying float vIsHuman;
  varying float vFlash;
  varying float vActivity;

  void main() {
    vColor = aInstColor;
    vIsHuman = aIsHuman;
    vActivity = clamp(aActivity, 0.0, 1.0);

    float age = uCurrentFrame - aFlashTime;
    vFlash = clamp(1.0 - age / uFlashFrames, 0.0, 1.0);

    // Apply instance transform then view + projection.
    vec4 instancePos = instanceMatrix * vec4(position, 1.0);
    vec4 mvPos = modelViewMatrix * instancePos;

    // Normal in view space. Uniform scale assumption — fine for our
    // setMatrixAt usage which only translates + uniformly scales.
    mat3 nmat = mat3(modelViewMatrix * instanceMatrix);
    vNormalView = normalize(nmat * normal);

    gl_Position = projectionMatrix * mvPos;
  }
`;

// Fragment shader: Lambert diffuse + emissive term. Humans take a
// warm gold mix in their lit channel and a brightness boost; agents
// render the sector palette straight. The emissive lift on flash is
// what the bloom pass picks up.
const FRAGMENT_SHADER = /* glsl */ `
  precision highp float;

  uniform vec3 uLightDirView;
  uniform float uAmbient;

  varying vec3 vColor;
  varying vec3 vNormalView;
  varying float vIsHuman;
  varying float vFlash;
  varying float vActivity;

  void main() {
    // Lambert diffuse, kept well below saturation so the cells read
    // as physical 3D objects rather than blown-out blobs. The
    // overall multiplier of 0.55 is what gives the scene its breathing
    // room — bloom only catches genuine emissive events on top.
    float NdotL = max(dot(normalize(vNormalView), normalize(uLightDirView)), 0.0);
    vec3 diffuse = vColor * (uAmbient + (1.0 - uAmbient) * NdotL) * 0.55;

    // Emissive only fires meaningfully on active or flashing cells.
    // Baseline 0 so quiet cells stay quiet; activity + flash push
    // them above the bloom threshold.
    float emissiveLevel = 0.10 * vActivity + 0.85 * vFlash;
    vec3 emissive = vColor * emissiveLevel;

    if (vIsHuman > 0.5) {
      vec3 gold = vec3(1.00, 0.86, 0.55);
      diffuse = mix(diffuse, diffuse * gold * 1.15, 0.45);
      emissive *= 1.3;
    }

    gl_FragColor = vec4(diffuse + emissive, 1.0);
  }
`;

/**
 * Build the cast renderer.
 *
 * @param {THREE.Scene} scene
 * @param {{
 *   maxAgents?: number,
 *   layoutRadius?: number,
 * }} opts
 */
export function createAgents(scene, opts = {}) {
  const maxAgents = opts.maxAgents ?? 5000;
  const radius = opts.layoutRadius ?? 400;

  const palette = sectorPalette();

  // Cell geometry — themes can pick a different polyhedron via the
  // `geometry` opt to vary the per-cell silhouette across the field.
  const geometry = buildCellGeometry(opts.geometry ?? 'dodecahedron');

  // Per-instance attributes via InstancedBufferAttribute.
  const colorsBuf = new Float32Array(maxAgents * 3);
  const isHumanBuf = new Float32Array(maxAgents);
  const flashTimesBuf = new Float32Array(maxAgents);
  flashTimesBuf.fill(NEVER_FLASHED);
  const activitiesBuf = new Float32Array(maxAgents);

  geometry.setAttribute(
    'aInstColor',
    new THREE.InstancedBufferAttribute(colorsBuf, 3),
  );
  geometry.setAttribute(
    'aIsHuman',
    new THREE.InstancedBufferAttribute(isHumanBuf, 1),
  );
  geometry.setAttribute(
    'aFlashTime',
    new THREE.InstancedBufferAttribute(flashTimesBuf, 1),
  );
  geometry.setAttribute(
    'aActivity',
    new THREE.InstancedBufferAttribute(activitiesBuf, 1),
  );

  const material = new THREE.ShaderMaterial({
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
    uniforms: {
      uCurrentFrame: { value: 0 },
      uFlashFrames: { value: FLASH_FRAMES },
      uLightDirView: { value: new THREE.Vector3(0.4, 0.8, 0.6).normalize() },
      uAmbient: { value: 0.22 },
    },
    transparent: false,
    depthWrite: true,
  });

  const mesh = new THREE.InstancedMesh(geometry, material, maxAgents);
  mesh.frustumCulled = false;
  mesh.count = 0;  // ramps up once initialLayout runs
  scene.add(mesh);

  // Per-slot motion buffers.
  const positions = new Float32Array(maxAgents * 3);
  const velocities = new Float32Array(maxAgents * 3);
  const homes = new Float32Array(maxAgents * 3);
  const scales = new Float32Array(maxAgents);
  const baseSizes = new Float32Array(maxAgents);
  // Per-slot wealth and autonomy snapshot from the engine. wealth
  // drives the cell scale (size grows with wealth); autonomy drives
  // motion magnitude + rotation speed (more autonomous = more
  // movement and faster spin).
  const wealths = new Float32Array(maxAgents);
  const autonomies = new Float32Array(maxAgents);
  // Per-cell rotation axis (unit vector) and accumulated angle for
  // setMatrixAt. Each cell has its own random axis so the facet
  // structure reads differently across the field.
  const rotAxes = new Float32Array(maxAgents * 3);
  const rotAngles = new Float32Array(maxAgents);
  const rotSpeeds = new Float32Array(maxAgents);
  const targetRadii = new Float32Array(maxAgents);
  targetRadii.fill(radius);

  const slotByIdx = new Map();
  const lastWealth = new Float32Array(maxAgents);
  lastWealth.fill(NaN);

  let bondsRef = null;
  let initialized = false;
  let castCount = 0;
  let currentFrame = 0;

  // Scratch matrix4 + temp object for the InstancedMesh per-frame
  // setMatrixAt loop. Allocating these once and reusing avoids GC
  // pressure at 60fps × 5,000 instances.
  const dummy = new THREE.Object3D();
  const _rotAxis = new THREE.Vector3();

  function fibonacci(slot, total, out) {
    if (total <= 1) {
      out[0] = 0; out[1] = 0; out[2] = radius;
      return;
    }
    const phi = Math.PI * (3.0 - Math.sqrt(5.0));
    const y = 1.0 - (slot / (total - 1)) * 2.0;
    const r = Math.sqrt(Math.max(0, 1.0 - y * y));
    const theta = phi * slot;
    out[0] = Math.cos(theta) * r * radius;
    out[1] = y * radius;
    out[2] = Math.sin(theta) * r * radius;
  }

  function initialLayout(snapshot) {
    // Sort by sector ascending, then idx within sector for stability.
    const sorted = snapshot.slice().sort((a, b) => {
      if (a.sector !== b.sector) return a.sector - b.sector;
      return a.idx - b.idx;
    });
    castCount = Math.min(sorted.length, maxAgents);

    const tmp = [0, 0, 0];
    for (let slot = 0; slot < castCount; slot += 1) {
      const entry = sorted[slot];
      slotByIdx.set(entry.idx, slot);

      fibonacci(slot, castCount, tmp);
      positions[slot * 3 + 0] = tmp[0];
      positions[slot * 3 + 1] = tmp[1];
      positions[slot * 3 + 2] = tmp[2];

      homes[slot * 3 + 0] = tmp[0];
      homes[slot * 3 + 1] = tmp[1];
      homes[slot * 3 + 2] = tmp[2];

      const human = !!entry.is_human;
      isHumanBuf[slot] = human ? 1.0 : 0.0;
      baseSizes[slot] = human ? BASE_SCALE_HUMAN : BASE_SCALE_AGENT;

      // Initial wealth + autonomy from the first snapshot. The per-
      // snapshot handler keeps these up to date as the engine
      // streams ticks; scale + rotation read from them every frame.
      wealths[slot] = entry.wealth ?? 1.0;
      autonomies[slot] = Math.max(0, Math.min(1, entry.autonomy ?? 0.5));

      // Initial scale from wealth — gradient anchored before motion
      // begins so cells boot at the right size.
      scales[slot] = baseSizes[slot] *
        (SCALE_FLOOR + Math.log1p(Math.max(0, wealths[slot])) * SCALE_GROWTH);

      // Random unit axis for per-cell rotation.
      let rx, ry, rz, l2;
      do {
        rx = Math.random() * 2 - 1;
        ry = Math.random() * 2 - 1;
        rz = Math.random() * 2 - 1;
        l2 = rx * rx + ry * ry + rz * rz;
      } while (l2 === 0 || l2 > 1);
      const inv = 1 / Math.sqrt(l2);
      rotAxes[slot * 3 + 0] = rx * inv;
      rotAxes[slot * 3 + 1] = ry * inv;
      rotAxes[slot * 3 + 2] = rz * inv;
      // Rotation speed maps from autonomy. Cells with autonomy 1
      // spin fast; cells with autonomy 0 barely turn.
      rotSpeeds[slot] =
        ROT_SPEED_MIN + (ROT_SPEED_MAX - ROT_SPEED_MIN) * autonomies[slot];
      // Random initial phase so the field isn't synchronised.
      rotAngles[slot] = Math.random() * Math.PI * 2;
    }

    // Upload initial instance matrices to the GPU so cells appear
    // before the first rAF tick (Chrome background-throttles new
    // tabs; without this, the canvas reads as empty until focus).
    for (let i = 0; i < castCount; i += 1) {
      _rotAxis.set(
        rotAxes[i * 3 + 0],
        rotAxes[i * 3 + 1],
        rotAxes[i * 3 + 2],
      );
      dummy.position.set(
        positions[i * 3 + 0],
        positions[i * 3 + 1],
        positions[i * 3 + 2],
      );
      dummy.quaternion.setFromAxisAngle(_rotAxis, rotAngles[i]);
      dummy.scale.setScalar(scales[i]);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;

    geometry.getAttribute('aIsHuman').needsUpdate = true;
    mesh.count = castCount;
    initialized = true;
  }

  function handleCastSnapshot(snapshot) {
    if (!snapshot || snapshot.length === 0) return;
    if (!initialized) initialLayout(snapshot);

    for (let i = 0; i < castCount; i += 1) {
      activitiesBuf[i] *= ACTIVITY_FADE;
    }

    for (let i = 0; i < snapshot.length; i += 1) {
      const entry = snapshot[i];
      const slot = slotByIdx.get(entry.idx);
      if (slot === undefined) continue;

      const palIdx = ((entry.sector % palette.length) + palette.length) % palette.length;
      const rgb = palette[palIdx];
      colorsBuf[slot * 3 + 0] = rgb[0];
      colorsBuf[slot * 3 + 1] = rgb[1];
      colorsBuf[slot * 3 + 2] = rgb[2];

      // Refresh wealth and autonomy from the snapshot. Scale is
      // recomputed each tick from current wealth so cells visibly
      // inflate/deflate as wealth flows. Autonomy updates the
      // rotation speed and Brownian magnitude (read in tick()).
      const w = entry.wealth ?? 0;
      wealths[slot] = w;
      autonomies[slot] = Math.max(0, Math.min(1, entry.autonomy ?? autonomies[slot]));
      scales[slot] = baseSizes[slot] *
        (SCALE_FLOOR + Math.log1p(Math.max(0, w)) * SCALE_GROWTH);
      rotSpeeds[slot] =
        ROT_SPEED_MIN + (ROT_SPEED_MAX - ROT_SPEED_MIN) * autonomies[slot];

      const prev = lastWealth[slot];
      lastWealth[slot] = w;
      if (Number.isNaN(prev)) continue;

      const delta = w - prev;
      const adelta = Math.abs(delta);
      activitiesBuf[slot] += adelta * 1.4;

      const wRef = Math.max(prev, 1e-3);
      const rel = adelta / wRef;
      if (rel > FLASH_REL_THRESHOLD || adelta > FLASH_ABS_FLOOR) {
        flashTimesBuf[slot] = currentFrame;
      }

      // Wealth-delta velocity impulse, random tangent.
      if (adelta > 0) {
        let mag = adelta * WEALTH_IMPULSE_K;
        if (mag > WEALTH_IMPULSE_CAP) mag = WEALTH_IMPULSE_CAP;
        const px = positions[slot * 3 + 0];
        const py = positions[slot * 3 + 1];
        const pz = positions[slot * 3 + 2];
        const rx = Math.random() - 0.5;
        const ry = Math.random() - 0.5;
        const rz = Math.random() - 0.5;
        const tx = py * rz - pz * ry;
        const ty = pz * rx - px * rz;
        const tz = px * ry - py * rx;
        const tlen = Math.sqrt(tx * tx + ty * ty + tz * tz);
        if (tlen > 1e-6) {
          const s = mag / tlen;
          velocities[slot * 3 + 0] += tx * s;
          velocities[slot * 3 + 1] += ty * s;
          velocities[slot * 3 + 2] += tz * s;
        }
      }
    }

    geometry.getAttribute('aInstColor').needsUpdate = true;
    geometry.getAttribute('aActivity').needsUpdate = true;
    geometry.getAttribute('aFlashTime').needsUpdate = true;
  }

  function tick() {
    currentFrame += 1;
    material.uniforms.uCurrentFrame.value = currentFrame;

    if (!initialized || castCount === 0) return;

    if (bondsRef) {
      for (const { a, b, strength } of bondsRef.iterBonds()) {
        const ax = positions[a * 3 + 0];
        const ay = positions[a * 3 + 1];
        const az = positions[a * 3 + 2];
        const dx = positions[b * 3 + 0] - ax;
        const dy = positions[b * 3 + 1] - ay;
        const dz = positions[b * 3 + 2] - az;
        const d2 = dx * dx + dy * dy + dz * dz + 1e-6;
        const d = Math.sqrt(d2);
        const f = BOND_SPRING_K * strength * (d - BOND_SPRING_REST) / d;
        const fx = dx * f;
        const fy = dy * f;
        const fz = dz * f;
        velocities[a * 3 + 0] += fx;
        velocities[a * 3 + 1] += fy;
        velocities[a * 3 + 2] += fz;
        velocities[b * 3 + 0] -= fx;
        velocities[b * 3 + 1] -= fy;
        velocities[b * 3 + 2] -= fz;
      }
    }

    for (let i = 0; i < castCount; i += 1) {
      const px = positions[i * 3 + 0];
      const py = positions[i * 3 + 1];
      const pz = positions[i * 3 + 2];

      // Home tether.
      velocities[i * 3 + 0] += (homes[i * 3 + 0] - px) * HOMING_K;
      velocities[i * 3 + 1] += (homes[i * 3 + 1] - py) * HOMING_K;
      velocities[i * 3 + 2] += (homes[i * 3 + 2] - pz) * HOMING_K;

      // Autonomy-scaled tangential noise. Magnitude proportional to
      // the cell's current autonomy — high-autonomy agents wander
      // visibly, low-autonomy ones stay near home. Direction stays
      // random per-frame so motion reads as walk, not drift.
      const rx = Math.random() - 0.5;
      const ry = Math.random() - 0.5;
      const rz = Math.random() - 0.5;
      const tx = py * rz - pz * ry;
      const ty = pz * rx - px * rz;
      const tz = px * ry - py * rx;
      const tlen2 = tx * tx + ty * ty + tz * tz;
      if (tlen2 > 1e-6) {
        const mag = BROWNIAN_BASE * autonomies[i];
        const tinv = mag / Math.sqrt(tlen2);
        velocities[i * 3 + 0] += tx * tinv;
        velocities[i * 3 + 1] += ty * tinv;
        velocities[i * 3 + 2] += tz * tinv;
      }

      let vx = velocities[i * 3 + 0] * MOTION_DAMPING;
      let vy = velocities[i * 3 + 1] * MOTION_DAMPING;
      let vz = velocities[i * 3 + 2] * MOTION_DAMPING;

      const v2 = vx * vx + vy * vy + vz * vz;
      if (v2 > MAX_SPEED * MAX_SPEED) {
        const sc = MAX_SPEED / Math.sqrt(v2);
        vx *= sc; vy *= sc; vz *= sc;
      }
      velocities[i * 3 + 0] = vx;
      velocities[i * 3 + 1] = vy;
      velocities[i * 3 + 2] = vz;

      const nx = px + vx;
      const ny = py + vy;
      const nz = pz + vz;

      const r = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1;
      const s = targetRadii[i] / r;
      positions[i * 3 + 0] = nx * s;
      positions[i * 3 + 1] = ny * s;
      positions[i * 3 + 2] = nz * s;
    }

    // Re-pack instance matrices: position + rotation + uniform scale.
    // Rotation accumulates per slot at the slot's own speed so cells
    // catch the directional light's specular hits at different
    // angles, reading as crystalline objects rather than spheres.
    for (let i = 0; i < castCount; i += 1) {
      rotAngles[i] += rotSpeeds[i];
      _rotAxis.set(
        rotAxes[i * 3 + 0],
        rotAxes[i * 3 + 1],
        rotAxes[i * 3 + 2],
      );
      dummy.position.set(
        positions[i * 3 + 0],
        positions[i * 3 + 1],
        positions[i * 3 + 2],
      );
      dummy.quaternion.setFromAxisAngle(_rotAxis, rotAngles[i]);
      dummy.scale.setScalar(scales[i]);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
  }

  function setBonds(bonds) {
    bondsRef = bonds;
  }

  function resetTargetRadii() {
    targetRadii.fill(radius);
  }

  function setSlotRadius(slot, r) {
    if (slot < 0 || slot >= maxAgents) return;
    targetRadii[slot] = r;
  }

  // Update the light direction uniform from a world-space vector.
  // scene.js calls this when the camera moves so the lit hemisphere
  // stays anchored to the world light rather than rotating with the
  // viewpoint.
  function setLightDirView(viewSpaceDir) {
    material.uniforms.uLightDirView.value.copy(viewSpaceDir);
  }

  function getPosition(idx, out) {
    const slot = slotByIdx.get(idx);
    if (slot === undefined) return null;
    const base = slot * 3;
    const dst = out ?? [0, 0, 0];
    dst[0] = positions[base + 0];
    dst[1] = positions[base + 1];
    dst[2] = positions[base + 2];
    return dst;
  }

  function slotForIdx(idx) {
    const slot = slotByIdx.get(idx);
    return slot === undefined ? -1 : slot;
  }

  function slotCount() {
    return castCount;
  }

  function invalidatePositions() {
    // No-op now — positions go through setMatrixAt in tick(). Kept
    // for API compat with the prior Points-based renderer.
  }

  function setVisible(visible) {
    mesh.visible = !!visible;
  }

  function dispose() {
    scene.remove(mesh);
    geometry.dispose();
    material.dispose();
    slotByIdx.clear();
  }

  function diagnostics() {
    return { castCount, currentFrame, initialized };
  }

  return {
    mesh,
    handleCastSnapshot,
    tick,
    setBonds,
    resetTargetRadii,
    setSlotRadius,
    setLightDirView,
    getPosition,
    setVisible,
    dispose,
    diagnostics,
    positions,
    slotForIdx,
    slotCount,
    invalidatePositions,
    layoutRadius: radius,
    _slotByIdx: slotByIdx,
  };
}

export { SECTOR_NAMES };

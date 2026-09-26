// The story: how film grain forms, classically and on a quantum computer. Every frame is a pure function of the
// story's clock t, so scrubbing, replaying and recording draw the same pictures. Captions are drawn into the canvas,
// so a recording carries them.
import * as THREE from "three";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";
import { OutputPass } from "three/addons/postprocessing/OutputPass.js";
import { mulberry32, pauliKernel, newTile, place, density, decodeMasks, sitesOf } from "./law.js";

const W = 1920, H = 1080;
const canvas = document.getElementById("story");
const msg = document.getElementById("stage-msg");

// ---------- timing ----------
const S = {
  title: [0, 7], emulsion: [6, 21], expose: [20, 33], develop: [32, 45], grain: [44, 56],
  tile: [55, 72], hole: [71, 87], shots: [86, 97], stack: [96, 110], print: [109, 120],
  compare: [119, 138], record: [137, 149], credits: [148, 160],
};
const END = 160;
const CAPTIONS = [
  [7, 20, "A sheet of film is gelatin holding silver halide crystals, scattered at random."],
  [21, 32, "Light makes the crystals it strikes developable: a latent image."],
  [33, 44, "The developer turns those crystals to silver. The fixer washes the rest away."],
  [45, 55, "What remains is grain: clumps where crystals happened to gather, gaps where they did not. Chance, made permanent."],
  [56, 64, "Quantum film lays its crystals with a quantum circuit: sixteen qubits, one per site, holding five fermions."],
  [64, 69.4, "Fifty-one Givens rotations spread the five across the tile. Every site now holds a fermion with chance 5/16."],
  [69.6, 72.3, "Measure all sixteen qubits, and five crystals appear."],
  [72, 86, "Fermions obey Pauli exclusion. Place one, and the chance of another nearby falls: a hole opens around it."],
  [87, 96, "Measured on Moth's Atlas, each shot lays five crystals. Six jobs, 24,576 shots."],
  [97, 109, "Stacked twenty-nine layers deep, the shots coat a sheet at the density of Tri-X film."],
  [110, 119, "Developed and printed with atlas-film, on pinned arithmetic. Every crystal in this print was laid by Atlas."],
  [120, 127.8, "Random crystals clump and leave gaps. Pauli's crystals repel, so they spread more evenly."],
  [128, 137, "At the scales between a tile and its Fermi length, Pauli's grain carries roughly 30 to 65 percent of random film's noise power."],
  [138, 148, "Each print is fixed as a record: its rolls, its recipe, and the digest of every bit. Re-develop it, and the same print comes back."],
];

const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const smooth = (x) => { x = clamp(x); return x * x * (3 - 2 * x); };
const seg = (t, a, b) => clamp((t - a) / (b - a));
const bell = (t, a, b, f = 1) => smooth(seg(t, a, a + f)) * (1 - smooth(seg(t, b - f, b)));
const lerp = (a, b, u) => a + (b - a) * u;

// ---------- data ----------
const get = (p) => fetch(p).then((r) => { if (!r.ok) throw new Error(`${p}: HTTP ${r.status}`); return r.json(); });
let shotsData, fieldsData, structData;
try {
  [shotsData, fieldsData, structData] = await Promise.all([get("data/atlas-shots.json"), get("data/fields.json"),
                                                            get("data/structure.json")]);
} catch (e) {
  msg.textContent = `The story's data did not load (${e.message}). Serve this folder over HTTP.`;
  throw e;
}
const masks = decodeMasks(shotsData.masks_u16le_base64);

// ---------- renderer ----------
let renderer;
try {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
} catch (e) {
  msg.textContent = "This browser could not start WebGL, which the story needs.";
  throw e;
}
renderer.setPixelRatio(1);
renderer.setSize(W, H, false);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x05060a);
const camera = new THREE.PerspectiveCamera(36, W / H, 0.1, 500);
const composer = new EffectComposer(renderer);
composer.setSize(W, H);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(W, H), 0.55, 0.55, 0.8);
composer.addPass(bloom);
composer.addPass(new OutputPass());

scene.add(new THREE.AmbientLight(0xffffff, 0.55));
const sun = new THREE.DirectionalLight(0xfff2dd, 1.5);
sun.position.set(6, 12, 8);
scene.add(sun);
const rim = new THREE.DirectionalLight(0x88bbff, 0.6);
rim.position.set(-8, 4, -6);
scene.add(rim);

// HUD: a 2D canvas drawn every frame, laid over the render
const hud = document.createElement("canvas");
hud.width = W; hud.height = H;
const g = hud.getContext("2d");
const hudTex = new THREE.CanvasTexture(hud);
hudTex.colorSpace = THREE.SRGBColorSpace;
const hudScene = new THREE.Scene();
const hudCam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
hudScene.add(new THREE.Mesh(new THREE.PlaneGeometry(2, 2),
  new THREE.MeshBasicMaterial({ map: hudTex, transparent: true, depthTest: false, depthWrite: false, toneMapped: false })));

function discTexture(inner, outer) {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const x = c.getContext("2d");
  const grd = x.createRadialGradient(64, 64, 0, 64, 64, 64);
  grd.addColorStop(0, inner); grd.addColorStop(0.35, inner); grd.addColorStop(1, outer);
  x.fillStyle = grd; x.fillRect(0, 0, 128, 128);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
const glowTex = discTexture("rgba(255,255,255,1)", "rgba(255,255,255,0)");
const dotTex = (() => {
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const x = c.getContext("2d");
  x.fillStyle = "#fff"; x.beginPath(); x.arc(32, 32, 28, 0, Math.PI * 2); x.fill();
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
})();
const dummy = new THREE.Object3D();
const col = new THREE.Color();

// ---------- background dust ----------
const dust = (() => {
  const r = mulberry32(7), n = 700, pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) { pos[3 * i] = (r() - 0.5) * 80; pos[3 * i + 1] = (r() - 0.5) * 50; pos[3 * i + 2] = (r() - 0.5) * 80; }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const m = new THREE.Points(geo, new THREE.PointsMaterial({ size: 2, sizeAttenuation: false, color: 0x8899aa,
    transparent: true, opacity: 0.35, map: dotTex, depthWrite: false }));
  scene.add(m);
  return m;
})();

// ---------- 1. the emulsion ----------
const film = new THREE.Group();
scene.add(film);
const SLAB = { w: 16, h: 2.2, d: 10 };
const gelMat = new THREE.MeshStandardMaterial({ color: 0xd8b476, transparent: true, opacity: 0.1, roughness: 0.3,
  depthWrite: false });
const gel = new THREE.Mesh(new THREE.BoxGeometry(SLAB.w, SLAB.h, SLAB.d), gelMat);
gel.position.y = SLAB.h / 2;
film.add(gel);
const edgeMat = new THREE.LineBasicMaterial({ color: 0xf0b454, transparent: true, opacity: 0.35 });
const edges = new THREE.LineSegments(new THREE.EdgesGeometry(gel.geometry), edgeMat);
edges.position.copy(gel.position);
film.add(edges);
const baseMat = new THREE.MeshStandardMaterial({ color: 0x27303f, transparent: true, opacity: 0.85, roughness: 0.6 });
const base = new THREE.Mesh(new THREE.BoxGeometry(SLAB.w, 0.45, SLAB.d), baseMat);
base.position.y = -0.24;
film.add(base);
const tableMat = new THREE.MeshBasicMaterial({ color: 0xe9e4d8, transparent: true, opacity: 0 });
const table = new THREE.Mesh(new THREE.PlaneGeometry(60, 40), tableMat);
table.rotation.x = -Math.PI / 2;
table.position.y = -0.55;
film.add(table);

const NC = 1900;
const crystals = (() => {
  const r = mulberry32(11), out = [];
  const lum = (x, z) => {                       // the scene the film sees: a ramp and a bright disc
    const u = (x + SLAB.w / 2) / SLAB.w, v = (z + SLAB.d / 2) / SLAB.d;
    const disc = (u - 0.32) ** 2 + ((v - 0.5) * 0.625) ** 2 < 0.03 ? 0.55 : 0;
    return clamp(0.08 + 0.55 * u + disc, 0, 0.95);
  };
  for (let i = 0; i < NC; i++) {
    const x = (r() - 0.5) * (SLAB.w - 0.3), y = 0.15 + r() * (SLAB.h - 0.3), z = (r() - 0.5) * (SLAB.d - 0.3);
    const exposed = r() < lum(x, z);
    out.push({ x, y, z, rx: r() * 6, ry: r() * 6, exposed, hit: S.expose[0] + 1.5 + r() * 8.5, fix: r() });
  }
  return out;
})();
const crystalMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.35, metalness: 0.25,
  transparent: true, opacity: 1 });
const crystalMesh = new THREE.InstancedMesh(new THREE.OctahedronGeometry(0.12), crystalMat, NC);
crystalMesh.frustumCulled = false;
for (let i = 0; i < NC; i++) crystalMesh.setColorAt(i, col.set(0xe9dfc4));
film.add(crystalMesh);
const HALIDE = new THREE.Color(0xe9dfc4), SILVER = new THREE.Color(0x14161b);

// the latent image: a flash where a photon lands on a crystal
const flashGeo = new THREE.BufferGeometry();
flashGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(NC * 3), 3));
flashGeo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(NC * 3), 3));
const flashes = new THREE.Points(flashGeo, new THREE.PointsMaterial({ size: 44, sizeAttenuation: false, map: glowTex,
  vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
film.add(flashes);
crystals.forEach((c, i) => flashGeo.attributes.position.setXYZ(i, c.x, c.y, c.z));

// photons: short streaks falling onto exposed crystals, and some passing between
const NP = 1400;
const photons = (() => {
  const r = mulberry32(23), list = [];
  crystals.forEach((c) => { if (c.exposed) list.push({ x: c.x, z: c.z, stop: c.y, t: c.hit }); });
  while (list.length < NP) list.push({ x: (r() - 0.5) * SLAB.w, z: (r() - 0.5) * SLAB.d, stop: -0.3,
                                       t: S.expose[0] + 1.5 + r() * 9 });
  return list;
})();
const photonGeo = new THREE.BufferGeometry();
photonGeo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(NP * 6), 3));
photonGeo.setAttribute("color", new THREE.BufferAttribute(new Float32Array(NP * 6), 3));
const photonLines = new THREE.LineSegments(photonGeo, new THREE.LineBasicMaterial({ vertexColors: true,
  transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
film.add(photonLines);

// clump and gap markers for the grain view
const markMat = new THREE.MeshBasicMaterial({ color: 0xf0b454, transparent: true, opacity: 0, side: THREE.DoubleSide });
const marks = (() => {
  const grid = 8, cnt = new Map();
  crystals.forEach((c) => {
    if (!c.exposed) return;
    const k = `${Math.floor((c.x + SLAB.w / 2) / SLAB.w * grid * 1.6)},${Math.floor((c.z + SLAB.d / 2) / SLAB.d * grid)}`;
    cnt.set(k, (cnt.get(k) || 0) + 1);
  });
  let best = null, bestN = -1;
  for (const [k, n] of cnt) if (n > bestN) { bestN = n; best = k; }
  const [bi, bj] = best.split(",").map(Number);
  const cx = (bi + 0.5) / (grid * 1.6) * SLAB.w - SLAB.w / 2, cz = (bj + 0.5) / grid * SLAB.d - SLAB.d / 2;
  const out = [];
  for (const [x, z, rad] of [[cx, cz, 0.95]]) {
    const m = new THREE.Mesh(new THREE.RingGeometry(rad, rad + 0.07, 64), markMat);
    m.rotation.x = -Math.PI / 2;
    m.position.set(x, 2.5, z);
    film.add(m);
    out.push(m);
  }
  return out;
})();

// ---------- 2. the quantum tile ----------
const tile = new THREE.Group();
scene.add(tile);
const SITE = 1.9;
const sitePos = (s) => new THREE.Vector3(((s % 4) - 1.5) * SITE, 0, (Math.floor(s / 4) - 1.5) * SITE);
const qubitMat = new THREE.MeshStandardMaterial({ color: 0x3a4a5a, emissive: 0x0b2a3a, roughness: 0.3,
  metalness: 0.4, transparent: true });
const qubits = [];
for (let s = 0; s < 16; s++) {
  const m = new THREE.Mesh(new THREE.SphereGeometry(0.28, 32, 16), qubitMat);
  m.position.copy(sitePos(s));
  tile.add(m);
  qubits.push(m);
}
const lineGeo = new THREE.BufferGeometry().setFromPoints([...Array(16).keys()].map((s) => sitePos(s)));
const lineMat = new THREE.LineBasicMaterial({ color: 0x3d8fb8, transparent: true, opacity: 0.5 });
tile.add(new THREE.Line(lineGeo, lineMat));
const halos = [];
for (let s = 0; s < 16; s++) {
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color: 0x6fd3ff, transparent: true,
    blending: THREE.AdditiveBlending, depthWrite: false }));
  sp.position.copy(sitePos(s)).setY(0.02);
  tile.add(sp);
  halos.push(sp);
}
const pulseMat = new THREE.SpriteMaterial({ map: glowTex, color: 0xffffff, transparent: true,
  blending: THREE.AdditiveBlending, depthWrite: false });
const pulses = [];
for (let i = 0; i < 8; i++) { const p = new THREE.Sprite(pulseMat); p.scale.setScalar(0.45); tile.add(p); pulses.push(p); }
const tileCrystalMat = new THREE.MeshStandardMaterial({ color: 0xfff1d0, emissive: 0x6a5020, roughness: 0.3,
  metalness: 0.3, transparent: true });
const tileCrystals = [];
for (let s = 0; s < 16; s++) {
  const m = new THREE.Mesh(new THREE.OctahedronGeometry(0.42), tileCrystalMat);
  m.position.copy(sitePos(s)).setY(0.55);
  tile.add(m);
  tileCrystals.push(m);
}
// the rotations spread five fermions from the line's first five sites to 5/16 everywhere (a stylised schedule)
const occupation = (u) => [...Array(16).keys()].map((s) => lerp(s < 5 ? 1 : 0, 5 / 16, smooth(clamp(u * 1.15 - s / 40))));

// ---------- 3. the exclusion hole on a 16 x 16 tile ----------
const hole = new THREE.Group();
hole.position.set(2.2, 0, -0.6);               // clear of the label and the caption
scene.add(hole);
const HSITE = 0.62;
const holeSeq = (() => {
  const st = newTile("pauli", 16, 8, 20260926);
  const maps = [density(st)];
  while (st.order.length < st.N) { place(st); maps.push(density(st)); }
  return { order: st.order, maps, N: st.N };
})();
const cellMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true });
const cells = new THREE.InstancedMesh(new THREE.PlaneGeometry(HSITE * 0.92, HSITE * 0.92), cellMat, 256);
cells.frustumCulled = false;
for (let y = 0; y < 256; y++) {
  dummy.position.set(((y % 16) - 7.5) * HSITE, 0, (Math.floor(y / 16) - 7.5) * HSITE);
  dummy.rotation.set(-Math.PI / 2, 0, 0);
  dummy.scale.setScalar(1);
  dummy.updateMatrix();
  cells.setMatrixAt(y, dummy.matrix);
  cells.setColorAt(y, col.set(0x000000));
}
hole.add(cells);
const holeCrystals = new THREE.InstancedMesh(new THREE.OctahedronGeometry(0.2), tileCrystalMat, 25);
holeCrystals.frustumCulled = false;
hole.add(holeCrystals);
function heat(v, out) {                        // 0 -> deep blue, 1 -> cyan, 2 -> white
  v = clamp(v / 2);
  if (v < 0.5) return out.setRGB(0.02 + 0.1 * v, 0.03 + 0.9 * v, 0.1 + 1.4 * v);
  const u = (v - 0.5) * 2;
  return out.setRGB(0.07 + 0.93 * u, 0.48 + 0.52 * u, 0.8 + 0.2 * u);
}

// ---------- 4. the stack: Atlas shots, 29 layers of 12 x 12 tiles ----------
const stack = new THREE.Group();
scene.add(stack);
const ST = { tiles: 12, layers: 29, pitch: 0.26, dy: 0.075 };
const stackItems = (() => {
  const r = mulberry32(31), idx = [];
  for (let i = 0; i < masks.length; i++) idx.push(i);
  for (let i = idx.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [idx[i], idx[j]] = [idx[j], idx[i]]; }
  const side = ST.tiles * 4, out = [];
  let k = 0;
  for (let l = 0; l < ST.layers; l++) {
    const oy = Math.floor(r() * 4), ox = Math.floor(r() * 4);
    for (let ty = 0; ty < ST.tiles; ty++) for (let tx = 0; tx < ST.tiles; tx++) {
      for (const s of sitesOf(masks[idx[k]])) {
        const rr = (ty * 4 + Math.floor(s / 4) + oy) % side, cc = (tx * 4 + (s % 4) + ox) % side;
        out.push({ l, x: (cc - side / 2 + 0.5) * ST.pitch, z: (rr - side / 2 + 0.5) * ST.pitch });
      }
      k++;
    }
  }
  return out;
})();
const stackMat = new THREE.MeshStandardMaterial({ color: 0xf3e6c8, emissive: 0x2a2010, roughness: 0.4,
  metalness: 0.2, transparent: true });
const stackMesh = new THREE.InstancedMesh(new THREE.BoxGeometry(ST.pitch * 0.72, ST.dy * 0.8, ST.pitch * 0.72),
  stackMat, stackItems.length);
stackMesh.frustumCulled = false;
stack.add(stackMesh);

// the developed print, from docs/prints
const printTex = await new THREE.TextureLoader().loadAsync("img/atlas-pauli-4x4-print.png");
printTex.colorSpace = THREE.SRGBColorSpace;
printTex.magFilter = THREE.NearestFilter;
printTex.minFilter = THREE.LinearFilter;
printTex.generateMipmaps = false;
const printMat = new THREE.MeshBasicMaterial({ map: printTex, color: 0xbdbdbd, transparent: true, opacity: 0,
  toneMapped: false });
const printSide = ST.tiles * 4 * ST.pitch;
const printPlane = new THREE.Mesh(new THREE.PlaneGeometry(printSide, printSide), printMat);
printPlane.rotation.x = -Math.PI / 2;
printPlane.position.set(0, ST.layers * ST.dy + 0.3, -1.3);   // above the caption
scene.add(printPlane);

// ---------- 5. the comparison: one layer of golden Pauli tiles beside its random twin ----------
const compare = new THREE.Group();
scene.add(compare);
const CROP = 64;                              // 4 x 4 tiles of the 8 x 8 exported: dots big enough to see spacing
function field(all, side, x0, colour) {
  const sites = all.filter((s) => s % side < CROP && Math.floor(s / side) < CROP);
  const pos = new Float32Array(sites.length * 3), span = 6.9;
  sites.forEach((s, i) => {
    pos[3 * i] = x0 + (((s % side) + 0.5) / CROP - 0.5) * span;
    pos[3 * i + 1] = 0;
    pos[3 * i + 2] = ((Math.floor(s / side) + 0.5) / CROP - 0.5) * span - 0.3;
  });
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const m = new THREE.Points(geo, new THREE.PointsMaterial({ size: 9, sizeAttenuation: false, map: dotTex,
    color: colour, transparent: true, depthWrite: false, alphaTest: 0.3 }));
  compare.add(m);
  return m;
}
const fieldRandom = field(fieldsData.poisson, fieldsData.side, -4.3, 0xf07a5a);
const fieldPauli = field(fieldsData.pauli, fieldsData.side, 4.3, 0x6fd3ff);

// ---------- camera path: [t, position, target] ----------
const KEYS = [
  [0, [13, 8.5, 17], [0, 1, 0]], [7, [11, 7.2, 14], [0, 1, 0]], [20, [-12, 7, 13], [0, 1, 0]],
  [32, [0, 14, 9], [0, 0.6, 0]], [44, [0, 19, 0.01], [0, 0, 0]], [55, [0, 17, 0.01], [0, 0, 0]],
  [58, [7.5, 7.5, 9.5], [0, 0, 0]], [70, [5.5, 9.5, 8.5], [0, 0, 0]], [73, [0, 17.5, 5.5], [0, 0, 0.3]],
  [86, [0, 17, 5], [0, 0, 0.3]], [88, [0, 14.5, 7], [0, 0, 0]], [96, [0, 14, 6.5], [0, 0, 0]],
  [99, [14, 9.5, 15], [0, 1.2, 0]], [108, [9, 13, 10.5], [0, 1.2, 0]], [111, [0, 27, 0.01], [0, 0, 0]],
  [119, [0, 26, 0.01], [0, 0, 0]], [121, [0, 15.5, 0.01], [0, 0, 0]], [137, [0, 15, 0.01], [0, 0, 0]],
  [160, [0, 15, 0.01], [0, 0, 0]],
];
const vA = new THREE.Vector3(), vB = new THREE.Vector3();
function cameraAt(t) {
  let k = 0;
  while (k < KEYS.length - 2 && t >= KEYS[k + 1][0]) k++;
  const [t0, p0, q0] = KEYS[k], [t1, p1, q1] = KEYS[k + 1];
  const u = smooth(seg(t, t0, t1));
  camera.position.set(lerp(p0[0], p1[0], u), lerp(p0[1], p1[1], u), lerp(p0[2], p1[2], u));
  vA.set(lerp(q0[0], q1[0], u), lerp(q0[1], q1[1], u), lerp(q0[2], q1[2], u));
  camera.lookAt(vA);
}

// ---------- the frame ----------
function frameAt(t) {
  cameraAt(t);
  dust.rotation.y = t * 0.01;

  // the emulsion, exposure, development and grain
  const aFilm = bell(t, 4.5, S.grain[1], 1.8);       // the slab arrives as the title leaves
  film.visible = aFilm > 0.001;
  if (film.visible) {
    const uDev = smooth(seg(t, S.develop[0] + 1, S.develop[0] + 7));
    const uFix = smooth(seg(t, S.develop[0] + 5, S.develop[1] - 1));
    gelMat.opacity = 0.1 * aFilm * (1 - 0.7 * uFix);
    edgeMat.opacity = 0.35 * aFilm * (1 - uFix);
    baseMat.opacity = 0.85 * aFilm * (1 - uFix);
    tableMat.opacity = aFilm * smooth(seg(t, S.develop[0] + 4, S.develop[1]));
    crystalMat.opacity = aFilm;
    const fp = flashGeo.attributes.color;
    crystals.forEach((c, i) => {
      let s = 1;
      if (c.exposed) col.copy(HALIDE).lerp(SILVER, uDev);
      else { col.copy(HALIDE); s = 1 - smooth(clamp(uFix * 1.6 - c.fix * 0.6)); }
      crystalMesh.setColorAt(i, col);
      dummy.position.set(c.x, c.y, c.z);
      dummy.rotation.set(c.rx + t * 0.1, c.ry, 0);
      dummy.scale.setScalar(Math.max(s, 0.0001) * (c.exposed ? 1 + 0.25 * uDev : 1));
      dummy.updateMatrix();
      crystalMesh.setMatrixAt(i, dummy.matrix);
      const f = c.exposed ? Math.exp(-Math.max(0, t - c.hit) * 2.2) * (t >= c.hit ? 1 : 0) : 0;
      fp.setXYZ(i, f * 2.2, f * 1.9, f * 1.2);
    });
    crystalMesh.instanceMatrix.needsUpdate = true;
    crystalMesh.instanceColor.needsUpdate = true;
    fp.needsUpdate = true;
    const pp = photonGeo.attributes.position, pc = photonGeo.attributes.color;
    const aPh = bell(t, S.expose[0], S.expose[1], 1);
    photons.forEach((p, i) => {
      const fall = 14 * (t - (p.t - 0.7)), top = 9.5 - fall;
      const visible = aPh > 0 && top > p.stop && top < 9.5;
      const y0 = visible ? top : -50, y1 = visible ? Math.max(top + 0.9, p.stop) : -50;
      pp.setXYZ(2 * i, p.x, Math.max(y0, p.stop), p.z);
      pp.setXYZ(2 * i + 1, p.x, y1, p.z);
      const b = visible ? aPh : 0;
      pc.setXYZ(2 * i, b * 1.0, b * 0.9, b * 0.6);
      pc.setXYZ(2 * i + 1, 0, 0, 0);
    });
    pp.needsUpdate = true; pc.needsUpdate = true;
    markMat.opacity = 0.9 * bell(t, S.grain[0] + 3, S.grain[1] - 0.5, 1);
  }

  // the quantum tile: qubits, rotations, measurement, and Atlas's shots
  const aTile = Math.max(bell(t, S.tile[0], S.tile[1], 1.2), bell(t, S.shots[0], S.shots[1], 1));
  tile.visible = aTile > 0.001;
  if (tile.visible) {
    qubitMat.opacity = aTile;
    lineMat.opacity = 0.5 * aTile * (1 - smooth(seg(t, S.tile[1] - 3, S.tile[1] - 1)));
    const uRot = seg(t, S.tile[0] + 8, S.tile[1] - 3.5);
    const occ = occupation(uRot);
    const measured = t >= S.tile[1] - 2.5;
    let shot = -1;
    if (t >= S.shots[0]) {
      const u = seg(t, S.shots[0] + 1, S.shots[1] - 1);
      shot = Math.min(masks.length - 1, Math.floor(u * u * 380));
    } else if (measured) shot = 0;
    const sites = shot >= 0 ? new Set(sitesOf(masks[(shot * 61) % masks.length])) : null;
    halos.forEach((h, s) => {
      const o = sites ? 0 : occ[s];
      h.material.opacity = aTile * clamp(o * 0.9);
      h.scale.setScalar(0.55 + 1.35 * o);
    });
    tileCrystals.forEach((m, s) => {
      const on = sites && sites.has(s);
      m.visible = !!on;
      m.rotation.y = t * 0.8;
      m.scale.setScalar(on ? 1 : 0.001);
    });
    tileCrystalMat.opacity = aTile;
    pulses.forEach((p, i) => {
      const active = uRot > 0 && uRot < 1;
      const phase = (t * 1.6 + i / pulses.length) % 1, a = Math.floor(((t * 3.1 + i * 5) % 15));
      const q0 = sitePos(a), q1 = sitePos(a + 1);
      p.position.copy(q0).lerp(q1, phase).setY(0.1);
      p.material.opacity = active ? aTile * 0.55 : 0;
    });
    shotIndex = shot;
  }

  // the exclusion hole, crystal by crystal
  const aHole = bell(t, S.hole[0], S.hole[1], 1.2);
  hole.visible = aHole > 0.001;
  if (hole.visible) {
    cellMat.opacity = aHole;
    const steps = holeSeq.N, u = seg(t, S.hole[0] + 2, S.hole[1] - 2.5) * steps;
    const k = Math.min(steps, Math.floor(u)), frac = smooth(u - k);
    const m0 = holeSeq.maps[k], m1 = holeSeq.maps[Math.min(steps, k + 1)];
    const norm = 256;                            // the density over its average: 1 is an average site
    const c2 = new THREE.Color();
    for (let y = 0; y < 256; y++) {
      heat(m0[y] * norm, col);
      heat(m1[y] * norm, c2);
      cells.setColorAt(y, col.lerp(c2, frac).multiplyScalar(0.78));
    }
    cells.instanceColor.needsUpdate = true;
    for (let j = 0; j < 25; j++) {
      const s = holeSeq.order[j], on = j < k || (j === k && frac > 0.5);
      dummy.position.set(((s % 16) - 7.5) * HSITE, 0.3, (Math.floor(s / 16) - 7.5) * HSITE);
      dummy.rotation.set(0, t * 0.8 + j, 0);
      dummy.scale.setScalar(on ? 1 : 0.0001);
      dummy.updateMatrix();
      holeCrystals.setMatrixAt(j, dummy.matrix);
    }
    holeCrystals.instanceMatrix.needsUpdate = true;
    holeStep = Math.min(k, steps);
  }

  // the stack of Atlas shots, and the developed print
  const aStack = bell(t, S.stack[0], S.print[0] + 3, 1);
  stack.visible = aStack > 0.001;
  if (stack.visible) {
    stackMat.opacity = aStack;
    stackItems.forEach((c, i) => {
      const drop = seg(t, S.stack[0] + 1 + c.l * 0.3, S.stack[0] + 1.6 + c.l * 0.3);
      dummy.position.set(c.x, c.l * ST.dy + (1 - smooth(drop)) * 4, c.z);
      dummy.rotation.set(0, 0, 0);
      dummy.scale.setScalar(drop > 0 ? 1 : 0.0001);
      dummy.updateMatrix();
      stackMesh.setMatrixAt(i, dummy.matrix);
    });
    stackMesh.instanceMatrix.needsUpdate = true;
  }
  printMat.opacity = bell(t, S.print[0] + 1, S.print[1], 1.2);
  printPlane.visible = printMat.opacity > 0.001;

  // the comparison
  const aCmp = bell(t, S.compare[0], S.compare[0] + 9.6, 1.2);
  compare.visible = aCmp > 0.001;
  fieldRandom.material.opacity = aCmp;
  fieldPauli.material.opacity = aCmp;

  drawHud(t);
  hudTex.needsUpdate = true;
  renderer.autoClear = true;
  composer.render();
  renderer.autoClear = false;
  renderer.clearDepth();
  renderer.render(hudScene, hudCam);
}
let shotIndex = -1, holeStep = 0;

// ---------- the HUD ----------
const SANS = '"Segoe UI", "Helvetica Neue", Arial, sans-serif';
const MONO = '"Cascadia Mono", Consolas, "SFMono-Regular", Menlo, monospace';
function wrap(text, maxW) {
  const words = text.split(" "), lines = [];
  let line = "";
  for (const w of words) {
    const test = line ? `${line} ${w}` : w;
    if (g.measureText(test).width > maxW && line) { lines.push(line); line = w; } else line = test;
  }
  if (line) lines.push(line);
  return lines;
}
function caption(t) {
  for (const [a, b, text] of CAPTIONS) {
    const al = bell(t, a, b, 0.7);
    if (al <= 0) continue;
    g.font = `400 40px ${SANS}`;
    const lines = wrap(text, 1500);
    const h = lines.length * 54 + 36, y0 = H - 70 - h;
    g.globalAlpha = al * 0.62;
    g.fillStyle = "#000";
    g.fillRect(W / 2 - 800, y0, 1600, h);
    g.globalAlpha = al;
    g.fillStyle = "#f2efe8";
    g.textAlign = "center";
    g.textBaseline = "top";
    lines.forEach((l, i) => g.fillText(l, W / 2, y0 + 18 + i * 54));
  }
  g.globalAlpha = 1;
}
function title(t) {
  const al = bell(t, S.title[0], S.title[1], 1.3);
  if (al <= 0) return;
  g.globalAlpha = al;
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.fillStyle = "#f2efe8";
  g.font = `200 118px ${SANS}`;
  g.save();
  g.letterSpacing = "34px";
  g.fillText("QUANTUM FILM", W / 2 + 17, H / 2 - 50);
  g.restore();
  g.font = `400 36px ${SANS}`;
  g.fillStyle = "#f0b454";
  g.fillText("Film grain laid by a quantum computer, and fixed bit for bit", W / 2, H / 2 + 60);
  g.font = `400 26px ${SANS}`;
  g.fillStyle = "#9a978f";
  g.fillText("Moth Hack 2026", W / 2, H / 2 + 120);
  g.globalAlpha = 1;
}
function labels(t) {
  const aT = bell(t, S.tile[0] + 1, S.tile[1], 1);
  const aS = bell(t, S.shots[0], S.shots[1], 1);
  g.textAlign = "left";
  g.textBaseline = "top";
  if (aT > 0) {
    g.globalAlpha = aT;
    g.font = `500 30px ${SANS}`;
    g.fillStyle = "#6fd3ff";
    g.fillText("16 qubits · 5 fermions · pauli-4x4", 90, 80);
    g.globalAlpha = 1;
  }
  if (aS > 0 && shotIndex >= 0) {
    const i = (shotIndex * 61) % masks.length;
    let j = 0, acc = shotsData.per_job[0];
    while (i >= acc && j < shotsData.per_job.length - 1) { j++; acc += shotsData.per_job[j]; }
    g.globalAlpha = aS;
    g.font = `500 30px ${SANS}`;
    g.fillStyle = "#f0b454";
    g.fillText("Moth Atlas · tomography-api-v2", 90, 80);
    g.font = `400 28px ${MONO}`;
    g.fillStyle = "#e9e6df";
    g.fillText(`shot ${(i + 1).toLocaleString("en-US")} of ${masks.length.toLocaleString("en-US")}`, 90, 126);
    g.fillText(`job ${shotsData.jobs[j].slice(0, 8)}`, 90, 166);
    g.globalAlpha = 1;
  }
  const aH = bell(t, S.hole[0] + 1, S.hole[1], 1);
  if (aH > 0) {
    g.globalAlpha = aH;
    g.font = `500 30px ${SANS}`;
    g.fillStyle = "#6fd3ff";
    g.fillText("The chance of the next crystal, site by site", 90, 80);
    g.font = `400 28px ${MONO}`;
    g.fillStyle = "#e9e6df";
    g.fillText(`${holeStep} of ${holeSeq.N} crystals placed · 16 x 16 tile`, 90, 126);
    const x0 = 90, y0 = 186;
    const grd = g.createLinearGradient(x0, 0, x0 + 300, 0);
    for (let i = 0; i <= 10; i++) { heat(i / 5, col); grd.addColorStop(i / 10, `#${col.getHexString()}`); }
    g.fillStyle = grd;
    g.fillRect(x0, y0, 300, 18);
    g.font = `400 22px ${SANS}`;
    g.fillStyle = "#9a978f";
    g.fillText("none", x0, y0 + 26);
    g.textAlign = "right";
    g.fillText("twice the average", x0 + 300, y0 + 26);
    g.globalAlpha = 1;
  }
  const aC = bell(t, S.compare[0] + 0.5, S.compare[0] + 9.6, 1);
  if (aC > 0) {
    g.globalAlpha = aC;
    g.textAlign = "center";
    g.font = `500 32px ${SANS}`;
    g.fillStyle = "#f07a5a";
    g.fillText("Random placement: classical", W / 2 - 470, 48);
    g.fillStyle = "#6fd3ff";
    g.fillText("Pauli: quantum", W / 2 + 470, 48);
    g.font = `400 23px ${SANS}`;
    g.fillStyle = "#9a978f";
    g.fillText("400 crystals on 64 x 64 sites, 25 in every 16 x 16 tile, from the project's golden rolls", W / 2, 96);
    g.globalAlpha = 1;
  }
  const aP = bell(t, S.compare[0] + 9.2, S.compare[1], 1);
  if (aP > 0) plot(aP, smooth(seg(t, S.compare[0] + 9.6, S.compare[0] + 14.5)));
}
function plot(alpha, reveal) {
  const x0 = 380, y0 = 170, w = 1160, h = 560;
  g.globalAlpha = alpha * 0.8;
  g.fillStyle = "#07080c";
  g.fillRect(x0 - 110, y0 - 90, w + 180, h + 170);
  g.globalAlpha = alpha;
  const lx = (k) => x0 + ((Math.log10(k) + 2.45) / 2.15) * w;            // cycles per column, 10^-2.45 .. 10^-0.3
  const ly = (v) => y0 + h - ((Math.log10(Math.max(v, 0.003)) + 2.5) / 2.75) * h;   // 10^-2.5 .. 10^0.25
  // the band where the law, not the tiling, speaks: from the tile's scale to the Fermi scale
  g.fillStyle = "rgba(111, 211, 255, 0.07)";
  g.fillRect(lx(1 / 16), y0, lx(45 / 256) - lx(1 / 16), h);   // k_F = 16 sqrt(8) = 45.25 on this sheet
  g.fillStyle = "#6fd3ff";
  g.font = `400 22px ${SANS}`;
  g.textAlign = "center";
  g.textBaseline = "top";
  g.fillText("between the tile and the Fermi scale", (lx(1 / 16) + lx(45 / 256)) / 2, y0 + 10);
  g.strokeStyle = "#3a3f4a";
  g.lineWidth = 1;
  for (const v of [1, 0.1, 0.01]) { g.beginPath(); g.moveTo(x0, ly(v)); g.lineTo(x0 + w, ly(v)); g.stroke(); }
  g.fillStyle = "#9a978f";
  g.textAlign = "right";
  g.textBaseline = "middle";
  for (const [v, lab] of [[1, "1"], [0.1, "0.1"], [0.01, "0.01"]]) g.fillText(lab, x0 - 14, ly(v));
  g.textAlign = "center";
  g.textBaseline = "top";
  g.fillText("spatial frequency: cycles per crystal column (log scale)", x0 + w / 2, y0 + h + 16);
  g.save();
  g.translate(x0 - 80, y0 + h / 2);
  g.rotate(-Math.PI / 2);
  g.fillText("noise power of the crystal count, S(k)", 0, 0);
  g.restore();
  const series = [["trix", "#b8b3a8", "film: TRI-X as atlas-film coats it"],
                  ["poisson", "#f07a5a", "random placement, same count per tile"], ["pauli", "#6fd3ff", "Pauli: quantum"]];
  for (const [name, colour] of series) {
    const d = structData[name], n = Math.max(2, Math.floor(d.S.length * reveal));
    g.strokeStyle = colour;
    g.lineWidth = 4;
    g.beginPath();
    for (let i = 0; i < n; i++) {
      const X = lx((i + 1) / d.side), Y = ly(d.S[i]);
      if (i === 0) g.moveTo(X, Y); else g.lineTo(X, Y);
    }
    g.stroke();
  }
  g.textAlign = "left";
  g.textBaseline = "middle";
  g.font = `400 24px ${SANS}`;
  series.forEach(([, colour, lab], i) => {
    const y = y0 + h - 150 + i * 40, lx0 = x0 + w - 520;
    g.strokeStyle = colour;
    g.lineWidth = 4;
    g.beginPath(); g.moveTo(lx0, y); g.lineTo(lx0 + 50, y); g.stroke();
    g.fillStyle = "#e9e6df";
    g.fillText(lab, lx0 + 65, y);
  });
  g.globalAlpha = 1;
}
function recordCard(t) {
  const al = bell(t, S.record[0], S.record[1], 1);
  if (al <= 0) return;
  const d = structData["atlas-pauli-4x4"];
  const lines = [
    "{",
    '  "format": "quantum-film/print/v1",',
    '  "name": "atlas-pauli-4x4",',
    `  "rolls": { "kind": "device", "jobs": ${shotsData.jobs.length}, "shots": ${shotsData.shots} },`,
    `  "layers": ${d.layers},  "pitch_um": ${d.pitch_um},`,
    '  "paper": "silver, ungrained",',
    `  "digests": { "print": "${d.print.slice(0, 24)}…" }`,
    "}",
  ];
  g.globalAlpha = al * 0.85;
  g.fillStyle = "#0c0e13";
  g.fillRect(200, 150, 1000, 470);
  g.strokeStyle = "#f0b454";
  g.lineWidth = 2;
  g.strokeRect(200, 150, 1000, 470);
  g.globalAlpha = al;
  g.font = `400 27px ${MONO}`;
  g.fillStyle = "#e9e6df";
  g.textAlign = "left";
  g.textBaseline = "top";
  const shown = Math.floor(lines.length * smooth(seg(t, S.record[0] + 0.5, S.record[0] + 3)));
  lines.slice(0, shown).forEach((l, i) => g.fillText(l, 235, 185 + i * 50));
  const u = seg(t, S.record[0] + 3.5, S.record[0] + 7);
  const want = d.print.slice(0, 16);
  const hex = "0123456789abcdef";
  const scramble = (k) => [...want].map((c, i) => (i < Math.floor(u * 16) ? c : hex[(k * 7 + i * 13 + Math.floor(t * 30)) % 16])).join("");
  for (const [i, lab] of [[0, "developed"], [1, "re-developed from the record"]]) {
    const x = 1260, y = 190 + i * 210;
    g.globalAlpha = al * 0.85;
    g.fillStyle = "#0c0e13";
    g.fillRect(x, y, 470, 170);
    g.strokeStyle = "#3d8fb8";
    g.strokeRect(x, y, 470, 170);
    g.globalAlpha = al;
    g.fillStyle = "#9a978f";
    g.font = `400 24px ${SANS}`;
    g.fillText(lab, x + 24, y + 22);
    g.fillStyle = u >= 1 ? "#6fd3ff" : "#e9e6df";
    g.font = `500 34px ${MONO}`;
    g.fillText(i === 0 ? want : scramble(i), x + 24, y + 80);
  }
  if (u >= 1) {
    g.fillStyle = "#6fd3ff";
    g.font = `500 30px ${SANS}`;
    g.fillText("the same bits", 1260 + 24, 190 + 2 * 210 - 6);
  }
  g.globalAlpha = 1;
}
function credits(t) {
  const al = bell(t, S.credits[0], S.credits[1] + 1, 1.2);
  if (al <= 0) return;
  g.globalAlpha = al;
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.fillStyle = "#f2efe8";
  g.save();
  g.font = `200 84px ${SANS}`;
  g.letterSpacing = "24px";
  g.fillText("QUANTUM FILM", W / 2 + 12, H / 2 - 190);
  g.restore();
  const rows = [
    ["#f0b454", "Crystals laid on Moth's Atlas · tomography-api-v2 · six jobs, 24,576 shots"],
    ["#e9e6df", "Developed with atlas-film · pinned arithmetic from cft-fp256"],
    ["#e9e6df", "An exact 256-bit model of the law checks every run"],
    ["#9a978f", "Made by Logan W. with AI collaborators: Claude, by Anthropic, and the agents it directed"],
    ["#9a978f", "github.com/loganw234/Quantum-Film · MIT"],
  ];
  g.font = `400 34px ${SANS}`;
  rows.forEach(([c, s], i) => { g.fillStyle = c; g.fillText(s, W / 2, H / 2 - 40 + i * 64); });
  g.globalAlpha = 1;
}
function drawHud(t) {
  g.clearRect(0, 0, W, H);
  title(t);
  labels(t);
  recordCard(t);
  credits(t);
  caption(t);
}

// ---------- playback ----------
const ui = {
  play: document.getElementById("play"), restart: document.getElementById("restart"),
  scrub: document.getElementById("scrub"), clock: document.getElementById("clock"),
  full: document.getElementById("full"), record: document.getElementById("record"),
  note: document.getElementById("record-note"), stage: document.getElementById("stage"),
};
let t = Number(new URLSearchParams(location.search).get("t")) || 0;
let playing = false, last = null, recorder = null;
const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
function setPlaying(p) { playing = p; ui.play.textContent = p ? "Pause" : "Play"; }
let drawn = -1, onScreen = true;
new IntersectionObserver((es) => { onScreen = es[0].isIntersecting; }).observe(ui.stage);
function tick(now) {
  if (playing) {
    if (last !== null) t = Math.min(END, t + (now - last) / 1000);
    last = now;
    if (t >= END) { setPlaying(false); if (recorder) recorder.stop(); }
  } else last = null;
  if ((playing || t !== drawn) && (onScreen || recorder)) {   // a still frame is drawn once, not sixty times a second
    frameAt(t);
    drawn = t;
    ui.scrub.value = String(Math.round((t / END) * 1000));
    ui.clock.textContent = `${fmt(t)} / ${fmt(END)}`;
  }
  requestAnimationFrame(tick);
}
ui.play.onclick = () => { if (t >= END) t = 0; setPlaying(!playing); };
ui.restart.onclick = () => { t = 0; setPlaying(true); };
ui.scrub.oninput = () => { t = (Number(ui.scrub.value) / 1000) * END; };
ui.full.onclick = () => ui.stage.requestFullscreen?.();
ui.record.onclick = () => {
  if (recorder) return;
  const type = ["video/mp4;codecs=avc1", "video/webm;codecs=vp9", "video/webm"].find((m) => MediaRecorder.isTypeSupported(m));
  if (!type) { ui.note.textContent = "This browser cannot record a canvas; use a screen recorder instead."; return; }
  const chunks = [];
  recorder = new MediaRecorder(canvas.captureStream(60), { mimeType: type, videoBitsPerSecond: 16e6 });
  recorder.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
  recorder.onstop = () => {
    const blob = new Blob(chunks, { type: type.split(";")[0] });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `quantum-film.${type.includes("mp4") ? "mp4" : "webm"}`;
    a.click();
    ui.note.textContent = `Saved ${a.download} (${(blob.size / 1e6).toFixed(1)} MB).`;
    ui.record.textContent = "Record video";
    recorder = null;
  };
  t = 0;
  recorder.start(1000);
  ui.record.textContent = "Recording…";
  ui.note.textContent = `Recording the canvas as ${type.split(";")[0]}; it saves itself when the story ends.`;
  setPlaying(true);
};
document.addEventListener("keydown", (e) => {
  if (e.target.closest("input, button, textarea")) return;
  if (e.code === "Space") { e.preventDefault(); ui.play.onclick(); }
  if (e.key === "r" || e.key === "R") ui.restart.onclick();
});
msg.style.display = "none";
if (new URLSearchParams(location.search).has("play")) setTimeout(() => setPlaying(true), 1500);
requestAnimationFrame(tick);

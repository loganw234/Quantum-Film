// The page's two toys: an A|B slider over classical and quantum pictures, and a tile you can roll crystal by crystal.
import { newTile, place, placeAt, density, decodeMasks, sitesOf } from "./law.js";

const get = (p) => fetch(p).then((r) => { if (!r.ok) throw new Error(`${p}: HTTP ${r.status}`); return r.json(); });
const [fields, shots] = await Promise.all([get("data/fields.json"), get("data/atlas-shots.json")]);
const masks = decodeMasks(shots.masks_u16le_base64);
const image = (src) => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = src; });

// ---------- A|B ----------
const ab = document.getElementById("ab"), left = document.getElementById("ab-left"), right = document.getElementById("ab-right");
const bar = document.getElementById("ab-bar"), capEl = document.getElementById("ab-caption");
const labL = document.getElementById("ab-label-left"), labR = document.getElementById("ab-label-right");
const PAIRS = {
  crystals: {
    left: "Random placement (classical)", right: "Pauli (quantum)",
    caption: "Both: 25 crystals in every 16 x 16 tile of sites, 1,600 on 128 x 128, from the project's golden rolls. " +
             "Placed at random they clump and leave gaps; laid by the Pauli law, fermions keep their distance.",
    draw: (cv, which) => drawField(cv, fields[which === "left" ? "poisson" : "pauli"], which === "left" ? "#f07a5a" : "#6fd3ff"),
  },
  prints: {
    left: "TRI-X, as atlas-film coats it", right: "Pauli, 91 layers of quantum-laid tiles",
    caption: "The same scene, the same density, both developed and printed through atlas-film's pinned mode. Each " +
             "pixel is one column of crystals, 1.24 um across. The difference lives in the grain's structure at " +
             "scales between the tile and the Fermi length: the Pauli sheet carries 0.28-0.64 of film's noise " +
             "power there, 0.47 on average, against 0.89 for random placement.",
    draw: (cv, which) => drawImage(cv, which === "left" ? "img/trix-print.png" : "img/pauli-print.png"),
  },
  atlas: {
    left: "Pauli 4x4, from the exact law", right: "Pauli 4x4, every crystal laid by Atlas",
    caption: "Right: 24,389 shots measured on Moth's Atlas (tomography-api-v2), stacked 29 deep. Left: the same law " +
             "from its exact sampler. The two share their grain statistics (docs/prints/ in the repository).",
    draw: (cv, which) => drawImage(cv, which === "left" ? "img/golden-pauli-4x4-print.png" : "img/atlas-pauli-4x4-print.png"),
  },
};
function drawField(cv, sites, colour) {
  cv.width = cv.height = 768;
  const x = cv.getContext("2d"), side = fields.side, cell = 768 / side;
  x.fillStyle = "#050608";
  x.fillRect(0, 0, 768, 768);
  x.fillStyle = colour;
  for (const s of sites) {
    x.beginPath();
    x.arc(((s % side) + 0.5) * cell, (Math.floor(s / side) + 0.5) * cell, cell * 0.42, 0, Math.PI * 2);
    x.fill();
  }
}
async function drawImage(cv, src) {
  const img = await image(src);
  cv.width = img.naturalWidth;
  cv.height = img.naturalHeight;
  const x = cv.getContext("2d");
  x.imageSmoothingEnabled = false;
  x.drawImage(img, 0, 0);
}
let split = 50;
function setSplit(p) {
  split = Math.min(100, Math.max(0, p));
  right.style.clipPath = `inset(0 0 0 ${split}%)`;
  bar.style.left = `${split}%`;
}
async function showPair(name) {
  const p = PAIRS[name];
  labL.textContent = p.left;
  labR.textContent = p.right;
  capEl.textContent = p.caption;
  await Promise.all([p.draw(left, "left"), p.draw(right, "right")]);
  for (const b of document.querySelectorAll("#ab-tabs button")) b.setAttribute("aria-selected", String(b.dataset.pair === name));
}
function onDrag(e) {
  const r = ab.getBoundingClientRect();
  setSplit(((e.clientX - r.left) / r.width) * 100);
}
ab.addEventListener("pointerdown", (e) => { ab.setPointerCapture(e.pointerId); onDrag(e); });
ab.addEventListener("pointermove", (e) => { if (e.buttons) onDrag(e); });
for (const b of document.querySelectorAll("#ab-tabs button")) b.onclick = () => showPair(b.dataset.pair);
setSplit(50);
showPair("crystals");

// ---------- roll a tile ----------
const tileCv = document.getElementById("tile"), tx = tileCv.getContext("2d");
const status = document.getElementById("tile-status"), help = document.getElementById("tile-help");
const HELP = {
  pauli: "A 16 x 16 tile under the Pauli law: 25 fermions filling a Fermi disc. Colour is the chance that the next " +
         "crystal lands on each site, against the average. Place a crystal (or click a site) and watch a hole open " +
         "around it: fermions keep their distance.",
  random: "The same tile and count, placed at random. Every free site is equally likely, whatever is already there: " +
          "no hole, so crystals clump by chance.",
  atlas: "A 4 x 4 tile, the one Moth's Atlas ran. New tile shows a real measured shot. Next crystal reveals its five " +
         "crystals one at a time, with the exact law's chances given the ones already revealed.",
};
let law = "pauli", st, seed = 1, shot = 0, atlasSites = [];
function reset() {
  if (law === "atlas") {
    st = newTile("pauli", 4, 1, seed);
    atlasSites = sitesOf(masks[(shot * 7919) % masks.length]);
  } else st = newTile(law, 16, 8, seed);
  draw();
}
function heat(v) {
  v = Math.min(1, Math.max(0, v / 2));
  const c = v < 0.5 ? [0.02 + 0.1 * v, 0.03 + 0.9 * v, 0.1 + 1.4 * v]
                    : [0.07 + 0.93 * (v - 0.5) * 2, 0.48 + 0.52 * (v - 0.5) * 2, 0.8 + 0.2 * (v - 0.5) * 2];
  return `rgb(${c.map((u) => Math.round(255 * Math.min(1, u))).join(",")})`;
}
function draw() {
  const L = st.L, cell = 640 / L, d = density(st);
  tx.fillStyle = "#050608";
  tx.fillRect(0, 0, 640, 640);
  for (let s = 0; s < st.M; s++) {
    tx.fillStyle = heat(d[s] * st.M);
    tx.fillRect((s % L) * cell + 1, Math.floor(s / L) * cell + 1, cell - 2, cell - 2);
  }
  tx.fillStyle = "#fff1d0";
  for (const s of st.order) {
    tx.beginPath();
    tx.arc(((s % L) + 0.5) * cell, (Math.floor(s / L) + 0.5) * cell, cell * 0.32, 0, Math.PI * 2);
    tx.fill();
  }
  let line = `${st.order.length} of ${st.N} crystals placed`;
  if (law === "atlas") {
    const i = (shot * 7919) % masks.length;
    let j = 0, acc = shots.per_job[0];
    while (i >= acc && j < shots.per_job.length - 1) { j++; acc += shots.per_job[j]; }
    line += ` · Atlas shot ${(i + 1).toLocaleString("en-US")} of ${masks.length.toLocaleString("en-US")}, job ${shots.jobs[j].slice(0, 8)}`;
  }
  status.textContent = line;
  help.textContent = HELP[law];
}
function next() {
  if (law === "atlas") {
    const k = st.order.length;
    if (k < atlasSites.length) placeAt(st, atlasSites[k]);
  } else place(st);
  draw();
}
document.getElementById("tile-next").onclick = next;
document.getElementById("tile-fill").onclick = () => { for (let i = 0; i < st.N; i++) next(); };
document.getElementById("tile-new").onclick = () => { seed += 1; shot += 1; reset(); };
tileCv.addEventListener("click", (e) => {
  if (law === "atlas") return next();
  const r = tileCv.getBoundingClientRect(), L = st.L;
  const c = Math.floor(((e.clientX - r.left) / r.width) * L), rr = Math.floor(((e.clientY - r.top) / r.height) * L);
  if (placeAt(st, rr * L + c) >= 0) draw();
});
for (const b of document.querySelectorAll("#tile-law button")) {
  b.onclick = () => {
    law = b.dataset.law;
    for (const o of document.querySelectorAll("#tile-law button")) o.setAttribute("aria-selected", String(o === b));
    reset();
  };
}
reset();

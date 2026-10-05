// The page's two toys: an A|B slider over classical and quantum pictures, and a tile you can roll crystal by crystal.
import { newTile, place, placeAt, density, decodeMasks, sitesOf } from "./law.js";

const get = (p) => fetch(p).then((r) => { if (!r.ok) throw new Error(`${p}: HTTP ${r.status}`); return r.json(); });
const [fields, shots, hw] = await Promise.all([get("data/fields.json"), get("data/atlas-shots.json"),
                                               get("data/hardware.json")]);
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
  ibm: {
    left: "Pauli 4x4, the exact law's own rolls", right: () => `Pauli 4x4, laid by ${device}`,
    caption: () => `Right: a day of ${device}'s law shots that kept five crystals, stacked 29 deep ` +
             `(${dayOf(device).sheet_layouts.toLocaleString("en-US")} layouts, ${dayOf(device).sheet_columns} ` +
             `columns across). Left: the exact law's own rolls at 256 columns. The eye cannot tell them apart; ` +
             `the forbidden shots below show what it misses.`,
    draw: (cv, which) => drawImage(cv, which === "left" ? "img/golden-pauli-4x4-sheet-print.png" : `img/${sheetOf(device)}-print.png`),
  },
  ibmtwin: {
    left: "Random placement (classical), five crystals a tile", right: () => `Pauli 4x4, laid by ${device}`,
    caption: () => `Left: five crystals placed at random in every 4 x 4 tile, 29 deep, at the same density. ` +
             `Right: ${device}'s day of shots. At this scale both look like film; what differs is which layouts ` +
             `occur: ${pct(hw.twin.forbidden_share)} of the random tiles are layouts the law forbids, against ` +
             `${pct(dayOf(device).forbidden_share)} of ${device}'s.`,
    draw: (cv, which) => drawImage(cv, which === "left" ? "img/twin-pauli-4x4-sheet-print.png" : `img/${sheetOf(device)}-print.png`),
  },
};
let device = "ibm_kingston";
const sheetOf = (d) => `ibm-${d.split("_")[1]}-sheet`;
const dayOf = (d) => hw.devices.find((x) => x.name === d).day;
const pct = (x, digits = 1) => `${(100 * x).toFixed(digits)}%`;
const text = (v) => (typeof v === "function" ? v() : v);
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
let pair = "crystals";
async function showPair(name) {
  const p = PAIRS[name];
  pair = name;
  labL.textContent = text(p.left);
  labR.textContent = text(p.right);
  capEl.textContent = text(p.caption);
  await Promise.all([p.draw(left, "left"), p.draw(right, "right")]);
  for (const b of document.querySelectorAll("#ab-tabs button")) b.setAttribute("aria-selected", String(b.dataset.pair === name));
}
const devSel = document.getElementById("ab-device");
devSel.onchange = () => { device = devSel.value; if (pair === "ibm" || pair === "ibmtwin") showPair(pair); };
function onDrag(e) {
  const r = ab.getBoundingClientRect();
  setSplit(((e.clientX - r.left) / r.width) * 100);
}
ab.addEventListener("pointerdown", (e) => { ab.setPointerCapture(e.pointerId); onDrag(e); });
ab.addEventListener("pointermove", (e) => { if (e.buttons) onDrag(e); });
for (const b of document.querySelectorAll("#ab-tabs button")) b.onclick = () => showPair(b.dataset.pair);
setSplit(50);
showPair("crystals");

// ---------- on IBM hardware ----------
{
  const devs = hw.devices, fx = (v, d = 3) => (v >= 0 ? "+" : "") + v.toFixed(d);
  const cols = [["The exact law", hw.law], ["Atlas (emulator)", hw.emulator],
                ...devs.map((d) => [d.name, d.first_set]), ["Random placement", hw.twin]];
  const rows = [
    ["Shots that kept five crystals", (c) => pct(c.five_crystal_share)],
    ["Of those, on layouts the law forbids", (c) => pct(c.forbidden_share)],
    ["Linear XEB (random 0, the law 1)", (c) => fx(c.xeb)],
    ["⟨X0X1⟩ (a mixture gives 0)", (c) => fx(c.X0X1)],
    ["⟨Y0Y1⟩", (c) => fx(c.Y0Y1)],
  ];
  const t = document.getElementById("hw-table");
  t.innerHTML = `<thead><tr><th></th>${cols.map(([n]) => `<th>${n}</th>`).join("")}</tr></thead><tbody>` +
    rows.map(([n, f]) => `<tr><th>${n}</th>${cols.map(([, c]) => `<td>${f(c)}</td>`).join("")}</tr>`).join("") + "</tbody>";
  const lo = Math.min(...devs.map((d) => d.first_set.forbidden_share)), hi = Math.max(...devs.map((d) => d.first_set.forbidden_share));
  document.getElementById("hw-caption").textContent =
    `Each device's pre-registered set: 24,576 law shots and 8,192 for the two coherences. All three carry the law's ` +
    `two quantum signatures, far from random placement: ${pct(lo)} to ${pct(hi)} of their five-crystal shots on ` +
    `forbidden layouts against ${pct(hw.twin.forbidden_share)}, and coherences near the law's +0.375 where a ` +
    `classical mixture gives 0. All three fall short of the noiseless emulator: that is the hardware's noise, measured. ` +
    `Every table: docs/HARDWARE-RESULTS.md in the repository.`;
  const strip = document.getElementById("hw-sheets");
  for (const d of devs) {
    const fig = document.createElement("figure");
    fig.innerHTML = `<img src="img/${sheetOf(d.name)}-print.png" alt="A print laid by ${d.name}" loading="lazy">` +
      `<figcaption><b>${d.name}</b><br>${d.day.law_runs} law runs, ${d.day.sheet_layouts.toLocaleString("en-US")} ` +
      `layouts, ${d.day.sheet_columns} columns</figcaption>`;
    fig.onclick = () => {
      device = devSel.value = d.name;
      showPair("ibm");
      document.getElementById("compare").scrollIntoView({ behavior: "smooth" });
    };
    strip.appendChild(fig);
  }
}

// ---------- the forbidden shots ----------
{
  const F = hw.forbidden, k = F["ibm-kingston-sheet"], tw = F["twin-pauli-4x4-sheet"];
  const ibm = ["ibm-kingston-sheet", "ibm-marrakesh-sheet", "ibm-fez-sheet"].map((n) => F[n]);
  const lo = Math.min(...ibm.map((s) => s.forbidden_share)), hi = Math.max(...ibm.map((s) => s.forbidden_share));
  const kept = hw.devices.map((d) => 1 - d.first_set.five_crystal_share);
  const [num, den] = k.forbidden_layouts_mean_nn_pairs.split("/").map(Number);
  document.getElementById("why-forbidden").textContent =
    `The five crystals of a tile are five fermions sharing its five longest standing waves. Quantum mechanics gives ` +
    `each layout a chance equal to a determinant: the five waves read at the five sites. For ` +
    `${hw.forbidden_layouts.toLocaleString("en-US")} of the ${hw.layouts.toLocaleString("en-US")} ways to place five ` +
    `crystals on sixteen sites, those readings are not independent, the determinant is exactly zero, and a perfect ` +
    `quantum computer never lays them. They are clumps: the law's layouts average ${k.law_mean_nn_pairs} ` +
    `neighbouring pairs, the forbidden ones ${(num / (den || 1)).toFixed(2)}, and every layout with more than ` +
    `${k.most_nn_pairs_the_law_allows} neighbouring pairs is forbidden. Fermions repel.`;
  document.getElementById("how-forbidden").textContent =
    `On a real machine every gate is a little off and every qubit slowly forgets. Many errors change the number of ` +
    `crystals (${pct(Math.min(...kept), 0)} to ${pct(Math.max(...kept), 0)} of the IBM shots did) and leave the ` +
    `five-crystal set. A forbidden shot needs an error that keeps the count: a rotation a little too far, a stray ` +
    `phase, or two errors that cancel. On the three IBM devices ${pct(lo)} to ${pct(hi)} of the five-crystal shots ` +
    `were forbidden. Placed at random, as a classical machine would, ${pct(tw.forbidden_share)} are.`;
  document.getElementById("tint-forbidden").textContent =
    `In a print each crystal column sums 29 layers, so a forbidden shot's five crystals blend into the grain: about ` +
    `a third of an IBM print's columns hold one, among about nine crystals each. The tint shows each column's share ` +
    `of forbidden crystals, at twice that share. The red is the hardware's error; how little of it there is, beside ` +
    `random placement, is the quantum effect.`;
  const cv = document.getElementById("fb-canvas"), cap = document.getElementById("fb-caption");
  const NAMES = { "golden-pauli-4x4-sheet": "the exact law's own rolls", "twin-pauli-4x4-sheet": "random placement",
                  "ibm-kingston-sheet": "ibm_kingston", "ibm-marrakesh-sheet": "ibm_marrakesh", "ibm-fez-sheet": "ibm_fez" };
  let sheet = "golden-pauli-4x4-sheet", view = "forbidden";
  async function show() {
    const s = F[sheet], img = await image(`img/${sheet}-${view}.png`), x = cv.getContext("2d");
    const scale = img.naturalWidth / s.side, crop = 64;           // the saved images are scaled by whole numbers
    cv.width = cv.height = view === "forbidden" ? img.naturalWidth : 768;
    x.imageSmoothingEnabled = false;                                // after the resize, which resets the context
    if (view === "forbidden") x.drawImage(img, 0, 0);
    else x.drawImage(img, 0, 0, crop * scale, crop * scale, 0, 0, 768, 768);   // one layer's corner, 64 x 64 cells
    cap.textContent = `${NAMES[sheet]}: ${s.forbidden_layouts.toLocaleString("en-US")} of ` +
      `${s.layouts.toLocaleString("en-US")} layouts forbidden (${pct(s.forbidden_share, 2)}). ` +
      (view === "forbidden"
        ? `${pct(s.share_of_cells)} of the print's columns hold at least one forbidden crystal.`
        : `One layer's top-left corner, 64 x 64 cells: each 4 x 4 tile is one shot, and forbidden shots are in colour.` +
          (s.mean_nn_pairs_forbidden_laid === null ? "" : ` Here they average ${s.mean_nn_pairs_forbidden_laid.toFixed(2)} ` +
           `neighbouring pairs, against ${s.mean_nn_pairs_allowed_laid.toFixed(2)} for the allowed shots.`));
  }
  for (const b of document.querySelectorAll("#fb-tabs button")) b.onclick = () => {
    sheet = b.dataset.sheet;
    for (const o of document.querySelectorAll("#fb-tabs button")) o.setAttribute("aria-selected", String(o === b));
    show();
  };
  for (const b of document.querySelectorAll("#fb-view button")) b.onclick = () => {
    view = b.dataset.view;
    for (const o of document.querySelectorAll("#fb-view button")) o.setAttribute("aria-selected", String(o === b));
    show();
  };
  show();
  const tiles = document.getElementById("fb-tiles");
  for (const t of hw.kingston_commonest_forbidden) {
    const c = document.createElement("canvas");
    c.width = c.height = 96;
    const g = c.getContext("2d");
    g.fillStyle = "#050608";
    g.fillRect(0, 0, 96, 96);
    for (let s = 0; s < 16; s++) {
      g.fillStyle = t.sites.includes(s) ? "#e6451f" : "#1a1d24";
      g.fillRect((s % 4) * 24 + 2, Math.floor(s / 4) * 24 + 2, 20, 20);
    }
    const fig = document.createElement("figure");
    fig.appendChild(c);
    fig.insertAdjacentHTML("beforeend", `<figcaption>${t.shots} shots<br>${t.nn_pairs} neighbouring pairs</figcaption>`);
    tiles.appendChild(fig);
  }
  document.getElementById("fb-tiles-caption").textContent =
    `${hw.kingston_forbidden_shots.toLocaleString("en-US")} of ibm_kingston's five-crystal shots landed on forbidden ` +
    `layouts. These are the eight it laid most often, each a tile of 4 x 4 sites. The tile wraps around at its ` +
    `edges, as the circuit's lattice does, so crystals on opposite edges are neighbours too. The first, a full row ` +
    `of four with one crystal tucked under it, is the tightest clump there is; the law gives it no chance at all.`;
}

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

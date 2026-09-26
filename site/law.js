// The Pauli law in the browser, for illustration only: ordinary float64, not the project's 256-bit authority.
// Free fermions fill the Fermi disc |k|^2 <= r2 (k in units of 2 pi / L) of a periodic L x L tile. Measuring every
// site lays a projection determinantal point process with kernel K(x, y) = (1/M) sum_k cos(k . (x - y)).

export function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function pauliKernel(L, r2) {
  const M = L * L;
  const modes = [];
  for (let a = -L / 2; a < L / 2; a++) for (let b = -L / 2; b < L / 2; b++) if (a * a + b * b <= r2) modes.push([a, b]);
  const N = modes.length;
  const K = new Float64Array(M * M);
  for (let x = 0; x < M; x++) {
    const xr = Math.floor(x / L), xc = x % L;
    for (let y = x; y < M; y++) {
      const dr = xr - Math.floor(y / L), dc = xc - (y % L);
      let s = 0;
      for (const [a, b] of modes) s += Math.cos((2 * Math.PI * (a * dr + b * dc)) / L);
      K[x * M + y] = K[y * M + x] = s / M;
    }
  }
  return { K, N, M, L };
}

// The chance of each site being the next crystal: the conditional kernel's diagonal, over the crystals left.
export function density(state) {
  const { M } = state;
  const d = new Float64Array(M);
  if (state.law === "pauli") {
    for (let y = 0; y < M; y++) d[y] = Math.max(0, state.K[y * M + y]);
  } else {
    for (let y = 0; y < M; y++) d[y] = state.taken[y] ? 0 : 1;
  }
  let tot = 0;
  for (let y = 0; y < M; y++) tot += d[y];
  if (tot > 0) for (let y = 0; y < M; y++) d[y] /= tot;
  return d;
}

export function newTile(law, L, r2, seed) {
  const k = pauliKernel(L, r2);
  return { law, L, M: k.M, N: k.N, K: Float64Array.from(k.K), taken: new Uint8Array(k.M), order: [],
           rng: mulberry32(seed) };
}

// One draw of the chain rule: pick a site by the current density, then condition the kernel on it.
export function place(state) {
  if (state.order.length >= state.N) return -1;
  const d = density(state);
  let u = state.rng(), x = 0;
  for (; x < state.M - 1; x++) { u -= d[x]; if (u <= 0 && d[x] > 0) break; }
  while (d[x] === 0 && x > 0) x--;
  return placeAt(state, x);
}

// Condition on a crystal at site x, chosen by the caller; refused (-1) where the law gives it no chance.
export function placeAt(state, x) {
  if (state.order.length >= state.N || state.taken[x]) return -1;
  if (state.law === "pauli" && state.K[x * state.M + x] <= 1e-12) return -1;
  state.order.push(x);
  state.taken[x] = 1;
  if (state.law === "pauli") {
    const { M, K } = state;
    const kxx = K[x * M + x];
    const col = new Float64Array(M);
    for (let y = 0; y < M; y++) col[y] = K[y * M + x];
    for (let a = 0; a < M; a++) {
      const ca = col[a] / kxx;
      if (ca === 0) continue;
      const row = a * M;
      for (let b = 0; b < M; b++) K[row + b] -= ca * col[b];
    }
  }
  return x;
}

export function decodeMasks(b64) {
  const bin = atob(b64);
  const out = new Uint16Array(bin.length / 2);
  for (let i = 0; i < out.length; i++) out[i] = bin.charCodeAt(2 * i) | (bin.charCodeAt(2 * i + 1) << 8);
  return out;
}

export function sitesOf(mask) {
  const s = [];
  for (let i = 0; i < 16; i++) if (mask & (1 << i)) s.push(i);
  return s;
}

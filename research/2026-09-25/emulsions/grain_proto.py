"""Three candidate emulsions on a periodic 64x64 lattice, at most one crystal a site.

  poisson  N sites uniformly without replacement: the classical reference.
           atlas-film lays its crystal field as a Poisson count; this is the
           fixed-count lattice twin of that.
  fermion  a projection determinantal point process: N free fermions filling
           the N lowest plane-wave modes of the lattice (a Fermi sea), sampled
           exactly by the spectral algorithm (Hough, Krishnapur, Peres, Virag).
           It is the distribution a qubit device samples when it prepares that
           Slater determinant and measures every site's occupation.
  speckle  Born-rule shots of a simulated 12-qubit circuit: a random circuit on
           the three low bits of each 6-qubit momentum register, sign-extended
           by CNOTs, then a QFT on each register (applied as its matrix, an
           orthonormal inverse FFT, not as a gate decomposition). The output is
           band-limited speckle whose intensity is Porter-Thomas, so the grain
           is a speckle-driven Cox process. Crystals are the first N distinct
           sites the shots hit.

Everything is seeded (numpy PCG64). Each layout's SHA-256 is printed so a run
on another machine, thread count or arithmetic can be compared bit for bit.
This is exploration, not the project's authority.
"""
import hashlib
import json
import pathlib
import sys
import time

import numpy as np

L = 64
M = L * L
N = 512                       # 12.5 % of sites
REPS = 6
OUT = pathlib.Path(__file__).with_name("proto")    # made by main(), not by an import


def digest(sites):
    return hashlib.sha256(np.sort(np.asarray(sites)).astype("<u2").tobytes()).hexdigest()[:16]


def field(sites, L=L):
    f = np.zeros(L * L, dtype=np.int64)
    f[np.asarray(sites)] = 1
    return f.reshape(L, L)


# ---------------------------------------------------------------- the stocks
def stock_poisson(rng):
    return rng.choice(M, N, replace=False)


def fermi_sea(L, N):
    ks = [(kx, ky) for kx in range(-L // 2, L // 2) for ky in range(-L // 2, L // 2)]
    ks.sort(key=lambda k: (k[0] ** 2 + k[1] ** 2, k[0], k[1]))   # ties broken by a fixed order
    return np.array(ks[:N])


def dpp_basis(L, N, dtype=np.complex128):
    """Plane waves e^{2 pi i (x kx + y ky)/L} / sqrt(M). The phase is reduced mod L
    as an INTEGER first, so the whole basis rests on L angles 2 pi m / L."""
    ks = fermi_sea(L, N)
    x = np.repeat(np.arange(L), L)
    y = np.tile(np.arange(L), L)
    m = (np.outer(x, ks[:, 0]) + np.outer(y, ks[:, 1])) % L
    table = np.exp(2j * np.pi * np.arange(L) / L)
    return (table[m] / np.sqrt(L * L)).astype(dtype)


def sample_projection_dpp(V, u, update="matmul"):
    """Chain-rule sampler for the projection kernel K = V V^H. At step j the site
    i is drawn with probability ||P_perp v_i||^2 / (N - j), v_i the i-th row,
    P_perp removing the span of the rows already drawn. O(M N^2)."""
    Mv, Nv = V.shape
    rdt = np.float32 if V.dtype == np.complex64 else np.float64
    c = (V.real ** 2 + V.imag ** 2).sum(axis=1).astype(rdt)
    E = np.zeros((Nv, Nv), dtype=V.dtype)
    picks = []
    for j in range(Nv):
        cs = np.cumsum(np.maximum(c, 0))
        i = int(np.searchsorted(cs, u[j] * float(cs[-1]), side="right"))
        i = min(i, Mv - 1)
        picks.append(i)
        v = V[i].copy()
        for _ in range(2):                                   # Gram-Schmidt, twice
            if j:
                v -= (E[:j].conj() @ v) @ E[:j]
        v /= np.linalg.norm(v)
        E[j] = v
        if update == "matmul":
            w = V @ v.conj()
        else:
            w = np.einsum("ik,k->i", V, v.conj())
        c = c - (w.real ** 2 + w.imag ** 2).astype(rdt)
        c[i] = 0
    return np.array(picks)


def haar_u2(rng):
    z = (rng.standard_normal((2, 2)) + 1j * rng.standard_normal((2, 2))) / np.sqrt(2)
    q, r = np.linalg.qr(z)
    return q * (np.diag(r) / np.abs(np.diag(r)))


def apply_1q(psi, U, q):
    return np.moveaxis(np.tensordot(U, psi, axes=([1], [q])), 0, q)


def apply_cz(psi, a, b):
    idx = [slice(None)] * psi.ndim
    idx[a] = 1
    idx[b] = 1
    psi[tuple(idx)] *= -1
    return psi


def apply_cx(psi, c, t):
    idx = [slice(None)] * psi.ndim
    idx[c] = 1
    sub = psi[tuple(idx)]
    tt = t - (1 if t > c else 0)
    psi[tuple(idx)] = np.flip(sub, axis=tt)
    return psi


def speckle_probs(rng, depth=10, band=True):
    """12 qubits; qubit 0 is the MSB of kx, qubit 6 the MSB of ky."""
    n = 12
    psi = np.zeros((2,) * n, dtype=np.complex128)
    psi[(0,) * n] = 1
    live = [3, 4, 5, 9, 10, 11] if band else list(range(n))
    for layer in range(depth):
        for q in live:
            psi = apply_1q(psi, haar_u2(rng), q)
        for a, b in zip(live[layer % 2::2], live[layer % 2 + 1::2]):
            psi = apply_cz(psi, a, b)
    if band:
        for c, ts in ((3, (2, 1, 0)), (9, (8, 7, 6))):       # sign-extend the 3-bit values
            for t in ts:
                psi = apply_cx(psi, c, t)
        amp = np.fft.ifft2(psi.reshape(L, L), norm="ortho")  # the QFT on each register
    else:
        amp = psi.reshape(L, L)
    p = (amp.real ** 2 + amp.imag ** 2).ravel()
    return p / p.sum()


def stock_speckle(rng, band=True):
    p = speckle_probs(rng, band=band)
    cdf = np.cumsum(p)
    seen, order, shots = set(), [], 0
    while len(order) < N:
        draws = np.searchsorted(cdf, rng.random(4096) * cdf[-1], side="right")
        for s in draws:
            shots += 1
            s = int(min(s, M - 1))
            if s not in seen:
                seen.add(s)
                order.append(s)
                if len(order) == N:
                    break
    return np.array(order), shots, float(M * np.sum(p ** 2))


# ------------------------------------------------------------- the statistics
def radial_bins(L):
    d = np.minimum(np.arange(L), L - np.arange(L))
    return np.sqrt(d[:, None] ** 2 + d[None, :] ** 2)


def pair_corr(f):
    F = np.fft.fft2(f)
    C = np.rint(np.real(np.fft.ifft2(F * np.conj(F))))
    n = f.sum()
    g = C * f.size / (n * (n - 1))
    g[0, 0] = 0.0                                              # one crystal a site
    r = radial_bins(f.shape[0])
    out = []
    for lo in np.arange(0.5, 12.5, 1.0):
        m = (r >= lo) & (r < lo + 1)
        out.append(float(g[m].mean()))
    return out


def structure_factor(f):
    n = f.sum()
    S = np.abs(np.fft.fft2(f - n / f.size)) ** 2 / n
    r = radial_bins(f.shape[0])
    out = []
    for lo in np.arange(0.5, 16.5, 1.0):
        m = (r >= lo) & (r < lo + 1)
        out.append(float(S[m].mean()))
    return out


def number_variance(f, sides=(1, 2, 3, 4, 6, 8, 12, 16)):
    out = []
    for a in sides:
        p = np.pad(f, ((0, a), (0, a)), mode="wrap")
        I = np.pad(p.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
        cnt = I[a:a + L, a:a + L] - I[:L, a:a + L] - I[a:a + L, :L] + I[:L, :L]
        out.append(float(cnt.var() / cnt.mean()))
    return out


def summarise(name, layouts):
    fs = [field(s) for s in layouts]
    g = np.mean([pair_corr(f) for f in fs], axis=0)
    S = np.mean([structure_factor(f) for f in fs], axis=0)
    nv = np.mean([number_variance(f) for f in fs], axis=0)
    return {"stock": name, "g_r": [round(x, 3) for x in g], "S_k": [round(x, 3) for x in S],
            "var_over_mean": [round(x, 3) for x in nv], "digests": [digest(s) for s in layouts]}


# ------------------------------------------------------------------- the run
def main():
    OUT.mkdir(exist_ok=True)
    t0 = time.time()
    rng = np.random.default_rng(np.random.SeedSequence(20260925))
    seeds = rng.integers(0, 2 ** 63, size=(4, REPS))
    results = {}

    lay = [stock_poisson(np.random.default_rng(int(s))) for s in seeds[0]]
    results["poisson"] = summarise("poisson", lay)
    keep = {"poisson": lay[0]}

    V = dpp_basis(L, N)
    lay = []
    for s in seeds[1]:
        u = np.random.default_rng(int(s)).random(N)
        lay.append(sample_projection_dpp(V, u))
    results["fermion"] = summarise("fermion", lay)
    keep["fermion"] = lay[0]

    lay, meta = [], []
    for s in seeds[2]:
        order, shots, coll = stock_speckle(np.random.default_rng(int(s)), band=True)
        lay.append(order)
        meta.append((shots, round(coll, 3)))
    results["speckle"] = summarise("speckle", lay)
    results["speckle"]["shots_and_M_sum_p2"] = meta
    keep["speckle"] = lay[0]

    lay, meta = [], []
    for s in seeds[3]:
        order, shots, coll = stock_speckle(np.random.default_rng(int(s)), band=False)
        lay.append(order)
        meta.append((shots, round(coll, 3)))
    results["speckle-white"] = summarise("speckle-white", lay)
    results["speckle-white"]["shots_and_M_sum_p2"] = meta

    results["_meta"] = {"L": L, "N": N, "reps": REPS, "numpy": np.__version__,
                        "seconds": round(time.time() - t0, 1)}
    (OUT / "stats.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    np.savez(OUT / "layouts.npz", **{k: np.asarray(v) for k, v in keep.items()})
    for k, v in results.items():
        if k.startswith("_"):
            continue
        print(f"== {k}")
        for key in ("g_r", "S_k", "var_over_mean", "digests", "shots_and_M_sum_p2"):
            if key in v:
                print(f"   {key:18} {v[key]}")
    print("meta", results["_meta"])


if __name__ == "__main__":
    main()

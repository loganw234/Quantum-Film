"""The Pauli law, exactly: a projection determinantal point process.

N fermions fill the Fermi disc of plane-wave modes on a periodic L x L tile of
crystal sites (the disc is quantum_film.stocks.fermi_disc). Measuring every
site's occupation lays a crystal layout Y of exactly N sites, with probability

    P(Y) = det(K_Y),   K(x, y) = (1/M) * sum over k in the disc of cos(2 pi k.(x - y) / L)

(the disc is symmetric under k -> -k, so K is real). K = Phi Phi^T for a real
orthonormal basis Phi of the disc: the constant mode, and a cos and a sin for
each pair {k, -k}.

Everything is computed with mpmath at PREC bits. Angles are reduced mod L as
integers before any trigonometry, so the whole basis rests on the L values
cos(2 pi m / L) and sin(2 pi m / L).

Sampling is the chain rule. At step j, site i is drawn with probability
c_i / (N - j), where c_i is the squared norm of row i of Phi after the rows
already drawn are projected out. The draw compares u * total with the
cumulative sums of c using the stream's exact uniforms. When u * total lands
within 2^-(PREC - 32) of a boundary, rounding could decide which crystal is
laid, so the draw is REFUSED by name (TieRefusal) rather than decided.
"""
from fractions import Fraction
from itertools import combinations

import mpmath
from mpmath import mp, mpf

from ..stocks import fermi_disc
from .uniform import uniform

PREC = 256


class TieRefusal(ValueError):
    """A draw's target landed within the refusal margin of a cumulative boundary."""


def _to_mpf(fr):
    return mpf(fr.numerator) / mpf(fr.denominator)


def orbitals(L, r2, prec=PREC):
    """Phi as M rows of N mpf values; site index = x * L + y."""
    ks = fermi_disc(L, r2)
    reps, seen = [], set()
    for k in ks:
        if k in seen:
            continue
        seen.update({k, (-k[0], -k[1])})
        reps.append(k)
    M = L * L
    with mp.workprec(prec):
        c = [mpmath.cos(2 * mpmath.pi * m / L) for m in range(L)]
        s = [mpmath.sin(2 * mpmath.pi * m / L) for m in range(L)]
        a0 = 1 / mpmath.sqrt(M)
        a = mpmath.sqrt(mpf(2) / M)
        cols = []
        for kx, ky in reps:
            if (kx, ky) == (0, 0):
                cols.append([+a0] * M)
                continue
            ms = [(kx * x + ky * y) % L for x in range(L) for y in range(L)]
            cols.append([a * c[m] for m in ms])
            cols.append([a * s[m] for m in ms])
    if len(cols) != len(ks):
        raise AssertionError(f"basis has {len(cols)} columns for {len(ks)} modes")
    return [[col[i] for col in cols] for i in range(M)]


def kernel(L, r2, prec=PREC):
    rows = orbitals(L, r2, prec)
    with mp.workprec(prec):
        return [[mpmath.fsum(a * b for a, b in zip(ri, rj, strict=True)) for rj in rows] for ri in rows]


def probability(rows, Y, prec=PREC):
    """det(K_Y) for a layout Y of exactly N sites."""
    with mp.workprec(prec):
        G = mpmath.matrix([[mpmath.fsum(a * b for a, b in zip(rows[i], rows[j], strict=True)) for j in Y] for i in Y])
        return mpmath.det(G)


def total_probability(L, r2, prec=96):
    """Sum of det(K_Y) over every N-subset: 1 for a projection DPP. Small tiles only."""
    rows = orbitals(L, r2, prec)
    N = len(rows[0])
    with mp.workprec(prec):
        return mpmath.fsum(probability(rows, Y, prec) for Y in combinations(range(len(rows)), N))


def sample(L, r2, stream_bytes, prec=PREC, uniform_fn=uniform):
    """One crystal layout: the sorted site indices of N crystals."""
    rows = orbitals(L, r2, prec)
    M, N = len(rows), len(rows[0])
    with mp.workprec(prec):
        margin = mpf(2) ** (-(prec - 32))
        c = [mpmath.fsum(v * v for v in r) for r in rows]
        taken = [False] * M
        basis, picks = [], []
        for j in range(N):
            total = mpmath.fsum(c[i] for i in range(M) if not taken[i])
            u = uniform_fn(stream_bytes, j)
            if not isinstance(u, Fraction) or not 0 <= u < 1:
                raise ValueError(f"draw {j}: uniform {u!r} is not an exact Fraction in [0, 1)")
            target = _to_mpf(u) * total
            acc, chosen = mpf(0), None
            for i in range(M):
                if taken[i]:
                    continue
                nxt = acc + (c[i] if c[i] > 0 else mpf(0))
                if abs(nxt - target) < margin:
                    raise TieRefusal(f"draw {j}: the target lies within 2^-{prec - 32} of the boundary "
                                     f"after site {i}; rounding would choose, so the authority refuses")
                if target < nxt:
                    chosen = i
                    break
                acc = nxt
            if chosen is None:
                raise TieRefusal(f"draw {j}: the target is not below the last cumulative sum")
            picks.append(chosen)
            taken[chosen] = True
            v = list(rows[chosen])
            for _ in range(2):                                    # Gram-Schmidt, twice
                for e in basis:
                    d = mpmath.fsum(a * b for a, b in zip(v, e, strict=True))
                    v = [a - d * b for a, b in zip(v, e, strict=True)]
            nv = mpmath.sqrt(mpmath.fsum(a * a for a in v))
            e = [a / nv for a in v]
            basis.append(e)
            for i in range(M):
                if not taken[i]:
                    d = mpmath.fsum(a * b for a, b in zip(rows[i], e, strict=True))
                    c[i] -= d * d
    return sorted(picks)

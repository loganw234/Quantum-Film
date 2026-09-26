"""The certificate: enclosures of the EXACT chain rule, at binary64, from directed rounding alone.

At draw j the exact weights are c_i = |phi_i|^2 - |P phi_i|^2, where phi_i is
row i of the exact orthonormal basis (golden.fermi.orbitals) and P projects
onto the span of the rows drawn so far. Enclosing P through an interval
Gram-Schmidt fails: each basis vector's enclosure widens the next, and on the
16x16 stock the widths grew 2.5-3x a draw, to 1e-4 by draw 24 (measured
2026-09-25). So nothing here is enclosed as a recurrence:

  - Q = A^T T EXACTLY, where A holds the k drawn rows and T is any binary64
    k x k matrix. Q's columns lie in the drawn rows' span whatever T is, and
    once Q^T Q is certified within F < 1 of I (below) they are k independent
    vectors, so they span it. So T can come from plain round-to-nearest
    Gram-Schmidt (quantum_film.pinned.sampler.Chain): it need only make Q
    nearly orthonormal, and an error in it costs tightness, never soundness.
    Each column of Q is enclosed directly from A's enclosure and T (`column`).
  - E = Q^T Q - I is bounded rigorously: |E|_2 <= |E|_F <= F (`gram_terms`,
    `gram_bound`, `gram_factors`). If F is not below 1 the draw is not certified.
  - |P phi|^2 = y^T (Q^T Q)^-1 y with y = Q^T phi, and the eigenvalues of
    (I + E)^-1 lie in [1/(1+F), 1/(1-F)], so |P phi|^2 lies in
    [|y|^2 / (1+F), |y|^2 / (1-F)]. |y|^2 gains one term <phi_i, q_k>^2 a
    draw (`inner`, `square`).
  - c_i lies in [n_lo - s_hi/(1-F), n_hi - s_lo/(1+F)] (`weights`).

Prefix sums of those bound every cumulative weight the authority compares,
their last entries bound its total, and u times the total, from u's own exact
bounds, bounds its target (`target`). `locate` certifies a draw only when the
target's enclosure clears every boundary it is compared with by TAU.

EVERY ROUNDING HERE GOES THROUGH quantum_film.pinned.bounds, which names the
two attributes once. What this module may do is an ALLOWLIST read from its
source (tests/pinned/test_pinned_source_rule.py): its imports, the calls it makes, the
names of bounds and numpy it touches, and arithmetic only between integers.
Whatever the list does not name is refused, so a rounding slip spelled some
new way is refused too. Each step above is a small function whose claim is
held to exact rational arithmetic on wide synthetic boxes, where every term of
it matters, with a planted fault per step (tests/pinned/test_pinned_certificate.py).
The end-to-end gates cannot see such a fault, because the enclosures have
slack: of eleven faults planted in these steps and in bounds, ten passed
equality with the authority on 32 rolls, its values and the exact Fractions
inside the enclosures, and the planted control streams (2026-09-26).
"""
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache

import numpy as np

from . import bounds as bd
from .basis import angles, assemble, modes
from .cft import FP64
from .encode import exact, to_fraction

TAU = float.fromhex("0x1p-200")                 # 2^-200, exact by its spelling


class EnclosureBroken(AssertionError):
    """The certificate contradicted the mathematics or the authority: a defect of the pinned path, never absorbed."""


@dataclass(frozen=True)
class Enclosure:
    lo: np.ndarray       # (M, N): lower bounds of the rows
    hi: np.ndarray       # (M, N): upper bounds
    n_lo: np.ndarray     # (M,): bounds of |phi_i|^2
    n_hi: np.ndarray
    l1: np.ndarray       # (M,): upper bounds of sum_n |lo[i, n]|
    dl1: np.ndarray      # (M,): upper bounds of sum_n (hi - lo)[i, n]


# ---------------------------------------------------------------------------
# The steps. Each returns bounds of every value its operands' boxes allow.


def magnitudes(lo, hi):
    """(the least, the greatest) |x| over x in [lo, hi]; exact (selects and sign flips). A select, never
    np.maximum, whose choice between -0.0 and +0.0 is the build's (P2, 2026-09-25)."""
    small = np.where(lo > 0, lo, np.where(hi < 0, -hi, 0.0))
    a, b = np.abs(lo), np.abs(hi)
    return small, np.where(a >= b, a, b)


def times_positive(a_lo, a_hi, t_lo, t_hi):
    """a * t over a in [a_lo, a_hi] (a_lo > 0) and t in [t_lo, t_hi]. a is positive, so the least product
    takes t_lo with a_lo when t_lo >= 0 and with a_hi when t_lo < 0; the greatest, t_hi likewise."""
    lo = np.where(t_lo >= 0, bd.mul_lo(a_lo, t_lo), bd.mul_lo(a_hi, t_lo))
    hi = np.where(t_hi >= 0, bd.mul_hi(a_hi, t_hi), bd.mul_hi(a_lo, t_hi))
    return lo, hi


def square(lo, hi):
    """y^2 over y in [lo, hi]: the squares of the least and the greatest |y|."""
    small, big = magnitudes(lo, hi)
    return bd.mul_lo(small, small), bd.mul_hi(big, big)


def rows(lo, hi):
    """The Enclosure of M rows in the box [lo, hi]: bounds of every row's squared norm, and the two 1-norms
    `inner` needs."""
    M, N = lo.shape
    small, big = magnitudes(lo, hi)
    ones = np.ones(M * N)
    return Enclosure(lo, hi, bd.dot_lo(small.ravel(), small.ravel(), N), bd.dot_hi(big.ravel(), big.ravel(), N),
                     bd.dot_hi(np.abs(lo).ravel(), ones, N), bd.dot_hi(bd.sub_hi(hi, lo).ravel(), ones, N))


def column(t, a_lo, a_hi):
    """q = A^T t over A in the box [a_lo, a_hi] (k rows of N), t a binary64 point: q[n] = sum_m t[m] A[m, n],
    least where each A[m, n] is its lower bound if t[m] >= 0 and its upper bound if t[m] < 0."""
    k, N = a_lo.shape
    pos = (t >= 0)[:, None]
    tt = np.tile(t, N)                                   # segment n: t[0..k-1] against A[0..k-1, n]
    q_lo = bd.dot_lo(tt, np.where(pos, a_lo, a_hi).T.ravel(), k)
    q_hi = bd.dot_hi(tt, np.where(pos, a_hi, a_lo).T.ravel(), k)
    return q_lo, q_hi


def inner(e, q_lo, q_hi):
    """<phi_i, q> for every row i, over phi_i in [e.lo[i], e.hi[i]] and q in [q_lo, q_hi]:
    <phi_i, q> = <lo_i, q_lo> + <phi_i - lo_i, q> + <lo_i, q - q_lo>. The first is a point product, rounded
    down and up; |the second| <= sum(hi_i - lo_i) * max|q| <= dl1_i * qabs; |the third| <= sum|lo_i| *
    max(q_hi - q_lo) <= l1_i * wmax."""
    M, N = e.lo.shape
    w = bd.sub_hi(q_hi, q_lo)
    qabs, wmax = magnitudes(q_lo, q_hi)[1].max(), w.max()
    rep = np.tile(q_lo, M)
    p_lo, p_hi = bd.dot_lo(e.lo.ravel(), rep, N), bd.dot_hi(e.lo.ravel(), rep, N)
    r = bd.add_hi(bd.mul_hi(e.dl1, qabs), bd.mul_hi(e.l1, wmax))
    return bd.sub_lo(p_lo, r), bd.add_hi(p_hi, r)


def gram_terms(q_prev, q_lo, q_hi):
    """What joining column q (in [q_lo, q_hi]) to Q's earlier point parts q_prev adds to upper bounds of
    |G0|_F^2, |Q_lo|_F^2 and |D|_F^2, with Q_lo the columns' lower bounds, G0 = Q_lo^T Q_lo - I and
    D = Q - Q_lo (entrywise in [0, q_hi - q_lo]). G0 gains a row and a column: its diagonal entry once,
    each off-diagonal entry twice."""
    Q = np.vstack([*q_prev, q_lo])
    k, N = Q.shape
    rep = np.tile(q_lo, k)
    g_lo, g_hi = bd.dot_lo(Q.ravel(), rep, N), bd.dot_hi(Q.ravel(), rep, N)
    g_lo[-1], g_hi[-1] = bd.sub_lo(g_lo[-1], 1.0), bd.sub_hi(g_hi[-1], 1.0)
    b = magnitudes(g_lo, g_hi)[1]
    off = bd.dot_hi(b[:-1], b[:-1], k - 1)[0] if k > 1 else 0.0
    w = bd.sub_hi(q_hi, q_lo)
    return (bd.add_hi(bd.mul_hi(b[-1], b[-1]), bd.mul_hi(2.0, off)), bd.dot_hi(q_lo, q_lo, N)[0],
            bd.dot_hi(w, w, N)[0])


def gram_bound(g0, qf, df):
    """F >= |E|_F >= |E|_2, E = Q^T Q - I, from upper bounds g0, qf, df of |G0|_F^2, |Q_lo|_F^2, |D|_F^2:
    E = G0 + Q_lo^T D + D^T Q_lo + D^T D, so |E|_F <= |G0|_F + 2 |Q_lo|_F |D|_F + |D|_F^2."""
    r = bd.sqrt_hi(np.array([g0, qf, df]))
    return bd.add_hi(bd.add_hi(r[0], bd.mul_hi(2.0, bd.mul_hi(r[1], r[2]))), df)


def gram_factors(F):
    """Bounds (g_lo, g_hi) of 1/(1+F) and 1/(1-F): (Q^T Q)^-1 = (I + E)^-1 has its eigenvalues between them.
    None unless F < 1."""
    if not F < 1.0:
        return None
    return bd.div_lo(1.0, bd.add_hi(1.0, F)), bd.div_hi(1.0, bd.sub_lo(1.0, F))


def weights(n_lo, n_hi, s_lo, s_hi, g_lo, g_hi):
    """c = n - p over n in [n_lo, n_hi] and p = |P phi|^2 in [s_lo * g_lo, s_hi * g_hi] (s = |y|^2 >= 0)."""
    return bd.sub_lo(n_lo, bd.mul_hi(s_hi, g_hi)), bd.sub_hi(n_hi, bd.mul_lo(s_lo, g_lo))


def target(u_lo, u_hi, s_lo, s_hi):
    """u * S over u in [u_lo, u_hi] and S in [s_lo, s_hi], both non-negative, widened by TAU either side."""
    return bd.sub_lo(bd.mul_lo(u_lo, s_lo), TAU), bd.add_hi(bd.mul_hi(u_hi, s_hi), TAU)


def locate(t_lo, t_hi, b_lo, b_hi):
    """(position, None) when certified: every boundary before it lies below t_lo, so the exact target
    passes it by more than TAU, and its own boundary lies above t_hi, so the exact target falls short of it by
    more than TAU. (None, why) when no position is."""
    passed = b_hi < t_lo
    p = len(passed) if passed.all() else np.argmin(passed)
    if p == len(passed):
        return None, "the target is not certifiably below the last cumulative weight"
    if not t_hi < b_lo[p]:
        return None, f"the target's enclosure meets that of the boundary after untaken site {p}"
    return p, None


# ---------------------------------------------------------------------------
# The basis enclosed, and the certificate along a roll.


@lru_cache(maxsize=16)
def enclosure(L, r2):
    """The exact basis enclosed at binary64: cospi and sinpi of the exact angles rounded down and up, times
    sqrt(2/M) rounded down and up, and the constant 1/L exactly. tests/pinned/test_pinned_exact.py holds it to the
    authority's own orbitals, entry by entry."""
    M = L * L
    N = modes(L, r2)[0].size
    ang = angles(L, FP64)
    two_m = exact(Fraction(2, M), FP64)[0]
    a_lo, a_hi = bd.sqrt_lo(two_m), bd.sqrt_hi(two_m)
    cos, sin = times_positive(a_lo, a_hi, bd.cospi_lo(ang), bd.cospi_hi(ang)), \
        times_positive(a_lo, a_hi, bd.sinpi_lo(ang), bd.sinpi_hi(ang))
    one = exact(Fraction(1, L), FP64)
    lo = assemble(L, r2, one, {1: cos[0], 2: sin[0]}, np.float64)
    hi = assemble(L, r2, one, {1: cos[1], 2: sin[1]}, np.float64)
    e = rows(lo, hi)
    diag = Fraction(N, M)                      # K_ii = N/M exactly, for an orthonormal basis of N columns
    if not all(to_fraction(FP64, a) <= diag <= to_fraction(FP64, b) for a, b in zip(e.n_lo, e.n_hi, strict=True)):
        raise EnclosureBroken(f"|phi_i|^2 is N/M = {N}/{M} exactly, and its enclosure misses it")
    return e


class Certificate:
    """Enclosures of the exact chain rule along one roll: `decide` a draw, then `extend` by its column."""

    def __init__(self, L, r2):
        self.e = enclosure(L, r2)
        self.M, self.N = self.e.lo.shape
        self.s_lo, self.s_hi = np.zeros(self.M), np.zeros(self.M)
        self.g0 = self.qf = self.df = 0.0
        self.q = []

    def decide(self, j, idx, u_lo, u_hi, trace=None):
        """(position among the untaken sites idx, None, slack) if draw j is certified, else (None, why, None).
        u_lo and u_hi are binary64 bounds of the draw's exact uniform."""
        g = gram_factors(gram_bound(self.g0, self.qf, self.df))
        if g is None:
            return None, f"draw {j}: the drawn basis's Gram bound is not below 1", None
        c_lo, c_hi = weights(self.e.n_lo[idx], self.e.n_hi[idx], self.s_lo[idx], self.s_hi[idx], *g)
        if (c_hi < 0).any():
            raise EnclosureBroken(f"draw {j}: a weight's upper bound is negative; an exact weight never is")
        # Exact weights are >= 0. A select, not np.maximum: numpy's maximum picks the sign of a zero by
        # whichever loop it runs (P2, 2026-09-25), and a select yields +0.0 on every machine.
        c_lo = np.where(c_lo > 0, c_lo, 0.0)
        b_lo, b_hi = bd.scan_lo(c_lo), bd.scan_hi(c_hi)
        if not b_lo[-1] <= self.N - j <= b_hi[-1]:
            raise EnclosureBroken(f"draw {j}: the untaken weights sum to N - j = {self.N - j} exactly, and their "
                                  f"enclosure [{b_lo[-1]!r}, {b_hi[-1]!r}] misses it")
        t_lo, t_hi = target(u_lo, u_hi, b_lo[-1], b_hi[-1])
        p, why = locate(t_lo, t_hi, b_lo, b_hi)
        if trace is not None:
            trace(j, {"target": (t_lo, t_hi), "bounds": (b_lo, b_hi), "untaken": idx, "position": p})
        if p is None:
            return None, f"draw {j}: {why}", None
        # Diagnostics, never a decision: how far the target cleared (at least), against how wide (at most).
        clear = min(bd.sub_lo(b_lo[p], t_hi), bd.sub_lo(t_lo, b_hi[p - 1]) if p else np.inf)
        width = max(bd.sub_hi(t_hi, t_lo), bd.sub_hi(b_hi[p], b_lo[p]),
                    bd.sub_hi(b_hi[p - 1], b_lo[p - 1]) if p else 0.0)
        return p, None, (clear, width)

    def extend(self, drawn, t):
        """Join Q's column q = A^T t: A the drawn rows (site indices, in draw order), t binary64 coefficients."""
        q_lo, q_hi = column(t, self.e.lo[drawn], self.e.hi[drawn])
        dg, dq, dd = gram_terms(self.q, q_lo, q_hi)
        self.g0, self.qf, self.df = bd.add_hi(self.g0, dg), bd.add_hi(self.qf, dq), bd.add_hi(self.df, dd)
        sq_lo, sq_hi = square(*inner(self.e, q_lo, q_hi))
        self.s_lo, self.s_hi = bd.add_lo(self.s_lo, sq_lo), bd.add_hi(self.s_hi, sq_hi)
        self.q.append(q_lo)

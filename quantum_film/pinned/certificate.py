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
    `gram_accumulate`, `gram_bound`). If F is not below 1 the draw is not
    certified.
  - |P phi|^2 = y^T (Q^T Q)^-1 y with y = Q^T phi, and the eigenvalues of
    (I + E)^-1 lie in [1/(1+F), 1/(1-F)] (`gram_factors`), so |P phi|^2 lies
    in [|y|^2 / (1+F), |y|^2 / (1-F)]. |y|^2 gains one term <phi_i, q_k>^2 a
    draw (`inner`, `square`, `accumulate`).
  - c_i lies in [n_lo - s_hi/(1-F), n_hi - s_lo/(1+F)] (`weights`).

Prefix sums of those bound every cumulative weight the authority compares
(`boundaries`), their last entries bound its total, and u times the total,
from u's own exact bounds (`uniform_box`), bounds its target (`target`).
`locate` certifies a draw only when the target's enclosure clears every
boundary it is compared with by TAU.

THREE LAYERS HOLD IT (verifier-P1's D2 and D3, 2026-09-26):
  1. THE STEPS, behaviourally. Every directed operation lives in a step: a
     module-level function from intervals (lo, hi) to intervals or bounds.
     Each step is held to exact rational arithmetic on TIGHT inputs, where
     the exact value its bound claims is not representable and nothing but
     the step's own roundings separates the bound from it, so a bound on the
     wrong side of its exact value shows however it was spelled
     (tests/pinned/test_pinned_certificate.py). And every directed call,
     flipped alone to the other direction, fails its step's check there: a
     mutation gate over this file's source. A one-ulp wrong direction in an
     accumulation passed every gate before (six of them, verifier-P1), because
     the accumulations sat outside any step and wide boxes left slack.
  2. THE ORCHESTRATION, structurally. `Certificate` and `enclosure` only
     compose steps: no bounds, no numpy, no subscripts, no unpacking, only
     integer arithmetic. An interval passes from step to step whole, so its
     two ends cannot be swapped between them. The ALLOWLIST read from this
     file's source (tests/pinned/test_pinned_source_rule.py) holds that, and
     what the whole module may name: its imports, its calls by name and
     arity, exact float literals and fromhex strings, integers up to 2^53, and
     no item or slice assignment.
  3. THE ROLLS, end to end: equality with the authority, exact containment,
     refusals that survive, and the planted control (tests/pinned).
"""
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache
from typing import NamedTuple

import numpy as np

from . import bounds as bd
from .basis import angles, assemble, frozen, modes
from .cft import FP64
from .encode import bounds64, exact, to_fraction

TAU = float.fromhex("0x1p-200")                 # 2^-200, exact by its spelling


class EnclosureBroken(AssertionError):
    """The certificate contradicted the mathematics or the authority: a defect of the pinned path, never absorbed."""


@dataclass(frozen=True)
class Enclosure:
    box: tuple           # (lo, hi): (M, N) bounds of the exact rows
    norm: tuple          # (n_lo, n_hi): (M,) bounds of each row's squared norm
    l1: np.ndarray       # (M,): upper bounds of sum_n |lo[i, n]|
    dl1: np.ndarray      # (M,): upper bounds of sum_n (hi - lo)[i, n]
    M: int
    N: int


class Located(NamedTuple):
    position: object     # the certified position among the untaken sites, or None
    reason: object       # why no position is certified, or None


# ---------------------------------------------------------------------------
# Data and exact helpers: selections, comparisons and sign flips. No rounding.


def magnitudes(x):
    """[min |v|, max |v|] over v in the interval x; exact (selects and sign flips). A select, never np.maximum,
    whose choice between -0.0 and +0.0 is the build's (P2, 2026-09-25)."""
    lo, hi = x
    small = np.where(lo > 0, lo, np.where(hi < 0, -hi, 0.0))
    a, b = np.abs(lo), np.abs(hi)
    return small, np.where(a >= b, a, b)


def select(x, idx):
    """The interval x's entries at idx."""
    lo, hi = x
    return lo[idx], hi[idx]


def last(x):
    """The interval x's last entry: the prefix sums' total."""
    lo, hi = x
    return lo[-1], hi[-1]


def lower(x):
    """The interval x's lower end: Q's point part."""
    return x[0]


def zero(size):
    """The interval [0, 0] of `size` sums not yet begun."""
    return np.zeros(size), np.zeros(size)


def upper_negative(c):
    """Whether some weight's upper bound is negative: an exact weight never is."""
    return (c[1] < 0).any()


def holds(x, value):
    """Whether the exact value (an int or a Fraction) lies in the interval x, compared exactly."""
    lo, hi = x
    return to_fraction(FP64, lo) <= value <= to_fraction(FP64, hi)


def holds_all(x, value):
    lo, hi = x
    return all(to_fraction(FP64, a) <= value <= to_fraction(FP64, b) for a, b in zip(lo, hi, strict=True))


def assemble_box(L, r2, one, cos, sin):
    """The (M, N) box of the basis: its constant column exactly `one`, its cosine and sine columns from the
    intervals cos and sin over the L angles (quantum_film.pinned.basis.assemble, once for each end)."""
    return (assemble(L, r2, one, {1: cos[0], 2: sin[0]}, np.float64),
            assemble(L, r2, one, {1: cos[1], 2: sin[1]}, np.float64))


def freeze(e):
    """e, with every array read-only: the enclosure is cached and shared, so no caller may write into it."""
    frozen(*e.box, *e.norm, e.l1, e.dl1)
    return e


def locate(t, b):
    """Located(position, None) when certified: every boundary before the position lies below t_lo, so the exact
    target passes it by more than TAU, and its own boundary lies above t_hi, so the exact target falls short of it
    by more than TAU. Located(None, why) when no position is. Exact comparisons."""
    (t_lo, t_hi), (b_lo, b_hi) = t, b
    passed = b_hi < t_lo
    p = len(passed) if passed.all() else np.argmin(passed)
    if p == len(passed):
        return Located(None, "the target is not certifiably below the last cumulative weight")
    if not t_hi < b_lo[p]:
        return Located(None, f"the target's enclosure meets that of the boundary after untaken site {p}")
    return Located(p, None)


# ---------------------------------------------------------------------------
# The steps. Each returns bounds of every value its operands' intervals allow; each is held exactly on tight inputs.


def uniform_box(u):
    """[u_lo, u_hi]: the binary64 numbers either side of the exact uniform u, a Fraction (equal when u is one)."""
    return bounds64(u)


def sqrt_box(x):
    return bd.sqrt_lo(x), bd.sqrt_hi(x)


def cospi_box(a):
    return bd.cospi_lo(a), bd.cospi_hi(a)


def sinpi_box(a):
    return bd.sinpi_lo(a), bd.sinpi_hi(a)


def times_positive(a, t):
    """a * t over a in the interval a (a_lo > 0) and t in the interval t. a is positive, so the least product takes
    t_lo with a_lo when t_lo >= 0 and with a_hi when t_lo < 0; the greatest, t_hi likewise."""
    (a_lo, a_hi), (t_lo, t_hi) = a, t
    lo = np.where(t_lo >= 0, bd.mul_lo(a_lo, t_lo), bd.mul_lo(a_hi, t_lo))
    hi = np.where(t_hi >= 0, bd.mul_hi(a_hi, t_hi), bd.mul_hi(a_lo, t_hi))
    return lo, hi


def square(y):
    """y^2 over y in the interval y: the squares of the least and the greatest |y|."""
    small, big = magnitudes(y)
    return bd.mul_lo(small, small), bd.mul_hi(big, big)


def rows(phi):
    """The Enclosure of M rows in the box phi: bounds of every row's squared norm, and the two 1-norms `inner`
    needs."""
    lo, hi = phi
    M, N = lo.shape
    small, big = magnitudes(phi)
    ones = np.ones(M * N)
    norm = bd.dot_lo(small.ravel(), small.ravel(), N), bd.dot_hi(big.ravel(), big.ravel(), N)
    return Enclosure(phi, norm, bd.dot_hi(np.abs(lo).ravel(), ones, N),
                     bd.dot_hi(bd.sub_hi(hi, lo).ravel(), ones, N), M, N)


def column(t, A):
    """q = A^T t over A in the box A (k rows of N), t a binary64 point: q[n] = sum_m t[m] A[m, n], least where
    each A[m, n] is its lower bound if t[m] >= 0 and its upper bound if t[m] < 0."""
    a_lo, a_hi = A
    k, N = a_lo.shape
    pos = (t >= 0)[:, None]
    tt = np.tile(t, N)                                   # segment n: t[0..k-1] against A[0..k-1, n]
    return (bd.dot_lo(tt, np.where(pos, a_lo, a_hi).T.ravel(), k),
            bd.dot_hi(tt, np.where(pos, a_hi, a_lo).T.ravel(), k))


def inner(e, q):
    """<phi_i, q> for every row i, over phi_i in the row's box and q in the interval q:
    <phi_i, q> = <lo_i, q_lo> + <phi_i - lo_i, q> + <lo_i, q - q_lo>. The first is a point product, rounded
    down and up; |the second| <= sum(hi_i - lo_i) * max|q| <= dl1_i * qabs; |the third| <= sum|lo_i| *
    max(q_hi - q_lo) <= l1_i * wmax."""
    q_lo, q_hi = q
    lo = e.box[0]
    w = bd.sub_hi(q_hi, q_lo)
    qabs, wmax = magnitudes(q)[1].max(), w.max()
    rep = np.tile(q_lo, e.M)
    p_lo, p_hi = bd.dot_lo(lo.ravel(), rep, e.N), bd.dot_hi(lo.ravel(), rep, e.N)
    r = bd.add_hi(bd.mul_hi(e.dl1, qabs), bd.mul_hi(e.l1, wmax))
    return bd.sub_lo(p_lo, r), bd.add_hi(p_hi, r)


def accumulate(s, d):
    """The interval sum s + d: |y|^2 gaining its newest term."""
    (s_lo, s_hi), (d_lo, d_hi) = s, d
    return bd.add_lo(s_lo, d_lo), bd.add_hi(s_hi, d_hi)


def gram_terms(q_prev, q):
    """What joining column q (in the interval q) to Q's earlier point parts q_prev adds to upper bounds of
    |G0|_F^2, |Q_lo|_F^2 and |D|_F^2, with Q_lo the columns' lower bounds, G0 = Q_lo^T Q_lo - I and
    D = Q - Q_lo (entrywise in [0, q_hi - q_lo]). G0 gains a row and a column, Q_lo^T q_lo - e_k: its diagonal
    entry once, each off-diagonal entry twice."""
    q_lo, q_hi = q
    Q = np.vstack([*q_prev, q_lo])
    k, N = Q.shape
    rep = np.tile(q_lo, k)
    unit = np.eye(k)[k - 1]
    g = bd.sub_lo(bd.dot_lo(Q.ravel(), rep, N), unit), bd.sub_hi(bd.dot_hi(Q.ravel(), rep, N), unit)
    b = magnitudes(g)[1]
    diag = bd.mul_hi(b[k - 1], b[k - 1])
    off = bd.dot_hi(b[:k - 1], b[:k - 1], k - 1)[0] if k > 1 else 0.0
    w = bd.sub_hi(q_hi, q_lo)
    return bd.add_hi(bd.add_hi(diag, off), off), bd.dot_hi(q_lo, q_lo, N)[0], bd.dot_hi(w, w, N)[0]


def gram_accumulate(g, d):
    """Upper bounds of the three running sums |G0|_F^2, |Q_lo|_F^2 and |D|_F^2, each after its increment."""
    return bd.add_hi(g[0], d[0]), bd.add_hi(g[1], d[1]), bd.add_hi(g[2], d[2])


def gram_bound(g):
    """F >= |E|_F >= |E|_2, E = Q^T Q - I, from upper bounds (g0, qf, df) of |G0|_F^2, |Q_lo|_F^2 and |D|_F^2:
    E = G0 + Q_lo^T D + D^T Q_lo + D^T D, so |E|_F <= |G0|_F + 2 |Q_lo|_F |D|_F + |D|_F^2."""
    m = bd.mul_hi(bd.sqrt_hi(g[1]), bd.sqrt_hi(g[2]))
    return bd.add_hi(bd.add_hi(bd.add_hi(bd.sqrt_hi(g[0]), m), m), g[2])


def gram_factors(F):
    """The interval [1/(1+F), 1/(1-F)]: (Q^T Q)^-1 = (I + E)^-1 has its eigenvalues in it. None unless F < 1."""
    if not F < 1.0:
        return None
    return bd.div_lo(1.0, bd.add_hi(1.0, F)), bd.div_hi(1.0, bd.sub_lo(1.0, F))


def weights(n, s, g):
    """c = n - p over n in the interval n and p = |P phi|^2 in [s_lo * g_lo, s_hi * g_hi] (s = |y|^2 >= 0)."""
    (n_lo, n_hi), (s_lo, s_hi), (g_lo, g_hi) = n, s, g
    return bd.sub_lo(n_lo, bd.mul_hi(s_hi, g_hi)), bd.sub_hi(n_hi, bd.mul_lo(s_lo, g_lo))


def boundaries(c):
    """The prefix sums of weights in the interval c. Exact weights are >= 0, so their lower bounds are raised to 0
    first, by a select."""
    c_lo, c_hi = c
    return bd.scan_lo(np.where(c_lo > 0, c_lo, 0.0)), bd.scan_hi(c_hi)


def target(u, S):
    """u * S over u in the interval u and S in the interval S, both non-negative, widened by TAU either side."""
    (u_lo, u_hi), (s_lo, s_hi) = u, S
    return bd.sub_lo(bd.mul_lo(u_lo, s_lo), TAU), bd.add_hi(bd.mul_hi(u_hi, s_hi), TAU)


def clearance(t, b, p):
    """Diagnostics, never a decision: a lower bound of how far the exact target cleared the boundaries either side
    of position p, and an upper bound of the widest of their enclosures and the target's."""
    (t_lo, t_hi), (b_lo, b_hi) = t, b
    clear = min(bd.sub_lo(b_lo[p], t_hi), bd.sub_lo(t_lo, b_hi[p - 1]) if p else np.inf)
    width = max(bd.sub_hi(t_hi, t_lo), bd.sub_hi(b_hi[p], b_lo[p]),
                bd.sub_hi(b_hi[p - 1], b_lo[p - 1]) if p else 0.0)
    return clear, width


# ---------------------------------------------------------------------------
# The orchestration: steps composed, nothing computed here.


@lru_cache(maxsize=16)
def enclosure(L, r2):
    """The exact basis enclosed at binary64: cospi and sinpi of the exact angles rounded down and up, times
    sqrt(2/M) rounded down and up, and the constant 1/L exactly; read-only, since it is cached and shared.
    tests/pinned/test_pinned_exact.py holds it to the authority's own orbitals, entry by entry."""
    M = L * L
    modes(L, r2)                                          # refuses a tile that is not a power of two, first
    ang = angles(L, FP64)
    a = sqrt_box(exact(Fraction(2, M), FP64))
    phi = assemble_box(L, r2, exact(Fraction(1, L), FP64), times_positive(a, cospi_box(ang)),
                       times_positive(a, sinpi_box(ang)))
    e = rows(phi)
    if not holds_all(e.norm, Fraction(e.N, M)):          # K_ii = N/M exactly, for an orthonormal basis
        raise EnclosureBroken(f"|phi_i|^2 is N/M = {e.N}/{M} exactly, and its enclosure misses it")
    return freeze(e)


class Certificate:
    """Enclosures of the exact chain rule along one roll: `decide` a draw, then `extend` by its column."""

    def __init__(self, L, r2):
        self.e = enclosure(L, r2)
        self.M = self.e.M
        self.N = self.e.N
        self.s = zero(self.M)
        self.g = (0.0, 0.0, 0.0)
        self.q = []

    def decide(self, j, idx, u, trace=None):
        """(position among the untaken sites idx, None, slack) if draw j is certified, else (None, why, None).
        u is the draw's exact uniform, a Fraction."""
        factors = gram_factors(gram_bound(self.g))
        if factors is None:
            return None, f"draw {j}: the drawn basis's Gram bound is not below 1", None
        c = weights(select(self.e.norm, idx), select(self.s, idx), factors)
        if upper_negative(c):
            raise EnclosureBroken(f"draw {j}: a weight's upper bound is negative; an exact weight never is")
        b = boundaries(c)
        if not holds(last(b), self.N - j):
            raise EnclosureBroken(f"draw {j}: the untaken weights sum to N - j = {self.N - j} exactly, and their "
                                  f"enclosure {last(b)!r} misses it")
        t = target(uniform_box(u), last(b))
        found = locate(t, b)
        if trace is not None:
            trace(j, {"target": t, "bounds": b, "untaken": idx, "position": found.position})
        if found.position is None:
            return None, f"draw {j}: {found.reason}", None
        return found.position, None, clearance(t, b, found.position)

    def extend(self, drawn, t):
        """Join Q's column q = A^T t: A the drawn rows (site indices, in draw order), t binary64 coefficients."""
        q = column(t, select(self.e.box, drawn))
        self.g = gram_accumulate(self.g, gram_terms(self.q, q))
        self.s = accumulate(self.s, square(inner(self.e, q)))
        self.q.append(lower(q))

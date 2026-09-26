"""The Pauli law on pinned binary64: libcft's chain rule, certified draw by draw.

WHAT IT RETURNS: the authority's roll (quantum_film.golden.fermi), for every
stream, by construction, on any Pauli stock whose tile edge L is a power of
two (both shelf stocks are); another L is refused by name, because its angles
2m/L are not dyadic and cospi and sinpi could not take them exactly.

1. Every draw is decided from ENCLOSURES of the EXACT chain rule's cumulative
   weights and target, computed in binary64 by libcft under directed rounding
   (quantum_film.pinned.certificate). A draw is CERTIFIED when the target's
   enclosure clears every boundary it is compared with, on the right side,
   by more than TAU = 2^-200.
2. The authority decides every draw it does not refuse as the exact chain
   rule does: its error in a boundary or a target stays far below half its
   2^-224 margin (docs/DETERMINISM.md; measured against references it does
   not share at 2^-252.4 on pauli-4x4 and 2^-249.2 on the 16x16 stock, the
   lead, 2026-09-25). So a draw whose exact target clears its boundaries by
   more than TAU is one the authority neither refuses nor decides
   differently. TAU is 2^24 times the margin: the authority's error would
   have to grow more than 2^47-fold before a certified draw could part from it.
3. A draw that cannot be certified hands the WHOLE roll to the authority
   (golden exposes no per-draw entry point): its answer is returned, its
   refusals (TieRefusal, PrecisionChanged) propagate, and the hand-off is
   counted. A stream the authority refuses therefore gets no pinned answer:
   a refused draw's exact target lies within 2^-224 plus twice the
   authority's error of a boundary, far inside TAU, so no enclosure clears it.
4. The hand-off AUDITS the certificate. The authority's first draws must be
   the ones the certificate decided, and it must not refuse any of them;
   otherwise the pinned path refuses by name (EnclosureBroken). So does an
   enclosure that contradicts the mathematics: a weight whose upper bound is
   negative, or untaken weights whose enclosed sum excludes N - j (for an
   orthonormal basis the exact sum is N - j at draw j).

CERTIFICATION OFF (`certify=False`) is the same chain rule in plain
round-to-nearest arithmetic, at binary32, binary64 or binary128: its own
weights, its own sums, its own comparisons, and no hand-off. That is the
precision demonstration. `handoff=False` keeps the certificate but lets plain
binary64 decide a draw the certificate cannot clear: the negative control's
sampler (quantum_film.pinned.control).

Not thread-safe, by rule: libcft's device is not, and the hand-off runs the
authority, whose mpmath precision is process-global. It runs on the main
thread only (ThreadRefusal).
"""
import threading
from dataclasses import dataclass, field
from fractions import Fraction

import numpy as np

from ..golden import fermi as golden
from ..golden.uniform import stream as golden_stream
from ..golden.uniform import uniform as golden_uniform
from ..stocks import params
from . import cft
from .basis import FORMATS, basis
from .certificate import TAU, Certificate, EnclosureBroken, enclosure
from .cft import DOT, FP64, RNE, SUM
from .encode import round_fraction
from .uniform import uniform as pinned_uniform

__all__ = ["roll", "sample", "lay", "Roll", "Chain", "EnclosureBroken", "FloatRefusal", "TAU", "COUNTS",
           "enclosure", "basis", "FORMATS"]

COUNTS = {"rolls": 0, "handoffs": 0}


class FloatRefusal(ValueError):
    """Certification OFF: the plain chain's target was not below its own last cumulative sum."""


@dataclass
class Roll:
    crystals: list                   # sorted site indices, as golden.fermi.sample returns them
    draws: list                      # the same sites in draw order
    fmt: str = "fp64"
    certified: bool = True           # False: certification was switched OFF
    handed_off: bool = False
    draw: int | None = None          # the first draw that could not be certified
    reason: str | None = None
    slack: list = field(default_factory=list)        # per certified draw: (clearance, enclosure width)
    uncertified: list = field(default_factory=list)  # handoff=False only: draws binary64 decided uncertified


def _scan(fmt, rnd, x):
    """Prefix sums (Hillis-Steele: log2 n passes, one fixed association for each prefix)."""
    y = x.copy()
    d = 1
    while d < len(y):
        nxt = y.copy()
        nxt[d:] = cft.add(fmt, rnd, y[d:], y[:-d])
        y, d = nxt, 2 * d
    return y


class Chain:
    """The chain rule in plain round-to-nearest arithmetic in `fmt`: the sampler with certification OFF (with
    `weights`), and the certified sampler's source of basis coefficients T (with `coefficients`, binary64).
    Gram-Schmidt is classical and applied twice, as the authority applies it twice."""

    def __init__(self, L, r2, fmt, weights, coefficients):
        self.fmt = fmt
        self.phi = basis(L, r2, fmt)
        self.M, self.N = self.phi.shape
        self.q, self.T = [], []
        self.coefficients = coefficients
        if weights:
            self.c = cft.reduce_seg(DOT, fmt, RNE, self.phi.ravel(), self.phi.ravel(), self.N)

    def decide(self, j, idx, u, trace=None):
        f = self.fmt
        cu = self.c[idx]
        total = cft.reduce(SUM, f, RNE, cu)                        # unclamped, as the authority's total
        target = cft.mul(f, RNE, round_fraction(u, f, RNE), total)
        bounds = _scan(f, RNE, cft.maximum(f, cu, np.zeros(len(cu), cft.dtype(f))))
        below = cft.less(f, np.repeat(target, len(bounds)), bounds)
        if trace is not None:
            trace(j, {"target": target, "total": total, "bounds": bounds, "untaken": idx})
        if not below.any():
            raise FloatRefusal(f"draw {j}: the {cft.FORMATS[f][0]} target is not below its last cumulative sum")
        return int(np.argmax(below))

    def grow(self, s):
        """Orthonormalise row s against the basis so far; with `coefficients`, also its column t of T."""
        f, a, N, j = self.fmt, self.phi[s], self.N, len(self.q)
        if j:
            Q = np.stack(self.q)
            Qt = np.ascontiguousarray(Q.T).ravel()
            d = cft.reduce_seg(DOT, f, RNE, Q.ravel(), np.tile(a, j), N)
            v1 = cft.sub(f, RNE, a, cft.reduce_seg(DOT, f, RNE, Qt, np.tile(d, N), j))
            d2 = cft.reduce_seg(DOT, f, RNE, Q.ravel(), np.tile(v1, j), N)
            v = cft.sub(f, RNE, v1, cft.reduce_seg(DOT, f, RNE, Qt, np.tile(d2, N), j))
        else:
            v = a
        nv = cft.sqrt(f, RNE, cft.reduce(DOT, f, RNE, v, v))
        q = cft.div(f, RNE, v, np.repeat(nv, N))
        self.q.append(q)
        if self.coefficients:
            # v = a - sum_k (d_k + d2_k) q_k and q_k ~ A^T t_k, so t_j = (e_j - sum_k (d_k + d2_k) t_k) / |v|.
            one = np.ones(1)
            if j:
                e = cft.add(FP64, RNE, d, d2)
                Tm = np.zeros((j, j))
                for k, t in enumerate(self.T):
                    Tm[:len(t), k] = t
                w = cft.reduce_seg(DOT, FP64, RNE, Tm.ravel(), np.tile(e, j), j)
                t = np.concatenate([cft.div(FP64, RNE, -w, np.repeat(nv, j)), cft.div(FP64, RNE, one, nv)])
            else:
                t = cft.div(FP64, RNE, one, nv)
            self.T.append(t)
        return q

    def update(self, q):
        """c_i -= <phi_i, q>^2, rounded to nearest, as the authority's c[i] -= d * d."""
        f = self.fmt
        y = cft.reduce_seg(DOT, f, RNE, self.phi.ravel(), np.tile(q, self.M), self.N)
        self.c = cft.sub(f, RNE, self.c, cft.mul(f, RNE, y, y))


def _main_thread():
    if threading.current_thread() is not threading.main_thread():
        raise cft.ThreadRefusal("the pinned sampler runs on the main thread only: it may hand a roll to the "
                                "authority, and mpmath's working precision is process-global")


def _uniform(fn, stream_bytes, j):
    u = fn(stream_bytes, j)
    if not isinstance(u, Fraction) or not 0 <= u < 1:
        raise ValueError(f"draw {j}: uniform {u!r} is not an exact Fraction in [0, 1)")
    return u


def roll(L, r2, stream_bytes, uniform_fn=None, certify=True, handoff=True, fmt="fp64", trace=None):
    """One roll of the Pauli law on an L x L tile with Fermi disc r2.

    certify=True (binary64): the authority's roll, certified draw by draw or handed off whole.
    handoff=False (the negative control's sampler): a draw the certificate cannot clear is decided by the
      plain binary64 chain instead of being handed off, and the roll records which draws those were.
    certify=False: the plain chain rule in `fmt` (fp32, fp64 or fp128), with no certificate and no hand-off.
    `uniform_fn(stream_bytes, j)` defaults to the authority's uniforms, hashed by libcft.
    `trace(j, info)` observes each draw's target and boundaries (enclosures when certified)."""
    _main_thread()
    f = FORMATS[fmt]
    if certify and f != FP64:
        raise ValueError(f"the certificate is binary64; {fmt} runs with certification off only")
    ufn = uniform_fn if uniform_fn is not None else pinned_uniform
    weights = not certify or not handoff
    chain = Chain(L, r2, f, weights=weights, coefficients=certify)
    cert = Certificate(L, r2) if certify else None
    taken = np.zeros(chain.M, dtype=bool)
    draws, slack, uncertified = [], [], []
    for j in range(chain.N):
        u = _uniform(ufn, stream_bytes, j)
        idx = np.flatnonzero(~taken)
        if certify:
            p, why, sl = cert.decide(j, idx, u, trace)
            if p is None and handoff:
                return _hand_off(L, r2, stream_bytes, uniform_fn, draws, why)
            if p is None:
                p = chain.decide(j, idx, u)
                uncertified.append(j)
            else:
                slack.append(sl)
        else:
            p = chain.decide(j, idx, u, trace)
        s = int(idx[p])
        draws.append(s)
        taken[s] = True
        if j == chain.N - 1:
            break
        q = chain.grow(s)
        if certify:
            cert.extend(np.array(draws), chain.T[-1])
        if weights:
            chain.update(q)
    COUNTS["rolls"] += 1
    return Roll(sorted(draws), draws, fmt=fmt, certified=certify, slack=slack, uncertified=uncertified)


def _hand_off(L, r2, stream_bytes, uniform_fn, decided, why):
    """The whole roll, from the authority; the draws the certificate decided must be its first draws."""
    order, taken = [], set()

    def watch(_j, _target, seen):
        s = [i for i in range(L * L) if i not in taken][len(seen) - 1]
        order.append(s)
        taken.add(s)

    j = len(decided)
    try:
        crystals = golden.sample(L, r2, stream_bytes, uniform_fn=uniform_fn or golden_uniform, trace=watch)
    except golden.TieRefusal as refusal:
        # Only the first j draws are the certificate's. A refusal at draw j or later is the authority's own, and
        # propagates as it is; a refusal of a draw the certificate decided, or other draws before it, is not.
        if len(order) < j:
            raise EnclosureBroken(f"the authority refused draw {len(order)}, which the certificate had decided "
                                  f"(draws {decided}); {why}") from refusal
        if order[:j] != decided:
            raise EnclosureBroken(f"the certificate decided draws {decided}, and the authority drew "
                                  f"{order[:j]} before refusing draw {len(order)}") from refusal
        raise
    if order[:j] != decided:
        raise EnclosureBroken(f"the certificate decided draws {decided}, and the authority drew {order[:j]}")
    COUNTS["rolls"] += 1
    COUNTS["handoffs"] += 1
    return Roll(crystals, order, handed_off=True, draw=j, reason=why)


def sample(L, r2, stream_bytes, uniform_fn=None):
    """golden.fermi.sample's call and answer: the sorted crystals of one roll, certified or handed off."""
    return roll(L, r2, stream_bytes, uniform_fn=uniform_fn).crystals


def lay(stock_id, seed, **kw):
    """The roll of a shelf stock on its stream ("roll", stock_id, seed), as quantum_film.fixer.lay draws it."""
    law = params(stock_id)
    if law["family"] != "determinantal":
        raise LookupError(f"the pinned path lays the Pauli law only; {stock_id!r} is {law['family']}")
    return roll(law["L"], law["fermi_r2"], golden_stream("roll", stock_id, seed), **kw)

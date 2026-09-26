"""Every step of the certificate held to exact rational arithmetic on TIGHT inputs, and a mutation gate over its
directed calls (verifier-P1's D2, 2026-09-26).

A bound computed in the wrong direction is off by one unit in the last place, and a gate on the rolls cannot see
that: the real enclosures carry slack larger than an ulp. Six such faults passed every gate, because the
accumulations in decide and extend belonged to no step, and because wide random boxes leave a step's own bound
slack. So:

- every directed operation lives in a step (certificate.py; the source rule keeps the orchestration free of them);
- each step's check feeds it TIGHT inputs: point intervals, or boxes on which its bound's formula is attained, so
  that nothing but the step's own roundings separates the bound from the exact value it claims, and that value is
  not a binary64 number. A bound must land on its own side of the exact value, computed here in Fractions (or, for
  square roots and pi, bracketed at 256 to 300 bits);
- THE MUTATION GATE flips each directed call in certificate.py, alone, to its other direction (add_lo to add_hi,
  ...), loads the mutant, and holds the step to its check: every flip must fail it. So a one-ulp wrong direction
  anywhere in the certificate is seen, not only the wholesale faults planted before.

The checks are behavioural: whatever spelling moves a step's output across its exact value on these inputs, a
Fraction assigned into an array, a positional dtype, a long hex literal, is seen here as surely as a flipped call.
Some inputs lie outside what a roll can reach (a uniform near 2^-100, where TAU is not negligible): the step's claim
holds for all its inputs, and those are where one of its calls would otherwise never matter.
"""
import ast
import inspect
import math
import random
from fractions import Fraction

import mpmath
import numpy as np
import pytest
from mpmath import mp

from quantum_film.golden import fermi
from quantum_film.pinned import certificate as c
from quantum_film.pinned.control import mpf_fraction

SOURCE = inspect.getsource(c)


def X(v):
    return Fraction(float(v))


def exact64(fr):
    """Whether an exact rational is a binary64 number."""
    return Fraction(float(fr)) == fr


def fl(rng, e_lo, e_hi, bits=53, sign=1):
    """A random binary64 with `bits` significant bits and its binary exponent in [e_lo, e_hi)."""
    m = rng.randrange(1 << (bits - 1), 1 << bits)
    return sign * float(Fraction(m, 1 << (bits - 1)) * Fraction(2) ** rng.randrange(e_lo, e_hi))


def pm(rng):
    return rng.choice((1, -1))


def arr(xs):
    return np.array(xs, dtype=np.float64)


def up(x):
    return float(np.nextafter(float(x), np.inf))


def sqrt_exact(fr):
    """The square root of a non-negative Fraction if it is rational, else None."""
    n, d = fr.numerator, fr.denominator
    rn, rd = math.isqrt(n), math.isqrt(d)
    return Fraction(rn, rd) if rn * rn == n and rd * rd == d else None


def sqrt_floor(fr, bits=300):
    """A lower bound of the square root of a non-negative Fraction, within 2^-bits of it (integer arithmetic)."""
    n, d = fr.numerator, fr.denominator
    return Fraction(math.isqrt(n * d * 4 ** bits), d * 2 ** bits)


# ---------------------------------------------------------------------------------------------------------------
# One check per step: (problems, how many of the exact values checked were not binary64 numbers).


def check_uniform_box(fn):
    rng = random.Random(1)
    us = [Fraction(rng.randrange(0, q), q) for q in (rng.randrange(3, 1 << 80) | 1 for _ in range(150))]
    us += [Fraction(rng.randrange(0, 1 << 64), 1 << 64) for _ in range(20)]      # the streams' own: exact
    out, inexact = [], 0
    for u in us:
        lo, hi = fn(u)
        if exact64(u):
            ok = X(lo) == X(hi) == u
        else:
            inexact += 1
            ok = X(lo) < u < X(hi) and float(hi) == up(lo)
        if not ok:
            out.append(f"uniform_box({u}) = [{lo!r}, {hi!r}]")
    return out, inexact


def check_sqrt_box(fn):
    rng = random.Random(2)
    xs = [fl(rng, -80, 80) for _ in range(150)] + [float(rng.randrange(1, 1 << 26) ** 2) for _ in range(20)]
    lo, hi = fn(arr(xs))
    out, inexact = [], 0
    for x, a, b in zip(xs, lo, hi, strict=True):
        s = sqrt_exact(Fraction(x))
        if s is not None:
            ok = X(a) == X(b) == s
        else:
            inexact += 1
            ok = X(a) ** 2 < Fraction(x) < X(b) ** 2 and float(b) == up(a)
        if not ok:
            out.append(f"sqrt_box({x!r}) = [{a!r}, {b!r}]")
    return out, inexact


def check_trig(fn, f, name):
    angs = [Fraction(2 * m, L) for L in (4, 8, 16, 32, 64) for m in range(L)]
    lo, hi = fn(arr([float(a) for a in angs]))
    out, inexact = [], 0
    for a, x, y in zip(angs, lo, hi, strict=True):
        with mp.workprec(256):
            v = mpf_fraction(f(mpmath.mpf(a.numerator) / a.denominator))
        if (2 * a).denominator == 1:                     # a half-integer: the value is -1, 0 or 1 exactly
            ok = X(x) == X(y) == round(v)
        else:
            inexact += 1
            ok = X(x) < v < X(y) and float(y) == up(x)
        if not ok:
            out.append(f"{name}({a}) = [{x!r}, {y!r}]")
    return out, inexact


def check_cospi_box(fn):
    return check_trig(fn, mpmath.cospi, "cospi_box")


def check_sinpi_box(fn):
    return check_trig(fn, mpmath.sinpi, "sinpi_box")


def corners(a, b, x, y):
    """The least and the greatest of v * w over v in [a, b] and w in [x, y], exactly."""
    vals = [Fraction(v) * Fraction(w) for v in (a, b) for w in (x, y)]
    return min(vals), max(vals)


def check_times_positive(fn):
    rng = random.Random(4)
    out, inexact = [], 0
    xs = [fl(rng, -8, 8) for _ in range(150)]
    ys = [fl(rng, -8, 8, sign=pm(rng)) for _ in range(150)]
    lo, hi = fn((arr(xs), arr(xs)), (arr(ys), arr(ys)))                     # point intervals
    for x, y, a, b in zip(xs, ys, lo, hi, strict=True):
        e = Fraction(x) * Fraction(y)
        inexact += not exact64(e)
        if not X(a) <= e <= X(b):
            out.append(f"times_positive({x!r}, {y!r}) = [{a!r}, {b!r}]")
    a_lo = [fl(rng, -4, 4) for _ in range(150)]
    a_hi = [v + fl(rng, -12, -2) for v in a_lo]
    t_lo = [fl(rng, -4, 4, sign=pm(rng)) for _ in range(150)]
    t_hi = [v + fl(rng, -6, 2) for v in t_lo]
    lo, hi = fn((arr(a_lo), arr(a_hi)), (arr(t_lo), arr(t_hi)))             # boxes: the corners
    for i in range(150):
        mn, mx = corners(a_lo[i], a_hi[i], t_lo[i], t_hi[i])
        if not X(lo[i]) <= mn or not X(hi[i]) >= mx:
            out.append(f"times_positive(box {i})")
    return out, inexact


def check_square(fn):
    rng = random.Random(5)
    out, inexact = [], 0
    ys = [fl(rng, -30, 30, sign=pm(rng)) for _ in range(150)]
    lo, hi = fn((arr(ys), arr(ys)))
    for y, a, b in zip(ys, lo, hi, strict=True):
        e = Fraction(y) ** 2
        inexact += not exact64(e)
        if not X(a) <= e <= X(b):
            out.append(f"square({y!r}) = [{a!r}, {b!r}]")
    y_lo = [fl(rng, -6, 4, sign=pm(rng)) for _ in range(100)]
    y_hi = [v + fl(rng, -6, 4) for v in y_lo]
    lo, hi = fn((arr(y_lo), arr(y_hi)))
    for i in range(100):
        a, b = Fraction(y_lo[i]), Fraction(y_hi[i])
        mn = Fraction(0) if a <= 0 <= b else min(a * a, b * b)
        if not X(lo[i]) <= mn or not X(hi[i]) >= max(a * a, b * b):
            out.append(f"square(box {i})")
    return out, inexact


def check_rows(fn):
    rng = random.Random(6)
    out, inexact = [], 0
    for trial in range(12):
        M, N = rng.randrange(2, 10), rng.randrange(1, 8)
        lo = [[fl(rng, -30, 3, sign=pm(rng)) for _ in range(N)] for _ in range(M)]
        if trial % 3 == 0:
            hi = lo                                                        # point rows
        elif trial % 3 == 1:
            hi = [[v + fl(rng, -60, -20) for v in r] for r in lo]         # narrow boxes
        else:
            hi = [[max(v, 0.0) + fl(rng, -2, 3) for v in r] for r in lo]  # far ends: hi - lo does not round exactly
        e = fn((arr(lo), arr(hi)))
        for i in range(M):
            ends = [(Fraction(a), Fraction(b)) for a, b in zip(lo[i], hi[i], strict=True)]
            nm = sum((Fraction(0) if a <= 0 <= b else min(abs(a), abs(b))) ** 2 for a, b in ends)
            nM = sum(max(abs(a), abs(b)) ** 2 for a, b in ends)
            l1 = sum(abs(a) for a, _ in ends)
            dl1 = sum(b - a for a, b in ends)
            inexact += sum(not exact64(v) for v in (nm, nM, l1, dl1))
            if not (X(e.norm[0][i]) <= nm and X(e.norm[1][i]) >= nM and X(e.l1[i]) >= l1 and X(e.dl1[i]) >= dl1):
                out.append(f"rows(trial {trial}) row {i}")
    return out, inexact


def check_column(fn):
    rng = random.Random(7)
    out, inexact = [], 0
    for trial in range(30):
        k, N = rng.randrange(1, 6), rng.randrange(1, 7)
        t = [fl(rng, -3, 3, sign=pm(rng)) for _ in range(k)]
        a_lo = [[fl(rng, -12, 1, sign=pm(rng)) for _ in range(N)] for _ in range(k)]
        a_hi = a_lo if trial % 2 else [[v + fl(rng, -40, -2) for v in r] for r in a_lo]
        q_lo, q_hi = fn(arr(t), (arr(a_lo), arr(a_hi)))
        for n in range(N):
            ext = [corners(t[m], t[m], a_lo[m][n], a_hi[m][n]) for m in range(k)]
            mn, mx = sum(v for v, _ in ext), sum(v for _, v in ext)
            inexact += (not exact64(mn)) + (not exact64(mx))
            if not X(q_lo[n]) <= mn or not X(q_hi[n]) >= mx:
                out.append(f"column(trial {trial}) entry {n}")
    return out, inexact


def inner_family(rng, name, M=24):
    """A family of tight inputs for `inner`: (rows lo, rows hi, q_lo, q_hi), N = 1 unless noted. Each makes one of
    its bound's terms, or the sum of two, attain the exact extreme it bounds."""
    few = 12
    if name == "C":                                        # points: the dot product alone
        N = 4
        lo = [[fl(rng, -8, 2, sign=pm(rng)) for _ in range(N)] for _ in range(M)]
        q = [fl(rng, -8, 2, sign=pm(rng)) for _ in range(N)]
        return lo, lo, q, q
    if name in ("A+", "A-"):                               # phi in [0, a], q one-signed: dl1 * qabs attained
        a = [[fl(rng, -6, 4)] for _ in range(M)]
        b = fl(rng, -6, 2)
        cc = b + fl(rng, -6, 2)
        q = ([b], [cc]) if name == "A+" else ([-cc], [-b])
        return [[0.0]] * M, a, *q
    if name in ("Bt+", "Bt-"):          # p and r exact, their sum x * c (54 bits) not: the last rounding alone
        s = 1 if name.endswith("+") else -1
        x = [[fl(rng, -6, 4, few, sign=s)] for _ in range(M)]
        e = rng.randrange(-10, 0)
        b, w = fl(rng, e, e + 1, 41), fl(rng, e, e + 1, 41)
        return x, x, [b], [b + w]
    if name in ("B0+", "B0-", "B+", "B-"):                 # a point row, q a box: l1 * wmax attained
        s = 1 if name.endswith("+") else -1
        bits = few if name in ("B+", "B-") else 53
        x = [[fl(rng, -6, 4, bits, sign=s)] for _ in range(M)]
        b = 0.0 if name.startswith("B0") else fl(rng, -30, -6, bits)
        cc = b + fl(rng, -2, 4, bits)
        return x, x, [b], [cc]
    x = [fl(rng, 0, 4, few) for _ in range(M)]            # D0 and D: both radius terms attained at once
    a = [v * float(Fraction(1, 2 ** 35)) * fl(rng, 0, 1, few) for v in x]
    b = 0.0 if name == "D0" else fl(rng, -40, -10)
    cc = b + fl(rng, 0, 4, few)
    return [[v] for v in x], [[v + w] for v, w in zip(x, a, strict=True)], [b], [cc]


INNER_FAMILIES = ("A+", "A-", "B0+", "B0-", "B+", "B-", "Bt+", "Bt-", "C", "D0", "D")


def check_inner(fn):
    rng = random.Random(8)
    out, inexact = [], 0
    for name in INNER_FAMILIES:
        for _trial in range(6):
            lo, hi, q_lo, q_hi = inner_family(rng, name)
            e = c.rows((arr(lo), arr(hi)))
            y_lo, y_hi = fn(e, (arr(q_lo), arr(q_hi)))
            for i in range(len(lo)):
                ext = [corners(a, b, x, y) for a, b, x, y in zip(lo[i], hi[i], q_lo, q_hi, strict=True)]
                mn, mx = sum(v for v, _ in ext), sum(v for _, v in ext)
                inexact += (not exact64(mn)) + (not exact64(mx))
                if not X(y_lo[i]) <= mn or not X(y_hi[i]) >= mx:
                    out.append(f"inner(family {name}) row {i}")
    return out, inexact


def check_accumulate(fn):
    rng = random.Random(9)
    s = [fl(rng, -20, 2) for _ in range(150)]
    d = [fl(rng, -80, 0) for _ in range(150)]
    lo, hi = fn((arr(s), arr(s)), (arr(d), arr(d)))
    out, inexact = [], 0
    for x, y, a, b in zip(s, d, lo, hi, strict=True):
        e = Fraction(x) + Fraction(y)
        inexact += not exact64(e)
        if not X(a) <= e <= X(b):
            out.append(f"accumulate({x!r}, {y!r}) = [{a!r}, {b!r}]")
    return out, inexact


def gram_case(rng, family):
    """(q_prev, q_lo, q_hi) for `gram_terms`: full precision (the dots round), few bits in a narrow range (the dots
    are exact, so only the squares and sums round), a short q (G0's diagonal is near -1), a long one (above 0), a
    huge one (|q|^2 past 2^53, where |q|^2 - 1 rounds with G0's diagonal above 0), a wide box (q_hi - q_lo does not
    round exactly, so D's path rounds), or q_lo a unit vector (G0's diagonal exactly 0, and its column the first
    entries of q_prev, so the off-diagonal sum's rounding stands alone)."""
    k, N = rng.randrange(3 if family == "unit" else 1, 6), rng.randrange(2, 7)

    def entry():
        if family == "few":
            return fl(rng, -2, 0, 10, sign=pm(rng))
        e = {"full": (-4, 0), "short": (-14, -10), "long": (0, 2), "huge": (26, 28), "wide": (-40, -30)}.get(
            family, (-2, 0))
        return fl(rng, *e, sign=pm(rng))

    q_prev = [[entry() for _ in range(N)] for _ in range(k - 1)]
    q_lo = [entry() for _ in range(N)]
    if family == "unit":
        q_lo = [1.0] + [0.0] * (N - 1)
        for r in q_prev:
            e = rng.choice((0, -40))
            r[0] = fl(rng, e, e + 1, 20, sign=pm(rng))
    if family in ("few", "unit"):
        q_hi = [v + fl(rng, -12, -6, 10) for v in q_lo]
    elif family == "wide":
        q_hi = [fl(rng, -1, 1) for _ in q_lo]
    else:
        q_hi = [v + fl(rng, -50, -20) for v in q_lo]
    return q_prev, q_lo, q_hi


def check_gram_terms(fn):
    rng = random.Random(10)
    out, inexact = [], 0
    for family in ("full", "few", "short", "long", "huge", "wide", "unit"):
        for _ in range(40):
            q_prev, q_lo, q_hi = gram_case(rng, family)
            dg, dq, dd = fn([arr(v) for v in q_prev], (arr(q_lo), arr(q_hi)))
            Q = [[Fraction(v) for v in r] for r in q_prev + [q_lo]]
            ql = [Fraction(v) for v in q_lo]
            g = [sum(a * b for a, b in zip(r, ql, strict=True)) for r in Q]
            g[-1] -= 1
            e_dg = g[-1] ** 2 + 2 * sum(v * v for v in g[:-1])
            e_dq = sum(v * v for v in ql)
            e_dd = sum((Fraction(b) - Fraction(a)) ** 2 for a, b in zip(q_lo, q_hi, strict=True))
            inexact += sum(not exact64(v) for v in (e_dg, e_dq, e_dd))
            if not (X(dg) >= e_dg and X(dq) >= e_dq and X(dd) >= e_dd):
                out.append(f"gram_terms({family}, k={len(Q)})")
    return out, inexact


def check_gram_accumulate(fn):
    rng = random.Random(11)
    out, inexact = [], 0
    for _ in range(150):
        g = tuple(fl(rng, -60, 4) for _ in range(3))
        d = tuple(fl(rng, -110, -20) for _ in range(3))
        got = fn(g, d)
        for a, b, v in zip(g, d, got, strict=True):
            e = Fraction(a) + Fraction(b)
            inexact += not exact64(e)
            if not X(v) >= e:
                out.append(f"gram_accumulate({a!r} + {b!r}) = {v!r}")
    return out, inexact


def gram_bound_cases(rng):
    for _ in range(60):
        yield fl(rng, -100, 0), fl(rng, -2, 3), fl(rng, -110, -40)             # a roll's ranges
    for _ in range(40):
        yield fl(rng, -24, -16), fl(rng, -1, 1), fl(rng, -110, -100)           # G0's norm dominant
    for _ in range(40):
        yield fl(rng, -130, -120), fl(rng, 3, 5), fl(rng, -62, -58)            # the cross term dominant
    for _ in range(40):
        yield fl(rng, -130, -120), fl(rng, -110, -100), fl(rng, -6, -4)        # D's norm dominant
    for _ in range(60):                                    # verifier-P1's: k = 1, D parallel to q_lo, all squares
        G, x, d = fl(rng, -20, -8, 20), fl(rng, 0, 1, 20), fl(rng, -60, -40, 20)
        yield G * G, x * x, d * d


def check_gram_bound(fn):
    rng = random.Random(12)
    out, inexact = [], 0
    for g0, qf, df in gram_bound_cases(rng):
        F = fn((g0, qf, df))
        g0f, qff, dff = Fraction(g0), Fraction(qf), Fraction(df)
        exact = [sqrt_exact(v) for v in (g0f, qff * dff)]
        if None not in exact:
            f = exact[0] + 2 * exact[1] + dff
            inexact += not exact64(f)
        else:
            f = sqrt_floor(g0f) + 2 * sqrt_floor(qff * dff) + dff
            inexact += 1
        if not X(F) >= f:
            out.append(f"gram_bound({g0!r}, {qf!r}, {df!r}) = {F!r}")
    return out, inexact


def check_gram_factors(fn):
    rng = random.Random(13)
    out, inexact = [], 0
    Fs = [fl(rng, -60, -40) for _ in range(60)] + [fl(rng, -40, -10) for _ in range(60)]
    Fs += [fl(rng, -5, 0) for _ in range(60)] + [fl(rng, -30, -1, 20) for _ in range(30)]
    for F in Fs:
        lo, hi = fn(F)
        a, b = 1 / (1 + Fraction(F)), 1 / (1 - Fraction(F))
        inexact += (not exact64(a)) + (not exact64(b))
        if not X(lo) <= a or not X(hi) >= b:
            out.append(f"gram_factors({F!r}) = [{lo!r}, {hi!r}]")
    if fn(1.0) is not None or fn(1.5) is not None:
        out.append("gram_factors certified F >= 1")
    return out, inexact


def check_weights(fn):
    rng = random.Random(14)
    out, inexact = [], 0
    for family in ("full", "zero", "few"):
        n = [0.0 if family == "zero" else fl(rng, -4, 0) for _ in range(100)]
        bits = 20 if family == "few" else 53
        s = [fl(rng, -12, 0, bits) for _ in range(100)]
        g = [fl(rng, 0, 1, bits) for _ in range(100)]
        lo, hi = fn((arr(n), arr(n)), (arr(s), arr(s)), (arr(g), arr(g)))
        for i in range(100):
            e = Fraction(n[i]) - Fraction(s[i]) * Fraction(g[i])
            inexact += not exact64(e)
            if not X(lo[i]) <= e <= X(hi[i]):
                out.append(f"weights({family}) {i}")
    n_lo = [fl(rng, -4, 0) for _ in range(100)]
    n_hi = [v + fl(rng, -50, -40) for v in n_lo]
    s_lo = [fl(rng, -12, 0) for _ in range(100)]
    s_hi = [v + fl(rng, -50, -40) for v in s_lo]
    g_lo = [fl(rng, -1, 0) for _ in range(100)]
    g_hi = [v + fl(rng, -50, -40) for v in g_lo]
    lo, hi = fn((arr(n_lo), arr(n_hi)), (arr(s_lo), arr(s_hi)), (arr(g_lo), arr(g_hi)))
    for i in range(100):
        mn = Fraction(n_lo[i]) - Fraction(s_hi[i]) * Fraction(g_hi[i])
        mx = Fraction(n_hi[i]) - Fraction(s_lo[i]) * Fraction(g_lo[i])
        if not X(lo[i]) <= mn or not X(hi[i]) >= mx:
            out.append(f"weights(box {i})")
    return out, inexact


def check_boundaries(fn):
    rng = random.Random(15)
    out, inexact = [], 0
    for trial in range(30):
        M = rng.randrange(1, 40)
        if trial % 2:
            cl = [fl(rng, -60, 0) for _ in range(M)]
            ch = cl                                                         # point weights
        else:
            cl = [fl(rng, -40, 0, sign=pm(rng)) for _ in range(M)]          # some lower bounds below 0: raised
            ch = [max(v, 0.0) + fl(rng, -40, -2) for v in cl]
        b_lo, b_hi = fn((arr(cl), arr(ch)))
        lo_sum = hi_sum = Fraction(0)
        for i in range(M):
            lo_sum += max(Fraction(cl[i]), Fraction(0))
            hi_sum += Fraction(ch[i])
            inexact += (not exact64(lo_sum)) + (not exact64(hi_sum))
            if not X(b_lo[i]) <= lo_sum or not X(b_hi[i]) >= hi_sum:
                out.append(f"boundaries(trial {trial}) prefix {i}")
    return out, inexact


def check_target(fn):
    rng = random.Random(16)
    out, inexact = [], 0
    tau = Fraction(c.TAU)
    cases = [(fl(rng, -12, 0, 12), fl(rng, 0, 5, 12)) for _ in range(80)]           # exact products
    cases += [(fl(rng, -110, -90), fl(rng, -110, -90)) for _ in range(80)]          # TAU not negligible
    cases += [(fl(rng, -64, 0), fl(rng, 0, 5)) for _ in range(80)]                  # a roll's ranges
    for u, S in cases:
        lo, hi = fn((u, u), (np.float64(S), np.float64(S)))
        e = Fraction(u) * Fraction(S)
        inexact += (not exact64(e - tau)) + (not exact64(e + tau))
        if not X(lo) <= e - tau or not X(hi) >= e + tau:
            out.append(f"target({u!r}, {S!r}) = [{lo!r}, {hi!r}]")
    for _ in range(80):                                                             # intervals: their ends
        u_lo, S_lo = fl(rng, -30, 0), fl(rng, 0, 5)
        u_hi, S_hi = up(u_lo), S_lo + fl(rng, -40, -10)
        lo, hi = fn((u_lo, u_hi), (np.float64(S_lo), np.float64(S_hi)))
        if not X(lo) <= Fraction(u_lo) * Fraction(S_lo) - tau or not X(hi) >= Fraction(u_hi) * Fraction(S_hi) + tau:
            out.append(f"target(box {u_lo!r})")
    return out, inexact


def check_clearance(fn):
    rng = random.Random(17)
    out, inexact = [], 0
    for _ in range(150):
        K = rng.randrange(1, 6)
        b_lo = sorted(fl(rng, -40, 4) for _ in range(K))
        b_hi = [v + fl(rng, -50, -5) for v in b_lo]
        p = rng.randrange(0, K)
        base = b_hi[p - 1] if p else 0.0
        t_lo = base + fl(rng, -50, -5)
        t_hi = t_lo + fl(rng, -60, -5)
        clear, width = fn((np.float64(t_lo), np.float64(t_hi)), (arr(b_lo), arr(b_hi)), p)
        B_lo, B_hi, T_lo, T_hi = ([Fraction(v) for v in x] for x in (b_lo, b_hi, [t_lo], [t_hi]))
        e_clear = min([B_lo[p] - T_hi[0]] + ([T_lo[0] - B_hi[p - 1]] if p else []))
        e_width = max([T_hi[0] - T_lo[0], B_hi[p] - B_lo[p]] + ([B_hi[p - 1] - B_lo[p - 1]] if p else []))
        inexact += (not exact64(e_clear)) + (not exact64(e_width))
        if not X(clear) <= e_clear or not X(width) >= e_width:
            out.append(f"clearance(p={p})")
    return out, inexact


CHECKS = {
    "uniform_box": check_uniform_box, "sqrt_box": check_sqrt_box, "cospi_box": check_cospi_box,
    "sinpi_box": check_sinpi_box, "times_positive": check_times_positive, "square": check_square,
    "rows": check_rows, "column": check_column, "inner": check_inner, "accumulate": check_accumulate,
    "gram_terms": check_gram_terms, "gram_accumulate": check_gram_accumulate, "gram_bound": check_gram_bound,
    "gram_factors": check_gram_factors, "weights": check_weights, "boundaries": check_boundaries,
    "target": check_target, "clearance": check_clearance,
}


@pytest.mark.parametrize("step", sorted(CHECKS))
def test_each_step_lands_on_its_own_side_of_the_exact_value_on_tight_inputs(step):
    problems, inexact = CHECKS[step](getattr(c, step))
    assert problems == []
    assert inexact >= 60, f"only {inexact} of {step}'s exact values are not binary64: its inputs are not tight"


# ---------------------------------------------------------------------------------------------------------------
# The mutation gate.


def directed_sites():
    """(enclosing top-level definition, the `bd.<name>` attribute node) for every use of the bounds module."""
    for top in ast.parse(SOURCE).body:
        for node in ast.walk(top):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "bd":
                yield getattr(top, "name", "<module>"), node


SITES = list(directed_sites())


def twin(name):
    return name[:-2] + ("hi" if name.endswith("lo") else "lo")


def load(source):
    """A variant of certificate.py's source, loaded as a module of its own; its namespace."""
    ns = {"__name__": "quantum_film.pinned._certificate_mutant", "__package__": "quantum_film.pinned"}
    exec(compile(source, "certificate_mutant.py", "exec"), ns)              # a variant of our own file, nothing else
    return ns


def mutant(*nodes):
    """certificate.py with each given `bd.<name>` flipped to its twin, loaded as a module of its own."""
    lines = SOURCE.splitlines(keepends=True)
    for node in sorted(nodes, key=lambda n: (n.lineno, n.col_offset), reverse=True):
        line = lines[node.lineno - 1]
        assert line[node.col_offset:node.end_col_offset] == f"bd.{node.attr}"
        lines[node.lineno - 1] = line[:node.col_offset] + f"bd.{twin(node.attr)}" + line[node.end_col_offset:]
    return load("".join(lines))


def test_every_directed_call_is_in_a_step_that_has_a_check():
    assert SOURCE.isascii()
    assert len(SITES) >= 40
    assert sorted({name for name, _ in SITES}) == sorted(CHECKS.keys() - {"uniform_box"})
    assert all(node.attr.endswith(("_lo", "_hi")) for _, node in SITES)


@pytest.mark.parametrize("site", range(len(SITES)), ids=[f"{n}:{node.lineno}:{node.attr}" for n, node in SITES])
def test_each_directed_call_flipped_alone_fails_its_steps_check(site):
    name, node = SITES[site]
    problems, _ = CHECKS[name](mutant(node)[name])
    assert problems, f"bd.{node.attr} at line {node.lineno} flipped to bd.{twin(node.attr)}, and {name} still passes"


@pytest.mark.parametrize("step", sorted({name for name, _ in SITES}))
def test_every_directed_call_of_a_step_flipped_together_fails_its_check(step):
    problems, _ = CHECKS[step](mutant(*[n for name, n in SITES if name == step])[step])
    assert problems


# Roundings spelled past the source rule (verifier-P1's D3 kinds), each planted inside a step: the step's check sees
# each, without the rule. The rule refuses each as well (test_pinned_source_rule.py); here the behaviour is held.
RESPELLINGS = {
    "a Fraction converted by np.array with a positional dtype, in uniform_box": (
        "uniform_box", "    return bounds64(u)\n",
        "    return np.array(u, np.float64), np.array(u, np.float64)\n"),
    "numpy's own addition, in accumulate": (
        "accumulate", "    return bd.add_lo(s_lo, d_lo), bd.add_hi(s_hi, d_hi)\n",
        "    return s_lo + d_lo, bd.add_hi(s_hi, d_hi)\n"),
    "an integer past 2^53 in np.where, in boundaries": (
        "boundaries", "np.where(c_lo > 0, c_lo, 0.0)", "np.where(c_lo > 0, c_lo, 10000000000000001)"),
    "exact Fractions stored by slice assignment, in weights": (
        "weights", "    return bd.sub_lo(n_lo, bd.mul_hi(s_hi, g_hi)), bd.sub_hi(n_hi, bd.mul_lo(s_lo, g_lo))\n",
        "    lo = np.zeros(len(n_lo))\n"
        "    lo[:] = [Fraction(float(a)) - Fraction(float(b)) * Fraction(float(v))\n"
        "             for a, b, v in zip(n_lo, s_hi, g_hi)]\n"
        "    return lo, bd.sub_hi(n_hi, bd.mul_lo(s_lo, g_lo))\n"),
}


@pytest.mark.parametrize("name", sorted(RESPELLINGS))
def test_a_rounding_spelled_past_the_rule_inside_a_step_fails_its_check(name):
    step, old, new = RESPELLINGS[name]
    assert SOURCE.count(old) == 1
    problems, _ = CHECKS[step](load(SOURCE.replace(old, new))[step])
    assert problems, f"{name}: the step's check did not see it"


def test_the_uniforms_box_with_its_ends_swapped_fails_its_check():
    """verifier-P1's sixth fault: u's bounds swapped where the sampler called decide. The exact u now enters the
    certificate, and its box comes from this one step, whole."""
    problems, _ = check_uniform_box(lambda u: c.uniform_box(u)[::-1])
    assert problems


# ---------------------------------------------------------------------------------------------------------------
# The exact helpers, and TAU.


def test_locate_certifies_only_a_position_whose_boundaries_all_clear():
    b_lo = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
    b = (b_lo, b_lo + 0.01)
    for t, want in (((0.25, 0.26), 2), ((0.05, 0.06), 0), ((0.205, 0.215), None), ((0.52, 0.53), None),
                    ((0.305, 0.45), None), ((0.211, 0.29), 2)):
        found = c.locate(t, b)
        assert found.position == want and (found.position is None) == (found.reason is not None)


def test_locate_sees_an_overlapping_boundary_skipped():
    """The check above, against a planted locate that takes the first boundary clear above the target."""
    def first_clear_above(t, b):
        above = b[0] > t[1]
        return c.Located(np.argmax(above) if above.any() else None, None)
    b_lo = np.array([0.1, 0.2, 0.3])
    assert first_clear_above((0.205, 0.215), (b_lo, b_lo + 0.01)).position == 2
    assert c.locate((0.205, 0.215), (b_lo, b_lo + 0.01)).position is None


def test_holds_compares_exactly():
    x = (np.float64(0.5), np.float64(0.75))
    assert c.holds(x, Fraction(1, 2)) and c.holds(x, Fraction(3, 4))
    tiny = Fraction(1, 2 ** 80)
    assert not c.holds(x, Fraction(3, 4) + tiny) and not c.holds(x, Fraction(1, 2) - tiny)


def test_tau_is_2_to_the_minus_200_and_2_to_the_24_times_the_authoritys_margin():
    assert Fraction(c.TAU) == Fraction(1, 2 ** 200) == 2 ** 24 * mpf_fraction(fermi.margin())

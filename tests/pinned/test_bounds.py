"""The certificate's only arithmetic, held to exact rational arithmetic, and the check shown to see a wrong attribute.

The trap the brief names: a lower bound computed under the wrong rounding
attribute is almost always still a bound, off by one unit in the last place
at most, so an end-to-end comparison with the authority essentially never
sees it. So each bound is held BIT FOR BIT to the exact floor or ceiling of
its operation (for a reduction or a scan, to the same tree rounded down or up
node by node in rational arithmetic), where round-to-nearest differs in about
half of the inexact cases. cospi and sinpi are held the same way, to their
floor and ceiling from mpmath at 256 bits (the angles are irrational multiples
of pi's cosines, so no value is within 2^-200 of a binary64 number). The
planted tests swap LO, then HI, for round-to-nearest and show the check failing.

What may call these functions, and how, is tests/pinned/test_source_rule.py's.
"""
import random
from fractions import Fraction

import mpmath
import numpy as np
import pytest
from mpmath import mp

from quantum_film.pinned import bounds, cft
from quantum_film.pinned.cft import FP64, RDN, RUP
from quantum_film.pinned.encode import round_fraction, to_fraction


def floor64(x):
    return to_fraction(FP64, round_fraction(x, FP64, RDN))


def ceil64(x):
    return to_fraction(FP64, round_fraction(x, FP64, RUP))


def operands(seed, n=400):
    rng = np.random.default_rng(seed)
    x = np.concatenate([rng.standard_normal(n) * 10.0 ** rng.integers(-8, 8, n), [0.0, 1.0, -1.0, 5e-324]])
    y = np.concatenate([rng.standard_normal(n) * 10.0 ** rng.integers(-8, 8, n), [3.0, 3.0, 7.0, 0.5]])
    return x, y


def tree(leaves, rnd):
    def node(lo, hi):
        if hi - lo == 1:
            return leaves[lo]
        mid = lo + (1 << ((hi - lo - 1).bit_length() - 1))
        return to_fraction(FP64, round_fraction(node(lo, mid) + node(mid, hi), FP64, rnd))
    return node(0, len(leaves))


def problems():
    """Every way the bounds depart from exact directed rounding, on fixed operands. Empty when they are right."""
    out = []
    x, y = operands(1)
    F = [Fraction(float(v)) for v in x]
    G = [Fraction(float(v)) for v in y]
    exact_ops = {"add": (bounds.add_lo, bounds.add_hi, lambda a, b: a + b),
                 "sub": (bounds.sub_lo, bounds.sub_hi, lambda a, b: a - b),
                 "mul": (bounds.mul_lo, bounds.mul_hi, lambda a, b: a * b),
                 "div": (bounds.div_lo, bounds.div_hi, lambda a, b: a / b)}
    for name, (lo_fn, hi_fn, op) in exact_ops.items():
        lo, hi = lo_fn(x, y), hi_fn(x, y)
        for i, (a, b) in enumerate(zip(F, G, strict=True)):
            e = op(a, b)
            if Fraction(float(lo[i])) != floor64(e):
                out.append(f"{name}_lo[{i}]")
            if Fraction(float(hi[i])) != ceil64(e):
                out.append(f"{name}_hi[{i}]")
    ax = np.abs(x)
    for i, (lo, hi) in enumerate(zip(bounds.sqrt_lo(ax), bounds.sqrt_hi(ax), strict=True)):
        v, lo, hi = Fraction(float(ax[i])), Fraction(float(lo)), Fraction(float(hi))
        nxt = Fraction(float(np.nextafter(float(lo), np.inf)))
        prv = Fraction(float(np.nextafter(float(hi), -np.inf)))
        if not (lo * lo <= v < nxt * nxt):                     # lo is the largest binary64 whose square <= v
            out.append(f"sqrt_lo[{i}]")
        if not (hi * hi >= v > prv * prv or (hi == 0 and v == 0)):
            out.append(f"sqrt_hi[{i}]")
    rng = random.Random(4)
    for n in (1, 2, 3, 5, 16, 25, 31):
        k = rng.randrange(0, len(x) - n)
        a, b = x[k:k + n], y[k:k + n]
        for rnd, fn in ((RDN, bounds.dot_lo), (RUP, bounds.dot_hi)):
            leaves = [to_fraction(FP64, round_fraction(Fraction(float(p)) * Fraction(float(q)), FP64, rnd))
                      for p, q in zip(a, b, strict=True)]
            if Fraction(float(fn(a, b, n)[0])) != tree(leaves, rnd):
                out.append(f"dot {n} {rnd}")
        for rnd, fn in ((RDN, bounds.scan_lo), (RUP, bounds.scan_hi)):
            want = [Fraction(float(v)) for v in a]
            d = 1
            while d < n:
                want = want[:d] + [to_fraction(FP64, round_fraction(want[i] + want[i - d], FP64, rnd))
                                   for i in range(d, n)]
                d *= 2
            got = [Fraction(float(v)) for v in fn(a)]
            if got != want:
                out.append(f"scan {n} {rnd}")
    for L in (4, 8, 16, 32, 64):
        ang = np.array([2 * m / L for m in range(L)])            # dyadic, so exact in binary64
        for lo_fn, hi_fn, fn, name in ((bounds.cospi_lo, bounds.cospi_hi, mpmath.cospi, "cospi"),
                                       (bounds.sinpi_lo, bounds.sinpi_hi, mpmath.sinpi, "sinpi")):
            lo, hi = lo_fn(ang), hi_fn(ang)
            for i, x in enumerate(ang):
                with mp.workprec(256):
                    v = fn(mpmath.mpf(float(x)))
                    sign, man, exp, _bc = v._mpf_
                    e = (-1) ** sign * Fraction(man) * Fraction(2) ** exp if man else Fraction(0)
                if Fraction(float(lo[i])) != floor64(e):
                    out.append(f"{name}_lo L={L} m={i}")
                if Fraction(float(hi[i])) != ceil64(e):
                    out.append(f"{name}_hi L={L} m={i}")
    return out


def test_every_bound_is_the_exact_floor_or_ceiling_of_its_operation():
    assert problems() == []


def test_the_check_sees_a_lower_bound_rounded_to_nearest(monkeypatch):
    """The trap the brief names, planted: LO swapped for round-to-nearest. Every bound it touches is usually
    still a bound, and this check must say it is not the floor."""
    monkeypatch.setattr(bounds, "LO", cft.RNE)
    found = problems()
    assert any(p.startswith(("add_lo", "mul_lo", "div_lo")) for p in found)
    assert any(p.startswith("dot") for p in found) and any(p.startswith("scan") for p in found)
    assert any(p.startswith("cospi_lo") for p in found) and any(p.startswith("sinpi_lo") for p in found)


def test_the_check_sees_an_upper_bound_rounded_to_nearest(monkeypatch):
    monkeypatch.setattr(bounds, "HI", cft.RNE)
    found = problems()
    assert any(p.startswith(("add_hi", "mul_hi", "div_hi")) for p in found)
    assert any(p.startswith("cospi_hi") for p in found) and any(p.startswith("sinpi_hi") for p in found)


def test_bounds_refuse_an_operand_numpy_would_have_to_convert():
    with pytest.raises(TypeError, match="binary64"):
        bounds.add_lo(np.float32(1.0), 1.0)
    with pytest.raises(TypeError, match="binary64"):
        bounds.mul_hi(2, 1.0)

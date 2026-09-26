"""Exact rational <-> binary32/64/128 conversions, held to Python's correctly rounded division and to libcft."""
import random
from fractions import Fraction

import numpy as np
import pytest

from quantum_film.pinned import cft
from quantum_film.pinned.cft import FP32, FP64, FP128, RDN, RNE, RTZ, RUP
from quantum_film.pinned.encode import bounds64, exact, round_fraction, to_fraction


def fractions(seed, n=600):
    rng = random.Random(seed)
    out = [Fraction(0), Fraction(1, 3), Fraction(-2, 7), Fraction(1, 2 ** 1074), Fraction(3, 2 ** 1075),
           Fraction(2 ** 70 + 1, 2 ** 64), Fraction(1, 16) + Fraction(1, 5 * 2 ** 240)]
    for _ in range(n):
        p, q = rng.randrange(1, 2 ** rng.randrange(1, 90)), rng.randrange(1, 2 ** rng.randrange(1, 90))
        out.append(Fraction(p, q) * rng.choice((1, -1)))
    return out


def bits(fmt, enc):
    return int.from_bytes(np.asarray(enc).tobytes(), "little")


def test_round_to_nearest_binary64_is_pythons_correctly_rounded_int_division():
    for x in fractions(1):
        assert float(round_fraction(x, FP64, RNE)[0]) == x.numerator / x.denominator


@pytest.mark.parametrize("fmt", [FP32, FP64, FP128])
def test_directed_roundings_bracket_the_value_one_step_apart(fmt):
    for x in fractions(2):
        lo, hi = round_fraction(x, fmt, RDN), round_fraction(x, fmt, RUP)
        vlo, vhi = to_fraction(fmt, lo), to_fraction(fmt, hi)
        assert vlo <= x <= vhi
        if vlo == vhi:
            assert vlo == x
        else:
            assert abs(bits(fmt, hi) - bits(fmt, lo)) == 1           # adjacent encodings: nothing between them
        tz = to_fraction(fmt, round_fraction(x, fmt, RTZ))
        assert tz == (vlo if x >= 0 else vhi)
        near = to_fraction(fmt, round_fraction(x, fmt, RNE))
        assert near in (vlo, vhi) and abs(near - x) <= abs((vhi if near == vlo else vlo) - x)


@pytest.mark.parametrize("fmt", [FP32, FP128])
def test_the_narrow_and_the_wide_format_round_as_libcft_converts(fmt):
    rng = np.random.default_rng(5)
    xs = np.concatenate([rng.standard_normal(200), rng.standard_normal(50) * 1e-39, [0.0, 1.0, -0.75]])
    for rnd in (RNE, RDN, RUP):
        got = cft.convert(FP64, fmt, rnd, xs)
        want = np.concatenate([round_fraction(Fraction(float(x)), fmt, rnd) for x in xs])
        assert got.tobytes() == want.tobytes(), rnd


def test_exact_refuses_a_constant_that_would_round():
    assert to_fraction(FP64, exact(Fraction(2, 256), FP64)) == Fraction(1, 128)
    with pytest.raises(ValueError, match="not exactly representable"):
        exact(Fraction(1, 3), FP64)


def test_bounds64_are_floats_bracketing_the_value():
    lo, hi = bounds64(Fraction(1, 3))
    assert isinstance(lo, float) and Fraction(lo) < Fraction(1, 3) < Fraction(hi)
    assert bounds64(Fraction(1, 4)) == (0.25, 0.25)

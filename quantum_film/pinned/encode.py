"""Exact conversions between rationals and IEEE binary encodings, by integer arithmetic.

The uniforms are exact Fractions (quantum_film.golden.uniform), and a sampler
in a binary format needs them as encodings: rounded to nearest for the float
chain, and rounded DOWN and UP for the certificate's enclosure. Python's
integers are exact on every machine, so these conversions need no floating
point at all and give the same bits everywhere; tests/pinned holds them to
libcft's own conversions and to Python's correctly rounded int division.

    round_fraction(x, fmt, rnd)   the encoding of x rounded under rnd (RNE, RTZ, RDN, RUP)
    to_fraction(fmt, enc)         the exact value of one finite encoding
"""
from fractions import Fraction

import numpy as np

from .cft import FORMATS, FP32, FP64, FP128, RDN, RNE, RTZ, RUP

# (significand bits including the hidden one, exponent bits) per format.
LAYOUT = {FP32: (24, 8), FP64: (53, 11), FP128: (113, 15)}


def _layout(fmt):
    p, e = LAYOUT[fmt]
    bias = (1 << (e - 1)) - 1
    return p, e, bias, 1 - bias, bias          # precision, exponent bits, bias, emin, emax


def _floor_log2(num, den):
    """floor(log2(num / den)) for positive integers."""
    e = num.bit_length() - den.bit_length()
    if (num << max(-e, 0)) < (den << max(e, 0)):
        e -= 1
    return e


def _pack(fmt, sign, sig, ue):
    """The encoding of (-1)^sign * sig * 2^ue, sig < 2^p, already rounded."""
    p, e, bias, emin, emax = _layout(fmt)
    width = 1 + e + p - 1
    if sig == 0:
        bits = 0
    elif sig >= 1 << (p - 1):
        biased = ue + (p - 1) + bias
        if biased >= (1 << e) - 1:
            raise OverflowError(f"{sig} * 2^{ue} overflows {FORMATS[fmt][0]}")
        bits = (biased << (p - 1)) | (sig - (1 << (p - 1)))
    else:
        if ue != emin - (p - 1):
            raise AssertionError("a subnormal significand at a normal exponent")
        bits = sig
    bits |= sign << (width - 1)
    return np.frombuffer(bits.to_bytes(width // 8, "little"), dtype=FORMATS[fmt][1]).copy()


def round_fraction(x, fmt, rnd):
    """x (an int, Fraction or float, taken exactly) as a one-element array of fmt's encoding, rounded under rnd."""
    x = Fraction(x)
    if rnd not in (RNE, RTZ, RDN, RUP):
        raise ValueError(f"rounding attribute {rnd} is not one this module implements")
    sign = 1 if x < 0 else 0
    num, den = abs(x.numerator), x.denominator
    if num == 0:
        return _pack(fmt, 0, 0, 0)
    # On the magnitude, "down" means toward zero for a positive x and away from it for a negative one.
    away = (rnd == RUP and not sign) or (rnd == RDN and sign)
    p, _e, _bias, emin, _emax = _layout(fmt)
    ue = max(_floor_log2(num, den), emin) - (p - 1)
    n2, d2 = num << max(-ue, 0), den << max(ue, 0)
    sig, rem = divmod(n2, d2)
    if rem:
        if rnd == RNE:
            if 2 * rem > d2 or (2 * rem == d2 and sig & 1):
                sig += 1
        elif away:
            sig += 1
    if sig == 1 << p:                      # the rounding carried into a new binade
        sig >>= 1
        ue += 1
    return _pack(fmt, sign, sig, ue)


def to_fraction(fmt, enc):
    """The exact value of one finite encoding (an array element, or a one-element array)."""
    p, e, bias, emin, _emax = _layout(fmt)
    width = 1 + e + p - 1
    bits = int.from_bytes(np.asarray(enc, dtype=FORMATS[fmt][1]).reshape(-1)[:1].tobytes(), "little")
    sign = bits >> (width - 1)
    biased = (bits >> (p - 1)) & ((1 << e) - 1)
    frac = bits & ((1 << (p - 1)) - 1)
    if biased == (1 << e) - 1:
        raise ValueError("an infinity or a NaN has no exact rational value")
    if biased == 0:
        v = Fraction(frac) * Fraction(2) ** (emin - (p - 1))
    else:
        v = Fraction(frac + (1 << (p - 1))) * Fraction(2) ** (biased - bias - (p - 1))
    return -v if sign else v


def bounds64(x):
    """(the largest binary64 <= x, the smallest binary64 >= x), as Python floats."""
    return float(round_fraction(x, FP64, RDN)[0]), float(round_fraction(x, FP64, RUP)[0])


def exact(x, fmt):
    """x's encoding in fmt, refused unless x is representable exactly: a constant that must not round."""
    enc = round_fraction(x, fmt, RNE)
    if to_fraction(fmt, enc) != Fraction(x):
        raise ValueError(f"{x} is not exactly representable in {FORMATS[fmt][0]}")
    return enc


__all__ = ["round_fraction", "to_fraction", "bounds64", "exact", "FP32", "FP64", "FP128"]

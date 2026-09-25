"""Directed-rounding bounds at binary64: the only arithmetic the certificate does.

Each function returns a LOWER bound (name ending `_lo`) or an UPPER bound
(`_hi`) of the EXACT result of one operation on binary64 point values,
computed by libcft under roundTowardNegative or roundTowardPositive. The two
attributes are named once, as LO and HI below, and nothing else in the
certificate names a rounding attribute, so the question "was this bound
rounded the right way?" has one place to be answered.

WHY THEY ARE BOUNDS. Under roundTowardNegative a correctly rounded operation
returns the largest representable number at or below the exact result, and
under roundTowardPositive the smallest at or above it (IEEE 754-2019 4.3.2);
libcft's add, sub, mul, div and sqrt are correctly rounded under every
attribute. A reduction under LO rounds every product and every tree node
down, and rounding down is monotone, so by induction over the tree it is at
or below the exact sum of the exact products; the same holds up, under HI.
A scan is that argument applied to each prefix. No error analysis is needed,
and none is used: a bound here is a bound because of the attribute it was
rounded under, which is exactly why a wrong attribute is the fault to fear.
tests/pinned/test_bounds.py holds every function to exact rational arithmetic,
bit for bit where the operation is a single rounding, and shows that the same
check fails when LO is swapped for round-to-nearest.

Operands are binary64 point values (numpy float64 arrays or Python floats). A
scalar operand is broadcast by numpy, which moves bits and rounds nothing.
"""
import numpy as np

from . import cft

LO = cft.RDN
HI = cft.RUP
F = cft.FP64


def _f64(x):
    x = np.asarray(x)
    if x.dtype != np.float64:
        raise TypeError(f"a bound's operand must be binary64, not {x.dtype}: numpy would round the conversion")
    return x


def _pair(x, y):
    x, y = _f64(x), _f64(y)
    if x.shape == y.shape:
        return x.reshape(-1), y.reshape(-1)
    if x.ndim == 0:
        return np.full(y.size, x), y.reshape(-1)
    if y.ndim == 0:
        return x.reshape(-1), np.full(x.size, y)
    x, y = np.broadcast_arrays(x, y)
    return np.ascontiguousarray(x).reshape(-1), np.ascontiguousarray(y).reshape(-1)


def _shape(x, y):
    sx, sy = np.shape(x), np.shape(y)
    return sx if sx == sy or not sy else sy if not sx else np.broadcast_shapes(sx, sy)


def _out(r, shape):
    return r.reshape(shape) if shape else r[0]


def add_lo(x, y):
    return _out(cft.add(F, LO, *_pair(x, y)), _shape(x, y))


def add_hi(x, y):
    return _out(cft.add(F, HI, *_pair(x, y)), _shape(x, y))


def sub_lo(x, y):
    """A lower bound of x - y."""
    return _out(cft.sub(F, LO, *_pair(x, y)), _shape(x, y))


def sub_hi(x, y):
    return _out(cft.sub(F, HI, *_pair(x, y)), _shape(x, y))


def mul_lo(x, y):
    return _out(cft.mul(F, LO, *_pair(x, y)), _shape(x, y))


def mul_hi(x, y):
    return _out(cft.mul(F, HI, *_pair(x, y)), _shape(x, y))


def div_lo(x, y):
    return _out(cft.div(F, LO, *_pair(x, y)), _shape(x, y))


def div_hi(x, y):
    return _out(cft.div(F, HI, *_pair(x, y)), _shape(x, y))


def sqrt_lo(x):
    x = _f64(x)
    return _out(cft.sqrt(F, LO, x.reshape(-1)), x.shape)


def sqrt_hi(x):
    x = _f64(x)
    return _out(cft.sqrt(F, HI, x.reshape(-1)), x.shape)


def cospi_lo(x):
    """A lower bound of cos(pi * x): libcft's cospi is correctly rounded under every attribute."""
    return cft.cospi(F, LO, _f64(x).reshape(-1))


def cospi_hi(x):
    return cft.cospi(F, HI, _f64(x).reshape(-1))


def sinpi_lo(x):
    return cft.sinpi(F, LO, _f64(x).reshape(-1))


def sinpi_hi(x):
    return cft.sinpi(F, HI, _f64(x).reshape(-1))


def dot_lo(a, b, seg):
    """A lower bound of sum(a[i] * b[i]) over each segment of `seg` elements (cft_reduce_seg, CFT_DOT)."""
    return cft.reduce_seg(cft.DOT, F, LO, *_pair(a, b), seg)


def dot_hi(a, b, seg):
    return cft.reduce_seg(cft.DOT, F, HI, *_pair(a, b), seg)


def scan_lo(x):
    """Lower bounds of every prefix sum x[0] + ... + x[k] (a Hillis-Steele scan, every node rounded down)."""
    return _scan(_f64(x), LO)


def scan_hi(x):
    return _scan(_f64(x), HI)


def _scan(x, rnd):
    y = np.ascontiguousarray(x).copy()
    d = 1
    while d < len(y):
        nxt = y.copy()
        nxt[d:] = cft.add(F, rnd, y[d:], y[:-d])
        y = nxt
        d *= 2
    return y

"""The authority's basis, rebuilt on libcft: its columns as integers, and its values rounded to nearest.

golden.fermi.orbitals builds Phi column by column: the constant mode 1/sqrt(M),
then a cosine and a sine column for each pair {k, -k} of the Fermi disc, with
every angle reduced mod L as an integer before any trigonometry. The same
columns here are integers (`modes`); the certificate encloses their exact
values (quantum_film.pinned.certificate) and the plain chain rounds them to
nearest in one format (`basis`).
"""
from fractions import Fraction
from functools import lru_cache

import numpy as np

from ..stocks import fermi_disc
from . import cft
from .cft import FP32, FP64, FP128, RNE
from .encode import exact

FORMATS = {"fp32": FP32, "fp64": FP64, "fp128": FP128}


@lru_cache(maxsize=16)
def modes(L, r2):
    """Each column's kind (0 the constant mode, 1 a cosine, 2 a sine) and, per site i = x * L + y, the angle
    index m = (kx * x + ky * y) mod L of that column: golden.fermi.orbitals' columns, as integers."""
    if L < 1 or L & (L - 1):
        raise ValueError(f"the pinned path needs L a power of two, not {L}: its angles 2m/L must be dyadic, so "
                         f"that cospi and sinpi take them exactly")
    ks = fermi_disc(L, r2)
    reps, seen = [], set()
    for k in ks:
        if k in seen:
            continue
        seen.update({k, (-k[0], -k[1])})
        reps.append(k)
    xs, ys = np.repeat(np.arange(L), L), np.tile(np.arange(L), L)
    kinds, cols = [], []
    for kx, ky in reps:
        m = (kx * xs + ky * ys) % L
        if (kx, ky) == (0, 0):
            kinds.append(0)
            cols.append(np.zeros(L * L, dtype=np.int64))
        else:
            kinds += [1, 2]
            cols += [m, m]
    if len(kinds) != len(ks):
        raise AssertionError(f"basis has {len(kinds)} columns for {len(ks)} modes")
    return np.array(kinds), np.stack(cols, axis=1)


def angles(L, fmt):
    """2m/L for m < L, exact in every format (L is a power of two), as fmt's encodings."""
    return np.concatenate([exact(Fraction(2 * m, L), fmt) for m in range(L)])


def assemble(L, r2, one, table, dtype):
    """Phi from its values: `one` for the constant column, table[1][m] and table[2][m] for a cosine and a sine."""
    kinds, m = modes(L, r2)
    M, N = m.shape
    phi = np.empty((M, N), dtype=dtype)
    for n, kind in enumerate(kinds):
        phi[:, n] = np.repeat(one, M) if kind == 0 else table[kind][m[:, n]]
    return phi


@lru_cache(maxsize=16)
def basis(L, r2, fmt):
    """The basis rounded to nearest in `fmt`: RN(RN(sqrt(2/M)) * RN(cospi(2m/L))), and 1/L for the constant."""
    modes(L, r2)                                          # refuses a tile that is not a power of two, first
    M = L * L
    ang = angles(L, fmt)
    a = np.repeat(cft.sqrt(fmt, RNE, exact(Fraction(2, M), fmt)), L)
    table = {1: cft.mul(fmt, RNE, a, cft.cospi(fmt, RNE, ang)), 2: cft.mul(fmt, RNE, a, cft.sinpi(fmt, RNE, ang))}
    return assemble(L, r2, exact(Fraction(1, L), fmt), table, cft.dtype(fmt))

"""The certificate's only arithmetic, held to exact rational arithmetic, and the check shown to see a wrong attribute.

The trap the brief names: a lower bound computed under the wrong rounding
attribute is almost always still a bound, off by one unit in the last place
at most, so an end-to-end comparison with the authority essentially never
sees it. So each bound is held BIT FOR BIT to the exact floor or ceiling of
its operation (for a reduction or a scan, to the same tree rounded down or up
node by node in rational arithmetic), where round-to-nearest differs in about
half of the inexact cases. The last test swaps LO for round-to-nearest and
shows the same check failing.
"""
import ast
import inspect
import random
from fractions import Fraction

import numpy as np
import pytest

from quantum_film.pinned import bounds, certificate, cft
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
    ang = np.array([m / 8 for m in range(16)])
    for lo, hi, name in ((bounds.cospi_lo(ang), bounds.cospi_hi(ang), "cospi"),
                         (bounds.sinpi_lo(ang), bounds.sinpi_hi(ang), "sinpi")):
        for i in range(16):
            if not lo[i] <= hi[i] or (lo[i] == hi[i] and float(ang[i] * 2) != int(ang[i] * 2)):
                out.append(f"{name}[{i}]")                       # exact only at the half-integers (Niven)
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


def test_the_check_sees_an_upper_bound_rounded_to_nearest(monkeypatch):
    monkeypatch.setattr(bounds, "HI", cft.RNE)
    found = problems()
    assert any(p.startswith(("add_hi", "mul_hi", "div_hi")) for p in found)


def test_bounds_refuse_an_operand_numpy_would_have_to_convert():
    with pytest.raises(TypeError, match="binary64"):
        bounds.add_lo(np.float32(1.0), 1.0)
    with pytest.raises(TypeError, match="binary64"):
        bounds.mul_hi(2, 1.0)


def names_rounding(node):
    """Rounding attributes or direct libcft calls anywhere inside an AST node."""
    found = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in ("RNE", "RDN", "RUP", "RTZ", "RMM", "LO", "HI"):
            found.append(sub.id)
        if isinstance(sub, ast.Attribute) and sub.attr in ("RNE", "RDN", "RUP", "RTZ", "RMM"):
            found.append(sub.attr)
        if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name) and sub.value.id == "cft":
            found.append(f"cft.{sub.attr}")
    return found


def cft_imports(node):
    """What a module imports from quantum_film.pinned.cft, or the module itself."""
    out = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.ImportFrom) and (sub.module or "").split(".")[-1] == "cft":
            out += [a.name for a in sub.names]
        if isinstance(sub, ast.ImportFrom) and any(a.name == "cft" for a in sub.names):
            out.append("cft")
        if isinstance(sub, ast.Import) and any(a.name.split(".")[-1] == "cft" for a in sub.names):
            out.append("cft")
    return out


def test_the_certificate_names_no_rounding_attribute_and_calls_libcft_only_through_bounds():
    """Mechanically: quantum_film.pinned.certificate rounds only through quantum_film.pinned.bounds, where LO
    and HI are named once. From cft it may take the format constant FP64 and nothing else."""
    module = ast.parse(inspect.getsource(certificate))
    assert names_rounding(module) == []
    assert cft_imports(module) == ["FP64"]


def test_the_structural_check_sees_a_planted_attribute_and_a_planted_import():
    planted = ast.parse("class Certificate:\n    def f(self):\n        return cft.mul(FP64, RNE, 1.0, 2.0)\n")
    assert set(names_rounding(planted)) == {"cft.mul", "RNE"}
    assert cft_imports(ast.parse("from .cft import FP64, mul\nfrom . import cft\n")) == ["FP64", "mul", "cft"]

"""The certificate held to EXACT values: the basis to the authority's orbitals, the chain rule to exact Fractions.

The certificate claims to enclose the exact chain rule, so it is held to exact values, not to another float path.

- THE BASIS. Every entry of golden.fermi.orbitals (256 bits, within about 2^-256 of exact) must lie inside the
  certificate's basis enclosure, on both stocks. The planted fault: the cosine and sine tables swapped. Every row
  keeps its squared norm N/M, so the enclosure's own N/M check passes, and this one must not.
- THE CHAIN RULE, EXACTLY. On pauli-4x4, cos(2 pi m / 4) is 1, 0, -1 or 0, so the kernel is rational (entries
  k/16) and every weight, boundary and target of the chain rule is an exact Fraction. `exact_chain` computes them
  with rank-one Schur updates (an LDL^T factorisation, one column a draw), code that shares nothing with the
  authority's orbitals or projections, or with the certificate. The certified draws must be the exact chain rule's,
  and every exact boundary and target must lie inside the certificate's enclosures with NO slack at all. The
  planted fault: a target "enclosure" that is one rounded point, the product rounded down at both ends, which is
  exactly the slip an enclosure exists to prevent. The rolls stay right (no random target is that close to a
  boundary), so the equality gate cannot see it; this one must.

The lead's exact_draws (test_golden_premise.py in the golden stage's directory, on main since 5fe9741, after this
branch's base) is the same law by another route, Gaussian elimination; the two gave the same Fractions on 200 of
200 streams (P1.md, 2026-09-26).
"""
from fractions import Fraction

import numpy as np
import pytest

from quantum_film.golden import fermi
from quantum_film.golden.uniform import stream, uniform
from quantum_film.pinned import bounds as bd
from quantum_film.pinned import certificate, control, sampler
from quantum_film.stocks import fermi_disc

SLACK = Fraction(1, 2 ** 240)


@pytest.fixture
def fresh_enclosure():
    certificate.enclosure.cache_clear()
    yield
    certificate.enclosure.cache_clear()


def orbital_problems(L, r2):
    e = certificate.enclosure(L, r2)
    rows = fermi.orbitals(L, r2)
    out = []
    for i, row in enumerate(rows):
        for n, v in enumerate(row):
            x = control.mpf_fraction(v)
            if not Fraction(float(e.box[0][i, n])) - SLACK <= x <= Fraction(float(e.box[1][i, n])) + SLACK:
                out.append((i, n))
    return out


@pytest.mark.parametrize("L,r2", [(4, 1), (16, 8)])
def test_the_basis_enclosure_holds_every_orbital_of_the_authority(L, r2, fresh_enclosure):
    assert orbital_problems(L, r2) == []


def test_the_orbital_check_sees_the_cosine_and_sine_tables_swapped(monkeypatch, fresh_enclosure):
    cos_lo, cos_hi, sin_lo, sin_hi = bd.cospi_lo, bd.cospi_hi, bd.sinpi_lo, bd.sinpi_hi
    monkeypatch.setattr(bd, "cospi_lo", sin_lo)
    monkeypatch.setattr(bd, "cospi_hi", sin_hi)
    monkeypatch.setattr(bd, "sinpi_lo", cos_lo)
    monkeypatch.setattr(bd, "sinpi_hi", cos_hi)
    assert orbital_problems(16, 8)                    # the enclosure's own N/M check passes: each row keeps its norm


def exact_kernel(L=4, r2=1):
    """pauli-4x4's K as Fractions: K(x, y) = (1/M) sum over the disc of cos(2 pi k.(x - y) / L)."""
    cos = {0: 1, 1: 0, 2: -1, 3: 0}                              # cos(2 pi m / 4)
    ks = fermi_disc(L, r2)
    sites = [(x, y) for x in range(L) for y in range(L)]           # site index x * L + y
    return [[Fraction(sum(cos[(kx * (xa - xb) + ky * (ya - yb)) % L] for kx, ky in ks), L * L)
             for xb, yb in sites] for xa, ya in sites]


def exact_chain(s, uniform_fn=uniform):
    """The chain rule for pauli-4x4, exactly: (draws in order, [(target, boundaries) per draw]).
    After drawing site d with weight c_d, every weight loses w_i^2 / c_d, where w_i is K(i, d) less the earlier
    draws' components: an LDL^T factorisation of K on the drawn sites, one column a draw."""
    K = exact_kernel()
    M, N = len(K), len(fermi_disc(4, 1))
    c = [K[i][i] for i in range(M)]
    cols, order, seen = [], [], []                                  # cols: (w, pivot) per draw
    for j in range(N):
        untaken = [i for i in range(M) if i not in order]
        total = sum(c[i] for i in untaken)
        assert total == N - j and all(c[i] >= 0 for i in untaken), (j, total)
        target = uniform_fn(s, j) * total
        acc, bounds, chosen = Fraction(0), [], None
        for i in untaken:
            acc += c[i]
            bounds.append(acc)
            if target < acc:
                chosen = i
                break
        assert target != acc, "an exact tie: the authority would refuse this draw"
        order.append(chosen)
        seen.append((target, bounds))
        w = [K[i][chosen] - sum(wk[i] * wk[chosen] / pk for wk, pk in cols) for i in range(M)]
        pivot = c[chosen]
        assert w[chosen] == pivot
        cols.append((w, pivot))
        c = [ci - w[i] * w[i] / pivot for i, ci in enumerate(c)]
    return order, seen


def containment(s):
    """(certified draws, exact draws, values outside the certificate's enclosures), no slack."""
    order, seen = exact_chain(s)
    boxes = {}
    r = sampler.roll(4, 1, s, trace=lambda j, info: boxes.__setitem__(j, info))
    outside = []
    for j, (target, bounds) in enumerate(seen):
        (t_lo, t_hi), (b_lo, b_hi) = boxes[j]["target"], boxes[j]["bounds"]
        if not Fraction(float(t_lo)) <= target <= Fraction(float(t_hi)):
            outside.append((j, "target"))
        outside += [(j, k) for k, b in enumerate(bounds)
                    if not Fraction(float(b_lo[k])) <= b <= Fraction(float(b_hi[k]))]
    return r.draws, order, outside


def test_the_certified_rolls_are_the_exact_chain_rules_with_every_exact_value_enclosed_without_slack():
    for seed in range(1, 41):
        s = stream("roll", "pauli-4x4", seed)
        draws, order, outside = containment(s)
        assert draws == order and outside == [], seed
        assert fermi.sample(4, 1, s) == sorted(order), seed          # and the authority agrees with it


def test_the_exact_check_sees_a_target_enclosure_that_is_one_rounded_point(monkeypatch):
    def point(u, S):
        t = bd.mul_lo(u[0], S[0])
        return t, t
    monkeypatch.setattr(certificate, "target", point)
    draws, order, outside = containment(stream("roll", "pauli-4x4", 1))
    assert draws == order, "the plant is meant to leave the roll right: only containment can see it"
    assert any(k == "target" for _, k in outside)


def test_the_exact_reference_agrees_with_itself_on_a_planted_near_tie():
    """The reference on the control's planted stream: the exact chain rule decides the plant as the authority
    does, and differently from plain binary64 (the control's premise, from code the control does not use)."""
    s = stream("roll", "pauli-4x4", 1)
    pl = control.plant(4, 1, s)
    order, _ = exact_chain(s, pl.uniform_fn)
    assert sorted(order) == fermi.sample(4, 1, s, uniform_fn=pl.uniform_fn)
    assert sorted(order) != sampler.roll(4, 1, s, uniform_fn=pl.uniform_fn, certify=False).crystals
    assert np.array_equal(np.array(sorted(order)), np.array(sampler.roll(4, 1, s, uniform_fn=pl.uniform_fn).crystals))

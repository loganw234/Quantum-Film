"""The authority's refusals survive a hand-off: a draw refused AFTER the certificate handed the roll off is the
authority's TieRefusal, never the pinned path's own EnclosureBroken (verifier-P1's D1, 2026-09-26).

Each case plants two draws on a stream. Draw j0's target sits 2^-100 below the boundary it falls below: the authority
decides it, and no binary64 enclosure can clear it, so the certificate hands the roll off there. Draw j1 > j0's target
sits 2^-240 above or below the boundary it falls below: inside the authority's 2^-224 margin, so it refuses. Both
boundaries are the authority's own 256-bit values (its error, about 2^-249, is far below both distances), and the
plant at j0 keeps the same site, so the draws up to j1 are the stream's own.

The hand-off audit once compared the whole of the authority's draws with the certificate's, and every one of these
cases came back as EnclosureBroken (21 of 21, verifier-P1). Only the draws before the hand-off are the certificate's.
"""
from fractions import Fraction

import pytest

from quantum_film.golden import fermi
from quantum_film.golden.uniform import stream, uniform
from quantum_film.pinned import control, sampler

NEAR, TIE = Fraction(1, 2 ** 100), Fraction(1, 2 ** 240)


def planted(L, r2, s, j0, j1=None, side=1):
    """The stream's uniforms with draw j0 planted 2^-100 below its boundary and, if j1 is given, draw j1 planted
    2^-240 on `side` of its boundary. None when draw j1's boundary is the total, so that no u lies above it."""
    _crystals, order, seen = control.golden_draws(L, r2, s)
    N = len(order)
    u = {j0: (seen[j0][1][-1] - NEAR) / (N - j0)}
    if j1 is not None:
        bounds = seen[j1][1]
        B = bounds[-1]
        if abs(B - (N - j1)) < TIE and side > 0:          # the chosen site's boundary is the total
            if len(bounds) < 2 or bounds[-2] == 0:
                return None
            B = bounds[-2]
        u[j1] = (B + side * TIE) / (N - j1)
    if not all(0 <= v < 1 for v in u.values()):
        return None

    def fn(st, j):
        return u[j] if j in u else uniform(st, j)
    return fn


def pinned_positions(L, r2, s, fn):
    """The pinned roll (or its exception), and the certificate's position at each draw it saw (None: handed off)."""
    seen = {}
    try:
        out = sampler.roll(L, r2, s, uniform_fn=fn, trace=lambda j, info: seen.__setitem__(j, info["position"]))
    except (fermi.TieRefusal, sampler.EnclosureBroken) as e:
        out = e
    return out, seen


CASES = [("pauli-4x4", 4, 1, k, j0, j1, side) for k in range(3) for j0, j1 in ((0, 1), (0, 4), (1, 3), (2, 4))
         for side in (1, -1)]


@pytest.mark.parametrize("stock,L,r2,k,j0,j1,side", CASES)
def test_a_draw_refused_after_a_hand_off_is_the_authoritys_refusal(stock, L, r2, k, j0, j1, side):
    s = stream("p1-d1", stock, k)
    fn = planted(L, r2, s, j0, j1, side)
    if fn is None:
        fn = planted(L, r2, s, j0, j1, -side)          # the one plant with no u above its boundary: take the other side
    with pytest.raises(fermi.TieRefusal):
        fermi.sample(L, r2, s, uniform_fn=fn)
    out, positions = pinned_positions(L, r2, s, fn)
    assert isinstance(out, fermi.TieRefusal), f"the pinned path answered {out!r}"
    assert "refuses" in str(out)
    assert [positions[j] is None for j in range(j0 + 1)] == [False] * j0 + [True]   # handed off at j0, no later


@pytest.mark.parametrize("side", [1, -1])
def test_the_same_on_the_16x16_stock(side):
    s = stream("p1-d1", "pauli", 0)
    fn = planted(16, 8, s, 3, 20, side)
    with pytest.raises(fermi.TieRefusal):
        fermi.sample(16, 8, s, uniform_fn=fn)
    out, positions = pinned_positions(16, 8, s, fn)
    assert isinstance(out, fermi.TieRefusal), f"the pinned path answered {out!r}"
    assert positions[3] is None and all(positions[j] is not None for j in range(3))


@pytest.mark.parametrize("j0", [0, 2, 4])
def test_with_no_later_refusal_the_handed_off_roll_is_the_authoritys(j0):
    s = stream("p1-d1", "pauli-4x4", 7)
    fn = planted(4, 1, s, j0)
    r = sampler.roll(4, 1, s, uniform_fn=fn)
    assert r.handed_off and r.draw == j0 and r.crystals == fermi.sample(4, 1, s, uniform_fn=fn)

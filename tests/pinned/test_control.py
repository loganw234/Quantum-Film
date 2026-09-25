"""The negative control the brief names, and planted targets straddling the certificate's reach.

The control: on a planted near-tie stream, the certified sampler with its
hand-off removed must DISAGREE with the authority, and the shipped sampler
must AGREE with it on the same stream. quantum_film.pinned.control says how
the plant is made: inside binary64's own error at the planted boundary, since
a plant at 1e-14 relative (the brief's figure) is decided correctly by plain
binary64 and could not make the control fail (P1.md, 2026-09-25).
"""
from fractions import Fraction

import pytest

from quantum_film.golden.uniform import stream
from quantum_film.pinned import control
from quantum_film.stocks import params


@pytest.mark.parametrize("stock,seed", [("pauli-4x4", 1), ("pauli-4x4", 2), ("pauli-4x4", 3), ("pauli", 1)])
def test_without_the_hand_off_a_planted_near_tie_disagrees_and_with_it_the_roll_is_the_authoritys(stock, seed):
    law = params(stock)
    c = control.control(law["L"], law["fermi_r2"], stream("roll", stock, seed))
    pl, without, shipped = c["plant"], c["without_handoff"], c["with_handoff"]
    assert Fraction(1, 2 ** 200) < pl.distance, "the plant must be a draw the authority decides, not refuses"
    assert pl.distance < Fraction(c["enclosure_widths"]["boundary"]), "the plant must be inside the enclosure"
    assert without.uncertified == [pl.draw]
    assert c["without_handoff_disagrees"], "THE CONTROL COULD NOT FAIL: binary64 decided the plant as the authority"
    assert c["with_handoff_agrees"]
    assert shipped.handed_off and shipped.draw == pl.draw and shipped.draws[:pl.draw] == without.draws[:pl.draw]
    assert c["plain_fp64"].crystals == without.crystals          # with the hand-off removed it is plain binary64


@pytest.mark.parametrize("seed,j", [(1, None), (4, 2)])
def test_planted_targets_either_side_of_a_boundary_are_the_authoritys_at_every_distance(seed, j):
    distances = [Fraction(1, 10 ** k) for k in (6, 9, 12, 13, 14, 15, 16, 17)]
    rows = control.ladder(4, 1, stream("roll", "pauli-4x4", seed), distances, j=j)
    assert len(rows) == 2 * len(distances)
    for r in rows:
        assert r["certified"] == r["authority"], (r["distance"], r["side"])
    assert any(not r["handed_off"] for r in rows) and any(r["handed_off"] for r in rows), \
        "the family must straddle the certificate's reach: some plants certified, some handed off"

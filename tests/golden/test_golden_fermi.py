"""The authority for the Pauli law: normalisation, projection, reproducibility, and the tie refusal."""
from fractions import Fraction

import mpmath
import pytest
from mpmath import mp

from quantum_film.golden import fermi
from quantum_film.golden.uniform import stream, uniform


def test_the_layout_probabilities_sum_to_one():
    total = fermi.total_probability(4, 1, prec=96)
    assert abs(total - 1) < mpmath.mpf(2) ** -80


def test_the_normalisation_check_can_fail(monkeypatch):
    """Negative control: a basis that is not orthonormal (every row scaled by
    1.01) is not a projection DPP, and the same check must see it."""
    real = fermi.orbitals

    def scaled(L, r2, prec=fermi.PREC):
        with mp.workprec(prec):
            return [[v * mpmath.mpf("1.01") for v in row] for row in real(L, r2, prec)]

    monkeypatch.setattr(fermi, "orbitals", scaled)
    assert abs(fermi.total_probability(4, 1, prec=96) - 1) > mpmath.mpf("1e-3")


@pytest.mark.parametrize("L,r2", [(4, 1), (16, 8)])
def test_the_basis_is_orthonormal_and_the_kernel_diagonal_is_n_over_m(L, r2):
    prec = 128
    rows = fermi.orbitals(L, r2, prec)
    M, N = len(rows), len(rows[0])
    tol = mpmath.mpf(2) ** -(prec - 12)
    with mp.workprec(prec):
        for a in range(N):
            for b in range(a, N):
                g = mpmath.fsum(rows[i][a] * rows[i][b] for i in range(M))
                assert abs(g - (1 if a == b else 0)) < tol, (a, b)
        for r in rows:
            assert abs(mpmath.fsum(v * v for v in r) - mpmath.mpf(N) / M) < tol


def test_a_roll_is_n_distinct_sites_and_the_same_stream_lays_the_same_roll():
    for seed in range(1, 6):
        s = stream("roll", "pauli-4x4", seed)
        y = fermi.sample(4, 1, s)
        assert y == sorted(set(y)) and len(y) == 5 and 0 <= y[0] and y[-1] < 16
        assert fermi.sample(4, 1, s) == y
    assert len({tuple(fermi.sample(4, 1, stream("roll", "pauli-4x4", k))) for k in range(1, 9)}) > 1


# The margin's premise (the arithmetic's error is far below the margin) is
# measured in tests/golden/test_golden_premise.py, against references that
# share no code with the authority. It was first measured here, against the
# authority itself at 512 bits, which could not see an error that does not
# scale with the precision (the P0 verifier, 2026-09-25).


def planted(delta):
    """Every site of the 4x4 tile starts with c_i = N/M = 5/16 and the total is
    N = 5, so u = 1/16 + delta/5 puts the first target delta past the boundary
    after site 0."""
    def uniform_fn(_stream, j):
        return Fraction(1, 16) + Fraction(delta) / 5 if j == 0 else uniform(b"planted", j)
    return uniform_fn


def test_a_target_inside_the_margin_is_refused_though_rounding_could_not_move_it():
    """2^-240 past the boundary: inside the margin (2^-224), and far above the
    arithmetic's error (about 2^-249). An exact tie cannot tell a margin that is
    too small from a right one; this can. A margin below the arithmetic's own
    error, or none, lets this draw be decided."""
    with pytest.raises(fermi.TieRefusal, match="refuses"):
        fermi.sample(4, 1, b"near-tie", uniform_fn=planted(Fraction(1, 2 ** 240)))


def test_a_target_outside_the_margin_is_decided_and_goes_past_the_boundary():
    firsts = []
    roll = fermi.sample(4, 1, b"clear", uniform_fn=planted(Fraction(1, 2 ** 200)),
                        trace=lambda j, target, bounds: firsts.append(len(bounds)) if j == 0 else None)
    assert firsts == [2] and 1 in roll                   # site 0's interval was passed; site 1 was laid


def test_a_precision_changed_under_a_draw_is_refused_by_name():
    """mpmath's precision is process-global (verifier-P0 11c). This stands in
    for another thread: the uniform for draw 1 drops it to binary64."""
    def meddling(s, j):
        if j == 1:
            mp.prec = 53
        return uniform(s, j)

    with pytest.raises(fermi.PrecisionChanged, match="53 bits, not 256"):
        fermi.sample(4, 1, b"threads", uniform_fn=meddling)


def test_a_draw_on_a_boundary_is_refused_not_rounded():
    """Every site of the 4x4 tile starts with c_i = N/M = 5/16, so a uniform of
    exactly 1/16 puts the first target on the boundary after site 0. The
    authority must refuse that draw by name, never choose it by rounding."""
    def on_the_boundary(_stream, j):
        return Fraction(1, 16) if j == 0 else Fraction(1, 3)

    with pytest.raises(fermi.TieRefusal, match="refuses"):
        fermi.sample(4, 1, b"tie", uniform_fn=on_the_boundary)


def test_a_uniform_that_is_not_an_exact_fraction_is_refused():
    with pytest.raises(ValueError, match="exact Fraction"):
        fermi.sample(4, 1, b"x", uniform_fn=lambda _s, _j: 0.5)


def test_a_basis_built_while_the_precision_moved_is_refused_and_never_cached(monkeypatch):
    """verifier-P0's re-check: orbitals() is cached, and a basis built while
    another thread held 53 bits served every later roll with no refusal. This
    stands in for that thread: the first cosine drops the precision."""
    real_cos = mpmath.cos

    def meddling(x):
        mp.prec = 53
        return real_cos(x)

    fermi.orbitals.cache_clear()
    monkeypatch.setattr(mpmath, "cos", meddling)
    with pytest.raises(fermi.PrecisionChanged, match="the basis: mpmath's working precision is 53 bits"):
        fermi.orbitals(4, 1, 200)
    monkeypatch.undo()
    assert fermi.orbitals.cache_info().currsize == 0
    rows = fermi.orbitals(4, 1, 200)                      # built again, cleanly
    with mp.workprec(200):
        assert abs(mpmath.fsum(v * v for v in rows[0]) - mpmath.mpf(5) / 16) < mpmath.mpf(2) ** -190


def test_a_target_just_below_a_boundary_is_refused_too():
    """The mirror of the 2^-240 plant above. A margin checked only on one side,
    or checked after the choice is made, decides this draw; every other gate
    passed such a reordering (the P0 verifier's third pass)."""
    with pytest.raises(fermi.TieRefusal, match="refuses"):
        fermi.sample(4, 1, b"near-tie-below", uniform_fn=planted(-Fraction(1, 2 ** 240)))


def test_a_basis_whose_rows_are_not_n_over_m_is_refused_before_it_is_cached(monkeypatch):
    """A transient precision drop in another thread can come and go between
    two checks, and the P0 verifier cached a corrupted 16x16 basis 26 times in
    40 that way. So the basis's content is checked too: every row's squared
    norm is N/M. This stands in for a drop that the precision check misses."""
    real_sqrt = mpmath.sqrt

    def coarse(x):
        return real_sqrt(mpmath.mpf(float(x)))           # a binary64 value, returned at full precision

    fermi.orbitals.cache_clear()
    monkeypatch.setattr(mpmath, "sqrt", coarse)
    with pytest.raises(fermi.PrecisionChanged, match="the basis: its rows"):
        fermi.orbitals(6, 1, 192)
    monkeypatch.undo()
    assert fermi.orbitals.cache_info().currsize == 0

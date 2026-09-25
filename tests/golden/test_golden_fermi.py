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


def traced(seed, prec):
    draws = []
    roll = fermi.sample(16, 8, stream("roll", "pauli", seed), prec=prec,
                        trace=lambda j, target, bounds: draws.append((target, bounds)))
    return roll, draws


def test_the_margin_dwarfs_the_arithmetic_error_along_real_rolls():
    """The premise of the contract's central argument (docs/DETERMINISM.md): the
    256-bit arithmetic's error in every boundary and every target is far below
    the refusal margin. Measured against the same rolls at 512 bits, draw by
    draw. The P0 verifier measured the error at up to 2^-248.8 against a margin
    of 2^-224, a headroom of about 2^23; this gate demands 2^16.

    It replaces a test that compared rolls at 256 and 320 bits and could not
    fail: random seeds come no closer than about 2^-15 to a boundary, so the
    rolls agreed with the refusal removed, and with a margin below the
    arithmetic's own error (verifier-P0 item 2)."""
    worst = mpmath.mpf(0)
    for seed in range(1, 5):
        roll, draws = traced(seed, 256)
        again, exact = traced(seed, 512)
        assert roll == again, seed
        with mp.workprec(512):
            for (t, bs), (t2, bs2) in zip(draws, exact, strict=True):
                worst = max([worst, abs(t - t2)] + [abs(a - b) for a, b in zip(bs, bs2, strict=True)])
    headroom = fermi.margin(256) / worst
    log2 = lambda x: float(mpmath.log(x, 2))  # noqa: E731
    assert headroom > 2 ** 16, f"error 2^{log2(worst):.1f}, headroom 2^{log2(headroom):.1f}"


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

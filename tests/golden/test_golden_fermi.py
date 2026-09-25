"""The authority for the Pauli law: normalisation, projection, reproducibility, and the tie refusal."""
from fractions import Fraction

import mpmath
import pytest
from mpmath import mp

from quantum_film.golden import fermi
from quantum_film.golden.uniform import stream


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


def test_the_working_precision_does_not_decide_the_roll():
    """The contract's central argument (docs/DETERMINISM.md): a draw is decided
    only when its target is at least 2^-(prec-32) from every boundary, far above
    the arithmetic's own error, and anything closer is refused. So 256 and 320
    bits must lay the same rolls. If they ever differ, the argument is wrong."""
    for seed in range(1, 5):
        s = stream("roll", "pauli", seed)
        assert fermi.sample(16, 8, s, prec=256) == fermi.sample(16, 8, s, prec=320), seed


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

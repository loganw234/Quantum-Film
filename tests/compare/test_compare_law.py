"""The comparison's exact law and its perfect sampler, held to the authority (quantum_film.golden), never to
another float path: the integer kernel to fermi's 256-bit kernel, the weights to det(K_Y), the zeros to the 1,360
forbidden layouts, and the sampler's inverse CDF to the weights on every possible target."""
import itertools
import math
from fractions import Fraction

import mpmath
import numpy as np
import pytest

from quantum_film import compare
from quantum_film.atlas import pauli_tile
from quantum_film.golden import fermi
from quantum_film.golden.uniform import stream, uniform


@pytest.fixture(scope="module")
def law():
    return compare.exact_law("pauli-4x4")


def test_the_integer_kernel_over_16_is_the_authoritys_kernel():
    """K = A / 16 entry by entry, against the authority's kernel at 256 bits: exact up to its own precision."""
    A = compare.integer_kernel("pauli-4x4")
    K = fermi.kernel(4, 1)
    with mpmath.mp.workprec(256):
        worst = max(abs(K[i][j] - mpmath.mpf(A[i][j]) / 16) for i in range(16) for j in range(16))
    assert worst < mpmath.mpf(2) ** -200
    assert A[0][0] == 5 and all(A[i][j] == A[j][i] for i in range(16) for j in range(16))


def test_the_weights_are_the_authoritys_determinants(law):
    """P(Y) = w / 4096 with w in {0, 1, 4, 9}; it is det(K_Y) to binary64 for all 4,368 layouts, and the zeros are
    exactly pauli_tile.law_of's 1,360 forbidden layouts."""
    layouts, weights, den = law
    K, forbidden, dets = pauli_tile.law_of("pauli-4x4")
    assert layouts == tuple(itertools.combinations(range(16), 5)) and len(layouts) == 4368
    assert den == 4096 and sum(weights) == den and set(weights) == {0, 1, 4, 9}
    assert {Y for Y, w in zip(layouts, weights, strict=True) if w == 0} == set(forbidden)
    assert len(forbidden) == 1360
    assert max(abs(w / den - dets[Y]) for Y, w in zip(layouts, weights, strict=True)) < 1e-15


def test_some_weights_against_the_authoritys_own_determinant(law):
    """A spread of layouts, each det(K_Y) taken from the authority (fermi.probability, 256 bits)."""
    layouts, weights, den = law
    rows = fermi.orbitals(4, 1)
    for i in range(0, 4368, 97):
        with mpmath.mp.workprec(256):
            d = fermi.probability(rows, layouts[i])
            assert abs(d - mpmath.mpf(weights[i]) / den) < mpmath.mpf(2) ** -200, layouts[i]


def test_probability_reads_the_table(law):
    layouts, weights, den = law
    assert compare.probability((0, 1, 2, 4, 8)) == Fraction(weights[layouts.index((0, 1, 2, 4, 8))], den)
    assert compare.probability((0, 1)) == 0 and compare.probability(()) == 0


def test_a_stock_whose_cosines_are_not_integers_is_refused_by_name():
    with pytest.raises(LookupError, match="exact here only"):
        compare.exact_law("pauli")
    with pytest.raises(LookupError, match="exact here only"):
        compare.exact_law("poisson")


def test_the_golden_words_are_the_golden_uniforms():
    """uniform_words is golden.uniform at speed: word i / 2^64 is uniform(stream, i), exactly."""
    parts = ("compare-floor", "pauli-4x4", 4096, 3)
    words = compare.uniform_words(parts, 300)
    for i in (*range(20), 299):
        assert Fraction(int(words[i]), 1 << 64) == uniform(stream(*parts), i)


def test_the_inverse_cdf_lays_each_layout_exactly_its_weight(law):
    """Every one of the 4,096 targets, once: each layout is picked exactly w times, a forbidden one never.
    So a uniform target makes the sampler the law, exactly."""
    layouts, weights, den = law
    picked = np.bincount(compare.pick(np.arange(den)), minlength=len(layouts))
    assert picked.tolist() == list(weights)


def test_the_draws_use_the_top_bits_of_each_word():
    parts = ("compare-test-draws", 1)
    words = compare.uniform_words(parts, 50)
    by_hand = compare.pick([int(w) >> 52 for w in words])
    assert compare.law_draws(50, parts).tolist() == by_hand.tolist()


def test_a_perfect_samplers_draws_follow_the_law():
    """40,960 draws: no forbidden layout, and the chi-square of the four weight classes is ordinary."""
    layouts, weights, den = compare.exact_law()
    c = np.bincount(compare.law_draws(40960, ("compare-test-chi2",)), minlength=len(layouts))
    W = np.array(weights)
    assert int(c[W == 0].sum()) == 0
    chi2 = 0.0
    for w in (1, 4, 9):
        expected = 40960 * int(W[W == w].sum()) / den
        chi2 += (int(c[W == w].sum()) - expected) ** 2 / expected
    assert chi2 < 13.8                       # chi-square with 2 dof: p = 0.001


def test_the_floor_is_exact_and_deterministic():
    """The floor is a function of n alone: the same replicas twice, exact rationals, the percentile by nearest
    rank (190 of 200), and the mean between the least and the upper value."""
    a = compare.floor_replicas(512)
    assert a == compare._floor_replicas.__wrapped__(512, "pauli-4x4", 200) and len(a) == 200    # uncached
    assert all(isinstance(v, Fraction) for v in a) and list(a) == sorted(a)
    f = compare.tvd_floor(512)
    assert f["upper"] == float(a[189]) and f["max"] == float(a[-1]) and f["percentile"] == 95
    assert float(a[0]) < f["mean"] < f["upper"] <= f["max"]
    assert f["exact"]["upper"] == str(a[189])


def test_a_replicas_tvd_is_the_tvd_of_its_counts():
    """Replica 0 at n = 300, re-counted by hand in Fractions."""
    layouts, weights, den = compare.exact_law()
    idx = compare.law_draws(300, ("compare-floor", "pauli-4x4", 300, 0))
    counts = {}
    for i in idx.tolist():
        counts[layouts[i]] = counts.get(layouts[i], 0) + 1
    by_hand = sum((abs(Fraction(counts.get(Y, 0), 300) - Fraction(w, den))
                   for Y, w in zip(layouts, weights, strict=True)), Fraction(0)) / 2
    assert by_hand in compare.floor_replicas(300)


def test_the_floor_falls_as_the_shots_grow():
    means = [compare.tvd_floor(n)["mean"] for n in (512, 1024, 4096)]
    assert means == sorted(means, reverse=True) and not math.isclose(means[0], means[-1])
    for bad in (0, -5, 2.0, True):
        with pytest.raises(ValueError, match="positive whole number"):
            compare.floor_replicas(bad)

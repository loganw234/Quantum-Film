"""The authority samples the law it claims: its rolls reproduce det(K)'s statistics.

Everything else in golden/ checks the kernel, or the sampler's mechanics. This
checks the claim itself: over many rolls of the 4x4 tile, the one-site and
pair frequencies match K_ii and K_ii K_jj - K_ij^2. The statistic is a
chi-square over all 16 + 120 frequencies. Pair frequencies are correlated, so
chi^2/dof is used as a measurement with a generous bound, not as an exact test.

The control is the Poisson sampler, which lays the same number of crystals
uniformly. It must FAIL the same check: if it passed, the check could not
tell a repulsive law from a uniform one.
"""
import itertools

import pytest

from quantum_film.golden import binomial, fermi
from quantum_film.golden.uniform import stream

L, R2, M, N = 4, 1, 16, 5
ROLLS = 2000


@pytest.fixture(scope="module")
def exact():
    K = [[float(v) for v in row] for row in fermi.kernel(L, R2, prec=128)]
    one = [K[i][i] for i in range(M)]
    two = {(i, j): K[i][i] * K[j][j] - K[i][j] ** 2 for i, j in itertools.combinations(range(M), 2)}
    return one, two


def chi2_per_dof(rolls, exact):
    one, two = exact
    n = len(rolls)
    c1 = [0] * M
    c2 = dict.fromkeys(two, 0)
    for y in rolls:
        for i in y:
            c1[i] += 1
        for pair in itertools.combinations(y, 2):
            c2[pair] += 1
    chi2 = sum((c1[i] - n * one[i]) ** 2 / (n * one[i] * (1 - one[i])) for i in range(M))
    chi2 += sum((c2[p] - n * q) ** 2 / (n * q * (1 - q)) for p, q in two.items())
    return chi2 / (M + len(two))


@pytest.fixture(scope="module")
def golden_rolls():
    return [fermi.sample(L, R2, stream("law-check", "pauli-4x4", k)) for k in range(ROLLS)]


def test_the_golden_rolls_reproduce_the_determinantal_law(golden_rolls, exact):
    assert chi2_per_dof(golden_rolls, exact) < 1.6


def test_uniform_rolls_fail_the_same_check(exact):
    uniform_rolls = [binomial.sample(M, N, stream("law-check", "poisson", k)) for k in range(ROLLS)]
    assert chi2_per_dof(uniform_rolls, exact) > 2.5

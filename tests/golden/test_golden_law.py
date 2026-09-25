"""The authority samples the law it claims: its rolls reproduce det(K)'s statistics.

Everything else in golden/ checks the kernel, or the sampler's mechanics. This
checks the claim itself, on 2,000 rolls of the 4x4 tile, with two statistics:

  1. FORBIDDEN LAYOUTS. 1,360 of the tile's 4,368 five-site layouts have
     det(K_Y) = 0: the law never lays them. Not one roll may land on one.
  2. CHI-SQUARE. The one-site and pair frequencies match K_ii and
     K_ii K_jj - K_ij^2, over all 16 + 120 of them. Pair frequencies are
     correlated, so chi^2/dof is used as a measurement with a generous bound,
     not as an exact test. Under the true law it exceeds 1.6 about 0.7% of
     the time (the P0 verifier measured its null distribution); the streams
     are fixed, so the test is deterministic.

The chi-square alone could not see a partial defect: a sampler that skips one
projection update scores 1.203 and passes it, while laying forbidden layouts
in 18% of its rolls (verifier-P0, 2026-09-25). So the gate is held to planted
sampler bugs here, in a float copy of the chain rule that first has to lay
the authority's own 2,000 rolls exactly. The uniform Poisson sampler is the
third control.
"""
import itertools
import math

import numpy as np
import pytest

from quantum_film.golden import binomial, fermi
from quantum_film.golden.uniform import stream, uniform

L, R2, M, N = 4, 1, 16, 5
ROLLS = 2000
FORBIDDEN_BELOW = 1e-9     # measured: allowed det(K_Y) >= 2.4e-4; forbidden |det| <= 6.5e-19


@pytest.fixture(scope="module")
def kernel():
    return np.array([[float(v) for v in row] for row in fermi.kernel(L, R2, prec=128)])


@pytest.fixture(scope="module")
def forbidden(kernel):
    dets = {Y: np.linalg.det(kernel[np.ix_(Y, Y)]) for Y in itertools.combinations(range(M), N)}
    allowed = min(d for d in dets.values() if d > FORBIDDEN_BELOW)
    zero = max(abs(d) for d in dets.values() if d <= FORBIDDEN_BELOW)
    assert allowed > 1e4 * FORBIDDEN_BELOW and zero < 1e-6 * FORBIDDEN_BELOW, (allowed, zero)
    return {Y for Y, d in dets.items() if d <= FORBIDDEN_BELOW}


def chi2_per_dof(rolls, K):
    one = [K[i][i] for i in range(M)]
    two = {(i, j): K[i][i] * K[j][j] - K[i][j] ** 2 for i, j in itertools.combinations(range(M), 2)}
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


def law_gate(rolls, K, forbidden):
    """The named reasons these rolls are not the law's; empty means they pass."""
    out = []
    off = sum(tuple(y) in forbidden for y in rolls)
    if off:
        out.append(f"{off} of {len(rolls)} rolls lie on layouts the law forbids")
    stat = chi2_per_dof(rolls, K)
    if stat >= 1.6:
        out.append(f"chi^2/dof {stat:.3f} >= 1.6")
    return out


def chain_rule(rows, s, bug=None):
    """The authority's chain rule in binary64, with a switch for planted bugs."""
    c = [math.fsum(v * v for v in r) for r in rows]
    taken = [False] * M
    basis, picks = [], []
    for j in range(N):
        total = math.fsum(c[i] for i in range(M) if not taken[i])
        target = float(uniform(s, j)) * total
        acc, chosen = 0.0, None
        for i in range(M):
            if taken[i]:
                continue
            nxt = acc + (c[i] if c[i] > 0 else 0.0)
            if target < nxt:
                chosen = i
                break
            acc = nxt
        picks.append(chosen)
        taken[chosen] = True
        if bug == "stale-last" and j == N - 2:
            continue                                   # no projection update before the last draw
        v = list(rows[chosen])
        for _ in range(2):
            for e in basis:
                d = math.fsum(a * b for a, b in zip(v, e, strict=True))
                v = [a - d * b for a, b in zip(v, e, strict=True)]
        nv = math.sqrt(math.fsum(a * a for a in v))
        e = [a / nv for a in v]
        basis.append(e)
        w = 0.5 if (bug == "half-update" and j == 0) else 1.0     # the first projection at half weight
        for i in range(M):
            if not taken[i]:
                d = math.fsum(a * b for a, b in zip(rows[i], e, strict=True))
                c[i] -= w * d * d
    return sorted(picks)


def streams():
    return [stream("law-check", "pauli-4x4", k) for k in range(ROLLS)]


@pytest.fixture(scope="module")
def golden_rolls():
    return [fermi.sample(L, R2, s) for s in streams()]


@pytest.fixture(scope="module")
def float_rows():
    return [[float(v) for v in r] for r in fermi.orbitals(L, R2, 128)]


def test_the_golden_rolls_reproduce_the_determinantal_law(golden_rolls, kernel, forbidden):
    assert law_gate(golden_rolls, kernel, forbidden) == []


def test_uniform_rolls_fail_the_same_gate(kernel, forbidden):
    uniform_rolls = [binomial.sample(M, N, stream("law-check", "poisson", k)) for k in range(ROLLS)]
    assert chi2_per_dof(uniform_rolls, kernel) > 2.5
    assert law_gate(uniform_rolls, kernel, forbidden)


def test_the_float_copy_lays_the_authoritys_own_rolls(golden_rolls, float_rows):
    """Without this, a planted bug below would be a bug in a sampler nobody checked."""
    assert [chain_rule(float_rows, s) for s in streams()] == golden_rolls


@pytest.mark.parametrize("bug", ["stale-last", "half-update"])
def test_each_planted_sampler_bug_fails_the_gate(bug, float_rows, kernel, forbidden):
    rolls = [chain_rule(float_rows, s, bug) for s in streams()]
    assert any("forbids" in p for p in law_gate(rolls, kernel, forbidden))

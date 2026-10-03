"""A run that leaks crystals, as hardware will (the research expects 61-74% of shots to hold exactly five): every
sector measure held to an independent spelling.

verifier-P2 (18:04Z) planted four faults that every other test passes, because every other input has as many
N-crystal shots as shots: the floor taken at all shots, the TVD normalised by all shots, and the N-crystal pair
correlation taken on all shots (the fourth, the print's order, is test_compare_runs.py's). Here 40% of the shots
leave the sector. Nothing below comes from compare.py:
- the law's probabilities: the kernel written by hand from its closed form, 16 K(i, j) = 1 + 2 cos(pi dx / 2) +
  2 cos(pi dy / 2), and determinants by Fraction Gauss-Jordan elimination (compare.py uses Bareiss on its own
  integer kernel);
- every measure, spelled out from its definition in compare.py's docstring;
- one replica of the floor, drawn with golden.uniform's own Fractions and bisect.
"""
import bisect
import functools
import itertools
import math
from fractions import Fraction

import pytest

from quantum_film import compare
from quantum_film.golden import fermi
from quantum_film.golden.uniform import stream, uniform

L, M, N = 4, 16, 5
D = math.comb(M, N)
COS = {0: 1, 1: 0, 2: -1, 3: 0}                     # cos(pi d / 2) for d mod 4


def det(rows):
    """Fraction Gauss-Jordan: pivot on the first nonzero entry below, eliminate, multiply the pivots."""
    m = [[Fraction(v) for v in row] for row in rows]
    out = Fraction(1)
    for k in range(len(m)):
        p = next((r for r in range(k, len(m)) if m[r][k] != 0), None)
        if p is None:
            return Fraction(0)
        if p != k:
            m[k], m[p] = m[p], m[k]
            out = -out
        out *= m[k][k]
        for r in range(len(m)):
            if r != k and m[r][k] != 0:
                f = m[r][k] / m[k][k]
                m[r] = [a - f * b for a, b in zip(m[r], m[k], strict=True)]
    return out


@functools.lru_cache(maxsize=None)
def P(Y):
    """det(K_Y) for a five-site layout, from the kernel by hand; 0 for any other crystal count."""
    if len(Y) != N:
        return Fraction(0)
    k16 = [[1 + 2 * COS[(i // L - j // L) % L] + 2 * COS[(i % L - j % L) % L] for j in Y] for i in Y]
    return det([[Fraction(v, 16) for v in row] for row in k16])


@pytest.fixture(scope="module")
def law():
    """Every five-site layout's probability, in itertools.combinations order."""
    layouts = list(itertools.combinations(range(M), N))
    probs = [P(Y) for Y in layouts]
    assert sum(probs) == 1
    return layouts, probs


@pytest.fixture(scope="module")
def leaky(law):
    """600 shots from the authority (golden.fermi), then leaked by rule: every fifth shot from shot 1 loses its
    lowest crystal (4), every fifth from shot 2 gains the lowest empty site (6), and of the rest every seventh from
    shot 3 is replaced by the first forbidden layout. 360 shots keep five crystals."""
    layouts, probs = law
    forbidden = layouts[probs.index(0)]
    shots = []
    for k in range(600):
        Y = tuple(fermi.sample(4, 1, stream("compare-test-leaky", "pauli-4x4", k)))
        if k % 5 == 1:
            Y = Y[1:]
        elif k % 5 == 2:
            Y = tuple(sorted(Y + (min(set(range(M)) - set(Y)),)))
        elif k % 7 == 3:
            Y = forbidden
        shots.append(Y)
    counts = {}
    for Y in shots:
        counts[Y] = counts.get(Y, 0) + 1
    return counts


def nn_pairs():
    out = set()
    for s in range(M):
        x, y = divmod(s, L)
        for t in (((x + 1) % L) * L + y, x * L + (y + 1) % L):
            out.add((min(s, t), max(s, t)))
    return sorted(out)


def pair_correlation(counts):
    total = sum(counts.values())
    rho = [Fraction(sum(c for Y, c in counts.items() if s in Y), total) for s in range(M)]
    both = [Fraction(sum(c for Y, c in counts.items() if i in Y and j in Y), total) for i, j in nn_pairs()]
    return sum(b / (rho[i] * rho[j]) for b, (i, j) in zip(both, nn_pairs(), strict=True)) / len(nn_pairs())


@pytest.fixture(scope="module")
def measured(leaky):
    return compare.law_measures(leaky)


def sector(counts):
    return {Y: c for Y, c in counts.items() if len(Y) == N}


def test_the_leaky_run_is_what_hardware_will_send(leaky, measured):
    assert sum(leaky.values()) == 600 and sum(sector(leaky).values()) == 360
    assert measured["shots"] == 600 and measured["n_crystal"]["shots"] == 360
    assert measured["n_crystal"]["share"] == 360 / 600
    assert measured["crystals_per_shot"] == {"4": 120, "5": 360, "6": 120}
    on_forbidden = sum(c for Y, c in sector(leaky).items() if P(Y) == 0)
    assert on_forbidden > 0 and measured["forbidden"]["shots"] == on_forbidden
    assert measured["forbidden"]["share_of_n_crystal"] == on_forbidden / 360


def test_the_tvd_is_over_the_n_crystal_shots(leaky, measured):
    """TVD = (1/2) sum over all D layouts of |c_Y / n - P(Y)|, n the N-crystal shots; a layout no shot laid
    contributes P(Y), so the sum is the laid layouts' terms plus the law's mass on the rest."""
    c = sector(leaky)
    n = sum(c.values())
    laid = sum(abs(Fraction(k, n) - P(Y)) for Y, k in c.items())
    tvd = (laid + 1 - sum(P(Y) for Y in c)) / 2
    assert measured["tvd"]["value"] == float(tvd)
    over_all = (sum(abs(Fraction(k, 600) - P(Y)) for Y, k in c.items()) + 1 - sum(P(Y) for Y in c)) / 2
    assert float(over_all) != float(tvd)                     # the test can tell the two normalisations apart


def test_the_floor_is_a_perfect_sampler_at_the_n_crystal_count(law, measured):
    """The floor stands at n = 360, not at the 600 shots. Two of its replicas, drawn here with golden.uniform's
    Fractions and bisect on the hand-made weights, are among its 200."""
    floor = measured["tvd"]["floor"]
    assert floor["shots"] == 360 and floor["replicas"] == 200
    layouts, probs = law
    cum = list(itertools.accumulate(int(p * 4096) for p in probs))
    assert cum[-1] == 4096 and all(p * 4096 == int(p * 4096) for p in probs)
    replicas = compare.floor_replicas(360)
    for r in (0, 199):
        s = stream("compare-floor", "pauli-4x4", 360, r)
        counts = {}
        for i in range(360):
            Y = layouts[bisect.bisect_right(cum, math.floor(uniform(s, i) * 4096))]
            counts[Y] = counts.get(Y, 0) + 1
        tvd = (sum(abs(Fraction(k, 360) - P(Y)) for Y, k in counts.items()) + 1 - sum(P(Y) for Y in counts)) / 2
        assert tvd in replicas
    rank = math.ceil(0.95 * 200)
    assert floor["upper"] == float(replicas[rank - 1]) and floor["mean"] == float(sum(replicas) / 200)


def test_the_fidelity_is_over_the_n_crystal_shots(law, leaky, measured):
    """F = (mean of P over the N-crystal shots - 1/D) / (sum of P^2 - 1/D), and its error the sample deviation of P
    over those shots, over sqrt(n), over the normaliser."""
    layouts, probs = law
    c = sector(leaky)
    n = sum(c.values())
    norm = sum(p * p for p in probs) - Fraction(1, D)
    mean = sum(k * P(Y) for Y, k in c.items()) / n
    assert measured["xeb"]["exact"] == str((mean - Fraction(1, D)) / norm) and measured["xeb"]["shots"] == 360
    var = sum(k * (P(Y) - mean) ** 2 for Y, k in c.items()) / (n - 1)
    assert math.isclose(measured["xeb"]["se"], math.sqrt(var / n) / float(norm), rel_tol=1e-12)


def test_the_pair_correlation_is_taken_on_all_shots_and_on_the_n_crystal_shots_apart(leaky, measured):
    g_all, g_n = pair_correlation(leaky), pair_correlation(sector(leaky))
    assert measured["pair_correlation"]["all"] == float(g_all)
    assert measured["pair_correlation"]["n_crystal"] == float(g_n)
    assert float(g_all) != float(g_n)                         # the leak moves it, so a mix-up shows

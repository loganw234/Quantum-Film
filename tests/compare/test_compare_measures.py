"""Each measure on inputs whose answer is known exactly: hand-made counts, counts proportional to the law or to the
twin, and a brute-force spelling of each definition that shares no code with compare.py's."""
import itertools
import math
from fractions import Fraction

import pytest

from quantum_film import compare
from quantum_film.atlas import pauli_tile


@pytest.fixture(scope="module")
def law():
    return compare.exact_law()


@pytest.fixture(scope="module")
def a_forbidden_and_an_allowed(law):
    layouts, weights, den = law
    return layouts[weights.index(0)], layouts[weights.index(9)]


def test_the_shares_count_the_n_crystal_shots_and_the_forbidden_among_them(a_forbidden_and_an_allowed):
    """12 shots: 2 on a forbidden five-crystal layout, 6 on an allowed one, 4 holding two crystals. The N-crystal
    share is 8/12; the forbidden share is of the N-crystal shots, 2/8, not of all shots."""
    bad, good = a_forbidden_and_an_allowed
    m = compare.law_measures({bad: 2, good: 6, (0, 1): 4})
    assert m["shots"] == 12 and m["crystals_per_shot"] == {"2": 4, "5": 8}
    assert m["n_crystal"] == {"N": 5, "shots": 8, "share": 8 / 12}
    assert m["forbidden"] == {"shots": 2, "share_of_n_crystal": 2 / 8, "distinct": 1}


def test_the_tvd_and_the_fidelity_are_exact_at_the_law_the_twin_and_halfway(law):
    """Counts proportional to the law: TVD 0, fidelity 1. One shot per layout (the twin, exactly): TVD 85/273,
    fidelity 0. Equal shots of each: fidelity 1/2 exactly, by the definition's linearity."""
    layouts, weights, den = law
    as_law = {Y: w for Y, w in zip(layouts, weights, strict=True) if w}
    as_twin = {Y: 1 for Y in layouts}
    m = compare.law_measures(as_law, floor=False)
    assert m["tvd"]["value"] == 0 and m["xeb"]["exact"] == "1"
    m = compare.law_measures(as_twin, floor=False)
    assert m["xeb"]["exact"] == "0" and Fraction(m["tvd"]["value"]).limit_denominator(10000) == Fraction(85, 273)
    half = {Y: as_law.get(Y, 0) * len(layouts) + den for Y in layouts}           # 4096 * 4368 shots of each
    assert compare.xeb(half)["exact"] == "1/2"


def test_the_fidelity_is_its_definition_spelled_out(law):
    """F = (mean P - 1/D) / (sum P^2 - 1/D), with P from the exact law, on a small sample of the twin, and its
    standard error the sample deviation of P over sqrt(n) over the normaliser."""
    layouts, weights, den = law
    P = {Y: Fraction(w, den) for Y, w in zip(layouts, weights, strict=True)}
    counts = compare.twin_sample(300, ("compare-test-xeb",))
    shots = [P[Y] for Y, c in counts.items() for _ in range(c)]
    D = len(layouts)
    norm = sum(p * p for p in P.values()) - Fraction(1, D)
    mean = sum(shots) / len(shots)
    got = compare.xeb(counts)
    assert got["exact"] == str((mean - Fraction(1, D)) / norm)
    sd = math.sqrt(sum((float(p) - float(mean)) ** 2 for p in shots) / (len(shots) - 1))
    assert math.isclose(got["se"], sd / math.sqrt(len(shots)) / float(norm), rel_tol=1e-12)


def brute_pair_correlation(counts):
    L = 4
    pairs = set()
    for x, y in itertools.product(range(L), repeat=2):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            a, b = x * L + y, ((x + dx) % L) * L + (y + dy) % L
            pairs.add((min(a, b), max(a, b)))
    total = sum(counts.values())
    rho = {s: Fraction(sum(c for Y, c in counts.items() if s in Y), total) for s in range(16)}
    both = {p: Fraction(sum(c for Y, c in counts.items() if p[0] in Y and p[1] in Y), total) for p in pairs}
    return len(pairs), sum(both[p] / (rho[p[0]] * rho[p[1]]) for p in pairs) / len(pairs)


def test_the_pair_correlation_where_the_densities_differ_from_site_to_site():
    """A law sample with site 6's bit flipped in a third of its shots: site 6's density moves, so a wrong
    denominator (one site's density squared, say) shows; the law's translation invariance would hide it."""
    sample = compare.law_sample(3000, ("compare-test-pairs",))
    shots = [Y for Y, c in sorted(sample.items()) for _ in range(c)]
    flipped = {}
    for k, Y in enumerate(shots):
        Y = tuple(sorted(set(Y) ^ {6})) if k % 3 == 0 else Y
        flipped[Y] = flipped.get(Y, 0) + 1
    n_pairs, want = brute_pair_correlation(flipped)
    assert n_pairs == 32 == len(compare.neighbour_pairs())
    assert compare.pair_correlation(flipped) == want


def test_the_pair_correlation_is_none_where_a_site_never_holds_a_crystal():
    assert compare.pair_correlation({(0, 1, 2, 3, 4): 5}) is None


def test_z_is_pauli_tiles_score_on_all_shots_and_on_the_n_crystal_shots(a_forbidden_and_an_allowed):
    bad, good = a_forbidden_and_an_allowed
    counts = {bad: 3, good: 11, (0, 1, 2, 3, 4, 5): 2, (7,): 1}
    K, forbidden, _ = pauli_tile.law_of()
    m = compare.law_measures(counts, circuit_sha256="ab" * 32)
    for subset, which in ((counts, "all"), ({bad: 3, good: 11}, "n_crystal")):
        score = pauli_tile.score(subset, K, forbidden, "ab" * 32)
        assert m["z"][which]["one_site"]["z"] == score["one_site"]["z"]
        assert m["z"][which]["pairs"]["max_abs_z"] == score["pairs"]["max_abs_z"]
        assert m["z"][which]["chi2_per_dof"] == score["chi2_per_dof"]


@pytest.mark.parametrize("counts, why", [
    ({(1, 0, 2, 3, 4): 1}, "not strictly increasing"), ({(0, 0, 2, 3, 4): 1}, "not strictly increasing"),
    ({(0, 1, 2, 3, 16): 1}, "not strictly increasing sites of 0..15"), ({(True, 2): 1}, "not strictly increasing"),
    ({(0, 1, 2, 3, 4): -1}, "not a whole number"), ({(0, 1, 2, 3, 4): 1.0}, "not a whole number"),
    ({(0, 1, 2, 3, 4): True}, "not a whole number"), ({(0, 1, 2, 3, 4): 0}, "no shots to measure")])
def test_counts_that_are_not_canonical_are_refused_by_name(counts, why):
    with pytest.raises(ValueError, match=why):
        compare.law_measures(counts)
    if why != "no shots to measure":
        with pytest.raises(ValueError, match=why):
            compare.coherence(counts, "XX" + "Z" * 14)


def test_a_run_with_no_n_crystal_shot_is_measured_without_the_sector_measures():
    m = compare.law_measures({(0, 1): 3, (2, 3, 4, 5, 6, 7): 1})
    assert m["n_crystal"]["shots"] == 0 and "tvd" not in m and "xeb" not in m
    assert m["forbidden"]["share_of_n_crystal"] is None and "n_crystal" not in m["z"]


def test_the_perfect_sampler_is_the_law_in_its_counts():
    sample = compare.law_sample(1000, ("compare-test-sample",))
    assert sum(sample.values()) == 1000 and all(compare.probability(Y) > 0 for Y in sample)

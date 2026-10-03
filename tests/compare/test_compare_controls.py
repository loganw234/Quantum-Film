"""The comparison's four negative controls (round 3's P2 brief), each with its positive twin in the same test.

The inputs are made deterministically, on streams named before any result was looked at:
- law samples from the authority itself, golden.fermi.sample(4, 1, stream("compare-test-law", "pauli-4x4", i));
- twin samples from golden.binomial, stream("compare-test-twin", "pauli-4x4", i);
- a mixture and the corruptions by rule: coins on golden uniforms, every fourth shot replaced or flipped.
The perfect sampler's floor is compare's own exact sampler, so control 3 holds two independent samplers of the
law against each other: the authority's chain rule, and the integer inverse CDF.
"""
import math

import numpy as np
import pytest

from quantum_film import compare
from quantum_film.circuits import givens_line
from quantum_film.golden import binomial, fermi
from quantum_film.golden.uniform import stream

N_LAW = 2048
XX, YY = "XX" + "Z" * 14, "YY" + "Z" * 14
FORBIDDEN_SHARE = 1360 / 4368


def tally(shots):
    out = {}
    for Y in shots:
        out[tuple(Y)] = out.get(tuple(Y), 0) + 1
    return out


@pytest.fixture(scope="module")
def law_shots():
    """2,048 shots of the exact law, laid by the authority, in stream order."""
    return [tuple(fermi.sample(4, 1, stream("compare-test-law", "pauli-4x4", i))) for i in range(N_LAW)]


@pytest.fixture(scope="module")
def law_measured(law_shots):
    return compare.law_measures(tally(law_shots))


def law_coherence_run(letter, shots):
    """A coherence run of the law circuit as hardware would read it with no noise: the committed circuit's state
    from the project's simulator, qubits 0 and 1 rotated (H for X; S-dagger then H for Y), every qubit read in
    Z, `shots` outcomes drawn by inverse CDF on golden uniforms."""
    gate_list, M = givens_line.from_qasm((compare.ROOT / compare.SOURCE_QASM).read_text(encoding="ascii"))
    psi = givens_line.simulate(gate_list, M).astype(complex)
    H = np.array([[1, 1], [1, -1]]) / math.sqrt(2)
    U = H if letter == "X" else H @ np.diag([1, -1j])
    for q in (0, 1):
        psi = np.moveaxis(np.tensordot(U, psi, axes=([1], [q])), 0, q)
    cdf = np.cumsum((np.abs(psi) ** 2).reshape(-1))
    words = compare.uniform_words(("compare-test-coherence", letter), shots)
    out = {}
    for w in words:
        n = int(np.searchsorted(cdf, int(w) / 2.0 ** 64 * cdf[-1], side="right"))
        Y = tuple(q for q in range(M) if (n >> (M - 1 - q)) & 1)          # C order: qubit 0 is the high bit
        out[Y] = out.get(Y, 0) + 1
    return out


# ---- 1. coherence near 0


@pytest.mark.parametrize("letter, basis", [("X", XX), ("Y", YY)])
def test_a_classical_mixture_reads_no_coherence_and_the_law_reads_three_eighths(law_shots, letter, basis):
    """Each shot a computational-basis layout of the law, read in X (or Y) on the pair: its bits there are fair
    coins, so <P0P1> is 0 within its error, and told apart from the law's +0.375. The law's own run is the twin."""
    mixture = compare.mixture_read_in_x(tally(law_shots), ("compare-test-mixture", letter))
    m = compare.coherence(mixture, basis)
    assert m["observable"] == f"{letter}0{letter}1" and m["shots"] == N_LAW
    assert abs(m["value"]) <= 3 * m["se"]
    assert abs(m["value"] - 0.375) > 10 * m["se"]
    law = compare.coherence(law_coherence_run(letter, N_LAW), basis)
    assert abs(law["value"] - 0.375) <= 3 * law["se"]
    assert abs(law["value"]) > 10 * law["se"]


def test_the_mixture_keeps_every_other_site_of_its_layouts(law_shots):
    """Only the pair is re-read: the other fourteen sites' occupations are the law's, shot for shot."""
    counts = tally(law_shots)
    mixture = compare.mixture_read_in_x(counts, ("compare-test-mixture", "X"))
    rest = {}
    for Y, c in mixture.items():
        key = tuple(q for q in Y if q > 1)
        rest[key] = rest.get(key, 0) + c
    want = {}
    for Y, c in counts.items():
        key = tuple(q for q in Y if q > 1)
        want[key] = want.get(key, 0) + c
    assert rest == want


# ---- 2. the twin


def test_a_twin_sample_puts_a_third_of_its_shots_on_forbidden_layouts_and_scores_no_fidelity(law_measured):
    """The twin: about 31.1% forbidden (85/273), cross-entropy fidelity 0 within its error, and the pair
    correlation the twin's 64/75; the law's sample beside it: none forbidden, fidelity 1 within its error, 16/25."""
    n = 4096
    twin = compare.law_measures(compare.twin_sample(n, ("compare-test-twin", "pauli-4x4")))
    share = twin["forbidden"]["share_of_n_crystal"]
    assert abs(share - FORBIDDEN_SHARE) <= 3 * math.sqrt(FORBIDDEN_SHARE * (1 - FORBIDDEN_SHARE) / n)
    assert abs(twin["xeb"]["value"]) <= 3 * twin["xeb"]["se"]
    assert twin["xeb"]["value"] < 1 - 10 * twin["xeb"]["se"]
    assert abs(twin["pair_correlation"]["all"] - 64 / 75) < 0.03
    law = law_measured
    assert law["forbidden"]["shots"] == 0 and law["n_crystal"]["share"] == 1
    assert abs(law["xeb"]["value"] - 1) <= 3 * law["xeb"]["se"]
    assert abs(law["pair_correlation"]["all"] - 16 / 25) < 0.03


def test_the_twin_sample_is_golden_binomial_shot_by_shot():
    twin = compare.twin_sample(50, ("compare-test-twin", "pauli-4x4"))
    by_hand = {}
    for i in range(50):
        Y = tuple(binomial.sample(16, 5, stream("compare-test-twin", "pauli-4x4", i)))
        by_hand[Y] = by_hand.get(Y, 0) + 1
    assert twin == by_hand


# ---- 3. the floor


def test_exact_law_samples_score_at_the_floor_and_a_corrupted_sample_does_not(law_shots, law_measured):
    """The authority's 2,048 shots: their TVD falls inside the perfect sampler's stated percentile (95th) at the
    same count. The negative: every fourth of them replaced by a twin shot lands above every one of the 200
    replicas. A perfect sample exceeds the 95th percentile one time in twenty by construction; these streams
    were named before the result was seen, and the margin is printed by the run, not chosen."""
    tvd = law_measured["tvd"]
    assert tvd["floor"]["shots"] == N_LAW
    assert tvd["value"] <= tvd["floor"]["upper"]
    corrupted = [tuple(binomial.sample(16, 5, stream("compare-test-corrupt", "pauli-4x4", k))) if k % 4 == 0 else Y
                 for k, Y in enumerate(law_shots)]
    bad = compare.law_measures(tally(corrupted))
    assert bad["tvd"]["value"] > bad["tvd"]["floor"]["max"]
    assert bad["forbidden"]["shots"] > 0 and bad["xeb"]["value"] < law_measured["xeb"]["value"]


# ---- 4. a readout error


def flip(Y, site):
    return tuple(sorted(set(Y) ^ {site}))


def test_a_planted_readout_error_moves_the_n_crystal_share_and_that_sites_z(law_shots, law_measured):
    """Site 6's bit flipped in every fourth shot: those shots leave the five-crystal sector, so the N-crystal share
    is exactly 3/4, and site 6's one-site z over all shots is the worst on the tile and far out. Read on the
    N-crystal shots alone, site 6 is ordinary again: a single flip cannot stay in the sector."""
    site = 6
    bad = compare.law_measures(tally([flip(Y, site) if k % 4 == 0 else Y for k, Y in enumerate(law_shots)]))
    assert law_measured["n_crystal"]["share"] == 1 and bad["n_crystal"]["share"] == 0.75
    assert bad["crystals_per_shot"].keys() == {"4", "5", "6"}
    z_all = bad["z"]["all"]["one_site"]["z"]
    assert max(range(16), key=lambda q: abs(z_all[q])) == site and z_all[site] > 6
    assert law_measured["z"]["all"]["one_site"]["max_abs_z"] < 4
    assert abs(bad["z"]["n_crystal"]["one_site"]["z"][site]) < 4

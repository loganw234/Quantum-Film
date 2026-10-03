"""IBM's sampler bitstrings, read as the logical qubits that read 1 (quantum_film.ibm.decode).

THE KNOWN ANSWER: X on {0, 1, 3, 7, 12}, measured into one 16-bit register by
measure_all, read 0001000010001011 through get_bitstrings() on 2026-10-01
(qiskit 2.5.2 and qiskit-ibm-runtime 0.50.0 on the fake ibm_kingston, ibm_fez
and ibm_marrakesh; the research-ibm agent's ka_bitorder.py, round 3), and again
through both samplers at levels 1-3 by round 3's P0 verifier. That is a
simulator's string: the first job of every hardware route repeats it on the
device. Its set is not its own mirror under q -> 15 - q, which is what lets it
tell the two orders apart; on the 4x4 tile the mirror is a gauge of the law.
"""
import pytest

from quantum_film.ibm import decode

M = 16
KNOWN = (0, 1, 3, 7, 12)
MIRROR = (3, 8, 12, 14, 15)
STRING = "0001000010001011"


def test_the_known_answer_reads_as_the_qubits_that_were_flipped():
    assert decode.ones(STRING, M) == KNOWN


def test_plain_order_would_read_the_mirror_and_this_answer_can_tell_them_apart():
    plain = tuple(p for p in range(M) if STRING[p] == "1")
    assert plain == MIRROR == tuple(sorted(M - 1 - q for q in KNOWN))
    assert set(KNOWN) != set(MIRROR)        # a mirror-symmetric answer could not tell the orders apart


@pytest.mark.parametrize("bad", [STRING[:-1], STRING + "0", "000100001000101x", 0b1011, None])
def test_anything_but_m_bits_is_refused(bad):
    with pytest.raises(ValueError):
        decode.ones(bad, M)


def test_tally_and_canonical_give_a_device_runs_counts():
    counts = decode.tally([STRING, STRING, "0" * M, "1" * M], M)
    assert counts == {KNOWN: 2, (): 1, tuple(range(M)): 1}
    assert decode.canonical(counts) == [[[], 1], [list(range(M)), 1], [list(KNOWN), 2]]


def test_a_known_answer_run_holds_when_the_expected_set_is_modal_noise_and_all():
    noisy = {KNOWN: 880, (0, 1, 3, 7): 60, (0, 1, 3, 7, 12, 13): 50, MIRROR: 10}
    verdict = decode.known_answer(noisy, KNOWN, M)
    assert verdict["holds"] and verdict["modal"] == list(KNOWN)
    assert verdict["share"] == 0.88 and verdict["mirror_share"] == 0.01 and verdict["shots"] == 1000


def test_a_known_answer_run_read_in_the_wrong_order_fails():
    mirrored = {MIRROR: 880, KNOWN: 10, (3, 8, 12, 14): 110}
    verdict = decode.known_answer(mirrored, KNOWN, M)
    assert not verdict["holds"] and verdict["modal"] == list(MIRROR) and verdict["mirror_share"] == 0.88


def test_a_known_answer_that_cannot_tell_the_orders_apart_is_refused():
    with pytest.raises(ValueError, match="its own mirror"):
        decode.known_answer({(0, 15): 10}, (0, 15), M)
    with pytest.raises(ValueError, match="no shots"):
        decode.known_answer({}, KNOWN, M)


def test_a_tie_with_the_mirror_decides_nothing():
    verdict = decode.known_answer({MIRROR: 5, KNOWN: 5}, KNOWN, M)
    assert verdict["modal"] == list(KNOWN)          # the tie is broken the same way every time: the smaller key
    assert not verdict["holds"]                     # but a tie between the orders is not a reading of either

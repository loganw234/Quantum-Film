"""IBM's sampler bitstrings, read as the logical qubits that read 1 (quantum_film.ibm.decode).

THE KNOWN ANSWER: X on {0, 1, 3, 7, 12}, measured into one 16-bit register by
measure_all, read 0001000010001011 through get_bitstrings() on 2026-10-01
(qiskit 2.5.2 and qiskit-ibm-runtime 0.50.0 on the fake ibm_kingston, ibm_fez
and ibm_marrakesh; the research-ibm agent's ka_bitorder.py, round 3). That is a
simulator's string: the first job of every hardware route repeats it on the
device. Its set is not its own mirror under q -> 15 - q, which is what lets it
tell the two orders apart; on the 4x4 tile the mirror is a gauge of the law.
"""
import pytest

from quantum_film.ibm import decode

M = 16
KNOWN = (0, 1, 3, 7, 12)
STRING = "0001000010001011"


def test_the_known_answer_reads_as_the_qubits_that_were_flipped():
    assert decode.ones(STRING, M) == KNOWN


def test_plain_order_would_read_the_mirror_and_this_answer_can_tell_them_apart():
    plain = tuple(p for p in range(M) if STRING[p] == "1")
    mirror = tuple(sorted(M - 1 - q for q in KNOWN))
    assert plain == mirror == (3, 8, 12, 14, 15)
    assert set(KNOWN) != set(mirror)        # a mirror-symmetric answer could not tell the orders apart


@pytest.mark.parametrize("bad", [STRING[:-1], STRING + "0", "000100001000101x", 0b1011, None])
def test_anything_but_m_bits_is_refused(bad):
    with pytest.raises(ValueError):
        decode.ones(bad, M)


def test_tally_and_canonical_give_a_device_runs_counts():
    counts = decode.tally([STRING, STRING, "0" * M, "1" * M], M)
    assert counts == {KNOWN: 2, (): 1, tuple(range(M)): 1}
    assert decode.canonical(counts) == [[[], 1], [list(range(M)), 1], [list(KNOWN), 2]]

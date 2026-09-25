"""tomography-api-v2's count order, held to a frozen known-answer run from Atlas."""
import json
import math
import pathlib

import pytest

from quantum_film.atlas.decode import basis_of, layouts, order, z_setting

VEC = pathlib.Path(__file__).parent / "vectors" / "tomography-bitorder-2026-09-25.json"
M = 16


def expected_p1(label, q):
    """The known answer: qubit q was prepared by ry(theta_q), sin^2(theta_q/2) = (q+0.5)/16."""
    theta = 2 * math.asin(math.sqrt((q + 0.5) / M))
    b = basis_of(label, q)
    return {"Z": (q + 0.5) / M, "X": (1 - math.sin(theta)) / 2, "Y": 0.5}[b]


def worst_z(order_fn):
    meas = json.loads(VEC.read_text(encoding="utf-8"))["measurements"]
    worst = 0.0
    for label, v in meas.items():
        counts, pos2q = v["counts"], order_fn(label)
        n = sum(counts.values())
        for p in range(M):
            q = pos2q[p]
            e = expected_p1(label, q)
            m = sum(c for s, c in counts.items() if s[p] == "1") / n
            worst = max(worst, abs(m - e) / math.sqrt(max(e * (1 - e), 1e-12) / n))
    return worst


def test_the_rule_accounts_for_every_position_of_every_setting():
    assert worst_z(order) < 4.0            # 144 comparisons; 2.49 on the day


def test_plain_circuit_order_fails_the_same_check():
    assert worst_z(lambda label: list(range(M - 1, -1, -1))) > 50.0     # 316.61 on the day


def test_the_order_changes_between_settings_within_one_response():
    meas = json.loads(VEC.read_text(encoding="utf-8"))["measurements"]
    assert len({tuple(order(label)) for label in meas}) > 1


def test_layouts_read_whole_registers_through_the_rule():
    # A worked 4-qubit example, derived by hand: in "IZIZ" the non-I label
    # positions are 1 and 3, which are qubits 2 and 0 (labels are qubit 0
    # rightmost). The register from the right is therefore [0, 2, 1, 3], and
    # the string "0110" holds qubits 1 and 2.
    result = {"measurements": {"IZIZ": {"counts": {"0110": 7, "1001": 2}},
                               "IXIX": {"counts": {"0000": 9}}}}
    assert order("IZIZ") == [3, 1, 2, 0]
    assert layouts(result) == {(1, 2): 7, (0, 3): 2}


def test_exactly_one_all_z_setting_or_a_refusal():
    with pytest.raises(ValueError, match="exactly one"):
        z_setting({"IXIX": {}, "XIXI": {}})
    with pytest.raises(ValueError, match="exactly one"):
        z_setting({"IZIZ": {}, "ZIZI": {}})

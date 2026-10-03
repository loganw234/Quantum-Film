"""The table's baselines: the exact law and the twin as exact values, Atlas's 24,576 emulator shots read from the
committed records, and the twin as a sample of the same count. The exact values are stated as fractions."""
import math
from fractions import Fraction

import pytest

from quantum_film import compare, fixer

ATLAS_JOBS = {"8586f1cc", "3673f9fe", "579df87d", "5831ff5e", "933138bc", "d017540c"}


@pytest.fixture(scope="module")
def table_columns():
    return compare.baselines()


def by_label(columns, start):
    (col,) = [c for c in columns if c["label"].startswith(start)]
    return col


def test_the_emulator_is_every_committed_atlas_shot_of_the_shelfs_circuit():
    """Six jobs of 4,096 shots, all of circuit ed767c01, every one five crystals on an allowed layout."""
    rolls = compare.emulator_rolls()
    assert len(rolls) == 12071 and {job[:8] for job, _, _ in rolls} == ATLAS_JOBS
    counts = compare.emulator_counts()
    assert sum(counts.values()) == compare.EMULATOR_SHOTS == 24576
    assert {len(Y) for Y in counts} == {5} and all(compare.probability(Y) > 0 for Y in counts)


def test_the_emulator_scores_at_the_floor_and_reads_three_eighths(table_columns):
    """Atlas's emulator laid the law (round 1 showed it); here its TVD is inside the perfect sampler's 95th
    percentile, its fidelity 1 within 3 errors, and the engine's own <X0X1> and <Y0Y1> within P3's 4.5 errors of
    +0.375 (pauli_tile.ENGINE_Z)."""
    emu = by_label(table_columns, "emulator")
    law = emu["law"]
    assert law["n_crystal"]["share"] == 1 and law["forbidden"]["shots"] == 0
    assert law["tvd"]["value"] <= law["tvd"]["floor"]["upper"]
    assert abs(law["xeb"]["value"] - 1) <= 3 * law["xeb"]["se"]
    for name in ("X0X1", "Y0Y1"):
        m = emu["coherence"][name]
        assert m["shots"] == 24576 and m["jobs"] == 6 and abs(m["value"] - 0.375) <= 4.5 * m["se"]


def test_the_exact_law_column(table_columns):
    law = by_label(table_columns, "law (exact)")
    m = law["law"]
    assert m["tvd"]["value"] == 0 and m["xeb"]["value"] == 1 and m["forbidden"]["share_of_n_crystal"] == 0
    assert m["pair_correlation"]["exact"] == "16/25"
    assert m["z"]["all"]["one_site"]["max_abs_z"] < 1e-9 and m["z"]["all"]["pairs"]["max_abs_z"] < 1e-9
    assert m["tvd"]["floor"]["shots"] == 24576
    for name in ("X0X1", "Y0Y1"):
        assert abs(law["coherence"][name]["value"] - 0.375) < 1e-12


def test_the_exact_twin_column(table_columns):
    """The twin forbids nothing, so its TVD to the law is exactly the law's forbidden mass under the twin,
    1,360 / 4,368 = 85/273; its expected pair z at 24,576 shots is (1/12 - P_law(11)) over the binomial error."""
    twin = by_label(table_columns, "twin (exact)")
    m = twin["law"]
    assert m["forbidden"]["exact"] == "85/273" == m["tvd"]["exact"] == str(Fraction(1360, 4368))
    assert m["xeb"]["value"] == 0 and m["pair_correlation"]["exact"] == "64/75"
    assert m["z"]["all"]["one_site"]["max_abs_z"] < 1e-9                       # the twin's densities are 5/16 too
    nn = (1 / 12 - 1 / 16) / math.sqrt((1 / 16) * (15 / 16) / 24576)           # a nearest-neighbour pair
    assert abs(m["z"]["all"]["pairs"]["max_abs_z"] - nn) < 1e-9
    assert all(c["value"] == 0 for c in twin["coherence"].values())


def test_the_twin_sample_column_is_the_twin_at_the_same_count(table_columns):
    twin = by_label(table_columns, "twin (sample")
    m = twin["law"]
    assert m["shots"] == 24576 and m["n_crystal"]["share"] == 1
    p = 1360 / 4368
    assert abs(m["forbidden"]["share_of_n_crystal"] - p) <= 3 * math.sqrt(p * (1 - p) / 24576)
    assert abs(m["xeb"]["value"]) <= 3 * m["xeb"]["se"]
    assert m["tvd"]["value"] > m["tvd"]["floor"]["max"]
    for name in ("X0X1", "Y0Y1"):
        assert abs(twin["coherence"][name]["value"]) <= 3 * twin["coherence"][name]["se"]


def test_the_law_columns_coherence_is_the_simulators_on_the_committed_circuit():
    """The brief's check: givens_line's simulate and pauli_expectation on the committed QASM give +0.375 twice."""
    got = compare.coherence_law()
    assert abs(got["X0X1"] - 0.375) < 1e-12 and abs(got["Y0Y1"] - 0.375) < 1e-12
    assert all(abs(got[k] - v) < 1e-12 for k, v in compare.COHERENCE_LAW.items())


def test_another_circuit_file_is_refused(tmp_path):
    src = (compare.ROOT / compare.SOURCE_QASM).read_text(encoding="ascii")
    planted = tmp_path / compare.SOURCE_QASM
    planted.parent.mkdir(parents=True)
    planted.write_text(src.replace("ry(", "ry(-", 1), encoding="ascii", newline="\n")
    with pytest.raises(ValueError, match="is not the circuit ed767c01bd4b851d"):
        compare.coherence_law(root=tmp_path)


def test_an_emulator_roll_the_fixer_refuses_is_refused(tmp_path):
    good = sorted((compare.ROOT / compare.EMULATOR_DIRS[0]).glob("rolls-*/*.json"))[0]
    rolls = tmp_path / compare.EMULATOR_DIRS[0] / good.parent.name
    rolls.mkdir(parents=True)
    rec = fixer.check_file(good)[0]
    rec["source"]["occurrences"] += 1                                         # the digest kept
    (rolls / good.name).write_text(fixer.text(rec), encoding="ascii", newline="\n")
    with pytest.raises(ValueError, match="the fixer refuses it"):
        compare.emulator_records(root=tmp_path)


def test_the_table_has_a_row_per_measure_and_a_column_per_baseline(table_columns):
    text = compare.table(table_columns)
    lines = text.splitlines()
    assert lines[0].startswith("| measure | law (exact) | emulator (Atlas, 24576 shots) | twin (exact) | twin (sample")
    assert len(lines) == 2 + len(compare.ROWS)
    assert "| forbidden share of N-crystal shots | 0.0000 | 0.0000 | 0.3114 |" in text

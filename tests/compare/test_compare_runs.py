"""Device runs into the comparison: a hardware column and the print take qpu runs only, a simulator's run appears
only under its own label, every record passes the fixer first, and the print's layouts and geometry follow
their rule. The records are made with fixer.fix_run, as tests/fixer/test_device_runs.py makes them."""
import copy
import hashlib

import pytest

from quantum_film import compare, develop, fixer
from quantum_film.ibm import decode

Z = "Z" * 16
XX, YY = "XX" + "Z" * 14, "YY" + "Z" * 14
OPTIONS = {"dynamical_decoupling": {"enable": False}, "twirling": {"enable_gates": False, "enable_measure": False}}
LAW_COUNTS = [[[0, 1, 2, 3, 4], 1], [[0, 1, 2, 4, 8], 3], [[0, 1, 2, 4, 9], 2], [[2, 5], 2],
              [[3, 6, 9, 12, 13, 15], 1], [[3, 6, 9, 12, 15], 4]]


def source(role, basis, shots, pub=0, kind="qpu", backend="ibm_kingston", job="d3stand1n0job"):
    s = {"kind": kind, "route": "ibm-direct", "backend": backend, "program": "sampler", "job_id": job,
         "pub": pub, "circuit_sha256": hashlib.sha256(role.encode() + basis.encode()).hexdigest(),
         "isa_sha256": hashlib.sha256(b"isa" + role.encode() + basis.encode()).hexdigest(), "shots": shots,
         "options": OPTIONS, "options_sha256": fixer.options_digest(OPTIONS), "decode": decode.DECODE,
         "salt": hashlib.sha256(job.encode() + bytes([pub])).hexdigest(),
         "submitted_at": "2026-10-04T18:00:00Z", "fixed_at": "2026-10-04T18:05:00Z"}
    s["commitment"] = fixer.commitment_v3(stock="pauli-4x4", role=role, basis=basis,
                                          **{k: s[k] for k in fixer.RUN_COMMITTED})
    return s


def run(role, basis, counts, **over):
    """fix_run keeps the caller's counts list by reference (verifier-P0, round 3), so each record gets its own
    copy: a test that tampers with a record must not change LAW_COUNTS under the tests that follow."""
    counts = copy.deepcopy(counts)
    return fixer.fix_run("pauli-4x4", role, basis, counts, source(role, basis, sum(n for _, n in counts), **over))


def film(job="d3stand1n0job", **over):
    """The plan's law job (its one PUB) and coherence job (XX at PUB 0, YY at PUB 1), on one backend
    (lead.md, 16:24Z: one shot count per job)."""
    return [run("law", Z, LAW_COUNTS, pub=0, job=job, **over),
            run("coherence", XX, [[[], 6], [[0], 1], [[0, 1], 3], [[1, 7], 2]], pub=0, job=f"{job}-coh", **over),
            run("coherence", YY, [[[0], 4], [[0, 1, 5], 2], [[2], 2]], pub=1, job=f"{job}-coh", **over)]


def test_a_hardware_column_measures_the_law_run_and_both_coherence_runs():
    col = compare.run_column(film())
    assert col["label"] == "qpu: ibm_kingston" and col["kind"] == "qpu"
    assert col["jobs"] == ["d3stand1n0job", "d3stand1n0job-coh"]
    law, rec = col["law"], film()[0]
    assert law["shots"] == 13 and law["crystals_per_shot"] == {"2": 2, "5": 10, "6": 1}
    assert law["n_crystal"] == {"N": 5, "shots": 10, "share": 10 / 13}
    assert law == dict(compare.law_measures(compare.run_counts(rec), circuit_sha256=rec["source"]["circuit_sha256"]),
                       job_id="d3stand1n0job")
    xx, yy = col["coherence"]["X0X1"], col["coherence"]["Y0Y1"]
    assert (xx["value"], xx["shots"]) == ((6 - 1 + 3 - 2) / 12, 12)       # agree: [] and [0, 1]; differ: [0], [1, 7]
    assert (yy["value"], yy["shots"]) == ((-4 + 2 + 2) / 8, 8)            # [0] differs; [0, 1, 5] and [2] agree
    assert abs(yy["se"] - (1 / 8) ** 0.5) < 1e-15


def test_a_simulator_run_is_refused_from_a_hardware_column_by_name():
    sim = film(kind="simulator", backend="fake_kingston")
    with pytest.raises(ValueError, match="a simulator run is not hardware"):
        compare.run_column(sim)
    with pytest.raises(ValueError, match="a simulator run is not hardware"):
        compare.run_column([*film(), sim[1]])


def test_a_simulator_column_carries_its_own_label():
    col = compare.run_column(film(kind="simulator", backend="fake_kingston"), kind="simulator")
    assert col["label"] == "simulator: fake_kingston" and col["kind"] == "simulator"
    with pytest.raises(ValueError, match="a qpu run is not a simulator run"):
        compare.run_column([*film(kind="simulator", backend="fake_kingston")[:2], film()[2]], kind="simulator")
    with pytest.raises(ValueError, match="kind is one of"):
        compare.run_column(film(), kind="atlas-emu")


def test_a_record_the_fixer_refuses_is_refused():
    bad = copy.deepcopy(film())
    bad[0]["counts"][0][1] += 1                               # a count moved, the digest kept
    with pytest.raises(ValueError, match="compare refuses a record the fixer refuses: .*digest"):
        compare.run_column(bad)
    roll = {"format": fixer.FORMAT}
    with pytest.raises(ValueError, match="compare refuses a record the fixer refuses"):
        compare.run_column([roll])


def test_one_column_is_one_backends_runs_with_one_law_run_and_one_run_per_observable():
    with pytest.raises(ValueError, match="one column is one backend's"):
        compare.run_column([*film(), *film(backend="ibm_fez", job="d3second0job")])
    with pytest.raises(ValueError, match="one law run"):
        compare.run_column([*film(), *film(job="d3second0job")])
    with pytest.raises(ValueError, match="two coherence runs of X0X1"):
        compare.run_column([*film(), film(job="d3second0job")[1]])
    with pytest.raises(ValueError, match="no runs"):
        compare.run_column([])


def test_a_known_answer_run_is_judged_by_the_readers_rule_given_its_expected_set():
    ka = run("known-answer", Z, [[[0, 1, 3, 7, 12], 9], [[0, 1, 3, 12], 2], [[3, 8, 12, 14, 15], 1]],
             job="d3known0answer")
    col = compare.run_column([ka, *film()], expected_known_answer=[0, 1, 3, 7, 12])
    (verdict,) = col["known_answer"]
    assert verdict["holds"] and verdict["share"] == 9 / 12 and verdict["job_id"] == "d3known0answer"
    assert "known_answer" not in compare.run_column([ka, *film()])


@pytest.mark.parametrize("basis", ["X" + "Z" * 15, "XY" + "Z" * 14, "XXX" + "Z" * 13, Z, "XX" + "Z" * 13,
                                   "xx" + "Z" * 14])
def test_a_basis_that_is_not_one_pair_in_one_letter_is_refused(basis):
    with pytest.raises(ValueError, match="exactly two of the 16 qubits out of Z"):
        compare.coherence({(): 1}, basis)


def test_the_pair_may_be_any_two_qubits_and_names_them():
    m = compare.coherence({(3, 9): 2, (3,): 2}, "ZZZXZZZZZXZZZZZZ")
    assert m["observable"] == "X3X9" and m["value"] == 0.0


def write(directory, records):
    directory.mkdir(parents=True, exist_ok=True)
    for i, rec in enumerate(records):
        (directory / f"run-{i}.json").write_text(fixer.text(rec), encoding="ascii", newline="\n")


def test_device_runs_are_read_from_a_records_directory_and_grouped_by_kind_and_backend(tmp_path):
    """A records directory also holds job lines, metrics and raw results: only device runs are read, each
    through the fixer's file check; one column per kind and backend, qpu first."""
    write(tmp_path / "ibm", film())
    write(tmp_path / "dry", film(kind="simulator", backend="fake_kingston", job="d3dry0run"))
    (tmp_path / "ibm" / "job-line.json").write_text('{"format": "quantum-film/hardware-job/v1"}\n', encoding="ascii")
    (tmp_path / "ibm" / "raw.json").write_text("not json at all", encoding="ascii")
    runs = compare.device_runs([tmp_path])
    assert len(runs) == 6 and all(r["format"] == fixer.RUN_FORMAT for r in runs)
    cols = compare.run_columns(runs)
    assert [c["label"] for c in cols] == ["qpu: ibm_kingston", "simulator: fake_kingston"]
    bad = film()[0]
    bad["counts"][0][1] += 1
    write(tmp_path / "tampered", [bad])
    with pytest.raises(ValueError, match="the fixer refuses it"):
        compare.device_runs([tmp_path / "tampered"])


def test_a_column_with_coherence_runs_only_shows_them_and_dashes_elsewhere():
    col = compare.run_column(film()[1:])
    assert col["law"] is None
    rows = dict(line.split(" | ", 1) for line in compare.table([col]).splitlines()[2:])
    assert rows["| <X0X1>"] == "+0.5000 +- 0.2500 |" and rows["| N-crystal share"] == "- |"


def test_a_prediction_is_a_column_labelled_as_one():
    """tools/hw_predict.py's JSON, made here by hand with compare's own measures: the label says it is predicted,
    by which noise model and of which date; anything else is refused."""
    pred = {"format": compare.PREDICTION_FORMAT, "backend": "fake_kingston", "source": "fake", "noise": "backend",
            "calibration": "2026-04-15 09:15:15+02:00", "seed": 7,
            "circuits": [{"role": "law", "measures": compare.law_measures(compare.run_counts(film()[0]))},
                         {"role": "xx", "measures": compare.coherence(compare.run_counts(film()[1]), XX)}]}
    col = compare.prediction_column(pred)
    assert col["label"] == "predicted: fake_kingston, fake noise model, calibration 2026-04-15 09:15:15+02:00"
    assert col["kind"] == "prediction" and col["law"]["shots"] == 13 and set(col["coherence"]) == {"X0X1"}
    assert "predicted:" in compare.table([col]).splitlines()[0]
    for bad in ({"format": fixer.RUN_FORMAT}, [], None):
        with pytest.raises(ValueError, match="not a prediction"):
            compare.prediction_column(bad)


def test_the_command_line_prints_the_baselines_and_the_runs_found(tmp_path, capsys):
    write(tmp_path, film())
    assert compare.main(["table", str(tmp_path)]) == 0
    head = capsys.readouterr().out.splitlines()[0]
    assert head.endswith("| twin (exact) | twin (sample, 24576 shots) | qpu: ibm_kingston |")
    bad = film()[0]
    bad["counts"][0][1] += 1
    write(tmp_path / "tampered", [bad])
    assert compare.main(["table", str(tmp_path)]) == 1
    assert "REFUSED" in capsys.readouterr().out
    assert compare.main([]) == 2


# ---- the print rule


def test_the_print_takes_the_n_crystal_shots_of_qpu_law_runs_by_job_then_layout():
    first = film(job="d3bbbb0job")[0]
    second = run("law", Z, [[[0, 1, 2, 3, 4], 2], [[1, 2], 1]], job="d3aaaa0job")
    layouts = compare.print_layouts([first, second])
    assert layouts == [[0, 1, 2, 3, 4]] * 2 + [[0, 1, 2, 3, 4]] + [[0, 1, 2, 4, 8]] * 3 + [[0, 1, 2, 4, 9]] * 2 \
        + [[3, 6, 9, 12, 15]] * 4
    assert compare.print_layouts([second, first]) == layouts                      # the order is the rule's


def test_the_print_refuses_a_simulator_run_and_any_run_that_is_not_the_law_by_name():
    with pytest.raises(ValueError, match="a simulator run is not hardware"):
        compare.print_layouts(film(kind="simulator", backend="fake_kingston")[:1])
    with pytest.raises(ValueError, match="a coherence run is not crystal layouts"):
        compare.print_layouts(film()[1:2])
    ka = run("known-answer", Z, [[[0, 1, 3, 7, 12], 4]], job="d3known0answer")
    with pytest.raises(ValueError, match="a known-answer run is not crystal layouts"):
        compare.print_layouts([ka])


def test_the_honesty_floor_is_the_fewest_layers_develop_accepts():
    assert compare.honesty_floor() == 29
    develop.pitch_um("pauli-4x4", 29)
    with pytest.raises(develop.SheetRefused, match="honesty floor"):
        develop.pitch_um("pauli-4x4", 28)


@pytest.mark.parametrize("count, tiles, used", [(24576, 29, 24389), (16000, 23, 15341), (29, 1, 29), (115, 1, 29),
                                                (116, 2, 116)])
def test_the_geometry_is_square_tiles_at_the_floor_with_the_rest_counted(count, tiles, used):
    """24,576 layouts give the Atlas print's own geometry (tools/first_prints.py: 29 layers of 29 x 29 tiles,
    187 unused)."""
    g = compare.print_geometry(count)
    assert g["tiles"] == [tiles, tiles] and g["layers"] == 29 == g["honesty_floor"]
    assert g["used"] == used == tiles * tiles * 29 and g["left_over"] == count - used
    assert g["pitch_um"] == develop.pitch_um("pauli-4x4", 29)


def test_the_geometry_refuses_too_few_layouts_and_too_few_layers():
    with pytest.raises(develop.SheetRefused, match="do not fill one tile"):
        compare.print_geometry(28)
    with pytest.raises(develop.SheetRefused, match="honesty floor"):
        compare.print_geometry(24576, layers=28)
    deeper = compare.print_geometry(24576, layers=30)
    assert deeper["tiles"] == [28, 28] and deeper["used"] == 23520 and deeper["layers"] == 30
    for bad in (-1, 2.5, True, "24576"):
        with pytest.raises(ValueError, match="whole number"):
            compare.print_geometry(bad)

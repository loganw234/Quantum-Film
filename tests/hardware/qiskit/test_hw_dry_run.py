"""The qiskit stage: a bundle frozen afresh against fake_kingston (a Heron r2) and a dry run of its three jobs,
end to end, offline, in the IBM virtualenv; then the brief's controls on that real path. Every venv process
runs under tests/hardware/qiskit/offline.py: no network, no process but git and its own python, no write
outside the test's directory."""
import json
import sys

import pytest

import hwq

sys.path.insert(0, str(hwq.HERE.parent / "pure"))
import hwfix  # noqa: E402

from quantum_film import fixer  # noqa: E402
from quantum_film.ibm import audit, bundle, runner  # noqa: E402

pytestmark = hwq.NEEDS
JOBS = [name for name, _ in bundle.PLAN]
NAMES = [e for _j, cs in bundle.PLAN for e, *_ in cs]


@pytest.fixture(scope="module")
def frozen(tmp_path_factory):
    root = tmp_path_factory.mktemp("hwq")
    work = hwq.make_repo(root / "repo")
    p = hwq.freeze(root, work / "main" / "bundle")
    assert p.returncode == 0, hwq.out(p)
    hwq.commit_push(work, "the frozen bundle", "main/bundle")
    return root, work, work / "main" / "bundle", p


CO_AUTHOR = "Ada Tester <ada@example.com>"     # given for the law job only (test_a_co_author_...)


@pytest.fixture(scope="module")
def ran(frozen):
    root, work, bdir, _p = frozen
    return {job: hwq.dry(root, bdir, job, work / "main" / "run", *(("--co-author", CO_AUTHOR) if job == "law" else ()))
            for job in JOBS}


def test_a_fresh_freeze_holds_and_is_the_fixture_gate_for_gate(frozen):
    """Same target, seed and qiskit: the logical circuits and the gate lists are the committed fixture's byte
    for byte. The QPY files are not compared: their bytes are not reproducible (stated in bundle.py)."""
    _root, _work, bdir, p = frozen
    assert hwq.blocked_network(p) == []
    m, _digest, found = bundle.check(bdir, hwq.ROOT)
    assert found == [] and m["kind"] == "simulator" and m["backend"] == "fake_kingston"
    for name in NAMES:
        for part in ("circuit", "gates", "qasm3"):
            fresh = (bdir / (name + bundle.SUFFIX[part])).read_bytes()
            assert fresh == (hwfix.FIXTURE / "bundle" / (name + bundle.SUFFIX[part])).read_bytes(), (name, part)
    assert "ISA max_abs_error" in p.stdout and "chain [117, 105, 106" in p.stdout


def test_the_dry_run_runs_every_job_end_to_end(frozen, ran):
    root, work, _bdir, _p = frozen
    for job, p in ran.items():
        assert p.returncode == 0, (job, hwq.out(p))
        assert hwq.blocked_network(p) == []
        assert f"line anchored: {job}-line.json" in p.stdout and f"raw result written: {job}-raw.json" in p.stdout
    assert "HOLDS: the device reads in decode's order" in ran["known-answer"].stdout
    assert audit.audit(work / "main", hwq.ROOT) == ([], 3)
    hwq.commit_push(work, "the results, after their lines", "main/run")
    assert audit.audit(work / "main", hwq.ROOT, git_order=True) == ([], 3)


def test_each_line_was_pushed_before_its_result_was_read(frozen, ran):
    _root, work, _bdir, _p = frozen
    log = hwq.git(["log", "--format=%s", "--name-only", "--reverse"], work)
    for job in JOBS:
        assert f"hardware job line: {job} of bundle" in log and f"main/run/{job}-line.json" in log


def test_a_co_author_rides_in_the_line_commit_when_given_and_only_then(frozen, ran):
    """--co-author puts one Co-Authored-By trailer at the end of the line's commit message (the project's commits
    each carry one); a job run without it gets none; a value that would add lines to the message is refused."""
    root, work, bdir, _p = frozen
    bodies = [b.strip() for b in hwq.git(["log", "--format=%B%x00"], work).split("\x00") if b.strip()]
    lines = {job: [b for b in bodies if b.startswith(f"hardware job line: {job} of bundle")] for job in JOBS}
    assert all(len(found) == 1 for found in lines.values()), lines
    assert lines["law"][0].endswith(f"before any result\n\nCo-Authored-By: {CO_AUTHOR}")
    assert all("Co-Authored-By" not in lines[job][0] for job in JOBS if job != "law")
    for bad in ("Ada <ada@example.com>\nSigned-off-by: someone", " ", "Ada\r"):
        p = hwq.dry(root, bdir, "law", root / "refused-co-author", "--co-author", bad)
        assert p.returncode == 2 and "REFUSED: --co-author is one line" in p.stdout, hwq.out(p)


def test_the_known_answer_reads_back_and_every_reader_agrees(frozen, ran):
    """Each raw payload read three ways: the runtime's decoder and BitArray.get_bitstrings() (what the runner
    fixes from), BitArray.array's bytes most significant bit first, and quantum_film.ibm.raw (what the
    records test reads). The known answer's modal outcome is {0, 1, 3, 7, 12}."""
    root, work, _bdir, _p = frozen
    run = work / "main" / "run"
    check = hwq.script(root, "readers", f"""
        import json, pathlib
        from qiskit_ibm_runtime import RuntimeDecoder
        from quantum_film.ibm import raw
        out = {{}}
        for p in sorted(pathlib.Path({str(run)!r}).glob("*-raw.json")):
            text = p.read_text(encoding="utf-8")
            lib = json.loads(text, cls=RuntimeDecoder)
            ours = raw.pubs(text)
            out[p.name] = [[pub.data.meas.get_bitstrings() == s,
                            ["".join(f"{{b:08b}}" for b in row) for row in pub.data.meas.array.tolist()] == s]
                           for pub, (s, _m) in zip(lib, ours, strict=True)]
        print(json.dumps(out))
        """)
    p = hwq.venv(check, root=root)
    assert p.returncode == 0, hwq.out(p)
    agree = json.loads(p.stdout.strip().splitlines()[-1])
    assert set(agree) == {f"{j}-raw.json" for j in JOBS}
    assert all(all(flags) for pubs in agree.values() for flags in pubs)
    verdict = json.loads((run / "known-answer-verdict.json").read_text())
    assert verdict["holds"] and verdict["modal"] == list(bundle.KNOWN_ANSWER)


def test_control_6_every_record_of_a_dry_run_is_a_simulator_run(frozen, ran):
    _root, work, _bdir, _p = frozen
    records = sorted((work / "main" / "run").glob("*-pub*-*.json"))
    assert len(records) == len(NAMES)
    for path in records:
        rec, problems = fixer.check_file(path)
        assert problems == [] and rec["source"]["kind"] == "simulator" and rec["source"]["backend"] == "fake_kingston"


def test_control_9_a_second_submission_is_refused_before_it_submits(frozen, ran):
    root, work, bdir, _p = frozen
    before = sorted(p.name for p in (work / "main" / "run").iterdir())
    p = hwq.dry(root, bdir, "known-answer", work / "main" / "run")
    assert p.returncode == 2 and "REFUSED: once only: known-answer already has a line" in p.stdout
    assert "submitted known-answer: job" not in p.stdout                   # the runner's line when it submits
    assert sorted(x.name for x in (work / "main" / "run").iterdir()) == before


def control(frozen, name, job, patch):
    root, work, bdir, _p = frozen
    out_dir = work / "controls" / name
    plant = hwq.driver(root, name, patch)
    return hwq.dry(root, bdir, job, out_dir, driver=plant), out_dir


def test_control_7_a_result_asked_for_before_the_line_is_anchored_fails_the_run(frozen, ran):
    """The commit step removed (the anchor replaced by nothing): the stand-in job refuses its result."""
    p, out_dir = control(frozen, "no_anchor", "known-answer", """
        from quantum_film.ibm import runner
        real = runner.run
        def planted(*args, **kw):
            kw["anchor"] = lambda path: None
            return real(*args, **kw)
        runner.run = planted
        """)
    assert p.returncode != 0
    assert "asked for its result before the job line was committed and pushed" in hwq.out(p)
    f = runner.files(out_dir, "known-answer")
    assert f["line"].exists() and not f["raw"].exists()


def test_control_2_a_reader_in_plain_order_fails_the_known_answer(frozen, ran):
    p, out_dir = control(frozen, "plain_order", "known-answer", """
        from quantum_film.ibm import decode
        decode.ones = lambda bits, M: tuple(p for p in range(M) if bits[p] == "1")
        """)
    assert p.returncode == 3 and "DOES NOT HOLD: run nothing else until this is understood" in p.stdout
    assert not json.loads(runner.files(out_dir, "known-answer")["verdict"].read_text())["holds"]


def test_control_8_a_malformed_bitstring_never_loses_the_raw_bytes(frozen, ran):
    """One shot's string malformed, as both readers return it: decode refuses it, nothing is fixed, and the
    raw payload is on disk all the same."""
    p, out_dir = control(frozen, "malformed", "known-answer", """
        from qiskit.primitives.containers.bit_array import BitArray
        from quantum_film.ibm import raw
        real_bits, real_pubs = BitArray.get_bitstrings, raw.pubs
        def bad(strings):
            return ["00010000100010x1"] + strings[1:]
        BitArray.get_bitstrings = lambda self, *a, **k: bad(real_bits(self, *a, **k))
        raw.pubs = lambda text, *a, **k: [(bad(s), m) for s, m in real_pubs(text, *a, **k)]
        """)
    assert p.returncode == 4, hwq.out(p)
    assert "STOPPED: known-answer: nothing was fixed (ValueError: not a bitstring of 16 bits" in p.stdout
    f = runner.files(out_dir, "known-answer")
    assert f["raw"].exists() and f["raw"].stat().st_size > 0 and not list(out_dir.glob("known-answer-pub*"))


def test_control_10_a_pub_swap_planted_in_the_runner_is_caught(frozen, ran):
    p, out_dir = control(frozen, "pub_swap", "coherence", """
        from quantum_film.ibm import runner
        real = runner.results_for
        runner.results_for = lambda entries, decoded: real(entries, decoded[::-1])
        """)
    assert p.returncode == 4 and "its result carries the commitment" in p.stdout and "not its own" in p.stdout
    assert not list(out_dir.glob("coherence-pub*")) and runner.files(out_dir, "coherence")["raw"].exists()


def test_control_1_a_transpiled_circuit_with_one_gate_changed_is_refused_before_submission(frozen):
    """One sx made an x in the law's QPY and its gate list, the bundle re-sealed (every hash and commitment
    recomputed): only the ISA check can refuse it, and it does, before anything is submitted."""
    root, work, bdir, _p = frozen
    planted = root / "c1" / "bundle"
    planted.parent.mkdir()
    import shutil
    shutil.copytree(bdir, planted)
    edit = hwq.script(root, "one_gate", f"""
        import io, pathlib
        from qiskit import qpy
        from qiskit.circuit.library import XGate
        from quantum_film.ibm import bundle, isa
        d = pathlib.Path({str(planted)!r})
        (c,) = qpy.load(io.BytesIO((d / "law.qpy").read_bytes()))
        i = next(k for k in range(len(c.data) // 2, len(c.data)) if c.data[k].operation.name == "sx")
        c.data[i] = c.data[i].replace(operation=XGate())
        buf = io.BytesIO()
        qpy.dump(c, buf)
        (d / "law.qpy").write_bytes(buf.getvalue())
        (d / "law.gates.json").write_bytes(bundle.text(isa.gate_list(c)).encode("ascii"))
        print("changed gate", i)
        """)
    p = hwq.venv(edit, root=root)
    assert p.returncode == 0, hwq.out(p)
    hwfix.reseal(planted)
    p = hwq.dry(root, planted, "law", root / "c1" / "run")
    assert p.returncode == 2 and "REFUSED: the bundle does not hold" in p.stdout
    assert "law[0] law: isa: the transpiled circuit's distribution differs" in p.stdout
    assert not (root / "c1" / "run").exists() or not list((root / "c1" / "run").iterdir())


def test_control_5_a_chain_with_a_swap_is_refused_by_the_swap_free_checks(frozen):
    """research's layout_controls.py: two chain entries swapped, so the router must insert SWAPs."""
    root, _work, bdir, _p = frozen
    probe = hwq.script(root, "broken_chain", f"""
        import json, pathlib
        from qiskit import qasm2
        from qiskit.transpiler import generate_preset_pass_manager
        from qiskit_ibm_runtime.fake_provider import FakeKingston
        from quantum_film.ibm import bundle, isa
        m = bundle.load(pathlib.Path({str(bdir)!r}))[0]
        chain = list(m["jobs"][1]["circuits"][0]["chain"])
        broken = list(chain)
        broken[3], broken[12] = broken[12], broken[3]
        c = qasm2.loads(bundle.logical_qasm("law", bundle.read_source(bundle.pathlib.Path({str(hwq.ROOT)!r}))))
        be = FakeKingston()
        out = {{}}
        for name, layout in (("pinned", chain), ("broken", broken)):
            t = generate_preset_pass_manager(optimization_level=2, backend=be, seed_transpiler=11,
                                             initial_layout=layout).run(c)
            out[name] = isa.swap_free(isa.gate_list(t), be.coupling_map.get_edges(), 102)
        print(json.dumps(out))
        """)
    p = hwq.venv(probe, root=root)
    assert p.returncode == 0, hwq.out(p)
    found = json.loads(p.stdout.strip().splitlines()[-1])
    assert found["pinned"] == []
    broken = " | ".join(found["broken"])
    for needle in ("the routing permutation is not the identity", "the initial layout is not the final one",
                   "not neighbours on the logical line", "not a path of the coupling map", "where the logical circuit "
                   "needs exactly 102"):
        assert needle in broken, (needle, found["broken"])


def test_moths_route_runs_without_a_repository_and_hands_the_line_over(frozen):
    """A bundle frozen for route moth runs where Moth's CTO runs it: no git, the line written to the output
    directory and printed for him to send at once, the README saying so."""
    root, _work, _bdir, _p = frozen
    bdir, out_dir = root / "moth" / "bundle", root / "moth" / "run"
    p = hwq.venv(hwq.HW_BUNDLE, "--route", "moth", "--out", bdir, "--shots-for-tests", hwq.SHOTS, root=root)
    assert p.returncode == 0, hwq.out(p)
    m = bundle.load(bdir)[0]
    assert m["route"] == "moth" and "Send it to the owner at once" in (bdir / bundle.README).read_text()
    p = hwq.dry(root, bdir, "known-answer", out_dir)
    assert p.returncode == 0, hwq.out(p)
    assert "route moth: the job line is" in p.stdout and "Send it to the owner now, before the results" in p.stdout
    line = json.loads(runner.files(out_dir, "known-answer")["line"].read_text())
    assert line["route"] == "moth" and fixer.check_job_line(line) == []
    assert "HOLDS" in p.stdout


def test_the_isa_check_agrees_with_qiskits_own_simulator(frozen):
    """The ISA check never uses qiskit's simulators; this test does, to hold it to them: each frozen circuit's
    distribution, from quantum_film.ibm.isa and from qiskit's Statevector of the same circuit."""
    root, _work, bdir, _p = frozen
    probe = hwq.script(root, "against_qiskit", f"""
        import io, json, pathlib
        import numpy as np
        from qiskit import QuantumCircuit, qpy
        from qiskit.quantum_info import Statevector
        from quantum_film.ibm import isa
        d = pathlib.Path({str(bdir)!r})
        out = {{}}
        for name in {NAMES!r}:
            (c,) = qpy.load(io.BytesIO((d / (name + ".qpy")).read_bytes()))
            ours = isa.distribution(isa.gate_list(c))
            final = c.layout.final_index_layout(filter_ancillas=True)
            active = sorted(set(final))
            compact = c.remove_final_measurements(inplace=False)
            small = QuantumCircuit(len(active))
            pos = {{q: k for k, q in enumerate(active)}}
            for inst in compact.data:
                if inst.operation.name == "barrier":
                    continue
                small.append(inst.operation, [pos[compact.find_bit(q).index] for q in inst.qubits])
            probs = Statevector(small).probabilities_dict()
            theirs = np.zeros(2 ** 16)
            for key, pr in probs.items():
                bits = key[::-1]                     # qiskit's key: qubit 0 rightmost
                n = sum(1 << i for i, q in enumerate(final) if bits[pos[q]] == "1")
                theirs[n] += pr
            out[name] = float(np.max(np.abs(ours - theirs)))
        print(json.dumps(out))
        """)
    p = hwq.venv(probe, root=root)
    assert p.returncode == 0, hwq.out(p)
    diffs = json.loads(p.stdout.strip().splitlines()[-1])
    assert set(diffs) == set(NAMES) and max(diffs.values()) < 1e-12, diffs

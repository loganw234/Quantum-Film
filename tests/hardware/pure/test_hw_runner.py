"""The runner's order of operations (quantum_film.ibm.runner), with a stand-in for IBM: no qiskit, no network.

The stand-in submits one job per call, answers a created time, and hands over the raw payload the test chose
(in the runtime's own JSON encoding) only once the job's line has been anchored: a result asked for before
then fails the test. The bundle is the committed fixture (kind simulator, fake_kingston, test shots).
Controls 2, 6, 7, 8, 9 and 10 of the P1 brief are here in their pure form; the qiskit stage repeats them on a
real dry run."""
import datetime
import json
import subprocess
import sys

import pytest
from hwfix import KNOWN, ROOT, copy_fixture, encode_raw, manifest

from quantum_film import fixer
from quantum_film.ibm import audit, bundle, decode, raw, runner

MIRROR = "".join(reversed(KNOWN))         # the known answer read in plain order: {3, 8, 12, 14, 15}


class AnchorOrderBroken(AssertionError):
    pass


class World:
    """IBM, stood in for. `strings[k]` are PUB k's bitstrings; `echo` puts each circuit's commitment in its
    result's metadata, as the legacy sampler's result does."""

    def __init__(self, m, job, strings, echo=True, state="DONE"):
        self.m, self.job, self.strings, self.echo, self.state = m, job, strings, echo, state
        self.calls, self.anchored, self.submits = [], set(), 0
        self.created = datetime.datetime(2026, 10, 3, 18, 0, 0, 123456, tzinfo=datetime.timezone.utc)

    def submit(self):
        self.submits += 1
        self.calls.append("submit")
        return f"stand1n-{self.job}-{self.submits}"

    def created_utc(self, h):
        self.calls.append("created")
        return self.created.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def anchor(self, path):
        self.calls.append("anchor")
        self.anchored.add(path.name)

    def wait(self, h):
        self.calls.append("wait")
        return self.state

    def payload(self):
        entries = bundle.job(self.m, self.job)["circuits"]
        return encode_raw([(s, {"shots": len(s), **({"circuit_metadata": {runner.COMMITMENT_KEY: e["commitment"]}}
                                                     if self.echo else {})})
                           for e, s in zip(entries, self.strings, strict=True)])

    def fetch_raw(self, h):
        self.calls.append("fetch")
        if f"{self.job}-line.json" not in self.anchored:
            raise AnchorOrderBroken("the result was asked for before the job line was anchored")
        return self.payload()

    def status_of(self, h):
        return {"state": {"status": "Failed", "reason": "stand-in"}, "usage": {"quantum_seconds": 0}}

    def metrics_of(self, h, payload):
        return {"job_id": h, "stand_in": True}

    def now_utc(self):
        return (self.created + datetime.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def library(raw_text):
    """The stand-in for the runtime's decoder: the payload's strings, read by a path apart from raw.pubs."""
    out = []
    for pub in json.loads(raw_text)["__value__"]["pub_results"]:
        value = pub["__value__"]
        arr = value["data"]["__value__"]["fields"]["meas"]["__value__"]["array"]["__value__"]
        rows = raw._ndarray({"__type__": "ndarray", "__value__": arr}, "stand-in")
        out.append(([format(int.from_bytes(bytes(r), "big"), "016b") for r in rows.tolist()], value["metadata"]))
    return out


def check_cli(paths):
    p = subprocess.run([sys.executable, "-m", "quantum_film.fixer", "check", *paths], cwd=ROOT, capture_output=True,
                       text=True)
    return p.returncode, p.stdout + p.stderr


def run(world, out, roots=(), **over):
    m = world.m
    calls = dict(backend_name=m["backend"], kind=m["kind"], submit=world.submit, job_id=lambda h: h,
                 created_utc=world.created_utc, anchor=world.anchor, wait=world.wait, fetch_raw=world.fetch_raw,
                 decode_library=library, status_of=world.status_of, metrics_of=world.metrics_of, check_cli=check_cli,
                 now_utc=world.now_utc, log=lambda *a: None)
    calls.update(over)
    digest = bundle.sha256((world.bundle_dir / bundle.MANIFEST).read_bytes())
    return runner.run(m, digest, world.job, out, list(roots), **calls)


@pytest.fixture
def setup(tmp_path):
    bdir, _none = copy_fixture(tmp_path, run=False)
    out = tmp_path / "out"
    out.mkdir()
    m = manifest(bdir)

    def world(job, strings, **kw):
        w = World(m, job, strings, **kw)
        w.bundle_dir = bdir
        return w
    return world, out, m


def shots(m, job):
    return [e["shots"] for e in bundle.job(m, job)["circuits"]]


def test_a_known_answer_job_end_to_end(setup):
    world, out, m = setup
    (n,) = shots(m, "known-answer")
    w = world("known-answer", [[KNOWN] * (n - 3) + ["0" * 16, MIRROR, KNOWN[:-1] + "0"]])
    assert run(w, out) == 0
    assert w.calls == ["submit", "created", "anchor", "wait", "fetch"]
    f = runner.files(out, "known-answer")
    line = json.loads(f["line"].read_text())
    assert fixer.check_job_line(line) == [] and line["submitted_at"] == "2026-10-03T18:00:00.123456Z"
    assert f["raw"].read_bytes() == w.payload().encode("utf-8")
    entry = bundle.job(m, "known-answer")["circuits"][0]
    rec, problems = fixer.check_file(runner.record_path(out, "known-answer", entry))
    assert problems == [] and fixer.held_to_line(rec, line) == []
    assert rec["source"]["kind"] == "simulator" and rec["source"]["options"] == bundle.OPTIONS
    verdict = json.loads(f["verdict"].read_text())
    assert verdict["holds"] and verdict["modal"] == [0, 1, 3, 7, 12] and verdict["shots"] == n


def test_control_2_a_reader_in_plain_order_fails_the_known_answer(setup, monkeypatch):
    world, out, m = setup
    (n,) = shots(m, "known-answer")
    monkeypatch.setattr(decode, "ones", lambda bits, M: tuple(p for p in range(M) if bits[p] == "1"))
    assert run(world("known-answer", [[KNOWN] * n]), out) == 3
    verdict = json.loads(runner.files(out, "known-answer")["verdict"].read_text())
    assert not verdict["holds"] and verdict["modal"] == [3, 8, 12, 14, 15]


def test_control_7_a_result_is_never_asked_for_before_the_line_is_anchored(setup):
    """With the anchor, the stand-in hands the result over; with the commit step removed, the run fails at
    the result, the raw payload never arrives, and the line stays."""
    world, out, m = setup
    (n,) = shots(m, "known-answer")
    w = world("known-answer", [[KNOWN] * n])
    with pytest.raises(runner.Stopped, match="its result could not be fetched .AnchorOrderBroken: the result was "
                                             "asked for before the job line was anchored.") as stopped:
        run(w, out, anchor=lambda path: None)
    assert isinstance(stopped.value.__cause__, AnchorOrderBroken)
    f = runner.files(out, "known-answer")
    assert f["line"].exists() and not f["raw"].exists() and w.calls[-1] == "fetch"


def test_once_the_line_is_anchored_every_failure_names_the_job_and_how_to_resume(setup):
    world, out, m = setup
    (n,) = shots(m, "known-answer")
    w = world("known-answer", [[KNOWN] * n])

    def timed_out(h):
        raise TimeoutError("waited 3600 s")
    with pytest.raises(runner.Stopped, match="waiting for its final state failed .* --resume stand1n-known-answer-1"):
        run(w, out, wait=timed_out)
    assert w.submits == 1 and not runner.files(out, "known-answer")["raw"].exists()


def test_a_failed_job_whose_status_cannot_be_read_still_keeps_its_line(setup):
    world, out, m = setup
    w = world("known-answer", [[KNOWN] * shots(m, "known-answer")[0]], state="ERROR")

    def unreadable(h):
        raise ConnectionError("status call failed")
    with pytest.raises(runner.Stopped, match="ended ERROR, and IBM's state and usage could not be read"):
        run(w, out, status_of=unreadable)
    assert runner.files(out, "known-answer")["line"].exists()


def test_metrics_that_cannot_be_read_never_stand_in_the_way_of_the_fix(setup):
    world, out, m = setup
    w = world("known-answer", [[KNOWN] * shots(m, "known-answer")[0]])

    def unreadable(h, payload):
        raise ConnectionError("metrics call failed")
    assert run(w, out, metrics_of=unreadable) == 0
    assert json.loads(runner.files(out, "known-answer")["metrics"].read_text()) == {
        "not_read": "ConnectionError: metrics call failed"}


def test_a_line_that_cannot_be_anchored_stops_before_any_result(setup):
    world, out, m = setup
    (n,) = shots(m, "known-answer")
    w = world("known-answer", [[KNOWN] * n])

    def push_fails(path):
        raise RuntimeError("git push: rejected")
    with pytest.raises(runner.Stopped, match="could not be anchored .* run with --resume; no result was read"):
        run(w, out, anchor=push_fails)
    assert "fetch" not in w.calls and runner.files(out, "known-answer")["line"].exists()


@pytest.mark.parametrize("plant", ["malformed string", "fifteen bits", "not json", "fixed before submitted"])
def test_control_8_a_decode_error_never_loses_the_raw_bytes(setup, plant):
    world, out, m = setup
    (n,) = shots(m, "known-answer")
    w = world("known-answer", [[KNOWN] * n])
    over = {}
    if plant == "malformed string":
        over["decode_library"] = lambda text: [([KNOWN] * (n - 1) + ["00010000100010x1"], meta)
                                               for _s, meta in library(text)]
    elif plant == "fifteen bits":
        w.payload = lambda: encode_raw([([KNOWN[1:]] * n, {})], num_bits=15)
    elif plant == "not json":
        w.payload = lambda: "<html>a proxy's error page</html>"
    else:
        over["now_utc"] = lambda: "2026-10-03T17:59:59Z"       # a local clock behind IBM's
    with pytest.raises(runner.Stopped, match="nothing was fixed .* The raw bytes are on disk"):
        run(w, out, **over)
    f = runner.files(out, "known-answer")
    assert f["raw"].read_bytes() == w.payload().encode("utf-8")
    assert not list(out.glob("known-answer-pub*"))                # no record, not even a partial set
    if plant == "fixed before submitted":                         # fixed from the bytes on disk, never resubmitted
        assert runner.refix(m, "known-answer", out, decode_library=library, check_cli=check_cli,
                            now_utc=w.now_utc, log=lambda *a: None) == 0
        assert w.submits == 1


def test_control_9_a_second_submission_is_refused_before_it_submits(setup, tmp_path):
    world, out, m = setup
    (n,) = shots(m, "known-answer")
    w = world("known-answer", [[KNOWN] * n])
    assert run(w, out) == 0
    with pytest.raises(runner.Refused, match="known-answer already has a line"):
        run(w, out)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    with pytest.raises(runner.Refused, match="known-answer-line.json already holds a commitment of known-answer"):
        run(w, elsewhere, roots=[out])
    assert w.submits == 1


def test_once_only_refuses_an_unreadable_line(setup, tmp_path):
    world, out, m = setup
    (out / "law-line.json").write_text('{"job_id": 1, "job_id": 2}')
    w = world("known-answer", [[KNOWN] * shots(m, "known-answer")[0]])
    with pytest.raises(runner.Refused, match="law-line.json is not a readable job line"):
        run(w, out)
    assert w.submits == 0


def _coherence(world, m, echo=True):
    n0, n1 = shots(m, "coherence")
    a, b = "0000000000000011", "0000000000001100"         # PUB 0 reads {0, 1}, PUB 1 reads {2, 3}: told apart
    return world("coherence", [[a] * n0, [b] * n1], echo=echo), (a, b)


def test_control_10_counts_land_under_their_own_pub(setup):
    world, out, m = setup
    w, (a, b) = _coherence(world, m)
    assert run(w, out) == 0
    entries = bundle.job(m, "coherence")["circuits"]
    for e, s in zip(entries, (a, b), strict=True):
        rec = json.loads(runner.record_path(out, "coherence", e).read_text())
        assert rec["counts"] == [[list(decode.ones(s, 16)), e["shots"]]] and rec["source"]["pub"] == e["pub"]


def test_control_10_a_swap_planted_in_the_runner_is_caught_by_the_echoed_commitments(setup, monkeypatch):
    world, out, m = setup
    w, _ = _coherence(world, m)
    real = runner.results_for
    monkeypatch.setattr(runner, "results_for", lambda entries, decoded: real(entries, decoded[::-1]))
    with pytest.raises(runner.Stopped, match="its result carries the commitment .* not its own"):
        run(w, out)
    assert not list(out.glob("coherence-pub*")) and runner.files(out, "coherence")["raw"].exists()


def test_control_10_without_echoes_a_swap_is_caught_by_the_records_audit(setup, monkeypatch):
    """With no commitment echoed, a planted swap fixes each PUB's counts under the other's record: every
    record is intact, held to its line, and wrong. held_to_line cannot see it; the audit's comparison with
    the raw payload, PUB by PUB, does."""
    world, out, m = setup
    (n,) = shots(m, "known-answer")
    assert run(world("known-answer", [[KNOWN] * n]), out) == 0
    w, _ = _coherence(world, m, echo=False)
    w.created += datetime.timedelta(minutes=1)
    real = runner.results_for
    monkeypatch.setattr(runner, "results_for", lambda entries, decoded: real(entries, decoded[::-1]))
    assert run(w, out) == 0
    line = json.loads(runner.files(out, "coherence")["line"].read_text())
    for e in bundle.job(m, "coherence")["circuits"]:
        rec, problems = fixer.check_file(runner.record_path(out, "coherence", e))
        assert problems == [] and fixer.held_to_line(rec, line) == []
    found, n_lines = audit.audit(out.parent, ROOT)
    assert n_lines == 2
    assert "coherence-pub0-coherence-xx.json: its counts are not the raw payload's PUB 0 read through decode" in found
    assert "coherence-pub1-coherence-yy.json: its counts are not the raw payload's PUB 1 read through decode" in found


def test_control_6_the_kind_comes_from_the_backend_object():
    """qpu only for an IBM backend from the service that is not a simulator: a fake, Aer, or an object that
    merely carries a device's name is a simulator."""
    assert runner.kind_from(True, True, False) == "qpu"
    for args in [(False, False, True), (False, True, False), (True, False, False), (True, True, True),
                 (1, True, False), (True, 1, False), (True, True, 0)]:
        assert runner.kind_from(*args) == "simulator", args


def test_control_6_a_backend_of_another_kind_or_name_is_refused_before_submission(setup):
    world, out, m = setup
    w = world("known-answer", [[KNOWN] * shots(m, "known-answer")[0]])
    with pytest.raises(runner.Refused, match="the backend object is kind 'qpu'; the bundle's commitments bind "
                                             "'simulator'"):
        run(w, out, kind="qpu")
    with pytest.raises(runner.Refused, match="the backend is 'fake_fez'"):
        run(w, out, backend_name="fake_fez")
    assert w.submits == 0


def test_control_6_the_fixer_refuses_a_fake_named_as_a_qpu_the_second_lock(setup):
    """Were a runner to write kind qpu for the fake backend, the fixer would refuse the record."""
    world, out, m = setup
    w = world("known-answer", [[KNOWN] * shots(m, "known-answer")[0]])
    run(w, out)
    rec = json.loads(next(out.glob("known-answer-pub0-*.json")).read_text())
    with pytest.raises(ValueError, match="a qpu run's backend must be an IBM device"):
        fixer.fix_run(rec["stock"], rec["role"], rec["basis"], rec["counts"], dict(rec["source"], kind="qpu"))


def test_a_job_that_did_not_complete_keeps_its_line_and_gets_its_status(setup):
    world, out, m = setup
    w = world("known-answer", [[KNOWN] * shots(m, "known-answer")[0]], state="ERROR")
    with pytest.raises(runner.Stopped, match="ended ERROR: its line stays"):
        run(w, out)
    f = runner.files(out, "known-answer")
    assert f["line"].exists() and not f["raw"].exists() and "fetch" not in w.calls
    assert json.loads(f["status"].read_text()) == w.status_of(None)


def test_an_unreadable_created_time_stops_before_any_line(setup):
    world, out, m = setup
    w = world("known-answer", [[KNOWN] * shots(m, "known-answer")[0]])

    def no_time(h):
        raise ConnectionError("status call failed")
    with pytest.raises(runner.Stopped, match="its created time could not be read"):
        run(w, out, created_utc=no_time)
    assert not runner.files(out, "known-answer")["line"].exists()

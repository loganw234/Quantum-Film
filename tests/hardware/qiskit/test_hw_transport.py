"""The LIVE path, offline: tools/hw_bundle.py and tools/hw_run.py run against IBM's service stood in for at the
HTTP transport (recorded.py), with a fake key and a fake CRN, every request logged.

  - The key goes only to iam.cloud.ibm.com, never as `Authorization: apikey` anywhere, and every API call
    names the instance.
  - When IAM fails after its first token, the runtime's "API Key will be used instead" warning is an error:
    the run stops, and no request carries the key anywhere else.
  - The job sent is the frozen one: program sampler on ibm_fez, the options as the manifest states them, the
    cap, and each circuit gate for gate the frozen gate list with its commitment in its metadata.
  - The result is never asked for before the job's line is committed and pushed.
  - Control 6: a fake backend object that carries a device's name is still kind simulator, and a qpu bundle
    refuses it before anything is submitted.
"""
import json

import pytest

import hwq
from quantum_film import fixer
from quantum_film.ibm import account, bundle, isa, runner

pytestmark = hwq.NEEDS
RECORDED = hwq.HERE / "recorded.py"
FAKE_KEY = "FAKEKEY-not-a-credential-0123456789abcdef"
FAKE_CRN = "crn:v1:bluemix:public:quantum-computing:us-east:a/00000000:11111111-2222-3333-4444-555555555555::"


@pytest.fixture(scope="module")
def live(tmp_path_factory):
    root = tmp_path_factory.mktemp("transport")
    keys = root / "keys"
    keys.mkdir()
    (keys / "apikey.json").write_text(json.dumps({"name": "fake", "apikey": FAKE_KEY}))
    (keys / "crn.txt").write_text(FAKE_CRN + "\n")
    env = {account.KEY_VARIABLE: str(keys / "apikey.json"), account.INSTANCE_VARIABLE: str(keys / "crn.txt")}
    work = hwq.make_repo(root / "repo")
    bdir, out_dir = work / "qpu" / "bundle", work / "qpu" / "run"
    (root / "logs").mkdir()
    froze = hwq.venv(RECORDED, root / "logs" / "freeze.jsonl", "normal", out_dir, "--", hwq.HW_BUNDLE,
                     "--backend", "ibm_fez", "--route", "ibm-direct", "--out", bdir, root=root, env=env)
    assert froze.returncode == 0, hwq.out(froze)
    hwq.commit_push(work, "the frozen qpu bundle", "qpu/bundle")
    ran = hwq.venv(RECORDED, root / "logs" / "known-answer.jsonl", "normal", out_dir, "--", hwq.HW_RUN,
                   "--bundle", bdir, "--job", "known-answer", "--out", out_dir, root=root, env=env)
    return root, env, work, bdir, out_dir, froze, ran


def log(root, name):
    return [json.loads(ln) for ln in (root / "logs" / name).read_text().splitlines()]


def test_the_live_freeze_makes_a_qpu_bundle_from_the_service(live):
    root, _env, _work, bdir, _out, froze, _ran = live
    m, _digest, found = bundle.check(bdir, hwq.ROOT)
    assert found == [] and (m["kind"], m["backend"]) == ("qpu", "ibm_fez")
    assert [e["shots"] for j in m["jobs"] for e in j["circuits"]] == [1024, 24576, 4096, 4096]   # the plan's
    assert "instance: plan 'open', pricing 'free'" in froze.stdout
    assert hwq.blocked_network(froze) == []


def test_the_live_known_answer_runs_end_to_end_as_kind_qpu(live):
    root, _env, _work, bdir, out_dir, _froze, ran = live
    assert ran.returncode == 0, hwq.out(ran)
    assert "HOLDS: the device reads in decode's order" in ran.stdout
    m = bundle.load(bdir)[0]
    line = json.loads(runner.files(out_dir, "known-answer")["line"].read_text())
    assert (line["kind"], line["backend"], line["job_id"]) == ("qpu", "ibm_fez", "mockjob0000000000001")
    created = (root / "logs" / "known-answer.created.txt").read_text()     # what the stand-in IBM said, in UTC
    assert line["submitted_at"] == created                          # not job.creation_date's local time
    rec, problems = fixer.check_file(runner.record_path(out_dir, "known-answer",
                                                        bundle.job(m, "known-answer")["circuits"][0]))
    assert problems == [] and fixer.held_to_line(rec, line) == [] and rec["source"]["kind"] == "qpu"
    metrics = json.loads(runner.files(out_dir, "known-answer")["metrics"].read_text())
    assert metrics["job"]["created"] == created and metrics["metrics"]["usage"] == {"quantum_seconds": 3, "seconds": 3}
    assert set(metrics["metrics"]["timestamps"]) == {"created", "running", "finished"}
    assert "removed" not in metrics and FAKE_CRN not in json.dumps(metrics)


@pytest.mark.parametrize("name", ["freeze.jsonl", "known-answer.jsonl"])
def test_the_key_goes_only_to_iam_and_every_api_call_names_the_instance(live, name):
    root = live[0]
    entries = log(root, name)
    assert entries and all(e["status"] < 400 for e in entries), [e for e in entries if e["status"] >= 400]
    assert {e["host"] for e in entries if e["key"]} == {"iam.cloud.ibm.com"}
    assert not any(e["auth"] == "apikey" for e in entries)
    assert all(e["crn_header"] for e in entries if e["host"] == "quantum.cloud.ibm.com")
    assert not any(e.get("result_before_anchor") for e in entries)


def test_the_job_sent_is_the_frozen_one(live):
    root, _env, _work, bdir, _out, _froze, _ran = live
    m = bundle.load(bdir)[0]
    entries = log(root, "known-answer.jsonl")
    assert [e["path"] for e in entries if e["method"] == "POST" and e["host"] == "quantum.cloud.ibm.com"] == \
        ["/api/v1/jobs"]
    probe = hwq.script(root, "payload", f"""
        import json, pathlib
        from qiskit_ibm_runtime import RuntimeDecoder
        from quantum_film.ibm import isa
        raw = json.loads(pathlib.Path({str(root / 'logs' / 'payload-1.json')!r}).read_text())
        params = json.loads(json.dumps(raw["params"]), cls=RuntimeDecoder)
        print(json.dumps({{"program_id": raw["program_id"], "backend": raw["backend"], "cost": raw.get("cost"),
                          "options": raw["params"]["options"],
                          "pubs": [[isa.gate_list(c), c.metadata, shots] for c, _v, shots in params["pubs"]]}}))
        """)
    p = hwq.venv(probe, root=root)
    assert p.returncode == 0, hwq.out(p)
    sent = json.loads(p.stdout.strip().splitlines()[-1])
    job = bundle.job(m, "known-answer")
    assert (sent["program_id"], sent["backend"], sent["cost"]) == ("sampler", "ibm_fez", job["max_execution_time"])
    assert sent["options"] == m["options"] == bundle.OPTIONS
    (e,) = job["circuits"]
    (gates, metadata, shots), = sent["pubs"]
    frozen = bundle.load_json((bdir / (e["name"] + bundle.SUFFIX["gates"])).read_bytes())
    assert bundle.same_json(gates, frozen) and metadata == {runner.COMMITMENT_KEY: e["commitment"]}
    assert shots == e["shots"] and isa.read(gates) == []


def test_when_iam_fails_after_its_first_token_the_run_stops_at_once_and_the_key_stays_put(live):
    """The refusal is a BaseException raised inside the auth hook: the run ends rc 2 at the first request that
    needs a token, naming why, and no request reaches the API host. (A warnings filter alone was absorbed by
    the runtime and failed two minutes later as "No backend matches the criteria": round 3's P2, 16:58Z.)"""
    import time
    root, env, _work, bdir, out_dir, _froze, _ran = live
    t0 = time.monotonic()
    p = hwq.venv(RECORDED, root / "logs" / "fallback.jsonl", "iam_fails_later", out_dir, "--", hwq.HW_RUN,
                 "--bundle", bdir, "--job", "law", "--out", out_dir, root=root, env=env)
    took = time.monotonic() - t0
    assert p.returncode == 2, hwq.out(p)
    assert "REFUSED: IAM could not issue a token" in p.stdout and "Nothing was submitted." in p.stdout
    assert took < 60, f"{took:.0f} s: the refusal should stop the run at once"
    entries = log(root, "fallback.jsonl")
    assert any(e["host"] == "iam.cloud.ibm.com" and e["status"] == 503 for e in entries)
    assert {e["host"] for e in entries if e["key"]} == {"iam.cloud.ibm.com"}
    assert not any(e["auth"] == "apikey" for e in entries)
    assert not any(e["host"] == "quantum.cloud.ibm.com" for e in entries)
    assert not runner.files(out_dir, "law")["line"].exists()


def test_control_6_a_fake_backend_named_as_a_device_is_refused_by_a_qpu_bundle(live):
    root, _env, _work, bdir, _out, _froze, _ran = live
    plant = hwq.driver(root, "impostor", """
        from qiskit_ibm_runtime.fake_provider import FakeFez
        from qiskit_ibm_runtime.fake_provider.local_service import QiskitRuntimeLocalService

        def impostor(self, name=None, instance=None):
            backend = FakeFez()
            backend.name = "ibm_fez"                     # a fake backend that carries a device's name
            return backend
        QiskitRuntimeLocalService.backend = impostor
        """)
    p = hwq.dry(root, bdir, "coherence", root / "impostor-run", driver=plant)
    assert p.returncode == 2, hwq.out(p)
    assert "REFUSED: the backend object is kind 'simulator'; the bundle's commitments bind 'qpu'" in p.stdout
    assert not (root / "impostor-run" / "coherence-line.json").exists()


def test_a_job_whose_push_failed_is_resumed_and_never_resubmitted(live):
    """After submission the push is rejected (planted): the run stops with the job's line written and says to
    resume. The line is then pushed by hand, and --resume fetches, fixes and holds the job without a second
    submission. The coherence job (two PUBs of 4,096 shots): nothing here needs the law's 24,576."""
    root, env, work, bdir, out_dir, _froze, _ran = live
    plant = hwq.driver(root, "push_rejected", """
        from quantum_film.ibm import anchor
        def rejected(path, message):
            raise anchor.AnchorError("git push: rejected (planted)")
        anchor.commit_and_push = rejected
        """)
    p = hwq.venv(RECORDED, root / "logs" / "coherence.jsonl", "normal", out_dir, "--", plant,
                 "--bundle", bdir, "--job", "coherence", "--out", out_dir, root=root, env=env)
    assert p.returncode == 4 and "could not be anchored" in p.stdout and "run with --resume" in p.stdout
    f = runner.files(out_dir, "coherence")
    line = json.loads(f["line"].read_text())
    assert not f["raw"].exists() and not any(e.get("result_before_anchor") for e in log(root, "coherence.jsonl"))
    hwq.commit_push(work, "the coherence job's line, pushed by hand", f["line"].relative_to(work))
    p = hwq.venv(RECORDED, root / "logs" / "coherence-resume.jsonl", "normal", out_dir, "--", hwq.HW_RUN,
                 "--bundle", bdir, "--job", "coherence", "--out", out_dir, "--resume", line["job_id"], root=root,
                 env=env)
    assert p.returncode == 0, hwq.out(p)
    entries = log(root, "coherence-resume.jsonl")
    assert not any(e["method"] == "POST" and e["path"].endswith("/jobs") for e in entries)       # never resubmitted
    assert not any(e.get("result_before_anchor") for e in entries)
    m = bundle.load(bdir)[0]
    for e in bundle.job(m, "coherence")["circuits"]:
        rec, problems = fixer.check_file(runner.record_path(out_dir, "coherence", e))
        assert problems == [] and fixer.held_to_line(rec, line) == [] and rec["source"]["shots"] == 4096

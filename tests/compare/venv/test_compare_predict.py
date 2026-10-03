"""tools/hw_predict.py, run as the lead runs it: with the virtualenv's Python ($QF_IBM_PYTHON), in a subprocess,
on QPY circuits that make_circuits.py compiles for a fake Heron r2 backend. The project's Python has no qiskit, so
every step that needs it is a child process (lead.md, 15:34Z). verify/run.sh runs this directory only when
QF_IBM_PYTHON is set, and skips it by name otherwise; a test here never skips, it fails.

Nothing here reaches IBM: the fakes' own noise models, and for the live path a recorded transport with the
network refused (recorded_live.py)."""
import json
import os
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).resolve().parent
PREDICT = ROOT / "tools" / "hw_predict.py"
KEEP = ("SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "COMSPEC", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "OS")
# The round's rule for every simulation (lead.md, 17:23Z: the owner's machine was maxed out): set in every child,
# never inherited, so a gate run uncapped still runs its children capped (verifier-P2, 18:04Z: 766 s under load).
CAPS = {"OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "QISKIT_IN_PARALLEL": "FALSE"}
FAKE_KEY = "FAKEKEY-not-a-credential-0123456789abcdefgh"
FAKE_CRN = "crn:v1:bluemix:public:quantum-computing:us-east:a/00000000000000000000000000000000:11111111-2222-3333-4444-555555555555::"


def venv_python():
    py = os.environ.get("QF_IBM_PYTHON")
    assert py, "QF_IBM_PYTHON is unset: this directory is the predict stage's, which verify/run.sh skips by name"
    return py


def environment(tmp, **extra):
    """The child's environment: nothing that steers qiskit or IBM's stack, its home and temp under tmp, and the
    round's thread caps."""
    home = tmp / "home"
    home.mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k.upper() in KEEP}
    env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONNOUSERSITE="1", PYTHONIOENCODING="utf-8", TEMP=str(tmp),
               TMP=str(tmp), USERPROFILE=str(home), HOME=str(home), APPDATA=str(home), LOCALAPPDATA=str(home),
               QISKIT_SETTINGS=str(tmp / "no-such-settings.conf"), **CAPS)
    env.update(extra)
    return env


def test_every_child_runs_under_the_rounds_thread_caps(tmp):
    """What a child sees, read in the child itself: the four caps, whatever this process's own environment says."""
    p = run(["-c", "import json, os; print(json.dumps({k: os.environ.get(k) for k in "
                   "('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'QISKIT_IN_PARALLEL')}))"], tmp)
    assert p.returncode == 0 and json.loads(p.stdout) == CAPS, p.stdout + p.stderr


def run(args, tmp, cwd=None, **extra):
    return subprocess.run([venv_python(), *map(str, args)], capture_output=True, text=True, timeout=900,
                          cwd=cwd or ROOT, env=environment(tmp, **extra))


def predict(args, tmp, **extra):
    p = run([PREDICT, *args], tmp, **extra)
    assert p.returncode == 0, p.stderr[-3000:]
    return p.stdout


@pytest.fixture(scope="module")
def tmp(tmp_path_factory):
    return tmp_path_factory.mktemp("predict")


@pytest.fixture(scope="module")
def kingston(tmp):
    """The four circuits and the planted bad one, compiled for fake_kingston at level 2 with seed 11."""
    out = tmp / "kingston"
    p = run([HERE / "make_circuits.py", out, "fake_kingston"], tmp)
    assert p.returncode == 0, p.stderr[-3000:]
    return out


def test_an_ideal_run_reads_the_known_answer_in_every_shot(kingston, tmp):
    """The read-out order end to end: QPY, Aer, decode.ones. With no noise every shot is {0, 1, 3, 7, 12}."""
    out = json.loads(predict(["--noise", "none", "--known-answer", kingston / "known-answer.qpy",
                              "--shots-known-answer", 256], tmp))
    (row,) = out["circuits"]
    assert row["role"] == "known-answer" and row["expected"] == [0, 1, 3, 7, 12]
    assert row["measures"]["holds"] and row["measures"]["share"] == 1.0 and row["measures"]["modal"] == [0, 1, 3, 7, 12]


def test_an_ideal_run_of_the_compiled_law_lays_the_law(kingston, tmp):
    """The positive control of the whole chain: the compiled circuit, simulated with no noise, is a perfect sampler,
    so it lands in the floor: no shot outside five crystals, none forbidden, the fidelity 1 within its error."""
    out = json.loads(predict(["--noise", "none", "--law", kingston / "law.qpy", "--shots-law", 2048], tmp))
    m = out["circuits"][0]["measures"]
    assert m["n_crystal"]["share"] == 1.0 and m["forbidden"]["shots"] == 0
    assert m["tvd"]["value"] <= m["tvd"]["floor"]["max"]
    assert abs(m["xeb"]["value"] - 1) <= 3 * m["xeb"]["se"]


def test_an_ideal_run_of_the_coherence_circuits_reads_three_eighths(kingston, tmp):
    out = json.loads(predict(["--noise", "none", "--xx", kingston / "xx.qpy", "--yy", kingston / "yy.qpy",
                              "--shots-xx", 2048, "--shots-yy", 2048], tmp))
    got = {row["measures"]["observable"]: row["measures"] for row in out["circuits"]}
    assert set(got) == {"X0X1", "Y0Y1"}
    for m in got.values():
        assert abs(m["value"] - 0.375) <= 3 * m["se"] and m["shots"] == 2048


def test_a_noisy_prediction_states_what_it_ran_and_repeats_byte_for_byte(kingston, tmp):
    """The fake's own noise model: some shots leave the five-crystal sector. The output names the backend, the
    noise model's calibration date, the seeds and the versions, and a second run gives the same bytes."""
    args = ["--backend", "fake_kingston", "--law", kingston / "law.qpy", "--shots-law", 128,
            "--known-answer", kingston / "known-answer.qpy", "--shots-known-answer", 64, "--seed", 7, "--with-counts"]
    first, again = predict(args, tmp), predict(args, tmp)
    assert first == again
    out = json.loads(first)
    assert out["backend"] == "fake_kingston" and out["source"] == "fake" and out["noise"] == "backend"
    assert out["calibration"] == "2026-04-15 09:15:15+02:00" and out["seed"] == 7
    assert [(r["role"], r["seed_simulator"]) for r in out["circuits"]] == [("law", 7), ("known-answer", 10)]
    assert set(out["versions"]) == {"python", "qiskit", "qiskit-aer", "qiskit-ibm-runtime", "numpy", "quantum_film"}
    assert out["versions"]["qiskit"] == "2.5.2" and out["versions"]["qiskit-aer"] == "0.17.2"
    assert out["circuits"][0]["qpy_sha256"] == __import__("hashlib").sha256((kingston / "law.qpy").read_bytes()).hexdigest()
    # A leaky run: its sector measures stand on its five-crystal shots, counted here from its own counts.
    law = out["circuits"][0]
    five = sum(n for ones, n in law["counts"] if len(ones) == 5)
    assert sum(n for _, n in law["counts"]) == 128 and 0 < five < 128
    m = law["measures"]
    assert m["n_crystal"]["shots"] == five and m["n_crystal"]["share"] == five / 128
    assert m["tvd"]["floor"]["shots"] == five and m["xeb"]["shots"] == five


def test_a_prediction_takes_its_place_in_the_table_under_its_own_label(kingston, tmp):
    """The JSON hw_predict writes is what compare.prediction_column reads (the project's Python, no qiskit)."""
    from quantum_film import compare
    out = json.loads(predict(["--noise", "none", "--xx", kingston / "xx.qpy", "--shots-xx", 512], tmp))
    col = compare.prediction_column(out)
    assert col["label"] == "predicted: fake_kingston, no noise, calibration 2026-04-15 09:15:15+02:00"
    assert col["law"] is None and set(col["coherence"]) == {"X0X1"}


@pytest.mark.parametrize("args, why", [
    (["--known-answer", "bad.qpy"], "not an ISA circuit for fake_kingston: ['cz on (0, 100)']"),
    (["--backend", "fake_torino", "--law", "law.qpy"], "a fake is one of"),
    (["--backend", "ibm_kingston", "--law", "law.qpy"], "a device needs --live"),
    ([], "no circuit given"),
])
def test_what_it_cannot_honestly_run_is_refused_by_name(kingston, tmp, args, why):
    p = run([PREDICT, *args], tmp, cwd=kingston)
    assert p.returncode == 2 and why in p.stderr, p.stderr[-2000:]


# ---- the live path: refusals first, and the key only ever to IAM


@pytest.mark.parametrize("name, value", [
    ("IAM_URL", "https://iam.example.invalid"), ("IBM_CREDENTIALS_FILE", "x.env"), ("VCAP_SERVICES", "{}"),
    ("REQUESTS_CA_BUNDLE", "ca.pem"), ("CURL_CA_BUNDLE", "ca.pem"), ("SSL_CERT_FILE", "ca.pem"),
    ("SSL_CERT_DIR", "certs"), ("NETRC", "n"), ("SSLKEYLOGFILE", "keys.log"), ("GLOBAL_SEARCH_URL", "https://x"),
    ("GLOBAL_CATALOG_DISABLE_SSL", "true"), ("RESOURCE_CONTROLLER_URL", "https://x"),
    ("QISKIT_IBM_RUNTIME_LOG_FILE", "log.txt")])
def test_each_key_leak_variable_is_refused_by_name(tmp, name, value):
    p = run([PREDICT, "--check-environment"], tmp, **{name: value})
    assert p.returncode == 1 and f"REFUSED: the variable {name} is set" in p.stdout, p.stdout + p.stderr


def test_a_proxy_is_refused(tmp):
    p = run([PREDICT, "--check-environment"], tmp, HTTPS_PROXY="http://127.0.0.1:9")
    assert p.returncode == 1 and "a proxy is configured" in p.stdout and "https" in p.stdout


@pytest.mark.parametrize("where, name", [("cwd", "ibm-credentials.env"), ("home", "ibm-credentials.env"),
                                         ("home", ".netrc"), ("home", "_netrc")])
def test_a_credentials_or_netrc_file_is_refused(tmp_path, where, name):
    cwd = tmp_path / "work"
    cwd.mkdir()
    (cwd if where == "cwd" else tmp_path / "home").mkdir(exist_ok=True)
    (cwd if where == "cwd" else tmp_path / "home").joinpath(name).write_text("x\n", encoding="ascii")
    p = run([PREDICT, "--check-environment"], tmp_path, cwd=cwd)
    assert p.returncode == 1 and name in p.stdout, p.stdout + p.stderr


def test_a_clean_environment_passes_the_check(tmp):
    p = run([PREDICT, "--check-environment"], tmp)
    assert p.returncode == 0 and "no key-leak condition is present" in p.stdout, p.stdout + p.stderr


def key_files(tmp):
    key, crn = tmp / "apikey.json", tmp / "instance.txt"
    key.write_text(json.dumps({"apikey": FAKE_KEY}), encoding="ascii")
    crn.write_text(FAKE_CRN + "\n", encoding="ascii")
    return {"QF_IBM_KEY_FILE": str(key), "QF_IBM_INSTANCE_FILE": str(crn)}


def test_the_live_path_needs_its_files_and_refuses_a_key_inside_the_tree(kingston, tmp):
    p = run([PREDICT, "--live", "--backend", "ibm_fez", "--known-answer", kingston / "known-answer.qpy"], tmp)
    assert p.returncode == 2 and "needs QF_IBM_KEY_FILE" in p.stderr
    inside = dict(key_files(tmp), QF_IBM_KEY_FILE=str(ROOT / "README.md"))
    p = run([PREDICT, "--live", "--backend", "ibm_fez", "--known-answer", kingston / "known-answer.qpy"], tmp,
            **inside)
    assert p.returncode == 2 and "inside this repository" in p.stderr
    p = run([PREDICT, "--live", "--backend", "ibm_fez", "--known-answer", kingston / "known-answer.qpy"], tmp,
            IAM_URL="https://iam.example.invalid", **key_files(tmp))
    assert p.returncode == 2 and "the variable IAM_URL is set" in p.stderr


@pytest.fixture(scope="module")
def fez(tmp):
    out = tmp / "fez"
    p = run([HERE / "make_circuits.py", out, "fake_fez", "--only", "known-answer"], tmp)
    assert p.returncode == 0, p.stderr[-3000:]
    return out


def recorded(tmp, fez, scenario):
    log = tmp / f"requests-{scenario}.jsonl"
    p = run([HERE / "recorded_live.py", log, scenario, "--", "--live", "--backend", "ibm_fez", "--known-answer",
             fez / "known-answer.qpy", "--shots-known-answer", 64], tmp, **key_files(tmp))
    return p, [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]


def test_the_live_path_reads_the_device_and_sends_the_key_only_to_iam(tmp, fez):
    """Through the recorded transport: the service is built with the key, the backend and its calibration are
    read, the circuit is simulated locally, and no job is submitted; the key goes to iam.cloud.ibm.com alone."""
    p, log = recorded(tmp, fez, "normal")
    assert p.returncode == 0, p.stderr[-3000:]
    out = json.loads(p.stdout)
    assert out["backend"] == "ibm_fez" and out["source"] == "live" and out["calibration"].startswith("2025-02-26")
    assert out["circuits"][0]["measures"]["modal"] == [0, 1, 3, 7, 12]
    assert {e["host"] for e in log if e["key_in_request"]} == {"iam.cloud.ibm.com"}
    assert not any(e["auth"] == "apikey" for e in log)
    assert not any(e["method"] == "POST" and e["path"].endswith("/jobs") for e in log)
    assert any(e["host"] == "quantum.cloud.ibm.com" and e["path"].endswith("/ibm_fez/properties") for e in log)


def test_the_iam_fallback_stops_the_run_before_the_key_goes_anywhere_else(tmp, fez):
    """IAM down after the first token: qiskit-ibm-runtime would send the raw key to the API host with only a
    warning (docs/HARDWARE.md). Here the run stops at that warning, refused by name, before the request that would
    carry the key is prepared: no request reaches the API host at all. (An ordinary exception there was absorbed by
    the runtime's own handlers, which retried for two minutes and reported "No backend matches the criteria".)"""
    p, log = recorded(tmp, fez, "iam_fails_later")
    assert p.returncode == 2 and "REFUSED: IAM could not issue a token" in p.stderr, p.stderr[-2000:]
    assert {e["host"] for e in log if e["key_in_request"]} == {"iam.cloud.ibm.com"}
    assert not any(e["auth"] == "apikey" for e in log)
    assert not any(e["host"] == "quantum.cloud.ibm.com" for e in log)

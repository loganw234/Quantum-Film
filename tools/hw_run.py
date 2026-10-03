"""Run ONE job of a frozen bundle (round 3), on IBM hardware or, with --dry-run, on a local simulator.

    python tools/hw_run.py --bundle DIR --job known-answer --out DIR --dry-run      # offline: fake backend, no key
    python tools/hw_run.py --bundle DIR --job known-answer --out DIR                # live: the lead (or Moth's CTO)
    python tools/hw_run.py --bundle DIR --job law --out DIR --resume JOB_ID         # a submitted job, line anchored
    python tools/hw_run.py --bundle DIR --job law --out DIR --refix                 # fix the raw payload on disk

The jobs, in order: known-answer, then law and coherence only after the known answer has printed HOLDS.

Run it with the IBM virtualenv's Python. The order of operations is quantum_film.ibm.runner's (its docstring
lists the eleven steps); this script builds the calls it makes, and checks, before anything is submitted:
  - no key-leak condition holds (quantum_film.ibm.keyleak), before qiskit is imported;
  - qiskit-ibm-runtime is 0.50.0, the version whose private job._api_client.job_results(job_id) returns the
    raw result text below result(), and qiskit is the version the bundle was frozen with;
  - the bundle holds (quantum_film.ibm.bundle.check: every file's hash, the logical circuits to their source,
    the commitments, the SWAP-free checks and the ISA check, re-run);
  - each QPY file reads back as its frozen gate list, gate for gate, and still does after its commitment is
    put in its metadata and after the runtime's own JSON encoding of the job (RuntimeEncoder) round-trips it;
  - the options SamplerV2 will send are the manifest's (dynamical decoupling and both twirlings off, stated);
  - the backend's name is the manifest's, and its KIND, taken from the backend object, is the manifest's: qpu
    only for an IBMBackend obtained from the service, simulator for a fake or Aer backend;
  - for route ibm-direct, the output directory is in a git work tree whose head is on origin, with the bundle
    committed there unchanged (quantum_film.ibm.anchor.ready): the line can be pushed before any result.

WHY SamplerV2 (program "sampler"), deprecated on 2026-09-24 and removed no sooner than about 2026-12-24:
  - it sends exactly the three stated option paths, which the fixer requires (fixer.STATED_OPTIONS);
  - its result echoes each PUB's circuit metadata, the commitment included (verifier-P0, round 3), so each
    PUB's counts are held to their own commitment (runner.echo_problems); the executor-based Sampler zips
    client-side passthrough data by position, which checks nothing about the server's order;
  - both samplers read the same strings (verifier-P0: 78 noisy readings through each);
  - its removal falls after this round's deadline (5 October), and the runtime is pinned.
Its program is recorded in every run (`program`, which the commitment binds).

THE DRY RUN takes the same path with a local SamplerV2 on a fake backend and a stand-in job (DryRunJob) in
place of IBM's: a job id, a created time in UTC, and the raw result as IBM's client receives it (the
runtime's JSON encoding of the result). The stand-in hands the raw result over only once the job line is
anchored, so a result asked for before the line is committed and pushed fails the run. Its records are kind
simulator. A dry run of an ibm-direct bundle anchors with git like a live one, so it needs a work tree whose
origin it may push to (tests/hardware/qiskit builds a throwaway one).
"""
if __name__ != "__main__":
    raise ImportError("tools/hw_run.py is a script: run it, never import it")

import argparse  # noqa: E402
import datetime  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import pathlib  # noqa: E402
import re  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import urllib.request  # noqa: E402
import warnings  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Only the refusal module before the check: the rest (numpy, mpmath, qiskit) is imported after it (load()).
from quantum_film.ibm import keyleak  # noqa: E402

account = anchor = bundle = isa = runner = None


def load():
    """The package's modules, once the key-leak check has passed."""
    global account, anchor, bundle, isa, runner
    from quantum_film.ibm import account, anchor, bundle, isa, runner  # noqa: F811


RUNTIME = "0.50.0"
_CRN = re.compile(r"crn:v1:[A-Za-z0-9_.:/-]+")
# The fields of IBM's job record (GET /jobs/{id}) kept with the metrics: a list, so nothing else (a user id,
# the instance) rides into a record that is committed publicly.
JOB_FIELDS = ("created", "status", "state", "usage", "cost", "calibration_id", "backend", "program",
              "estimated_running_time_seconds")


def fail(msg, code=2):
    print(f"REFUSED: {msg}")
    sys.exit(code)


def utc(dt):
    if dt.tzinfo is None:
        raise ValueError("a time without a zone: refusing to guess whether it is local or UTC")
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def scrubbed(obj, path="", removed=None):
    """IBM's objects for the record, with any instance CRN removed (the CRN stays out of the repository).
    -> (object, [JSON paths whose values were removed])."""
    removed = [] if removed is None else removed
    if isinstance(obj, dict):
        return {k: scrubbed(v, f"{path}.{k}", removed)[0] for k, v in obj.items()}, removed
    if isinstance(obj, list):
        return [scrubbed(v, f"{path}[{i}]", removed)[0] for i, v in enumerate(obj)], removed
    if isinstance(obj, str) and _CRN.search(obj):
        removed.append(path or ".")
        return "<an instance CRN, removed>", removed
    if isinstance(obj, datetime.datetime):
        return utc(obj if obj.tzinfo else obj.replace(tzinfo=datetime.timezone.utc)), removed
    return obj, removed


def as_json(obj):
    """IBM's dict as JSON-able data: datetimes as UTC strings, anything else unknown as its repr."""
    return json.loads(json.dumps(obj, default=lambda o: utc(o) if isinstance(o, datetime.datetime) else repr(o)))


class DryRunJob:
    """The dry run's stand-in for IBM's RuntimeJobV2 around a local job (see the module's docstring)."""

    def __init__(self, local, line_path, route):
        self.local = local
        self.id = "dryrun-" + os.urandom(8).hex()
        self.created = datetime.datetime.now(datetime.timezone.utc)
        self.line_path, self.route = line_path, route

    def job_id(self):
        return self.id

    def anchored(self):
        if self.route == "moth":
            return self.line_path.exists()
        return anchor.anchored(self.line_path)

    def raw(self):
        if not self.anchored():
            raise RuntimeError("the dry run's stand-in job was asked for its result before the job line was "
                               "committed and pushed: the anchor's order is broken")
        from qiskit_ibm_runtime import RuntimeEncoder
        return json.dumps(self.local.result(), cls=RuntimeEncoder)

    def state(self):
        try:
            self.local.result()
        except Exception:
            return "ERROR"
        return "DONE"


def parse(argv):
    ap = argparse.ArgumentParser(description="Run one job of a frozen bundle.")
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--job", required=True, help="known-answer, law or coherence: one of the bundle's jobs")
    ap.add_argument("--out", required=True, help="the run's records directory")
    ap.add_argument("--dry-run", action="store_true", help="offline: a local simulator, kind simulator")
    ap.add_argument("--fake", help="with --dry-run: the fake backend (default: the one the bundle names)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--resume", metavar="JOB_ID", help="a submitted job whose line is anchored: wait, fetch, fix")
    mode.add_argument("--refix", action="store_true", help="fix the job's raw payload on disk; no service")
    ap.add_argument("--wait", type=float, default=3600.0, help="seconds to wait for the job's final state")
    a = ap.parse_args(argv)
    if a.fake and not a.dry_run:
        fail("--fake is for a dry run")
    if a.dry_run and a.resume:
        fail("a dry run cannot be resumed: its stand-in job lives in one process")
    return a


def check_cli(paths):
    p = subprocess.run([sys.executable, "-m", "quantum_film.fixer", "check", *paths], cwd=ROOT,
                       capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


def decode_library(raw_text):
    """The raw payload read by the library's own decoder (as result() would), each PUB's strings from
    BitArray.get_bitstrings(), the only strings decode reads."""
    from qiskit_ibm_runtime.decoders.result_decoder import ResultDecoder
    result = ResultDecoder.decode(raw_text)
    out = []
    for pub in result:
        if list(pub.data.keys()) != ["meas"]:
            raise ValueError(f"a PUB's data is {list(pub.data.keys())}, not the one register 'meas'")
        out.append((pub.data.meas.get_bitstrings(), dict(pub.metadata)))
    return out


def same_circuit_checks(manifest, bundle_dir, job_entry):
    """Load each QPY file, hold it to its frozen gate list, put its commitment in its metadata, and hold the
    runtime's own JSON encoding of it to the gate list too. -> [(circuit, shots)] in PUB order."""
    from qiskit import qpy
    from qiskit_ibm_runtime import RuntimeDecoder, RuntimeEncoder
    pubs = []
    for e in job_entry["circuits"]:
        data = (bundle_dir / (e["name"] + bundle.SUFFIX["isa"])).read_bytes()
        if bundle.sha256(data) != e["isa_sha256"]:
            fail(f"{e['name']}: the QPY file is not the manifest's")
        frozen = bundle.load_json((bundle_dir / (e["name"] + bundle.SUFFIX["gates"])).read_bytes())
        (c,) = qpy.load(io.BytesIO(data))
        if not bundle.same_json(isa.gate_list(c), frozen):
            fail(f"{e['name']}: the QPY file and the gate list are not the same circuit")
        c.metadata = {runner.COMMITMENT_KEY: e["commitment"]}
        wire = json.loads(json.dumps({"circuit": c}, cls=RuntimeEncoder), cls=RuntimeDecoder)["circuit"]
        if not bundle.same_json(isa.gate_list(wire), frozen) or wire.metadata != c.metadata:
            fail(f"{e['name']}: the runtime's encoding of the circuit is not the frozen gate list and commitment")
        pubs.append((c, None, e["shots"]))           # (circuit, parameter values, shots): a SamplerPub
    return pubs


def main(argv):
    a = parse(argv)
    bundle_dir, out_dir = pathlib.Path(a.bundle), pathlib.Path(a.out)
    if not a.refix:
        leaks = keyleak.refusals(os.environ, os.getcwd(), os.path.expanduser("~"), urllib.request.getproxies())
        if leaks:
            fail("a key-leak condition holds:\n  " + "\n  ".join(leaks))
    load()
    if a.job not in [name for name, _ in bundle.PLAN]:
        fail(f"--job {a.job!r}: a bundle's jobs are {[name for name, _ in bundle.PLAN]}")
    import qiskit
    import qiskit_ibm_runtime
    manifest, digest, problems = bundle.check(bundle_dir, ROOT)
    if problems:
        fail("the bundle does not hold:\n  " + "\n  ".join(problems))
    if qiskit_ibm_runtime.__version__ != RUNTIME or qiskit.__version__ != manifest["versions"]["qiskit"]:
        fail(f"qiskit-ibm-runtime {qiskit_ibm_runtime.__version__} and qiskit {qiskit.__version__}; this run is "
             f"pinned to runtime {RUNTIME} and to the qiskit the bundle was frozen with, "
             f"{manifest['versions']['qiskit']}")
    job_entry = bundle.job(manifest, a.job)
    print(f"bundle {digest[:16]}: {manifest['stock']} on {manifest['backend']} ({manifest['kind']}, "
          f"{manifest['route']}); job {a.job}: "
          + ", ".join(f"{e['name']} {e['shots']}" for e in job_entry["circuits"]))
    out_dir.mkdir(parents=True, exist_ok=True)
    roots = [ROOT / runner.RECORDS]
    now = lambda: utc(datetime.datetime.now(datetime.timezone.utc))  # noqa: E731

    if a.refix:
        return runner.refix(manifest, a.job, out_dir, decode_library=decode_library, check_cli=check_cli,
                            now_utc=now)

    from qiskit_ibm_runtime import IBMBackend
    if a.dry_run:
        from qiskit_ibm_runtime.fake_provider.local_service import QiskitRuntimeLocalService
        backend = QiskitRuntimeLocalService().backend(a.fake or manifest["backend"])
        from_service = False
    else:
        from qiskit_ibm_runtime import QiskitRuntimeService
        try:
            service = account.connect(QiskitRuntimeService, os.environ, ROOT)
        except PermissionError as e:
            fail(str(e))
        plan, pricing = account.plan_of(service)
        print(f"instance: plan {plan!r}, pricing {pricing!r}")
        if manifest["route"] == "ibm-direct" and plan != "open":
            fail(f"the instance's plan is {plan!r}: the ibm-direct route runs on the Open plan only")
        backend = service.backend(manifest["backend"])
        from_service = True
    simulator = bool(getattr(backend.configuration(), "simulator", True)) if hasattr(backend, "configuration") \
        else True
    kind = runner.kind_from(isinstance(backend, IBMBackend), from_service, simulator)
    if backend.name != manifest["backend"]:
        fail(f"the backend is {backend.name!r}; the bundle was frozen for {manifest['backend']!r}")
    if kind != manifest["kind"]:
        fail(f"the backend object is kind {kind!r}; the bundle's commitments bind {manifest['kind']!r}")

    line_path = runner.files(out_dir, a.job)["line"]
    if manifest["route"] == "ibm-direct":
        def anchor_line(path):
            return anchor.commit_and_push(path, f"hardware job line: {a.job} of bundle {digest[:16]} on "
                                                f"{manifest['backend']}, before any result")
    else:
        def anchor_line(path):
            print(f"route moth: the job line is {path}. Send it to the owner now, before the results:\n"
                  + path.read_text(encoding="ascii"))

    if a.resume:
        if not line_path.exists():
            fail(f"--resume needs this job's line, {line_path.name}, in the output directory")
        line = bundle.load_json(line_path.read_bytes())
        if line.get("job_id") != a.resume or runner.files(out_dir, a.job)["raw"].exists():
            fail("--resume needs this job's line, naming that job id, and no raw result yet")
        if manifest["route"] == "ibm-direct" and not anchor.anchored(line_path):
            fail("the line is not committed and pushed: anchor it before any result is read")
        handle = service.job(a.resume)
        calls = {k: v for k, v in live_calls(a).items() if k != "created_utc"}     # the line has it already
        try:
            return runner.after_anchor(manifest, a.job, out_dir, line, handle, **calls, check_cli=check_cli,
                                       now_utc=now)
        except runner.Stopped as e:
            print(f"STOPPED: {e}")
            return 4

    if manifest["route"] == "ibm-direct":
        not_ready = anchor.ready(bundle_dir, out_dir)
        if not_ready:
            fail("\n  ".join(not_ready))
    pubs = same_circuit_checks(manifest, bundle_dir, job_entry)
    from dataclasses import asdict

    from qiskit_ibm_runtime.options import SamplerOptions
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from qiskit_ibm_runtime import SamplerV2
        sampler = SamplerV2(mode=backend)
    sampler.options.dynamical_decoupling.enable = False
    sampler.options.twirling.enable_gates = False
    sampler.options.twirling.enable_measure = False
    sampler.options.max_execution_time = job_entry["max_execution_time"]
    sent = SamplerOptions._get_program_inputs(asdict(sampler.options))["options"]
    if not bundle.same_json(sent, manifest["options"]):
        fail(f"SamplerV2 would send the options {sent}, not the manifest's {manifest['options']}")

    def submit():
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Options .* have no effect in local testing mode")
            job = sampler.run(pubs)
        return DryRunJob(job, line_path, manifest["route"]) if a.dry_run else job

    calls = dry_calls() if a.dry_run else live_calls(a)
    try:
        return runner.run(manifest, digest, a.job, out_dir, roots, backend_name=backend.name, kind=kind,
                          submit=submit, job_id=lambda h: h.job_id(), anchor=anchor_line, check_cli=check_cli,
                          now_utc=now, **calls)
    except runner.Refused as e:
        fail(str(e))
    except runner.Stopped as e:
        print(f"STOPPED: {e}")
        return 4


def dry_calls():
    return {"created_utc": lambda h: utc(h.created), "wait": lambda h: h.state(), "fetch_raw": lambda h: h.raw(),
            "decode_library": decode_library,
            "status_of": lambda h: {"state": {"status": h.state()}, "usage": None},
            "metrics_of": lambda h, payload: {"dry_run": True, "job_id": h.job_id(), "created": utc(h.created),
                                              "result_metadata": json.loads(payload)["__value__"].get("metadata")}}


def live_calls(a):
    def wait(job):
        job.wait_for_final_state(timeout=a.wait)
        return job.status()

    def status_of(job):
        state = job._api_client.job_get(job.job_id()).get("state")
        usage = job._api_client.job_metadata(job.job_id()).get("usage")
        data, removed = scrubbed({"state": as_json(state), "usage": as_json(usage)})
        return dict(data, **({"removed": removed} if removed else {}))

    def metrics_of(job, payload):
        """The job's metrics as IBM returns them (created, running and finished times, usage), the fields of its
        record named in JOB_FIELDS (the calibration id among them, when IBM gives one), and the result's own
        metadata (its execution spans). A CRN anywhere is removed, and said so."""
        metrics = as_json(job.metrics())
        record = job._api_client.job_get(job.job_id())
        fields = {k: as_json(record[k]) for k in JOB_FIELDS if k in record}
        result_metadata = json.loads(payload)["__value__"].get("metadata")
        data, removed = scrubbed({"job_id": job.job_id(), "job": fields, "metrics": metrics,
                                  "result_metadata": result_metadata,
                                  "backend": job.backend().name if job.backend() else None})
        if _CRN.search(payload):
            print("WARNING: the raw payload holds an instance CRN; scrub it before the run is committed")
        return dict(data, **({"removed": removed} if removed else {}))

    return {"created_utc": lambda job: utc(job.creation_date), "wait": wait,
            "fetch_raw": lambda job: job._api_client.job_results(job.job_id()), "decode_library": decode_library,
            "status_of": status_of, "metrics_of": metrics_of}


def refused_fallback(argv):
    """What a FallbackRefused stopped, said plainly: before or after the job was submitted."""
    a = parse(argv)
    load()
    line = runner.files(pathlib.Path(a.out), a.job)["line"]
    after = (f" The job was submitted and its line {line.name} is written: once IAM answers, run again with "
             "--resume JOB_ID (the line names it); never resubmit." if line.exists() else
             " Nothing was submitted.")
    print("REFUSED: IAM could not issue a token, and qiskit-ibm-runtime would now send the API key itself to the API "
          "host (docs/HARDWARE.md); stopped before that request: the key went only to IAM." + after)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except keyleak.FallbackRefused:
        sys.exit(refused_fallback(sys.argv[1:]))

"""Freeze a hardware bundle (round 3): the plan's circuits compiled for one backend, checked, committed to.

    python tools/hw_bundle.py --route ibm-direct --out DIR                    # against fake_kingston, offline
    python tools/hw_bundle.py --fake fake_fez --route moth --out DIR
    python tools/hw_bundle.py --backend ibm_kingston --route ibm-direct --out DIR    # the live target: the lead only

Run it with the IBM virtualenv's Python (qiskit 2.5.2, qiskit-ibm-runtime 0.50.0). In order, it:
  1. refuses to start under any key-leak condition (quantum_film.ibm.keyleak), before it imports qiskit;
  2. reaches the backend: a fake one by name (kind simulator), or the live one through the named instance
     (quantum_film.ibm.account, with QF_IBM_KEY_FILE and QF_IBM_INSTANCE_FILE; kind qpu), and reads its target;
     against the live backend this is a read with the owner's key, and no job;
  3. writes each logical circuit as OpenQASM 2, derived from the committed source circuit ed767c01bd4b851d
     (quantum_film.ibm.bundle.logical_qasm), and checks qiskit reads it as exactly the circuit measure_all
     builds;
  4. compiles the law at optimization level 2 with a fixed seed, so the calibration chooses its chain, and the
     other three circuits at level 2 on that same chain (pinned), so every circuit reads the same qubits;
  5. checks every transpiled circuit: the five SWAP-free checks, and this package's own ISA check
     (quantum_film.ibm.isa), which simulates the gate list without qiskit and holds the law to det(K_Y), the
     coherence circuits to <X0X1> and <Y0Y1>, and the known answer to its outcome;
  6. writes each transpiled circuit as QPY (what the runner submits), as a gate list (what the ISA check
     reads) and as OpenQASM 3 (to read), and checks the QPY file reads back as the gate list;
  7. records the estimated success probability with the chain; draws a salt per circuit from os.urandom;
     forms each commitment v3; computes the options as SamplerV2 will send them and refuses unless they are
     the bundle's (dynamical decoupling and both twirlings off, stated);
  8. writes README.md and manifest.json, and holds the whole directory with quantum_film.ibm.bundle.check, the
     same check the runner and the records test make.
Commit the bundle before it is run: its manifest's SHA-256 is its identity.
"""
if __name__ != "__main__":
    raise ImportError("tools/hw_bundle.py is a script: run it, never import it")

import argparse  # noqa: E402
import importlib.metadata  # noqa: E402
import io  # noqa: E402
import os  # noqa: E402
import pathlib  # noqa: E402
import platform  # noqa: E402
import sys  # noqa: E402
import urllib.request  # noqa: E402
import warnings  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Only the refusal module before the check: the rest (numpy, mpmath, qiskit) is imported after it (load()).
from quantum_film.ibm import keyleak  # noqa: E402

__version__ = fixer = account = bundle = decode = isa = runner = None


def load():
    """The package's modules, once the key-leak check has passed."""
    global __version__, fixer, account, bundle, decode, isa, runner
    from quantum_film import __version__, fixer  # noqa: F811
    from quantum_film.ibm import account, bundle, decode, isa, runner  # noqa: F811


QISKIT, RUNTIME = "2.5.2", "0.50.0"
# The basis rotations, built gate by gate on the qiskit side, apart from the text bundle.logical_qasm writes:
# the two must agree (step 3).
ROTATION_GATES = {"law": (), "coherence-xx": (("h", 0), ("h", 1)),
                  "coherence-yy": (("sdg", 0), ("h", 0), ("sdg", 1), ("h", 1))}


def fail(msg, code=2):
    print(f"REFUSED: {msg}")
    sys.exit(code)


def parse(argv):
    ap = argparse.ArgumentParser(description="Freeze a hardware bundle for one backend.")
    where = ap.add_mutually_exclusive_group()
    where.add_argument("--fake", help="a fake backend's name (default fake_kingston): offline, kind simulator")
    where.add_argument("--backend", help="a live IBM backend's name: needs the key files; the lead only")
    ap.add_argument("--route", required=True, choices=("ibm-direct", "moth"))
    ap.add_argument("--out", required=True, help="the bundle directory to write; it must not exist or be empty")
    ap.add_argument("--seed", type=int, default=11, help="seed_transpiler (default 11)")
    ap.add_argument("--max-execution-time", default=None,
                    help="seconds of QPU time per job, known-answer,law,coherence (default: the bundle module's "
                         "MAX_EXECUTION_TIME)")
    ap.add_argument("--shots-for-tests", default=None,
                    help="shots per job, known-answer,law,coherence; for a fake backend only (tests)")
    a = ap.parse_args(argv)
    if a.backend is None and a.fake is None:
        a.fake = "fake_kingston"
    if a.shots_for_tests and a.backend:
        fail("--shots-for-tests is for a fake backend only: a qpu bundle takes the plan's shots")
    return a


def calibration_of(backend):
    try:
        props = backend.properties()
        when = getattr(props, "last_update_date", None)
    except Exception:            # a backend that states no properties
        when = None
    if when is None:
        return "not stated by the backend"
    import datetime
    if when.tzinfo is None:
        when = when.replace(tzinfo=datetime.timezone.utc)
    return when.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def errors_of(target, doc):
    out = {}
    for name, qs, _c, _p in doc["gates"]:
        if name == "barrier":
            continue
        try:
            props = target[name][tuple(qs)]
        except KeyError:
            continue
        if props is not None and props.error is not None:
            out[f"{name}:{','.join(map(str, qs))}"] = float(props.error)
    return out


def main(argv):
    a = parse(argv)
    out = pathlib.Path(a.out)
    if out.exists() and any(out.iterdir()):
        fail(f"{out} is not empty: a bundle is written once, into a new directory")
    if a.backend:
        leaks = keyleak.refusals(os.environ, os.getcwd(), os.path.expanduser("~"), urllib.request.getproxies())
        if leaks:
            fail("a key-leak condition holds:\n  " + "\n  ".join(leaks))
    load()

    import qiskit
    import qiskit_ibm_runtime
    from qiskit import qasm2, qasm3, qpy
    from qiskit.transpiler import generate_preset_pass_manager
    if (qiskit.__version__, qiskit_ibm_runtime.__version__) != (QISKIT, RUNTIME):
        fail(f"qiskit {qiskit.__version__} and qiskit-ibm-runtime {qiskit_ibm_runtime.__version__}; this tool is "
             f"pinned to {QISKIT} and {RUNTIME}")

    if a.backend:
        from qiskit_ibm_runtime import IBMBackend, QiskitRuntimeService
        try:
            service = account.connect(QiskitRuntimeService, os.environ, ROOT)
        except PermissionError as e:
            fail(str(e))
        plan, pricing = account.plan_of(service)
        print(f"instance: plan {plan!r}, pricing {pricing!r}")
        backend = service.backend(a.backend)
        kind = runner.kind_from(isinstance(backend, IBMBackend), True,
                                bool(getattr(backend.configuration(), "simulator", True)))
    else:
        from qiskit_ibm_runtime.fake_provider.local_service import QiskitRuntimeLocalService
        backend = QiskitRuntimeLocalService().backend(a.fake)
        kind = runner.kind_from(False, False, True)
    if kind == "qpu" and backend.name not in fixer.IBM_DEVICES:
        fail(f"{backend.name} is not in fixer.IBM_DEVICES: the lead adds a device there by name before a bundle is "
             "frozen for it")
    target = backend.target
    edges = sorted({tuple(sorted(e)) for e in backend.coupling_map.get_edges()})
    print(f"backend {backend.name} ({kind}), {target.num_qubits} qubits, calibration {calibration_of(backend)}")

    jobs = [name for name, _ in bundle.PLAN]
    shots = {name: n for _job, cs in bundle.PLAN for name, _r, _b, n in cs}
    if a.shots_for_tests:
        values = [int(x) for x in a.shots_for_tests.split(",")]
        if len(values) != len(jobs) or min(values) < 1:
            fail(f"--shots-for-tests takes {len(jobs)} positive numbers, one per job: {','.join(jobs)}")
        shots = {name: n for (_job, cs), n in zip(bundle.PLAN, values, strict=True) for name, _r, _b, _s in cs}
    met = dict(bundle.MAX_EXECUTION_TIME)
    if a.max_execution_time:
        values = [int(x) for x in a.max_execution_time.split(",")]
        if len(values) != len(jobs):
            fail(f"--max-execution-time takes {len(jobs)} numbers, one per job: {','.join(jobs)}")
        met = dict(zip(jobs, values, strict=True))

    source = bundle.read_source(ROOT)
    out.mkdir(parents=True, exist_ok=True)

    # 3. the logical circuits, as text derived from the source, read back by qiskit
    from qiskit import QuantumCircuit
    logical = {}
    for _job, cs in bundle.PLAN:
        for name, _role, _basis, _shots in cs:
            text = bundle.logical_qasm(name, source)
            c = qasm2.loads(text)
            if name == "known-answer":
                built = QuantumCircuit(bundle.M)
                for q in bundle.KNOWN_ANSWER:
                    built.x(q)
            else:
                built = qasm2.loads(source)
                for gate, q in ROTATION_GATES[name]:
                    getattr(built, gate)(q)
            built.measure_all()
            if c != built:
                fail(f"{name}: qiskit does not read the derived text as the circuit measure_all builds")
            c.name = name
            logical[name] = (text, c)

    # 4. compile: the law chooses the chain; the others are pinned to it
    def compile_(c, chain=None):
        pm = generate_preset_pass_manager(optimization_level=bundle.OPTIMIZATION_LEVEL, backend=backend,
                                          seed_transpiler=a.seed, initial_layout=chain)
        return pm.run(c)

    transpiled = {"law": compile_(logical["law"][1])}
    chain = transpiled["law"].layout.initial_index_layout(filter_ancillas=True)
    for name in ("known-answer", "coherence-xx", "coherence-yy"):
        transpiled[name] = compile_(logical[name][1], chain)

    # 5-7. check, write, commit
    from dataclasses import asdict

    from qiskit_ibm_runtime.options import SamplerOptions
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from qiskit_ibm_runtime import SamplerV2
        sampler = SamplerV2(mode=backend)
    sampler.options.dynamical_decoupling.enable = False
    sampler.options.twirling.enable_gates = False
    sampler.options.twirling.enable_measure = False
    options = SamplerOptions._get_program_inputs(asdict(sampler.options))["options"]
    if not bundle.same_json(options, bundle.OPTIONS):
        fail(f"SamplerV2 would send the options {options}, not the bundle's {bundle.OPTIONS}")

    manifest = {"format": bundle.FORMAT, "stock": bundle.STOCK, "kind": kind, "route": a.route,
                "backend": backend.name, "program": bundle.PROGRAM, "decode": decode.DECODE,
                "options": options, "options_sha256": fixer.options_digest(options),
                "known_answer": list(bundle.KNOWN_ANSWER), "pair": list(bundle.PAIR),
                "source": {"path": bundle.SOURCE, "sha256": bundle.SOURCE_SHA256},
                "target": {"name": backend.name, "num_qubits": int(target.num_qubits),
                           "calibration": calibration_of(backend), "coupling": [list(e) for e in edges]},
                "compile": {"optimization_level": bundle.OPTIMIZATION_LEVEL, "seed_transpiler": a.seed,
                            "layout": "the law's, chosen at level 2 against this target's calibration; the other "
                                      "circuits pinned to it"},
                "versions": {"python": platform.python_version(), "qiskit": qiskit.__version__,
                             "qiskit_ibm_runtime": qiskit_ibm_runtime.__version__,
                             "qiskit_aer": importlib.metadata.version("qiskit-aer"),
                             "numpy": importlib.metadata.version("numpy"), "qpy": str(qpy.QPY_VERSION),
                             "quantum_film": __version__},
                "frozen_at": bundle.utc_now(), "readme_sha256": None, "jobs": []}
    for job_name, cs in bundle.jobs():
        entries = []
        for pub, name, role, basis, _shots in cs:
            t = transpiled[name]
            doc = isa.gate_list(t)
            if isa.read(doc):
                fail(f"{name}: {isa.read(doc)}")
            sf = isa.swap_free(doc, edges, bundle.CZ[name])
            if sf:
                fail(f"{name}: " + "; ".join(sf))
            held, values = bundle.hold_isa(doc, name, role, basis, source)
            if held:
                fail(f"{name}: " + "; ".join(held))
            text, _c = logical[name]
            files = {"circuit": text.encode("ascii"), "gates": bundle.text(doc).encode("ascii"),
                     "qasm3": qasm3.dumps(t).encode("ascii")}
            buf = io.BytesIO()
            qpy.dump(t, buf)
            files["isa"] = buf.getvalue()
            again = qpy.load(io.BytesIO(files["isa"]))[0]
            if not bundle.same_json(isa.gate_list(again), doc):
                fail(f"{name}: the QPY file does not read back as the gate list")
            for part, data in files.items():
                (out / (name + bundle.SUFFIX[part])).write_bytes(data)
            entry = {"pub": pub, "name": name, "role": role, "basis": basis, "shots": shots[name],
                     "source_sha256": None if role == "known-answer" else bundle.SOURCE_SHA256,
                     "circuit_sha256": bundle.sha256(files["circuit"]), "isa_sha256": bundle.sha256(files["isa"]),
                     "gates_sha256": bundle.sha256(files["gates"]), "qasm3_sha256": bundle.sha256(files["qasm3"]),
                     "chain": doc["layout"]["initial"], "esp": isa.esp(doc, errors_of(target, doc)),
                     "isa": values, "salt": os.urandom(32).hex(), "commitment": None}
            entries.append(entry)
            print(f"  {job_name}[{pub}] {name:13s} {len(doc['gates'])} gates, ESP {entry['esp']:.3f}, ISA "
                  + ", ".join(f"{k} {v:.2e}" for k, v in values.items()))
        manifest["jobs"].append({"job": job_name, "max_execution_time": met[job_name], "circuits": entries})
    for j in manifest["jobs"]:
        for e in j["circuits"]:
            e["commitment"] = bundle.commitment(manifest, e)
    readme = bundle.readme(manifest).encode("ascii")
    (out / bundle.README).write_bytes(readme)
    manifest["readme_sha256"] = bundle.sha256(readme)
    (out / bundle.MANIFEST).write_bytes(bundle.text(manifest).encode("ascii"))

    # 8. the same check the runner and the records test make
    _m, digest, problems = bundle.check(out, ROOT)
    if problems:
        fail("the bundle written does not hold:\n  " + "\n  ".join(problems))
    print(f"chain {chain}")
    print(f"bundle {out}: manifest {digest}")
    print("commit it before it runs: its manifest's SHA-256 is its identity")
    return 0


try:
    sys.exit(main(sys.argv[1:]))
except keyleak.FallbackRefused:
    print("REFUSED: IAM could not issue a token, and qiskit-ibm-runtime would now send the API key itself to the API "
          "host (docs/HARDWARE.md); stopped before that request: the key went only to IAM. Nothing was written.")
    sys.exit(2)

#!/usr/bin/env python3
"""Predictions for a frozen bundle's circuits: what the hardware is predicted to lay (round 3, P2).

A noisy simulation of the device, never the device: AerSimulator.from_backend(backend) with a fixed seed, on
exactly the transpiled circuits the bundle holds (QPY files, given by path; the manifest is not read here). Every
shot is read through quantum_film.ibm.decode and measured by quantum_film.compare, so a prediction and a
hardware run are scored by the same code. It runs in the lead's virtualenv (qiskit, qiskit-aer and
qiskit-ibm-runtime), never in the project's Python, and writes nothing but the JSON it is asked to write.

    $QF_IBM_PYTHON tools/hw_predict.py --backend fake_kingston --law LAW.qpy [--xx XX.qpy] [--yy YY.qpy]
                                       [--known-answer KA.qpy] [--seed 20261003] [--out PREDICTION.json]
    $QF_IBM_PYTHON tools/hw_predict.py --backend ibm_kingston --live ...   the lead only: the device's own
                                       calibration, read with the key; never a job
    $QF_IBM_PYTHON tools/hw_predict.py --check-environment                 the live path's refusals, alone

Per circuit, in the order law, xx, yy, known-answer (its place i, from 0): load the QPY (one circuit, its bytes'
SHA-256 stated); refuse it unless the backend's target supports every instruction on its qubits; simulate its
shots with seed_simulator = seed + i; read each bitstring with decode.ones; measure:
  - law: compare.law_measures (crystals per shot, N-crystal and forbidden shares, the TVD and its floor, the
    cross-entropy fidelity, one-site and pair z, the nearest-neighbour pair correlation);
  - xx, yy: compare.coherence, <X0X1> or <Y0Y1> with its error (basis "XX" or "YY" then fourteen Z);
  - known-answer: decode.known_answer against --expected (the plan's {0, 1, 3, 7, 12} by default).
The output states the backend, its calibration date (backend.properties().last_update_date), the noise
(--noise backend, the default; or none, an ideal run of the same circuits as a control), the seeds, and the
versions of Python, qiskit, qiskit-aer, qiskit-ibm-runtime, numpy and this package. It has no wall-clock time:
the same inputs give the same bytes, on the same versions. Aer's sampling is Aer's own (C++) random stream, so a
prediction is reproducible on the same Aer version, not across versions.

THE LIVE PATH reads IBM's key, so before anything it refuses every condition docs/HARDWARE.md lists (each by
name): the variables that redirect the key or the tokens, or switch off TLS checks; an ibm-credentials.env in
the working or home directory; a proxy (urllib.request.getproxies(), the registry's on Windows); a CA bundle;
a netrc; SSLKEYLOGFILE; the variables the SDK reads for the services this stack configures (GLOBAL_SEARCH_*,
GLOBAL_CATALOG_*: their URLs and TLS switches); a runtime log file. It also refuses RESOURCE_CONTROLLER_*, read only
when an instance is named rather than given as a CRN. This list is a copy until the merge, when the lead points
the live path at P1's refusal module (lead.md, 16:05Z). The key and the instance come from QF_IBM_KEY_FILE and
QF_IBM_INSTANCE_FILE, files outside this repository; the service is named explicitly (channel, token, instance);
IAM's "API Key will be used instead" fallback is an error, raised before any request carries the key; nothing is
saved, nothing printed, no job submitted.
"""
if __name__ != "__main__":
    raise ImportError("this script simulates a device and can read IBM's key; run it, never import it (CLAUDE.md)")

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import pathlib  # noqa: E402
import platform  # noqa: E402
import sys  # noqa: E402
import urllib.request  # noqa: E402
import warnings  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ROLES = ("law", "xx", "yy", "known-answer")
BASIS = {"law": "Z" * 16, "xx": "XX" + "Z" * 14, "yy": "YY" + "Z" * 14, "known-answer": "Z" * 16}
SHOTS = {"law": 24576, "xx": 4096, "yy": 4096, "known-answer": 1024}          # docs/ROUND3.md, the bundle's table
EXPECTED = (0, 1, 3, 7, 12)                                                    # the known-answer circuit's X gates
FAKES = {"fake_kingston": "FakeKingston", "fake_fez": "FakeFez", "fake_marrakesh": "FakeMarrakesh"}
SEED = 20261003
# docs/HARDWARE.md's refusals, by name. The prefixes: ibm_cloud_sdk_core's configure_service(name) reads every
# variable starting with the service's upper-cased name and takes its URL and its TLS switch from them
# (base_service.py:160-193); qiskit-ibm-runtime configures global_search and global_catalog, and resource_controller
# when an instance is given by name rather than as a CRN (accounts/account.py:353-360, accounts/utils.py:72-76).
REFUSED_VARIABLES = ("IAM_URL", "IBM_CREDENTIALS_FILE", "VCAP_SERVICES", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE",
                     "SSL_CERT_FILE", "SSL_CERT_DIR", "NETRC", "SSLKEYLOGFILE", "QISKIT_IBM_RUNTIME_LOG_FILE")
REFUSED_PREFIXES = ("GLOBAL_SEARCH", "GLOBAL_CATALOG", "RESOURCE_CONTROLLER")
IAM_FALLBACK = "Unable to retrieve IBM Cloud access token"


class Refused(SystemExit):
    def __init__(self, why):
        super().__init__(2)
        self.why = why


def refusals(environ=None, cwd=None, home=None):
    """Every key-leak condition present, by name; [] when none is."""
    environ = os.environ if environ is None else environ
    cwd = pathlib.Path(os.getcwd() if cwd is None else cwd)
    home = pathlib.Path(os.path.expanduser("~") if home is None else home)
    out = [f"the variable {name} is set" for name in sorted(environ)
           if name.upper() in REFUSED_VARIABLES or name.upper().startswith(REFUSED_PREFIXES)]
    out += [f"a credentials file is present: {where}/ibm-credentials.env" for where, d in (("the working directory",
            cwd), ("the home directory", home)) if (d / "ibm-credentials.env").exists()]
    out += [f"a netrc file is present in the home directory: {n}" for n in (".netrc", "_netrc") if (home / n).exists()]
    proxies = urllib.request.getproxies()
    if proxies:
        out.append(f"a proxy is configured (urllib.request.getproxies() names {sorted(proxies)})")
    return out


def inside_repository(path):
    p = pathlib.Path(path).resolve()
    return p == ROOT or ROOT in p.parents


def live_backend(name):
    """The device's backend object, read with the key and no job. Refuses first; the fallback is an error."""
    found = refusals()
    if found:
        raise Refused("the live path refuses to start: " + "; ".join(found))
    files = {}
    for var in ("QF_IBM_KEY_FILE", "QF_IBM_INSTANCE_FILE"):
        path = os.environ.get(var)
        if not path:
            raise Refused(f"the live path needs {var}, naming a file outside this repository")
        if inside_repository(path):
            raise Refused(f"{var} names a file inside this repository; the key never enters the tree")
        files[var] = path
    with open(files["QF_IBM_KEY_FILE"], encoding="utf-8") as f:
        key = json.load(f).get("apikey")
    with open(files["QF_IBM_INSTANCE_FILE"], encoding="utf-8") as f:
        crn = f.read().strip()
    if not (isinstance(key, str) and key and crn.startswith("crn:")):
        raise Refused("QF_IBM_KEY_FILE holds no apikey, or QF_IBM_INSTANCE_FILE no CRN")
    warnings.filterwarnings("error", message=IAM_FALLBACK, category=UserWarning)
    from qiskit_ibm_runtime import QiskitRuntimeService
    service = QiskitRuntimeService(channel="ibm_quantum_platform", token=key, instance=crn)
    del key
    return service.backend(name)


def fake_backend(name):
    if name not in FAKES:
        raise Refused(f"--backend {name!r}: a fake is one of {sorted(FAKES)}; a device needs --live")
    from qiskit_ibm_runtime import fake_provider
    return getattr(fake_provider, FAKES[name])()


def load_circuit(path):
    from qiskit import qpy
    raw = pathlib.Path(path).read_bytes()
    with open(path, "rb") as f:
        circuits = qpy.load(f)
    if len(circuits) != 1:
        raise Refused(f"{pathlib.Path(path).name}: {len(circuits)} circuits; a bundle's QPY holds one")
    qc = circuits[0]
    if [(r.name, r.size) for r in qc.cregs] != [("meas", 16)]:
        raise Refused(f"{pathlib.Path(path).name}: its classical register is not measure_all's 16-bit 'meas', "
                      "so quantum_film.ibm.decode's contract does not hold")
    return qc, hashlib.sha256(raw).hexdigest()


def unsupported(qc, target):
    """The instructions the backend's target does not support on their qubits (barriers aside)."""
    out = []
    for inst in qc.data:
        name = inst.operation.name
        if name == "barrier":
            continue
        qargs = tuple(qc.find_bit(q).index for q in inst.qubits)
        if not target.instruction_supported(operation_name=name, qargs=qargs):
            out.append(f"{name} on {qargs}")
    return out


def calibration(backend):
    props = backend.properties()
    when = getattr(props, "last_update_date", None)
    return None if when is None else str(when)


def counts_read(raw_counts):
    from quantum_film.ibm import decode
    out = {}
    for bits, n in raw_counts.items():
        key = decode.ones(bits, 16)
        out[key] = out.get(key, 0) + int(n)
    return out


def measure(role, counts, expected):
    from quantum_film import compare
    from quantum_film.ibm import decode
    if role == "law":
        return compare.law_measures(counts)
    if role in ("xx", "yy"):
        return compare.coherence(counts, BASIS[role])
    return decode.known_answer(counts, expected, 16)


def versions():
    from importlib.metadata import version

    import quantum_film
    return {"python": platform.python_version(), "qiskit": version("qiskit"), "qiskit-aer": version("qiskit-aer"),
            "qiskit-ibm-runtime": version("qiskit-ibm-runtime"), "numpy": version("numpy"),
            "quantum_film": quantum_film.__version__}


def predict(args):
    from qiskit_aer import AerSimulator

    from quantum_film.compare import PREDICTION_FORMAT
    backend = live_backend(args.backend) if args.live else fake_backend(args.backend)
    cal = calibration(backend)
    out = {"format": PREDICTION_FORMAT, "backend": backend.name, "source": "live" if args.live else "fake",
           "calibration": cal, "noise": args.noise,
           "simulator": "AerSimulator.from_backend(backend)" if args.noise == "backend" else "AerSimulator()",
           "seed": args.seed, "versions": versions(), "circuits": []}
    expected = tuple(sorted(args.expected))
    for i, role in enumerate(ROLES):
        path = getattr(args, role.replace("-", "_"))
        if path is None:
            continue
        qc, sha = load_circuit(path)
        bad = unsupported(qc, backend.target)
        if bad:
            raise Refused(f"{pathlib.Path(path).name}: not an ISA circuit for {backend.name}: {bad[:5]}")
        shots = getattr(args, "shots_" + role.replace("-", "_"))
        seed = args.seed + i
        sim = AerSimulator.from_backend(backend, seed_simulator=seed) if args.noise == "backend" \
            else AerSimulator(seed_simulator=seed)
        raw = sim.run(qc, shots=shots).result().get_counts()
        counts = counts_read(raw)
        row = {"role": role, "file": pathlib.Path(path).name, "qpy_sha256": sha, "basis": BASIS[role],
               "shots": shots, "seed_simulator": seed, "measures": measure(role, counts, expected)}
        if role == "known-answer":
            row["expected"] = list(expected)
        if args.with_counts:
            row["counts"] = [[list(k), n] for k, n in sorted(counts.items())]
        out["circuits"].append(row)
    if not out["circuits"]:
        raise Refused("no circuit given: --law, --xx, --yy or --known-answer")
    return out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--backend", default="fake_kingston")
    ap.add_argument("--live", action="store_true", help="the lead only: the device's own calibration, with the key")
    for role in ROLES:
        ap.add_argument(f"--{role}", metavar="QPY")
        ap.add_argument(f"--shots-{role}", type=int, default=SHOTS[role])
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--noise", choices=("backend", "none"), default="backend")
    ap.add_argument("--expected", type=lambda s: [int(q) for q in s.split(",")], default=list(EXPECTED))
    ap.add_argument("--with-counts", action="store_true", help="put each circuit's counts in the output")
    ap.add_argument("--out", help="write the JSON here (default: standard output)")
    ap.add_argument("--check-environment", action="store_true", help="print the live path's refusals and exit")
    args = ap.parse_args(argv)
    try:
        if args.check_environment:
            found = refusals()
            for why in found:
                print(f"REFUSED: {why}")
            if not found:
                print("no key-leak condition is present")
            return 1 if found else 0
        result = predict(args)
    except Refused as e:
        print(f"REFUSED: {e.why}", file=sys.stderr)
        return 2
    text = json.dumps(result, indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    if args.out:
        pathlib.Path(args.out).write_text(text, encoding="ascii", newline="\n")
    else:
        sys.stdout.write(text)
    return 0


sys.exit(main(sys.argv[1:]))

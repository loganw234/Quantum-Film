"""A frozen hardware bundle (round 3): the manifest that fixes a hardware run completely, and its check.

A bundle is a directory, committed to git before it is run (docs/ROUND3.md, "The frozen bundle"). For each
circuit of PLAN it holds four files, named for the circuit:
    <name>.qasm          the LOGICAL circuit, OpenQASM 2, measurements included. circuit_sha256 is its SHA-256.
                         It is derived here, as text, from the committed source circuit (`logical_qasm`).
    <name>.qpy           the TRANSPILED circuit, QPY. isa_sha256 is its SHA-256. The runner loads it, adds
                         the circuit's commitment to its metadata, and submits it: nothing else.
    <name>.gates.json    its gate list (quantum_film.ibm.isa), what this package's ISA check reads. The
                         tools check that the QPY file and the gate list are the same circuit, at freezing
                         and again before submission.
    <name>.isa.qasm3     an OpenQASM 3 copy of the transpiled circuit, for reading only.
and beside them MANIFEST, this module's record of everything a commitment binds, and README, the
instructions for whoever runs it. The bundle's identity is the SHA-256 of the manifest file (a job
line's bundle_sha256).

Why the commitment is not inside the QPY file: the commitment binds isa_sha256, the hash of those bytes,
so it cannot be in them. The runner puts it in the circuit's metadata at submission, and checks that the
circuit it submits is the frozen one, gate for gate.

QPY bytes are not reproducible: qiskit 2.5.2 wrote the same transpiled circuit to different bytes twice
in one process (the layout's registers in another order; measured 2026-10-03). So a QPY file's hash names
the frozen FILE, and a re-freeze is compared by its gate lists, which are deterministic.

`check` holds a bundle directory to its manifest by name: every file's hash, the logical circuits to the
committed source ed767c01bd4b851d, the plan's jobs, roles, bases and shots, the options, the commitments,
the chain, and the ISA check, re-run.
"""
import datetime
import hashlib
import json
import pathlib
import re

import numpy as np

from .. import fixer
from ..atlas import pauli_tile
from ..circuits import givens_line
from . import decode, isa

FORMAT = "quantum-film/hardware-bundle/v1"
STOCK = "pauli-4x4"
M = 16
SOURCE = "docs/records/2026-09-25/p3/circuit-ed767c01bd4b851d.qasm"
SOURCE_SHA256 = "ed767c01bd4b851d08993da80f715676e345fc95a10f3bda05400f738e400b36"
PROGRAM = "sampler"              # the legacy SamplerV2's program; tools/hw_run.py says why it is this one
KNOWN_ANSWER = (0, 1, 3, 7, 12)  # not its own mirror under q -> 15 - q (tests/decode/test_ibm_decode.py)
PAIR = (0, 1)
# The options AS SENT: what SamplerV2 puts in the job's params["options"] with the three switches set off
# and nothing else set (measured, qiskit-ibm-runtime 0.50.0). A bundle states them, never defaults them.
OPTIONS = {"dynamical_decoupling": {"enable": False}, "twirling": {"enable_gates": False, "enable_measure": False}}
# The plan (docs/ROUND3.md): the jobs in order, each with its circuits in PUB order, PUBs numbered within
# the job from 0: (name, role, basis, shots). basis[q] is qubit q. Each job's PUBs share one shot count:
# qiskit-ibm-runtime 0.50.0 deprecates different shots across a job's PUBs, so the film is two jobs, the law
# and then the coherence pair (the lead's decision, 2026-10-03 16:24Z).
PLAN = (("known-answer", (("known-answer", "known-answer", "Z" * M, 1024),)),
        ("law", (("law", "law", "Z" * M, 24576),)),
        ("coherence", (("coherence-xx", "coherence", "XX" + "Z" * (M - 2), 4096),
                       ("coherence-yy", "coherence", "YY" + "Z" * (M - 2), 4096))))
CZ = {"known-answer": 0, "law": 102, "coherence-xx": 102, "coherence-yy": 102}
# Seconds of QPU time a job may take, at most: several times IBM's estimate of about 2 s plus 0.35 ms a shot
# (docs/HARDWARE.md), so a slow day still completes and a runaway job still stops.
MAX_EXECUTION_TIME = {"known-answer": 60, "law": 120, "coherence": 60}
MAX_EXECUTION_CAP = 300
OPTIMIZATION_LEVEL = 2
MANIFEST = "manifest.json"
README = "README.md"
SUFFIX = {"circuit": ".qasm", "isa": ".qpy", "gates": ".gates.json", "qasm3": ".isa.qasm3"}
FIELDS = ("format", "stock", "kind", "route", "backend", "program", "decode", "options", "options_sha256",
          "known_answer", "pair", "source", "target", "compile", "versions", "frozen_at", "readme_sha256", "jobs")
ENTRY = ("pub", "name", "role", "basis", "shots", "source_sha256", "circuit_sha256", "isa_sha256",
         "gates_sha256", "qasm3_sha256", "chain", "esp", "isa", "salt", "commitment")
_HEX = re.compile(r"[0-9a-f]{64}", re.ASCII)
_NAME = re.compile(r"[a-z][a-z0-9_-]{0,63}", re.ASCII)
_HELD = {}            # check's ISA verdicts in this process: (gate list sha256, name, role, basis, known answer) -> []
# The rotations that take qubits 0 and 1 of the law into a coherence circuit's basis, as OpenQASM 2 lines.
# YY: S-dagger then H on each qubit of the pair; a different S convention on the two qubits would flip the
# sign of <Y0Y1> (verifier-P0, round 3).
ROTATIONS = {"law": (), "coherence-xx": ("h q[0];", "h q[1];"),
             "coherence-yy": ("sdg q[0];", "h q[0];", "sdg q[1];", "h q[1];")}


def text(obj):
    """The one file form of a manifest or a gate list: sorted keys, a one-space indent, ASCII, a final
    newline (as fixer.text)."""
    return json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=True) + "\n"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def jobs():
    """[(job, [(pub, name, role, basis, shots), ...]), ...] in the plan's order."""
    return [(job, [(pub, *c) for pub, c in enumerate(circuits)]) for job, circuits in PLAN]


def read_source(root):
    """The committed source circuit's text, refused unless it is ed767c01bd4b851d byte for byte."""
    raw = (pathlib.Path(root) / SOURCE).read_bytes()
    if sha256(raw) != SOURCE_SHA256:
        raise ValueError(f"{SOURCE} does not hash to {SOURCE_SHA256[:16]}: it is not the circuit that ran on Atlas")
    return raw.decode("ascii")


def logical_qasm(name, source_text, known_answer=KNOWN_ANSWER):
    """A logical circuit's OpenQASM 2 text, measurements included: the source's gates (or the known answer's
    X gates), the pair's rotations, then what QuantumCircuit.measure_all adds: a barrier on every qubit and
    qubit i measured into bit i of one register, `meas`. qiskit's qasm2.loads reads this text as exactly the
    circuit measure_all builds (the qiskit stage checks it). The text is derived here, from the source's own
    bytes, because qiskit's qasm2.dumps writes some angles differently (pi/2 for 1.5707963267948966)."""
    lines = source_text.split("\n")
    head = ['OPENQASM 2.0;', 'include "qelib1.inc";', f"qreg q[{M}];"]
    if name == "known-answer":
        body = [f"x q[{q}];" for q in sorted(known_answer)]
    elif name in ROTATIONS:
        if lines[:3] != head or lines[-1] != "":
            raise ValueError("the source is not an OpenQASM 2 file of one 16-qubit register")
        body = lines[3:-1] + list(ROTATIONS[name])
    else:
        raise ValueError(f"no circuit {name!r} in the plan")
    measure = ["barrier " + ",".join(f"q[{q}]" for q in range(M)) + ";"] + \
        [f"measure q[{q}] -> meas[{q}];" for q in range(M)]
    return "\n".join(head + [f"creg meas[{M}];"] + body + measure) + "\n"


def logical_state(name, source_text, known_answer=KNOWN_ANSWER):
    """The logical circuit's state before its basis rotations, from circuits.givens_line (float64, a code
    path apart from the ISA check's): the source circuit's state, or the known answer's basis state."""
    if name == "known-answer":
        psi = np.zeros((2,) * M)
        psi[tuple(1 if q in known_answer else 0 for q in range(M))] = 1.0
        return psi
    gate_list, m = givens_line.from_qasm(source_text)
    if m != M:
        raise ValueError(f"the source has {m} qubits, not {M}")
    return givens_line.simulate(gate_list, m)


def hold_isa(doc, name, role, basis, source_text, known_answer=KNOWN_ANSWER):
    """The ISA check of one circuit: its transpiled gate list, simulated by quantum_film.ibm.isa, against its
    logical circuit's exact distribution and its role. -> (problems, values)."""
    psi = logical_state(name, source_text, known_answer)
    exact = isa.exact_distribution(psi, basis)
    p = isa.distribution(doc)
    kwargs = {}
    if role == "law":
        kwargs["law"] = pauli_tile.law_of(STOCK)[2]
    elif role == "coherence":
        kwargs.update(pair=PAIR, pair_value=givens_line.pauli_expectation(psi, {q: basis[q] for q in PAIR}))
    elif role == "known-answer":
        kwargs["expected"] = tuple(known_answer)
    return isa.hold(p, exact, role=role, **kwargs)


def utc_time(s):
    """A checked UTC string (is_utc) as an aware datetime, to the microsecond."""
    fraction = s[20:-1] if s[19] == "." else ""
    return datetime.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(
        microsecond=int((fraction + "000000")[:6]), tzinfo=datetime.timezone.utc)


def readme(m):
    """The bundle's README.md, for whoever runs it (Moth's CTO, or the lead): what to install, what to run,
    what to send back. Written from the manifest's fields; its SHA-256 is in the manifest."""
    jobs_text = []
    for j in m["jobs"]:
        parts = ", ".join(f"{e['name']} ({e['shots']:,} shots)" for e in j["circuits"])
        jobs_text.append(f"- `{j['job']}`: {parts}; at most {j['max_execution_time']} s of QPU time.")
    moth = m["route"] == "moth"
    anchor = (["- The job line (`<job>-line.json`) is written to the output directory as soon as IBM has created "
               "the job, before any result is read. **Send it to the owner at once**, before the results come "
               "back: it is this run's only anchor that precedes the results (docs/ROUND3.md states the limit)."]
              if moth else
              ["- The job line (`<job>-line.json`) is committed and pushed by the runner as soon as IBM has created "
               "the job, before any result is read. The output directory must be inside this repository, on a "
               "branch whose head is already on origin."])
    later = [name for name, _ in PLAN][1:]
    lines = [
        f"# Quantum-Film hardware bundle: {m['stock']} on {m['backend']}",
        "",
        "This directory is a frozen bundle. It fixes completely what will run: run it as it is, and change "
        "nothing in it. Its identity is the SHA-256 of `manifest.json`, which every job line names.",
        "",
        f"- Backend `{m['backend']}` (kind `{m['kind']}`), route `{m['route']}`, program `{m['program']}`.",
        f"- Compiled at optimization level {m['compile']['optimization_level']} with seed "
        f"{m['compile']['seed_transpiler']}, against the target's calibration of {m['target']['calibration']}.",
        f"- The chain, the physical qubits of logical qubits 0 to {M - 1}: {m['jobs'][0]['circuits'][0]['chain']}.",
        "- Options, stated: dynamical decoupling off, gate twirling off, measurement twirling off.",
        "",
        "## The jobs, in order",
        "",
        *jobs_text,
        "",
        f"The known answer puts X on {m['known_answer']}: it checks the order in which the device's bitstrings "
        f"are read. Run the {' and '.join(later)} jobs only after the known-answer job has printed HOLDS. Each "
        "job takes one shot count across its circuits.",
        "",
        "## What to install",
        "",
        f"- Python {m['versions'].get('python', '3.12')}, with exactly qiskit=={m['versions']['qiskit']} and "
        f"qiskit-ibm-runtime=={m['versions']['qiskit_ibm_runtime']} (the runner refuses another runtime version), "
        "numpy and mpmath. To rehearse offline with `--dry-run`, also "
        f"qiskit-aer=={m['versions'].get('qiskit_aer', '0.17.2')}.",
        "- A checkout of github.com/loganw234/Quantum-Film at the commit that holds this bundle.",
        "",
        "## The key, outside every directory you run in",
        "",
        "- `QF_IBM_KEY_FILE` names IBM's `apikey.json` (its field `apikey`), and `QF_IBM_INSTANCE_FILE` a file "
        "holding the instance's CRN. Both files live outside the checkout; the runner refuses a path inside it.",
        "- The runner refuses to start while any of these is configured, and names it: a proxy (the environment, "
        "or the Windows registry), a CA bundle (REQUESTS_CA_BUNDLE, CURL_CA_BUNDLE, SSL_CERT_FILE, SSL_CERT_DIR), "
        "a netrc file (~/.netrc, ~/_netrc, NETRC), SSLKEYLOGFILE, IAM_URL, IBM_CREDENTIALS_FILE, VCAP_SERVICES, "
        "an ibm-credentials.env file, or a GLOBAL_SEARCH_*, GLOBAL_CATALOG_*, RESOURCE_CONTROLLER_* or "
        "*_DISABLE_SSL variable. Unset it for the run.",
        "- It never saves an account, and stops if IBM's client says it will send the API key instead of a token.",
        "",
        "## What to run, from the checkout's root",
        "",
        "    python tools/hw_run.py --bundle <this directory> --job known-answer --out <an output directory>",
        "",
        "and then, only if that printed HOLDS, one after the other:",
        "",
        *[f"    python tools/hw_run.py --bundle <this directory> --job {name} --out <the same output directory>"
          for name in later],
        "",
        *anchor,
        "- Each job is submitted once. The runner refuses a job that already has a line, and never resubmits. "
        "A job that fails keeps its line and gets a status file; a re-run needs a newly frozen bundle.",
        "- To rehearse offline first, add `--dry-run`: a local simulator, no account, records of kind `simulator`.",
        "",
        "## What to send back",
        "",
        "The whole output directory, unchanged: for each job its line, its raw result (`<job>-raw.json`, written "
        "before anything decodes it), its metrics, its records (`<job>-pub<k>-<name>.json`) and, for the known "
        "answer, its verdict; for a job that did not complete, its status file. And the console output.",
        "",
    ]
    return "\n".join(lines)


def commitment(manifest, entry):
    """A circuit's commitment v3, from the manifest's fields and the entry's."""
    return fixer.commitment_v3(
        stock=manifest["stock"], role=entry["role"], basis=entry["basis"], kind=manifest["kind"],
        route=manifest["route"], backend=manifest["backend"], program=manifest["program"], pub=entry["pub"],
        circuit_sha256=entry["circuit_sha256"], isa_sha256=entry["isa_sha256"], shots=entry["shots"],
        options_sha256=manifest["options_sha256"], decode=manifest["decode"], salt=entry["salt"])


def job(manifest, name):
    """The manifest's entry for job `name`; KeyError if the bundle has no such job."""
    for j in manifest["jobs"]:
        if j["job"] == name:
            return j
    raise KeyError(f"the bundle has no job {name!r}; it has {[j['job'] for j in manifest['jobs']]}")


def files(manifest):
    """Every file the manifest names, with the SHA-256 it states: {file name: sha256}."""
    out = {README: manifest["readme_sha256"]}
    for j in manifest["jobs"]:
        for e in j["circuits"]:
            for part, suffix in SUFFIX.items():
                out[e["name"] + suffix] = e["circuit_sha256" if part == "circuit" else f"{part}_sha256"]
    return out


def _no_twice(pairs):
    keys = [k for k, _ in pairs]
    twice = sorted({k for k in keys if keys.count(k) > 1})
    if twice:
        raise ValueError(f"a key appears twice: {twice}")
    return dict(pairs)


def load_json(raw):
    """JSON from file bytes, refusing a key that appears twice (a second, unsealed reading)."""
    return json.loads(raw.decode("ascii"), object_pairs_hook=_no_twice)


def load(bundle_dir):
    """(manifest, its SHA-256) from a bundle directory, refused unless the file is its canonical text."""
    raw = (pathlib.Path(bundle_dir) / MANIFEST).read_bytes()
    manifest = load_json(raw)
    if raw != text(manifest).encode("ascii"):
        raise ValueError(f"{MANIFEST}: its bytes are not the manifest's canonical text")
    return manifest, sha256(raw)


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def same_json(a, b):
    """Equal as JSON, not as Python: false is not 0."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def is_utc(s):
    """A real UTC time, YYYY-MM-DDTHH:MM:SS[.ffffff]Z, in ASCII digits."""
    shape = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?Z"
    if not (isinstance(s, str) and re.fullmatch(shape, s, re.ASCII)):
        return False
    try:
        datetime.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return False
    return True


def _top_problems(m):
    out = []
    if m["format"] != FORMAT:
        out.append(f"format: {m['format']!r} is not {FORMAT!r}")
    if m["stock"] != STOCK:
        out.append(f"stock: {m['stock']!r}; a bundle of this plan is {STOCK!r}")
    if m["program"] != PROGRAM:
        out.append(f"program: {m['program']!r}; this runner submits to {PROGRAM!r}")
    if m["decode"] != decode.DECODE:
        out.append(f"decode: {m['decode']!r}; IBM's strings are read by {decode.DECODE!r}")
    if m["kind"] not in fixer.RUN_KINDS or m["route"] not in fixer.ROUTES:
        out.append(f"kind is one of {fixer.RUN_KINDS} and route one of {fixer.ROUTES}")
    elif not (isinstance(m["backend"], str) and _NAME.fullmatch(m["backend"])):
        out.append("backend: a lowercase name")
    elif (m["kind"] == "qpu") != (m["backend"] in fixer.IBM_DEVICES):
        out.append("kind: a qpu bundle names an IBM device in fixer.IBM_DEVICES, and only a qpu bundle does")
    if not same_json(m["options"], OPTIONS):
        out.append(f"options: {m['options']!r}; a bundle states dynamical decoupling and both twirlings off, "
                   f"exactly {OPTIONS}")
    if m["options_sha256"] != fixer.options_digest(m["options"]):
        out.append("options_sha256: not the digest of the options the manifest states")
    if m["known_answer"] != list(KNOWN_ANSWER):
        out.append(f"known_answer: {m['known_answer']!r}; the plan's is {list(KNOWN_ANSWER)}")
    if m["pair"] != list(PAIR):
        out.append(f"pair: {m['pair']!r}; the plan's is {list(PAIR)}")
    if m["source"] != {"path": SOURCE, "sha256": SOURCE_SHA256}:
        out.append(f"source: not {{path: {SOURCE}, sha256: {SOURCE_SHA256[:16]}...}}")
    t = m["target"]
    if not (isinstance(t, dict) and set(t) == {"name", "num_qubits", "calibration", "coupling"}
            and t["name"] == m["backend"] and _is_int(t["num_qubits"]) and isinstance(t["calibration"], str)
            and isinstance(t["coupling"], list)
            and all(isinstance(e, list) and len(e) == 2 and all(_is_int(q) for q in e) for e in t["coupling"])):
        out.append("target: {name (the backend), num_qubits, calibration, coupling [[a, b], ...]}")
    c = m["compile"]
    if not (isinstance(c, dict) and set(c) == {"optimization_level", "seed_transpiler", "layout"}
            and c["optimization_level"] == OPTIMIZATION_LEVEL and _is_int(c["seed_transpiler"])
            and isinstance(c["layout"], str)):
        out.append(f"compile: {{optimization_level {OPTIMIZATION_LEVEL}, seed_transpiler, layout}}")
    v = m["versions"]
    if not (isinstance(v, dict) and all(isinstance(v.get(k), str) for k in ("qiskit", "qiskit_ibm_runtime"))):
        out.append("versions: the qiskit and qiskit_ibm_runtime versions, at least")
    if not is_utc(m["frozen_at"]):
        out.append("frozen_at: a UTC time")
    if not (isinstance(m["readme_sha256"], str) and _HEX.fullmatch(m["readme_sha256"])):
        out.append("readme_sha256: 64 lowercase hex digits")
    return out


def _jobs_problems(m):
    """The plan's jobs, PUBs, names, roles, bases and shots, and each entry's fields."""
    out = []
    js = m["jobs"]
    if not (isinstance(js, list) and [j.get("job") if isinstance(j, dict) else None for j in js]
            == [name for name, _ in PLAN]):
        return [f"jobs: the plan's jobs in order, {[name for name, _ in PLAN]}"]
    for j, (name, planned) in zip(js, jobs(), strict=True):
        if set(j) != {"job", "max_execution_time", "circuits"}:
            out.append(f"jobs.{name}: fields {sorted(j)}; a job carries job, max_execution_time and circuits")
            continue
        if not (_is_int(j["max_execution_time"]) and 1 <= j["max_execution_time"] <= MAX_EXECUTION_CAP):
            out.append(f"jobs.{name}: max_execution_time is whole seconds from 1 to {MAX_EXECUTION_CAP}")
        cs = j["circuits"]
        if not (isinstance(cs, list) and len(cs) == len(planned) and all(isinstance(e, dict) for e in cs)):
            out.append(f"jobs.{name}: {len(planned)} circuits, in PUB order")
            continue
        if len({json.dumps(e.get("shots")) for e in cs}) != 1:
            out.append(f"jobs.{name}: its PUBs take different shots; a job's PUBs share one shot count")
        for e, (pub, cname, role, basis, shots) in zip(cs, planned, strict=True):
            where = f"jobs.{name}[{pub}]"
            if tuple(sorted(e)) != tuple(sorted(ENTRY)):
                out.append(f"{where}: fields {sorted(e)}; an entry carries exactly {sorted(ENTRY)}")
                continue
            if (e["pub"], e["name"], e["role"], e["basis"]) != (pub, cname, role, basis) or not _is_int(e["pub"]):
                out.append(f"{where}: pub, name, role and basis are the plan's {(pub, cname, role, basis)}")
            if not (_is_int(e["shots"]) and e["shots"] >= 1):
                out.append(f"{where}: shots are a positive whole number")
            elif m["kind"] == "qpu" and e["shots"] != shots:
                out.append(f"{where}: {e['shots']} shots; a qpu bundle takes the plan's {shots}")
            want_source = None if role == "known-answer" else SOURCE_SHA256
            if e["source_sha256"] != want_source:
                out.append(f"{where}: source_sha256 is {want_source!r} for a {role} circuit")
            for f in ("circuit_sha256", "isa_sha256", "gates_sha256", "qasm3_sha256", "salt", "commitment"):
                if not (isinstance(e[f], str) and _HEX.fullmatch(e[f])):
                    out.append(f"{where}: {f} is 64 lowercase hex digits")
            if not (isinstance(e["chain"], list) and len(e["chain"]) == M and all(_is_int(q) for q in e["chain"])):
                out.append(f"{where}: chain is the {M} physical qubits of logical qubits 0..{M - 1}")
            if not (isinstance(e["esp"], float) and 0 < e["esp"] <= 1):
                out.append(f"{where}: esp is the estimated success probability, in (0, 1]")
            if not isinstance(e["isa"], dict):
                out.append(f"{where}: isa is the ISA check's values at freezing")
    return out


def check(bundle_dir, root):
    """(manifest, its SHA-256, the named reasons the bundle is refused). [] means it holds: every file is
    the one the manifest hashes, each logical circuit is derived from the committed source, the plan,
    options and commitments are the manifest's, and every transpiled circuit passes the SWAP-free checks and
    the ISA check here. `root` is the repository root, where the source circuit is committed."""
    bundle_dir = pathlib.Path(bundle_dir)
    try:
        m, digest = load(bundle_dir)
    except (OSError, UnicodeDecodeError, ValueError, RecursionError) as e:
        return None, None, [f"{MANIFEST}: unreadable ({type(e).__name__}: {e})"[:300]]
    if not isinstance(m, dict) or tuple(sorted(m)) != tuple(sorted(FIELDS)):
        return m, digest, [f"{MANIFEST}: fields {sorted(m) if isinstance(m, dict) else type(m).__name__}; "
                           f"a manifest carries exactly {sorted(FIELDS)}"]
    out = _top_problems(m)
    out += _jobs_problems(m)
    if out:
        return m, digest, out
    try:
        source_text = read_source(root)
    except (OSError, UnicodeDecodeError, ValueError) as e:
        return m, digest, [f"source: {e}"]
    named = files(m)
    present = sorted(p.name for p in bundle_dir.iterdir())
    extra = sorted(set(present) - set(named) - {MANIFEST})
    if extra:
        out.append(f"files: {extra} are in the bundle and not in its manifest")
    for name, want in sorted(named.items()):
        try:
            got = sha256((bundle_dir / name).read_bytes())
        except OSError:
            out.append(f"{name}: missing")
            continue
        if got != want:
            out.append(f"{name}: its SHA-256 is not the manifest's (the file is {got[:16]}, the manifest "
                       f"says {want[:16]})")
    if out:
        return m, digest, out
    chains = set()
    salts, commitments = [], []
    edges = [tuple(e) for e in m["target"]["coupling"]]
    for j in m["jobs"]:
        for e in j["circuits"]:
            where = f"{j['job']}[{e['pub']}] {e['name']}"
            logical = (bundle_dir / (e["name"] + SUFFIX["circuit"])).read_bytes()
            if logical != logical_qasm(e["name"], source_text, m["known_answer"]).encode("ascii"):
                out.append(f"{where}: the logical circuit is not the one derived from the source "
                           f"{SOURCE_SHA256[:16]}" + (" and the known answer" if e["role"] == "known-answer" else ""))
            raw = (bundle_dir / (e["name"] + SUFFIX["gates"])).read_bytes()
            try:
                doc = load_json(raw)
            except (UnicodeDecodeError, ValueError, RecursionError) as ex:
                out.append(f"{where}: the gate list is unreadable ({type(ex).__name__})")
                continue
            if raw != text(doc).encode("ascii"):
                out.append(f"{where}: the gate list's bytes are not its canonical text")
            read = isa.read(doc)
            if read:
                out += [f"{where}: {p}" for p in read[:5]]
                continue
            if doc["layout"]["initial"] != e["chain"] or doc["num_clbits"] != M:
                out.append(f"{where}: the gate list's chain is not the manifest's, or it measures other than "
                           f"{M} bits")
            chains.add(tuple(e["chain"]))
            out += [f"{where}: {p}" for p in isa.swap_free(doc, edges, CZ[e["name"]])]
            # The ISA check is a function of the gate list's bytes, the circuit's name, role and basis and the
            # known answer (the source is fixed: read_source refused anything but ed767c01), so its verdict is
            # kept for this process under exactly those: a check of an unchanged bundle is not re-simulated.
            key = (sha256(raw), e["name"], e["role"], e["basis"], tuple(m["known_answer"]))
            if key not in _HELD:
                try:
                    _HELD[key] = hold_isa(doc, e["name"], e["role"], e["basis"], source_text, m["known_answer"])[0]
                except (isa.IsaRefusal, ValueError) as ex:
                    _HELD[key] = [f"isa: {ex}"]
            out += [f"{where}: {p}" for p in _HELD[key]]
            if e["commitment"] != commitment(m, e):
                out.append(f"{where}: the commitment does not recompute from the manifest's fields")
            salts.append(e["salt"])
            commitments.append(e["commitment"])
    if len(chains) > 1:
        out.append(f"chain: the circuits are on {len(chains)} different chains; a bundle runs every circuit on "
                   "the law's")
    if len(set(salts)) != len(salts) or len(set(commitments)) != len(commitments):
        out.append("salt: every circuit has its own salt and commitment")
    return m, digest, out

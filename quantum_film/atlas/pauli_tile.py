"""The pauli-4x4 stock on tomography-api-v2: everything but the network.

tools/pauli_atlas_run.py drives this; nothing here calls Atlas, so everything
here is testable offline (tests/circuits/test_pauli_tile.py).

THE ORDER A DEVICE ROLL IS MADE IN (docs/ROUND1.md, P3):
  1. The circuit sent is circuits.givens_line's circuit for the stock, held to
     the authority's law on a local statevector first (`check_circuit`). The
     fixer binds only a circuit's SHA-256, so this is where the law is bound.
  2. The job is submitted. Its commitment is formed from what is known at
     submission (stock, circuit SHA-256, engine, job id, shots, decode rule,
     salt), and committed to git with the exact QASM text BEFORE the first
     status call. Once a job has completed, its STATUS response carries the
     whole result as well (the 2026-09-25 records in docs/records show it), so a
     status poll counts as a fetch. That order is the code's; the only
     timestamps on it are local (the commit's, the client's saved responses),
     and nothing third-party dates the commitment (verifier-P3, D2).
  3. The result is read through decode.layouts, and nothing else, and scored
     against the authority's kernel with atlas_tile_compare.py's statistics
     (research/2026-09-25/emulsions/), the circuit's SHA-256 beside the score.
  4. One device roll is fixed per distinct layout, `occurrences` counting its
     shots. A layout the law forbids is fixed like any other: a device records
     what it laid. Its count is the score's witness of noise.

`audit` is every check a committed run must pass, by name. `--score` exits
non-zero on any of them, and tests/circuits/test_p3_records.py holds the
committed runs to it.
"""
import datetime
import functools
import hashlib
import itertools
import json
import math
import platform
import re
import sys

import numpy as np

from .. import fixer
from ..circuits import givens, givens_line
from ..golden import fermi
from ..stocks import params
from . import decode

STOCK = "pauli-4x4"
ENGINE = "tomography-api-v2"
KIND = "atlas-emu"
DECODE = "quantum_film.atlas.decode/v1"      # decode.layouts, as at b0e9ed1; committed before submission
SHOTS = 4096
FORBIDDEN_BELOW = 1e-9     # as tests/golden/test_golden_law.py: allowed det >= 2.4e-4, forbidden |det| <= 6.5e-19
ENGINE_Z = 4.5             # an emulator's own observables, within this many standard errors of the circuit's state
LINE_CONSTANTS = {"format": fixer.COMMITMENT_DOMAIN, "stock": STOCK, "engine": ENGINE, "decode": DECODE}
# Credentials and personal data a record must never carry. Matching text is
# refused, never printed: the presigned-URL markers, a Moth key, an
# Authorization header, and any e-mail address (the account's included).
SECRET = re.compile(r"moth_[A-Za-z0-9]{8,}|x-amz-|amazonaws\.com|authorization|bearer\s+\S"
                    r"|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", re.IGNORECASE)


def shape(stock=STOCK):
    p = params(stock)
    if p["family"] != "determinantal":
        raise LookupError(f"{stock!r} is not a determinantal stock")
    return p["L"], p["fermi_r2"], p["M"], p["N"]


def golden_kernel(stock=STOCK):
    """The authority's kernel for the stock, at 128 bits, as float64."""
    L, r2, _M, _N = shape(stock)
    return np.array([[float(v) for v in row] for row in fermi.kernel(L, r2, prec=128)])


def forbidden_layouts(K, N):
    """The N-site layouts the law never lays (det(K_Y) = 0), with the gap
    between them and the smallest allowed det checked, as the law test does."""
    dets = {Y: float(np.linalg.det(K[np.ix_(Y, Y)])) for Y in itertools.combinations(range(len(K)), N)}
    allowed = min(d for d in dets.values() if d > FORBIDDEN_BELOW)
    zero = max(abs(d) for d in dets.values() if d <= FORBIDDEN_BELOW)
    if not (allowed > 1e4 * FORBIDDEN_BELOW and zero < 1e-6 * FORBIDDEN_BELOW):
        raise ArithmeticError(f"no clean gap between forbidden (|det| <= {zero:.1e}) and allowed ({allowed:.1e})")
    return {Y for Y, d in dets.items() if d <= FORBIDDEN_BELOW}, dets


@functools.lru_cache(maxsize=4)
def law_of(stock=STOCK):
    """(K read-only, the forbidden layouts, det(K_Y) per layout), once per stock."""
    K = golden_kernel(stock)
    K.setflags(write=False)
    forbidden, dets = forbidden_layouts(K, shape(stock)[3])
    return K, frozenset(forbidden), dict(dets)


def sha256_text(text):
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def check_state(psi, K, N, dets=None):
    """A statevector against the authority: the kernel statistics (<n_i>,
    <n_i n_j>) and the whole layout law."""
    n1, n2 = givens_line.occupations(psi)
    e2 = np.outer(np.diag(K), np.diag(K)) - K ** 2
    np.fill_diagonal(e2, 0.0)
    kernel_error = max(float(np.max(np.abs(n1 - np.diag(K)))), float(np.max(np.abs(n2 - e2))))
    law, leaked = givens_line.layout_law(psi, N)
    dets = dets if dets is not None else forbidden_layouts(K, N)[1]
    law_error = max(abs(law[Y] - d) for Y, d in dets.items())
    return {"kernel_error": kernel_error, "law_error": law_error, "leaked": leaked}


def check_circuit(gate_list, K, N):
    """A gate list against the authority on a local statevector."""
    return check_state(givens_line.simulate(gate_list, len(K)), K, N)


def circuit(stock=STOCK):
    """(gate list, QASM text, SHA-256, stats) of the stock's circuit, refused unless
    it lays the authority's law to 1e-12 here and reads back from its own text."""
    gate_list, qasm, N, layers = givens_line.for_stock(stock)
    K = golden_kernel(stock)
    held = check_circuit(gate_list, K, N)
    if max(held.values()) >= 1e-12:
        raise AssertionError(f"the circuit does not lay {stock}'s law here: {held}")
    if givens_line.from_qasm(qasm) != (gate_list, len(K)):
        raise AssertionError("the QASM text does not read back as the gate list it was written from")
    return gate_list, qasm, sha256_text(qasm), dict(givens_line.stats(gate_list, layers), **held)


def request(qasm, M, shots=SHOTS):
    """The job body: every qubit in qubit_list and one pair, (0, 1), with single
    and double tomography. That is exactly the shape of the 2026-09-25
    known-answer runs that read in plain order (jobs 93924d11, 5ad38bfe,
    e4d62182, 4cc3c663).

    Measured on job 8586f1cc: the engine merges the qubit-wise settings with
    the pair's, so its nine labels are XXXXXXXXXXXXXXXX, YYYYYYYYYYYYYYYX,
    ZZZZZZZZZZZZZZZX and six pair-only ones, IIIIIIIIIIIIIIXY .. IIIIIIIIIIIIIIZZ.
    The one with no X or Y is IIIIIIIIIIIIIIZZ: every qubit is measured in Z
    there ("I" is measured, unrotated), which is what makes its strings whole
    crystal layouts, whatever qubit_list says. decode's rule reads it as
    [0, 1] + [2..15], which is plain order."""
    return {"params": {"circuit_qasm": qasm, "qubit_list": list(range(M)), "qubit_pair_list": [[0, 1]],
                       "shots": shots, "single_tomography": True, "double_tomography": True,
                       "mutual_information": False, "classical_mutual_information": False}}


def committed_fields(*, job_id, circuit_sha256, salt, shots=SHOTS, engine=ENGINE, decode_rule=DECODE):
    fields = {"circuit_sha256": circuit_sha256, "engine": engine, "job_id": job_id, "shots": shots,
              "decode": decode_rule, "salt": salt}
    if set(fields) != set(fixer.COMMITTED):
        raise AssertionError(f"the commitment's fields are {fixer.COMMITTED}")
    return fields


def commitment_line(*, stock=STOCK, qasm_file, submitted_at, code_commit, **committed):
    """The line committed to git before the result is fetched: the commitment and
    every field it binds, and where the exact QASM text is. No result."""
    fields = committed_fields(**committed)
    return dict(fields, format=fixer.COMMITMENT_DOMAIN, stock=stock,
                commitment=fixer.commitment(stock=stock, **fields),
                qasm_file=qasm_file, submitted_at=submitted_at, code_commit=code_commit)


def layouts(result):
    """{sorted tuple of occupied qubits: shots} from a tomography-api-v2 result,
    read through decode.layouts and nothing else."""
    out = decode.layouts(result)
    for Y in out:
        if not all(type(q) is int for q in Y):
            raise TypeError(f"layout {Y!r}: decode must yield Python ints")
    return out


def score(counts, K, forbidden, circuit_sha256):
    """atlas_tile_compare.py's statistics against K: <n_q> for every site, P(11)
    for every pair, each as z = (measured - exact) / binomial standard error;
    the crystal count per layout; and the shots on layouts the law forbids."""
    M = len(K)
    shots = sum(counts.values())
    sizes = {}
    for Y, c in counts.items():
        sizes[len(Y)] = sizes.get(len(Y), 0) + c
    one = np.zeros(M)
    two = np.zeros((M, M))
    for Y, c in counts.items():
        for i in Y:
            one[i] += c
        for i, j in itertools.combinations(Y, 2):
            two[i, j] += c
    z1 = [(one[q] / shots - K[q, q]) / math.sqrt(K[q, q] * (1 - K[q, q]) / shots) for q in range(M)]
    z2 = {}
    for i, j in itertools.combinations(range(M), 2):
        ex = K[i, i] * K[j, j] - K[i, j] ** 2
        z2[(i, j)] = (two[i, j] / shots - ex) / math.sqrt(ex * (1 - ex) / shots)
    worst = max(z2, key=lambda p: abs(z2[p]))
    off = {Y: c for Y, c in counts.items() if Y in forbidden}
    return {"stock": STOCK, "circuit_sha256": circuit_sha256, "shots": shots, "distinct_layouts": len(counts),
            "crystals_per_layout": {str(k): v for k, v in sorted(sizes.items())},
            "one_site": {"n": M, "max_abs_z": max(abs(z) for z in z1), "chi2": sum(z * z for z in z1),
                         "z": [round(z, 4) for z in z1]},
            "pairs": {"n": len(z2), "max_abs_z": abs(z2[worst]), "chi2": sum(z * z for z in z2.values()),
                      "worst_pair": list(worst), "worst_z": z2[worst]},
            "chi2_per_dof": (sum(z * z for z in z1) + sum(z * z for z in z2.values())) / (M + len(z2)),
            "forbidden": {"layouts_in_law": len(forbidden), "distinct_laid": len(off),
                          "shots": sum(off.values()), "fraction": sum(off.values()) / shots}}


def engine_observables(result, psi, pair=(0, 1)):
    """The engine's OWN derived observables, which it computes from its other
    settings without decode, against the committed circuit's own state psi,
    SIGNS INCLUDED: every <X_q>, <Y_q> and <Z_q>, and the pair's nine
    correlators. On the JW-adjacent pair, |<XX>| = |<YY>| = 2|K_pq|, which only a
    coherent state gives (a mixture with the same layouts gives 0). Their sign
    is the circuit's: the gauge leaves it open until a circuit is chosen, and
    the circuit then fixes it (+0.375 for ed767c01bd4b851d), so a negated pair
    fails. -> [(name, measured, exact, z)], z against one setting's binomial error."""
    M = psi.ndim
    shots = min(v["shots"] for v in result["measurements"].values())
    ob = result["observables"]
    rows = []
    psi = np.asarray(psi, dtype=complex)                  # once, not per observable

    def add(name, measured, exact):
        rows.append((name, measured, exact, (measured - exact) / math.sqrt(max(1 - exact * exact, 1e-12) / shots)))

    for s in range(M):
        for b in "XYZ":
            add(f"<{b}_{s}>", float(ob[str(s)][b]), givens_line.pauli_expectation(psi, {s: b}))
    p, q = pair
    for a in "XYZ":
        for b in "XYZ":
            add(f"<{a}{b}>_{p}{q}", float(ob[f"{p},{q}"][a + b]), givens_line.pauli_expectation(psi, {p: a, q: b}))
    return rows


def device_rolls(counts, line, fixed_at, stock=STOCK):
    """One record per distinct layout, `occurrences` its shots. -> (records, refused),
    refused being (layout, shots, the fixer's reason): a layout the fixer will
    not seal is reported, never reshaped into one it will."""
    records, refused = [], []
    for Y, c in sorted(counts.items()):
        try:
            records.append(fixer.fix_device(stock, list(Y), roll_source(line, fixed_at, c)))
        except ValueError as e:
            refused.append((list(Y), c, str(e)))
    return records, refused


def roll_source(line, fixed_at, occurrences):
    return {"kind": KIND, "fixed_at": fixed_at, "occurrences": occurrences,
            **{k: line[k] for k in (*fixer.COMMITTED, "commitment")}}


def record_name(record):
    return "-".join(f"{q:02d}" for q in record["crystals"]) + ".json"


def scrub(o):
    """Presigned storage URLs out (tomography results carry none; this is the second lock)."""
    if isinstance(o, dict):
        return {k: ("<presigned url removed>" if k in ("url", "download_url") else scrub(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [scrub(v) for v in o]
    return o


def safe_json(obj):
    """JSON text for docs/records, refused if anything in it looks like a
    credential or an e-mail address. The match is never printed."""
    text = json.dumps(scrub(obj), indent=1, sort_keys=True, ensure_ascii=True) + "\n"
    found = SECRET.search(text)
    if found:
        raise PermissionError(f"refused: the text for docs/records matches a credential or e-mail pattern "
                              f"at offset {found.start()}; nothing was written")
    return text


# ---------------------------------------------------------------- the audit


def utc(stamp):
    """A UTC time stamp as this project and Atlas write it: 2026-09-25T22:52:49Z."""
    return datetime.datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)


def load_run(out, line):
    """A committed run, read from its directory exactly as committed. -> (run,
    problems): a file that is missing or unreadable is a problem, never repaired."""
    job = str(line.get("job_id", ""))[:8]
    run, problems = {"line": line}, []
    files = {"qasm": out / str(line.get("qasm_file")), "submit": out / f"atlas-{job}-submit.json",
             "result": out / f"atlas-{job}-result.json", "score": out / f"score-{job}.json"}
    for key, path in files.items():
        try:
            raw = path.read_bytes().decode("ascii")
            run[key] = raw if key == "qasm" else json.loads(raw)
        except (OSError, UnicodeDecodeError, ValueError) as e:
            problems.append(f"{path.name}: missing or unreadable ({e.__class__.__name__})")
            run[key] = None
    rolls = out / f"rolls-{job}"
    run["records"] = [(f.name, f.read_bytes()) for f in sorted(rolls.glob("*.json"))]
    if not run["records"]:
        problems.append(f"{rolls.name}: no device rolls")
    return run, problems


def audit(run):
    """Every check a committed run must pass, by name; [] means it holds.

    The line's constants; the circuit (its text hashes to the line's circuit,
    the commitment recomputes, the text is what the submit exchange sent, and
    it lays the stock's law here); the records (bytes, the fixer's check, name,
    kind, fixed_at no earlier than the server's submitted_at, the line's
    fields, and together with the score's not_fixed exactly the committed
    result read through decode); the committed score, recomputed; and the
    engine's own observables against the committed circuit's state, signs
    included. The last is an emulator's check: a QPU's would need its noise."""
    line = run["line"]
    out = [f"line: {k} is {line.get(k)!r}, not {v!r}" for k, v in LINE_CONSTANTS.items() if line.get(k) != v]
    if any(run.get(k) is None for k in ("qasm", "submit", "result")):
        return out + ["run: the QASM, the submit exchange or the result is missing; nothing else can be held"]
    found, psi = audit_circuit(line, run["qasm"], run["submit"])
    out += found
    try:
        result = run["result"]["response"]["result"]
        counts = layouts(result)
    except (KeyError, TypeError, ValueError) as e:
        return out + [f"result: not readable through decode ({e.__class__.__name__}: {e})"]
    not_fixed = (run.get("score") or {}).get("not_fixed", [])
    out += audit_records(line, run["submit"], counts, run.get("records", []), not_fixed)
    out += audit_score(line, counts, run.get("score"))
    if psi is not None:
        out += audit_engine(result, psi)
    return out


def audit_circuit(line, qasm, submit):
    """-> (problems, the committed circuit's statevector, or None if it has none)."""
    out = []
    if sha256_text(qasm) != line.get("circuit_sha256"):
        out.append("circuit: the committed QASM does not hash to the line's circuit_sha256")
    try:
        again = fixer.commitment(stock=line.get("stock"), **{k: line.get(k) for k in fixer.COMMITTED})
    except (TypeError, ValueError):
        again = None
    if line.get("commitment") != again:
        out.append("commitment: it does not recompute from the line's fields")
    sent = ((submit.get("body") or {}).get("params") or {})
    response = submit.get("response") or {}
    if sent.get("circuit_qasm") != qasm:
        out.append("circuit: the submit exchange sent other text than the committed QASM")
    if sent.get("shots") != line.get("shots"):
        out.append("shots: the submit exchange asked for other shots than the line binds")
    if response.get("job_id") != line.get("job_id") or response.get("submitted_at") != line.get("submitted_at"):
        out.append("submit: the exchange's job_id or submitted_at is not the line's")
    K, _forbidden, dets = law_of(STOCK)
    N = shape(STOCK)[3]
    try:
        gate_list, M = givens_line.from_qasm(qasm)
        if M != len(K):
            raise ValueError(f"{M} qubits, where {STOCK} has {len(K)} sites")
        psi = givens_line.simulate(gate_list, M)
    except ValueError as e:
        return out + [f"circuit: the committed QASM cannot be simulated here ({e})"], None
    held = check_state(psi, K, N, dets)
    if max(held.values()) >= 1e-12:
        out.append(f"law: the committed QASM does not lay {STOCK}'s law here: kernel error "
                   f"{held['kernel_error']:.1e}, law {held['law_error']:.1e}, "
                   f"outside {N} crystals {held['leaked']:.1e}")
    return out, psi


def audit_records(line, submit, counts, records, not_fixed=()):
    """The device rolls against the line, the submit exchange and the result."""
    out = []
    try:
        submitted = utc((submit.get("response") or {}).get("submitted_at"))
    except (TypeError, ValueError):
        submitted = None
        out.append("submit: no server submitted_at to hold fixed_at to")
    laid = {}
    for name, raw in records:
        try:
            rec = json.loads(raw.decode("ascii"))
        except (UnicodeDecodeError, ValueError) as e:
            out.append(f"{name}: unreadable ({e.__class__.__name__})")
            continue
        if not (isinstance(rec, dict) and isinstance(rec.get("source"), dict)
                and isinstance(rec.get("crystals"), list)):
            out.append(f"{name}: not a device roll")
            continue
        if raw != fixer.text(rec).encode("ascii"):
            out.append(f"{name}: its bytes are not fixer.text of the record they hold")
        out += [f"{name}: {p}" for p in fixer.check(rec)]
        src, cs = rec["source"], rec["crystals"]
        if not all(type(q) is int for q in cs) or name != record_name(rec):
            out.append(f"{name}: named for other crystals than it holds")
        if src.get("kind") != KIND:
            out.append(f"{name}: kind {src.get('kind')!r}; this run was {KIND!r}, the only kind the account can run")
        differ = [k for k in (*fixer.COMMITTED, "commitment") if src.get(k) != line.get(k)]
        if differ:
            out.append(f"{name}: {differ} are not the committed line's")
        try:
            fixed = utc(src.get("fixed_at"))
        except (TypeError, ValueError):
            out.append(f"{name}: fixed_at {src.get('fixed_at')!r} is not a UTC time stamp")
        else:
            if submitted is not None and fixed < submitted:
                out.append(f"{name}: fixed_at {src['fixed_at']} is before the job was submitted "
                           f"({submit['response']['submitted_at']})")
        key = tuple(q if type(q) is int else repr(q) for q in cs)
        if key in laid:
            out.append(f"{name}: a second record of the layout {cs}")
        laid[key] = src.get("occurrences")
    for entry in not_fixed:
        key = tuple(entry.get("crystals") or ())
        if key in laid:
            out.append(f"not_fixed: {list(key)} is also a record")
        laid[key] = entry.get("occurrences")
        try:
            fixer.fix_device(STOCK, list(key), roll_source(line, "2000-01-01T00:00:00Z", entry.get("occurrences")))
        except (ValueError, TypeError, KeyError):
            pass
        else:
            out.append(f"not_fixed: {list(key)} is a layout the fixer fixes")
    differ = sum(1 for k in set(laid) | set(counts) if laid.get(k) != counts.get(k))
    if differ:
        out.append(f"records: they are not the committed result read through decode ({differ} layouts differ "
                   "in presence or occurrences)")
    if sum(counts.values()) != line.get("shots"):
        out.append(f"result: {sum(counts.values())} layouts where the line binds {line.get('shots')} shots")
    return out


def audit_score(line, counts, committed):
    """The committed score, recomputed from the committed result."""
    if committed is None:
        return ["score: none committed"]
    K, forbidden, _dets = law_of(STOCK)
    again = score(counts, K, forbidden, line.get("circuit_sha256"))
    out = []
    for path in (("circuit_sha256",), ("shots",), ("distinct_layouts",), ("crystals_per_layout",),
                 ("one_site", "max_abs_z"), ("one_site", "chi2"), ("pairs", "max_abs_z"), ("pairs", "chi2"),
                 ("chi2_per_dof",), ("forbidden", "shots"), ("forbidden", "distinct_laid")):
        a, b = again, committed
        for k in path:
            a, b = a[k], (b or {}).get(k) if isinstance(b, dict) else None
        same = math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12) if isinstance(a, float) and isinstance(b, float) \
            else a == b
        if not same:
            out.append(f"score: {'.'.join(path)} is committed as {b!r}; the committed result gives {a!r}")
    if committed.get("job_id") != line.get("job_id") or committed.get("commitment") != line.get("commitment"):
        out.append("score: its job_id or commitment is not the line's")
    return out


def audit_engine(result, psi, pair=(0, 1)):
    try:
        rows = engine_observables(result, psi, pair)
    except (KeyError, TypeError, ValueError) as e:
        return [f"engine: its observables are not readable ({e.__class__.__name__}: {e})"]
    return [f"engine: {name} measured {m:+.4f} where the committed circuit's state gives {e:+.4f} (z {z:+.1f})"
            for name, m, e, z in rows if abs(z) >= ENGINE_Z]


# ---------------------------------------------------------------- the platform


def _git_blob(path):
    """The id git gives a file's bytes (sha1 of "blob <size>\\0" + bytes): which code ran."""
    with open(path, "rb") as f:
        data = f.read()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def platform_record(qasm, made_by, head):
    """What turns givens_line into this QASM text: Python, numpy, the platform, and
    the libm whose atan2 decides the angles' last bits (the float basis is exact
    once its noise is snapped to zero; math.hypot is CPython's own code; numpy's
    + - * / round correctly). Refused unless THIS machine's module writes exactly
    this text, so the record describes a platform that makes these bytes; the
    code that checked it is named by git blob id, whatever HEAD was."""
    L, r2, M, N = shape()
    A = givens.orbitals(L, r2)
    trace = []
    text = givens_line.to_qasm(givens_line.gates(givens_line.plan(A, trace=trace), N), M)
    if text != qasm:
        raise AssertionError("this machine's givens_line does not write this QASM text; it cannot say what made it")
    magnitudes = sorted({0.0 if abs(v) <= givens_line.ZERO else abs(float(v)) for v in A.ravel()})
    code = {f"quantum_film/{sub}": _git_blob(mod.__file__) for sub, mod in
            (("circuits/givens_line.py", givens_line), ("circuits/givens.py", givens),
             ("stocks.py", sys.modules[params.__module__]))}
    rec = {"circuit_sha256": sha256_text(qasm), "made_by": made_by,
           "checked": {"what": "this machine's module writes exactly these bytes", "head": head,
                       "code (git blob ids)": code},
           "python": {"version": sys.version, "implementation": platform.python_implementation()},
           "numpy": {"version": np.__version__},
           "platform": {"system": platform.system(), "release": platform.release(), "version": platform.version(),
                        "machine": platform.machine(), "processor": platform.processor()},
           "basis": {"magnitudes_after_snapping": [repr(v) for v in magnitudes],
                     "exact": magnitudes == [0.0, 0.25, math.sqrt(0.125)]},
           "atan2_calls": len(trace)}
    try:
        cfg = np.show_config(mode="dicts")
        rec["numpy"]["compilers"] = {k: f"{v.get('name')} {v.get('version')}" for k, v in cfg["Compilers"].items()
                                     if isinstance(v, dict) and k in ("c", "c++")}
        rec["numpy"]["simd"] = {k: cfg["SIMD Extensions"].get(k) for k in ("baseline", "found")}
    except (AttributeError, KeyError, TypeError):
        rec["numpy"]["compilers"] = "not reported by this numpy"
    rec["libm"] = _libm(trace)
    return rec


def _libm(trace):
    """The C library whose atan2 Python's math.atan2 calls, identified and checked
    bit for bit against math.atan2 on the plan's own arguments."""
    if sys.platform != "win32":
        name, version = platform.libc_ver()
        return {"library": name or "unknown", "version": version or "unknown",
                "note": "not Windows: the libm is named by libc_ver only, and not checked call by call"}
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32")
    k32.GetModuleHandleW.restype, k32.GetModuleHandleW.argtypes = wintypes.HMODULE, [wintypes.LPCWSTR]
    k32.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    handle = k32.GetModuleHandleW("ucrtbase.dll")
    if not handle:
        return {"library": "ucrtbase.dll", "loaded": False, "note": "this Python does not use the UCRT"}
    buf = ctypes.create_unicode_buffer(1024)
    k32.GetModuleFileNameW(handle, buf, 1024)
    path = buf.value
    with open(path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    c_atan2 = ctypes.CDLL(path).atan2
    c_atan2.restype, c_atan2.argtypes = ctypes.c_double, [ctypes.c_double, ctypes.c_double]
    same = sum(math.atan2(b, a).hex() == c_atan2(b, a).hex() for a, b in trace)
    rng = np.random.default_rng(0)
    probe = [(float(a), float(b)) for a, b in rng.standard_normal((10000, 2))]
    same_probe = sum(math.atan2(b, a).hex() == c_atan2(b, a).hex() for a, b in probe)
    return {"library": "ucrtbase.dll (the Universal C Runtime)", "path": path, "file_version": _file_version(path),
            "sha256": sha, "math.atan2 equals its atan2 bit for bit": {
                "on the plan's calls": f"{same} of {len(trace)}",
                "on 10,000 random arguments": f"{same_probe} of 10000"}}


def _file_version(path):
    import ctypes
    from ctypes import wintypes
    ver = ctypes.WinDLL("version")
    ver.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    ver.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    ver.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    ver.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_void_p),
                                   ctypes.POINTER(wintypes.UINT)]
    size = ver.GetFileVersionInfoSizeW(path, None)
    buf = ctypes.create_string_buffer(size)
    p, n = ctypes.c_void_p(), wintypes.UINT()
    if not size or not ver.GetFileVersionInfoW(path, 0, size, buf) or \
            not ver.VerQueryValueW(buf, "\\", ctypes.byref(p), ctypes.byref(n)):
        return "unknown"
    words = ctypes.cast(p, ctypes.POINTER(wintypes.DWORD * 4)).contents      # signature, struct version, MS, LS
    ms, ls = words[2], words[3]
    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"

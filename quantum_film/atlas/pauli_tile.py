"""The pauli-4x4 stock on tomography-api-v2: everything but the network.

tools/pauli_atlas_run.py drives this; nothing here calls Atlas, so everything
here is testable offline (tests/circuits/test_pauli_tile.py).

THE ORDER A DEVICE ROLL IS MADE IN (docs/ROUND1.md, P3):
  1. The circuit sent is circuits.givens_line's circuit for the stock, held to
     the authority's law on a local statevector first (`check_circuit`). The
     fixer binds only a circuit's SHA-256, so this is where the law is bound.
  2. The job is submitted. Its commitment is formed from what is known at
     submission (stock, circuit SHA-256, engine, job id, shots, decode rule,
     salt), and committed to git with the exact QASM text BEFORE any status or
     result is fetched. Once a job has completed, its STATUS response carries
     the whole result as well (the 2026-09-25 records in docs/records show it),
     so a status poll counts as a fetch.
  3. The result is read through decode.layouts, and nothing else, and scored
     against the authority's kernel with atlas_tile_compare.py's statistics
     (research/2026-09-25/emulsions/), the circuit's SHA-256 beside the score.
  4. One device roll is fixed per distinct layout, `occurrences` counting its
     shots. A layout the law forbids is fixed like any other: a device records
     what it laid. Its count is the score's witness of noise.
"""
import hashlib
import itertools
import json
import math
import re

import numpy as np

from .. import fixer
from ..circuits import givens_line
from ..golden import fermi
from ..stocks import params
from . import decode

STOCK = "pauli-4x4"
ENGINE = "tomography-api-v2"
KIND = "atlas-emu"
DECODE = "quantum_film.atlas.decode/v1"      # decode.layouts, as at b0e9ed1; committed before submission
SHOTS = 4096
FORBIDDEN_BELOW = 1e-9     # as tests/golden/test_golden_law.py: allowed det >= 2.4e-4, forbidden |det| <= 6.5e-19
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


def sha256_text(text):
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def check_circuit(gate_list, K, N):
    """A gate list against the authority on a local statevector: the kernel
    statistics (<n_i>, <n_i n_j>) and the whole layout law."""
    M = len(K)
    psi = givens_line.simulate(gate_list, M)
    n1, n2 = givens_line.occupations(psi)
    e2 = np.outer(np.diag(K), np.diag(K)) - K ** 2
    np.fill_diagonal(e2, 0.0)
    kernel_error = max(float(np.max(np.abs(n1 - np.diag(K)))), float(np.max(np.abs(n2 - e2))))
    law, leaked = givens_line.layout_law(psi, N)
    _forb, dets = forbidden_layouts(K, N)
    law_error = max(abs(law[Y] - d) for Y, d in dets.items())
    return {"kernel_error": kernel_error, "law_error": law_error, "leaked": leaked}


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
    """The job body. Every qubit is in qubit_list, so the all-Z setting is
    active on all of them and decode's rule reads it in plain order. The shape
    (full list, one pair, single and double tomography) is the one the
    2026-09-25 known-answer runs used (jobs 93924d11, 5ad38bfe, e4d62182,
    4cc3c663)."""
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


def device_rolls(counts, line, fixed_at, stock=STOCK):
    """One record per distinct layout, `occurrences` its shots. -> (records, refused),
    refused being (layout, shots, the fixer's reason): a layout the fixer will
    not seal is reported, never reshaped into one it will."""
    records, refused = [], []
    for Y, c in sorted(counts.items()):
        src = {"kind": KIND, "fixed_at": fixed_at, "occurrences": c,
               **{k: line[k] for k in (*fixer.COMMITTED, "commitment")}}
        try:
            records.append(fixer.fix_device(stock, list(Y), src))
        except ValueError as e:
            refused.append((list(Y), c, str(e)))
    return records, refused


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

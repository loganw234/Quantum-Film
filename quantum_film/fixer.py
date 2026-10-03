"""The fixer: the bath that makes a developed image permanent.

A roll of quantum film is unique. Its crystals were laid by the Born rule (on
a device) or by a stream of exact uniforms (in emulation). The fixer makes it
permanent: it writes the roll as a NEGATIVE RECORD, integers and provenance
with nothing that rounds, named by the SHA-256 of its canonical bytes. After
that, everything is computed from the record, so the roll never has to be
reproduced, only read.

CANONICAL BYTES: JSON with sorted keys, no whitespace, ASCII only. The digest
covers every field except the digest itself.

THE FILE: a record on disk is exactly `text(record)`, byte for byte (sorted
keys, a one-space indent, ASCII, a final newline). The command line refuses a
file whose bytes are anything else, so a file cannot carry a second, unsealed
reading of itself, such as a duplicated key that one JSON reader takes and
another ignores (verifier-P0, 2026-09-25).

The record carries the law it was laid under (the stock's resolved
parameters at fixing time). A later change to the shelf therefore cannot
quietly reinterpret an old roll: `check` refuses a record whose law is no
longer the shelf's, by name.

An EMULATED roll's record carries no wall-clock time. The same stock and
stream give the same crystals on any machine, and the same record, byte for
byte, from the same version of this package: the digest also covers
`code.quantum_film`, the version that fixed it. `reproduce` compares the roll
itself (stock, law, stream and crystals), so a later version that lays the
same roll still reproduces it. A roll from a device carries `fixed_at`,
because there the event is the thing.

A DEVICE RUN (`quantum-film/device-run/v1`, round 3) is every shot of one
circuit in one hardware job, in one record, with a commitment (v3) that binds
the route, the backend and the exact circuit the device ran. `check` reads
either kind of record by its format.

The constructors refuse what `check` refuses: `fix` seals nothing that
`check` would reject, and never rounds a value into shape.

    python -m quantum_film.fixer check FILE...    # 0 = every record intact, 1 = refused
    python -m quantum_film.fixer lay STOCK SEED   # print a golden roll's record
"""
import datetime
import hashlib
import json
import re
import sys
from itertools import pairwise

from . import __version__
from .golden.uniform import stream
from .stocks import STOCKS, params

FORMAT = "quantum-film/negative/v1"
FIELDS = ("format", "stock", "law", "crystals", "source", "code", "digest")
SOURCES = ("golden", "local-emu", "atlas-emu", "qpu")
DEVICE = ("atlas-emu", "qpu")
GOLDEN_SOURCE = ("authority", "kind", "stream")
COMMITMENT_DOMAIN = "quantum-film/commitment/v2"
_HEX64 = set("0123456789abcdef")

# A DEVICE ROLL (Atlas or a QPU) carries the job it came from and a commitment
# to everything known when the job was SUBMITTED, before any result existed:
#     commitment = SHA-256(stream(COMMITMENT_DOMAIN, stock, circuit_sha256,
#                                 engine, job_id, shots, decode, salt))
# `stream` is golden.uniform's encoding: each field length-prefixed and
# type-tagged, so no field can absorb its neighbour. (v1 joined the fields with
# a bare "|", and an engine and a job could be re-attributed together with the
# commitment intact; no v1 device roll was ever fixed.)
#
# `check` recomputes the commitment, so a record whose fields do not match its
# own commitment is refused. That is all the record can do alone: the salt is
# in the record, so whoever changes a field can recompute the commitment too
# (verifier-P3, 2026-09-26). What binds a device roll is its ANCHOR: the
# commitment published, in a git commit, before the job's first status call
# (a completed job's status already carries its result). A reader holds each
# roll to that published line, as P3's records test does for its run's rolls
# against its committed commitments.jsonl.
#
# What the record alone CANNOT prove:
#   - that the commitment was formed before the result existed; only the
#     anchor evidences that, and today only by the local clock and the code;
#   - which law the circuit lays. The commitment binds circuit_sha256, and a
#     reader must check that hash against the stock's circuit;
#   - `kind`, `fixed_at` and `occurrences`, which no commitment binds (kind is
#     known at submission and a later version should bind it; fixed_at comes
#     after the result by design). The anchor's run holds them;
#   - that the layout is one the law allows. A device records what it laid,
#     noise included: a layout the law forbids, or a crystal count it never
#     lays, is kept, not refused.
DEVICE_FIELDS = {"fixed_at": str, "engine": str, "job_id": str, "circuit_sha256": str,
                 "shots": int, "decode": str, "salt": str, "commitment": str}
DEVICE_OPTIONAL = {"occurrences": int}      # how many shots laid this layout, when a run fixes one per layout
COMMITTED = ("circuit_sha256", "engine", "job_id", "shots", "decode", "salt")
_UTC = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z", re.ASCII)
LOCAL_FIELDS = ("backend", "fixed_at", "kind")

# A DEVICE RUN (round 3, 2026-10-03) is every shot of ONE circuit in ONE
# hardware job, in one record. A device roll is one layout, and hardware noise
# spreads a run over thousands of distinct layouts: one Atlas job already made
# 1,995 files (docs/ROADMAP.md, carried from round 1).
#   counts  [[ones, occurrences], ...]: `ones` the logical qubits that read 1
#           in the measured basis, strictly increasing; sorted by `ones`, no
#           `ones` twice, occurrences >= 1 and summing to the run's shots. A
#           run records what the device laid, noise included: any crystal count.
#   role    what the circuit was for: "known-answer" (the read-out order, held
#           to a circuit with a known result), "law" (the stock's law: these
#           are crystal layouts), "coherence" (the law's circuit with basis
#           rotations: what a classical mixture with the same layouts lacks).
#   basis   one letter per logical qubit, X, Y or Z, the basis each was read in.
#           basis[q] is qubit q, qubit 0 FIRST: the opposite of a bitstring,
#           and of Qiskit's Pauli labels, which put qubit 0 last.
#   kind    "qpu" for a device (its backend must be an IBM device's name),
#           "simulator" for anything else that ran the same path, such as a dry
#           run on a fake backend (its backend must not look like a device's).
#   pub     the circuit's index in its job. Two circuits of one job differ by
#           it, so two runs with the same shots cannot be swapped unseen.
# The options are the options AS SENT, as the primitive serialises them.
# - They must state dynamical decoupling and both twirlings, true or false.
#   The legacy SamplerV2 sends exactly
#   {"dynamical_decoupling": {"enable": false}, "twirling": {"enable_gates":
#   false, "enable_measure": false}}. The executor Sampler's full options dump
#   has the same paths (measured by round 3's P0 verifier). STATED_OPTIONS
#   names the paths.
# - decode must be a rule this package reads (RUN_DECODES).
# The commitment (v3) binds everything known BEFORE submission: what ran, where
# and how, and the decode rule. The job id is known only after, so the record
# carries it beside the commitment, and the job line binds the two (JOB_FORMAT,
# below): committed and pushed after submission and before any result is read.
# For a run made from a frozen bundle, the bundle's own commit before it left
# this repository is a second anchor. What v2 left unbound, v3 binds: the kind,
# the route, the backend, the job's PUB index and the exact circuit that ran.
RUN_FORMAT = "quantum-film/device-run/v1"
RUN_FIELDS = ("format", "stock", "law", "role", "basis", "counts", "source", "code", "digest")
ROLES = ("known-answer", "law", "coherence")
RUN_KINDS = ("qpu", "simulator")
ROUTES = ("ibm-direct", "moth")
RUN_DECODES = ("quantum_film.ibm.decode/v1",)
STATED_OPTIONS = (("dynamical_decoupling", "enable"), ("twirling", "enable_gates"), ("twirling", "enable_measure"))
COMMITMENT_V3 = "quantum-film/commitment/v3"
RUN_COMMITTED = ("kind", "route", "backend", "program", "pub", "circuit_sha256", "isa_sha256", "shots",
                 "options_sha256", "decode", "salt")
RUN_SOURCE = {"kind": str, "route": str, "backend": str, "program": str, "job_id": str, "pub": int,
              "circuit_sha256": str, "isa_sha256": str, "shots": int, "options": dict, "options_sha256": str,
              "decode": str, "salt": str, "commitment": str, "submitted_at": str, "fixed_at": str}
_NAME = re.compile(r"[a-z][a-z0-9_-]{0,63}", re.ASCII)            # a backend or program name
_DEVICE = re.compile(r"ibm_[a-z]+", re.ASCII)                      # an IBM Quantum device: a qpu run's backend
_JOB = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", re.ASCII)    # a provider's job id


def _is_utc(s):
    """A real UTC time in ASCII digits. The first check read only a shape, and passed
    month 13 and Arabic-Indic digits (the P0 verifier's fourth pass)."""
    if not (isinstance(s, str) and _UTC.fullmatch(s)):
        return False
    try:
        datetime.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return False
    return True


def commitment(*, stock, circuit_sha256, engine, job_id, shots, decode, salt):
    msg = stream(COMMITMENT_DOMAIN, stock, circuit_sha256, engine, job_id, shots, decode, salt)
    return hashlib.sha256(msg).hexdigest()


def commitment_v3(*, stock, role, basis, kind, route, backend, program, pub, circuit_sha256, isa_sha256, shots,
                  options_sha256, decode, salt):
    """A device run's commitment: SHA-256 of golden.uniform's stream of these fields, all known at submission.
    The record's other fields (job_id, submitted_at, fixed_at, counts, code) are not in it."""
    msg = stream(COMMITMENT_V3, stock, role, basis, kind, route, backend, program, pub, circuit_sha256, isa_sha256,
                 shots, options_sha256, decode, salt)
    return hashlib.sha256(msg).hexdigest()


def options_digest(options):
    """The SHA-256 of the run options' canonical JSON (sorted keys, no whitespace, ASCII)."""
    return hashlib.sha256(json.dumps(options, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode("ascii")).hexdigest()


def canonical(record):
    body = {k: v for k, v in record.items() if k != "digest"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def digest(record):
    return hashlib.sha256(canonical(record)).hexdigest()


def text(record):
    """The one file form of a record."""
    return json.dumps(record, sort_keys=True, indent=1, ensure_ascii=True) + "\n"


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def fix(stock_id, crystals, source):
    """Make a negative record from a layout and the source that laid it."""
    if not isinstance(crystals, (list, tuple)) or not all(_is_int(c) for c in crystals):
        raise ValueError("the fixer refuses this layout: crystals: not a list of integers "
                         "(it rounds nothing into shape)")
    law = params(stock_id)
    rec = {"format": FORMAT, "stock": stock_id, "law": law, "crystals": list(crystals),
           "source": source, "code": {"quantum_film": __version__}}
    rec["digest"] = digest(rec)
    problems = check(rec)
    if problems:
        raise ValueError("the fixer refuses this layout: " + "; ".join(problems))
    return rec


def _layout_problems(rec, law):
    out = []
    cs = rec.get("crystals")
    if not isinstance(cs, list) or not all(_is_int(c) for c in cs):
        return ["crystals: not a list of integers"]
    if any(b <= a for a, b in pairwise(cs)):
        out.append("crystals: not strictly increasing (sorted, no site twice)")
    if cs and (cs[0] < 0 or cs[-1] >= law["M"]):
        out.append(f"crystals: a site outside 0..{law['M'] - 1}")
    laid_by_a_device = isinstance(rec.get("source"), dict) and rec["source"].get("kind") in DEVICE
    if law["family"] in ("determinantal", "binomial") and len(cs) != law["N"] and not laid_by_a_device:
        out.append(f"count: {len(cs)} crystals where the {law['family']} law lays exactly {law['N']}")
    return out


def _same_json(a, b):
    """Equal as JSON, not as Python: true is not 1, and 16.0 is not 16."""
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def check(record):
    """The named reasons this record is refused; an empty list means fixed and intact."""
    out = []
    if not isinstance(record, dict):
        return ["not a record"]
    if record.get("format") == RUN_FORMAT:
        return check_run(record)
    extra = sorted(set(record) - set(FIELDS))
    if extra:
        out.append(f"fields: unexpected {extra}; a record carries exactly {list(FIELDS)}")
    if record.get("format") != FORMAT:
        out.append(f"format: {record.get('format')!r} is not {FORMAT!r}")
    sid = record.get("stock")
    if not isinstance(sid, str) or sid not in STOCKS:
        return out + [f"stock: {sid!r} is not on the shelf"]
    try:
        law = params(sid)
    except LookupError as e:
        return out + [f"stock: {e}"]
    if not _same_json(record.get("law"), law):
        out.append("law: the record was laid under a law the shelf no longer states")
    out += _layout_problems(record, law)
    src = record.get("source")
    if not isinstance(src, dict) or src.get("kind") not in SOURCES:
        out.append(f"source: kind must be one of {SOURCES}")
    elif src["kind"] == "golden":
        out += _golden_problems(src, sid)
    elif "fixed_at" not in src:
        out.append("source: a roll from a device must carry fixed_at")
    elif src["kind"] in DEVICE:
        out += _device_problems(src, sid)
    else:                                  # a local emulator: the same rules on its fields as a device's
        if not isinstance(src.get("backend"), str):
            out.append("source: a local-emu roll must name its backend")
        if not _is_utc(src.get("fixed_at")):
            out.append("source: fixed_at must be a UTC time, YYYY-MM-DDTHH:MM:SSZ")
        unknown = sorted(set(src) - set(LOCAL_FIELDS))
        if unknown:
            out.append(f"source: {unknown} are fields the fixer does not know; they would ride unchecked")
    code = record.get("code")
    if not (isinstance(code, dict) and list(code) == ["quantum_film"] and isinstance(code["quantum_film"], str)):
        out.append('code: exactly {"quantum_film": <the version that fixed it>}')
    if record.get("digest") != digest(record):
        out.append("digest: the record's bytes are not the bytes it was fixed with")
    return out


def authority(law):
    """The authority a golden roll of this law names: one fact, read by lay() and by check()."""
    if law["family"] == "determinantal":
        from .golden import fermi
        return {"module": "quantum_film.golden.fermi", "prec": fermi.PREC}
    if law["family"] == "binomial":
        return {"module": "quantum_film.golden.binomial"}
    raise LookupError(f"no golden sampler for the {law['family']} family")


def _golden_problems(src, sid):
    out = []
    if sorted(src) != sorted(GOLDEN_SOURCE):
        out.append(f"source: a golden roll's source is exactly {list(GOLDEN_SOURCE)}, "
                   "with no wall-clock time, so its record is the same on every machine")
    parts = src.get("stream")
    if not (isinstance(parts, list) and len(parts) == 3 and parts[:2] == ["roll", sid] and _is_int(parts[2])):
        out.append(f'source: a golden roll\'s stream is ["roll", {sid!r}, <integer seed>]')
    try:
        want = authority(params(sid))
    except LookupError as e:
        return out + [f"source: {e}"]
    if not _same_json(src.get("authority"), want):
        out.append(f"source: a golden roll of {sid!r} names its authority as exactly {want}")
    return out


def _device_problems(src, sid):
    out = []
    for field, kind in DEVICE_FIELDS.items():
        v = src.get(field)
        if not isinstance(v, kind) or isinstance(v, bool):
            out.append(f"source: a {src['kind']} roll must carry {field} ({kind.__name__})")
    unknown = sorted(set(src) - {"kind"} - set(DEVICE_FIELDS) - set(DEVICE_OPTIONAL))
    if unknown:
        out.append(f"source: {unknown} are fields the fixer does not know; they would ride unchecked")
    if out:
        return out
    for field in ("circuit_sha256", "salt", "commitment"):
        if len(src[field]) != 64 or not set(src[field]) <= _HEX64:
            out.append(f"source: {field} must be 64 lowercase hex digits")
    if src["shots"] < 1:
        out.append("source: shots must be positive")
    if not _is_utc(src["fixed_at"]):
        out.append("source: fixed_at must be a UTC time, YYYY-MM-DDTHH:MM:SSZ")
    if "occurrences" in src and not (_is_int(src["occurrences"]) and 1 <= src["occurrences"] <= src["shots"]):
        out.append("source: occurrences must be a whole number of shots, from 1 to shots")
    if not out and src["commitment"] != commitment(stock=sid, **{k: src[k] for k in COMMITTED}):
        out.append("source: the commitment does not bind this stock, circuit, engine, job, shots, decode and salt")
    return out


def fix_device(stock_id, crystals, source):
    """Fix a roll laid by a device. `source` must carry DEVICE_FIELDS, the
    commitment included; the record is refused rather than fixed incomplete."""
    rec_source = dict(source)
    problems = _device_problems(rec_source, stock_id) if rec_source.get("kind") in DEVICE else \
        [f"source: kind must be one of {DEVICE}"]
    if problems:
        raise ValueError("the fixer refuses this device roll: " + "; ".join(problems))
    return fix(stock_id, crystals, rec_source)


def _option(options, path):
    """The value at a nested path of the options as sent, or None when the path is not there."""
    for key in path:
        if not isinstance(options, dict) or key not in options:
            return None
        options = options[key]
    return options


def _utc_time(s):
    """A checked UTC string as a datetime, to the microsecond: a fraction counts (verifier-P0, round 3, 1a)."""
    fraction = s[20:-1] if s[19] == "." else ""
    return datetime.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S").replace(
        microsecond=int((fraction + "000000")[:6]))


def _counts_problems(counts, M, shots):
    if not isinstance(counts, list) or not counts:
        return ["counts: a non-empty list of [ones, occurrences] pairs"]
    total, previous = 0, None
    for i, pair in enumerate(counts):
        if not (isinstance(pair, list) and len(pair) == 2):
            return [f"counts[{i}]: not an [ones, occurrences] pair"]
        ones, n = pair
        if not (isinstance(ones, list) and all(_is_int(q) for q in ones)):
            return [f"counts[{i}]: ones is not a list of integers"]
        if any(b <= a for a, b in pairwise(ones)):
            return [f"counts[{i}]: ones not strictly increasing (sorted, no qubit twice)"]
        if ones and (ones[0] < 0 or ones[-1] >= M):
            return [f"counts[{i}]: a qubit outside 0..{M - 1}"]
        if not (_is_int(n) and n >= 1):
            return [f"counts[{i}]: occurrences must be a whole number of shots, at least 1"]
        if previous is not None and not previous < ones:
            return [f"counts[{i}]: not in canonical order (sorted by ones, none twice)"]
        previous, total = ones, total + n
    if _is_int(shots) and total != shots:
        return [f"counts: {total} shots counted where the run took {shots}"]
    return []


def _run_source_problems(src):
    out = []
    for field, kind in RUN_SOURCE.items():
        v = src.get(field)
        if not isinstance(v, kind) or isinstance(v, bool):
            out.append(f"source: a device run must carry {field} ({kind.__name__})")
    unknown = sorted(set(src) - set(RUN_SOURCE))
    if unknown:
        out.append(f"source: {unknown} are fields the fixer does not know; they would ride unchecked")
    if out:
        return out
    if src["kind"] not in RUN_KINDS:
        out.append(f"source: a device run's kind is one of {RUN_KINDS}")
    if src["route"] not in ROUTES:
        out.append(f"source: route must be one of {ROUTES}")
    for field in ("backend", "program"):
        if not _NAME.fullmatch(src[field]):
            out.append(f"source: {field} must be a lowercase name ([a-z][a-z0-9_-]*)")
    if src["kind"] == "qpu" and not _DEVICE.fullmatch(src["backend"]):
        out.append("source: a qpu run's backend must be an IBM device (ibm_<name>); a simulator is kind simulator")
    if src["kind"] == "simulator" and _DEVICE.fullmatch(src["backend"]):
        out.append("source: a simulator run may not name an IBM device as its backend")
    if not _JOB.fullmatch(src["job_id"]):
        out.append("source: job_id must be a provider's job id ([A-Za-z0-9_-]+)")
    if src["pub"] < 0:
        out.append("source: pub is the circuit's index in its job, from 0")
    for field in ("circuit_sha256", "isa_sha256", "options_sha256", "salt", "commitment"):
        if len(src[field]) != 64 or not set(src[field]) <= _HEX64:
            out.append(f"source: {field} must be 64 lowercase hex digits")
    if src["shots"] < 1:
        out.append("source: shots must be positive")
    if src["decode"] not in RUN_DECODES:
        out.append(f"source: decode must name a rule this package reads, one of {RUN_DECODES}")
    unstated = [".".join(path) for path in STATED_OPTIONS if not isinstance(_option(src["options"], path), bool)]
    if unstated:
        out.append(f"source: the options as sent must state {unstated}, true or false")
    for field in ("submitted_at", "fixed_at"):
        if not _is_utc(src[field]):
            out.append(f"source: {field} must be a UTC time, YYYY-MM-DDTHH:MM:SSZ")
    if out:
        return out
    if _utc_time(src["fixed_at"]) < _utc_time(src["submitted_at"]):
        out.append("source: fixed_at comes before submitted_at; a run is fixed after it is submitted")
    if options_digest(src["options"]) != src["options_sha256"]:
        out.append("source: options_sha256 is not the digest of the options the record carries")
    return out


def check_run(record):
    """The named reasons a device-run record is refused; an empty list means fixed and intact."""
    out = []
    extra = sorted(set(record) - set(RUN_FIELDS))
    if extra:
        out.append(f"fields: unexpected {extra}; a run record carries exactly {list(RUN_FIELDS)}")
    missing = sorted(set(RUN_FIELDS) - set(record))
    if missing:
        out.append(f"fields: missing {missing}")
    sid = record.get("stock")
    if not isinstance(sid, str) or sid not in STOCKS:
        return out + [f"stock: {sid!r} is not on the shelf"]
    try:
        law = params(sid)
    except LookupError as e:
        return out + [f"stock: {e}"]
    if not _same_json(record.get("law"), law):
        out.append("law: the record was laid under a law the shelf no longer states")
    M, role, basis = law["M"], record.get("role"), record.get("basis")
    framed = True
    if role not in ROLES:
        out.append(f"role: must be one of {ROLES}")
        framed = False
    if not (isinstance(basis, str) and len(basis) == M and set(basis) <= set("XYZ")):
        out.append(f"basis: one of X, Y or Z for each of the {M} qubits")
        framed = False
    elif role in ("known-answer", "law") and basis != "Z" * M:
        out.append(f"basis: a {role} run is read in Z on every qubit")
    elif role == "coherence" and basis == "Z" * M:
        out.append("basis: a coherence run reads at least one qubit out of Z")
    src = record.get("source")
    out += _counts_problems(record.get("counts"), M, src.get("shots") if isinstance(src, dict) else None)
    if not isinstance(src, dict):
        out.append("source: not an object")
    else:
        problems = _run_source_problems(src)
        out += problems
        if not problems and framed and src["commitment"] != commitment_v3(
                stock=sid, role=role, basis=basis, **{k: src[k] for k in RUN_COMMITTED}):
            out.append("source: the commitment does not bind this stock, role, basis, route, backend, program, "
                       "circuit, ISA circuit, shots, options, decode and salt")
    code = record.get("code")
    if not (isinstance(code, dict) and list(code) == ["quantum_film"] and isinstance(code["quantum_film"], str)):
        out.append('code: exactly {"quantum_film": <the version that fixed it>}')
    if record.get("digest") != digest(record):
        out.append("digest: the record's bytes are not the bytes it was fixed with")
    return out


def fix_run(stock_id, role, basis, counts, source):
    """Fix a device run: every shot of one circuit in one hardware job. `counts` must already be
    canonical ([[ones, occurrences], ...] sorted by ones); the record is refused, never reshaped."""
    rec = {"format": RUN_FORMAT, "stock": stock_id, "law": params(stock_id), "role": role, "basis": basis,
           "counts": counts, "source": dict(source), "code": {"quantum_film": __version__}}
    rec["digest"] = digest(rec)
    problems = check_run(rec)
    if problems:
        raise ValueError("the fixer refuses this device run: " + "; ".join(problems))
    return rec


# THE JOB LINE (round 3) is what a runner writes, git-commits and pushes after
# it submits a job and before it reads any result.
# - Timing: on IBM, status and result are separate calls, and a job's created
#   time is read with a status call, so a status call may come first.
# - Content: the line names the job and the commitments its circuits were
#   submitted with, in PUB order. Every run record of the job is held to a line
#   that existed before its counts could be read (`held_to_line`).
# - Once only: a runner submits a bundle once. A bundle that already has a line
#   is never submitted again, so no two jobs share one set of commitments.
JOB_FORMAT = "quantum-film/hardware-job/v1"
JOB_LINE = {"format": str, "stock": str, "kind": str, "route": str, "backend": str, "program": str, "job_id": str,
            "submitted_at": str, "bundle_sha256": str, "commitments": list}


def check_job_line(line):
    """The named reasons a job line is refused; an empty list means well formed."""
    if not isinstance(line, dict):
        return ["job line: not an object"]
    out = []
    for field, kind in JOB_LINE.items():
        v = line.get(field)
        if not isinstance(v, kind) or isinstance(v, bool):
            out.append(f"job line: must carry {field} ({kind.__name__})")
    unknown = sorted(set(line) - set(JOB_LINE))
    if unknown:
        out.append(f"job line: {unknown} are fields it does not know")
    if out:
        return out
    if line["format"] != JOB_FORMAT:
        out.append(f"job line: format {line['format']!r} is not {JOB_FORMAT!r}")
    if line["stock"] not in STOCKS:
        out.append(f"job line: stock {line['stock']!r} is not on the shelf")
    if line["kind"] not in RUN_KINDS or line["route"] not in ROUTES:
        out.append(f"job line: kind is one of {RUN_KINDS} and route one of {ROUTES}")
    elif (line["kind"] == "qpu") != bool(_DEVICE.fullmatch(line["backend"])):
        out.append("job line: a qpu job names an IBM device, and only a qpu job does")
    if not (_NAME.fullmatch(line["backend"]) and _NAME.fullmatch(line["program"])):
        out.append("job line: backend and program must be lowercase names")
    if not _JOB.fullmatch(line["job_id"]):
        out.append("job line: job_id must be a provider's job id ([A-Za-z0-9_-]+)")
    if not _is_utc(line["submitted_at"]):
        out.append("job line: submitted_at must be a UTC time, YYYY-MM-DDTHH:MM:SSZ")
    hexes = [line["bundle_sha256"], *line["commitments"]]
    if not line["commitments"] or not all(isinstance(h, str) and len(h) == 64 and set(h) <= _HEX64 for h in hexes):
        out.append("job line: bundle_sha256 and each commitment are 64 lowercase hex digits, at least one commitment")
    elif len(set(line["commitments"])) != len(line["commitments"]):
        out.append("job line: a commitment appears twice")
    return out


def held_to_line(record, line):
    """The named reasons a device run is not the run its job line committed to; [] when it is."""
    out = check_job_line(line)
    if out:
        return out
    src = record.get("source") if isinstance(record, dict) else None
    if not isinstance(src, dict):
        return ["line: the record has no source"]
    if record.get("stock") != line["stock"]:
        out.append("line: the record's stock is not the line's")
    for field in ("kind", "route", "backend", "program", "job_id", "submitted_at"):
        if src.get(field) != line[field]:
            out.append(f"line: the record's {field} is not the line's")
    pub = src.get("pub")
    if not (_is_int(pub) and 0 <= pub < len(line["commitments"])):
        out.append("line: the record's pub is not one of the line's circuits")
    elif src.get("commitment") != line["commitments"][pub]:
        out.append(f"line: the record's commitment is not the one the line committed for pub {pub}")
    return out


def lay(stock_id, seed):
    """A golden roll of `stock_id`, fixed. Stream: ("roll", stock_id, seed)."""
    from .golden import binomial, fermi
    if not _is_int(seed):
        raise ValueError(f"a seed is an integer, not {seed!r}")
    law = params(stock_id)
    parts = ["roll", stock_id, seed]
    s = stream(*parts)
    named = authority(law)
    if law["family"] == "determinantal":
        crystals = fermi.sample(law["L"], law["fermi_r2"], s)
    else:
        crystals = binomial.sample(law["M"], law["N"], s)
    return fix(stock_id, crystals, {"kind": "golden", "stream": parts, "authority": named})


def reproduce(record):
    """Re-lay a golden roll from its record, and say whether this code lays the
    same roll: the same crystals under the same law from the same stream. The
    digest is not compared, because it also covers the version that fixed it."""
    if record.get("source", {}).get("kind") != "golden":
        raise ValueError("only a golden roll can be reproduced; a device roll can only be read")
    parts = record["source"]["stream"]
    if parts[:2] != ["roll", record["stock"]] or len(parts) != 3:
        raise ValueError(f"stream {parts!r} is not a roll stream of {record['stock']!r}")
    again = lay(record["stock"], parts[2])
    same = all(_same_json(again[k], record[k]) for k in ("format", "stock", "law", "crystals")) \
        and _same_json(again["source"], record["source"])
    return same, again


def _no_twice(pairs):
    keys = [k for k, _ in pairs]
    twice = sorted({k for k in keys if keys.count(k) > 1})
    if twice:
        raise ValueError(f"a key appears twice: {twice}")
    return dict(pairs)


def check_file(path):
    """The named reasons the record in this file is refused, its bytes included."""
    try:
        raw = open(path, "rb").read()
        rec = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_twice)
    except (OSError, UnicodeDecodeError, ValueError) as e:
        return None, [f"unreadable: {e}"]
    problems = check(rec)
    if raw != text(rec).encode("ascii", "replace"):
        problems.append("bytes: the file is not the record's canonical text (fixer.text)")
    return rec, problems


def main(argv):
    if len(argv) >= 2 and argv[0] == "check":
        bad = 0
        for f in argv[1:]:
            rec, problems = check_file(f)
            if problems:
                bad += 1
                print(f"REFUSED {f}")
                for p in problems:
                    print(f"   {p}")
            elif rec.get("format") == RUN_FORMAT:
                print(f"fixed   {f}  {rec['digest'][:16]}  {rec['stock']}, a {rec['role']} run: "
                      f"{rec['source']['shots']} shots, {len(rec['counts'])} distinct outcomes")
            else:
                print(f"fixed   {f}  {rec['digest'][:16]}  {rec['stock']}, {len(rec['crystals'])} crystals")
        return 1 if bad else 0
    if len(argv) == 3 and argv[0] == "lay":
        try:
            seed = int(argv[2])
        except ValueError:
            print(f"REFUSED: a seed is an integer, not {argv[2]!r}")
            return 2
        try:
            record = lay(argv[1], seed)
        except LookupError as e:                   # an unknown stock (KeyError) or one not on the shelf
            print(f"REFUSED: {e.args[0] if e.args else e}")
            return 2
        sys.stdout.write(text(record))
        return 0
    print(__doc__.split("\n\n")[-1])
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

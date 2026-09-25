"""The fixer: the bath that makes a developed image permanent.

A roll of quantum film is unique. Its crystals were laid by the Born rule (on
a device) or by a stream of exact uniforms (in emulation). The fixer makes it
permanent: it writes the roll as a NEGATIVE RECORD, integers and provenance
with nothing that rounds, named by the SHA-256 of its canonical bytes. After
that, everything is computed from the record, so the roll never has to be
reproduced, only read.

CANONICAL BYTES: JSON with sorted keys, no whitespace, ASCII only. The digest
covers every field except the digest itself.

The record carries the law it was laid under (the stock's resolved
parameters at fixing time). A later change to the shelf therefore cannot
quietly reinterpret an old roll: `check` refuses a record whose law is no
longer the shelf's, by name.

An EMULATED roll's record carries no wall-clock time. The same stock and
stream give the same record, and so the same digest, on any machine: that is
the reproducibility claim, and `reproduce` tests it. A roll from a device
carries `fixed_at`, because there the event is the thing.

    python -m quantum_film.fixer check FILE...    # 0 = every record intact, 1 = refused
    python -m quantum_film.fixer lay STOCK SEED   # print a golden roll's record
"""
import hashlib
import json
import sys
from itertools import pairwise

from . import __version__
from .stocks import STOCKS, params

FORMAT = "quantum-film/negative/v1"
SOURCES = ("golden", "local-emu", "atlas-emu", "qpu")
DEVICE = ("atlas-emu", "qpu")
COMMITMENT_DOMAIN = "quantum-film/commitment/v1"
_HEX64 = set("0123456789abcdef")

# A DEVICE ROLL (Atlas or a QPU) carries the job it came from and a commitment:
#     commitment = SHA-256(COMMITMENT_DOMAIN | circuit_sha256 | engine | job_id | salt)
# `check` recomputes it, so a record cannot be re-attributed to another circuit
# or job without the refusal naming it. What the record alone CANNOT prove is
# that the commitment was formed before the result existed. That is evidenced
# only if the commitment was published (committed to git, say) before the
# result was fetched, and the device-roll runner is responsible for doing that.
DEVICE_FIELDS = {"fixed_at": str, "engine": str, "job_id": str, "circuit_sha256": str,
                 "shots": int, "decode": str, "salt": str, "commitment": str}


def commitment(circuit_sha256, engine, job_id, salt):
    msg = "|".join((COMMITMENT_DOMAIN, circuit_sha256, engine, job_id, salt))
    return hashlib.sha256(msg.encode("utf-8")).hexdigest()


def canonical(record):
    body = {k: v for k, v in record.items() if k != "digest"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def digest(record):
    return hashlib.sha256(canonical(record)).hexdigest()


def fix(stock_id, crystals, source):
    """Make a negative record from a layout and the source that laid it."""
    law = params(stock_id)
    rec = {"format": FORMAT, "stock": stock_id, "law": law,
           "crystals": [int(c) for c in crystals], "source": source,
           "code": {"quantum_film": __version__}}
    problems = _layout_problems(rec, law)
    if problems:
        raise ValueError("the fixer refuses this layout: " + "; ".join(problems))
    rec["digest"] = digest(rec)
    return rec


def _layout_problems(rec, law):
    out = []
    cs = rec.get("crystals")
    if not isinstance(cs, list) or not all(isinstance(c, int) and not isinstance(c, bool) for c in cs):
        return ["crystals: not a list of integers"]
    if any(b <= a for a, b in pairwise(cs)):
        out.append("crystals: not strictly increasing (sorted, no site twice)")
    if cs and (cs[0] < 0 or cs[-1] >= law["M"]):
        out.append(f"crystals: a site outside 0..{law['M'] - 1}")
    if law["family"] in ("determinantal", "binomial") and len(cs) != law["N"]:
        out.append(f"count: {len(cs)} crystals where the {law['family']} law lays exactly {law['N']}")
    return out


def check(record):
    """The named reasons this record is refused; an empty list means fixed and intact."""
    out = []
    if not isinstance(record, dict):
        return ["not a record"]
    if record.get("format") != FORMAT:
        out.append(f"format: {record.get('format')!r} is not {FORMAT!r}")
    sid = record.get("stock")
    if sid not in STOCKS:
        return out + [f"stock: {sid!r} is not on the shelf"]
    try:
        law = params(sid)
    except LookupError as e:
        return out + [f"stock: {e}"]
    if record.get("law") != law:
        out.append("law: the record was laid under a law the shelf no longer states")
    out += _layout_problems(record, law)
    src = record.get("source")
    if not isinstance(src, dict) or src.get("kind") not in SOURCES:
        out.append(f"source: kind must be one of {SOURCES}")
    elif src["kind"] == "golden":
        parts = src.get("stream")
        if not isinstance(parts, list) or not all(isinstance(p, (str, int)) for p in parts):
            out.append("source: a golden roll must name its stream as a list of str and int parts")
    elif "fixed_at" not in src:
        out.append("source: a roll from a device must carry fixed_at")
    elif src["kind"] in DEVICE:
        out += _device_problems(src)
    elif not isinstance(src.get("backend"), str):
        out.append("source: a local-emu roll must name its backend")
    if record.get("digest") != digest(record):
        out.append("digest: the record's bytes are not the bytes it was fixed with")
    return out


def _device_problems(src):
    out = []
    for field, kind in DEVICE_FIELDS.items():
        v = src.get(field)
        if not isinstance(v, kind) or isinstance(v, bool):
            out.append(f"source: a {src['kind']} roll must carry {field} ({kind.__name__})")
    if out:
        return out
    for field in ("circuit_sha256", "salt", "commitment"):
        if len(src[field]) != 64 or not set(src[field]) <= _HEX64:
            out.append(f"source: {field} must be 64 lowercase hex digits")
    if src["shots"] < 1:
        out.append("source: shots must be positive")
    if not out and src["commitment"] != commitment(src["circuit_sha256"], src["engine"], src["job_id"], src["salt"]):
        out.append("source: the commitment does not bind this circuit, engine, job and salt")
    return out


def fix_device(stock_id, crystals, source):
    """Fix a roll laid by a device. `source` must carry DEVICE_FIELDS, the
    commitment included; the record is refused rather than fixed incomplete."""
    rec_source = dict(source)
    problems = _device_problems(rec_source) if rec_source.get("kind") in DEVICE else \
        [f"source: kind must be one of {DEVICE}"]
    if problems:
        raise ValueError("the fixer refuses this device roll: " + "; ".join(problems))
    return fix(stock_id, crystals, rec_source)


def lay(stock_id, seed):
    """A golden roll of `stock_id`, fixed. Stream: ("roll", stock_id, seed)."""
    from .golden import binomial, fermi
    from .golden.uniform import stream
    law = params(stock_id)
    parts = ["roll", stock_id, int(seed)]
    s = stream(*parts)
    if law["family"] == "determinantal":
        crystals = fermi.sample(law["L"], law["fermi_r2"], s)
        authority = {"module": "quantum_film.golden.fermi", "prec": fermi.PREC}
    elif law["family"] == "binomial":
        crystals = binomial.sample(law["M"], law["N"], s)
        authority = {"module": "quantum_film.golden.binomial"}
    else:
        raise LookupError(f"no golden sampler for the {law['family']} family")
    return fix(stock_id, crystals, {"kind": "golden", "stream": parts, "authority": authority})


def reproduce(record):
    """Re-lay a golden roll from its record and say whether it matches, bit for bit."""
    if record.get("source", {}).get("kind") != "golden":
        raise ValueError("only a golden roll can be reproduced; a device roll can only be read")
    parts = record["source"]["stream"]
    if parts[:2] != ["roll", record["stock"]] or len(parts) != 3:
        raise ValueError(f"stream {parts!r} is not a roll stream of {record['stock']!r}")
    again = lay(record["stock"], parts[2])
    return again["digest"] == record["digest"], again


def main(argv):
    if len(argv) >= 2 and argv[0] == "check":
        bad = 0
        for f in argv[1:]:
            try:
                rec = json.loads(open(f, encoding="utf-8").read())
                problems = check(rec)
            except (OSError, json.JSONDecodeError) as e:
                problems = [f"unreadable: {e}"]
            if problems:
                bad += 1
                print(f"REFUSED {f}")
                for p in problems:
                    print(f"   {p}")
            else:
                print(f"fixed   {f}  {rec['digest'][:16]}  {rec['stock']}, {len(rec['crystals'])} crystals")
        return 1 if bad else 0
    if len(argv) == 3 and argv[0] == "lay":
        print(json.dumps(lay(argv[1], int(argv[2])), sort_keys=True, indent=1))
        return 0
    print(__doc__.split("\n\n")[-1])
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

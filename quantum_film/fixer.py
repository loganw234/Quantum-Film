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
    if record.get("digest") != digest(record):
        out.append("digest: the record's bytes are not the bytes it was fixed with")
    return out


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

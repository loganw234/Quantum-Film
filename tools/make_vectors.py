#!/usr/bin/env python3
"""Write, and check, the frozen vectors in tests/vectors/.

Two kinds of vector, one list of each:

  GENERATED  golden rolls fixed by this package. --check regenerates each one
             and fails on any byte of difference. This is generate-then-check
             (HonestFramework METHOD §4): the generator is the only way to
             change these files.
  MEASURED   results from the Atlas platform. They cannot be regenerated,
             because the platform's shots are unseeded, so each is frozen once
             from its recorded source and afterwards held to SHA256SUMS.
             --write never overwrites a measured vector that differs from its
             source: that is refused.

TAMPERED is one golden record with a crystal moved and the digest left as it
was: the runner's permanent negative control (the fixer must refuse it).

    python tools/make_vectors.py --write    # after a deliberate change; commit the result
    python tools/make_vectors.py --check    # the gate: 0 = every vector is what it claims
"""
import argparse
import copy
import hashlib
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from quantum_film import fixer  # noqa: E402

VEC = ROOT / "tests" / "vectors"
GENERATED = [("negative-pauli-4x4-seed1.json", "pauli-4x4", 1),
             ("negative-pauli-seed1.json", "pauli", 1),
             ("negative-poisson-seed1.json", "poisson", 1)]
TAMPERED = "negative-tampered.json"
MEASURED = [("tomography-bitorder-2026-09-25.json",
             ROOT / "research" / "2026-09-25" / "atlas" / "bitorder_probe3.json")]


text = fixer.text      # one file form, the fixer's own: its command line refuses any other bytes


def tampered():
    rec = copy.deepcopy(fixer.lay("pauli-4x4", 1))
    free = sorted(set(range(rec["law"]["M"])) - set(rec["crystals"]))
    rec["crystals"] = sorted(rec["crystals"][1:] + [free[0]])    # one crystal moved; digest untouched
    return rec


def expected():
    out = {name: text(fixer.lay(stock, seed)) for name, stock, seed in GENERATED}
    out[TAMPERED] = text(tampered())
    return out


def sums_text():
    lines = [f"{hashlib.sha256((VEC / p.name).read_bytes()).hexdigest()}  {p.name}"
             for p in sorted(VEC.glob("*.json"))]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    a = ap.parse_args()
    VEC.mkdir(parents=True, exist_ok=True)
    want = expected()
    problems = []

    if a.write:
        for name, body in want.items():
            (VEC / name).write_text(body, encoding="utf-8", newline="\n")
        for name, src in MEASURED:
            dst = VEC / name
            if dst.exists() and dst.read_bytes() != src.read_bytes():
                problems.append(f"{name}: the frozen copy differs from {src}; a measured vector is never overwritten")
            elif not dst.exists():
                shutil.copyfile(src, dst)
        if problems:
            print("\n".join(problems), file=sys.stderr)
            return 1
        (VEC / "SHA256SUMS").write_text(sums_text(), encoding="utf-8", newline="\n")
        print(f"wrote {len(want)} generated vectors, kept {len(MEASURED)} measured, and SHA256SUMS")
        return 0

    for name, body in want.items():
        f = VEC / name
        if not f.exists():
            problems.append(f"{name}: missing (run --write)")
        elif f.read_text(encoding="utf-8") != body:
            problems.append(f"{name}: DRIFTED from what the package generates today")
    sums = VEC / "SHA256SUMS"
    if not sums.exists():
        problems.append("SHA256SUMS: missing")
    elif sums.read_text(encoding="utf-8") != sums_text():
        problems.append("SHA256SUMS: does not match the files (a vector changed, appeared or vanished)")
    for name, _stock, _seed in GENERATED:
        if (VEC / name).exists() and fixer.check_file(VEC / name)[1]:
            problems.append(f"{name}: the fixer refuses a generated record")
    if (VEC / TAMPERED).exists():
        refusal = fixer.check_file(VEC / TAMPERED)[1]
        if not any(p.startswith("digest:") for p in refusal):
            problems.append(f"{TAMPERED}: the fixer does not refuse the tampered record by its digest: {refusal}")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print(f"{len(want)} generated vectors regenerate byte for byte; SHA256SUMS holds "
          f"{len(sums.read_text(encoding='utf-8').splitlines())} files; the tampered record is refused")
    return 0


if __name__ == "__main__":
    sys.exit(main())

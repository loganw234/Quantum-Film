#!/usr/bin/env python3
"""The shelf's Pauli law on Atlas: pauli-4x4's hardware circuit through
tomography-api-v2, scored against the authority and fixed as device rolls.

    python tools/pauli_atlas_run.py --dry-run     everything but the network; writes nothing
    python tools/pauli_atlas_run.py               ONE Atlas job (needs QF_ATLAS_AUTH), end to end
    python tools/pauli_atlas_run.py --fetch JOB   finish a run whose commitment is committed
    python tools/pauli_atlas_run.py --score       audit and re-score every committed P3 run, offline;
                                                  exits 1 if any check fails (pauli_tile.audit)
    python tools/pauli_atlas_run.py --controls    run both negative controls and print what they say
    python tools/pauli_atlas_run.py --platform    record, beside each committed QASM without one, the
                                                  platform that writes its bytes (refused if this one does not)

A live run, in this order (quantum_film/atlas/pauli_tile.py says why):
  1. refuse a dirty tree, or main unless --on-main; build the circuit from the
     committed code and hold it to the authority's law on a local statevector;
  2. submit; form the commitment; write it, the exact QASM text and the
     platform that wrote that text under docs/records/<UTC date>/p3/, and
     git-commit them BEFORE the first status call (a completed job's status
     response carries the result). That order is this code's; the only
     timestamps on it are local, and nothing third-party dates the commit;
  3. poll; fetch the result once; read it through decode.layouts; score it
     against the authority's kernel, the circuit's SHA-256 beside the score;
  4. fix one device roll per distinct layout; check every file with the
     fixer's own command line; write the sanitised responses and the score;
     commit them.
A run is a device roll, not a reproduction: running it again makes another.
"""
if __name__ != "__main__":
    raise ImportError("this script calls Atlas when it runs; run it, never import it (CLAUDE.md)")

import argparse  # noqa: E402
import datetime  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import pathlib  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402

from quantum_film import fixer  # noqa: E402
from quantum_film.atlas import pauli_tile  # noqa: E402
from quantum_film.atlas.client import call  # noqa: E402
from quantum_film.circuits import givens_line  # noqa: E402

RECORDS = ROOT / "docs" / "records"
TERMINAL = ("completed", "failed", "cancelled", "error")


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def rel(p):
    return pathlib.Path(p).resolve().relative_to(ROOT).as_posix()


def git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"git {' '.join(args[:2])} failed: {p.stderr.strip()}")
    return p.stdout.strip()


def commit(paths, message, co_author):
    git("add", "--", *[rel(p) for p in paths])
    msg = message + (f"\n\nCo-Authored-By: {co_author}" if co_author else "")
    git("commit", "-q", "-m", msg, "--", *[rel(p) for p in paths])
    return git("rev-parse", "HEAD")


def show(obj):
    """A response body for a message, unless it looks like it carries a credential."""
    text = json.dumps(obj)[:600]
    return "(withheld: it matches a credential or e-mail pattern)" if pauli_tile.SECRET.search(text) else text


def fixer_cli(files):
    """The fixer's own command line over every file, in chunks under Windows'
    command-line limit. -> (fixed, refused, the REFUSED lines)."""
    fixed, refused, lines = 0, 0, []
    for k in range(0, len(files), 150):
        p = subprocess.run([sys.executable, "-m", "quantum_film.fixer", "check", *[rel(f) for f in files[k:k + 150]]],
                           cwd=ROOT, capture_output=True, text=True)
        out = p.stdout.splitlines()
        fixed += sum(ln.startswith("fixed") for ln in out)
        refused += sum(ln.startswith("REFUSED") for ln in out)
        lines += [ln for ln in out if not ln.startswith("fixed")]
        if (p.returncode != 0) != any(ln.startswith("REFUSED") for ln in out):
            raise SystemExit(f"the fixer's command line exited {p.returncode}: {p.stderr.strip()[:300]}")
    return fixed, refused, lines


def print_score(sc, label):
    sha = sc["circuit_sha256"][:16]
    print(f"{label}: circuit {sha}, {sc['shots']} layouts, {sc['distinct_layouts']} distinct; "
          f"crystals per layout {sc['crystals_per_layout']}")
    print(f"  circuit {sha}  one-site <n_q>, 16 sites:  max |z| {sc['one_site']['max_abs_z']:.2f}, "
          f"chi^2 {sc['one_site']['chi2']:.1f} over 16")
    print(f"  circuit {sha}  pair P(11), 120 pairs:     max |z| {sc['pairs']['max_abs_z']:.2f} "
          f"(pair {tuple(sc['pairs']['worst_pair'])}), chi^2 {sc['pairs']['chi2']:.1f} over 120")
    print(f"  circuit {sha}  chi^2/dof over all 136:    {sc['chi2_per_dof']:.3f}")
    f = sc["forbidden"]
    print(f"  circuit {sha}  forbidden layouts laid:    {f['shots']} of {sc['shots']} shots "
          f"({f['distinct_laid']} distinct of the law's {f['layouts_in_law']})")


def engine_summary(rows):
    worst = max(rows, key=lambda r: abs(r[3]))
    return {"n": len(rows), "max_abs_z": abs(worst[3]), "worst": worst[0],
            "coherence": [{"observable": n, "measured": m, "exact": e, "z": z} for n, m, e, z in rows
                          if n in ("<XX>_01", "<YY>_01")]}


def print_engine(rows, sha):
    s = engine_summary(rows)
    coh = "; ".join(f"{c['observable']} {c['measured']:+.4f} against {c['exact']:+.4f} (z {c['z']:+.2f})"
                    for c in s["coherence"])
    print(f"  circuit {sha[:16]}  the engine's own {s['n']} observables (no decode), against the circuit's state, "
          f"signs included: max |z| {s['max_abs_z']:.2f} ({s['worst']}); {coh}")


def committed_state(out, line):
    """The statevector of the committed QASM text: what the engine's observables are held to."""
    gate_list, M = givens_line.from_qasm((out / line["qasm_file"]).read_bytes().decode("ascii"))
    return givens_line.simulate(gate_list, M)


def platform_file(qfile):
    return qfile.with_name(qfile.name[:-len(".qasm")] + ".platform.json")


def platform_text(qasm, code_commit, note):
    """The record of the platform that writes this QASM text, or None if refused."""
    head = git("rev-parse", "HEAD") + ("+dirty" if git("status", "--porcelain", "--", "quantum_film") else "")
    try:
        rec = pauli_tile.platform_record(qasm, {"code_commit": code_commit}, head)
        rec.update(recorded_at=now(), note=note)
        return pauli_tile.safe_json(rec)
    except (AssertionError, OSError, PermissionError) as e:
        print(f"no platform record: {e}")
        return None


def preflight(on_main, strict=True):
    status = git("status", "--porcelain")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    if status and strict:
        raise SystemExit("REFUSED: the tree is dirty. A device roll's circuit must come from committed code, and "
                         "the commitment commit must carry nothing else. Commit or set the changes aside.")
    if branch in ("main", "master") and not on_main and strict:
        raise SystemExit(f"REFUSED: on {branch}. This commits records; run it on a branch, or pass --on-main.")
    return git("rev-parse", "HEAD"), branch, bool(status)


def build():
    gate_list, qasm, sha, st = pauli_tile.circuit()
    print(f"circuit {sha[:16]} (sha256 {sha}): {st['rotations']} rotations in {st['layers']} layers, "
          f"{st['cx']} cx, {st['gates']} gates, depth {st['depth']} (cx depth {st['cx_depth']}); "
          f"against the authority: kernel {st['kernel_error']:.1e}, whole law {st['law_error']:.1e}, "
          f"leaked {st['leaked']:.1e}")
    return gate_list, qasm, sha, st


def outgoing(qasm, sha, gate_list, shots):
    """The body sent, asserted to carry this module's circuit for the stock."""
    body = pauli_tile.request(qasm, pauli_tile.shape()[2], shots)
    sent = body["params"]["circuit_qasm"]
    if pauli_tile.sha256_text(sent) != sha or givens_line.from_qasm(sent)[0] != gate_list:
        raise SystemExit("REFUSED: the QASM about to be sent is not givens_line's circuit for pauli-4x4")
    if givens_line.from_qasm(givens_line.for_stock(pauli_tile.STOCK)[1])[0] != givens_line.from_qasm(sent)[0]:
        raise SystemExit("REFUSED: the circuit changed between building and sending")
    return body


def dry_run(args):
    code_commit, branch, dirty = preflight(args.on_main, strict=False)
    gate_list, qasm, sha, _st = build()
    body = outgoing(qasm, sha, gate_list, args.shots)
    p = body["params"]
    print(f"would submit to {pauli_tile.ENGINE}: {len(p['circuit_qasm'])} bytes of QASM, qubit_list "
          f"{p['qubit_list'][0]}..{p['qubit_list'][-1]}, shots {p['shots']}, pairs {p['qubit_pair_list']}")
    line = pauli_tile.commitment_line(job_id="<the job id>", circuit_sha256=sha, salt=os.urandom(32).hex(),
                                      shots=args.shots, qasm_file=f"circuit-{sha[:16]}.qasm",
                                      submitted_at="<at submission>", code_commit=code_commit)
    print(f"would commit, before any result: {json.dumps(line, sort_keys=True)}")
    made_on = platform_text(qasm, code_commit, "dry run")
    if made_on:
        rec = json.loads(made_on)
        print(f"and beside the QASM, the platform that writes it: Python {rec['python']['version'].split()[0]}, "
              f"numpy {rec['numpy']['version']}, libm {rec['libm'].get('library')} {rec['libm'].get('file_version')}")
    print(f"branch {branch}, HEAD {code_commit[:12]}{', DIRTY: a live run would refuse' if dirty else ''}")


def live(args):
    code_commit, branch, _ = preflight(args.on_main)
    gate_list, qasm, sha, _st = build()
    body = outgoing(qasm, sha, gate_list, args.shots)
    # Everything that could fail is done before the POST: after it, a job exists and must get its commitment.
    made_on = platform_text(qasm, code_commit, "recorded by the run itself, before submission")
    salt = os.urandom(32).hex()
    code, sub = call("POST", f"/api/v1/engines/{pauli_tile.ENGINE}/process", body)
    if code >= 300 or not isinstance(sub, dict) or not isinstance(sub.get("job_id"), str):
        raise SystemExit(f"submit refused: HTTP {code}: {show(sub)}")
    job = sub["job_id"]
    print(f"submitted: job {job} at {sub.get('submitted_at')}")
    out = RECORDS / datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d") / "p3"
    out.mkdir(parents=True, exist_ok=True)
    qfile = out / f"circuit-{sha[:16]}.qasm"
    if qfile.exists() and qfile.read_bytes() != qasm.encode("ascii"):
        raise SystemExit(f"REFUSED: {rel(qfile)} exists with other bytes")
    qfile.write_bytes(qasm.encode("ascii"))
    line = pauli_tile.commitment_line(job_id=job, circuit_sha256=sha, salt=salt, shots=args.shots,
                                      qasm_file=qfile.name, submitted_at=sub.get("submitted_at"),
                                      code_commit=code_commit)
    jsonl = out / "commitments.jsonl"
    with open(jsonl, "a", encoding="ascii", newline="\n") as f:
        f.write(json.dumps(line, sort_keys=True) + "\n")
    paths = [qfile, jsonl]
    if made_on and not platform_file(qfile).exists():
        platform_file(qfile).write_text(made_on, encoding="ascii", newline="\n")
        paths.append(platform_file(qfile))
    try:                    # the submit exchange goes with it, unless the scan refuses it
        text = pauli_tile.safe_json({"method": "POST", "path": f"/api/v1/engines/{pauli_tile.ENGINE}/process",
                                     "body": body, "status": code, "response": sub})
        (out / f"atlas-{job[:8]}-submit.json").write_text(text, encoding="ascii", newline="\n")
        paths.append(out / f"atlas-{job[:8]}-submit.json")
    except PermissionError as e:
        print(f"the submit exchange is not recorded: {e}")
    c = commit(paths, f"P3: the commitment for Atlas job {job[:8]} (pauli-4x4, circuit {sha[:16]}), before its "
               "result is fetched", args.co_author)
    print(f"commitment {line['commitment'][:16]} committed as {c[:12]} on {branch}, before any status or result call")
    finish(args, out, line)


def find_line(job):
    for jsonl in sorted(RECORDS.glob("*/p3/commitments.jsonl")):
        for raw in jsonl.read_text(encoding="ascii").splitlines():
            line = json.loads(raw)
            if line["job_id"] == job:
                return jsonl.parent, line
    raise SystemExit(f"no committed commitment for job {job}: a result is fetched only after its commitment")


def finish(args, out, line):
    job = line["job_id"]
    committed = git("log", "-1", "--format=%H", "--", rel(out / "commitments.jsonl"))
    if not committed or git("status", "--porcelain", "--", rel(out / "commitments.jsonl")):
        raise SystemExit("REFUSED: the commitment is not committed; the result is not fetched before it is")
    t0 = time.time()
    while True:
        _c, st = call("GET", f"/api/v1/jobs/{job}/status", save=False)
        state = (st or {}).get("status")
        if state in TERMINAL:
            break
        if time.time() - t0 > args.wait:
            raise SystemExit(f"job {job} still {state!r} after {args.wait} s; finish it later with --fetch {job}")
        time.sleep(2.0)
    print(f"job {job}: {state} after {time.time() - t0:.0f} s of polling")
    fetched_at = now()
    code, res = call("GET", f"/api/v1/jobs/{job}/result")
    result = res.get("result") if isinstance(res, dict) else None
    source_of_result = "/result"
    if not isinstance(result, dict) and isinstance((st or {}).get("result"), dict):
        result, source_of_result = st["result"], "/status (the /result call failed)"
    if not isinstance(result, dict):
        raise SystemExit(f"no result for job {job}: /result HTTP {code}: {show(res)}")
    status_record = {k: v for k, v in (st or {}).items() if k != "result"}
    status_record["result_in_status"] = ("absent" if "result" not in (st or {}) else
                                         "equal to /result" if (st or {}).get("result") == result else "different")
    counts = pauli_tile.layouts(result)
    K = pauli_tile.golden_kernel()
    forbidden, _ = pauli_tile.forbidden_layouts(K, pauli_tile.shape()[3])
    sc = pauli_tile.score(counts, K, forbidden, line["circuit_sha256"])
    engine = pauli_tile.engine_observables(result, committed_state(out, line))
    sc["engine_observables"] = engine_summary(engine)
    records, refused = pauli_tile.device_rolls(counts, line, now())
    rolls = out / f"rolls-{job[:8]}"
    rolls.mkdir(exist_ok=True)
    files = []
    for r in records:
        f = rolls / pauli_tile.record_name(r)
        f.write_bytes(fixer.text(r).encode("ascii"))
        files.append(f)
    fixed, bad, lines = fixer_cli(files)
    print(f"device rolls: {len(records)} fixed from {len(counts)} distinct layouts; the fixer's command line: "
          f"{fixed} fixed, {bad} refused")
    for ln in lines[:10]:
        print("   " + ln)
    for Y, n, why in refused[:10]:
        print(f"   NOT FIXED {Y} x{n}: {why}")
    written = [out / f"atlas-{job[:8]}-result.json", out / f"atlas-{job[:8]}-status.json",
               out / f"score-{job[:8]}.json"]
    texts = [pauli_tile.safe_json({"job_id": job, "path": f"/api/v1/jobs/{job}/result", "status": code,
                                   "fetched_at": fetched_at, "taken_from": source_of_result,
                                   "response": {"result": result}}),
             pauli_tile.safe_json(status_record),
             pauli_tile.safe_json(dict(sc, job_id=job, engine=line["engine"], commitment=line["commitment"],
                                       decode=line["decode"], records=len(records),
                                       fixer_cli={"fixed": fixed, "refused": bad},
                                       not_fixed=[{"crystals": Y, "occurrences": n, "reason": why}
                                                  for Y, n, why in refused]))]
    for f, text in zip(written, texts, strict=True):
        f.write_text(text, encoding="ascii", newline="\n")
    print_score(sc, f"Atlas job {job}")
    print_engine(engine, line["circuit_sha256"])
    c = commit([rolls, *written], f"P3: Atlas job {job[:8]}: the result, its score against the authority "
               f"(circuit {line['circuit_sha256'][:16]}) and {len(records)} device rolls", args.co_author)
    print(f"results committed as {c[:12]}")
    if bad or refused:
        raise SystemExit(1)


def rescore(_args):
    """Offline: every committed run audited (pauli_tile.audit: the circuit, the
    commitment, the records, the score, the engine's observables) and re-scored.
    Exits 1 if any check fails, or if there is no committed run to check."""
    K, forbidden, _dets = pauli_tile.law_of()
    runs, problems = 0, []
    for jsonl in sorted(RECORDS.glob("*/p3/commitments.jsonl")):
        out = jsonl.parent
        for raw in jsonl.read_text(encoding="ascii").splitlines():
            line = json.loads(raw)
            job = str(line.get("job_id"))
            run, found = pauli_tile.load_run(out, line)
            found += pauli_tile.audit(run)
            print(f"job {job}: {len(run['records'])} committed records under {rel(out)}; "
                  f"{len(found)} problem(s) in the audit")
            problems += [f"job {job[:8]}: {p}" for p in found]
            runs += 1
            try:
                result = run["result"]["response"]["result"]
                print_score(pauli_tile.score(pauli_tile.layouts(result), K, forbidden, line.get("circuit_sha256")),
                            f"re-scored job {job}")
                print_engine(pauli_tile.engine_observables(result, committed_state(out, line)),
                             line.get("circuit_sha256"))
            except (KeyError, TypeError, ValueError, OSError) as e:
                print(f"job {job}: not re-scored ({e.__class__.__name__}: {e})")
    if not runs:
        problems.append("no committed P3 run under docs/records/*/p3/")
    for p in problems[:40]:
        print(f"PROBLEM {p}")
    if len(problems) > 40:
        print(f"PROBLEM ... and {len(problems) - 40} more")
    print(f"{runs} committed run(s) audited: {'ALL CHECKS HOLD' if not problems else f'{len(problems)} PROBLEM(S)'}")
    if problems:
        raise SystemExit(1)


def platform(_args):
    """A platform record beside every committed QASM that has none. This one
    writes it only if this machine's module writes exactly that QASM's bytes."""
    written = 0
    for jsonl in sorted(RECORDS.glob("*/p3/commitments.jsonl")):
        for raw in jsonl.read_text(encoding="ascii").splitlines():
            line = json.loads(raw)
            qfile = jsonl.parent / line["qasm_file"]
            if platform_file(qfile).exists():
                continue
            text = platform_text(qfile.read_bytes().decode("ascii"), line["code_commit"],
                                 "recorded after the run by --platform: what ties it to the text is the check "
                                 "that this machine's module writes exactly these bytes")
            if text:
                platform_file(qfile).write_text(text, encoding="ascii", newline="\n")
                print(f"wrote {rel(platform_file(qfile))}")
                written += 1
    print(f"{written} platform record(s) written; commit them by hand")


def controls(_args):
    """1. every rotation of the circuit dropped in turn must fail the kernel check;
    2. a device roll with its job_id altered and re-sealed must be refused by the
    fixer's command line, naming the commitment."""
    gate_list, _qasm, sha, st = build()
    K = pauli_tile.golden_kernel()
    L, r2, M, N = pauli_tile.shape()
    e2 = np.outer(np.diag(K), np.diag(K)) - K ** 2
    np.fill_diagonal(e2, 0.0)
    errors = []
    for k in range(st["rotations"]):
        start = N + 6 * k
        n1, n2 = givens_line.occupations(givens_line.simulate(gate_list[:start] + gate_list[start + 6:], M))
        errors.append(max(float(np.max(np.abs(n1 - np.diag(K)))), float(np.max(np.abs(n2 - e2)))))
    failed = sum(e > 1e-6 for e in errors)
    print(f"control 1, circuit {sha[:16]}: each of the {len(errors)} rotations dropped in turn: {failed} of "
          f"{len(errors)} fail the kernel check (error > 1e-6); smallest error {min(errors):.4f} "
          f"(rotation {errors.index(min(errors))}), largest {max(errors):.4f}")
    files = sorted(RECORDS.glob("*/p3/rolls-*/*.json"))
    if files:
        rec, problems = fixer.check_file(files[0])
        origin = rel(files[0])
    else:
        line = pauli_tile.commitment_line(job_id="00000000-stand-in", circuit_sha256=sha, salt="0" * 64,
                                          qasm_file="-", submitted_at="-", code_commit="-")
        rec, problems = pauli_tile.device_rolls({(0, 1, 4, 11, 13): 1}, line, now())[0][0], []
        origin = "a stand-in roll (no committed record yet)"
    rec = json.loads(json.dumps(rec))
    rec["source"]["job_id"] = rec["source"]["job_id"][:-1] + ("0" if rec["source"]["job_id"][-1] != "0" else "1")
    rec["digest"] = fixer.digest(rec)
    with tempfile.TemporaryDirectory() as td:
        f = pathlib.Path(td) / "altered-job-id.json"
        f.write_bytes(fixer.text(rec).encode("ascii"))
        p = subprocess.run([sys.executable, "-m", "quantum_film.fixer", "check", str(f)], cwd=ROOT,
                           capture_output=True, text=True)
    print(f"control 2, from {origin} (intact before: {problems == []}): job_id altered to {rec['source']['job_id']}, "
          f"digest re-sealed; the fixer's command line exits {p.returncode}:")
    for ln in p.stdout.splitlines():
        print("   " + ln.replace(td, "<tmp>"))
    if failed != len(errors) or p.returncode != 1 or "commitment does not bind" not in p.stdout:
        raise SystemExit("A CONTROL DID NOT FAIL")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--fetch", metavar="JOB")
    mode.add_argument("--score", action="store_true")
    mode.add_argument("--controls", action="store_true")
    mode.add_argument("--platform", action="store_true")
    ap.add_argument("--shots", type=int, default=pauli_tile.SHOTS)
    ap.add_argument("--wait", type=int, default=900, help="seconds to poll before giving up (then --fetch)")
    ap.add_argument("--on-main", action="store_true", help="allow a live run to commit on main")
    ap.add_argument("--co-author", default="", help="a Co-Authored-By trailer for the commits this makes")
    args = ap.parse_args()
    if args.dry_run:
        dry_run(args)
    elif args.score:
        rescore(args)
    elif args.controls:
        controls(args)
    elif args.platform:
        platform(args)
    elif args.fetch:
        preflight(args.on_main)
        out, line = find_line(args.fetch)
        finish(args, out, line)
    else:
        live(args)


if __name__ == "__main__":
    main()

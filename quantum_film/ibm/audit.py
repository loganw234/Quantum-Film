"""Every committed hardware run, held offline from its files alone: the hardware twin of the checks
tests/circuits/test_p3_records.py makes of Atlas's runs. tests/hardware/pure/test_hardware_records.py runs
`audit` over docs/records.

A run is a job line, <job>-line.json, and the files quantum_film.ibm.runner wrote beside it. For each line:
  - the lines as a set (fixer.check_job_lines): no job id twice, no commitment in two lines;
  - its bundle: the directory under the root whose manifest.json hashes to the line's bundle_sha256, held by
    bundle.check (every file's hash, the logical circuits to their source ed767c01bd4b851d, the plan, the
    commitments, the SWAP-free checks and the ISA check, re-run);
  - the line is that bundle's job of its name: the job's commitments in PUB order, and the manifest's stock,
    kind, route, backend and program;
  - a job that did not complete has its status file, and no raw result and no record;
  - a completed job has its raw payload, read by quantum_film.ibm.raw, and one record per PUB, each intact as a
    file (fixer.check_file), held to the line (fixer.held_to_line), with the bundle's hashes, salt, options and
    decode, and with exactly the raw payload's counts for its own PUB, read through decode. A PUB that echoes
    a commitment echoes its own. This is the one check that sees counts put under the wrong PUB;
  - the law and coherence jobs run only after their bundle's known answer held: that job has a line
    submitted earlier, and its verdict, recomputed from its record, holds;
  - with `git_order`, an ibm-direct line was committed strictly before its raw result: the commit that added
    the line is an ancestor of the one that added the raw payload, and not the same commit.
"""
import pathlib

from .. import fixer
from . import anchor, bundle, decode, raw, runner


def _manifests(root):
    out = {}
    for p in sorted(pathlib.Path(root).rglob(bundle.MANIFEST)):
        try:
            out.setdefault(bundle.sha256(p.read_bytes()), p.parent)
        except OSError:
            continue
    return out


def _added_in(path):
    rc, out, _err = anchor.git(["log", "--diff-filter=A", "--format=%H", "--", path.name], path.parent)
    commits = out.split() if rc == 0 else []
    return commits[-1] if commits else None


def anchored_first(line_path, raw_path):
    """The named reasons the line was not committed strictly before the raw result; [] when it was."""
    a, b = _added_in(line_path), _added_in(raw_path)
    if a is None or b is None:
        return [f"{line_path.name}: the line or the raw result is not committed; the order of the anchor cannot "
                "be read"]
    if a == b:
        return [f"{line_path.name}: the line and the raw result were committed together: the line came no earlier"]
    if anchor.git(["merge-base", "--is-ancestor", a, b], line_path.parent)[0] != 0:
        return [f"{line_path.name}: the commit that added the line is not an ancestor of the one that added the raw "
                "result"]
    return []


def _verdict(m, out_dir):
    entry = bundle.job(m, "known-answer")["circuits"][0]
    rec, problems = fixer.check_file(runner.record_path(out_dir, "known-answer", entry))
    if problems:
        return None
    counts = {tuple(ones): n for ones, n in rec["counts"]}
    return decode.known_answer(counts, tuple(m["known_answer"]), bundle.M)


def audit_line(path, line, manifests, checked, repo, lines, git_order=False):
    where = path.name
    problems = fixer.check_job_line(line)
    if problems:
        return [f"{where}: {p}" for p in problems]
    if path.read_bytes() != fixer.text(line).encode("ascii"):
        return [f"{where}: its bytes are not the line's canonical text"]
    bdir = manifests.get(line["bundle_sha256"])
    if bdir is None:
        return [f"{where}: no bundle under the root has the manifest {line['bundle_sha256'][:16]}"]
    if bdir not in checked:
        checked[bdir] = bundle.check(bdir, repo)
    m, _digest, bp = checked[bdir]
    if bp:
        return [f"{where}: its bundle is refused: {p}" for p in bp]
    job_name = where[:-len(runner.LINE_SUFFIX)]
    try:
        entry = bundle.job(m, job_name)
    except KeyError:
        return [f"{where}: the bundle has no job {job_name!r}"]
    out = []
    if line["commitments"] != [e["commitment"] for e in entry["circuits"]]:
        out.append(f"{where}: its commitments are not job {job_name}'s, in PUB order")
    out += [f"{where}: its {k} is not the bundle's" for k in ("stock", "kind", "route", "backend", "program")
            if line[k] != m[k]]
    d = path.parent
    f = runner.files(d, job_name)
    records = [runner.record_path(d, job_name, e) for e in entry["circuits"]]
    stray = sorted(p.name for p in d.glob(f"{job_name}-pub*.json") if p not in records)
    if stray:
        out.append(f"{where}: files named as records of this job that are not its circuits': {stray}")
    if f["status"].exists():
        if f["raw"].exists() or any(p.exists() for p in records):
            out.append(f"{where}: the job did not complete (its status file), yet it has a raw result or a record")
        return out
    if not f["raw"].exists():
        return out + [f"{where}: no raw result and no status file"]
    try:
        pubs = raw.pubs(f["raw"].read_bytes().decode("utf-8"), bundle.M)
    except (raw.RawRefusal, UnicodeDecodeError) as e:
        return out + [f"{f['raw'].name}: {e}"]
    if len(pubs) != len(entry["circuits"]):
        return out + [f"{f['raw'].name}: {len(pubs)} PUBs where the job has {len(entry['circuits'])}"]
    for e, rp in zip(entry["circuits"], records, strict=True):
        if not rp.exists():
            out.append(f"{rp.name}: missing")
            continue
        rec, problems = fixer.check_file(rp)
        if problems:
            out += [f"{rp.name}: {p}" for p in problems]
            continue
        out += [f"{rp.name}: {p}" for p in fixer.held_to_line(rec, line)]
        src = rec["source"]
        want = {"circuit_sha256": e["circuit_sha256"], "isa_sha256": e["isa_sha256"], "shots": e["shots"],
                "salt": e["salt"], "decode": m["decode"], "options_sha256": m["options_sha256"]}
        out += [f"{rp.name}: its {k} is not the bundle's" for k, v in want.items() if src.get(k) != v]
        if (rec["role"], rec["basis"]) != (e["role"], e["basis"]):
            out.append(f"{rp.name}: its role and basis are not the bundle's {e['role']} {e['basis']}")
        strings, meta = pubs[e["pub"]]
        if rec["counts"] != runner.counts_of(strings):
            out.append(f"{rp.name}: its counts are not the raw payload's PUB {e['pub']} read through decode")
        echoed = (meta.get("circuit_metadata") or {}).get(runner.COMMITMENT_KEY) if isinstance(meta, dict) else None
        if echoed is not None and echoed != e["commitment"]:
            out.append(f"{rp.name}: the raw payload's PUB {e['pub']} echoes another circuit's commitment")
    if job_name != "known-answer":
        ka = [(p, ln) for p, ln in lines if ln.get("bundle_sha256") == line["bundle_sha256"]
              and p.name == runner.files(p.parent, "known-answer")["line"].name]
        if not ka:
            out.append(f"{where}: the bundle's known-answer job has no line; the {job_name} job runs only after "
                       "it holds")
        else:
            kp, kl = ka[0]
            verdict = _verdict(m, kp.parent)
            if verdict is None or not verdict["holds"]:
                out.append(f"{where}: the bundle's known answer did not hold, or has no intact record")
            if not (bundle.is_utc(kl.get("submitted_at"))
                    and bundle.utc_time(kl["submitted_at"]) < bundle.utc_time(line["submitted_at"])):
                out.append(f"{where}: the known-answer job was not submitted before this one")
    if git_order and line["route"] == "ibm-direct":
        out += anchored_first(path, f["raw"])
    return out


def audit(root, repo, git_order=False):
    """(problems, the number of job lines) over every run under `root`; [] problems means every run holds."""
    found = runner.lines_under(root)
    out = [f"{p.name}: not a readable job line" for p, ln in found if ln is None]
    lines = [(p, ln) for p, ln in found if ln is not None]
    out += [f"lines: {p}" for p in fixer.check_job_lines([ln for _p, ln in lines])]
    manifests, checked = _manifests(root), {}
    for path, line in lines:
        out += audit_line(path, line, manifests, checked, repo, lines, git_order)
    return out, len(lines)

"""Running one job of a frozen bundle (round 3): the order of operations, with every call to IBM injected.

tools/hw_run.py builds the calls (a live job, or a dry run's stand-in) and hands them to `run`, which does
the rest in this order (docs/ROUND3.md and the P1 brief):
   1. (the tool, before `run`: the bundle holds by bundle.check, and its QPY files are its gate lists) the
      bundle names this backend, and this kind, which the tool took from the backend object;
   2. once only: the job has no line, and none of its commitments is in any line already, here or under
      docs/records (fixer.check_job_lines stays clean);
   3. write <job>-submitting.json, exclusively, then submit ONE job: from the marker on, once-only refuses this
      job here, so a submission that raised (the job may exist at IBM with no line) is never repeated;
   4. read IBM's created time, in UTC (a status call);
   5. write the job line (fixer.JOB_FORMAT) and anchor it: for ibm-direct, git commit and push, before
      anything can fetch a result; for moth, the line is written to the output directory, for Moth to send
      back at once (the bundle's README says so; docs/ROUND3.md states the weaker anchor);
   6. wait for the job's final state (status calls). A job that did not complete keeps its line, gets a
      status file of IBM's own state and usage, and no record; a re-run needs a newly frozen bundle;
   7. fetch the RAW result and write its bytes at once, before anything decodes them;
   8. decode them with the library's decoder and, independently, with quantum_film.ibm.raw: the two must
      give the same strings, and a PUB that echoes a commitment must echo its own;
   9. read each PUB's bitstrings through quantum_film.ibm.decode, fix one device run per circuit
      (fixer.fix_run), hold each to the line (fixer.held_to_line), and write it;
  10. write the metrics, and check every record with the fixer's own command line;
  11. judge a known-answer job (decode.known_answer) against the manifest's expected set.
It never resubmits. Before step 3 a failure is `Refused` (nothing was sent); after it, `Stopped`, whose
message says what exists and what to do. The files of a job, in the output directory:
    <job>-submitting.json  <job>-line.json  <job>-raw.json  <job>-status.json  <job>-metrics.json
    <job>-verdict.json
    <job>-pub<k>-<name>.json   one device run per circuit, PUB k
(main's .gitattributes, since 9c44f37, stores every *-raw.json exactly, with no line ending converted.) `refix`
redoes steps 8 to 11 from the files alone, for a raw payload whose fixing failed.
"""
import json
import os
import pathlib

from .. import fixer
from . import bundle, decode, raw

COMMITMENT_KEY = "qf_commitment"        # the key in each circuit's metadata
RECORDS = "docs/records"


class Refused(Exception):
    """Refused before submission: nothing was sent."""


class Stopped(Exception):
    """Stopped after submission: the job exists. The message says what was written and what to do."""


def kind_from(is_ibm_backend, from_service, simulator):
    """The kind a run is recorded as, from the backend OBJECT, never from its name: qpu only for an IBM
    backend obtained from the service that is not a simulator. A fake backend, Aer, or an object that merely
    carries a device's name is a simulator. (The fixer's refusal of a simulator naming an IBM device is the
    second lock; this is the first, since only the runner holds the object.)"""
    return "qpu" if (is_ibm_backend is True and from_service is True and simulator is False) else "simulator"


LINE_SUFFIX = "-line.json"


def files(out_dir, job):
    out = pathlib.Path(out_dir)
    return {part: out / f"{job}-{part}.json" for part in ("line", "raw", "status", "metrics", "verdict", "submitting")}


def record_path(out_dir, job, entry):
    return pathlib.Path(out_dir) / f"{job}-pub{entry['pub']}-{entry['name']}.json"


def write_new(path, data):
    """Write bytes to a file that must not exist yet, and flush them to disk before returning."""
    with open(path, "xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def lines_under(*dirs):
    """[(path, line)] for every <job>-line.json under these directories (recursively); a line that does not
    load is (path, None)."""
    out, seen = [], set()
    for d in dirs:
        d = pathlib.Path(d)
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*" + LINE_SUFFIX)):
            key = p.resolve()
            if key in seen:
                continue
            seen.add(key)
            try:
                out.append((p, bundle.load_json(p.read_bytes())))
            except (OSError, UnicodeDecodeError, ValueError):
                out.append((p, None))
    return out


def once_only(manifest, job_name, out_dir, roots):
    """The named reasons this job may not be submitted: it has a line, or a commitment of it is in a line."""
    entry = bundle.job(manifest, job_name)
    mine = {e["commitment"] for e in entry["circuits"]}
    out = []
    if files(out_dir, job_name)["line"].exists():
        out.append(f"once only: {job_name} already has a line in the output directory; a job is submitted once, "
                   "and a re-run needs a newly frozen bundle")
    if files(out_dir, job_name)["submitting"].exists():
        out.append(f"once only: {files(out_dir, job_name)['submitting'].name} exists: a submission of {job_name} was "
                   "begun here, and IBM may hold the job; read the instance's job list before anything else, and a "
                   "re-run needs a newly frozen bundle")
    for path, line in lines_under(out_dir, *roots):
        if line is None:
            out.append(f"once only: {path.name} is not a readable job line")
        elif mine & set(line.get("commitments", [])):
            out.append(f"once only: {path.name} already holds a commitment of {job_name}: it was submitted")
    return out


def build_line(manifest, bundle_sha256, job_name, job_id, submitted_at):
    entry = bundle.job(manifest, job_name)
    line = {"format": fixer.JOB_FORMAT, "stock": manifest["stock"], "kind": manifest["kind"],
            "route": manifest["route"], "backend": manifest["backend"], "program": manifest["program"],
            "job_id": job_id, "submitted_at": submitted_at, "bundle_sha256": bundle_sha256,
            "commitments": [e["commitment"] for e in entry["circuits"]]}
    return line


def results_for(entries, decoded):
    """Each circuit with its own PUB's (strings, metadata): PUB k of the job is the payload's k-th result."""
    if len(decoded) != len(entries):
        raise Stopped(f"the result has {len(decoded)} PUBs where the job submitted {len(entries)}")
    return [(e, *decoded[e["pub"]]) for e in entries]


def echo_problems(pairs):
    """A PUB whose result echoes a commitment must echo its own circuit's. -> (problems, how many echoed)."""
    out, echoed = [], 0
    for e, _strings, meta in pairs:
        got = (meta.get("circuit_metadata") or {}).get(COMMITMENT_KEY) if isinstance(meta, dict) else None
        if got is None:
            continue
        echoed += 1
        if got != e["commitment"]:
            out.append(f"pub {e['pub']} ({e['name']}): its result carries the commitment {str(got)[:16]}, "
                       f"not its own {e['commitment'][:16]}: counts would land under the wrong PUB")
    return out, echoed


def source_of(manifest, entry, line, fixed_at):
    return {"kind": manifest["kind"], "route": manifest["route"], "backend": manifest["backend"],
            "program": manifest["program"], "job_id": line["job_id"], "pub": entry["pub"],
            "circuit_sha256": entry["circuit_sha256"], "isa_sha256": entry["isa_sha256"], "shots": entry["shots"],
            "options": manifest["options"], "options_sha256": manifest["options_sha256"],
            "decode": manifest["decode"], "salt": entry["salt"], "commitment": entry["commitment"],
            "submitted_at": line["submitted_at"], "fixed_at": fixed_at}


def counts_of(strings):
    """A PUB's bitstrings, read through decode, as a device run's counts."""
    return decode.canonical(decode.tally(strings, bundle.M))


def fix_job(manifest, job_name, line, raw_text, decode_library, now_utc, out_dir, log=print):
    """Steps 8 and 9: the raw payload decoded two ways, then one record per circuit, each held to the line.
    Every record is made and held before any is written, so a failure leaves none. -> [record paths]."""
    entries = bundle.job(manifest, job_name)["circuits"]
    paths = [record_path(out_dir, job_name, e) for e in entries]
    if any(p.exists() for p in paths):
        raise Stopped(f"{job_name}: records exist already ({[p.name for p in paths if p.exists()]}); "
                      "a record is written once")
    try:
        library = decode_library(raw_text)
        ours = raw.pubs(raw_text, bundle.M)
        if [s for s, _m in library] != [s for s, _m in ours]:
            raise Stopped("the library's decoder and quantum_film.ibm.raw read different bitstrings from the "
                          "raw payload")
        pairs = results_for(entries, library)
        problems, echoed = echo_problems(pairs)
        if problems:
            raise Stopped("; ".join(problems))
        if echoed < len(pairs):
            log(f"note: {len(pairs) - echoed} of {len(pairs)} PUBs echo no commitment; their order is the "
                "payload's")
        fixed_at = now_utc()
        records = []
        for e, strings, _meta in pairs:
            if len(strings) != e["shots"]:
                raise Stopped(f"pub {e['pub']} ({e['name']}): {len(strings)} shots where the bundle asked "
                              f"{e['shots']}")
            record = fixer.fix_run(manifest["stock"], e["role"], e["basis"], counts_of(strings),
                                   source_of(manifest, e, line, fixed_at))
            held = fixer.held_to_line(record, line)
            if held:
                raise Stopped(f"pub {e['pub']}: the record is not held to its line: {held}")
            records.append(record)
    except Exception as e:
        raise Stopped(f"{job_name}: nothing was fixed ({type(e).__name__}: {e}). The raw bytes are on disk "
                      f"({files(out_dir, job_name)['raw'].name}): fix them with --refix once the cause is "
                      "understood; never by resubmitting.") from e
    for path, record in zip(paths, records, strict=True):
        write_new(path, fixer.text(record).encode("ascii"))
    return paths


def known_answer_verdict(manifest, job_name, out_dir):
    """The known answer, judged from its written record against the manifest's expected set (never one given
    on a command line: known_answer is only as right as the set it is handed)."""
    entry = bundle.job(manifest, job_name)["circuits"][0]
    record = json.loads(record_path(out_dir, job_name, entry).read_text(encoding="ascii"))
    counts = {tuple(ones): n for ones, n in record["counts"]}
    return decode.known_answer(counts, tuple(manifest["known_answer"]), bundle.M)


def finish(manifest, job_name, line, out_dir, record_paths, check_cli, log=print):
    """Steps 10 and 11 after the records are written. -> 0 when everything holds."""
    rc, output = check_cli([str(p) for p in record_paths])
    log(output.rstrip())
    if rc != 0:
        raise Stopped("the fixer's command line refused a record it was handed (see above)")
    if bundle.job(manifest, job_name)["circuits"][0]["role"] != "known-answer":
        return 0
    verdict = known_answer_verdict(manifest, job_name, out_dir)
    write_new(files(out_dir, job_name)["verdict"], bundle.text(verdict).encode("ascii"))
    log(f"known answer {verdict['expected']}: modal {verdict['modal']}, share {verdict['share']:.4f}, mirror "
        f"{verdict['mirror_share']:.4f}, over {verdict['shots']} shots -> "
        + ("HOLDS: the device reads in decode's order" if verdict["holds"] else
           "DOES NOT HOLD: run nothing else until this is understood"))
    return 0 if verdict["holds"] else 3


def run(manifest, bundle_sha256, job_name, out_dir, roots, *, backend_name, kind, submit, job_id, created_utc,
        anchor, wait, fetch_raw, decode_library, status_of, metrics_of, check_cli, now_utc, log=print):
    """One job of a frozen bundle, start to finish (the module's eleven steps). -> exit code: 0 when every
    record is fixed and held (and a known answer holds), 3 when a known answer does not hold. Raises Refused
    before submission and Stopped after it."""
    out_dir = pathlib.Path(out_dir)
    if backend_name != manifest["backend"]:
        raise Refused(f"the backend is {backend_name!r}; the bundle was frozen for {manifest['backend']!r}")
    if kind != manifest["kind"]:
        raise Refused(f"the backend object is kind {kind!r}; the bundle's commitments bind {manifest['kind']!r}")
    once = once_only(manifest, job_name, out_dir, roots)
    if once:
        raise Refused("; ".join(once))
    f = files(out_dir, job_name)
    # 3: the marker first, written exclusively, so that whatever happens next once_only refuses this job here.
    try:
        write_new(f["submitting"], bundle.text({"begun_at": now_utc(), "bundle_sha256": bundle_sha256,
                                                "job": job_name}).encode("ascii"))
    except FileExistsError:
        raise Refused(f"once only: {f['submitting'].name} appeared after the check: another run of {job_name} began "
                      "here at the same time, and this one sends nothing") from None
    try:
        handle = submit()                                                # the job exists from here on
    except Exception as e:
        raise Stopped(f"the submission of {job_name} raised ({type(e).__name__}: {e}), and IBM may or may not hold "
                      f"the job: {f['submitting'].name} stays, so this job is refused here from now on. Read the "
                      "instance's job list before anything else; a re-run needs a newly frozen bundle.") from e
    jid = job_id(handle)
    log(f"submitted {job_name}: job {jid}")
    try:
        submitted_at = created_utc(handle)                               # 4: a status call
    except Exception as e:
        raise Stopped(f"job {jid} was submitted, and its created time could not be read ({type(e).__name__}: "
                      f"{e}); no line was written. Write it by hand from IBM's record before any result.") from e
    line = build_line(manifest, bundle_sha256, job_name, jid, submitted_at)
    bad = fixer.check_job_line(line)
    if bad:
        raise Stopped(f"job {jid}: its line is refused ({bad}); nothing was written")
    write_new(f["line"], fixer.text(line).encode("ascii"))              # 5: the line, then its anchor
    others = [ln for p, ln in lines_under(out_dir, *roots) if ln is not None]
    set_problems = fixer.check_job_lines(others)
    if set_problems:
        raise Stopped(f"job {jid}: with its line, the lines are refused as a set: {set_problems}")
    try:
        anchor(f["line"])
    except Exception as e:
        raise Stopped(f"job {jid}: the line is written ({f['line'].name}) and could not be anchored "
                      f"({type(e).__name__}: {e}). Commit and push it by hand, then run with --resume; "
                      "no result was read.") from e
    log(f"line anchored: {f['line'].name}")
    return after_anchor(manifest, job_name, out_dir, line, handle, wait=wait, fetch_raw=fetch_raw,
                        decode_library=decode_library, status_of=status_of, metrics_of=metrics_of,
                        check_cli=check_cli, now_utc=now_utc, log=log)


def after_anchor(manifest, job_name, out_dir, line, handle, *, wait, fetch_raw, decode_library, status_of,
                 metrics_of, check_cli, now_utc, log=print):
    """Steps 6 to 11, for a job whose line is anchored (`run`, or --resume). Anything that fails from here is
    `Stopped`, naming the job: its line is anchored, so the lead resumes it (--resume) or fixes its raw bytes
    (--refix), and never submits it again."""
    f = files(out_dir, job_name)
    jid = line["job_id"]
    resume = f"its line is anchored ({f['line'].name}): run again with --resume {jid}; nothing is resubmitted"
    try:
        state = wait(handle)                                             # 6: status calls only
    except Exception as e:
        raise Stopped(f"job {jid}: waiting for its final state failed ({type(e).__name__}: {e}); {resume}") from e
    if state != "DONE":
        try:
            status = status_of(handle)
        except Exception as e:
            raise Stopped(f"job {jid} ended {state}, and IBM's state and usage could not be read ({type(e).__name__}"
                          f": {e}); write {f['status'].name} from IBM's record. Its line stays and no run is "
                          "fixed; a re-run needs a newly frozen bundle.") from e
        write_new(f["status"], bundle.text(status).encode("ascii"))
        raise Stopped(f"job {jid} ended {state}: its line stays, {f['status'].name} holds IBM's state and usage, "
                      "and no run is fixed. A re-run needs a newly frozen bundle.")
    try:
        payload = fetch_raw(handle)                                      # 7: the raw bytes first
    except Exception as e:
        raise Stopped(f"job {jid}: its result could not be fetched ({type(e).__name__}: {e}); nothing was "
                      f"written; {resume}") from e
    if not isinstance(payload, str) or not payload:
        raise Stopped(f"job {jid}: the raw result is empty or not text; nothing was written; {resume}")
    write_new(f["raw"], payload.encode("utf-8"))
    log(f"raw result written: {f['raw'].name} ({len(payload)} characters)")
    try:
        metrics = metrics_of(handle, payload)
    except Exception as e:                                               # secondary: never in the way of the fix
        metrics = {"not_read": f"{type(e).__name__}: {e}"[:300]}
        log(f"note: the job's metrics could not be read ({metrics['not_read']}); fixing goes on")
    write_new(f["metrics"], bundle.text(metrics).encode("ascii"))
    paths = fix_job(manifest, job_name, line, payload, decode_library, now_utc, out_dir, log)   # 8, 9
    return finish(manifest, job_name, line, out_dir, paths, check_cli, log)                     # 10, 11


def refix(manifest, job_name, out_dir, *, decode_library, check_cli, now_utc, log=print):
    """Steps 8 to 11 from a job's written line and raw payload alone: no service, no submission."""
    f = files(out_dir, job_name)
    line = bundle.load_json(f["line"].read_bytes())
    payload = f["raw"].read_bytes().decode("utf-8")
    paths = fix_job(manifest, job_name, line, payload, decode_library, now_utc, out_dir, log)
    return finish(manifest, job_name, line, out_dir, paths, check_cli, log)

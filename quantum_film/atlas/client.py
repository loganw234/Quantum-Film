"""A small Atlas client that drives Windows' curl.exe.

Why curl, and why this one:
- api.mothquantum.com sits behind Cloudflare, which answers Python-urllib's
  default user agent with Error 1010, "browser_signature_banned"
  (2026-09-25). Moth's own API docs use curl in every code sample, so this
  client uses the documented client rather than disguising another.
- Git for Windows' bundled curl 8.8.0 failed here with error 43 on every
  request, so the client uses System32's.

THE KEY never lives in this repository. QF_ATLAS_AUTH names a file OUTSIDE
the tree holding one line, "Authorization: Bearer moth_...". curl reads the
file itself, so the key never appears on a command line. Two refusals guard
it:
- any host but HOST is refused, so a URL lifted from a response (a presigned
  upload, a redirect) can never carry the bearer token;
- a key file inside the tree is refused.

Every response is written under .atlas/responses/ (git-ignored). Results
come back with presigned storage URLs, which are bearer credentials for
their lifetime, so they are never printed and never go into docs/records/
unscrubbed.
"""
import datetime
import json
import os
import pathlib
import subprocess
import tempfile
import time
import urllib.parse

HOST = "https://api.mothquantum.com"
CURL = r"C:\Windows\System32\curl.exe"
REPO = pathlib.Path(__file__).resolve().parents[2]
OUT = REPO / ".atlas" / "responses"


def auth_header_file():
    p = os.environ.get("QF_ATLAS_AUTH")
    if not p:
        raise PermissionError("QF_ATLAS_AUTH is not set: name a header file outside the repository")
    p = pathlib.Path(p).resolve()
    if REPO == p or REPO in p.parents:
        raise PermissionError(f"{p} is inside the repository; the key is kept outside it")
    return p


def call(method, path, body=None, save=True):
    """-> (http status, parsed JSON or None). Never raises on HTTP errors."""
    url = urllib.parse.urljoin(HOST, path)
    # The scheme too: plain http to the right host would send the key in clear
    # (found writing tests/client/, 2026-09-25).
    if urllib.parse.urlsplit(url)[:2] != urllib.parse.urlsplit(HOST)[:2]:
        raise PermissionError(f"{url} is not {HOST}; the key goes nowhere else")
    with tempfile.TemporaryDirectory() as td:
        outp = pathlib.Path(td) / "body"
        cmd = [CURL, "-sS", "-X", method, "-o", str(outp), "-w", "%{http_code}",
               "-H", "@" + str(auth_header_file()), "-H", "Accept: application/json"]
        if body is not None:
            inp = pathlib.Path(td) / "req.json"
            inp.write_text(json.dumps(body), encoding="utf-8")
            cmd += ["-H", "Content-Type: application/json", "--data-binary", "@" + str(inp)]
        cmd.append(url)
        t0 = datetime.datetime.now(datetime.timezone.utc)
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise ConnectionError(f"curl rc={p.returncode}: {p.stderr.strip()}")
        raw = outp.read_bytes() if outp.exists() else b""
    status = int(p.stdout.strip())
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {"_non_json_bytes": len(raw)}
    if save:
        OUT.mkdir(parents=True, exist_ok=True)
        slug = path.strip("/").replace("/", "_").replace("?", "_").replace("&", "_")[:90]
        rec = {"at": t0.isoformat(), "method": method, "path": path, "body": body,
               "status": status, "response": payload}
        (OUT / f"{t0.strftime('%Y%m%dT%H%M%S%fZ')}_{method}_{slug}.json").write_text(
            json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    return status, payload


def run_job(engine, body, wait=900, poll=2.0):
    """Submit, poll to a terminal state, fetch the result once. The platform's own
    code sample says results are deleted after the fetch, so the saved response
    is the record."""
    code, sub = call("POST", f"/api/v1/engines/{engine}/process", body)
    if code >= 300:
        return {"engine": engine, "submit_status": code, "error": sub}
    jid = sub["job_id"]
    t0 = time.time()
    st = {}
    while time.time() - t0 < wait:
        _, st = call("GET", f"/api/v1/jobs/{jid}/status", save=False)
        if st and st.get("status") in ("completed", "failed", "cancelled", "error"):
            break
        time.sleep(poll)
    code, res = call("GET", f"/api/v1/jobs/{jid}/result")
    return {"engine": engine, "job_id": jid, "status": (st or {}).get("status"),
            "seconds": round(time.time() - t0, 1), "result_status": code, "result": res}

"""Tiny Atlas (moth-api) client for exploration, driving Windows curl.exe.

Why curl and not urllib: api.mothquantum.com sits behind Cloudflare, which
answers Python-urllib's default user agent with Error 1010 ("browser
signature banned", 2026-09-25). Moth's own API docs show curl in every code
sample, so this uses the documented client rather than disguising another
one. Git Bash's bundled curl fails locally with error 43, hence System32's.

The key never lives in this repository. FIXER_ATLAS_AUTH names a file OUTSIDE
the tree holding one line, "Authorization: Bearer moth_...", which curl reads
itself (never on a command line). It is sent to ONE host only: any other host
is refused, so a URL lifted from a response (a presigned upload, a redirect)
can never carry the bearer token. Every response is saved under responses/
(git-ignored) with a UTC stamp; docs/records/ holds the sanitised copies.

    set FIXER_ATLAS_AUTH=C:\\somewhere\\outside\\atlas-auth.hdr
    python moth.py GET /api/v1/me
    python moth.py POST /api/v1/engines/coin-toss-v1/process '{"params":{"shots":10}}'

This is the copy of the 2026-09-25 exploration client (it ran from the session
scratchpad with the header file beside it); only the key path changed.
"""
import datetime
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import urllib.parse

HERE = pathlib.Path(__file__).resolve().parent
HOST = "https://api.mothquantum.com"
CURL = r"C:\Windows\System32\curl.exe"
OUT = HERE / "responses"


def _auth_header_file():
    p = os.environ.get("FIXER_ATLAS_AUTH")
    if not p:
        raise SystemExit("REFUSED: set FIXER_ATLAS_AUTH to a header file outside the repository")
    p = pathlib.Path(p).resolve()
    repo = HERE.parents[2]
    if repo in p.parents:
        raise SystemExit(f"REFUSED: {p} is inside the repository; keep the key outside it")
    return p


def call(method, path, body=None, save=True, quiet=False):
    url = urllib.parse.urljoin(HOST, path)
    if urllib.parse.urlsplit(url).netloc != urllib.parse.urlsplit(HOST).netloc:
        raise SystemExit(f"REFUSED: {url} is not {HOST}; the key goes nowhere else")
    with tempfile.TemporaryDirectory() as td:
        outp = pathlib.Path(td) / "body"
        cmd = [CURL, "-sS", "-X", method, "-o", str(outp), "-w", "%{http_code} %{time_total}",
               "-H", "@" + str(_auth_header_file()), "-H", "Accept: application/json"]
        if body is not None:
            inp = pathlib.Path(td) / "req.json"
            inp.write_text(json.dumps(body), encoding="utf-8")
            cmd += ["-H", "Content-Type: application/json", "--data-binary", "@" + str(inp)]
        cmd.append(url)
        t0 = datetime.datetime.now(datetime.timezone.utc)
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise SystemExit(f"curl rc={p.returncode}: {p.stderr.strip()}")
        code, secs = p.stdout.split()
        raw = outp.read_bytes() if outp.exists() else b""
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {"_non_json_bytes": len(raw), "_head": raw[:200].decode("latin-1")}
    rec = {"at": t0.isoformat(), "seconds": float(secs), "method": method, "path": path,
           "body": body, "status": int(code), "response": payload}
    if save:
        OUT.mkdir(exist_ok=True)
        stamp = t0.strftime("%Y%m%dT%H%M%S%fZ")
        slug = path.strip("/").replace("/", "_").replace("?", "_").replace("&", "_")[:90]
        (OUT / f"{stamp}_{method}_{slug}.json").write_text(
            json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    if not quiet:
        print(f"{method} {path} -> {code} ({float(secs):.2f} s)")
        print(json.dumps(payload, indent=1, ensure_ascii=False)[:6000])
    return int(code), payload


if __name__ == "__main__":
    m, p = sys.argv[1], sys.argv[2]
    b = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
    call(m, p, b)

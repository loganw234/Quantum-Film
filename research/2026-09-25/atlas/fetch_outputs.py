"""Fetch two qdrive output files through fresh download URLs and compare bytes.
The presigned URL goes to storage WITHOUT the bearer token (it carries its own
signature) and is never printed."""

if __name__ != "__main__":
    raise ImportError("this script calls Atlas when it runs; run it, never import it (CLAUDE.md)")
import hashlib
import pathlib
import subprocess

from moth import CURL, call

HERE = pathlib.Path(__file__).resolve().parent
got = {}
for aid in ("cd17718d-c7d5-48c1-a667-cf1e61722b2d", "594c2cb4-cafb-4442-8f9d-abd0a45b0037"):
    code, meta = call("GET", f"/api/v1/assets/{aid}/download", quiet=True)
    if code != 200:
        print(aid, code, meta)
        continue
    dst = HERE / "responses" / f"qdrive-output-{aid[:8]}.txt"
    p = subprocess.run([CURL, "-sS", "-o", str(dst), "-w", "%{http_code}", meta["download_url"]],
                       capture_output=True, text=True)
    data = dst.read_bytes()
    got[aid] = data
    print(f"{aid[:8]}: http {p.stdout}, {len(data)} bytes, sha256 {hashlib.sha256(data).hexdigest()[:16]}")
if len(got) == 2:
    a, b = got.values()
    print("IDENTICAL" if a == b else "DIFFERENT")
    print("--- first file ---")
    print(a.decode("utf-8", "replace")[:1100])

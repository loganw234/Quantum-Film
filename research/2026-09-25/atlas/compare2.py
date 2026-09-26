"""Compare the qdrive and graph pairs on CONTENT, not on the whole body (which
carries fresh presigned URLs and job ids, so it can never match). Presigned
URLs are never printed: they are bearer credentials for 15 minutes."""

if __name__ != "__main__":
    raise ImportError("this script does its work when it runs; run it, never import it (CLAUDE.md)")
import hashlib
import json
import pathlib

R = pathlib.Path(__file__).resolve().parent / "responses"


def canon(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def strip(o):
    if isinstance(o, dict):
        return {k: ("<presigned url>" if k == "url" else strip(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o


def results_for(job_ids):
    out = {}
    for jid in job_ids:
        f = sorted(R.glob(f"*_GET_api_v1_jobs_{jid}_result.json"))[-1]
        out[jid] = json.loads(f.read_text(encoding="utf-8"))["response"]
    return out


qd = results_for(["4b13ab95-a6f8-4d06-aa86-f06196a5521b", "d7fd3028-a817-4937-b03b-8eb863c190e5"])
print("== qdrive, seed 7: top-level keys", {k: list(v.keys()) for k, v in qd.items()})
for jid, v in qd.items():
    res = v.get("result")
    print(f"  {jid[:8]} inline result: {json.dumps(strip(res))[:1200] if res is not None else None}")
    print(f"  {jid[:8]} outputs: {json.dumps(strip(v.get('outputs')))[:400]}")
a, b = list(qd.values())
print("  inline results identical:", canon(a.get("result")) == canon(b.get("result")))

gr = results_for(["3bdb394e-770a-48c8-bfa2-294c4cbdd8dc", "e38e59b6-8e10-4e82-88f8-7d1fa1e10d5d"])
outs = [v["result"]["output"] for v in gr.values()]
print("\n== graph, seed 7: output keys", list(outs[0].keys()))
for key in outs[0]:
    same = canon(outs[0][key]) == canon(outs[1][key])
    print(f"  {key:22} {'IDENTICAL' if same else 'differs'}")
print("  tomography sample:", json.dumps(outs[0].get("tomography"))[:600])

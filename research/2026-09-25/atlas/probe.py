"""Determinism probes against Atlas, emu only.

Each probe submits the SAME request twice and compares a canonical hash of
what came back. The question is narrow: does an identical request return
identical bytes? Results are deleted by the platform after the first fetch,
so moth.call's saved copy under responses/ is the only record.
"""
import hashlib
import json
import time

from moth import call


def canon(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")).hexdigest()


def run(engine, body, wait=240):
    code, sub = call("POST", f"/api/v1/engines/{engine}/process", body, quiet=True)
    if code >= 300:
        return {"engine": engine, "submit_status": code, "error": sub}
    jid = sub["job_id"]
    t0 = time.time()
    st = {}
    while time.time() - t0 < wait:
        code, st = call("GET", f"/api/v1/jobs/{jid}/status", quiet=True, save=False)
        if st and st.get("status") in ("completed", "failed", "cancelled", "error"):
            break
        time.sleep(2)
    call("GET", f"/api/v1/jobs/{jid}/status", quiet=True)            # keep the final status
    code, res = call("GET", f"/api/v1/jobs/{jid}/result", quiet=True)  # deleted after this fetch
    return {"engine": engine, "job_id": jid, "status": st.get("status"), "secs": round(time.time() - t0, 1),
            "result_status": code, "result": res, "status_record": st}


QASM = ('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\n'
        'h q[0];\ncx q[0],q[1];\nry(0.3) q[1];\n')
GRID = [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9, 10, 11], [12, 13, 14, 15]]

PROBES = [
    ("coin-toss build only", "coin-toss-v1", {"params": {"shots": 1000}, "stop_after": "build"}, 1),
    ("coin-toss emu, shots 1000", "coin-toss-v1", {"params": {"shots": 1000}}, 2),
    ("blur-core exact", "blur-core-v1", {"params": {"values": GRID, "strength": 0.3}}, 2),
    ("blur-core shots 64", "blur-core-v1", {"params": {"values": GRID, "strength": 0.3, "shots": 64}}, 2),
    ("tomography, own QASM", "tomography-api-v2",
     {"params": {"circuit_qasm": QASM, "qubit_list": [0, 1], "qubit_pair_list": [[0, 1]], "shots": 1000}}, 2),
]

if __name__ == "__main__":
    summary = []
    for label, engine, body, reps in PROBES:
        outs = []
        for i in range(reps):
            r = run(engine, body)
            res = r.get("result") or {}
            payload = res.get("result", res) if isinstance(res, dict) else res
            h = canon(payload)[:16] if r.get("result_status") == 200 else None
            outs.append((r.get("job_id"), r.get("status"), r.get("secs"), r.get("result_status"), h))
            print(f"[{label} #{i+1}] job={r.get('job_id')} status={r.get('status')} "
                  f"t={r.get('secs')}s result_http={r.get('result_status')} sha={h}")
            if r.get("error") or r.get("result_status") != 200:
                print("   detail:", json.dumps(r.get("error") or res, ensure_ascii=False)[:800])
            else:
                print("   result:", json.dumps(payload, ensure_ascii=False)[:900])
        hs = [o[4] for o in outs if o[4]]
        verdict = ("single run" if len(outs) == 1 else
                   "IDENTICAL" if len(hs) == len(outs) and len(set(hs)) == 1 else
                   "DIFFERENT" if len(hs) == len(outs) else "INCOMPLETE")
        summary.append((label, verdict, [o[4] for o in outs]))

    print("\n== summary")
    for label, verdict, hs in summary:
        print(f"  {label:32} {verdict:10} {hs}")

"""Second probe set, emu only. Question 1: does a SEED make a seeded engine's
output repeatable? Question 2: does any engine return full-register samples
(a crystal layout needs every site's bit in the same shot, not pair marginals)?"""

if __name__ != "__main__":
    raise ImportError("this script calls Atlas when it runs; run it, never import it (CLAUDE.md)")
import json

from probe import canon, run

PROBES = [
    ("qdrive, seed 7, sample", "qdrive-api-v1",
     {"params": {"n_qubits": 4, "targets": [{"qubits": [0, 1], "expvals": {"ZZ": 1.0}}],
                 "sample": True, "shots": 1000, "seed": 7}}),
    ("graph, seed 7, 6 qubits", "graph-v1", {"params": {"num_qubits": 6, "seed": 7, "shots": 1000}}),
]
for label, engine, body in PROBES:
    hs = []
    for i in range(2):
        r = run(engine, body)
        res = r.get("result") or {}
        payload = res.get("result", res) if isinstance(res, dict) else res
        ok = r.get("result_status") == 200
        h = canon(payload)[:16] if ok else None
        hs.append(h)
        print(f"[{label} #{i+1}] job={r.get('job_id')} status={r.get('status')} t={r.get('secs')}s "
              f"result_http={r.get('result_status')} sha={h}")
        body_txt = json.dumps(r.get("error") or res, ensure_ascii=False)
        print("   ", body_txt[:1500])
    print(f"== {label}: {'IDENTICAL' if hs[0] and hs[0] == hs[1] else 'DIFFERENT or incomplete'} {hs}\n")

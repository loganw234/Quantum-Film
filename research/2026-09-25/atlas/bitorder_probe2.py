"""Known-answer calibration WITH two-qubit gates: does routing permute raw counts?

The same distinct-marginal product state as bitorder_probe.py (qubit q reads 1
with probability (q + 0.5) / 16), followed by CZ on every JW-adjacent pair
(q, q+1), in two sweeps - the adjacency the fermion tile uses. CZ is diagonal,
so every Z-marginal is unchanged: the known answer survives the gates, but a
router must now place sixteen qubits on a line. Run twice.
"""

if __name__ != "__main__":
    raise ImportError("this script calls Atlas when it runs; run it, never import it (CLAUDE.md)")
import json
import math

from probe import run

M = 16
theta = [2 * math.asin(math.sqrt((q + 0.5) / M)) for q in range(M)]
lines = ['OPENQASM 2.0;', 'include "qelib1.inc";', f"qreg q[{M}];"]
lines += [f"ry({t!r}) q[{q}];" for q, t in enumerate(theta)]
for sweep in range(2):
    lines += [f"cz q[{q}],q[{q + 1}];" for q in range(sweep % 2, M - 1, 2)]
    lines += [f"cz q[{q}],q[{q + 1}];" for q in range((sweep + 1) % 2, M - 1, 2)]
qasm = "\n".join(lines) + "\n"
body = {"params": {"circuit_qasm": qasm, "qubit_list": list(range(M)), "qubit_pair_list": [[0, 1]],
                   "shots": 4096, "single_tomography": True, "double_tomography": True,
                   "mutual_information": False, "classical_mutual_information": False}}

orders = []
for rep in range(2):
    r = run("tomography-api-v2", body, wait=900)
    res = (r.get("result") or {}).get("result", {})
    meas = res.get("measurements", {})
    zk = [k for k in meas if set(k) <= {"Z", "I"}]
    counts = meas[zk[0]]["counts"]
    shots = sum(counts.values())
    means = [sum(c for s, c in counts.items() if s[p] == "1") / shots for p in range(M)]
    order = [min(range(M), key=lambda q: abs(means[p] - (q + 0.5) / M)) for p in range(M)]
    worst = max(abs(means[p] - (order[p] + 0.5) / M) for p in range(M))
    obs = [(1 - res["observables"][str(q)]["Z"]) / 2 for q in range(M)]
    obs_ok = all(abs(obs[q] - (q + 0.5) / M) < 0.03 for q in range(M))
    print(f"run {rep + 1}: job {r.get('job_id')} in {r.get('secs')} s")
    print(f"   string position p -> qubit: {order}")
    print(f"   Qiskit order would be:      {list(range(M - 1, -1, -1))}")
    print(f"   worst |mean - level| {worst:.4f}; a permutation: {sorted(order) == list(range(M))}; "
          f"engine's own <Z> fit the levels: {obs_ok}")
    orders.append(order)
print("SAME order in both runs" if orders[0] == orders[1] else "the order CHANGED between runs")
json.dump({"orders": orders, "qasm": qasm}, open("bitorder_probe2.json", "w"), indent=1)

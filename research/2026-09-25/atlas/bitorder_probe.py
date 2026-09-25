"""Known-answer calibration: in what order does tomography-api-v2 write raw counts?

Each qubit q gets ry(theta_q) with sin^2(theta_q / 2) = (q + 0.5) / 16, a product
state whose marginals are 1/16 apart - about 8 standard errors at 4096 shots -
so every string position names its qubit without any help from symmetry.
Run twice: a layout that is chosen stochastically would change between jobs.
"""
import json
import math

from probe import run

M = 16
theta = [2 * math.asin(math.sqrt((q + 0.5) / M)) for q in range(M)]
qasm = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n' + f"qreg q[{M}];\n" + \
    "".join(f"ry({t!r}) q[{q}];\n" for q, t in enumerate(theta))
body = {"params": {"circuit_qasm": qasm, "qubit_list": list(range(M)), "qubit_pair_list": [[0, 1]],
                   "shots": 4096, "single_tomography": True, "double_tomography": True,
                   "mutual_information": False, "classical_mutual_information": False}}

orders = []
for rep in range(2):
    r = run("tomography-api-v2", body, wait=900)
    res = (r.get("result") or {}).get("result", {})
    meas = res.get("measurements", {})
    zk = [k for k in meas if set(k) <= {"Z", "I"}]
    if not zk:
        print(f"run {rep + 1}: job {r.get('job_id')} {r.get('status')}: no all-Z setting; keys {list(meas)[:5]}")
        continue
    counts = meas[zk[0]]["counts"]
    shots = sum(counts.values())
    means = [sum(c for s, c in counts.items() if s[p] == "1") / shots for p in range(M)]
    order = [min(range(M), key=lambda q: abs(means[p] - (q + 0.5) / M)) for p in range(M)]
    worst = max(abs(means[p] - (order[p] + 0.5) / M) for p in range(M))
    obs_ok = all(abs((1 - res["observables"][str(q)]["Z"]) / 2 - (q + 0.5) / M) < 0.03 for q in range(M))
    print(f"run {rep + 1}: job {r.get('job_id')} in {r.get('secs')} s, setting {zk[0]}")
    print(f"   string position p -> qubit: {order}")
    print(f"   worst |mean - level| {worst:.4f} (levels are 0.0625 apart); "
          f"a permutation: {sorted(order) == list(range(M))}; "
          f"engine's own <Z> fit the levels: {obs_ok}")
    orders.append(order)
if len(orders) == 2:
    print("SAME order in both runs" if orders[0] == orders[1] else "the order CHANGED between runs")
json.dump({"theta": theta, "orders": orders}, open("bitorder_probe.json", "w"), indent=1)

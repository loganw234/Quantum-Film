"""Known-answer calibration with an UNSORTED, PARTIAL qubit_list.

Hypothesis from the fermion run: tomography-api-v2 writes count strings with
the qubit_list's qubits in the rightmost positions, then the other qubits,
while each setting's LABEL stays in circuit order (qubit 0 rightmost). With a
full, sorted list the two coincide, which would explain why the first two
calibrations decoded as plain Qiskit order. Here qubit_list = [9, 2, 14, 5]:
the answer distinguishes "list order" from "sorted order" from "circuit order".
"""

if __name__ != "__main__":
    raise ImportError("this script calls Atlas when it runs; run it, never import it (CLAUDE.md)")
import json
import math

from probe import run

M = 16
LIST = [9, 2, 14, 5]
theta = [2 * math.asin(math.sqrt((q + 0.5) / M)) for q in range(M)]
qasm = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n' + f"qreg q[{M}];\n" + \
    "".join(f"ry({t!r}) q[{q}];\n" for q, t in enumerate(theta))
body = {"params": {"circuit_qasm": qasm, "qubit_list": LIST, "qubit_pair_list": [[9, 2]],
                   "shots": 4096, "single_tomography": True, "double_tomography": True,
                   "mutual_information": False, "classical_mutual_information": False}}
r = run("tomography-api-v2", body, wait=900)
res = (r.get("result") or {}).get("result", {})
meas = res["measurements"]
print(f"job {r.get('job_id')} in {r.get('secs')} s; settings: {list(meas)}")
for key, v in meas.items():
    counts = v["counts"]
    shots = sum(counts.values())
    means = [sum(c for s, c in counts.items() if s[p] == "1") / shots for p in range(M)]
    # a position measured in Z shows its qubit's level; a rotated one shows ~0.5 or so
    order = [min(range(M), key=lambda q: abs(means[p] - (q + 0.5) / M)) for p in range(M)]
    print(f"  {key}: position p -> nearest level's qubit {order}")
    print(f"  {' ' * len(key)}  means {[round(m, 3) for m in means]}")
rest = [q for q in range(M) if q not in LIST]
print("predictions (position p = 0 is leftmost):")
print("  circuit order:      ", list(range(M - 1, -1, -1)))
print("  list order first:   ", list(reversed(LIST + rest)))
print("  sorted list first:  ", list(reversed(sorted(LIST) + rest)))
json.dump({"job": r.get("job_id"), "measurements": meas}, open("bitorder_probe3.json", "w"), indent=1)

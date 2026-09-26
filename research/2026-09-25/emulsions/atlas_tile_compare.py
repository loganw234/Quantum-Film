"""Score Atlas's run of the fermion tile against the exact determinantal law.

Reads fermion_tile_atlas.json (tomography-api-v2's result for fermion_tile.qasm)
and decodes each setting's count strings with the order rule in
../atlas/decode_rule.py (held to a known-answer run; see its docstring). From
the setting that measures every qubit in Z it takes WHOLE-REGISTER samples -
crystal layouts - and compares, each with a binomial standard error:
  - <n_q> for all 16 sites,
  - P(n_i = 1, n_j = 1) for all 120 site pairs,
  - the crystal count per layout (a 5-fermion state must give exactly 5).

History: the first version of this script read the strings in plain circuit
order and reported disagreements of up to 11 sigma. The engine's own derived
observables agreed with the exact law, which is what sent the reading, not
the engine's physics, back for checking.
"""

if __name__ != "__main__":
    raise ImportError("this script does its work when it runs; run it, never import it (CLAUDE.md)")
import json
import math
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "atlas"))
from decode_rule import order                      # noqa: E402
from fermion_tile import M, N, PAIRS, orbitals     # noqa: E402

d = json.loads((HERE / "fermion_tile_atlas.json").read_text(encoding="utf-8"))
meas = d["result"]["measurements"]
zlabel = [k for k in meas if set(k) <= {"Z", "I"}]
assert len(zlabel) == 1
zlabel = zlabel[0]
counts = meas[zlabel]["counts"]
shots = sum(counts.values())
pos2q = order(zlabel)
q2pos = {q: p for p, q in enumerate(pos2q)}
K = orbitals() @ orbitals().T


def occ(s, q):
    return s[q2pos[q]] == "1"


sizes = {}
for s, c in counts.items():
    sizes[s.count("1")] = sizes.get(s.count("1"), 0) + c
print(f"setting {zlabel}: {shots} whole-register samples; crystals per layout {dict(sorted(sizes.items()))} "
      f"(exact: always {N})")

z1 = []
for q in range(M):
    m = sum(c for s, c in counts.items() if occ(s, q)) / shots
    z1.append((m - K[q, q]) / math.sqrt(K[q, q] * (1 - K[q, q]) / shots))
print(f"one-site means, 16 sites: max |z| {max(map(abs, z1)):.2f}, chi^2 {sum(z * z for z in z1):.1f} over 16")

z2, rows = [], []
for i in range(M):
    for j in range(i + 1, M):
        ex = K[i, i] * K[j, j] - K[i, j] ** 2
        m = sum(c for s, c in counts.items() if occ(s, i) and occ(s, j)) / shots
        z = (m - ex) / math.sqrt(ex * (1 - ex) / shots)
        z2.append(z)
        rows.append((i, j, ex, m, z))
print(f"pair P(11), 120 pairs: max |z| {max(map(abs, z2)):.2f}, chi^2 {sum(z * z for z in z2):.1f} over 120")
print("named pairs:   exact P(11)  atlas     z      g exact  g atlas")
for i, j in PAIRS:
    _, _, ex, m, z = next(r for r in rows if r[0] == i and r[1] == j)
    mi = sum(c for s, c in counts.items() if occ(s, i)) / shots
    mj = sum(c for s, c in counts.items() if occ(s, j)) / shots
    print(f"  ({i:2},{j:2})      {ex:.4f}      {m:.4f}   {z:+.2f}   {ex / (K[i, i] * K[j, j]):.3f}    {m / (mi * mj):.3f}")
(HERE / "fermion_tile_scored.json").write_text(json.dumps(
    {"setting": zlabel, "shots": shots, "crystals_per_layout": sizes,
     "one_site_max_abs_z": max(map(abs, z1)), "one_site_chi2": sum(z * z for z in z1),
     "pairs_max_abs_z": max(map(abs, z2)), "pairs_chi2": sum(z * z for z in z2)}, indent=1), encoding="utf-8")

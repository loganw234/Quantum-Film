"""The count-string order tomography-api-v2 writes, as far as four runs show it.

RULE (inferred 2026-09-25, then held to known answers below): in each setting,
the count string is little-endian over a register ordered
    [the setting's non-I qubits, ascending] + [every other qubit, ascending]
while the setting's LABEL is written in circuit order, qubit 0 rightmost.

`order(label)` returns, for string position p (0 = leftmost), the circuit qubit.
Run as a script, it predicts every position's P(1) in bitorder_probe3's nine
settings from the known product state and reports the worst z-score.
"""
import json
import math
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def order(label):
    M = len(label)
    active = sorted(M - 1 - p for p, ch in enumerate(label) if ch != "I")
    rest = sorted(set(range(M)) - set(active))
    clbits = active + rest                       # clbit k -> circuit qubit
    return [clbits[M - 1 - p] for p in range(M)]


def basis_of(label, q):
    ch = label[len(label) - 1 - q]
    return "Z" if ch == "I" else ch


if __name__ == "__main__":
    d = json.loads((HERE / "bitorder_probe3.json").read_text(encoding="utf-8"))
    M = 16
    theta = [2 * math.asin(math.sqrt((q + 0.5) / M)) for q in range(M)]
    expect = {"Z": lambda q: (q + 0.5) / M,
              "X": lambda q: (1 - math.sin(theta[q])) / 2,     # ry(t)|0>: <X> = sin t
              "Y": lambda q: 0.5}                             # ry(t)|0>: <Y> = 0
    worst = (0.0, None)
    for label, v in d["measurements"].items():
        counts = v["counts"]
        shots = sum(counts.values())
        pos2q = order(label)
        for p in range(M):
            q = pos2q[p]
            e = expect[basis_of(label, q)](q)
            m = sum(c for s, c in counts.items() if s[p] == "1") / shots
            z = (m - e) / math.sqrt(max(e * (1 - e), 1e-9) / shots)
            if abs(z) > abs(worst[0]):
                worst = (z, (label, p, q, round(m, 4), round(e, 4)))
    print(f"rule held to 9 settings x 16 positions of the known-answer run; worst z {worst[0]:+.2f} at {worst[1]}")

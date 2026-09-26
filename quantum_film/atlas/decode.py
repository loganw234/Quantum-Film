"""The order in which tomography-api-v2 writes its counts, and crystal layouts read through it.

THE RULE was inferred on 2026-09-25 and then held to a known-answer run (the
frozen vector in tests/vectors/). In each measurement setting, the count
string is little-endian over a register ordered
    [the setting's non-I qubits, ascending] + [every other qubit, ascending]
while the setting's LABEL is written in circuit order, qubit 0 rightmost.
The order therefore changes from setting to setting within one response, and
nothing in the response says which order a string is in.

Every setting measures every qubit ("I" means measured without a basis
rotation, not unmeasured). So the setting with no X or Y anywhere gives
whole-register samples: for a crystal circuit, whole crystal layouts.

This is inferred from the engine's output; the engine's code is not public.
The rule is scoped to what the vectors show. A result it cannot account for
is refused, never guessed at.

DECODE names this rule in the records that were read with it (a device roll's
`decode` field, which its commitment binds). A change to the rule is a new
name, never an edit under the old one.
"""

DECODE = "quantum_film.atlas.decode/v1"


def order(label):
    """For each string position p (0 = leftmost), the circuit qubit it holds."""
    M = len(label)
    active = sorted(M - 1 - p for p, ch in enumerate(label) if ch != "I")
    rest = sorted(set(range(M)) - set(active))
    clbits = active + rest
    return [clbits[M - 1 - p] for p in range(M)]


def basis_of(label, q):
    """The basis circuit qubit q was measured in, in the setting `label`."""
    ch = label[len(label) - 1 - q]
    return "Z" if ch == "I" else ch


def z_setting(measurements):
    """The one setting that measured every qubit in Z. Refused if there is not exactly one."""
    zs = [k for k in measurements if set(k) <= {"Z", "I"}]
    if len(zs) != 1:
        raise ValueError(f"expected exactly one all-Z setting, found {zs}")
    return zs[0]


def layouts(result):
    """Whole-register crystal layouts from a tomography-api-v2 result:
    a dict mapping a sorted tuple of occupied qubits to its count."""
    meas = result["measurements"]
    label = z_setting(meas)
    pos2q = order(label)
    out = {}
    for s, c in meas[label]["counts"].items():
        if len(s) != len(label):
            raise ValueError(f"a count string of length {len(s)} under a {len(label)}-qubit label")
        occ = tuple(sorted(pos2q[p] for p, ch in enumerate(s) if ch == "1"))
        out[occ] = out.get(occ, 0) + c
    return out

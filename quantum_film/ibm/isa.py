"""This project's own check of a transpiled (ISA) circuit, independent of qiskit's simulators.

A device runs the TRANSPILED circuit, not the logical one, so the bundle holds
the transpiled circuit itself to what the logical circuit must give. qiskit's
transpiler wrote it; qiskit's simulators would share its conventions, so they
are not used here: this module simulates the gate list with numpy alone.

THE GATE LIST (`gate_list`): one document per transpiled circuit, read from a
qiskit QuantumCircuit by duck typing (this module imports no qiskit):
    {"format": FORMAT, "num_qubits": 156, "num_clbits": 16, "global_phase": f,
     "layout": {"initial": [p for logical 0..15], "final": [...],
                "routing_permutation": [...]},
     "gates": [[name, [physical qubits], [clbits], [params]], ...]}
in the circuit's own order. The bundle stores it as JSON beside the QPY file
the runner submits, and the runner checks the two are the same circuit.

THE SIMULATION (`distribution`) runs on the ACTIVE qubits only, those a gate or
a measurement touches, in a dense complex statevector. It reads exactly the
gates of the Heron r2 targets' ISA, GATES, and refuses any other by name:
    rz(t) = diag(exp(-i t/2), exp(i t/2))    sx = [[1+i, 1-i], [1-i, 1+i]] / 2
    x     = [[0, 1], [1, 0]]                  cz = diag(1, 1, 1, -1)
(qiskit's definitions; tests/hardware/pure/test_hw_isa.py holds each to its
matrix by the amplitudes, since Z-basis probabilities alone cannot tell sx
from its adjoint here, and the qiskit stage holds every frozen circuit's
distribution to qiskit's own Statevector).
A measurement maps a physical qubit to a classical bit; a gate on a qubit
after its measurement is refused. The result is the distribution over the
classical register, index n = sum of bit i * 2^i, so bit i is logical qubit i
under decode's contract (measure_all on the logical circuit, then compile).

THE HOLDS (`hold`): the transpiled circuit's distribution against the exact
one of its logical circuit (`exact_distribution`, from a statevector of
circuits.givens_line and Pauli algebra, a different code path), and against
what each role means:
    law            P(Y) = det(K_Y) on all 4,368 five-crystal layouts, 0 elsewhere;
    coherence      the pair's parity in its basis = <P_p P_q> (+0.375 here);
    known-answer   the one expected outcome.

THE TOLERANCE is 1e-10 on every probability, and on the parity. Measured
(P1, 2026-10-03) on the four circuits compiled at level 2 for the three fake
Heron r2 backends (Kingston, Fez, Marrakesh): the largest difference from the
exact values is 6.3e-17, the float64 rounding of some 600 gates on 2^16
amplitudes. Planted single-gate changes (sx made x, an rz angle moved by pi/2,
a cz dropped; every seventh such gate of the law and the YY circuit on
Kingston, 165 plants) moved some probability by 3.2e-4 or more whenever they
moved it at all. The smallest det(K_Y) of an allowed layout is 1/4096, 2.4e-4.
So 1e-10 is over a million times the rounding, and over a million times smaller
than the smallest change a plant made.

WHAT IT CANNOT SEE: a change that leaves every Z-basis probability alone: an
rz on a qubit still in a basis state (before its first sx), or after its last
two-qubit gate, right before its measurement. 7 of the 165 plants were such
phases. That is another circuit with the same experiment; the bundle's hashes
(the QPY file's and the gate list's) are what refuse it.
"""
import math
from itertools import pairwise

import numpy as np

FORMAT = "quantum-film/isa-gates/v1"
GATES = ("rz", "sx", "x", "cz", "measure", "barrier")
TOLERANCE = 1e-10
MAX_ACTIVE = 20          # 2^20 complex amplitudes, 16 MB: past this a dense statevector is the wrong tool
_ARITY = {"rz": (1, 0, 1), "sx": (1, 0, 0), "x": (1, 0, 0), "cz": (2, 0, 0), "measure": (1, 1, 0)}
_SX = np.array([[1 + 1j, 1 - 1j], [1 - 1j, 1 + 1j]]) / 2


class IsaRefusal(ValueError):
    """A gate list this check will not read, or a circuit that does not hold."""


def gate_list(circuit):
    """The gate-list document of a transpiled qiskit QuantumCircuit (duck-typed: no qiskit import)."""
    layout = circuit.layout
    if layout is None:
        raise IsaRefusal("the circuit has no layout: it was not transpiled for a device")
    gates = []
    for inst in circuit.data:
        op = inst.operation
        params = []
        for p in op.params:
            v = float(p)                               # an unbound parameter raises here, by design
            if not math.isfinite(v):
                raise IsaRefusal(f"{op.name}: a parameter that is not a finite number")
            params.append(v)
        gates.append([op.name, [circuit.find_bit(q).index for q in inst.qubits],
                      [circuit.find_bit(c).index for c in inst.clbits], params])
    return {"format": FORMAT, "num_qubits": int(circuit.num_qubits), "num_clbits": int(circuit.num_clbits),
            "global_phase": float(circuit.global_phase),
            "layout": {"initial": [int(q) for q in layout.initial_index_layout(filter_ancillas=True)],
                       "final": [int(q) for q in layout.final_index_layout(filter_ancillas=True)],
                       "routing_permutation": [int(q) for q in layout.routing_permutation()]},
            "gates": gates}


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _int_list(v):
    return isinstance(v, list) and all(_is_int(x) for x in v)


def read(doc):
    """The named reasons a gate-list document is not one this check reads; [] when it is."""
    if not isinstance(doc, dict):
        return ["gate list: not an object"]
    want = {"format", "num_qubits", "num_clbits", "global_phase", "layout", "gates"}
    if set(doc) != want:
        return [f"gate list: fields {sorted(doc)}; it carries exactly {sorted(want)}"]
    out = []
    if doc["format"] != FORMAT:
        out.append(f"gate list: format {doc['format']!r} is not {FORMAT!r}")
    n, m = doc["num_qubits"], doc["num_clbits"]
    if not (_is_int(n) and n >= 1 and _is_int(m) and m >= 1):
        return out + ["gate list: num_qubits and num_clbits are positive integers"]
    if not (isinstance(doc["global_phase"], float) and math.isfinite(doc["global_phase"])):
        out.append("gate list: global_phase is a finite float")
    lay = doc["layout"]
    if not (isinstance(lay, dict) and set(lay) == {"initial", "final", "routing_permutation"}
            and all(_int_list(lay[k]) for k in lay)):
        return out + ["gate list: layout is {initial, final, routing_permutation}, each a list of integers"]
    for k in ("initial", "final"):
        if len(lay[k]) != m or len(set(lay[k])) != m or not all(0 <= q < n for q in lay[k]):
            out.append(f"gate list: layout {k} names {m} distinct physical qubits")
    if not isinstance(doc["gates"], list):
        return out + ["gate list: gates is a list"]
    for i, g in enumerate(doc["gates"]):
        if not (isinstance(g, list) and len(g) == 4 and isinstance(g[0], str) and _int_list(g[1])
                and _int_list(g[2]) and isinstance(g[3], list)):
            out.append(f"gate {i}: not [name, [qubits], [clbits], [params]]")
            continue
        name, qs, cs, ps = g
        if name not in GATES:
            out.append(f"gate {i}: {name!r} is not in the ISA this check reads {GATES}")
            continue
        if not all(0 <= q < n for q in qs) or not all(0 <= c < m for c in cs):
            out.append(f"gate {i}: {name} on a qubit or clbit outside the circuit")
        if not all(isinstance(p, float) and math.isfinite(p) for p in ps):
            out.append(f"gate {i}: {name} has a parameter that is not a finite float")
        if name == "barrier":
            if cs or ps or len(set(qs)) != len(qs):
                out.append(f"gate {i}: a barrier has distinct qubits, no clbits and no parameters")
        elif (len(qs), len(cs), len(ps)) != _ARITY[name] or len(set(qs)) != len(qs):
            nq, nc, npar = _ARITY[name]
            out.append(f"gate {i}: {name} takes {nq} distinct qubit(s), {nc} clbit(s), {npar} parameter(s)")
    return out


def distribution(doc):
    """P(outcome) over the classical register, index n = sum of bit i * 2^i. Refuses (IsaRefusal) a gate
    list it does not read, a clbit not measured exactly once, and a gate on a qubit after its measurement."""
    psi, axis, clbit_of = _simulate(doc)
    n, m = psi.ndim, doc["num_clbits"]
    p = (psi.real ** 2 + psi.imag ** 2)
    keep = [axis[clbit_of[c]] for c in range(m)]
    drop = tuple(k for k in range(n) if k not in keep)
    if drop:
        p = p.sum(axis=drop)
        keep = [k - sum(1 for d in drop if d < k) for k in keep]
    # Axes in clbit order m-1 .. 0: C order then makes clbit 0 the low bit.
    return np.transpose(p, [keep[c] for c in reversed(range(m))]).reshape(-1)


def statevector(doc):
    """The final state on the active qubits, before any measurement: index sum of bit k * 2^k, k the active
    qubits in ascending physical order. For tests that hold each gate to its matrix: probabilities alone cannot
    tell sx from its adjoint (in circuits of rz, sx, x and cz from |0...0>, every Z-basis probability is the
    same either way, while the states differ; measured by P1, 2026-10-03)."""
    psi, _axis, _clbit_of = _simulate(doc)
    return np.transpose(psi, list(reversed(range(psi.ndim)))).reshape(-1)


def _simulate(doc):
    """-> (the final state as an n-axis tensor over the active qubits, {physical qubit: axis}, {clbit: qubit})."""
    problems = read(doc)
    if problems:
        raise IsaRefusal("; ".join(problems[:5]))
    gates = doc["gates"]
    active = sorted({q for name, qs, _c, _p in gates if name != "barrier" for q in qs})
    if len(active) > MAX_ACTIVE:
        raise IsaRefusal(f"{len(active)} active qubits; this check simulates at most {MAX_ACTIVE}")
    axis = {q: k for k, q in enumerate(active)}
    n = len(active)
    psi = np.zeros((2,) * n, dtype=complex)
    psi[(0,) * n] = 1.0
    measured = {}                                      # physical qubit -> clbit
    clbit_of = {}
    for i, (name, qs, cs, ps) in enumerate(gates):
        if name == "barrier":
            continue
        for q in qs:
            if q in measured:
                raise IsaRefusal(f"gate {i}: {name} on qubit {q} after its measurement")
        if name == "measure":
            if cs[0] in clbit_of:
                raise IsaRefusal(f"gate {i}: clbit {cs[0]} is measured twice")
            measured[qs[0]], clbit_of[cs[0]] = cs[0], qs[0]
            continue
        k = axis[qs[0]]
        if name == "rz":
            lo, hi = [slice(None)] * n, [slice(None)] * n
            lo[k], hi[k] = 0, 1
            psi[tuple(lo)] *= complex(math.cos(ps[0] / 2), -math.sin(ps[0] / 2))
            psi[tuple(hi)] *= complex(math.cos(ps[0] / 2), math.sin(ps[0] / 2))
        elif name == "sx":
            psi = np.moveaxis(np.tensordot(_SX, psi, axes=([1], [k])), 0, k)
        elif name == "x":
            psi = np.flip(psi, axis=k)
        else:                                           # cz
            both = [slice(None)] * n
            both[k], both[axis[qs[1]]] = 1, 1
            psi[tuple(both)] *= -1
    m = doc["num_clbits"]
    missing = [c for c in range(m) if c not in clbit_of]
    if missing:
        raise IsaRefusal(f"clbits {missing} are never measured")
    return psi, axis, clbit_of


def _pauli(phi, q, letter):
    """phi with the Pauli `letter` applied on axis q (qubit q; |1> at index 1)."""
    if letter == "X":
        return np.flip(phi, axis=q)
    z = phi * np.array([1.0, -1.0]).reshape([2 if k == q else 1 for k in range(phi.ndim)])
    return 1j * np.flip(z, axis=q)                    # Y = i X Z


def exact_distribution(psi, basis):
    """The exact distribution of a logical state measured qubit by qubit in `basis` (basis[q] for qubit q:
    X, Y or Z), index n = sum of bit q * 2^q. With S the qubits read in X or Y, each outcome's probability is
    2^-|S| sum over T within S of (-1)^(b_T) <psi| prod_T P_q  |b_rest><b_rest| |psi>: Pauli algebra on the
    logical statevector, with no basis-change gate simulated."""
    psi = np.asarray(psi, dtype=complex)
    M = psi.ndim
    if len(basis) != M or not set(basis) <= set("XYZ"):
        raise ValueError(f"a basis of X, Y or Z for each of {M} qubits")
    S = [q for q in range(M) if basis[q] != "Z"]
    out = np.zeros((2,) * M)
    for t in range(1 << len(S)):
        T = [S[j] for j in range(len(S)) if t >> j & 1]
        phi = psi
        for q in T:
            phi = _pauli(phi, q, basis[q])
        g = (np.conj(psi) * phi).sum(axis=tuple(S)) if S else np.conj(psi) * phi
        if np.max(np.abs(g.imag)) > 1e-12:
            raise ArithmeticError("a Hermitian reading with an imaginary part: the basis algebra is wrong")
        g = np.real(g)
        for b in range(1 << len(S)):
            sign = (-1) ** sum(1 for j in range(len(S)) if (b >> j & 1) and S[j] in T)
            idx = [slice(None)] * M
            for j, q in enumerate(S):
                idx[q] = b >> j & 1
            out[tuple(idx)] += sign * g / (1 << len(S))
    # out axes are qubits 0..M-1; index n = sum bit q 2^q wants qubit M-1 first in C order.
    return np.transpose(out, list(reversed(range(M)))).reshape(-1)


def parity(p, pair):
    """The expectation of (-1)^(b_p + b_q) under a distribution indexed by sum of bit q * 2^q."""
    n = np.arange(p.size)
    a, b = pair
    return float(np.dot(p, 1 - 2 * (((n >> a) ^ (n >> b)) & 1)))


def hold(p, exact, *, role, law=None, pair=None, pair_value=None, expected=None):
    """The named reasons a transpiled circuit's distribution `p` is refused against its logical circuit's
    exact one and its role's meaning; also returns the measured values. -> (problems, values)."""
    values = {"max_abs_error": float(np.max(np.abs(p - exact)))}
    out = []
    if values["max_abs_error"] > TOLERANCE:
        out.append(f"isa: the transpiled circuit's distribution differs from its logical circuit's by "
                   f"{values['max_abs_error']:.1e}, past {TOLERANCE:g}")
    if role == "law":
        dets = law
        index = {Y: sum(1 << q for q in Y) for Y in dets}
        worst = max(abs(float(p[index[Y]]) - d) for Y, d in dets.items())
        outside = float(p.sum() - sum(float(p[i]) for i in index.values()))
        values.update(law_error=worst, outside_law=outside)
        if worst > TOLERANCE or abs(outside) > TOLERANCE:
            out.append(f"isa: the law circuit does not lay det(K_Y): worst layout {worst:.1e}, "
                       f"{outside:.1e} outside the {len(dets)} layouts")
    elif role == "coherence":
        got = parity(p, pair)
        values.update(parity=got, exact_parity=pair_value)
        if abs(got - pair_value) > TOLERANCE:
            out.append(f"isa: the pair {list(pair)}'s parity is {got:+.6f} where the logical circuit gives "
                       f"{pair_value:+.6f}")
    elif role == "known-answer":
        index = sum(1 << q for q in expected)
        values.update(expected_probability=float(p[index]))
        if p[index] < 1 - TOLERANCE:
            out.append(f"isa: the known-answer circuit gives {sorted(expected)} with probability {p[index]:.6f}, "
                       "not 1")
    else:
        out.append(f"isa: no hold for role {role!r}")
    return out, values


def swap_free(doc, edges, cz):
    """The five SWAP-free checks of docs/HARDWARE.md, each refused by name; [] when the chain holds:
    the routing permutation is the identity; the initial layout equals the final one; every CZ joins
    neighbouring logical qubits; each consecutive pair of the chain is coupled; exactly `cz` CZ."""
    lay = doc["layout"]
    out = []
    perm = lay["routing_permutation"]
    if perm != list(range(len(perm))):
        out.append("swap-free: the routing permutation is not the identity")
    if lay["initial"] != lay["final"]:
        out.append("swap-free: the initial layout is not the final one")
    logical = {p: v for v, p in enumerate(lay["final"])}
    far = [i for i, (name, qs, _c, _p) in enumerate(doc["gates"]) if name == "cz"
           and not (qs[0] in logical and qs[1] in logical and abs(logical[qs[0]] - logical[qs[1]]) == 1)]
    if far:
        out.append(f"swap-free: {len(far)} CZ join qubits that are not neighbours on the logical line "
                   f"(first at gate {far[0]})")
    coupled = {tuple(sorted(e)) for e in edges}
    chain = lay["initial"]
    gaps = [(a, b) for a, b in pairwise(chain) if tuple(sorted((a, b))) not in coupled]
    if gaps:
        out.append(f"swap-free: the chain is not a path of the coupling map: {gaps[:3]} are not coupled")
    n_cz = sum(1 for g in doc["gates"] if g[0] == "cz")
    if n_cz != cz:
        out.append(f"swap-free: {n_cz} CZ where the logical circuit needs exactly {cz}")
    return out


def esp(doc, errors):
    """The estimated success probability: the product of (1 - error) over every gate and measurement, from
    `errors` {"name:q0,q1": error} (the target's, as frozen). A gate with no stated error counts as perfect."""
    log = 0.0
    for name, qs, _c, _p in doc["gates"]:
        if name == "barrier":
            continue
        e = errors.get(f"{name}:{','.join(map(str, qs))}")
        if e is not None:
            log += math.log1p(-e)
    return math.exp(log)

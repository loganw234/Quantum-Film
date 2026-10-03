"""The order in which an IBM Quantum sampler writes its bitstrings, and outcomes read through it.

THE CONTRACT with the runner: the logical circuit measures logical qubit i
into classical bit i of one register (QuantumCircuit.measure_all on the
logical circuit, before transpilation). Transpilation keeps that: the
transpiled circuit measures the physical qubit holding logical qubit i into
classical bit i, whatever chain it chose.

THE ORDER: a sampler bitstring, as BitArray.get_bitstrings() and get_counts()
give it, is written most significant bit first. Position p, counting from
the left, holds classical bit M - 1 - p.

Both were measured on 2026-10-01 (qiskit 2.5.2, qiskit-ibm-runtime 0.50.0,
the fake Heron r2 backends of the owner's three QPUs, through the legacy
SamplerV2 and the executor-based Sampler alike), with X on {0, 1, 3, 7, 12}:
the strings read 0001000010001011. Read in plain
order, the same string gives {3, 8, 12, 14, 15}, the mirror q -> M - 1 - q,
and on the 4x4 tile that mirror is a gauge of the law: no occupation
statistic can tell the two orders apart (CLAUDE.md). So the order is held to
a known-answer circuit, never to the physics: tests/decode/test_ibm_decode.py
here, and on hardware the first job of every route.

Only those strings are this reader's input. BitArray.array is big-endian
bytes, and the Executor's raw output is a boolean array whose column j is
bit j: either read as a string here would be the mirror.

DECODE names this rule in the records read with it (a device run's
`decode`, which its commitment binds). A change to the rule is a new name.
"""

DECODE = "quantum_film.ibm.decode/v1"


def ones(bits, M):
    """The logical qubits that read 1 in one bitstring of M bits, ascending."""
    if not isinstance(bits, str) or len(bits) != M or not set(bits) <= {"0", "1"}:
        raise ValueError(f"not a bitstring of {M} bits: {bits!r}")
    return tuple(i for i in range(M) if bits[M - 1 - i] == "1")


def tally(bitstrings, M):
    """{ones: shots} over a sampler's per-shot bitstrings."""
    out = {}
    for bits in bitstrings:
        key = ones(bits, M)
        out[key] = out.get(key, 0) + 1
    return out


def canonical(counts):
    """{ones: shots} as a device run's counts: [[ones, shots], ...], sorted by ones."""
    return [[list(key), n] for key, n in sorted(counts.items())]

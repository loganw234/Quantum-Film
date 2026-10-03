"""Transpiled circuits for tools/hw_predict.py's tests, built as round 3's research built them: run with the
lead's virtualenv ($QF_IBM_PYTHON), never imported by the project's Python.

    $QF_IBM_PYTHON tests/compare/venv/make_circuits.py OUTDIR BACKEND [--level 2] [--seed-transpiler 11]
                                                     [--scheduling alap] [--only law,xx,yy,known-answer,bad]

Writes OUTDIR/<role>.qpy, one circuit each, compiled for the fake BACKEND at an explicit level with a fixed seed:
  law            the committed circuit (docs/records/2026-09-25/p3/circuit-ed767c01bd4b851d.qasm), measure_all;
  xx, yy         the same, then H on qubits 0 and 1 (xx), or S-dagger then H on both (yy), then measure_all;
  known-answer   X on {0, 1, 3, 7, 12}, measure_all;
  bad            the known-answer circuit with a CZ planted between physical qubits 0 and 100, which no
                 Heron r2 couples: a circuit no backend's target supports.
Each circuit is measured with measure_all BEFORE compiling, the contract quantum_film.ibm.decode reads.
"""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
QASM = ROOT / "docs" / "records" / "2026-09-25" / "p3" / "circuit-ed767c01bd4b851d.qasm"
FAKES = {"fake_kingston": "FakeKingston", "fake_fez": "FakeFez", "fake_marrakesh": "FakeMarrakesh"}


def logical(role):
    from qiskit import QuantumCircuit, qasm2
    if role == "known-answer" or role == "bad":
        qc = QuantumCircuit(16)
        for q in (0, 1, 3, 7, 12):
            qc.x(q)
    else:
        qc = qasm2.loads(QASM.read_text(encoding="ascii"))
        if role == "xx":
            qc.h(0)
            qc.h(1)
        elif role == "yy":
            for q in (0, 1):
                qc.sdg(q)
                qc.h(q)
    qc.measure_all()
    return qc


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("backend", choices=sorted(FAKES))
    ap.add_argument("--level", type=int, default=2)
    ap.add_argument("--seed-transpiler", type=int, default=11)
    ap.add_argument("--scheduling", default=None)
    ap.add_argument("--only", default="law,xx,yy,known-answer,bad")
    args = ap.parse_args(argv)
    from qiskit import qpy
    from qiskit.transpiler import generate_preset_pass_manager
    from qiskit_ibm_runtime import fake_provider
    backend = getattr(fake_provider, FAKES[args.backend])()
    pm = generate_preset_pass_manager(optimization_level=args.level, backend=backend,
                                      seed_transpiler=args.seed_transpiler, scheduling_method=args.scheduling)
    out = pathlib.Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    for role in args.only.split(","):
        tqc = pm.run(logical(role))
        if role == "bad":
            tqc.cz(0, 100)
        with open(out / f"{role}.qpy", "wb") as f:
            qpy.dump(tqc, f)
        chain = tqc.layout.initial_index_layout(filter_ancillas=True)
        print(f"{role}: {dict(tqc.count_ops())} chain {chain}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

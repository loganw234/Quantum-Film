"""IBM Quantum hardware, as this project uses it (round 3, from 2026-10-03).

Nothing here imports qiskit: the modules are pure, so the import gate
(tests/docs/test_atlas_guards.py) passes them and every stage can read them.
The scripts that talk to IBM import qiskit inside `__main__` only.
"""

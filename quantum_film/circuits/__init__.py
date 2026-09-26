"""Circuits that lay crystal fields: what runs on an emulator or a QPU.

Written in float64 numpy, independently of quantum_film.golden. It shares only
the stock table's integer definitions with it, and is held to it by
tests/circuits/test_givens.py (givens.py, the reference) and
tests/circuits/test_givens_line.py (givens_line.py, the hardware-shaped
layout, 51 rotations and 102 CNOTs for pauli-4x4, which ran on Atlas).
"""

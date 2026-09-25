"""The definition of correct.

Slow, exact and independent: pure Python on the standard library, with
mpmath for the irrational constants. It imports nothing from this project but
the stock table (the definition itself), and nothing numerical from outside
the standard library and mpmath. tests/test_independence.py holds both rules
mechanically, because an authority that shares a helper with what it judges
tests nothing.

Every other way of laying a crystal field - numpy, libcft, a circuit on Atlas
or on hardware - is scored against this package, never against each other.
"""

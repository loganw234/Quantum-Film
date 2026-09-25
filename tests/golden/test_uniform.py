"""The counter-based uniforms: their byte encoding, checked independently of the code."""
import hashlib
from fractions import Fraction

import pytest

from quantum_film.golden.uniform import DOMAIN, stream, uniform


def test_the_encoding_is_the_documented_bytes():
    # Re-derived here from the docstring's specification, not from stream():
    # "s<len>:<utf8>" for a str, "i<decimal>" for an int, joined by "|".
    assert stream("roll", "pauli", 7) == b"s4:roll|s5:pauli|i7"
    raw = hashlib.sha256(b"quantum-film/uniform/v1|s4:roll|s5:pauli|i7|3").digest()
    assert DOMAIN == b"quantum-film/uniform/v1"
    assert uniform(stream("roll", "pauli", 7), 3) == Fraction(int.from_bytes(raw[:8], "big"), 1 << 64)


def test_streams_do_not_collide_across_part_boundaries():
    assert stream("roll", "pauli", 7) != stream("roll", "pauli7")
    assert stream("ab", "c") != stream("a", "bc")
    assert stream(1, 2) != stream(12)


def test_uniforms_are_exact_dyadics_in_the_unit_interval():
    s = stream("range-check")
    us = [uniform(s, i) for i in range(2000)]
    assert all(isinstance(u, Fraction) and 0 <= u < 1 for u in us)
    assert all((u * (1 << 64)).denominator == 1 for u in us)
    assert len(set(us)) == len(us)


@pytest.mark.parametrize("bad", [1.5, True, None, b"x"])
def test_a_part_that_is_not_str_or_int_is_refused(bad):
    with pytest.raises(TypeError):
        stream("roll", bad)


@pytest.mark.parametrize("bad", [-1, 1.0, True])
def test_a_draw_index_that_is_not_a_non_negative_int_is_refused(bad):
    with pytest.raises(ValueError):
        uniform(stream("x"), bad)

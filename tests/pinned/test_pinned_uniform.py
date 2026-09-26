"""The pinned path's uniforms: the authority's construction, with libcft computing the hash."""
import pytest

from quantum_film.golden import uniform as golden
from quantum_film.golden.uniform import stream
from quantum_film.pinned import uniform as pinned


def test_the_pinned_uniforms_are_the_authoritys():
    streams = [stream("roll", s, k) for s in ("pauli", "pauli-4x4") for k in range(1, 26)]
    streams += [b"", b"planted", "é|:i1".encode(), bytes(range(256))]
    for s in streams:
        for i in (0, 1, 7, 24, 10 ** 12):
            assert pinned.uniform(s, i) == golden.uniform(s, i)


def test_the_pinned_uniform_refuses_an_index_the_authority_refuses():
    for bad in (-1, True, 1.0):
        with pytest.raises(ValueError, match="non-negative int"):
            pinned.uniform(b"x", bad)
        with pytest.raises(ValueError, match="non-negative int"):
            golden.uniform(b"x", bad)


def test_a_changed_hash_input_changes_the_uniform():
    """The comparison above could pass if both sides ignored the stream; they do not."""
    assert pinned.uniform(b"a", 0) != pinned.uniform(b"b", 0) and pinned.uniform(b"a", 0) != pinned.uniform(b"a", 1)

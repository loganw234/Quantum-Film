"""The pinned path's uniforms: the authority's construction, with libcft computing the hash."""
import pytest

from quantum_film.golden import uniform as golden
from quantum_film.golden.uniform import stream
from quantum_film.pinned import sampler
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


@pytest.mark.parametrize("bad", [5, [1, 2, 3], "abc", None, 1.5])
def test_a_stream_the_authority_cannot_hash_is_refused_by_name_and_gets_no_roll(bad):
    """verifier-P1's D5: bytes(5) is five zero bytes, so a coercing hash laid a roll where the authority raised."""
    with pytest.raises(TypeError):
        golden.uniform(bad, 0)
    with pytest.raises(TypeError, match="a stream is bytes"):
        pinned.uniform(bad, 0)
    with pytest.raises(TypeError, match="a stream is bytes"):
        sampler.roll(4, 1, bad)


def test_a_bytes_like_stream_is_taken_as_the_authority_takes_it():
    for s in (bytearray(b"roll"), memoryview(b"roll")):
        assert pinned.uniform(s, 3) == golden.uniform(s, 3) == golden.uniform(b"roll", 3)


def test_a_changed_hash_input_changes_the_uniform():
    """The comparison above could pass if both sides ignored the stream; they do not."""
    assert pinned.uniform(b"a", 0) != pinned.uniform(b"b", 0) and pinned.uniform(b"a", 0) != pinned.uniform(b"a", 1)

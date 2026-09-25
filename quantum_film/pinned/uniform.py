"""The authority's uniforms, with the hash computed by libcft (cft_sha256).

    u(stream, i) = the first 8 bytes of SHA-256(DOMAIN | stream | i), read big-endian, / 2^64

The construction and the domain string are quantum_film.golden.uniform's, read
from there so there is one definition. Only the hash is computed elsewhere:
by libcft here, by Python's hashlib in the authority. tests/pinned holds the
two to the same bits.
"""
from fractions import Fraction

from ..golden.uniform import DOMAIN
from . import cft


def uniform(stream_bytes, i):
    """The i-th uniform of a stream, as an exact Fraction in [0, 1)."""
    if not isinstance(i, int) or isinstance(i, bool) or i < 0:
        raise ValueError(f"draw index must be a non-negative int, got {i!r}")
    h = cft.sha256(DOMAIN + b"|" + bytes(stream_bytes) + b"|" + b"%d" % i)
    return Fraction(int.from_bytes(h[:8], "big"), 1 << 64)

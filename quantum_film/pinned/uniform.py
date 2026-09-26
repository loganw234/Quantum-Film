"""The authority's uniforms, with the hash computed by libcft (cft_sha256).

    u(stream, i) = the first 8 bytes of SHA-256(DOMAIN | stream | i), read big-endian, / 2^64

The construction and the domain string are quantum_film.golden.uniform's, read
from there so there is one definition. Only the hash is computed elsewhere:
by libcft here, by Python's hashlib in the authority. tests/pinned holds the
two to the same bits, and to the same refusals: the message is built by the
authority's own expression, so a stream the authority cannot hash (an int, a
list, a str) is refused here too, by name, never coerced (bytes(5) is five
zero bytes; verifier-P1's D5, 2026-09-26).
"""
from fractions import Fraction

from ..golden.uniform import DOMAIN
from . import cft


def uniform(stream_bytes, i):
    """The i-th uniform of a stream, as an exact Fraction in [0, 1)."""
    if not isinstance(i, int) or isinstance(i, bool) or i < 0:
        raise ValueError(f"draw index must be a non-negative int, got {i!r}")
    try:
        message = DOMAIN + b"|" + stream_bytes + b"|" + b"%d" % i
    except TypeError:
        raise TypeError(f"a stream is bytes (quantum_film.golden.uniform.stream encodes one), not "
                        f"{type(stream_bytes).__name__}: the authority's uniforms refuse it too") from None
    h = cft.sha256(message)
    return Fraction(int.from_bytes(h[:8], "big"), 1 << 64)

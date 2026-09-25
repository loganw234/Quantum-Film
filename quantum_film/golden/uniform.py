"""Counter-based uniforms: the only randomness an emulated roll may use.

    u(stream, i) = the first 8 bytes of SHA-256(DOMAIN | stream | i),
                   read big-endian, divided by 2^64

u is an exact dyadic rational in [0, 1). SHA-256 is specified to the bit and
is available wherever this project will be reproduced (Python's hashlib, a
browser's WebCrypto, libcft's cft_sha256), so the uniforms are the same
everywhere by construction. A library PRNG is not: numpy promises stable bit
generators, not stable distributions (NEP 19), and atlas-film's own
determinism test is scoped "Deterministic per machine".

A stream names what it is for, with its parts tagged by type so that no two
different tuples encode to the same bytes: ("roll", "pauli", 7) and
("roll", "pauli7") are different streams.
"""
import hashlib
from fractions import Fraction

DOMAIN = b"quantum-film/uniform/v1"


def stream(*parts):
    """Encode a tuple of str and int parts, unambiguously, as bytes."""
    out = []
    for p in parts:
        if isinstance(p, bool) or not isinstance(p, (str, int)):
            raise TypeError(f"a stream part must be str or int, not {type(p).__name__}")
        if isinstance(p, str):
            b = p.encode("utf-8")
            out.append(b"s%d:%s" % (len(b), b))
        else:
            out.append(b"i%d" % p)
    return b"|".join(out)


def uniform(stream_bytes, i):
    """The i-th uniform of a stream, as an exact Fraction in [0, 1)."""
    if not isinstance(i, int) or isinstance(i, bool) or i < 0:
        raise ValueError(f"draw index must be a non-negative int, got {i!r}")
    h = hashlib.sha256(DOMAIN + b"|" + stream_bytes + b"|" + b"%d" % i).digest()
    return Fraction(int.from_bytes(h[:8], "big"), 1 << 64)

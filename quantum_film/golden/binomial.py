"""The Poisson reference, exactly: N of M sites, uniformly, without replacement.

Draw j picks the floor(u * (M - j))-th of the sites not yet taken, in
ascending order. That is exact integer arithmetic on the stream's exact
uniforms, with no rounding anywhere and so nothing to refuse.
"""
from math import floor

from .uniform import uniform


def sample(M, N, stream_bytes, uniform_fn=uniform):
    if not 0 <= N <= M:
        raise ValueError(f"cannot lay {N} crystals on {M} sites")
    free = list(range(M))
    picks = []
    for j in range(N):
        u = uniform_fn(stream_bytes, j)
        idx = floor(u * (M - j))
        picks.append(free.pop(idx))
    return sorted(picks)

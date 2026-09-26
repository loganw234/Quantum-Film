"""Does the arithmetic decide the grain? The fermion stock sampled with the SAME
uniforms under four arithmetics:

  A  complex128, V @ e  (BLAS zgemv)            - the reference
  B  complex128, einsum (numpy's own loop)       - a different summation order
  C  complex64,  V @ e                           - binary32
  D  complex128, V @ e, OPENBLAS_NUM_THREADS=1   - run in a child process

A layout is compared as its ORDERED pick sequence; the first differing step is
where the two films part. Exploration, not the project's authority.
"""

if __name__ != "__main__":
    raise ImportError("this script does its work when it runs; run it, never import it (CLAUDE.md)")
import json
import os
import subprocess
import sys

import numpy as np

from grain_proto import dpp_basis, digest, sample_projection_dpp

L, N, R = 32, 128, 40


def uniforms():
    ss = np.random.SeedSequence(20260925 + 1)
    return [np.random.default_rng(s).random(N) for s in ss.spawn(R)]


def run(dtype, update):
    V = dpp_basis(L, N, dtype=dtype)
    return [sample_projection_dpp(V, u, update=update) for u in uniforms()]


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--child":
    print(json.dumps([list(map(int, p)) for p in run(np.complex128, "matmul")]))
    sys.exit(0)

A = run(np.complex128, "matmul")
variants = {"B einsum (complex128)": run(np.complex128, "einsum"),
            "C binary32 (complex64)": run(np.complex64, "matmul")}
env = dict(os.environ, OPENBLAS_NUM_THREADS="1")
out = subprocess.run([sys.executable, __file__, "--child"], env=env, capture_output=True, text=True)
variants["D one BLAS thread"] = [np.array(p) for p in json.loads(out.stdout)]

print(f"fermion stock, {L}x{L} sites, {N} crystals, {R} layouts; reference A digests "
      f"{[digest(p) for p in A[:3]]}...")
for name, got in variants.items():
    same = sum(np.array_equal(a, b) for a, b in zip(A, got))
    firsts, overlaps = [], []
    for a, b in zip(A, got):
        if not np.array_equal(a, b):
            firsts.append(int(np.argmax(a != b)))
            overlaps.append(len(set(a) & set(b)) / N)
    line = f"  {name:24} identical {same}/{R}"
    if firsts:
        line += (f"; parted at step {sorted(firsts)} of {N};"
                 f" crystals shared after parting: {min(overlaps):.2f}-{max(overlaps):.2f}")
    print(line)

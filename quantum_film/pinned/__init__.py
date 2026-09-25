"""The pinned path: the Pauli law on cft-fp256's libcft, in binary64, equal to the authority by construction.

    quantum_film.pinned.cft          the ctypes shim over libcft (QF_CFT_ROOT, default vendor/cft-fp256)
    quantum_film.pinned.encode       exact rational <-> binary32/64/128 encodings, by integer arithmetic
    quantum_film.pinned.bounds       directed-rounding bounds: the only arithmetic the certificate does
    quantum_film.pinned.uniform      the authority's uniforms, hashed by libcft's SHA-256
    quantum_film.pinned.basis        the authority's basis columns, and their values rounded to nearest
    quantum_film.pinned.certificate  enclosures of the exact chain rule, step by step
    quantum_film.pinned.sampler      the chain rule, certified draw by draw or handed whole to the authority
    quantum_film.pinned.control      planted near-ties: the negative control and a ladder of distances
    quantum_film.pinned.measure      the hand-off rate, the precision table, the timings (python -m ...)

Every operation here that rounds is a libcft call; numpy only moves bits,
selects and compares. Nothing is claimed for a draw the certificate cannot
clear: that roll is the authority's own (quantum_film.golden.fermi).
"""

# Third-party notices

Quantum-Film is MIT (LICENSE). What it depends on keeps its own licence.

| component | how it is used | licence |
|---|---|---|
| [cft-fp256](https://github.com/loganw234/cft-fp256) | a git submodule at `vendor/cft-fp256`, pinned to `7d7285d`, built locally for the pinned-arithmetic path | Apache-2.0 |
| [atlas-film](https://github.com/loganw234/atlas-film) | an optional dependency (`pip install .[film]`), pinned to `be1d674`, for development's sourced organs | MIT |
| [numpy](https://numpy.org) | the float64 fast path and the circuits' simulator | BSD-3-Clause |
| [mpmath](https://mpmath.org) | the golden model's irrational constants, at 256 bits | BSD-3-Clause |

## cft-fp256 NOTICE

Reproduced as Apache-2.0 §4(d) asks, for any distribution that includes the
submodule's source or a library built from it:

```
cft-fp256 - Coordinated Fusion Compute Tile
Copyright 2026 Logan W.

This product includes software developed as part of the cft-fp256
project (https://github.com/loganw234/cft-fp256).
```

The full Apache-2.0 text is `vendor/cft-fp256/LICENSE`.

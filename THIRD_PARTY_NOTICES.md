# Third-party notices

Quantum-Film is MIT (LICENSE). What it depends on keeps its own licence.

| component | how it is used | licence |
|---|---|---|
| [cft-fp256](https://github.com/loganw234/cft-fp256) | a git submodule at `vendor/cft-fp256`, pinned to `7d7285d`, built locally for the pinned-arithmetic path | Apache-2.0 |
| [atlas-film](https://github.com/loganw234/atlas-film) | a git submodule at `vendor/atlas-film`, pinned to `d4007b2` (its pinned branch), for development's sourced organs | MIT |
| [numpy](https://numpy.org) | the float64 fast path and the circuits' simulator | BSD-3-Clause |
| [mpmath](https://mpmath.org) | the golden model's irrational constants, at 256 bits | BSD-3-Clause |
| [Pillow](https://python-pillow.org) | the image tools only (`pip install .[media]`): the prints' images, the gallery, the poster | HPND |
| [matplotlib](https://matplotlib.org) | the image tools only (`pip install .[media]`): the structure-factor figure | Matplotlib License (PSF-based) |
| [three.js](https://threejs.org) | the web demo in site/, loaded at r170 from jsDelivr, not vendored | MIT |

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

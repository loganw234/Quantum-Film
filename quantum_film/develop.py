"""Development: rolls become a sheet of film, and the sheet a negative and a print.

A stock's law places crystals on the sites of an L x L tile (quantum_film.stocks). atlas-film, the medium,
develops a SHEET: per pixel-cell, K crystals, each with a 16-bit sensitivity threshold. A crystal develops
iff its threshold is at or below the exposure's developable fraction, a comparison, not a draw
(atlas_film.emulsion). This module lays the sheet from rolls and hands it to atlas-film's PINNED mode, whose
negative and print are the same bits on every IEEE 754 binary64 machine (atlas-film's docs/PINNED.md). The
sheet itself is integers, laid by integer arithmetic and SHA-256, so it is the same everywhere too.

THE MAPPING, declared; every choice in it is an operator's, not sourced:
- A cell is one site. The emulsion's depth holds LAYERS: each is one roll of every tile, independent of the
  other layers. A cell's K is its column's crystal count, over the layers.
- Each layer's tile grid is shifted by an offset drawn from the print's stream, so the tiles' seams do not
  line up through the depth. The sheet wraps at its edges (a torus), so a shifted layer loses no crystal.
- The pitch is DERIVED from the layer count. Every roll holds exactly N crystals, so the sheet's mean K over
  whole tiles is layers * N / L^2 whatever the layouts, and the pitch is the one at which the borrowed
  stock's own coating density, lambda_K = dmax * pitch^2 / (KAPPA * grain_um2), equals it. atlas-film's
  `sheet=` path does not check the mean of K; here it holds by construction (to binary64 rounding in the
  pitch, which is a correctly rounded square root).
- The pitch must clear the borrowed stock's honesty floor (a cell at least one crystal across) and stay in
  pinned mode's exact regime (lambda_K + 8 sqrt(lambda_K) + 16 <= 192). A layer count outside them is refused
  by name.
- Each crystal's threshold is the top 16 bits of the golden uniform over the print's stream, the layer and
  the tile, at the crystal's index: a uniform in law, the same bits everywhere.
- Device rolls come as distinct layouts with occurrence counts. Their shots are laid in a canonical order
  (by job, then layout) and shuffled by a Fisher-Yates walk on the print's stream, so no job and no layout
  clusters on the sheet.

What a print does NOT carry from the borrowed stock: its MTF and halation (pinned mode refuses both, so the
negative is pixel-sharp) and colour.

atlas-film is imported from the pinned submodule vendor/atlas-film, and from nowhere else: an editable install
of another checkout would otherwise answer the import (CLAUDE.md).
"""
import hashlib
import math
import pathlib
import sys
from fractions import Fraction

import numpy as np

from .golden.uniform import stream, uniform
from .stocks import params

ROOT = pathlib.Path(__file__).resolve().parent.parent
ATLAS_ROOT = ROOT / "vendor" / "atlas-film"
PRINT_FORMAT = "quantum-film/print/v1"
EXACT_KMAX = 192            # atlas_film.emulsion's own bound on the exact regime, held here by value


class AtlasFilmMissing(RuntimeError):
    """The pinned submodule is not checked out."""


class AtlasFilmShadowed(RuntimeError):
    """atlas_film was imported from somewhere other than the pinned submodule."""


class SheetRefused(ValueError):
    """A sheet this mapping cannot lay honestly."""


def atlas():
    """(films, processes, emulsion) from vendor/atlas-film, or refused by name."""
    if not (ATLAS_ROOT / "atlas_film" / "__init__.py").is_file():
        raise AtlasFilmMissing(f"atlas-film is not checked out at {ATLAS_ROOT}: "
                               "git submodule update --init vendor/atlas-film")
    if "atlas_film" not in sys.modules:
        sys.path.insert(0, str(ATLAS_ROOT))
        try:
            import atlas_film  # noqa: F401
        finally:
            sys.path.remove(str(ATLAS_ROOT))
    where = pathlib.Path(sys.modules["atlas_film"].__file__).resolve()
    if not where.is_relative_to(ATLAS_ROOT.resolve()):
        raise AtlasFilmShadowed(f"atlas_film is imported from {where}, not from the pinned submodule "
                                f"{ATLAS_ROOT}: import quantum_film.develop before anything imports atlas_film")
    from atlas_film import emulsion, films, processes
    return films, processes, emulsion


def borrowed(stock_id):
    """The atlas-film stock a Quantum-Film stock borrows everything after coating from, and its numbers."""
    films, processes, emulsion = atlas()
    name = params(stock_id)["borrows"]
    st = films.FILMS[name]
    return name, float(st["dmax"]), float(st["grain_um2"]), float(processes.KAPPA), emulsion.floor_um(st["grain_um2"])


def mean_k(stock_id, layers):
    law = params(stock_id)
    return Fraction(layers * law["N"], law["M"])


def pitch_um(stock_id, layers):
    """The pitch at which the borrowed stock's lambda_K equals this sheet's mean K; refused by name outside
    the honesty floor and pinned mode's exact regime."""
    if not isinstance(layers, int) or isinstance(layers, bool) or layers < 1:
        raise SheetRefused(f"layers is a positive int, not {layers!r}")
    name, dmax, a, kappa, floor = borrowed(stock_id)
    k = mean_k(stock_id, layers)
    pitch = math.sqrt(float(k) * kappa * a / dmax)
    if pitch < floor:
        need = math.ceil(dmax * floor * floor / (kappa * a) * params(stock_id)["M"] / params(stock_id)["N"])
        raise SheetRefused(f"{layers} layers of {stock_id} put {float(k):.3f} crystals in a cell, and {name}'s "
                           f"density then asks a {pitch:.3f} um cell, under its honesty floor of {floor:.3f} um "
                           f"(one crystal across): lay at least {need} layers")
    lam = float(k)
    if lam + 8.0 * math.sqrt(lam) + 16.0 > EXACT_KMAX:
        raise SheetRefused(f"{layers} layers put {lam:.1f} crystals in a cell: past pinned mode's exact regime "
                           f"(lambda + 8 sqrt(lambda) + 16 <= {EXACT_KMAX})")
    return pitch


def _u16(parts, i):
    u = uniform(stream(*parts), i)
    return (u.numerator * 65536) // u.denominator          # the top 16 bits of the 64-bit uniform


def _below(parts, i, n):
    """An int uniform in [0, n), exactly: floor(u * n)."""
    u = uniform(stream(*parts), i)
    return (u.numerator * n) // u.denominator


def sheet(layouts, stock_id, tiles, layers, print_stream):
    """(K, thresholds, (height, width)) for `tiles` = (across, down) tiles, `layers` deep.

    `layouts[slot]` is one roll's sorted site indices, N of them; slot = (layer * down + ty) * across + tx.
    `print_stream` is a tuple of str and int parts naming this print; offsets and thresholds are drawn on it."""
    law = params(stock_id)
    L, N = law["L"], law["N"]
    across, down = tiles
    if len(layouts) != layers * across * down:
        raise SheetRefused(f"{len(layouts)} layouts for {layers} layers of {across} x {down} tiles")
    H, W = down * L, across * L
    columns = [[] for _ in range(H * W)]
    for d in range(layers):
        oy = _below(("offset", *print_stream, d), 0, L)
        ox = _below(("offset", *print_stream, d), 1, L)
        for ty in range(down):
            for tx in range(across):
                sites = layouts[(d * down + ty) * across + tx]
                if len(sites) != N or len(set(sites)) != N or not all(0 <= s < L * L for s in sites):
                    raise SheetRefused(f"layer {d}, tile ({tx}, {ty}): {sites!r} is not {N} distinct sites "
                                       f"of a {L} x {L} tile")
                parts = ("threshold", *print_stream, d, ty, tx)
                for j, s in enumerate(sites):
                    r, c = divmod(s, L)
                    columns[((ty * L + r + oy) % H) * W + (tx * L + c + ox) % W].append(_u16(parts, j))
    K = np.array([len(c) for c in columns], np.int32)
    thr = np.full((K.size, max(int(K.max()), 1)), 65535, np.uint16)
    for i, c in enumerate(columns):
        thr[i, :len(c)] = c
    if int(K.sum()) != layers * across * down * N:
        raise AssertionError("a crystal was lost laying the sheet")
    return K, thr, (H, W)


def shuffled(items, print_stream):
    """`items` in a Fisher-Yates order drawn on the print's stream: exact, the same everywhere."""
    out = list(items)
    for i in range(len(out) - 1, 0, -1):
        j = _below(("shuffle", *print_stream), i, i + 1)
        out[i], out[j] = out[j], out[i]
    return out


def device_shots(records):
    """Every shot of a set of device-roll records, as layouts, in the canonical order: by job, then layout,
    each layout `occurrences` times."""
    keyed = sorted(((r["source"]["job_id"], tuple(r["crystals"]), int(r["source"].get("occurrences", 1)))
                    for r in records))
    return [list(lay) for _job, lay, n in keyed for _ in range(n)]


def negative(scene, E, stock_id, K, thr, pitch):
    """The borrowed stock's negative on this sheet, in pinned mode: density, float32 as atlas-film returns."""
    films, _processes, _emulsion = atlas()
    name = params(stock_id)["borrows"]
    return films.negative(np.asarray(scene, np.float64), float(E), name, pitch_um=float(pitch), sheet=(K, thr),
                          mtf=False, pinned=True)


def positive(D, E_print, paper="silver"):
    """The negative printed on a paper, ungrained, in pinned mode: reflectance per RGB channel."""
    films, processes, _emulsion = atlas()
    T = np.asarray(films.transmit(D, pinned=True), np.float64)
    return processes.process_print(np.repeat(T[..., None], 3, -1), float(E_print), paper, grain=False,
                                   pinned=True)


def digest(array):
    """SHA-256 of an array's dtype, shape and bytes."""
    a = np.ascontiguousarray(array)
    h = hashlib.sha256(f"{a.dtype.str}|{a.shape}|".encode("ascii"))
    h.update(a.tobytes())
    return h.hexdigest()

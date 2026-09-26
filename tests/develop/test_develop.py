"""The develop seam: rolls -> a sheet -> atlas-film's pinned negative and print (quantum_film/develop.py)."""
import hashlib
import math
import types

import numpy as np
import pytest

from quantum_film import develop
from quantum_film.golden import fermi
from quantum_film.golden.uniform import stream

# atlas-film's package files at the pinned submodule (d4007b2), line endings normalised: bumping the submodule
# fails here first, so the frozen prints below are re-derived deliberately, never by accident
ATLAS_FILM_TREE = "54689c45ac886b92a769966e9be1ed1c1a6f70b723ce1be78189af1f4234a114"

# one small print, laid from golden rolls, frozen: the same bits on every machine (quantum_film/develop.py)
TILES, LAYERS, STREAM = (3, 2), 29, ("test-print", 1)
E_SCENE = 0.0625                  # exact in binary64; not metered, so the default path cannot move it
FROZEN = {"K": "d98b82b30e0ea6475026ce0d641de22946f1c18c046e56ce6b6c142f629c081c",
          "thresholds": "e1a4dab38adb666f70f76e734c9c42b6b0364cf0a1f8732ff9eca1e6e5630c39",
          "negative": "442a7a1e4b7fe078321cfb69dc3b9c025b709255dec3b3f9faacd5049682a471",
          "print": "fd22a1508b26d5db4c33b8d14ff0c986081700f14176db700e072d267360da70"}


def tree_digest():
    h = hashlib.sha256()
    for f in sorted((develop.ATLAS_ROOT / "atlas_film").glob("*.py")):
        h.update(f.name.encode("ascii") + b"\0" + f.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return h.hexdigest()


def rolls(stock, count, first=1):
    law = develop.params(stock)
    return [fermi.sample(law["L"], law["fermi_r2"], stream("roll", stock, first + s)) for s in range(count)]


def scene(H, W):
    xx = np.mgrid[0:H, 0:W][1] / max(W - 1, 1)
    return 0.25 * (16.0 ** xx)


@pytest.fixture(scope="module")
def small():
    lays = rolls("pauli-4x4", LAYERS * TILES[0] * TILES[1])
    K, thr, (H, W) = develop.sheet(lays, "pauli-4x4", TILES, LAYERS, STREAM)
    pitch = develop.pitch_um("pauli-4x4", LAYERS)
    D = develop.negative(scene(H, W), E_SCENE, "pauli-4x4", K, thr, pitch)
    P = develop.positive(D, 1.0)
    return {"lays": lays, "K": K, "thr": thr, "H": H, "W": W, "pitch": pitch, "D": D, "P": P}


def test_atlas_film_comes_from_the_pinned_submodule_and_is_the_one_frozen_here():
    films, _processes, _emulsion = develop.atlas()
    import sys
    assert sys.modules["atlas_film"].__file__.startswith(str(develop.ATLAS_ROOT))
    assert films.__file__.startswith(str(develop.ATLAS_ROOT))
    assert tree_digest() == ATLAS_FILM_TREE


def test_an_atlas_film_imported_from_elsewhere_is_refused_by_name(monkeypatch, tmp_path):
    fake = types.ModuleType("atlas_film")
    fake.__file__ = str(tmp_path / "atlas_film" / "__init__.py")
    monkeypatch.setitem(__import__("sys").modules, "atlas_film", fake)
    with pytest.raises(develop.AtlasFilmShadowed, match="not from the pinned submodule"):
        develop.atlas()


def test_a_missing_submodule_is_refused_by_name(monkeypatch, tmp_path):
    monkeypatch.setattr(develop, "ATLAS_ROOT", tmp_path)
    with pytest.raises(develop.AtlasFilmMissing, match="git submodule update --init"):
        develop.atlas()


@pytest.mark.parametrize("stock,least", [("pauli", 91), ("pauli-4x4", 29), ("poisson", 91)])
def test_the_pitch_puts_the_borrowed_stocks_own_density_in_every_cell_and_no_cell_is_under_the_floor(stock, least):
    _films, processes, _emulsion = develop.atlas()
    _name, dmax, a, kappa, floor = develop.borrowed(stock)
    for layers in (least, least + 1, 3 * least):
        pitch = develop.pitch_um(stock, layers)
        lam = dmax * pitch * pitch / (kappa * a)
        assert math.isclose(lam, float(develop.mean_k(stock, layers)), rel_tol=4 * 2.0 ** -52)
        assert pitch >= floor
    with pytest.raises(develop.SheetRefused, match=rf"honesty floor .* lay at least {least} layers"):
        develop.pitch_um(stock, least - 1)


def test_a_sheet_past_pinned_modes_exact_regime_is_refused_by_name():
    with pytest.raises(develop.SheetRefused, match="exact regime"):
        develop.pitch_um("pauli-4x4", 400)              # 125 crystals a cell
    assert develop.pitch_um("pauli-4x4", 300)          # 93.75 a cell: inside


def test_every_crystal_lands_in_exactly_one_column(small):
    K = small["K"]
    assert int(K.sum()) == LAYERS * TILES[0] * TILES[1] * 5
    one, _thr, _hw = develop.sheet(small["lays"][:TILES[0] * TILES[1]], "pauli-4x4", TILES, 1, STREAM)
    assert set(np.unique(one)) <= {0, 1} and int(one.sum()) == TILES[0] * TILES[1] * 5


def test_the_sheet_keeps_atlas_films_contract_and_a_broken_pad_is_refused_there(small):
    K, thr = small["K"], small["thr"]
    cols = np.arange(thr.shape[1])[None, :]
    assert np.all(thr[cols >= K[:, None]] == 65535)
    bad = thr.copy()
    i = int(np.argmin(K))
    bad[i, int(K[i])] = 7                               # a pad that develop_on would count as a crystal
    with pytest.raises(ValueError):
        develop.negative(scene(small["H"], small["W"]), E_SCENE, "pauli-4x4", K, bad, small["pitch"])


def test_a_print_is_the_same_bits_again_and_the_frozen_ones(small):
    again = develop.negative(scene(small["H"], small["W"]), E_SCENE, "pauli-4x4", small["K"], small["thr"],
                             small["pitch"])
    assert develop.digest(again) == develop.digest(small["D"])
    assert develop.digest(develop.positive(again, 1.0)) == develop.digest(small["P"])
    got = {"K": develop.digest(small["K"]), "thresholds": develop.digest(small["thr"]),
           "negative": develop.digest(small["D"]), "print": develop.digest(small["P"])}
    assert got == FROZEN


def test_one_moved_crystal_changes_the_negative(small):
    lays = [list(x) for x in small["lays"]]
    free = next(s for s in range(16) if s not in lays[0])
    lays[0][0] = free
    lays[0].sort()
    K2, thr2, _hw = develop.sheet(lays, "pauli-4x4", TILES, LAYERS, STREAM)
    assert int(np.abs(K2 - small["K"]).sum()) == 2
    bright = np.full((small["H"], small["W"]), 1e3)     # every crystal develops: density is the count
    D1 = develop.negative(bright, 1.0, "pauli-4x4", small["K"], small["thr"], small["pitch"])
    D2 = develop.negative(bright, 1.0, "pauli-4x4", K2, thr2, small["pitch"])
    assert develop.digest(D1) != develop.digest(D2)


def test_layouts_that_are_not_rolls_are_refused_by_name(small):
    lays = [list(x) for x in small["lays"]]
    for broken in ([0, 0, 1, 2, 3], [0, 1, 2, 3], [0, 1, 2, 3, 16]):
        bad = lays[:]
        bad[5] = broken
        with pytest.raises(develop.SheetRefused, match="distinct sites"):
            develop.sheet(bad, "pauli-4x4", TILES, LAYERS, STREAM)
    with pytest.raises(develop.SheetRefused, match="layouts for"):
        develop.sheet(lays[:-1], "pauli-4x4", TILES, LAYERS, STREAM)


def test_offsets_and_shuffles_are_exact_and_the_streams_own():
    order = develop.shuffled(range(1000), ("s", 1))
    assert sorted(order) == list(range(1000)) and order != list(range(1000))
    assert order == develop.shuffled(range(1000), ("s", 1)) and order != develop.shuffled(range(1000), ("s", 2))
    offs = {(develop._below(("offset", "x", d), 0, 16), develop._below(("offset", "x", d), 1, 16)) for d in range(64)}
    assert all(0 <= y < 16 and 0 <= x < 16 for y, x in offs) and len(offs) > 32


def test_device_shots_are_every_occurrence_in_the_canonical_order():
    recs = [{"crystals": [0, 1, 2, 3, 4], "source": {"job_id": "b", "occurrences": 2}},
            {"crystals": [0, 1, 2, 3, 5], "source": {"job_id": "a", "occurrences": 1}},
            {"crystals": [0, 1, 2, 3, 6], "source": {"job_id": "b", "occurrences": 3}}]
    shots = develop.device_shots(recs)
    assert shots == [[0, 1, 2, 3, 5]] + [[0, 1, 2, 3, 4]] * 2 + [[0, 1, 2, 3, 6]] * 3
    assert develop.device_shots(list(reversed(recs))) == shots

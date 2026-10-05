#!/usr/bin/env python3
"""The first prints: rolls laid as sheets of film, developed and printed through atlas-film's pinned mode.

    python tools/first_prints.py [--workers N] [--only NAME ...]

Each print is written under docs/prints/ as a record (<name>.json) and two images (<name>-negative.png and
<name>-print.png; each pixel is one cell, a column of crystals). A record names everything the print is a
function of: its rolls, the mapping (tiles, layers, the print's stream), the pitch, the scene, the exposures
and atlas-film's commit. It also names the digests of the sheet, the negative and the print, so
`--check` can re-develop every print and compare its bits.

    python tools/first_prints.py --check           re-develop each committed print; exit 1 unless every
                                                   digest matches (golden rolls re-laid, device rolls re-read)

The prints (quantum_film/develop.py says how a sheet is laid):
  atlas-pauli-4x4    every shot of the six Atlas jobs (docs/records/*/p3/), shuffled, 29 layers of 29 x 29 tiles
  golden-pauli-4x4   the same law, the same geometry, from golden rolls
  pauli              91 layers of 16 x 16 Pauli tiles, 256 x 256 cells, from golden rolls
  poisson            the same geometry and density, N sites uniformly without replacement per tile
  trix               atlas-film's own TRI-X coating at the same pitch (its pinned sheet): the classical film
  ibm-<device>-pauli-4x4   round 3's hardware prints, one per IBM device (kingston, marrakesh, fez): the device's
                     qpu law run by compare's print rule (its N-crystal shots in canonical order, shuffled on the
                     print stream), in the geometry their count allows (compare.print_geometry: 29 layers deep)
"""
if __name__ not in ("__main__", "__mp_main__"):     # a spawned worker re-imports this file as __mp_main__
    raise ImportError("this script writes files when it runs; run it, never import it (CLAUDE.md)")

import argparse  # noqa: E402
import json  # noqa: E402
import pathlib  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from multiprocessing import Pool  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402

from quantum_film import develop  # noqa: E402
from quantum_film.golden import binomial  # noqa: E402
from quantum_film.golden.uniform import stream  # noqa: E402
from quantum_film.stocks import params  # noqa: E402

OUT = ROOT / "docs" / "prints"
RECORDS = ROOT / "docs" / "records"
E_PRINT = 1.0
PRINTS = {
    "atlas-pauli-4x4": {"stock": "pauli-4x4", "tiles": (29, 29), "layers": 29, "rolls": "device"},
    "golden-pauli-4x4": {"stock": "pauli-4x4", "tiles": (29, 29), "layers": 29, "rolls": "golden"},
    "pauli": {"stock": "pauli", "tiles": (16, 16), "layers": 91, "rolls": "golden"},
    "poisson": {"stock": "poisson", "tiles": (16, 16), "layers": 91, "rolls": "golden"},
    "trix": {"stock": "pauli", "tiles": (16, 16), "layers": 91, "rolls": "atlas-film"},
    # Round 3's hardware prints: each device's qpu law run by compare's print rule (docs/PREREGISTRATION.md); the
    # tiles and layers follow from the count of its N-crystal shots (compare.print_geometry), so they are filled in
    # from the records when the print is made (spec_of).
    "ibm-kingston-pauli-4x4": {"stock": "pauli-4x4", "rolls": "qpu", "device": "ibm_kingston"},
    "ibm-marrakesh-pauli-4x4": {"stock": "pauli-4x4", "rolls": "qpu", "device": "ibm_marrakesh"},
    "ibm-fez-pauli-4x4": {"stock": "pauli-4x4", "rolls": "qpu", "device": "ibm_fez"},
}
QPU_RUNS = RECORDS / "2026-10-05" / "ibm"


def qpu_layouts(device):
    """compare's print rule over one device's committed qpu law runs: every shot with exactly N crystals, in canonical
    order (job, then layout, each layout its shots), and the geometry their count allows."""
    from quantum_film import compare
    recs = [r for r in compare.device_runs([QPU_RUNS / device / "run"]) if r["role"] == "law"]
    layouts = compare.print_layouts(recs)
    return recs, layouts, compare.print_geometry(len(layouts))


def spec_of(name):
    spec = PRINTS[name]
    if spec["rolls"] != "qpu":
        return spec
    _recs, _layouts, geo = qpu_layouts(spec["device"])
    return dict(spec, tiles=tuple(geo["tiles"]), layers=geo["layers"])


def roll(job):
    """One golden roll: the pinned sampler for the determinantal law (the authority's roll by construction,
    quantum_film/pinned), the golden sampler for the binomial one."""
    stock, seed = job
    law = params(stock)
    s = stream("roll", stock, seed)
    if law["family"] == "determinantal":
        from quantum_film.pinned import sampler
        return list(sampler.sample(law["L"], law["fermi_r2"], s))
    return list(binomial.sample(law["M"], law["N"], s))


def device_records():
    recs = []
    for f in sorted(RECORDS.glob("*/p3/rolls-*/*.json")):
        recs.append(json.loads(f.read_text(encoding="ascii")))
    jobs = sorted({r["source"]["job_id"] for r in recs})
    return recs, jobs


def scene(H, W):
    """A ramp across the frame with a bright disc: tone and grain in one field. Only IEEE's correctly rounded
    operations make it, no libm, so it is the same bits everywhere (its digest is in each record)."""
    yy, xx = np.mgrid[0:H, 0:W]
    y, x = yy / max(H - 1, 1), xx / max(W - 1, 1)
    out = 0.02 + 0.58 * x
    out[(y - 0.5) * (y - 0.5) + (x - 0.3) * (x - 0.3) < 0.04] = 0.9
    return out


def radial_s(K):
    """The count field's structure factor, per crystal, radially averaged at integer |k| (units of 2 pi / side)."""
    f = K.astype(np.float64)
    side = f.shape[0]
    P = np.abs(np.fft.fft2(f - f.mean())) ** 2 / (f.size * f.mean())
    ky, kx = np.meshgrid(np.fft.fftfreq(side) * side, np.fft.fftfreq(f.shape[1]) * f.shape[1], indexing="ij")
    kr = np.rint(np.hypot(kx, ky)).astype(int)
    return [round(float(P[kr == k].mean()), 4) for k in range(1, side // 2)]


def lay(name, spec, pool):
    stock, (across, down), layers = spec["stock"], spec["tiles"], spec["layers"]
    n = across * down * layers
    parts = ("print", name)
    source = {"kind": spec["rolls"]}
    if spec["rolls"] == "golden":
        layouts = pool.map(roll, [(stock, 1 + i) for i in range(n)], chunksize=32)
        source.update(stock=stock, stream=["roll", stock, "seed"], seeds=[1, n])
    elif spec["rolls"] == "device":
        recs, jobs = device_records()
        shots = develop.shuffled(develop.device_shots(recs), parts)
        layouts = shots[:n]
        source.update(stock=stock, jobs=jobs, shots=len(shots), used=n, unused=len(shots) - n,
                      order="canonical (job, layout), each layout its occurrences, then shuffled on the print "
                            "stream; the first `used` are laid")
    elif spec["rolls"] == "qpu":
        recs, qlayouts, geo = qpu_layouts(spec["device"])
        if (list(spec["tiles"]), spec["layers"]) != (geo["tiles"], geo["layers"]):
            raise SystemExit(f"{name}: the spec's geometry is not compare.print_geometry's")
        layouts = develop.shuffled(qlayouts, parts)[:n]
        source.update(stock=stock, device=spec["device"], jobs=sorted({r["source"]["job_id"] for r in recs}),
                      shots=sum(sum(c for _y, c in r["counts"]) for r in recs), n_crystal_shots=len(qlayouts),
                      used=n, unused=len(qlayouts) - n,
                      order="compare.print_layouts: the N-crystal shots of the qpu law run in canonical order (job, "
                            "layout), each layout its shots; then shuffled on the print stream; the first `used` "
                            "are laid (compare.print_geometry)")
    else:
        return None, source
    return layouts, source


def make(name, spec, pool, E=None):
    t0 = time.perf_counter()
    films, processes, emulsion = develop.atlas()
    stock, (across, down), layers = spec["stock"], spec["tiles"], spec["layers"]
    law = params(stock)
    pitch = develop.pitch_um(stock, layers)
    layouts, source = lay(name, spec, pool)
    if layouts is None:                  # atlas-film's own coating of the borrowed stock, at the same pitch
        bname, dmax, a, _kappa, _floor = develop.borrowed(stock)
        H, W = down * law["L"], across * law["L"]
        K, thr = emulsion.coat(H * W, dmax, a, pitch, 1, pinned=True)
        source.update(stock=bname, coat="atlas_film.emulsion.coat(cells, dmax, grain_um2, pitch, seed=1, "
                                        "pinned=True)")
    else:
        K, thr, (H, W) = develop.sheet(layouts, stock, (across, down), layers, ("print", name))
    img = scene(H, W)
    if E is None:                        # metered once, on atlas-film's default path; the record keeps it exactly
        E = float(films.normal_exposure(img, law["borrows"]))
    D = develop.negative(img, E, stock, K, thr, pitch)
    P = develop.positive(D, E_PRINT)
    rec = {"format": develop.PRINT_FORMAT, "name": name,
           "stock": source["stock"] if spec["rolls"] == "atlas-film" else stock, "borrows": law["borrows"],
           "rolls": source, "tiles": [across, down], "layers": layers, "print_stream": ["print", name],
           "cells": [H, W], "pitch_um": pitch.hex(), "pitch_um_decimal": round(pitch, 6),
           "mean_K": float(K.mean()),
           "scene": {"name": "log ramp with a bright disc (tools/first_prints.py: scene)",
                     "sha256": develop.digest(img)},
           "E": E.hex(), "E_print": E_PRINT.hex(), "paper": "silver, ungrained",
           "atlas_film": atlas_commit(),
           "digests": {"K": develop.digest(K), "thresholds": develop.digest(thr), "negative": develop.digest(D),
                       "print": develop.digest(P)},
           "structure_factor": {"of": "the sheet's count field K, per crystal, radially averaged",
                                "k_units": "2 pi / side", "S": radial_s(K.reshape(H, W))}}
    return rec, D, P, time.perf_counter() - t0


def atlas_commit():
    p = subprocess.run(["git", "-C", str(develop.ATLAS_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
    return p.stdout.strip() or "unknown"


def save(rec, D, P):
    from PIL import Image
    OUT.mkdir(parents=True, exist_ok=True)
    name = rec["name"]
    d = np.asarray(D, np.float64)
    neg = np.clip(255.0 * (1.0 - d / max(float(d.max()), 1e-9)), 0, 255).astype(np.uint8)
    pos = np.clip(np.asarray(P, np.float64)[..., 0] * 255.0, 0, 255).astype(np.uint8)
    scale = max(1, 512 // max(neg.shape))
    for suffix, a in (("negative", neg), ("print", pos)):
        Image.fromarray(a).resize((a.shape[1] * scale, a.shape[0] * scale), Image.NEAREST).save(
            OUT / f"{name}-{suffix}.png", optimize=True)
    (OUT / f"{name}.json").write_text(json.dumps(rec, indent=1) + "\n", encoding="ascii", newline="\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    names = args.only or list(PRINTS)
    bad = 0
    with Pool(args.workers) as pool:
        for name in names:
            old = json.loads((OUT / f"{name}.json").read_text(encoding="ascii")) if args.check else None
            rec, D, P, secs = make(name, spec_of(name), pool, float.fromhex(old["E"]) if old else None)
            if args.check:
                same = old["digests"] == rec["digests"] and old["scene"] == rec["scene"]
                bad += not same
                print(f"{name}: {'the same bits' if same else 'DIFFERENT BITS'} ({secs:.0f} s)")
            else:
                save(rec, D, P)
                print(f"{name}: {rec['cells'][0]} x {rec['cells'][1]} cells at {rec['pitch_um_decimal']} um, "
                      f"mean K {rec['mean_K']:.4f}, print {rec['digests']['print'][:16]} ({secs:.0f} s)")
    if bad:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

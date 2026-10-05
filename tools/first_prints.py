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
  golden-pauli-4x4-sheet  the exact law's own rolls at 64 x 64 tiles, 29 layers deep: 256 columns, the reference
                     for the sheets below
  ibm-<device>-sheet the same rule over every law run of the device on 2026-10-05, the morning's and the sheet
                     bundles' (docs/PREREGISTRATION.md, the note of that day): about 256 columns from each device
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
    # The sheets (docs/PREREGISTRATION.md, the note of 2026-10-05): each device's law runs of that day pooled, the
    # morning's and the sheet bundles', for a print of about 256 columns from each device.
    "golden-pauli-4x4-sheet": {"stock": "pauli-4x4", "tiles": (64, 64), "layers": 29, "rolls": "golden"},
    "twin-pauli-4x4-sheet": {"stock": "pauli-4x4", "tiles": (64, 64), "layers": 29, "rolls": "twin"},
    "ibm-kingston-sheet": {"stock": "pauli-4x4", "rolls": "qpu", "device": "ibm_kingston", "runs": "day"},
    "ibm-marrakesh-sheet": {"stock": "pauli-4x4", "rolls": "qpu", "device": "ibm_marrakesh", "runs": "day"},
    "ibm-fez-sheet": {"stock": "pauli-4x4", "rolls": "qpu", "device": "ibm_fez", "runs": "day"},
}
QPU_RUNS = RECORDS / "2026-10-05" / "ibm"
TINT = (0.90, 0.27, 0.12)       # the forbidden layouts' colour, in the overlay and the layer view
TINT_GAIN = 2.0                 # a column's tint is TINT_GAIN times the share of its crystals that are forbidden


def qpu_run_dirs(device, runs="morning"):
    """The run directories a print reads: the morning's set alone, or every law run of the device that day."""
    dirs = [QPU_RUNS / device / "run"]
    return dirs if runs == "morning" else dirs + sorted((QPU_RUNS / device).glob("sheet-*/run"))


def qpu_layouts(device, runs="morning"):
    """compare's print rule over one device's committed qpu law runs: every shot with exactly N crystals, in canonical
    order (job, then layout, each layout its shots), and the geometry their count allows."""
    from quantum_film import compare
    recs = [r for r in compare.device_runs(qpu_run_dirs(device, runs)) if r["role"] == "law"]
    layouts = compare.print_layouts(recs)
    return recs, layouts, compare.print_geometry(len(layouts))


def spec_of(name):
    spec = PRINTS[name]
    if spec["rolls"] != "qpu":
        return spec
    _recs, _layouts, geo = qpu_layouts(spec["device"], spec.get("runs", "morning"))
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
    elif spec["rolls"] == "twin":       # compare's classical twin: N distinct sites of the tile, uniformly
        law = params(stock)
        layouts = [binomial.sample(law["M"], law["N"], stream("twin", stock, i)) for i in range(1, n + 1)]
        source.update(stock=stock, law="the classical twin: N distinct sites of M, uniformly (golden.binomial)",
                      stream=["twin", stock, "i"], seeds=[1, n])
    elif spec["rolls"] == "qpu":
        recs, qlayouts, geo = qpu_layouts(spec["device"], spec.get("runs", "morning"))
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


def nn_pairs(sites, L):
    """The nearest-neighbour pairs a layout holds on its L x L periodic tile: how clumped its crystals are."""
    s = set(sites)
    return sum(((r * L + (c + 1) % L) in s) + ((((r + 1) % L) * L + c) in s) for r, c in (divmod(p, L) for p in s))


def law_clumping(stock):
    """(the law's mean nearest-neighbour pairs per layout, exactly as a Fraction; the forbidden layouts' mean, each
    counted once; the largest count among the layouts the law allows)."""
    from fractions import Fraction

    from quantum_film import compare
    L = params(stock)["L"]
    ys, ws, den = compare.exact_law(stock)
    law = sum(Fraction(w * nn_pairs(Y, L), den) for Y, w in zip(ys, ws, strict=True))
    bad = [nn_pairs(Y, L) for Y, w in zip(ys, ws, strict=True) if w == 0]
    return law, Fraction(sum(bad), len(bad)), max(nn_pairs(Y, L) for Y, w in zip(ys, ws, strict=True) if w > 0)


def forbidden_counts(layouts, stock, tiles, layers, print_stream):
    """(K, F, forbidden layouts laid): K each crystal column's crystals and F how many of them came from a layout
    the exact law forbids (compare.exact_law: weight 0), mapped exactly as develop.sheet maps them (its per-layer
    offsets, drawn on the print stream). The caller holds K to develop.sheet's own."""
    from quantum_film import compare
    law = params(stock)
    L = law["L"]
    ys, ws, _den = compare.exact_law(stock)
    forbidden = {Y for Y, w in zip(ys, ws, strict=True) if w == 0}
    across, down = tiles
    H, W = down * L, across * L
    K = np.zeros(H * W, np.int32)
    F = np.zeros(H * W, np.int32)
    laid = 0
    for d in range(layers):
        oy = develop._below(("offset", *print_stream, d), 0, L)
        ox = develop._below(("offset", *print_stream, d), 1, L)
        for ty in range(down):
            for tx in range(across):
                sites = layouts[(d * down + ty) * across + tx]
                bad = tuple(sorted(sites)) in forbidden
                laid += bad
                for s in sites:
                    r, c = divmod(s, L)
                    i = ((ty * L + r + oy) % H) * W + (tx * L + c + ox) % W
                    K[i] += 1
                    F[i] += bad
    return K, F, laid


def forbidden_overlay(name, spec, pool):
    """A committed print with every crystal column that holds a crystal of a forbidden layout tinted: the layouts
    re-laid exactly as the print was, the print re-developed at its recorded exposure, and both its crystal counts
    and its print digest held to the committed record's before anything is drawn."""
    rec = json.loads((OUT / f"{name}.json").read_text(encoding="ascii"))
    stock, (across, down), layers = spec["stock"], spec["tiles"], spec["layers"]
    layouts, _source = lay(name, spec, pool)
    K0, thr, (H, W) = develop.sheet(layouts, stock, (across, down), layers, ("print", name))
    K, F, laid = forbidden_counts(layouts, stock, (across, down), layers, ("print", name))
    if not np.array_equal(K, K0):
        raise SystemExit(f"{name}: the forbidden map's crystal counts are not develop.sheet's")
    E = float.fromhex(rec["E"])
    D = develop.negative(scene(H, W), E, stock, K0, thr, develop.pitch_um(stock, layers))
    P = develop.positive(D, E_PRINT)
    if develop.digest(P) != rec["digests"]["print"]:
        raise SystemExit(f"{name}: the re-developed print is not the committed one")
    gray = np.clip(np.asarray(P, np.float64)[..., 0], 0.0, 1.0)
    # each column tinted by the share of its crystals that came from forbidden layouts, at a gain of TINT_GAIN: a
    # column with one forbidden crystal among nine is tinted 0.22, one with a third forbidden 0.67
    share = np.divide(F, K, out=np.zeros(F.shape, np.float64), where=K > 0).reshape(H, W)
    a = np.minimum(1.0, TINT_GAIN * share)[..., None]
    rgb = gray[..., None] * (1.0 - a) + np.array(TINT) * a
    hist = np.bincount(np.minimum(F, 3), minlength=4)
    stats = {"name": name, "layouts": len(layouts), "forbidden_layouts": int(laid),
             "forbidden_share": round(laid / len(layouts), 6), "cells": int(K.size),
             "cells_with_a_forbidden_crystal": int((F > 0).sum()),
             "share_of_cells": round(float((F > 0).mean()), 6), "mean_forbidden_crystals_per_cell": round(
                 float(F.mean()), 6), "cells_by_forbidden_crystals_0_1_2_3plus": [int(x) for x in hist],
             "share_of_crystals_forbidden": round(float(F.sum() / K.sum()), 6),
             **clumping(layouts, stock),
             "print_digest": rec["digests"]["print"],
             "tint": f"rgb{tuple(round(255 * c) for c in TINT)}, alpha min(1, {TINT_GAIN} x F / K) per column"}
    return np.clip(rgb * 255.0, 0, 255).round().astype(np.uint8), stats, layer_view(layouts, stock, (across, down),
                                                                                   ("print", name))


def clumping(layouts, stock):
    """The mean nearest-neighbour pairs of the forbidden and the allowed layouts a print laid, beside the law's."""
    from quantum_film import compare
    L = params(stock)["L"]
    ys, ws, _den = compare.exact_law(stock)
    forbidden = {Y for Y, w in zip(ys, ws, strict=True) if w == 0}
    bad, good = [], []
    for sites in layouts:
        (bad if tuple(sorted(sites)) in forbidden else good).append(nn_pairs(sites, L))
    law, forb, most = law_clumping(stock)
    return {"mean_nn_pairs_forbidden_laid": round(sum(bad) / len(bad), 4) if bad else None,
            "mean_nn_pairs_allowed_laid": round(sum(good) / len(good), 4) if good else None,
            "law_mean_nn_pairs": str(law), "forbidden_layouts_mean_nn_pairs": str(forb),
            "most_nn_pairs_the_law_allows": most}


def layer_view(layouts, stock, tiles, print_stream, d=0):
    """One layer of a sheet, shot by shot: each tile is one layout, its crystals dark on white, and a layout the
    exact law forbids drawn in the tint, so its shape shows (the print sums 29 such layers and hides it)."""
    from quantum_film import compare
    law = params(stock)
    L = law["L"]
    ys, ws, _den = compare.exact_law(stock)
    forbidden = {Y for Y, w in zip(ys, ws, strict=True) if w == 0}
    across, down = tiles
    H, W = down * L, across * L
    img = np.full((H, W, 3), 255, np.uint8)
    oy = develop._below(("offset", *print_stream, d), 0, L)
    ox = develop._below(("offset", *print_stream, d), 1, L)
    ink = np.array([40, 40, 40], np.uint8)
    tint = np.array([round(255 * c) for c in TINT], np.uint8)
    for ty in range(down):
        for tx in range(across):
            sites = layouts[(d * down + ty) * across + tx]
            colour = tint if tuple(sorted(sites)) in forbidden else ink
            for s in sites:
                r, c = divmod(s, L)
                img[(ty * L + r + oy) % H, (tx * L + c + ox) % W] = colour
    return img


def save_overlay(name, rgb, stats, layer):
    from PIL import Image
    for suffix, img in (("forbidden", rgb), ("layer", layer)):
        h, w = img.shape[:2]
        scale = max(1, 512 // max(h, w))
        Image.fromarray(img, "RGB").resize((w * scale, h * scale), Image.NEAREST).save(OUT / f"{name}-{suffix}.png",
                                                                                        optimize=True)
    path = OUT / "forbidden.json"
    table = json.loads(path.read_text(encoding="ascii")) if path.exists() else {}
    table[name] = stats
    path.write_text(json.dumps(table, indent=1, sort_keys=True) + "\n", encoding="ascii", newline="\n")


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
    ap.add_argument("--forbidden", action="store_true",
                    help="tint, in each committed print named, the crystal columns that hold a crystal of a layout the "
                         "exact law forbids (docs/prints/<name>-forbidden.png and forbidden.json)")
    args = ap.parse_args()
    names = args.only or list(PRINTS)
    bad = 0
    with Pool(args.workers) as pool:
        if args.forbidden:
            for name in names:
                t0 = time.perf_counter()
                rgb, stats, layer = forbidden_overlay(name, spec_of(name), pool)
                save_overlay(name, rgb, stats, layer)
                print(f"{name}: {stats['forbidden_layouts']:,} of {stats['layouts']:,} layouts forbidden "
                      f"({100 * stats['forbidden_share']:.2f}%), {100 * stats['share_of_cells']:.1f}% of cells tinted "
                      f"({time.perf_counter() - t0:.0f} s)")
            return
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

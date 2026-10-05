#!/usr/bin/env python3
"""The web demo's data, exported from the project's own records and authority.

    python tools/site_data.py

Writes under site/:
  data/atlas-shots.json   every Atlas shot of pauli-4x4 (docs/records/*/p3/), each a 16-bit mask of its five
                          sites, in the canonical order quantum_film.develop.device_shots gives
  data/fields.json        one layer of 8 x 8 tiles (128 x 128 sites): Pauli from golden rolls (the pinned
                          sampler, the authority's roll by construction) and its Poisson twin, the same streams
                          as the first prints' first tiles
  data/structure.json     each first print's structure factor, from its record
  data/hardware.json      round 3's IBM results, by quantum_film.compare over docs/records/2026-10-05/ibm, and
                          the forbidden layouts (docs/prints/forbidden.json)
  img/                    the first prints, and round 3's sheets (each print, tinted and one layer), copied from
                          docs/prints/
Nothing here is sampled by the page itself except the "roll a tile" toy, which says so.
"""
if __name__ != "__main__":
    raise ImportError("this script writes files when it runs; run it, never import it (CLAUDE.md)")

import base64  # noqa: E402
import json  # noqa: E402
import pathlib  # noqa: E402
import shutil  # noqa: E402
import sys  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np  # noqa: E402

from quantum_film import develop  # noqa: E402
from quantum_film.golden import binomial  # noqa: E402
from quantum_film.golden.uniform import stream  # noqa: E402
from quantum_film.pinned import sampler  # noqa: E402

SITE = ROOT / "site"
PRINTS = ROOT / "docs" / "prints"
NAMES = ("atlas-pauli-4x4", "golden-pauli-4x4", "pauli", "poisson", "trix")


def atlas_shots():
    files = sorted((ROOT / "docs" / "records").glob("*/p3/rolls-*/*.json"))
    recs = [json.loads(f.read_text(encoding="ascii")) for f in files]
    shots = develop.device_shots(recs)
    masks = np.array([sum(1 << s for s in lay) for lay in shots], "<u2")
    jobs = sorted({r["source"]["job_id"] for r in recs})
    per_job = [sum(int(r["source"].get("occurrences", 1)) for r in recs if r["source"]["job_id"] == j) for j in jobs]
    return {"stock": "pauli-4x4", "L": 4, "N": 5, "shots": len(shots), "jobs": jobs, "per_job": per_job,
            "order": "canonical: by job, then layout, each layout its occurrences",
            "masks_u16le_base64": base64.b64encode(masks.tobytes()).decode("ascii")}


def fields(tiles=8):
    out = {"L": 16, "N": 25, "tiles": tiles, "side": 16 * tiles}
    for name, fn in (("pauli", lambda s: list(sampler.sample(16, 8, s))),
                     ("poisson", lambda s: list(binomial.sample(256, 25, s)))):
        sites = []
        for i in range(tiles * tiles):
            ty, tx = divmod(i, tiles)
            for s in fn(stream("roll", name, 1 + i)):
                r, c = divmod(s, 16)
                sites.append((ty * 16 + r) * 16 * tiles + tx * 16 + c)
        out[name] = sorted(sites)
    out["source"] = ("golden rolls ('roll', stock, seed) for seeds 1..64, one per tile: the first tiles of the "
                     "first prints' first layer; Pauli laid by the pinned sampler, which lays the authority's roll")
    return out


def structure():
    out = {}
    for n in NAMES:
        rec = json.loads((PRINTS / f"{n}.json").read_text(encoding="ascii"))
        out[n] = {"side": rec["cells"][0], "S": rec["structure_factor"]["S"], "print": rec["digests"]["print"],
                  "pitch_um": rec["pitch_um_decimal"], "layers": rec["layers"]}
    return out


SHEETS = ("golden-pauli-4x4-sheet", "twin-pauli-4x4-sheet", "ibm-kingston-sheet", "ibm-marrakesh-sheet",
          "ibm-fez-sheet")
DEVICES = ("ibm_kingston", "ibm_marrakesh", "ibm_fez")
IBM = ROOT / "docs" / "records" / "2026-10-05" / "ibm"


def hardware():
    """Round 3's IBM results for the page, from the committed records by quantum_film.compare's own functions: each
    device's first set (the pre-registered runs) and its day of law runs pooled (the sheets), the predictions, the
    baselines, and the forbidden layouts (docs/prints/forbidden.json, tools/first_prints.py --forbidden)."""
    from quantum_film import compare

    def law_row(m):
        # six places, so that the page's own rounding to one place is not a second rounding of a rounded value
        return {"shots": m["shots"], "five_crystal_share": round(m["n_crystal"]["share"], 6),
                "forbidden_share": round(m["forbidden"]["share_of_n_crystal"], 6),
                "xeb": round(m["xeb"]["value"], 6),
                "xeb_se": None if m["xeb"].get("se") is None else round(m["xeb"]["se"], 6)}   # the law's is exact

    base = compare.baselines()
    out = {"law": {**law_row(base[0]["law"]), "X0X1": 0.375, "Y0Y1": 0.375},
           "emulator": {**law_row(base[1]["law"]),
                        **{k: round(v["value"], 6) for k, v in base[1]["coherence"].items()}},
           "twin": {"five_crystal_share": 1.0,
                    "forbidden_share": round(base[2]["law"]["forbidden"]["share_of_n_crystal"], 6), "xeb": 0.0,
                    "X0X1": 0.0, "Y0Y1": 0.0},
           "devices": []}
    for dev in DEVICES:
        recs = compare.device_runs([IBM / dev / "run"])
        (col,) = compare.run_columns(recs, expected_known_answer=[0, 1, 3, 7, 12])
        pred = compare.prediction_column(json.loads((IBM / dev / "prediction-backend.json").read_text(
            encoding="ascii")))
        day = [r for r in compare.device_runs([IBM / dev / "run", *sorted((IBM / dev).glob("sheet-*/run"))])
               if r["role"] == "law"]
        pooled = {}
        for r in day:
            for y, n in compare.run_counts(r).items():
                pooled[y] = pooled.get(y, 0) + n
        sheet = json.loads((PRINTS / f"ibm-{dev.split('_')[1]}-sheet.json").read_text(encoding="ascii"))
        kas = [json.loads(p.read_text(encoding="ascii"))["share"]
               for p in sorted((IBM / dev).glob("**/known-answer-verdict.json"))]
        out["devices"].append({
            "name": dev, "first_set": {**law_row(col["law"]),
                                       **{k: round(v["value"], 6) for k, v in col["coherence"].items()},
                                       **{f"{k}_se": round(v["se"], 6) for k, v in col["coherence"].items()},
                                       "known_answer": round(col["known_answer"][0]["share"], 6)},
            "prediction": {**law_row(pred["law"]),
                           **{k: round(v["value"], 6) for k, v in pred["coherence"].items()}},
            "day": {**law_row(compare.law_measures(pooled, compare.STOCK, day[0]["source"]["circuit_sha256"],
                                                   floor=False)),                # the page shows no pooled floor
                    "law_runs": len(day), "known_answers": len(kas), "known_answers_held": len(kas),
                    "known_answer_least": round(min(kas), 6), "sheet_columns": sheet["cells"][1],
                    "sheet_layouts": sheet["rolls"]["used"]}})
    # kingston's commonest forbidden shots, over its day, with how clumped each is
    forbidden = json.loads((PRINTS / "forbidden.json").read_text(encoding="ascii"))
    ys, ws, _den = compare.exact_law()
    banned = {Y for Y, w in zip(ys, ws, strict=True) if w == 0}
    tally = {}
    for r in compare.device_runs([IBM / "ibm_kingston" / "run", *sorted((IBM / "ibm_kingston").glob("sheet-*/run"))]):
        if r["role"] == "law":
            for y, n in compare.run_counts(r).items():
                if tuple(y) in banned:
                    tally[tuple(y)] = tally.get(tuple(y), 0) + n
    L = 4

    def nn(sites):
        s = set(sites)
        return sum(((r * L + (c + 1) % L) in s) + ((((r + 1) % L) * L + c) in s) for r, c in (divmod(p, L) for p in s))

    top = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    out["kingston_commonest_forbidden"] = [{"sites": list(y), "shots": n, "nn_pairs": nn(y)} for y, n in top]
    out["kingston_forbidden_shots"] = sum(tally.values())
    out["forbidden"] = {k: {**{f: v[f] for f in ("layouts", "forbidden_layouts", "forbidden_share", "share_of_cells",
                                                 "mean_nn_pairs_forbidden_laid", "mean_nn_pairs_allowed_laid",
                                                 "law_mean_nn_pairs", "forbidden_layouts_mean_nn_pairs",
                                                 "most_nn_pairs_the_law_allows")},
                            "side": json.loads((PRINTS / f"{k}.json").read_text(encoding="ascii"))["cells"][1]}
                        for k, v in forbidden.items()}
    out["forbidden_layouts"], out["layouts"] = sum(w == 0 for w in ws), len(ys)
    out["source"] = ("docs/records/2026-10-05/ibm by quantum_film.compare; docs/prints/forbidden.json by "
                     "tools/first_prints.py --forbidden (tools/site_data.py, hardware)")
    return out


def main():
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    (SITE / "img").mkdir(parents=True, exist_ok=True)
    for name, obj in (("atlas-shots", atlas_shots()), ("fields", fields()), ("structure", structure()),
                      ("hardware", hardware())):
        (SITE / "data" / f"{name}.json").write_text(json.dumps(obj, separators=(",", ":")) + "\n", encoding="ascii",
                                                   newline="\n")
        print(f"wrote site/data/{name}.json ({(SITE / 'data' / f'{name}.json').stat().st_size} bytes)")
    for n in NAMES:
        for suffix in ("print", "negative"):
            shutil.copyfile(PRINTS / f"{n}-{suffix}.png", SITE / "img" / f"{n}-{suffix}.png")
    for f in ("gallery.png", "structure.png"):
        shutil.copyfile(PRINTS / f, SITE / "img" / f)
    for n in SHEETS:                                   # round 3: the sheets, tinted and shot by shot
        for suffix in ("print", "forbidden", "layer"):
            shutil.copyfile(PRINTS / f"{n}-{suffix}.png", SITE / "img" / f"{n}-{suffix}.png")
    print(f"copied {len(NAMES) * 2 + 2 + len(SHEETS) * 3} images into site/img/")


if __name__ == "__main__":
    main()

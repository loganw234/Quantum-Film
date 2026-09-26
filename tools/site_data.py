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
  img/                    the first prints, copied from docs/prints/
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


def main():
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    (SITE / "img").mkdir(parents=True, exist_ok=True)
    for name, obj in (("atlas-shots", atlas_shots()), ("fields", fields()), ("structure", structure())):
        (SITE / "data" / f"{name}.json").write_text(json.dumps(obj, separators=(",", ":")) + "\n", encoding="ascii",
                                                   newline="\n")
        print(f"wrote site/data/{name}.json ({(SITE / 'data' / f'{name}.json').stat().st_size} bytes)")
    for n in NAMES:
        for suffix in ("print", "negative"):
            shutil.copyfile(PRINTS / f"{n}-{suffix}.png", SITE / "img" / f"{n}-{suffix}.png")
    for f in ("gallery.png", "structure.png"):
        shutil.copyfile(PRINTS / f, SITE / "img" / f)
    print(f"copied {len(NAMES) * 2 + 2} images into site/img/")


if __name__ == "__main__":
    main()

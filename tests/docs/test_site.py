"""The web demo shows the records, not a copy that drifted from them (site/, made by tools/site_data.py)."""
import base64
import json
import pathlib

from quantum_film import develop
from quantum_film.golden import binomial, fermi
from quantum_film.golden.uniform import stream

ROOT = pathlib.Path(__file__).resolve().parents[2]
SITE = ROOT / "site"


def data(name):
    return json.loads((SITE / "data" / f"{name}.json").read_text(encoding="ascii"))


def test_the_sites_atlas_shots_are_every_committed_shot_in_the_canonical_order():
    d = data("atlas-shots")
    files = sorted((ROOT / "docs" / "records").glob("*/p3/rolls-*/*.json"))
    recs = [json.loads(f.read_text(encoding="ascii")) for f in files]
    shots = develop.device_shots(recs)
    raw = base64.b64decode(d["masks_u16le_base64"])
    masks = [raw[2 * i] | (raw[2 * i + 1] << 8) for i in range(len(raw) // 2)]
    assert masks == [sum(1 << s for s in lay) for lay in shots]
    assert d["shots"] == len(shots) == sum(d["per_job"])
    assert d["jobs"] == sorted({r["source"]["job_id"] for r in recs})


def test_the_sites_crystal_fields_are_the_golden_rolls_they_name():
    d = data("fields")
    side, tiles = d["side"], d["tiles"]
    for name, lay in (("pauli", lambda s: fermi.sample(16, 8, s)), ("poisson", lambda s: binomial.sample(256, 25, s))):
        for i in (0, tiles * tiles - 1):                       # the first tile and the last
            ty, tx = divmod(i, tiles)
            want = sorted((ty * 16 + s // 16) * side + tx * 16 + s % 16 for s in lay(stream("roll", name, 1 + i)))
            got = sorted(s for s in d[name] if (s // side) // 16 == ty and (s % side) // 16 == tx)
            assert got == want, (name, i)
        assert len(d[name]) == tiles * tiles * 25


def test_the_sites_prints_and_structure_are_the_records_own():
    s = data("structure")
    for name, v in s.items():
        rec = json.loads((ROOT / "docs" / "prints" / f"{name}.json").read_text(encoding="ascii"))
        assert v["S"] == rec["structure_factor"]["S"] and v["print"] == rec["digests"]["print"]
        for suffix in ("print", "negative"):
            assert (SITE / "img" / f"{name}-{suffix}.png").read_bytes() == \
                (ROOT / "docs" / "prints" / f"{name}-{suffix}.png").read_bytes()
    for f in ("gallery.png", "structure.png", "poster.png"):
        assert (SITE / "img" / f).read_bytes() == (ROOT / "docs" / "prints" / f).read_bytes()

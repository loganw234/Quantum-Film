"""The web demo shows the records, not a copy that drifted from them (site/, made by tools/site_data.py)."""
import base64
import html.parser
import json
import pathlib
import struct

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


class Head(html.parser.HTMLParser):
    """A page's <title> and its meta tags by name or property; a tag given twice keeps both values."""

    def __init__(self, text):
        super().__init__()
        self.tags, self.title, self.in_title = {}, "", False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.in_title = tag == "title"
        if tag == "meta" and "content" in a:
            self.tags.setdefault(a.get("property") or a.get("name"), []).append(a["content"])

    def handle_endtag(self, tag):
        self.in_title = False

    def handle_data(self, text):
        self.title += text if self.in_title else ""


def test_the_link_preview_shows_the_poster_the_page_serves():
    """Discord and other link previews read the Open Graph tags: they must name a file the site serves."""
    head = Head((SITE / "index.html").read_text(encoding="utf-8"))
    one = {k: v[0] for k, v in head.tags.items() if len(v) == 1}
    base, image = one["og:url"], one["og:image"]
    assert base in (ROOT / "README.md").read_text(encoding="utf-8")        # the live link the README gives
    assert image.startswith(base)
    png = (SITE / image[len(base):]).read_bytes()
    assert png == (ROOT / "docs" / "prints" / "poster.png").read_bytes()
    assert (int(one["og:image:width"]), int(one["og:image:height"])) == struct.unpack(">II", png[16:24])
    assert one["og:title"] == head.title and one["og:description"] == one["description"]
    assert one["twitter:card"] == "summary_large_image"


SHEETS = ("golden-pauli-4x4-sheet", "twin-pauli-4x4-sheet", "ibm-kingston-sheet", "ibm-marrakesh-sheet",
          "ibm-fez-sheet")
IBM = ROOT / "docs" / "records" / "2026-10-05" / "ibm"


def test_the_sites_hardware_numbers_are_the_records_own():
    """The IBM results the page shows (site/data/hardware.json, tools/site_data.py), recomputed here from the
    committed runs by quantum_film.compare: each device's pre-registered set, its day of law runs pooled, kingston's
    commonest forbidden layouts, and the forbidden prints' numbers (docs/prints/forbidden.json)."""
    from quantum_film import compare
    d = data("hardware")
    six = lambda x: round(x, 6)  # noqa: E731
    assert [x["name"] for x in d["devices"]] == ["ibm_kingston", "ibm_marrakesh", "ibm_fez"]
    for dev in d["devices"]:
        recs = compare.device_runs([IBM / dev["name"] / "run"])
        law = next(r for r in recs if r["role"] == "law")
        m = compare.law_measures(compare.run_counts(law), floor=False)
        first = dev["first_set"]
        assert first["five_crystal_share"] == six(m["n_crystal"]["share"])
        assert first["forbidden_share"] == six(m["forbidden"]["share_of_n_crystal"])
        assert (first["xeb"], first["xeb_se"]) == (six(m["xeb"]["value"]), six(m["xeb"]["se"]))
        for r in (r for r in recs if r["role"] == "coherence"):
            c = compare.coherence(compare.run_counts(r), r["basis"])
            assert first[c["observable"]] == six(c["value"])
        day = [r for r in compare.device_runs([IBM / dev["name"] / "run", *sorted((IBM / dev["name"]).glob(
            "sheet-*/run"))]) if r["role"] == "law"]
        pooled = {}
        for r in day:
            for y, n in compare.run_counts(r).items():
                pooled[y] = pooled.get(y, 0) + n
        pm = compare.law_measures(pooled, floor=False)
        assert dev["day"]["law_runs"] == len(day) and dev["day"]["shots"] == sum(pooled.values())
        assert dev["day"]["forbidden_share"] == six(pm["forbidden"]["share_of_n_crystal"])
        assert dev["day"]["xeb"] == six(pm["xeb"]["value"])
    ys, ws, _den = compare.exact_law()
    banned = {Y for Y, w in zip(ys, ws, strict=True) if w == 0}
    tally = {}
    for r in compare.device_runs([IBM / "ibm_kingston" / "run", *sorted((IBM / "ibm_kingston").glob("sheet-*/run"))]):
        if r["role"] == "law":
            for y, n in compare.run_counts(r).items():
                if tuple(y) in banned:
                    tally[tuple(y)] = tally.get(tuple(y), 0) + n
    top = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))[:8]
    assert [(t["sites"], t["shots"]) for t in d["kingston_commonest_forbidden"]] == [(list(y), n) for y, n in top]
    assert d["kingston_commonest_forbidden"][0]["sites"] == [0, 1, 2, 3, 4]      # the page's caption names it
    assert d["kingston_forbidden_shots"] == sum(tally.values())
    assert (d["forbidden_layouts"], d["layouts"]) == (len(banned), len(ys))
    printed = json.loads((ROOT / "docs" / "prints" / "forbidden.json").read_text(encoding="ascii"))
    for name, v in d["forbidden"].items():
        assert {k: x for k, x in v.items() if k != "side"} == {k: printed[name][k] for k in v if k != "side"}


def test_the_sites_sheets_are_the_records_own_images():
    for name in SHEETS:
        for suffix in ("print", "forbidden", "layer"):
            assert (SITE / "img" / f"{name}-{suffix}.png").read_bytes() == \
                (ROOT / "docs" / "prints" / f"{name}-{suffix}.png").read_bytes(), (name, suffix)


def test_the_pages_typed_counts_of_ibm_jobs_and_law_shots_are_the_records():
    """index.html types two counts into its prose; both are held here to the committed runs."""
    from quantum_film import compare
    from quantum_film.ibm import runner
    lines = runner.lines_under(ROOT / "docs" / "records")
    law = [r for r in compare.device_runs([IBM]) if r["role"] == "law"]
    shots = sum(sum(n for _y, n in r["counts"]) for r in law)
    page = (SITE / "index.html").read_text(encoding="utf-8")
    assert f"({len(lines)} jobs, {shots:,} law shots)" in page, (len(lines), shots)

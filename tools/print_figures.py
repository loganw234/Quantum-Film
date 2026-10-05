#!/usr/bin/env python3
"""Figures for the first prints, made only from what docs/prints/ already holds.

    python tools/print_figures.py

Writes docs/prints/gallery.png (the prints side by side, labelled), docs/prints/hardware.png (round 3's three IBM
prints under the exact law's and Atlas's) and docs/prints/structure.png (each sheet's
structure factor, from its record). They illustrate; the claims are the records' digests and
docs/VALIDATION.md's figures, not these pixels, which move with the plotting library.
"""
if __name__ != "__main__":
    raise ImportError("this script writes files when it runs; run it, never import it (CLAUDE.md)")

import json  # noqa: E402
import pathlib  # noqa: E402

import numpy as np  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRINTS = ROOT / "docs" / "prints"
LABELS = {
    "atlas-pauli-4x4": "Pauli 4x4, every crystal laid by Atlas",
    "golden-pauli-4x4": "Pauli 4x4, the exact law's own rolls",
    "pauli": "Pauli 16x16: crystals repel",
    "poisson": "Poisson twin: placed at random",
    "trix": "TRI-X as atlas-film coats it",
    "ibm-kingston-pauli-4x4": "Pauli 4x4, laid by IBM's ibm_kingston",
    "ibm-marrakesh-pauli-4x4": "Pauli 4x4, laid by IBM's ibm_marrakesh",
    "ibm-fez-pauli-4x4": "Pauli 4x4, laid by IBM's ibm_fez",
    "golden-pauli-4x4-sheet": "the exact law's own rolls, for reference",
    "ibm-kingston-sheet": "ibm_kingston: a day's law shots",
    "ibm-marrakesh-sheet": "ibm_marrakesh: a day's law shots",
    "ibm-fez-sheet": "ibm_fez: a day's law shots",
}


def font(size):
    from PIL import ImageFont
    for name in ("DejaVuSans.ttf", "arial.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def panel(name, side):
    from PIL import Image, ImageDraw
    img = Image.open(PRINTS / f"{name}-print.png").convert("L").resize((side, side), Image.NEAREST)
    rec = json.loads((PRINTS / f"{name}.json").read_text(encoding="ascii"))
    h, w = rec["cells"]
    um = h * rec["pitch_um_decimal"]
    out = Image.new("L", (side, side + 64), 255)
    out.paste(img, (0, 0))
    d = ImageDraw.Draw(out)
    d.text((6, side + 6), LABELS[name], fill=0, font=font(17))
    d.text((6, side + 32), f"{h} x {w} crystal columns, {um:.0f} um of film", fill=90, font=font(14))
    return out


def gallery(rows=(("atlas-pauli-4x4", "golden-pauli-4x4"), ("pauli", "poisson", "trix")), name="gallery.png"):
    from PIL import Image
    side, gap = 360, 16
    panels = [[panel(n, side) for n in row] for row in rows]
    W = max(len(r) for r in panels) * (side + gap) + gap
    H = sum(p[0].height + gap for p in panels) + gap
    out = Image.new("L", (W, H), 255)
    y = gap
    for row in panels:
        x = (W - len(row) * (side + gap) + gap) // 2
        for p in row:
            out.paste(p, (x, y))
            x += side + gap
        y += row[0].height + gap
    out.save(PRINTS / name, optimize=True)


def structure():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8.0, 4.6), dpi=110)
    style = {"trix": ("#6b6b6b", "-"), "poisson": ("#c2452d", "-"), "pauli": ("#1f6fb4", "-"),
             "golden-pauli-4x4": ("#2a9d5c", "--"), "atlas-pauli-4x4": ("#2a9d5c", "-")}
    for name, (colour, ls) in style.items():
        rec = json.loads((PRINTS / f"{name}.json").read_text(encoding="ascii"))
        side = rec["cells"][0]
        S = np.array(rec["structure_factor"]["S"])
        k = np.arange(1, len(S) + 1) / side                 # cycles per crystal column
        ax.plot(k, S, ls, color=colour, lw=1.4, label=LABELS[name])
    for tile, colour in ((16, "#1f6fb4"), (4, "#2a9d5c")):
        ax.axvline(1 / tile, color=colour, lw=0.7, ls=":")
    ax.axhline(1.0, color="k", lw=0.6, ls=":")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("spatial frequency, cycles per crystal column (dotted: the tile scales, 1/16 and 1/4)")
    ax.set_ylabel("structure factor S(k) of the crystal count")
    ax.set_title("Grain the eye cannot see: Pauli's crystals repel, so its S(k) falls below film's")
    ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    fig.tight_layout()
    fig.savefig(PRINTS / "structure.png")


SHEETS = (("golden-pauli-4x4-sheet", "ibm-kingston-sheet"), ("ibm-marrakesh-sheet", "ibm-fez-sheet"))


def sheets(rows=SHEETS, name="sheets.png", scale=2):
    """The devices' sheets, and the exact law's at 256 columns for reference, at one scale (each crystal column
    `scale` pixels), so that they compare by eye at their true relative sizes: no panel is stretched to fit."""
    from PIL import Image, ImageDraw
    gap, foot = 24, 70
    grid = []
    for row in rows:
        cells = []
        for n in row:
            rec = json.loads((PRINTS / f"{n}.json").read_text(encoding="ascii"))
            h, w = rec["cells"]
            img = Image.open(PRINTS / f"{n}-print.png").convert("L").resize((w * scale, h * scale), Image.NEAREST)
            cells.append((n, rec, img))
        grid.append(cells)
    col_w = max(i.width for row in grid for _n, _r, i in row)
    row_h = max(i.height for row in grid for _n, _r, i in row) + foot
    W = max(len(row) for row in grid) * (col_w + gap) + gap
    H = len(grid) * (row_h + gap) + gap
    out = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(out)
    for ri, row in enumerate(grid):
        for ci, (n, rec, img) in enumerate(row):
            x, y = gap + ci * (col_w + gap), gap + ri * (row_h + gap)
            out.paste(img, (x, y))
            h, w = rec["cells"]
            used = rec["rolls"].get("used", h * w // 16 * rec["layers"])
            d.text((x, y + img.height + 8), LABELS[n], fill=0, font=font(20))
            d.text((x, y + img.height + 38), f"{w} x {h} crystal columns, {h * rec['pitch_um_decimal']:.0f} um of "
                   f"film, {used:,} layouts", fill=90, font=font(15))
    out.save(PRINTS / name, optimize=True)


FORBIDDEN = ("golden-pauli-4x4-sheet", "twin-pauli-4x4-sheet", "ibm-kingston-sheet", "ibm-marrakesh-sheet",
             "ibm-fez-sheet")
SHORT = {"golden-pauli-4x4-sheet": "the exact law", "twin-pauli-4x4-sheet": "the classical twin",
         "ibm-kingston-sheet": "ibm_kingston", "ibm-marrakesh-sheet": "ibm_marrakesh", "ibm-fez-sheet": "ibm_fez"}


def forbidden(name="forbidden.png", crop=128, zoom=4):
    """The crystals of the layouts the exact law forbids, in colour (tools/first_prints.py --forbidden). Top: each
    print, every crystal column tinted by the share of its crystals that came from forbidden layouts. Bottom: one
    layer of three of the sheets, shot by shot, `crop` cells square from its corner, each cell `zoom` pixels."""
    from PIL import Image, ImageDraw
    stats = json.loads((PRINTS / "forbidden.json").read_text(encoding="ascii"))
    gap, foot = 20, 66

    def cells(n, suffix):
        """The saved image at one pixel a crystal column: the files are scaled up by whole numbers to ~512 px."""
        h, w = json.loads((PRINTS / f"{n}.json").read_text(encoding="ascii"))["cells"]
        return Image.open(PRINTS / f"{n}-{suffix}.png").convert("RGB").resize((w, h), Image.NEAREST)

    tops = [(n, cells(n, "forbidden")) for n in FORBIDDEN]
    lows = [(n, cells(n, "layer").crop((0, 0, crop, crop)).resize((crop * zoom, crop * zoom), Image.NEAREST))
            for n in FORBIDDEN[:3]]
    W = max(sum(i.width for _n, i in tops) + gap * (len(tops) + 1), sum(i.width for _n, i in lows) + gap * 4)
    H = gap + max(i.height for _n, i in tops) + foot + gap + max(i.height for _n, i in lows) + foot + gap
    out = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(out)
    x, y = gap, gap
    for n, im in tops:
        out.paste(im, (x, y))
        st = stats[n]
        d.text((x, y + im.height + 6), SHORT[n], fill=(0, 0, 0), font=font(17))
        d.text((x, y + im.height + 30), f"{100 * st['forbidden_share']:.2f}% of layouts forbidden", fill=(90, 90, 90),
               font=font(13))
        x += im.width + gap
    y += max(i.height for _n, i in tops) + foot + gap
    x = gap
    for n, im in lows:
        out.paste(im, (x, y))
        d.text((x, y + im.height + 6), f"{SHORT[n]}: one layer, {crop} x {crop} cells", fill=(0, 0, 0), font=font(17))
        d.text((x, y + im.height + 30), "each 4 x 4 tile is one shot; forbidden shots in colour", fill=(90, 90, 90),
               font=font(13))
        x += im.width + gap
    out.save(PRINTS / name, optimize=True)


def main():
    gallery()
    # round 3: the three IBM devices' prints under the exact law's and Atlas's, each at its own size in film
    gallery((("golden-pauli-4x4", "atlas-pauli-4x4"),
             ("ibm-kingston-pauli-4x4", "ibm-marrakesh-pauli-4x4", "ibm-fez-pauli-4x4")), "hardware.png")
    written = ["gallery.png", "hardware.png", "structure.png"]
    if all((PRINTS / f"{n}.json").exists() for row in SHEETS for n in row):
        sheets()                                       # round 3's sheets, once all three are laid
        written.insert(2, "sheets.png")
    if (PRINTS / "forbidden.json").exists() and all(n in json.loads((PRINTS / "forbidden.json").read_text(
            encoding="ascii")) for n in FORBIDDEN):
        forbidden()                                    # their forbidden crystals, once all five are mapped
        written.insert(3, "forbidden.png")
    structure()
    for f in written:
        print(f"wrote docs/prints/{f} ({(PRINTS / f).stat().st_size} bytes)")


if __name__ == "__main__":
    main()

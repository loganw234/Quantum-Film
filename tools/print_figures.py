#!/usr/bin/env python3
"""Figures for the first prints, made only from what docs/prints/ already holds.

    python tools/print_figures.py

Writes docs/prints/gallery.png (the prints side by side, labelled) and docs/prints/structure.png (each sheet's
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


def gallery():
    from PIL import Image
    rows = [["atlas-pauli-4x4", "golden-pauli-4x4"], ["pauli", "poisson", "trix"]]
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
    out.save(PRINTS / "gallery.png", optimize=True)


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


def main():
    gallery()
    structure()
    for f in ("gallery.png", "structure.png"):
        print(f"wrote docs/prints/{f} ({(PRINTS / f).stat().st_size} bytes)")


if __name__ == "__main__":
    main()

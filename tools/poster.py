#!/usr/bin/env python3
"""The poster: three real prints on a strip of 35 mm film, over a field of real Pauli crystals: the shelf's law laid
by Moth's Atlas emulator, then by one of IBM's quantum computers, then classical TRI-X grain.

    python tools/poster.py

Writes docs/prints/poster.png (2400 x 3200) and a copy in site/img/. Every grain on it comes from a committed
record: the frames are docs/prints/'s prints, and the faint dots behind them are site/data/fields.json's golden
Pauli layer. The two shares it states are read from site/data/hardware.json (tools/site_data.py). Fonts are Windows'
Segoe UI and Consolas; elsewhere a similar font stands in.
"""
if __name__ != "__main__":
    raise ImportError("this script writes files when it runs; run it, never import it (CLAUDE.md)")

import json  # noqa: E402
import pathlib  # noqa: E402
import shutil  # noqa: E402

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRINTS = ROOT / "docs" / "prints"
W, H = 2400, 3200
BG, INK, DIM, AMBER, CYAN = (7, 8, 11), (242, 239, 232), (154, 151, 143), (240, 180, 84), (111, 211, 255)
FRAMES = [("atlas-pauli-4x4", "QUANTUM, EMULATED", "every crystal laid by", "Moth's Atlas: {atlas} shots"),
          ("ibm-kingston-sheet", "QUANTUM, ON A QPU", "every crystal laid by IBM's", "ibm_kingston: {kingston} shots"),
          ("trix", "CLASSICAL", "TRI-X as atlas-film", "coats it: random grain")]
INSET = 64, 6       # the IBM frame's inset: a corner of one layer of its sheet, cells across and pixels a cell


def font(names, size):
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


LIGHT = lambda s: font(["segoeuil.ttf", "DejaVuSans-ExtraLight.ttf", "DejaVuSans.ttf"], s)  # noqa: E731
REG = lambda s: font(["segoeui.ttf", "DejaVuSans.ttf"], s)  # noqa: E731
SEMI = lambda s: font(["seguisb.ttf", "DejaVuSans-Bold.ttf"], s)  # noqa: E731
MONO = lambda s: font(["consolab.ttf", "DejaVuSansMono-Bold.ttf"], s)  # noqa: E731


def spaced(d, xy, text, f, fill, spacing, anchor_center=True):
    widths = [d.textlength(c, font=f) for c in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x = xy[0] - total / 2 if anchor_center else xy[0]
    for c, w in zip(text, widths, strict=True):
        d.text((x, xy[1]), c, font=f, fill=fill)
        x += w + spacing


def main():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img, "RGBA")

    # the field: one golden Pauli layer, tiled faintly across the whole sheet
    fl = json.loads((ROOT / "site" / "data" / "fields.json").read_text(encoding="ascii"))
    side, step = fl["side"], 19.0
    for oy in range(0, int(H / (side * step)) + 1):
        for ox in range(0, int(W / (side * step)) + 1):
            for s in fl["pauli"]:
                x = (ox * side + s % side + 0.5) * step
                y = (oy * side + s // side + 0.5) * step
                if x < W and y < H:
                    d.ellipse((x - 3.2, y - 3.2, x + 3.2, y + 3.2), fill=CYAN + (38,))

    # the title
    spaced(d, (W / 2, 150), "QUANTUM FILM", LIGHT(168), INK, 46)
    sub = "Film grain laid by quantum computers, and fixed bit for bit"
    d.text((W / 2, 400), sub, font=REG(56), fill=AMBER, anchor="mm")

    # the strip
    fr, gap = 720, 56
    sx0, sx1 = W / 2 - fr / 2 - 150, W / 2 + fr / 2 + 150
    top = 470
    bottom = top + 3 * fr + 4 * gap
    d.rectangle((sx0, top, sx1, bottom), fill=(22, 19, 15))
    hole_w, hole_h, pitch = 54, 78, 118
    y = top + 30
    while y + hole_h < bottom - 20:
        for x in (sx0 + 48, sx1 - 48 - hole_w):
            d.rounded_rectangle((x, y, x + hole_w, y + hole_h), radius=10, fill=BG)
        y += pitch
    edge = MONO(30)
    hw = json.loads((ROOT / "site" / "data" / "hardware.json").read_text(encoding="ascii"))
    kingston = next(x for x in hw["devices"] if x["name"] == "ibm_kingston")
    atlas = json.loads((PRINTS / "atlas-pauli-4x4.json").read_text(encoding="ascii"))
    counts = {"atlas": f"{atlas['rolls']['used']:,}", "kingston": f"{kingston['day']['sheet_layouts']:,}"}
    for i, (name, kind, l1, l2) in enumerate(FRAMES):
        l2 = l2.format(**counts)
        fy = top + gap + i * (fr + gap)
        frame = Image.open(PRINTS / f"{name}-print.png").convert("RGB").resize((fr, fr), Image.NEAREST)
        img.paste(frame, (int(W / 2 - fr / 2), int(fy)))
        d.rectangle((W / 2 - fr / 2 - 3, fy - 3, W / 2 + fr / 2 + 3, fy + fr + 3), outline=(60, 52, 40), width=3)
        # edge code on the film, rotated along the strip
        code = f"  QUANTUM FILM  ▸ {i + 1}  {name.upper()}  "
        tw = int(d.textlength(code, font=edge)) + 10
        lab = Image.new("RGBA", (tw, 40), (0, 0, 0, 0))
        ImageDraw.Draw(lab).text((5, 2), code, font=edge, fill=AMBER + (210,))
        lab = lab.rotate(90, expand=True)
        img.paste(lab, (int(sx0 + 112), int(fy + fr / 2 - tw / 2)), lab)
        # the label beside the frame
        lx = sx0 - 60
        d.text((lx, fy + fr / 2 - 70), kind, font=SEMI(46), fill=CYAN if "QUANTUM" in kind else (240, 122, 90),
               anchor="rm")
        d.text((lx, fy + fr / 2), l1, font=REG(38), fill=INK, anchor="rm")
        d.text((lx, fy + fr / 2 + 50), l2, font=REG(38), fill=INK, anchor="rm")

    # the right margin: what the frames are
    rx = sx1 + 60
    notes = ["Each frame is a print", "developed with atlas-film", "on pinned arithmetic:", "the same bits on",
             "every machine."]
    for j, line in enumerate(notes):
        d.text((rx, top + gap + fr / 2 - 110 + j * 52), line, font=REG(38), fill=DIM)
    # beside the IBM frame: a corner of one layer of its sheet, shot by shot, the layouts the law forbids tinted
    # (tools/first_prints.py --forbidden), and their share beside random placement's
    n, z = INSET
    fy = top + 2 * gap + fr
    layer = Image.open(PRINTS / "ibm-kingston-sheet-layer.png").convert("RGB")
    if layer.size != (kingston["day"]["sheet_columns"],) * 2:
        raise SystemExit("the IBM layer view is not one pixel a cell of the sheet; the inset would misstate its scale")
    img.paste(layer.crop((0, 0, n, n)).resize((n * z, n * z), Image.NEAREST), (int(rx), int(fy)))
    d.rectangle((rx - 3, fy - 3, rx + n * z + 2, fy + n * z + 2), outline=(60, 52, 40), width=3)
    pct = lambda x: f"{100 * x:.1f}%"  # noqa: E731
    forb = ["A corner of one layer, shot", "by shot. Tinted: layouts the",
            f"law forbids. They are {pct(kingston['day']['forbidden_share'])}", "of ibm_kingston's five-crystal",
            f"shots; placed at random, {pct(hw['twin']['forbidden_share'])}."]
    for j, line in enumerate(forb):
        d.text((rx, fy + n * z + 34 + j * 50), line, font=REG(36), fill=DIM)

    # the foot
    d.text((W / 2, bottom + 110), "Moth Hack 2026", font=SEMI(50), fill=INK, anchor="mm")
    d.text((W / 2, bottom + 180), "Moth Atlas · IBM Quantum · atlas-film · cft-fp256",
           font=REG(40), fill=DIM, anchor="mm")
    d.text((W / 2, bottom + 240), "github.com/loganw234/Quantum-Film", font=REG(40), fill=AMBER, anchor="mm")

    out = PRINTS / "poster.png"
    img.save(out, optimize=True)
    (ROOT / "site" / "img").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out, ROOT / "site" / "img" / "poster.png")
    print(f"wrote docs/prints/poster.png ({out.stat().st_size} bytes) and site/img/poster.png")


if __name__ == "__main__":
    main()

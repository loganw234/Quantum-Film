"""Draw the prototype's three emulsions: crystals, then the same fields at print
scale, then their statistics. Reads proto/layouts.npz and proto/stats.json."""

if __name__ != "__main__":
    raise ImportError("this script does its work when it runs; run it, never import it (CLAUDE.md)")
import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter

HERE = pathlib.Path(__file__).resolve().parent / "proto"
L, CELL = 64, 8
lay = np.load(HERE / "layouts.npz")
stats = json.loads((HERE / "stats.json").read_text(encoding="utf-8"))
ORDER = [("fermion", "fermion: a determinantal point process"),
         ("poisson", "poisson: the classical reference"),
         ("speckle", "speckle: shots of a 12-qubit QFT circuit")]

tiles = []
for key, _title in ORDER:
    img = Image.new("L", (L * CELL, L * CELL), 236)
    d = ImageDraw.Draw(img)
    for s in lay[key]:
        x, y = divmod(int(s), L)
        cx, cy = x * CELL + CELL / 2, y * CELL + CELL / 2
        d.ellipse([cx - 3.1, cy - 3.1, cx + 3.1, cy + 3.1], fill=24)
    tiles.append(np.asarray(img, dtype=np.float64))

# Print scale: the same crystals seen through a Gaussian aperture of 1.6 cells.
# ONE grey scale for all three panels - scaled separately, a small variation
# is stretched to look like a large one, which is the thing being compared.
dens = [gaussian_filter(t, sigma=1.6 * CELL, mode="wrap") for t in tiles]
lo = min(float(d.min()) for d in dens)
hi = max(float(d.max()) for d in dens)
rms = [float(np.std(d)) for d in dens]      # grey levels, at this aperture

fig = plt.figure(figsize=(15, 13.2), dpi=110)
gs = fig.add_gridspec(3, 3, height_ratios=[1, 1, 0.78], hspace=0.28, wspace=0.12)
for col, ((key, title), tile, dd, s) in enumerate(zip(ORDER, tiles, dens, rms)):
    ax = fig.add_subplot(gs[0, col])
    ax.imshow(tile, cmap="gray", vmin=0, vmax=255, interpolation="nearest")
    ax.set_title(title, fontsize=11)
    ax.set_xticks([]); ax.set_yticks([])
    ax = fig.add_subplot(gs[1, col])
    ax.imshow(dd, cmap="gray", vmin=lo, vmax=hi, interpolation="bilinear")
    ax.set_title(f"print scale, shared grey scale: RMS {s:.2f}", fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])

colours = {"fermion": "#1f6fb4", "poisson": "#6b6b6b", "speckle": "#c2452d"}
ax = fig.add_subplot(gs[2, 0])
r = np.arange(1, 13)
for key, _ in ORDER:
    ax.plot(r, stats[key]["g_r"], "o-", ms=3.5, color=colours[key], label=key)
ax.axhline(1, color="k", lw=0.6, ls=":")
ax.set_xlabel("separation r (sites)"); ax.set_ylabel("pair correlation g(r)")
ax.legend(frameon=False, fontsize=9)
ax = fig.add_subplot(gs[2, 1])
k = np.arange(1, 17)
for key, _ in ORDER:
    ax.semilogy(k, stats[key]["S_k"], "o-", ms=3.5, color=colours[key], label=key)
ax.axhline(1, color="k", lw=0.6, ls=":")
ax.set_xlabel("|k| (units of 2π/L)"); ax.set_ylabel("structure factor S(k)")
ax = fig.add_subplot(gs[2, 2])
a = [1, 2, 3, 4, 6, 8, 12, 16]
for key, _ in ORDER:
    ax.loglog(a, stats[key]["var_over_mean"], "o-", ms=3.5, color=colours[key], label=key)
ax.axhline(1, color="k", lw=0.6, ls=":")
ax.set_xlabel("window side (sites)"); ax.set_ylabel("count variance / mean")
fig.suptitle("Three emulsions, 512 crystals on 64×64 sites, six layouts each for the statistics "
             "(exploratory prototype, 2026-09-25)", fontsize=12)
out = HERE / "three-emulsions.png"
fig.savefig(out, bbox_inches="tight")
print(out)

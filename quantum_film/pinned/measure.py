"""The pinned path's measurements: the hand-off rate, the precision demonstration, the timings and the control.

    python -m quantum_film.pinned.measure                                    # both stocks, the default counts
    python -m quantum_film.pinned.measure --stock pauli --first 301 --streams 2000 --formats fp32 --only-streams

For each stream ("roll", stock, seed), seed = first .. first + streams - 1:
  - the authority's roll and its draw order (quantum_film.golden.fermi, traced);
  - the certified roll: equal to the authority's? handed off? how far its closest draw cleared its boundaries,
    against how wide its enclosures were;
  - the plain chain (certification off) in each of --formats: does it part from the authority, at which draw,
    by how many crystals at the end, and is its layout one the law forbids;
  - timings, interleaved on the same streams: the authority, the certified roll, the plain binary64 chain.
Then, per stock: the negative control on --controls planted streams; the cascade (a plant at an early, a middle
and the last draw inside each format's own error); and a ladder of planted distances on one boundary.

Nothing here is a gate: tests/pinned holds the gates. This prints what they measure at scale. Machine load is not
measured here: say what it was beside any timing taken from it.
"""
import argparse
import statistics
import time
from fractions import Fraction

from ..golden import fermi as golden
from ..golden.uniform import stream
from ..stocks import params
from . import cft, control, sampler

FORMATS = ("fp32", "fp64", "fp128")
LADDER = [Fraction(1, 10 ** k) for k in (2, 4, 6, 7, 8, 10, 12, 14, 15, 16, 17, 20, 25, 30, 32, 33, 34, 36)]


def forbidden(L, r2, crystals):
    """Whether the law gives this layout probability zero: det(K_Y) below 2^-200 at 256 bits (the authority's
    own probability; a forbidden layout's is zero up to the authority's rounding)."""
    return golden.probability(golden.orbitals(L, r2), crystals) < golden.mpf(2) ** -200


def stock_run(stock, first, streams, formats=FORMATS):
    law = params(stock)
    L, r2 = law["L"], law["fermi_r2"]
    out = {"stock": stock, "first": first, "streams": streams, "formats": formats, "mismatch": [], "handoffs": [],
           "clear": [], "width": [], "parted": {f: [] for f in formats}, "t_golden": [], "t_pinned": [],
           "t_fp64": []}
    sampler.enclosure(L, r2)
    for f in formats:
        sampler.basis(L, r2, sampler.FORMATS[f])
    for seed in range(first, first + streams):
        s = stream("roll", stock, seed)
        t4 = time.perf_counter()
        crystals, order, _seen = control.golden_draws(L, r2, s)
        t5 = time.perf_counter()
        t0 = time.perf_counter()
        r = sampler.roll(L, r2, s)
        t1 = time.perf_counter()
        out["t_golden"].append(t5 - t4)
        out["t_pinned"].append(t1 - t0)
        if r.crystals != crystals:
            out["mismatch"].append(seed)
        if r.handed_off:
            out["handoffs"].append((seed, r.draw, r.reason))
        for c, w in r.slack:
            out["clear"].append(float(c) / float(w) if w > 0 else float("inf"))
            out["width"].append(float(w))
        for f in formats:
            t2 = time.perf_counter()
            p = sampler.roll(L, r2, s, certify=False, fmt=f)
            t3 = time.perf_counter()
            if f == "fp64":
                out["t_fp64"].append(t3 - t2)
            j = control._first_parting(p.draws, order)
            if j is not None:
                out["parted"][f].append((seed, j, len(set(p.crystals) - set(crystals)),
                                         forbidden(L, r2, p.crystals)))
    return out


def report_stock(o):
    n, a, b = o["streams"], o["first"], o["first"] + o["streams"] - 1
    lines = [f"### {o['stock']}: {n} streams (\"roll\", \"{o['stock']}\", {a}..{b})", ""]
    lines.append(f"- certified roll equal to the authority's: {n - len(o['mismatch'])} of {n}"
                 + (f"; MISMATCH at seeds {o['mismatch']}" if o["mismatch"] else ""))
    lines.append(f"- hand-offs: {len(o['handoffs'])} of {n}" + (f" {o['handoffs']}" if o["handoffs"] else ""))
    if o["width"]:
        lines.append(f"- certified draws: {len(o['width'])}; widest enclosure {max(o['width']):.3g}; "
                     f"tightest clearance {min(o['clear']):.3g} enclosure widths")
    lines += ["", "| format | rolls parted from the authority | at draw (seed: draw) | crystals different "
              "at the end | layouts the law forbids |", "|---|---|---|---|---|"]
    for f in o["formats"]:
        ps = o["parted"][f]
        more = " ..." if len(ps) > 12 else ""
        where = ", ".join(f"{s}: {j}" for s, j, _, _ in ps[:12]) + more
        diff = ", ".join(str(d) for _, _, d, _ in ps[:12]) + more
        lines.append(f"| {f} | {len(ps)} of {n} | {where or '-'} | {diff or '-'} | "
                     f"{sum(1 for *_, z in ps if z)} of {len(ps)} |")
    tg, tp, tf = o["t_golden"], o["t_pinned"], o["t_fp64"]
    lines += ["", "| roll | median ms | mean ms | rolls timed |", "|---|---|---|---|",
              f"| authority (golden, 256 bits, traced) | {statistics.median(tg) * 1e3:.1f} | "
              f"{statistics.mean(tg) * 1e3:.1f} | {len(tg)} |",
              f"| pinned, certified (binary64) | {statistics.median(tp) * 1e3:.1f} | "
              f"{statistics.mean(tp) * 1e3:.1f} | {len(tp)} |"]
    if tf:
        lines.append(f"| plain binary64 chain, no certificate | {statistics.median(tf) * 1e3:.1f} | "
                     f"{statistics.mean(tf) * 1e3:.1f} | {len(tf)} |")
    return lines + [""]


def report_control(stock, seeds):
    law = params(stock)
    L, r2 = law["L"], law["fermi_r2"]
    lines = [f"### the negative control, {stock}", "",
             "| seed | planted draw, boundary | distance (relative) | binary64's boundary error | enclosure width "
             "(target; boundary) | hand-off removed | shipped |", "|---|---|---|---|---|---|---|"]
    for seed in seeds:
        c = control.control(L, r2, stream("roll", stock, seed))
        pl, w = c["plant"], c["enclosure_widths"]
        off = "DISAGREES" if c["without_handoff_disagrees"] else "agrees (THE CONTROL FAILED)"
        on = ("agrees, handed off at draw %s" % c["with_handoff"].draw) if c["with_handoff_agrees"] \
            else "DISAGREES (A DEFECT)"
        lines.append(f"| {seed} | {pl.draw}, {pl.boundary} | {float(pl.distance):.3g} "
                     f"({float(pl.distance / pl.boundary_value):.3g}) | {float(pl.format_error):.3g} | "
                     f"{w['target']:.3g}; {w['boundary']:.3g} | {off} | {on} |")
    return lines + [""]


def report_cascade(stock, seed, draws):
    law = params(stock)
    L, r2 = law["L"], law["fermi_r2"]
    lines = [f"### the cascade, {stock}, seed {seed}: a target planted inside one format's own error", "",
             "| planted in | at draw | distance (relative) | fp32 | fp64 | fp128 | certified |",
             "|---|---|---|---|---|---|---|"]

    def cell(row, f):
        d, extra, _ = row[f]
        return "=" if d is None else f"parts at {d}; {extra} crystal{'s differ' if extra != 1 else ' differs'}"

    for fmt in FORMATS:
        for j in draws:
            try:
                row = control.cascade(L, r2, stream("roll", stock, seed), j, fmt)
            except ValueError as e:
                lines.append(f"| {fmt} | {j} | no plant: {e} | | | | |")
                continue
            pl = row["plant"]
            ok, handed, at = row["certified"]
            cert = ("=" if ok else "DIFFERS (A DEFECT)") + (f", handed off at {at}" if handed else "")
            lines.append(f"| {fmt} | {j} | {float(pl.distance / pl.boundary_value):.2g} | {cell(row, 'fp32')} | "
                         f"{cell(row, 'fp64')} | {cell(row, 'fp128')} | {cert} |")
    return lines + ["", "(= : the same roll as the authority)", ""]


def report_ladder(stock, seed, distances):
    law = params(stock)
    rows = control.ladder(law["L"], law["fermi_r2"], stream("roll", stock, seed), distances)
    lines = [f"### planted distances, {stock}, seed {seed}, last draw", "",
             "| relative distance | side | fp32 | fp64 | fp128 | certified |", "|---|---|---|---|---|---|"]

    def mark(x, a):
        return "refused" if x == "refused" else ("=" if x == a else "PARTS")

    for r in rows:
        a = r["authority"]
        cert = mark(r["certified"], a) + (" (handed off)" if r["handed_off"] else "")
        lines.append(f"| {float(r['distance']):.0e} | {'+' if r['side'] > 0 else '-'} | {mark(r['fp32'], a)} | "
                     f"{mark(r['fp64'], a)} | {mark(r['fp128'], a)} | {cert} |")
    return lines + ["", "(= : the same roll as the authority; PARTS : a different roll)", ""]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stock", action="append", help="pauli and/or pauli-4x4 (default both)")
    ap.add_argument("--first", type=int, default=1, help="the first seed (default 1)")
    ap.add_argument("--streams", type=int, default=None, help="streams per stock (default 2000 / 300)")
    ap.add_argument("--formats", default=",".join(FORMATS), help="plain-chain formats to compare (default all)")
    ap.add_argument("--controls", type=int, default=3, help="planted control streams per stock")
    ap.add_argument("--only-streams", action="store_true", help="skip the control, the cascade and the ladder")
    a = ap.parse_args(argv)
    path, sha, abi = cft.identity()
    print(f"libcft {abi} at {path}, sha256 {sha}")
    print("TAU = 2^-200; certificate: binary64, directed rounding\n")
    formats = tuple(f for f in a.formats.split(",") if f)
    for stock in a.stock or ["pauli-4x4", "pauli"]:
        n = a.streams or (2000 if stock == "pauli-4x4" else 300)
        print("\n".join(report_stock(stock_run(stock, a.first, n, formats))), flush=True)
        if a.only_streams:
            continue
        print("\n".join(report_control(stock, range(1, a.controls + 1))), flush=True)
        N = params(stock)["N"]
        print("\n".join(report_cascade(stock, 1, sorted({1, N // 2, N - 1}))), flush=True)
        print("\n".join(report_ladder(stock, 1, LADDER)), flush=True)
    print(f"counts: {sampler.COUNTS}")


if __name__ == "__main__":
    main()

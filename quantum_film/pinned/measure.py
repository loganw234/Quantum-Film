"""The pinned path's measurements: the hand-off rate, the precision table, the timings and the control.

    python -m quantum_film.pinned.measure                          # both stocks, the default counts
    python -m quantum_film.pinned.measure --stock pauli-4x4 --streams 500

For each stream ("roll", stock, seed), seed = 1..streams:
  - the authority's roll and its draw order (quantum_film.golden.fermi, traced);
  - the certified roll: equal to the authority's? handed off? how far its closest draw cleared its
    boundaries, against how wide its enclosures were;
  - the plain chain (certification off) at binary32, binary64 and binary128: does it part from the
    authority, at which draw, and by how many crystals by the end of the roll;
  - timings, interleaved on the same streams: the authority, the certified roll, the plain binary64 chain.
Then the negative control on `--controls` streams per stock, and a ladder of planted distances.

Nothing here is a gate: tests/pinned holds the gates. This prints what they measure at scale.
"""
import argparse
import statistics
import time
from fractions import Fraction

from ..golden import fermi as golden
from ..golden.uniform import stream
from ..stocks import params
from . import cft, control, sampler


def _first_parting(a, b):
    return next((j for j, (x, y) in enumerate(zip(a, b, strict=True)) if x != y), None)


def forbidden(L, r2, crystals):
    """Whether the law gives this layout probability zero: det(K_Y) below 2^-200 at 256 bits (the authority's
    own probability; a forbidden layout's is zero up to the authority's rounding)."""
    return golden.probability(golden.orbitals(L, r2), crystals) < golden.mpf(2) ** -200


def stock_run(stock, streams, time_every=1):
    law = params(stock)
    L, r2 = law["L"], law["fermi_r2"]
    out = {"stock": stock, "streams": streams, "mismatch": [], "handoffs": [], "clear": [], "width": [],
           "parted": {f: [] for f in ("fp32", "fp64", "fp128")}, "t_golden": [], "t_pinned": [], "t_fp64": []}
    sampler.enclosure(L, r2)
    for f in ("fp32", "fp64", "fp128"):
        sampler.basis(L, r2, sampler.FORMATS[f])
    for seed in range(1, streams + 1):
        s = stream("roll", stock, seed)
        crystals, order, _seen = control.golden_draws(L, r2, s)
        t0 = time.perf_counter()
        r = sampler.roll(L, r2, s)
        t1 = time.perf_counter()
        if r.crystals != crystals:
            out["mismatch"].append(seed)
        if r.handed_off:
            out["handoffs"].append((seed, r.draw, r.reason))
        for c, w in r.slack:
            out["clear"].append(c / w if w > 0 else float("inf"))
            out["width"].append(w)
        for f in ("fp32", "fp64", "fp128"):
            t2 = time.perf_counter()
            p = sampler.roll(L, r2, s, certify=False, fmt=f)
            t3 = time.perf_counter()
            if f == "fp64":
                out["t_fp64"].append(t3 - t2)
            j = _first_parting(p.draws, order)
            if j is not None:
                out["parted"][f].append((seed, j, len(set(p.crystals) - set(crystals)),
                                         forbidden(L, r2, p.crystals)))
        if seed % time_every == 0:
            t4 = time.perf_counter()
            golden.sample(L, r2, s)
            t5 = time.perf_counter()
            out["t_golden"].append(t5 - t4)
            out["t_pinned"].append(t1 - t0)
    return out


def report_stock(o):
    n = o["streams"]
    lines = [f"### {o['stock']}: {n} streams (\"roll\", \"{o['stock']}\", 1..{n})", ""]
    lines.append(f"- certified roll equal to the authority's: {n - len(o['mismatch'])} of {n}"
                 + (f"; MISMATCH at seeds {o['mismatch']}" if o["mismatch"] else ""))
    lines.append(f"- hand-offs: {len(o['handoffs'])} of {n}" + (f" {o['handoffs']}" if o["handoffs"] else ""))
    if o["width"]:
        lines.append(f"- certified draws: {len(o['width'])}; widest enclosure {max(o['width']):.3g}; "
                     f"tightest clearance {min(o['clear']):.3g} enclosure widths")
    lines += ["", "| format | rolls parted from the authority | at draw (seed: draw) | crystals different "
              "at the end | layouts the law forbids |", "|---|---|---|---|---|"]
    for f in ("fp32", "fp64", "fp128"):
        ps = o["parted"][f]
        more = " ..." if len(ps) > 12 else ""
        where = ", ".join(f"{s}: {j}" for s, j, _, _ in ps[:12]) + more
        diff = ", ".join(str(d) for _, _, d, _ in ps[:12]) + more
        lines.append(f"| {f} | {len(ps)} of {n} | {where or '-'} | {diff or '-'} | "
                     f"{sum(1 for *_, z in ps if z)} of {len(ps)} |")
    tg, tp, tf = o["t_golden"], o["t_pinned"], o["t_fp64"]
    lines += ["", "| roll | median ms | mean ms | rolls timed |", "|---|---|---|---|",
              f"| authority (golden, 256 bits) | {statistics.median(tg) * 1e3:.1f} | "
              f"{statistics.mean(tg) * 1e3:.1f} | {len(tg)} |",
              f"| pinned, certified (binary64) | {statistics.median(tp) * 1e3:.1f} | "
              f"{statistics.mean(tp) * 1e3:.1f} | {len(tp)} |",
              f"| plain binary64 chain, no certificate | {statistics.median(tf) * 1e3:.1f} | "
              f"{statistics.mean(tf) * 1e3:.1f} | {len(tf)} |", ""]
    return lines


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
                     f"({float(pl.distance / pl.boundary_value):.3g}) | {float(pl.float_error):.3g} | "
                     f"{w['target']:.3g}; {w['boundary']:.3g} | {off} | {on} |")
    return lines + [""]


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
    ap.add_argument("--streams", type=int, default=None, help="streams per stock (default 2000 / 300)")
    ap.add_argument("--controls", type=int, default=3, help="planted control streams per stock")
    ap.add_argument("--time-every", type=int, default=1, help="time the authority on every k-th stream")
    a = ap.parse_args(argv)
    path, sha, abi = cft.identity()
    print(f"libcft {abi} at {path}, sha256 {sha}")
    print("TAU = 2^-200; certificate: binary64, directed rounding\n")
    for stock in a.stock or ["pauli-4x4", "pauli"]:
        n = a.streams or (2000 if stock == "pauli-4x4" else 300)
        print("\n".join(report_stock(stock_run(stock, n, a.time_every))))
        print("\n".join(report_control(stock, range(1, a.controls + 1))))
        print("\n".join(report_ladder(stock, 1, [Fraction(1, 10 ** k) for k in (8, 10, 12, 13, 14, 15, 16)])))
    print(f"counts: {sampler.COUNTS}")


if __name__ == "__main__":
    main()

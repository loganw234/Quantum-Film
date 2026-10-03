"""The comparison (round 3): hardware shots against the exact law, Atlas's emulator and the classical twin.

It MEASURES; it never gates. Hardware will not lay the exact law: noise leaks crystals and lands shots on layouts
the law forbids. So every function here is a measure of counts, written and tested before any hardware data exists,
and the lead reports every measure whatever it shows (docs/ROUND3.md, P2). Nothing here passes or fails a run.

THE INPUTS
- Counts are {layout: shots}, a layout being the sorted tuple of the sites that hold a crystal (the qubits that
  read 1). Read from a device run (fixer.RUN_FORMAT), they are its `counts`, whatever crystal count each has.
- A hardware column takes `qpu` device runs only, and refuses any other kind by name; a simulator's run may appear
  in a table only under its own label (`run_column`). Every record must first pass `fixer.check`.
- The emulator is Atlas's 24,576 shots: the device rolls under docs/records/2026-09-25/p3 and
  docs/records/2026-09-26/p3, expanded in develop.device_shots' canonical order.
- The twin is five distinct sites of 16, uniformly: each of the 4,368 layouts has 1/4,368, and
  golden.binomial.sample(16, 5, stream) samples it.

THE LAW, EXACTLY. pauli-4x4's kernel is K = A / 16 with A an integer matrix, because on a 4 x 4 torus every
cos(2 pi m / 4) is 0 or +-1. So each det(K_Y) is an integer over 16^5; on this tile it is 0, 1, 4 or 9 over 4,096
(`exact_law`, by fraction-free elimination). tests/compare/test_compare_law.py holds A / 16 to the authority's own
kernel (quantum_film.golden.fermi, 256 bits), the weights to pauli_tile.law_of's det(K_Y), and the zeros to its
1,360 forbidden layouts. A denominator that is a power of two makes the perfect sampler below exact.

THE MEASURES OF A LAW RUN (`law_measures`); N is the stock's crystal count (5), D the number of N-site layouts.
- crystals per shot: shots per crystal count, 0 to 16.
- the N-crystal share: the fraction of shots holding exactly N crystals.
- the forbidden share: among the N-crystal shots, the fraction on layouts the law forbids (det(K_Y) = 0). In law
  it is 0; for the twin it is 1,360 / 4,368 = 85 / 273.
- the total variation distance, TVD = (1/2) sum over the D layouts of |c_Y / n - P(Y)|, c_Y the N-crystal shots
  on Y and n their number. Exact: a rational, computed in integers. It comes with THE FLOOR, a perfect sampler's
  TVD at the same n (`tvd_floor`): FLOOR_REPLICAS replicas, replica r drawing n layouts from the exact law with
  the golden uniforms of stream("compare-floor", stock, n, r), draw i taking uniform i: target = floor(u * 4,096),
  and the layout whose interval of the cumulative integer weights holds the target. No rounding anywhere; the
  replicas' TVDs are exact rationals. Stated: their mean, and the FLOOR_PERCENTILE-th percentile by nearest rank
  (the value at rank ceil(0.95 * 200) = 190 of 200, ascending).
- the linear cross-entropy fidelity over the D layouts,
      F = (mean over the N-crystal shots of P(Y) - 1/D) / (sum over Y of P(Y)^2 - 1/D),
  so that the law scores 1 in expectation, the twin 0, and a mixture eps * law + (1 - eps) * twin scores eps.
  Exact as a rational. Its standard error is the sample standard deviation of P(Y) over the N-crystal shots
  (divisor n - 1), over sqrt(n), over the same normaliser.
- one-site and pair z, on all shots and on the N-crystal shots alone: pauli_tile.score itself, so the definitions
  are round 1's (z = (measured - exact) / binomial standard error, against the authority's kernel).
- the nearest-neighbour pair correlation: on the periodic 4 x 4 tile, for each of its 32 nearest-neighbour pairs,
  P(both sites hold a crystal) over the product of the two sites' densities, all three measured in the same
  shots; then the mean over the 32 pairs. Exactly 16/25 in law (K_ii K_jj - K_ij^2 = 1/16 over (5/16)^2) and
  64/75 for the twin (1/12 over (5/16)^2).

THE COHERENCE RUNS (`coherence`): a run whose basis reads exactly two qubits out of Z, in the same letter, gives
<P_a P_b>: the mean of +1 when the two bits agree and -1 when they differ, with its binomial standard error
sqrt((1 - mean^2) / shots). For the law circuit both <X0X1> and <Y0Y1> are +0.375 (`coherence_law`, the project's
own simulator on the committed QASM); a classical mixture with the same layouts gives exactly 0.

THE PRINT RULE (`print_layouts`, `print_geometry`): a hardware print is laid from the qpu law runs' shots with
exactly N crystals, in canonical order (by job, then by layout, each repeated its shots), in square tiles at
least the honesty floor deep (develop.pitch_um), the shots left over counted.

DETERMINISM. Everything here is a function of its inputs. Every random draw (the floor, the twin sample, the coin
of a classical mixture read in X) is a golden uniform: SHA-256 of a named stream, so the same on every machine and
under every numpy version; no numpy random generator is used. numpy does exact integer work here (cumulative
sums, searchsorted, bincount, integer sums); the z values are pauli_tile.score's float64 arithmetic.
"""
import functools
import hashlib
import itertools
import json
import math
import pathlib
import sys
from fractions import Fraction

import numpy as np

from . import develop, fixer
from .atlas import pauli_tile
from .circuits import givens_line
from .golden import binomial
from .golden.uniform import DOMAIN, stream
from .ibm import decode as ibm_decode
from .stocks import fermi_disc, params

ROOT = pathlib.Path(__file__).resolve().parent.parent
STOCK = "pauli-4x4"
SOURCE_CIRCUIT = "ed767c01bd4b851d08993da80f715676e345fc95a10f3bda05400f738e400b36"   # the shelf's law, as run
SOURCE_QASM = "docs/records/2026-09-25/p3/circuit-ed767c01bd4b851d.qasm"
EMULATOR_DIRS = ("docs/records/2026-09-25/p3", "docs/records/2026-09-26/p3")
EMULATOR_SHOTS = 24576
FLOOR_REPLICAS = 200
FLOOR_PERCENTILE = 95
COHERENCE_LAW = {"X0X1": 0.375, "Y0Y1": 0.375}      # what coherence_law gives; held to it by a test, never assumed
# cos(2 pi m / L) for m = 0 .. L - 1, for the tiles where every one is an integer.
_INTEGER_COS = {1: (1,), 2: (1, -1), 4: (1, 0, -1, 0)}


# ---------------------------------------------------------------- the law, exactly


def _det(rows):
    """The determinant of an integer matrix, exactly (Bareiss's fraction-free elimination)."""
    m = [list(r) for r in rows]
    n, sign, prev = len(m), 1, 1
    for k in range(n - 1):
        if m[k][k] == 0:
            swap = next((r for r in range(k + 1, n) if m[r][k] != 0), None)
            if swap is None:
                return 0
            m[k], m[swap] = m[swap], m[k]
            sign = -sign
        for i in range(k + 1, n):
            for j in range(k + 1, n):
                m[i][j] = (m[i][j] * m[k][k] - m[i][k] * m[k][j]) // prev
        prev = m[k][k]
    return sign * m[n - 1][n - 1]


@functools.lru_cache(maxsize=4)
def integer_kernel(stock=STOCK):
    """A = M * K as integers: K(x, y) = (1/M) sum over the disc of cos(2 pi k.(x - y) / L), site = x * L + y."""
    law = params(stock)
    if law["family"] != "determinantal" or law["L"] not in _INTEGER_COS:
        raise LookupError(f"{stock!r}: the law is exact here only for a determinantal stock on a tile where every "
                          f"cos(2 pi m / L) is an integer (L in {sorted(_INTEGER_COS)})")
    L, M, cos = law["L"], law["M"], _INTEGER_COS[law["L"]]
    disc = fermi_disc(L, law["fermi_r2"])
    sites = [divmod(s, L) for s in range(M)]
    return tuple(tuple(sum(cos[(kx * (xi - xj) + ky * (yi - yj)) % L] for kx, ky in disc) for xj, yj in sites)
                 for xi, yi in sites)


@functools.lru_cache(maxsize=4)
def exact_law(stock=STOCK):
    """(layouts, weights, denominator): every N-site layout in itertools.combinations order, and P(Y) =
    weight / denominator exactly, the fraction in lowest terms over the whole table."""
    law = params(stock)
    M, N = law["M"], law["N"]
    A = integer_kernel(stock)
    layouts = tuple(itertools.combinations(range(M), N))
    dets = [_det([[A[i][j] for j in Y] for i in Y]) for Y in layouts]
    scale = M ** N
    if min(dets) < 0 or sum(dets) != scale:
        raise ArithmeticError(f"{stock}: the minors are not a projection kernel's (sum {sum(dets)} where "
                              f"{scale}, least {min(dets)})")
    g = math.gcd(scale, *dets)
    return layouts, tuple(d // g for d in dets), scale // g


@functools.lru_cache(maxsize=4)
def _law_index(stock=STOCK):
    layouts, weights, den = exact_law(stock)
    return {Y: i for i, Y in enumerate(layouts)}


def probability(layout, stock=STOCK):
    """P(Y) under the law, exactly; 0 for a layout without N crystals."""
    layouts, weights, den = exact_law(stock)
    i = _law_index(stock).get(tuple(layout))
    return Fraction(0) if i is None else Fraction(weights[i], den)


# ---------------------------------------------------------------- golden draws


def uniform_words(parts, count):
    """The first `count` golden uniforms of stream(*parts) as 64-bit integers: golden.uniform.uniform(s, i) is
    word i / 2^64 exactly (tests hold the two together). A numpy uint64 array."""
    head = hashlib.sha256(DOMAIN + b"|" + stream(*parts) + b"|")
    buf = bytearray()
    for i in range(count):
        h = head.copy()
        h.update(b"%d" % i)
        buf += h.digest()[:8]
    return np.frombuffer(bytes(buf), dtype=">u8").astype(np.uint64)


def _bits(stock):
    den = exact_law(stock)[2]
    bits = den.bit_length() - 1
    if den != 1 << bits:
        raise ArithmeticError(f"{stock}: the law's denominator {den} is not a power of two, so floor(u * den) "
                              "from a 64-bit uniform would not be exactly uniform")
    return bits


def pick(targets, stock=STOCK):
    """Layout indices for integer targets in [0, den): the layout whose interval [cum_(i-1), cum_i) of the
    cumulative weights holds the target. A layout of weight 0 has an empty interval and is never picked."""
    cum = np.cumsum(np.array(exact_law(stock)[1], dtype=np.int64))
    return np.searchsorted(cum, np.asarray(targets, dtype=np.int64), side="right")


def law_draws(n, parts, stock=STOCK):
    """n layouts drawn from the exact law, as indices into exact_law's layouts: draw i takes uniform i of
    stream(*parts), target = floor(u * den) (the top bits of its 64-bit word, den being a power of two), and
    `pick`."""
    bits = _bits(stock)
    return pick((uniform_words(parts, n) >> np.uint64(64 - bits)).astype(np.int64), stock)


def law_sample(n, parts, stock=STOCK):
    """{layout: shots} for n exact draws from the law (a perfect sampler)."""
    layouts = exact_law(stock)[0]
    c = np.bincount(law_draws(n, parts, stock), minlength=len(layouts))
    return {layouts[i]: int(c[i]) for i in np.flatnonzero(c)}


def twin_sample(n, parts, stock=STOCK):
    """{layout: shots}: n shots of the twin, shot i laid by golden.binomial.sample(M, N, stream(*parts, i))."""
    law = params(stock)
    out = {}
    for i in range(n):
        Y = tuple(binomial.sample(law["M"], law["N"], stream(*parts, i)))
        out[Y] = out.get(Y, 0) + 1
    return out


# ---------------------------------------------------------------- the floor


def _tvd_exact(c, n, stock=STOCK):
    """(1/2) sum |c_Y / n - P(Y)| exactly, c an int64 array of N-crystal shots per layout (exact_law's order)."""
    layouts, weights, den = exact_law(stock)
    W = np.array(weights, dtype=np.int64)
    return Fraction(int(np.abs(c.astype(np.int64) * den - n * W).sum()), 2 * n * den)


def floor_replicas(n, stock=STOCK, replicas=FLOOR_REPLICAS):
    """The perfect sampler's TVDs at n shots, exact and ascending: replica r is n exact draws from the law on
    stream("compare-floor", stock, n, r)."""
    for name, v in (("shots", n), ("replicas", replicas)):
        if not (isinstance(v, int) and not isinstance(v, bool) and v >= 1):
            raise ValueError(f"a floor needs a positive whole number of {name}, not {v!r}")
    return _floor_replicas(n, stock, replicas)        # checked first: the cache would take True for 1


@functools.lru_cache(maxsize=64)
def _floor_replicas(n, stock, replicas):
    D = len(exact_law(stock)[0])
    return tuple(sorted(_tvd_exact(np.bincount(law_draws(n, ("compare-floor", stock, n, r), stock), minlength=D),
                                   n, stock) for r in range(replicas)))


def tvd_floor(n, stock=STOCK, replicas=FLOOR_REPLICAS, percentile=FLOOR_PERCENTILE):
    """A perfect sampler's TVD to the law at n shots: the mean and the percentile-th percentile by nearest rank
    (the value at rank ceil(percentile * replicas / 100), ascending) of `floor_replicas`. Floats, with the exact
    rationals as strings."""
    vals = floor_replicas(n, stock, replicas)
    rank = math.ceil(percentile * replicas / 100)
    mean = sum(vals, Fraction(0)) / replicas
    return {"shots": n, "replicas": replicas, "mean": float(mean), "percentile": percentile,
            "upper": float(vals[rank - 1]), "max": float(vals[-1]),
            "exact": {"mean": str(mean), "upper": str(vals[rank - 1])},
            "stream": ["compare-floor", stock, n, "<replica>"],
            "rule": f"replica r lays n exact draws from the law; the upper value is the {percentile}th percentile, "
                    f"the value at rank {rank} of {replicas}, ascending"}


# ---------------------------------------------------------------- the measures


def crystals_per_shot(counts):
    """{crystal count: shots}, ascending."""
    out = {}
    for Y, c in counts.items():
        out[len(Y)] = out.get(len(Y), 0) + c
    return dict(sorted(out.items()))


def neighbour_pairs(stock=STOCK):
    """The nearest-neighbour pairs (i, j), i < j, of the periodic L x L tile, site = x * L + y."""
    L = params(stock)["L"]
    return tuple(sorted({tuple(sorted((x * L + y, ((x + dx) % L) * L + (y + dy) % L)))
                         for x in range(L) for y in range(L) for dx, dy in ((1, 0), (0, 1))}))


def pair_correlation(counts, stock=STOCK):
    """The mean over the nearest-neighbour pairs of P(both hold a crystal) / (rho_i rho_j), all measured in the
    same shots. Exact (a Fraction) for whole counts or exact weights; None where a site never holds one."""
    total = sum(counts.values())
    one, two = {}, {}
    for Y, c in counts.items():
        s = set(Y)
        for i in s:
            one[i] = one.get(i, 0) + c
        for i, j in itertools.combinations(sorted(s), 2):
            two[(i, j)] = two.get((i, j), 0) + c
    pairs = neighbour_pairs(stock)
    if not total or any(not one.get(i) for p in pairs for i in p):
        return None
    return sum((Fraction(two.get(p, 0)) * total / (Fraction(one[p[0]]) * one[p[1]]) for p in pairs),
               Fraction(0)) / len(pairs)


def xeb(counts_N, stock=STOCK):
    """The linear cross-entropy fidelity over the N-site layouts (module docstring), exactly, with its standard
    error. counts_N holds N-crystal shots only."""
    layouts, weights, den = exact_law(stock)
    index = _law_index(stock)
    D = len(layouts)
    n = sum(counts_N.values())
    s1 = sum(c * weights[index[Y]] for Y, c in counts_N.items())               # sum over shots of P * den
    s2 = sum(c * weights[index[Y]] ** 2 for Y, c in counts_N.items())          # sum over shots of (P * den)^2
    norm = Fraction(sum(w * w for w in weights), den * den) - Fraction(1, D)
    value = (Fraction(s1, n * den) - Fraction(1, D)) / norm
    var = (Fraction(s2, den * den) - Fraction(s1 * s1, n * den * den)) / (n - 1) if n > 1 else None
    se = math.sqrt(var / n) / float(norm) if var is not None else None
    return {"value": float(value), "se": se, "shots": n, "exact": str(value)}


def _z(score):
    one, pairs = score["one_site"], score["pairs"]
    return {"one_site": {"max_abs_z": one["max_abs_z"], "chi2": one["chi2"], "z": one["z"]},
            "pairs": {"max_abs_z": pairs["max_abs_z"], "chi2": pairs["chi2"], "worst_pair": pairs["worst_pair"],
                      "worst_z": pairs["worst_z"]},
            "chi2_per_dof": score["chi2_per_dof"]}


def canonical_counts(counts, stock=STOCK):
    """{layout: shots} with every layout a strictly increasing tuple of sites in 0..M-1 and every count a
    positive whole number; anything else is refused by name, never reshaped. Zero counts are dropped."""
    M = params(stock)["M"]
    out = {}
    for Y, c in counts.items():
        Y = tuple(Y)
        if not all(isinstance(q, int) and not isinstance(q, bool) for q in Y) or \
                any(b <= a for a, b in itertools.pairwise(Y)) or (Y and (Y[0] < 0 or Y[-1] >= M)):
            raise ValueError(f"layout {Y!r}: not strictly increasing sites of 0..{M - 1}")
        if not (isinstance(c, int) and not isinstance(c, bool) and c >= 0):
            raise ValueError(f"layout {Y!r}: {c!r} shots is not a whole number")
        if c:
            out[Y] = c
    return out


def law_measures(counts, stock=STOCK, circuit_sha256=SOURCE_CIRCUIT, floor=True):
    """Every measure of a law run's counts ({layout: shots}), as the module docstring defines them."""
    law = params(stock)
    N = law["N"]
    K, forbidden, _dets = pauli_tile.law_of(stock)
    counts = canonical_counts(counts, stock)
    shots = sum(counts.values())
    if not shots:
        raise ValueError("no shots to measure")
    per = crystals_per_shot(counts)
    counts_N = {Y: c for Y, c in counts.items() if len(Y) == N}
    n = sum(counts_N.values())
    on_forbidden = sum(c for Y, c in counts_N.items() if Y in forbidden)
    out = {"shots": shots, "crystals_per_shot": {str(k): v for k, v in per.items()},
           "n_crystal": {"N": N, "shots": n, "share": n / shots},
           "forbidden": {"shots": on_forbidden, "share_of_n_crystal": on_forbidden / n if n else None,
                         "distinct": sum(1 for Y in counts_N if Y in forbidden)},
           "z": {"all": _z(pauli_tile.score(counts, K, forbidden, circuit_sha256))},
           "pair_correlation": {"all": _float(pair_correlation(counts, stock))}}
    if n:
        layouts = exact_law(stock)[0]
        index = _law_index(stock)
        c = np.zeros(len(layouts), dtype=np.int64)
        for Y, k in counts_N.items():
            c[index[Y]] += k
        out["tvd"] = {"value": float(_tvd_exact(c, n, stock)), "floor": tvd_floor(n, stock) if floor else None}
        out["xeb"] = xeb(counts_N, stock)
        out["z"]["n_crystal"] = _z(pauli_tile.score(counts_N, K, forbidden, circuit_sha256))
        out["pair_correlation"]["n_crystal"] = _float(pair_correlation(counts_N, stock))
    return out


def _float(x):
    return None if x is None else float(x)


# ---------------------------------------------------------------- coherence


def coherence(counts, basis, stock=STOCK):
    """<P_a P_b> for a run whose basis reads exactly two qubits out of Z in the same letter P (basis[q] is qubit
    q): the mean of +1 when their bits agree and -1 when they differ, with its binomial standard error
    sqrt((1 - mean^2) / shots)."""
    M = params(stock)["M"]
    off = [(q, b) for q, b in enumerate(basis) if b != "Z"]
    if not (isinstance(basis, str) and len(basis) == M and set(basis) <= set("XYZ")) or len(off) != 2 \
            or off[0][1] != off[1][1]:
        raise ValueError(f"basis {basis!r}: a coherence measure reads exactly two of the {M} qubits out of Z, "
                         "both in X or both in Y")
    (a, letter), (b, _) = off
    counts = canonical_counts(counts, stock)
    shots = sum(counts.values())
    if not shots:
        raise ValueError("no shots to measure")
    agree = sum(c for Y, c in counts.items() if (a in Y) == (b in Y))
    mean = Fraction(2 * agree - shots, shots)
    return {"observable": f"{letter}{a}{letter}{b}", "value": float(mean),
            "se": math.sqrt((1 - mean * mean) / shots), "shots": shots}


@functools.lru_cache(maxsize=2)
def _coherence_law(qasm, root):
    raw = (root / qasm).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_CIRCUIT:
        raise ValueError(f"{qasm} is not the circuit {SOURCE_CIRCUIT[:16]}")
    gate_list, M = givens_line.from_qasm(raw.decode("ascii"))
    psi = givens_line.simulate(gate_list, M)
    return (givens_line.pauli_expectation(psi, {0: "X", 1: "X"}), givens_line.pauli_expectation(psi, {0: "Y", 1: "Y"}))


def coherence_law(qasm=SOURCE_QASM, root=ROOT):
    """<X0X1> and <Y0Y1> of the committed law circuit, by the project's own simulator (givens_line), refused
    unless the file is the shelf's circuit."""
    xx, yy = _coherence_law(qasm, root)
    return {"X0X1": xx, "Y0Y1": yy}


def mixture_read_in_x(counts, parts, pair=(0, 1)):
    """A classical mixture's shots read in X (or Y) on a pair: each shot is a computational-basis layout, so each
    of the pair's bits reads as a fair coin, the top bit of golden words 2k and 2k + 1 of stream(*parts) for shot
    k (canonical order: by layout, each repeated its shots). The rest of the layout is kept. -> {layout: shots}."""
    a, b = pair
    total = sum(counts.values())
    words = uniform_words(parts, 2 * total)
    out, k = {}, 0
    for Y in sorted(counts):
        rest = [q for q in Y if q not in pair]
        for _ in range(counts[Y]):
            coins = [q for q, w in ((a, words[2 * k]), (b, words[2 * k + 1])) if int(w) >> 63]
            key = tuple(sorted(rest + coins))
            out[key] = out.get(key, 0) + 1
            k += 1
    return out


# ---------------------------------------------------------------- device runs


def run_counts(record):
    """A device run's counts as {layout: shots}."""
    return {tuple(ones): n for ones, n in record["counts"]}


def _held(record, kind, stock):
    problems = fixer.check(record)
    if problems:
        raise ValueError("compare refuses a record the fixer refuses: " + "; ".join(problems))
    if record.get("format") != fixer.RUN_FORMAT:
        raise ValueError(f"not a device run ({fixer.RUN_FORMAT}): {record.get('format')!r}")
    got = record["source"]["kind"]
    if got != kind:
        if kind == "qpu":
            raise ValueError(f"a {got} run is not hardware: a hardware column and the print take qpu runs only, "
                             "and a simulator's run appears only under its own label (kind='simulator')")
        raise ValueError(f"a {got} run is not a {kind} run: one column holds one kind")
    if record["stock"] != stock:
        raise ValueError(f"a run of {record['stock']!r}, where this comparison is of {stock!r}")


def run_column(records, kind="qpu", stock=STOCK, expected_known_answer=None):
    """One column of the table from one backend's device runs of one kind: the law run's measures, each coherence
    run's, and (given its expected set) the known-answer run's verdict. Labelled by kind, so a simulator's column
    can never read as hardware."""
    if kind not in fixer.RUN_KINDS:
        raise ValueError(f"kind is one of {fixer.RUN_KINDS}")
    records = list(records)
    if not records:
        raise ValueError("no runs")
    for rec in records:
        _held(rec, kind, stock)
    backends = sorted({r["source"]["backend"] for r in records})
    if len(backends) != 1:
        raise ValueError(f"one column is one backend's: {backends}")
    by_role = {}
    for rec in records:
        by_role.setdefault(rec["role"], []).append(rec)
    M = params(stock)["M"]
    col = {"label": f"{kind}: {backends[0]}", "kind": kind, "backend": backends[0],
           "jobs": sorted({r["source"]["job_id"] for r in records}), "law": None, "coherence": {}}
    laws = by_role.get("law", [])
    if len(laws) > 1:
        raise ValueError(f"one column holds one law run, not {len(laws)}")
    if laws:
        col["law"] = law_measures(run_counts(laws[0]), stock, laws[0]["source"]["circuit_sha256"])
        col["law"]["job_id"] = laws[0]["source"]["job_id"]
    for rec in by_role.get("coherence", []):
        m = coherence(run_counts(rec), rec["basis"], stock)
        if m["observable"] in col["coherence"]:
            raise ValueError(f"two coherence runs of {m['observable']} in one column")
        col["coherence"][m["observable"]] = dict(m, job_id=rec["source"]["job_id"])
    kas = by_role.get("known-answer", [])
    if kas and expected_known_answer is not None:
        col["known_answer"] = [dict(ibm_decode.known_answer(run_counts(r), expected_known_answer, M),
                                    job_id=r["source"]["job_id"]) for r in kas]
    return col


# ---------------------------------------------------------------- the print rule


def print_layouts(records, stock=STOCK):
    """The layouts a hardware print is laid from: every shot with exactly N crystals of the qpu law runs, in
    canonical order: by job, then by layout, each layout repeated its shots. Any other kind or role is refused by
    name. (develop.shuffled then orders them on the print's own stream; that is the print's, not this rule's.)"""
    N = params(stock)["N"]
    keyed = []
    for rec in records:
        _held(rec, "qpu", stock)
        if rec["role"] != "law":
            raise ValueError(f"a {rec['role']} run is not crystal layouts: a print takes law runs only")
        keyed += [(rec["source"]["job_id"], tuple(ones), n) for ones, n in rec["counts"] if len(ones) == N]
    return [list(Y) for _job, Y, n in sorted(keyed) for _ in range(n)]


@functools.lru_cache(maxsize=4)
def honesty_floor(stock=STOCK):
    """The fewest layers develop.pitch_um accepts for this stock: the borrowed stock's honesty floor (29 for
    pauli-4x4)."""
    for layers in range(1, 100000):
        try:
            develop.pitch_um(stock, layers)
        except develop.SheetRefused:
            continue
        return layers
    raise develop.SheetRefused(f"no layer count of {stock} clears the honesty floor")


def print_geometry(count, stock=STOCK, layers=None):
    """The print's geometry from its layouts' count: square tiles, t across and t down, `layers` deep (the
    honesty floor unless given; fewer is refused by develop.pitch_um), t as large as the count allows, so
    t * t * layers layouts are laid and the rest are counted as left over."""
    if not (isinstance(count, int) and not isinstance(count, bool) and count >= 0):
        raise ValueError(f"a count of layouts is a whole number, not {count!r}")
    floor = honesty_floor(stock)
    layers = floor if layers is None else layers
    pitch = develop.pitch_um(stock, layers)
    t = math.isqrt(count // layers)
    if t < 1:
        raise develop.SheetRefused(f"{count} layouts do not fill one tile {layers} layers deep")
    used = t * t * layers
    return {"tiles": [t, t], "layers": layers, "honesty_floor": floor, "pitch_um": pitch, "layouts": count,
            "used": used, "left_over": count - used}


# ---------------------------------------------------------------- the baselines


def emulator_records(root=ROOT, stock=STOCK):
    """Atlas's emulator rolls: every device roll in a rolls-* directory under EMULATOR_DIRS, each held to the
    fixer (its bytes included), to its kind, to the stock and to the shelf's circuit."""
    files = sorted(f for d in EMULATOR_DIRS for f in (root / d).glob("rolls-*/*.json"))
    out = []
    for f in files:
        rec, problems = fixer.check_file(f)
        if problems:
            raise ValueError(f"{f.name}: the fixer refuses it: {problems}")
        src = rec["source"]
        if src.get("kind") != "atlas-emu" or rec["stock"] != stock or src.get("circuit_sha256") != SOURCE_CIRCUIT:
            raise ValueError(f"{f.name}: not an Atlas emulator roll of {stock}'s circuit {SOURCE_CIRCUIT[:16]}")
        out.append(rec)
    return out


@functools.lru_cache(maxsize=4)
def emulator_rolls(root=ROOT, stock=STOCK):
    """Each emulator roll as (job id, crystals, occurrences), read and checked once per tree: what the counts
    are made of, and nothing a caller could change."""
    return tuple((r["source"]["job_id"], tuple(r["crystals"]), r["source"]["occurrences"])
                 for r in emulator_records(root, stock))


def emulator_counts(root=ROOT, stock=STOCK):
    """{layout: shots} over Atlas's emulator shots, read as develop.device_shots expands them."""
    rolls = [{"source": {"job_id": job, "occurrences": n}, "crystals": list(Y)}
             for job, Y, n in emulator_rolls(root, stock)]
    out = {}
    for Y in develop.device_shots(rolls):
        out[tuple(Y)] = out.get(tuple(Y), 0) + 1
    return out


def emulator_coherence(root=ROOT):
    """The engine's own <X0X1> and <Y0Y1> per Atlas job (its derived observables, not shots read through a decode
    rule; P3's audit held them to the circuit's state, signs included), pooled over the jobs: the shot-weighted
    mean, with the binomial error of the pooled shots (each job's shots counted as its settings' least)."""
    files = sorted(f for d in EMULATOR_DIRS for f in (root / d).glob("atlas-*-result.json"))
    pooled = {}
    for f in files:
        result = json.loads(f.read_text(encoding="ascii"))["response"]["result"]
        shots = min(v["shots"] for v in result["measurements"].values())
        for name, key in (("X0X1", "XX"), ("Y0Y1", "YY")):
            pooled.setdefault(name, []).append((float(result["observables"]["0,1"][key]), shots))
    out = {}
    for name, rows in pooled.items():
        shots = sum(s for _, s in rows)
        mean = sum(v * s for v, s in rows) / shots
        out[name] = {"observable": name, "value": mean, "se": math.sqrt((1 - mean * mean) / shots),
                     "shots": shots, "jobs": len(rows), "how": "the engine's own derived observable"}
    return out


def law_column(shots=EMULATOR_SHOTS, stock=STOCK):
    """The exact law, as expectations (no sampling). Its TVD is 0; its floor is what a perfect sampler shows at
    `shots`, the expectation a law run is measured against."""
    layouts, weights, den = exact_law(stock)
    K, forbidden, _ = pauli_tile.law_of(stock)
    expected = {Y: shots * w / den for Y, w in zip(layouts, weights, strict=True) if w}
    g = pair_correlation({Y: Fraction(w, den) for Y, w in zip(layouts, weights, strict=True) if w}, stock)
    co = coherence_law()
    N = params(stock)["N"]
    z = _z(pauli_tile.score(expected, K, forbidden, SOURCE_CIRCUIT))
    return {"label": "law (exact)", "kind": "exact",
            "law": {"shots": shots, "crystals_per_shot": {str(N): shots}, "n_crystal": {"N": N, "shots": shots,
                                                                                       "share": 1.0},
                    "forbidden": {"shots": 0, "share_of_n_crystal": 0.0, "distinct": 0},
                    "tvd": {"value": 0.0, "floor": tvd_floor(shots, stock)},
                    "xeb": {"value": 1.0, "se": None, "exact": "1"},
                    "z": {"all": z, "n_crystal": z,
                          "note": "z of the expected counts at this many shots: 0 up to rounding"},
                    "pair_correlation": {"all": float(g), "n_crystal": float(g), "exact": str(g)}},
            "coherence": {k: {"observable": k, "value": v, "se": 0.0, "how": "the project's simulator on the "
                              "committed circuit"} for k, v in co.items()}}


def twin_column(shots=EMULATOR_SHOTS, stock=STOCK):
    """The twin, exactly: every N-site layout 1/D. z is the twin's expected z at `shots`."""
    layouts, weights, den = exact_law(stock)
    K, forbidden, _ = pauli_tile.law_of(stock)
    D, N = len(layouts), params(stock)["N"]
    share = Fraction(len(forbidden), D)
    tvd = sum((abs(Fraction(1, D) - Fraction(w, den)) for w in weights), Fraction(0)) / 2
    g = pair_correlation({Y: Fraction(1, D) for Y in layouts}, stock)
    z = _z(pauli_tile.score({Y: shots / D for Y in layouts}, K, forbidden, SOURCE_CIRCUIT))
    return {"label": "twin (exact)", "kind": "exact",
            "law": {"shots": shots, "crystals_per_shot": {str(N): shots}, "n_crystal": {"N": N, "shots": shots,
                                                                                       "share": 1.0},
                    "forbidden": {"shots": float(shots * share), "share_of_n_crystal": float(share),
                                  "distinct": len(forbidden), "exact": str(share)},
                    "tvd": {"value": float(tvd), "floor": None, "exact": str(tvd)},
                    "xeb": {"value": 0.0, "se": None, "exact": "0"},
                    "z": {"all": z, "n_crystal": z, "note": "the twin's expected z at this many shots"},
                    "pair_correlation": {"all": float(g), "n_crystal": float(g), "exact": str(g)}},
            "coherence": {k: {"observable": k, "value": 0.0, "se": 0.0, "how": "a classical mixture: exactly 0"}
                          for k in COHERENCE_LAW}}


def twin_sample_column(shots=EMULATOR_SHOTS, stock=STOCK):
    """The twin as a sample of `shots` (stream "compare-twin"), its coherence read as a classical mixture is."""
    counts = twin_sample(shots, ("compare-twin", stock))
    col = {"label": f"twin (sample, {shots} shots)", "kind": "sample", "law": law_measures(counts, stock),
           "coherence": {}}
    for name, letter in (("X0X1", "X"), ("Y0Y1", "Y")):
        read = mixture_read_in_x(counts, ("compare-twin-mixture", stock, letter))
        col["coherence"][name] = coherence(read, letter * 2 + "Z" * (params(stock)["M"] - 2))
    return col


def emulator_column(root=ROOT, stock=STOCK):
    counts = emulator_counts(root, stock)
    return {"label": f"emulator (Atlas, {sum(counts.values())} shots)", "kind": "emulator",
            "law": law_measures(counts, stock), "coherence": emulator_coherence(root)}


def baselines(shots=EMULATOR_SHOTS, root=ROOT, stock=STOCK):
    """The table's baseline columns: the exact law, Atlas's emulator, the twin exactly and as a sample."""
    return [law_column(shots, stock), emulator_column(root, stock), twin_column(shots, stock),
            twin_sample_column(shots, stock)]


# ---------------------------------------------------------------- the table


def _cell(x, fmt="{:.4f}"):
    return "-" if x is None else fmt.format(x)


def _pm(m):
    if not m:
        return "-"
    return f"{m['value']:+.4f}" + ("" if not m.get("se") else f" +- {m['se']:.4f}")


def _floor(law):
    f = (law.get("tvd") or {}).get("floor")
    return "-" if not f else f"{f['mean']:.4f} / {f['upper']:.4f}"


def _both(law, field, key):
    z = law["z"]
    return _cell(z["all"][field][key], "{:.2f}") + " / " + _cell(((z.get("n_crystal") or {}).get(field) or {}).get(key),
                                                               "{:.2f}")


# (row, the part of a column it reads, the cell); a column without that part shows "-".
ROWS = (
    ("shots", "law", lambda m: f"{m['shots']:,}"),
    ("N-crystal share", "law", lambda m: _cell(m["n_crystal"]["share"])),
    ("forbidden share of N-crystal shots", "law", lambda m: _cell(m["forbidden"]["share_of_n_crystal"])),
    ("TVD to the law", "law", lambda m: _cell((m.get("tvd") or {}).get("value"))),
    (f"perfect sampler's TVD floor: mean / p{FLOOR_PERCENTILE}", "law", _floor),
    ("linear XEB", "law", lambda m: _pm(m.get("xeb"))),
    ("one-site max |z|: all / N-crystal", "law", lambda m: _both(m, "one_site", "max_abs_z")),
    ("pair max |z|: all / N-crystal", "law", lambda m: _both(m, "pairs", "max_abs_z")),
    ("NN pair correlation: all / N-crystal", "law", lambda m: _cell(m["pair_correlation"]["all"]) + " / "
     + _cell(m["pair_correlation"].get("n_crystal"))),
    ("<X0X1>", "coherence", lambda m: _pm(m.get("X0X1"))),
    ("<Y0Y1>", "coherence", lambda m: _pm(m.get("Y0Y1"))),
)


def table(columns):
    """The columns as one Markdown table, one row per measure."""
    out = ["| measure | " + " | ".join(c["label"] for c in columns) + " |", "|---" * (len(columns) + 1) + "|"]
    for name, part, cell in ROWS:
        out.append(f"| {name} | " + " | ".join(cell(c[part]) if c.get(part) else "-" for c in columns) + " |")
    return "\n".join(out) + "\n"


def device_runs(paths):
    """Every device-run record (fixer.RUN_FORMAT) in these files and directories (searched recursively), each held
    to the fixer, its bytes included; other JSON files (job lines, metrics, raw results) are passed over."""
    files = []
    for p in map(pathlib.Path, paths):
        files += sorted(p.rglob("*.json")) if p.is_dir() else [p]
    out = []
    for f in files:
        try:
            fmt = json.loads(f.read_text(encoding="utf-8")).get("format")
        except (ValueError, AttributeError, UnicodeDecodeError):
            continue
        if fmt != fixer.RUN_FORMAT:
            continue
        rec, problems = fixer.check_file(f)
        if problems:
            raise ValueError(f"{f}: the fixer refuses it: {problems}")
        out.append(rec)
    return out


PREDICTION_FORMAT = "quantum-film/prediction/v1"          # tools/hw_predict.py's output


def prediction_column(prediction):
    """A column from tools/hw_predict.py's JSON, labelled as a prediction with its noise model and the model's
    calibration date, so it can never read as hardware. Its measures are compare's own, taken where it ran."""
    if not isinstance(prediction, dict) or prediction.get("format") != PREDICTION_FORMAT:
        raise ValueError(f"not a prediction ({PREDICTION_FORMAT}, tools/hw_predict.py's output)")
    rows = {r["role"]: r for r in prediction["circuits"]}
    noise = "no noise" if prediction["noise"] == "none" else f"{prediction['source']} noise model"
    col = {"label": f"predicted: {prediction['backend']}, {noise}, calibration {prediction['calibration']}",
           "kind": "prediction", "backend": prediction["backend"], "seed": prediction["seed"],
           "law": rows["law"]["measures"] if "law" in rows else None, "coherence": {}}
    for role in ("xx", "yy"):
        if role in rows:
            col["coherence"][rows[role]["measures"]["observable"]] = rows[role]["measures"]
    if "known-answer" in rows:
        col["known_answer"] = rows["known-answer"]["measures"]
    return col


def run_columns(records, stock=STOCK, expected_known_answer=None):
    """One column per kind and backend, qpu first: a simulator's runs only ever under their own label."""
    groups = {}
    for rec in records:
        groups.setdefault((rec["source"]["kind"] != "qpu", rec["source"]["kind"], rec["source"]["backend"]),
                          []).append(rec)
    return [run_column(recs, kind, stock, expected_known_answer) for (_, kind, _b), recs in sorted(groups.items())]


def main(argv):
    """python -m quantum_film.compare table [--json] [--expected 0,1,3,7,12] [--prediction FILE ...] [RECORDS ...]"""
    if argv[:1] != ["table"]:
        print("python -m quantum_film.compare table [--json] [--expected Q,Q,...] [--prediction FILE ...] "
              "[RECORDS ...]\n"
              "    the law, the emulator and the twin; each prediction (tools/hw_predict.py's JSON) under its own\n"
              "    label; then one column per kind and backend of the device runs found in RECORDS (files or\n"
              "    directories), a simulator's under its own label")
        return 2
    args, as_json, expected, predictions = argv[1:], False, None, []
    if "--json" in args:
        args.remove("--json")
        as_json = True
    while "--expected" in args or "--prediction" in args:
        i = args.index("--expected") if "--expected" in args else args.index("--prediction")
        if args[i] == "--expected":
            expected = [int(q) for q in args[i + 1].split(",")]
        else:
            predictions.append(pathlib.Path(args[i + 1]))
        del args[i:i + 2]
    try:
        columns = baselines() + [prediction_column(json.loads(p.read_text(encoding="ascii"))) for p in predictions] \
            + run_columns(device_runs(args), expected_known_answer=expected)
    except ValueError as e:
        print(f"REFUSED: {e}")
        return 1
    sys.stdout.write(json.dumps(columns, indent=1, sort_keys=True) + "\n" if as_json else table(columns))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

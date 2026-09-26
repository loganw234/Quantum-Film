"""The certificate's helpers, each held exactly, and its orchestration run end to end on TIGHT inputs
(verifier-P1's D8, 2026-09-26).

HELPERS. Every function the orchestration may call that is not a step is registered in HELPER_CHECKS with an exact
check of its answer, and each check is shown to fail when the helper's ends are swapped or its answer inverted
(HELPER_FAULTS). tests/pinned/test_pinned_source_rule.py refuses any top-level function of certificate.py that is
neither a step with its tight check nor a helper here.

THE ORCHESTRATION, END TO END. Certificate is driven on inputs where what it composes decides every claim it makes:
  - an exactly orthonormal basis whose rows are binary64 numbers: columns 0, 1, 2, 4 and 8 of Sylvester's Hadamard
    matrix of order 16, over 4, every entry +-1/4. Its enclosure is a point, so no slack hides a fault;
  - family G: coefficient columns deliberately off orthonormal by 2^-37 each, so Q^T Q misses I by about 2^-36 and
    the Gram factor moves every weight by about 1e-12;
  - family U: the first draw alone, where the total is exactly 5, with uniforms one tenth and nine tenths of an ulp
    above a binary64 number, so the uniform's box decides the target's ends;
  - family Q: two columns whose coefficients carry 53 significant bits, so the columns round and their width is
    all that keeps the projections' state true.
Every claim is held to the exact chain rule, in Fractions: after each extend, the state (|y|^2's interval, the three
Gram sums, the Gram bound F); at each decide, the boundaries and the target it traces, and the decision it RETURNS,
which is what the sampler draws from (verifier-P1's D10: the first version read only the trace, and a decide that
traced honestly and returned a position certified on other weights passed it). The returned position must be the
traced one; None, or the exact chain rule's position cleared by TAU on both sides; None wherever the exact target lies
within TAU of a boundary; and not None wherever it clears every boundary by CERTAIN. On the first LADDER plans of
family G, decide is also asked about planted targets on both sides of every exact boundary, at relative distances from
0 to 1e-6 (PROBE_DISTANCES): there the Gram factor moves the boundaries by about 1e-12, so a decision taken from other
weights than the ones traced lands on the wrong side of some of them.
"""
from fractions import Fraction

import mpmath
import numpy as np
import pytest
from mpmath import mp

from quantum_film.pinned import basis, certificate, encode
from quantum_film.pinned.cft import FP64, RNE
from quantum_film.pinned.encode import round_fraction

c = certificate
SOURCE = open(c.__file__, encoding="utf-8").read()


def X(v):
    return Fraction(float(v))


def arr(xs):
    return np.array(xs, dtype=np.float64)


def load(source):
    """A variant of certificate.py's source, loaded as a module of its own; its namespace."""
    ns = {"__name__": "quantum_film.pinned._certificate_variant", "__package__": "quantum_film.pinned"}
    exec(compile(source, "certificate_variant.py", "exec"), ns)              # a variant of our own file, nothing else
    return ns


# ---------------------------------------------------------------------------------------------------------------
# The helpers: one exact check each.


def check_magnitudes(fn):
    cases = [(-3.0, -1.0, 1.0, 3.0), (-1.0, 2.0, 0.0, 2.0), (-2.0, 1.0, 0.0, 2.0), (0.5, 4.0, 0.5, 4.0),
             (-0.25, -0.25, 0.25, 0.25), (0.0, 0.0, 0.0, 0.0)]
    lo, hi = arr([k[0] for k in cases]), arr([k[1] for k in cases])
    small, big = fn((lo, hi))
    return [f"magnitudes([{a}, {b}]) = [{s}, {g}], not [{w}, {W}]"
            for (a, b, w, W), s, g in zip(cases, small, big, strict=True)
            if not (float(s) == w and float(g) == W and not np.signbit(s) and not np.signbit(g))]


def check_select(fn):
    lo, hi = arr([1.0, 2.0, 3.0, 4.0]), arr([11.0, 12.0, 13.0, 14.0])
    a, b = fn((lo, hi), np.array([3, 0, 2]))
    return [] if list(a) == [4.0, 1.0, 3.0] and list(b) == [14.0, 11.0, 13.0] else [f"select gave {a}, {b}"]


def check_last(fn):
    a, b = fn((arr([1.0, 2.0, 3.0]), arr([4.0, 5.0, 6.0])))
    return [] if (float(a), float(b)) == (3.0, 6.0) else [f"last gave {a}, {b}"]


def check_lower(fn):
    v = fn((arr([1.0, -2.0]), arr([3.0, 4.0])))
    return [] if list(v) == [1.0, -2.0] else [f"lower gave {v}"]


def check_zero(fn):
    a, b = fn(7)
    ok = a.shape == b.shape == (7,) and a.dtype == b.dtype == np.float64 and not a.any() and not b.any() \
        and not np.signbit(a).any() and not np.signbit(b).any()
    return [] if ok else [f"zero gave {a}, {b}"]


def check_gram_zero(fn):
    v = fn()
    ok = len(v) == 3 and all(type(x) is float and x == 0.0 and not np.signbit(x) for x in v)
    return [] if ok else [f"gram_zero gave {v!r}"]


def check_upper_negative(fn):
    out = []
    for lo, hi, want in (([-1.0, 0.5], [0.5, 1.0], False), ([0.0, 0.0], [0.0, -1e-300], True),
                         ([-5.0], [-0.0], False), ([1.0, 2.0], [-2.0, 3.0], True)):
        if bool(fn((arr(lo), arr(hi)))) != want:
            out.append(f"upper_negative({lo}, {hi})")
    return out


def check_holds(fn):
    third, tiny = Fraction(1, 3), Fraction(1, 2 ** 80)
    lo, hi = round_fraction(third, FP64, 2)[0], round_fraction(third, FP64, 3)[0]
    cases = [((lo, hi), third, True), ((lo, lo), third, False), ((hi, hi), third, False),
             ((np.float64(0.5), np.float64(0.75)), Fraction(3, 4), True),
             ((np.float64(0.5), np.float64(0.75)), Fraction(3, 4) + tiny, False),
             ((np.float64(0.5), np.float64(0.75)), Fraction(1, 2) - tiny, False), ((np.float64(5.0),) * 2, 5, True)]
    return [f"holds({x}, {v})" for x, v, want in cases if bool(fn(x, v)) != want]


def check_holds_all(fn):
    lo, hi = arr([0.25, 0.25 - 2 ** -60]), arr([0.25, 0.25])
    out = []
    if not fn((lo, hi), Fraction(1, 4)):
        out.append("holds_all missed a value inside every interval")
    if fn((lo, hi), Fraction(1, 4) - Fraction(1, 2 ** 70)):
        out.append("holds_all passed a value outside one interval")
    return out


def check_assemble_box(fn):
    L, r2 = 4, 1
    cos = (arr([0.1, 0.2, 0.3, 0.4]), arr([1.1, 1.2, 1.3, 1.4]))
    sin = (arr([-0.1, -0.2, -0.3, -0.4]), arr([0.9, 0.8, 0.7, 0.6]))
    one = np.float64(0.25)
    lo, hi = fn(L, r2, one, cos, sin)
    want_lo = basis.assemble(L, r2, one, {1: cos[0], 2: sin[0]}, np.float64)
    want_hi = basis.assemble(L, r2, one, {1: cos[1], 2: sin[1]}, np.float64)
    return [] if np.array_equal(lo, want_lo) and np.array_equal(hi, want_hi) else ["assemble_box's ends"]


def check_freeze(fn):
    phi = (arr([[0.25, 0.5]]), arr([[0.25, 0.75]]))
    e = c.rows(phi)
    out = fn(e)
    arrays = (*out.box, *out.norm, out.l1, out.dl1)
    return [] if out is e and not any(a.flags.writeable for a in arrays) else ["freeze left an array writable"]


def check_locate(fn):
    b_lo = arr([0.1, 0.2, 0.3, 0.4, 0.5])
    b = (b_lo, b_lo + 0.01)
    out = []
    for t, want in (((0.25, 0.26), 2), ((0.05, 0.06), 0), ((0.205, 0.215), None), ((0.52, 0.53), None),
                    ((0.305, 0.45), None), ((0.211, 0.29), 2)):
        found = fn((np.float64(t[0]), np.float64(t[1])), b)
        if found.position != want or (found.position is None) != (found.reason is not None):
            out.append(f"locate({t}) = {found}")
    return out


def check_modes(fn):
    """pauli-4x4's columns: the constant, then a cosine and a sine for (-1, 0) and for (0, -1), with angle index
    (kx * x + ky * y) mod 4 at site x * 4 + y; and a tile edge that is not a power of two refused."""
    kinds, m = fn(4, 1)
    out = []
    want = [[0, (-x) % 4, (-x) % 4, (-y) % 4, (-y) % 4] for x in range(4) for y in range(4)]
    if list(kinds) != [0, 1, 2, 1, 2] or m.tolist() != want:
        out.append(f"modes(4, 1): kinds {list(kinds)}, angles {m.tolist()[:3]}...")
    try:
        fn(6, 1)
        out.append("modes(6, 1) did not refuse")
    except ValueError:
        pass
    return out


def check_angles(fn):
    out = []
    for L in (4, 16, 64):
        a = fn(L, FP64)
        if [Fraction(float(v)) for v in a] != [Fraction(2 * m, L) for m in range(L)]:
            out.append(f"angles({L}) are not exactly 2m/L")
    return out


def check_exact(fn):
    out = []
    if Fraction(float(fn(Fraction(1, 8), FP64)[0])) != Fraction(1, 8):
        out.append("exact(1/8) is not 1/8")
    try:
        fn(Fraction(1, 3), FP64)
        out.append("exact(1/3) did not refuse")
    except ValueError:
        pass
    return out


HELPER_CHECKS = {
    "magnitudes": (c, check_magnitudes), "select": (c, check_select), "last": (c, check_last),
    "lower": (c, check_lower), "zero": (c, check_zero), "gram_zero": (c, check_gram_zero),
    "upper_negative": (c, check_upper_negative), "holds": (c, check_holds), "holds_all": (c, check_holds_all),
    "assemble_box": (c, check_assemble_box), "freeze": (c, check_freeze), "locate": (c, check_locate),
    "modes": (basis, check_modes), "angles": (basis, check_angles), "exact": (encode, check_exact),
}

# Each helper's check must fail on the helper with its ends swapped or its answer inverted.
HELPER_FAULTS = {
    "magnitudes": lambda f: lambda x: f(x)[::-1],
    "select": lambda f: lambda x, idx: f(x, idx)[::-1],
    "last": lambda f: lambda x: f(x)[::-1],
    "lower": lambda f: lambda x: x[1],
    "zero": lambda f: lambda size: (np.full(size, -0.0), np.zeros(size)),
    "gram_zero": lambda f: lambda: (0.0, 0.0, 2.0 ** -1074),
    "upper_negative": lambda f: lambda cc: (cc[0] < 0).any(),
    "holds": lambda f: lambda x, v: not f(x, v),
    "holds_all": lambda f: lambda x, v: not f(x, v),
    "assemble_box": lambda f: lambda *a: f(*a)[::-1],
    "freeze": lambda f: lambda e: e,
    "locate": lambda f: lambda t, b: c.Located(np.argmax(b[0] > t[1]) if (b[0] > t[1]).any() else None, None),
    "modes": lambda f: lambda L, r2: (f(L, r2)[0][::-1], f(L, r2)[1]),
    "angles": lambda f: lambda L, fmt: f(L, fmt)[::-1],
    "exact": lambda f: lambda x, fmt: round_fraction(x, fmt, RNE),
}


@pytest.mark.parametrize("name", sorted(HELPER_CHECKS))
def test_each_helper_is_exact(name):
    module, check = HELPER_CHECKS[name]
    assert check(getattr(module, name)) == []


@pytest.mark.parametrize("name", sorted(HELPER_CHECKS))
def test_each_helpers_check_fails_with_its_ends_swapped_or_its_answer_inverted(name):
    module, check = HELPER_CHECKS[name]
    assert check(HELPER_FAULTS[name](getattr(module, name))), f"{name}'s check did not see the fault"


def test_every_helper_has_a_fault():
    assert HELPER_FAULTS.keys() == HELPER_CHECKS.keys()


# ---------------------------------------------------------------------------------------------------------------
# The orchestration, end to end, on tight inputs.


def hadamard(n):
    H = [[1]]
    while len(H) < n:
        H = [r + r for r in H] + [r + [-v for v in r] for r in H]
    return H


H16 = hadamard(16)
COLS = (0, 1, 2, 4, 8)
PHI_F = [[Fraction(H16[i][k], 4) for k in COLS] for i in range(16)]
PHI = arr([[float(v) for v in r] for r in PHI_F])
MS, NS = 16, 5


def fdot(a, b):
    return sum(x * y for x, y in zip(a, b, strict=True))


def solve(G, v):
    """G x = v over Fractions (G small and invertible)."""
    n = len(G)
    A = [list(r) + [v[i]] for i, r in enumerate(G)]
    for col in range(n):
        piv = next(r for r in range(col, n) if A[r][col] != 0)
        A[col], A[piv] = A[piv], A[col]
        for r in range(n):
            if r != col and A[r][col] != 0:
                f = A[r][col] / A[col][col]
                A[r] = [a - f * b for a, b in zip(A[r], A[col], strict=True)]
    return [A[r][n] / A[r][r] for r in range(n)]


def exact_weights(taken):
    """c_i = |phi_i|^2 minus its projection onto the span of the taken rows, for every site, exactly."""
    A = [PHI_F[d] for d in taken]
    G = [[fdot(a, b) for b in A] for a in A]
    out = []
    for i in range(MS):
        n = fdot(PHI_F[i], PHI_F[i])
        if A:
            v = [fdot(a, PHI_F[i]) for a in A]
            n -= fdot(v, solve(G, v))
        out.append(n)
    return out


def coefficients(taken, scale=1):
    """T = R^-1 with G = R^T R the Cholesky factorisation of the taken rows' Gram matrix, at 200 bits, each column
    times `scale`, rounded to binary64: column j is what extend takes at draw j."""
    k = len(taken)
    with mp.workprec(200):
        G = [[mpmath.mpf(fdot(PHI_F[a], PHI_F[b]).numerator) / fdot(PHI_F[a], PHI_F[b]).denominator
              for b in taken] for a in taken]
        R = [[mpmath.mpf(0)] * k for _ in range(k)]
        for i in range(k):
            R[i][i] = mpmath.sqrt(G[i][i] - mpmath.fsum(R[m][i] ** 2 for m in range(i)))
            for j in range(i + 1, k):
                R[i][j] = (G[i][j] - mpmath.fsum(R[m][i] * R[m][j] for m in range(i))) / R[i][i]
        T = [[mpmath.mpf(0)] * k for _ in range(k)]
        for j in range(k):
            T[j][j] = 1 / R[j][j]
            for i in range(j - 1, -1, -1):
                T[i][j] = -mpmath.fsum(R[i][m] * T[m][j] for m in range(i + 1, j + 1)) / R[i][i]
        return [arr([float(T[i][j] * scale) for i in range(j + 1)]) for j in range(k)]


def independent(rng, k):
    while True:
        taken = rng.sample(range(MS), k)
        A = [PHI_F[d] for d in taken]
        try:
            solve([[fdot(a, b) for b in A] for a in A], [Fraction(0)] * k)
            return taken
        except StopIteration:
            continue


def uniform64(rng):
    return Fraction(rng.getrandbits(64), 1 << 64)


def near_binary64(rng, tenths):
    """A uniform `tenths` tenths of an ulp above a 50-bit binary64 in [0.5, 0.8): 5u's binary64 neighbours are then
    exact, and only the uniform's own box decides the target's ends."""
    while True:
        lo = Fraction(rng.getrandbits(50) | (1 << 49), 1 << 50)
        if Fraction(1, 2) <= lo < Fraction(4, 5):
            return lo + Fraction(tenths, 10) * Fraction(1, 1 << 53)


def families():
    rng = __import__("random").Random(2609)
    G, U, Q = [], [], []
    for _ in range(6):
        taken = independent(rng, 4)
        G.append((taken, coefficients(taken, 1 + mpmath.mpf(2) ** -37), [uniform64(rng) for _ in range(5)]))
    for tenths in (1, 9):
        for _ in range(30):
            U.append(([], [], [near_binary64(rng, tenths)]))
    for _ in range(40):
        taken = independent(rng, 2)
        ts = coefficients(taken)
        wobble = [arr([float(Fraction(v) * (1 + Fraction(rng.getrandbits(20) - (1 << 19), 1 << 50))) for v in t])
                  for t in ts]
        Q.append((taken, wobble, [uniform64(rng) for _ in range(3)]))
    return {"G": G, "U": U, "Q": Q}


FAMILIES = families()
LADDER = {"G": 3}                  # how many of each family's plans are probed with planted targets
PROBE_DISTANCES = (Fraction(0), Fraction(1, 2 ** 210), Fraction(1, 10 ** 14), Fraction(1, 10 ** 13),
                   Fraction(1, 10 ** 12), Fraction(1, 10 ** 11), Fraction(1, 10 ** 10), Fraction(1, 10 ** 8),
                   Fraction(1, 10 ** 6))
CERTAIN = Fraction(1, 10 ** 7)     # a target this far from every boundary is certified: enclosures here are narrower


def exact_boundaries(taken):
    """The exact chain rule's cumulative weights over the untaken sites, in site order."""
    cs = exact_weights(taken)
    out, acc = [], Fraction(0)
    for i in range(MS):
        if i not in taken:
            acc += cs[i]
            out.append(acc)
    return out


def probes(u, B, j, ladder):
    """The uniforms decide is asked about at draw j: the plan's own and, on a ladder plan, a target at each of
    PROBE_DISTANCES either side of every exact boundary, where that is a uniform below 1."""
    out = [u]
    if ladder:
        for v in B:
            for d in PROBE_DISTANCES:
                for side in (-1, 1):
                    w = v * (1 + side * d) / (NS - j)
                    if 0 <= w < 1 and w not in out:
                        out.append(w)
    return out


def decide_problems(ns, tag, j, B, u, info):
    """The claims decide traced at draw j, held to the exact chain rule: every boundary, and the target."""
    out = []
    TAU = Fraction(ns["TAU"])
    if not info:
        return [f"{tag} draw {j} u={float(u)!r}: decide traced nothing"]
    b_lo, b_hi = info["bounds"]
    out += [f"{tag} draw {j}: boundary {k} {float(B[k])!r} outside [{b_lo[k]!r}, {b_hi[k]!r}]"
            for k in range(len(B)) if not X(b_lo[k]) <= B[k] <= X(b_hi[k])]
    t_lo, t_hi = info["target"]
    target = u * (NS - j)
    if not X(t_lo) <= target - TAU or not X(t_hi) >= target + TAU:
        out.append(f"{tag} draw {j}: the exact target {float(target)!r} +- TAU is outside [{t_lo!r}, {t_hi!r}]")
    return out


def decision_problems(ns, tag, j, B, u, returned, info):
    """The decision decide RETURNED at draw j, the one the sampler draws from, held to the exact chain rule's own."""
    out = []
    TAU = Fraction(ns["TAU"])
    p, why, slack = returned
    T = u * (NS - j)
    where = f"{tag} draw {j} u={float(u)!r}"
    if info.get("position", "untraced") != p:
        out.append(f"{where}: decide returned position {p}, and traced {info.get('position', 'nothing')}")
    if (p is None) != (why is not None) or (p is None) != (slack is None):
        out.append(f"{where}: decide returned {returned!r}: a position with a slack, or a reason, never both")
    exact = next(k for k, v in enumerate(B) if T < v)
    near = min(abs(T - v) for v in B)
    if p is not None:
        if p != exact:
            out.append(f"{where}: decide certified position {p}; the exact chain rule's is {exact}")
        else:
            gap = min(B[p] - T, T - B[p - 1] if p else B[p] - T)
            if gap <= TAU:
                out.append(f"{where}: decide certified position {p} with the exact target {float(gap)!r} from a "
                           f"boundary, inside TAU")
            elif not X(slack[0]) <= gap:
                out.append(f"{where}: decide's clearance {slack[0]!r} is above the exact one {float(gap)!r}")
    if near <= TAU and p is not None:
        out.append(f"{where}: the exact target is within TAU of a boundary, and decide certified {p}")
    if near >= CERTAIN and p is None:
        out.append(f"{where}: the exact target clears every boundary by {float(near)!r}, and decide handed off")
    return out


def state_problems(ns, tag, j, taken, ts, cert):
    """The state extend composed after draw j, held to the exact chain rule's Q = A^T T."""
    out = []
    A = [PHI_F[d] for d in taken]
    Qx = [[sum(Fraction(t[r]) * A[r][n] for r in range(len(t))) for n in range(NS)] for t in ts[:j + 1]]
    s_lo, s_hi = cert.s
    for i in range(MS):
        s = sum(fdot(PHI_F[i], q) ** 2 for q in Qx)
        if not X(s_lo[i]) <= s <= X(s_hi[i]):
            out.append(f"{tag} after draw {j}: |y_{i}|^2 = {float(s)!r} outside [{s_lo[i]!r}, {s_hi[i]!r}]")
    Ql = [[X(v) for v in col] for col in cert.q]
    if len(Ql) != j + 1:
        return out + [f"{tag} after draw {j}: {len(Ql)} stored columns"]
    k = j + 1
    g0 = sum((fdot(Ql[a], Ql[b]) - (a == b)) ** 2 for a in range(k) for b in range(k))
    qf = sum(fdot(q, q) for q in Ql)
    df = sum((Qx[a][n] - Ql[a][n]) ** 2 for a in range(k) for n in range(NS))
    for name, value, bound in (("|G0|^2", g0, cert.g[0]), ("|Q_lo|^2", qf, cert.g[1]), ("|D|^2", df, cert.g[2])):
        if not X(bound) >= value:
            out.append(f"{tag} after draw {j}: {name} = {float(value)!r} above its bound {bound!r}")
    E2 = sum((fdot(Qx[a], Qx[b]) - (a == b)) ** 2 for a in range(k) for b in range(k))
    F = ns["gram_bound"](cert.g)
    if not X(F) ** 2 >= E2:
        out.append(f"{tag} after draw {j}: F = {F!r} below |Q^T Q - I|_F = {float(E2) ** 0.5!r}")
    return out


def orchestration_problems(ns, name, ladder=None):
    """Every claim the orchestration composes, on every plan of a family, against the exact chain rule: yielded one
    by one. `ladder` overrides how many plans are probed with planted targets (LADDER)."""
    ladder = LADDER.get(name, 0) if ladder is None else ladder
    for n, (taken_plan, ts, us) in enumerate(FAMILIES[name]):
        tag = f"{name} plan {n}"
        cert = ns["Certificate"](ns["rows"]((PHI, PHI)))
        taken = []
        for j, u in enumerate(us):
            idx = np.array([i for i in range(MS) if i not in taken])
            B = exact_boundaries(taken)
            for w in probes(u, B, j, n < ladder):
                info = {}
                try:
                    returned = cert.decide(j, idx, w, trace=lambda _j, record, info=info: info.update(record))
                except AssertionError as e:                # EnclosureBroken, the mutant's own class
                    yield f"{tag} draw {j}: {e}"
                    return
                yield from decide_problems(ns, tag, j, B, w, info)
                yield from decision_problems(ns, tag, j, B, w, returned, info)
            if j == len(taken_plan):
                break
            taken.append(taken_plan[j])
            cert.extend(np.array(taken), ts[j])
            yield from state_problems(ns, tag, j, taken, ts, cert)


def first_problem(ns, **kw):
    for name in sorted(FAMILIES):
        found = next(orchestration_problems(ns, name, **kw), None)
        if found:
            return found
    return None


SHIPPED = {"Certificate": c.Certificate, "rows": c.rows, "gram_bound": c.gram_bound, "TAU": c.TAU}


@pytest.mark.parametrize("family", sorted(FAMILIES))
def test_every_claim_the_orchestration_composes_holds_exactly_on_tight_inputs(family):
    assert list(orchestration_problems(SHIPPED, family)) == []


def test_the_ladder_reaches_both_decisions_and_the_hand_off():
    """On the ladder, the shipped decide certifies some planted targets and hands others off: the probes reach both
    sides of its enclosures, so a decision taken from other weights has somewhere to go wrong."""
    certified = handed = 0
    taken_plan, ts, us = FAMILIES["G"][0]
    cert = c.Certificate(c.rows((PHI, PHI)))
    cert.extend(np.array(taken_plan[:1]), ts[0])
    B = exact_boundaries(taken_plan[:1])
    idx = np.array([i for i in range(MS) if i not in taken_plan[:1]])
    for w in probes(us[1], B, 1, True):
        p, _why, _slack = cert.decide(1, idx, w)
        certified += p is not None
        handed += p is None
    assert certified > 50 and handed > 50


def test_the_tight_basis_is_exactly_orthonormal_and_its_enclosure_a_point():
    for a in range(NS):
        for b in range(NS):
            assert sum(PHI_F[i][a] * PHI_F[i][b] for i in range(MS)) == (a == b)
    e = c.rows((PHI, PHI))
    assert all(X(v) == Fraction(NS, MS) for v in (*e.norm[0], *e.norm[1])) and not e.dl1.any()


def test_family_g_is_off_orthonormal_by_about_2_to_the_minus_36_and_family_q_rounds():
    taken, ts, _us = FAMILIES["G"][0]
    q = [sum(Fraction(ts[0][r]) * PHI_F[taken[r]][n] for r in range(1)) for n in range(NS)]
    assert abs(fdot(q, q) - 1 - Fraction(1, 2 ** 36)) < Fraction(1, 2 ** 40)
    rounds = 0
    for taken, ts, _us in FAMILIES["Q"]:
        cert = c.Certificate(c.rows((PHI, PHI)))
        cert.extend(np.array(taken[:1]), ts[0])
        cert.extend(np.array(taken), ts[1])
        lo, hi = c.column(ts[1], c.select((PHI, PHI), np.array(taken)))
        rounds += bool((hi > lo).any())
    assert rounds >= 30


# ---------------------------------------------------------------------------------------------------------------
# verifier-P1's five D8 faults, planted into the orchestration as it wrote them, anchors kept.

HEADER = "# The orchestration: steps composed, nothing computed here.\n"
ANCHOR_S = "        self.s = accumulate(self.s, square(inner(self.e, q)))\n"
ANCHOR_F = "        factors = gram_factors(gram_bound(self.g))\n"
ANCHOR_T = "        t = target(uniform_box(u), last(b))\n"

DECIDE_TRACE = '            trace(j, {"target": t, "bounds": b, "untaken": idx, "position": found.position})\n'

FIVE = {
    "B2a_kept: the Gram sums reset to (0.0, 0.0, 0.0) after every draw":
        [(ANCHOR_S, ANCHOR_S + "        self.g = (0.0, 0.0, 0.0)\n")],
    "B2a_kept, spelled with the registered helper": [(ANCHOR_S, ANCHOR_S + "        self.g = gram_zero()\n")],
    "B2b: gram_factors fed a literal": [(ANCHOR_F, ANCHOR_F + "        factors = gram_factors(0.0)\n")],
    "B4b_kept: u's box collapsed to its lower end":
        [(ANCHOR_T, ANCHOR_T + "        ub = uniform_box(u)\n        t = target((lower(ub), lower(ub)), last(b))\n")],
    "B4c_kept: q's width dropped before inner": [(ANCHOR_S, "        q = (lower(q), lower(q))\n" + ANCHOR_S)],
    "B6_kept: u's ends swapped by a helper": [
        (HEADER, "def ends(x):\n    return x[1], x[0]\n\n\n" + HEADER),
        (ANCHOR_T, ANCHOR_T + "        t = target(ends(uniform_box(u)), last(b))\n")],
}


# verifier-P1's D10: decide traces honestly and RETURNS a decision taken elsewhere. N3b is its fault as written
# (two lines, within the rule's spellings at 6dcd5a1): a position certified on weights without the Gram factor.
# N3d takes the decision on weights with no projection at all. Each is caught by the returned decision's check.
DECISIONS = {
    "N3b: the returned position certified without the Gram factor": [(DECIDE_TRACE, DECIDE_TRACE + (
        "        unsound = gram_factors(gram_bound(gram_zero()))\n"
        "        found = locate(t, boundaries(weights(select(self.e.norm, idx), select(self.s, idx), unsound)))\n"))],
    "N3d: the returned position certified on unprojected weights": [(DECIDE_TRACE, DECIDE_TRACE + (
        "        found = locate(t, boundaries(weights(select(self.e.norm, idx), select(zero(self.M), idx), "
        "factors)))\n"))],
    "N3e: N3b respelled with a second name, which the rule's single assignment does not refuse": [
        (DECIDE_TRACE, DECIDE_TRACE + (
            "        unsound = gram_factors(gram_bound(gram_zero()))\n"
            "        chosen = locate(t, boundaries(weights(select(self.e.norm, idx), select(self.s, idx), "
            "unsound)))\n")),
        ("        if found.position is None:\n            return None, f\"draw {j}: {found.reason}\", None\n"
         "        return found.position, None, clearance(t, b, found.position)\n",
         "        if chosen.position is None:\n            return None, f\"draw {j}: {chosen.reason}\", None\n"
         "        return chosen.position, None, clearance(t, b, chosen.position)\n")],
}


def planted(name):
    source = SOURCE
    for old, new in {**FIVE, **DECISIONS}[name]:
        assert source.count(old) == 1, f"the plant's anchor {old.strip()!r} is gone: re-anchor this plant"
        source = source.replace(old, new)
    return source


@pytest.mark.parametrize("name", sorted(FIVE))
def test_each_of_verifier_p1s_five_fails_the_orchestrations_tight_end_to_end_check(name):
    assert first_problem(load(planted(name))), f"{name} passed the tight end-to-end check"


@pytest.mark.parametrize("name", sorted(DECISIONS))
def test_a_returned_decision_that_differs_from_the_traced_one_fails_the_check(name):
    found = first_problem(load(planted(name)))
    assert found and "decide" in found, f"{name} passed the tight end-to-end check: {found}"


def test_n3b_is_seen_only_by_the_returned_decision_on_the_ladder():
    """What catches N3b: with the ladder off it passes every claim, as it passed the first version of this check."""
    ns = load(planted("N3b: the returned position certified without the Gram factor"))
    assert first_problem(ns, ladder=0) is None
    found = list(orchestration_problems(ns, "G"))
    assert any("and traced" in p for p in found)                   # returned, not what it traced
    assert any("; the exact chain rule's is" in p for p in found)  # and a wrong site, as verifier-P1 found it

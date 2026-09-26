"""The margin's premise, measured against references that share no code with the authority.

docs/DETERMINISM.md's argument: two implementations whose error in
(boundary - target) stays below half the refusal margin decide every draw the
same way. Its premise is that the authority's 256-bit arithmetic errs far less
than the margin, 2^-224. This file measures that error, draw by draw, along
real rolls.

The first gate for it compared the authority at 256 bits with the authority at
512 bits. That compares the code with itself, so an error that does not scale
with the working precision is invisible to it: one binary64 `math.fsum` in the
basis norm put every boundary 2^-51.5 off, and the gate reported 2^-249 (the
P0 verifier, 2026-09-25). So both references here are separate code:

  - EXACTLY, wherever the kernel is rational. cos(2 pi m / L) is rational for
    every m only when L is 1, 2, 3, 4 or 6 (Niven's theorem). There every
    chain-rule weight c_i = K_ii - K_iS K_SS^-1 K_Si is an exact Fraction, and
    so is every boundary and every target u * (N - j). Two tiles:
      pauli-4x4 (L = 4), the shelf's own;
      L = 6, r2 = 1, which is on no shelf. It is here because its arithmetic is
      not accidentally exact: N/M = 5/36 is not dyadic. On L = 4 and 16,
      several binary64 slips (int/int division, a binary64 sum of the initial
      weights or of each draw's total) round to the exact value and change
      nothing, so no output gate there can see them. On L = 6 each one moves
      the boundaries by about 2^-52 (the P0 verifier's third pass).
  - pauli (16x16), an INDEPENDENT chain rule at 512 bits: the closed-form kernel
    (1/M) sum_k cos(2 pi k.d / L), and Schur complements grown one Cholesky
    column per draw. It shares neither orbitals() nor sample()'s projections.
    It is kept beside L = 6: a cosine table rounded to binary64 is invisible
    on L = 6, whose cosines are dyadic, and shows at 2^-51 here.

The shared parts are the definitions, not the arithmetic: the stock's mode set
(stocks.fermi_disc) and the exact uniforms (golden.uniform).
"""
from fractions import Fraction

import mpmath
from mpmath import mp, mpf

from quantum_film.golden import fermi
from quantum_film.golden.uniform import stream, uniform
from quantum_film.stocks import fermi_disc

HEADROOM = 2 ** 16          # the gate: the worst error times this stays below the margin
EXACT_SEEDS = range(1, 21)  # pauli-4x4
L6_SEEDS = range(1, 11)     # L = 6, r2 = 1: on no shelf; its arithmetic is not accidentally exact
REF_SEEDS = (1, 2)          # pauli, 16x16
COS_DEGREES = {0: Fraction(1), 60: Fraction(1, 2), 90: Fraction(0), 120: Fraction(-1, 2), 180: Fraction(-1),
               240: Fraction(-1, 2), 270: Fraction(0), 300: Fraction(1, 2)}


def exact_kernel(L, r2):
    """K as Fractions, for the L whose cosines 2 pi m / L are all rational: 1, 2, 3, 4, 6."""
    if L not in (1, 2, 3, 4, 6):
        raise ValueError(f"L = {L} has an irrational cosine (Niven's theorem): no exact kernel")
    ks = fermi_disc(L, r2)
    sites = [(x, y) for x in range(L) for y in range(L)]          # site index x * L + y

    def k(dx, dy):
        return sum((COS_DEGREES[360 * ((kx * dx + ky * dy) % L) // L] for kx, ky in ks), Fraction(0)) / (L * L)

    return [[k(xi - xj, yi - yj) for xj, yj in sites] for xi, yi in sites]


def _solve(A, B):
    """A X = B over Fractions, by Gaussian elimination (A small and invertible)."""
    n = len(A)
    A = [row[:] for row in A]
    B = [row[:] for row in B]
    for col in range(n):
        piv = next(r for r in range(col, n) if A[r][col] != 0)
        A[col], A[piv] = A[piv], A[col]
        B[col], B[piv] = B[piv], B[col]
        for r in range(n):
            if r != col and A[r][col] != 0:
                f = A[r][col] / A[col][col]
                A[r] = [a - f * b for a, b in zip(A[r], A[col], strict=True)]
                B[r] = [a - f * b for a, b in zip(B[r], B[col], strict=True)]
    return [[b / A[r][r] for b in B[r]] for r in range(n)]


def exact_draws(s, L=4, r2=1):
    """pauli-4x4's roll for stream `s`, exactly: (roll, [(target, boundaries) per draw])."""
    K = exact_kernel(L, r2)
    M, N = L * L, len(fermi_disc(L, r2))
    picks, draws = [], []
    for j in range(N):
        if picks:
            X = _solve([[K[a][b] for b in picks] for a in picks], [[K[a][i] for i in range(M)] for a in picks])
            c = [K[i][i] - sum(K[i][p] * X[r][i] for r, p in enumerate(picks)) for i in range(M)]
        else:
            c = [K[i][i] for i in range(M)]
        total = sum(c[i] for i in range(M) if i not in picks)
        assert total == N - j and all(c[i] >= 0 for i in range(M)), (j, total)
        target = uniform(s, j) * total
        acc, bounds, chosen = Fraction(0), [], None
        for i in range(M):
            if i in picks:
                continue
            acc += c[i]
            bounds.append(acc)
            if target < acc:
                chosen = i
                break
        draws.append((target, bounds))
        picks.append(chosen)
    return sorted(picks), draws


def independent_draws(s, L, r2, prec=512):
    """The chain rule on the closed-form kernel, with Schur complements grown one
    Cholesky column per draw: code that shares nothing with orbitals() or sample()."""
    ks = fermi_disc(L, r2)
    M, N = L * L, len(ks)
    sites = [(x, y) for x in range(L) for y in range(L)]
    with mp.workprec(prec):
        cos = [mpmath.cos(2 * mpmath.pi * m / L) for m in range(L)]
        table = {(dx, dy): mpmath.fsum(cos[(kx * dx + ky * dy) % L] for kx, ky in ks) / M
                 for dx in range(L) for dy in range(L)}

        def K(i, k):
            return table[(sites[i][0] - sites[k][0]) % L, (sites[i][1] - sites[k][1]) % L]

        c = [K(i, i) for i in range(M)]
        W = [[] for _ in range(M)]          # W[i]: site i's components on the picks' Cholesky columns
        picks, draws = [], []
        for j in range(N):
            total = mpmath.fsum(c[i] for i in range(M) if i not in picks)
            u = uniform(s, j)
            target = mpf(u.numerator) / mpf(u.denominator) * total
            acc, bounds, chosen = mpf(0), [], None
            for i in range(M):
                if i in picks:
                    continue
                acc += c[i] if c[i] > 0 else mpf(0)
                bounds.append(acc)
                if target < acc:
                    chosen = i
                    break
            draws.append((target, bounds))
            picks.append(chosen)
            p, lpp = chosen, mpmath.sqrt(c[chosen])
            for i in range(M):
                if i not in picks:
                    w = (K(p, i) - mpmath.fsum(a * b for a, b in zip(W[p], W[i], strict=True))) / lpp
                    W[i].append(w)
                    c[i] -= w * w
    return sorted(picks), draws


def traced(s, L, r2, prec=fermi.PREC):
    draws = []
    roll = fermi.sample(L, r2, s, prec=prec, trace=lambda j, target, bounds: draws.append((target, bounds)))
    return roll, draws


def worst_error(draws, reference):
    """The largest |authority - reference| over every target and boundary, at 1024 bits."""
    worst = mpf(0)
    with mp.workprec(1024):
        def v(x):
            return mpf(x.numerator) / mpf(x.denominator) if isinstance(x, Fraction) else x
        for (t, bs), (t2, bs2) in zip(draws, reference, strict=True):
            worst = max([worst, abs(t - v(t2))] + [abs(a - v(b)) for a, b in zip(bs, bs2, strict=True)])
    return worst


def log2(x):
    return float(mpmath.log(x, 2)) if x else float("-inf")


def test_the_exact_rolls_are_the_authoritys_and_its_error_is_far_inside_the_margin():
    worst = mpf(0)
    for seed in EXACT_SEEDS:
        s = stream("roll", "pauli-4x4", seed)
        roll, draws = traced(s, 4, 1)
        exact, reference = exact_draws(s)
        assert roll == exact, seed
        worst = max(worst, worst_error(draws, reference))
    assert worst * HEADROOM < fermi.margin(), f"error 2^{log2(worst):.1f} against margin 2^-224"


def test_on_a_tile_whose_arithmetic_is_not_accidentally_exact_the_error_is_still_far_inside_the_margin():
    worst = mpf(0)
    for seed in L6_SEEDS:
        s = stream("premise", "L6", seed)
        roll, draws = traced(s, 6, 1)
        exact, reference = exact_draws(s, L=6, r2=1)
        assert roll == exact, seed
        worst = max(worst, worst_error(draws, reference))
    assert worst * HEADROOM < fermi.margin(), f"error 2^{log2(worst):.1f} against margin 2^-224"


def test_an_independent_chain_rule_at_512_bits_agrees_on_the_16x16_stock():
    worst = mpf(0)
    for seed in REF_SEEDS:
        s = stream("roll", "pauli", seed)
        roll, draws = traced(s, 16, 8)
        again, reference = independent_draws(s, 16, 8)
        assert roll == again, seed
        worst = max(worst, worst_error(draws, reference))
    assert worst * HEADROOM < fermi.margin(), f"error 2^{log2(worst):.1f} against margin 2^-224"


def test_the_references_themselves_agree():
    """The exact reference and the 512-bit one, on the 4x4 tile: a reference
    that is wrong would make the gates above measure the wrong distance."""
    for seed in (1, 2, 3):
        s = stream("roll", "pauli-4x4", seed)
        exact, a = exact_draws(s)
        again, b = independent_draws(s, 4, 1)
        assert exact == again and worst_error(b, a) < mpf(2) ** -500, seed


def test_the_basis_lays_the_closed_form_kernel():
    """The P0 verifier found the 16x16 basis held only by its own orthonormality.
    Rows of Phi Phi^T at 256 bits against the closed form at 512 bits."""
    for L, r2 in ((4, 1), (16, 8)):
        rows = fermi.orbitals(L, r2, 256)
        M = L * L
        ks = fermi_disc(L, r2)
        with mp.workprec(512):
            cos = [mpmath.cos(2 * mpmath.pi * m / L) for m in range(L)]
            worst = mpf(0)
            for i in (0, 1, M // 2 + 3, M - 1):
                xi, yi = divmod(i, L)
                for k in range(M):
                    xk, yk = divmod(k, L)
                    closed = mpmath.fsum(cos[(kx * (xi - xk) + ky * (yi - yk)) % L] for kx, ky in ks) / M
                    worst = max(worst, abs(mpmath.fsum(a * b for a, b in zip(rows[i], rows[k], strict=True)) - closed))
        assert worst < mpf(2) ** -240, (L, r2, log2(worst))

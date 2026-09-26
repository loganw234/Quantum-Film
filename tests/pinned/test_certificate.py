"""Each step of the certificate, held to the exact extremes of its claim on wide synthetic boxes.

In the real problem the enclosures carry slack: when a step was broken on
purpose (its radius dropped, the Gram factor ignored, one bound rounded to
nearest) the rolls still equalled the authority's, and the authority's own
values still lay inside the enclosures, on 33 rolls and the planted streams
(2026-09-25). Neither end-to-end gate can see a fault in how the bounds are
put together. So every step is checked here on boxes wide enough that each of
its terms matters, against the exact rational extremes of what it claims to
bound, and each check is shown to catch one planted fault in its step.
"""
from fractions import Fraction

import numpy as np
import pytest

from quantum_film.pinned import bounds as bd
from quantum_film.pinned import certificate as c


def X(v):
    return Fraction(float(v))


def box(rng, shape, width, sign=None):
    lo = rng.standard_normal(shape) if sign is None else np.abs(rng.standard_normal(shape)) * sign
    return lo, lo + rng.uniform(0, width, shape)


def corners_min_max(pairs):
    """min and max of a product over its corners, exactly: pairs of (lo, hi) boxes."""
    (a, b), (x, y) = pairs
    vals = [X(a) * X(x), X(a) * X(y), X(b) * X(x), X(b) * X(y)]
    return min(vals), max(vals)


# --- times_positive -----------------------------------------------------------------------------------


def problems_times_positive(fn):
    rng = np.random.default_rng(11)
    a_lo = rng.uniform(0.2, 1.0, 300)
    a_hi = a_lo + rng.uniform(1e-3, 0.1, 300)
    t_lo, t_hi = box(rng, 300, 0.5)
    lo, hi = fn(a_lo, a_hi, t_lo, t_hi)
    out = []
    for i in range(300):
        mn, mx = corners_min_max(((a_lo[i], a_hi[i]), (t_lo[i], t_hi[i])))
        if not (X(lo[i]) <= mn and X(hi[i]) >= mx):
            out.append(i)
    return out


def test_times_positive_bounds_every_product_in_its_box():
    assert problems_times_positive(c.times_positive) == []


def test_times_positive_check_sees_endpoints_paired_regardless_of_sign():
    assert problems_times_positive(lambda a_lo, a_hi, t_lo, t_hi: (bd.mul_lo(a_lo, t_lo), bd.mul_hi(a_hi, t_hi)))


# --- square and rows ----------------------------------------------------------------------------------


def problems_square(fn):
    rng = np.random.default_rng(12)
    lo, hi = box(rng, 300, 1.0)
    s_lo, s_hi = fn(lo, hi)
    out = []
    for i in range(300):
        a, b = X(lo[i]), X(hi[i])
        mn = Fraction(0) if a <= 0 <= b else min(a * a, b * b)
        if not (X(s_lo[i]) <= mn and X(s_hi[i]) >= max(a * a, b * b)):
            out.append(i)
    return out


def test_square_bounds_every_square_in_its_box_including_across_zero():
    assert problems_square(c.square) == []


def test_square_check_sees_the_endpoints_squared_as_they_come():
    assert problems_square(lambda lo, hi: (bd.mul_lo(lo, lo), bd.mul_hi(hi, hi)))


def problems_rows(fn):
    rng = np.random.default_rng(13)
    lo, hi = box(rng, (20, 6), 0.3)
    e = fn(lo, hi)
    out = []
    for i in range(20):
        mins, maxs = [], []
        for a, b in zip(lo[i], hi[i], strict=True):
            a, b = X(a), X(b)
            mins.append(Fraction(0) if a <= 0 <= b else min(a * a, b * b))
            maxs.append(max(a * a, b * b))
        if not (X(e.n_lo[i]) <= sum(mins) and X(e.n_hi[i]) >= sum(maxs)):
            out.append(("n", i))
        if X(e.l1[i]) < sum(abs(X(a)) for a in lo[i]) or X(e.dl1[i]) < sum(X(b) - X(a) for a, b in
                                                                              zip(lo[i], hi[i], strict=True)):
            out.append(("l1", i))
    return out


def test_rows_bound_every_norm_in_their_box():
    assert problems_rows(c.rows) == []


def test_rows_check_sees_a_norm_taken_from_the_lower_bounds_alone():
    def wrong(lo, hi):
        e = c.rows(lo, hi)
        N = lo.shape[1]
        return c.Enclosure(e.lo, e.hi, bd.dot_lo(lo.ravel(), lo.ravel(), N), e.n_hi, e.l1, e.dl1)
    assert problems_rows(wrong)


# --- column ---------------------------------------------------------------------------------------------


def problems_column(fn):
    rng = np.random.default_rng(14)
    out = []
    for trial in range(20):
        k, N = rng.integers(1, 6), rng.integers(1, 8)
        t = rng.standard_normal(k)
        if trial % 3 == 0:
            t[rng.integers(0, k)] = 0.0
        a_lo, a_hi = box(rng, (k, N), 0.2)
        q_lo, q_hi = fn(t, a_lo, a_hi)
        for n in range(N):
            ext = [corners_min_max(((t[m], t[m]), (a_lo[m, n], a_hi[m, n]))) for m in range(k)]
            if not (X(q_lo[n]) <= sum(e[0] for e in ext) and X(q_hi[n]) >= sum(e[1] for e in ext)):
                out.append((trial, n))
    return out


def test_column_bounds_every_combination_of_rows_in_their_box():
    assert problems_column(c.column) == []


def test_column_check_sees_the_lower_rows_taken_whatever_the_sign_of_t():
    assert problems_column(lambda t, a_lo, a_hi: (bd.dot_lo(np.tile(t, a_lo.shape[1]), a_lo.T.ravel(), len(t)),
                                                  bd.dot_hi(np.tile(t, a_lo.shape[1]), a_hi.T.ravel(), len(t))))


def test_column_check_sees_the_box_passed_upside_down():
    assert problems_column(lambda t, a_lo, a_hi: c.column(t, a_hi, a_lo))


# --- inner --------------------------------------------------------------------------------------------


def problems_inner(fn):
    rng = np.random.default_rng(15)
    lo, hi = box(rng, (12, 7), 0.1)
    e = c.rows(lo, hi)
    out = []
    for trial in range(10):
        q_lo, q_hi = box(rng, 7, 0.1)
        y_lo, y_hi = fn(e, q_lo, q_hi)
        for i in range(12):
            ext = [corners_min_max(((lo[i, n], hi[i, n]), (q_lo[n], q_hi[n]))) for n in range(7)]
            if not (X(y_lo[i]) <= sum(x[0] for x in ext) and X(y_hi[i]) >= sum(x[1] for x in ext)):
                out.append((trial, i))
    return out


def test_inner_bounds_every_product_of_a_row_and_a_column_in_their_boxes():
    assert problems_inner(c.inner) == []


def test_inner_check_sees_the_radius_dropped():
    def point_only(e, q_lo, q_hi):
        M, N = e.lo.shape
        rep = np.tile(q_lo, M)
        return bd.dot_lo(e.lo.ravel(), rep, N), bd.dot_hi(e.lo.ravel(), rep, N)
    assert problems_inner(point_only)


def test_inner_check_sees_half_the_radius_dropped():
    def rows_only(e, q_lo, q_hi):
        blind = c.Enclosure(e.lo, e.hi, e.n_lo, e.n_hi, e.l1, np.zeros_like(e.dl1))
        return c.inner(blind, q_lo, q_hi)
    assert problems_inner(rows_only)


# --- the Gram bound and its factors ---------------------------------------------------------------------


def gram_setup(seed, noise, width, k=3, N=6):
    """k rows near an orthonormal set (off by up to `noise`), each entry's box `width` wide. A wide noise with
    a narrow box makes G0 = Q_lo^T Q_lo - I the whole of E; no noise with a wide box makes D its whole."""
    rng = np.random.default_rng(seed)
    Q0 = np.linalg.qr(rng.standard_normal((N, k)))[0].T         # orthonormal rows (numpy: test data)
    Q_lo = Q0 + rng.uniform(-noise, noise, (k, N))
    Q_hi = Q_lo + rng.uniform(0, width, (k, N))
    return rng, Q_lo, Q_hi


SETUPS = [(0.08, 1e-9), (0.0, 0.05), (0.03, 0.02)]


def accumulate(terms, Q_lo, Q_hi):
    g0 = qf = df = 0.0
    prev = []
    for j in range(len(Q_lo)):
        dg, dq, dd = terms(prev, Q_lo[j], Q_hi[j])
        g0, qf, df = bd.add_hi(g0, dg), bd.add_hi(qf, dq), bd.add_hi(df, dd)
        prev.append(Q_lo[j])
    return g0, qf, df


def frobenius2(Q):
    """|Q Q^T - I|_F^2 exactly, Q's rows the columns of the text's Q."""
    k = len(Q)
    return sum((sum(Q[a][n] * Q[b][n] for n in range(len(Q[a]))) - (1 if a == b else 0)) ** 2
               for a in range(k) for b in range(k))


def problems_gram(terms=c.gram_terms, bound=c.gram_bound):
    out = []
    for seed, (noise, width) in enumerate(SETUPS * 3):
        rng, Q_lo, Q_hi = gram_setup(seed, noise, width)
        F = X(bound(*accumulate(terms, Q_lo, Q_hi)))
        picks = [Q_lo, Q_hi] + [Q_lo + rng.uniform(0, 1, Q_lo.shape) * (Q_hi - Q_lo) for _ in range(4)]
        for Q in picks:
            if frobenius2([[X(v) for v in row] for row in Q]) > F * F:
                out.append(seed)
    return out


def test_the_gram_bound_holds_for_every_basis_in_the_box():
    assert problems_gram() == []


def test_the_gram_check_sees_the_off_diagonal_counted_once():
    def once(q_prev, q_lo, q_hi):
        g, q, d = c.gram_terms(q_prev, q_lo, q_hi)
        Q = np.vstack(q_prev + [q_lo])
        k, N = Q.shape
        rep = np.tile(q_lo, k)
        g_lo, g_hi = bd.dot_lo(Q.ravel(), rep, N), bd.dot_hi(Q.ravel(), rep, N)
        g_lo[-1], g_hi[-1] = bd.sub_lo(g_lo[-1], 1.0), bd.sub_hi(g_hi[-1], 1.0)
        b = c.magnitudes(g_lo, g_hi)[1]
        return bd.dot_hi(b, b, k)[0], q, d
    assert problems_gram(terms=once)


def test_the_gram_check_sees_the_cross_term_dropped():
    def no_cross(g0, qf, df):
        return bd.add_hi(bd.sqrt_hi(g0), df)
    assert problems_gram(bound=no_cross)


def problems_factors(factors):
    """y^T (Q Q^T)^-1 y / |y|^2 at the extreme eigenvectors must lie within the factors' bounds."""
    out = []
    for seed, (noise, width) in enumerate(SETUPS * 3):
        rng, Q_lo, Q_hi = gram_setup(seed, noise, width)
        g = factors(c.gram_bound(*accumulate(c.gram_terms, Q_lo, Q_hi)))
        for Q in (Q_lo, Q_hi):
            G = [[sum(X(Q[a, n]) * X(Q[b, n]) for n in range(Q.shape[1])) for b in range(len(Q))]
                 for a in range(len(Q))]
            inv = invert(G)
            for y in np.linalg.eigh(Q @ Q.T)[1].T:              # the extreme directions (numpy: test data)
                y = [X(v) for v in y]
                num = sum(y[a] * inv[a][b] * y[b] for a in range(len(y)) for b in range(len(y)))
                den = sum(v * v for v in y)
                if not X(g[0]) * den <= num <= X(g[1]) * den:
                    out.append(seed)
    return out


def invert(G):
    """The exact inverse of a small matrix of Fractions (Gauss-Jordan)."""
    n = len(G)
    A = [row[:] + [Fraction(int(i == j)) for j in range(n)] for i, row in enumerate(G)]
    for col in range(n):
        piv = next(r for r in range(col, n) if A[r][col] != 0)
        A[col], A[piv] = A[piv], A[col]
        p = A[col][col]
        A[col] = [v / p for v in A[col]]
        for r in range(n):
            if r != col and A[r][col] != 0:
                f = A[r][col]
                A[r] = [a - f * b for a, b in zip(A[r], A[col], strict=True)]
    return [row[n:] for row in A]


def test_the_gram_factors_bound_the_inverse_gram_matrix():
    assert problems_factors(c.gram_factors) == []


def test_the_factors_check_sees_the_gram_matrix_taken_for_the_identity():
    assert problems_factors(lambda F: (1.0, 1.0))


def test_a_gram_bound_not_below_one_certifies_nothing():
    assert c.gram_factors(1.0) is None and c.gram_factors(float("nan")) is None


# --- weights, target, locate --------------------------------------------------------------------------------


def problems_weights(fn):
    rng = np.random.default_rng(16)
    n_lo, n_hi = box(rng, 200, 0.2)
    s_lo, s_hi = box(rng, 200, 0.2, sign=1.0)
    g_lo = rng.uniform(0.5, 1.0, 200)
    g_hi = g_lo + rng.uniform(0, 0.5, 200)
    c_lo, c_hi = fn(n_lo, n_hi, s_lo, s_hi, g_lo, g_hi)
    out = []
    for i in range(200):
        mn = X(n_lo[i]) - X(s_hi[i]) * X(g_hi[i])
        mx = X(n_hi[i]) - X(s_lo[i]) * X(g_lo[i])
        if not (X(c_lo[i]) <= mn and X(c_hi[i]) >= mx):
            out.append(i)
    return out


def test_weights_bound_every_residual_in_their_boxes():
    assert problems_weights(c.weights) == []


def test_weights_check_sees_the_projection_taken_at_the_wrong_end():
    assert problems_weights(lambda n_lo, n_hi, s_lo, s_hi, g_lo, g_hi:
                            (bd.sub_lo(n_lo, bd.mul_hi(s_lo, g_lo)), bd.sub_hi(n_hi, bd.mul_lo(s_hi, g_hi))))


def problems_target(fn):
    rng = np.random.default_rng(17)
    u_lo = rng.uniform(0, 1, 200)
    u_hi = np.minimum(u_lo + rng.uniform(0, 0.1, 200), 1.0)
    s_lo, s_hi = box(rng, 200, 1.0, sign=1.0)
    t_lo, t_hi = fn(u_lo, u_hi, s_lo, s_hi)
    tau = Fraction(c.TAU)
    return [i for i in range(200) if not (X(t_lo[i]) <= X(u_lo[i]) * X(s_lo[i]) - tau
                                          and X(t_hi[i]) >= X(u_hi[i]) * X(s_hi[i]) + tau)]


def test_the_target_bounds_every_product_and_clears_it_by_tau():
    assert problems_target(c.target) == []


def test_tau_is_2_to_the_minus_200_and_2_to_the_24_times_the_authoritys_margin():
    """The check above reads TAU from the module, so its value is pinned here: a certified draw clears its boundaries
    by TAU, far past the margin inside which the authority refuses (quantum_film/pinned/sampler.py, point 2)."""
    from quantum_film.golden import fermi
    from quantum_film.pinned.control import mpf_fraction
    assert Fraction(c.TAU) == Fraction(1, 2 ** 200) == 2 ** 24 * mpf_fraction(fermi.margin())


def test_the_target_check_sees_the_uniform_taken_at_the_wrong_end():
    assert problems_target(lambda u_lo, u_hi, s_lo, s_hi: (bd.mul_lo(u_hi, s_lo), bd.mul_hi(u_lo, s_hi)))


def problems_locate(fn):
    """Claims: a returned position p has every boundary before it certifiably below the target, and its own
    certifiably above; a first boundary that overlaps the target is never skipped."""
    b_lo = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
    b_hi = b_lo + 0.01
    out = []
    for t_lo, t_hi, want in ((0.25, 0.26, 2), (0.05, 0.06, 0), (0.205, 0.215, None), (0.52, 0.53, None),
                             (0.305, 0.45, None), (0.211, 0.29, 2)):
        p, why = fn(t_lo, t_hi, b_lo, b_hi)
        if p != want or (p is None) == (why is None):
            out.append((t_lo, t_hi, p))
    return out


def test_locate_certifies_only_a_position_whose_boundaries_all_clear():
    assert problems_locate(c.locate) == []


def test_locate_check_sees_an_overlapping_boundary_skipped():
    def first_clear_above(t_lo, t_hi, b_lo, b_hi):
        above = b_lo > t_hi
        return (int(np.argmax(above)), None) if above.any() else (None, "none")
    assert problems_locate(first_clear_above)


@pytest.mark.parametrize("F", [0.0, 1e-15, 0.25])
def test_the_factors_are_ordered_and_bracket_one(F):
    g_lo, g_hi = c.gram_factors(F)
    assert g_lo <= 1.0 <= g_hi and (F > 0) == (g_lo < 1.0 < g_hi)

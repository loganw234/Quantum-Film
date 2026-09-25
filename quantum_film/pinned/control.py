"""Planted near-ties: the negative control, and where each precision starts to decide wrongly.

Random streams never test a certificate. Their targets land 2^-15 or farther
from every boundary (CLAUDE.md, "Random seeds never test a margin"), so a
certificate that certified everything, and a binary64 chain that decided
everything itself, would both pass any number of them. The control therefore
PLANTS a draw's target where plain binary64 decides it the other way from the
exact chain rule, and asks two samplers about that same stream:

  - the certified sampler with its hand-off removed (`handoff=False`: a draw
    the certificate cannot clear is decided by the binary64 chain) must
    DISAGREE with the authority;
  - the certified sampler as shipped must AGREE with it, by handing the roll
    off at the planted draw.

HOW A PLANT IS MADE. At draw j of a base stream, boundary p's exact value B
comes from the authority's trace (256 bits; its error, about 2^-249, is far
below every distance here), so the exact chain passes boundary p exactly when
u > u* = B / (N - j): the untaken weights sum to N - j exactly. The binary64
chain passes it exactly when RN(RN(u) * total) >= its own boundary b, which
holds for u above one midpoint m between two neighbouring binary64 numbers,
found with libcft. Every u strictly between u* and m is decided one way by
the exact chain and the other way by binary64, and the plant takes their
midpoint, an exact Fraction. Planting at the LAST draw makes the two rolls
differ in a crystal, not only in an order, and keeps every earlier draw
certified, so the hand-off is the planted draw's alone.

`ladder` plants targets at fixed relative distances from a boundary instead,
to show at which distance each format starts to decide wrongly and where the
certificate starts handing off.
"""
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from ..golden import fermi as golden
from ..golden.uniform import uniform as golden_uniform
from ..stocks import fermi_disc
from . import cft, sampler
from .cft import FP64, RNE
from .encode import to_fraction


def mpf_fraction(x):
    """An mpf as an exact Fraction, sign first (mpf.man_exp drops the sign: P2, 2026-09-25)."""
    sign, man, exp, _bc = x._mpf_
    v = Fraction(man) * Fraction(2) ** exp
    return -v if sign else v


def golden_draws(L, r2, stream_bytes, uniform_fn=None):
    """The authority's roll, its draws in order, and each draw's (target, boundaries), all exact Fractions."""
    order, taken, seen = [], set(), []

    def watch(_j, target, bounds):
        order.append([i for i in range(L * L) if i not in taken][len(bounds) - 1])
        taken.add(order[-1])
        seen.append((mpf_fraction(target), [mpf_fraction(b) for b in bounds]))

    crystals = golden.sample(L, r2, stream_bytes, uniform_fn=uniform_fn or golden_uniform, trace=watch)
    return crystals, order, seen


def chain_trace(L, r2, stream_bytes, uniform_fn=None, fmt="fp64"):
    """The plain chain's roll (certification off) and each draw's target, total and boundaries."""
    seen = {}
    r = sampler.roll(L, r2, stream_bytes, uniform_fn=uniform_fn, certify=False, fmt=fmt,
                     trace=lambda j, info: seen.__setitem__(j, info))
    return r, seen


def planted(j, u):
    """The authority's uniforms, with draw j's replaced by u."""
    def fn(s, i):
        return u if i == j else golden_uniform(s, i)
    return fn


@dataclass
class Plant:
    uniform_fn: object
    draw: int
    boundary: int            # position among the untaken sites
    u: Fraction
    distance: Fraction       # |exact target - exact boundary| at the planted draw
    boundary_value: Fraction
    float_error: Fraction    # |binary64 boundary - exact boundary| there


def _boundary(bounds, chain_bounds):
    """The boundary the authority's target fell below, or the nearest earlier one, between two sites of
    positive weight: the site before it by the authority's exact boundaries, the site after it by the binary64
    chain's (the authority's trace stops at its chosen site). A site of exact weight zero is a forbidden
    crystal, and a plant beside one would test that site rather than the boundary."""
    for p in range(len(bounds) - 1, -1, -1):
        after = (to_fraction(FP64, chain_bounds[p + 1]) - to_fraction(FP64, chain_bounds[p])
                 if p + 1 < len(chain_bounds) else 0)
        if bounds[p] > (bounds[p - 1] if p else 0) and after > Fraction(1, 2 ** 20):
            return p
    raise ValueError("no boundary to plant at on this draw")


def _switch(bound, total):
    """The smallest binary64 v with RN(v * total) >= bound, both binary64 (one-element arrays)."""
    v = cft.div(FP64, RNE, bound, total)

    def reaches(x):
        return not cft.less(FP64, cft.mul(FP64, RNE, x, total), bound)[0]

    while not reaches(v):
        v = np.nextafter(v, np.inf)
    while reaches(np.nextafter(v, -np.inf)):
        v = np.nextafter(v, -np.inf)
    return v


def plant(L, r2, stream_bytes, j=None):
    """A uniform function equal to the stream's except at draw j (default: the last), where the exact chain
    rule and the plain binary64 chain decide boundary p differently."""
    N = len(fermi_disc(L, r2))
    j = N - 1 if j is None else j
    _crystals, order, seen = golden_draws(L, r2, stream_bytes)
    chain, info = chain_trace(L, r2, stream_bytes)
    if chain.draws[:j] != order[:j]:
        raise ValueError(f"the binary64 chain parted from the authority before draw {j}; plant on another stream")
    bounds_exact = seen[j][1]
    p = _boundary(bounds_exact, info[j]["bounds"])
    B = bounds_exact[p]
    u_star = B / (N - j)
    b = info[j]["bounds"][p:p + 1]
    v = _switch(b, info[j]["total"])
    m = (to_fraction(FP64, np.nextafter(v, -np.inf)) + to_fraction(FP64, v)) / 2
    u = (u_star + m) / 2
    if not 0 < u < 1 or u == m:
        raise ValueError("no plant at this boundary")
    return Plant(planted(j, u), j, p, u, abs(u - u_star) * (N - j), B,
                 abs(to_fraction(FP64, b) - B))


def control(L, r2, stream_bytes):
    """The negative control on one planted stream: returns every roll, and the two verdicts it must give."""
    pl = plant(L, r2, stream_bytes)
    widths = {}

    def watch(j, info):
        if j == pl.draw:
            (t_lo, t_hi), (b_lo, b_hi) = info["target"], info["bounds"]
            widths["target"] = float(t_hi - t_lo)
            widths["boundary"] = float(b_hi[pl.boundary] - b_lo[pl.boundary])

    authority = golden.sample(L, r2, stream_bytes, uniform_fn=pl.uniform_fn)
    without = sampler.roll(L, r2, stream_bytes, uniform_fn=pl.uniform_fn, handoff=False)
    shipped = sampler.roll(L, r2, stream_bytes, uniform_fn=pl.uniform_fn, trace=watch)
    plain = sampler.roll(L, r2, stream_bytes, uniform_fn=pl.uniform_fn, certify=False)
    return {"plant": pl, "authority": authority, "without_handoff": without, "with_handoff": shipped,
            "plain_fp64": plain, "enclosure_widths": widths,
            "without_handoff_disagrees": without.crystals != authority,
            "with_handoff_agrees": shipped.crystals == authority}


def ladder(L, r2, stream_bytes, distances, j=None):
    """Targets planted at each relative distance d (both sides) of draw j's boundary: how each format and the
    certified sampler decide them, against the authority. Returns rows of dicts."""
    N = len(fermi_disc(L, r2))
    j = N - 1 if j is None else j
    _c, order, seen = golden_draws(L, r2, stream_bytes)
    bounds_exact = seen[j][1]
    p = _boundary(bounds_exact, chain_trace(L, r2, stream_bytes)[1][j]["bounds"])
    B = bounds_exact[p]
    rows = []
    for d in distances:
        for side in (-1, 1):
            u = B * (1 + side * Fraction(d)) / (N - j)
            fn = planted(j, u)
            row = {"distance": d, "side": side}
            try:
                row["authority"] = golden.sample(L, r2, stream_bytes, uniform_fn=fn)
            except golden.TieRefusal:
                row["authority"] = "refused"
            for fmt in ("fp32", "fp64", "fp128"):
                row[fmt] = sampler.roll(L, r2, stream_bytes, uniform_fn=fn, certify=False, fmt=fmt).crystals
            try:
                r = sampler.roll(L, r2, stream_bytes, uniform_fn=fn)
                row["certified"] = r.crystals
                row["handed_off"] = r.handed_off
            except golden.TieRefusal:
                row["certified"], row["handed_off"] = "refused", True
            rows.append(row)
    return rows


__all__ = ["control", "ladder", "plant", "golden_draws", "chain_trace", "mpf_fraction"]

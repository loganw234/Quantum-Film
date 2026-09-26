"""The certified sampler against the authority: equal rolls, enclosures that contain the authority's own values,
refusals that survive, and audits that fire when the certificate lies."""
import dataclasses
import threading
from fractions import Fraction

import pytest

from quantum_film import fixer
from quantum_film.golden import fermi
from quantum_film.golden.uniform import stream, uniform
from quantum_film.pinned import basis, certificate, cft, control, sampler
from quantum_film.pinned.cft import FP64

SLACK = Fraction(1, 2 ** 240)       # the authority's values are within about 2^-249 of exact


def test_every_pauli_4x4_roll_is_the_authoritys_and_none_is_handed_off():
    for seed in range(1, 201):
        s = stream("roll", "pauli-4x4", seed)
        r = sampler.roll(4, 1, s)
        assert r.crystals == fermi.sample(4, 1, s), seed
        assert not r.handed_off and len(r.slack) == 5


def enclosed(L, r2, s):
    """The certified roll, checked draw by draw: every boundary the authority compared its target with, and
    the target itself, lie inside the certificate's enclosures. Returns the roll."""
    crystals, order, seen = control.golden_draws(L, r2, s)
    boxes = {}
    r = sampler.roll(L, r2, s, trace=lambda j, info: boxes.__setitem__(j, info))
    assert r.crystals == crystals and r.draws == order and not r.handed_off
    for j, (target, bounds) in enumerate(seen):
        (t_lo, t_hi), (b_lo, b_hi) = boxes[j]["target"], boxes[j]["bounds"]
        assert Fraction(t_lo) - SLACK <= target <= Fraction(t_hi) + SLACK, j
        for k, b in enumerate(bounds):
            assert Fraction(b_lo[k]) - SLACK <= b <= Fraction(b_hi[k]) + SLACK, (j, k)
        assert boxes[j]["position"] == len(bounds) - 1
    return r


def test_the_enclosures_contain_the_authoritys_boundaries_and_targets_on_pauli_4x4():
    for seed in range(1, 31):
        enclosed(4, 1, stream("roll", "pauli-4x4", seed))


def test_every_pauli_roll_is_the_authoritys_with_its_values_inside_the_enclosures():
    for seed in range(1, 4):
        r = enclosed(16, 8, stream("roll", "pauli", seed))
        assert len(r.slack) == 25


def test_an_exact_tie_the_authority_refuses_gets_no_pinned_answer():
    def on_the_boundary(_s, j):
        return Fraction(1, 16) if j == 0 else Fraction(1, 3)

    with pytest.raises(fermi.TieRefusal, match="refuses"):
        sampler.roll(4, 1, b"tie", uniform_fn=on_the_boundary)


def near(delta):
    """tests/golden/test_golden_fermi.py's planted(): every c_i starts at 5/16 and the total is 5 on pauli-4x4, so
    u = 1/16 + delta/5 puts the first target delta past the boundary after site 0."""
    def fn(_s, j):
        return Fraction(1, 16) + Fraction(delta) / 5 if j == 0 else uniform(b"planted", j)
    return fn


@pytest.mark.parametrize("side", [1, -1])
def test_a_target_inside_the_authoritys_margin_is_refused_on_either_side_of_the_boundary(side):
    """2^-240 above AND below: a refusal checked on one side only passed every golden gate (verifier-P0's third
    pass, defect 3), so the mirror is planted too."""
    with pytest.raises(fermi.TieRefusal, match="refuses"):
        sampler.roll(4, 1, b"near-tie", uniform_fn=near(side * Fraction(1, 2 ** 240)))


@pytest.mark.parametrize("side,laid", [(1, 1), (-1, 0)])
def test_a_target_the_authority_decides_but_binary64_cannot_see_is_handed_off_and_answered_as_the_authority(
        side, laid):
    fn = near(side * Fraction(1, 2 ** 200))
    r = sampler.roll(4, 1, b"clear", uniform_fn=fn)
    assert r.handed_off and r.draw == 0 and "draw 0" in r.reason
    assert r.crystals == fermi.sample(4, 1, b"clear", uniform_fn=fn) and laid in r.crystals


def lying(real, at):
    """Certificate.decide, planted with a lie: at draw 0 it certifies the wrong site, then it cannot certify."""
    def decide(self, j, idx, u, trace=None):
        p, why, sl = real(self, j, idx, u, trace)
        if j == 0:
            return at(p, len(idx)), None, (1.0, 1.0)
        return None, "planted: cannot certify", None
    return decide


def test_the_hand_off_audits_a_certificate_that_decided_a_draw_wrongly(monkeypatch):
    monkeypatch.setattr(sampler.Certificate, "decide", lying(sampler.Certificate.decide, lambda p, n: (p + 1) % n))
    with pytest.raises(sampler.EnclosureBroken, match="the authority drew"):
        sampler.roll(4, 1, stream("roll", "pauli-4x4", 1))


def test_the_hand_off_audits_a_certificate_that_decided_a_draw_the_authority_refuses(monkeypatch):
    monkeypatch.setattr(sampler.Certificate, "decide", lying(sampler.Certificate.decide, lambda p, n: 0))

    def tie(_s, j):
        return Fraction(1, 16) if j == 0 else Fraction(1, 3)

    with pytest.raises(sampler.EnclosureBroken, match="refused draw 0"):
        sampler.roll(4, 1, b"tie", uniform_fn=tie)


def test_an_enclosure_that_misses_the_exact_total_is_refused_by_name(monkeypatch):
    real = certificate.enclosure(4, 1)
    shifted = dataclasses.replace(real, norm=(real.norm[0] + 0.25, real.norm[1] + 0.25))
    monkeypatch.setattr(certificate, "enclosure", lambda L, r2: shifted)
    with pytest.raises(sampler.EnclosureBroken, match="N - j"):
        sampler.roll(4, 1, stream("roll", "pauli-4x4", 1))


def test_a_negative_weight_bound_is_refused_by_name(monkeypatch):
    real = sampler.Certificate.extend

    def inflated(self, rows, t):
        real(self, rows, t)
        self.s = (self.s[0] + 1.0, self.s[1])          # |P phi|^2 claimed above |phi|^2 = 5/16

    monkeypatch.setattr(sampler.Certificate, "extend", inflated)
    with pytest.raises(sampler.EnclosureBroken, match="negative"):
        sampler.roll(4, 1, stream("roll", "pauli-4x4", 1))


def cached_tables():
    e = certificate.enclosure(4, 1)
    return {"enclosure": (*e.box, *e.norm, e.l1, e.dl1), "basis": (basis.basis(4, 1, FP64),),
            "modes": basis.modes(4, 1)}


@pytest.mark.parametrize("name", ["enclosure", "basis", "modes"])
def test_every_cached_table_is_read_only(name):
    """verifier-P1's D4: the caches were writable, and a caller that wrote into one changed later rolls."""
    for a in cached_tables()[name]:
        assert not a.flags.writeable
        with pytest.raises(ValueError, match="read-only"):
            a[0] = a[0]


def test_verifier_p1s_swap_of_two_cached_rows_is_refused_and_the_rolls_stay_the_authoritys():
    lo = certificate.enclosure(4, 1).box[0]
    with pytest.raises(ValueError, match="read-only"):
        lo[[0, 5]] = lo[[5, 0]]
    for seed in range(1, 21):
        s = stream("roll", "pauli-4x4", seed)
        assert sampler.roll(4, 1, s).crystals == fermi.sample(4, 1, s)


def test_a_uniform_that_is_not_an_exact_fraction_is_refused():
    with pytest.raises(ValueError, match="exact Fraction"):
        sampler.roll(4, 1, b"x", uniform_fn=lambda _s, _j: 0.5)


def test_a_tile_edge_that_is_not_a_power_of_two_is_refused_by_name():
    with pytest.raises(ValueError, match="power of two"):
        sampler.roll(6, 1, b"x")


def test_the_sampler_refuses_to_run_off_the_main_thread():
    caught = []

    def work():
        try:
            sampler.roll(4, 1, b"x")
        except cft.ThreadRefusal as e:
            caught.append(e)

    t = threading.Thread(target=work)
    t.start()
    t.join()
    assert len(caught) == 1 and "main thread" in str(caught[0])


def test_certification_off_runs_in_all_three_formats_and_only_binary64_certifies():
    s = stream("roll", "pauli-4x4", 1)
    for fmt in ("fp32", "fp64", "fp128"):
        r = sampler.roll(4, 1, s, certify=False, fmt=fmt)
        assert len(set(r.crystals)) == 5 and not r.certified and not r.handed_off
    with pytest.raises(ValueError, match="binary64"):
        sampler.roll(4, 1, s, fmt="fp32")


def test_lay_draws_the_fixers_stream_and_refuses_another_family():
    assert sampler.lay("pauli-4x4", 3).crystals == fixer.lay("pauli-4x4", 3)["crystals"]
    with pytest.raises(LookupError, match="binomial"):
        sampler.lay("poisson", 1)

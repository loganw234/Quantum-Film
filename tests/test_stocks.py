"""The shelf holds itself to its own admission rules."""
import importlib

import pytest

from quantum_film.stocks import DERIVED, OPERATOR, STOCKS, fermi_disc, params


def entries(stock):
    return {k: v for k, v in stock.items() if isinstance(v, dict) and "kind" in v}


@pytest.mark.parametrize("sid", sorted(STOCKS))
def test_every_parameter_is_derived_or_a_named_operators_number(sid):
    for key, e in entries(STOCKS[sid]).items():
        assert e["kind"] in (OPERATOR, DERIVED), f"{sid}.{key}"
        assert e.get("why"), f"{sid}.{key} carries no reason"
        if e["kind"] == OPERATOR:
            lo, hi = e["range"]
            assert lo <= e["value"] <= hi, f"{sid}.{key} = {e['value']} outside its stated range {lo}..{hi}"
        else:
            assert e["value"] in STOCKS, f"{sid}.{key} derives from an unknown stock {e['value']!r}"


@pytest.mark.parametrize("sid", sorted(STOCKS))
def test_a_shelf_stock_has_an_authority_and_a_planned_one_is_refused_by_name(sid):
    s = STOCKS[sid]
    assert s["status"] in ("shelf", "planned")
    if s["status"] == "shelf":
        importlib.import_module(s["authority"])
        p = params(sid)
        assert p["N"] >= 1 and p["M"] == p["L"] ** 2
    else:
        assert s["authority"] is None
        with pytest.raises(LookupError, match="planned"):
            params(sid)


def test_an_unknown_stock_is_refused_by_name():
    with pytest.raises(KeyError, match="unknown stock"):
        params("tri-x")


def test_the_disc_is_symmetric_and_refuses_the_nyquist_row():
    for L, r2 in ((4, 1), (16, 8), (16, 20)):
        ks = set(fermi_disc(L, r2))
        assert all((-kx, -ky) in ks for kx, ky in ks)
    with pytest.raises(ValueError, match="Nyquist"):
        fermi_disc(4, 4)


def test_pauli_and_poisson_compare_at_equal_density():
    assert params("poisson")["L"] == params("pauli")["L"]
    assert params("poisson")["N"] == params("pauli")["N"] == len(fermi_disc(16, 8))

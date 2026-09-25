"""Negative records: fixed once, checked from the record alone, refused by name."""
import copy
import json
import pathlib
import random

import pytest

from quantum_film import fixer

VEC = pathlib.Path(__file__).parent / "vectors"


@pytest.fixture(scope="module")
def roll():
    return fixer.lay("pauli-4x4", 1)


def test_a_golden_roll_is_fixed_intact_and_reproduces_bit_for_bit(roll):
    assert fixer.check(roll) == []
    same, _again = fixer.reproduce(roll)
    assert same


def test_the_frozen_records_check_and_the_tampered_one_is_refused():
    for name in ("negative-pauli-4x4-seed1.json", "negative-pauli-seed1.json", "negative-poisson-seed1.json"):
        assert fixer.check(json.loads((VEC / name).read_text(encoding="utf-8"))) == [], name
    problems = fixer.check(json.loads((VEC / "negative-tampered.json").read_text(encoding="utf-8")))
    assert any(p.startswith("digest") for p in problems)


def test_the_digest_does_not_depend_on_key_order(roll):
    items = list(roll.items())
    random.Random(7).shuffle(items)
    assert fixer.digest(dict(items)) == roll["digest"]


def refused(rec, prefix):
    rec["digest"] = fixer.digest(rec)          # re-sealed, so only the named rule can object
    problems = fixer.check(rec)
    assert any(p.startswith(prefix) for p in problems), problems


def test_each_rule_refuses_by_name(roll):
    r = copy.deepcopy(roll)
    r["crystals"] = list(reversed(r["crystals"]))
    refused(r, "crystals: not strictly increasing")
    r = copy.deepcopy(roll)
    r["crystals"] = r["crystals"][:-1] + [r["crystals"][-2]]
    refused(r, "crystals: not strictly increasing")
    r = copy.deepcopy(roll)
    r["crystals"] = r["crystals"][:-1] + [16]
    refused(r, "crystals: a site outside")
    r = copy.deepcopy(roll)
    r["crystals"] = r["crystals"][:-1]
    refused(r, "count")
    r = copy.deepcopy(roll)
    r["law"]["fermi_r2"] = 2
    refused(r, "law")
    r = copy.deepcopy(roll)
    r["source"] = {"kind": "qpu"}
    refused(r, "source: a roll from a device must carry fixed_at")
    r = copy.deepcopy(roll)
    r["stock"] = "speckle"
    refused(r, "stock")


def test_the_fixer_refuses_to_fix_a_layout_the_law_forbids():
    with pytest.raises(ValueError, match="count"):
        fixer.fix("pauli-4x4", [0, 1, 2], {"kind": "golden", "stream": ["roll", "pauli-4x4", 0]})


def test_a_device_roll_cannot_be_reproduced_only_read(roll):
    r = copy.deepcopy(roll)
    r["source"] = {"kind": "atlas-emu", "fixed_at": "2026-09-25T00:00:00Z"}
    with pytest.raises(ValueError, match="only be read"):
        fixer.reproduce(r)

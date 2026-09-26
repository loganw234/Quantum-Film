"""Negative records: fixed once, checked from the record alone, refused by name."""
import copy
import json
import pathlib
import random

import pytest

from quantum_film import fixer

VEC = pathlib.Path(__file__).resolve().parent.parent / "vectors"


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


def test_a_golden_roll_must_name_its_own_roll_stream(roll):
    """verifier-P0 A2, A4: check once accepted streams that reproduce() and
    stream() refuse."""
    for parts in (["roll", "pauli", 1], ["roll", "pauli-4x4", True], ["roll", "pauli-4x4"], ["draw", "pauli-4x4", 1]):
        r = copy.deepcopy(roll)
        r["source"]["stream"] = parts
        refused(r, "source: a golden roll's stream")


def test_a_golden_roll_carries_no_wall_clock_time(roll):
    r = copy.deepcopy(roll)
    r["source"]["fixed_at"] = "2026-09-25T18:00:00Z"
    refused(r, "source: a golden roll's source is exactly")


def test_the_law_is_compared_as_json_not_as_python(roll):
    """verifier-P0 A5: true == 1 and 16.0 == 16 in Python, and the law check
    once used Python's ==."""
    for key, value in (("fermi_r2", True), ("M", 16.0)):
        r = copy.deepcopy(roll)
        r["law"][key] = value
        refused(r, "law")


def test_a_record_carries_exactly_its_fields(roll):
    r = copy.deepcopy(roll)
    r["note"] = "an unsealed reading"
    refused(r, "fields: unexpected")


def test_a_later_version_still_reproduces_the_same_roll(roll, monkeypatch):
    """verifier-P0 6b: the digest covers the version that fixed a record, so a
    version bump once made reproduce() reject every correct roll."""
    monkeypatch.setattr(fixer, "__version__", "0.1.1")
    same, again = fixer.reproduce(roll)
    assert same and again["digest"] != roll["digest"]


def test_a_seed_is_an_integer_and_is_never_truncated():
    with pytest.raises(ValueError, match="a seed is an integer"):
        fixer.lay("pauli-4x4", 1.9)


def cli(tmp_path, capsys, *bodies):
    paths = []
    for i, body in enumerate(bodies):
        p = tmp_path / f"record{i}.json"
        p.write_bytes(body.encode("utf-8"))
        paths.append(str(p))
    rc = fixer.main(["check", *paths])
    return rc, capsys.readouterr().out


def test_the_command_line_accepts_a_record_in_its_canonical_text(tmp_path, capsys, roll):
    rc, out = cli(tmp_path, capsys, fixer.text(roll))
    assert rc == 0 and out.startswith("fixed"), out


def test_a_file_with_a_second_crystals_key_is_refused(tmp_path, capsys, roll):
    """verifier-P0 6a: a file carrying two crystal lists was accepted with the
    genuine digest; a reader that takes the first sees other crystals."""
    body = fixer.text(roll).replace('"code":', '"crystals": [\n  2,\n  3,\n  7,\n  8,\n  12\n ],\n "code":', 1)
    rc, out = cli(tmp_path, capsys, body)
    assert rc == 1 and "a key appears twice: ['crystals']" in out, out


def test_a_file_whose_bytes_differ_from_its_text_is_refused(tmp_path, capsys, roll):
    body = json.dumps(roll, sort_keys=True, indent=4) + "\n"
    rc, out = cli(tmp_path, capsys, body)
    assert rc == 1 and "bytes: the file is not the record's canonical text" in out, out


def test_a_malformed_record_is_refused_by_name_and_the_next_file_is_still_checked(tmp_path, capsys, roll):
    rc, out = cli(tmp_path, capsys, '{"stock": []}\n', fixer.text(roll))
    assert rc == 1 and "stock: [] is not on the shelf" in out and "\nfixed" in out, out


def test_a_golden_roll_names_exactly_the_authority_that_lays_it(roll):
    """verifier-P0's re-check, N1 and N3: check once looked neither inside the
    authority nor at which sampler it named."""
    for named in ({"module": "quantum_film.golden.fermi", "prec": 256, "at": "2026-09-25T18:00:00Z"},
                  {"module": "quantum_film.golden.binomial"}, "quantum_film.golden.fermi",
                  {"module": "quantum_film.golden.fermi", "prec": 320}):
        r = copy.deepcopy(roll)
        r["source"]["authority"] = named
        refused(r, "source: a golden roll of 'pauli-4x4' names its authority")


def test_the_code_field_is_exactly_the_version(roll):
    """verifier-P0's re-check, N2: a wall-clock time rode in `code`, and
    reproduce() ignored it."""
    r = copy.deepcopy(roll)
    r["code"]["fixed_at"] = "2026-09-25T18:00:00Z"
    refused(r, "code: exactly")


def test_the_lay_command_refuses_a_seed_that_is_not_an_integer(capsys):
    assert fixer.main(["lay", "pauli-4x4", "1.9"]) == 2
    assert "REFUSED: a seed is an integer" in capsys.readouterr().out


def test_the_lay_command_refuses_a_stock_that_is_not_on_the_shelf(capsys):
    for stock in ("nosuch", "speckle"):
        assert fixer.main(["lay", stock, "1"]) == 2
        assert capsys.readouterr().out.startswith("REFUSED: ")

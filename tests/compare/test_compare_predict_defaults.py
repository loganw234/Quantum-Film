"""tools/hw_predict.py's defaults, held to the plan: every simulating test passes its shots explicitly, so a changed
default passed them all (verifier-P2, round 3: SHOTS one short and SEED moved, 33 of 33 passed). The tool refuses
import, so its constants are read from its source; the shots are held to quantum_film.ibm.bundle.PLAN, the table
every bundle is frozen from, and the basis and expected set to the same plan."""
import ast
import pathlib

import pytest

from quantum_film.ibm import bundle

ROOT = pathlib.Path(__file__).resolve().parents[2]
SEED = 20261003       # the seed the committed predictions state (docs/records/2026-10-05/ibm/*/prediction-*.json)
ROLE_OF = {"law": "law", "xx": "coherence-xx", "yy": "coherence-yy", "known-answer": "known-answer"}


def constants(source, names=("ROLES", "BASIS", "SHOTS", "EXPECTED", "SEED")):
    """These module-level constants of a source text, each evaluated from its own expression with no builtins and
    no names (they are literals and string products, "Z" * 16)."""
    out = {}
    for node in ast.parse(source).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in names):
            out[node.targets[0].id] = eval(compile(ast.Expression(node.value), "<hw_predict>", "eval"),  # noqa: S307
                                           {"__builtins__": {}}, {})
    assert set(out) == set(names), f"hw_predict.py no longer assigns {sorted(set(names) - set(out))}"
    return out


def plan():
    return {name: (basis, shots) for _job, circuits in bundle.PLAN for name, _role, basis, shots in circuits}


def held(c):
    """The named ways these constants differ from the plan; [] when they agree."""
    p, out = plan(), []
    for role, name in ROLE_OF.items():
        if c["SHOTS"].get(role) != p[name][1]:
            out.append(f"SHOTS[{role!r}] is {c['SHOTS'].get(role)}, the plan's {name} has {p[name][1]}")
        if c["BASIS"].get(role) != p[name][0]:
            out.append(f"BASIS[{role!r}] is not the plan's {name} basis")
    if set(c["SHOTS"]) != set(ROLE_OF) or tuple(c["ROLES"]) != tuple(ROLE_OF):
        out.append("the roles are not law, xx, yy, known-answer")
    if c["SEED"] != SEED:
        out.append(f"SEED is {c['SEED']}, not {SEED}")
    if tuple(c["EXPECTED"]) != bundle.KNOWN_ANSWER:
        out.append(f"EXPECTED is {c['EXPECTED']}, the plan's known answer is {bundle.KNOWN_ANSWER}")
    return out


def test_hw_predicts_defaults_are_the_plans_shots_and_the_committed_seed():
    c = constants((ROOT / "tools" / "hw_predict.py").read_text(encoding="utf-8"))
    assert held(c) == []


@pytest.mark.parametrize("old, new", [
    ('"law": 24576, "xx": 4096', '"law": 24575, "xx": 4096'),      # verifier-P2's D1, in part
    ('"known-answer": 1024}', '"known-answer": 1023}'),
    ("SEED = 20261003", "SEED = 20261004"),                          # verifier-P2's D2
    ('"xx": "XX" + "Z" * 14', '"xx": "YY" + "Z" * 14'),
    ("EXPECTED = (0, 1, 3, 7, 12)", "EXPECTED = (0, 1, 3, 7, 13)"),
])
def test_a_moved_default_is_named(old, new):
    """Negative controls: verifier-P2's plants, made in a copy of the source text."""
    source = (ROOT / "tools" / "hw_predict.py").read_text(encoding="utf-8")
    assert source.count(old) == 1
    assert held(constants(source.replace(old, new)))

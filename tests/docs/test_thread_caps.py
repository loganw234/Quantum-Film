"""The round's thread caps, by value, wherever they are written (round 3: the owner's machine was maxed out by an
uncapped simulation, lead.md 2026-10-03). Each test helper pins that its children receive its own CAPS dict, which
says nothing about the values: OMP_NUM_THREADS made 12 there passed every test (verifier-P2, 2026-10-05, C2). So
the values are held here, read as text: the two stage lines that run qiskit, and the two helpers' CAPS."""
import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
RULE = {"OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "QISKIT_IN_PARALLEL": "FALSE"}
STAGES = ("tests/compare/predict", "tests/hardware/qiskit")
HELPERS = ("tests/compare/predict/test_compare_predict.py", "tests/hardware/qiskit/hwq.py")


def stage_caps(runner_text, directory):
    """The `env NAME=VALUE ...` prefix of the stage line that runs this directory."""
    m = re.search(rf"^\s*env ((?:[A-Z_]+=\S+ )+)bash verify/pytest-stage\.sh {re.escape(directory)}\s*$", runner_text,
                  re.MULTILINE)
    return dict(kv.split("=", 1) for kv in m.group(1).split()) if m else None


def helper_caps(source):
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and [getattr(t, "id", None) for t in node.targets] == ["CAPS"]:
            return ast.literal_eval(node.value)
    return None


def found(texts):
    """{place: its caps} for the runner's two stage lines and the two helpers."""
    out = {f"verify/run.sh, the {d} stage": stage_caps(texts["verify/run.sh"], d) for d in STAGES}
    out.update({h: helper_caps(texts[h]) for h in HELPERS})
    return out


def texts():
    return {p: (ROOT / p).read_text(encoding="utf-8") for p in ("verify/run.sh", *HELPERS)}


def test_every_place_the_caps_are_written_holds_the_rounds_values():
    assert {place: caps for place, caps in found(texts()).items() if caps != RULE} == {}


@pytest.mark.parametrize("path, old, new", [
    ("tests/compare/predict/test_compare_predict.py", '"OMP_NUM_THREADS": "2"', '"OMP_NUM_THREADS": "12"'),  # C2
    ("tests/hardware/qiskit/hwq.py", '"MKL_NUM_THREADS": "1"', '"MKL_NUM_THREADS": "8"'),
    ("verify/run.sh", "QISKIT_IN_PARALLEL=FALSE bash verify/pytest-stage.sh tests/hardware/qiskit",
     "QISKIT_IN_PARALLEL=TRUE bash verify/pytest-stage.sh tests/hardware/qiskit"),
    ("verify/run.sh", "env OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 QISKIT_IN_PARALLEL=FALSE bash "
                      "verify/pytest-stage.sh tests/compare/predict",
     "bash verify/pytest-stage.sh tests/compare/predict"),                                    # the prefix dropped
])
def test_a_moved_or_dropped_cap_is_named(path, old, new):
    """Negative controls, each made in a copy of the text: verifier-P2's C2, and one per other place."""
    t = texts()
    assert t[path].count(old) == 1
    t[path] = t[path].replace(old, new)
    assert {place for place, caps in found(t).items() if caps != RULE}

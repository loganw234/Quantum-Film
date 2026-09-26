"""The authority imports nothing it could share with what it judges (METHOD §1).

The rule is checked mechanically: golden/ may import the standard library,
mpmath, the stock table (the definition itself) and its own modules. The
circuits must not import golden: two implementations that share a helper
agree with each other for free, and that agreement would be worth nothing.
"""
import ast
import pathlib
import sys

PKG = pathlib.Path(__file__).resolve().parents[2] / "quantum_film"
STDLIB = set(sys.stdlib_module_names)


def imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield 0, a.name
        elif isinstance(node, ast.ImportFrom):
            yield node.level, node.module or ""


def test_the_golden_model_imports_only_the_stdlib_mpmath_the_shelf_and_itself():
    for f in sorted((PKG / "golden").glob("*.py")):
        for level, name in imports(f):
            if level == 0:
                assert name.split(".")[0] in STDLIB | {"mpmath"}, f"{f.name} imports {name}"
            elif level == 1:
                pass                                        # golden's own modules
            else:
                assert (level, name) == (2, "stocks"), f"{f.name} imports ..{name}"


def test_the_circuits_do_not_import_the_golden_model():
    for f in sorted((PKG / "circuits").glob("*.py")):
        for _level, name in imports(f):
            assert "golden" not in name, f"{f.name} imports {name}"


def test_the_check_can_see_a_forbidden_import(tmp_path):
    """Negative control for the rule above: a planted numpy import is caught."""
    bad = tmp_path / "planted.py"
    bad.write_text("import numpy as np\nfrom ..circuits import givens\n", encoding="utf-8")
    found = list(imports(bad))
    assert (0, "numpy") in found and (2, "circuits") in found
    assert "numpy" not in STDLIB | {"mpmath"}


# The authority does no binary64 arithmetic at all. A binary64 slip that is
# inert on today's shelf (the initial weights K_ii = N/M are dyadic when L is a
# power of two, and each draw's total is the integer N - j) changes no output
# there, so no output gate on the shelf can see it (the P0 verifier's re-check,
# 2026-09-25). This rule reads the source, as a cheap first line. It reads
# SPELLINGS, and says so: it cannot see int/int true division (`2 / M`), which
# needs the types. The output gate that sees every slip the verifier found,
# that one included, is the exact L = 6 reference in test_golden_premise.py,
# a tile whose arithmetic is not accidentally exact.
EXACT_MATH = {"floor", "ceil", "comb", "gcd", "isqrt"}      # exact on ints and Fractions
INEXACT = {"cmath", "statistics", "random", "decimal", "importlib", "numpy"}


def binary64(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    maths = {"math"} | {a.asname for n in ast.walk(tree) if isinstance(n, ast.Import)
                        for a in n.names if a.name == "math" and a.asname}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            yield node.lineno, f"the float literal {node.value!r}"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("float", "__import__"):
            yield node.lineno, f"{node.func.id}()"
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == "math":
            yield from ((node.lineno, f"math.{a.name}") for a in node.names if a.name not in EXACT_MATH)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module == "mpmath" \
                and any(a.name == "fp" for a in node.names):
            yield node.lineno, "mpmath's fp context (binary64)"
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            yield from ((node.lineno, f"import {n}") for n in names if n.split(".")[0] in INEXACT)
        elif isinstance(node, ast.Attribute) and node.attr == "__float__":
            yield node.lineno, "__float__"
        elif isinstance(node, ast.Attribute) and node.attr == "fp" and isinstance(node.value, ast.Name) \
                and node.value.id in ("mpmath", "mp"):
            yield node.lineno, "mpmath's fp context (binary64)"
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in maths \
                and node.attr not in EXACT_MATH:
            yield node.lineno, f"math.{node.attr}"


def test_the_golden_model_does_no_binary64_arithmetic():
    found = [f"{f.name}:{line}: {what}" for f in sorted((PKG / "golden").glob("*.py")) for line, what in binary64(f)]
    assert found == []


def test_the_binary64_rule_sees_each_slip(tmp_path):
    planted = tmp_path / "planted.py"
    planted.write_text("import math\nfrom math import floor, fsum\nimport statistics\n"
                       "x = math.fsum([1])\ny = float(2)\nz = 1.01\nw = floor(3)\n", encoding="utf-8")
    found = sorted(what for _line, what in binary64(planted))
    assert found == sorted(["math.fsum", "import statistics", "math.fsum", "float()", "the float literal 1.01"]), found


def test_the_binary64_rule_sees_the_respellings_the_verifier_used(tmp_path):
    """The P0 verifier's third pass: a math alias, mpmath's fp context,
    __float__ and importlib each passed the first version of this rule."""
    planted = tmp_path / "respelled.py"
    planted.write_text("import math as _m\nfrom mpmath import fp\nimport mpmath\nimport importlib\n"
                       "a = _m.fsum([1])\nb = x.__float__()\nc = mpmath.fp.fsum([1])\n"
                       "d = __import__('numpy')\n", encoding="utf-8")
    found = sorted(what for _line, what in binary64(planted))
    assert found == sorted(["mpmath's fp context (binary64)", "import importlib", "math.fsum", "__float__",
                            "mpmath's fp context (binary64)", "__import__()"]), found

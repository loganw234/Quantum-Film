"""The authority imports nothing it could share with what it judges (METHOD §1).

The rule is checked mechanically: golden/ may import the standard library,
mpmath, the stock table (the definition itself) and its own modules. The
circuits must not import golden: two implementations that share a helper
agree with each other for free, and that agreement would be worth nothing.
"""
import ast
import pathlib
import sys

PKG = pathlib.Path(__file__).resolve().parent.parent / "quantum_film"
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

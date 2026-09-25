"""Every script that calls Atlas at module level refuses to be imported (CLAUDE.md).

An import of a probe script without a guard re-ran nine Atlas jobs on
2026-09-25, and the P0 verifier then found seven more scripts open to the
same accident. A module qualifies when a module-level statement calls a name
it imported from an Atlas client (moth, probe, quantum_film.atlas.client), or
a function of its own that does. It passes when an
`if __name__ != "__main__": raise ...` comes before that call, or when the
call sits under `if __name__ == "__main__":`.
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLIENTS = {"moth", "probe", "client", "quantum_film.atlas.client"}
SCANNED = ("research", "tools", "quantum_film")


def _names_main(test, op):
    return (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == "__name__"
            and len(test.ops) == 1 and isinstance(test.ops[0], op)
            and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value == "__main__")


def _calls(node, names, modules):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            f = sub.func
            if (isinstance(f, ast.Name) and f.id in names) or (
                    isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in modules):
                return sub.lineno
    return None


def unguarded(src):
    """The line of the first module-level Atlas call that no guard stops, or None."""
    tree = ast.parse(src)
    names, modules = set(), set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module in CLIENTS:
            names |= {a.asname or a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module == "quantum_film.atlas":
            modules |= {a.asname or a.name for a in node.names if a.name == "client"}
        elif isinstance(node, ast.Import):
            modules |= {a.asname or a.name for a in node.names if a.name in CLIENTS}
    defs = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    grew = True
    while grew:                                  # a function that calls one that calls Atlas, and so on
        grew = False
        for fn in defs:
            if fn.name not in names and _calls(fn, names, modules):
                names.add(fn.name)
                grew = True
    for node in tree.body:
        if isinstance(node, ast.If) and _names_main(node.test, ast.NotEq) \
                and any(isinstance(b, ast.Raise) for b in node.body):
            return None                          # nothing below it runs on an import
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.If) and _names_main(node.test, ast.Eq):
            continue
        line = _calls(node, names, modules)
        if line:
            return line
    return None


def test_every_script_that_calls_atlas_refuses_import():
    bad = []
    for d in SCANNED:
        for f in sorted((ROOT / d).rglob("*.py")):
            line = unguarded(f.read_text(encoding="utf-8"))
            if line:
                bad.append(f"{f.relative_to(ROOT).as_posix()}:{line}")
    assert bad == []


def test_an_unguarded_atlas_script_is_caught_and_a_guarded_one_is_not():
    assert unguarded("from probe import run\nrun('x')\n") == 2
    assert unguarded("import moth\nmoth.call('GET', '/')\n") == 2
    assert unguarded("from moth import call\n\n\ndef main():\n    call('GET', '/')\n\n\nmain()\n") == 8
    assert unguarded('"""doc"""\nif __name__ != "__main__":\n    raise ImportError("no")\n'
                     "from probe import run\nrun('x')\n") is None
    assert unguarded("from moth import call\n\n\ndef main():\n    call('GET', '/')\n\n\n"
                     "if __name__ == '__main__':\n    main()\n") is None

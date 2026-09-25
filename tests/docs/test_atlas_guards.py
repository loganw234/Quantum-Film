"""No module calls Atlas because it was imported (CLAUDE.md).

An import of a probe script re-ran nine Atlas jobs on 2026-09-25. Two rules
hold that shut:

  1. A SCRIPT (anything under research/ or tools/) that imports an Atlas
     client in any form refuses to be imported: an
     `if __name__ != "__main__": raise ...` at module level, with nothing but
     the docstring and imports before it. A module that another script
     imports (research's probe.py, fermion_tile.py) cannot refuse import; it is
     held by rule 2 instead.
  2. No module anywhere (the package under quantum_film/ included, where a
     library module cannot refuse import) calls an Atlas client in code that
     runs at import: module-level statements, the bodies of module-level
     if/try/with/for/while blocks and of classes, decorators and default
     arguments.

The first version of this gate tracked a few import spellings, and the P0
verifier passed seven others through it: a dotted `import
quantum_film.atlas.client`, a star import, `from . import client`, an import
inside `try`, and a call in a class body, a decorator or a default argument.
Rule 1 no longer depends on spelling. Rule 2 reads all seven, and they are
this file's negative controls.

An Atlas client is a module whose last name is `moth`, `probe` or `client`
(research's clients, and quantum_film.atlas.client), however it is imported.
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
CLIENTS = {"moth", "probe", "client"}
SCRIPTS = ("research", "tools")
EVERYWHERE = ("research", "tools", "quantum_film")


def _is_client(dotted):
    return dotted.rsplit(".", 1)[-1] in CLIENTS


def _names_main(test, op):
    return (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == "__name__"
            and len(test.ops) == 1 and isinstance(test.ops[0], op)
            and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value == "__main__")


def _refusal(node):
    return isinstance(node, ast.If) and _names_main(node.test, ast.NotEq) and any(
        isinstance(b, ast.Raise) for b in node.body)


def imports_a_client(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(_is_client(a.name) for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom):
            if _is_client(node.module or "") or any(a.name in CLIENTS for a in node.names):
                return True
    return False


def script_problem(src):
    """Rule 1: None, or why this script may run Atlas when imported."""
    tree = ast.parse(src)
    if not imports_a_client(tree):
        return None
    for i, node in enumerate(tree.body):
        if _refusal(node):
            return None
        docstring = i == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        if not (docstring or isinstance(node, (ast.Import, ast.ImportFrom))):
            return f"line {node.lineno}: imports an Atlas client and runs code before refusing import"
    return "imports an Atlas client and never refuses import"


class _Bindings:
    """What each name at module level means: a client module, or a callable from one."""

    def __init__(self):
        self.modules, self.callables, self.star = set(), set(), False

    def learn(self, node):
        if isinstance(node, ast.Import):
            for a in node.names:
                if _is_client(a.name):
                    self.modules.add(a.asname or a.name)     # `import a.b.client` is called as a.b.client.x
        elif isinstance(node, ast.ImportFrom):
            if _is_client(node.module or ""):
                for a in node.names:
                    if a.name == "*":
                        self.star = True
                    else:
                        self.callables.add(a.asname or a.name)
            else:
                self.modules |= {a.asname or a.name for a in node.names if a.name in CLIENTS}

    def is_atlas(self, func):
        parts = []
        while isinstance(func, ast.Attribute):
            parts.append(func.attr)
            func = func.value
        if not isinstance(func, ast.Name):
            return False
        dotted = ".".join([func.id, *reversed(parts)])
        if dotted in self.callables:
            return True
        return any(dotted.startswith(m + ".") for m in self.modules)


def _calls(node, b):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call) and b.is_atlas(sub.func):
            return sub.lineno
    return None


def _run_at_import(body, b):
    """Yield the line of each Atlas call in code that runs when the module is imported."""
    for node in body:
        if _refusal(node):
            return
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            b.learn(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for part in [*node.decorator_list, *node.args.defaults, *node.args.kw_defaults]:
                if part is not None and (line := _calls(part, b)):
                    yield line
            if _calls(node, b):                    # a function that calls Atlas is Atlas, if called
                b.callables.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for part in [*node.decorator_list, *node.bases, *(k.value for k in node.keywords)]:
                if line := _calls(part, b):
                    yield line
            yield from _run_at_import(node.body, b)
        elif isinstance(node, ast.If) and _names_main(node.test, ast.Eq):
            continue
        elif isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try)):
            for field in ("body", "orelse", "finalbody"):
                yield from _run_at_import(getattr(node, field, []), b)
            for h in getattr(node, "handlers", []):
                yield from _run_at_import(h.body, b)
            for part in [getattr(node, "test", None), getattr(node, "iter", None),
                         *(i.context_expr for i in getattr(node, "items", []))]:
                if part is not None and (line := _calls(part, b)):
                    yield line
        elif line := _calls(node, b):
            yield line


def import_problem(src):
    """Rule 2: None, or where this module calls Atlas when it is imported."""
    tree = ast.parse(src)
    b = _Bindings()
    lines = list(_run_at_import(tree.body, b))
    if b.star:
        return "a star import of an Atlas client: what it calls cannot be read"
    return f"line {lines[0]}: calls an Atlas client when imported" if lines else None


def imported_by_a_script(files):
    """The stems of modules that some script imports by a plain name (research's sibling imports)."""
    names = set()
    for f in files:
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def test_every_script_that_imports_an_atlas_client_refuses_import():
    files = [f for d in SCRIPTS for f in sorted((ROOT / d).rglob("*.py"))]
    libraries = imported_by_a_script(files)
    bad = [f"{f.relative_to(ROOT).as_posix()}: {p}" for f in files
           if f.stem not in libraries and (p := script_problem(f.read_text(encoding="utf-8")))]
    assert bad == []
    assert {"probe", "fermion_tile"} <= libraries          # the exemption covers what it says, and no less


def test_no_module_calls_atlas_when_imported():
    bad = [f"{f.relative_to(ROOT).as_posix()}: {p}" for d in EVERYWHERE for f in sorted((ROOT / d).rglob("*.py"))
           if (p := import_problem(f.read_text(encoding="utf-8")))]
    assert bad == []


# verifier-P0's seven shapes, each of which passed the first version of this gate.
SEVEN = {
    "dotted import": "import quantum_film.atlas.client\nquantum_film.atlas.client.call('GET', '/')\n",
    "star import": "from quantum_film.atlas.client import *\ncall('GET', '/')\n",
    "relative import": "from . import client\nclient.call('GET', '/')\n",
    "import inside try": "try:\n    from moth import call\nexcept ImportError:\n    call = None\ncall('GET', '/')\n",
    "class body": "from moth import call\n\n\nclass A:\n    x = call('GET', '/')\n",
    "decorator": ("from moth import call\n\n\ndef deco(x):\n    return lambda f: f\n\n\n"
                  "@deco(call('GET', '/'))\ndef f():\n    pass\n"),
    "default argument": "from moth import call\n\n\ndef f(x=call('GET', '/')):\n    pass\n",
}


def test_each_of_the_seven_shapes_is_caught_by_both_rules():
    for name, src in SEVEN.items():
        assert import_problem(src), name
        assert script_problem(src), name


def test_the_forms_that_are_safe_pass_and_the_old_controls_still_fail():
    guarded = ('"""doc"""\nimport sys\nif __name__ != "__main__":\n    raise ImportError("no")\n'
               'from probe import run\nrun("x")\n')
    main_only = ("from moth import call\n\n\ndef main():\n    call('GET', '/')\n\n\n"
                 "if __name__ == '__main__':\n    main()\n")
    library = "from . import client\n\n\ndef fetch(job):\n    return client.call('GET', job)\n"
    assert script_problem(guarded) is None and import_problem(guarded) is None
    assert import_problem(main_only) is None and script_problem(main_only)      # a script still must refuse
    assert import_problem(library) is None
    assert import_problem("from probe import run\nrun('x')\n") == "line 2: calls an Atlas client when imported"
    assert import_problem("from moth import call\n\n\ndef main():\n    call('GET', '/')\n\n\nmain()\n")
    assert script_problem('"""doc"""\nimport sys\nsys.path.insert(0, ".")\nif __name__ != "__main__":\n'
                          '    raise ImportError("no")\nfrom moth import call\n')

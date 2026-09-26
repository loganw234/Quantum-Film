"""Importing a module runs nothing that could reach Atlas (CLAUDE.md).

An import of a probe script re-ran nine Atlas jobs on 2026-09-25. The rule
that holds this shut, for every module under research/, tools/ and
quantum_film/:

    a module either REFUSES IMPORT (an `if __name__ != "__main__": raise ...`
    with nothing before it that calls anything outside the allowlist), or
    runs NOTHING AT IMPORT BUT THE ALLOWLIST below.

The allowlist is pure construction, calls that cannot reach a network, a
process or a file:
  - anything in a pure module: math, fractions, dataclasses, typing, enum,
    collections, itertools, functools, operator, re, struct, hashlib, mpmath,
    and numpy apart from its file functions (load, save, fromfile, ...);
  - pathlib.Path and its resolve/with_name/joinpath/absolute (a path made,
    no file touched); sys.path.insert; os.environ.get;
  - float.fromhex, int.from_bytes, bytes.fromhex, and a few builtins,
    provided the module does not rebind them;
  - the module's own functions whose bodies call only these.
The first allowlist named functions, not modules, and would have refused
the parcels' np.dtype, Fraction, dataclass and math.sqrt at merge.

Code that runs at import is read everywhere it hides: module-level
statements; the bodies of module-level if/try/with/for/while blocks and of
classes; decorators, defaults, annotations and base classes. Only
`if __name__ == "__main__":` blocks and lambda bodies are skipped.

Why an allowlist. Two earlier versions named what to refuse: calls to
modules called client, moth or probe, and the spellings that import them. The
P0 verifier passed over a dozen shapes through them: a dotted import, a star
import, a relative import, an import inside `try`, a wrapper module, an
alias (`fetch = client.call`), `getattr`, `importlib`, curl called directly,
a function-local import, and a class body, a decorator, a default or an
annotation. A library exemption keyed on 28 bare import names was a loophole
too. Against an allowlist the spelling does not matter: anything that is not
pure construction must sit behind a refusal.
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
EVERYWHERE = ("research", "tools", "quantum_film")
BUILTINS = {"set", "frozenset", "dict", "list", "tuple", "sorted", "len", "str", "int", "float", "range",
            "enumerate", "zip", "max", "min", "sum", "abs", "bool", "isinstance", "bytes", "round", "pow"}
BUILTIN_METHODS = {("float", "fromhex"), ("int", "from_bytes"), ("bytes", "fromhex")}
PURE_MODULES = {"math", "fractions", "dataclasses", "typing", "enum", "collections", "itertools", "functools",
                "operator", "re", "struct", "hashlib", "mpmath", "numpy"}
NUMPY_FILES = {"load", "save", "savez", "savez_compressed", "loadtxt", "savetxt", "genfromtxt", "fromfile",
               "tofile", "memmap", "fromregex", "lib", "ctypeslib", "DataSource"}
DOTTED = {"pathlib.Path", "sys.path.insert", "os.environ.get"}
PATH_METHODS = {"resolve", "with_name", "joinpath", "absolute"}


def _names_main(test, op):
    return (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == "__name__"
            and len(test.ops) == 1 and isinstance(test.ops[0], op)
            and isinstance(test.comparators[0], ast.Constant) and test.comparators[0].value == "__main__")


def _refusal(node):
    return isinstance(node, ast.If) and _names_main(node.test, ast.NotEq) and any(
        isinstance(b, ast.Raise) for b in node.body)


class _Module:
    def __init__(self, tree):
        self.imports = {}                  # a module-level name -> the dotted thing it was imported as
        self.bound = set()                 # every other name bound at module level
        for node in tree.body:
            if isinstance(node, ast.Import):
                for a in node.names:
                    self.imports[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                for a in node.names:
                    self.imports[a.asname or a.name] = f"{node.module}.{a.name}"
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.bound.add(node.name)
            for sub in ast.walk(node):
                if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                    self.bound.add(sub.id)
        defs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        self.pure = set()
        grew = True
        while grew:                        # a function of this module is pure if all it calls is allowed
            grew = False
            for name, fn in defs.items():
                if name not in self.pure and all(self.allowed(c) for c in _calls_in(fn.body)):
                    self.pure.add(name)
                    grew = True

    def dotted(self, func):
        parts = []
        while isinstance(func, ast.Attribute):
            parts.append(func.attr)
            func = func.value
        if not isinstance(func, ast.Name):
            return None
        head = self.imports.get(func.id)
        return ".".join([head, *reversed(parts)]) if head else None

    def _path_made(self, node):
        """Is `node` a Path built from allowed calls, possibly through .parent, [i] and PATH_METHODS?"""
        while isinstance(node, (ast.Attribute, ast.Subscript)) or (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in PATH_METHODS):
            node = node.func.value if isinstance(node, ast.Call) else node.value
        return isinstance(node, ast.Call) and self.dotted(node.func) == "pathlib.Path"

    def _unbound_builtin(self, name):
        return name not in self.bound and name not in self.imports

    def allowed(self, call):
        f = call.func
        if isinstance(f, ast.Name) and f.id in BUILTINS and self._unbound_builtin(f.id):
            return True
        if isinstance(f, ast.Name) and f.id in self.pure:
            return True
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and \
                (f.value.id, f.attr) in BUILTIN_METHODS and self._unbound_builtin(f.value.id):
            return True
        dotted = self.dotted(f)
        if dotted in DOTTED:
            return True
        if dotted and dotted.split(".")[0] in PURE_MODULES:
            parts = dotted.split(".")
            return not (parts[0] == "numpy" and any(p in NUMPY_FILES for p in parts[1:]))
        return isinstance(f, ast.Attribute) and f.attr in PATH_METHODS and self._path_made(f.value)


def _calls_in(nodes):
    """Every call in these nodes that runs when they run: lambda bodies are not entered."""
    stack = list(nodes)
    while stack:
        n = stack.pop()
        if isinstance(n, ast.Lambda):
            continue
        if isinstance(n, ast.Call):
            yield n
        stack.extend(ast.iter_child_nodes(n))


def _at_import(body):
    """The calls that run when these module- or class-level statements run."""
    for node in body:
        if _refusal(node):
            return
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = node.args
            parts = [*node.decorator_list, *a.defaults, *(d for d in a.kw_defaults if d is not None),
                     *(x.annotation for x in [*a.posonlyargs, *a.args, *a.kwonlyargs] if x.annotation)]
            parts += [x.annotation for x in (a.vararg, a.kwarg) if x is not None and x.annotation]
            parts += [node.returns] if node.returns else []
            yield from _calls_in(parts)
        elif isinstance(node, ast.ClassDef):
            yield from _calls_in([*node.decorator_list, *node.bases, *(k.value for k in node.keywords)])
            yield from _at_import(node.body)
        elif isinstance(node, ast.If) and _names_main(node.test, ast.Eq):
            continue
        elif isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try)):
            heads = [getattr(node, "test", None), getattr(node, "iter", None),
                     *(i.context_expr for i in getattr(node, "items", []))]
            yield from _calls_in([h for h in heads if h is not None])
            for field in ("body", "orelse", "finalbody"):
                yield from _at_import(getattr(node, field, []))
            for h in getattr(node, "handlers", []):
                yield from _at_import(h.body)
        else:
            yield from _calls_in([node])


def problems(src):
    """The calls this module runs at import that are not pure construction, as 'line: call'."""
    tree = ast.parse(src)
    m = _Module(tree)
    out = []
    for call in _at_import(tree.body):
        if not m.allowed(call):
            out.append(f"line {call.lineno}: {ast.unparse(call.func)}(...)")
    return out


def test_importing_any_module_runs_only_pure_construction_or_is_refused():
    bad = [f"{f.relative_to(ROOT).as_posix()}: {p}" for d in EVERYWHERE for f in sorted((ROOT / d).rglob("*.py"))
           for p in problems(f.read_text(encoding="utf-8"))]
    assert bad == []


# Shapes that passed an earlier version of this gate (the P0 verifier, 2026-09-25), each a negative control.
CAUGHT = {
    "dotted import": "import quantum_film.atlas.client\nquantum_film.atlas.client.call('GET', '/')\n",
    "star import": "from quantum_film.atlas.client import *\ncall('GET', '/')\n",
    "relative import": "from . import client\nclient.call('GET', '/')\n",
    "import inside try": "try:\n    from moth import call\nexcept ImportError:\n    call = None\ncall('GET', '/')\n",
    "class body": "from moth import call\n\n\nclass A:\n    x = call('GET', '/')\n",
    "decorator": "from moth import call\n\n\n@call('GET', '/')\ndef f():\n    pass\n",
    "default argument": "from moth import call\n\n\ndef f(x=call('GET', '/')):\n    pass\n",
    "annotation": "from moth import call\n\n\ndef f(x: call('GET', '/')):\n    pass\n",
    "wrapper module": "from quantum_film.atlas.jobs import submit\nsubmit('pauli-4x4')\n",
    "alias": "from quantum_film.atlas import client\nfetch = client.call\nENGINES = fetch('GET', '/')\n",
    "getattr": "from quantum_film.atlas import client\ngetattr(client, 'call')('GET', '/')\n",
    "importlib": "import importlib\nimportlib.import_module('probe').run('x')\n",
    "curl directly": "import subprocess\nsubprocess.run(['curl', 'https://api.mothquantum.com'])\n",
    "function-local import": "def main():\n    from moth import call\n    call('GET', '/')\n\n\nmain()\n",
    "rebound builtin": "from moth import call\nlen = call\nlen('GET')\n",
    "a Path that is not one": "from moth import call as Path\nPath('x').resolve()\n",
    "numpy's file functions": "import numpy as np\nX = np.load('layouts.npz')\n",
    "a pure module's name on something else": "from moth import call as math\nmath.sqrt(2)\n",
}


def test_each_shape_that_once_passed_is_caught():
    for name, src in CAUGHT.items():
        assert problems(src), name


def test_pure_modules_and_guarded_scripts_pass():
    library = ('"""doc"""\nimport pathlib\nimport re\nimport sys\nfrom functools import lru_cache\n\n'
               "ROOT = pathlib.Path(__file__).resolve().parents[2]\nsys.path.insert(0, str(ROOT))\n"
               "LINK = re.compile(r'x')\nN = len([1, 2])\n\n\ndef _op(v):\n    return {'v': v}\n\n\n"
               "TABLE = {'a': _op(1)}\n\n\n@lru_cache(maxsize=4)\ndef f(x):\n    return x\n\n\n"
               "if __name__ == '__main__':\n    print(f(1))\n")
    guarded = ('"""doc"""\nimport sys\nif __name__ != "__main__":\n    raise ImportError("run it")\n'
               "from probe import run\nrun('x')\n")
    assert problems(library) == [] and problems(guarded) == []
    assert problems("def main():\n    print('x')\n\n\nmain()\n")      # a script's work belongs behind a refusal

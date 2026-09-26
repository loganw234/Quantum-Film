"""quantum_film/pinned/certificate.py read against an ALLOWLIST: what the list does not name, it may not do.

A rule that lists forbidden spellings is bypassed by other spellings. The P0 verifier passed binary64 through the
authority's source rule as int/int division, a `math` alias, mpmath's `fp` context and `__float__`
(verifier-P0.md, 2026-09-25 23:30Z), and this rule's first version, a list of rounding-attribute names, missed ten
respellings of a rounding slip in the certificate (a numpy multiply, bd.cft.add, getattr, a math alias, np.dot,
sum, __mul__, np.float64('0.1'), bd.LO, __import__; P1.md), and its second passed six round-to-nearest conversions
(verifier-P1's D3, 2026-09-26: a Fraction stored into a float64 array by item or slice assignment; np.array with a
positional dtype, np.float64 or float; float.fromhex of 68 significant bits; np.where with an integer past 2^53).
So the certificate is held to what it MAY do:

- IMPORTS: exactly the statements in IMPORTS.
- CALLS: a function or class the module defines; a callable it imports from IMPORTS; bounds' directed functions
  (DIRECTED, each held bit for bit by tests/pinned/test_pinned_bounds.py); the numpy functions in NP_ARITY, which
  only move, select or index, with at most that many positional arguments and no keyword (either would carry a
  dtype, which converts); the builtins in BUILTINS; the methods in METHODS; float.fromhex of one string literal whose
  value is exactly a binary64; and the `trace` observer. Fraction takes integers only.
- NAMES of bd and np: only those, called or not (bd.cft, bd.LO and np.dot are refused even uncalled).
- NO ITEM OR SLICE ASSIGNMENT: numpy converts what it stores into an array, to nearest.
- ARITHMETIC (+ - * // %) between integers only: int literals, the names in INT_NAMES, .M and .N, and len(), one
  operator deep, and integer literals no larger than 2^53, so no integer that meets a float can round. True
  division, powers and matrix products are refused outright: `2 / M` is a rounded float. Unary minus is exact.
  Bitwise operators cannot round and pass.
- An INT_NAME is bound only from an integer (.shape, .size, len, np.argmin, locate, integer arithmetic), or is one
  of TRUSTED_PARAMS; so a float cannot be laundered through one. A name the list relies on (an allowed callable,
  np, bd) is never rebound.
- FLOAT LITERALS are exact: the literal's text is its value (2.0 passes; 0.1 does not).
- No lambda, walrus, global, nonlocal, with, try, match, async, yield or del.
- THE ORCHESTRATION (ORCHESTRATION: the Certificate class and enclosure) only composes steps: it names neither bd nor
  np, subscripts nothing, stars nothing and unpacks nothing, so each interval passes from step to step whole and its
  two ends cannot be swapped or rounded between steps. The steps are held behaviourally, each directed call flipped
  (tests/pinned/test_pinned_certificate.py).

WHICH LAYER HOLDS WHAT. This rule reads spellings, so it holds what can be named: the imports, the calls, the
conversions above, and the orchestration's shape. The tight-input checks in test_pinned_certificate.py hold
behaviour: whatever moves a step's output across its exact value on those inputs, however it is spelled (a flipped
call, a conversion this list never thought of), is seen there, and every directed call is shown to matter. A rounding
that moves no step's output on any input is harmless to the certificate, whatever its spelling.

What the rule rests on, held elsewhere: bounds' directed functions are exact floors and ceilings
(tests/pinned/test_pinned_bounds.py); encode.exact and to_fraction are exact
(tests/pinned/test_pinned_encode.py); basis.angles, assemble and modes are integer and data-movement code, and the
enclosure they build holds the authority's own orbitals (tests/pinned/test_pinned_exact.py).
"""
import ast
import inspect
import pathlib
import re
from fractions import Fraction

import pytest

from quantum_film.pinned import bounds, certificate

IMPORTS = {
    "from dataclasses import dataclass",
    "from fractions import Fraction",
    "from functools import lru_cache",
    "from typing import NamedTuple",
    "import numpy as np",
    "from . import bounds as bd",
    "from .basis import angles, assemble, frozen, modes",
    "from .cft import FP64",
    "from .encode import bounds64, exact, to_fraction",
}
IMPORTED_CALLABLE = {"dataclass", "Fraction", "lru_cache", "NamedTuple", "angles", "assemble", "frozen", "modes",
                     "bounds64", "exact", "to_fraction"}
DIRECTED = {f"{op}_{side}" for op in ("add", "sub", "mul", "div", "sqrt", "cospi", "sinpi", "dot", "scan")
            for side in ("lo", "hi")}
NP_ARITY = {"where": 3, "abs": 1, "tile": 2, "vstack": 1, "zeros": 1, "ones": 1, "argmin": 1, "eye": 1}
NP_VALUES = {"ndarray", "float64", "inf"}
BUILTINS = {"len", "min", "max", "all", "zip"}
METHODS = {"max", "all", "any", "ravel", "append"}
INT_NAMES = {"L", "M", "N", "j", "k", "p"}
TRUSTED_PARAMS = {"L", "j", "p"}        # the tile edge, a draw's index, and a position: each indexes, or refuses
INT_LIMIT = 2 ** 53
ORCHESTRATION = {"Certificate", "enclosure"}
INT_OPS = (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod)
BIT_OPS = (ast.BitAnd, ast.BitOr, ast.BitXor)
FORBIDDEN = tuple(getattr(ast, n) for n in ("Lambda", "NamedExpr", "Global", "Nonlocal", "With", "AsyncWith", "Try",
                                            "TryStar", "Match", "AsyncFunctionDef", "Await", "Yield", "YieldFrom",
                                            "Delete") if hasattr(ast, n))


def _names_only(e):
    """A name, or a chain of attributes on one (self.e)."""
    return isinstance(e, ast.Name) or (isinstance(e, ast.Attribute) and _names_only(e.value))


def _is_self(e, attrs):
    return isinstance(e, ast.Attribute) and isinstance(e.value, ast.Name) and e.value.id == "self" and e.attr in attrs


def is_int(e):
    """An expression that is an integer by its spelling."""
    if isinstance(e, ast.Constant):
        return type(e.value) is int
    if isinstance(e, ast.Name):
        return e.id in INT_NAMES
    if isinstance(e, ast.Attribute) and e.attr in ("M", "N") and _names_only(e.value):
        return True
    if isinstance(e, ast.Call):
        return isinstance(e.func, ast.Name) and e.func.id == "len"
    if isinstance(e, ast.BinOp):
        return isinstance(e.op, INT_OPS) and is_int(e.left) and is_int(e.right)
    if isinstance(e, ast.UnaryOp):
        return isinstance(e.op, ast.USub) and is_int(e.operand)
    return False


def exact_hex(text):
    """The exact value of a hexadecimal floating-point literal ('0x1.8p-3'), or None if it is not one."""
    m = re.fullmatch(r"([+-]?)0[xX]([0-9a-fA-F]*)(?:\.([0-9a-fA-F]*))?[pP]([+-]?[0-9]+)", text)
    if not m or not (m.group(2) or m.group(3)):
        return None
    sign, whole, frac, exp = m.groups()
    frac = frac or ""
    v = Fraction(int(whole + frac, 16), 16 ** len(frac)) * Fraction(2) ** int(exp)
    return -v if sign == "-" else v


def fromhex_exact(node):
    """Whether a float.fromhex call reads one string literal whose value is exactly a binary64 number."""
    if node.keywords or len(node.args) != 1 or not isinstance(node.args[0], ast.Constant) \
            or not isinstance(node.args[0].value, str):
        return False
    text, v = node.args[0].value, exact_hex(node.args[0].value)
    try:
        return v is not None and Fraction(float.fromhex(text)) == v
    except (OverflowError, ValueError):
        return False


def int_source(e):
    """A value an INT_NAME may be bound from."""
    if is_int(e):
        return True
    if isinstance(e, ast.Attribute) and e.attr in ("shape", "size"):
        return True
    if isinstance(e, ast.Call) and ast.unparse(e.func) in ("np.argmin", "locate"):
        return True
    if isinstance(e, ast.IfExp):
        return int_source(e.body) and int_source(e.orelse)
    return False


def orchestration_violations(tree):
    """The orchestration composes steps only: no bd, no np, no subscript, no star, no unpacking."""
    out = []
    for top in tree.body:
        if getattr(top, "name", None) not in ORCHESTRATION:
            continue
        for node in ast.walk(top):
            why = None
            if isinstance(node, ast.Name) and node.id in ("bd", "np"):
                why = f"the orchestration names {node.id}: its arithmetic belongs in a step"
            elif isinstance(node, ast.Subscript):
                why = "the orchestration subscripts: an interval passes whole between steps"
            elif isinstance(node, ast.Starred):
                why = "the orchestration stars an interval open"
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.For, ast.comprehension)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, (ast.Tuple, ast.List)) for t in targets):
                    why = "the orchestration unpacks an interval"
            if why:
                out.append(f"line {node.lineno}: {why}: {ast.unparse(node)[:70]}")
    return out


def violations(source):
    tree = ast.parse(source)
    defined = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    callables = defined | IMPORTED_CALLABLE | BUILTINS | {"trace"}
    reserved = callables | {"np", "bd", "float", "FP64", "self"}
    out = orchestration_violations(tree)

    def bad(node, why):
        out.append(f"line {node.lineno}: {why}: {ast.unparse(node)[:70]}")

    def int_targets(target):
        return [t for t in ast.walk(target) if (isinstance(t, ast.Name) and t.id in INT_NAMES)
                or _is_self(t, ("M", "N"))]

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Subscript) for target in targets for t in ast.walk(target)):
                bad(node, "item or slice assignment: numpy rounds what it stores into an array")
        if isinstance(node, FORBIDDEN):
            bad(node, "a construct the allowlist does not name")
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            if ast.unparse(node) not in IMPORTS:
                bad(node, "an import the allowlist does not name")
        elif isinstance(node, ast.Call):
            f = node.func
            if isinstance(f, ast.Name) and f.id in callables:
                if f.id == "Fraction" and (node.keywords or not all(is_int(a) for a in node.args)):
                    bad(node, "Fraction takes integers only here")
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "bd":
                pass                                       # the attribute itself is checked below
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "np":
                if f.attr not in NP_ARITY:
                    bad(node, "a numpy call the allowlist does not name (np.float64 is a dtype here, not a call)")
                elif node.keywords or len(node.args) > NP_ARITY[f.attr]:
                    bad(node, "a numpy call with a keyword or an extra positional argument (either carries a dtype)")
            elif ast.unparse(f) == "float.fromhex":
                if not fromhex_exact(node):
                    bad(node, "float.fromhex of anything but a literal that is exactly a binary64")
            elif isinstance(f, ast.Attribute) and f.attr in METHODS:
                pass
            else:
                bad(node, "a call the allowlist does not name")
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "bd":
            if node.attr not in DIRECTED:
                bad(node, "bounds is reached only through its directed functions")
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "np":
            if node.attr not in NP_ARITY.keys() | NP_VALUES:
                bad(node, "a numpy name the allowlist does not name")
        elif isinstance(node, ast.BinOp):
            if not isinstance(node.op, BIT_OPS) and not (isinstance(node.op, INT_OPS) and is_int(node.left)
                                                         and is_int(node.right)):
                bad(node, "arithmetic outside bounds: only + - * // % between integers")
            elif isinstance(node.left, ast.BinOp) or isinstance(node.right, ast.BinOp):
                bad(node, "integer arithmetic more than one operator deep: its value could pass 2^53")
        elif isinstance(node, ast.Constant) and type(node.value) is int and abs(node.value) > INT_LIMIT:
            bad(node, "an integer literal past 2^53: it rounds where it meets a float")
        elif isinstance(node, ast.AugAssign):
            if not isinstance(node.op, BIT_OPS) and not (isinstance(node.op, INT_OPS) and is_int(node.target)
                                                         and is_int(node.value)):
                bad(node, "augmented arithmetic outside bounds")
        elif isinstance(node, ast.Constant) and isinstance(node.value, float):
            text = ast.get_source_segment(source, node)
            if text is None or Fraction(text.replace("_", "")) != Fraction(node.value):
                bad(node, "a float literal that is not exactly its value")
        elif isinstance(node, ast.Constant) and isinstance(node.value, complex):
            bad(node, "a complex literal")
        # Bindings.
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            declared = isinstance(node, ast.AnnAssign) and node.value is None and ast.unparse(node.annotation) == "int"
            bound = node.value is not None and int_source(node.value)
            if any(int_targets(t) for t in targets) and not declared and not bound:
                bad(node, "an integer name bound from something not an integer")
        elif isinstance(node, (ast.For, ast.comprehension)):
            if int_targets(node.target):
                bad(node.target, "an integer name bound by a loop")
        elif isinstance(node, ast.arguments):
            for a in node.posonlyargs + node.args + node.kwonlyargs + [x for x in (node.vararg, node.kwarg) if x]:
                if a.arg in INT_NAMES - TRUSTED_PARAMS or (a.arg in reserved and a.arg not in ("trace", "self")):
                    bad(a, f"a parameter named {a.arg}")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in reserved:
            bad(node, f"{node.id} rebound")
    return out


SOURCE = inspect.getsource(certificate)


def test_the_certificate_does_only_what_the_allowlist_names():
    assert violations(SOURCE) == []


def test_the_directed_functions_are_bounds_whole_set_and_each_is_held_bit_for_bit():
    """A directed function added to bounds must join the list here AND the exactness check."""
    assert {n for n in vars(bounds) if n.endswith(("_lo", "_hi")) and callable(vars(bounds)[n])} == DIRECTED
    held = pathlib.Path(__file__).with_name("test_pinned_bounds.py").read_text(encoding="utf-8")
    problems = next(n for n in ast.parse(held).body if isinstance(n, ast.FunctionDef) and n.name == "problems")
    used = {n.attr for n in ast.walk(problems) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
            and n.value.id == "bounds"}
    assert DIRECTED <= used, sorted(DIRECTED - used)


def shared_basenames(tests_root):
    """Test-file basenames used in two directories. `make test` collects every stage's directory in one pytest
    session, and pytest's default import mode refuses a second module of the same name: this package's first
    test_uniform.py, beside golden's, broke it (2026-09-26). Each runner stage runs one directory, so no stage saw."""
    seen = {}
    for f in sorted(tests_root.rglob("*.py")):
        if f.name.startswith("test_") or f.name.endswith("_test.py"):
            seen.setdefault(f.name, []).append(f.parent.name)
    return {n: d for n, d in seen.items() if len(d) > 1}


def test_no_test_file_here_shares_its_basename_with_another_directory():
    clashes = shared_basenames(pathlib.Path(__file__).resolve().parents[1])
    assert {n: d for n, d in clashes.items() if "pinned" in d} == {}


def test_the_basename_check_sees_a_clash(tmp_path):
    for d, n in (("golden", "test_uniform.py"), ("pinned", "test_uniform.py"), ("pinned", "test_pinned_ok.py")):
        (tmp_path / d).mkdir(exist_ok=True)
        (tmp_path / d / n).write_text("", encoding="utf-8")
    assert shared_basenames(tmp_path) == {"test_uniform.py": ["golden", "pinned"]}


PLANTED = {
    # arithmetic that rounds to nearest, outside libcft
    "a numpy multiply": "def planted(x, y):\n    return x * y\n",
    "a numpy subtract": "def planted(x, y):\n    return x - y\n",
    "int/int true division": "def planted():\n    return 2 / M\n",
    "an integer power": "def planted():\n    return 2 ** -3\n",
    "a matrix product": "def planted(x, y):\n    return x @ y\n",
    "augmented arithmetic": "def planted(x, y):\n    x += y\n    return x\n",
    "a float times an integer": "def planted(x):\n    return x * N\n",
    "a float literal in integer arithmetic": "def planted():\n    return M * 1.5\n",
    # libcft reached around bounds
    "libcft through bounds": "def planted(x, y):\n    return bd.cft.add(bd.F, 0, x, y)\n",
    "getattr to the module": "def planted(x, y):\n    return getattr(bd, 'cft').mul(1, 0, x, y)\n",
    "a private bounds helper": "def planted(x):\n    return bd._out(x, ())\n",
    "a rounding attribute": "def planted():\n    return bd.LO\n",
    "an import from cft": "from .cft import RNE\n",
    "the cft module": "from . import cft\n",
    "an import from bounds by name": "from .bounds import add_lo\n",
    # libm and numpy reductions by other names
    "math": "import math\n",
    "math under an alias": "import math as _m\n",
    "mpmath's fp context": "from mpmath import fp\n",
    "__import__": "def planted(x):\n    return __import__('math').exp(x)\n",
    "eval": "def planted(x, y):\n    return eval('x * y')\n",
    "np.dot": "def planted(x, y):\n    return np.dot(x, y)\n",
    "np.add.reduce": "def planted(x):\n    return np.add.reduce(x)\n",
    "np.maximum (its signed zero is the build's)": "def planted(x, y):\n    return np.maximum(x, y)\n",
    "np.float64 of a decimal": "def planted():\n    return np.float64('0.1')\n",
    "a numpy dtype conversion": "def planted(x):\n    return np.array(x, dtype=np.float32)\n",
    "builtin sum": "def planted(xs):\n    return sum(xs)\n",
    "a sum method": "def planted(x):\n    return x.sum()\n",
    "a dunder multiply": "def planted(x, y):\n    return x.__mul__(y)\n",
    "__float__": "def planted(x):\n    return x.__float__()\n",
    "float() of a Fraction": "def planted():\n    return float(Fraction(1, 3))\n",
    "Fraction of a decimal string": "def planted():\n    return Fraction('0.1')\n",
    "an inexact float literal": "def planted(x):\n    return bd.add_lo(x, 0.1)\n",
    "a lambda": "def planted(x):\n    return (lambda a: a)(x)\n",
    # laundering a float through an integer's name, or rebinding an allowed name
    "a float bound to an integer name": "def planted(x, y):\n    k = bd.mul_hi(x, y)\n    return k * N\n",
    "an untrusted integer parameter": "def planted(k):\n    return k * N\n",
    "an integer name bound by a loop": "def planted(xs):\n    return [k * N for k in xs]\n",
    "a walrus": "def planted(x):\n    return (k := x) * N\n",
    "a float bound to self.N": "def planted(self, x):\n    self.N = x\n    return self.N * 2\n",
    "len rebound": "def planted(x):\n    len = sum\n    return len(x)\n",
    "np rebound": "def planted(x):\n    np = x\n    return np.where(x)\n",
    "a with block": "def planted(x):\n    with x:\n        return x\n",
    # verifier-P1's D3: round-to-nearest conversions spelled past the second version of this rule
    "a Fraction stored by item assignment": "def planted(z):\n    z[0] = Fraction(1, 3)\n    return z\n",
    "a Fraction stored by slice assignment": "def planted(z):\n    z[:] = Fraction(1, 3)\n    return z\n",
    "a tuple target holding an item": "def planted(z, w):\n    z[0], w = Fraction(1, 3), 0.5\n    return z\n",
    "np.array with np.float64 as a positional dtype":
        "def planted():\n    return np.array(Fraction(1, 3), np.float64)\n",
    "np.array with float as a positional dtype": "def planted():\n    return np.array(Fraction(1, 3), float)\n",
    "np.zeros with a positional dtype": "def planted():\n    return np.zeros(3, np.float32)\n",
    "float.fromhex of 68 significant bits": "def planted():\n    return float.fromhex('0x1.999999999999999ap-4')\n",
    "float.fromhex of a name": "def planted(h):\n    return float.fromhex(h)\n",
    "float.fromhex of a decimal-looking string": "def planted():\n    return float.fromhex('0x0.1')\n",
    "np.where with an integer past 2^53": "def planted(c):\n    return np.where(c > 0, c, 10000000000000001)\n",
    "an integer past 2^53 built by arithmetic": "def planted():\n    return 94906267 * 94906267 + 1\n",
}


@pytest.mark.parametrize("name", sorted(PLANTED))
def test_the_rule_refuses_each_respelling_planted_in_the_certificate(name):
    found = violations(SOURCE + "\n\n" + PLANTED[name])
    assert found, f"the allowlist let {name} through"


def test_the_rule_passes_an_exact_hex_literal_and_the_certificates_own():
    assert fromhex_exact(ast.parse("float.fromhex('0x1p-200')").body[0].value)
    assert fromhex_exact(ast.parse("float.fromhex('-0x1.8p+3')").body[0].value)


# verifier-P1's D2 faults as they were written, in decide and extend, and the sixth's swap of u's ends: each is now
# an arithmetic or a subscript in the orchestration, which the rule refuses (inside a step, the mutation gate sees it).
ORCHESTRATION_PLANTS = {
    "lower boundaries scanned up, in decide": (
        "        b = boundaries(c)\n",
        "        b = (bd.scan_hi(lower(c)), bd.scan_hi(c[1]))\n"),
    "s_lo accumulated up, in extend": (
        "        self.s = accumulate(self.s, square(inner(self.e, q)))\n",
        "        self.s = (bd.add_hi(self.s[0], lower(square(inner(self.e, q)))), self.s[1])\n"),
    "the Gram sums accumulated down, in extend": (
        "        self.g = gram_accumulate(self.g, gram_terms(self.q, q))\n",
        "        self.g = bd.add_lo(self.g, gram_terms(self.q, q))\n"),
    "u's ends swapped before the target": (
        "        t = target(uniform_box(u), last(b))\n",
        "        t = target(uniform_box(u)[::-1], last(b))\n"),
    "u's ends unpacked and swapped": (
        "        t = target(uniform_box(u), last(b))\n",
        "        u_lo, u_hi = uniform_box(u)\n        t = target((u_hi, u_lo), last(b))\n"),
    "a clamp by numpy in decide": (
        "        b = boundaries(c)\n",
        "        b = boundaries((np.where(lower(c) > 0, lower(c), 0.0), c[1]))\n"),
    "a directed call in enclosure": (
        "    a = sqrt_box(exact(Fraction(2, M), FP64))\n",
        "    a = (bd.sqrt_hi(exact(Fraction(2, M), FP64)), bd.sqrt_hi(exact(Fraction(2, M), FP64)))\n"),
}


@pytest.mark.parametrize("name", sorted(ORCHESTRATION_PLANTS))
def test_the_rule_refuses_arithmetic_or_a_subscript_in_the_orchestration(name):
    old, new = ORCHESTRATION_PLANTS[name]
    assert SOURCE.count(old) == 1
    found = violations(SOURCE.replace(old, new))
    assert any("orchestration" in f for f in found), f"the rule let {name} through: {found}"

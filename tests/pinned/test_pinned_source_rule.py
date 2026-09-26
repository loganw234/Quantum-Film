"""quantum_film/pinned/certificate.py read against an ALLOWLIST: what the list does not name, it may not do.

A rule that lists forbidden spellings is bypassed by other spellings. The P0 verifier passed binary64 through the
authority's source rule as int/int division, a `math` alias, mpmath's `fp` context and `__float__`
(verifier-P0.md, 2026-09-25 23:30Z); this rule's first version, a list of rounding-attribute names, missed ten
respellings (a numpy multiply, bd.cft.add, getattr, a math alias, np.dot, sum, __mul__, np.float64('0.1'), bd.LO,
__import__; P1.md); its second passed six round-to-nearest conversions (verifier-P1's D3), its third five more (D9:
a method keyword, a float dunder as a default, an integer name squared past 2^53, a float in a field declared int,
and the two together) and five orchestration faults (D8). So certificate.py is held to what it MAY do:

THE FILE IS CLOSED. Its top-level statements are its docstring, the imports in IMPORTS, TAU, and definitions: every
function a STEP registered in test_pinned_certificate.py's CHECKS (with its tight check) or a HELPER registered in
test_pinned_orchestration.py's HELPER_CHECKS (with its exact test), or `enclosure`; every class one of CLASSES, and
Certificate's methods exactly __init__, decide and extend. Nothing is defined inside a function.

EVERYWHERE:
- CALLS: a function or class the module defines; a callable imported by IMPORTS; bounds' directed functions (DIRECTED,
  each held bit for bit by tests/pinned/test_pinned_bounds.py); the numpy functions in NP_ARITY, at most that many
  positional arguments; the builtins in BUILTINS; the methods in METHODS; float.fromhex of one literal that is exactly
  a binary64; and `trace`, only as a statement. Keywords only as KEYWORDS names them. Fraction takes integers only.
  `bounds64` only in uniform_box; `lower` only as the argument of `self.q.append`.
- NAMES of bd and np: only those, called or not. No dunder attribute; `float` and `int` only as float.fromhex.
- NO ITEM OR SLICE ASSIGNMENT: numpy converts what it stores into an array, to nearest.
- ARITHMETIC (+ - * // %) between integers only, one operator deep: integer literals up to 2^16, the INT_NAMES,
  `.M` and `.N` of self, e and self.e, and len(). True division, powers and matrix products are refused outright.
  An integer may be a call's argument only where INT_OK names it (a size, a count, a segment, an exact value), never
  as a numpy value. Each INT_NAME is bound once in its function, from an integer; fields declared int only in
  Enclosure.
- DEFAULTS are None. Float literals are exact. No lambda, walrus, global, nonlocal, with, try, match, async, yield
  or del.

THE ORCHESTRATION (Certificate, enclosure) only composes steps and helpers, and passes each interval whole: it calls
only STEPS, HELPERS, EnclosureBroken, trace and Fraction; it builds no tuple, list, dict or set (a return's value,
trace's record and the empty column list excepted); it holds no float literal, no subscript, star or unpacking, no
bd or np, and no literal as a step's argument; its state is set only in __init__ (e, M, N, s, g, q) and in extend's
two accumulations, each its own step fed its own state first, and its column list grows only by
`self.q.append(lower(q))`.

WHICH LAYER HOLDS WHAT. This rule reads spellings, so a respelling it does not list may pass it. The tight checks in
test_pinned_certificate.py hold each step's behaviour however it is spelled, on their inputs; the exact tests in
test_pinned_orchestration.py hold each helper's; and its tight end-to-end check holds what the orchestration
composes, on its inputs. A fault spelled past this rule that moves no claimed value on those inputs may pass.
"""
import ast
import inspect
import pathlib
import re
from fractions import Fraction

import pytest

from quantum_film.pinned import bounds, certificate

HERE = pathlib.Path(__file__).resolve().parent


def registry(file, name):
    """The string keys of the dict literal assigned to `name` in a sibling test file."""
    for node in ast.parse((HERE / file).read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return {k.value for k in node.value.keys}
    raise AssertionError(f"{file} has no {name}")


STEPS = registry("test_pinned_certificate.py", "CHECKS")
HELPERS = registry("test_pinned_orchestration.py", "HELPER_CHECKS")

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
KEYWORDS = {("zip", "strict"), ("dataclass", "frozen"), ("lru_cache", "maxsize")}
INT_NAMES = {"L", "M", "N", "j", "k", "p"}
TRUSTED_PARAMS = {"L", "j", "p"}        # the tile edge, a draw's index, and a position: each indexes, or refuses
INT_BASES = {"self", "e", "self.e"}
INT_LITERAL_LIMIT = 2 ** 16
INT_OK = {("modes", 0), ("angles", 0), ("Fraction", 0), ("Fraction", 1), ("assemble_box", 0), ("assemble", 0),
          ("zero", 0), ("holds", 1), ("np.ones", 0), ("np.zeros", 0), ("np.eye", 0), ("np.tile", 1),
          ("bd.dot_lo", 2), ("bd.dot_hi", 2), ("Enclosure", 4), ("Enclosure", 5), ("Located", 0), ("trace", 0)}
CLASSES = {"EnclosureBroken", "Enclosure", "Located", "Certificate"}
ORCHESTRATION = {"Certificate", "enclosure"}
CERTIFICATE_METHODS = {"__init__", "decide", "extend"}
ORCHESTRATION_CALLS = STEPS | HELPERS | {"EnclosureBroken", "trace", "Fraction"}
INIT_STATE = {"e", "M", "N", "s", "g", "q"}
ACCUMULATIONS = {"s": "accumulate", "g": "gram_accumulate"}
INT_OPS = (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod)
BIT_OPS = (ast.BitAnd, ast.BitOr, ast.BitXor)
DISPLAYS = (ast.Tuple, ast.List, ast.Dict, ast.Set, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
FORBIDDEN = tuple(getattr(ast, n) for n in ("Lambda", "NamedExpr", "Global", "Nonlocal", "With", "AsyncWith", "Try",
                                            "TryStar", "Match", "AsyncFunctionDef", "Await", "Yield", "YieldFrom",
                                            "Delete") if hasattr(ast, n))


def dotted(e):
    """'a.b.c' for a Name or a chain of attributes on one, else None."""
    if isinstance(e, ast.Name):
        return e.id
    if isinstance(e, ast.Attribute):
        base = dotted(e.value)
        return None if base is None else f"{base}.{e.attr}"
    return None


def is_int(e):
    """An expression that is an integer by its spelling."""
    if isinstance(e, ast.Constant):
        return type(e.value) is int
    if isinstance(e, ast.Name):
        return e.id in INT_NAMES
    if isinstance(e, ast.Attribute):
        return e.attr in ("M", "N") and dotted(e.value) in INT_BASES
    if isinstance(e, ast.Call):
        return isinstance(e.func, ast.Name) and e.func.id == "len"
    if isinstance(e, ast.BinOp):
        return isinstance(e.op, INT_OPS) and is_int(e.left) and is_int(e.right)
    if isinstance(e, ast.UnaryOp):
        return isinstance(e.op, ast.USub) and is_int(e.operand)
    return False


def int_source(e):
    """A value an integer name may be bound from."""
    if is_int(e):
        return True
    if isinstance(e, ast.Attribute) and e.attr in ("shape", "size"):
        return True
    if isinstance(e, ast.Call) and dotted(e.func) == "np.argmin":
        return True
    if isinstance(e, ast.IfExp):
        return int_source(e.body) and int_source(e.orelse)
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


def closed_violations(tree):
    """The file is closed: every definition registered, nothing else at the top level, nothing nested."""
    out = []
    for i, node in enumerate(tree.body):
        why = None
        if isinstance(node, ast.Expr) and i == 0 and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            pass
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            pass                                            # held by IMPORTS below
        elif isinstance(node, ast.Assign) and [dotted(t) for t in node.targets] == ["TAU"]:
            pass
        elif isinstance(node, ast.FunctionDef):
            if node.name not in STEPS | HELPERS | {"enclosure"}:
                why = f"{node.name} is neither a registered step (CHECKS) nor a registered helper (HELPER_CHECKS)"
        elif isinstance(node, ast.ClassDef):
            if node.name not in CLASSES:
                why = f"a class {node.name} the file does not name"
            elif node.name == "Certificate":
                methods = {n.name for n in node.body if isinstance(n, ast.FunctionDef)}
                others = [n for n in node.body if not isinstance(n, ast.FunctionDef)
                          and not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
                if methods != CERTIFICATE_METHODS or others:
                    why = f"Certificate's body is not its docstring and {sorted(CERTIFICATE_METHODS)}"
        else:
            why = "a top-level statement the file does not name"
        if why:
            out.append(f"line {node.lineno}: {why}")
    names = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
    out += [f"{n} is defined twice" for n in sorted({n for n in names if names.count(n) > 1})]
    for top in tree.body:
        scope = top.body if isinstance(top, ast.ClassDef) and top.name == "Certificate" else [top]
        for fn in scope:
            if isinstance(fn, ast.FunctionDef):
                out += [f"line {n.lineno}: a definition inside {fn.name}" for n in ast.walk(fn)
                        if n is not fn and isinstance(n, (ast.FunctionDef, ast.ClassDef))]
    return out


def body_nodes(fn):
    """Every node of a function's parameters and body: its decorators are not its orchestration."""
    for part in [fn.args, *fn.body]:
        yield from ast.walk(part)


def annotations(tree):
    """The ids of every node inside an annotation: a type named there converts nothing."""
    out = set()
    for node in ast.walk(tree):
        for ann in (getattr(node, "annotation", None), getattr(node, "returns", None)):
            if ann is not None:
                out.update(id(n) for n in ast.walk(ann))
    return out


def orchestration_violations(tree):
    """The orchestration composes steps and helpers only, and passes each interval whole."""
    out = []

    def bad(node, why):
        out.append(f"line {node.lineno}: the orchestration {why}: {ast.unparse(node)[:70]}")

    for top in tree.body:
        if getattr(top, "name", None) not in ORCHESTRATION:
            continue
        functions = [n for n in top.body if isinstance(n, ast.FunctionDef)] if isinstance(top, ast.ClassDef) \
            else [top]
        for fn in functions:
            allowed = set()                                   # the displays this function may build
            for node in body_nodes(fn):
                if isinstance(node, ast.Return) and node.value is not None:
                    allowed.add(id(node.value))
                if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) \
                        and dotted(node.value.func) == "trace" and len(node.value.args) == 2:
                    allowed.add(id(node.value.args[1]))
                if fn.name == "__init__" and isinstance(node, ast.Assign) and [dotted(t) for t in node.targets] \
                        == ["self.q"] and isinstance(node.value, ast.List) and not node.value.elts:
                    allowed.add(id(node.value))
            assigned = []
            for node in body_nodes(fn):
                if isinstance(node, ast.Name) and node.id in ("bd", "np"):
                    bad(node, f"names {node.id}: its arithmetic belongs in a step")
                elif isinstance(node, ast.Subscript):
                    bad(node, "subscripts: an interval passes whole between steps")
                elif isinstance(node, ast.Starred):
                    bad(node, "stars an interval open")
                elif isinstance(node, DISPLAYS) and id(node) not in allowed:
                    bad(node, "builds a tuple, list, dict or set: an interval passes whole between steps")
                elif isinstance(node, ast.Constant) and isinstance(node.value, float):
                    bad(node, "holds a float literal: a step is fed only what steps and helpers return")
                elif isinstance(node, ast.Call):
                    name = dotted(node.func)
                    if name not in ORCHESTRATION_CALLS and name != "self.q.append":
                        bad(node, f"calls {name}, which is neither a step nor a helper")
                    elif name in STEPS and any(isinstance(a, ast.Constant) for a in node.args):
                        bad(node, "feeds a step a literal")
                if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.For, ast.comprehension)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    if any(isinstance(t, (ast.Tuple, ast.List)) for t in targets):
                        bad(node, "unpacks an interval")
                    for t in targets:
                        name = dotted(t)
                        if name and name.startswith("self."):
                            assigned.append((name[5:], node))
            for attr, node in assigned:
                if fn.name == "__init__":
                    ok = attr in INIT_STATE and [a for a, _ in assigned].count(attr) == 1
                elif fn.name == "extend":
                    step = ACCUMULATIONS.get(attr)
                    ok = step is not None and isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) \
                        and dotted(node.value.func) == step and node.value.args \
                        and dotted(node.value.args[0]) == f"self.{attr}" \
                        and [a for a, _ in assigned].count(attr) == 1
                else:
                    ok = False
                if not ok:
                    bad(node, f"sets its state self.{attr} outside __init__ and its own accumulation in extend")
            if fn.name == "extend":
                for attr in ACCUMULATIONS:
                    if [a for a, _ in assigned].count(attr) != 1:
                        out.append(f"line {fn.lineno}: the orchestration's extend does not accumulate self.{attr} "
                                   f"exactly once")
                appends = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and dotted(n.func) == "self.q.append"]
                if len(appends) != 1:
                    out.append(f"line {fn.lineno}: the orchestration's extend grows its column list "
                               f"{len(appends)} times, not once")
    return out


def global_violations(tree, source):
    out = []
    defined = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    callables = defined | IMPORTED_CALLABLE | BUILTINS | {"trace"}
    reserved = callables | {"np", "bd", "float", "int", "FP64", "self"}

    def bad(node, why):
        out.append(f"line {node.lineno}: {why}: {ast.unparse(node)[:70]}")

    statement_traces, append_lowers, fromhex_funcs = set(), set(), set()
    typed = annotations(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call) and dotted(node.value.func) == "trace":
            statement_traces.add(id(node.value))
        if isinstance(node, ast.Call) and dotted(node.func) == "self.q.append" and len(node.args) == 1 \
                and isinstance(node.args[0], ast.Call) and dotted(node.args[0].func) == "lower":
            append_lowers.add(id(node.args[0]))
        if isinstance(node, ast.Call) and dotted(node.func) == "float.fromhex":
            fromhex_funcs.update({id(node.func), id(node.func.value)})
    for top in tree.body:
        if isinstance(top, ast.FunctionDef) and top.name != "uniform_box":
            for node in ast.walk(top):
                if isinstance(node, ast.Call) and dotted(node.func) == "bounds64":
                    bad(node, "bounds64 outside uniform_box: a directed rounding outside its checked step")
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
            f, name = node.func, dotted(node.func)
            for kw in node.keywords:
                if (name, kw.arg) not in KEYWORDS:
                    bad(node, f"a keyword {kw.arg} the allowlist does not name (a keyword can carry a value)")
            for i, a in enumerate(node.args):
                if is_int(a) and (name, i) not in INT_OK:
                    bad(node, f"an integer as argument {i} of {name}: an integer meets a float only where INT_OK "
                              f"names it")
            if name == "trace" and id(node) not in statement_traces:
                bad(node, "trace used for its value: it only observes")
            if name == "lower" and id(node) not in append_lowers:
                bad(node, "lower outside self.q.append: an interval's end taken where a whole interval passes")
            if isinstance(f, ast.Name) and f.id in callables:
                if f.id == "Fraction" and (node.keywords or not all(is_int(a) for a in node.args)):
                    bad(node, "Fraction takes integers only here")
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "bd":
                pass                                       # the attribute itself is checked below
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "np":
                if f.attr not in NP_ARITY:
                    bad(node, "a numpy call the allowlist does not name (np.float64 is a dtype here, not a call)")
                elif len(node.args) > NP_ARITY[f.attr]:
                    bad(node, "a numpy call with an extra positional argument (it carries a dtype)")
            elif name == "float.fromhex":
                if not fromhex_exact(node):
                    bad(node, "float.fromhex of anything but a literal that is exactly a binary64")
            elif isinstance(f, ast.Attribute) and f.attr in METHODS:
                pass
            else:
                bad(node, "a call the allowlist does not name")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__"):
                bad(node, "a dunder attribute: an operator reached by name")
            elif isinstance(node.value, ast.Name) and node.value.id == "bd" and node.attr not in DIRECTED:
                bad(node, "bounds is reached only through its directed functions")
            elif isinstance(node.value, ast.Name) and node.value.id == "np" and \
                    node.attr not in NP_ARITY.keys() | NP_VALUES:
                bad(node, "a numpy name the allowlist does not name")
            elif isinstance(node.value, ast.Name) and node.value.id in ("float", "int") \
                    and id(node) not in fromhex_funcs:
                bad(node, f"{node.value.id}.{node.attr}: float is used only as float.fromhex")
        elif isinstance(node, ast.Name) and node.id in ("float", "int", "complex", "bool") and \
                isinstance(node.ctx, ast.Load) and id(node) not in fromhex_funcs | typed:
            bad(node, f"the type {node.id} as a value: it converts")
        elif isinstance(node, ast.BinOp):
            if not isinstance(node.op, BIT_OPS) and not (isinstance(node.op, INT_OPS) and is_int(node.left)
                                                         and is_int(node.right)):
                bad(node, "arithmetic outside bounds: only + - * // % between integers")
            elif isinstance(node.left, ast.BinOp) or isinstance(node.right, ast.BinOp):
                bad(node, "integer arithmetic more than one operator deep: its value could pass 2^53")
        elif isinstance(node, ast.Constant) and type(node.value) is int and abs(node.value) > INT_LITERAL_LIMIT:
            bad(node, "an integer literal past 2^16: two of them multiplied could pass 2^53")
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
        elif isinstance(node, ast.arguments):
            for a in node.posonlyargs + node.args + node.kwonlyargs + [x for x in (node.vararg, node.kwarg) if x]:
                if a.arg in INT_NAMES - TRUSTED_PARAMS or (a.arg in reserved and a.arg not in ("trace", "self")):
                    bad(a, f"a parameter named {a.arg}")
            for d in node.defaults + [d for d in node.kw_defaults if d is not None]:
                if not (isinstance(d, ast.Constant) and d.value is None):
                    bad(d, "a default that is not None: a value reaches a parameter unseen")
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in reserved:
            bad(node, f"{node.id} rebound")
    return out


def binding_violations(tree):
    """Integer names bound once per function, from an integer; fields declared int only in Enclosure."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for n in node.body:
                if isinstance(n, ast.AnnAssign) and ast.unparse(n.annotation) == "int" and \
                        (node.name != "Enclosure" or dotted(n.target) not in ("M", "N") or n.value is not None):
                    out.append(f"line {n.lineno}: an int field declared outside Enclosure's M and N")
        if not isinstance(node, ast.FunctionDef):
            continue
        a = node.args
        bound = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs if x.arg in INT_NAMES]
        for n in ast.walk(node):
            targets = []
            if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                ints = [t for tg in targets for t in ast.walk(tg) if isinstance(t, ast.Name) and t.id in INT_NAMES]
                if ints and not (getattr(n, "value", None) is not None and int_source(n.value)):
                    out.append(f"line {n.lineno}: an integer name bound from something not an integer")
                bound += [t.id for t in ints]
                selfs = [t for tg in targets for t in ast.walk(tg) if dotted(t) in ("self.M", "self.N")]
                if selfs and not (getattr(n, "value", None) is not None and int_source(n.value)):
                    out.append(f"line {n.lineno}: self.M or self.N bound from something not an integer")
            elif isinstance(n, (ast.For, ast.comprehension)):
                if any(isinstance(t, ast.Name) and t.id in INT_NAMES for t in ast.walk(n.target)):
                    out.append(f"line {n.target.lineno}: an integer name bound by a loop")
        out += [f"line {node.lineno}: {x} bound more than once in {node.name}: its value could grow past 2^53"
                for x in sorted({x for x in bound if bound.count(x) > 1})]
    return out


def violations(source, closed=True):
    """Every way certificate.py's source departs from what the allowlist names. closed=False leaves out the check
    that its definitions are registered: a planted respelling is appended as a function of its own."""
    tree = ast.parse(source)
    out = closed_violations(tree) if closed else []
    return out + orchestration_violations(tree) + global_violations(tree, source) + binding_violations(tree)


SOURCE = inspect.getsource(certificate)


def test_the_certificate_does_only_what_the_allowlist_names():
    assert violations(SOURCE) == []


def test_the_registries_name_what_the_certificate_defines_or_imports():
    tree = ast.parse(SOURCE)
    defined = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert STEPS <= defined and HELPERS <= defined | IMPORTED_CALLABLE and not STEPS & HELPERS


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


# Respellings: each is appended to the certificate's source as a function of its own and must be refused by the
# layers that read every function (closed=False, so the registration check does not refuse it first).
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
    # verifier-P1's D9: the five respellings that passed the third version (R1-R5), and variants
    "R1: a method keyword": "def planted(w):\n    return w.max(initial=Fraction(1, 3))\n",
    "R2: a float dunder as a default": "def planted(x, y, trace=float.__mul__):\n    return trace(x, y)\n",
    "R2: an ndarray dunder as a default": "def planted(x, y, trace=np.ndarray.__add__):\n    return trace(x, y)\n",
    "R2: trace used for its value": "def planted(x, y, trace=None):\n    return trace(x, y)\n",
    "R3: an integer name squared past 2^53":
        "def planted(c):\n    k = 94906267\n    k = k * k\n    return np.where(c > 0, c, k)\n",
    "R3: integers past 2^53 through two names":
        "def planted(c):\n    k = 65536 * 65536\n    p = k * k\n    return np.where(c > 0, c, p)\n",
    "R3: an integer as a numpy value": "def planted(c, k):\n    return np.where(c > 0, c, k)\n",
    "R4: a float in a field declared int":
        "class B(NamedTuple):\n    N: int\n\n\ndef planted(b):\n    return b.N * 3\n",
    "R4: an int field on any name": "def planted(b):\n    return b.N * 3\n",
    "R5: R1 with R3's integer": "def planted(w):\n    k = 94906267\n    k = k * k\n    return w.max(initial=k)\n",
    "bounds64 outside uniform_box": "def planted(u):\n    return bounds64(u)\n",
}


@pytest.mark.parametrize("name", sorted(PLANTED))
def test_the_rule_refuses_each_respelling_planted_in_the_certificate(name):
    found = violations(SOURCE + "\n\n" + PLANTED[name], closed=False)
    assert found, f"the allowlist let {name} through"


def test_the_rule_passes_an_exact_hex_literal_and_the_certificates_own():
    assert fromhex_exact(ast.parse("float.fromhex('0x1p-200')").body[0].value)
    assert fromhex_exact(ast.parse("float.fromhex('-0x1.8p+3')").body[0].value)


# The file is closed: a function, class or statement it does not register is refused.
CLOSED_PLANTS = {
    "an unregistered helper": "def ends(x):\n    return x[1], x[0]\n",
    "an unregistered class": "class Box(NamedTuple):\n    lo: object\n",
    "a module-level statement": "K = TAU\n",
    "a step defined twice": "def square(y):\n    return y\n",
    "a fourth method": None,
}


@pytest.mark.parametrize("name", sorted(CLOSED_PLANTS))
def test_the_rule_refuses_what_the_file_does_not_register(name):
    if CLOSED_PLANTS[name] is None:
        old = "    def extend(self, drawn, t):\n"
        assert SOURCE.count(old) == 1, "the plant's anchor is gone: re-anchor this plant"
        source = SOURCE.replace(old, "    def reset(self):\n        return self.e\n\n" + old)
    else:
        source = SOURCE + "\n\n" + CLOSED_PLANTS[name]
    assert closed_violations(ast.parse(source)), f"the closed file let {name} through"


# Faults written into the orchestration, anchors kept: each is refused by the rule. verifier-P1's five D8 faults are
# test_pinned_orchestration.py's FIVE, planted here as there, where the tight end-to-end check fails each as well.
ANCHOR_S = "        self.s = accumulate(self.s, square(inner(self.e, q)))\n"
ORCHESTRATION_PLANTS = {
    "lower boundaries scanned up, in decide": (
        "        b = boundaries(c)\n", "        b = (bd.scan_hi(lower(c)), bd.scan_hi(c[1]))\n"),
    "s_lo accumulated up, in extend": (
        ANCHOR_S, "        self.s = (bd.add_hi(self.s[0], lower(square(inner(self.e, q)))), self.s[1])\n"),
    "the Gram sums accumulated down, in extend": (
        "        self.g = gram_accumulate(self.g, gram_terms(self.q, q))\n",
        "        self.g = bd.add_lo(self.g, gram_terms(self.q, q))\n"),
    "u's ends swapped before the target": (
        "        t = target(uniform_box(u), last(b))\n", "        t = target(uniform_box(u)[::-1], last(b))\n"),
    "u's ends unpacked and swapped": (
        "        t = target(uniform_box(u), last(b))\n",
        "        u_lo, u_hi = uniform_box(u)\n        t = target((u_hi, u_lo), last(b))\n"),
    "a clamp by numpy in decide": (
        "        b = boundaries(c)\n", "        b = boundaries((np.where(lower(c) > 0, lower(c), 0.0), c[1]))\n"),
    "a directed call in enclosure": (
        "    a = sqrt_box(exact(Fraction(2, M), FP64))\n",
        "    a = (bd.sqrt_hi(exact(Fraction(2, M), FP64)), bd.sqrt_hi(exact(Fraction(2, M), FP64)))\n"),
    "a step's state accumulated from another's": (
        ANCHOR_S, "        self.s = accumulate(self.g, square(inner(self.e, q)))\n"),
    "a column appended twice": (
        "        self.q.append(lower(q))\n", "        self.q.append(lower(q))\n        self.q.append(lower(q))\n"),
    "an accumulation dropped": (ANCHOR_S, ""),
    "state set in decide": (
        "        b = boundaries(c)\n", "        b = boundaries(c)\n        self.s = zero(self.M)\n"),
}


@pytest.mark.parametrize("name", sorted(ORCHESTRATION_PLANTS))
def test_the_rule_refuses_arithmetic_or_a_subscript_or_a_stray_state_in_the_orchestration(name):
    old, new = ORCHESTRATION_PLANTS[name]
    assert SOURCE.count(old) == 1, "the plant's anchor is gone: re-anchor this plant"
    found = violations(SOURCE.replace(old, new))
    assert any("orchestration" in f for f in found), f"the rule let {name} through: {found}"


def five():
    import importlib.util
    spec = importlib.util.spec_from_file_location("_rule_orchestration", HERE / "test_pinned_orchestration.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FIVE_MODULE = five()


@pytest.mark.parametrize("name", sorted(FIVE_MODULE.FIVE))
def test_the_rule_refuses_each_of_verifier_p1s_five_as_planted(name):
    found = violations(FIVE_MODULE.planted(name))
    assert found, f"the rule let {name} through"

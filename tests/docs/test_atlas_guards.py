"""Importing a module does nothing outside the process (CLAUDE.md).

An import of a probe script re-ran nine Atlas jobs on 2026-09-25. The rule,
for every module under research/, tools/ and quantum_film/:

    importing it runs no subprocess, opens no socket or browser, loads no
    native code, and writes, moves or deletes no file or directory;
    or it refuses to be imported (`if __name__ != "__main__": raise ...`).

It is checked by BEHAVIOUR, not by reading. tests/docs/import_audit.py
imports every module in one child process under a PEP 578 audit hook, which
sees each such effect however it is spelled, and stops it before it happens.

Two versions that read the source instead were walked past by the P0
verifier:
  - The first named Atlas spellings. It missed dotted, star and relative
    imports, wrappers, aliases, getattr, importlib and curl.
  - The second allowlisted pure modules. It missed calls with no call
    expression (a decorator's application, __init_subclass__, dunders
    reached through builtins), impure callables handed to pure modules'
    higher-order functions (operator.call, itertools.starmap), names
    rebound by assignment, and `import antigravity`, which opens a browser.
Every one of those that can run is now a negative control below.

Its limit: it sees the branch an import takes on this machine. An import
that does something only on another platform, or only when an environment
variable is set, is not seen here.
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
EVERYWHERE = ("research", "tools", "quantum_film")
AUDIT = pathlib.Path(__file__).with_name("import_audit.py")


def audit(files):
    p = subprocess.run([sys.executable, str(AUDIT), str(ROOT), *map(str, files)],
                       capture_output=True, text=True, timeout=300, cwd=ROOT)
    assert p.returncode == 0, p.stderr[-2000:]
    return json.loads(p.stdout)


def test_importing_any_module_does_nothing_outside_the_process():
    files = [f for d in EVERYWHERE for f in sorted((ROOT / d).rglob("*.py"))]
    out = audit(files)
    effects = {f: o for f, o in out.items() if o.startswith("effect")}
    assert effects == {}
    errors = {f: o for f, o in out.items() if o.startswith("error")}
    assert errors == {}, "a module that cannot even be imported here is not checked by this gate"
    assert sum(o == "ok" for o in out.values()) > 10 and sum(o == "refused" for o in out.values()) > 10


# Shapes that passed a reading of the source (the P0 verifier, 2026-09-25/26). Each tries an effect
# at import; the hook must stop every one. MARK is a path the hook never lets them write.
PLANTED = {
    "bare_decorator": ("def register(f):\n    open(MARK, 'w').write('x')\n    return f\n\n\n"
                       "@register\ndef f():\n    pass\n"),
    "init_subclass": ("class Base:\n    def __init_subclass__(cls):\n        open(MARK, 'w').write('x')\n\n\n"
                      "class Child(Base):\n    pass\n"),
    "operator_call": ("import operator\nimport subprocess\n"
                      "operator.call(subprocess.run, [sys.executable, '-c', 'pass'])\n"),
    "starmap": ("import itertools\nimport subprocess\n"
                "list(itertools.starmap(subprocess.run, [([sys.executable, '-c', 'pass'],)]))\n"),
    "rebound_math": ("import math\nimport subprocess\nx = math.sqrt(2)\nmath = subprocess\n"
                     "math.run([sys.executable, '-c', 'pass'])\n"),
    "antigravity": "import antigravity\n",
    "socket": "import socket\nsocket.create_connection(('api.mothquantum.com', 443), timeout=1)\n",
    "mkdir": "import os\nos.mkdir(MARK + '.d')\n",
    "curl": "import subprocess\nsubprocess.run(['curl.exe', '--version'])\n",
}


def test_every_planted_effect_is_stopped_and_named(tmp_path):
    mark = tmp_path / "mark.txt"
    files = []
    for name, body in PLANTED.items():
        f = tmp_path / f"planted_{name}.py"
        f.write_text(f"import sys\nMARK = {str(mark)!r}\n{body}", encoding="utf-8")
        files.append(f)
    out = audit(files)
    missed = {f: o for f, o in out.items() if not o.startswith("effect")}
    assert missed == {}
    assert not mark.exists() and not (tmp_path / "mark.txt.d").exists()        # stopped, not merely seen


def test_a_pure_module_and_a_refusing_script_pass(tmp_path):
    pure = tmp_path / "pure.py"
    pure.write_text("import math\nfrom fractions import Fraction\nX = Fraction(1, 3) + math.sqrt(2)\n",
                    encoding="utf-8")
    refusing = tmp_path / "refusing.py"
    refusing.write_text('if __name__ != "__main__":\n    raise ImportError("run it, never import it")\n'
                        "import subprocess\nsubprocess.run(['curl.exe'])\n", encoding="utf-8")
    assert audit([pure, refusing]) == {str(pure): "ok", str(refusing): "refused"}

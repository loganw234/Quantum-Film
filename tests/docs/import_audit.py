"""Import modules under a PEP 578 audit hook, and report any effect an import has.

Run as a child process by tests/docs/test_atlas_guards.py:

    python import_audit.py ROOT FILE...

It prints one JSON object: {file: outcome}. The outcome is "ok", "refused"
(the module's own import refusal fired), "effect: <event> <args>" (the import
tried to do something outside the process and was stopped), or
"error: <type>: <message>" (the import failed for another reason).

The hook stops the effect before it happens: raising inside an audit hook
aborts the operation that raised the event. numpy and mpmath are imported
before the hook is installed, since their own imports load native code.
"""
import importlib
import importlib.util
import json
import pathlib
import sys

sys.dont_write_bytecode = True
import mpmath  # noqa: E402,F401  (imported before the hook: its import is not the module's)
import numpy  # noqa: E402,F401

EFFECTS = ("subprocess.", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.startfile", "os.kill",
           "os.fork", "socket.", "urllib.", "http.client.", "ftplib.", "smtplib.", "poplib.", "imaplib.",
           "nntplib.", "telnetlib.", "webbrowser.", "ctypes.dlopen", "ctypes.call_function", "winreg.",
           "os.mkdir", "os.rmdir", "os.remove", "os.rename", "os.replace", "os.symlink", "os.link", "os.chmod",
           "os.chown", "os.truncate", "os.utime", "shutil.", "tempfile.mkstemp", "tempfile.mkdtemp",
           "sqlite3.connect", "os.chdir")
WRITE_MODES = set("wax+")


class Effect(Exception):
    pass


def hook(event, args):
    if any(event == e or (e.endswith(".") and event.startswith(e)) for e in EFFECTS):
        raise Effect(f"{event} {str(args)[:120]}")
    if event == "open" and len(args) > 1 and isinstance(args[1], str) and WRITE_MODES & set(args[1]):
        raise Effect(f"open for writing {str(args[0])[:120]}")
    if event == "open" and len(args) > 2 and isinstance(args[2], int) and args[2] & 0o3:   # os.open, O_WRONLY/O_RDWR
        raise Effect(f"os.open for writing {str(args[0])[:120]}")


def load(root, path):
    try:
        rel = path.relative_to(root)
    except ValueError:                       # a planted file outside the tree (the gate's own controls)
        rel = pathlib.Path(path.name)
    if rel.parts[0] == "quantum_film":
        name = ".".join(rel.with_suffix("").parts)
        name = name[: -len(".__init__")] if name.endswith(".__init__") else name
        importlib.import_module(name)
        return
    spec = importlib.util.spec_from_file_location(f"_audited_{abs(hash(str(rel)))}", path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(path.parent))


def main(argv):
    root = pathlib.Path(argv[0]).resolve()
    sys.path.insert(0, str(root))
    sys.addaudithook(hook)
    out = {}
    for f in argv[1:]:
        path = pathlib.Path(f).resolve()
        try:
            load(root, path)
            out[f] = "ok"
        except Effect as e:
            out[f] = f"effect: {e}"
        except ImportError as e:
            out[f] = "refused" if "never import it" in str(e) else f"error: ImportError: {e}"
        except BaseException as e:            # a module that fails on import did nothing further
            out[f] = f"error: {type(e).__name__}: {str(e)[:120]}"
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    main(sys.argv[1:])

"""Run a script as __main__ in the IBM virtualenv, offline: offline.py SCRIPT [args...]

Adapted from round 3's research agent's guard.py. A PEP 578 audit hook, installed before anything else,
refuses and logs:
  - every name lookup and every socket connection or send (no network at all; a bind to loopback, which
    urllib3 tries at import to test for IPv6, is refused too, and urllib3 carries on);
  - every process except git (the anchor) and this Python (the fixer's command line);
  - every file opened for writing, and every directory made, moved or removed, outside QF_TEST_ROOT.
The events are printed to stderr at exit, the refused ones marked BLOCKED, so a test can assert none was a
connection. A child process (git, the fixer) is not hooked: git here only ever talks to a bare repository
on disk.
"""
import atexit
import os
import runpy
import sys

sys.dont_write_bytecode = True
ROOT = os.path.normcase(os.path.realpath(os.environ["QF_TEST_ROOT"]))
EVENTS = []
_WRITE = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
_NET = ("socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyname_ex", "socket.gethostbyaddr",
        "socket.connect", "socket.sendto", "socket.sendmsg", "socket.bind")
_ALLOWED = [False]


_NULL = {os.devnull.lower(), "nul", "\\\\.\\nul", "/dev/null"}


def _inside(path):
    try:
        raw = os.fsdecode(path)
        if raw.lower() in _NULL:                       # the null device: dill opens it at import
            return True
        p = os.path.normcase(os.path.realpath(os.path.abspath(raw)))
    except (TypeError, ValueError):
        return False
    return p == ROOT or p.startswith(ROOT + os.sep)


def _program(cmd):
    try:
        first = cmd[0] if isinstance(cmd, (list, tuple)) else (str(cmd).split('"')[1] if str(cmd).startswith('"')
                                                               else str(cmd).split()[0])
        return os.path.normcase(str(first))
    except (IndexError, TypeError):
        return None


def _hook(event, args):
    if event in _NET:
        EVENTS.append(f"BLOCKED {event} {str(args)[:160]}")
        raise PermissionError(f"offline: {event} refused")
    if event == "open":
        path, mode, flags = args
        writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or \
            (not isinstance(mode, str) and isinstance(flags, int) and bool(flags & _WRITE))
        if writing and isinstance(path, (str, bytes, os.PathLike)) and not _inside(path):
            EVENTS.append(f"BLOCKED write {str(path)[:160]}")
            raise PermissionError(f"offline: a write outside the test's directory: {path}")
    elif event in ("os.mkdir", "os.rename", "os.replace", "os.remove", "os.rmdir", "os.unlink", "shutil.rmtree",
                   "shutil.move"):
        paths = [a for a in args if isinstance(a, (str, bytes, os.PathLike))]
        if any(not _inside(p) for p in paths):
            EVENTS.append(f"BLOCKED {event} {str(args)[:160]}")
            raise PermissionError(f"offline: {event} outside the test's directory")
    elif event == "subprocess.Popen":
        if _program(args[1]) in ("git", os.path.normcase(sys.executable)):
            _ALLOWED[0] = True
            EVENTS.append(f"process {str(args[1])[:120]}")
        else:
            EVENTS.append(f"BLOCKED process {str(args[1])[:120]}")
            raise PermissionError("offline: a process other than git or this python")
    elif event == "_winapi.CreateProcess":
        if not _ALLOWED[0]:
            EVENTS.append(f"BLOCKED process {str(args)[:120]}")
            raise PermissionError("offline: a process other than git or this python")
        _ALLOWED[0] = False
    elif event in ("os.system", "os.startfile", "os.exec", "os.posix_spawn", "os.spawn"):
        EVENTS.append(f"BLOCKED {event}")
        raise PermissionError(f"offline: {event}")


sys.addaudithook(_hook)


@atexit.register
def _report():
    for e in EVENTS:
        print(f"[offline] {e}", file=sys.stderr)


script = sys.argv[1]
sys.argv = [script, *sys.argv[2:]]
sys.path.insert(0, os.path.dirname(os.path.abspath(script)))
runpy.run_path(script, run_name="__main__")

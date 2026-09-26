"""A ctypes shim over libcft, the C library of cft-fp256: the pinned arithmetic.

libcft computes IEEE 754 arithmetic in software on integer limbs, correctly
rounded under whichever of the five rounding attributes a call names, over a
fixed reduction tree, so a call returns the same bits on every machine. This
module is the only place in Quantum-Film that knows libcft is a C library.

WHERE IT LOOKS. `QF_CFT_ROOT` names a cft-fp256 checkout with a built library
(host/cft.dll on Windows, host/libcft.so or host/libcft.dylib elsewhere); the
default is this repository's pinned submodule, vendor/cft-fp256. A git
worktree has that submodule uninitialised, so a worktree points QF_CFT_ROOT
at a built copy. The library found is audited before any number is computed:
its ABI must be the one this shim was written against, and every opcode and
format number used here must carry the name libcft itself gives it, so a
mistranscribed number is refused instead of computing the wrong operation.

WHY NOT cftmpfr. cft-fp256's own Python binding does not bind cft_reduce_seg
(one call for a whole matrix-vector product, over the contract's tree),
cft_sha256 or cft_convert, and the pinned path needs all three.

THE OPERAND ROLES are cft.h's, and they are not uniform: ADD and SUB read `a`
and `c`, MUL, MIN, MAX and the comparisons read `a` and `b`, FMA reads all
three. The wrappers below (add, sub, mul, ...) take their operands in reading
order and put each where cft.h reads it.

A REDUCTION ROUNDS EVERY PRODUCT. CFT_DOT is sum(round(a[i] * b[i])) over the
fixed tree whose left child is the largest power of two below the range
(cft.h, the reduction contract): it is not an fma chain. That is the one dot
form this package uses, everywhere, at every rounding attribute.

REFUSED BY NAME: a status other than OK, and any call that raised invalid,
divide-by-zero or overflow. Nothing in the pinned path should meet a NaN, a
pole or an overflow, and a result that did is not one to decide a crystal on.

NOT THREAD-SAFE, and it says so. A cft_device is not thread-safe (cft.h), and
the pinned sampler hands uncertified rolls to the authority, whose mpmath
precision is process-global. The device belongs to the thread that opened it;
a call from any other thread is refused (ThreadRefusal).
"""
import ctypes
import hashlib
import os
import pathlib
import sys
import threading

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]
ABI = (0, 14)

# Formats, rounding attributes and opcodes: cft.h's numbers. Each opcode and
# format is audited against the library's own name for it when it is loaded.
FP32, FP64, FP128 = 0, 1, 2
FORMATS = {FP32: ("fp32", np.dtype("<f4")), FP64: ("fp64", np.dtype("<f8")), FP128: ("fp128", np.dtype("V16"))}
RNE, RTZ, RDN, RUP, RMM = 0, 1, 2, 3, 4
OPS = {"fma": 0, "add": 1, "sub": 2, "mul": 3, "abs": 4, "neg": 5, "min": 7, "max": 8,
       "cmplt": 12, "cmple": 13, "sum": 24, "dot": 25, "sumsq": 28, "sumabs": 29}
FMA, ADD, SUB, MUL = OPS["fma"], OPS["add"], OPS["sub"], OPS["mul"]
ABS, NEG, MIN, MAX = OPS["abs"], OPS["neg"], OPS["min"], OPS["max"]
CMPLT, CMPLE = OPS["cmplt"], OPS["cmple"]
SUM, DOT, SUMSQ, SUMABS = OPS["sum"], OPS["dot"], OPS["sumsq"], OPS["sumabs"]

FLAG_INVALID, FLAG_DIVBYZERO, FLAG_OVERFLOW, FLAG_UNDERFLOW, FLAG_INEXACT = 1, 2, 4, 8, 16
REFUSED = {FLAG_INVALID: "invalid", FLAG_DIVBYZERO: "divide-by-zero", FLAG_OVERFLOW: "overflow"}


class LibcftMissing(RuntimeError):
    """No built libcft where QF_CFT_ROOT (or the pinned submodule) points."""


class CftError(RuntimeError):
    """A libcft call failed, or raised a flag the pinned path refuses."""


class ThreadRefusal(RuntimeError):
    """libcft was called from a thread other than the one that opened its device."""


def cft_root():
    return pathlib.Path(os.environ.get("QF_CFT_ROOT") or ROOT / "vendor" / "cft-fp256")


def library_path():
    name = {"win32": "cft.dll", "cygwin": "cft.dll", "darwin": "libcft.dylib"}.get(sys.platform, "libcft.so")
    return cft_root() / "host" / name


_LIB = None
_DEV = None
_OWNER = None


def _bind(lib):
    vp, sz, i, u32 = ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_uint32
    u32p = ctypes.POINTER(u32)
    protos = {
        "cft_abi_version": ([], u32),
        "cft_op_name": ([i], ctypes.c_char_p),
        "cft_format_name": ([i], ctypes.c_char_p),
        "cft_strerror": ([i], ctypes.c_char_p),
        "cft_last_error": ([], ctypes.c_char_p),
        "cft_open": ([ctypes.c_char_p, i, ctypes.POINTER(vp)], i),
        "cft_close": ([vp], None),
        "cft_run": ([vp, i, i, i, vp, vp, vp, vp, sz, u32p, u32p], i),
        "cft_reduce": ([vp, i, i, i, vp, vp, vp, sz, u32p, u32p], i),
        "cft_reduce_seg": ([vp, i, i, i, vp, vp, vp, sz, sz, u32p, u32p], i),
        "cft_div": ([vp, i, i, vp, vp, vp, sz, u32p, u32p], i),
        "cft_sqrt": ([vp, i, i, vp, vp, sz, u32p, u32p], i),
        "cft_cospi": ([vp, i, i, vp, vp, sz, u32p], i),
        "cft_sinpi": ([vp, i, i, vp, vp, sz, u32p], i),
        "cft_convert": ([vp, i, i, i, vp, vp, sz, u32p], i),
        "cft_next_up": ([vp, i, vp, vp, sz, u32p], i),
        "cft_next_down": ([vp, i, vp, vp, sz, u32p], i),
        "cft_sha256": ([vp, sz, vp], i),
    }
    for name, (args, res) in protos.items():
        fn = getattr(lib, name)
        fn.argtypes, fn.restype = args, res
    v = lib.cft_abi_version()
    if (v >> 16, v & 0xFFFF) != ABI:
        raise LibcftMissing(f"libcft at {library_path()} reports ABI {v >> 16}.{v & 0xFFFF}; the pinned path is "
                            f"written against {ABI[0]}.{ABI[1]}")
    wrong = [f"op {n} = {k} is {lib.cft_op_name(k).decode()!r}" for n, k in OPS.items()
             if lib.cft_op_name(k).decode() != n]
    wrong += [f"format {n} = {k} is {lib.cft_format_name(k).decode()!r}" for k, (n, _) in FORMATS.items()
              if lib.cft_format_name(k).decode() != n]
    if wrong:
        raise LibcftMissing("this shim's numbers disagree with the library's names: " + "; ".join(wrong))
    return lib


def lib():
    global _LIB
    if _LIB is None:
        path = library_path()
        if not path.exists():
            raise LibcftMissing(f"libcft is not built at {path}. Point QF_CFT_ROOT at a cft-fp256 checkout with "
                                f"a built library (CLAUDE.md has the build line); the runner's pinned stage skips "
                                f"by name when it is absent")
        _LIB = _bind(ctypes.CDLL(str(path)))
    return _LIB


def identity():
    """(path, SHA-256 of the library file, ABI): the library's identity, since the ABI alone names a
    calling surface and not a build (verifier-P0 11b)."""
    path = library_path()
    lib()
    return str(path), hashlib.sha256(path.read_bytes()).hexdigest(), f"{ABI[0]}.{ABI[1]}"


def device():
    """The software device, opened once, owned by the thread that opened it."""
    global _DEV, _OWNER
    me = threading.get_ident()
    if _DEV is None:
        h = ctypes.c_void_p()
        _status(lib().cft_open(None, 0, ctypes.byref(h)), "cft_open")
        _DEV, _OWNER = h, me
    elif _OWNER != me:
        raise ThreadRefusal("libcft's device belongs to the thread that opened it; a cft_device is not "
                            "thread-safe (cft.h), and the pinned sampler hands off to an authority whose "
                            "mpmath precision is process-global, so the pinned path runs on one thread")
    return _DEV


def _status(st, where):
    if st != 0:
        L = lib()
        raise CftError(f"{where}: {L.cft_strerror(st).decode()} (status {st}): {L.cft_last_error().decode()}")


def _flags(flags, where):
    bad = [name for bit, name in REFUSED.items() if flags & bit]
    if bad:
        raise CftError(f"{where} raised {', '.join(bad)}; the pinned path refuses a result that met a NaN, "
                       f"a pole or an overflow")


def dtype(fmt):
    return FORMATS[fmt][1]


def arr(x, fmt, n=None):
    """x as a contiguous 1-D array of fmt's encodings. Its dtype must already be fmt's: numpy is never asked
    to convert between formats, because that conversion rounds outside libcft. (A Python float is binary64.)"""
    if type(x) is np.ndarray and x.ndim == 1 and x.dtype == FORMATS[fmt][1] and x.flags.c_contiguous \
            and (n is None or len(x) == n):
        return x
    a = np.asarray(x)
    if a.dtype != dtype(fmt):
        raise TypeError(f"an operand of dtype {a.dtype} given to a {FORMATS[fmt][0]} call; the pinned path "
                        f"changes format only through cft_convert or quantum_film.pinned.encode")
    a = np.ascontiguousarray(a.reshape(-1))
    if n is not None and len(a) != n:
        raise ValueError(f"operand has {len(a)} elements, not {n}")
    return a


def _ptr(a):
    return None if a is None else a.ctypes.data


def run(op, fmt, rnd, a, b=None, c=None):
    """d[i] = op(a[i], b[i], c[i]), cft.h's elementwise call; operands in cft.h's roles."""
    dev = device()
    a = arr(a, fmt)
    n = len(a)
    b = None if b is None else arr(b, fmt, n)
    c = None if c is None else arr(c, fmt, n)
    d = np.empty(n, dtype(fmt))
    fl = ctypes.c_uint32(0)
    if n:
        _status(lib().cft_run(dev, op, fmt, rnd, _ptr(a), _ptr(b), _ptr(c), _ptr(d), n, ctypes.byref(fl), None),
                "cft_run")
        _flags(fl.value, f"cft_run op {op}")
    return d


def add(fmt, rnd, x, y):
    return run(ADD, fmt, rnd, x, None, y)


def sub(fmt, rnd, x, y):
    return run(SUB, fmt, rnd, x, None, y)


def mul(fmt, rnd, x, y):
    return run(MUL, fmt, rnd, x, y)


def fma(fmt, rnd, x, y, z):
    return run(FMA, fmt, rnd, x, y, z)


def neg(fmt, x):
    return run(NEG, fmt, RNE, x)


def maximum(fmt, x, y):
    return run(MAX, fmt, RNE, x, y)


def less(fmt, x, y):
    """x[i] < y[i] as booleans, compared by libcft: CMPLT writes 1.0 or +0.0, and +0.0 is all zero bytes."""
    r = run(CMPLT, fmt, RNE, x, y)
    return r.view(np.uint8).reshape(len(r), -1).any(axis=1)


def reduce(op, fmt, rnd, a, b=None):
    """One element: cft_reduce over the contract's fixed tree."""
    dev = device()
    a = arr(a, fmt)
    b = None if b is None else arr(b, fmt, len(a))
    d = np.empty(1, dtype(fmt))
    fl = ctypes.c_uint32(0)
    _status(lib().cft_reduce(dev, op, fmt, rnd, _ptr(a), _ptr(b), _ptr(d), len(a), ctypes.byref(fl), None),
            "cft_reduce")
    _flags(fl.value, f"cft_reduce op {op}")
    return d


def reduce_seg(op, fmt, rnd, a, b, seg):
    """n / seg elements: the same tree over every segment of `seg` elements (cft_reduce_seg, ABI 0.13)."""
    dev = device()
    a = arr(a, fmt)
    n = len(a)
    b = None if b is None else arr(b, fmt, n)
    if seg < 1 or n % seg:
        raise ValueError(f"{n} elements are not a whole number of segments of {seg}")
    d = np.empty(n // seg, dtype(fmt))
    fl = ctypes.c_uint32(0)
    if n:
        _status(lib().cft_reduce_seg(dev, op, fmt, rnd, _ptr(a), _ptr(b), _ptr(d), n, seg, ctypes.byref(fl), None),
                "cft_reduce_seg")
        _flags(fl.value, f"cft_reduce_seg op {op}")
    return d


def div(fmt, rnd, a, b):
    dev = device()
    a = arr(a, fmt)
    b = arr(b, fmt, len(a))
    d = np.empty(len(a), dtype(fmt))
    fl = ctypes.c_uint32(0)
    _status(lib().cft_div(dev, fmt, rnd, _ptr(a), _ptr(b), _ptr(d), len(a), ctypes.byref(fl), None), "cft_div")
    _flags(fl.value, "cft_div")
    return d


def sqrt(fmt, rnd, a):
    dev = device()
    a = arr(a, fmt)
    d = np.empty(len(a), dtype(fmt))
    fl = ctypes.c_uint32(0)
    _status(lib().cft_sqrt(dev, fmt, rnd, _ptr(a), _ptr(d), len(a), ctypes.byref(fl), None), "cft_sqrt")
    _flags(fl.value, "cft_sqrt")
    return d


def _unary(name, fmt, rnd, a):
    dev = device()
    a = arr(a, fmt)
    d = np.empty(len(a), dtype(fmt))
    fl = ctypes.c_uint32(0)
    _status(getattr(lib(), name)(dev, fmt, rnd, _ptr(a), _ptr(d), len(a), ctypes.byref(fl)), name)
    _flags(fl.value, name)
    return d


def cospi(fmt, rnd, a):
    """cos(pi * a), correctly rounded under `rnd`; the argument is exact, so a dyadic angle needs no pi."""
    return _unary("cft_cospi", fmt, rnd, a)


def sinpi(fmt, rnd, a):
    return _unary("cft_sinpi", fmt, rnd, a)


def convert(sfmt, dfmt, rnd, a):
    """formatOf-convertFormat: widening is exact, narrowing rounds once under `rnd`."""
    dev = device()
    a = arr(a, sfmt)
    d = np.empty(len(a), dtype(dfmt))
    fl = ctypes.c_uint32(0)
    _status(lib().cft_convert(dev, sfmt, dfmt, rnd, _ptr(a), _ptr(d), len(a), ctypes.byref(fl)), "cft_convert")
    _flags(fl.value, "cft_convert")
    return d


def _step(name, fmt, a):
    dev = device()
    a = arr(a, fmt)
    d = np.empty(len(a), dtype(fmt))
    fl = ctypes.c_uint32(0)
    _status(getattr(lib(), name)(dev, fmt, _ptr(a), _ptr(d), len(a), ctypes.byref(fl)), name)
    _flags(fl.value, name)
    return d


def next_up(fmt, a):
    """nextUp (754-2019 5.3.1): the least encoding above each element. Exact; no rounding attribute."""
    return _step("cft_next_up", fmt, a)


def next_down(fmt, a):
    return _step("cft_next_down", fmt, a)


def sha256(data):
    """FIPS 180-4 SHA-256 of `data`, computed by libcft (cft_sha256, ABI 0.9)."""
    data = bytes(data)
    out = ctypes.create_string_buffer(32)
    buf = ctypes.create_string_buffer(data, len(data)) if data else None
    device()
    _status(lib().cft_sha256(buf, len(data), out), "cft_sha256")
    return out.raw

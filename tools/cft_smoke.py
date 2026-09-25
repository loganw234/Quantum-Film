#!/usr/bin/env python3
"""libcft smoke: the pinned library loads, reports ABI 0.14, and computes one
correctly rounded cosine that matches the bits recorded in cft-fp256's own
survey of 2026-09-25 (cos(1) at binary64 = 0x1.14a280fb5068cp-1).

The DLL is built from the pinned submodule (vendor/cft-fp256), never from the
owner's own checkout, where another session may be working. The build
commands and their traps are in CLAUDE.md.
"""
import ctypes
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DLL = ROOT / "vendor" / "cft-fp256" / "host" / "cft.dll"
if not DLL.exists():
    print(f"{DLL} is not built")
    sys.exit(1)
lib = ctypes.CDLL(str(DLL))
lib.cft_abi_version.restype = ctypes.c_uint32
v = lib.cft_abi_version()
if (v >> 16, v & 0xFFFF) != (0, 14):
    print(f"ABI {v >> 16}.{v & 0xFFFF}, not 0.14")
    sys.exit(1)
sys.path.insert(0, str(ROOT / "vendor" / "cft-fp256" / "bindings" / "python"))
from cftmpfr import Context, batch  # noqa: E402

import numpy as np  # noqa: E402

ctx = Context(53)
out, _flags = batch.cos(ctx, np.array([1.0]))
bits = struct.unpack("<Q", struct.pack("<d", float(out[0])))[0]
want = struct.unpack("<Q", struct.pack("<d", float.fromhex("0x1.14a280fb5068cp-1")))[0]
if bits != want:
    print(f"cos(1) = {float(out[0]).hex()}, not 0x1.14a280fb5068cp-1")
    sys.exit(1)
print(f"libcft ABI 0.14 loaded from {DLL.relative_to(ROOT)}; cos(1) = {float(out[0]).hex()}, correctly rounded")

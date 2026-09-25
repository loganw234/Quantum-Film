#!/usr/bin/env python3
"""libcft smoke: the pinned library loads, reports ABI 0.14, and computes one
correctly rounded cosine that matches the bits recorded in cft-fp256's own
survey of 2026-09-25 (cos(1) at binary64 = 0x1.14a280fb5068cp-1).

The DLL checked is the one QF_CFT_ROOT names (default: the pinned submodule,
vendor/cft-fp256), because that is the one the parcels load; a git worktree's
own submodule is uninitialised. The binding is pointed at the same file
through CFT_LIB, so the ABI and the cosine come from one DLL. Its path and
SHA-256 are printed: the ABI number is the only identity the DLL exports, and
a stale build with the same ABI would pass on that alone (verifier-P0 11b).

The DLL is built from the pinned submodule, never from the owner's own
checkout, where another session may be working. The build commands and their
traps are in CLAUDE.md.
"""
import ctypes
import hashlib
import os
import pathlib
import struct
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFT_ROOT = pathlib.Path(os.environ.get("QF_CFT_ROOT") or ROOT / "vendor" / "cft-fp256")
DLL = CFT_ROOT / "host" / "cft.dll"
# One constant per fact: the comparison and the failure message read the same
# value. (A first version hard-coded the message and printed "ABI 0.14, not
# 0.14" when a sabotaged copy expected 0.13; 2026-09-25.)
ABI = (0, 14)
COS1 = "0x1.14a280fb5068cp-1"
if not DLL.exists():
    print(f"{DLL} is not built")
    sys.exit(1)
lib = ctypes.CDLL(str(DLL))
lib.cft_abi_version.restype = ctypes.c_uint32
v = lib.cft_abi_version()
if (v >> 16, v & 0xFFFF) != ABI:
    print(f"ABI {v >> 16}.{v & 0xFFFF}, expected {ABI[0]}.{ABI[1]}")
    sys.exit(1)
os.environ["CFT_LIB"] = str(DLL)
sys.path.insert(0, str(CFT_ROOT / "bindings" / "python"))
from cftmpfr import Context, batch  # noqa: E402

import numpy as np  # noqa: E402

ctx = Context(53)
out, _flags = batch.cos(ctx, np.array([1.0]))
bits = struct.unpack("<Q", struct.pack("<d", float(out[0])))[0]
want = struct.unpack("<Q", struct.pack("<d", float.fromhex(COS1)))[0]
if bits != want:
    print(f"cos(1) = {float(out[0]).hex()}, expected {COS1}")
    sys.exit(1)
sha = hashlib.sha256(DLL.read_bytes()).hexdigest()
print(f"libcft ABI {ABI[0]}.{ABI[1]} loaded from {DLL} (sha256 {sha[:16]}...); "
      f"cos(1) = {float(out[0]).hex()}, correctly rounded")

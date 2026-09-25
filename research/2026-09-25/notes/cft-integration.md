# libcft as the pinned arithmetic layer for "fixer": integration survey

Read-only survey of `C:\Users\logan\source\repos\cft-fp256`, 2026-09-25, for the
Moth Quantum hackathon project "fixer" (the quantum film stock).

**How to read the citations.** `path:line` is relative to the cft-fp256 root.
`mem-build:N` is `C:\Users\logan\.claude\projects\C--Users-logan-source-repos\memory\reference-cft-host-build-windows.md`
and `mem-tools:N` is `reference-desktop-toolchains.md` in the same folder.

**Labels.**
- **INFERRED** marks my reasoning, which I did not read in a file.
- **MEASURED** marks a spot check I ran this session. I built nothing and wrote nothing into the repo. The checks were: `objdump`/`file` on existing binaries; the committed WASM module loaded in memory by Node; and `curl` of the live pages.
- **ESTIMATE** marks the throughput projections that question 4 asked for.
- Everything else was read directly.

**Repo state (one line):** HEAD `7d7285dfd735cb32faeee609c68c829c85b1593e` on branch `main` (equal to `origin/main` as last fetched). The tree was clean at the start of the survey. By 10:57 two untracked files, `trunc.c` and `trunc.exe`, had appeared at the repo root, created at 10:55 by another process (not this survey). Three other worktrees exist: `ode-round`, `ode-round-f0b` and `verify-v1`.

---

## The answers in one screen

1. **Coverage.** Everything the pipeline needs is in the C ABI (ABI 0.14):
   - elementwise add/sub/mul/fma through `cft_run`;
   - correctly rounded `cft_div`/`cft_sqrt`;
   - reductions over a fixed tree, including a segmented form (`cft_reduce_seg`), which makes a matrix-vector product one call;
   - all 39 IEEE 754-2019 table 9.1 functions, correctly rounded at all four formats under all five rounding attributes;
   - exact decimal/hex conversions and SHA-256.

   It has no matrix routines, no prefix scan and no RNG. Python reaches it through `bindings/python/cftmpfr`, which is pure ctypes (no cffi anywhere). That package does not bind `cft_run_ex`, `cft_reduce_seg`, programs, buffers, `cft_sha256` or `cft_convert`.
2. **Building and loading.**
   - **Python:** build `host/cft.dll` with mingw64 gcc, `OS=Windows_NT`, and `TMP`/`TEMP` passed as make variables, in a private clone.
   - **Node:** works from the committed module with no build.
   - **Browser:** needs a web loader that only the Docker `build.sh` produces.
   - **Live pages:** byte-identical to HEAD (MEASURED).
3. **Determinism.** Every contract operation returns the same bits on every backend and platform, flags included.
   - Not covered: timing, NaN payloads, the status word, and per-backend capacities.
   - Evidence gaps: WASM is measured on V8 only; cross-card agreement is not yet shown.
4. **Throughput (software, fp64).** About 200-320 ns per mul/fma and 4.5-5.6 µs per div/sqrt.
   - **Transcendentals are unmeasured in the repo.** MEASURED here: about 0.2-0.4 ms per element at fp64 and 0.6-1.1 ms at fp128.
   - ESTIMATES: about 0.12-0.15 s per general single-qubit gate on 2^16 amplitudes at fp64, and about 30-45 ms per 64-site / 32-particle DPP sample at fp64.
5. **Sequencer.** Both kernels are expressible as programs. The binding limits are:
   - 64 deposits per lane on the tile, 32 registers, 256 scratch slots, a 512-entry constant bank;
   - nothing composed inside a program (no transcendentals, no div/sqrt except by inlining), and no cross-lane operations;
   - gathers cost 310-340 ns per element on the tile;
   - a program runs on tile 0 only.
6. **Licence.** Apache-2.0 with a NOTICE file. Usable from MIT or Apache projects. Ship the LICENSE and the NOTICE text with any vendored source or distributed binary, including a WASM module inside a web page.
7. **Hackathon path.** Python-first at binary64, with numpy arrays as the carrier and libcft for every operation that rounds. Pin a submodule at 7d7285d. Use Node/WASM for the browser verifier.
   - Hours-sink 1: the Windows DLL build traps.
   - Hours-sink 2: the cost of transcendentals.

---

## 1. What libcft exposes

### 1.1 The ABI

- **Language and version.** Plain C99, one header, `host/include/cft.h`. The ABI is 0.14: `CFT_ABI_VERSION_MAJOR 0` and `MINOR 14` (cft.h:111-112). `cft_abi_version()` returns `(major<<16)|minor`, which is 14 today. Check it at run time rather than trusting the header (cft.h:103-110, 114-129).
- **Exports.** `CFT_API` becomes `__declspec(dllexport)` under `CFT_BUILD_SHARED` on Windows (cft.h:85-101).
- **Status codes.** `cft_status` (cft.h:134-157), with `cft_strerror` and `cft_last_error`. The last-error slot is static and not thread-safe (cft.h:159-168).
- **Formats.** `CFT_FP32/64/128/256` are 0..3; binary256 has p = 237 (cft.h:177-182).
- **Buffers.** Dense, little-endian arrays of interchange encodings, `cft_format_size(fmt)` bytes per element. `n` is arbitrary, and `d` may alias an input (cft.h:816-826; CONFORMANCE.md:52-60).
- **Devices.**
  - `cft_open(NULL, 0, &dev)` is the software backend, with no card and no driver (cft.h:50-54, 373-388).
  - `"cft://host:port"` is a remote device (cft.h:390-446).
  - An `.xclbin` path is the tile, and only in `XRT=1` builds (cft.h:6-18).
- **Threads.** A `cft_device` is not thread-safe: open one per thread (cft.h:382-384). Neither `host/src` nor `host/include` contains any thread code, so the software backend is strictly one core per device (grep). BENCHMARKS.md:627-628 says every software row is one core.
- **Asking before calling.** `cft_get_caps` and `cft_supports` report what a device implements (cft.h:448-579, 795-803).

### 1.2 Elementwise arithmetic, at binary64, 128 and 256 alike

| need | call | notes |
|---|---|---|
| add, sub, mul, fma | `cft_run(dev, op, fmt, rnd, a, b, c, d, n, &flags, &bus)` (cft.h:842-852) | `CFT_ADD`/`CFT_SUB` read `a` and `c`; `CFT_MUL` reads `a` and `b`; `CFT_FMA` is `a*b + c` with one rounding (cft.h:190-196). The flags are the OR over the run. |
| scalar broadcast, gathered operands | `cft_run_ex` with `cft_elem_args` (`scalar_mask`, `idx_a/b/c`) (cft.h:2579-2660) | Portable. On the software backend a scalar is simply element 0. |
| div, sqrt | `cft_div`, `cft_sqrt` (cft.h:1029-1046) | Correctly rounded per 5.4.1 under every attribute. Composed from roughly 25-30 passes (cft.h:995-1011), which makes them 15-25x the cost of an fma in software. |
| the rest of the useful set | `cft_rsqrt` (cft.h:1751-1753); `cft_hypot` (cft.h:1319-1321); abs/neg/copysign/min/max/select/cmp (cft.h:197-222); integer ops on the encodings, including `CFT_IMUL` (cft.h:224-236, 286-305); `cft_rint` for floor/ceil/trunc (cft.h:1077-1084); `cft_scaleb` (cft.h:1086-1091); augmented add/sub/mul, the TwoSum/TwoProduct pairs (cft.h:1994-2093) | The comparisons return 1.0 or +0.0, so `CFT_SELECT` consumes them directly (cft.h:212-222). |

### 1.3 Reductions, and their ordering rules

- **The call.** `cft_reduce(dev, op, fmt, rnd, a, b, d, n, &flags, &bus)` writes ONE element (cft.h:854-937). The opcodes are:
  - `CFT_SUM`;
  - `CFT_DOT`, which is Σ round(a[i]·b[i]): each product is rounded, so it is *not* an fma chain (cft.h:247);
  - `CFT_SUMSQ` and `CFT_SUMABS`, compositions over the same tree (cft.h:267-284, 899-919);
  - `CFT_MAXALL` (cft.h:307-336).
- **Ordering rule.** Every reduction is a fixed binary tree over the element index.
  - The left child of a node is the largest power of two strictly smaller than its range.
  - Every node is rounded under the caller's attribute.
  - It is never a sequential accumulation, never reassociated, never padded (cft.h:871-888; CONFORMANCE.md:128-142).
  - The definition is `python/cft_golden/reduce.py` (`split`, reduce.py:305).
  - The schedule, the operand order within a pair, and which tile evaluates a node are all free: four tiles return one tile's bits (DETERMINISM.md:1336-1381).
  - Edge cases: n = 0 gives +0, and n = 1 returns a[0] verbatim (cft.h:890-897). `MAXALL` needs no tree because the 754 maximum is exactly associative (cft.h:319-326).
- **`cft_reduce_seg`.** The same tree applied to every segment of `seg` elements, with `n/seg` outputs (cft.h:939-981). The software backend has carried it since ABI 0.13.
  - INFERRED use: a matrix-vector product A·x (m rows × n columns) is one call, `cft_reduce_seg(CFT_DOT, A_flat, x_tiled, m*n, seg=n)`, with a fixed summation order per row.
- **Scaled products.** `cft_scaled_prod*` returns a (significand, int64 scale) pair and cannot overflow or underflow (cft.h:1873-1992). INFERRED use: DPP likelihoods and determinants as products of pivots.
- **Missing: a prefix scan (cumulative sum).** Compose one from `cft_run` adds; the association order is then yours to pin (INFERRED).

### 1.4 Transcendentals

- **Which ones.** All thirty-nine functions of 754-2019 table 9.1 (CAPABILITIES.md:184-200; cft.h:1217-1871):
  - exp, expm1, exp2, exp2m1, exp10, exp10m1;
  - log, log1p, log2, log2p1, log10, log10p1;
  - pow, pown, powr, compound, rootn, rsqrt, hypot;
  - **sin, cos, tan** of a radian argument, reduced by Payne-Hanek against a stored 270,336-bit 2/π (cft.h:1783-1797);
  - sinpi, cospi, tanpi, asin, acos, atan;
  - **atan2** (y first: cft.h:1431-1435), asinpi, acospi, atanpi, atan2pi;
  - sinh, cosh, tanh, asinh, acosh, atanh.
- **Correctly rounded.** At all four formats, under all five attributes, with exact flags (cft.h:1227-1236, 1334-1336, 1658-1664, 1781-1785; DETERMINISM.md:326-330; TRANSCENDENTALS.md:17-36). This is the MPFR-parity-checked claim.
- **Refusal instead of a guess.** An input that cannot be proven correctly rounded within the working-precision cap returns `CFT_ERR_INTERNAL`, never a plausible number (cft.h:1282-1288). The radian reduction also refuses past the reach of its stored constant (cft.h:1794-1797).
- **HOST operations.** No device pass on any backend: on a tile or a remote handle they run on the client CPU (cft.h:1238-1245, 398-409; TRANSCENDENTALS.md:38-65; CAPABILITIES.md:194-213).
- **Dyadic arguments are cheap to reduce.** sinpi/cospi reduce exactly for dyadic arguments (cft.h:1338-1345). On a 64-site ring every phase 2πkd/64 equals π·(kd/32), which is an exact binary64 input to `cft_cospi`/`cft_sinpi`.
- **Signatures.**
  - `cft_cos(dev, fmt, rnd, a, d, n, &flags)` takes no bus word (cft.h:1845-1850).
  - `cft_atan2(dev, fmt, rnd, y, x, d, n, &flags)` (cft.h:1433-1435).
  - `cft_pow(dev, fmt, rnd, a, b, d, n, &flags)` (cft.h:1316-1318).
- **Rounding modes.** `CFT_RNE/RTZ/RDN/RUP/RMM` = 0..4 (cft.h:344-353; DETERMINISM.md:101-116).
  - `cft_run` selects the attribute per call; programs select it per instruction (DETERMINISM.md:143-148; SEQUENCER.md:551-555).
  - roundTiesTowardZero exists only inside the augmented operations (DETERMINISM.md:118-125).

### 1.5 Conversions: Python floats and decimal strings

- **In C.**
  - `cft_convert` changes format: widening is exact, narrowing rounds once (cft.h:1102-1110).
  - Integer conversions: `cft_cvt_from_{i32,u32,i64,u64}` and `cft_cvt_to_*` (cft.h:1112-1150).
  - `cft_from_decimal_char` converts a batch of strings of any length, correctly rounded (cft.h:1545-1557).
  - `cft_to_decimal_char` converts one value: `digits = 0` gives the exact decimal, `digits >= 1` a correctly rounded one (cft.h:1559-1583).
  - `cft_format_decimal_digits` gives Pmin, the round-trip digit count: 9/17/36/73 (cft.h:1533-1543).
  - Hex sequences: `cft_from_hex_char` and `cft_to_hex_char` (cft.h:1585-1608).
  - The syntax is strict: no whitespace, no locale (cft.h:1500-1518).
- **Python floats (cftmpfr).**
  - `Context.from_float` is exact into binary64/128/256 (core.py:612-634).
  - `Float.to_float` is exact from binary64; from a wider format it rounds through gmpy2 or refuses (core.py:245-260).
  - `batch.*` accepts numpy arrays directly: float64 for a binary64 context, returning float64 (batch.py:15-24, 81-104). INFERRED from the byte layout: numpy float64 and libcft fp64 are the same bits, so there is no conversion step.
  - binary128/256 travel as `V16`/`V32` or uint8 arrays (batch.py:21-24, 86-100).
  - A single `Float` operand broadcasts (batch.py:25-27, 124-127).
- **Decimal strings (cftmpfr).**
  - `Context.from_str` and `from_decimal` go through the library (core.py:636-652).
  - `Float.to_decimal(digits)` (core.py:317-337); `to_hex`.
  - `to_str` needs gmpy2 (core.py:262-279).

### 1.6 The Python-facing surface: yes, a real binding

- **`bindings/python/cftmpfr/`**: pure stdlib ctypes, no build step (bindings/python/README.md:28-34; `_lib.py:1-11`).
  - **Discovery order:** `CFT_LIB`, then `<repo>/host/cft.dll`, then a copy beside the package, then `find_library` (`_lib.py:12-34, 146-178`).
  - Every prototype is declared, because ctypes' default int return truncates pointers on Win64 (`_lib.py:181-185`). Opcode and format numbers are audited against the loaded library at bind time (`_lib.py:378-423`).
  - **`Context`:** `Context(precision, rounding="RNDN", artifact=None)`. The precision is 24/53/113/237. The rounding names are RNDN/RNDZ/RNDD/RNDU/RNDNA. `artifact` is `None`, an xclbin path or `cft://` (core.py:445-466; bindings/python/README.md:66-69, 145-158).
  - **`batch` covers:** fma/add/sub/mul/div/sqrt, the 39 transcendentals, `tree_sum`/`tree_dot`/`tree_sumsq`/`tree_sumabs`, the scaled products, the augmented pairs, formatOf and the min/max-mag forms (batch.py:145-821).
- **Not bound by cftmpfr** (a diff of cft.h's exports against the names cftmpfr uses; the four min/max-mag forms *are* bound by constructed name at `_lib.py:340-344`):
  - `cft_run_ex`, `cft_reduce_seg` (also stated at COMPATIBILITY.md:607);
  - all program calls (COMPATIBILITY.md:456, 501) and all buffer calls;
  - `cft_sha256`, `cft_convert`, `cft_cvt_*`, `cft_rint`, `cft_scaleb`, `cft_logb`;
  - `cft_next_up/down`, `cft_rem`, `cft_class`, `cft_total_order*`, `cft_cmp_sig`, `cft_conformance`.

  Also: the integer opcodes 16-23 and 30 have no named constants (`_lib.py:74-80`), although `_lib.run` accepts any opcode number. The `Caps` mirror stops at `backend` (`_lib.py:426-434`; COMPATIBILITY.md:422).
- **Other Python callers of libcft.** `host/examples/vector_fma_ctypes.py` is the minimal CDLL-plus-seven-argtypes pattern (lines 11-12, 48-88). The `host/tests/*_check.py` harnesses use ctypes too. There is no cffi anywhere in the tree (grep).
- **Golden model.** `python/cft_golden` is separate, pure Python on stdlib ints, with mpmath only for the transcendentals (python/README.md:1-9; README.md:171).
  - Functions take and return bit patterns: for example `softfloat.fma(FP64, xa, xb, xc, rnd)` returns `(bits, flags)` (softfloat.py:332-333); `transcend.cos(fmt, xa, rnd)` (transcend.py:1752); `reduce.fsum`/`fdot` (reduce.py:468-473).
  - It is the definition everything is scored against (CLAUDE.md:161-165; CONFORMANCE.md:45-48).
  - Its speed is not measured in the repo. INFERRED: fine for spot checks, far too slow for a pipeline.

### 1.7 Node and browser surface

- **`bindings/node`** exports the 141 `cftw_*` functions one to one. On top sit `Context`/`Float`, `map`, `mapEx` (scalar and gathered operands), `reduce`, `reduceSeg` and `loadProgram`/`run` (COMPATIBILITY.md:52; bindings/node/README.md:15-26, 177-190, 221-240; core.mjs:2098, 2297, 2471, 2510, 2575).
- **Transport.** `Uint8Array` carries the bits; BigInt holds exact scalars; `fromNumber`/`toNumber` go through `cft_convert` (bindings/node/README.md:470-484).

---

## 2. Building and loading on this desktop

### 2.1 For Python (Windows)

**Rule 0: build in your own clone, never in `C:\Users\logan\source\repos\cft-fp256`.** Another session is active there (see the repo state), and `make -C host clean` removes every tool in `host/` (CLAUDE.md:75-77).

**The command** is the owner's tested invocation (mem-build:56-61), which is what the verification runner's `HOSTMAKE` does (verify/run.sh:93-121). Run it from Git Bash:

```bash
git clone https://github.com/loganw234/cft-fp256.git /c/Users/logan/source/repos/moth-quantum/vendor/cft-fp256
cd /c/Users/logan/source/repos/moth-quantum/vendor/cft-fp256
git checkout 7d7285dfd735cb32faeee609c68c829c85b1593e
rm -f host/src/*.o host/src/*.lo host/libcft.a
PATH="/c/msys64/mingw64/bin:$PATH" make -C host CC=gcc OS=Windows_NT \
  TMP='C:/Users/logan/AppData/Local/Temp' TEMP='C:/Users/logan/AppData/Local/Temp' \
  all > build.log 2>&1
```

- That produced zero errors and zero warnings on 2026-09-12 (mem-build:63).
- INFERRED shortcuts, not run:
  - Replacing `all` with `cft.dll` builds only the `$(SHLIB)` target (Makefile:92-95, 219-220).
  - The equivalent one-liner is `gcc -std=c99 -O2 -Ihost/include -DCFT_BUILD_SHARED -shared host/src/*.c -o host/cft.dll -Wl,--out-implib,host/libcft.dll.a`. It mirrors Makefile:60-63, 205-207 and 219-220. `host/src/*.c` is exactly the Makefile's `SRC` (build.sh cross-checks this: bindings/wasm/build.sh:191-204).

**Sanity checks before touching Python:**

```bash
file host/cft.dll                                                  # PE32+ ... x86-64
/c/msys64/mingw64/bin/objdump -p host/cft.dll | grep -c ' cft_'    # ~120; 0 = the OS=Windows_NT trap
```

**Loading it:**

```python
import os, sys, numpy as np
os.environ["CFT_LIB"] = r"C:\Users\logan\source\repos\moth-quantum\vendor\cft-fp256\host\cft.dll"
sys.path.insert(0, r"C:\Users\logan\source\repos\moth-quantum\vendor\cft-fp256\bindings\python")
from cftmpfr import Context, batch
ctx = Context(53)                          # binary64, RNDN, software backend
x = np.linspace(0.0, 1.0, 8)
y, flags = batch.fma(ctx, x, x, x)         # float64 in, float64 out, one C call
```

**Where the DLL lands.** `host/cft.dll`, with the import library `host/libcft.dll.a` and the static `host/libcft.a` beside it (Makefile:92-95, 216-220). All are gitignored (.gitignore:57-60).
- MEASURED on the owner's existing copy: `objdump -p` shows the DLL imports only `KERNEL32.dll` and `msvcrt.dll`, so any 64-bit Python loads it without MSYS on PATH.
- Winsock is loaded lazily, only for `cft://` (cft.h:441-445).

**Python on this desktop.** MEASURED: `C:\Users\logan\AppData\Local\Programs\Miniconda3\python.exe` 3.12.9, 64-bit. It has numpy, gmpy2, mpmath and pytest (mem-tools:31-33). Run the package's own tests with `python -m pytest bindings/python/test_cftmpfr.py` (bindings/python/README.md:71-76).

**The traps, each of which looks like something else:**

| symptom | cause | fix | source |
|---|---|---|---|
| `undefined reference to cft_open`; `file format not recognized` on a good COFF object; `cc.exe: internal compiler error ... collect2`; `WinError 193` from ctypes | bare `cc`/`gcc` resolves to MSYS2 **mingw32 (i686)** | prepend `/c/msys64/mingw64/bin`; `cc -dumpmachine` must say x86_64; delete the 32-bit objects | mem-build:36-55; mem-tools:11-24; Makefile:29-39 |
| ctypes: `function 'cft_open' not found` | make did not see `OS=Windows_NT`, took the unix branch, and built with `-fvisibility=hidden` and no dllexport | pass `OS=Windows_NT`; delete `*.lo`/`*.o`; rebuild | mem-build:21, 86-91 |
| gcc: `Cannot create temporary file in C:\WINDOWS\` | MSYS make strips the recipe environment | pass `TMP`/`TEMP` as **make command-line variables** | mem-build:20; mem-tools:43-47 |
| undefined references incl. `__snprintf_chk` | ELF objects left by a WSL build of the same tree | `make -C host clean`; `objdump -f host/src/device.o` shows which platform built it | mem-build:26-34 |
| hang at 0% CPU, no message | a long make piped through `\| grep \| head` | redirect to a file, then grep it | CLAUDE.md:112-114 |
| the old behaviour after a fix | test tools link `libcft.a` statically, and `all` does not rebuild them | name the targets; check timestamps | CLAUDE.md:101-110; mem-build:65-84 |

**The prebuilt copy in the owner's checkout.** MEASURED: `host/cft.dll` from 2026-09-18 09:55, PE32+ x86-64, 122 `cft_` exports. It is untracked. It predates commit `8a8f492` (2026-09-24), which made the software handle publish SCALAR/REDUCE_SEG and made `cft_supports(IMUL)` answer yes (COMPATIBILITY.md:726-758). The bits are unchanged, but don't ship it.

### 2.2 For Node

**No build needed.** The committed module is `bindings/node/cft_node.wasm`: 257,252 bytes, sha256 `3737534db4d44304…`, which matches bindings/wasm/README.md:1003 (MEASURED). Beside it is `cft_node.js`, the Node loader.
- The package `cft-node` 0.11.0 is `"private": true`, so it is not on npm; it needs node >= 18 (bindings/node/package.json:2-16).
- **Usage:**

```js
import { Context } from "./vendor/cft-fp256/bindings/node/index.mjs";
const ctx = await Context.open(64);
```

  Tests: `node bindings/node/test.mjs`; conformance: `node bindings/node/conformance.mjs` after `make vectors` (bindings/node/README.md:9-26).
- MEASURED on this desktop with Node v22.19.0: it loads and reports ABI `"0.14"`, backend `software`, seq_features `0x7f1f`, which is what COMPATIBILITY.md:733-737 says it should.
- **Node only.** The loader imports `node:fs`/`node:module` (lib.mjs:32-38, 425-438).
- **Bulk work: use the raw layer.** `Context.map` packs each element through `from()` (core.mjs:2105-2115). MEASURED: that adds about 1.5-2 µs of JavaScript per element, against about 0.3 µs for a native fma. For bulk work, call the raw `cftw_*` layer on `Uint8Array` buffers.

### 2.3 For a browser

**The live pages.**
- `https://loganw234.github.io/cft-fp256/` is the conformance replayer plus a calculator for all four formats, five attributes and thirty-nine transcendentals (README.md:26-39; bindings/wasm/README.md:3-21, 82-95).
- `/demos.html` runs the five workloads.
- Both are deployed from the committed files by `.github/workflows/pages.yml:48-58`.
- MEASURED today: the served bytes equal HEAD's, sha256 `87294879…` and `5ce2fc2b…`, the hashes bindings/wasm/README.md:1003-1006 records. Last-Modified is 2026-09-25 07:22:48 GMT.
- They are checkers to link to, not libraries to import.

**Your own page.** The WASM bytes are the same whichever loader wraps them (build.sh:51-57; bindings/wasm/README.md:147-152). But the **web** loader is not committed.
- `cft_split.js` is built with `-sENVIRONMENT=web -sMODULARIZE=1 -sEXPORT_NAME=createCftModule`, only by `bash bindings/wasm/build.sh`, into the untracked `bindings/wasm/build/` (build.sh:207-229; bindings/wasm/.gitignore:1).
- It needs Docker. The image is pinned as `emscripten/emsdk:6.0.9@sha256:96617f27…` (build.sh:84-86, 104-107), and any other emcc is refused (build.sh:135-147).
- **It rewrites committed files:** `bindings/wasm/conformance.html` and `bindings/node/cft_node.*` (build.sh:233-241, 262-266). Run it only in your private clone.
- The owner's `bindings/wasm/build/` is stale: 2026-09-15 05:15, a 248,888-byte module from before `cftw_run_ex` reached it (bindings/wasm/README.md:956-966).

**Faster alternative (INFERRED).** Copy `bindings/node/{index,lib,core}.mjs`. Replace `loadModule` (lib.mjs:360-438) with a `fetch` of `cft_node.wasm` handed to a web-built `createCftModule` as `wasmBinary`, which is the same trick lib.mjs uses in Node (lib.mjs:425-438).

**Engine coverage.** Measured on V8 only (Node 22.19, Chromium 148). Other engines rest on the argument from the WASM integer specification (bindings/wasm/README.md:23-43, 704-708).

**The tile from a browser.** `cft-serve --ws PORT` exposes the U50 over WebSocket (REMOTE.md:524-531; `bindings/wasm/remote.mjs`).
- There is no authentication, and any web page can open a loopback WebSocket (REMOTE.md:616-640), so use it only through an SSH tunnel.
- `remote.mjs` does not send REDUCE_SEG (bindings/wasm/README.md:824-831).

### 2.4 The U50 from this desktop

- **Nothing FPGA runs on Windows** (CLAUDE.md:55).
- **Server.** Run `cft-serve [--port N] [--bind ADDR] [--artifact PATH]` on amd-arc-box (REMOTE.md:464-471; the host is `ssh logan@192.168.0.201`, CLAUDE.md:43). It listens on `127.0.0.1:7754` by default (REMOTE.md:468-470).
- **Client.** Tunnel with `ssh -N -L 7754:127.0.0.1:7754 …` (the pattern at REMOTE.md:629-630). Then use `Context(53, artifact="cft://127.0.0.1:7754")` in cftmpfr, or `cft_open("cft://…")` in C (cft.h:390-399).
- **What crosses the wire.** Only device calls. The transcendentals and conversions run in the client (cft.h:398-409).
- Which xclbin to serve is the owner's call (INFERRED; docs/CARDDAY.md is the runbook).

---

## 3. The determinism contract as it applies to fixer

### What is guaranteed

- **The promise.** "Same inputs, same op, same bits" on the tile, on the golden model and on any conforming implementation. No configuration, compiler, driver, tool version, placement seed or timing may change a result bit or a flag bit (DETERMINISM.md:13-18). Concretely, the software and tile backends give byte-identical buffers and identical flags (cft.h:24-32).
- **Scope: every contract operation.** That is the opcodes, div/sqrt, the clause-5 completion set, all 39 transcendentals, the augmented pairs, all reductions, the character conversions and formatOf (DETERMINISM.md:63-87; CONFORMANCE.md:77-112).
- **Pinned choices.**
  - Each rounding attribute is its own deterministic contract (DETERMINISM.md:127-131).
  - Tininess is detected after rounding; every NaN result is the canonical NaN; the sign of every exact zero is fixed (CONFORMANCE.md:114-127).
  - Subnormals are never flushed (DETERMINISM.md:1260-1265).
- **Reductions.** The tree is fixed, and any partitioning (tiles, threads, machines) returns the same bits, flags included (CONFORMANCE.md:128-145).
- **Programs.** A program runs bit for bit or is refused by name (CONFORMANCE.md:147-185). The deposit layout does not depend on the tile count (cft.h:2425-2427).
- **Clock-independent.** A slower conforming implementation is complete (CONFORMANCE.md:197-208).
- **Why it survives compilers and platforms.** The software backend computes on uint32 limbs with uint64 intermediates and has no C float/double in the result path (bindings/wasm/README.md:29-43; build.sh:70-76). MEASURED by grep: no `float` or `double` type appears in `host/src` outside comments.
- **Scoring.**
  - 1,068,915 cases in 168 sets, hashed in `vectors/SHA256SUMS`.
  - One FNV-1a checksum line per format that every language must reproduce (CONFORMANCE.md:210-245).

**Evidence by platform:**

| platform | what ran | source |
|---|---|---|
| Windows x86_64, mingw64 gcc 16.1 | `make -C host test` over all 1,068,915 cases, plus the runner's stages | COMPATIBILITY.md:775 |
| Linux x86_64 + U50 | the card; the published sets replayed on silicon | COMPATIBILITY.md:776; README.md:212-220 |
| macOS 26 arm64, Apple clang 21 | the library's gates locally, 1,071,635 cases in 388 s | COMPATIBILITY.md:777 |
| WebAssembly (emscripten, V8) | 1,903,270 cases over 316 set replays | COMPATIBILITY.md:778 |
| ESP32-S3 | 508,000 binary32/64 cases | COMPATIBILITY.md:782 |
| an independent GPU | the darkroom photograph, bit-identical to an RTX 5060 Ti record | DETERMINISM.md:29-41 |

### What is NOT guaranteed, or is explicitly outside the contract

1. **Timing and performance** (DETERMINISM.md:1405-1406).
2. **NaN payloads through arithmetic.** Every NaN result is the one canonical quiet NaN (DETERMINISM.md:1267-1279; CONFORMANCE.md:37). Payloads survive only abs/neg/copysign/select and the conversions (DETERMINISM.md:192-211).
3. **The device's sticky status word** is not part of the determinism contract (DETERMINISM.md:972-979). Each call's own `flags_out` is.
4. **Capacities differ by backend.** The software backend accepts 2^20 deposits per lane where the tile accepts 64, so "it ran on software" does not mean "it fits the tile" (SEQUENCER.md:603-613, 643-647; cft.h:477-503).
5. **Two different cards returning the same bits is not yet shown** (DETERMINISM.md:1411-1415).
6. **macOS:** the whole census over the network is not claimed; it stops early with an internal error (COMPATIBILITY.md:777).
7. **WASM engines other than V8 are not measured** (bindings/wasm/README.md:704-708).
8. **A transcendental may refuse** with `CFT_ERR_INTERNAL` (cft.h:1282-1288, 1794-1797). That is an error, not a different number, but a pipeline must handle it.
9. **The buffer-sync hazard.** Writing a `cft_alloc` mirror without calling `cft_buffer_to_device` gives different answers on a device than on software (cft.h:2165-2173).
10. **Unassigned opcodes** return the canonical NaN with invalid raised, not an error (cft.h:828-834; DETERMINISM.md:213-222).
11. **Versioning.** The bits are versioned by the conformance *profile* (Profile 1, 2026-09-16). The ABI (0.14) versions only the calling surface (CONFORMANCE.md:261-278). Pin both.
12. **Reserved rounding encodings 5-7** (DETERMINISM.md:114-116). The remote transport has no authentication or encryption (cft.h:436-439).
13. **Anything computed outside libcft** (INFERRED): numpy reductions, `Math.cos`, libm. Numpy is safe for data movement, integer arithmetic and comparisons. It is not safe for anything that rounds.

---

## 4. Throughput, and the two estimates

### 4.1 Already measured, software backend (docs)

**Provenance.** Intel Core i5-12400F (this desktop's CPU), Ubuntu 24.04 container, gcc 13.3 `-O2`, one core pinned. Operands are fast-path normals; rounding is RNE (BENCHMARKS.md:31-62, 624-630).

Nanoseconds per element. Each cell gives `cft-bench` (BENCHMARKS.md:224-231) / `cft-bench-peers` (BENCHMARKS.md:256-294):

| op | fp64 | fp128 | fp256 |
|---|---|---|---|
| add | 259.0 / 309.8 | 477.4 / 344.9 | 469.6 / 488.3 |
| mul | 197.4 / 206.1 | 240.6 / 243.5 | 355.3 / 332.5 |
| fma | 234.7 / 316.3 | 285.5 / 394.5 | 400.7 / 448.3 |
| div | 4,468.0 | 6,678.4 | 11,563.1 |
| sqrt | 5,638.2 | 8,018.5 | 12,704.3 |

- **Other machine.** On the card box's Xeon the software backend did an fp64 fma in 309 ns (3.24 M/s) and an fp128 fma in 396 ns (BENCHMARKS.md:76-83).
- **Against the alternatives.** Native `double` fma is 0.97 ns (BENCHMARKS.md:266-274), so libcft is about 300x the CPU. MPFR is 6-19x faster on add/mul/fma and 94-316x on div/sqrt (BENCHMARKS.md:331-335).
- **WASM** runs at 0.7-1.4x native on batched work (bindings/wasm/README.md:1088-1105).
- **Program executor, fp32 figures.**
  - An atlas-engine fp32 micro-test gave 0.98 ns per instruction per lane on the tile and 14.4 ns in software (1024 trips, BENCHMARKS.md:451-461).
  - A real fp32 program, `hopf`, took 88 s for 1,048,576 lanes of 1,081 instructions on one desktop core (BENCHMARKS.md:493-500), about 78 ns per static instruction (my arithmetic).
- **Transcendentals: no timing anywhere.** TRANSCENDENTALS.md:1589-1593 says so. `host/tools/cft_bench.c` and `docs/bench/*.csv` have no transcendental rows (grep).
- **The tile, for scale.** An fp64 fma staged runs at 76-89 M/s; resident, 413-416 M/s per tile (INTEGRATION.md:36-43, 217-222). The README is candid that at binary32/64 a CPU wins (README.md:22).

### 4.2 MEASURED spot checks, this session

**Setup.** The committed WASM module (sha256 `3737534d…`) in Node v22.19.0 on this desktop, with CPU load at 1% at the time. Software backend, RNE. Operands: 0.001-369 for cos/sin/exp/log, and dyadic k/32 for cospi/sinpi. The times include `Context.map`'s JavaScript packing. This is one run, not a benchmark.

| µs per element | fp64 | fp128 |
|---|---|---|
| fma (JS packing dominates) | 1.68 | 0.98 |
| cos | 381 | 1,109 |
| sin | 380 | 1,059 |
| cospi, dyadic argument | 388 | 878 |
| sinpi, dyadic argument | 377 | 926 |
| exp | 209 | 608 |
| log | 310 | 1,077 |
| atan2 | 350 | 1,074 |

- **Sanity check.** `cos(1)` at fp64 = `0x1.14a280fb5068cp-1`, the correctly rounded value.
- **Program executor at fp64.** `programs/out/spill-ref-fp64.cftp` is 40 mul + 39 fma per lane, read and run in memory. It took 19.5 µs per lane at n = 4,096 and 29.8 µs at n = 16,384. That is **247-377 ns per floating-point operation**, the same order as `cft_run`. So programs buy no software speed-up at fp64.
- **Native transcendentals (INFERRED).** Probably the same order of magnitude as the WASM figures. A plausible cause is the evaluator's fixed 2,048-bit bigint container, even at binary64 (TRANSCENDENTALS.md:305-323).

### 4.3 ESTIMATE A: one single-qubit gate on a 2^16-amplitude statevector

**Assumptions.**
- The real and imaginary parts are separate arrays: numpy float64 for fp64, `V16`/`V32` for fp128/fp256.
- The amplitude pairs (i0, i1 = i0 | 2^k) are arranged by exact numpy reindexing, which involves no rounding.
- The arithmetic is whole-array libcft calls, with the gate coefficients broadcast.
- A general U(2) gate is 4 outputs × (1 mul + 3 fma) = 4 mul + 12 fma per pair, over 2^15 = 32,768 pairs.

| gate | fp64 | fp128 | fp256 |
|---|---|---|---|
| general U(2) | **118-151 ms** | **144-187 ms** | 201-223 ms |
| real rotation Ry, or diagonal Rz/phase (8 ops per pair or 4 per amplitude) | 57-69 ms | 69-84 ms | 96-105 ms |
| X, CNOT, CZ, SWAP (permutation or sign flip, exact) | ~1-3 ms: numpy reindexing, or `CFT_NEG` | same | same |
| the gate's cos and sin, computed once | ~0.8 ms | ~2 ms | unmeasured |

- **The arithmetic.**
  - fp64: 32,768 × (4×197.4 + 12×234.7) ns = 118 ms, up to 32,768 × (4×206.1 + 12×316.3) ns = 151 ms.
  - fp128: 32,768 × (4×240.6 + 12×285.5) ns = 144 ms, up to 32,768 × (4×243.5 + 12×394.5) ns = 187 ms.
- **A circuit.** 16 qubits × 20 layers of general gates, with CZ entanglers, is about 38-48 s at fp64 and 46-60 s at fp128 on one core.
  - INFERRED: it splits across processes by pair-index range, one device each, for roughly 6x on the 6 P-cores.
- **Measurement.**
  - Probabilities |a|² over 2^16 amplitudes take about 28-34 ms at fp64.
  - A binary sum-tree for the CDF (65,535 adds) takes about 17-20 ms. INFERRED: its root equals `cft_reduce(CFT_SUM)` bit for bit, because the contract tree splits a power-of-two range at its midpoint (cft.h:876-883).
  - Each shot is `u = lowbias32(seed)·2^-32`, exact in binary64, compared down 16 levels: microseconds.
- **For scale (INFERRED).** numpy complex128 does such a gate in roughly 0.1-0.5 ms.

### 4.4 ESTIMATE B: one 64-site DPP sample

**The model.**
- A projection DPP: N = 32 fermions on a 64-site ring, plane-wave modes, complex numbers carried as real/imaginary arrays.
- A sequential chain-rule sampler with incremental Cholesky-style vectors: v_k(x) = [K(x,x_k) − Σ_{j<k} v_j(x)·conj(v_j(x_k))] / sqrt(p_k(x_k)), then p_{k+1}(x) = p_k(x) − |v_k(x)|².

**The counts.**
- About 135,000 mul/fma per sample: 126,976 fma for the vectors, plus 4,096 fma for the diagonal, plus 4,096 mul to normalise.
- 32 sqrt and 32 div.
- About 2,016 adds for the 32 CDFs over 64 sites.
- 32 hash draws with exact comparisons.

| | fp64 | fp128 | fp256 |
|---|---|---|---|
| kernel build, once per kernel: 64 `cospi` + 64 `sinpi` at k/32, plus 4,096 complex adds | ~50 ms | ~120 ms | unmeasured |
| ~135k mul/fma per sample | 27-43 ms | 33-53 ms | 45-61 ms |
| 32 sqrt + 32 div per sample | 0.3 ms | 0.5 ms | 0.8 ms |
| CDF adds per sample | ~0.6 ms | ~0.8 ms | ~1 ms |
| **per sample** | **~30-45 ms** | **~35-55 ms** | **~47-63 ms** |

The table leaves out ctypes call overhead: about 200-400 calls per sample, INFERRED to be at most a few ms. Samples are independent, so they run in parallel across processes.

**Design sensitivities (ESTIMATE).**
- **Building the kernel naively** from 4,096 distinct cos/sin pairs costs about 3 s at fp64 and 8 s at fp128. A ring has only 64 distinct phases.
- **A re-orthonormalising O(L·N³) sampler** costs about 20-40x more per sample.
- **A general L-ensemble** needs a 64×64 Hermitian eigendecomposition. Jacobi at about 20-30 M fma costs about 5-10 s at fp64, once per kernel, but only with algebraic rotation formulas (sqrt/div). Computing each rotation through atan2/cos/sin adds about 10-20 s.

---

## 5. Can a sequencer program run these per-lane kernels?

### The program model in brief

- **Structure.** A program is an image: header, constant bank, then 64-bit instructions. Lanes are independent (SEQUENCER.md:294-357, 388-413; cft.h:2270-2434).
- **Lane state.** Each lane owns 32 registers, 256 scratch slots and an active bit. `r0`-`r2` load from the three input streams; an optional per-run block fills scratch on the way in and reads it back on the way out. Constants are shared and read-only. The output is up to `max_deposits` deposits per lane plus a count.
- **The ALU** is the opcode set: fma/mul/add/sub, abs/neg/copysign/min/max, select, cmplt/cmple/cmpeq, the integer group including `imul`, and the recip/rsqrt seeds. The rounding attribute is chosen per instruction (PROGRAMS.md:85-116; SEQUENCER.md:551-555).
- **Control codes** (SEQUENCER.md:563-601):
  - `REPEAT`/`ENDREP`, with trip counts given as immediates and at most 4-deep nesting;
  - `DEPOSIT`;
  - `SETACT` narrows the active mask, which gives the early exit;
  - `ACTALL` and `HALT`;
  - `STL`/`LDL`/`STX`/`LDX` for scratch.
- **Per-run data.** A `BANK_EXT` constant bank lets one image serve every parameter set (cft.h:2436-2468; PROGRAMS.md:67). ABI 0.14 adds index tables and a lane mask (cft.h:2509-2533).
- **Tooling.** Text source is `.cfta`, assembled by `cft-asm` or `python/cft_golden/asm.py`. The runner is `positive-run` (PROGRAMS.md:33-60, 148-166, 248-283). Node has `loadProgram` (bindings/node/README.md:221-240). The definition is `python/cft_golden/seq.py` (cft.h:2280-2282).

### Kernel 1: a 2×2 complex rotation over amplitude pairs. Plausible.

**Sketch (INFERRED design, not assembled).**
- `.format fp64`, `.deposits 4`, and `.bank external` holding 8 constants: u00r, −u00i, u01r, −u01i, u10r, −u10i, u11r, −u11i.
- `.scratch in 1`.
- Streams a, b and c carry re[i0], im[i0] and re[i1]; the scratch preload carries im[i1]. Each is either gathered through its index table (cft.h:2509-2524) or pre-permuted on the host.
- The body is 1 mul + 3 fma per output component, 16 ALU instructions for the four components, plus `ldl`, 4 deposits and `halt`: about 22 instructions.
- The output is lane-major (cft.h:2425-2427) and there is no scatter (CAPABILITIES.md:268; INTEGRATION.md:199-204). So either re-permute on the host, or feed the next gate through its index tables.

**Cost.**
- **Software:** MEASURED about 250-380 ns per operation, so a gate costs about 130-200 ms. No better than plain `cft_run` calls.
- **Tile (INFERRED from measured unit costs):**
  - Instruction time is roughly 16 × 0.98 ns + about 6 control codes × about 4 ns, about 40 ns per lane (SEQUENCER.md:1553-1566).
  - On top of that is a fixed 0.07-0.18 µs per lane (HOSTAPI.md:494-502).
  - Densely laid out, a gate takes about 4-7 ms.
  - Gathering 4 elements per lane at 310-340 ns each (INTEGRATION.md:195-197; BENCHMARKS.md:421-425) makes it about 43 ms, so pre-permute densely for the tile.
- **Remote from Windows (INFERRED).** The client gathers the tables and sends dense frames (cft.h:771-776), so the network (about 2 MB per gate) sets the cost.

### Kernel 2: hash-to-uniform, then compare against a CDF. Plausible.

- **The hash already exists as a program.** `programs/lowbias32-fp32.cfta` is 8 integer instructions plus deposit and halt, with 4 constants; it needs IMUL. It is checked on 4,096 draws (programs/lowbias32-fp32.cfta:1-49; PROGRAMS.md:212). IMUL is the low 32 bits of a 32×32 product at *every* format, so it runs in fp64 lanes too (cft.h:286-305).
- **The uniform.** ATLAS.md:88-97 gives the fp32 recipe for `float(x)·2^-32` in nine instructions. INFERRED for fp64, where the conversion is exact: OR `x` under the encoding of 2^52, subtract 2^52, multiply by 2^-32. About 3 instructions, with no rounding.
- **The CDF comparison.**
  - `CMPLT` returns 1.0 or +0.0 (cft.h:212-222), so the bin index is Σ_k cmplt(cdf_k, u), 2 instructions per bin.
  - The CDF lives in the per-run bank, which holds at most 512 entries (SEQUENCER.md:603-613). A 64-bin CDF is about 130 instructions per lane.
  - Binary search cannot run against the bank, because constant indices are immediates (SEQUENCER.md:501-531).
  - It can run against scratch, where `LDX` takes a register index (SEQUENCER.md:573-577). But then every lane needs its own copy of the CDF; `idx_scratch_in` can fan one pool out to all of them (cft.h:2520-2524).
- **At binary64 none of this needs libcft to be deterministic (INFERRED).** 32-bit integer hashing, the exact int→float step and IEEE comparisons are exact everywhere, in numpy uint32 or JS `Math.imul` alike. libcft is needed for the CDF's sums, and for binary128/256.

### Capacity limits that matter

| limit | value | source |
|---|---|---|
| deposits per lane | **64 on the tile**; 2^20 in software | SEQUENCER.md:603-613, 643-647 |
| instructions per program | 16,384 | SEQUENCER.md:606-607 |
| constant bank | 512 entries, per run with BANK_EXT | SEQUENCER.md:517-525, 608 |
| registers | 32 per lane | SEQUENCER.md:334 |
| scratch | 256 slots per lane | SEQUENCER.md:608-609 |
| loops | immediate trip counts, 4-deep; worst case 2^40 instructions | SEQUENCER.md:600-601, 673-677 |
| no calls, no composed ops, no reductions inside a program | div/sqrt only by inlining a seed+Newton image (`divfull`, ~167 instructions) | BENCHMARKS.md:561-564; HOSTAPI.md:479-502 |
| no transcendentals inside a program | they are host operations | cft.h:1238-1245 |
| no cross-lane operations, no scatter | | BENCHMARKS.md:557-560; CAPABILITIES.md:268 |
| gather cost | one HBM round trip per element, 310-340 ns | INTEGRATION.md:195-197 |
| tile count | **one program runs on tile 0 only** (on main) | README.md:174; BENCHMARKS.md:434-437 |
| small runs | below the lane block (64 lanes at fp64) the pipe cannot fill | SEQUENCER.md:403-413, 454-459 |
| per-lane fixed cost | 0.07-0.18 µs; a control code costs ~4 ns against 0.98 ns for arithmetic on the tile | HOSTAPI.md:494-502; SEQUENCER.md:1553-1566 |

**Fit for DPP sampling (INFERRED).** A sequential DPP sampler is *not* a per-lane kernel: one sample's state (64 × 32 complex values) far exceeds 32 registers plus 256 slots. What does fit is a single step's update, with one lane per site and the chosen site's row in the bank. That is a correctness demonstration on the tile, not a speed-up.

**In flight, not on main.** The `ode-round` branch is 8 commits ahead as of 2026-09-25. It splits a program run's lanes across tiles in the XRT backend, still at ABI 0.14 (`git log ode-round`, 617b753).

---

## 6. Licence

**The facts.**
- Apache-2.0 throughout (LICENSE; README.md:433-437). All 233 SPDX tags under `host/`, `bindings/`, `python/` and `programs/` say Apache-2.0 (grep).
- Copyright "2026 Logan W." (cft.h:1-2; LICENSE:189; NOTICE:2).
- **NOTICE** (NOTICE:1-5) names the project and the copyright holder, and says the product includes software from the cft-fp256 project, with its URL.
- The library has no dependencies (cft.h:38-45; host/Makefile:4-6). The golden model needs mpmath (BSD) only for the transcendentals (README.md:435-437).

**What Apache-2.0 asks when you redistribute** (LICENSE:89-128):
- (a) give recipients a copy of the licence;
- (b) mark the files you modified;
- (c) keep the copyright and attribution notices in source;
- (d) reproduce the NOTICE attributions in a NOTICE file, in the documentation, or in a display.

Also: §3 grants a patent licence, which terminates if you sue (LICENSE:73-87). §6 grants no trademark rights beyond describing origin (LICENSE:138-141). CONFORMANCE.md:294-301 says an implementation may call itself "cft-fp256 conforming" only after passing the test.

**From MIT or Apache-2.0.** Both are fine. Under MIT, the libcft files stay Apache-2.0 and your code stays MIT (LICENSE:123-128 allows other terms for your own modifications). Say so in your README (INFERRED; the standard reading of a permissive combination).

| mode | what you distribute | what you owe |
|---|---|---|
| **vendor**: copy `host/include`, `host/src`, `bindings/python/cftmpfr`, `bindings/node` | libcft source | keep the SPDX headers; add a copy of LICENSE; put the NOTICE text in your NOTICE or THIRD_PARTY_NOTICES; mark changed files |
| **submodule** pinned at 7d7285d | a pointer only; the upstream carries LICENSE and NOTICE | nothing more for the source tree, until you ship binaries |
| **link**: ship `cft.dll` or `libcft.so`, or `cft_node.wasm` inside a web page | the Work in object form | LICENSE plus the NOTICE text alongside; for the web, a licences page or a header in the bundle |

- **The WASM glue.** The loader JavaScript is emscripten output. INFERRED: emscripten is MIT / University of Illinois-NCSA; check before shipping.
- **Recommendation.** A submodule at 7d7285d; a THIRD_PARTY_NOTICES file carrying the NOTICE text and naming Apache-2.0; and a licences page in the web deliverable.
- INFERRED: the copyright holder can grant other terms outright, if that matters for the team.

---

## 7. The minimal, lowest-risk integration path for one week

1. **Pin.** Once moth-quantum is a git repo, `git submodule add https://github.com/loganw234/cft-fp256 vendor/cft-fp256` and check out 7d7285d. Never build in the owner's checkout.
2. **Build once.** Build `cft.dll` with the owner's full invocation (§2.1). Check the exports and ABI 14, and run the package's pytest.
3. **Choose the carrier.** Use numpy float64 arrays at binary64.
   - Route every operation that rounds (add, mul, fma, div, sqrt, the transcendentals, sums) through `cftmpfr.batch`.
   - Use numpy only for data movement, uint32 hashing, comparisons, and SHA-256 over raw bytes. `hashlib` computes the same SHA-256 as `cft_sha256` (INFERRED).
   - The precision demo: widen with `Context(113)` / `Context(237)`, which is exact (cft.h:1102-1106). Run the same seeds and diff the layouts.
4. **Write a ctypes shim** of about 40 lines, with argtypes on every prototype (`_lib.py:181-185`). It needs `cft_reduce_seg` for matrix-vector products, `cft_sha256` for film digests, `cft_convert`, and optionally `cft_run_ex`.
5. **Days 2-4.** Build the statevector and the DPP in Python. Cache every distinct angle's cos and sin. Use `cospi`/`sinpi` on dyadic arguments, and algebraic formulas in any eigensolver.
6. **Days 4-5: the browser.**
   - Ship the films with their digests.
   - Recompute a small patch in the browser with the WASM module. The web loader comes from `build.sh` in your clone, or from the fetch-based adaptation of `bindings/node`.
   - Link the live conformance page as independent evidence.
7. **Optional.**
   - Run the elementwise parts on the U50 through `cft-serve` and an SSH tunnel, and compare digests.
   - Cross-check a few thousand operations against `python/cft_golden`.

**The two things most likely to cost hours:**

1. **The Windows DLL build traps.** In order of appearance:
   - the i686 `cc` comes first on PATH;
   - make never sees `OS=Windows_NT`, and the DLL exports nothing;
   - `TMP`/`TEMP` must be make variables;
   - stale ELF or i686 objects are taken as up to date.

   Every symptom reads as a source bug or a broken compiler (mem-build:18-55, 86-91; mem-tools:11-24; Makefile:29-39). The defence: copy the full command verbatim, redirect output to a file (CLAUDE.md:112-114), and check the exports with `objdump -p` before blaming Python.
2. **Transcendental cost.** About 0.4 ms per element at fp64 and about 1 ms at fp128 (MEASURED in WASM; native INFERRED similar). Any transcendental per sample, per site pair or per Jacobi rotation turns seconds into tens of minutes. That rules out Box-Muller and log-based samplers in an inner loop.

A close third: the browser needs a web loader that only a Docker build produces, and that build rewrites committed files.

---

## Anything surprising

1. **Transcendentals are about 1000x an fma.**
   - MEASURED in the shipped WASM: about 380 µs per element at fp64 and about 1.1 ms at fp128 for cos.
   - Nothing in the repo times them (TRANSCENDENTALS.md:1589-1593).
   - INFERRED cause: the fixed 2,048-bit container (TRANSCENDENTALS.md:320-323).
2. **The transcendentals never touch the tile.** They are host operations on every backend (cft.h:1238-1245, 398-409). A "same bits on the U50" demonstration therefore proves the arithmetic, reductions and programs, and not the trigonometry.
3. **Programs buy no software speed at fp64.** The executor costs about 250-380 ns per operation (MEASURED), the same as `cft_run`. The 14.4 ns per instruction in BENCHMARKS.md:451-461 comes from an fp32 micro-test whose operands are not stated.
4. **COMPATIBILITY.md:45 overstates cftmpfr.** It says the package carries "every clause-5 … operation". It has no `cft_rint`, `cft_convert`, `cft_scaleb`, `cft_cvt_*` or `cft_rem`, and none of the newer calls (`run_ex`, `reduce_seg`, programs, buffers, `sha256`).
5. **Browser determinism beyond V8 is argued, not measured** (bindings/wasm/README.md:704-708). Opening the live page in Firefox and Safari and reading its verdict line is a free hackathon contribution.
6. **`CFT_DOT` rounds every product** (cft.h:247), so a dot product accumulated with fma gives different bits. Pick one form and pin it.
7. **The IMUL proof is open.** IMUL is the opcode the hash relies on, and its formal proof does not close. Its evidence is simulation benches and a differential test (ATLAS.md:115-121).
8. **Stale artifacts in the owner's checkout.** The WASM build directory there (2026-09-15) is older than the committed module (2026-09-24), and the prebuilt `host/cft.dll` (2026-09-18) predates `8a8f492`.
9. **The live GitHub Pages site is byte-identical to HEAD** (MEASURED). The published page is exactly what the repository says it is.
10. **The checkout is shared right now.** During the survey, another session created `trunc.c`/`trunc.exe` in the owner's checkout, and multi-tile program runs are in flight on `ode-round`. Pin a SHA; don't track `main` during hackathon week.

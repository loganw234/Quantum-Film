# Working on Quantum-Film

Short, and only things that are non-obvious AND have already cost time. The
README says what this project is; this file says what will bite you.

## Start here: one command answers "does it still hold?"

```
make verify-quick          # ~30 s: lint, docs, vectors, golden, circuits, decode, client, fixer, the control and its twin
make verify                # adds cft and the live Atlas smoke; each skips BY NAME when it cannot run
bash verify/run.sh --list  # every stage, with * on what a budget selects
```

`verify/run.sh` is the runner. **Reach for it before hand-running tests.**
`make test` runs pytest alone and is not a verdict. A pytest stage runs a
directory: a new test joins its stage by where it is saved (tests/<stage>/),
and tests/docs/test_registry.py fails a test file no stage runs.

- **A test that skips inside a stage FAILS the stage** (verify/pytest-stage.sh).
  A skip happens only at stage level, by name: `need_file` / `need_env` in
  verify/run.sh, where `--require-all` can see it.
- **There is no cache across runs.** A run id is timestamp + pid + commit
  (+dirty). `--resume` refuses to cross commits, a dirty tree, or a changed
  environment (QF_CFT_ROOT's DLL and binding, python and its packages, ruff
  and pytest, whether an Atlas key is set). `--only ""` is refused, and a run
  whose every stage skipped FAILS: a skip is not a run.
- **A device roll's commitment is bound by its anchor, not by its value.**
  The salt is in the record, so a changed field can be re-sealed with its
  commitment recomputed. What binds is the commitment committed to git before
  the job's first status call, which already carries the result.
- `make vectors` regenerates tests/vectors after a deliberate change; never
  hand-edit a vector. A record on disk is exactly `fixer.text(record)`, and
  the fixer's command line refuses any other bytes.

## The authority

`quantum_film/golden` **is the definition of correct.** It is pure Python plus
mpmath at 256 bits, with SHA-256 counter-based uniforms, and it imports
nothing but the stdlib, mpmath and the stock table
(tests/golden/test_independence.py). The circuits, the float paths and Atlas's
results are held to it, never to each other. A draw that rounding could
decide is refused (`TieRefusal`). Every stock parameter lives only in
`quantum_film/stocks.py`.

- **mpmath's working precision is process-global.** Never call the authority
  from threads. It refuses (`PrecisionChanged`) a draw whose precision moved,
  and a basis whose rows' squared norms miss N/M, before it is cached: a
  brief drop in another thread can come and go between two checks.
- **Measure the authority against code it does not share, on a tile whose
  arithmetic is not accidentally exact.** The first premise gate compared it
  with itself, and passed a binary64 `math.fsum` 2^-51.5 off. On the shelf's
  tiles (L = 4, 16) several binary64 slips round to the exact value and show
  nowhere. The references are exact Fractions on L = 4 and L = 6 (Niven: the
  only L with rational cosines besides 1-3) and an independent 512-bit chain
  rule on 16x16. The source rule (no binary64 in golden) reads spellings only.

## Atlas (Moth's platform): what bites

1. **`Error 1010: browser_signature_banned` from Cloudflare** means Python's
   default urllib user agent was used. The client drives System32's
   `curl.exe`, the client Moth's own docs use. Do not disguise a user agent to
   get past a block; that is evading bot detection.
2. **`curl: (43) A libcurl function was given a bad argument`, even without a
   key.** That is Git for Windows' bundled curl 8.8.0. Use
   `C:\Windows\System32\curl.exe`.
3. **An API path turns into `C:/Program Files/Git/api/v1/...`.** MSYS path
   conversion rewrote a slash-leading argument in Git Bash. Set
   `MSYS_NO_PATHCONV=1`. It also stops git.exe reading `-C /c/...`, so the
   runner runs git from inside the tree.
4. **The key never enters the tree.** `QF_ATLAS_AUTH` names a header file
   outside the repository. The client refuses a path inside it, and any
   scheme and host but `https://api.mothquantum.com` (tests/client/). Results
   carry presigned S3 URLs, which are bearer credentials for 15 minutes: never
   print them, and scrub them before anything reaches docs/records/.
5. **tomography-api-v2's count strings change qubit order from setting to
   setting** within one response, and nothing says so. Read them only through
   `quantum_film.atlas.decode`, which has been held to a known-answer run. The
   first reading of 2026-09-25 used plain order and reported 11-sigma
   "disagreements" that were the reader's, not the physics'.
6. **A seed on Atlas fixes the circuit, not the shots.** qdrive with `seed: 7`
   fitted two different circuits. Nothing that samples on Atlas repeats; record
   it, don't re-run it.
7. **The account has `features: []`**: no QPU, no engine publishing
   (2026-09-25).
8. **Know which circuit ran.** The tile Atlas ran on 2026-09-25 was
   research/2026-09-25/emulsions/fermion_tile.py, an open box's standing waves
   in snake order, not the shelf's Pauli law. Five documents said otherwise
   until the P0 verifier checked the QASM hashes. A score is against one
   law; name the circuit's SHA-256 beside it.

## Controls that cannot fail (every one happened, 2026-09-25/26)

- **The same film is never a sabotage.** Negating every rotation angle is a
  gauge (K -> SKS), and so is reversing the qubit line, q -> 15 - q, on the
  4x4 tile (verifier-P3). tests/circuits/test_givens.py pins the first.
- **On a mirror-symmetric tile, occupation statistics cannot tell two bit
  orders apart.** Decide an order with a known-answer circuit, not with the
  physics you are trying to measure.
- **Random seeds never test a margin**, and a plant on one side of a
  boundary tests one side. A margin checked after the choice passed every
  gate until the mirror plant, 2^-240 below (tests/golden/test_golden_fermi.py).
- **A control named by a number can miss.** "Plant 1e-14 from a boundary"
  (P1's brief) is where binary64 is still right; plant inside its own error.

## cft-fp256 (the pinned-arithmetic path)

- **Build only in `vendor/cft-fp256`** (the submodule at 7d7285d), never in
  `../cft-fp256`: that checkout is shared with other sessions. Building only
  `cft.dll` (not `all`) took 8 s with 0 warnings on 2026-09-25. A git
  worktree has the submodule uninitialised: point `QF_CFT_ROOT` at a built
  one, and the `cft` stage checks that DLL (it prints its path and SHA-256).
- **The build** is the owner's tested invocation, from Git Bash:
  `PATH="/c/msys64/mingw64/bin:$PATH" make -C vendor/cft-fp256/host CC=gcc OS=Windows_NT TMP='C:/Users/logan/AppData/Local/Temp' TEMP='C:/Users/logan/AppData/Local/Temp' cft.dll > build.log 2>&1`.
  - The i686 `cc` first on PATH, a missing `OS=Windows_NT` (the DLL then
    exports nothing) and stale ELF objects each read as a source bug. Check
    `objdump -p .../cft.dll | grep -c ' cft_'` (about 120) before blaming
    Python.
  - Never pipe a long make through `| grep | head`: it hangs at 0% CPU.
  - Two builds of the same source differ in exactly three fields: the COFF
    and export-directory TimeDateStamps and the PE CheckSum (the P0
    verifier). A hash with those zeroed would pin a build; today a DLL is
    identified by its path and full hash in the log.
- **libcft's transcendentals cost about 1,000x an fma**: natively, at
  binary64 through cftmpfr, cos 0.24 ms and exp 0.12 ms per element (measured
  2026-09-25; the first figure, 0.4 ms, was WASM). Build tables of cos, sin
  and exp once per stock, never per pixel or per draw.

## Housekeeping that has bitten

- **An import runs nothing but pure construction, or is refused**
  (tests/docs/test_atlas_guards.py). An import re-ran nine probe jobs on
  2026-09-25. Every module under research/, tools/ and quantum_film/ either
  starts with `if __name__ != "__main__": raise ImportError(...)` or calls
  only an allowlist at import (Path, re.compile, lru_cache, sys.path.insert,
  a few builtins, its own pure helpers). Two versions that named Atlas
  spellings instead were each walked past by the verifier.
- **Never compare two spellings of a path.** Git Bash mounts %TEMP% at /tmp,
  and a check that did refused every verifier's clone; the runner asks git
  `--show-cdup`.
- **The session scratchpad is shared by every agent**, and it holds the Atlas
  key. Brief every agent to write only under a subdirectory named for it:
  P1 overwrote a lead file at its root on 2026-09-25.
- **Third-party pytest plugins are switched off** in the gates
  (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`). zarr's plugin imports CuPy and
  prints a CUDA warning into every log on this desktop.
- **A path named in plain text is checked** (tools/check_docs.py, rule 3).
  Moving the tests into stage directories left seven names pointing at
  nothing.

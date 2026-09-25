# Working on Quantum-Film

Short, and only things that are non-obvious AND have already cost time. The
README says what this project is; this file says what will bite you.

## Start here: one command answers "does it still hold?"

```
make verify-quick          # ~20 s: lint, docs, vectors, golden, circuits, decode, fixer, the negative control
make verify                # adds cft and the live Atlas smoke; each skips BY NAME when it cannot run
bash verify/run.sh --list  # every stage, with * on what a budget selects
```

`verify/run.sh` is the runner. **Reach for it before hand-running tests.**
`make test` runs pytest alone and is not a verdict. A pytest stage runs a
directory: a new test joins its stage by where it is saved (tests/<stage>/),
and tests/docs/test_registry.py fails a test file no stage runs.

**There is no cache across runs.** A run id is timestamp + commit (+dirty),
and `--resume` refuses to cross trees. `make vectors` regenerates
tests/vectors after a deliberate change; never hand-edit a vector.

## The authority

`quantum_film/golden` **is the definition of correct.** It is pure Python plus
mpmath at 256 bits, with SHA-256 counter-based uniforms, and it imports
nothing but the stdlib, mpmath and the stock table
(tests/test_independence.py). The circuits, the float paths and Atlas's
results are held to it, never to each other. A draw that rounding could
decide is refused (`TieRefusal`). Every stock parameter lives only in
`quantum_film/stocks.py`.

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
   `MSYS_NO_PATHCONV=1`.
4. **The key never enters the tree.** `QF_ATLAS_AUTH` names a header file
   outside the repository, and the client refuses a path inside it and any
   host but `api.mothquantum.com`. Results carry presigned S3 URLs, which are
   bearer credentials for 15 minutes: never print them, and scrub them before
   anything reaches docs/records/.
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

## Controls that cannot fail (both happened on 2026-09-25)

- **Negating every rotation angle of the Pauli circuit is a gauge
  transformation** (K -> SKS). Every occupation probability is unchanged, so
  it is the same film, and it can never be a sabotage. tests/test_givens.py
  pins this.
- **On a mirror-symmetric tile, occupation statistics cannot tell two bit
  orders apart.** Decide an order with a known-answer circuit, not with the
  physics you are trying to measure.

## cft-fp256 (the pinned-arithmetic path)

- **Build only in `vendor/cft-fp256`** (the submodule at 7d7285d), never in
  `../cft-fp256`: that checkout is shared with other sessions. Building only
  `cft.dll` (not `all`) took 8 s with 0 warnings on 2026-09-25. A git
  worktree has the submodule uninitialised: point `QF_CFT_ROOT` at a built one.
- **The build** is the owner's tested invocation, from Git Bash:
  `PATH="/c/msys64/mingw64/bin:$PATH" make -C vendor/cft-fp256/host CC=gcc OS=Windows_NT TMP='C:/Users/logan/AppData/Local/Temp' TEMP='C:/Users/logan/AppData/Local/Temp' all > build.log 2>&1`.
  - The i686 `cc` first on PATH, a missing `OS=Windows_NT` (the DLL then
    exports nothing) and stale ELF objects each read as a source bug. Check
    `objdump -p .../cft.dll | grep -c ' cft_'` (about 120) before blaming
    Python.
  - Never pipe a long make through `| grep | head`: it hangs at 0% CPU.
- **libcft's transcendentals cost about 1,000x an fma** (0.4 ms at binary64,
  measured 2026-09-25). Build tables of cos, sin and exp once per stock, never
  per pixel or per draw.

## Housekeeping that has bitten

- **Every script that talks to Atlas has a `__main__` guard.** An import
  without one re-ran nine probe jobs on 2026-09-25.
- **Third-party pytest plugins are switched off** in the gates
  (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`). zarr's plugin imports CuPy and
  prints a CUDA warning into every log on this desktop.

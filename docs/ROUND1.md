# Round 1: the pinned path, atlas-film on pinned arithmetic, circuits for hardware

A ParcelRound round (github.com/loganw234/ParcelRound, METHOD.md). The lead
is the session that built P0. There are three parcels, each an Opus 5.5 agent
with a brief, a named negative control and a verifier of its own. Before any
parcel was dispatched, a verifier checked P0 itself, at the owner's
instruction (2026-09-25).

## What P0 settled

These are lead-owned. Parcels read them and never edit them.

- **Code:**
  - `quantum_film/stocks.py`, the shelf;
  - `quantum_film/golden/`, the authority;
  - `quantum_film/fixer.py`, the record format, device rolls and their
    commitment included;
  - `quantum_film/atlas/client.py` and `decode.py`;
  - `tools/make_vectors.py` and `tests/vectors/`.
- **Front door and packaging:** `verify/run.sh`, apart from the one-line
  additions a parcel's section names; `pyproject.toml`.
- **The claims files:** `README.md`, `CLAUDE.md`, `THIRD_PARTY_NOTICES.md`,
  `docs/`. A parcel that finds one stale reports it and does not edit it.
- **The built libcft:** `vendor/cft-fp256/host/cft.dll` in the lead's
  checkout (`C:\Users\logan\source\repos\moth-quantum`), from the submodule at
  7d7285d; the `cft` stage is green. A parcel's worktree has the submodule
  UNINITIALISED. **Do not build libcft; use the lead's copy** by setting
  `QF_CFT_ROOT=C:/Users/logan/source/repos/moth-quantum/vendor/cft-fp256`.
  The lead does not rebuild it during the round.
- **Tests run by directory.** A new test file joins its stage by where it is
  saved; tests/docs/test_registry.py fails any test file that no stage runs.

## The ledger

`C:\Users\logan\source\repos\quantum-film-ledger\round1\`. It is outside every
worktree and every repository. It has one file per author, append only, and an
`urgent/` directory that every agent watches. Its README is ParcelRound's
ledger template.

## P1: the pinned path (Quantum-Film)

- **Owns:**
  - `quantum_film/pinned/` (new) and `tests/pinned/` (new);
  - in `verify/run.sh`, exactly: one new `stage pinned` line pair, and
    `pinned` added to `BUDGET_QUICK`.
- **The job:**
  - a ctypes shim over the lead's libcft (at least `cft_reduce_seg` and
    `cft_sha256`), located through `QF_CFT_ROOT`, defaulting to
    `<repo>/vendor/cft-fp256`;
  - a binary64 Pauli sampler on libcft that EQUALS the authority on every
    roll by construction: a draw whose target lies within a stated,
    justified error bound of a boundary is handed to the authority for
    that draw;
  - measure the hand-off rate;
  - a precision demonstration at binary32, 64 and 128: which rolls part
    from the authority, and at which draw;
  - timings.
- **Negative control:** the same sampler with the hand-off removed, run on a
  planted near-tie stream, must disagree with the authority, and the
  version with the hand-off must agree on the same stream.
- **Forbidden:** everything P0 settled; `quantum_film/circuits/` and every
  file P3 owns.

## P2: atlas-film on the pinned primitive set (the atlas-film repository)

- **Where:** a fresh clone at `C:\Users\logan\source\repos\atlas-film-round1`,
  branch `pinned` from atlas-film's origin/main at `be1d674`. It is NOT the
  owner's checkout, which carries the owner's uncommitted work.
- **The job:** a deterministic mode for atlas-film. Its outputs must be the
  same bits on every IEEE-754 machine, with cft-fp256 as its authority. That
  means:
  - it is built only from correctly rounded binary64 `+ - * /` and `sqrt`,
    and exact comparisons;
  - no libm, no BLAS, no FFT library, and fixed-order reductions;
  - coating uses counter-based uniforms, not numpy's Generator
    distributions, whose streams numpy does not promise to keep stable
    (NEP 19);
  - the black-and-white negative and print chains run in that mode;
  - an organ not yet pinned is refused by name in that mode;
  - the default numpy path stays bit-identical.
  - The owner's direction (2026-09-25): atlas-film was always meant to move
    onto cft-fp256, and its survey findings are symptoms of that step not
    being taken yet.
- **Negative controls:**
  1. one det primitive swapped for numpy's libm call must fail the libcft
     bit-identity check;
  2. the default path's outputs, hashed at `be1d674` and after, must be
     identical, and a deliberate one-ulp change to the default path must
     show up in that comparison.
- **Forbidden:**
  - atlas-film's README.md, PLAN.md and PROVENANCE.md, the owner's claims
    files: report staleness instead;
  - the owner's checkout at `C:\Users\logan\source\repos\atlas-film`;
  - everything in Quantum-Film.

## P3: circuits for hardware (Quantum-Film)

- **Owns:**
  - new modules under `quantum_film/circuits/` (not `givens.py`, the
    reference the kernel check holds; it has not run on Atlas) and under
    `quantum_film/atlas/` (not `client.py` or `decode.py`);
  - new files under `tests/circuits/`;
  - a new script under `tools/`;
  - records under `docs/records/<date it runs>/p3/` (new).
- **The job:**
  - the (M - N) * N Givens layout with 2-CNOT rotations for the Pauli
    tile, held to the same kernel check and the same kinds of sabotage;
  - its QASM run through tomography-api-v2 and read with
    `quantum_film.atlas.decode`: **the first run of the shelf's Pauli law on
    Atlas**, scored against the golden kernel;
  - device rolls fixed with `fixer.fix_device`, each commitment committed
    to the branch BEFORE the job's result is fetched.
- **Negative controls:** the optimised circuit with one rotation dropped fails
  the kernel check; a device roll whose `job_id` is altered fails its
  commitment.
- **Forbidden:** everything P0 settled, `givens.py`, and every file P1
  owns.

## Merges and pushes

- **Merges.** The lead merges each Quantum-Film parcel after its verifier,
  one at a time, running the full suite after each merge and reading the
  log. P1 and P3 share no file, so the order is set only by who finishes
  first.
- **Pushes.**
  - Quantum-Film's main is pushed by the lead after each verified merge.
  - atlas-film's `pinned` branch reaches its origin only with the owner's
    word: it is another repository.

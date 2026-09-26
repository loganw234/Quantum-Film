# Roadmap

The order of work from the skeleton (2026-09-25) to the submission. Moth
Hack's virtual window runs 26 Sept to 2 Oct. The work is split as a
ParcelRound round: the lead keeps the seams (the shelf, the authority, the
record format, the docs), and each parcel below is one agent with a brief, a
named negative control, and a verifier.

## The parcels

**P1: cft, the pinned path.** (Merged, round 1; docs/VALIDATION.md.)
- (Done in P0: libcft is built in the pinned submodule, and the `cft` stage
  is green.)
- Done: a ctypes shim over libcft, `quantum_film/pinned/cft.py`: its
  elementwise operations under any rounding attribute, `cft_reduce_seg`,
  `cft_sha256` and `cft_convert`, which cftmpfr does not bind.
- Done: a binary64 Pauli sampler on libcft that certifies each draw against
  the exact chain rule, or hands the whole roll to the authority. It equals
  the authority by construction. The hand-off rate is 0 of 3,040 random
  rolls.
- Done: a precision demonstration at binary32, 64 and 128. On the shelf no
  random roll parts; a target planted inside a format's own error parts it,
  and the cascade from one parted draw is measured.
- Negative control: a sampler with the hand-off removed disagrees with the
  authority on a near-tie planted inside binary64's own error.

**P2: atlas-film on pinned arithmetic.** The owner's direction (2026-09-25):
atlas-film was always meant to move onto cft-fp256, and the gaps its survey
found are that step not yet taken.
- A deterministic mode in atlas-film, built only from correctly rounded
  primitives, coated with counter-based uniforms, with cft-fp256 as its
  authority. It runs in atlas-film's own repository; docs/ROUND1.md has
  the scope and the controls.
- Quantum-Film's side of development waits for it, in round 2: turning a
  layout into atlas-film's `(K, thr)` sheet, the honesty floor and mean-K
  check, the first prints, and the film-science statistics.

**P3: circuits for hardware.** (Merged, round 1; docs/VALIDATION.md.)
- Done: the (M - N) * N Givens layout with 2-CNOT rotations,
  `quantum_film/circuits/givens_line.py`. It lays 51 rotations and 102 CNOTs
  for `pauli-4x4`, since four of its 55 places are structural zeros, against
  59 rotations and 236 CNOTs in `givens.py`.
- Done: the first run of the shelf's Pauli law on Atlas, job 8586f1cc. The
  2026-09-25 tile before it was a research prototype with another law.
- Tile batches through Atlas, read through `decode`, fixed as device rolls
  with `fixed_at` and a commitment made before the results are read.
- Negative control: the optimised circuit with one rotation dropped fails
  against the kernel.

**P4: speckle.** The authority (exact probabilities from the statevector at
256 bits), the circuit, the Atlas run, and admission to the shelf.

**P5: the web page.**
- Re-develop a print from a record in the browser, through libcft's WASM
  build, and show the digest match.
- It would also serve challenge #8 if it calls the Atlas API.

**P6: the notebook and the gallery.**
- Challenge #10's notebook walks one roll from Atlas to a fixed record to a
  print.
- A gallery of prints, each captioned with its record's digest.

**P7: hardware.**
- The Pauli tile and the speckle stock on IBM's free Open Plan: 10 QPU
  minutes per 28 days, where 20 circuits x 4,000 shots is about 30 s.
- It needs an account the owner creates.
- What noise does to the grain (particle-number leak, the low-k floor,
  speckle contrast = fidelity) is the measurement.

## After the week

- **Colour:** the Pauli tripack (docs/STOCKS.md), through atlas-film's colour
  chain. That needs its `sheets=` parameter, a small upstream change.
- **The rest of the unique-stock programme:** Pauli-streak, quantum light,
  Rydberg voids.

## Standing items

- The ask to Moth for `publish_engines`, and the count-order finding (docs/ATLAS.md).
- A second machine running `make verify-quick`: the cross-machine evidence
  docs/DETERMINISM.md is still missing.

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

**P2: atlas-film on pinned arithmetic.** (Pushed, round 1: atlas-film's
`pinned` branch at d4007b2, not merged into its main.) The owner's direction
(2026-09-25): atlas-film was always meant to move onto cft-fp256, and the
gaps its survey found are that step not yet taken.
- Done: a deterministic mode in atlas-film, built only from correctly
  rounded primitives, coated with counter-based uniforms, with cft-fp256 as
  its authority. docs/ROUND1.md has the scope and the controls.
- Its gates, and what no gate sees, are in atlas-film's docs/PINNED.md.
- Done (2026-09-26): Quantum-Film's side of development.
  - quantum_film/develop.py turns rolls into atlas-film's `(K, thr)` sheet,
    at the borrowed stock's own density by construction, with the honesty
    floor refused by name.
  - The first prints are in docs/prints/, one of them laid entirely by Atlas.
- Still to come:
  - the film-science statistics on prints (Selwyn, g(r)) between the tile's
    scale and the stock's correlation length;
  - a faster certified sampler, since a square millimetre of TRI-X holds
    about 5.8 million crystals, or 230,000 pauli rolls;
  - colour.

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

**P6: the notebook and the gallery.** (The gallery is done: docs/prints/ and
the web demo. The entry is for challenge #9 alone.)
- A notebook walking one roll from Atlas to a fixed record to a print.
- A gallery of prints, each captioned with its record's digest.

**P7: hardware.**
- The Pauli tile and the speckle stock on IBM's free Open Plan: 10 QPU
  minutes per 28 days, where 20 circuits x 4,000 shots is about 30 s.
- It needs an account the owner creates.
- What noise does to the grain (particle-number leak, the low-k floor,
  speckle contrast = fidelity) is the measurement.

## Carried from round 1

What round 1's verifiers left open, each stated where it lives:
- **Device rolls.**
  - A commitment v3 that binds `kind`.
  - Anchor evidence beyond the local clock: push the commitment before the
    first status call, or put its hash in the job request.
  - A bundle format: one job made 1,995 files.
  - A test that holds `--score`'s exit code.
  - An upper bound on `fixed_at`.
- **libcft's DLL** pinned by a hash with its PE timestamps and checksum
  zeroed, not by its path and full hash.
- **The pinned sampler** (quantum_film/pinned/certificate.py's stated limit).
  N3m is a decision fault that fires only where the Gram bound is below
  2^-40, and it passes every gate. A laddered family with a smaller bound
  would narrow it.
- **atlas-film's pinned mode** (its docs/PINNED.md):
  - a tripwire at chain entry for code the interpreter runs inside a chain
    (sys.gettrace and the rest);
  - operand types in the integer and primitive layers (INT1, CAST1b).

## Carried from round 2

What round 2 left open, each stated where it lives:
- **Figures only the verifier's scripts reproduce.** Four figures the docs
  quote were computed by verifier-P0's own scripts, and nothing in the tree
  reproduces them:
  - the laws' expected S(k) on a sheet (README: 0.30-0.64 for Pauli, and
    about 0.4 of the twin's below the tile scale);
  - the bunched-tiling control (docs/STOCKS.md: 1.6 to 11.7);
  - the density identity at every allowed layer count up to 1,000
    (docs/DETERMINISM.md: within 2 x 2^-52).

  P4 needs the first two, because Speckle's twin must be measured, not
  assumed (docs/STOCKS.md). The scripts are archived with round 2's
  ledger, as ParcelRound's `archive/round4-second-ledger.zip`.
- **The prints' re-development.** `tools/first_prints.py --check`
  re-develops all five prints, and no stage runs it. Only the Atlas print's
  sheet is a gate (tests/develop). A slow stage in `make verify` would hold
  the other four.
- **The notices.** Nothing holds THIRD_PARTY_NOTICES.md against .gitmodules,
  pyproject.toml and the site's import map. Before the submission one entry
  was stale and three were missing (339e2ca).
- **The demo, the poster and the paper.** No verifier read them, beyond the
  S(k) captions verifier-P0's D1 reached. tests/docs/test_site.py holds the
  demo's data to the records, and the paper's build holds the numbers it
  lists (docs/VALIDATION.md, 2026-09-26 and 2026-10-05). Nothing holds the
  rest of their prose.

## After the week

- **Colour:** the Pauli tripack (docs/STOCKS.md), through atlas-film's colour
  chain. That needs its `sheets=` parameter, a small upstream change.
- **The rest of the unique-stock programme:** Pauli-streak, quantum light,
  Rydberg voids.

## Standing items

- The ask to Moth for `publish_engines`, and the count-order finding (docs/ATLAS.md).
- A second machine running `make verify-quick`: the cross-machine evidence
  docs/DETERMINISM.md is still missing.

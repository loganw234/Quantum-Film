# Quantum-Film

**Film stocks whose crystals are laid by quantum circuits, and a fixer that
makes every print of a roll the same, bit for bit, on every machine.**

A roll of film is chance made permanent. Silver-halide crystals land where they
land, and the fixer bath locks the image in. This project makes both halves
literal:

- a quantum measurement lays the crystals, under the Born rule, which no
  machine can repeat;
- the fixer writes the roll down as integers with its provenance;
- everything after that is arithmetic that gets the same answer everywhere.

The stocks are meant to behave in ways real film never has, while staying
physically plausible. Each stock's crystal layout is the measurement
statistics of a quantum state a circuit can prepare, and its tone curve and
grain scale are borrowed from a real stock in
[atlas-film](https://github.com/loganw234/atlas-film), so only the placement
of the crystals is new.

| stock | what lays the crystals | how its grain differs from real film | status |
|---|---|---|---|
| **Pauli** | free fermions filling a Fermi disc: a determinantal point process | crystals repel; the grain is hyperuniform, with its structure factor falling to zero at low frequency | on the shelf: golden sampler, and a hardware-shaped circuit whose law ran on Atlas and holds |
| **Poisson** | uniform placement at the same density | none: the classical reference every other stock is measured against | on the shelf |
| **Speckle** | Born-rule shots of a random pupil through a 2D quantum Fourier transform | crystals bunch; the grain's contrast equals the fidelity of the machine that exposed it | planned |

## What has been measured

Every figure below has a dated entry in [docs/VALIDATION.md](docs/VALIDATION.md).

- **The shelf's Pauli law ran on Moth's Atlas emulator, and holds**
  (2026-09-25, job 8586f1cc).
  - **The circuit:** `givens_line.py`, 51 Givens rotations in 15 layers on
    the qubit line, 102 CNOTs. Its QASM has SHA-256 `ed767c01bd4b851d...`.
  - **The layouts:** 4,096 whole crystal layouts, every one of 5 crystals.
  - **Against the exact law:**
    - one-site frequencies within 1.48 standard errors, and all 120 pair
      frequencies within 2.52 (chi^2 112.3 over 120);
    - the whole distribution over the tile's symmetry orbits, chi^2 33.7 on
      33 degrees of freedom;
    - none of the 1,360 layouts the law forbids appeared.
  - **Coherence:** the engine's own <XX> and <YY> on two sites, 0.3755 and
    0.3687, match the exact 0.375.
  - **The records:** 1,995 device rolls, each bound to a commitment committed
    to git before the job's first status call. That ordering rests on the
    code and the local clock.
- **A fermion tile of this project's own ran on Moth's Atlas emulator**
  (2026-09-25). It had 16 qubits, 5 fermions and 256 CNOTs, and returned
  4,096 whole crystal layouts:
  - every layout held exactly 5 crystals;
  - all 120 site-pair statistics fell within 2.21 standard errors of that
    tile's exact law.

  Reading the samples needed a count order the platform does not document;
  it was decoded against known answers.
  - **That tile was a research prototype, not the shelf's Pauli law.** It
    filled the standing waves of an open box, not the Fermi disc of a
    periodic tile. The shelf's law ran later the same day (above).
  - This README first said otherwise, and so did four other documents.
    The P0 verifier caught it. Against the shelf's law, the same data
    score 20 standard errors off.
- **The three statistics are distinct at equal density** (2026-09-25). This
  was a classical simulation of the quantum laws, not hardware:

  | measure | fermionic | Poisson | speckle |
  |---|---|---|---|
  | nearest-neighbour pair correlation | 0.47 | 1.02 | 1.73 |
  | print-scale RMS on one shared scale, first layout only (grey levels) | 5.70 | 9.45 | 16.73 |

- **Arithmetic decides a roll unless it is pinned** (2026-09-25). The same
  random numbers were run at binary32, and 2 of 40 fermion films parted from
  the binary64 reference. From the first differing draw on, they shared only
  55–86% of their crystals.
- **The authority's rolls do not depend on its arithmetic.** A draw closer
  than 2^-224 to a boundary is refused, not decided. The 256-bit error in
  every target and boundary is at most 2^-249.2. It was measured draw by draw
  against references that share none of the authority's code: exact
  Fractions on pauli-4x4, whose kernel is rational, and an independent chain
  rule at 512 bits on the 16x16 stock.
- **Identical requests to Atlas returned different bytes wherever sampling
  was involved**, seeded engines included; a seed fixes the circuit, not
  the shots.

## What it is not

- **Not a quantum advantage.** At these sizes both quantum laws are classically
  simulable. That is exactly what makes them checkable. "Quantum" here means
  the crystals were laid by coherent interference, verified against the exact
  law.
- **Not deterministic at the shot.** A roll from a device is unique. The fixer
  records it, and nothing reproduces it. What is deterministic is everything
  downstream of the record, and every emulated roll.
- **Not on hardware yet.** The Atlas account used here has no QPU access.
  Hardware runs are planned on IBM's free Open Plan.
- **Not a model of any real film's grain.** Poisson is the reference; Pauli and
  Speckle are the point.

## How the claims are checked

One command, in two sizes:

```bash
make verify-quick   # ~30 s: lint, docs, vectors, golden, circuits, decode, client, fixer, the control and its twin
make verify         # adds the cft and live-Atlas stages, each skipped BY NAME when it cannot run
bash verify/run.sh --list
```

- **The authority** is `quantum_film/golden`: pure Python and mpmath at 256
  bits, with exact counter-based uniforms (SHA-256). It imports nothing it
  could share with what it judges; a test holds that mechanically. The
  circuits, the float paths and Atlas's results are all scored against it.
- **Refusals.** A draw that rounding could decide is refused by name, and so
  is a record whose bytes or law have changed.
- **The negative control, and its twin.** Every run feeds the fixer's own
  command line a record with one crystal moved. If the fixer accepts it, or
  refuses it for any reason but its digest, the run fails. The twin feeds it
  the genuine records, which it must accept, because a command line that
  refused everything would pass the control alone.
- **Gates are held to planted faults.** Among them: a sampler bug, a shrunken
  margin, a moved crystal, a re-attributed job, a skipped test, a stale path.
  The P0 verifier found gates that could not fail, and a runner that could
  report PASSED over a failure. docs/VALIDATION.md records each, and what now
  makes it fail.

What is promised, and what is not, is written down once, in
[docs/DETERMINISM.md](docs/DETERMINISM.md).

## Layout

```
quantum_film/stocks.py     the shelf: every stock's parameters, in one table
quantum_film/golden/       the authority: exact uniforms, the Pauli and Poisson laws
quantum_film/circuits/     the Pauli law as a Givens circuit (float64, independent of golden)
quantum_film/atlas/        the Atlas client (key kept outside the tree) and the count-order rule
quantum_film/fixer.py      negative records: fix, check from the record alone, reproduce
verify/                    the runner: make verify-quick / make verify
tools/                     the vector generator and the cft and Atlas smoke checks
tests/, tests/vectors/     the gates, and the frozen vectors they replay
docs/                      one file per subject; docs/README.md is the index
research/2026-09-25/       the day of exploration the project started from, kept as run
vendor/cft-fp256           the pinned-arithmetic library, a submodule at 7d7285d
```

## Moth Hack 2026

Entered for the Expert challenges #9 (a repository) and #10 (a notebook). **By
its owner's intent this entry is not a candidate for cash prizes.** It was
built by Logan W. together with AI collaborators (Claude Opus 5.5 and the
agents it directed), who are credited here as contributors equal to the human
one; every commit carries its co-author line.

## Neighbours

- [atlas-film](https://github.com/loganw234/atlas-film): the medium; the
  sourced organs development borrows.
- [cft-fp256](https://github.com/loganw234/cft-fp256): deterministic IEEE 754
  arithmetic, and the pinned path for development.
- [atlas-engine](https://github.com/loganw234/atlas-engine): the same
  discipline on GPUs, one hash across vendors.
- The methods it is built under:
  [HonestFramework](https://github.com/loganw234/HonestFramework) and
  [ParcelRound](https://github.com/loganw234/ParcelRound).

## Licence

MIT ([LICENSE](LICENSE)). cft-fp256 is Apache-2.0 and is pinned as a
submodule; [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) carries its
NOTICE and lists every other dependency's licence.

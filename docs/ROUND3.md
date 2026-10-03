# Round 3: the shelf's law on IBM hardware, and the bundle Moth runs

A ParcelRound round (github.com/loganw234/ParcelRound, METHOD.md). The lead is
the session that built P0. There are two parcels, each an Opus 5.5 agent with
a brief, named negative controls and a verifier of its own.
- **Before dispatch:** a verifier checks P0 before either parcel is
  dispatched, as in round 1.
- **Every hardware job is the lead's.** It is submitted only at the owner's
  word, after a verifier has checked that exact submission.

**The aim** (the owner, 2026-10-01 and 03):
- Run the shelf's Pauli law (pauli-4x4; circuit `ed767c01bd4b851d`, the one
  that ran on Atlas) on IBM hardware. The first runs validate the system
  where a mistake is cheap.
- Then make an honest comparison: 24,576 hardware shots against Atlas's
  24,576 emulator shots, the exact law and the classical twin.
- Then hand the same bundle to Moth, whose CTO runs it on Moth's IBM access.
  Moth has no route for arbitrary circuits (2026-10-03).

docs/HARDWARE.md holds what was measured before any job ran. The deadline is
5 October (PT).

## What P0 settled

These are lead-owned. Parcels read them and never edit them.

- **The device-run record and commitment v3** in `quantum_film/fixer.py`:
  `RUN_FORMAT`, `check_run`, `fix_run`, `commitment_v3`, `options_digest`.
  - One record holds every shot of one circuit in one job, with its role and
    the basis each qubit was read in. Its commitment binds the route, the
    backend, the program, the logical and the transpiled circuit, the shots,
    the options and the decode rule.
  - Tests: `tests/fixer/test_device_runs.py`.
- **The IBM reader**, `quantum_film/ibm/decode.py`, held to a known answer by
  `tests/decode/test_ibm_decode.py`.
- **The claims files and the front door.** The claims files are README.md,
  CLAUDE.md, THIRD_PARTY_NOTICES.md and `docs/`. The front door is
  `verify/run.sh`, apart from the additions a parcel's section names, and
  `pyproject.toml`. A parcel that finds one stale reports it and does not
  edit it.
- **The keys.** `QF_IBM_KEY_FILE` and `QF_IBM_INSTANCE_FILE` name files in
  `C:\Users\logan\.quantum-film\`, outside every directory an agent is
  given. No parcel reads them, contacts IBM or submits a job.
- **The emulator's records**, under `docs/records/2026-09-25/` and `docs/records/2026-09-26/`, stay as they
  are.

## The frozen bundle

Both parcels serve this design. A bundle is a directory, committed to git
before it is run, that fixes a hardware run completely.
- **The manifest** states:
  - the stock, the backend and the calibration time of the target it was
    compiled against;
  - the qiskit and qiskit-ibm-runtime versions, and the program;
  - the options: dynamical decoupling and twirling off, stated, not
    defaulted.
  - For each circuit: its role and basis, its shots, the logical and
    transpiled circuits' SHA-256, the chain, a salt and its commitment v3.
- **The circuits**, each measured with `measure_all` before compiling:

  | circuit | what it is | shots |
  |---|---|---|
  | known-answer | X on {0, 1, 3, 7, 12} | 1,024 |
  | law | `ed767c01bd4b851d` | 24,576 |
  | coherence XX | the law, with qubits 0 and 1 rotated to X | 4,096 |
  | coherence YY | the law, with qubits 0 and 1 rotated to Y | 4,096 |

  In law, the pair's ⟨XX⟩ and ⟨YY⟩ are +0.375 for this circuit, and a
  classical mixture with the same layouts gives 0.
- **Running a bundle never compiles.**
  - The runner submits exactly the committed transpiled circuits, after
    checking their bytes and the backend's name against the manifest.
  - So both routes run the same circuits, and everything the commitment binds
    is in git before the job exists.
  - The price: the chain was chosen against the calibration of the day the
    bundle was frozen. So a bundle is frozen close to its run, and another
    device gets another bundle.

## P1: the hardware runner and the bundle (Quantum-Film)

- **Owns:**
  - `tools/hw_bundle.py` (new) and `tools/hw_run.py` (new), both scripts that
    refuse to be imported;
  - new pure modules in `quantum_film/ibm/`, apart from `decode.py`;
  - `tests/hardware/` (new);
  - in `verify/run.sh`, exactly: new `stage` line pairs for its tests, with
    any skip by name through `need_file` or `need_env`, and those stages
    added to the budgets that should run them.
  - Its qiskit lives in its own virtualenv, never in the project's main
    Python.
- **The job:**
  - **Freezing a bundle.** `hw_bundle.py` takes a backend's target and
    builds the bundle from it.
    - It compiles at an explicit level with a fixed seed.
    - It applies the five SWAP-free checks of docs/HARDWARE.md.
    - It holds every transpiled circuit to its expected result with this
      project's own simulator, not qiskit's:
      - the law circuit, to the authority's det(K_Y) over all 4,368 layouts;
      - the coherence circuits, to ⟨XX⟩ and ⟨YY⟩;
      - the known-answer circuit, to its one outcome.
    - The lead freezes the real bundle against the live target, a read with
      the owner's key and no job. P1 tests against the fake backends.
  - **Running a bundle.** `hw_run.py` does these, in order:
    - refuses every key-leak condition in docs/HARDWARE.md, and names the
      Open instance;
    - checks the backend and the transpiled circuits' bytes against the
      manifest;
    - puts each circuit's commitment in its metadata;
    - submits one job, with `max_execution_time` capped;
    - git-commits the job line (job id and IBM's created time) BEFORE any
      status or result call;
    - then fetches, reads every circuit's bitstrings through
      `quantum_film.ibm.decode`, fixes one device run per circuit, and writes
      the raw results and the job's metrics;
    - checks every record with the fixer's command line.
  - A dry run against a fake backend exercises the whole path offline.
  - **Moth's route.** A README in the bundle tells Moth's CTO what to run,
    with what, and what to send back. It is the same runner and the same
    bundle; only the account differs. This was P3 before Moth's answer.
- **Negative controls:**
  - A transpiled circuit with one gate changed is refused before
    submission.
  - A reader in plain order fails the known-answer check.
  - The runner refuses to start under each key-leak condition.
  - A manifest whose hash differs from a circuit file is refused.
- **Forbidden:**
  - everything P0 settled, and every file P2 owns;
  - any contact with IBM or Moth;
  - reading the key files;
  - installing into the project's main Python.

## P2: the comparison (Quantum-Film)

- **Owns:**
  - `quantum_film/compare.py` (new), pure;
  - `tools/hw_predict.py` (new), a script that refuses to be imported and runs
    in P1's virtualenv;
  - `tests/compare/` (new);
  - in `verify/run.sh`, exactly: new `stage` line pairs for its tests, added
    to the budgets that should run them.
- **The job:** measure, never gate.
  - **For a law run:**
    - the number of crystals per shot;
    - the share with exactly N crystals, and among those the share on
      layouts the law forbids;
    - the total variation distance to the law, against a perfect sampler's
      floor at the same count;
    - a linear cross-entropy fidelity;
    - one-site and pair z, raw and with only the N-crystal shots;
    - the nearest-neighbour pair correlation.
  - **For the coherence runs:** ⟨X0X1⟩ and ⟨Y0Y1⟩ with their errors.
  - **The same measures for the baselines:**
    - the exact law;
    - Atlas's 24,576 emulator shots;
    - the twin, exactly and at the same shot count.
  - **Predictions** for a frozen bundle's chain, from a noisy simulation of
    its device, with the model's date stated.
  - **The print rule:** a hardware print is laid from the shots with exactly
    N crystals, in canonical order. Its geometry follows from their count and
    the honesty floor.
- **Negative controls:**
  - A classical mixture with the law's layout statistics scores coherence
    near 0.
  - A twin sample puts about 31% of its shots on forbidden layouts.
  - Samples of the exact law score at the floor.
- **Forbidden:**
  - everything P0 settled, and every file P1 owns;
  - any contact with IBM or Moth;
  - reading the key files.

## The lead's runs, in order

Each run needs the owner's word, and a verifier's check of exactly what will
be submitted.
1. **Freeze the IBM bundle** against the live target of the device chosen at
   freezing (the best estimated success probability among the three, unless
   the owner names one), and commit it.
2. **Commit the pre-registration**, `docs/PREREGISTRATION.md` (new). It states:
   - the measures and the baselines;
   - P2's predictions for the frozen chain;
   - that everything will be reported, whatever it shows.

   It is committed before the law circuit runs.
3. **The known-answer job** (1,024 shots), alone. If the device reads it in
   any order but decode's, nothing else runs until that is understood.
4. **The film's job:** the law and both coherence circuits.
5. **Moth's run:** a bundle frozen for a device Moth's account reaches, handed
   to Moth, and its results recorded the same way.

## The ledger

It lives at `C:\Users\logan\source\repos\quantum-film-ledger\round3\`,
outside every repository. It has one file per author, append only, and an
`urgent/` directory that every agent watches. Its README is ParcelRound's
ledger template.

## Merges and pushes

The lead merges each parcel after its verifier says READY. It then runs
`verify/run.sh --require-all` and pushes main, checking the push with
`git ls-remote`.

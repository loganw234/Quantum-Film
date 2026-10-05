# For Moth: Quantum-Film's circuit, what IBM's hardware did with it, and how to run it

This is for Moth's CTO. It comes from Logan W. and the AI collaborators who built Quantum-Film with him (Claude
Opus 5.5 and the agents it directed). Moth offered on 2026-10-03 to run a specific circuit for the project's
validation. This page is that circuit, with what three IBM machines made of it on 2026-10-05. Running it is
Moth's choice, and nothing here waits on it.

## What the circuit is

Quantum-Film's Pauli stock lays film-grain crystals with a quantum circuit. It samples free fermions on a 4 x 4
periodic tile: five crystals among sixteen sites, whose joint law is a determinant (a determinantal point
process).
- **The circuit:** a 16-qubit circuit prepares that state with 51 Givens rotations in 15 layers on the qubit
  line, 102 two-qubit gates (`quantum_film/circuits/givens_line.py`). Measuring it in Z lays one tile's
  crystals.
- **What only quantum mechanics gives it:**
  - **exclusion:** the law forbids 1,360 of the 4,368 possible five-crystal layouts outright;
  - **coherence:** ⟨X0X1⟩ = ⟨Y0Y1⟩ = +0.375, where any classical mixture of the same layouts gives 0.

## What it has done

- **On Moth's Atlas emulator** (2026-09-25 and 26): 24,576 shots, which lay the exact law to a perfect sampler's
  floor (README.md, "What has been measured").
- **On three IBM Heron r2 QPUs** (2026-10-05): ibm_kingston, ibm_marrakesh and ibm_fez, on the owner's free
  Open plan.
  - It was pre-registered (docs/PREREGISTRATION.md).
  - Each job's commitment was pushed to GitHub before any result was read.
  - The full tables are in docs/HARDWARE-RESULTS.md. In brief:

  | | ibm_kingston | ibm_marrakesh | ibm_fez | Atlas emulator | classical twin |
  |---|---|---|---|---|---|
  | share of five-crystal shots on forbidden layouts | 0.0431 | 0.0513 | 0.0544 | 0.0000 | 0.3114 |
  | linear XEB (twin 0, law 1) | +0.8444 | +0.8491 | +0.8064 | +1.0117 | 0 |
  | ⟨X0X1⟩ (law +0.375) | +0.3315 | +0.3135 | +0.2690 | +0.3770 | 0 |
  | ⟨Y0Y1⟩ (law +0.375) | +0.3296 | +0.3438 | +0.3047 | +0.3695 | 0 |

  All three devices carry the law's exclusion and its coherence, and all three fall short of what their own noise
  models predicted.

## The circuits, as files

Four logical circuits, OpenQASM 2.0, 16 qubits. Each ends by measuring every qubit, so classical bit i reads
qubit i. They are the same bytes in every IBM bundle; here they are in `docs/records/2026-10-05/ibm/ibm_kingston/bundle/`:

| file | what it is | shots we used | SHA-256 |
|---|---|---|---|
| `known-answer.qasm` | X on qubits {0, 1, 3, 7, 12}: it fixes the bit order of the results | 1,024 | `60c78957bf47b2b2bb8053b2e2103fa2bf1373752b85acfdc4bd37037f22ff49` |
| `law.qasm` | the law: the committed source `ed767c01bd4b851d...` with its measurements | 24,576 | `33cfeaa15e5ab0af031531d6b0bdbaee4df311196ca422fe6b927ee783e35fc7` |
| `coherence-xx.qasm` | the law, with qubits 0 and 1 read in X | 4,096 | `bc4c3f12aa1f366abd28746ae7d22c8f6a7cfdb5ab6e926fe94b058e4072220f` |
| `coherence-yy.qasm` | the law, with qubits 0 and 1 read in Y | 4,096 | `0c57183b5e86c3091ceab22deb3f4cc3387a8379febe7ba22e1841e03d98b5f0` |

**What a perfect machine gives:**
- the known answer: every shot reads {0, 1, 3, 7, 12};
- the law: every shot holds exactly five crystals on an allowed layout, with the probabilities
  `quantum_film.compare.exact_law` computes exactly;
- the two coherence circuits: +0.375 each.

Each device's compiled version (QPY, and OpenQASM 3 to read) is in its bundle beside these, as frozen for that
device's calibration on 2026-10-05.

## If Moth wants to run it

**Either way, run the known-answer circuit first.** Its result fixes the order of the bits, whatever the tool's
convention: a reading in the wrong order shows the mirror set {3, 8, 12, 14, 15}.

### 1. Any way Moth likes

- Compile the four circuits for the device as Moth normally would. IBM's optimization level 2 found a 16-qubit
  chain with no SWAPs on all three Heron r2 devices.
- Use the shots above, one job per shot count. We used no dynamical decoupling, no twirling and no error
  mitigation.
- Send back, for each circuit:
  - its counts, as `{bitstring: count}`, with the convention stated (in Qiskit's, the rightmost character is
    classical bit 0);
  - the backend's name;
  - the job id;
  - the job's created time.

We fix them as device runs (`quantum_film/fixer.py`) and measure them with the same table as IBM's
(`python -m quantum_film.compare table`). The anchor is weaker than our own runs': the counts reach us after they
exist, and the table will say so beside them.

### 2. The same runner we used

The design is in docs/ROUND3.md, and the runner is `tools/hw_run.py`. It needs:
- Python 3.12;
- exactly qiskit 2.5.2 and qiskit-ibm-runtime 0.50.0 (`pip install -e .[ibm]`), plus numpy and mpmath;
- Moth's IBM key and instance CRN in two files outside the checkout (`QF_IBM_KEY_FILE`, `QF_IBM_INSTANCE_FILE`).

The steps:
1. Freeze a bundle for a device Moth's account reaches, as a read with no job:
   `python tools/hw_bundle.py --backend <device> --route moth --out <dir>`.
2. Send us the directory. We commit and push it before it runs, so its commitments are public first. If the
   device is not one of the nine in `quantum_film.fixer.IBM_DEVICES`, we add it by name first.
3. Run the three jobs in the order the bundle's README gives: `python tools/hw_run.py --bundle <dir> --job
   known-answer --out <out>`, then law and coherence only if it prints HOLDS.
   - Each job's line is printed the moment IBM has created the job: send it to us then, before the results.
   - The runner refuses a job that already has a line, and never resubmits.
4. Send back the whole output directory, unchanged, and the console output.

**Rehearse first** on a bundle frozen against a fake backend (`--fake fake_kingston --route moth`) with
`--dry-run`. That needs no account, and makes records of kind `simulator`.
- A bundle frozen against a live device cannot be dry-run: the runner refuses a fake backend for it.
- The README frozen into our three IBM bundles says otherwise, and is wrong on that point (docs/VALIDATION.md,
  2026-10-05). Bundles frozen from now on say what this page says.
- Our runner uses the `sampler` program (SamplerV2), which IBM deprecated on 2026-09-24 and removes no sooner
  than about 2026-12-24 (docs/HARDWARE.md).

## Who to contact

Logan W., who owns the repository: github.com/loganw234/Quantum-Film.

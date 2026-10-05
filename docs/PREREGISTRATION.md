# Pre-registration: pauli-4x4 on three IBM Heron r2 devices

This file is committed and pushed before any law circuit runs (docs/ROUND3.md,
"The lead's runs"). Git's history dates it. It fixes:
- what will run, and in what order;
- when to stop;
- what will be measured;
- what was predicted, and against what;
- what will be reported.

After a run, nothing here is edited. A change is a dated note appended at the
end, saying what changed and why.

## What will run

The same design runs on each of the three devices the owner's instance
reaches. That is one bundle per device, each a full set of three jobs.

- **The bundles** were frozen together at 2026-10-05T08:34Z, each against its
  device's live target. The freeze was a read with the owner's key, and no job
  ran. Each bundle's identity is its manifest's SHA-256:

  | device | bundle | manifest SHA-256 | calibration | law ESP | chain (logical 0 to 15) |
  |---|---|---|---|---|---|
  | ibm_kingston | `docs/records/2026-10-05/ibm/ibm_kingston/bundle` | `6894a01142e24b2f47c13f19a80ef6c9ed48e26bd94285ba3035cce31881b656` | 2026-10-05T06:57:43Z | 0.682 | [20, 21, 36, 41, 42, 43, 44, 45, 46, 47, 57, 67, 66, 65, 64, 63] |
  | ibm_marrakesh | `docs/records/2026-10-05/ibm/ibm_marrakesh/bundle` | `c4752138034ed618db85512ec835c8d8bf25edc9b4aea60f66b9283188135882` | 2026-10-05T07:35:49Z | 0.656 | [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15] |
  | ibm_fez | `docs/records/2026-10-05/ibm/ibm_fez/bundle` | `3e5a5959d1cd8200c6ed348942d68d7112a13c0a21127e2f482298dd6c75f0fa` | 2026-10-05T08:16:22Z | 0.631 | [140, 141, 142, 143, 136, 123, 124, 125, 117, 105, 106, 107, 108, 109, 110, 111] |

- **What every bundle shares:**
  - the logical circuits, derived from `ed767c01bd4b851d`;
  - the compile: optimization level 2 with seed 11, the law's chain chosen by
    the device's calibration, and the other circuits pinned to it;
  - route `ibm-direct`, program `sampler` (SamplerV2), on the Open plan's
    instance;
  - the options: dynamical decoupling and gate and measurement twirling off,
    stated, and no error mitigation.
- **How the devices came to be three.** docs/ROUND3.md chose one device: the
  best estimated success probability (ESP) of the law's chain.
  - All three were frozen to apply that rule, and it chose ibm_kingston.
  - The owner then asked for a set on each device, for comparison (round-3
    ledger, lead.md, 2026-10-05).
  - So the ESP order is now the order the devices run in.
- **The jobs, on each device, each submitted once:**

  | job | circuits | shots | QPU-time cap |
  |---|---|---|---|
  | known-answer | X on {0, 1, 3, 7, 12} | 1,024 | 60 s |
  | law | the law, `ed767c01bd4b851d` | 24,576 | 120 s |
  | coherence | the law read in XX, then in YY, on qubits 0 and 1 | 4,096 each | 60 s |

  - The law job's 24,576 shots are the emulator's count. Each measure over
    five-crystal shots carries its floor at its own count.
  - By docs/HARDWARE.md's estimate, a set costs about 18 s of QPU time, and the
    three sets about 54 s of the instance's 600 s.

## The order, and when to stop

1. **The devices run in ESP order:** ibm_kingston, then ibm_marrakesh, then
   ibm_fez.
2. **On each device, the known-answer job runs alone first.** Its verdict is
   decode's `known_answer`:
   - the modal outcome must be exactly {0, 1, 3, 7, 12};
   - it must be strictly ahead of its mirror, {3, 8, 12, 14, 15}.

   If a known answer does not hold, nothing more runs on any device until
   that is understood, and a note appended here says what was found.
3. **Then that device's law job, then its coherence job.**
4. **What every job needs before it runs:**
   - the owner's word, given for the three sets on 2026-10-05;
   - its line committed and pushed before any result is read.
5. **Failures.**
   - A job that fails keeps its line and its status file, and is reported as
     failed.
   - A re-run needs a newly frozen bundle, with new salts. It is a new entry
     here, never a replacement.

## What will be measured

The comparison measures; it never passes or fails a run
(`quantum_film/compare.py`). For each device the table is

    python -m quantum_film.compare table --prediction <its predictions> docs/records/2026-10-05/ibm/<device>/run

It has one column per baseline and prediction, and one for the device's `qpu`
runs. Its rows:
- the shots;
- the share with exactly five crystals;
- among those, the share on layouts the law forbids;
- the total variation distance to the law, beside a perfect sampler's floor at
  the same count;
- the linear cross-entropy fidelity (XEB), normalised so that the law scores 1
  and the twin 0;
- one-site and pair z, the worst of each, on all shots and on the five-crystal
  shots;
- the nearest-neighbour pair correlation;
- ⟨X0X1⟩ and ⟨Y0Y1⟩, with binomial errors.

The three devices' columns are also shown side by side. Each known-answer
verdict and its shares are reported beside the tables.

## The baselines, before any hardware data

The baselines are:
- the exact law;
- Atlas's 24,576 emulator shots, the device rolls under
  `docs/records/2026-09-25/p3` and `docs/records/2026-09-26/p3`;
- the classical twin, five distinct sites of 16 chosen uniformly;
- the twin sampled at 24,576 shots.

The table, at lead-merge-r3 87e732c:

| measure | law (exact) | emulator (Atlas, 24576 shots) | twin (exact) | twin (sample, 24576 shots) |
|---|---|---|---|---|
| shots | 24,576 | 24,576 | 24,576 | 24,576 |
| N-crystal share | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| forbidden share of N-crystal shots | 0.0000 | 0.0000 | 0.3114 | 0.3048 |
| TVD to the law | 0.0000 | 0.1289 | 0.3114 | 0.3942 |
| perfect sampler's TVD floor: mean / p95 | 0.1319 / 0.1350 | 0.1319 / 0.1350 | - | 0.1319 / 0.1350 |
| linear XEB | +1.0000 | +1.0117 +- 0.0095 | +0.0000 | +0.0006 +- 0.0053 |
| one-site max \|z\|: all / N-crystal | 0.00 / 0.00 | 2.15 / 2.15 | 0.00 / 0.00 | 2.31 / 2.31 |
| pair max \|z\|: all / N-crystal | 0.00 / 0.00 | 2.64 / 2.64 | 13.49 / 13.49 | 15.60 / 15.60 |
| NN pair correlation: all / N-crystal | 0.6400 / 0.6400 | 0.6371 / 0.6371 | 0.8533 / 0.8533 | 0.8533 / 0.8533 |
| `<X0X1>` | +0.3750 | +0.3770 +- 0.0059 | +0.0000 | -0.0101 +- 0.0064 |
| `<Y0Y1>` | +0.3750 | +0.3695 +- 0.0059 | +0.0000 | -0.0033 +- 0.0064 |

## The predictions for these bundles

`tools/hw_predict.py --live` ran on exactly each bundle's four QPY files, with
seed 20261003. Each run read its device with the key, and no job ran.
- **With no noise** (`prediction-none.json`), each is a control. It is the
  frozen circuits, compiled for the device, laid by a perfect simulator and
  read through decode, so it must lay the law to within its sampling:
  - ibm_kingston: TVD 0.1331 against the floor's 0.1319 / 0.1350, XEB
    +0.9925 ± 0.0094, coherences +1.8 and +0.7 standard errors from +0.375;
  - ibm_marrakesh: TVD 0.1305, XEB +0.9933 ± 0.0093, coherences +2.4 and +0.0;
  - ibm_fez: TVD 0.1316, XEB +0.9947 ± 0.0093, coherences +0.4 and +0.4.
- **With the noise model** Aer builds from the device's calibration as read
  at the time (`prediction-backend.json`), each is the prediction.
- **The calibrations behind it all** are committed beside the bundles as
  `properties-<stamp>.json`:
  - one for each freeze, which chose the chain and its ESP;
  - one for each noisy prediction where its stamp differs: marrakesh's and
    fez's stamps had moved on by then, and kingston's had not.

  The values had not moved. Between each device's two snapshots, 0 of
  marrakesh's 6,230 values and 0 of fez's 6,203 differ; only their dates do
  (round 3's verifier-P2). So each device's freeze and its prediction rest on
  the same error data.

  Each was read again from IBM's history, as of the moment it was first read,
  and its `last_update_date` is the stamp it is named by. Together they hold
  every gate and readout error the ESPs and the noise models were built from.

The files are in `docs/records/2026-10-05/ibm/<device>/`. Each circuit's simulator
seed is the seed plus its place (law, xx, yy, known-answer: 0 to 3), the same
on every device, so the devices' sampling may be correlated.
- Measured on the ideal controls (verifier-P2), the correlation is weak. Two
  devices' per-outcome deviations correlate by -0.03 to +0.08, against about
  +0.01 for two independent samples.
- So the three ideal coherences in X, +1.8, +2.4 and +0.4 standard errors
  from +0.375, are close to three independent draws.
- The bundle check's exact parities of the frozen circuits are 0.375, and
  verifier-P1's amplitude check gives each circuit fidelity 1 with its logical
  circuit.

With each device's noise model:

| measure | ibm_kingston, noise model of 2026-10-05T06:57:43Z | ibm_marrakesh, noise model of 2026-10-05T08:32:46Z | ibm_fez, noise model of 2026-10-05T08:38:44Z |
|---|---|---|---|
| shots | 24,576 | 24,576 | 24,576 |
| N-crystal share | 0.7215 | 0.6934 | 0.6770 |
| forbidden share of N-crystal shots | 0.0224 | 0.0247 | 0.0272 |
| TVD to the law | 0.1704 | 0.1712 | 0.1764 |
| perfect sampler's TVD floor: mean / p95 | 0.1580 / 0.1616 | 0.1600 / 0.1643 | 0.1603 / 0.1639 |
| linear XEB | +0.9390 +- 0.0110 | +0.9210 +- 0.0111 | +0.9210 +- 0.0113 |
| one-site max \|z\|: all / N-crystal | 4.45 / 2.74 | 4.79 / 3.13 | 5.17 / 3.51 |
| pair max \|z\|: all / N-crystal | 8.78 / 3.26 | 9.62 / 3.38 | 9.83 / 3.58 |
| NN pair correlation: all / N-crystal | 0.6971 / 0.6503 | 0.7049 / 0.6525 | 0.7084 / 0.6534 |
| `<X0X1>` | +0.3628 +- 0.0146 | +0.3628 +- 0.0146 | +0.3564 +- 0.0146 |
| `<Y0Y1>` | +0.3569 +- 0.0146 | +0.3530 +- 0.0146 | +0.3613 +- 0.0146 |

With no noise, the controls:

| measure | ibm_kingston, no noise | ibm_marrakesh, no noise | ibm_fez, no noise |
|---|---|---|---|
| shots | 24,576 | 24,576 | 24,576 |
| N-crystal share | 1.0000 | 1.0000 | 1.0000 |
| forbidden share of N-crystal shots | 0.0000 | 0.0000 | 0.0000 |
| TVD to the law | 0.1331 | 0.1305 | 0.1316 |
| perfect sampler's TVD floor: mean / p95 | 0.1319 / 0.1350 | 0.1319 / 0.1350 | 0.1319 / 0.1350 |
| linear XEB | +0.9925 +- 0.0094 | +0.9933 +- 0.0093 | +0.9947 +- 0.0093 |
| one-site max \|z\|: all / N-crystal | 1.87 / 1.87 | 2.17 / 2.17 | 2.01 / 2.01 |
| pair max \|z\|: all / N-crystal | 2.71 / 2.71 | 2.87 / 2.87 | 3.08 / 3.08 |
| NN pair correlation: all / N-crystal | 0.6399 / 0.6399 | 0.6403 / 0.6403 | 0.6381 / 0.6381 |
| `<X0X1>` | +0.4004 +- 0.0143 | +0.4087 +- 0.0143 | +0.3804 +- 0.0145 |
| `<Y0Y1>` | +0.3853 +- 0.0144 | +0.3755 +- 0.0145 | +0.3813 +- 0.0144 |

- **The known answers** are predicted to hold on every device. With no noise,
  all 1,024 shots read {0, 1, 3, 7, 12}. Under each noise model:

  | device | shots on {0, 1, 3, 7, 12} | shots on the mirror |
  |---|---|---|
  | ibm_kingston | 86.9% | 0.0% |
  | ibm_marrakesh | 85.5% | 0.0% |
  | ibm_fez | 84.1% | 0.0% |
- **What the noise model leaves out:**
  - It is Aer's model from the backend's reported properties: gate errors,
    relaxation and dephasing, and readout errors.
  - It leaves out crosstalk, leakage, non-Markovian noise and drift after the
    calibration it was built from.
  - On round 3's fake-backend runs (docs/HARDWARE.md), the full model and the
    same model with idle decoherence differed by 5.0 to 5.3 points in the
    five-crystal share.
  - So a prediction is a reference, not a bound.
- **What a prediction's error bar is.** The ± on a predicted coherence or XEB
  is the shot noise of the simulation itself, at 4,096 or 24,576 shots. It is
  not the model's uncertainty, which is not quantified (round 3's
  verifier-P2).
- **Who has re-run these predictions.** The lead ran each of them once.
  - Each noise model was built from the device's calibration as read at the
    time. A plain read returns a later calibration now.
  - **Round 3's verifier-P2 re-made 7 of the 12 noisy circuits' counts bit for
    bit** from the committed calibrations: the three known answers, the three
    XX circuits and kingston's YY.
    - Its backend took its properties from the snapshot, and its
      configuration from the same-named fake backend, whose coupling map
      equals the manifest's.
    - It built the simulator as hw_predict does, then ran the frozen QPY at the
      stated seed.
    - The script is in the round-3 ledger (verifier-P2.md, 10:13Z).
  - **Not re-made:** the three law predictions (24,576 shots each), and
    marrakesh's and fez's YY.
  - No tool in this repository rebuilds a noise model from a snapshot. Given
    the same calibration, a prediction repeats only on the same Aer version
    (qiskit-aer 0.17.2).
  - Each file holds its counts (`--with-counts`), so every measure can be
    recomputed from it. verifier-P2 did that for all six files, and re-made all
    three ideal ones bit for bit from the frozen QPY.

## What the measures bear on

These are stated so that a reader can hold the results to them. None of them
is a pass mark, and every measure is reported whatever it shows.
- **Exclusion.** The law forbids 1,360 of the 4,368 five-crystal layouts; the
  twin puts 85/273 = 31.1% of its five-crystal shots on them.
  - A device that carries the law's exclusion shows a forbidden share far
    below 31.1%, near its prediction.
  - A fully depolarised device, whose bitstrings are uniformly random, also
    shows 31.1% among its five-crystal shots.
- **Coherence.** In law, ⟨X0X1⟩ = ⟨Y0Y1⟩ = +0.375. A classical mixture with
  the same layouts gives 0, so a value of either sign away from 0, beyond its
  error, is coherence that no reshuffling of layouts gives.
- **Fidelity.** The XEB sits between the twin's 0 and the law's 1. Noise pulls
  it towards 0, and the predictions give a value for each device.
- **Between the devices.** The predictions order the devices as their ESPs
  do, kingston then marrakesh then fez, on the five-crystal share and the
  forbidden share. On the XEB, marrakesh and fez tie, and the coherences are
  within one another's errors. The tables show whether the hardware keeps that
  order.
- **Against the emulator.** Atlas's emulator laid the law to the perfect
  sampler's floor: its TVD is 0.1289, against the floor's mean of 0.1319 and
  95th percentile of 0.1350. The hardware is expected to fall short of it, and
  the tables say by how much.

## What will be reported

- **Every job,** whatever its outcome, with its committed files:
  - its line;
  - its status file, for a job that did not complete;
  - its raw result, written before anything decoded it;
  - its records, each held by the fixer;
  - its metrics.
- **Every measure in the tables, for every `qpu` run.** No run is left out, no
  shot is dropped, and no measure is replaced after the data are seen.
  - The five-crystal rows restrict to shots that kept the crystal count, and
    state what share of shots that is.
- **Anything later is exploratory.** Any analysis not named here, for example
  a read-out-error correction, is labelled exploratory and shown beside the
  pre-registered tables, never in their place.
- **The prints** are laid by compare's print rule from each law run's
  five-crystal shots, in canonical order. Their geometry follows from that
  count.

## The Moth leg

At the owner's word (2026-10-05), Moth's leg is a handoff. It is not a run
this round waits for. Moth receives:
- the three devices' results;
- the logical circuit;
- the runner and its design, so that Moth's CTO can run the same jobs on Moth's
  IBM access if Moth wishes.

A bundle for that would be frozen with route `moth`, committed and pushed
before it is handed over. That leg's job lines are written on Moth's machine,
so this project cannot commit them before its results exist (docs/ROUND3.md
states the weaker anchor). Any results Moth returns are measured by the same
table, under a note appended here.

## A note, 2026-10-05 (about 11:30Z): a sheet of about 256 columns from each device

At the owner's word, after the nine jobs above had run and their results were committed, each device runs more law
shots, so that each gives a print of about 256 columns to compare by eye. Nothing above changes.

- **What will run.** 28 more standard bundles were frozen at 11:24-11:28Z, each against its device's live target,
  a read with no job. They are in `docs/records/2026-10-05/ibm/<device>/sheet-NN/bundle`:
  - 8 on ibm_kingston: calibration 11:05:15Z, the same chain as above, law ESP now 0.649;
  - 10 on ibm_marrakesh: 09:51:18Z, the same chain, 0.656;
  - 10 on ibm_fez: 10:08:31Z, the same chain, 0.631.

  Of each bundle, only the known-answer job and then the law job run; no coherence job.
- **The order, and when to stop.** Device by device, in the ESP order above. In each bundle the known answer runs
  first, and the law runs only if it holds. A known answer that does not hold stops everything, as above. Each
  job is submitted once.
- **The sheets.** Each device's sheet is laid by compare's print rule:
  - from the five-crystal shots of every qpu law run of that device on 2026-10-05, the run above and these;
  - in canonical order (job, then layout), shuffled on the print's own stream;
  - 29 layers deep, in the largest square of tiles their count fills (compare.print_geometry).

  64 tiles across, 256 columns, needs 118,784 five-crystal shots. At the morning's yields the sheets would be 68,
  69 and 70 tiles across.
- **What will be reported:**
  - every job, as above;
  - each new law run's measures, job by job. They show the run-to-run variation that each device's single run
    above could not;
  - each device's measures pooled over all its law runs;
  - the three sheets.
- **No new predictions.** The chains are the ones predicted above. kingston's calibration has moved (its law ESP
  from 0.682 to 0.649), and its prediction is not re-made.
- **QPU:** about 11 s a bundle by the nine jobs' charges, about 308 s in all, of the 555 s left.

# What IBM's hardware did: pauli-4x4 on three Heron r2 devices

On 2026-10-05 the design docs/PREREGISTRATION.md fixed beforehand ran on each of the three IBM Quantum devices the owner's Open-plan instance reaches. Every table below is quantum_film/compare.py's own, made from the records committed under `docs/records/2026-10-05/ibm/`, and every number in the prose is computed from them (docs/VALIDATION.md has the entry).

**In one paragraph.** All three devices carry the law's two quantum signatures, well clear of the classical twin: 4.3% to 5.4% of their five-crystal shots on forbidden layouts against the twin's 31.1%, and coherences of +0.27 to +0.34 where a classical mixture gives 0. And all three fall short of what their own noise models predicted.

## The jobs

Nine jobs, each submitted once, in the pre-registered order. Each job's line was committed and pushed before any result was read. On every device the known answer held before its law and coherence jobs ran.

| device | job | IBM job | created (UTC) | QPU seconds |
|---|---|---|---|---|
| ibm_kingston | known-answer | `db1nms2vog1s73fidhc0` | 2026-10-05T10:26:56Z | 2 |
| ibm_kingston | law | `db1nn11b694s73dsidjg` | 2026-10-05T10:27:16Z | 9 |
| ibm_kingston | coherence | `db1noheegvvc73bhtif0` | 2026-10-05T10:30:29Z | 4 |
| ibm_marrakesh | known-answer | `db1npihb694s73dsigqg` | 2026-10-05T10:32:42Z | 2 |
| ibm_marrakesh | law | `db1npojid5ic73erdnfg` | 2026-10-05T10:33:06Z | 9 |
| ibm_marrakesh | coherence | `db1npvavog1s73fidkvg` | 2026-10-05T10:33:33Z | 4 |
| ibm_fez | known-answer | `db1nq4rid5ic73erdnt0` | 2026-10-05T10:33:55Z | 2 |
| ibm_fez | law | `db1nq9hb694s73dsihg0` | 2026-10-05T10:34:14Z | 9 |
| ibm_fez | coherence | `db1nqg9b694s73dsihmg` | 2026-10-05T10:34:41Z | 4 |

IBM charged 45 QPU-seconds in all, 15 a device, of the instance's 600.

**The known answers** (X on {0, 1, 3, 7, 12}, 1,024 shots each) all held: the modal outcome is the expected set on every device, and no shot read its mirror.

| device | shots on {0, 1, 3, 7, 12} | predicted | on the mirror |
|---|---|---|---|
| ibm_kingston | 90.8% | 86.9% | 0.0% |
| ibm_marrakesh | 87.1% | 85.5% | 0.0% |
| ibm_fez | 88.6% | 84.1% | 0.0% |

## The three devices side by side

| measure | law (exact) | qpu: ibm_kingston | qpu: ibm_marrakesh | qpu: ibm_fez | emulator (Atlas, 24576 shots) | twin (exact) | twin (sample, 24576 shots) |
|---|---|---|---|---|---|---|---|
| shots | 24,576 | 24,576 | 24,576 | 24,576 | 24,576 | 24,576 | 24,576 |
| N-crystal share | 1.0000 | 0.6095 | 0.5185 | 0.5310 | 1.0000 | 1.0000 | 1.0000 |
| forbidden share of N-crystal shots | 0.0000 | 0.0431 | 0.0513 | 0.0544 | 0.0000 | 0.3114 | 0.3048 |
| TVD to the law | 0.0000 | 0.1998 | 0.2189 | 0.2194 | 0.1289 | 0.3114 | 0.3942 |
| perfect sampler's TVD floor: mean / p95 | 0.1319 / 0.1350 | 0.1726 / 0.1764 | 0.1841 / 0.1885 | 0.1829 / 0.1867 | 0.1319 / 0.1350 | - | 0.1319 / 0.1350 |
| linear XEB | +1.0000 | +0.8444 +- 0.0117 | +0.8491 +- 0.0129 | +0.8064 +- 0.0125 | +1.0117 +- 0.0095 | +0.0000 | +0.0006 +- 0.0053 |
| one-site max \|z\|: all / N-crystal | 0.00 / 0.00 | 14.90 / 6.31 | 18.59 / 6.78 | 15.87 / 5.26 | 2.15 / 2.15 | 0.00 / 0.00 | 2.31 / 2.31 |
| pair max \|z\|: all / N-crystal | 0.00 / 0.00 | 26.67 / 5.43 | 32.31 / 7.52 | 29.41 / 7.14 | 2.64 / 2.64 | 13.49 / 13.49 | 15.60 / 15.60 |
| NN pair correlation: all / N-crystal | 0.6400 / 0.6400 | 0.7626 / 0.6672 | 0.7738 / 0.6608 | 0.7799 / 0.6733 | 0.6371 / 0.6371 | 0.8533 / 0.8533 | 0.8533 / 0.8533 |
| `<X0X1>` | +0.3750 | +0.3315 +- 0.0147 | +0.3135 +- 0.0148 | +0.2690 +- 0.0150 | +0.3770 +- 0.0059 | +0.0000 | -0.0101 +- 0.0064 |
| `<Y0Y1>` | +0.3750 | +0.3296 +- 0.0148 | +0.3438 +- 0.0147 | +0.3047 +- 0.0149 | +0.3695 +- 0.0059 | +0.0000 | -0.0033 +- 0.0064 |

## What the measures bear on

Each point below is one the pre-registration named before any job ran. None of them is a pass mark.

- **Exclusion holds on all three devices.** Of the shots that kept five crystals, 4.3% to 5.4% landed on layouts the law forbids, against 31.1% for the classical twin and for uniformly random bitstrings. The noise models predicted 2.2% to 2.7%; the hardware put 1.92 to 2.08 times that on them.
- **Coherence holds on all three devices.** ⟨X0X1⟩ and ⟨Y0Y1⟩ run from +0.269 to +0.344, 18 to 23 standard errors from the 0 a classical mixture of the same layouts gives, and 2 to 7 below the law's +0.375.
- **Fidelity.** The linear XEB is +0.806 to +0.849 (the twin scores 0, the law 1), 4 to 7 combined standard errors below the predictions' +0.921 to +0.939.
- **Every prediction was kinder than its device.** The five-crystal share fell 11 to 17 points below its prediction, and the forbidden share came out about twice its prediction on each device. The noise models leave out crosstalk, leakage and drift, as the pre-registration said. Noise also moved more shots to six crystals than to four on every device: eleven of the sixteen sites are empty, so an error that flips a site at random adds a crystal more often than it removes one.
- **Between the devices.** kingston, first in the ESP order, is first on the five-crystal share (60.9%) and the forbidden share (4.3%), as predicted. marrakesh and fez swapped places on the five-crystal share (51.9% against 53.1%, predicted 69.3% against 67.7%), and fez has the lowest XEB and coherences.
- **Against the emulator.** Atlas's emulator laid the law to the perfect sampler's floor; each device's TVD (0.200 to 0.219) is above its own floor's 95th percentile (0.176 to 0.189): the excess over the floor is the devices' noise, measured.

## Each device beside its predictions

### ibm_kingston

| measure | law (exact) | predicted: ibm_kingston, no noise | predicted: ibm_kingston, noise model of 2026-10-05T06:57:43Z | qpu: ibm_kingston |
|---|---|---|---|---|
| shots | 24,576 | 24,576 | 24,576 | 24,576 |
| N-crystal share | 1.0000 | 1.0000 | 0.7215 | 0.6095 |
| forbidden share of N-crystal shots | 0.0000 | 0.0000 | 0.0224 | 0.0431 |
| TVD to the law | 0.0000 | 0.1331 | 0.1704 | 0.1998 |
| perfect sampler's TVD floor: mean / p95 | 0.1319 / 0.1350 | 0.1319 / 0.1350 | 0.1580 / 0.1616 | 0.1726 / 0.1764 |
| linear XEB | +1.0000 | +0.9925 +- 0.0094 | +0.9390 +- 0.0110 | +0.8444 +- 0.0117 |
| one-site max \|z\|: all / N-crystal | 0.00 / 0.00 | 1.87 / 1.87 | 4.45 / 2.74 | 14.90 / 6.31 |
| pair max \|z\|: all / N-crystal | 0.00 / 0.00 | 2.71 / 2.71 | 8.78 / 3.26 | 26.67 / 5.43 |
| NN pair correlation: all / N-crystal | 0.6400 / 0.6400 | 0.6399 / 0.6399 | 0.6971 / 0.6503 | 0.7626 / 0.6672 |
| `<X0X1>` | +0.3750 | +0.4004 +- 0.0143 | +0.3628 +- 0.0146 | +0.3315 +- 0.0147 |
| `<Y0Y1>` | +0.3750 | +0.3853 +- 0.0144 | +0.3569 +- 0.0146 | +0.3296 +- 0.0148 |

### ibm_marrakesh

| measure | law (exact) | predicted: ibm_marrakesh, no noise | predicted: ibm_marrakesh, noise model of 2026-10-05T08:32:46Z | qpu: ibm_marrakesh |
|---|---|---|---|---|
| shots | 24,576 | 24,576 | 24,576 | 24,576 |
| N-crystal share | 1.0000 | 1.0000 | 0.6934 | 0.5185 |
| forbidden share of N-crystal shots | 0.0000 | 0.0000 | 0.0247 | 0.0513 |
| TVD to the law | 0.0000 | 0.1305 | 0.1712 | 0.2189 |
| perfect sampler's TVD floor: mean / p95 | 0.1319 / 0.1350 | 0.1319 / 0.1350 | 0.1600 / 0.1643 | 0.1841 / 0.1885 |
| linear XEB | +1.0000 | +0.9933 +- 0.0093 | +0.9210 +- 0.0111 | +0.8491 +- 0.0129 |
| one-site max \|z\|: all / N-crystal | 0.00 / 0.00 | 2.17 / 2.17 | 4.79 / 3.13 | 18.59 / 6.78 |
| pair max \|z\|: all / N-crystal | 0.00 / 0.00 | 2.87 / 2.87 | 9.62 / 3.38 | 32.31 / 7.52 |
| NN pair correlation: all / N-crystal | 0.6400 / 0.6400 | 0.6403 / 0.6403 | 0.7049 / 0.6525 | 0.7738 / 0.6608 |
| `<X0X1>` | +0.3750 | +0.4087 +- 0.0143 | +0.3628 +- 0.0146 | +0.3135 +- 0.0148 |
| `<Y0Y1>` | +0.3750 | +0.3755 +- 0.0145 | +0.3530 +- 0.0146 | +0.3438 +- 0.0147 |

### ibm_fez

| measure | law (exact) | predicted: ibm_fez, no noise | predicted: ibm_fez, noise model of 2026-10-05T08:38:44Z | qpu: ibm_fez |
|---|---|---|---|---|
| shots | 24,576 | 24,576 | 24,576 | 24,576 |
| N-crystal share | 1.0000 | 1.0000 | 0.6770 | 0.5310 |
| forbidden share of N-crystal shots | 0.0000 | 0.0000 | 0.0272 | 0.0544 |
| TVD to the law | 0.0000 | 0.1316 | 0.1764 | 0.2194 |
| perfect sampler's TVD floor: mean / p95 | 0.1319 / 0.1350 | 0.1319 / 0.1350 | 0.1603 / 0.1639 | 0.1829 / 0.1867 |
| linear XEB | +1.0000 | +0.9947 +- 0.0093 | +0.9210 +- 0.0113 | +0.8064 +- 0.0125 |
| one-site max \|z\|: all / N-crystal | 0.00 / 0.00 | 2.01 / 2.01 | 5.17 / 3.51 | 15.87 / 5.26 |
| pair max \|z\|: all / N-crystal | 0.00 / 0.00 | 3.08 / 3.08 | 9.83 / 3.58 | 29.41 / 7.14 |
| NN pair correlation: all / N-crystal | 0.6400 / 0.6400 | 0.6381 / 0.6381 | 0.7084 / 0.6534 | 0.7799 / 0.6733 |
| `<X0X1>` | +0.3750 | +0.3804 +- 0.0145 | +0.3564 +- 0.0146 | +0.2690 +- 0.0150 |
| `<Y0Y1>` | +0.3750 | +0.3813 +- 0.0144 | +0.3613 +- 0.0146 | +0.3047 +- 0.0149 |

## What this does not show

- **One set a device.** Each device ran once, on one calibration; run-to-run and day-to-day variation is not measured.
- **The calibration moved.** kingston recalibrated between its bundle's freeze (06:57:43Z) and its run; each bundle keeps the chain chosen at its freeze, and each prediction the calibration it read.
- **The comparison measures; it does not gate.** It says how far each device is from the law and from the twin, not whether a device "passed".
- **No mitigation.** Dynamical decoupling, twirling and read-out correction were all off, as stated; any mitigated analysis would be exploratory and shown beside these tables, never in their place.
- **The limits round 3's verifiers stated** for the code that ran these jobs are in docs/VALIDATION.md (2026-10-05).

## The records

Each device's directory under `docs/records/2026-10-05/ibm/` holds:
- `bundle/`: the frozen circuits, their manifest and commitments, committed before any job;
- `prediction-none.json` and `prediction-backend.json`: the control and the prediction;
- `properties-<stamp>.json`: the calibrations behind its ESP and its noise model;
- `run/`: for each job its marker, line, raw result (written before anything decoded it), records, metrics and, for the known answer, its verdict.

To remake every table here: `python -m quantum_film.compare table --prediction <a prediction> docs/records/2026-10-05/ibm/<device>/run`, or `--json` for the numbers.

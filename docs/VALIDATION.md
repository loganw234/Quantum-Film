# Validation ledger

Every run that established something, in the order it happened. **A figure
here is a fact about the run that produced it**, on the date given, and is
never updated to match a later measurement - a later run gets a later entry.

Failures stay in, including the ones caused by the author of this file. A
ledger of successes is a brochure.

What this file is NOT: a description of how the project works, or a list of
what is true now. It is the evidence those documents will cite.

---

## 2026-09-25 - what an Atlas account with no features can do, and what repeats

Asked: which routes of Moth's Atlas platform (moth-api v0.41.0, the spec saved
as `api-1.json`) this project can use for Moth Hack 2026, whether the account
carries hardware access, and whether identical requests return identical
bytes. The owner supplied a throwaway API key for exploration, expiring within
24 hours; it is recorded nowhere in this repository. Every job ran on `emu`
(Aer). Times are UTC.

### Access, measured

- `GET /api/v1/me` - `features: []`, `platform_role: player`, no
  organisations. So **no `run_quantum`** (hardware) and **no
  `publish_engines`** (custom engines). The body carries the account email
  and is not kept in the records; this line is the fact taken from it.
- `GET /api/v1/me/storage` - quotas 1 GiB upload, 10 GiB total, 2 GiB
  notebooks; nothing used.
- `GET /api/v1/keys` and `/me/invitations` - 401 with an API key; the spec
  says both need a Supabase JWT.
- `GET /api/v1/engines` - 31 visible, all public, six of them test or demo
  engines. `credits_per_run` is 0 to 5, but no billing surface was found
  (the owner reports none on the site either).
- No jobs and no showcases on the account before these runs.

### Transport, measured

Cloudflare in front of `api.mothquantum.com` answers Python-urllib's default
user agent with **Error 1010, `browser_signature_banned`**. The client was not
disguised; it moved to curl, which Moth's own code samples use: 401 without
the key, 200 with it. Git for Windows' bundled curl 8.8.0 failed on every
request with error 43 (without the key too), so System32's curl.exe 8.13.0
is the one used. The client refuses any host but `api.mothquantum.com`.

### The census: each request made twice, compared

Commands (from `research/2026-09-25/atlas/`, `FIXER_ATLAS_AUTH` set):
`python recon.py`, `python probe.py`, `python probe2.py`, `python compare2.py`,
`python fetch_outputs.py`. Compared as SHA-256 of canonical JSON of the
result body, or of the content where the body carries fresh URLs.

| engine | request | seed parameter | two identical requests |
|---|---|---|---|
| coin-toss-v1 | 1000 shots | none | **differ**, both pairs: 519/481 vs 510/490; 514/486 vs 509/491 |
| blur-core-v1 | 4x4 grid, strength 0.3, exact mode | none (no sampling) | **identical**: `3d7a31ea90dd892b` in all four runs, the first and last about 15 minutes apart |
| blur-core-v1 | the same with 64 shots | none | **differ**, both pairs |
| tomography-api-v2 | this project's own 2-qubit QASM (`h`, `cx`, `ry(0.3)`), 1000 shots | none | **differ**, both pairs; per-basis pair counts come back; about 54 s a job |
| graph-v1 | 6 qubits, seed 7, 1000 shots | yes | **the circuit is identical, the shots are not**: `tomography` equal bit for bit, `measurements` differ |
| qdrive-api-v1 | 4 qubits, target ZZ = 1 on (0, 1), `sample: true`, seed 7 | yes | **differ**: all 15 fitted angles of the output circuit differ; no samples came back, inline or in the one output file |
| coin-toss-v1 | `stop_after: build` | - | **410** "job produced no result", twice: the built circuit is not exposed |

The raw responses are in `docs/records/2026-09-25/atlas/` (85 files),
written by `export_records.py`. Every presigned URL and the `/me` body are
removed, and a scan for key, token and email patterns refuses the export.
The scan was watched to fail: three planted strings were caught and one
clean string passed.

### A failure, mine

`probe2.py` imported `probe.py`, which had no main guard, so the whole first
probe set ran a second time: nine jobs at 17:47-17:48 that nobody asked for.
Their results are kept. They are the second pair in each of the first four
rows above, and the reason those rows say "both pairs". The guard is added.

### Findings

- **On Atlas a seed fixes the circuit, not the shots.** graph-v1 says so in
  the row above; no engine exposes a sampling seed.
- An engine with no sampling (blur-core exact) repeated its bytes across
  four runs. Everything that samples differed, the seeded engines included.
- tomography-api-v2 is the one route that runs an arbitrary circuit and
  returns counts, but only per qubit pair and per Pauli basis, never
  whole-register bitstrings.

### What this does not prove

"Identical" means two calls returned the same bytes; which worker served
each is not visible, so it is not a cross-machine claim. "Differ" is about
unseeded sampling on `emu` and says nothing about hardware. qdrive's seed may
drive something these runs did not observe.

### Not done, and why

Hardware: no `run_quantum`. A custom engine on Atlas: no `publish_engines`,
and the schema registers a definition only, with the code running on Moth's
workers (inferred from the schema, not observed).

---

## 2026-09-25 - three candidate emulsions, and whether arithmetic decides the grain

Asked: what a crystal field laid by a quantum distribution looks like against
the classical Poisson field atlas-film lays, measured, not described. These
are CLASSICAL SIMULATIONS of quantum distributions; no quantum device sampled
anything.

- **fermion**: 512 free fermions filling the lowest plane-wave modes of a
  periodic 64x64 lattice, a projection determinantal point process, sampled
  exactly by the chain rule;
- **poisson**: 512 sites uniformly without replacement;
- **speckle**: Born-rule shots of a simulated 12-qubit circuit (a random
  circuit on the low bits of two momentum registers, sign-extended, then a
  QFT applied as its matrix, not as gates), the first 512 distinct sites hit.

Command: `python research/2026-09-25/emulsions/grain_proto.py`, then
`render_proto.py`. Host: Windows 11, Intel Alder Lake, numpy 2.2.6 on
OpenBLAS 0.3.29, 12 threads; 8.8 s. Six layouts per stock,
`SeedSequence(20260925)`.

| stock | g(r = 1), mean of 6 | S(k) at the lowest k, mean of 6 | count variance/mean, 16x16 window, mean of 6 | RMS at print scale (Gaussian aperture 1.6 cells), grey levels, the FIRST layout only |
|---|---|---|---|---|
| fermion | 0.469 | 0.076 | 0.180 | 5.70 |
| poisson | 1.018 | 0.815 | 0.778 | 9.45 |
| speckle | 1.733 | 9.357 | 5.518 | 16.73 |

Antibunched, Poissonian and bunched: the fermion field is hyperuniform (S(k)
falls towards zero, and variance grows slower than area), and the speckle
field clusters on the speckle scale. The speckle circuit's M*sum(p^2) was
1.89 to 2.32 against Porter-Thomas's 2. The all-qubit "white" variant was
2.78 to 4.06 at depth 10: not scrambled, so it is not used. The first
layouts' digests: fermion `8f3859e5a44faf1a`, poisson `6ce415b295807d1b`,
speckle `ae91d556415f11a6`.

**A figure corrected.** The first render scaled each print-scale panel's grey
range on its own, which made the smoothest grain look as contrasty as the
coarsest. It was re-rendered on one shared scale before it was shown to the
owner, and the RMS figures above are that render's.

### Does the arithmetic decide the grain?

Command: `python research/2026-09-25/emulsions/precision_proto.py`. The
fermion stock at 32x32 with 128 crystals, 40 layouts, the same uniforms in
every variant, compared as ordered draw sequences against complex128 through
BLAS:

- complex128 with numpy's einsum in place of BLAS: **40/40 identical**;
- complex128 on one OpenBLAS thread in place of 12: **40/40 identical**;
- **complex64 (binary32): 38/40 identical.** The two that parted did so at
  draws 7 and 105 of 128, and afterwards shared only 55% and 86% of their
  crystals.

One flipped draw changes the rest of the film: the samples are equally
valid, and different. Scaling the binary32 rate by the ratio of unit
roundoffs puts binary64 near one film in 10^9 (AN ESTIMATE, not measured).
Very likely identical is not the same promise as identical, and pinned
arithmetic is what closes the gap.

### What this does not prove

Six layouts per stock separate the stocks by an order of magnitude; they do
not pin the statistics to quotable precision. The fermion sampler is the
classical exact algorithm, not a circuit. Nothing here ran on another
machine.

---

## 2026-09-25 - a fermion emulsion tile as a circuit, run by Atlas; and the order Atlas writes its counts in

Asked: can this project's own circuit lay crystals on Moth's platform, and do
the crystals obey the exact law? This entry also **corrects the first
entry's** line "never whole-register bitstrings": every tomography-api-v2
setting returns whole-register strings. With two qubits, as in that probe,
the whole register is two qubits.

### The tile, checked locally

`python research/2026-09-25/emulsions/fermion_tile.py` builds the tile:
- a 4x4 emulsion patch, 16 qubits in snake order, 5 fermions in the 5 lowest
  standing waves of the open box;
- 64 Givens rotations, written in `x`, `ry` and `cx` only: 389 gates, 256 of
  them `cx`;
- QASM of 7,680 bytes, SHA-256 `d701cfb85790c2af...`.

Its own statevector against the exact law, <n_i n_j> = K_ii K_jj - K_ij^2:
max error 1.5e-15 on <n_i> and 1.9e-16 on <n_i n_j>; particle number exactly
5. The check was watched to fail:

| sabotage | max error | verdict |
|---|---|---|
| one `ry` angle +0.05 rad | 1.75e-3 | FAIL |
| one Givens rotation dropped | 0.454 | FAIL |
| one `cx` reversed | 0.553 | FAIL |
| every `ry` angle negated | 1.5e-15 | PASS, correctly |

The first control I chose was the last row, and it could not fail. Negating
every angle conjugates the kernel by a diagonal of signs, K -> SKS, and every
occupation probability is a determinant of K, unchanged by S. It is the same
film, so a control built on it tests nothing. **The stock is defined up to
that gauge, and so is any check on it.**

### On Atlas

- **The run.** tomography-api-v2 job `0082f37b`, 59.8 s, 9 settings of 4,096
  shots. `python fermion_tile.py --atlas`, then `python atlas_tile_compare.py`.
- **The misreading, mine.** Read in plain circuit order, the raw counts
  disagreed with the exact law by up to 11 sigma. The engine's own derived
  observables agreed: one-site |z| at most 1.3; pairs within 1.6, except
  (0, 1) at -2.45. So the reading was suspect, not the physics.
- **Two hypotheses.** Deciding the order from the tile's own data could not
  work: the two candidate orders differ by q -> 15 - q, which is a mirror
  symmetry of this tile. A routing hypothesis, raw strings in physical-qubit
  order, was then falsified by known answers. Rules 1 and 2 below.
- **Known-answer calibrations.** Qubit q is prepared with P(1) = (q + 0.5)/16,
  one level every 0.0625, about 8 standard errors apart:
  1. product state, full list, no two-qubit gates, run twice (jobs
     `93924d11`, `5ad38bfe`): plain Qiskit order, the same both times;
  2. the same plus CZ on every JW-adjacent pair, so a router must act, run
     twice (jobs `e4d62182`, `4cc3c663`): still plain Qiskit order, the same
     both times;
  3. an unsorted partial list `[9, 2, 14, 5]` (job `2e41913f`): the rule below.
- **The rule, `research/2026-09-25/atlas/decode_rule.py`.** In each setting,
  the count string is little-endian over [the setting's non-I qubits,
  ascending] + [every other qubit, ascending]. The setting's label is in
  circuit order. **The order changes from setting to setting within one
  response.** Held to all 9 settings x 16 positions of the known-answer run,
  the worst |z| was 2.49; the control, plain circuit order, scored 316.61.

### Re-scored with the rule

| check | result |
|---|---|
| whole-register layouts, all-Z setting | 4,096, every one with exactly 5 crystals |
| <n_q>, 16 sites | max |z| 2.18, chi^2 13.7 over 16 |
| P(11), all 120 site pairs | max |z| 2.21, chi^2 112.2 over 120 |
| repulsion g, the six named pairs | 0.167-0.889 against exact 0.189-0.958, each within noise |

**Moth's emulator reproduces the fermion emulsion's law, and Atlas can
return whole crystal layouts from this project's own circuit**, provided the
per-setting order is decoded. Six Atlas jobs in this entry: the tile, and
five calibrations.

### What this does not prove

The rule is inferred from four runs and held to one known-answer run. The
engine's code is not visible, so why it orders strings this way is not
known. The 120 pair statistics are correlated, so chi^2 against 120 is
indicative, not a test with 120 degrees of freedom. All of it is `emu`: the
emulator is noiseless, and hardware is untested.

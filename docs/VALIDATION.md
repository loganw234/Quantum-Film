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

---

## 2026-09-25 - the skeleton: the shelf, the authority, the fixer, and a runner that has watched each gate fail

The owner named the project Quantum-Film (MIT) and asked for the skeleton. It
is a ParcelRound P0: the seams every later parcel shares. It is built in the
house style of cft-fp256, HonestFramework and atlas-engine.

### What was built

- **The shelf** (`quantum_film/stocks.py`): one table of stock laws. Every
  parameter is derived or an operator's number with a stated range.
- **The authority** (`quantum_film/golden`): SHA-256 counter-based uniforms,
  plus the exact Pauli and Poisson laws in mpmath at 256 bits. A draw that
  rounding could decide is refused.
- **The Givens circuit**: float64 and independent of the authority.
- **The Atlas client and count-order rule**, promoted from the research
  scripts.
- **The fixer** (`quantum_film/fixer.py`): negative records named by the
  SHA-256 of canonical bytes, checked from the record alone.
- **The front door**: `verify/run.sh`, adapted from HonestFramework's
  gate-runner, behind `make verify-quick` and `make verify`.
- **The rest**: generate-and-check vectors, the docs gate, and the documents.

### Measured

Host: Windows 11, Python 3.12.9, numpy 2.2.6, mpmath 1.3.0, pytest 9.1.1,
ruff 0.11.9.

- `make verify-quick`: 8 of 8 stages pass in 14.1 s.
- `make verify`: 8 pass, and 2 skip by name:
  - `cft`: "libcft is not built";
  - `atlas`: "no Atlas key configured".

  With `QF_ATLAS_AUTH` set, the atlas stage passes against the live
  platform: `features: []`, 31 engines, tomography-api-v2 among them.
- **The authority.**
  - The probabilities of all 4,368 layouts of the 4x4 tile sum to 1 within
    2^-80 (96 bits, 2.7 s).
  - A 16x16 Pauli roll of 25 crystals takes 0.4 s.
  - Seeds 1-4 lay identical rolls at 256 and 320 bits.
- **The frozen golden records' digests.** `pauli-4x4` seed 1:
  `18ebea56f8d7f2b4`; `pauli` seed 1: `5f56d896f8cde98a`; `poisson` seed 1:
  `83a559f3779e48c6`. These are the cross-machine check: `make verify-quick`
  on any other machine regenerates them and compares bytes.

### Controls, each watched to fail

- **Inside the tests** (tests/):
  - a basis scaled by 1.01 breaks normalisation;
  - a uniform forced exactly onto a boundary raises `TieRefusal`;
  - a planted numpy import is caught by the independence check;
  - the three circuit sabotages fail the kernel check (errors above 1e-6);
  - plain count order fails the decode check;
  - a planted broken link and an orphaned document both fail the docs gate.
- **On the runner itself:**
  - one byte appended to a vector made the `vectors` stage fail;
  - a tampered record re-sealed with a fresh digest made the runner print
    `NEGATIVE CONTROL DID NOT FAIL - this runner cannot detect a defect` and
    exit 1;
  - zero tests collected made `pytest-stage` exit 1 (pytest's rc 5).

  Each sabotage was undone by `make vectors`, and the next run passed.

### Found on the way

- **ruff's B905 flagged six `zip()` calls without `strict=`** on the first
  run. In the authority a silent truncation would be a wrong answer, so
  every `zip` there is strict, and a length mismatch now raises. The one
  deliberate offset pair uses `itertools.pairwise`.
- **A CuPy warning in every pytest log came from zarr's pytest plugin.** The
  gates now set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, so no installed plugin can
  touch a verdict.
- **The measured Atlas vector had CRLF endings.** Python's json.dump on
  Windows had written it, and git's normalisation would have made a fresh
  clone fail its own hash. It was re-frozen as LF before the first commit:
  SHA-256 `f28b62d9...`, against `1a69afa8...` for the CRLF copy, with the
  same JSON. `tests/vectors/** -text` now keeps git from touching it.

### Not done, and why

- The cft build and the pinned path: P1 in docs/ROADMAP.md.
- Development through atlas-film: P2.
- The hardware-shaped circuit: P3.
- Speckle's authority: P4.
- A second machine: the missing evidence named in docs/DETERMINISM.md.

---

## 2026-09-25 - P0 finished for round 1: libcft built, the authority held to its own law, device rolls, and a test layout parcels cannot outgrow

The owner asked for three things that evening:
- create the repository and push it;
- dispatch P1-P3 once P0 was finished, and only after a verifier had
  checked P0;
- move atlas-film onto cft-fp256 as P2.

This entry is the P0 that verifier checks. docs/ROUND1.md is the round's
plan.

### Measured

- **The repository.** github.com/loganw234/Quantum-Film is public, with main
  at `eb5068b`. That was confirmed with `git ls-remote origin`, not by
  echoing a local ref.
- **libcft.** The owner's invocation, limited to the `cft.dll` target
  (CLAUDE.md):
  - 8 s, 0 warnings, 0 errors;
  - PE32+ x86-64, 122 `cft_` exports, importing only KERNEL32 and msvcrt;
  - the submodule stays clean, because its build outputs are ignored.

  The `cft` stage now passes: ABI 0.14, and cos(1) = `0x1.14a280fb5068cp-1`.
  It was watched to fail: copies expecting ABI 0.13, or cos(1) one ulp high,
  both exit 1.
- **The authority samples the law it claims.** This had not been tested
  before: the kernel and the sampler's mechanics were, and the law was not.
  - Over 2,000 rolls of the 4x4 tile, chi^2/dof across the 16 one-site and
    120 pair frequencies was **0.943**, against a bound of < 1.6.
  - The control is the uniform Poisson sampler put through the same check.
    It scored **7.052** against a bound of > 2.5, and failed, as it must.
  - 2.9 s.
- **Device rolls.** `fixer.fix_device` requires a job's provenance and a
  commitment, SHA-256(domain | circuit | engine | job | salt), which `check`
  recomputes.
  - Re-attributing a roll by any one of those four breaks the commitment,
    and every field is required.
  - 23 fixer tests.
- **Tests run by directory.** A planted test file outside every stage
  directory is caught by tests/docs/test_registry.py. Packages are
  discovered by setuptools rather than listed.
- **`make verify`:** 9 passed, and `atlas` skipped by name (no key), in
  19.6 s. **`make verify-quick`:** 19.1 s. The docs had said ~15 s and now
  say ~20 s.

### Why each of these was P0 and not a parcel's

- **libcft** is needed by P1 and by P2, and a seam that two parcels need is
  the lead's (ParcelRound METHOD §2).
- **The device-roll format** is the record format, which is lead-owned.
- **The test layout and package discovery** remove the shared files a
  parcel would otherwise edit: a new test file needs no runner edit, and a
  new subpackage needs no pyproject edit.
- **The law test** closes the gap between "the authority's kernel is right"
  and "the authority samples it".

### Found on the way

- The first `cft` check hard-coded its failure messages, and printed "ABI
  0.14, not 0.14" when a sabotaged copy expected 0.13. The check could fail,
  but it could not say why. Each fact is now one constant, read by both the
  comparison and the message.
- A long heredoc carrying backslashes was mangled on its way through the
  shell, and the runner edit it carried failed its own match check before
  anything was written. The edit went through a script file instead, the
  owner's standing workaround.

## 2026-09-25 - the P0 verifier: a run credited to the wrong law, gates that could not fail, and what now makes each one fail

Asked of an independent verifier before any parcel was dispatched, at the
owner's direction: does P0 at `775b5ed` hold? It re-ran every number on a
fresh clone. Its report is in the round's ledger (`verifier-P0.md`), which is
archived with the round. **The authority itself held**: its basis and span,
its law over 50,000 rolls (none on a forbidden layout), normalisation, the
uniforms' encoding, the decode rule and the Givens gauge. What did not hold
is below, the loss first.

### The loss: the Atlas run was credited to the wrong circuit and law

- **The claim**, in the README, STOCKS.md, ROUND1.md, DETERMINISM.md and the
  not-yet-dispatched P3 brief: `givens.py`'s Pauli tile ran on Atlas and
  matched the exact law. ROADMAP's "256 today" rested on it too.
- **What ran** (the lead reproduced the verifier's numbers):
  - Atlas job `0082f37b` ran `research/2026-09-25/emulsions/fermion_tile.qasm`,
    SHA-256 `d701cfb85790c2af...`. That is 64 rotations and 256 cx: an open
    box's standing waves, in snake order. The entry above says so.
  - `givens.circuit(4, 1)`, the `pauli-4x4` stock, is 59 rotations and 236 cx,
    QASM SHA-256 `4ff16974a060b0d4...`. It has run only on a local
    statevector.
- **The same 4,096 layouts**, read through `decode.layouts`:

  | scored against | sites: max \|z\|, chi^2 over 16 | pairs: max \|z\|, chi^2 over 120 |
  |---|---|---|
  | the open box, which ran | 2.18, 13.7 | 2.21, 112.2 |
  | golden `pauli-4x4`, the shelf's law | 10.01, 521.2 | 20.20, 5328.3 |

- **So the shelf's Pauli law has never run on Atlas.** P3's first job is its
  first run. The five documents are corrected, and `givens.py`'s docstring
  says so.
- **How it happened.** The research tile was "the fermion tile"; the shelf's
  stock became "the 16-qubit tile" later, and the documents joined the two by
  name. A score is against one law, so the circuit's SHA-256 now goes beside
  every score (CLAUDE.md, Atlas item 8).
- **Two counts were wrong with it.** `givens.py` claimed N*M - N(N+1)/2
  rotations (65 here). It skips entries that are already exactly zero, so it
  lays 59. ROADMAP's "about 96 CNOTs" for the 2-CNOT layout is 55 rotations
  and 110 CNOTs.

### Gates that could not fail, and what now fails them

Each fault was planted in a scratch copy of the fixed tree, and each was
refused.

| finding | what passed before | the gate now | planted, and refused |
|---|---|---|---|
| 1, the law test | a sampler that skips one projection update: chi^2/dof 1.203 < 1.6, while 18% of its rolls lay on forbidden layouts | no roll may lie on one of the 1,360 layouts with det(K_Y) = 0 (allowed det >= 2.4e-4; forbidden \|det\| <= 6.5e-19). A float copy of the chain rule must first lay the authority's own 2,000 rolls exactly (it does, 2,000 of 2,000); then two planted bugs must fail | "stale-last" in the copy: 366 of 2,000 forbidden; "half-update": 125. "stale-last" planted in the authority itself: 2 tests fail |
| 2, the 256 vs 320 bits test | the refusal removed; a margin of 0; a margin of 2^-255 | the premise measured draw by draw at 512 bits (worst error 2^-248.8; headroom 2^24.8, where 2^16 is demanded); a target planted 2^-240 past a boundary must be refused, and 2^-200 past must be decided | refusal removed: 2 fail; margin 0: 3 fail; margin 2^-255: 2 fail |
| 7a | `--only ""` ran zero stages: PASSED | refused, rc 2; zero stages run is FAILED | rc 2 |
| 7b | `--resume` from one dirty tree to another: PASSED over a failing authority | `--resume` refuses any dirty tree | rc 2 |
| 7c | two runs in one second shared `.ok` markers | pid in the run id; a fresh run refuses an existing directory | two concurrent runs, two directories |
| 7d | a fixer command line that refused every record passed the control | a twin stage, `fixer-cli`, must accept the generated records, and the control must fail naming the digest | refuse-everything: `fixer-cli` FAIL. A crash on the tampered record: `controls` FAIL, "not with digest" |
| 7e | a test that skipped inside a stage passed it, unseen by `--require-all` | a skipped, xpassed or deselected test fails its stage | a planted `skipif(True)`: `golden` FAIL |

**Found on the way, by the lead: the runner could not see a dirty tree
under `MSYS_NO_PATHCONV=1`.** CLAUDE.md sets that for Atlas work, and with it
`git -C /c/...` failed silently. Every run was then "nogit" and never dirty,
so 7b's new guard could not fire. git now runs from inside the tree, and a
tree whose `.git` git cannot read is refused.

### Claims with nothing behind them, now held

- **6a.** A file with two `crystals` keys was accepted with the genuine
  digest. A record on disk is now exactly `fixer.text(record)`, and a
  duplicated key is refused by name.
- **6b.** The digest covers the package version, so a version bump made
  `reproduce()` reject correct rolls. `reproduce` now compares the roll
  (stock, law, stream, crystals). DETERMINISM.md names the version.
- **6c.** `fix_device` sealed `[0.7, 1.2, 4.0, 11.5, 13.9]` as
  `[0, 1, 4, 11, 13]`. The constructors now refuse non-integers and a
  non-integer seed, and `fix` refuses whatever `check` would.
- **6d.** The commitment joined free text with a bare `|`, so an engine and a
  job could be re-attributed together. It is now `quantum-film/commitment/v2`:
  length-prefixed and type-tagged (golden.uniform's `stream` encoding), and
  binding the stock, the shots and the decode rule too. No v1 device roll was
  ever fixed.
- **The fixer's minor findings.**
  - A golden stream must be `["roll", stock, <int>]`.
  - A golden roll carries no wall-clock time.
  - The law is compared as JSON, so `true` is not 1.
  - An unexpected top-level field is refused.
  - A malformed record is refused by name, and the next file is still
    checked.
- **8c.** Seven research scripts called Atlas when imported. They now refuse
  import, and tests/docs/test_atlas_guards.py fails any script that does not.
  **On its first run, the gate found an eighth: `tools/atlas_smoke.py`, the
  lead's own.**
- **8d.** The registry now finds `*_test.py` as well as `test_*.py`.
- **8f.** Seven stale test paths. A new rule in tools/check_docs.py fails any
  repository path named in plain text that does not exist. Before the fix it
  listed exactly those seven.
- **8g.** The client's refusals now have offline tests (tests/client/, a new
  stage), with a positive twin. **Found on the way:** the client compared the
  host but not the scheme, so `http://api.mothquantum.com/...` would have sent
  the key in clear. The scheme is now compared, and the new test failed on the
  old client.
- **8h.** libcft natively, at binary64 through cftmpfr: cos 0.236 ms and exp
  0.119 ms per element (the lead; the verifier measured 0.211 and 0.110). The
  0.4 ms figure was WASM.
- **The verifier's own additions (11).**
  - The `cft` stage checks the DLL that `QF_CFT_ROOT` names, and prints its
    path and SHA-256. Two builds of the same source differ in hash
    (`23f0f2e6...`, `6ca569a8...`).
  - Each of the authority's draws checks mpmath's process-global precision
    (`PrecisionChanged`).
  - `build.log` is ignored.

### Not changed, and why

- **A device roll on a forbidden layout is kept.** A device records what it
  laid, noise included, and P3 counts such layouts as a witness of noise.
- **The fixer cannot tell which law a device roll's circuit lays.** The
  commitment binds the circuit's hash, not its law. fixer.py and
  DETERMINISM.md say so.
- **The decode rule was inferred from, and held to, the same known-answer
  run.** Its one use outside that run rests on the tile's physics. The entry
  on it above already says so.
- **The authority is not made thread-safe.** It refuses when its precision
  moves.

### What this does not prove

The planted faults are the ones named here; a gate can still miss a fault
nobody planted. One CPU so far.

`make verify`: 12 passed, none skipped (the live Atlas smoke included),
33.4 s. `make verify-quick`: 10 passed, 28.6 s, with P2 running on the same
desktop.

## 2026-09-25 - the P0 verifier's re-check: three of the new gates missed a fault they claimed, and a resume crossed a changed DLL

Asked of the same verifier after `b0e9ed1`: do the fixes hold? **All 21 of its
findings were fixed as found.** It then found four new defects, three of them
in the gates written to answer it, and five minor ones. Its entry is in the
round's ledger (`verifier-P0.md`, 22:59Z).

### The loss: a premise gate that compared the authority with itself

- **The gate compared the 256-bit authority with itself at 512 bits.** An
  error that does not depend on the working precision cannot show between
  the two.
- One binary64 `math.fsum` in the new basis vector's norm put every boundary
  2^-51.5 to 2^-52.9 from the clean authority's. The gate reported 2^-249,
  and every executed stage passed.
- So the previous entry's "the premise measured draw by draw at 512 bits
  (worst error 2^-248.8; headroom 2^24.8)" was a measurement of the code's
  agreement with itself, not of its error. **It is withdrawn.**
- **Now** (tests/golden/test_golden_premise.py), two references that share no
  code with the authority:
  - **pauli-4x4, exactly.** cos(2 pi m / 4) is 1, 0 or -1, so the kernel is
    rational (entries k/16). Every weight c_i = K_ii - K_iS K_SS^-1 K_Si,
    every boundary and every target is an exact Fraction. Over 20 rolls the
    authority's worst error is **2^-252.4**, and its rolls equal the exact
    ones.
  - **pauli (16x16), an independent chain rule at 512 bits.** It uses the
    closed-form kernel and Schur complements grown one Cholesky column per
    draw. It shares neither `orbitals()` nor `sample()`. Worst error
    **2^-249.2** over 2 rolls.
  - The two references agree with each other on 4x4 to below 2^-500. Rows of
    the basis's kernel match the closed form at 512 bits, on both tiles.
  - The gate demands 2^16 of headroom below the 2^-224 margin.
- **Planted, each in a scratch copy:**

  | binary64 slip | the premise gate | the source rule |
  |---|---|---|
  | the basis vector's norm (`math.fsum`) | caught | caught |
  | the update coefficient | caught | caught |
  | the Gram-Schmidt coefficient | caught | caught |
  | the basis's cosines (`math.cos`) | caught | caught |
  | the initial weights | inert | caught |
  | each draw's total | inert | caught |

  The inert pair change no output on today's shelf. K_ii = N/M is dyadic when
  L is a power of two, and each total is the integer N - j, so their binary64
  roundings are exact. No output gate can see them, and on a stock with
  another L they would decide rolls. So tests/golden/test_independence.py now
  reads the rule from golden's source: no float literal, no `float()`, from
  `math` only `floor`, `ceil`, `comb`, `gcd` and `isqrt`, and no `cmath`,
  `statistics`, `random` or `decimal`.

### The other three new defects

- **The cached basis.** `orbitals()` never checked its precision, so a basis
  built while another thread held 53 bits was cached and served every later
  roll. It now checks before returning, so a refusal also keeps the basis out
  of the cache; `kernel()` and `probability()` check too. Planted (a cosine
  that drops the precision): refused by name, and the cache stays empty.
  Removing the check fails that test.
- **The guards gate read a few import spellings.** Seven others passed it:
  - a dotted `import quantum_film.atlas.client`;
  - a star import;
  - `from . import client`;
  - an import inside `try`;
  - a call in a class body, in a decorator, or in a default argument.

  Now two rules.
  - Rule 1: a script under research/ or tools/ that imports a client in any
    form must refuse import. Modules other scripts import (research's probe.py
    and fermion_tile.py) are exempt, and rule 2 holds them.
  - Rule 2: no module calls a client in code that runs at import. It reads
    dotted, relative and star imports, nested blocks, class bodies,
    decorators and default arguments.

  All seven shapes are the gate's own negative controls. Removing class
  bodies from rule 2 fails the gate.
- **`--resume` crossed a changed `QF_CFT_ROOT`.** A resumed run reported cft
  passed for a DLL that failed a fresh run. A fresh run now writes
  `environment` beside its markers: QF_CFT_ROOT, the DLL's SHA-256, python,
  mpmath and numpy, and whether an Atlas key is set (never the key). A resume
  in another environment is refused. Planted: a text file as the DLL, then
  `--resume`: refused by name, rc 2. The same DLL resumes, with cft cached.

### The minor ones

- **Every stage skipped** reported PASSED. A skip is not a run: it now FAILS.
  Planted: `--skip` of all 12 stages exits 1.
- **The runner walked up** to an enclosing repository and stamped its
  commit. A tree that is not its own git toplevel is now "nogit". Planted: an
  export inside another repository runs as `...-nogit`.
- **`PYTEST_ADDOPTS=--ignore=...`** passed golden on 35 of its 40 tests.
  pytest-stage.sh clears PYTEST_ADDOPTS and PYTEST_PLUGINS. Planted: golden
  ran 46 of 46.
- **`check` did not read inside a golden roll's `authority` or `code`.** A
  wall-clock time rode in either, and an authority naming the wrong sampler
  passed. Both are held now to exactly what `lay()` writes, from one function,
  `fixer.authority(law)`.
- **`fixer lay STOCK 1.9`** ended in a traceback. It now refuses by name.

### Corrections to the previous entry

- "Two builds of the same source differ in hash": they differ in exactly
  three fields, the COFF and export-directory TimeDateStamps and the PE
  CheckSum. A hash with those zeroed would pin a build. "Not pinned by hash"
  was a choice, not a necessity.
- 8f's docs rule listed eight stale paths on 775b5ed's tree, not "exactly
  those seven". The eighth was the P3 records directory ROUND1.md planned
  for 2026-09-26, not yet made.
- The stray clone in the lead's tree was the verifier's first WSL command.
  `wsl.exe` hands its command line to WSL's shell, which expanded `$D` to
  nothing, so git cloned into the directory WSL started in. Found and
  explained by the verifier itself.

`make verify` with `--require-all`: 12 passed, none skipped, 30.6 s.

## 2026-09-26 - the P0 verifier's third pass and verifier-P3's fixer findings: an allowlist for imports, a tile that is not accidentally exact, and a commitment bound by its anchor

Asked of the P0 verifier after `5fe9741`, and found on the way by verifier-P3.
The lead's fixes held as far as they reached. Five new defects, and three of
verifier-P3's in the fixer. Their entries are in the round's ledger
(`verifier-P0.md` 00:25Z, `verifier-P3.md` 00:39Z).

### The regression first: the runner refused every clone under %TEMP%

- 5fe9741's toplevel check compared two spellings of the tree's path. Git
  Bash mounts %TEMP% at /tmp, so every clone there, where the verifiers
  work, stopped with "git cannot read the repository". Both verifiers hit it.
  It was loud, not a false pass.
- Fixed at 900b9e5, pushed ahead of the rest: `git rev-parse --show-cdup` is
  empty exactly at the toplevel and needs no spelling.
- Held from both spellings of a clone under %TEMP%. An export nested inside
  another repository still runs as "nogit".

### Binary64 spelled another way

- **The finding.** Seven respellings passed all 46 golden tests:
  - int/int division (`2 / M`, `m / L`);
  - `len(r) / M`;
  - `import math as _m`;
  - mpmath's `fp` context;
  - `__float__`;
  - a binary64 total.

  On the shelf's tiles (L = 4 and 16) each rounds to the exact value.
- **The fix is an output gate on a tile whose arithmetic is not accidentally
  exact.** cos(2 pi m / L) is rational for every m only when L is 1, 2, 3, 4
  or 6 (Niven's theorem). L = 6 with r2 = 1 has N/M = 5/36, which is not
  dyadic.
  - An exact Fraction reference there gives the clean authority 2^-251.0
    over 10 rolls.
  - Each of the verifier's six respellings, planted in a scratch copy, fails
    it: `2 / M`, `m / L`, `len(r) / M`, the weights via an alias, via
    `__float__`, and the total via an alias.
  - The 16x16 independent reference stays. A cosine table rounded to binary64
    is exact on L = 6, whose cosines are dyadic, and shows at 2^-51 on 16x16.
- **The source rule** also refuses a `math` alias, mpmath's `fp`,
  `__float__`, `importlib` and `__import__`. Its docstring now says it reads
  spellings and cannot see int/int division, which the L = 6 gate does.

### A refusal on one side of a boundary

- Checking the margin after the choice decided a target 2^-240 below a
  boundary, and passed every gate: the planted near-ties were all at or
  above one.
- The mirror plant, 2^-240 below the boundary after site 0, must now be
  refused. Planted (the reordering), it fails.

### Import: an allowlist, not a list of spellings

- **The finding.** The two-rule guards gate was walked past by:
  - a wrapper module;
  - an alias (`fetch = client.call`);
  - `getattr`, `importlib`, curl called directly;
  - a function-local import, and an annotation.

  Its library exemption was keyed on 28 bare import names, stdlib included,
  and exempted any file with such a stem.
- **Now.** Every module under research/, tools/ and quantum_film/ either
  refuses import, or runs at import only an allowlist:
  - pathlib.Path and its resolve/with_name/joinpath/absolute;
  - re.compile, functools.lru_cache, sys.path.insert, os.environ.get;
  - a few builtins the module does not rebind;
  - its own functions that call only these.
- **No exemptions.** Class bodies, decorators, defaults, annotations and
  module-level blocks are read; lambda bodies and main guards are not.
- **Every shape that once passed is a negative control in the gate** (16 of
  them). The verifier's three real planted files each fail the docs stage.
  The wrapper library itself passes, correctly: it only defines a function.
- **The tree held to it.** Six research scripts that do their work at import
  now refuse import:
  - compare2.py and export_records.py, which rewrote records when imported;
  - atlas_tile_compare.py, precision_proto.py, render_proto.py and
    selwyn_dpp.py.

  So does tools/cft_smoke.py. grain_proto.py, which precision_proto imports,
  makes its output directory in main(), not at import.

### The resume fingerprint, and the cached basis

- **The fingerprint.** It now records the cftmpfr binding's hash and the
  ruff and pytest versions. A binding changed after a run fails the resume
  by name. Before, a one-ulp break there resumed as PASSED.
- **The cached basis.** A transient precision drop, one that comes and goes
  between two checks, cached a corrupted basis 26 times in 40. The basis now
  checks its content before it is cached: every row's squared norm must be
  N/M to 2^-(prec - 16). Planted with a binary64 square root: refused, and
  the cache stays empty. Removing the check fails that test.

### The fixer (verifier-P3)

- **The commitment claimed more than it binds.** The salt is in the record,
  so a re-attributed roll with its commitment recomputed passes `check`
  (verifier-P3's A11 and A12). The docstring's "cannot be re-attributed
  without the refusal naming it" was false. It now says what binds is the
  anchor: the commitment committed to git before the job's first status
  call. A test pins that the record alone passes such a forgery.
- **`kind`, `fixed_at` and `occurrences` are bound by no commitment.**
  - An emulator roll re-sealed as `qpu` passed.
  - `occurrences` is now a known field, a whole number of shots from 1 to
    `shots`.
  - An unknown source field is refused, since it would ride unchecked.
  - `fixed_at` must be a UTC time.
  - Binding `kind` needs a commitment v3, since P3's rolls are anchored in
    v2. It is left for the next round, and the docstring says so.
- **A device roll no longer has to lay the law's crystal count.** A QPU's
  leaked layouts were unfixable, against "a device records what it laid".
  A golden roll is still held to the count.
- **`fixer lay` with an unknown stock** refuses by name.

### Recorded, not fixed

- The timing of P3's commitment rests on the code and the local clock. The
  server records no completion time, and nothing third-party timestamps the
  commit (verifier-P3's D2). Pushing the commitment before the first status
  call, or putting its hash in the job request, would make the evidence
  external.

`make verify --require-all`: 12 passed, none skipped.

### Correction, the same day: the import allowlist named functions, and would have refused the parcels

- Checked against P1's and P3's branches before either merged, the
  allowlist above refused their pure module-level constructors: `np.dtype`,
  `Fraction`, `dataclass` and `field`, `float.fromhex`, `math.sqrt` and
  `np.array`.
- It now allows modules, not functions: anything in math, fractions,
  dataclasses, typing, enum, collections, itertools, functools, operator, re,
  struct, hashlib, mpmath, and numpy apart from its file functions (load,
  save, fromfile, ...). Also float.fromhex, int.from_bytes and bytes.fromhex.
- Two more negative controls: `np.load` at import, and a client imported
  under a pure module's name (`from moth import call as math`).
- Every new module on both parcel branches now passes. The files the rule
  still refuses there are the research scripts of their base, which main has
  since guarded.

## 2026-09-26 - the status call carries the result, the decode rule has one name, and test basenames are unique

Three things the parcels found that belong in P0's files, landed while their
branches are checked:

- **A completed job's status response carries its whole result** (P3, on
  jobs 9e04918d and 8586f1cc). So a device roll's commitment is committed
  after the POST and before the first status call. `client.run_job` polls at
  once, and its docstring now says it never runs a device roll. docs/ATLAS.md
  says so too.
- **The decode rule's name has one home.** `decode.DECODE` is
  `quantum_film.atlas.decode/v1`, the string P3's records bind in their
  commitments. A change to the rule is a new name, never an edit under the
  old one.
- **No two test files share a basename.** The test directories are not
  packages, so pytest imports each file under its bare basename. P1's
  `test_uniform.py` beside golden's stopped one session over tests/
  (`make test`) at collection, while each stage, run alone, passed.
  - tests/docs/test_registry.py now fails any clash, with a planted clash as
    its control.
  - main and both parcel branches have none.
  - One session over tests/ on main: 127 passed.

## 2026-09-26 - the P0 verifier's fourth pass: imports checked by behaviour, the kernel held to its closed form, and times read as times

Asked of the P0 verifier after 73a79af. Every fault it had planted before
fails now. Its entry is `verifier-P0.md`, 04:12Z. Five defects:

- **The import allowlist did not hold.** Five lint-clean modules passed
  the whole front door and, imported, wrote a file or ran a subprocess:
  - a bare decorator, and `__init_subclass__`;
  - `operator.call(subprocess.run, ...)` and `itertools.starmap(...)`;
  - a rebound `math`.

  Seventeen more shapes carried an Atlas call past it, among them
  `import antigravity`, which opens a browser. A reading of the source
  cannot close calls with no call expression, impure callables handed to
  pure modules, rebinding by assignment, or import statements.

  **Now the rule is checked by behaviour.** tests/docs/import_audit.py
  imports every module under research/, tools/ and quantum_film/ in a child
  process under a PEP 578 audit hook. The hook stops, before it happens, and
  names any subprocess, socket, browser, native load, or file or directory
  write.
  - The tree: 19 modules import cleanly, and 15 scripts refuse import.
    There are no effects and no errors.
  - The negative controls are nine planted effects: the verifier's five
    executed shapes, antigravity, a socket, a mkdir, and curl. Each is
    stopped and named, and nothing is written. A tools/ module running a
    subprocess through `operator.call`, planted in a scratch copy, fails
    the docs stage.
  - P1's and P3's new modules pass it. P1's libcft shim loads its DLL
    lazily, not at import.
  - Its limit is stated in the gate: it sees the branch an import takes on
    this machine.
- **The basis content check saw norms only.** A drop confined to the angles
  keeps cos^2 + sin^2 = 1. The verifier cached such a basis with its kernel
  2^-56 off. The basis now also holds three kernel entries to the closed
  form, from cosines computed afresh. Planted (the first L cosines and sines
  of the build taken at an angle off by 2^-53): refused, and not cached.
  With the check removed, that test fails.
- **The resume fingerprint left out the import path.** With
  `PYTHONSAFEPATH=1` a fresh run fails golden, and a resume passed it. The
  fingerprint now records PYTHONPATH, PYTHONSAFEPATH and PYTHONHOME, a hash
  of every installed distribution's version, and the machine. Planted: a
  resume with PYTHONSAFEPATH set after the run is refused.
- **`fixed_at` was a shape.** Month 13 and Arabic-Indic digits passed. It is
  now ASCII digits that parse as a real time (2026-02-30 is refused), and a
  local-emulator roll is held like a device's: fixed_at a real time, and no
  unknown field. With the parse removed, the test fails.
- **CLAUDE.md's import paragraph** named the old function allowlist. It now
  names the audit hook and its limit.

verifier-P3 re-checked P3's fixes (961b385) the same hour: READY TO MERGE.

## 2026-09-26 - P3 merged: the shelf's Pauli law ran on Atlas as a hardware-shaped circuit, and holds

P3's branch (6130b39 to 961b385) is merged at 63a831e, after verifier-P3's
re-check (READY TO MERGE, `verifier-P3.md` 04:18Z). Every figure below was
re-run by verifier-P3, sharing no code with P3.

- **The circuit.** `quantum_film/circuits/givens_line.py` is the (M - N)N
  layout on the Jordan-Wigner line.
  - pauli-4x4: 51 Givens rotations in 15 layers. Four of the 55 places are
    structural zeros: every entry examined is at most 6.5e-17 or at least
    0.25.
  - 102 CNOTs, all between neighbours; depth 62, and 30 counting CNOTs only.
  - Against golden's kernel on a local statevector: 4.8e-15. Over all 4,368
    layouts, 3.6e-17.
  - Every rotation dropped in turn fails the kernel check; the smallest
    error is 0.1875.
- **The run.** tomography-api-v2 job 8586f1cc, 4,096 shots, circuit
  `ed767c01bd4b851d...`. Read only through `decode.layouts`:
  - every layout held 5 crystals;
  - one-site max |z| 1.48 (chi^2 9.8 over 16), and pairs max |z| 2.52 (chi^2
    112.3 over 120);
  - the whole distribution over the tile's 53 symmetry orbits: chi^2 33.7
    on 33 degrees of freedom (verifier-P3);
  - 0 of 4,096 shots on the 1,360 layouts the law forbids.

  The engine's own <XX> and <YY> on sites 0 and 1 (0.3755 and 0.3687
  against 0.375, the sign pinned) show a coherent state. A mixture with the
  same layouts would give 0. The engine's <ZZ> equals decode's reading of
  the same strings exactly (verifier-P3).
- **The records.**
  - 1,995 device rolls, one per distinct layout, with `occurrences` summing
    to 4,096. Each passes the fixer, main's included.
  - The commitment (434c705) was committed after the POST and before the
    first status call. That ordering is shown by the code, with only the
    local clock to date it: the server records no completion time, and
    nothing third-party timestamps the commit.
  - A completed job's status response carries the whole result, so the
    ordering has to be before the first status call, not merely before the
    result fetch.
  - The QASM is committed beside the commitment, since its text depends on
    atan2. The platform that wrote it (Python 3.12.9, numpy 2.2.6, ucrtbase)
    is recorded beside it.
- **At the merge, the lead also landed:**
  - `pauli_tile.DECODE` taken from `decode.DECODE`, so the rule's name has
    one home;
  - 51 and 102 in ROADMAP.md, givens.py's docstring and STOCKS.md, where
    this ledger's earlier entry said 55 and 110 (the generic bound);
  - the Atlas result in README.md, STOCKS.md and DETERMINISM.md;
  - circuits/__init__.py naming both circuits' tests.
- **Left open (verifier-P3's minor items):**
  - no test holds `--score`'s exit code, and its audit ignores the platform
    record;
  - `fixed_at` has no upper bound;
  - a forgery that keeps every committed file consistent passes by design:
    git history is the anchor.
- One Atlas job of the six allowed was used.

The merged tree: `run.sh --require-all` 12 passed, none skipped. All 1,995
rolls pass the fixer. One pytest session over tests/: 180 passed.

## 2026-09-26 - P1 merged: the Pauli law in binary64 on libcft, the authority's roll by construction

P1's branch (e65e98c to b7cb207) is merged at a389653, after verifier-P1's
fourth pass (READY TO MERGE, `verifier-P1.md` 06:50Z). The lead's
integration is 04fe2fe. Figures marked (v) were re-run by verifier-P1 with
scripts of its own.

- **What it is.** `quantum_film/pinned` lays the Pauli law in binary64 on
  libcft, cft-fp256's C library, through a ctypes shim. Every operation that
  rounds is a libcft call.
  - The certificate encloses the EXACT chain rule by directed rounding. A
    draw is decided only when the target's enclosure clears every boundary
    by TAU = 2^-200, which is 2^24 times the authority's margin.
  - A roll with any draw it cannot certify goes whole to golden, whose
    refusals propagate. golden's first draws must be the certified ones, or
    the path raises `EnclosureBroken`.
  - The projections are bounded through Q = A^T T and a certified F < 1 on
    Q^T Q - I. An interval Gram-Schmidt widened 2.5-3x a draw on the 16x16
    stock, to 1.3e-4 by draw 24, and would have handed off nearly every roll.
  - The tile edge must be a power of two, so the angles are dyadic; another
    edge is refused by name.
- **Equality.** 2,300 pauli-4x4 rolls (seeds 1-2,000 and 9,001-9,300) and
  740 pauli rolls (seeds 1-700 and 9,001-9,040) equal the authority's, and
  none was handed off.
  - The tightest clearance was 2.0e8 enclosure widths on pauli-4x4 and 2.1e5
    on pauli.
  - verifier-P1 (v): 600 of 600 and 60 of 60 equal, and no exact value
    outside the enclosures on 300 streams.
- **The named control.** On 6 of 6 streams, a target was planted inside
  binary64's own error, 2.8e-17 to 3.4e-16 from a boundary (relative). With
  the hand-off removed each roll disagrees with the authority; as shipped,
  each agrees, handed off at the planted draw. The brief's plant, about
  1e-14 from a boundary, could not fail: binary64 decides it right (P1,
  2026-09-25 23:17Z).
- **Precision, plain round-to-nearest.** No random roll parted at any
  format: binary32 on 5,800 rolls, binary64 and binary128 on 2,300.
  - The worst error in (boundary - target), in units of u: binary32 4.6e-7,
    binary64 1.7e-15, binary128 1.3e-33.
  - Random targets came no closer than 1.2e-6 to a boundary.
  - Planted on a ladder of distances, each format parts inside its own error,
    on the side its error points to.
  - The 2 of 40 binary32 films of 2026-09-25 above were a 32x32 research tile
    with 128 crystals. P1's report called it the 64x64 prototype; the entry
    above says 32x32.
- **Timings.** They were taken on a throttled desktop, where processes got
  0.22-0.61 of a core, so the ratios are the figures. The certified roll
  takes 0.62x the authority's wall time on pauli (0.69x CPU), and 3.5x on
  pauli-4x4. There its 302 libcft calls a roll make call overhead dominate.
- **What sees a faulty certificate.** Equality did not. 10 of 11 faults
  planted in the certificate passed equality, exact containment and the
  control, and each fails a step test. Each step is held to exact rationals
  on tight inputs, where only its own roundings separate its bound from the
  exact value. Every directed call flipped to its other direction fails its
  step (the mutation gate).
- **verifier-P1's four passes.**
  1. 04:32Z. Five defects:
     - a refusal after a hand-off came back misnamed;
     - six one-ulp faults in the wrong direction passed every gate, because
       wide boxes hid the slack;
     - six respellings passed the source rule;
     - the caches were writable;
     - a non-bytes stream was accepted.
  2. 05:38Z: seven new faults passed every gate, and five respellings passed
     the new allowlist.
  3. 06:24Z: the end-to-end check read the position `decide` traced, not the
     one it returned. A two-line fault, a decision certified without its Gram
     factor and traced honestly, passed every gate and 300 of 300 equal rolls,
     while certifying the wrong site on a tight input.
  4. 06:50Z: READY TO MERGE. The check now holds the returned decision, with
     targets planted either side of every boundary on family G's first three
     plans. N3b gives 317 problems there, and so does its respelling past the
     rule (v).
- **Stated limit** (certificate.py). The source rule reads spellings. Inside
  a step, the tight check sees any rounding on its inputs. In the
  orchestration, a fault passes only if it is spelled past the rule AND moves
  none of the end-to-end check's claims on that check's inputs.
- **Left open** (verifier-P1's minor items):
  - N3m. It returns the unsound decision only where the Gram bound F is below
    2^-40, and passes every gate: family G's F is about 2^-36, so no planted
    target reaches it. On a family off orthonormal by 2^-44 it certifies 2
    wrong sites. It lies inside the stated limit. A laddered family with a
    smaller F would narrow it (believed, not tried).
  - A field added to Located passes the class-shape rule. It cannot pass
    silently, since Located's construction would then fail on every roll.
- **At the merge, the lead also landed:**
  - `pinned` in the Makefile's help and in README's and CLAUDE.md's budget
    lines;
  - P1's duplicate basename check removed, since tests/docs/test_registry.py
    holds it for every directory;
  - ROUND1.md: a roll is handed off whole, not per draw;
  - DETERMINISM.md: the pinned path, its checks and its gap;
  - README: the pinned path, and the binary32 figure's tile;
  - ROADMAP: P1 merged;
  - CLAUDE.md: equality cannot see a faulty certificate.

The merged tree at 04fe2fe:
- `run.sh --require-all` (run 20260925-234943-9312-04fe2fe): 13 passed,
  none skipped, 51 s;
- the quick budget at a389653: 11 passed, 56 s, with a verifier running
  beside it;
- one pytest session over tests/: 537 passed. That is 539 less the two
  duplicate basename tests.

## 2026-09-26 - corrections to the P1 entry: two labels copied without their definitions

The P0 verifier's fifth pass found the first (`verifier-P0.md` 07:09Z). The
lead found the second while checking it, in the same table's source.

- **"The worst error in (boundary - target), in units of u: binary32 4.6e-7,
  binary64 1.7e-15, binary128 1.3e-33" is false as stated.** Beside a format,
  "u" reads as its unit roundoff. Read that way, binary32's worst error would
  be about 2.7e-14, below binary32's own rounding.
  - The figures are (boundary - target) / (N - j), the error as a fraction of
    the weight left to draw. That is the scale of the uniform the target is
    drawn from, and P1's measuring script calls it "units of u". The entry
    copied the label without its definition.
  - In each format's unit roundoff they are about 7.7, 15.3 and 13.5.
  - The P0 verifier measured the absolute errors with P1's plain chain over
    40 pauli-4x4 streams: 4.97e-7, 1.07e-15 and 6.42e-34. Those are 8.3, 9.7
    and 6.7 unit roundoffs.
  - "Random targets came no closer than 1.2e-6 to a boundary" is on the same
    scale: a fraction of the weight left to draw.
- **"2.8e-17 to 3.4e-16 from a boundary (relative)" mislabels absolute
  distances.** In P1's control table the first figure is the absolute
  distance, and the bracketed one is relative to the boundary's value
  (`report_control` in quantum_film/pinned/measure.py). Relative to the
  boundary, the six plants lie 3.0e-17 to 4.1e-16 from it.
- The README's sentence on random targets now says "of the weight left to
  draw" where it said "relative". CLAUDE.md drops a 2 us ctypes figure that
  P1 had not measured as stated (the verifier's minor).

## 2026-09-26 - five more Atlas runs of the shelf's law, for a print laid by Atlas

At the owner's word, the throwaway key's last five jobs were spent before it
expires (about 17:25Z).
- They used the same circuit (givens_line, `ed767c01bd4b851d`) and the same
  tool (tools/pauli_atlas_run.py), with 4,096 shots each.
- They were submitted from 11:46:31Z to 11:51:53Z.
- Each commitment was committed, on a branch, before the job's first status
  call. As for 8586f1cc, only the local clock dates that.

| job | distinct layouts | one-site: max \|z\|, chi^2 over 16 | pairs: max \|z\|, chi^2 over 120 | forbidden | engine's <XX>, <YY> on (0, 1) |
|---|---|---|---|---|---|
| 579df87d | 1,997 | 2.53, 19.9 | 2.73, 138.5 | 0 | +0.3955, +0.3599 |
| d017540c | 2,027 | 1.72, 9.8 | 2.14, 84.1 | 0 | +0.3740, +0.3560 |
| 5831ff5e | 2,026 | 2.33, 19.1 | 2.52, 147.2 | 0 | +0.3740, +0.4097 |
| 3673f9fe | 2,006 | 2.66, 24.6 | 2.84, 131.7 | 0 | +0.3779, +0.3408 |
| 933138bc | 2,020 | 3.14, 34.0 | 3.11, 181.2 | 0 | +0.3652, +0.3818 |

- **Pooled with 8586f1cc** (24,576 shots):
  - 3,004 distinct layouts, of the law's 3,008 allowed;
  - one-site max |z| 2.15, chi^2 17.1 over 16;
  - pairs max |z| 2.64, chi^2 128.0 over 120;
  - no forbidden layout.

  The one-site z's are correlated, because every layout holds five crystals,
  so one run's sum of squares is not chi^2 with 16 degrees of freedom.
  933138bc's 34.0 does not survive pooling.
- **The records.** 10,076 device rolls were fixed, and the fixer's command
  line accepts each. `--score` audits all six runs: ALL CHECKS HOLD.
- **A test assumed one run per directory.** tests/circuits/test_p3_records.py
  held the platform record's code commit equal to each run's.
  - Runs 2-5 each started after the previous run's results commit. They
    wrote the same QASM file, and the tool writes its platform record once.
  - The quantum_film code is identical at all five commits.
  - The check now asks that the record name the commit of a run that wrote
    that file. A planted record naming another commit fails it for all five.
- All six of the Atlas account's jobs are now used.

## 2026-09-26 - the first prints: rolls laid as sheets of film, developed through atlas-film's pinned mode

The owner's word: the lead builds round 2's seam and the first prints alone, and
one verifier pass follows. atlas-film is vendored as a submodule at d4007b2, its
pushed pinned branch.

**A spike first**, in scratch.
- Pauli tiles were stacked in layers, and the sheet went through atlas-film's
  pinned `sheet=` path beside a Poisson twin: 11,776 rolls in 233 s on ten
  workers, for 128 x 128 cells.
- It found what shapes the design:
  - atlas-film coats about 9 crystals in each column even at TRI-X's honesty
    floor, so a site cannot be a cell's only crystal, and the depth needs
    layers;
  - a sheet of independent fixed-count tiles suppresses S(k) above the tile's
    scale for ANY law. The Poisson twin measured 0.024 at the lowest k,
    against Pauli's 0.016.

**The seam** (quantum_film/develop.py).
- A cell is one site. Each layer of the emulsion's depth is one roll of every
  tile.
- Every layer's grid is offset, and every crystal gets a 16-bit threshold,
  both from the golden uniform on the print's stream.
- The pitch is derived from the layer count, so the borrowed stock's lambda_K
  equals the sheet's mean K. The test's bound is 4 x 2^-52 relative; one ulp
  was measured, 9.0625 against 9.062500000000002.
- The honesty floor and pinned mode's exact regime are refused by name. Pauli
  needs 91 layers at least, pauli-4x4 29.
- atlas_film is imported from vendor/atlas-film only. Any other copy is
  refused by name. The refusal fired on the lead's own smoke test, which had
  imported the editable checkout first.

**The gates** (tests/develop, stage `develop`, in the quick budget).
- 14 tests:
  - a small print frozen, as the digests of its sheet, negative and print;
  - atlas-film's files frozen, as a digest;
  - the density identity for three stocks at three layer counts;
  - the refusals;
  - one moved crystal moves the negative;
  - a broken pad is refused by atlas-film's contract;
  - the shuffle is a permutation.
- The frozen values were watched to fail before they were set. Eight faults
  were then planted in develop.py, one at a time, and every one failed a gate:
  - the thresholds' bits shifted;
  - the pitch without its square root;
  - no honesty floor;
  - no shadow check;
  - a pad of 0;
  - no per-layer offset;
  - the exact regime unchecked;
  - sites unchecked.

**The prints** (tools/first_prints.py, docs/prints/). All are on silver paper,
ungrained, at E = 0x1.3a7550d6f4737p-3 (0.1535), metered once on atlas-film's
default path and kept.

| print | cells | layers | pitch, um | mean K | rolls | print digest |
|---|---|---|---|---|---|---|
| atlas-pauli-4x4 | 116 x 116 | 29 | 1.252639 | 9.0625 | 24,389 Atlas shots of 24,576, shuffled; 187 unused | 78c70404809c0da3 |
| golden-pauli-4x4 | 116 x 116 | 29 | 1.252639 | 9.0625 | 24,389 golden rolls | 971a5446da0594a1 |
| pauli | 256 x 256 | 91 | 1.240431 | 8.88672 | 23,296 golden rolls (pinned sampler), 741 s on 11 workers | 96415fe7964c0a6c |
| poisson | 256 x 256 | 91 | 1.240431 | 8.88672 | 23,296 golden rolls | bd468d75946b56b9 |
| trix | 256 x 256 | - | 1.240431 | 8.87343 | atlas-film's own pinned coat, seed 1 | e6b6d9292142dd31 |

**The grain, by its structure factor** (each record's `structure_factor`, k in
units of 2 pi / side).

| k | 8 | 16 | 24 | 32 | 48 | 64 |
|---|---|---|---|---|---|---|
| pauli | 0.223 | 0.292 | 0.367 | 0.496 | 0.708 | 0.720 |
| poisson (the twin) | 0.415 | 0.800 | 0.851 | 0.921 | 0.963 | 0.931 |
| trix (atlas-film's coating) | 0.936 | 0.907 | 1.137 | 0.858 | 1.101 | 0.942 |

- Between the tile's scale (k = 16) and about twice Pauli's Fermi scale
  (k = 90), Pauli's count carries 0.29-0.72 of random placement's noise power.
- Below k = 16, the twin is suppressed too, down to 0.019 at k = 1. That is the
  tiling, not the law.
- The Atlas-laid sheet and its golden twin trace one curve: at k = 8, 16 and
  32, 0.122, 0.307 and 0.592 against 0.113, 0.401 and 0.628.
- **A print is a function of its record.** `python tools/first_prints.py --check`
  re-develops all five from their records alone. The golden rolls were
  re-laid, and the Atlas shots re-read and re-shuffled, with the recorded
  exposure. Every sheet, negative, print and scene digest matched. Pauli's
  23,296 rolls took 798 s on eleven workers.

## 2026-09-26 - the web demo and the poster, drawn from the records

At the owner's request, for the submission's web demo, video and poster.
- **site/** is a static page, deployed to GitHub Pages by
  .github/workflows/pages.yml. Its first deploy was run 36244571651 at 7e6f60d,
  and it succeeded.
  - The story is a pure function of its clock, 2:40 long, drawn in three.js
    with its captions in the canvas. It records itself as a video.
  - The A|B sliders compare classical and quantum crystals and prints.
  - The tile toy samples in the browser in float64, and the page says so.
- **Its data come from the records.** tools/site_data.py exports three things:
  - every Atlas shot, as 24,576 16-bit masks;
  - one golden layer each of Pauli and its Poisson twin;
  - the first prints' structure factors and images.

  tests/docs/test_site.py holds them to docs/records and docs/prints: the
  shots in the canonical order, two named golden tiles per stock, and the
  images byte for byte. A planted moved crystal fails it.
- **The poster** (tools/poster.py, docs/prints/poster.png, 2400 x 3200) puts
  three real prints on a strip of film: Atlas's, Pauli's and TRI-X's. The dots
  behind them are the golden Pauli layer.
- The story's figures are this ledger's:
  - 51 rotations;
  - 24,576 shots in six jobs;
  - 29 layers;
  - "about 30 to 70 percent" for Pauli's 0.29-0.72;
  - the Atlas print's digest.

## 2026-09-26 - corrections to the first prints and the demo entries: S(k)'s band, and what tiling does

Verifier-P0's one pass over round 2 found two claims false as stated (round-2 ledger, verifier-P0.md 13:23Z). Both
are prose. The code, the records, the gates and the prints held. The lead re-read each figure from the records.
- **D1.** "Between the tile's scale (k = 16) and about twice Pauli's Fermi scale (k = 90), Pauli's count carries
  0.29-0.72 of random placement's noise power" is false.
  - 0.29-0.72 were the table's columns, k = 16 to 64. A Fermi sea's S(k) reaches 1 at twice the Fermi scale,
    k = 90.5 on these sheets, and Pauli's record reaches 1.131 at k = 90.
  - What the records hold between the tile's scale and the Fermi scale (k = 16 to 45, where k_F = 16 sqrt(8) =
    45.25):

    | sheet | min | max | mean |
    |---|---|---|---|
    | Pauli | 0.279 | 0.642 | 0.472 |
    | the twin | 0.657 | 1.122 | 0.892 |
    | TRI-X | 0.798 | 1.167 | 0.997 |

  - Every Pauli bin in that band lies below every twin bin.
  - The exact law expects 0.301-0.644 for Pauli and 0.889-0.905 for the twin (verifier-P0).
  - The demo entry's "about 30 to 70 percent" for "Pauli's 0.29-0.72" inherited the error. The story now says
    roughly 30 to 65 percent, and its plot's band ends at the Fermi scale.
- **D2.** "A sheet of independent fixed-count tiles suppresses S(k) above the tile's scale for ANY law" is false.
  The spike above and STOCKS.md both said it.
  - A fixed count sends S(k) to 0 as k goes to 0, for every law. How far above the tile's scale the suppression
    reaches depends on the law, through the variance of a tile's dipole moment.
  - Verifier-P0's control used the prints' geometry, with crystals bunched in a 6 x 6 block at a random place in
    each tile. It gave S of 1.6 to 11.7 at k = 4 to 12: enhanced, not suppressed.
  - The evidence for "ANY law" was one law, the uniform twin.
  - STOCKS.md now says what holds, and names the case it matters for: Speckle, whose crystals bunch.
- **Also corrected (the verifier's minor items).**
  - DETERMINISM said lambda_K equals the mean K "to one rounding". It holds within 2 x 2^-52 relative, measured at
    every allowed layer count up to 1,000, and exactly at about 40% of them.
  - README's "1.24 um across" was the 256-cell prints' pitch. The 4x4 prints' pitch is 1.2526 um.
- **Recorded, not changed.**
  - The table's golden-pauli-4x4 rolls also come from the pinned sampler, the authority's roll by construction.
    Its --check therefore needs libcft too.
  - TRI-X's lowest bin (0.238 at k = 1) holds two modes. "About 1 at every k" holds in law and on average: 0.997
    over k = 16 to 45.
  - The spike's figures (11,776 rolls in 233 s; 0.024 against 0.016) come from scratch work that nothing in the
    tree reproduces.
  - 933138bc is the six runs' outlier. Under the exact law, P(one-site chi^2 >= 34.0) = 0.0094, and the chance of
    such a run among six is 5.5% (verifier-P0, 20,000 replicates).
- **A gate for the shuffle** (verifier-P0's m1).
  - A Sattolo walk planted in develop.shuffled passed every stage; only --check caught it.
  - tests/develop now rebuilds the Atlas print's sheet from the committed device rolls. It holds the sheet's K
    and threshold digests to the print's record, in about 3 s.
  - The Sattolo plant fails it, and 15 tests pass.
- Correction to the line above, from verifier-P0's confirming pass (13:37Z): TRI-X's lowest bin does not hold two
  modes. It holds eight, four of them independent: every wave vector whose length rounds to 1, the diagonals
  included. A reading of 0.238 there has a 1.6% chance in law, and 10 of 600 coating seeds gave one. "About 1 at
  every k" still holds in law. The error came first from verifier-P0's own earlier entry.

## 2026-09-26 - round 2 closed: the paper, and the ledger archived

- **The paper**, docs/chance-made-permanent.pdf (15 pages), is StoryDocs' build of its projects/quantum-film at
  673148c there, byte for byte.
  - Its build recomputes the numbers of 21 of its sentences from this repository's records, re-checks five
    conditions its sentences rest on, and finds 20 cited figures in the documents they are attributed to. A
    planted wrong number fails its build. A number outside those lists is held by nothing.
  - No verifier read it. The demo and the poster were read only where verifier-P0's D1 reached them, in the S(k)
    captions (round-2 ledger, lead.md 13:38Z).
- **Round 2's ledger** is archived beside ParcelRound's fourth case study, as its `archive/round4-second-ledger.zip`,
  with verifier-P0's scripts. The entries above that cite the round-2 ledger resolve there. The working copy is
  deleted.
- What round 2 left open is in docs/ROADMAP.md, "Carried from round 2".

## 2026-09-26 - the link preview: the site's Open Graph tags show the poster

At the owner's request, a link to the site previews with the poster, in Discord and elsewhere.
- site/index.html carries Open Graph tags: the page's own title and description, and the poster, img/poster.png, as a
  large image (`twitter:card` is `summary_large_image`).
- tests/docs/test_site.py holds the tags to what the site serves:
  - og:url is the live link the README gives, and og:image is a file under it, byte for byte docs/prints/poster.png;
  - the stated width and height are the PNG's own, 2400 x 3200;
  - the preview's title and description equal the page's;
  - a tag given twice fails.
- Six faults were planted one at a time, and every one failed the test: the image renamed, the width wrong, the
  description drifted, the URL's case wrong, the image given twice, and the small card. The page was restored byte
  for byte.
- Not held: how each service draws a preview, which nothing here can check. The poster is portrait, 3:4, so a service
  that crops previews to a wide card will crop it. A service may also keep a preview it fetched before these tags.

## 2026-10-03 - round 3's P0: the device-run record, commitment v3 and IBM's reader

The owner's word (2026-10-01 and 03):
- validate the system on IBM's free tier first, where a mistake is cheap;
- then take 24,576 hardware shots for an honest comparison with the emulator, the law and the classical twin;
- then hand the same bundle to Moth, whose CTO runs it.

docs/HARDWARE.md holds what was read and measured before any job ran, and docs/ROUND3.md is the round's plan.
- **The device-run record** (`quantum-film/device-run/v1`, in quantum_film/fixer.py).
  - It holds every shot of one circuit in one hardware job: its role (known-answer, law, coherence), the basis
    each qubit was read in, and the counts, canonical and summing to the shots.
  - A device roll is one layout per file. Hardware noise spreads a run over thousands of distinct layouts, which
    is the bundle format carried from round 1.
- **Commitment v3** binds:
  - the stock, the role and the basis;
  - the route, the backend and the program;
  - the logical circuit's and the transpiled circuit's SHA-256;
  - the shots, the options' digest, the decode rule and the salt.

  The kind and the device were unbound in v2, and v3 binds them. The job id exists only after submission, so the
  record carries it beside the commitment, and the anchor binds it.
- **IBM's reader** (quantum_film/ibm/decode.py) reads a sampler bitstring as the logical qubits that read 1.
  - Position p holds classical bit 15 - p. It is held to the known answer X on {0, 1, 3, 7, 12}, which read
    0001000010001011 on the fake Heron r2 backends on 2026-10-01.
  - Plain order gives the mirror, {3, 8, 12, 14, 15}. On the device, the first job of every route repeats the
    known answer.
- **Tests:** tests/fixer/test_device_runs.py and tests/decode/test_ibm_decode.py. The fixer and decode stages pass
  105 tests.
- **Eight faults were planted** one at a time, and every one failed a test. The files were restored byte for byte.
  - a commitment without the transpiled circuit;
  - the shots not summed;
  - a law run read out of Z;
  - counts in any order;
  - a run fixed before it was submitted;
  - options not held to their digest;
  - runs checked as negatives;
  - the reader in plain order.
- **Stated, not closed:** a record alone cannot prove its commitment came first, because the salt is in it.
  test_a_record_alone_cannot_prove_its_commitment_came_first shows a re-sealed backend passing `check`. What binds a
  run is its anchor:
  - its commitment committed to git before any result is read;
  - for a frozen bundle, the bundle's own commit before it leaves this repository;
  - the commitment in the submitted circuits' metadata, which IBM keeps with the job.

## 2026-10-03 - round 3's P0, revised after its verifier: the simulator kind, the job line, and corrections

Verifier-P0 (Sonnet 5.5, at the owner's word that this round's verifiers are Sonnet models) checked 33e0a08 and
said NOT READY (round-3 ledger, verifier-P0.md 14:05Z-14:11Z). It confirmed by measurement:
- **the reader:** 354 of 360 transpiles over levels 1-3 and five layout kinds read exactly, and none read wrong
  (6 simulator memory failures). So did 78 noisy readings through both samplers;
- **the commitment's encoding:** injective over 100,000 random tuples;
- **the eight planted faults;**
- **no regressions:** the fixer's verdict on all 12,185 JSON files was identical before and after.

Every one of its defects is closed here:
- **A simulator passed as a QPU.** Device runs now have two kinds:
  - `qpu`, whose backend must be an IBM device's name (`ibm_<name>`);
  - `simulator`, which may not name one.

  `fake_kingston`, `aer_simulator`, `fake_ibm_kingston` and `ibm_kingston_sim` are refused as `qpu`.
- **The anchor could not be run as written.**
  - A job line (`quantum-film/hardware-job/v1`: `check_job_line`, `held_to_line`) names the job, IBM's created
    time, the bundle's manifest hash and every circuit's commitment in PUB order. Each record is held to it.
  - The order: submit; read IBM's created time, a status call; commit AND push the line; only then
    `result()`, which fetches results itself.
  - A bundle is submitted once.
  - The Moth leg's line is written on Moth's machine. That is stated as a limit (docs/ROUND3.md).
- **The key-leak list was incomplete.** docs/HARDWARE.md now also refuses:
  - a proxy, by reading `urllib.request.getproxies()`, which on Windows includes the registry's;
  - CA bundles: `REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE`, `SSL_CERT_FILE` and `SSL_CERT_DIR`;
  - a `.netrc`.
- **decode.py was wrong about BitArray.array.** Read MSB-first, its bytes are the right string. Only the raw
  Executor array in column order is the mirror. Corrected.
- **Raw results were written after decoding.** The plan now writes them first.
- **The minors:**
  - the time order counts fractions of a second;
  - `decode` must be a known rule, so a lone surrogate is refused by name, not by a traceback;
  - the options are the options AS SENT, and must state `dynamical_decoupling.enable`, `twirling.enable_gates`
    and `twirling.enable_measure`. Those paths are what both samplers send;
  - the job's PUB index is a bound field, so two runs with equal shots cannot be swapped;
  - `basis[q]` is qubit q, stated;
  - `decode.known_answer` judges a known-answer run: the expected set must be modal and strictly ahead of its
    mirror, and a mirror-symmetric answer is refused.
- **Commitment v3 is redefined in place.** It now also binds the kind and the PUB index. No v3 record existed.
  33e0a08 is public, so this line says it.
- **Correction to the entry above.** "The kind and the device were unbound in v2, and v3 binds them" was false as
  written at 33e0a08: v3 there had one kind and did not bind it. It is true from this commit.
- **Correction to the entry above.** "Tests: ... The fixer and decode stages pass 105 tests" stands. The verifier
  found six conditions in that code that no test held, among them `options_digest` without `sort_keys` and a qubit
  twice in one outcome. Each is now tested.
- **Tests:** tests/fixer/test_device_runs.py, tests/fixer/test_job_line.py (new) and
  tests/decode/test_ibm_decode.py. The fixer and decode stages pass 149 tests.
- **Twenty faults were planted** one at a time, and every one failed a test. The files were restored byte for
  byte. They included:
  - the verifier's six uncaught ones;
  - a simulator as a qpu;
  - the commitment without the kind or without the PUB;
  - a line holding any commitment at any PUB;
  - a known answer passing on a tie with its mirror.

## 2026-10-03 - round 3's P0 after verifier-P0's confirming pass: jobs within a bundle, the device list, and three more paths closed

Verifier-P0's confirming pass on e8454ef (round-3 ledger, verifier-P0.md 14:45Z) found:
- every defect of its first pass closed, by a gate it watched fail or by a stated limit;
- four text-level points left open, A to D below, and one test gap.

Each is closed here:
- **A. "A bundle is submitted once" contradicted the plan's two jobs.**
  - A bundle holds jobs: the known-answer job, then the film's.
  - Each job has its circuits in PUB order, PUBs numbered within the job from 0, and one line per job.
  - Once-only is per job. A runner refuses a job that already has a line, and over a record directory
    `fixer.check_job_lines` refuses a job id twice or a commitment in two lines.
- **B. Two more key-leak paths join docs/HARDWARE.md:**
  - `SSLKEYLOGFILE`, which would write the IAM exchange's TLS secrets to disk;
  - every netrc spelling requests reads: `~/.netrc`, `~/_netrc` and `NETRC`.
- **C. A failed job's record.** ROUND3.md promised "a line saying so" for a job that fails before its circuits
  run, with no field for it. Now such a job keeps its line, its final status is recorded beside the line, and
  no run is fixed from it.
- **D. P1's brief gains controls and the details that make them possible:**
  - **Raw bytes:** a decode error never loses them. `result()` decodes internally, so raw-first means fetching
    the payload below it.
  - **Once-only:** a second submission is refused.
  - **PUBs:** counts land under their own PUB. `held_to_line` cannot see counts put under the wrong one; the
    verifier showed it.
  - **The created time** is read in UTC, since `job.creation_date` is local time.
  - **The executor Sampler's options** are found where it puts them.
  - **The preimages:** each hash's preimage file.
  - **ROUND3.md's control list** matches the brief's ten.
- **A qpu run's backend is now one of the nine IBM QPUs online on 2026-10-01**, a list of real names. A shape
  (`ibm_[a-z]+`) passed `ibm_simulator` and `ibm_fake`, and a list of forbidden words would have refused a real
  device (`ibm_rensselaer` holds "aer"). A device that comes online later is added by name.
- **A file nested too deep is refused by name** ("unreadable: RecursionError"), not by a traceback.
- **Correction to the entry above.** "Each is now tested" was one short: the early return after the source's
  type checks was held by no test, and without it a string `shots` raised TypeError inside `check`. It is tested
  now, with six fields of the wrong type.
- **Tests:** tests/fixer and tests/decode pass 158.
- **Planted:** seven new faults, one at a time, and every one failed a test:
  - a commitment in two lines;
  - a job id twice;
  - a bad line inside a set;
  - any `ibm_` name taken for a device;
  - a device missing from the list;
  - deep nesting crashing `check_file`;
  - no early return after the type checks.
- **Addendum, the same day: the boundaries verifier-P0's mutants passed at e8454ef** (its 14:46Z entry) are each held
  by a test now. Thirteen of its mutants were planted again, one at a time, and every one failed:
  - a time order compared to the millisecond;
  - an int taken as a stated option;
  - the Atlas rule among a run's decode rules;
  - a third kind;
  - the stock not compared in `held_to_line`;
  - a negative or a bool PUB;
  - a line that is not an object;
  - no early return in `check_job_line`;
  - a line's kind, route or names not held;
  - a record with no source;
  - the known answer's expected set left unsorted.

  Its mutant D4 (`decode.lower()` inside the commitment) is now equivalent, since `decode` must be one of
  `RUN_DECODES`, all lowercase. The fixer and decode stages pass 175 tests.
- **Addendum, verifier-P0's read of 07fbe49 and 6a48f97** (15:04Z). That read found A-D, the device list and the
  thirteen boundaries closed. It found two small defects in 07fbe49's code, each failing closed, and both are
  closed here.
  - **`check_job_lines` passed a resubmission given as a generator.** It walked its lines three times, and a
    one-shot iterable is seen once.
    - It now reads them into a list first, and refuses by name anything that is not a sequence of lines.
    - A resubmission is refused given as a list, a tuple, an iterator, a generator or a map.
  - **A file nested between about 990 and 3,000 levels crashed `check_file`.** `fixer.text`'s indented encoder
    recursed too deep outside the refusal. The check and the canonical text now sit inside the same refusal.
    Tested at 1,500 and 2,500 levels.
  - **The early return in `check_job_lines` is tested:** a line missing `job_id` and a `None` line are named, not
    crashed.
  - **Planted:** four faults, one at a time, and every one failed a test. The fixer and decode stages pass 183
    tests.
  - **ROUND3.md and the briefs:**
    - a failed job's status file holds IBM's own state and usage, and no function checks its form, which is
      stated;
    - a device outside `IBM_DEVICES` is added by name before a bundle is frozen for it.
- **Addendum, during P1 and P2's work:**
  - `fix_run` now copies its counts and its source. A caller that changes or reuses them afterwards no longer changes
    a record already fixed. verifier-P0 noted the aliasing, and P2's tests were bitten by it (round-3 ledger, P2.md
    16:58Z).
  - A test changes the caller's copies after fixing and finds the record intact. Planted, the aliasing fails it.
  - The fixer and decode stages pass 184 tests.

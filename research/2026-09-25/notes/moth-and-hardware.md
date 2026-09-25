# Moth engine ecosystem and QPU rental costs

Research date: Friday 25 September 2026, for the "fixer" entry to Moth Hack 2026.

**Legend**
- **[V] VERIFIED**: fetched on 25 Sept 2026. Sources were web pages, public read-only GitHub API calls (`gh api`), public registries, or public price files.
- **[M] FROM MEMORY**: not fetched. Treat as unconfirmed. The URL shows where to check.
- Each price carries the date its source states. "Undated" means the page gives no date, and the fetch date (25 Sept 2026) applies.
- Published figures are in sections 2.1 to 2.4. My own estimates are only in section 2.5, and each is labelled ESTIMATE.

---

## Key findings

1. **There is no public engine SDK, template or authoring guide.** `archaeo-sdk` and `features-0.6.md` appear only as names inside Moth's public API spec. Neither exists on GitHub, PyPI or npm. [V] (details in 1a)
2. **There is no public way for community or hackathon participants to publish an engine.** Engine creation needs `publish_engines`. Features come from "plan bundle and entitlement rows", and the API has no endpoint to request one. None of the hackathon challenges asks for a published engine. The site's "Submit project" button is still disabled. [V] (1b)
3. **Two of the libraries behind the engines are public; three are not.** QuantumBlur and QuantumGraph are public and Apache-2.0. The `quantum-echo`, `iqpixl` (Tessa) and `qrc` libraries are not public. Only QuantumBlur's `hub` branch shows an engine-side entry point, and it is not the `run(params) -> dict` signature. [V] (1c)
4. **The repos have no shared seeding convention, but the public API spec does.** In the spec, `seed` is optional; if you omit it, the server draws one and returns it in provenance or state. Seeds are capped at 2^53-1, and a seed fixes the circuit, not the shot noise. [V] (1d)
5. **IBM costs $1.60 per QPU-second.** That is the pay-as-you-go catalogue price, effective 1 to 30 Sept 2026. 20 circuits x 4,000 shots on a Heron QPU comes to about 30 s, or about $48. That fits inside the free Open Plan allowance of 10 min per 28 days. [V prices; ESTIMATE usage]
6. **Braket charges $0.30 per task plus a per-shot fee.** From the AWS offer file dated 11 Sept 2026, the per-shot fees are:
   - Rigetti Cepheus-1-108Q: $0.000425
   - IQM Garnet: $0.00145
   - IQM Emerald: $0.0016
   - QuEra Aquila: $0.01
   - AQT IBEX-Q1: $0.0235
   - IonQ Forte: $0.08

   The same 20 x 4,000 experiment would cost about $34 to $40 on Cepheus and about $128 to $134 on Emerald. [V prices; ESTIMATE totals]

---

## Part 1: Moth's engine ecosystem (public sources only)

The GitHub org `moth-quantum` has 29 public repos, and the org was created on 3 Mar 2024. [V] https://github.com/moth-quantum

Moth's public API spec is also public: https://api.mothquantum.com/openapi.yaml (`moth-api v0.41.0`). It is served without auth, and the Scalar viewer at https://api.mothquantum.com/docs reads it. I cite it below as "the spec". [V]

### 1(a) Is there a public engine SDK, template or authoring guide?

**No.** Nothing public documents how to write and ship an Atlas engine.

| Check (25 Sept 2026) | Result | Status | URL |
|---|---|---|---|
| GitHub code search for `archaeo-sdk` | 0 results | [V] | https://github.com/search?q=archaeo-sdk&type=code |
| GitHub code search for `archaeo-jobs` | 0 results | [V] | https://github.com/search?q=archaeo-jobs&type=code |
| GitHub code search for `engine.yaml` in org:moth-quantum | 0 results | [V] | https://github.com/search?q=org%3Amoth-quantum+engine.yaml&type=code |
| PyPI: `archaeo-sdk`, `archaeo_sdk`, `mothquantum`, `moth-quantum`, `moth-sdk`, `mothprovider`, `mothbackend` | All 404. The PyPI package named `archaeo` is an unrelated 0.0.1 utility by Anders Cui. | [V] | https://pypi.org/pypi/archaeo-sdk/json |
| npm search for `mothquantum` | 0 packages | [V] | https://registry.npmjs.org/-/v1/search?text=mothquantum |
| GitHub code search for `mothprovider` / `mothbackend` | Only unrelated repos | [V] | https://github.com/search?q=mothprovider&type=code |
| Moth Substack (9 posts, 11 Aug 2025 to 22 May 2026) | No engine-authoring content | [V] | https://mothquantum.substack.com/archive |
| mothquantum.com and /index | Mentions Atlas, an alpha community and a waitlist; no developer docs | [V] | https://mothquantum.com , https://mothquantum.com/index |
| Hackathon repo and site | Challenges, agenda and links only; no SDK or template | [V] | https://github.com/moth-quantum/moth-hack-sep-2026 , https://hack.mothquantum.com |

These are the closest public artefacts, from most to least useful for writing an engine:

1. **Engine descriptions in the spec.** These are hints at the contract, not a guide. [V] https://api.mothquantum.com/openapi.yaml
   - `tamagotchi-v0` and `tamagotchi-v1` state the contract as `run(params) -> dict` plus a separate `validate(params) -> None`.
   - `graph-v1`, `labyrinth-v1` and `comet-qrng-v1` each document an internal pipeline of `build -> submit -> collect -> format`.
   - `comet-qrng-v1` also mentions an SDK call, `update_progress`.
   - `otoc-echo-v1` says the engine file owns the params schema, validation, credits, estimate and the typed result envelope, while the library owns the physics.
   - `qrc-train-v2` names "archaeo-sdk's named-binary-output + JSON envelope, see features-0.6.md".
   - `SubmitJobInputBody` has `start_from` and `stop_after` fields for steps engines.
   - The `Engine` schema exposes `has_validate_fn`, `has_estimate_fn`, `estimate_needs_container`, `sidecar_endpoint`, `queue` and `run_policy`. `run_policy` has `heartbeat`, `max_retries` and `timeout`, in seconds.
2. **QuantumBlur `hub` branch.** It is the only public engine-side code.
   - Its README says the branch is "specifically designed for the API deployment".
   - `quantumblur/basic.py` says it "will be called from Archaeo API".
   - It defines `run(blurStyle, blurStrength, imgForm, imgData, imgCoor, callback=None)`, which returns `{"output": <image bytes>}`. The optional progress callback has the form `callback(step, total)`.
   - It is packaged with Poetry (Python ^3.10, qiskit>=1.0, qiskit-aer>=0.13).
   - The last commit was on 8 Apr 2026.
   - There is no `engine.yaml` in the branch.

   [V] https://github.com/moth-quantum/QuantumBlur/tree/hub , https://github.com/moth-quantum/QuantumBlur/blob/hub/quantumblur/basic.py
3. **coccoon QuickStartGuide.** This is a client-side guide to calling engines. [V] https://github.com/moth-quantum/coccoon/blob/main/QuickStartGuide.md , https://github.com/moth-quantum/coccoon/blob/main/games/quantum_caverns/quantum_caverns.gd
   - Call pattern:
     1. `POST https://api.mothquantum.com/api/v1/engines/<id>/process` with a `{"params": {...}}` body and a Bearer API key.
     2. Receive HTTP 202 with a `job_id`.
     3. Poll `GET /api/v1/jobs/<job_id>` until the status is completed, succeeded or done.
     4. Read the result inline in `result`, or from presigned URLs in `outputs`.
   - The worked example uses `blur-core-v1` with `values` and `strength`.
   - The repo has no licence (see 1c).
4. **QuantumBrush plugin template.** This is a sibling contract, not an Atlas one. [V] https://github.com/moth-quantum/QuantumBrush (README, `Hackathons.md`, `effect/apply_effect.py`, `effect/backend.py`); example brush: https://github.com/moth-quantum/QuantumBrush/tree/example-brush/effect/example
   - Each brush lives in `effect/<id>/<id>.py` and exposes `run(params)`.
   - A `<id>_requirements.json` manifest holds name, id, author, version, dependencies, `user_input` (typed, with min, max and default), `stroke_input` and `flags`.
   - The runner injects the backend (Aer, or IQM Resonance via `IQM_TOKEN`), a pre-flight QPU-seconds cost estimate and a per-stroke cap.
   - `run` returns an RGBA array, not a dict.

### 1(b) How can community or hackathon participants get an engine onto Atlas?

**No public path was found.** There is no submission path, no request form, and no public statement that `publish_engines` is granted on request.

**What the spec says about publishing** [V] https://api.mothquantum.com/openapi.yaml
- `POST /api/v1/engines` (create-engine) and `PATCH` (update-engine) both "require the publish_engines feature". Creating or editing a showcase also requires `publish_engines`.
- `GET /api/v1/me` returns `features`, described as the "Sorted union of the configured plan bundle and current entitlement rows". The spec has no endpoint to request a feature. My reading is that Moth grants features administratively.
- The create-engine body is metadata only:
  - `engine_id`, `name`, `params_schema`
  - `execution_mode` (`handler` or `steps`) and `steps`
  - `input_files` and `output_files`
  - `credits_per_run`, `visibility`, `run_policy`
  - `version`, described as the "(engine.yaml version)"

  There is no field for code, a container image or a repo. My inference is that the worker behind an engine's queue is deployed outside the public API, by Moth.
- Organisation settings include `creation_role` (admin or editor). This controls which org members may create engines, but `publish_engines` is still required.

**What the hackathon says** [V] https://github.com/moth-quantum/moth-hack-sep-2026/blob/main/content/event.ts (commit `bc40f0ce`, 25 Sept 2026 13:20 UTC), https://hack.mothquantum.com
- There are 10 challenges, and none asks you to publish an engine.
  - Challenge 9 (Expert, £200) asks for a repo of a quantum application that processes media, "especially" one that uses the Atlas API.
  - Challenge 10 asks for a Python notebook that uses the API.
  - Prizes are £100, £150 and £200 per challenge by tier.
- The "Submit your project" link has `href: null`, so the button renders disabled as "Submit project".
- On Saturday 26 Sept at 12:00, Spencer gives "Introducing Atlas". The session covers the web app, the API and how to submit projects.
- The virtual hackathon runs from 26 Sept to 2 Oct, and winners are announced on Discord on Monday 5 Oct.
- The hackathon Discord is https://discord.gg/N9y6URcYS.

**Other signals**
- The Luma page for the 25 Sept opening says attendees will leave "having run jobs on real quantum computers". It says nothing about engine publishing or feature grants. [V] https://luma.com/2myo5mu4
- The RSVP page promises access to Atlas, but gives no rules or submission details. [V] https://luma.com/wmrrdpcj
- Moth's home page reads "Join our alpha community and be the first to use Atlas". [V] https://mothquantum.com
- The index page says the upcoming platform already has "its first cohort of alpha users" and has a waitlist. [V] https://mothquantum.com/index

**Precedents for community contributions**
These all flowed into Moth libraries, not into Atlas directly.
- QuantumBrush: fork the repo, add a brush and open a PR. After review, Moth merges it into the `dist` branch with credit. Hackathon winners become official contributors. [V] https://github.com/moth-quantum/QuantumBrush/blob/dist/README.md , https://github.com/moth-quantum/QuantumBrush/blob/dist/Hackathons.md
- At the Bradford Quantum Hackathon, Moth set a challenge to create new Quantum Brush effects. [V] https://mothquantum.com/index
- QPIXL, the lineage behind Tessa/iqpixl, has two hackathon repos:
  - `HeidelbergQuantum/QPIXL_ITU-2025` describes itself as "QPIXL base code for the MOTH hackathon challenge". [V] https://github.com/HeidelbergQuantum/QPIXL_ITU-2025
  - `moth-quantum/QuantumArtHack`, the unitaryHACK 2025 version of QPIXL, merged external PRs in June 2025. [V] https://github.com/moth-quantum/QuantumArtHack/commits/main

**What this implies for fixer (my recommendation, not a published fact)**
- Ask Moth in the Discord, or at the Atlas talk, for a temporary `publish_engines` grant or for Moth to host the engine.
- Meanwhile, build fixer as a standalone repo that implements `run(params) -> dict` and `validate(params)` locally, and enter it for challenge 9. Adding a notebook would also cover challenge 10.

### 1(c) Public repos behind existing engines

Engine IDs are from the spec's "engines catalog". I checked licences and repo contents with `gh api` [V].

| Atlas engine(s) | Library named in the spec | Public repo(s) found | Licence | Shows the engine contract? |
|---|---|---|---|---|
| `blur-v0`, `blur-v1`, plus the related `blur-core-v1`, `blur-midi-v1`, `telablur-v1` | `blur-v1` links to https://github.com/qiskit-community/QuantumBlur. `blur-core-v1` uses its own `gray_encoding.py`. | https://github.com/moth-quantum/QuantumBlur (fork; branches include `main`, `hub`, `csharp`). Upstream is https://github.com/qiskit-community/QuantumBlur (archived). NuGet: https://www.nuget.org/packages/Moth.QuantumBlur (1.0.0, C#). | Apache-2.0 (fork and upstream) | **Partly.** The `hub` branch has an engine-side `run(...) -> {"output": bytes}` with a progress callback, called "from Archaeo API". It is not `run(params) -> dict` and has no `engine.yaml`. [V] |
| `graph-v1`, `labyrinth-v1` | `graph-v1` says it is "Built on QuantumGraph" and links the Moth fork. `labyrinth-v1` uses "ZZ-prep QuantumGraph". | https://github.com/moth-quantum/QuantumGraph, a fork of https://github.com/qiskit-community/QuantumGraph. Its dependency https://github.com/moth-quantum/pairwise-tomography is a fork of if-quantum/pairwise-tomography. | Apache-2.0 (all three) | **No.** These are libraries only. [V] |
| `otoc-echo-v1` (Quantum Echo), `retrocausal-echo-v1` | Both are wrappers over the `quantum-echo` library | **None found.** GitHub repo and code search return only unrelated "quantum-echo" repos. [V] https://github.com/search?q=quantum-echo&type=repositories | n/a | n/a |
| `tessa-image-v1`, `qpixl-v1` | `tessa-image-v1` names "Tessa (the `iqpixl` library)". `qpixl-v1` names "Interwoven QPIXL". Both also use `media_utils` and `topology`. | **No iqpixl repo found.** Public ancestors: https://github.com/moth-quantum/QuantumArtHack (unitaryHACK 2025 QPIXL, main author Daniel Bultrini), https://github.com/HeidelbergQuantum/ParallelQPIXL and https://github.com/HeidelbergQuantum/QPIXL_ITU-2025 | None of the three has a licence file, so no reuse rights are granted by default. | **No.** [V] |
| `qrc-audio-v1`, `qrc-gen-v2`, `qrc-image-v1`, `qrc-midi-v1`, `qrc-train-v2` | `qrc_core`, `qrc.generator.QRCGenerator`, `qrc.data.sequence_mapping.SequenceMapping` | **None found.** Searches for QRC repos return only unrelated projects. [V] https://github.com/search?q=qrc+quantum+reservoir&type=repositories | n/a | n/a |
| `comet-qrng-v1` | None named. The spec describes a Python engine on mothbackend that uses a Toeplitz extractor and NIST SP 800-90B estimators. | https://github.com/moth-quantum/quantum_rng_comet, a C library forked from tsotchke/quantum_rng with no Moth commits. Its name and concepts match the engine (SP 800-90B, CHSH), but the link is **unconfirmed**. | MIT | **No.** [V] |
| `entanglement-shader-v0`, `entanglement-shader-v1` | None named | The engine code is not public. https://github.com/moth-quantum/actually-quantum-moon ships baked output of an entanglement-shader job, and its README says the generation pipeline is not in the repo. | Apache-2.0 | **No.** [V] |
| `tamagotchi-v0`, `tamagotchi-v1` | "Qiskit QEC engine" | None found | n/a | The spec text itself states `run(params) -> dict` plus `validate(params) -> None`. [V] |
| `qdrive-api-v1`, `tomography-api-v2`, `coin-toss-v1`, `deep-fryer-v1` | `qdrive-api-v1` uses QDrive (`QDrive.target()` and `QDrive.update()`). The others name no library. | None found (`pairwise-tomography`, above, may relate to `tomography-api-v2`, unconfirmed) | n/a | n/a |

Related public Moth repos that are not engines [V]:
- https://github.com/moth-quantum/MicroMoth (Apache-2.0): a minimal simulator used by coccoon and by QuantumBlur's fallback.
- https://github.com/moth-quantum/coccoon: a Godot client of the Atlas API. GitHub reports no licence and the tree has no LICENSE file.
- https://github.com/moth-quantum/QuantumBrush: GitHub reports no licence, but the repo contains `LICENSE-2.0.txt` (Apache 2.0) and the README licence section says Apache-2.0.
- https://github.com/moth-quantum/quantum-audio (Apache-2.0), published on PyPI as `quantumaudio` 0.2.0: https://pypi.org/project/quantumaudio/
- https://github.com/moth-quantum/mqa-data (Apache-2.0).

### 1(d) Determinism and seeding conventions

**In the repos: no consistent convention** [V]

| Repo | Finding | URL |
|---|---|---|
| coccoon | The QuickStart makes the output mode the determinism switch: use `probabilities_dict` for deterministic values (terrain generation) and `counts` or `memory` for real randomness. | https://github.com/moth-quantum/coccoon/blob/main/QuickStartGuide.md |
| coccoon, Qubit Park | Six random `_s` values drive the world; the comments say to fix them (for example all 0.1) for a reproducible world. | https://github.com/moth-quantum/coccoon/blob/main/games/qubit_park/qubit_park.gd |
| coccoon, Quantum Caverns | Only the decorative title screen is seeded (`rng.seed = 42`). The maze's initial randomness uses unseeded `randi()`/`randf()`. | https://github.com/moth-quantum/coccoon/blob/main/games/quantum_caverns/quantum_caverns.gd |
| coccoon, MicroMoth in GDScript | Sampling uses global `randf()`, with no seed argument. | https://github.com/moth-quantum/coccoon/blob/main/micromoth.gd |
| MicroMoth | The C# `Counts`/`Memory` take an optional `int? seed`, with a comment about seeding for game development. The Python `micromoth.py` uses unseeded `random.random()`. | https://github.com/moth-quantum/MicroMoth/blob/main/versions/Csharp/MicroMoth/MicroMoth.cs |
| QuantumBlur | Probabilities come exactly from the statevector (Aer `SaveStatevectorDict`, `shots=1`), so blur output is deterministic. Only `dotdot()` uses unseeded `random`, for optional jitter. The `hub` `run()` has no seed parameter. | https://github.com/moth-quantum/QuantumBlur/blob/main/quantumblur/quantumblur.py |
| QuantumGraph | The library uses unseeded `random()` (and `np.random.randn` on `fix/random-vector-gauge-bias`). Only the tests on `feat/incremental-tomography` call `random.seed(0)`. Tests treat `ExpectationValue` as exact and allow EPS 0.05 (about 4σ at 8192 shots). | https://github.com/moth-quantum/QuantumGraph |
| QuantumBrush | No seeds: `AerSimulator()` uses its defaults, and pointillism uses unseeded `np.random`. | https://github.com/moth-quantum/QuantumBrush/blob/dist/effect/utils.py |
| mqa-data (Moth's benchmarking paper data) | The strictest convention. `SEED = 123` sets `PYTHONHASHSEED`, `random.seed`, `np.random.seed` and `seed_simulator`. The seed is saved as `{job_id}/{job_id}_seed.json` beside each IBM hardware job. | https://github.com/moth-quantum/mqa-data/blob/main/mqa-hardware.ipynb |

**In the public spec: a clear convention in the newer engines** [V] https://api.mothquantum.com/openapi.yaml
- `seed` is an optional integer or null, defaulting to null. It appears on `graph-v1`, `otoc-echo-v1`, `retrocausal-echo-v1`, `qdrive-api-v1`, `qrc-audio-v1`, `qrc-midi-v1`, `qrc-image-v1`, `qrc-train-v2` and `tamagotchi-v0`/`v1`. Tamagotchi describes it as a "simulator seed for reproducibility".
- If you omit it, the engine draws one and returns it.
  - The echo engines draw a 31-bit integer, "returned in provenance".
  - `qrc-train-v2` and `qrc-image-v1` record it in the returned state so the run can be reproduced.
- Seeds are capped at 2^53-1, because moth-api (Go) and browser clients re-encode larger integers as float64.
- A seed fixes construction, not shot noise. For `graph-v1`, the same seed builds the same circuit, so emu and qpu runs can be compared on identical states.
- Training and sampling seeds are separate. `qrc-gen-v2` has `random_seed`, applied after the model loads, while the training seed is always reused exactly.
- `comet-qrng-v1` has `public_seed`, a Toeplitz extractor seed id (default `toeplitz-v1`).
- The provenance block in the `comet-qrng-v1` example has `mode`, `backend`, `provider_job_id`, `qpu_seconds` and `circuit_hash`.
- Bitstring convention: mothbackend reports counts with qubit 0 leftmost, and engines reverse Qiskit's order exactly once at the boundary (`qpixl-v1`, `graph-v1`, `comet-qrng-v1`).
- `tessa-image-v1` and `qpixl-v1` have no exact mode for sampled runs, and `shots` defaults to 4096.

My recommendation, not a published fact: fixer should copy the spec's convention.
- Make `seed` optional, with a default of null.
- If it is null, draw a 31-bit seed and echo it in `provenance`.
- Keep seeds at or below 2^53-1.
- Use the seed for circuit construction and for Aer `seed_simulator`.
- Record `backend`, `provider_job_id`, `qpu_seconds` and `circuit_hash`.

---

## Part 2: Renting real quantum hardware (as of 25 Sept 2026)

### 2.1 IBM Quantum: published figures

| Item | Published figure | Date the source states | Status | URL |
|---|---|---|---|---|
| Pay-As-You-Go list price | "Starts at $96 USD / minute", billed per second, minimum purchase 1 second | Undated | [V] | https://www.ibm.com/quantum/pricing |
| Pay-As-You-Go catalogue price | USD 1.60 per Quantum Compute Second (GBP 1.17306352, EUR 1.368984) | Effective 2026-09-01 to 2026-09-30 | [V] | https://globalcatalog.cloud.ibm.com/api/v1/5304b575-3cff-4455-90dc-ae4367762093/pricing |
| Flex Plan | From $72/min, at least 400 min/year, contract required | Undated | [V] | https://www.ibm.com/quantum/pricing |
| Premium Plan | From $48/min, at least 5,200 min/year, contract required | Undated | [V] | https://www.ibm.com/quantum/pricing |
| On-Prem Plan | Quote only | Undated | [V] | https://www.ibm.com/quantum/pricing |
| Open Plan (free) | 10 min of runtime "per month" on the pricing page; "per 28-day rolling window" in the docs. Instances can only be created in us-east. Workloads are blocked at the limit, with no charges. | Pricing page undated; catalogue plan record updated 2026-08-18 | [V] | https://quantum.cloud.ibm.com/docs/en/guides/plans-overview , https://globalcatalog.cloud.ibm.com/api/v1?q=quantum |
| Open Plan one-time promotion | Use 20 min of runtime in any 12-month period on a non-trial account, then opt in for 180 min over the next 12 months. The plan then reverts to 10 min/month. | Blog dated 16 Mar 2026 | [V] | https://www.ibm.com/quantum/blog/open-plan-updates |
| Open Plan devices | `ibm_kingston` (Heron r2) opened to all Open Plan users. The full Open Plan QPU list is shown only when you create an instance. | 16 Mar 2026 | [V] | https://www.ibm.com/quantum/blog/open-plan-updates , https://quantum.cloud.ibm.com/docs/en/guides/instances |
| What counts as usage | Time the QPU is locked. Session usage is wall-clock time; batch usage is cumulative. User-error failures and user cancellations are billed. | Undated | [V] | https://quantum.cloud.ibm.com/docs/en/guides/estimate-job-run-time |
| IBM's usage formula | About 2 s per sub-job + (rep_delay + circuit length) x executions. rep_delay is 250 µs on most backends. Quick form: 2 + 0.00035 x executions (seconds), without advanced mitigation. | Undated | [V] | https://quantum.cloud.ibm.com/docs/en/guides/estimate-job-run-time |
| Cost controls | PAYG instances can have a total cost limit (set in USD). Billing is in local currency. | Undated | [V] | https://quantum.cloud.ibm.com/docs/en/guides/manage-cost |

### 2.2 IBM fleet (Compute resources page, fetched 25 Sept 2026) [V] https://quantum.cloud.ibm.com/computers

| QPU | Processor | Programmable qubits | Region | Status | MCPS (max circuits/s) |
|---|---|---|---|---|---|
| ibm_phoenix | Nighthawk r2 | 120 | us-east | Online | 109.7 kHz |
| ibm_miami | Nighthawk r1 | 120 | us-east | Online | 250 Hz |
| ibm_berlin | Nighthawk r1 | 120 | eu-de | Online | 250 Hz |
| ibm_boston | Heron r3 | 156 | us-east | Online | 3.8 kHz |
| ibm_pittsburgh | Heron r3 | 156 | us-east | Online | 3.8 kHz |
| ibm_aachen | Heron r3 | 156 | eu-de | Online | 3.8 kHz |
| ibm_kingston | Heron r2 | 156 | us-east | Online | 3.8 kHz |
| ibm_fez | Heron r2 | 156 | us-east | Online | 3.9 kHz |
| ibm_marrakesh | Heron r2 | 156 | us-east | Paused | 3.7 kHz |

- MCPS means the maximum circuits per second for a circuit with one Hadamard and one measurement, including reset. [V] https://quantum.cloud.ibm.com/docs/en/guides/qpu-information
- The current processor families are Nighthawk and Heron. Nighthawk r2 (September 2026) has 120 programmable qubits and fast per-qubit reset. [V] https://quantum.cloud.ibm.com/docs/en/guides/processor-types
- **No IBM device has between 27 and 119 qubits any more.** [V] https://quantum.cloud.ibm.com/docs/en/guides/retired-qpus
  - The last 27-qubit QPUs (ibm_algiers, ibm_cairo, ibm_hanoi) retired on 2024-04-30.
  - The last 127-qubit Eagles (ibm_strasbourg, ibm_brussels) retired on 2026-04-27.
  - ibm_torino (133 qubits) retired on 2026-04-01.
- Before those retirements, the Open Plan included ibm_brisbane, ibm_sherbrooke and ibm_torino. [M] https://quantum.cloud.ibm.com/docs/en/guides/retired-qpus

### 2.3 Amazon Braket: published figures

**Price sources**
- The AWS Price List offer file for Amazon Braket has `publicationDate` 2026-09-11T12:44:10Z and term `effectiveDate` 2026-08-01. [V] https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBraket/current/index.json
- The Braket pricing page shows the same QPU prices but is undated. [V] https://aws.amazon.com/braket/pricing/

**Devices and qubit counts**
- Devices, regions and ARNs are listed at [V] https://docs.aws.amazon.com/braket/latest/developerguide/braket-devices.html
- Qubit counts for IQM and Rigetti are from [V] https://docs.aws.amazon.com/braket/latest/developerguide/braket-submit-tasks.html. Sources for the other counts are in the table.

| Vendor / device | Qubits | Region | Per task | Per shot | Reservation (Braket Direct), per hour | Price date | Status |
|---|---|---|---|---|---|---|---|
| Rigetti Cepheus-1-108Q | 108 (launched on Braket 7 Apr 2026: https://aws.amazon.com/about-aws/whats-new/2026/04/amazon-braket-rigetti-cepheus/) | us-west-1 | $0.30 | $0.000425 | $4,100 | Offer file 2026-09-11 (effective 2026-08-01) | [V] |
| Rigetti Ankaa-3 | 84 | us-west-1 | $0.30 | $0.0009 | $5,750 | Offer file 2026-09-11. Still in the device list and price file, but **not** in the pricing-page table. | [V] |
| IQM Garnet | 20 | eu-north-1 | $0.30 | $0.00145 | $3,000 | Offer file 2026-09-11 | [V] |
| IQM Emerald | 54 | eu-north-1 | $0.30 | $0.0016 | $4,000 | Offer file 2026-09-11 | [V] |
| IonQ Forte-1 | 36 [M] | us-east-1 | $0.30 | $0.08 | $7,000 | Offer file 2026-09-11 | [V] prices |
| IonQ Forte-Enterprise-1 | 36 (what's-new 20 Mar 2025: https://aws.amazon.com/about-aws/whats-new/2025/03/ionq-forte-enterprise-amazon-braket) | us-east-1 | $0.30 | $0.08 | $7,000 | Offer file 2026-09-11 | [V] |
| AQT IBEX-Q1 | 12 (what's-new 20 Nov 2025: https://aws.amazon.com/about-aws/whats-new/2025/11/amazon-braket-alpine-quantum-technologies/) | eu-north-1 | $0.30 | $0.0235 | $4,800 | Offer file 2026-09-11 | [V] |
| QuEra Aquila | Analog Hamiltonian simulation, not gate circuits | us-east-1 | $0.30 | $0.01 | $2,500 | Offer file 2026-09-11 | [V] |

Other Braket facts [V]:
- IonQ error mitigation needs at least 2,500 shots per task. (Pricing page, undated.) https://aws.amazon.com/braket/pricing/
- **Program sets** bundle up to 100 programs, or one parametric circuit with up to 100 parameter sets, into one task. You pay one per-task fee plus per-shot fees on the total shots.
  - They were announced on 14 Aug 2025. https://aws.amazon.com/about-aws/whats-new/2025/08/amazon-braket-program-sets
  - Supported devices are unclear. One docs page says "all gate-based QPUs": https://docs.aws.amazon.com/braket/latest/developerguide/braket-batching-tasks.html
  - Another docs page says "AQT, IQM and Rigetti", so IonQ support is uncertain: https://docs.aws.amazon.com/braket/latest/developerguide/braket-constructing-circuit.html
- The Free Tier gives 1 hour of on-demand **simulator** time per month for the first 12 months. There is no free QPU tier. The SV1 simulator costs $0.075/min. (Pricing page, undated.) https://aws.amazon.com/braket/pricing/
- The pricing page's Example 4 says Rigetti costs "$0.00090" per shot, but its arithmetic uses $0.000425. That is stale text; use the price table. https://aws.amazon.com/braket/pricing/
- Moth's own QuantumBrush code calls IQM Resonance directly (`https://resonance.iqm.tech`), not Braket. This is a possible third route, not priced here. https://github.com/moth-quantum/QuantumBrush/blob/dist/effect/backend.py

### 2.4 Research credits and free allowances [V]

**IBM Quantum Credits** (undated page). https://www.ibm.com/quantum/quantum-credits
- Open to academic researchers; a faculty member or research lead must apply.
- The research must be "novel, utility-scale", at more than about 30 qubits.
- Proposals should make progress within 3 to 10 hours of QPU time.
- Applications are reviewed on a rolling basis.

**IBM Classroom Accounts** (undated). https://www.ibm.com/quantum/pricing
- Professors can request Classroom Accounts.
- Students then use Open Plan resources without a credit card.

**IBM Open Plan** allowance and promotion: see 2.1.

**AWS Cloud Credit for Research** (undated page, with a dated notice). https://pages.awscloud.com/aws-cloud-credit-for-research.html
- Students are capped at $5,000; faculty and staff are uncapped.
- Applications are reviewed on a rolling basis, typically in 30 to 60 days.
- Credits are valid for 1 year.
- "Effective February 16, 2026, Free Tier accounts will be ineligible for promotional credits."

**Braket research page** (undated). https://aws.amazon.com/braket/quantum-computing-research/
- Points researchers to the programme above.
- Suggests emailing quantum-bd@amazon.com to speed up a request.

### 2.5 Worked cost estimates (ESTIMATES, my arithmetic on the published figures above)

**Assumptions**
- The workload is 20 circuits x 4,000 shots = **80,000 executions**, sampler-style.
- No PEC, PEA or ZNE error mitigation, and no dynamic-circuit extras.
- USD, before tax. Queue time is not billed.
- Qubit count (16 to 64) does not change the price on either platform. IBM bills QPU time; Braket bills per shot, whatever the circuit depth.

**(i) IBM, 20 x 4,000 on a 120 to 156-qubit QPU** (27-qubit devices are retired; see 2.2). Price used: $1.60/s, effective 1 to 30 Sept 2026.

| Scenario | Usage (ESTIMATE) | Cost (ESTIMATE) |
|---|---|---|
| One Sampler job with 20 PUBs on Heron, IBM quick formula: 2 + 0.00035 x 80,000 | **30 s** | **$48.00** (£35.19 at GBP 1.17306352/s) |
| Same work sent as 20 separate jobs: 20 x 2 s + 28 s | 68 s | $108.80 (£79.77) |
| Floor from Heron MCPS (3.7 to 3.9 kHz): 80,000 / MCPS + 2 s | about 22.5 to 23.6 s | about $36 to $38 |
| ibm_phoenix (Nighthawk r2, MCPS 109.7 kHz): floor 80,000 / 109,700 + 2 s | about 2.7 s, plus the gate time of your circuits | from about $4.40; likely under $10 |
| ibm_miami or ibm_berlin (Nighthawk r1, MCPS 250 Hz): 80,000 / 250 + 2 s | **at least 322 s** | **at least $515.20** |
| Open Plan (600 s per 28 days) | 30 s is 5% of the allowance; the Nighthawk r1 case would be 54% | **$0** on an Open Plan QPU such as ibm_kingston |

**The IBM choice matters more than the price list.**
- Heron is about $48, or free under the Open Plan.
- Nighthawk r1's published MCPS implies about 10x more QPU time.
- Moth's own spec examples mention `ibm_fez` and `ibm_miami`.
- Check `backend.default_rep_delay` and `backend.configuration().mcps` before submitting.
- Use job or batch mode, not session mode: sessions bill wall-clock time.

**(ii) Braket, same 20 x 4,000 workload.** Prices are from the offer file dated 2026-09-11.

| Device | Shot fees (80,000 x per-shot) | Total as 20 separate tasks | Total as 1 program set | Fits 16 to 64 qubits? |
|---|---|---|---|---|
| **Rigetti Cepheus-1-108Q** | $34.00 | **$40.00** | **$34.30** | Yes (108 qubits) |
| **IQM Emerald** | $128.00 | **$134.00** | **$128.30** | Up to 54 qubits |
| IQM Garnet | $116.00 | $122.00 | $116.30 | Up to 20 qubits only |
| Rigetti Ankaa-3 (price file only) | $72.00 | $78.00 | $72.30 | Yes (84 qubits) |
| IonQ Forte / Forte Enterprise | $6,400.00 | $6,406.00 | $6,400.30, if program sets are supported (unclear) | Up to 36 qubits |
| AQT IBEX-Q1 | $1,880.00 | $1,886.00 | $1,880.30 | No (12 qubits) |
| QuEra Aquila | n/a | n/a | n/a | Not a gate-circuit device |

**Sensitivity across the stated range** (ESTIMATE; IBM uses the Heron quick formula, Braket uses one program set)

| Workload | Executions | IBM Heron | Rigetti Cepheus | IQM Emerald | IonQ Forte (separate tasks) |
|---|---|---|---|---|---|
| 10 circuits x 1,000 shots | 10,000 | 5.5 s = $8.80 | $4.55 | $16.30 | $803.00 |
| 20 circuits x 4,000 shots | 80,000 | 30 s = $48.00 | $34.30 | $128.30 | $6,406.00 |
| 50 circuits x 10,000 shots | 500,000 | 177 s = $283.20 (still inside the 600 s Open Plan window) | $212.80 | $800.30 | $40,015.00 |

**Caveats on these estimates**
- IBM "usage" grows with Estimator resilience, twirling and error mitigation.
- The 2 s per sub-job overhead repeats whenever IBM splits a large job.
- IBM's list price says "starts at" $96/min. The September 2026 catalogue shows a single $1.60/s metric, and I found no per-QPU surcharge.
- Braket QPUs run only in availability windows and add small S3 storage costs.
- I did not find a published per-task shot limit for program sets. Check each device's `shotsRange` in the Braket console before submitting 50 x 10,000.

---

## Sources (all fetched 25 Sept 2026 unless marked [M])

**Moth**
- https://mothquantum.com , https://mothquantum.com/index , https://mothquantum.com/company
- https://mothquantum.substack.com/archive (and the posts `a-new-way-to-think-about-quantum` and `painting-with-quantum-physics`)
- https://hack.mothquantum.com , https://luma.com/wmrrdpcj , https://luma.com/2myo5mu4
- https://api.mothquantum.com/docs , https://api.mothquantum.com/openapi.yaml (moth-api v0.41.0)

**GitHub, via `gh api`**
- https://github.com/moth-quantum and the repos cited above
- https://github.com/qiskit-community/QuantumBlur , https://github.com/qiskit-community/QuantumGraph
- https://github.com/HeidelbergQuantum/ParallelQPIXL , https://github.com/HeidelbergQuantum/QPIXL_ITU-2025
- https://github.com/QuantumComputingLab/qpixlpp (QPIXL++, licence NOASSERTION; not used by the spec)

**Registries**
- https://pypi.org/pypi/archaeo-sdk/json (404)
- https://pypi.org/project/quantumaudio/
- https://registry.npmjs.org/-/v1/search?text=mothquantum
- https://www.nuget.org/packages/Moth.QuantumBlur

**IBM**
- https://www.ibm.com/quantum/pricing
- https://globalcatalog.cloud.ibm.com/api/v1/5304b575-3cff-4455-90dc-ae4367762093/pricing
- https://www.ibm.com/quantum/blog/open-plan-updates
- https://www.ibm.com/quantum/quantum-credits
- https://quantum.cloud.ibm.com/computers
- https://quantum.cloud.ibm.com/docs/en/guides/plans-overview
- https://quantum.cloud.ibm.com/docs/en/guides/instances
- https://quantum.cloud.ibm.com/docs/en/guides/estimate-job-run-time
- https://quantum.cloud.ibm.com/docs/en/guides/manage-cost
- https://quantum.cloud.ibm.com/docs/en/guides/processor-types
- https://quantum.cloud.ibm.com/docs/en/guides/retired-qpus
- https://quantum.cloud.ibm.com/docs/en/guides/qpu-information

**AWS**
- https://aws.amazon.com/braket/pricing/
- https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBraket/current/index.json
- https://docs.aws.amazon.com/braket/latest/developerguide/braket-devices.html
- https://docs.aws.amazon.com/braket/latest/developerguide/braket-submit-tasks.html
- https://docs.aws.amazon.com/braket/latest/developerguide/braket-batching-tasks.html
- https://docs.aws.amazon.com/braket/latest/developerguide/braket-constructing-circuit.html
- https://aws.amazon.com/about-aws/whats-new/2025/08/amazon-braket-program-sets
- https://aws.amazon.com/about-aws/whats-new/2026/04/amazon-braket-rigetti-cepheus/
- https://aws.amazon.com/about-aws/whats-new/2025/03/ionq-forte-enterprise-amazon-braket
- https://aws.amazon.com/about-aws/whats-new/2025/11/amazon-braket-alpine-quantum-technologies/
- https://aws.amazon.com/braket/quantum-computing-research/
- https://pages.awscloud.com/aws-cloud-credit-for-research.html

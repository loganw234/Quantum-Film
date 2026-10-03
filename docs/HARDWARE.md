# IBM Quantum hardware, as this project uses it

Read and measured on 2026-10-01, before any job ran, by round 3's research
(two agents, one on IBM's own pages and a local simulation, one on Moth's
route; sources at the end). Each point says how it is known:
- **verified** means read on IBM's or Moth's own pages that day;
- **measured** means run locally on qiskit 2.5.2, qiskit-ibm-runtime 0.50.0
  and qiskit-aer 0.17.2, against the fake backends of the owner's three QPUs;
- **inferred** means neither.

## The account

- **The plan (verified):**
  - The Open Plan gives 10 QPU-minutes per rolling 28 days, in us-east.
  - The owner's instance reaches ibm_kingston, ibm_fez and ibm_marrakesh: Heron
    r2, 156 qubits, CZ native.
  - Sessions are refused on Open. Batch and job modes are allowed, and
    `max_execution_time` caps a job's QPU time.
- **Pay-As-You-Go costs $96 a minute (verified).** A client given no instance
  picks one itself, so every call names the Open instance's CRN.
- **The key and the instance live outside the tree.**
  - `QF_IBM_KEY_FILE` names IBM's `apikey.json`, and `QF_IBM_INSTANCE_FILE`
    names a file holding the CRN.
  - Both are in `C:\Users\logan\.quantum-film\`, outside every repository and
    every directory an agent is given.
  - Nothing calls `save_account()`.
- **Cost (verified, measured):** a job costs about 2 s plus about 0.35 ms a
  shot. The film's 24,576 shots are 8 to 11 s.

## Where the key can go wrong (measured, with the HTTP transport replaced by a recorder)

- **The normal path.** With a token and a CRN, the key goes only to
  `iam.cloud.ibm.com`. After that, bearer tokens go to `quantum.cloud.ibm.com`,
  `api.global-search-tagging.cloud.ibm.com` and `globalcatalog.cloud.ibm.com`.
- **If IAM fails after the first token, the raw key goes out.** Every later
  call carried `Authorization: apikey <key>` to the API host, with only a
  warning. A runner treats that warning as fatal.
- **The key or the tokens can be redirected.** Any of these redirects them or
  switches off TLS checks, so a runner refuses to start while one is present:
  - the variables `IAM_URL`, `IBM_CREDENTIALS_FILE` and `VCAP_SERVICES`;
  - any variable that STARTS with a service's upper-cased name. The stack
    configures the services `GLOBAL_SEARCH` and `GLOBAL_CATALOG`, and from
    their prefixed variables applies the URL, the TLS switch (`DISABLE_SSL`),
    compression and retries.
    - The URL or the TLS switch is enough to redirect the bearer token or
      switch off TLS checks, so a runner refuses any variable starting
      `GLOBAL_SEARCH` or `GLOBAL_CATALOG`.
    - The prefixed `_APIKEY`, `_AUTH_URL` and `_AUTH_TYPE` are read only by
      constructors this stack does not call.
    - `RESOURCE_CONTROLLER` is configured only when the instance is named by
      name, not by CRN, and a runner passes the CRN.
    - Read in the installed source by round 3's P2 (corrected by P2 at 16:07Z).
      Before that the list named only `<SERVICE>_URL` and
      `<SERVICE>_DISABLE_SSL`.
  - `QISKIT_IBM_RUNTIME_LOG_FILE`, which makes the client write a log file
    (round 3's P2, from source);
  - a file `ibm-credentials.env` in the working or home directory;
  - a proxy:
    - All three HTTP session classes the stack uses take one from the
      environment. They are requests, `ibm_cloud_sdk_core.BaseService` and
      `qiskit_ibm_runtime`'s RetrySession, all with `trust_env` on.
    - On Windows, `urllib.request.getproxies()` falls back to the
      registry's system proxy when the environment names none.
    - So a runner reads `getproxies()` and refuses a non-empty answer.
      Measured by round 3's P0 verifier.
  - a CA bundle in `REQUESTS_CA_BUNDLE` or `CURL_CA_BUNDLE` (measured by the
    verifier); `SSL_CERT_FILE` and `SSL_CERT_DIR` are refused too (inferred,
    from OpenSSL);
  - a netrc file, which requests reads for credentials when no other auth is
    given: `~/.netrc`, Windows' `~/_netrc`, or the file the `NETRC` variable
    names (from its source, not measured);
  - `SSLKEYLOGFILE`, the variable whose file urllib3's TLS context writes the
    session secrets to, those of the IAM exchange included (measured at the
    function by round 3's P0 verifier; from source for the path).
- **Names that are not read.** With an explicit token and channel, the client
  never reads `QISKIT_IBM_URL` or `QISKIT_IBM_TOKEN` (from its source,
  verifier-P0). Naming the token and the instance is what keeps them out.
- **Job tags are not evidence (verified, measured).** They can be replaced
  after submission and carry no time of their own. A run's commitment rides
  in `circuit.metadata` instead: that goes inside the submitted job's
  parameters, which IBM keeps with the job's server-set `created` time, unless
  the job is private or its owner deletes it.
  - **Where the metadata sits in the payload.** The executor Sampler puts it
    in plain text, in its passthrough data. The legacy SamplerV2 puts it
    inside the QPY-encoded circuit, which decodes back unchanged (round 3's
    P0 verifier).
- **Status and result are separate calls on IBM (measured, from the client's
  source, verifier-P0).**
  - A job's created time is not in the submit response, and
    `job.creation_date` fetches it with `GET /jobs/{id}`, a status call.
  - `job.result()` polls status and then fetches `/results` in one call.
  - So a runner may make status calls before it commits its job line. It never
    calls `result()` before that line is committed and pushed (docs/ROUND3.md).
- **What the client sends (measured, verifier-P0).** Both samplers send a
  pre-transpiled circuit identical, operation for operation, to the one
  given, when dynamical decoupling and twirling are off. With either on, the
  circuit sent changes. Whether IBM's server then runs it unchanged is not
  established.

## Compiling

- **Optimization level 1 ignores the calibration (measured).** It takes the
  trivial layout: qubits 0 to 15, the top row of the chip.
  - In a noisy simulation of ibm_kingston, the shots holding exactly five
    crystals fell from 68.7% to 53.1%.
  - Pass the level explicitly (2 or 3), or pin the chain. qiskit 2.5.2's
    default is 2, or whatever `~/.qiskit/settings.conf` says.
- **The output is deterministic (measured).** It is a function of the
  circuit, the target (the day's calibration), the seed and the qiskit version.
  One changed CZ or readout error moved the level-2 chain.
- **A clean compile has no SWAPs.** The film's circuit, compiled onto a 16-qubit
  line, has exactly 102 CZ and no SWAP. It was checked five ways:
  - the routing permutation is the identity;
  - the initial layout equals the final one;
  - every CZ joins neighbouring logical qubits;
  - each consecutive pair in the chain is coupled;
  - there are exactly 102 CZ.

  Every compile, mapped back to 16 qubits, laid the exact law to a total
  variation distance of 9.4e-14 or less.

## Reading

- **The bitstring order (measured).** Position p of a sampler bitstring
  holds classical bit 15 - p, and classical bit i holds logical qubit i when
  the logical circuit is measured with `measure_all` before compiling.
  `quantum_film/ibm/decode.py` reads that order. Read the other way, the
  layout is mirrored q -> 15 - q, which is a gauge of the 4x4 tile, so the
  order is held to a known-answer circuit on the device, never to the
  physics.
- **No mitigation by default (verified).** The Sampler applies none. A run
  still sets dynamical decoupling and twirling off explicitly, and records
  the options it sent.
- **The sampler interface is changing (verified).** SamplerV2 (program
  `sampler`) was deprecated on 2026-09-24, and is removed no sooner than about
  2026-12-24. The executor-based Sampler is another server program. Pin the
  versions, and record the program.

## What the hardware is predicted to do (measured, noisy simulation)

24,576 shots on each device's level-2 chain, with the fake backends' own
noise models. Those snapshots are 5 to 19 months old, and the models leave
out crosstalk, leakage and drift.

| device | exactly five crystals | forbidden, of those | worst one-site \|z\|, raw |
|---|---|---|---|
| ibm_kingston | 63.7-68.7% | 2.66-3.12% | 5.92-7.00 |
| ibm_fez | 61.3-66.6% | 3.42-4.09% | 5.56-9.37 |
| ibm_marrakesh | 69.0-74.3% | 1.88-2.30% | 4.29-7.83 |

Each range runs from the full noise model to the same model with idle
decoherence. For comparison, the exact law puts 0% of five-crystal shots on
forbidden layouts, and random placement of five crystals puts 1,360 / 4,368
= 31.1% there.

## Moth's hardware

- **It is IBM hardware (verified).** Moth's `qpu` mode submits to IBM
  Quantum hardware, through Moth's own IBM account (moth-api v0.41.0).
- **No route for our circuits (verified).**
  - The account holds no `run_quantum`.
  - tomography-api-v2 has no documented route to hardware, and its results
    name no device or IBM job.
- **What Moth offered (the owner, 2026-10-03).** Moth has disabled arbitrary
  circuits on tomography-api-v2, and offered to run a specific circuit for the
  project's validation. A job that fails before its circuit executes does not
  run, and sequential jobs each run.
- **So the Moth leg is the same design, run by Moth on Moth's IBM access**
  (docs/ROUND3.md).
  - It is the same logical circuits and the same runner, in a bundle frozen
    for a device Moth's account reaches.
  - It is the IBM leg's bundle itself only when that device is the same one.
  - Both legs are IBM hardware: one vendor, reached by two accounts.

## Sources (read 2026-10-01)

- **IBM:** quantum.cloud.ibm.com/docs/en/, the guides
  - plans-overview, execution-modes, job-limits, max-execution-time;
  - estimate-job-run-time, initialize-account, cloud-setup-untrusted;
  - bit-ordering, primitive-input-output;
  - defaults-and-configuration-options, transpile;
  - and the qiskit-ibm-runtime release notes.
- **IBM's live device page:** quantum.cloud.ibm.com/computers.
- **Moth:** api.mothquantum.com/openapi.yaml (moth-api v0.41.0) and
  docs.mothquantum.com, both read without credentials, and the account's own
  `GET /api/v1/me`.
- **The agents' scripts and logs** are kept with round 3's ledger.

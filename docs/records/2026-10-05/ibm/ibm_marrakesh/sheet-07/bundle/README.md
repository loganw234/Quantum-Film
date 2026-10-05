# Quantum-Film hardware bundle: pauli-4x4 on ibm_marrakesh

This directory is a frozen bundle. It fixes completely what will run: run it as it is, and change nothing in it. Its identity is the SHA-256 of `manifest.json`, which every job line names.

- Backend `ibm_marrakesh` (kind `qpu`), route `ibm-direct`, program `sampler`.
- Compiled at optimization level 2 with seed 11, against the target's calibration of 2026-10-05T09:51:18Z.
- The chain, the physical qubits of logical qubits 0 to 15: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15].
- Options, stated: dynamical decoupling off, gate twirling off, measurement twirling off.

## The jobs, in order

- `known-answer`: known-answer (1,024 shots); at most 60 s of QPU time.
- `law`: law (24,576 shots); at most 120 s of QPU time.
- `coherence`: coherence-xx (4,096 shots), coherence-yy (4,096 shots); at most 60 s of QPU time.

The known answer puts X on [0, 1, 3, 7, 12]: it checks the order in which the device's bitstrings are read. Run the law and coherence jobs only after the known-answer job has printed HOLDS. Each job takes one shot count across its circuits.

## What to install

- Python 3.12.9, with exactly qiskit==2.5.2 and qiskit-ibm-runtime==0.50.0 (the runner refuses another runtime version), numpy and mpmath. To rehearse offline with `--dry-run`, also qiskit-aer==0.17.2.
- A checkout of github.com/loganw234/Quantum-Film at the commit that holds this bundle.

## The key, outside every directory you run in

- `QF_IBM_KEY_FILE` names IBM's `apikey.json` (its field `apikey`), and `QF_IBM_INSTANCE_FILE` a file holding the instance's CRN. Both files live outside the checkout; the runner refuses a path inside it.
- The runner refuses to start while any of these is configured, and names it: a proxy (the environment, or the Windows registry), a CA bundle (REQUESTS_CA_BUNDLE, CURL_CA_BUNDLE, SSL_CERT_FILE, SSL_CERT_DIR), a netrc file (~/.netrc, ~/_netrc, NETRC), SSLKEYLOGFILE, IAM_URL, IBM_CREDENTIALS_FILE, VCAP_SERVICES, an ibm-credentials.env file, or a GLOBAL_SEARCH_*, GLOBAL_CATALOG_*, RESOURCE_CONTROLLER_* or *_DISABLE_SSL variable. Unset it for the run.
- It never saves an account, and stops if IBM's client says it will send the API key instead of a token.

## What to run, from the checkout's root

    python tools/hw_run.py --bundle <this directory> --job known-answer --out <an output directory>

and then, only if that printed HOLDS, one after the other:

    python tools/hw_run.py --bundle <this directory> --job law --out <the same output directory>
    python tools/hw_run.py --bundle <this directory> --job coherence --out <the same output directory>

- The job line (`<job>-line.json`) is committed and pushed by the runner as soon as IBM has created the job, before any result is read. The output directory must be inside this repository, on a branch whose head is already on origin.
- Each job is submitted once. The runner refuses a job that already has a line, and never resubmits. A job that fails keeps its line and gets a status file; a re-run needs a newly frozen bundle.
- This bundle is never dry-run: it binds kind `qpu`, and the runner refuses a fake backend for it. To rehearse offline, freeze a second bundle against a fake backend (`python tools/hw_bundle.py --fake fake_kingston --route ibm-direct --out <another directory>`) and dry-run that one, in a throwaway clone: its line is committed and pushed as a live one is.

## What to send back

The whole output directory, unchanged: for each job its line, its raw result (`<job>-raw.json`, written before anything decodes it), its metrics, its records (`<job>-pub<k>-<name>.json`) and, for the known answer, its verdict; for a job that did not complete, its status file. And the console output.

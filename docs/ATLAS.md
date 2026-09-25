# Atlas, as this project uses it

Moth's platform, reached at `https://api.mothquantum.com`. What is below was
measured on 2026-09-25 with a throwaway key the owner supplied for
exploration. The measurements themselves are in
[VALIDATION.md](VALIDATION.md), and the sanitised responses are in
`docs/records/2026-09-25/atlas/`.

## The spec

- moth-api v0.41.0, as published at `https://api.mothquantum.com/openapi.yaml`.
- The copy the owner saved as `api-1.json` has SHA-256
  `cbc6876136d50ca0bb04c55a83b7f0c44bc43be8eb395535095569d13fbe2889`.
- It is kept out of this repository because it states no licence.

## What an account without features can do

- **`GET /api/v1/me` returns `features: []`.** There is no `run_quantum` (no
  QPU) and no `publish_engines` (no custom engine on the platform).
- **Engines are registered, not uploaded.** The create-engine body carries a
  definition only, and the code runs on Moth's workers. There is no public
  engine SDK and no request path; features are granted by Moth
  (research/2026-09-25/notes/moth-and-hardware.md).
- **Custom circuits run through tomography-api-v2.** It is the one engine that
  runs this project's own circuits: it accepts OpenQASM 2 and measures every
  qubit in nine settings.

## The census: does the same request return the same bytes?

| engine | request | result |
|---|---|---|
| coin-toss-v1 | 1000 shots, twice, two pairs | different every time |
| blur-core-v1 | exact mode | identical, four runs over about 15 minutes |
| blur-core-v1 | 64 shots | different |
| tomography-api-v2 | own QASM | different; returns counts |
| graph-v1 | seed 7 | the circuit identical, the shots different |
| qdrive-api-v1 | seed 7 | two different fitted circuits |

## Reading tomography-api-v2

- **Every setting measures every qubit.** An `I` in a label means "no basis
  rotation", not "not measured". So the setting with no X or Y gives
  whole-register samples: crystal layouts.
- **The count strings change qubit order from setting to setting.** The rule,
  held to a known-answer run with a worst |z| of 2.49, while plain order
  scored 316.61: each string is little-endian over [the setting's non-I
  qubits, ascending] + [the rest, ascending], while the label is in circuit
  order. `quantum_film/atlas/decode.py` implements it, and
  tests/test_decode.py replays the frozen run. Nothing in the response states
  the order. The rule is inferred, and scoped to what the vectors show.

## The client

- `quantum_film/atlas/client.py` drives `C:\Windows\System32\curl.exe`.
  Cloudflare bans Python-urllib's user agent (Error 1010), and Moth's own docs
  use curl.
- The key is read from the file `QF_ATLAS_AUTH` names, outside the tree.
- Any host but the API's is refused, and presigned URLs are never printed.
- `tools/atlas_smoke.py` is the runner's live stage, and makes only GET calls.

## Asked of Moth (the owner's to send)

- A `publish_engines` grant for the hackathon, or Moth hosting the engine. It
  would follow their `run(params)` / `validate(params)` contract.
- The count-order finding above, with the known-answer circuits that show it.

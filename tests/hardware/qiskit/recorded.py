"""IBM's service, stood in for at the HTTP transport, so a tool's LIVE path runs offline with a fake key.

    recorded.py LOG SCENARIO OUT_DIR -- TOOL [args...]     (run under offline.py, in the IBM virtualenv)

Adapted from round 3's research agent's trace_auth.py. requests' HTTPAdapter.send, which every HTTP session
of the stack ends in (requests, ibm_cloud_sdk_core and the runtime's RetrySession), is replaced by a recorder
that answers as IBM's API does: an IAM token, the Global Search and Catalog entries of one Open instance, the
backend ibm_fez (its configuration and properties are the fake backend's), the instance's usage, and jobs.
Nothing leaves the machine; offline.py refuses every socket besides.
  - A submitted job's payload is kept (payload-<n>.json in LOG's directory), and its result is the submitted
    circuits sampled from this package's own ISA simulation, encoded as the runtime encodes a result, each
    PUB echoing its circuit's metadata.
  - The result of a job is refused (409, and logged as RESULT BEFORE ANCHOR) unless that job's line in OUT_DIR
    is committed and pushed: the anchor's order, on the live path.
  - SCENARIO "iam_fails_later" fails every IAM request after the first, the case in which qiskit-ibm-runtime
    0.50.0 sends `Authorization: apikey <key>` to the API host after a warning (docs/HARDWARE.md).
Every request is logged to LOG as one JSON line: method, host, path, the Authorization scheme, whether the key
is anywhere in it, whether it names the instance (Service-CRN), and the status answered.
"""
import atexit
import base64
import datetime
import importlib.util
import json
import os
import pathlib
import runpy
import sys
import time

import numpy as np
from requests.adapters import HTTPAdapter
from requests.models import Response

LOG, SCENARIO, OUT_DIR = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
TOOL, ARGS = sys.argv[sys.argv.index("--") + 1], sys.argv[sys.argv.index("--") + 2:]
KEY = json.loads(pathlib.Path(os.environ["QF_IBM_KEY_FILE"]).read_text())["apikey"]
CRN = pathlib.Path(os.environ["QF_IBM_INSTANCE_FILE"]).read_text().strip()
FEZ = pathlib.Path(importlib.util.find_spec("qiskit_ibm_runtime").origin).parent / "fake_provider" / "backends" / "fez"
CONF = json.loads((FEZ / "conf_fez.json").read_text())
PROPS = json.loads((FEZ / "props_fez.json").read_text())
# IBM's created time: half a minute ago, in UTC, to the microsecond (a time ahead of the local clock would
# make every record's fixed_at precede it, which the fixer refuses). The test reads it back from
# <LOG's stem>.created.txt.
_T0 = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=30)
CREATED = _T0.replace(microsecond=123456).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
(LOG.parent / f"{LOG.stem}.created.txt").write_text(CREATED)
ENTRIES, JOBS = [], {}


def b64(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()


NOW = int(time.time())
JWT = f"{b64({'alg': 'RS256', 'typ': 'JWT'})}.{b64({'iat': NOW, 'exp': NOW + 3600, 'sub': 'mock'})}.c2ln"


def respond(req, status, body):
    r = Response()
    r.status_code = status
    r._content = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    r.headers["Content-Type"] = "application/json"
    r.url, r.request, r.encoding = req.url, req, "utf-8"
    return r


def anchored(job_id):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
    from quantum_film.ibm import anchor
    for line in OUT_DIR.glob("*-line.json"):
        if json.loads(line.read_text()).get("job_id") == job_id:
            return anchor.anchored(line)
    return False


def result_of(params):
    """The submitted PUBs sampled from this package's ISA simulation, encoded as the runtime encodes a result."""
    from qiskit.primitives.containers import BitArray, DataBin, PrimitiveResult, SamplerPubResult
    from qiskit_ibm_runtime import RuntimeEncoder
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3]))
    from quantum_film.ibm import isa
    rng = np.random.default_rng(20261004)
    pubs = []
    for circuit, _values, shots in params["pubs"]:
        p = isa.distribution(isa.gate_list(circuit))
        draws = rng.choice(p.size, size=shots, p=p / p.sum())
        bits = BitArray.from_samples([format(int(n), "016b") for n in draws], num_bits=16)
        pubs.append(SamplerPubResult(DataBin(meas=bits, shape=()),
                                     metadata={"shots": shots, "circuit_metadata": circuit.metadata}))
    return json.dumps(PrimitiveResult(pubs, metadata={"version": 2}), cls=RuntimeEncoder)


def restore(job_id):
    """A job submitted by an earlier process (a --resume), from the payload that process kept."""
    if not (job_id.startswith("mockjob") and job_id[7:].isdigit()):
        return
    path = LOG.parent / f"payload-{int(job_id[7:])}.json"
    if path.exists():
        from qiskit_ibm_runtime import RuntimeDecoder
        JOBS[job_id] = {"params": json.loads(path.read_bytes(), cls=RuntimeDecoder)["params"], "polls": 0}


def locked():
    """Both of keyleak's locks on the IAM fallback, as a request is sent: warnings.warn is its wrapper, and the
    fallback's message is an error by filter. verifier-P2 (round 3, K6) moved hw_predict's lock after the service's
    constructor and its outcome tests still passed; here each request says whether it was sent locked."""
    import warnings

    from quantum_film.ibm import keyleak
    wrapper = getattr(warnings.warn, "refuses_the_fallback", False) is True
    return wrapper and any(f[0] == "error" and f[1] is not None and f[1].match(keyleak.FALLBACK)
                           for f in warnings.filters)


def send(self, req, **kw):
    url = req.url.split("?")[0]
    host, path = url.split("/")[2], "/" + "/".join(url.split("/")[3:])
    auth = req.headers.get("Authorization", "")
    body = req.body or b""
    body = body.encode() if isinstance(body, str) else body
    entry = {"method": req.method, "host": host, "path": path, "auth": auth.split(" ")[0] if auth else "-",
             "key": KEY.encode() in body or KEY in auth or any(KEY in str(v) for v in req.headers.values()),
             "crn_header": "Service-CRN" in req.headers, "locked": locked()}
    ENTRIES.append(entry)
    answer = route(req, host, path, body)
    entry["status"] = answer.status_code
    return answer


def route(req, host, path, body):
    if host == "iam.cloud.ibm.com":
        if SCENARIO == "iam_fails_later" and sum(e["host"] == host for e in ENTRIES) > 1:
            return respond(req, 503, {"errorMessage": "mock outage"})
        return respond(req, 200, {"access_token": JWT, "refresh_token": "mock", "token_type": "Bearer",
                                  "expires_in": 3600, "expiration": NOW + 3600})
    if host == "api.global-search-tagging.cloud.ibm.com":
        return respond(req, 200, {"items": [{"crn": CRN, "service_plan_unique_id": "mock-open-plan",
                                             "name": "open-instance", "doc": {"extensions": {"x": 1}}, "tags": []}],
                                  "search_cursor": None})
    if host == "globalcatalog.cloud.ibm.com":
        return respond(req, 200, {"overview_ui": {"en": {"display_name": "Open"}},
                                  "metadata": {"pricing": {"type": "free"}}})
    if host != "quantum.cloud.ibm.com":
        return respond(req, 404, {"errors": [{"message": "mock: no such host"}]})
    p = path.split("/api/v1")[-1]
    if p == "/backends":
        return respond(req, 200, {"devices": [{"name": "ibm_fez"}]})
    if p == "/backends/ibm_fez/configuration":
        return respond(req, 200, dict(CONF, backend_name="ibm_fez"))
    if p == "/backends/ibm_fez/properties":
        return respond(req, 200, dict(PROPS, backend_name="ibm_fez"))
    if p == "/backends/ibm_fez/status":
        return respond(req, 200, {"state": True, "status": "active", "message": "available", "length_queue": 0,
                                  "backend_version": "1.0.0", "name": "ibm_fez"})
    if "usage" in p:
        return respond(req, 200, {"usage_consumed_seconds": 0, "usage_limit_seconds": 600,
                                  "usage_limit_reached": False})
    if p == "/jobs" and req.method == "POST":
        n = len(list(LOG.parent.glob("payload-*.json"))) + 1           # numbered across processes
        (LOG.parent / f"payload-{n}.json").write_bytes(body)
        from qiskit_ibm_runtime import RuntimeDecoder
        job_id = f"mockjob{n:013d}"
        JOBS[job_id] = {"params": json.loads(body, cls=RuntimeDecoder)["params"], "polls": 0}
        return respond(req, 200, {"id": job_id, "backend": "ibm_fez"})
    parts = p.split("/")
    if len(parts) >= 3 and parts[1] == "jobs" and parts[2] not in JOBS:
        restore(parts[2])
    if len(parts) >= 3 and parts[1] == "jobs" and parts[2] in JOBS:
        job_id, job = parts[2], JOBS[parts[2]]
        if len(parts) == 3:
            job["polls"] += 1
            status = "Queued" if job["polls"] == 1 else "Completed"
            return respond(req, 200, {"id": job_id, "status": status, "state": {"status": status},
                                      "created": CREATED, "backend": "ibm_fez", "program": {"id": "sampler"}})
        if parts[3] == "results":
            if not anchored(job_id):
                ENTRIES[-1]["result_before_anchor"] = True
                return respond(req, 409, {"errors": [{"message": "RESULT BEFORE ANCHOR"}]})
            return respond(req, 200, result_of(job["params"]).encode())
        if parts[3] == "metrics":
            later = [(_T0 + datetime.timedelta(seconds=s)).strftime("%Y-%m-%dT%H:%M:%SZ") for s in (5, 9)]
            return respond(req, 200, {"timestamps": {"created": CREATED, "running": later[0], "finished": later[1]},
                                      "usage": {"quantum_seconds": 3, "seconds": 3}, "bss": {"seconds": 3}})
    return respond(req, 404, {"errors": [{"message": "mock: no route"}]})


HTTPAdapter.send = send


@atexit.register
def _write_log():
    LOG.write_text("".join(json.dumps(e) + "\n" for e in ENTRIES))


sys.path.insert(0, str(pathlib.Path(TOOL).resolve().parent.parent))
sys.argv = [TOOL, *ARGS]
runpy.run_path(TOOL, run_name="__main__")

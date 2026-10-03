"""tools/hw_predict.py --live with the HTTP transport replaced by a recorder: every request is answered from
the fake backend's own files (FakeFez's configuration and properties, served as ibm_fez), and nothing leaves
the machine: an audit hook refuses every socket connection and name lookup. For the predict stage's tests,
run with the lead's virtualenv ($QF_IBM_PYTHON); the key and the instance are fakes the test writes.

    $QF_IBM_PYTHON tests/compare/venv/recorded_live.py LOG SCENARIO -- [hw_predict.py's arguments]

SCENARIO is "normal", or "iam_fails_later": IAM answers the first token request and refuses every later one
with a 503, which is when qiskit-ibm-runtime falls back to sending the raw key (docs/HARDWARE.md). LOG receives
one JSON line per request: method, host, path, the Authorization scheme, and whether the fake key is anywhere in
the request. The exit code is hw_predict's.
"""
import base64
import json
import os
import pathlib
import runpy
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[3]
PREDICT = ROOT / "tools" / "hw_predict.py"
NETWORK = ("socket.connect", "socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyname_ex",
           "socket.sendto", "socket.sendmsg")


def refuse_the_network(event, args):
    if event in NETWORK:
        raise PermissionError(f"recorded_live: network refused: {event}")


def main(argv):
    log_path, scenario = argv[0], argv[1]
    args = argv[argv.index("--") + 1:]
    sys.addaudithook(refuse_the_network)
    with open(os.environ["QF_IBM_KEY_FILE"], encoding="utf-8") as f:
        key = json.load(f)["apikey"]
    with open(os.environ["QF_IBM_INSTANCE_FILE"], encoding="utf-8") as f:
        crn = f.read().strip()

    from qiskit_ibm_runtime import fake_provider
    from requests.adapters import HTTPAdapter
    from requests.models import Response
    fez = pathlib.Path(fake_provider.__file__).parent / "backends" / "fez"
    conf = dict(json.loads((fez / "conf_fez.json").read_text(encoding="utf-8")), backend_name="ibm_fez")
    props = dict(json.loads((fez / "props_fez.json").read_text(encoding="utf-8")), backend_name="ibm_fez")
    now = int(time.time())

    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()

    jwt = f"{b64({'alg': 'RS256', 'typ': 'JWT'})}.{b64({'iat': now, 'exp': now + 3600, 'sub': 'mock'})}.c2ln"
    log = []

    def respond(req, status, body):
        r = Response()
        r.status_code = status
        r._content = b"" if body is None else json.dumps(body).encode()
        r.headers["Content-Type"] = "application/json"
        r.url, r.request, r.encoding = req.url, req, "utf-8"
        return r

    def send(self, req, **kw):
        url = req.url.split("?")[0]
        host, path = url.split("/")[2], "/" + "/".join(url.split("/")[3:])
        auth = req.headers.get("Authorization", "")
        body = req.body or b""
        body = body.encode() if isinstance(body, str) else body
        log.append({"method": req.method, "host": host, "path": path, "auth": auth.split(" ")[0] if auth else "-",
                    "key_in_request": key.encode() in body or key in auth or key in req.url})
        if host == "iam.cloud.ibm.com":
            if scenario == "iam_fails_later" and sum(e["host"] == host for e in log) > 1:
                return respond(req, 503, {"errorMessage": "recorded: IAM is down"})
            return respond(req, 200, {"access_token": jwt, "refresh_token": "recorded", "token_type": "Bearer",
                                      "expires_in": 3600, "expiration": now + 3600})
        if host == "api.global-search-tagging.cloud.ibm.com":
            return respond(req, 200, {"items": [{"crn": crn, "service_plan_unique_id": "recorded-open-plan",
                                                 "name": "recorded-open-instance", "doc": {"extensions": {"x": 1}},
                                                 "tags": []}], "search_cursor": None})
        if host == "globalcatalog.cloud.ibm.com":
            return respond(req, 200, {"overview_ui": {"en": {"display_name": "Open"}},
                                      "metadata": {"pricing": {"type": "free"}}})
        if host == "quantum.cloud.ibm.com":
            p = path.split("/api/v1")[-1]
            if p == "/backends":
                return respond(req, 200, {"devices": [{"name": "ibm_fez"}]})
            if p == "/backends/ibm_fez/configuration":
                return respond(req, 200, conf)
            if p == "/backends/ibm_fez/properties":
                return respond(req, 200, props)
            if p == "/backends/ibm_fez/status":
                return respond(req, 200, {"state": True, "status": "active", "message": "available",
                                          "length_queue": 0, "backend_version": "1.0.0", "name": "ibm_fez"})
            if p == "/instances/usage":
                return respond(req, 200, {"usage_consumed_seconds": 0, "usage_limit_seconds": 600,
                                          "usage_limit_reached": False})
        return respond(req, 404, {"errors": [{"message": "recorded: no such route"}]})

    HTTPAdapter.send = send
    sys.argv = [str(PREDICT), *args]
    code = 1
    try:
        runpy.run_path(str(PREDICT), run_name="__main__")
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
    finally:
        pathlib.Path(log_path).write_text("".join(json.dumps(e) + "\n" for e in log), encoding="utf-8")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

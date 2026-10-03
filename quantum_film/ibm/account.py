"""The IBM account as the tools reach it: the key read from a file, the instance named, the fallback fatal.

docs/HARDWARE.md, measured with the transport replaced by a recorder: with a token and an instance's CRN
the key goes only to iam.cloud.ibm.com, and bearer tokens go everywhere else. If IAM fails after the first
token, qiskit-ibm-runtime 0.50.0 warns "Unable to retrieve IBM Cloud access token. API Key will be used
instead." (api/auth.py) and sends `Authorization: apikey <key>` to the API host on every later call. Before
the service exists, `connect` arms keyleak.refuse_the_fallback: that warning raises FallbackRefused, a
BaseException, inside the auth hook, so the request that would carry the key is never sent and the run stops
at once (tests/hardware/qiskit/test_hw_transport.py records it).

`connect` takes the service class as an argument (the tools pass QiskitRuntimeService), so this module
imports no qiskit and its rules are tested without it. It never prints the key or the CRN, and never calls
save_account().
"""
import json
import pathlib
import re

from . import keyleak

KEY_VARIABLE = "QF_IBM_KEY_FILE"            # IBM's apikey.json, its field "apikey"
INSTANCE_VARIABLE = "QF_IBM_INSTANCE_FILE"  # a file holding the instance's CRN
CHANNEL = "ibm_quantum_platform"
_CRN = re.compile(r"crn:v1:[A-Za-z0-9_.:/-]+", re.ASCII)


def _outside(path, repo):
    p = pathlib.Path(path).resolve()
    repo = pathlib.Path(repo).resolve()
    if p == repo or repo in p.parents:
        raise PermissionError(f"{p.name}: the file is inside the repository; the key and the CRN are kept outside it")
    return p


def read_key(path, repo):
    """The API key from IBM's apikey.json (field "apikey"). Never printed."""
    p = _outside(path, repo)
    try:
        key = json.loads(p.read_text(encoding="utf-8")).get("apikey")
    except (OSError, ValueError, AttributeError) as e:
        raise PermissionError(f"{KEY_VARIABLE}: not IBM's apikey.json ({type(e).__name__})") from None
    if not (isinstance(key, str) and key.strip() and key == key.strip()):
        raise PermissionError(f"{KEY_VARIABLE}: the file has no apikey field")
    return key


def read_crn(path, repo):
    """The instance's CRN, the file's one line. Never printed."""
    p = _outside(path, repo)
    try:
        crn = p.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError) as e:
        raise PermissionError(f"{INSTANCE_VARIABLE}: unreadable ({type(e).__name__})") from None
    if not _CRN.fullmatch(crn):
        raise PermissionError(f"{INSTANCE_VARIABLE}: the file does not hold one instance CRN (crn:v1:...)")
    return crn


def connect(service_class, environ, repo):
    """A service on the named instance: channel ibm_quantum_platform, the token and the CRN given explicitly,
    the fallback fatal, and the active instance checked to be the CRN named."""
    for var in (KEY_VARIABLE, INSTANCE_VARIABLE):
        if not environ.get(var):
            raise PermissionError(f"{var} is not set: name the file outside the repository")
    key = read_key(environ[KEY_VARIABLE], repo)
    crn = read_crn(environ[INSTANCE_VARIABLE], repo)
    keyleak.refuse_the_fallback()
    service = service_class(channel=CHANNEL, token=key, instance=crn)
    if service.active_instance() != crn:
        raise PermissionError("the service's active instance is not the CRN named in "
                              f"{INSTANCE_VARIABLE}; nothing is submitted to another instance")
    return service


def plan_of(service, crn_from_service=None):
    """(plan, pricing type) of the active instance, as the service lists it, for the tools to print."""
    crn = crn_from_service or service.active_instance()
    for inst in service.instances():
        if inst.get("crn") == crn:
            return inst.get("plan"), inst.get("pricing_type")
    return None, None

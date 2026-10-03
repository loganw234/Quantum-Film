"""The IBM account as the tools reach it (quantum_film.ibm.account), with a stand-in service class: the key read
from IBM's apikey.json outside the repository, the instance named by its CRN, the channel explicit, the
active instance checked, and the "API Key will be used instead" warning made an error. Never a value
printed."""
import json
import warnings

import pytest

from quantum_film.ibm import account, keyleak

KEY = "FAKEKEY-not-a-credential-0123456789abcdef"
CRN = "crn:v1:bluemix:public:quantum-computing:us-east:a/0000:1111-2222::"


@pytest.fixture(autouse=True)
def warnings_restored(monkeypatch):
    """connect() arms keyleak.refuse_the_fallback, which wraps warnings.warn process-wide: put it back."""
    monkeypatch.setattr(warnings, "warn", warnings.warn)
    with warnings.catch_warnings():
        yield


class Service:
    made = []

    def __init__(self, **kw):
        Service.made.append(kw)
        self.kw = kw

    def active_instance(self):
        return self.kw["instance"]


@pytest.fixture
def files(tmp_path):
    keys = tmp_path / "keys"
    keys.mkdir()
    (keys / "apikey.json").write_text(json.dumps({"name": "x", "apikey": KEY}))
    (keys / "crn.txt").write_text(CRN + "\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {account.KEY_VARIABLE: str(keys / "apikey.json"), account.INSTANCE_VARIABLE: str(keys / "crn.txt")}
    return env, repo


def test_the_service_is_named_explicitly(files):
    env, repo = files
    Service.made.clear()
    with warnings.catch_warnings():
        service = account.connect(Service, env, repo)
    assert Service.made == [{"channel": "ibm_quantum_platform", "token": KEY, "instance": CRN}]
    assert service.active_instance() == CRN


def test_connecting_arms_the_fallback_refusal(files):
    """Before the service exists: the runtime's fallback warning raises FallbackRefused, a BaseException that an
    `except Exception` in the runtime cannot absorb (round 3's P2, 16:58Z)."""
    env, repo = files
    account.connect(Service, env, repo)
    with pytest.raises(keyleak.FallbackRefused):
        try:
            warnings.warn("Unable to retrieve IBM Cloud access token. API Key will be used instead. mock outage",
                          stacklevel=1)
        except Exception:                                   # what qiskit_runtime_service.py does with an error
            pytest.fail("an `except Exception` absorbed the refusal")
    with pytest.warns(UserWarning, match="unrelated"):
        warnings.warn("an unrelated warning stays a warning", stacklevel=1)


def test_a_key_file_inside_the_repository_is_refused(files):
    env, repo = files
    inside = repo / "apikey.json"
    inside.write_text(json.dumps({"apikey": KEY}))
    with pytest.raises(PermissionError, match="inside the repository") as refusal:
        account.connect(Service, dict(env, **{account.KEY_VARIABLE: str(inside)}), repo)
    assert KEY not in str(refusal.value)


@pytest.mark.parametrize("what, needle", [
    ("no key variable", "QF_IBM_KEY_FILE is not set"),
    ("no instance variable", "QF_IBM_INSTANCE_FILE is not set"),
    ("no apikey field", "the file has no apikey field"),
    ("not json", "not IBM's apikey.json"),
    ("not a crn", "does not hold one instance CRN"),
    ("another instance", "the service's active instance is not the CRN named"),
])
def test_each_refusal_is_named_and_prints_no_value(files, what, needle):
    env, repo = files
    service = Service
    if what == "no key variable":
        env = {account.INSTANCE_VARIABLE: env[account.INSTANCE_VARIABLE]}
    elif what == "no instance variable":
        env = {account.KEY_VARIABLE: env[account.KEY_VARIABLE]}
    elif what == "no apikey field":
        open(env[account.KEY_VARIABLE], "w").write(json.dumps({"api_key": KEY}))
    elif what == "not json":
        open(env[account.KEY_VARIABLE], "w").write(f"apikey={KEY}")
    elif what == "not a crn":
        open(env[account.INSTANCE_VARIABLE], "w").write("open-instance")
    else:
        class Other(Service):
            def active_instance(self):
                return CRN.replace("1111", "9999")
        service = Other
    with warnings.catch_warnings(), pytest.raises(PermissionError, match=needle) as refusal:
        account.connect(service, env, repo)
    assert KEY not in str(refusal.value) and CRN not in str(refusal.value)

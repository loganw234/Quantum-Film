"""Control 3: the runner refuses to start under each key-leak condition of docs/HARDWARE.md, by name, and
never prints a value (quantum_film.ibm.keyleak, which the tools call before they import qiskit)."""
import pytest

from quantum_film.ibm import keyleak

SECRET = "s3cr3t-value-never-printed"


def clean(tmp_path):
    cwd, home = tmp_path / "cwd", tmp_path / "home"
    cwd.mkdir()
    home.mkdir()
    return cwd, home


def test_a_clean_machine_starts(tmp_path):
    cwd, home = clean(tmp_path)
    assert keyleak.refusals({"PATH": "x", "ANTHROPIC_BASE_URL": "https://example.invalid"}, cwd, home, {}) == []


@pytest.mark.parametrize("var", sorted(keyleak.VARIABLES))
def test_each_listed_variable_is_refused_by_name(tmp_path, var):
    cwd, home = clean(tmp_path)
    found = keyleak.refusals({var: SECRET}, cwd, home, {})
    assert len(found) == 1 and found[0].startswith(f"{var} is set:") and SECRET not in found[0]


def test_the_list_is_the_documented_one():
    """docs/HARDWARE.md's list (as of the lead's f92caca), plus what this module adds and says why."""
    assert set(keyleak.VARIABLES) == {"IAM_URL", "IBM_CREDENTIALS_FILE", "VCAP_SERVICES", "REQUESTS_CA_BUNDLE",
                                      "CURL_CA_BUNDLE", "SSL_CERT_FILE", "SSL_CERT_DIR", "NETRC", "SSLKEYLOGFILE",
                                      "QISKIT_IBM_RUNTIME_LOG_FILE"}
    assert keyleak.SERVICE_PREFIXES == ("GLOBAL_SEARCH", "GLOBAL_CATALOG", "RESOURCE_CONTROLLER")


@pytest.mark.parametrize("var", ["GLOBAL_SEARCH_URL", "GLOBAL_CATALOG_DISABLE_SSL", "GLOBAL_SEARCH_APIKEY",
                                 "GLOBAL_CATALOGXURL", "RESOURCE_CONTROLLER_URL", "global_search_url",
                                 "QUANTUM_DISABLE_SSL"])
def test_a_service_variable_or_a_tls_switch_is_refused_whatever_follows_its_prefix(tmp_path, var):
    """ibm_cloud_sdk_core takes every variable that STARTS with a configured service's name (round 3's P2);
    Windows keeps variable names upper-cased, so case is ignored."""
    cwd, home = clean(tmp_path)
    found = keyleak.refusals({var: SECRET}, cwd, home, {})
    assert len(found) == 1 and var in found[0] and SECRET not in found[0]


def test_other_url_variables_are_not_refused(tmp_path):
    """No *_URL besides the services' is read; this desktop sets ANTHROPIC_BASE_URL."""
    cwd, home = clean(tmp_path)
    assert keyleak.refusals({"ANTHROPIC_BASE_URL": SECRET, "QISKIT_IBM_URL": SECRET, "QISKIT_IBM_TOKEN": SECRET},
                            cwd, home, {}) == []


@pytest.mark.parametrize("where", ["cwd", "home"])
def test_the_credentials_file_in_the_working_or_home_directory_is_refused(tmp_path, where):
    cwd, home = clean(tmp_path)
    ((cwd if where == "cwd" else home) / "ibm-credentials.env").write_text(f"GLOBAL_SEARCH_URL={SECRET}\n")
    found = keyleak.refusals({}, cwd, home, {})
    label = "working" if where == "cwd" else "home"
    assert found == [f"ibm-credentials.env is in the {label} directory: ibm_cloud_sdk_core reads service settings "
                     "from it"]


@pytest.mark.parametrize("name", [".netrc", "_netrc"])
def test_a_netrc_file_in_the_home_directory_is_refused(tmp_path, name):
    cwd, home = clean(tmp_path)
    (home / name).write_text(f"machine iam.cloud.ibm.com login x password {SECRET}\n")
    found = keyleak.refusals({}, cwd, home, {})
    assert len(found) == 1 and found[0].startswith(f"{name} is in the home directory") and SECRET not in found[0]


def test_a_proxy_is_refused_by_its_scheme_never_its_url(tmp_path):
    """getproxies() is the environment's proxies or, on Windows, the registry's: either is refused, and the
    proxy's URL (which may carry credentials) is never printed."""
    cwd, home = clean(tmp_path)
    found = keyleak.refusals({}, cwd, home, {"https": f"http://user:{SECRET}@127.0.0.1:9"})
    assert len(found) == 1 and "['https']" in found[0] and SECRET not in found[0]
    assert keyleak.refusals({}, cwd, home, {"no": "localhost"}) != []        # over-refuses, harmlessly


TOOLS = {"hw_run": ["--bundle", "b", "--job", "known-answer", "--out", "o"],
         "hw_bundle": ["--backend", "ibm_fez", "--route", "ibm-direct", "--out", "o"]}


def run_tool(tmp_path, tool, env_over, cwd=None, home=None):
    """The tool itself, in this (qiskit-less) Python: it refuses before it imports qiskit, or it fails trying."""
    import os
    import subprocess
    import sys

    from hwfix import ROOT
    env = {k: v for k, v in os.environ.items() if k.upper() not in keyleak.VARIABLES}
    home = home or tmp_path / "home"
    home.mkdir(exist_ok=True)
    env.update(USERPROFILE=str(home), HOME=str(home), HOMEDRIVE="", HOMEPATH="", **env_over)
    return subprocess.run([sys.executable, str(ROOT / "tools" / f"{tool}.py"), *TOOLS[tool]], cwd=cwd or tmp_path,
                          env=env, capture_output=True, text=True, timeout=120)


CASES = [("hw_run", var) for var in sorted(keyleak.VARIABLES) + ["GLOBAL_SEARCH_URL", "HTTPS_PROXY"]] + \
    [("hw_bundle", "IAM_URL"), ("hw_bundle", "HTTPS_PROXY")]       # the freezer shares the runner's function


@pytest.mark.parametrize("tool, var", CASES)
def test_control_3_the_tools_refuse_to_start_under_each_variable(tmp_path, tool, var):
    """The runner under each variable alone; the freezer (live) under one listed variable and a proxy."""
    p = run_tool(tmp_path, tool, {var: f"http://127.0.0.1:9/{SECRET}"})
    assert p.returncode == 2 and p.stdout.startswith("REFUSED: a key-leak condition holds"), p.stdout + p.stderr
    assert "qiskit" not in p.stderr and SECRET not in p.stdout


@pytest.mark.parametrize("tool", sorted(TOOLS))
def test_control_3s_twin_a_clean_environment_passes_the_check(tmp_path, tool):
    """The refusal is not unconditional: with nothing configured the tool passes the check and goes on to
    import qiskit, which this Python does not have."""
    p = run_tool(tmp_path, tool, {})
    assert p.returncode == 1 and "No module named 'qiskit'" in p.stderr and "REFUSED" not in p.stdout


@pytest.mark.parametrize("where", ["cwd", "home"])
def test_control_3_the_runner_refuses_to_start_beside_a_credentials_file(tmp_path, where):
    cwd, home = clean(tmp_path)
    ((cwd if where == "cwd" else home) / "ibm-credentials.env").write_text("x=y\n")
    p = run_tool(tmp_path, "hw_run", {}, cwd=cwd, home=home)
    assert p.returncode == 2 and "ibm-credentials.env is in the" in p.stdout, p.stdout + p.stderr


def test_the_fallback_raises_a_base_exception_and_a_filter_is_the_second_lock(monkeypatch):
    """keyleak.refuse_the_fallback: the runtime's warning raises FallbackRefused, which an `except Exception`
    cannot absorb (round 3's P2 measured the runtime absorbing an ordinary error); a filter stands behind it."""
    import warnings
    original = warnings.warn
    monkeypatch.setattr(warnings, "warn", original)
    with warnings.catch_warnings():
        keyleak.refuse_the_fallback()
        wrapper = warnings.warn
        keyleak.refuse_the_fallback()
        assert warnings.warn is wrapper and wrapper is not original           # idempotent: one wrapper
        assert not issubclass(keyleak.FallbackRefused, Exception)
        with pytest.raises(keyleak.FallbackRefused):
            warnings.warn(keyleak.FALLBACK + ". API Key will be used instead. mock outage", stacklevel=1)
        with pytest.raises(UserWarning, match=keyleak.FALLBACK):              # the second lock
            original(keyleak.FALLBACK + ". reached another way", UserWarning, stacklevel=1)
        with pytest.warns(DeprecationWarning, match="anything else"):
            warnings.warn("anything else is a warning still", DeprecationWarning, stacklevel=1)


def test_every_condition_at_once_is_each_named(tmp_path):
    cwd, home = clean(tmp_path)
    (cwd / "ibm-credentials.env").write_text("x")
    (home / "ibm-credentials.env").write_text("x")
    (home / ".netrc").write_text("x")
    (home / "_netrc").write_text("x")
    env = dict.fromkeys([*keyleak.VARIABLES, "GLOBAL_SEARCH_URL", "X_DISABLE_SSL"], SECRET)
    found = keyleak.refusals(env, cwd, home, {"https": SECRET})
    assert len(found) == len(keyleak.VARIABLES) + 2 + 2 + 2 + 1
    assert not any(SECRET in f for f in found)

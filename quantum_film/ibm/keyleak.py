"""When a process that holds the IBM key refuses to start: docs/HARDWARE.md's key-leak list, as one function.

Each condition below redirects the key or the tokens, or switches off a TLS check, in the HTTP stack that
qiskit-ibm-runtime 0.50.0 drives (requests, ibm_cloud_sdk_core and the runtime's own RetrySession, all with
trust_env on). `refusals` is pure: it is handed the environment, the working and home directories and the
proxies, so tests reach it without qiskit and without touching the machine's own settings. The tools call it
with os.environ, os.getcwd(), os.path.expanduser("~") and urllib.request.getproxies(), before they import
qiskit. A message names the condition, never a value.

The service variables: ibm_cloud_sdk_core reads every variable whose name starts with a configured
service's name, upper-cased, as that service's settings (`_parse_key_and_update_config`). This stack
configures global_search and global_catalog for every account, and resource_controller when an instance is
given by name, not by CRN (qiskit_ibm_runtime's accounts/account.py and accounts/utils.py, 0.50.0; round 3's
P2). So any variable with one of the three prefixes is refused, whatever follows it (its URL, DISABLE_SSL and
the rest), and any *_DISABLE_SSL besides. A blanket *_URL rule is not used: no other *_URL is read, and this
desktop sets one (ANTHROPIC_BASE_URL) that would refuse every run.

Not refused, and why: QISKIT_IBM_TOKEN, QISKIT_IBM_URL and QISKIT_IBM_INSTANCE are not read when the token,
the channel and the instance are named (verifier-P0, round 3); QISKIT_IBM_RUNTIME_LOG_LEVEL alone writes no
file, and the client's log leaves headers out and redacts secrets (api/session.py, ibm_cloud_sdk_core's
LoggingFilter). QISKIT_IBM_RUNTIME_LOG_FILE is refused all the same, as docs/HARDWARE.md lists it.

THE FALLBACK. If IAM cannot issue a token, qiskit-ibm-runtime 0.50.0 warns "Unable to retrieve IBM Cloud access
token. API Key will be used instead." and sends `Authorization: apikey <key>` to the API host
(api/auth.py, CloudAuth.get_headers). `refuse_the_fallback` makes warnings.warn itself raise FallbackRefused on
that message, before the request that would carry the key is prepared, and keeps a warnings filter as a second
lock. FallbackRefused is a BaseException because the runtime's own `except Exception` handlers absorbed an
ordinary one: the run sent no key, but failed two minutes later as "No backend matches the criteria" (round 3's
P2, 16:58Z; the lead, 17:00Z). The same API as P2's hw_predict tool, so that one module holds both refusals.
"""
import os
import warnings

FALLBACK = "Unable to retrieve IBM Cloud access token"


class FallbackRefused(BaseException):
    """IAM could not issue a token, and the runtime would now send the raw key with only a warning. A
    BaseException, so that no `except Exception` in the runtime absorbs it."""


def refuse_the_fallback():
    """Two locks on IAM's apikey fallback, process-wide: warnings.warn raises FallbackRefused on that message,
    and a filter makes it an error should anything reach the warning another way. Idempotent."""
    warnings.filterwarnings("error", message=FALLBACK)
    original = warnings.warn
    if getattr(original, "refuses_the_fallback", False):
        return

    def warn(message, category=None, stacklevel=1, source=None, **kwargs):
        if str(message).startswith(FALLBACK):
            raise FallbackRefused(FALLBACK)
        return original(message, category, stacklevel + 1, source, **kwargs)

    warn.refuses_the_fallback = True
    warnings.warn = warn

VARIABLES = {
    "IAM_URL": "it redirects the IAM token exchange, the one request that carries the key",
    "IBM_CREDENTIALS_FILE": "it names a credentials file ibm_cloud_sdk_core reads service settings from",
    "VCAP_SERVICES": "ibm_cloud_sdk_core reads service credentials and settings from it",
    "REQUESTS_CA_BUNDLE": "requests trusts that CA bundle in place of its own",
    "CURL_CA_BUNDLE": "requests trusts that CA bundle in place of its own",
    "SSL_CERT_FILE": "OpenSSL trusts that certificate file",
    "SSL_CERT_DIR": "OpenSSL trusts the certificates in that directory",
    "NETRC": "requests sends the credentials of the netrc file it names",
    "SSLKEYLOGFILE": "urllib3 writes every TLS session's secrets to that file, the IAM exchange's included",
    "QISKIT_IBM_RUNTIME_LOG_FILE": "the client writes its log to that file (docs/HARDWARE.md, round 3's P2)",
}
SERVICE_PREFIXES = ("GLOBAL_SEARCH", "GLOBAL_CATALOG", "RESOURCE_CONTROLLER")
CREDENTIAL_FILES = ("ibm-credentials.env",)     # read from the working directory, then the home directory
NETRC_FILES = (".netrc", "_netrc")              # requests reads ~/.netrc, then Windows' ~/_netrc


def refusals(environ, cwd, home, proxies):
    """The named key-leak conditions that hold; [] means the runner may start. `environ` is a mapping of
    variable names (case is ignored, as on Windows), `proxies` what urllib.request.getproxies() returns."""
    out = []
    names = {str(k).upper(): str(k) for k in environ}
    for var, why in VARIABLES.items():
        if var in names:
            out.append(f"{var} is set: {why}")
    for upper in sorted(names):
        if upper.startswith(SERVICE_PREFIXES):
            out.append(f"{names[upper]} is set: ibm_cloud_sdk_core reads it as the settings of a service this stack "
                       "configures (its URL and its TLS check)")
        elif upper.endswith("_DISABLE_SSL"):
            out.append(f"{names[upper]} is set: a <SERVICE>_DISABLE_SSL switches a TLS check off")
    for where, d in (("working", cwd), ("home", home)):
        for f in CREDENTIAL_FILES:
            if os.path.exists(os.path.join(d, f)):
                out.append(f"{f} is in the {where} directory: ibm_cloud_sdk_core reads service settings from it")
    for f in NETRC_FILES:
        if os.path.exists(os.path.join(home, f)):
            out.append(f"{f} is in the home directory: requests sends a netrc file's credentials")
    if proxies:
        out.append(f"a proxy is configured for {sorted(proxies)} (urllib.request.getproxies(): the environment, "
                   "or on Windows the registry's system proxy); the key and every token would go through it")
    return out

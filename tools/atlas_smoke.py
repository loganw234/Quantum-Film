#!/usr/bin/env python3
"""Live Atlas smoke: the account answers, and the engine this project uses is listed.

Reads only (GET). Needs QF_ATLAS_AUTH (see quantum_film/atlas/client.py).
Prints the account's features, because what the account can do decides which
stages of the project can run at all.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from quantum_film.atlas.client import call  # noqa: E402

code, me = call("GET", "/api/v1/me", save=False)       # the body carries the email: not saved
if code != 200:
    print(f"GET /api/v1/me -> {code}")
    sys.exit(1)
print(f"account answers; features: {me.get('features')}")
code, body = call("GET", "/api/v1/engines?limit=200")
ids = [e.get("engine_id") for e in (body or {}).get("engines", [])]
if code != 200 or "tomography-api-v2" not in ids:
    print(f"GET /api/v1/engines -> {code}; tomography-api-v2 listed: {'tomography-api-v2' in ids}")
    sys.exit(1)
print(f"{len(ids)} engines visible, tomography-api-v2 among them")

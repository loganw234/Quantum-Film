"""Read-only survey of what this account can see. GET requests only."""
import json
import sys

from moth import call


def pages(path, key):
    items, cursor = [], None
    while True:
        q = path + (("&" if "?" in path else "?") + "cursor=" + cursor if cursor else "")
        code, body = call("GET", q, quiet=True)
        if code != 200:
            print(f"GET {q} -> {code}: {json.dumps(body)[:300]}")
            return items
        items += body.get(key) or []
        cursor = body.get("next_cursor")
        if not cursor:
            return items


for path in ("/api/v1/me/storage", "/api/v1/keys", "/api/v1/me/invitations", "/api/v1/orgs"):
    code, body = call("GET", path, quiet=True)
    print(f"GET {path} -> {code}: {json.dumps(body, ensure_ascii=False)[:700]}")

engines = pages("/api/v1/engines?limit=200", "engines")
print(f"\n== {len(engines)} engines visible")
for e in engines:
    print(f"  {e.get('engine_id'):28} v{e.get('version') or '?':8} credits={e.get('credits_per_run')!s:4} "
          f"owner={e.get('owner')!s:6} mode={e.get('execution_mode')!s:8} async={e.get('is_async')} "
          f"in={e.get('input_type')} out={e.get('output_type')} vis={e.get('visibility')} enabled={e.get('enabled')}")
missing = sorted({e.get("engine_id") for e in engines} - set(sys.argv[1:]))
json.dump(engines, open("engines_list.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)

jobs = pages("/api/v1/jobs?limit=200", "jobs")
print(f"\n== {len(jobs)} jobs on this account")
for j in jobs[:20]:
    print("  ", json.dumps(j)[:200])

shows = pages("/api/v1/showcases?limit=200", "showcases")
print(f"\n== {len(shows)} showcases visible")
for s in shows[:60]:
    print(f"  {s.get('title')!s:50} engine={s.get('engine_id')} owner_type={s.get('owner_type')} url={s.get('url')}")

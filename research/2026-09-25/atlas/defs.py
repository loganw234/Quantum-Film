"""Read full engine definitions (GET only) and print the fields that say how an
engine is built, queued and priced - the route to a custom engine."""

if __name__ != "__main__":
    raise ImportError("this script calls Atlas when it runs; run it, never import it (CLAUDE.md)")
import json
import sys

from moth import call

IDS = sys.argv[1:] or ["test-engine-submission-v1", "demo-callback-v1", "test-engine-v1",
                       "tomography-api-v2", "qdrive-api-v1", "coin-toss-v1"]
for eid in IDS:
    code, e = call("GET", f"/api/v1/engines/{eid}", quiet=True)
    print("=" * 90)
    if code != 200:
        print(eid, code, json.dumps(e)[:300])
        continue
    keep = {k: e.get(k) for k in ("engine_id", "name", "version", "owner", "owner_type", "created_by",
                                  "execution_mode", "queue", "is_async", "is_multipart", "input_type",
                                  "output_type", "input_files", "output_files", "steps", "run_policy",
                                  "credits_per_run", "has_estimate", "estimate", "has_estimate_fn",
                                  "estimate_needs_container", "has_validate_fn", "sidecar_endpoint",
                                  "error_codes", "registered_at", "updated_at")}
    print(json.dumps(keep, indent=1, ensure_ascii=False)[:2500])
    print("-- description:", (e.get("description") or "")[:1500])
    for cs in (e.get("code_samples") or [])[:3]:
        print(f"-- code sample [{cs.get('lang')}]:\n{(cs.get('source') or '')[:1200]}")
    ps = e.get("params_schema") or {}
    print("-- params:", list((ps.get("properties") or {}).keys()))

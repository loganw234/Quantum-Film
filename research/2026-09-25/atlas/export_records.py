"""Copy today's Atlas responses into the project as dated records, sanitised.

Removed on the way out, because a record is not a place for credentials or
personal data: every presigned URL (a bearer credential for its lifetime),
the /me body (it carries the account email and user id; the one fact taken
from it - features: [] - is stated in the ledger), and nothing else. The
bearer key was never in a response, and a scan below refuses the export if a
moth_ token or an X-Amz-Security-Token turns up anyway.
"""
import json
import pathlib
import re
import shutil

SRC = pathlib.Path(__file__).resolve().parent / "responses"
DST = pathlib.Path(__file__).resolve().parents[3] / "docs" / "records" / "2026-09-25" / "atlas"
DST.mkdir(parents=True, exist_ok=True)


def scrub(o):
    if isinstance(o, dict):
        return {k: ("<presigned url removed>" if k in ("url", "download_url") else scrub(v))
                for k, v in o.items()}
    if isinstance(o, list):
        return [scrub(v) for v in o]
    return o


n = 0
for f in sorted(SRC.glob("*.json")):
    if f.name.endswith("_GET_api_v1_me.json"):
        continue
    rec = json.loads(f.read_text(encoding="utf-8"))
    rec = scrub(rec)
    text = json.dumps(rec, indent=1, ensure_ascii=False)
    if re.search(r"moth_[A-Za-z0-9]{8,}|X-Amz-Security-Token|logan@", text):
        raise SystemExit(f"REFUSED: {f.name} still carries a credential or the account email")
    (DST / f.name).write_text(text + "\n", encoding="utf-8", newline="\n")
    n += 1
for f in sorted(SRC.glob("qdrive-output-*.txt")):
    shutil.copyfile(f, DST / f.name)
    n += 1
print(f"{n} records written to {DST}")

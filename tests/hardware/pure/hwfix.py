"""Helpers for the hardware tests that run without qiskit: raw payloads in the runtime's own JSON encoding,
the committed fixture (a bundle frozen against fake_kingston and a dry run of both its jobs), and re-sealing
a planted bundle so that only the check under test can refuse it.

The fixture was made by tools/hw_bundle.py and tools/hw_run.py --dry-run (tests/hardware/fixture/MADE.txt
says how); the qiskit stage makes a fresh one on every run and holds it to the same audit.
"""
import base64
import io
import json
import pathlib
import shutil
import zlib

import numpy as np

from quantum_film import fixer
from quantum_film.ibm import bundle

ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests" / "hardware" / "fixture"
KNOWN = "0001000010001011"          # X on {0, 1, 3, 7, 12}, as a sampler writes it (tests/decode/test_ibm_decode.py)


def bits_array(strings, num_bits=16):
    """Sampler bitstrings as a BitArray's bytes: uint8 (shots, ceil(bits / 8)), big-endian."""
    width = (num_bits + 7) // 8
    return np.array([list(int(s, 2).to_bytes(width, "big")) for s in strings], dtype=np.uint8).reshape(-1, width)


def ndarray(arr):
    buf = io.BytesIO()
    np.save(buf, arr, allow_pickle=False)
    return {"__type__": "ndarray", "__value__": base64.standard_b64encode(zlib.compress(buf.getvalue())).decode()}


def encode_raw(pubs, result_metadata=None, num_bits=16):
    """[(bitstrings, pub metadata), ...] as the raw result text of a sampler job (RuntimeEncoder's form)."""
    results = []
    for strings, meta in pubs:
        bits = {"__type__": "BitArray", "__value__": {"array": ndarray(bits_array(strings, num_bits)),
                                                       "num_bits": num_bits}}
        results.append({"__type__": "SamplerPubResult", "__value__": {
            "data": {"__type__": "DataBin", "__value__": {"field_names": ["meas"], "shape": [],
                                                           "fields": {"meas": bits}}},
            "metadata": meta}})
    return json.dumps({"__type__": "PrimitiveResult",
                       "__value__": {"pub_results": results, "metadata": result_metadata or {"version": 2}}})


def copy_fixture(dest, run=True):
    """The committed fixture, copied under dest: dest/bundle and (with `run`) dest/run. -> (bundle dir, run dir
    or None). A test that runs jobs of its own copies the bundle alone: the committed run's lines already hold
    the bundle's commitments, and once-only would refuse a second set."""
    shutil.copytree(FIXTURE / "bundle", dest / "bundle")
    if run:
        shutil.copytree(FIXTURE / "run", dest / "run")
    return dest / "bundle", (dest / "run" if run else None)


def manifest(bundle_dir):
    return bundle.load(bundle_dir)[0]


def reseal(bundle_dir, change=None):
    """Re-seal a bundle after a planted change: every file's SHA-256 and every commitment recomputed from
    the files as they now are, then the manifest rewritten in its canonical form. -> the manifest."""
    bundle_dir = pathlib.Path(bundle_dir)
    m = manifest(bundle_dir)
    if change:
        change(m)
    for j in m["jobs"]:
        for e in j["circuits"]:
            for part, suffix in bundle.SUFFIX.items():
                key = "circuit_sha256" if part == "circuit" else f"{part}_sha256"
                e[key] = bundle.sha256((bundle_dir / (e["name"] + suffix)).read_bytes())
            e["commitment"] = bundle.commitment(m, e)
    m["readme_sha256"] = bundle.sha256((bundle_dir / bundle.README).read_bytes())
    (bundle_dir / bundle.MANIFEST).write_bytes(bundle.text(m).encode("ascii"))
    return m


def write_doc(path, doc):
    path.write_bytes(bundle.text(doc).encode("ascii"))


def read_doc(path):
    return bundle.load_json(path.read_bytes())


def resealed_record(path, change):
    """A record file re-sealed after `change(record)`: its digest recomputed, its bytes canonical."""
    rec = json.loads(path.read_text(encoding="ascii"))
    change(rec)
    rec["digest"] = fixer.digest(rec)
    path.write_bytes(fixer.text(rec).encode("ascii"))
    return rec

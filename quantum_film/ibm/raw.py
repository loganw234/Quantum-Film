"""A sampler job's raw result payload, read without qiskit: each PUB's bitstrings and metadata.

The runner writes the payload to disk the moment it arrives, before anything decodes it: the text that
qiskit-ibm-runtime 0.50.0's `job._api_client.job_results(job_id)` returns (the body of GET /jobs/{id}/results).
For the sampler program that text is JSON in the runtime's own encoding (qiskit_ibm_runtime.RuntimeEncoder):
    {"__type__": "PrimitiveResult", "__value__": {"pub_results": [
        {"__type__": "SamplerPubResult", "__value__": {
            "data": {"__type__": "DataBin", "__value__": {"fields": {"meas": {
                "__type__": "BitArray", "__value__": {"num_bits": 16,
                    "array": {"__type__": "ndarray", "__value__": base64(zlib(numpy.save(uint8 (shots, 2))))}}}},
                "field_names": ["meas"], "shape": []}},
            "metadata": {"shots": ..., "circuit_metadata": {...}, ...}}}, ...],
     "metadata": {...}}}
`pubs` reads that and nothing else: anything else is refused by name. A BitArray's bytes, each row read most
significant bit first, ARE the sampler's bitstring (verifier-P0 measured it; decode.py states it), so the
strings here are the ones BitArray.get_bitstrings() gives. The qiskit stage holds the two to each other on
every payload a dry run makes, and the runner holds them on every payload it fixes.

This is how the records test reads a committed run's counts from its raw bytes, offline, as
tests/circuits/test_p3_records.py reads Atlas's committed results.
"""
import base64
import io
import json
import zlib

import numpy as np


class RawRefusal(ValueError):
    """A raw payload this reader does not read."""


def _typed(obj, name, where):
    if not (isinstance(obj, dict) and obj.get("__type__") == name and "__value__" in obj):
        raise RawRefusal(f"{where}: not a {name}")
    return obj["__value__"]


def _ndarray(obj, where):
    value = _typed(obj, "ndarray", where)
    if not isinstance(value, str):
        raise RawRefusal(f"{where}: an ndarray that is not numpy.save bytes")
    try:
        data = zlib.decompress(base64.b64decode(value.encode("ascii"), validate=True))
        return np.load(io.BytesIO(data), allow_pickle=False)
    except (ValueError, zlib.error, OSError) as e:
        raise RawRefusal(f"{where}: an ndarray that does not decode ({type(e).__name__})") from None


def pubs(raw_text, num_bits=16, register="meas"):
    """[(bitstrings, metadata), ...] per PUB, in the payload's order, from the raw result text."""
    try:
        top = json.loads(raw_text)
    except (ValueError, RecursionError) as e:
        raise RawRefusal(f"the payload is not JSON ({type(e).__name__})") from None
    value = _typed(top, "PrimitiveResult", "result")
    if not isinstance(value, dict) or not isinstance(value.get("pub_results"), list):
        raise RawRefusal("result: no list of pub_results")
    out = []
    for i, pub in enumerate(value["pub_results"]):
        where = f"pub {i}"
        v = _typed(pub, "SamplerPubResult", where)
        if not (isinstance(v, dict) and isinstance(v.get("metadata", {}), dict)):
            raise RawRefusal(f"{where}: no data and metadata")
        data = _typed(v.get("data"), "DataBin", f"{where} data")
        fields = data.get("fields") if isinstance(data, dict) else None
        if not (isinstance(fields, dict) and list(fields) == [register] and data.get("shape") == []):
            raise RawRefusal(f"{where}: the data is not exactly one register {register!r} of shape ()")
        bits = _typed(fields[register], "BitArray", f"{where} {register}")
        if not (isinstance(bits, dict) and set(bits) == {"array", "num_bits"} and bits["num_bits"] == num_bits):
            raise RawRefusal(f"{where}: {register} is not a BitArray of {num_bits} bits")
        arr = _ndarray(bits["array"], f"{where} {register} array")
        width = (num_bits + 7) // 8
        if arr.dtype != np.uint8 or arr.ndim != 2 or arr.shape[1] != width:
            raise RawRefusal(f"{where}: the bits are not uint8 of shape (shots, {width}); {arr.dtype} {arr.shape}")
        strings = ["".join(f"{b:08b}" for b in row)[-num_bits:] for row in arr.tolist()]
        out.append((strings, v.get("metadata", {})))
    return out

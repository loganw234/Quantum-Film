"""A sampler job's raw result, read without qiskit (quantum_film.ibm.raw): the reader the records test uses to
hold every committed record to the bytes IBM returned."""
import json

import pytest
from hwfix import KNOWN, encode_raw, ndarray

from quantum_film.ibm import decode, raw


def test_the_known_answer_reads_back_as_its_string_and_its_set():
    text = encode_raw([([KNOWN, KNOWN, "0" * 16], {"shots": 3, "circuit_metadata": {"qf_commitment": "ab" * 32}})])
    ((strings, meta),) = raw.pubs(text)
    assert strings == [KNOWN, KNOWN, "0" * 16]
    assert decode.ones(strings[0], 16) == (0, 1, 3, 7, 12)
    assert meta["circuit_metadata"]["qf_commitment"] == "ab" * 32


def test_the_bytes_read_most_significant_bit_first_are_the_string():
    """BitArray stores the known answer as the bytes 0x10 0x8b; read MSB first they ARE the string
    (decode.py; verifier-P0 measured it). Read LSB first they would not be."""
    import numpy as np
    arr = np.array([[0x10, 0x8B]], dtype=np.uint8)
    payload = json.loads(encode_raw([([KNOWN], {})]))
    payload["__value__"]["pub_results"][0]["__value__"]["data"]["__value__"]["fields"]["meas"]["__value__"][
        "array"] = ndarray(arr)
    ((strings, _),) = raw.pubs(json.dumps(payload))
    assert strings == [KNOWN] and "".join(f"{b:08b}"[::-1] for b in (0x10, 0x8B)) != KNOWN


def test_pubs_keep_their_order():
    text = encode_raw([(["1" * 16], {"p": 0}), (["0" * 16], {"p": 1}), ([KNOWN], {"p": 2})])
    assert [(s, m["p"]) for s, m in raw.pubs(text)] == [(["1" * 16], 0), (["0" * 16], 1), ([KNOWN], 2)]


def _mutated(path, value):
    payload = json.loads(encode_raw([([KNOWN], {})]))
    node = payload
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    return json.dumps(payload)


PUB = ["__value__", "pub_results", 0, "__value__"]
DATA = PUB + ["data", "__value__"]
BITS = DATA + ["fields", "meas", "__value__"]


REFUSED = {
    "not-json": ("not json", "not JSON"),
    "not-a-primitive-result": (json.dumps({"__type__": "PubResult", "__value__": {}}), "result: not a PrimitiveResult"),
    "no-pub-list": (_mutated(["__value__", "pub_results"], {}), "no list of pub_results"),
    "not-a-sampler-pub": (_mutated(PUB[:-1] + ["__type__"], "PubResult"), "pub 0: not a SamplerPubResult"),
    "two-registers": (_mutated(DATA + ["fields"], {"meas": None, "other": None}), "not exactly one register 'meas'"),
    "a-shaped-bin": (_mutated(DATA + ["shape"], [2]), "not exactly one register 'meas' of shape ()"),
    "fifteen-bits": (_mutated(BITS + ["num_bits"], 15), "is not a BitArray of 16 bits"),
    "not-base64": (_mutated(BITS + ["array", "__value__"], "!!"), "does not decode"),
    "three-bytes": (_mutated(BITS + ["array"], ndarray(__import__("numpy").zeros((1, 3), dtype="uint8"))),
                    "shape (shots, 2)"),
    "int64": (_mutated(BITS + ["array"], ndarray(__import__("numpy").zeros((1, 2), dtype="int64"))), "are not uint8"),
}


@pytest.mark.parametrize("text, needle", list(REFUSED.values()), ids=list(REFUSED))
def test_anything_else_is_refused_by_name(text, needle):
    with pytest.raises(raw.RawRefusal) as refusal:
        raw.pubs(text)
    assert needle in str(refusal.value)

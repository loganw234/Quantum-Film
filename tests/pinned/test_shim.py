"""The ctypes shim over libcft: where it looks, what it binds, and that each call means what cft.h says."""
import hashlib
import threading
from fractions import Fraction

import numpy as np
import pytest

from quantum_film.pinned import cft
from quantum_film.pinned.cft import DOT, FP64, RDN, RNE, RUP, SUM
from quantum_film.pinned.encode import round_fraction, to_fraction


def test_the_library_is_the_one_qf_cft_root_names_and_its_abi_is_0_14():
    path, sha, abi = cft.identity()
    assert abi == "0.14" and len(sha) == 64
    assert path == str(cft.library_path()) and cft.library_path().parents[1] == cft.cft_root()


def test_a_missing_library_is_refused_by_name(monkeypatch, tmp_path):
    monkeypatch.setenv("QF_CFT_ROOT", str(tmp_path))
    monkeypatch.setattr(cft, "_LIB", None)
    with pytest.raises(cft.LibcftMissing, match="not built"):
        cft.lib()


def test_sha256_is_fips_180_4():
    for msg in (b"", b"abc", b"quantum-film/uniform/v1|s4:roll|s5:pauli|i1|0", bytes(range(256)) * 9):
        assert cft.sha256(msg) == hashlib.sha256(msg).digest()


def test_reduce_seg_is_reduce_over_each_segment():
    rng = np.random.default_rng(7)
    a, b = rng.standard_normal(6 * 25), rng.standard_normal(6 * 25)
    for op in (DOT, SUM):
        for rnd in (RNE, RDN, RUP):
            bb = b if op == DOT else None
            seg = cft.reduce_seg(op, FP64, rnd, a, bb, 25)
            one = np.concatenate([cft.reduce(op, FP64, rnd, a[k * 25:(k + 1) * 25],
                                             None if bb is None else bb[k * 25:(k + 1) * 25]) for k in range(6)])
            assert seg.tobytes() == one.tobytes(), (op, rnd)


def tree(leaves, rnd):
    """cft.h's reduction tree over exact leaves, every node rounded under rnd: the left child of a range is the
    largest power of two strictly below its length (python/cft_golden/reduce.py's split)."""
    def node(lo, hi):
        if hi - lo == 1:
            return leaves[lo]
        mid = lo + (1 << ((hi - lo - 1).bit_length() - 1))
        return to_fraction(FP64, round_fraction(node(lo, mid) + node(mid, hi), FP64, rnd))
    return node(0, len(leaves)) if leaves else Fraction(0)


def dot_replica(a, b, rnd):
    """sum(round(a[i] * b[i])) over the tree: every product rounded under rnd, then every node."""
    return tree([to_fraction(FP64, round_fraction(Fraction(x) * Fraction(y), FP64, rnd))
                 for x, y in zip(a, b, strict=True)], rnd)


def test_dot_rounds_every_product_over_the_fixed_tree_and_is_not_an_fma_chain():
    """The one dot form this package uses (cft.h:247). An fma chain, one rounding per term, gives other bits."""
    rng = np.random.default_rng(3)
    fma_differs = 0
    for n in (1, 2, 3, 5, 7, 16, 25, 33):
        for _ in range(12):
            a, b = rng.standard_normal(n), rng.standard_normal(n)
            for rnd in (RNE, RDN, RUP):
                got = to_fraction(FP64, cft.reduce(DOT, FP64, rnd, a, b))
                assert got == dot_replica(a, b, rnd), (n, rnd)
            acc = Fraction(0)
            for x, y in zip(a, b, strict=True):
                acc = to_fraction(FP64, round_fraction(acc + Fraction(x) * Fraction(y), FP64, RNE))
            fma_differs += acc != to_fraction(FP64, cft.reduce(DOT, FP64, RNE, a, b))
    assert fma_differs > 0


def test_each_operand_sits_where_cft_h_reads_it():
    three, one = np.array([3.0]), np.array([1.0])
    assert cft.sub(FP64, RNE, three, one)[0] == 2.0            # SUB reads a and c: a - c
    assert cft.add(FP64, RNE, three, one)[0] == 4.0
    assert cft.mul(FP64, RNE, three, one)[0] == 3.0            # MUL reads a and b
    assert cft.fma(FP64, RNE, three, three, one)[0] == 10.0    # a * b + c
    assert cft.less(FP64, one, three)[0] and not cft.less(FP64, three, one)[0]
    assert cft.div(FP64, RNE, three, one)[0] == 3.0


def test_the_rounding_attribute_reaches_the_library():
    third = (np.array([1.0]), np.array([3.0]))
    lo, near, hi = (to_fraction(FP64, cft.div(FP64, r, *third)) for r in (RDN, RNE, RUP))
    assert lo < Fraction(1, 3) < hi and near in (lo, hi) and lo != hi


def test_a_nan_a_pole_or_an_overflow_is_refused_by_name():
    with pytest.raises(cft.CftError, match="divide-by-zero"):
        cft.div(FP64, RNE, np.array([1.0]), np.array([0.0]))
    with pytest.raises(cft.CftError, match="invalid"):
        cft.sqrt(FP64, RNE, np.array([-1.0]))
    with pytest.raises(cft.CftError, match="overflow"):
        cft.mul(FP64, RNE, np.array([1e300]), np.array([1e300]))


def test_numpy_is_never_asked_to_change_a_format():
    with pytest.raises(TypeError, match="cft_convert"):
        cft.add(FP64, RNE, np.float32([1.0]), np.float32([1.0]))
    with pytest.raises(TypeError, match="cft_convert"):
        cft.add(cft.FP32, RNE, np.array([1.0]), np.array([1.0]))


def test_a_call_from_another_thread_is_refused():
    cft.device()                                   # the device is this (the main) thread's
    caught = []

    def work():
        try:
            cft.add(FP64, RNE, np.array([1.0]), np.array([1.0]))
        except cft.ThreadRefusal as e:
            caught.append(e)

    t = threading.Thread(target=work)
    t.start()
    t.join()
    assert len(caught) == 1

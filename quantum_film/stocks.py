"""The shelf: every stock this project defines, in one table.

A stock here is the LAW of a crystal field: the probability distribution its
crystal layouts are drawn from, on a periodic tile of L x L crystal sites.
Everything after coating (the characteristic curve, the grain's area, the MTF)
is borrowed by reference from a named atlas-film stock, so the count law and
the density scale stay sourced and only the placement of the crystals is new.

This table is the ONLY place a stock's parameters are written. The golden
model, the circuits, the fixer and the docs read them from here, and
tests/golden/test_stocks.py holds the table to the admission rules below.

ADMISSION: "physically plausible". A stock's law must be the measurement
distribution of a physically realisable quantum state, one a circuit can
prepare. Every parameter is either DERIVED from the table's other entries or
an OPERATOR'S NUMBER: chosen, not sourced, named as such wherever it appears,
and given a stated range. atlas-film's halation strength is the precedent: a
number nobody has published, owned by whoever sets it.

UNIQUE: a stock is "unique" when a film-science statistic measured on it falls
outside what a silver-halide emulsion gives. `unique_because` names the
statistic; docs/STOCKS.md records the measurement.

STATUS: "shelf" stocks have an authority in quantum_film.golden and can be
coated. "planned" stocks are declared so their parameters have one home, and
a request to coat one is refused by name.
"""

OPERATOR = "operator"   # chosen, not sourced
DERIVED = "derived"     # a function of other entries in this table


def _op(value, why, low, high):
    return {"value": value, "kind": OPERATOR, "why": why, "range": (low, high)}


STOCKS = {
    "pauli": {
        "name": "Pauli",
        "status": "shelf",
        "family": "determinantal",
        "law": "free fermions filling a Fermi disc of plane waves on a periodic tile; measuring "
               "every site's occupation lays the crystals as a projection determinantal point process",
        "L": _op(16, "crystal sites along a tile edge", 4, 64),
        "fermi_r2": _op(8, "the Fermi disc |k|^2 <= r2, k in units of 2*pi/L: sets the crystal count "
                           "and the length over which crystals repel", 0, 64),
        "borrows": "trix",
        "authority": "quantum_film.golden.fermi",
        "unique_because": "hyperuniform grain: the structure factor S(k) falls to 0 as k -> 0, which the "
                          "near-Poisson placement of a silver-halide emulsion never gives",
    },
    "pauli-4x4": {
        "name": "Pauli, 16-qubit tile",
        "status": "shelf",
        "family": "determinantal",
        "law": "the Pauli law on a 4 x 4 tile: small enough for one qubit per site on hardware today",
        "L": _op(4, "crystal sites along a tile edge, one qubit per site", 4, 4),
        "fermi_r2": _op(1, "the Fermi disc |k|^2 <= r2 on the 4 x 4 torus", 0, 1),
        "borrows": "trix",
        "authority": "quantum_film.golden.fermi",
        "unique_because": "as Pauli, at the size a circuit lays directly",
    },
    "poisson": {
        "name": "Poisson (reference)",
        "status": "shelf",
        "family": "binomial",
        "law": "N sites uniformly without replacement: the fixed-count lattice twin of atlas-film's "
               "classical Poisson crystal field, and the baseline every other stock is measured against",
        "L": {"value": "pauli", "kind": DERIVED, "why": "the same tile as Pauli, so they compare at equal density"},
        "count": {"value": "pauli", "kind": DERIVED, "why": "Pauli's crystal count on that tile"},
        "borrows": "trix",
        "authority": "quantum_film.golden.binomial",
        "unique_because": None,
    },
    "speckle": {
        "name": "Speckle",
        "status": "planned",
        "family": "cox",
        "law": "Born-rule shots of a random pupil state on the low bits of two momentum registers, "
               "then a 2D quantum Fourier transform; each shot is a crystal, the first N distinct sites "
               "the roll",
        "L": {"value": "pauli", "kind": DERIVED, "why": "the same tile as Pauli"},
        "pupil_bits": _op(3, "low-order momentum bits per register the pupil occupies", 1, 4),
        "borrows": "trix",
        "authority": None,
        "unique_because": "grain contrast equals the machine's fidelity p (linear XEB): each roll records "
                          "the hardware that exposed it",
    },
}


def params(stock_id):
    """Resolve a stock's parameters to plain values, following DERIVED links.
    Refuses by name an unknown stock or a stock without an authority."""
    if stock_id not in STOCKS:
        raise KeyError(f"unknown stock {stock_id!r}; the shelf is {sorted(STOCKS)}")
    s = STOCKS[stock_id]
    if s["status"] != "shelf":
        raise LookupError(f"stock {stock_id!r} is {s['status']}: it has no authority yet, so it cannot "
                          f"be coated (docs/ROADMAP.md)")

    def val(entry, key):
        e = entry[key]
        if e["kind"] == DERIVED:
            return params(e["value"])[key if key != "count" else "N"]
        return e["value"]

    out = {"id": stock_id, "family": s["family"], "L": val(s, "L"), "borrows": s["borrows"]}
    if s["family"] == "determinantal":
        out["fermi_r2"] = val(s, "fermi_r2")
        out["N"] = len(fermi_disc(out["L"], out["fermi_r2"]))
    elif s["family"] == "binomial":
        out["N"] = val(s, "count")
    out["M"] = out["L"] * out["L"]
    return out


def fermi_disc(L, r2):
    """The momenta k = (kx, ky), kx and ky in [-L/2, L/2), with |k|^2 <= r2, in one
    fixed order. This is integer arithmetic only, and so it lives here beside the
    table rather than in any one implementation. A disc reaching the Nyquist row
    is refused: there k and -k are the same mode mod L, and the real basis every
    implementation builds would count it twice."""
    half = L // 2
    ks = [(kx, ky) for kx in range(-half, L - half) for ky in range(-half, L - half)
          if kx * kx + ky * ky <= r2]
    if any(kx == -half or ky == -half for kx, ky in ks):
        raise ValueError(f"the disc r2={r2} reaches the Nyquist frequency on L={L}; use r2 < {half * half}")
    return sorted(ks, key=lambda k: (k[0] * k[0] + k[1] * k[1], k))

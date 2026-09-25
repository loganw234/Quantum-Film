# The shelf

What each stock is, what makes it physically plausible, and what makes it
unlike any film that was ever coated. The parameters themselves live only in
`quantum_film/stocks.py`; this file explains them and never restates a value
that code reads.

## Two rules every stock obeys

**Physically plausible.**
- A stock's law must be the measurement distribution of a quantum state that a
  circuit can prepare. It is admitted to the shelf only once it has an
  authority: an exact sampler in `quantum_film/golden`.
- Every parameter is either derived from the table or an **operator's
  number**. An operator's number is chosen, not sourced; it is named as such
  and given a stated range. atlas-film's halation strength is the precedent:
  a number nobody ever published, owned by whoever sets it.
- Everything after coating is borrowed by reference from a real atlas-film
  stock (`borrows`): the characteristic curve, the grain's projected area and
  the MTF. So the count law and the density scale stay sourced, and only the
  placement of the crystals is new.

**Unique.** A stock earns the word only when a film-science statistic measured
on it falls outside what a silver-halide emulsion gives. The statistics that
can tell grain types apart are:
- the pair correlation g(r) of crystal centres, before development;
- the structure factor S(k), or equivalently the noise power spectrum at low
  frequency;
- a Selwyn plot, sigma * sqrt(A) across at least one decade of aperture.

A single RMS granularity reading at 48 um cannot tell them apart, because it
mixes density, grain size and correlation into one number
(research/2026-09-25/notes/quantum-film-physics.md).

## On the shelf

### Pauli

- **The law.** Free fermions fill the N lowest plane-wave modes, a Fermi disc,
  of a periodic tile of crystal sites. Measuring every site lays a
  determinantal point process: crystals repel, and at most one sits on each
  site.
- **Why real film never did this.** An emulsion places its crystals very
  nearly at random, with S(k) about 1 at low frequency. Pauli's S(k) falls
  towards zero: the grain is hyperuniform. Selwyn's law breaks downward, and
  the grain looks finer than its crystal count predicts.
- **Measured (2026-09-25, prototype, classical simulation, 12.5% filling):**
  - g at the nearest site: 0.47;
  - S(k) at the lowest k: 0.076;
  - count variance over mean in a 16x16 window: 0.18 (Poisson: 0.78).
- **The operator's numbers.** `L`, the sites along a tile's edge, and
  `fermi_r2`, the disc radius squared in units of (2 pi / L)^2. Together
  they set N and the length over which crystals repel.
- **The authority** is `quantum_film/golden/fermi.py`. It is checked by
  normalisation (all layouts of the 4x4 tile sum to 1), orthonormality, and
  precision independence.
- **The circuit** is `quantum_film/circuits/givens.py`, held to the
  authority's kernel to 1e-12 on a local statevector. For the 16-qubit tile
  it has 59 rotations and 236 CNOTs.
  - **It has not run on Atlas yet.** The tile Atlas ran on 2026-09-25 was a
    research prototype with a different law: an open box's standing waves,
    in snake order (docs/VALIDATION.md).

### Pauli, 16-qubit tile

The Pauli law on a 4x4 tile: one qubit per site, small enough to lay directly
on a device today. It is a separate stock because the tile size is part of the
law.

### Poisson (reference)

N sites uniformly without replacement, on Pauli's tile at Pauli's count. It is
the lattice twin of atlas-film's classical Poisson crystal field, and the
baseline every other stock is measured against. It is not unique, by design.

## Planned

### Speckle

- **The law.** Born-rule shots of a random pupil state on the low bits of two
  momentum registers, sent through a 2D quantum Fourier transform. That is
  Fraunhofer speckle made with qubits. Each shot is a crystal.
- **What makes it unique.** Crystals bunch: g(0) = 1 + p^2. Above all, the
  grain's contrast equals p, the fidelity of the machine that exposed it,
  which is its linear cross-entropy score (Google's "speckle purity").
  Every roll exposed on hardware records the hardware in its grain.
- **Its authority, before admission**: exact output probabilities from the
  statevector at 256 bits.

## The unique-stock programme

These are candidates, not promises. Each needs an authority, a circuit, and a
measured statistic before it reaches the shelf.

- **Pauli tripack (colour).** atlas-film's colour chain coats three layers,
  each with independent grain, and its own test holds the layers
  uncorrelated (|rho| < 0.35). In a Pauli tripack, one fermionic state spans
  (site x layer) modes, so crystals repel across layers too. The result is
  colour grain whose channels are anticorrelated: a crystal in the red layer
  makes one in the green layer at the same place less likely. No real colour
  film does this, and it is the same physics as Pauli with three times the
  modes.
- **Pauli-streak.** An elliptical Fermi disc gives directional grain. Real
  grain is isotropic; anisotropic Fermi surfaces are ordinary in real
  crystals.
- **Quantum light.** Expose with antibunched (sub-Poissonian) light, which
  resonance fluorescence produces. The exposure noise then falls below shot
  noise before any crystal is involved.
- **Rydberg voids (stretch).** A blockaded Rydberg array (QuEra Aquila, on
  Braket) behaves as a Poisson-disk sampler. It would give the most
  photographic grain of all, but it has no exact check at 256 atoms, so it
  stays off the shelf until it has one.

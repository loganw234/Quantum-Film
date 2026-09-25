# The determinism contract

What Quantum-Film promises about every crystal and every print, stated so that
someone who trusts none of this code can check it. Written 2026-09-25, the day
the project began; each claim names its evidence, and the evidence that is
still missing.

## The promise

**The Born rule is not made deterministic.** Nothing can do that. A roll laid
by a device is unique. What this project makes deterministic is everything
around the shot:

1. **An emulated roll is a function of (stock, seed) alone.** The same stock
   and seed give the same crystal layout, the same negative record byte for
   byte, and so the same digest, on any machine.
2. **A fixed record is permanent.** Its digest is re-derived from its own
   bytes, and a changed byte, a changed law or a missing provenance field is
   refused by name.
3. **A print will be a function of its record.** (Planned.) Development will
   borrow atlas-film's sourced organs, with every rounding operation pinned
   (libcft) and every transcendental built into a table once. Nothing is
   claimed for this layer until it exists.

## Why arithmetic cannot decide an emulated roll

The authority, `quantum_film/golden`, lays a roll from:
- **uniforms** that are the first 8 bytes of a SHA-256, exact dyadic
  rationals, the same wherever SHA-256 is SHA-256;
- **integer arithmetic** for everything combinatorial, including which
  momenta are in the Fermi disc;
- **mpmath at 256 bits** for the irrational parts: cos, sin and square roots
  of the basis, and the chain rule's projections.

The only place rounding could choose a crystal is a draw whose target
u * total lands near a boundary between two sites' cumulative weights. The
authority decides a draw only when the target is at least 2^-224 from every
boundary, and REFUSES it otherwise (`TieRefusal`, tested by forcing a target
exactly onto a boundary).

**The argument.** Two implementations whose total error in the cumulative
weights stays below half that margin make the same decision on every draw
that is not refused. So the roll does not depend on the implementation:
- not on the platform;
- not on the libm (none is used);
- not on the working precision, provided that precision is high enough.

**The check on the argument.** The same rolls are laid at 256 and at 320 bits
and must be identical (tests/test_golden_fermi.py). If they ever differ, the
argument is wrong somewhere, and that test is where it will show.

## What is NOT promised

- **A device roll is not reproducible.** That covers Atlas's emulator and any
  QPU. It is recorded, with `fixed_at` and its provenance, and read; it is never
  re-run. The census of 2026-09-25 found that identical Atlas requests
  returned different bytes wherever sampling was involved, and that seeds pin
  circuits, not shots.
- **The numpy float path is not a column of this contract.** It rounds without
  pinning. On 2026-09-25, binary32 parted 2 of 40 fermion films from the
  binary64 reference; binary64 parted none of 80 comparisons. "None of 80" is
  not "never".
- **A circuit is scored, not trusted.** Its statistics are held to the
  authority's kernel: exactly on a local statevector, and with standard errors
  on an emulator or device.

## Evidence, and its gaps

| claim | evidence | gap |
|---|---|---|
| an emulated roll is f(stock, seed) | `fixer.reproduce`; tests/vectors regenerate byte for byte on every run; 256 and 320 bits lay the same rolls | **one machine so far**: Windows 11, Python 3.12.9, mpmath 1.3.0. Running `make verify-quick` anywhere else regenerates the vectors and compares bytes, so a second machine is the next evidence and costs one command. |
| records are permanent | `fixer.check` on every rule; the runner's negative control, a moved crystal the fixer must refuse | none known |
| the circuit lays the Pauli law | local statevector against the golden kernel to 1e-12; three sabotages fail it; on Atlas, 120 pair statistics within 2.21 sigma | the circuit is not yet hardware-shaped (docs/ROADMAP.md) |
| mpmath is accurate enough | the precision test above | a different mpmath version is a claim to test, not assume |

## Versioning

- A negative record names its format, `quantum-film/negative/v1`, and carries
  the law it was laid under.
- The uniforms' domain string is `quantum-film/uniform/v1`.
- Changing either one changes every digest. That change is made deliberately:
  a new version string, and `make vectors`. It is never made in place.

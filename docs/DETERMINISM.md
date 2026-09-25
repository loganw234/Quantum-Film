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
   and seed give the same crystal layout on any machine. From the same
   version of this package they also give the same negative record, byte for
   byte, and so the same digest: a record names the version that fixed it.
2. **A fixed record is permanent.** On disk it is exactly its canonical
   text. Its digest is re-derived from its content. A changed byte, a
   duplicated key, a changed law or a missing provenance field is refused by
   name.
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
boundary, and REFUSES it otherwise (`TieRefusal`).

**The argument.** Two implementations whose error in (boundary - target)
stays below half that margin make the same decision on every draw that is
not refused. So the roll does not depend on the implementation:
- not on the platform;
- not on the libm (none is used);
- not on the working precision, provided that precision is high enough.

**The checks on the argument** (tests/golden/test_golden_fermi.py):
- **Its premise, measured.** Along real rolls, draw by draw, every 256-bit
  target and boundary is compared with the same roll at 512 bits. The worst
  error was 2^-248.8 on 2026-09-25, against the 2^-224 margin. The gate
  demands 2^16 of headroom, and 2^24.8 was measured.
- **The refusal, planted.** A target 2^-240 past a boundary must be refused:
  that is inside the margin, and too far from the boundary for rounding to
  move. So the gate fails if the margin shrinks below the arithmetic's own
  error, or if the refusal goes. A target 2^-200 past must be decided, and
  go past the boundary.
- **Its precision, held.** mpmath's working precision is process-global, so
  another thread could turn the authority into binary64 arithmetic behind
  the same margin. Every draw checks its precision and refuses by name
  (`PrecisionChanged`). The authority is not to be called from threads.

The first check on the argument laid the same rolls at 256 and 320 bits. It
could not fail: random seeds come no closer than about 2^-15 to a boundary,
so it passed with the refusal removed, and with a margin below the
arithmetic's own error (the P0 verifier, 2026-09-25).

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
| an emulated roll is f(stock, seed) | `fixer.reproduce`; tests/vectors regenerate byte for byte on every run; the margin's premise measured at 512 bits | **one CPU so far.** Windows 11 (Python 3.12.9, mpmath 1.3.0), and WSL2 Ubuntu 22.04 on the same desktop (Python 3.10.12, mpmath 1.4.1), where the P0 verifier regenerated the vectors byte for byte. Running `make verify-quick` on another machine is the next evidence, and costs one command. |
| records are permanent | `fixer.check` on every rule; a file is exactly its canonical text; the runner's control, a moved crystal the fixer's command line must refuse by its digest, and its twin, which the command line must accept | a device roll's commitment proves what it binds, not when it was made, and not which law its circuit lays (quantum_film/fixer.py) |
| the circuit lays the Pauli law | local statevector against the golden kernel to 1e-12; three sabotages fail it | **not yet run on Atlas or a device.** The tile Atlas ran on 2026-09-25 was a research prototype with another law (docs/VALIDATION.md). The circuit is not yet hardware-shaped (docs/ROADMAP.md). |
| mpmath is accurate enough | the premise gate above, at 512 bits | a different mpmath version is a claim to test, not assume (1.4.1 in WSL matched) |

## Versioning

- A negative record names its format, `quantum-film/negative/v1`, and carries
  the law it was laid under.
- The uniforms' domain string is `quantum-film/uniform/v1`.
- Changing either one changes every digest. That change is made deliberately:
  a new version string, and `make vectors`. It is never made in place.
- A record also names the package version that fixed it (`code.quantum_film`),
  and the digest covers it, so the same roll fixed by another version has
  another digest. `reproduce` compares the roll itself (stock, law, stream,
  crystals), not the digest.
- A device roll's commitment is `quantum-film/commitment/v2`. v1 joined its
  fields with a bare "|", so an engine and a job could be re-attributed
  together. No v1 device roll was ever fixed.

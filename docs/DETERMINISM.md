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
   Two paths lay it: the authority, and a binary64 path on libcft that lays
   the authority's roll by construction (below).
2. **A fixed record is permanent.** On disk it is exactly its canonical
   text. Its digest is re-derived from its content. A changed byte, a
   duplicated key, a changed law or a missing provenance field is refused by
   name.
3. **A black-and-white print is a function of its record** (since 2026-09-26;
   below, "From rolls to a print"). Development borrows atlas-film's sourced
   organs through its pinned mode. Nothing is claimed for what that mode
   refuses: colour, the MTF, halation, and a grained paper.

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

**The checks on the argument** (tests/golden/test_golden_premise.py,
test_golden_fermi.py and test_independence.py):
- **Its premise, measured against code the authority does not share.**
  Along real rolls, draw by draw, every 256-bit target and boundary is
  compared with two references:
  - **Exactly, where the kernel is rational.** cos(2 pi m / L) is rational
    for every m only when L is 1, 2, 3, 4 or 6 (Niven's theorem), and there
    every weight, boundary and target is an exact Fraction.
    - pauli-4x4 (L = 4): worst error 2^-252.4 over 20 rolls.
    - L = 6, r2 = 1, which is on no shelf: worst error 2^-251.0 over 10
      rolls. It is there because its arithmetic is not accidentally exact:
      N/M = 5/36 is not dyadic. On L = 4 and 16, several binary64 slips round
      to the exact value, and no output there shows them: int/int division,
      a binary64 sum of the initial weights, and one of each draw's total.
      On L = 6 each moves the boundaries by about 2^-52 (the P0 verifier's
      third pass).
  - **pauli (16x16), an independent chain rule at 512 bits**: Schur
    complements on the closed-form kernel, one Cholesky column per draw.
    Worst error 2^-249.2. It stays beside L = 6: a cosine table rounded to
    binary64 is exact on L = 6, whose cosines are dyadic, and shows here.

  The gate demands 2^16 of headroom below the 2^-224 margin, and at least
  2^25 was measured. The first premise gate compared the authority with
  itself at 512 bits. That cannot see an error that does not scale with the
  precision: a binary64 `math.fsum` in one norm put every boundary 2^-51.5
  off, and that gate reported 2^-249 (the P0 verifier, 2026-09-25).
- **No binary64 in the authority**, read from its source as a cheap first
  line. It checks for float literals, `float()`, `__float__`, `math` beyond
  what is exact on Fractions (an alias included), mpmath's `fp` context, and
  `importlib`. It reads spellings, so it cannot see int/int division. The
  L = 6 reference catches that in the outputs.
- **The refusal, planted on both sides.** A target 2^-240 past a boundary,
  and one 2^-240 short of it, must each be refused. Both are inside the
  margin, and too far from the boundary for rounding to move them. So the
  gate fails if the margin shrinks below the arithmetic's own error, if the
  refusal goes, or if it is checked only on one side or after the choice. A
  reordering of the last kind passed every other gate. A target 2^-200 past
  must be decided, and go past the boundary.
- **Its precision, held.** mpmath's working precision is process-global, so
  another thread could turn the authority into binary64 arithmetic behind
  the same margin.
  - Every draw checks its precision.
  - The basis checks its precision, and its content, before it is cached.
    Every row's squared norm must be N/M, and three entries of K = Phi Phi^T
    must match the closed form from cosines computed afresh, each to
    2^-(prec - 16). A brief drop can come and go between two checks. Before
    the norm check, the verifier cached a corrupted basis 26 times in 40.
    Norms alone missed a drop confined to the angles, since cos^2 + sin^2
    stays 1; that basis was cached with K 2^-56 off. The closed-form
    entries catch it.
  - Each refuses by name (`PrecisionChanged`). The authority is not to be
    called from threads.

The first check on the argument laid the same rolls at 256 and 320 bits. It
could not fail: random seeds come no closer than about 2^-15 to a boundary,
so it passed with the refusal removed, and with a margin below the
arithmetic's own error (the P0 verifier, 2026-09-25).

## A second path: binary64 on libcft, equal by construction

`quantum_film/pinned` lays the same roll in binary64 on libcft (P1, round 1).
It does not trust binary64 to be close. It shows, draw by draw, that the
authority would decide the same way:
- **It encloses the exact chain rule.** Every weight, boundary and target is
  bracketed by directed rounding around its exact value, not around the
  authority's. The projections are bounded through Q = A^T T and a
  certified bound F < 1 on Q^T Q - I, not enclosed as a recurrence; an
  interval recurrence widened 2.5-3x a draw on the 16x16 stock.
  quantum_film/pinned/certificate.py's docstring has the argument.
- **A draw is decided only when its target's enclosure clears every boundary
  by TAU = 2^-200.** That is 2^24 times the authority's margin, and the
  authority errs by about 2^-249. So on a certified draw the authority
  neither refuses nor decides otherwise.
- **A roll with any draw it cannot certify goes whole to the authority**,
  whose refusals propagate. The hand-off also audits the certificate: the
  authority's first draws must be the certified ones, or the path raises
  `EnclosureBroken`.
- **The tile edge must be a power of two**, so every angle 2m/L is dyadic and
  libcft's cospi and sinpi take it exactly. Both shelf stocks qualify, and
  another L is refused by name.

**The checks** (tests/pinned, the `pinned` stage):
- Each directed operation is held bit for bit to its exact floor or ceiling.
- Each certificate step is held to exact rationals on tight inputs, where
  only its own roundings separate its bound from the exact value. Flipping
  any directed call to the other direction fails its step.
- The decision the sampler draws from is held to the exact chain rule's, in
  Fractions, with targets planted either side of every boundary.
- The named control: with the hand-off removed, a target planted inside
  binary64's own error parts from the authority. As shipped, the same stream
  agrees.
- What the source rule cannot see is stated in certificate.py: it reads
  spellings.

**Equality with the authority is not enough.** 10 of 11 faults planted in
the certificate passed equality, exact containment and the control; each
fails its step check. And the first end-to-end check held the decision the
certificate traced, not the one it returned. A fault that traced honestly
and returned another answer passed it (verifier-P1, 2026-09-26).

Measured: 2,300 pauli-4x4 and 740 pauli rolls equal the authority's, and
none was handed off. From the enclosure widths, P1 believes a random 16x16
roll hands off about once in 10^6.

## From rolls to a print

`quantum_film/develop.py` lays rolls as a sheet of film. It develops the sheet
through atlas-film's pinned mode, from the vendor/atlas-film submodule at
d4007b2 (its pinned branch).
- **The sheet is integers.** A cell is one site. Each layer of the emulsion's
  depth is one roll of every tile, and a cell's K is its column's count. The
  per-layer offsets and every crystal's 16-bit threshold come from the golden
  uniform on the print's stream. So the sheet is laid by integer arithmetic
  and SHA-256 alone.
- **The density is the borrowed stock's own, by construction.** Every roll
  holds N crystals, so the mean K is layers * N / L^2 exactly. The pitch is
  derived so that the borrowed stock's lambda_K equals that mean, to one
  rounding in a correctly rounded square root. atlas-film's `sheet=` path
  does not check the mean of K; this one does.
- **The honesty floor and the exact regime are refused by name.** At TRI-X's
  density, pauli needs at least 91 layers and pauli-4x4 at least 29.
- **The negative and the print are atlas-film's pinned mode.** They are the
  same bits on every IEEE 754 binary64 machine, under the gates and stated
  limits of atlas-film's docs/PINNED.md.
- **A print record** (docs/prints/*.json) names what the print is a function
  of:
  - the rolls and the mapping;
  - the pitch and both exposures, as hex floats;
  - the scene's digest and atlas-film's commit;
  - the digests of the sheet, the negative and the print.

  `python tools/first_prints.py --check` re-develops each print and compares
  its bits.

**The checks** (tests/develop, the `develop` stage):
- a small print, frozen: its sheet, negative and print digests;
- the density identity;
- the floor and regime refusals;
- one moved crystal moves the negative;
- a broken pad is refused by atlas-film's contract;
- atlas-film is imported only from the submodule, with its files' digest
  frozen.

## What is NOT promised

- **A device roll is not reproducible.** That covers Atlas's emulator and any
  QPU. It is recorded, with `fixed_at` and its provenance, and read; it is never
  re-run. The census of 2026-09-25 found that identical Atlas requests
  returned different bytes wherever sampling was involved, and that seeds pin
  circuits, not shots.
- **The numpy float path is not a column of this contract.** It rounds without
  pinning.
  - On 2026-09-25, on a 32x32 research tile with 128 crystals, binary32
    parted 2 of 40 fermion films from the binary64 reference. binary64
    parted none of 80 comparisons.
  - On the shelf's own stocks no random roll parted at any format: binary32
    on 5,800 rolls, binary64 and binary128 on 2,300 (P1).
  - A target planted inside a format's own error parts that format's roll.

  "None of 5,800" is not "never".
- **A circuit is scored, not trusted.** Its statistics are held to the
  authority's kernel: exactly on a local statevector, and with standard errors
  on an emulator or device.

## Evidence, and its gaps

| claim | evidence | gap |
|---|---|---|
| an emulated roll is f(stock, seed) | `fixer.reproduce`; tests/vectors regenerate byte for byte on every run; the margin's premise measured against exact Fractions and an independent 512-bit chain rule | **one CPU so far.** Windows 11 (Python 3.12.9, mpmath 1.3.0), and WSL2 Ubuntu 22.04 on the same desktop (Python 3.10.12, mpmath 1.4.1), where the P0 verifier regenerated the vectors byte for byte. Running `make verify-quick` on another machine is the next evidence, and costs one command. |
| records are permanent | `fixer.check` on every rule; a file is exactly its canonical text; the runner's control, a moved crystal the fixer's command line must refuse by its digest, and its twin, which the command line must accept | **a device roll's commitment binds by its anchor, not by its value.** The salt is in the record, so a changed field can be re-sealed with a recomputed commitment; what binds is the line committed to git before the job's first status call. That timing rests on the code and the local clock, with nothing third-party (verifier-P3). The commitment does not bind `kind`, `fixed_at` or `occurrences`, nor which law the circuit lays (quantum_film/fixer.py) |
| the circuit lays the Pauli law | local statevector against the golden kernel to 1e-12, for `givens.py` and `givens_line.py`; every rotation dropped fails it. On Atlas (job 8586f1cc), `givens_line`'s layouts matched the exact law: 1.48 and 2.52 standard errors, no forbidden layout | **not yet on a device.** Atlas's emulator is noiseless. A device's fraction of forbidden layouts will be its first witness of noise. |
| mpmath is accurate enough | the premise gate above: exact on pauli-4x4, independent at 512 bits on the 16x16 stock | a different mpmath version is a claim to test, not assume (1.4.1 in WSL matched) |
| the pinned path lays the authority's roll | tests/pinned: every directed operation exact; every certificate step exact on tight inputs, each directed call flipped failing; the decision returned held to the exact chain rule with planted targets; the named control. 2,300 pauli-4x4 and 740 pauli rolls equal | **its source rule reads spellings**, a limit stated in certificate.py. In the orchestration a respelling passes if it moves none of the end-to-end check's claims on that check's inputs. **One libcft build**, identified by its path and hash; no hash with the PE timestamps zeroed pins it yet |
| a black-and-white print is a function of its record | tests/develop's frozen print; `tools/first_prints.py --check` re-develops the five first prints and compares their digests | **one machine so far.** The paper is ungrained. A scene's exposure is metered once on atlas-film's default path and kept as a hex float, never re-metered |

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

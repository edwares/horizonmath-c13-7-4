# Research status

Status date: 2026-07-30 UTC

## Claims currently supported

### Published class-52 result

All 30 corrected class-52 pseudo-Boolean instances have VeriPB-accepted UNSAT
certificates. Every verification used `--requireUnsat`; formula and proof
hashes were checked; and a fresh-environment clean-room run passed 30/30.

Scoped conclusion: link class 52 is eliminated under the audited corrected
class-52 reduction.

### Generalized class-52 regression

The class-agnostic implementation independently reproduces:

- automorphism-group order 36;
- all 26 orbits of the 495 four-subsets;
- all 107 symmetry-reduced exact degree profiles;
- the historical `70 / 17 / 20` screening partition;
- all 20 corrected retained profiles;
- the eleven pair-multiplicity branches for case 21/profile 014;
- all 30 native OPBs, byte for byte.

The fresh candidate-orbit proof phase records:

- `VERIFIED_UNSAT`: orbit indices 0 through 18;
- `TIMEOUT`: orbit indices 19 through 25.

The current reconstructed end-to-end chain is not independently formal at
every upstream discard. Seventeen whole exact-minimum-set exclusions and 87
early-profile exclusions remain `SOLVER_UNSAT` only.

### Classification and numbering

The catalog audit enumerates all 21,952 Figure 1 completions, finds exactly 67
isomorphism classes, and verifies that Figure 6 is a distinct 68th class. The
recovered templates were matched exactly to the figures in:

Daniel M. Gordon, Oren Patashnik, John Petro, and Herbert Taylor,
*Minimum (12, 6, 3) Covers*, Ars Combinatorica 40 (1995), 161–177.

Theorem 5.9 supplies the human mathematical exhaustiveness theorem. That
published proof has not been translated into a machine-checked formal proof.
The indices 1–68 are project-local; the paper does not individually number the
67 Figure 1 classes.

## Status ledger

| Item | Status |
|---|---|
| 68-entry link catalog | `AUDITED_AGAINST_PUBLISHED_THEOREM` |
| Project numbering map | `AUDITED` |
| Class-52 enumeration/regression | `ENUMERATED` |
| Class-52 corrected formulas | `FORMULAS_GENERATED` 30/30 |
| Published class-52 terminal instances | `VERIFIED_UNSAT` 30/30 |
| Fresh class-52 candidate screens | 19 `VERIFIED_UNSAT`, 7 `TIMEOUT` |
| Fresh whole-case exclusions | 17 `SOLVER_UNSAT` |
| Fresh early-profile exclusions | 87 `SOLVER_UNSAT` |
| Other 67 classes at profile depth | `NOT_STARTED` |
| Global \(C(13,7,4)=30\) claim | Not authorized |

## Next gate

Before launching proof-scale work on another class:

1. load the audited 68-entry numbering manifest as a first-class pipeline
   input;
2. run validation, multiplicities, automorphism groups, residual-four-set
   counts, and candidate-minimum-set orbit enumeration across all 68 classes;
3. preserve one complete manifest per class;
4. rank the unresolved classes using only inexpensive structural and screening
   features;
5. select an easy, median, and difficult pilot.

No all-67 solver campaign should start before that gate passes.

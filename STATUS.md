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

### Solver-free all-68 structural census

The deterministic v0.5.0 front end has now processed every audited
representative without generating formulas or launching LP, solver, proof, or
verifier work. For each class it preserves:

- a canonical labeled-link input and hashes;
- validation as a 15-block \(C(12,6,3)\) cover;
- point, pair, triple, four-set, and residual-four-set multiplicities;
- the complete automorphism group and deterministic generators;
- every candidate minimum-point four-set orbit representative;
- the exact Burnside count of all unscreened degree-profile orbits;
- a status ledger in which every unperformed downstream stage remains
  `NOT_STARTED`.

The structural ranking contains 23 tie groups. Its provisional pilot is class
68 (easy/high symmetry), class 4 (median tie group), and class 59
(difficult/low symmetry). This is a structural preselection only.

For class 52, the census obtains group order 36, 26 candidate four-set orbits,
and 2,578 **unscreened** degree-profile orbits. The 2,578 count and the
historical 107 profiles are not competing results: 107 is the count after the
historical candidate/case screening that this census deliberately does not
run.

## Status ledger

| Item | Status |
|---|---|
| 68-entry link catalog | `AUDITED_AGAINST_PUBLISHED_THEOREM` |
| Project numbering map | `AUDITED` |
| All-68 canonical link extraction | `ENUMERATED` 68/68 |
| All-68 structural census | `ENUMERATED` 68/68 |
| Solver-free structural ranking | `ENUMERATED`; 23 tie groups |
| Provisional three-class pilot | Classes 68 / 4 / 59; structural preselection only |
| Class-52 enumeration/regression | `ENUMERATED` |
| Class-52 corrected formulas | `FORMULAS_GENERATED` 30/30 |
| Published class-52 terminal instances | `VERIFIED_UNSAT` 30/30 |
| Fresh class-52 candidate screens | 19 `VERIFIED_UNSAT`, 7 `TIMEOUT` |
| Fresh whole-case exclusions | 17 `SOLVER_UNSAT` |
| Fresh early-profile exclusions | 87 `SOLVER_UNSAT` |
| Other 67 classes at screening/profile depth | `NOT_STARTED` |
| Other 67 classes at formula/solver/proof depth | `NOT_STARTED` |
| Global \(C(13,7,4)=30\) claim | Not authorized |

## Next gate

Before launching proof-scale work on another class:

1. materialize exact profile representatives for the provisional classes 68,
   4, and 59;
2. run and audit every inexpensive mathematical screen, with no silent
   disappearances;
3. refine the provisional ranking with retained-profile and formula-size
   metrics;
4. inspect root LP feasibility only after formula generation is audited;
5. authorize bounded pilot solver runs separately.

No all-67 solver campaign is authorized.

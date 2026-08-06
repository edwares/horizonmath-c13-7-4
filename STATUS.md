# Research status

Status date: 2026-08-06 UTC

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

### Solver-free three-class pilot screening

The v0.6.0 pipeline has materialized every symmetry-reduced degree-profile
representative for the provisional pilot classes 68, 4, and 59. It retained
all candidate four-set orbits because no solver-free candidate contradiction
was asserted. It then:

- recorded every exact minimum-set orbit;
- discarded the unique 12-point exact-minimum-set orbit in each class because
  eight positive excess units cannot be placed outside a 12-point minimum set;
- materialized every remaining profile orbit;
- checked the screening decision on every member of every profile orbit;
- discarded a profile only when some extension degree exceeded the 14
  available extension blocks;
- audited every corrected pair-multiplicity interval and found no empty
  interval among the remaining profiles.

| Class | Candidate orbits | Exact-set orbits | Unscreened profiles | Direct arithmetic discards | Retained profiles |
|---:|---:|---:|---:|---:|---:|
| 68 | 12 | 88 | 755 | 4 | 751 |
| 4 | 279 | 2,123 | 39,618 | 54 | 39,564 |
| 59 | 495 | 3,797 | 75,582 | 78 | 75,504 |
| **Total** | **786** | **6,008** | **115,955** | **136** | **115,819** |

The direct screen removes about 0.12% of the profile orbits. A retained profile
has not been shown feasible; it merely survived the implemented arithmetic
checks. This result strengthens the case for beginning with class 68, but it is
not a measured solver- or proof-difficulty result.

### Class-68 candidate formula checkpoint

The v0.7.0 pipeline has generated one native necessary-condition OPB for every
class-68 candidate minimum-point orbit:

- 12 candidate orbits;
- 12 formulas;
- 792 binary variables per formula;
- 563 bounded mathematical rows and 568 serialized constraints per formula;
- 6,816 serialized rows independently reconstructed and compared in order;
- 12/12 native hashes and 12/12 canonical hashes distinct;
- no direct-containment, LP, MILP, proof, or verifier run.

The generator audits the complete structural-census and pilot-screening
checkpoints before emitting a formula. Its independent audit does not import
the production candidate-formula builder or PB module. All 12 comparisons
pass, but no orbit is pruned: formula generation is not an infeasibility
result.

### Class-68 direct-containment checkpoint

The v0.8.0 pipeline has exhaustively compared every serialized lower row with
every serialized upper row in all 12 audited class-68 candidate formulas:

- 563 lower rows and 5 upper rows per formula;
- 2,815 support comparisons per formula;
- 33,780 comparisons overall;
- 14,284 actual lower-support/upper-support containments;
- maximum bound gap exactly zero in every formula;
- zero strict direct-containment contradictions;
- zero proofs generated;
- all 12 formulas preserved for the next stage.

An independent implementation reparsed all formulas and recomputed every
comparison, containment, and bound gap. All 12 comparisons pass. No LP, MILP,
solver, proof verifier, class-4 run, or class-59 run occurred.

The proof renderer is regression-tested against the published class-52 method:
it finds the exact `eq9` through `eq14` threshold, selects rows 283 and 642,
and reproduces the 57-byte four-line cutting-planes proof. Class 68 produces
no such witness.

Surviving this scan does not establish feasibility. No class-68 orbit is
formally pruned, and class 68 is not eliminated.

### Class-68 exact root-LP checkpoint and formal verification

The v0.9.0 pipeline has run the bounded root-LP stage on exactly the 12
class-68 candidate formulas that survived direct containment. It did not
launch MILP, RoundingSat, class 4, or class 59.

The exact evidence partitions the 12 orbits as follows:

- exact rational root-LP witnesses: 0, 2, 4, 5, 9, 10;
- exact integer Farkas contradictions: 1, 3, 6, 7, 8, 11.

For each LP-feasible case, floating HiGHS output was used only to select a
candidate active system. The pipeline then solved that system with exact
rational arithmetic and checked all 568 serialized constraints and all
variable bounds exactly. These witnesses establish feasibility only of the
continuous relaxation; they are not Boolean assignments and do not establish
`SAT`.

For each root-LP-infeasible case, the pipeline converted the exact serialized
rows to a primitive positive integer Farkas combination. An independent
implementation reparsed the native OPB, reconstructed the normalized proof
formula, and recomputed the complete weighted sum with arbitrary-precision
integers. The independent exact-evidence audit passed 12/12 cases: six exact
LP witnesses and six exact Farkas contradictions.

All six Farkas proofs were then checked with the pinned VeriPB 0.3a0 build.
Every invocation used `--requireUnsat`; every expected formula and proof hash
matched; all six verifier runs exited successfully and reported
`Verification succeeded.`; and all logs were preserved. A separate audit of
the verification artifacts, commands, hashes, exit codes, logs, wheel, and
build provenance passed 6/6.

Therefore only class-68 orbits 1, 3, 6, 7, 8, and 11 are now
`VERIFIED_UNSAT` and formally pruned. Orbits 0, 2, 4, 5, 9, and 10 remain
unresolved. Class 68 is not eliminated.

## Status ledger

| Item | Status |
|---|---|
| 68-entry link catalog | `AUDITED_AGAINST_PUBLISHED_THEOREM` |
| Project numbering map | `AUDITED` |
| All-68 canonical link extraction | `ENUMERATED` 68/68 |
| All-68 structural census | `ENUMERATED` 68/68 |
| Solver-free structural ranking | `ENUMERATED`; 23 tie groups |
| Provisional three-class pilot | Classes 68 / 4 / 59; structural preselection only |
| Pilot exact minimum sets | `ENUMERATED` 6,008 orbits |
| Pilot degree profiles | `ENUMERATED` 115,955 orbits |
| Pilot direct arithmetic screening | `ENUMERATED`; 136 discarded, 115,819 retained |
| Class-68 candidate formulas | `FORMULAS_GENERATED` 12/12; independent audit 12/12 |
| Class-68 direct containment | `ENUMERATED`; 12/12 scanned, zero contradictions, 12 survivors |
| Class-68 root LP | `ENUMERATED` 12/12; 6 exact rational LP witnesses, 6 `SOLVER_UNSAT` cases with exact Farkas contradictions |
| Class-68 root-LP proofs | `PROOF_GENERATED` 6/6 contradiction cases |
| Class-68 root-LP verification | `VERIFIED_UNSAT` 6/6 proofs; orbits 1 / 3 / 6 / 7 / 8 / 11 formally pruned |
| Class-68 root-LP survivors | Orbits 0 / 2 / 4 / 5 / 9 / 10; exact continuous-LP witnesses only, not `SAT` |
| Class-4 and class-59 formulas / root LP / solver / proof | `NOT_STARTED` |
| Class-52 enumeration/regression | `ENUMERATED` |
| Class-52 corrected formulas | `FORMULAS_GENERATED` 30/30 |
| Published class-52 terminal instances | `VERIFIED_UNSAT` 30/30 |
| Fresh class-52 candidate screens | 19 `VERIFIED_UNSAT`, 7 `TIMEOUT` |
| Fresh whole-case exclusions | 17 `SOLVER_UNSAT` |
| Fresh early-profile exclusions | 87 `SOLVER_UNSAT` |
| Non-52 classes at screening/profile depth | Classes 4, 59, and 68 `ENUMERATED`; remaining 64 `NOT_STARTED` |
| Non-52 classes at formula depth | Class 68 `FORMULAS_GENERATED`; remaining 66 `NOT_STARTED` |
| Non-52 classes at solver/proof depth | Class 68 has 6 `VERIFIED_UNSAT` root-LP orbits and 6 root-LP survivors; remaining 66 classes `NOT_STARTED` at this depth |
| Global \(C(13,7,4)=30\) claim | Not authorized |

## Next gate

Before launching proof-scale work on another class, the next bounded gate is
an exact LP split-tree/Farkas attempt on only the six class-68 root-LP
survivors: 0, 2, 4, 5, 9, and 10. Any contradiction must again be promoted
only after an independent exact audit and VeriPB `--requireUnsat`
verification. A surviving branch or formula must not be called `SAT` without
a Boolean witness and the required independent design check.

The legacy command that couples root-LP screening to MILP must not be used for
this gate. MILP, RoundingSat, class-4, class-59, and all-67 campaigns remain
unauthorized.

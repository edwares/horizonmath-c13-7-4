# Research status

Status date: 2026-08-08 UTC

## Claims currently supported

### Published class-52 result

All 30 corrected class-52 pseudo-Boolean instances have VeriPB-accepted UNSAT
certificates. Every verification used `--requireUnsat`; formula and proof
hashes were checked; and a fresh-environment clean-room run passed 30/30.

Scoped conclusion: **link class 52 is eliminated under the audited corrected
class-52 reduction.**

The authoritative publication remains:

- <https://github.com/edwares/class52-formal-certification>
- <https://doi.org/10.5281/zenodo.21660461>

The generalized `horizonlink` regression independently reproduces the
class-52 structural and formula corpus. Its reconstructed upstream screening
chain contains historical `SOLVER_UNSAT` records and is not substituted for
the separately audited published certification.

### Formal class-68 elimination

Class 68 is now formally eliminated under the audited link-class reduction.
Its structural candidate minimum-point four-set partition has exactly 12
orbits, and the class-level closure audit accounts for all 12 with exact proofs
accepted by VeriPB with `--requireUnsat`.

The formal routes are:

| Candidate orbit(s) | Coverage |
|---|---|
| `1, 3, 6, 7, 8, 11` | Direct exact root-LP Farkas contradictions; 6/6 VeriPB `VERIFIED_UNSAT` |
| `2` | Exhaustive 155-profile decomposition; 155/155 VeriPB `VERIFIED_UNSAT` |
| `0, 4, 5, 9, 10` | Exhaustive retained exact-minimum/profile decomposition; 46 profile occurrences covered |

For orbit 2, 131 profiles are covered by the baseline formal corpus and 24
harder residual profiles by exact pair-CG/Farkas or split-tree/Farkas proofs.
The orbit-2 closure audit covers exactly profile indices `0..154` with no
gaps or overlap.

For candidate orbits 0, 4, 5, 9, and 10, 43 of 46 profile occurrences have
direct root-Farkas or forced integral pair-cut/Farkas proofs. The three
remaining occurrences are the same exact profile formula, canonical SHA-256:

`1c5d7b88906c89280e3bdbce4c74fbafacf1d350bf2e5cf5c7d7c7d2fbc057b0`

That shared formula is refuted by 13 exact one-sided pair Chvatal-Gomory cuts
followed by a 203-node / 102-leaf exact Farkas split tree of maximum depth 39.
The stitched proof is VeriPB `VERIFIED_UNSAT`.

The final class-level closure manifest is checked in at
`results/class68-formal-certification-v0.1.0/class68-formal-closure.json`.
Its SHA-256 is:

`ed2b3532c4e0f337fc3afcad05711135d175c639bd007414c8c638073c3a76d7`

A deterministic rerun of the closure audit reproduced the same hash.

The complete formal checkpoint archive is
`C13_class68_formal_checkpoint_2026-08-08.zip`, SHA-256:

`62b5c13608a8501e508270bb563bf24c57dda7f0aa8694e7ffc8217eec3dc3fb`

The verifier wheel used by every formal source in the closure has SHA-256:

`3844f3b416c870f6ef96fc737125e4ec97b6cfd1c4d1726a2bc158626c77b369`

See
[`docs/CLASS68_FORMAL_CERTIFICATION_V0.1.0.md`](docs/CLASS68_FORMAL_CERTIFICATION_V0.1.0.md)
for the proof-method and artifact summary.

### Classification and numbering

The catalog audit enumerates all 21,952 Figure 1 completions, finds exactly 67
isomorphism classes, and verifies that Figure 6 is a distinct 68th class. The
recovered templates were matched exactly to the figures in:

Daniel M. Gordon, Oren Patashnik, John Petro, and Herbert Taylor,
*Minimum (12, 6, 3) Covers*, Ars Combinatorica 40 (1995), 161-177.

Theorem 5.9 supplies the human mathematical exhaustiveness theorem. That
published proof has not been translated into a machine-checked formal proof.
The indices 1-68 are project-local; the paper does not individually number the
67 Figure 1 classes.

### Solver-free all-68 structural census

The deterministic front end has processed every audited representative and
preserves, for each link:

- canonical input and hashes;
- validation as a 15-block `C(12,6,3)` cover;
- point, pair, triple, four-set, and residual-four-set multiplicities;
- the complete automorphism group and deterministic generators;
- every candidate minimum-point four-set orbit representative; and
- exact unscreened degree-profile orbit counts.

The structural ranking contains 23 tie groups. The provisional three-class
pilot was class 68 / class 4 / class 59. Class 68 has now progressed from that
pilot through complete formal elimination.

### Solver-free pilot screening outside class 68

Classes 4 and 59 have the previously recorded solver-free exact-minimum-set and
degree-profile screening data. They have **not** been formally eliminated.
The other 64 currently unresolved classes have the all-68 structural census
but no class-level formal elimination.

## Status ledger

| Item | Status |
|---|---|
| 68-entry link catalog | `AUDITED_AGAINST_PUBLISHED_THEOREM` |
| Project numbering map | `AUDITED` |
| All-68 canonical link extraction | `ENUMERATED` 68/68 |
| All-68 structural census | `ENUMERATED` 68/68 |
| Solver-free structural ranking | `ENUMERATED`; 23 tie groups |
| Published class-52 terminal instances | `VERIFIED_UNSAT` 30/30 |
| Link class 52 | **FORMALLY ELIMINATED** |
| Class-68 candidate formulas | `FORMULAS_GENERATED` 12/12; independent audit 12/12 |
| Class-68 direct containment | Historical gate complete; 12/12 survived |
| Class-68 candidate-orbit formal coverage | `VERIFIED_UNSAT` 12/12 |
| Class-68 orbit-2 profile coverage | `VERIFIED_UNSAT` 155/155 |
| Link class 68 | **`VERIFIED_UNSAT_CLASS_68` / FORMALLY ELIMINATED** |
| Formally eliminated link classes | **2/68: 52 and 68** |
| Remaining link classes | **66** |
| Global \(C(13,7,4)=30\) claim | **Not authorized** |

## Claim boundary

The project now has two fully eliminated link classes: 52 and 68. This is a
strictly stronger project state than the earlier direct-containment checkpoint,
but it is not the global covering-number theorem. A proof of
\(C(13,7,4)=30\) still requires formal elimination of the remaining 66 link
classes or a stronger exhaustive argument that closes them collectively.

## Next gate

Use the audited all-68 census and the exact proof machinery demonstrated on
class 68 to choose and attack the next unresolved link class. Classes 4 and 59
already have pilot-profile material and are natural comparison points, but no
future elimination is to be claimed without the same exact-certificate and
verification gate.

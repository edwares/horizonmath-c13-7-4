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

### Formal class-48 elimination

Class 48 is formally eliminated. Its 35 candidate minimum-point four-set
orbits split into 10 exact root-pruned orbits and 25 retained orbits. The
retained side expands to 78 exact minimum-set orbits and 675 exact degree
profiles, all covered by pinned-VeriPB UNSAT proofs: 509 direct root-Farkas,
157 forced-pair-cut/Farkas, and 9 exact split-tree/Farkas proofs.

The checked-in class-level closure is
`results/class48-formal-certification-v0.1.0/class48-formal-closure.json`,
SHA-256
`8b108f154e1e7e786f7f75e2f9db154803999e01a439cb5e746548c95dea61d2`.
See
[`docs/CLASS48_FORMAL_CERTIFICATION_V0.1.0.md`](docs/CLASS48_FORMAL_CERTIFICATION_V0.1.0.md)
for the proof and checkpoint details.

### Formal class-50 elimination

Class 50 is formally eliminated. Its 35 candidate minimum-point four-set
orbits split into 3 exact root-pruned orbits and 32 retained orbits. The
retained side expands to 138 exact minimum-set orbits and 1508 exact degree
profiles, all covered by pinned-VeriPB UNSAT proofs: 1343 direct root-Farkas,
156 forced-pair-cut/Farkas, and 9 exact split-tree/Farkas proofs.

The checked-in class-level closure is
`results/class50-formal-certification-v0.1.0/class50-formal-closure.json`,
SHA-256
`cdcc401a0dac72e064cd6d216676e3763c2c44eda8084da43ff4ed1c81249699`.
See
[`docs/CLASS50_FORMAL_CERTIFICATION_V0.1.0.md`](docs/CLASS50_FORMAL_CERTIFICATION_V0.1.0.md)
for the proof and checkpoint details.

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
The other 62 currently unresolved classes have the all-68 structural census
but no class-level formal elimination.

### Class-68 exact root-LP checkpoint and formal verification

The v0.9.0 pipeline has run the bounded root-LP stage on exactly the 12
class-68 candidate formulas that survived direct containment. It did not
launch MILP, RoundingSat, class 4, or class 59.

The original v0.1 mathematical checkpoint remains immutable because its six
Farkas proofs are the exact inputs bound into the preserved VeriPB verification
records. A compact v0.2 regeneration fingerprint fixes and guards against a
byte-reproducibility defect in diagnostic metadata: raw HiGHS floating
objective margins are not serialized; instead, the primitive exact Farkas ray
is normalized to total multiplier one and its rational margin is recorded.
CI regenerates the full v0.2 output from source and requires its complete
SHA-256 inventory to match. The regression suite separately requires the exact
LP witnesses, exact Farkas certificates, verifier-normalized OPBs, and PBP
proof bytes to match v0.1.

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

At this intermediate checkpoint, only class-68 orbits 1, 3, 6, 7, 8, and 11
were `VERIFIED_UNSAT` and formally pruned; orbits 0, 2, 4, 5, 9, and 10 were
still unresolved. Those six survivors were subsequently closed by the formal
proof routes described above, so this section is retained as provenance for
the root-LP stage rather than as the current class-68 status.

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
| Class-68 direct containment | Historical gate complete; 12/12 survived |
| Class-68 root LP | `ENUMERATED` 12/12; 6 exact rational LP witnesses, 6 exact Farkas contradictions |
| Class-68 root-LP verification | `VERIFIED_UNSAT` 6/6 proofs; orbits 1 / 3 / 6 / 7 / 8 / 11 formally pruned at that gate |
| Class-68 root-LP survivors | Orbits 0 / 2 / 4 / 5 / 9 / 10 at the intermediate checkpoint; all subsequently closed |
| Class-68 candidate-orbit formal coverage | `VERIFIED_UNSAT` 12/12 |
| Class-68 orbit-2 profile coverage | `VERIFIED_UNSAT` 155/155 |
| Link class 68 | **`VERIFIED_UNSAT_CLASS_68` / FORMALLY ELIMINATED** |
| Link class 48 | **`VERIFIED_UNSAT_CLASS_48` / FORMALLY ELIMINATED** |
| Link class 50 | **`VERIFIED_UNSAT_CLASS_50` / FORMALLY ELIMINATED** |
| Class-4 and class-59 formulas / root LP / solver / proof | `NOT_STARTED` |
| Class-52 enumeration/regression | `ENUMERATED` |
| Class-52 corrected formulas | `FORMULAS_GENERATED` 30/30 |
| Published class-52 terminal instances | `VERIFIED_UNSAT` 30/30 |
| Link class 52 | **FORMALLY ELIMINATED** |
| Fresh class-52 candidate screens | 19 `VERIFIED_UNSAT`, 7 `TIMEOUT` |
| Fresh whole-case exclusions | 17 `SOLVER_UNSAT` |
| Fresh early-profile exclusions | 87 `SOLVER_UNSAT` |
| Formally eliminated link classes | **4/68: 48, 50, 52, and 68** |
| Remaining link classes | **64** |
| Global \(C(13,7,4)=30\) claim | **Not authorized** |

## Claim boundary

The project now has four fully eliminated link classes: 48, 50, 52, and 68. This is a
strictly stronger project state than the earlier direct-containment checkpoint,
but it is not the global covering-number theorem. A proof of
\(C(13,7,4)=30\) still requires formal elimination of the remaining 64 link
classes or a stronger exhaustive argument that closes them collectively.

## Next gate

Use the audited all-68 census and the exact proof machinery demonstrated on
class 68 to choose and attack the next unresolved link class. Classes 4 and 59
already have pilot-profile material and are natural comparison points, but no
future elimination is to be claimed without the same exact-certificate and
verification gate.

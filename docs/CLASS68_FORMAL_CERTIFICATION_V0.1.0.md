# Class-68 formal certification v0.1.0

Status date: 2026-08-08 UTC

## Result

Link class 68 is formally eliminated under the audited link-class reduction.
The class has 12 candidate minimum-point four-set orbits, and the final closure
audit accounts for every orbit with VeriPB-accepted UNSAT proofs checked with
`--requireUnsat`.

This is the second fully eliminated link class in the project, after the
separately published class-52 certification. It does **not** by itself prove
`C(13,7,4)=30`; 66 link classes remain.

## Exhaustive formal coverage

| Candidate orbit(s) | Formal route |
|---|---|
| `1, 3, 6, 7, 8, 11` | Direct exact root-LP Farkas contradictions; all six VeriPB-verified |
| `2` | Exhaustive 155-profile decomposition; 131 baseline and 24 residual profiles, all `VERIFIED_UNSAT` |
| `0, 4, 5, 9, 10` | Exhaustive retained exact-minimum/profile decomposition: 46 profile occurrences total |

For the final five orbits, 43 of the 46 profile occurrences are covered by
direct root Farkas or forced integral pair-cut/Farkas proofs. The three
remaining occurrences are the same canonical profile formula:

`1c5d7b88906c89280e3bdbce4c74fbafacf1d350bf2e5cf5c7d7c7d2fbc057b0`

That shared formula is refuted by 13 exact one-sided pair Chvatal-Gomory cuts
followed by a 203-node, 102-leaf exact Farkas split tree of maximum depth 39.
The stitched proof passes VeriPB with `--requireUnsat`.

The class-level audit verifies that the candidate-orbit partition is exactly
`0..11`, that every retained profile decomposition is covered exactly, and
that there are no missing or unexpected candidate orbits.

## Audited records

The checked-in closure record is
[`results/class68-formal-certification-v0.1.0/class68-formal-closure.json`](../results/class68-formal-certification-v0.1.0/class68-formal-closure.json).
Its SHA-256 is:

`ed2b3532c4e0f337fc3afcad05711135d175c639bd007414c8c638073c3a76d7`

A deterministic rerun of the closure audit reproduced the same hash.

The full formal checkpoint archive is
`C13_class68_formal_checkpoint_2026-08-08.zip`, SHA-256:

`62b5c13608a8501e508270bb563bf24c57dda7f0aa8694e7ffc8217eec3dc3fb`

The archive contains the exact OPB/PBP proofs, verification manifests and
logs, structural provenance, proof-generation sources, closure-audit source,
and the verifier wheel. The ZIP passed an integrity test before this checkpoint
was recorded.
As with the earlier pipeline checkpoints, this bulky corpus is an immutable
artifact rather than ordinary Git source.

The VeriPB wheel used by every formal source in the class-level closure has
SHA-256:

`3844f3b416c870f6ef96fc737125e4ec97b6cfd1c4d1726a2bc158626c77b369`

## Proof machinery used

The formal campaign combines:

- corrected exact-degree pseudo-Boolean formulas;
- exact Farkas contradictions for root-LP-infeasible formulas;
- integral one-sided pair-count inequalities obtained by exact Farkas
  combinations and Chvatal-Gomory division;
- deterministic Boolean split trees for residual formulas;
- exact Farkas certificates for every infeasible leaf;
- bottom-up resolution of each split tree to the empty root clause; and
- clean-room VeriPB checking with `--requireUnsat`.

Floating-point LP was used only to discover supports, cuts, and branch choices.
No elimination is promoted from floating-point status alone; the formal claim
gate is the exact certificate plus independent VeriPB acceptance.

The exact proof-generation snapshot used for this campaign remains inside the
formal checkpoint. It is intentionally not copied over the evolving
class-agnostic `src/horizonlink/` tree, whose later pipeline modules have a
different source-control lifecycle.

## Claim boundary

Supported claim: **link class 68 is eliminated**.

Not supported by this checkpoint alone: **`C(13,7,4)=30`**.

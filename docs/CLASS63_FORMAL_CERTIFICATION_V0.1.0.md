# Class-63 formal certification v0.1.0

Status date: 2026-08-08 UTC

## Result

Link class 63 is formally eliminated under the audited link-class reduction.
The structural candidate minimum-point four-set partition has 58 orbits. Forty-two
orbits are eliminated directly at the root, and an independently recomputed
exact-minimum-set / degree-profile decomposition of the other 16 orbits is
covered by 460 pinned-VeriPB UNSAT proofs with no gaps or duplicates.

This does **not** by itself prove `C(13,7,4)=30`.

## Exhaustive formal coverage

The 42 root-pruned candidate orbits are
`0..16, 19..24, 34..39, 42..54`. Their exact Farkas proofs all pass VeriPB
with `--requireUnsat`.

The 16 retained candidate orbits are
`17, 18, 25, 26, 27, 28, 29, 30, 31, 32, 33, 40, 41, 55, 56, 57`.
Re-expanding them gives 53 exact minimum-set orbits and 460 exact degree-profile
orbits. Their formal proof partition is:

| Method | Verified profiles |
|---|---:|
| Direct exact root-LP Farkas | 232 |
| Exact integral pair cuts, then Farkas | 215 |
| Exact split tree with Farkas leaves | 13 |
| **Total** | **460** |

The 13 split-tree residuals are:

| Profile index | Pair cuts | Nodes | Leaves |
|---:|---:|---:|---:|
| 293 | 0 | 287 | 144 |
| 317 | 1 | 293 | 147 |
| 334 | 2 | 263 | 132 |
| 353 | 0 | 305 | 153 |
| 384 | 1 | 319 | 160 |
| 407 | 2 | 325 | 163 |
| 427 | 2 | 53 | 27 |
| 428 | 0 | 181 | 91 |
| 430 | 0 | 175 | 88 |
| 449 | 5 | 55 | 28 |
| 450 | 0 | 181 | 91 |
| 452 | 1 | 185 | 93 |
| 459 | 0 | 155 | 78 |

The initial 16-cut census had three `CUT_LIMIT` rows: 155, 176, and 192.
A selective, provenance-checked refinement recomputed only those rows at a
32-cut cap and closed them after 20, 18, and 18 cuts respectively. The refined
228-profile census contains 215 cut-closed rows and 13 genuine split-tree
residuals, with SHA-256:

`b7b03d2052d67ff9449091f01b720fbd111a1135a078bd473c2ce92fd8bee4e6`

The class-level audit independently recomputes the retained exact minimum sets
and degree profiles, rebuilds every verifier OPB, checks proof/tree/log hashes,
requires one common verifier fingerprint, and requires exact candidate-orbit
and profile coverage. The checked-in closure record is
[`results/class63-formal-certification-v0.1.0/class63-formal-closure.json`](../results/class63-formal-certification-v0.1.0/class63-formal-closure.json),
SHA-256:

`09be1a62500c132bd5462c8d0ab9d312bbd79e62492ced275e81e2823b346f32`

## Durable proof checkpoint

The consolidated proof checkpoint is
`C13_class63_formal_checkpoint_2026-08-08.zip`, SHA-256:

`91ea983c43f801802dc225a3491bf7a41397e7eb2686175c55776234f9f207e2`

It contains the Class 63 structural/root evidence, refined pair-cut census,
447 canonical direct/cut proof instances, 13 split-tree proof instances,
verification logs, proof-source snapshot, and the pinned verifier wheel. The
archive passed an integrity test before this reference was recorded.

Every formal verification source uses the same VeriPB wheel, SHA-256:

`3844f3b416c870f6ef96fc737125e4ec97b6cfd1c4d1726a2bc158626c77b369`

## Proof discipline

Floating-point LP is used only to discover supports, integral cuts, and branch
choices. No floating-point solver disposition is promoted to an elimination.
Root contradictions, derived pair bounds, and split-tree leaves are converted
to exact integer certificates and the stitched pseudo-Boolean proofs are then
checked independently by VeriPB with `--requireUnsat`.

## Claim boundary

Supported claim: **link class 63 is eliminated**.

Not supported by this checkpoint alone: **`C(13,7,4)=30`**.

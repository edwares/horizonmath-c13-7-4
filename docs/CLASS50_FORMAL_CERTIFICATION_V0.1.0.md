# Class-50 formal certification v0.1.0

Status date: 2026-08-08 UTC

## Result

Link class 50 is formally eliminated under the audited link-class reduction.
The structural candidate minimum-point four-set partition has 35 orbits. Three
orbits are eliminated directly at the root, and an independently recomputed
exact-minimum-set / degree-profile decomposition of the other 32 orbits is
covered by 1508 pinned-VeriPB UNSAT proofs with no gaps or duplicates.

This does **not** by itself prove `C(13,7,4)=30`.

## Exhaustive formal coverage

The three root-pruned candidate orbits are `21, 33, 34`. Their exact Farkas
proofs all pass VeriPB with `--requireUnsat`.

Re-expanding the other 32 candidate orbits gives 138 exact minimum-set orbits
and 1508 exact degree-profile orbits. Their formal proof partition is:

| Method | Verified profiles |
|---|---:|
| Direct exact root-LP Farkas | 1343 |
| Exact forced pair cuts, then Farkas | 156 |
| Exact split tree with Farkas leaves | 9 |
| **Total** | **1508** |

The nine split-tree residuals are:

| Profile index | Pair cuts | Nodes | Leaves |
|---:|---:|---:|---:|
| 9 | 3 | 391 | 196 |
| 11 | 3 | 389 | 195 |
| 146 | 8 | 45 | 23 |
| 147 | 2 | 283 | 142 |
| 148 | 1 | 263 | 132 |
| 149 | 2 | 319 | 160 |
| 686 | 3 | 33 | 17 |
| 687 | 1 | 179 | 90 |
| 688 | 0 | 213 | 107 |

The class-level audit independently recomputes the retained exact minimum
sets and degree profiles, rebuilds every verifier OPB, checks proof/tree/log
hashes, requires one common verifier fingerprint, and requires exact profile
coverage. The checked-in closure record is
[`results/class50-formal-certification-v0.1.0/class50-formal-closure.json`](../results/class50-formal-certification-v0.1.0/class50-formal-closure.json),
SHA-256:

`cdcc401a0dac72e064cd6d216676e3763c2c44eda8084da43ff4ed1c81249699`

## Durable proof checkpoint

The consolidated proof checkpoint is
`C13_class50_formal_checkpoint_2026-08-08.zip`, SHA-256:

`d886ee445710de3ae86bc27a259a6cf01e96548015691e1b3df00d2efc2b4712`

It contains the complete Class 50 recovery/proof tree, exact OPB/PBP proof
artifacts, verification logs, the pinned verifier wheel, and the recovery
source Git bundle. The archive passed an integrity test before this reference
was recorded.

Every formal verification source uses the same VeriPB wheel, SHA-256:

`3844f3b416c870f6ef96fc737125e4ec97b6cfd1c4d1726a2bc158626c77b369`

## Proof discipline

Floating-point LP is used only to discover supports, integral cuts, and branch
choices. No floating-point solver disposition is promoted to an elimination.
Root contradictions, derived pair bounds, and split-tree leaves are converted
to exact integer certificates and the stitched pseudo-Boolean proofs are then
checked independently by VeriPB with `--requireUnsat`.

## Claim boundary

Supported claim: **link class 50 is eliminated**.

Not supported by this checkpoint alone: **`C(13,7,4)=30`**.

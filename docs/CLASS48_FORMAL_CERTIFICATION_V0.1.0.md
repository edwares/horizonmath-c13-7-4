# Class-48 formal certification v0.1.0

Status date: 2026-08-08 UTC

## Result

Link class 48 is formally eliminated under the audited link-class reduction.
The structural candidate minimum-point four-set partition has 35 orbits. Ten
orbits are eliminated directly at the root, and an independently recomputed
exact-minimum-set / degree-profile decomposition of the other 25 orbits is
covered by 675 pinned-VeriPB UNSAT proofs with no gaps or duplicates.

This does **not** by itself prove `C(13,7,4)=30`.

## Exhaustive formal coverage

The 10 root-pruned candidate orbits are
`1, 3, 5, 6, 7, 8, 10, 12, 20, 21`. Their exact Farkas proofs all pass VeriPB
with `--requireUnsat`.

Re-expanding the other 25 candidate orbits gives 78 exact minimum-set orbits
and 675 exact degree-profile orbits. Their formal proof partition is:

| Method | Verified profiles |
|---|---:|
| Direct exact root-LP Farkas | 509 |
| Exact forced pair cuts, then Farkas | 157 |
| Exact split tree with Farkas leaves | 9 |
| **Total** | **675** |

The nine split-tree residuals are:

| Profile index | Pair cuts | Nodes | Leaves |
|---:|---:|---:|---:|
| 23 | 8 | 357 | 179 |
| 24 | 3 | 377 | 189 |
| 162 | 11 | 53 | 27 |
| 163 | 1 | 293 | 147 |
| 164 | 2 | 259 | 130 |
| 165 | 5 | 275 | 138 |
| 451 | 0 | 35 | 18 |
| 452 | 2 | 193 | 97 |
| 453 | 1 | 223 | 112 |

The class-level audit independently recomputes the retained exact minimum
sets and degree profiles, rebuilds every verifier OPB, checks proof/tree/log
hashes, requires one common verifier fingerprint, and requires exact profile
coverage. The checked-in closure record is
[`results/class48-formal-certification-v0.1.0/class48-formal-closure.json`](../results/class48-formal-certification-v0.1.0/class48-formal-closure.json),
SHA-256:

`8b108f154e1e7e786f7f75e2f9db154803999e01a439cb5e746548c95dea61d2`

## Durable proof checkpoint

The consolidated proof checkpoint is
`C13_class48_formal_checkpoint_2026-08-08.zip`, SHA-256:

`993f070de1c1f3aa2caeef2497d18e1fd319d5dbec06b7f5bd071166cb670230`

It contains the complete Class 48 recovery/proof tree, exact OPB/PBP proof
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

Supported claim: **link class 48 is eliminated**.

Not supported by this checkpoint alone: **`C(13,7,4)=30`**.

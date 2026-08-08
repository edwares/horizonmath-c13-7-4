# C(13,7,4) work — link class 68

Status: **VERIFIED_UNSAT_CLASS_68**

Link class 68 is formally eliminated. Its structural minimum-point-set partition has 12 candidate orbits, and the final closure audit accounts for all 12 with independently VeriPB-verified UNSAT proofs.

## Formal coverage

- Candidate orbits `1, 3, 6, 7, 8, 11`: direct exact root-LP Farkas proofs, all 6 checked by VeriPB with `--requireUnsat`.
- Candidate orbit `2`, representative `[0,1,2,6]`: previously closed by the exhaustive 155-profile formal certification; all 155/155 profiles are VeriPB `VERIFIED_UNSAT`.
- Candidate orbits `0, 4, 5, 9, 10`: re-enumerated after removing the seven eliminated orbits above. Their retained exact-minimum-set decomposition has 8 cases and 46 target-profile occurrences in total.
  - 43 profile occurrences are covered by direct root Farkas or forced integral pair-cut/Farkas proofs and are VeriPB `VERIFIED_UNSAT`.
  - The only three remaining occurrences (orbit 4 index 15, orbit 5 index 13, orbit 9 index 13) are the same exact profile formula, with canonical formula SHA-256 `1c5d7b88906c89280e3bdbce4c74fbafacf1d350bf2e5cf5c7d7c7d2fbc057b0`.
  - That shared formula is refuted by 13 exact one-sided pair CG cuts followed by a 203-node / 102-leaf exact Farkas split tree (maximum depth 39). The stitched proof passes VeriPB with `--requireUnsat`.

The class-level closure manifest is `build/class68-formal-closure-r26.json`, SHA-256:

`ed2b3532c4e0f337fc3afcad05711135d175c639bd007414c8c638073c3a76d7`

A deterministic rerun of the closure audit reproduced the same manifest hash.

The VeriPB wheel used by every formal source in the closure has SHA-256:

`3844f3b416c870f6ef96fc737125e4ec97b6cfd1c4d1726a2bc158626c77b369`

## Scope

This result eliminates link class 68. Together with the already published elimination of link class 52, two of the 68 link classes are now formally eliminated.

This does **not** by itself prove `C(13,7,4)=30`; the other 66 link classes still require formal elimination (or a stronger argument that closes them collectively).

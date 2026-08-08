# C(13,7,4) work — link class 63

Status: **VERIFIED_UNSAT_CLASS_63**

Link class 63 is formally eliminated. Its structural minimum-point four-set
partition has 58 candidate orbits, and the class-level closure audit
independently accounts for all 58 with exact proofs accepted by VeriPB using
`--requireUnsat`.

## Formal coverage

- 42 candidate orbits have direct exact root-LP Farkas contradictions, all
  VeriPB `VERIFIED_UNSAT`.
- The other 16 candidate orbits expand into 53 exact minimum-set orbits and
  460 exact degree-profile orbits.
- Of those 460 profiles, 232 have direct root-LP Farkas contradictions and
  215 close after exact integral pair cuts followed by Farkas contradiction.
- The remaining 13 profile indices
  `293, 317, 334, 353, 384, 407, 427, 428, 430, 449, 450, 452, 459`
  close by exact split-tree/Farkas proofs. All 13 stitched proofs are VeriPB
  `VERIFIED_UNSAT`.

The class-level closure manifest is `class63-formal-closure.json`, SHA-256:

`09be1a62500c132bd5462c8d0ab9d312bbd79e62492ced275e81e2823b346f32`

The consolidated formal checkpoint archive is
`C13_class63_formal_checkpoint_2026-08-08.zip`, SHA-256:

`91ea983c43f801802dc225a3491bf7a41397e7eb2686175c55776234f9f207e2`

The verifier wheel used throughout has SHA-256:

`3844f3b416c870f6ef96fc737125e4ec97b6cfd1c4d1726a2bc158626c77b369`

## Scope

This result eliminates link class 63. It does **not** by itself prove
`C(13,7,4)=30`; the remaining link classes still require formal elimination or
a stronger exhaustive argument.

# C(13,7,4) work — link class 50

Status: **VERIFIED_UNSAT_CLASS_50**

Link class 50 is formally eliminated. Its structural minimum-point four-set partition has 35 candidate orbits, and the class-level closure audit independently accounts for all 35 with exact proofs accepted by VeriPB using `--requireUnsat`.

## Formal coverage

- Candidate orbits `21, 33, 34`: 3 direct exact root-LP Farkas contradictions, all VeriPB `VERIFIED_UNSAT`.
- The other 32 candidate orbits expand into 138 exact minimum-set orbits and 1508 exact degree-profile orbits.
- Of those 1508 profiles, 1343 have direct root-LP Farkas contradictions and 156 close after exact forced integral pair cuts followed by Farkas contradiction.
- The remaining nine profile indices `9, 11, 146, 147, 148, 149, 686, 687, 688` close by exact split-tree/Farkas proofs. All nine stitched proofs are VeriPB `VERIFIED_UNSAT`.

The class-level closure manifest is `class50-formal-closure.json`, SHA-256:

`cdcc401a0dac72e064cd6d216676e3763c2c44eda8084da43ff4ed1c81249699`

The consolidated formal checkpoint archive is `C13_class50_formal_checkpoint_2026-08-08.zip`, SHA-256:

`d886ee445710de3ae86bc27a259a6cf01e96548015691e1b3df00d2efc2b4712`

The verifier wheel used throughout has SHA-256:

`3844f3b416c870f6ef96fc737125e4ec97b6cfd1c4d1726a2bc158626c77b369`

## Scope

This result eliminates link class 50. It does **not** by itself prove `C(13,7,4)=30`; the remaining link classes still require formal elimination or a stronger exhaustive argument.

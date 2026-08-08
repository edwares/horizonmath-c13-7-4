# C(13,7,4) work — link class 48

Status: **VERIFIED_UNSAT_CLASS_48**

Link class 48 is formally eliminated. Its structural minimum-point four-set partition has 35 candidate orbits, and the class-level closure audit independently accounts for all 35 with exact proofs accepted by VeriPB using `--requireUnsat`.

## Formal coverage

- Candidate orbits `1, 3, 5, 6, 7, 8, 10, 12, 20, 21`: 10 direct exact root-LP Farkas contradictions, all VeriPB `VERIFIED_UNSAT`.
- The other 25 candidate orbits expand into 78 exact minimum-set orbits and 675 exact degree-profile orbits.
- Of those 675 profiles, 509 have direct root-LP Farkas contradictions and 157 close after exact forced integral pair cuts followed by Farkas contradiction.
- The remaining nine profile indices `23, 24, 162, 163, 164, 165, 451, 452, 453` close by exact split-tree/Farkas proofs. All nine stitched proofs are VeriPB `VERIFIED_UNSAT`.

The class-level closure manifest is `class48-formal-closure.json`, SHA-256:

`8b108f154e1e7e786f7f75e2f9db154803999e01a439cb5e746548c95dea61d2`

The consolidated formal checkpoint archive is `C13_class48_formal_checkpoint_2026-08-08.zip`, SHA-256:

`993f070de1c1f3aa2caeef2497d18e1fd319d5dbec06b7f5bd071166cb670230`

The verifier wheel used throughout has SHA-256:

`3844f3b416c870f6ef96fc737125e4ec97b6cfd1c4d1726a2bc158626c77b369`

## Scope

This result eliminates link class 48. It does **not** by itself prove `C(13,7,4)=30`; the remaining link classes still require formal elimination or a stronger exhaustive argument.

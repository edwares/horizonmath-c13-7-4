# Class-52 candidate-screening certification phase

Audit date: 2026-07-29 UTC

Status extension: the split-tree task identified at the end of this report is
complete. Orbits `5,6,8,14` are now `VERIFIED_UNSAT`; see
[`SPLIT_FARKAS_PHASE_AUDIT.md`](SPLIT_FARKAS_PHASE_AUDIT.md). This report is
retained as the audit of the preceding 15-proof root-LP subphase.

## Outcome

The historical class-52 candidate minimum-point screen has been reconstructed
as a class-agnostic, deterministic formula generator. Fifteen of its 26
candidate orbits now have fresh VeriPB-accepted exact root-LP Farkas
certificates.

| Check | Result |
|---|---:|
| Candidate-orbit formulas emitted | 26/26 |
| Independent historical-source row comparisons | 26/26 |
| Rows compared per formula | 567 |
| Root LP `SOLVER_UNSAT` | 15 |
| Root LP feasible | 11 |
| Exact Farkas proofs generated | 15/15 |
| Independent exact arithmetic/PBP audits | 15/15 |
| Expected formula hashes matched | 15/15 |
| Expected proof hashes matched | 15/15 |
| VeriPB runs using `--requireUnsat` | 15/15 |
| VeriPB zero exits and success reports | 15/15 |
| Independent verification-log audits | 15/15 |

The 15 formally pruned orbit indices are:

`0,1,2,3,4,7,9,10,11,12,13,15,16,17,18`

The 11 retained orbit indices are:

`5,6,8,14,19,20,21,22,23,24,25`

Among those 11, the controlled three-second MILP run reports
`SOLVER_UNSAT` for `5,6,8,14` and `TIMEOUT` for `19` through `25`. The four
solver reports are not formal eliminations.

## Recovered historical source

The exact historical model source is
`legacy_source/full_minpoints.py` in the corrected checkpoint. Its semantics
are:

1. 792 binary variables, one for each lexicographic seven-subset;
2. 279 residual four-set lower bounds;
3. 12 point-degree lower bounds;
4. an upper bound fixing each of the four selected candidate points at its
   minimum extension degree;
5. 66 positive pair lower bounds;
6. 204 positive triple lower bounds;
7. exactly 14 extension blocks.

This gives 562 bounded mathematical rows and 567 serialized inequalities.

The original 26 per-orbit solver result files remain unavailable. The
historical source later records:

`HARD4 = {14,19,20,21,22,23,24,25}`

so the old exploratory partition can be reconstructed as the complement
`18 / 8`, but the missing result files, commands, solver version, logs, and
hashes cannot be inferred.

## Independent formula audit

`scripts/audit_candidate_screening_source.py` does not import the candidate
formula builder. It independently transcribes the historical source, parses
each generated OPB, and compares every row in order.

All 26 comparisons pass. Every candidate orbit is present exactly once. The
native formula hashes and independently computed canonical formula hashes
match their manifests.

## Controlled solver reconstruction

The screening run used SciPy 1.17.0 with bundled HiGHS 1.8.0, one thread, a
zero feasibility objective, deterministic options, a three-second root-LP
limit, and a three-second MILP limit.

The root LP split is:

- 15 `SOLVER_UNSAT`;
- 11 `LP_FEASIBLE`.

The aggregate MILP outcome is:

- 19 `SOLVER_UNSAT`;
- 7 `TIMEOUT`.

The fresh exploratory result agrees with the historical disposition on 25 of
26 orbits. Orbit 14 is newly solver-UNSAT within the short modern run, whereas
the historical run retained it. This is recorded as solver/runtime drift. It
does not alter the historical 107-profile regression and does not authorize
formal pruning without a certificate.

## Exact Farkas method

For each root-LP-infeasible formula:

1. HiGHS dual simplex identifies a sparse nonnegative Farkas support,
   including Boolean bounds;
2. exact sparse Gaussian elimination over `fractions.Fraction` computes the
   one-dimensional nullspace;
3. the vector is converted to primitive, strictly positive integers;
4. all row coefficients and the contradiction RHS are recomputed with Python
   arbitrary-precision integers;
5. required Boolean lower or upper bounds are added exactly;
6. a four-line VeriPB cutting-planes proof is emitted.

All 15 generated certificates cancel all 792 variable coefficients and leave
a strictly positive contradiction RHS. The proof files are deterministic.

`scripts/audit_root_lp_farkas.py` independently parses both formulas and every
PBP token and repeats the full integer sum without importing the generator.
It passes 15/15.

## Native and verifier formula boundary

The historically exact native screens contain five `<=` inequalities. The
VeriPB 0.3a0 parser bundled with the public release expects the
verifier-normalized syntax used in the published certificates.

Therefore both artifacts are preserved:

- the native formula, which is compared row for row with the historical
  source;
- an all-`>=` verifier formula, in which every native `<=` row has its
  coefficients and RHS negated.

Row order and constraint IDs are unchanged. The independent audit parses both
and confirms ordered canonical equality. An initial attempt to submit the
native syntax failed at parsing and is preserved under `build/archive/`; it
never produced a verification claim.

## VeriPB provenance and verification

The immutable public release archive is:

`Class52_formal_certification_complete.zip`

SHA-256:

`c4c1ddc812affd9bd05c452855bdfcd614a68906f8bf536fab8bcd4b3123ae56`

Its bundled extension binaries target CPython 3.13. No ABI renaming is used.
Instead, `scripts/build_veripb_cp312.py` performs a clean CPython 3.12 rebuild
from the immutable archive's generated C and C++ sources with pinned
dependencies. The resulting wheel is:

`verifier/veripb-0.3a0-cp312-cp312-linux_x86_64.whl`

SHA-256:

`3844f3b416c870f6ef96fc737125e4ec97b6cfd1c4d1726a2bc158626c77b369`

Before use, the rebuilt verifier accepted the already published
`c52_case21_profile014_pair12_eq6` proof with `--requireUnsat`, exit code zero,
and `Verification succeeded.`

For the new corpus, the verification driver:

- matched the immutable source archive, build setup, wheel, installed wheel
  `RECORD`, formula, proof, and certificate hashes;
- used `--requireUnsat` in every command;
- preserved stdout, stderr, exit code, command, duration, and hashes;
- promoted an orbit only after exit code zero and the exact success report.

The independent verification audit passes all 15 records.

## Formal status

| Layer | Status |
|---|---|
| Candidate-orbit enumeration | `ENUMERATED` |
| Candidate formulas | `FORMULAS_GENERATED` 26/26 |
| Root-LP exact proofs | `PROOF_GENERATED` 15/26 |
| Root-LP formal verification | `VERIFIED_UNSAT` 15/26 |
| MILP-only unresolved formulas | `SOLVER_UNSAT` 4/26 |
| Timed-out formulas | `TIMEOUT` 7/26 |
| Candidate orbits formally retained | 11/26 |
| Class 52 | not `CLASS_FORMALLY_ELIMINATED` by this phase |

This phase certifies only the 15 listed candidate-orbit exclusions. The
downstream historical exclusions of 17 exact-minimum-set cases and 87 early
profiles remain solver-only, although the final 30 published formulas remain
formally certified.

## Principal artifacts

- `build/class52.candidate-screens/`
- `build/class52.candidate-screening-source-comparison.json`
- `build/class52.candidate-screening-solver/`
- `build/class52.candidate-root-lp-farkas/`
- `build/class52.candidate-root-lp-farkas-audit.json`
- `build/class52.candidate-root-lp-verification/`
- `build/class52.candidate-root-lp-verification-audit.json`
- `build/class52.candidate-screening-phase.manifest.json`
- `verifier/build.provenance.json`

No candidate orbit disappears silently; the phase manifest contains one final
record for each index 0 through 25.

## Next bounded task

The identified split-tree task has been completed and independently audited.
All 18 historically discarded candidate orbits now have verified
certificates, and orbit 14 is one additional verified exclusion tracked
separately because its fresh result differs from the historical retained
disposition.

The remaining candidate orbits `19` through `25` are `TIMEOUT`. Before
another class is launched, the project must also resolve the audited
classification-source and numbering-map requirement described in
`PROVENANCE.md`.

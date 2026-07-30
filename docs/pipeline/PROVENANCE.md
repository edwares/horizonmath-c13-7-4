# Provenance boundary

## Recovered source chain

The class-52 reconstruction uses the following archived project artifacts:

| Artifact | SHA-256 |
|---|---|
| `HorizonMath_C13_7_4_research_v1.zip` | `a0ee576c68caf4259e314b0a3db899f5e36e41b06a3e0de0ac05271fcfd15b99` |
| `HorizonMath_C13_7_4_research_v2.zip` | `a2d77bf206497a0d6afde2704f5f269adc528e7eb0a8df6cf8a54be5ac9c363e` |
| `HorizonMath_C13_7_4_sat_bundle.zip` | `06ae94d3fd8a7e7f91d8022bd8f0a05a87775ef65eca1bd8cb6460c3cbca18e1` |
| `HorizonMath_C13_7_4_class52_checkpoint.zip` | `4114c7965c4c112afa31996bf785b2c388640042a6d6b574652649ab4cf09377` |
| `HorizonMath_C13_7_4_class52_corrected_checkpoint.zip` | `6a6d69fb5886c795c2ec285b6fa9558f27159201bcdb9ca9ae045f57149102e3` |
| `HorizonMath_C13_7_4_class52_pb_bundle.zip` | `7a59e48afd3895e15f267913d65a7ef058f68e1551c418ee647d1488b67c49bb` |

The corrected checkpoint's `SHA256SUMS` file omits the conventional
digest/path whitespace separator. Splitting every row after its 64-character
digest validates all 228 entries.

The separate public certification release remains pinned by:

- GitHub: <https://github.com/edwares/class52-formal-certification>
- Zenodo version DOI: <https://doi.org/10.5281/zenodo.21660461>

The prior source/asset audit found the six GitHub and Zenodo assets
byte-for-byte identical and confirmed the archived 30/30 `--requireUnsat`
verification result.

The complete immutable release archive used for the fresh verifier rebuild is
`Class52_formal_certification_complete.zip`, SHA-256
`c4c1ddc812affd9bd05c452855bdfcd614a68906f8bf536fab8bcd4b3123ae56`.

## Numbering source

The labeled class-52 link is
`results/link_classes.json: representatives[51]`. Its canonical labeled-link
SHA-256 is:

`034d4c7cd44947c6fe2e8d562850611670af399f5d850b2c141990152a6af571`

The SAT bundle contains deterministic classification code and data:

- 67 ordered representatives produced from the first published template;
- a separate second-template representative, `fig6`;
- class-specific metadata and CNFs numbered 1 through 68.

The archived `classify_links.py` stops after finding 67 first-template classes,
rather than completing all 21,952 template completions. It therefore supplies
the project's representatives and numbering convention but is not, by itself,
an independent proof of classification exhaustiveness. A literature/source
audit and a complete rerun without the early stop remain required before
claiming an audited exhaustive 68-class catalog.

## Independently recomputed

The new standard-library implementation recomputes, without importing the
historical SciPy model:

- cover validation and all multiplicities;
- all 36 class-52 automorphisms;
- all 26 four-set orbits;
- exact minimum-point-set orbits;
- stabilizers and exact extension-degree profile orbits;
- the corrected pseudo-Boolean rows and native OPB serialization.

The historical `HARD4` set is:

`{14,19,20,21,22,23,24,25}`

It is parsed from the recovered source and recorded as screening provenance.
It is not re-derived from missing evidence.

Using that recorded screening input, the reconstruction finds:

- raw exact minimum sets by size:
  `144, 126, 84, 36, 9, 1` for sizes 4 through 9;
- 400 raw exact minimum sets total;
- 26 exact-minimum-set orbits;
- nine profile-decomposed cases:
  `4,18,19,20,21,22,23,24,25`;
- 225 raw positive profiles;
- 107 profile orbits.

Every generated `(case, profile)` vector matches exactly one row of
`results/corrected_statuses.json` and its archived result file.

## Formula reconstruction

The corrected generator uses:

1. residual four-set coverage;
2. exact extension point degrees;
3. pair lower bounds;
4. corrected pair upper bounds
   `min(6*r_i-70-ell_ij, 6*r_j-70-ell_ij)`;
5. positive triple lower bounds;
6. exactly 14 extension blocks;
7. an optional exact pair-multiplicity split.

The fixed link pair multiplicity `ell_ij` is subtracted exactly once.

The 19 direct formulas contain 562 mathematical rows serialized as 641 OPB
constraints. The eleven split formulas contain 563 mathematical rows
serialized as 643 OPB constraints.

All 30 regenerated native files are byte-for-byte identical to the recovered
native OPBs. Their ordered canonical-row hashes also match the formulas in the
published certification corpus.

## Fresh candidate-screening certification

The surviving `full_minpoints.py` source was independently transcribed into a
class-agnostic generator. It emits 26 formulas, one for every four-set orbit.
Every one of their 567 serialized rows matches the independently transcribed
historical semantics in order.

A controlled SciPy/HiGHS run found 15 root-LP-infeasible formulas and 11
root-LP-feasible formulas. Exact integer Farkas proofs were generated for all
15 infeasible relaxations. An independent parser and arbitrary-precision
integer audit passes 15/15.

The public release's VeriPB 0.3a0 source was cleanly rebuilt for CPython 3.12.
The preserved wheel has SHA-256
`3844f3b416c870f6ef96fc737125e4ec97b6cfd1c4d1726a2bc158626c77b369`.
It first accepted a published class-52 proof. It then accepted all 15 new
proofs with `--requireUnsat`. Expected formula and proof hashes matched in
every run; all exits were zero; all logs report `Verification succeeded.`;
and an independent verification-log audit passes 15/15.

Formal pruning is therefore authorized for candidate-orbit indices
`0,1,2,3,4,7,9,10,11,12,13,15,16,17,18`.

The subsequent LP split-tree phase addresses the four root-LP-feasible
solver-UNSAT formulas `5,6,8,14`. The generalized implementation emitted four
complete trees with 28 total nodes and 16 LP-infeasible leaves. Every leaf has
an exact positive-integer Farkas clause; an independent implementation
recomputed all 16 clauses, resolved every tree to the empty root clause, and
rebuilt all four proof files byte for byte.

The pinned VeriPB rebuild then accepted all four expected proofs with
`--requireUnsat`. Formula and proof hashes matched, all exits were zero, and
an independent verification audit passes 4/4. Formal pruning is therefore
also authorized for `5,6,8,14`.

The consolidated candidate-orbit statuses are:

- `VERIFIED_UNSAT`: every index `0` through `18`;
- `TIMEOUT`: `19,20,21,22,23,24,25`.

The exact split reconstruction used pinned SymPy 1.13.3 and mpmath 1.3.0
wheels preserved under `proof_dependencies/`. Their hashes are recorded in
the split corpus manifest and `SPLIT_FARKAS_PHASE_AUDIT.md`.

The native screens and verifier formulas are distinct, hashed artifacts. The
five native `<=` rows are rewritten as equivalent all-`>=` rows by negating
their coefficients and RHS. Row order and constraint IDs are preserved, and
the independent audit confirms ordered canonical equality.

## Evidence that remains incomplete

The recovered checkpoint contains solver logs/results, not formal
certificates, for:

- 17 whole exact-minimum-set exclusions;
- 70 base-profile exclusions;
- 17 proof-tuned profile exclusions.

The individual result files from the earlier 26-model `full_minpoints` screen
were not recovered. The source survives, and the later `HARD4` constant
identifies the eight historically retained four-set orbits, but the original
18 discarded-orbit records and their hashes are absent. Fresh exact root-LP
and split-tree certificates now replace the mathematical evidence for all 18
historically discarded orbits. Orbit 14, which was historically retained, is
one additional fresh formal candidate-screen exclusion and remains marked as
a historical solver-disposition difference.

Accordingly:

| Layer | Current status |
|---|---|
| Link/group/orbit/profile enumeration | `ENUMERATED` |
| Candidate-orbit screens | `FORMULAS_GENERATED` 26/26 |
| Candidate root-LP proofs | `PROOF_GENERATED` 15/26 |
| Candidate LP split-tree proofs | `PROOF_GENERATED` 4/26 |
| Candidate formally pruned | `VERIFIED_UNSAT` 19/26 |
| Candidate unresolved | 7 `TIMEOUT` |
| 17 whole-case exclusions | `SOLVER_UNSAT` |
| 87 early profile exclusions | `SOLVER_UNSAT` |
| 20 retained profiles / 30 current OPBs | `FORMULAS_GENERATED` |
| Prior published 30-formula corpus | `VERIFIED_UNSAT` |
| Current end-to-end class status | not `CLASS_FORMALLY_ELIMINATED` |

This is stricter than treating archived HiGHS status 2 as a proof. It follows
the program rule that `SOLVER_UNSAT` must never be promoted to
`VERIFIED_UNSAT`.

The next proof work must either address candidate orbits `19` through `25`,
formalize the remaining upstream exact-set/profile exclusions, or replace the
screening reduction with a formally certified exhaustive construction whose
leaves are the 30 published formulas. No other class should be treated as
part of an audited exhaustive 68-class campaign until the classification
source and numbering map are independently audited.

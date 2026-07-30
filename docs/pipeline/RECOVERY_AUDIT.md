# HorizonMath class-52 provenance-recovery audit

Audit date: 2026-07-29 UTC

## Outcome

Recent-chat and project-file recovery closed the earlier 107-profile
reconstruction blocker. The generalized code now reproduces the complete
class-52 combinatorial path from the eight historically retained four-set
orbits through all 107 exact degree profiles and all 30 corrected native
formulas.

The final automated result is:

| Check | Result |
|---|---:|
| Unit/regression tests | 40/40 pass |
| Class-52 regression checks | 32/32 pass |
| Exact profile rows | 107/107 match |
| Historical partition | 70/17/20 exact |
| Retained profiles | 20/20 exact |
| Pair split | 11 branches, values 4–14 |
| Regenerated OPBs | 30/30 byte-identical |
| Canonical formula comparisons | 30/30 equal |

No solver or proof-generation run was used to obtain those historical
regression results. A separate audited phase has now reconstructed and
partially certified the earlier candidate-orbit screen.

## Candidate-screening certification update

The generalized `full_minpoints` implementation emits one formula for each of
the 26 candidate four-set orbits. An independent implementation parses every
generated OPB and compares all 567 rows with the historical source semantics.
All 26 formulas pass.

The controlled solver result is:

- root LP: 15 `SOLVER_UNSAT`, 11 feasible;
- short MILP: 19 `SOLVER_UNSAT`, 7 `TIMEOUT`.

All 15 root-LP-infeasible formulas now have deterministic exact Farkas proofs.
An independent integer/PBP audit passes 15/15. A clean CPython 3.12 rebuild of
the immutable release's VeriPB source accepted all 15 with `--requireUnsat`;
all expected formula and proof hashes matched, all exits were zero, every log
reported success, and a separate log/status audit passes 15/15.

The later split-tree extension now gives:

- 19 `VERIFIED_UNSAT` (every orbit index `0` through `18`);
- 7 `TIMEOUT` (`19` through `25`).

The four added proofs use 28 split-tree nodes and 16 independently checked
exact leaf clauses. VeriPB accepted all four with `--requireUnsat`, and the
separate hash/log audit passes 4/4. See `SPLIT_FARKAS_PHASE_AUDIT.md`.

This is a further formal improvement to the upstream chain, but it does not
by itself make this fresh pipeline claim class 52
`CLASS_FORMALLY_ELIMINATED`.

## What was recovered

### Classification and early research

- `HorizonMath_C13_7_4_research_v1.zip`
- `HorizonMath_C13_7_4_research_v2.zip`
- `HorizonMath_C13_7_4_sat_bundle.zip`
- `classify_links.py`
- `link_extension.py`
- `results/link_classes.json`
- 68 class metadata records and CNFs

### Class-52 orbit and screening work

- `full_minpoints.py`
- `exact_minset.py`
- `degree_profiles.py`
- `degree_profiles_prove.py`
- `degree_profiles_pairlp_corrected.py`
- `portable_corrected_model.py`
- `results/class52_automorphisms.json`
- `results/class52_minpoint4_orbits.json`
- `results/statuses.json`
- `results/corrected_statuses.json`
- 17 archived exact-minimum-set infeasibility records
- 70 base-profile records
- 17 proof-tuned profile records
- 19 corrected direct-profile records
- eleven corrected pair-split records

### Native PB and certification linkage

- 30 native OPBs and per-instance metadata
- native normalized-row hashes
- recovered native manifest
- prior canonical native-to-published formula comparison
- prior formula/proof hashes and final certification-audit flags

## Reconstruction details

The class-52 link has point degrees:

`(9,7,7,7,9,7,7,7,9,7,7,7)`

The minimum extension degree vector is:

`(6,8,8,8,6,8,8,8,6,8,8,8)`

Fourteen extension blocks of size seven contribute 98 point incidences. The
minimum vector contributes 90, leaving exactly eight integral excess units.
Thus at least four points have zero excess.

The complete order-36 automorphism group partitions all 495 four-subsets into
26 orbits. The recovered historical screen retains orbit indices:

`14,19,20,21,22,23,24,25`

A larger exact minimum-point set is admissible only when each of its
four-subsets lies in one of those retained orbits. Enumerating all such sets
and quotienting by the complete group gives:

| Exact-set size | Raw sets | Orbits |
|---:|---:|---:|
| 4 | 144 | 8 |
| 5 | 126 | 7 |
| 6 | 84 | 6 |
| 7 | 36 | 3 |
| 8 | 9 | 1 |
| 9 | 1 | 1 |
| Total | 400 | 26 |

Seventeen cases have archived whole-case HiGHS infeasibility reports. The
remaining nine case identifiers are:

`4,18,19,20,21,22,23,24,25`

For an exact minimum set `M`, every point outside `M` receives a positive
integer excess and the total excess is eight. Positive compositions are
enumerated lexicographically and quotiented by the full stabilizer of `M`.

| Case | Size of `M` | Stabilizer | Raw profiles | Profile orbits |
|---:|---:|---:|---:|---:|
| 4 | 4 | 2 | 1 | 1 |
| 18 | 6 | 12 | 21 | 6 |
| 19 | 6 | 2 | 21 | 13 |
| 20 | 6 | 6 | 21 | 6 |
| 21 | 7 | 4 | 35 | 16 |
| 22 | 7 | 4 | 35 | 19 |
| 23 | 7 | 2 | 35 | 19 |
| 24 | 8 | 4 | 35 | 22 |
| 25 | 9 | 36 | 21 | 5 |
| Total |  |  | 225 | 107 |

The recovered profile ledger partitions the 107 rows as:

- 70 `initial_milp`;
- 17 `proof_tuned_milp`;
- 19 `corrected_pairbound_milp`;
- one `corrected_pair_split`.

The last two categories are the historical group of 20 corrected/retained
profiles.

## Exact formula regression

The new generator uses 792 Boolean variables, one for each labeled
seven-subset in lexicographic order. For every retained profile it emits
constraints in a fixed order:

1. 279 residual four-set covering inequalities;
2. 12 exact point-degree rows;
3. 66 corrected pair intervals;
4. 204 positive triple lower bounds;
5. one exact 14-block row;
6. an optional exact pair-split row.

An equality or finite interval is serialized as separate lower and upper OPB
inequalities. This gives:

- 562 mathematical rows and 641 OPB constraints for a direct formula;
- 563 mathematical rows and 643 OPB constraints for a split formula.

The renderer also reproduces the original header, comment, variable, row, and
whitespace conventions. All 30 output byte hashes equal the recovered native
hashes.

## Provenance/status finding

The public certification verifies the 30 published formulas. The recovered
upstream screening chain is not uniformly formal:

| Upstream group | Count | Recovered evidence |
|---|---:|---|
| Initial four-orbit exclusions | 18 | all 18 have fresh `VERIFIED_UNSAT`; original result files remain missing |
| Whole exact-minimum-set exclusions | 17 | HiGHS status 2 |
| Base profile exclusions | 70 | HiGHS status 2 |
| Proof-tuned profile exclusions | 17 | HiGHS status 2 |
| Corrected retained profile formulas | 30 formulas from 20 profiles | published VeriPB certificates |

This matters because formula UNSAT and reduction exhaustiveness are separate
claims. The present pipeline records the 30 prior formulas as
`VERIFIED_UNSAT`, but keeps the archived HiGHS rows at `SOLVER_UNSAT`.

## Classification-source finding

The recovered classification source constructs first-template completions and
groups them by exact incidence-graph isomorphism. It stops once it has found
67 classes after 2,681 completions, relying on the published expectation that
there are 67 first-template classes. The full template space has 21,952
completions. The second template supplies the separate `fig6` representative.

Therefore the recovered files provide:

- the exact project numbering used by the 68 downstream class files;
- all labeled representatives;
- deterministic classification mechanics.

They do not yet provide:

- a complete no-early-stop run over all 21,952 first-template completions;
- an audited proof that the two templates exhaust all minimum
  `C(12,6,3)` covers;
- an independently audited literature-to-numbering map.

## Minimum missing evidence

The remaining minimum provenance requests are:

1. for a complete historical audit, the 26 original
   `results/full_minpoints/orbit_XX.json` files and their exact solver
   environment; the fresh run replaces mathematical evidence for 15 orbits
   but cannot reconstruct missing historical hashes;
2. formal certificates for candidate orbits `5,6,8` (and separately the
   solver-drift orbit `14`);
3. formal certificates for the 17 whole-case and 87 early-profile
   infeasibility claims, or a formally certified replacement reduction;
4. an authoritative classification citation/template derivation;
5. a complete no-early-stop classification run and explicit 1–68 manifest.

Until the remaining formal-reduction gaps are resolved, the safest class-52
statement is:

> The 30 published formulas are formally UNSAT, the recovered
> combinatorial/profile/formula pipeline reproduces them exactly, and 15 of
> the 26 candidate minimum-point orbits now have fresh VeriPB-accepted exact
> Farkas certificates. The other candidate and downstream historical
> exclusions are not yet uniformly formal.

No other link class has been analyzed by this new pipeline.

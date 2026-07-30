# Class-52 LP split-tree/Farkas certification phase

Audit date: 2026-07-29 UTC

## Outcome

The four class-52 candidate screens that were root-LP feasible but reported
MILP `SOLVER_UNSAT` now have complete, exact LP split-tree/Farkas
refutations accepted by VeriPB.

| Check | Result |
|---|---:|
| Selected candidate orbits | 4/4 |
| Complete binary split trees | 4/4 |
| Total tree nodes | 28 |
| LP-infeasible leaves | 16 |
| Exact integer leaf certificates | 16/16 |
| Independent leaf/tree audits | 16/16 |
| Proofs byte-identical to independent rebuild | 4/4 |
| Expected formula hashes matched | 4/4 |
| Expected proof hashes matched | 4/4 |
| VeriPB runs using `--requireUnsat` | 4/4 |
| VeriPB zero exits and success reports | 4/4 |
| Independent verification-log audits | 4/4 |

The status transition is:

| Orbit | Prior status | New status |
|---:|---|---|
| 5 | `SOLVER_UNSAT` | `VERIFIED_UNSAT` |
| 6 | `SOLVER_UNSAT` | `VERIFIED_UNSAT` |
| 8 | `SOLVER_UNSAT` | `VERIFIED_UNSAT` |
| 14 | `SOLVER_UNSAT` | `VERIFIED_UNSAT` |

Orbit 14 remains explicitly marked as a historical-disposition difference:
the recovered exploratory run retained it, while the fresh solver and the new
formal certificate show that its candidate necessary-condition formula is
UNSAT. The historical `18 / 8` regression ledger is preserved unchanged.

## Per-orbit proof structure

| Orbit | Candidate points | Nodes | Leaves | Maximum depth | Proof SHA-256 |
|---:|---|---:|---:|---:|---|
| 5 | `0,1,4,6` | 3 | 2 | 1 | `c95913c838e157ef37a5101627a4ed68c3010512be8a91c509ccf3fb41cfb2ad` |
| 6 | `0,1,4,8` | 5 | 3 | 2 | `60ead95acc08ec3a9437323e64c45a7f026ad182099eb8ff5d36fa97f1ae121a` |
| 8 | `0,1,4,10` | 3 | 2 | 1 | `6e04c9b92b843ea04e284c9306a9dfc2fc4c6824c6ff417ab16d2ec5e87e15a5` |
| 14 | `0,1,6,11` | 17 | 9 | 8 | `8f98cd4d5abd1560720371d36c7b27982661358f6faab173ae7e87b2a6c248de` |

All formulas have 792 variables and 567 ordered constraints. The native
formulas retain their five `<=` rows. The verifier formulas negate those
rows' coefficients and right-hand sides to obtain ordered, canonically
equivalent all-`>=` formulas accepted by the pinned VeriPB release.

## Class-agnostic proof method

For each selected formula, the new `horizonlink.split_farkas` module:

1. solves the root LP with deterministic one-thread HiGHS dual simplex;
2. branches on the unassigned fractional variable closest to one half, using
   the smallest variable index as the tie break;
3. records both binary children and continues until every leaf LP is
   infeasible;
4. extracts a floating nonnegative Farkas support at each leaf;
5. reconstructs the one-dimensional support with SymPy `DomainMatrix` over
   the integer domain;
6. normalizes the ray to primitive, strictly positive integers;
7. recomputes every coefficient and right-hand side with Python integers;
8. omits the path assumptions to derive a globally valid weighted path
   clause;
9. divides and saturates that cut to an ordinary clause;
10. resolves all leaf clauses bottom-up to the empty root clause.

Floating LP results select the tree and supports only. They never authorize a
formal status. Exact integer checks and VeriPB verification are mandatory.

The pinned proof wheels are preserved under `proof_dependencies/`:

| Dependency | SHA-256 |
|---|---|
| `mpmath-1.3.0-py3-none-any.whl` | `a0b2b9fe80bbcd81a6647ff13108738cfb482d481d826cc0e02f5b35e5c88d2c` |
| `sympy-1.13.3-py3-none-any.whl` | `54612cf55a62755ee71824ce692986f23c88ffa77207b30c1368eda4a7060f73` |

## Independent audit

`scripts/audit_split_farkas.py` does not import the split-proof generator. It
independently:

- parses native and verifier OPBs;
- confirms ordered canonical row equality;
- checks every tree parent, child, assignment, branch, and leaf;
- recomputes all 16 Farkas sums with arbitrary-precision integers;
- verifies each leaf clause against its path;
- independently resolves the tree;
- rebuilds every PBP proof byte for byte;
- rehashes every formula, tree, leaf certificate, proof, metadata file,
  manifest, and checksum entry;
- rehashes the five relevant source scripts inside the immutable public
  release.

The audit passes 4/4 instances, 16/16 leaves, and 4/4 independent proof
rebuilds.

## Immutable source provenance

The source mechanism was audited against:

`Class52_formal_certification_complete.zip`

SHA-256:

`c4c1ddc812affd9bd05c452855bdfcd614a68906f8bf536fab8bcd4b3123ae56`

The generalized implementation records hashes for:

- `build_lp_split_tree.py`;
- `extract_leaf_exact_cut.py`;
- `extract_leaf_exact_cut_fast.py`;
- `build_split_tree_proof_generic.py`;
- `certify_remaining_split_trees.py`.

Those scripts were used as a mechanism reference. The generalized module does
not execute or copy class-number-specific source.

## VeriPB verification

The verifier is the preserved CPython 3.12 rebuild of VeriPB 0.3a0. Before
proof submission, the accepted environment matched all 31 hashed files in the
pinned wheel's `RECORD`.

For every orbit:

- the expected verifier-formula hash matched;
- the expected proof hash matched;
- the command contained `--requireUnsat` exactly once;
- the verifier did not time out;
- the exit code was zero;
- stdout was exactly `Verification succeeded.`;
- stderr was empty;
- the command, hashes, duration, output, and status were preserved.

An earlier preflight environment failed the wheel-identity check. No formula
verification was started and no status changed. That failed preflight is
preserved under `build/archive/split-tree-verifier-preflight/`.

## Consolidated candidate-screen status

Combining the 15 exact root-LP certificates with these four split-tree
certificates gives:

| Status | Count | Orbit indices |
|---|---:|---|
| `VERIFIED_UNSAT` | 19 | `0–18` |
| `TIMEOUT` | 7 | `19,20,21,22,23,24,25` |

Here `0–18` means every integer index from 0 through 18, including orbit 14.
All 18 historically discarded candidate orbits now have verified
certificates; orbit 14 is the one additional formal exclusion beyond that
historical set.

This phase does not:

- newly claim `CLASS_FORMALLY_ELIMINATED` for class 52;
- formalize the 17 whole exact-minimum-set exclusions;
- formalize the 70 base-profile or 17 proof-tuned profile exclusions;
- audit the 68-class catalog as exhaustive;
- analyze another class;
- claim `C(13,7,4)=30`.

## Principal artifacts

- `build/class52.candidate-lp-split-farkas/`
- `build/class52.candidate-lp-split-farkas-audit.json`
- `build/class52.candidate-lp-split-verification/`
- `build/class52.candidate-lp-split-verification-audit.json`
- `build/class52.candidate-screening-phase.manifest.json`
- `src/horizonlink/split_farkas.py`
- `scripts/audit_split_farkas.py`
- `tests/test_split_farkas.py`
- `proof_dependencies/`

No selected orbit or leaf disappears silently.

## Next bounded decision

The inexpensive candidate screen now leaves only orbits 19 through 25
unresolved, all of which timed out in the three-second MILP run. Before
another link class is attempted, the project still needs an audited
exhaustive source and numbering map for all 68 link representatives. For a
fully fresh end-to-end class-52 reduction, the remaining upstream
exact-minimum-set and early-profile solver exclusions also require formal
certificates or a replacement formally exhaustive reduction.

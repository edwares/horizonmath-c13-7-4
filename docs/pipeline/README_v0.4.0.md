# horizonlink

`horizonlink` is a deterministic, class-agnostic link-to-PB front end for the
HorizonMath `C(13,7,4)` program. Given one labeled 15-block `C(12,6,3)` link,
it computes:

- strict input validation and canonical hashes;
- point, pair, triple, four-set, and residual-four-set multiplicities;
- the complete automorphism group and deterministic generators;
- candidate minimum-point-set orbits;
- exact minimum-point-set orbits and extension-degree profiles;
- every screening decision without silently dropping a case;
- corrected native pseudo-Boolean formulas;
- exact root-LP Farkas proofs and verifier-normalized formulas;
- complete LP split trees with exact Farkas leaf clauses;
- formula, proof, verification-log, manifest, and corpus hashes.

The deterministic combinatorial and formula layers use only the Python
standard library. Controlled LP/MILP and Farkas-support extraction use
NumPy/SciPy. A pinned CPython 3.12 VeriPB wheel, its build definition, and its
build dependencies are preserved under `verifier/`.

## Exact class-52 regression

From the recovered provenance ledger, the generalized implementation
independently reproduces:

- automorphism-group order 36;
- all 26 orbits of the 495 four-subsets;
- 400 raw surviving exact minimum sets in 26 orbits;
- 225 raw positive excess profiles;
- exactly 107 symmetry-reduced profile orbits, compared row for row;
- the historical `70 / 17 / 20` profile partition;
- the final 20 retained profiles;
- the eleven `{1,2}` pair-multiplicity branches, with values 4 through 14;
- all 30 corrected native OPBs.

All 30 regenerated OPBs are byte-for-byte identical to the recovered native
formulas and canonically row-equivalent to the published certification
formulas.

## Independently reconstructed candidate screening

The historical `full_minpoints.py` model has also been generalized:

- all 26 candidate-orbit formulas were regenerated;
- an independent transcription/parser compared all 567 serialized rows of
  every formula in order: 26/26 passed;
- controlled root LPs found 15 infeasible and 11 feasible relaxations;
- three-second controlled MILPs ended with 19 `SOLVER_UNSAT` and 7 `TIMEOUT`;
- exact integer Farkas proofs were generated for the 15 root-LP-infeasible
  formulas;
- an independent arbitrary-precision audit passed all 15 proofs;
- exact LP split-tree/Farkas proofs were generated for root-LP-feasible
  solver-UNSAT orbits `5,6,8,14`, using 28 nodes and 16 exact leaf clauses;
- independent arithmetic/tree audits passed 16/16 leaf certificates, and all
  four proofs matched an independent byte-for-byte rebuild;
- all 19 expected formula hashes and all 19 expected proof hashes matched;
- VeriPB ran 19 times with `--requireUnsat`, exited successfully 19 times, and
  reported “Verification succeeded.” 19 times;
- independent log/hash/status audits passed 19/19.

The resulting formal candidate-orbit accounting is:

| Status | Count | Orbit indices |
|---|---:|---|
| `VERIFIED_UNSAT` | 19 | every index `0` through `18` |
| `TIMEOUT` | 7 | `19,20,21,22,23,24,25` |

Thus 19 candidate orbits may be formally pruned and seven remain in formal
accounting. This does not newly eliminate class 52 in this pipeline: the
exact-minimum-set and early-profile exclusions farther downstream still
include solver-only claims.

The fresh quick-solver partition differs from the historical exploratory
`18 / 8` partition only at orbit 14. All 18 historically discarded orbits now
have verified certificates; orbit 14 is one additional verified exclusion.
The difference is recorded, not hidden, and does not replace the historical
regression path.

See [SCREENING_PHASE_AUDIT.md](SCREENING_PHASE_AUDIT.md),
[SPLIT_FARKAS_PHASE_AUDIT.md](SPLIT_FARKAS_PHASE_AUDIT.md),
[PROVENANCE.md](PROVENANCE.md), and [RECOVERY_AUDIT.md](RECOVERY_AUDIT.md).

## Status boundary

The public 30-formula certification remains pinned at:

- [GitHub](https://github.com/edwares/class52-formal-certification)
- [Zenodo DOI](https://doi.org/10.5281/zenodo.21660461)

This checkpoint does not claim:

- that all upstream class-52 exclusions are formally certified;
- that class 52 is newly `CLASS_FORMALLY_ELIMINATED`;
- that the 68-class classification is independently exhaustive;
- that another class has been analyzed;
- that `C(13,7,4)=30`.

`SOLVER_UNSAT` is never promoted to `VERIFIED_UNSAT`.

## Principal commands

Structural/profile regression:

```bash
PYTHONPATH=src python3 -m horizonlink regress-class52 \
  data/class52.link.json \
  --golden-automorphisms \
    tests/data/golden/results_class52_automorphisms.json \
  --golden-four-orbits \
    tests/data/golden/results_class52_minpoint4_orbits.json \
  --screening-ledger data/class52.recovered-screening-ledger.json \
  --output build/class52.regression.json
```

Generate the 30 corrected formulas:

```bash
PYTHONPATH=src python3 -m horizonlink generate-formulas \
  data/class52.link.json \
  --screening-ledger data/class52.recovered-screening-ledger.json \
  --output-directory build/class52.formulas \
  --analysis-manifest build/class52.formula-analysis.manifest.json
```

Generate all candidate-orbit screens:

```bash
PYTHONPATH=src python3 -m horizonlink generate-candidate-screens \
  data/class52.link.json \
  --output-directory build/class52.candidate-screens \
  --analysis-manifest build/class52.candidate-screening-analysis.json
```

Run controlled screening only:

```bash
PYTHONPATH=src python3 -m horizonlink solve-candidate-screens \
  data/class52.link.json \
  --corpus-directory build/class52.candidate-screens \
  --output-directory build/class52.candidate-screening-solver \
  --root-lp-time-limit 3 \
  --mip-time-limit 3 \
  --historical-ledger data/class52.recovered-screening-ledger.json
```

Generate exact root-LP Farkas proofs:

```bash
PYTHONPATH=src python3 -m horizonlink generate-root-lp-farkas \
  data/class52.link.json \
  --corpus-directory build/class52.candidate-screens \
  --solver-manifest \
    build/class52.candidate-screening-solver/solver_run.manifest.json \
  --output-directory build/class52.candidate-root-lp-farkas
```

Independently audit their arithmetic and serialization:

```bash
PYTHONPATH=src python3 scripts/audit_root_lp_farkas.py \
  --candidate-corpus-directory build/class52.candidate-screens \
  --solver-manifest \
    build/class52.candidate-screening-solver/solver_run.manifest.json \
  --farkas-directory build/class52.candidate-root-lp-farkas \
  --output build/class52.candidate-root-lp-farkas-audit.json
```

Generate exact LP split-tree/Farkas proofs for selected root-LP-feasible
solver-UNSAT screens:

```bash
PYTHONPATH=src python3 -m horizonlink generate-lp-split-farkas \
  data/class52.link.json \
  --corpus-directory build/class52.candidate-screens \
  --solver-manifest \
    build/class52.candidate-screening-solver/solver_run.manifest.json \
  --output-directory build/class52.candidate-lp-split-farkas \
  --orbit 5 --orbit 6 --orbit 8 --orbit 14 \
  --reference-release Class52_formal_certification_complete.zip \
  --dependency-wheel \
    proof_dependencies/sympy-1.13.3-py3-none-any.whl \
  --dependency-wheel \
    proof_dependencies/mpmath-1.3.0-py3-none-any.whl
```

Independently audit every tree, leaf certificate, and emitted proof:

```bash
PYTHONPATH=src python3 scripts/audit_split_farkas.py \
  --candidate-directory build/class52.candidate-screens \
  --split-directory build/class52.candidate-lp-split-farkas \
  --reference-release Class52_formal_certification_complete.zip \
  --output build/class52.candidate-lp-split-farkas-audit.json
```

The VeriPB build and verification commands are documented in
[`verifier/README.md`](verifier/README.md). The immutable public release ZIP
must be supplied to the build script; it is referenced by hash but is not
duplicated inside this checkpoint.

Run the complete local regression/audit over preserved phase artifacts:

```bash
python3 -m pip install --no-index --find-links proof_dependencies \
  --require-hashes -r proof_dependencies/requirements-proof.txt
python3 scripts/run_audit.py
```

Create the deterministic release ZIP:

```bash
python3 scripts/package_release.py
```

## Determinism

- Labeled points are never relabeled.
- Blocks, subsets, automorphisms, and representatives use lexicographic order.
- Degree profiles use lexicographically ordered positive compositions and
  complete stabilizer actions.
- OPB variables are the 792 seven-subsets in lexicographic order.
- Row families and lower/upper serialization have fixed orders.
- Verifier formulas preserve row order and rewrite native `<=` rows as
  equivalent all-`>=` constraints.
- Root Farkas proofs use exact sparse rational elimination. Split-tree leaves
  use a pinned exact integer-domain nullspace engine. Both normalize to
  primitive positive integer multipliers and recompute every row exactly.
- JSON uses sorted keys, two-space indentation, and one trailing newline.
- Every corpus, proof, verifier run, and audit has SHA-256 accounting.

Solver runtimes and verification durations are observational metadata and are
not claimed to be byte-deterministic. Combinatorial outputs, formulas, exact
proofs, and their canonical hashes are deterministic.

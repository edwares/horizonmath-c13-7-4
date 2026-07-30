# HorizonMath \(C(13,7,4)\) link-class pipeline

This repository is the class-agnostic research workspace for the
HorizonMath \(C(13,7,4)\) covering-design program. It contains deterministic
code and provenance for turning a labeled minimum \(C(12,6,3)\) link into
auditable structural data, screened cases, corrected pseudo-Boolean formulas,
and—where available—formally verified UNSAT certificates.

The existing class-52 certification remains the authoritative completed
result:

- [GitHub certification repository](https://github.com/edwares/class52-formal-certification)
- [Zenodo version DOI](https://doi.org/10.5281/zenodo.21660461)

This repository does not claim that \(C(13,7,4)=30\).

## Current audited position

| Layer | Current result |
|---|---|
| Minimum \(C(12,6,3)\) link catalog | 68 project classes audited against Gordon–Patashnik–Petro–Taylor, Theorem 5.9 |
| Project numbering | Classes 1–67 are project-local Figure 1 completion classes; class 68 is Figure 6 |
| Solver-free structural census | 68/68 links validated and enumerated; complete automorphism data, candidate four-set orbit representatives, and exact unscreened profile-orbit counts preserved |
| Structural pre-ranking | 68 classes ranked in 23 structural tie groups; provisional pilot classes 68 / 4 / 59 |
| Class-52 structural regression | Group order 36, 26 four-set orbits, 107 profiles, `70 / 17 / 20`, 20 retained profiles |
| Class-52 formula regression | 30/30 regenerated native OPBs byte-identical to the recovered formulas |
| Published class-52 certificates | 30/30 `VERIFIED_UNSAT` with VeriPB `--requireUnsat` |
| Fresh candidate-orbit certificates | 19 `VERIFIED_UNSAT`; 7 `TIMEOUT` |
| Fresh downstream class-52 chain | 17 whole-case and 87 early-profile exclusions remain `SOLVER_UNSAT` only |
| Other link classes | 67 structurally `ENUMERATED`; screening, formulas, LP, solver, proof, and verification remain `NOT_STARTED` |
| Global covering number | Not proved; no claim that \(C(13,7,4)=30\) |

The published class-52 result and the current reconstructed pipeline have
different scopes. The former certifies all 30 corrected terminal formulas
under its audited reduction. The latter independently reproduces that complete
formula corpus but deliberately does not promote solver-only upstream rows to
formal verification.

See [STATUS.md](STATUS.md) for the exact claim boundary.

## What `horizonlink` computes

Given one labeled 15-block \(C(12,6,3)\) link, the deterministic front end
computes:

- strict input validation and canonical SHA-256 hashes;
- point, pair, triple, four-set, and residual-four-set multiplicities;
- the complete automorphism group and deterministic generators;
- orbits of candidate minimum-degree point sets;
- exact minimum-set orbits and extension-degree profiles;
- status-complete screening ledgers;
- corrected native OPB formulas;
- exact root-LP Farkas and LP split-tree/Farkas proofs;
- canonical manifests and artifact hashes.

No case is silently discarded, and `SOLVER_UNSAT` is never treated as
`VERIFIED_UNSAT`.

## Repository layout

| Path | Purpose |
|---|---|
| `src/horizonlink/` | Class-agnostic link analysis, profiles, PB generation, and exact proof code |
| `data/` | Audited class-52 input and recovered screening ledger |
| `schemas/` | Machine-readable labeled-link input schema |
| `tests/` | Deterministic regressions, including all class-52 targets |
| `catalog_audit/` | Complete 21,952-completion audit and explicit 68-entry numbering map |
| `provenance/classification/` | Published-theorem and exact-template provenance bridge |
| `docs/pipeline/` | Preserved phase reports for the recovered v0.4.0 pipeline |
| `results/structural-census-v0.1.0/` | Audited solver-free 68-class census, ranking, canonical inputs, and checksums |
| `ARTIFACTS.md` | Hashes and roles of the immutable checkpoint packages |
| `SOURCE_MANIFEST.json` | Deterministic SHA-256 inventory of the source checkpoint |

Generated formulas, proof corpora, solver logs, and verifier environments are
release artifacts rather than ordinary source files.

## Quick start

Core deterministic tests use the Python standard library:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

Install the exact-proof extras to run the complete test suite:

```bash
python -m pip install -e ".[proof]"
python -m unittest discover -s tests -v
```

Run the class-52 structural/profile regression:

```bash
horizonlink regress-class52 \
  data/class52.link.json \
  --golden-automorphisms \
    tests/data/golden/results_class52_automorphisms.json \
  --golden-four-orbits \
    tests/data/golden/results_class52_minpoint4_orbits.json \
  --screening-ledger data/class52.recovered-screening-ledger.json \
  --output build/class52.regression.json
```

Generate the 30 corrected class-52 formulas:

```bash
horizonlink generate-formulas \
  data/class52.link.json \
  --screening-ledger data/class52.recovered-screening-ledger.json \
  --output-directory build/class52.formulas \
  --analysis-manifest build/class52.formula-analysis.manifest.json
```

Validate the independent catalog-audit code:

```bash
PYTHONPATH=catalog_audit/src \
  python -m unittest discover -s catalog_audit/tests -v
```

Reproduce the solver-free 68-class structural census:

```bash
horizonlink structural-census \
  --numbering-manifest \
    catalog_audit/build/authoritative/numbering.manifest.json \
  --classification-audit \
    provenance/classification/audit/classification-provenance.audit.json \
  --output-directory build/structural-census
```

Compare the regenerated checkpoint byte for byte:

```bash
diff -qr \
  results/structural-census-v0.1.0 \
  build/structural-census
```

Verify that the checked-in source tree matches its integrity manifest:

```bash
python scripts/build_source_manifest.py --check
```

The solver-free structural gate is complete. The next bounded stage is to
materialize and audit exact profile representatives and mathematical screening
for the provisional three-class pilot—class 68, class 4, and class 59—before
any LP or solver run is authorized. The present ranking is a structural
pre-ranking, not a measured solver- or proof-difficulty result.

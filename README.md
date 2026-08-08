# HorizonMath \(C(13,7,4)\) link-class pipeline

This repository is the class-agnostic research workspace for the
HorizonMath \(C(13,7,4)\) covering-design program. It contains deterministic
code and provenance for turning a labeled minimum \(C(12,6,3)\) link into
auditable structural data, screened cases, corrected pseudo-Boolean formulas,
and—where available—formally verified UNSAT certificates.

Five link classes are now formally eliminated:

- class 48: [formal certification status](results/class48-formal-certification-v0.1.0/STATUS.md)
  and [class-level closure manifest](results/class48-formal-certification-v0.1.0/class48-formal-closure.json);
- class 50: [formal certification status](results/class50-formal-certification-v0.1.0/STATUS.md)
  and [class-level closure manifest](results/class50-formal-certification-v0.1.0/class50-formal-closure.json);
- class 52: [published certification repository](https://github.com/edwares/class52-formal-certification)
  and [Zenodo DOI](https://doi.org/10.5281/zenodo.21660461);
- class 63: [formal certification status](results/class63-formal-certification-v0.1.0/STATUS.md)
  and [class-level closure manifest](results/class63-formal-certification-v0.1.0/class63-formal-closure.json);
- class 68: [formal certification status](results/class68-formal-certification-v0.1.0/STATUS.md)
  and [class-level closure manifest](results/class68-formal-certification-v0.1.0/class68-formal-closure.json).

This repository does not claim that \(C(13,7,4)=30\).

## Current audited position

| Layer | Current result |
|---|---|
| Minimum \(C(12,6,3)\) link catalog | 68 project classes audited against Gordon–Patashnik–Petro–Taylor, Theorem 5.9 |
| Project numbering | Classes 1–67 are project-local Figure 1 completion classes; class 68 is Figure 6 |
| Solver-free structural census | 68/68 links validated and enumerated; complete automorphism data, candidate four-set orbit representatives, and exact unscreened profile-orbit counts preserved |
| Structural pre-ranking | 68 classes ranked in 23 structural tie groups; provisional pilot classes 68 / 4 / 59 |
| Solver-free pilot screening | 115,955 profile orbits materialized across classes 68 / 4 / 59; 136 direct arithmetic contradictions discarded; 115,819 retained |
| Class-48 formal closure | 35/35 candidate orbits formally covered; 675/675 retained degree profiles VeriPB `VERIFIED_UNSAT`; class-level status `VERIFIED_UNSAT_CLASS_48` |
| Class-50 formal closure | 35/35 candidate orbits formally covered; 1508/1508 retained degree profiles VeriPB `VERIFIED_UNSAT`; class-level status `VERIFIED_UNSAT_CLASS_50` |
| Class-63 formal closure | 58/58 candidate orbits formally covered; 460/460 retained degree profiles VeriPB `VERIFIED_UNSAT`; class-level status `VERIFIED_UNSAT_CLASS_63` |
| Class-68 candidate formulas | 12/12 native OPBs generated; all 6,816 serialized rows independently reconstructed and matched |
| Class-68 direct containment | 33,780 lower/upper row pairs scanned; 14,284 support containments; zero strict contradictions; all 12 formulas survive |
| Class-68 exact root LP | 6 exact rational LP witnesses; 6 exact integer Farkas contradictions; independent exact audit passed 12/12 |
| Class-68 root-LP verification | Farkas orbits 1 / 3 / 6 / 7 / 8 / 11 are `VERIFIED_UNSAT` with VeriPB `--requireUnsat`; 6/6 verification records independently audited |
| Class-68 formal closure | 12/12 candidate orbits formally covered; class-level status `VERIFIED_UNSAT_CLASS_68` |
| Class-68 orbit 2 | Exhaustive 155/155 profile-orbit closure; all profiles VeriPB `VERIFIED_UNSAT` |
| Class-68 final shared residual | 13 exact pair CG cuts + 203-node / 102-leaf exact Farkas split tree; stitched proof VeriPB `VERIFIED_UNSAT` |
| Class-52 structural regression | Group order 36, 26 four-set orbits, 107 profiles, `70 / 17 / 20`, 20 retained profiles |
| Class-52 formula regression | 30/30 regenerated native OPBs byte-identical to the recovered formulas |
| Published class-52 certificates | 30/30 `VERIFIED_UNSAT` with VeriPB `--requireUnsat` |
| Fresh candidate-orbit certificates | 19 `VERIFIED_UNSAT`; 7 `TIMEOUT` |
| Fresh downstream class-52 chain | 17 whole-case and 87 early-profile exclusions remain `SOLVER_UNSAT` only |
| Formally eliminated link classes | 5/68: classes 48, 50, 52, 63, and 68 |
| Remaining link classes | 63 require formal elimination or a stronger collective argument |
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
- exhaustive direct support-containment scans and short cutting-planes proofs
  when a witness exists;
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
| `results/pilot-screening-v0.1.0/` | Every exact-set and profile-orbit representative for pilot classes 68 / 4 / 59, with solver-free screening decisions |
| `results/class68-candidate-formulas-v0.1.0/` | All 12 class-68 candidate-orbit OPBs, independent ordered-row audit, manifests, and checksums |
| `results/class68-direct-containment-v0.1.0/` | Exhaustive direct-containment results for all 12 class-68 formulas, independent audit, manifests, and checksums |
| `results/class68-root-lp-v0.1.0/` | Immutable verifier-bound root-LP checkpoint used by the preserved v0.1 verification records |
| `results/class68-root-lp-v0.2.0/` | Byte-stable regeneration fingerprint; CI regenerates the full output and requires its SHA-256 inventory plus exact evidence and OPB/PBP proof bytes to match the recorded baseline/v0.1 evidence |
| `results/class68-root-lp-verification-v0.1.0/` | Preserved VeriPB `--requireUnsat` results and independent verification audit for the six root-LP contradictions |
| `results/class48-formal-certification-v0.1.0/` | Checked-in class-48 closure/status records proving exact coverage of all 35 candidate orbits |
| `results/class50-formal-certification-v0.1.0/` | Checked-in class-50 closure/status records proving exact coverage of all 35 candidate orbits |
| `results/class63-formal-certification-v0.1.0/` | Checked-in class-63 closure/status records proving exact coverage of all 58 candidate orbits |
| `results/class68-formal-certification-v0.1.0/` | Checked-in class-68 closure/status records proving exact coverage of all 12 candidate orbits |
| `docs/CLASS48_FORMAL_CERTIFICATION_V0.1.0.md` | Formal class-48 result, proof routes, verifier gate, hashes, and claim boundary |
| `docs/CLASS50_FORMAL_CERTIFICATION_V0.1.0.md` | Formal class-50 result, proof routes, verifier gate, hashes, and claim boundary |
| `docs/CLASS63_FORMAL_CERTIFICATION_V0.1.0.md` | Formal class-63 result, proof routes, verifier gate, hashes, and claim boundary |
| `docs/CLASS68_FORMAL_CERTIFICATION_V0.1.0.md` | Formal class-68 result, proof routes, verifier gate, hashes, and claim boundary |
| `ARTIFACTS.md` | Hashes and roles of the immutable checkpoint packages |
| `SOURCE_MANIFEST.json` | Deterministic SHA-256 inventory of the source checkpoint |

The bounded class-68 candidate, direct-containment, root-LP, and root-LP
verification checkpoints are checked in for exact regression. The pinned
VeriPB build environment itself remains provenance input rather than ordinary
source.

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

Reproduce the solver-free pilot profile screening:

```bash
horizonlink screen-profiles \
  --structural-census-directory \
    results/structural-census-v0.1.0 \
  --class-index 68 \
  --class-index 4 \
  --class-index 59 \
  --output-directory build/pilot-screening

diff -qr \
  results/pilot-screening-v0.1.0 \
  build/pilot-screening
```

Reproduce the class-68 candidate formula checkpoint:

```bash
horizonlink generate-candidate-checkpoint \
  --structural-census-directory \
    results/structural-census-v0.1.0 \
  --profile-screening-directory \
    results/pilot-screening-v0.1.0 \
  --class-index 68 \
  --output-directory build/class68-candidate-formulas

diff -qr \
  results/class68-candidate-formulas-v0.1.0 \
  build/class68-candidate-formulas
```

Reproduce the class-68 direct-containment checkpoint:

```bash
horizonlink scan-direct-containment \
  --candidate-checkpoint-directory \
    results/class68-candidate-formulas-v0.1.0 \
  --output-directory build/class68-direct-containment

diff -qr \
  results/class68-direct-containment-v0.1.0 \
  build/class68-direct-containment
```

Reproduce the byte-stable class-68 root-LP checkpoint:

```bash
horizonlink scan-root-lp \
  --candidate-checkpoint-directory \
    results/class68-candidate-formulas-v0.1.0 \
  --direct-containment-directory \
    results/class68-direct-containment-v0.1.0 \
  --output-directory build/class68-root-lp

diff -u \
  results/class68-root-lp-v0.2.0/SHA256SUMS \
  build/class68-root-lp/SHA256SUMS
```

The preserved v0.1 checkpoint remains the input bound into the original
VeriPB verification records. The compact v0.2 fingerprint avoids duplicating
that corpus in source control. v0.2 changes only reproducibility metadata for
the six Farkas cases: the raw floating HiGHS objective margin is no longer
serialized. The regression suite requires its exact rational witnesses, exact
integer Farkas certificates, verifier-normalized OPBs, and PBP proof bytes to
match v0.1.

Verification of the six exact Farkas proofs is a separate, fail-closed gate.
Given the pinned VeriPB 0.3a0 wheel and its preserved build-provenance JSON:

```bash
horizonlink verify-root-lp \
  --root-lp-directory results/class68-root-lp-v0.1.0 \
  --verifier /path/to/venv/bin/veripb \
  --verifier-python /path/to/venv/bin/python \
  --verifier-wheel /path/to/veripb-0.3a0-cp312-cp312-linux_x86_64.whl \
  --verifier-build-provenance /path/to/build.provenance.json \
  --output-directory build/class68-root-lp-verification
```

Verify that the checked-in source tree matches its integrity manifest:

```bash
python scripts/build_source_manifest.py --check
```

Class 68 has advanced beyond the historical direct-containment checkpoint and
is now formally eliminated: all 12 candidate orbits are covered by exact
proofs accepted by VeriPB with `--requireUnsat`, and the class-level closure
audit passes. Together with the class-48, class-50, and class-63
certifications and the separately published class-52 elimination, 5 of the 68
link classes are formally closed. The next research stage is to
apply the audited structural ranking and reusable exact-proof machinery to the
remaining 63 classes. The global \(C(13,7,4)=30\) claim remains unauthorized
until the full reduction is closed.

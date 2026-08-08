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
| Solver-free pilot screening | 115,955 profile orbits materialized across classes 68 / 4 / 59; 136 direct arithmetic contradictions discarded; 115,819 retained |
| Refined pilot order | Class 68 / class 4 / class 59; no LP or solver metrics used |
| Class-68 candidate formulas | 12/12 native OPBs generated; all 6,816 serialized rows independently reconstructed and matched |
| Class-68 direct containment | 33,780 lower/upper row pairs scanned; 14,284 support containments; zero strict contradictions; all 12 formulas survive |
| Class-68 exact root LP | 6 exact rational LP witnesses; 6 exact integer Farkas contradictions; independent exact audit passed 12/12 |
| Class-68 root-LP verification | Farkas orbits 1 / 3 / 6 / 7 / 8 / 11 are `VERIFIED_UNSAT` with VeriPB `--requireUnsat`; 6/6 verification records independently audited |
| Class-52 structural regression | Group order 36, 26 four-set orbits, 107 profiles, `70 / 17 / 20`, 20 retained profiles |
| Class-52 formula regression | 30/30 regenerated native OPBs byte-identical to the recovered formulas |
| Published class-52 certificates | 30/30 `VERIFIED_UNSAT` with VeriPB `--requireUnsat` |
| Fresh candidate-orbit certificates | 19 `VERIFIED_UNSAT`; 7 `TIMEOUT` |
| Fresh downstream class-52 chain | 17 whole-case and 87 early-profile exclusions remain `SOLVER_UNSAT` only |
| Other link classes | Class 68 has six formally pruned root-LP orbits and six exact-LP survivors; classes 4 and 59 remain at solver-free screening depth |
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
| `results/class68-root-lp-v0.1.0/` | Exact root-LP evidence for all 12 class-68 formulas, including six rational witnesses and six exact Farkas proof packages |
| `results/class68-root-lp-verification-v0.1.0/` | Preserved VeriPB `--requireUnsat` results and independent verification audit for the six root-LP contradictions |
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

Reproduce the exact class-68 root-LP checkpoint:

```bash
horizonlink scan-root-lp \
  --candidate-checkpoint-directory \
    results/class68-candidate-formulas-v0.1.0 \
  --direct-containment-directory \
    results/class68-direct-containment-v0.1.0 \
  --output-directory build/class68-root-lp

diff -qr \
  results/class68-root-lp-v0.1.0 \
  build/class68-root-lp
```

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

The class-68 root-LP gate is complete. Six formulas have independently audited
exact rational LP witnesses. The other six have exact integer Farkas
contradictions and VeriPB-accepted proofs, so only orbits 1, 3, 6, 7, 8, and
11 are formally pruned at this stage. Orbits 0, 2, 4, 5, 9, and 10 survive the
root LP; that does not make them Boolean SAT instances. Class 68 is therefore
not eliminated. The next bounded research stage is a separately controlled
exact LP split-tree/Farkas attempt on those six survivors. No MILP,
RoundingSat, class-4, or class-59 campaign is authorized.

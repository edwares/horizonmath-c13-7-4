# HorizonMath link-catalog audit

Source-tree note: the immutable SAT source bundle and the 4.4 MB completion
ledger remain in the hashed release package listed in `../ARTIFACTS.md`.
The extracted catalog input, audit implementation, numbering map, and other
authoritative manifests are included here. The complete enumeration can be
rerun directly from `data/catalog-input.json`.

This package audits the recovered upstream numbering source for the 68
minimum `C(12,6,3)` link representatives used by the HorizonMath
`C(13,7,4)` program.

The audit has a deliberately narrow scope:

1. extract the two archived templates and the historical catalog without
   executing the archived source;
2. enumerate every completion of the archived first template, with no early
   stop;
3. validate every resulting 15-block `C(12,6,3)` cover;
4. classify the completions by exact hypergraph isomorphism;
5. compare the complete result with the 67 archived first-template
   representatives and the separate `fig6` representative;
6. emit an explicit 1-through-68 numbering manifest and a row for every
   enumerated completion;
7. independently audit the emitted partition.

Passing this audit establishes catalog consistency **conditional on the
archived template specification**. It does not prove that the two templates
exhaust all minimum `C(12,6,3)` covers, because the recovered bundle contains
neither a derivation of that theorem nor an authoritative classification
citation.

The new classifier uses only the Python standard library. Exact isomorphism is
checked by deterministic point-map backtracking that preserves every subset
containment multiplicity through size six; no hash or color-refinement result
is accepted as an isomorphism proof.

## Reproduction

The release contains the exact immutable SAT bundle used as the recovered
source. From the release root:

```sh
mkdir -p work/source
unzip -q source_archives/HorizonMath_C13_7_4_sat_bundle.zip -d work/source

PYTHONPATH=src python3 -m unittest discover -s tests -v

PYTHONPATH=src python3 scripts/extract_catalog_input.py \
  --bundle-root work/source/HorizonMath_C13_7_4_sat_bundle \
  --output work/catalog-input.json

PYTHONPATH=src python3 scripts/run_catalog_audit.py \
  --input work/catalog-input.json \
  --output-dir work/run

PYTHONPATH=src python3 scripts/verify_catalog_audit.py \
  --input work/catalog-input.json \
  --run-dir work/run \
  --output work/run/catalog.independent-audit.json

PYTHONPATH=src python3 scripts/audit_bundle_numbering.py \
  --bundle-root work/source/HorizonMath_C13_7_4_sat_bundle \
  --numbering-manifest work/run/numbering.manifest.json \
  --output work/run/bundle-numbering.audit.json
```

The complete classifier and independent verifier are intentionally not
parallelized. On the audited environment the production pass takes roughly two
minutes and the independent pass roughly eight minutes. Runtime is not part of
any signed manifest.

Check the release itself with:

```sh
sha256sum -c SHA256SUMS
```

The authoritative precomputed outputs are in `build/authoritative/`.

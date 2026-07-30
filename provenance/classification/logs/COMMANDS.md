# Audited commands

Audit date: 2026-07-29 UTC

## Extract and compare paper templates

```bash
python literature_audit/scripts/extract_paper_templates.py \
  --pdf literature_audit/sources/c-12-6-3.pdf \
  --source numbering_audit/source_bundle/HorizonMath_C13_7_4_sat_bundle/source/link_extension.py \
  --output-dir literature_audit/audit
```

Observed result:

```text
overall_status=PASS
figure1 block sizes=6,6,6,6,6,6,6,6,6,6,6,6,4,4,4
figure6 block sizes=6,6,6,6,6,6,6,6,6,6,6,6,6,6,6
```

## Build the classification bridge

```bash
python literature_audit/scripts/build_classification_provenance.py \
  --pdf literature_audit/sources/c-12-6-3.pdf \
  --paper-templates literature_audit/audit/paper.templates.json \
  --template-comparison literature_audit/audit/paper-template-comparison.audit.json \
  --catalog-input numbering_audit/audit_project/data/catalog-input.json \
  --catalog-audit numbering_audit/audit_project/build/run2/catalog.audit.manifest.json \
  --independent-audit numbering_audit/audit_project/build/run2/catalog.independent-audit.json \
  --numbering-manifest numbering_audit/audit_project/build/run2/numbering.manifest.json \
  --bundle-numbering-audit numbering_audit/audit_project/build/run2/bundle-numbering.audit.json \
  --output-dir literature_audit/audit
```

Observed result:

```text
checks_passed=18
checks_total=18
overall_status=PASS
```

## Status boundary

No command in this phase generated a PB formula, invoked an LP/MILP solver,
generated a proof, or invoked VeriPB.

# HorizonMath classification-source audit

This checkpoint closes the literature and template provenance boundary for
the recovered 68-entry minimum `C(12,6,3)` link catalog.

The main results are:

- the authoritative primary paper and its journal metadata are identified;
- its Figures 1 and 6 are extracted geometrically from the PDF;
- all 30 published template rows match the recovered source exactly;
- Theorem 5.9 is anchored as the two-template exhaustiveness theorem;
- the complete 21,952-completion audit supplies an independent replacement
  for the paper’s reported 67-class computation;
- every project class is mapped to its published template family;
- the absence of individual literature class numbers is recorded explicitly.

See:

- `CLASSIFICATION_PROVENANCE_AUDIT.md` for the human audit;
- `audit/classification-provenance.audit.json` for the 18-check bridge;
- `audit/paper-template-comparison.audit.json` for row-level comparisons;
- `audit/literature-to-project-class-map.json` for all 68 project entries;
- `audit/source-search.audit.json` for the bounded source search;
- `REPRODUCE.md` for exact reproduction commands.

The primary PDF is referenced by URL and SHA-256 but is not redistributed in
the release ZIP.

This checkpoint performs no new link-profile analysis, solver run, proof
generation, or class elimination.

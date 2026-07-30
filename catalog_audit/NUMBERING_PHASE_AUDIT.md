# HorizonMath recovered link-catalog and numbering audit

## Outcome

The recovered first-template completion space has now been enumerated without
the archived early stop.

- Completion space: `28^3 = 21,952`
- Completion rows emitted: `21,952`
- Valid 15-block `C(12,6,3)` covers: `21,952`
- Invalid completions: `0`
- First-template isomorphism classes: `67`
- Classes first seen after archived completion 2,681: `0`
- Separate `fig6` representative isomorphic to a first-template class: `no`
- Explicit project numbering entries: `68`

All ten primary catalog checks pass. The archived first 2,681 rows reproduce
the historical 67 representatives, their order, their labels, their examples,
and their prefix multiplicities exactly. Continuing through row 21,952 finds
no additional first-template class. Full multiplicities sum to 21,952 and are
recorded in `build/authoritative/catalog.audit.manifest.json`.

Class 52 is exactly `metadata/link_classes.json: representatives[51]`. Its
canonical labeled-link hash, using the same `{points, blocks}` serialization
as horizonlink v0.4.0, is:

`034d4c7cd44947c6fe2e8d562850611670af399f5d850b2c141990152a6af571`

## Independent audit

The independent verifier does not import the production classifier's
isomorphism routine. It:

1. reconstructs all 21,952 links from the extracted template;
2. validates every triple-cover condition;
3. recomputes every canonical labeled-link hash;
4. tests every row against independently bucketed representatives;
5. requires exactly one exact isomorphism match;
6. checks all 68 numbered representatives pairwise.

It reports:

- audited completion rows: `21,952`
- invalid completions: `0`
- ambiguous assignments: `0`
- wrong assignments: `0`
- completion-hash mismatches: `0`
- pairwise numbered-representative collisions: `0`
- status: `PASS`

The exact method is a separately written point-map backtracker. At each node it
preserves point fingerprints, pair and triple multiplicities, and the full
restricted block-incidence pattern; at leaves it requires equality of the
mapped block set.

## Numbering-to-bundle audit

Every numbered representative was compared with its archived class metadata
and CNF:

- classes checked: `68`
- classes passed: `68`
- immutable bundle hashes checked: `148/148`
- residual coverage clauses checked: `18,892`
- metadata/residual/CNF/manifest mismatches: `0`

This check does not solve the CNFs and makes no satisfiability or elimination
claim.

## Determinism

Two complete invocations produced byte-identical copies of:

- `catalog.audit.manifest.json`
- `completion-ledger.jsonl`
- `numbering.manifest.json`

The authoritative hashes are:

| Artifact | SHA-256 |
|---|---|
| catalog input | `6b91c12518cb72444a0341e88d8157766b07832da5bd0c7ce39a0973c5dd53ab` |
| catalog audit manifest | `087cb62e9bb6b1b6d18d0df6b928ed59c60aa613459ebf1e6062a520e412ebeb` |
| completion ledger | `f085043dd3c460857f24c3adbe976b2720fe4b7ab1c00f8ebf94e420b61ddcf7` |
| numbering manifest | `2a650187b10f18a6c1526f591363eafddc5eca576313371404e665d97593c17c` |
| independent audit | `3c010126ae92f44edd0403acab51ef8af6f02b1ae21bc41945fb7bc42a7d011c` |
| bundle-numbering audit | `774da7c6ff807c37029aa3e580894ebd7bf74c8494eeeae58c89b2db93262dcf` |
| determinism audit | `9e3e3bf1597b96a776132ccf83b6042d7e6cca151602e748124c191519e9de4c` |

## What this closes

This phase closes the archived classifier's early-stop defect as an internal
project-catalog question:

- the first template has exactly the same 67 classes after all 21,952
  completions;
- `fig6` is distinct from all of them;
- the recovered project convention is now explicitly mapped as classes 1–67
  followed by `fig6` as class 68;
- the downstream metadata and CNF numbering uses that map exactly.

The project numbering map can therefore be treated as audited **conditional on
the recovered two-template specification**.

## What remains missing

This phase does **not** prove that the two recovered templates exhaust all
minimum `C(12,6,3)` covers. The immutable bundle contains no derivation or
authoritative citation for that classification theorem and no independently
audited literature-to-project numbering correspondence. The original
NetworkX version is also unrecorded, although the new complete audit avoids
that dependency entirely.

Accordingly:

- the mathematical exhaustiveness status of the 68-class catalog remains
  `NOT_AUDITED`;
- no other link class was enumerated through the HorizonMath profile/formula
  pipeline;
- no solver or proof-generation run was launched;
- no additional class is claimed eliminated;
- no claim about `C(13,7,4)=30` is authorized.

## Next bounded task

Audit the classification theorem itself: identify the authoritative source for
the two templates, recover or reconstruct its derivation, and build a
literature-to-project representative map. Only after that provenance boundary
is closed should the inexpensive front-end enumeration and screening stages be
run across classes 1–51 and 53–68.


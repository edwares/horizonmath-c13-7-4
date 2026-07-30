# Solver-free all-68 structural census v0.1.0

Status date: 2026-07-30 UTC

## Result

The `horizonlink` v0.5.0 front end processed all 68 audited minimum
\(C(12,6,3)\) link representatives. The run performed structural enumeration
only. It did not generate formulas and did not run an LP solver, PB solver,
proof generator, or verifier.

The checkpoint is in
[`results/structural-census-v0.1.0/`](../results/structural-census-v0.1.0/).
Its `SHA256SUMS` file covers every other file in the directory.

| Artifact | SHA-256 |
|---|---|
| `census.manifest.json` | `6954eefecdad34d27abc4715a2b1934a18e33dae7f306e34e28e4d651cd2b18f` |
| `ranking.json` | `27a0269c4656a188f56db40aeb25f23d04c0fb9357d32851219f37e7c47dd886` |
| `ranking.csv` | `7022c39e38dddac3f286313202a3646381715cef0633c9f1e65a36c33747ad82` |
| Class-52 census record | `5bc45b56f902c5b2f5a55f0499f9ca622c8377b6cd8cf5501d036612a2839a22` |

## Audited inputs and numbering

The run fails closed unless both input audits pass and agree on their hashes:

| Input | SHA-256 |
|---|---|
| `catalog_audit/build/authoritative/numbering.manifest.json` | `2a650187b10f18a6c1526f591363eafddc5eca576313371404e665d97593c17c` |
| `provenance/classification/audit/classification-provenance.audit.json` | `4158592d9737bb3fb1f91b65f0b9379e763b56054e1b26b5b65838af1f6476b2` |
| Catalog input, as cited by both audits | `6b91c12518cb72444a0341e88d8157766b07832da5bd0c7ce39a0973c5dd53ab` |

The classification audit connects the explicit project-local numbering map to
the exhaustive classification in Gordon, Patashnik, Petro, and Taylor,
*Minimum (12, 6, 3) Covers*, Theorem 5.9 and remarks. The published theorem is
human mathematics; it has not been machine-formalized in this project.

## Deterministic per-class stages

For each class, in ascending project class index, the pipeline:

1. extracts the labeled block list from the audited numbering manifest without
   relabeling;
2. writes the canonical `horizonmath.link-input.v1` document;
3. validates 12 points, 15 distinct blocks of size 6, and complete triple
   coverage;
4. computes point, pair, triple, four-set, and residual-four-set
   multiplicities;
5. enumerates the complete labeled automorphism group and selects deterministic
   generators;
6. partitions all 495 four-subsets into automorphism orbits and records every
   orbit representative;
7. derives the extension degree-excess budget;
8. uses Burnside's lemma over the complete automorphism group to count all
   weak nonnegative degree-excess profiles exactly, by exact minimum-set size.

The Burnside stage counts profile orbits without materializing their
representatives. It is therefore inexpensive even for classes with a trivial
automorphism group.

## Census summary

| Metric | Result |
|---|---:|
| Classes expected / enumerated | 68 / 68 |
| Generated files | 140 |
| Per-class census records | 68 |
| Canonical labeled-link inputs | 68 |
| Structural tie groups | 23 |
| Automorphism-group order range | 1–240 |
| Candidate four-set orbit-count range | 12–495 |
| Residual four-set-count range | 276–285 |
| Unscreened profile-orbit-count range | 755–75,582 |

The automorphism-group order histogram is:

| Group order | Classes |
|---:|---:|
| 1 | 21 |
| 2 | 28 |
| 4 | 8 |
| 6 | 4 |
| 8 | 2 |
| 12 | 1 |
| 24 | 2 |
| 36 | 1 |
| 240 | 1 |

## Ranking method and pilot

The structural pre-ranking orders classes lexicographically by:

1. unscreened degree-profile orbit count, ascending;
2. candidate minimum-point four-set orbit count, ascending;
3. residual four-set count, ascending;
4. automorphism-group order, descending.

Class index is used only to make output within a structural tie group
deterministic. It is not a difficulty metric.

| Pilot role | Class | Structural position | Tie span |
|---|---:|---:|---:|
| Easy / high symmetry | 68 | 1 | 1 |
| Median | 4 | 33 | 33–38 |
| Difficult / low symmetry | 59 | 66 | 66–68 |

This pilot selection is provisional. Retained-profile counts, root-LP
feasibility, quick solver runtime, and estimated proof size remain
`NOT_STARTED`; those unavailable metrics did not influence the ranking.

## Class-52 regression boundary

The solver-free census independently obtains:

| Class-52 metric | Result |
|---|---:|
| Canonical labeled-link SHA-256 | `034d4c7cd44947c6fe2e8d562850611670af399f5d850b2c141990152a6af571` |
| Automorphism-group order | 36 |
| Four-subsets / orbit count | 495 / 26 |
| Residual four-sets | 279 |
| Unscreened degree-profile orbits | 2,578 |

The 2,578 profile-orbit count is before candidate and case screening. The
historical class-52 count of 107 is after those screens. This census does not
claim to regenerate 107, the `70 / 17 / 20` partition, or the 30 formulas;
those are covered by the separate full class-52 regression.

## Reproduction and audit

```bash
python -m pip install -e .

horizonlink structural-census \
  --numbering-manifest \
    catalog_audit/build/authoritative/numbering.manifest.json \
  --classification-audit \
    provenance/classification/audit/classification-provenance.audit.json \
  --output-directory build/structural-census

sha256sum -c results/structural-census-v0.1.0/SHA256SUMS
diff -qr results/structural-census-v0.1.0 build/structural-census
```

The regression suite also performs an independent second generation and
requires byte-for-byte equality.

## Claim boundary

This phase establishes a deterministic, audited structural census and
pre-ranking. It eliminates no additional link class. It does not reverify the
published class-52 proofs, and it does not establish
\(C(13,7,4)=30\).

# HorizonMath minimum-cover classification provenance audit

Audit date: 2026-07-29 UTC

## Outcome

The recovered 68-entry project catalog is now tied to an authoritative
classification theorem and to the exact published templates.

| Check | Result |
|---|---:|
| Primary-source text anchors | 6/6 pass |
| Machine checks in the provenance bridge | 18/18 pass |
| Published Figure 1 fixed rows vs. recovered `FIG1_FULL` | 12/12 exact |
| Published Figure 1 short rows vs. recovered `FILES` | 3/3 exact |
| Published Figure 6 rows vs. recovered `FIG6` | 15/15 exact |
| First-template completions enumerated | 21,952/21,952 |
| First-template isomorphism classes | 67 |
| Separate Figure 6 class | 1 |
| Project numbering entries mapped to a published family | 68/68 |

The correct status is:

- global 68-class exhaustiveness:
  `AUDITED_AGAINST_PUBLISHED_THEOREM`;
- exact identity of the recovered and published templates: `AUDITED`;
- the reported 67-class computational count:
  `INDEPENDENTLY_RECOMPUTED_AND_AUDITED`;
- formal machine verification of the published classification proof:
  `NOT_PERFORMED`.

No other link class was passed through the profile/formula pipeline, and no
solver or proof-generation run was launched in this phase.

## Authoritative source

The source is the paper by Daniel M. Gordon, Oren Patashnik, John Petro, and
Herbert Taylor whose printed title is *Minimum (12, 6, 3) Covers*.

- Author-hosted paper:
  <https://www.dmgordon.org/papers/c-12-6-3.pdf>
- Author publication index:
  <https://www.dmgordon.org/publications/>
- Bibliographic entry on the author page:
  *C(12,6,3)=15*, Ars Combinatorica 40 (1995), 161–177
- Audited PDF SHA-256:
  `6da3d15935e5eb8eca9e533c60ffb08db48cb335a94f88c007bd449729f8cf79`

The differing printed title and author-page link text are recorded explicitly;
the link points to the audited PDF.

## Published derivation

The source supplies a human mathematical proof, not merely a database count.
The audit locates and hashes the following proof chain:

1. Lemma 2.1 establishes the Figure 1 element-minimal covering family.
2. Lemma 5.7 sends the case with no duplicate 777-triple to a completion of
   Figure 1.
3. Lemma 5.8 sends the duplicate-777 case to a completion of Figure 1 or to
   Figure 6.
4. Theorem 5.9 concludes that every minimum cover belongs to one of those two
   families and not both.
5. The following remarks report that Figure 1 has 67 nonisomorphic
   completions, hence 68 minimum-cover isomorphism classes in total.

The text-anchor audit confirms those sections in the hashed PDF. It does not
translate their human combinatorial arguments into a formal proof language.

## Exact template comparison

`scripts/extract_paper_templates.py` uses PDF geometry rather than a manual
block transcription. On the two figure pages it:

1. identifies the twelve column headers `0` through `9`, `T`, and `E`;
2. identifies row labels 1 through 15;
3. assigns every bullet glyph to its nearest labeled row and column within
   explicit tolerances;
4. emits the blocks in published row order; and
5. compares them with literal assignments parsed from the recovered
   `link_extension.py`.

All three comparisons are exact, including row and element order:

| Comparison | Status | Canonical block-list SHA-256 |
|---|---:|---|
| Figure 1 rows 1–12 vs. `FIG1_FULL` | PASS | `6ec18b13dc9db19ac83155b06cffedad31bb676f0d9522954200a0e77f4f6ff9` |
| Figure 1 rows 13–15 vs. `FILES` | PASS | `d6336cc810c563eb5c15ded3bcf48e3ed6f0c474c4468db176fd2f27298626d0` |
| Figure 6 rows 1–15 vs. `FIG6` | PASS | `eb882237452fab21a4afb5b1d7bc1794601d2830f354164e7dfeea8c899fa7c7` |

Figure 1 contains twelve 6-sets and three 4-set files. By the paper’s
definition, completing each file means adding any two of its eight
complementary points. The recovered domains are exactly those three
lexicographic 2-subset domains, so the full labeled completion space is
`28^3 = 21,952`.

## Bridge to the project catalog

The earlier no-early-stop phase independently established:

- all 21,952 Figure 1 completions are valid 15-block `C(12,6,3)` covers;
- they occupy exactly 67 isomorphism classes;
- Figure 6 is not isomorphic to any of those 67 classes;
- the project numbering contains exactly 68 pairwise nonisomorphic
  representatives;
- classes 1–67 are the ordered Figure 1 classes;
- class 68 is Figure 6;
- all 68 metadata/CNF entries use that numbering exactly.

Combining those checked computations with Theorem 5.9 closes the earlier
classification-source boundary. The resulting map is explicit in
`audit/literature-to-project-class-map.json`.

Class 52 remains:

- project source:
  `metadata/link_classes.json: representatives[51]`;
- published family: Figure 1 completion;
- canonical labeled-link SHA-256:
  `034d4c7cd44947c6fe2e8d562850611670af399f5d850b2c141990152a6af571`.

## Numbering semantics

The paper does not publish individual identifiers, representatives, or a
1-through-67 ordering for its Figure 1 isomorphism classes. Consequently:

| Mapping layer | Status |
|---|---|
| Published family: Figure 1 completion or Figure 6 | Audited for all 68 project classes |
| Project-local indices 1–68 | Audited |
| Individual literature indices 1–67 | Not present in the primary source |

This is not an unresolved ambiguity in the project numbering. It means only
that the numbers are project-local and must not be presented as numbering
assigned by Gordon–Patashnik–Petro–Taylor.

The defined source search also found no public per-class representative list
or original 1994 enumeration program. That negative result is recorded as
`NOT_LOCATED_IN_DEFINED_SEARCH`, not as a claim that such material never
existed.

## Remaining provenance and proof gaps

This phase closes the missing classification citation/template derivation and
the global catalog-exhaustiveness boundary. It does not close other known
gaps:

- the published Theorem 5.9 proof is not formally machine verified;
- the original 1994 code used for the paper’s 67-class count was not located;
- the original class-52 `full_minpoints` result files and historical hashes
  remain unavailable, although fresh formal proofs replace the mathematical
  evidence for the historically discarded candidate orbits;
- the 17 whole exact-minimum-set exclusions and 87 early-profile exclusions
  in the recovered class-52 chain remain solver-only;
- this fresh pipeline therefore does not newly assign class 52 the status
  `CLASS_FORMALLY_ELIMINATED`;
- no claim that `C(13,7,4)=30` is authorized.

## Next bounded implementation task

Add the audited 68-entry numbering manifest as a first-class input to
`horizonlink`, then run only a no-solver catalog census:

- validate every representative and hash;
- recompute multiplicities, automorphism groups, residual four-set counts,
  and candidate minimum-point orbit counts;
- emit one status-complete manifest for all 68 classes;
- compare class 52 with its existing regression as a control;
- do not generate formulas or launch LP/MILP work in that census.

That census will supply the inexpensive structural features needed to choose
the easy/median/difficult three-class pilot without prematurely analyzing all
67 unresolved classes at solver depth.

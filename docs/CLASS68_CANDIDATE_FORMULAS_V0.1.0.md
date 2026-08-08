# Class-68 candidate formulas v0.1.0

> Historical phase checkpoint. Class 68 was subsequently formally eliminated;
> see [CLASS68_FORMAL_CERTIFICATION_V0.1.0.md](CLASS68_FORMAL_CERTIFICATION_V0.1.0.md).

Status date: 2026-07-30 UTC

## Result

The `horizonlink` v0.7.0 pipeline generated one native pseudo-Boolean
necessary-condition formula for each of the 12 candidate minimum-point
four-set orbits of project class 68.

Every formula was independently parsed and reconstructed row for row without
importing either the production candidate-formula builder or the production PB
module.

| Check | Result |
|---|---:|
| Candidate orbits | 12 |
| Native OPB formulas | 12 |
| Variables per formula | 792 |
| Bounded mathematical rows per formula | 563 |
| Serialized OPB constraints per formula | 568 |
| Serialized rows independently compared | 6,816 |
| Ordered row comparisons passed | 6,816 / 6,816 |
| Distinct native formula hashes | 12 |
| Distinct canonical formula hashes | 12 |
| Total native formula bytes | 6,325,777 |

No direct-containment test, LP, MILP, proof generation, or verifier run was
performed. All 12 orbits remain formally unresolved.

## Input gates

The phase fails closed unless both immutable input checkpoints pass their
complete `SHA256SUMS` audits.

| Input artifact | SHA-256 |
|---|---|
| Structural census `SHA256SUMS` | `86ec09c20b888ceffe88c70c5f4013e5dcddda94e12d55b348a05dfc712a553e` |
| Structural census manifest | `6954eefecdad34d27abc4715a2b1934a18e33dae7f306e34e28e4d651cd2b18f` |
| Class-68 structural record | `2ca8672ed77587b4d937c5f130f3bc1d73bcd5da9cfbba0daa0cf66fa61af7d2` |
| Class-68 canonical input file | `91b17dfc428d1a667f46157e888ba543e02c16d03fdea19c6ff89b4f8a286d9e` |
| Pilot-screening `SHA256SUMS` | `5202b0e664e2ddef7860a488afecad623e7cca42e06d2217d4ea648d4ff9cecb` |
| Pilot-screening manifest | `04b00c4026be1f29057ff8a2d1c6ce9d5d4dfdd95c28d05ce2c0acb21d2f5f32` |
| Class-68 screening manifest | `d5a20f382e811cc80d4f3715d0658816be7e081321b87ac994037cbf7c50d626` |

The class-68 labeled-link hash is
`a66e49afc58526140a16d71c9cd89ab11add1e1e01832eecd1a6792764a28731`.
The candidate-orbit partition hash is
`9c433703f4d97c2d68d841f4b42e232db4631e6c4342a4a4611122ace3b70d96`.

The gate also recomputes class 68 from the canonical link and compares:

- cover validation;
- class index and numbering source;
- canonical link hashes;
- automorphism-group order and group hash;
- all 12 candidate representatives, orbit sizes, and stabilizers;
- the complete candidate partition hash;
- all prior candidate decisions.

The pilot screening retained all 12 candidate orbits. This phase does not
reinterpret that retention as feasibility.

## Formula semantics

Each variable represents one of the
\(\binom{12}{7}=792\) possible seven-subsets of the labeled link ground set.
A selected variable represents an extension block containing the distinguished
link point in a hypothetical 29-block \(C(13,7,4)\) cover.

Each formula contains these ordered row families:

| Row family | Serialized constraints |
|---|---:|
| Residual four-set coverage | 285 |
| Point-degree bounds, including four candidate equalities | 16 |
| Positive pair-degree lower bounds | 65 |
| Positive triple-degree lower bounds | 200 |
| Exact 14-block count | 2 |
| **Total** | **568** |

The four points in the orbit representative are fixed at full degree 15. All
other points retain the lower bound implied by the link. The model is only a
necessary condition: a satisfying assignment would require independent
validation before it could be interpreted as a covering design.

## Independent serialization audit

The independent audit:

1. loads and structurally recomputes the class-68 link;
2. independently enumerates the 792 extension blocks;
3. independently constructs every residual-four, point, pair, triple, and
   block-count row;
4. parses every native OPB line;
5. compares all rows in exact order;
6. independently recomputes the canonical and normalized-row hashes;
7. checks OPB headers, comments, byte counts, metadata files, and status
   boundaries;
8. verifies the corpus checksum inventory.

All 12 formula comparisons pass.

## Checkpoint artifacts

The complete checkpoint is in
[`results/class68-candidate-formulas-v0.1.0/`](../results/class68-candidate-formulas-v0.1.0/).

| Artifact | SHA-256 |
|---|---|
| `phase.manifest.json` | `ea3d5a6a9318d6fd9ff702346b577956db42f43ea2a3e5e7d588d3438f2e2cd9` |
| `independent-audit.json` | `340dcac87e9e4a13df9391f580497f0e287556e95bfb6e42469043e1e96d3428` |
| `corpus/corpus.manifest.json` | `d39d08680cc5509a76299d09386a1bd9b3e74a4af185cd3801369d37ce1e6945` |
| `SHA256SUMS` | `013581a5b4a289030194d9d63b21d212be42c637728fd74d330fc55f7af97b1a` |

The phase manifest records every orbit representative, formula path, native
hash, canonical hash, metadata hash, independent comparison, and status
ledger. No orbit disappears silently.

## Reproduction

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

## Claim boundary and next gate

This checkpoint establishes exact formula generation, not infeasibility. It
does not eliminate any class-68 orbit or class 68 itself.

The direct-containment follow-on is complete; see
[`CLASS68_DIRECT_CONTAINMENT_V0.1.0.md`](CLASS68_DIRECT_CONTAINMENT_V0.1.0.md).
It found no direct-containment contradiction. The subsequent exact root-LP
phase is also complete; see
[`CLASS68_ROOT_LP_V0.1.0.md`](CLASS68_ROOT_LP_V0.1.0.md). Six of the 12 formulas
are now formally pruned by verified exact Farkas proofs, while six survive the
root LP. Class 68 remains unresolved.

# Class-68 exact root-LP checkpoint v0.1.0

Status date: 2026-08-06 UTC

## Result

The `horizonlink` v0.9.0 pipeline inspected exactly the 12 audited class-68
candidate formulas that survived the exhaustive direct-containment phase.
The result is an exact 6/6 partition:

| Orbit | Candidate minimum points | Exact root-LP result | Formal disposition after verification |
|---:|---|---|---|
| 0 | `0,1,2,3` | exact rational LP witness | survives root LP |
| 1 | `0,1,2,4` | exact integer Farkas contradiction | `VERIFIED_UNSAT`; formally pruned |
| 2 | `0,1,2,6` | exact rational LP witness | survives root LP |
| 3 | `0,1,3,4` | exact integer Farkas contradiction | `VERIFIED_UNSAT`; formally pruned |
| 4 | `0,1,3,6` | exact rational LP witness | survives root LP |
| 5 | `0,1,3,8` | exact rational LP witness | survives root LP |
| 6 | `0,1,4,5` | exact integer Farkas contradiction | `VERIFIED_UNSAT`; formally pruned |
| 7 | `0,1,4,6` | exact integer Farkas contradiction | `VERIFIED_UNSAT`; formally pruned |
| 8 | `0,1,4,8` | exact integer Farkas contradiction | `VERIFIED_UNSAT`; formally pruned |
| 9 | `0,1,6,7` | exact rational LP witness | survives root LP |
| 10 | `0,1,8,11` | exact rational LP witness | survives root LP |
| 11 | `0,3,4,5` | exact integer Farkas contradiction | `VERIFIED_UNSAT`; formally pruned |

The mathematical checkpoint accounts for all 12 orbits, and its independent
exact-evidence audit passes 12/12. The verification checkpoint accounts for
all six generated proofs, and its independent verification audit passes 6/6.

This does not eliminate class 68. Orbits 0, 2, 4, 5, 9, and 10 remain
unresolved.

## Exact LP evidence

The floating stage is a deterministic zero-objective SciPy/HiGHS feasibility
probe with presolve enabled, one thread, HiGHS parallelism disabled, and
random seed zero. Floating output is not treated as a certificate.

For an LP-feasible report, the implementation uses the floating solution only
to identify zero-bound variables and tight rows. It then solves a full-rank
active system with `fractions.Fraction` arithmetic. The resulting rational
vector is checked exactly against every one of the 568 serialized formula
rows and every `0 <= x <= 1` bound.

All six LP-feasible cases pass those exact checks. These vectors witness only
the continuous root relaxation; they are not Boolean assignments, do not make
the native pseudo-Boolean formulas `SAT`, and do not establish a 29-block
covering design.

For a root-LP-infeasible report, floating dual information is used only to
select a support. The pipeline reconstructs a primitive positive integer
Farkas combination from the exact serialized rows. The combination cancels
every variable coefficient and leaves a strictly positive contradiction
right-hand side.

## Independent mathematical audit

The independent auditor deliberately does not import the production root-LP
scanner, production OPB parser, or production Farkas renderer. It separately:

1. verifies both complete input checkpoints and their stage boundaries;
2. reparses every native OPB;
3. checks every rational LP witness against every row and bound exactly;
4. reconstructs each normalized verifier formula row by row;
5. recomputes every Farkas weighted sum with arbitrary-precision integers;
6. reconstructs every four-line proof token stream; and
7. requires all 12 candidate orbits to be present explicitly.

The audit confirms six exact LP-feasible roots and six exact Farkas
contradictions, with 12/12 records passing.

## Formal verification gate

The mathematical checkpoint deliberately stops the six contradiction cases at
`PROOF_GENERATED`; it does not authorize formal pruning on the basis of the LP
solver or Farkas generator alone.

A separate fail-closed verification checkpoint rehashes the mathematical
checkpoint, formula, proof, pinned verifier wheel, and preserved verifier
build provenance before invoking VeriPB. All six calls use
`--requireUnsat`. Each exits zero and reports exactly
`Verification succeeded.`. The verification logs are preserved.

The pinned verifier is VeriPB 0.3a0. Its wheel SHA-256 is
`3844f3b416c870f6ef96fc737125e4ec97b6cfd1c4d1726a2bc158626c77b369`.
The build-provenance SHA-256 is
`b829e64b9b6c0872bd6dc2e8cb89702ac8c29ec9c6697637d7d97aa8854d2f99`.
That provenance connects the build to the immutable published class-52 source
archive with SHA-256
`c4c1ddc812affd9bd05c452855bdfcd614a68906f8bf536fab8bcd4b3123ae56`.

The independent verification auditor then rehashes the stored artifacts and
logs without rerunning the verifier, checks that `--requireUnsat` occurs in
every preserved logical command, and requires successful exit and success
output. All 6/6 verification records pass. Only at this gate are orbits 1, 3,
6, 7, 8, and 11 promoted to `VERIFIED_UNSAT` and formally pruned.

## Checkpoint artifacts

The exact mathematical checkpoint is in
[`results/class68-root-lp-v0.1.0/`](../results/class68-root-lp-v0.1.0/).

| Artifact | SHA-256 |
|---|---|
| `root-lp.manifest.json` | `ea9fbae84801906d6ac35f238e3f06cfb0625a123034083da39d0cded051871c` |
| `phase.manifest.json` | `2f6df256d087a71dabaaccd892e2d15470f0934273e36cefb7d0e727939e2a06` |
| `independent-audit.json` | `97d053f58ef2f269e4109f8cbbbee69584219cddae80611fbce2cb8267ed67da` |
| `SHA256SUMS` | `33c41b072d5a44bf7520ccea97d71785f61a2f24882f2203ab34b104168a50b9` |

The formal verification checkpoint is in
[`results/class68-root-lp-verification-v0.1.0/`](../results/class68-root-lp-verification-v0.1.0/).

| Artifact | SHA-256 |
|---|---|
| `verification.manifest.json` | `5d117e361cf277c3102c55507d3c902f8197ba31fe58822ad546007ef60ac995` |
| `phase.manifest.json` | `f309c9e97b11ae87c85c4c97baed73ee2d8a06a6188cc8f8b490baf28cfdb286` |
| `independent-audit.json` | `79a3e6db1272e03f7669e73af4546df001ed2188b29601acbe1956877f8a344a` |
| `SHA256SUMS` | `be3d9f800886ca53b1f9fd9538d329476a7f1a2dd5e235f0be7884a51124aec9` |

Every candidate orbit has a root-LP metadata record. Every Farkas case also
has a normalized OPB and proof in the mathematical checkpoint, plus its own
verification result and log in the verification checkpoint. No case
disappears silently.

## Reproduction

Regenerate the mathematical checkpoint:

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

With the pinned VeriPB wheel installed in a clean environment, regenerate the
verification checkpoint:

```bash
horizonlink verify-root-lp \
  --root-lp-directory results/class68-root-lp-v0.1.0 \
  --verifier /path/to/venv/bin/veripb \
  --verifier-python /path/to/venv/bin/python \
  --verifier-wheel /path/to/veripb-0.3a0-cp312-cp312-linux_x86_64.whl \
  --verifier-build-provenance /path/to/build.provenance.json \
  --output-directory build/class68-root-lp-verification
```

## Claim boundary and next gate

This checkpoint formally prunes six class-68 candidate orbits. It does not
eliminate class 68, does not establish a satisfying Boolean assignment for any
survivor, and does not establish `C(13,7,4)=30`.

The next bounded research gate is an exact LP split-tree/Farkas attempt on
only the six root-LP survivors. MILP, RoundingSat, class 4, class 59, and a
bulk all-67 campaign remain deferred.

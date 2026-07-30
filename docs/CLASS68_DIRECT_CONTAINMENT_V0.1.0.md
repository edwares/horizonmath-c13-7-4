# Class-68 direct-containment scan v0.1.0

Status date: 2026-07-30 UTC

## Result

The `horizonlink` v0.8.0 pipeline exhaustively scanned all 12 audited
class-68 candidate-orbit formulas for a direct support-containment
contradiction.

| Check | Result |
|---|---:|
| Candidate formulas expected | 12 |
| Candidate formulas scanned | 12 |
| Lower rows per formula | 563 |
| Upper rows per formula | 5 |
| Lower/upper row pairs tested per formula | 2,815 |
| Lower/upper row pairs tested overall | 33,780 |
| Support containments found overall | 14,284 |
| Strictly contradictory containments | 0 |
| Cutting-planes proofs emitted | 0 |
| Formulas surviving this screen | 12 |
| Independent scan comparisons passed | 12 / 12 |

All 12 formulas survive this narrow screen. “Survives” means only that no
contradiction of this exact form was found. It is not evidence that an OPB is
satisfiable or that a 29-block covering design exists.

No LP, MILP, pseudo-Boolean solver, proof verifier, or class-4/class-59 run was
performed. No class-68 orbit was pruned, and class 68 is not eliminated.

## Exact criterion

For every serialized lower row

\[
\sum_{i\in S}x_i \ge L
\]

and every serialized upper row

\[
\sum_{i\in T}x_i \le U,
\]

the scanner tests whether \(S\subseteq T\) and \(L>U\).

When both conditions hold, sign-reversing the upper row and adding the two
input constraints gives

\[
-\sum_{i\in T\setminus S}x_i \ge L-U>0.
\]

The left side is nonpositive for Boolean variables, so the result is an
immediate cutting-planes contradiction.

The scan is exhaustive over the serialized formula rows. For each formula it
records:

- the number of lower and upper rows;
- every lower/upper pair tested;
- the number of support containments;
- the complete histogram of \(L-U\) over those containments;
- every strict witness, if any;
- the source formula hash and status boundary.

For class 68, the maximum observed containment gap is exactly zero in every
formula. Therefore none of the 14,284 support containments is contradictory.

## Published-method regression

The implementation includes a regression against the previously certified
class-52 method. It regenerates case 21/profile 014 with pair multiplicities
4 through 14 and obtains:

- no direct-containment witness for `eq4` through `eq8`;
- exactly two endpoint witnesses for each of `eq9` through `eq14`;
- first deterministic witness: pair lower row 642 contained in point upper
  row 283;
- exact `eq9` proof bytes:

```text
pseudo-Boolean proof version 1.0
f 643
p 283 642 +
c 644
```

That proof is 57 bytes, matching the size of the published direct-containment
certificates. Its SHA-256 is
`d5de2f400f23568490fcbaf33a0a9919f1246b7e6889f907d9fdf0a4f000b48c`.

This regression validates the proof construction. It does not create any
class-68 proof because the class-68 scan found no witness.

## Input gate

The phase refuses to run unless the complete class-68 candidate-formula
checkpoint passes its `SHA256SUMS` inventory and all of the following remain
true:

- checkpoint status is `FORMULAS_GENERATED`;
- all 12 candidate orbits are accounted for;
- all 6,816 source rows passed the prior independent audit;
- direct containment, root LP, solver, proof, and verifier stages were
  previously `NOT_STARTED`;
- every formula byte count and SHA-256 matches its manifest.

The input checkpoint `SHA256SUMS` hash is
`013581a5b4a289030194d9d63b21d212be42c637728fd74d330fc55f7af97b1a`.

## Independent audit

The independent audit does not import the production scanner, OPB parser, or
proof renderer. It separately:

1. verifies the complete candidate-checkpoint checksum inventory;
2. parses every native formula;
3. independently enumerates all 33,780 lower/upper row pairs;
4. recomputes all 14,284 support containments and every bound gap;
5. compares the complete per-orbit scan records;
6. requires proof artifacts to be absent for every survivor;
7. checks every per-orbit metadata file and the exact output inventory.

All 12 independent comparisons pass.

## Checkpoint artifacts

The complete checkpoint is in
[`results/class68-direct-containment-v0.1.0/`](../results/class68-direct-containment-v0.1.0/).

| Artifact | SHA-256 |
|---|---|
| `phase.manifest.json` | `49c3d14d2918261398fa2e683ebcb27d347af9cdceadfa5d26057d3267f2a470` |
| `scan.manifest.json` | `a8d5a2b96eb067fe2b82855876163392b1459f9945365063d7c2ac2a20b4b479` |
| `independent-audit.json` | `df713833ee5a18634f4b24c76891efee7b8620f54b83861a433ea9512a34973d` |
| `SHA256SUMS` | `fe14bac9f54439a52eee055952381c26e2075081e7126a873239034699433f81` |

Every orbit has its own
`instances/c68_candidate_orbitNN.direct-containment.json` record. No case
disappears silently.

## Reproduction

```bash
horizonlink scan-direct-containment \
  --candidate-checkpoint-directory \
    results/class68-candidate-formulas-v0.1.0 \
  --output-directory build/class68-direct-containment

diff -qr \
  results/class68-direct-containment-v0.1.0 \
  build/class68-direct-containment
```

## Claim boundary and next gate

This phase establishes only that the 12 candidate formulas have no
single-lower-row/single-upper-row direct-containment contradiction.

The next bounded step is exact root-LP inspection of these 12 surviving
formulas. Any root-LP-infeasible formula must receive an exact integer Farkas
certificate and a preserved VeriPB `--requireUnsat` verification before its
orbit may be treated as formally pruned. MILP and RoundingSat remain deferred.

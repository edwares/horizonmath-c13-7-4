# Solver-free pilot profile screening v0.1.0

Status date: 2026-07-30 UTC

## Result

The `horizonlink` v0.6.0 pipeline materialized and screened every
symmetry-reduced degree-profile orbit for pilot classes 68, 4, and 59.

The run did not emit a pseudo-Boolean formula and did not invoke an LP solver,
PB solver, proof generator, or verifier.

| Class | Group order | Candidate four-set orbits | Exact-set orbits | Profile orbits | Direct arithmetic discards | Retained |
|---:|---:|---:|---:|---:|---:|---:|
| 68 | 240 | 12 | 88 | 755 | 4 | 751 |
| 4 | 2 | 279 | 2,123 | 39,618 | 54 | 39,564 |
| 59 | 1 | 495 | 3,797 | 75,582 | 78 | 75,504 |
| **Total** |  | **786** | **6,008** | **115,955** | **136** | **115,819** |

Only about 0.12% of the profile orbits were removed. This is not a strong
reduction, but it is an honest one: no historical MILP disposition was copied
to a new class, and no unproved heuristic was used to discard a case.

## Checkpoint artifacts

The complete checkpoint is in
[`results/pilot-screening-v0.1.0/`](../results/pilot-screening-v0.1.0/).

| Artifact | SHA-256 |
|---|---|
| `screening.manifest.json` | `04b00c4026be1f29057ff8a2d1c6ce9d5d4dfdd95c28d05ce2c0acb21d2f5f32` |
| `ranking.json` | `33d6533b78f9d7f53e7b593b296333163093a248a087eb2a6178505720233177` |
| `ranking.csv` | `e63834596f5186930b4d688b4187f8769b359573543da6c31112ead40a69f65a` |
| `SHA256SUMS` | `5202b0e664e2ddef7860a488afecad623e7cca42e06d2217d4ea648d4ff9cecb` |
| Class-68 manifest | `d5a20f382e811cc80d4f3715d0658816be7e081321b87ac994037cbf7c50d626` |
| Class-4 manifest | `205d6d14da012a1a8694fc640151b50f7cd0d73fb941430e72299241e9bced52` |
| Class-59 manifest | `c05255cdac2932b9b0423a6cb0e04bd3f621955406f5ac85aafa9ae7bd270668` |

`SHA256SUMS` covers every other checkpoint file. Exact minimum sets and degree
profiles are stored as deterministic gzip-compressed JSON Lines. Their gzip
timestamps are zero, and each manifest records both compressed and
uncompressed hashes, byte counts, and line counts.

## Input provenance

The screening stage consumes the immutable structural census:

| Structural input | SHA-256 |
|---|---|
| `structural-census-v0.1.0/census.manifest.json` | `6954eefecdad34d27abc4715a2b1934a18e33dae7f306e34e28e4d651cd2b18f` |
| `structural-census-v0.1.0/ranking.json` | `27a0269c4656a188f56db40aeb25f23d04c0fb9357d32851219f37e7c47dd886` |
| `structural-census-v0.1.0/SHA256SUMS` | `86ec09c20b888ceffe88c70c5f4013e5dcddda94e12d55b348a05dfc712a553e` |

Before profile generation, the pipeline verifies every structural-checkpoint
checksum, reloads each canonical link, recomputes its structural manifest, and
compares the labeled-link hash, automorphism-group hash, candidate-orbit
partition hash, and structural counts.

## Deterministic decision rules

### Candidate four-set orbits

Every candidate orbit is retained. The degree budget proves that at least four
points have zero excess, but it does not by itself eliminate a particular
four-set orbit. The historical class-52 candidate pruning depended on
necessary-condition PB models and later proof work; it is not silently reused
for these classes.

### Exact minimum sets

For an exact minimum set \(M\), every point outside \(M\) receives positive
integral excess, with total excess eight. The raw count is

\[
\binom{7}{12-|M|-1}
\]

when \(1 \le 12-|M| \le 8\), with the zero-part case handled separately.
The unique 12-point exact-minimum-set orbit in each class therefore has zero
valid positive compositions and is discarded. Every exact-set orbit and its
decision is recorded.

### Degree profiles

The rules are applied in this order:

1. **Extension point capacity.** Fourteen binary extension blocks are selected,
   so every extension point degree is at most 14. A vector with a degree above
   14 is a direct arithmetic contradiction.
2. **Corrected pair interval.** For link pair multiplicity
   \(\ell_{ij}\) and full point degrees \(r_i,r_j\), the extension pair
   multiplicity must satisfy the corrected upper bound

   \[
   y_{ij}\le
   \min(6r_i-70-\ell_{ij},6r_j-70-\ell_{ij}).
   \]

   The lower bound is \(y_{ij}\ge 7-\ell_{ij}\). An empty interval would be a
   direct contradiction. No additional pilot profile was removed by this
   test.
3. **Retain.** A profile passing both tests is retained with
   `NO_CONTRADICTION_FOUND`. Retention is not a SAT result.

Every decision is recomputed for every member of the corresponding profile
orbit, and the manifest requires orbit invariance.

## Refined pilot order

Ordering the three pilot classes by retained profile count, followed by the
previous structural tie-breakers, gives:

1. class 68 — 751 retained profiles;
2. class 4 — 39,564 retained profiles;
3. class 59 — 75,504 retained profiles.

The order is unchanged. Root-LP feasibility, solver runtime, and proof-size
metrics remain `NOT_STARTED`.

## Class-52 boundary

Applying this new unscreened arithmetic stage to class 52 would materialize
2,578 profile orbits, discard 6 by point capacity, and retain 2,572. This does
not replace or reinterpret the historical class-52 chain:

- 107 profiles were generated only after historical candidate and exact-case
  screening;
- 20 of those were retained for the corrected terminal formula corpus;
- the published 30 terminal instances remain the authoritative
  `VERIFIED_UNSAT` result.

The two workflows have different inputs and screening depth.

## Reproduction

```bash
python -m pip install -e .

horizonlink screen-profiles \
  --structural-census-directory \
    results/structural-census-v0.1.0 \
  --class-index 68 \
  --class-index 4 \
  --class-index 59 \
  --output-directory build/pilot-screening

sha256sum -c results/pilot-screening-v0.1.0/SHA256SUMS
diff -qr \
  results/pilot-screening-v0.1.0 \
  build/pilot-screening
```

The regression suite performs a second generation with the class arguments in
a different order and requires byte-for-byte equality.

## Claim boundary and next gate

This checkpoint eliminates 136 impossible profile orbits by direct arithmetic.
It does not eliminate class 68, class 4, class 59, or any other additional link
class. It does not establish \(C(13,7,4)=30\).

Generating terminal formulas for all 115,819 survivors would be a poor next
move. The next bounded gate is the 12 candidate-orbit formulas for class 68,
followed by direct containment proofs and only then exact root-LP inspection
for unresolved candidates.

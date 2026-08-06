# Immutable checkpoint artifacts

The source tree is derived from the following audited packages. Historical
bulky corpora and verifier build environments remain in their immutable
packages rather than being duplicated wholesale as ordinary Git source. The
later bounded class-68 checkpoints listed below deliberately check in their
own formulas, exact proofs, manifests, and verification logs for regression.

| Artifact | SHA-256 |
|---|---|
| `HorizonMath_horizonlink_frontend_v0.4.0.zip` | `1eb19f63c94f303e9a275d5c82444cfc34ff3ce47f48f7063361310858dac4de` |
| `HorizonMath_link_catalog_audit_v0.1.0.zip` | `b9541b92e25e27b1e343e46c96daa878945acfa3c8b74eb5753e10c10dd08cdd` |
| `HorizonMath_classification_provenance_audit_v0.1.0.zip` | `aadb502f39908c7ab61e5348bd68e12c939194332385a418fff4f222b77b9aff` |

The separately published class-52 certification is archived at:

- <https://github.com/edwares/class52-formal-certification>
- <https://doi.org/10.5281/zenodo.21660461>

Its complete release archive has SHA-256:

`c4c1ddc812affd9bd05c452855bdfcd614a68906f8bf536fab8bcd4b3123ae56`

The evolving repository also contains deterministic checked-in checkpoints:

| Checkpoint | Integrity artifact | SHA-256 |
|---|---|---|
| Solver-free 68-class structural census | `results/structural-census-v0.1.0/SHA256SUMS` | `86ec09c20b888ceffe88c70c5f4013e5dcddda94e12d55b348a05dfc712a553e` |
| Solver-free three-class pilot screening | `results/pilot-screening-v0.1.0/SHA256SUMS` | `5202b0e664e2ddef7860a488afecad623e7cca42e06d2217d4ea648d4ff9cecb` |
| Class-68 candidate formula corpus | `results/class68-candidate-formulas-v0.1.0/SHA256SUMS` | `013581a5b4a289030194d9d63b21d212be42c637728fd74d330fc55f7af97b1a` |
| Class-68 direct-containment scan | `results/class68-direct-containment-v0.1.0/SHA256SUMS` | `fe14bac9f54439a52eee055952381c26e2075081e7126a873239034699433f81` |
| Class-68 exact root-LP checkpoint | `results/class68-root-lp-v0.1.0/SHA256SUMS` | `33c41b072d5a44bf7520ccea97d71785f61a2f24882f2203ab34b104168a50b9` |
| Class-68 root-LP VeriPB verification checkpoint | `results/class68-root-lp-verification-v0.1.0/SHA256SUMS` | `be3d9f800886ca53b1f9fd9538d329476a7f1a2dd5e235f0be7884a51124aec9` |

The class-68 verification checkpoint identifies the preserved verifier build
by these additional hashes:

| Verifier provenance input | SHA-256 |
|---|---|
| `veripb-0.3a0-cp312-cp312-linux_x86_64.whl` | `3844f3b416c870f6ef96fc737125e4ec97b6cfd1c4d1726a2bc158626c77b369` |
| `build.provenance.json` | `b829e64b9b6c0872bd6dc2e8cb89702ac8c29ec9c6697637d7d97aa8854d2f99` |

The repository adapts the v0.4.0 package for source control by:

- moving historical phase reports under `docs/pipeline/`;
- incorporating the later audited catalog and literature bridge;
- upgrading the class-52 numbering-source status from `PARTIAL` to `AUDITED`;
- making proof tests regenerate candidate formulas from source rather than
  requiring the complete generated build tree.

Consequently, the repository tree is not asserted to be byte-identical to the
three ZIP packages. The ZIP hashes identify the immutable phase checkpoints;
Git commits identify the evolving source tree.

# Class-68 root-LP regeneration fingerprint v0.2.0

This directory intentionally stores the deterministic `SHA256SUMS` fingerprint
rather than a second copy of the complete root-LP corpus. The complete,
verifier-bound v0.1 checkpoint remains at `../class68-root-lp-v0.1.0/`.

Current `horizonlink scan-root-lp` output must reproduce `SHA256SUMS` exactly.
The regression suite also requires every exact rational witness, exact integer
Farkas certificate, verifier-normalized OPB, and PBP proof to match v0.1. The
v0.2 serialization change replaces raw floating HiGHS dual-margin diagnostics
with exact unit-sum Farkas-ray margins.

The SHA-256 of `SHA256SUMS` is
`c2b1b3cc74784f4377fc877f705816cc5befcfb3c0bca6c782b3ad515438bff2`.

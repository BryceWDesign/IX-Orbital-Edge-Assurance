# Validation record, 25 September 2026

## Executed release checks

The release was generated and checked in the handoff environment using the
following commands:

```text
python -m compileall -q orbital_assurance tests
python -m unittest discover -s tests -v
python -m orbital_assurance demo --output demo-output
python -m orbital_assurance verify demo-output
```

Observed local result: **48 tests passed**. The default demo generated 60
synthetic records and independently verified its signed manifest, signed
mission authority, all signed decision receipts, receipt chain, file hashes,
deterministic replay, assurance-case reconstruction, and ground review.

Default authority-state coverage:

```text
ACT                    36
ABSTAIN                 1
DEGRADE                 2
RETAIN                  14
REQUEST_GROUND_REVIEW    4
FALLBACK                 3
```

## Adversarial/negative coverage

The automated suite includes checks for:

- Ed25519 payload tampering,
- signature key-ID tampering,
- signed authority mutation,
- wrong mission scope,
- authority expiry,
- disallowed phase and decision class,
- changed model and policy scope,
- physical-control enablement rejection,
- receipt-signature corruption,
- receipt-chain modification,
- evidence-file corruption,
- file rehashing without re-signing the manifest,
- manifest-signature corruption,
- invalid authority fail-closed behavior,
- stale telemetry escalation,
- battery fallback,
- distribution-shift degradation,
- outage retention,
- raw-evidence hash linkage,
- assurance-case exact reconstruction,
- deterministic repeat-bundle byte identity.

## Meaning of GREEN

GREEN means the included deterministic evaluation contracts passed locally.
The GitHub workflow is configured to run the suite on Python 3.11, 3.12, and
3.13 after push. This handoff does **not** claim those remote jobs have run.

GREEN does not mean flight-qualified, safe for spacecraft use, cryptographically
rooted in hardware, certified, radiation tested, HIL validated, or suitable for
an operational mission. The demo keys are intentionally public and non-secret.

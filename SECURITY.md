# Security scope

v2.0.0 adds real Ed25519 signatures to mission authority, the bundle manifest,
and every decision receipt. The verifier validates public-key fingerprints,
signatures, receipt chaining, canonical artifact hashes, deterministic replay,
and assurance-case traceability.

## Evaluation-key warning

The included ground-release and edge-runtime demo private keys are derived
deterministically from public repository strings. They are **not secrets** and
must never be treated as operational trust anchors. Their purpose is to make
cryptographic behavior executable, testable, adversarially verifiable, and
byte-reproducible in a public evaluation package.

Operationalization would require at minimum externally provisioned protected
private keys, hardware/OS trust boundaries, secure key storage, rotation and
revocation, authenticated update/recovery channels, independent identity
binding, incident recovery, and mission-specific authorization policy.

No credentials, network services, spacecraft command interfaces, actuator
paths, or real mission data are included. Do not connect this release to a
spacecraft or operational mission workflow.

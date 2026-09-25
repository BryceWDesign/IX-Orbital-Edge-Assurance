# IX-Orbital-Edge-Assurance

**Evaluation-only mission-assurance control plane for spacecraft edge autonomy.**

The runtime decides whether a synthetic onboard AI result may **ACT, ABSTAIN,
DEGRADE, RETAIN evidence, REQUEST_GROUND_REVIEW, or FALLBACK**. Every decision
is bound to mission scope, model and policy identity, runtime qualification
state, raw-observation integrity, traceability requirements, a hash-chained
receipt, and an Ed25519 runtime signature. The generated evidence bundle itself
is signed by a separate ground-release identity and independently replayed.

This is a terrestrial research/evaluation runtime, **not flight software and
not flight-qualified**. It has no spacecraft command bus, no actuator path, no
RF stack, no real mission telemetry, and no operational trust anchor.

## What v2.0.0 actually implements

- **Signed mission authority**: mission, time, phase, model, policy, and decision
  class are checked before AI output is treated as authorized.
- **Explicit authority states**: `ACT`, `ABSTAIN`, `DEGRADE`, `RETAIN`,
  `REQUEST_GROUND_REVIEW`, and `FALLBACK` are executable runtime outcomes, not
  documentation labels.
- **Uncertainty gating**: confidence-near-boundary behavior causes abstention or
  ground review according to policy.
- **Distribution-shift gating**: deterministic feature-domain drift can reduce
  authority or force fallback.
- **Sensor and platform gates**: stale telemetry, poor sensor quality, and low
  battery change authority state without pretending the model remains valid.
- **Evidence retention**: review/degraded/fallback outcomes create retained raw
  evidence references linked to the original observation hash and signed receipt.
- **Prioritized store-and-forward**: outage traffic is queued by P0-P4 mission
  evidence priority with finite capacity and explicit drop accounting.
- **Cryptographic attribution**: ground release, manifest, and every runtime
  decision use real Ed25519 signatures through `cryptography`.
- **Receipt chaining**: each signed decision receipt binds the previous receipt,
  decision digest, and traceability identifiers.
- **Assurance-case traceability**: mission need -> hazards -> requirements ->
  claims -> concrete receipt hashes is generated from the run and reverified.
- **Deterministic replay**: the verifier recomputes edge behavior, validates all
  signatures and hashes, rebuilds the assurance case, and recomputes the ground
  report.
- **Physical control prohibited**: propulsion, attitude control, payload
  shutdown, and thermal override are explicitly denied in the signed authority;
  the software exposes no actuator interface.

## Quick start

Requires Python **3.11+** and `cryptography>=42`.

```powershell
python -m pip install -e .
python -m orbital_assurance demo --output demo-output
python -m orbital_assurance verify demo-output
python -m unittest discover -s tests -v
```

The default 60-record synthetic campaign deliberately exercises all six runtime
states. In the included release generated on 25 September 2026 the state counts
are:

| Authority outcome | Count |
| --- | ---: |
| ACT | 36 |
| ABSTAIN | 1 |
| DEGRADE | 2 |
| RETAIN | 14 |
| REQUEST_GROUND_REVIEW | 4 |
| FALLBACK | 3 |

These counts are deterministic properties of the included synthetic scenario,
not spacecraft reliability or mission-performance statistics.

## Evidence bundle

`demo-output/` contains:

| Artifact | Meaning |
| --- | --- |
| `scenario.json` | Fully synthetic sensor records and ground-only labels |
| `model.json` | Deterministically trained synthetic logistic classifier |
| `policy.json` | Uncertainty, drift, battery, sensor, link, and queue gates |
| `mission_authority.json` | Ed25519-signed mission/model/policy/time/phase authority |
| `edge_run.json` | Runtime decisions, signed chained receipts, retention ledger, and transport outcomes |
| `assurance_case.json` | Mission need, hazards, requirements, claims, and receipt-level traceability |
| `ground_review.json` | Replayed ground evaluation and limitations |
| `manifest.json` | Canonical file inventory and hashes |
| `manifest_signature.json` | Ed25519 signature over the manifest |

Verification is intentionally strict. Changing an artifact without updating its
manifest fails integrity. Rehashing a changed artifact without the release key
fails the signed manifest. Changing a decision or receipt fails signature,
receipt-chain, deterministic replay, and/or assurance-case verification.

## Important cryptographic boundary

The default demo identities are **deterministic, public, non-secret evaluation
keys** so the repository can reproduce the same signed bundle byte-for-byte.
The signatures therefore prove attribution to the bundled evaluation key, not
to a person, HSM, spacecraft, or protected operational identity. Real mission
use would require externally provisioned protected keys, hardware/OS trust,
secure update/recovery procedures, key rotation/revocation, and independent
identity governance.

## What this release does not claim

It does not claim flight readiness, certification, autonomous spacecraft
control, secure boot, hardware attestation, radiation tolerance, real RF or
contact-plan fidelity, model generalization on mission data, safety assurance,
or economic savings. All telemetry, hazards exercised, drift events, link
outages, cost inputs, and labels in the example are synthetic or assumed.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md),
[docs/VALIDATION.md](docs/VALIDATION.md), and [SECURITY.md](SECURITY.md).

## Evaluation and ownership

This repository is source-available for private, non-operational evaluation
only under [LICENSE](LICENSE). No production, mission, funded customer,
commercial-profit, redistribution, derivative-product, or IP ownership rights
are granted. Broader use or ownership requires a separate signed written
agreement. See [COMMERCIAL.md](COMMERCIAL.md).

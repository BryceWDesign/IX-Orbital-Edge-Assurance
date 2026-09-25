# Architecture, v2.0.0

## System boundary

IX-Orbital-Edge-Assurance v2.0.0 is a local evaluation runtime representing
three logical roles: **ground release authority**, **spacecraft edge runtime**,
and **ground assurance review**. They execute on one terrestrial computer in
the demo. There is no spacecraft interface or control path.

```text
Ground release identity
        |
        | Ed25519 signed mission authority
        v
Synthetic observation -> qualification -> authority decision
                         | uncertainty
                         | drift
                         | freshness
                         | sensor quality
                         | battery
                         | mission/model/policy/time/phase scope
                         v
          ACT / ABSTAIN / DEGRADE / RETAIN
          REQUEST_GROUND_REVIEW / FALLBACK
                         |
                         | signed chained decision receipt
                         v
                 evidence retention
                         |
                         v
              priority store/forward
                         |
                         v
                 ground verification
                         |
                         +-> deterministic replay
                         +-> Ed25519 verification
                         +-> assurance-case traceability
```

## Authority contract

`mission_authority.json` is signed by the ground-release evaluation identity.
It binds:

- mission identifier,
- runtime subject,
- valid tick interval,
- model SHA-256,
- policy SHA-256,
- permitted decision classes,
- permitted mission phases,
- explicitly denied physical-control classes,
- evaluation-only / non-operational status.

A signature-valid authority can still be rejected if any scope does not match
the current runtime context.

## Runtime qualification order

For each observation the runtime checks:

1. canonical input/schema validity,
2. signed mission authority and scope,
3. battery fallback floor,
4. telemetry freshness,
5. sensor-quality floor,
6. synthetic-model inference,
7. uncertainty state,
8. distribution-shift state,
9. contact availability,
10. bounded authority outcome.

Invalid authority and hard qualification limits fail closed to `FALLBACK`.
Stale/low-quality data escalates to `REQUEST_GROUND_REVIEW`. Intermediate
uncertainty produces `ABSTAIN`; stronger uncertainty produces ground review.
Declared drift thresholds produce `DEGRADE` then `FALLBACK`. Qualified records
during loss of contact can produce `RETAIN` so evidence is preserved for later
review rather than silently discarded.

## Decision provenance

Each decision contains model, policy, authority, and raw-observation hashes,
qualification metrics, decision reason, evidence priority, retention/review
flags, and traceability IDs. A receipt then binds:

- decision SHA-256,
- previous receipt SHA-256,
- traceability IDs,
- runtime Ed25519 key ID and signature.

The resulting receipt chain detects removal, reordering, or modification when
verified against the signed records.

## Assurance case

`assurance_case.json` is generated from runtime evidence rather than maintained
as a disconnected prose claim. It links:

`MN-001` mission need -> hazards -> `REQ-*` requirements -> `CLM-*` claims ->
exact signed receipt hashes.

The verifier rebuilds the assurance case from `edge_run.json` and rejects a
mismatch.

## Communications behavior

The link emulator assigns evidence priorities P0-P4. Fallback is P0; ground
review and flagged risk are P1; abstain/degrade are P2; explicit retention is
P3; nominal activity is P4. Queue capacity is finite. On contact, higher
priority backlog is transmitted first. Under pressure, lower-priority packets
are discarded first and every discard remains explicit in the run record.

This is a byte-level store-and-forward model only. It is not an RF, CCSDS,
latency, retransmission, coding, or orbital contact simulator.

## Safety boundary

The signed authority explicitly denies propulsion, attitude control, payload
shutdown, and thermal override, while the policy sets
`physical_control_commands_enabled=false`. No module exposes an actuator or
spacecraft command interface. `ACT` means the bounded edge-AI decision is
accepted for the **telemetry-triage evaluation function**, not that a physical
spacecraft command is executed.

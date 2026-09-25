# System boundary and design

This release is an offline software experiment on a terrestrial computer. Its
edge, contact window, ground review, and cloud-side release preparation are
*roles in one local process*. It has no network, cloud credentials, radio,
spacecraft command bus, spacecraft fault-management integration, or connection
to a real sensor. It cannot issue actuator commands.

## Separation of concerns

| Stage | Implemented behavior | Boundary |
| --- | --- | --- |
| Preparation | Train a four-feature logistic classifier on generated, labeled examples. Establish model and policy SHA-256 pins for one mission and expiry tick. | Pins detect mismatch relative to the supplied ground release. They do not authenticate the publisher. |
| Edge | Check pin, mission, expiry, freshness, battery, input schema, and action allowlist; score a record only when gates pass. | Priority and routine actions produce metadata packets. Invalid state requests review and never commands hardware. |
| Link emulator | Queue packets during a scripted outage, cap local queue bytes, prioritize review packets on later contact, and account for drops. | The contact budget is an invented byte count, without headers, retransmissions, coding, or actual RF. |
| Ground audit | Recreate each edge decision from original inputs, verify all hashes, count false negatives and false positives using ground-only synthetic truth, and compare serialized byte volumes. | The ground has access to all observations in the example, even those whose summaries were dropped. A live system would need a separately validated raw-data retention policy. |
| Economics | Calculate an illustrative byte-price delta, assumed compute energy, and missed-event penalty break-even expression. | No economic conclusion follows without real prices, processor measurements, workload, and mission-specific missed-event costs. |

The bundle contains the full scenario, model, policy, release pin, all edge
packets, decisions, delivery events, queue drops, ground report, three-threshold
study, and a checksum manifest. Ground truth labels never enter `edge_run.json`.

## Failure semantics

- A changed model or policy, mismatched mission, or expired release pin stops
  model scoring for the affected record and requests ground review.
- Stale telemetry and low battery also stop model scoring for that record.
- The only actions are packet transmission, packet queuing, or review request;
  no action path has an actuator interface.
- Queued packets consume a finite byte budget. Full queues discard the oldest
  routine packet first and report every discard with its packet digest.
- Recorded receipts bind packet hashes in order. Verification independently
  recomputes the run and the study. Anyone able to replace the entire bundle
  and its manifest can create a new consistent bundle, so this is **not**
  cryptographic provenance, attestation, or an adversarial tamper guarantee.

## Economic interpretation

`raw_baseline_serialized_bytes` is the JSON size of all raw observations if
every one were sent. `all_packet_serialized_bytes` is the JSON size of every
summary, including ones later dropped or still pending. The difference is a
serialization comparison and does not account for communications overhead or
retransmissions. `illustrative_transport_delta_usd` multiplies that difference
in MiB by the user-supplied assumed price. Energy is an **assumption**, not a
measurement. The break-even expression divides the transport delta by the
number of missed synthetic faults, assuming an unrealistically perfect raw-data
baseline. These quantities are displayed together to expose the trade, not to
claim cost-effectiveness.

## Validation required before an operational proposal

Obtain authorized, labeled telemetry with held-out mission conditions. Specify
what events are harmful, how delayed ground contact affects them, and what raw
observations are actually retained. Measure inference latency, worst-case CPU
load, memory, power, and storage on a candidate target processor. Use a real
link and contact plan with packet overhead and retransmissions. Specify a
separate authenticated release channel, secure key lifecycle, recovery state
machine, and independent evidence collection. Run fault injection and hazard
analysis against an actual mission boundary. None of these claims is supplied
by the present demonstration.

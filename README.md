# IX-Orbital-Edge-Assurance

**Governed satellite edge-AI research demonstrator, runnable offline on a
normal computer.** A small trained classifier evaluates synthetic sensor
records. A mission-scoped model and policy pin limits when its output may be
used. The system records bounded decisions, carries summaries across a
simulated link outage, and replays every decision against ground-only truth.

This is an evaluation prototype, **not flight software**. It does not connect
to a spacecraft, train on real mission data, provide secure publisher
authentication, prove safety, or establish a cost saving.

## The question it answers

If inference moves onboard, how do you inspect the resulting trade? This
repository lets a reviewer change a decision threshold and observe **missed
faults, unnecessary alerts, serialized bytes, queue loss, and illustrative
transport assumptions in the same evidence bundle**. A default synthetic run
deliberately misses faults hidden from the model's four features. The software
records the failure rather than claiming it was solved.

## Run locally

Requires Python **3.11 or newer**. There are no runtime dependencies, network
requests, API keys, containers, or external services. From the extracted
repository directory:

```powershell
python -m orbital_assurance demo --output demo-output
python -m orbital_assurance verify demo-output
python -m unittest discover -s tests -v
```

Run another experiment without overwriting the included example:

```powershell
python -m orbital_assurance demo --output my-experiment --threshold 0.4 --queue-bytes 1200 --outage-start 8 --outage-length 18 --downlink-usd-per-mib 50
python -m orbital_assurance verify my-experiment
```

The bundled wheel can also be installed without fetching dependencies:

```powershell
python -m pip install --no-deps .\dist\ix_orbital_edge_assurance-1.0.0-py3-none-any.whl
ix-orbital-edge demo --output another-experiment
```

## What a default run shows

| Synthetic observation | Default result |
| --- | ---: |
| Records | 48 |
| True positives / false positives | 6 / 1 |
| True negatives / false negatives | 36 / 5 |
| Queue drops after the scripted outage | 6 packets |
| Difference in serialized raw vs all summary packets | About 57.41% fewer bytes |

The threshold study compares 0.4, 0.6, and 0.8: respectively 3, 5, and 6
missed synthetic faults in this scenario. These figures are **not RF savings,
real ML accuracy, measured energy, or dollars saved**. A byte-priced sensitivity
calculation is reported alongside explicit limitations, including a break-even
expression that assumes a perfect ground baseline.

## Open the evidence

`demo-output/` is a complete sample run:

| File | Purpose |
| --- | --- |
| `scenario.json` | Generated raw observations, hidden faults, and ground-only truth labels |
| `model.json` | Deterministically trained coefficients and declared feature schema |
| `policy.json`, `release_pin.json` | Allowed actions, thresholds, mission scope, expiry, and model/policy hashes |
| `edge_run.json` | Packets, decision reasons, receipt chain, contact deliveries, queue drops, and backlog |
| `ground_review.json` | Confusion counts, byte accounting, cost sensitivity, and limitations |
| `threshold_study.json` | Same records evaluated at three risk thresholds |
| `manifest.json` | File sizes and SHA-256 integrity checks; **not a signature** |

The verifier checks every file digest, recomputes each edge decision and
transport outcome, then recomputes the ground review and threshold study. The
release pin is a mismatch detector in this local experiment. A real mission
would also need authenticated publication and independent trust anchors.

## Evaluation and ownership

This repository is **source available for private, non-operational evaluation
only**, under [LICENSE](LICENSE). It is **not open source**. No commercial
profit, production use, funded customer work, real mission use, redistribution,
or IP ownership transfer is granted. A separate signed written agreement is
required for broader use or ownership. See [COMMERCIAL.md](COMMERCIAL.md) for
the contact route.

For exact boundaries, read [architecture](docs/ARCHITECTURE.md),
[validation](docs/VALIDATION.md), and [security scope](SECURITY.md).

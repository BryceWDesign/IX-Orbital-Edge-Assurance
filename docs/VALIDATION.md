# Validation record, 25 September 2026

## Commands and observed state

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -s tests -v` | 30 passed on local Python 3.12 |
| `python3 -m orbital_assurance demo --output demo-output` | Completed and self-verified |
| `python3 -m orbital_assurance verify demo-output` | Replay and bundle integrity passed |
| `python3 -m pip wheel --no-deps --no-build-isolation . -w dist` | Wheel built locally |
| Install wheel to a separate target and run demo from `/tmp` | Completed; no repository working directory required |

The suite exercises changed model and policy pins, wrong mission, expiry,
stale telemetry, low battery, invalid sensor values, prohibited actions,
outage queue pressure, capacity drops, byte accounting, missing labels in edge
packets, threshold sensitivity, altered edge packets, modified ground reports,
modified threshold studies, and repeat-run byte identity.

## Included deterministic example

The default scenario has 48 synthetic records and a 13-tick simulated outage.
The default decision threshold is 0.6. The generated evidence reports **6 true
positives, 1 false positive, 36 true negatives, and 5 false negatives** against
invented ground labels. The threshold study records 3 missed records at 0.4,
5 at 0.6, and 6 at 0.8. The store-and-forward queue drops 6 summary packets
at default byte capacity. The raw-vs-summary JSON serialization difference is
about **57.41%**, and it must not be interpreted as actual downlink throughput
or monetary saving. The source of record for exact byte counts is
`demo-output/ground_review.json`.

## Meaning of GREEN

The local release is GREEN for these deterministic software checks. GitHub
Actions is configured for Python 3.11, 3.12, and 3.13, but remote CI will run
only after the files are pushed. This record asserts no green remote checks,
flight verification, ML generalization, operational authorization, secure
provenance, actual power profile, or economic viability.

# IX-Orbital-Edge-Assurance v2.0.0 Validation Report

Date: 2026-09-25

## Executed checks

- `python -m compileall -q orbital_assurance tests` -> PASS
- `python -m unittest discover -s tests -v` -> **48 tests passed**
- `python -m orbital_assurance demo --output demo-output` -> PASS, self-verification true
- `python -m orbital_assurance verify demo-output` -> PASS
- `python -m pip wheel --no-deps --no-build-isolation . -w dist` -> PASS
- installed the built wheel to a separate target directory and ran demo + verify from `/tmp` -> PASS

## Default campaign evidence

- Records: 60 synthetic records
- ACT: 36
- ABSTAIN: 1
- DEGRADE: 2
- RETAIN: 14
- REQUEST_GROUND_REVIEW: 4
- FALLBACK: 3
- Manifest signature verified: true
- Decision signatures verified: true
- Deterministic replay verified: true
- Assurance traceability verified: true

Ground release evaluation key ID:
`9332c006c2249478a224022e06b602ee232b9603699b727784414bc71444edf9`

Runtime evaluation key ID:
`d4c59c5625b83fdeb2ddea5d890a144c102bf7c77505e908204bad1ef1bafe0f`

## Claim boundary

This validation demonstrates the repository's deterministic synthetic
evaluation contracts. It does not establish flight qualification, operational
security, hardware attestation, safety certification, spacecraft integration,
or suitability for a real mission. The included demo keys are intentionally
public/non-secret and are evaluation trust anchors only.

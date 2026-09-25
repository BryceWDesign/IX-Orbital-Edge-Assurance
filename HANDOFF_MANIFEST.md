# Handoff manifest

IX-Orbital-Edge-Assurance v2.0.0 is delivered as a standalone evaluation-only
repository. The implementation is self-contained at the application level and
does not import the donor repositories. Runtime cryptographic operations use
the third-party `cryptography` Python package declared in `pyproject.toml` and
`requirements.txt`.

Core release surfaces:

- `orbital_assurance/authority.py` - signed mission authority
- `orbital_assurance/qualification.py` - uncertainty and drift qualification
- `orbital_assurance/runtime.py` - six-state governed runtime, retention,
  transport, signed receipts, replay audit
- `orbital_assurance/signing.py` - Ed25519 signing and verification
- `orbital_assurance/assurance.py` - mission/hazard/requirement/claim evidence graph
- `orbital_assurance/bundle.py` - signed evidence package generation/verification
- `tests/` - behavioral, cryptographic, adversarial, and reproducibility checks
- `demo-output/` - fully generated signed reference run

Claims remain bounded to synthetic terrestrial evaluation as documented in
README, SECURITY, and docs/VALIDATION.

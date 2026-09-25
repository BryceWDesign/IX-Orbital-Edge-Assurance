# Security scope

This research release makes no secure-update or authenticated-publisher claim.
SHA-256 pins identify a model and policy relative to a supplied local release;
the manifest and receipt chain catch inconsistency within an evidence bundle.
An adversary who can replace the entire release or bundle can replace the pins
and manifest. Real operations require an independently trusted signing key,
protected update transport, recovery procedure, and mission-specific review.

No secrets, credentials, external services, or spacecraft control interfaces
are included. Do not connect the demonstration to a spacecraft or a real
mission workflow. For private vulnerability reports, contact the owner using
the contact route in [COMMERCIAL.md](COMMERCIAL.md).

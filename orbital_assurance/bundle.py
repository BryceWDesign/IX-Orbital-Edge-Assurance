"""Evidence bundle creation, signed manifest, assurance case, and deterministic verification."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .assurance import build_assurance_case, verify_assurance_case
from .authority import issue_authority
from .core import canonical, policy as new_policy, require, train
from .runtime import audit, simulate, verify_receipts
from .scenario import generate
from .signing import deterministic_demo_identity, sign_payload, verify_signature

FILES = (
    "scenario.json",
    "model.json",
    "policy.json",
    "mission_authority.json",
    "edge_run.json",
    "assurance_case.json",
    "ground_review.json",
)


def _write(path: Path, value: Any) -> tuple[int, str]:
    raw = canonical(value) + b"\n"
    path.write_bytes(raw)
    return len(raw), hashlib.sha256(raw).hexdigest()


def make_bundle(output: Path, *, count: int = 60, seed: int = 991,
                threshold: float = 0.6, queue_bytes: int = 6500,
                outage_start: int = 10, outage_length: int = 16,
                downlink: float = 25.0, energy: float = 12.0) -> dict[str, Any]:
    require(all(math.isfinite(x) and x >= 0 for x in (downlink, energy)), "invalid pricing or energy")
    scenario = generate(count=count, seed=seed, outage_start=outage_start, outage_length=outage_length)
    model = train()
    rules = new_policy(threshold=threshold, queue_bytes=queue_bytes)
    ground = deterministic_demo_identity("ground-release-evaluation")
    runtime = deterministic_demo_identity("orbital-edge-runtime-evaluation")
    authority = issue_authority(
        mission=scenario["mission"], model=model, policy=rules,
        signer=ground, expires_at=count - 1,
    )
    edge = simulate(scenario, model, rules, authority, runtime)
    assurance = build_assurance_case(edge)
    report = audit(
        scenario, model, rules, authority, edge, runtime,
        downlink_usd_per_mib=downlink, inference_mj_per_record=energy,
    )
    items = dict(zip(FILES, (scenario, model, rules, authority, edge, assurance, report)))
    output.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "schema": "oea.bundle.manifest.v2",
        "authentication": "Ed25519_signed_manifest_and_decision_receipts",
        "evaluation_only": True,
        "files": {},
        "ground_release_identity": ground.descriptor(),
        "runtime_identity": runtime.descriptor(),
        "replay_command": "python -m orbital_assurance verify BUNDLE_DIRECTORY",
    }
    for name, data in items.items():
        size, sha = _write(output / name, data)
        manifest["files"][name] = {"sha256": sha, "bytes": size}
    _write(output / "manifest.json", manifest)
    _write(output / "manifest_signature.json", sign_payload(ground, manifest))
    return report


def verify_bundle(path: Path) -> dict[str, Any]:
    manifest_raw = (path / "manifest.json").read_bytes()
    signature_raw = (path / "manifest_signature.json").read_bytes()
    manifest = json.loads(manifest_raw)
    manifest_signature = json.loads(signature_raw)
    require(canonical(manifest) + b"\n" == manifest_raw, "noncanonical manifest")
    require(canonical(manifest_signature) + b"\n" == signature_raw, "noncanonical manifest signature")
    require(manifest.get("schema") == "oea.bundle.manifest.v2", "unknown manifest")
    require(manifest.get("authentication") == "Ed25519_signed_manifest_and_decision_receipts", "unrecognized authentication mode")
    require(manifest.get("evaluation_only") is True, "evaluation-only manifest contract missing")
    verify_signature(manifest, manifest_signature)
    require(manifest_signature["key_id"] == manifest["ground_release_identity"]["key_id"], "manifest signer does not match release identity")
    require(set(manifest.get("files", {})) == set(FILES), "unexpected manifest file set")

    values: dict[str, Any] = {}
    for name in FILES:
        raw = (path / name).read_bytes()
        entry = manifest["files"][name]
        require(len(raw) == entry["bytes"] and hashlib.sha256(raw).hexdigest() == entry["sha256"], f"integrity mismatch: {name}")
        values[name] = json.loads(raw)
        require(canonical(values[name]) + b"\n" == raw, f"noncanonical artifact: {name}")

    scenario, model, rules, authority, edge, assurance, report = (values[x] for x in FILES)
    require(authority["signature"]["key_id"] == manifest["ground_release_identity"]["key_id"], "authority signer mismatch")
    require(edge["runtime_identity"]["key_id"] == manifest["runtime_identity"]["key_id"], "runtime signer mismatch")
    verify_receipts(edge)

    # The included reproducible evaluation bundle uses deterministic non-secret demo
    # identities. Replay reproduces complete signed evidence byte-for-byte.
    runtime = deterministic_demo_identity("orbital-edge-runtime-evaluation")
    expected_edge = simulate(scenario, model, rules, authority, runtime)
    require(edge == expected_edge, "edge execution mismatch")
    verify_assurance_case(assurance, edge)
    expected_report = audit(
        scenario, model, rules, authority, edge, runtime,
        downlink_usd_per_mib=report["assumptions"]["downlink_usd_per_mib"],
        inference_mj_per_record=report["assumptions"]["inference_mj_per_record"],
    )
    require(report == expected_report, "ground review mismatch")
    return {
        "verified": True,
        "records": report["records"],
        "authentication": "Ed25519",
        "manifest_signature_verified": True,
        "decision_signatures_verified": True,
        "deterministic_replay_verified": True,
        "assurance_traceability_verified": True,
        "runtime_key_id": manifest["runtime_identity"]["key_id"],
        "ground_release_key_id": manifest["ground_release_identity"]["key_id"],
        "report": report,
    }

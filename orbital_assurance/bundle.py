"""Evidence bundle creation and independent deterministic replay verification."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .core import canonical, policy as new_policy, release, require, train
from .runtime import audit, simulate
from .scenario import generate

FILES = ("scenario.json", "model.json", "policy.json", "release_pin.json",
         "edge_run.json", "ground_review.json", "threshold_study.json")


def studies(scenario: dict[str, Any], model: dict[str, Any],
            policy: dict[str, Any], *, downlink: float, energy: float) -> list[dict[str, Any]]:
    outputs = []
    for threshold in (0.4, 0.6, 0.8):
        variant = {**policy, "threshold": threshold}
        pin = release(model, variant, mission=scenario["mission"], expires_at=len(scenario["records"]) - 1)
        result = audit(scenario, model, variant, pin, simulate(scenario, model, variant, pin),
                       downlink_usd_per_mib=downlink, inference_mj_per_record=energy)
        outputs.append({"threshold": threshold, "confusion": result["confusion"],
                        "all_packet_serialized_bytes": result["all_packet_serialized_bytes"],
                        "dropped_packets": result["dropped_packets"],
                        "illustrative_transport_delta_usd": result["illustrative_transport_delta_usd"]})
    return outputs


def make_bundle(output: Path, *, count: int = 48, seed: int = 991,
                threshold: float = 0.6, queue_bytes: int = 2800,
                outage_start: int = 10, outage_length: int = 13,
                downlink: float = 25.0, energy: float = 12.0) -> dict[str, Any]:
    require(all(math.isfinite(x) and x >= 0 for x in (downlink, energy)), "invalid pricing or energy")
    scenario = generate(count=count, seed=seed, outage_start=outage_start,
                        outage_length=outage_length)
    model = train()
    rules = new_policy(threshold=threshold, queue_bytes=queue_bytes)
    pin = release(model, rules, mission=scenario["mission"], expires_at=count - 1)
    edge = simulate(scenario, model, rules, pin)
    report = audit(scenario, model, rules, pin, edge,
                   downlink_usd_per_mib=downlink, inference_mj_per_record=energy)
    sweep = studies(scenario, model, rules, downlink=downlink, energy=energy)
    items = dict(zip(FILES, (scenario, model, rules, pin, edge, report, sweep)))
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": "oea.bundle.manifest.v1", "authentication": "none_hash_integrity_only",
                "files": {}, "replay_command": "python -m orbital_assurance verify BUNDLE_DIRECTORY"}
    for name, data in items.items():
        payload = canonical(data) + b"\n"
        (output / name).write_bytes(payload)
        manifest["files"][name] = {"sha256": hashlib.sha256(payload).hexdigest(),
                                    "bytes": len(payload)}
    (output / "manifest.json").write_bytes(canonical(manifest) + b"\n")
    return report


def verify_bundle(path: Path) -> dict[str, Any]:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    require(manifest.get("schema") == "oea.bundle.manifest.v1", "unknown manifest")
    require(manifest.get("authentication") == "none_hash_integrity_only", "unrecognized authenticity assertion")
    require(set(manifest.get("files", {})) == set(FILES), "unexpected manifest file set")
    values = {}
    for name in FILES:
        raw = (path / name).read_bytes()
        entry = manifest["files"][name]
        require(len(raw) == entry["bytes"] and hashlib.sha256(raw).hexdigest() == entry["sha256"],
                f"integrity mismatch: {name}")
        values[name] = json.loads(raw)
        require(canonical(values[name]) + b"\n" == raw, f"noncanonical artifact: {name}")
    scenario, model, rules, pin = (values[x] for x in FILES[:4])
    edge, report, sweep = (values[x] for x in FILES[4:])
    require(edge == simulate(scenario, model, rules, pin), "edge execution mismatch")
    expected = audit(scenario, model, rules, pin, edge,
                     downlink_usd_per_mib=report["assumptions"]["downlink_usd_per_mib"],
                     inference_mj_per_record=report["assumptions"]["inference_mj_per_record"])
    require(report == expected, "ground review mismatch")
    require(sweep == studies(scenario, model, rules,
                             downlink=report["assumptions"]["downlink_usd_per_mib"],
                             energy=report["assumptions"]["inference_mj_per_record"]),
            "threshold study mismatch")
    return {"verified": True, "records": report["records"],
            "level": "deterministic_replay_and_file_integrity_only",
            "authenticity_verified": False, "report": report}

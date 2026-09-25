"""Governed edge-AI mission-assurance runtime and deterministic replay."""
from __future__ import annotations

from typing import Any

from .authority import validate_authority
from .core import canonical, digest, predict, require, strip_truth, validate_model, validate_observation, validate_policy
from .qualification import drift_score, qualification_state, uncertainty
from .signing import SigningIdentity, sign_payload, verify_signature


def _size(value: dict[str, Any]) -> int:
    return len(canonical(value))


def _priority(decision: str, risk_flagged: bool) -> str:
    if decision == "FALLBACK":
        return "P0"
    if decision == "REQUEST_GROUND_REVIEW" or risk_flagged:
        return "P1"
    if decision in ("ABSTAIN", "DEGRADE"):
        return "P2"
    if decision == "RETAIN":
        return "P3"
    return "P4"


def _receipt_body(decision: dict[str, Any], previous_sha256: str) -> dict[str, Any]:
    return {
        "schema": "oea.decision.receipt.v2",
        "tick": decision["tick"],
        "decision_sha256": digest(decision),
        "previous_sha256": previous_sha256,
        "traceability": decision["traceability"],
    }


def simulate(scenario: dict[str, Any], model: dict[str, Any], policy: dict[str, Any],
             authority: dict[str, Any], runtime_signer: SigningIdentity) -> dict[str, Any]:
    validate_model(model)
    validate_policy(policy)
    require(scenario.get("schema") == "oea.synthetic.scenario.v2", "unknown scenario")
    require(scenario.get("labels_are_synthetic") is True, "unverified scenario label type")
    mission = scenario.get("mission")
    require(isinstance(mission, str) and bool(mission), "missing mission")
    rows = scenario.get("records")
    require(isinstance(rows, list) and bool(rows), "missing records")

    decisions: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    retained_evidence: list[dict[str, Any]] = []
    delivered: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    queue: list[dict[str, Any]] = []
    prev_hash = "0" * 64
    model_hash = digest(model)
    policy_hash = digest(policy)

    for idx, row in enumerate(rows):
        require(isinstance(row, dict), "invalid row")
        observation = strip_truth(row)
        validate_observation(observation)
        tick = observation["tick"]
        require(tick == idx, "ticks must be contiguous")
        phase = observation["mission_phase"]
        authorized, authority_reason = validate_authority(
            authority, mission=mission, model=model, policy=policy, tick=tick,
            phase=phase, decision_class="telemetry_triage",
        )
        link_ok = observation["link_quality"] >= policy["minimum_link_quality"]
        battery_ok = observation["battery_percent"] >= policy["battery_fallback_percent"]
        sensor_ok = observation["sensor_quality"] >= policy["minimum_sensor_quality"]
        fresh = observation["telemetry_fresh"]

        score: float | None = None
        u: float | None = None
        drift: float = drift_score(observation)
        qstate = "unqualified"
        reason = ""
        decision = "FALLBACK"
        retain_raw = True
        review = True
        fallback = True

        if not authorized:
            reason = authority_reason
        elif not battery_ok:
            reason = "battery_below_fallback_floor"
        elif not fresh:
            decision, reason, fallback = "REQUEST_GROUND_REVIEW", "telemetry_stale", False
        elif not sensor_ok:
            decision, reason, fallback = "REQUEST_GROUND_REVIEW", "sensor_quality_below_floor", False
        else:
            score = round(predict(model, observation), 6)
            u = uncertainty(score)
            qstate = qualification_state(score=score, drift=drift, policy=policy)
            if qstate == "fallback":
                decision, reason = "FALLBACK", "distribution_shift_exceeds_fallback_limit"
            elif qstate == "degraded":
                decision, reason, fallback = "DEGRADE", "distribution_shift_requires_reduced_authority", False
            elif qstate == "review":
                decision, reason, fallback = "REQUEST_GROUND_REVIEW", "uncertainty_requires_ground_review", False
            elif qstate == "abstain":
                decision, reason, fallback, review = "ABSTAIN", "uncertainty_requires_abstention", False, False
            elif not link_ok:
                decision, reason, fallback, review = "RETAIN", "contact_unavailable_retain_evidence", False, score >= policy["risk_threshold"]
            else:
                decision, reason, fallback, retain_raw = "ACT", "qualified_within_authority", False, score >= policy["risk_threshold"]
                review = score >= policy["risk_threshold"]

        require(decision in policy["allowed_authority_decisions"], "unapproved authority decision")
        risk_flagged = bool(score is not None and score >= policy["risk_threshold"])
        if decision in ("ABSTAIN", "DEGRADE", "REQUEST_GROUND_REVIEW", "FALLBACK"):
            retain_raw = True
        if decision in ("DEGRADE", "REQUEST_GROUND_REVIEW", "FALLBACK"):
            review = True

        trace = ["MN-001", "REQ-AUTH-001", "REQ-CRYPTO-006"]
        if drift >= 0:
            trace.append("REQ-DRIFT-002")
        if retain_raw:
            trace.append("REQ-RETAIN-003")
        if review:
            trace.append("REQ-REVIEW-004")
        if fallback:
            trace.append("REQ-FALLBACK-005")

        core_decision: dict[str, Any] = {
            "schema": "oea.edge.decision.v2",
            "tick": tick,
            "mission_phase": phase,
            "decision_class": "telemetry_triage",
            "authority_decision": decision,
            "reason": reason,
            "score": score,
            "uncertainty": u,
            "drift_score": drift,
            "qualification_state": qstate,
            "risk_flagged": risk_flagged,
            "retain_raw": retain_raw,
            "ground_review_required": review,
            "fallback_active": fallback,
            "priority": _priority(decision, risk_flagged),
            "raw_sha256": digest(observation),
            "model_sha256": model_hash,
            "policy_sha256": policy_hash,
            "authority_sha256": digest(authority),
            "traceability": trace,
        }
        body = _receipt_body(core_decision, prev_hash)
        sig = sign_payload(runtime_signer, body)
        receipt = {**body, "signature": sig}
        receipt_hash = digest(receipt)
        receipt["receipt_sha256"] = receipt_hash
        prev_hash = receipt_hash
        decisions.append({**core_decision, "receipt_sha256": receipt_hash})
        receipts.append(receipt)

        if retain_raw:
            retained_evidence.append({
                "tick": tick,
                "raw_sha256": core_decision["raw_sha256"],
                "reason": reason,
                "priority": core_decision["priority"],
                "receipt_sha256": receipt_hash,
            })

        packet = {
            "tick": tick,
            "decision": decision,
            "priority": core_decision["priority"],
            "review_required": review,
            "receipt_sha256": receipt_hash,
            "raw_retained": retain_raw,
        }
        packet_hash = digest(packet)
        queued = {
            "tick": tick,
            "packet_sha256": packet_hash,
            "priority": core_decision["priority"],
            "bytes": _size(packet),
            "receipt_sha256": receipt_hash,
        }
        budget = policy["contact_budget_bytes"] if link_ok else 0
        if link_ok:
            rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4, "P5": 5}
            for item in sorted(queue[:], key=lambda x: (rank[x["priority"]], x["tick"])):
                if item["bytes"] <= budget:
                    budget -= item["bytes"]
                    delivered.append({"tick": item["tick"], "at_tick": tick, **{k: item[k] for k in ("packet_sha256", "bytes", "priority", "receipt_sha256")}})
                    queue.remove(item)
        if link_ok and queued["bytes"] <= budget:
            delivered.append({"tick": tick, "at_tick": tick, **{k: queued[k] for k in ("packet_sha256", "bytes", "priority", "receipt_sha256")}})
        else:
            queue.append(queued)

        rank_drop = {"P4": 0, "P3": 1, "P2": 2, "P1": 3, "P0": 4}
        while sum(x["bytes"] for x in queue) > policy["queue_capacity_bytes"]:
            victim = min(queue, key=lambda x: (rank_drop[x["priority"]], x["tick"]))
            queue.remove(victim)
            dropped.append({"tick": victim["tick"], "at_tick": tick,
                            "packet_sha256": victim["packet_sha256"], "bytes": victim["bytes"],
                            "priority": victim["priority"], "receipt_sha256": victim["receipt_sha256"],
                            "reason": "queue_capacity"})

    return {
        "schema": "oea.edge.run.v2",
        "mission": mission,
        "authority_sha256": digest(authority),
        "runtime_identity": runtime_signer.descriptor(),
        "decisions": decisions,
        "receipts": receipts,
        "retained_evidence": retained_evidence,
        "delivered": delivered,
        "dropped": dropped,
        "pending": sorted(queue, key=lambda x: x["tick"]),
        "final_receipt_sha256": prev_hash,
    }


def verify_receipts(edge: dict[str, Any]) -> bool:
    decisions = edge["decisions"]
    receipts = edge["receipts"]
    require(len(decisions) == len(receipts), "decision/receipt cardinality mismatch")
    previous = "0" * 64
    for decision, receipt in zip(decisions, receipts):
        decision_core = {k: v for k, v in decision.items() if k != "receipt_sha256"}
        expected_body = _receipt_body(decision_core, previous)
        body = {k: receipt[k] for k in ("schema", "tick", "decision_sha256", "previous_sha256", "traceability")}
        require(body == expected_body, "decision receipt body mismatch")
        verify_signature(body, receipt["signature"])
        computed = digest({**body, "signature": receipt["signature"]})
        require(computed == receipt["receipt_sha256"] == decision["receipt_sha256"], "decision receipt hash mismatch")
        previous = computed
    require(previous == edge["final_receipt_sha256"], "final receipt mismatch")
    return True


def audit(scenario: dict[str, Any], model: dict[str, Any], policy: dict[str, Any],
          authority: dict[str, Any], edge: dict[str, Any], runtime_signer: SigningIdentity,
          *, downlink_usd_per_mib: float = 25.0,
          inference_mj_per_record: float = 12.0) -> dict[str, Any]:
    require(downlink_usd_per_mib >= 0 and inference_mj_per_record >= 0, "invalid assumptions")
    expected = simulate(scenario, model, policy, authority, runtime_signer)
    require(edge == expected, "edge replay mismatch; bundle rejected")
    verify_receipts(edge)
    rows = scenario["records"]
    confusion = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    decision_counts: dict[str, int] = {}
    for row, decision in zip(rows, edge["decisions"]):
        flagged = decision["risk_flagged"] or decision["ground_review_required"]
        actual = row["synthetic_truth"]
        require(type(actual) is bool, "invalid ground label")
        category = "tp" if flagged and actual else "fp" if flagged else "fn" if actual else "tn"
        confusion[category] += 1
        d = decision["authority_decision"]
        decision_counts[d] = decision_counts.get(d, 0) + 1
    raw_bytes = sum(len(canonical(strip_truth(row))) for row in rows)
    packet_bytes = sum(item["bytes"] for item in edge["delivered"] + edge["pending"] + edge["dropped"])
    inference_count = sum(d["score"] is not None for d in edge["decisions"])
    transport_delta = (raw_bytes - packet_bytes) / (1024 * 1024) * downlink_usd_per_mib
    return {
        "schema": "oea.ground.review.v2",
        "evidence_level": "synthetic_ground_evaluation_with_ed25519_attribution",
        "mission": scenario["mission"],
        "records": len(rows),
        "confusion": confusion,
        "authority_decision_counts": decision_counts,
        "signed_receipts_verified": True,
        "retained_raw_evidence_count": len(edge["retained_evidence"]),
        "raw_baseline_serialized_bytes": raw_bytes,
        "transport_packet_bytes": packet_bytes,
        "inferences_executed": inference_count,
        "illustrative_transport_delta_usd": round(transport_delta, 8),
        "assumed_compute_energy_j": round(inference_count * inference_mj_per_record / 1000, 6),
        "assumptions": {
            "downlink_usd_per_mib": downlink_usd_per_mib,
            "inference_mj_per_record": inference_mj_per_record,
            "processor_power_measured": False,
        },
        "limitations": [
            "All mission records, labels, outages, drift events, and cost inputs are synthetic or assumed.",
            "Ed25519 signatures prove possession of the bundled evaluation key, not legal identity or hardware-rooted provenance.",
            "Bundled demo private keys are deterministic and intentionally non-secret; they are not operational trust anchors.",
            "No spacecraft bus, flight processor, RF stack, command path, hardware-in-the-loop bench, or orbital mission is connected.",
            "This release evaluates governance and evidence behavior; it does not establish flight qualification, safety certification, or mission suitability.",
        ],
        "decision": "mission_assurance_control_plane_behavior_demonstrated_in_synthetic_evaluation",
    }

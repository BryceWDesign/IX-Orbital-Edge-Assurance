"""Assurance-case traceability generated from executable evidence."""
from __future__ import annotations

from typing import Any

from .core import digest, require


def build_assurance_case(edge: dict[str, Any]) -> dict[str, Any]:
    decisions = edge["decisions"]
    counts: dict[str, int] = {}
    for item in decisions:
        counts[item["authority_decision"]] = counts.get(item["authority_decision"], 0) + 1

    requirement_evidence = {
        "REQ-AUTH-001": [d["receipt_sha256"] for d in decisions],
        "REQ-DRIFT-002": [d["receipt_sha256"] for d in decisions if d["drift_score"] >= 0],
        "REQ-RETAIN-003": [d["receipt_sha256"] for d in decisions if d["retain_raw"]],
        "REQ-REVIEW-004": [d["receipt_sha256"] for d in decisions if d["ground_review_required"]],
        "REQ-FALLBACK-005": [d["receipt_sha256"] for d in decisions if d["authority_decision"] == "FALLBACK"],
        "REQ-CRYPTO-006": [d["receipt_sha256"] for d in decisions],
    }
    requirements = [
        {"id": "REQ-AUTH-001", "hazard": "HZ-UNAUTHORIZED-AI", "text": "Every AI-mediated decision shall be checked against signed mission authority."},
        {"id": "REQ-DRIFT-002", "hazard": "HZ-OOD-AI", "text": "Runtime shall detect declared distribution shift and reduce authority at configured thresholds."},
        {"id": "REQ-RETAIN-003", "hazard": "HZ-EVIDENCE-LOSS", "text": "Evidence requiring later review shall retain raw observation integrity references."},
        {"id": "REQ-REVIEW-004", "hazard": "HZ-AMBIGUOUS-AI", "text": "Ambiguous or degraded decisions shall be escalated for ground review."},
        {"id": "REQ-FALLBACK-005", "hazard": "HZ-UNSAFE-AUTONOMY", "text": "Invalid authority or severe qualification failure shall enter deterministic fallback."},
        {"id": "REQ-CRYPTO-006", "hazard": "HZ-PROVENANCE", "text": "Each decision shall carry a verifiable Ed25519 runtime signature and receipt-chain link."},
    ]
    claims = []
    for req in requirements:
        refs = requirement_evidence[req["id"]]
        claims.append({
            "claim_id": "CLM-" + req["id"].split("-", 1)[1],
            "requirement_id": req["id"],
            "status": "supported" if refs else "not_exercised",
            "evidence_receipts": refs,
        })
    body = {
        "schema": "oea.assurance.case.v2",
        "mission": edge["mission"],
        "mission_need": {"id": "MN-001", "text": "Bound spacecraft edge AI with reviewable mission authority and evidence."},
        "hazards": [
            {"id": "HZ-UNAUTHORIZED-AI", "text": "AI output used outside approved scope."},
            {"id": "HZ-OOD-AI", "text": "Model acts under distribution shift."},
            {"id": "HZ-EVIDENCE-LOSS", "text": "Decision evidence is lost during contact outage."},
            {"id": "HZ-AMBIGUOUS-AI", "text": "Uncertain inference is treated as authoritative."},
            {"id": "HZ-UNSAFE-AUTONOMY", "text": "Autonomy continues after a safety/qualification gate fails."},
            {"id": "HZ-PROVENANCE", "text": "Decision provenance cannot be cryptographically verified."},
        ],
        "requirements": requirements,
        "claims": claims,
        "decision_counts": counts,
        "final_receipt_sha256": edge["final_receipt_sha256"],
    }
    body["case_sha256"] = digest(body)
    return body


def verify_assurance_case(case: dict[str, Any], edge: dict[str, Any]) -> bool:
    expected = build_assurance_case(edge)
    require(case == expected, "assurance case mismatch")
    receipt_set = {d["receipt_sha256"] for d in edge["decisions"]}
    for claim in case["claims"]:
        require(set(claim["evidence_receipts"]).issubset(receipt_set), "unknown assurance evidence")
    return True

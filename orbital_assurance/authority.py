"""Mission-scoped authority and signed release contracts."""
from __future__ import annotations

from typing import Any

from cryptography.exceptions import InvalidSignature

from .core import digest, require
from .signing import SigningIdentity, sign_payload, verify_signature

DECISION_CLASSES = (
    "telemetry_triage",
    "anomaly_priority",
    "downlink_selection",
)
DENIED_CONTROL_CLASSES = (
    "attitude_control",
    "propulsion",
    "payload_shutdown",
    "thermal_override",
)


def issue_authority(*, mission: str, model: dict[str, Any], policy: dict[str, Any],
                    signer: SigningIdentity, expires_at: int) -> dict[str, Any]:
    require(bool(mission) and expires_at >= 0, "invalid authority scope")
    body: dict[str, Any] = {
        "schema": "oea.mission.authority.v2",
        "mission": mission,
        "issuer": signer.name,
        "subject": "orbital-edge-runtime",
        "valid_from_tick": 0,
        "expires_after_tick": expires_at,
        "model_sha256": digest(model),
        "policy_sha256": digest(policy),
        "permitted_decision_classes": list(DECISION_CLASSES),
        "permitted_mission_phases": ["nominal", "eclipse", "contact", "outage"],
        "explicitly_denied_control_classes": list(DENIED_CONTROL_CLASSES),
        "operational_use": False,
        "evaluation_only": True,
    }
    return {**body, "signature": sign_payload(signer, body)}


def authority_body(authority: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in authority.items() if k != "signature"}


def validate_authority(authority: dict[str, Any], *, mission: str,
                       model: dict[str, Any], policy: dict[str, Any], tick: int,
                       phase: str, decision_class: str) -> tuple[bool, str]:
    try:
        require(authority.get("schema") == "oea.mission.authority.v2", "authority_schema")
        require(authority.get("evaluation_only") is True and authority.get("operational_use") is False,
                "authority_mode")
        verify_signature(authority_body(authority), authority["signature"])
        require(authority.get("mission") == mission, "mission_scope")
        require(authority.get("model_sha256") == digest(model), "model_scope")
        require(authority.get("policy_sha256") == digest(policy), "policy_scope")
        require(type(authority.get("valid_from_tick")) is int and
                type(authority.get("expires_after_tick")) is int and
                authority["valid_from_tick"] <= tick <= authority["expires_after_tick"], "time_scope")
        require(phase in authority.get("permitted_mission_phases", []), "phase_scope")
        require(decision_class in authority.get("permitted_decision_classes", []), "decision_scope")
        require(set(authority.get("explicitly_denied_control_classes", [])) == set(DENIED_CONTROL_CLASSES),
                "denied_control_contract")
        return True, "authorized"
    except (ValueError, KeyError, TypeError, InvalidSignature):
        return False, "authority_invalid_or_out_of_scope"

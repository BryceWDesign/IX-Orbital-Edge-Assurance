"""Deterministic model, policy, and input contracts; no flight interfaces."""
from __future__ import annotations

import hashlib
import json
import math
import random
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


FEATURES = ("temperature", "vibration", "current", "battery")


def features(observation: dict[str, Any]) -> tuple[float, ...]:
    values = (
        (observation["temperature_c"] - 20.0) / 12.0,
        observation["vibration_g"] / 0.8,
        (observation["current_a"] - 2.0) / 2.0,
        (observation["battery_percent"] - 50.0) / 50.0,
    )
    require(all(math.isfinite(v) for v in values), "nonfinite sensor input")
    return values


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    exp = math.exp(x)
    return exp / (1.0 + exp)


def predict(model: dict[str, Any], observation: dict[str, Any]) -> float:
    validate_model(model)
    score = model["bias"] + sum(w * x for w, x in zip(model["weights"], features(observation)))
    return _sigmoid(score)


def validate_model(model: dict[str, Any]) -> None:
    require(model.get("kind") == "synthetic_logistic_v1", "unsupported model")
    require(model.get("feature_schema") == list(FEATURES), "feature schema mismatch")
    weights = model.get("weights")
    require(isinstance(weights, list) and len(weights) == len(FEATURES), "invalid weights")
    require(all(type(x) is float and math.isfinite(x) for x in weights), "nonfinite weights")
    require(type(model.get("bias")) is float and math.isfinite(model["bias"]), "invalid bias")


def train(*, seed: int = 403, count: int = 360) -> dict[str, Any]:
    """Train only on generated examples; hidden fault class is held out entirely."""
    require(count >= 50, "insufficient generated training examples")
    rng = random.Random(seed)
    weights = [0.0] * len(FEATURES)
    bias = 0.0
    examples: list[tuple[tuple[float, ...], float]] = []
    for i in range(count):
        known_fault = i % 4 == 0
        obs = {
            "temperature_c": 20 + rng.uniform(-2, 2) + (12 if known_fault else 0),
            "vibration_g": 0.08 + rng.uniform(0, 0.09) + (0.43 if known_fault else 0),
            "current_a": 2 + rng.uniform(-0.3, 0.3) + (0.9 if known_fault else 0),
            "battery_percent": 45 + rng.uniform(0, 45),
        }
        examples.append((features(obs), float(known_fault)))
    for _ in range(260):
        for vector, label in examples:
            error = _sigmoid(bias + sum(a * b for a, b in zip(weights, vector))) - label
            for j, value in enumerate(vector):
                weights[j] -= 0.065 * (error * value + 0.0002 * weights[j])
            bias -= 0.065 * error
    model = {
        "kind": "synthetic_logistic_v1",
        "feature_schema": list(FEATURES),
        "weights": [round(x, 9) for x in weights],
        "bias": round(bias, 9),
        "training_seed": seed,
        "training_count": count,
        "training_data": "generated_synthetic_only",
    }
    validate_model(model)
    return model


def policy(*, threshold: float = 0.6, queue_bytes: int = 6500) -> dict[str, Any]:
    result = {
        "schema": "oea.policy.v2",
        "risk_threshold": float(threshold),
        "battery_fallback_percent": 15.0,
        "minimum_link_quality": 0.35,
        "minimum_sensor_quality": 0.50,
        "uncertainty_abstain": 0.30,
        "uncertainty_review": 0.78,
        "drift_degrade": 1.65,
        "drift_fallback": 2.85,
        "queue_capacity_bytes": int(queue_bytes),
        "contact_budget_bytes": 2700,
        "allowed_authority_decisions": ["ACT", "ABSTAIN", "DEGRADE", "RETAIN", "REQUEST_GROUND_REVIEW", "FALLBACK"],
        "physical_control_commands_enabled": False,
        "evaluation_only": True,
    }
    validate_policy(result)
    return result


def validate_policy(value: dict[str, Any]) -> None:
    require(value.get("schema") == "oea.policy.v2", "unsupported policy")
    require(type(value.get("risk_threshold")) is float and 0 < value["risk_threshold"] < 1, "invalid risk threshold")
    require(value.get("physical_control_commands_enabled") is False, "physical control commands prohibited")
    require(value.get("evaluation_only") is True, "evaluation-only contract missing")
    require(value.get("allowed_authority_decisions") == ["ACT", "ABSTAIN", "DEGRADE", "RETAIN", "REQUEST_GROUND_REVIEW", "FALLBACK"], "authority decision list mismatch")
    for key in ("queue_capacity_bytes", "contact_budget_bytes"):
        require(type(value.get(key)) is int and value[key] >= 512, f"invalid {key}")
    for key in ("battery_fallback_percent", "minimum_link_quality", "minimum_sensor_quality", "uncertainty_abstain", "uncertainty_review"):
        x = value.get(key)
        require(type(x) is float and 0 <= x <= 100 if key == "battery_fallback_percent" else type(x) is float and 0 <= x <= 1, f"invalid {key}")
    require(0 <= value["uncertainty_abstain"] < value["uncertainty_review"] <= 1, "uncertainty thresholds invalid")
    require(type(value.get("drift_degrade")) is float and type(value.get("drift_fallback")) is float and 0 < value["drift_degrade"] < value["drift_fallback"], "drift thresholds invalid")


def validate_observation(obs: dict[str, Any]) -> None:
    require(type(obs.get("tick")) is int and obs["tick"] >= 0, "invalid tick")
    for key, lo, hi in (("temperature_c", -70, 150), ("vibration_g", 0, 40),
                        ("current_a", -50, 50), ("battery_percent", 0, 100),
                        ("link_quality", 0, 1), ("sensor_quality", 0, 1)):
        x = obs.get(key)
        require(type(x) in (float, int) and math.isfinite(x) and lo <= x <= hi, f"invalid {key}")
    require(type(obs.get("telemetry_fresh")) is bool, "invalid freshness")
    require(obs.get("mission_phase") in ("nominal", "eclipse", "contact", "outage"), "invalid mission phase")
    wave = obs.get("waveform")
    require(isinstance(wave, list) and len(wave) == 80, "invalid waveform length")
    require(all(type(x) is float and math.isfinite(x) and -2 <= x <= 2 for x in wave), "invalid waveform")


def strip_truth(row: dict[str, Any]) -> dict[str, Any]:
    """No synthetic truth metadata crosses the edge inference boundary."""
    return {key: val for key, val in row.items() if key not in ("synthetic_truth", "fault_class", "injected_condition")}

"""Deterministic model, release, and input contracts; no flight interfaces."""

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


def policy(*, threshold: float = 0.6, queue_bytes: int = 2800) -> dict[str, Any]:
    result = {
        "schema": "oea.policy.v1",
        "threshold": threshold,
        "battery_floor_percent": 12.0,
        "minimum_link_quality": 0.35,
        "queue_capacity_bytes": queue_bytes,
        "contact_budget_bytes": 1700,
        "allowed_actions": ["send_priority", "send_summary", "queue_priority", "queue_summary", "hold_raw_for_review"],
        "control_commands_enabled": False,
    }
    validate_policy(result)
    return result


def validate_policy(value: dict[str, Any]) -> None:
    require(value.get("schema") == "oea.policy.v1", "unsupported policy")
    require(type(value.get("threshold")) is float and 0 < value["threshold"] < 1, "invalid threshold")
    require(value.get("control_commands_enabled") is False, "control commands prohibited")
    require(value.get("allowed_actions") == ["send_priority", "send_summary", "queue_priority", "queue_summary", "hold_raw_for_review"], "action list mismatch")
    for key in ("queue_capacity_bytes", "contact_budget_bytes"):
        require(type(value.get(key)) is int and value[key] >= 512, f"invalid {key}")
    require(type(value.get("battery_floor_percent")) is float and 0 <= value["battery_floor_percent"] <= 100,
            "invalid battery floor")
    require(type(value.get("minimum_link_quality")) is float and 0 <= value["minimum_link_quality"] <= 1,
            "invalid link threshold")


def release(model: dict[str, Any], rules: dict[str, Any], *, mission: str, expires_at: int) -> dict[str, Any]:
    require(bool(mission) and expires_at >= 0, "invalid release scope")
    validate_model(model)
    validate_policy(rules)
    return {"schema": "oea.release.pin.v1", "mission": mission, "model_sha256": digest(model),
            "policy_sha256": digest(rules), "expires_after_tick": expires_at,
            "status": "ground_evaluation_only", "authentication": "none_hash_pinning_only"}


def validate_observation(obs: dict[str, Any]) -> None:
    require(type(obs.get("tick")) is int and obs["tick"] >= 0, "invalid tick")
    for key, lo, hi in (("temperature_c", -70, 150), ("vibration_g", 0, 40),
                        ("current_a", -50, 50), ("battery_percent", 0, 100),
                        ("link_quality", 0, 1)):
        x = obs.get(key)
        require(type(x) in (float, int) and math.isfinite(x) and lo <= x <= hi, f"invalid {key}")
    require(type(obs.get("telemetry_fresh")) is bool, "invalid freshness")
    wave = obs.get("waveform")
    require(isinstance(wave, list) and len(wave) == 80, "invalid waveform length")
    require(all(type(x) is float and math.isfinite(x) and -2 <= x <= 2 for x in wave), "invalid waveform")


def strip_truth(row: dict[str, Any]) -> dict[str, Any]:
    """No ground-truth label crosses the edge inference boundary."""
    return {key: val for key, val in row.items() if key not in ("synthetic_truth", "fault_class")}

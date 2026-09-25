"""Reproducible invented records. These are never represented as spacecraft telemetry."""
from __future__ import annotations

import random
from typing import Any

from .core import require, validate_observation


def generate(*, count: int = 60, seed: int = 991, outage_start: int = 10,
             outage_length: int = 16, mission: str = "synthetic-scout") -> dict[str, Any]:
    require(24 <= count <= 1000, "count must be 24..1000")
    require(0 <= outage_start <= count and 0 <= outage_length <= count, "invalid outage")
    rng = random.Random(seed)
    rows: list[dict[str, Any]] = []
    hidden_ticks = {i for i in range(7, count, 17)}
    known_ticks = {i for i in range(4, count, 6)} - hidden_ticks
    for i in range(count):
        hidden = i in hidden_ticks
        known = i in known_ticks
        severity = (0.65 if i % 3 == 1 else 0.75 if i % 3 == 2 else 1.0) if known else 0.0
        wave = [round(rng.uniform(-0.28, 0.28), 5) for _ in range(80)]
        if hidden:
            wave[23] = 1.27
        offline = outage_start <= i < outage_start + outage_length
        phase = "outage" if offline else "eclipse" if 32 <= i < 38 else "contact" if i % 15 in (0, 1) else "nominal"
        temp_shift = 0.0
        current_shift = 0.0
        injected = "nominal"
        if 26 <= i < 29:
            temp_shift, current_shift, injected = 26.0, 3.8, "moderate_distribution_shift"
        if 42 <= i < 44:
            temp_shift, current_shift, injected = 48.0, 7.0, "severe_distribution_shift"
        battery = round(50 + rng.uniform(0, 35), 5)
        if i == 39:
            battery, injected = 9.0, "battery_fallback"
        fresh = i != 19
        if not fresh:
            injected = "stale_telemetry"
        sensor_quality = 0.42 if i == 36 else 0.96
        if i == 36:
            injected = "sensor_quality_loss"
        obs = {
            "tick": i,
            "temperature_c": round(20 + rng.uniform(-2.6, 2.6) + 13 * severity + temp_shift, 5),
            "vibration_g": round(0.1 + rng.uniform(0, 0.08) + 0.42 * severity, 5),
            "current_a": round(2 + rng.uniform(-0.25, 0.25) + severity + current_shift, 5),
            "battery_percent": battery,
            "link_quality": 0.08 if offline else 0.92,
            "sensor_quality": sensor_quality,
            "telemetry_fresh": fresh,
            "mission_phase": phase,
            "waveform": wave,
        }
        validate_observation(obs)
        rows.append({**obs, "synthetic_truth": known or hidden,
                     "fault_class": "unmodeled" if hidden else "modeled" if known else "none",
                     "injected_condition": injected})
    return {
        "schema": "oea.synthetic.scenario.v2",
        "mission": mission,
        "seed": seed,
        "outage": {"start_tick": outage_start, "length_ticks": outage_length},
        "records": rows,
        "labels_are_synthetic": True,
        "purpose": "exercise governed action, abstention, degradation, retention, ground review, and fallback",
    }

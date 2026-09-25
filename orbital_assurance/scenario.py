"""Reproducible invented records. These are never represented as spacecraft telemetry."""

from __future__ import annotations

import random
from typing import Any

from .core import require, validate_observation


def generate(*, count: int = 48, seed: int = 991, outage_start: int = 10,
             outage_length: int = 13, mission: str = "synthetic-scout") -> dict[str, Any]:
    require(12 <= count <= 1000, "count must be 12..1000")
    require(0 <= outage_start <= count and 0 <= outage_length <= count, "invalid outage")
    rng = random.Random(seed)
    rows = []
    hidden_ticks = {i for i in range(7, count, 17)}
    known_ticks = {i for i in range(4, count, 6)} - hidden_ticks
    for i in range(count):
        hidden = i in hidden_ticks
        known = i in known_ticks
        severity = (0.65 if i % 3 == 1 else 0.75 if i % 3 == 2 else 1.0) if known else 0.0
        wave = [round(rng.uniform(-0.28, 0.28), 5) for _ in range(80)]
        if hidden:
            wave[23] = 1.27  # Unmodeled fault only present in retained waveform.
        offline = outage_start <= i < outage_start + outage_length
        obs = {
            "tick": i,
            "temperature_c": round(20 + rng.uniform(-2.6, 2.6) + 13 * severity, 5),
            "vibration_g": round(0.1 + rng.uniform(0, 0.08) + 0.42 * severity, 5),
            "current_a": round(2 + rng.uniform(-0.25, 0.25) + severity, 5),
            "battery_percent": round(50 + rng.uniform(0, 35), 5),
            "link_quality": 0.08 if offline else 0.92,
            "telemetry_fresh": i % 29 != 19,
            "waveform": wave,
        }
        validate_observation(obs)
        rows.append({**obs, "synthetic_truth": known or hidden,
                     "fault_class": "unmodeled" if hidden else "modeled" if known else "none"})
    return {"schema": "oea.synthetic.scenario.v1", "mission": mission, "seed": seed,
            "outage": {"start_tick": outage_start, "length_ticks": outage_length},
            "records": rows, "labels_are_synthetic": True}

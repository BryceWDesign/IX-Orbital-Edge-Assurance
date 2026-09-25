"""Bounded edge inference, scoped release pinning, and store-and-forward emulator."""

from __future__ import annotations

from typing import Any

from .core import (canonical, digest, predict, require, strip_truth, validate_model,
                   validate_observation, validate_policy)


def _size(value: dict[str, Any]) -> int:
    return len(canonical(value))


def simulate(scenario: dict[str, Any], model: dict[str, Any], policy: dict[str, Any],
             approved: dict[str, Any]) -> dict[str, Any]:
    validate_model(model)
    validate_policy(policy)
    require(scenario.get("schema") == "oea.synthetic.scenario.v1", "unknown scenario")
    require(scenario.get("labels_are_synthetic") is True, "unverified scenario label type")
    mission = scenario.get("mission")
    require(isinstance(mission, str) and bool(mission), "missing mission")
    rows = scenario.get("records")
    require(isinstance(rows, list) and bool(rows), "missing records")
    packets: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    delivered: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    queue: list[dict[str, Any]] = []
    prev_hash = "0" * 64
    expected_model = digest(model)
    expected_policy = digest(policy)
    for idx, row in enumerate(rows):
        require(isinstance(row, dict), "invalid row")
        observation = strip_truth(row)
        validate_observation(observation)
        tick = observation["tick"]
        require(tick == idx, "ticks must be contiguous")
        release_valid = (
            approved.get("schema") == "oea.release.pin.v1"
            and approved.get("mission") == mission
            and approved.get("status") == "ground_evaluation_only"
            and approved.get("authentication") == "none_hash_pinning_only"
            and approved.get("model_sha256") == expected_model
            and approved.get("policy_sha256") == expected_policy
            and type(approved.get("expires_after_tick")) is int
            and tick <= approved["expires_after_tick"]
        )
        fresh = observation["telemetry_fresh"]
        battery_ok = observation["battery_percent"] >= policy["battery_floor_percent"]
        link = observation["link_quality"] >= policy["minimum_link_quality"]
        score = round(predict(model, observation), 6) if release_valid and fresh and battery_ok else None
        if not release_valid:
            reason, base_action = "release_pin_invalid_or_expired", "hold_raw_for_review"
        elif not fresh:
            reason, base_action = "telemetry_stale", "hold_raw_for_review"
        elif not battery_ok:
            reason, base_action = "battery_below_floor", "hold_raw_for_review"
        elif score is not None and score >= policy["threshold"]:
            reason, base_action = "risk_at_or_above_threshold", "priority"
        else:
            reason, base_action = "risk_below_threshold", "summary"
        action = (f"{'send' if link else 'queue'}_{base_action}"
                  if base_action in ("priority", "summary") else base_action)
        require(action in policy["allowed_actions"], "unapproved action")
        packet = {
            "tick": tick, "action": action, "reason": reason, "score": score,
            "review_required": base_action in ("priority", "hold_raw_for_review"),
            "raw_sha256": digest(observation), "model_sha256": expected_model,
            "policy_sha256": expected_policy,
        }
        packets.append(packet)
        packet_hash = digest(packet)
        receipt = {"tick": tick, "packet_sha256": packet_hash, "previous_sha256": prev_hash}
        receipt["receipt_sha256"] = digest(receipt)
        prev_hash = receipt["receipt_sha256"]
        receipts.append(receipt)
        queued = {"tick": tick, "packet_sha256": packet_hash, "priority": packet["review_required"],
                  "bytes": _size(packet)}
        budget = policy["contact_budget_bytes"] if link else 0
        if link:
            # Higher-priority backlog is serviced first; both orders are stable.
            for item in sorted(queue[:], key=lambda x: (not x["priority"], x["tick"])):
                if item["bytes"] <= budget:
                    budget -= item["bytes"]
                    delivered.append({"tick": item["tick"], "at_tick": tick,
                                      "packet_sha256": item["packet_sha256"], "bytes": item["bytes"]})
                    queue.remove(item)
        if link and queued["bytes"] <= budget:
            delivered.append({"tick": tick, "at_tick": tick,
                              "packet_sha256": packet_hash, "bytes": queued["bytes"]})
        else:
            queue.append(queued)
        while sum(x["bytes"] for x in queue) > policy["queue_capacity_bytes"]:
            # Evict the oldest routine packet first, then the oldest priority packet.
            victim = min(queue, key=lambda x: (x["priority"], x["tick"]))
            queue.remove(victim)
            dropped.append({"tick": victim["tick"], "at_tick": tick,
                            "packet_sha256": victim["packet_sha256"], "bytes": victim["bytes"],
                            "reason": "queue_capacity"})
    return {"schema": "oea.edge.run.v1", "mission": mission, "packets": packets,
            "receipts": receipts, "delivered": delivered, "dropped": dropped,
            "pending": sorted(queue, key=lambda x: x["tick"]), "final_receipt_sha256": prev_hash}


def audit(scenario: dict[str, Any], model: dict[str, Any], policy: dict[str, Any],
          approved: dict[str, Any], edge: dict[str, Any],
          *, downlink_usd_per_mib: float = 25.0,
          inference_mj_per_record: float = 12.0) -> dict[str, Any]:
    require(downlink_usd_per_mib >= 0 and inference_mj_per_record >= 0, "invalid assumptions")
    expected = simulate(scenario, model, policy, approved)
    require(edge == expected, "edge replay mismatch; bundle rejected")
    rows = scenario["records"]
    confusion = {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
    model_blind = 0
    modeled_seen = 0
    for row, packet in zip(rows, edge["packets"]):
        flagged = packet["review_required"]
        actual = row["synthetic_truth"]
        require(type(actual) is bool, "invalid ground label")
        category = "tp" if flagged and actual else "fp" if flagged else "fn" if actual else "tn"
        confusion[category] += 1
        if row["fault_class"] == "unmodeled" and not flagged:
            model_blind += 1
        if row["fault_class"] == "modeled" and flagged:
            modeled_seen += 1
    raw_bytes = sum(len(canonical(strip_truth(row))) for row in rows)
    packet_bytes = sum(len(canonical(packet)) for packet in edge["packets"])
    inference_count = sum(packet["score"] is not None for packet in edge["packets"])
    delivered_bytes = sum(item["bytes"] for item in edge["delivered"])
    pending_bytes = sum(item["bytes"] for item in edge["pending"])
    dropped_bytes = sum(item["bytes"] for item in edge["dropped"])
    require(delivered_bytes + pending_bytes + dropped_bytes == packet_bytes,
            "transport accounting mismatch")
    # Illustrative transport price and compute energy are separate: energy is
    # not monetized here because satellite power has mission-specific value.
    transport_delta = (raw_bytes - packet_bytes) / (1024 * 1024) * downlink_usd_per_mib
    misses = confusion["fn"]
    break_even = transport_delta / misses if misses else None
    return {
        "schema": "oea.ground.review.v1", "evidence_level": "synthetic_ground_only",
        "mission": scenario["mission"], "records": len(rows),
        "confusion": confusion, "modeled_faults_flagged": modeled_seen,
        "unmodeled_faults_missed": model_blind,
        "raw_baseline_serialized_bytes": raw_bytes,
        "all_packet_serialized_bytes": packet_bytes,
        "inferences_executed": inference_count,
        "serialization_reduction_fraction": round(1 - packet_bytes / raw_bytes, 6),
        "delivered_packet_bytes": delivered_bytes, "pending_packet_bytes": pending_bytes,
        "dropped_packet_bytes": dropped_bytes, "dropped_packets": len(edge["dropped"]),
        "link_model": "synthetic_window_and_queue_no_radio_overhead",
        "assumptions": {"downlink_usd_per_mib": downlink_usd_per_mib,
                        "inference_mj_per_record": inference_mj_per_record,
                        "review_labor_usd": "not_modeled", "missed_event_usd": "not_modeled",
                        "processor_power_measured": False},
        "illustrative_transport_delta_usd": round(transport_delta, 8),
        "assumed_compute_energy_j": round(inference_count * inference_mj_per_record / 1000, 6),
        "miss_penalty_break_even_usd_each_if_baseline_detects_all":
            round(break_even, 8) if break_even is not None else None,
        "decision": "cost_effectiveness_not_established",
        "limitations": [
            "Training, records, labels, outage, and cost inputs are synthetic or assumed.",
            "The break-even expression assumes a perfect raw-data baseline and omits labor, latency, power opportunity cost, and radio overhead.",
            "Hash pins and receipts detect replay changes relative to this bundle; they provide no source authentication or tamper resistance against bundle replacement.",
            "Queue drops and pending packets represent delayed or missing summaries; raw data is retained only in this ground simulation.",
            "No flight processor, cloud backend, spacecraft interface, or orbital hardware was used.",
        ],
    }

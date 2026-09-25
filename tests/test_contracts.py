import copy
import math
import unittest

from orbital_assurance.core import (digest, policy, predict, release, train,
                                    validate_observation, validate_policy)
from orbital_assurance.runtime import audit, simulate
from orbital_assurance.scenario import generate


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = train()
        cls.rules = policy()
        cls.scenario = generate()
        cls.pin = release(cls.model, cls.rules, mission=cls.scenario["mission"], expires_at=47)

    def test_training_reproducible(self):
        self.assertEqual(self.model, train())
        self.assertNotEqual(self.model, train(seed=404))

    def test_synthetic_scenarios_reproducible(self):
        self.assertEqual(self.scenario, generate())
        self.assertNotEqual(self.scenario, generate(seed=992))

    def test_model_misses_unmodeled_fault_class(self):
        unseen = [r for r in self.scenario["records"] if r["fault_class"] == "unmodeled"]
        self.assertGreater(len(unseen), 0)
        self.assertTrue(all(predict(self.model, r) < self.rules["threshold"] for r in unseen))

    def test_no_ground_truth_in_edge_packets(self):
        edge = simulate(self.scenario, self.model, self.rules, self.pin)
        self.assertNotIn("synthetic_truth", str(edge))
        self.assertNotIn("fault_class", str(edge))

    def test_release_pin_change_holds_all_actions(self):
        changed = copy.deepcopy(self.pin)
        changed["model_sha256"] = "0" * 64
        edge = simulate(self.scenario, self.model, self.rules, changed)
        self.assertTrue(all(p["action"] == "hold_raw_for_review" and p["score"] is None
                            for p in edge["packets"]))

    def test_policy_mutation_fails_pin(self):
        changed = {**self.rules, "threshold": 0.8}
        edge = simulate(self.scenario, self.model, changed, self.pin)
        self.assertEqual(edge["packets"][0]["reason"], "release_pin_invalid_or_expired")

    def test_model_mutation_fails_pin(self):
        changed = copy.deepcopy(self.model)
        changed["bias"] += 1.0
        edge = simulate(self.scenario, changed, self.rules, self.pin)
        self.assertIsNone(edge["packets"][0]["score"])

    def test_mission_change_fails_pin(self):
        changed = copy.deepcopy(self.scenario)
        changed["mission"] = "different-mission"
        edge = simulate(changed, self.model, self.rules, self.pin)
        self.assertIsNone(edge["packets"][0]["score"])

    def test_expiry_blocks_new_inference(self):
        changed = {**self.pin, "expires_after_tick": 2}
        edge = simulate(self.scenario, self.model, self.rules, changed)
        self.assertIsNotNone(edge["packets"][2]["score"])
        self.assertIsNone(edge["packets"][3]["score"])

    def test_missing_freshness_requests_review(self):
        packet = simulate(self.scenario, self.model, self.rules, self.pin)["packets"][19]
        self.assertEqual((packet["reason"], packet["action"]),
                         ("telemetry_stale", "hold_raw_for_review"))

    def test_low_battery_requests_review(self):
        changed = copy.deepcopy(self.scenario)
        changed["records"][0]["battery_percent"] = 2.0
        packet = simulate(changed, self.model, self.rules, self.pin)["packets"][0]
        self.assertEqual(packet["reason"], "battery_below_floor")
        self.assertIsNone(packet["score"])

    def test_rejects_actuation_policy(self):
        changed = {**self.rules, "control_commands_enabled": True}
        with self.assertRaisesRegex(ValueError, "control commands"):
            validate_policy(changed)

    def test_rejects_unapproved_action_set(self):
        changed = {**self.rules, "allowed_actions": self.rules["allowed_actions"] + ["fire_thruster"]}
        with self.assertRaisesRegex(ValueError, "action list"):
            validate_policy(changed)

    def test_rejects_nonfinite_input(self):
        changed = copy.deepcopy(self.scenario["records"][0])
        changed["temperature_c"] = math.nan
        with self.assertRaisesRegex(ValueError, "invalid temperature"):
            validate_observation(changed)

    def test_rejects_missing_tick(self):
        changed = copy.deepcopy(self.scenario)
        changed["records"][1]["tick"] = 0
        with self.assertRaisesRegex(ValueError, "contiguous"):
            simulate(changed, self.model, self.rules, self.pin)

    def test_rejects_unsafe_contact_threshold(self):
        with self.assertRaisesRegex(ValueError, "link threshold"):
            validate_policy({**self.rules, "minimum_link_quality": 7.0})

    def test_outage_queues_and_capacity_drops(self):
        edge = simulate(self.scenario, self.model, self.rules, self.pin)
        self.assertGreater(len(edge["dropped"]), 0)
        for item in edge["delivered"]:
            self.assertGreaterEqual(item["at_tick"], item["tick"])
        self.assertLessEqual(sum(x["bytes"] for x in edge["pending"]),
                             self.rules["queue_capacity_bytes"])

    def test_all_actions_remain_bounded(self):
        edge = simulate(self.scenario, self.model, self.rules, self.pin)
        self.assertTrue({x["action"] for x in edge["packets"]} <= set(self.rules["allowed_actions"]))

    def test_receipt_chain_covers_each_packet(self):
        edge = simulate(self.scenario, self.model, self.rules, self.pin)
        previous = "0" * 64
        for packet, item in zip(edge["packets"], edge["receipts"]):
            self.assertEqual(item["previous_sha256"], previous)
            self.assertEqual(item["packet_sha256"], digest(packet))
            previous = item["receipt_sha256"]
        self.assertEqual(previous, edge["final_receipt_sha256"])

    def test_ground_rejects_tampered_edge(self):
        edge = simulate(self.scenario, self.model, self.rules, self.pin)
        edge["packets"][0]["action"] = "send_priority"
        with self.assertRaisesRegex(ValueError, "replay mismatch"):
            audit(self.scenario, self.model, self.rules, self.pin, edge)

    def test_missed_fault_and_transport_trade(self):
        edge = simulate(self.scenario, self.model, self.rules, self.pin)
        report = audit(self.scenario, self.model, self.rules, self.pin, edge)
        self.assertGreater(report["unmodeled_faults_missed"], 0)
        self.assertLess(report["inferences_executed"], report["records"])
        self.assertAlmostEqual(report["assumed_compute_energy_j"],
                               report["inferences_executed"] * 12 / 1000)
        self.assertGreater(report["dropped_packets"], 0)
        self.assertEqual(report["decision"], "cost_effectiveness_not_established")
        self.assertGreater(report["raw_baseline_serialized_bytes"], report["all_packet_serialized_bytes"])

    def test_threshold_sensitivity_has_more_misses_at_higher_threshold(self):
        outcomes = []
        for threshold in (0.4, 0.8):
            rules = policy(threshold=threshold)
            pin = release(self.model, rules, mission=self.scenario["mission"], expires_at=47)
            edge = simulate(self.scenario, self.model, rules, pin)
            outcomes.append(audit(self.scenario, self.model, rules, pin, edge)["confusion"]["fn"])
        self.assertLess(outcomes[0], outcomes[1])


if __name__ == "__main__":
    unittest.main()

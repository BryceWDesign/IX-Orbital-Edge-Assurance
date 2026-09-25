import copy
import unittest

from orbital_assurance.core import policy, train, validate_observation, validate_policy
from orbital_assurance.scenario import generate


class ContractTests(unittest.TestCase):
    def test_model_training_is_deterministic(self):
        self.assertEqual(train(), train())

    def test_scenario_generation_is_deterministic(self):
        self.assertEqual(generate(), generate())

    def test_policy_disables_physical_control(self):
        self.assertFalse(policy()["physical_control_commands_enabled"])

    def test_policy_rejects_enabled_control(self):
        p = policy()
        p["physical_control_commands_enabled"] = True
        with self.assertRaisesRegex(ValueError, "prohibited"):
            validate_policy(p)

    def test_policy_rejects_bad_drift_threshold_order(self):
        p = policy()
        p["drift_degrade"] = 4.0
        with self.assertRaisesRegex(ValueError, "drift thresholds"):
            validate_policy(p)

    def test_observation_rejects_unknown_phase(self):
        obs = copy.deepcopy(generate()["records"][0])
        obs["mission_phase"] = "landing"
        with self.assertRaisesRegex(ValueError, "mission phase"):
            validate_observation(obs)

    def test_scenario_truth_is_declared_synthetic(self):
        self.assertTrue(generate()["labels_are_synthetic"])

    def test_scenario_contains_declared_fault_injections(self):
        conditions = {r["injected_condition"] for r in generate()["records"]}
        self.assertIn("moderate_distribution_shift", conditions)
        self.assertIn("severe_distribution_shift", conditions)
        self.assertIn("battery_fallback", conditions)
        self.assertIn("stale_telemetry", conditions)


if __name__ == "__main__":
    unittest.main()

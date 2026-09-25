import copy
import unittest

from cryptography.exceptions import InvalidSignature

from orbital_assurance.authority import issue_authority
from orbital_assurance.core import digest, policy, strip_truth, train
from orbital_assurance.qualification import drift_score, uncertainty
from orbital_assurance.runtime import simulate, verify_receipts
from orbital_assurance.scenario import generate
from orbital_assurance.signing import deterministic_demo_identity


class QualificationTests(unittest.TestCase):
    def test_uncertainty_boundary(self):
        self.assertEqual(uncertainty(0.5), 1.0)
        self.assertEqual(uncertainty(0.0), 0.0)
        self.assertEqual(uncertainty(1.0), 0.0)

    def test_injected_severe_shift_has_more_drift_than_nominal(self):
        s = generate()
        nominal = strip_truth(s["records"][2])
        severe = strip_truth(s["records"][42])
        self.assertGreater(drift_score(severe), drift_score(nominal))


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.scenario = generate()
        self.model = train()
        self.policy = policy()
        self.ground = deterministic_demo_identity("ground-release-evaluation")
        self.runtime = deterministic_demo_identity("orbital-edge-runtime-evaluation")
        self.authority = issue_authority(mission=self.scenario["mission"], model=self.model,
                                         policy=self.policy, signer=self.ground,
                                         expires_at=len(self.scenario["records"]) - 1)
        self.edge = simulate(self.scenario, self.model, self.policy, self.authority, self.runtime)

    def test_all_six_authority_states_are_exercised(self):
        states = {d["authority_decision"] for d in self.edge["decisions"]}
        self.assertEqual(states, {"ACT", "ABSTAIN", "DEGRADE", "RETAIN", "REQUEST_GROUND_REVIEW", "FALLBACK"})

    def test_every_decision_has_receipt(self):
        self.assertEqual(len(self.edge["decisions"]), len(self.edge["receipts"]))
        self.assertEqual(len(self.edge["decisions"]), len(self.scenario["records"]))

    def test_receipt_chain_and_signatures_verify(self):
        self.assertTrue(verify_receipts(self.edge))

    def test_runtime_key_matches_all_receipts(self):
        key_id = self.edge["runtime_identity"]["key_id"]
        self.assertTrue(all(r["signature"]["key_id"] == key_id for r in self.edge["receipts"]))

    def test_receipt_signature_tamper_fails(self):
        edge = copy.deepcopy(self.edge)
        edge["receipts"][0]["signature"]["signature_b64"] = "AAAA"
        with self.assertRaises((InvalidSignature, ValueError)):
            verify_receipts(edge)

    def test_receipt_chain_tamper_fails(self):
        edge = copy.deepcopy(self.edge)
        edge["receipts"][1]["previous_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "receipt body mismatch"):
            verify_receipts(edge)

    def test_retained_evidence_points_to_real_observation_hash(self):
        by_tick = {x["tick"]: x for x in self.edge["retained_evidence"]}
        for tick, item in by_tick.items():
            self.assertEqual(item["raw_sha256"], digest(strip_truth(self.scenario["records"][tick])))

    def test_stale_telemetry_requests_ground_review(self):
        d = self.edge["decisions"][19]
        self.assertEqual(d["authority_decision"], "REQUEST_GROUND_REVIEW")
        self.assertEqual(d["reason"], "telemetry_stale")

    def test_battery_floor_enters_fallback(self):
        d = self.edge["decisions"][39]
        self.assertEqual(d["authority_decision"], "FALLBACK")
        self.assertTrue(d["fallback_active"])

    def test_moderate_shift_degrades(self):
        self.assertIn("DEGRADE", {self.edge["decisions"][i]["authority_decision"] for i in range(26, 29)})

    def test_outage_exercises_retention(self):
        self.assertIn("RETAIN", {self.edge["decisions"][i]["authority_decision"] for i in range(10, 26)})

    def test_invalid_authority_forces_fallback(self):
        auth = copy.deepcopy(self.authority)
        auth["mission"] = "tampered"
        edge = simulate(self.scenario, self.model, self.policy, auth, self.runtime)
        self.assertTrue(all(d["authority_decision"] == "FALLBACK" for d in edge["decisions"]))

    def test_control_commands_remain_disabled(self):
        self.assertFalse(self.policy["physical_control_commands_enabled"])

    def test_every_decision_trace_links_authority_and_crypto_requirements(self):
        for d in self.edge["decisions"]:
            self.assertIn("REQ-AUTH-001", d["traceability"])
            self.assertIn("REQ-CRYPTO-006", d["traceability"])

    def test_priority_zero_reserved_for_fallback(self):
        for d in self.edge["decisions"]:
            if d["priority"] == "P0":
                self.assertEqual(d["authority_decision"], "FALLBACK")


if __name__ == "__main__":
    unittest.main()

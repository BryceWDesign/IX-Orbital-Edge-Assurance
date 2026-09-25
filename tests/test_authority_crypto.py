import copy
import unittest

from cryptography.exceptions import InvalidSignature

from orbital_assurance.authority import issue_authority, validate_authority
from orbital_assurance.core import policy, train
from orbital_assurance.signing import deterministic_demo_identity, sign_payload, verify_signature


class SigningTests(unittest.TestCase):
    def test_signature_round_trip(self):
        identity = deterministic_demo_identity("test")
        payload = {"a": 1, "b": [2, 3]}
        sig = sign_payload(identity, payload)
        self.assertTrue(verify_signature(payload, sig))

    def test_payload_tamper_rejected(self):
        identity = deterministic_demo_identity("test")
        sig = sign_payload(identity, {"a": 1})
        with self.assertRaises(InvalidSignature):
            verify_signature({"a": 2}, sig)

    def test_key_id_tamper_rejected(self):
        identity = deterministic_demo_identity("test")
        sig = sign_payload(identity, {"a": 1})
        sig["key_id"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "key id mismatch"):
            verify_signature({"a": 1}, sig)

    def test_demo_identity_is_deterministic(self):
        a = deterministic_demo_identity("same")
        b = deterministic_demo_identity("same")
        self.assertEqual(a.key_id, b.key_id)


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.model = train()
        self.policy = policy()
        self.signer = deterministic_demo_identity("ground")
        self.auth = issue_authority(mission="m1", model=self.model, policy=self.policy,
                                    signer=self.signer, expires_at=9)

    def valid(self, **overrides):
        args = dict(mission="m1", model=self.model, policy=self.policy, tick=1,
                    phase="nominal", decision_class="telemetry_triage")
        args.update(overrides)
        return validate_authority(self.auth, **args)

    def test_valid_authority(self):
        self.assertEqual(self.valid(), (True, "authorized"))

    def test_wrong_mission_rejected(self):
        self.assertFalse(self.valid(mission="other")[0])

    def test_expired_rejected(self):
        self.assertFalse(self.valid(tick=10)[0])

    def test_wrong_phase_rejected(self):
        self.assertFalse(self.valid(phase="commissioning")[0])

    def test_wrong_decision_class_rejected(self):
        self.assertFalse(self.valid(decision_class="propulsion")[0])

    def test_model_mutation_rejected(self):
        model = copy.deepcopy(self.model)
        model["bias"] += 0.1
        self.assertFalse(self.valid(model=model)[0])

    def test_policy_mutation_rejected(self):
        rules = copy.deepcopy(self.policy)
        rules["risk_threshold"] = 0.7
        self.assertFalse(self.valid(policy=rules)[0])

    def test_authority_body_tamper_rejected(self):
        self.auth["expires_after_tick"] = 99
        self.assertFalse(self.valid()[0])

    def test_physical_controls_explicitly_denied(self):
        denied = set(self.auth["explicitly_denied_control_classes"])
        self.assertEqual(denied, {"attitude_control", "propulsion", "payload_shutdown", "thermal_override"})


if __name__ == "__main__":
    unittest.main()

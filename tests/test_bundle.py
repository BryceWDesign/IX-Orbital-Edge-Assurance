import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.exceptions import InvalidSignature

from orbital_assurance.assurance import build_assurance_case, verify_assurance_case
from orbital_assurance.bundle import FILES, make_bundle, verify_bundle
from orbital_assurance.core import canonical


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "evidence"
        make_bundle(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_bundle_verifies_end_to_end(self):
        result = verify_bundle(self.path)
        self.assertTrue(result["verified"])
        self.assertTrue(result["manifest_signature_verified"])
        self.assertTrue(result["decision_signatures_verified"])
        self.assertTrue(result["deterministic_replay_verified"])
        self.assertTrue(result["assurance_traceability_verified"])

    def test_manifest_has_exact_file_set(self):
        manifest = json.loads((self.path / "manifest.json").read_bytes())
        self.assertEqual(set(manifest["files"]), set(FILES))

    def test_one_byte_file_corruption_fails(self):
        p = self.path / "edge_run.json"
        p.write_bytes(p.read_bytes() + b"x")
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            verify_bundle(self.path)

    def test_rehashing_file_without_resigning_manifest_fails_manifest_signature(self):
        p = self.path / "edge_run.json"
        edge = json.loads(p.read_bytes())
        edge["decisions"][0]["reason"] = "forged"
        raw = canonical(edge) + b"\n"
        p.write_bytes(raw)
        manifest = json.loads((self.path / "manifest.json").read_bytes())
        manifest["files"]["edge_run.json"] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        (self.path / "manifest.json").write_bytes(canonical(manifest) + b"\n")
        with self.assertRaises(InvalidSignature):
            verify_bundle(self.path)

    def test_manifest_signature_corruption_fails(self):
        sig = json.loads((self.path / "manifest_signature.json").read_bytes())
        sig["signature_b64"] = "AAAA"
        (self.path / "manifest_signature.json").write_bytes(canonical(sig) + b"\n")
        with self.assertRaises((InvalidSignature, ValueError)):
            verify_bundle(self.path)

    def test_assurance_case_recomputes_exactly(self):
        edge = json.loads((self.path / "edge_run.json").read_bytes())
        case = json.loads((self.path / "assurance_case.json").read_bytes())
        self.assertEqual(case, build_assurance_case(edge))
        self.assertTrue(verify_assurance_case(case, edge))

    def test_assurance_case_has_supported_crypto_claim(self):
        case = json.loads((self.path / "assurance_case.json").read_bytes())
        claim = next(c for c in case["claims"] if c["requirement_id"] == "REQ-CRYPTO-006")
        self.assertEqual(claim["status"], "supported")
        self.assertEqual(len(claim["evidence_receipts"]), 60)

    def test_repeat_bundle_is_byte_identical(self):
        second = Path(self.temp.name) / "second"
        make_bundle(second)
        for name in (*FILES, "manifest.json", "manifest_signature.json"):
            self.assertEqual((self.path / name).read_bytes(), (second / name).read_bytes(), name)

    def test_ground_review_reports_all_states(self):
        report = json.loads((self.path / "ground_review.json").read_bytes())
        self.assertEqual(set(report["authority_decision_counts"]),
                         {"ACT", "ABSTAIN", "DEGRADE", "RETAIN", "REQUEST_GROUND_REVIEW", "FALLBACK"})

    def test_demo_keys_are_labeled_non_operational_in_report(self):
        report = json.loads((self.path / "ground_review.json").read_bytes())
        self.assertTrue(any("deterministic" in x and "non-secret" in x for x in report["limitations"]))


if __name__ == "__main__":
    unittest.main()

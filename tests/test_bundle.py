import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from orbital_assurance.bundle import make_bundle, verify_bundle
from orbital_assurance.core import canonical


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "release-evidence"
        make_bundle(self.path, count=24, outage_start=5, outage_length=14)

    def _replace_and_update_manifest(self, filename, changed):
        raw = canonical(changed) + b"\n"
        (self.path / filename).write_bytes(raw)
        manifest = json.loads((self.path / "manifest.json").read_bytes())
        manifest["files"][filename] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        (self.path / "manifest.json").write_bytes(canonical(manifest) + b"\n")

    def test_can_verify_written_bundle(self):
        result = verify_bundle(self.path)
        self.assertTrue(result["verified"])
        self.assertFalse(result["authenticity_verified"])

    def test_one_byte_corruption_fails_manifest(self):
        p = self.path / "edge_run.json"
        p.write_bytes(p.read_bytes() + b"x")
        with self.assertRaisesRegex(ValueError, "integrity mismatch"):
            verify_bundle(self.path)

    def test_rehashed_tamper_still_fails_replay(self):
        edge = json.loads((self.path / "edge_run.json").read_bytes())
        edge["packets"][0]["reason"] = "altered"
        self._replace_and_update_manifest("edge_run.json", edge)
        with self.assertRaisesRegex(ValueError, "edge execution mismatch"):
            verify_bundle(self.path)

    def test_rehashed_ground_change_fails_review(self):
        report = json.loads((self.path / "ground_review.json").read_bytes())
        report["confusion"]["fn"] = 0
        self._replace_and_update_manifest("ground_review.json", report)
        with self.assertRaisesRegex(ValueError, "ground review mismatch"):
            verify_bundle(self.path)

    def test_rehashed_study_change_fails_study_replay(self):
        study = json.loads((self.path / "threshold_study.json").read_bytes())
        study[0]["dropped_packets"] = 0
        self._replace_and_update_manifest("threshold_study.json", study)
        with self.assertRaisesRegex(ValueError, "threshold study mismatch"):
            verify_bundle(self.path)

    def test_rehashed_model_mutation_fails_release_pin_semantics(self):
        model = json.loads((self.path / "model.json").read_bytes())
        model["bias"] += 0.3
        self._replace_and_update_manifest("model.json", model)
        with self.assertRaisesRegex(ValueError, "edge execution mismatch"):
            verify_bundle(self.path)

    def test_unknown_manifest_file_rejected(self):
        manifest = json.loads((self.path / "manifest.json").read_bytes())
        manifest["files"]["unapproved.json"] = {"bytes": 0, "sha256": ""}
        (self.path / "manifest.json").write_bytes(canonical(manifest) + b"\n")
        with self.assertRaisesRegex(ValueError, "file set"):
            verify_bundle(self.path)

    def test_repeat_run_is_byte_identical(self):
        second = Path(self.folder.name) / "second"
        make_bundle(second, count=24, outage_start=5, outage_length=14)
        self.assertEqual((self.path / "manifest.json").read_bytes(),
                         (second / "manifest.json").read_bytes())


if __name__ == "__main__":
    unittest.main()

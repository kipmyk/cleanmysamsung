import unittest
import os
import json
import tempfile
from unittest.mock import patch

from cleanmysamsung.packages import (
    validate_package_name,
    parse_profile,
    disable_package_verified,
    enable_package_verified,
    get_package_state_map
)

class TestPackageValidation(unittest.TestCase):
    def test_valid_package_names(self):
        valid = [
            "com.facebook.appmanager",
            "com.sec.android.diagmonagent",
            "com.samsung.android.bixby.agent",
            "ke.co.synergy.dosikaa",
            "org.chromium.webview_shell"
        ]
        for name in valid:
            self.assertTrue(validate_package_name(name), f"Failed for {name}")

    def test_invalid_package_names(self):
        invalid = [
            "invalid_single_word",
            "123.numeric.start",
            "com.facebook;rm -rf /",
            "com..double.dot",
            "com.facebook.appmanager&&id",
            "",
            "   "
        ]
        for name in invalid:
            self.assertFalse(validate_package_name(name), f"Expected False for {name}")

    def test_parse_json_profile(self):
        sample = {
            "profile_name": "Test Profile",
            "target_models": ["SM-A528B"],
            "tiers": {
                "tier1": [
                    {"package": "com.facebook.system"},
                    {"package": "com.facebook.services"},
                    {"package": "invalid name"}
                ],
                "tier2": [
                    {"package": "com.sec.android.diagmonagent"},
                    {"package": "com.facebook.system"}
                ]
            }
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(sample, f)
            temp_path = f.name

        try:
            meta, pkgs = parse_profile(temp_path)
            self.assertEqual(meta["profile_name"], "Test Profile")
            self.assertEqual(len(pkgs), 3)
            self.assertIn("com.facebook.system", pkgs)
            self.assertIn("com.facebook.services", pkgs)
            self.assertIn("com.sec.android.diagmonagent", pkgs)
        finally:
            os.remove(temp_path)

    @patch("cleanmysamsung.packages.run_adb")
    def test_disable_package_verified_success(self, mock_adb):
        def fake_run(cmd, device, check):
            if "disable-user" in cmd:
                return "Package com.facebook.system new state: disabled-user", "", 0
            if "-d" in cmd:
                return "package:com.facebook.system", "", 0
            return "", "", 0

        mock_adb.side_effect = fake_run
        success, err = disable_package_verified("dev", "com.facebook.system")
        self.assertTrue(success)
        self.assertEqual(err, "")

    @patch("cleanmysamsung.packages.run_adb")
    def test_disable_package_verified_failure(self, mock_adb):
        def fake_run(cmd, device, check):
            if "disable-user" in cmd:
                return "Success", "", 0
            if "-d" in cmd:
                return "", "", 0  # Verification fails: not in disabled list
            return "", "", 0

        mock_adb.side_effect = fake_run
        success, err = disable_package_verified("dev", "com.facebook.system")
        self.assertFalse(success)
        self.assertIn("Verification failed", err)

    def test_disable_package_invalid_syntax_rejected(self):
        success, err = disable_package_verified("dev", "invalid;syntax")
        self.assertFalse(success)
        self.assertIn("Invalid package name", err)

if __name__ == "__main__":
    unittest.main()

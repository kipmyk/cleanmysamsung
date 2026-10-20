import unittest
import os
import json
import tempfile
from unittest.mock import patch

from cleanmysamsung.sessions import (
    create_session_record,
    save_session_record,
    load_session,
    validate_session_data,
    rollback_session,
    SessionValidationError
)

class TestSessionTracking(unittest.TestCase):
    def setUp(self):
        self.device_info = {
            "target": "192.168.1.100:5555",
            "serial": "MOCK_SERIAL_12345",
            "model": "SM-A528B",
            "fingerprint": "samsung/mock_model/galaxy:14/UP1A.000000.000",
            "android_version": "14",
            "oneui_version": "6.01"
        }
        self.targets = [
            "com.facebook.system",
            "com.facebook.services",
            "com.sec.android.diagmonagent",
            "com.nonexistent.app"
        ]
        self.current_states = {
            "com.facebook.system": "ENABLED",
            "com.facebook.services": "DISABLED",
            "com.sec.android.diagmonagent": "ENABLED"
        }

    def test_session_state_categorization(self):
        record = create_session_record(
            self.device_info,
            "test_profile.json",
            self.targets,
            self.current_states
        )

        packages = record["packages"]
        self.assertEqual(packages["original_states"]["com.facebook.system"], "ENABLED")
        self.assertEqual(packages["original_states"]["com.facebook.services"], "DISABLED")
        self.assertEqual(packages["original_states"]["com.nonexistent.app"], "NOT_INSTALLED")

        self.assertIn("com.facebook.services", packages["skipped_already_disabled"])
        self.assertIn("com.nonexistent.app", packages["not_installed"])

    def test_session_persistence_and_loading(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            record = create_session_record(
                self.device_info,
                "test_profile.json",
                self.targets,
                self.current_states
            )
            saved_path = save_session_record(record, backup_dir=temp_dir)
            self.assertTrue(os.path.isfile(saved_path))

            loaded_path, loaded_data = load_session(saved_path, backup_dir=temp_dir)
            self.assertEqual(loaded_path, saved_path)
            self.assertEqual(loaded_data["device"]["model"], "SM-A528B")
            self.assertEqual(loaded_data["session_id"], record["session_id"])

    def test_validate_session_data_rejects_malformed_records(self):
        # Missing device block
        bad1 = {"session_id": "session_20261020_000000", "packages": {}}
        with self.assertRaises(SessionValidationError):
            validate_session_data(bad1)

        # Invalid session_id attempting path traversal
        bad2 = {
            "session_id": "../session_escape",
            "device": {},
            "packages": {}
        }
        with self.assertRaises(SessionValidationError):
            validate_session_data(bad2)

        # Unsafe package name with shell command injection attempt
        bad3 = {
            "session_id": "session_20261020_000000",
            "device": {"model": "SM-A528B"},
            "packages": {
                "confirmed_disabled": ["com.facebook.system; rm -rf /"]
            }
        }
        with self.assertRaises(SessionValidationError):
            validate_session_data(bad3)

    @patch("builtins.input", return_value="n")
    def test_rollback_device_mismatch_aborts_without_confirmation(self, mock_input):
        with tempfile.TemporaryDirectory() as temp_dir:
            record = create_session_record(
                self.device_info,
                "test_profile.json",
                self.targets,
                self.current_states
            )
            saved_path = save_session_record(record, backup_dir=temp_dir)

            mismatched_device = {
                "model": "SM-G998B",  # Different Galaxy model
                "serial": "DIFFERENT_SERIAL"
            }
            # Attempt rollback without user confirmation (returns False)
            result = rollback_session("target_dev", mismatched_device, saved_path, dry_run=True, backup_dir=temp_dir)
            self.assertFalse(result)

    @patch("cleanmysamsung.sessions.enable_package_verified")
    def test_rollback_handles_partial_failures_honestly(self, mock_enable):
        # First package succeeds, second package fails
        mock_enable.side_effect = [
            (True, ""),
            (False, "Device error")
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            record = create_session_record(
                self.device_info,
                "test_profile.json",
                self.targets,
                self.current_states
            )
            record["packages"]["confirmed_disabled"] = [
                "com.facebook.system",
                "com.sec.android.diagmonagent"
            ]
            saved_path = save_session_record(record, backup_dir=temp_dir)

            ok = rollback_session("target_dev", self.device_info, saved_path, dry_run=False, backup_dir=temp_dir)
            self.assertFalse(ok)  # Returns False because one package failed

    @patch("builtins.input", return_value="n")
    def test_rollback_unverifiable_serial_warns_and_requires_confirmation(self, mock_input):
        with tempfile.TemporaryDirectory() as temp_dir:
            record = create_session_record(
                self.device_info,
                "test_profile.json",
                self.targets,
                self.current_states
            )
            saved_path = save_session_record(record, backup_dir=temp_dir)

            # Device where serial could not be queried
            unverified_device = {
                "model": "SM-A528B",
                "serial": "Unknown"
            }
            # Aborts when user declines confirmation
            result = rollback_session("target_dev", unverified_device, saved_path, dry_run=True, backup_dir=temp_dir)
            self.assertFalse(result)

if __name__ == "__main__":
    unittest.main()

import subprocess
import unittest
from unittest.mock import patch, MagicMock

from cleanmysamsung.adb import (
    run_adb,
    get_connected_devices,
    select_device,
    AdbError,
    AdbNotFoundError,
    AdbTimeoutError
)

class TestAdbExecution(unittest.TestCase):
    @patch("subprocess.run")
    def test_run_adb_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="success\n", stderr="")
        stdout, stderr, code = run_adb(["get-state"], device="dev1")
        self.assertEqual(stdout, "success")
        self.assertEqual(code, 0)
        # Check command structure
        called_cmd = mock_run.call_args[0][0]
        self.assertIn("-s", called_cmd)
        self.assertIn("dev1", called_cmd)
        self.assertIn("get-state", called_cmd)

    @patch("subprocess.run")
    def test_run_adb_command_failure_raises_adberror(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error: closed")
        with self.assertRaises(AdbError):
            run_adb(["shell", "pm", "list"], check=True)

    @patch("subprocess.run")
    def test_run_adb_timeout_raises_adbtimeouterror(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["adb"], timeout=5.0)
        with self.assertRaises(AdbTimeoutError):
            run_adb(["shell", "sleep", "10"], timeout=5.0)

    @patch("subprocess.run")
    def test_run_adb_file_not_found_raises_adbnotfounderror(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        with self.assertRaises(AdbNotFoundError):
            run_adb(["devices"])

    @patch("cleanmysamsung.adb.run_adb")
    def test_get_connected_devices_categorization(self, mock_adb):
        # Mock adb devices -l output
        devices_output = (
            "List of devices attached\n"
            "dev_online           device product:a52sxq model:SM_A528B device:a52sxq\n"
            "dev_unauthorized     unauthorized usb:1-1\n"
            "dev_offline          offline usb:1-2\n"
        )
        def fake_run(args, device=None, check=True, timeout=30.0):
            if "devices" in args:
                return devices_output, "", 0
            if "ro.serialno" in args:
                return f"SERIAL_{device}", "", 0
            return "", "", 0

        mock_adb.side_effect = fake_run
        authorized, unauthorized = get_connected_devices()
        self.assertEqual(authorized, ["dev_online"])
        self.assertIn(("dev_unauthorized", "unauthorized"), unauthorized)
        self.assertIn(("dev_offline", "offline"), unauthorized)

    @patch("cleanmysamsung.adb.get_connected_devices")
    def test_select_device_specified_valid(self, mock_devices):
        mock_devices.return_value = (["dev1", "dev2"], [])
        chosen = select_device("dev1")
        self.assertEqual(chosen, "dev1")

    @patch("cleanmysamsung.adb.get_connected_devices")
    def test_select_device_specified_invalid_exits(self, mock_devices):
        mock_devices.return_value = (["dev1"], [])
        with self.assertRaises(SystemExit):
            select_device("dev_unknown")

    @patch("cleanmysamsung.adb.get_connected_devices")
    def test_select_device_single_auto_selects(self, mock_devices):
        mock_devices.return_value = (["single_dev"], [])
        chosen = select_device()
        self.assertEqual(chosen, "single_dev")

    @patch("builtins.input", return_value="2")
    @patch("cleanmysamsung.adb.run_adb")
    @patch("cleanmysamsung.adb.get_connected_devices")
    def test_select_device_multiple_prompts_user(self, mock_devices, mock_adb, mock_input):
        mock_devices.return_value = (["dev1", "dev2"], [])
        mock_adb.return_value = ("SM-A528B", "", 0)
        chosen = select_device()
        self.assertEqual(chosen, "dev2")

if __name__ == "__main__":
    unittest.main()

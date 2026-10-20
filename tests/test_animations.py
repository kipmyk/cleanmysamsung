import unittest
from unittest.mock import patch
from cleanmysamsung.animations import (
    get_animation_scales,
    set_animation_scales,
    restore_animations,
    is_valid_scale
)

class TestAnimationSettings(unittest.TestCase):
    def test_is_valid_scale(self):
        self.assertTrue(is_valid_scale("0.5"))
        self.assertTrue(is_valid_scale("1.0"))
        self.assertTrue(is_valid_scale("0"))
        self.assertFalse(is_valid_scale("-1.0"))
        self.assertFalse(is_valid_scale("invalid"))
        self.assertFalse(is_valid_scale(None))

    @patch("cleanmysamsung.animations.run_adb")
    def test_get_animation_scales_does_not_assume_defaults(self, mock_adb):
        # Return null for window and empty for transition
        def fake_run(args, device, check):
            key = args[4]
            if key == "window_animation_scale":
                return "null", "", 0
            elif key == "transition_animation_scale":
                return "", "", 0
            elif key == "animator_duration_scale":
                return "0.5", "", 0
            return "", "", 1

        mock_adb.side_effect = fake_run
        scales = get_animation_scales("test_device")
        self.assertIsNone(scales["window_animation_scale"])
        self.assertIsNone(scales["transition_animation_scale"])
        self.assertEqual(scales["animator_duration_scale"], "0.5")

    @patch("cleanmysamsung.animations.run_adb")
    def test_restore_animations_only_restores_valid_values(self, mock_adb):
        calls = []
        def fake_run(args, device, check):
            calls.append(args)
            if args[1] == "settings" and args[2] == "get":
                return "0.75", "", 0
            return "", "", 0

        mock_adb.side_effect = fake_run

        original = {
            "window_animation_scale": "0.75",
            "transition_animation_scale": None,
            "animator_duration_scale": "invalid"
        }
        success, err = restore_animations("test_device", original)
        self.assertTrue(success)
        self.assertEqual(err, "")
        # Only window_animation_scale should have been put
        put_calls = [c for c in calls if len(c) > 3 and c[2] == "put"]
        self.assertEqual(len(put_calls), 1)
        self.assertEqual(put_calls[0][4], "window_animation_scale")
        self.assertEqual(put_calls[0][5], "0.75")

if __name__ == "__main__":
    unittest.main()

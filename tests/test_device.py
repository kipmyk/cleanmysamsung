import unittest
from cleanmysamsung.device import check_profile_compatibility

class TestDeviceCompatibility(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "profile_name": "Samsung Galaxy A52s / A52 5G",
            "target_models": ["SM-A528B", "SM-A525F"],
            "min_android_version": 11,
            "max_android_version": 14
        }

    def test_valid_samsung_device(self):
        dev = {
            "manufacturer": "Samsung",
            "model": "SM-A528B",
            "android_version": "14"
        }
        compatible, msg = check_profile_compatibility(dev, self.profile)
        self.assertTrue(compatible)
        self.assertEqual(msg, "")

    def test_non_samsung_manufacturer_rejected(self):
        dev = {
            "manufacturer": "Xiaomi",
            "model": "SM-A528B",
            "android_version": "14"
        }
        compatible, msg = check_profile_compatibility(dev, self.profile)
        self.assertFalse(compatible)
        self.assertIn("strictly designed for Samsung Galaxy devices", msg)

    def test_unsupported_model_rejected(self):
        dev = {
            "manufacturer": "Samsung",
            "model": "SM-G998B",
            "android_version": "14"
        }
        compatible, msg = check_profile_compatibility(dev, self.profile)
        self.assertFalse(compatible)
        self.assertIn("not in profile target models", msg)

    def test_out_of_range_android_version(self):
        dev = {
            "manufacturer": "Samsung",
            "model": "SM-A528B",
            "android_version": "10"
        }
        compatible, msg = check_profile_compatibility(dev, self.profile)
        self.assertFalse(compatible)
        self.assertIn("below profile minimum", msg)

if __name__ == "__main__":
    unittest.main()

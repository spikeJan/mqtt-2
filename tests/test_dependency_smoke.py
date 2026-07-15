import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def requirement_lines(path):
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


class DependencySmokeTests(unittest.TestCase):
    def test_paho_callback_api_version_2_is_available(self):
        import paho.mqtt.client as mqtt

        self.assertTrue(hasattr(mqtt, "CallbackAPIVersion"))
        self.assertTrue(hasattr(mqtt.CallbackAPIVersion, "VERSION2"))
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.assertIsNotNone(client)

    def test_yaml_dependency_is_importable(self):
        import yaml

        self.assertEqual(yaml.safe_load("enabled: true\n"), {"enabled": True})

    def test_openpyxl_dependency_is_importable(self):
        import openpyxl

        workbook = openpyxl.Workbook()
        try:
            self.assertEqual(workbook.active.title, "Sheet")
        finally:
            workbook.close()

    def test_root_requirements_include_bridge_and_analysis(self):
        lines = requirement_lines(REPOSITORY_ROOT / "requirements.txt")
        self.assertIn("-r bridge/requirements.txt", lines)
        self.assertIn("-r analysis/requirements.txt", lines)

    def test_declared_paho_version_matches_version2_api(self):
        lines = requirement_lines(REPOSITORY_ROOT / "bridge" / "requirements.txt")
        self.assertIn("paho-mqtt==2.1.0", lines)

    def test_unused_opencv_is_not_declared(self):
        lines = requirement_lines(REPOSITORY_ROOT / "bridge" / "requirements.txt")
        self.assertFalse(any(line.lower().startswith("opencv-python") for line in lines))


if __name__ == "__main__":
    unittest.main()

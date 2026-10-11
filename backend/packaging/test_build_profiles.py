"""Packaging checks only: no shared database or system service is used."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("server_bundle", Path(__file__).with_name("build_server_bundle.py"))
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class BuildProfiles(unittest.TestCase):
    def test_windows81(self):
        self.assertEqual(bundle.validate_compatibility("windows81", (3, 12, 9), "postgres (PostgreSQL) 17.11"), 17)

    def test_modern(self):
        self.assertEqual(bundle.validate_compatibility("modern", (3, 13, 15), "postgres (PostgreSQL) 17.11"), 17)

    def test_new_python_rejected(self):
        with self.assertRaises(SystemExit):
            bundle.validate_compatibility("windows81", (3, 13, 15), "postgres (PostgreSQL) 17.11")

    def test_engine_downgrade_rejected(self):
        with self.assertRaises(SystemExit):
            bundle.validate_compatibility("windows81", (3, 12, 9), "postgres (PostgreSQL) 14.20")

    def test_unknown_engine_rejected(self):
        with self.assertRaises(SystemExit):
            bundle.validate_compatibility("windows81", (3, 12, 9), "unknown")


if __name__ == "__main__":
    unittest.main()

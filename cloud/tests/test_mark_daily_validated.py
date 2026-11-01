"""Never mark a batch validated before its source load is complete."""

from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mark_daily_validated import mark


class MarkDailyValidatedTests(unittest.TestCase):
    def test_rejects_missing_or_ambiguous_completed_batch(self):
        config = Mock(project="demo-project")
        config.query.return_value = []
        with self.assertRaises(ValueError):
            mark("2026-11-01", config)
        self.assertEqual(config.query.call_count, 1)
        config.query.return_value = [SimpleNamespace(fingerprint="a"), SimpleNamespace(fingerprint="b")]
        with self.assertRaises(ValueError):
            mark("2026-11-01", config)

    def test_marks_completed_batch_with_fingerprint(self):
        config = Mock(project="demo-project")
        config.query.side_effect = [[SimpleNamespace(fingerprint="sha")], []]
        mark("2026-11-01", config)
        sql = config.query.call_args.args[1]
        self.assertIn("MERGE `demo-project.ecobottle_ops.daily_validations`", sql)
        self.assertIn("@fingerprint", sql)
        self.assertEqual(config.query.call_args.args[2][1].value, "sha")


if __name__ == "__main__":
    unittest.main()

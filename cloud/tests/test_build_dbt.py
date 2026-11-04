"""Retry terminal service failures without hiding SQL or data quality failures."""

import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_dbt import build


class BuildDbtTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        (self.project / "target").mkdir()
        self.path = self.project / "target/run_results.json"

    def runner(self, rows, succeed=False):
        def run(*args, **kwargs):
            self.path.write_text(json.dumps({"results": rows}), encoding="utf-8")
            return SimpleNamespace(returncode=0 if succeed else 1)
        return run

    def test_terminal_500_rebuilds_whole_project_then_succeeds(self):
        failed = [{"status": "error", "message": "Database Error: 500 Error; reason: backendError"},
                  {"status": "skipped"}, {"status": "pass"}]
        runner = Mock(side_effect=[self.runner(failed)(), SimpleNamespace(returncode=0)])
        sleep = Mock()
        self.assertEqual(build(self.project, runner=runner, sleep=sleep, clock=lambda: 0), 0)
        self.assertEqual(runner.call_count, 2)
        self.assertTrue(all(call.args[0] == ["dbt", "build"] for call in runner.call_args_list))
        sleep.assert_called_once_with(15)

    def test_repeated_backend_errors_stop_after_three_attempts(self):
        runner = Mock(side_effect=self.runner([{"status": "error", "message": "503 Service Unavailable"}]))
        sleep = Mock()
        self.assertEqual(build(self.project, runner=runner, sleep=sleep, clock=lambda: 0), 1)
        self.assertEqual(runner.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [15, 30])

    def test_data_failures_sql_errors_and_missing_artifact_never_retry(self):
        for rows in (
            [{"status": "fail", "message": "Got 1 result"}],
            [{"status": "error", "message": "400 Syntax error"}],
            [{"status": "error", "message": "backendError"}, {"status": "fail"}],
            [{"status": "error", "message": "Permission denied"}],
        ):
            runner = Mock(side_effect=self.runner(rows))
            sleep = Mock()
            self.assertEqual(build(self.project, runner=runner, sleep=sleep, clock=lambda: 0), 1)
            runner.assert_called_once()
            sleep.assert_not_called()
        runner = Mock(return_value=SimpleNamespace(returncode=2))
        self.assertEqual(build(self.project, runner=runner, clock=lambda: float("inf")), 2)
        runner.assert_called_once()


if __name__ == "__main__":
    unittest.main()

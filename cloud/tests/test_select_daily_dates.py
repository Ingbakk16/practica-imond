"""Selection safeguards for scheduled catch-up and manual ranges."""

from datetime import date, timedelta
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from select_daily_dates import select_dates


class SelectDailyDatesTests(unittest.TestCase):
    def test_manual_historical_only_and_one_day(self):
        self.assertEqual(select_dates(None, None), [])
        self.assertEqual(select_dates(date(2025, 10, 1), None), [date(2025, 10, 1)])
        with self.assertRaises(ValueError):
            select_dates(None, date(2025, 10, 2))

    def test_manual_range_is_bounded(self):
        start = date(2025, 10, 1)
        self.assertEqual(len(select_dates(start, start + timedelta(days=6))), 7)
        with self.assertRaises(ValueError):
            select_dates(start, start + timedelta(days=7))
        with self.assertRaises(ValueError):
            select_dates(start, start - timedelta(days=1))

    def test_schedule_skips_complete_and_recovers_gaps(self):
        self.assertEqual(select_dates(None, None, scheduled=True, go_live=date(2026, 11, 1),
                                      completed={"2026-11-01", "2026-11-03"}, today=date(2026, 11, 5)),
                         [date(2026, 11, 2), date(2026, 11, 4)])
        self.assertEqual(select_dates(None, None, scheduled=True, go_live=date(2026, 11, 5),
                                      today=date(2026, 11, 5)), [])

    def test_large_backlog_fails_instead_of_silently_skipping(self):
        with self.assertRaisesRegex(ValueError, "missing days"):
            select_dates(None, None, scheduled=True, go_live=date(2026, 11, 1),
                         today=date(2026, 11, 20))


if __name__ == "__main__":
    unittest.main()

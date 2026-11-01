#!/usr/bin/env python3
"""Choose bounded daily batches for a manual run or a scheduled catch-up."""

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from config import Config


FIRST_DAY = date(2025, 10, 1)
MAX_DAYS = 7  # Keep a single cloud run bounded; recover larger gaps in stages.


def select_dates(start, end, *, scheduled=False, go_live=None, completed=(), today=None):
    if scheduled:
        if go_live is None or go_live < FIRST_DAY:
            raise ValueError("Scheduled runs require a valid ECOBOTTLE_DAILY_START_DATE")
        if today is None:
            today = datetime.now(ZoneInfo("America/Argentina/Buenos_Aires")).date()
        yesterday = today - timedelta(days=1)
        start, end = go_live, yesterday
        if end < start:
            return []
    elif start is None:
        if end is not None:
            raise ValueError("daily_end requires daily_date")
        return []
    elif end is None:
        end = start
    if start < FIRST_DAY or end < start:
        raise ValueError("Invalid daily date range")
    if not scheduled and (end - start).days >= MAX_DAYS:
        raise ValueError(f"Manual runs are limited to {MAX_DAYS} consecutive days")
    if scheduled:
        missing = [start + timedelta(days=offset) for offset in range((end - start).days + 1)
                   if (start + timedelta(days=offset)).isoformat() not in completed]
        if len(missing) > MAX_DAYS:
            raise ValueError(f"{len(missing)} missing days since {go_live}; recover with manual ranges of at most {MAX_DAYS} days before scheduling resumes")
        return missing
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scheduled", action="store_true")
    parser.add_argument("--date", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--go-live", type=date.fromisoformat)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.scheduled and (args.date or args.end):
        parser.error("Scheduled runs cannot specify manual dates")
    if not args.scheduled and args.go_live:
        parser.error("--go-live is only for scheduled runs")
    completed = set()
    if args.scheduled:
        # Query only after the historical bootstrap and daily schema checks succeed.
        config = Config.from_env()
        rows = config.query(config.client(),
                            f"SELECT b.batch_id FROM `{config.project}.ecobottle_ops.daily_batches` b "
                            f"JOIN `{config.project}.ecobottle_ops.daily_validations` v "
                            "ON b.batch_id = v.batch_id AND b.fingerprint = v.fingerprint "
                            "WHERE b.status = 'complete'")
        completed = {row.batch_id for row in rows}
    days = select_dates(args.date, args.end, scheduled=args.scheduled,
                        go_live=args.go_live, completed=completed)
    args.out.write_text("".join(f"{day.isoformat()}\n" for day in days))
    print(f"Selected {len(days)} daily batch(es): {', '.join(map(str, days)) or 'none'}")


if __name__ == "__main__":
    main()

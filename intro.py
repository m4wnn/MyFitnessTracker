#!/usr/bin/env python3
"""Smoke test for Garmin Connect authentication and first summary fetch."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from myfitnesstracker.analysis import daily_summary_frame
from myfitnesstracker.client import build_client
from myfitnesstracker.config import load_project_config
from myfitnesstracker.download import fetch_last_activity, fetch_recent_user_summary
from myfitnesstracker.summary import render_intro_report


def main() -> int:
    try:
        config = load_project_config(PROJECT_ROOT)
        client = build_client(config)
        summary_date, summary = fetch_recent_user_summary(client, start=date.today())
        last_activity = fetch_last_activity(client)
    except Exception as exc:
        print(f"Connection test failed: {exc}", file=sys.stderr)
        return 1

    print(
        render_intro_report(
            email=config.email,
            full_name=client.get_full_name(),
            unit_system=client.get_unit_system(),
            summary_date=summary_date,
            summary=summary,
            last_activity=last_activity,
            token_store=config.token_store,
        )
    )

    frame = daily_summary_frame(summary, summary_date)
    preview_columns = ", ".join(frame.columns[:8].tolist())
    print()
    print(f"Pandas frame ready with {len(frame.columns)} columns.")
    print(f"First columns: {preview_columns}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

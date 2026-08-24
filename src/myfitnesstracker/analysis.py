"""Small pandas-based analysis helpers."""

from __future__ import annotations

from datetime import date

import pandas as pd


def daily_summary_frame(summary: dict, summary_date: date) -> pd.DataFrame:
    row = dict(summary)
    row["summary_date"] = summary_date.isoformat()
    return pd.DataFrame([row])

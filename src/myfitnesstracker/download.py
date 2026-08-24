"""Download helpers for Garmin Connect endpoints."""

from __future__ import annotations

from datetime import date, timedelta


def fetch_user_summary(client, day: date) -> dict:
    """Fetch the Garmin daily user summary for a specific calendar date."""

    return client.get_user_summary(day.isoformat())


def fetch_recent_user_summary(client, start: date, lookback_days: int = 7) -> tuple[date, dict]:
    """Fetch the most recent available Garmin daily summary near a target date.

    Args:
        client: Authenticated Garmin client.
        start: Date to probe first.
        lookback_days: Maximum number of days to walk backwards.

    Returns:
        The first date with data and its summary payload.
    """

    last_error = None
    for offset in range(lookback_days + 1):
        candidate = start - timedelta(days=offset)
        try:
            return candidate, fetch_user_summary(client, candidate)
        except Exception as exc:  # pragma: no cover - network/remote behavior
            last_error = exc
    if last_error is None:
        raise RuntimeError("Could not fetch any daily summary.")
    raise last_error


def fetch_last_activity(client) -> dict | None:
    """Fetch the most recent activity available through Garmin Connect."""

    return client.get_last_activity()

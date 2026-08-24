"""Human-readable summaries for console output."""

from __future__ import annotations

from datetime import date
from pathlib import Path


def render_intro_report(
    *,
    email: str,
    full_name: str | None,
    unit_system: str | None,
    summary_date: date,
    summary: dict,
    last_activity: dict | None,
    token_store: Path,
) -> str:
    lines = [
        "Connection OK",
        f"User: {full_name or email}",
        f"Unit system: {unit_system or 'unknown'}",
        f"Token store: {token_store}",
        f"Summary date: {summary_date.isoformat()}",
    ]

    metric_lines = [
        ("Steps", summary.get("steps")),
        ("Distance km", _format_distance(summary.get("distanceMeters"))),
        ("Calories", summary.get("totalKilocalories")),
        ("Active calories", summary.get("activeKilocalories")),
        ("Resting HR", summary.get("restingHeartRate")),
        ("Moderate minutes", summary.get("moderateIntensityMinutes")),
        ("Vigorous minutes", summary.get("vigorousIntensityMinutes")),
    ]
    for label, value in metric_lines:
        if value is not None:
            lines.append(f"{label}: {value}")

    if last_activity:
        activity_name = last_activity.get("activityName") or "unknown"
        activity_start = last_activity.get("startTimeLocal") or "unknown"
        activity_type = (last_activity.get("activityType") or {}).get("typeKey", "unknown")
        lines.append(
            f"Last activity: {activity_name} [{activity_type}] at {activity_start}"
        )

    return "\n".join(lines)


def _format_distance(distance_meters: float | int | None) -> str | None:
    if distance_meters is None:
        return None
    return f"{float(distance_meters) / 1000:.2f}"

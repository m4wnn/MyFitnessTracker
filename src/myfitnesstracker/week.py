"""Canonical weekly windows for Sunday-through-Saturday reporting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from .config import DEFAULT_TIMEZONE_NAME

SelectionMode = Literal["official", "preview_current", "explicit"]
WeekState = Literal["closed", "incomplete", "future"]


@dataclass(frozen=True, slots=True)
class WeekWindow:
    """Canonical Sunday-through-Saturday reporting window.

    Attributes:
        start_date: Sunday that opens the reporting window.
        end_date: Saturday that closes the reporting window.
        end_exclusive_date: Following Sunday; useful for interval comparisons.
        timezone_name: IANA timezone used to interpret local dates.
    """

    start_date: date
    end_date: date
    end_exclusive_date: date
    timezone_name: str = DEFAULT_TIMEZONE_NAME

    def __post_init__(self) -> None:
        """Validate that the window matches the canonical 7-day contract."""

        if self.start_date.weekday() != 6:
            raise ValueError(
                "WeekWindow.start_date must be a Sunday "
                f"(received {self.start_date.isoformat()})."
            )
        if self.end_exclusive_date - self.start_date != timedelta(days=7):
            raise ValueError("WeekWindow must span exactly 7 calendar days.")
        if self.end_date != self.end_exclusive_date - timedelta(days=1):
            raise ValueError("WeekWindow.end_date must be the Saturday before end_exclusive_date.")

    @property
    def week_id(self) -> str:
        """Return the canonical identifier for the reporting week."""

        return self.start_date.isoformat()

    def to_dict(self) -> dict[str, str]:
        """Serialize the window to plain strings for logs and manifests."""

        return {
            "week_id": self.week_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "end_exclusive_date": self.end_exclusive_date.isoformat(),
            "timezone_name": self.timezone_name,
        }


@dataclass(frozen=True, slots=True)
class ResolvedWeek:
    """Selected reporting window plus its lifecycle state."""

    window: WeekWindow
    selection_mode: SelectionMode
    week_state: WeekState
    reference_date: date

    @property
    def week_id(self) -> str:
        """Return the canonical week identifier."""

        return self.window.week_id

    def to_dict(self) -> dict[str, str]:
        """Serialize the resolved week for CLI output."""

        payload = self.window.to_dict()
        payload.update(
            {
                "selection_mode": self.selection_mode,
                "week_state": self.week_state,
                "reference_date": self.reference_date.isoformat(),
            }
        )
        return payload


def local_today(timezone_name: str = DEFAULT_TIMEZONE_NAME) -> date:
    """Return the local date for the configured project timezone."""

    return datetime.now(ZoneInfo(timezone_name)).date()


def week_for_day(day: date, timezone_name: str = DEFAULT_TIMEZONE_NAME) -> WeekWindow:
    """Build the canonical reporting week that contains a local date."""

    start_date = day - timedelta(days=_days_since_sunday(day))
    return week_from_start_date(start_date, timezone_name=timezone_name)


def week_from_start_date(
    start_date: date,
    timezone_name: str = DEFAULT_TIMEZONE_NAME,
) -> WeekWindow:
    """Construct a canonical reporting week from its Sunday start date."""

    end_exclusive_date = start_date + timedelta(days=7)
    end_date = end_exclusive_date - timedelta(days=1)
    return WeekWindow(
        start_date=start_date,
        end_date=end_date,
        end_exclusive_date=end_exclusive_date,
        timezone_name=timezone_name,
    )


def previous_week(window: WeekWindow) -> WeekWindow:
    """Return the canonical reporting week immediately before another one."""

    return week_from_start_date(
        start_date=window.start_date - timedelta(days=7),
        timezone_name=window.timezone_name,
    )


def resolve_official_week(
    reference_date: date | None = None,
    timezone_name: str = DEFAULT_TIMEZONE_NAME,
) -> ResolvedWeek:
    """Resolve the most recent fully closed official week.

    The project treats the week in progress as non-official. Therefore the
    official week for any reference date is always the immediately preceding
    Sunday-through-Saturday window.
    """

    local_reference = reference_date or local_today(timezone_name)
    current_week = week_for_day(local_reference, timezone_name=timezone_name)
    official_week = previous_week(current_week)
    return ResolvedWeek(
        window=official_week,
        selection_mode="official",
        week_state="closed",
        reference_date=local_reference,
    )


def resolve_preview_current_week(
    reference_date: date | None = None,
    timezone_name: str = DEFAULT_TIMEZONE_NAME,
) -> ResolvedWeek:
    """Resolve the current open week as a non-official preview window."""

    local_reference = reference_date or local_today(timezone_name)
    current_week = week_for_day(local_reference, timezone_name=timezone_name)
    return ResolvedWeek(
        window=current_week,
        selection_mode="preview_current",
        week_state=_week_state_for_window(current_week, local_reference),
        reference_date=local_reference,
    )


def resolve_explicit_week(
    start_date: date,
    *,
    reference_date: date | None = None,
    timezone_name: str = DEFAULT_TIMEZONE_NAME,
) -> ResolvedWeek:
    """Resolve an explicitly requested week by its Sunday start date."""

    local_reference = reference_date or local_today(timezone_name)
    explicit_week = week_from_start_date(start_date, timezone_name=timezone_name)
    return ResolvedWeek(
        window=explicit_week,
        selection_mode="explicit",
        week_state=_week_state_for_window(explicit_week, local_reference),
        reference_date=local_reference,
    )


def _days_since_sunday(day: date) -> int:
    """Return the offset between a date and its preceding Sunday."""

    # Python counts Monday as 0 and Sunday as 6. The modulo remaps Sunday to 0.
    return (day.weekday() + 1) % 7


def _week_state_for_window(window: WeekWindow, reference_date: date) -> WeekState:
    """Classify a reporting week as closed, incomplete or future."""

    if reference_date >= window.end_exclusive_date:
        return "closed"
    if reference_date < window.start_date:
        return "future"
    return "incomplete"

"""Weekly export pipeline for Garmin-backed reporting bundles.

This module builds a debuggable weekly bundle by combining three layers:

1. Local SQLite summaries from GarminDB.
2. Local raw artifacts already cached on disk (JSON and FIT files).
3. Live Garmin Connect payloads when online access is enabled.

The output is intentionally redundant. Weekly CSV tables provide normalized
analysis inputs, while the raw JSON and FIT artifacts remain available for
manual inspection and deeper re-processing later.
"""

from __future__ import annotations

import csv
import io
import json
import shutil
import sqlite3
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from garminconnect import Garmin

from .client import build_client
from .config import ProjectConfig, load_project_config
from .data_sources import ResolvedDataSource, resolve_data_source
from .week import ResolvedWeek
from .week_registry import WeekRegistry


@dataclass(frozen=True, slots=True)
class WeeklyExportResult:
    """Summary of a completed weekly export."""

    week_id: str
    artifact_root: Path
    manifest_path: Path
    storage_bucket: str
    week_state: str
    source_data_root: Path
    source_data_label: str
    used_legacy_fallback: bool
    activities_count: int
    wellbeing_rows: int
    online_activity_count: int
    wellbeing_online_days: int
    fit_files_copied: int
    summary_json_copied: int
    details_json_copied: int
    records_exports: int
    online_estimates_status: str
    report_path: Path

    def to_dict(self) -> dict[str, Any]:
        """Serialize the export result for CLI output."""

        return {
            "week_id": self.week_id,
            "artifact_root": str(self.artifact_root),
            "manifest_path": str(self.manifest_path),
            "storage_bucket": self.storage_bucket,
            "week_state": self.week_state,
            "source_data_root": str(self.source_data_root),
            "source_data_label": self.source_data_label,
            "used_legacy_fallback": self.used_legacy_fallback,
            "activities_count": self.activities_count,
            "wellbeing_rows": self.wellbeing_rows,
            "online_activity_count": self.online_activity_count,
            "wellbeing_online_days": self.wellbeing_online_days,
            "fit_files_copied": self.fit_files_copied,
            "summary_json_copied": self.summary_json_copied,
            "details_json_copied": self.details_json_copied,
            "records_exports": self.records_exports,
            "online_estimates_status": self.online_estimates_status,
            "report_path": str(self.report_path),
        }


@dataclass(slots=True)
class ActivityCatalogEntry:
    """All local and online payloads associated with one activity."""

    activity_id: str
    local_row: dict[str, Any] | None = None
    local_summary_path: Path | None = None
    local_details_path: Path | None = None
    local_summary_payload: dict[str, Any] = field(default_factory=dict)
    local_details_payload: dict[str, Any] = field(default_factory=dict)
    online_list_payload: dict[str, Any] = field(default_factory=dict)
    online_summary_payload: dict[str, Any] = field(default_factory=dict)
    online_details_payload: dict[str, Any] = field(default_factory=dict)
    local_fit_paths: list[Path] = field(default_factory=list)


@dataclass(slots=True)
class OnlineContext:
    """Authenticated Garmin Connect session state for one export run."""

    client: Garmin | None
    status: str
    user_settings: dict[str, Any] = field(default_factory=dict)
    profile_settings: dict[str, Any] = field(default_factory=dict)
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class DailyOnlinePayload:
    """Raw Garmin Connect payloads collected for one calendar day."""

    date: str
    user_summary: dict[str, Any]
    sleep: dict[str, Any]
    hrv: dict[str, Any]
    body_battery: list[dict[str, Any]]
    body_composition: dict[str, Any]


def export_week_bundle(
    *,
    project_root: Path,
    resolved_week: ResolvedWeek,
    overwrite: bool = False,
    include_online_estimates: bool = True,
    include_debug_records: bool = True,
) -> WeeklyExportResult:
    """Export a weekly Garmin bundle from local and live Garmin sources.

    Args:
        project_root: Repository root for configuration and output paths.
        resolved_week: Selected week window to export.
        overwrite: Whether to reuse or rewrite an existing manifest.
        include_online_estimates: Whether to enable live Garmin Connect
            supplementation. When disabled, the exporter stays fully local.
        include_debug_records: Whether to dump per-record activity data from
            ``garmin_activities.db`` into ``debug/activity_records``.

    Returns:
        A structured summary of the export outputs that were written.
    """

    config = load_project_config(project_root)
    registry = WeekRegistry(project_root=project_root, timezone_name=config.timezone_name)
    prepared = registry.prepare_week(resolved_week, overwrite=overwrite)
    artifact_root = prepared.artifact_root
    data_source = resolve_data_source(config)

    online_context = _load_online_context(
        config=config,
        enable_online_sync=include_online_estimates,
    )
    activity_catalog = _build_local_activity_catalog(data_source, resolved_week)
    online_activities, activity_fetch_errors = _augment_activity_catalog_with_online_payloads(
        data_source=data_source,
        resolved_week=resolved_week,
        activity_catalog=activity_catalog,
        online_context=online_context,
    )
    sessions_df = _build_sessions_dataframe(activity_catalog)

    daily_online_payloads, wellbeing_fetch_errors = _fetch_online_wellbeing_payloads(
        resolved_week=resolved_week,
        online_context=online_context,
    )
    wellbeing_df = _build_wellbeing_dataframe(
        data_source=data_source,
        resolved_week=resolved_week,
        daily_online_payloads=daily_online_payloads,
    )
    laps_df = _build_laps_dataframe(data_source, sessions_df)
    file_inventory_df = _copy_activity_artifacts(
        activity_catalog=activity_catalog,
        sessions_df=sessions_df,
        artifact_root=artifact_root,
        online_context=online_context,
    )
    _write_activity_index_artifact(
        artifact_root=artifact_root,
        resolved_week=resolved_week,
        online_activities=online_activities,
        online_context=online_context,
        activity_fetch_errors=activity_fetch_errors,
    )
    _write_daily_online_payloads(
        artifact_root=artifact_root,
        daily_online_payloads=daily_online_payloads,
    )

    records_exports = 0
    if include_debug_records:
        records_exports = _export_activity_records(
            data_source=data_source,
            sessions_df=sessions_df,
            artifact_root=artifact_root,
        )

    _copy_profile_artifacts(data_source=data_source, artifact_root=artifact_root)
    online_estimates_status = _write_online_estimates(
        resolved_week=resolved_week,
        artifact_root=artifact_root,
        sessions_df=sessions_df,
        include_online_estimates=include_online_estimates,
        online_context=online_context,
        activity_fetch_errors=activity_fetch_errors,
        wellbeing_fetch_errors=wellbeing_fetch_errors,
    )

    sessions_path = artifact_root / "csv" / f"sesiones_{resolved_week.week_id}.csv"
    wellbeing_path = artifact_root / "csv" / f"bienestar_{resolved_week.week_id}.csv"
    enriched_path = artifact_root / "csv" / f"sesiones_enriquecidas_{resolved_week.week_id}.csv"
    laps_path = artifact_root / "csv" / f"laps_{resolved_week.week_id}.csv"
    inventory_path = artifact_root / "csv" / f"file_inventory_{resolved_week.week_id}.csv"
    export_context_path = artifact_root / "json" / f"export_context_{resolved_week.week_id}.json"
    report_path = artifact_root / f"reporte_{resolved_week.week_id}.md"

    _write_dataframe(_sessions_canonical_columns(sessions_df), sessions_path)
    _write_dataframe(sessions_df, enriched_path)
    _write_dataframe(wellbeing_df, wellbeing_path)
    _write_dataframe(laps_df, laps_path)
    _write_dataframe(file_inventory_df, inventory_path)

    _write_json(
        export_context_path,
        {
            "week": resolved_week.to_dict(),
            "artifact_root": str(artifact_root),
            "source_data_root": str(data_source.root),
            "source_data_label": data_source.source_label,
            "used_legacy_fallback": data_source.used_fallback,
            "activities_count": int(len(sessions_df)),
            "online_activity_count": len(online_activities),
            "wellbeing_rows": int(len(wellbeing_df)),
            "wellbeing_online_days": len(daily_online_payloads),
            "fit_files_copied": _artifact_count(file_inventory_df, "fit"),
            "summary_json_copied": _artifact_count(file_inventory_df, "activity_summary_json"),
            "details_json_copied": _artifact_count(file_inventory_df, "activity_details_json"),
            "records_exports": records_exports,
            "online_estimates_status": online_estimates_status,
            "activity_fetch_errors": activity_fetch_errors,
            "wellbeing_fetch_errors": wellbeing_fetch_errors,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
    )
    _write_text(
        report_path,
        _render_export_report(
            resolved_week=resolved_week,
            data_source=data_source,
            sessions_df=sessions_df,
            wellbeing_df=wellbeing_df,
            file_inventory_df=file_inventory_df,
            online_estimates_status=online_estimates_status,
            online_activity_count=len(online_activities),
            wellbeing_online_days=len(daily_online_payloads),
        ),
    )

    registry.update_manifest_status(
        prepared.manifest,
        run_status="exported",
    )

    return WeeklyExportResult(
        week_id=resolved_week.week_id,
        artifact_root=artifact_root,
        manifest_path=prepared.manifest_path,
        storage_bucket=prepared.manifest.storage_bucket,
        week_state=resolved_week.week_state,
        source_data_root=data_source.root,
        source_data_label=data_source.source_label,
        used_legacy_fallback=data_source.used_fallback,
        activities_count=int(len(sessions_df)),
        wellbeing_rows=int(len(wellbeing_df)),
        online_activity_count=len(online_activities),
        wellbeing_online_days=len(daily_online_payloads),
        fit_files_copied=_artifact_count(file_inventory_df, "fit"),
        summary_json_copied=_artifact_count(file_inventory_df, "activity_summary_json"),
        details_json_copied=_artifact_count(file_inventory_df, "activity_details_json"),
        records_exports=records_exports,
        online_estimates_status=online_estimates_status,
        report_path=report_path,
    )


def _load_online_context(
    *,
    config: ProjectConfig,
    enable_online_sync: bool,
) -> OnlineContext:
    """Authenticate Garmin Connect once and retain reusable profile payloads."""

    if not enable_online_sync:
        return OnlineContext(client=None, status="skipped")

    try:
        client = build_client(config)
        user_settings = client.connectapi("/userprofile-service/userprofile/user-settings")
        profile_settings = client.connectapi("/userprofile-service/userprofile/settings")
        return OnlineContext(
            client=client,
            status="ok",
            user_settings=user_settings or {},
            profile_settings=profile_settings or {},
        )
    except Exception as exc:  # pragma: no cover - remote behavior
        return OnlineContext(
            client=None,
            status="error",
            user_settings={},
            profile_settings={},
            error_type=type(exc).__name__,
            error_message=str(exc),
        )


def _build_local_activity_catalog(
    data_source: ResolvedDataSource,
    resolved_week: ResolvedWeek,
) -> dict[str, ActivityCatalogEntry]:
    """Load local SQLite rows and local raw artifacts for one reporting week."""

    activity_db_path = data_source.db_dir / "garmin_activities.db"
    if not activity_db_path.exists():
        return {}

    query = """
        SELECT
            activity_id,
            start_time,
            sport,
            name,
            elapsed_time,
            moving_time,
            distance,
            avg_hr,
            max_hr,
            avg_cadence,
            max_cadence,
            avg_speed,
            max_speed,
            avg_temperature,
            max_temperature,
            min_temperature,
            calories,
            training_load,
            training_effect
        FROM activities
        WHERE DATE(start_time) BETWEEN ? AND ?
        ORDER BY start_time
    """
    with sqlite3.connect(activity_db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            query,
            (
                resolved_week.window.start_date.isoformat(),
                resolved_week.window.end_date.isoformat(),
            ),
        ).fetchall()

    catalog: dict[str, ActivityCatalogEntry] = {}
    for row in rows:
        row_dict = dict(row)
        activity_id = str(row_dict["activity_id"])
        entry = ActivityCatalogEntry(
            activity_id=activity_id,
            local_row=row_dict,
        )
        _hydrate_local_activity_entry(entry, data_source.activities_dir)
        catalog[activity_id] = entry

    return catalog


def _hydrate_local_activity_entry(entry: ActivityCatalogEntry, activities_dir: Path) -> None:
    """Attach local JSON and FIT artifacts to an activity entry when present."""

    summary_path = activities_dir / f"activity_{entry.activity_id}.json"
    details_path = activities_dir / f"activity_details_{entry.activity_id}.json"
    if summary_path.exists():
        entry.local_summary_path = summary_path
        entry.local_summary_payload = _load_json_if_exists(summary_path)
    if details_path.exists():
        entry.local_details_path = details_path
        entry.local_details_payload = _load_json_if_exists(details_path)
    entry.local_fit_paths = sorted(activities_dir.glob(f"*{entry.activity_id}*.fit"))


def _augment_activity_catalog_with_online_payloads(
    *,
    data_source: ResolvedDataSource,
    resolved_week: ResolvedWeek,
    activity_catalog: dict[str, ActivityCatalogEntry],
    online_context: OnlineContext,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Supplement the catalog with live Garmin Connect activity payloads."""

    if online_context.client is None:
        return [], []

    effective_end_date = min(resolved_week.window.end_date, resolved_week.reference_date)
    if effective_end_date < resolved_week.window.start_date:
        return [], []

    client = online_context.client
    errors: list[dict[str, str]] = []
    try:
        activities = client.get_activities_by_date(
            resolved_week.window.start_date.isoformat(),
            effective_end_date.isoformat(),
            sortorder="asc",
        )
    except Exception as exc:  # pragma: no cover - remote behavior
        return [], [_error_payload("activities_index", None, exc)]

    for payload in activities:
        activity_id = str(payload.get("activityId") or "").strip()
        if not activity_id:
            continue
        entry = activity_catalog.setdefault(activity_id, ActivityCatalogEntry(activity_id=activity_id))
        entry.online_list_payload = payload
        if not entry.local_summary_payload and not entry.local_details_payload and not entry.local_fit_paths:
            _hydrate_local_activity_entry(entry, data_source.activities_dir)

    for payload in activities:
        activity_id = str(payload.get("activityId") or "").strip()
        if not activity_id:
            continue
        entry = activity_catalog[activity_id]
        try:
            entry.online_summary_payload = client.get_activity(activity_id)
        except Exception as exc:  # pragma: no cover - remote behavior
            errors.append(_error_payload("activity_summary", activity_id, exc))
        try:
            entry.online_details_payload = client.get_activity_details(activity_id)
        except Exception as exc:  # pragma: no cover - remote behavior
            errors.append(_error_payload("activity_details", activity_id, exc))

    return activities, errors


def _build_sessions_dataframe(
    activity_catalog: dict[str, ActivityCatalogEntry],
) -> pd.DataFrame:
    """Build a detailed per-activity DataFrame for a reporting week."""

    records = [
        _build_session_row(entry)
        for entry in activity_catalog.values()
    ]
    if not records:
        return pd.DataFrame()

    frame = pd.DataFrame(records)
    if "start_time" in frame.columns:
        frame = frame.sort_values(by=["start_time", "activity_id"], na_position="last")
    return frame.reset_index(drop=True)


def _build_session_row(entry: ActivityCatalogEntry) -> dict[str, Any]:
    """Normalize one activity into the enriched weekly session row format."""

    local_row = entry.local_row or {}
    local_summary = entry.local_summary_payload or {}
    local_details_summary = _summary_dto(entry.local_details_payload)
    online_list = entry.online_list_payload or {}
    online_summary_root = entry.online_summary_payload or {}
    online_summary_dto = _summary_dto(online_summary_root)

    metric_sources = [
        online_list,
        online_summary_dto,
        local_summary,
        local_details_summary,
    ]

    start_time = _first_non_null(
        online_list.get("startTimeLocal"),
        local_summary.get("startTimeLocal"),
        local_row.get("start_time"),
    )
    if start_time is None:
        start_time = _choose_path(
            [online_summary_root],
            ("summaryDTO", "startTimeLocal"),
            ("metadataDTO", "startTimeLocal"),
        )

    start_date = str(start_time)[:10] if start_time else _first_non_null(
        local_row.get("start_time", "")[:10] if local_row.get("start_time") else None,
        local_row.get("date"),
    )
    distance_km = _distance_to_km_from_sources(metric_sources, local_row)

    return {
        "activity_id": entry.activity_id,
        "date": start_date,
        "start_time": start_time,
        "sport": _first_non_null(
            _choose_path([online_summary_root], ("activityTypeDTO", "typeKey")),
            _choose_path([online_list], ("activityType", "typeKey")),
            _choose_path([local_summary], ("activityType", "typeKey")),
            local_row.get("sport"),
        ),
        "name": _first_non_null(
            online_summary_root.get("activityName"),
            online_list.get("activityName"),
            local_summary.get("activityName"),
            local_row.get("name"),
        ),
        "duration_seconds": _coerce_duration_seconds(
            _choose_first(*metric_sources, "duration", "elapsedDuration")
            or local_row.get("elapsed_time")
        ),
        "moving_duration_seconds": _coerce_duration_seconds(
            _choose_first(*metric_sources, "movingDuration")
            or local_row.get("moving_time")
        ),
        "distance_km": distance_km,
        "avg_hr_bpm": _choose_first(*metric_sources, "averageHR", "avgHR") or local_row.get("avg_hr"),
        "max_hr_bpm": _choose_first(*metric_sources, "maxHR") or local_row.get("max_hr"),
        "avg_power_w": _choose_first(*metric_sources, "avgPower", "averagePower"),
        "max_power_w": _choose_first(*metric_sources, "maxPower"),
        "normalized_power_w": _choose_first(*metric_sources, "normPower", "normalizedPower"),
        "tss": _choose_first(*metric_sources, "trainingStressScore"),
        "training_load": _choose_first(*metric_sources, "activityTrainingLoad", "trainingLoad")
        or local_row.get("training_load"),
        "training_effect": _choose_first(
            *metric_sources,
            "aerobicTrainingEffect",
            "trainingEffect",
        )
        or local_row.get("training_effect"),
        "avg_respiration_rate": _choose_first(*metric_sources, "avgRespirationRate"),
        "min_respiration_rate": _choose_first(*metric_sources, "minRespirationRate"),
        "max_respiration_rate": _choose_first(*metric_sources, "maxRespirationRate"),
        "avg_cadence_rpm": _choose_first(
            *metric_sources,
            "averageBikingCadenceInRevPerMinute",
            "averageBikeCadence",
        )
        or local_row.get("avg_cadence"),
        "max_cadence_rpm": _choose_first(
            *metric_sources,
            "maxBikingCadenceInRevPerMinute",
            "maxBikeCadence",
        )
        or local_row.get("max_cadence"),
        "avg_speed_mps": _choose_first(*metric_sources, "averageSpeed") or local_row.get("avg_speed"),
        "max_speed_mps": _choose_first(*metric_sources, "maxSpeed") or local_row.get("max_speed"),
        "avg_temperature_c": _choose_first(*metric_sources, "averageTemperature") or local_row.get("avg_temperature"),
        "max_temperature_c": _choose_first(*metric_sources, "maxTemperature") or local_row.get("max_temperature"),
        "min_temperature_c": _choose_first(*metric_sources, "minTemperature") or local_row.get("min_temperature"),
        "calories_total": _choose_first(*metric_sources, "calories") or local_row.get("calories"),
        "intensity_factor": _choose_first(*metric_sources, "intensityFactor"),
        "functional_threshold_power_w": _choose_first(*metric_sources, "functionalThresholdPower"),
        "activity_type_key": _first_non_null(
            _choose_path([online_summary_root], ("activityTypeDTO", "typeKey")),
            _choose_path([online_list], ("activityType", "typeKey")),
            _choose_path([local_summary], ("activityType", "typeKey")),
        ),
        "lap_count": _first_non_null(
            online_list.get("lapCount"),
            local_summary.get("lapCount"),
            local_details_summary.get("lapCount"),
        ),
        "summary_json_exists": 1
        if (entry.local_summary_payload or entry.online_summary_payload or entry.online_list_payload)
        else 0,
        "details_json_exists": 1 if (entry.local_details_payload or entry.online_details_payload) else 0,
        "fit_file_count": len(entry.local_fit_paths),
        "summary_json_path": str(entry.local_summary_path) if entry.local_summary_path else "",
        "details_json_path": str(entry.local_details_path) if entry.local_details_path else "",
        "source_fit_paths": json.dumps([str(path) for path in entry.local_fit_paths]),
        "online_summary_available": 1 if entry.online_summary_payload else 0,
        "online_details_available": 1 if entry.online_details_payload else 0,
        "local_sql_available": 1 if local_row else 0,
        "hr_time_in_zone_1_s": _choose_first(*metric_sources, "hrTimeInZone_1"),
        "hr_time_in_zone_2_s": _choose_first(*metric_sources, "hrTimeInZone_2"),
        "hr_time_in_zone_3_s": _choose_first(*metric_sources, "hrTimeInZone_3"),
        "hr_time_in_zone_4_s": _choose_first(*metric_sources, "hrTimeInZone_4"),
        "hr_time_in_zone_5_s": _choose_first(*metric_sources, "hrTimeInZone_5"),
        "power_time_in_zone_1_s": _choose_first(*metric_sources, "powerTimeInZone_1"),
        "power_time_in_zone_2_s": _choose_first(*metric_sources, "powerTimeInZone_2"),
        "power_time_in_zone_3_s": _choose_first(*metric_sources, "powerTimeInZone_3"),
        "power_time_in_zone_4_s": _choose_first(*metric_sources, "powerTimeInZone_4"),
        "power_time_in_zone_5_s": _choose_first(*metric_sources, "powerTimeInZone_5"),
        "power_time_in_zone_6_s": _choose_first(*metric_sources, "powerTimeInZone_6"),
        "power_time_in_zone_7_s": _choose_first(*metric_sources, "powerTimeInZone_7"),
        "difference_body_battery": _choose_first(*metric_sources, "differenceBodyBattery"),
    }


def _distance_to_km_from_sources(
    metric_sources: list[dict[str, Any]],
    local_row: dict[str, Any],
) -> float | None:
    """Resolve activity distance with correct unit handling."""

    for source in metric_sources:
        if "distance" in source and source.get("distance") is not None:
            return _meters_to_km(source.get("distance"))
        if "totalDistanceMeters" in source and source.get("totalDistanceMeters") is not None:
            return _meters_to_km(source.get("totalDistanceMeters"))
    return _safe_float(local_row.get("distance"))


def _fetch_online_wellbeing_payloads(
    *,
    resolved_week: ResolvedWeek,
    online_context: OnlineContext,
) -> tuple[dict[str, DailyOnlinePayload], list[dict[str, str]]]:
    """Collect live day-level wellbeing payloads for the queryable days only."""

    if online_context.client is None:
        return {}, []

    client = online_context.client
    errors: list[dict[str, str]] = []
    payloads: dict[str, DailyOnlinePayload] = {}
    current_day = resolved_week.window.start_date
    last_queryable_day = min(resolved_week.window.end_date, resolved_week.reference_date)

    while current_day <= last_queryable_day:
        day = current_day.isoformat()
        user_summary: dict[str, Any] = {}
        sleep: dict[str, Any] = {}
        hrv: dict[str, Any] = {}
        body_battery: list[dict[str, Any]] = []
        body_composition: dict[str, Any] = {}

        try:
            user_summary = client.get_user_summary(day) or {}
        except Exception as exc:  # pragma: no cover - remote behavior
            errors.append(_error_payload("user_summary", day, exc))
        try:
            sleep = client.get_sleep_data(day) or {}
        except Exception as exc:  # pragma: no cover - remote behavior
            errors.append(_error_payload("sleep", day, exc))
        try:
            hrv = client.get_hrv_data(day) or {}
        except Exception as exc:  # pragma: no cover - remote behavior
            errors.append(_error_payload("hrv", day, exc))
        try:
            body_battery = client.get_body_battery(day, day) or []
        except Exception as exc:  # pragma: no cover - remote behavior
            errors.append(_error_payload("body_battery", day, exc))
        try:
            body_composition = client.get_body_composition(day, day) or {}
        except Exception as exc:  # pragma: no cover - remote behavior
            errors.append(_error_payload("body_composition", day, exc))

        payloads[day] = DailyOnlinePayload(
            date=day,
            user_summary=user_summary,
            sleep=sleep,
            hrv=hrv,
            body_battery=body_battery,
            body_composition=body_composition,
        )
        current_day += timedelta(days=1)

    return payloads, errors


def _build_wellbeing_dataframe(
    data_source: ResolvedDataSource,
    resolved_week: ResolvedWeek,
    daily_online_payloads: dict[str, DailyOnlinePayload],
) -> pd.DataFrame:
    """Build the weekly wellbeing DataFrame with one row per calendar day."""

    records_by_day = _build_local_wellbeing_row_map(data_source, resolved_week)
    for day, payload in daily_online_payloads.items():
        online_row = _build_online_wellbeing_row(payload, resolved_week)
        base_row = records_by_day.get(day, _blank_wellbeing_row(day, resolved_week))
        records_by_day[day] = _overlay_record(base_row, online_row)

    records: list[dict[str, Any]] = []
    current_day = resolved_week.window.start_date
    while current_day <= resolved_week.window.end_date:
        day = current_day.isoformat()
        records.append(records_by_day.get(day, _blank_wellbeing_row(day, resolved_week)))
        current_day += timedelta(days=1)

    return pd.DataFrame(records)


def _build_local_wellbeing_row_map(
    data_source: ResolvedDataSource,
    resolved_week: ResolvedWeek,
) -> dict[str, dict[str, Any]]:
    """Read local GarminDB wellbeing summaries and expand them to 7 daily rows."""

    garmin_db_path = data_source.db_dir / "garmin.db"
    row_by_day: dict[str, tuple[Any, ...]] = {}
    if garmin_db_path.exists():
        query = """
            SELECT
                d.day AS date,
                rh.resting_heart_rate AS resting_hr_bpm,
                h.last_night_avg AS hrv_last_night_avg_ms,
                h.weekly_avg AS hrv_weekly_avg_ms,
                h.status AS hrv_status,
                s.total_sleep AS total_sleep_text,
                s.score AS sleep_score,
                d.bb_min AS body_battery_min,
                d.bb_max AS body_battery_max,
                d.bb_charged AS body_battery_charged,
                w.weight AS weight_kg,
                d.steps AS steps,
                d.distance AS distance_km,
                d.calories_total AS calories_total,
                d.calories_active AS calories_active,
                d.moderate_activity_time AS moderate_activity_time,
                d.vigorous_activity_time AS vigorous_activity_time
            FROM daily_summary d
            LEFT JOIN sleep s ON s.day = d.day
            LEFT JOIN weight w ON w.day = d.day
            LEFT JOIN resting_hr rh ON rh.day = d.day
            LEFT JOIN hrv h ON h.day = d.day
            WHERE DATE(d.day) BETWEEN ? AND ?
            ORDER BY d.day
        """
        with sqlite3.connect(garmin_db_path) as connection:
            rows = connection.execute(
                query,
                (
                    resolved_week.window.start_date.isoformat(),
                    resolved_week.window.end_date.isoformat(),
                ),
            ).fetchall()
        row_by_day = {str(row[0])[:10]: row for row in rows}

    records_by_day: dict[str, dict[str, Any]] = {}
    current_day = resolved_week.window.start_date
    while current_day <= resolved_week.window.end_date:
        key = current_day.isoformat()
        row = row_by_day.get(key)
        if row is None:
            records_by_day[key] = _blank_wellbeing_row(key, resolved_week)
            current_day += timedelta(days=1)
            continue

        sleep_hours = _time_text_to_hours(row[5])
        records_by_day[key] = {
            "date": key,
            "resting_hr_bpm": row[1],
            "hrv_last_night_avg_ms": row[2],
            "hrv_weekly_avg_ms": row[3],
            "hrv_status": row[4],
            "sleep_hours": sleep_hours,
            "sleep_score": row[6],
            "body_battery_min": row[7],
            "body_battery_max": row[8],
            "body_battery_charged": row[9],
            "weight_kg": row[10],
            "watch_worn_night": 1 if sleep_hours and sleep_hours > 0 else 0,
            "steps": row[11],
            "distance_km": row[12],
            "calories_total": row[13],
            "calories_active": row[14],
            "moderate_activity_minutes": _time_text_to_seconds(row[15]) / 60 if row[15] else None,
            "vigorous_activity_minutes": _time_text_to_seconds(row[16]) / 60 if row[16] else None,
            "is_future_day": 1 if current_day > resolved_week.reference_date else 0,
        }
        current_day += timedelta(days=1)

    return records_by_day


def _build_online_wellbeing_row(
    payload: DailyOnlinePayload,
    resolved_week: ResolvedWeek,
) -> dict[str, Any]:
    """Normalize one day of live Garmin Connect wellbeing payloads."""

    sleep_dto = payload.sleep.get("dailySleepDTO") or {}
    hrv_summary = payload.hrv.get("hrvSummary") or {}
    body_battery_day = payload.body_battery[0] if payload.body_battery else {}
    body_comp_total_avg = payload.body_composition.get("totalAverage") or {}
    sleep_hours = _seconds_to_hours(sleep_dto.get("sleepTimeSeconds"))

    return {
        "date": payload.date,
        "resting_hr_bpm": _first_non_null(
            payload.user_summary.get("restingHeartRate"),
            payload.sleep.get("restingHeartRate"),
        ),
        "hrv_last_night_avg_ms": _first_non_null(
            hrv_summary.get("lastNightAvg"),
            payload.sleep.get("avgOvernightHrv"),
        ),
        "hrv_weekly_avg_ms": hrv_summary.get("weeklyAvg"),
        "hrv_status": _first_non_null(
            hrv_summary.get("status"),
            payload.sleep.get("hrvStatus"),
        ),
        "sleep_hours": sleep_hours,
        "sleep_score": _extract_sleep_score(sleep_dto),
        "body_battery_min": _first_non_null(
            payload.user_summary.get("bodyBatteryLowestValue"),
            _safe_min(body_battery_day.get("bodyBatteryValuesArray")),
        ),
        "body_battery_max": _first_non_null(
            payload.user_summary.get("bodyBatteryHighestValue"),
            _safe_max(body_battery_day.get("bodyBatteryValuesArray")),
        ),
        "body_battery_charged": _first_non_null(
            payload.user_summary.get("bodyBatteryChargedValue"),
            body_battery_day.get("charged"),
        ),
        "weight_kg": _first_non_null(
            body_comp_total_avg.get("weight"),
            _extract_weight_from_body_composition(payload.body_composition),
        ),
        "watch_worn_night": 1 if sleep_hours and sleep_hours > 0 else 0,
        "steps": payload.user_summary.get("totalSteps"),
        "distance_km": _meters_to_km(payload.user_summary.get("totalDistanceMeters")),
        "calories_total": payload.user_summary.get("totalKilocalories"),
        "calories_active": _first_non_null(
            payload.user_summary.get("activeKilocalories"),
            payload.user_summary.get("wellnessActiveKilocalories"),
        ),
        "moderate_activity_minutes": payload.user_summary.get("moderateIntensityMinutes"),
        "vigorous_activity_minutes": payload.user_summary.get("vigorousIntensityMinutes"),
        "is_future_day": 1 if payload.date > resolved_week.reference_date.isoformat() else 0,
    }


def _blank_wellbeing_row(
    day: str,
    resolved_week: ResolvedWeek,
) -> dict[str, Any]:
    """Return an empty wellbeing row that preserves date and future-day flags."""

    return {
        "date": day,
        "resting_hr_bpm": None,
        "hrv_last_night_avg_ms": None,
        "hrv_weekly_avg_ms": None,
        "hrv_status": None,
        "sleep_hours": None,
        "sleep_score": None,
        "body_battery_min": None,
        "body_battery_max": None,
        "body_battery_charged": None,
        "weight_kg": None,
        "watch_worn_night": 0,
        "steps": None,
        "distance_km": None,
        "calories_total": None,
        "calories_active": None,
        "moderate_activity_minutes": None,
        "vigorous_activity_minutes": None,
        "is_future_day": 1 if day > resolved_week.reference_date.isoformat() else 0,
    }


def _overlay_record(
    base_row: dict[str, Any],
    overlay_row: dict[str, Any],
) -> dict[str, Any]:
    """Merge two row dictionaries while preferring non-null overlay values."""

    merged = dict(base_row)
    for key, value in overlay_row.items():
        if key == "date":
            merged[key] = value
            continue
        if value is not None:
            merged[key] = value
    return merged


def _build_laps_dataframe(
    data_source: ResolvedDataSource,
    sessions_df: pd.DataFrame,
) -> pd.DataFrame:
    """Export per-lap summaries for every activity found in local GarminDB."""

    if sessions_df.empty:
        return pd.DataFrame()

    garmin_activities_path = data_source.db_dir / "garmin_activities.db"
    if not garmin_activities_path.exists():
        return pd.DataFrame()

    activity_ids = [str(value) for value in sessions_df["activity_id"].tolist()]
    placeholders = ",".join("?" for _ in activity_ids)
    query = f"""
        SELECT
            activity_id,
            lap,
            start_time,
            stop_time,
            elapsed_time,
            moving_time,
            distance,
            avg_hr,
            max_hr,
            avg_cadence,
            max_cadence,
            avg_speed,
            max_speed,
            avg_temperature,
            max_temperature,
            min_temperature,
            calories
        FROM activity_laps
        WHERE activity_id IN ({placeholders})
        ORDER BY activity_id, lap
    """
    with sqlite3.connect(garmin_activities_path) as connection:
        rows = connection.execute(query, activity_ids).fetchall()

    records: list[dict[str, Any]] = []
    for row in rows:
        records.append(
            {
                "activity_id": str(row[0]),
                "lap": row[1],
                "start_time": row[2],
                "stop_time": row[3],
                "elapsed_seconds": _time_text_to_seconds(row[4]),
                "moving_seconds": _time_text_to_seconds(row[5]),
                "distance_km": _safe_float(row[6]),
                "avg_hr_bpm": row[7],
                "max_hr_bpm": row[8],
                "avg_cadence_rpm": row[9],
                "max_cadence_rpm": row[10],
                "avg_speed_mps": row[11],
                "max_speed_mps": row[12],
                "avg_temperature_c": row[13],
                "max_temperature_c": row[14],
                "min_temperature_c": row[15],
                "calories": row[16],
            }
        )
    return pd.DataFrame(records)


def _copy_activity_artifacts(
    *,
    activity_catalog: dict[str, ActivityCatalogEntry],
    sessions_df: pd.DataFrame,
    artifact_root: Path,
    online_context: OnlineContext,
) -> pd.DataFrame:
    """Copy or materialize activity JSON and FIT artifacts into the bundle."""

    json_activities_dir = artifact_root / "json" / "activities"
    json_details_dir = artifact_root / "json" / "activity_details"
    fit_dir = artifact_root / "fit"
    json_activities_dir.mkdir(parents=True, exist_ok=True)
    json_details_dir.mkdir(parents=True, exist_ok=True)
    fit_dir.mkdir(parents=True, exist_ok=True)

    inventory_records: list[dict[str, Any]] = []
    rows_by_activity_id = {
        str(row["activity_id"]): row
        for row in sessions_df.to_dict(orient="records")
    }

    for activity_id, row in rows_by_activity_id.items():
        entry = activity_catalog.get(activity_id)
        if entry is None:
            continue

        start_date = row.get("date") or "unknown-date"
        slug = _slugify(row.get("name") or "activity")

        summary_target = json_activities_dir / f"{start_date}_{slug}_{activity_id}_summary.json"
        details_target = json_details_dir / f"{start_date}_{slug}_{activity_id}_details.json"

        summary_payload = (
            entry.online_summary_payload
            or entry.online_list_payload
            or entry.local_summary_payload
        )
        if summary_payload:
            _write_json(summary_target, summary_payload)
            inventory_records.append(
                _inventory_row(
                    activity_id,
                    "activity_summary_json",
                    f"garmin-activity-summary://{activity_id}",
                    summary_target,
                    size_bytes=summary_target.stat().st_size,
                )
            )

        details_payload = entry.online_details_payload or entry.local_details_payload
        if details_payload:
            _write_json(details_target, details_payload)
            inventory_records.append(
                _inventory_row(
                    activity_id,
                    "activity_details_json",
                    f"garmin-activity-details://{activity_id}",
                    details_target,
                    size_bytes=details_target.stat().st_size,
                )
            )

        if entry.local_fit_paths:
            for index, fit_match in enumerate(entry.local_fit_paths, start=1):
                suffix = f"_{index}" if len(entry.local_fit_paths) > 1 else ""
                target = fit_dir / f"{start_date}_{slug}_{activity_id}{suffix}.fit"
                shutil.copy2(fit_match, target)
                inventory_records.append(_inventory_row(activity_id, "fit", fit_match, target))
            continue

        if online_context.client is None:
            continue

        try:
            downloaded_paths = _download_activity_original_fit(
                client=online_context.client,
                activity_id=activity_id,
                target_dir=fit_dir,
                target_stem=f"{start_date}_{slug}_{activity_id}",
            )
        except Exception:  # pragma: no cover - remote behavior
            continue

        for downloaded_path in downloaded_paths:
            inventory_records.append(
                _inventory_row(
                    activity_id,
                    "fit",
                    f"garmin-activity-original://{activity_id}",
                    downloaded_path,
                    size_bytes=downloaded_path.stat().st_size,
                )
            )

    return pd.DataFrame(inventory_records)


def _download_activity_original_fit(
    *,
    client: Garmin,
    activity_id: str,
    target_dir: Path,
    target_stem: str,
) -> list[Path]:
    """Download the original Garmin activity file and materialize FIT artifacts.

    Garmin may return a raw FIT file or a zip archive. The exporter normalizes
    both cases into concrete ``.fit`` files under the weekly bundle.
    """

    payload = client.download_activity(activity_id, Garmin.ActivityDownloadFormat.ORIGINAL)
    if payload.startswith(b"PK"):
        return _extract_fit_files_from_zip(payload, target_dir, target_stem)

    target_path = target_dir / f"{target_stem}.fit"
    target_path.write_bytes(payload)
    return [target_path]


def _extract_fit_files_from_zip(
    payload: bytes,
    target_dir: Path,
    target_stem: str,
) -> list[Path]:
    """Extract FIT files from an activity zip payload into deterministic paths."""

    extracted_paths: list[Path] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [
            member
            for member in archive.namelist()
            if not member.endswith("/") and member.lower().endswith(".fit")
        ]
        if not members:
            members = [member for member in archive.namelist() if not member.endswith("/")]
        for index, member in enumerate(members, start=1):
            suffix = f"_{index}" if len(members) > 1 else ""
            target_path = target_dir / f"{target_stem}{suffix}.fit"
            with archive.open(member) as source_stream, target_path.open("wb") as target_stream:
                shutil.copyfileobj(source_stream, target_stream)
            extracted_paths.append(target_path)
    return extracted_paths


def _write_activity_index_artifact(
    *,
    artifact_root: Path,
    resolved_week: ResolvedWeek,
    online_activities: list[dict[str, Any]],
    online_context: OnlineContext,
    activity_fetch_errors: list[dict[str, str]],
) -> None:
    """Persist the online weekly activity index for debugging and audit."""

    path = artifact_root / "json" / f"activities_index_{resolved_week.week_id}.json"
    _write_json(
        path,
        {
            "week_id": resolved_week.week_id,
            "status": _combine_online_status(
                context_status=online_context.status,
                activity_fetch_errors=activity_fetch_errors,
                wellbeing_fetch_errors=[],
                estimate_errors=[],
            ),
            "activities": online_activities,
            "activity_fetch_errors": activity_fetch_errors,
        },
    )


def _write_daily_online_payloads(
    *,
    artifact_root: Path,
    daily_online_payloads: dict[str, DailyOnlinePayload],
) -> None:
    """Persist raw daily online wellbeing payloads into the weekly bundle."""

    if not daily_online_payloads:
        return

    daily_dir = artifact_root / "json" / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    for day, payload in sorted(daily_online_payloads.items()):
        _write_json(daily_dir / f"{day}_user_summary.json", payload.user_summary)
        _write_json(daily_dir / f"{day}_sleep.json", payload.sleep)
        _write_json(daily_dir / f"{day}_hrv.json", payload.hrv)
        _write_json(daily_dir / f"{day}_body_battery.json", {"days": payload.body_battery})
        _write_json(daily_dir / f"{day}_body_composition.json", payload.body_composition)


def _copy_profile_artifacts(
    *,
    data_source: ResolvedDataSource,
    artifact_root: Path,
) -> None:
    """Copy cached profile JSON files into the weekly bundle when available."""

    profile_dir = artifact_root / "json" / "profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("user-settings.json", "personal-information.json", "social-profile.json"):
        source = data_source.fitfiles_dir / filename
        if source.exists():
            shutil.copy2(source, profile_dir / filename)


def _export_activity_records(
    *,
    data_source: ResolvedDataSource,
    sessions_df: pd.DataFrame,
    artifact_root: Path,
) -> int:
    """Dump raw per-record activity rows to debug CSV files for inspection."""

    if sessions_df.empty:
        return 0

    garmin_activities_path = data_source.db_dir / "garmin_activities.db"
    if not garmin_activities_path.exists():
        return 0

    output_dir = artifact_root / "debug" / "activity_records"
    output_dir.mkdir(parents=True, exist_ok=True)
    exported_count = 0
    with sqlite3.connect(garmin_activities_path) as connection:
        connection.row_factory = sqlite3.Row
        for activity_id in sessions_df["activity_id"].tolist():
            rows = connection.execute(
                """
                    SELECT
                        activity_id,
                        record,
                        timestamp,
                        position_lat,
                        position_long,
                        distance,
                        cadence,
                        altitude,
                        hr,
                        rr,
                        speed,
                        temperature
                    FROM activity_records
                    WHERE activity_id = ?
                    ORDER BY record
                """,
                (str(activity_id),),
            ).fetchall()
            if not rows:
                continue

            path = output_dir / f"activity_records_{activity_id}.csv"
            with path.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                for row in rows:
                    writer.writerow(dict(row))
            exported_count += 1
    return exported_count


def _write_online_estimates(
    *,
    resolved_week: ResolvedWeek,
    artifact_root: Path,
    sessions_df: pd.DataFrame,
    include_online_estimates: bool,
    online_context: OnlineContext,
    activity_fetch_errors: list[dict[str, str]],
    wellbeing_fetch_errors: list[dict[str, str]],
) -> str:
    """Write online Garmin estimates, live settings, and fetch diagnostics."""

    estimates_path = artifact_root / "json" / f"garmin_estimates_{resolved_week.week_id}.json"
    if not include_online_estimates:
        _write_json(
            estimates_path,
            {
                "week_id": resolved_week.week_id,
                "status": "skipped",
                "reason": "include_online_estimates was disabled",
            },
        )
        return "skipped"

    if online_context.client is None:
        _write_json(
            estimates_path,
            {
                "week_id": resolved_week.week_id,
                "status": online_context.status,
                "error_type": online_context.error_type,
                "error_message": online_context.error_message,
                "activity_fetch_errors": activity_fetch_errors,
                "wellbeing_fetch_errors": wellbeing_fetch_errors,
            },
        )
        return online_context.status

    client = online_context.client
    estimate_errors: list[dict[str, str]] = []
    latest_activity_id = None
    if not sessions_df.empty:
        latest_activity_id = str(sessions_df.sort_values("start_time").iloc[-1]["activity_id"])

    estimates_payload: dict[str, Any] = {
        "week_id": resolved_week.week_id,
        "status": "ok",
        "retrieved_at": datetime.now().isoformat(timespec="seconds"),
        "profile_estimates": {
            "vo2max_running": _choose_path(
                [online_context.user_settings],
                ("userData", "vo2MaxRunning"),
            ),
            "vo2max_cycling": _choose_path(
                [online_context.user_settings],
                ("userData", "vo2MaxCycling"),
            ),
        },
        "profile_settings": online_context.profile_settings,
        "activity_fetch_errors": activity_fetch_errors,
        "wellbeing_fetch_errors": wellbeing_fetch_errors,
    }

    try:
        estimates_payload["latest_cycling_ftp"] = client.get_cycling_ftp()
    except Exception as exc:  # pragma: no cover - remote behavior
        estimate_errors.append(_error_payload("latest_cycling_ftp", None, exc))
        estimates_payload["latest_cycling_ftp"] = {}

    if latest_activity_id is not None:
        estimates_payload["reference_activity_id"] = latest_activity_id
        try:
            estimates_payload["zones_heart_rate"] = client.get_activity_hr_in_timezones(latest_activity_id)
        except Exception as exc:  # pragma: no cover - remote behavior
            estimate_errors.append(_error_payload("zones_heart_rate", latest_activity_id, exc))
            estimates_payload["zones_heart_rate"] = []
        try:
            estimates_payload["zones_power"] = client.get_activity_power_in_timezones(latest_activity_id)
        except Exception as exc:  # pragma: no cover - remote behavior
            estimate_errors.append(_error_payload("zones_power", latest_activity_id, exc))
            estimates_payload["zones_power"] = []

    status = _combine_online_status(
        context_status=online_context.status,
        activity_fetch_errors=activity_fetch_errors,
        wellbeing_fetch_errors=wellbeing_fetch_errors,
        estimate_errors=estimate_errors,
    )
    estimates_payload["status"] = status
    estimates_payload["estimate_errors"] = estimate_errors
    _write_json(estimates_path, estimates_payload)
    return status


def _combine_online_status(
    *,
    context_status: str,
    activity_fetch_errors: list[dict[str, str]],
    wellbeing_fetch_errors: list[dict[str, str]],
    estimate_errors: list[dict[str, str]],
) -> str:
    """Collapse online bootstrap and fetch diagnostics into one status value."""

    if context_status in {"skipped", "error"}:
        return context_status
    if activity_fetch_errors or wellbeing_fetch_errors or estimate_errors:
        return "partial"
    return "ok"


def _render_export_report(
    *,
    resolved_week: ResolvedWeek,
    data_source: ResolvedDataSource,
    sessions_df: pd.DataFrame,
    wellbeing_df: pd.DataFrame,
    file_inventory_df: pd.DataFrame,
    online_estimates_status: str,
    online_activity_count: int,
    wellbeing_online_days: int,
) -> str:
    """Render a concise markdown summary for a weekly export bundle."""

    lines = [
        f"# Exporte semanal {resolved_week.week_id}",
        "",
        f"- Estado de la semana: `{resolved_week.week_state}`",
        f"- Modo de seleccion: `{resolved_week.selection_mode}`",
        f"- Ventana: `{resolved_week.window.start_date.isoformat()}` a `{resolved_week.window.end_date.isoformat()}`",
        f"- Fuente de datos local: `{data_source.root}` (`{data_source.source_label}`)",
        f"- Estado online: `{online_estimates_status}`",
        "",
        "## Conteos",
        "",
        f"- Actividades exportadas: `{len(sessions_df)}`",
        f"- Actividades vistas online: `{online_activity_count}`",
        f"- Filas de bienestar: `{len(wellbeing_df)}`",
        f"- Dias con payload online: `{wellbeing_online_days}`",
        f"- FIT copiados o descargados: `{_artifact_count(file_inventory_df, 'fit')}`",
        f"- JSON de actividad escritos: `{_artifact_count(file_inventory_df, 'activity_summary_json')}`",
        f"- JSON de detalle escritos: `{_artifact_count(file_inventory_df, 'activity_details_json')}`",
        "",
    ]

    if not sessions_df.empty:
        lines.extend(
            [
                "## Actividades",
                "",
                "| Fecha | Actividad | Deporte | Duracion s | Potencia media | NP | Resp media |",
                "|---|---|---|---|---|---|---|",
            ]
        )
        for row in sessions_df.to_dict(orient="records"):
            lines.append(
                f"| {row.get('date') or ''} | {row.get('name') or ''} | {row.get('sport') or ''} | "
                f"{row.get('duration_seconds') or ''} | {row.get('avg_power_w') or ''} | "
                f"{row.get('normalized_power_w') or ''} | {row.get('avg_respiration_rate') or ''} |"
            )
        lines.append("")

    if not wellbeing_df.empty:
        lines.extend(
            [
                "## Bienestar",
                "",
                "| Fecha | RHR | HRV | Sueno h | Body Battery min | Future day |",
                "|---|---|---|---|---|---|",
            ]
        )
        for row in wellbeing_df.to_dict(orient="records"):
            lines.append(
                f"| {row.get('date')} | {row.get('resting_hr_bpm') or ''} | {row.get('hrv_last_night_avg_ms') or ''} | "
                f"{row.get('sleep_hours') or ''} | {row.get('body_battery_min') or ''} | {row.get('is_future_day')} |"
            )
        lines.append("")

    return "\n".join(lines)


def _sessions_canonical_columns(sessions_df: pd.DataFrame) -> pd.DataFrame:
    """Return the canonical session columns required by REQUEST.md."""

    required_columns = [
        "activity_id",
        "date",
        "start_time",
        "sport",
        "name",
        "duration_seconds",
        "distance_km",
        "avg_hr_bpm",
        "max_hr_bpm",
        "avg_power_w",
        "normalized_power_w",
        "tss",
        "training_load",
        "training_effect",
    ]
    for column in required_columns:
        if column not in sessions_df:
            sessions_df[column] = None
    return sessions_df.loc[:, required_columns]


def _summary_dto(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the nested Garmin ``summaryDTO`` object when present."""

    summary = payload.get("summaryDTO")
    return summary if isinstance(summary, dict) else {}


def _extract_sleep_score(sleep_dto: dict[str, Any]) -> int | float | None:
    """Extract the top-level sleep score value from Garmin sleep payloads."""

    sleep_scores = sleep_dto.get("sleepScores")
    if not isinstance(sleep_scores, dict):
        return None
    overall = sleep_scores.get("overall")
    if isinstance(overall, dict):
        return overall.get("value")
    if isinstance(overall, (int, float)):
        return overall
    return None


def _extract_weight_from_body_composition(payload: dict[str, Any]) -> float | None:
    """Extract a concrete day weight value when Garmin provides it explicitly."""

    date_weight_list = payload.get("dateWeightList") or []
    if not isinstance(date_weight_list, list):
        return None
    for item in date_weight_list:
        if isinstance(item, dict) and item.get("weight") is not None:
            return _safe_float(item.get("weight"))
    return None


def _time_text_to_seconds(value: Any) -> float | None:
    """Convert ``HH:MM:SS(.microseconds)`` strings into seconds."""

    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    parts = str(value).split(":")
    if len(parts) != 3:
        return None
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = float(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def _coerce_duration_seconds(value: Any) -> float | None:
    """Normalize duration fields that may already be numeric or time text."""

    return _time_text_to_seconds(value)


def _time_text_to_hours(value: Any) -> float | None:
    """Convert GarminDB time text into hours with decimal precision."""

    seconds = _time_text_to_seconds(value)
    if seconds is None:
        return None
    return round(seconds / 3600, 3)


def _seconds_to_hours(value: Any) -> float | None:
    """Convert a second count into hours with decimal precision."""

    seconds = _safe_float(value)
    if seconds is None:
        return None
    return round(seconds / 3600, 3)


def _meters_to_km(value: Any) -> float | None:
    """Convert Garmin meter distances to kilometers."""

    number = _safe_float(value)
    if number is None:
        return None
    return round(number / 1000, 3)


def _safe_float(value: Any) -> float | None:
    """Convert a scalar to float when possible."""

    if value is None or value == "":
        return None
    return float(value)


def _first_non_null(*values: Any) -> Any:
    """Return the first value that is not ``None`` among the candidates."""

    for value in values:
        if value is not None:
            return value
    return None


def _choose_first(*sources_and_keys: Any) -> Any:
    """Return the first non-null value found among several dict sources."""

    sources: list[dict[str, Any]] = []
    keys: list[str] = []
    for item in sources_and_keys:
        if isinstance(item, dict):
            sources.append(item)
        else:
            keys.append(str(item))

    for key in keys:
        for source in sources:
            value = source.get(key)
            if value is not None:
                return value
    return None


def _choose_path(
    sources: list[dict[str, Any]],
    *paths: tuple[str, ...],
) -> Any:
    """Return the first nested dict value that exists for the requested paths."""

    for path in paths:
        for source in sources:
            value = _get_nested_value(source, *path)
            if value is not None:
                return value
    return None


def _get_nested_value(source: dict[str, Any], *path: str) -> Any:
    """Resolve a nested dict path safely without raising key errors."""

    current: Any = source
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _safe_min(values: Any) -> Any:
    """Return the minimum numeric value from a list, ignoring nulls."""

    if not isinstance(values, list):
        return None
    numeric_values = [value for value in values if isinstance(value, (int, float))]
    if not numeric_values:
        return None
    return min(numeric_values)


def _safe_max(values: Any) -> Any:
    """Return the maximum numeric value from a list, ignoring nulls."""

    if not isinstance(values, list):
        return None
    numeric_values = [value for value in values if isinstance(value, (int, float))]
    if not numeric_values:
        return None
    return max(numeric_values)


def _slugify(value: str) -> str:
    """Convert a label into a stable ASCII-ish filename slug."""

    cleaned = "".join(character.lower() if character.isalnum() else "-" for character in value)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "activity"


def _inventory_row(
    activity_id: str,
    artifact_type: str,
    source_path: str | Path,
    target_path: Path,
    size_bytes: int | None = None,
) -> dict[str, Any]:
    """Build an inventory row for a copied or synthesized artifact."""

    if size_bytes is None:
        size_bytes = target_path.stat().st_size
    return {
        "activity_id": activity_id,
        "artifact_type": artifact_type,
        "source_path": str(source_path),
        "target_path": str(target_path),
        "size_bytes": size_bytes,
    }


def _load_json_if_exists(path: Path) -> dict[str, Any]:
    """Load JSON from disk if the file exists, otherwise return an empty dict."""

    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _artifact_count(frame: pd.DataFrame, artifact_type: str) -> int:
    """Count artifact inventory rows safely even when the frame is empty."""

    if frame.empty or "artifact_type" not in frame.columns:
        return 0
    return int((frame["artifact_type"] == artifact_type).sum())


def _error_payload(stage: str, identifier: str | None, exc: Exception) -> dict[str, str]:
    """Build a serializable error description for remote Garmin fetches."""

    payload = {
        "stage": stage,
        "error_type": type(exc).__name__,
        "error_message": str(exc),
    }
    if identifier is not None:
        payload["identifier"] = identifier
    return payload


def _write_dataframe(frame: pd.DataFrame, path: Path) -> None:
    """Write a DataFrame to CSV with deterministic formatting."""

    if frame.empty:
        frame = pd.DataFrame()
    frame.to_csv(path, index=False)


def _write_json(path: Path, payload: Any) -> None:
    """Write JSON payloads with stable indentation."""

    with path.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def _write_text(path: Path, content: str) -> None:
    """Write UTF-8 text content to disk."""

    path.write_text(content, encoding="utf-8")

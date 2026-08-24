"""Persistence helpers for weekly report manifests and artifact roots."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import DEFAULT_TIMEZONE_NAME, DEFAULT_WEEKLY_REPORTS_RELATIVE_PATH
from .week import ResolvedWeek


@dataclass(frozen=True, slots=True)
class WeekManifest:
    """Manifest persisted for each prepared reporting window."""

    week_id: str
    start_date: str
    end_date: str
    end_exclusive_date: str
    timezone_name: str
    selection_mode: str
    week_state: str
    storage_bucket: str
    run_status: str
    reference_date: str
    artifact_root: str
    created_at: str
    updated_at: str
    manifest_version: int = 1

    def to_dict(self) -> dict[str, str | int]:
        """Serialize the manifest for on-disk storage."""

        return {
            "manifest_version": self.manifest_version,
            "week_id": self.week_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "end_exclusive_date": self.end_exclusive_date,
            "timezone_name": self.timezone_name,
            "selection_mode": self.selection_mode,
            "week_state": self.week_state,
            "storage_bucket": self.storage_bucket,
            "run_status": self.run_status,
            "reference_date": self.reference_date,
            "artifact_root": self.artifact_root,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_path(cls, manifest_path: Path) -> "WeekManifest":
        """Load a persisted manifest from disk."""

        with manifest_path.open(encoding="utf-8") as stream:
            payload = json.load(stream)
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class PreparedWeek:
    """Result of preparing the filesystem for a reporting window."""

    resolved_week: ResolvedWeek
    artifact_root: Path
    manifest_path: Path
    manifest: WeekManifest
    existed: bool

    def to_dict(self) -> dict[str, str | bool | None]:
        """Serialize the prepared week for CLI output."""

        payload = self.resolved_week.to_dict()
        payload.update(
            {
                "storage_bucket": self.manifest.storage_bucket,
                "artifact_root": str(self.artifact_root),
                "manifest_path": str(self.manifest_path),
                "manifest_exists": True,
                "run_status": self.manifest.run_status,
                "created_at": self.manifest.created_at,
                "updated_at": self.manifest.updated_at,
                "existed": self.existed,
            }
        )
        return payload


class WeekRegistry:
    """Manage weekly artifact directories and manifest files.

    The registry keeps official closed weeks separate from non-official preview
    runs. This prevents incomplete data from polluting the official history.
    """

    def __init__(
        self,
        project_root: Path,
        *,
        timezone_name: str = DEFAULT_TIMEZONE_NAME,
    ) -> None:
        """Create a registry rooted at the current repository."""

        self.project_root = project_root.resolve()
        self.timezone_name = timezone_name
        self.reports_root = self.project_root / DEFAULT_WEEKLY_REPORTS_RELATIVE_PATH

    def describe_week(self, resolved_week: ResolvedWeek) -> dict[str, str | bool | None]:
        """Describe where a week would be stored and whether it already exists."""

        artifact_root = self.artifact_root(resolved_week)
        manifest_path = artifact_root / "manifest.json"
        manifest = self.load_manifest(resolved_week)
        payload = resolved_week.to_dict()
        payload.update(
            {
                "storage_bucket": self.storage_bucket(resolved_week),
                "artifact_root": str(artifact_root),
                "manifest_path": str(manifest_path),
                "manifest_exists": manifest is not None,
                "run_status": manifest.run_status if manifest else None,
                "created_at": manifest.created_at if manifest else None,
                "updated_at": manifest.updated_at if manifest else None,
            }
        )
        return payload

    def prepare_week(
        self,
        resolved_week: ResolvedWeek,
        *,
        overwrite: bool = False,
    ) -> PreparedWeek:
        """Create the artifact tree and manifest for a reporting week."""

        artifact_root = self.artifact_root(resolved_week)
        manifest_path = artifact_root / "manifest.json"
        existing_manifest = self.load_manifest(resolved_week)

        if existing_manifest is not None and not overwrite:
            return PreparedWeek(
                resolved_week=resolved_week,
                artifact_root=artifact_root,
                manifest_path=manifest_path,
                manifest=existing_manifest,
                existed=True,
            )

        try:
            artifact_root.mkdir(parents=True, exist_ok=True)
            for relative_dir in ("csv", "fit", "json", "debug", "debug/fit_rows"):
                (artifact_root / relative_dir).mkdir(parents=True, exist_ok=True)

            timestamp = self._timestamp_now()
            created_at = existing_manifest.created_at if existing_manifest else timestamp
            manifest = WeekManifest(
                week_id=resolved_week.week_id,
                start_date=resolved_week.window.start_date.isoformat(),
                end_date=resolved_week.window.end_date.isoformat(),
                end_exclusive_date=resolved_week.window.end_exclusive_date.isoformat(),
                timezone_name=resolved_week.window.timezone_name,
                selection_mode=resolved_week.selection_mode,
                week_state=resolved_week.week_state,
                storage_bucket=self.storage_bucket(resolved_week),
                run_status="prepared",
                reference_date=resolved_week.reference_date.isoformat(),
                artifact_root=str(artifact_root),
                created_at=created_at,
                updated_at=timestamp,
            )
            self._write_manifest(manifest_path, manifest)
            self._update_index(manifest_path, manifest)
        except OSError as exc:
            raise OSError(
                "Could not prepare weekly artifact root "
                f"'{artifact_root}'. Verify repository write permissions."
            ) from exc

        return PreparedWeek(
            resolved_week=resolved_week,
            artifact_root=artifact_root,
            manifest_path=manifest_path,
            manifest=manifest,
            existed=existing_manifest is not None,
        )

    def load_manifest(self, resolved_week: ResolvedWeek) -> WeekManifest | None:
        """Load an existing manifest for a reporting week if one exists."""

        manifest_path = self.artifact_root(resolved_week) / "manifest.json"
        if not manifest_path.exists():
            return None
        return WeekManifest.from_path(manifest_path)

    def update_manifest_status(
        self,
        manifest: WeekManifest,
        *,
        run_status: str,
    ) -> WeekManifest:
        """Update the run status of an existing manifest.

        Args:
            manifest: Existing manifest to update.
            run_status: New lifecycle state for the weekly run.

        Returns:
            The rewritten manifest instance.
        """

        manifest_path = Path(manifest.artifact_root) / "manifest.json"
        updated_manifest = WeekManifest(
            week_id=manifest.week_id,
            start_date=manifest.start_date,
            end_date=manifest.end_date,
            end_exclusive_date=manifest.end_exclusive_date,
            timezone_name=manifest.timezone_name,
            selection_mode=manifest.selection_mode,
            week_state=manifest.week_state,
            storage_bucket=manifest.storage_bucket,
            run_status=run_status,
            reference_date=manifest.reference_date,
            artifact_root=manifest.artifact_root,
            created_at=manifest.created_at,
            updated_at=self._timestamp_now(),
            manifest_version=manifest.manifest_version,
        )
        self._write_manifest(manifest_path, updated_manifest)
        self._update_index(manifest_path, updated_manifest)
        return updated_manifest

    def artifact_root(self, resolved_week: ResolvedWeek) -> Path:
        """Return the directory that stores artifacts for a reporting week."""

        return self.reports_root / self.storage_bucket(resolved_week) / resolved_week.week_id

    def storage_bucket(self, resolved_week: ResolvedWeek) -> str:
        """Return the storage bucket for a reporting week."""

        if resolved_week.week_state == "closed":
            return "official"
        return "preview"

    def _index_path(self) -> Path:
        """Return the registry index path."""

        return self.reports_root / "index.json"

    def _read_index(self) -> dict[str, dict[str, str]]:
        """Load the weekly index if present."""

        index_path = self._index_path()
        if not index_path.exists():
            return {}
        with index_path.open(encoding="utf-8") as stream:
            return json.load(stream)

    def _timestamp_now(self) -> str:
        """Return a timezone-aware ISO timestamp for manifests."""

        return datetime.now(ZoneInfo(self.timezone_name)).isoformat(timespec="seconds")

    def _update_index(self, manifest_path: Path, manifest: WeekManifest) -> None:
        """Update the lightweight lookup index for prepared weeks."""

        index = self._read_index()
        key = f"{manifest.storage_bucket}/{manifest.week_id}"
        index[key] = {
            "week_id": manifest.week_id,
            "storage_bucket": manifest.storage_bucket,
            "week_state": manifest.week_state,
            "run_status": manifest.run_status,
            "selection_mode": manifest.selection_mode,
            "artifact_root": manifest.artifact_root,
            "manifest_path": str(manifest_path),
            "updated_at": manifest.updated_at,
        }
        self.reports_root.mkdir(parents=True, exist_ok=True)
        with self._index_path().open("w", encoding="utf-8") as stream:
            json.dump(index, stream, indent=2, sort_keys=True)
            stream.write("\n")

    @staticmethod
    def _write_manifest(manifest_path: Path, manifest: WeekManifest) -> None:
        """Persist a manifest to disk with stable formatting."""

        with manifest_path.open("w", encoding="utf-8") as stream:
            json.dump(manifest.to_dict(), stream, indent=2, sort_keys=True)
            stream.write("\n")

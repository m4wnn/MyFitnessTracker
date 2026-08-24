"""Resolve local GarminDB source directories for weekly exports.

The project prefers repository-local data under ``data/raw/HealthData``.
Because the current repository was scaffolded before those raw files were
copied in, the exporter also supports a read-only fallback to the legacy
``~/.GarminDb/HealthData`` tree. That fallback is explicit and surfaced in
the export metadata so it can be debugged and eventually removed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import ProjectConfig

LEGACY_GARMINDDB_RELATIVE_PATH = Path(".GarminDb/HealthData")


@dataclass(frozen=True, slots=True)
class ResolvedDataSource:
    """Concrete GarminDB source tree used by the exporter."""

    root: Path
    source_label: str
    used_fallback: bool

    @property
    def db_dir(self) -> Path:
        """Return the directory that contains Garmin SQLite databases."""

        return self.root / "DBs"

    @property
    def activities_dir(self) -> Path:
        """Return the directory that stores activity FIT and JSON files."""

        return self.root / "FitFiles" / "Activities"

    @property
    def fitfiles_dir(self) -> Path:
        """Return the generic FitFiles directory."""

        return self.root / "FitFiles"


def resolve_data_source(config: ProjectConfig) -> ResolvedDataSource:
    """Resolve the GarminDB source tree for weekly exports.

    Args:
        config: Project configuration with the preferred project-local data root.

    Returns:
        A resolved data source pointing either at the repository-local raw data
        directory or the legacy ``~/.GarminDb/HealthData`` fallback.

    Raises:
        FileNotFoundError: If neither the repository-local nor the legacy data
            source contains the expected Garmin SQLite databases.
    """

    preferred_root = config.data_dir
    preferred_db = preferred_root / "DBs" / "garmin.db"
    if preferred_db.exists():
        return ResolvedDataSource(
            root=preferred_root,
            source_label="project_data_dir",
            used_fallback=False,
        )

    legacy_root = Path.home() / LEGACY_GARMINDDB_RELATIVE_PATH
    legacy_db = legacy_root / "DBs" / "garmin.db"
    if legacy_db.exists():
        return ResolvedDataSource(
            root=legacy_root,
            source_label="legacy_home_garmindb",
            used_fallback=True,
        )

    raise FileNotFoundError(
        "No GarminDB source tree was found. Expected either "
        f"'{preferred_db}' or '{legacy_db}'."
    )

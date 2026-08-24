"""Project-local config loading helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG_RELATIVE_PATH = Path("config/private/GarminConnectConfig.json")
DEFAULT_PASSWORD_RELATIVE_PATH = Path("secrets/.garmin_password")
DEFAULT_TOKENSTORE_RELATIVE_PATH = Path("secrets/garmin_tokens.json")
DEFAULT_DATA_RELATIVE_PATH = Path("data/raw/HealthData")
DEFAULT_WEEKLY_REPORTS_RELATIVE_PATH = Path("reports/weekly")
DEFAULT_TIMEZONE_NAME = "America/Guatemala"


@dataclass(frozen=True, slots=True)
class ProjectConfig:
    """Resolved project configuration for local Garmin workflows."""

    project_root: Path
    config_path: Path
    email: str
    password_file: Path
    token_store: Path
    garmin_domain: str
    data_dir: Path
    weekly_reports_dir: Path
    timezone_name: str
    raw_config: dict


def load_project_config(project_root: Path | None = None) -> ProjectConfig:
    """Load the project-local Garmin configuration file.

    Args:
        project_root: Optional repository root. When omitted, the path is
            inferred from the current source tree.

    Returns:
        A fully resolved :class:`ProjectConfig` with repository-relative paths
        expanded to absolute filesystem locations.
    """

    root = project_root or Path(__file__).resolve().parents[2]
    config_path = root / DEFAULT_CONFIG_RELATIVE_PATH
    with config_path.open(encoding="utf-8") as stream:
        raw_config = json.load(stream)

    email = raw_config["credentials"]["user"].strip()
    password_file = _resolve_path(
        root,
        raw_config["credentials"].get("password_file"),
        DEFAULT_PASSWORD_RELATIVE_PATH,
    )
    data_dir = _resolve_path(
        root,
        raw_config["directories"].get("base_dir"),
        DEFAULT_DATA_RELATIVE_PATH,
    )

    return ProjectConfig(
        project_root=root,
        config_path=config_path,
        email=email,
        password_file=password_file,
        token_store=root / DEFAULT_TOKENSTORE_RELATIVE_PATH,
        garmin_domain=raw_config.get("garmin", {}).get("domain", "garmin.com"),
        data_dir=data_dir,
        weekly_reports_dir=root / DEFAULT_WEEKLY_REPORTS_RELATIVE_PATH,
        timezone_name=raw_config.get("project", {}).get(
            "timezone_name",
            DEFAULT_TIMEZONE_NAME,
        ),
        raw_config=raw_config,
    )


def read_password(config: ProjectConfig) -> str:
    """Read the Garmin password from the configured password file."""

    password = config.password_file.read_text(encoding="utf-8").strip()
    if not password:
        raise ValueError(f"Empty password file: {config.password_file}")
    return password


def _resolve_path(project_root: Path, value: str | None, default_relative_path: Path) -> Path:
    """Resolve a path field from the local project configuration."""

    if not value:
        return project_root / default_relative_path

    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return project_root / path

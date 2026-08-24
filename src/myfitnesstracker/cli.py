"""Command-line entry points for weekly report orchestration helpers."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from .config import DEFAULT_TIMEZONE_NAME
from .export import export_week_bundle
from .week import (
    ResolvedWeek,
    resolve_explicit_week,
    resolve_official_week,
    resolve_preview_current_week,
)
from .week_registry import WeekRegistry


def main(argv: list[str] | None = None) -> int:
    """Run the MyFitnessTracker command-line interface."""

    parser = _build_parser()
    try:
        args = parser.parse_args(argv)

        if args.command == "week":
            return _handle_week_command(args)
    except (OSError, ValueError) as exc:
        parser.exit(status=2, message=f"Error: {exc}\n")

    parser.error(f"Unsupported command: {args.command}")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""

    parser = argparse.ArgumentParser(
        prog="myfitnesstracker",
        description="Utilities for weekly Garmin reporting workflows.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    week_parser = subparsers.add_parser("week", help="Resolve or prepare reporting weeks.")
    week_subparsers = week_parser.add_subparsers(dest="week_command", required=True)

    status_parser = week_subparsers.add_parser(
        "status",
        help="Describe the selected reporting week without writing files.",
    )
    _add_week_selection_arguments(status_parser)
    _add_output_arguments(status_parser)

    prepare_parser = week_subparsers.add_parser(
        "prepare",
        help="Create the artifact tree and manifest for a reporting week.",
    )
    _add_week_selection_arguments(prepare_parser)
    _add_output_arguments(prepare_parser)
    prepare_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Rewrite an existing manifest instead of reusing it.",
    )

    export_parser = week_subparsers.add_parser(
        "export",
        help="Prepare a week and export the complete weekly artifact bundle.",
    )
    _add_week_selection_arguments(export_parser)
    _add_output_arguments(export_parser)
    export_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Rewrite an existing manifest and export artifacts again.",
    )
    export_parser.add_argument(
        "--skip-online-estimates",
        action="store_true",
        help="Do not query Garmin Connect for live weekly supplementation, estimates, or zones.",
    )
    export_parser.add_argument(
        "--skip-debug-records",
        action="store_true",
        help="Do not export raw activity_records CSV files under debug/.",
    )

    return parser


def _add_week_selection_arguments(parser: argparse.ArgumentParser) -> None:
    """Register common arguments that select a reporting week."""

    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root. Defaults to the current working directory.",
    )
    parser.add_argument(
        "--date",
        dest="reference_date",
        type=_parse_iso_date,
        default=None,
        help="Reference local date in YYYY-MM-DD format. Defaults to today in the project timezone.",
    )
    parser.add_argument(
        "--timezone",
        default=DEFAULT_TIMEZONE_NAME,
        help="IANA timezone used for local week boundaries.",
    )
    parser.add_argument(
        "--mode",
        choices=("official", "preview-current", "explicit"),
        default="official",
        help="How to resolve the reporting week.",
    )
    parser.add_argument(
        "--week-start",
        type=_parse_iso_date,
        default=None,
        help="Explicit Sunday start date for --mode explicit.",
    )


def _add_output_arguments(parser: argparse.ArgumentParser) -> None:
    """Register common output-format arguments."""

    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the result as JSON.",
    )
    parser.add_argument(
        "--field",
        default=None,
        help="Print a single field from the result payload for shell scripting.",
    )


def _handle_week_command(args: argparse.Namespace) -> int:
    """Dispatch the week subcommands."""

    registry = WeekRegistry(
        project_root=args.project_root,
        timezone_name=args.timezone,
    )
    resolved_week = _resolve_week_from_args(args)

    if args.week_command == "status":
        payload = registry.describe_week(resolved_week)
    elif args.week_command == "prepare":
        payload = registry.prepare_week(
            resolved_week,
            overwrite=args.overwrite,
        ).to_dict()
    elif args.week_command == "export":
        payload = export_week_bundle(
            project_root=args.project_root,
            resolved_week=resolved_week,
            overwrite=args.overwrite,
            include_online_estimates=not args.skip_online_estimates,
            include_debug_records=not args.skip_debug_records,
        ).to_dict()
    else:
        raise ValueError(f"Unsupported week command: {args.week_command}")

    _emit_payload(payload, json_output=args.json, field_name=args.field)
    return 0


def _resolve_week_from_args(args: argparse.Namespace) -> ResolvedWeek:
    """Resolve a week-selection request from parsed CLI arguments."""

    if args.mode == "official":
        return resolve_official_week(
            reference_date=args.reference_date,
            timezone_name=args.timezone,
        )
    if args.mode == "preview-current":
        return resolve_preview_current_week(
            reference_date=args.reference_date,
            timezone_name=args.timezone,
        )
    if args.week_start is None:
        raise ValueError("--week-start is required when --mode explicit is used.")
    return resolve_explicit_week(
        args.week_start,
        reference_date=args.reference_date,
        timezone_name=args.timezone,
    )


def _emit_payload(
    payload: dict[str, object],
    *,
    json_output: bool,
    field_name: str | None,
) -> None:
    """Render a CLI payload in the requested format."""

    if field_name:
        if field_name not in payload:
            raise ValueError(f"Unknown field requested: {field_name}")
        value = payload[field_name]
        print("" if value is None else value)
        return

    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return

    for key in sorted(payload):
        print(f"{key}: {payload[key]}")


def _parse_iso_date(raw_value: str) -> date:
    """Parse an ISO local date for CLI arguments."""

    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date '{raw_value}'. Expected YYYY-MM-DD."
        ) from exc


if __name__ == "__main__":
    sys.exit(main())

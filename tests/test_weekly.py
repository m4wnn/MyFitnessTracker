"""Unit tests for canonical weekly window and registry behavior."""

from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from myfitnesstracker.week import (
    resolve_explicit_week,
    resolve_official_week,
    resolve_preview_current_week,
    week_for_day,
)
from myfitnesstracker.week_registry import WeekRegistry


class WeekResolutionTests(unittest.TestCase):
    """Verify canonical Sunday-through-Saturday week resolution."""

    def test_week_for_day_uses_sunday_start(self) -> None:
        """A Friday should map to the Sunday that opened the current week."""

        window = week_for_day(date(2026, 8, 14))
        self.assertEqual(window.start_date.isoformat(), "2026-08-09")
        self.assertEqual(window.end_date.isoformat(), "2026-08-15")
        self.assertEqual(window.end_exclusive_date.isoformat(), "2026-08-16")

    def test_official_week_skips_current_open_week(self) -> None:
        """Official mode should always point to the most recent closed week."""

        resolved = resolve_official_week(reference_date=date(2026, 8, 14))
        self.assertEqual(resolved.week_id, "2026-08-02")
        self.assertEqual(resolved.window.end_date.isoformat(), "2026-08-08")
        self.assertEqual(resolved.week_state, "closed")

    def test_preview_current_week_is_incomplete(self) -> None:
        """Preview mode should surface the current week as incomplete."""

        resolved = resolve_preview_current_week(reference_date=date(2026, 8, 14))
        self.assertEqual(resolved.week_id, "2026-08-09")
        self.assertEqual(resolved.week_state, "incomplete")

    def test_explicit_future_week_is_marked_future(self) -> None:
        """Explicit future weeks should not masquerade as incomplete history."""

        resolved = resolve_explicit_week(
            date(2026, 8, 16),
            reference_date=date(2026, 8, 14),
        )
        self.assertEqual(resolved.week_state, "future")


class WeekRegistryTests(unittest.TestCase):
    """Verify manifest creation and week reuse semantics."""

    def test_prepare_week_creates_manifest_and_reuses_it(self) -> None:
        """Preparing the same week twice should detect the existing manifest."""

        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            registry = WeekRegistry(project_root=project_root)
            resolved = resolve_official_week(reference_date=date(2026, 8, 14))

            first = registry.prepare_week(resolved)
            second = registry.prepare_week(resolved)

            self.assertFalse(first.existed)
            self.assertTrue(second.existed)
            self.assertTrue(first.manifest_path.exists())
            self.assertEqual(first.artifact_root.name, "2026-08-02")
            self.assertEqual(first.manifest.run_status, "prepared")
            self.assertEqual(second.manifest.created_at, first.manifest.created_at)


if __name__ == "__main__":
    unittest.main()

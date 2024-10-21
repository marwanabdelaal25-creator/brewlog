"""Tests for brewlog.stats."""

import json

from brewlog.stats import CellarStats


class TestCellarStats:
    def test_snapshot_empty(self, empty_storage):
        stats = CellarStats(empty_storage)
        snap = stats.snapshot()
        assert snap["beans_total"] == 0

    def test_snapshot_populated(self, populated_storage):
        stats = CellarStats(populated_storage)
        snap = stats.snapshot()
        assert snap["beans_total"] >= 2
        assert snap["beans_active"] >= 1

    def test_generated_at(self, populated_storage):
        stats = CellarStats(populated_storage)
        snap = stats.snapshot()
        assert "generated_at" in snap

    def test_origin_stations_tags_counts(self, populated_storage):
        stats = CellarStats(populated_storage)
        snap = stats.snapshot()
        assert snap["origin_count"] >= 1
        assert snap["stations_count"] >= 1

    def test_brewed_last_7_days(self, populated_storage):
        stats = CellarStats(populated_storage)
        snap = stats.snapshot()
        assert "brewed_last_7_days" in snap

    def test_brewed_last_30_days(self, populated_storage):
        stats = CellarStats(populated_storage)
        snap = stats.snapshot()
        assert snap["brewed_last_30_days"] >= 0

    def test_overdue_count(self, populated_storage):
        stats = CellarStats(populated_storage)
        snap = stats.snapshot()
        assert "overdue_count" in snap

    def test_due_today_count(self, populated_storage):
        stats = CellarStats(populated_storage)
        snap = stats.snapshot()
        assert "due_today_count" in snap

    def test_avg_brew_interval(self, populated_storage):
        stats = CellarStats(populated_storage)
        snap = stats.snapshot()
        assert snap["avg_brew_interval_days"] > 0

    def test_tasting_logs_and_notes_totals(self, populated_storage):
        stats = CellarStats(populated_storage)
        snap = stats.snapshot()
        assert snap["notes_total"] >= 1

    def test_render_text(self, populated_storage):
        stats = CellarStats(populated_storage)
        text = stats.render_text()
        assert "beans" in text.lower() or "Cellar" in text

    def test_render_text_empty(self, empty_storage):
        stats = CellarStats(empty_storage)
        text = stats.render_text()
        assert isinstance(text, str)

    def test_archived_not_in_active_count(self, populated_storage, sample_bean):
        populated_storage.update_bean(sample_bean.id, {"archived": True})
        stats = CellarStats(populated_storage)
        snap = stats.snapshot()
        assert snap["beans_active"] < snap["beans_total"]

    def test_collections_total(self, empty_storage):
        stats = CellarStats(empty_storage)
        snap = stats.snapshot()
        assert snap.get("collections_total", 0) == 0

    def test_snapshot_json_serializable(self, populated_storage):
        stats = CellarStats(populated_storage)
        snap = stats.snapshot()
        json.dumps(snap)

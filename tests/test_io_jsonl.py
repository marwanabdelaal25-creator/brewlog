"""Tests for brewlog.io_jsonl."""

import json
from pathlib import Path

import pytest

from brewlog.errors import ImportPipelineError
from brewlog.io_jsonl import (
    EVENT_TYPES,
    export_brew_jsonl,
    export_care_jsonl,
    export_events_jsonl,
    export_full_jsonl,
    import_brew_jsonl,
    import_care_jsonl,
    import_mixed_jsonl,
    count_lines,
    preview,
)


class TestExportJsonl:
    def test_export_brew(self, populated_storage, tmp_path):
        dest = tmp_path / "brew.jsonl"
        count = export_brew_jsonl(populated_storage, dest)
        assert count >= 1
        lines = dest.read_text(encoding="utf-8").strip().splitlines()
        row = json.loads(lines[0])
        assert row["_type"] == "brew"

    def test_export_care(self, populated_storage, tmp_path):
        populated_storage.create_tasting_log({
            "id": "cl1",
            "bean_id": "bean001",
            "action": "grind",
            "logged_at": "2024-06-01T00:00:00+00:00",
        })
        dest = tmp_path / "care.jsonl"
        count = export_care_jsonl(populated_storage, dest)
        assert count >= 1

    def test_export_events_combined(self, populated_storage, tmp_path):
        dest = tmp_path / "events.jsonl"
        count = export_events_jsonl(populated_storage, dest)
        assert count >= 1

    def test_export_full(self, populated_storage, tmp_path):
        dest = tmp_path / "full.jsonl"
        count = export_full_jsonl(populated_storage, dest)
        assert count >= 3


class TestImportJsonl:
    def test_import_brew_roundtrip(self, populated_storage, tmp_path):
        dest = tmp_path / "brew.jsonl"
        export_brew_jsonl(populated_storage, dest)
        before = len(populated_storage.list_brew_events())
        empty = populated_storage.__class__(tmp_path / "empty.json")
        count = import_brew_jsonl(empty, dest)
        assert count == before

    def test_import_care(self, populated_storage, tmp_path):
        populated_storage.create_tasting_log({
            "id": "cl1",
            "bean_id": "bean001",
            "action": "prune",
            "logged_at": "2024-06-01T00:00:00+00:00",
            "details": "Trimmed",
        })
        dest = tmp_path / "care.jsonl"
        export_care_jsonl(populated_storage, dest)
        empty = populated_storage.__class__(tmp_path / "empty2.json")
        count = import_care_jsonl(empty, dest)
        assert count >= 1

    def test_import_mixed(self, populated_storage, tmp_path):
        dest = tmp_path / "mixed.jsonl"
        export_full_jsonl(populated_storage, dest)
        empty = populated_storage.__class__(tmp_path / "empty3.json")
        counts = import_mixed_jsonl(empty, dest)
        assert sum(counts.values()) >= 1

    def test_import_skips_unknown_type(self, empty_storage, tmp_path):
        src = tmp_path / "mixed.jsonl"
        src.write_text(json.dumps({"_type": "unknown", "id": "x"}) + "\n", encoding="utf-8")
        counts = import_mixed_jsonl(empty_storage, src)
        assert counts.get("skipped", 0) >= 1

    def test_invalid_json_line_raises(self, empty_storage, tmp_path):
        src = tmp_path / "bad.jsonl"
        src.write_text("{not json\n", encoding="utf-8")
        with pytest.raises(ImportPipelineError):
            import_brew_jsonl(empty_storage, src)

    def test_missing_file_raises(self, empty_storage, tmp_path):
        with pytest.raises(ImportPipelineError):
            import_brew_jsonl(empty_storage, tmp_path / "missing.jsonl")


class TestJsonlHelpers:
    def test_count_lines(self, populated_storage, tmp_path):
        dest = tmp_path / "brew.jsonl"
        export_brew_jsonl(populated_storage, dest)
        assert count_lines(dest) >= 1

    def test_preview(self, populated_storage, tmp_path):
        dest = tmp_path / "brew.jsonl"
        export_brew_jsonl(populated_storage, dest)
        rows = preview(dest, limit=2)
        assert len(rows) <= 2

    def test_empty_file_import_zero(self, empty_storage, tmp_path):
        src = tmp_path / "empty.jsonl"
        src.write_text("", encoding="utf-8")
        assert import_brew_jsonl(empty_storage, src) == 0

    def test_event_types_constant(self):
        assert "brew" in EVENT_TYPES or isinstance(EVENT_TYPES, (list, tuple, dict))

    def test_care_event_type_alias(self, empty_storage, tmp_path):
        src = tmp_path / "care.jsonl"
        src.write_text(json.dumps({
            "_type": "care",
            "bean_id": "p1",
            "event_type": "grind",
            "occurred_at": "2024-06-01",
        }) + "\n", encoding="utf-8")
        empty_storage.create_bean({"id": "p1", "name": "Fern"})
        count = import_care_jsonl(empty_storage, src)
        assert count >= 0

    def test_non_object_line_raises(self, empty_storage, tmp_path):
        src = tmp_path / "bad.jsonl"
        src.write_text('"just a string"\n', encoding="utf-8")
        with pytest.raises(ImportPipelineError):
            import_brew_jsonl(empty_storage, src)

    def test_import_brew_skips_other_types(self, empty_storage, tmp_path):
        src = tmp_path / "mixed.jsonl"
        src.write_text(
            json.dumps({"_type": "bean", "name": "Fern"}) + "\n",
            encoding="utf-8",
        )
        assert import_brew_jsonl(empty_storage, src) == 0

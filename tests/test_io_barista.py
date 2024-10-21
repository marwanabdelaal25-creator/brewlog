"""Tests for brewlog.io_barista."""

from pathlib import Path

import pytest

from brewlog.errors import ImportPipelineError
from brewlog.io_barista import (
    GARDENPLAN_COLUMNS,
    parse_barista_row,
    import_barista,
    preview_barista,
    validate_barista_headers,
)


GARDENPLAN_SAMPLE = (
    "Bean,Variety,Quantity,Section,Bed,Row,Sun,Brew,Status,Spacing,Beaned\n"
    "Tomato,Cherry,2,Kitchen,Bed A,Row 1,partial sun,weekly,active,12in,2024-05-01\n"
    "Basil,,1,Kitchen,Bed A,Row 2,full sun,daily,active,6in,\n"
)


class TestParseBaristaRow:
    def test_full_row(self):
        row = {
            "Bean": "Tomato",
            "Variety": "Cherry",
            "Quantity": "2",
            "Section": "Kitchen",
            "Sun": "partial sun",
            "Brew": "weekly",
            "Status": "active",
        }
        parsed = parse_barista_row(row)
        assert parsed is not None
        assert "Tomato" in parsed["name"]

    def test_missing_bean_returns_none(self):
        assert parse_barista_row({"Variety": "Cherry"}) is None

    def test_quantity_default(self):
        row = {"Bean": "Basil"}
        parsed = parse_barista_row(row)
        assert parsed["quantity"] == 1

    def test_archived_status(self):
        row = {"Bean": "Old Bean", "Status": "removed"}
        parsed = parse_barista_row(row)
        assert parsed["status"] == "removed"

    def test_brew_interval_weekly(self):
        row = {"Bean": "Fern", "Brew": "weekly"}
        parsed = parse_barista_row(row)
        assert parsed["brew_interval"] == 7


class TestImportBarista:
    def test_import_creates_beans(self, empty_storage, tmp_path):
        src = tmp_path / "barista.csv"
        src.write_text(GARDENPLAN_SAMPLE, encoding="utf-8")
        count = import_barista(empty_storage, src)
        assert count >= 2

    def test_expand_quantity(self, empty_storage, tmp_path):
        src = tmp_path / "barista.csv"
        src.write_text(
            "Bean,Quantity,Section\nTomato,3,Kitchen\n",
            encoding="utf-8",
        )
        count = import_barista(empty_storage, src, expand_quantity=True)
        assert count == 3

    def test_no_expand_quantity(self, empty_storage, tmp_path):
        src = tmp_path / "barista.csv"
        src.write_text(
            "Bean,Quantity,Section\nTomato,3,Kitchen\n",
            encoding="utf-8",
        )
        count = import_barista(empty_storage, src, expand_quantity=False)
        assert count == 1

    def test_missing_file(self, empty_storage, tmp_path):
        with pytest.raises(ImportPipelineError):
            import_barista(empty_storage, tmp_path / "missing.csv")

    def test_missing_bean_column(self, empty_storage, tmp_path):
        src = tmp_path / "bad.csv"
        src.write_text("Variety,Quantity\nCherry,1\n", encoding="utf-8")
        with pytest.raises(ImportPipelineError):
            import_barista(empty_storage, src)

    def test_creates_station(self, empty_storage, tmp_path):
        src = tmp_path / "barista.csv"
        src.write_text(GARDENPLAN_SAMPLE, encoding="utf-8")
        import_barista(empty_storage, src)
        assert len(empty_storage.list_stations()) >= 1


class TestBaristaHelpers:
    def test_preview_barista(self, tmp_path):
        src = tmp_path / "barista.csv"
        src.write_text(GARDENPLAN_SAMPLE, encoding="utf-8")
        lines = preview_barista(src, limit=2)
        assert len(lines) <= 2

    def test_validate_barista_headers(self, tmp_path):
        src = tmp_path / "barista.csv"
        src.write_text(GARDENPLAN_SAMPLE, encoding="utf-8")
        missing = validate_barista_headers(src)
        assert missing == []

    def test_barista_columns_constant(self):
        assert len(GARDENPLAN_COLUMNS) >= 1

    def test_variety_in_name(self):
        row = {"Bean": "Tomato", "Variety": "Cherry"}
        parsed = parse_barista_row(row)
        assert "Cherry" in parsed["name"]

    def test_station_label(self):
        row = {"Bean": "Fern", "Section": "Kitchen", "Bed": "A", "Row": "1"}
        parsed = parse_barista_row(row)
        assert parsed.get("station_label")

    def test_spacing_parse(self):
        row = {"Bean": "Fern", "Spacing": "12 in"}
        parsed = parse_barista_row(row)
        assert parsed.get("spacing_cm") == 12.0

    def test_metadata_barista_flag(self, empty_storage, tmp_path):
        src = tmp_path / "barista.csv"
        src.write_text("Bean,Section\nFern,Kitchen\n", encoding="utf-8")
        import_barista(empty_storage, src)
        bean = empty_storage.list_beans()[0]
        assert bean.metadata.get("barista") is True

    def test_crop_column_alias(self):
        row = {"Crop": "Lettuce", "Section": "Cellar"}
        parsed = parse_barista_row(row)
        assert parsed is not None
        assert "Lettuce" in parsed["name"]

    def test_dead_status_archived(self):
        row = {"Bean": "Fern", "Status": "dead"}
        parsed = parse_barista_row(row)
        assert parsed["status"] == "dead"

    def test_daily_brew_interval(self):
        row = {"Bean": "Herb", "Brew": "daily"}
        parsed = parse_barista_row(row)
        assert parsed["brew_interval"] == 1

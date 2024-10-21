"""Tests for brewlog.io_beanconqueror."""

from pathlib import Path

import pytest

from brewlog.errors import ImportPipelineError
from brewlog.io_beanconqueror import (
    PLANTLY_COLUMNS,
    parse_beanconqueror_row,
    import_beanconqueror,
    preview_beanconqueror,
    validate_beanconqueror_headers,
)


PLANTLY_SAMPLE = (
    "Bean Name,Origin,Room,Brew Every,Light,Health,Pot Size,Humidity\n"
    "Monstera Deliciosa,Monstera,Living Room,7 days,bright indirect,good,6in ceramic,55%\n"
    "Snake Bean,Sansevieria,Bedroom,2 weeks,low,great,8in,40%\n"
)


class TestParseBeanconquerorRow:
    def test_full_row(self):
        row = {
            "Bean Name": "Monstera",
            "Origin": "Monstera deliciosa",
            "Room": "Living Room",
            "Brew Every": "7 days",
            "Light": "bright indirect",
            "Health": "good",
            "Pot Size": "6in ceramic",
            "Humidity": "55%",
        }
        parsed = parse_beanconqueror_row(row)
        assert parsed is not None
        assert parsed["name"] == "Monstera"

    def test_missing_name_returns_none(self):
        assert parse_beanconqueror_row({"Origin": "Fern"}) is None

    def test_health_mapping(self):
        row = {"Bean Name": "Fern", "Health": "great"}
        parsed = parse_beanconqueror_row(row)
        assert parsed["health"] == "thriving"

    def test_humidity_parse(self):
        row = {"Bean Name": "Fern", "Humidity": "60%"}
        parsed = parse_beanconqueror_row(row)
        assert parsed.get("humidity_override") == 60.0


class TestImportBeanconqueror:
    def test_import_creates_beans(self, empty_storage, tmp_path):
        src = tmp_path / "beanconqueror.csv"
        src.write_text(PLANTLY_SAMPLE, encoding="utf-8")
        count = import_beanconqueror(empty_storage, src)
        assert count >= 2

    def test_import_creates_station(self, empty_storage, tmp_path):
        src = tmp_path / "beanconqueror.csv"
        src.write_text(PLANTLY_SAMPLE, encoding="utf-8")
        import_beanconqueror(empty_storage, src)
        assert len(empty_storage.list_stations()) >= 1

    def test_import_missing_file(self, empty_storage, tmp_path):
        with pytest.raises(ImportPipelineError):
            import_beanconqueror(empty_storage, tmp_path / "missing.csv")

    def test_import_missing_bean_column(self, empty_storage, tmp_path):
        src = tmp_path / "bad.csv"
        src.write_text("Origin,Room\nMonstera,Living Room\n", encoding="utf-8")
        with pytest.raises(ImportPipelineError):
            import_beanconqueror(empty_storage, src)

    def test_update_by_external_id(self, empty_storage, tmp_path):
        src = tmp_path / "beanconqueror.csv"
        src.write_text(
            "Bean Name,Beanconqueror ID,Room\nMonstera,ext123,Living Room\n",
            encoding="utf-8",
        )
        import_beanconqueror(empty_storage, src)
        src.write_text(
            "Bean Name,Beanconqueror ID,Room,Health\nMonstera Updated,ext123,Living Room,great\n",
            encoding="utf-8",
        )
        count = import_beanconqueror(empty_storage, src, update=True)
        assert count >= 1

    def test_update_by_name(self, populated_storage, tmp_path):
        src = tmp_path / "beanconqueror.csv"
        src.write_text(
            "Bean Name,Room,Health\nMonstera,Living Room,great\n",
            encoding="utf-8",
        )
        count = import_beanconqueror(populated_storage, src, update=True)
        assert count >= 1


class TestBeanconquerorHelpers:
    def test_preview_beanconqueror(self, tmp_path):
        src = tmp_path / "beanconqueror.csv"
        src.write_text(PLANTLY_SAMPLE, encoding="utf-8")
        lines = preview_beanconqueror(src, limit=2)
        assert len(lines) <= 2

    def test_validate_beanconqueror_headers(self, tmp_path):
        src = tmp_path / "beanconqueror.csv"
        src.write_text(PLANTLY_SAMPLE, encoding="utf-8")
        missing = validate_beanconqueror_headers(src)
        assert missing == []

    def test_column_aliases(self):
        row = {"Name": "Fern", "Brew Every": "7d"}
        parsed = parse_beanconqueror_row(row)
        assert parsed is not None

    def test_beanconqueror_columns_constant(self):
        assert len(PLANTLY_COLUMNS) >= 1

    def test_light_level_parse(self):
        row = {"Bean Name": "Fern", "Light": "medium"}
        parsed = parse_beanconqueror_row(row)
        assert parsed.get("light_override") == "medium"

    def test_bag_size_parse(self):
        row = {"Bean Name": "Fern", "Pot Size": "6in terracotta"}
        parsed = parse_beanconqueror_row(row)
        assert parsed.get("bag", {}).get("diameter") == 6.0

    def test_interval_from_brew_every(self):
        row = {"Bean Name": "Fern", "Brew Every": "14 days"}
        parsed = parse_beanconqueror_row(row)
        assert parsed.get("brew_interval_days") == 14

    def test_label_url_stored(self):
        row = {"Bean Name": "Fern", "Label URL": "https://example.com/p.jpg"}
        parsed = parse_beanconqueror_row(row)
        assert parsed.get("label_url") == "https://example.com/p.jpg"

    def test_auto_create_origin(self, empty_storage, tmp_path):
        src = tmp_path / "beanconqueror.csv"
        src.write_text(
            "Bean Name,Origin,Room\nCustom Fern,Custom Fern spp,Kitchen\n",
            encoding="utf-8",
        )
        import_beanconqueror(empty_storage, src)
        assert len(empty_storage.list_origin()) >= 1

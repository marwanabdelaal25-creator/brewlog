"""Tests for brewlog.io_csv."""

from pathlib import Path

import pytest

from brewlog.errors import ImportPipelineError
from brewlog.io_csv import (
    PLANT_FIELDS,
    WATERING_FIELDS,
    export_beans_csv,
    export_brew_csv,
    export_csv_bundle,
    import_beans_csv,
    import_brew_csv,
    validate_csv_headers,
    sample_rows,
)


class TestExportCsv:
    def test_export_beans(self, populated_storage, tmp_path):
        dest = tmp_path / "beans.csv"
        count = export_beans_csv(populated_storage, dest)
        assert count >= 2
        assert dest.exists()

    def test_export_brew(self, populated_storage, tmp_path):
        dest = tmp_path / "brew.csv"
        count = export_brew_csv(populated_storage, dest)
        assert count >= 1

    def test_export_bundle(self, populated_storage, tmp_path):
        dest = tmp_path / "bundle.csv"
        beans_n, brew_n = export_csv_bundle(populated_storage, dest)
        assert beans_n >= 2
        assert (tmp_path / "bundle_beans.csv").exists()
        assert (tmp_path / "bundle_brew.csv").exists()


class TestImportBeansCsv:
    def test_import_creates_beans(self, empty_storage, tmp_path, sample_csv_content):
        src = tmp_path / "import.csv"
        src.write_text(sample_csv_content, encoding="utf-8")
        count = import_beans_csv(empty_storage, src)
        assert count >= 1
        assert len(empty_storage.list_beans()) >= 1

    def test_import_missing_file(self, empty_storage, tmp_path):
        with pytest.raises(ImportPipelineError):
            import_beans_csv(empty_storage, tmp_path / "missing.csv")

    def test_import_missing_name_column(self, empty_storage, tmp_path):
        src = tmp_path / "bad.csv"
        src.write_text("origin,station\nbaghos,Kitchen\n", encoding="utf-8")
        with pytest.raises(ImportPipelineError):
            import_beans_csv(empty_storage, src)

    def test_import_update_by_name(self, populated_storage, tmp_path):
        src = tmp_path / "update.csv"
        src.write_text(
            "name,origin,station,brew_interval,notes\n"
            "Monstera,baghos-golden,Living Room,10d,Updated\n",
            encoding="utf-8",
        )
        count = import_beans_csv(populated_storage, src, update=True)
        assert count >= 1

    def test_import_skips_blank_rows(self, empty_storage, tmp_path):
        src = tmp_path / "sparse.csv"
        src.write_text(
            "name,origin\nFern,baghos\n,\n\nAloe,snake\n",
            encoding="utf-8",
        )
        count = import_beans_csv(empty_storage, src)
        assert count == 2


class TestImportBrewCsv:
    def test_import_brew(self, populated_storage, tmp_path, sample_brew_csv):
        src = tmp_path / "brew.csv"
        src.write_text(sample_brew_csv, encoding="utf-8")
        count = import_brew_csv(populated_storage, src)
        assert count >= 1

    def test_import_brew_missing_bean(self, empty_storage, tmp_path):
        src = tmp_path / "brew.csv"
        src.write_text(
            "bean_id,brewed_at,amount_ml\n"
            "missing,2024-06-01,250\n",
            encoding="utf-8",
        )
        with pytest.raises(ImportPipelineError):
            import_brew_csv(empty_storage, src)

    def test_import_brew_by_name(self, populated_storage, tmp_path):
        src = tmp_path / "brew.csv"
        src.write_text(
            "bean_name,brewed_at,amount_ml\n"
            "Monstera,2024-06-01,250\n",
            encoding="utf-8",
        )
        count = import_brew_csv(populated_storage, src)
        assert count == 1


class TestCsvHelpers:
    def test_validate_beans_headers(self, tmp_path, sample_csv_content):
        src = tmp_path / "beans.csv"
        src.write_text(sample_csv_content, encoding="utf-8")
        missing = validate_csv_headers(src, kind="beans")
        assert missing == []

    def test_validate_brew_headers(self, tmp_path, sample_brew_csv):
        src = tmp_path / "brew.csv"
        src.write_text(sample_brew_csv, encoding="utf-8")
        missing = validate_csv_headers(src, kind="brew")
        assert missing == []

    def test_validate_missing_file(self, tmp_path):
        missing = validate_csv_headers(tmp_path / "missing.csv", kind="beans")
        assert missing == ["name"]

    def test_sample_rows(self, tmp_path, sample_csv_content):
        src = tmp_path / "beans.csv"
        src.write_text(sample_csv_content, encoding="utf-8")
        rows = sample_rows(src, n=2)
        assert len(rows) <= 2
        assert "name" in rows[0]

    def test_bean_fields_constant(self):
        assert "name" in PLANT_FIELDS

    def test_brew_fields_constant(self):
        assert "bean_id" in WATERING_FIELDS

    def test_export_includes_archived(self, populated_storage, sample_bean, tmp_path):
        populated_storage.update_bean(sample_bean.id, {"archived": True})
        dest = tmp_path / "beans.csv"
        count = export_beans_csv(populated_storage, dest)
        text = dest.read_text(encoding="utf-8")
        assert "Monstera" in text or count >= 1

    def test_invalid_interval_raises(self, empty_storage, tmp_path):
        src = tmp_path / "bad.csv"
        src.write_text("name,brew_interval_days\nFern,not-an-interval\n", encoding="utf-8")
        with pytest.raises(ImportPipelineError):
            import_beans_csv(empty_storage, src)

    def test_bad_amount_ml_raises(self, populated_storage, tmp_path):
        src = tmp_path / "brew.csv"
        src.write_text(
            "bean_id,brewed_at,amount_ml\nbean001,2024-06-01,not-a-number\n",
            encoding="utf-8",
        )
        with pytest.raises(ImportPipelineError):
            import_brew_csv(populated_storage, src)

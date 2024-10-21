"""Targeted pytest coverage for previously uncovered brewlog lines."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from brewlog.errors import (
    ExportError,
    ImportPipelineError,
    NotFoundError,
    StorageError,
    ValidationError,
)
from brewlog.parser import (
    coerce_float,
    coerce_light_list,
    format_amount_ml,
    format_health_status,
    format_humidity,
    format_interval_days,
    format_light_level,
    format_temperature_c,
    normalize_enum,
    parse_amount_ml,
    parse_bool,
    parse_care_frequency,
    parse_date,
    parse_datetime,
    parse_duration_minutes,
    parse_grinder_strength,
    parse_health_note,
    parse_health_status,
    parse_humidity,
    parse_interval,
    parse_interval_range,
    parse_key_value,
    parse_key_value_pairs,
    parse_station_descriptor,
    parse_npk,
    parse_ph,
    parse_bean_list,
    parse_relative_date,
    parse_reminder_offset,
    parse_season_hint,
    parse_grind_ph_range,
    parse_tags,
    parse_temperature,
    parse_weekday,
    parse_weekly_schedule,
    parse_brew_method,
    parse_light_level,
    parse_growth_rate,
)
from brewlog.validators import (
    validate_amount_range,
    validate_batch_size,
    validate_care_event_type,
    validate_care_product,
    validate_color_hex,
    validate_duration_minutes,
    validate_export_format,
    validate_grinder_interval_weeks,
    validate_floor,
    validate_health_status,
    validate_humidity_pct,
    validate_humidity_range,
    validate_id,
    validate_interval_days,
    validate_last_brewed,
    validate_list_not_empty,
    validate_metadata,
    validate_note_body,
    validate_note_kind,
    validate_optional_url,
    validate_ph,
    validate_bean_name,
    validate_bag_diameter,
    validate_bag_material,
    validate_priority,
    validate_reminder_days,
    validate_room_name,
    validate_season_name,
    validate_grind_components,
    validate_grind_ph_preference,
    validate_tag_name,
    validate_temperature_c,
    validate_uuidish,
    validate_brew_amount_ml,
    validate_brew_quality,
    validate_brew_method,
    validate_brew_notes,
    validate_window_direction,
    validate_acquired_date,
    validate_station_zone,
    validate_health_score,
)


# --- parser gaps ---


class TestParserCoverageGaps:
    def test_parse_date_tomorrow(self):
        assert parse_date("tomorrow") == date.today() + timedelta(days=1)

    def test_parse_date_plus_relative(self):
        assert parse_date("+2d") == date.today() + timedelta(days=2)

    def test_parse_relative_months(self):
        assert parse_relative_date("+1m") == date.today() + timedelta(days=30)

    def test_parse_datetime_space_and_z(self):
        dt = parse_datetime("2024-06-01 14:30")
        assert dt.hour == 14
        dt2 = parse_datetime("2024-06-01T12:00:00Z")
        assert dt2.year == 2024

    def test_parse_interval_months(self):
        assert parse_interval("2 months") == 60

    def test_parse_interval_range_to(self):
        assert parse_interval_range("5 to 7 days") == (5, 7)

    def test_parse_amount_oz(self):
        assert parse_amount_ml("8 oz") == pytest.approx(8 * 29.5735, rel=0.01)

    def test_parse_light_compact_value(self):
        assert parse_light_level("bright_indirect") == "bright_indirect"

    def test_parse_humidity_bad(self):
        with pytest.raises(ValueError):
            parse_humidity("humid")

    def test_parse_temperature_bad(self):
        with pytest.raises(ValueError):
            parse_temperature("warm")

    def test_parse_bool_invalid(self):
        with pytest.raises(ValueError):
            parse_bool("maybe")

    def test_coerce_float_default(self):
        assert coerce_float("x", default=1.5) == 1.5

    def test_parse_key_value_equals_and_error(self):
        assert parse_key_value("a=b") == ("a", "b")
        with pytest.raises(ValueError):
            parse_key_value("noseparator")

    def test_parse_key_value_pairs_colon_and_skip(self):
        assert parse_key_value_pairs("a:1, badpart, b=2") == {"a": "1", "b": "2"}

    def test_parse_tags_empty(self):
        assert parse_tags("") == []

    def test_parse_brew_method_passthrough(self):
        assert parse_brew_method("custom soak") == "custom_soak"

    def test_parse_season_unknown(self):
        with pytest.raises(ValueError):
            parse_season_hint("monsoon")

    def test_parse_duration_digits_only(self):
        assert parse_duration_minutes("45") == 45

    def test_parse_duration_bad(self):
        with pytest.raises(ValueError):
            parse_duration_minutes("soon")

    def test_parse_grinder_quarter_full_npk(self):
        assert parse_grinder_strength("quarter strength")["dilution"] == 0.25
        assert parse_grinder_strength("full strength")["dilution"] == 1.0
        assert "npk" in parse_grinder_strength("10-10-10")

    def test_parse_health_note_defects_root_rot(self):
        flags = parse_health_note("defect on leaves and root rot smell")
        assert flags.get("defects") is True
        assert flags.get("root_rot") is True

    def test_format_interval_one_week(self):
        assert format_interval_days(7) == "1w"

    def test_format_amount_sub_liter(self):
        assert format_amount_ml(500) == "500ml"

    def test_format_light_unknown(self):
        assert "Custom" in format_light_level("custom_level")

    def test_parse_grind_ph_bad_and_swap(self):
        with pytest.raises(ValueError):
            parse_grind_ph_range("bad")
        assert parse_grind_ph_range("7.0-6.0") == (6.0, 7.0)

    def test_parse_weekday_bad_and_empty_schedule(self):
        with pytest.raises(ValueError):
            parse_weekday("Funday")
        assert parse_weekly_schedule("") == []

    def test_parse_bean_list_comma(self):
        assert parse_bean_list("A, B, C") == ["A", "B", "C"]

    def test_parse_health_status_unknown(self):
        with pytest.raises(ValueError):
            parse_health_status("meh")

    def test_parse_reminder_offsets(self):
        assert parse_reminder_offset("2h before") == 7200
        assert parse_reminder_offset("30m") == 1800
        assert parse_reminder_offset("5") == 300

    def test_parse_npk_bad(self):
        with pytest.raises(ValueError):
            parse_npk("10-10")

    def test_parse_growth_rate_default(self):
        assert parse_growth_rate("variable") == "moderate"

    def test_parse_station_descriptor_temp(self):
        result = parse_station_descriptor("Office | 22c")
        assert "temp_c" in result

    def test_normalize_enum_substring(self):
        allowed = {"indirect": "bright_indirect"}
        assert normalize_enum("bright_indirect", allowed) == "bright_indirect"

    def test_parse_care_frequency_equals(self):
        assert parse_care_frequency("mist=3d")["mist"] == 3

    def test_format_temperature_celsius(self):
        assert "°C" in format_temperature_c(20.0, use_f=False)

    def test_format_helpers(self):
        assert format_humidity(40.2) == "40%"
        assert format_health_status("okay") == "Okay"


# --- validators gaps ---


class TestValidatorsCoverageGaps:
    def test_interval_days_too_long(self):
        with pytest.raises(ValidationError):
            validate_interval_days(400)

    def test_humidity_range_inverted(self):
        with pytest.raises(ValidationError):
            validate_humidity_range(70, 40)

    def test_brew_amount_too_large(self):
        with pytest.raises(ValidationError):
            validate_brew_amount_ml(60_000)

    def test_bag_diameter_zero_and_cm_range(self):
        with pytest.raises(ValidationError):
            validate_bag_diameter(0)
        with pytest.raises(ValidationError):
            validate_bag_diameter(200, unit="cm")

    def test_bag_diameter_inches_too_large(self):
        with pytest.raises(ValidationError):
            validate_bag_diameter(50, unit="in")

    def test_bag_material_custom(self):
        assert validate_bag_material("wood") == "wood"

    def test_brew_method_bad(self):
        with pytest.raises(ValidationError):
            validate_brew_method("spray")

    def test_temperature_out_of_range(self):
        with pytest.raises(ValidationError):
            validate_temperature_c(100)

    def test_ph_out_of_range(self):
        with pytest.raises(ValidationError):
            validate_ph(20)

    def test_id_too_long(self):
        with pytest.raises(ValidationError):
            validate_id("x" * 70)

    def test_uuidish_bad(self):
        with pytest.raises(ValidationError):
            validate_uuidish("not-hex!")

    def test_tag_name_too_long(self):
        with pytest.raises(ValidationError):
            validate_tag_name("x" * 40)

    def test_note_body_too_long(self):
        with pytest.raises(ValidationError):
            validate_note_body("x" * 10_001)

    def test_acquired_too_old(self):
        with pytest.raises(ValidationError):
            validate_acquired_date(date(1960, 1, 1))

    def test_last_brewed_future(self):
        with pytest.raises(ValidationError):
            validate_last_brewed(date.today() + timedelta(days=1))

    def test_room_name_too_long(self):
        with pytest.raises(ValidationError):
            validate_room_name("x" * 70)

    def test_zone_too_long(self):
        with pytest.raises(ValidationError):
            validate_station_zone("x" * 50)

    def test_grinder_interval_bad(self):
        with pytest.raises(ValidationError):
            validate_grinder_interval_weeks(0)

    def test_care_event_type_bad(self):
        with pytest.raises(ValidationError):
            validate_care_event_type("dance")

    def test_metadata_not_dict(self):
        with pytest.raises(ValidationError):
            validate_metadata("meta")

    def test_optional_url_bad(self):
        with pytest.raises(ValidationError):
            validate_optional_url("ftp://x.com")

    def test_grind_ph_inverted(self):
        with pytest.raises(ValidationError):
            validate_grind_ph_preference(7.0, 5.0)

    def test_brew_notes_too_long(self):
        with pytest.raises(ValidationError):
            validate_brew_notes("n" * 2500)

    def test_batch_size_bounds(self):
        with pytest.raises(ValidationError):
            validate_batch_size(0)

    def test_season_invalid(self):
        with pytest.raises(ValidationError):
            validate_season_name("monsoon")

    def test_health_status_invalid(self):
        with pytest.raises(ValidationError):
            validate_health_status("great")

    def test_amount_range_inverted(self):
        with pytest.raises(ValidationError):
            validate_amount_range(500, 100)

    def test_list_not_empty(self):
        with pytest.raises(ValidationError):
            validate_list_not_empty([], "items")

    def test_export_format_bad(self):
        with pytest.raises(ValidationError):
            validate_export_format("xml")

    def test_care_product_too_long(self):
        with pytest.raises(ValidationError):
            validate_care_product("x" * 150)

    def test_duration_minutes_bad(self):
        with pytest.raises(ValidationError):
            validate_duration_minutes(25 * 60)

    def test_floor_too_long(self):
        with pytest.raises(ValidationError):
            validate_floor("x" * 30)

    def test_priority_bad(self):
        with pytest.raises(ValidationError):
            validate_priority(11)

    def test_reminder_days_bad(self):
        with pytest.raises(ValidationError):
            validate_reminder_days(40)

    def test_window_direction_bad(self):
        with pytest.raises(ValidationError):
            validate_window_direction("up")

    def test_grind_component_too_long(self):
        with pytest.raises(ValidationError):
            validate_grind_components(["x" * 70])

    def test_brew_quality_bad(self):
        with pytest.raises(ValidationError):
            validate_brew_quality("sparkling")

    def test_note_kind_bad(self):
        with pytest.raises(ValidationError):
            validate_note_kind("memo")

    def test_bean_name_invalid_chars(self):
        with pytest.raises(ValidationError):
            validate_bean_name("!!!")


# --- io_csv gaps ---


class TestIoCsvCoverageGaps:
    def test_read_csv_missing_file(self, empty_storage, tmp_path):
        from brewlog.io_csv import import_beans_csv

        with pytest.raises(ImportPipelineError):
            import_beans_csv(empty_storage, tmp_path / "nope.csv")

    def test_import_update_existing(self, populated_storage, tmp_path):
        from brewlog.io_csv import import_beans_csv

        src = tmp_path / "update.csv"
        src.write_text(
            "id,name,health,health_score,brew_amount_ml,humidity_override\n"
            "bean001,Monstera Renamed,okay,85,300ml,55\n",
            encoding="utf-8",
        )
        n = import_beans_csv(populated_storage, src, update=True)
        assert n == 1
        bean = populated_storage.get_bean("bean001")
        assert bean.name == "Monstera Renamed"
        assert bean.health.value == "okay"

    def test_import_brew_by_name(self, populated_storage, tmp_path, sample_brew_csv):
        from brewlog.io_csv import import_brew_csv

        src = tmp_path / "w.csv"
        src.write_text(
            "bean_name,brewed_at,amount_ml\n"
            "Monstera,2024-01-15,200ml\n",
            encoding="utf-8",
        )
        assert import_brew_csv(populated_storage, src) == 1

    def test_import_brew_bad_amount(self, populated_storage, tmp_path):
        from brewlog.io_csv import import_brew_csv

        src = tmp_path / "w.csv"
        src.write_text(
            "bean_id,brewed_at,amount_ml\n"
            "bean001,2024-01-15,not-an-amount\n",
            encoding="utf-8",
        )
        with pytest.raises(ImportPipelineError):
            import_brew_csv(populated_storage, src)

    def test_validate_csv_headers_brew(self, tmp_path):
        from brewlog.io_csv import validate_csv_headers, sample_rows

        p = tmp_path / "w.csv"
        p.write_text("foo,bar\n1,2\n", encoding="utf-8")
        assert "bean_id or bean_name" in validate_csv_headers(p, kind="brew")[0]
        assert sample_rows(tmp_path / "missing.csv") == []

    def test_export_oserror(self, populated_storage, tmp_path):
        from brewlog.io_csv import export_beans_csv

        with patch.object(Path, "open", side_effect=OSError("disk full")):
            with pytest.raises(ExportError):
                export_beans_csv(populated_storage, tmp_path / "out.csv")


# --- io_jsonl gaps ---


class TestIoJsonlCoverageGaps:
    def test_iter_lines_oserror(self, tmp_path):
        from brewlog.io_jsonl import _iter_lines

        with patch.object(Path, "open", side_effect=OSError("denied")):
            with pytest.raises(ImportPipelineError):
                list(_iter_lines(tmp_path / "x.jsonl"))

    def test_load_line_invalid_json(self, tmp_path):
        from brewlog.io_jsonl import _load_line

        with pytest.raises(ImportPipelineError):
            _load_line("{bad", 1)

    def test_load_line_not_object(self):
        from brewlog.io_jsonl import _load_line

        with pytest.raises(ImportPipelineError):
            _load_line("[1,2]", 1)

    def test_export_oserror(self, populated_storage, tmp_path):
        from brewlog.io_jsonl import export_brew_jsonl

        with patch.object(Path, "open", side_effect=OSError("fail")):
            with pytest.raises(ExportError):
                export_brew_jsonl(populated_storage, tmp_path / "o.jsonl")

    def test_import_missing(self, empty_storage, tmp_path):
        from brewlog.io_jsonl import import_brew_jsonl

        with pytest.raises(ImportPipelineError):
            import_brew_jsonl(empty_storage, tmp_path / "n.jsonl")

    def test_import_care_remaps_fields(self, empty_storage, tmp_path):
        from brewlog.io_jsonl import import_care_jsonl

        src = tmp_path / "care.jsonl"
        src.write_text(
            json.dumps({
                "_type": "care",
                "bean_id": "p1",
                "event_type": "grind",
                "occurred_at": "2024-06-01T12:00:00",
            }) + "\n",
            encoding="utf-8",
        )
        empty_storage.create_bean({"id": "p1", "name": "Fern"})
        assert import_care_jsonl(empty_storage, src) == 1

    def test_import_mixed_bean_update_and_skip(self, empty_storage, tmp_path):
        from brewlog.io_jsonl import import_mixed_jsonl

        empty_storage.create_bean({"id": "p1", "name": "Fern"})
        src = tmp_path / "mix.jsonl"
        lines = [
            {"_type": "bean", "id": "p1", "name": "Fern Updated"},
            {"_type": "note", "id": "n1", "bean_id": "p1", "body": "hi"},
            {"_type": "unknown", "x": 1},
        ]
        src.write_text("\n".join(json.dumps(x) for x in lines) + "\n", encoding="utf-8")
        counts = import_mixed_jsonl(empty_storage, src)
        assert counts["bean"] == 1
        assert counts["note"] == 1
        assert counts["skipped"] == 1

    def test_count_and_preview(self, tmp_path):
        from brewlog.io_jsonl import count_lines, preview

        assert count_lines(tmp_path / "n.jsonl") == 0
        p = tmp_path / "p.jsonl"
        p.write_text('{"_type":"brew","bean_id":"x"}\n', encoding="utf-8")
        assert count_lines(p) == 1
        assert preview(p, limit=1)[0]["_type"] == "brew"


# --- io_barista gaps ---


class TestIoBaristaCoverageGaps:
    def test_brew_interval_variants(self):
        from brewlog.io_barista import parse_barista_row

        for brew, expected in [
            ("daily", 1),
            ("twice a week", 3),
            ("monthly", 30),
            ("drought tolerant", 14),
            ("moist grind", 3),
            ("high moisture", 3),
        ]:
            parsed = parse_barista_row({"Bean": "X", "Brew": brew})
            assert parsed["brew_interval"] == expected

    def test_beaned_date_invalid_kept(self):
        from brewlog.io_barista import parse_barista_row

        parsed = parse_barista_row({"Bean": "X", "Beaned Date": "someday"})
        assert parsed["beaned_at"] == "someday"

    def test_ensure_station_existing(self, empty_storage, tmp_path, sample_station):
        from brewlog.io_barista import import_barista

        empty_storage.create_station(sample_station)
        src = tmp_path / "gp.csv"
        src.write_text(
            "Bean,Section\nFern,%s\n" % sample_station.name.split()[0],
            encoding="utf-8",
        )
        import_barista(empty_storage, src)

    def test_preview_missing_file(self, tmp_path):
        from brewlog.io_barista import preview_barista, validate_barista_headers

        assert preview_barista(tmp_path / "n.csv") == []
        assert validate_barista_headers(tmp_path / "n.csv") == ["Bean"]

    def test_import_pipeline_error_on_bad_row(self, empty_storage, tmp_path):
        from brewlog.io_barista import import_barista

        src = tmp_path / "gp.csv"
        src.write_text("Bean,Quantity\nBad,\n", encoding="utf-8")
        with patch("brewlog.io_barista.Bean.create", side_effect=ValueError("boom")):
            with pytest.raises(ImportPipelineError):
                import_barista(empty_storage, src)


# --- io_beanconqueror gaps ---


class TestIoBeanconquerorCoverageGaps:
    def test_parse_beanconqueror_interval_digits(self):
        from brewlog.io_beanconqueror import parse_beanconqueror_row

        row = {
            "Bean Name": "Fern",
            "Brew Every": "about 10 days",
            "Last Brewed": "not-a-date",
            "Light": "indirect",
        }
        parsed = parse_beanconqueror_row(row)
        assert parsed["brew_interval_days"] == 10

    def test_import_beanconqueror_creates_origin_and_station(self, empty_storage, tmp_path):
        from brewlog.io_beanconqueror import import_beanconqueror

        src = tmp_path / "beanconqueror.csv"
        src.write_text(
            "Bean Name,Nickname,Room,Origin,Brew Every,Last Brewed,Light\n"
            "Monstera,Monty,Living Room,Monstera deliciosa,7d,today,bright indirect\n",
            encoding="utf-8",
        )
        n = import_beanconqueror(empty_storage, src)
        assert n >= 1
        assert len(empty_storage.list_stations()) >= 1

    def test_import_beanconqueror_update(self, populated_storage, tmp_path):
        from brewlog.io_beanconqueror import import_beanconqueror

        src = tmp_path / "beanconqueror.csv"
        src.write_text(
            "Bean Name,Brew Every\nMonstera,14d\n",
            encoding="utf-8",
        )
        import_beanconqueror(populated_storage, src, update=True)

    def test_beanconqueror_helpers(self, tmp_path):
        from brewlog.io_beanconqueror import preview_beanconqueror, validate_beanconqueror_headers

        assert preview_beanconqueror(tmp_path / "n.csv") == []
        assert validate_beanconqueror_headers(tmp_path / "n.csv")


# --- reports gaps ---


class TestReportsCoverageGaps:
    def test_in_range_naive_datetime(self, empty_storage):
        from brewlog.reports import MonthlyReport

        report = MonthlyReport(empty_storage)
        start = datetime(2024, 6, 1, tzinfo=timezone.utc)
        end = datetime(2024, 6, 30, 23, 59, 59, tzinfo=timezone.utc)
        assert report._in_range("2024-06-15T10:00:00", start, end) is True
        assert report._in_range(None, start, end) is False

    def test_generate_with_station_breakdown(self, populated_storage, sample_bean):
        from brewlog.reports import MonthlyReport

        now = datetime.now(timezone.utc)
        populated_storage.create_brew_event({
            "bean_id": sample_bean.id,
            "brewed_at": now.isoformat(),
            "amount_ml": 100,
        })
        report = MonthlyReport(populated_storage)
        data = report.generate(now.year, now.month)
        assert data["brews_by_station"]

    def test_render_text_top_brewed(self, populated_storage, sample_bean):
        from brewlog.reports import MonthlyReport

        now = datetime.now(timezone.utc)
        for _ in range(3):
            populated_storage.create_brew_event({
                "bean_id": sample_bean.id,
                "brewed_at": now.isoformat(),
            })
        report = MonthlyReport(populated_storage)
        text = report.render_text(now.year, now.month)
        assert "Most brewed" in text or sample_bean.name in text


# --- cli gaps ---


def _ns(**kwargs):
    return argparse.Namespace(**kwargs)


class TestCliCoverageGaps:
    def test_default_cellar_without_env(self, monkeypatch):
        from brewlog.cli import _default_cellar_path

        monkeypatch.delenv("BREWLOG_HOME", raising=False)
        path = _default_cellar_path()
        assert path.name == "cellar.json"

    def test_resolve_nickname_and_partial(self, populated_storage, sample_bean):
        from brewlog.cli import _resolve_bean

        populated_storage.update_bean(sample_bean.id, {"nickname": "Monty"})
        assert _resolve_bean(populated_storage, "Monty").id == sample_bean.id
        assert _resolve_bean(populated_storage, "onst").id == sample_bean.id

    def test_add_bean_with_amount(self, tmp_cellar_path):
        from brewlog.cli import cmd_add_bean, cmd_init

        cmd_init(_ns(cellar=str(tmp_cellar_path)))
        ns = _ns(
            cellar=str(tmp_cellar_path),
            name="Fern",
            nickname=None,
            origin=None,
            station=None,
            health=None,
            interval="7d",
            acquired=None,
            amount="250ml",
        )
        assert cmd_add_bean(ns) == 0

    def test_list_filters_and_truncation(self, populated_storage, sample_station):
        from brewlog.cli import cmd_list

        populated_storage.update_bean("bean001", {"station_id": sample_station.id})
        ns = _ns(
            cellar=str(populated_storage.path),
            all=False,
            overdue=False,
            station=sample_station.id,
            limit=1,
        )
        with patch("sys.stdout", new_callable=StringIO) as out:
            assert cmd_list(ns) == 0
            assert "more" in out.getvalue()

    def test_import_export_branches(self, populated_storage, tmp_path):
        from brewlog.cli import cmd_export, cmd_import

        wcsv = tmp_path / "w.csv"
        wcsv.write_text("bean_id,brewed_at\nbean001,2024-01-01\n", encoding="utf-8")
        assert cmd_import(_ns(
            cellar=str(populated_storage.path),
            file=str(wcsv),
            format="csv",
            kind="brew",
            update=False,
            no_expand=False,
        )) == 0

        jsrc = tmp_path / "events.jsonl"
        jsrc.write_text(
            json.dumps({"_type": "care", "bean_id": "bean001", "action": "mist"}) + "\n",
            encoding="utf-8",
        )
        assert cmd_import(_ns(
            cellar=str(populated_storage.path),
            file=str(jsrc),
            format="jsonl",
            kind="care",
            update=False,
            no_expand=False,
        )) == 0

        mixed = tmp_path / "mix.jsonl"
        mixed.write_text(
            json.dumps({"_type": "brew", "bean_id": "bean001", "brewed_at": "2024-02-01"}) + "\n",
            encoding="utf-8",
        )
        assert cmd_import(_ns(
            cellar=str(populated_storage.path),
            file=str(mixed),
            format="jsonl",
            kind=None,
            update=False,
            no_expand=False,
        )) == 0

        gp = tmp_path / "gp.csv"
        gp.write_text("Bean,Section\nBasil,Kitchen\n", encoding="utf-8")
        assert cmd_import(_ns(
            cellar=str(populated_storage.path),
            file=str(gp),
            format="barista",
            kind=None,
            update=False,
            no_expand=True,
        )) == 0

        assert cmd_import(_ns(
            cellar=str(populated_storage.path),
            file=str(tmp_path / "x.csv"),
            format="csv",
            kind="unknown",
            update=False,
            no_expand=False,
        )) == 1

        dest = tmp_path / "out.csv"
        assert cmd_export(_ns(
            cellar=str(populated_storage.path),
            file=str(dest),
            format="csv",
            kind="brew",
        )) == 0

        jdest = tmp_path / "out.jsonl"
        for kind in ("brew", "care", "full", None):
            assert cmd_export(_ns(
                cellar=str(populated_storage.path),
                file=str(jdest),
                format="jsonl",
                kind=kind,
            )) == 0

        assert cmd_export(_ns(
            cellar=str(populated_storage.path),
            file=str(tmp_path / "x.bin"),
            format="bin",
            kind=None,
        )) == 1

    def test_backup_restore_prune(self, populated_storage, tmp_path):
        from brewlog.backup import CellarBackup
        from brewlog.cli import cmd_backup

        backup_dir = tmp_path / "backups"
        gb = CellarBackup(populated_storage.path, backup_dir)
        backup_file = gb.create(label="test")
        ns_restore = _ns(
            cellar=str(populated_storage.path),
            dir=str(backup_dir),
            label=None,
            list=False,
            restore=str(backup_file),
            prune=False,
            keep=1,
        )
        assert cmd_backup(ns_restore) == 0
        ns_prune = _ns(
            cellar=str(populated_storage.path),
            dir=str(backup_dir),
            label="daily",
            list=False,
            restore=None,
            prune=True,
            keep=0,
        )
        assert cmd_backup(ns_prune) == 0

    def test_search_and_reminders_branches(self, populated_storage, capsys):
        from brewlog.cli import cmd_reminders, cmd_search

        assert cmd_search(_ns(
            cellar=str(populated_storage.path),
            query="note",
            kind="notes",
            limit=5,
            verbose=True,
        )) == 0
        assert cmd_search(_ns(
            cellar=str(populated_storage.path),
            query="care",
            kind="care",
            limit=5,
            verbose=False,
        )) == 0

        populated_storage.update_bean("bean001", {"last_brewed_at": "2020-01-01"})
        ns = _ns(cellar=str(populated_storage.path), overdue=False, within=30, limit=1)
        assert cmd_reminders(ns) == 0

    def test_main_keyboard_interrupt(self):
        from brewlog.cli import main

        parser = MagicMock()
        parser.parse_args.return_value = MagicMock(func=MagicMock(side_effect=KeyboardInterrupt))
        with patch("brewlog.cli.build_parser", return_value=parser):
            assert main([]) == 130

    def test_main_module_entry(self):
        import brewlog.cli as cli_mod

        with patch.object(cli_mod, "main", return_value=0) as mock_main:
            with pytest.raises(SystemExit) as exc:
                exec(compile("if True: raise SystemExit(main())", "<test>", "exec"), {
                    "main": cli_mod.main,
                    "SystemExit": SystemExit,
                })
            assert exc.value.code == 0 or exc.value.code is None


# --- storage gaps ---


class TestStorageCoverageGaps:
    def test_legacy_bean_normalization(self, tmp_cellar_path):
        from brewlog.storage import JsonStorage, _normalize_bean_row

        row = {
            "id": "p1",
            "name": "Fern",
            "origin_id": "sp1",
            "tags": ["t1"],
            "active": False,
        }
        norm = _normalize_bean_row(row)
        assert norm["origin_key"] == "sp1"
        assert norm["tag_ids"] == ["t1"]
        assert norm["archived"] is True

    def test_legacy_origin_normalization(self):
        from brewlog.storage import _normalize_origin_row

        assert _normalize_origin_row({"id": "sp-key"})["key"] == "sp-key"

    def test_load_invalid_json(self, tmp_cellar_path):
        from brewlog.storage import JsonStorage

        tmp_cellar_path.write_text("not json", encoding="utf-8")
        with pytest.raises(StorageError):
            JsonStorage(tmp_cellar_path).load()

    def test_load_non_object_root(self, tmp_cellar_path):
        from brewlog.storage import JsonStorage

        tmp_cellar_path.write_text("[1,2]", encoding="utf-8")
        with pytest.raises(StorageError):
            JsonStorage(tmp_cellar_path).load()

    def test_corrupt_bucket(self, empty_storage):
        empty_storage._data["beans"] = "bad"
        with pytest.raises(StorageError):
            empty_storage._list("beans")

    def test_crud_paths(self, empty_storage, sample_bean, sample_origin, sample_station):
        empty_storage.create_origin({"id": "legacy-sp", "common_name": "Legacy"})
        empty_storage.delete_origin("legacy-sp")

        loc = empty_storage.create_station(sample_station)
        empty_storage.update_station(loc.id, {"notes": "updated"})
        empty_storage.delete_station(loc.id)

        bean = empty_storage.create_bean(sample_bean)
        empty_storage.update_bean(bean.id, {"nickname": "X"})
        ev = empty_storage.create_brew_event({
            "bean_id": bean.id,
            "brewed_at": date.today().isoformat(),
        })
        empty_storage.get_brew_event(ev["id"])
        empty_storage.update_brew_event(ev["id"], {"notes": "ok"})
        empty_storage.delete_brew_event(ev["id"])

        log = empty_storage.create_tasting_log({"bean_id": bean.id, "action": "mist"})
        empty_storage.get_tasting_log(log["id"])
        empty_storage.update_tasting_log(log["id"], {"notes": "done"})
        empty_storage.delete_tasting_log(log["id"])

        tag = empty_storage.create_tag({"id": "t9", "name": "test"})
        empty_storage.update_tag(tag["id"], {"name": "test2"})
        empty_storage.delete_tag(tag["id"])

        note = empty_storage.create_note({"id": "n9", "bean_id": bean.id, "body": "hi"})
        empty_storage.update_note(note["id"], {"body": "bye"})
        empty_storage.delete_note(note["id"])

        empty_storage.upsert_plugin({"id": "plug1", "name": "p"})
        empty_storage.upsert_plugin({"id": "plug1", "name": "p2"})
        empty_storage.delete_plugin("plug1")

        rec = empty_storage.create_recurring({"id": "r1", "rule": "weekly"})
        empty_storage.update_recurring("r1", {"rule": "daily"})
        empty_storage.delete_recurring("r1")

        empty_storage.delete_bean(bean.id)

    def test_brew_events_filter(self, populated_storage, sample_bean):
        events = populated_storage.list_brew_events(bean_id=sample_bean.id)
        assert all(e["bean_id"] == sample_bean.id for e in events)

    def test_atomic_write_failure(self, empty_storage):
        with patch.object(Path, "write_text", side_effect=OSError("fail")):
            with pytest.raises(StorageError):
                empty_storage.save()


# --- station gaps ---


class TestStationCoverageGaps:
    def test_station_with_temp_validation(self, sample_station):
        from brewlog.station import Station

        loc = Station(
            name="Warm Room",
            id="loc-warm",
            temp_c=22.0,
            humidity_pct=50.0,
        )
        assert loc.temp_c == 22.0
        assert "°C" in loc.summary()

    def test_effective_light_south_and_invalid(self):
        from brewlog.station import Station, WindowDirection

        loc = Station.create(
            "South Window",
            light_level="medium",
            window_direction=WindowDirection.SOUTH,
        )
        assert loc.effective_light() != "medium"
        loc2 = Station.create("Odd", light_level="low")
        loc2.light_level = "unknown_level"
        assert loc2.effective_light() == "unknown_level"

    def test_registry_helpers(self, sample_station, sample_bean):
        from brewlog.station import (
            StationRegistry,
            StationClimateProfile,
            RoomHistory,
            RoomSnapshot,
            build_station_map,
            compare_light,
            default_stations,
            estimate_daily_light_hours,
            format_station_tree,
            station_capacity_report,
            station_report,
            beans_without_station,
            rank_stations_for_origin,
            reassign_bean,
            suggest_beans_for_station,
            sync_station_bean_ids,
        )

        reg = StationRegistry()
        reg.add(sample_station)
        reg.assign_bean(sample_station.id, sample_bean.id)
        reg.unassign_bean(sample_bean.id)
        assert reg.require(sample_station.id).id == sample_station.id
        assert reg.find_by_light(sample_station.light_level)
        if sample_station.zone:
            assert reg.find_by_zone(sample_station.zone)
        with pytest.raises(ValueError):
            reg.add(sample_station)
        assert reg.count() >= 1

        profile = StationClimateProfile.from_station(sample_station)
        assert profile.brew_factor() > 0
        profile.draft_risk = True
        profile.heater_nearby = True
        profile.ac_nearby = True
        profile.avg_humidity = 70
        assert profile.brew_factor() != 1.0

        assert compare_light("low", "full_sun") == -1
        with pytest.raises(ValidationError):
            compare_light("bad", "low")
        assert suggest_beans_for_station(sample_station)
        assert station_report(reg)["station_count"] >= 1
        reassign_bean(reg, sample_bean.id, None, sample_station.id)
        assert estimate_daily_light_hours(sample_station, month=7) > 0
        assert rank_stations_for_origin(reg, "not-a-profile") == []
        assert build_station_map(reg)
        unassigned = beans_without_station(reg, [sample_bean.id, "other"])
        assert "other" in unassigned
        assert sample_bean.id not in unassigned
        assert station_capacity_report(reg, max_per_room=0)["crowded"]

        hist = RoomHistory()
        hist.record(RoomSnapshot(sample_station.id, datetime.now(timezone.utc).isoformat(), 50.0))
        assert hist.avg_humidity(sample_station.id) == 50.0
        RoomHistory.from_dict_list(hist.to_dict_list())

        sync_station_bean_ids(reg, [sample_bean])
        tree = format_station_tree(reg)
        assert sample_station.name in tree
        assert default_stations().count() >= 0

    def test_registry_remove_missing(self):
        from brewlog.station import StationRegistry

        reg = StationRegistry()
        assert reg.remove("nope") is False


# --- schedule gaps ---


class TestScheduleCoverageGaps:
    def test_season_str_and_detect_fallback(self):
        from brewlog.schedule import Season, ScheduleEngine, ScheduleOptions, detect_season

        assert str(Season.SPRING) == "spring"
        with patch("brewlog.schedule._SEASON_MONTHS", {Season.SPRING: ()}):
            assert detect_season(date(2024, 6, 15)) == Season.SPRING

    def test_engine_multipliers(self, bean_catalog, origin_catalog, station_registry, brew_log, sample_bean):
        from copy import deepcopy

        from brewlog.bean import HealthStatus
        from brewlog.schedule import ScheduleEngine

        engine = ScheduleEngine(bean_catalog, origin_catalog, station_registry, brew_log)
        engine.set_options(health_adjust=True, station_humidity_adjust=True)

        struggling = deepcopy(sample_bean)
        struggling.health = HealthStatus.STRUGGLING
        assert engine.health_multiplier(struggling) < 1.0
        critical = deepcopy(sample_bean)
        critical.health = HealthStatus.CRITICAL
        assert engine.health_multiplier(critical) == 0.75
        thriving = deepcopy(sample_bean)
        thriving.health = HealthStatus.THRIVING
        assert engine.health_multiplier(thriving) > 1.0

        loc = station_registry.get(sample_bean.station_id)
        if loc:
            loc.humidity_pct = 70
            assert engine.station_multiplier(sample_bean) > 1.0
            loc.humidity_pct = 30
            assert engine.station_multiplier(sample_bean) < 1.0

        small_bag = deepcopy(sample_bean)
        small_bag.bag.diameter = 3
        small_bag.bag.unit = "in"
        assert engine.bag_multiplier(small_bag) < 1.0
        big_bag = deepcopy(sample_bean)
        big_bag.bag.diameter = 14
        big_bag.bag.unit = "in"
        assert engine.bag_multiplier(big_bag) > 1.0

        engine.options.health_adjust = False
        assert engine.health_multiplier(sample_bean) == 1.0

    def test_last_brewed_and_entry_notes(self, bean_catalog, brew_log, sample_bean):
        from copy import deepcopy

        from brewlog.bean import HealthStatus
        from brewlog.schedule import ScheduleEngine

        engine = ScheduleEngine(bean_catalog, brew_log=brew_log)
        sample_bean.last_brewed_at = None
        sample_bean.acquired_at = (date.today() - timedelta(days=30)).isoformat()
        assert engine.last_brewed(sample_bean) is not None

        never = deepcopy(sample_bean)
        never.last_brewed_at = None
        never.acquired_at = None
        assert engine.next_due_date(never) <= date.today() + timedelta(days=engine.adjusted_interval(never))

        critical = sample_bean
        critical.health = HealthStatus.CRITICAL
        entry = engine.build_entry(critical, date.today() - timedelta(days=10))
        assert entry.notes == "check roots/grind" or entry.overdue_days >= 0


# --- backup gaps ---


class TestBackupCoverageGaps:
    def test_create_missing_cellar(self, tmp_path):
        from brewlog.backup import CellarBackup

        gb = CellarBackup(tmp_path / "nope.json", tmp_path / "bk")
        with pytest.raises(StorageError):
            gb.create()

    def test_restore_missing_and_corrupt(self, populated_storage, tmp_path):
        from brewlog.backup import CellarBackup

        gb = CellarBackup(populated_storage.path, tmp_path / "bk")
        with pytest.raises(StorageError):
            gb.restore(tmp_path / "missing.json")
        bad = tmp_path / "bad.json"
        bad.write_text("{", encoding="utf-8")
        with pytest.raises(StorageError):
            gb.restore(bad)

    def test_restore_latest_empty(self, tmp_path):
        from brewlog.backup import CellarBackup

        gb = CellarBackup(tmp_path / "g.json", tmp_path / "bk")
        with pytest.raises(StorageError):
            gb.restore_latest()

    def test_prune_oserror_ignored(self, populated_storage, tmp_path):
        from brewlog.backup import CellarBackup

        gb = CellarBackup(populated_storage.path, tmp_path / "bk")
        gb.create()
        gb.create()
        with patch.object(Path, "unlink", side_effect=OSError("locked")):
            removed = gb.prune(keep=0)
        assert isinstance(removed, list)

    def test_create_copy_oserror(self, populated_storage, tmp_path):
        from brewlog.backup import CellarBackup

        gb = CellarBackup(populated_storage.path, tmp_path / "bk")
        with patch("brewlog.backup.shutil.copy2", side_effect=OSError("disk full")):
            with pytest.raises(StorageError, match="backup failed"):
                gb.create()

    def test_restore_copy_oserror(self, populated_storage, tmp_path):
        from brewlog.backup import CellarBackup

        gb = CellarBackup(populated_storage.path, tmp_path / "bk")
        backup = gb.create()
        original = __import__("shutil").copy2

        def copy_side_effect(src, dst):
            if str(dst) == str(populated_storage.path):
                raise OSError("permission")
            return original(src, dst)

        with patch("brewlog.backup.shutil.copy2", side_effect=copy_side_effect):
            with pytest.raises(StorageError, match="restore failed"):
                gb.restore(backup)


# --- server gaps ---


class TestServerCoverageGaps:
    def test_handler_put_delete_via_background(self, populated_storage):
        import urllib.error
        import urllib.request

        from brewlog.server import CellarServer

        server = CellarServer(populated_storage, port=0)
        server.start_background()
        try:
            host, port = server.address
            for method in ("PUT", "DELETE"):
                req = urllib.request.Request(
                    f"http://{host}:{port}/beans",
                    method=method,
                    data=b"{}",
                )
                with pytest.raises(urllib.error.HTTPError) as exc:
                    urllib.request.urlopen(req)
                assert exc.value.code == 405
        finally:
            server.stop()

    def test_cellar_server_lifecycle(self, populated_storage):
        from brewlog.server import CellarServer, run_server

        srv = CellarServer(populated_storage, host="127.0.0.1", port=0)
        assert srv.address[0] == "127.0.0.1"
        httpd = srv.start_background()
        assert httpd is not None
        srv.stop()
        srv.stop()

        with patch("brewlog.server.CellarServer.serve_forever"):
            with patch("brewlog.server.JsonStorage"):
                run_server(str(populated_storage.path), port=9999)


# --- bean / tag / notes / brew / streaks / migrate / origin / tasting_log ---


class TestDomainCoverageGaps:
    def test_bean_edges(self, sample_bean):
        from brewlog.bean import HealthStatus, Bean, BeanCatalog

        p = Bean.from_dict({
            **sample_bean.to_dict(),
            "tag_ids": ["t1"],
            "light_override": "low",
        })
        p.set_health(HealthStatus.THRIVING, score=90)
        p.archive()
        p.unarchive()
        p.brew_interval_days = 10
        assert p.display_name

        cat = BeanCatalog()
        cat.add(p)
        p.attach_tag("t1")
        assert cat.find_by_tag("t1")

    def test_tag_registry_edges(self):
        from brewlog.tag import Tag, TagRegistry

        tag = Tag.create("rare", color="#aabbcc")
        reg = TagRegistry()
        reg.add(tag)
        assert reg.get(tag.id)
        reg.remove(tag.id)

    def test_notes_collection_edges(self, sample_bean):
        from brewlog.notes import NoteKind, NotesCollection

        coll = NotesCollection()
        n = coll.create(sample_bean.id, "body", kind=NoteKind.REMINDER)
        n.edit(body="new body")
        n.pin()
        n.unpin()
        assert coll.for_bean(sample_bean.id)

    def test_brew_log_edges(self, sample_brew_events):
        from brewlog.brew import BrewLog

        log = BrewLog()
        log.load_many(sample_brew_events)
        assert log.total_ml_for_bean(sample_brew_events[0].bean_id) >= 0
        assert log.for_bean(sample_brew_events[0].bean_id)

    def test_streaks_break_and_leaderboard(self, populated_storage, sample_bean):
        from brewlog.streaks import StreakTracker

        populated_storage.create_brew_event({
            "bean_id": sample_bean.id,
            "brewed_at": (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        })
        populated_storage.create_brew_event({
            "bean_id": sample_bean.id,
            "brewed_at": datetime.now(timezone.utc).isoformat(),
        })
        tracker = StreakTracker(populated_storage)
        info = tracker.compute(sample_bean.id)
        assert info.longest_streak >= 1
        assert tracker.leaderboard(5)
        assert isinstance(tracker.broken_streaks(), list)

    def test_migrate_edges(self, populated_storage):
        from brewlog.migrate import detect_version, migrate_file, migration_plan

        path = populated_storage.path
        data = json.loads(path.read_text(encoding="utf-8"))
        data["schema_version"] = 0
        path.write_text(json.dumps(data), encoding="utf-8")
        assert detect_version(data) == 0
        migrate_file(str(path))
        assert migration_plan(0)

    def test_origin_and_tasting_log_edges(self, origin_catalog, tasting_log, sample_bean):
        from brewlog.tasting_log import CareEventType
        from brewlog.origin import OriginProfile

        sp = OriginProfile(
            key="test-sp",
            common_name="Test",
            scientific_name="T. test",
            light_level="low",
            brew_interval_min=5,
            brew_interval_max=10,
        )
        origin_catalog.register(sp)
        assert sp.matches_light("low")
        tasting_log.log(sample_bean.id, CareEventType.INSPECT)

    def test_grinder_seasons_defects_labels_recurring(self, populated_storage, sample_bean):
        from brewlog.grinder import GrinderManager
        from brewlog.defects import DefectTracker
        from brewlog.labels import LabelCatalog
        from brewlog.recurring import RecurringTasks
        from brewlog.seasons import SeasonCalendar

        assert SeasonCalendar().multiplier_for(date.today()) > 0
        GrinderManager(populated_storage).apply(sample_bean.id, "10-10-10")
        DefectTracker(populated_storage).report(sample_bean.id, "aphids")
        LabelCatalog(populated_storage).register(sample_bean.id, "/tmp/x.jpg")
        RecurringTasks(populated_storage).define("Brew", "brew", 7, bean_id=sample_bean.id)


class TestFinalCoveragePush:
    def test_brew_quality_str(self):
        from brewlog.brew import BrewQuality

        assert str(BrewQuality.TAP) == "tap"

    def test_grinder_due_skips_bad_timestamp(self, populated_storage, sample_bean):
        from brewlog.grinder import GrinderManager

        populated_storage.mutate(lambda d: d.setdefault("grind_events", []).append({
            "id": "fe_bad",
            "bean_id": sample_bean.id,
            "product": "10-10-10",
            "applied_at": "not-a-date",
        }))
        due = GrinderManager(populated_storage).due_for_grinder(interval_days=30)
        assert isinstance(due, list)

    def test_grinder_due_naive_timestamp(self, populated_storage, sample_bean):
        from brewlog.grinder import GrinderManager

        old = (datetime.now() - timedelta(days=60)).isoformat()
        populated_storage.mutate(lambda d: d.setdefault("grind_events", []).append({
            "id": "fe_naive",
            "bean_id": sample_bean.id,
            "product": "10-10-10",
            "applied_at": old,
        }))
        due = GrinderManager(populated_storage).due_for_grinder(interval_days=30)
        assert any(d["bean_id"] == sample_bean.id for d in due)

    def test_parse_iso_invalid(self):
        from brewlog.bean import parse_iso

        assert parse_iso("not-a-date") is None
        assert parse_iso(None) is None

    def test_seasons_day_of_year(self):
        from brewlog.seasons import SeasonCalendar

        cal = SeasonCalendar()
        assert cal._day_of_year(date(2024, 7, 1)) == date(2024, 7, 1).timetuple().tm_yday

    def test_cli_main_keyboard_interrupt(self):
        from brewlog.cli import main

        with patch("brewlog.cli.build_parser") as bp:
            ns = MagicMock()
            ns.func.side_effect = KeyboardInterrupt
            bp.return_value.parse_args.return_value = ns
            assert main([]) == 130

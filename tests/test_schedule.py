"""Tests for brewlog.schedule."""

from datetime import date, timedelta

import pytest

from brewlog.bean import HealthStatus, BeanCatalog
from brewlog.schedule import (
    Season,
    detect_season,
    ScheduleEntry,
    ScheduleOptions,
    ScheduleEngine,
    compute_next_brew,
    month_calendar,
    format_schedule_text,
    group_by_station,
    estimate_weekly_brew_ml,
    reschedule_after_brew,
    compare_seasons,
    ScheduleReport,
    build_schedule_report,
    beans_by_urgency,
    next_n_days,
    interval_audit,
    apply_seasonal_intervals,
    schedule_conflicts,
)


class TestDetectSeason:
    @pytest.mark.parametrize("month,expected", [
        (6, Season.SUMMER), (12, Season.WINTER), (3, Season.SPRING), (10, Season.FALL),
    ])
    def test_season_for_month(self, month, expected):
        assert detect_season(date(2024, month, 15)) == expected


class TestScheduleEntry:
    def test_days_until_due(self):
        entry = ScheduleEntry(
            bean_id="p1",
            bean_name="Fern",
            next_due=(date.today() + timedelta(days=3)).isoformat(),
            base_interval_days=7,
            adjusted_interval_days=7,
            season="summer",
        )
        assert entry.days_until_due() == 3

    def test_to_dict_from_dict(self):
        entry = ScheduleEntry(
            bean_id="p1",
            bean_name="Fern",
            next_due=date.today().isoformat(),
            base_interval_days=7,
            adjusted_interval_days=7,
            season="spring",
        )
        restored = ScheduleEntry.from_dict(entry.to_dict())
        assert restored.bean_id == "p1"


class TestScheduleEngine:
    def test_build_entry(self, bean_catalog, origin_catalog, station_registry, sample_bean):
        engine = ScheduleEngine(
            beans=bean_catalog,
            origin=origin_catalog,
            stations=station_registry,
        )
        entry = engine.build_entry(sample_bean)
        assert entry.bean_id == sample_bean.id

    def test_overdue(self, bean_catalog, origin_catalog, sample_bean):
        sample_bean.last_brewed_at = (date.today() - timedelta(days=30)).isoformat()
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        overdue = engine.overdue()
        assert len(overdue) >= 1

    def test_today(self, bean_catalog, origin_catalog, sample_bean):
        sample_bean.last_brewed_at = (date.today() - timedelta(days=30)).isoformat()
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        due = engine.today()
        assert len(due) >= 1

    def test_week_schedule(self, bean_catalog, origin_catalog):
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        entries = engine.week_schedule()
        assert isinstance(entries, list)

    def test_full_schedule(self, bean_catalog, origin_catalog):
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        entries = engine.full_schedule()
        assert len(entries) == 2

    def test_adjusted_interval_season(self, bean_catalog, origin_catalog, sample_bean):
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        engine.set_options(season_override=Season.WINTER)
        interval = engine.adjusted_interval(sample_bean)
        assert interval >= engine.options.min_interval_days

    def test_health_multiplier_critical(self, bean_catalog, origin_catalog, sample_bean):
        sample_bean.set_health(HealthStatus.CRITICAL)
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        mult = engine.health_multiplier(sample_bean)
        assert mult < 1.0

    def test_station_multiplier(self, bean_catalog, origin_catalog, station_registry, sample_bean):
        engine = ScheduleEngine(
            beans=bean_catalog,
            origin=origin_catalog,
            stations=station_registry,
        )
        mult = engine.station_multiplier(sample_bean)
        assert mult > 0

    def test_bag_multiplier_small_bag(self, bean_catalog, origin_catalog, sample_bean):
        sample_bean.bag.diameter = 3.0
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        assert engine.bag_multiplier(sample_bean) < 1.0

    def test_preview_interval_change(self, bean_catalog, origin_catalog, sample_bean):
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        preview = engine.preview_interval_change(sample_bean, 14)
        assert preview["new_base_days"] == 14

    def test_summarize_week(self, bean_catalog, origin_catalog):
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        summary = engine.summarize_week()
        assert "total_due" in summary

    def test_sync_bean_intervals_from_origin(self, bean_catalog, origin_catalog, sample_bean2):
        sample_bean2.brew_interval_days = 7
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        updated = engine.sync_bean_intervals_from_origin()
        assert updated >= 0


class TestScheduleHelpers:
    def test_compute_next_brew(self, sample_bean):
        nxt = compute_next_brew(sample_bean)
        assert isinstance(nxt, date)

    def test_format_schedule_text(self, bean_catalog, origin_catalog, sample_bean):
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        text = format_schedule_text([engine.build_entry(sample_bean)])
        assert "Brew schedule" in text

    def test_group_by_station(self, bean_catalog, origin_catalog, station_registry):
        engine = ScheduleEngine(
            beans=bean_catalog,
            origin=origin_catalog,
            stations=station_registry,
        )
        groups = group_by_station(engine)
        assert isinstance(groups, dict)

    def test_estimate_weekly_brew_ml(self, bean_catalog, origin_catalog):
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        ml = estimate_weekly_brew_ml(engine)
        assert ml >= 0

    def test_reschedule_after_brew(self, bean_catalog, origin_catalog, sample_bean):
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        entry = reschedule_after_brew(engine, sample_bean)
        assert entry.last_brewed_at == date.today().isoformat()

    def test_compare_seasons(self, bean_catalog, origin_catalog, sample_bean):
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        seasons = compare_seasons(engine, sample_bean)
        assert "winter" in seasons
        assert seasons["winter"] >= seasons["summer"]

    def test_build_schedule_report(self, bean_catalog, origin_catalog):
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        report = build_schedule_report(engine)
        assert isinstance(report, ScheduleReport)
        assert report.due_today >= 0

    def test_beans_by_urgency(self, bean_catalog, origin_catalog):
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        entries = beans_by_urgency(engine)
        assert len(entries) == 2

    def test_next_n_days(self, bean_catalog, origin_catalog):
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        buckets = next_n_days(engine, n=14)
        assert isinstance(buckets, dict)

    def test_interval_audit(self, bean_catalog, origin_catalog):
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        rows = interval_audit(engine)
        assert len(rows) == 2

    def test_apply_seasonal_intervals_dry_run(self, bean_catalog, origin_catalog):
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        changes = apply_seasonal_intervals(engine, dry_run=True)
        assert len(changes) == 2

    def test_schedule_conflicts(self, bean_catalog, origin_catalog, station_registry):
        engine = ScheduleEngine(
            beans=bean_catalog,
            origin=origin_catalog,
            stations=station_registry,
        )
        entries = engine.full_schedule()
        conflicts = schedule_conflicts(entries)
        assert isinstance(conflicts, list)

    def test_month_calendar(self, bean_catalog, origin_catalog):
        engine = ScheduleEngine(beans=bean_catalog, origin=origin_catalog)
        cal = month_calendar(engine, date.today().year, date.today().month)
        assert isinstance(cal, dict)

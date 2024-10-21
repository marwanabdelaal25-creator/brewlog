"""Tests for brewlog.brew."""

from datetime import date, timedelta

import pytest

from brewlog.brew import (
    BrewQuality,
    BrewEvent,
    BrewLog,
    BrewBatch,
    log_batch_brew,
    weekly_brew_stats,
    beans_brewed_on,
    export_brew_csv_rows,
    detect_brew_drift,
    brew_history_summary,
    compare_beans_brew_use,
    missed_brews_estimate,
    filter_events_by_method,
    BrewAnalytics,
    merge_brew_logs,
)


class TestBrewEvent:
    def test_create(self, sample_bean):
        ev = BrewEvent.create(sample_bean.id, amount_ml=250.0)
        assert ev.bean_id == sample_bean.id

    def test_skip(self, sample_bean):
        ev = BrewEvent.skip(sample_bean.id, reason="travel")
        assert ev.skipped is True

    def test_brewed_date(self, sample_bean):
        ev = BrewEvent.create(
            sample_bean.id,
            brewed_at="2024-06-01",
        )
        assert ev.brewed_date == date(2024, 6, 1)

    def test_to_dict_from_dict(self, sample_bean):
        ev = BrewEvent.create(sample_bean.id, amount_ml=200.0)
        restored = BrewEvent.from_dict(ev.to_dict())
        assert restored.amount_ml == 200.0

    def test_summary(self, sample_bean):
        ev = BrewEvent.create(sample_bean.id, amount_ml=250.0)
        assert "250ml" in ev.summary()

    def test_skip_summary(self, sample_bean):
        ev = BrewEvent.skip(sample_bean.id, reason="vacation")
        assert "skipped" in ev.summary()


class TestBrewLog:
    def test_record_and_get(self, brew_log, sample_brew_events):
        assert brew_log.count() == 3

    def test_duplicate_raises(self, brew_log, sample_brew_events):
        with pytest.raises(ValueError):
            brew_log.record(sample_brew_events[0])

    def test_log_brew(self, sample_bean):
        log = BrewLog()
        ev = log.log_brew(sample_bean.id, amount_ml=300.0)
        assert ev.amount_ml == 300.0

    def test_for_bean(self, brew_log, sample_bean):
        events = brew_log.for_bean(sample_bean.id)
        assert len(events) == 2

    def test_last_for_bean(self, brew_log, sample_bean):
        last = brew_log.last_for_bean(sample_bean.id)
        assert last is not None
        assert not last.skipped

    def test_between(self, brew_log):
        start = date.today() - timedelta(days=30)
        end = date.today()
        events = brew_log.between(start, end)
        assert len(events) >= 1

    def test_total_ml_for_bean(self, brew_log, sample_bean):
        total = brew_log.total_ml_for_bean(sample_bean.id, days=30)
        assert total == 450.0

    def test_average_interval_days(self, brew_log, sample_bean):
        avg = brew_log.average_interval_days(sample_bean.id)
        assert avg == 7.0

    def test_count_for_bean(self, brew_log, sample_bean):
        assert brew_log.count_for_bean(sample_bean.id) == 2

    def test_remove_for_bean(self, brew_log, sample_bean):
        removed = brew_log.remove_for_bean(sample_bean.id)
        assert removed == 2

    def test_streak_days(self, brew_log, sample_bean):
        assert brew_log.streak_days(sample_bean.id) == 3

    def test_from_dict_list(self, sample_brew_events):
        log = BrewLog.from_dict_list([e.to_dict() for e in sample_brew_events])
        assert log.count() == 3


class TestBatchBrew:
    def test_log_batch_brew(self, sample_bean, sample_bean2):
        log = BrewLog()
        batch = log_batch_brew(
            log,
            {sample_bean.id: 250.0, sample_bean2.id: 150.0},
        )
        assert batch.total_ml == 400.0
        assert len(batch.event_ids) == 2


class TestBrewHelpers:
    def test_weekly_brew_stats(self, brew_log):
        stats = weekly_brew_stats(brew_log, weeks=4)
        assert "total_ml" in stats

    def test_beans_brewed_on(self, brew_log):
        today = date.today()
        ids = beans_brewed_on(brew_log, today - timedelta(days=3))
        assert isinstance(ids, list)

    def test_export_brew_csv_rows(self, brew_log):
        rows = export_brew_csv_rows(brew_log)
        assert rows[0][0] == "id"
        assert len(rows) > 1

    def test_detect_brew_drift(self, brew_log, sample_bean):
        result = detect_brew_drift(brew_log, sample_bean.id, 7)
        assert result["bean_id"] == sample_bean.id

    def test_detect_drift_not_enough_data(self, sample_bean):
        log = BrewLog()
        log.log_brew(sample_bean.id, amount_ml=100.0)
        result = detect_brew_drift(log, sample_bean.id, 7)
        assert result["drift"] is None

    def test_brew_history_summary(self, brew_log, sample_bean):
        summary = brew_history_summary(brew_log, sample_bean.id)
        assert summary["count"] == 2

    def test_compare_beans_brew_use(self, brew_log, sample_bean, sample_bean2):
        rows = compare_beans_brew_use(
            brew_log, [sample_bean.id, sample_bean2.id]
        )
        assert len(rows) == 2

    def test_missed_brews_estimate(self, brew_log, sample_bean):
        count = missed_brews_estimate(brew_log, sample_bean.id, 7)
        assert count >= 0

    def test_filter_events_by_method(self, brew_log):
        events = filter_events_by_method(brew_log, "top_brew")
        assert all(e.method == "top_brew" for e in events)

    def test_merge_brew_logs(self, brew_log, sample_bean):
        other = BrewLog()
        other.log_brew(sample_bean.id, amount_ml=100.0)
        merged = merge_brew_logs(brew_log, other)
        assert merged.count() > brew_log.count()


class TestBrewAnalytics:
    def test_report(self, brew_log):
        analytics = BrewAnalytics(brew_log)
        report = analytics.report()
        assert report["total_events"] == 3
        assert "busiest_day" in report

    def test_total_volume_ml(self, brew_log):
        analytics = BrewAnalytics(brew_log)
        assert analytics.total_volume_ml() > 0

    def test_skip_rate(self, brew_log):
        analytics = BrewAnalytics(brew_log)
        assert analytics.skip_rate() == 0.0

    def test_method_breakdown(self, brew_log):
        analytics = BrewAnalytics(brew_log)
        breakdown = analytics.method_breakdown()
        assert "top_brew" in breakdown

    def test_avg_amount_by_bean(self, brew_log, sample_bean):
        analytics = BrewAnalytics(brew_log)
        avgs = analytics.avg_amount_by_bean()
        assert sample_bean.id in avgs

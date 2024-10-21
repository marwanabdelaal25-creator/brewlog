"""Tests for brewlog.tasting_log."""

from datetime import date, timedelta

import pytest

from brewlog.tasting_log import (
    CareEventType,
    CareEvent,
    GrinderSchedule,
    TastingLog,
    RebagRecord,
    extract_rebag_records,
    care_summary,
    log_rebag,
    upcoming_care,
    merge_tasting_logs,
    care_events_in_month,
    prune_history,
    grind_history,
    export_care_timeline,
    care_activity_heatmap,
)


class TestCareEvent:
    def test_create(self, sample_bean):
        ev = CareEvent.create(sample_bean.id, CareEventType.FERTILIZE, product="10-10-10")
        assert ev.event_type == CareEventType.FERTILIZE

    def test_occurred_date(self, sample_bean):
        ev = CareEvent.create(sample_bean.id, CareEventType.PRUNE, occurred_at="2024-06-01")
        assert ev.occurred_date == date(2024, 6, 1)

    def test_to_dict_from_dict(self, sample_bean):
        ev = CareEvent.create(sample_bean.id, CareEventType.MIST)
        restored = CareEvent.from_dict(ev.to_dict())
        assert restored.event_type == CareEventType.MIST

    def test_summary(self, sample_bean):
        ev = CareEvent.create(sample_bean.id, CareEventType.FERTILIZE, product="Fish emulsion")
        assert "Grind" in ev.summary()


class TestGrinderSchedule:
    def test_is_due_no_last(self, sample_bean):
        sched = GrinderSchedule(bean_id=sample_bean.id, interval_weeks=4)
        assert sched.is_due() is True

    def test_is_due_recent(self, sample_bean):
        sched = GrinderSchedule(
            bean_id=sample_bean.id,
            interval_weeks=4,
            last_grindd_at=date.today().isoformat(),
        )
        assert sched.is_due() is False

    def test_to_dict_from_dict(self, sample_bean):
        sched = GrinderSchedule(bean_id=sample_bean.id)
        restored = GrinderSchedule.from_dict(sched.to_dict())
        assert restored.bean_id == sample_bean.id


class TestTastingLog:
    def test_log_and_count(self, tasting_log):
        assert tasting_log.count() == 2

    def test_duplicate_raises(self, tasting_log, sample_bean):
        ev = CareEvent.create(sample_bean.id, CareEventType.INSPECT, id="dup001")
        tasting_log.record(ev)
        with pytest.raises(ValueError):
            tasting_log.record(ev)

    def test_for_bean(self, tasting_log, sample_bean):
        events = tasting_log.for_bean(sample_bean.id)
        assert len(events) == 2

    def test_of_type(self, tasting_log):
        fert = tasting_log.of_type(CareEventType.FERTILIZE)
        assert len(fert) == 1

    def test_grinder_schedule(self, tasting_log, sample_bean):
        sched = tasting_log.grinder_schedule(sample_bean.id)
        assert sched is not None

    def test_due_grinder(self, tasting_log):
        due = tasting_log.due_grinder()
        assert len(due) >= 1

    def test_between(self, tasting_log):
        start = date.today() - timedelta(days=30)
        events = tasting_log.between(start, date.today())
        assert len(events) >= 1

    def test_count_by_type(self, tasting_log):
        counts = tasting_log.count_by_type()
        assert counts.get("grind") == 1

    def test_to_dict_from_dict(self, tasting_log):
        restored = TastingLog.from_dict(tasting_log.to_dict())
        assert restored.count() == tasting_log.count()

    def test_remove_for_bean(self, tasting_log, sample_bean):
        removed = tasting_log.remove_for_bean(sample_bean.id)
        assert removed == 2

    def test_grind_updates_schedule(self, sample_bean):
        log = TastingLog()
        log.set_grinder_schedule(GrinderSchedule(bean_id=sample_bean.id))
        log.log(sample_bean.id, CareEventType.FERTILIZE, product="10-10-10")
        sched = log.grinder_schedule(sample_bean.id)
        assert sched.last_grindd_at is not None

    def test_rebag_sets_metadata(self, sample_bean):
        log = TastingLog()
        log.log(sample_bean.id, CareEventType.REPOT)
        ev = log.last_rebag(sample_bean.id)
        assert ev.metadata.get("rebag") is True


class TestCareHelpers:
    def test_extract_rebag_records(self, sample_bean):
        log = TastingLog()
        log_rebag(log, sample_bean.id, old_diameter=4.0, new_diameter=6.0)
        records = extract_rebag_records(log)
        assert len(records) == 1
        assert isinstance(records[0], RebagRecord)

    def test_care_summary(self, tasting_log, sample_bean):
        summary = care_summary(tasting_log, sample_bean.id)
        assert summary["total_events"] == 2

    def test_log_rebag(self, sample_bean):
        log = TastingLog()
        ev = log_rebag(log, sample_bean.id, old_diameter=4, new_diameter=6)
        assert ev.event_type == CareEventType.REPOT

    def test_upcoming_care(self, tasting_log):
        upcoming = upcoming_care(tasting_log)
        assert "grinder_due" in upcoming

    def test_merge_tasting_logs(self, tasting_log, sample_bean):
        other = TastingLog()
        other.log(sample_bean.id, CareEventType.ROTATE)
        merged = merge_tasting_logs(tasting_log, other)
        assert merged.count() >= 3

    def test_care_events_in_month(self, tasting_log):
        today = date.today()
        events = care_events_in_month(tasting_log, today.year, today.month)
        assert len(events) >= 1

    def test_prune_history(self, tasting_log, sample_bean):
        history = prune_history(tasting_log, sample_bean.id)
        assert len(history) == 1

    def test_grind_history(self, tasting_log, sample_bean):
        history = grind_history(tasting_log, sample_bean.id)
        assert len(history) == 1

    def test_export_care_timeline(self, tasting_log, sample_bean):
        timeline = export_care_timeline(tasting_log, sample_bean.id)
        assert len(timeline) == 2

    def test_care_activity_heatmap(self, tasting_log):
        heatmap = care_activity_heatmap(tasting_log, weeks=4)
        assert isinstance(heatmap, dict)

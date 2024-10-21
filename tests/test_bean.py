"""Tests for brewlog.bean."""

from datetime import date, timedelta

import pytest

from brewlog.errors import NotFoundError
from brewlog.bean import (
    HealthStatus,
    PotInfo,
    Bean,
    BeanCatalog,
    bean_health_report,
    apply_origin_defaults,
    sort_by_brew_priority,
    clone_bean,
    bulk_update_interval,
    catalog_to_summary_lines,
    find_duplicates_by_name,
    parse_iso,
)
from brewlog.origin import OriginProfile


class TestHealthStatus:
    def test_emoji(self):
        assert HealthStatus.THRIVING.emoji == "🌿"

    def test_score_hint(self):
        assert HealthStatus.CRITICAL.score_hint() == 15


class TestPotInfo:
    def test_to_dict_roundtrip(self):
        bag = PotInfo(diameter=6.0, unit="in", material="ceramic")
        restored = PotInfo.from_dict(bag.to_dict())
        assert restored.diameter == 6.0

    def test_label(self):
        bag = PotInfo(diameter=6.0, unit="in", material="ceramic")
        assert "6.0in" in bag.label()

    def test_label_no_drainage(self):
        bag = PotInfo(diameter=6.0, has_drainage=False)
        assert "no drainage" in bag.label()


class TestBean:
    def test_create(self, sample_bean):
        assert sample_bean.name == "Monstera"
        assert sample_bean.id == "bean001"

    def test_display_name_with_nickname(self, sample_bean):
        assert "Monty" in sample_bean.display_name

    def test_set_health(self, sample_bean):
        sample_bean.set_health(HealthStatus.THRIVING, 90)
        assert sample_bean.health == HealthStatus.THRIVING
        assert sample_bean.health_score == 90

    def test_record_brew(self, sample_bean):
        when = date.today()
        sample_bean.record_brew(when)
        assert sample_bean.last_brewed_at == when.isoformat()

    def test_days_since_brewed(self, sample_bean):
        assert sample_bean.days_since_brewed() == 3

    def test_is_overdue(self, sample_bean):
        sample_bean.last_brewed_at = (date.today() - timedelta(days=20)).isoformat()
        assert sample_bean.is_overdue() is True

    def test_overdue_by_days(self, sample_bean):
        sample_bean.last_brewed_at = (date.today() - timedelta(days=20)).isoformat()
        assert sample_bean.overdue_by_days() == 13

    def test_attach_detach_tag(self, sample_bean):
        sample_bean.attach_tag("tag001")
        assert "tag001" in sample_bean.tag_ids
        assert sample_bean.detach_tag("tag001") is True

    def test_detach_missing_tag(self, sample_bean):
        assert sample_bean.detach_tag("missing") is False

    def test_archive_unarchive(self, sample_bean):
        sample_bean.archive()
        assert sample_bean.archived is True
        sample_bean.unarchive()
        assert sample_bean.archived is False

    def test_to_dict_from_dict(self, sample_bean):
        restored = Bean.from_dict(sample_bean.to_dict())
        assert restored.name == sample_bean.name

    def test_summary_line(self, sample_bean):
        line = sample_bean.summary_line()
        assert "Monstera" in line or "Monty" in line


class TestBeanCatalog:
    def test_add_and_get(self, bean_catalog, sample_bean):
        assert bean_catalog.get(sample_bean.id) is not None

    def test_duplicate_id_raises(self, sample_bean):
        cat = BeanCatalog()
        cat.add(sample_bean)
        with pytest.raises(ValueError):
            cat.add(sample_bean)

    def test_require_raises(self):
        cat = BeanCatalog()
        with pytest.raises(NotFoundError):
            cat.require("missing")

    def test_all_excludes_archived(self, bean_catalog, sample_bean):
        sample_bean.archive()
        assert sample_bean not in bean_catalog.all()

    def test_find_by_name(self, bean_catalog, sample_bean):
        assert sample_bean in bean_catalog.find_by_name("Monstera")

    def test_find_by_station(self, bean_catalog, sample_bean, sample_station):
        found = bean_catalog.find_by_station(sample_station.id)
        assert len(found) >= 1

    def test_find_by_origin(self, bean_catalog, sample_bean):
        found = bean_catalog.find_by_origin("baghos-golden")
        assert sample_bean in found

    def test_find_overdue(self, bean_catalog, sample_bean):
        sample_bean.last_brewed_at = (date.today() - timedelta(days=30)).isoformat()
        assert sample_bean in bean_catalog.find_overdue()

    def test_find_by_tag(self, bean_catalog, sample_bean):
        sample_bean.attach_tag("tag001")
        assert sample_bean in bean_catalog.find_by_tag("tag001")

    def test_remove(self, bean_catalog, sample_bean):
        assert bean_catalog.remove(sample_bean.id) is True
        assert bean_catalog.get(sample_bean.id) is None

    def test_count_by_health(self, bean_catalog):
        counts = bean_catalog.count_by_health()
        assert isinstance(counts, dict)

    def test_merge(self, bean_catalog, sample_bean2):
        other = BeanCatalog()
        other.add(sample_bean2)
        merged = bean_catalog.merge(other)
        assert merged.count() == 2


class TestBeanHelpers:
    def test_bean_health_report(self, bean_catalog):
        report = bean_health_report(bean_catalog)
        assert "total" in report
        assert "overdue_count" in report

    def test_apply_origin_defaults(self, sample_bean, sample_origin):
        sample_bean.brew_interval_days = 7
        apply_origin_defaults(sample_bean, sample_origin)
        assert sample_bean.origin_key == sample_origin.key

    def test_sort_by_brew_priority(self, sample_bean, sample_bean2):
        sample_bean.last_brewed_at = (date.today() - timedelta(days=30)).isoformat()
        sorted_beans = sort_by_brew_priority([sample_bean2, sample_bean])
        assert sorted_beans[0].id == sample_bean.id

    def test_clone_bean(self, sample_bean):
        clone = clone_bean(sample_bean, "Monstera Jr")
        assert clone.id != sample_bean.id
        assert clone.name == "Monstera Jr"
        assert clone.metadata.get("propagated_from") == sample_bean.id

    def test_bulk_update_interval(self, bean_catalog, sample_bean):
        updated = bulk_update_interval(bean_catalog, [sample_bean.id], 10)
        assert updated == 1
        assert bean_catalog.get(sample_bean.id).brew_interval_days == 10

    def test_catalog_to_summary_lines(self, bean_catalog):
        lines = catalog_to_summary_lines(bean_catalog)
        assert len(lines) >= 1

    def test_find_duplicates_by_name(self, sample_bean):
        cat = BeanCatalog()
        cat.add(sample_bean)
        dup = Bean.create("Monstera", id="dup001")
        cat.add(dup)
        dupes = find_duplicates_by_name(cat)
        assert "monstera" in dupes

    def test_parse_iso(self):
        assert parse_iso("2024-06-01T12:00:00") is not None

    def test_parse_iso_none(self):
        assert parse_iso(None) is None

    def test_record_brew_bumps_struggling_health(self):
        bean = Bean.create("Fern", health=HealthStatus.STRUGGLING, health_score=40)
        bean.record_brew()
        assert bean.health_score >= 40

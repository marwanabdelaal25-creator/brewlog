"""Tests for brewlog.ambient."""

import pytest

from brewlog.errors import NotFoundError, ValidationError
from brewlog.ambient import AmbientLogger, VALID_LEVELS


class TestAmbientLogger:
    def test_log_with_bean(self, populated_storage, sample_bean):
        logger = AmbientLogger(populated_storage)
        row = logger.log(bean_id=sample_bean.id, level="bright", hours=6.0)
        assert row["bean_id"] == sample_bean.id

    def test_log_with_station(self, populated_storage, sample_station):
        logger = AmbientLogger(populated_storage)
        row = logger.log(station_id=sample_station.id, level="medium")
        assert row["station_id"] == sample_station.id

    def test_neither_id_raises(self, populated_storage):
        logger = AmbientLogger(populated_storage)
        with pytest.raises(ValidationError):
            logger.log(level="medium")

    def test_invalid_level_raises(self, populated_storage, sample_bean):
        logger = AmbientLogger(populated_storage)
        with pytest.raises(ValidationError):
            logger.log(bean_id=sample_bean.id, level="supernova")

    def test_level_normalized(self, populated_storage, sample_bean):
        logger = AmbientLogger(populated_storage)
        row = logger.log(bean_id=sample_bean.id, level="MEDIUM")
        assert row["level"] == "medium"

    def test_unknown_bean_raises(self, empty_storage):
        logger = AmbientLogger(empty_storage)
        with pytest.raises(NotFoundError):
            logger.log(bean_id="missing", level="low")

    def test_for_bean(self, populated_storage, sample_bean):
        logger = AmbientLogger(populated_storage)
        logger.log(bean_id=sample_bean.id, level="low")
        logger.log(bean_id=sample_bean.id, level="medium")
        rows = logger.for_bean(sample_bean.id)
        assert len(rows) == 2

    def test_for_station(self, populated_storage, sample_station):
        logger = AmbientLogger(populated_storage)
        logger.log(station_id=sample_station.id, level="bright")
        rows = logger.for_station(sample_station.id)
        assert len(rows) == 1

    def test_latest_for_bean(self, populated_storage, sample_bean):
        logger = AmbientLogger(populated_storage)
        assert logger.latest_for_bean(sample_bean.id) is None
        logger.log(bean_id=sample_bean.id, level="low")
        assert logger.latest_for_bean(sample_bean.id) is not None

    def test_delete(self, populated_storage, sample_bean):
        logger = AmbientLogger(populated_storage)
        row = logger.log(bean_id=sample_bean.id, level="low")
        logger.delete(row["id"])
        assert logger.latest_for_bean(sample_bean.id) is None

    def test_delete_missing_raises(self, populated_storage):
        logger = AmbientLogger(populated_storage)
        with pytest.raises(NotFoundError):
            logger.delete("missing")

    @pytest.mark.parametrize("level", list(VALID_LEVELS))
    def test_all_valid_levels(self, populated_storage, sample_bean, level):
        logger = AmbientLogger(populated_storage)
        row = logger.log(bean_id=sample_bean.id, level=level)
        assert row["level"] == level

    def test_hours_optional(self, populated_storage, sample_bean):
        logger = AmbientLogger(populated_storage)
        row = logger.log(bean_id=sample_bean.id, level="medium")
        assert row.get("hours") is None

    def test_notes_persisted(self, populated_storage, sample_bean):
        logger = AmbientLogger(populated_storage)
        row = logger.log(bean_id=sample_bean.id, level="low", notes="Cloudy day")
        assert row["notes"] == "Cloudy day"

    def test_both_ids(self, populated_storage, sample_bean, sample_station):
        logger = AmbientLogger(populated_storage)
        row = logger.log(
            bean_id=sample_bean.id,
            station_id=sample_station.id,
            level="direct",
        )
        assert row["bean_id"] == sample_bean.id

    def test_station_only_excluded_from_for_bean(self, populated_storage, sample_station):
        logger = AmbientLogger(populated_storage)
        logger.log(station_id=sample_station.id, level="medium")
        assert logger.for_bean("any") == []

    def test_observed_at_present(self, populated_storage, sample_bean):
        logger = AmbientLogger(populated_storage)
        row = logger.log(bean_id=sample_bean.id, level="low")
        assert "observed_at" in row

    def test_valid_levels_constant(self):
        assert "medium" in VALID_LEVELS
        assert "direct" in VALID_LEVELS

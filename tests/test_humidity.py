"""Tests for brewlog.humidity."""

import pytest

from brewlog.errors import NotFoundError, ValidationError
from brewlog.humidity import HumidityLogger


class TestHumidityLogger:
    def test_log_reading(self, populated_storage, sample_station):
        logger = HumidityLogger(populated_storage)
        row = logger.log(sample_station.id, 55.0, notes="Morning reading")
        assert row["percent"] == 55.0
        assert row["station_id"] == sample_station.id

    def test_percent_out_of_range_low(self, populated_storage, sample_station):
        logger = HumidityLogger(populated_storage)
        with pytest.raises(ValidationError):
            logger.log(sample_station.id, -1)

    def test_percent_out_of_range_high(self, populated_storage, sample_station):
        logger = HumidityLogger(populated_storage)
        with pytest.raises(ValidationError):
            logger.log(sample_station.id, 101)

    def test_unknown_station(self, empty_storage):
        logger = HumidityLogger(empty_storage)
        with pytest.raises(NotFoundError):
            logger.log("missing", 50.0)

    def test_list_for_station(self, populated_storage, sample_station):
        logger = HumidityLogger(populated_storage)
        logger.log(sample_station.id, 45.0)
        logger.log(sample_station.id, 50.0)
        rows = logger.list_for_station(sample_station.id)
        assert len(rows) == 2
        assert rows[0]["recorded_at"] >= rows[1]["recorded_at"]

    def test_list_with_limit(self, populated_storage, sample_station):
        logger = HumidityLogger(populated_storage)
        for pct in (40, 45, 50):
            logger.log(sample_station.id, pct)
        rows = logger.list_for_station(sample_station.id, limit=2)
        assert len(rows) == 2

    def test_latest(self, populated_storage, sample_station):
        logger = HumidityLogger(populated_storage)
        assert logger.latest(sample_station.id) is None
        logger.log(sample_station.id, 48.0)
        latest = logger.latest(sample_station.id)
        assert latest["percent"] == 48.0

    def test_average(self, populated_storage, sample_station):
        logger = HumidityLogger(populated_storage)
        logger.log(sample_station.id, 40.0)
        logger.log(sample_station.id, 60.0)
        assert logger.average(sample_station.id) == 50.0

    def test_average_no_data(self, populated_storage, sample_station):
        logger = HumidityLogger(populated_storage)
        assert logger.average(sample_station.id) is None

    def test_summary_by_station(self, populated_storage, sample_station):
        logger = HumidityLogger(populated_storage)
        logger.log(sample_station.id, 45.0)
        summary = logger.summary_by_station()
        assert sample_station.id in summary
        assert summary[sample_station.id]["station_name"] == sample_station.name

    def test_delete(self, populated_storage, sample_station):
        logger = HumidityLogger(populated_storage)
        row = logger.log(sample_station.id, 55.0)
        logger.delete(row["id"])
        assert logger.latest(sample_station.id) is None

    def test_delete_missing_raises(self, populated_storage):
        logger = HumidityLogger(populated_storage)
        with pytest.raises(NotFoundError):
            logger.delete("missing")

    def test_source_stored(self, populated_storage, sample_station):
        logger = HumidityLogger(populated_storage)
        row = logger.log(sample_station.id, 50.0, source="sensor")
        assert row["source"] == "sensor"

    def test_persist_survives_reload(self, populated_storage, sample_station, tmp_cellar_path):
        logger = HumidityLogger(populated_storage)
        logger.log(sample_station.id, 42.0)
        reloaded = HumidityLogger(populated_storage.__class__(tmp_cellar_path))
        assert reloaded.latest(sample_station.id) is not None

    def test_bucket_constant(self):
        assert HumidityLogger.BUCKET == "humidity_readings"

    def test_rounded_percent(self, populated_storage, sample_station):
        logger = HumidityLogger(populated_storage)
        row = logger.log(sample_station.id, 55.55)
        assert row["percent"] == 55.5

    def test_multiple_stations_isolated(self, populated_storage, sample_station):
        loc2 = populated_storage.create_station({"id": "loc2", "name": "Kitchen"})
        logger = HumidityLogger(populated_storage)
        logger.log(sample_station.id, 45.0)
        logger.log(loc2.id, 60.0)
        assert len(logger.list_for_station(sample_station.id)) == 1

    def test_summary_null_latest_for_empty(self, populated_storage, sample_station):
        logger = HumidityLogger(populated_storage)
        summary = logger.summary_by_station()
        assert summary[sample_station.id]["latest_percent"] is None

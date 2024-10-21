"""Tests for brewlog.station."""

import pytest

from brewlog.errors import NotFoundError
from brewlog.station import (
    WindowDirection,
    Station,
    StationRegistry,
    StationClimateProfile,
    default_stations,
    compare_light,
    suggest_beans_for_station,
    station_report,
    reassign_bean,
    estimate_daily_light_hours,
    rank_stations_for_origin,
    build_station_map,
    beans_without_station,
    station_capacity_report,
    RoomSnapshot,
    RoomHistory,
    sync_station_bean_ids,
    format_station_tree,
)
from brewlog.origin import OriginCatalog


class TestWindowDirection:
    def test_str(self):
        assert str(WindowDirection.SOUTH) == "south"


class TestStation:
    def test_create(self, sample_station):
        assert sample_station.name == "Living Room"

    def test_add_remove_bean(self, sample_station):
        sample_station.add_bean("bean001")
        assert "bean001" in sample_station.bean_ids
        assert sample_station.remove_bean("bean001") is True

    def test_effective_light_south(self):
        loc = Station.create(
            "Bright Room",
            light_level="medium",
            window_direction=WindowDirection.SOUTH,
        )
        assert compare_light(loc.effective_light(), "medium") >= 0

    def test_label(self, sample_station):
        assert "Living Room" in sample_station.label()

    def test_to_dict_from_dict(self, sample_station):
        restored = Station.from_dict(sample_station.to_dict())
        assert restored.name == sample_station.name

    def test_summary(self, sample_station):
        summary = sample_station.summary()
        assert "Living Room" in summary


class TestStationRegistry:
    def test_add_and_get(self, station_registry, sample_station):
        assert station_registry.get(sample_station.id) is not None

    def test_duplicate_id_raises(self, sample_station):
        reg = StationRegistry()
        reg.add(sample_station)
        with pytest.raises(ValueError):
            reg.add(sample_station)

    def test_get_by_name(self, station_registry, sample_station):
        assert station_registry.get_by_name("Living Room") is not None

    def test_require_raises(self):
        reg = StationRegistry()
        with pytest.raises(NotFoundError):
            reg.require("missing")

    def test_remove(self, station_registry, sample_station):
        assert station_registry.remove(sample_station.id) is True

    def test_assign_unassign_bean(self, station_registry, sample_station):
        station_registry.assign_bean(sample_station.id, "bean001")
        assert "bean001" in station_registry.get(sample_station.id).bean_ids
        station_registry.unassign_bean("bean001")
        assert "bean001" not in station_registry.get(sample_station.id).bean_ids

    def test_find_by_light(self, station_registry):
        found = station_registry.find_by_light("bright_indirect")
        assert len(found) >= 1

    def test_find_by_zone(self, station_registry, sample_station):
        found = station_registry.find_by_zone("main")
        assert sample_station in found

    def test_total_beans_assigned(self, station_registry, sample_station):
        sample_station.add_bean("p1")
        station_registry._stations[sample_station.id] = sample_station
        assert station_registry.total_beans_assigned() >= 1

    def test_stations_needing_humidifier(self, station_registry):
        low = station_registry.stations_needing_humidifier(threshold=50)
        assert isinstance(low, list)

    def test_merge(self, station_registry, sample_station):
        other = StationRegistry()
        other.add(Station.create("Kitchen", id="loc002"))
        merged = station_registry.merge(other)
        assert merged.count() == 2


class TestClimateProfile:
    def test_from_station(self, sample_station):
        profile = StationClimateProfile.from_station(sample_station)
        assert profile.station_id == sample_station.id

    def test_brew_factor_high_humidity(self):
        profile = StationClimateProfile(
            station_id="loc1",
            avg_humidity=70.0,
        )
        assert profile.brew_factor() > 1.0

    def test_brew_factor_draft(self, sample_station):
        sample_station.notes = "drafty window"
        profile = StationClimateProfile.from_station(sample_station)
        assert profile.draft_risk is True


class TestStationHelpers:
    def test_default_stations(self):
        reg = default_stations()
        assert reg.count() >= 4

    def test_compare_light(self):
        assert compare_light("low", "full_sun") == -1
        assert compare_light("full_sun", "low") == 1
        assert compare_light("medium", "medium") == 0

    def test_suggest_beans_for_station(self, sample_station):
        keys = suggest_beans_for_station(sample_station)
        assert isinstance(keys, list)

    def test_station_report(self, station_registry):
        report = station_report(station_registry)
        assert "station_count" in report

    def test_reassign_bean(self, station_registry, sample_station):
        kitchen = Station.create("Kitchen", id="loc_k")
        station_registry.add(kitchen)
        reassign_bean(station_registry, "bean001", sample_station.id, kitchen.id)
        assert "bean001" in kitchen.bean_ids

    def test_estimate_daily_light_hours(self, sample_station):
        hours = estimate_daily_light_hours(sample_station, month=7)
        assert hours > 0

    def test_rank_stations_for_origin(self, station_registry, sample_origin):
        ranked = rank_stations_for_origin(station_registry, sample_origin)
        assert len(ranked) >= 1

    def test_build_station_map(self, station_registry):
        mapping = build_station_map(station_registry)
        assert "living room" in mapping

    def test_beans_without_station(self, station_registry):
        missing = beans_without_station(station_registry, ["bean001", "bean999"])
        assert "bean999" in missing

    def test_station_capacity_report(self, station_registry, sample_station):
        sample_station.bean_ids = ["p1", "p2"]
        report = station_capacity_report(station_registry, max_per_room=1)
        assert len(report["crowded"]) >= 1

    def test_room_history(self):
        hist = RoomHistory()
        snap = RoomSnapshot(station_id="loc1", recorded_at="2024-06-01", humidity_pct=50)
        hist.record(snap)
        assert len(hist.for_station("loc1")) == 1
        assert hist.avg_humidity("loc1") == 50.0

    def test_sync_station_bean_ids(self, station_registry, sample_bean):
        sync_station_bean_ids(station_registry, [sample_bean])
        loc = station_registry.get(sample_bean.station_id)
        assert sample_bean.id in loc.bean_ids

    def test_format_station_tree(self, station_registry):
        text = format_station_tree(station_registry)
        assert "Living Room" in text

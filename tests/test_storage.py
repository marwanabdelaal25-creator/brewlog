"""Tests for brewlog.storage."""

import json

import pytest

from brewlog.errors import NotFoundError, StorageError, ValidationError
from brewlog.station import Station
from brewlog.bean import Bean, HealthStatus
from brewlog.origin import OriginProfile
from brewlog.storage import JsonStorage, DEFAULT_CELLAR, SCHEMA_VERSION


class TestJsonStorageInit:
    def test_creates_empty_cellar(self, tmp_cellar_path):
        storage = JsonStorage(tmp_cellar_path)
        assert tmp_cellar_path.exists()

    def test_loads_existing(self, populated_storage, tmp_cellar_path):
        storage2 = JsonStorage(tmp_cellar_path)
        assert len(storage2.list_beans()) >= 2


class TestBeans:
    def test_create_and_list(self, empty_storage, sample_bean):
        created = empty_storage.create_bean(sample_bean)
        assert created.name == sample_bean.name

    def test_get_bean(self, populated_storage, sample_bean):
        bean = populated_storage.get_bean(sample_bean.id)
        assert bean.id == sample_bean.id

    def test_get_bean_not_found(self, empty_storage):
        with pytest.raises(NotFoundError):
            empty_storage.get_bean("missing")

    def test_update_bean(self, populated_storage, sample_bean):
        updated = populated_storage.update_bean(sample_bean.id, {"nickname": "NewNick"})
        assert updated.nickname == "NewNick"

    def test_delete_bean(self, populated_storage, sample_bean):
        populated_storage.delete_bean(sample_bean.id)
        with pytest.raises(NotFoundError):
            populated_storage.get_bean(sample_bean.id)

    def test_list_beans_active_only(self, populated_storage, sample_bean):
        populated_storage.update_bean(sample_bean.id, {"archived": True})
        active = populated_storage.list_beans(active_only=True)
        assert all(not p.archived for p in active)

    def test_duplicate_bean_raises(self, populated_storage, sample_bean):
        with pytest.raises(ValidationError):
            populated_storage.create_bean(sample_bean.to_dict())


class TestOrigin:
    def test_create_origin(self, empty_storage, sample_origin):
        created = empty_storage.create_origin(sample_origin)
        assert created.key == sample_origin.key

    def test_get_origin(self, populated_storage, sample_origin):
        sp = populated_storage.get_origin(sample_origin.key)
        assert sp.common_name == sample_origin.common_name

    def test_delete_origin(self, populated_storage, sample_origin):
        populated_storage.delete_origin(sample_origin.key)
        with pytest.raises(NotFoundError):
            populated_storage.get_origin(sample_origin.key)


class TestStations:
    def test_create_station(self, empty_storage, sample_station):
        created = empty_storage.create_station(sample_station)
        assert created.name == sample_station.name

    def test_get_station(self, populated_storage, sample_station):
        loc = populated_storage.get_station(sample_station.id)
        assert loc.id == sample_station.id

    def test_update_station(self, populated_storage, sample_station):
        updated = populated_storage.update_station(sample_station.id, {"notes": "Updated"})
        assert updated.notes == "Updated"


class TestBrew:
    def test_create_brew_event(self, populated_storage, sample_bean):
        event = populated_storage.create_brew_event({
            "id": "we_new",
            "bean_id": sample_bean.id,
            "amount_ml": 300,
        })
        assert event["bean_id"] == sample_bean.id

    def test_list_brew_events_filtered(self, populated_storage, sample_bean):
        events = populated_storage.list_brew_events(bean_id=sample_bean.id)
        assert len(events) >= 1

    def test_delete_brew_event(self, populated_storage):
        events = populated_storage.list_brew_events()
        eid = events[0]["id"]
        populated_storage.delete_brew_event(eid)
        with pytest.raises(NotFoundError):
            populated_storage.get_brew_event(eid)


class TestTagsAndNotes:
    def test_create_tag(self, empty_storage):
        tag = empty_storage.create_tag({"id": "tag_new", "name": "test"})
        assert tag["name"] == "test"

    def test_create_note(self, populated_storage, sample_bean):
        note = populated_storage.create_note({
            "id": "note_new",
            "bean_id": sample_bean.id,
            "body": "Test note",
        })
        assert note["body"] == "Test note"

    def test_list_notes_filtered(self, populated_storage, sample_bean):
        notes = populated_storage.list_notes(bean_id=sample_bean.id)
        assert len(notes) >= 1


class TestAuditAndPlugins:
    def test_append_audit(self, empty_storage):
        entry = empty_storage.append_audit({"action": "create", "entity": "bean"})
        assert "timestamp" in entry

    def test_upsert_plugin(self, empty_storage):
        plugin = empty_storage.upsert_plugin({"id": "p1", "name": "Test Plugin"})
        assert plugin["name"] == "Test Plugin"
        updated = empty_storage.upsert_plugin({"id": "p1", "name": "Updated"})
        assert updated["name"] == "Updated"


class TestRecurringAndCollections:
    def test_create_recurring(self, empty_storage):
        task = empty_storage.create_recurring({"id": "r1", "title": "Weekly mist"})
        assert task["title"] == "Weekly mist"

    def test_create_collection(self, empty_storage):
        coll = empty_storage.create_collection({"id": "c1", "name": "Favorites"})
        assert coll["name"] == "Favorites"


class TestStorageCore:
    def test_snapshot(self, populated_storage):
        snap = populated_storage.snapshot()
        assert "beans" in snap

    def test_replace_all(self, empty_storage, sample_bean):
        empty_storage.replace_all({
            **DEFAULT_CELLAR,
            "beans": [sample_bean.to_dict()],
        })
        assert len(empty_storage.list_beans()) == 1

    def test_mutate(self, empty_storage):
        def add_tag(data):
            data["tags"].append({"id": "t1", "name": "test"})
        empty_storage.mutate(add_tag)
        assert len(empty_storage.list_tags()) == 1

    def test_load_corrupt_json(self, tmp_cellar_path):
        tmp_cellar_path.write_text("{not json", encoding="utf-8")
        with pytest.raises(StorageError):
            JsonStorage(tmp_cellar_path)

    def test_schema_version_in_default(self):
        assert DEFAULT_CELLAR["schema_version"] == SCHEMA_VERSION

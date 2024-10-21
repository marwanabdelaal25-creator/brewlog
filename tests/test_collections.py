"""Tests for brewlog.collections."""

import pytest

from brewlog.errors import NotFoundError, ValidationError
from brewlog.collections import CollectionManager


class TestCollectionManager:
    def test_create(self, populated_storage, sample_bean):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Kitchen Herbs", bean_ids=[sample_bean.id])
        assert coll["name"] == "Kitchen Herbs"
        assert sample_bean.id in coll["bean_ids"]

    def test_create_empty_name_raises(self, empty_storage):
        mgr = CollectionManager(empty_storage)
        with pytest.raises(ValidationError):
            mgr.create("  ")

    def test_create_invalid_bean_raises(self, empty_storage):
        mgr = CollectionManager(empty_storage)
        with pytest.raises(NotFoundError):
            mgr.create("Bad", bean_ids=["missing"])

    def test_list_all(self, populated_storage, sample_bean):
        mgr = CollectionManager(populated_storage)
        mgr.create("Group A", bean_ids=[sample_bean.id])
        assert len(mgr.list_all()) == 1

    def test_get(self, populated_storage, sample_bean):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Favorites")
        found = mgr.get(coll["id"])
        assert found["name"] == "Favorites"

    def test_get_not_found(self, empty_storage):
        mgr = CollectionManager(empty_storage)
        with pytest.raises(NotFoundError):
            mgr.get("missing")

    def test_add_bean(self, populated_storage, sample_bean, sample_bean2):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group")
        updated = mgr.add_bean(coll["id"], sample_bean.id)
        updated = mgr.add_bean(coll["id"], sample_bean2.id)
        assert len(updated["bean_ids"]) == 2

    def test_add_bean_dedupes(self, populated_storage, sample_bean):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group", bean_ids=[sample_bean.id])
        updated = mgr.add_bean(coll["id"], sample_bean.id)
        assert updated["bean_ids"].count(sample_bean.id) == 1

    def test_remove_bean(self, populated_storage, sample_bean):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group", bean_ids=[sample_bean.id])
        updated = mgr.remove_bean(coll["id"], sample_bean.id)
        assert sample_bean.id not in updated["bean_ids"]

    def test_rename(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Old Name")
        updated = mgr.rename(coll["id"], "New Name")
        assert updated["name"] == "New Name"

    def test_rename_blank_raises(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Name")
        with pytest.raises(ValidationError):
            mgr.rename(coll["id"], "  ")

    def test_delete(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Temp")
        mgr.delete(coll["id"])
        assert mgr.list_all() == []

    def test_beans_in(self, populated_storage, sample_bean):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group", bean_ids=[sample_bean.id])
        beans = mgr.beans_in(coll["id"])
        assert len(beans) == 1

    def test_beans_in_skips_stale(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group")
        populated_storage.update_collection(coll["id"], {"bean_ids": ["stale_id"]})
        assert mgr.beans_in(coll["id"]) == []

    def test_collections_for_bean(self, populated_storage, sample_bean):
        mgr = CollectionManager(populated_storage)
        mgr.create("A", bean_ids=[sample_bean.id])
        mgr.create("B", bean_ids=[sample_bean.id])
        cols = mgr.collections_for_bean(sample_bean.id)
        assert len(cols) == 2

    def test_merge(self, populated_storage, sample_bean, sample_bean2):
        mgr = CollectionManager(populated_storage)
        t = mgr.create("Target", bean_ids=[sample_bean.id])
        s = mgr.create("Source", bean_ids=[sample_bean2.id])
        merged = mgr.merge(t["id"], s["id"])
        assert sample_bean2.id in merged["bean_ids"]
        assert len(mgr.list_all()) == 1

    def test_merge_dedupes_overlap(self, populated_storage, sample_bean):
        mgr = CollectionManager(populated_storage)
        t = mgr.create("Target", bean_ids=[sample_bean.id])
        s = mgr.create("Source", bean_ids=[sample_bean.id])
        merged = mgr.merge(t["id"], s["id"])
        assert merged["bean_ids"].count(sample_bean.id) == 1

    def test_description_stored(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Herbs", description="Kitchen window")
        assert coll["description"] == "Kitchen window"

    def test_add_unknown_bean_raises(self, populated_storage):
        mgr = CollectionManager(populated_storage)
        coll = mgr.create("Group")
        with pytest.raises(NotFoundError):
            mgr.add_bean(coll["id"], "missing")

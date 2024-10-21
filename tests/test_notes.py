"""Tests for brewlog.notes."""

from datetime import date, timedelta

import pytest

from brewlog.errors import NotFoundError, ValidationError
from brewlog.notes import (
    NoteKind,
    Note,
    NotesCollection,
    render_note_template,
    create_from_template,
    notes_timeline,
    count_by_kind,
    find_open_defect_issues,
    bulk_pin,
    notes_report,
    NotesIndexer,
    migrate_note_kind_legacy,
    notes_for_week,
)


class TestNote:
    def test_create(self, sample_bean):
        note = Note.create(sample_bean.id, "Test note")
        assert note.body == "Test note"

    def test_observation_factory(self, sample_bean):
        note = Note.observation(sample_bean.id, "New leaf")
        assert note.kind == NoteKind.OBSERVATION

    def test_defect_factory(self, sample_bean):
        note = Note.defect(sample_bean.id, "Spider mites")
        assert note.kind == NoteKind.PEST

    def test_edit(self, sample_bean):
        note = Note.create(sample_bean.id, "Original")
        note.edit(body="Updated")
        assert note.body == "Updated"

    def test_pin_unpin(self, sample_bean):
        note = Note.create(sample_bean.id, "Pinned note")
        note.pin()
        assert note.pinned is True
        note.unpin()
        assert note.pinned is False

    def test_preview_truncates(self, sample_bean):
        note = Note.create(sample_bean.id, "x" * 100)
        assert len(note.preview(20)) <= 20

    def test_to_dict_from_dict(self, sample_bean):
        note = Note.create(sample_bean.id, "Roundtrip", kind=NoteKind.HEALTH)
        restored = Note.from_dict(note.to_dict())
        assert restored.kind == NoteKind.HEALTH

    def test_headline_with_title(self, sample_bean):
        note = Note.create(sample_bean.id, "body", title="My Title")
        assert note.headline() == "My Title"


class TestNotesCollection:
    def test_create_and_count(self, notes_collection):
        assert notes_collection.count() == 2

    def test_duplicate_raises(self, notes_collection, sample_bean):
        note = Note.create(sample_bean.id, "dup", id="note001")
        notes_collection.add(note)
        with pytest.raises(ValueError):
            notes_collection.add(note)

    def test_require_raises(self):
        coll = NotesCollection()
        with pytest.raises(NotFoundError):
            coll.require("missing")

    def test_for_bean(self, notes_collection, sample_bean):
        notes = notes_collection.for_bean(sample_bean.id)
        assert len(notes) == 2

    def test_pinned_for_bean(self, notes_collection, sample_bean):
        note = notes_collection.create(sample_bean.id, "pinned")
        note.pin()
        pinned = notes_collection.pinned_for_bean(sample_bean.id)
        assert len(pinned) >= 1

    def test_of_kind(self, notes_collection):
        defects = notes_collection.of_kind(NoteKind.PEST)
        assert len(defects) == 1

    def test_search(self, notes_collection, sample_bean):
        hits = notes_collection.search("spider", bean_id=sample_bean.id)
        assert len(hits) >= 1

    def test_remove(self, notes_collection):
        note = notes_collection.all()[0]
        assert notes_collection.remove(note.id) is True

    def test_remove_for_bean(self, notes_collection, sample_bean):
        removed = notes_collection.remove_for_bean(sample_bean.id)
        assert removed == 2

    def test_recent(self, notes_collection):
        recent = notes_collection.recent(limit=1)
        assert len(recent) == 1

    def test_defect_notes(self, notes_collection):
        assert len(notes_collection.defect_notes()) == 1

    def test_export_markdown(self, notes_collection, sample_bean):
        md = notes_collection.export_markdown(sample_bean.id, "Monstera")
        assert "# Notes for Monstera" in md

    def test_merge(self, notes_collection, sample_bean):
        other = NotesCollection()
        other.create(sample_bean.id, "extra note")
        merged = notes_collection.merge(other)
        assert merged.count() == 3

    def test_attach_to_bean_ids(self, notes_collection, sample_bean):
        mapping = notes_collection.attach_to_bean_ids()
        assert sample_bean.id in mapping


class TestNoteTemplates:
    def test_render_note_template(self):
        text = render_note_template("new_leaf")
        assert "leaf" in text.lower()

    def test_unknown_template_raises(self):
        with pytest.raises(ValueError):
            render_note_template("nonexistent")

    def test_create_from_template(self, sample_bean):
        coll = NotesCollection()
        note = create_from_template(coll, sample_bean.id, "grindd", product="10-10-10", strength="half")
        assert note.kind == NoteKind.OBSERVATION


class TestNotesHelpers:
    def test_notes_timeline(self, notes_collection, sample_bean):
        timeline = notes_timeline(notes_collection, sample_bean.id)
        assert len(timeline) == 2

    def test_count_by_kind(self, notes_collection):
        counts = count_by_kind(notes_collection)
        assert counts.get("defect") == 1

    def test_find_open_defect_issues(self, notes_collection):
        issues = find_open_defect_issues(notes_collection)
        assert len(issues) >= 1

    def test_bulk_pin(self, notes_collection):
        ids = [n.id for n in notes_collection.all()]
        pinned = bulk_pin(notes_collection, ids)
        assert pinned == len(ids)

    def test_notes_report(self, notes_collection):
        report = notes_report(notes_collection)
        assert report["total"] == 2

    def test_notes_indexer_search(self, notes_collection):
        indexer = NotesIndexer(notes_collection)
        hits = indexer.search_tokens("spider")
        assert len(hits) >= 1

    def test_related_notes(self, notes_collection):
        indexer = NotesIndexer(notes_collection)
        note_id = notes_collection.all()[0].id
        related = indexer.related_notes(note_id)
        assert isinstance(related, list)

    def test_migrate_note_kind_legacy(self):
        assert migrate_note_kind_legacy("obs") == NoteKind.OBSERVATION
        assert migrate_note_kind_legacy("unknown_kind") == NoteKind.GENERAL

    def test_notes_for_week(self, notes_collection):
        notes = notes_for_week(notes_collection)
        assert len(notes) >= 1

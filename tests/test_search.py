"""Tests for brewlog.search."""

from brewlog.search import SearchHit, CellarSearch


class TestSearchHit:
    def test_dataclass(self):
        hit = SearchHit(kind="bean", id="p1", title="Fern", snippet="...", score=1.0)
        assert hit.score == 1.0


class TestCellarSearch:
    def test_search_beans_by_name(self, populated_storage, sample_bean):
        search = CellarSearch(populated_storage)
        hits = search.search_beans("Monstera")
        assert len(hits) >= 1
        assert hits[0].kind == "bean"

    def test_search_beans_partial(self, populated_storage):
        search = CellarSearch(populated_storage)
        hits = search.search_beans("Snake")
        assert len(hits) >= 1

    def test_search_beans_empty_query(self, populated_storage):
        search = CellarSearch(populated_storage)
        hits = search.search_beans("")
        assert hits == []

    def test_search_beans_no_match(self, populated_storage):
        search = CellarSearch(populated_storage)
        hits = search.search_beans("zzzznonexistent")
        assert hits == []

    def test_search_beans_by_origin(self, populated_storage):
        search = CellarSearch(populated_storage)
        hits = search.search_beans("baghos-golden")
        assert len(hits) >= 1

    def test_search_notes(self, populated_storage):
        search = CellarSearch(populated_storage)
        hits = search.search_notes("unfurling")
        assert len(hits) >= 1
        assert hits[0].kind == "note"

    def test_search_notes_no_match(self, populated_storage):
        search = CellarSearch(populated_storage)
        assert search.search_notes("xyznotfound") == []

    def test_search_tasting_logs(self, populated_storage):
        populated_storage.create_tasting_log({
            "id": "cl1",
            "bean_id": "bean001",
            "action": "grind",
            "details": "Applied fish emulsion",
        })
        search = CellarSearch(populated_storage)
        hits = search.search_tasting_logs("grind")
        assert len(hits) >= 1

    def test_search_all_combined(self, populated_storage):
        search = CellarSearch(populated_storage)
        hits = search.search_all("Monstera")
        assert len(hits) >= 1

    def test_search_all_with_limit(self, populated_storage):
        search = CellarSearch(populated_storage)
        hits = search.search_all("bean", limit=1)
        assert len(hits) <= 1

    def test_search_all_sorted_by_score(self, populated_storage):
        search = CellarSearch(populated_storage)
        hits = search.search_all("Monstera")
        if len(hits) >= 2:
            assert hits[0].score >= hits[1].score

    def test_to_dicts(self, populated_storage):
        search = CellarSearch(populated_storage)
        hits = search.search_beans("Monstera")
        dicts = search.to_dicts(hits)
        assert dicts[0]["kind"] == "bean"
        assert "score" in dicts[0]

    def test_snippet_truncation(self, populated_storage):
        populated_storage.create_note({
            "id": "long_note",
            "bean_id": "bean001",
            "body": "x" * 200,
            "title": "Long",
        })
        search = CellarSearch(populated_storage)
        hits = search.search_notes("Long")
        if hits:
            assert len(hits[0].snippet) <= 120

    def test_case_insensitive(self, populated_storage):
        search = CellarSearch(populated_storage)
        hits = search.search_beans("monstera")
        assert len(hits) >= 1

    def test_multiple_tokens(self, populated_storage):
        search = CellarSearch(populated_storage)
        hits = search.search_beans("Snake Bean")
        assert len(hits) >= 1

    def test_metadata_searchable(self, populated_storage, sample_bean):
        populated_storage.update_bean(sample_bean.id, {
            "metadata": {"notes": "special keyword xyzzy"},
        })
        search = CellarSearch(populated_storage)
        hits = search.search_beans("xyzzy")
        assert len(hits) >= 1

    def test_tasting_log_missing_id(self, populated_storage):
        populated_storage.create_tasting_log({
            "bean_id": "bean001",
            "action": "inspect",
            "details": "Checked roots",
        })
        search = CellarSearch(populated_storage)
        hits = search.search_tasting_logs("roots")
        assert len(hits) >= 1

    def test_whitespace_tokens_stripped(self, populated_storage):
        search = CellarSearch(populated_storage)
        hits = search.search_beans("  Monstera   ")
        assert len(hits) >= 1

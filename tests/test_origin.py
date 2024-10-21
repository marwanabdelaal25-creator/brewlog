"""Tests for brewlog.origin."""

import pytest

from brewlog.errors import NotFoundError
from brewlog.origin import (
    BrewNeed,
    HumidityNeed,
    OriginProfile,
    OriginCatalog,
    origin_export_row,
    build_origin_index,
)


class TestOriginProfile:
    def test_create(self, sample_origin):
        assert sample_origin.key == "baghos-golden"
        assert sample_origin.common_name == "Golden Pothos"

    def test_brew_interval_days(self, sample_origin):
        assert sample_origin.brew_interval_days == 10

    def test_matches_light(self, sample_origin):
        assert sample_origin.matches_light("medium") is True

    def test_to_dict_from_dict(self, sample_origin):
        restored = OriginProfile.from_dict(sample_origin.to_dict())
        assert restored.key == sample_origin.key

    def test_care_summary(self, sample_origin):
        summary = sample_origin.care_summary()
        assert "Golden Pothos" in summary

    def test_temp_max_less_than_min_raises(self):
        with pytest.raises(ValueError):
            OriginProfile(
                key="bad-origin",
                common_name="Bad",
                temp_min_c=30.0,
                temp_max_c=10.0,
            )


class TestBrewNeed:
    def test_str(self):
        assert str(BrewNeed.LOW) == "low"


class TestOriginCatalog:
    def test_register_and_get(self, origin_catalog, sample_origin):
        assert origin_catalog.get(sample_origin.key) is not None

    def test_require_raises(self):
        cat = OriginCatalog()
        with pytest.raises(NotFoundError):
            cat.require("missing")

    def test_search(self, origin_catalog):
        hits = origin_catalog.search("baghos")
        assert len(hits) >= 1

    def test_search_empty_returns_all(self, origin_catalog):
        assert len(origin_catalog.search("")) >= 1

    def test_load_builtin(self):
        cat = OriginCatalog()
        cat.load_builtin()
        assert cat.count() >= 10

    def test_with_defaults(self):
        cat = OriginCatalog.with_defaults()
        assert cat.get("monstera-deliciosa") is not None

    def test_suggest_interval_winter(self, origin_catalog):
        interval = origin_catalog.suggest_interval_for("snake-bean", season="winter")
        assert interval > origin_catalog.require("snake-bean").brew_interval_days

    def test_suggest_interval_summer(self, origin_catalog):
        interval = origin_catalog.suggest_interval_for("snake-bean", season="summer")
        assert interval <= origin_catalog.require("snake-bean").brew_interval_days

    def test_filter_by_tag(self, origin_catalog):
        beginner = origin_catalog.filter_by_tag("beginner")
        assert len(beginner) >= 1

    def test_filter_pet_safe(self, origin_catalog):
        safe = origin_catalog.filter_pet_safe()
        assert all(not p.toxic_to_pets for p in safe)

    def test_merge(self, origin_catalog, sample_origin):
        other = OriginCatalog()
        other.register(OriginProfile(
            key="custom-fern",
            common_name="Custom Fern",
        ))
        merged = origin_catalog.merge(other)
        assert merged.get("custom-fern") is not None

    def test_keys(self, origin_catalog):
        keys = origin_catalog.keys()
        assert "baghos-golden" in keys

    def test_recommend_for_conditions(self, origin_catalog):
        hits = origin_catalog.recommend_for_conditions("medium", humidity_pct=50)
        assert len(hits) >= 1

    def test_recommend_pet_safe_only(self, origin_catalog):
        hits = origin_catalog.recommend_for_conditions("bright_indirect", pet_safe_only=True)
        assert all(not p.toxic_to_pets for p in hits)

    def test_difficulty_rank_beginner(self, origin_catalog):
        rank = origin_catalog.difficulty_rank("snake-bean")
        assert rank <= 3

    def test_difficulty_rank_fussy(self, origin_catalog):
        rank = origin_catalog.difficulty_rank("fiddle-leaf-fig")
        assert rank >= 3

    def test_difficulty_rank_unknown(self, origin_catalog):
        assert origin_catalog.difficulty_rank("nonexistent") == 3

    def test_from_dict_list(self, sample_origin):
        cat = OriginCatalog.from_dict_list([sample_origin.to_dict()])
        assert cat.get(sample_origin.key) is not None

    def test_to_dict_list(self, origin_catalog):
        rows = origin_catalog.to_dict_list()
        assert len(rows) >= 1


class TestOriginHelpers:
    def test_origin_export_row(self, sample_origin):
        row = origin_export_row(sample_origin)
        assert row[0] == sample_origin.key

    def test_build_origin_index(self, origin_catalog):
        index = build_origin_index(origin_catalog)
        assert "G" in index or "P" in index

import pytest
from edgar_names import load_overrides

from pipeline import config
from pipeline.match import HIGH, MEDIUM, _prep_companies, ladder


@pytest.mark.parametrize("issuer", ["Sunflower Labs Inc.", "Sunflower Inc.", "Sunflower X, Inc."])
def test_single_word_with_same_state_goes_to_review(issuer):
    companies = _prep_companies([{
        "slug": "sunflower", "name": "Sunflower", "tier": "speedrun", "location": "San Francisco, CA",
    }])
    candidate, = ladder({"entity_name": issuer, "state": "CA"}, companies)
    assert candidate.confidence == MEDIUM


def test_full_brand_alias_is_preserved():
    companies = _prep_companies([{
        "slug": "north-star", "name": "North Star", "aliases": ["North Star Labs"],
        "tier": "speedrun", "location": "San Francisco, CA",
    }])
    confirmed, = ladder({"entity_name": "North Star Labs Inc.", "state": "CA"}, companies)
    unconfirmed, = ladder({"entity_name": "North Star Technology Inc.", "state": "CA"}, companies)
    assert confirmed.confidence == HIGH
    assert unconfirmed.confidence == MEDIUM


def test_reviewed_issuer_decisions():
    decisions = load_overrides(config.OVERRIDES_FILE)
    assert decisions.confirmed_slug("0001939243") == "adaptive"
    assert decisions.is_rejected("0001876339", "sunflower")


def test_duplicate_override_sections_raise(tmp_path):
    path = tmp_path / "matches.yaml"
    path.write_text('confirm: [{cik: "1939243", slug: adaptive}]\nconfirm: []\n')
    with pytest.raises(ValueError, match="duplicate YAML key"):
        load_overrides(path)


def test_wear_linq_vehicle_rejection_is_specific_and_applies_to_cached_rows(tmp_path, monkeypatch):
    from datetime import date

    import polars as pl
    from pipeline.fetch_portfolio import canonical_slugs
    from pipeline.score import _spv_groups
    from pipeline.spv import SPV_SCHEMA, update_spvs

    today = date(2026, 11, 19)
    universe = [{"name": "Linq", "slug": "linq", "also": ["a16z:linq"]}]
    aliases = canonical_slugs(universe)
    decisions = load_overrides(config.OVERRIDES_FILE, slug_aliases=aliases)
    assert decisions.is_spv_rejected("0002140814", "linq")
    assert not decisions.is_spv_rejected("2140814", "a16z:other-target")
    assert not decisions.is_spv_rejected("1234567", "linq")

    entries = [
        {"adsh": "one", "cik": "2140814", "spv_name": "Wear Linq AngelSchool vc Jun 2026 a Series of CGF2021 LLC"},
        {"adsh": "two", "cik": "1234567", "spv_name": "Example Investors - Series Linq SPV"},
    ]
    cache = tmp_path / "vehicles.parquet"
    monkeypatch.setattr(config, "SPV_FILINGS", cache)
    cached_rows = [{**entry, "slug": "a16z:linq", "file_date": today} for entry in entries]
    pl.DataFrame(cached_rows, schema=SPV_SCHEMA).write_parquet(cache)

    # A standalone score run can use yesterday's cache of both vehicles.
    assert [row["adsh"] for row in _spv_groups(today, today, aliases)["linq"]] == ["two"]

    index = pl.DataFrame([{**e, "index_name": e["spv_name"], "items": ["3C7"], "file_date": today} for e in entries])
    result = update_spvs(None, index, universe, today)  # both XML records are already cached
    assert result.select("adsh", "slug").rows() == [("two", "linq")]

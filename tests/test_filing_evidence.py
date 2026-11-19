import csv
import io
import json
from datetime import date, timedelta

import polars as pl
import pytest

from pipeline import config
from pipeline import score as scoring
from pipeline.score import _filing_fields, _spv_csv, _spv_row, build_offerings, to_csv


TODAY = date(2026, 11, 19)


def _filing(accession, filed, sold, first_sale, *, cik="1", previous=None):
    return {
        "adsh": accession, "cik": cik, "file_date": filed, "is_amendment": previous is not None,
        "previous_accession": previous, "total_amount_sold": sold, "date_of_first_sale": first_sale,
        "total_offering_amount": 50_000_000, "offering_indefinite": False,
        "spv_name": "Example vehicle", "entity_name": "Example", "city": None, "state": None,
        "industry_group": None,
    }


def _direct_fields(*filings):
    (offering,) = build_offerings(list(filings))
    offering.update(match={"confidence": "High", "rung": "1"}, offerings_in_window=1)
    return _filing_fields(offering, TODAY)


def _spv(*filings):
    company = {"slug": "example", "name": "Example", "tier": "a16z"}
    return _spv_row(company, list(filings), None, False, False, TODAY)


def test_amended_amount_and_first_sale_cite_their_respective_filings():
    sale_date = date(2026, 7, 7)
    original = _filing("01", date(2026, 7, 22), 23_199_945, sale_date)
    amendment = _filing("02", date(2026, 7, 29), 24_999_937, sale_date, previous="01") | {
        "total_offering_amount": 24_999_937,
    }
    result = _direct_fields(amendment, original)
    assert result["amount"] == 24_999_937
    assert result["original_amount_sold"] == 23_199_945
    assert result["original_offering_amount"] == 50_000_000
    assert result["offering_amount"] == 24_999_937
    orphan = _direct_fields(amendment)
    assert orphan["original_amount_sold"] is None and orphan["original_offering_amount"] is None
    assert result["filing_url"] == result["first_sale_filing_url"]
    assert result["filing_url"].endswith("/01-index.htm")
    assert result["amount_filing_url"].endswith("/02-index.htm")
    (export,) = csv.DictReader(io.StringIO(to_csv([result | {"score": 0.0}])))
    assert export["amount_filing_url"] == result["amount_filing_url"]
    assert export["latest_accession"] == "02"
    assert export["original_amount_sold"] == "23199945"


def test_amendment_can_be_first_evidence_of_a_sale():
    original = _filing("01", date(2026, 7, 1), 0, None)
    amendment = _filing("02", date(2026, 7, 12), 100, date(2026, 7, 7), previous="01")
    result = _direct_fields(original, amendment)
    assert result["date_of_first_sale"] == "2026-07-07"
    assert result["first_sale_reported"] is True
    assert result["first_sale_filing_url"] == result["amount_filing_url"]
    unfunded = _direct_fields(original)
    assert unfunded["first_sale_reported"] is False
    assert unfunded["first_sale_filing_url"] is None
    assert _direct_fields(original | {"total_amount_sold": None})["amount_sold"] is None


@pytest.mark.parametrize(("sold", "first_sale", "expected"), [
    (0, None, "no_sales_reported"),
    (None, None, "unknown"),
    (150_000, None, "sale_date_unknown"),
    (150_000, date(2023, 12, 25), "historical_first_sale"),
    (150_000, TODAY - timedelta(days=config.WINDOW_DAYS), "recent_first_sale"),
])
def test_recent_spv_filing_does_not_establish_recent_sales(sold, first_sale, expected):
    result = _spv(_filing("01", TODAY, sold, first_sale))
    (vehicle,) = result["vehicles"]
    assert result["sale_status"] == vehicle["sale_status"] == expected
    assert result["latest_spv_file_date"] == TODAY.isoformat()
    assert result["spv_amount_sold"] == sold
    assert result["latest_first_sale_date"] == (first_sale.isoformat() if first_sale else None)
    assert vehicle["offering_amount"] == 50_000_000
    (export,) = csv.DictReader(io.StringIO(_spv_csv([result])))
    assert json.loads(export["vehicle_evidence"]) == [vehicle]


def test_spv_amendment_updates_amount_without_resetting_first_filing():
    first = date(2026, 7, 1)
    latest = date(2026, 7, 20)
    original = _filing("01", first, 10, first)
    amendment = _filing("02", latest, 40, first, previous="01")
    result = _spv(amendment, original)
    assert result["spvs"] == 1
    assert result["spv_amount_sold"] == 40
    assert result["first_spv_file_date"] == first.isoformat()
    assert result["latest_spv_file_date"] == latest.isoformat()
    assert result["vehicles"][0]["filing_url"].endswith("/02-index.htm")
    assert result["vehicles"][0]["is_amendment"] is True


def test_missing_vehicle_amount_prevents_complete_spv_total():
    known = _filing("01", TODAY, 40, TODAY)
    missing = _filing("02", TODAY, None, None, cik="2")
    result = _spv(known, missing)
    assert result["sale_status"] == "recent_first_sale"
    assert result["spv_amount_sold"] is None
    assert result["latest_first_sale_date"] == TODAY.isoformat()


def test_only_dated_sales_enter_collection_and_outlast_newer_notices(tmp_path, monkeypatch):
    for key in ("MATCHES", "FILINGS", "REGISTRY_JSON", "SPV_FILINGS", "HISTORY",
                "PUBLIC_COLLECTION", "PUBLIC_FILINGS", "PUBLIC_CSV", "PUBLIC_SPV_CSV"):
        monkeypatch.setattr(config, key, tmp_path / getattr(config, key).name)
    monkeypatch.setattr(config, "DATA", tmp_path)
    monkeypatch.setattr(config, "today", lambda: TODAY)
    companies = [
        {"slug": slug, "name": slug, "tier": "a16z", "open_roles": 1}
        for slug in ("mixed", "undated", "unsold", "off-network")
    ]
    monkeypatch.setattr(scoring, "load_companies", lambda: companies[:3])
    monkeypatch.setattr(scoring, "load_universe", lambda: companies)
    matches = [
        {"slug": c["slug"], "cik": str(i), "confidence": scoring.HIGH, "rung": "1"}
        for i, c in enumerate(companies, 1)
    ]
    # A different matched issuer for the same company files a newer unsold notice.
    matches.append(matches[0] | {"cik": "5"})
    pl.DataFrame(matches).write_parquet(config.MATCHES)
    sold_on = TODAY - timedelta(days=21)
    filings = [
        _filing("01", sold_on, 50, sold_on),
        _filing("02", TODAY, 500, None),
        _filing("03", TODAY, 500, None, cik="2"),
        _filing("04", TODAY, 0, None, cik="3"),
        _filing("05", sold_on, 100, sold_on, cik="4"),
        _filing("06", TODAY, 0, None, cik="5"),
    ]
    pl.DataFrame(filings).write_parquet(config.FILINGS)
    collection = scoring.run_score(details={})["collection"]
    assert [m["slug"] for m in collection["members"]] == ["mixed"]
    assert collection["roles"] == 1
    feed = json.loads(config.PUBLIC_FILINGS.read_text())
    assert feed["meta"]["members"] == 1
    assert feed["meta"]["direct_sales_reported"] == 2
    mixed = feed["filings"]["mixed"]
    assert mixed["accession"] == "01"
    assert {n["accession"] for n in mixed["additional_notices"]} == {"02", "06"}
    assert mixed["score"] == scoring.score(50, 1, 21)
    for slug in ("undated", "unsold"):
        notice = feed["filings"][slug]
        assert notice["score"] is None and notice["rank"] is None
        assert notice["open_roles"] == 1 and notice["url"]
    with config.PUBLIC_CSV.open() as file:
        exported = {r["slug"]: r for r in csv.DictReader(file)}
    assert exported["undated"]["score"] == exported["unsold"]["rank"] == ""
    assert json.loads(exported["mixed"]["additional_notices"]) == mixed["additional_notices"]
    assert pl.read_parquet(config.HISTORY)["slug"].to_list() == ["mixed"]

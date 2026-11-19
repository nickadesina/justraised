"""Check the files that the nightly refresh will actually publish."""

import csv
import json

from pipeline import config
from scripts.check_schema import _pages


def test_feed_evidence_survives_csv_and_collection_export():
    feed = json.loads(config.PUBLIC_FILINGS.read_text())
    direct = {**feed["filings"], **feed["off_network"]}
    with config.PUBLIC_CSV.open(newline="") as file:
        exported = {row["slug"]: row for row in csv.DictReader(file)}
    assert direct.keys() == exported.keys()
    assert feed["meta"]["direct_sales_reported"] == sum(
        row["first_sale_reported"] and row["amount_kind"] == "sold" and row["amount_sold"] > 0
        for row in direct.values()
    )
    for slug, row in direct.items():
        assert row["latest_accession"] in row["amount_filing_url"]
        assert exported[slug]["amount_filing_url"] == row["amount_filing_url"]
        assert exported[slug]["first_sale_filing_url"] == (row["first_sale_filing_url"] or "")

    pages = _pages(str(config.PUBLIC_COLLECTION))
    members = [member for _, page in pages for member in page["collection"]["members"]]
    assert len(members) == pages[0][1]["collection"]["members_total"]
    ranked = [row for row in feed["filings"].values() if row["rank"] is not None]
    assert [member["slug"] for member in members] == [r["slug"] for r in sorted(ranked, key=lambda r: r["rank"])]
    assert all(r["first_sale_reported"] and r["amount_sold"] > 0 for r in ranked)


def test_published_investor_profiles_use_the_current_roster():
    roster = {c["slug"]: c for c in json.loads(config.COMPANIES_JSON.read_text())["companies"]}
    universe = json.loads(config.UNIVERSE_JSON.read_text())["companies"]
    assert {c["slug"] for c in universe if c["on_network"]} == roster.keys()
    assert len({c["slug"] for c in universe}) == len(universe)
    current_ids = {c["slug"] for c in universe}
    feed = json.loads(config.PUBLIC_FILINGS.read_text())
    with config.PUBLIC_SPV_CSV.open(newline="") as file:
        exported = {row["slug"]: row for row in csv.DictReader(file)}
    assert feed["spv"].keys() == exported.keys()
    for slug, row in feed["spv"].items():
        assert slug in current_ids
        assert row["on_network"] == (slug in roster)
        assert row["open_roles"] == (roster[slug]["open_roles"] if slug in roster else None)
        assert json.loads(exported[slug]["vehicle_evidence"]) == row["vehicles"]
        if all(vehicle["amount_sold"] == 0 for vehicle in row["vehicles"]):
            assert row["sale_status"] == "no_sales_reported"


def test_static_schema_check_reads_every_advertised_page(tmp_path):
    first = tmp_path / "just-raised.json"
    first.write_text(json.dumps({"collection": {"page": 0, "total_pages": 2}}))
    folder = first.with_suffix("")
    folder.mkdir()
    second = folder / "page-1.json"
    second.write_text(json.dumps({"collection": {"page": 1, "total_pages": 2}}))
    assert [path for path, _ in _pages(str(first))] == [str(first), str(second)]

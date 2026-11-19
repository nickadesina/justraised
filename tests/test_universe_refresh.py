import html
import json

import httpx

from pipeline import fetch_portfolio as portfolio


def _source_row(slug, name, **kwargs):
    return {"slug": slug, "name": name, "tier": "a16z", "on_network": False, **kwargs}


def _portfolio_page(rows):
    return '<div data-companies="' + html.escape(json.dumps(rows), quote=True) + '" />'


def _speedrun_page(props):
    data = json.dumps({"props": {"pageProps": props}})
    return f'<script id="__NEXT_DATA__" type="application/json">{data}</script>'


def test_rebrand_joins_network_by_old_name_and_preserves_prior_id():
    old = _source_row("a16z:plai-labs", "Salt AI", website="https://salt.ai/")
    stub = _source_row("a16z:plai-labs", "Plai Labs")
    network = [{"slug": "plai", "name": "Plai Labs", "tier": "a16z", "open_roles": 4}]
    (merged,) = portfolio.build_universe(network, [old, stub])
    assert merged["slug"] == "plai" and merged["also"] == ["a16z:plai-labs"]
    assert merged["aliases"] == ["Salt AI"] and merged["website"] == old["website"]

    # The source id joins a renamed portfolio entry on subsequent runs, even
    # when the old investment-list spelling disappears.
    renamed = {**old, "name": "Salt Systems"}
    (refreshed,) = portfolio.build_universe(network, [renamed], previous=[merged])
    assert refreshed["slug"] == "plai" and refreshed["on_network"]
    assert set(refreshed["aliases"]) == {"Salt AI", "Salt Systems"}


def test_source_fallback_rebuilds_from_current_network_and_reapplies_exits(tmp_path, monkeypatch):
    for name, path in {"PORTFOLIO_SOURCES_JSON": "sources", "UNIVERSE_JSON": "universe",
                       "PEOPLE_JSON": "people"}.items():
        monkeypatch.setattr(portfolio.config, name, tmp_path / f"{path}.json")
    monkeypatch.setattr(portfolio, "load_aliases", lambda: {})
    network = []
    monkeypatch.setattr(portfolio, "load_companies", lambda: network)
    clock = ["first"]
    monkeypatch.setattr(portfolio.config, "now_iso", lambda: clock[0])
    live = {
        portfolio.A16Z_PORTFOLIO_URL: _portfolio_page([
            {"display_name": "Shield AI", "permalink": "/companies/shield-ai/", "status": "Active"}
        ]),
        portfolio.A16Z_INVESTMENT_LIST_URL: "<li>0x</li><li>Shield AI</li><li>ExitMe</li><li>Zynga</li>",
        portfolio.SPEEDRUN_COMPANIES_URL: _speedrun_page({"list": {"companies": [
            {"name": "Asterfox", "slug": "asterfox", "oneLiner": "Test", "location": "Los Angeles", "logoUrl": "logo"}
        ]}}),
    }

    def get(url):
        if url not in live:
            raise httpx.ConnectError("unavailable")
        return live[url]

    monkeypatch.setattr(portfolio, "_get", get)
    portfolio.fetch_portfolio()
    del live[portfolio.SPEEDRUN_COMPANIES_URL], live[portfolio.A16Z_INVESTMENT_LIST_URL]
    live[portfolio.A16Z_PORTFOLIO_URL] = _portfolio_page([
        {"display_name": "Shield AI", "permalink": "/companies/shield-ai/", "status": "Active"},
        {"display_name": "ExitMe", "status": "Exited"},
    ])
    network.append({"name": "Shield AI", "slug": "shield-ai", "tier": "a16z", "open_roles": 665})
    clock[0] = "second"
    portfolio.fetch_portfolio()
    doc = json.loads(portfolio.config.UNIVERSE_JSON.read_text())
    rows = {c["slug"]: c for c in doc["companies"]}
    assert len(rows) == len(doc["companies"])
    assert rows["shield-ai"]["on_network"] and rows["shield-ai"]["open_roles"] == 665
    assert "a16z:shield-ai" not in rows and "a16z:exitme" not in rows
    assert rows["speedrun:asterfox"]["blurb"] == "Test"
    assert doc["source_fetched_at"] == {"portfolio": "second", "speedrun": "first", "investments": "first"}


def test_legacy_snapshot_retains_external_members_and_drops_stale_job_fields(tmp_path, monkeypatch):
    for attr, file in (("PORTFOLIO_SOURCES_JSON", "cache"), ("UNIVERSE_JSON", "universe"), ("PEOPLE_JSON", "people")):
        monkeypatch.setattr(portfolio.config, attr, tmp_path / f"{file}.json")
    legacy = [
        _source_row("a16z:shield-ai", "Shield AI", focus_areas=[]),
        _source_row("speedrun:sample", "Sample"),
        {"slug": "old", "tier": "a16z", "on_network": True, "name": "Old", "open_roles": 2, "also": ["a16z:old"]},
    ]
    portfolio.config.UNIVERSE_JSON.write_text(json.dumps({"fetched_at": "yesterday", "companies": legacy}))
    monkeypatch.setattr(portfolio, "load_aliases", lambda: {})
    monkeypatch.setattr(portfolio, "load_companies", lambda: [{"slug": "shield-ai", "name": "Shield AI", "open_roles": 665}])

    def unavailable(url):
        if url == portfolio.A16Z_INVESTMENT_LIST_URL:
            return "<li>0x</li><li>Unverified Exit</li><li>Zynga</li>"
        raise httpx.ConnectError("unavailable")
    monkeypatch.setattr(portfolio, "_get", unavailable)
    portfolio.fetch_portfolio()
    rows = {row["slug"]: row for row in portfolio.load_universe()}
    assert set(rows) == {"shield-ai", "speedrun:sample", "a16z:old"}
    assert rows["shield-ai"]["open_roles"] == 665
    assert not rows["a16z:old"]["on_network"] and "open_roles" not in rows["a16z:old"]


def test_previous_speedrun_format():
    (company,) = portfolio.parse_speedrun(_speedrun_page({"companies": {"results": [
        {"slug": "old", "name": "Old", "city": "Seattle", "state": "WA", "preamble": "Team", "logo": "logo"}
    ]}}))
    assert company["location"] == "Seattle, WA" and company["blurb"] == "Team" and company["logo"] == "logo"


def test_review_decisions_follow_unambiguous_source_ids(tmp_path):
    from edgar_names import load_overrides

    aliases = portfolio.canonical_slugs([
        {"slug": "shield-ai", "also": ["a16z:shield-ai", "a16z:shared"]},
        {"slug": "second", "also": ["a16z:shared", "third"]},
        {"slug": "third"},
    ])
    assert "a16z:shared" not in aliases and aliases["third"] == "third"
    path = tmp_path / "decisions.yaml"
    path.write_text('confirm: [{cik: "1", slug: "a16z:shield-ai"}]\n'
                    'reject: [{cik: "2", slug: "a16z:shield-ai"}]\n'
                    'spv_ignore: ["a16z:shield-ai", "a16z:shared"]\n')
    reviewed = load_overrides(path, slug_aliases=aliases)
    assert reviewed.confirmed_slug("1") == "shield-ai"
    assert reviewed.is_rejected("2", "shield-ai")
    assert reviewed.spv_ignore == {"shield-ai", "a16z:shared"}


def test_scoring_resolves_vehicles_cached_under_earlier_source_ids(tmp_path, monkeypatch):
    from datetime import date
    import polars as pl
    from pipeline.score import _spv_groups

    old = tmp_path / "spvs.parquet"
    pl.DataFrame({"slug": ["a16z:shield-ai", "a16z:masked"], "cik": ["1", "2"],
                  "file_date": [date(2026, 11, 7)] * 2}).write_parquet(old)
    config = portfolio.config
    monkeypatch.setattr(config, "SPV_FILINGS", old)
    decisions = tmp_path / "matches.yaml"
    decisions.write_text('spv_ignore: ["a16z:masked"]\n')
    monkeypatch.setattr(config, "OVERRIDES_FILE", decisions)
    aliases = {"a16z:shield-ai": "shield-ai", "a16z:masked": "masked"}
    result = _spv_groups(date(2026, 11, 1), date(2026, 11, 10), aliases)
    assert list(result) == ["shield-ai"]

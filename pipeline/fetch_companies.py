"""Step 1: pull the talent network's hiring companies into data/companies.json.

/companies lists only companies with at least one live role (777 on
2026-11-10: 438 market, 290 a16z, 49 speedrun). Pages are 0-based. Stage,
remote policy, functions and cities are not on the list view, so they are
read from the two portfolio collections, which carry them for every member.

A registry of every portfolio slug ever seen is kept too. A company that
raised and then has zero open roles drops off /companies; the registry lets
score.py still look it up by slug.
"""

from __future__ import annotations

import json
import logging

from . import config
from .clients import TalentClient

log = logging.getLogger(__name__)

_MEMBER_EXTRAS = ("stage", "remote_policy", "functions", "cities", "investors")


def _all_pages(client: TalentClient, path: str, unwrap) -> list[dict]:
    """Walk a 0-based paged endpoint. unwrap(body) -> (rows, total_pages)."""
    out: list[dict] = []
    page = 0
    while True:
        body = client.get(path, page=page)
        if body is None:
            raise RuntimeError(f"{path} returned 404")
        rows, total_pages = unwrap(body)
        out.extend(rows)
        page += 1
        if page >= total_pages:
            return out


def fetch_companies() -> dict:
    client = TalentClient()
    try:
        companies = _all_pages(client, "/companies", lambda b: (b["companies"], b["total_pages"]))
        extras: dict[str, dict] = {}
        for slug in config.PORTFOLIO_COLLECTIONS:
            members = _all_pages(
                client,
                f"/collections/{slug}",
                lambda b: (b["collection"]["members"], b["collection"]["total_pages"]),
            )
            for m in members:
                if m.get("slug"):
                    extras[m["slug"]] = {k: m.get(k) for k in _MEMBER_EXTRAS}
    finally:
        client.close()

    portfolio = []
    for c in companies:
        if c.get("tier") not in config.PORTFOLIO_TIERS:
            continue
        c = {**c, **extras.get(c["slug"], {})}
        portfolio.append(c)

    doc = {
        "fetched_at": config.now_iso(),
        "listed_total": len(companies),
        "portfolio_total": len(portfolio),
        "tiers": {t: sum(1 for c in companies if c.get("tier") == t) for t in sorted({c.get("tier") for c in companies})},
        "companies": sorted(portfolio, key=lambda c: c["slug"]),
    }
    config.DATA.mkdir(parents=True, exist_ok=True)
    config.COMPANIES_JSON.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")

    registry = json.loads(config.REGISTRY_JSON.read_text()) if config.REGISTRY_JSON.exists() else {}
    for c in portfolio:
        registry[c["slug"]] = {
            "name": c["name"],
            "tier": c["tier"],
            "location": c.get("location"),
            "last_seen": doc["fetched_at"][:10],
        }
    config.REGISTRY_JSON.write_text(json.dumps(dict(sorted(registry.items())), indent=1, ensure_ascii=False) + "\n")

    log.info("companies: %d listed, %d portfolio (%s)", len(companies), len(portfolio), doc["tiers"])
    return doc


def load_companies() -> list[dict]:
    return json.loads(config.COMPANIES_JSON.read_text())["companies"]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    fetch_companies()


if __name__ == "__main__":
    main()

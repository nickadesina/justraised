"""Step 1b: the wider portfolio, beyond companies hiring on the talent network.

The talent network's /companies lists only companies with a live role (340
a16z and speedrun companies on 2026-11-10). A company that just raised and has
not posted is exactly the one this list is for, so the matcher also runs
against:

* a16z.com/portfolio: every a16z company, embedded in the page as JSON
  (``data-companies``). Kept: status Active, no acquirer, no ticker.
* a16z.com/investment-list: every disclosed investment (about 1,470 names,
  no status). Names that a16z.com/portfolio marks as exited, acquired or
  public are dropped; the rest join the universe.
* speedrun.a16z.com/companies: the public speedrun list (current cohort only;
  earlier cohorts sit behind a login).
* a16z.com/team: names of the investing team, embedded the same way. A Form D
  that lists one of them as a director or officer is strong evidence the
  issuer is an a16z company (see match.py).

Rebuilds data/portfolio_universe.json with current hiring companies every run.
Each external source has its own last successful snapshot in portfolio_sources.json.
Off-network companies get an identity like ``a16z:databricks`` or
``speedrun:abliteration`` so they can be pinned in matches.yaml like any other.
"""

from __future__ import annotations

import html
import json
import logging
import re
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

import httpx
from edgar_names import name_variants

from . import config
from .fetch_companies import load_companies

log = logging.getLogger(__name__)

A16Z_PORTFOLIO_URL = "https://a16z.com/portfolio/"
A16Z_INVESTMENT_LIST_URL = "https://a16z.com/investment-list/"
A16Z_TEAM_URL = "https://a16z.com/team/"
SPEEDRUN_COMPANIES_URL = "https://speedrun.a16z.com/companies"

# Roles whose people sit on boards and show up on Form Ds.
INVESTING_ROLES = ("Investing", "Board Partners", "Growth Advisory", "Special Advisors", "speedrun")


def _get(url: str) -> str:
    with httpx.Client(timeout=60.0, follow_redirects=True, headers={"User-Agent": "just-raised-pipeline/0.1"}) as c:
        resp = c.get(url)
        resp.raise_for_status()
        return resp.text


def _portfolio_rows(page: str) -> list[dict]:
    m = re.search(r'data-companies="(\[\{.*?)"\s', page, re.S)
    if not m:
        raise ValueError("no data-companies array on a16z.com/portfolio")
    return json.loads(html.unescape(m.group(1)))


def _is_active(c: dict) -> bool:
    return "Active" in (c.get("status") or "") and not c.get("acquirer") and not c.get("ticker_symbol")


def exited_keys(page: str) -> set[str]:
    """Normalized names a16z.com/portfolio marks as exited, acquired or public."""
    return {
        v.strict
        for c in _portfolio_rows(page)
        if not _is_active(c)
        for v in name_variants(c.get("display_name") or c.get("name") or "")
    }


def parse_investment_list(page: str, exited: set[str]) -> list[dict]:
    items = [html.unescape(x).strip() for x in re.findall(r"<li[^>]*>\s*(?:<[^>]+>\s*)*([^<]{1,80}?)\s*(?:<[^>]+>\s*)*</li>", page)]
    if "0x" not in items or "Zynga" not in items:
        raise ValueError("investment list markers not found")
    names = items[items.index("0x") : items.index("Zynga") + 1]
    out, seen = [], set()
    for name in names:
        if not name or name.startswith("[") or len(name) < 2:
            continue
        keys = {v.strict for v in name_variants(name)}
        if keys & exited or keys & seen:
            continue
        seen |= keys
        key = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        out.append({"slug": f"a16z:{key}", "name": name, "tier": "a16z", "on_network": False,
                    "location": None, "blurb": None, "url": None, "website": None})
    return out


def parse_a16z_portfolio(page: str) -> list[dict]:
    out = []
    for c in _portfolio_rows(page):
        if not _is_active(c):
            continue
        name = (c.get("display_name") or c.get("name") or "").strip()
        permalink = c.get("permalink") or ""
        key = permalink.rstrip("/").rsplit("/", 1)[-1] or re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        out.append(
            {
                "slug": f"a16z:{key}",
                "name": name,
                "tier": "a16z",
                "on_network": False,
                "location": None,
                "blurb": (c.get("overview") or c.get("website_description") or "")[:400] or None,
                "url": permalink or None,
                "website": c.get("external_url") or c.get("url") or None,
                "logo": c.get("logo") or None,
                "focus_areas": c.get("focus_areas") or [],
                "first_funded": c.get("initial_a16z_date_funded") or None,
            }
        )
    return out


def parse_speedrun(page: str) -> list[dict]:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', page, re.S)
    if not m:
        raise ValueError("no __NEXT_DATA__ on speedrun.a16z.com/companies")
    props = json.loads(m.group(1))["props"]["pageProps"]
    rows = props["list"]["companies"] if "list" in props else props["companies"]["results"]
    out = []
    for c in rows:
        loc = c.get("location") or ", ".join(x for x in (c.get("city"), c.get("state") or c.get("country")) if x) or None
        out.append(
            {
                "slug": f"speedrun:{c['slug']}",
                "name": c["name"].strip(),
                "tier": "speedrun",
                "on_network": False,
                "cohort": c.get("cohort"),
                "location": loc,
                "blurb": c.get("oneLiner") or c.get("preamble"),
                "url": f"https://speedrun.a16z.com/companies/{c['slug']}",
                "website": None,
                "logo": c.get("logoUrl") or c.get("logo") or None,
            }
        )
    return out


def parse_a16z_team(page: str) -> list[dict]:
    text = html.unescape(page)
    people = {}
    for m in re.finditer(
        r'\{"id":\d+,"name":"([^"]+)","profile_url":"https://a16z\.com/author/([a-z0-9-]+)/".{0,800}?"role_display":"([^"]*)"',
        text,
    ):
        name, slug, role = m.groups()
        if any(r in role for r in INVESTING_ROLES):
            people[slug] = {"name": name, "role": role}
    if not people:
        raise ValueError("no investing-team people parsed from a16z.com/team")
    return [{"slug": k, **v} for k, v in sorted(people.items())]


def load_aliases() -> dict[str, list[str]]:
    if not config.ALIASES_FILE.exists():
        return {}
    import yaml

    return {str(k): [str(x) for x in v] for k, v in (yaml.safe_load(config.ALIASES_FILE.read_text()) or {}).items()}


def _names(company: dict) -> list[str]:
    return [company["name"], *company.get("aliases", [])]


def _name_keys(names: list[str]) -> set[str]:
    return {v.strict for name in names for v in name_variants(name) if v.strict}


def _merge_company(row: dict, other: dict) -> None:
    """Keep the preferred record's identity and retain the other record's spellings."""
    for field, primary, values in (
        ("aliases", "name", _names(other)),
        ("also", "slug", [other["slug"], *other.get("also", [])]),
    ):
        merged = list(dict.fromkeys([*row.get(field, []), *values]))
        merged = [value for value in merged if value != row[primary]]
        if merged:
            row[field] = merged
    for field in ("website", "logo", "blurb"):
        if other.get(field) and not row.get(field):
            row[field] = other[field]


def build_universe(network: list[dict], extra: list[dict], aliases: dict[str, list[str]] | None = None,
                   previous: list[dict] | None = None) -> list[dict]:
    # A renamed portfolio company and its old investment-list entry can share
    # one permalink. Combine these before matching either name to the network.
    sources: dict[str, dict] = {}
    for c in extra:
        if c["slug"] in sources:
            _merge_company(sources[c["slug"]], c)
        else:
            sources[c["slug"]] = dict(c)

    historical: dict[str, list[dict]] = defaultdict(list)
    for old in previous or []:
        for slug in {old["slug"], *old.get("also", [])}:
            historical[slug].append(old)
    alias_keys = {k: names for brand, names in (aliases or {}).items() for k in _name_keys([brand])}
    out: dict[str, dict] = {}
    by_name: dict[str, set[str]] = defaultdict(set)
    by_id: dict[str, str] = {}
    network_rows = [{**c, "on_network": True} for c in network]
    for c in [*network_rows, *sources.values()]:
        row = dict(c)
        for old in historical.get(row["slug"], []):
            # Identity persists between snapshots; jobs and profile fields always
            # come from the current source. Never carry a former network's jobs.
            _merge_company(row, {k: old[k] for k in ("name", "slug", "also", "aliases") if k in old})
        for key in _name_keys(_names(row)):
            for alias in alias_keys.get(key, []):
                _merge_company(row, {"slug": row["slug"], "name": alias})

        ids = [row["slug"], *row.get("also", [])]
        matches = {by_id[key] for key in ids if key in by_id}
        if not row["on_network"] and not matches:
            matches = {slug for key in _name_keys(_names(row)) for slug in by_name.get(key, ())}
        if len(matches) == 1 and (not row["on_network"] or row["slug"] in out):
            (slug,) = matches
            _merge_company(out[slug], row)
        else:
            slug = row["slug"]
            out[slug] = row
        for key in ids:
            by_id.setdefault(key, slug)
        for key in _name_keys(_names(row)):
            by_name[key].add(slug)
    return list(out.values())


def _legacy_source(previous: list[dict], source: str) -> list[dict]:
    """Recover a failed source on the first upgrade from the old merged snapshot."""
    rows = []
    for c in previous:
        ids = [c["slug"], *c.get("also", [])]
        for slug in dict.fromkeys(ids):
            if ":" not in slug:
                continue
            if slug.startswith("speedrun:"):
                origin = "speedrun"
            elif slug == c["slug"] and "focus_areas" in c:
                origin = "portfolio"
            else:
                origin = "investments"
            # Before per-source snapshots, a network row retained its external
            # IDs but not which of the two a16z pages supplied each ID.
            if origin != source and not (source == "portfolio" and c["on_network"] and slug.startswith("a16z:")):
                continue
            row = {k: c[k] for k in ("name", "location", "blurb", "website", "logo", "aliases") if k in c}
            row.update(slug=slug, on_network=False, tier=slug.split(":")[0],
                       url=c.get("url") if not c["on_network"] else None)
            rows.append(row)
    return rows


def _write_json(path: Path, doc: dict) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    tmp.replace(path)


def refresh_universe() -> None:
    previous = json.loads(config.UNIVERSE_JSON.read_text()) if config.UNIVERSE_JSON.exists() else {}
    cache = json.loads(config.PORTFOLIO_SOURCES_JSON.read_text()) if config.PORTFOLIO_SOURCES_JSON.exists() else {}
    now = config.now_iso()
    for source, url, parse in (
        ("portfolio", A16Z_PORTFOLIO_URL, parse_a16z_portfolio),
        ("speedrun", SPEEDRUN_COMPANIES_URL, parse_speedrun),
        ("investments", A16Z_INVESTMENT_LIST_URL, lambda page: parse_investment_list(page, set())),
    ):
        try:
            page = _get(url)
            rows = parse(page)
            if not rows:
                raise ValueError("empty company list")
            snapshot = {"fetched_at": now, "companies": rows}
            if source == "portfolio":
                snapshot["exited"] = sorted(exited_keys(page))
            cache[source] = snapshot
            log.info("portfolio: %d companies from %s", len(rows), url)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            if source not in cache:
                cache[source] = {"fetched_at": previous.get("fetched_at"),
                                 "companies": _legacy_source(previous.get("companies", []), source)}
            log.warning("portfolio: using last known %s snapshot after %s", source, exc)

    # Keep the investment source unfiltered in its cache, so a refreshed
    # portfolio can remove exits even when the investment-list request fails.
    exited = cache["portfolio"].get("exited")
    old_keys = _name_keys([c["name"] for c in previous.get("companies", [])]) if exited is None else set()
    excluded = set(exited or [])
    extra = [*cache["portfolio"]["companies"], *cache["speedrun"]["companies"]]
    for c in cache["investments"]["companies"]:
        keys = _name_keys(_names(c))
        # A legacy snapshot has no exit list. Until its first successful
        # refresh, retain only investment names already in the filtered universe.
        if not keys & excluded and (exited is not None or keys & old_keys):
            extra.append(c)
    universe = build_universe(load_companies(), extra, load_aliases(), previous.get("companies", []))
    doc = {
        "fetched_at": now,
        "source_fetched_at": {key: value["fetched_at"] for key, value in cache.items()},
        "on_network": sum(1 for c in universe if c["on_network"]),
        "off_network": sum(1 for c in universe if not c["on_network"]),
        "companies": universe,
    }
    _write_json(config.PORTFOLIO_SOURCES_JSON, cache)
    _write_json(config.UNIVERSE_JSON, doc)
    log.info("universe: %d on the talent network, %d off it", doc["on_network"], doc["off_network"])


def fetch_portfolio() -> None:
    refresh_universe()
    try:
        people = parse_a16z_team(_get(A16Z_TEAM_URL))
        config.PEOPLE_JSON.write_text(json.dumps({"fetched_at": config.now_iso(), "people": people}, indent=1) + "\n")
        log.info("people: %d a16z investing-team names", len(people))
    except Exception as exc:
        log.warning("people: could not read a16z.com/team (%s); keeping the previous file", exc)


def load_universe() -> list[dict]:
    if not config.UNIVERSE_JSON.exists():
        return [{**c, "on_network": True} for c in load_companies()]
    return json.loads(config.UNIVERSE_JSON.read_text())["companies"]


def canonical_slugs(universe: Iterable[dict]) -> dict[str, str]:
    """Resolve alternate source IDs only when they have a single current owner."""
    current = {}
    owners: dict[str, set[str]] = defaultdict(set)
    for c in universe:
        slug = c["slug"]
        current[slug] = slug
        for alias in c.get("also", []):
            owners[alias].add(slug)
    for alias, slugs in owners.items():
        if len(slugs) == 1:
            current.setdefault(alias, next(iter(slugs)))
    return current


def load_people() -> list[str]:
    if not config.PEOPLE_JSON.exists():
        return []
    return [p["name"] for p in json.loads(config.PEOPLE_JSON.read_text())["people"]]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    fetch_portfolio()


if __name__ == "__main__":
    main()

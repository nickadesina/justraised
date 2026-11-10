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

Writes data/portfolio_universe.json and data/a16z_people.json. If a page
cannot be fetched or parsed, the previous file is kept and the run goes on.
Off-network companies get an identity like ``a16z:databricks`` or
``speedrun:abliteration`` so they can be pinned in matches.yaml like any other.
"""

from __future__ import annotations

import html
import json
import logging
import re

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
    rows = json.loads(m.group(1))["props"]["pageProps"]["companies"]["results"]
    out = []
    for c in rows:
        loc = ", ".join(x for x in (c.get("city"), c.get("state") or c.get("country")) if x) or None
        out.append(
            {
                "slug": f"speedrun:{c['slug']}",
                "name": c["name"].strip(),
                "tier": "speedrun",
                "on_network": False,
                "cohort": c.get("cohort"),
                "location": loc,
                "blurb": c.get("preamble"),
                "url": f"https://speedrun.a16z.com/companies/{c['slug']}",
                "website": None,
                "logo": c.get("logo") or None,
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


def build_universe(network: list[dict], extra: list[dict], aliases: dict[str, list[str]] | None = None) -> list[dict]:
    """Talent-network companies first; wider-portfolio companies whose name is
    already present are folded into that entry, not duplicated. Earlier sources
    win, so pass a16z.com/portfolio (which has websites) before the bare
    investment list."""
    by_key: dict[str, dict] = {}
    out = []
    for c in network:
        entry = {**c, "on_network": True}
        out.append(entry)
        for v in name_variants(c["name"]):
            by_key.setdefault(v.strict, entry)
    for c in extra:
        keys = [v.strict for v in name_variants(c["name"])]
        hit = next((by_key[k] for k in keys if k in by_key), None)
        if hit is not None:
            hit.setdefault("also", []).append(c["slug"])
            for k in ("website", "logo", "blurb"):
                if c.get(k) and not hit.get(k):
                    hit[k] = c[k]
            continue
        out.append(c)
        for k in keys:
            by_key.setdefault(k, c)
    alias_by_key = {v.strict: names for brand, names in (aliases or {}).items() for v in name_variants(brand)}
    for c in out:
        for v in name_variants(c["name"]):
            if v.strict in alias_by_key:
                c["aliases"] = alias_by_key[v.strict]
    return out


def fetch_portfolio() -> None:
    extra: list[dict] = []
    ok = True
    exited: set[str] = set()
    try:
        page = _get(A16Z_PORTFOLIO_URL)
        exited = exited_keys(page)
        rows = parse_a16z_portfolio(page)
        log.info("portfolio: %d active companies from a16z.com/portfolio (%d exited names)", len(rows), len(exited))
        extra += rows
    except Exception as exc:  # a redesign of any page must not stop the nightly run
        ok = False
        log.warning("portfolio: could not read a16z.com/portfolio (%s)", exc)
    for url, parse in ((SPEEDRUN_COMPANIES_URL, parse_speedrun), (A16Z_INVESTMENT_LIST_URL, lambda p: parse_investment_list(p, exited))):
        try:
            rows = parse(_get(url))
            log.info("portfolio: %d companies from %s", len(rows), url)
            extra += rows
        except Exception as exc:
            ok = False
            log.warning("portfolio: could not read %s (%s)", url, exc)

    if ok or not config.UNIVERSE_JSON.exists():
        universe = build_universe(load_companies(), extra, load_aliases())
        doc = {
            "fetched_at": config.now_iso(),
            "on_network": sum(1 for c in universe if c["on_network"]),
            "off_network": sum(1 for c in universe if not c["on_network"]),
            "companies": universe,
        }
        config.UNIVERSE_JSON.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
        log.info("universe: %d on the talent network, %d off it", doc["on_network"], doc["off_network"])
    else:
        log.warning("universe: keeping the previous %s", config.UNIVERSE_JSON.name)

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


def load_people() -> list[str]:
    if not config.PEOPLE_JSON.exists():
        return []
    return [p["name"] for p in json.loads(config.PEOPLE_JSON.read_text())["people"]]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    fetch_portfolio()


if __name__ == "__main__":
    main()

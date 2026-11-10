"""Board health: what the talent team could fix on its own job board.

For every portfolio company on the talent network, one
``/jobs?company=<name>&page_size=1`` call. Its facets give the company's
posting buckets (24h / 7d / 30d), function mix, founding roles, and how many
roles post comp, and its total says whether the company filter works at all:
``/jobs`` filters on the name the jobs carry, which for some companies is not
the name ``/companies`` returns ("Anduril" vs "Anduril Industries"). A miss
falls back to a free-text search for the jobs-side name.

One download of ``/jobs.md`` (every open role on the board, one line each)
counts listings that repeat a title at the same company, usually one role
posted once per city. jobs.md uses the ``/companies`` display name, so it
joins on that.

Writes public/api/just-raised/board.json. score.py reuses the posting buckets
instead of calling ``/jobs`` again.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter, defaultdict

from . import config
from .clients import TalentClient
from .fetch_companies import load_companies

log = logging.getLogger(__name__)

# "- [Staff Brand Designer at Harvey](https://.../jobs/...) - New York · Full Time · $181k - $249k"
_MD_ROLE = re.compile(r"^- \[(?P<title>.+) at (?P<company>.+?)\]\(https://speedrun-talent-network\.com/jobs/[^)]+\)")


def parse_jobs_md(text: str) -> list[tuple[str, str]]:
    """(title, company) for every role line in /jobs.md."""
    out = []
    for line in text.splitlines():
        m = _MD_ROLE.match(line)
        if m:
            out.append((m["title"].strip(), m["company"].strip()))
    return out


def duplicate_counts(roles: list[tuple[str, str]]) -> dict[str, dict]:
    """company -> {rows, titles}: listings vs distinct titles."""
    titles: dict[str, set[str]] = defaultdict(set)
    rows: Counter[str] = Counter()
    for title, company in roles:
        rows[company] += 1
        titles[company].add(title.lower())
    return {c: {"rows": rows[c], "titles": len(titles[c])} for c in rows}


def summarize(body: dict | None) -> dict | None:
    """The per-company numbers the board page shows, from one /jobs response."""
    if not body:
        return None
    f = body.get("facets") or {}
    posted = f.get("posted") or {}
    return {
        "total": int(body.get("total") or 0),
        "posted_24h": posted.get("24h"),
        "posted_7d": posted.get("7d"),
        "posted_30d": posted.get("30d"),
        "comp_posted": f.get("compAvailable"),
        "founding": f.get("founding"),
        "functions": [
            {"function": x["v"], "n": x["n"]}
            for x in sorted(f.get("fn") or [], key=lambda x: -x.get("n", 0))
            if x.get("n")
        ][:5],
    }


def run_board(companies: list[dict] | None = None) -> dict:
    from .score import _jobs_company_key  # same fallback score.py uses

    companies = companies if companies is not None else load_companies()
    client = TalentClient()
    rows = []
    try:
        md = client.get_site_text("/jobs.md")
        roles = parse_jobs_md(md)
        dupes = duplicate_counts(roles)
        for c in companies:
            name, open_roles = c["name"], int(c.get("open_roles") or 0)
            body = client.get("/jobs", company=name, page_size=1)
            jobs_name = name
            filter_ok = (body or {}).get("total", 0) > 0 or open_roles == 0
            if not filter_ok:
                alt = _jobs_company_key(client, c["slug"], name)
                retry = client.get("/jobs", company=alt, page_size=1) if alt and alt != name else None
                if (retry or {}).get("total", 0) > 0:
                    body, jobs_name = retry, alt
                else:
                    body, jobs_name = None, None
            s = summarize(body) or {}
            d = dupes.get(name) or {}
            rows.append(
                {
                    "slug": c["slug"],
                    "name": name,
                    "tier": c.get("tier"),
                    "cohort": c.get("cohort"),
                    "logo": c.get("logo"),
                    "url": c.get("url"),
                    "open_roles": open_roles,
                    "filter_ok": filter_ok,
                    "jobs_name": jobs_name,  # the name company= accepts; None if none found
                    "listings": d.get("rows"),
                    "distinct_titles": d.get("titles"),
                    **{k: s.get(k) for k in ("posted_24h", "posted_7d", "posted_30d", "comp_posted", "founding")},
                    "functions": s.get("functions") or [],
                }
            )
    finally:
        client.close()

    distinct = len({(c, t.lower()) for t, c in roles})
    doc = {
        "generated_at": config.now_iso(),
        "board": {
            "roles": len(roles),
            "distinct_company_titles": distinct,
            "repeat_listings": len(roles) - distinct,
        },
        "portfolio": {
            "companies": len(rows),
            "filter_misses": sum(1 for r in rows if not r["filter_ok"]),
            "roles_behind_filter_misses": sum(r["open_roles"] for r in rows if not r["filter_ok"]),
        },
        "companies": sorted(rows, key=lambda r: -r["open_roles"]),
    }
    config.PUBLIC_BOARD.parent.mkdir(parents=True, exist_ok=True)
    config.PUBLIC_BOARD.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    log.info(
        "board: %d roles, %d repeat listings; %d/%d portfolio companies miss the company filter",
        doc["board"]["roles"], doc["board"]["repeat_listings"],
        doc["portfolio"]["filter_misses"], doc["portfolio"]["companies"],
    )
    return doc


def load_board_buckets() -> dict[str, dict]:
    """slug -> {"24h", "7d", "30d"} from the last board run, for score.py."""
    if not config.PUBLIC_BOARD.exists():
        return {}
    doc = json.loads(config.PUBLIC_BOARD.read_text())
    if not str(doc.get("generated_at", "")).startswith(config.today().isoformat()):
        return {}  # stale: score.py fetches fresh counts instead
    return {
        r["slug"]: {"24h": r["posted_24h"], "7d": r["posted_7d"], "30d": r["posted_30d"]}
        for r in doc.get("companies", [])
        if r.get("posted_30d") is not None
    }


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    run_board()


if __name__ == "__main__":
    main()

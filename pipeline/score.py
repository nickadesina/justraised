"""Step 4: rank High matches and write the three public files.

    score = log10(amount + 1) / (open_roles + 1) * 0.5 ** (days_since_first_sale / 45)

amount is totalAmountSold when nonzero, else totalOfferingAmount (flagged
"offering, not yet sold"). The window (config.WINDOW_DAYS) and the decay both run from
dateOfFirstSale on the original notice; an amendment updates the amount and
nothing else.

Writes (static files; GitHub Pages serves them as the API):
  public/api/collections/just-raised.json  exactly the talent network's
                           GET /api/v1/collections/{slug} response (page 0;
                           just-raised/page-N.json if it ever passes 100)
  public/api/just-raised/filings.json      the Form D detail per slug, plus run
                           metadata (additive)
  public/api/just-raised.csv               every column
  data/history.parquet     one row per company per night, so the hiring lag
                           can be measured instead of assumed

Refuses to publish if the High-confidence count falls more than
MAX_HIGH_DROP from the previous run (a broken normalizer, not real news).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import logging
import math
import sys
from datetime import date, datetime, timedelta

import polars as pl

from . import config
from .clients import TalentClient
from .fetch_companies import load_companies
from .fetch_portfolio import load_universe
from .match import HIGH

log = logging.getLogger(__name__)

def collection_description() -> str:
    return f"Portfolio companies with a Form D in the last {config.WINDOW_DAYS} days, ranked by cash per open role"
PAGE_SIZE = 100  # their collection page size
MEMBER_FIELDS = (
    "rank", "name", "slug", "url", "tier", "cohort", "open_roles", "location", "blurb",
    "stage", "remote_policy", "investors", "functions", "cities", "logo",
)  # exactly the properties of their collection member schema


def score(amount: float | None, open_roles: int, days: int) -> float:
    return math.log10((amount or 0.0) + 1.0) / (open_roles + 1) * 0.5 ** (days / config.HALF_LIFE_DAYS)


# --- offerings ----------------------------------------------------------------


def build_offerings(filings: list[dict]) -> list[dict]:
    """Group one issuer's filings into offerings: an original notice plus its amendments.

    An amendment joins the original named in previousAccessionNumber (following
    chains of amendments), else the original with the same dateOfFirstSale,
    else it stands alone and its own dateOfFirstSale (never its file date)
    starts the window.
    """
    by_adsh = {f["adsh"]: f for f in filings}
    originals = {f["adsh"]: f for f in filings if not f["is_amendment"]}
    groups: dict[str, list[dict]] = {a: [f] for a, f in originals.items()}

    def root_of(f: dict) -> str | None:
        seen = set()
        cur = f
        while cur["is_amendment"] and cur.get("previous_accession") and cur["adsh"] not in seen:
            seen.add(cur["adsh"])
            nxt = by_adsh.get(cur["previous_accession"])
            if nxt is None:
                return None
            cur = nxt
        return cur["adsh"] if not cur["is_amendment"] else None

    for f in sorted(filings, key=lambda x: x["file_date"]):
        if not f["is_amendment"]:
            continue
        root = root_of(f)
        if root is None:
            same_date = [
                o for o in originals.values()
                if o["date_of_first_sale"] and o["date_of_first_sale"] == f["date_of_first_sale"]
            ]
            root = same_date[0]["adsh"] if same_date else None
        if root is None:
            groups[f["adsh"]] = [f]
        else:
            groups[root].append(f)

    offerings = []
    for root_adsh, members in groups.items():
        members.sort(key=lambda x: (x["file_date"], x["adsh"]))
        root = members[0]
        latest = members[-1]
        first_sale = root["date_of_first_sale"]
        if first_sale is None:
            # "Yet to occur" or missing: the notice itself is the earliest date we have.
            first_sale = root["file_date"]
        sold = latest["total_amount_sold"] or 0.0
        offered = latest["total_offering_amount"]
        if sold > 0:
            amount, kind = sold, "sold"
        elif offered:
            amount, kind = offered, "offering"
        else:
            amount, kind = None, "unknown"
        offerings.append(
            {
                "root": root,
                "latest": latest,
                "amendments": len(members) - 1,
                "first_sale": first_sale,
                "first_sale_reported": root["date_of_first_sale"] is not None,
                "amount": amount,
                "amount_kind": kind,
                "amount_sold": sold,
                "offering_amount": offered,
                "offering_indefinite": bool(latest["offering_indefinite"]),
            }
        )
    return offerings


# --- talent network detail ----------------------------------------------------


def _parse_ts(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def fetch_details(slugs: list[str]) -> dict[str, dict | None]:
    client = TalentClient()
    try:
        return {s: (client.get(f"/companies/{s}") or {}).get("company") for s in slugs}
    finally:
        client.close()


def posted_counts(body: dict | None, open_roles: int | None) -> dict | None:
    """Read the 24h / 7d / 30d posting buckets from a /jobs response's facets.

    /jobs filters on the display name, case-sensitive, not the slug
    (company=harvey returns nothing), and an unmatched name returns zero rows
    rather than an error. Zero rows for a company that has open roles means the
    name didn't match, so that is None, not a hiring freeze.
    """
    if not body:
        return None
    buckets = (body.get("facets") or {}).get("posted") or {}
    if body.get("total", 0) == 0 and (open_roles or 0) > 0:
        return None
    try:
        return {k: int(buckets[k]) for k in ("24h", "7d", "30d")}
    except (KeyError, TypeError, ValueError):
        return None


def _jobs_company_key(client: TalentClient, slug: str, name: str) -> str | None:
    """The name /jobs filters on, when it differs from the /companies name.

    /companies says "Anduril", but company=Anduril returns nothing; the jobs
    carry "Anduril Industries". A free-text search finds a job with the right
    company_slug, and its company field is the key the filter accepts.
    """
    body = client.get("/jobs", q=name[:120]) or {}
    for job in body.get("jobs") or []:
        if job.get("company_slug") == slug and job.get("company"):
            return job["company"]
    return None


def fetch_posted(names: dict[str, tuple[str, int | None]]) -> dict[str, dict | None]:
    """slug -> posting buckets, usually one /jobs call per company (slug -> (name, open_roles))."""
    client = TalentClient()
    out: dict[str, dict | None] = {}
    try:
        for slug, (name, open_roles) in names.items():
            buckets = posted_counts(client.get("/jobs", company=name, page_size=1), open_roles)
            if buckets is None and (open_roles or 0) > 0:
                key = _jobs_company_key(client, slug, name)
                if key and key != name:
                    log.info("posted: %s is %r on /jobs, not %r", slug, key, name)
                    buckets = posted_counts(client.get("/jobs", company=key, page_size=1), open_roles)
            out[slug] = buckets
        return out
    finally:
        client.close()


# --- publish ------------------------------------------------------------------


def _previous_high_count() -> int | None:
    if not config.PUBLIC_FILINGS.exists():
        return None
    try:
        return json.loads(config.PUBLIC_FILINGS.read_text())["meta"]["high_matches"]
    except (KeyError, ValueError):
        return None


def run_score(force: bool = False, details: dict | None = None, buckets_by_slug: dict | None = None) -> dict:
    today = config.today()
    window_start = today - timedelta(days=config.WINDOW_DAYS)
    companies = {c["slug"]: c for c in load_companies()}
    universe = {c["slug"]: c for c in load_universe()}
    registry = json.loads(config.REGISTRY_JSON.read_text()) if config.REGISTRY_JSON.exists() else {}

    matches = pl.read_parquet(config.MATCHES).filter(pl.col("confidence") == HIGH)
    filings = pl.read_parquet(config.FILINGS)
    by_cik: dict[str, list[dict]] = {}
    for f in filings.iter_rows(named=True):
        by_cik.setdefault(f["cik"], []).append(f)

    # Best in-window offering per company.
    chosen: dict[str, dict] = {}
    high_pairs_in_window = 0
    for m in matches.iter_rows(named=True):
        slug = m["slug"]
        if slug not in companies and slug not in registry and slug not in universe:
            continue
        # Keyed on CIK: every filing by this issuer, so amendments filed under a
        # slightly different name still attach to their original.
        issuer_filings = by_cik.get(m["cik"], [])
        in_window = [
            o for o in build_offerings(issuer_filings)
            if window_start <= o["first_sale"] <= today
        ]
        if not in_window:
            continue
        high_pairs_in_window += 1
        best = max(in_window, key=lambda o: (o["first_sale"], o["latest"]["file_date"]))
        best["match"] = m
        best["offerings_in_window"] = len(in_window)
        prev = chosen.get(slug)
        if prev is None or best["first_sale"] > prev["first_sale"]:
            chosen[slug] = best

    # Guardrail before any network calls or writes.
    prev_high = _previous_high_count()
    if prev_high and not force:
        drop = 1 - high_pairs_in_window / prev_high
        if drop > config.MAX_HIGH_DROP:
            log.error(
                "refusing to publish: High matches fell from %d to %d (%.0f%% drop > %.0f%%). "
                "Check the normalizer, or rerun with --force if the drop is real.",
                prev_high, high_pairs_in_window, drop * 100, config.MAX_HIGH_DROP * 100,
            )
            sys.exit(2)

    network_slugs = sorted(s for s in chosen if s in companies or s in registry)
    spv_groups = _spv_groups(window_start, today)
    spv_network = sorted(s for s in spv_groups if s in companies and s not in network_slugs)
    details = details if details is not None else fetch_details(network_slugs + spv_network)
    if buckets_by_slug is None:
        names = {}
        for s in network_slugs + spv_network:
            c = {**(details.get(s) or {}), **(companies.get(s) or {})}
            if c.get("name"):
                names[s] = (c["name"], c.get("open_roles"))
        buckets_by_slug = fetch_posted(names)

    rows = []
    off_rows = []
    for slug, off in chosen.items():
        if slug not in network_slugs:
            row = _off_network_row(universe[slug], off, today)
            if row:
                off_rows.append(row)
            continue
        base = companies.get(slug)
        detail = details.get(slug)
        if base is None and detail is None:
            log.info("skip %s: no longer on the talent network", slug)
            continue
        company = {**(detail or {}), **(base or {})}
        if (company.get("name") or "").strip().lower() == "stealth":
            continue  # never unmask a stealth company, whatever the join key
        if company.get("stage") in config.EXCLUDE_STAGES:
            log.info("skip %s: stage %s", slug, company.get("stage"))
            continue
        jobs = (detail or {}).get("jobs") or []
        open_roles = int(company.get("open_roles") if base else len(jobs))
        posted = sorted(d for d in (_parse_ts(j.get("published_at")) for j in jobs) if d)
        since = [d for d in posted if d >= off["first_sale"]]
        days = (today - off["first_sale"]).days
        labels = (detail or {}).get("labels") or {}
        rows.append(
            {
                "on_network": True,
                "slug": slug,
                "name": company["name"],
                "url": company.get("url") or f"https://speedrun-talent-network.com/companies/{slug}",
                "tier": company["tier"],
                "cohort": company.get("cohort"),
                "open_roles": open_roles,
                "location": company.get("location"),
                "blurb": company.get("blurb"),
                "stage": company.get("stage"),
                "remote_policy": company.get("remote_policy"),
                "investors": company.get("investors") or [],
                "functions": company.get("functions") or [],
                "cities": company.get("cities") or [],
                "logo": company.get("logo"),
                # --- filing detail (additive endpoint) ---
                "stage_label": labels.get("stage"),
                "size_label": labels.get("size"),
                "score": score(off["amount"], open_roles, days),
                **_filing_fields(off, today),
                "roles_since_first_sale": len(since),
                "first_post_since": since[0].isoformat() if since else None,
                "days_to_first_post": (since[0] - off["first_sale"]).days if since else None,
                "roles_posted_30d": (buckets_by_slug.get(slug) or {}).get("30d"),
                "roles_posted_7d": (buckets_by_slug.get(slug) or {}).get("7d"),
            }
        )

    direct = {r["slug"] for r in rows} | {r["slug"] for r in off_rows}
    spv_rows = []
    for slug, group in spv_groups.items():
        company = companies.get(slug) or universe.get(slug)
        if not company or (company.get("name") or "").strip().lower() == "stealth":
            continue
        if company.get("stage") in config.EXCLUDE_STAGES:
            continue
        row = _spv_row(company, group, details.get(slug), slug in companies, slug in direct, today)
        buckets = buckets_by_slug.get(slug) if slug in companies else None
        row["roles_posted_30d"] = (buckets or {}).get("30d")
        row["roles_posted_7d"] = (buckets or {}).get("7d")
        spv_rows.append(row)
    spv_rows.sort(key=lambda r: (r["latest_spv_file_date"], r["spvs"]), reverse=True)
    for i, r in enumerate(spv_rows, 1):
        r["rank"] = i

    rows.sort(key=lambda r: (-r["score"], r["name"].lower()))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    off_rows.sort(key=lambda r: (-r["score"], r["name"].lower()))
    for i, r in enumerate(off_rows, 1):
        r["rank"] = i

    generated_at = config.now_iso()
    meta = {
        "generated_at": generated_at,
        "run_date": today.isoformat(),
        "window_days": config.WINDOW_DAYS,
        "half_life_days": config.HALF_LIFE_DAYS,
        "formula": f"log10(amount + 1) / (open_roles + 1) * 0.5 ^ (days_since_first_sale / {config.HALF_LIFE_DAYS})",
        "high_matches": high_pairs_in_window,
        "members": len(rows),
        "off_network": len(off_rows),
        "spv_companies": len(spv_rows),
        "off_network_formula": f"log10(amount + 1) * 0.5 ^ (days_since_first_sale / {config.HALF_LIFE_DAYS}); open roles are not tracked",
        "lag_assumption": "Postings follow a raise by one to three months. Assumed, not yet measured.",
    }
    members = [{k: r[k] for k in MEMBER_FIELDS} for r in rows]
    header = {
        "slug": "just-raised",
        "title": "Just raised",
        "description": collection_description(),
        "group": "signals",
        "url": config.SITE_URL,
        "companies": len(rows),
        "roles": sum(r["open_roles"] for r in rows),
        "portfolio_members": sum(1 for r in rows if r["tier"] in config.PORTFOLIO_TIERS),
    }
    total_pages = math.ceil(len(members) / PAGE_SIZE)
    pages = []
    for p in range(max(total_pages, 1)):
        pages.append(
            {
                "collection": {
                    **header,
                    "members": members[p * PAGE_SIZE : (p + 1) * PAGE_SIZE],
                    "members_total": len(members),
                    "page": p,
                    "page_size": PAGE_SIZE,
                    "total_pages": total_pages,
                }
            }
        )
    keep = ("rank", "slug", "name", "tier", "cohort")
    filings_doc = {
        "meta": meta,
        "filings": {r["slug"]: {k: v for k, v in r.items() if k not in MEMBER_FIELDS or k in keep} for r in rows},
        # Portfolio companies (a16z.com, speedrun.a16z.com) with a matched Form D
        # that are not on the talent network: no slug there, no open-role count.
        "off_network": {r["slug"]: r for r in off_rows},
        # Investor SPVs named after a portfolio company (pipeline/spv.py): a sign
        # money is being pooled to buy in, as a new round or a share purchase.
        "spv": {r["slug"]: r for r in spv_rows},
    }

    for path in (config.PUBLIC_COLLECTION, config.PUBLIC_FILINGS, config.PUBLIC_CSV):
        path.parent.mkdir(parents=True, exist_ok=True)
    config.PUBLIC_COLLECTION.write_text(json.dumps(pages[0], indent=1, ensure_ascii=False) + "\n")
    extra_dir = config.PUBLIC_COLLECTION.with_suffix("")
    for old in extra_dir.glob("page-*.json") if extra_dir.exists() else []:
        old.unlink()
    for p, doc in enumerate(pages[1:], 1):
        extra_dir.mkdir(exist_ok=True)
        (extra_dir / f"page-{p}.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n")
    config.PUBLIC_FILINGS.write_text(json.dumps(filings_doc, indent=1, ensure_ascii=False) + "\n")
    config.PUBLIC_CSV.write_text(to_csv(rows + off_rows))
    config.PUBLIC_SPV_CSV.write_text(_spv_csv(spv_rows))
    _append_history(today, rows)
    log.info(
        "score: %d on the talent network + %d off it + %d with investor SPVs published (%d High pairs in window)",
        len(rows), len(off_rows), len(spv_rows), high_pairs_in_window,
    )
    return pages[0]


CSV_FIELDS = [
    "on_network", "rank", "name", "slug", "tier", "cohort", "stage", "stage_label", "size_label", "location",
    "score", "amount", "amount_kind", "amount_sold", "offering_amount", "date_of_first_sale",
    "days_since_first_sale", "file_date", "latest_file_date", "amendments", "open_roles",
    "roles_since_first_sale", "roles_posted_30d", "roles_posted_7d", "first_post_since", "days_to_first_post", "issuer_name",
    "issuer_cik", "issuer_city", "issuer_state", "accession", "filing_url", "url", "website",
    "match_rung", "a16z_person",
]


def _filing_fields(off: dict, today: date) -> dict:
    root, latest, m = off["root"], off["latest"], off["match"]
    return {
        "amount": off["amount"],
        "amount_kind": off["amount_kind"],
        "amount_sold": off["amount_sold"],
        "offering_amount": off["offering_amount"],
        "offering_indefinite": off["offering_indefinite"],
        "date_of_first_sale": off["first_sale"].isoformat(),
        "first_sale_reported": off["first_sale_reported"],
        "days_since_first_sale": (today - off["first_sale"]).days,
        "file_date": root["file_date"].isoformat(),
        "latest_file_date": latest["file_date"].isoformat(),
        "amendments": off["amendments"],
        "offerings_in_window": off["offerings_in_window"],
        "accession": root["adsh"],
        "latest_accession": latest["adsh"],
        "filing_url": config.FILING_INDEX_URL.format(
            cik=root["cik"], adsh_nodash=root["adsh"].replace("-", ""), adsh=root["adsh"]
        ),
        "issuer_name": root["entity_name"],
        "issuer_cik": root["cik"],
        "issuer_city": root["city"],
        "issuer_state": root["state"],
        "industry_group": root["industry_group"],
        "match_rung": m["rung"],
        "match_confidence": m["confidence"],
        "a16z_person": m.get("a16z_person"),
    }


def _off_network_row(company: dict, off: dict, today: date) -> dict | None:
    if (company.get("name") or "").strip().lower() == "stealth":
        return None
    days = (today - off["first_sale"]).days
    return {
        "on_network": False,
        "slug": company["slug"],
        "name": company["name"],
        "tier": company["tier"],
        "cohort": company.get("cohort"),
        "url": company.get("url"),
        "website": company.get("website"),
        "location": company.get("location"),
        "blurb": company.get("blurb"),
        "logo": company.get("logo"),
        "open_roles": None,
        "roles_since_first_sale": None,
        "roles_posted_30d": None,
        "roles_posted_7d": None,
        # Cash and recency only: open roles are not tracked off the network.
        "score": score(off["amount"], 0, days),
        **_filing_fields(off, today),
    }


def _spv_groups(window_start: date, today: date) -> dict[str, list[dict]]:
    if not config.SPV_FILINGS.exists():
        return {}
    from .spv import load_ignore

    ignore = load_ignore()
    groups: dict[str, list[dict]] = {}
    for r in pl.read_parquet(config.SPV_FILINGS).iter_rows(named=True):
        if r["slug"] not in ignore and window_start <= r["file_date"] <= today:
            groups.setdefault(r["slug"], []).append(r)
    return groups


def _spv_row(company: dict, group: list[dict], detail: dict | None, on_network: bool, has_direct: bool, today: date) -> dict:
    # One entry per vehicle (CIK); an amendment updates its vehicle.
    by_vehicle: dict[str, dict] = {}
    for f in sorted(group, key=lambda x: (x["file_date"], x["adsh"])):
        by_vehicle[f["cik"]] = f
    vehicles = sorted(by_vehicle.values(), key=lambda x: x["file_date"], reverse=True)
    first = min(v["file_date"] for v in vehicles)
    jobs = (detail or {}).get("jobs") or []
    since = [d for d in (_parse_ts(j.get("published_at")) for j in jobs) if d and d >= first]
    return {
        "slug": company["slug"],
        "name": company["name"],
        "tier": company["tier"],
        "cohort": company.get("cohort"),
        "on_network": on_network,
        "has_own_form_d": has_direct,
        "url": company.get("url") if on_network else (company.get("website") or company.get("url")),
        "logo": company.get("logo"),
        "blurb": company.get("blurb"),
        "location": company.get("location"),
        "stage": company.get("stage"),
        "open_roles": company.get("open_roles") if on_network else None,
        "roles_since_first_spv": len(since) if on_network else None,
        "spvs": len(vehicles),
        "spv_amount_sold": sum(v["total_amount_sold"] or 0 for v in vehicles),
        "first_spv_file_date": first.isoformat(),
        "latest_spv_file_date": vehicles[0]["file_date"].isoformat(),
        "days_since_latest_spv": (today - vehicles[0]["file_date"]).days,
        "vehicles": [
            {
                "name": v["spv_name"],
                "file_date": v["file_date"].isoformat(),
                "amount_sold": v["total_amount_sold"],
                "filing_url": config.FILING_INDEX_URL.format(
                    cik=v["cik"], adsh_nodash=v["adsh"].replace("-", ""), adsh=v["adsh"]
                ),
            }
            for v in vehicles
        ],
    }


SPV_CSV_FIELDS = [
    "rank", "name", "slug", "tier", "on_network", "has_own_form_d", "spvs", "spv_amount_sold",
    "first_spv_file_date", "latest_spv_file_date", "open_roles", "roles_since_first_spv", "roles_posted_30d", "url", "vehicle_names",
]


def _spv_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=SPV_CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({**r, "vehicle_names": " | ".join(v["name"] for v in r["vehicles"])})
    return buf.getvalue()


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({**r, "score": f"{r['score']:.4f}"})
    return buf.getvalue()


def _append_history(today: date, rows: list[dict]) -> None:
    fresh = pl.DataFrame(
        [
            {
                "run_date": today,
                "slug": r["slug"],
                "accession": r["accession"],
                "date_of_first_sale": date.fromisoformat(r["date_of_first_sale"]),
                "open_roles": r["open_roles"],
                "roles_since_first_sale": r["roles_since_first_sale"],
                "roles_posted_30d": r.get("roles_posted_30d"),
                "amount": r["amount"],
                "score": r["score"],
                "rank": r["rank"],
            }
            for r in rows
        ],
        schema={
            "run_date": pl.Date, "slug": pl.Utf8, "accession": pl.Utf8, "date_of_first_sale": pl.Date,
            "open_roles": pl.Int64, "roles_since_first_sale": pl.Int64, "roles_posted_30d": pl.Int64, "amount": pl.Float64,
            "score": pl.Float64, "rank": pl.Int64,
        },
    )
    if config.HISTORY.exists():
        old = pl.read_parquet(config.HISTORY).filter(pl.col("run_date") != today)
        fresh = pl.concat([old, fresh], how="diagonal_relaxed")  # older runs predate roles_posted_30d
    fresh.sort(["run_date", "rank"]).write_parquet(config.HISTORY)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="publish even if High matches dropped sharply")
    args = ap.parse_args()
    run_score(force=args.force)


if __name__ == "__main__":
    main()

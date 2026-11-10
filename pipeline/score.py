"""Step 4: rank High matches and write the three public files.

    score = log10(amount + 1) / (open_roles + 1) * 0.5 ** (days_since_first_sale / 45)

amount is totalAmountSold when nonzero, else totalOfferingAmount (flagged
"offering, not yet sold"). The window (config.WINDOW_DAYS) and the decay both run from
dateOfFirstSale on the original notice; an amendment updates the amount and
nothing else.

Writes:
  public/just-raised.json  the full ranked collection, in the talent network's
                           /collections/{slug} member shape (routes page it)
  public/filings.json      the Form D detail per slug (additive endpoint)
  public/just-raised.csv   every column
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
from .match import HIGH

log = logging.getLogger(__name__)

def collection_description() -> str:
    return f"Portfolio companies with a Form D in the last {config.WINDOW_DAYS} days, ranked by cash per open role"
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


# --- publish ------------------------------------------------------------------


def _previous_high_count() -> int | None:
    if not config.PUBLIC_COLLECTION.exists():
        return None
    try:
        return json.loads(config.PUBLIC_COLLECTION.read_text())["meta"]["high_matches"]
    except (KeyError, ValueError):
        return None


def run_score(force: bool = False, details: dict | None = None) -> dict:
    today = config.today()
    window_start = today - timedelta(days=config.WINDOW_DAYS)
    companies = {c["slug"]: c for c in load_companies()}
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
        if slug not in companies and slug not in registry:
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

    details = details if details is not None else fetch_details(sorted(chosen))

    rows = []
    for slug, off in chosen.items():
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
        root, latest, m = off["root"], off["latest"], off["match"]
        labels = (detail or {}).get("labels") or {}
        rows.append(
            {
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
                "amount": off["amount"],
                "amount_kind": off["amount_kind"],
                "amount_sold": off["amount_sold"],
                "offering_amount": off["offering_amount"],
                "offering_indefinite": off["offering_indefinite"],
                "date_of_first_sale": off["first_sale"].isoformat(),
                "first_sale_reported": off["first_sale_reported"],
                "days_since_first_sale": days,
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
                "roles_since_first_sale": len(since),
                "first_post_since": since[0].isoformat() if since else None,
                "days_to_first_post": (since[0] - off["first_sale"]).days if since else None,
                "match_rung": m["rung"],
                "match_confidence": m["confidence"],
            }
        )

    rows.sort(key=lambda r: (-r["score"], r["name"].lower()))
    for i, r in enumerate(rows, 1):
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
        "lag_assumption": "Postings follow a raise by one to three months. Assumed, not yet measured.",
    }
    collection_doc = {
        "meta": meta,
        "collection": {
            "slug": "just-raised",
            "title": "Just raised",
            "description": collection_description(),
            "group": "signals",
            "url": config.SITE_URL,
            "companies": len(rows),
            "roles": sum(r["open_roles"] for r in rows),
            "portfolio_members": sum(1 for r in rows if r["tier"] in config.PORTFOLIO_TIERS),
            "members": [{k: r[k] for k in MEMBER_FIELDS} for r in rows],
        },
    }
    filing_fields = [k for k in rows[0] if k not in MEMBER_FIELDS or k in ("rank", "slug", "name", "tier")] if rows else []
    filings_doc = {
        "meta": meta,
        "filings": {r["slug"]: {k: r[k] for k in filing_fields} for r in rows},
    }

    config.PUBLIC.mkdir(parents=True, exist_ok=True)
    config.PUBLIC_COLLECTION.write_text(json.dumps(collection_doc, indent=1, ensure_ascii=False) + "\n")
    config.PUBLIC_FILINGS.write_text(json.dumps(filings_doc, indent=1, ensure_ascii=False) + "\n")
    config.PUBLIC_CSV.write_text(to_csv(rows))
    _append_history(today, rows)
    log.info("score: %d companies published (%d High pairs in window)", len(rows), high_pairs_in_window)
    return collection_doc


CSV_FIELDS = [
    "rank", "name", "slug", "tier", "cohort", "stage", "stage_label", "size_label", "location",
    "score", "amount", "amount_kind", "amount_sold", "offering_amount", "date_of_first_sale",
    "days_since_first_sale", "file_date", "latest_file_date", "amendments", "open_roles",
    "roles_since_first_sale", "first_post_since", "days_to_first_post", "issuer_name",
    "issuer_cik", "issuer_city", "issuer_state", "accession", "filing_url", "url", "match_rung",
]


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
                "amount": r["amount"],
                "score": r["score"],
                "rank": r["rank"],
            }
            for r in rows
        ],
        schema={
            "run_date": pl.Date, "slug": pl.Utf8, "accession": pl.Utf8, "date_of_first_sale": pl.Date,
            "open_roles": pl.Int64, "roles_since_first_sale": pl.Int64, "amount": pl.Float64,
            "score": pl.Float64, "rank": pl.Int64,
        },
    )
    if config.HISTORY.exists():
        old = pl.read_parquet(config.HISTORY).filter(pl.col("run_date") != today)
        fresh = pl.concat([old, fresh])
    fresh.sort(["run_date", "rank"]).write_parquet(config.HISTORY)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="publish even if High matches dropped sharply")
    args = ap.parse_args()
    run_score(force=args.force)


if __name__ == "__main__":
    main()

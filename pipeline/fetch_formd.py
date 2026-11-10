"""Step 2: index new Form D and D/A filings, then parse the ones that matter.

Two layers:

1. **Index** (data/formd_index.parquet): one cheap row per Form D or D/A
   filing: accession, CIK, name, form, file date, and (from full-text search)
   business state and exemption items. The first run backfills WINDOW_DAYS
   from the quarterly form.idx files; every later run reads EDGAR full-text
   search from the last indexed date (minus a small overlap) to today.

2. **Filings** (data/filings.parquet): the parsed primary_doc.xml for each
   indexed filing that passes the gate. Parsed accessions are never
   refetched, and the raw XML is cached under data/cache/xml.

The gate is the one deviation from the design doc, which downloads every
primary_doc.xml (about 16,000 for a 90-day backfill). Here a filing's XML is
fetched only if its index name is not obviously a fund and reaches
GATE_MIN token_set_ratio against some portfolio company name. GATE_MIN sits
below every rung of the ladder, so the gate never drops a filing the ladder
could have matched. It cuts SEC requests by roughly 50x. The index keeps
every filing, so when a company joins the talent network, the next run gates
its past filings back in. Pass --no-gate to fetch everything.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections.abc import Iterable
from datetime import date, timedelta

import polars as pl
from edgar_names import fund_name_reason, name_variants
from rapidfuzz import fuzz, process

from . import config
from .clients import SecClient
from .fetch_companies import load_companies
from .formd_xml import parse_primary_doc

log = logging.getLogger(__name__)

INDEX_SCHEMA = {
    "adsh": pl.Utf8,
    "cik": pl.Utf8,
    "form": pl.Utf8,
    "index_name": pl.Utf8,
    "file_date": pl.Date,
    "biz_state": pl.Utf8,
    "items": pl.List(pl.Utf8),
    "index_source": pl.Utf8,
}

FILINGS_SCHEMA = {
    "adsh": pl.Utf8,
    "cik": pl.Utf8,
    "form": pl.Utf8,
    "file_date": pl.Date,
    "submission_type": pl.Utf8,
    "entity_name": pl.Utf8,
    "entity_type": pl.Utf8,
    "jurisdiction": pl.Utf8,
    "year_of_inc": pl.Utf8,
    "city": pl.Utf8,
    "state": pl.Utf8,
    "previous_names": pl.List(pl.Utf8),
    "industry_group": pl.Utf8,
    "exemptions": pl.List(pl.Utf8),
    "is_amendment": pl.Boolean,
    "previous_accession": pl.Utf8,
    "date_of_first_sale": pl.Date,
    "first_sale_yet_to_occur": pl.Boolean,
    "total_offering_amount": pl.Float64,
    "offering_indefinite": pl.Boolean,
    "total_amount_sold": pl.Float64,
    "related_persons": pl.List(pl.Utf8),
    "related_surnames": pl.List(pl.Utf8),
    "xml_url": pl.Utf8,
    "fetched_at": pl.Utf8,
}

_IDX_LINE = re.compile(r"^(D|D/A)\s+(.+?)\s{2,}(\d+)\s+(\d{4}-\d{2}-\d{2})\s+(\S+)\s*$")


# --- index ------------------------------------------------------------------


def _quarters(start: date, end: date) -> list[tuple[int, int]]:
    out = []
    y, q = start.year, (start.month - 1) // 3 + 1
    while (y, q) <= (end.year, (end.month - 1) // 3 + 1):
        out.append((y, q))
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)
    return out


def index_from_form_idx(sec: SecClient, start: date, end: date) -> list[dict]:
    """Backfill rows from the static quarterly form.idx files."""
    rows: list[dict] = []
    current = (end.year, (end.month - 1) // 3 + 1)
    for year, q in _quarters(start, end):
        url = config.FORM_INDEX_URL.format(year=year, q=q)
        path = config.CACHE / "form_idx" / f"{year}-QTR{q}.idx"
        # Past quarters never change; the current one grows daily.
        body = sec.get_cached(url, path, refresh=(year, q) == current)
        if body is None:
            continue
        for line in body.decode("latin-1").splitlines():
            m = _IDX_LINE.match(line)
            if not m:
                continue
            form, name, cik, filed, fname = m.groups()
            filed_d = date.fromisoformat(filed)
            if not (start <= filed_d <= end):
                continue
            adsh = fname.rsplit("/", 1)[-1].removesuffix(".txt")
            rows.append(
                {
                    "adsh": adsh,
                    "cik": cik.lstrip("0"),
                    "form": form,
                    "index_name": name.strip(),
                    "file_date": filed_d,
                    "biz_state": None,
                    "items": None,
                    "index_source": "form_idx",
                }
            )
    log.info("form.idx: %d Form D/D-A rows between %s and %s", len(rows), start, end)
    return rows


_DISPLAY_CIK = re.compile(r"\s*\(CIK \d+\)\s*$")


def index_from_efts(sec: SecClient, start: date, end: date) -> list[dict]:
    """Daily pull from EDGAR full-text search.

    The design doc's ``q=*`` returns zero hits (it becomes a phrase match on
    "*"); leaving q out returns every Form D. Results are capped at 10,000 per
    query, so long ranges are split by day.
    """
    rows: list[dict] = []
    day = start
    while day <= end:
        offset = 0
        while True:
            body = sec.get_json(
                config.EFTS_URL,
                params={
                    "forms": "D",
                    "dateRange": "custom",
                    "startdt": day.isoformat(),
                    "enddt": day.isoformat(),
                    "from": offset,
                },
            )
            hits = body.get("hits", {}).get("hits", [])
            for h in hits:
                src = h["_source"]
                names = src.get("display_names") or [""]
                rows.append(
                    {
                        "adsh": src["adsh"],
                        "cik": (src.get("ciks") or [""])[0].lstrip("0"),
                        "form": src.get("form") or src.get("file_type"),
                        "index_name": _DISPLAY_CIK.sub("", names[0]).strip(),
                        "file_date": date.fromisoformat(src["file_date"]),
                        "biz_state": (src.get("biz_states") or [None])[0],
                        "items": src.get("items") or [],
                        "index_source": "efts",
                    }
                )
            total = body.get("hits", {}).get("total", {}).get("value", 0)
            offset += len(hits)
            if not hits or offset >= total or offset >= 10_000:
                break
        day += timedelta(days=1)
    log.info("efts: %d Form D/D-A rows between %s and %s", len(rows), start, end)
    return rows


def _read(path, schema) -> pl.DataFrame:
    if path.exists():
        return pl.read_parquet(path)
    return pl.DataFrame(schema=schema)


def update_index(sec: SecClient, today: date) -> pl.DataFrame:
    index = _read(config.FORMD_INDEX, INDEX_SCHEMA)
    start = today - timedelta(days=config.WINDOW_DAYS)
    new_rows: list[dict] = []
    if index.is_empty():
        new_rows += index_from_form_idx(sec, start, today)
        efts_start = today - timedelta(days=config.EFTS_OVERLAP_DAYS)
    else:
        # A wider window than last run (e.g. 90 -> 180 days) backfills the gap.
        if index["file_date"].min() > start:
            new_rows += index_from_form_idx(sec, start, index["file_date"].min() - timedelta(days=1))
        efts_start = index["file_date"].max() - timedelta(days=config.EFTS_OVERLAP_DAYS)
    new_rows += index_from_efts(sec, max(efts_start, start), today)

    if new_rows:
        fresh = pl.DataFrame(new_rows, schema=INDEX_SCHEMA)
        # Prefer the EFTS row for an accession (it carries state and items).
        index = (
            pl.concat([index, fresh])
            .with_columns(pl.when(pl.col("index_source") == "efts").then(0).otherwise(1).alias("_pref"))
            .sort(["adsh", "_pref"])
            .unique("adsh", keep="first")
            .drop("_pref")
            .sort(["file_date", "adsh"])
        )
    # Nothing filed before the window can have a first sale inside it.
    index = index.filter(pl.col("file_date") >= start)
    config.DATA.mkdir(parents=True, exist_ok=True)
    index.write_parquet(config.FORMD_INDEX)
    log.info("index: %d filings, %s to %s", index.height, index["file_date"].min(), index["file_date"].max())
    return index


# --- gate -------------------------------------------------------------------


def portfolio_name_keys(companies: Iterable[dict]) -> list[str]:
    from .match import company_variants

    keys: set[str] = set()
    for c in companies:
        for v in company_variants(c):
            keys.update({v.strict, v.brand})
    return sorted(k for k in keys if k)


def gate_reason(name: str, items: list[str] | None, keys: list[str]) -> tuple[bool, str]:
    """(fetch?, why). Cheap checks on the index row only."""
    if items and any(i.upper().startswith("3C") for i in items):
        return False, "3(c) fund exclusion"
    variants = name_variants(name)
    key_set = set(keys)
    exact = any(v.strict in key_set or v.brand in key_set for v in variants)
    # Same rule as match.py: an exact portfolio-name hit skips the name-word
    # fund check, so a company called "X Capital" is not thrown away.
    if not exact:
        why = fund_name_reason(name)
        if why:
            return False, why
    else:
        return True, "exact portfolio name"
    best = 0.0
    for v in variants:
        for form in {v.strict, v.brand}:
            hit = process.extractOne(form, keys, scorer=fuzz.token_set_ratio)
            if hit:
                best = max(best, hit[1])
    if best >= config.GATE_MIN:
        return True, f"name candidate ({best:.0f})"
    return False, f"no portfolio name near ({best:.0f})"


# --- fetch + parse ------------------------------------------------------------


def fetch_filings(sec: SecClient, index: pl.DataFrame, today: date, no_gate: bool = False) -> pl.DataFrame:
    filings = _read(config.FILINGS, FILINGS_SCHEMA)
    have = set(filings["adsh"].to_list())
    keys = portfolio_name_keys(load_companies())
    start = today - timedelta(days=config.WINDOW_DAYS)

    todo: list[dict] = []
    gated_out = 0
    for row in index.filter(pl.col("file_date") >= start).iter_rows(named=True):
        if row["adsh"] in have:
            continue
        if not no_gate:
            ok, _ = gate_reason(row["index_name"], row["items"], keys)
            if not ok:
                gated_out += 1
                continue
        todo.append(row)
    log.info("filings: %d already parsed, %d to fetch, %d gated out", len(have), len(todo), gated_out)

    parsed: list[dict] = []
    for n, row in enumerate(todo, 1):
        adsh_nodash = row["adsh"].replace("-", "")
        url = config.PRIMARY_DOC_URL.format(cik=row["cik"], adsh_nodash=adsh_nodash)
        body = sec.get_cached(url, config.CACHE / "xml" / f"{row['adsh']}.xml")
        if body is None:
            log.warning("no primary_doc.xml for %s (%s)", row["adsh"], row["index_name"])
            continue
        try:
            rec = parse_primary_doc(body)
        except Exception as exc:  # malformed XML is rare; skip and log it
            log.warning("could not parse %s: %s", row["adsh"], exc)
            continue
        rec.update(
            {
                "adsh": row["adsh"],
                "cik": rec["cik"] or row["cik"],
                "form": row["form"],
                "file_date": row["file_date"],
                "xml_url": url,
                "fetched_at": config.now_iso(),
            }
        )
        parsed.append(rec)
        if n % 50 == 0:
            log.info("  parsed %d/%d", n, len(todo))

    if parsed:
        filings = pl.concat([filings, pl.DataFrame(parsed, schema=FILINGS_SCHEMA)]).unique("adsh", keep="last")
    filings = filings.sort(["file_date", "adsh"])
    filings.write_parquet(config.FILINGS)
    log.info("filings: %d parsed rows total (%d new), %d SEC requests this run", filings.height, len(parsed), sec.requests)
    return filings


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--no-gate", action="store_true", help="fetch every non-indexed Form D XML (slow)")
    args = ap.parse_args()

    today = config.today()
    sec = SecClient()
    try:
        index = update_index(sec, today)
        fetch_filings(sec, index, today, no_gate=args.no_gate)
    finally:
        sec.close()
    state = json.loads(config.STATE_JSON.read_text()) if config.STATE_JSON.exists() else {}
    state["formd_last_run"] = config.now_iso()
    config.STATE_JSON.write_text(json.dumps(state, indent=1) + "\n")


if __name__ == "__main__":
    main()

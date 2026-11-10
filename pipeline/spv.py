"""Investor SPVs named after a portfolio company.

Most large venture rounds never produce a Form D from the company itself
(Anysphere, Navan and Character.AI have none for their recent rounds), but
the special-purpose vehicles investors form to buy in file constantly:
"HII Anysphere-01, a Series of HII Anysphere LLC", "AVSF - Replit 2026",
"Greenbird Intelligence Fund, LLC, Series W - Shield AI". An SPV filing means
money is being pooled to buy into the company now. That can be a new round or
a purchase of existing shares from employees and early investors, so it is a
weaker hiring signal than the company's own Form D and is published as its
own section.

Matching runs on the issuer name only:

* the name must look like a vehicle (the fund filters say so);
* it must contain exactly one portfolio brand, as whole words. A one-word
  brand counts only if it is rare in English (``SPV_MAX_ZIPF``), so "Titan"
  and "Flow" never match; aliases from aliases.yaml count too;
* the brand must not be the manager's name: "Koru Ventures", "Celo Capital",
  "OpenAI Startup Fund" are rejected because a manager word follows it.

``spv_ignore`` in matches.yaml drops a slug for good.
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta

import polars as pl
import yaml
from edgar_names import fund_name_reason, name_variants
from wordfreq import zipf_frequency

from . import config
from .clients import SecClient
from .formd_xml import parse_primary_doc

log = logging.getLogger(__name__)

# A brand followed by one of these is the vehicle's manager, not its target.
MANAGER_WORDS = (
    "capital", "ventures", "venture", "partners", "management", "holdings", "storage", "asset", "assets",
    "employee", "employees", "startup", "productive", "offshore", "advisors", "group", "investments",
    "secondary", "secondaries", "equity", "opportunity", "opportunities", "income", "credit", "growth",
    "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x",
)
# Words that make a two-word brand distinctive even when the other word is
# common: "Shield AI", "Black Forest Labs".
BRAND_SUFFIXES = {"ai", "labs", "bio", "robotics", "space", "health", "therapeutics", "security", "systems"}
# Program and platform names that appear in many vehicle names.
ALWAYS_IGNORE = {"speedrun"}

SPV_SCHEMA = {
    "adsh": pl.Utf8,
    "cik": pl.Utf8,
    "slug": pl.Utf8,
    "spv_name": pl.Utf8,
    "form": pl.Utf8,
    "file_date": pl.Date,
    "date_of_first_sale": pl.Date,
    "total_amount_sold": pl.Float64,
    "total_offering_amount": pl.Float64,
    "is_amendment": pl.Boolean,
    "xml_url": pl.Utf8,
}


def _clean(text: str) -> str:
    text = re.sub(r"['’]", "", text.lower())
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def brand_phrases(universe: list[dict], ignore: set[str]) -> dict[str, str]:
    """phrase -> slug, for every brand distinctive enough to find in an SPV name."""
    phrases: dict[str, set[str]] = {}
    for c in universe:
        if c["slug"] in ignore:
            continue
        for raw in [c["name"], *(c.get("aliases") or [])]:
            for v in name_variants(raw):
                for form in {v.strict, v.brand}:
                    toks = form.split()
                    if not toks or form in ALWAYS_IGNORE:
                        continue
                    if len(toks) == 1:
                        if len(form) < config.SPV_MIN_LEN or zipf_frequency(form, "en") >= config.SPV_MAX_ZIPF:
                            continue
                    elif all(zipf_frequency(t, "en") >= 4.0 for t in toks):
                        # "digital asset", "series ai": every word is common, unless a
                        # brand suffix sits on a word that is not very common ("shield ai").
                        rest = [t for t in toks if t not in BRAND_SUFFIXES]
                        if not (len(rest) < len(toks) and rest and all(zipf_frequency(t, "en") < 4.6 for t in rest)):
                            continue
                    phrases.setdefault(form, set()).add(c["slug"])
    # A phrase that names two companies cannot pick one.
    return {p: next(iter(s)) for p, s in phrases.items() if len(s) == 1}


def spv_target(name: str, items: list[str] | None, phrases: dict[str, str], patterns: dict[str, re.Pattern]) -> str | None:
    is_vehicle = bool(fund_name_reason(name)) or bool(items and any(i.upper().startswith("3C") for i in items))
    if not is_vehicle:
        return None
    text = _clean(name)
    found = set()
    for phrase, rx in patterns.items():
        for m in rx.finditer(text):
            after = text[m.end():].split()
            if after and after[0] in MANAGER_WORDS:
                continue
            found.add(phrases[phrase])
    return found.pop() if len(found) == 1 else None


def load_ignore() -> set[str]:
    if not config.OVERRIDES_FILE.exists():
        return set()
    raw = yaml.safe_load(config.OVERRIDES_FILE.read_text()) or {}
    return {str(x) for x in raw.get("spv_ignore") or []}


def update_spvs(sec: SecClient, index: pl.DataFrame, universe: list[dict], today: date) -> pl.DataFrame:
    ignore = load_ignore()
    phrases = brand_phrases(universe, ignore)
    patterns = {p: re.compile(r"\b" + re.escape(p) + r"\b") for p in phrases}
    start = today - timedelta(days=config.WINDOW_DAYS)

    have = pl.read_parquet(config.SPV_FILINGS) if config.SPV_FILINGS.exists() else pl.DataFrame(schema=SPV_SCHEMA)
    parsed = {r["adsh"]: r for r in have.iter_rows(named=True)}
    rows = []
    for r in index.filter(pl.col("file_date") >= start).iter_rows(named=True):
        slug = spv_target(r["index_name"], r["items"], phrases, patterns)
        if slug is None:
            continue
        prev = parsed.get(r["adsh"])
        if prev is None:
            url = config.PRIMARY_DOC_URL.format(cik=r["cik"], adsh_nodash=r["adsh"].replace("-", ""))
            body = sec.get_cached(url, config.CACHE / "xml" / f"{r['adsh']}.xml")
            if body is None:
                continue
            try:
                rec = parse_primary_doc(body)
            except Exception as exc:
                log.warning("spv: could not parse %s: %s", r["adsh"], exc)
                continue
            prev = {
                "adsh": r["adsh"], "cik": r["cik"], "spv_name": rec["entity_name"] or r["index_name"],
                "form": r["form"], "file_date": r["file_date"], "date_of_first_sale": rec["date_of_first_sale"],
                "total_amount_sold": rec["total_amount_sold"], "total_offering_amount": rec["total_offering_amount"],
                "is_amendment": rec["is_amendment"], "xml_url": url,
            }
        rows.append({**prev, "slug": slug})  # re-resolve the slug every run

    out = pl.DataFrame(rows, schema=SPV_SCHEMA).sort(["slug", "file_date"])
    out.write_parquet(config.SPV_FILINGS)
    log.info("spv: %d vehicle filings into %d portfolio companies (%d brands searchable)",
             out.height, out["slug"].n_unique(), len(set(phrases.values())))
    return out

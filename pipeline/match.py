"""Step 3: join parsed Form Ds to talent-network companies by name.

Filters, then the match ladder, then human overrides. Writes
data/matches.parquet (every High and Medium pair), review/medium.csv (rows to
check by eye before a publish) and review/low.csv (logged, never shown).

Ladder (first hit wins):

  1  strict normalized names equal                         High
  2  brand-form names equal                                High
  3  token_set >= 95, guard, issuer state = company state  High
  4  token_set >= 90, location match, a related person's
     surname appears in the company blurb                  Medium
  5  token_set >= 90, no corroboration                     Low (dropped)

"guard" is token_sort_ratio >= SUBSET_GUARD_MIN; see config.py. A rung 3
candidate that fails only the guard goes to review as Medium.

Precision rules that demote High to Medium:

* location conflict: rung 1 or 2 hit, but both sides have a known location
  and they disagree ("Gamma, Inc." in Texas vs "Gamma" in San Francisco).
* off-network, no location: rung 1 or 2 against a wider-portfolio company
  (a16z.com or speedrun.a16z.com, not on the talent network) with no location
  to check.
* ambiguous issuer: one filing reaches its best rung against two companies.
* contested company: two different issuers (CIKs) reach High for the same
  company.

One rule that promotes:

* rung P: a Medium from rung 1, 2 or 3 (location conflict, off-network, or
  extra words) becomes High when the Form D lists a member of the a16z
  investing team (a16z.com/team) as a director or officer. Ambiguity and
  contest still apply afterwards.

matches.yaml overrides everything: confirm pins a pair to High, reject and
block_cik remove pairs.
"""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass, field

import polars as pl
from edgar_names import (
    edgar_region,
    is_fund_filing,
    load_overrides,
    name_variants,
    parse_location,
)
from rapidfuzz import fuzz

from . import config
from .fetch_portfolio import load_people, load_universe

log = logging.getLogger(__name__)

HIGH, MEDIUM, LOW = "high", "medium", "low"
_CONF_ORDER = {HIGH: 0, MEDIUM: 1, LOW: 2}
_RUNG_ORDER = {"pinned": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5}


def _strength(confidence: str, rung: str) -> tuple[int, int]:
    """Lower is stronger."""
    return _CONF_ORDER[confidence], _RUNG_ORDER[rung]

MATCH_SCHEMA = {
    "cik": pl.Utf8,
    "slug": pl.Utf8,
    "company_name": pl.Utf8,
    "entity_name": pl.Utf8,
    "rung": pl.Utf8,
    "confidence": pl.Utf8,
    "token_set": pl.Float64,
    "token_sort": pl.Float64,
    "issuer_region": pl.Utf8,
    "company_region": pl.Utf8,
    "location_match": pl.Boolean,
    "surname_hit": pl.Utf8,
    "notes": pl.Utf8,
    "a16z_person": pl.Utf8,
    "on_network": pl.Boolean,
    "adshs": pl.List(pl.Utf8),
}


@dataclass
class Company:
    slug: str
    name: str
    tier: str
    location: str | None
    blurb: str
    region: str | None
    on_network: bool = True
    variants: list = field(default_factory=list)


@dataclass
class Candidate:
    slug: str
    rung: str
    confidence: str
    token_set: float
    token_sort: float
    location_match: bool | None
    surname_hit: str | None
    notes: list[str] = field(default_factory=list)
    a16z_person: str | None = None


def company_variants(c: dict) -> list:
    """The brand name, plus the slug read as a name.

    Slugs often carry the legal name the brand drops ("anduril-industries" for
    Anduril, "arc-boat-company" for Arc Boats), which turns a fuzzy subset match
    into an exact one.
    """
    out = list(name_variants(c["name"]))
    seen = {v.strict for v in out}
    for v in name_variants((c.get("slug") or "").split(":")[-1].replace("-", " ")):
        if v.strict and v.strict not in seen:
            out.append(v)
    return out


def _prep_companies(rows: list[dict]) -> list[Company]:
    out = []
    for c in rows:
        region, _ = parse_location(c.get("location"))
        out.append(
            Company(
                slug=c["slug"],
                name=c["name"],
                tier=c["tier"],
                location=c.get("location"),
                blurb=(c.get("blurb") or ""),
                region=region,
                on_network=c.get("on_network", True),
                variants=company_variants(c),
            )
        )
    return out


def _surname_in_blurb(surnames: list[str], blurb: str) -> str | None:
    words = {w.strip(".,;:()'\"").lower() for w in blurb.split()}
    for s in surnames:
        s_l = s.lower()
        if len(s_l) >= 3 and s_l in words:
            return s
    return None


def person_key(name: str) -> str:
    """'Schuyler (Baker) Tilney' / 'Erin Price-Wright' -> 'schuyler tilney' / 'erin pricewright'."""
    name = re.sub(r"\([^)]*\)", " ", name or "").lower()
    tokens = [re.sub(r"[^a-z]", "", t) for t in name.replace("-", "").split()]
    tokens = [t for t in tokens if len(t) > 1]
    return f"{tokens[0]} {tokens[-1]}" if len(tokens) >= 2 else ""


def a16z_person_on(filing: dict, people: frozenset[str]) -> str | None:
    for p in filing.get("related_persons") or []:
        if person_key(p) in people:
            return p
    return None


def _score_pair(filing_variants, comp: Company) -> tuple[str | None, float, float]:
    """(exact_rung, best token_set, best token_sort) over every variant pair."""
    exact = None
    ts = so = 0.0
    for fv in filing_variants:
        for cv in comp.variants:
            if fv.strict and fv.strict == cv.strict:
                exact = "1"
            elif exact is None and fv.brand and fv.brand == cv.brand:
                exact = "2"
            for a, b in ((fv.strict, cv.strict), (fv.brand, cv.brand)):
                ts = max(ts, fuzz.token_set_ratio(a, b))
                so = max(so, fuzz.token_sort_ratio(a, b))
    return exact, ts, so


def ladder(filing: dict, companies: list[Company], people: frozenset[str] = frozenset()) -> list[Candidate]:
    """Every company this filing reaches on the ladder, best rung first.

    ``people`` is the a16z investing team (person_key form). One of them on the
    Form D as a director or officer corroborates a name match that the ladder
    alone would send to review.
    """
    variants = name_variants(filing["entity_name"] or "")
    issuer_region = edgar_region(filing.get("state"))
    surnames = filing.get("related_surnames") or []
    partner = a16z_person_on(filing, people)
    out: list[Candidate] = []
    for comp in companies:
        exact, ts, so = _score_pair(variants, comp)
        if exact is None and ts < config.RUNG5_MIN:
            continue
        loc_known = issuer_region is not None and comp.region is not None
        loc_match = (issuer_region == comp.region) if loc_known else None
        guard = so >= config.SUBSET_GUARD_MIN
        surname = _surname_in_blurb(surnames, comp.blurb)

        if exact:
            cand = Candidate(comp.slug, exact, HIGH, ts, so, loc_match, surname)
            if loc_match is False:
                cand.confidence = MEDIUM
                cand.notes.append(f"location conflict: issuer {issuer_region}, company {comp.region}")
            elif not comp.on_network and loc_match is None:
                # Wider-portfolio companies often have no location to check, and
                # many are single common words ("Relay", "Trunk"); a bare name
                # match goes to review.
                cand.confidence = MEDIUM
                cand.notes.append("off-network name match, no location to check")
        elif ts >= config.RUNG3_MIN and loc_match and guard:
            cand = Candidate(comp.slug, "3", HIGH, ts, so, loc_match, surname)
        elif ts >= config.RUNG3_MIN and loc_match:
            # Rung 3 by the doc, but the legal name carries extra words
            # ("Anduril Industries" or "Modal Health Group" vs "Modal"). Strings
            # cannot tell those apart, so a person does, once, in matches.yaml.
            cand = Candidate(comp.slug, "3", MEDIUM, ts, so, loc_match, surname, ["extra words: subset guard"])
        elif ts >= config.RUNG4_MIN and loc_match and surname:
            cand = Candidate(comp.slug, "4", MEDIUM, ts, so, loc_match, surname)
        else:
            cand = Candidate(comp.slug, "5", LOW, ts, so, loc_match, surname, [] if guard else ["fails subset guard"])
        # Rung P: a Medium name match (exact, or rung 3 with extra words) with an
        # a16z investing-team member on the Form D is High.
        if partner and cand.confidence == MEDIUM and cand.rung in ("1", "2", "3"):
            cand.confidence = HIGH
            cand.notes.append(f"a16z person on the Form D: {partner}")
        cand.a16z_person = partner
        out.append(cand)

    out.sort(key=lambda c: (*_strength(c.confidence, c.rung), -c.token_set))
    if len(out) > 1 and out[0].confidence == out[1].confidence and out[0].rung == out[1].rung:
        for c in out:
            if c.confidence == HIGH and c.rung == out[0].rung:
                c.confidence = MEDIUM
                c.notes.append("ambiguous: issuer reaches several companies at this rung")
    return out


def _drop_reason(f: dict, exact_name_hit: bool) -> str | None:
    # A filing whose name exactly matches a portfolio company keeps the
    # structural fund checks but skips the name-word check, so an operating
    # company with "Capital" or "Partners" in its brand is not thrown away.
    reason = is_fund_filing(
        "" if exact_name_hit else (f["entity_name"] or ""),
        f.get("industry_group"),
        f.get("entity_type"),
        f.get("exemptions"),
    )
    return reason


def run_match() -> pl.DataFrame:
    companies = _prep_companies(load_universe())
    people = frozenset(k for k in (person_key(n) for n in load_people()) if k)
    by_slug = {c.slug: c for c in companies}
    strict_keys = {v.strict for c in companies for v in c.variants} | {v.brand for c in companies for v in c.variants}
    overrides = load_overrides(config.OVERRIDES_FILE)

    filings = pl.read_parquet(config.FILINGS) if config.FILINGS.exists() else pl.DataFrame()
    dropped: dict[str, int] = {}
    pairs: dict[tuple[str, str], dict] = {}
    low_rows: dict[tuple[str, str], dict] = {}

    for f in filings.iter_rows(named=True):
        variants = name_variants(f["entity_name"] or "")
        exact_hit = any(v.strict in strict_keys or v.brand in strict_keys for v in variants)
        reason = _drop_reason(f, exact_hit)
        if reason:
            dropped[reason.split(" '")[0]] = dropped.get(reason.split(" '")[0], 0) + 1
            continue

        cands = ladder(f, companies, people)
        pinned = overrides.confirmed_slug(f["cik"])
        if pinned and pinned in by_slug:
            cands = [c for c in cands if c.slug != pinned]
            cands.insert(0, Candidate(pinned, "pinned", HIGH, 100.0, 100.0, None, None, ["confirmed in matches.yaml"]))
        for c in cands:
            if overrides.is_rejected(f["cik"], c.slug):
                continue
            if c.confidence == LOW:
                low_rows[(f["cik"], c.slug)] = _review_row(f, by_slug[c.slug], c)
                continue
            key = (f["cik"], c.slug)
            prev = pairs.get(key)
            row = {
                "cik": f["cik"],
                "slug": c.slug,
                "company_name": by_slug[c.slug].name,
                "entity_name": f["entity_name"],
                "rung": c.rung,
                "confidence": c.confidence,
                "token_set": c.token_set,
                "token_sort": c.token_sort,
                "issuer_region": edgar_region(f.get("state")),
                "company_region": by_slug[c.slug].region,
                "location_match": c.location_match,
                "surname_hit": c.surname_hit,
                "notes": "; ".join(c.notes),
                "a16z_person": c.a16z_person,
                "on_network": by_slug[c.slug].on_network,
                "adshs": [f["adsh"]],
                "_filing": f,
            }
            if prev is None:
                pairs[key] = row
            else:
                # One row per (issuer, company): every accession, strongest evidence.
                row["adshs"] = sorted(set(prev["adshs"]) | {f["adsh"]})
                if _strength(row["confidence"], row["rung"]) < _strength(prev["confidence"], prev["rung"]):
                    pairs[key] = row
                else:
                    prev["adshs"] = row["adshs"]

    # Contested company: two issuers reach High for one slug -> both to review,
    # unless one of them is pinned.
    high_by_slug: dict[str, list[tuple[str, str]]] = {}
    for key, row in pairs.items():
        if row["confidence"] == HIGH:
            high_by_slug.setdefault(row["slug"], []).append(key)
    for slug, keys in high_by_slug.items():
        ciks = {k[0] for k in keys}
        if len(ciks) > 1 and not any(pairs[k]["rung"] == "pinned" for k in keys):
            for k in keys:
                pairs[k]["confidence"] = MEDIUM
                pairs[k]["notes"] = "; ".join(
                    x for x in (pairs[k]["notes"], f"contested: {len(ciks)} issuers reach High for {slug}") if x
                )

    rows = list(pairs.values())
    medium = [r for r in rows if r["confidence"] == MEDIUM]
    matches = pl.DataFrame([{k: v for k, v in r.items() if k != "_filing"} for r in rows], schema=MATCH_SCHEMA)
    matches = matches.sort(["confidence", "slug", "cik"])
    config.DATA.mkdir(parents=True, exist_ok=True)
    matches.write_parquet(config.MATCHES)

    _write_review(config.REVIEW / "medium.csv", [_review_row(r["_filing"], by_slug[r["slug"]], r) for r in medium])
    _write_review(config.REVIEW / "low.csv", list(low_rows.values()))

    n_high = sum(1 for r in rows if r["confidence"] == HIGH)
    log.info(
        "match: %d filings in, %d dropped as funds %s, %d High pairs, %d Medium for review, %d Low logged",
        filings.height,
        sum(dropped.values()),
        dropped,
        n_high,
        len(medium),
        len(low_rows),
    )
    return matches


REVIEW_FIELDS = [
    "confidence",
    "rung",
    "notes",
    "company_name",
    "slug",
    "tier",
    "company_location",
    "entity_name",
    "cik",
    "issuer_city",
    "issuer_state",
    "entity_type",
    "year_of_inc",
    "related_persons",
    "a16z_person",
    "on_network",
    "total_amount_sold",
    "date_of_first_sale",
    "token_set",
    "token_sort",
    "company_blurb",
    "edgar_url",
    "talent_url",
    "yaml_confirm",
    "yaml_reject",
]


def _review_row(f: dict, comp: Company, c) -> dict:
    get = (lambda k: c[k]) if isinstance(c, dict) else (lambda k: getattr(c, k))
    notes = get("notes")
    adsh = f["adsh"]
    return {
        "confidence": get("confidence"),
        "rung": get("rung"),
        "notes": notes if isinstance(notes, str) else "; ".join(notes),
        "company_name": comp.name,
        "slug": comp.slug,
        "tier": comp.tier,
        "company_location": comp.location,
        "entity_name": f["entity_name"],
        "cik": f["cik"],
        "issuer_city": f.get("city"),
        "issuer_state": f.get("state"),
        "entity_type": f.get("entity_type"),
        "year_of_inc": f.get("year_of_inc"),
        "related_persons": "; ".join(f.get("related_persons") or []),
        "a16z_person": get("a16z_person"),
        "on_network": comp.on_network,
        "total_amount_sold": f.get("total_amount_sold"),
        "date_of_first_sale": f.get("date_of_first_sale"),
        "token_set": round(get("token_set"), 1),
        "token_sort": round(get("token_sort"), 1),
        "company_blurb": comp.blurb,
        "edgar_url": config.FILING_INDEX_URL.format(cik=f["cik"], adsh_nodash=adsh.replace("-", ""), adsh=adsh),
        "talent_url": f"https://speedrun-talent-network.com/companies/{comp.slug}" if comp.on_network else "",
        "yaml_confirm": f'- {{cik: "{f["cik"]}", slug: {comp.slug}, note: ""}}',
        "yaml_reject": f'- {{cik: "{f["cik"]}", slug: {comp.slug}, note: ""}}',
    }


def _write_review(path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: (r["company_name"].lower(), r["cik"]))
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=REVIEW_FIELDS)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    run_match()


if __name__ == "__main__":
    main()


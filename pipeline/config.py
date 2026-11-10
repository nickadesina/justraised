"""Every tunable number and path in the pipeline, in one place.

The README quotes these values; change them here and update it there.
"""

from __future__ import annotations

import os
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
PUBLIC = ROOT / "public"
REVIEW = ROOT / "review"
OVERRIDES_FILE = ROOT / "matches.yaml"
ALIASES_FILE = ROOT / "aliases.yaml"

COMPANIES_JSON = DATA / "companies.json"
REGISTRY_JSON = DATA / "company_registry.json"
UNIVERSE_JSON = DATA / "portfolio_universe.json"
PEOPLE_JSON = DATA / "a16z_people.json"
SPV_FILINGS = DATA / "spv_filings.parquet"
FORMD_INDEX = DATA / "formd_index.parquet"
FILINGS = DATA / "filings.parquet"
MATCHES = DATA / "matches.parquet"
HISTORY = DATA / "history.parquet"
STATE_JSON = DATA / "state.json"

# GitHub Pages serves static files only, so the "endpoints" are files whose
# paths mirror the API: /api/collections/just-raised.json is byte-for-byte the
# response their GET /api/v1/collections/{slug} would return.
PUBLIC_API = PUBLIC / "api"
PUBLIC_COLLECTION = PUBLIC_API / "collections" / "just-raised.json"
PUBLIC_FILINGS = PUBLIC_API / "just-raised" / "filings.json"
PUBLIC_CSV = PUBLIC_API / "just-raised.csv"
PUBLIC_SPV_CSV = PUBLIC_API / "just-raised-spvs.csv"
PUBLIC_BOARD = PUBLIC_API / "just-raised" / "board.json"

# --- talent network ---------------------------------------------------------
TALENT_SITE = "https://speedrun-talent-network.com"
TALENT_BASE = f"{TALENT_SITE}/api/v1"
SOURCE_TAG = "just-raised"  # their attribution ask: ?source= on every call
TALENT_MAX_RPS = 1.0
PORTFOLIO_TIERS = ("speedrun", "a16z")  # market tier is not the portfolio
# A public company's Form D (Roblox's in June 2026) is deal consideration or a
# private placement, not a venture round that precedes hiring.
EXCLUDE_STAGES = ("public",)
# Collections that carry stage / remote_policy / functions / cities for every
# portfolio company in one paged call, instead of one detail call per company.
PORTFOLIO_COLLECTIONS = ("speedrun-companies", "a16z-portfolio")

# --- EDGAR ------------------------------------------------------------------
# SEC fair access: a descriptive User-Agent with a contact address. Set
# SEC_USER_AGENT="Just Raised you@example.com" locally and as a repository
# variable in GitHub Actions.
SEC_USER_AGENT = os.environ.get("SEC_USER_AGENT", "just-raised-pipeline/0.1 (research)")
SEC_MAX_RPS = 8.0  # SEC allows 10; stay under it
EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
FORM_INDEX_URL = "https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{q}/form.idx"
PRIMARY_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{adsh_nodash}/primary_doc.xml"
FILING_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{adsh_nodash}/{adsh}-index.htm"
EFTS_OVERLAP_DAYS = 3  # re-read the last few days; EFTS indexes late sometimes

# --- window and score -------------------------------------------------------
# The design doc's plan is 90 days, with 180 as the fallback when the list is
# thin (under 20 High matches). The first backfill on 2026-11-10 found 3 at 90
# days and 5 at 180, so v1 runs at 180. JUST_RAISED_WINDOW_DAYS=90 switches
# back; the page header and collection description read it from the data.
WINDOW_DAYS = int(os.environ.get("JUST_RAISED_WINDOW_DAYS", "180"))
HALF_LIFE_DAYS = 45

# --- matcher ----------------------------------------------------------------
RUNG3_MIN = 95  # token_set_ratio, plus state match -> High
RUNG4_MIN = 90  # token_set_ratio, plus location and a founder surname in blurb -> Medium
RUNG5_MIN = 90  # token_set_ratio, no corroboration -> Low (dropped)
# token_set_ratio scores 100 whenever one name's tokens are a subset of the
# other's: "modal health group" vs "modal", but also "anduril industries" vs
# "anduril". A rung 3 hit must also clear this token_sort_ratio bar to be
# High; one that clears only token_set goes to review as Medium.
SUBSET_GUARD_MIN = 85
# Before downloading a filing's XML, its index name must reach this
# token_set_ratio against some portfolio company. Lower than every rung, so
# the gate never drops a filing the ladder could have matched.
GATE_MIN = 85

# --- investor SPVs -----------------------------------------------------------
# A single-word brand is distinctive enough to find inside an SPV's name only
# if it is rare in English (wordfreq Zipf scale: "saronic" 1.4, "titan" 3.7).
SPV_MAX_ZIPF = 2.5
SPV_MIN_LEN = 4

# --- publish guardrail ------------------------------------------------------
MAX_HIGH_DROP = 0.30  # refuse to publish if High matches fall more than this

SITE_URL = os.environ.get("JUST_RAISED_SITE_URL", "https://nickadesina.github.io/justraised")


def today() -> date:
    """Run date. JUST_RAISED_TODAY=YYYY-MM-DD pins it for tests and replays."""
    pinned = os.environ.get("JUST_RAISED_TODAY")
    if pinned:
        return date.fromisoformat(pinned)
    return datetime.now(UTC).date()


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
